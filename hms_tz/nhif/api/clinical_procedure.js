frappe.ui.form.on("Clinical Procedure", {
  setup: function (frm) {
    frm.set_query("practitioner", () => {
      return { filters: { practitioner_role: "Doctor" } };
    });
    frm.set_query("ot_schedule", () => {
      return {
        filters: {
          patient: frm.doc.patient,
          company: frm.doc.company,
          procedure_template: frm.doc.procedure_template,
        },
      };
    });
  },
  refresh: function (frm) {
    $('[data-label="Not%20Serviced"]').parent().hide();
    frm.remove_custom_button("Start");
    frm.remove_custom_button("Complete");

    render_cp_consumables_section(frm);
    render_cp_vital_signs(frm);
    render_cp_anesthesia_records(frm);
    render_cp_implant_specimen_buttons(frm);
  },

  onload: function (frm) {
    $('[data-label="Not%20Serviced"]').parent().hide();
    frm.remove_custom_button("Start");
    frm.remove_custom_button("Complete");
    if (frm.doc.patient) {
      frm.add_custom_button(__("Patient History"), function () {
        frappe.route_options = { patient: frm.doc.patient };
        frappe.set_route("tz-patient-history");
      });
    }
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

    if (!frm.doc.insurance_subscription) {
      frappe.msgprint(
        "Insurance Subscription is required to request approval"
      );
      return;
    }

    new RequestApproval({
      frm: frm,
      ref_doctype: frm.doc.doctype,
      ref_docname: frm.doc.name,
      service_type: "Clinical Procedure Template",
      service_name: frm.doc.procedure_template,
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
        service_type: "Clinical Procedure Template",
        service_name: frm.doc.procedure_template,
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
            frm.save().then(() => {
              frm.reload_doc();
            });

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
            frappe.utils.play_sound("submit");
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
            frm.save().then(() => {
              frm.reload_doc();
            });

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
            frappe.utils.play_sound("submit");
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
          service_type: "Clinical Procedure Template",
          service_name: frm.doc.procedure_template,
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
          frappe.utils.play_sound("submit");
          frm.save().then(() => {
            frm.reload_doc();
          });

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
        service_type: "Clinical Procedure Template",
        service_name: frm.doc.procedure_template,
        fingerprint: biometricData.Data,
        fpcode: biometricData.fpCode,
        biometric_method: frm.doc.biometric_method,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          if (r.message) {
            frm.save().then(() => {
              frm.reload_doc();
            });

            frappe.utils.play_sound("submit");
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
        service_type: "Clinical Procedure Template",
        service_name: frm.doc.procedure_template,
        fingerprint: biometricData.Data,
        fpcode: biometricData.fpCode,
        biometric_method: frm.doc.biometric_method,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          frappe.utils.play_sound("submit");
          let data = r.message;
          frm.save().then(() => {
            frm.reload_doc();
          });
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  },
});

// ─── Consumables Section (same pattern as Preoperative Assessment) ───

function render_cp_consumables_section(frm) {
  if (!frm.fields_dict.cp_consumables_html) return;

  if (frm.is_new() || !frm.doc.patient) {
    frm.fields_dict.cp_consumables_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Save the Clinical Procedure first to add consumables.") +
        "</div>"
    );
    return;
  }

  const $wrapper = frm.fields_dict.cp_consumables_html.$wrapper;
  $wrapper.empty();

  // Button container
  const $btn_container = $(
    '<div class="d-flex justify-content-end mb-3" style="gap: 8px;"></div>'
  ).appendTo($wrapper);

  // "Add Consumables" button
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
        prescribed_by: "",
        source_doctype: "Clinical Procedure",
        source_docname: frm.doc.name,
        service_name: frm.doc.procedure_template || "",
        on_success: () => {
          frm.reload_doc();
        },
      });
    })
    .appendTo($btn_container);

  // Fetch and display existing consumable records
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

        // Action column — Submit button for draft records
        if (rec.docstatus === 0) {
          table_html +=
            '<td class="text-center">' +
            '<button class="btn btn-xs btn-primary btn-submit-consumable" data-name="' +
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

      // Wire submit buttons
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

// ─── Vital Signs (same pattern as Nurse Record) ───

function render_cp_vital_signs(frm) {
  if (!frm.fields_dict.cp_vital_signs_html) return;

  if (frm.is_new() || !frm.doc.patient) {
    frm.fields_dict.cp_vital_signs_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Save the Clinical Procedure first to record vital signs.") +
        "</div>"
    );
    return;
  }

  const $wrapper = frm.fields_dict.cp_vital_signs_html.$wrapper;
  $wrapper.empty();

  // Button container (same pattern as consumables)
  const $btn_container = $(
    '<div class="d-flex justify-content-end mb-3" style="gap: 8px;"></div>'
  ).appendTo($wrapper);

  // "Record Vital Signs" button
  if (frm.doc.docstatus !== 2) {
    $('<button class="btn btn-primary btn-sm">')
      .html('<i class="fa fa-heartbeat mr-1"></i>' + __("Record Vital Signs"))
      .on("click", () => {
        show_cp_vital_signs_dialog(frm);
      })
      .appendTo($btn_container);
  }

  // Fetch and display existing vital signs
  frappe.call({
    method: "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_vital_signs",
    args: {
      patient: frm.doc.patient,
      appointment: frm.doc.appointment || "",
    },
    callback: function (r) {
      if (r.message && r.message.length > 0) {
        render_cp_vitals_chart_and_table(frm, r.message, $wrapper);
      } else {
        $('<div class="text-muted text-center p-3">')
          .text(__("No vital signs recorded for this patient episode."))
          .appendTo($wrapper);
      }
    },
  });
}

