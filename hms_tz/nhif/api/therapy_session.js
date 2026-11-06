frappe.ui.form.on("Therapy Session", {
  refresh: function (frm) {
    $('[data-label="Not%20Serviced"]').parent().hide();
    if (!frm.doc.__islocal && frm.doc.status == "Not Serviced") {
      frm.clear_custom_buttons();
      // frm.remove_custom_button("Create")
    }
    if (frm.doc.patient) {
      frm.add_custom_button(__("Patient History"), () => {
        frappe.route_options = { patient: frm.doc.patient };
        frappe.set_route("tz-patient-history");
      });
    }
    render_ts_consumables_section(frm);
    RequestApproval.show_restricted_banner(frm);
    NHIFUnissuedServices.add_button(frm);
  },
  onload: function (frm) {
    $('[data-label="Not%20Serviced"]').parent().hide();
    if (!frm.doc.__islocal && frm.doc.status == "Not Serviced") {
      frm.clear_custom_buttons();
      // frm.remove_custom_button("Create")
    }
    if (frm.doc.patient) {
      frm.add_custom_button(__("Patient History"), () => {
        frappe.route_options = { patient: frm.doc.patient };
        frappe.set_route("tz-patient-history");
      });
    }
  },
  approval_number: (frm) => {
    RequestApproval.show_restricted_banner(frm);
  },
  is_restricted: (frm) => {
    RequestApproval.show_restricted_banner(frm);
  },
  request_approval_no: (frm) => {
    if (
      !frm.doc.insurance_company ||
      !frm.doc.insurance_company.includes("NHIF")
    ) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    new RequestApproval({
      frm: frm,
      ref_doctype: frm.doc.doctype,
      ref_docname: frm.doc.name,
      service_type: "Therapy Type",
      service_name: frm.doc.therapy_type,
      encounter_no: frm.doc.ref_docname,
      supportive_document: frm.doc.support_document || "",
    });
  },
  update_approval_request: (frm) => {
    if (
      !frm.doc.insurance_company ||
      !frm.doc.insurance_company.includes("NHIF")
    ) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    if (!frm.doc.insurance_subscription) {
      frappe.msgprint(
        "Insurance Subscription is required to request approval"
      );
      return;
    }

    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.update_service_approval",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        service_type: "Therapy Type",
        service_name: frm.doc.therapy_type,
        qty: 1,
        item_authorization_id: frm.doc.item_authorization_id,
        service_authorization_id: frm.doc.service_authorization_id,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          frm.refresh();
          if (r.message.status == "success") {
            frappe.show_alert(
              {
                message: __(
                  "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                                Approval Request Successful. Reference Number: " +
                    r.message.reference_no +
                    "</h4>"
                ),
                indicator: "green",
              },
              15
            );
            if (frm.is_dirty()) {
              frm.save();
            }
            frappe.utils.play_sound("submit");
            frm.reload_doc();
          } else {
            frappe.show_alert(
              {
                message: __(
                  "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                                Approval Request Failed: </h4>"
                ),
                indicator: "red",
              },
              20
            );
            frappe.utils.play_sound("error");
          }
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  },
  get_approval_status: (frm) => {
    if (
      !frm.doc.insurance_company ||
      !frm.doc.insurance_company.includes("NHIF")
    ) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_approval_status",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          frm.refresh();
          if (r.message.status == "success") {
            frappe.show_alert(
              {
                message: __(
                  "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                                Request Approval Status Successful. Reference Number: " +
                    r.message.reference_no +
                    "</h4>"
                ),
                indicator: "green",
              },
              15
            );
            if (frm.is_dirty()) {
              frm.save();
            }
            frappe.utils.play_sound("submit");
            frm.reload_doc();
          } else {
            frappe.show_alert(
              {
                message: __(
                  "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                                Request Approval Status Failed: </h4>"
                ),
                indicator: "red",
              },
              20
            );
            frappe.utils.play_sound("error");
          }
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  },
  verify_approval_no: (frm) => {
    if (!frm.doc.insurance_company.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }
    if (!frm.doc.approval_number) {
      frappe.msgprint("Approval Number is required to verify");
      return;
    }
    frappe
      .call({
        method: "hms_tz.nhif.nhif_api.approval.verify_approval_number",
        args: {
          company: frm.doc.company,
          approval_number: frm.doc.approval_number,
          service_type: "Therapy Type",
          service_name: frm.doc.therapy_type,
          appointment: frm.doc.appointment,
          ref_doctype: frm.doc.doctype,
          ref_docname: frm.doc.name,
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      })
      .then((r) => {
        if (
          r.message &&
          r.message == "approval number validation is disabled"
        ) {
          frappe.utils.play_sound("error");
          return;
        } else if (r.message) {
          if (frm.is_dirty()) {
            frm.save();
          }
          frappe.utils.play_sound("submit");
          frm.reload_doc();
          frappe.show_alert(
            {
              message: __(
                "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                        Approval Number is Valid</h4>"
              ),
              indicator: "green",
            },
            20
          );
        } else {
          frappe.utils.play_sound("error");
          frm.set_value("approval_number", "");
          frappe.show_alert(
            {
              message: __(
                "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                        Approval Number is not Valid</h4>"
              ),
              indicator: "Red",
            },
            20
          );
        }
      });
  },
  get_poc_reference_no: async (frm) => {
    if (frm.doc.poc_reference_no) return;

    if (!frm.doc.insurance_company.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    let biometricData;

    if (frm.doc.biometric_method === "FACIAL") {
      biometricData = await new FacialRecognition({
        label: "Get POC Reference No",
      });
      if (!biometricData) {
        frappe.msgprint(__("Face capture failed. Please try again."));
        return;
      }
    } else if (frm.doc.biometric_method === "FINGERPRINT") {
      biometricData = await new Fingerprint({ label: "Get POC Reference No" });
      if (!biometricData) {
        frappe.msgprint(__("Fingerprint capture failed. Please try again."));
        return;
      }
    } else {
      const confirmed = await new Promise((resolve) => {
        frappe.confirm(
          __(`
            <div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
              <p class="text-center"><i>Biometric Method: <b>${frm.doc.biometric_method}</b> is only used when Patient is not able to take fingerprint or face.</i></p>
            </div>
            <br>
            <p class="text-center"><i>Are you sure you want to continue?</i></p>`),
          () => resolve(true),
          () => resolve(false)
        );
      });

      if (!confirmed) {
        return;
      }

      biometricData = { Data: "", fpCode: "" };
    }
    frappe.call({
      method: "hms_tz.nhif.utils.get_poc_reference_no_for_lrpmt",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        service_type: "Therapy Type",
        service_name: frm.doc.therapy_type,
        fingerprint: biometricData.Data,
        fpcode: biometricData.fpCode,
        biometric_method: frm.doc.biometric_method,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          if (r.message) {
            if (frm.is_dirty()) {
              frm.save();
            }
            frappe.utils.play_sound("submit");
            frm.reload_doc();
          } else {
            frappe.utils.play_sound("error");
          }
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  },
  issue_service: async (frm) => {
    if (frm.doc.service_reference_no) return;

    if (!frm.doc.insurance_company.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }
    if (frm.doc.is_restricted == 1 && !frm.doc.approval_number) {
      frappe.msgprint("Approval Number is required to issue approved service");
      return;
    }

    let biometricData;

    if (frm.doc.biometric_method === "FACIAL") {
      biometricData = await new FacialRecognition({ label: "Issue Service" });
      if (!biometricData) {
        frappe.msgprint(__("Face capture failed. Please try again."));
        return;
      }
    } else if (frm.doc.biometric_method === "FINGERPRINT") {
      biometricData = await new Fingerprint({ label: "Issue Service" });
      if (!biometricData) {
        frappe.msgprint(__("Fingerprint capture failed. Please try again."));
        return;
      }
    } else {
      const confirmed = await new Promise((resolve) => {
        frappe.confirm(
          __(`
            <div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
              <p class="text-center"><i>Biometric Method: <b>${frm.doc.biometric_method}</b> is only used when Patient is not able to take fingerprint or face.</i></p>
            </div>
            <br>
            <p class="text-center"><i>Are you sure you want to continue?</i></p>`),
          () => resolve(true),
          () => resolve(false)
        );
      });

      if (!confirmed) {
        return;
      }

      biometricData = { Data: "", fpCode: "" };
    }

    frappe.call({
      method: "hms_tz.nhif.utils.issue_nhif_service",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        service_type: "Therapy Type",
        service_name: frm.doc.therapy_type,
        fingerprint: biometricData.Data,
        fpcode: biometricData.fpCode,
        biometric_method: frm.doc.biometric_method,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          if (frm.is_dirty()) {
            frm.save();
          }
          frappe.utils.play_sound("submit");
          frm.reload_doc();
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  },
});

// ─── Consumables Section (same pattern as Preoperative Assessment) ───

function render_ts_consumables_section(frm) {
  if (!frm.fields_dict.ts_consumables_html) return;

  if (frm.is_new() || !frm.doc.patient) {
    frm.fields_dict.ts_consumables_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Save the Therapy Session first to add consumables.") +
        "</div>"
    );
    return;
  }

  const $wrapper = frm.fields_dict.ts_consumables_html.$wrapper;
  $wrapper.empty();

  const $btn_container = $(
    '<div class="d-flex justify-content-end mb-3" style="gap: 8px;"></div>'
  ).appendTo($wrapper);

  $('<button class="btn btn-primary btn-sm">')
    .html('<i class="fa fa-plus mr-1"></i>' + __("Add Consumables"))
    .on("click", () => {
      if (!window.hms_tz || !hms_tz.open_consumable_dialog) {
        frappe.msgprint(
          __("Consumable dialog not loaded. Please reload the page.")
        );
        return;
      }
      hms_tz.open_consumable_dialog({
        patient: frm.doc.patient,
        patient_name: frm.doc.patient_name,
        appointment: frm.doc.appointment || "",
        company: frm.doc.company,
        payment_type: frm.doc.insurance_company ? "Insurance" : "Cash",
        insurance_subscription: frm.doc.insurance_subscription || "",
        insurance_company: frm.doc.insurance_company || "",
        insurance_coverage_plan: frm.doc.hms_tz_insurance_coverage_plan || "",
        prescribed_by: frm.doc.practitioner,
        source_doctype: "Therapy Session",
        source_docname: frm.doc.name,
        service_name: frm.doc.therapy_type || "",
        on_success: () => {
          frm.reload_doc();
        },
      });
    })
    .appendTo($btn_container);

  const filters = { patient: frm.doc.patient };
  if (frm.doc.appointment) {
    filters.appointment = frm.doc.appointment;
  }

  frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Consumable Record",
      filters: filters,
      fields: [
        "name",
        "posting_date",
        "status",
        "total_amount",
        "payment_type",
        "delivery_note",
        "docstatus",
      ],
      order_by: "creation desc",
      limit_page_length: 50,
    },
    callback: (r) => {
      if (!r.message || r.message.length === 0) {
        $('<div class="text-muted text-center p-3">')
          .text(__("No consumable records yet."))
          .appendTo($wrapper);
        return;
      }

      const records = r.message;
      let table_html =
        '<div class="table-responsive"><table class="table table-bordered table-sm">';
      table_html += "<thead><tr>";
      table_html += '<th class="text-left">' + __("Record") + "</th>";
      table_html += '<th class="text-left">' + __("Date") + "</th>";
      table_html += '<th class="text-left">' + __("Payment") + "</th>";
      table_html += '<th class="text-right">' + __("Total") + "</th>";
      table_html += '<th class="text-center">' + __("Status") + "</th>";
      table_html += '<th class="text-left">' + __("Delivery Note") + "</th>";
      table_html += '<th class="text-center">' + __("Action") + "</th>";
      table_html += "</tr></thead><tbody>";

      records.forEach((rec) => {
        const status_color = {
          Draft: "orange",
          Submitted: "blue",
          "Pending Payment": "red",
          Dispensed: "green",
          Finalized: "darkgreen",
          Billed: "purple",
        };
        const color = status_color[rec.status] || "gray";

        table_html += "<tr>";
        table_html +=
          '<td><a href="/app/consumable-record/' +
          rec.name +
          '">' +
          rec.name +
          "</a></td>";
        table_html += "<td>" + (rec.posting_date || "") + "</td>";
        table_html += "<td>" + (rec.payment_type || "") + "</td>";
        table_html +=
          '<td class="text-right">' +
          format_currency(rec.total_amount || 0) +
          "</td>";
        table_html +=
          '<td class="text-center"><span class="indicator-pill ' +
          color +
          '">' +
          (rec.status || "Draft") +
          "</span></td>";
        table_html +=
          "<td>" +
          (rec.delivery_note
            ? '<a href="/app/delivery-note/' +
              rec.delivery_note +
              '">' +
              rec.delivery_note +
              "</a>"
            : "-") +
          "</td>";

        if (rec.docstatus === 0) {
          table_html +=
            '<td class="text-center"><button class="btn btn-xs btn-primary btn-submit-consumable" data-name="' +
            rec.name +
            '">' +
            __("Submit") +
            "</button></td>";
        } else {
          table_html += '<td class="text-center">-</td>';
        }
        table_html += "</tr>";
      });

      table_html += "</tbody></table></div>";
      const $table = $(table_html).appendTo($wrapper);

      $table.find(".btn-submit-consumable").on("click", function () {
        const consumable_name = $(this).data("name");
        frappe.confirm(
          __("Are you sure you want to submit Consumable Record {0}?", [
            consumable_name,
          ]),
          () => {
            frappe.call({
              method:
                "hms_tz.hms_tz.doctype.consumable_record.consumable_api.submit_consumable_record",
              args: { consumable_record: consumable_name },
              freeze: true,
              freeze_message: __("Submitting..."),
              callback: (r) => {
                if (!r.exc) {
                  frappe.show_alert({
                    message: __("Consumable Record {0} submitted.", [
                      consumable_name,
                    ]),
                    indicator: "green",
                  });
                  frm.reload_doc();
                }
              },
            });
          }
        );
      });
    },
  });
}
