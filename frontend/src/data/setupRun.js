/** Why Start setup is locked, or "" once the settings are complete. */
export const getLockReason = (run) => {
  if (!run.setting)
    return "Create the HMS TZ Setting on the settings page first.";
  if (!run.settings_complete)
    return "Complete every group on the settings page first.";
  return "";
};

const getAddedText = (added) => (added ? `${added} added` : "nothing missing");

/** Right-hand text of a step: its result and what it added, its progress while running, or its status. */
export const getStepState = (step) => {
  if (step.status === "Done") {
    return `${step.result || "done"}, ${getAddedText(step.added)}`;
  }
  if (step.status === "Running") {
    return step.total ? `${step.done} of ${step.total}` : "running";
  }
  return step.status.toLowerCase();
};

/** Health check of the last run once every step is done: what it added, or that nothing was missing. */
export const getRunReport = (steps) => {
  if (!steps.length || steps.some((step) => step.status !== "Done")) return "";
  const added = steps.reduce((sum, step) => sum + (step.added || 0), 0);
  if (!added) return "Nothing missing. The last run changed nothing.";
  const names = steps.filter((step) => step.added).map((step) => step.label);
  return `The last run added ${added} missing ${
    added === 1 ? "record" : "records"
  }: ${names.join(", ")}.`;
};

/** Badge text of a step another app registered, for example "Polyclinic step"; "" for HMS TZ steps. */
export const getStepOwner = (step) =>
  step.app && step.app !== "hms_tz"
    ? `${step.app_title || step.app} step`
    : "";

/** How far one step is, as a percentage; a finished step is full. */
export const getStepPercent = (step) => {
  if (step.status === "Done") return 100;
  return step.total ? Math.round((step.done / step.total) * 100) : 0;
};

/** Apply a live progress message of the setup job to the matching step of this setting. */
export const applyStepProgress = (run, message) => {
  if (!run || message.setting !== run.setting) return;
  const step = run.steps.find((row) => row.step === message.step);
  if (!step) return;
  const { setting, ...values } = message;
  Object.assign(step, values);
};