function render_cp_vitals_chart_and_table(frm, vitals, $wrapper) {
  let chart_id = "cp-vitals-chart-" + frm.doc.name;
  $wrapper.append('<div class="mb-4"><div id="' + chart_id + '"></div></div>');

  let labels = vitals.map((v) => v.signs_date);
  let temp_data = vitals.map((v) => parseFloat(v.temperature) || 0);
  let pulse_data = vitals.map((v) => parseFloat(v.pulse) || 0);
  let rr_data = vitals.map((v) => parseFloat(v.respiratory_rate) || 0);
  let bp_sys_data = vitals.map((v) => parseFloat(v.bp_systolic) || 0);
  let bp_dia_data = vitals.map((v) => parseFloat(v.bp_diastolic) || 0);

  new frappe.Chart("#" + chart_id, {
    title: __("Vital Signs Trend"),
    data: {
      labels: labels,
      datasets: [
        { name: __("Temperature (°C)"), values: temp_data },
        { name: __("Pulse (bpm)"), values: pulse_data },
        { name: __("Respiratory Rate"), values: rr_data },
        { name: __("BP Systolic"), values: bp_sys_data },
        { name: __("BP Diastolic"), values: bp_dia_data },
      ],
    },
    type: "line",
    height: 280,
    colors: ["#ff6384", "#36a2eb", "#4bc0c0", "#ff9f40", "#9966ff"],
    lineOptions: { regionFill: 0, hideDots: 0 },
  });

  let table_html = '<table class="table table-bordered table-sm mt-3">';
  table_html += "<thead><tr>";
  table_html += "<th>" + __("Date") + "</th>";
  table_html += "<th>" + __("Time") + "</th>";
  table_html += "<th>" + __("Temp (°C)") + "</th>";
  table_html += "<th>" + __("Pulse") + "</th>";
  table_html += "<th>" + __("RR") + "</th>";
  table_html += "<th>" + __("BP") + "</th>";
  table_html += "<th>" + __("SpO2") + "</th>";
  table_html += "<th>" + __("RBG") + "</th>";
  table_html += "<th>" + __("Height (cm)") + "</th>";
  table_html += "<th>" + __("Weight (kg)") + "</th>";
  table_html += "<th>" + __("BMI") + "</th>";
  // table_html += "<th>" + __("Notes") + "</th>";
  table_html += "</tr></thead><tbody>";

  vitals.forEach((v) => {
    let bp_display = v.bp || v.bp_systolic + "/" + v.bp_diastolic;
    let time_display = v.signs_time ? v.signs_time.substring(0, 5) : "";
    table_html += "<tr>";
    table_html += "<td>" + (v.signs_date || "") + "</td>";
    table_html += "<td>" + time_display + "</td>";
    table_html += "<td>" + (v.temperature || "") + "</td>";
    table_html += "<td>" + (v.pulse || "") + "</td>";
    table_html += "<td>" + (v.respiratory_rate || "") + "</td>";
    table_html += "<td>" + bp_display + "</td>";
    table_html += "<td>" + (v.oxygen_saturation_spo2 || "") + "</td>";
    table_html += "<td>" + (v.rbg || "") + "</td>";
    table_html += "<td>" + (v.height_in_cm || "") + "</td>";
    table_html += "<td>" + (v.weight || "") + "</td>";
    table_html += "<td>" + (v.bmi || "") + "</td>";
    // table_html += "<td>" + (v.vital_signs_note || "") + "</td>";
    table_html += "</tr>";
  });

  table_html += "</tbody></table>";
  $wrapper.append(table_html);
}

