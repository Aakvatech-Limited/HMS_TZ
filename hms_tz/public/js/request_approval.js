/**
 * RequestApproval Class
 * A reusable class to show a dialog for requesting NHIF service approval
 *
 * Usage:
 * new RequestApproval({
 *   frm: frm,
 *   ref_doctype: "Lab Test",
 *   ref_docname: "LAB-00001",
 *   service_type: "Lab Test Template",
 *   service_name: "Blood Test",
 *   encounter_no: "HLC-ENC-00001",
 *   // Optional parameters
 *   item_code: "ITEM-001",
 *   reference_name: "REF-001",
 *   reference_doctype: "Patient Encounter",
 *   supportive_document: "attachment.pdf",
 *   qty: 1,
 *   is_qty_read_only: false
 * });
 */

class RequestApproval {
  constructor(options) {
    // Validate mandatory parameters
    if (!options.frm) {
      frappe.msgprint(__("Form reference (frm) is required"));
      return;
    }
    if (!options.ref_doctype) {
      frappe.msgprint(__("Reference DocType (ref_doctype) is required"));
      return;
    }
    if (!options.ref_docname) {
      frappe.msgprint(__("Reference DocName (ref_docname) is required"));
      return;
    }
    if (!options.service_type) {
      frappe.msgprint(__("Service Type (service_type) is required"));
      return;
    }
    if (!options.service_name && options.service_name !== "") {
      frappe.msgprint(__("Service Name (service_name) is required"));
      return;
    }
    if (!options.encounter_no) {
      frappe.msgprint(__("Encounter Number (encounter_no) is required"));
      return;
    }

    // Store mandatory parameters
    this.frm = options.frm;
    this.ref_doctype = options.ref_doctype;
    this.ref_docname = options.ref_docname;
    this.service_type = options.service_type;
    this.service_name = options.service_name;
    this.encounter_no = options.encounter_no;

    // Store optional parameters
    this.item_code = options.item_code || "";
    this.reference_name = options.reference_name || "";
    this.reference_doctype = options.reference_doctype || "";
    this.supportive_document = options.supportive_document || "";
    this.qty = options.qty || 0;
    this.is_qty_read_only = options.is_qty_read_only || false;

    // Initialize the dialog
    this.init();
  }

  async init() {
    try {
      // Fetch clinical notes from Patient Encounter
      const clinical_notes = await this.fetchClinicalNotes();

      // Show the dialog
      this.showDialog(clinical_notes);
    } catch (error) {
      console.error("Error initializing RequestApproval:", error);
      frappe.msgprint({
        title: __("Error"),
        indicator: "red",
        message:
          __("Failed to initialize approval request dialog: ") + error.message,
      });
    }
  }

