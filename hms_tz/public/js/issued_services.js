/**
 * NHIF Issued Services: the services the facility issued to NHIF patients between two dates, at most one month.
 *
 * Usage, in the form's refresh: NHIFIssuedServices.add_button(frm);
 */
class NHIFIssuedServices {
  static add_button(frm) {
    if (frm.is_new()) {
      return;
    }
    frm.add_custom_button(
      __("Get Issued Services by date"),
      () => NHIFIssuedServices.ask_dates(frm),
      __("NHIF")
    );
  }

  static ask_dates(frm) {
    const today = frappe.datetime.get_today();
    frappe.prompt(
      [
        {
          fieldname: "from_date",
          fieldtype: "Date",
          label: __("From Date"),
          default: today,
          reqd: 1,
        },
        {
          fieldname: "to_date",
          fieldtype: "Date",
          label: __("To Date"),
          default: today,
          reqd: 1,
        },
      ],
      (values) => NHIFIssuedServices.show(frm, values),
      __("Get Issued Services by date"),
      __("Get")
    );
  }

  static show(frm, values) {
    frappe.call({
      method: "hms_tz.nhif.nhif_api.approval.get_issued_services",
      args: {
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        from_date: values.from_date,
        to_date: values.to_date,
      },
      freeze: true,
      freeze_message: __("Fetching issued services from NHIF..."),
      callback: (r) => {
        if (r.message) {
          const dialog = NHIFServiceDialog.show(
            __("NHIF Issued Services {0} to {1} ({2})", [
              frappe.datetime.str_to_user(values.from_date),
              frappe.datetime.str_to_user(values.to_date),
              r.message.length,
            ]),
            NHIFIssuedServices.get_table_html(r.message)
          );
          dialog.$wrapper.find(".modal-dialog").css("max-width", "90vw");
        }
      },
    });
  }

  static get_table_html(services) {
    const escape = NHIFServiceDialog.escape;
    const rows = services
      .map(
        (line) => `<tr>
          <td class="text-nowrap">${NHIFServiceDialog.format_date(
            line.DateIssued,
            true
          )}</td>
          <td class="text-nowrap">${escape(line.CardNo)}</td>
          <td class="text-nowrap">${escape(line.FullName)}</td>
          <td>${escape(line.ItemName)}</td>
          <td class="text-right">${escape(line.Quantity)}</td>
          <td class="text-right">${format_currency(line.UnitPrice)}</td>
          <td class="text-right">${format_currency(line.AmountClaimed)}</td>
          <td class="text-nowrap">${escape(line.ServiceReferenceNo)}</td>
        </tr>`
      )
      .join("");

    return `<table class="table table-bordered table-condensed">
      <thead><tr>
        <th class="text-nowrap">${__("Date Issued")}</th>
        <th class="text-nowrap">${__("Card No")}</th>
        <th>${__("Full Name")}</th>
        <th>${__("Item Name")}</th>
        <th>${__("Qty")}</th>
        <th class="text-nowrap">${__("Unit Price")}</th>
        <th class="text-nowrap">${__("Amount Claimed")}</th>
        <th class="text-nowrap">${__("Service Reference No")}</th>
      </tr></thead>
      <tbody>${
        rows ||
        `<tr><td colspan="8" class="text-muted text-center">${__(
          "No issued services found"
        )}</td></tr>`
      }</tbody>
    </table>`;
  }
}

window.NHIFIssuedServices = NHIFIssuedServices;
