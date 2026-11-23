// Copyright (c) 2025, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("HMS TZ Setting", {
  get_nhif_token: (frm) => {
    if (frm.is_dirty()) {
      frm.save();
    }

    if (frm.doc.enable_nhif_token === 0) {
      frappe.msgprint(__("Please Enable NHIF API to proceed.."));
      return;
    }

    frm.call("get_nhif_token").then(
      frm.reload_doc(),
      frappe.show_alert({
        message: __("Token Successful fetched...!!"),
        indicator: "green",
      })
    );
  },

  get_jubilee_token: (frm) => {
    if (frm.is_dirty()) {
      frm.save();
    }

    if (frm.doc.enable_jubilee_api === 0) {
      frappe.msgprint(__("Please Enable Jubilee API to proceed.."));
      return;
    }

    frm.call("get_jubilee_token").then(
      frm.reload_doc(),
      frappe.show_alert({
        message: __("Token Successful fetched...!!"),
        indicator: "green",
      })
    );
  },

  auto_submit_patient_claim: (frm) => {
    if (!frm.doc.submit_claim_year || !frm.doc.submit_claim_month) {
      frappe.msgprint("Please set submit claim year or submit claim month");
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