  async fetchClinicalNotes() {
    return new Promise((resolve, reject) => {
      frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: "Patient Encounter",
          filters: { name: this.encounter_no },
          fieldname: "examination_detail",
        },
        async: true,
        callback: function (r) {
          if (r.message && r.message.examination_detail) {
            resolve(r.message.examination_detail);
          } else {
            resolve("");
          }
        },
        error: function (err) {
          console.error("Error fetching clinical notes:", err);
          resolve(""); // Resolve with empty string on error
        },
      });
    });
  }

  showDialog(clinical_notes) {
    const me = this;

    // Get today's date for default start_date
    const start_date =
      me.frm.start_date ||
      me.frm.result_date ||
      me.frm.posting_date ||
      frappe.datetime.get_today();

    // Calculate default expire_date (30 days from today)
    // const expire_date = frappe.datetime.add_days(start_date, 30);

    const dialog = new frappe.ui.Dialog({
      title: __("Request Kibali (Approval)"),
      size: "large",
      fields: [
        {
          fieldname: "start_date",
          fieldtype: "Date",
          label: __("Start Date"),
          default: start_date,
          reqd: 1,
        },
        {
          fieldname: "col_break_1",
          fieldtype: "Column Break",
        },
        {
          fieldname: "expire_date",
          fieldtype: "Date",
          label: __("Expire Date"),
          // default: expire_date,
          reqd: 1,
        },
        {
          fieldname: "col_break_2",
          fieldtype: "Column Break",
        },
        {
          fieldname: "quantity",
          fieldtype: "Float",
          label: __("Quantity"),
          default: me.qty,
          reqd: 1,
          read_only: me.is_qty_read_only ? 1 : 0,
        },
        {
          fieldname: "sec_col_1",
          fieldtype: "Section Break",
        },
        {
          fieldname: "clinical_notes",
          fieldtype: "Text Editor",
          label: __("Clinical Notes"),
          bold: true,
          default: clinical_notes || "",
        },
      ],
      primary_action_label: __("Request Kibali"),
      primary_action: function (values) {
        me.submitApprovalRequest(values, dialog);
      },
      secondary_action_label: __("Cancel"),
      secondary_action: function () {
        dialog.hide();
      },
    });

    // Add validation for dates
    dialog.fields_dict.expire_date.$input.on("change", function () {
      const start_date = dialog.get_value("start_date");
      const expire_date = dialog.get_value("expire_date");

      if (start_date && expire_date && expire_date < start_date) {
        frappe.msgprint(__("Expire Date cannot be before Start Date"));
      }
    });

    dialog.fields_dict.start_date.$input.on("change", function () {
      const start_date = dialog.get_value("start_date");
      const expire_date = dialog.get_value("expire_date");

      if (start_date && expire_date && expire_date < start_date) {
        frappe.msgprint(__("Expire Date cannot be before Start Date"));
      }
    });

    dialog.show();
  }

  submitApprovalRequest(values, dialog) {
    const me = this;

    // Validate required fields
    if (!values.start_date) {
      frappe.msgprint(__("Start Date is required"));
      return;
    }

    if (!values.expire_date) {
      frappe.msgprint(__("Expire Date is required"));
      return;
    }

    if (!values.quantity || values.quantity <= 0) {
      frappe.msgprint(__("Quantity must be greater than 0"));
      return;
    }

    if (values.expire_date < values.start_date) {
      frappe.msgprint(__("Expire Date cannot be before Start Date"));
      return;
    }

    if (!values.clinical_notes || values.clinical_notes.trim() === "") {
      frappe.msgprint(__("Clinical Notes cannot be empty"));
      return;
    }

    // Build API arguments
    const args = {
      ref_doctype: me.ref_doctype,
      ref_docname: me.ref_docname,
      service_type: me.service_type,
      service_name: me.service_name,
      start_date: values.start_date,
      expire_date: values.expire_date,
      clinical_notes: values.clinical_notes || "",
      qty: values.quantity,
    };

    // Add optional parameters if provided
    if (me.item_code) {
      args.item_code = me.item_code;
    }
    if (me.reference_name) {
      args.reference_name = me.reference_name;
    }
    if (me.reference_doctype) {
      args.reference_doctype = me.reference_doctype;
    }
    if (me.supportive_document) {
      args.supportive_document = me.supportive_document;
    }

    // Make the API call
    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_service_approval",
      args: args,
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (r) {
        if (r.message) {
          me.frm.refresh();

          if (r.message.status == "success") {
            // Hide the dialog first
            dialog.hide();

            // Show success alert
            frappe.show_alert(
              {
                message: __(
                  "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>" +
                    "Approval Request Successful. Reference Number: " +
                    r.message.reference_no +
                    "</h4>"
                ),
                indicator: "green",
              },
              15
            );

            if (me.frm.is_dirty()) {
              me.frm.save();
            }
            frappe.utils.play_sound("submit");
            me.frm.reload_doc();
          } else {
            // Show error alert with message from API if available
            const error_message =
              r.message.message || "Approval Request Failed";

            frappe.show_alert(
              {
                message: __(
                  "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>" +
                    "Approval Request Failed: " +
                    error_message +
                    "</h4>"
                ),
                indicator: "red",
              },
              20
            );

            frappe.utils.play_sound("error");
          }
        } else {
          frappe.utils.play_sound("error");
          frappe.msgprint({
            title: __("Error"),
            indicator: "red",
            message: __(
              "No response received from the server. Please try again."
            ),
          });
        }
      },
      error: function (err) {
        console.error("API Error:", err);
        frappe.utils.play_sound("error");
        frappe.msgprint({
          title: __("Error"),
          indicator: "red",
          message: __(
            "An error occurred while processing the request. Please try again."
          ),
        });
      },
    });
  }

  /** Show or clear the orange banner asking for the NHIF approval number. */
  static show_restricted_banner(frm) {
    frm.layout.message
      .find(".nhif-approval-banner")
      .closest(".form-message")
      .remove();

    const needs_approval =
      frm.doc.doctype === "Delivery Note"
        ? (frm.doc.items || []).some(
            (row) => row.is_restricted == 1 && !row.approval_number
          )
        : frm.doc.is_restricted == 1 && !frm.doc.approval_number;

    if (!needs_approval) {
      if (!frm.layout.message.children().length) {
        frm.layout.show_message();
      }
      return;
    }
    frm.layout.show_message(
      `<div class="nhif-approval-banner" style="text-align: left; font-size: var(--text-base); font-weight: var(--weight-semibold);">
        <span style="display: inline-block; vertical-align: middle; margin-right: var(--margin-xs);">${frappe.utils.icon(
          "es-solid-alert-triangle",
          "sm"
        )}</span><span style="vertical-align: middle;">${__(
        "Get Approval Number from NHIF before doing anything, click the button of 'Get Approval Status'"
      )}</span>
      </div>`,
      "orange",
      true
    );
  }
}

// Export the class for use in other files
window.RequestApproval = RequestApproval;
