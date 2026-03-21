<script lang="ts">
    import Icon from '@iconify/svelte';
    
    export let title: string = '暂无层信息';
    export let description: string = '无法从模型扫描结果中获取层信息';
</script>

<div class="text-center py-6">
    <Icon icon="mdi:file-document-outline" class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
    <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-white">{title}</h3>
    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        {description}
    </p>
</div>