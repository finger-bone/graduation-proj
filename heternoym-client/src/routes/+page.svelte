<script lang="ts">
    import HostCard from "$lib/components/HostCard.svelte";
	import Label from "$lib/components/Label.svelte";
    import Modal from "$lib/components/Modal.svelte";
    import TorchModelManager from "$lib/components/TorchModelManager.svelte";
    import { persistent } from "$lib/persist/persist";
    import { goto } from "$app/navigation";
	import { verifyPwd } from "$lib/api";

    const hosts = persistent<Array<string>>("hosts", []);
    let selectedHost = $state("");
    let selectedModelId = $state("");
    let showAddModal = $state(false);
    let showDeleteModal = $state(false);
    let newHost = $state("");
    let passwordDict = persistent<Record<string, string>>("passwordDict", {});

    // 新增分页和搜索状态
    let currentPage = $state(1);
    let itemsPerPage = $state(10);
    let totalItems = $derived($hosts.length);
    let totalPages = $derived(Math.ceil(totalItems / itemsPerPage));
    let searchQuery = $state("");

    // 添加密码状态
    let password = $state("");
    
    // Watch for changes in both selectedHost and selectedModelId
    $effect(() => {
        if (selectedHost && selectedModelId) {
            // Navigate to the new page with host and model ID
            goto(`/model/${encodeURIComponent(selectedHost)}/${selectedModelId}`);
        }
    });

    // 计算过滤后的宿主机列表
    const filteredHosts = $derived(
        $hosts.filter(host => !searchQuery || host.includes(searchQuery))
    );

    // 计算分页后的宿主机列表
    const paginatedHosts = $derived(
        filteredHosts.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );
</script>

<div class="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 sm:p-6">
    <div class="w-full">
        <!-- Header Section -->
        <div class="mb-8 bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div class="flex justify-between items-center">
                <div>
                    <h1 class="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                        宿主机管理
                    </h1>
                    <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        管理和监控您的远程宿主机
                    </p>
                </div>
                <div class="flex space-x-3">
                    <button 
                        class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5"
                        onclick={() => showAddModal = true}
                    >
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                        添加宿主机
                    </button>
                    <button 
                        class="inline-flex items-center px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-red-500 to-red-600 rounded-xl hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                        onclick={() => showDeleteModal = true}
                        disabled={!selectedHost}
                    >
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                        删除
                    </button>
                </div>
            </div>
        </div>

        <!-- Search Form -->
        <div class="mb-6">
            <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                </div>
                <input
                    type="text"
                    bind:value={searchQuery}
                    placeholder="搜索宿主机地址..."
                    class="w-full pl-11 pr-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 dark:text-white placeholder-slate-400"
                />
            </div>
        </div>

        <!-- Host Cards Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {#each paginatedHosts as host}
            <div class="transform transition-all duration-200 hover:scale-[1.02]">
                <HostCard remoteAddress={host} selected={selectedHost === host} onclick={() => {
                    if(selectedHost === host) {
                        selectedHost = "";
                    } else {
                        selectedHost = host;
                        // Reset model selection when host changes
                        selectedModelId = "";
                    }
                }} password={($passwordDict)[host]} onUpdatePassword={
                    async () => {
                        let newPwd = prompt(`修改 ${host} 的密码：`);
                        if (newPwd) {
                            if (!(await verifyPwd(host, newPwd))) {
                                alert("密码错误，密码未变更。");
                                return;
                            }
                            passwordDict.update(pwd => ({...pwd, [host]: newPwd}));
                        }
                    }
                }/>
            </div>
            {/each}
        </div>

        <!-- Model Manager Section -->
        {#if selectedHost}
            <div class="mt-8 bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <TorchModelManager 
                    remoteAddress={selectedHost} 
                    bind:selectedModelId
                    password={($passwordDict)[selectedHost]}
                />
            </div>
        {/if}

        <!-- Pagination Controls -->
        {#if totalPages > 1}
            <div class="mt-8 flex justify-center items-center space-x-3">
                <button
                    class="inline-flex items-center px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    onclick={() => { if (currentPage > 1) { currentPage -= 1; } }}
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
                    class="inline-flex items-center px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    onclick={() => { if (currentPage < totalPages) { currentPage += 1; } }}
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
</div>

<Modal 
    open={showAddModal} 
    title="添加宿主机"
    confirmText="添加"
    cancelText="不"
    onConfirm={async () => {
        if (newHost.trim() && password.trim()) {
            if (!(await verifyPwd(newHost.trim(), password))) {
                alert("密码错误或宿主机地址错误，请重新输入。");
                return;
            }
            hosts.update(h => [...h, newHost.trim()]);
            passwordDict.update(pwd => ({...pwd, [newHost.trim()]: password}));
            newHost = "";
            password = "";
            showAddModal = false;
        }
    }}
    onCancel={() => {
        newHost = "";
        password = "";
        showAddModal = false;
    }}
>
    <div class="space-y-5">
        <div>
            <label for="host-input" class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                宿主机地址
            </label>
            <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"></path>
                    </svg>
                </div>
                <input
                    type="text"
                    id="host-input"
                    bind:value={newHost}
                    placeholder="例如: 192.168.1.100:8000"
                    class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                />
            </div>
        </div>
        <div>
            <label for="password-input" class="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                密码
            </label>
            <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
                    </svg>
                </div>
                <input
                    type="password"
                    id="password-input"
                    bind:value={password}
                    placeholder="输入访问密码"
                    class="w-full pl-10 pr-4 py-2.5 border border-slate-300 dark:border-slate-600 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 dark:bg-slate-700 dark:text-white placeholder-slate-400"
                />
            </div>
        </div>
    </div>
</Modal>

<Modal 
    open={showDeleteModal} 
    title="确认删除"
    confirmText="删除"
    cancelText="不"
    onConfirm={() => {
        if (selectedHost) {
            hosts.update(h => h.filter(host => host !== selectedHost));
            passwordDict.update(pwd => {
                const {[selectedHost]: _, ...rest} = pwd;
                return rest;
            });
            selectedHost = "";
            selectedModelId = "";
            showDeleteModal = false;
        }
    }}
    onCancel={() => {
        showDeleteModal = false;
    }}
>
    <div class="flex items-start space-x-4">
        <div class="flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/30">
            <svg class="h-6 w-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>
        </div>
        <div class="flex-1">
            <p class="text-sm text-slate-600 dark:text-slate-300">
                您确定要删除以下宿主机吗？此操作不可恢复。
            </p>
            <div class="mt-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-200 dark:border-slate-600">
                <p class="text-sm font-mono font-semibold text-slate-900 dark:text-slate-100">
                    {selectedHost}
                </p>
            </div>
        </div>
    </div>
</Modal>