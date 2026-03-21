import torch
from .logger import logger


def get_leaf_module_names(model: torch.nn.Module) -> list[str]:
    """
    Get the names of all leaf modules in a model. Leaf modules are modules that have no children modules.

    Args:
        model (torch.nn.Module): The model to scan.

    Returns:
        list[str]: A list of names of all leaf modules in the model.
    """
    logger.debug(f"Starting to get leaf module names for model: {type(model).__name__}")
    leaf_module_names = []

    for name, module in model.named_modules():
        if len(list(module.named_children())) == 0 and any(
            True for _ in module.parameters()
        ):
            leaf_module_names.append(name)

    logger.debug(f"Found {len(leaf_module_names)} leaf modules in model")
    return leaf_module_names
