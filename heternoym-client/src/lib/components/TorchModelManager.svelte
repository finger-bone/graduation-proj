<script lang="ts">
    import { onMount } from 'svelte';
    import { createApiService } from '../api';
    import Label from './Label.svelte';
    import Modal from './Modal.svelte';
    import Icon from '@iconify/svelte';
	import { goto } from '$app/navigation';

    // Props
    let { 
        remoteAddress,
        selectedModelId = $bindable(''),
        password,
    }: { 
        remoteAddress: string,
        selectedModelId?: string,
        password: string,
    } = $props();

    // State
    let models = $state<{id: string, name: string, hf_name: string, path: string, scan_status: string}[]>([]);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let showCreateModal = $state(false);
    let newModel = $state({ name: '', hf_name: '', path: '' });
    let apiService = $state(createApiService(remoteAddress, password));

    // Selected models for batch operations
    let selectedModels = $state<Set<string>>(new Set());
    let batchDeleting = $state(false);

    // New Pagination and Filter States
    let currentPage = $state(1);
    let itemsPerPage = $state(10);
    let totalItems = $state(0);
    let totalPages = $state(0);
    let searchFilters = $state<{
        hf_name: string | null,
        name: string | null,
        scan_status: string | null
    }>({ hf_name: null, name: null, scan_status: null });

    // Load models on mount
    onMount(async () => {
        await loadModels();
    });

    // Load all models from the API with pagination and filters
    async function loadModels() {
        try {
            loading = true;
            error = null;
            const response = await apiService.search(
                searchFilters.hf_name,
                searchFilters.name,
                searchFilters.scan_status,
                itemsPerPage,
                currentPage - 1 // API uses zero-based indexing for pages
            );
            models = response.items;
            totalItems = response.total;
            totalPages = Math.ceil(totalItems / itemsPerPage);
        } catch (err: any) {
            error = err.message || 'Failed to load models';
            console.error('Error loading models:', err);
        } finally {
            loading = false;
        }
    }

    // Handle search form submission
    function handleSearch(filters: { hf_name: string | null, name: string | null, scan_status: string | null }) {
        searchFilters = filters;
        currentPage = 1; // Reset to first page on new search
        loadModels();
    }

    // Create a new model
    async function createModel() {
        if (!newModel.name.trim() || !newModel.hf_name.trim() || !newModel.path.trim()) {
            return;
        }

        try {
            await apiService.create(newModel);
            newModel = { name: '', hf_name: '', path: '' };
            showCreateModal = false;
            await loadModels(); // Refresh the list
        } catch (err: any) {
            error = err.message || 'Failed to create model';
            console.error('Error creating model:', err);
        }
    }

    // Delete a model
    async function deleteModel(modelId: string) {
        try {
            await apiService.delete(modelId);
            await loadModels(); // Refresh the list
        } catch (err: any) {
            error = err.message || 'Failed to delete model';
            console.error('Error deleting model:', err);
        }
    }
    
    // Handle model selection
    function selectModel(modelId: string) {
        if (selectedModelId === modelId) {
            // Deselect if clicking the same model
            selectedModelId = '';
        } else {
            // Select the new model
            selectedModelId = modelId;
        }
    }

    function deployModel(modelId: string) {
        goto(`/deploy/${remoteAddress}/${modelId}`)
    }

    function generateConfig(modelId: string) {
        // Navigate to the config generation page (Step3LayerSelection)
        goto(`/model/${encodeURIComponent(remoteAddress)}/${modelId}`);
    }

    function manageConfig(modelId: string) {
        // Navigate to the dedicated configuration management page
        goto(`/model/${encodeURIComponent(remoteAddress)}/${modelId}/configs-manage`);
    }

    // Toggle model selection for batch operations
    function toggleModelSelection(modelId: string) {
        if (selectedModels.has(modelId)) {
            selectedModels.delete(modelId);
        } else {
            selectedModels.add(modelId);
        }
        selectedModels = new Set(selectedModels); // Trigger reactivity
    }

    // Select all visible models
    function selectAllModels() {
        selectedModels = new Set(models.map(m => m.id));
    }

    // Deselect all models
    function deselectAllModels() {
        selectedModels.clear();
        selectedModels = new Set();
    }

    // Batch delete selected models
    async function batchDeleteModels() {
        if (selectedModels.size === 0) {
            alert('请先选择要删除的模型');
            return;
        }

        if (!confirm(`确定要删除选中的 ${selectedModels.size} 个模型吗？`)) {
            return;
        }

        batchDeleting = true;
        const modelsToDelete = Array.from(selectedModels);
        let successCount = 0;
        let failCount = 0;

        try {
            // Delete each model by calling the single delete API multiple times
            for (const modelId of modelsToDelete) {
                try {
                    await apiService.delete(modelId);
                    successCount++;
                } catch (err: any) {
                    console.error(`Failed to delete model ${modelId}:`, err);
                    failCount++;
                }
            }

            // Clear selections
            selectedModels.clear();
            selectedModels = new Set();

            // Refresh the list
            await loadModels();

            // Show result
            if (failCount === 0) {
                alert(`已成功删除 ${successCount} 个模型`);
            } else {
                alert(`删除完成：成功 ${successCount} 个，失败 ${failCount} 个`);
            }
        } catch (err: any) {
            console.error('Batch delete error:', err);
            alert('批量删除失败: ' + (err.message || '未知错误'));
        } finally {
            batchDeleting = false;
        }
    }
