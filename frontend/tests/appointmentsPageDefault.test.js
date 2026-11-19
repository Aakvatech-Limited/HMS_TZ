import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  OPEN_BY_DEFAULT,
  PAGE_TRIED,
  PAGE_TRIED_SETTINGS,
  isOpenByDefault,
  toUserSettings,
} from "../src/data/appointmentsPageDefault.js";

describe("open by default", () => {
  test("reads the choice from the user's list settings", () => {
    assert.equal(
      isOpenByDefault(JSON.stringify({ [OPEN_BY_DEFAULT]: 1 })),
      true
    );
    assert.equal(
      isOpenByDefault(JSON.stringify({ [OPEN_BY_DEFAULT]: 0 })),
      false
    );
  });

  test("users without saved settings stay on the list", () => {
    assert.equal(isOpenByDefault("{}"), false);
    assert.equal(isOpenByDefault(null), false);
    assert.equal(
      isOpenByDefault(JSON.stringify({ last_view: "Report" })),
      false
    );
  });

  test("saves only its own key, so other list settings are kept", () => {
    assert.deepEqual(JSON.parse(toUserSettings(true)), {
      [OPEN_BY_DEFAULT]: 1,
    });
    assert.deepEqual(JSON.parse(toUserSettings(false)), {
      [OPEN_BY_DEFAULT]: 0,
    });
  });

  test("a visit records the page as tried", () => {
    assert.deepEqual(JSON.parse(PAGE_TRIED_SETTINGS), { [PAGE_TRIED]: 1 });
  });
});
