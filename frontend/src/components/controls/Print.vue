<template>
  <Button
    :variant="variant"
    :size="size"
    :theme="theme"
    :disabled="disabled || isLoading"
    @click="handlePrint"
    :class="buttonClass"
    :title="title || `Print ${doctype}`"
  >
    <template #prefix v-if="showIcon">
      <FeatherIcon name="printer" class="w-4 h-4" />
    </template>
    <LoadingIndicator v-if="isLoading" class="w-4 h-4" />
    <template v-else>
      {{ label || "Print" }}
    </template>
  </Button>
</template>

<script setup>
import { ref, computed } from "vue";
import { call, createResource } from "frappe-ui";
import { useToast } from "@/composables/useToast";

// Props
const props = defineProps({
  // Required props
  doctype: {
    type: String,
    required: true,
    validator: (value) => value && value.trim().length > 0,
  },
  docname: {
    type: String,
    required: true,
    validator: (value) => value && value.trim().length > 0,
  },

  // Optional props for customization
  variant: {
    type: String,
    default: "subtle",
  },
  size: {
    type: String,
    default: "lg",
  },
  theme: {
    type: String,
    default: "green",
  },
  label: {
    type: String,
    default: "Print",
  },
  title: {
    type: String,
    default: "",
  },
  showIcon: {
    type: Boolean,
    default: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  buttonClass: {
    type: String,
    default: "font-semibold inline-flex items-center",
  },

  // Print options
  autoTriggerPrint: {
    type: Boolean,
    default: true,
  },
  windowOptions: {
    type: String,
    default: "width=1000,height=700,scrollbars=yes,resizable=yes",
  },

  // Advanced options
  letterhead: {
    type: String,
    default: "No Letterhead",
  },
  noLetterhead: {
    type: [Boolean, Number],
    default: 0,
  },
  settings: {
    type: Object,
    default: () => ({}),
  },
  language: {
    type: String,
    default: "en",
  },
});

// Emits
const emit = defineEmits([
  "print-started",
  "print-success",
  "print-error",
  "format-fetched",
]);

// Composables
const { notifications } = useToast();

// Reactive state
const isLoading = ref(false);
const defaultPrintFormat = ref(null);
const formatFetched = ref(false);

const fallbackPrintFormat = () =>
  props.doctype === "Sales Invoice" ? "AV Tax Invoice" : "Standard";

/** The default print format set in the desk; the fallback only when none is set. */
const fetchDefaultPrintFormat = async () => {
  const printFormat = await call(
    "hms_tz.api.appointment.get_default_print_format",
    { doctype: props.doctype }
  );
  defaultPrintFormat.value = printFormat || fallbackPrintFormat();
  formatFetched.value = true;
  emit("format-fetched", defaultPrintFormat.value);
};

const handlePrint = async () => {
  if (!props.doctype || !props.docname) {
    notifications.error.generic(
      "Document type and name are required for printing"
    );
    emit("print-error", "Document type and name are required");
    return;
  }

  isLoading.value = true;
  emit("print-started");

  try {
    // Fetch print format if not already fetched
    if (!formatFetched.value) {
      await fetchDefaultPrintFormat();
    }

    let letter_head = 0; // Default to no letterhead

    // For Sales Invoice, get the letter_head from the document
    if (props.doctype === "Sales Invoice") {
      try {
        const getSalesInvoice = createResource({
          url: "frappe.client.get",
          method: "GET",
          auto: false,
          makeParams() {
            return {
              doctype: "Sales Invoice",
              name: props.docname,
            };
          },
        });

        const salesInvoiceData = await getSalesInvoice.submit();
        if (salesInvoiceData && salesInvoiceData.letter_head) {
          letter_head = 0; // If letter_head exists, set no_letterhead to 0
        } else {
          letter_head = 1; // If no letter_head, set no_letterhead to 1
        }
      } catch (error) {
        console.warn(
          "Failed to get letter_head from Sales Invoice, using default:",
          error
        );
        letter_head = 1;
      }
    } else {
      // For other doctypes, use the letterhead prop
      letter_head = props.noLetterhead;
    }

    const print_format = defaultPrintFormat.value;

    // Construct URL exactly like the working load_print_page function
    const baseUrl = window.location.origin;
    const url =
      baseUrl +
      "/printview?doctype=" +
      encodeURIComponent(props.doctype) +
      "&name=" +
      encodeURIComponent(props.docname) +
      "&trigger_print=" +
      (props.autoTriggerPrint ? 1 : 0) +
      "&format=" +
      encodeURIComponent(print_format);
    // +
    // "&no_letterhead=1"
    // + letter_head

    console.log("Print URL:", url); // Debug log

    // Open print window exactly like the working example
    const printWindow = window.open(url, "Print");

    if (!printWindow) {
      // Fallback if popup blocked
      notifications.error.generic("Please allow popups to print the document");
      emit("print-error", "Popup blocked");
      return;
    }

    emit("print-success", {
      doctype: props.doctype,
      docname: props.docname,
      format: print_format,
      url: url,
    });

    console.log("Print initiated successfully:", props.docname);
    notifications.success.generic("Print dialog opened successfully");
  } catch (error) {
    console.error("Error printing document:", error);
    notifications.error.generic(
      `Error opening print dialog: ${error.message}`
    );
    emit("print-error", error.message);
  } finally {
    isLoading.value = false;
  }
};

// Expose methods for parent components
defineExpose({
  print: handlePrint,
  fetchFormat: fetchDefaultPrintFormat,
  printFormat: computed(() => defaultPrintFormat.value),
  isLoading: computed(() => isLoading.value),
});
</script>

<style scoped>
/* Component-specific styles if needed */
.print-button-loading {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
