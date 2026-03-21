<script lang="ts">
    import Icon from '@iconify/svelte';
    import chartjs from 'chart.js/auto';
    import { onMount } from 'svelte';

    let { model, host, modelId, onPrev, onNext }: { 
        model: {id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null, 
        host: string, 
        modelId: string,
        onPrev: () => void,
        onNext: () => void,
        
    } = $props();

    // 模块列表状态
    let moduleLists = $state(Object.keys(model?.scan_results || {}));
    let selectedModuleList = $state(moduleLists.length > 0 ? moduleLists[0] : '');
    
    // 标签页状态
    let activeTab = $state('order');
    
    // 图表相关
    // svelte-ignore non_reactive_update
        let chartCanvas: HTMLCanvasElement;
    let chart: any;

    // 获取当前选中模块列表的数据
    let currentData = $derived(
        model?.scan_results && selectedModuleList 
            ? model.scan_results[selectedModuleList] 
            : null
    );

    // 获取叶模块调用顺序
    let leafModuleOrder = $derived(
        currentData?.leaf_module_usage_order || []
    );

    // 获取计算时间数据
    let computeTimeData = $derived((() => {
        const computeTime = currentData?.compute_time || {};
        const computeTimeStd = currentData?.compute_time_std || {};
        const order = leafModuleOrder;
        return {
            values: order.map((module: string) => computeTime[module] || 0),
            std: order.map((module: string) => computeTimeStd[module] || 0)
        };
    })());

    // 获取加载时间数据
    let onLoadTimeData = $derived((() => {
        const onLoadTime = currentData?.onload_time || {};
        const onLoadTimeStd = currentData?.onload_time_std || {};
        const order = leafModuleOrder;
        return {
            values: order.map((module: string) => onLoadTime[module] || 0),
            std: order.map((module: string) => onLoadTimeStd[module] || 0)
        };
    })());

    // 创建或更新图表
    function updateChart() {
        if (chart) {
            chart.destroy();
        }

        if (!chartCanvas || !selectedModuleList || activeTab === 'order') return;

        const ctx = chartCanvas.getContext('2d');
        const data = activeTab === 'compute' ? computeTimeData : onLoadTimeData;
        
        // 为每个条形创建三段数据
        const segment1Data = []; // 0 to (value - std)
        const segment2Data = []; // (value - std) to value
        const segment3Data = []; // value to (value + std)
        const segment1Colors = [];
        const segment2Colors = [];
        const segment3Colors = [];
        
        for (let i = 0; i < data.values.length; i++) {
            const value = data.values[i];
            const std = data.std[i];
            
            // 确保不会出现负数
            const lowerBound = Math.max(0, value - std);
            const upperBound = value + std;
            
            segment1Data.push(lowerBound);
            segment2Data.push(value - lowerBound);
            segment3Data.push(upperBound - value);
            
            // 为三段分配不同颜色
            segment1Colors.push('rgba(156, 156, 156, 0.8)'); // 灰色
            segment2Colors.push('rgba(54, 162, 235, 0.8)');  // 蓝色
            segment3Colors.push('rgba(255, 99, 132, 0.8)');  // 红色
        }
        
        chart = new chartjs(ctx as any, {
            type: 'bar',
            data: {
                labels: leafModuleOrder,
                datasets: [
                    {
                        label: '0 到 (平均值-标准差)',
                        data: segment1Data,
                        backgroundColor: segment1Colors,
                        borderColor: 'rgba(0, 0, 0, 0.1)',
                        borderWidth: 1,
                        borderSkipped: false,
                    },
                    {
                        label: '(平均值-标准差) 到 平均值',
                        data: segment2Data,
                        backgroundColor: segment2Colors,
                        borderColor: 'rgba(0, 0, 0, 0.1)',
                        borderWidth: 1,
                        borderSkipped: false,
                    },
                    {
                        label: '平均值 到 (平均值+标准差)',
                        data: segment3Data,
                        backgroundColor: segment3Colors,
                        borderColor: 'rgba(0, 0, 0, 0.1)',
                        borderWidth: 1,
                        borderSkipped: false,
                    }
                ]
            },
            options: {
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: activeTab === 'compute' ? '计算时间 (ms)' : '加载时间 (ms)'
                        },
                        stacked: true
                    },
                    y: {
                        stacked: true
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const datasetIndex = context.datasetIndex;
                                const dataIndex = context.dataIndex;
                                const value = data.values[dataIndex];
                                const std = data.std[dataIndex];
                                
                                if (datasetIndex === 0) {
                                    return `0 到 ${Math.max(0, value - std).toFixed(2)}ms`;
                                } else if (datasetIndex === 1) {
                                    return `${Math.max(0, value - std).toFixed(2)} 到 ${value.toFixed(2)}ms`;
                                } else {
                                    return `${value.toFixed(2)} 到 ${(value + std).toFixed(2)}ms`;
                                }
                            },
                            afterLabel: function(context) {
                                const dataIndex = context.dataIndex;
                                const value = data.values[dataIndex];
                                const std = data.std[dataIndex];
                                if (value > 0) {
                                    const cov = (std / value * 100).toFixed(2);
                                    return `平均值: ${value.toFixed(2)}ms, 标准差: ${std.toFixed(2)}ms, 变异系数: ${cov}%`;
                                }
                                return '';
                            }
                        }
                    }
                }
            }
        });
    }

    $effect(() => {
        if (selectedModuleList && activeTab !== 'order') {
            // 延迟执行确保DOM已更新
            setTimeout(updateChart, 0);
        } else if (chart) {
            chart.destroy();
            chart = null;
        }
        
        return () => {
            if (chart) {
                chart.destroy();
                chart = null;
            }
        };
    });
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg ring-1 ring-gray-300 dark:ring-gray-700 overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">扫描结果</h1>
    </div>
    
    <div class="px-6 py-4">
        <!-- 模块列表选择 -->
        {#if moduleLists.length > 0}
            <div class="mb-6">
                <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">选择模块列表</span>
                <div class="flex flex-wrap gap-2">
                    {#each moduleLists as list}
                        <button 
                            class="px-3 py-1 text-sm rounded focus:outline-none focus:ring-2 focus:ring-blue-500 {list === selectedModuleList ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'}"
                            onclick={() => selectedModuleList = list}
                        >
                            {list}
                        </button>
                    {/each}
                </div>
            </div>
        {:else}
            <div class="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center mb-6">
                <Icon icon="mdi:file-search" class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
                <h3 class="mt-4 text-lg font-medium text-gray-900 dark:text-white">暂无扫描结果</h3>
                <p class="mt-2 text-gray-500 dark:text-gray-400">未找到任何模块列表</p>
            </div>
        {/if}

        <!-- 标签页 -->
        {#if selectedModuleList}
            <div class="border-b border-gray-200 dark:border-gray-700 mb-6">
                <nav class="flex space-x-8">
                    <button
                        class="py-2 px-1 text-sm font-medium border-b-2 {activeTab === 'order' ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'}"
                        onclick={() => activeTab = 'order'}
                    >
                        调用顺序
                    </button>
                    <button
                        class="py-2 px-1 text-sm font-medium border-b-2 {activeTab === 'compute' ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'}"
                        onclick={() => activeTab = 'compute'}
                    >
                        计算时间
                    </button>
                    <button
                        class="py-2 px-1 text-sm font-medium border-b-2 {activeTab === 'load' ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'}"
                        onclick={() => activeTab = 'load'}
                    >
                        加载时间
                    </button>
                </nav>
            </div>

            <!-- 标签页内容 -->
            <div class="min-h-64">
                <!-- 调用顺序 -->
                {#if activeTab === 'order'}
                    {#if leafModuleOrder.length > 0}
                        <div>
                            <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-3">叶模块调用顺序</h3>
                            <ol class="list-decimal list-inside bg-gray-50 dark:bg-gray-700 rounded p-4 max-h-60 overflow-auto">
                                {#each leafModuleOrder as module, i}
                                    <li class="py-1 text-gray-800 dark:text-gray-200">
                                        <span class="font-mono">{module}</span>
                                    </li>
                                {/each}
                            </ol>
                        </div>
                    {:else}
                        <div class="text-center py-8">
                            <Icon icon="mdi:information-outline" class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
                            <h3 class="mt-4 text-lg font-medium text-gray-900 dark:text-white">无叶模块</h3>
                            <p class="mt-2 text-gray-500 dark:text-gray-400">当前模块列表中未找到叶模块</p>
                        </div>
                    {/if}
                {/if}

                <!-- 计算时间图表 -->
                {#if activeTab === 'compute'}
                    <div>
                        <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-3">计算时间</h3>
                        <div class="bg-gray-50 dark:bg-gray-700 rounded p-4">
                            <canvas bind:this={chartCanvas}></canvas>
                        </div>
                    </div>
                {/if}

                <!-- 加载时间图表 -->
                {#if activeTab === 'load'}
                    <div>
                        <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-3">加载时间</h3>
                        <div class="bg-gray-50 dark:bg-gray-700 rounded p-4">
                            <canvas bind:this={chartCanvas}></canvas>
                        </div>
                    </div>
                {/if}
            </div>
        {/if}
        
        <div class="mt-6 flex justify-between">
            <button 
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                onclick={onPrev}
            >
                上一步
            </button>
            <button 
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                onclick={onNext}
            >
                下一步
            </button>
        </div>
    </div>
</div>