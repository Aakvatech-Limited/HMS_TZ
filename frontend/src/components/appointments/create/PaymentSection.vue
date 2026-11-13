<template>
  <section class="flex flex-col gap-3">
    <h3 class="text-[15px] font-semibold text-gray-900">Payment</h3>
    <TabButtons
      class="w-fit"
      :buttons="PAYMENT_OPTIONS"
      :model-value="form.payment"
      @update:model-value="emit('set-payment', $event)"
    />

    <template v-if="isInsurance">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:items-end">
        <div>
          <FieldLabel label="Card no" :from-card="cardNoSource" />
          <FormControl
            v-model="form.card_no"
            type="text"
            placeholder="Card no"
          />
        </div>
        <div v-if="form.payment === 'NHIF'">
          <FieldLabel label="National ID" />
          <FormControl
            v-model="form.national_id"
            type="text"
            placeholder="20-digit NIDA number"
          />
        </div>
        <Button
          v-if="canCheckCard"
          variant="subtle"
          :loading="checking"
          :disabled="checking"
          @click="emit('check-card')"
        >
          <template #prefix>
            <FeatherIcon name="refresh-cw" class="h-4 w-4" />
          </template>
          Check with {{ form.payment }}
        </Button>
      </div>

      <div
        v-if="form.cardStatus"
        role="status"
        class="flex gap-2.5 rounded-lg p-3 text-sm"
        :class="statusClasses"
      >
        <FeatherIcon
          :name="form.cardStatus.tone === 'success' ? 'check' : 'info'"
          class="mt-0.5 h-4 w-4 flex-none"
        />
        <div class="flex flex-col gap-0.5">
          <strong class="font-semibold">{{ form.cardStatus.title }}</strong>
          <span>{{ form.cardStatus.text }}</span>
        </div>
      </div>

      <div>
        <FieldLabel label="Or find an existing subscription" />
        <Autocomplete
          :options="subscriptionOptions"
          :model-value="selectedOption"
          :filterable="false"
          placeholder="Search by patient name, mobile, card no or subscription ID"
          @update:model-value="
            (option) => emit('select-subscription', option?.value || '')
          "
          @update:query="searchSubscriptions"
        />
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { TabButtons } from "frappe-ui";
import { watchDebounced } from "@vueuse/core";
import Autocomplete from "@/components/controls/Autocomplete.vue";
import {
  PAYMENT_OPTIONS,
  searchSubscriptions as searchApi,
} from "@/data/insurance";
import FieldLabel from "./FieldLabel.vue";

const props = defineProps({
  form: { type: Object, required: true },
  isInsurance: { type: Boolean, default: false },
  canCheckCard: { type: Boolean, default: false },
  checking: { type: Boolean, default: false },
});
const emit = defineEmits(["set-payment", "check-card", "select-subscription"]);

const query = ref("");
const subscriptions = ref([]);

const searchSubscriptions = (text) => {
  query.value = text || "";
};

watchDebounced(
  () => [props.form.payment, query.value],
  async () => {
    if (!props.isInsurance) return;
    subscriptions.value = await searchApi(props.form.payment, query.value);
  },
  { debounce: 300, immediate: true }
);

const subscriptionOptions = computed(() =>
  subscriptions.value.map((subscription) => ({
    label: `${subscription.name} · ${subscription.patient_name} · ${
      subscription.coverage_plan_name ||
      subscription.healthcare_insurance_coverage_plan
    }`,
    value: subscription.name,
  }))
);

const selectedOption = computed(
  () =>
    subscriptionOptions.value.find(
      (option) => option.value === props.form.subscription?.name
    ) ||
    (props.form.subscription
      ? {
          label: props.form.subscription.name,
          value: props.form.subscription.name,
        }
      : null)
);

const cardNoSource = computed(() => {
  if (props.form.fromCard.patient && props.form.card)
    return `from ${props.form.payment}`;
  if (props.form.subscription && !props.form.card) return "from subscription";
  return false;
});

const statusClasses = computed(() =>
  props.form.cardStatus?.tone === "success"
    ? "bg-green-50 text-green-900"
    : "bg-blue-50 text-blue-900"
);
</script>
