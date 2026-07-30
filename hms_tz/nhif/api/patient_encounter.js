frappe.ui.form.on("Patient Encounter", {
  setup: (frm) => {
    nhif_btns(frm);
    jubilee_btns(frm);
  },
  on_submit: function (frm) {
    if (!frm.doc.patient_encounter_final_diagnosis) {
      frappe.throw(__("Final diagnosis mandatory before submit"));
    }
  },

  // Rock Regency#: 102
  // remove medical code restriction: 03-07-2023
  // validate: function (frm) {
  //     validate_medical_code(frm);
  // },

  onload: function (frm) {
    control_practitioners_to_submit_others_encounters(frm);
    nhif_btns(frm);
    jubilee_btns(frm);
    add_patient_history_btn(frm);
    add_refer_practtitioner_btn(frm);
    add_btn_final(frm);
    // duplicate(frm);
    set_btn_properties(frm);
    // set_empty_row_on_all_child_tables(frm);
    validate_healthcare_package_order_items(frm);
  },
  refresh: function (frm) {
    nhif_btns(frm);
    jubilee_btns(frm);
    control_practitioners_to_submit_others_encounters(frm);

    frm.fields_dict["drug_prescription"].grid.get_field(
      "healthcare_service_unit"
    ).get_query = function (doc, cdt, cdn) {
      return {
        filters: {
          company: doc.company,
          service_unit_type: "Pharmacy",
        },
      };
    };
    set_medical_code(frm, true);

    if (
      frm.doc.duplicated == 1 ||
      frm.doc.finalized ||
      frm.doc.practitioner.includes("Direct")
    ) {
      frm.remove_custom_button("Schedule Admission");
      frm.remove_custom_button("Refer Practitioner");
      frm.remove_custom_button("Vital Signs", "Create");
      frm.remove_custom_button("Medical Record", "Create");
      frm.remove_custom_button("Clinical Procedure", "Create");
    }
    if (frm.doc.duplicated == 1 && frm.doc.inpatient_record) {
      frm.remove_custom_button("Schedule Discharge");
    }
    duplicate(frm);
    if (frm.doc.source == "External Referral") {
      frm.set_df_property("referring_practitioner", "hidden", 1);
      frm.set_df_property("referring_practitioner", "reqd", 0);
    }
    frm.set_query("lab_test_code", "lab_test_prescription", function () {
      return {
        filters: {
          disabled: 0,
        },
      };
    });
    frm.set_query(
      "radiology_examination_template",
      "radiology_procedure_prescription",
      function () {
        return {
          filters: {
            disabled: 0,
          },
        };
      }
    );
    frm.set_query("procedure", "procedure_prescription", function () {
      return {
        filters: {
          disabled: 0,
        },
      };
    });

    // filter medication based on company
    filter_drug_prescriptions(frm);

    // Mosaic: https://worklog.aakvatech.com/Mosaic/Task/96b2f5e26c
    //filter dosage based on dosage form and has restricted qty ticked
    // comment this for now until further testing 13-02-2024
    // frm.set_query("dosage", "drug_prescription", function (doc, cdt, cdn) {
    //     const child = locals[cdt][cdn];
    //     return {
    //         query: "hms_tz.nhif.api.patient_encounter.get_filtered_dosage",
    //         filters: {
    //             dosage_form: child.dosage_form
    //         }
    //     }
    // });

    frm.set_query("therapy_type", "therapies", function () {
      return {
        filters: {
          disabled: 0,
        },
      };
    });

    frm.set_query(
      "code_value",
      "patient_encounter_preliminary_diagnosis",
      function () {
        return {
          filters: {
            disabled: 0,
            is_non_specific: 0,
            code_system: ["in", ["ICD-9", "ICD-10", "ICD-11"]],
          },
        };
      }
    );
    frm.set_query(
      "code_value",
      "patient_encounter_final_diagnosis",
      function () {
        return {
          filters: {
            disabled: 0,
            is_non_specific: 0,
            code_system: ["in", ["ICD-9", "ICD-10", "ICD-11"]],
          },
        };
      }
    );
    frm.set_query("main_diagnosis_code", function () {
      return {
        filters: {
          disabled: 0,
          is_non_specific: 0,
          code_system: ["in", ["ICD-9", "ICD-10", "ICD-11"]],
        },
      };
    });

    frm.set_query("default_healthcare_service_unit", function () {
      return {
        filters: {
          company: frm.doc.company,
          name: ["like", "%Pharmacy%"],
        },
      };
    });
    if (!frm.doc.practitioner.includes("Direct")) {
      frm.toggle_reqd("examination_detail", 1);
    }
    validate_healthcare_package_order_items(frm);
    set_btn_properties(frm);
    // set_delete_button_in_child_table(frm);
    frm.set_query("admission_service_unit_type", function () {
      return {
        filters: {
          inpatieint_occupancy: 1,
        },
      };
    });
  },

  clear_history: function (frm) {
    frm.set_value("examination_detail", "");
    frm.refresh_field("examination_detail");
  },

  default_healthcare_service_unit: function (frm) {
    if (frm.doc.default_healthcare_service_unit && frm.doc.drug_prescription) {
      frm.doc.drug_prescription.forEach((row) => {
        if (!row.healthcare_service_unit) {
          frappe.model.set_value(
            row.doctype,
            row.name,
            "healthcare_service_unit",
            frm.doc.default_healthcare_service_unit
          );
        }
      });
    }
  },
  get_chronic_diagnosis: function (frm) {
    if (frm.doc.docstatus == 1) {
      return;
    }
    frappe.call({
      method: "hms_tz.nhif.api.patient_encounter.get_chronic_diagnosis",
      args: {
        patient: frm.doc.patient,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (data) {
        if (data.message) {
          if (data.message.length == 0) {
            frappe.show_alert(
              {
                message: __(`There are no Chronic Diagnosis for this patient`),
                indicator: "red",
              },
              5
            );
            return;
          }
          data.message.forEach((element) => {
            const row_idx =
              frm.doc.patient_encounter_preliminary_diagnosis.findIndex(
                (x) => x.code_value === element.code_value
              );
            if (row_idx === -1) {
              let row = frappe.model.add_child(
                frm.doc,
                "Codification Table",
                "patient_encounter_preliminary_diagnosis"
              );
              row.code_value = element.code_value;
              row.code = element.code;
              row.definition = element.definition;
              frappe.show_alert(
                {
                  message: __(
                    `Medical Code '${element.code_value}' added successfully`
                  ),
                  indicator: "green",
                },
                5
              );
            } else {
              frappe.show_alert(
                {
                  message: __(
                    `Medical Code '${element.code_value}' already exists`
                  ),
                  indicator: "red",
                },
                5
              );
            }
          });
          frm.refresh_field("patient_encounter_preliminary_diagnosis");
          set_medical_code(frm, true);
          frm.trigger("copy_from_preliminary_diagnosis");
        }
      },
    });
  },

  hms_tz_add_chronic_diagnosis: function (frm) {
    if (frm.doc.docstatus == 0) {
      frappe
        .call("hms_tz.nhif.api.patient_encounter.add_chronic_diagnosis", {
          patient: frm.doc.patient,
          encounter: frm.doc.name,
          freeze: true,
          freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        })
        .then((r) => {
          // console.log(r.message);
        });
    }
  },

  get_chronic_medications: function (frm) {
    if (frm.doc.docstatus == 1) {
      return;
    }
    frappe.call({
      method: "hms_tz.nhif.api.patient_encounter.get_chronic_medications",
      args: {
        patient: frm.doc.patient,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (data) {
        if (data.message) {
          if (data.message.length == 0) {
            frappe.show_alert(
              {
                message: __(`There is no Chronic Medications`),
                indicator: "red",
              },
              5
            );
            return;
          }
          data.message.forEach((element) => {
            const row_idx = frm.doc.drug_prescription.findIndex(
              (x) => x.drug_code === element.drug_code
            );
            if (row_idx === -1) {
              let row = frappe.model.add_child(
                frm.doc,
                "Drug Prescription",
                "drug_prescription"
              );
              row.drug_code = element.drug_code;
              row.drug_name = element.drug_name;
              row.dosage = element.dosage;
              row.period = element.period;
              row.dosage_form = element.dosage_form;
              row.comment = element.comment;
              row.usage_interval = element.usage_interval;
              row.interval = element.interval;
              row.interval_uom = element.interval_uom;
              row.update_schedule = element.update_schedule;
              row.intent = element.intent;
              row.quantity = element.quantity;
              row.sequence = element.sequence;
              row.expected_date = element.expected_date;
              row.as_needed = element.as_needed;
              row.patient_instruction = element.patient_instruction;
              row.replaces = element.replaces;
              row.priority = element.priority;
              row.occurrence = element.occurrence;
              row.occurence_period = element.occurence_period;
              row.note = element.note;
              frm.trigger("default_healthcare_service_unit");
              frappe.show_alert(
                {
                  message: __(
                    `Drug '${element.drug_code}' added successfully`
                  ),
                  indicator: "green",
                },
                5
              );
            } else {
              frappe.show_alert(
                {
                  message: __(`Drug '${element.drug_code}' already exists`),
                  indicator: "red",
                },
                5
              );
            }
          });
          frm.refresh_field("drug_prescription");
        }
      },
    });
  },
  add_chronic_medications: (frm) => {
    if (frm.doc.docstatus == 0) {
      let items = frm
        .get_field("drug_prescription")
        .grid.get_selected_children();
      frappe
        .call("hms_tz.nhif.api.patient_encounter.add_chronic_medications", {
          patient: frm.doc.patient,
          encounter: frm.doc.name,
          items: items,
          freeze: true,
          freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
        })
        .then((r) => {
          // console.log(r.message);
        });
    }
  },
  copy_from_preliminary_diagnosis: function (frm) {
    if (frm.doc.docstatus == 1) {
      return;
    }
    function set_final_diagnosis(frm, preliminary_diagnosis) {
      preliminary_diagnosis.forEach((element) => {
        const row_idx = frm.doc.patient_encounter_final_diagnosis.findIndex(
          (x) => x.code_value === element.code_value
        );
        if (row_idx === -1) {
          let row = frappe.model.add_child(
            frm.doc,
            "Codification Table",
            "patient_encounter_final_diagnosis"
          );
          row.code_value = element.code_value;
          row.code = element.code;
          row.definition = element.definition;
          row.mtuha = element.mtuha;
          // frappe.show_alert({
          //     message: __(`Medical Code '${element.code_value}' added successfully`),
          //     indicator: 'green'
          // }, 5);
        } else {
          frappe.show_alert(
            {
              message: __(
                `Medical Code '${element.code_value}' already exists`
              ),
              indicator: "yellow",
            },
            5
          );
        }
      });
      frm.refresh_field("patient_encounter_final_diagnosis");
      set_medical_code(frm);
    }
    if (frm.doc.patient_encounter_preliminary_diagnosis.length > 0) {
      let selected = frm
        .get_field("patient_encounter_preliminary_diagnosis")
        .grid.get_selected_children();
      if (selected.length > 0) {
        set_final_diagnosis(frm, selected);
      } else {
        set_final_diagnosis(
          frm,
          frm.doc.patient_encounter_preliminary_diagnosis
        );
      }
    } else {
      frappe.show_alert(
        {
          message: __(`There are no Preliminary Diagnosis`),
          indicator: "yellow",
        },
        5
      );
    }
  },
  encounter_category: function (frm) {
    if (
      frm.doc.patient_encounter_preliminary_diagnosis &&
      frm.doc.patient_encounter_preliminary_diagnosis.length > 1
    ) {
      return;
    } else if (frm.doc.practitioner.includes("Direct")) {
      let preliminary_row = frappe.model.add_child(
        frm.doc,
        "Codification Table",
        "patient_encounter_preliminary_diagnosis"
      );
      preliminary_row.code_value = "ICD-10 R69";
      preliminary_row.code = "R69";
      preliminary_row.description =
        "Unknown and unspecified causes of morbidity";
      preliminary_row.mtuha = "Other";
      frm.refresh_field("patient_encounter_preliminary_diagnosis");
      let final_row = frappe.model.add_child(
        frm.doc,
        "Codification Table",
        "patient_encounter_final_diagnosis"
      );
      final_row.code_value = "ICD-10 R69";
      final_row.code = "R69";
      final_row.description = "Unknown and unspecified causes of morbidity";
      final_row.mtuha = "Other";
      frm.refresh_field("patient_encounter_final_diagnosis");
    }
    set_medical_code(frm, true);
  },
  create_sales_invoice: function (frm) {
    if (
      frm.doc.docstatus != 0 ||
      !frm.doc.encounter_mode_of_payment ||
      !frm.doc.encounter_category ||
      frm.doc.sales_invoice
    ) {
      frappe.show_alert(__("The criteria for this button to work not met!"));
      return;
    }
    frappe.call({
      method: "hms_tz.nhif.api.patient_encounter.create_sales_invoice",
      args: {
        encounter: frm.doc.name,
        encounter_category: frm.doc.encounter_category,
        encounter_mode_of_payment: frm.doc.encounter_mode_of_payment,
      },
      callback: function (data) {
        frm.reload_doc();
      },
    });
  },
  sent_to_vfd: function (frm) {
    if (!frm.doc.sales_invoice) return;
    frappe.call({
      method: "hms_tz.nhif.api.patient_appointment.send_vfd",
      args: {
        invoice_name: frm.doc.sales_invoice,
      },
      callback: function (data) {
        if (data.message) {
          if (data.message.enqueue) {
            load_print_page(frm.doc.sales_invoice, data.message.pos_rofile);
          }
        }
      },
    });
  },
  undo_set_as_final: function (frm) {
    if (!frm.doc.finalized) return;
    if (frm.doc.healthcare_package_order) {
      frappe.msgprint(
        __(
          "This encounter cannot undo set as final because it is from healthcare package order"
        )
      );
      return;
    }
    frappe.call({
      method: "hms_tz.nhif.api.patient_encounter.undo_finalized_encounter",
      args: {
        ref_encounter: frm.doc.reference_encounter,
        cur_encounter: frm.doc.name,
      },
      freeze: true,
      freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      callback: function (data) {
        frm.reload_doc();
      },
    });
  },
  get_lab_bundle_items: function (frm, cdt, cdn) {
    var doc = locals[cdt][cdn];
    if (doc.lab_bundle) {
      frappe.call({
        method: "frappe.client.get",
        args: {
          name: doc.lab_bundle,
          doctype: "Lab Bundle",
        },
        callback(r) {
          if (r.message) {
            for (var row in r.message.lab_bundle_item) {
              var child = frm.add_child("lab_test_prescription");
              frappe.model.set_value(
                child.doctype,
                child.name,
                "lab_test_code",
                r.message.lab_bundle_item[row].lab_test_template
              );
              frm.refresh_field("lab_test_prescription");
            }
          }
        },
      });
    }
  },
  hms_tz_convert_to_inpatient: (frm) => {
    if (!frm.doc.mode_of_payment) {
      frappe.msgprint(`<p class='text-center font-weight-bold h6' style='background-color: #DCDCDC; font-size: 12pt;'>\
                This encounter has insurance of <b>${__(
                  frm.doc.insurance_coverage_plan
                )}</b>,\
                no need to convert this encounter to inpatient encounter </p>`);
      return;
    }
    frappe
      .call(
        "hms_tz.nhif.api.patient_encounter.convert_opd_encounter_to_ipd_encounter",
        {
          encounter: frm.doc.name,
        }
      )
      .then((r) => {
        if (r.message) {
          frm.refresh();
        }
      });
  },
  hms_tz_reuse_lab_items: (frm) => {
    let fields = [
      "lab_test_code as item",
      "lab_test_name as item_name",
      "creation as date",
    ];
    let value_dict = {
      table_field: "lab_test_prescription",
      item_field: "lab_test_code",
      item_name_field: "lab_test_name",
    };
    reuse_lrpmt_items(
      frm,
      "Lab Prescription",
      fields,
      value_dict,
      "Lab Items"
    );
  },
  hms_tz_reuse_radiology_items: (frm) => {
    let fields = [
      "radiology_examination_template as item",
      "radiology_procedure_name as item_name",
      "creation as date",
    ];
    let value_dict = {
      table_field: "radiology_procedure_prescription",
      item_field: "radiology_examination_template",
      item_name_field: "radiology_procedure_name",
    };
    reuse_lrpmt_items(
      frm,
      "Radiology Procedure Prescription",
      fields,
      value_dict,
      "Radiology Items"
    );
  },
  hms_tz_reuse_procedure_items: (frm) => {
    let fields = [
      "procedure as item",
      "procedure_name as item_name",
      "creation as date",
    ];
    let value_dict = {
      table_field: "procedure_prescription",
      item_field: "procedure",
      item_name_field: "procedure_name",
    };
    reuse_lrpmt_items(
      frm,
      "Procedure Prescription",
      fields,
      value_dict,
      "Procedure Items"
    );
  },
  hms_tz_reuse_drug_items: (frm) => {
    let fields = [
      "drug_code as item",
      "drug_name as item_name",
      "medical_code",
      "dosage",
      "period",
      "quantity",
      "quantity_returned",
      "creation as date",
    ];
    let value_dict = {
      table_field: "drug_prescription",
      item_field: "drug_code",
      item_name_field: "drug_name",
    };
    reuse_lrpmt_items(
      frm,
      "Drug Prescription",
      fields,
      value_dict,
      "Drug Items",
      "Medication"
    );
  },
  hms_tz_reuse_therapy_items: (frm) => {
    let fields = [
      "therapy_type as item",
      "therapy_type as item_name",
      "creation as date",
    ];
    let value_dict = {
      table_field: "therapies",
      item_field: "therapy_type",
      item_name_field: "therapy_type",
    };
    reuse_lrpmt_items(
      frm,
      "Therapy Plan Detail",
      fields,
      value_dict,
      "Therapy Items"
    );
  },
  hms_tz_reuse_previous_diagnosis: (frm) => {
    let fields = [
      "code_value as item",
      "code as item_name",
      "definition as description",
      "mtuha",
      "creation as date",
    ];
    let value_dict = {
      table_field: "patient_encounter_preliminary_diagnosis",
      item_field: "code_value",
      item_name_field: "code",
      description_field: "definition",
      mtuha_field: "mtuha",
    };
    reuse_lrpmt_items(
      frm,
      "Codification Table",
      fields,
      value_dict,
      "Previous Diagnosis",
      "Diagnosis"
    );
  },
  hms_tz_patient_history: (frm) => {
    if (frm.doc.patient) {
      frappe.route_options = { patient: frm.doc.patient };
      frappe.open_in_new_tab = true;
      frappe.set_route("tz-patient-history");
    } else {
      frappe.msgprint(__("Please select Patient"));
    }
  },
  cost_estimate: (frm) => {
    if (!frm.doc.patient) {
      frappe.msgprint(__("Please select Patient"));
      return;
    }
    frappe.call({
      method: "hms_tz.nhif.api.patient_encounter.get_encounter_cost_estimate",
      args: {
        encounter_doc: frm.doc,
      },
      callback: function (r) {
        if (r.message) {
          show_cost_estimate_model(frm, r.message);
        }
      },
    });
  },
});

function show_cost_estimate_model(frm, cost_estimate) {
  // create a dialog
  const dialog = new frappe.ui.Dialog({
    title: __("Cost Estimate"),
    fields: [
      {
        fieldtype: "HTML",
        fieldname: "cost_estimate_html",
        label: __("Cost Estimate"),
      },
    ],
    primary_action_label: __("Close"),
    primary_action: () => {
      dialog.hide();
    },
  });
  // setup the html content
  let cost_estimate_html = '<div class="container-fluid">';
  cost_estimate_html += '<div class="row">';
  cost_estimate_html += '<div class="col-md-12">';
  cost_estimate_html += '<table class="table table-bordered">';
  cost_estimate_html += "<thead>";
  cost_estimate_html += "<tr>";
  cost_estimate_html += '<th scope="col">Item</th>';
  cost_estimate_html += '<th scope="col">Amount</th>';
  cost_estimate_html += "</tr>";
  cost_estimate_html += "</thead>";
  cost_estimate_html += "<tbody>";
  for (let item_type in cost_estimate.details) {
    cost_estimate_html += "<tr>";
    cost_estimate_html +=
      '<td colspan="2" class="text-center"><strong>' +
      item_type +
      "</strong></td>";
    cost_estimate_html += "</tr>";
    for (let item of cost_estimate.details[item_type]) {
      cost_estimate_html += "<tr>";
      cost_estimate_html += "<td>" + item.item + "</td>";
      cost_estimate_html +=
        "<td>" +
        item.amount.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }) +
        "</td>";
      cost_estimate_html += "</tr>";
    }
  }
  cost_estimate_html += "<tr>";
  cost_estimate_html +=
    '<td colspan="2" class="text-center"><strong>Total Cost: ' +
    cost_estimate.total_cost.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }) +
    "</strong></td>";
  cost_estimate_html += "</tr>";
  cost_estimate_html += "</tbody>";
  cost_estimate_html += "</table>";
  cost_estimate_html += "</div>";
  cost_estimate_html += "</div>";
  cost_estimate_html += "</div>";
  dialog.fields_dict.cost_estimate_html.$wrapper.html(cost_estimate_html);
  dialog.show();
}

