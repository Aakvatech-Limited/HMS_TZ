<template>
  <div class="flex flex-col gap-3">
    <ProviderReplyPanel
      v-if="providerReply"
      :reply="providerReply"
      @close="providerReply = null"
    />

    <NhifVerificationSection
      v-if="isNhif"
      :form="form"
      :api-enabled="settings.enable_nhif_api"
      :authorizing="busy"
      :can-authorize="!form.verification.authorization_number"
      @authorize="run(authorizeNhif)"
    />

    <section v-else class="flex flex-col gap-3 border-t border-gray-200 pt-5">
      <h3 class="text-[15px] font-semibold text-gray-900">Authorization</h3>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:items-end">
        <div>
          <FieldLabel
            label="Referral no"
            :required="Boolean(form.visitType.requires_referral_no)"
          />
          <FormControl
            v-model="form.verification.referral_no"
            type="text"
            placeholder="Referral no"
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
          :required="Boolean(form.visitType.requires_remarks)"
        />
        <FormControl v-model="form.verification.remarks" type="textarea" />
      </div>
      <div v-if="isJubileeApi" class="flex justify-end">
        <Button
          variant="solid"
          :loading="busy"
          :disabled="busy || Boolean(form.verification.authorization_number)"
          @click="run(authorizeJubilee)"
        >
          <template #prefix>
            <FeatherIcon name="shield" class="h-4 w-4" />
          </template>
          Authorize
        </Button>
      </div>
    </section>

    <BiometricCaptureDialog
      v-model:show="showCapture"
      :method="form.verification.method"
      @captured="onCaptured"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { call } from "frappe-ui";
import { useToast } from "@/composables/useToast";
import {
  authorizeJubileeAppointment,
  authorizeNhifAppointment,
  getInsuranceApiSettings,
} from "@/data/insurance";
import BiometricCaptureDialog from "./create/BiometricCaptureDialog.vue";
import FieldLabel from "./create/FieldLabel.vue";
import NhifVerificationSection from "./create/NhifVerificationSection.vue";
import ProviderReplyPanel from "./create/ProviderReplyPanel.vue";

const props = defineProps({
  appointment: { type: Object, required: true },
});
const emit = defineEmits(["authorized"]);

const { showError, showSuccess, showWarning, handleResourceError } =
  useToast();
const settings = ref({ enable_nhif_api: false, enable_jubilee_api: false });
const busy = ref(false);
const providerReply = ref(null);
const showCapture = ref(false);
const form = reactive({
  visitType: { requires_remarks: 0, requires_referral_no: 0 },
  verification: {
    method: props.appointment.biometric_method || "FINGERPRINT",
    referral_no: props.appointment.referral_no || "",
    remarks: props.appointment.remarks || "",
    authorization_number: "",
  },
  authorization: null,
});
let resolveCapture = null;

const insuranceCompany = computed(
  () => props.appointment.insurance_company || ""
);
const isNhif = computed(() => insuranceCompany.value.includes("NHIF"));
const isJubileeApi = computed(
  () =>
    insuranceCompany.value.includes("Jubilee") &&
    settings.value.enable_jubilee_api
);

const run = async (work) => {
  busy.value = true;
  providerReply.value = null;
  try {
    await work();
  } catch (error) {
    if (error.exc_type === "ProviderReplyError") {
      providerReply.value = JSON.parse(error.messages[0]);
    } else {
      handleResourceError(error);
    }
  } finally {
    busy.value = false;
  }
};

const captureBiometric = () =>
  new Promise((resolve) => {
    resolveCapture = resolve;
    showCapture.value = true;
  });

const onCaptured = (result) => {
  resolveCapture?.(result);
  resolveCapture = null;
};

const authorizeNhif = async () => {
  const { method, referral_no, remarks } = form.verification;
  if (method === "NONE" && !remarks.trim()) {
    showError(
      "Remarks are required when the patient is not verified by biometrics"
    );
    return;
  }
  const biometric =
    method === "NONE" ? { Data: "", fpCode: "" } : await captureBiometric();
  if (!biometric) return;
  const result = await authorizeNhifAppointment({
    appointment: props.appointment.name,
    fingerprint: biometric.Data,
    fpcode: biometric.fpCode,
    biometric_method: method,
    referral_no,
    remarks,
  });
  if (result.authorization_status !== "ACCEPTED") {
    showWarning(`${result.authorization_status}: ${result.remarks}`, {
      timeout: 10000,
    });
  }
  done(result.authorization_number);
};

const authorizeJubilee = async () => {
  const number = await authorizeJubileeAppointment(props.appointment.name);
  if (!number) {
    showError("Jubilee did not return an authorization no");
    return;
  }
  done(number);
};

const done = (number) => {
  showSuccess(`Authorization no ${number} saved`);
  emit("authorized");
};

const loadVisitType = async () => {
  const visitType = await call("frappe.client.get_value", {
    doctype: "Appointment Type",
    filters: props.appointment.appointment_type,
    fieldname: ["requires_remarks", "requires_referral_no"],
  });
  form.visitType = {
    requires_remarks: visitType?.requires_remarks || 0,
    requires_referral_no: visitType?.requires_referral_no || 0,
  };
};

onMounted(async () => {
  [settings.value] = await Promise.all([
    getInsuranceApiSettings(props.appointment.company),
    loadVisitType(),
  ]);
});

defineExpose({ verification: form.verification });
</script>
