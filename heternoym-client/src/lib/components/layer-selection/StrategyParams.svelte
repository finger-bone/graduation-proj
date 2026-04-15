<script lang="ts">
    let { 
        strategy = '', 
        params = {}, 
        onParamsChange = () => {} 
    } = $props();
    
    // 遗传算法默认参数
    let geneticParams = $state({
        population_size: 50,
        generations: 100,
        crossover_rate: 0.8,
        mutation_rate: 0.1
    });
    
    // 梯度策略默认参数
    let gradientParams = $state({
        learning_rate: 0.1,
        iterations: 1000,
        threshold: 0.5
    });
    
    // 贪婪策略默认参数
    let greedyParams = $state({
        time_constraint_ratio: 1.0
    });
    
    // 根据当前策略更新 params - 只在策略变化或内部参数变化时触发
    $effect(() => {
        if (strategy === 'genetic') {
            onParamsChange({ genetic: geneticParams });
        } else if (strategy === 'gradient') {
            onParamsChange({ gradient: gradientParams });
        } else if (strategy === 'greedy') {
            onParamsChange({ greedy: greedyParams });
        } else {
            onParamsChange({});
        }
    });
</script>

<div class="mt-4 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
    <h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
        策略参数配置
    </h3>
    
    {#if strategy === 'genetic'}
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    种群大小
                </label>
                <input
                    type="number"
                    value={geneticParams.population_size}
                    oninput={(e: any) => geneticParams.population_size = parseInt(e.target.value) || 50}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    迭代次数
                </label>
                <input
                    type="number"
                    value={geneticParams.generations}
                    oninput={(e: any) => geneticParams.generations = parseInt(e.target.value) || 100}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    交叉率
                </label>
                <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={geneticParams.crossover_rate}
                    oninput={(e: any) => geneticParams.crossover_rate = parseFloat(e.target.value) || 0.8}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    变异率
                </label>
                <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={geneticParams.mutation_rate}
                    oninput={(e: any) => geneticParams.mutation_rate = parseFloat(e.target.value) || 0.1}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
        </div>
    {:else if strategy === 'gradient'}
        <div class="grid grid-cols-3 gap-4">
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    学习率
                </label>
                <input
                    type="number"
                    step="0.01"
                    min="0.001"
                    value={gradientParams.learning_rate}
                    oninput={(e: any) => gradientParams.learning_rate = parseFloat(e.target.value) || 0.1}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    迭代次数
                </label>
                <input
                    type="number"
                    value={gradientParams.iterations}
                    oninput={(e: any) => gradientParams.iterations = parseInt(e.target.value) || 1000}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    阈值
                </label>
                <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={gradientParams.threshold}
                    oninput={(e: any) => gradientParams.threshold = parseFloat(e.target.value) || 0.5}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
            </div>
        </div>
    {:else if strategy === 'greedy'}
        <div class="max-w-xs">
            <div>
                <label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                    时间约束比例
                </label>
                <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="2"
                    value={greedyParams.time_constraint_ratio}
                    oninput={(e: any) => greedyParams.time_constraint_ratio = parseFloat(e.target.value) || 1.0}
                    class="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    1.0 表示使用总计算时间作为约束，&gt;1.0 放宽约束，&lt;1.0 收紧约束
                </p>
            </div>
        </div>
    {:else}
        <p class="text-sm text-gray-500 dark:text-gray-400">
            请先选择一个策略来配置参数
        </p>
    {/if}
</div>
