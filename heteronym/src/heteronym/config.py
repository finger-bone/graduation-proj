"""全局配置模块 - 管理 DEBUG 等环境变量"""

import os

# 从环境变量读取 DEBUG 配置
# 当 DEBUG=true 时，所有模型将在 CPU 上运行，绕过 CUDA
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def is_debug_mode() -> bool:
    """检查是否处于 DEBUG 模式"""
    return DEBUG


def get_device(device_id: int = 0):
    """
    获取设备对象
    
    Args:
        device_id: CUDA 设备 ID
        
    Returns:
        torch.device 对象，DEBUG 模式下返回 cpu，否则返回 cuda:{device_id}
    """
    import torch
    if DEBUG:
        return torch.device("cpu")
    return torch.device(f"cuda:{device_id}")
