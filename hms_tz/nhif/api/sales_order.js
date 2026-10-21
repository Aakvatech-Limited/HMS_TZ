frappe.ui.form.on("Sales Order", {
  refresh: function (frm) {
    lock_encounter_items(frm);

    // 2024-03-12
    // disabling this, because sales order will be created automatic from patient encounter
    // if (frappe.boot.active_domains.includes("Healthcare")) {
    //     frm.set_df_property("patient", "hidden", 0);
    //     frm.set_df_property("patient_name", "hidden", 0);
    //     frm.set_df_property("ref_practitioner", "hidden", 0);
    //     if (cint(frm.doc.docstatus == 0) && cur_frm.page.current_view_name !== "pos" && !frm.doc.is_return) {
    //         frm.add_custom_button(__('Healthcare Services'), function () {
    //             get_healthcare_services_to_invoice(frm);
    //         }, "Get Items From");
    //     }
    // };
  },
  onload: function (frm) {
    lock_encounter_items(frm);
  },
  med_change_request: (frm) => {
    if (!frm.doc.med_change_request_comment) {
      frappe.msgprint(
        "<b>Please write an item(s) to be changed on the comment field</b>"
      );
      return;
    }
    frappe.call({
      method:
        "hms_tz.nhif.doctype.medication_change_request.medication_change_request.create_medication_change_request_from_so",
      args: {
        doctype: frm.doc.doctype,
        name: frm.doc.name,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: (r) => {},
    });
  },
});

frappe.ui.form.on("Sales Order Item", {
  form_render: (frm, cdt, cdn) => {
    if (frm.doc.patient_encounter) {
      frm.fields_dict.items.grid.wrapper.find(".grid-delete-row").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-insert-row-below").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-insert-row").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-duplicate-row").hide();
      frm.fields_dict.items.grid.wrapper.find(".grid-move-row").hide();
    }
  },
});

// Encounter items can only move to another warehouse
var lock_encounter_items = function (frm) {
  if (!frm.doc.patient_encounter) {
    return;
  }

  const grid = frm.get_field("items").grid;
  frappe.get_meta("Sales Order Item").fields.forEach((field) => {
    if (field.fieldname !== "warehouse") {
      grid.update_docfield_property(field.fieldname, "read_only", 1);
    }
  });

  // hide button to add rows of sales order item
  grid.cannot_add_rows = true;

  // hide button to delete rows of sales order item
  $("*[data-fieldname='items']").find(".grid-remove-rows").hide();
  $("*[data-fieldname='items']").find(".grid-remove-all-rows").hide();
};

