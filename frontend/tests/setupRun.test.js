import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  applyStepProgress,
  getLockReason,
  getStepPercent,
  getStepState,
} from "../src/data/setupRun.js";

const unlocked = {
  setting: "Clinic",
  settings_complete: true,
  has_rooms: true,
};

describe("setup run page", () => {
  test("setup is locked until the setting exists and its settings are complete", () => {
    assert.match(getLockReason({}), /HMS TZ Setting/);
    assert.match(
      getLockReason({ ...unlocked, settings_complete: false }),
      /settings page/
    );
    assert.equal(getLockReason({ ...unlocked, has_rooms: false }), "");
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
  test("a step's progress bar follows its done and total counts", () => {
    assert.equal(
      getStepPercent({ status: "Running", done: 3, total: 12 }),
      25
    );
    assert.equal(getStepPercent({ status: "Running", done: 0, total: 0 }), 0);
    assert.equal(getStepPercent({ status: "Done", done: 0, total: 0 }), 100);
  });
  test("a live progress message updates only its own step and setting", () => {
    const run = {
      setting: "Clinic",
      steps: [
        { step: "visit_types", status: "Waiting", done: 0, total: 0 },
        { step: "card_verifiers", status: "Waiting", done: 0, total: 0 },
      ],
    };
    applyStepProgress(run, {
      setting: "Clinic",
      step: "visit_types",
      status: "Running",
      done: 4,
      total: 10,
    });
    applyStepProgress(run, {
      setting: "Other",
      step: "card_verifiers",
      status: "Done",
    });
    assert.deepEqual(run.steps[0], {
      step: "visit_types",
      status: "Running",
      done: 4,
      total: 10,
    });
    assert.equal(run.steps[1].status, "Waiting");
  });
});
