<template>
  <Dialog
    :model-value="localShowDialog"
    @update:model-value="updateDialogState"
    :options="{
      title: dialogTitle,
      size: '4xl',
      icon: {
        name: 'book',
        appearance: 'black',
      },
    }"
    :disable-outside-click-to-close="true"
    class="appointment-dialog-overlay z-[1050]"
  >
    <!-- <template #body-title>
      <div class="flex gap-36 items-center justify-center mb-0">
        <div class="w-112 mb-4 justify-center">
          <h3 class="flex justify-center text-2xl text-center font-semibold leading-6 text-gray-900">
            {{ dialogTitle }}
          </h3>
        </div>
      </div>
    </template> -->
    <template #body-content>
      <div class="space-y-4 relative">
        <DialogErrorPanel
          v-if="dialogError"
          :error="dialogError"
          @close="dialogError = null"
        />

        <!-- Mode Badge -->
        <div
          v-if="!isCreateMode"
          class="flex justify-between items-center mb-4"
        >
          <div class="flex items-center space-x-2">
            <span
              class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium"
              :class="modeBadgeClasses"
            >
              <svg
                class="w-3 h-3 mr-1"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  v-if="isCreateMode"
                  fill-rule="evenodd"
                  d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                  clip-rule="evenodd"
                />
                <path
                  v-else-if="props.mode === 'edit'"
                  fill-rule="evenodd"
                  d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
                  clip-rule="evenodd"
                />
                <path
                  v-else
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z"
                  clip-rule="evenodd"
                />
              </svg>
              {{ modeBadgeText }}
            </span>
          </div>

          <!-- Cancel Appointment Button in View Mode -->
          <div v-if="isViewMode" class="flex items-center">
            <Button
              v-if="
                appointment['Patient Appointment']['status']?.toLowerCase() !==
                  'cancelled' &&
                canShowCancelButton &&
                !isPractitionerDisabled
              "
              variant="subtle"
              size="md"
              theme="red"
              :disabled="isCreating || cancel_appointment_doc?.loading"
              :loading="cancel_appointment_doc?.loading"
              @click="showCancelConfirmation = true"
            >
              <template #prefix>
                <FeatherIcon name="x" class="w-4 h-4" />
              </template>
              Cancel Appointment
            </Button>
          </div>

          <!-- Sales Invoice Button for Cash Appointments in View Mode -->
          <div v-if="isViewMode" class="flex items-center gap-2">
            <!-- Make Payment Button - Only show if invoice not created -->
            <Button
              v-if="
                appointment['Patient Appointment']['payment_mode'] ===
                  'Cash' &&
                !appointment['Patient Appointment']['ref_sales_invoice'] &&
                !isPractitionerDisabled
              "
              variant="subtle"
              size="lg"
              theme="blue"
              :disabled="isCreating"
              @click="showPaymentDialog = true"
              class="font-semibold inline-flex items-center"
              title="Create Sales Invoice for Cash Appointment"
            >
              <template #prefix>
                <FeatherIcon name="dollar-sign" class="w-4 h-4" />
              </template>
              Make Payment
            </Button>

            <Button
              v-if="appointmentStore.canViewItemizedBill"
              variant="subtle"
              size="lg"
              :disabled="!isClosed"
              :title="
                isClosed
                  ? 'Open the Itemized Bill Report to view and print it'
                  : 'The itemized bill is ready after the appointment is Closed'
              "
              class="font-semibold inline-flex items-center"
              @click="openItemizedBill"
            >
              <template #prefix>
                <FeatherIcon name="file-text" class="w-4 h-4" />
              </template>
              Itemized Bill
            </Button>

            <!-- Print Button - Only show if invoice has been created -->
            <Print
              v-if="appointment['Patient Appointment']['ref_sales_invoice']"
              doctype="Sales Invoice"
              :docname="
                appointment['Patient Appointment']['ref_sales_invoice']
              "
              variant="subtle"
              size="lg"
              theme="green"
              :disabled="isCreating"
              label="Print"
              title="Print Tax Invoice"
              class="font-semibold inline-flex items-center"
              @print-success="handlePrintSuccess"
              @print-error="handlePrintError"
            />
          </div>
        </div>

        <!-- Success Banner for newly created cash appointments -->
        <div
          v-if="
            isViewMode &&
            justCreated &&
            appointment['Patient Appointment']['payment_mode'] === 'Cash'
          "
          class="bg-green-50 border border-green-200 rounded-lg p-4 mb-4 animate-pulse-gentle"
        >
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <svg
                class="h-5 w-5 text-green-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="ml-3">
              <p class="text-sm font-medium text-green-800">
                Appointment created successfully!
              </p>
              <p class="text-xs text-green-600 mt-1">
                You can now create a sales invoice for this cash payment
                appointment.
              </p>
            </div>
          </div>
        </div>

        <!-- Edit Mode Banner -->
        <div
          v-if="props.mode === 'edit'"
          class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4"
        >
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <svg
                class="h-5 w-5 text-blue-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="ml-3">
              <p class="text-sm font-medium text-blue-800">
                Edit Mode: You can modify selected fields
              </p>
              <p class="text-xs text-blue-600 mt-1">
                Only practitioner, appointment time and, for insurance, the
                authorization no, referral no and remarks can be edited. The
                visit type can be changed until the appointment is authorized
                or invoiced.
                <template v-if="isInvoiced">
                  This appointment is invoiced, so its practitioner cannot
                  change.
                </template>
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white px-2 pb-6 pt-1 sm:px-2">
          <div class="mb-5 flex gap-36 items-center justify-around">
            <!-- <div class="w-112 mb-4">
              <h3 class="text-2xl text-center font-semibold leading-6 text-gray-900">
                {{ dialogTitle }}
              </h3>
            </div> -->
          </div>
          <div class="relative">
            <CreateAppointmentForm
              v-if="isCreateMode && localShowDialog"
              ref="createForm"
              :company="props.company"
              :practitioner="props.practitionerData?.name"
              :appointment-date="dateStore.selectedDate"
              :appointment-time="props.timeSlot"
              @progress="onProgress"
              @created="onCreated"
            />
            <template v-else-if="sections">
              <div
                v-if="isViewMode && isPractitionerDisabled"
                class="mb-5 flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700"
              >
                <FeatherIcon name="lock" class="h-4 w-4 shrink-0" />
                {{
                  practitionerStatus === "Missing"
                    ? "The practitioner of this appointment has no record in HMS."
                    : "The practitioner is disabled."
                }}
                This appointment is kept as a record and cannot be changed.
              </div>
              <div
                v-else-if="isViewMode && isUnauthorized"
                class="mb-5 flex items-center gap-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800"
              >
                <FeatherIcon name="alert-triangle" class="h-4 w-4 shrink-0" />
                The patient is not authorized. Click Edit to authorize or to
                enter the authorization no.
              </div>
              <PaymentModeStrip :payment="paymentSection" />
              <FieldMap :sections="sections" :data="appointment" />
              <AuthorizeAppointmentSection
                v-if="props.mode === 'edit' && isUnauthorized"
                ref="authorizeSection"
                :key="appointment['Patient Appointment'].name"
                class="mt-5"
                :appointment="appointment['Patient Appointment']"
                @progress="onProgress"
                @authorized="onAuthorized"
              />
            </template>

            <!-- Local Dialog Content Overlay -->
            <Transition name="loading-fade">
              <div
                v-if="isCreating"
                class="absolute inset-0 bg-white bg-opacity-80 backdrop-blur-sm z-10 flex items-center justify-center"
                @click.stop
                @keydown.stop
                @mousedown.stop
                @touchstart.stop
              >
                <div class="text-center p-4">
                  <div class="spinner-container">
                    <div
                      class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-100 mb-3"
                    >
                      <div
                        class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"
                      ></div>
                    </div>
                  </div>
                  <p class="text-sm text-gray-600 font-medium">
                    Processing...
                  </p>
                </div>
              </div>
            </Transition>
          </div>
        </div>

        <!-- Full Screen Loading Overlay -->
        <Teleport to="body">
          <Transition name="loading-fade">
            <div
              v-if="isCreating"
              class="fixed inset-0 z-[1100] flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm loading-overlay"
              @click.stop
              @keydown.stop
              @mousedown.stop
              @touchstart.stop
            >
              <div
                class="bg-white rounded-lg shadow-2xl p-8 max-w-md w-full mx-4 transform transition-all duration-300"
              >
                <div class="text-center">
                  <!-- Animated Loading Spinner -->
                  <div class="mb-6 spinner-container">
                    <div
                      class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-100 mb-4"
                    >
                      <div
                        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
                      ></div>
                    </div>
                  </div>

                  <!-- Loading Title -->
                  <h3 class="text-xl font-semibold text-gray-900 mb-2">
                    {{ loadingTitle }}
                  </h3>

                  <!-- Dynamic Status Message -->
                  <p class="text-gray-600 mb-4 min-h-[1.5rem]">
                    {{ statusMessage }}
                  </p>

                  <!-- Progress Indicator -->
                  <div class="w-full bg-gray-200 rounded-full h-2 mb-4">
                    <div
                      class="bg-blue-600 h-2 rounded-full progress-bar"
                      :style="{ width: `${loadingProgress}%` }"
                    ></div>
                  </div>

                  <!-- Please Wait Message -->
                  <p class="text-sm text-gray-500">
                    Please wait while we process your request...
                  </p>

                  <!-- Additional instruction -->
                  <p class="text-xs text-gray-400 mt-2">
                    Please do not close this window
                  </p>
                </div>
              </div>
            </div>
          </Transition>
        </Teleport>

        <!-- Nested inside this Dialog so headlessui hands focus to it -->
        <PaymentDialog
          v-model:show-dialog="showPaymentDialog"
          :appointment-data="appointment['Patient Appointment']"
          @paymentCompleted="handlePaymentCompleted"
        />
      </div>
    </template>

    <!-- Action buttons -->
    <template #actions>
      <div class="flex gap-2 justify-between">
        <div class="flex items-center">
          <p v-if="isCreateMode" class="text-xs text-gray-500">
            {{ createForm?.creates }}
          </p>
          <Button
            v-if="isViewMode"
            variant="subtle"
            size="lg"
            :disabled="isCreating"
            @click="closeDialog()"
          >
            <template #prefix>
              <FeatherIcon name="x" class="w-4 h-4 mr-1" />
            </template>
            Close
          </Button>

          <Button
            v-if="props.mode === 'edit'"
            variant="subtle"
            size="lg"
            theme="gray"
            :disabled="isCreating"
            @click="backToViewMode()"
            class="font-medium inline-flex items-center"
            title="Back to previous page"
          >
            <template #prefix>
              <FeatherIcon name="arrow-left" class="w-6 h-4 mr-1" />
            </template>
            Back
          </Button>
        </div>

        <div class="flex gap-2">
          <template v-if="isViewMode">
            <Button
              v-if="!isReadOnlyStatus && !isPractitionerDisabled"
              variant="subtle"
              size="lg"
              theme="gray"
              :disabled="isCreating"
              @click="editAppointment()"
            >
              <template #suffix>
                <FeatherIcon name="edit-3" class="w-4 h-4 mr-1" />
              </template>
              Edit
            </Button>
          </template>

          <template v-else-if="isCreateMode">
            <Button
              variant="subtle"
              size="lg"
              theme="gray"
              :disabled="isCreating"
              @click="closeDialog()"
            >
              Close
            </Button>

            <Button
              variant="solid"
              size="lg"
              :loading="isCreating"
              :disabled="isCreating || !createForm?.canSubmit"
              @click="createForm.submit()"
            >
              Create
            </Button>
          </template>

          <template v-else>
            <Button
              variant="subtle"
              size="lg"
              theme="gray"
              :disabled="isCreating"
              @click="closeDialog()"
            >
              <template #prefix>
                <FeatherIcon name="x" class="w-4 h-4 mr-1" />
              </template>
              Close
            </Button>

            <Button
              variant="subtle"
              size="lg"
              theme="blue"
              :loading="isCreating"
              :disabled="isCreating"
              @click="handleSubmit()"
            >
              Update
              <template #suffix>
                <FeatherIcon name="check-circle" class="w-4 h-4 mr-1" />
              </template>
            </Button>
          </template>
        </div>
      </div>
    </template>
  </Dialog>

  <!-- Cancel Appointment Confirmation Dialog -->
  <Dialog
    :model-value="showCancelConfirmation"
    @update:model-value="showCancelConfirmation = $event"
    :options="{
      title: 'Confirm',
      size: 'md',
      icon: {
        name: 'alert-triangle',
        appearance: 'blue',
      },
    }"
    class="cancel-confirmation-dialog z-[1100]"
  >
    <template #body-content>
      <div class="p-6">
        <div class="flex items-start space-x-4">
          <div class="flex-shrink-0">
            <div
              class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100"
            >
              <FeatherIcon name="help-circle" class="h-6 w-6 text-blue-600" />
            </div>
          </div>
          <div class="flex-1">
            <h3 class="text-lg font-semibold text-blue-900 mb-2 font-semibold">
              Are you sure you want to cancel this appointment?
            </h3>
            <!-- - This action cannot be undone and Patient will need to book a new appointment. -->
            <p class="text-sm text-red-800">- This action cannot be undone</p>
            <p class="text-sm text-red-800">
              - Patient will need to book a new appointment.
            </p>
          </div>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex gap-3 justify-end">
        <Button
          variant="outline"
          size="md"
          theme="gray"
          :disabled="cancel_appointment_doc?.loading"
          @click="showCancelConfirmation = false"
        >
          <template #prefix>
            <FeatherIcon name="x" class="w-4 h-4" />
          </template>
          No, Keep It
        </Button>

        <Button
          variant="solid"
          size="md"
          theme="red"
          :loading="cancel_appointment_doc?.loading"
          :disabled="cancel_appointment_doc?.loading"
          @click="confirmCancelAppointment()"
        >
          <template #prefix>
            <FeatherIcon name="check" class="w-4 h-4" />
          </template>
          Yes, Cancel
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import {
  computed,
  reactive,
  watch,
  ref,
  nextTick,
  onUnmounted,
  onMounted,
} from "vue";
import { createResource } from "frappe-ui";
import { useAppointmentStore } from "@/data/appointment";
import { usePractitionerStore } from "@/data/practitioner";
import { useDateStore } from "@/data/date";
import { useToast } from "@/composables/useToast";
import { provideDialogError } from "@/composables/dialogError";
import FieldMap from "@/components/controls/FieldMap.vue";
import PaymentModeStrip from "@/components/appointments/PaymentModeStrip.vue";
import { getPaymentOption } from "@/data/appointmentFilters";
import CreateAppointmentForm from "@/components/appointments/create/CreateAppointmentForm.vue";
import PaymentDialog from "@/components/appointments/PaymentDialog.vue";
import AuthorizeAppointmentSection from "@/components/appointments/AuthorizeAppointmentSection.vue";
import DialogErrorPanel from "@/components/appointments/DialogErrorPanel.vue";
import Print from "@/components/controls/Print.vue";
import dayjs from "dayjs";

