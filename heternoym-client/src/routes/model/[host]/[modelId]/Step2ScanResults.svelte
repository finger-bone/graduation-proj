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

<div class="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 rounded-2xl shadow-xl ring-1 ring-slate-200 dark:ring-slate-700 overflow-hidden">
    <!-- Header Section -->
    <div class="px-6 py-5 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-blue-500 via-cyan-500 to-teal-500">
        <h1 class="text-2xl font-bold text-white flex items-center">
            <svg class="w-7 h-7 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
            扫描结果分析
        </h1>
        <p class="text-sm text-white/80 mt-1 ml-10">查看模型模块的调用顺序和性能数据</p>
    </div>
    
    <div class="px-6 py-6">
        <!-- Module List Selection -->
        {#if moduleLists.length > 0}
            <div class="mb-6">
                <span class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">选择模块列表</span>
                <div class="flex flex-wrap gap-2">
                    {#each moduleLists as list}
                        <button 
                            class="inline-flex items-center px-4 py-2 text-sm font-semibold rounded-xl transition-all duration-200 shadow-sm hover:shadow-md transform hover:-translate-y-0.5 {list === selectedModuleList ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white ring-2 ring-blue-500 ring-offset-2' : 'bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-600 border border-slate-200 dark:border-slate-600'}"
                            onclick={() => selectedModuleList = list}
                        >
                            <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                            </svg>
                            {list}
                        </button>
                    {/each}
                </div>
            </div>
        {:else}
            <div class="border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl p-8 text-center mb-6 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/30 dark:to-slate-700/50">
                <svg class="w-16 h-16 mx-auto text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <h3 class="mt-4 text-lg font-semibold text-slate-900 dark:text-white">暂无扫描结果</h3>
                <p class="mt-2 text-sm text-slate-500 dark:text-slate-400">未找到任何模块列表，请先完成模型扫描</p>
            </div>
        {/if}

        <!-- Tabs Navigation -->
        {#if selectedModuleList}
            <div class="border-b border-slate-200 dark:border-slate-700 mb-6">
                <nav class="flex space-x-2" aria-label="Tabs">
                    <button
                        class="py-3 px-5 text-sm font-semibold border-b-2 transition-all duration-200 {activeTab === 'order' ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-300'}"
                        onclick={() => activeTab = 'order'}
                    >
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
                            </svg>
                            调用顺序
                        </div>
                    </button>
                    <button
                        class="py-3 px-5 text-sm font-semibold border-b-2 transition-all duration-200 {activeTab === 'compute' ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-300'}"
                        onclick={() => activeTab = 'compute'}
                    >
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                            计算时间
                        </div>
                    </button>
                    <button
                        class="py-3 px-5 text-sm font-semibold border-b-2 transition-all duration-200 {activeTab === 'load' ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-300'}"
                        onclick={() => activeTab = 'load'}
                    >
                        <div class="flex items-center">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                            </svg>
                            加载时间
                        </div>
                    </button>
                </nav>
            </div>

            <!-- Tab Content -->
            <div class="min-h-64">
                <!-- Call Order Tab -->
                {#if activeTab === 'order'}
                    {#if leafModuleOrder.length > 0}
                        <div class="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-5 border border-slate-200 dark:border-slate-700">
                            <h3 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                                <svg class="w-5 h-5 mr-2 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"></path>
                                </svg>
                                叶模块调用顺序
                            </h3>
                            <ol class="list-decimal list-inside bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-lg p-4 max-h-96 overflow-auto border border-slate-200 dark:border-slate-600">
                                {#each leafModuleOrder as module, i}
                                    <li class="py-2 px-3 text-slate-800 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 rounded transition-colors duration-150">
                                        <span class="font-mono text-sm break-all">{module}</span>
                                    </li>
                                {/each}
                            </ol>
                            <div class="mt-3 text-xs text-slate-500 dark:text-slate-400 flex items-center">
                                <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
                                </svg>
                                共 {leafModuleOrder.length} 个叶模块
                            </div>
                        </div>
                    {:else}
                        <div class="text-center py-12 bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700">
                            <svg class="w-16 h-16 mx-auto text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            <h3 class="mt-4 text-lg font-semibold text-slate-900 dark:text-white">无叶模块</h3>
                            <p class="mt-2 text-sm text-slate-500 dark:text-slate-400">当前模块列表中未找到叶模块</p>
                        </div>
                    {/if}
                {/if}

                <!-- Compute Time Chart -->
                {#if activeTab === 'compute'}
                    <div class="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-5 border border-slate-200 dark:border-slate-700">
                        <h3 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                            计算时间分布
                        </h3>
                        <div class="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-lg p-6 border border-slate-200 dark:border-slate-600">
                            <canvas bind:this={chartCanvas}></canvas>
                        </div>
                        <div class="mt-4 grid grid-cols-3 gap-3">
                            <div class="flex items-center p-2 bg-gray-100 dark:bg-slate-700 rounded-lg">
                                <div class="w-4 h-4 rounded mr-2" style="background-color: rgba(156, 156, 156, 0.8)"></div>
                                <span class="text-xs text-slate-700 dark:text-slate-300">0 到 (均值-标准差)</span>
                            </div>
                            <div class="flex items-center p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                                <div class="w-4 h-4 rounded mr-2" style="background-color: rgba(54, 162, 235, 0.8)"></div>
                                <span class="text-xs text-slate-700 dark:text-slate-300">(均值-标准差) 到 均值</span>
                            </div>
                            <div class="flex items-center p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
                                <div class="w-4 h-4 rounded mr-2" style="background-color: rgba(255, 99, 132, 0.8)"></div>
                                <span class="text-xs text-slate-700 dark:text-slate-300">均值 到 (均值+标准差)</span>
                            </div>
                        </div>
                    </div>
                {/if}

                <!-- Load Time Chart -->
                {#if activeTab === 'load'}
                    <div class="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-5 border border-slate-200 dark:border-slate-700">
                        <h3 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                            </svg>
                            加载时间分布
                        </h3>
                        <div class="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-lg p-6 border border-slate-200 dark:border-slate-600">
                            <canvas bind:this={chartCanvas}></canvas>
                        </div>
                        <div class="mt-4 grid grid-cols-3 gap-3">
                            <div class="flex items-center p-2 bg-gray-100 dark:bg-slate-700 rounded-lg">
                                <div class="w-4 h-4 rounded mr-2" style="background-color: rgba(156, 156, 156, 0.8)"></div>
                                <span class="text-xs text-slate-700 dark:text-slate-300">0 到 (均值-标准差)</span>
                            </div>
                            <div class="flex items-center p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                                <div class="w-4 h-4 rounded mr-2" style="background-color: rgba(54, 162, 235, 0.8)"></div>
                                <span class="text-xs text-slate-700 dark:text-slate-300">(均值-标准差) 到 均值</span>
                            </div>
                            <div class="flex items-center p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
                                <div class="w-4 h-4 rounded mr-2" style="background-color: rgba(255, 99, 132, 0.8)"></div>
                                <span class="text-xs text-slate-700 dark:text-slate-300">均值 到 (均值+标准差)</span>
                            </div>
                        </div>
                    </div>
                {/if}
            </div>
        {/if}
        
        <!-- Navigation Buttons -->
        <div class="mt-6 flex justify-between">
            <button 
                class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 transition-all duration-200 shadow-sm hover:shadow-md dark:bg-slate-700 dark:text-slate-200 dark:border-slate-600 dark:hover:bg-slate-600"
                onclick={onPrev}
            >
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
                上一步
            </button>
            <button 
                class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5"
                onclick={onNext}
            >
                下一步
                <svg class="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </button>
        </div>
    </div>
</div>