/**
 * NHIF Check Eligibility: ask NHIF whether the patient's card may get an approval for each restricted service of this form.
 * A Delivery Note can carry several restricted items, and all of them are checked before the dialog opens.
 *
 * Added to the NHIF menu by NHIFServiceDialog.add_buttons(frm).
 */
class NHIFEligibility {
  static add_button(frm) {
    if (frm.is_new() || !NHIFServiceDialog.is_nhif_restricted(frm)) {
      return;
    }
    frm.add_custom_button(
      __("Check Eligibility"),
      () => NHIFEligibility.show(frm),
      __("NHIF")
    );
  }

  static show(frm) {
    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.check_eligibility",
      args: { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
      freeze: true,
      freeze_message: __("Checking eligibility with NHIF..."),
      callback: (r) => {
        if (r.message) {
          NHIFServiceDialog.show(
            __("NHIF Eligibility"),
            NHIFEligibility.get_table_html(r.message)
          );
        }
      },
    });
  }

  static get_table_html(services) {
    const escape = NHIFServiceDialog.escape;
    const rows = services
      .map((line) => {
        const [color, status] = line.CanAccess
          ? ["green", __("Eligible")]
          : ["red", __("Not Eligible")];
        return `<tr>
          <td>${escape(line.service)}</td>
          <td class="text-nowrap">${escape(line.item_code)}</td>
          <td class="text-nowrap"><span class="indicator-pill ${color}">${status}</span></td>
          <td>${escape(line.Remarks)}</td>
        </tr>`;
      })
      .join("");

    return `<table class="table table-bordered table-condensed">
      <thead><tr>
        <th style="width: 30%">${__("Service")}</th>
        <th class="text-nowrap">${__("Item Code")}</th>
        <th class="text-nowrap">${__("Eligibility")}</th>
        <th style="width: 40%">${__("Remarks")}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }
}

window.NHIFEligibility = NHIFEligibility;