// Props for v-model approach
const props = defineProps({
  showDialog: {
    type: Boolean,
    default: false,
  },
  timeSlot: {
    type: String,
    default: "",
  },
  practitionerData: {
    type: Object,
    default: () => ({}),
  },
  mode: {
    type: String,
    default: "create", // 'create', 'edit', 'view'
  },
  appData: {
    type: Object,
    default: () => ({}),
  },
  company: {
    type: String,
    default: "",
  },
});

// Emits for v-model approach
const emit = defineEmits([
  "update:showDialog",
  "closeDialog",
  "appointmentCreated",
  "editAppointment",
  "modeChanged",
]);

const appointmentStore = useAppointmentStore();
const practitionerStore = usePractitionerStore();
const dateStore = useDateStore();
const dialogError = provideDialogError();
const { notifications, handleResourceError, showError, showInfo, clearError } =
  useToast(dialogError);

// Local dialog state for v-model approach
const localShowDialog = ref(props.showDialog);
const isCreating = ref(false);
const statusMessage = ref("");
const loadingTitle = ref("Creating Appointment");
const error = ref("");
const loadingProgress = ref(0);
const justCreated = ref(false);
const showCancelConfirmation = ref(false);
const showPaymentDialog = ref(false);

// Dialog computed properties
const isViewMode = computed(() => props.mode === "view");
const isCreateMode = computed(() => props.mode === "create");

