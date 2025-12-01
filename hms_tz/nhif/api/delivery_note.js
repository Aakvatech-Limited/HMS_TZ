frappe.ui.form.on("Delivery Note", {
  refresh(frm) {
    $('[data-label="Not%20Serviced"]').parent().hide();
    $('[data-label="Request%20Changes"]').parent().hide();
    $('[data-label="Make%20Changes"]').parent().hide();
    $('[data-label="Issue%20Returns"]').parent().hide();
    $('[data-label="Return"]').parent().hide();

    if (!frappe.user.has_role("DN Changed Allowed")) {
      // hide button to add rows of delivery note item
      frm.get_field("items").grid.cannot_add_rows = true;

      // hide button to delete rows of delivery note item
      $("*[data-fieldname='items']").find(".grid-remove-rows").hide();
      $("*[data-fieldname='items']").find(".grid-remove-all-rows").hide();
    }
  },
  onload(frm) {
    $('[data-label="Not%20Serviced"]').parent().hide();
    $('[data-label="Request%20Changes"]').parent().hide();
    $('[data-label="Make%20Changes"]').parent().hide();
    $('[data-label="Issue%20Returns"]').parent().hide();
    $('[data-label="Return"]').parent().hide();

    if (!frappe.user.has_role("DN Changed Allowed")) {
      // hide button to add rows of delivery note item
      frm.get_field("items").grid.cannot_add_rows = true;

      // hide button to delete rows of delivery note item
      $("*[data-fieldname='items']").find(".grid-remove-rows").hide();
      $("*[data-fieldname='items']").find(".grid-remove-all-rows").hide();
    }
  },
  hms_tz_lrpmt_returns: (frm) => {
    frappe.call({
      method:
        "hms_tz.nhif.api.healthcare_utils.return_quatity_or_cancel_delivery_note_via_lrpmt_returns",
      args: {
        source_doc: frm.doc,
        method: "From Front End",
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: (r) => {
        if (r.message == true) {
          frm.refresh();
        } else {
          frappe.set_route("FORM", "LRPMT Returns", r.message);
        }
      },
    });
  },
  hms_tz_medicatiion_change_request: (frm) => {
    if (!frm.doc.hms_tz_comment) {
      frappe.msgprint(
        "<b>Please write an item(s) to be changed on the comment field</b>"
      );
      return;
    }
    frappe.call({
      method:
        "hms_tz.nhif.doctype.medication_change_request.medication_change_request.create_medication_change_request_from_dn",
      args: {
        doctype: frm.doc.doctype,
        name: frm.doc.name,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: (r) => {},
    });
  },
  get_poc_reference_no: async (frm) => {
    if (!frm.doc.customer.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    if (frm.is_dirty()) {
      frappe.msgprint("Please save the document before issuing approved service");
      return;
    }

    let biometricData;

    if (frm.doc.biometric_method === "FACIAL") {
      biometricData = await new FacialRecognition({ label: "Get POC Reference No" });
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
            <p class="text-center"><i>Are you sure you want to continue?</i></p>`
          ),
          () => resolve(true),
          () => resolve(false)
        );
      });
      
      if (!confirmed) {
        return;
      }

      biometricData = {Data: "", fpCode: ""};
    }
    frappe.call({
      method: "hms_tz.nhif.utils.get_poc_reference_no_for_lrpmt",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        service_type: "Medication",
        service_name: "",
        fingerprint: biometricData.Data,
        fpcode: biometricData.fpCode,
        biometric_method: frm.doc.biometric_method,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          if (r.message) {
            frm.reload_doc();
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
    if (!frm.doc.customer.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    if (frm.is_dirty()) {
      frappe.msgprint("Please save the document before issuing approved service");
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
            <p class="text-center"><i>Are you sure you want to continue?</i></p>`
          ),
          () => resolve(true),
          () => resolve(false)
        );
      });
      
      if (!confirmed) {
        return;
      }

      biometricData = {Data: "", fpCode: ""};
    }

    frappe.call({
      method: "hms_tz.nhif.utils.issue_nhif_service",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        service_type: "Medication",
        service_name: "",
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
          // if (data.ReferenceNo) {
          //   frm.save().then(() => {
          //     frm.reload_doc();
          //   });
          // } 
        } else {
          frappe.utils.play_sound("error");
        }
      },
    });
  },
});

