from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from heteronym.server.db.client import get_db, TorchModel
from heteronym.server.logger import logger
from typing import List, Optional

torch_model_router = APIRouter()


class TorchModelCreation(BaseModel):
    name: str
    hf_name: str
    path: str


class TorchModelResponse(BaseModel):
    id: int
    hf_name: Optional[str] = None
    name: Optional[str] = None
    path: Optional[str] = None
    scan_status: Optional[str] = None
    scan_results: Optional[dict] = None


@torch_model_router.post("/create")
async def create_torch_model(
    model_creation: TorchModelCreation, db: Session = Depends(get_db)
) -> dict[str, str]:
    logger.info(f"Creating new torch model: {model_creation.name}")
    logger.debug(
        f"Model creation data: hf_name={model_creation.hf_name}, path={model_creation.path}"
    )

    empty_model = TorchModel()
    empty_model.name = model_creation.name
    empty_model.path = model_creation.path
    empty_model.scan_status = "ready"
    empty_model.scan_results = {}
    empty_model.hf_name = model_creation.hf_name

    db.add(empty_model)
    db.commit()

    logger.info(f"Successfully created torch model with ID: {empty_model.id}")
    return {"id": str(empty_model.id)}


@torch_model_router.get("/all")
async def get_all_torch_models(
    db: Session = Depends(get_db),
) -> List[TorchModelResponse]:
    logger.debug("Fetching all torch models")
    models = db.query(TorchModel).all()
    logger.info(f"Retrieved {len(models)} torch models")

    result = [
        TorchModelResponse(
            id=model.id,
            hf_name=model.hf_name,
            name=model.name,
            path=model.path,
            scan_status=model.scan_status,
            scan_results=model.scan_results,
        )
        for model in models
    ]

    logger.debug("Successfully formatted all torch models for response")
    return result


@torch_model_router.get("/{model_id:int}")
async def get_torch_model(
    model_id: int, db: Session = Depends(get_db)
) -> TorchModelResponse:
    logger.info(f"Fetching torch model with ID: {model_id}")
    model = db.query(TorchModel).filter(TorchModel.id == model_id).first()

    if model:
        logger.debug(f"Found torch model: {model.name}")
    else:
        logger.warning(f"Torch model with ID {model_id} not found")

    return TorchModelResponse(
        id=model.id,
        hf_name=model.hf_name,
        name=model.name,
        path=model.path,
        scan_status=model.scan_status,
        scan_results=model.scan_results,
    )

@torch_model_router.get("/search")
async def search_torch_models(
    hf_name: Optional[str] = Query(None, description="HuggingFace 模型名"),
    name: Optional[str] = Query(None, description="模型名称"),
    scan_status: Optional[str] = Query(None, description="扫描状态"),
    items_per_page: int = Query(20, ge=1),
    page_idx: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    logger.info(f"Searching for torch models with hf_name={hf_name}, name={name}, scan_status={scan_status}")
    logger.info(f"Searching torch models with hf_name={hf_name}, name={name}, scan_status={scan_status}")
    models = db.query(TorchModel).filter(
        (TorchModel.hf_name.like(f"%{hf_name}%") if hf_name else True),
        (TorchModel.name.like(f"%{name}%") if name else True),
        (TorchModel.scan_status.like(f"%{scan_status}%") if scan_status else True),
    ).offset(page_idx * items_per_page).limit(items_per_page).all()
    logger.info(f"Retrieved {len(models)} torch models")
    result = [
        TorchModelResponse(
            id=model.id,
            hf_name=model.hf_name,
            name=model.name,
            path=model.path,
            scan_status=model.scan_status,
            scan_results={},
        )
        for model in models
    ]
    logger.debug("Successfully formatted all torch models for response")
    total_count = db.query(TorchModel).filter(
        (TorchModel.hf_name.like(f"%{hf_name}%") if hf_name else True),
        (TorchModel.name.like(f"%{name}%") if name else True),
        (TorchModel.scan_status.like(f"%{scan_status}%") if scan_status else True),
    ).count()
    return {
        "items": result,
        "total": total_count,
    }

@torch_model_router.delete("/{model_id:int}")
async def delete_torch_model(model_id: int, db: Session = Depends(get_db)) -> None:
    logger.info(f"Deleting torch model with ID: {model_id}")
    deleted_count = db.query(TorchModel).filter(TorchModel.id == model_id).delete()
    db.commit()

    if deleted_count > 0:
        logger.info(f"Successfully deleted torch model with ID: {model_id}")
    else:
        logger.warning(f"No torch model found with ID: {model_id} for deletion")
    