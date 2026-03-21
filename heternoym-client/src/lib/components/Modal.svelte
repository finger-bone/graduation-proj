<script lang="ts">
  import type { Snippet } from 'svelte';

  let { 
    open,
    title = '',
    onConfirm = () => {},
    onCancel = () => {},
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    children
  } = $props<{
    open: boolean;
    title?: string;
    onConfirm?: () => void;
    onCancel?: () => void;
    confirmText?: string;
    cancelText?: string;
    children: Snippet;
  }>();
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <!-- Backdrop -->
    <div 
      class="fixed inset-0 bg-black bg-opacity-50" 
      onclick={onCancel}
      onkeydown={(e) => {
        if (e.key === 'Escape') {
          onCancel();
        }
      }}
      role="button"
      tabindex="0"
      aria-label="关闭"
    ></div>
    
    <!-- Modal -->
    <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md z-10 mx-4">
      <div class="p-6">
        {#if title}
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {title}
          </h3>
        {/if}
        
        <div class="mb-6">
          {@render children()}
        </div>
        
        <div class="flex justify-end space-x-3">
          <button 
            type="button" 
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white dark:border-gray-600 dark:hover:bg-gray-600"
            onclick={onCancel}
          >
            {cancelText}
          </button>
          <button 
            type="button" 
            class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            onclick={onConfirm}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}