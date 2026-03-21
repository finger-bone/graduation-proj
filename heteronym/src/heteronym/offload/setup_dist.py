from .registry import (
    OffloadQuantizationConfig,
    OffloadTensorRegistryBuilder,
    TensorRegistry,
)
import torch
from typing import Optional, List, Tuple, Callable
import torch.distributed as dist
from .const import MASTER_RANK

class HookHandleRef:
    """
    A reference container for hook handles that allows one-time removal.
    
    This class provides a way to store a hook handle and remove it exactly once.
    It's designed to be used with one-time hooks that remove themselves after execution.
    """
    
    def __init__(self):
        self._handle: Optional[torch.utils.hooks.RemovableHandle] = None
    
    def set_handle(self, handle: torch.utils.hooks.RemovableHandle) -> None:
        """Set the hook handle."""
        self._handle = handle
    
    def remove(self) -> None:
        """Remove the hook. Can only be called once after the handle is set."""
        if self._handle is None:
            raise RuntimeError("Hook handle not initialized")
        self._handle.remove()
        self._handle = None

def _create_one_time_hook_remover():
    """
    Create a one-time hook remover function.
    
    Returns:
        A tuple of (remover_function, handle_ref) where:
        - remover_function: Function to remove the hook
        - handle_ref: HookHandleRef to store the hook handle
    """
    handle_ref = HookHandleRef()
    return handle_ref.remove, handle_ref

def _make_pre_hook(registry: TensorRegistry, module_name: str, param_name_in_offload_no_prefix: List[str], module: torch.nn.Module, offload_device: torch.device):
    """
    make a forward pre-hook function for a module.
    
    Effect:
        Replaces parameter data with tensors from the registry during forward pass
        The hook is one-time and will remove itself after first execution
        
    Args:
        registry: Tensor registry for managing offloaded tensors
        module_name: Name of the module this hook is for
        param_name_in_offload_no_prefix: List of parameter names to offload (without module prefix)
        module: The module to attach the hook to
        
    Returns:
        A tuple of (pre_hook_function, hook_handle_ref)
    """
    full_param_names = [f"{module_name}.{param_name}" for param_name in param_name_in_offload_no_prefix]
    remove_myself, hook_handle_ref = _create_one_time_hook_remover()
    def pre_hook(*_):
        state_dict = {}
        for name, fullname in zip(param_name_in_offload_no_prefix, full_param_names):
            state_dict[name] = registry.get(fullname)
        module.load_state_dict(state_dict, strict=False, assign=True)
        remove_myself()
    return pre_hook, hook_handle_ref

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
        remove_myself()
    return post_hook

