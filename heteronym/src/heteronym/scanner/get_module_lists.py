import torch
from .logger import logger


def get_top_module_lists(model: torch.nn.Module) -> dict[str, torch.nn.ModuleList]:
    """
    Get the top-level module lists (exclude nested ones)

    Args:
        model (torch.nn.Module): The model

    Returns:
        dict[str, torch.nn.ModuleList]: The top-level module lists
    """
    logger.debug(f"Getting top module lists for model: {type(model).__name__}")

    # 先收集所有 ModuleList 及其路径
    all_lists = [
        (name, module)
        for name, module in model.named_modules()
        if isinstance(module, torch.nn.ModuleList)
    ]

    top_lists = {}
    for name, module in all_lists:
        # 检查当前 ModuleList 是否在其它 ModuleList 内
        if not any(
            name != other_name and name.startswith(other_name + ".")
            for other_name, _ in all_lists
        ):
            top_lists[name] = module

    logger.debug(f"Found {len(top_lists)} top-level module lists in model")
    return top_lists
