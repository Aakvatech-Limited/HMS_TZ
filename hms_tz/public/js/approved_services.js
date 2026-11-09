/**
 * NHIF Approved Services: show what NHIF approved under each approval number of this form.
 * A Delivery Note can carry several numbers, one per item, and all of them are fetched before the dialog opens.
 *
 * Usage, in the form's refresh: NHIFApprovedServices.add_button(frm);
 */
class NHIFApprovedServices {
  static add_button(frm) {
    if (frm.is_new() || !NHIFApprovedServices.has_approval_number(frm)) {
      return;
    }
    frm.add_custom_button(
      __("Get Approved Services"),
      () => NHIFApprovedServices.show(frm),
      __("NHIF")
    );
  }

  static has_approval_number(frm) {
    return (
      NHIFServiceDialog.is_nhif(frm) &&
      NHIFServiceDialog.get_service_rows(frm).some(
        (row) => row.approval_number
      )
    );
  }

  static show(frm) {
    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_approved_services",
      args: { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
      freeze: true,
      freeze_message: __("Fetching approved services from NHIF..."),
      callback: (r) => {
        if (r.message) {
          NHIFServiceDialog.show(
            __("NHIF Approved Services"),
            NHIFApprovedServices.get_table_html(r.message)
          );
        }
      },
    });
  }

  static get_table_html(approvals) {
    const escape = NHIFServiceDialog.escape;
    const rows = approvals
      .map((approval) => {
        const number = `<span class="indicator-pill green">${escape(
          approval.approval_number
        )}</span>`;
        if (!approval.services.length) {
          return `<tr>
            <td colspan="3" class="text-muted">${__(
              "NHIF returned no services for this approval number."
            )}</td>
            <td>${number}</td>
            <td colspan="4"></td>
          </tr>`;
        }
        return approval.services
          .map(
            (line) => `<tr>
              <td class="text-nowrap">${escape(
                line.CardNo || line.NationalID
              )}</td>
              <td>${escape(line.ItemCode)}</td>
              <td>${escape(line.ItemName)}</td>
              <td>${number}</td>
              <td class="text-right text-nowrap">${format_currency(
                line.UnitPrice
              )}</td>
              <td class="text-right">${escape(line.Quantity)}</td>
              <td class="text-right">${escape(line.RemainQuantity)}</td>
              <td>${line.RequiresBiometric ? __("Yes") : __("No")}</td>
            </tr>`
          )
          .join("");
      })
      .join("");

    return `<table class="table table-bordered table-condensed">
      <thead><tr>
        <th class="text-nowrap">${__("Card No")}</th>
        <th>${__("Item Code")}</th>
        <th style="width: 30%">${__("Item Name")}</th>
        <th>${__("Approval No")}</th>
        <th class="text-nowrap">${__("Unit Price")}</th>
        <th>${__("Quantity")}</th>
        <th class="text-nowrap">${__("Qty Remain")}</th>
        <th>${__("Biometric")}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }
}

window.NHIFApprovedServices = NHIFApprovedServices;
