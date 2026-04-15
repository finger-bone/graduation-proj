import gradio as gr
import time
import torch
import json
import pandas as pd
import numpy as np
import imageio
import tempfile
from threading import Thread

from diffusers import DiffusionPipeline
from heteronym.server.db.client import TorchModel, OffloadConfig
from heteronym.config import DEBUG, get_device

if DEBUG:
    torch.cuda.reset_peak_memory_stats = lambda *args, **kwargs: None
    torch.cuda.memory_allocated = lambda *args, **kwargs: 2
    torch.cuda.max_memory_allocated = lambda *args, **kwargs: 2


# =========================
# Offload config
# =========================
def create_config(config: OffloadConfig, model: TorchModel):
    quantization_config = {
        "quantize": config.quantize,
        "quantize_dtype": config.quantize_dtype,
        "enable_scale": config.enable_scale,
        "enable_bias": config.enable_bias,
    }

    offload_layers = json.loads(config.offload_layers)
    scan_results = model.scan_results
    offload_config = {}

    for key, layers_list in offload_layers.items():
        if key not in scan_results:
            continue

        memory_info = scan_results[key]["memory"]
        total_bytes = 0
        valid_layers = []

        for layer in layers_list:
            valid_layers.append(layer)
            if layer in memory_info:
                total_bytes += memory_info[layer]

        offload_config[key] = {
            "layers": [
                f"{key}.{i}.{layer}"
                for layer in valid_layers
                for i in range(int(scan_results[key]["module_list_len"][key]))
            ],
            "bytes": total_bytes,
        }

    return {
        "quantization": quantization_config,
        "offload": offload_config
    }


# =========================
# Video helper
# =========================
def frames_to_video(frames, fps=8):
    """将 diffusers frames 转为 mp4，处理维度和格式问题"""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    
    # 1. 确保是 Numpy 数组
    if isinstance(frames, torch.Tensor):
        # 移出 GPU 并转为 float32 处理
        frames = frames.cpu().float().numpy()
    elif isinstance(frames, list):
        # 如果是 PIL 图像列表，先转为 numpy 堆栈
        if len(frames) > 0 and not isinstance(frames[0], np.ndarray):
            frames = np.stack([np.array(f) for f in frames])
        else:
            frames = np.array(frames)

    # 2. 处理维度 (Squeeze batch dimension if exists)
    if frames.ndim == 5: # (1, F, C, H, W)
        frames = frames[0]
        
    # 3. 核心修复：检查通道位置 (C, H, W) -> (H, W, C)
    # Diffusers 视频张量通常是 (F, C, H, W)
    if frames.ndim == 4 and frames.shape[1] in [1, 3, 4]:
        frames = frames.transpose(0, 2, 3, 1)

    # 4. 归一化到 0-255 并转为 uint8
    if frames.max() <= 1.01:
        frames = (frames * 255).clip(0, 255).astype(np.uint8)
    else:
        frames = frames.astype(np.uint8)

    # 5. 写入视频
    imageio.mimsave(path, frames, fps=fps, macro_block_size=1)
    return path


