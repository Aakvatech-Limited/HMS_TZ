// Copyright (c) 2025, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Healthcare Service Request", {
  setup: (frm) => {
    set_filters(frm);
    frm.trigger("get_services");
    control_add_remove_btns(frm);
  },
  refresh: (frm) => {
    set_filters(frm);
    frm.trigger("get_services");
    control_add_remove_btns(frm);
    set_preauth_headline(frm);
    frm.trigger("send_approval_request");
    frm.trigger("get_approval_status");
  },
  send_approval_request: (frm) => {
    if (
      frm.is_new() ||
      frm.doc.docstatus !== 0 ||
      !frm.doc.requires_approval ||
      frm.doc.submission_id
    ) {
      return;
    }

    frm.add_custom_button(
      __("Request Pre-Authorization"),
      () => {
        call_approval_check(
          frm,
          "send_approval_request",
          __("Sending Pre-Auth Request...")
        );
      },
      __("Jubilee")
    );
  },
  get_approval_status: (frm) => {
    if (frm.is_new() || !frm.doc.submission_id) {
      return;
    }

    frm.add_custom_button(
      __("Get Pre-Auth Status"),
      () => {
        call_approval_check(
          frm,
          "get_approval_status",
          __("Checking Pre-Auth Status...")
        );
      },
      __("Jubilee")
    );
  },
  onload: (frm) => {
    set_filters(frm);
    frm.trigger("get_services");
    control_add_remove_btns(frm);

    frm.get_service_rate = (row) => {
      frm.call("get_service_rate", { row_obj: row }).then((r) => {
        if (r.message) {
          row.rate = r.message.item_rate;
          if (r.message.discount_percent > 0) {
            row.discount_applied = 1;
          }
          let amount =
            (row.percent_covered / 100) * r.message.item_rate * row.qty;
          row.amount = amount;
          frm.refresh_field("payments");
        }
      });
    };

    frm.get_plan_name = (row) => {
      let insurance_subscription = row.insurance_subscription;
      frm.call("get_coverage_plan", { insurance_subscription }).then((r) => {
        if (r.message) {
          row.payor_plan = r.message;
          frm.refresh_field("payments");
        }
      });
    };

    frm.get_percent_covered = (row) => {
      frm.call("get_percent_covered", { item_obj: row }).then((r) => {
        if (r.message) {
          row.percent_covered = r.message;
          frm.refresh_field("payments");
        }
      });
    };
  },
  get_services: (frm) => {
    frm.call("get_services", {}).then((r) => {
      if (r.message && r.message.length > 0) {
        const grid = frm.fields_dict.payments.grid;

        grid.visible_columns = undefined;
        grid.setup_visible_columns();

        grid.fields_map.service_name.options = r.message;
        grid.refresh();

        frm.fields_dict.payments.grid.grid_rows.forEach((row) => {
          row.docfields.forEach((docfield) => {
            if (docfield.fieldname === "service_name") {
              docfield.options = r.message;
            }
          });
        });

        frm.refresh_field("payments");
        grid.refresh();
        grid.setup_visible_columns();

        // frm.fields_dict.payments.grid.fields_map.service_name.options = r.message;
        // frm.refresh_field("payments");
      }
    });
  },
  payment_type: (frm) => {
    if (frm.doc.payment_type == "Cash") {
      frm.set_value("insurance_company", "");
      frm.set_value("insurance_coverage_plan", "");
      frm.set_value("insurance_subscription", "");
      frm.set_value("card_no", "");
      frm.set_value("national_id", "");
    }
  },
});

frappe.ui.form.on("Healthcare Service Request Item", {
  form_render: (frm, cdt, cdn) => {
    control_add_remove_btns(frm, true);
  },
});

frappe.ui.form.on("Healthcare Service Request Payment", {
  service_name: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];

    if (row.service_name) {
      frm.get_percent_covered(row);

      if (row.price_list) {
        frm.get_service_rate(row);
      }
    }
  },
  price_list: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.price_list && row.service_name) {
      frm.get_service_rate(row);
    }
  },
  payment_type: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.payment_type == "Cash") {
      frappe.model.set_value(cdt, cdn, "insurance_subscription", "");
      frappe.model.set_value(cdt, cdn, "insurance_company", "");
      frappe.model.set_value(cdt, cdn, "card_no", "");
      frappe.model.set_value(cdt, cdn, "national_id", "");
      frappe.model.set_value(cdt, cdn, "authorization_number", "");

      frappe.model.set_value(cdt, cdn, "payor_plan", "Cash");
      frappe.model.set_value(
        cdt,
        cdn,
        "percent_covered",
        get_uncovered_percent(frm, row)
      );
      frappe.model.set_value(cdt, cdn, "price_list", "");
    }
  },
  percent_covered: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.percent_covered > 100) {
      frappe.msgprint(__("Percent Covered cannot be more than 100"));
      frappe.model.set_value(cdt, cdn, "percent_covered", 0);
      frm.refresh_field("payments");
      return;
    } else if (row.percent_covered < 0) {
      frappe.msgprint(__("Percent Covered cannot be less than 0"));
      frappe.model.set_value(cdt, cdn, "percent_covered", 0);
      frm.refresh_field("payments");
      return;
    } else {
      let amount = (row.percent_covered / 100) * row.rate * row.qty;
      frappe.model.set_value(cdt, cdn, "amount", amount);
      frm.refresh_field("payments");
    }
  },
  qty: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    let amount = (row.percent_covered / 100) * row.rate * row.qty;
    frappe.model.set_value(cdt, cdn, "amount", amount);
    frm.refresh_field("payments");
  },
  insurance_subscription: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.insurance_subscription) {
      frm.get_plan_name(row);
    } else {
      frappe.model.set_value(cdt, cdn, "payor_plan", "Cash");
      frm.refresh_field("payments");
    }
  },
});

