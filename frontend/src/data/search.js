import { contains } from "./appointmentFilters.js";

/** Pages whose label or description contains the text: exact label first, then labels starting with it; input order is kept within each. */
export const matchPages = (pages, text) => {
  const query = text.trim().toLowerCase();
  const rank = (label) => {
    const lower = label.toLowerCase();
    if (lower === query) return 0;
    return lower.startsWith(query) ? 1 : 2;
  };
  return pages
    .filter(
      ({ label, description }) =>
        contains(label, text) || contains(description, text)
    )
    .sort((first, second) => rank(first.label) - rank(second.label));
};

/** The rows to show and whether more match; the server is asked for one row more than the page shows. */
export const splitPage = (rows, pageLength) => ({
  rows: pageLength ? rows.slice(0, pageLength) : rows,
  hasMore: Boolean(pageLength) && rows.length > pageLength,
});

// The server sends a time as "9:05:00", without the leading zero.
const toHoursMinutes = (time) => {
  const [hours, minutes] = String(time).split(":");
  return `${hours.padStart(2, "0")}:${minutes}`;
};

const joinDetails = (details) => details.filter(Boolean).join(" · ");

/** Search rows for the patients and appointments the server found; a patient opens in the desk, an appointment on the grid. */
export const toRecordResults = ({ patients, appointments }) => [
  ...patients.map((patient) => ({
    type: "patient",
    label: patient.patient_name,
    description: joinDetails([
      patient.value,
      patient.mobile,
      patient.card_no && `Card ${patient.card_no}`,
    ]),
    route: `/app/patient/${encodeURIComponent(patient.value)}`,
  })),
  ...appointments.map((appointment) => ({
    type: "appointment",
    label: `${appointment.patient_name} · ${
      appointment.appointment_date
    } ${toHoursMinutes(appointment.appointment_time)}`,
    description: joinDetails([
      appointment.practitioner_name,
      appointment.status,
      appointment.name,
    ]),
    query: {
      appointment: appointment.name,
      company: appointment.company,
      date: appointment.appointment_date,
    },
  })),
];

// Patients and appointments have their own sections, with the appointment opening on the grid.
const OWN_SECTION_DOCTYPES = ["Patient", "Patient Appointment"];

/** Global search rows of every other doctype the user may read; each opens in the desk. */
export const toOtherRecordResults = (rows) =>
  rows
    .filter(({ doctype }) => !OWN_SECTION_DOCTYPES.includes(doctype))
    .map(({ doctype, name }) => ({
      type: "record",
      label: name,
      description: doctype,
      route: `/app/${doctype
        .replace(/\s+/g, "-")
        .toLowerCase()}/${encodeURIComponent(name)}`,
    }));
