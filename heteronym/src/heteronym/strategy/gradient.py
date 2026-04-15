import torch
import torch.nn.functional as F
from ..util.logger import logger


def gradient_strategy_generator(
    onload_time: dict[str, int],
    compute_time: dict[str, int],
    leaf_modules: list[str],
    params: dict = None,
) -> list[str]:
    if params is None:
        params = {}
    
    logger.info("Starting gradient strategy generation")
    logger.debug(f"Input parameters - leaf_modules count: {len(leaf_modules)}, params: {params}")
    
    # 将问题转化为连续优化问题
    # 创建可学习参数 x，通过 sigmoid 转换为 0-1 之间的权重 w
    x = torch.randn(len(leaf_modules), requires_grad=True)
    logger.debug(f"Initialized parameters with shape: {x.shape}")
    
    # 设置优化器 - 使用参数中的学习率
    learning_rate = params.get("learning_rate", 0.1)
    optimizer = torch.optim.Adam([x], lr=learning_rate)
    logger.debug(f"Optimizer initialized with learning rate: {learning_rate}")
    
    # 获取 onload_time 和 compute_time 的 tensor 形式
    onload_times = torch.tensor([onload_time.get(module, 0) for module in leaf_modules], dtype=torch.float32)
    total_compute_time = sum(compute_time.values())
    
    logger.debug(f"Total compute time: {total_compute_time}")
    
    # 进行优化 - 使用参数中的迭代次数和阈值
    iterations = params.get("iterations", 1000)
    threshold = params.get("threshold", 0.5)
    logger.debug(f"Running optimization for {iterations} iterations with threshold {threshold}")
    
    for i in range(iterations):
        optimizer.zero_grad()
        
        # 使用 sigmoid 函数将 x 映射到 0-1 之间
        w = torch.sigmoid(x)
        
        # 计算目标函数：最大化选中的 onload_time 总和
        selected_onload_time = torch.sum(w * onload_times)
        objective = -selected_onload_time  # 负号因为我们要最大化
        
        # 计算约束项：选中的 onload_time 总和不能超过总的 compute_time
        constraint_violation = torch.relu(selected_onload_time - total_compute_time)
        
        # 正则化项：鼓励 x 趋向于无穷大以使 w 接近 0 或 1
        regularization = 0.01 * torch.norm(x, p=2)
        
        # 总损失
        loss = objective + constraint_violation + regularization
        
        # 反向传播和优化
        loss.backward()
        optimizer.step()
        
        # 每 100 次迭代记录一次日志
        if i % 100 == 0:
            logger.debug(f"Iteration {i}, loss: {loss.item()}, "
                         f"selected onload time: {selected_onload_time.item()}, "
                         f"constraint violation: {constraint_violation.item()}")
    
    # 获取最终的权重
    final_w = torch.sigmoid(x).detach()
    
    # 选择权重超过阈值的模块
    strategy = []
    for i, module in enumerate(leaf_modules):
        if final_w[i].item() > threshold:
            strategy.append(module)
    
    logger.info(f"Gradient strategy generation completed, selected {len(strategy)} modules")
    return strategy