const dialogTitle = computed(() => {
  switch (props.mode) {
    case "create":
      return "New Appointment";
    case "edit":
      return "Edit Appointment";
    case "view":
      return "Appointment Details";
    default:
      return "Appointment";
  }
});

// Mode badge styling
const modeBadgeClasses = computed(() => {
  switch (props.mode) {
    case "create":
      return "bg-green-100 text-green-800 border border-green-300";
    case "edit":
      return "bg-blue-100 text-blue-800 border border-blue-300";
    case "view":
      return "bg-gray-100 text-gray-800 border border-gray-300";
    default:
      return "bg-gray-100 text-gray-800 border border-gray-300";
  }
});

const modeBadgeText = computed(() => {
  switch (props.mode) {
    case "create":
      return "Create Mode";
    case "edit":
      return "Edit Mode";
    case "view":
      return "View Mode";
    default:
      return "Unknown Mode";
  }
});

// The Itemized Bill Report refuses appointments that are not Closed.
const isClosed = computed(
  () => appointment["Patient Appointment"].status?.toLowerCase() === "closed"
);

// The desk report owns the data and its print template; its filters come from the URL.
const openItemizedBill = () => {
  const { name, patient } = appointment["Patient Appointment"];
  const filters = new URLSearchParams({ patient, patient_appointment: name });
  window.open(
    `/app/query-report/Itemized%20Bill%20Report?${filters}`,
    "_blank",
    "noopener"
  );
};