def setup_offload(
    model: torch.nn.Module,
    onload_device: torch.device,
    offload_device: torch.device,
    offload_parameter_names_in_order: List[str],
    onload_buffer_numels: int,
    rank: int,
    world_size: int,
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
        world_size: Number of processes in distributed training, default to 1 (single process)
        rank: Rank of current process, default to 0
        process_group: Process group for distributed communication, default to None (use default group)
    
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
    registry_builder = OffloadTensorRegistryBuilder()
    is_master = (rank == MASTER_RANK)
    if is_master:
        model.to(offload_device)
        for name in offload_parameter_names_in_order.copy():
            registry_builder.add_tensor(name, model.get_parameter(name))
        if registry_builder.device != offload_device:
            raise RuntimeError("Model is not on offload device")
    else:
        model.to(torch.device("meta"))
    dist.broadcast_object_list(offload_parameter_names_in_order, MASTER_RANK, device=torch.device("cpu"))
    registry = TensorRegistry(registry_builder, onload_buffer_numels, onload_device, rank, world_size, offload_quantization_config)
    

    state_dict_to_broadcast = {}
    for name, param in model.named_parameters():
        if name not in offload_parameter_names_in_order:
            if is_master:
                param.data = param.data.to(onload_device)
            state_dict_to_broadcast[name] = (
                param.data
                if is_master else
                torch.empty_like(param.data, device=onload_device, dtype=param.data.dtype)
            )
    for key in state_dict_to_broadcast.keys():
        dist.broadcast(state_dict_to_broadcast[key], src=MASTER_RANK)
    model.load_state_dict(state_dict_to_broadcast, strict=False, assign=True)
    
    for name, buffer in model.named_buffers():
        buffer.to(onload_device)
    
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
        pre_hook, pre_hook_handle_ref = _make_pre_hook(registry, module_name, param_names, model.get_submodule(module_name), offload_device)
        pre_hook_handle = model.get_submodule(module_name).register_forward_pre_hook(pre_hook)
        pre_hook_handle_ref.set_handle(pre_hook_handle)
        pre_hook_handles.append(pre_hook_handle)
        
        remove_post_hook, post_hook_handle_ref = _create_one_time_hook_remover()
        post_hook = _make_post_hook(registry, module_name, param_names, remove_post_hook, post_hook_handles)
        post_hook_handle = model.get_submodule(module_name).register_forward_hook(post_hook)
        post_hook_handle_ref.set_handle(post_hook_handle)
        
    torch.cuda.empty_cache()
    return registry, pre_hook_handles, post_hook_handles

# def auto_setup_offload(
#     model: torch.nn.Module,
#     onload_device: torch.device,
#     rank: int,
#     world_size: int,
#     offload_device: Optional[torch.device] = None,
#     blocks_to_keep: Optional[int] = None,
#     param_name_blacklist_keywords: Optional[List[str]] = None,
#     offload_quantization_config: Optional[OffloadQuantizationConfig] = None,
#     numel_threshold: Optional[int] = None,
#     bytes_at_least: Optional[int] = None,
# ) -> List[Tuple[TensorRegistry, List[torch.utils.hooks.RemovableHandle], List[torch.utils.hooks.RemovableHandle]]]:
#     """
#     Automatically detect module lists and set up tensor offloading for them.
    
#     Model will be moved to the offload device (default to CPU) if not after the setup. After the setup, the model will function as if it were on the onload device.
    
#     Usage:
#         _ = auto_setup_offload(model, torch.device("cuda"), torch.device("cpu"), blocks_to_keep=4, offload_quantization_config={"offload_dtype": torch.float8_e4m3fn})
    
#     Effect:
#         Generates offload module configurations based on model structure
#         Sets up tensor offloading for each configuration
#         Returns list of offload setups
        
#     Requires:
#         onload_device.type == "cuda"
        
#     Args:
#         model: The model to offload tensors for
#         onload_device: Device to load tensors onto (must be CUDA)
#         offload_device: Device to offload tensors to (default to CPU)
#         blocks_to_keep: Number of blocks to keep on the GPU
#         param_name_blacklist_keywords: Keywords to blacklist parameter names from offloading
#         offload_quantization_config: Configuration for quantization, if any. If it is None, no quantization will be performed. Otherwise, it should be a dictionary with following keys,
#             - "offload_dtype": torch.dtype, dtype to offload to, default to torch.float8_e4m3fn
#             - "enable_scale": bool, whether to enable scale, default to False
#             - "enable_bias": bool, whether to enable bias default to False
#         numel_threshold: Parameters having numels fewer than this will be ignored to prevent fragmented reading/writing
#         bytes_at_least: If not set, will try to offload as many parameters as possible. If set, will try to offload on slightly above this number of bytes.
#         world_size: Number of processes in distributed training, default to 1 (single process)
#         rank: Rank of current process, default to 0
#         process_group: Process group for distributed communication, default to None (use default group)
    
#     Returns:
#         List of tuples containing: TensorRegistry: The tensor registry managing offloaded tensors; List[RemovableHandle]: Pre-hook remove handles; List[RemovableHandle]: Post-hook remove handles, note that this is a list that will be modified after the first forward pass. It would stay empty before that.
        
#         The returned values can be safely ignored completely.
        
#     Raises:
#         NotImplementedError: If onload_device is not a CUDA device
#     """
#     if onload_device.type != "cuda":
#         raise NotImplementedError("onload_device must be a CUDA device")
#     if offload_device is None:
#         offload_device = torch.device("cpu")
#     configs = None
#     if rank == MASTER_RANK:
#         configs = generate_offload_modules(model, blocks_to_keep, param_name_blacklist_keywords, numel_threshold, bytes_at_least)
#     dist.barrier()
#     configs = [configs]
#     dist.broadcast_object_list(configs, src=MASTER_RANK, device=torch.device("cpu"))[0]
#     configs = configs[0]
#     return [
#         setup_offload(model, onload_device, offload_device, offload_param_names, numels, rank, world_size, offload_quantization_config)
#         for offload_param_names, numels in configs
#     ]