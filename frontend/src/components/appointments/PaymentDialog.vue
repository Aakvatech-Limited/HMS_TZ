<template>
  <Dialog
    :model-value="showDialog"
    @update:model-value="emit('update:showDialog', $event)"
    :options="{
      title: 'Make Payment',
      size: '4xl',
      icon: {
        name: 'dollar-sign',
        appearance: 'blue',
      },
    }"
    :disable-outside-click-to-close="true"
    class="payment-dialog-overlay z-[1060]"
  >
    <template #body-content>
      <div class="space-y-4 p-4">
        <!-- Amount to be Paid -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <div class="flex-shrink-0">
                <FeatherIcon
                  name="dollar-sign"
                  class="h-5 w-5 text-blue-600"
                />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-blue-900">
                  Total Amount to be Paid
                </h3>
              </div>
            </div>
            <div class="text-right">
              <div class="text-2xl font-bold text-blue-900">
                {{ formatCurrency(totalAmountToPay) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Loading State for Mode of Payments -->
        <div
          v-if="isLoadingModeOfPayments"
          class="flex items-center justify-center py-8"
        >
          <div class="inline-flex items-center space-x-2 text-blue-600">
            <div
              class="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"
            ></div>
            <span class="text-sm font-medium">Loading payment methods...</span>
          </div>
        </div>

        <!-- Error State for Mode of Payments -->
        <div
          v-else-if="modeOfPaymentError"
          class="bg-red-50 border border-red-200 rounded-lg p-4"
        >
          <div class="flex items-center space-x-3">
            <div class="flex-shrink-0">
              <FeatherIcon name="x-circle" class="h-4 w-4 text-red-600" />
            </div>
            <div>
              <p class="text-sm text-red-700">Error loading payment methods</p>
              <h3 class="text-base font-medium text-red-800 mt-1">
                {{ modeOfPaymentError }}
              </h3>
            </div>
          </div>
          <div class="mt-4">
            <Button
              variant="subtle"
              size="md"
              theme="red"
              @click="fetchModeOfPayments"
            >
              <template #prefix>
                <FeatherIcon name="refresh-cw" class="w-4 h-4" />
              </template>
              Retry
            </Button>
          </div>
        </div>

        <!-- Mode of Payment Table -->
        <div
          v-else-if="modeOfPayments.length > 0"
          class="bg-white border border-gray-200 rounded-lg overflow-hidden"
        >
          <div class="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900 text-center">
              Payment Methods
            </h3>
          </div>

          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th
                    class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Payment Method
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Amount (TZS)
                  </th>
                  <th
                    class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    Payment Reference
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr
                  v-for="(payment, index) in paymentEntries"
                  :key="payment.mode_of_payment"
                  class="hover:bg-gray-50"
                >
                  <!-- Payment Method -->
                  <td class="px-4 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <div
                          class="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center"
                        >
                          <svg
                            v-if="isCashPayment(payment.mode_of_payment)"
                            class="h-4 w-4 text-blue-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
                            ></path>
                          </svg>
                          <svg
                            v-else
                            class="h-4 w-4 text-blue-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                            ></path>
                          </svg>
                        </div>
                      </div>
                      <div class="ml-4">
                        <div class="text-sm font-medium text-gray-900">
                          {{ payment.mode_of_payment }}
                        </div>
                        <div class="text-sm text-gray-500">
                          {{ payment.type }}
                        </div>
                      </div>
                    </div>
                  </td>

                  <!-- Amount Input -->
                  <td class="px-4 py-4 whitespace-nowrap">
                    <div class="relative">
                      <input
                        v-model.number="payment.amount"
                        type="number"
                        step="0.01"
                        min="0"
                        :max="totalAmountToPay"
                        class="block w-full min-w-[12rem] px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 text-lg font-semibold"
                        placeholder="0.00"
                        :class="{
                          'border-red-300 ring-red-500':
                            errors[`amount_${index}`],
                        }"
                        @input="validatePaymentEntry(index)"
                      />
                      <p
                        v-if="errors[`amount_${index}`]"
                        class="mt-1 text-xs text-red-600"
                      >
                        {{ errors[`amount_${index}`] }}
                      </p>
                    </div>
                  </td>

                  <!-- Payment Reference -->
                  <td class="px-4 py-4 whitespace-nowrap">
                    <div class="relative">
                      <input
                        v-model="payment.payment_reference"
                        type="text"
                        class="block w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 text-sm"
                        :class="{
                          'border-red-300 ring-red-500':
                            errors[`payment_reference_${index}`],
                        }"
                        :required="
                          !isCashPayment(payment.mode_of_payment) &&
                          payment.amount > 0
                        "
                        @input="validatePaymentEntry(index)"
                      />
                      <p
                        v-if="errors[`payment_reference_${index}`]"
                        class="mt-1 text-xs text-red-600"
                      >
                        {{ errors[`payment_reference_${index}`] }}
                      </p>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Payment Summary -->
          <div class="px-6 py-4 bg-gray-50 border-t border-gray-200">
            <div class="flex justify-between items-center">
              <div class="text-sm text-gray-600">
                <span>Total Distributed: </span>
                <span class="font-medium" :class="getTotalDistributedColor()">
                  {{ formatCurrency(getTotalDistributed()) }}
                </span>
              </div>
              <div class="text-sm text-gray-600">
                <span>Remaining: </span>
                <span class="font-medium" :class="getRemainingAmountColor()">
                  {{ formatCurrency(getRemainingAmount()) }}
                </span>
              </div>
            </div>
            <div v-if="getRemainingAmount() !== 0" class="mt-2">
              <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  class="h-full transition-all duration-300"
                  :class="
                    getRemainingAmount() > 0 ? 'bg-yellow-400' : 'bg-red-400'
                  "
                  :style="{
                    width: `${Math.min(
                      100,
                      (Math.abs(getRemainingAmount()) / totalAmountToPay) * 100
                    )}%`,
                  }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- No Payment Methods Found -->
        <div
          v-else
          class="bg-yellow-50 border border-yellow-200 rounded-lg p-4"
        >
          <div class="flex items-center space-x-3">
            <div class="flex-shrink-0">
              <div
                class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-yellow-100"
              >
                <FeatherIcon
                  name="alert-triangle"
                  class="h-6 w-6 text-yellow-600"
                />
              </div>
            </div>
            <div>
              <h3 class="text-sm font-medium text-yellow-800">
                No payment methods available
              </h3>
              <p class="text-sm text-yellow-700 mt-1">
                Please contact your administrator to set up payment methods.
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex gap-3 justify-between">
        <div class="flex items-center">
          <Button
            variant="subtle"
            size="lg"
            theme="gray"
            :disabled="isProcessingPayment"
            @click="closeDialog()"
          >
            <template #prefix>
              <FeatherIcon name="x" class="w-4 h-4" />
            </template>
            Close
          </Button>
        </div>

        <div class="flex gap-2">
          <Button
            variant="subtle"
            size="lg"
            theme="gray"
            :disabled="isProcessingPayment || isLoadingModeOfPayments"
            @click="resetPayments()"
          >
            <template #prefix>
              <FeatherIcon name="refresh-cw" class="w-4 h-4" />
            </template>
            Reset
          </Button>

          <div v-if="getRemainingAmount() === 0">
            <Button
              variant="subtle"
              size="lg"
              theme="blue"
              :loading="isProcessingPayment"
              :disabled="!canProcessPayment"
              @click="processPayment()"
            >
              <template v-if="!isProcessingPayment" #prefix>
                <FeatherIcon name="credit-card" class="w-4 h-4" />
              </template>
              {{ isProcessingPayment ? "Processing..." : "Create Invoice" }}
            </Button>
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, watch, ref } from "vue";
import { createResource } from "frappe-ui";
import { serverErrorText, useToast } from "@/composables/useToast";
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue";

