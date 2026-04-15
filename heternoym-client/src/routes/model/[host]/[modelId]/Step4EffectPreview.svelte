
<script lang="ts">
    import Icon from '@iconify/svelte';
    import { onMount } from 'svelte';
    import { createApiService } from '$lib/api';

    let { model, host, modelId, onPrev, onNext, selectedConfig: bindingSelectedConfig = $bindable(), password }: { 
        model: {id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null, 
        host: string, 
        modelId: string,
        onPrev: () => void,
        onNext: () => void,
        selectedConfig?: number | null,
        password: string
    } = $props();

    // API service initialization
    let apiService = $state(createApiService(host, password));

    // Offload config states
    let configs = $state<{id: number, model_id: number, name: string, offload_layers: string, quantize: boolean, quantize_dtype: string, enable_scale: boolean, enable_bias: boolean}[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);
    
    // Selected config
    let selectedConfigId = $state<number | null>(bindingSelectedConfig || null);
    
    // Load configs on mount
    onMount(async () => {
        await loadConfigs();
    });

    // Load all configs for this model
    async function loadConfigs() {
        try {
            loading = true;
            error = null;
            configs = await apiService.getOffloadConfigsByModel(parseInt(modelId));
        } catch (err: any) {
            error = err.message || 'Failed to load configs';
            console.error('Error loading configs:', err);
        } finally {
            loading = false;
        }
    }

    // Calculate memory time for a config
    function calculateMemoryTime(config: {offload_layers: string, quantize: boolean, quantize_dtype: string, enable_scale: boolean, enable_bias: boolean}): number {
        if (!model?.scan_results) return 0;
        
        let totalTime = 0;
        // Parse the offload_layers as a dictionary: {module_list_name: [layer_names]}
        const moduleDict = JSON.parse(config.offload_layers);
        
        // Iterate through each module list in the dictionary
        for (const moduleListName in moduleDict) {
            const layers = moduleDict[moduleListName];
            // Find the corresponding module data
            if (model.scan_results[moduleListName]) {
                const moduleData = model.scan_results[moduleListName];
                if (moduleData.onload_time) {
                    // Check each layer in the offload list
                    for (const layerName of layers) {
                        if (moduleData.onload_time[layerName] !== undefined) {
                            totalTime += moduleData.onload_time[layerName];
                        }
                    }
                }
            }
        }
        
        // If quantization is enabled, halve the memory time
        if (config.quantize) {
            totalTime /= 2;
        }
        
        return totalTime;
    }

    // Calculate compute time (always the same for the model)
    function calculateComputeTime(): number {
        if (!model?.scan_results) return 0;
        
        let totalTime = 0;
        for (const moduleName in model.scan_results) {
            const moduleData = model.scan_results[moduleName];
            if (moduleData.compute_time) {
                for (const layerName in moduleData.compute_time) {
                    totalTime += moduleData.compute_time[layerName];
                }
            }
        }
        return totalTime;
    }

    // Calculate estimated memory savings in bytes
    function calculateMemorySavings(config: {offload_layers: string}): number {
        if (!model?.scan_results) return 0;
        
        let totalBytes: number[] = [];
        // Parse the offload_layers as a dictionary: {module_list_name: [layer_names]}
        const moduleDict = JSON.parse(config.offload_layers);
        
        // Iterate through each module list in the dictionary
        for (const moduleListName in moduleDict) {
            totalBytes = [0, ...totalBytes];
            const layers = moduleDict[moduleListName];
            // Find the corresponding module data
            if (model.scan_results[moduleListName]) {
                const moduleData = model.scan_results[moduleListName];
                // Use the direct memory bytes from scan results
                if (moduleData.memory) {
                    // Check each layer in the offload list
                    for (const layerName of layers) {
                        if (moduleData.memory[layerName] !== undefined) {
                            totalBytes[0] += moduleData.memory[layerName];
                        }
                    }
                }
            }
            totalBytes[0] *= model.scan_results[moduleListName]["module_list_len"][moduleListName];
        }

        return totalBytes.reduce((a, b) => a + b, 0);
    }

    // Format bytes to human readable format
    function formatBytes(bytes: number): string {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Get layer count from config
    function getLayerCount(offloadLayers: string): number {
        try {
            if (typeof offloadLayers === 'string' && offloadLayers) {
                // Parse as dictionary: {module_list_name: [layer_names]}
                const moduleDict = JSON.parse(offloadLayers);
                let count = 0;
                // Sum up all layers across all module lists
                for (const moduleListName in moduleDict) {
                    const layers = moduleDict[moduleListName];
                    count += Array.isArray(layers) ? layers.length : 0;
                }
                return count;
            }
            return 0;
        } catch (e) {
            console.error('Error parsing offload_layers:', e);
            return 0;
        }
    }

    // Export selected config ID
    $effect(() => {
        bindingSelectedConfig = selectedConfigId;
    });

    // Download config
    async function downloadConfig() {
        if (selectedConfigId) {
            const config = configs.find(c => c.id === selectedConfigId);
            if (config) {
                const resp = await apiService.downloadOffloadConfig(config.id)
                const blob = new Blob([JSON.stringify(resp)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${config.name}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
        }
    }
</script>

<div class="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 rounded-2xl shadow-xl ring-1 ring-slate-200 dark:ring-slate-700 overflow-hidden">
    <!-- Header Section -->
    <div class="px-6 py-5 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500">
        <h1 class="text-2xl font-bold text-white flex items-center">
            <svg class="w-7 h-7 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
            </svg>
            效果预览与配置选择
        </h1>
        <p class="text-sm text-white/80 mt-1 ml-10">查看不同配置的性能预期并选择合适的配置</p>
    </div>
    
    <div class="px-6 py-6 space-y-6">
        <!-- Display error if exists -->
        {#if error}
            <div class="p-4 bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-800/30 border-l-4 border-red-500 rounded-xl text-red-700 dark:text-red-300 shadow-sm">
                <div class="flex items-center">
                    <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>
                    <span class="font-medium">{error}</span>
                </div>
            </div>
        {/if}
        
        <!-- Config selection section -->
        <div>
            <h2 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                <svg class="w-5 h-5 mr-2 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path>
                </svg>
                选择配置
            </h2>
            
            {#if loading}
                <div class="text-center py-8 bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700">
                    <div class="relative inline-block">
                        <div class="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 dark:border-indigo-900"></div>
                        <div class="animate-spin rounded-full h-12 w-12 border-t-4 border-indigo-600 absolute top-0 left-0"></div>
                    </div>
                    <span class="ml-4 text-lg font-medium text-slate-600 dark:text-slate-300">加载中...</span>
                </div>
            {:else if configs.length === 0}
                <div class="text-center py-12 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700/30 dark:to-slate-700/50">
                    <svg class="w-16 h-16 mx-auto text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <h3 class="mt-4 text-lg font-semibold text-slate-900 dark:text-white">暂无配置</h3>
                    <p class="mt-2 text-sm text-slate-500 dark:text-slate-400">
                        请先在"层选择"步骤创建卸载配置
                    </p>
                </div>
            {:else}
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {#each configs as config}
                        <button 
                            class="border-2 rounded-xl p-5 cursor-pointer transition-all duration-200 hover:shadow-lg transform hover:-translate-y-1 text-left {selectedConfigId === config.id ? 'ring-2 ring-blue-500 border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-blue-300 dark:hover:border-blue-600'}"
                            onclick={() => selectedConfigId = config.id}
                        >
                            <div class="flex items-center justify-between mb-3">
                                <h3 class="font-semibold text-slate-900 dark:text-white text-base">
                                    {config.name}
                                </h3>
                                {#if selectedConfigId === config.id}
                                    <svg class="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                    </svg>
                                {/if}
                            </div>
                            
                            <div class="space-y-2">
                                <div class="flex items-center text-sm">
                                    <svg class="w-4 h-4 mr-2 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
                                    </svg>
                                    <span class="text-slate-600 dark:text-slate-400">层数:</span>
                                    <span class="ml-auto font-semibold text-slate-900 dark:text-white">{getLayerCount(config.offload_layers)}</span>
                                </div>
                                <div class="flex items-center text-sm">
                                    <svg class="w-4 h-4 mr-2 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                                    </svg>
                                    <span class="text-slate-600 dark:text-slate-400">量化:</span>
                                    <span class="ml-auto font-semibold text-slate-900 dark:text-white">{config.quantize ? `是 (${config.quantize_dtype})` : '否'}</span>
                                </div>
                                {#if config.quantize && (config.enable_scale || config.enable_bias)}
                                <div class="flex items-center text-sm">
                                    <svg class="w-4 h-4 mr-2 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span class="text-slate-600 dark:text-slate-400">Scale/Bias:</span>
                                    <span class="ml-auto font-semibold text-slate-900 dark:text-white">
                                        {config.enable_scale ? 'S' : ''}{config.enable_scale && config.enable_bias ? '/' : ''}{config.enable_bias ? 'B' : ''}
                                    </span>
                                </div>
                                <div class="text-xs text-slate-500 dark:text-slate-400 pl-6">
                                    (减少精度损失)
                                </div>
                                {/if}
                                <div class="flex items-center text-sm pt-2 border-t border-slate-200 dark:border-slate-700">
                                    <svg class="w-4 h-4 mr-2 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    <span class="text-slate-600 dark:text-slate-400">访存时间:</span>
                                    <span class="ml-auto font-bold text-blue-600 dark:text-blue-400">{calculateMemoryTime(config).toFixed(2)} ns</span>
                                </div>
                            </div>
                        </button>
                    {/each}
                </div>
            {/if}
        </div>
        
        <!-- Effect preview section -->
        {#if selectedConfigId}
            {@const selectedConfig = configs.find(c => c.id === selectedConfigId)}
            {#if selectedConfig}
                <div class="p-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl border-2 border-blue-200 dark:border-blue-800 shadow-lg">
                    <h2 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                        <svg class="w-5 h-5 mr-2 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                        </svg>
                        预期效果分析
                    </h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div class="p-4 bg-white dark:bg-slate-800 rounded-xl shadow-md border border-slate-200 dark:border-slate-700 hover:shadow-lg transition-shadow duration-200">
                            <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path>
                                </svg>
                                配置名称
                            </div>
                            <div class="text-xl font-bold text-slate-900 dark:text-white break-all">
                                {selectedConfig.name}
                            </div>
                        </div>
                        
                        <div class="p-4 bg-white dark:bg-slate-800 rounded-xl shadow-md border border-slate-200 dark:border-slate-700 hover:shadow-lg transition-shadow duration-200">
                            <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
                                </svg>
                                卸载层数
                            </div>
                            <div class="text-2xl font-bold text-slate-900 dark:text-white">
                                {getLayerCount(selectedConfig.offload_layers)}
                                <span class="text-sm font-normal text-slate-500 dark:text-slate-400 ml-1">层</span>
                            </div>
                        </div>
                        
                        <div class="p-4 bg-white dark:bg-slate-800 rounded-xl shadow-md border border-slate-200 dark:border-slate-700 hover:shadow-lg transition-shadow duration-200">
                            <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                                访存时间
                            </div>
                            <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">
                                {calculateMemoryTime(selectedConfig).toFixed(2)}
                                <span class="text-sm font-normal text-slate-500 dark:text-slate-400 ml-1">ns</span>
                            </div>
                        </div>
                        
                        <div class="p-4 bg-white dark:bg-slate-800 rounded-xl shadow-md border border-slate-200 dark:border-slate-700 hover:shadow-lg transition-shadow duration-200">
                            <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                                </svg>
                                计算时间
                            </div>
                            <div class="text-2xl font-bold text-green-600 dark:text-green-400">
                                {calculateComputeTime().toFixed(2)}
                                <span class="text-sm font-normal text-slate-500 dark:text-slate-400 ml-1">ns</span>
                            </div>
                        </div>
                        
                        <div class="p-4 bg-white dark:bg-slate-800 rounded-xl shadow-md border border-slate-200 dark:border-slate-700 hover:shadow-lg transition-shadow duration-200 md:col-span-2">
                            <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                </svg>
                                量化设置
                            </div>
                            <div class="text-lg font-bold text-slate-900 dark:text-white">
                                {selectedConfig.quantize ? `${selectedConfig.quantize_dtype} ${selectedConfig.enable_scale ? '+Scale' : ''} ${selectedConfig.enable_bias ? '+Bias' : ''}` : '未启用'}
                            </div>
                            {#if selectedConfig.quantize && (selectedConfig.enable_scale || selectedConfig.enable_bias)}
                            <div class="mt-2 text-xs text-slate-500 dark:text-slate-400 flex items-start">
                                <svg class="w-4 h-4 mr-1 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
                                </svg>
                                Scale/Bias可减少量化带来的精度损失，但会增加少量时间开销
                            </div>
                            {/if}
                        </div>
                    </div>
                    
                    <div class="mt-4 p-5 bg-white dark:bg-slate-800 rounded-xl shadow-md border border-slate-200 dark:border-slate-700">
                        <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            总时间/层（估计）
                        </div>
                        <div class="text-3xl font-black text-slate-900 dark:text-white">
                            {Math.max(calculateMemoryTime(selectedConfig), calculateComputeTime()).toFixed(2)}
                            <span class="text-lg font-normal text-slate-500 dark:text-slate-400 ml-1">ns</span>
                        </div>
                    </div>
                    
                    <div class="mt-4 p-5 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-xl shadow-md border-2 border-purple-200 dark:border-purple-800">
                        <div class="flex items-center text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                            </svg>
                            预计节省显存
                        </div>
                        <div class="text-3xl font-black text-purple-600 dark:text-purple-400">
                            {formatBytes(calculateMemorySavings(selectedConfig))}
                        </div>
                    </div>
                </div>
            {/if}
        {/if}
        
        <!-- Navigation Buttons -->
        <div class="mt-6 flex justify-between pt-6 border-t border-slate-200 dark:border-slate-700">
            <button 
                class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 transition-all duration-200 shadow-sm hover:shadow-md dark:bg-slate-700 dark:text-slate-200 dark:border-slate-600 dark:hover:bg-slate-600"
                onclick={onPrev}
            >
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
                上一步
            </button>
            <div class="flex space-x-3">
                {#if selectedConfigId}
                    <button 
                        class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-green-500 to-emerald-600 rounded-xl hover:from-green-600 hover:to-emerald-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5"
                        onclick={downloadConfig}
                    >
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                        </svg>
                        下载配置
                    </button>
                {/if}
                <button 
                    class="inline-flex items-center px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    onclick={() => onNext()}
                    disabled={!selectedConfigId}
                >
                    完成
                    <svg class="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                </button>
            </div>
        </div>
    </div>
</div>