frappe.ui.form.on("Delivery Note Item", {
  form_render: (frm, cdt, cdn) => {
    if (!frappe.user.has_role("DN Changed Allowed")) {
      frm.fields_dict.items.grid.wrapper.find(".grid-delete-row").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-insert-row-below").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-insert-row").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-duplicate-row").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-move-row").hide();
    }
  },
  request_approval_no: (frm, cdt, cdn) => {
    if (!frm.doc.customer || !frm.doc.customer.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    if (frm.is_dirty()) {
      frappe.msgprint("Please save the document before requesting approval");
      return;
    }

    let row = locals[cdt][cdn];

    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_service_approval",
      args: {
        ref_doctype: frm.doctype,
        ref_docname: frm.docname,
        service_type: "Medication",
        service_name: "",
        qty: row.qty,
        item_code: row.item_code,
        reference_name: row.reference_name,
        reference_doctype: row.reference_doctype,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          frm.reload_doc();
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
  get_approval_status: (frm, cdt, cdn) => {
    if (!frm.doc.customer || !frm.doc.customer.includes("NHIF")) {
      frappe.show_alert(
        {
          message: __("This feature is only applicable for NHIF insurance"),
          indicator: "orange",
        },
        5
      );
      return;
    }

    if (frm.is_dirty()) {
      frappe.msgprint(
        "Please save the document before requesting approval status"
      );
      return;
    }

    let row = locals[cdt][cdn];

    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_approval_status",
      args: {
        ref_doctype: frm.doctype,
        ref_docname: frm.docname,
        dni_id: row.name,
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
  verify_approval_no: (frm, cdt, cdn) => {
    if (!frm.doc.customer || !frm.doc.customer.includes("NHIF")) {
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

    if (frm.is_dirty()) {
      frappe.msgprint(
        "Please save the document before requesting approval status"
      );
      return;
    }

    let row = locals[cdt][cdn];

    frappe
      .call({
        method: "hms_tz.nhif.nhif_api.approval.verify_approval_number",
        args: {
          company: frm.doc.company,
          approval_number: row.approval_number,
          service_type: "Medication",
          service_name: "",
          appointment: frm.doc.hms_tz_appointment_no,
          ref_doctype: frm.doctype,
          ref_docname: frm.docname,
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
});

frappe.ui.form.on("Original Delivery Note Item", {
  form_render: (frm, cdt, cdn) => {
    if (frm.doc.hms_tz_all_items_out_of_stock == 1) {
      frm.fields_dict.hms_tz_original_items.grid.wrapper
        .find('[data-fieldname="convert_to_in_stock_item"]')
        .hide();
    }
    if (locals[cdt][cdn].hms_tz_is_out_of_stock == 0) {
      frm.fields_dict.hms_tz_original_items.grid.wrapper
        .find('[data-fieldname="convert_to_in_stock_item"]')
        .hide();
    }
  },

  convert_to_in_stock_item: (frm, cdt, cdn) => {
    let original_row = frappe.get_doc(cdt, cdn);

    if (original_row.hms_tz_is_out_of_stock == 1) {
      frappe
        .call("hms_tz.nhif.api.delivery_note.convert_to_instock_item", {
          name: frm.doc.name,
          row: original_row,
        })
        .then((r) => {
          if (r.message) {
            frm.reload_doc();
          }
        });
    } else {
      frappe.msgprint("This Item is not out of stock");
    }
  },
});
