from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from heteronym.server.db.client import get_db, OffloadConfig, TorchModel
from heteronym.server.logger import logger

offload_config_router = APIRouter()


class OffloadConfigCreate(BaseModel):
    model_id: int
    name: str
    offload_layers: str
    quantize: bool = False
    quantize_dtype: str = "int8"
    enable_scale: bool = False
    enable_bias: bool = False


class OffloadConfigUpdate(BaseModel):
    name: Optional[str] = None
    offload_layers: Optional[dict] = None
    quantize: Optional[bool] = None
    quantize_dtype: Optional[str] = None
    enable_scale: Optional[bool] = None
    enable_bias: Optional[bool] = None


class OffloadConfigResponse(BaseModel):
    id: int
    model_id: int
    name: str
    offload_layers: str
    quantize: bool
    quantize_dtype: str
    enable_scale: bool
    enable_bias: bool


@offload_config_router.post("/create", response_model=OffloadConfigResponse)
async def create_offload_config(
    config: OffloadConfigCreate, db: Session = Depends(get_db)
):
    logger.info(f"Creating offload config for model ID: {config.model_id}")
    logger.debug(f"Config details - name: {config.name}, quantize: {config.quantize}")

    # Check if model exists
    model = db.query(TorchModel).filter(TorchModel.id == config.model_id).first()
    if not model:
        logger.warning(f"Model with ID {config.model_id} not found")
        raise HTTPException(status_code=404, detail="Model not found")

    logger.debug(f"Found model: {model.name}")

    # Create offload config
    db_config = OffloadConfig(
        model_id=config.model_id,
        name=config.name,
        offload_layers=config.offload_layers,
        quantize=config.quantize,
        quantize_dtype=config.quantize_dtype,
        enable_scale=config.enable_scale,
        enable_bias=config.enable_bias,
    )

    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    logger.info(f"Successfully created offload config with ID: {db_config.id}")
    return db_config


@offload_config_router.get("/{config_id}", response_model=OffloadConfigResponse)
async def get_offload_config(config_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching offload config with ID: {config_id}")

    config = db.query(OffloadConfig).filter(OffloadConfig.id == config_id).first()
    if not config:
        logger.warning(f"Offload config with ID {config_id} not found")
        raise HTTPException(status_code=404, detail="Offload config not found")

    logger.debug(f"Found offload config for model ID: {config.model_id}")
    return config


@offload_config_router.get(
    "/model/{model_id}", response_model=List[OffloadConfigResponse]
)
async def get_offload_configs_by_model(model_id: int, db: Session = Depends(get_db)):
    logger.info(f"Fetching all offload configs for model ID: {model_id}")

    # Check if model exists
    model = db.query(TorchModel).filter(TorchModel.id == model_id).first()
    if not model:
        logger.warning(f"Model with ID {model_id} not found")
        raise HTTPException(status_code=404, detail="Model not found")

    configs = db.query(OffloadConfig).filter(OffloadConfig.model_id == model_id).all()
    logger.info(f"Found {len(configs)} offload configs for model ID: {model_id}")
    return configs


@offload_config_router.put("/{config_id}", response_model=OffloadConfigResponse)
async def update_offload_config(
    config_id: int, config: OffloadConfigUpdate, db: Session = Depends(get_db)
):
    logger.info(f"Updating offload config with ID: {config_id}")
    logger.debug(f"Update data - name: {config.name}, quantize: {config.quantize}")

    db_config = db.query(OffloadConfig).filter(OffloadConfig.id == config_id).first()
    if not db_config:
        logger.warning(f"Offload config with ID {config_id} not found")
        raise HTTPException(status_code=404, detail="Offload config not found")

    if config.name is not None:
        logger.debug(f"Updating name from '{db_config.name}' to '{config.name}'")
        db_config.name = config.name
    if config.offload_layers is not None:
        logger.debug(f"Updating offload layers")
        db_config.offload_layers = config.offload_layers
    # 更新量化参数
    if config.quantize is not None:
        logger.debug(
            f"Updating quantize from {db_config.quantize} to {config.quantize}"
        )
        db_config.quantize = config.quantize
    if config.quantize_dtype is not None:
        logger.debug(
            f"Updating quantize_dtype from {db_config.quantize_dtype} to {config.quantize_dtype}"
        )
        db_config.quantize_dtype = config.quantize_dtype
    if config.enable_scale is not None:
        logger.debug(
            f"Updating enable_scale from {db_config.enable_scale} to {config.enable_scale}"
        )
        db_config.enable_scale = config.enable_scale
    if config.enable_bias is not None:
        logger.debug(
            f"Updating enable_bias from {db_config.enable_bias} to {config.enable_bias}"
        )
        db_config.enable_bias = config.enable_bias

    db.commit()
    db.refresh(db_config)

    logger.info(f"Successfully updated offload config with ID: {config_id}")
    return db_config


@offload_config_router.delete("/{config_id}")
async def delete_offload_config(config_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deleting offload config with ID: {config_id}")

    db_config = db.query(OffloadConfig).filter(OffloadConfig.id == config_id).first()
    if not db_config:
        logger.warning(f"Offload config with ID {config_id} not found")
        raise HTTPException(status_code=404, detail="Offload config not found")

    db.delete(db_config)
    db.commit()

    logger.info(f"Successfully deleted offload config with ID: {config_id}")
    return {"message": "Offload config deleted successfully"}


@offload_config_router.get("/download/{config_id}")
async def download_offload_config(config_id: int, db: Session = Depends(get_db)):
    logger.info(f"Downloading offload config with ID: {config_id}")
    config = db.get(OffloadConfig, config_id)
    if not config:
        logger.warning(f"Offload config with ID {config_id} not found")
        raise HTTPException(status_code=404, detail="Offload config not found")
    # get related model
    model = db.query(TorchModel).filter(TorchModel.id == config.model_id).first()
    if not model:
        logger.warning(f"Model with ID {config.model_id} not found")
        raise HTTPException(status_code=404, detail="Model not found")
    quantization_config = {
        "quantize": config.quantize,
        "quantize_dtype": config.quantize_dtype,
        "enable_scale": config.enable_scale,
        "enable_bias": config.enable_bias,
    }
    offload_layers = json.loads(config.offload_layers)
    scan_results = model.scan_results
    offload_config = {}
    # 处理offload_layers中的每个键
    for key, layers_list in offload_layers.items():
        memory_info = scan_results[key]["memory"]
        # 计算当前键下所有layers的内存总和
        total_bytes = 0
        valid_layers = []

        for layer in layers_list:
            valid_layers.append(layer)
            if layer in memory_info:
                total_bytes += memory_info[layer]

        offload_config[key] = {
            "layers": [
                f"{key}.{i}.{layer}"
                for layer in valid_layers
                for i in range(int(model.scan_results[key]["module_list_len"][key]))
            ],
            "bytes": total_bytes,
        }

    return {"quantization": quantization_config, "offload": offload_config}
