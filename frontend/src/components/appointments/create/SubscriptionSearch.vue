<template>
  <Autocomplete
    :options="options"
    :model-value="selectedOption"
    :filterable="false"
    :placeholder="placeholder"
    @update:model-value="(option) => emit('select', option?.value || '')"
    @update:query="(text) => (query = text || '')"
  >
    <template #item-label="{ option }">
      <div class="flex min-w-0 flex-col">
        <span class="truncate font-medium text-gray-900">
          {{ option.patient_name || option.value }}
        </span>
        <span class="truncate text-sm text-gray-600">
          {{ option.details }}
        </span>
      </div>
    </template>
  </Autocomplete>
</template>

<script setup>
import { computed, ref } from "vue";
import { watchDebounced } from "@vueuse/core";
import Autocomplete from "@/components/controls/Autocomplete.vue";
import { searchSubscriptions } from "@/data/insurance";

const props = defineProps({
  provider: { type: String, default: "" },
  patient: { type: String, default: "" },
  selected: { type: Object, default: null },
  placeholder: {
    type: String,
    default: "Search by patient name, mobile, card no or subscription ID",
  },
});
const emit = defineEmits(["select"]);

const query = ref("");
const subscriptions = ref([]);

watchDebounced(
  () => [props.provider, props.patient, query.value],
  async () => {
    subscriptions.value = await searchSubscriptions(
      props.provider,
      query.value,
      props.patient
    );
  },
  { debounce: 300, immediate: true }
);

const coveragePlan = (subscription) =>
  subscription.coverage_plan_name ||
  subscription.healthcare_insurance_coverage_plan;

const toOption = (subscription) => ({
  label: `${subscription.name} · ${subscription.patient_name} · ${coveragePlan(
    subscription
  )}`,
  value: subscription.name,
  patient_name: subscription.patient_name,
  details: [
    subscription.name,
    subscription.gender,
    subscription.coverage_plan_card_number &&
      `Card: ${subscription.coverage_plan_card_number}`,
    coveragePlan(subscription) && `Coverage: ${coveragePlan(subscription)}`,
  ]
    .filter(Boolean)
    .join(" · "),
});

const options = computed(() => subscriptions.value.map(toOption));

const selectedOption = computed(() => {
  const name = props.selected?.name;
  if (!name) return null;
  return (
    options.value.find((option) => option.value === name) ||
    toOption(props.selected)
  );
});
</script>
