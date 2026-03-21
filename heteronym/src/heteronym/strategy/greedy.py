from ..util.logger import logger


def greedy_strategy_generator(
    onload_time: dict[str, int],
    compute_time: dict[str, int],
    leaf_modules: list[str],
) -> list[str]:
    logger.info("Starting greedy strategy generation")
    logger.debug(f"Input parameters - leaf_modules count: {len(leaf_modules)}")
    
    # 计算每个模块的比率
    ratios = {}
    for module in leaf_modules:
        if onload_time.get(module, 0) > 0:
            ratios[module] = compute_time.get(module, 0) / onload_time.get(module, 0)
        else:
            # 如果onload_time为0，则给一个很大的比率值，使其优先被选择
            ratios[module] = float("inf")
    
    # 按比率降序排序
    sorted_modules = sorted(ratios.keys(), key=lambda x: ratios[x], reverse=True)
    
    # 计算总的计算时间
    total_compute_time = sum(compute_time.values())
    logger.debug(f"Total compute time: {total_compute_time}")
    
    # 贪婪选择模块，直到达到计算时间上限
    strategy = []
    total_onload_time = 0
    
    for module in sorted_modules:
        module_onload_time = onload_time.get(module, 0)
        if total_onload_time + module_onload_time <= total_compute_time:
            strategy.append(module)
            total_onload_time += module_onload_time
            logger.debug(f"Added module {module} to strategy, total onload time: {total_onload_time}")
        # 如果添加这个模块会超出限制，则跳过它
    
    logger.info(f"Greedy strategy generation completed, selected {len(strategy)} modules")
    return strategy