from .registry import (
    OffloadQuantizationConfig,
    OffloadTensorRegistryBuilder,
    TensorRegistry,
)
from .generate_offload_modules import generate_offload_modules
import torch
from typing import Optional, List, Tuple, Callable

def _make_pre_hook(registry: TensorRegistry, module_name: str, param_name_in_offload_no_prefix: List[str], module: torch.nn.Module):
    """
    make a forward pre-hook function for a module.
    
    Effect:
        Replaces parameter data with tensors from the registry during forward pass
        
    Args:
        registry: Tensor registry for managing offloaded tensors
        module_name: Name of the module this hook is for
        param_name_in_offload_no_prefix: List of parameter names to offload (without module prefix)
        module: The module to attach the hook to
        
    Returns:
        Pre-hook function
    """
    full_param_names = [f"{module_name}.{param_name}" for param_name in param_name_in_offload_no_prefix]
    param_refs = [
        module.get_parameter(param_name) for param_name in param_name_in_offload_no_prefix
    ]
    cache = zip(param_refs, full_param_names)
    def pre_hook(*_):
        for param_ref, full_name in cache:
            param_ref.data = registry.get(full_name)
    
    return pre_hook

def _make_post_hook(registry: TensorRegistry, module_name: str, param_name_in_offload_no_prefix: List[str], remove_myself: Callable[[], None], post_hook_handles: List[torch.utils.hooks.RemovableHandle]):
    """
    Make a forward post-hook function for a module.
    
    Effect:
        Releases tensors from the registry after forward pass
        Registers additional hooks if buffer rotation is triggered
        
    Args:
        registry: Tensor registry for managing offloaded tensors
        module_name: Name of the module this hook is for
        param_name_in_offload_no_prefix: List of parameter names to offload (without module prefix)
        remove_myself: Function to remove this hook
        post_hook_handles: List to store post-hook handles
        
    Returns:
        Post-hook function
    """
    to_release = [
        f"{module_name}.{param_name}" for param_name in param_name_in_offload_no_prefix
    ]
    # For the first forward pass, use registry.release because it is not known whether the buffer rotation should be triggered
    def post_hook(module: torch.nn.Module, inputs, outputs):
        should_release = registry.release(to_release)
        if should_release:
            # if the buffer rotation is triggered in the first forward pass, due to the deterministic order of modules, we can directly trigger buffer rotation using release_all to avoid extra overhead for poping dict items (refer to the implementation of registry.release)
            post_hook_handles.append(
                module.register_forward_hook(
                    lambda *_: registry.release_all()
                )
            )
        # the first forward pass will be triggered only once and it will remove itself, this function has to be externally given
        nonlocal remove_myself
        remove_myself()
    return post_hook

def setup_offload(
    model: torch.nn.Module,
    onload_device: torch.device,
    offload_device: torch.device,
    offload_parameter_names_in_order: List[str],
    onload_buffer_numels: int,
    offload_quantization_config: Optional[OffloadQuantizationConfig] = None,
) -> Tuple[TensorRegistry, List[torch.utils.hooks.RemovableHandle], List[torch.utils.hooks.RemovableHandle]]:
    """
    Set up tensor offloading for a model.
    
    Effect:
        Moves model to offload device
        Creates tensor registry for offloaded parameters
        Moves non-offloaded parameters and buffers to onload device
        Registers forward pre-hooks and post-hooks for offloaded modules
        Clears CUDA cache
        
    Requires:
        model is already on offload device.
        onload_device.type == "cuda"
        
    Args:
        model: The model to offload tensors for
        onload_device: Device to load tensors onto (must be CUDA)
        offload_device: Device to offload tensors from
        offload_parameter_names_in_order: List of parameter names in order of offloading. Should be in the same order as the usage order of the parameters (or alternatively, every offload_buffer_numels // 2 worth of parameters are used sequentially).
        onload_buffer_numels: Number of elements in the onload buffer
        offload_quantization_config: Configuration for quantization, if any
    
    Returns:
        Tuple containing:
        - TensorRegistry: The tensor registry managing offloaded tensors
        - List[RemovableHandle]: Pre-hook remove handles
        - List[RemovableHandle]: Post-hook remove handles, note that this is a list that will be modified after the first forward pass. It would stay empty before that.
        
    Raises:
        NotImplementedError: If onload_device is not a CUDA device
        RuntimeError: If model is not on offload device
    """
    if onload_device.type != "cuda":
        raise NotImplementedError("onload_device must be a CUDA device")
    model.to(offload_device)
    registry_builder = OffloadTensorRegistryBuilder()
    import copy
    for name in copy.deepcopy(offload_parameter_names_in_order):
        try:
            registry_builder.add_tensor(name, model.get_parameter(name))
        except Exception:
            # remove the name
            offload_parameter_names_in_order.remove(name)
    if registry_builder.device != offload_device:
        # raise RuntimeError("Model is not on offload device")
        registry_builder.device = offload_device
        for k in registry_builder.tensors:
            registry_builder.tensors[k] = registry_builder.tensors[k].to(offload_device)
            
    registry = TensorRegistry(registry_builder, onload_buffer_numels, onload_device, offload_quantization_config)
    
    for name, param in model.named_parameters():
        if name not in offload_parameter_names_in_order:
            param.data = param.data.to(onload_device)
    
    for name, buffer in model.named_buffers():
        if name not in offload_parameter_names_in_order:
            buffer.data = buffer.data.to(onload_device)
    pre_hook_handles = []
    post_hook_handles = []
    
    module_to_offload_param_names = {}
    for param_name in offload_parameter_names_in_order:
        module_name = param_name.rsplit(".", 1)[0]
        if module_name not in module_to_offload_param_names:
            module_to_offload_param_names[module_name] = []
        module_to_offload_param_names[module_name].append(
            param_name.rsplit(".", 1)[1]
        )
    
    for module_name, param_names in module_to_offload_param_names.items():
        pre_hook = _make_pre_hook(registry, module_name, param_names, model.get_submodule(module_name))
        pre_hook_handles.append(model.get_submodule(module_name).register_forward_pre_hook(pre_hook))
        # 初始化钩子容器，用于存储初始的后向钩子 handle
        # 使用列表是为了在嵌套函数中能访问到引用
        init_hook_handle_container = [None]
        def create_init_hook_remover(handle_container):
            def remove_init_post_hook():
                # 检查 handle 是否初始化
                if handle_container[0] is not None:
                    # 移除钩子
                    handle_container[0].remove()
                else:
                    raise RuntimeError("Hook handle not initialized")
            return remove_init_post_hook
        remove_init_post_hook = create_init_hook_remover(init_hook_handle_container)
        # 创建 post hook 并提供 remove_myself 函数
        post_hook = _make_post_hook(registry, module_name, param_names, remove_init_post_hook, post_hook_handles)
        init_post_hook_handle = model.get_submodule(module_name).register_forward_hook(post_hook)
        
        # 让 remove_myself 函数起作用
        init_hook_handle_container[0] = init_post_hook_handle
        
    torch.cuda.empty_cache()
    return registry, pre_hook_handles, post_hook_handles

