// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Healthcare Practitioner", {
  setup: function (frm) {
    frm.set_query("account", "accounts", function (doc, cdt, cdn) {
      let d = locals[cdt][cdn];
      return {
        filters: {
          root_type: "Income",
          company: d.company,
          is_group: 0,
        },
      };
    });
  },
  refresh: function (frm) {
    frappe.dynamic_link = {
      doc: frm.doc,
      fieldname: "name",
      doctype: "Healthcare Practitioner",
    };

    if (!frm.is_new()) {
      frappe.contacts.render_address_and_contact(frm);
    } else {
      frappe.contacts.clear_address_and_contact(frm);
    }

    frm.set_query("service_unit", "practitioner_schedules", function () {
      return {
        filters: {
          is_group: false,
          allow_appointments: true,
        },
      };
    });

    frm.set_query("supplier", function () {
      return {
        filters: {
          supplier_type: "Individual",
        },
      };
    });

    manage_internal_external_practitioner(frm);
    set_query_service_item(frm, "inpatient_visit_charge_item");
    set_query_service_item(frm, "op_consulting_charge_item");

    if (!frm.is_new() && frm.doc.hms_tz_company) {
      frm.add_custom_button(
        __("View Practitioners"),
        () => view_nhif_practitioners(frm),
        __("NHIF")
      );
    }

    if (!frm.is_new() && frm.doc.hms_tz_company) {
      frm.add_custom_button(
        __("Practitioner Details"),
        () => view_nhif_practitioner_details(frm),
        __("NHIF")
      );
      frm.add_custom_button(
        __("Register Practitioner"),
        () => register_nhif_practitioner(frm),
        __("NHIF")
      );
    }
  },
  healthcare_practitioner_type: function (frm) {
    manage_internal_external_practitioner(frm);
  },
});

let set_query_service_item = function (frm, service_item_field) {
  frm.set_query(service_item_field, function () {
    return {
      filters: {
        is_sales_item: 1,
        is_stock_item: 0,
      },
    };
  });
};

frappe.ui.form.on("Healthcare Practitioner", "user_id", function (frm) {
  if (frm.doc.user_id) {
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "User",
        name: frm.doc.user_id,
      },
      callback: function (data) {
        frappe.model.get_value(
          "Employee",
          { user_id: frm.doc.user_id },
          "name",
          function (data) {
            if (data) {
              if (!frm.doc.employee || frm.doc.employee != data.name)
                frappe.model.set_value(
                  frm.doctype,
                  frm.docname,
                  "employee",
                  data.name
                );
            } else {
              frappe.model.set_value(frm.doctype, frm.docname, "employee", "");
            }
          }
        );

        if (
          !frm.doc.first_name ||
          frm.doc.first_name != data.message.first_name
        )
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "first_name",
            data.message.first_name
          );
        if (
          !frm.doc.middle_name ||
          frm.doc.middle_name != data.message.middle_name
        )
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "middle_name",
            data.message.middle_name
          );
        if (!frm.doc.last_name || frm.doc.last_name != data.message.last_name)
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "last_name",
            data.message.last_name
          );
        if (
          !frm.doc.mobile_phone ||
          frm.doc.mobile_phone != data.message.mobile_no
        )
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "mobile_phone",
            data.message.mobile_no
          );
      },
    });
  }
});

frappe.ui.form.on("Healthcare Practitioner", "employee", function (frm) {
  if (frm.doc.employee) {
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Employee",
        name: frm.doc.employee,
      },
      callback: function (data) {
        if (!frm.doc.user_id || frm.doc.user_id != data.message.user_id)
          frm.set_value("user_id", data.message.user_id);
        if (
          !frm.doc.designation ||
          frm.doc.designation != data.message.designation
        )
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "designation",
            data.message.designation
          );
        if (!frm.doc.first_name || !frm.doc.user_id) {
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "first_name",
            data.message.first_name
          );
          frappe.model.set_value(frm.doctype, frm.docname, "middle_name", "");
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "last_name",
            data.message.last_name
          );
        }
        if (!frm.doc.mobile_phone || !frm.doc.user_id)
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "mobile_phone",
            data.message.cell_number
          );
        if (
          !frm.doc.address ||
          frm.doc.address != data.message.current_address
        )
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "address",
            data.message.current_address
          );
      },
    });
  }
});

