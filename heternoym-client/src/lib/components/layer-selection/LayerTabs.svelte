<script lang="ts">
    import type { TorchModel } from '$lib/api';
    
    export let model: TorchModel | null = null;
    export let activeTab: string = '';
    export let onTabChange: (tab: string) => void = () => {};
    
    function getModuleLists(): string[] {
        if (!model?.scan_results) return [];
        return Object.keys(model.scan_results).sort();
    }
</script>

<div class="mb-4 border-b border-gray-200 dark:border-gray-700">
    <nav class="-mb-px flex space-x-8 overflow-x-auto">
        {#each getModuleLists() as moduleListName}
            <button
                class="whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm transition-colors duration-200 {activeTab === moduleListName ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'}"
                onclick={() => onTabChange(moduleListName)}
            >
                {moduleListName}
            </button>
        {/each}
    </nav>
</div>

{#if model?.scan_results}
    <!-- Tabs for module lists -->
{/if}