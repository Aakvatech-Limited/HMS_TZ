// Shared desk modules call Frappe's __(); this page has no translations, so it only formats.
window.__ ||= (text, args = []) =>
  String(text).replace(/\{(\d+)\}/g, (match, index) => args[index] ?? match);
