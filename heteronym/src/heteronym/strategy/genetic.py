import random
from typing import List, Tuple
from ..util.logger import logger


def genetic_strategy_generator(
    onload_time: dict[str, int],
    compute_time: dict[str, int],
    leaf_modules: list[str],
) -> list[str]:
    logger.info("Starting genetic strategy generation")
    logger.debug(f"Input parameters - leaf_modules count: {len(leaf_modules)}")
    
    # 计算总计算时间作为约束
    total_compute_time = sum(compute_time.values())
    logger.debug(f"Total compute time: {total_compute_time}")
    
    # 遗传算法参数
    population_size = 50
    generations = 100
    crossover_rate = 0.8
    mutation_rate = 0.1
    
    logger.debug(f"Genetic algorithm parameters - population_size: {population_size}, "
                 f"generations: {generations}, crossover_rate: {crossover_rate}, "
                 f"mutation_rate: {mutation_rate}")
    
    # 初始化种群
    population = _initialize_population(leaf_modules, population_size)
    logger.debug(f"Initialized population with size: {len(population)}")
    
    # 进化过程
    for generation in range(generations):
        # 计算适应度
        fitness_scores = [
            _calculate_fitness(individual, onload_time, compute_time, total_compute_time)
            for individual in population
        ]
        
        # 选择
        selected = _selection(population, fitness_scores)
        
        # 交叉和变异
        next_generation = []
        for i in range(0, len(selected), 2):
            parent1 = selected[i]
            parent2 = selected[(i + 1) % len(selected)]
            
            if random.random() < crossover_rate:
                child1, child2 = _crossover(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()
                
            if random.random() < mutation_rate:
                child1 = _mutate(child1, leaf_modules)
            if random.random() < mutation_rate:
                child2 = _mutate(child2, leaf_modules)
                
            next_generation.extend([child1, child2])
            
        population = next_generation[:population_size]
        
        # 日志记录每10代的最佳适应度
        if generation % 10 == 0:
            best_fitness = max(fitness_scores)
            logger.debug(f"Generation {generation}, best fitness: {best_fitness}")
    
    # 返回最佳个体
    final_fitness = [
        _calculate_fitness(individual, onload_time, compute_time, total_compute_time)
        for individual in population
    ]
    best_index = max(range(len(final_fitness)), key=lambda i: final_fitness[i])
    best_individual = population[best_index]
    
    logger.info(f"Genetic strategy generation completed, best fitness: {final_fitness[best_index]}")
    
    # 将选中的模块名转换为列表
    result = [module for i, module in enumerate(leaf_modules) if best_individual[i]]
    logger.debug(f"Selected {len(result)} modules in final strategy")
    return result

def _initialize_population(leaf_modules: List[str], population_size: int) -> List[List[int]]:
    """初始化种群"""
    population = []
    for _ in range(population_size):
        # 随机生成个体（二进制编码）
        individual = [random.randint(0, 1) for _ in range(len(leaf_modules))]
        population.append(individual)
    return population

def _calculate_fitness(
    individual: List[int], 
    onload_time: dict[str, int], 
    compute_time: dict[str, int], 
    total_compute_time: int
) -> float:
    """计算个体适应度"""
    total_onload = 0
    for i, selected in enumerate(individual):
        if selected and i < len(list(onload_time.keys())):  # 确保索引有效
            total_onload += onload_time.get(list(onload_time.keys())[i], 0)
    
    # 如果超过了总计算时间，给予惩罚
    if total_onload > total_compute_time:
        return -1  # 无效解
    
    # 否则适应度就是选中的模块数量（我们希望最大化这个值）
    return sum(individual)

def _selection(population: List[List[int]], fitness_scores: List[float]) -> List[List[int]]:
    """锦标赛选择"""
    selected = []
    for _ in range(len(population)):
        # 随机选择两个个体
        idx1, idx2 = random.sample(range(len(population)), 2)
        # 选择适应度更高的个体
        if fitness_scores[idx1] > fitness_scores[idx2]:
            selected.append(population[idx1])
        else:
            selected.append(population[idx2])
    return selected

def _crossover(parent1: List[int], parent2: List[int]) -> Tuple[List[int], List[int]]:
    """单点交叉"""
    if len(parent1) <= 1:
        return parent1.copy(), parent2.copy()
    
    point = random.randint(1, len(parent1) - 1)
    child1 = parent1[:point] + parent2[point:]
    child2 = parent2[:point] + parent1[point:]
    return child1, child2

def _mutate(individual: List[int], leaf_modules: List[str]) -> List[int]:
    """变异操作"""
    mutated = individual.copy()
    for i in range(len(mutated)):
        # 每个基因位都有一定概率发生变异
        if random.random() < 1.0 / len(leaf_modules):
            mutated[i] = 1 - mutated[i]  # 翻转该位
    return mutated