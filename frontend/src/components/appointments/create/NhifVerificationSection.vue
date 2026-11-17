<template>
  <section class="flex flex-col gap-3 border-t border-gray-200 pt-5">
    <h3 class="text-[15px] font-semibold text-gray-900">Verification</h3>

    <div
      class="grid grid-cols-1 gap-4 sm:grid-cols-[auto_1fr_1fr] sm:items-end"
    >
      <div class="sm:mr-24">
        <FieldLabel label="Verify patient by" />
        <TabButtons
          :buttons="METHODS"
          v-model="form.verification.method"
          :disabled="Boolean(form.authorization)"
        />
      </div>
      <div>
        <FieldLabel label="Referral no" />
        <FormControl
          v-model="form.verification.referral_no"
          type="text"
          placeholder="If the visit type needs it"
        />
      </div>
      <div>
        <FieldLabel label="Authorization no" />
        <FormControl
          v-model="form.verification.authorization_number"
          type="text"
          placeholder="Authorization no"
        />
      </div>
    </div>

    <div>
      <FieldLabel
        label="Remarks"
        :required="form.verification.method === 'NONE'"
      />
      <FormControl
        v-model="form.verification.remarks"
        type="textarea"
        placeholder="Required when method is None"
      />
    </div>

    <div v-if="apiEnabled" class="flex justify-end">
      <Button
        variant="solid"
        :loading="authorizing"
        :disabled="authorizing || !canAuthorize"
        title="Needs the visit type, the patient and the subscription, and an empty authorization no. Saves a new patient and subscription first, then captures the fingerprint or face and gets the authorization no from NHIF. Create appointment stays disabled until it is filled."
        @click="emit('authorize')"
      >
        <template #prefix>
          <FeatherIcon name="shield" class="h-4 w-4" />
        </template>
        Authorize patient
      </Button>
    </div>
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
  canAuthorize: { type: Boolean, default: false },
});
const emit = defineEmits(["authorize"]);
</script>
