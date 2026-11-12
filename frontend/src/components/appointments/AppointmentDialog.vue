<template>
  <Dialog
    :model-value="localShowDialog"
    @update:model-value="updateDialogState"
    :options="{
      title: dialogTitle,
      size: '2xl',
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
        <!-- Mode Badge -->
        <div class="flex justify-between items-center mb-4">
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
                  'cancelled' && canShowCancelButton
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
                !appointment['Patient Appointment']['ref_sales_invoice']
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
                Only practitioner, and appointment time can be edited.
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
            <FieldMap
              v-if="sections"
              :sections="sections"
              :data="appointment"
            />

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
                    Creating Appointment
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
      </div>
    </template>

    <!-- Action buttons -->
    <template #actions>
      <div class="flex gap-2 justify-between">
        <div class="flex items-center">
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
              v-if="
                appointment['Patient Appointment']['status'] !== 'cancelled'
              "
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
              {{ isCreateMode ? "Create" : "Update" }}
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

  <!-- Payment Dialog -->
  <PaymentDialog
    :show-dialog="showPaymentDialog"
    @update:show-dialog="showPaymentDialog = $event"
    :appointment-data="appData"
    @paymentCompleted="handlePaymentCompleted"
  />
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
import FieldMap from "@/components/controls/FieldMap.vue";
import PaymentDialog from "@/components/appointments/PaymentDialog.vue";
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
const { notifications, handleResourceError, showError } = useToast();

// Local dialog state for v-model approach
const localShowDialog = ref(props.showDialog);
const isCreating = ref(false);
const statusMessage = ref("");
const error = ref("");
const loadingProgress = ref(0);
const justCreated = ref(false);
const showCancelConfirmation = ref(false);
const showPaymentDialog = ref(false);

// Form validation errors
const errors = reactive({});

// Dialog computed properties
const isViewMode = computed(() => props.mode === "view");
const isCreateMode = computed(() => props.mode === "create");

