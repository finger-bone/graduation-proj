import torch
from typing import TypedDict


class QuantizationConfig(TypedDict):

    quantize: bool
    quantize_dtype: torch.dtype
    enable_scale: bool
    enable_bias: bool


class OffloadTensorRegistryBuilder:

    def __init__(self, dtype: torch.dtype, device: torch.device):
        self.tensors: dict[str, torch.Tensor] = {}
        self.tensor_order: list[str] = []
        self.dtype = dtype
        self.device = device

    def count(self) -> int:
        return sum([t.numel() for t in self.tensors.values()])

    def add_tensor(
        self, name: str, tensor: torch.Tensor
    ) -> "OffloadTensorRegistryBuilder":
        if tensor.dtype != self.dtype:
            raise RuntimeError("Every tensor must be of the same dtype")
        if tensor.device != self.device:
            raise RuntimeError("Every tensor must be on the same device")
        self.dtype = tensor.dtype
        self.tensors[name] = tensor.clone().detach().contiguous()
        self.tensor_order.append(name)
        return self


class TensorInBufferMeta(TypedDict):

    start: int
    end: int
    shape: list[int]


class TensorRegistry:

    def _create_offload_buffer(self, builder: OffloadTensorRegistryBuilder):
        self.offload_meta: dict[str, TensorInBufferMeta] = {}
        offset = 0
        for name, tensor in builder.tensors.items():
            end = tensor.numel() + offset
            self.offload_meta[name] = {
                "start": offset,
                "end": end,
                "shape": tensor.shape,
            }

            # 如果启用了量化，则对张量进行量化处理
            if self.quantization_config.get("quantize", False):
                tensor_data = tensor.flatten()
                # 量化过程：将数据转换为指定的量化类型
                if self.quantization_config.get(
                    "enable_scale", False
                ) or self.quantization_config.get("enable_bias", False):
                    # 如果启用了scale或bias，使用预先计算的值
                    chunk_idx = self._get_chunk_index(name)
                    if self.quantization_config.get("enable_scale", False):
                        scale = self.chunk_scales[chunk_idx]
                        tensor_data = tensor_data / scale
                    if self.quantization_config.get("enable_bias", False):
                        bias = self.chunk_biases[chunk_idx]
                        tensor_data = tensor_data - bias
                    # 转换为量化类型
                    tensor_data = tensor_data.to(
                        self.quantization_config["quantize_dtype"]
                    )
                else:
                    # 直接转换为量化类型
                    tensor_data = tensor_data.to(
                        self.quantization_config["quantize_dtype"]
                    )
                self.offload_buffer[offset:end].copy_(tensor_data)
            else:
                # 未启用量化，保持原有逻辑
                self.offload_buffer[offset:end].copy_(tensor.flatten())
            offset = end

    def _get_chunk_index(self, name: str) -> int:
        """获取给定张量名称所属的chunk索引"""
        for idx, chunk in enumerate(self.chunks):
            if name in chunk:
                return idx
        return -1

    def _gen_chunks(self, builder: OffloadTensorRegistryBuilder):
        self.chunks: list[list[str]] = []
        self.loading_chunk_idx: int = 0
        chunk_size = 0
        current_chunk = []

        for name, tensor in builder.tensors.items():
            numel = tensor.numel()
            if current_chunk and chunk_size + numel > self.onload_numel:
                self.chunks.append(current_chunk)
                current_chunk = []
                chunk_size = 0
            if numel > self.onload_numel:
                raise RuntimeError("Offloading tensor larger than the onload buffer!")
            else:
                current_chunk.append(name)
                chunk_size += numel
        if current_chunk:
            self.chunks.append(current_chunk)
        if len(self.chunks) %2 != 0:
            self.chunks.append([
                self.chunks[-1].pop()
            ])
        # 如果启用了scale或bias，在这里计算每个chunk的scale/bias
        if self.quantization_config.get(
            "enable_scale", False
        ) or self.quantization_config.get("enable_bias", False):
            self.chunk_scales: dict[int, float] = {}
            self.chunk_biases: dict[int, float] = {}

            for chunk_idx, chunk in enumerate(self.chunks):
                # 收集当前chunk中的所有张量数据
                chunk_data = []
                for name in chunk:
                    tensor = builder.tensors[name]
                    chunk_data.append(tensor.flatten())

                if chunk_data:  # 确保有数据
                    all_data = torch.cat(chunk_data)

                    if self.quantization_config.get("enable_scale", False):
                        # 计算scale为数据的最大绝对值
                        max_abs_val = torch.max(torch.abs(all_data)).item()
                        self.chunk_scales[chunk_idx] = (
                            max_abs_val if max_abs_val > 0 else 1.0
                        )

                    if self.quantization_config.get("enable_bias", False):
                        # 计算bias为数据的最小值
                        min_val = torch.min(all_data).item()
                        self.chunk_biases[chunk_idx] = min_val

    def __init__(
        self,
        builder: OffloadTensorRegistryBuilder,
        onload_numel: int,
        onload_device: torch.device,
        quantization_config: QuantizationConfig = None,
    ):
        self.offload_device = builder.device
        self.device = onload_device
        self.dtype = builder.dtype
        self.total_numel = builder.count()
        self.onload_numel = onload_numel // 2
        self.quantization_config = (
            quantization_config
            if quantization_config is not None
            else {
                "quantize": False,
                "quantize_dtype": torch.int8,
                "enable_scale": False,
                "enable_bias": False,
            }
        )

        # 根据是否启用量化决定offload_buffer的数据类型
        offload_dtype = (
            self.quantization_config["quantize_dtype"]
            if self.quantization_config.get("quantize", False)
            else self.dtype
        )
        self.offload_buffer = torch.empty(
            self.total_numel,
            dtype=offload_dtype,
            device=self.offload_device,
            pin_memory=True,
        )
        self.loaded_buffer = torch.empty(
            self.onload_numel, dtype=self.dtype, device=self.device
        )
        self.prefetch_buffer = torch.empty(
            self.onload_numel, dtype=self.dtype, device=self.device
        )

        self.ready_buffer_meta: dict[str, TensorInBufferMeta] = {}
        self.loading_buffer_meta: dict[str, TensorInBufferMeta] = {}

        self._gen_chunks(builder)
        self._create_offload_buffer(builder)

        self.loading_stream = torch.cuda.Stream(self.device)
        self.loading_event = torch.Event(self.device)
        self._load_chunk(0)
        self._rotate()

    def _rotate(self):
        self.loading_event.synchronize()
        self.loaded_buffer, self.prefetch_buffer = (
            self.prefetch_buffer,
            self.loaded_buffer,
        )
        self.ready_buffer_meta = self.loading_buffer_meta
        self.loading_buffer_meta = {}
        self.loading_chunk_idx = (self.loading_chunk_idx + 1) % len(self.chunks)
        self._load_chunk(self.loading_chunk_idx)

    def _load_chunk(self, chunk_idx: int):
        chunk = self.chunks[chunk_idx]
        if not chunk:
            return
        offload_buffer_start = self.offload_meta[chunk[0]]["start"]
        offload_buffer_end = self.offload_meta[chunk[-1]]["end"]
        src_tensor = self.offload_buffer[offload_buffer_start:offload_buffer_end]

        with torch.cuda.stream(self.loading_stream):
            # 先复制数据到loading buffer
            target_tensor = self.prefetch_buffer[
                : offload_buffer_end - offload_buffer_start
            ]
            target_tensor.copy_(src_tensor, non_blocking=True)

            # 如果启用了量化，需要进行反量化处理
            if self.quantization_config.get("quantize", False):
                # 反量化处理
                if self.quantization_config.get(
                    "enable_scale", False
                ) or self.quantization_config.get("enable_bias", False):
                    # 应用scale和bias进行反量化
                    if self.quantization_config.get("enable_scale", False):
                        scale = self.chunk_scales[chunk_idx]
                        target_tensor.mul_(scale)

                    if self.quantization_config.get("enable_bias", False):
                        bias = self.chunk_biases[chunk_idx]
                        target_tensor.add_(bias)

            self.loading_event.record(self.loading_stream)

        offset_in_buffer = 0
        for name in chunk:
            meta = self.offload_meta[name]
            numel = meta["end"] - meta["start"]
            self.loading_buffer_meta[name] = {
                "start": offset_in_buffer,
                "end": offset_in_buffer + numel,
                "shape": meta["shape"],
            }
            offset_in_buffer += numel

    def release(self, names: list[str]) -> bool:
        for n in names:
            self.ready_buffer_meta.pop(n)
        if len(self.ready_buffer_meta) == 0:
            torch.cuda.current_stream(self.device).synchronize()
            self._rotate()
            return True
        return False

    def release_all(self):
        self.ready_buffer_meta.clear()
        torch.cuda.current_stream(self.device).synchronize()
        self._rotate()

    def get(self, name: str) -> torch.Tensor:
        while True:
            if name in self.ready_buffer_meta:
                meta = self.ready_buffer_meta[name]
                tensor_view = self.loaded_buffer[meta["start"] : meta["end"]].view(
                    meta["shape"]
                )
                return tensor_view
