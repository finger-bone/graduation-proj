<script lang="ts">
    import { createApiService } from '$lib/api';
    import Icon from '@iconify/svelte';
    import { onMount, onDestroy } from 'svelte';

    let { model, host, password }: { 
        model: {id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null, 
        host: string,
        password: string // 新增 password 属性
    } = $props();

    let queueSize = $state<number | null>(null);
    let orderInQueue = $state<number | null>(null);
    let loading = $state(false);
    let error = $state<string | null>(null);
    let pollingInterval: number | null = $state(null);
    let apiService: ReturnType<typeof createApiService> | null = $state(null);

    $effect(() => {
        if (host && password) { // 检查 host 和 password 是否存在
            apiService = createApiService(host, password); // 传入 password 参数
        }
    });

    onMount(() => {
        startPolling();
    });

    onDestroy(() => {
        stopPolling();
    });

    function startPolling() {
        // 只有当模型状态不是ready或completed时才进行轮询
        if (model?.scan_status !== 'ready' && model?.scan_status !== 'completed') {
            pollQueueInfo();
            pollingInterval = window.setInterval(pollQueueInfo, 3000); // 每3秒轮询一次
        }
    }

    function stopPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    async function pollQueueInfo() {
        if (!apiService || !model) return;

        try {
            loading = true;
            error = null;
            
            // 获取队列大小
            const queueResponse = await apiService.getQueueSize();
            queueSize = queueResponse.queue_size;
            
            // 获取当前模型在队列中的位置
            const orderResponse = await apiService.getOrderInQueue(model.id);
            orderInQueue = orderResponse.order_in_queue;
            
            // 同时更新模型状态
            const updatedModel = await apiService.getById(model.id);
            // 这里我们不能直接修改传入的model属性，但可以在UI上反映最新状态
            // 如果状态变为completed，则停止轮询
            if (updatedModel.scan_status === 'completed') {
                stopPolling();
            }
        } catch (err: any) {
            error = err.message || '获取队列信息失败';
            console.error('Error polling queue info:', err);
        } finally {
            loading = false;
        }
    }
</script>

<div class="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
    <div class="flex items-center justify-between">
        <h3 class="text-lg font-medium text-blue-900 dark:text-blue-100 flex items-center">
            <Icon icon="mdi:queue" class="w-5 h-5 mr-2" />
            队列状态
        </h3>
        <button 
            class="text-sm px-3 py-1 bg-blue-100 hover:bg-blue-200 dark:bg-blue-800/30 dark:hover:bg-blue-800/50 text-blue-800 dark:text-blue-200 rounded"
            onclick={pollQueueInfo}
            disabled={loading}
        >
            {#if loading}
                <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
            {:else}
                <Icon icon="mdi:refresh" class="w-4 h-4" />
            {/if}
        </button>
    </div>

    {#if error}
        <div class="mt-2 text-sm text-red-700 dark:text-red-300">
            {error}
        </div>
    {/if}

    <div class="mt-3 grid grid-cols-2 gap-4">
        <div class="bg-white dark:bg-gray-800 p-3 rounded border border-gray-200 dark:border-gray-700">
            <div class="text-sm text-gray-500 dark:text-gray-400">队列大小</div>
            <div class="text-xl font-semibold text-gray-900 dark:text-white">
                {#if queueSize !== null}
                    {queueSize}
                {:else}
                    --
                {/if}
            </div>
        </div>
        <div class="bg-white dark:bg-gray-800 p-3 rounded border border-gray-200 dark:border-gray-700">
            <div class="text-sm text-gray-500 dark:text-gray-400">您的位置</div>
            <div class="text-xl font-semibold text-gray-900 dark:text-white">
                {#if orderInQueue !== null}
                    {orderInQueue}
                {:else}
                    --
                {/if}
            </div>
        </div>
    </div>

    <div class="mt-3 text-xs text-blue-700 dark:text-blue-300">
        {#if model?.scan_status === 'ready'}
            模型尚未提交扫描任务
        {:else if model?.scan_status === 'completed'}
            扫描已完成，无需查询队列信息
        {:else if pollingInterval}
            正在轮询队列信息...
        {:else}
            轮询已停止
        {/if}
    </div>
</div>