</script>

<div class="mt-6">
    <!-- Header Section -->
    <div class="mb-6 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl shadow-lg p-6 text-white">
        <div class="flex justify-between items-center">
            <div>
                <h2 class="text-xl font-bold flex items-center">
                    <svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                    Torch Models
                </h2>
                <p class="text-sm text-white/80 mt-1">
                    管理您的 PyTorch 模型
                </p>
            </div>
            <div class="flex space-x-3">
                <button 
                    class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-indigo-600 bg-white rounded-xl hover:bg-indigo-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-indigo-500 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5"
                    onclick={() => showCreateModal = true}
                >
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                    </svg>
                    添加模型
                </button>
                {#if models.length > 0}
                    <button 
                        class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-slate-700 bg-white/90 backdrop-blur-sm rounded-xl hover:bg-white focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-indigo-500 transition-all duration-200 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                        onclick={selectAllModels}
                        disabled={selectedModels.size === models.length || models.length === 0}
                    >
                        全选
                    </button>
                    <button 
                        class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-slate-700 bg-white/90 backdrop-blur-sm rounded-xl hover:bg-white focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-indigo-500 transition-all duration-200 shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                        onclick={deselectAllModels}
                        disabled={selectedModels.size === 0}
                    >
                        取消
                    </button>
                    <button 
                        class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-red-500 to-red-600 rounded-xl hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-indigo-500 transition-all duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                        onclick={batchDeleteModels}
                        disabled={selectedModels.size === 0 || batchDeleting}
                    >
                        {#if batchDeleting}
                            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            删除中...
                        {:else}
                            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                            </svg>
                            批量删除 ({selectedModels.size})
                        {/if}
                    </button>
                {/if}
                <button 
                    class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-indigo-600 bg-white rounded-xl hover:bg-indigo-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-indigo-500 transition-all duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                    onclick={() => loadModels()}
                    disabled={loading}
                >
                    {#if loading}
                        <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-indigo-600" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        刷新中...
                    {:else}
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                        </svg>
                        刷新
                    {/if}
                </button>
            </div>
        </div>
    </div>

    <!-- Search Form -->
    <form onsubmit={() => handleSearch({ hf_name: searchFilters.hf_name, name: searchFilters.name, scan_status: searchFilters.scan_status })} class="mb-6">
        <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-md p-6 border border-slate-200 dark:border-slate-700">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="relative">
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path>
                        </svg>
                    </div>
                    <input
                        type="text"
                        bind:value={searchFilters.hf_name}
                        placeholder="HuggingFace 名称"
                        class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                    />
                </div>
                <div class="relative">
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                        </svg>
                    </div>
                    <input
                        type="text"
                        bind:value={searchFilters.name}
                        placeholder="模型名称"
                        class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                    />
                </div>
                <div class="relative">
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <select bind:value={searchFilters.scan_status} class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white appearance-none cursor-pointer">
                        <option value={null}>所有状态</option>
                        <option value="pending">待处理</option>
                        <option value="ready">已就绪</option>
                        <option value="scanning">扫描中</option>
                        <option value="completed">已完成</option>
                    </select>
                    <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                        <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </div>
                </div>
            </div>
            <div class="flex justify-end mt-4">
                <button type="submit" class="inline-flex items-center px-6 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl hover:from-indigo-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                    搜索
                </button>
            </div>
        </div>
    </form>

    {#if error}
        <div class="mb-6 p-4 bg-gradient-to-r from-red-50 to-red-100 dark:from-red-900/30 dark:to-red-800/30 border-l-4 border-red-500 rounded-xl text-red-700 dark:text-red-300 shadow-sm">
            <div class="flex items-center">
                <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <span class="font-medium">错误:</span>
                <span class="ml-1">{error}</span>
            </div>
        </div>
    {/if}

    {#if loading}
        <div class="flex justify-center items-center py-16 bg-white dark:bg-slate-800 rounded-2xl shadow-md border border-slate-200 dark:border-slate-700">
            <div class="relative">
                <div class="animate-spin rounded-full h-16 w-16 border-4 border-indigo-200 dark:border-indigo-900"></div>
                <div class="animate-spin rounded-full h-16 w-16 border-t-4 border-indigo-600 absolute top-0 left-0"></div>
            </div>
            <span class="ml-4 text-lg font-medium text-slate-600 dark:text-slate-300">加载中...</span>
        </div>
    {:else}
        {#if models.length === 0}
            <div class="py-16 text-center bg-white dark:bg-slate-800 rounded-2xl shadow-md border border-slate-200 dark:border-slate-700">
                <svg class="mx-auto h-16 w-16 text-slate-300 dark:text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                </svg>
                <p class="mt-4 text-lg font-medium text-slate-500 dark:text-slate-400">暂无模型数据</p>
                <p class="mt-2 text-sm text-slate-400 dark:text-slate-500">点击"添加模型"按钮创建第一个模型</p>
            </div>
        {:else}
            <div class="overflow-hidden rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                <table class="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
                    <thead class="bg-gradient-to-r from-slate-50 to-slate-100 dark:from-slate-700 dark:to-slate-800">
                        <tr>
                            <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider w-12">
                                <input 
                                    type="checkbox" 
                                    checked={selectedModels.size === models.length && models.length > 0}
                                    onchange={() => {
                                        if (selectedModels.size === models.length) {
                                            deselectAllModels();
                                        } else {
                                            selectAllModels();
                                        }
                                    }}
                                    class="w-4 h-4 text-indigo-600 border-slate-300 dark:border-slate-600 rounded focus:ring-indigo-500 cursor-pointer transition-colors"
                                />
                            </th>
                            <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                                模型名称
                            </th>
                            <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                                HuggingFace 名称
                            </th>
                            <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                                路径
                            </th>
                            <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                                状态
                            </th>
                            <th scope="col" class="px-6 py-4 text-right text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                                操作
                            </th>
                        </tr>
                    </thead>
                    <tbody class="bg-white dark:bg-slate-800 divide-y divide-slate-200 dark:divide-slate-700">
                        {#each models as model, index (model.id)}
                            <tr class="hover:bg-gradient-to-r hover:from-indigo-50 hover:to-purple-50 dark:hover:from-indigo-900/20 dark:hover:to-purple-900/20 transition-all duration-200 {index % 2 === 0 ? 'bg-white dark:bg-slate-800' : 'bg-slate-50/50 dark:bg-slate-800/50'}">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <input 
                                        type="checkbox" 
                                        checked={selectedModels.has(model.id)}
                                        onchange={() => toggleModelSelection(model.id)}
                                        class="w-4 h-4 text-indigo-600 border-slate-300 dark:border-slate-600 rounded focus:ring-indigo-500 cursor-pointer transition-colors"
                                    />
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-semibold text-slate-900 dark:text-white">{model.name}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm text-slate-600 dark:text-slate-400 font-mono">{model.hf_name}</div>
                                </td>
                                <td class="px-6 py-4">
                                    <div class="text-sm text-slate-600 dark:text-slate-400 truncate max-w-xs font-mono">{model.path}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    {#if model.scan_status === 'pending'}
                                        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gradient-to-r from-yellow-100 to-yellow-200 text-yellow-800 dark:from-yellow-900/50 dark:to-yellow-800/50 dark:text-yellow-200 shadow-sm">
                                            <svg class="w-3 h-3 mr-1.5" fill="currentColor" viewBox="0 0 8 8">
                                                <circle cx="4" cy="4" r="3"></circle>
                                            </svg>
                                            待处理
                                        </span>
                                    {:else if model.scan_status === 'ready'}
                                        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gradient-to-r from-cyan-100 to-cyan-200 text-cyan-800 dark:from-cyan-900/50 dark:to-cyan-800/50 dark:text-cyan-200 shadow-sm">
                                            <svg class="w-3 h-3 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                                            </svg>
                                            已就绪
                                        </span>
                                    {:else if model.scan_status === 'scanning'}
                                        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/50 dark:to-blue-800/50 dark:text-blue-200 shadow-sm">
                                            <svg class="w-3 h-3 mr-1.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            扫描中
                                        </span>
                                    {:else if model.scan_status === 'completed'}
                                        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gradient-to-r from-green-100 to-green-200 text-green-800 dark:from-green-900/50 dark:to-green-800/50 dark:text-green-200 shadow-sm">
                                            <svg class="w-3 h-3 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                                            </svg>
                                            已完成
                                        </span>
                                    {:else}
                                        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gradient-to-r from-slate-100 to-slate-200 text-slate-800 dark:from-slate-700 dark:to-slate-600 dark:text-slate-200 shadow-sm">
                                            {model.scan_status}
                                        </span>
                                    {/if}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                    <div class="flex justify-end space-x-2">
                                        <button
                                            class="inline-flex items-center px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg hover:from-blue-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-sm hover:shadow-md transform hover:-translate-y-0.5"
                                            onclick={() => deployModel(model.id)}
                                        >
                                            <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                                            </svg>
                                            部署
                                        </button>
                                        <button
                                            class="inline-flex items-center px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-green-500 to-green-600 rounded-lg hover:from-green-600 hover:to-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-all duration-200 shadow-sm hover:shadow-md transform hover:-translate-y-0.5"
                                            onclick={() => generateConfig(model.id)}
                                        >
                                            <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                            </svg>
                                            生成配置
                                        </button>
                                        <button
                                            class="inline-flex items-center px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg hover:from-purple-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition-all duration-200 shadow-sm hover:shadow-md transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                                            onclick={() => manageConfig(model.id)}
                                            disabled={model.scan_status !== 'completed'}
                                            title={model.scan_status !== 'completed' ? '模型扫描完成后才能管理配置' : ''}
                                        >
                                            <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                            </svg>
                                            配置管理
                                        </button>
                                        <button
                                            class="inline-flex items-center px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-red-500 to-red-600 rounded-lg hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-all duration-200 shadow-sm hover:shadow-md transform hover:-translate-y-0.5"
                                            onclick={() => deleteModel(model.id)}
                                        >
                                            <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                            </svg>
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
    {/if}

    <!-- Pagination Controls -->
    {#if totalPages > 1}
        <div class="mt-6 flex justify-center items-center space-x-3">
            <button
                class="inline-flex items-center px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-all duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                onclick={() => { if (currentPage > 1) { currentPage -= 1; loadModels(); } }}
                disabled={currentPage === 1}
            >
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
                上一页
            </button>
            <span class="px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm">
                第 {currentPage} 页 / 共 {totalPages} 页
            </span>
            <button
                class="inline-flex items-center px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-all duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                onclick={() => { if (currentPage < totalPages) { currentPage += 1; loadModels(); } }}
                disabled={currentPage === totalPages}
            >
                下一页
                <svg class="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </button>
        </div>
    {/if}
</div>

<Modal 
    open={showCreateModal} 
    title="添加模型"
    confirmText="添加"
    cancelText="取消"
    onConfirm={createModel}
    onCancel={() => {
        showCreateModal = false;
        newModel = { name: '', hf_name: '', path: '' };
    }}
>
    <div class="space-y-5">
        <div>
            <label for="model-name" class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                模型名称
            </label>
            <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                </div>
                <input
                    type="text"
                    id="model-name"
                    bind:value={newModel.name}
                    placeholder="例如: my-model"
                    class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                />
            </div>
        </div>
        <div>
            <label for="hf-name" class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                HuggingFace 名称
            </label>
            <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path>
                    </svg>
                </div>
                <input
                    type="text"
                    id="hf-name"
                    bind:value={newModel.hf_name}
                    placeholder="例如: meta-llama/Llama-2-7b"
                    class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                />
            </div>
        </div>
        <div>
            <label for="model-path" class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                模型路径
            </label>
            <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                    </svg>
                </div>
                <input
                    type="text"
                    id="model-path"
                    bind:value={newModel.path}
                    placeholder="例如: /models/my-model"
                    class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                />
            </div>
        </div>
    </div>
</Modal>