// Role-based visibility for Cancel button
const canShowCancelButton = computed(() => {
  return appointmentStore.canCancelAppointment;
});

const emptyAppointment = () => ({
  "Patient Appointment": {
    name: "",
    payment_mode: "",
    patient: "",
    patient_name: "",
    patient_sex: "",
    practitioner: "",
    department: "",
    appointment_type: "",
    appointment_date: "",
    appointment_time: "",
    follow_up: false,
    apply_fasttrack_charge: false,
    has_no_consultation_charges: false,
    billing_item: "",
    paid_amount: "",
    referral_no: "",
    remarks: "",
    insurance_subscription: "",
    insurance_company: "",
    coverage_plan_name: "",
    coverage_plan_card_number: "",
    authorization_number: "",
    require_fingerprint: "",
    require_facial_recognation: "",
    biometric_method: "",
    fpcode: "",
    poc_reference_no: "",
    mode_of_payment: "",
    ref_sales_invoice: "",
    invoiced: 0,
    status: "",
    company: "",
  },
  Patient: {
    first_name: "",
    middle_name: "",
    last_name: "",
    sex: "",
    dob: "",
    mobile: "",
    product_code: "",
    scheme_id: "",
    membership_no: "",
    card_no: "",
    next_to_kin_name: "",
    next_to_kin_mobile_no: "",
    next_to_kin_relationship: "",
  },
  "Healthcare Insurance Subscription": {
    patient: "",
    patient_name: "",
    insurance_company: "",
    healthcare_insurance_coverage_plan: "",
    coverage_plan_card_number: "",
  },
});

const appointment = reactive(emptyAppointment());

const isInsurance = computed(
  () => appointment["Patient Appointment"]["payment_mode"] === "Insurance"
);
const paymentSection = computed(() =>
  getPaymentOption(
    isInsurance.value,
    appointment["Patient Appointment"]["insurance_company"] ?? ""
  )
);
const isNhif = computed(() => paymentSection.value === "NHIF");
// Edit mode keeps the number saved when it opened, so typing in the field does not swap in the authorization section.
const authorizationNumberAtEdit = ref("");
watch(
  () => props.mode,
  (mode) => {
    if (mode === "edit") {
      authorizationNumberAtEdit.value =
        appointment["Patient Appointment"]["authorization_number"] || "";
    }
  },
  { immediate: true }
);
const isUnauthorized = computed(() => {
  const doc = appointment["Patient Appointment"];
  const authorizationNumber =
    props.mode === "edit"
      ? authorizationNumberAtEdit.value
      : doc.authorization_number;
  return (
    isInsurance.value &&
    !authorizationNumber &&
    doc.status?.toLowerCase() !== "cancelled"
  );
});

const isReadOnlyStatus = computed(() =>
  ["closed", "cancelled"].includes(
    appointment["Patient Appointment"]["status"]?.toLowerCase()
  )
);

const practitionerStatus = computed(
  () =>
    practitionerStore.practitioners.find(
      ({ name }) => name === appointment["Patient Appointment"].practitioner
    )?.status
);
// Appointments of a disabled practitioner, or of one with no record, are records only.
const isPractitionerDisabled = computed(() =>
  ["Disabled", "Missing"].includes(practitionerStatus.value)
);

const EDITABLE_FIELDS = [
  "practitioner",
  "appointment_time",
  "authorization_number",
  "referral_no",
  "remarks",
];

// The visit type decides what NHIF authorizes and what is billed, so it changes only before either.
const canChangeVisitType = computed(
  () =>
    !authorizationNumberAtEdit.value &&
    !appointment["Patient Appointment"].invoiced
);
// The submitted invoice names the practitioner, so an invoiced appointment keeps it.
const isInvoiced = computed(() =>
  Boolean(appointment["Patient Appointment"].ref_sales_invoice)
);
const editableFields = computed(() => {
  const fields = EDITABLE_FIELDS.filter(
    (name) => name !== "practitioner" || !isInvoiced.value
  );
  return canChangeVisitType.value ? [...fields, "appointment_type"] : fields;
});

