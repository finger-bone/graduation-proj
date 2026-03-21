<script lang="ts">
    import { page } from '$app/state';
    import { createApiService } from '$lib/api';
    import Icon from '@iconify/svelte';
    import { onMount } from 'svelte';
    import Step3LayerSelection from '../Step3LayerSelection.svelte';
    import { persistent } from '$lib/persist/persist';
    import { derived } from 'svelte/store';

    let host = $state('');
    let modelId = $state('');
    let model = $state<{id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null>(null);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let apiService: ReturnType<typeof createApiService> | null = $state(null);
    
    let passwordDict = persistent<Record<string, string>>('passwordDict', {});
    let password = $derived(() => {
        return $passwordDict[host];
    });

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
    });

    async function loadModel() {
        try {
            loading = true;
            error = null;
            
            apiService = createApiService(host, password());
            const loadedModel = await apiService.getById(modelId);
            model = loadedModel;
        } catch (err: any) {
            error = err.message || 'Failed to load model details';
            console.error('Error loading model:', err);
        } finally {
            loading = false;
        }
    }

    function handleBack() {
        // Navigate back to the model list or main model page
        history.back();
    }
</script>

<div class="max-w-6xl mx-auto p-4 sm:p-6">
    <div class="mb-6 flex items-center justify-between">
        <div>
            <h1 class="text-2xl font-bold text-gray-900 dark:text-white">配置管理</h1>
            {#if model}
                <p class="text-gray-600 dark:text-gray-400 mt-1">模型: {model.name}</p>
            {/if}
        </div>
        <button 
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            onclick={handleBack}
        >
            返回
        </button>
    </div>

    {#if loading && !model}
        <div class="flex justify-center items-center py-12">
            <Icon icon="mdi:loading" class="w-8 h-8 text-blue-500 animate-spin" />
            <span class="ml-3 text-gray-600 dark:text-gray-400">加载中...</span>
        </div>
    {:else if error && !model}
        <div class="p-6 bg-red-50 border border-red-200 rounded-lg text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
            <div class="flex items-start">
                <Icon icon="mdi:alert-circle" class="w-6 h-6 mr-2 shrink-0" />
                <div>
                    <h2 class="text-lg font-medium mb-2">加载失败</h2>
                    <p>{error}</p>
                    <button 
                        class="mt-4 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                        onclick={loadModel}
                    >
                        重试
                    </button>
                </div>
            </div>
        </div>
    {:else if model}
        <Step3LayerSelection 
            {model} 
            {host} 
            {modelId} 
            onPrev={handleBack} 
            onNext={handleBack} 
            password={password()} 
        />
    {/if}
</div>