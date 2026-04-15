<script lang="ts">
    import { createApiService } from '$lib/api';
    import Icon from '@iconify/svelte';
    import QueueStatus from './QueueStatus.svelte';
    import { onMount } from 'svelte';

    let { model, host, modelId, onNext, password }: { 
        model: {id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null, 
        host: string, 
        modelId: string,
        onNext: () => void,
        password: string
    } = $props();

    let loading = $state(false);
    let error = $state<string | null>(null);
    let apiService: ReturnType<typeof createApiService> | null = $state(null);
    let refreshInterval: number | null = $state(null);
    let showScanParams = $state(true);
    let scanParams = $state({
        testOnOffloadDevice: true,
        warmupSteps: 10,
        samplingSteps: 1000
    });

    $effect(() => {
        if (host) {
            apiService = createApiService(host, password);
        }
    });

    onMount(() => {
        // 只有当模型状态不是completed且不是ready时，才定期刷新状态
        if (model?.scan_status !== 'completed' && model?.scan_status !== 'ready') {
            refreshInterval = window.setInterval(refreshModelStatus, 1000);
        }
        
        return () => {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
        };
    });

    async function refreshModelStatus() {
        if (!apiService || !model) return;
        
        try {
            const updatedModel = await apiService.getById(modelId);
            // 更新父组件传入的model对象的状态
            if (model && updatedModel.scan_status !== model.scan_status) {
                model.scan_status = updatedModel.scan_status;
                
                // 如果状态变为completed或ready，清除定时器
                if (updatedModel.scan_status === 'completed' || updatedModel.scan_status === 'ready') {
                    if (refreshInterval) {
                        clearInterval(refreshInterval);
                        refreshInterval = null;
                    }
                }
            }
        } catch (err: any) {
            console.error('Error refreshing model status:', err);
        }
    }

    async function handleScan() {
        if (!apiService) return;
        
        try {
            loading = true;
            error = null;
            const resp = await apiService.requestScan(
                modelId, 
                scanParams.testOnOffloadDevice, 
                scanParams.warmupSteps, 
                scanParams.samplingSteps
            );
            if ((resp as any).failed) {
                // update error message
                alert(resp.message);
            }
            
            // 开始定期刷新状态
            if (!refreshInterval) {
                refreshInterval = window.setInterval(refreshModelStatus, 1000);
            }
            
            // 注意：点击开始扫描后不进入下一步，等待扫描完成
        } catch (err: any) {
            error = err.message || 'Failed to scan model';
            console.error('Error scanning model:', err);
        } finally {
            loading = false;
        }
    }
    
    async function handleRescan() {
        if (!apiService) return;
        
        try {
            loading = true;
            error = null;
            const resp = await apiService.requestScan(
                modelId, 
                scanParams.testOnOffloadDevice, 
                scanParams.warmupSteps, 
                scanParams.samplingSteps
            );
            if((resp as any).failed) {
                // update error message
                alert(resp.message);
            }
            
            // 重新开始定期刷新状态
            if (!refreshInterval) {
                refreshInterval = window.setInterval(refreshModelStatus, 1000);
            }
            
            // 更新模型状态为pending
            if (model) {
                model.scan_status = 'pending';
            }
        } catch (err: any) {
            error = err.message || 'Failed to scan model';
            console.error('Error scanning model:', err);
        } finally {
            loading = false;
        }
    }
</script>

<div class="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 rounded-2xl shadow-xl ring-1 ring-slate-200 dark:ring-slate-700 overflow-hidden">
    <!-- Header Section -->
    <div class="px-6 py-5 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500">
        <h1 class="text-2xl font-bold text-white flex items-center">
            <svg class="w-7 h-7 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
            </svg>
            模型处理流程
        </h1>
        <p class="text-sm text-white/80 mt-1 ml-10">扫描和分析模型结构与性能特征</p>
    </div>
    
    <div class="px-6 py-6">
        <!-- Model Info and Status Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <!-- Model Information Card -->
            <div class="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-5 border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-shadow duration-200">
                <h2 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                    <svg class="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    模型信息
                </h2>
                <div class="space-y-4">
                    <div class="p-3 bg-gradient-to-r from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-lg border border-slate-200 dark:border-slate-600">
                        <span class="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">模型名称</span>
                        <p class="text-base font-semibold text-slate-900 dark:text-white break-all">{model?.name}</p>
                    </div>
                    <div class="p-3 bg-gradient-to-r from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-lg border border-slate-200 dark:border-slate-600">
                        <span class="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">模型路径</span>
                        <p class="text-sm font-mono text-slate-700 dark:text-slate-300 break-all">{model?.path}</p>
                    </div>
                    <div class="p-3 bg-gradient-to-r from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-lg border border-slate-200 dark:border-slate-600">
                        <span class="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">HuggingFace 名称</span>
                        <p class="text-sm font-mono text-slate-700 dark:text-slate-300 break-all">{model?.hf_name}</p>
                    </div>
                </div>
            </div>
            
            <!-- Scan Status Card -->
            <div class="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-5 border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-shadow duration-200">
                <h2 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                    <svg class="w-5 h-5 mr-2 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    扫描状态
                </h2>
                <div class="min-h-[120px] flex items-center justify-center p-6 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/30 dark:to-slate-700/50 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600">
                    {#if model?.scan_status === 'pending'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-yellow-100 to-yellow-200 text-yellow-800 dark:from-yellow-900/50 dark:to-yellow-800/50 dark:text-yellow-200 shadow-md">
                            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 8 8">
                                <circle cx="4" cy="4" r="3"></circle>
                            </svg>
                            待处理
                        </span>
                    {:else if model?.scan_status === 'scanning'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/50 dark:to-blue-800/50 dark:text-blue-200 shadow-md">
                            <svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            扫描中
                        </span>
                    {:else if model?.scan_status === 'scanning_usage_order'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/50 dark:to-blue-800/50 dark:text-blue-200 shadow-md">
                            <svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            扫描使用顺序
                        </span>
                    {:else if model?.scan_status === 'scanning_compute_time'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/50 dark:to-blue-800/50 dark:text-blue-200 shadow-md">
                            <svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            扫描计算时间
                        </span>
                    {:else if model?.scan_status === 'scanning_onload_time'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/50 dark:to-blue-800/50 dark:text-blue-200 shadow-md">
                            <svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            扫描加载时间
                        </span>
                    {:else if model?.scan_status === 'scanning_memory'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/50 dark:to-blue-800/50 dark:text-blue-200 shadow-md">
                            <svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            扫描内存使用
                        </span>
                    {:else if model?.scan_status === 'ready'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-cyan-100 to-cyan-200 text-cyan-800 dark:from-cyan-900/50 dark:to-cyan-800/50 dark:text-cyan-200 shadow-md">
                            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                            </svg>
                            已就绪，可以扫描
                        </span>
                    {:else if model?.scan_status === 'completed'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-green-100 to-green-200 text-green-800 dark:from-green-900/50 dark:to-green-800/50 dark:text-green-200 shadow-md">
                            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                            </svg>
                            已完成
                        </span>
                    {:else if model?.scan_status === 'failed'}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-red-100 to-red-200 text-red-800 dark:from-red-900/50 dark:to-red-800/50 dark:text-red-200 shadow-md">
                            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                            </svg>
                            扫描失败
                        </span>
                    {:else}
                        <span class="inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-slate-100 to-slate-200 text-slate-800 dark:from-slate-700 dark:to-slate-600 dark:text-slate-200 shadow-md">
                            {model?.scan_status}
                        </span>
                    {/if}
                </div>
                
                <!-- Queue Status -->
                {#if model?.scan_status === 'pending' || model?.scan_status === 'scanning' || model?.scan_status === 'scanning_usage_order' || model?.scan_status === 'scanning_compute_time' || model?.scan_status === 'scanning_onload_time' || model?.scan_status === 'scanning_memory' || model?.scan_status === 'ready'}
                    <div class="mt-4">
                        <QueueStatus {model} {host} {password} />
                    </div>
                {/if}
            </div>
        </div>
        
        <!-- Scan Parameters Section -->
        {#if model?.scan_status === 'pending' || model?.scan_status === 'ready' || model?.scan_status === 'completed' || model?.scan_status === 'failed'}
        <div class="mb-6">
            <button 
                class="flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors duration-200"
                onclick={() => showScanParams = !showScanParams}
            >
                <svg class="w-5 h-5 mr-1 transition-transform duration-200 {showScanParams ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                </svg>
                {showScanParams ? '隐藏扫描参数' : '显示扫描参数'}
            </button>
            
            {#if showScanParams}
                <div class="mt-4 p-5 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/50 dark:to-slate-700/30 rounded-xl border border-slate-200 dark:border-slate-600 shadow-inner">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div class="p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-600">
                            <span class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                                按需加载
                            </span>
                            <div class="flex items-center">
                                <input 
                                    type="checkbox" 
                                    bind:checked={scanParams.testOnOffloadDevice}
                                    class="w-4 h-4 text-indigo-600 border-slate-300 dark:border-slate-500 rounded focus:ring-indigo-500 cursor-pointer"
                                />
                                <span class="ml-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                                    启用
                                </span>
                            </div>
                        </div>
                        
                        <div class="p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-600">
                            <span class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                                预热步数
                            </span>
                            <input 
                                type="number" 
                                bind:value={scanParams.warmupSteps}
                                min="1"
                                class="block w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-500 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 dark:bg-slate-700 dark:text-white text-sm transition-all duration-200"
                            />
                        </div>
                        
                        <div class="p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-600">
                            <span class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                                采样步数
                            </span>
                            <input 
                                type="number" 
                                bind:value={scanParams.samplingSteps}
                                min="1"
                                class="block w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-500 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 dark:bg-slate-700 dark:text-white text-sm transition-all duration-200"
                            />
                        </div>
                    </div>
                    
                    <div class="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                        <p class="text-xs font-semibold text-blue-900 dark:text-blue-200 mb-2 flex items-center">
                            <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
                            </svg>
                            参数说明：
                        </p>
                        <ul class="text-xs text-blue-800 dark:text-blue-300 space-y-1.5 ml-5">
                            <li class="flex items-start">
                                <span class="mr-2">•</span>
                                <span><strong>按需加载</strong>：如果当前设备无法完全加载目标模型，请启用，但可能会降低扫描速度</span>
                            </li>
                            <li class="flex items-start">
                                <span class="mr-2">•</span>
                                <span><strong>预热步数</strong>：在正式测量前运行的步数，用于预热设备以获得更准确的测量结果</span>
                            </li>
                            <li class="flex items-start">
                                <span class="mr-2">•</span>
                                <span><strong>采样步数</strong>：用于性能测量的步数，步数越多结果越准确但耗时越长</span>
                            </li>
                        </ul>
                    </div>
                </div>
            {/if}
        </div>
        {/if}
        
        <!-- Error Message -->
        {#if error}
            <div class="mb-6 p-4 bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-800/30 border-l-4 border-red-500 rounded-xl text-red-700 dark:text-red-300 shadow-sm">
                <div class="flex items-center">
                    <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>
                    <span class="font-medium">{error}</span>
                </div>
            </div>
        {/if}
        
        <!-- Action Buttons -->
        <div class="mt-6 flex justify-end space-x-3">
            {#if model?.scan_status === 'completed'}
                <button 
                    class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-orange-500 to-orange-600 rounded-xl hover:from-orange-600 hover:to-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    onclick={handleRescan}
                    disabled={loading}
                >
                    {#if loading}
                        <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        重新扫描中...
                    {:else}
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                        </svg>
                        重新扫描
                    {/if}
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
            {:else if model?.scan_status === 'failed'}
                <button 
                    class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-red-500 to-red-600 rounded-xl hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    onclick={handleRescan}
                    disabled={loading}
                >
                    {#if loading}
                        <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        重新扫描中...
                    {:else}
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                        </svg>
                        重新扫描
                    {/if}
                </button>
            {:else}
                <button 
                    class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    onclick={handleScan}
                    disabled={loading || !(model?.scan_status === 'pending' || model?.scan_status === 'ready')}
                >
                    {#if loading}
                        <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        处理中...
                    {:else}
                        {#if model?.scan_status === 'pending' || model?.scan_status === 'ready'}
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            开始扫描
                        {:else}
                            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            处理中...
                        {/if}
                    {/if}
                </button>
            {/if}
        </div>
    </div>
</div>