frappe.ui.form.on("Codification Table", {
  patient_encounter_preliminary_diagnosis_remove: set_medical_code,
  patient_encounter_final_diagnosis_remove: set_medical_code,
  code_value: set_medical_code,
});

function get_diagnosis_list(frm, table_name) {
  const diagnosis_list = [];
  if (frm.doc[table_name]) {
    frm.doc[table_name].forEach((element) => {
      if (!element.code_value) return;
      let d = String(element.code_value) + "\n " + String(element.definition);
      diagnosis_list.push(d);
    });
  }
  return diagnosis_list;
}

const medical_code_mapping = {
  patient_encounter_preliminary_diagnosis: [
    "radiology_procedure_prescription",
    "lab_test_prescription",
  ],
  patient_encounter_final_diagnosis: [
    "procedure_prescription",
    "drug_prescription",
    "therapies",
    "diet_recommendation",
  ],
};

function set_medical_code(frm, reset_columns) {
  function set_options_for_fields(fields, from_table) {
    const options = get_diagnosis_list(frm, from_table);

    for (const fieldname of fields) {
      const grid = frm.fields_dict[fieldname].grid;

      if (reset_columns) {
        grid.visible_columns = undefined;
        grid.setup_visible_columns();
      }

      grid.fields_map.medical_code.options = options;
      grid.refresh();

      if (reset_columns) {
        frm.fields_dict[fieldname].grid.grid_rows.forEach((row) => {
          row.docfields.forEach((docfield) => {
            if (docfield.fieldname === "medical_code") {
              docfield.options = options;
            }
          });
        });
      }
      frm.refresh_field(fieldname);
      grid.refresh();
      grid.setup_visible_columns();
    }
  }

  for (const [from_table, fields] of Object.entries(medical_code_mapping)) {
    set_options_for_fields(fields, from_table);
  }
}

