// Keys and URL shared with frontend/src/data/appointmentsPageDefault.js.
const APPOINTMENT_DOCTYPE = "Patient Appointment";
const APPOINTMENTS_PAGE_URL = "/frontend/appointments";
const OPEN_BY_DEFAULT = "hms_tz_open_appointments_page";
const PAGE_TRIED = "hms_tz_appointments_page_tried";
const INTRO_SNOOZED_UNTIL = "hms_tz_appointments_page_intro_snoozed_until";
const INTRO_SNOOZE_MS = 24 * 60 * 60 * 1000;
const INTRO_CLICK = "click.hms_tz_appointments_page_intro";
const INTRO_READ_SECONDS = 5;
const INTRO_ROLES = [
  "Healthcare Receptionist",
  "Healthcare Head Receptionist",
];

const openAppointmentsPage = () =>
  window.location.assign(APPOINTMENTS_PAGE_URL);

const getAppointmentSettings = () =>
  frappe.get_user_settings(APPOINTMENT_DOCTYPE);

/** True on the plain Patient Appointment link (sidebar, workspace, search); a chosen view has /view/ in its path. */
const isOpenedByDoctypeLink = () =>
  frappe.router.get_sub_path() === frappe.router.slug(APPOINTMENT_DOCTYPE);

const openPageIfDefault = () => {
  if (isOpenedByDoctypeLink() && getAppointmentSettings()[OPEN_BY_DEFAULT]) {
    openAppointmentsPage();
  }
};

// The first list load runs onload; later visits reuse the list view, so only the router sees them.
// List scripts run again when the doctype meta reloads, and the router cannot unbind a handler.
frappe.provide("hms_tz.appointments_page");
if (!hms_tz.appointments_page.is_redirect_bound) {
  hms_tz.appointments_page.is_redirect_bound = true;
  frappe.router.on("change", openPageIfDefault);
}

const addAppointmentsPageView = (listview) => {
  if (!listview.views_menu) return;
  listview.page.add_custom_menu_item(
    listview.views_menu,
    __("Appointments Page"),
    openAppointmentsPage,
    true,
    null,
    "calendar"
  );
};

/** Try it opens the page, which records the user as having tried it; Not now asks again a day later. */
const closeIntro = (driver, tryIt) => {
  driver.reset();
  if (tryIt) {
    frappe.model.user_settings
      .save(APPOINTMENT_DOCTYPE, OPEN_BY_DEFAULT, 1)
      .then(openAppointmentsPage);
  } else {
    frappe.model.user_settings.save(
      APPOINTMENT_DOCTYPE,
      INTRO_SNOOZED_UNTIL,
      Date.now() + INTRO_SNOOZE_MS
    );
  }
};

/** Receptionists who never opened the Appointments Page and are not snoozed see the intro. */
const isIntroDue = () => {
  const settings = getAppointmentSettings();
  const isReceptionist = INTRO_ROLES.some((role) =>
    frappe.user.has_role(role)
  );
  return (
    isReceptionist &&
    !settings[PAGE_TRIED] &&
    Date.now() >= (settings[INTRO_SNOOZED_UNTIL] || 0)
  );
};

/** Note on the view switcher that introduces the Appointments Page. */
const showAppointmentsPageIntro = (listview) => {
  const switcher = listview.views_menu?.siblings("button").get(0);
  if (!switcher || !isIntroDue()) return;

  const driver = new frappe.Driver({
    className: "frappe-driver",
    allowClose: false,
    opacity: 0.25,
    padding: 6,
  });
  // Bound before the popover exists; driver.js calls no hook for a single highlight.
  $(document)
    .off(INTRO_CLICK)
    .on(INTRO_CLICK, ".hms-tz-intro-try, .hms-tz-intro-skip", (event) => {
      $(document).off(INTRO_CLICK);
      closeIntro(driver, $(event.currentTarget).hasClass("hms-tz-intro-try"));
    });
  driver.highlight({
    element: switcher,
    popover: {
      title: __("Try the new Appointments Page"),
      description: `<p style="color: var(--text-color); font-weight: 600; margin-bottom: 6px">
        ${__("Book patients faster and easier.")}
      </p>
      <ul style="padding-left: 18px; margin-bottom: 8px; color: var(--text-color)">
        <li>${__("See all doctors and free slots at a glance")}</li>
        <li>${__("Register new patients & HIS in the same form")}</li>
        <li>${__("Check NHIF and authorize Jubilee in one step")}</li>
        <li>${__("Take payment and print the bill quickly")}</li>
      </ul>
      <p>${__("Find it later in this menu.")}</p>
      <div class="d-flex justify-content-end" style="gap: 8px">
        <button class="btn btn-default btn-xs hms-tz-intro-skip" disabled>${__(
          "Not now ({0})",
          [INTRO_READ_SECONDS]
        )}</button>
        <button class="btn btn-primary btn-xs hms-tz-intro-try">${__(
          "Try it"
        )}</button>
      </div>`,
      position: "bottom",
      showButtons: false,
    },
  });
  holdSkipButton();
};

/** Not now unlocks after a short countdown, so the note is read before it is skipped. */
const holdSkipButton = (seconds = INTRO_READ_SECONDS) => {
  const $skip = $(".hms-tz-intro-skip");
  if (seconds <= 0) {
    $skip.text(__("Not now")).prop("disabled", false);
    return;
  }
  $skip.text(__("Not now ({0})", [seconds]));
  setTimeout(() => holdSkipButton(seconds - 1), 1000);
};

frappe.listview_settings[APPOINTMENT_DOCTYPE] ||= {};
const appointmentListSettings = frappe.listview_settings[APPOINTMENT_DOCTYPE];
const healthcareOnload = appointmentListSettings.onload;
appointmentListSettings.onload = (listview) => {
  healthcareOnload?.(listview);
  openPageIfDefault();
  // The view switcher is built after onload.
  listview.init_promise.then(() => {
    addAppointmentsPageView(listview);
    showAppointmentsPageIntro(listview);
  });
};
