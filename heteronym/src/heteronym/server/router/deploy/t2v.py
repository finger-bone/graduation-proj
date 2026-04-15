import gradio as gr
import time
import torch
import json
from threading import Thread

from diffusers import DiffusionPipeline

from heteronym.server.db.client import TorchModel, OffloadConfig
from heteronym.config import DEBUG, get_device

if DEBUG:
    torch.cuda.reset_peak_memory_stats = lambda *args, **kwargs: None
    torch.cuda.memory_allocated = lambda *args, **kwargs: 2
    torch.cuda.max_memory_allocated = lambda *args, **kwargs: 2


# =========================
# offload config（复用）
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
                for i in range(int(model.scan_results[key]["module_list_len"][key]))
            ],
            "bytes": total_bytes,
        }

    return {"quantization": quantization_config, "offload": offload_config}


# =========================
# UI 构建
# =========================
def create_ui(
    model_info: TorchModel,
    offload_config: OffloadConfig = None,
    enable_offload: bool = False,
    device: int = 0
):
    device = get_device(device)

    # =========================
    # 加载视频模型
    # =========================
    pipe = DiffusionPipeline.from_pretrained(
        model_info.hf_name.removeprefix("pipe:"),
        cache_dir=model_info.path,
    )

    # ⚠️ 文生视频核心模块
    video_module = pipe.unet if hasattr(pipe, "unet") else pipe.transformer

    if enable_offload:
        offload_conf = create_config(offload_config, model_info)
        from heteronym.offload.setup_config import setup_from_config
        setup_from_config(video_module, json.dumps(offload_conf))
    else:
        pipe = pipe.to(device)

    pipe.enable_attention_slicing()

    if not DEBUG:
        torch.cuda.reset_peak_memory_stats(device)

    stop_generation = False

    # =========================
    # 推理函数
    # =========================
    def infer(prompt):
        nonlocal stop_generation
        stop_generation = False

        start_time = time.time()

        video_frames = None

        def run():
            nonlocal video_frames
            result = pipe(
                prompt,
                num_inference_steps=30,
                num_frames=16,        # 👈 关键参数
                guidance_scale=7.5,
            )
            video_frames = result.frames

        thread = Thread(target=run)
        thread.start()

        # 实时状态刷新
        while thread.is_alive():
            if stop_generation:
                return None, "已停止生成"

            elapsed = time.time() - start_time

            # 显存监控 (DEBUG 模式下使用占位值)
            if not DEBUG:
                current_mem = torch.cuda.memory_allocated(device) / 1024**2
                peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2
            else:
                current_mem = 0
                peak_mem = 0

            status = (
                f"⏳ 生成视频中... {elapsed:.2f}s | "
                f"📦 当前显存：{current_mem:.2f} MB | "
                f"📈 峰值显存：{peak_mem:.2f} MB"
            )

            yield None, status
            time.sleep(0.2)

        # =========================
        # frames → video (mp4)
        # =========================
        import imageio
        import numpy as np
        video_path = "/tmp/output.mp4"

        imageio.mimsave(
            video_path,
            [np.array(f) for f in video_frames],
            fps=8
        )

        elapsed = time.time() - start_time

        if not DEBUG:
            current_mem = torch.cuda.memory_allocated(device) / 1024**2
            peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2
        else:
            current_mem = 0
            peak_mem = 0

        status = (
            f"✅ 完成 | ⏱ {elapsed:.2f}s | "
            f"📦 当前显存：{current_mem:.2f} MB | "
            f"📈 峰值显存：{peak_mem:.2f} MB"
        )

        yield video_path, status

    def stop_infer():
        nonlocal stop_generation
        stop_generation = True
        return "已停止生成"

    # =========================
    # Gradio UI
    # =========================
    with gr.Blocks() as demo:
        gr.Markdown("# 🎬 Text-to-Video Demo")

        with gr.Row():
            inp = gr.Textbox(label="Prompt", lines=3)

        with gr.Row():
            out = gr.Video(label="生成视频")

        status = gr.Textbox(label="性能监控")

        with gr.Row():
            btn = gr.Button("生成")
            stop_btn = gr.Button("停止")

        btn.click(
            infer,
            inputs=inp,
            outputs=[out, status]
        )

        stop_btn.click(
            stop_infer,
            inputs=[],
            outputs=[status]
        )

    return demo
