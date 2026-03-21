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
        // 只有当模型状态不是completed时，才定期刷新状态
        if (model?.scan_status !== 'completed') {
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
                
                // 如果状态变为completed，清除定时器
                if (updatedModel.scan_status === 'completed') {
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

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg ring-1 ring-gray-300 dark:ring-gray-700 overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">模型处理流程</h1>
    </div>
    
    <div class="px-6 py-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
                <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">模型信息</h2>
                <div class="space-y-3">
                    <div>
                        <span class="block text-sm font-medium text-gray-500 dark:text-gray-400">模型名称</span>
                        <p class="mt-1 text-gray-900 dark:text-white">{model?.name}</p>
                    </div>
                    <div>
                        <span class="block text-sm font-medium text-gray-500 dark:text-gray-400">模型路径</span>
                        <p class="mt-1 text-gray-900 dark:text-white wrap-break-word">{model?.path}</p>
                    </div>
                    <div>
                        <span class="block text-sm font-medium text-gray-500 dark:text-gray-400">HuggingFace 名称</span>
                        <p class="mt-1 text-gray-900 dark:text-white">{model?.hf_name}</p>
                    </div>
                </div>
            </div>
            
            <div>
                <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">扫描状态</h2>
                <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4 min-h-[120px] flex items-center justify-center">
                    {#if model?.scan_status === 'pending'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
                            <Icon icon="mdi:clock-outline" class="w-4 h-4 mr-1" />
                            待处理
                        </span>
                    {:else if model?.scan_status === 'scanning'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                            <Icon icon="mdi:loading" class="w-4 h-4 mr-1 animate-spin" />
                            扫描中
                        </span>
                    {:else if model?.scan_status === 'scanning_usage_order'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                            <Icon icon="mdi:loading" class="w-4 h-4 mr-1 animate-spin" />
                            扫描使用顺序
                        </span>
                    {:else if model?.scan_status === 'scanning_compute_time'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                            <Icon icon="mdi:loading" class="w-4 h-4 mr-1 animate-spin" />
                            扫描计算时间
                        </span>
                    {:else if model?.scan_status === 'scanning_onload_time'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                            <Icon icon="mdi:loading" class="w-4 h-4 mr-1 animate-spin" />
                            扫描加载时间
                        </span>
                    {:else if model?.scan_status === 'scanning_memory'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                            <Icon icon="mdi:loading" class="w-4 h-4 mr-1 animate-spin" />
                            扫描内存使用
                        </span>
                    {:else if model?.scan_status === 'completed'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                            <Icon icon="mdi:check-circle" class="w-4 h-4 mr-1" />
                            已完成
                        </span>
                    {:else if model?.scan_status === 'failed'}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                            <Icon icon="mdi:alert-circle" class="w-4 h-4 mr-1" />
                            扫描失败
                        </span>
                    {:else}
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                            {model?.scan_status}
                        </span>
                    {/if}
                </div>
                
                <!-- 显示队列状态 -->
                {#if model?.scan_status === 'pending' || model?.scan_status === 'scanning' || model?.scan_status === 'scanning_usage_order' || model?.scan_status === 'scanning_compute_time' || model?.scan_status === 'scanning_onload_time' || model?.scan_status === 'scanning_memory'}
                    <QueueStatus {model} {host} {password} />
                {/if}
            </div>
        </div>
        
        <!-- 扫描参数设置 -->
        {#if model?.scan_status === 'pending' || model?.scan_status === 'completed' || model?.scan_status === 'failed'}
        <div class="mb-6">
            <button 
                class="flex items-center text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                onclick={() => showScanParams = !showScanParams}
            >
                <Icon icon={showScanParams ? "mdi:chevron-up" : "mdi:chevron-down"} class="w-5 h-5 mr-1" />
                {showScanParams ? '隐藏' : '显示'}扫描参数
            </button>
            
            {#if showScanParams}
                <div class="mt-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                按需加载
                            </span>
                            <div class="flex items-center">
                                <input 
                                    type="checkbox" 
                                    bind:checked={scanParams.testOnOffloadDevice}
                                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:bg-gray-600 dark:border-gray-500"
                                />
                                <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                                    {scanParams.testOnOffloadDevice ? '启用' : '启用'}
                                </span>
                            </div>
                        </div>
                        
                        <div>
                            <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                预热步数
                            </span>
                            <input 
                                type="number" 
                                bind:value={scanParams.warmupSteps}
                                min="1"
                                class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-600 dark:border-gray-500 dark:text-white sm:text-sm"
                            />
                        </div>
                        
                        <div>
                            <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                采样步数
                            </span>
                            <input 
                                type="number" 
                                bind:value={scanParams.samplingSteps}
                                min="1"
                                class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-600 dark:border-gray-500 dark:text-white sm:text-sm"
                            />
                        </div>
                    </div>
                    
                    <div class="mt-3 text-xs text-gray-500 dark:text-gray-400">
                        <p>参数说明：</p>
                        <ul class="list-disc pl-5 mt-1 space-y-1">
                            <li><strong>按需加载</strong>：如果当前设备无法完全加载目标模型，请启用，但是可能会降低扫描速度</li>
                            <li><strong>预热步数</strong>：在正式测量前运行的步数，用于预热设备</li>
                            <li><strong>采样步数</strong>：用于性能测量的步数</li>
                        </ul>
                    </div>
                </div>
            {/if}
        </div>
        {/if}
        
        {#if error}
            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
                {error}
            </div>
        {/if}
        
        <div class="mt-6 flex justify-end space-x-3">
            {#if model?.scan_status === 'completed'}
                <button 
                    class="px-4 py-2 text-sm font-medium text-white bg-orange-600 rounded hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 disabled:opacity-50"
                    onclick={handleRescan}
                    disabled={loading}
                >
                    {#if loading}
                        <Icon icon="mdi:loading" class="w-4 h-4 mr-1 inline-block animate-spin" />
                        重新扫描中...
                    {:else}
                        重新扫描
                    {/if}
                </button>
                <button 
                    class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
                    onclick={onNext}
                >
                    下一步
                </button>
            {:else if model?.scan_status === 'failed'}
                <button 
                    class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50"
                    onclick={handleRescan}
                    disabled={loading}
                >
                    {#if loading}
                        <Icon icon="mdi:loading" class="w-4 h-4 mr-1 inline-block animate-spin" />
                        重新扫描中...
                    {:else}
                        重新扫描
                    {/if}
                </button>
            {:else}
                <button 
                    class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
                    onclick={handleScan}
                    disabled={loading || !(model?.scan_status === 'pending' || model?.scan_status === 'ready')}
                >
                    {#if loading}
                        <Icon icon="mdi:loading" class="w-4 h-4 mr-1 inline-block animate-spin" />
                        处理中...
                    {:else}
                        {#if model?.scan_status === 'pending' || model?.scan_status === 'ready'}
                            开始扫描
                        {:else}
                            <Icon icon="mdi:loading" class="w-4 h-4 mr-1 inline-block animate-spin" />
                            处理中...
                        {/if}
                    {/if}
                </button>
            {/if}
        </div>
    </div>
</div>