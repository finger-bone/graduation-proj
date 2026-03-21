<script lang="ts">
    import Icon from '@iconify/svelte';
    import type { TorchModel } from '$lib/api';
    
    export let model: TorchModel | null = null;
    export let activeTab: string = '';
    export let selectedLayersDict: Record<string, string[]> = {};
    export let onToggleLayer: (moduleListName: string, layerName: string) => void = () => {};
    export let onSelectAll: (moduleListName: string, layers: string[]) => void = () => {};
    export let onDeselectAll: (moduleListName: string) => void = () => {};
    
    function getLayersForModule(moduleListName: string): string[] {
        if (!model?.scan_results || !model.scan_results[moduleListName]) return [];
        
        const moduleData = model.scan_results[moduleListName];
        if (moduleData.leaf_module_usage_order) {
            return [...moduleData.leaf_module_usage_order].sort();
        }
        return [];
    }
    
    function getLayerLoadTime(moduleListName: string, layerName: string): number {
        if (!model?.scan_results || !model.scan_results[moduleListName]) return 0;
        
        const moduleData = model.scan_results[moduleListName];
        if (moduleData.onload_time && moduleData.onload_time[layerName] !== undefined) {
            return moduleData.onload_time[layerName];
        }
        return 0;
    }
    
    function isAllSelected(moduleListName: string): boolean {
        const allLayers = getLayersForModule(moduleListName);
        const selectedLayers = selectedLayersDict[moduleListName] || [];
        return allLayers.length > 0 && allLayers.length === selectedLayers.length;
    }
    
    function handleSelectAll() {
        const layers = getLayersForModule(activeTab);
        onSelectAll(activeTab, layers);
    }
    
    function handleDeselectAll() {
        onDeselectAll(activeTab);
    }
</script>

<div class="border border-gray-200 dark:border-gray-700 rounded-lg">
    <div class="flex justify-between items-center p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
        <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
            层列表
        </div>
        <div class="flex space-x-2">
            <button 
                class="px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                on:click={handleSelectAll}
                disabled={!activeTab || getLayersForModule(activeTab).length === 0}
            >
                全选
            </button>
            <button 
                class="px-2 py-1 text-xs font-medium text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-300"
                on:click={handleDeselectAll}
                disabled={!activeTab || (selectedLayersDict[activeTab] || []).length === 0}
            >
                取消全选
            </button>
        </div>
    </div>
    
    <div class="max-h-80 overflow-y-auto">
        {#if activeTab && getLayersForModule(activeTab).length > 0}
            {#each getLayersForModule(activeTab) as layerName}
                <button 
                    class="flex items-center w-full px-4 py-3 border-b border-gray-200 dark:border-gray-700 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-750 cursor-pointer"
                    on:click={() => onToggleLayer(activeTab, layerName)}
                >
                    <input
                        type="checkbox"
                        checked={(selectedLayersDict[activeTab] || []).includes(layerName)}
                        class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        on:click={(e) => e.stopPropagation()}
                    />
                    <div class="ml-3 flex-1 text-left">
                        <div class="text-sm text-gray-700 dark:text-gray-300">
                            {layerName}
                        </div>
                        <div class="text-xs text-gray-500 dark:text-gray-400">
                            访存时间: {getLayerLoadTime(activeTab, layerName).toFixed(2)} ns
                        </div>
                    </div>
                </button>
            {/each}
        {:else}
            <div class="text-center py-6">
                <Icon icon="mdi:file-document-outline" class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
                <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-white">暂无层信息</h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    该模块列表中没有可选择的层
                </p>
            </div>
        {/if}
    </div>
</div>