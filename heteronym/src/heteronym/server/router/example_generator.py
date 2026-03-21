import torch
import inspect
import re
import math
from typing import Any, Dict, List, Tuple, Optional, get_origin, get_args


def generate_example_inputs(
    model: torch.nn.Module,
    model_name: str,
    onload_device: torch.device,
    offload_device: torch.device,
    test_on_offload_device: bool = False,
    tokenizer: Optional[Any] = None,
    batch_size: int = 1,
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Config-aware + probe-and-retry example input generator.

    返回和你的原版本一致： ([], kwargs)
    """
    sig = inspect.signature(model.forward)
    arg_names = list(sig.parameters.keys())
    if arg_names and arg_names[0] == "self":
        arg_names = arg_names[1:]
    config = getattr(model, "config", None)
    fwd_doc = model.forward.__doc__ or ""

    # ---------- helpers ----------
    def infer_text_seq_len() -> int:
        if config is not None:
            for k in (
                "max_position_embeddings",
                "n_positions",
                "max_length",
                "seq_length",
            ):
                v = getattr(config, k, None)
                if isinstance(v, int):
                    return min(v, 512)
        if tokenizer is not None:
            return getattr(
                tokenizer, "model_max_length", getattr(tokenizer, "vocab_size", 77)
            )
        return 77

    def infer_vocab_size() -> int:
        if config is not None and hasattr(config, "vocab_size"):
            return config.vocab_size
        if tokenizer is not None and hasattr(tokenizer, "vocab_size"):
            return tokenizer.vocab_size
        return 30522

    def infer_latent_shape_from_config():
        # returns (B, C, H, W)
        if config is not None:
            in_ch = (
                getattr(config, "in_channels", None)
                or getattr(config, "latent_channels", None)
                or 4
            )
            sample = (
                getattr(config, "sample_size", None)
                or getattr(config, "image_size", None)
                or 512
            )
            if isinstance(sample, (list, tuple)):
                sample = sample[0]
            vae_sf = getattr(config, "vae_scale_factor", 8)
            h = int(sample // vae_sf)
            return (batch_size, in_ch, h, h)
        return (batch_size, 4, 64, 64)

    def make_encoder_hidden_states(device, seq_len=None, hidden_dim=None):
        if hidden_dim is None:
            if config is not None:
                hidden_dim = getattr(config, "cross_attention_dim", None) or getattr(
                    config, "hidden_size", None
                )
            if hidden_dim is None:
                hidden_dim = 768
        if seq_len is None:
            seq_len = infer_text_seq_len()
        return torch.randn(
            (batch_size, seq_len, hidden_dim), dtype=torch.float, device=device
        )

    def make_latents(device, shape=None):
        if shape is None:
            shape = infer_latent_shape_from_config()
        return torch.randn(shape, dtype=torch.float, device=device)

    def make_timestep(device):
        return torch.tensor([0] * batch_size, dtype=torch.long, device=device)

    # ---------- initial kwargs construction (heuristics) ----------
    kwargs: Dict[str, Any] = {}
    for name in arg_names:
        if name in (
            "latents",
            "sample",
            "hidden_states",
            "noisy_sample",
            "noise_sample",
        ):
            kwargs[name] = make_latents(onload_device)
        elif name in ("encoder_hidden_states", "text_embeddings", "context_embeddings"):
            kwargs[name] = make_encoder_hidden_states(onload_device)
        elif name in ("timestep", "timesteps", "time_step"):
            kwargs[name] = make_timestep(onload_device)
        else:
            kwargs[name] = None  # fallback

    # ---------- ensure sample & encoder_hidden_states alignment ----------
    # 对 UNet cross-attention 来说，seq_len = H*W
    latent_shape = None
    for name in ("latents", "sample", "hidden_states", "noisy_sample", "noise_sample"):
        if (
            name in kwargs
            and isinstance(kwargs[name], torch.Tensor)
            and kwargs[name].dim() == 4
        ):
            latent_shape = kwargs[name].shape
            break

    if latent_shape is not None and "encoder_hidden_states" in kwargs:
        b, c, h, w = latent_shape
        spatial_tokens = h * w
        hidden_dim = kwargs["encoder_hidden_states"].shape[-1]
        # 重新生成 encoder_hidden_states，使长度等于 latent 的 H*W
        kwargs["encoder_hidden_states"] = make_encoder_hidden_states(
            onload_device, seq_len=spatial_tokens, hidden_dim=hidden_dim
        )

    if "input_ids" in arg_names:
        kwargs["input_ids"] = torch.randint(
            low=0,
            high=infer_vocab_size(),
            size=(batch_size, infer_text_seq_len()),
            dtype=torch.long,
            device=onload_device,
        )
    
    if "attention_mask" in arg_names:
        kwargs["attention_mask"] = torch.ones(
            (batch_size, infer_text_seq_len()),
            dtype=torch.long,
            device=onload_device,
        )

    # ---------- final offload if requested ----------
    if test_on_offload_device:
        for k, v in list(kwargs.items()):
            if isinstance(v, torch.Tensor):
                kwargs[k] = v.to(offload_device)

    for k, v in list(kwargs.items()):
        if v is None:
            kwargs.pop(k)

    return [], kwargs
