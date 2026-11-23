export const SETTING_DOCTYPE = "HMS TZ Setting";

// Company comes from the page picker; buttons, tokens and hidden fields stay on the desk form.
const isEditable = (field) =>
  field.fieldname !== "company" &&
  field.fieldtype !== "Button" &&
  !field.hidden &&
  !field.read_only;

const isLayoutBreak = (field) =>
  ["Tab Break", "Section Break", "Column Break"].includes(field.fieldtype);

const newSection = (field) => ({
  label: field.label || field.fieldname,
  hideLabel: !field.label,
  depends_on: field.depends_on,
  fields: [],
});

/** Desk depends_on rule: "eval:<js>" against the doc, or a fieldname that must be set. */
export const evaluateDependsOn = (expression, doc) => {
  if (!expression) return true;
  if (!expression.startsWith("eval:")) return Boolean(doc[expression]);
  return Boolean(evaluate(expression, doc));
};

const evaluate = (expression, doc) =>
  new Function("doc", `return (${expression.slice(5)});`)(doc);

/** Tabs of sections in DocType order; the fields before the first tab break form the Details tab. */
export const getSettingTabs = (fields) => {
  const tabs = [
    { label: "Details", sections: [newSection({ fieldname: "details" })] },
  ];
  for (const field of fields) {
    const tab = tabs.at(-1);
    if (field.fieldtype === "Tab Break") {
      tabs.push({
        label: field.label,
        sections: [newSection({ fieldname: field.fieldname })],
      });
    } else if (field.fieldtype === "Section Break") {
      tab.sections.push(newSection(field));
    } else if (!isLayoutBreak(field) && isEditable(field)) {
      tab.sections.at(-1).fields.push(field);
    }
  }
  return tabs.map((tab) => ({
    ...tab,
    sections: tab.sections.filter((section) => section.fields.length),
  }));
};

/** Desk link_filters as Link control filters, with "eval:" values read from the doc. */
export const getLinkFilters = (field, doc) =>
  Object.fromEntries(
    JSON.parse(field.link_filters || "[]").map(
      ([, fieldname, operator, value]) => [
        fieldname,
        [
          operator,
          String(value).startsWith("eval:") ? evaluate(value, doc) : value,
        ],
      ]
    )
  );

const toControl = (field, doc) => ({
  name: field.fieldname,
  label: field.label,
  type: field.fieldtype,
  options:
    field.fieldtype === "Select"
      ? (field.options || "").split("\n")
      : field.options,
  reqd:
    field.reqd ||
    (field.mandatory_depends_on &&
      evaluateDependsOn(field.mandatory_depends_on, doc)),
  filters: getLinkFilters(field, doc),
});

/** FieldMap sections of one tab, showing only what the doc's depends_on rules allow. */
export const getVisibleSections = (tab, form, company) => {
  const doc = { ...form, company };
  return tab.sections
    .filter((section) => evaluateDependsOn(section.depends_on, doc))
    .map((section) => ({
      ...section,
      doctype: SETTING_DOCTYPE,
      columns: 3,
      fields: section.fields
        .filter((field) => evaluateDependsOn(field.depends_on, doc))
        .map((field) => toControl(field, doc)),
    }))
    .filter((section) => section.fields.length);
};

const editableFields = (fields) =>
  fields.filter((field) => !isLayoutBreak(field) && isEditable(field));

/** Form values from a saved setting, or DocType defaults for a new one; checks become booleans. */
export const toSettingForm = (fields, setting) =>
  Object.fromEntries(
    editableFields(fields).map((field) => {
      const value = setting ? setting[field.fieldname] : field.default;
      return [
        field.fieldname,
        field.fieldtype === "Check" ? Boolean(Number(value)) : value ?? "",
      ];
    })
  );

/** Values to save; checks become 1 or 0. */
export const toSettingValues = (fields, form) =>
  Object.fromEntries(
    editableFields(fields).map((field) => [
      field.fieldname,
      field.fieldtype === "Check"
        ? Number(Boolean(form[field.fieldname]))
        : form[field.fieldname],
    ])
  );
