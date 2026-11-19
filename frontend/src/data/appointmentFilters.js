/** Appointments grid filters. Text filters match by "contains", as a desk list "like" filter; selects match exactly. */
export const EMPTY_APPOINTMENT_FILTERS = Object.freeze({
  patient_name: "",
  status: "",
  payment: "",
  coverage_plan_name: "",
  billing_item: "",
  appointment_type: "",
  follow_up: false,
  apply_fasttrack_charge: false,
});

/** Practitioner and department filters pick grid columns, so a column keeps all its cards. */
export const EMPTY_PRACTITIONER_FILTERS = Object.freeze({
  practitioner: "",
  department: "",
});

/** The create-mode payment tab of an appointment; insurance companies are told apart by name, as in provider_condition. */
export const getPaymentOption = (isInsurance, insuranceCompany) => {
  if (!isInsurance) return "Cash";
  if (insuranceCompany.includes("NHIF")) return "NHIF";
  return insuranceCompany.includes("Jubilee") ? "Jubilee" : "Other";
};

export const contains = (value, text) => {
  const needle = text.trim().toLowerCase();
  return !needle || (value || "").toLowerCase().includes(needle);
};

const equals = (value, selected) => !selected || value === selected;

const isTicked = (value, ticked) => !ticked || Boolean(value);

export const matchesAppointment = (appointment, filters) =>
  contains(appointment.patient_name, filters.patient_name) &&
  equals(appointment.status, filters.status) &&
  equals(appointment.payment, filters.payment) &&
  contains(appointment.coverage_plan_name, filters.coverage_plan_name) &&
  contains(appointment.billing_item, filters.billing_item) &&
  contains(appointment.appointment_type, filters.appointment_type) &&
  isTicked(appointment.follow_up, filters.follow_up) &&
  isTicked(appointment.apply_fasttrack_charge, filters.apply_fasttrack_charge);

export const matchesPractitioner = (practitioner, filters) =>
  contains(practitioner.name, filters.practitioner) &&
  contains(practitioner.department, filters.department);

export const countActiveFilters = (filters) =>
  Object.values(filters).filter((value) =>
    typeof value === "string" ? value.trim() : value
  ).length;

/** The time slots and practitioners that hold a filtered appointment; a slot counts only if its match is in a shown column. */
export const getMatchedGrid = (
  timeSlots,
  practitioners,
  appointmentsBySlot
) => {
  const withMatches = new Set();
  for (const byPractitioner of appointmentsBySlot.values())
    for (const name of byPractitioner.keys()) withMatches.add(name);
  const shown = practitioners.filter(({ name }) => withMatches.has(name));
  const shownNames = new Set(shown.map(({ name }) => name));
  return {
    slots: timeSlots.filter((slot) =>
      [...(appointmentsBySlot.get(slot.time)?.keys() ?? [])].some((name) =>
        shownNames.has(name)
      )
    ),
    practitioners: shown,
  };
};
