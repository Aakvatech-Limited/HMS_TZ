import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, test } from "node:test";
import {
  SETUP_GROUPS,
  getNavigationGroups,
  getRunLabel,
} from "../src/data/setupNavigation.js";

const navigation = {
  settings_complete: false,
  steps: [
    { document_type: "HMS TZ Setting", completed: 1 },
    { document_type: "Healthcare Practitioner", completed: 1 },
    { document_type: "Lab Test Template", completed: 0 },
  ],
  nhif_templates_to_review: 12,
};

const getScreens = (groups) =>
  Object.fromEntries(
    groups
      .flatMap((group) => group.screens)
      .map((screen) => [screen.label, screen])
  );

describe("setup navigation", () => {
  test("every setup screen route is in one sidebar group", () => {
    const router = readFileSync(
      new URL("../src/router.js", import.meta.url),
      "utf8"
    );
    const setupRoutes = [
      ...router.matchAll(/path: "\/setup[^"]*",\s*name: "(\w+)"/g),
    ]
      .map((match) => match[1])
      .filter((name) => name !== "SetupRun");
    const routes = SETUP_GROUPS.flatMap((group) => group.screens).map(
      (screen) => screen.route
    );
    assert.deepEqual([...routes].sort(), [...setupRoutes].sort());
  });

  test("each route opens a fresh page, so record screens sharing one page reload their own records", () => {
    const app = readFileSync(
      new URL("../src/App.vue", import.meta.url),
      "utf8"
    );
    assert.match(app, /<router-view :key="\$route\.name"/);
  });

  test("a screen is done when its setup step is done", () => {
    const screens = getScreens(getNavigationGroups(navigation));
    assert.equal(screens["Doctors"].status, "done");
    assert.equal(screens["Lab templates"].status, "todo");
    assert.equal(screens["Rooms"].status, "todo");
    assert.equal(screens["NHIF items"].status, null);
  });

  test("the settings screen is done only when every settings group is complete", () => {
    assert.equal(
      getScreens(getNavigationGroups(navigation))["HMS TZ Setting"].status,
      "todo"
    );
    const complete = { ...navigation, settings_complete: true };
    assert.equal(
      getScreens(getNavigationGroups(complete))["HMS TZ Setting"].status,
      "done"
    );
  });

  test("NHIF templates shows the codes waiting for review", () => {
    const screens = getScreens(getNavigationGroups(navigation));
    assert.equal(screens["NHIF templates"].toReview, 12);
    assert.equal(screens["Doctors"].toReview, 0);
  });

  test("screens have no status before the navigation loads", () => {
    const screens = getScreens(getNavigationGroups(null));
    assert.equal(screens["Doctors"].status, null);
  });

  test("Run setup shows how many setup steps are done", () => {
    assert.equal(getRunLabel(navigation), "Run setup · 2 of 3 done");
    assert.equal(getRunLabel({ steps: [] }), "Run setup");
    assert.equal(getRunLabel(undefined), "Run setup");
  });
});
