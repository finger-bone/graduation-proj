<script lang="ts">
    export let editingConfigId: number | null = null;
    export let newConfig = {
        name: '',
        quantize: false,
        quantize_dtype: 'float8',
        enable_scale: false,
        enable_bias: false
    };
    export let onCreateConfig: () => void = () => {};
    export let onUpdateConfig: () => void = () => {};
    export let loading: boolean = false;
    export let onNameChange: (name: string) => void = () => {};
    export let onQuantizeChange: (quantize: boolean) => void = () => {};
    export let onQuantizeDtypeChange: (dtype: string) => void = () => {};
    export let onEnableScaleChange: (enable: boolean) => void = () => {};
    export let onEnableBiasChange: (enable: boolean) => void = () => {};
</script>

<div class="mb-6 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
    <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
        {editingConfigId ? '编辑配置' : '创建新配置'}
    </h2>
    <div class="space-y-4">
        <div>
            <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                配置名称
            </span>
            <input
                type="text"
                bind:value={newConfig.name}
                oninput={(e: any) => onNameChange(e.target.value)}
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                placeholder="输入配置名称"
            />
        </div>
        
        <div class="flex items-center">
            <input
                type="checkbox"
                bind:checked={newConfig.quantize}
                onchange={(e: any) => onQuantizeChange(e.target.checked)}
                id="quantize"
                class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label for="quantize" class="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                启用量化 <span class="text-gray-500 dark:text-gray-400">(开启后访存时间减半)</span>
            </label>
        </div>
        
        {#if newConfig.quantize}
            <div class="ml-6 space-y-3">
                <div>
                    <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        量化数据类型
                    </span>
                    <select
                        bind:value={newConfig.quantize_dtype}
                        onchange={(e: any) => onQuantizeDtypeChange(e.target.value)}
                        class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    >
                        <option value="float8">Float8</option>
                    </select>
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Scale/Bias可减少量化带来的精度损失，但会增加少量时间开销
                </div>
                <div class="flex items-center">
                    <input
                        type="checkbox"
                        bind:checked={newConfig.enable_scale}
                        onchange={(e: any) => onEnableScaleChange(e.target.checked)}
                        id="enable_scale"
                        class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label for="enable_scale" class="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                        启用 Scale
                    </label>
                </div>
                
                <div class="flex items-center">
                    <input
                        type="checkbox"
                        bind:checked={newConfig.enable_bias}
                        onchange={(e: any) => onEnableBiasChange(e.target.checked)}
                        id="enable_bias"
                        class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label for="enable_bias" class="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                        启用 Bias
                    </label>
                </div>
            </div>
        {/if}
        
        <div class="flex space-x-2">
            <button 
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                onclick={editingConfigId ? onUpdateConfig : onCreateConfig}
                disabled={loading}
            >
                {loading ? '保存中...' : (editingConfigId ? '更新配置' : '创建配置')}
            </button>
        </div>
    </div>
</div>