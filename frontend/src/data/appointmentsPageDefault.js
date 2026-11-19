// Keys and URL shared with hms_tz/nhif/api/patient_appointment_list.js.
export const APPOINTMENT_DOCTYPE = "Patient Appointment";
export const OPEN_BY_DEFAULT = "hms_tz_open_appointments_page";
/** Set on every visit; once set, the desk intro for this page is not shown again. */
export const PAGE_TRIED = "hms_tz_appointments_page_tried";
/** The list view by its own route, so desk does not send the user back to this page. */
export const LIST_VIEW_URL = "/app/patient-appointment/view/list";

/** Whether the user's Patient Appointment list settings send them to the Appointments Page. */
export const isOpenByDefault = (userSettingsJson) =>
  Boolean(JSON.parse(userSettingsJson || "{}")[OPEN_BY_DEFAULT]);

export const toUserSettings = (openByDefault) =>
  JSON.stringify({ [OPEN_BY_DEFAULT]: openByDefault ? 1 : 0 });

export const PAGE_TRIED_SETTINGS = JSON.stringify({ [PAGE_TRIED]: 1 });
