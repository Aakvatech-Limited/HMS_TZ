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
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-4 sm:items-end">
        <div v-if="isNhif">
          <FieldLabel label="Card type" required />
          <Select
            v-model="form.card_type"
            :options="cardTypeOptions"
            placeholder="Select"
          />
        </div>
        <div>
          <FieldLabel label="Card no" :from-card="cardNoSource" />
          <FormControl
            v-model="form.card_no"
            type="text"
            :placeholder="(isNhif && form.card_type) || 'Card no'"
          />
        </div>
        <Button
          v-if="canCheckCard"
          variant="subtle"
          :loading="checking"
          :disabled="checking || (isNhif && !form.card_type)"
          @click="emit('check-card')"
        >
          <template #prefix>
            <FeatherIcon name="refresh-cw" class="h-4 w-4" />
          </template>
          Check with {{ form.payment }}
        </Button>
        <div :class="searchSpan">
          <FieldLabel label="Or find an existing subscription" />
          <SubscriptionSearch
            :provider="form.payment"
            :selected="form.subscription"
            placeholder="Name, mobile, card no or ID"
            @select="(name) => emit('select-subscription', name)"
          />
        </div>
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
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { Select, TabButtons } from "frappe-ui";
import { getCardTypes, PAYMENT_OPTIONS } from "@/data/insurance";
import FieldLabel from "./FieldLabel.vue";
import SubscriptionSearch from "./SubscriptionSearch.vue";

const props = defineProps({
  form: { type: Object, required: true },
  isInsurance: { type: Boolean, default: false },
  isNhif: { type: Boolean, default: false },
  canCheckCard: { type: Boolean, default: false },
  checking: { type: Boolean, default: false },
});
const emit = defineEmits(["set-payment", "check-card", "select-subscription"]);

const SEARCH_SPANS = ["", "sm:col-span-3", "sm:col-span-2", "sm:col-span-1"];

const cardTypeOptions = ref([]);
onMounted(async () => {
  const names = await getCardTypes();
  cardTypeOptions.value = names.map((name) => ({ label: name, value: name }));
});

// The search fills the row after card type, card no and the check button.
const searchSpan = computed(
  () => SEARCH_SPANS[1 + Number(props.isNhif) + Number(props.canCheckCard)]
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
