import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  evaluateDependsOn,
  getSettingTabs,
  getVisibleSections,
  toSettingForm,
  toSettingValues,
} from "../src/data/setupSettings.js";

const NHIF_ON = "eval: doc.enable_nhif_api == 1";
const FIELDS = [
  { fieldname: "company", fieldtype: "Link", label: "Company", reqd: 1 },
  { fieldname: "facility_code", fieldtype: "Data", label: "Facility Code" },
  {
    fieldname: "encounter_section",
    fieldtype: "Section Break",
    label: "Encounter",
  },
  {
    fieldname: "notes_length",
    fieldtype: "Int",
    label: "Notes Length",
    default: "20",
  },
  { fieldname: "column_break", fieldtype: "Column Break" },
  {
    fieldname: "limit_action",
    fieldtype: "Select",
    label: "Limit Action",
    options: "\nWarn\nStop",
  },
  {
    fieldname: "cash_pharmacy",
    fieldtype: "Link",
    label: "Cash Pharmacy",
    options: "Healthcare Service Unit",
    link_filters: JSON.stringify([
      ["Healthcare Service Unit", "company", "=", "eval: doc.company"],
      ["Healthcare Service Unit", "disabled", "=", 0],
    ]),
  },
  { fieldname: "nhif_tab", fieldtype: "Tab Break", label: "NHIF" },
  {
    fieldname: "enable_nhif_api",
    fieldtype: "Check",
    label: "Enable NHIF API",
    default: "0",
  },
  {
    fieldname: "nhif_user",
    fieldtype: "Data",
    label: "NHIF User",
    depends_on: NHIF_ON,
  },
  {
    fieldname: "get_nhif_token",
    fieldtype: "Button",
    label: "Get NHIF Token",
  },
  {
    fieldname: "nhif_token",
    fieldtype: "Small Text",
    label: "NHIF Token",
    read_only: 1,
  },
  {
    fieldname: "dates_section",
    fieldtype: "Section Break",
    label: "Submit Dates",
    depends_on: NHIF_ON,
  },
  {
    fieldname: "submit_claim_month",
    fieldtype: "Int",
    label: "Submit Claim Month",
  },
  { fieldname: "jubilee_tab", fieldtype: "Tab Break", label: "Jubilee" },
  { fieldname: "jubilee_user", fieldtype: "Data", label: "Jubilee User" },
];

const tabs = getSettingTabs(FIELDS);
const fieldNames = (sections) =>
  sections.flatMap((section) => section.fields.map((field) => field.name));

describe("setup settings form", () => {
  test("tab breaks split the fields into Details, NHIF and Jubilee tabs", () => {
    assert.deepEqual(
      tabs.map((tab) => tab.label),
      ["Details", "NHIF", "Jubilee"]
    );
    assert.deepEqual(
      tabs[0].sections.map((section) => section.label),
      ["details", "Encounter"]
    );
  });

  test("company, buttons and read-only fields are left out", () => {
    const names = fieldNames(
      getVisibleSections(tabs[1], { enable_nhif_api: true }, "Clinic")
    );
    assert.deepEqual(names, [
      "enable_nhif_api",
      "nhif_user",
      "submit_claim_month",
    ]);
    const details = fieldNames(getVisibleSections(tabs[0], {}, "Clinic"));
    assert.ok(!details.includes("company"));
  });

  test("depends_on hides fields and sections while the switch is off", () => {
    const names = fieldNames(
      getVisibleSections(tabs[1], { enable_nhif_api: false }, "Clinic")
    );
    assert.deepEqual(names, ["enable_nhif_api"]);
  });

  test("a plain fieldname rule needs that field set", () => {
    assert.equal(
      evaluateDependsOn("enable_nhif_api", { enable_nhif_api: 0 }),
      false
    );
    assert.equal(
      evaluateDependsOn("enable_nhif_api", { enable_nhif_api: 1 }),
      true
    );
  });

  test("link filters read eval values from the doc", () => {
    const [encounter] = getVisibleSections(tabs[0], {}, "Clinic").slice(-1);
    const pharmacy = encounter.fields.find(
      (field) => field.name === "cash_pharmacy"
    );
    assert.deepEqual(pharmacy.filters, {
      company: ["=", "Clinic"],
      disabled: ["=", 0],
    });
  });

  test("select options become a list", () => {
    const [encounter] = getVisibleSections(tabs[0], {}, "Clinic").slice(-1);
    const action = encounter.fields.find(
      (field) => field.name === "limit_action"
    );
    assert.deepEqual(action.options, ["", "Warn", "Stop"]);
  });

  test("a new setting starts from the DocType defaults", () => {
    const form = toSettingForm(FIELDS, null);
    assert.equal(form.notes_length, "20");
    assert.equal(form.enable_nhif_api, false);
    assert.equal(form.nhif_user, "");
    assert.ok(!("company" in form) && !("nhif_token" in form));
  });

  test("a saved setting fills the form and checks become booleans", () => {
    const form = toSettingForm(FIELDS, {
      facility_code: "0042",
      enable_nhif_api: 1,
    });
    assert.equal(form.facility_code, "0042");
    assert.equal(form.enable_nhif_api, true);
  });

  test("saved values turn checks into 1 or 0", () => {
    const values = toSettingValues(FIELDS, {
      facility_code: "0042",
      enable_nhif_api: true,
    });
    assert.equal(values.facility_code, "0042");
    assert.equal(values.enable_nhif_api, 1);
    assert.ok(!("get_nhif_token" in values));
  });
});
