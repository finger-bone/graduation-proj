import torch
from typing import Dict, List, Optional, TypedDict
from collections import namedtuple
from .const import MASTER_RANK
import torch.distributed as dist

class OffloadTensorRegistryBuilder:
    """
    Builds a registry of tensors for offloading.
    All tensors must have the same dtype and reside on the same device.
    """
    
    def __init__(self, dtype: Optional[torch.dtype] = None, device: Optional[torch.device] = None):
        """
        Initialize the tensor registry builder.
        
        Args:
            dtype: Data type for all tensors
            device: Device where all tensors are located
        """
        self.tensors: Dict[str, torch.Tensor] = {}
        self.tensor_order: List[str] = []
        self.dtype = dtype
        self.device = device
        
    def numels(self) -> int:
        """
        Count the total number of elements across all tensors.
        
        Returns:
            Total number of elements
        """
        return sum(t.numel() for t in self.tensors.values())
        
    def add_tensor(self, name: str, tensor: torch.Tensor) -> "OffloadTensorRegistryBuilder":
        """
        Add a tensor to the registry.
        
        Effect:
            Modifies self.tensors and self.tensor_order
            Updates self.dtype and self.device to match the tensor's properties
            
        Args:
            name: Name identifier for the tensor
            tensor: The tensor to add
            
        Returns:
            Self reference for chaining
            
        Raises:
            RuntimeError: If tensor has different dtype or device than expected
        """
        if self.dtype is not None and tensor.dtype != self.dtype:
            raise RuntimeError("Every tensor must be of the same dtype")
        if self.device is not None and tensor.device != self.device:
            raise RuntimeError("Every tensor must be on the same device")
        self.dtype = tensor.dtype
        self.device = tensor.device
            
        self.tensors[name] = tensor
        self.tensor_order.append(name)
        return self

# Replace the TypedDict with namedtuple
TensorInBufferMeta = namedtuple('TensorInBufferMeta', ['start', 'end', 'shape'])

class OffloadQuantizationConfig(TypedDict):
    """Configuration for quantization."""
    enable_scale: bool
    enable_bias: bool
    offload_dtype: torch.dtype