const dialogTitle = computed(() => {
  switch (props.mode) {
    case "create":
      return "Create New Appointment";
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

// Role-based visibility for Cancel button
const canShowCancelButton = computed(() => {
  return appointmentStore.canCancelAppointment;
});

const appointment = reactive({
  "Patient Appointment": {
    payment_mode: "",
    insurance_provider: "",
    is_new_patient: false,
    patient: "",
    patient_name: "",
    patient_sex: "",
    practitioner: "",
    department: "",
    appointment_type: "",
    appointment_date: "",
    appointment_time: "",
    follow_up: false,
    has_no_consultation_charges: false,
    billing_item: "",
    paid_amount: "",
    referral_no: "",
    remarks: "",
    is_new_his: false,
    insurance_subscription: "",
    coverage_plan_card_number: "",
    national_id: "",
    card_no: "",
    authorization_number: "",
    require_fingerprint: "",
    require_facial_recognation: "",
    biometric_method: "",
    fpcode: "",
    poc_reference_no: "",
    mode_of_payment: "",
    ref_sales_invoice: "",
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
    national_id: "",
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
    national_id: "",
  },
});

// Computed property to reorder sections with "Initial Data" first
const sections = computed(() => {
  const paymentMode = appointment["Patient Appointment"]["payment_mode"];
  const insuranceFields = [
    "insurance_provider",
    "card_no",
    "national_id",
    "insurance_company",
    "coverage_plan",
    "is_new_his",
    "insurance_subscription",
    "referral_no",
    "remarks",
    "require_fingerprint",
    "require_facial_recognation",
    "biometric_method",
    "fpcode",
    "poc_reference_no",
    "authorization_number",
  ];
  const currentMode = props.mode;

  // Helper function to filter fields based on payment mode and dialog mode
  const filterFieldsByPaymentMode = (fields, doctype) => {
    let filteredFields = fields;

    // Only apply payment mode filtering in create mode
    if (currentMode === "create") {
      if (!paymentMode) {
        // If payment mode is empty in create mode, only show payment_mode field
        filteredFields = fields.filter(
          (field) => field.name === "payment_mode"
        );
      } else if (paymentMode === "Cash") {
        // Hide insurance-related fields when payment mode is Cash in create mode
        filteredFields = fields.filter(
          (field) => !insuranceFields.includes(field.name)
        );
      }

      const nonCreationFields = [
        "patient_sex",
        "department",
        "billing_item",
        "paid_amount",
        "has_no_consultation_charges",
        "mode_of_payment",
        "ref_sales_invoice",
      ];
      filteredFields = filteredFields.filter(
        (field) => !nonCreationFields.includes(field.name)
      );
    }

    // In view/edit mode, show ALL fields - don't filter by payment mode
    // Then filter by dialog mode
    if (currentMode === "view") {
      // In view mode, hide fields that are only relevant during creation
      const excludeFields = ["is_new_patient", "is_new_his"].concat(
        insuranceFields
      );

      if (!appointment["Patient Appointment"]["ref_sales_invoice"]) {
        excludeFields.push("ref_sales_invoice");
      }

      filteredFields = filteredFields.filter(
        (field) => !excludeFields.includes(field.name)
      );

      // Make all fields read-only in view mode
      filteredFields = filteredFields.map((field) => ({
        ...field,
        read_only: true,
      }));
    } else if (currentMode === "edit") {
      // In edit mode, hide creation-only fields and make most fields read-only except specific editable ones
      const excludeFields = ["is_new_patient", "is_new_his"].concat(
        insuranceFields
      );

      if (!appointment["Patient Appointment"]["ref_sales_invoice"]) {
        excludeFields.push("ref_sales_invoice");
      }

      filteredFields = filteredFields.filter(
        (field) => !excludeFields.includes(field.name)
      );

      const editableFields = ["practitioner", "appointment_time"];
      filteredFields = filteredFields.map((field) => ({
        ...field,
        read_only: !editableFields.includes(field.name),
      }));
    }

    return filteredFields;
  };

  const allSections = [
    // Initial Data section - always first
    {
      label: "Initial Data",
      doctype: "Patient Appointment",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "payment_mode",
            label: "Payment Mode",
            type: "Select",
            options: [
              { label: "", value: "" },
              { label: "Cash", value: "Cash" },
              { label: "Insurance", value: "Insurance" },
            ],
            reqd: true,
          },
          {
            name: "insurance_provider",
            label: "Insurance Provider",
            type: "Select",
            options: [
              { label: "", value: "" },
              { label: "NHIF", value: "NHIF" },
              { label: "Jubilee", value: "Jubilee" },
            ],
            placeholder: "for API triggering",
            reqd: false,
          },
          {
            name: "card_no",
            label: "Card No",
            type: "Data",
            placeholder: "Card No",
            reqd: false,
          },
          {
            name: "national_id",
            label: "National ID",
            type: "Data",
            placeholder: "National ID",
            reqd: false,
          },
        ],
        "Patient Appointment"
      ),
      columns: 2,
      hideLabel: true,
    },

    // Patient
    {
      label: "Patient Details",
      doctype: "Patient",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "first_name",
            label: "First Name",
            type: "Data",
            placeholder: "First Name",
            reqd: true,
          },
          {
            name: "middle_name",
            label: "Middle Name",
            type: "Data",
            placeholder: "Middle Name",
            reqd: false,
          },
          {
            name: "last_name",
            label: "Last Name",
            type: "Data",
            placeholder: "Last Name",
            reqd: true,
          },
          {
            name: "sex",
            label: "Gender",
            type: "Select",
            placeholder: "Gender",
            options: [
              { label: "Male", value: "Male" },
              { label: "Female", value: "Female" },
            ],
            reqd: true,
          },
          {
            name: "dob",
            label: "Date of Birth",
            type: "Date",
            placeholder: "Date of Birth",
            reqd: true,
          },
          {
            name: "mobile",
            label: "Mobile",
            type: "Int",
            placeholder: "Mobile",
            reqd: true,
          },
          {
            name: "next_to_kin_name",
            label: "Next of Kin Name",
            type: "Data",
            placeholder: "Next of Kin Name",
            reqd: false,
          },
          {
            name: "next_to_kin_mobile_no",
            label: "Next of Kin Mobile",
            type: "Data",
            placeholder: "Next of Kin Mobile",
            reqd: false,
          },
          {
            name: "next_to_kin_relationship",
            label: "Next of Kin Relationship",
            type: "Data",
            placeholder: "Next of Kin Relationship",
            reqd: false,
          },
        ],
        "Patient"
      ),
      columns: 3,
      hideLabel: false,
      hideBorder: false,
    },

    // Healthcare Insurance Subscription
    {
      label: "Healthcare Insurance Subscription",
      doctype: "Healthcare Insurance Subscription",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "insurance_company",
            label: "Insurance Company",
            type: "Link",
            placeholder: "Insurance Company",
            options: "Healthcare Insurance Company",
            reqd: true,
          },
          {
            name: "healthcare_insurance_coverage_plan",
            label: "Coverage Plan",
            type: "Link",
            placeholder: "Coverage Plan",
            options: "Healthcare Insurance Coverage Plan",
            reqd: true,
          },
        ],
        "Healthcare Insurance Subscription"
      ),
      columns: 2,
      hideLabel: false,
      hideBorder: false,
    },

    // Check box fields
    {
      label: "",
      doctype: "Patient Appointment",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "is_new_patient",
            label: "Is New Patient",
            type: "Check",
            reqd: false,
          },
          {
            name: "is_new_his",
            label: "Is New HIS",
            type: "Check",
            reqd: false,
          },
          {
            name: "follow_up",
            label: "Follow Up",
            type: "Check",
            placeholder: "Follow Up",
            reqd: false,
          },
          {
            name: "has_no_consultation_charges",
            label: "Has No Consultation Charges",
            type: "Check",
            placeholder: "Has No Consultation Charges",
            reqd: false,
          },
          {
            name: "require_fingerprint",
            label: "Require Fingerprint",
            type: "Check",
            placeholder: "Require Fingerprint",
            reqd: false,
          },
          {
            name: "require_facial_recognation",
            label: "Require Facial Recognition",
            type: "Check",
            placeholder: "Require Facial Recognition",
            reqd: false,
          },
        ],
        "Patient Appointment"
      ),
      columns: 2,
      hideLabel: true,
    },

    {
      label: "Appointment Details",
      doctype: "Patient Appointment",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "patient",
            label: "Patient",
            type: "Link",
            placeholder: "Patient",
            options: "Patient",
            reqd: true,
          },
          {
            name: "patient_name",
            label: "Patient Name",
            type: "Data",
            placeholder: "Patient Name",
            reqd: false,
          },
          {
            name: "patient_sex",
            label: "Gender",
            type: "Data",
            placeholder: "Gender",
            reqd: false,
          },
          {
            name: "practitioner",
            label: "Practitioner",
            type: "Link",
            placeholder: "Practitioner",
            options: "Healthcare Practitioner",
            reqd: true,
          },
          {
            name: "department",
            label: "Department",
            type: "Link",
            placeholder: "Department",
            options: "Medical Department",
            reqd: false,
          },
          {
            name: "appointment_type",
            label: "Appointment Type",
            type: "Link",
            placeholder: "Appointment Type",
            options: "Appointment Type",
            reqd: true,
          },
          {
            name: "appointment_date",
            label: "Appointment Date",
            type: "Date",
            placeholder: "Appointment Date",
            reqd: true,
          },
          {
            name: "appointment_time",
            label: "Appointment Time",
            type: "Time",
            placeholder: "Appointment Time",
            reqd: true,
          },
        ],
        "Patient Appointment"
      ),
      columns: 3,
      hideLabel: ["view", "edit"].includes(currentMode), // Hide label in view mode since it duplicates dialog title
      hideBorder: false,
    },

    // insurance based appointment fields
    {
      label: "Insurance Details",
      doctype: "Patient Appointment",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "insurance_subscription",
            label: "Insurance Subscription",
            type: "Link",
            placeholder: "Insurance Subscription",
            options: "Healthcare Insurance Subscription",
            reqd: false,
          },
          {
            name: "insurance_company",
            label: "Insurance Company",
            type: "Data",
            placeholder: "Insurance Company",
            reqd: false,
          },
          {
            name: "coverage_plan",
            label: "Coverage Plan",
            type: "Data",
            placeholder: "Coverage Plan",
            reqd: false,
          },
          {
            name: "referral_no",
            label: "Referral No",
            type: "Data",
            placeholder: "Referral No",
            reqd: false,
          },
          {
            name: "remarks",
            label: "Remarks",
            type: "Small Text",
            placeholder: "Remarks",
            reqd: false,
          },
          {
            name: "biometric_method",
            label: "Biometric Method",
            type: "Select",
            placeholder: "Biometric Method",
            options: [
              { value: "FINGERPRINT", label: "FINGERPRINT" },
              { value: "FACIAL", label: "FACIAL" },
              { value: "NONE", label: "NONE" },
            ],
            reqd: false,
          },
          {
            name: "authorization_number",
            label: "Authorization Number",
            type: "Data",
            placeholder: "Authorization Number",
            reqd: false,
          },
        ],
        "Patient Appointment"
      ),
      columns: 3,
      hideLabel: ["view", "edit"].includes(currentMode),
      hideBorder: false,
    },

    // Revenue based appointment fields
    {
      label: "",
      doctype: "Patient Appointment",
      fields: filterFieldsByPaymentMode(
        [
          {
            name: "mode_of_payment",
            label: "Mode of Payment",
            type: "Data",
            placeholder: "Mode of Payment",
            reqd: false,
          },
          {
            name: "billing_item",
            label: "Billing Item",
            type: "Link",
            placeholder: "Billing Item",
            options: "Item",
            reqd: false,
          },
          {
            name: "paid_amount",
            label: "Paid Amount",
            type: "Currency",
            placeholder: "Paid Amount",
            reqd: false,
          },
          {
            name: "ref_sales_invoice",
            label: "Sales Invoice",
            type: "Data",
            placeholder: "Sales Invoice",
            reqd: false,
          },
        ],
        "Patient Appointment"
      ),
      columns: 3,
      hideLabel: ["view", "edit"].includes(currentMode),
      hideBorder: false,
    },
  ];

  // Filter sections based on payment mode and dialog mode
  if (currentMode === "create") {
    // In create mode, filter sections based on payment mode selection
    if (!paymentMode) {
      // If payment mode is empty in create mode, only show Initial Data section
      return allSections.filter((section) => section.label === "Initial Data");
    }

    if (paymentMode === "Cash") {
      // For Cash payment mode in create mode, hide Healthcare Insurance Subscription section
      return allSections.filter(
        (section) =>
          section.doctype !== "Healthcare Insurance Subscription" &&
          section.label !== "Insurance Details"
      );
    }

    // For Insurance payment mode in create mode, show all sections
    return allSections;
  }

  // For view mode or edit mode, always show all sections (user needs to see all data)
  return allSections;
});

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
          } else if (isCreateMode.value) {
            // Pre-fill data for create mode
            appointment["Patient Appointment"]["appointment_time"] =
              props.timeSlot;
            appointment["Patient Appointment"]["practitioner"] =
              props.practitionerData?.name;
            appointment["Patient Appointment"]["appointment_date"] =
              dateStore.selectedDate;
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
  appointment["Patient Appointment"] = {
    payment_mode: "",
    insurance_provider: "",
    is_new_patient: false,
    patient: "",
    patient_name: "",
    patient_sex: "",
    practitioner: "",
    department: "",
    appointment_type: "",
    appointment_date: "",
    appointment_time: "",
    follow_up: false,
    has_no_consultation_charges: false,
    billing_item: "",
    paid_amount: "",
    referral_no: "",
    remarks: "",
    is_new_his: false,
    insurance_subscription: "",
    coverage_plan_card_number: "",
    national_id: "",
    card_no: "",
    authorization_number: "",
    require_fingerprint: "",
    require_facial_recognation: "",
    biometric_method: "",
    fpcode: "",
    poc_reference_no: "",
    mode_of_payment: "",
    ref_sales_invoice: "",
    status: "",
    company: "",
  };

  appointment["Patient"] = {
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
    national_id: "",
    next_to_kin_name: "",
    next_to_kin_mobile_no: "",
    next_to_kin_relationship: "",
  };

  appointment["Healthcare Insurance Subscription"] = {
    patient: "",
    patient_name: "",
    insurance_company: "",
    healthcare_insurance_coverage_plan: "",
    coverage_plan_card_number: "",
    national_id: "",
  };

  // Reset loading states
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

  // Auto-fill payment mode for view/edit mode based on insurance subscription
  if (props.mode === "view" || props.mode === "edit") {
    // Check multiple ways an appointment might have insurance
    const hasInsurance =
      appointment["Patient Appointment"]["insurance_subscription"] ||
      appointment["Patient Appointment"]["insurance_provider"] ||
      appointment["Healthcare Insurance Subscription"]["insurance_company"];

    appointment["Patient Appointment"]["payment_mode"] = hasInsurance
      ? "Insurance"
      : "Cash";

    // If we don't have a payment_mode value already, try to determine it from the original data
    if (
      !appointment["Patient Appointment"]["payment_mode"] &&
      appointmentData
    ) {
      const originalPaymentMode =
        appointmentData["Patient Appointment"]?.payment_mode ||
        appointmentData.payment_mode;
      if (originalPaymentMode) {
        appointment["Patient Appointment"]["payment_mode"] =
          originalPaymentMode;
      }
    }
  }

  // Reset loading states
  isCreating.value = false;
  statusMessage.value = "";
  loadingProgress.value = 0;
  error.value = "";
  justCreated.value = false;
};

