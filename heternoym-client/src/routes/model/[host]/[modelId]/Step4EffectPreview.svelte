
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

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg ring-1 ring-gray-300 dark:ring-gray-700 overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">效果预览</h1>
    </div>
    
    <div class="px-6 py-4">
        <!-- Display error if exists -->
        {#if error}
            <div class="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
            </div>
        {/if}
        
        <!-- Config selection -->
        <div class="mb-6">
            <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
                选择配置
            </h2>
            
            {#if loading}
                <div class="text-center py-4">
                    <div class="inline-block animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-blue-500"></div>
                    <span class="ml-2 text-gray-600 dark:text-gray-400">加载中...</span>
                </div>
            {:else if configs.length === 0}
                <div class="text-center py-6 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                    <Icon icon="mdi:file-document-outline" class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
                    <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-white">暂无配置</h3>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        请先创建卸载配置
                    </p>
                </div>
            {:else}
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {#each configs as config}
                        <button 
                            class="border rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-md {selectedConfigId === config.id ? 'ring-2 ring-blue-500 border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700'}"
                            onclick={() => selectedConfigId = config.id}
                        >
                            <div class="flex items-center justify-between">
                                <h3 class="font-medium text-gray-900 dark:text-white">
                                    {config.name}
                                </h3>
                                {#if selectedConfigId === config.id}
                                    <Icon icon="mdi:check-circle" class="w-5 h-5 text-blue-500" />
                                {/if}
                            </div>
                            
                            <div class="mt-2 space-y-1">
                                <div class="text-sm text-gray-500 dark:text-gray-400">
                                    层数: {getLayerCount(config.offload_layers)}
                                </div>
                                <div class="text-sm text-gray-500 dark:text-gray-400">
                                    量化: {config.quantize ? `是 (${config.quantize_dtype})` : '否'}
                                </div>
                                {#if config.quantize && (config.enable_scale || config.enable_bias)}
                                <div class="text-sm text-gray-500 dark:text-gray-400">
                                    Scale/Bias: {config.enable_scale ? 'S' : ''}{config.enable_scale && config.enable_bias ? '/' : ''}{config.enable_bias ? 'B' : ''}
                                    <span class="text-gray-400 dark:text-gray-500">(减少精度损失)</span>
                                </div>
                                {/if}
                                <div class="text-sm text-gray-500 dark:text-gray-400">
                                    预期访存时间: {calculateMemoryTime(config).toFixed(2)} ns
                                </div>
                            </div>
                        </button>
                    {/each}
                </div>
            {/if}
        </div>
        
        <!-- Effect preview -->
        {#if selectedConfigId}
            {@const selectedConfig = configs.find(c => c.id === selectedConfigId)}
            {#if selectedConfig}
                <div class="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                    <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
                        预期效果
                    </h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="p-3 bg-white dark:bg-gray-700 rounded shadow">
                            <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                                配置名称
                            </div>
                            <div class="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                {selectedConfig.name}
                            </div>
                        </div>
                        
                        <div class="p-3 bg-white dark:bg-gray-700 rounded shadow">
                            <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                                卸载层数
                            </div>
                            <div class="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                {getLayerCount(selectedConfig.offload_layers)}
                            </div>
                        </div>
                        
                        <div class="p-3 bg-white dark:bg-gray-700 rounded shadow">
                            <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                                访存时间
                            </div>
                            <div class="mt-1 text-lg font-semibold text-blue-600 dark:text-blue-400">
                                {calculateMemoryTime(selectedConfig).toFixed(2)} ns
                            </div>
                        </div>
                        
                        <div class="p-3 bg-white dark:bg-gray-700 rounded shadow">
                            <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                                计算时间
                            </div>
                            <div class="mt-1 text-lg font-semibold text-green-600 dark:text-green-400">
                                {calculateComputeTime().toFixed(2)} ns
                            </div>
                        </div>
                        
                        <div class="p-3 bg-white dark:bg-gray-700 rounded shadow">
                            <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                                量化设置
                            </div>
                            <div class="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                {selectedConfig.quantize ? `${selectedConfig.quantize_dtype} ${selectedConfig.enable_scale ? '+Scale' : ''} ${selectedConfig.enable_bias ? '+Bias' : ''}` : '未启用'}
                            </div>
                            {#if selectedConfig.quantize && (selectedConfig.enable_scale || selectedConfig.enable_bias)}
                            <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                Scale/Bias可减少量化带来的精度损失，但会增加少量时间开销
                            </div>
                            {/if}
                        </div>
                    </div>
                    
                    <div class="mt-4 p-3 bg-white dark:bg-gray-700 rounded shadow">
                        <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                            总时间/层 （估计）
                        </div>
                        <div class="mt-1 text-xl font-bold text-gray-900 dark:text-white">
                            {Math.max(calculateMemoryTime(selectedConfig), calculateComputeTime()).toFixed(2)} ns
                        </div>
                    </div>
                    
                    <div class="mt-4 p-3 bg-white dark:bg-gray-700 rounded shadow">
                        <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
                            预计节省显存
                        </div>
                        <div class="mt-1 text-xl font-bold text-purple-600 dark:text-purple-400">
                            {formatBytes(calculateMemorySavings(selectedConfig))}
                        </div>
                    </div>

                </div>
            {/if}
        {/if}
        
        <div class="mt-6 flex justify-between">
            <button 
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                onclick={onPrev}
            >
                上一步
            </button>
            <div class="flex space-x-2">
                {#if selectedConfigId}
                    <button 
                        class="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
                        onclick={downloadConfig}
                    >
                        下载配置
                    </button>
                {/if}
                <button 
                    class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 {selectedConfigId ? '' : 'opacity-50 cursor-not-allowed'}"
                    onclick={() => onNext()}
                >
                    完成
                </button>
            </div>
        </div>
    </div>
</div>