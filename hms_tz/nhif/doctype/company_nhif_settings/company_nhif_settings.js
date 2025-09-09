// Copyright (c) 2020, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company NHIF Settings", {
  refresh: function(frm) {
    frm.set_query("opd_cash_pharmacy", () => {
      return {
        filters: {
          disabled: 0,
          company: frm.doc.company,
          service_unit_type: "Pharmacy",
        },
      };
    });
    frm.set_query("ipd_cash_pharmacy", () => {
      return {
        filters: {
          disabled: 0,
          company: frm.doc.company,
          service_unit_type: "Pharmacy",
        },
      };
    });
    frm.set_query("opd_insurance_pharmacy", () => {
      return {
        filters: {
          disabled: 0,
          company: frm.doc.company,
          service_unit_type: "Pharmacy",
        },
      };
    });
    frm.set_query("ipd_insurance_pharmacy", () => {
      return {
        filters: {
          disabled: 0,
          company: frm.doc.company,
          service_unit_type: "Pharmacy",
        },
      };
    });
    frm.set_query("sales_order_opd_pharmacy", () => {
      return {
        filters: {
          disabled: 0,
          company: frm.doc.company,
        },
      };
    });
  },

  auto_submit_patient_claim: (frm) => {
    if (!frm.doc.submit_claim_year || !frm.doc.submit_claim_month) {
      frappe.msgprint("Please set submit claim year or submit claim month}");
      return;
    }
    frappe
      .call(
        "hms_tz.nhif.api.healthcare_utils.auto_submit_nhif_patient_claim",
        {
          setting_dict: {
            company: frm.doc.company,
            submit_claim_year: frm.doc.submit_claim_year,
            submit_claim_month: frm.doc.submit_claim_month,
          },
        }
      )
      .then((r) => {
        // do nothing
      });
  },
});
