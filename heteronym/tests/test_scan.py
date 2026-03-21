import torch
from transformers import Qwen3ForCausalLM, AutoTokenizer
from loguru import logger
from heteronym.scanner.get_module_lists import get_top_module_lists
from heteronym.scanner.get_leaf_module_names import get_leaf_module_names
from heteronym.scanner.scan import scan
import os

if os.path.exists("debug.log"):
    os.remove("debug.log")
logger.add("debug.log", level="DEBUG", rotation="1 MB")

cache_dir = "cache"
qwen_model_name = "Qwen/Qwen3-0.6B"

def get_qwen() -> torch.nn.Module:
    model: torch.nn.Module = Qwen3ForCausalLM.from_pretrained(
        qwen_model_name,
        cache_dir=cache_dir,
        local_files_only=True,
    )
    print(model)
    return model

def get_qwen_example_inputs(
    device: torch.device    
) -> tuple[list[torch.Tensor], dict[str, torch.Tensor]]:
    tokenizer = AutoTokenizer.from_pretrained(
        qwen_model_name,
        cache_dir=cache_dir,
        local_files_only=True,
    )
    example_inputs = tokenizer(
        "Qwen:",
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512
    )
    example_input_kwargs = {
        "input_ids": example_inputs.input_ids.to(device),
        "attention_mask": example_inputs.attention_mask.to(device)
    }
    print(example_inputs.input_ids.shape)
    print(example_inputs.attention_mask.shape)
    return [], example_input_kwargs
    
    
def test_scan_qwen_on_onload() -> None:
    model = get_qwen().to(torch.device("mps"))
    module_lists = get_top_module_lists(model)
    logger.debug(module_lists)

    example_input_args, example_input_kwargs = get_qwen_example_inputs(
        torch.device("mps")
    )
    logger.debug(scan(
        model,
        example_input_args,
        example_input_kwargs,
        module_lists,
        torch.device("mps"),
        torch.device("cpu"),
        10,
        1000,
        False,
    ))

def test_scan_qwen_on_offload() -> None:
    model = get_qwen().to(torch.device("cpu"))
    module_lists = get_top_module_lists(model)
    logger.debug(module_lists)

    example_input_args, example_input_kwargs = get_qwen_example_inputs(
        torch.device("cpu")
    )
    logger.debug(scan(
        model,
        example_input_args,
        example_input_kwargs,
        module_lists,
        torch.device("mps"),
        torch.device("cpu"),
        10,
        1000,
        True,
    ))