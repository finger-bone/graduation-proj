import torch
import torch.nn.functional as F
from ..util.logger import logger


def gradient_strategy_generator(
    onload_time: dict[str, int],
    compute_time: dict[str, int],
    leaf_modules: list[str],
) -> list[str]:
    logger.info("Starting gradient strategy generation")
    logger.debug(f"Input parameters - leaf_modules count: {len(leaf_modules)}")
    
    # 将问题转化为连续优化问题
    # 创建可学习参数x，通过sigmoid转换为0-1之间的权重w
    x = torch.randn(len(leaf_modules), requires_grad=True)
    logger.debug(f"Initialized parameters with shape: {x.shape}")
    
    # 设置优化器
    optimizer = torch.optim.Adam([x], lr=0.1)
    
    # 获取onload_time和compute_time的tensor形式
    onload_times = torch.tensor([onload_time.get(module, 0) for module in leaf_modules], dtype=torch.float32)
    total_compute_time = sum(compute_time.values())
    
    logger.debug(f"Total compute time: {total_compute_time}")
    
    # 进行优化
    for i in range(1000):  # 运行1000次迭代
        optimizer.zero_grad()
        
        # 使用sigmoid函数将x映射到0-1之间
        w = torch.sigmoid(x)
        
        # 计算目标函数：最大化选中的onload_time总和
        selected_onload_time = torch.sum(w * onload_times)
        objective = -selected_onload_time  # 负号因为我们要最大化
        
        # 计算约束项：选中的onload_time总和不能超过总的compute_time
        constraint_violation = torch.relu(selected_onload_time - total_compute_time)
        
        # 正则化项：鼓励x趋向于无穷大以使w接近0或1
        regularization = 0.01 * torch.norm(x, p=2)
        
        # 总损失
        loss = objective + constraint_violation + regularization
        
        # 反向传播和优化
        loss.backward()
        optimizer.step()
        
        # 每100次迭代记录一次日志
        if i % 100 == 0:
            logger.debug(f"Iteration {i}, loss: {loss.item()}, "
                         f"selected onload time: {selected_onload_time.item()}, "
                         f"constraint violation: {constraint_violation.item()}")
    
    # 获取最终的权重
    final_w = torch.sigmoid(x).detach()
    
    # 选择权重超过0.5的模块
    strategy = []
    for i, module in enumerate(leaf_modules):
        if final_w[i].item() > 0.5:
            strategy.append(module)
    
    logger.info(f"Gradient strategy generation completed, selected {len(strategy)} modules")
    return strategy