function validate_medical_code(frm) {
  let values_mapping = {
    lab_test_prescription: "lab_test_code",
    radiology_procedure_prescription: "radiology_examination_template",
    procedure_prescription: "procedure",
    drug_prescription: "drug_code",
    therapies: "therapy_type",
  };

  for (const [from_table, fields] of Object.entries(medical_code_mapping)) {
    const options = get_diagnosis_list(frm, from_table);

    for (const fieldname of fields) {
      if (!frm.doc[fieldname]) continue;

      frm.doc[fieldname].forEach((element) => {
        if (
          element[values_mapping[fieldname]] &&
          !options.includes(element.medical_code)
        ) {
          frappe.throw(
            __(`The Medical Code in the
                    ${frm.fields_dict[fieldname].df.label} table
                    at line ${element.idx} is empty or does not exist in the
                    ${frm.fields_dict[from_table].df.label} table.`)
          );
        }
      });
    }
  }
}

var add_btn_final = (frm) => {
  if (
    frm.doc.docstatus == 1 &&
    frm.doc.encounter_type != "Final" &&
    frm.doc.duplicated == 0
  ) {
    if (!frm.page.fields_dict.set_as_final) {
      frm.page
        .add_field({
          fieldname: "set_as_final",
          label: __("Set as Final"),
          fieldtype: "Button",
          click: function () {
            frappe.call({
              method: "hms_tz.nhif.api.patient_encounter.finalized_encounter",
              args: {
                cur_encounter: frm.doc.name,
                ref_encounter: frm.doc.reference_encounter,
              },
              freeze: true,
              freeze_message: __(
                '<i class="fa fa-spinner fa-spin fa-4x"></i>'
              ),
              callback: function (data) {
                $('[data-fieldname="set_as_final"]').hide();
                $('[data-fieldname="referring_practitioner"]').hide();
                frm.reload_doc();
              },
            });
          },
        })
        .$input.addClass("btn-sm");
    }
  }
};

var duplicate = function (frm) {
  if (
    frm.doc.docstatus != 1 ||
    frm.doc.encounter_type == "Final" ||
    frm.doc.duplicated == 1 ||
    frm.doc.practitioner.includes("Direct")
  ) {
    return;
  }
  let click_count = 0;
  frm.add_custom_button(__("Duplicate"), function () {
    if (click_count > 0) {
      return;
    }
    click_count += 1;

    if (frm.is_dirty()) {
      frm.save();
    }

    frappe.call({
      method: "hms_tz.nhif.api.patient_encounter.duplicate_encounter",
      args: {
        encounter: frm.doc.name,
      },
      callback: function (data) {
        if (data.message) {
          frappe.set_route("Form", "Patient Encounter", data.message);
          setTimeout(function () {
            frm.reload_doc();
          }, 2000);
        }
      },
    });
  });
};

frappe.ui.form.on("Lab Prescription", {
  lab_test_code: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.lab_test_code) {
      return;
    }
    set_is_not_available_inhouse(frm, row, row.lab_test_code).then(() => {
      if (row.is_not_available_inhouse) {
        msgprint =
          "NOTE: This healthcare service item, <b>" +
          row.lab_test_code +
          "</b>, is not available inhouse and has been marked as prescribe.<br><br>Request the patient to get it from another healthcare service provider.";
        frappe.show_alert(__(msgprint));
      } else {
        frappe.model.set_value(cdt, cdn, "prescribe", 0);
      }
    });
  },
  is_not_available_inhouse: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.is_not_available_inhouse) {
      frappe.model.set_value(cdt, cdn, "prescribe", 1);
    } else {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
  prescribe: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.prescribe || !row.lab_test_code) {
      frappe.model.set_value(cdt, cdn, "override_subscription", 0);
    }
  },
  override_subscription: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.override_subscription) {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
});