var get_healthcare_services_to_invoice = function (frm) {
  var me = this;
  let selected_patient = "";
  var dialog = new frappe.ui.Dialog({
    title: __("Get Items From Healthcare Services"),
    fields: [
      {
        fieldtype: "Link",
        options: "Patient",
        label: "Patient",
        fieldname: "patient",
        reqd: true,
      },
      {
        fieldtype: "Link",
        options: "Patient Encounter",
        label: "Patient Encounter",
        fieldname: "encounter",
        reqd: true,
        get_query: function (doc) {
          return {
            filters: {
              patient: dialog.get_value("patient"),
              company: frm.doc.company,
              docstatus: 1,
            },
          };
        },
      },
      {
        fieldtype: "Button",
        label: "Get Items",
        fieldname: "get_items",
      },
      { fieldtype: "Section Break" },
      { fieldtype: "HTML", fieldname: "results_area" },
    ],
  });
  var $wrapper;
  var $results;
  var $placeholder;
  dialog.set_values({
    patient: frm.doc.patient,
  });
  dialog.fields_dict.get_items.input.onclick = function () {
    var patient = dialog.fields_dict.patient.input.value;
    var encounter = dialog.fields_dict.encounter.input.value;
    if (patient && encounter) {
      selected_patient = patient;
      var method =
        "hms_tz.nhif.api.healthcare_utils.get_healthcare_services_to_invoice";
      var args = {
        patient: patient,
        company: frm.doc.company,
        encounter: encounter,
        prescribed: 1,
      };
      var columns = ["service", "reference_name", "reference_type"];
      get_healthcare_items(
        frm,
        true,
        $results,
        $placeholder,
        method,
        args,
        columns
      );
    } else if (!patient) {
      selected_patient = "";
      $results.empty();
      $results.append($placeholder);
    }
  };
  $wrapper = dialog.fields_dict.results_area.$wrapper
    .append(`<div class="results"
		style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
  $results = $wrapper.find(".results");
  $placeholder = $(`<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x fa-heartbeat text-extra-muted"></i>
					<p class="text-extra-muted">No billable Healthcare Services found</p>
				</span>
			</div>`);
  $results.on("click", ".list-item--head :checkbox", (e) => {
    $results
      .find(".list-item-container .list-row-check")
      .prop("checked", $(e.target).is(":checked"));
  });
  set_primary_action(frm, dialog, $results, true);
  dialog.show();
};

var get_healthcare_items = function (
  frm,
  invoice_healthcare_services,
  $results,
  $placeholder,
  method,
  args,
  columns
) {
  var me = this;
  $results.empty();
  frappe.call({
    method: method,
    args: args,
    callback: function (data) {
      if (data.message) {
        $results.append(make_list_row(columns, invoice_healthcare_services));
        for (let i = 0; i < data.message.length; i++) {
          $results.append(
            make_list_row(
              columns,
              invoice_healthcare_services,
              data.message[i]
            )
          );
        }
      } else {
        $results.append($placeholder);
      }
    },
  });
};

var make_list_row = function (
  columns,
  invoice_healthcare_services,
  result = {}
) {
  var me = this;
  // Make a head row by default (if result not passed)
  let head = Object.keys(result).length === 0;
  let contents = ``;
  columns.forEach(function (column) {
    contents += `<div class="list-item__content ellipsis">
			${
        head
          ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`
          : column !== "name"
          ? `<span class="ellipsis">${__(result[column])}</span>`
          : `<a class="list-id ellipsis">
						${__(result[column])}</a>`
      }
		</div>`;
  });

  let $row = $(`<div class="list-item">
		<div class="list-item__content" style="flex: 0 0 10px;">
			<input type="checkbox" class="list-row-check" ${
        result.checked ? "checked" : ""
      }>
		</div>
		${contents}
	</div>`);

  $row = list_row_data_items(head, $row, result, invoice_healthcare_services);
  return $row;
};

var set_primary_action = function (
  frm,
  dialog,
  $results,
  invoice_healthcare_services
) {
  var me = this;
  dialog.set_primary_action(__("Add"), function () {
    let checked_values = get_checked_values($results);
    if (checked_values.length > 0) {
      if (invoice_healthcare_services) {
        frm.set_value("patient", dialog.fields_dict.patient.input.value);
      }
      add_to_item_line(frm, checked_values, invoice_healthcare_services);
      dialog.hide();
    } else {
      if (invoice_healthcare_services) {
        frappe.msgprint(__("Please select Healthcare Service"));
      } else {
        frappe.msgprint(__("Please select Drug"));
      }
    }
  });
};

var get_checked_values = function ($results) {
  return $results
    .find(".list-item-container")
    .map(function () {
      let checked_values = {};
      if ($(this).find(".list-row-check:checkbox:checked").length > 0) {
        checked_values["dn"] = $(this).attr("data-dn");
        checked_values["dt"] = $(this).attr("data-dt");
        checked_values["item"] = $(this).attr("data-item");
        if ($(this).attr("data-rate") != "undefined") {
          checked_values["rate"] = $(this).attr("data-rate");
        } else {
          checked_values["rate"] = false;
        }
        if ($(this).attr("data-income-account") != "undefined") {
          checked_values["income_account"] = $(this).attr(
            "data-income-account"
          );
        } else {
          checked_values["income_account"] = false;
        }
        if ($(this).attr("data-qty") != "undefined") {
          checked_values["qty"] = $(this).attr("data-qty");
        } else {
          checked_values["qty"] = false;
        }
        if ($(this).attr("data-description") != "undefined") {
          checked_values["description"] = $(this).attr("data-description");
        } else {
          checked_values["description"] = false;
        }
        if ($(this).attr("data-discount-percentage") != "undefined") {
          checked_values["discount_percentage"] = $(this).attr(
            "data-discount-percentage"
          );
        } else {
          checked_values["discount_percentage"] = false;
        }
        if ($(this).attr("data-insurance-claim-coverage") != "undefined") {
          checked_values["insurance_claim_coverage"] = $(this).attr(
            "data-insurance-claim-coverage"
          );
        } else {
          checked_values["insurance_claim_coverage"] = false;
        }
        if ($(this).attr("data-insurance-claim") != "undefined") {
          checked_values["insurance_claim"] = $(this).attr(
            "data-insurance-claim"
          );
        } else {
          checked_values["insurance_claim"] = false;
        }
        return checked_values;
      }
    })
    .get();
};
