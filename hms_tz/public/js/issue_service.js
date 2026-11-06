/**
 * Ask for the qty to issue on an NHIF restricted Lab Test, Radiology Examination,
 * Clinical Procedure or Therapy Session. Resolves to the qty, or null when the dialog is closed.
 *
 * Usage: const qty = await prompt_nhif_issue_qty(frm, frm.doc.template);
 */
function prompt_nhif_issue_qty(frm, template) {
  return new Promise((resolve) => {
    const dialog = new frappe.ui.Dialog({
      title: __("Issue Service"),
      fields: [
        {
          fieldname: "template",
          fieldtype: "Data",
          label: __("Template"),
          default: template,
          read_only: 1,
        },
        {
          fieldtype: "Column Break",
        },
        {
          fieldname: "approval_number",
          fieldtype: "Data",
          label: __("Approval Number"),
          default: frm.doc.approval_number,
          read_only: 1,
        },
        {
          fieldtype: "Column Break",
        },
        {
          fieldname: "qty",
          fieldtype: "Int",
          label: __("Qty to be Issued"),
          default: 1,
          reqd: 1,
        },
      ],
      primary_action_label: __("Issue"),
      primary_action: ({ qty }) => {
        if (qty < 1) {
          frappe.msgprint(__("Qty to be Issued must be at least 1"));
          return;
        }
        resolve(qty);
        dialog.hide();
      },
    });
    // resolving after the primary action is a no-op
    dialog.onhide = () => resolve(null);
    dialog.show();
  });
}

window.prompt_nhif_issue_qty = prompt_nhif_issue_qty;