// Props
const props = defineProps({
  showDialog: {
    type: Boolean,
    default: false,
  },
  appointmentData: {
    type: Object,
    default: () => ({}),
  },
});

// Emits
const emit = defineEmits(["update:showDialog", "paymentCompleted"]);

// Composables
const { notifications } = useToast();

// Reactive state
const modeOfPayments = ref([]);
const paymentEntries = ref([]);
const totalAmountToPay = computed(
  () => Number.parseFloat(props.appointmentData?.paid_amount) || 0
);
const isLoadingModeOfPayments = ref(false);
const isProcessingPayment = ref(false);
const modeOfPaymentError = ref("");
const errors = reactive({});

// Resource to fetch mode of payments
const modeOfPaymentResource = createResource({
  url: "hms_tz.api.appointment.get_mode_of_payment",
  method: "GET",
  auto: false,
  onSuccess: (data) => {
    modeOfPayments.value = data || [];
    initializePaymentEntries();
    isLoadingModeOfPayments.value = false;
    modeOfPaymentError.value = "";
  },
  onError: (error) => {
    modeOfPaymentError.value = serverErrorText(error);
    isLoadingModeOfPayments.value = false;
    modeOfPayments.value = [];
  },
});

// Resource to create invoice with payments
const salesInvoiceResource = createResource({
  url: "hms_tz.nhif.api.patient_appointment.invoice_appointment",
  method: "POST",
  auto: false,
  onSuccess: (data) => {
    notifications.success.generic("Payment processed successfully!");
    emit("paymentCompleted", { paymentData: data });
    closeDialog();

    isProcessingPayment.value = false;
  },
  onError: (error) => {
    notifications.error.generic(serverErrorText(error));
    isProcessingPayment.value = false;
  },
});

const initializePaymentEntries = () => {
  paymentEntries.value = modeOfPayments.value.map((mop) => ({
    mode_of_payment: mop.mode_of_payment,
    type: mop.type,
  }));
  resetPayments();
};

// Fetch mode of payments
const fetchModeOfPayments = () => {
  isLoadingModeOfPayments.value = true;
  modeOfPaymentError.value = "";
  modeOfPaymentResource.fetch();
};

