<template>
  <div class="w-full h-full">
    <div
      class="flex flex-col items-center p-3 bg-white border-2 border-gray-300 rounded-md hover:bg-blue-50 transition-colors w-full h-full overflow-hidden shadow-sm"
    >
      <!-- Avatar on top -->
      <div class="mb-1 flex-shrink-0">
        <Avatar
          :label="practitioner.avatar"
          :image="practitioner.image"
          size="sm"
          :class="
            practitioner.image
              ? 'ring-2 ring-green-400 !w-8 !h-8'
              : 'ring-2 ring-blue-400 !w-8 !h-8'
          "
        />
      </div>

      <!-- Practitioner Info -->
      <div class="text-center w-full flex-1 min-h-0">
        <h3
          class="text-xs font-bold text-gray-900 truncate mb-1 leading-tight"
          :title="practitioner.name"
        >
          {{ practitioner.name }}
        </h3>
        <p class="text-xs font-semibold text-gray-700 truncate leading-tight">
          {{ practitioner.department || "General" }}
        </p>
        <!-- <p class="text-xs font-semibold text-gray-700 truncate leading-tight">
          {{ practitioner.billing_item }}
        </p> -->
      </div>
    </div>
  </div>
</template>

<script setup>
import { Avatar, Badge } from "frappe-ui";

const props = defineProps({
  practitioner: {
    type: Object,
    required: true,
  },
});
</script>