const validateForm = () => {
  // Clear previous errors
  Object.keys(errors).forEach((key) => delete errors[key]);

  const appointmentData = appointment["Patient Appointment"];
  const patientData = appointment["Patient"];
  const insuranceData = appointment["Healthcare Insurance Subscription"];
  const validationErrors = [];

  // For edit mode, only validate editable fields
  if (props.mode === "edit") {
    // Only validate practitioner, appointment_time, and appointment_type for edit mode
    if (!appointmentData.practitioner) {
      validationErrors.push("Practitioner is required");
    }

    if (!appointmentData.appointment_time) {
      validationErrors.push("Appointment Time is required");
    }
  } else {
    // Full validation for create mode
    // Payment mode validation
    if (!appointmentData.payment_mode) {
      validationErrors.push("Payment Mode is required");
    }

    // Insurance-specific validations
    if (appointmentData.payment_mode === "Insurance") {
      if (!appointmentData.insurance_provider) {
        validationErrors.push("Insurance Provider is required");
      }
      if (!appointmentData.card_no && !appointmentData.national_id) {
        validationErrors.push("Card No or National ID is required");
      }

      // Insurance subscription validations
      if (appointmentData.is_new_his) {
        if (!insuranceData.insurance_company) {
          validationErrors.push("Insurance Company is required");
        }
        if (!insuranceData.healthcare_insurance_coverage_plan) {
          validationErrors.push("Coverage Plan is required");
        }
      }
    }

    // Patient validations
    if (appointmentData.is_new_patient) {
      if (!patientData.first_name?.trim()) {
        validationErrors.push("First Name is required");
      }
      if (!patientData.last_name?.trim()) {
        validationErrors.push("Last Name is required");
      }
      if (!patientData.sex) {
        validationErrors.push("Sex is required");
      }
      if (!patientData.dob) {
        validationErrors.push("Date of Birth is required");
      }
      if (!patientData.mobile) {
        validationErrors.push("Mobile is required");
      }
    } else {
      if (!appointmentData.patient) {
        validationErrors.push("Patient is required");
      }
    }

    // Appointment details validations
    if (!appointmentData.practitioner) {
      validationErrors.push("Practitioner is required");
    }

    if (!appointmentData.appointment_type) {
      validationErrors.push("Appointment Type is required");
    }

    if (!appointmentData.appointment_date) {
      validationErrors.push("Appointment Date is required");
    }

    if (!appointmentData.appointment_time) {
      validationErrors.push("Appointment Time is required");
    }
  }

  // Show validation errors as a single toast notification
  if (validationErrors.length > 0) {
    let errorMessage;

    if (validationErrors.length === 1) {
      errorMessage = validationErrors[0];
    } else {
      // Create a clean, readable error message with proper formatting
      const title = "Please fill in all required fields:";
      const errorList = validationErrors
        .map((error) => `• ${error}`)
        .join("\n");
      errorMessage = `${title}\n\n${errorList}`;
    }

    showError(errorMessage, {
      timeout: 10000, // Show for 10 seconds as requested
      position: "bottom-right", // Use bottom-right position consistently
      closeOnClick: true,
      pauseOnHover: true,
      draggable: false, // Disable dragging to prevent accidental dismissal
    });
    return false;
  }

  return true;
};

