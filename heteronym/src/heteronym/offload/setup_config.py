from typing import Dict, List
from pydantic import BaseModel, RootModel
import json
import torch
import os

class BlockData(BaseModel):
    layers: List[str]
    bytes: int

class OffloadConfig(RootModel[Dict[str, BlockData]]):
    pass

class QuantizationConfig(BaseModel):
    quantize: bool
    quantize_dtype: str
    enable_scale: bool
    enable_bias: bool

class ModelConfig(BaseModel):
    quantization: QuantizationConfig
    offload: OffloadConfig
    
def convert_config(obj) -> ModelConfig:
    return ModelConfig(**obj)

def setup_from_config(
    model: torch.nn.Module,
    config_content: str,
    use_sync: bool = False
):
    config = convert_config(json.loads(config_content))
    
    if not(torch.distributed.is_available() and torch.distributed.is_initialized()):
        from .auto import setup_offload
        from .auto import auto_setup_offload
        for _, v in config.offload.root.items():
            auto_setup_offload(
                model,
                torch.device(f"cuda:{rank}"),
                torch.device("cpu"),
                param_name_whitelist_keywords=v.layers,
            )
    else:
        from .dist import setup_offload
        rank = torch.distributed.get_rank()
        for _, v in config.offload.root.items():
            setup_offload(
                model,
                torch.device(f"cuda:{rank}"),
                torch.device("cpu"),
                v.layers,
                v.bytes // (2 if not config.quantization.quantize else 1),
                {
                    "offload_dtype": torch.float8_e4m3fn if config.quantization.quantize_dtype == "fp8" else torch.float8_e4m3fn,
                    "enable_bias": config.quantization.enable_bias,
                    "enable_scale": config.quantization.enable_scale,
                } if config.quantization.quantize else None,
                rank,
                world_size=torch.distributed.get_world_size(),
            )