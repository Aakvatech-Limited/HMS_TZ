/** First letter in capitals, for example "doctors" to "Doctors". */
export const capitalize = (text = "") =>
  text.charAt(0).toUpperCase() + text.slice(1);

/** Number of records with the screen's label, for example "3 doctors", or "First 500 coverages" when more match. */
export const getCountText = (count, screen, hasMore = false) => {
  const text = `${count} ${count === 1 ? screen.label : screen.plural_label}`;
  return hasMore ? `First ${text}, filter to see the others` : text;
};

/** Dialog fields; a set_only_once field, such as the one that names the record, is read only when changing it. */
export const getDialogFields = (fields, isEditing) =>
  fields.map((field) => ({
    ...field,
    read_only: field.read_only || (isEditing && Boolean(field.set_only_once)),
  }));

const ACTIVE_STATUSES = ["Queued", "Running"];

/** Whether a background run of an action is still queued or running. */
export const isRunActive = (run) =>
  Boolean(run && ACTIVE_STATUSES.includes(run.status));

/** Dropdown options of one action group; a click queues that action, unless it is still running. */
export const getActionOptions = (group, runs, runAction) =>
  group.actions.map((action) => ({
    label: action.label,
    disabled: isRunActive(runs[action.key]),
    onClick: () => runAction(action),
  }));

/** Whether an action of this group is still running, so its dropdown shows the spinner. */
export const isGroupRunning = (group, runs) =>
  group.actions.some((action) => isRunActive(runs[action.key]));

/** Every action of the groups with its last run, or null when it never ran, in dropdown order. */
export const getRunRows = (groups, runs) =>
  groups.flatMap((group) =>
    group.actions.map((action) => ({
      ...action,
      run: runs[action.key] || null,
    }))
  );