frappe.ui.form.on("Radiology Procedure Prescription", {
  radiology_examination_template: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (!row.radiology_examination_template) {
      return;
    }
    set_is_not_available_inhouse(
      frm,
      row,
      row.radiology_examination_template
    ).then(() => {
      if (row.is_not_available_inhouse) {
        msgprint =
          "NOTE: This healthcare service item, <b>" +
          row.radiology_examination_template +
          "</b>, is not available inhouse and has been marked as prescribe.<br>Request the patient to get it from another healthcare service provider.";
        frappe.show_alert(__(msgprint));
      } else {
        frappe.model.set_value(cdt, cdn, "prescribe", 0);
      }
    });
  },
  is_not_available_inhouse: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.is_not_available_inhouse) {
      frappe.model.set_value(cdt, cdn, "prescribe", 1);
    } else {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
  prescribe: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.prescribe || !row.radiology_examination_template) {
      frappe.model.set_value(cdt, cdn, "override_subscription", 0);
    }
  },
  override_subscription: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.override_subscription) {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
});

frappe.ui.form.on("Procedure Prescription", {
  procedure: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (!row.procedure) {
      return;
    }
    set_is_not_available_inhouse(frm, row, row.procedure).then(() => {
      if (row.is_not_available_inhouse) {
        msgprint =
          "NOTE: This healthcare service item, <b>" +
          row.procedure +
          "</b>, is not available inhouse and has been marked as prescribe.<br>Request the patient to get it from another healthcare service provider.";
        frappe.show_alert(__(msgprint));
      } else {
        frappe.model.set_value(cdt, cdn, "prescribe", 0);
      }
    });
  },
  is_not_available_inhouse: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.is_not_available_inhouse) {
      frappe.model.set_value(cdt, cdn, "prescribe", 1);
    } else {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
  prescribe: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.prescribe || !row.procedure) {
      frappe.model.set_value(cdt, cdn, "override_subscription", 0);
    }
  },
  override_subscription: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.override_subscription) {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
});

frappe.ui.form.on("Drug Prescription", {
  drug_code: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (!row.drug_code) {
      return;
    }
    set_is_not_available_inhouse(frm, row, row.drug_code).then(() => {
      if (row.is_not_available_inhouse) {
        msgprint =
          "NOTE: This healthcare service item, <b>" +
          row.drug_code +
          "</b>, is not available inhouse and has been marked as prescribe.<br>Request the patient to get it from another healthcare service provider.";
        frappe.show_alert(__(msgprint));
      } else {
        frappe.model.set_value(cdt, cdn, "prescribe", 0);
      }
    });
    validate_stock_item(
      frm,
      row.drug_code,
      row.prescribe,
      row.quantity,
      row.healthcare_service_unit,
      "Drug Prescription"
    );

    // shm rock: 169
    validate_medication_class(frm, row.drug_code);
  },
  healthcare_service_unit: function (frm, cdt, cdn) {
    if (frm.healthcare_service_unit) frm.trigger("drug_code");
  },
  is_not_available_inhouse: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.is_not_available_inhouse) {
      frappe.model.set_value(cdt, cdn, "prescribe", 1);
    } else {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
  prescribe: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.prescribe == 1) {
      frappe.db
        .get_value("HMS TZ Setting", frm.doc.company, [
          "auto_set_pharmacy_on_patient_encounter",
          "opd_cash_pharmacy",
          "ipd_cash_pharmacy",
        ])
        .then((r) => {
          let values = r.message;
          if (values && values.auto_set_pharmacy_on_patient_encounter == 1) {
            if (frm.doc.inpatient_record) {
              frappe.model.set_value(
                cdt,
                cdn,
                "healthcare_service_unit",
                values.ipd_cash_pharmacy
              );
            } else {
              frappe.model.set_value(
                cdt,
                cdn,
                "healthcare_service_unit",
                values.opd_cash_pharmacy
              );
            }
          }

          frm.refresh_field("drug_prescription");
        });
    } else {
      if (row.prescribe == 0 && frm.doc.insurance_coverage_plan) {
        frappe.db
          .get_value(
            "Healthcare Insurance Coverage Plan",
            frm.doc.insurance_coverage_plan,
            [
              "auto_set_pharmacy_on_patient_encounter",
              "opd_insurance_pharmacy",
              "ipd_insurance_pharmacy",
            ]
          )
          .then((r) => {
            let values = r.message;
            if (values && values.auto_set_pharmacy_on_patient_encounter == 1) {
              if (frm.doc.inpatient_record) {
                if (
                  row.healthcare_service_unit != values.ipd_insurance_pharmacy
                ) {
                  frappe.model.set_value(
                    cdt,
                    cdn,
                    "healthcare_service_unit",
                    values.ipd_insurance_pharmacy
                  );
                }
              } else {
                if (
                  row.healthcare_service_unit != values.opd_insurance_pharmacy
                ) {
                  frappe.model.set_value(
                    cdt,
                    cdn,
                    "healthcare_service_unit",
                    values.opd_insurance_pharmacy
                  );
                }
              }
              frm.refresh_field("drug_prescription");
            }
          });
      }
      if (row.prescribe || !row.drug_code) {
        frappe.model.set_value(cdt, cdn, "override_subscription", 0);
      }
    }
  },
  quantity: function (frm, cdt, cdn) {
    if (frm.quantity) frm.trigger("drug_code");
  },
  override_subscription: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.override_subscription) {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
      validate_stock_item(
        frm,
        row.drug_code,
        row.prescribe,
        row.quantity,
        row.healthcare_service_unit,
        "Drug Prescription"
      );
    }
  },
  dosage: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.dosage && row.period) {
      auto_calculate_drug_quantity(frm, row);
    } else {
      frappe.model.set_value(cdt, cdn, "quantity", 0);
    }
    frm.refresh_field("drug_prescription");
  },
  period: (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.dosage && row.period) {
      auto_calculate_drug_quantity(frm, row);
    } else {
      frappe.model.set_value(cdt, cdn, "quantity", 0);
    }
    frm.refresh_field("drug_prescription");
  },
  drug_prescription_add: function (frm, cdt, cdn) {
    var row = frappe.get_doc(cdt, cdn);
    if (!row.healthcare_service_unit)
      row.healthcare_service_unit = frm.doc.default_healthcare_service_unit;
    frm.refresh_field("drug_prescription");
  },
});

frappe.ui.form.on("Therapy Plan Detail", {
  therapy_type: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (!row.therapy_type) {
      return;
    }
    set_is_not_available_inhouse(frm, row, row.therapy_type).then(() => {
      if (row.is_not_available_inhouse) {
        msgprint =
          "NOTE: This healthcare service item, <b>" +
          row.therapy_type +
          "</b>, is not available inhouse and has been marked as prescribe.<br>Request the patient to get it from another healthcare service provider.";
        frappe.show_alert(__(msgprint));
      } else {
        frappe.model.set_value(cdt, cdn, "prescribe", 0);
      }
    });
  },
  is_not_available_inhouse: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.is_not_available_inhouse) {
      frappe.model.set_value(cdt, cdn, "prescribe", 1);
    } else {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
  prescribe: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.prescribe || !row.therapy_type) {
      frappe.model.set_value(cdt, cdn, "override_subscription", 0);
    }
  },
  override_subscription: function (frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.override_subscription) {
      frappe.model.set_value(cdt, cdn, "prescribe", 0);
    }
  },
});

const validate_stock_item = function (
  frm,
  healthcare_service,
  prescribe = 0,
  qty = 1,
  healthcare_service_unit = "",
  caller = "Unknown"
) {
  if (healthcare_service_unit == "") {
    healthcare_service_unit = frm.doc.healthcare_service_unit;
  }
  frappe.call({
    method: "hms_tz.nhif.api.healthcare_utils.validate_stock_item",
    args: {
      healthcare_service: healthcare_service,
      qty: qty,
      company: frm.doc.company,
      prescribe: prescribe,
      caller: caller,
      healthcare_service_unit: healthcare_service_unit,
    },
    callback: function (data) {
      if (data.message) {
        // console.log(data.message)
      }
    },
  });
};
const load_print_page = function (invoice_name, pos_profile) {
  const print_format = pos_profile.print_format || "AV Tax Invoice";
  const letter_head = pos_profile.letter_head || 0;
  const url =
    frappe.urllib.get_base_url() +
    "/printview?doctype=Sales%20Invoice&name=" +
    invoice_name +
    "&trigger_print=1" +
    "&format=" +
    print_format +
    "&no_letterhead=" +
    letter_head;
  const printWindow = window.open(url, "Print");
  printWindow.addEventListener(
    "load",
    function () {
      printWindow.print();
    },
    true
  );
};

const set_is_not_available_inhouse = function (frm, row, template) {
  return frappe.call({
    method: "hms_tz.nhif.api.healthcare_utils.get_template_company_option",
    args: {
      template: template,
      company: frm.doc.company,
      method: "validate",
    },
    callback: function (data) {
      if (data.message) {
        row.is_not_available_inhouse = data.message.is_not_available;
      } else {
        row.is_not_available_inhouse = 0;
      }
    },
  });
};

