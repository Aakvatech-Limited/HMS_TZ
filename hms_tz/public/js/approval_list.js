/**
 * NHIF Approval List: every approval request NHIF holds for the patient's card, from any facility, with a search box.
 *
 * Usage, in the form's refresh: NHIFApprovalList.add_button(frm);
 * Patient Encounter adds its own page button and calls NHIFApprovalList.show(frm).
 */
class NHIFApprovalList {
  static SEARCH_KEYS = [
    "AuthorizationNo",
    "ApprovalReferenceNo",
    "ItemName",
    "ApprovalStatus",
    "ServiceIssuingFacilityName",
    "PrescribedBy",
  ];

  static add_button(frm) {
    if (frm.is_new() || !NHIFServiceDialog.is_nhif(frm)) {
      return;
    }
    frm.add_custom_button(
      __("Get Approval List"),
      () => NHIFApprovalList.show(frm),
      __("NHIF")
    );
  }

  static show(frm) {
    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_approval_list",
      args: { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
      freeze: true,
      freeze_message: __("Fetching approval list from NHIF..."),
      callback: (r) => {
        if (r.message) {
          NHIFApprovalList.show_dialog(r.message);
        }
      },
    });
  }

  static show_dialog(approvals) {
    approvals.sort((a, b) =>
      (b.AttendanceDate || "").localeCompare(a.AttendanceDate || "")
    );
    const search_texts = approvals.map((line) =>
      NHIFApprovalList.SEARCH_KEYS.map((key) => line[key] ?? "")
        .join(" ")
        .toLowerCase()
    );
    const render = () => {
      const search = (dialog.get_value("search") || "").toLowerCase();
      const matches = search
        ? approvals.filter((line, idx) => search_texts[idx].includes(search))
        : approvals;
      dialog.fields_dict.services_html.$wrapper.html(
        NHIFApprovalList.get_table_html(matches)
      );
    };
    const dialog = NHIFServiceDialog.show(
      __("NHIF Approval List ({0})", [approvals.length]),
      NHIFApprovalList.get_table_html(approvals),
      [
        {
          fieldtype: "Column Break",
        },
        {
          fieldtype: "Column Break",
        },
        {
          fieldname: "search",
          fieldtype: "Data",
          label: __(
            "Search by Authorization No, Approval No, Item Name, Status, Facility or Prescriber"
          ),
          onchange: render,
        },
        {
          fieldtype: "Column Break",
        },
        {
          fieldtype: "Section Break",
        },
      ]
    );
    dialog.$wrapper.find(".modal-dialog").css("max-width", "90vw");
  }

  static get_status_color(status) {
    status = (status || "").toLowerCase();
    if (status.startsWith("waiting")) {
      return "orange";
    }
    return { approved: "green", rejected: "red" }[status] || "gray";
  }

  static get_date(value) {
    return value ? frappe.datetime.str_to_user(value.split("T")[0]) : "";
  }

  static get_table_html(approvals) {
    const escape = NHIFServiceDialog.escape;
    const rows = approvals
      .map(
        (line) => `<tr>
          <td class="text-nowrap">${NHIFApprovalList.get_date(
            line.AttendanceDate
          )}</td>
          <td class="text-nowrap">${escape(line.AuthorizationNo)}</td>
          <td>${escape(line.ItemName)}</td>
          <td>${escape(line.ServiceIssuingFacilityName)}</td>
          <td>${escape(line.PrescribedBy)}</td>
          <td class="text-right">${escape(line.QuantityRequested)}</td>
          <td class="text-right">${escape(line.QuantityApproved)}</td>
          <td class="text-nowrap"><span class="indicator-pill ${NHIFApprovalList.get_status_color(
            line.ApprovalStatus
          )}">${escape(line.ApprovalStatus)}</span></td>
          <td class="text-nowrap">${escape(line.ApprovalReferenceNo)}</td>
          <td class="text-nowrap">${NHIFApprovalList.get_date(
            line.ApprovalDate
          )}</td>
        </tr>`
      )
      .join("");

    return `<table class="table table-bordered table-condensed">
      <thead><tr>
        <th class="text-nowrap">${__("Attendance Date")}</th>
        <th class="text-nowrap">${__("Authorization No")}</th>
        <th style="width: 20%">${__("Item Name")}</th>
        <th>${__("Issuing Facility")}</th>
        <th>${__("Prescribed By")}</th>
        <th>${__("Qty Requested")}</th>
        <th>${__("Qty Approved")}</th>
        <th>${__("Status")}</th>
        <th class="text-nowrap">${__("Approval No")}</th>
        <th class="text-nowrap">${__("Approval Date")}</th>
      </tr></thead>
      <tbody>${
        rows ||
        `<tr><td colspan="10" class="text-muted text-center">${__(
          "No approvals found"
        )}</td></tr>`
      }</tbody>
    </table>`;
  }
}

window.NHIFApprovalList = NHIFApprovalList;
