import torch
import inspect
import math
from typing import Any, Dict, List, Tuple, Optional

def is_video_model(model: torch.nn.Module) -> bool:
    """
    通过类名和配置项的启发式方法判断是否为视频/3D模型。
    """
    class_name = model.__class__.__name__.lower()
    
    # 1. 检查类名中的常见视频模型关键字
    if any(kw in class_name for kw in ["video", "3d", "spatiotemporal", "animatediff", "wan", "cogvideo"]):
        return True
        
    # 2. 检查 config 中的视频专属属性
    config = getattr(model, "config", None)
    if config is not None:
        if hasattr(config, "num_frames") or hasattr(config, "patch_size_t") or hasattr(config, "temporal_attention"):
            return True
            
    return False


def generate_example_inputs(
    model: torch.nn.Module,
    model_name: str,
    onload_device: torch.device,
    offload_device: torch.device,
    test_on_offload_device: bool = False,
    tokenizer: Optional[Any] = None,
    batch_size: int = 1,
) -> Tuple[List[Any], Dict[str, Any]]:

    sig = inspect.signature(model.forward)
    arg_names = list(sig.parameters.keys())
    if arg_names and arg_names[0] == "self":
        arg_names = arg_names[1:]

    config = getattr(model, "config", None)
    
    # 判断是否为视频模型
    is_video = is_video_model(model)

    # -----------------------------
    # SAFE inference helpers (通用)
    # -----------------------------
    def infer_vocab_size():
        if tokenizer is not None and hasattr(tokenizer, "vocab_size"):
            return tokenizer.vocab_size
        return 49408

    # ==========================================
    # 3D 视频生成模型专属通道 (Video/3D Channel)
    # ==========================================
    if is_video:
        def infer_text_seq_len():
            if tokenizer is not None and hasattr(tokenizer, "model_max_length"):
                v = tokenizer.model_max_length
                if isinstance(v, int) and 0 < v < 10000:
                    return v
            # 现代视频模型多使用 T5-XXL，常见 max_length 为 226 或 512
            return getattr(config, "max_sequence_length", 226)

        def infer_hidden_dim():
            if config is not None:
                return (
                    getattr(config, "text_embed_dim", None)
                    or getattr(config, "caption_channels", None)     # 兼容 CogVideoX
                    or getattr(config, "joint_attention_dim", None)  # 兼容部分 DiT 架构
                    or getattr(config, "encoder_hid_dim", None)
                    or getattr(config, "cross_attention_dim", None)
                    or getattr(config, "hidden_size", None)
                    or 4096  # T5-XXL 的默认特征维度，解决 768 vs 4096 报错
                )
            return 4096

        def infer_latent_shape():
            if config is not None:
                # 兼容不同命名习惯，视频模型（如 Wan/CogVideo）有时候会用 16 通道
                ch = getattr(config, "in_channels", getattr(config, "out_channels", 16))
                base = getattr(config, "sample_size", 64)
                
                # 解析 spatial 尺寸
                if isinstance(base, (list, tuple)):
                    base = base[-1]
                
                # 确保是 8 的倍数（针对 VAE）
                base = int(math.ceil(base / 8) * 8) if base % 8 != 0 else base
                num_frames = getattr(config, "num_frames", 8) 
                
                # 视频模型需要 5D 张量: (batch_size, channels, frames, height, width)
                return (batch_size, ch, num_frames, base, base)
            
            # Config 缺失时的 Fallback 策略 (常见 DiT 视频模型)
            return (batch_size, 16, 8, 64, 64)

    # ==========================================
    # 2D 图像生成模型专属通道 (Image Channel)
    # ==========================================
    else:
        def infer_text_seq_len():
            if tokenizer is not None:
                if hasattr(tokenizer, "model_max_length"):
                    v = tokenizer.model_max_length
                    if isinstance(v, int) and 0 < v < 10000:
                        return min(v, 77)
            return 77

        def infer_hidden_dim():
            if config is not None:
                return (
                    getattr(config, "cross_attention_dim", None)
                    or getattr(config, "text_embed_dim", None)
                    or getattr(config, "hidden_size", None)
                    or 768
                )
            return 768

        def infer_latent_shape():
            if config is not None:
                ch = getattr(config, "in_channels", getattr(config, "out_channels", 4))
                base = getattr(config, "sample_size", 64)
                
                if isinstance(base, (list, tuple)):
                    base = base[-1]
                    
                base = int(math.ceil(base / 8) * 8) if base % 8 != 0 else base
                return (batch_size, ch, base, base)
                
            return (batch_size, 4, 64, 64)

    # -----------------------------
    # Tensor builders
    # -----------------------------
    def make_latents(device):
        return torch.randn(infer_latent_shape(), device=device, dtype=torch.float32)

    def make_encoder_hidden_states(device):
        seq_len = infer_text_seq_len()
        hidden_dim = infer_hidden_dim()
        return torch.randn(
            (batch_size, seq_len, hidden_dim),
            device=device,
            dtype=torch.float32,
        )

    def make_timestep(device):
        return torch.tensor([1] * batch_size, device=device, dtype=torch.long)

    # -----------------------------
    # build kwargs
    # -----------------------------
    kwargs: Dict[str, Any] = {}

    for name in arg_names:
        # 1. 隐变量输入 (Latents)
        if name in ("sample", "samples", "latents", "hidden_states", "noisy_sample"):
            kwargs[name] = make_latents(onload_device)

        # 2. 文本嵌入输入 (Conditioning)
        elif name in ("encoder_hidden_states", "text_embeddings", "context"):
            kwargs[name] = make_encoder_hidden_states(onload_device)

        # 3. 时间步 (Timesteps)
        elif name in ("timestep", "timesteps", "time_step", "t"):
            kwargs[name] = make_timestep(onload_device)

        # 4. 重点修复：Attention Mask
        elif name == "attention_mask":
            kwargs[name] = None 

        elif name == "input_ids":
            kwargs[name] = torch.randint(
                0,
                infer_vocab_size(),
                (batch_size, infer_text_seq_len()),
                device=onload_device,
                dtype=torch.long,
            )
        
        # 处理 SDXL / Video 等模型可能需要的额外参数
        elif name == "added_cond_kwargs":
             kwargs[name] = None
             
        # CogVideoX 中可能需要图像旋转位置编码
        elif name == "image_rotary_emb":
            kwargs[name] = None

        else:
            kwargs[name] = None

    # -----------------------------
    # cleanup None
    # -----------------------------
    # 移除所有为 None 的参数，让模型使用内部默认值
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    # -----------------------------
    # optional device offload
    # -----------------------------
    if test_on_offload_device:
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor):
                kwargs[k] = v.to(offload_device)

    return [], kwargs