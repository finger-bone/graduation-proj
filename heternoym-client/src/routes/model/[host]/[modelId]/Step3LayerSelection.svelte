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

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg ring-1 ring-gray-300 dark:ring-gray-700 overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">层选择</h1>
    </div>
    
    <div class="px-6 py-4">
        <!-- Display error if exists -->
        {#if error}
            <div class="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
            </div>
        {/if}
        
        <TimeIndicators {memoryTime} {computeTime} {selectedLayersCount} />
        
        <TimeDistributionChart {memoryTime} {computeTime} />
        
        <!-- Layer selection -->
        <div class="mb-6">
            <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
                层选择
            </h2>
            
            {#if model?.scan_results}
                <LayerTabs {model} {activeTab} onTabChange={handleTabChange} />
                <AutoSelectStrategy 
                    {strategies}
                    {selectedStrategy}
                    onStrategyChange={handleStrategyChange}
                    onAutoSelect={handleAutoSelect}
                    loading={autoSelectLoading}
                />
                <LayerList 
                    {model} 
                    {activeTab} 
                    {selectedLayersDict} 
                    onToggleLayer={toggleLayer}
                    onSelectAll={selectAllLayers}
                    onDeselectAll={deselectAllLayers}
                />
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