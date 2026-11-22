import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { getPaymentMarker } from "../src/components/appointments/appointmentStatus.js";

const label = (values) =>
  getPaymentMarker({ status: "open", ...values })?.label ?? null;

describe("getPaymentMarker", () => {
  test("a cash appointment is Paid with a Sales Invoice and Unpaid without one", () => {
    assert.equal(
      label({ payment: "Cash", ref_sales_invoice: "ACC-SINV-1" }),
      "Paid"
    );
    assert.equal(label({ payment: "Cash", ref_sales_invoice: "" }), "Unpaid");
  });

  test("a cash follow-up without an invoice has nothing to pay", () => {
    assert.equal(label({ payment: "Cash", follow_up: 1 }), null);
  });

  test("every insurance is Not authorized until it has an authorization number", () => {
    for (const payment of ["NHIF", "Jubilee", "Other"]) {
      assert.equal(
        label({ payment, authorization_number: "" }),
        "Not authorized"
      );
      assert.equal(label({ payment, authorization_number: "AUTH-1" }), null);
    }
  });

  test("a cancelled appointment has no marker", () => {
    assert.equal(label({ status: "cancelled", payment: "Cash" }), null);
    assert.equal(label({ status: "cancelled", payment: "NHIF" }), null);
  });
});
