<template>
  <div class="flex flex-col gap-3">
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
import { computed, onMounted, reactive, ref, watch } from "vue";
import { call } from "frappe-ui";
import { useToast } from "@/composables/useToast";
import {
  authorizeJubileeAppointment,
  authorizeNhifAppointment,
  getInsuranceApiSettings,
  NHIF_WAIT_MESSAGE,
} from "@/data/insurance";
import BiometricCaptureDialog from "./create/BiometricCaptureDialog.vue";
import FieldLabel from "./create/FieldLabel.vue";
import NhifVerificationSection from "./create/NhifVerificationSection.vue";

const props = defineProps({
  appointment: { type: Object, required: true },
});
const emit = defineEmits(["authorized", "progress"]);

const {
  showError,
  showErrorReply,
  showSuccess,
  clearError,
  handleResourceError,
} = useToast();
const settings = ref({ enable_nhif_api: false, enable_jubilee_api: false });
const busy = ref(false);
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

const waitMessage = ref("");

const run = async (work) => {
  // One request at a time: a second click while NHIF is busy would authorize twice.
  if (busy.value) return;
  busy.value = true;
  clearError();
  try {
    await work();
  } catch (error) {
    handleResourceError(error);
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
  waitMessage.value = NHIF_WAIT_MESSAGE;
  const result = await authorizeNhifAppointment({
    appointment: props.appointment.name,
    fingerprint: biometric.Data,
    fpcode: biometric.fpCode,
    biometric_method: method,
    referral_no,
    remarks,
    appointment_type: props.appointment.appointment_type,
  });
  if (result.authorization_status !== "ACCEPTED") {
    showErrorReply({
      title: result.authorization_status,
      message: result.remarks,
    });
  }
  done(result.authorization_number);
};

const authorizeJubilee = async () => {
  waitMessage.value = "Waiting for Jubilee...";
  const number = await authorizeJubileeAppointment({
    appointment: props.appointment.name,
    appointment_type: props.appointment.appointment_type,
  });
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

// The Appointment dialog shows the progress and stays open; the capture dialog is not covered.
watch([busy, showCapture, waitMessage], () =>
  emit("progress", {
    busy: busy.value && !showCapture.value,
    title: "Authorizing Patient",
    message: waitMessage.value,
    percent: 75,
  })
);

// A visit type changed in Edit brings its own referral and remarks rules.
watch(() => props.appointment.appointment_type, loadVisitType);

onMounted(async () => {
  [settings.value] = await Promise.all([
    getInsuranceApiSettings(props.appointment.company),
    loadVisitType(),
  ]);
});

defineExpose({ verification: form.verification });
</script>
