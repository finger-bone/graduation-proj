import torch
from .scan_result import ScanResult
import itertools
from .logger import logger

DTYPE_BYTES = {
    torch.float64: 8,
    torch.double: 8,
    torch.float32: 4,
    torch.float: 4,
    torch.float16: 2,
    torch.half: 2,
    torch.bfloat16: 2,
    torch.uint8: 1,
    torch.int8: 1,
    torch.int16: 2,
    torch.short: 2,
    torch.int32: 4,
    torch.int: 4,
    torch.int64: 8,
    torch.long: 8,
    torch.bool: 1,
}


def _tensor_nbytes(t: torch.Tensor) -> int:
    """计算一个 tensor 的 byte 占用"""
    nbytes = t.nelement() * DTYPE_BYTES.get(t.dtype, t.element_size())
    logger.debug(
        f"Tensor of shape {t.shape} and dtype {t.dtype} occupies {nbytes} bytes"
    )
    return nbytes


def _count_memory(module: torch.nn.Module) -> int:
    logger.debug(f"Counting memory for module: {type(module).__name__}")
    total = 0

    for p in module.parameters(recurse=False):
        if p is not None:
            nbytes = _tensor_nbytes(p)
            total += nbytes

    for b in module.buffers(recurse=False):
        if b is not None:
            nbytes = _tensor_nbytes(b)
            total += nbytes

    logger.debug(f"Module {type(module).__name__} total memory: {total} bytes")
    return total


def scan_memory(
    example_modules: dict[str, torch.nn.Module],
    leaf_module_names: dict[str, list[str]],
    results: dict[str, ScanResult],
):
    logger.info("Starting memory scanning")
    logger.debug(f"Processing {len(example_modules)} module lists")

    for module_list_name, example_module in example_modules.items():
        logger.debug(f"Processing module list: {module_list_name}")
        for leaf_module_name in leaf_module_names[module_list_name]:
            logger.debug(f"Measuring memory for leaf module: {leaf_module_name}")
            memory_bytes = _count_memory(example_module.get_submodule(leaf_module_name))
            results[module_list_name].memory[leaf_module_name] = memory_bytes
            logger.debug(f"Leaf module {leaf_module_name} memory: {memory_bytes} bytes")

    logger.info("Memory scanning completed")