const field = (name, label, type, extra = {}) => ({
  name,
  label,
  type,
  placeholder: label,
  ...extra,
});

// View and edit show the saved appointment; only editableFields open in edit mode.
const sections = computed(() => {
  const readOnly = (fields) =>
    fields.map((item) => ({
      ...item,
      read_only: isViewMode.value || !editableFields.value.includes(item.name),
    }));
  const revenueFields = isInsurance.value
    ? [
        field("insurance_company", "Insurance Company", "Data"),
        field("coverage_plan_name", "Coverage Plan", "Data"),
        field("coverage_plan_card_number", "Card No", "Data"),
        // In edit mode the authorization section below owns these fields.
        ...(props.mode === "edit" && isUnauthorized.value
          ? []
          : [
              field("authorization_number", "Authorization No", "Data", {
                highlight: isUnauthorized.value,
                placeholder: isUnauthorized.value
                  ? "Not authorized"
                  : "Authorization No",
              }),
              field("referral_no", "Referral No", "Data"),
            ]),
        field("billing_item", "Billing Item", "Link", { options: "Item" }),
        field("paid_amount", "Billing Amount", "Currency"),
        ...(props.mode === "edit" && isUnauthorized.value
          ? []
          : [field("remarks", "Remarks", "Small Text")]),
      ]
    : [
        field("mode_of_payment", "Mode of Payment", "Data"),
        field("billing_item", "Billing Item", "Link", { options: "Item" }),
        field("paid_amount", "Paid Amount", "Currency"),
      ];
  if (appointment["Patient Appointment"]["ref_sales_invoice"]) {
    revenueFields.push(field("ref_sales_invoice", "Sales Invoice", "Data"));
  }

  return [
    {
      label: "Flags",
      doctype: "Patient Appointment",
      fields: readOnly([
        field("follow_up", "Follow Up", "Check"),
        ...(isNhif.value
          ? [field("apply_fasttrack_charge", "Fast Track", "Check")]
          : []),
        field(
          "has_no_consultation_charges",
          "Has No Consultation Charges",
          "Check"
        ),
      ]),
      columns: isNhif.value ? 3 : 2,
      hideLabel: true,
    },
    {
      label: "Appointment Details",
      doctype: "Patient Appointment",
      fields: readOnly([
        field("patient", "Patient", "Link", {
          options: "Patient",
          reqd: true,
        }),
        field("patient_name", "Patient Name", "Data"),
        field("patient_sex", "Gender", "Data"),
        field("practitioner", "Practitioner", "Link", {
          options: "Healthcare Practitioner",
          reqd: true,
        }),
        field("department", "Department", "Link", {
          options: "Medical Department",
        }),
        field("appointment_type", "Visit Type", "Link", {
          options: "Appointment Type",
          reqd: true,
        }),
        field("appointment_date", "Appointment Date", "Date", { reqd: true }),
        field("appointment_time", "Appointment Time", "Time", { reqd: true }),
      ]),
      columns: 3,
      hideLabel: true,
    },
    {
      label: "Revenue",
      doctype: "Patient Appointment",
      fields: readOnly(revenueFields),
      columns: 3,
      hideLabel: true,
    },
  ];
});

// An error belongs to one opening of the dialog.
watch(localShowDialog, clearError);

// Dialog state update handler
const updateDialogState = (newVal) => {
  if (localShowDialog.value === newVal) return; // Prevent unnecessary updates

  // Prevent closing dialog while creating documents
  if (!newVal && isCreating.value) {
    return; // Don't allow closing during document creation
  }

  localShowDialog.value = newVal;
  emit("update:showDialog", newVal);

  if (newVal) {
    // Dialog is opening - ensure popovers appear above dialog
    ensurePopoverZIndex();
  } else {
    // Dialog is closing - restore normal popover z-index
    restorePopoverZIndex();
    emit("closeDialog");
    // Only reset appointment data if not in view mode to preserve data
    if (!isViewMode.value) {
      resetAppointment();
    }
  }
};

// Utility functions to manage popover z-index
let popoverObserver = null;

const ensurePopoverZIndex = () => {
  nextTick(() => {
    const popoverRoot = document.getElementById("frappeui-popper-root");
    if (popoverRoot) {
      popoverRoot.style.zIndex = "1080";
      // Also apply to any existing popover content
      const popoverElements = popoverRoot.querySelectorAll("*");
      popoverElements.forEach((el) => {
        if (el.classList.contains("z-[100]") || el.style.zIndex) {
          el.style.zIndex = "1080";
        }
      });

      // Set up mutation observer to handle dynamically created popovers
      if (!popoverObserver) {
        popoverObserver = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
              if (node.nodeType === Node.ELEMENT_NODE) {
                // Apply z-index to new popover elements
                if (node.classList?.contains("z-[100]")) {
                  node.style.zIndex = "1080";
                }
                // Also check children
                const childPopovers = node.querySelectorAll?.(".z-\\[100\\]");
                childPopovers?.forEach((child) => {
                  child.style.zIndex = "1080";
                });
              }
            });
          });
        });

        popoverObserver.observe(popoverRoot, {
          childList: true,
          subtree: true,
        });
      }
    }

    // Apply to any existing bootstrap popovers
    const bootstrapPopovers = document.querySelectorAll(".popover");
    bootstrapPopovers.forEach((el) => {
      el.style.zIndex = "1080";
    });
  });
};

