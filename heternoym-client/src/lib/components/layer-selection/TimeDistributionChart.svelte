<script lang="ts">
    // export let memoryTime: number = 0;
    // export let computeTime: number = 0;
    let {
        memoryTime,
        computeTime,
    } : {
        memoryTime: number,
        computeTime: number,
    } = $props();
    
    function getSingleArcLength(time: number, total: number): string {
        if (total === 0) return "0, 283"; // 283 is approx circumference of circle with radius 45
        
        const percent = (time / total) * 100;
        const arcLength = (percent / 100) * 283; // 283 is approx circumference
        return `${arcLength}, 283`;
    }
</script>

<div class="mb-6 flex justify-center">
    <div class="relative w-48 h-48">
        <svg class="w-full h-full" viewBox="0 0 100 100">
            <!-- Background circle -->
            <circle
                cx="50"
                cy="50"
                r="45"
                fill="none"
                stroke="#e5e7eb"
                stroke-width="8"
                class="dark:stroke-gray-600"
            />
            <!-- Inner circle for memory time -->
            <circle
                cx="50"
                cy="50"
                r="35"
                fill="none"
                stroke="#3b82f6"
                stroke-width="8"
                stroke-dasharray={getSingleArcLength(memoryTime, Math.max(memoryTime, computeTime))}
                stroke-dashoffset="0"
                stroke-linecap="round"
                transform="rotate(-90 50 50)"
            />
            <!-- Outer circle for compute time -->
            <circle
                cx="50"
                cy="50"
                r="45"
                fill="none"
                stroke="#10b981"
                stroke-width="8"
                stroke-dasharray={getSingleArcLength(computeTime, Math.max(memoryTime, computeTime))}
                stroke-dashoffset="0"
                stroke-linecap="round"
                transform="rotate(-90 50 50)"
            />
        </svg>
    </div>
</div>