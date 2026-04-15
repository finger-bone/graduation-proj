<script lang="ts">
    import { page } from '$app/state';
    import { createApiService } from '$lib/api';
    import Icon from '@iconify/svelte';
    import { onMount } from 'svelte';
    import { persistent } from '$lib/persist/persist';
    import { derived } from 'svelte/store';
    import { goto } from '$app/navigation';

    let host = $state('');
    let modelId = $state('');
    let model = $state<{id: string, name: string, hf_name: string, path: string, scan_status: string} | null>(null);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let apiService: ReturnType<typeof createApiService> | null = $state(null);
    
    // Config states
    let configs = $state<{id: number, model_id: number, name: string, offload_layers: string, quantize: boolean, quantize_dtype: string, enable_scale: boolean, enable_bias: boolean}[]>([]);
    let configsLoading = $state(false);
    let configsError = $state<string | null>(null);
    
    // Form state for creating/updating configs
    let showFormModal = $state(false);
    let editingConfigId = $state<number | null>(null);
    let newConfig = $state({
        name: '',
        quantize: false,
        quantize_dtype: 'float8',
        enable_scale: false,
        enable_bias: false
    });
    
    // Layer selection state - dictionary: {module_list_name: [layer_names]}
    let selectedLayersDict = $state<Record<string, string[]>>({});
    let activeTab = $state<string>('');
    
    // Strategy states
    let strategies = $state<string[]>([]);
    let selectedStrategy = $state<string>('');
    let autoSelectLoading = $state<boolean>(false);
    
    // Strategy params - separate state for each strategy type
    let geneticParams = $state({
        population_size: 50,
        generations: 100,
        crossover_rate: 0.8,
        mutation_rate: 0.1
    });
    
    let gradientParams = $state({
        learning_rate: 0.1,
        iterations: 1000,
        threshold: 0.5
    });
    
    let greedyParams = $state({
        time_constraint_ratio: 1.0
    });
    
    let passwordDict = persistent<Record<string, string>>('passwordDict', {});
    let password = $derived($passwordDict[host]);
    
    // Selected configs for batch operations
    let selectedConfigIds = $state<Set<number>>(new Set());
    let batchDeleting = $state(false);

    onMount(async () => {
        // Get host and modelId from URL params
        host = window.decodeURIComponent(page.params.host || '');
        modelId = page.params.modelId || '';
        
        if (!host || !modelId) {
            error = '缺少必要的参数';
            loading = false;
            return;
        }
        
        await loadModel();
        await loadConfigs();
        await loadStrategies();
    });

    async function loadModel() {
        try {
            loading = true;
            error = null;
            
            apiService = createApiService(host, password);
            const loadedModel = await apiService.getById(modelId);
            model = loadedModel;
        } catch (err: any) {
            error = err.message || 'Failed to load model details';
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

    // Create a new config
    async function createConfig() {
        if (!newConfig.name.trim()) {
            configsError = '配置名称不能为空';
            return;
        }

        try {
            await apiService.createOffloadConfig({
                model_id: parseInt(modelId),
                name: newConfig.name,
                offload_layers: JSON.stringify(selectedLayersDict),
                quantize: newConfig.quantize,
                quantize_dtype: newConfig.quantize_dtype,
                enable_scale: newConfig.enable_scale,
                enable_bias: newConfig.enable_bias,
                enable_fp8: false
            });
            
            // Reset form
            resetForm();
            showFormModal = false;
            await loadConfigs();
        } catch (err: any) {
            configsError = err.message || 'Failed to create config';
            console.error('Error creating config:', err);
        }
    }

    // Update an existing config
    async function updateConfig() {
        if (!editingConfigId || !newConfig.name.trim()) {
            configsError = '配置名称不能为空';
            return;
        }

        try {
            await apiService.updateOffloadConfig(editingConfigId, {
                name: newConfig.name,
                offload_layers: JSON.stringify(selectedLayersDict),
                quantize: newConfig.quantize,
                quantize_dtype: newConfig.quantize_dtype,
                enable_scale: newConfig.enable_scale,
                enable_bias: newConfig.enable_bias,
                enable_fp8: false
            });
            
            // Reset form
            resetForm();
            showFormModal = false;
            await loadConfigs();
        } catch (err: any) {
            configsError = err.message || 'Failed to update config';
            console.error('Error updating config:', err);
        }
    }

    // Delete a config
    async function deleteConfig(configId: number) {
        if (!confirm('确定要删除这个配置吗？')) {
            return;
        }

        try {
            await apiService.deleteOffloadConfig(configId);
            await loadConfigs();
        } catch (err: any) {
            configsError = err.message || 'Failed to delete config';
            console.error('Error deleting config:', err);
        }
    }
    
    // Toggle config selection
    function toggleConfigSelection(configId: number) {
        if (selectedConfigIds.has(configId)) {
            selectedConfigIds.delete(configId);
        } else {
            selectedConfigIds.add(configId);
        }
        selectedConfigIds = new Set(selectedConfigIds); // Trigger reactivity
    }
    
    // Select all configs
    function selectAllConfigs() {
        selectedConfigIds = new Set(configs.map(c => c.id));
    }
    
    // Deselect all configs
    function deselectAllConfigs() {
        selectedConfigIds.clear();
        selectedConfigIds = new Set();
    }
    
    // Batch delete selected configs
    async function batchDeleteConfigs() {
        if (selectedConfigIds.size === 0) {
            configsError = '请先选择要删除的配置';
            return;
        }
        
        if (!confirm(`确定要删除选中的 ${selectedConfigIds.size} 个配置吗？`)) {
            return;
        }
        
        batchDeleting = true;
        const idsToDelete = Array.from(selectedConfigIds);
        
        try {
            // Delete each config individually by calling the delete API
            for (const configId of idsToDelete) {
                await apiService.deleteOffloadConfig(configId);
            }
            
            selectedConfigIds.clear();
            selectedConfigIds = new Set();
            await loadConfigs();
        } catch (err: any) {
            configsError = err.message || '批量删除失败';
            console.error('Batch delete error:', err);
        } finally {
            batchDeleting = false;
        }
    }

    // Handle edit config
    function handleEditConfig(config: any) {
        editingConfigId = config.id;
        newConfig = {
            name: config.name,
            quantize: config.quantize,
            quantize_dtype: config.quantize_dtype,
            enable_scale: config.enable_scale,
            enable_bias: config.enable_bias
        };
        
        // Parse the JSON string back to dictionary
        try {
            if (typeof config.offload_layers === 'string') {
                selectedLayersDict = JSON.parse(config.offload_layers);
            } else {
                selectedLayersDict = {};
            }
        } catch (e) {
            selectedLayersDict = {};
            console.error('Error parsing offload_layers:', e);
        }
        
        // Set the first tab as active if available
        const moduleLists = getModuleLists();
        if (moduleLists.length > 0) {
            activeTab = moduleLists[0];
        }
        
        showFormModal = true;
    }

    // Handle create new config
    function handleCreateConfig() {
        resetForm();
        showFormModal = true;
    }

    // Reset form
    function resetForm() {
        editingConfigId = null;
        newConfig = {
            name: '',
            quantize: false,
            quantize_dtype: 'float8',
            enable_scale: false,
            enable_bias: false
        };
        selectedLayersDict = {};
        activeTab = '';
        configsError = null;
    }

    // Toggle layer selection
    function toggleLayer(moduleListName: string, layerName: string) {
        const selectedLayers = selectedLayersDict[moduleListName] || [];
        const index = selectedLayers.indexOf(layerName);
        
        if (index !== -1) {
            selectedLayersDict[moduleListName] = selectedLayers.filter(layer => layer !== layerName);
        } else {
            selectedLayersDict[moduleListName] = [...selectedLayers, layerName];
        }
    }

    // Select all layers in a module list
    function selectAllLayers(moduleListName: string, layers: string[]) {
        selectedLayersDict[moduleListName] = [...layers];
    }

    // Deselect all layers in a module list
    function deselectAllLayers(moduleListName: string) {
        selectedLayersDict[moduleListName] = [];
    }

    // Get module lists from scan results
    function getModuleLists(): string[] {
        if (!model?.scan_results) return [];
        return Object.keys(model.scan_results).sort();
    }

    // Load available strategies
    async function loadStrategies() {
        if (!apiService) return;
        try {
            strategies = await apiService.getStrategyNames();
        } catch (err: any) {
            console.error('Error loading strategies:', err);
            strategies = [];
        }
    }

    // Handle strategy change
    function handleStrategyChange(strategy: string) {
        selectedStrategy = strategy;
    }

    // Get current strategy params based on selected strategy
    function getCurrentStrategyParams(): Record<string, any> {
        if (selectedStrategy === 'genetic') {
            return { genetic: geneticParams };
        } else if (selectedStrategy === 'gradient') {
            return { gradient: gradientParams };
        } else if (selectedStrategy === 'greedy') {
            return { greedy: greedyParams };
        }
        return {};
    }

    // Auto-select layers based on strategy
    async function autoSelectLayers(moduleListName: string, strategy: string): Promise<string[]> {
        if (!model?.scan_results || !model.scan_results[moduleListName]) {
            return [];
        }
        
        try {
            const params = getCurrentStrategyParams();
            const result = await apiService.generateStrategy(
                strategy,
                JSON.stringify(model.scan_results[moduleListName]),
                newConfig.quantize,
                params
            );
            return result;
        } catch (err: any) {
            configsError = err.message || '自动选择失败';
            console.error('Error auto-selecting layers:', err);
            return [];
        }
    }

    // Handle auto-select button click
    async function handleAutoSelect() {
        if (!activeTab || !selectedStrategy) {
            configsError = '请先选择一个策略';
            return;
        }
        
        try {
            autoSelectLoading = true;
            configsError = null;
            const layersToSelect = await autoSelectLayers(activeTab, selectedStrategy);
            selectedLayersDict[activeTab] = layersToSelect;
        } catch (err: any) {
            configsError = err.message || '自动选择失败';
            console.error('Error auto-selecting layers:', err);
        } finally {
            autoSelectLoading = false;
        }
    }

    // Get layer count from offload_layers
    function getLayerCount(offloadLayers: string): number {
        try {
            if (typeof offloadLayers === 'string' && offloadLayers) {
                const moduleDict = JSON.parse(offloadLayers);
                let count = 0;
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

    function handleBack() {
        history.back();
    }
</script>

<div class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-purple-50/20 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 p-4 sm:p-6 lg:p-8">
    <div class="max-w-7xl mx-auto">
        <!-- Header Section -->
        <div class="mb-8">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div class="space-y-2">
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                            <Icon icon="mdi:cog-outline" class="w-7 h-7 text-white" />
                        </div>
                        <div>
                            <h1 class="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent">配置管理</h1>
                            {#if model}
                                <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5 flex items-center gap-1.5">
                                    <Icon icon="mdi:cube-outline" class="w-4 h-4" />
                                    <span class="font-medium">{model.name}</span>
                                    <span class="text-gray-400 dark:text-gray-500">•</span>
                                    <span class="text-gray-400 dark:text-gray-500">{model.hf_name}</span>
                                </p>
                            {/if}
                        </div>
                    </div>
                </div>
                <button 
                    class="group inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-xl border border-gray-200/60 dark:border-gray-700/60 hover:bg-white dark:hover:bg-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-2 transition-all duration-200"
                    onclick={handleBack}
                >
                    <Icon icon="mdi:arrow-left" class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
                    返回
                </button>
            </div>
        </div>

        {#if loading && !model}
            <!-- Loading State -->
            <div class="flex flex-col justify-center items-center py-24">
                <div class="relative">
                    <div class="w-16 h-16 rounded-full border-4 border-blue-100 dark:border-blue-900/30"></div>
                    <div class="absolute inset-0 w-16 h-16 rounded-full border-4 border-transparent border-t-blue-500 border-r-blue-500 animate-spin"></div>
                </div>
                <span class="mt-4 text-gray-600 dark:text-gray-400 font-medium">加载中...</span>
            </div>
        {:else if error && !model}
            <!-- Error State -->
            <div class="p-8 bg-gradient-to-br from-red-50/80 to-red-100/50 dark:from-red-950/30 dark:to-red-900/20 border border-red-200/60 dark:border-red-800/50 rounded-2xl backdrop-blur-sm">
                <div class="flex items-start gap-4">
                    <div class="w-12 h-12 rounded-xl bg-red-100 dark:bg-red-900/40 flex items-center justify-center shrink-0">
                        <Icon icon="mdi:alert-circle" class="w-7 h-7 text-red-600 dark:text-red-400" />
                    </div>
                    <div class="flex-1">
                        <h2 class="text-lg font-semibold text-red-900 dark:text-red-200 mb-1">加载失败</h2>
                        <p class="text-red-700 dark:text-red-300/90">{error}</p>
                        <button 
                            class="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-600 to-red-500 rounded-lg hover:from-red-700 hover:to-red-600 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg"
                            onclick={loadModel}
                        >
                            <Icon icon="mdi:refresh" class="w-4 h-4" />
                            重试
                        </button>
                    </div>
                </div>
            </div>
        {:else if model}
            <!-- Config List Card -->
            <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl rounded-2xl shadow-xl shadow-gray-200/50 dark:shadow-black/30 ring-1 ring-gray-200/60 dark:ring-gray-700/60 overflow-hidden">
                <!-- Card Header -->
                <div class="px-6 py-5 border-b border-gray-200/60 dark:border-gray-700/60 bg-gradient-to-r from-gray-50/50 to-transparent dark:from-gray-700/30">
                    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
                                <Icon icon="mdi:format-list-bulleted" class="w-5 h-5 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div>
                                <h2 class="text-lg font-semibold text-gray-900 dark:text-white">配置列表</h2>
                                <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">共 {configs.length} 个配置</p>
                            </div>
                        </div>
                        <div class="flex flex-wrap items-center gap-2">
                            {#if configs.length > 0}
                                <button 
                                    class="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 bg-gray-100/80 dark:bg-gray-700/80 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                                    onclick={selectAllConfigs}
                                    disabled={selectedConfigIds.size === configs.length}
                                >
                                    全选
                                </button>
                                <button 
                                    class="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 bg-gray-100/80 dark:bg-gray-700/80 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                                    onclick={deselectAllConfigs}
                                    disabled={selectedConfigIds.size === 0}
                                >
                                    取消全选
                                </button>
                                <button 
                                    class="px-3 py-2 text-sm font-medium text-white bg-gradient-to-r from-red-600 to-red-500 rounded-lg hover:from-red-700 hover:to-red-600 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg"
                                    onclick={batchDeleteConfigs}
                                    disabled={selectedConfigIds.size === 0 || batchDeleting}
                                >
                                    {batchDeleting ? '删除中...' : `批量删除 (${selectedConfigIds.size})`}
                                </button>
                            {/if}
                            <button 
                                class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-blue-500 rounded-lg hover:from-blue-700 hover:to-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-1 transition-all duration-200 shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                                onclick={handleCreateConfig}
                            >
                                <Icon icon="mdi:plus" class="w-4 h-4" />
                                新建配置
                            </button>
                        </div>
                    </div>
                </div>

                {#if configsError}
                    <div class="mx-6 mt-4 p-4 bg-gradient-to-r from-red-50 to-red-100/80 dark:from-red-950/40 dark:to-red-900/30 border border-red-200/60 dark:border-red-800/50 rounded-xl">
                        <div class="flex items-center gap-2 text-red-700 dark:text-red-300">
                            <Icon icon="mdi:alert-circle" class="w-5 h-5" />
                            <span class="text-sm font-medium">{configsError}</span>
                        </div>
                    </div>
                {/if}

                {#if configsLoading}
                    <div class="flex justify-center items-center py-16">
                        <div class="relative">
                            <div class="w-12 h-12 rounded-full border-4 border-blue-100 dark:border-blue-900/30"></div>
                            <div class="absolute inset-0 w-12 h-12 rounded-full border-4 border-transparent border-t-blue-500 border-r-blue-500 animate-spin"></div>
                        </div>
                        <span class="ml-3 text-gray-600 dark:text-gray-400 font-medium">加载中...</span>
                    </div>
                {:else if configs.length === 0}
                    <div class="py-16 text-center">
                        <div class="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-gray-100 to-gray-200/50 dark:from-gray-700 dark:to-gray-600/50 flex items-center justify-center mb-4">
                            <Icon icon="mdi:file-document-outline" class="w-10 h-10 text-gray-400 dark:text-gray-500" />
                        </div>
                        <p class="text-gray-500 dark:text-gray-400 font-medium">暂无配置</p>
                        <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">创建您的第一个配置以开始使用</p>
                        <button 
                            class="mt-6 inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-blue-500 rounded-lg hover:from-blue-700 hover:to-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                            onclick={handleCreateConfig}
                        >
                            <Icon icon="mdi:plus" class="w-4 h-4" />
                            创建第一个配置
                        </button>
                    </div>
                {:else}
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200/60 dark:divide-gray-700/60">
                            <thead class="bg-gradient-to-r from-gray-50/80 to-gray-100/50 dark:from-gray-700/50 dark:to-gray-700/30">
                                <tr>
                                    <th scope="col" class="px-6 py-4 text-left">
                                        <input
                                            type="checkbox"
                                            checked={selectedConfigIds.size === configs.length && configs.length > 0}
                                            onchange={() => {
                                                if (selectedConfigIds.size === configs.length) {
                                                    deselectAllConfigs();
                                                } else {
                                                    selectAllConfigs();
                                                }
                                            }}
                                            class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer transition-colors"
                                        />
                                    </th>
                                    <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                                        配置名称
                                    </th>
                                    <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                                        卸载层数
                                    </th>
                                    <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                                        量化
                                    </th>
                                    <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                                        Scale/Bias
                                    </th>
                                    <th scope="col" class="px-6 py-4 text-right text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                                        操作
                                    </th>
                                </tr>
                            </thead>
                            <tbody class="bg-transparent divide-y divide-gray-200/60 dark:divide-gray-700/60">
                                {#each configs as config (config.id)}
                                    <tr class="group hover:bg-blue-50/50 dark:hover:bg-blue-900/20 transition-all duration-200">
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            <input
                                                type="checkbox"
                                                checked={selectedConfigIds.has(config.id)}
                                                onchange={() => toggleConfigSelection(config.id)}
                                                class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer transition-colors"
                                            />
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            <div class="flex items-center gap-2">
                                                <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">
                                                    {config.name.charAt(0).toUpperCase()}
                                                </div>
                                                <span class="text-sm font-semibold text-gray-900 dark:text-white">{config.name}</span>
                                            </div>
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            <div class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200/60 dark:border-indigo-700/50">
                                                <Icon icon="mdi:layers" class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                                                <span class="text-sm font-semibold text-indigo-700 dark:text-indigo-300">{getLayerCount(config.offload_layers)}</span>
                                            </div>
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            {#if config.quantize}
                                                <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-emerald-50 to-emerald-100/80 text-emerald-700 dark:from-emerald-900/40 dark:to-emerald-800/30 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-700/50 shadow-sm">
                                                    <Icon icon="mdi:chip" class="w-3.5 h-3.5" />
                                                    {config.quantize_dtype}
                                                </span>
                                            {:else}
                                                <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100/80 text-gray-600 dark:bg-gray-700/60 dark:text-gray-400 border border-gray-200/60 dark:border-gray-600/50">
                                                    <Icon icon="mdi:cancel" class="w-3.5 h-3.5" />
                                                    未启用
                                                </span>
                                            {/if}
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap">
                                            {#if config.enable_scale || config.enable_bias}
                                                <span class="inline-flex items-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-300">
                                                    {#if config.enable_scale}
                                                        <span class="px-2 py-1 rounded-md bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs font-semibold border border-purple-200/60 dark:border-purple-700/50">Scale</span>
                                                    {/if}
                                                    {#if config.enable_scale && config.enable_bias}
                                                        <Icon icon="mdi:plus" class="w-3 h-3 text-gray-400" />
                                                    {/if}
                                                    {#if config.enable_bias}
                                                        <span class="px-2 py-1 rounded-md bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-semibold border border-amber-200/60 dark:border-amber-700/50">Bias</span>
                                                    {/if}
                                                </span>
                                            {:else}
                                                <span class="text-sm text-gray-400 dark:text-gray-500">-</span>
                                            {/if}
                                        </td>
                                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            <div class="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                                <button
                                                    class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-800/50 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-1 transition-all duration-200 border border-blue-200/60 dark:border-blue-700/50"
                                                    onclick={() => handleEditConfig(config)}
                                                >
                                                    <Icon icon="mdi:pencil" class="w-3.5 h-3.5" />
                                                    编辑
                                                </button>
                                                <button
                                                    class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 rounded-lg hover:bg-red-100 dark:hover:bg-red-800/50 focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:ring-offset-1 transition-all duration-200 border border-red-200/60 dark:border-red-700/50"
                                                    onclick={() => deleteConfig(config.id)}
                                                >
                                                    <Icon icon="mdi:trash-can" class="w-3.5 h-3.5" />
                                                    删除
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {/if}
            </div>
        {/if}
    </div>
</div>

<!-- Config Form Modal -->
{#if showFormModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
        <!-- Backdrop with blur -->
        <div 
            class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onclick={() => {
                resetForm();
                showFormModal = false;
            }}
        ></div>
        
        <!-- Modal Content -->
        <div class="relative w-full max-w-5xl max-h-[90vh] bg-gradient-to-br from-white via-white to-blue-50/30 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 rounded-2xl shadow-2xl shadow-black/30 ring-1 ring-gray-200/60 dark:ring-gray-700/60 overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
            <!-- Modal Header -->
            <div class="px-6 py-5 border-b border-gray-200/60 dark:border-gray-700/60 bg-gradient-to-r from-gray-50/50 to-transparent dark:from-gray-700/30">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                            <Icon icon={editingConfigId ? "mdi:pencil" : "mdi:plus-circle"} class="w-6 h-6 text-white" />
                        </div>
                        <div>
                            <h2 class="text-xl font-bold text-gray-900 dark:text-white">
                                {editingConfigId ? '编辑配置' : '新建配置'}
                            </h2>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                {editingConfigId ? '修改现有配置的参数' : '创建一个新的模型卸载配置'}
                            </p>
                        </div>
                    </div>
                    <button 
                        class="group w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200"
                        onclick={() => {
                            resetForm();
                            showFormModal = false;
                        }}
                    >
                        <Icon icon="mdi:close" class="w-5 h-5 group-hover:rotate-90 transition-transform duration-200" />
                    </button>
                </div>
            </div>

            <!-- Modal Body -->
            <div class="px-6 py-5 overflow-y-auto custom-scrollbar">
                {#if configsError}
                    <div class="mb-5 p-4 bg-gradient-to-r from-red-50 to-red-100/80 dark:from-red-950/40 dark:to-red-900/30 border border-red-200/60 dark:border-red-800/50 rounded-xl">
                        <div class="flex items-center gap-2 text-red-700 dark:text-red-300">
                            <Icon icon="mdi:alert-circle" class="w-5 h-5" />
                            <span class="text-sm font-medium">{configsError}</span>
                        </div>
                    </div>
                {/if}

                <!-- Config Name -->
                <div class="mb-5">
                    <label class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                        <span class="flex items-center gap-1.5">
                            <Icon icon="mdi:label-outline" class="w-4 h-4 text-blue-500" />
                            配置名称
                        </span>
                    </label>
                    <input
                        type="text"
                        bind:value={newConfig.name}
                        placeholder="输入配置名称，例如：optimized-config-v1"
                        class="w-full px-4 py-2.5 border border-gray-300/80 dark:border-gray-600/80 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 bg-white/80 dark:bg-gray-700/80 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 transition-all duration-200"
                    />
                </div>

                <!-- Quantization Options -->
                <div class="mb-5 p-4 bg-gradient-to-br from-emerald-50/50 to-emerald-100/30 dark:from-emerald-950/20 dark:to-emerald-900/10 rounded-xl border border-emerald-200/60 dark:border-emerald-700/40">
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <div class="relative">
                            <input
                                type="checkbox"
                                bind:checked={newConfig.quantize}
                                class="peer sr-only"
                            />
                            <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer-checked:bg-emerald-500 transition-colors duration-200"></div>
                            <div class="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow-md transform transition-transform duration-200 peer-checked:translate-x-5"></div>
                        </div>
                        <div class="flex items-center gap-2">
                            <Icon icon="mdi:chip" class="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                            <span class="text-sm font-semibold text-gray-800 dark:text-gray-200">启用量化</span>
                        </div>
                    </label>
                </div>

                {#if newConfig.quantize}
                    <div class="mb-5 ml-4 pl-4 border-l-2 border-emerald-300 dark:border-emerald-700/50 space-y-4">
                        <div>
                            <label class="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                                <span class="flex items-center gap-1.5">
                                    <Icon icon="mdi:format-list-numbered" class="w-4 h-4 text-purple-500" />
                                    量化数据类型
                                </span>
                            </label>
                            <select
                                bind:value={newConfig.quantize_dtype}
                                class="w-full px-4 py-2.5 border border-gray-300/80 dark:border-gray-600/80 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 bg-white/80 dark:bg-gray-700/80 text-gray-900 dark:text-white transition-all duration-200"
                            >
                                <option value="float8">Float8 (推荐)</option>
                                <option value="int8">Int8</option>
                                <option value="int4">Int4</option>
                            </select>
                        </div>

                        <div class="space-y-3">
                            <label class="flex items-center gap-3 cursor-pointer group">
                                <div class="relative">
                                    <input
                                        type="checkbox"
                                        bind:checked={newConfig.enable_scale}
                                        class="peer sr-only"
                                    />
                                    <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer-checked:bg-purple-500 transition-colors duration-200"></div>
                                    <div class="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow-md transform transition-transform duration-200 peer-checked:translate-x-5"></div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <Icon icon="mdi:tune-vertical" class="w-4 h-4 text-purple-600 dark:text-purple-400" />
                                    <span class="text-sm font-medium text-gray-700 dark:text-gray-300">启用 Scale</span>
                                    <span class="text-xs text-gray-500 dark:text-gray-400">(减少精度损失)</span>
                                </div>
                            </label>
                            <label class="flex items-center gap-3 cursor-pointer group">
                                <div class="relative">
                                    <input
                                        type="checkbox"
                                        bind:checked={newConfig.enable_bias}
                                        class="peer sr-only"
                                    />
                                    <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer-checked:bg-amber-500 transition-colors duration-200"></div>
                                    <div class="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow-md transform transition-transform duration-200 peer-checked:translate-x-5"></div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <Icon icon="mdi:arrow-expand-horizontal" class="w-4 h-4 text-amber-600 dark:text-amber-400" />
                                    <span class="text-sm font-medium text-gray-700 dark:text-gray-300">启用 Bias</span>
                                    <span class="text-xs text-gray-500 dark:text-gray-400">(减少精度损失)</span>
                                </div>
                            </label>
                        </div>
                    </div>
                {/if}

                <!-- Layer Selection -->
                {#if model?.scan_results}
                    <div class="mb-5">
                        <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                            <Icon icon="mdi:layers-outline" class="w-5 h-5 text-indigo-500" />
                            选择卸载层
                        </h3>
                        
                        <!-- Auto Select Strategy -->
                        {#if strategies.length > 0}
                            <div class="mb-5 p-5 bg-gradient-to-br from-purple-50/60 to-purple-100/40 dark:from-purple-950/25 dark:to-purple-900/15 rounded-xl border border-purple-200/60 dark:border-purple-700/40">
                                <h4 class="text-sm font-bold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                                    <Icon icon="mdi:magic-staff" class="w-4 h-4 text-purple-600 dark:text-purple-400" />
                                    自动选择策略
                                </h4>
                                <div class="flex items-center gap-2 mb-3">
                                    <select
                                        value={selectedStrategy}
                                        onchange={(e) => handleStrategyChange(e.target.value)}
                                        class="flex-1 px-4 py-2.5 border border-gray-300/80 dark:border-gray-600/80 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 bg-white/80 dark:bg-gray-700/80 text-gray-900 dark:text-white text-sm transition-all duration-200"
                                    >
                                        <option value="">选择策略</option>
                                        {#each strategies as strategy}
                                            <option value={strategy}>{strategy}</option>
                                        {/each}
                                    </select>
                                    <button
                                        class="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-purple-600 to-purple-500 rounded-xl hover:from-purple-700 hover:to-purple-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                                        onclick={handleAutoSelect}
                                        disabled={!selectedStrategy || autoSelectLoading}
                                    >
                                        {#if autoSelectLoading}
                                            <div class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                            应用中...
                                        {:else}
                                            <Icon icon="mdi:play" class="w-4 h-4" />
                                            应用
                                        {/if}
                                    </button>
                                </div>
                                
                                <!-- Strategy Parameters -->
                                {#if selectedStrategy === 'genetic'}
                                    <div class="grid grid-cols-2 gap-3">
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">种群大小</label>
                                            <input
                                                type="number"
                                                bind:value={geneticParams.population_size}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">迭代次数</label>
                                            <input
                                                type="number"
                                                bind:value={geneticParams.generations}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">交叉率</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                bind:value={geneticParams.crossover_rate}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">变异率</label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                min="0"
                                                max="1"
                                                bind:value={geneticParams.mutation_rate}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                    </div>
                                {:else if selectedStrategy === 'gradient'}
                                    <div class="grid grid-cols-3 gap-3">
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">学习率</label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                min="0.001"
                                                bind:value={gradientParams.learning_rate}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">迭代次数</label>
                                            <input
                                                type="number"
                                                bind:value={gradientParams.iterations}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                        <div class="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">阈值</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                bind:value={gradientParams.threshold}
                                                class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                            />
                                        </div>
                                    </div>
                                {:else if selectedStrategy === 'greedy'}
                                    <div class="max-w-sm p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/50">
                                        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">时间约束比例</label>
                                        <input
                                            type="number"
                                            step="0.1"
                                            min="0.1"
                                            max="2"
                                            bind:value={greedyParams.time_constraint_ratio}
                                            class="w-full px-3 py-2 text-sm border border-gray-300/80 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 dark:bg-gray-700/80 dark:border-gray-600/80 dark:text-white transition-all duration-200"
                                        />
                                        <p class="text-xs text-gray-500 dark:text-gray-400 mt-2 flex items-start gap-1.5">
                                            <Icon icon="mdi:information" class="w-3.5 h-3.5 mt-0.5 shrink-0" />
                                            <span>1.0 表示使用总计算时间作为约束，&gt;1.0 放宽约束，&lt;1.0 收紧约束</span>
                                        </p>
                                    </div>
                                {/if}
                                
                                {#if selectedStrategy}
                                    <div class="mt-3 p-2.5 bg-purple-100/60 dark:bg-purple-900/30 rounded-lg border border-purple-200/60 dark:border-purple-700/40">
                                        <div class="flex items-center gap-2 text-xs text-purple-700 dark:text-purple-300">
                                            <Icon icon="mdi:check-circle" class="w-3.5 h-3.5" />
                                            <span>当前策略将应用于 "<strong>{activeTab || '未选择模块'}</strong>" 模块</span>
                                        </div>
                                    </div>
                                {/if}
                            </div>
                        {/if}
                        
                        <!-- Tabs -->
                        <div class="mb-4">
                            <div class="border-b border-gray-200/60 dark:border-gray-700/60">
                                <nav class="-mb-px flex gap-2 overflow-x-auto">
                                    {#each getModuleLists() as moduleListName}
                                        <button
                                            class="px-4 py-2.5 text-sm font-medium border-b-2 transition-all duration-200 whitespace-nowrap {activeTab === moduleListName ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50/50 dark:bg-blue-900/20 rounded-t-lg' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300 hover:bg-gray-50/50 dark:hover:bg-gray-700/30 rounded-t-lg'}"
                                            onclick={() => activeTab = moduleListName}
                                        >
                                            <span class="flex items-center gap-1.5">
                                                <Icon icon="mdi:package-variant" class="w-4 h-4" />
                                                {moduleListName}
                                            </span>
                                        </button>
                                    {/each}
                                </nav>
                            </div>
                        </div>

                        <!-- Layer List -->
                        {#if activeTab && model.scan_results[activeTab]}
                            {@const moduleData = model.scan_results[activeTab]}
                            {@const layers = moduleData.leaf_module_usage_order || []}
                            {@const selectedLayers = selectedLayersDict[activeTab] || []}
                            
                            <div class="mb-4 flex items-center gap-2">
                                <button
                                    class="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-1 transition-all duration-200 shadow-sm hover:shadow-md"
                                    onclick={() => selectAllLayers(activeTab, layers)}
                                >
                                    <Icon icon="mdi:check-all" class="w-3.5 h-3.5" />
                                    全选
                                </button>
                                <button
                                    class="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400/50 focus:ring-offset-1 transition-all duration-200"
                                    onclick={() => deselectAllLayers(activeTab)}
                                >
                                    <Icon icon="mdi:close-circle" class="w-3.5 h-3.5" />
                                    取消全选
                                </button>
                                <div class="ml-auto px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/30 rounded-lg border border-indigo-200/60 dark:border-indigo-700/50">
                                    <span class="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                                        已选择 <strong>{selectedLayers.length}</strong> / {layers.length} 层
                                    </span>
                                </div>
                            </div>

                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-64 overflow-y-auto p-4 bg-gray-50/50 dark:bg-gray-800/50 rounded-xl border border-gray-200/60 dark:border-gray-700/60 custom-scrollbar">
                                {#each layers as layerName}
                                    <label class="flex items-center gap-2 p-2.5 rounded-lg hover:bg-white dark:hover:bg-gray-700/60 cursor-pointer transition-all duration-200 group">
                                        <input
                                            type="checkbox"
                                            checked={selectedLayers.includes(layerName)}
                                            onchange={() => toggleLayer(activeTab, layerName)}
                                            class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer transition-colors"
                                        />
                                        <span class="text-sm text-gray-700 dark:text-gray-300 truncate group-hover:text-gray-900 dark:group-hover:text-white transition-colors">{layerName}</span>
                                    </label>
                                {/each}
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>

            <!-- Modal Footer -->
            <div class="px-6 py-4 border-t border-gray-200/60 dark:border-gray-700/60 bg-gradient-to-r from-gray-50/50 to-transparent dark:from-gray-700/30 flex justify-end gap-3">
                <button
                    class="px-5 py-2.5 text-sm font-semibold text-gray-700 dark:text-gray-200 bg-white/80 dark:bg-gray-700/80 rounded-xl border border-gray-300/80 dark:border-gray-600/80 hover:bg-gray-50 dark:hover:bg-gray-600 hover:border-gray-400 dark:hover:border-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400/50 focus:ring-offset-1 transition-all duration-200 shadow-sm hover:shadow-md"
                    onclick={() => {
                        resetForm();
                        showFormModal = false;
                    }}
                >
                    取消
                </button>
                <button
                    class="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-blue-500 rounded-xl hover:from-blue-700 hover:to-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:ring-offset-1 transition-all duration-200 shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                    onclick={editingConfigId ? updateConfig : createConfig}
                >
                    <Icon icon={editingConfigId ? "mdi:content-save" : "mdi:plus"} class="w-4 h-4" />
                    {editingConfigId ? '更新配置' : '创建配置'}
                </button>
            </div>
        </div>
    </div>
{/if}
