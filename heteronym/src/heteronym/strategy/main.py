from .genetic import genetic_strategy_generator
from .gradient import gradient_strategy_generator
from .greedy import greedy_strategy_generator
from ..util.logger import logger


def generate_strategy(
    onload_time: dict[str, int],
    compute_time: dict[str, int],
    leaf_modules: list[str],
    strategy_generator_name: str,
) -> list[str]:
    logger.info(f"Generating strategy with method: {strategy_generator_name}")
    logger.debug(f"Input parameters - onload_time keys: {len(onload_time)}, "
                 f"compute_time keys: {len(compute_time)}, "
                 f"leaf_modules count: {len(leaf_modules)}")
    
    if strategy_generator_name == "greedy":
        result = greedy_strategy_generator(onload_time, compute_time, leaf_modules)
        logger.info("Greedy strategy generation completed")
        return result
    if strategy_generator_name == "genetic":
        result = genetic_strategy_generator(onload_time, compute_time, leaf_modules)
        logger.info("Genetic strategy generation completed")
        return result
    if strategy_generator_name == "gradient":
        result = gradient_strategy_generator(onload_time, compute_time, leaf_modules)
        logger.info("Gradient strategy generation completed")
        return result
    
    error_msg = f"Unknown strategy generator name: {strategy_generator_name}"
    logger.error(error_msg)
    raise ValueError(error_msg)