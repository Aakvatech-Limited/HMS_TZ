<template>
  <div
    class="appointment-card cursor-pointer transition-colors duration-200 w-full h-full overflow-hidden rounded-md border border-dotted shadow-sm group"
    :class="statusStyle.card"
  >
    <div class="p-1 h-full flex flex-col">
      <!-- Patient Name -->
      <div class="flex-shrink-0 mb-1">
        <h4
          class="text-xs font-bold leading-tight truncate"
          :class="statusStyle.text"
          :title="appointment.patient_name"
        >
          {{ appointment.patient_name || "Unknown Patient" }}
        </h4>
      </div>

      <!-- Compact Info Section -->
      <div class="flex flex-col space-y-0.5">
        <!-- Insurance Company -->
        <div class="flex items-start flex-shrink-0" :class="statusStyle.text">
          <FeatherIcon
            name="shield"
            class="h-2 w-2 mr-1 flex-shrink-0 mt-0.5"
          />
          <span
            class="text-2xs font-semibold leading-tight truncate"
            style="font-size: 10px"
            :title="appointment.insurance_company"
            >{{ appointment.insurance_company || "Cash" }}</span
          >
        </div>

        <!-- Billing Item -->
        <div
          v-if="appointment.billing_item"
          class="flex items-start flex-shrink-0"
          :class="statusStyle.text"
        >
          <FeatherIcon
            name="file-text"
            class="h-2 w-2 mr-1 flex-shrink-0 mt-0.5"
          />
          <span
            class="text-2xs font-semibold leading-tight truncate"
            style="font-size: 10px"
            :title="appointment.billing_item"
            >{{ appointment.billing_item }}</span
          >
        </div>

        <!-- Paid Amount / Item Rate -->
        <div class="flex items-start flex-shrink-0" :class="statusStyle.text">
          <FeatherIcon
            name="dollar-sign"
            class="h-2 w-2 mr-1 flex-shrink-0 mt-0.5"
          />
          <span
            class="text-2xs font-semibold leading-tight"
            style="font-size: 10px"
            >{{
              formatAmount(
                appointment.paid_amount || appointment.item_rate || 0
              )
            }}</span
          >
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { FeatherIcon } from "frappe-ui";
import { getStatusStyle } from "./appointmentStatus";

const props = defineProps({
  appointment: {
    type: Object,
    required: true,
  },
});

const statusStyle = computed(() => getStatusStyle(props.appointment.status));

const formatAmount = (amount) => {
  if (!amount || amount === 0) return "TZS 0";
  return `TZS ${Number(amount).toLocaleString()}`;
};
</script>

<style scoped>
.appointment-card {
  min-height: 100%;
}

@media (prefers-contrast: high) {
  .appointment-card {
    border: 2px solid;
  }
}
</style>