var set_btn_properties = (frm) => {
  $('[data-fieldname="hms_tz_convert_to_inpatient"]')
    .removeClass("btn-default")
    .addClass("btn-info align-middle text-white font-weight-bold")
    .css({
      "font-size": "16px",
      "border-radius": "6px",
      cursor: "pointer",
      width: "180px",
    });
  $('[data-fieldname="hms_tz_patient_history"]')
    .removeClass("btn-default")
    .addClass("btn-primary align-middle text-white font-weight-bold")
    .css({
      "font-size": "16px",
      "border-radius": "6px",
      cursor: "pointer",
      width: "180px",
    });
};

var reuse_lrpmt_items = (
  frm,
  doctype,
  fields,
  value_dict,
  item_category,
  caller = ""
) => {
  let filters = {
    patient: frm.doc.patient,
    appointment: frm.doc.appointment,
    doctype: doctype,
    fields: fields,
  };
  let d = new frappe.ui.Dialog({
    title: "Select Item",
    fields: [
      {
        fieldname: "item_category",
        fieldtype: "Data",
        read_only: 1,
        Bold: 1,
      },
      {
        fieldname: "no_of_visit_sb",
        fieldtype: "Section Break",
      },
      {
        fieldname: "number_of_visit",
        fieldtype: "Int",
        label: "Number of Visit",
        default: 5,
        reqd: 1,
      },
      {
        fieldname: "include_cb",
        fieldtype: "Column Break",
      },
      {
        fieldname: "include_ipd_encounters",
        fieldtype: "Check",
        label: "Include IPD Encounters",
        Bold: 1,
      },
      {
        fieldname: "filters_cb",
        fieldtype: "Column Break",
      },
      {
        fieldname: "apply_filters",
        fieldtype: "Button",
        label: "Apply Filters",
      },
      {
        fieldname: "space_sb",
        fieldtype: "Section Break",
      },
      {
        fieldname: "space",
        fieldtype: "HTML",
      },
    ],
  });
  d.set_value("item_category", item_category);
  let wrapper = d.fields_dict.space.$wrapper;

  filters.number_of_visit = d.get_value("number_of_visit");
  if (filters.number_of_visit) {
    get_items(filters, wrapper, caller);
  }

  d.fields_dict.apply_filters.$input.click(() => {
    if (!d.get_value("number_of_visit")) {
      frappe.msgprint(
        "<h4 class='text-center' style='background-color: #D3D3D3; font-weight: bold;'>\
                Please enter number of visit</h4>"
      );
      return;
    }

    filters.number_of_visit = d.get_value("number_of_visit");
    filters.include_ipd_encounters = d.get_value("include_ipd_encounters");
    get_items(filters, wrapper, caller);
  });

  d.set_primary_action(__("Reuse Item"), () => {
    let items = [];

    wrapper.find("tr:has(input:checked)").each(function () {
      if (caller == "Diagnosis") {
        items.push({
          item: $(this).find("#item").attr("data-item"),
          item_name: $(this).find("#item_name").attr("data-item_name"),
          description: $(this).find("#description").attr("data-description"),
          mtuha: $(this).find("#mtuha").attr("data-mtuha"),
        });
      } else if (caller == "Medication") {
        items.push({
          item: $(this).find("#item").attr("data-item"),
          item_name: $(this).find("#item_name").attr("data-item_name"),
          medical_code: $(this)
            .find("#medical_code")
            .attr("data-medical_code"),
          dosage: $(this).find("#dosage").attr("data-dosage"),
          period: $(this).find("#period").attr("data-period"),
          quantity: $(this).find("#quantity").attr("data-quantity"),
        });
      } else {
        items.push({
          item: $(this).find("#item").attr("data-item"),
          item_name: $(this).find("#item_name").attr("data-item_name"),
        });
      }
    });

    if (items.length > 0) {
      let field = String(value_dict.table_field);
      if (caller == "Diagnosis") {
        items.forEach((item) => {
          let new_row = {};
          new_row[value_dict.item_field] = item.item;
          new_row[value_dict.item_name_field] = item.item_name;
          new_row[value_dict.description_field] = item.description;
          new_row[value_dict.mtuha_field] = item.mtuha;
          let row = frm.add_child(field, new_row);
        });
        set_medical_code(frm, true);
      } else {
        if (doctype == "Drug Prescription") {
          items.forEach((item) => {
            if (item.medical_code) {
              let diagnosis_codes =
                frm.doc.patient_encounter_final_diagnosis.map(
                  (d) => d.medical_code
                );
              let medical_code = item.medical_code.split("\n");
              if (!diagnosis_codes.includes(medical_code[0])) {
                let new_row = {};
                new_row.medical_code = medical_code[0];
                new_row.code = medical_code[0].split(" ")[1];
                new_row.description = medical_code[1];
                let row = frm.add_child(
                  "patient_encounter_final_diagnosis",
                  new_row
                );
              }
              set_medical_code(frm, true);
              frm.refresh_field("patient_encounter_final_diagnosis");
            }
            if (item.item) {
              let new_row = {};
              new_row[value_dict.item_field] = item.item;
              new_row[value_dict.item_name_field] = item.item_name;
              new_row.medical_code = item.medical_code;
              new_row.dosage = item.dosage;
              new_row.period = item.period;
              new_row.quantity = parseInt(item.quantity);
              let row = frm.add_child(field, new_row);
            }
          });
          frm.trigger("default_healthcare_service_unit");
        } else {
          items.forEach((item) => {
            let new_row = {};
            new_row[value_dict.item_field] = item.item;
            new_row[value_dict.item_name_field] = item.item_name;
            let row = frm.add_child(field, new_row);
          });
        }
      }
      frm.refresh_field(field);
      d.hide();
    } else {
      frappe.msgprint({
        title: __("Message"),
        indicator: "red",
        message: __(
          '<h4 class="text-center" style="background-color: #D3D3D3; font-weight: bold;">\
                    No any Item selected<h4>'
        ),
      });
    }
  });

  d.$body
    .find("button[data-fieldtype='Button']")
    .removeClass("btn-default")
    .addClass("btn-info");
  d.$body.on("change", "#th", function () {
    var isChecked = $(this).prop("checked");
    wrapper.find('input[type="checkbox"]').prop("checked", isChecked);
  });

  d.$wrapper.find(".modal-content").css({
    width: "650px",
    "max-height": "1000px",
    overflow: "auto",
  });

  d.show();

  function get_items(filters, wrapper, caller) {
    frappe
      .call({
        method:
          "hms_tz.nhif.api.patient_encounter.get_previous_diagnosis_and_lrpmt_items_to_reuse",
        args: {
          kwargs: filters,
          caller: caller,
        },
        freeze: true,
        freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
      })
      .then((r) => {
        let records = r.message;
        if (records.length > 0) {
          let html = show_details(records, caller);
          wrapper.html(html);
        } else {
          wrapper.html("");
          wrapper.append(`<div class="multiselect-empty-state"
                    style="border: 1px solid #d1d8dd; border-radius: 3px; height: 200px; overflow: auto;">
                    <span class="text-center" style="margin-top: -40px;">
                        <i class="fa fa-2x fa-heartbeat text-extra-muted"></i>
                        <p class="text-extra-muted text-center" style="font-size: 16px; font-weight: bold;">
                        No Item(s) reuse</p>
                    </span>
                </div>`);
        }
      });
  }

  function show_details(data, caller = "") {
    let html = `<table class="table table-hover" style="width:100%;">`;
    if (caller == "Diagnosis") {
      html += `
            <colgroup>
                <col width="5%">
                <col width=17%">
                <col width="10%">
                <col width="26%">
                <col width="22%">
                <col width="20%">
            </colgroup>
            <tr>
                <th><input type="checkbox" id="th" class="check-all" style="border: 2px solid black;"/></th>
                <th style="background-color: #D3D3D3;">Medical Code</th>
                <th style="background-color: #D3D3D3;">Code Name</th>
                <th style="background-color: #D3D3D3;">Description</th>
                <th style="background-color: #D3D3D3;">Mtuha</th>
                <th style="background-color: #D3D3D3;">Date of Service</th>
            </tr>`;

      data.forEach((row) => {
        html += `<tr>
                        <td><input type="checkbox"/></td>
                        <td id="item" data-item="${row.item}">${row.item}</td>
                        <td id="item_name" data-item_name="${row.item_name}">${
          row.item_name
        }</td>
                        <td id="description" data-description="${
                          row.description
                        }">${row.description}</td>
                        <td id="mtuha" data-mtuha="${row.mtuha}">${
          row.mtuha
        }</td>
                        <td id="date" data-date="${frappe.datetime.get_datetime_as_string(
                          row.date
                        )}">${frappe.datetime.get_datetime_as_string(
          row.date
        )}</td>
                    </tr>`;
      });
    } else if (caller == "Medication") {
      html += `
            <colgroup>
                <col width="5%">
                <col width=20%">
                <col width="1%">
                <col width="30%">
                <col width="10%">
                <col width=10%">
                <col width="5%">
                <col width="19%">
            </colgroup>
            <tr>
                <th><input type="checkbox" id="th" class="check-all" style="border: 2px solid black;" /></th>
                <th style="background-color: #D3D3D3;">Item</th>
                <th style="background-color: #D3D3D3;"></th>
                <th style="background-color: #D3D3D3;">Medical Code</th>
                <th style="background-color: #D3D3D3;">Dosage</th>
                <th style="background-color: #D3D3D3;">Period</th>
                <th style="background-color: #D3D3D3;">Qty</th>
                <th style="background-color: #D3D3D3;">ServiceDate</th>
            </tr>`;

      data.forEach((row) => {
        let quantity = row.quantity - row.quantity_returned;
        html += `<tr>
                        <td><input type="checkbox"/></td>
                        <td id="item" data-item="${row.item}">${row.item}</td>
                        <td id="item_name" data-item_name="${
                          row.item_name
                        }"></td>
                        <td id="medical_code" data-medical_code="${
                          row.medical_code
                        }">${row.medical_code}</td>
                        <td id="dosage" data-dosage="${row.dosage}">${
          row.dosage
        }</td>
                        <td id="period" data-period="${row.period}">${
          row.period
        }</td>
                        <td id="quantity" data-quantity="${quantity}">${quantity}</td>
                        <td id="date" data-date="${frappe.datetime.get_datetime_as_string(
                          row.date
                        )}">${frappe.datetime.get_datetime_as_string(
          row.date
        )}</td>
                    </tr>`;
      });
    } else {
      html += `
            <colgroup>
                <col width="5%">
                <col width=30%">
                <col width="35%">
                <col width="30%">
            </colgroup>
            <tr>
                <th><input type="checkbox" id="th" class="check-all" style="border: 2px solid black;" /></th>
                <th style="background-color: #D3D3D3;">Item</th>
                <th style="background-color: #D3D3D3;">Item Name</th>
                <th style="background-color: #D3D3D3;">Date of Service</th>
            </tr>`;

      data.forEach((row) => {
        html += `<tr>
                        <td><input type="checkbox"/></td>
                        <td id="item" data-item="${row.item}">${row.item}</td>
                        <td id="item_name" data-item_name="${row.item_name}">${
          row.item_name
        }</td>
                        <td id="date" data-date="${frappe.datetime.get_datetime_as_string(
                          row.date
                        )}">${frappe.datetime.get_datetime_as_string(
          row.date
        )}</td>
                    </tr>`;
      });
    }
    html += `</table>`;
    return html;
  }
};

