// Copyright (c) 2020, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("NHIF Patient Claim", {
  setup: function (frm) {
    frm.set_query("patient_appointment", function () {
      return {
        filters: {
          nhif_patient_claim: ["in", ["", "None"]],
          insurance_company: ["like", "NHIF%"],
          insurance_subscription: ["not in", ["", "None"]],
        },
      };
    });
  },

  refresh(frm) {
    $("[data-action='delete_all_rows']").hide();

    if (frm.doc.docstatus === 0 && frm.doc.authorization_no) {
      frm.add_custom_button(__("Re-concile Repeated Items"), () => {
        frappe
          .call({
            method:
              "hms_tz.nhif.doctype.nhif_patient_claim.nhif_patient_claim.reconcile_repeated_items",
            args: {
              claim_no: frm.doc.name,
            },
            freeze: true,
            freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
          })
          .then((r) => {
            if (r.message) {
              frm.refresh();
            }
          });
      });

      frm.add_custom_button(__("Merge Claims"), function () {
        const original_practitioner_name = frm.doc.practitioner_name;
        frm.dirty();
        frm
          .call("get_appointments", {
            self: frm.doc,
            freeze: true,
            freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
          })
          .then((r) => {
            frm.doc.practitioner_name = original_practitioner_name;
            frm.save();
            frm.refresh();
          });
      });
    }
  },

  onload: function (frm) {
    $("[data-action='delete_all_rows']").hide();
    if (frm.doc.patient && frm.doc.patient_appointment) {
      frappe.db
        .get_list("LRPMT Returns", {
          fields: ["name"],
          filters: {
            patient: frm.doc.patient,
            appointment: frm.doc.patient_appointment,
            docstatus: 1,
          },
        })
        .then((data) => {
          if (data.length > 0) {
            let msg_lrpmt = ``;
            data.forEach((element) => {
              msg_lrpmt += `${__(element.name)} ,`;
            });

            frappe.msgprint({
              title: __("Notification"),
              indicator: "orange",
              message: __(`
							<p class='text-left'>This Patient: <b>${__(
                frm.doc.patient
              )}</b> of appointment No: <b>${__(
                frm.doc.patient_appointment
              )}</b>
							having some item(s) cancelled or some quantity of item(s) returned to stock, by <b>${__(
                msg_lrpmt
              )}</b>,
							inorder for items and their quantities to be reflected on this claim</p>
							<p class='text-center' style='background-color: #FFA500; font-size: 14px;'>
							<strong><em><i>Tick allow changes, then Untick allow changes and Save again</i></em></strong></p>
							`),
            });
          }
        });
    }
  },

  after_save: (frm) => {
    if (needs_folio_signature(frm)) {
      show_signature_method_dialog(frm);
    }
    alert_signed_amount_mismatch(frm);
  },

  is_ready_for_auto_submission: (frm) => {
    if (frm.doc.is_ready_for_auto_submission == 1) {
      frm.set_value("reviewed_by", frappe.user.full_name());
    } else {
      frm.set_value("reviewed_by", "");
    }
  },

  sign_folio: (frm) => {
    if (needs_folio_signature(frm)) {
      show_signature_method_dialog(frm);
    }
  },

  send_confirmation_code: (frm) => {
    frappe
      .call({
        method: "hms_tz.nhif.nhif_api.patient_claim.send_confirmation_code",
        args: {
          ref_doctype: frm.doc.doctype,
          ref_docname: frm.doc.name,
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      })
      .then((r) => {
        if (r.message) {
          frm.reload_doc();
        }
      });
  },

  get_receipt: (frm) => {
    frappe.call({
      method: "hms_tz.nhif.nhif_api.patient_claim.get_receipt",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          frm.reload_doc();
        }
      },
    });
  },

  bypass_sending_to_nhif: (frm) => {
    if (frm.doc.bypass_sending_to_nhif == 1) {
      frm.set_value("bypassed_by", frappe.user.full_name());
    } else {
      frm.set_value("bypassed_by", "");
      frm.set_value("bypass_reason", "");
    }
  },
});

function alert_signed_amount_mismatch(frm) {
  const { signed_amount, total_amount } = frm.doc;
  if (
    !signed_amount ||
    !total_amount ||
    flt(signed_amount, 0) === flt(total_amount, 0)
  )
    return;

  frappe.show_alert(
    {
      message: __("Signed Amount {0} is different from Total Amount {1}", [
        format_number(signed_amount, null, 0),
        format_number(total_amount, null, 0),
      ]),
      indicator: "orange",
    },
    10
  );
}

function needs_folio_signature(frm) {
  return (
    frm.doc.docstatus === 0 &&
    !frm.doc.patient_signature &&
    !frm.doc.folio_signed
  );
}

/**
 * Show dialog to choose signature method (Signature or Fingerprint)
 */