def auto_setup_offload(
    model: torch.nn.Module,
    onload_device: torch.device,
    offload_device: Optional[torch.device] = None,
    blocks_to_keep: Optional[int] = None,
    param_name_blacklist_keywords: Optional[List[str]] = None,
    param_name_whitelist_keywords: Optional[List[str]] = None,
    offload_quantization_config: Optional[OffloadQuantizationConfig] = None,
    numel_threshold: Optional[int] = None,
    bytes_at_least: Optional[int] = None
) -> List[Tuple[TensorRegistry, List[torch.utils.hooks.RemovableHandle], List[torch.utils.hooks.RemovableHandle]]]:
    """
    Automatically detect module lists and set up tensor offloading for them.
    
    Model will be moved to the offload device (default to CPU) if not after the setup. After the setup, the model will function as if it were on the onload device.
    
    Usage:
        _ = auto_setup_offload(model, torch.device("cuda"), torch.device("cpu"), blocks_to_keep=4, offload_quantization_config={"offload_dtype": torch.float8_e4m3fn})
    
    Effect:
        Generates offload module configurations based on model structure
        Sets up tensor offloading for each configuration
        Returns list of offload setups
        
    Requires:
        onload_device.type == "cuda"
        
    Args:
        model: The model to offload tensors for
        onload_device: Device to load tensors onto (must be CUDA)
        offload_device: Device to offload tensors to (default to CPU)
        blocks_to_keep: Number of blocks to keep on the GPU
        param_name_blacklist_keywords: Keywords to blacklist parameter names from offloading
        offload_quantization_config: Configuration for quantization, if any. If it is None, no quantization will be performed. Otherwise, it should be a dictionary with following keys,
            - "offload_dtype": torch.dtype, dtype to offload to, default to torch.float8_e4m3fn
            - "enable_scale": bool, whether to enable scale, default to False
            - "enable_bias": bool, whether to enable bias default to False
        numel_threshold: Parameters having numels fewer than this will be ignored to prevent fragmented reading/writing
        bytes_at_least: If not set, will try to offload as many parameters as possible. If set, will try to offload on slightly above this number of bytes.
    
    Returns:
        List of tuples containing: TensorRegistry: The tensor registry managing offloaded tensors; List[RemovableHandle]: Pre-hook remove handles; List[RemovableHandle]: Post-hook remove handles, note that this is a list that will be modified after the first forward pass. It would stay empty before that.
        
        The returned values can be safely ignored completely.
        
    Raises:
        NotImplementedError: If onload_device is not a CUDA device
    """
    if onload_device.type != "cuda":
        raise NotImplementedError("onload_device must be a CUDA device")
    if offload_device is None:
        offload_device = torch.device("cpu")
    configs = generate_offload_modules(model, blocks_to_keep, param_name_blacklist_keywords, numel_threshold, bytes_at_least, param_name_whitelist_keywords=param_name_whitelist_keywords)
    return [
        setup_offload(model, onload_device, offload_device, offload_param_names, numels, offload_quantization_config)
        for offload_param_names, numels in configs
    ]
