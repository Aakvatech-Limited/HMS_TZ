import assert from "node:assert/strict";
import { test } from "node:test";
import { matchPages, splitPage } from "../src/data/search.js";

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
