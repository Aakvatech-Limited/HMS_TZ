import { useToast as useVueToastification } from "vue-toastification";

/** Plain text with line breaks kept: tags and entities removed. */
export const toPlainText = (text) => {
  const withBreaks = String(text ?? "").replace(
    /<br\s*\/?>|<\/(p|div|h\d|li)>/gi,
    "\n"
  );
  const plain =
    new DOMParser().parseFromString(withBreaks, "text/html").body
      .textContent || "";
  return plain
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .join("\n")
    .trim();
};

/** One line of plain text from a server message. */
export const htmlToText = (html) =>
  toPlainText(html).replace(/\s+/g, " ").trim();

/**
 * Messages of a failed frappe call, one per entry.
 * Frappe sends the raised error last, so it is moved first; a MandatoryError keeps the field order.
 */
export const serverErrors = (error) => {
  const messages = (error?.messages || []).map(htmlToText).filter(Boolean);
  if (!messages.length) {
    return [
      htmlToText(error?.message) || "The request failed. Please try again.",
    ];
  }
  if (error.exc_type !== "MandatoryError") messages.unshift(messages.pop());
  return [...new Set(messages)];
};

export const serverErrorText = (error) => {
  const errors = serverErrors(error);
  if (errors.length === 1) return errors[0];
  return errors.map((e) => `• ${e}`).join("\n");
};

export const useToast = () => {
  const toast = useVueToastification();

  /** Every toast passes here, so server HTML never reaches the user. */
  const showToast = (html, type = "info", options = {}) => {
    const message = toPlainText(html);
    const defaultOptions = {
      timeout: options.timeout || 5000, // Default to 5 seconds for better readability
      position: options.position || "bottom-right",
      hideProgressBar: true,
      closeOnClick: true,
      pauseOnHover: true,
      draggable: true,
      icon: true,
      ...options,
    };

    switch (type) {
      case "success":
        toast.success(message, defaultOptions);
        break;
      case "error":
        toast.error(message, {
          ...defaultOptions,
          timeout: options.timeout || 5000,
        }); // Longer timeout for errors
        break;
      case "warning":
        toast.warning(message, defaultOptions);
        break;
      case "info":
        toast.info(message, defaultOptions);
        break;
      default:
        toast(message, defaultOptions);
    }
  };

  const showSuccess = (message, options = {}) => {
    showToast(message, "success", options);
  };

  const showError = (message, options = {}) => {
    showToast(message, "error", options);
  };

  const showWarning = (message, options = {}) => {
    showToast(message, "warning", options);
  };

  const showInfo = (message, options = {}) => {
    showToast(message, "info", options);
  };

  const clear = () => {
    toast.clear();
  };

  // Patient Appointment specific toast notifications for HMS TZ
  const notifySuccess = {
    appointmentCreated: () => showSuccess("Appointment created successfully!"),
    appointmentUpdated: () => showSuccess("Appointment updated successfully!"),
    appointmentCancelled: () =>
      showSuccess("Appointment cancelled successfully!"),
    appointmentRescheduled: () =>
      showSuccess("Appointment rescheduled successfully!"),
    patientCreated: () => showSuccess("Patient created successfully!"),
    dataRefreshed: () => showSuccess("Data refreshed successfully!"),
    generic: (message) => showSuccess(message),
  };

  // Appointment error messages
  const notifyError = {
    appointmentCreateFailed: (error = "") =>
      showError("Failed to create appointment"),
    appointmentUpdateFailed: (error = "") =>
      showError("Failed to update appointment"),
    appointmentDeleteFailed: (error = "") =>
      showError("Failed to cancel appointment"),
    dataLoadFailed: (error = "") => showError("Failed to load data"),
    patientCreateFailed: (error = "") => showError("Failed to create patient"),
    validationFailed: () => showError("Please fix the form errors"),
    networkError: () =>
      showError("Network error. Please check your connection"),
    serverError: () => showError("Server error. Please try again later"),
    generic: (message) => showError(message),
  };

  // Appointment warning messages
  const notifyWarning = {
    pastTimeSlot: () => showWarning("Cannot book appointments in the past"),
    practitionerUnavailable: () =>
      showWarning("Practitioner is not available at this time"),
    duplicateAppointment: () =>
      showWarning("An appointment already exists at this time"),
    insufficientBuffer: () =>
      showWarning(
        "Appointments must be booked at least 15 minutes in advance"
      ),
    unsavedChanges: () => showWarning("You have unsaved changes"),
  };

  // Appointment info messages
  const notifyInfo = {
    loadingData: () => showInfo("Loading appointments..."),
    savingData: () => showInfo("Saving appointment..."),
    processingRequest: () => showInfo("Processing your request..."),
  };

  const handleResourceError = (error) => {
    showError(serverErrorText(error), { timeout: 10000 });
  };

  // Convenience object for easy access to notification methods
  const notifications = {
    success: notifySuccess,
    error: notifyError,
    warning: notifyWarning,
    info: notifyInfo,
  };

  return {
    showToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    clear,
    notifySuccess,
    notifyError,
    notifyWarning,
    notifyInfo,
    handleResourceError,
    notifications,
  };
};
