import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { getLockReason, getStepState } from "../src/data/setupRun.js";

const unlocked = {
  setting: "Clinic",
  settings_complete: true,
  has_rooms: true,
};

describe("setup run page", () => {
  test("setup is locked until the setting, settings and a room exist", () => {
    assert.match(getLockReason({}), /HMS TZ Setting/);
    assert.match(
      getLockReason({ ...unlocked, settings_complete: false }),
      /settings page/
    );
    assert.match(getLockReason({ ...unlocked, has_rooms: false }), /room/);
    assert.equal(getLockReason(unlocked), "");
  });

  test("a running step shows its progress", () => {
    assert.equal(
      getStepState({ status: "Running", done: 312, total: 480 }),
      "312 of 480"
    );
    assert.equal(
      getStepState({ status: "Running", done: 0, total: 0 }),
      "running"
    );
  });

  test("a done step shows what it created", () => {
    assert.equal(
      getStepState({ status: "Done", result: "9 types" }),
      "9 types"
    );
    assert.equal(getStepState({ status: "Done" }), "done");
  });

  test("other steps show their status", () => {
    assert.equal(getStepState({ status: "Waiting" }), "waiting");
    assert.equal(getStepState({ status: "Failed" }), "failed");
  });
});
