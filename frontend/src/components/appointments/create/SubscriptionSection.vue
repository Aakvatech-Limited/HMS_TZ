<template>
  <section class="flex flex-col gap-3 border-t border-gray-200 pt-5">
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="text-[15px] font-semibold text-gray-900">
          Insurance subscription
        </h3>
        <span
          v-if="form.subscription && form.card"
          class="rounded-full bg-blue-50 px-1.5 text-[10px] font-medium leading-4 text-blue-700"
        >
          loaded from card
        </span>
      </div>
      <TabButtons
        :buttons="SUBSCRIPTION_MODES"
        v-model="form.subscriptionMode"
      />
    </div>

    <div
      v-if="form.subscriptionMode === 'existing'"
      class="grid grid-cols-1 gap-4 sm:grid-cols-3"
    >
      <div>
        <FieldLabel label="Subscription" required />
        <Link
          :value="form.subscription?.name || ''"
          doctype="Healthcare Insurance Subscription"
          :filters="subscriptionFilters"
          placeholder="Subscription"
          @change="(value) => emit('select-subscription', value)"
        />
      </div>
      <div>
        <FieldLabel label="Insurance company" />
        <div class="readonly">
          {{ form.subscription?.insurance_company || "—" }}
        </div>
      </div>
      <div>
        <FieldLabel label="Coverage plan" />
        <div class="readonly">
          {{
            form.subscription?.coverage_plan_name ||
            form.subscription?.healthcare_insurance_coverage_plan ||
            "—"
          }}
        </div>
      </div>
    </div>

    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div>
        <FieldLabel label="Insurance company" required />
        <Link
          :value="form.newSubscription.insurance_company"
          doctype="Healthcare Insurance Company"
          placeholder="Insurance company"
          @change="(value) => (form.newSubscription.insurance_company = value)"
        />
      </div>
      <div>
        <FieldLabel
          label="Coverage plan"
          required
          :from-card="form.fromCard.healthcare_insurance_coverage_plan"
        />
        <Link
          :value="form.newSubscription.healthcare_insurance_coverage_plan"
          doctype="Healthcare Insurance Coverage Plan"
          :filters="planFilters"
          placeholder="Coverage plan"
          @change="
            (value) =>
              (form.newSubscription.healthcare_insurance_coverage_plan = value)
          "
        />
      </div>
      <div>
        <FieldLabel label="Card no" required />
        <FormControl
          v-model="form.newSubscription.coverage_plan_card_number"
          type="text"
          placeholder="Card no"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { TabButtons } from "frappe-ui";
import Link from "@/components/controls/Link.vue";
import FieldLabel from "./FieldLabel.vue";

const SUBSCRIPTION_MODES = [
  { label: "Use existing", value: "existing" },
  { label: "Create new", value: "new" },
];

const props = defineProps({ form: { type: Object, required: true } });
const emit = defineEmits(["select-subscription"]);

const subscriptionFilters = computed(() => ({
  docstatus: 1,
  is_active: 1,
  ...(props.form.patient ? { patient: props.form.patient } : {}),
}));

const planFilters = computed(() => ({
  is_active: 1,
  ...(props.form.newSubscription.insurance_company
    ? { insurance_company: props.form.newSubscription.insurance_company }
    : {}),
}));
</script>

<style scoped>
.readonly {
  @apply min-h-[28px] rounded border border-gray-200 bg-white px-2 py-1 text-sm text-gray-600;
}
</style>
