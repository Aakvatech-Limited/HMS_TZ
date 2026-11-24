import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { capitalize, getCountText } from "../src/data/setupRecords.js";

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
});
