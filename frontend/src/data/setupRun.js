/** Why Start setup is locked, or "" once the settings are complete and a room exists. */
export const getLockReason = (run) => {
  if (!run.setting)
    return "Create the HMS TZ Setting on the settings page first.";
  if (!run.settings_complete)
    return "Complete every group on the settings page first.";
  if (!run.has_rooms)
    return "Add at least one room on the rooms screen first.";
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
