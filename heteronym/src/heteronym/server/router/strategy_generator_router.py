from fastapi import APIRouter, Body
from heteronym.server.logger import logger
from heteronym.strategy import generate_strategy as generate_strategy_worker
import json

strategy_generator_router = APIRouter()


@strategy_generator_router.get("/names")
async def get_strategy_generator_names():
    logger.info("Getting strategy generator names")
    names = ["greedy", "genetic", "gradient"]
    logger.debug(f"Returning strategy names: {names}")
    return names


@strategy_generator_router.post("/generate")
async def generate_strategy(
    quantization: bool,
    strategy_generator_name: str = Body(...),
    scan_result: str = Body(...),
    params: dict = Body(default_factory=dict),
):
    logger.info(f"Generating strategy with method: {strategy_generator_name}")
    logger.debug(f"Quantization flag: {quantization}, params: {params}")
    
    try:
        scan_result_obj = json.loads(scan_result)
        onload_time = scan_result_obj["onload_time"]
        compute_time = scan_result_obj["compute_time"]
        leaf_modules = scan_result_obj["leaf_module_usage_order"]
        
        logger.debug(f"Parsed scan result - onload_time keys: {len(onload_time)}, "
                     f"compute_time keys: {len(compute_time)}, "
                     f"leaf_modules count: {len(leaf_modules)}")
    except Exception as e:
        logger.error(f"Failed to parse scan result: {str(e)}")
        raise
    
    try:
        strategy = generate_strategy_worker(
            onload_time, 
            compute_time, 
            leaf_modules, 
            strategy_generator_name,
            params
        )
        logger.info(f"Strategy generation completed, selected {len(strategy)} modules")
        return strategy
    except Exception as e:
        logger.error(f"Failed to generate strategy: {str(e)}")
        raise