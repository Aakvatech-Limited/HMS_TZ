/**
 * Shared parts of the NHIF service dialogs (Unissued Services, Approved Services, Eligibility, Approval List, Issued Services).
 */
class NHIFServiceDialog {
  static add_buttons(frm) {
    NHIFEligibility.add_button(frm);
    NHIFApprovalList.add_button(frm);
    NHIFApprovedServices.add_button(frm);
    NHIFUnissuedServices.add_button(frm);
    NHIFIssuedServices.add_button(frm);
  }

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

  static is_nhif_restricted(frm) {
    return (
      NHIFServiceDialog.is_nhif(frm) &&
      NHIFServiceDialog.get_service_rows(frm).some(
        (row) => row.is_restricted == 1
      )
    );
  }

  static escape(value) {
    return frappe.utils.escape_html(String(value ?? ""));
  }

  static format_date(value, with_time = false) {
    if (!value) {
      return "";
    }
    const [date, time = ""] = value.split("T");
    return frappe.datetime.str_to_user(
      with_time ? `${date} ${time.split(".")[0]}` : date
    );
  }

  static show(title, html, extra_fields = []) {
    const dialog = new frappe.ui.Dialog({
      title: title,
      size: "extra-large",
      fields: [
        ...extra_fields,
        { fieldname: "services_html", fieldtype: "HTML" },
      ],
    });
    dialog.onhide = () => dialog.$wrapper.remove();
    dialog.fields_dict.services_html.$wrapper.html(html);
    dialog.show();
    return dialog;
  }
}

window.NHIFServiceDialog = NHIFServiceDialog;
