<template>
  <section class="mb-5 flex flex-col gap-3">
    <h3 class="text-[15px] font-semibold text-gray-900">Payment</h3>
    <div class="flex w-fit gap-0.5 rounded-lg bg-gray-100 p-0.5">
      <span
        v-for="option in PAYMENT_OPTIONS"
        :key="option.value"
        class="flex items-center gap-1 rounded-md px-3 py-1 text-sm"
        :class="
          option.value === payment
            ? 'bg-blue-50 font-semibold text-blue-700 shadow ring-1 ring-outline-gray-5'
            : 'text-gray-500'
        "
        :aria-current="option.value === payment || undefined"
      >
        <FeatherIcon
          v-if="option.value === payment"
          name="check"
          class="h-3.5 w-3.5"
        />
        {{ option.label }}
      </span>
    </div>
  </section>
</template>

<script setup>
import { PAYMENT_OPTIONS } from "@/data/insurance";

/** Read-only payment choice of a saved appointment, shown like the create-mode tabs. */
defineProps({ payment: { type: String, required: true } });
</script>
