from dataclasses import dataclass


@dataclass
class ScanResult:
    leaf_module_usage_order: list[str]
    compute_time: dict[str, float]  # ns
    compute_time_std: dict[str, float]  # ns
    onload_time: dict[str, float]  # ns
    onload_time_std: dict[str, float]  # ns
    memory: dict[str, float]  # bytes

    def __init__(self) -> None:
        self.leaf_module_usage_order = []
        self.compute_time = {}
        self.compute_time_std = {}
        self.onload_time = {}
        self.onload_time_std = {}
        self.memory = {}
