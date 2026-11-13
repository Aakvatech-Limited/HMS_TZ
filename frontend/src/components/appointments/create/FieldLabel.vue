<template>
  <div
    class="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-gray-600"
  >
    <span>{{ label }}</span>
    <span v-if="required" class="text-red-500">*</span>
    <span
      v-if="fromCard"
      class="rounded-full bg-blue-50 px-1.5 text-[10px] font-medium leading-4 text-blue-700"
    >
      {{ fromCard === true ? "from card" : fromCard }}
    </span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  required: { type: Boolean, default: false },
  fromCard: { type: [Boolean, String], default: false },
});
</script>
