import { contains } from "./appointmentFilters.js";

/** Pages whose label or description contains the text: exact label first, then labels starting with it; input order is kept within each. */
export const matchPages = (pages, text) => {
  const query = text.trim().toLowerCase();
  const rank = (label) => {
    const lower = label.toLowerCase();
    if (lower === query) return 0;
    return lower.startsWith(query) ? 1 : 2;
  };
  return pages
    .filter(
      ({ label, description }) =>
        contains(label, text) || contains(description, text)
    )
    .sort((first, second) => rank(first.label) - rank(second.label));
};