// Helper functions
const isCashPayment = (paymentMethod) => {
  return paymentMethod && paymentMethod.toLowerCase().includes("cash");
};

const formatCurrency = (amount) => {
  return new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency: "TZS",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount || 0);
};

const getTotalDistributed = () => {
  return paymentEntries.value.reduce(
    (total, entry) => total + (entry.amount || 0),
    0
  );
};

const getRemainingAmount = () => {
  return totalAmountToPay.value - getTotalDistributed();
};

const getTotalDistributedColor = () => {
  const total = getTotalDistributed();
  if (total === totalAmountToPay.value && total > 0) return "text-green-600";
  if (total > totalAmountToPay.value) return "text-red-600";
  return "text-gray-900";
};

const getRemainingAmountColor = () => {
  const remaining = getRemainingAmount();
  if (remaining === 0) return "text-green-600";
  if (remaining < 0) return "text-red-600";
  return "text-yellow-600";
};

// Validation
const validatePaymentEntry = (index) => {
  const entry = paymentEntries.value[index];

  // Clear previous errors for this entry
  delete errors[`amount_${index}`];
  delete errors[`payment_reference_${index}`];

  // Validate amount
  if (entry.amount < 0) {
    errors[`amount_${index}`] = "Amount cannot be negative";
  }

  // Validate payment reference for non-cash payments
  if (
    !isCashPayment(entry.mode_of_payment) &&
    entry.amount > 0 &&
    !entry.payment_reference.trim()
  ) {
    errors[`payment_reference_${index}`] = "Payment reference is required";
  }
};

const clearErrors = () => {
  for (const key of Object.keys(errors)) delete errors[key];
};

const validateAllPayments = () => {
  clearErrors();

  // Validate total amount (should be automatically set from appointment)
  if (!totalAmountToPay.value || totalAmountToPay.value <= 0) {
    errors.totalAmount = "No amount to pay found from appointment";
    return false;
  }

  // Validate payment entries
  let hasValidPayment = false;
  paymentEntries.value.forEach((entry, index) => {
    validatePaymentEntry(index);
    if (entry.amount > 0) {
      hasValidPayment = true;
    }
  });

  if (!hasValidPayment) {
    errors.totalAmount = "Please distribute the amount across payment methods";
    return false;
  }

  // Check if total distributed matches total amount
  const remaining = getRemainingAmount();
  if (remaining !== 0) {
    errors.totalAmount =
      remaining > 0
        ? `Please distribute the remaining ${formatCurrency(remaining)}`
        : `Total distributed exceeds amount by ${formatCurrency(
            Math.abs(remaining)
          )}`;
    return false;
  }

  return Object.keys(errors).length === 0;
};

// Computed properties
const canProcessPayment = computed(() => {
  return (
    !isProcessingPayment.value &&
    !isLoadingModeOfPayments.value &&
    modeOfPayments.value.length > 0 &&
    totalAmountToPay.value > 0 &&
    //  getRemainingAmount() === 0 &&
    paymentEntries.value.some((entry) => entry.amount > 0)
  );
});

const closeDialog = () => {
  emit("update:showDialog", false);
};

// Payment processing
const processPayment = () => {
  if (!validateAllPayments()) {
    notifications.error.generic(
      "Please fix the validation errors before proceeding"
    );
    return;
  }

  isProcessingPayment.value = true;

  // Get only entries with amounts > 0
  const activePayments = paymentEntries.value.filter(
    (entry) => entry.amount > 0
  );

  const paymentMethods = activePayments.map((entry) => ({
    mode_of_payment: entry.mode_of_payment,
    amount: entry.amount,
    payment_reference: entry.payment_reference || null,
  }));

  // Call the API to create
  salesInvoiceResource.submit({
    name: props.appointmentData.name,
    mops: paymentMethods,
  });
};

// Put the full amount on the first cash method so the cashier only confirms
const resetPayments = () => {
  const cashEntry = paymentEntries.value.find((entry) =>
    isCashPayment(entry.mode_of_payment)
  );
  for (const entry of paymentEntries.value) {
    entry.amount = entry === cashEntry ? totalAmountToPay.value : 0;
    entry.payment_reference = "";
  }
  clearErrors();
};

watch(
  () => props.showDialog,
  (isOpen) => {
    if (!isOpen) return;
    if (modeOfPayments.value.length) {
      resetPayments();
    } else {
      fetchModeOfPayments();
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.payment-dialog-overlay {
  z-index: 1060;
}

/* Custom scrollbar for table */
.overflow-x-auto::-webkit-scrollbar {
  height: 6px;
}

.overflow-x-auto::-webkit-scrollbar-track {
  background: #f1f5f9;
}

.overflow-x-auto::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.overflow-x-auto::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* Smooth transitions */
.transition-all {
  transition: all 0.3s ease;
}

/* Animation for gentle pulse */
@keyframes pulse-gentle {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.95;
  }
}

.animate-pulse-gentle {
  animation: pulse-gentle 2s infinite;
}
</style>
