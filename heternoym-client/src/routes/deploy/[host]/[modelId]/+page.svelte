<script lang="ts">
    import { page } from '$app/state';
    import { createApiService } from '$lib/api';
    import Icon from '@iconify/svelte';
    import { onMount, onDestroy } from 'svelte';
	import { persistent } from '$lib/persist/persist';
	import { derived } from 'svelte/store';
	import { json } from '@sveltejs/kit';
	import { goto } from '$app/navigation';

    let host = $state('');
    let modelId = $state('');
    let model = $state<{id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null>(null);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let apiService: ReturnType<typeof createApiService> | null = $state(null);
    let passwordDict = persistent<Record<string, string>>('passwordDict', {})
    let password = $derived(() => {
        return $passwordDict[host]
    });
    
    // Offload config states
    let configs = $state<{id: number, model_id: number, name: string, offload_layers: string, quantize: boolean, quantize_dtype: string, enable_scale: boolean, enable_bias: boolean}[]>([]);
    let configsLoading = $state(false);
    let configsError = $state<string | null>(null);
    
    // Selected config
    let selectedConfigId = $state<number | null>(null);
    
    // Model type and device selection
    let modelType = $state<'lm' | 't2v' | 't2i'>('lm');
    let deviceCount = $state<number>(1);
    let selectedDevice = $state<number>(0);
    let deploying = $state(false);
    let deployError = $state<string | null>(null);
    
    // Deployed ports
    let deployedPorts = $state<number[]>([]);
    let portsLoading = $state(false);
    let portsError = $state<string | null>(null);
    let stopping = $state(false);
    let pollingInterval: number | null = null;
    
    // Load model and configs on mount
    onMount(async () => {
        // Get host and modelId from URL params
        host = window.decodeURIComponent(page.params.host || '');
        modelId = page.params.modelId || '';
        
        // Create API service for the host with password
        apiService = createApiService(host, ($passwordDict)[host]);
        
        // Load model details
        await loadModel();
        
        // Load configs if model loaded successfully
        if (model) {
            await loadConfigs();
            // Load deployed ports initially
            await loadDeployedPorts();
            // Start polling for deployed ports
            startPolling();
        }
        
        // Load device count
        await loadDeviceCount();
    });

    // Clean up polling when component is destroyed
    onDestroy(() => {
        stopPolling();
    });

    async function loadModel() {
        if (!apiService) return;
        
        try {
            loading = true;
            error = null;
            model = await apiService.getById(modelId);
        } catch (err: any) {
            error = err.message || 'Failed to load model';
            console.error('Error loading model:', err);
        } finally {
            loading = false;
        }
    }

    // Load all configs for this model
    async function loadConfigs() {
        if (!apiService || !modelId) return;
        
        try {
            configsLoading = true;
            configsError = null;
            configs = await apiService.getOffloadConfigsByModel(parseInt(modelId));
        } catch (err: any) {
            configsError = err.message || 'Failed to load configs';
            console.error('Error loading configs:', err);
        } finally {
            configsLoading = false;
        }
    }
    
    // Load device count
    async function loadDeviceCount() {
        if (!apiService) return;
        
        try {
            const response = await apiService.deviceCount();
            deviceCount = response.count;
            // Ensure selected device is within valid range
            if (selectedDevice >= deviceCount) {
                selectedDevice = 0;
            }
        } catch (err: any) {
            console.error('Error loading device count:', err);
            deviceCount = 1;
            selectedDevice = 0;
        }
    }
    
    // Load deployed ports for this model
    async function loadDeployedPorts() {
        if (!apiService || !modelId) return;
        
        try {
            portsLoading = true;
            portsError = null;
            const response = await apiService.getPorts(modelId);
            deployedPorts = response.ports;
        } catch (err: any) {
            portsError = err.message || 'Failed to load deployed ports';
            console.error('Error loading deployed ports:', err);
            deployedPorts = [];
        } finally {
            portsLoading = false;
        }
    }
    
    // Start polling for deployed ports
    function startPolling() {
        if (pollingInterval) return;
        pollingInterval = window.setInterval(async () => {
            await loadDeployedPorts();
        }, 3000); // Poll every 3 seconds
    }
    
    // Stop polling
    function stopPolling() {
        if (pollingInterval) {
            window.clearInterval(pollingInterval);
            pollingInterval = null;
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

    // 部署函数
    async function deploy() {
        if (!apiService || deploying) return;
        
        deploying = true;
        deployError = null;
        
        try {
            const response = await apiService.createDeployment(
                modelId,
                selectedDevice,
                selectedConfigId ?? -1, // 如果没有选择配置，使用-1
                modelType,
                selectedConfigId !== null // 只有选择了配置才启用offload
            );
            
            // 部署成功后的处理（可以添加跳转或通知）
            console.log('Deployment created successfully on port:', response.port);
            alert(`部署成功！服务运行在端口: ${response.port}`);
            // 重新加载已部署的端口（立即刷新，然后轮询会继续）
            await loadDeployedPorts();
        } catch (err: any) {
            deployError = err.message || '部署失败';
            console.error('Deployment error:', err);
            alert('部署失败: ' + deployError);
        } finally {
            deploying = false;
        }
    }
    
    // 停止部署函数
    async function stopDeployment(port: number) {
        if (!apiService || stopping) return;
        
        // 询问用户确认
        if (!confirm(`确定要停止端口 ${port} 上的部署吗？`)) {
            return;
        }
        
        stopping = true;
        try {
            const response = await apiService.stop(modelId, port);
            console.log('Stop deployment response:', response);
            alert(`已成功停止端口 ${port} 上的部署`);
            // 重新加载已部署的端口（立即刷新，然后轮询会继续）
            await loadDeployedPorts();
        } catch (err: any) {
            const errorMessage = err.message || '停止部署失败';
            console.error('Stop deployment error:', err);
            alert('停止部署失败: ' + errorMessage);
        } finally {
            stopping = false;
        }
    }
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg ring-1 ring-gray-300 dark:ring-gray-700 overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div class="flex items-center space-x-4">
            <a href="/" class="px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex items-center">
                <Icon icon="mdi:arrow-left" class="w-4 h-4 mr-1" />
                返回主页
            </a>
            <h1 class="text-2xl font-bold text-gray-900 dark:text-white">部署</h1>
        </div>
    </div>
    
    <div class="px-6 py-4">
        <!-- Display error if exists -->
        {#if error}
            <div class="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
            </div>
        {/if}
        
        <!-- Deployed models section -->
        <div class="mb-6">
            <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
                已部署的实例
            </h2>
            
            {#if portsLoading}
                <div class="text-center py-4">
                    <div class="inline-block animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-blue-500"></div>
                    <span class="ml-2 text-gray-600 dark:text-gray-400">加载中...</span>
                </div>
            {:else if deployedPorts.length === 0}
                <div class="text-center py-6 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                    <Icon icon="mdi:server-off" class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
                    <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-white">暂无部署实例</h3>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        部署后会在此处显示运行中的实例
                    </p>
                </div>
            {:else}
                <div class="space-y-3">
                    {#each deployedPorts as port}
                        <div class="flex items-center justify-between p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                            <div class="flex items-center">
                                <Icon icon="mdi:server" class="w-5 h-5 text-green-600 dark:text-green-400 mr-2" />
                                <span class="font-medium text-gray-900 dark:text-white">端口: {port}</span>
                            </div>
                            <div class="flex space-x-2">
                                <button 
                                    class="px-3 py-1 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                                    onclick={() => {
                                        // remove host port if exists
                                        let striped_host = host;
                                        if(striped_host.endsWith("/")) {
                                            striped_host = striped_host.slice(0, -1);
                                        }
                                        // if has :number, remove
                                        const match = striped_host.match(/:\d+$/);
                                        if(match) {
                                            striped_host = striped_host.slice(0, match.index);
                                        }
                                        if(!striped_host.startsWith("http://") || !striped_host.startsWith("https://")) {
                                            striped_host = "http://" + striped_host;
                                        }
                                        const url = `${striped_host}:${port}`;
                                        console.log("Opening:", url)
                                        window.open(url)
                                    }}
                                >
                                    打开
                                </button>
                                <button 
                                    class="px-3 py-1 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                                    onclick={() => stopDeployment(port)}
                                    disabled={stopping}
                                >
                                    {stopping ? '停止中...' : '停止'}
                                </button>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
        
        <!-- Config selection -->
        <div class="mb-6">
            <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
                选择配置（可选）
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
                        可以直接部署而不使用卸载配置
                    </p>
                </div>
            {:else}
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {#each configs as config}
                        <button 
                            class="border rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-md {selectedConfigId === config.id ? 'ring-2 ring-blue-500 border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700'}"
                            onclick={() => {
                                // 点击已选中的配置可以取消选择
                                if (selectedConfigId === config.id) {
                                    selectedConfigId = null;
                                } else {
                                    selectedConfigId = config.id;
                                }
                            }}
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
        
        <!-- Deployment configuration -->
        <div class="mb-6 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
                部署配置
            </h2>
            
            <!-- Model Type Selection -->
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    模型类型
                </label>
                <select 
                    class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    bind:value={modelType}
                >
                    <option value="lm">语言模型 (LM)</option>
                    <option value="t2v">文本到视频 (T2V)</option>
                    <option value="t2i">文本到图像 (T2I)</option>
                </select>
            </div>
            
            <!-- Device Selection -->
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    设备编号 (可用设备数量: {deviceCount})
                </label>
                <select 
                    class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    bind:value={selectedDevice}
                >
                    {#each Array.from({length: deviceCount}, (_, i) => i) as deviceIndex}
                        <option value={deviceIndex}>设备 {deviceIndex}</option>
                    {/each}
                </select>
            </div>
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
        
        <!-- Deploy error message -->
        {#if deployError}
            <div class="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                {deployError}
            </div>
        {/if}
        
        <div class="mt-6 flex justify-end">
            <button 
                class="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                onclick={deploy}
                disabled={deploying}
            >
                {deploying ? '部署中...' : '部署'}
            </button>
        </div>
    </div>
</div>