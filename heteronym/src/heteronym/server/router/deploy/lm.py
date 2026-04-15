import gradio as gr

from heteronym.server.db.client import TorchModel, OffloadConfig
from heteronym.config import DEBUG, get_device
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import json
import pandas as pd


if DEBUG:
    torch.cuda.reset_peak_memory_stats = lambda *args, **kwargs: None
    torch.cuda.memory_allocated = lambda *args, **kwargs: 2
    torch.cuda.max_memory_allocated = lambda *args, **kwargs: 2


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
    # 处理 offload_layers 中的每个键
    for key, layers_list in offload_layers.items():
        memory_info = scan_results[key]["memory"]
        # 计算当前键下所有 layers 的内存总和
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


import gradio as gr
import time
import torch
from transformers import TextIteratorStreamer
from threading import Thread


def create_ui(
    model_info: TorchModel,
    offload_config: OffloadConfig = None,
    enable_offload: bool = False,
    device_id: int = 0
):
    device = get_device(device_id)
    tokenizer = AutoTokenizer.from_pretrained(model_info.hf_name, cache_dir=model_info.path)

    model = AutoModelForCausalLM.from_pretrained(
        model_info.hf_name,
        low_cpu_mem_usage=True,
        device_map={"": "cpu"},
        torch_dtype="auto",
        cache_dir=model_info.path,
    )

    if enable_offload:
        offload_conf = create_config(offload_config, model_info)
        from heteronym.offload.setup_config import setup_from_config
        setup_from_config(model, json.dumps(offload_conf), device)
    else:
        model = model.to(device)

    model = model.eval()
    # 全局停止标志
    stop_generation = False

    # =========================
    # 推理函数（streaming）
    # =========================
    def infer(prompt, max_new_tokens, temperature, top_p, top_k, do_sample, repetition_penalty, num_beams):
        nonlocal stop_generation
        stop_generation = False
        
        inputs = tokenizer(prompt, return_tensors="pt").to(device)

        streamer = TextIteratorStreamer(
            tokenizer,
            skip_prompt=True,
            skip_special_tokens=True
        )

        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=int(max_new_tokens),
            do_sample=bool(do_sample),
            temperature=float(temperature) if do_sample else 1.0,
            top_p=float(top_p) if do_sample else 1.0,
            top_k=int(top_k) if do_sample else 50,
            repetition_penalty=float(repetition_penalty),
            num_beams=int(num_beams) if not do_sample and num_beams > 1 else 1,
        )

        thread = Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()

        output_text = ""
        total_tokens = 0  # 跟踪总 token 数
        start_time = time.time()
        
        # 显存数据历史记录
        memory_data = []

        try:
            for new_text in streamer:
                if stop_generation:
                    break
                    
                output_text += new_text
                # 计算新文本对应的 token 数量
                new_tokens = len(tokenizer.encode(new_text, add_special_tokens=False))
                total_tokens += new_tokens

                elapsed = time.time() - start_time
                tps = total_tokens / elapsed if elapsed > 0 else 0

                # 显存监控 (DEBUG 模式下使用占位值)
                if not DEBUG:
                    current_mem = torch.cuda.memory_allocated(device) / 1024**2
                    peak_mem = torch.cuda.max_memory_allocated(device) / 1024**2
                else:
                    current_mem = 0
                    peak_mem = 0
                
                # 记录显存数据
                memory_data.append({
                    "time": elapsed,
                    "current_memory": current_mem,
                    "peak_memory": peak_mem,
                    "tokens_per_second": tps
                })
                
                # 创建 DataFrame 用于图表显示
                df = pd.DataFrame(memory_data)
                
                status_text = (
                    f"⚡ {tps:.2f} token/s | "
                    f"📦 当前显存：{current_mem:.2f} MB | "
                    f"📈 峰值显存：{peak_mem:.2f} MB"
                )

                yield output_text, df, status_text
        except Exception as e:
            error_df = pd.DataFrame(memory_data) if memory_data else pd.DataFrame(columns=["time", "current_memory", "peak_memory", "tokens_per_second"])
            yield output_text, error_df, f"生成过程中出现错误：{str(e)}"

    def stop_infer():
        nonlocal stop_generation
        stop_generation = True
        return "已停止生成"

    # =========================
    # Gradio UI
    # =========================
    with gr.Blocks() as demo:
        gr.Markdown("# 🚀 LLM Offload Demo")

        with gr.Row():
            inp = gr.Textbox(label="输入", lines=4)
        
        with gr.Row():
            out = gr.Textbox(label="输出", lines=12)
        
        # 显存统计图
        with gr.Row():
            memory_plot = gr.LinePlot(
                x="time",
                y="current_memory", 
                title="显存占用监控 (MB)",
                x_title="时间 (秒)",
                y_title="显存 (MB)",
                height=300,
                tooltip=["time", "current_memory", "peak_memory", "tokens_per_second"]
            )
        
        status_text = gr.Textbox(label="性能监控详情")

        # 生成参数控制面板
        with gr.Accordion("生成参数设置", open=False):
            with gr.Row():
                max_new_tokens = gr.Slider(
                    minimum=1, maximum=2048, value=256, step=1,
                    label="最大生成长度 (max_new_tokens)"
                )
                temperature = gr.Slider(
                    minimum=0.1, maximum=2.0, value=0.7, step=0.1,
                    label="温度 (temperature)"
                )
            with gr.Row():
                top_p = gr.Slider(
                    minimum=0.1, maximum=1.0, value=0.9, step=0.05,
                    label="Top-p (nucleus sampling)"
                )
                top_k = gr.Slider(
                    minimum=1, maximum=100, value=50, step=1,
                    label="Top-k"
                )
            with gr.Row():
                do_sample = gr.Checkbox(value=True, label="启用采样 (do_sample)")
                repetition_penalty = gr.Slider(
                    minimum=0.1, maximum=5.0, value=1.0, step=0.1,
                    label="重复惩罚 (repetition_penalty)"
                )
                num_beams = gr.Slider(
                    minimum=1, maximum=10, value=1, step=1,
                    label="束搜索数量 (num_beams)"
                )

        with gr.Row():
            btn = gr.Button("生成")
            stop_btn = gr.Button("停止")

        btn.click(
            infer,
            inputs=[inp, max_new_tokens, temperature, top_p, top_k, do_sample, repetition_penalty, num_beams],
            outputs=[out, memory_plot, status_text]
        )
        
        stop_btn.click(
            stop_infer,
            inputs=[],
            outputs=[status_text]
        )

    return demo
