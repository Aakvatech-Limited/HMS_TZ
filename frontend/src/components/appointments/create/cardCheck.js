/** The card a Check or a loaded subscription belongs to; another key means another card. */
export const cardKey = ({ payment, card_type, card_no }) =>
  [payment, card_type || "", (card_no || "").trim()].join("|");

/** Whether the typed card still needs a Check before Authorize or Create may use it. */
export const needsCardCheck = (form, canCheckCard) =>
  canCheckCard &&
  Boolean((form.card_no || "").trim()) &&
  cardKey(form) !== form.checkedCardKey;
