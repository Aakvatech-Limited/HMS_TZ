// Copyright (c) 2025, Aakvatech and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Hospital Revenue Report"] = {
  filters: [
    {
      fieldname: "company",
      label: __("Company"),
      fieldtype: "Link",
      options: "Company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1,
    },
    {
      fieldname: "from_date",
      label: __("From Date"),
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.add_days(frappe.datetime.nowdate(), -30),
    },
    {
      fieldname: "to_date",
      label: __("To Date"),
      fieldtype: "Date",
      reqd: 1,
      default: frappe.datetime.nowdate(),
    },
    {
      fieldname: "payment_type",
      label: __("Payment Type"),
      fieldtype: "Select",
      options: "\nCash\nInsurance",
    },
    {
      fieldname: "service_type",
      label: __("Service Type"),
      fieldtype: "Select",
      options: "\nConsultation Charges\nLab Test Template\nRadiology Examination Template\nClinical Procedure Template\nMedication\nTherapy Type",
    },
    {
      fieldname: "department",
      label: __("Department"),
      fieldtype: "Link",
      options: "Medical Department",
    },
    {
      fieldname: "healthcare_practitioner",
      label: __("Healthcare Practitioner"),
      fieldtype: "Link",
      options: "Healthcare Practitioner",
    },
    {
      fieldname: "healthcare_service_unit",
      label: __("Healthcare Service Unit"),
      fieldtype: "Link",
      options: "Healthcare Service Unit",
    },
    {
      fieldname: "group_by",
      label: __("Group By"),
      fieldtype: "Select",
      options: "Date\nService Type\nPayment Type\nDepartment\nPractitioner",
      default: "Date",
    },
    {
      fieldname: "chart_type",
      label: __("Chart Type"),
      fieldtype: "Select",
      options: "Revenue Trends\nService Type Analysis\nPayment Type Analysis\nDepartment Analysis",
      default: "Revenue Trends",
    },
  ],
};
