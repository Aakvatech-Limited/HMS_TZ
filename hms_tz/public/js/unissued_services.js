/**
 * NHIF Unissued Services: list the approvals of the patient's card that still have unissued qty
 * and let the user put one on a restricted service of this form.
 *
 * Added to the NHIF menu by NHIFServiceDialog.add_buttons(frm).
 */
class NHIFUnissuedServices {
  static add_button(frm) {
    if (frm.is_new() || !NHIFServiceDialog.is_nhif_restricted(frm)) {
      return;
    }
    frm.add_custom_button(
      __("Get Unissued Services"),
      () => NHIFUnissuedServices.show(frm),
      __("NHIF")
    );
  }

  static show(frm) {
    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_unissued_services",
      args: { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
      freeze: true,
      freeze_message: __("Fetching unissued services from NHIF..."),
      callback: (r) => {
        if (r.message) {
          NHIFUnissuedServices.show_dialog(frm, r.message);
        }
      },
    });
  }

  static show_dialog(frm, lines) {
    const dialog = NHIFServiceDialog.show(
      __("NHIF Unissued Services"),
      NHIFUnissuedServices.get_table_html(lines)
    );
    dialog.$wrapper.on("click", ".use-approval", function () {
      const line = lines[$(this).data("line")];
      const target = line.targets[$(this).data("target")];
      NHIFUnissuedServices.use_approval(target, line);
      dialog.hide();
    });
  }

  static get_table_html(lines) {
    if (!lines.length) {
      return `<p class="text-muted">${__(
        "NHIF has no unissued services for this card."
      )}</p>`;
    }

    const escape = NHIFServiceDialog.escape;
    const rows = lines
      .map((line, line_index) => {
        const buttons = line.targets
          .map(
            (target, target_index) =>
              `<button class="btn btn-xs btn-primary use-approval" data-line="${line_index}" data-target="${target_index}"
                title="${escape(target.label)}">${
                line.targets.length > 1
                  ? __("Use for {0}", [escape(target.label)])
                  : __("Use this approval")
              }</button>`
          )
          .join(" ");
        return `<tr>
          <td>${escape(line.ItemCode)}</td>
          <td>${escape(line.service_name)}</td>
          <td class="text-right">${escape(line.QuantityRequested)}</td>
          <td class="text-right">${escape(line.QuantityIssued)}</td>
          <td class="text-right">${escape(line.QuantityRemains)}</td>
          <td><span class="indicator-pill green">${escape(
            line.ApprovalReferenceNo
          )}</span></td>
          <td>${escape(frappe.datetime.str_to_user(line.ApprovalDate))}</td>
          <td>${escape(line.Remarks)}</td>
          <td>${buttons}</td>
        </tr>`;
      })
      .join("");

    return `<table class="table table-bordered table-condensed">
      <thead><tr>
        <th>${__("Item Code")}</th><th>${__("Service Name")}</th>
        <th>${__("Requested")}</th><th>${__("Issued")}</th><th>${__(
      "Remains"
    )}</th>
        <th>${__("Approval No")}</th><th>${__("Approval Date")}</th>
        <th>${__("Remarks")}</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  static use_approval(target, line) {
    // Same values as get_approval_values on the server; the ids belong to the new request, not this approval
    const values = {
      approval_number: line.ApprovalReferenceNo,
      approval_status: line.ApprovalStatus,
      approval_date: line.ApprovalDate ? line.ApprovalDate.slice(0, 10) : null,
      service_authorization_id: null,
      authorized_item_id: null,
    };
    if (target.doctype === "Delivery Note Item") {
      values.approved_qty = line.QuantityRemains;
    }
    frappe.model.set_value(target.doctype, target.name, values);
    frappe.show_alert({
      message: __("Approval No {0} is set on {1}. Save to keep it.", [
        frappe.utils.escape_html(line.ApprovalReferenceNo),
        frappe.utils.escape_html(target.label),
      ]),
      indicator: "green",
    });
  }
}

window.NHIFUnissuedServices = NHIFUnissuedServices;
