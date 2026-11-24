import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  applyStepProgress,
  getLockReason,
  getRunReport,
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

  test("a done step shows what it holds and what it added", () => {
    assert.equal(
      getStepState({ status: "Done", result: "9 types", added: 2 }),
      "9 types, 2 added"
    );
    assert.equal(
      getStepState({ status: "Done", result: "9 types", added: 0 }),
      "9 types, nothing missing"
    );
    assert.equal(getStepState({ status: "Done" }), "done, nothing missing");
  });

  test("the run report waits until every step is done", () => {
    assert.equal(getRunReport([]), "");
    assert.equal(
      getRunReport([
        { status: "Done", added: 1 },
        { status: "Failed", added: 0 },
      ]),
      ""
    );
  });

  test("the run report says nothing was missing or what was added", () => {
    const steps = [
      { label: "Visit types", status: "Done", added: 0 },
      { label: "Card verifiers", status: "Done", added: 0 },
    ];
    assert.match(getRunReport(steps), /^Nothing missing/);
    steps[1].added = 1;
    assert.equal(
      getRunReport(steps),
      "The last run added 1 missing record: Card verifiers."
    );
    steps[0].added = 2;
    assert.equal(
      getRunReport(steps),
      "The last run added 3 missing records: Visit types, Card verifiers."
    );
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