function show_signature_method_dialog(frm) {
  // Repeated saves must not stack dialogs on top of each other
  if (frm.sign_folio_in_progress) return;
  frm.sign_folio_in_progress = true;

  let method = null;
  const dialog = new frappe.ui.Dialog({
    title: __("Sign Folio:"),
    fields: [
      {
        fieldtype: "HTML",
        fieldname: "info_html",
        options: `
          <style>
            .signature-option { cursor: pointer; padding: 20px; border: 2px solid #ccc; border-radius: 10px; width: 150px; text-align: center; }
            .signature-option:hover { border-color: #5e64ff; background-color: #f0f4ff; }
          </style>
          <div style="text-align: center; padding: 20px;">
            <p style="font-size: 14px; margin-bottom: 20px;">
              ${__("Please select the signature method")}
            </p>
            <div style="display: flex; justify-content: center; gap: 30px; flex-wrap: wrap;">
              <div class="signature-option" data-method="signature">
                <i class="fa fa-pencil" style="font-size: 48px; color: #5e64ff;"></i>
                <p style="margin-top: 10px; font-weight: bold;">${__(
                  "Signature"
                )}</p>
                <small>${__("Draw signature with pen")}</small>
              </div>
              <div class="signature-option" data-method="fingerprint">
                <i class="fa fa-hand-paper-o" style="font-size: 48px; color: #28a745;"></i>
                <p style="margin-top: 10px; font-weight: bold;">${__(
                  "Fingerprint"
                )}</p>
                <small>${__("Use fingerprint device")}</small>
              </div>
            </div>
          </div>
        `,
      },
    ],
    size: "small",
    secondary_action_label: __("Cancel"),
    secondary_action: () => dialog.hide(),
  });

  dialog.$wrapper.find(".signature-option").on("click", function () {
    method = $(this).data("method");
    dialog.hide();
  });

  // Open the next modal only after this one is gone, otherwise the backdrop can stay stuck
  dialog.$wrapper.one("hidden.bs.modal", async () => {
    dialog.$wrapper.remove();
    try {
      if (method === "signature") {
        await capture_signature_and_sign(frm);
      } else if (method === "fingerprint") {
        await capture_fingerprint_and_sign(frm);
      }
    } finally {
      frm.sign_folio_in_progress = false;
    }
  });

  dialog.show();
}

/**
 * Capture handwritten signature using the Signature class and sign folio
 */
async function capture_signature_and_sign(frm) {
  const signature = await new Signature({
    label: __("Sign Folio"),
    title: __("Sign Folio - Draw Signature"),
    fields: [
      {
        fieldtype: "Data",
        fieldname: "signed_by_name",
        label: __("Signer Name"),
        reqd: 1,
        default: [frm.doc.first_name, frm.doc.last_name]
          .filter(Boolean)
          .join(" "),
      },
      { fieldtype: "Column Break" },
      {
        fieldtype: "Select",
        fieldname: "signed_by",
        label: __("Relationship to Patient"),
        options: [
          "PATIENT",
          "PARENT",
          "CHILD",
          "SPOUSE",
          "SISTER",
          "BROTHER",
          "RELATIVE",
          "FRIEND",
          "OTHER",
        ].map((value) => ({
          value,
          label: __(frappe.utils.to_title_case(value)),
        })),
        default: "PATIENT",
        reqd: 1,
      },
      { fieldtype: "Section Break" },
    ],
  });
  // Closed without signing: the dialog shows again on the next save
  if (!signature) return;

  const r = await frappe.call({
    method: "hms_tz.nhif.nhif_api.patient_claim.sign_folio",
    args: {
      ref_doctype: frm.doc.doctype,
      ref_docname: frm.doc.name,
      signature_method: "signature",
      signature: signature.Data,
      ...signature.values,
    },
    freeze: true,
    freeze_message: __("Signing folio with NHIF..."),
  });

  if (r.message && r.message !== "Error") {
    frappe.utils.play_sound("submit");
    frm.reload_doc();
  } else {
    frappe.utils.play_sound("error");
  }
}

/**
 * Capture fingerprint and sign folio
 */
async function capture_fingerprint_and_sign(frm) {
  try {
    let fingerprint = await new Fingerprint({ label: "Sign Folio" });
    if (!fingerprint) {
      frappe.msgprint(__("Fingerprint capture failed. Please try again."));
      return;
    }

    frappe.call({
      method: "hms_tz.nhif.nhif_api.patient_claim.sign_folio",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        signature_method: "fingerprint",
        fingerprint: fingerprint.Data,
        fpcode: fingerprint.fpCode,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message && r.message !== "Error") {
          frappe.utils.play_sound("submit");
          // frappe.show_alert({
          //   message: __("Folio signed successfully with fingerprint!"),
          //   indicator: "green",
          // });
          frm.reload_doc();
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  } catch (error) {
    console.error("Fingerprint capture error:", error);
    frappe.msgprint(__("Fingerprint capture failed. Please try again."));
  }
}