function set_delete_button_in_child_table(frm, child_table_fields) {
  if (frm.doc.docstatus != 0) {
    return;
  }
  $.each(child_table_fields, function (i, child_table_field) {
    if (frm.fields_dict[child_table_field]) {
      $.each(
        frm.fields_dict[child_table_field].grid.grid_rows,
        function (i, row) {
          if (!row.doc.__islocal) {
            if (!row.wrapper.find(".grid-row-delete").length) {
              $(row.wrapper)
                .find(".grid-row-check")
                .after(
                  '<button class="btn btn-default btn-xs grid-row-delete" style="margin-left: 5px;"><i class="fa fa-trash-o text-danger"></i></button>'
                );
              row.wrapper.find(".grid-row-delete").on("click", function () {
                frappe.model.clear_doc(row.doc.doctype, row.doc.name);
                row.remove();
              });
            }
          }
        }
      );
    }
  });
}

var auto_calculate_drug_quantity = (frm, drug_item) => {
  frappe
    .call({
      method: "hms_tz.nhif.api.healthcare_utils.get_drug_quantity",
      args: {
        drug_item: drug_item,
      },
    })
    .then((r) => {
      frappe.model.set_value(
        drug_item.doctype,
        drug_item.name,
        "quantity",
        r.message
      );
    });
};

var set_empty_row_on_all_child_tables = (frm) => {
  let table_fieldnames = [
    "system_and_symptoms",
    "patient_encounter_preliminary_diagnosis",
    "lab_test_prescription",
    "radiology_procedure_prescription",
    "patient_encounter_final_diagnosis",
    "procedure_prescription",
    "therapies",
    "diet_recommendation",
  ];

  table_fieldnames.forEach((fieldname) => {
    frm.fields_dict[fieldname].grid.add_new_row();
  });
};

var control_practitioners_to_submit_others_encounters = (frm) => {
  if (
    frm.doc.encounter_category != "Direct Cash" &&
    !frm.doc.inpatient_record
  ) {
    frappe.db
      .get_single_value(
        "Healthcare Settings",
        "allow_practitioner_to_take_other_encounters"
      )
      .then((value) => {
        if (value == 0) {
          frappe.db
            .get_value(
              "Healthcare Practitioner",
              { user_id: frappe.session.user },
              "name"
            )
            .then((r) => {
              let practitioner = r.message;

              if (
                practitioner.name &&
                practitioner.name != frm.doc.practitioner
              ) {
                frm.set_intro("");
                frm.disable_form();
                frm.set_read_only();
                frm.clear_custom_buttons();
                frm.toggle_display(
                  [
                    "section_break_28",
                    "sb_test_prescription",
                    "radiology_procedures_section",
                    "sb_procedures",
                    "medication_action_sb",
                    "sb_drug_prescription",
                    "rehabilitation_section",
                    "diet_recommendation_section",
                    "examination_detail",
                  ],
                  false
                );
                frm.toggle_enable(
                  [
                    "system_and_symptoms",
                    "patient_encounter_preliminary_diagnosis",
                    "lab_test_prescription",
                    "radiology_procedure_prescription",
                    "patient_encounter_final_diagnosis",
                    "procedure_prescription",
                    "drug_prescription",
                    "therapies",
                    "diet_recommendation",
                  ],
                  true
                );
                frm.set_intro(
                  __("This is not your encounter so cannot be edited."),
                  true
                );
              }
            });
        }
      });
  }
};

var validate_medication_class = (frm, drug_item) => {
  frappe
    .call({
      method: "hms_tz.nhif.api.patient_encounter.validate_medication_class",
      args: {
        company: frm.doc.company,
        encounter: frm.doc.name,
        patient: frm.doc.patient,
        drug_item: drug_item,
        caller: "Front End",
      },
    })
    .then((r) => {
      if (r.message) {
        let data = r.message;
        frappe.show_alert(
          {
            message: __(
              `<p class="text-left">Item: <strong>${__(
                data.drug_item
              )}</strong>
                    with same Medication Class ${__(data.medication_class)}\
                    was lastly prescribed on: <strong>${__(
                      data.prescribed_date
                    )}</strong><br>\
                    Therefore item with same <b>medication class</b> were suppesed to be\
                    prescribed after: <strong>${__(
                      data.valid_days
                    )}</strong> days
                    </p>`
            ),
            indicator: "red",
            title: __("Medication Class Validation"),
          },
          30
        );
      }
    });
};

var validate_healthcare_package_order_items = (frm) => {
  if (frm.doc.healthcare_package_order) {
    for (let field of [
      "lab_test_prescription",
      "radiology_procedure_prescription",
      "procedure_prescription",
      "therapies",
      "drug_prescription",
    ]) {
      frm.get_field(field).grid.cannot_add_rows = true;
      frm.set_df_property(field, "read_only", 1);
    }
  }
};

var filter_drug_prescriptions = (frm) => {
  frappe.db
    .get_value(
      "HMS TZ Setting",
      frm.doc.company,
      "allow_filtered_medication_on_patient_encounter"
    )
    .then((r) => {
      if (r.message.allow_filtered_medication_on_patient_encounter == 1) {
        frm.set_query("drug_code", "drug_prescription", function () {
          return {
            query: "hms_tz.nhif.api.patient_encounter.get_filterd_drug",
            filters: {
              price_list: frm.doc.price_list,
              disabled: 0,
            },
          };
        });
      } else {
        frm.set_query("drug_code", "drug_prescription", function () {
          return {
            filters: {
              disabled: 0,
            },
          };
        });
      }
    });
};

var add_patient_history_btn = (frm) => {
  if (!frm.page.fields_dict.patient_history) {
    frm.page
      .add_field({
        label: __("Patient History"),
        fieldname: "patient_history",
        fieldtype: "Button",
        click: function () {
          if (frm.doc.patient) {
            frappe.route_options = { patient: frm.doc.patient };
            frappe.set_route("tz-patient-history");
          } else {
            frappe.msgprint(__("Please select Patient"));
          }
        },
      })
      .$input.addClass("btn-sm");
  }
};

var add_refer_practtitioner_btn = (frm) => {
  if (
    frm.doc.docstatus == 1 &&
    frm.doc.encounter_type != "Final" &&
    frm.doc.duplicated == 0
  ) {
    if (!frm.page.fields_dict.referring_practitioner) {
      frm.page
        .add_field({
          label: __("Refer Practitioner"),
          fieldname: "referring_practitioner",
          fieldtype: "Button",
          click: function () {
            refer_practitioner(frm);
          },
        })
        .$input.addClass("btn-sm");
    }
  }
};

