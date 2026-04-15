<script lang="ts">
    import { onMount } from 'svelte';
    import { createApiService } from '$lib/api';
    import TimeIndicators from '$lib/components/layer-selection/TimeIndicators.svelte';
    import TimeDistributionChart from '$lib/components/layer-selection/TimeDistributionChart.svelte';
    import LayerTabs from '$lib/components/layer-selection/LayerTabs.svelte';
    import LayerList from '$lib/components/layer-selection/LayerList.svelte';
    import EmptyState from '$lib/components/layer-selection/EmptyState.svelte';
    import ConfigForm from '$lib/components/layer-selection/ConfigForm.svelte';
    import ConfigsTable from '$lib/components/layer-selection/ConfigsTable.svelte';
    import AutoSelectStrategy from '$lib/components/layer-selection/AutoSelectStrategy.svelte';
    import StrategyParams from '$lib/components/layer-selection/StrategyParams.svelte';
	import client from '$lib/client';
	import { json } from '@sveltejs/kit';

    let { model, host, modelId, onPrev, onNext, password }: { 
        model: {id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null, 
        host: string, 
        modelId: string,
        onPrev: () => void,
        onNext: () => void,
        password: string
    } = $props();

    // API service initialization
    let apiService = $state(createApiService(host, password));

    // Offload config states
    let configs = $state<{id: number, model_id: number, name: string, offload_layers: string, quantize: boolean, quantize_dtype: string, enable_scale: boolean, enable_bias: boolean}[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);
    
    // Strategy states
    let strategies = $state<string[]>([]);
    let selectedStrategy = $state<string>('');
    let autoSelectLoading = $state<boolean>(false);
    let strategyParams = $state<Record<string, any>>({});
    
    // Form state for creating/updating configs
    let newConfig = $state({
        name: '',
        quantize: false,
        quantize_dtype: 'float8',
        enable_scale: false,
        enable_bias: false
    });
    
    let editingConfigId = $state<number | null>(null);
    
    // Layer selection state - now a dictionary: {module_list_name: [layer_names]}
    let selectedLayersDict = $state<Record<string, string[]>>({});
    
    // Current active tab
    let activeTab = $state<string>('');
    
    // Reactive state for memory and compute times
    let memoryTime = $state(0);
    let computeTime = $state(0);
    let selectedLayersCount = $state(0);

    // Effect to calculate memory time when selected layers or model changes
    $effect(() => {
        if (!model?.scan_results) {
            memoryTime = 0;
            return;
        }
        
        let totalTime = 0;
        let layersCount = 0;
        // Iterate through each module list in the dictionary
        for (const moduleListName in selectedLayersDict) {
            const selectedLayers = selectedLayersDict[moduleListName];
            layersCount += selectedLayers.length;
            // Find the corresponding module data
            if (model.scan_results[moduleListName]) {
                const moduleData = model.scan_results[moduleListName];
                if (moduleData.onload_time) {
                    // Check each layer in the selected list
                    for (const layerName of selectedLayers) {
                        if (moduleData.onload_time[layerName] !== undefined) {
                            totalTime += moduleData.onload_time[layerName];
                        }
                    }
                }
            }
        }
        
        // 如果启用量化，访存时间减半
        if (newConfig.quantize) {
            totalTime /= 2;
        }
        
        memoryTime = totalTime;
        selectedLayersCount = layersCount;
    });
    
    // Effect to calculate compute time when model changes
    $effect(() => {
        if (!model?.scan_results) {
            computeTime = 0;
            return;
        }
        
        let totalTime = 0;
        // Calculate compute time for all module lists that have selected layers
        for (const moduleListName in selectedLayersDict) {
            const selectedLayers = selectedLayersDict[moduleListName];
            // Only calculate if there are selected layers in this module list
            if (selectedLayers.length > 0) {
                // Find the corresponding module data
                if (model.scan_results[moduleListName]) {
                    const moduleData = model.scan_results[moduleListName];
                    if (moduleData.compute_time) {
                        for (const layerName in moduleData.compute_time) {
                            totalTime += moduleData.compute_time[layerName];
                        }
                    }
                }
            }
        }
        computeTime = totalTime;
    });

    // Load configs on mount
    onMount(async () => {
        await loadConfigs();
        // Set the first tab as active if available
        const moduleLists = getModuleLists();
        if (moduleLists.length > 0) {
            activeTab = moduleLists[0];
        }
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

    // Create a new config
    async function createConfig() {
        if (!newConfig.name.trim()) {
            error = 'Configuration name is required';
            return;
        }

        try {
            await apiService.createOffloadConfig({
                model_id: parseInt(modelId),
                name: newConfig.name,
                offload_layers: JSON.stringify(selectedLayersDict), // Convert dictionary to JSON string
                quantize: newConfig.quantize,
                quantize_dtype: newConfig.quantize_dtype,
                enable_scale: newConfig.enable_scale,
                enable_bias: newConfig.enable_bias,
                enable_fp8: false // 保持与后端兼容，但不再使用
            });
            
            // Reset form
            newConfig = {
                name: '',
                quantize: false,
                quantize_dtype: 'float8',
                enable_scale: false,
                enable_bias: false
            };
            
            selectedLayersDict = {}; // Reset to empty dictionary
            
            await loadConfigs(); // Refresh the list
        } catch (err: any) {
            error = err.message || 'Failed to create config';
            console.error('Error creating config:', err);
        }
    }

    // Delete a config
    async function deleteConfig(configId: number) {
        try {
            await apiService.deleteOffloadConfig(configId);
            await loadConfigs(); // Refresh the list
        } catch (err: any) {
            error = err.message || 'Failed to delete config';
            console.error('Error deleting config:', err);
        }
    }
    
    // Toggle layer selection - updated to work with dictionary
    function toggleLayer(moduleListName: string, layerName: string) {
        const selectedLayers = selectedLayersDict[moduleListName] || [];
        const index = selectedLayers.indexOf(layerName);
        
        if (index !== -1) {
            // Remove layer if already selected
            selectedLayersDict[moduleListName] = selectedLayers.filter(layer => layer !== layerName);
        } else {
            // Add layer if not selected
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
    
    // Handle tab change
    function handleTabChange(tab: string) {
        activeTab = tab;
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
        
        // Populate selected layers from config
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
    }
    
    // Handle delete config
    function handleDeleteConfig(configId: number) {
        deleteConfig(configId);
    }
    
    // Handle form input changes
    function handleNameChange(name: string) {
        newConfig.name = name;
    }
    
    function handleQuantizeChange(quantize: boolean) {
        newConfig.quantize = quantize;
    }
    
    function handleQuantizeDtypeChange(dtype: string) {
        newConfig.quantize_dtype = dtype;
    }
    
    function handleEnableScaleChange(enable: boolean) {
        newConfig.enable_scale = enable;
    }
    
    function handleEnableBiasChange(enable: boolean) {
        newConfig.enable_bias = enable;
    }
    
    // Handle strategy change
    function handleStrategyChange(strategy: string) {
        selectedStrategy = strategy;
    }
    
    // Handle strategy params change
    function handleStrategyParamsChange(params: Record<string, any>) {
        strategyParams = params;
    }
    
    // Placeholder function for getting available strategies
    async function getAvailableStrategies(): Promise<string[]> {
        // In a real implementation, this would fetch strategies from an API
        // return ['balance-memory-compute', 'min-memory', 'min-compute'];
        return await apiService.getStrategyNames()
    }

    onMount(async() => {
        strategies = await getAvailableStrategies();
    })
    
    // Placeholder function for auto-selecting layers based on strategy
    async function autoSelectLayers(moduleListName: string, strategy: string): Promise<string[]> {
        // In a real implementation, this would call an API or run an algorithm
        // to determine which layers to select based on the strategy
        if (!model?.scan_results || !model.scan_results[moduleListName]) {
            return [];
        }
        
        const moduleData = model.scan_results[moduleListName];
        const layers = moduleData.leaf_module_usage_order || [];
        return await apiService.generateStrategy(
            strategy,
            JSON.stringify(model?.scan_results[moduleListName]),
            newConfig.quantize,
            strategyParams
        )
        // // Simple placeholder logic - in reality, this would depend on the strategy
        // switch (strategy) {
        //     case 'min-memory':
        //         // Select first half of layers
        //         return layers.slice(0, Math.floor(layers.length / 2));
        //     case 'min-compute':
        //         // Select second half of layers
        //         return layers.slice(Math.floor(layers.length / 2));
        //     case 'balance-memory-compute':
        //     default:
        //         // Select every other layer
        //         return layers.filter((_: string, i: number) => i % 2 === 0);
        // }
    }
    
    // Handle auto-select button click
    async function handleAutoSelect() {
        if (!activeTab || !selectedStrategy) return;
        
        try {
            autoSelectLoading = true;
            const layersToSelect = await autoSelectLayers(activeTab, selectedStrategy);
            selectedLayersDict[activeTab] = layersToSelect;
        } catch (err: any) {
            error = err.message || 'Failed to auto-select layers';
            console.error('Error auto-selecting layers:', err);
        } finally {
            autoSelectLoading = false;
        }
    }
</script>

<div class="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 rounded-2xl shadow-xl ring-1 ring-slate-200 dark:ring-slate-700 overflow-hidden">
    <!-- Header Section -->
    <div class="px-6 py-5 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-purple-500 via-pink-500 to-rose-500">
        <h1 class="text-2xl font-bold text-white flex items-center">
            <svg class="w-7 h-7 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
            </svg>
            层选择与配置管理
        </h1>
        <p class="text-sm text-white/80 mt-1 ml-10">选择要卸载的模型层并创建配置</p>
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
        
        <TimeIndicators {memoryTime} {computeTime} {selectedLayersCount} />
        
        <TimeDistributionChart {memoryTime} {computeTime} />
        
        <!-- Layer selection section -->
        <div>
            <h2 class="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
                <svg class="w-5 h-5 mr-2 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
                </svg>
                层选择
            </h2>
            
            {#if model?.scan_results}
                <div class="space-y-4">
                    <LayerTabs {model} {activeTab} onTabChange={handleTabChange} />
                    <AutoSelectStrategy 
                        {strategies}
                        {selectedStrategy}
                        onStrategyChange={handleStrategyChange}
                        onAutoSelect={handleAutoSelect}
                        loading={autoSelectLoading}
                    />
                    <StrategyParams 
                        strategy={selectedStrategy}
                        params={strategyParams}
                        onParamsChange={handleStrategyParamsChange}
                    />
                    <LayerList 
                        {model} 
                        {activeTab} 
                        {selectedLayersDict} 
                        onToggleLayer={toggleLayer}
                        onSelectAll={selectAllLayers}
                        onDeselectAll={deselectAllLayers}
                    />
                </div>
            {:else}
                <EmptyState 
                    title="暂无层信息" 
                    description="无法从模型扫描结果中获取层信息" 
                />
            {/if}
        </div>
        
        <ConfigForm 
            {editingConfigId}
            {newConfig}
            onCreateConfig={createConfig}
            loading={loading}
            onNameChange={handleNameChange}
            onQuantizeChange={handleQuantizeChange}
            onQuantizeDtypeChange={handleQuantizeDtypeChange}
            onEnableScaleChange={handleEnableScaleChange}
            onEnableBiasChange={handleEnableBiasChange}
        />
        
        <ConfigsTable 
            {configs} 
            {loading} 
            onEditConfig={handleEditConfig}
            onDeleteConfig={handleDeleteConfig}
        />
        
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