// Create resources for document creation
const appointment_doc = createResource({
  url: "hms_tz.api.appointment.create_appointment",
  method: "POST",
  makeParams() {
    return {
      appointment_data: appointment["Patient Appointment"],
    };
  },
  onSuccess: async (data) => {
    notifications.success.appointmentCreated();

    appointment["Patient Appointment"].name = data.name;

    // Fetch latest appointment data after successful creation
    await fetchLatestAppointmentData(data.name);

    // For cash appointments, automatically switch to view mode
    if (appointment["Patient Appointment"]["payment_mode"] === "Cash") {
      // Reset loading state
      isCreating.value = false;
      statusMessage.value = "";
      loadingProgress.value = 0;

      // Set flag to show success banner
      justCreated.value = true;

      // Small delay to let the UI update, then emit mode change with complete appointment data
      setTimeout(() => {
        // Emit mode change to view with complete appointment object
        emit("modeChanged", "view", {
          "Patient Appointment": appointment["Patient Appointment"],
          Patient: appointment["Patient"],
          "Healthcare Insurance Subscription":
            appointment["Healthcare Insurance Subscription"],
        });
      }, 300);
    } else {
      // For insurance appointments, just close and reset as before
      closeDialog();
      resetAppointment();
    }
  },
  onError: (err) => {
    handleResourceError(err);
    notifications.error.appointmentCreateFailed(err.message);
  },
});

