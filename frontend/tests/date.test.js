import assert from "node:assert/strict";
import { describe, test } from "node:test";
import dayjs from "dayjs";
import { getTimeSlots } from "../src/data/date.js";

describe("getTimeSlots", () => {
  const slots = getTimeSlots("2026-11-19", 10, 7);

  test("covers 24 hours in slot-sized steps", () => {
    assert.equal(slots.length, (24 * 60) / 10);
    assert.equal(new Set(slots.map((slot) => slot.time)).size, slots.length);
  });

  test("starts at the day start hour and wraps past midnight to the hour before it", () => {
    assert.equal(slots[0].time, "07:00");
    assert.equal(slots.at(-1).time, "06:50");
    const midnight = slots.findIndex((slot) => slot.time === "00:00");
    assert.equal(slots[midnight - 1].time, "23:50");
  });

  test("keeps every slot on the selected date", () => {
    for (const slot of slots)
      assert.equal(dayjs(slot.timestamp).format("YYYY-MM-DD"), "2026-11-19");
  });

  test("starts at midnight when the day start hour is 0", () => {
    assert.equal(getTimeSlots("2026-11-19", 30, 0)[0].time, "00:00");
  });
});
