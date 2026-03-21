import torch
from .scan_result import ScanResult
from typing import Any
import time
import numpy as np
from .logger import logger


def _register_scan_compute_time_hook(
    leaf_module: torch.nn.Module,
    leaf_module_name: str,
    result: ScanResult,
    onload_device: torch.device,
    offload_device: torch.device,
    warmup_steps: int,
    sampling_steps: int,
    test_on_offload_device: bool,
) -> torch.utils.hooks.RemovableHandle:
    def pre_hook(module: torch.nn.Module, inputs: tuple) -> None:
        logger.debug(f"Measuring compute time for leaf module: {leaf_module_name}")

        if test_on_offload_device:
            logger.debug(
                f"Moving module {leaf_module_name} to onload device: {onload_device}"
            )
            module = module.to(onload_device)
            inputs = tuple(
                x.to(onload_device) if isinstance(x, torch.Tensor) else x
                for x in inputs
            )

        measures = []
        logger.debug(
            f"Running {warmup_steps} warmup steps for module {leaf_module_name}"
        )
        for _ in range(warmup_steps):
            module.forward(*inputs)

        if onload_device.type == "cuda":
            logger.debug("Synchronizing CUDA device")
            torch.cuda.synchronize()
        if onload_device.type == "mps":
            logger.debug("Synchronizing MPS device")
            torch.mps.synchronize()

        logger.debug(
            f"Running {sampling_steps} sampling steps for module {leaf_module_name}"
        )
        for _ in range(sampling_steps):
            start = time.perf_counter_ns()
            module.forward(*inputs)
            if onload_device.type == "cuda":
                torch.cuda.synchronize()
            elif onload_device.type == "mps":
                torch.mps.synchronize()
            end = time.perf_counter_ns()
            measures.append(end - start)

        result.compute_time[leaf_module_name] = float(np.average(measures))
        result.compute_time_std[leaf_module_name] = float(np.std(measures))
        logger.debug(
            f"Module {leaf_module_name} average compute time: {result.compute_time[leaf_module_name]}ns "
            f"(std: {result.compute_time_std[leaf_module_name]}ns)"
        )

        if test_on_offload_device:
            logger.debug(
                f"Moving module {leaf_module_name} back to offload device: {offload_device}"
            )
            module.to(offload_device)
            [x.to(offload_device) for x in inputs if isinstance(x, torch.Tensor)]

    return leaf_module.register_forward_pre_hook(pre_hook)


def scan_compute_time(
    model: torch.nn.Module,
    example_inputs_args: list[Any],
    example_inputs_kwargs: dict[str, Any],
    example_modules: dict[str, torch.nn.Module],
    leaf_module_names: dict[str, list[str]],
    results: dict[str, ScanResult],
    onload_device: torch.device,
    offload_device: torch.device,
    warmup_steps: int,
    sampling_steps: int,
    test_on_offload_device: bool,
) -> None:
    logger.info("Starting compute time scanning")
    logger.debug(f"Devices - Onload: {onload_device}, Offload: {offload_device}")
    logger.debug(f"Warmup steps: {warmup_steps}, Sampling steps: {sampling_steps}")
    logger.debug(f"Test on offload device: {test_on_offload_device}")
    logger.debug(f"Processing {len(example_modules)} module lists")

    handles = [
        _register_scan_compute_time_hook(
            example_module.get_submodule(leaf_name),
            leaf_name,
            results[module_list_name],
            onload_device,
            offload_device,
            warmup_steps,
            sampling_steps,
            test_on_offload_device,
        )
        for module_list_name, example_module in example_modules.items()
        for leaf_name in leaf_module_names[module_list_name]
    ]

    logger.debug(f"Registered {len(handles)} hooks for compute time measurement")

    with torch.no_grad():
        logger.debug("Running forward pass to measure compute times")
        model(*example_inputs_args, **example_inputs_kwargs)
        logger.debug("Forward pass for compute time measurement completed")

    for handle in handles:
        handle.remove()

    logger.debug("Removed all compute time measurement hooks")
    logger.info("Compute time scanning completed")