const patient_doc = createResource({
  url: "frappe.client.insert",
  method: "POST",
  makeParams() {
    return {
      doc: {
        doctype: "Patient",
        ...appointment["Patient"],
      },
    };
  },
  validate(params) {
    error.value = null;
    if (!params.doc.first_name) {
      error.value = "First Name is required";
      return error.value;
    }
    if (!params.doc.last_name) {
      error.value = "Last Name is required";
      return error.value;
    }
    if (!params.doc.sex) {
      error.value = "Sex is required";
      return error.value;
    }
    if (!params.doc.dob) {
      error.value = "Date of Birth is required";
      return error.value;
    }
  },
  onSuccess: (data) => {
    appointment["Patient Appointment"]["patient"] = data.name;
    appointment["Patient Appointment"][
      "patient_name"
    ] = `${data.first_name} ${data.last_name}`;
    appointment["Healthcare Insurance Subscription"]["patient"] = data.name;
    appointment["Healthcare Insurance Subscription"][
      "patient_name"
    ] = `${data.first_name} ${data.last_name}`;
  },
  onError: (err) => {
    handleResourceError(err);
    notifications.error.patientCreateFailed(err.message);
  },
});

const insurance_doc = createResource({
  url: "frappe.client.insert",
  method: "POST",
  makeParams() {
    return {
      doc: {
        doctype: "Healthcare Insurance Subscription",
        ...appointment["Healthcare Insurance Subscription"],
      },
    };
  },
  validate(params) {
    error.value = null;
    if (!params.doc.patient) {
      error.value = "Patient is required";
      return error.value;
    }
    if (!params.doc.insurance_company) {
      error.value = "Insurance Company is required";
      return error.value;
    }
    if (!params.doc.healthcare_insurance_coverage_plan) {
      error.value = "Coverage Plan is required";
      return error.value;
    }
  },
  onSuccess: (data) => {
    appointment["Patient Appointment"]["insurance_subscription"] = data.name;
  },
  onError: (err) => {
    handleResourceError(err);
    notifications.error.appointmentCreateFailed(err.message);
  },
});

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
    };
  },
  onSuccess: async (data) => {
    notifications.success.appointmentUpdated();

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
    notifications.error.appointmentUpdateFailed(err.message);

    // Reset loading state on error
    isCreating.value = false;
    statusMessage.value = "";
    loadingProgress.value = 0;
  },
});

