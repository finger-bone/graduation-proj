<script lang="ts">
    import { page } from '$app/state';
    import { createApiService } from '$lib/api';
    import Icon from '@iconify/svelte';
    import { onMount } from 'svelte';
    import Step1ModelInfo from './Step1ModelInfo.svelte';
    import Step2ScanResults from './Step2ScanResults.svelte';
    import Step3LayerSelection from './Step3LayerSelection.svelte';
    import Step4EffectPreview from './Step4EffectPreview.svelte';
	import { persistent } from '$lib/persist/persist';
	import { derived } from 'svelte/store';

    let host = $state('');
    let modelId = $state('');
    let model = $state<{id: string, name: string, hf_name: string, path: string, scan_status: string, scan_results: Record<string, any>} | null>(null);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let apiService: ReturnType<typeof createApiService> | null = $state(null);
    
    // Current step in the wizard
    let currentStep = $state(1);
    
    // Selected config ID from step 4
    let selectedConfig = $state<number | null>(null);
    let passwordDict = persistent<Record<string, string>>('passwordDict', {})
    let password = $derived(() => {
        return $passwordDict[host]
    });
    onMount(async () => {
        // Get host and modelId from URL params
        host = window.decodeURIComponent(page.params.host || '');
        modelId = page.params.modelId || '';
        
        // Create API service for the host with password
        apiService = createApiService(host, ($passwordDict)[host]);
        
        // Load model details
        await loadModel();
    });

    async function loadModel() {
        if (!apiService) return;
        
        try {
            loading = true;
            error = null;
            model = await apiService.getById(modelId);
        } catch (err: any) {
            error = err.message || 'Failed to load model';
            console.error('Error loading model:', err);
        } finally {
            loading = false;
        }
    }

    function moveToNextStep() {
        if (currentStep < 4) {  // 改为4，因为移除了步骤5
            currentStep++;
        } else {
            // 如果在步骤4，完成流程回到步骤1
            currentStep = 1;
        }
    }

    function moveToPrevStep() {
        if (currentStep > 1) {
            currentStep--;
        }
    }

    function handleFinish() {
        // 返回主页
        window.location.href = '/';
    }

    function handleScanComplete() {
        // Refresh model data and move to next step
        loadModel().then(() => {
            currentStep = 2;
        });
    }
</script>

<div class="p-4 w-full">
    <div class="mb-6">
        <a href="/" class="inline-flex items-center text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
            <Icon icon="mdi:arrow-left" class="w-5 h-5 mr-1" />
            返回主页
        </a>
    </div>

    <!-- Step progress indicator -->
    <div class="mb-8">
        <div class="flex justify-between relative">
            <!-- Progress line -->
            <div class="absolute top-4 left-0 right-0 h-0.5 bg-gray-200 dark:bg-gray-700 -z-10"></div>
            <div class="absolute top-4 left-0 h-0.5 bg-blue-500 -z-10" style={`width: ${(currentStep-1)*33.33}%`}></div>
            
            {#each [1, 2, 3, 4] as step}
                <div class="flex flex-col items-center">
                    <div class={`w-8 h-8 rounded-full flex items-center justify-center ${
                        step <= currentStep 
                            ? 'bg-blue-500 text-white' 
                            : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                    }`}>
                        {step}
                    </div>
                    <div class="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                        {#if step === 1}模型信息{/if}
                        {#if step === 2}扫描结果{/if}
                        {#if step === 3}层选择{/if}
                        {#if step === 4}效果预览{/if}
                    </div>
                </div>
            {/each}
        </div>
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
        {#if currentStep === 1}
            <Step1ModelInfo {model} {host} {modelId} onNext={handleScanComplete} password={password()}/>
        {:else if currentStep === 2}
            <Step2ScanResults {model} {host} {modelId} onPrev={moveToPrevStep} onNext={moveToNextStep} />
        {:else if currentStep === 3}
            <Step3LayerSelection {model} {host} {modelId} onPrev={moveToPrevStep} onNext={moveToNextStep} password={password()} />
        {:else if currentStep === 4}
            <Step4EffectPreview 
                model={model} 
                host={host} 
                modelId={modelId} 
                onPrev={moveToPrevStep} 
                onNext={handleFinish}
                bind:selectedConfig
                password={password()}
            />
        {/if}
    {/if}
</div>