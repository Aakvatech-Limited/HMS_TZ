/** First letter in capitals, for example "doctors" to "Doctors". */
export const capitalize = (text = "") =>
  text.charAt(0).toUpperCase() + text.slice(1);

/** Number of records with the screen's label, for example "1 doctor" or "3 doctors". */
export const getCountText = (count, screen) =>
  `${count} ${count === 1 ? screen.label : screen.plural_label}`;