var nhif_btns = (frm) => {
  if (!frappe.user.has_role("Healthcare Practitioner")) {
    return;
  }

  if (
    !frm.doc.insurance_company ||
    !frm.doc.insurance_company.includes("NHIF")
  ) {
    return;
  }

  frappe.call({
    method:
      "hms_tz.nhif.api.healthcare_practitioner.get_nhif_practitioner_login_status",
    args: {},
    callback: (r) => {
      let data = r.message;
      if (data.show_login) {
        login_to_nhif(frm);

        frm.set_intro("");
        frm.disable_form();
        frm.set_read_only();
        frm.toggle_display(
          [
            "section_break_28",
            "hms_tz_section_break",
            "sb_test_prescription",
            "radiology_procedures_section",
            "sb_procedures",
            "medication_action_sb",
            "sb_drug_prescription",
            "rehabilitation_section",
            "diet_recommendation_section",
            "examination_detail",
            "copy_from_preliminary_diagnosis",
          ],
          false
        );
        frm.toggle_enable(
          [
            "system_and_symptoms",
            "patient_encounter_preliminary_diagnosis",
            "lab_test_prescription",
            "radiology_procedure_prescription",
            "patient_encounter_final_diagnosis",
            "procedure_prescription",
            "drug_prescription",
            "therapies",
            "diet_recommendation",
            "copy_from_preliminary_diagnosis",
          ],
          false
        );
        frm.set_intro(
          __(
            `<h5 style="text-align: center; color: #ff7421;">Please login to NHIF first!</h5>`
          ),
          "orange"
        );
      }

      if (data.show_logout) {
        logout_from_nhif(frm);
      }

      if (data.show_poc) {
        pre_approval_btn(frm);
        cancel_pre_approval_btn(frm);
        confirm_poc_btn(frm);
      }
    },
  });
};

var jubilee_btns = (frm) => {
  if (!frappe.user.has_role("Healthcare Practitioner")) {
    return;
  }

  if (
    !frm.doc.insurance_company ||
    !frm.doc.insurance_company.includes("Jubilee")
  ) {
    return;
  }

  verify_services_btn(frm);
};

var login_to_nhif = (frm) => {
  if (!frm.page.fields_dict.login_to_nhif) {
    frm.page
      .add_field({
        label: __("Login To NHIF"),
        fieldname: "login_to_nhif",
        fieldtype: "Button",
        click: async function () {
          let dialog = new frappe.ui.Dialog({
            title: __("<h4>Login To NHIF</h4>"),
            // width: 150,
            fields: [
              {
                fieldtype: "Select",
                label: "Biometric Method",
                fieldname: "biometric_method",
                options: [
                  { value: "FINGERPRINT", label: __("FINGERPRINT") },
                  { value: "FACIAL", label: __("FACIAL") },
                  // { value: "NONE", label: __("NONE") },
                ],
                default: "FINGERPRINT",
                reqd: 1,
              },
            ],
            size: "small",
            primary_action_label: __("Next"),
            primary_action: async () => {
              let biometricData;
              let values = dialog.get_values();
              dialog.hide();

              if (values.biometric_method === "FACIAL") {
                biometricData = await new FacialRecognition({
                  label: "Login To NHIF",
                });
                if (!biometricData) {
                  frappe.msgprint(
                    __("Face capture failed. Please try again.")
                  );
                  return;
                }
              } else if (values.biometric_method === "FINGERPRINT") {
                biometricData = await new Fingerprint({
                  label: "Login To NHIF",
                });
                if (!biometricData) {
                  frappe.msgprint(
                    __("Fingerprint capture failed. Please try again.")
                  );
                  return;
                }
              } else {
                const confirmed = await new Promise((resolve) => {
                  frappe.confirm(
                    __(`
                      <div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
                      <p class="text-center"><i>Biometric Method: <b>${values.biometric_method}</b> is only used when Patient is not able to take fingerprint or face.</i></p>
                      </div>
                      <br>
                      <p class="text-center"><i>Are you sure you want to continue?</i></p>`),
                    () => resolve(true),
                    () => resolve(false)
                  );
                });

                if (!confirmed) {
                  return;
                }

                biometricData = { Data: "", fpCode: "" };
              }

              frappe.call({
                method: "hms_tz.nhif.nhif_api.attendance.login_practitioner",
                args: {
                  fingerprint: biometricData.Data,
                  fpcode: biometricData.fpCode,
                },
                async: true,
                freeze: true,
                freeze_message: __(
                  '<i class="fa fa-spinner fa-spin fa-4x"></i>'
                ),
                callback: function (data) {
                  if (data.message && data.message !== "Error") {
                    frappe.utils.play_sound("submit");
                  } else {
                    frappe.utils.play_sound("error");
                  }
                },
                onerror: function (data) {
                  frappe.utils.play_sound("error");
                },
              });
            },
          });
          dialog.show();
        },
      })
      .$input.addClass("btn-sm");
  }
};

var logout_from_nhif = (frm) => {
  if (!frm.page.fields_dict.logout_from_nhif) {
    frm.page
      .add_field({
        label: __("Logout From NHIF"),
        fieldname: "logout_from_nhif",
        fieldtype: "Button",
        click: function () {
          frappe.call({
            method: "hms_tz.nhif.nhif_api.attendance.logout_practitioner",
            args: {},
            async: true,
            freeze: true,
            freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
            callback: function (data) {
              if (data.message && data.message !== "Error") {
                frappe.utils.play_sound("submit");
              } else {
                frappe.utils.play_sound("error");
              }
            },
            onerror: function (data) {
              frappe.utils.play_sound("error");
            },
          });
        },
      })
      .$input.addClass("btn-sm");
  }
};

var pre_approval_btn = (frm) => {
  if (!frm.page.fields_dict.pre_approval_btn) {
    frm.page
      .add_field({
        label: __("Get PreApproval"),
        fieldname: "pre_approval_btn",
        fieldtype: "Button",
        click: function () {
          if (frm.is_dirty()) {
            frappe.msgprint(
              "<b>Please save the form before requesting pre-approval</b>"
            );
            return;
          }

          frappe.call({
            method:
              "hms_tz.nhif.nhif_api.pre_approval.get_service_preapproval",
            args: {
              ref_doctype: frm.doc.doctype,
              ref_docname: frm.doc.name,
            },
            async: true,
            freeze: true,
            freeze_message: __('<i class="fa fa-spinner fa-spin fa-4x"></i>'),
            callback: function (data) {
              if (data.message && data.message !== "Error") {
                frappe.utils.play_sound("submit");
                frm.reload_doc();
                frappe.show_alert(
                  {
                    message: __("Pre-Approval request were successful"),
                    indicator: "green",
                  },
                  10
                );
              } else {
                frappe.utils.play_sound("error");
              }
            },
            onerror: function (data) {
              frappe.utils.play_sound("error");
            },
          });
        },
      })
      .$input.addClass("btn-sm");
  }
};

var cancel_pre_approval_btn = (frm) => {
  if (!frm.page.fields_dict.cancel_pre_approval_btn) {
    frm.page
      .add_field({
        label: __("Cancel PreApproval"),
        fieldname: "cancel_pre_approval_btn",
        fieldtype: "Button",
        click: function () {
          if (frm.is_dirty()) {
            frappe.msgprint(
              "<b>Please save the form before canceling pre-approval</b>"
            );
            return;
          }

          frappe.prompt(
            [
              {
                label: "Pre-Approval No",
                fieldname: "preapproval_no",
                fieldtype: "Data",
                reqd: 1,
              },
              {
                label: "Remarks",
                fieldname: "remarks",
                fieldtype: "Small Text",
                reqd: 1,
              },
            ],
            (values) => {
              frappe.call({
                method: "hms_tz.nhif.nhif_api.pre_approval.cancel_preapproval",
                args: {
                  ref_doctype: frm.doc.doctype,
                  ref_docname: frm.doc.name,
                  preapproval_no: values.preapproval_no,
                  remarks: values.remarks,
                },
                async: true,
                freeze: true,
                freeze_message: __(
                  '<i class="fa fa-spinner fa-spin fa-4x"></i>'
                ),
                callback: function (data) {
                  if (data.message && data.message !== "Error") {
                    frappe.utils.play_sound("submit");
                    frm.reload_doc();
                    frappe.show_alert(
                      {
                        message: __(
                          "Pre-Approval request canceled successfully"
                        ),
                        indicator: "green",
                      },
                      10
                    );
                  } else {
                    frappe.utils.play_sound("error");
                  }
                },
                onerror: function (data) {
                  frappe.utils.play_sound("error");
                },
              });
            }
          );
        },
      })
      .$input.addClass("btn-sm");
  }
};

