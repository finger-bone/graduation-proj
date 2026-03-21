from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import torch
import transformers
from typing import Literal
import socket
import multiprocessing

from heteronym.server.db.client import OffloadConfig, TorchModel, get_db

deploy_router = APIRouter()

# model id -> [port1, port2, ...]
deployed_models = {}
# (model id, port) -> process
deployed_process = {}

@deploy_router.get("/device-count")
async def get_device_count():
    # return {"device_count": torch.cuda.device_count()}
    return {"count": 2}


def find_free_port(start=1145, end=65535):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def worker_process(model, offload_config, enable_offload, device, port, model_kind):
    """
    子进程执行函数
    """
    if model_kind == "lm":
        from .deploy.lm import create_ui
        ui = create_ui(model, offload_config, enable_offload, device)
        ui.launch(server_name="0.0.0.0", server_port=port)


@deploy_router.post("/create")
async def create_deployment(
    model_id: str,
    device: int,
    offload_id: int,
    model_kind: Literal["lm"] | Literal["t2v"] | Literal["t2i"] = "lm",
    enable_offload: bool = False,
    port: int | None = None,
    db: Session = Depends(get_db),
):
    model = db.query(TorchModel).filter(TorchModel.id == model_id).first()

    if not port:
        port = find_free_port()

    offload_config = db.query(OffloadConfig).filter(
        OffloadConfig.id == offload_id
    ).first()

    # 创建子进程
    process = multiprocessing.Process(
        target=worker_process,
        args=(model, offload_config, enable_offload, device, port, model_kind),
        daemon=True,
    )

    global deployed_models
    global deployed_process

    if model_id not in deployed_models:
        deployed_models[model_id] = []
    deployed_models[model_id].append(port)
    deployed_process[(model_id, port)] = process

    process.start()

    return {"port": port}


@deploy_router.get("/ports/{model_id}")
async def get_ports(model_id: str):
    global deployed_models
    return {
        "ports": deployed_models.get(model_id, [])
    }


@deploy_router.post("/stop")
async def stop_deployment(model_id: str, port: int):
    global deployed_process

    process: multiprocessing.Process = deployed_process.get((model_id, port), None)

    if process and process.is_alive():
        process.terminate()
        process.join(timeout=5)

        # 清理记录
        del deployed_process[(model_id, port)]

        if model_id in deployed_models:
            deployed_models[model_id] = [
                p for p in deployed_models[model_id] if p != port
            ]

    return {"message": "Stopped"}