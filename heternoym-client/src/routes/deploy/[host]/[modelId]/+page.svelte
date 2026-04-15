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
    let customPort = $state<number | ''>('');
    let portChecking = $state(false);
    let portAvailable = $state<boolean | null>(null);
    let deploying = $state(false);
    let deployError = $state<string | null>(null);
    
    // Deployed ports
    let deployedPorts = $state<number[]>([]);
    let portsLoading = $state(false);
    let portsError = $state<string | null>(null);
    let stopping = $state(false);
    let pollingInterval: number | null = null;
    
    // Port status tracking
    let portStatus = $state<Record<number, boolean>>({});
    let portStatusPollingInterval: number | null = null;
    
    // Selected ports for batch operations
    let selectedPorts = $state<Set<number>>(new Set());
    let deleting = $state(false);
    
    // Load model and configs on mount
    onMount(async () => {
        // Get host and modelId from URL params
        host = window.decodeURIComponent(page.params.host || '');
        modelId = page.params.modelId || '';
        
        // Create API service for the host with password
        apiService = createApiService(host, ($passwordDict)[host]);
        
        // Load model details
        await loadModel();
        
        // Set default model type based on hf_name
        if (model?.hf_name?.startsWith('pipe:')) {
            modelType = 't2i';
        }
        
        // Load configs if model loaded successfully
        if (model) {
            await loadConfigs();
            // Load deployed ports initially
            await loadDeployedPorts();
            // Start polling for deployed ports
            startPolling();
            // Start polling for port status
            startPortStatusPolling();
        }
        
        // Load device count
        await loadDeviceCount();
    });

    // Clean up polling when component is destroyed
    onDestroy(() => {
        stopPolling();
        stopPortStatusPolling();
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
    
    // Check port status
    async function checkPortStatus(port: number) {
        if (!apiService || !modelId) return;
        try {
            const response = await apiService.checkPortStatus(modelId, port);
            portStatus[port] = (response.status === "ready");
        } catch (err: any) {
            portStatus[port] = false;
        }
    }
    
    // Start port status polling
    function startPortStatusPolling() {
        if (portStatusPollingInterval) return;
        // Check immediately
        deployedPorts.forEach(port => checkPortStatus(port));
        // Then poll every 2 seconds
        portStatusPollingInterval = window.setInterval(() => {
            deployedPorts.forEach(port => checkPortStatus(port));
        }, 2000);
    }
    
    // Stop port status polling
    function stopPortStatusPolling() {
        if (portStatusPollingInterval) {
            window.clearInterval(portStatusPollingInterval);
            portStatusPollingInterval = null;
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

    // 检查端口是否可用
    async function checkPortAvailability(port: number): Promise<boolean> {
        if (!apiService || !modelId) return false;
        try {
            const response = await apiService.checkPortStatus(modelId, port);
            return response.status === "not_ready"; // not_ready 表示端口未被占用
        } catch (err: any) {
            // 如果请求失败，说明端口可能未被占用
            return true;
        }
    }

    // 处理端口输入变化
    async function handlePortChange() {
        if (customPort === '' || customPort <= 0) {
            portAvailable = null;
            return;
        }

        portChecking = true;
        portAvailable = null;

        try {
            const available = await checkPortAvailability(customPort);
            portAvailable = available;
            if (!available) {
                alert(`端口 ${customPort} 已被占用，请选择其他端口`);
            }
        } catch (err: any) {
            console.error('Port check error:', err);
            portAvailable = null;
        } finally {
            portChecking = false;
        }
    }

    // 部署函数
    async function deploy() {
        if (!apiService || deploying) return;

        // 如果用户指定了端口，先检查是否可用
        if (customPort !== '' && customPort > 0) {
            portChecking = true;
            try {
                const available = await checkPortAvailability(customPort);
                if (!available) {
                    deployError = `端口 ${customPort} 已被占用，请选择其他端口`;
                    alert(deployError);
                    return;
                }
            } catch (err: any) {
                deployError = '端口检查失败，请重试';
                alert(deployError);
                return;
            } finally {
                portChecking = false;
            }
        }
        
        deploying = true;
        deployError = null;
        
        try {
            const response = await apiService.createDeployment(
                modelId,
                selectedDevice,
                selectedConfigId ?? -1, // 如果没有选择配置，使用-1
                modelType,
                selectedConfigId !== null, // 只有选择了配置才启用offload
                customPort !== '' ? customPort : undefined // 如果用户指定了端口则传递
            );
            
            // 部署成功后的处理（可以添加跳转或通知）
            console.log('Deployment created successfully on port:', response.port);
            alert(`部署成功！服务运行在端口: ${response.port}`);
            // 重新加载已部署的端口（立即刷新，然后轮询会继续）
            await loadDeployedPorts();
            // 清空自定义端口输入
            customPort = '';
            portAvailable = null;
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
    
    // 打开部署服务
    function openDeployment(port: number) {
        console.log("openDeployment called with port:", port);
        console.log("host value:", host);
        let baseUrl = host;
        if(baseUrl.endsWith("/")) {
            baseUrl = baseUrl.slice(0, -1);
        }
        const match = baseUrl.match(/:\d+$/);
        if(match) {
            baseUrl = baseUrl.slice(0, match.index);
        }
        if(!baseUrl.startsWith("http://") && !baseUrl.startsWith("https://")) {
            baseUrl = "http://" + baseUrl;
        }
        const url = `${baseUrl}:${port}`;
        console.log("Opening:", url)
        
        // Try to open in new window using a temporary link element
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    // Toggle port selection
    function togglePortSelection(port: number) {
        if (selectedPorts.has(port)) {
            selectedPorts.delete(port);
        } else {
            selectedPorts.add(port);
        }
        selectedPorts = new Set(selectedPorts); // Trigger reactivity
    }
    
    // Select all ports
    function selectAllPorts() {
        selectedPorts = new Set(deployedPorts);
    }
    
    // Deselect all ports
    function deselectAllPorts() {
        selectedPorts.clear();
        selectedPorts = new Set();
    }
    
    // Batch delete selected ports
    async function batchDeletePorts() {
        if (selectedPorts.size === 0) {
            alert('请先选择要删除的实例');
            return;
        }
        
        if (!confirm(`确定要停止选中的 ${selectedPorts.size} 个实例吗？`)) {
            return;
        }
        
        deleting = true;
        const portsToDelete = Array.from(selectedPorts);
        
        try {
            // Delete each port individually by calling the stop API
            for (const port of portsToDelete) {
                await apiService.stop(modelId, port);
            }
            
            alert(`已成功停止 ${portsToDelete.length} 个实例`);
            selectedPorts.clear();
            selectedPorts = new Set();
            await loadDeployedPorts();
        } catch (err: any) {
            const errorMessage = err.message || '批量停止失败';
            console.error('Batch stop error:', err);
            alert('批量停止失败: ' + errorMessage);
        } finally {
            deleting = false;
        }
    }
</script>

<div class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-purple-50/20 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 p-4 sm:p-6 lg:p-8">
    <div class="max-w-7xl mx-auto">
        <!-- Header -->
        <div class="mb-8">
            <div class="flex flex-col sm:flex-row sm:items-center gap-4">
                <a href="/" class="group inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-200/60 dark:border-gray-700/60 hover:bg-white dark:hover:bg-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-2 transition-all duration-200 w-fit">
                    <Icon icon="mdi:arrow-left" class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
                    返回主页
                </a>
                <div class="flex items-center gap-3">
                    <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg">
                        <Icon icon="mdi:rocket-launch" class="w-7 h-7 text-white" />
                    </div>
                    <div>
                        <h1 class="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent">部署</h1>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">部署和管理模型实例</p>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl rounded-2xl shadow-xl shadow-gray-200/50 dark:shadow-black/30 ring-1 ring-gray-200/60 dark:ring-gray-700/60 overflow-hidden">
            <div class="px-6 py-5 border-b border-gray-200/60 dark:border-gray-700/60 bg-gradient-to-r from-gray-50/50 to-transparent dark:from-gray-700/30">
                {#if error}
                    <div class="p-4 bg-gradient-to-r from-red-50 to-red-100/80 dark:from-red-950/40 dark:to-red-900/30 border border-red-200/60 dark:border-red-800/50 rounded-xl">
                        <div class="flex items-center gap-2 text-red-700 dark:text-red-300">
                            <Icon icon="mdi:alert-circle" class="w-5 h-5" />
                            <span class="text-sm font-medium">{error}</span>
                        </div>
                    </div>
                {/if}
            </div>
            
            <div class="px-6 py-6 space-y-8">
                <!-- Deployed models section -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/40 flex items-center justify-center">
                                <Icon icon="mdi:server" class="w-5 h-5 text-green-600 dark:text-green-400" />
                            </div>
                            <div>
                                <h2 class="text-lg font-semibold text-gray-900 dark:text-white">已部署的实例</h2>
                                <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">共 {deployedPorts.length} 个运行中的实例</p>
                            </div>
                        </div>
                        {#if deployedPorts.length > 0}
                            <div class="flex items-center gap-2">
                                <button 
                                    class="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 bg-gray-100/80 dark:bg-gray-700/80 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                                    onclick={selectAllPorts}
                                    disabled={selectedPorts.size === deployedPorts.length}
                                >
                                    全选
                                </button>
                                <button 
                                    class="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 bg-gray-100/80 dark:bg-gray-700/80 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                                    onclick={deselectAllPorts}
                                    disabled={selectedPorts.size === 0}
                                >
                                    取消全选
                                </button>
                                <button 
                                    class="px-3 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-600 to-red-500 rounded-lg hover:from-red-700 hover:to-red-600 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg"
                                    onclick={batchDeletePorts}
                                    disabled={selectedPorts.size === 0 || deleting}
                                >
                                    {deleting ? '停止中...' : `批量停止 (${selectedPorts.size})`}
                                </button>
                            </div>
                        {/if}
                    </div>
                    
                    {#if portsLoading}
                        <div class="flex flex-col justify-center items-center py-16">
                            <div class="relative">
                                <div class="w-12 h-12 rounded-full border-4 border-green-100 dark:border-green-900/30"></div>
                                <div class="absolute inset-0 w-12 h-12 rounded-full border-4 border-transparent border-t-green-500 border-r-green-500 animate-spin"></div>
                            </div>
                            <span class="mt-3 text-gray-600 dark:text-gray-400 font-medium">加载中...</span>
                        </div>
                    {:else if deployedPorts.length === 0}
                        <div class="py-16 text-center">
                            <div class="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-gray-100 to-gray-200/50 dark:from-gray-700 dark:to-gray-600/50 flex items-center justify-center mb-4">
                                <Icon icon="mdi:server-off" class="w-10 h-10 text-gray-400 dark:text-gray-500" />
                            </div>
                            <h3 class="text-base font-semibold text-gray-900 dark:text-white">暂无部署实例</h3>
                            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
                                部署后会在此处显示运行中的实例
                            </p>
                        </div>
                    {:else}
                        <div class="space-y-3">
                            {#each deployedPorts as port}
                                <div class="group flex items-center justify-between p-4 bg-gradient-to-r from-green-50/80 to-emerald-50/60 dark:from-green-950/25 dark:to-emerald-900/15 border border-green-200/60 dark:border-green-800/50 rounded-xl hover:shadow-md transition-all duration-200">
                                    <div class="flex items-center gap-3">
                                        <input
                                            type="checkbox"
                                            checked={selectedPorts.has(port)}
                                            onchange={() => togglePortSelection(port)}
                                            class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer transition-colors"
                                        />
                                        <div class="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/40 flex items-center justify-center">
                                            <Icon icon="mdi:server" class="w-5 h-5 text-green-600 dark:text-green-400" />
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <span class="font-semibold text-gray-900 dark:text-white">端口：{port}</span>
                                            {#if portStatus[port] === true}
                                                <Icon icon="mdi:check-circle" class="w-5 h-5 text-green-500" />
                                            {:else}
                                                <div class="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
                                            {/if}
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                        <button 
                                            class="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-sm hover:shadow-md {portStatus[port] === true ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-400 cursor-not-allowed'}"
                                            onclick={() => openDeployment(port)}
                                            disabled={portStatus[port] !== true}
                                        >
                                            <Icon icon="mdi:open-in-new" class="w-4 h-4" />
                                            打开
                                        </button>
                                        <button 
                                            class="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-600 to-red-500 rounded-lg hover:from-red-700 hover:to-red-600 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-sm hover:shadow-md"
                                            onclick={() => stopDeployment(port)}
                                            disabled={stopping}
                                        >
                                            <Icon icon="mdi:stop" class="w-4 h-4" />
                                            {stopping ? '停止中...' : '停止'}
                                        </button>
                                    </div>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </div>
                
                <!-- Config selection -->
                <div>
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
                            <Icon icon="mdi:cog-outline" class="w-5 h-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                            <h2 class="text-lg font-semibold text-gray-900 dark:text-white">选择配置（可选）</h2>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">选择预定义的卸载配置以优化性能</p>
                        </div>
                    </div>
                    
                    {#if loading}
                        <div class="flex flex-col justify-center items-center py-16">
                            <div class="relative">
                                <div class="w-12 h-12 rounded-full border-4 border-blue-100 dark:border-blue-900/30"></div>
                                <div class="absolute inset-0 w-12 h-12 rounded-full border-4 border-transparent border-t-blue-500 border-r-blue-500 animate-spin"></div>
                            </div>
                            <span class="mt-3 text-gray-600 dark:text-gray-400 font-medium">加载中...</span>
                        </div>
                    {:else if configs.length === 0}
                        <div class="py-16 text-center">
                            <div class="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-gray-100 to-gray-200/50 dark:from-gray-700 dark:to-gray-600/50 flex items-center justify-center mb-4">
                                <Icon icon="mdi:file-document-outline" class="w-10 h-10 text-gray-400 dark:text-gray-500" />
                            </div>
                            <h3 class="text-base font-semibold text-gray-900 dark:text-white">暂无配置</h3>
                            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
                                可以直接部署而不使用卸载配置
                            </p>
                        </div>
                    {:else}
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {#each configs as config}
                                <button 
                                    class="group relative border rounded-xl p-5 cursor-pointer transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 {selectedConfigId === config.id ? 'ring-2 ring-blue-500 border-blue-500 bg-blue-50/80 dark:bg-blue-900/20' : 'border-gray-200/60 dark:border-gray-700/60 bg-white/60 dark:bg-gray-800/60 hover:border-blue-300 dark:hover:border-blue-600'}"
                                    onclick={() => {
                                        if (selectedConfigId === config.id) {
                                            selectedConfigId = null;
                                        } else {
                                            selectedConfigId = config.id;
                                        }
                                    }}
                                >
                                    {#if selectedConfigId === config.id}
                                        <div class="absolute top-3 right-3">
                                            <Icon icon="mdi:check-circle" class="w-6 h-6 text-blue-500" />
                                        </div>
                                    {/if}
                                    
                                    <div class="flex items-center gap-2 mb-3">
                                        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">
                                            {config.name.charAt(0).toUpperCase()}
                                        </div>
                                        <h3 class="font-semibold text-gray-900 dark:text-white truncate pr-6">
                                            {config.name}
                                        </h3>
                                    </div>
                                    
                                    <div class="space-y-2">
                                        <div class="flex items-center justify-between text-sm">
                                            <span class="text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                                                <Icon icon="mdi:layers" class="w-4 h-4" />
                                                层数
                                            </span>
                                            <span class="font-semibold text-gray-900 dark:text-white">{getLayerCount(config.offload_layers)}</span>
                                        </div>
                                        <div class="flex items-center justify-between text-sm">
                                            <span class="text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                                                <Icon icon="mdi:chip" class="w-4 h-4" />
                                                量化
                                            </span>
                                            {#if config.quantize}
                                                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 text-xs font-semibold">
                                                    {config.quantize_dtype}
                                                </span>
                                            {:else}
                                                <span class="text-gray-400 dark:text-gray-500 text-xs">否</span>
                                            {/if}
                                        </div>
                                        {#if config.quantize && (config.enable_scale || config.enable_bias)}
                                        <div class="flex items-center justify-between text-sm">
                                            <span class="text-gray-500 dark:text-gray-400">Scale/Bias</span>
                                            <span class="text-xs text-gray-700 dark:text-gray-300 font-medium">
                                                {config.enable_scale ? 'S' : ''}{config.enable_scale && config.enable_bias ? '/' : ''}{config.enable_bias ? 'B' : ''}
                                            </span>
                                        </div>
                                        {/if}
                                        <div class="flex items-center justify-between text-sm">
                                            <span class="text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                                                <Icon icon="mdi:clock-outline" class="w-4 h-4" />
                                                访存时间
                                            </span>
                                            <span class="font-semibold text-blue-600 dark:text-blue-400">{calculateMemoryTime(config).toFixed(2)} ns</span>
                                        </div>
                                    </div>
                                </button>
                            {/each}
                        </div>
                    {/if}
                </div>
                
                <!-- Deployment configuration -->
                <div class="p-5 bg-gradient-to-br from-purple-50/60 to-purple-100/40 dark:from-purple-950/25 dark:to-purple-900/15 rounded-xl border border-purple-200/60 dark:border-purple-700/40">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/40 flex items-center justify-center">
                            <Icon icon="mdi:tune" class="w-5 h-5 text-purple-600 dark:text-purple-400" />
                        </div>
                        <div>
                            <h2 class="text-lg font-semibold text-gray-900 dark:text-white">部署配置</h2>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">设置模型类型和目标设备</p>
                        </div>
                    </div>
                    
                    <!-- Model Type Selection -->
                    <div class="mb-4">
                        <label class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                            <span class="flex items-center gap-1.5">
                                <Icon icon="mdi:shape" class="w-4 h-4 text-purple-500" />
                                模型类型
                            </span>
                        </label>
                        <select 
                            class="w-full px-4 py-2.5 border border-gray-300/80 dark:border-gray-600/80 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 bg-white/80 dark:bg-gray-700/80 text-gray-900 dark:text-white transition-all duration-200"
                            bind:value={modelType}
                        >
                            <option value="lm">语言模型 (LM)</option>
                            <option value="t2v">文本到视频 (T2V)</option>
                            <option value="t2i">文本到图像 (T2I)</option>
                        </select>
                    </div>
                    
                    <!-- Device Selection -->
                    <div class="mb-4">
                        <label class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                            <span class="flex items-center gap-1.5">
                                <Icon icon="mdi:memory" class="w-4 h-4 text-purple-500" />
                                设备编号
                            </span>
                            <span class="text-xs text-gray-500 dark:text-gray-400 ml-2">(可用设备数量: {deviceCount})</span>
                        </label>
                        <select 
                            class="w-full px-4 py-2.5 border border-gray-300/80 dark:border-gray-600/80 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 bg-white/80 dark:bg-gray-700/80 text-gray-900 dark:text-white transition-all duration-200"
                            bind:value={selectedDevice}
                        >
                            {#each Array.from({length: deviceCount}, (_, i) => i) as deviceIndex}
                                <option value={deviceIndex}>设备 {deviceIndex}</option>
                            {/each}
                        </select>
                    </div>

                    <!-- Custom Port Input (Optional) -->
                    <div class="mb-4">
                        <label class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                            <span class="flex items-center gap-1.5">
                                <Icon icon="mdi:network" class="w-4 h-4 text-purple-500" />
                                自定义端口（可选）
                            </span>
                            <span class="text-xs text-gray-500 dark:text-gray-400 ml-2">留空则自动分配可用端口</span>
                        </label>
                        <div class="relative">
                            <input 
                                type="number"
                                min="1024"
                                max="65535"
                                placeholder="例如: 8080"
                                class="w-full px-4 py-2.5 border rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 bg-white/80 dark:bg-gray-700/80 text-gray-900 dark:text-white transition-all duration-200 pr-10 {portAvailable === true ? 'border-green-500' : portAvailable === false ? 'border-red-500' : 'border-gray-300/80 dark:border-gray-600/80'}"
                                bind:value={customPort}
                                onblur={handlePortChange}
                            />
                            {#if portChecking}
                                <div class="absolute right-3 top-1/2 -translate-y-1/2">
                                    <div class="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
                                </div>
                            {:else if portAvailable === true}
                                <div class="absolute right-3 top-1/2 -translate-y-1/2">
                                    <Icon icon="mdi:check-circle" class="w-5 h-5 text-green-500" />
                                </div>
                            {:else if portAvailable === false}
                                <div class="absolute right-3 top-1/2 -translate-y-1/2">
                                    <Icon icon="mdi:close-circle" class="w-5 h-5 text-red-500" />
                                </div>
                            {/if}
                        </div>
                        {#if portAvailable === false}
                            <p class="mt-1.5 text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
                                <Icon icon="mdi:alert" class="w-3.5 h-3.5" />
                                该端口已被占用，请选择其他端口
                            </p>
                        {:else if portAvailable === true && customPort !== ''}
                            <p class="mt-1.5 text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                                <Icon icon="mdi:check-circle" class="w-3.5 h-3.5" />
                                端口可用
                            </p>
                        {/if}
                    </div>
                </div>
                
                <!-- Effect preview -->
                {#if selectedConfigId}
                    {@const selectedConfig = configs.find(c => c.id === selectedConfigId)}
                    {#if selectedConfig}
                        <div class="p-5 bg-gradient-to-br from-blue-50/60 to-blue-100/40 dark:from-blue-950/25 dark:to-blue-900/15 rounded-xl border border-blue-200/60 dark:border-blue-700/40">
                            <div class="flex items-center gap-3 mb-4">
                                <div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
                                    <Icon icon="mdi:chart-bar" class="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                </div>
                                <div>
                                    <h2 class="text-lg font-semibold text-gray-900 dark:text-white">预期效果</h2>
                                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">基于当前配置的预估性能指标</p>
                                </div>
                            </div>
                            
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                <div class="p-4 bg-white/80 dark:bg-gray-800/80 rounded-xl shadow-sm border border-gray-200/60 dark:border-gray-700/50">
                                    <div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                                        <Icon icon="mdi:label-outline" class="w-4 h-4" />
                                        配置名称
                                    </div>
                                    <div class="text-lg font-bold text-gray-900 dark:text-white truncate">
                                        {selectedConfig.name}
                                    </div>
                                </div>
                                
                                <div class="p-4 bg-white/80 dark:bg-gray-800/80 rounded-xl shadow-sm border border-gray-200/60 dark:border-gray-700/50">
                                    <div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                                        <Icon icon="mdi:layers" class="w-4 h-4" />
                                        卸载层数
                                    </div>
                                    <div class="text-lg font-bold text-indigo-600 dark:text-indigo-400">
                                        {getLayerCount(selectedConfig.offload_layers)}
                                    </div>
                                </div>
                                
                                <div class="p-4 bg-white/80 dark:bg-gray-800/80 rounded-xl shadow-sm border border-gray-200/60 dark:border-gray-700/50">
                                    <div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                                        <Icon icon="mdi:memory-arrow-down" class="w-4 h-4" />
                                        访存时间
                                    </div>
                                    <div class="text-lg font-bold text-blue-600 dark:text-blue-400">
                                        {calculateMemoryTime(selectedConfig).toFixed(2)} ns
                                    </div>
                                </div>
                                
                                <div class="p-4 bg-white/80 dark:bg-gray-800/80 rounded-xl shadow-sm border border-gray-200/60 dark:border-gray-700/50">
                                    <div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                                        <Icon icon="mdi:cpu-64-bit" class="w-4 h-4" />
                                        计算时间
                                    </div>
                                    <div class="text-lg font-bold text-green-600 dark:text-green-400">
                                        {calculateComputeTime().toFixed(2)} ns
                                    </div>
                                </div>
                                
                                <div class="p-4 bg-white/80 dark:bg-gray-800/80 rounded-xl shadow-sm border border-gray-200/60 dark:border-gray-700/50">
                                    <div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                                        <Icon icon="mdi:chip" class="w-4 h-4" />
                                        量化设置
                                    </div>
                                    <div class="text-lg font-bold text-gray-900 dark:text-white">
                                        {selectedConfig.quantize ? `${selectedConfig.quantize_dtype} ${selectedConfig.enable_scale ? '+S' : ''} ${selectedConfig.enable_bias ? '+B' : ''}` : '未启用'}
                                    </div>
                                    {#if selectedConfig.quantize && (selectedConfig.enable_scale || selectedConfig.enable_bias)}
                                    <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Scale/Bias可减少精度损失
                                    </div>
                                    {/if}
                                </div>

                                <div class="p-4 bg-white/80 dark:bg-gray-800/80 rounded-xl shadow-sm border border-gray-200/60 dark:border-gray-700/50">
                                    <div class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                                        <Icon icon="mdi:timer-outline" class="w-4 h-4" />
                                        总时间/层
                                    </div>
                                    <div class="text-xl font-bold text-gray-900 dark:text-white">
                                        {Math.max(calculateMemoryTime(selectedConfig), calculateComputeTime()).toFixed(2)} ns
                                    </div>
                                    <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">估计值</div>
                                </div>
                            </div>
                            
                            <div class="mt-4 p-4 bg-gradient-to-r from-purple-50/80 to-purple-100/60 dark:from-purple-900/30 dark:to-purple-800/20 rounded-xl border border-purple-200/60 dark:border-purple-700/40">
                                <div class="flex items-center gap-2 text-sm font-medium text-purple-700 dark:text-purple-300 mb-2">
                                    <Icon icon="mdi:memory" class="w-4 h-4" />
                                    预计节省显存
                                </div>
                                <div class="text-2xl font-bold text-purple-600 dark:text-purple-400">
                                    {formatBytes(calculateMemorySavings(selectedConfig))}
                                </div>
                            </div>
                        </div>
                    {/if}
                {/if}
                
                <!-- Deploy error message -->
                {#if deployError}
                    <div class="p-4 bg-gradient-to-r from-red-50 to-red-100/80 dark:from-red-950/40 dark:to-red-900/30 border border-red-200/60 dark:border-red-800/50 rounded-xl">
                        <div class="flex items-center gap-2 text-red-700 dark:text-red-300">
                            <Icon icon="mdi:alert-circle" class="w-5 h-5" />
                            <span class="text-sm font-medium">{deployError}</span>
                        </div>
                    </div>
                {/if}
                
                <div class="flex justify-end pt-4 border-t border-gray-200/60 dark:border-gray-700/60">
                    <button 
                        class="inline-flex items-center gap-2 px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-purple-600 to-purple-500 rounded-xl hover:from-purple-700 hover:to-purple-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
                        onclick={deploy}
                        disabled={deploying || portChecking || (portAvailable === false)}
                    >
                        {#if deploying}
                            <div class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            部署中...
                        {:else if portChecking}
                            <div class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            检查端口...
                        {:else}
                            <Icon icon="mdi:rocket-launch" class="w-5 h-5" />
                            部署
                        {/if}
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>