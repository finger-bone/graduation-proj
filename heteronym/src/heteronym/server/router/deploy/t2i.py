import gradio as gr
import time
import torch
import json
import pandas as pd
from threading import Thread

from diffusers import StableDiffusionPipeline, DiffusionPipeline
from heteronym.server.db.client import TorchModel, OffloadConfig
from heteronym.config import DEBUG, get_device

if DEBUG:
    torch.cuda.reset_peak_memory_stats = lambda *args, **kwargs: None
    torch.cuda.memory_allocated = lambda *args, **kwargs: 2
    torch.cuda.max_memory_allocated = lambda *args, **kwargs: 2

# =========================
# 复用 Offload 配置解析
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

        # 这里的 module_list_len 需要根据 diffusers 的结构匹配
        offload_config[key] = {
            "layers": [
                f"{key}.{i}.{layer}"
                for layer in valid_layers
                for i in range(int(scan_results[key]["module_list_len"][key]))
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
    device_id: int = 0
):
    device = get_device(device_id)

    # 1. 加载 Diffusers Pipeline
    # 移除前缀以便正常识别路径/名称
    hf_path = model_info.hf_name.removeprefix("pipe:")
    
    # 自动选择加载类 (使用 Pipeline 可以兼容 SD, SDXL, Flux 等)
    pipe = DiffusionPipeline.from_pretrained(
        hf_path,
        torch_dtype=torch.float16,
        cache_dir=model_info.path,
        use_safetensors=True
    )

    # 2. 处理 Offload 逻辑
    if enable_offload:
        offload_conf = create_config(offload_config, model_info)
        from heteronym.offload.setup_config import setup_from_config
        
        # 核心修改：判断是 UNet (SD) 还是 Transformer (Flux/SD3)
        target_model = getattr(pipe, "unet", None) or getattr(pipe, "transformer", None)
        
        if target_model:
            # 将 offload 应用到核心计算组件上
            setup_from_config(target_model, json.dumps(offload_conf), device)
            # for every attribute that is a pytorch model but not unet or transformer, move it to the device
            seen = set()
            for attr_name in dir(pipe):
                if attr_name.startswith("__"):
                    continue

                try:
                    attr = getattr(pipe, attr_name)
                except Exception:
                    continue

                # 避免重复处理（尤其是 property / descriptor）
                if id(attr) in seen:
                    continue
                seen.add(id(attr))

                # 跳过 backbone
                if attr is target_model:
                    continue

                # 只处理 torch module
                if isinstance(attr, torch.nn.Module):
                    try:
                        attr.to(device)
                    except Exception:
                        pass
        else:
            pipe.to(device) # 找不到则全量上显存
    else:
        pipe = pipe.to(device)

    # 优化显存使用
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()

    stop_generation = False

    # =========================
    # 推理函数
    # =========================
    def infer(prompt, negative_prompt, steps, cfg_scale, width, height, seed):
        nonlocal stop_generation
        stop_generation = False
        
        generator = torch.Generator(device=device).manual_seed(int(seed)) if seed != -1 else None
        
        result_container = {"image": None, "error": None}
        start_time = time.time()
        memory_data = []

        def run_generation():
            # try:
            if True:
                # 执行生成
                image = pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=int(steps),
                    guidance_scale=float(cfg_scale),
                    width=int(width),
                    height=int(height),
                    generator=generator
                ).images[0]
                result_container["image"] = image
            # except Exception as e:
            #     result_container["error"] = str(e)

        # 开启线程执行生成任务
        thread = Thread(target=run_generation)
        thread.start()

        # 在主线程中循环监控显存，直到生成结束或手动停止
        while thread.is_alive():
            if stop_generation:
                # 注意：diffusers 很难从外部直接 kill 正在计算的 CUDA kernel
                # 这里主要实现 UI 逻辑上的停止，实际后端会完成当前步骤
                yield None, pd.DataFrame(memory_data), "停止中..."
                break

            elapsed = time.time() - start_time
            
            # 显存监控
            if not DEBUG:
                current_mem = torch.cuda.memory_allocated(device) / 1024**2
                peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2
            else:
                current_mem = 1024.0 # 模拟值
                peak_mem = 2048.0
            
            memory_data.append({
                "time": elapsed,
                "current_memory": current_mem,
                "peak_memory": peak_mem
            })
            
            df = pd.DataFrame(memory_data)
            status_text = (
                f"🎨 正在绘制... {elapsed:.1f}s | "
                f"📦 显存：{current_mem:.2f} MB | "
                f"📈 峰值：{peak_mem:.2f} MB"
            )

            yield None, df, status_text
            time.sleep(0.5) # 降低刷新频率

        # 完成后的结果反馈
        if result_container["error"]:
            yield None, pd.DataFrame(memory_data), f"错误: {result_container['error']}"
        else:
            final_elapsed = time.time() - start_time
            final_status = f"✅ 生成完成 | 总耗时: {final_elapsed:.2f}s | 峰值显存: {peak_mem:.2f} MB"
            yield result_container["image"], pd.DataFrame(memory_data), final_status

    def stop_infer():
        nonlocal stop_generation
        stop_generation = True
        return "已发送停止指令"

    # =========================
    # Gradio UI 布局
    # =========================
    with gr.Blocks() as demo:
        gr.Markdown(f"# 🎨 Diffusers Offload 演示 ({model_info.hf_name})")

        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(label="正向提示词 (Prompt)", lines=3, placeholder="An astronaut riding a horse...")
                neg_prompt = gr.Textbox(label="负面提示词 (Negative Prompt)", lines=2)
                
                with gr.Accordion("生成参数", open=True):
                    with gr.Row():
                        steps = gr.Slider(1, 100, 25, step=1, label="步数 (Steps)")
                        cfg_scale = gr.Slider(1.0, 20.0, 7.5, step=0.5, label="CFG Scale")
                    with gr.Row():
                        width = gr.Slider(256, 1024, 512, step=64, label="宽")
                        height = gr.Slider(256, 1024, 512, step=64, label="高")
                    seed = gr.Number(label="随机种子 (-1 为随机)", value=-1)

                with gr.Row():
                    btn = gr.Button("🚀 开始生成", variant="primary")
                    stop_btn = gr.Button("🛑 停止")

            with gr.Column(scale=1):
                out_img = gr.Image(label="生成结果", type="pil")
                status_text = gr.Textbox(label="状态监控", interactive=False)
                memory_plot = gr.LinePlot(
                    x="time", y="current_memory",
                    title="显存占用 (MB)",
                    x_title="时间 (s)", y_title="MB",
                    height=250
                )

        btn.click(
            infer,
            inputs=[prompt, neg_prompt, steps, cfg_scale, width, height, seed],
            outputs=[out_img, memory_plot, status_text]
        )
        
        stop_btn.click(stop_infer, outputs=status_text)

    return demo