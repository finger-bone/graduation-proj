<script lang="ts">
    export let memoryTime: number = 0;
    export let computeTime: number = 0;
    export let selectedLayersCount: number = 0;
</script>

<div class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="p-4 bg-blue-50 dark:bg-blue-900 rounded-lg">
        <div class="text-sm font-medium text-blue-800 dark:text-blue-200">访存用时 (选中{selectedLayersCount}层)</div>
        <div class="mt-1 text-2xl font-bold text-blue-900 dark:text-white">
            {memoryTime.toFixed(2)} ns
        </div>
    </div>
    <div class="p-4 bg-green-50 dark:bg-green-900 rounded-lg">
        <div class="text-sm font-medium text-green-800 dark:text-green-200">计算用时 (选中模块)</div>
        <div class="mt-1 text-2xl font-bold text-green-900 dark:text-white">
            {computeTime.toFixed(2)} ns
        </div>
    </div>
</div>