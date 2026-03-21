import gradio as gr
import time
import torch
import json
from threading import Thread

from diffusers import StableDiffusionPipeline

from heteronym.server.db.client import TorchModel, OffloadConfig

DEBUG = False
if DEBUG:
    torch.cuda.reset_peak_memory_stats = lambda *args, **kwargs: None
    torch.cuda.memory_allocated = lambda *args, **kwargs: 2
    torch.cuda.max_memory_allocated = lambda *args, **kwargs: 2


# =========================
# 复用你的 offload config
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
    device = torch.device(f"cuda:{device}") if not DEBUG else torch.device("mps")

    # =========================
    # 加载 Diffusers pipeline
    # =========================
    pipe = StableDiffusionPipeline.from_pretrained(
        model_info.hf_name,
        cache_dir=model_info.path,
    )


    if enable_offload:
        offload_conf = create_config(offload_config, model_info)
        from heteronym.offload.setup_config import setup_from_config
        setup_from_config(pipe.unet if hasattr(pipe, "unet") else pipe.transformer, json.dumps(offload_conf))
    else:
        pipe = pipe.to(device)

    pipe.enable_attention_slicing()  # 降显存

    torch.cuda.reset_peak_memory_stats(device)

    # 停止标志
    stop_generation = False

    # =========================
    # 推理函数（文生图）
    # =========================
    def infer(prompt):
        nonlocal stop_generation
        stop_generation = False

        start_time = time.time()

        try:
            image = None

            def run():
                nonlocal image
                image = pipe(
                    prompt,
                    num_inference_steps=30,
                    guidance_scale=7.5
                ).images[0]

            thread = Thread(target=run)
            thread.start()

            while thread.is_alive():
                if stop_generation:
                    return None, "已停止生成"

                elapsed = time.time() - start_time

                current_mem = torch.cuda.memory_allocated(device) / 1024**2
                peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2

                status = (
                    f"⏳ 生成中... {elapsed:.2f}s | "
                    f"📦 当前显存: {current_mem:.2f} MB | "
                    f"📈 峰值显存: {peak_mem:.2f} MB"
                )

                yield None, status
                time.sleep(0.1)

            elapsed = time.time() - start_time

            current_mem = torch.cuda.memory_allocated(device) / 1024**2
            peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2

            status = (
                f"✅ 完成 | ⏱ {elapsed:.2f}s | "
                f"📦 当前显存: {current_mem:.2f} MB | "
                f"📈 峰值显存: {peak_mem:.2f} MB"
            )

            yield image, status

        except Exception as e:
            yield None, f"生成失败: {str(e)}"

    def stop_infer():
        nonlocal stop_generation
        stop_generation = True
        return "已停止生成"

    # =========================
    # Gradio UI
    # =========================
    with gr.Blocks() as demo:
        gr.Markdown("# 🎨 Diffusers 文生图 Demo")

        with gr.Row():
            inp = gr.Textbox(label="Prompt", lines=3)

        with gr.Row():
            out = gr.Image(label="生成图像")

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