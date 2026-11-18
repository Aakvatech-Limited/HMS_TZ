import assert from "node:assert/strict";
import { test } from "node:test";
import { matchPages } from "../src/data/search.js";

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
