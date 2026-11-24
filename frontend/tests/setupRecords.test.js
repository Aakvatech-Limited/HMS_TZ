import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  capitalize,
  getActionOptions,
  getCountText,
  getDialogFields,
  isGroupRunning,
} from "../src/data/setupRecords.js";

const doctors = { label: "doctor", plural_label: "doctors" };

describe("setup records screen", () => {
  test("the screen title starts with a capital", () => {
    assert.equal(capitalize("doctors"), "Doctors");
    assert.equal(capitalize(), "");
  });

  test("the record count uses the singular label for one record", () => {
    assert.equal(getCountText(1, doctors), "1 doctor");
    assert.equal(getCountText(0, doctors), "0 doctors");
    assert.equal(getCountText(3, doctors), "3 doctors");
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

  test("an action dropdown runs the clicked action and spins while it runs", () => {
    const group = {
      label: "NHIF actions",
      actions: [
        { key: "nhif_schemes", label: "Get NHIF Schemes" },
        { key: "nhif_items", label: "Get NHIF Items" },
      ],
    };
    const ran = [];
    const options = getActionOptions(group, (action) => ran.push(action.key));
    assert.deepEqual(
      options.map((option) => option.label),
      ["Get NHIF Schemes", "Get NHIF Items"]
    );
    options[1].onClick();
    assert.deepEqual(ran, ["nhif_items"]);
    assert.equal(isGroupRunning(group, "nhif_items"), true);
    assert.equal(isGroupRunning(group, "jubilee_packages"), false);
  });
});
