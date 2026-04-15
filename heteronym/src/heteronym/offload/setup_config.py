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
    onload_device,
    use_sync: bool = False
):
    config = convert_config(json.loads(config_content))
    from .auto import auto_setup_offload
    for _, v in config.offload.root.items():
        auto_setup_offload(
            model,
            onload_device,
            torch.device("cpu"),
            param_name_whitelist_keywords=v.layers,
        )