frappe.ui.form.on("Healthcare Practitioner", "supplier", function (frm) {
  if (frm.doc.supplier) {
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Supplier",
        name: frm.doc.supplier,
      },
      callback: function (data) {
        if (!frm.doc.first_name)
          frappe.model.set_value(
            frm.doctype,
            frm.docname,
            "first_name",
            data.message.supplier_name
          );
      },
    });
  }
});

let view_nhif_practitioners = function (frm) {
  frappe.call({
    method:
      "hms_tz.nhif.nhif_api.healthcare_practitioner.get_registered_practitioners",
    type: "GET",
    args: { company: frm.doc.hms_tz_company },
    freeze: true,
    freeze_message: __("Fetching practitioners from NHIF..."),
    callback: function (r) {
      show_nhif_practitioners(frm, r.message || []);
    },
  });
};

let show_nhif_practitioners = function (frm, practitioners) {
  practitioners = practitioners.map((p) => ({
    ...p,
    full_name: [p.firstName, p.middleName, p.lastName]
      .filter(Boolean)
      .join(" "),
  }));

  let dialog = new frappe.ui.Dialog({
    title: __("NHIF Registered Practitioners ({0})", [practitioners.length]),
    size: "large",
    fields: [
      { fieldtype: "Column Break" },
      { fieldtype: "Column Break" },
      {
        fieldname: "search",
        fieldtype: "Data",
        label: __("Search by Registration No or Name"),
        onchange: () => render_rows(dialog.get_value("search")),
      },
      { fieldtype: "Column Break" },
      { fieldtype: "Section Break" },
      { fieldname: "practitioners_html", fieldtype: "HTML" },
    ],
  });

  let render_rows = function (search_text) {
    let search = (search_text || "").toLowerCase();
    let rows = practitioners
      .filter((p) =>
        `${p.registrationNo} ${p.full_name}`.toLowerCase().includes(search)
      )
      .map((p) => nhif_practitioner_row(p, frm.doc.tz_mct_code))
      .join("");

    dialog.fields_dict.practitioners_html.$wrapper.html(`
      <table class="table table-bordered table-hover">
        <thead>
          <tr>
            <th>${__("Registration No")}</th>
            <th>${__("Name")}</th>
            <th>${__("Qualification")}</th>
            <th>${__("Practicing Status")}</th>
          </tr>
        </thead>
        <tbody>
          ${
            rows ||
            `<tr><td colspan="4" class="text-muted text-center">${__(
              "No practitioners found"
            )}</td></tr>`
          }
        </tbody>
      </table>`);
  };

  render_rows();
  dialog.show();
};

let nhif_practitioner_row = function (practitioner, current_registration_no) {
  let escape = frappe.utils.escape_html;
  let status = practitioner.practicingStatus;
  let color = !status
    ? "gray"
    : status.toLowerCase() === "allowed"
    ? "green"
    : "red";
  let is_current = practitioner.registrationNo === current_registration_no;
  let row_class =
    color === "red" ? "text-danger" : is_current ? "table-info" : "";

  return `
    <tr class="${row_class} ${is_current ? "font-weight-bold" : ""}">
      <td>${escape(practitioner.registrationNo || "")}</td>
      <td>${escape(practitioner.full_name)}</td>
      <td>${escape(practitioner.qualification || "")}</td>
      <td><span class="indicator-pill ${color}">${escape(
    status || __("Not Set")
  )}</span></td>
    </tr>`;
};

let view_nhif_practitioner_details = function (frm) {
  if (!frm.doc.tz_mct_code) {
    frappe.msgprint("MCT Code is required..!");
    return;
  }

  frappe.call({
    method:
      "hms_tz.nhif.nhif_api.healthcare_practitioner.get_practitioner_details",
    type: "GET",
    args: {
      company: frm.doc.hms_tz_company,
      practitioner_no: frm.doc.tz_mct_code,
    },
    freeze: true,
    freeze_message: __("Fetching practitioner details from NHIF..."),
    callback: function (r) {
      show_nhif_practitioner_details(frm, r.message || {});
    },
  });
};