function show_cp_vital_signs_dialog(frm) {
  let d = new frappe.ui.Dialog({
    title: __("Record Vital Signs"),
    fields: [
      {
        fieldname: "temperature",
        fieldtype: "Data",
        label: __("Temperature (°C)"),
      },
      { fieldname: "pulse", fieldtype: "Data", label: __("Pulse (bpm)") },
      {
        fieldname: "respiratory_rate",
        fieldtype: "Data",
        label: __("Respiratory Rate"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "bp_systolic",
        fieldtype: "Data",
        label: __("BP Systolic"),
      },
      {
        fieldname: "bp_diastolic",
        fieldtype: "Data",
        label: __("BP Diastolic"),
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "oxygen_saturation_spo2",
        fieldtype: "Data",
        label: __("SpO2 (%)"),
      },
      {
        fieldname: "rbg",
        fieldtype: "Float",
        label: __("Random Blood Glucose (RBG)"),
      },
      {
        fieldname: "abdomen",
        fieldtype: "Select",
        label: __("Abdomen"),
        options: "\nNormal\nBloated\nFull\nFluid\nConstipated",
      },
      { fieldtype: "Column Break" },
      { fieldname: "weight", fieldtype: "Float", label: __("Weight (kg)") },
      {
        fieldname: "height_in_cm",
        fieldtype: "Int",
        label: __("Height (cm)"),
      },
      {
        fieldname: "reflexes",
        fieldtype: "Select",
        label: __("Reflexes"),
        options: "\nNormal\nHyper\nVery Hyper\nOne Sided",
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "vital_signs_note",
        fieldtype: "Small Text",
        label: __("Notes"),
      },
      {
        fieldname: "signs_date",
        fieldtype: "Date",
        label: __("Date Taken"),
        default: frappe.datetime.get_today(),
        reqd: 1,
      },
      {
        fieldname: "signs_time",
        fieldtype: "Time",
        label: __("Time Taken"),
        default: frappe.datetime.now_time(),
        reqd: 1,
      },
      { fieldtype: "Section Break" },
    ],
    primary_action_label: __("Save"),
    primary_action(values) {
      frappe.call({
        method:
          "hms_tz.nhif.api.clinical_procedure.create_vital_signs_from_cp",
        args: {
          clinical_procedure: frm.doc.name,
          ...values,
        },
        callback: function (r) {
          if (r.message) {
            frappe.show_alert({
              message: __("Vital Signs {0} created and submitted", [
                r.message,
              ]),
              indicator: "green",
            });
            d.hide();
            render_cp_vital_signs(frm);
          }
        },
      });
    },
  });
  d.show();
}

// ─── Anesthesia Records ───

function render_cp_anesthesia_records(frm) {
  if (!frm.fields_dict.cp_anesthesia_html) return;

  if (frm.is_new() || !frm.doc.patient) {
    frm.fields_dict.cp_anesthesia_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Save the Clinical Procedure first to add anesthesia records.") +
        "</div>"
    );
    return;
  }

  const $wrapper = frm.fields_dict.cp_anesthesia_html.$wrapper;
  $wrapper.empty();

  // Button container (same pattern as consumables)
  const $btn_container = $(
    '<div class="d-flex justify-content-end mb-3" style="gap: 8px;"></div>'
  ).appendTo($wrapper);

  // "Add Anesthesia" button
  if (frm.doc.docstatus !== 2) {
    $('<button class="btn btn-primary btn-sm">')
      .html('<i class="fa fa-medkit mr-1"></i>' + __("Add Anesthesia"))
      .on("click", () => {
        show_cp_anesthesia_dialog(frm);
      })
      .appendTo($btn_container);
  }

  // Fetch and display existing anesthesia records
  frappe.call({
    method: "hms_tz.nhif.api.clinical_procedure.get_anesthesia_records",
    args: { clinical_procedure: frm.doc.name },
    callback: function (r) {
      if (!r.message || r.message.length === 0) {
        $('<div class="text-muted text-center p-3">')
          .text(__("No anesthesia records yet."))
          .appendTo($wrapper);
        return;
      }

      let records = r.message;
      let html =
        '<div class="table-responsive"><table class="table table-bordered table-sm">';
      html += "<thead><tr>";
      html += "<th>" + __("Record") + "</th>";
      html += "<th>" + __("Anesthetist") + "</th>";
      html += "<th>" + __("Type") + "</th>";
      html += "<th>" + __("ASA Grade") + "</th>";
      html += "<th>" + __("Start") + "</th>";
      html += "<th>" + __("End") + "</th>";
      html += "<th>" + __("Complications") + "</th>";
      html += "</tr></thead><tbody>";

      records.forEach((rec) => {
        html += "<tr>";
        html +=
          '<td><a href="/app/anesthesia-record/' +
          rec.name +
          '">' +
          rec.name +
          "</a></td>";
        html +=
          "<td>" + (rec.anesthetist_name || rec.anesthetist || "") + "</td>";
        html += "<td>" + (rec.anesthesia_type || "") + "</td>";
        html += "<td>" + (rec.asa_grade || "") + "</td>";
        html += "<td>" + (rec.start_time || "") + "</td>";
        html += "<td>" + (rec.end_time || "") + "</td>";
        html += "<td>" + (rec.complications || "-") + "</td>";
        html += "</tr>";
      });

      html += "</tbody></table></div>";
      $(html).appendTo($wrapper);
    },
  });
}

