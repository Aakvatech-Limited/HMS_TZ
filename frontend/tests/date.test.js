import assert from "node:assert/strict";
import { describe, test } from "node:test";
import dayjs from "dayjs";
import { getTimeSlots } from "../src/data/date.js";

describe("getTimeSlots", () => {
  const slots = getTimeSlots("2026-11-19", 10);

  test("covers 24 hours in slot-sized steps", () => {
    assert.equal(slots.length, (24 * 60) / 10);
    assert.equal(new Set(slots.map((slot) => slot.time)).size, slots.length);
  });

  test("runs from midnight to the last slot before the next midnight", () => {
    assert.equal(slots[0].time, "00:00");
    assert.equal(slots.at(-1).time, "23:50");
    assert.equal(getTimeSlots("2026-11-19", 20).at(-1).time, "23:40");
  });

  test("lists the slots in time order", () => {
    for (let index = 1; index < slots.length; index++)
      assert.ok(slots[index].timestamp > slots[index - 1].timestamp);
  });

  test("keeps every slot on the selected date", () => {
    for (const slot of slots)
      assert.equal(dayjs(slot.timestamp).format("YYYY-MM-DD"), "2026-11-19");
  });
});
