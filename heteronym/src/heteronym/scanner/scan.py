import torch
from .scan_result import ScanResult
from .get_leaf_module_names import get_leaf_module_names
from typing import Any
import time
from .scan_usage_order import scan_usage_order
from .scan_compute_time import scan_compute_time
from .scan_onload_time import scan_onload_time
from .scan_memory import scan_memory
from .logger import logger


def scan(
    model: torch.nn.Module,
    example_input_args: list[Any],
    example_input_kwargs: dict[str, Any],
    module_lists: dict[str, torch.nn.ModuleList],
    onload_device: torch.device,
    offload_device: torch.device,
    warmup_steps: int,
    sampling_steps: int,
    test_on_offload_device: bool,
) -> dict[str, ScanResult]:
    """
    The device of the input must be given by the external caller.

    The model and the input should be on offload device if test_on_offload_device is True. Or else, both should be on the onload device
    """
    logger.info("Starting comprehensive model scan")
    logger.debug(f"Model type: {type(model).__name__}")
    logger.debug(f"Onload device: {onload_device}, Offload device: {offload_device}")
    logger.debug(f"Warmup steps: {warmup_steps}, Sampling steps: {sampling_steps}")
    logger.debug(f"Test on offload device: {test_on_offload_device}")
    logger.debug(f"Number of module lists: {len(module_lists)}")

    example_modules = {
        module_list_name: module_list[(len(module_list) - 1) // 2]
        for module_list_name, module_list in module_lists.items()
    }
    logger.debug("Created example modules for scanning")

    scan_results = {
        module_list_name: ScanResult() for module_list_name in module_lists.keys()
    }
    logger.debug(f"Initialized {len(scan_results)} scan result objects")

    leaf_module_names = {
        module_list_name: get_leaf_module_names(example_modules[module_list_name])
        for module_list_name in module_lists.keys()
    }
    logger.debug("Retrieved leaf module names")

    if test_on_offload_device:
        logger.debug("Moving model to offload device")
        model = model.to(offload_device)

    logger.info("Scanning module usage order...")
    scan_usage_order(
        model,
        example_input_args,
        example_input_kwargs,
        example_modules,
        leaf_module_names,
        scan_results,
    )
    logger.info("Scanning compute time...")
    scan_compute_time(
        model,
        example_input_args,
        example_input_kwargs,
        example_modules,
        leaf_module_names,
        scan_results,
        onload_device,
        offload_device,
        warmup_steps,
        sampling_steps,
        test_on_offload_device,
    )
    logger.info("Scanning onload time...")
    scan_onload_time(
        scan_results, onload_device, offload_device, warmup_steps, sampling_steps
    )
    logger.info("Scanning memory...")
    scan_memory(example_modules, leaf_module_names, scan_results)

    logger.info("Comprehensive model scan completed")
    return scan_results
