import { call } from "frappe-ui";

const INSURANCE_API = "hms_tz.api.appointment_insurance";

export const PAYMENT_OPTIONS = [
  { label: "Cash", value: "Cash" },
  { label: "NHIF", value: "NHIF" },
  { label: "Jubilee", value: "Jubilee" },
  { label: "Other insurance", value: "Other" },
];

export const SEARCH_PATIENTS_METHOD = `${INSURANCE_API}.search_patients`;

export const getInsuranceApiSettings = (company) =>
  call(`${INSURANCE_API}.get_insurance_api_settings`, { company });

export const checkCard = (company, provider, card_no, card_type) =>
  call(`${INSURANCE_API}.check_card`, {
    company,
    provider,
    card_no,
    card_type,
  });

export const getCardTypes = () =>
  call("hms_tz.nhif.api.patient.get_card_verifier");

export const searchSubscriptions = (provider, txt, patient) =>
  call(`${INSURANCE_API}.search_subscriptions`, { provider, txt, patient });

export const getSubscription = (name) =>
  call(`${INSURANCE_API}.get_subscription`, { name });

export const getPatient = (name) =>
  call(`${INSURANCE_API}.get_patient`, { name });

export const createPatient = (patient) =>
  call("frappe.client.insert", { doc: { doctype: "Patient", ...patient } });

export const createSubscription = (subscription_data) =>
  call(`${INSURANCE_API}.create_insurance_subscription`, {
    subscription_data,
  });

export const authorizeNhifPatient = (args) =>
  call(`${INSURANCE_API}.authorize_nhif_patient`, args);

export const authorizeJubileePatient = (args) =>
  call(`${INSURANCE_API}.authorize_jubilee_patient`, args);

export const getCashCharge = (args) =>
  call("hms_tz.api.appointment.get_cash_charge", args);

export const createAppointment = (appointment_data) =>
  call("hms_tz.api.appointment.create_appointment", { appointment_data });

export const authorizeJubileeAppointment = (appointment) =>
  call(`${INSURANCE_API}.authorize_jubilee_appointment`, { appointment });

export const authorizeNhifAppointment = (args) =>
  call(`${INSURANCE_API}.authorize_nhif_appointment`, args);
