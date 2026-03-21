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
    let totalItems = $state($hosts.length);
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

<div>
    <div class="mb-4 flex justify-between items-center">
        <Label>宿主机</Label>
        <div class="space-x-2">
            <button 
                class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                onclick={() => showAddModal = true}
            >
                添加宿主机
            </button>
            <button 
                class="px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                onclick={() => showDeleteModal = true}
                disabled={!selectedHost}
            >
                删除宿主机
            </button>
        </div>
    </div>

    <!-- Search Form -->
    <form onsubmit={() => { currentPage = 1; }} class="mb-4">
        <input
            type="text"
            bind:value={searchQuery}
            placeholder="搜索宿主机地址"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
    </form>

    <div class="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each paginatedHosts as host}
        <div>
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

    {#if selectedHost}
        <TorchModelManager 
            remoteAddress={selectedHost} 
            bind:selectedModelId
            password={($passwordDict)[selectedHost]}
        />
    {/if}

    <!-- Pagination Controls -->
    {#if totalPages > 1}
        <div class="mt-6 flex justify-center space-x-2">
            <button
                class="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                onclick={() => { if (currentPage > 1) { currentPage -= 1; } }}
                disabled={currentPage === 1}
            >
                上一页
            </button>
            <span class="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-200 rounded-md">
                第 {currentPage} 页 / 共 {totalPages} 页
            </span>
            <button
                class="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                onclick={() => { if (currentPage < totalPages) { currentPage += 1; } }}
                disabled={currentPage === totalPages}
            >
                下一页
            </button>
        </div>
    {/if}
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
    <div class="mb-4">
        <label for="host-input" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            宿主机地址
        </label>
        <input
            type="text"
            id="host-input"
            bind:value={newHost}
            placeholder="输入宿主机地址"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
    </div>
    <div class="mb-4">
        <label for="password-input" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            密码
        </label>
        <input
            type="password"
            id="password-input"
            bind:value={password}
            placeholder="输入密码"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
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
    <p class="text-gray-600 dark:text-gray-300">
        确认删除宿主机 <span class="font-semibold">{selectedHost}</span>？
    </p>
</Modal>