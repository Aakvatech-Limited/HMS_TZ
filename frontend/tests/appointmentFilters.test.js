import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  EMPTY_APPOINTMENT_FILTERS,
  EMPTY_PRACTITIONER_FILTERS,
  contains,
  countActiveFilters,
  getMatchedGrid,
  getPaymentOption,
  getPractitionerLevels,
  matchesAppointment,
  matchesPractitioner,
} from "../src/data/appointmentFilters.js";

const appointment = {
  patient_name: "Juma Hassan",
  status: "scheduled",
  payment: "NHIF",
  coverage_plan_name: "NHIF Test Plan",
  billing_item: "Consultation OPD",
  appointment_type: "Normal Visit",
  follow_up: 0,
  apply_fasttrack_charge: 0,
};
const practitioner = { name: "Dr Asha Mussa", department: "Paediatrics" };
const EMPTY_FILTERS = {
  ...EMPTY_APPOINTMENT_FILTERS,
  ...EMPTY_PRACTITIONER_FILTERS,
};
const withFilters = (values) => ({ ...EMPTY_FILTERS, ...values });

describe("getPaymentOption", () => {
  test("names the payment tab from the insurance company", () => {
    assert.equal(getPaymentOption(false, ""), "Cash");
    assert.equal(getPaymentOption(false, "NHIF"), "Cash");
    assert.equal(getPaymentOption(true, "NHIF"), "NHIF");
    assert.equal(getPaymentOption(true, "Jubilee Insurance"), "Jubilee");
    assert.equal(getPaymentOption(true, "Strategis Test"), "Other");
  });

  test("an insurance appointment without a company stays Other", () => {
    assert.equal(getPaymentOption(true, ""), "Other");
  });
});

describe("matchesAppointment", () => {
  test("empty filters match every appointment", () => {
    assert.ok(matchesAppointment(appointment, EMPTY_FILTERS));
  });

  test("patient name matches a part, ignoring case and spaces", () => {
    assert.ok(
      matchesAppointment(appointment, withFilters({ patient_name: " hass " }))
    );
    assert.ok(
      !matchesAppointment(appointment, withFilters({ patient_name: "Neema" }))
    );
  });

  test("status and payment match exactly", () => {
    assert.ok(
      matchesAppointment(
        appointment,
        withFilters({ status: "scheduled", payment: "NHIF" })
      )
    );
    assert.ok(
      !matchesAppointment(appointment, withFilters({ status: "open" }))
    );
    assert.ok(
      !matchesAppointment(appointment, withFilters({ payment: "Cash" }))
    );
  });

  test("an appointment without a patient name fails a name filter", () => {
    assert.ok(
      !matchesAppointment(
        { ...appointment, patient_name: null },
        withFilters({ patient_name: "a" })
      )
    );
  });
});

describe("matchesAppointment visit filters", () => {
  test("coverage plan, billing item and visit type match a part", () => {
    assert.ok(
      matchesAppointment(
        appointment,
        withFilters({
          coverage_plan_name: "test plan",
          billing_item: "opd",
          appointment_type: "normal",
        })
      )
    );
    assert.ok(
      !matchesAppointment(appointment, withFilters({ billing_item: "Ward" }))
    );
  });

  test("follow up narrows only when ticked", () => {
    assert.ok(
      !matchesAppointment(appointment, withFilters({ follow_up: true }))
    );
    assert.ok(
      matchesAppointment(
        { ...appointment, follow_up: 1 },
        withFilters({ follow_up: true })
      )
    );
  });
});

describe("matchesAppointment fast track", () => {
  test("fast track narrows only when ticked", () => {
    assert.ok(matchesAppointment(appointment, EMPTY_FILTERS));
    assert.ok(
      !matchesAppointment(
        appointment,
        withFilters({ apply_fasttrack_charge: true })
      )
    );
    assert.ok(
      matchesAppointment(
        { ...appointment, apply_fasttrack_charge: 1 },
        withFilters({ apply_fasttrack_charge: true })
      )
    );
  });
});

describe("matchesPractitioner", () => {
  test("practitioner and department match a part, ignoring case", () => {
    assert.ok(
      matchesPractitioner(
        practitioner,
        withFilters({ practitioner: "asha", department: "PAED" })
      )
    );
    assert.ok(
      !matchesPractitioner(
        practitioner,
        withFilters({ department: "Surgery" })
      )
    );
  });
});

describe("practitioner level", () => {
  const specialist = {
    name: "Dr Juma",
    billing_item: "Specialist",
    inpatient_billing_item: "Specialist",
  };
  const inpatientOnly = {
    name: "Dr Neema",
    inpatient_billing_item: "Super Specialist",
  };
  const noLevel = { name: "Dr Baraka" };

  test("matches the outpatient or the inpatient charge item exactly", () => {
    assert.ok(
      matchesPractitioner(specialist, withFilters({ level: "Specialist" }))
    );
    assert.ok(
      matchesPractitioner(
        inpatientOnly,
        withFilters({ level: "Super Specialist" })
      )
    );
    assert.ok(
      !matchesPractitioner(
        specialist,
        withFilters({ level: "Super Specialist" })
      )
    );
    assert.ok(
      !matchesPractitioner(noLevel, withFilters({ level: "Specialist" }))
    );
  });

  test("a blank level matches every practitioner", () => {
    assert.ok(matchesPractitioner(noLevel, withFilters({})));
  });

  test("lists each level once, sorted, without blanks", () => {
    assert.deepEqual(
      getPractitionerLevels([specialist, inpatientOnly, noLevel]),
      ["Specialist", "Super Specialist"]
    );
  });
});

describe("contains", () => {
  test("blank text matches anything, including a missing value", () => {
    assert.ok(contains(null, "  "));
  });

  test("a missing value fails a non-blank text", () => {
    assert.ok(!contains(null, "paed"));
  });
});

describe("countActiveFilters", () => {
  test("counts filters that are not blank", () => {
    assert.equal(countActiveFilters(EMPTY_APPOINTMENT_FILTERS), 0);
    assert.equal(
      countActiveFilters(
        withFilters({ patient_name: "  ", status: "open", follow_up: true })
      ),
      2
    );
  });
});

describe("getMatchedGrid", () => {
  const timeSlots = ["09:00", "09:10", "18:10"].map((time) => ({ time }));
  const doctors = ["Dr A", "Dr B", "Dr C"].map((name) => ({ name }));

  test("keeps only slots and practitioners holding a match", () => {
    const bySlot = new Map([["18:10", new Map([["Dr B", [{}]]])]]);
    const grid = getMatchedGrid(timeSlots, doctors, bySlot);
    assert.deepEqual(
      grid.slots.map(({ time }) => time),
      ["18:10"]
    );
    assert.deepEqual(
      grid.practitioners.map(({ name }) => name),
      ["Dr B"]
    );
  });

  test("drops a slot whose only match is in a hidden column", () => {
    const bySlot = new Map([
      ["09:00", new Map([["Dr Z", [{}]]])],
      ["09:10", new Map([["Dr A", [{}]]])],
    ]);
    const grid = getMatchedGrid(timeSlots, doctors, bySlot);
    assert.deepEqual(
      grid.slots.map(({ time }) => time),
      ["09:10"]
    );
  });

  test("no matches leave an empty grid", () => {
    const grid = getMatchedGrid(timeSlots, doctors, new Map());
    assert.equal(grid.slots.length, 0);
    assert.equal(grid.practitioners.length, 0);
  });
});
