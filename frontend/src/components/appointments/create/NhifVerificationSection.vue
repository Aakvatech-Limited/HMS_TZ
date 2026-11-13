<template>
  <section class="flex flex-col gap-3.5 border-t border-gray-200 pt-5">
    <div class="flex items-center gap-2">
      <h3 class="text-[15px] font-semibold text-gray-900">
        NHIF verification
      </h3>
      <Badge theme="blue" variant="subtle">NHIF only</Badge>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <span class="text-sm font-medium text-gray-600">Verify patient by:</span>
      <TabButtons
        :buttons="METHODS"
        v-model="form.verification.method"
        :disabled="Boolean(form.authorization)"
      />
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div>
        <FieldLabel label="Referral no" />
        <FormControl
          v-model="form.verification.referral_no"
          type="text"
          placeholder="If the visit type needs it"
        />
      </div>
      <div>
        <FieldLabel
          label="Remarks"
          :required="form.verification.method === 'NONE'"
        />
        <FormControl
          v-model="form.verification.remarks"
          type="text"
          placeholder="Required when method is None"
        />
      </div>
    </div>

    <div
      v-if="apiEnabled"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:items-end"
    >
      <div>
        <FieldLabel label="Authorization no" />
        <div
          class="min-h-[28px] rounded border border-gray-200 bg-white px-2 py-1 text-sm"
          :class="form.authorization ? 'text-gray-900' : 'text-gray-500'"
        >
          {{
            form.authorization?.authorization_number || "Not authorized yet"
          }}
        </div>
      </div>
      <Button
        variant="solid"
        :loading="authorizing"
        :disabled="authorizing || Boolean(form.authorization)"
        @click="emit('authorize')"
      >
        <template #prefix>
          <FeatherIcon name="shield" class="h-4 w-4" />
        </template>
        {{ form.authorization ? "Patient authorized" : "Authorize patient" }}
      </Button>
    </div>
    <div v-else>
      <FieldLabel label="Authorization no" />
      <FormControl
        v-model="form.verification.authorization_number"
        type="text"
        placeholder="Authorization no"
      />
    </div>

    <p v-if="apiEnabled" class="text-xs text-gray-500">
      Saves a new patient and subscription first, then captures the fingerprint
      or face and gets the authorization no from NHIF. Create appointment stays
      disabled until it is filled.
    </p>
  </section>
</template>

<script setup>
import { TabButtons } from "frappe-ui";
import FieldLabel from "./FieldLabel.vue";

const METHODS = [
  { label: "Fingerprint", value: "FINGERPRINT" },
  { label: "Facial", value: "FACIAL" },
  { label: "None", value: "NONE" },
];

defineProps({
  form: { type: Object, required: true },
  apiEnabled: { type: Boolean, default: false },
  authorizing: { type: Boolean, default: false },
});
const emit = defineEmits(["authorize"]);
</script>