// Percent left to cover for a service, so a cash row fills the gap the
// insurer did not approve. Server side validate_service_percentage is the
// authority; this only pre-fills a sensible value.
var get_uncovered_percent = (frm, row) => {
  let covered = frm.doc.payments
    .filter(
      (d) =>
        d.name !== row.name &&
        d.service_name === row.service_name &&
        d.ref_docname === row.ref_docname
    )
    .reduce((total, d) => total + (d.percent_covered || 0), 0);

  return Math.max(100 - covered, 0);
};

var call_approval_check = (frm, method, freeze_message) => {
  frappe.call({
    method: method,
    doc: frm.doc,
    freeze: true,
    freeze_message: freeze_message,
    callback: (r) => {
      let data = r.message || {};
      let amount_note = get_amount_note(data);

      if (data.status && data.status !== "ERROR") {
        frappe.utils.play_sound("success");
        frappe.show_alert({
          message: __(data.status) + amount_note,
          indicator: "green",
        });

        frappe.msgprint(amount_note);
      } else {
        frappe.utils.play_sound("error");
        frappe.msgprint({
          title: __("Pre-Authorization"),
          indicator: "red",
          message: (data.description || __("Unknown error")) + amount_note,
        });
      }

      frm.reload_doc();
    },
  });
};

var get_amount_note = (data) => {
  if (!data.amount && !data.approved_amount) {
    return "";
  }

  let requested = format_currency(data.amount || 0);
  let approved = format_currency(data.approved_amount || 0);

  return `<br>${__("Requested Amount")}: <b>${requested}</b> | ${__(
    "Approved Amount"
  )}: <b>${approved}</b>`;
};

var set_preauth_headline = (frm) => {
  if (!frm.doc.requires_approval) {
    return;
  }

  let color = "orange";
  let text = __("Pre-Authorization not yet sent to {0}", [
    frm.doc.insurance_company,
  ]);

  if (frm.doc.approval_status === "ERROR") {
    color = "red";
    text = __("Pre-Auth Failed: {0}", [frm.doc.approval_description || ""]);
  } else if (frm.doc.approval_status) {
    color = "green";
    text = __("Pre-Auth {0} — Submission ID: {1}", [
      frm.doc.approval_status,
      frm.doc.submission_id || "",
    ]);
  }

  frm.dashboard.set_headline(
    `<span class="indicator whitespace-nowrap ${color}">${text}</span>`
  );
};

var control_add_remove_btns = (frm, for_child = false) => {
  if (!for_child) {
    // hide button to add rows of delivery note item
    frm.get_field("services").grid.cannot_add_rows = true;

    // hide button to delete rows of delivery note item
    $("*[data-fieldname='services']").find(".grid-remove-rows").hide();
    $("*[data-fieldname='services']").find(".grid-remove-all-rows").hide();
  } else {
    frm.fields_dict.services.grid.wrapper.find(".grid-delete-row").hide();
    frm.fields_dict.services.grid.wrapper
      .find(".grid-insert-row-below")
      .hide();
    frm.fields_dict.services.grid.wrapper.find(".grid-insert-row").hide();
    frm.fields_dict.services.grid.wrapper.find(".grid-duplicate-row").hide();
    frm.fields_dict.services.grid.wrapper.find(".grid-move-row").hide();
  }
};

var set_filters = (frm) => {
  frm.set_query("insurance_subscription", "payments", () => {
    return {
      filters: {
        is_active: 1,
        patient: frm.doc.patient,
        name: ["!=", frm.doc.insurance_subscription],
      },
    };
  });

  frm.set_query("price_list", "payments", () => {
    return {
      filters: {
        enabled: 1,
        selling: 1,
      },
    };
  });

  frm.set_query("practitioner", () => {
    return {
      filters: {
        practitioner_role: "Doctor",
      },
    };
  });
};
