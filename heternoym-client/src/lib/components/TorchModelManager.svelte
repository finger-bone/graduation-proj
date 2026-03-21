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

    function manageConfig(modelId: string) {
        // Navigate to the dedicated configuration management page
        goto(`/model/${encodeURIComponent(remoteAddress)}/${modelId}/configs`);
    }
</script>

<div class="mt-6">
    <div class="mb-4 flex justify-between items-center">
        <Label>Torch Models</Label>
        <div class="space-x-2">
            <button 
                class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                onclick={() => showCreateModal = true}
            >
                添加模型
            </button>
            <button 
                class="px-3 py-1.5 text-sm font-medium text-white bg-gray-600 rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
                onclick={() => loadModels()}
                disabled={loading}
            >
                {loading ? '刷新中...' : '刷新'}
            </button>
        </div>
    </div>

    <!-- Search Form -->
    <form onsubmit={() => handleSearch({ hf_name: searchFilters.hf_name, name: searchFilters.name, scan_status: searchFilters.scan_status })} class="mb-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
                type="text"
                bind:value={searchFilters.hf_name}
                placeholder="HuggingFace 名称"
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
            <input
                type="text"
                bind:value={searchFilters.name}
                placeholder="模型名称"
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
            <select bind:value={searchFilters.scan_status} class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white">
                <option value={null}>所有状态</option>
                <option value="pending">待处理</option>
                <option value="scanning">扫描中</option>
                <option value="completed">已完成</option>
            </select>
        </div>
        <div class="flex justify-end mt-4">
            <button type="submit" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors">
                搜索
            </button>
        </div>
    </form>

    {#if error}
        <div class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            错误: {error}
        </div>
    {/if}

    {#if loading}
        <div class="flex justify-center items-center py-8">
            <Icon icon="mdi:loading" class="w-6 h-6 text-blue-500 animate-spin" />
            <span class="ml-2 text-gray-600">加载中...</span>
        </div>
    {:else}
        {#if models.length === 0}
            <div class="py-8 text-center text-gray-500">
                暂无模型数据
            </div>
        {:else}
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {#each models as model (model.id)}
                    <div 
                        class="p-4 rounded-lg shadow-lg bg-white dark:bg-gray-800 cursor-pointer transition-all duration-200
                               {selectedModelId === model.id 
                                   ? 'ring-2 ring-blue-500' 
                                   : 'ring-1 ring-gray-300 hover:ring-blue-300'}"
                        role="button"
                        tabindex="0"
                        onclick={() => selectModel(model.id)}
                        onkeydown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                                selectModel(model.id);
                            }
                        }}
                    >
                        <div class="flex items-start justify-between">
                            <div>
                                <h3 class="font-medium text-gray-900 dark:text-white">{model.name}</h3>
                                <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{model.hf_name}</p>
                                <p class="text-xs text-gray-400 dark:text-gray-500 mt-2 truncate">{model.path}</p>
                            </div>
                            <div class="flex items-center">
                                {#if model.scan_status === 'pending'}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                        待处理
                                    </span>
                                {:else if model.scan_status === 'scanning'}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                        扫描中
                                    </span>
                                {:else if model.scan_status === 'completed'}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                        已完成
                                    </span>
                                {:else}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                        {model.scan_status}
                                    </span>
                                {/if}
                            </div>
                        </div>
                        <div class="mt-4 flex justify-end space-x-2">
                            <button
                                class="px-3 py-1 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    deployModel(model.id);
                                }}
                            >
                                部署
                            </button>
                        </div>
                        <div class="mt-4 flex justify-end space-x-2">
                            <button
                                class="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    deleteModel(model.id);
                                }}
                            >
                                删除
                            </button>
                        </div>
                    </div>
                {/each}
            </div>
        {/if}
    {/if}

    <!-- Pagination Controls -->
    {#if totalPages > 1}
        <div class="mt-6 flex justify-center space-x-2">
            <button
                class="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                onclick={() => { if (currentPage > 1) { currentPage -= 1; loadModels(); } }}
                disabled={currentPage === 1}
            >
                上一页
            </button>
            <span class="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-200 rounded-md">
                第 {currentPage} 页 / 共 {totalPages} 页
            </span>
            <button
                class="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                onclick={() => { if (currentPage < totalPages) { currentPage += 1; loadModels(); } }}
                disabled={currentPage === totalPages}
            >
                下一页
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
    <div class="space-y-4">
        <div>
            <label for="model-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                模型名称
            </label>
            <input
                type="text"
                id="model-name"
                bind:value={newModel.name}
                placeholder="输入模型名称"
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
        </div>
        <div>
            <label for="hf-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                HuggingFace 名称
            </label>
            <input
                type="text"
                id="hf-name"
                bind:value={newModel.hf_name}
                placeholder="输入 HuggingFace 名称"
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
        </div>
        <div>
            <label for="model-path" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                模型路径
            </label>
            <input
                type="text"
                id="model-path"
                bind:value={newModel.path}
                placeholder="输入模型路径"
                class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
        </div>
    </div>
</Modal>