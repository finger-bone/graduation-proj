<script lang="ts">
    export let configs: {
        id: number, 
        model_id: number, 
        name: string, 
        offload_layers: string, 
        quantize: boolean, 
        quantize_dtype: string, 
        enable_scale: boolean, 
        enable_bias: boolean
    }[] = [];
    export let loading: boolean = false;
    export let onEditConfig: (config: any) => void = () => {};
    export let onDeleteConfig: (configId: number) => void = () => {};
    
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
</script>

<div class="mb-6">
    <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
        现有配置 ({configs.length})
    </h2>
    
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead class="bg-gray-50 dark:bg-gray-700">
                <tr>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        名称
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        量化
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        类型
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        Scale/Bias
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        层数
                    </th>
                    <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                        操作
                    </th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200 dark:bg-gray-800 dark:divide-gray-700">
                {#if loading}
                    <tr>
                        <td colspan="6" class="px-6 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                            <div class="flex items-center justify-center">
                                <div class="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-2"></div>
                                加载中...
                            </div>
                        </td>
                    </tr>
                {:else}
                    {#each configs as config}
                        <tr class="hover:bg-gray-50 dark:hover:bg-gray-750">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                                {config.name}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {config.quantize ? '是' : '否'}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {config.quantize ? config.quantize_dtype : '-'}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {config.enable_scale ? 'Scale' : ''}{config.enable_scale && config.enable_bias ? '/' : ''}{config.enable_bias ? 'Bias' : ''}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {getLayerCount(config.offload_layers)}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button 
                                    on:click={() => onEditConfig(config)}
                                    class="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 mr-3"
                                >
                                    编辑
                                </button>
                                <button 
                                    on:click={() => onDeleteConfig(config.id)}
                                    class="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                                >
                                    删除
                                </button>
                            </td>
                        </tr>
                    {:else}
                        <tr>
                            <td colspan="6" class="px-6 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                                暂无配置
                            </td>
                        </tr>
                    {/each}
                {/if}
            </tbody>
        </table>
    </div>
</div>