const restorePopoverZIndex = () => {
  nextTick(() => {
    // Disconnect the mutation observer
    if (popoverObserver) {
      popoverObserver.disconnect();
      popoverObserver = null;
    }

    const popoverRoot = document.getElementById("frappeui-popper-root");
    if (popoverRoot) {
      popoverRoot.style.zIndex = "";
      // Restore original z-index for popover content
      const popoverElements = popoverRoot.querySelectorAll("*");
      popoverElements.forEach((el) => {
        if (el.style.zIndex === "1080") {
          el.style.zIndex = "";
        }
      });
    }

    // Restore bootstrap popovers
    const bootstrapPopovers = document.querySelectorAll(".popover");
    bootstrapPopovers.forEach((el) => {
      if (el.style.zIndex === "1080") {
        el.style.zIndex = "";
      }
    });
  });
};

// Watch for dialog state changes - v-model approach
watch(
  () => props.showDialog,
  (newVal, oldVal) => {
    // Only update if there's an actual change and it's different from local state
    if (oldVal !== newVal && newVal !== localShowDialog.value) {
      localShowDialog.value = newVal;
      if (newVal) {
        // Dialog is opening
        ensurePopoverZIndex();
        // Use nextTick for immediate opening
        nextTick(() => {
          resetAppointment();
          error.value = "";
          if (props.appData && Object.keys(props.appData).length > 0) {
            // Load existing appointment data for view/edit mode
            loadAppointmentData(props.appData);
          }
        });
      } else {
        // Dialog is closing
        restorePopoverZIndex();
      }
    }
  },
  { immediate: false }
);

// Watch for appointment prop changes (for view/edit mode updates from parent)
watch(
  () => props.appData,
  (newAppointment) => {
    if (
      newAppointment &&
      Object.keys(newAppointment).length > 0 &&
      (isViewMode.value || props.mode === "edit")
    ) {
      loadAppointmentData(newAppointment);
    }
  },
  { deep: true, immediate: true }
);

// Watch for mode changes to ensure sections are recalculated
watch(
  () => props.mode,
  (newMode) => {
    // Force reactivity update by triggering the computed property
    if (
      (newMode === "view" || newMode === "edit") &&
      props.appData &&
      Object.keys(props.appData).length > 0
    ) {
      loadAppointmentData(props.appData);
    }
  },
  { immediate: true }
);

// Watch for dialog prop changes (v-model approach)

const resetAppointment = () => {
  Object.assign(appointment, emptyAppointment());
  isCreating.value = false;
  statusMessage.value = "";
  loadingProgress.value = 0;
  error.value = "";
  justCreated.value = false;
};

// Function to load existing appointment data for view/edit mode
const loadAppointmentData = (appointmentData) => {
  if (!appointmentData) return;

  // Handle both nested structure and flat structure
  if (appointmentData["Patient Appointment"]) {
    // Nested structure
    const appointmentInfo = appointmentData["Patient Appointment"];
    Object.keys(appointment["Patient Appointment"]).forEach((key) => {
      if (appointmentInfo[key] !== undefined) {
        appointment["Patient Appointment"][key] = appointmentInfo[key];
      }
    });

    if (appointmentData["Patient"]) {
      Object.keys(appointment["Patient"]).forEach((key) => {
        if (appointmentData["Patient"][key] !== undefined) {
          appointment["Patient"][key] = appointmentData["Patient"][key];
        }
      });

      // Map patient fields to appointment fields for display
      if (appointmentData["Patient"]["sex"]) {
        appointment["Patient Appointment"]["patient_sex"] =
          appointmentData["Patient"]["sex"];
      }
    }

    if (appointmentData["Healthcare Insurance Subscription"]) {
      Object.keys(appointment["Healthcare Insurance Subscription"]).forEach(
        (key) => {
          if (
            appointmentData["Healthcare Insurance Subscription"][key] !==
            undefined
          ) {
            appointment["Healthcare Insurance Subscription"][key] =
              appointmentData["Healthcare Insurance Subscription"][key];
          }
        }
      );
    }
  } else {
    // Flat structure - appointmentData is the appointment directly
    Object.keys(appointment["Patient Appointment"]).forEach((key) => {
      if (appointmentData[key] !== undefined) {
        appointment["Patient Appointment"][key] = appointmentData[key];
      }
    });

    // Handle patient fields that might come from linked patient data
    if (appointmentData.patient_sex) {
      appointment["Patient Appointment"]["patient_sex"] =
        appointmentData.patient_sex;
    }
  }

  appointment["Patient Appointment"]["payment_mode"] = appointment[
    "Patient Appointment"
  ]["insurance_subscription"]
    ? "Insurance"
    : "Cash";

  // Reset loading states
  isCreating.value = false;
  statusMessage.value = "";
  loadingProgress.value = 0;
  error.value = "";
  justCreated.value = false;
};

const validateForm = () => {
  const appointmentData = appointment["Patient Appointment"];
  const validationErrors = [];
  if (!appointmentData.practitioner) {
    validationErrors.push("Practitioner is required");
  }
  if (!appointmentData.appointment_time) {
    validationErrors.push("Appointment Time is required");
  }
  if (validationErrors.length === 0) return true;

  showError(validationErrors.join("\n"), {
    timeout: 10000,
    position: "bottom-right",
    closeOnClick: true,
    pauseOnHover: true,
    draggable: false,
  });
  return false;
};

