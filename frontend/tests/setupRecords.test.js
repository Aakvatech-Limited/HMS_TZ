import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  capitalize,
  getActionOptions,
  getCountText,
  getDialogFields,
  getDialogTitle,
  getRunRows,
  isGroupRunning,
  isRunActive,
} from "../src/data/setupRecords.js";

const doctors = { label: "doctor", plural_label: "doctors" };

describe("setup records screen", () => {
  test("a read-only screen shows every dialog field read only and views records", () => {
    const fields = getDialogFields([{ fieldname: "timestamp" }], true, true);
    assert.equal(fields[0].read_only, true);
    const updates = {
      label: "NHIF update",
      title_field: "name",
      is_read_only: 1,
    };
    assert.equal(getDialogTitle(updates, { name: "NU-1" }), "View NU-1");
    const plans = { label: "plan", title_field: "plan_name" };
    assert.equal(
      getDialogTitle(plans, { name: "P", plan_name: "Gold" }),
      "Change Gold"
    );
    assert.equal(getDialogTitle(plans, null), "Add plan");
  });

  test("the screen title starts with a capital", () => {
    assert.equal(capitalize("doctors"), "Doctors");
    assert.equal(capitalize(), "");
  });

  test("the record count uses the singular label for one record", () => {
    assert.equal(getCountText(1, doctors), "1 doctor");
    assert.equal(getCountText(0, doctors), "0 doctors");
    assert.equal(getCountText(3, doctors), "3 doctors");
    assert.equal(
      getCountText(500, doctors, true),
      "First 500 doctors, filter to see the others"
    );
  });

  test("the naming field is read only only when changing a record", () => {
    const fields = [
      { fieldname: "coverage_plan_name", set_only_once: 1 },
      { fieldname: "price_list" },
    ];
    const readOnly = (isEditing) =>
      getDialogFields(fields, isEditing).map((field) => field.read_only);
    assert.deepEqual(readOnly(false), [false, false]);
    assert.deepEqual(readOnly(true), [true, false]);
  });

  test("an action dropdown queues the clicked action and spins while one runs", () => {
    const group = {
      label: "NHIF actions",
      actions: [
        { key: "nhif_schemes", label: "Get NHIF Schemes" },
        { key: "nhif_items", label: "Get NHIF Items" },
      ],
    };
    const runs = { nhif_items: { status: "Running" } };
    const ran = [];
    const options = getActionOptions(group, runs, (action) =>
      ran.push(action.key)
    );
    assert.deepEqual(
      options.map((option) => [option.label, option.disabled]),
      [
        ["Get NHIF Schemes", false],
        ["Get NHIF Items", true],
      ]
    );
    options[0].onClick();
    assert.deepEqual(ran, ["nhif_schemes"]);
    assert.equal(isGroupRunning(group, runs), true);
    assert.equal(
      isGroupRunning(group, { nhif_items: { status: "Done" } }),
      false
    );
  });

  test("every action is listed with its last run, or none when it never ran", () => {
    const groups = [
      { label: "Jubilee actions", actions: [{ key: "a" }, { key: "b" }] },
    ];
    const rows = getRunRows(groups, { b: { status: "Failed" } });
    assert.deepEqual(
      rows.map((row) => [row.key, row.run?.status ?? null]),
      [
        ["a", null],
        ["b", "Failed"],
      ]
    );
    assert.equal(isRunActive({ status: "Queued" }), true);
    assert.equal(isRunActive(null), false);
  });
});
