<script lang="ts">
  import type { Snippet } from 'svelte';
  
  let { 
    variant = 'primary',
    size = 'md',
    rounded = false,
    children 
  } = $props<{
    variant?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
    size?: 'sm' | 'md' | 'lg';
    rounded?: boolean;
    children: Snippet;
  }>();

  const variantClasses = $derived({
    primary: 'bg-blue-100 text-blue-800 border-blue-200',
    secondary: 'bg-gray-100 text-gray-800 border-gray-200',
    success: 'bg-green-100 text-green-800 border-green-200',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    error: 'bg-red-100 text-red-800 border-red-200',
    info: 'bg-indigo-100 text-indigo-800 border-indigo-200'
  });
  
  const sizeClasses = $derived({
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5'
  });
  
  const classes = $derived(`inline-flex items-center font-medium border ${variantClasses[variant as keyof typeof variantClasses]} ${sizeClasses[size as keyof typeof sizeClasses]} ${rounded ? 'rounded-full' : 'rounded'}`);
</script>

<span class={classes}>
  {@render children()}
</span>