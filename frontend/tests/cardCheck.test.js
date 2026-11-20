import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  cardKey,
  needsCardCheck,
} from "../src/components/appointments/create/cardCheck.js";

const card = (values) => ({
  payment: "NHIF",
  card_type: "NHIF Beneficiary Card",
  card_no: "CARD-0050",
  checkedCardKey: "",
  ...values,
});

describe("cardKey", () => {
  test("another payment, card type or card no is another card", () => {
    const key = cardKey(card());
    assert.notEqual(cardKey(card({ card_no: "CARD-0031" })), key);
    assert.notEqual(cardKey(card({ card_type: "NIDA ID" })), key);
    assert.notEqual(cardKey(card({ payment: "Jubilee" })), key);
  });

  test("spaces around the card no do not make another card", () => {
    assert.equal(cardKey(card({ card_no: " CARD-0050 " })), cardKey(card()));
  });
});

describe("needsCardCheck", () => {
  test("a typed card needs a Check until that card is checked", () => {
    assert.equal(needsCardCheck(card(), true), true);
    assert.equal(
      needsCardCheck(card({ checkedCardKey: cardKey(card()) }), true),
      false
    );
  });

  test("changing the card after a Check needs a new Check", () => {
    const checked = cardKey(card());
    assert.equal(
      needsCardCheck(
        card({ card_no: "CARD-0031", checkedCardKey: checked }),
        true
      ),
      true
    );
  });

  test("no card no, or a provider without a card API, needs no Check", () => {
    assert.equal(needsCardCheck(card({ card_no: "  " }), true), false);
    assert.equal(needsCardCheck(card(), false), false);
  });
});
