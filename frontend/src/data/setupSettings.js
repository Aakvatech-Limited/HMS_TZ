const isLayoutBreak = (field) =>
  ["Tab Break", "Section Break", "Column Break"].includes(field.fieldtype);

const newSection = (field) => ({
  doctype: field.doctype,
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

/** Tabs of sections in server order; the fields before the first tab break form the Details tab. */
export const getSettingTabs = (fields) => {
  const tabs = [
    {
      label: "Details",
      sections: [
        newSection({ fieldname: "details", doctype: fields[0]?.doctype }),
      ],
    },
  ];
  for (const field of fields) {
    const tab = tabs.at(-1);
    if (field.fieldtype === "Tab Break") {
      tabs.push({
        label: field.label,
        sections: [
          newSection({ fieldname: field.fieldname, doctype: field.doctype }),
        ],
      });
    } else if (field.fieldtype === "Section Break") {
      tab.sections.push(newSection(field));
    } else if (!isLayoutBreak(field)) {
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
  read_only: field.read_only,
});

/** FieldMap sections of one tab, showing only what each doc's depends_on rules allow. */
export const getVisibleSections = (tab, data, company) =>
  tab.sections
    .map((section) => ({
      section,
      doc: { ...data[section.doctype], company },
    }))
    .filter(({ section, doc }) => evaluateDependsOn(section.depends_on, doc))
    .map(({ section, doc }) => ({
      ...section,
      columns: 3,
      fields: section.fields
        .filter((field) => evaluateDependsOn(field.depends_on, doc))
        .map((field) => toControl(field, doc)),
    }))
    .filter((section) => section.fields.length);

const valueFields = (fields, doctype) =>
  fields.filter((field) => field.doctype === doctype && !isLayoutBreak(field));

const doctypesOf = (fields) => [
  ...new Set(fields.map((field) => field.doctype)),
];

const toFormValue = (field, value) =>
  field.fieldtype === "Check" ? Boolean(Number(value)) : value ?? "";

/** Form values per DocType from saved values; a DocType without saved values starts from its defaults. */
export const toSettingForm = (fields, values = {}) =>
  Object.fromEntries(
    doctypesOf(fields).map((doctype) => [
      doctype,
      Object.fromEntries(
        valueFields(fields, doctype).map((field) => [
          field.fieldname,
          toFormValue(
            field,
            values[doctype] ? values[doctype][field.fieldname] : field.default
          ),
        ])
      ),
    ])
  );

/** Values to save per DocType; checks become 1 or 0. */
export const toSettingValues = (fields, data) =>
  Object.fromEntries(
    doctypesOf(fields).map((doctype) => [
      doctype,
      Object.fromEntries(
        valueFields(fields, doctype).map((field) => {
          const value = data[doctype][field.fieldname];
          return [
            field.fieldname,
            field.fieldtype === "Check" ? Number(Boolean(value)) : value,
          ];
        })
      ),
    ])
  );
