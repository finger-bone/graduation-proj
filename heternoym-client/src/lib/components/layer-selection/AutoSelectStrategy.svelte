<script lang="ts">
    export let strategies: string[] = [];
    export let selectedStrategy: string = '';
    export let onStrategyChange: (strategy: string) => void = () => {};
    export let onAutoSelect: () => void = () => {};
    export let loading: boolean = false;
</script>

<div class="mb-6 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
    <h2 class="text-lg font-medium text-gray-900 dark:text-white mb-3">
        自动选择策略
    </h2>
    
    <div class="space-y-4">
        <div>
            <span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                选择策略
            </span>
            <select
                bind:value={selectedStrategy}
                onchange={(e: any) => onStrategyChange(e.target.value)}
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                disabled={strategies.length === 0 || loading}
            >
                <option value="" disabled>选择一个策略</option>
                {#each strategies as strategy}
                    <option value={strategy}>{strategy}</option>
                {/each}
            </select>
        </div>
        
        <div class="flex space-x-2">
            <button 
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                onclick={onAutoSelect}
                disabled={!selectedStrategy || loading}
            >
                {loading ? '应用中...' : '应用策略'}
            </button>
        </div>
    </div>
</div>