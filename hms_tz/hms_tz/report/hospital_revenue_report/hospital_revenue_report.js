// Copyright (c) 2025, Aakvatech and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Hospital Revenue Report"] = {
  onload: function (report) {
    // Populate payment type options
    frappe.call({
      method: "hms_tz.hms_tz.report.hospital_revenue_report.hospital_revenue_report.get_payment_types",
      callback: function (r) {
        if (r.message) {
          let payment_type_filter = report.get_filter("payment_type");
          let options = r.message.map(option => option.value).join("\n");
          payment_type_filter.df.options = options;
          payment_type_filter.refresh();
        }
      }
    });
  },
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
      options: "",
      on_change: function () {
        // This will be populated dynamically from Python
      }
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
  ],
};