// Create resource for fetching latest appointment details
const get_appointment_details_doc = createResource({
  url: "hms_tz.api.appointment.get_appointment_details",
  method: "GET",
  makeParams() {
    return {
      appointment_id:
        props.appData?.name || appointment["Patient Appointment"]?.name,
    };
  },
  onSuccess: (data) => {
    // Load the latest appointment data
    loadAppointmentData(data);
    // Emit event to refresh parent component data
    emit("appointmentCreated", data);
  },
  onError: (err) => {
    console.error("Error fetching latest appointment data:", err);
    // Don't show toast notification for this as it's a background operation
    // handleResourceError(err)
  },
});

// Function to fetch latest appointment data
const fetchLatestAppointmentData = async (appointmentId) => {
  try {
    if (!appointmentId) return;

    // Update the appointment ID in the resource params
    get_appointment_details_doc.params = { appointment_id: appointmentId };

    await get_appointment_details_doc.submit();
  } catch (error) {
    console.error("Error fetching latest appointment data:", error);
    // Don't show error notification here as it's handled by the resource onError
  }
};

// Create resource for updating appointment
const update_appointment_doc = createResource({
  url: "hms_tz.api.appointment.update_appointment",
  method: "POST",
  makeParams() {
    return {
      appointment_id:
        props.appData.name || appointment["Patient Appointment"].name,
      practitioner: appointment["Patient Appointment"]["practitioner"],
      appointment_time: appointment["Patient Appointment"]["appointment_time"],
      appointment_type: appointment["Patient Appointment"]["appointment_type"],
      ...authorizationValues(),
    };
  },
  onSuccess: async (data) => {
    if (data) {
      notifications.success.appointmentUpdated();
    } else {
      showInfo("No changes to save");
    }

    // Reset loading state
    isCreating.value = false;
    statusMessage.value = "";
    loadingProgress.value = 0;

    // Fetch latest appointment data after successful update
    const appointmentId =
      props.appData.name || appointment["Patient Appointment"].name;
    if (appointmentId) {
      await fetchLatestAppointmentData(appointmentId);
    }

    // Switch back to view mode with updated appointment data
    setTimeout(() => {
      emit("modeChanged", "view", {
        "Patient Appointment": appointment["Patient Appointment"],
        Patient: appointment["Patient"],
        "Healthcare Insurance Subscription":
          appointment["Healthcare Insurance Subscription"],
      });
    }, 300);
  },
  onError: (err) => {
    handleResourceError(err);

    // Reset loading state on error
    isCreating.value = false;
    statusMessage.value = "";
    loadingProgress.value = 0;
  },
});

const handleSubmit = async () => {
  error.value = "";
  clearError();
  if (props.mode === "edit" && validateForm()) {
    await update_appointment();
  }
};

const createForm = ref(null);
const authorizeSection = ref(null);

// The authorization section owns these values while the appointment is unauthorized.
const authorizationValues = () => {
  const verification = authorizeSection.value?.verification;
  const source = verification || appointment["Patient Appointment"];
  const { authorization_number, referral_no, remarks } = source;
  return {
    authorization_number,
    referral_no,
    remarks,
    biometric_method: verification?.method,
  };
};

const onAuthorized = async () => {
  await fetchLatestAppointmentData(appointment["Patient Appointment"].name);
  backToViewMode();
};

const onProgress = ({ busy, title, message, percent }) => {
  isCreating.value = busy;
  loadingTitle.value = title;
  statusMessage.value = message;
  loadingProgress.value = percent;
};

const onCreated = async (appointmentDoc, payment) => {
  notifications.success.appointmentCreated();
  appointment["Patient Appointment"].name = appointmentDoc.name;
  await fetchLatestAppointmentData(appointmentDoc.name);
  if (payment !== "Cash") {
    closeDialog();
    return;
  }
  justCreated.value = true;
  emit("modeChanged", "view", {
    "Patient Appointment": appointment["Patient Appointment"],
    Patient: appointment["Patient"],
    "Healthcare Insurance Subscription":
      appointment["Healthcare Insurance Subscription"],
  });
};

async function update_appointment() {
  isCreating.value = true;
  error.value = null;
  loadingProgress.value = 0;

  try {
    loadingTitle.value = "Updating Appointment";
    statusMessage.value = "Updating appointment...";
    loadingProgress.value = 50;

    await update_appointment_doc.submit();
  } catch (err) {
    error.value = "Error while updating appointment";
    statusMessage.value = "An error occurred. Please try again.";
    loadingProgress.value = 0;
  } finally {
    // Keep loading for a brief moment to show completion
    if (!error.value) {
      statusMessage.value = "Appointment updated successfully!";
      loadingProgress.value = 100;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }

    isCreating.value = false;
    loadingProgress.value = 0;
  }
}

const editAppointment = () => {
  // Switch to edit mode - handled by parent component
  emit("editAppointment");
};

const backToViewMode = () => {
  // Switch back to view mode with current appointment data
  emit("modeChanged", "view", {
    "Patient Appointment": appointment["Patient Appointment"],
    Patient: appointment["Patient"],
    "Healthcare Insurance Subscription":
      appointment["Healthcare Insurance Subscription"],
  });
};

const closeDialog = () => {
  // Prevent closing during document creation
  if (isCreating.value) {
    return;
  }
  updateDialogState(false);
};