function show_cp_anesthesia_dialog(frm) {
  let d = new frappe.ui.Dialog({
    title: __("Add Anesthesia Record"),
    size: "large",
    fields: [
      {
        fieldname: "anesthetist",
        fieldtype: "Link",
        label: __("Anesthetist"),
        options: "Healthcare Practitioner",
        reqd: 1,
        get_query: function () {
          return {
            filters: {
              status: "Active",
              practitioner_role: "Doctor",
              hms_tz_company: frm.doc.company,
            },
          };
        },
      },
      {
        fieldname: "anesthesia_type",
        fieldtype: "Select",
        label: __("Anesthesia Type"),
        options: "\nGeneral\nRegional\nLocal\nSpinal\nEpidural\nSedation",
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "airway_approach",
        fieldtype: "Select",
        label: __("Airway Approach"),
        options: "\nIntubation\nLMA\nMask\nNatural",
      },
      {
        fieldname: "asa_grade",
        fieldtype: "Select",
        label: __("ASA Grade"),
        options: "\nASA I\nASA II\nASA III\nASA IV\nASA V\nASA VI",
      },
      { fieldtype: "Section Break", label: __("Timing") },
      { fieldname: "start_time", fieldtype: "Time", label: __("Start Time") },
      { fieldname: "end_time", fieldtype: "Time", label: __("End Time") },
      { fieldtype: "Section Break", label: __("Vitals") },
      {
        fieldname: "pre_induction_vitals",
        fieldtype: "Small Text",
        label: __("Pre-Induction Vitals"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "post_induction_vitals",
        fieldtype: "Small Text",
        label: __("Post-Induction Vitals"),
      },
      { fieldtype: "Section Break", label: __("Drugs Administered") },
      {
        fieldname: "drugs",
        fieldtype: "Table",
        label: __("Drugs Administered"),
        fields: [
          {
            fieldname: "drug",
            fieldtype: "Link",
            label: __("Drug"),
            options: "Medication",
            in_list_view: 1,
            reqd: 1,
            get_query: function () {
              return {
                filters: {
                  disabled: 0,
                },
              };
            },
          },
          {
            fieldname: "dosage",
            fieldtype: "Link",
            label: __("Dosage"),
            options: "Prescription Dosage",
            in_list_view: 1,
            reqd: 1,
          },
          {
            fieldname: "route",
            fieldtype: "Select",
            label: __("Route"),
            options: "\nIV\nIM\nInhalation\nOral\nSubcutaneous",
            in_list_view: 1,
            reqd: 1,
          },
          {
            fieldname: "administered_time",
            fieldtype: "Time",
            label: __("Administered Time"),
            in_list_view: 1,
            reqd: 1,
          },
        ],
      },
      { fieldtype: "Section Break", label: __("Notes") },
      {
        fieldname: "complications",
        fieldtype: "Small Text",
        label: __("Complications"),
      },
      { fieldname: "notes", fieldtype: "Text", label: __("Notes") },
    ],
    primary_action_label: __("Create"),
    primary_action(values) {
      frappe.call({
        method: "hms_tz.nhif.api.clinical_procedure.create_anesthesia_record",
        args: {
          clinical_procedure: frm.doc.name,
          ...values,
        },
        freeze: true,
        freeze_message: __("Creating Anesthesia Record..."),
        callback: function (r) {
          if (r.message) {
            frappe.show_alert({
              message: __("Anesthesia Record {0} created.", [r.message]),
              indicator: "green",
            });
            d.hide();
            render_cp_anesthesia_records(frm);
          }
        },
      });
    },
  });
  d.show();
}

// ─── Implant & Specimen Buttons ───

function render_cp_implant_specimen_buttons(frm) {
  if (!frm.fields_dict.implant_specimen_bts) return;

  if (frm.is_new() || !frm.doc.patient) {
    frm.fields_dict.implant_specimen_bts.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Save the Clinical Procedure first.") +
        "</div>"
    );
    return;
  }

  const $wrapper = frm.fields_dict.implant_specimen_bts.$wrapper;
  $wrapper.empty();

  if (frm.doc.docstatus === 2) return;

  const $btn_container = $(
    '<div class="d-flex justify-content-end mb-3" style="gap: 8px;"></div>'
  ).appendTo($wrapper);

  // "Add Implant" button
  $('<button class="btn btn-primary btn-sm">')
    .html('<i class="fa fa-cube mr-1"></i>' + __("Add Implant"))
    .on("click", () => {
      show_cp_implant_dialog(frm);
    })
    .appendTo($btn_container);

  // "Add Specimen" button
  $('<button class="btn btn-primary btn-sm">')
    .html('<i class="fa fa-flask mr-1"></i>' + __("Add Specimen"))
    .on("click", () => {
      show_cp_specimen_dialog(frm);
    })
    .appendTo($btn_container);
}