class TensorRegistry:
    """
    Manages tensor offloading between CPU and GPU memory with double buffering.
    """
    def _master_init(self,
                 builder: OffloadTensorRegistryBuilder,
                 onload_numel: int,
                 onload_device: torch.device,
                 quantization_config: Optional[OffloadQuantizationConfig] = None,
                 ) -> None:
        """
        Init for the master node
        Initialize the tensor registry with double buffering.
        
        Effect:
            Initializes all internal buffers, metadata, and async loading mechanisms
            Performs initial buffer loading and rotation
            
        Requires:
            onload_device.type == "cuda"
            
        Args:
            builder: Builder containing tensors to manage
            onload_numel: Total number of elements that can be loaded at once
            onload_device: Device to load tensors onto, must be CUDA at the moment
            quantization_config: Configuration for quantization, if any. If it is not None, default values for enable_bias and enable_scale are False, and default value for offload_dtype is torch.float8_e4m3fn.
            
        Raises:
            NotImplementedError: If onload_device is not CUDA
            RuntimeError: If any tensor is larger than the onload buffer
        """
        if onload_device.type != "cuda":
            raise NotImplementedError("onload_device must be CUDA")
        self.offload_device = builder.device
        self.device = onload_device
        self.dtype = builder.dtype
        self.total_numel = builder.numels()
        self.onload_numel = onload_numel // 2
        
        # Process quantization config and store values directly in self
        if quantization_config is not None:
            self.quantization_config = True
            self.enable_bias = quantization_config.get("enable_bias", False)
            self.enable_scale = quantization_config.get("enable_scale", False)
            self.offload_dtype = quantization_config.get("offload_dtype", torch.float8_e4m3fn)
        else:
            self.quantization_config = False
            self.enable_bias = False
            self.enable_scale = False
            self.offload_dtype = self.dtype
        
        self.ready_buffer = torch.empty(
            self.onload_numel, 
            dtype=self.dtype, 
            device=self.device,
            requires_grad=False,
        )
        self.loading_buffer = torch.empty(
            self.onload_numel, 
            dtype=self.dtype, 
            device=self.device,
            requires_grad=False
        )
        self.offload_buffer = torch.empty(
            self.total_numel, 
            dtype=self.dtype if not self.quantization_config else self.offload_dtype,
            device=self.offload_device, 
            pin_memory=True if self.offload_device.type == "cpu" else False,
            requires_grad=False
        )
        self.ready_buffer_meta: Dict[str, TensorInBufferMeta] = {}
        self.loading_buffer_meta: Dict[str, TensorInBufferMeta] = {}
        self.chunks: List[List[str]] = []
        self.loading_chunk_idx: int = 0
        chunk_size = 0
        current_chunk: List[str] = []
        for name, tensor in builder.tensors.items():
            numel = tensor.numel()
            if current_chunk and chunk_size + numel > self.onload_numel:
                self.chunks.append(current_chunk)
                current_chunk = []
                chunk_size = 0
            if numel > self.onload_numel:
                raise RuntimeError("Offloading tensor larger than the onload buffer!")
            current_chunk.append(name)
            chunk_size += numel
            
        if current_chunk:
            self.chunks.append(current_chunk)
            
        if len(self.chunks) % 2 != 0:
            self.extra_rotate_idx = len(self.chunks)
            self.chunks.append([])
        else:
            self.extra_rotate_idx = None

        if self.quantization_config:
            self.scales = [1.] * len(self.chunks)
            self.biases = [0.] * len(self.chunks)
            for chunk_idx, chunk in enumerate(self.chunks):
                chunk_sum = 0.
                chunk_numel = 0.
                chunk_mean = 0.
                if self.enable_bias:
                    for name in chunk:
                        tensor = builder.tensors[name]
                        chunk_sum += tensor.sum().item()
                        chunk_numel += tensor.numel()
                    chunk_mean = chunk_sum / chunk_numel
                self.biases[chunk_idx] = chunk_mean
                abs_max = 0.
                if self.enable_scale:
                    for name in chunk:
                        tensor = builder.tensors[name]
                        abs_max = max(abs_max, (tensor - chunk_mean).abs().max().item())
                self.scales[chunk_idx] = abs_max / torch.finfo(self.offload_dtype).max if abs_max > 1e-8 else 1.0
        else:
            self.scales = None
            self.biases = None
        
        self.offload_meta: Dict[str, TensorInBufferMeta] = {}
        offset = 0
        
        for chunk_idx, chunk in enumerate(self.chunks):
            for name in chunk:
                tensor = builder.tensors[name]
                end = tensor.numel() + offset
                self.offload_meta[name] = TensorInBufferMeta(
                    start=offset,
                    end=end,
                    shape=tensor.shape,
                )
                tensor_to_store = tensor.flatten().clone()
                if self.quantization_config and self.enable_bias:
                    tensor_to_store.sub_(self.biases[chunk_idx])
                if self.quantization_config and self.enable_scale:
                    tensor_to_store.div_(self.scales[chunk_idx])
                self.offload_buffer[offset:end].copy_(tensor_to_store)
                offset = end
        self.chunk_metadata: List[Dict[str, TensorInBufferMeta]] = []
        
        for chunk_idx, chunk in enumerate(self.chunks):
            chunk_meta: Dict[str, TensorInBufferMeta] = {}
            offset_in_buffer = 0
            
            for name in chunk:
                meta = self.offload_meta[name]
                numel = meta.end - meta.start
                chunk_meta[name] = TensorInBufferMeta(
                    start=offset_in_buffer,
                    end=offset_in_buffer + numel,
                    shape=meta.shape,
                )
                offset_in_buffer += numel
            
            self.chunk_metadata.append(chunk_meta)
            
    def _broadcast_to_follower(self) -> None:
        property_names = [
            "offload_device", "dtype", "total_numel", "onload_numel", "quantization_config",
            "enable_bias", "enable_scale", "offload_dtype", "ready_buffer_meta",
            "loading_buffer_meta", "chunks", "loading_chunk_idx", "offload_meta",
            "chunk_metadata", "scales", "biases", "extra_rotate_idx"
        ]

        if self.is_master:
            object_list = [getattr(self, name) for name in property_names]
        else:
            object_list = [None] * len(property_names)

        dist.broadcast_object_list(object_list, src=0, device=torch.device("cpu"))

        if not self.is_master:
            for name, value in zip(property_names, object_list):
                setattr(self, name, value)

    
    def _follower_init(self) -> None:
        self.ready_buffer = torch.empty(
            self.onload_numel, 
            dtype=self.dtype, 
            device=self.device,
            requires_grad=False,
        )
        self.loading_buffer = torch.empty(
            self.onload_numel, 
            dtype=self.dtype, 
            device=self.device,
            requires_grad=False
        )
        
    def __init__(self,
                 builder: OffloadTensorRegistryBuilder,
                 onload_numel: int,
                 onload_device: torch.device,
                 rank: int,
                 world_size: int,
                 quantization_config: Optional[OffloadQuantizationConfig] = None,
                 ) -> None:
        self.rank = rank
        self.world_size = world_size
        self.device = onload_device
        self.is_master = (rank == MASTER_RANK)
        if self.is_master:
            self._master_init(
                builder, onload_numel, onload_device, quantization_config
            )
        dist.barrier()
        self._broadcast_to_follower()
        if not self.is_master:
            self._follower_init()
        
        self.loading_stream = torch.cuda.Stream(self.device)
        self.loading_event = torch.cuda.Event()
        self._load_chunk_meta(0)
        if self.is_master:
            self._load_chunk(0)
        dist.broadcast(self.ready_buffer, src=MASTER_RANK)
        self._rotate()
    
    def _rotate(self) -> None:
        self.loading_event.synchronize()
        
        self.ready_buffer, self.loading_buffer = self.loading_buffer, self.ready_buffer 
        self.ready_buffer_meta = self.loading_buffer_meta
        self.loading_chunk_idx = (self.loading_chunk_idx + 1) % len(self.chunks)
        self._load_chunk_meta(self.loading_chunk_idx)
        if self.is_master:
            self._load_chunk(self.loading_chunk_idx)
        if self.extra_rotate_idx == self.loading_chunk_idx:
            self._rotate()
            return
        dist.broadcast(self.ready_buffer, src=MASTER_RANK)
        
    def _load_chunk_meta(self, chunk_idx: int) -> None:
        self.loading_buffer_meta = self.chunk_metadata[chunk_idx]
        
    def _load_chunk(self, chunk_idx: int) -> None:
        chunk = self.chunks[chunk_idx]
        # Determine range of data to copy from offload buffer
        offload_buffer_start = self.offload_meta[chunk[0]].start
        offload_buffer_end = self.offload_meta[chunk[-1]].end
        src_tensor = self.offload_buffer[offload_buffer_start:offload_buffer_end]
        
        # Perform asynchronous copy
        with torch.cuda.stream(self.loading_stream):
            self.loading_buffer[:offload_buffer_end - offload_buffer_start].copy_(
                src_tensor, non_blocking=True
            )
            if self.quantization_config:
                if self.enable_scale and self.enable_bias:
                    self.loading_buffer.addcmul_(self.scales[chunk_idx], self.biases[chunk_idx])
                else:
                    if self.enable_scale:
                        self.loading_buffer.mul_(self.scales[chunk_idx])
                    if self.enable_bias:
                        self.loading_buffer.add_(self.biases[chunk_idx])
            self.loading_event.record(self.loading_stream)
    
    def release(self, names: List[str]) -> bool:
        """
        Release tensors from the ready buffer. If all tensors are released, trigger buffer rotation (release ready buffer, make loading buffer ready if loaded, and load the next chunk).
        
        Effect:
            Removes tensors from ready_buffer_meta
            Triggers buffer rotation if all tensors are released
            Synchronizes CUDA stream if rotation occurs
            
        Args:
            names: Names of tensors to release
            
        Returns:
            True if buffer rotation was triggered, False otherwise
        """
        # Remove released tensors from metadata
        for name in names:
            self.ready_buffer_meta.pop(name, None)
            
        # If no tensors remain, rotate buffers
        if len(self.ready_buffer_meta) == 0:
            torch.cuda.current_stream(self.device).synchronize()
            self._rotate()
            return True
        return False
    
    def release_all(self) -> None:
        """
        Release all tensors and trigger buffer rotation (release ready buffer, make loading buffer ready if loaded, and load the next chunk).
        
        Effect:
            Synchronizes CUDA stream and rotates buffers
        """
        torch.cuda.current_stream(self.device).synchronize()
        self._rotate()
                
    def get(self, name: str) -> torch.Tensor:
        """
        Retrieve a tensor from the ready buffer.

        Requires:
            name must exist in ready_buffer_meta
            
        Args:
            name: Name of tensor to retrieve
            
        Returns:
            View of the requested tensor
        """
        meta = self.ready_buffer_meta[name]
        tensor_view = self.ready_buffer[meta.start:meta.end].view(meta.shape)
        return tensor_view