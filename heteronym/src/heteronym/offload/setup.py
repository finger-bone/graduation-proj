import torch
import torch.nn as nn
from .registry import OffloadTensorRegistryBuilder

def setup_offloading(
    model: torch.nn.Module,
    module_names: list[str],
    onload_device: torch.device,
    offload_device: torch.device,
    keep_on_model_device: int,
    use_sync: bool = False
):
    first_param = next(model.parameters())
    builder = OffloadTensorRegistryBuilder(first_param.dtype, offload_device)

    total_numels = 0
    param_to_name: dict[nn.Parameter, str] = {}

    for module_name in module_names:
        module = model.get_submodule(module_name)
        for name, param in module.named_parameters(recurse=False):
            full_name = f"{module_name}.{name}"
            builder.add_tensor(full_name, param.data)
            total_numels += param.data.numel()
            param_to_name[param] = full_name

    avg_module_numel = (
        total_numels // len(module_names) if module_names else total_numels
    )
    onload_numel = int(avg_module_numel * keep_on_model_device)
    if not use_sync:
        from .registry import TensorRegistry
    else:
        from .registry_sync import TensorRegistry
    registry = TensorRegistry(builder, onload_numel, onload_device)
    model._offload_registry = registry
    model._param_to_name = param_to_name

    def make_pre_hook(module_name: str):
        cache = [
            (p, f"{module_name}.{name}")
            for name, p in module.named_parameters(recurse=False)
        ]

        def pre_hook(module: torch.nn.Module, *_):
            for p, full_name in cache:
                p.data = registry.get(full_name)

        return pre_hook

    init_post_hook_handles = {}

    def make_post_hook(module_name: str):
        nonlocal init_post_hook_handles

        def post_hook(module: torch.nn.Module, *_):
            should_release = registry.release(
                [
                    f"{module_name}.{name}"
                    for name, p in module.named_parameters(recurse=False)
                ]
            )
            if should_release:
                module.register_forward_hook(lambda module, *_: registry.release_all())
            nonlocal init_post_hook_handles
            init_post_hook_handles[module_name].remove()

        return post_hook

    for module_name in module_names:
        module = model.get_submodule(module_name)
        pre_hook = make_pre_hook(module_name)
        post_hook = make_post_hook(module_name)
        module.register_forward_pre_hook(pre_hook)
        init_hook_handle = module.register_forward_hook(post_hook)
        init_post_hook_handles[module_name] = init_hook_handle

    return registry
