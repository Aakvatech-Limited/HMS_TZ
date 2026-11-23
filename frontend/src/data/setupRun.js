/** Why Start setup is locked, or "" once the settings are complete. Steps that need rooms wait for one. */
export const getLockReason = (run) => {
  if (!run.setting)
    return "Create the HMS TZ Setting on the settings page first.";
  if (!run.settings_complete)
    return "Complete every group on the settings page first.";
  return "";
};

/** Right-hand text of a step: its result, its progress while running, or its status. */
export const getStepState = (step) => {
  if (step.status === "Done") return step.result || "done";
  if (step.status === "Running") {
    return step.total ? `${step.done} of ${step.total}` : "running";
  }
  return step.status.toLowerCase();
};

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
