<template>
  <div class="flex flex-col gap-6">
    <SlotFields :form="form" />

    <PaymentSection
      :form="form"
      :is-insurance="isInsurance"
      :can-check-card="canCheckCard"
      :checking="busy"
      @set-payment="setPayment"
      @check-card="checkCard"
      @select-subscription="selectSubscription"
    />

    <PatientSection :form="form" @select-patient="selectPatient" />

    <SubscriptionSection
      v-if="isInsurance"
      :form="form"
      @select-subscription="selectSubscription"
    />

    <NhifVerificationSection
      v-if="form.payment === 'NHIF'"
      :form="form"
      :api-enabled="settings.enable_nhif_api"
      :authorizing="busy"
      @authorize="authorize"
    />
    <JubileeAuthorizationSection
      v-else-if="isInsurance"
      :form="form"
      :api-enabled="form.payment === 'Jubilee' && settings.enable_jubilee_api"
    />

    <BiometricCaptureDialog
      v-model:show="showCapture"
      :method="form.verification.method"
      @captured="onCaptured"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import BiometricCaptureDialog from "./BiometricCaptureDialog.vue";
import JubileeAuthorizationSection from "./JubileeAuthorizationSection.vue";
import NhifVerificationSection from "./NhifVerificationSection.vue";
import PatientSection from "./PatientSection.vue";
import PaymentSection from "./PaymentSection.vue";
import SlotFields from "./SlotFields.vue";
import SubscriptionSection from "./SubscriptionSection.vue";
import { useBookingForm } from "./useBookingForm";

const props = defineProps({
  company: { type: String, default: "" },
  practitioner: { type: String, default: "" },
  appointmentDate: { type: String, default: "" },
  appointmentTime: { type: String, default: "" },
});
const emit = defineEmits(["progress", "created"]);

const {
  form,
  settings,
  busy,
  status,
  isInsurance,
  canCheckCard,
  creates,
  canSubmit,
  loadSettings,
  setPayment,
  selectPatient,
  selectSubscription,
  checkCard,
  authorizeNhif,
  book,
} = useBookingForm({
  company: props.company,
  practitioner: props.practitioner,
  appointment_date: props.appointmentDate,
  appointment_time: props.appointmentTime,
});

const showCapture = ref(false);
let resolveCapture = null;

const captureBiometric = () =>
  new Promise((resolve) => {
    resolveCapture = resolve;
    showCapture.value = true;
  });

const onCaptured = (result) => {
  resolveCapture?.(result);
  resolveCapture = null;
};

const authorize = () => authorizeNhif(captureBiometric);

const submit = async () => {
  const appointment = await book();
  if (appointment) emit("created", appointment, form.payment);
};

watch([busy, status], () =>
  emit("progress", { busy: busy.value, ...status.value })
);

onMounted(loadSettings);

defineExpose({ submit, canSubmit, creates });
</script>
