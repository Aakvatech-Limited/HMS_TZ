import assert from "node:assert/strict";
import { test } from "node:test";
import {
  matchPages,
  splitPage,
  toOtherRecordResults,
  toRecordResults,
} from "../src/data/search.js";

const page = (label) => ({ label, description: `${label} List` });
const PAGES = [
  "Inpatient Record",
  "NHIF Patient Claim",
  "Patient",
  "Patient Appointment",
  "Nurse Roster",
].map(page);

test("exact label first, then labels starting with the text", () => {
  assert.deepEqual(
    matchPages(PAGES, " PATIENT ").map(({ label }) => label),
    [
      "Patient",
      "Patient Appointment",
      "Inpatient Record",
      "NHIF Patient Claim",
    ]
  );
});

test("matches the description too", () => {
  assert.deepEqual(
    matchPages(PAGES, "roster list").map(({ label }) => label),
    ["Nurse Roster"]
  );
});

test("a page shows its rows and tells when the server had more", () => {
  const rows = [1, 2, 3];
  assert.deepEqual(splitPage(rows, 2), { rows: [1, 2], hasMore: true });
  assert.deepEqual(splitPage(rows, 3), { rows: [1, 2, 3], hasMore: false });
  assert.deepEqual(splitPage([], 20), { rows: [], hasMore: false });
});

test("without a page length every row shows", () => {
  assert.deepEqual(splitPage([1, 2, 3], 0), {
    rows: [1, 2, 3],
    hasMore: false,
  });
});

test("a patient row shows its ID, mobile and card no and opens the Patient", () => {
  const [row] = toRecordResults({
    patients: [
      {
        value: "HLC-PAT-52566",
        patient_name: "Ian Biteme",
        mobile: "255754100014",
        card_no: "",
      },
    ],
    appointments: [],
  });
  assert.equal(row.type, "patient");
  assert.equal(row.label, "Ian Biteme");
  assert.equal(row.description, "HLC-PAT-52566 · 255754100014");
  assert.equal(row.route, "/app/patient/HLC-PAT-52566");
});

test("an appointment row names its date and time and points the grid at it", () => {
  const [row] = toRecordResults({
    patients: [],
    appointments: [
      {
        name: "HLC-APP-2026-00028",
        patient_name: "Ian Biteme",
        practitioner_name: "Dr.Ronald Mclarty",
        appointment_date: "2026-11-22",
        appointment_time: "9:05:00",
        status: "Open",
        company: "Shree Hindu Mandal Hospital - Mwanza",
      },
    ],
  });
  assert.equal(row.type, "appointment");
  assert.equal(row.label, "Ian Biteme · 2026-11-22 09:05");
  assert.equal(
    row.description,
    "Dr.Ronald Mclarty · Open · HLC-APP-2026-00028"
  );
  assert.deepEqual(row.query, {
    appointment: "HLC-APP-2026-00028",
    company: "Shree Hindu Mandal Hospital - Mwanza",
    date: "2026-11-22",
  });
});

test("other global search rows open their desk form; patients and appointments are left to their own sections", () => {
  const rows = toOtherRecordResults([
    { doctype: "Customer", name: "Ian Biteme" },
    { doctype: "Patient", name: "HLC-PAT-52566" },
    { doctype: "Patient Appointment", name: "HLC-APP-2026-00028" },
    { doctype: "Healthcare Insurance Subscription", name: "HIS-2026-00002" },
  ]);
  assert.deepEqual(rows, [
    {
      type: "record",
      label: "Ian Biteme",
      description: "Customer",
      route: "/app/customer/Ian%20Biteme",
    },
    {
      type: "record",
      label: "HIS-2026-00002",
      description: "Healthcare Insurance Subscription",
      route: "/app/healthcare-insurance-subscription/HIS-2026-00002",
    },
  ]);
});
