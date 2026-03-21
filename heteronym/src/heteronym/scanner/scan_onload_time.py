import torch
from .scan_result import ScanResult
from typing import Any
import time
import numpy as np
from .logger import logger


def scan_onload_time(
    results: dict[str, ScanResult],
    onload_device: torch.device,
    offload_device: torch.device,
    warmup_steps: int = 3,
    sampling_steps: int = 10,
) -> None:
    """
    测试从offload_device到onload_device的数据传输时间，以纳秒/字节为单位
    使用128MB缓冲区进行测试

    Args:
        results: ScanResult字典，用于存储测试结果
        onload_device: 加载设备 (如cuda)
        offload_device: 卸载设备 (如cpu)
        warmup_steps: 预热步数
        sampling_steps: 采样步数
        test_on_offload_device: 是否在offload设备上测试
    """
    logger.info("Starting onload time scanning")
    logger.debug(f"Devices - Onload: {onload_device}, Offload: {offload_device}")
    logger.debug(f"Warmup steps: {warmup_steps}, Sampling steps: {sampling_steps}")

    # 创建128MB缓冲区
    buffer_size = 128 * 1024 * 1024  # 128 MB
    num_elements = buffer_size // 4  # 假设使用float32，每个元素4字节

    logger.debug(
        f"Creating buffer of size {buffer_size} bytes ({num_elements} float32 elements)"
    )

    # 在offload_device上创建源张量
    logger.debug(f"Creating source tensor on device: {offload_device}")
    src_tensor = torch.empty(num_elements, dtype=torch.float32, device=offload_device)

    # 在onload_device上创建目标张量
    logger.debug(f"Creating destination tensor on device: {onload_device}")
    dst_tensor = torch.empty(num_elements, dtype=torch.float32, device=onload_device)

    # 预热
    logger.debug(f"Running {warmup_steps} warmup steps for data transfer")
    for _ in range(warmup_steps):
        dst_tensor.copy_(src_tensor)
        if onload_device.type == "cuda":
            logger.debug("Synchronizing CUDA device")
            torch.cuda.synchronize()
        elif onload_device.type == "mps":
            logger.debug("Synchronizing MPS device")
            torch.mps.synchronize()

    # 实际测量
    logger.debug(
        f"Running {sampling_steps} sampling steps for data transfer measurement"
    )
    measures = []
    for _ in range(sampling_steps):
        start = time.perf_counter_ns()
        dst_tensor.copy_(src_tensor)
        if onload_device.type == "cuda":
            torch.cuda.synchronize()
        elif onload_device.type == "mps":
            torch.mps.synchronize()
        end = time.perf_counter_ns()
        measures.append(end - start)

    # 计算平均值和标准差
    avg_time = float(np.average(measures))
    std_time = float(np.std(measures))

    logger.debug(f"Average transfer time: {avg_time}ns (std: {std_time}ns)")

    # 计算每字节传输时间 (ns/byte)
    time_per_byte = avg_time / buffer_size
    logger.debug(f"Transfer speed: {time_per_byte}ns/byte")

    # # 将结果存储到所有ScanResult中
    # for result in results.values():
    #     # 使用特殊键表示整体传输速度
    #     result.onload_time["__transfer_speed__"] = time_per_byte
    #     result.onload_time_std["__transfer_speed__"] = std_time / buffer_size
    for result in results.values():
        for leaf_module_name in result.leaf_module_usage_order:
            onload_time = result.memory[leaf_module_name] * time_per_byte
            onload_time_std = result.memory[leaf_module_name] * std_time / buffer_size
            result.onload_time[leaf_module_name] = onload_time
            result.onload_time_std[leaf_module_name] = onload_time_std
            logger.debug(
                f"Module {leaf_module_name} onload time: {onload_time}ns (std: {onload_time_std}ns)"
            )

    logger.info("Onload time scanning completed")