var confirm_poc_btn = (frm) => {
  if (!frm.page.fields_dict.confirm_poc_btn && !frm.doc.poc_reference_no) {
    frm.page
      .add_field({
        label: __("Confirm POC"),
        fieldname: "confirm_poc_btn",
        fieldtype: "Button",
        click: async function () {
          let dialog = new frappe.ui.Dialog({
            title: __("<h4>Point of Care Confirmation</h4>"),
            // width: 150,
            fields: [
              {
                fieldtype: "Select",
                label: "Biometric Method",
                fieldname: "biometric_method",
                options: [
                  { value: "FINGERPRINT", label: __("FINGERPRINT") },
                  { value: "FACIAL", label: __("FACIAL") },
                  { value: "NONE", label: __("NONE") },
                ],
                default: "FINGERPRINT",
                reqd: 1,
              },
            ],
            size: "small",
            primary_action_label: __("Next"),
            primary_action: async () => {
              let biometricData;
              let values = dialog.get_values();
              dialog.hide();

              if (values.biometric_method === "FACIAL") {
                biometricData = await new FacialRecognition({
                  label: "Confirm POC",
                });
                if (!biometricData) {
                  frappe.msgprint(
                    __("Face capture failed. Please try again.")
                  );
                  return;
                }
              } else if (values.biometric_method === "FINGERPRINT") {
                biometricData = await new Fingerprint({
                  label: "Confirm POC",
                });
                if (!biometricData) {
                  frappe.msgprint(
                    __("Fingerprint capture failed. Please try again.")
                  );
                  return;
                }
              } else {
                const confirmed = await new Promise((resolve) => {
                  frappe.confirm(
                    __(`
                      <div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
                      <p class="text-center"><i>Biometric Method: <b>${values.biometric_method}</b> is only used when Patient is not able to take fingerprint or face.</i></p>
                      </div>
                      <br>
                      <p class="text-center"><i>Are you sure you want to continue?</i></p>`),
                    () => resolve(true),
                    () => resolve(false)
                  );
                });

                if (!confirmed) {
                  return;
                }

                biometricData = { Data: "", fpCode: "" };
              }

              frappe.call({
                method:
                  "hms_tz.nhif.nhif_api.verification.get_poc_reference_no",
                args: {
                  point_of_care: "Consultation",
                  practitioner: frm.doc.practitioner,
                  fingerprint: biometricData.Data,
                  fpcode: biometricData.fpCode,
                  biometric_method: values.biometric_method,
                  company: frm.doc.company,
                  appointment_id: frm.doc.appointment,
                  ref_doctype: frm.doc.doctype,
                  ref_docname: frm.doc.name,
                },
                async: true,
                freeze: true,
                freeze_message: __(
                  '<i class="fa fa-spinner fa-spin fa-4x"></i>'
                ),
                callback: function (r) {
                  if (r.message && r.message !== "Error") {
                    frappe.utils.play_sound("submit");

                    const data = r.message;
                    frappe.model.set_value(
                      frm.doc.doctype,
                      frm.doc.name,
                      "poc_reference_no",
                      data.ReferenceNo
                    );
                  } else {
                    frappe.utils.play_sound("error");
                  }
                },
                onerror: function (data) {
                  frappe.utils.play_sound("error");
                },
              });
            },
          });

          dialog.show();
        },
      })
      .$input.addClass("btn-sm");
  }
};

var verify_services_btn = (frm) => {
  if (!frm.page.fields_dict.verify_services_btn) {
    frm.page.add_field({
      label: "Get PreApproval",
      fieldname: "verify_services_btn",
      fieldtype: "Button",
      click: async () => {
        if (frm.is_dirty()) {
          frappe.msgprint(
            "<b>Please save the form before verifying services</b>"
          );
          return;
        }

        if (!frm.doc.jubilee_procedure) {
          frm.scroll_to_field("jubilee_procedure");
          frm.toggle_reqd("jubilee_procedure", true);
          frappe.show_alert(
            {
              message: __(
                "Please select Jubilee Procedure before verifying services"
              ),
              indicator: "red",
            },
            10
          );
          return;
        }

        frappe.prompt(
          [
            {
              label: "Jubilee Benefit",
              fieldname: "benefit_id",
              fieldtype: "Link",
              options: "Jubilee Benefit",
              reqd: 1,
              get_query: () => {
                return {
                  filters: {
                    appointment: frm.doc.appointment,
                  },
                };
              },
            },
            {
              label: "Benefit Name",
              fieldname: "benefit_name",
              fieldtype: "Data",
              read_only: 1,
              fetch_from: "benefit_id.benefit_name",
              depends_on: "benefit_id",
            },
            {
              label: "Benefit Code",
              fieldname: "benefit_code",
              fieldtype: "Data",
              read_only: 1,
              fetch_from: "benefit_id.benefit_code",
              depends_on: "benefit_id",
            },
          ],
          (values) => {
            frappe.call({
              method: "hms_tz.jubilee.api.api.verify_jubilee_services",
              args: {
                source_doctype: frm.doc.doctype,
                source_docname: frm.doc.name,
                benefit_code: values.benefit_code,
              },
              async: true,
              freeze: true,
              freeze_message: __(
                '<i class="fa fa-spinner fa-spin fa-4x"></i>'
              ),
              callback: function (r) {
                if (r.message === true) {
                  frappe.utils.play_sound("submit");
                  frm.reload_doc();
                  frappe.show_alert(
                    {
                      message: __("Services verified successfully"),
                      indicator: "green",
                    },
                    10
                  );
                } else if (
                  r.message &&
                  r.message.action === "PreAuthRequired"
                ) {
                  frappe.utils.play_sound("error");
                  show_preauth_dialog(frm, r.message);
                } else {
                  frappe.utils.play_sound("error");
                }
              },
              onerror: function (data) {
                frappe.utils.play_sound("error");
              },
            });
          }
        );
      },
    });
  }
};

function show_preauth_dialog(frm, data) {
  const d = new frappe.ui.Dialog({
    title: __("Jubilee: Pre-Authorization Required"),
    indicator: "orange",
    fields: [
      {
        fieldtype: "HTML",
        fieldname: "message_html",
        options: `
          <div style="border-left: 4px solid #ffc107; background-color: #fff3cd;
                      padding: 15px; border-radius: 10px;
                      box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin: 10px 0;">
            <p style="font-size: 16px; font-weight: bold;">⚠️ ${data.description}</p>
            <p style="font-size: 14px;">
              The total amount of the services exceeds the patient's daily balance.
            </p>
            <p style="font-size: 14px;">
              Click <b>"Request Pre-Auth"</b> to submit this encounter and send a
              pre-authorization request to Jubilee.
            </p>
            <p style="font-size: 14px;">
              Please tell the patient to proceed to the <b>Billing Team</b>.
              Jubilee usually responds within <b>15 minutes</b>.
            </p>
          </div>
        `,
      },
    ],
    primary_action_label: __("Request Pre-Auth"),
    primary_action: () => {
      d.hide();
      frappe.call({
        method: "hms_tz.jubilee.api.preauthorization.request_preauthorization",
        args: {
          source_doctype: data.source_doctype,
          source_docname: data.source_docname,
          benefit_code: data.benefit_code,
        },
        freeze: true,
        freeze_message: __(
          '<div style="text-align:center;">' +
            '<i class="fa fa-spinner fa-spin fa-4x"></i>' +
            "<p style='margin-top:15px; font-size:16px;'>Submitting encounter and sending Pre-Authorization to Jubilee…</p>" +
            "</div>"
        ),
        callback: (r) => {
          const result = r.message || {};
          const service_request_link = result.service_request
            ? `<a href="/app/healthcare-service-request/${result.service_request}">${result.service_request}</a>`
            : "N/A";

          if (result.status === "OK") {
            frappe.utils.play_sound("submit");
            // <p style="font-size: 16px; font-weight: bold;">✅ Pre-Authorization Request Sent</p>
            frappe.msgprint({
              title: __("Pre-Authorization Request Sent"),
              indicator: "green",
              message: `
                <div style="border-left: 4px solid #28a745; background-color: #d4edda;
                            padding: 15px; border-radius: 10px;
                            box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin: 10px 0;">

                  <p style="font-size: 14px;">Submission ID: <b>${
                    result.submission_id || "N/A"
                  }</b></p>
                  <p style="font-size: 14px;">Service Request: <b>${service_request_link}</b></p>
                  <p style="font-size: 14px;">Jubile Response: ${
                    result.description || ""
                  }</p>
                  <p style="font-size: 14px;"><b>Please send the patient to the Billing Team</b>.</p>
                </div>
              `,
            });
          } else {
            frappe.utils.play_sound("error");
            frappe.msgprint({
              title: __("Pre-Authorization Failed"),
              indicator: "red",
              message: `
                <div style="border-left: 4px solid #dc3545; background-color: #f8d7da;
                            padding: 15px; border-radius: 10px;
                            box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin: 10px 0;">
                  <p style="font-size: 16px; font-weight: bold;">❌ Pre-Authorization Failed</p>
                  <p style="font-size: 14px;">Status: <b>${
                    result.status || "ERROR"
                  }</b></p>
                  <p style="font-size: 14px;">Response: <b>${
                    result.description || "Unknown error"
                  }</b></p>
                  <p style="font-size: 14px;">Service Request: <b>${service_request_link}</b></p>
                  <p style="font-size: 14px;">
                    The encounter was submitted and the Service Request was created.
                    Open it and click <b>Send Pre-Auth</b> to retry.
                  </p>
                </div>
              `,
            });
          }

          frm.reload_doc();
        },
        onerror: function () {
          frappe.utils.play_sound("error");
          frappe.msgprint({
            title: __("Pre-Authorization Error"),
            indicator: "red",
            message: __(
              "An unexpected error occurred while sending the pre-authorization request. Please check the error log."
            ),
          });
        },
      });
    },
    secondary_action_label: __("Cancel"),
    secondary_action: () => d.hide(),
  });

  d.show();
}
