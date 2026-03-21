import torch
from typing import Any
from .scan_result import ScanResult
from .logger import logger


def _register_usage_order_hook(
    leaf_module: torch.nn.Module, leaf_module_name: str, result: ScanResult
) -> torch.utils.hooks.RemovableHandle:
    def pre_hook(*_):
        logger.debug(f"Leaf module '{leaf_module_name}' usage detected")
        result.leaf_module_usage_order.append(leaf_module_name)

    handle = leaf_module.register_forward_pre_hook(pre_hook)
    return handle


def scan_usage_order(
    model: torch.nn.Module,
    example_inputs_args: list[Any],
    example_inputs_kwargs: dict[str, Any],
    example_modules: dict[str, torch.nn.Module],
    leaf_module_names: dict[str, list[str]],
    results: dict[str, ScanResult],
) -> None:
    logger.info("Starting usage order scanning")
    logger.debug(f"Number of module lists to process: {len(example_modules)}")

    # register hook for every leaf module
    handles = [
        _register_usage_order_hook(
            example_module.get_submodule(leaf_name),
            leaf_name,
            results[module_list_name],
        )
        for module_list_name, example_module in example_modules.items()
        for leaf_name in leaf_module_names[module_list_name]
    ]

    logger.debug(f"Registered {len(handles)} hooks for usage order tracking")

    with torch.no_grad():
        logger.debug("Running forward pass to determine usage order")
        model(*example_inputs_args, **example_inputs_kwargs)
        logger.debug("Forward pass completed")

    for handle in handles:
        handle.remove()

    logger.debug("Removed all usage order hooks")
    logger.info("Usage order scanning completed")

    # Log results summary
    for module_list_name, result in results.items():
        logger.debug(
            f"Module list '{module_list_name}' has {len(result.leaf_module_usage_order)} leaf modules in usage order"
        )