function show_cp_implant_dialog(frm) {
  let d = new frappe.ui.Dialog({
    title: __("Add Implant"),
    size: "large",
    fields: [
      {
        fieldname: "implant_type",
        fieldtype: "Data",
        label: __("Implant Type"),
        reqd: 1,
      },
      {
        fieldname: "manufacturer",
        fieldtype: "Data",
        label: __("Manufacturer"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "lot_number",
        fieldtype: "Data",
        label: __("Lot Number"),
      },
      {
        fieldname: "serial_number",
        fieldtype: "Data",
        label: __("Serial Number"),
      },
      { fieldtype: "Section Break", label: __("Implant Details") },
      {
        fieldname: "anatomical_location",
        fieldtype: "Data",
        label: __("Anatomical Location"),
      },
      {
        fieldname: "expiry_date",
        fieldtype: "Date",
        label: __("Expiry Date"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "implanted_by",
        fieldtype: "Link",
        label: __("Implanted By"),
        options: "Healthcare Practitioner",
        get_query: function () {
          return {
            filters: {
              status: "Active",
              practitioner_role: "Doctor",
              hms_tz_company: frm.doc.company,
            },
          };
        },
      },
      {
        fieldname: "implant_date",
        fieldtype: "Date",
        label: __("Implant Date"),
        default: frappe.datetime.get_today(),
      },
      { fieldtype: "Section Break", label: __("Status & Notes") },
      {
        fieldname: "status",
        fieldtype: "Select",
        label: __("Status"),
        options: "Planned\nImplanted\nRemoved\nReplaced",
        default: "Implanted",
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "notes",
        fieldtype: "Small Text",
        label: __("Notes"),
      },
    ],
    primary_action_label: __("Create & Submit"),
    primary_action(values) {
      frappe.call({
        method: "hms_tz.nhif.api.clinical_procedure.create_implant_registry",
        args: {
          clinical_procedure: frm.doc.name,
          ...values,
        },
        freeze: true,
        freeze_message: __("Creating Implant Registry..."),
        callback: function (r) {
          if (r.message) {
            frappe.show_alert({
              message: __("Implant Registry {0} created and submitted.", [
                r.message,
              ]),
              indicator: "green",
            });
            d.hide();
            frm.reload_doc();
          }
        },
      });
    },
  });
  d.show();
}

function show_cp_specimen_dialog(frm) {
  let d = new frappe.ui.Dialog({
    title: __("Add Specimen"),
    size: "large",
    fields: [
      {
        fieldname: "patient",
        fieldtype: "Link",
        label: __("Patient"),
        options: "Patient",
        default: frm.doc.patient,
        read_only: 1,
      },
      {
        fieldname: "patient_name",
        fieldtype: "Data",
        label: __("Patient Name"),
        default: frm.doc.patient_name,
        read_only: 1,
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "patient_sex",
        fieldtype: "Data",
        label: __("Gender"),
        default: frm.doc.patient_sex,
        read_only: 1,
      },
      {
        fieldname: "patient_age",
        fieldtype: "Data",
        label: __("Age"),
        default: frm.doc.patient_age,
        read_only: 1,
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "specimen_name",
        fieldtype: "Data",
        label: __("Specimen Name"),
        reqd: 1,
      },
      {
        fieldname: "biopsy_type",
        fieldtype: "Select",
        label: __("Biopsy Type"),
        options: "Incision\nExcision\nResection\nOther",
        reqd: 1,
      },
      {
        fieldname: "fixative_used",
        fieldtype: "Select",
        label: __("Fixative Used"),
        options: "\nFormalin\nOther",
      },
      {
        fieldname: "time_placed_in_fixative",
        fieldtype: "Time",
        label: __("Time Placed in Fixative"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "side",
        fieldtype: "Select",
        label: __("Side"),
        options: "\nRight\nLeft\nNA",
      },
      {
        fieldname: "no_of_containers",
        fieldtype: "Int",
        label: __("No. of Containers"),
      },
      {
        fieldname: "special_request",
        fieldtype: "Select",
        label: __("Special Request (if any)"),
        options: "\nUrgent\nFrozen Section\nIHC\nSpecial Stain\nOther",
      },
      {
        fieldname: "practitioner",
        fieldtype: "Link",
        label: __("Collected By"),
        options: "Healthcare Practitioner",
        get_query: function () {
          return {
            filters: {
              status: "Active",
              hms_tz_company: frm.doc.company,
            },
          };
        },
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "site_collected",
        fieldtype: "Data",
        label: __("Site Collected"),
        description: __(
          "exact location: eg. left breast, upper lobe of the right lung, etc"
        ),
        reqd: 1,
      },
      {
        fieldname: "collection_date",
        fieldtype: "Date",
        label: __("Collection Date"),
        default: frappe.datetime.now_date(),
        reqd: 1,
      },
      {
        fieldname: "collection_time",
        fieldtype: "Time",
        label: __("Collection Time"),
        default: frappe.datetime.now_time(),
        reqd: 1,
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "provisional_diagnosis",
        fieldtype: "Small Text",
        label: __("Provisional Diagnosis"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "relevant_findings",
        fieldtype: "Small Text",
        label: __("Revelevant History/Findings"),
      },
    ],
    primary_action_label: __("Create"),
    primary_action(values) {
      frappe.call({
        method: "hms_tz.nhif.api.clinical_procedure.create_surgical_specimen",
        args: {
          clinical_procedure: frm.doc.name,
          ...values,
        },
        freeze: true,
        freeze_message: __("Creating Surgical Specimen..."),
        callback: function (r) {
          if (r.message) {
            frappe.show_alert({
              message: __("Surgical Specimen {0} created.", [r.message]),
              indicator: "green",
            });
            d.hide();
            frm.reload_doc();
          }
        },
      });
    },
  });
  d.show();
}
