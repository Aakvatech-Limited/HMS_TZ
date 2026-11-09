/**
 * Shared parts of the NHIF service dialogs (Unissued Services, Approved Services).
 */
class NHIFServiceDialog {
  static is_nhif(frm) {
    const payer =
      frm.doc.doctype === "Delivery Note"
        ? frm.doc.customer
        : frm.doc.insurance_company;
    return (payer || "").includes("NHIF");
  }

  static get_service_rows(frm) {
    return frm.doc.doctype === "Delivery Note"
      ? frm.doc.items || []
      : [frm.doc];
  }

  static escape(value) {
    return frappe.utils.escape_html(String(value ?? ""));
  }

  static show(title, html) {
    const dialog = new frappe.ui.Dialog({
      title: title,
      size: "extra-large",
      fields: [{ fieldname: "services_html", fieldtype: "HTML" }],
    });
    dialog.onhide = () => dialog.$wrapper.remove();
    dialog.fields_dict.services_html.$wrapper.html(html);
    dialog.show();
    return dialog;
  }
}

window.NHIFServiceDialog = NHIFServiceDialog;
