from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import torch
import transformers
import threading
from collections import deque

from heteronym.server.db.client import TorchModel, get_db
from heteronym.scanner.scan_result import ScanResult
from heteronym.scanner.get_leaf_module_names import get_leaf_module_names
from heteronym.scanner.scan_usage_order import scan_usage_order
from heteronym.scanner.scan_compute_time import scan_compute_time
from heteronym.scanner.scan_onload_time import scan_onload_time
from heteronym.scanner.scan_memory import scan_memory
from heteronym.scanner.get_module_lists import get_top_module_lists
from heteronym.server.logger import logger
from heteronym.server.router.example_generator import generate_example_inputs

from diffusers import DiffusionPipeline

import os

MAX_PENDING_WORK = int(os.getenv("MAX_PENDING_WORK") if os.getenv("MAX_PENDING_WORK") else "1")

scanner_router = APIRouter()

from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=1)
# 使用双端队列来跟踪正在运行/等待的任务
task_queue = deque()
task_queue_lock = threading.Lock()

def scan_model(
    model_id: str, test_on_offload_device: bool, warmup_steps: int, sampling_steps: int
):

    logger.info(f"Starting model scan for model ID: {model_id}")
    logger.debug(
        f"Scan parameters - test_on_offload_device: {test_on_offload_device}, "
        f"warmup_steps: {warmup_steps}, sampling_steps: {sampling_steps}"
    )

    db = next(get_db())
    model: TorchModel = db.query(TorchModel).filter(TorchModel.id == model_id).first()

    if not model:
        logger.error(f"Model with ID {model_id} not found in database")
        return

    logger.debug(f"Found model: {model.name}")
    model.scan_status = "scanning"
    db.commit()
    logger.info(f"Updated model status to 'scanning'")

    try:
        onload_device = (
            torch.device("cuda")
            if torch.cuda.is_available()
            else (
                torch.device("mps")
                if torch.backends.mps.is_available()
                else torch.device("cpu")
            )
        )
        offload_device = torch.device("cpu")

        logger.debug(
            f"Using onload device: {onload_device}, offload device: {offload_device}"
        )

        if model.hf_name.startswith("pipe:"):
            real_name = model.hf_name.split(":")[1]
            model_instance = DiffusionPipeline.from_pretrained(
                real_name, cache_dir=model.path
            )
            # get the backbone model
            if hasattr(model_instance, "transformer"):
                model_instance = model_instance.transformer
            elif hasattr(model_instance, "unet"):
                model_instance = model_instance.unet
            logger.debug(f"The pipeline has properties of {model_instance.__dict__}")
            logger.debug(f"Successfully loaded model: {type(model_instance)}")
        elif model.hf_name:
            logger.info(f"Loading model from HuggingFace: {model.hf_name}")
            # model_instance = transformers.AutoModel.from_pretrained(model.hf_name, cache_dir=model.path)
            model_instance = transformers.AutoModelForCausalLM.from_pretrained(
                model.hf_name, cache_dir=model.path
            ).to(onload_device if not test_on_offload_device else offload_device)
            logger.debug(f"Successfully loaded model: {type(model_instance)}")
        else:
            logger.error("Local model loading not implemented")
            raise NotImplementedError("Local model loading not implemented")

        if not test_on_offload_device:
            logger.debug("Moving model to onload device")
            model_instance = model_instance.to(onload_device)

        logger.info("Getting top module lists")
        module_lists = get_top_module_lists(model_instance)
        logger.debug(f"Found {len(module_lists)} module lists")

        example_modules = {
            module_list_name: module_list[(len(module_list) - 1) // 2]
            for module_list_name, module_list in module_lists.items()
        }
        leaf_module_names = {
            module_list_name: get_leaf_module_names(example_modules[module_list_name])
            for module_list_name in module_lists.keys()
        }

        scan_results = {
            module_list_name: ScanResult() for module_list_name in module_lists.keys()
        }

        # 使用新的示例输入生成器
        example_inputs_args, example_inputs_kwargs = generate_example_inputs(
            model=model_instance,
            model_name=model.hf_name,
            onload_device=onload_device,
            offload_device=offload_device,
            test_on_offload_device=test_on_offload_device,
        )
        logger.debug(
            f"Generated example inputs: {example_inputs_args}, {example_inputs_kwargs}"
        )

        logger.info("Scanning usage order")
        model.scan_status = "scanning_usage_order"
        db.commit()
        logger.debug("Updated model status to 'scanning_usage_order'")
        scan_usage_order(
            model=model_instance,
            example_inputs_args=example_inputs_args,
            example_inputs_kwargs=example_inputs_kwargs,
            example_modules=example_modules,
            leaf_module_names=leaf_module_names,
            results=scan_results,
        )
        logger.debug("Usage order scanning completed")

        # Step 2: Scan compute time
        logger.info("Scanning compute time")
        model.scan_status = "scanning_compute_time"
        db.commit()
        logger.debug("Updated model status to 'scanning_compute_time'")
        scan_compute_time(
            model=model_instance,
            example_inputs_args=example_inputs_args,
            example_inputs_kwargs=example_inputs_kwargs,
            example_modules=example_modules,
            leaf_module_names=leaf_module_names,
            results=scan_results,
            onload_device=onload_device,
            offload_device=offload_device,
            warmup_steps=warmup_steps,
            sampling_steps=sampling_steps,
            test_on_offload_device=test_on_offload_device,
        )
        logger.debug("Compute time scanning completed")

        # Step 4: Scan memory
        logger.info("Scanning memory")
        model.scan_status = "scanning_memory"
        db.commit()
        logger.debug("Updated model status to 'scanning_memory'")
        scan_memory(
            example_modules=example_modules,
            leaf_module_names=leaf_module_names,
            results=scan_results,
        )
        logger.debug("Memory scanning completed")

        # Step 3: Scan onload time
        logger.info("Scanning onload time")
        model.scan_status = "scanning_onload_time"
        db.commit()
        logger.debug("Updated model status to 'scanning_onload_time'")
        scan_onload_time(
            results=scan_results,
            onload_device=onload_device,
            offload_device=offload_device,
        )
        logger.debug("Onload time scanning completed")

        # Convert scan results to a JSON-serializable format
        logger.info("Converting scan results to serializable format")
        serializable_results = {}
        for key, result in scan_results.items():
            serializable_results[key] = {
                "leaf_module_usage_order": result.leaf_module_usage_order,
                "compute_time": result.compute_time,
                "compute_time_std": result.compute_time_std,
                "onload_time": result.onload_time,
                "onload_time_std": result.onload_time_std,
                "module_list_len": {k: len(l) for k, l in module_lists.items()},
                "memory": result.memory,
            }

        model.scan_results = serializable_results
        model.scan_status = "completed"
        db.commit()
        logger.info(f"Model scan completed successfully for model ID: {model_id}")

    except Exception as e:
        logger.exception(f"Scan failed for model {model_id}: {str(e)}")
        model.scan_status = "failed"
        # In a real implementation, you might want to store the error message
        print(f"Scan failed for model {model_id}: {str(e)}")
        db.commit()
    finally:
        # 任务完成时从队列中移除
        with task_queue_lock:
            if model_id in task_queue:
                task_queue.remove(model_id)
                logger.debug(f"Removed model {model_id} from task queue")


@scanner_router.post("/request-scan")
async def request_scan(
    model_id: str,
    test_on_offload_device: bool = True,
    warmup_steps: int = 10,
    sampling_steps: int = 10,
    db: Session = Depends(get_db),
):
    logger.debug(f"Processing scan request for model ID: {model_id}")
    logger.debug(f"MAX PENDING WORK: {MAX_PENDING_WORK}")
    if len(task_queue) >= MAX_PENDING_WORK:
        db.query(TorchModel).filter(TorchModel.id == model_id).update(
            {"scan_status": "failed"}
        )
        db.commit()
        return {"message": "扫描队列已满，请等待。", "model_id": model_id, "failed": True}
    
    logger.info(f"Received scan request for model ID: {model_id}")

    # Submit the scan task to the thread pool
    logger.debug("Submitting scan task to thread pool")
    executor.submit(
        scan_model, model_id, test_on_offload_device, warmup_steps, sampling_steps
    )

    # 将任务添加到队列中
    with task_queue_lock:
        task_queue.append(model_id)
        logger.info(
            f"Added model {model_id} to task queue. Queue size: {len(task_queue)}"
        )

    return {"message": "Scan task queued", "model_id": model_id}


@scanner_router.get("/get-scan-status/{model_id}")
async def get_scan_status(model_id: str, db: Session = Depends(get_db)):
    logger.debug(f"Fetching scan status for model ID: {model_id}")
    model: TorchModel = db.query(TorchModel).filter(TorchModel.id == model_id).first()
    logger.debug(f"Model {model_id} scan status: {model.scan_status}")
    return {"status": model.scan_status}


@scanner_router.get("/get-queue-size")
async def get_queue_size():
    with task_queue_lock:
        size = len(task_queue)
        logger.debug(f"Current task queue size: {size}")
        return {"queue_size": size}


@scanner_router.get("/get-order-in-queue/{model_id}")
async def get_order_in_queue(model_id: str):
    logger.debug(f"Checking order in queue for model ID: {model_id}")
    with task_queue_lock:
        try:
            # 查找model_id在队列中的位置（1-indexed）
            order = list(task_queue).index(model_id) + 1
            logger.debug(f"Model {model_id} is at position {order} in queue")
            return {"order_in_queue": order}
        except ValueError:
            # 如果找不到任务，则返回-1
            logger.debug(f"Model {model_id} not found in queue")
            return {"order_in_queue": -1}
