import torch
from typing import Dict, NamedTuple, List, Optional

def get_module_lists(model: torch.nn.Module) -> Dict[str, torch.nn.ModuleList]:
    """
    Get all top-level ModuleLists from a model.
    
    Args:
        model: The PyTorch model to analyze
        
    Returns:
        Dictionary mapping module names to ModuleList instances
    """
    all_module_lists = {
        name: module
        for name, module in model.named_modules()
        if isinstance(module, torch.nn.ModuleList)
    }

    # Filter out nested ModuleLists (those that are children of other ModuleLists)
    top_level_module_lists = {}
    for name, module in all_module_lists.items():
        # Check if this module is a child of any other ModuleList
        is_nested = False
        for parent_name, _ in all_module_lists.items():
            if name != parent_name and name.startswith(parent_name + '.'):
                is_nested = True
                break
        
        if not is_nested:
            top_level_module_lists[name] = module
            
    return top_level_module_lists

def get_example_modules(module_lists: Dict[str, torch.nn.ModuleList]) -> Dict[str, torch.nn.Module]:
    """
    Get example modules from ModuleLists.
    
    Args:
        module_lists: Dictionary mapping module names to ModuleList instances
        
    Returns:
        Dictionary mapping module names to example modules (first module in each ModuleList)
    """
    return {
        name: module[-1]
        for name, module in module_lists.items()
    }

class OffloadModulesConfig(NamedTuple):
    """Configuration for offloading modules."""
    
    offload_param_names: List[str]
    numels: int

def generate_offload_modules(
    model: torch.nn.Module,
    blocks_to_keep: Optional[int] = None,
    param_name_blacklist_keywords: Optional[List[str]] = None,
    numel_threshold: Optional[int] = None,
    bytes_at_least: Optional[int] = None,
) -> List[OffloadModulesConfig]:
    """
    Generate offload module configurations for a model.
    
    Effect:
        Analyzes the model to identify ModuleLists and creates offload configurations
        for parameters that meet the specified criteria
        
    Args:
        model: The PyTorch model to analyze for offloading
        blocks_to_keep: Number of blocks to keep in memory (default: 2)
        param_name_blacklist_keywords: List of keywords to exclude from offloading (default: ["lora", "norm", "bias"])
        numel_threshold: Minimum number of elements a parameter must have to be considered (default: 16 * 1024)
        bytes_at_least: If not set, will try to offload as many parameters as possible. If set, will try to offload on slightly above this number of bytes.
        
    Returns:
        List of OffloadModulesConfig objects containing parameter names and total element counts
    """
    # Set default values for None parameters
    if blocks_to_keep is None:
        blocks_to_keep = 2
    if param_name_blacklist_keywords is None:
        param_name_blacklist_keywords = ["lora", "norm", "bias"]
    if numel_threshold is None:
        numel_threshold = 16 * 1024
    
    top_level_module_lists = get_module_lists(model)
    for key in top_level_module_lists.keys():
        top_level_module_lists[key] = top_level_module_lists[key][:-1]
    example_modules = get_example_modules(top_level_module_lists)
    offload_modules_configs = []
    if bytes_at_least is None:
        bytes_at_least = float("inf")
    for name in top_level_module_lists.keys():
        sub_names = set.intersection(*[set(
            n
            for n, param in each_module.named_parameters()
            if not any(keyword in n for keyword in param_name_blacklist_keywords)
            if param.numel() >= numel_threshold
        ) for each_module in top_level_module_lists[name]])
        sub_names = list(sub_names)
        if len(sub_names) == 0:
            import warnings
            warnings.warn(f"Found no parameters valid for offloading in {name}")
            continue
        module_dtype = example_modules[name].get_parameter(sub_names[0]).dtype
        bytes_per_numels = module_dtype.itemsize
        module_cnt = len(top_level_module_lists[name])
        module_cnt -= module_cnt % (blocks_to_keep * 2)
        sub_names.sort(key=lambda x: example_modules[name].get_parameter(x).numel())
        small_param = []
        numel_at_least = bytes_at_least // (module_cnt * bytes_per_numels)
        # remove small parameters until the total numel is enough
        while sum(example_modules[name].get_parameter(sub_name).numel() for sub_name in sub_names) >= numel_at_least:
            small_param.append(sub_names.pop())
        if len(small_param) > 0:
            sub_names.append(small_param[-1])
        module_names = [
            f"{name}.{i}.{sub_name}"
            for i in range(module_cnt)
            for sub_name in sub_names
        ]
        for full_param_name in module_names.copy():
            try:
                model.get_parameter(full_param_name)
            except Exception as e:
                warnings.warn(f"Error when getting parameter {full_param_name}: {e}")
                warnings.warn(f"Skipping module {full_param_name}")
                module_names.remove(full_param_name)
        module_numels = sum(
            example_modules[name].get_parameter(sub_name).numel()
            for sub_name in sub_names
        )
        offload_modules_configs.append(OffloadModulesConfig(module_names, module_numels * blocks_to_keep * 2))
    return offload_modules_configs
