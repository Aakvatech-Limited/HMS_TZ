import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  evaluateDependsOn,
  getSettingTabs,
  getVisibleSections,
  toSettingForm,
  toSettingValues,
} from "../src/data/setupSettings.js";

const SETTING = "HMS TZ Setting";
const BILLING = "Healthcare Settings";
const NHIF_ON = "eval: doc.enable_nhif_api == 1";

const setting = (field) => ({ ...field, doctype: SETTING });
const billing = (field) => ({ ...field, doctype: BILLING });

const FIELDS = [
  setting({
    fieldname: "facility_code",
    fieldtype: "Data",
    label: "Facility Code",
  }),
  setting({
    fieldname: "encounter_section",
    fieldtype: "Section Break",
    label: "Encounter",
  }),
  setting({
    fieldname: "notes_length",
    fieldtype: "Int",
    label: "Notes Length",
    default: "20",
  }),
  setting({ fieldname: "column_break", fieldtype: "Column Break" }),
  setting({
    fieldname: "limit_action",
    fieldtype: "Select",
    label: "Limit Action",
    options: "\nWarn\nStop",
  }),
  setting({
    fieldname: "cash_pharmacy",
    fieldtype: "Link",
    label: "Cash Pharmacy",
    options: "Healthcare Service Unit",
    link_filters: JSON.stringify([
      ["Healthcare Service Unit", "company", "=", "eval: doc.company"],
      ["Healthcare Service Unit", "disabled", "=", 0],
    ]),
  }),
  setting({ fieldname: "nhif_tab", fieldtype: "Tab Break", label: "NHIF" }),
  setting({
    fieldname: "enable_nhif_api",
    fieldtype: "Check",
    label: "Enable NHIF API",
    default: "0",
  }),
  setting({
    fieldname: "nhif_user",
    fieldtype: "Data",
    label: "NHIF User",
    depends_on: NHIF_ON,
  }),
  setting({
    fieldname: "dates_section",
    fieldtype: "Section Break",
    label: "Submit Dates",
    depends_on: NHIF_ON,
  }),
  setting({
    fieldname: "submit_claim_month",
    fieldtype: "Int",
    label: "Submit Claim Month",
  }),
  setting({
    fieldname: "jubilee_tab",
    fieldtype: "Tab Break",
    label: "Jubilee",
  }),
  setting({
    fieldname: "jubilee_user",
    fieldtype: "Data",
    label: "Jubilee User",
  }),
  billing({
    fieldname: "billing_tab",
    fieldtype: "Tab Break",
    label: "Billing",
  }),
  billing({
    fieldname: "sb_op_settings",
    fieldtype: "Section Break",
    label: "Outpatient Settings",
  }),
  billing({
    fieldname: "collect_registration_fee",
    fieldtype: "Check",
    label: "Collect Fee",
  }),
  billing({
    fieldname: "registration_fee",
    fieldtype: "Currency",
    label: "Registration Fee",
    depends_on: "collect_registration_fee",
  }),
  billing({
    fieldname: "income_account",
    fieldtype: "Link",
    label: "Income Account",
    options: "Account",
    link_filters: JSON.stringify([
      ["Account", "company", "=", "eval: doc.company"],
    ]),
  }),
];

const tabs = getSettingTabs(FIELDS);
const fieldNames = (sections) =>
  sections.flatMap((section) => section.fields.map((field) => field.name));
const form = (values) => toSettingForm(FIELDS, values);