// Create resource for cancelling appointment
const cancel_appointment_doc = createResource({
  url: "hms_tz.api.appointment.cancel_appointment",
  method: "POST",
  makeParams() {
    return {
      appointment_id:
        props.appData?.name ||
        props.appData?.id ||
        appointment["Patient Appointment"]["name"],
    };
  },
  onSuccess: (data) => {
    // Show success notification
    notifications.success.appointmentCancelled();

    // Update local appointment status to match frontend format
    if (appointment["Patient Appointment"]) {
      appointment["Patient Appointment"]["status"] = "cancelled"; // Use lowercase for consistency
    }

    // Emit event to refresh parent data
    emit("appointmentCreated", { status: "cancelled" });

    // Close dialog automatically
    closeDialog();
  },
  onError: handleResourceError,
});

const cancelAppointment = async () => {
  showCancelConfirmation.value = true;
};

const confirmCancelAppointment = async () => {
  showCancelConfirmation.value = false;
  clearError();
  try {
    await cancel_appointment_doc.submit();
  } catch (error) {
    // Error handling is already done in the resource onError callback
    console.error("Error cancelling appointment:", error);
  }
};

// Handle payment completion
const handlePaymentCompleted = async (event) => {
  try {
    // Close payment dialog
    showPaymentDialog.value = false;

    // Extract payment data from event
    const paymentData = event?.paymentData;

    // If we have appointment ID, fetch the latest appointment data
    const appointmentId =
      props.appData?.name || appointment["Patient Appointment"]?.name;
    if (appointmentId) {
      await fetchLatestAppointmentData(appointmentId);
    } else if (paymentData) {
      // Fallback to using payment data if no appointment ID
      loadAppointmentData(paymentData);
    }
  } catch (error) {
    console.error("Error handling payment completion:", error);
    notifications.error.generic("Error during processing payment");
  }
};

// Print handlers for Print component
const handlePrintSuccess = (printData) => {
  // You can add any additional logic here, like tracking analytics
};

const handlePrintError = (error) => {
  // You can add additional error handling here if needed
};

// Cleanup on component unmount
onUnmounted(() => {
  if (popoverObserver) {
    popoverObserver.disconnect();
    popoverObserver = null;
  }
  // Restore popover z-index when component is destroyed
  restorePopoverZIndex();
  // Remove event listeners
  document.removeEventListener("keydown", handleKeyDown);
});

// Handle keyboard events to prevent closing during loading
const handleKeyDown = (event) => {
  if (isCreating.value && (event.key === "Escape" || event.keyCode === 27)) {
    event.preventDefault();
    event.stopPropagation();
    return false;
  }
};

// Add keyboard event listener
onMounted(() => {
  document.addEventListener("keydown", handleKeyDown, { capture: true });

  // Fetch user roles when component mounts
  appointmentStore.fetchUserRoles();
});
</script>

<style scoped>
/*
 * Strategic z-index layering to ensure proper dialog visibility
 * while preserving dropdown functionality inside the dialog
 */

/* Base dialog styling - appears above page elements but below dropdowns */
:deep(.dialog) {
  z-index: 1050 !important;
}

:deep(.dialog-wrapper) {
  z-index: 1050 !important;
}

/* Dialog backdrop - below dialog content */
:deep(.dialog-overlay) {
  z-index: 1040 !important;
}

/* Dialog content - main dialog layer */
:deep(.dialog-content) {
  z-index: 1055 !important;
}

/* Additional targeting for Frappe UI dialog components */
:deep([role="dialog"]) {
  z-index: 1055 !important;
}

/* Fixed backdrop elements */
:deep(.fixed.inset-0) {
  z-index: 1040 !important;
}

/* Modal backdrop */
:deep(.modal-backdrop) {
  z-index: 1035 !important;
}

/* Ensure dialog container has proper layering */
:deep(.modal) {
  z-index: 1055 !important;
}

/* Frappe-specific dialog wrapper */
:deep(.frappe-dialog) {
  z-index: 1055 !important;
}

/* Base dialog wrapper styling */
.appointment-dialog-overlay {
  z-index: 1050 !important;
}

/* Cancel confirmation dialog should appear above main appointment dialog */
.cancel-confirmation-dialog {
  z-index: 1100 !important;
}

/* Ensure cancel confirmation dialog elements have proper layering */
:deep(.cancel-confirmation-dialog .dialog) {
  z-index: 1100 !important;
}

:deep(.cancel-confirmation-dialog .dialog-wrapper) {
  z-index: 1100 !important;
}

:deep(.cancel-confirmation-dialog .dialog-content) {
  z-index: 1105 !important;
}

:deep(.cancel-confirmation-dialog .dialog-overlay) {
  z-index: 1095 !important;
}

:deep(.cancel-confirmation-dialog [role="dialog"]) {
  z-index: 1105 !important;
}

/* Custom actions styling */
:deep(.dialog .actions) {
  padding: 1rem !important;
}

/* Loading overlay animations */
.loading-fade-enter-active,
.loading-fade-leave-active {
  transition: all 0.3s ease;
}

.loading-fade-enter-from,
.loading-fade-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* Progress bar animation */
.progress-bar {
  transition: width 0.5s ease-in-out;
}

/* Prevent text selection during loading */
.loading-overlay * {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

/* Ensure spinner is always centered */
.spinner-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 4rem;
}

/* Gentle pulse animation for success banner */
@keyframes pulse-gentle {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

.animate-pulse-gentle {
  animation: pulse-gentle 2s ease-in-out 3;
}
</style>
