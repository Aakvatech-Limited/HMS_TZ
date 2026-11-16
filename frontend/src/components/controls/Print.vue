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
import { ref, computed, onMounted } from "vue";
import { createResource } from "frappe-ui";
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

// Create resource to fetch default print format from Property Setter
const printFormatResource = createResource({
  url: "frappe.client.get_list",
  method: "GET",
  auto: false,
  makeParams() {
    return {
      doctype: "Property Setter",
      filters: {
        doc_type: props.doctype,
        property: "default_print_format",
        doctype_or_field: "DocType",
      },
      fields: ["value"],
      limit_page_length: 1,
    };
  },
  onSuccess: (data) => {
    if (data && data.length > 0 && data[0].value) {
      console.log("Fetched print format from Property Setter:", data);
      defaultPrintFormat.value = data[0].value;
      emit("format-fetched", data[0].value);
    } else {
      // Fallback logic based on doctype
      if (props.doctype === "Sales Invoice") {
        defaultPrintFormat.value = "AV Tax Invoice"; // Specific fallback for Sales Invoice
      } else {
        defaultPrintFormat.value = "Standard"; // General fallback
      }
      emit("format-fetched", defaultPrintFormat.value);
    }
    formatFetched.value = true;
  },
  onError: (err) => {
    console.error("Error fetching default print format:", err);
    // Fallback logic based on doctype
    if (props.doctype === "Sales Invoice") {
      defaultPrintFormat.value = "AV Tax Invoice"; // Specific fallback for Sales Invoice
    } else {
      defaultPrintFormat.value = "Standard"; // General fallback
    }
    formatFetched.value = true;
    emit("format-fetched", defaultPrintFormat.value);
  },
});

// Methods
const fetchDefaultPrintFormat = async () => {
  if (!props.doctype) {
    throw new Error("Doctype is required to fetch print format");
  }

  try {
    await printFormatResource.submit();
  } catch (error) {
    console.error("Failed to fetch print format:", error);
    // Set fallback format based on doctype
    if (props.doctype === "Sales Invoice") {
      defaultPrintFormat.value = "AV Tax Invoice"; // Specific fallback for Sales Invoice
    } else {
      defaultPrintFormat.value = "Standard"; // General fallback
    }
    formatFetched.value = true;
  }
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

    // Use the print format from Property Setter or fall back to "AV Tax Invoice" for Sales Invoice
    const print_format =
      defaultPrintFormat.value ||
      (props.doctype === "Sales Invoice" ? "AV Tax Invoice" : "Standard");

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

// Lifecycle
onMounted(() => {
  // Pre-fetch the default print format when component mounts
  if (props.doctype) {
    fetchDefaultPrintFormat();
  }
});

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