# =========================
# UI
# =========================
def create_ui(
    model_info: TorchModel,
    offload_config: OffloadConfig = None,
    enable_offload: bool = False,
    device_id: int = 0
):
    device = get_device(device_id)

    hf_path = model_info.hf_name.removeprefix("pipe:")

    # =========================
    # Load T2V Pipeline
    # =========================
    pipe = DiffusionPipeline.from_pretrained(
        hf_path,
        torch_dtype=torch.float16,
        cache_dir=model_info.path,
        use_safetensors=True
    )

    # =========================
    # Offload
    # =========================
    if enable_offload:
        offload_conf = create_config(offload_config, model_info)
        from heteronym.offload.setup_config import setup_from_config

        target_model = getattr(pipe, "unet", None) or getattr(pipe, "transformer", None)

        if target_model:
            setup_from_config(target_model, json.dumps(offload_conf), device)

            seen = set()
            for attr_name in dir(pipe):
                if attr_name.startswith("__"):
                    continue

                try:
                    attr = getattr(pipe, attr_name)
                except Exception:
                    continue

                if id(attr) in seen:
                    continue
                seen.add(id(attr))

                if attr is target_model:
                    continue

                if isinstance(attr, torch.nn.Module):
                    try:
                        attr.to(device)
                    except Exception:
                        pass
        else:
            pipe.to(device)
    else:
        pipe = pipe.to(device)

    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    stop_generation = False

    # =========================
    # inference
    # =========================
    def infer(prompt, steps, cfg_scale, fps, num_frames, seed):
        nonlocal stop_generation
        stop_generation = False

        generator = (
            torch.Generator(device=device).manual_seed(int(seed))
            if seed != -1 else None
        )

        result_container = {"video": None, "error": None}
        start_time = time.time()
        memory_data = []

        def run_generation():
            try:
                out = pipe(
                    prompt=prompt,
                    num_inference_steps=int(steps),
                    guidance_scale=float(cfg_scale),
                    num_frames=int(num_frames),
                    generator=generator
                )

                # 兼容不同 T2V pipeline
                frames = None
                if hasattr(out, "frames"):
                    frames = out.frames
                elif isinstance(out, dict) and "frames" in out:
                    frames = out["frames"]
                elif hasattr(out, "videos"):
                    frames = out.videos[0]
                else:
                    frames = out[0]

                result_container["video"] = frames_to_video(frames, fps=fps)

            except Exception as e:
                result_container["error"] = str(e)

        thread = Thread(target=run_generation)
        thread.start()

        while thread.is_alive():
            if stop_generation:
                yield None, pd.DataFrame(memory_data), "停止中..."
                break

            elapsed = time.time() - start_time

            if not DEBUG:
                current_mem = torch.cuda.memory_allocated(device) / 1024**2
                peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2
            else:
                current_mem = 1024.0
                peak_mem = 2048.0

            memory_data.append({
                "time": elapsed,
                "current_memory": current_mem,
                "peak_memory": peak_mem
            })

            yield None, pd.DataFrame(memory_data), (
                f"🎬 生成视频中... {elapsed:.1f}s | "
                f"📦 {current_mem:.2f} MB | "
                f"📈 峰值 {peak_mem:.2f} MB"
            )

            time.sleep(0.5)

        if result_container["error"]:
            yield None, pd.DataFrame(memory_data), result_container["error"]
        else:
            yield result_container["video"], pd.DataFrame(memory_data), "✅ 完成"

    def stop_infer():
        nonlocal stop_generation
        stop_generation = True
        return "已发送停止"

    # =========================
    # UI
    # =========================
    with gr.Blocks() as demo:
        gr.Markdown(f"# 🎬 Text-to-Video Diffusers Offload ({model_info.hf_name})")

        with gr.Row():
            with gr.Column():
                prompt = gr.Textbox(label="Prompt", lines=3)

                with gr.Accordion("参数", open=True):
                    steps = gr.Slider(1, 100, 30, step=1, label="Steps")
                    cfg_scale = gr.Slider(1.0, 20.0, 7.5, step=0.5, label="CFG")
                    fps = gr.Slider(1, 30, 8, step=1, label="FPS")
                    num_frames = gr.Slider(8, 64, 16, step=1, label="Frames")
                    seed = gr.Number(value=-1, label="Seed")

                btn = gr.Button("🚀 生成视频", variant="primary")
                stop_btn = gr.Button("🛑 停止")

            with gr.Column():
                out_video = gr.Video(label="生成结果")
                status = gr.Textbox(label="状态")
                plot = gr.LinePlot(
                    x="time",
                    y="current_memory",
                    title="显存占用"
                )

        btn.click(
            infer,
            inputs=[prompt, steps, cfg_scale, fps, num_frames, seed],
            outputs=[out_video, plot, status]
        )

        stop_btn.click(stop_infer, outputs=status)

    return demo