async function create_appointment_docs() {
  isCreating.value = true;
  error.value = null;
  loadingProgress.value = 0;

  try {
    // Calculate total steps for progress tracking
    let totalSteps = 1; // Always create appointment
    let currentStep = 0;

    if (appointment["Patient Appointment"]["is_new_patient"]) {
      totalSteps++;
    }

    if (appointment["Patient Appointment"]["is_new_his"]) {
      totalSteps++;
    }

    if (!appointment["Patient Appointment"]["company"] && props.company) {
      appointment["Patient Appointment"]["company"] = props.company;
    }

    // Step 1: Create patient if needed
    if (appointment["Patient Appointment"]["is_new_patient"]) {
      currentStep++;
      statusMessage.value = "Creating new patient record...";
      loadingProgress.value = Math.round((currentStep / totalSteps) * 100);
      await patient_doc.submit();

      // Small delay for better UX
      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    // Step 2: Create insurance subscription if needed
    if (appointment["Patient Appointment"]["is_new_his"]) {
      currentStep++;
      statusMessage.value = "Setting up healthcare insurance subscription...";
      loadingProgress.value = Math.round((currentStep / totalSteps) * 100);
      await insurance_doc.submit();

      // Small delay for better UX
      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    // Final Step: Create appointment
    currentStep++;
    statusMessage.value = "Finalizing appointment booking...";
    loadingProgress.value = Math.round((currentStep / totalSteps) * 100);
    await appointment_doc.submit();
  } catch (err) {
    error.value = "Error while creating appointment documents";
    statusMessage.value = "An error occurred. Please try again.";
    loadingProgress.value = 0;
  } finally {
    // Keep loading for a brief moment to show completion
    if (!error.value) {
      statusMessage.value = "Appointment created successfully!";
      loadingProgress.value = 100;
      await new Promise((resolve) => setTimeout(resolve, 800));
    }

    isCreating.value = false;
    loadingProgress.value = 0;
  }
}

const handleSubmit = async () => {
  // Clear any previous errors
  error.value = "";

  // Validate the form - validation errors will be shown as toast notifications
  if (!validateForm()) {
    return;
  }

  // Differentiate between create and edit modes
  if (isCreateMode.value) {
    // Create mode: proceed with creating appointment documents
    await create_appointment_docs();
  } else if (props.mode === "edit") {
    // Edit mode: update existing appointment
    await update_appointment();
  }
};

async function update_appointment() {
  isCreating.value = true;
  error.value = null;
  loadingProgress.value = 0;

  try {
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
  onError: (err) => {
    handleResourceError(err);
    notifications.error.appointmentUpdateFailed(
      err.message || "Failed to cancel appointment"
    );
  },
});

const cancelAppointment = async () => {
  showCancelConfirmation.value = true;
};

const confirmCancelAppointment = async () => {
  showCancelConfirmation.value = false;
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