describe("setup settings form", () => {
  test("tab breaks give Details, NHIF, Jubilee and Billing tabs", () => {
    assert.deepEqual(
      tabs.map((tab) => tab.label),
      ["Details", "NHIF", "Jubilee", "Billing"]
    );
    assert.deepEqual(
      tabs[0].sections.map((section) => section.label),
      ["details", "Encounter"]
    );
  });

  test("each section binds to the DocType of its fields", () => {
    assert.deepEqual(
      tabs.map((tab) => tab.sections[0].doctype),
      [SETTING, SETTING, SETTING, BILLING]
    );
  });

  test("depends_on hides fields and sections while the switch is off", () => {
    const off = getVisibleSections(tabs[1], form(), "Clinic");
    assert.deepEqual(fieldNames(off), ["enable_nhif_api"]);
    const data = form();
    data[SETTING].enable_nhif_api = true;
    const on = getVisibleSections(tabs[1], data, "Clinic");
    assert.deepEqual(fieldNames(on), [
      "enable_nhif_api",
      "nhif_user",
      "submit_claim_month",
    ]);
  });

  test("billing fields read their own DocType values", () => {
    const data = form({ [BILLING]: { collect_registration_fee: 1 } });
    const names = fieldNames(getVisibleSections(tabs[3], data, "Clinic"));
    assert.deepEqual(names, [
      "collect_registration_fee",
      "registration_fee",
      "income_account",
    ]);
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

  test("an eval rule may end with a semicolon", () => {
    assert.equal(
      evaluateDependsOn("eval:doc.is_billable;", { is_billable: 1 }),
      true
    );
    assert.equal(
      evaluateDependsOn("eval:doc.is_billable; ", { is_billable: 0 }),
      false
    );
  });

  test("link filters read eval values from the doc", () => {
    const [account] = getVisibleSections(tabs[3], form(), "Clinic")
      .at(-1)
      .fields.slice(-1);
    assert.deepEqual(account.filters, { company: ["=", "Clinic"] });
    const encounter = getVisibleSections(tabs[0], form(), "Clinic").at(-1);
    const pharmacy = encounter.fields.find(
      (field) => field.name === "cash_pharmacy"
    );
    assert.deepEqual(pharmacy.filters, {
      company: ["=", "Clinic"],
      disabled: ["=", 0],
    });
  });

  test("select options become a list", () => {
    const encounter = getVisibleSections(tabs[0], form(), "Clinic").at(-1);
    const action = encounter.fields.find(
      (field) => field.name === "limit_action"
    );
    assert.deepEqual(action.options, ["", "Warn", "Stop"]);
  });

  test("a DocType without saved values starts from its defaults", () => {
    const data = form({
      [SETTING]: null,
      [BILLING]: { registration_fee: 500 },
    });
    assert.equal(data[SETTING].notes_length, "20");
    assert.equal(data[SETTING].enable_nhif_api, false);
    assert.equal(data[SETTING].nhif_user, "");
    assert.equal(data[BILLING].registration_fee, 500);
    assert.ok(!("nhif_tab" in data[SETTING]));
  });

  test("saved values are grouped by DocType and checks become 1 or 0", () => {
    const data = form({
      [SETTING]: { facility_code: "0042", enable_nhif_api: 1 },
    });
    data[BILLING].collect_registration_fee = true;
    const values = toSettingValues(FIELDS, data);
    assert.equal(values[SETTING].facility_code, "0042");
    assert.equal(values[SETTING].enable_nhif_api, 1);
    assert.equal(values[BILLING].collect_registration_fee, 1);
    assert.ok(!("billing_tab" in values[BILLING]));
  });
  test("a single-DocType field list binds its first section to that DocType", () => {
    const room = (field) => ({ ...field, doctype: "Healthcare Service Unit" });
    const [tab] = getSettingTabs([
      room({
        fieldname: "unit_name",
        fieldtype: "Data",
        label: "Room",
        reqd: 1,
      }),
    ]);
    const data = { "Healthcare Service Unit": { unit_name: "OPD 1" } };
    const [section] = getVisibleSections(tab, data, "Clinic");
    assert.equal(section.doctype, "Healthcare Service Unit");
    assert.equal(section.fields[0].name, "unit_name");
  });
  test("a dynamic link is a link of the DocType its options field holds", () => {
    const coverage = (field) => ({
      ...field,
      doctype: "Healthcare Service Insurance Coverage",
    });
    const [tab] = getSettingTabs([
      coverage({
        fieldname: "healthcare_service",
        fieldtype: "Select",
        options: "\nMedication\nLab Test Template",
      }),
      coverage({
        fieldname: "healthcare_service_template",
        fieldtype: "Dynamic Link",
        options: "healthcare_service",
      }),
    ]);
    const template = (service) =>
      getVisibleSections(
        tab,
        {
          "Healthcare Service Insurance Coverage": {
            healthcare_service: service,
          },
        },
        "Clinic"
      )[0].fields[1];
    assert.deepEqual(
      [template("Medication").type, template("Medication").options],
      ["Link", "Medication"]
    );
    assert.equal(template("").type, "Data");
  });
});
