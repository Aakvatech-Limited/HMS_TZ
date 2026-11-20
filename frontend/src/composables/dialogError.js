import { hasInjectionContext, inject, provide, ref } from "vue";

const DIALOG_ERROR = Symbol("dialogError");

/** Owns the error a dialog shows; errors reported by components inside it land here instead of a toast. */
export const provideDialogError = () => {
  const dialogError = ref(null);
  provide(DIALOG_ERROR, dialogError);
  return dialogError;
};

/** The error of the nearest dialog, or null outside a dialog. */
export const injectDialogError = () =>
  hasInjectionContext() ? inject(DIALOG_ERROR, null) : null;

/** The title and message an insurance provider sent with a ProviderReplyError, else null. */
export const providerReplyOf = (error) =>
  error?.exc_type === "ProviderReplyError"
    ? JSON.parse(error.messages[0])
    : null;
