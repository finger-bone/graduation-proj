<script lang="ts">
	import { onMount, type Snippet } from 'svelte';
	import Icon from '@iconify/svelte';
	import { createApiService } from '../api';

	// Props
	let { 
		remoteAddress,
		selected,
		onclick = ()=>{},
		password,
		onUpdatePassword = ()=>{},
		showCheckbox = false,
		checked = false,
		onToggleCheckbox = undefined,
	}: { 
		remoteAddress: string, 
		selected: boolean,
		onclick: () => void,
		password: string,
		onUpdatePassword: () => void,
		showCheckbox?: boolean,
		checked?: boolean,
		onToggleCheckbox?: (host: string) => void,
	} = $props();
	// State management using runes
	let status = $state<'online' | 'offline' | 'checking'>('checking');
	
	// Create API service for this remote address
	let apiService = createApiService(remoteAddress, password);

	// Check status with actual API ping
	async function checkStatus() {
		status = 'checking';
		try {
			// Ping the server
			const response = await apiService.ping();
			console.log(response);
			// If successful, mark as online
			status = response === 'pong' ? 'online' : 'offline';
		} catch (error) {
			// If there's an error, mark as offline
			console.error('Ping failed:', error);
			status = 'offline';
		}
	}

	onMount(() => {
		checkStatus();
	});
</script>

<button
	class="p-4 rounded-lg shadow-lg transition-all duration-300 min-h-[100px] flex flex-col justify-between {selected ? 'ring-1 ring-blue-500' : 'ring-1 ring-gray-300'} bg-white dark:bg-gray-800 w-full" onclick={onclick}
>
	<div class="flex items-start gap-3">
		<div class="p-2 rounded-full bg-gray-100 dark:bg-gray-700">
			<Icon icon="mdi:server" class="w-5 h-5 text-gray-600 dark:text-gray-300" />
		</div>
		<div>
			<h1 class="text-gray-600 dark:text-gray-300 text-lg mt-1">{remoteAddress}</h1>
		</div>
	</div>

	<div class="mt-4 flex items-center justify-between">
		<div class="flex items-center gap-2">
			{#if status === 'online'}
				<Icon icon="mdi:check-circle" class="w-4 h-4 text-green-500" />
				<span class="font-medium text-green-600 dark:text-green-400 text-sm">Online</span>
			{:else if status === 'offline'}
				<Icon icon="mdi:close-circle" class="w-4 h-4 text-red-500" />
				<span class="font-medium text-red-600 dark:text-red-400 text-sm">Offline</span>
			{:else}
				<Icon icon="mdi:clock-outline" class="w-4 h-4 text-yellow-500" />
				<span class="font-medium text-yellow-600 dark:text-yellow-400 text-sm">Checking...</span>
			{/if}
		</div>
	</div>

	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div 
		class="px-3 py-1.5 text-sm font-medium text-white bg-yellow-600 rounded-lg hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2 transition-colors mt-2 w-full"
		onclick={() => {onUpdatePassword()}}
		role="button"
		tabindex="0"
	>
		修改客户端密码
	</div>
</button>