// Copyright (c) 2023, Aakvatech and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["LRPMT returns"] = {
  filters: [
    {
      fieldname: "from_date",
      label: __("From Date"),
      fieldtype: "Date",
      reqd: 1,
    },
    {
      fieldname: "to_date",
      label: __("To Date"),
      fieldtype: "Date",
      reqd: 1,
    },
    {
      fieldname: "practitioner",
      label: __("Practitioner"),
      fieldtype: "Link",
      options: "Healthcare Practitioner",
    },
    {
      fieldname: "reference_doctype",
      label: __("Reference Doctype"),
      fieldtype: "Link",
      options: "DocType",
    },
    {
      fieldname: "item",
      label: __("Item"),
      fieldtype: "Link",
      options: "Item",
    },
    {
      fieldname: "reason",
      label: __("Reason"),
      fieldtype: "Link",
      options: "Healthcare Return Reason",
    },
    {
      fieldname: "item_condition",
      label: __("Item Condition"),
      fieldtype: "Link",
      options: "Medication Condition",
    },
  ],
};