let show_nhif_practitioner_details = function (frm, details) {
  let escape = frappe.utils.escape_html;
  let rows = Object.entries(details)
    .filter(([, value]) => value !== null && typeof value !== "object")
    .map(
      ([key, value]) => `
        <tr class="${practicing_status_class(key, value)}">
          <th>${escape(frappe.unscrub(key.replace(/([A-Z])/g, "_$1")))}</th>
          <td>${escape(String(value))}</td>
        </tr>`
    )
    .join("");

  let dialog = new frappe.ui.Dialog({
    title: __("NHIF Practitioner Details: {0}", [frm.doc.tz_mct_code]),
    fields: [{ fieldname: "details_html", fieldtype: "HTML" }],
  });
  dialog.fields_dict.details_html.$wrapper.html(`
    <table class="table table-bordered">
      <tbody>
        ${
          rows ||
          `<tr><td class="text-muted text-center">${__(
            "No details returned"
          )}</td></tr>`
        }
      </tbody>
    </table>`);
  dialog.show();
};

let register_nhif_practitioner = function (frm) {
  if (!frm.doc.tz_mct_code) {
    frappe.msgprint(__("MCT Code is required..!"));
    return;
  }
  if (frm.is_dirty()) {
    frappe.msgprint(
      __("Please save the practitioner before you register it with NHIF")
    );
    return;
  }

  frappe.confirm(
    __("Register MCT Code {0} to NHIF at this facility?", [
      frappe.utils.escape_html(frm.doc.tz_mct_code).bold(),
    ]),
    () =>
      frappe.call({
        method:
          "hms_tz.nhif.nhif_api.healthcare_practitioner.register_practitioner",
        args: { practitioner: frm.doc.name },
        freeze: true,
        freeze_message: __("Registering practitioner with NHIF..."),
        callback: function (r) {
          show_nhif_registration_result(frm, r.message || {});
        },
      })
  );
};

let show_nhif_registration_result = function (frm, result) {
  let escape = frappe.utils.escape_html;
  frappe.msgprint({
    title: __("NHIF Registration Completed"),
    indicator: "green",
    message: `
      <p>${escape(
        result.message ||
          __("The practitioner is registered with NHIF at this facility.")
      )}</p>
      <table class="table table-bordered">
        <tbody>
          <tr>
            <th>${__("Practitioner No")}</th>
            <td>${escape(result.practitionerNo || frm.doc.tz_mct_code)}</td>
          </tr>
          <tr>
            <th>${__("Facility Code")}</th>
            <td>${escape(result.facilityCode || "")}</td>
          </tr>
        </tbody>
      </table>`,
  });
};

let practicing_status_class = function (key, value) {
  if (key !== "practicingStatus") return "";
  return String(value).toLowerCase() === "allowed"
    ? "text-success"
    : "text-danger";
};

var manage_internal_external_practitioner = function (frm) {
  frm.set_df_property("employee", "hidden", 1);
  frm.set_df_property("supplier", "reqd", 0);
  frm.set_df_property("supplier", "hidden", 1);
  if (frm.doc.healthcare_practitioner_type) {
    if (frm.doc.healthcare_practitioner_type == "Internal") {
      frm.set_df_property("employee", "hidden", 0);
    } else if (frm.doc.healthcare_practitioner_type == "External") {
      frm.set_df_property("supplier", "hidden", 0);
      frm.set_df_property("supplier", "reqd", 1);
    }
  }
};

frappe.tour["Healthcare Practitioner"] = [
  {
    fieldname: "employee",
    title: __("Employee"),
    description: __(
      "If you want to track Payroll and other HRMS operations for a Practitoner, create an Employee and link it here."
    ),
  },
  {
    fieldname: "practitioner_schedules",
    title: __("Practitioner Schedules"),
    description: __(
      "Set the Practitioner Schedule you just created. This will be used while booking appointments."
    ),
  },
  {
    fieldname: "op_consulting_charge_item",
    title: __("Out Patient Consulting Charge Item"),
    description: __("Create a service item for Out Patient Consulting."),
  },
  {
    fieldname: "inpatient_visit_charge_item",
    title: __("Inpatient Visit Charge Item"),
    description: __(
      "If this Healthcare Practitioner works for the In-Patient Department, create a service item for Inpatient Visits."
    ),
  },
  {
    fieldname: "op_consulting_charge",
    title: __("Out Patient Consulting Charge"),
    description: __(
      "Set the Out Patient Consulting Charge for this Practitioner."
    ),
  },
  {
    fieldname: "inpatient_visit_charge",
    title: __("Inpatient Visit Charge"),
    description: __(
      "If this Healthcare Practitioner also works for the In-Patient Department, set the inpatient visit charge for this Practitioner."
    ),
  },
];
