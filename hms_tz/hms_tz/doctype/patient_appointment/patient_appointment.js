// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt
frappe.provide("erpnext.queries");
frappe.ui.form.on("Patient Appointment", {
  setup: function (frm) {
    frm.custom_make_buttons = {
      "Vital Signs": "Vital Signs",
      "Patient Encounter": "Patient Encounter",
    };
  },

  onload: function (frm) {
    if (frm.is_new()) {
      frm.set_value("appointment_time", null);
      frm.disable_save();
    }
    if (frm.doc.source) {
      set_source_referring_practitioner(frm);
    }
  },

  refresh: function (frm) {
    frm.set_query("patient", function () {
      return {
        filters: { status: "Active" },
      };
    });
    frm.set_query("practitioner", function () {
      return {
        filters: {
          department: frm.doc.department,
          practitioner_role: "Doctor",
        },
      };
    });
    frm.set_query("service_unit", function () {
      return {
        filters: {
          is_group: false,
          allow_appointments: true,
          company: frm.doc.company,
        },
      };
    });
    frm.set_query("radiology_examination_template", function () {
      return {
        filters: {
          modality_type: frm.doc.modality_type || "",
        },
      };
    });

    frm.set_query("referring_practitioner", function () {
      if (frm.doc.source == "External Referral") {
        return {
          filters: {
            healthcare_practitioner_type: "External",
            practitioner_role: "Doctor",
          },
        };
      } else {
        return {
          filters: {
            healthcare_practitioner_type: "Internal",
            practitioner_role: "Doctor",
          },
        };
      }
    });

    if (frm.doc.patient && frappe.user.has_role("Healthcare Receptionist")) {
      frm.add_custom_button(__("Itemized Bill"), function () {
        frappe.route_options = {
          patient: frm.doc.patient,
          patient_appointment: frm.doc.name,
        };
        frappe.set_route("query-report", "Itemized Bill Report");
      });
    }

    if (frm.doc.patient) {
      frm.add_custom_button(
        __("Patient History"),
        function () {
          frappe.route_options = { patient: frm.doc.patient };
          frappe.set_route("tz-patient-history");
        },
        __("View")
      );
    }

    if (frm.doc.__onload?.is_cancellable) {
      frm.add_custom_button(__("Cancel"), function () {
        update_status(frm, "Cancelled");
      });
    }

    if (
      frm.doc.status == "Open" ||
      (frm.doc.status == "Scheduled" && !frm.doc.__islocal)
    ) {
      if (frm.doc.procedure_template) {
        frm.add_custom_button(
          __("Clinical Procedure"),
          function () {
            frappe.model.open_mapped_doc({
              method:
                "healthcare.healthcare.doctype.clinical_procedure.clinical_procedure.make_procedure",
              frm: frm,
            });
          },
          __("Create")
        );
      } else if (frm.doc.therapy_type) {
        frm.add_custom_button(
          __("Therapy Session"),
          function () {
            frappe.model.open_mapped_doc({
              method:
                "hms_tz.hms_tz.doctype.therapy_session.therapy_session.create_therapy_session",
              frm: frm,
            });
          },
          "Create"
        );
      } else if (frm.doc.radiology_examination_template) {
        frm.add_custom_button(
          __("Radiology Examination"),
          function () {
            create_radiology_exam(frm);
          },
          "Create"
        );
      } else {
        frm.add_custom_button(
          __("Patient Encounter"),
          function () {
            frappe.model.open_mapped_doc({
              method:
                "hms_tz.hms_tz.doctype.patient_appointment.patient_appointment.make_encounter",
              frm: frm,
            });
          },
          __("Create")
        );
      }

      frm.add_custom_button(
        __("Vital Signs"),
        function () {
          create_vital_signs(frm);
        },
        __("Create")
      );
    }
    frm.set_query("insurance_subscription", function () {
      return {
        filters: {
          patient: frm.doc.patient,
          docstatus: 1,
          is_active: 1,
        },
      };
    });
  },

  patient: function (frm) {
    if (frm.doc.patient) {
      frm.trigger("toggle_payment_fields");
    } else {
      frm.set_value("patient_name", "");
      frm.set_value("patient_sex", "");
      frm.set_value("patient_age", "");
      frm.set_value("inpatient_record", "");
    }
  },

  therapy_type: function (frm) {
    if (frm.doc.therapy_type) {
      frappe.db.get_value(
        "Therapy Type",
        frm.doc.therapy_type,
        "default_duration",
        (r) => {
          if (r.default_duration) {
            frm.set_value("duration", r.default_duration);
          }
        }
      );
    }
  },

  service_unit: function (frm) {
    if (!frm.doc.service_unit) {
      frm.set_value("modality_type", "");
      frm.set_value("patient_name", "");
    }
    if (frm.doc.service_unit) {
      frappe.db.get_value(
        "Healthcare Service Unit",
        frm.doc.service_unit,
        "company",
        function (r) {
          if (r && r.company) {
            frm.set_value("company", r.company);
          }
        }
      );
    }
  },

  get_procedure_from_encounter: function (frm) {
    get_prescribed_procedure(frm);
  },

  get_ordered_radiology_procedures: function (frm) {
    get_radiology_prescribed(frm);
  },

  radiology_examination_template: function (frm) {
    if (frm.doc.radiology_examination_template) {
      frm.set_df_property("service_unit", "reqd", true);
    } else {
      frm.set_df_property("service_unit", "reqd", false);
    }
  },

  toggle_payment_fields: function (frm) {
    frappe.call({
      method:
        "hms_tz.hms_tz.doctype.patient_appointment.patient_appointment.check_payment_fields_reqd",
      args: { patient: frm.doc.patient },
      callback: function (data) {
        if (data.message.fee_validity) {
          // if fee validity exists and automated appointment invoicing is enabled,
          // show payment fields as non-mandatory
          frm.toggle_display("mode_of_payment", 0);
          frm.toggle_display("paid_amount", 0);
          frm.toggle_reqd("mode_of_payment", 0);
          frm.toggle_reqd("paid_amount", 0);
        } else {
          // if automated appointment invoicing is disabled, hide fields
          frm.toggle_display("mode_of_payment", data.message ? 1 : 0);
          frm.toggle_display("paid_amount", data.message ? 1 : 0);
          frm.toggle_reqd("mode_of_payment", data.message ? 1 : 0);
          frm.toggle_reqd("paid_amount", data.message ? 1 : 0);
        }
      },
    });
  },

  get_prescribed_therapies: function (frm) {
    if (frm.doc.patient) {
      frappe.call({
        method:
          "hms_tz.hms_tz.doctype.patient_appointment.patient_appointment.get_prescribed_therapies",
        args: { patient: frm.doc.patient },
        callback: function (r) {
          if (r.message) {
            show_therapy_types(frm, r.message);
          } else {
            frappe.msgprint({
              title: __("Not Therapies Prescribed"),
              message: __(
                "There are no Therapies prescribed for Patient {0}",
                [frm.doc.patient.bold()]
              ),
              indicator: "blue",
            });
          }
        },
      });
    }
  },

  source: function (frm) {
    if (frm.doc.source) {
      set_source_referring_practitioner(frm);
    }
  },
});

let get_prescribed_procedure = function (frm) {
  if (frm.doc.patient) {
    frappe.call({
      method:
        "hms_tz.hms_tz.doctype.patient_appointment.patient_appointment.get_procedure_prescribed",
      args: { patient: frm.doc.patient },
      callback: function (r) {
        if (r.message && r.message.length) {
          show_procedure_templates(frm, r.message);
        } else {
          frappe.msgprint({
            title: __("Not Found"),
            message: __(
              "No Prescribed Procedures found for the selected Patient"
            ),
          });
        }
      },
    });
  } else {
    frappe.msgprint({
      title: __("Not Allowed"),
      message: __("Please select a Patient first"),
    });
  }
};

let show_procedure_templates = function (frm, result) {
  let d = new frappe.ui.Dialog({
    title: __("Prescribed Procedures"),
    fields: [
      {
        fieldtype: "HTML",
        fieldname: "procedure_template",
      },
    ],
  });
  let html_field = d.fields_dict.procedure_template.$wrapper;
  html_field.empty();
  $.each(result, function (x, y) {
    let row = $(
      repl(
        '<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-5"> %(encounter)s <br> %(consulting_practitioner)s <br> %(encounter_date)s </div>\
		<div class="col-xs-5"> %(procedure_template)s <br>%(practitioner)s  <br> %(date)s</div>\
		<div class="col-xs-2">\
		<a data-name="%(name)s" data-procedure-template="%(procedure_template)s"\
		data-encounter="%(encounter)s" data-practitioner="%(practitioner)s"\
		data-date="%(date)s" data-department="%(department)s" data-source="%(source)s"\
		data-referring-practitioner="%(referring_practitioner)s"> <button class="btn btn-default btn-xs">Add\
		</button></a></div></div><div class="col-xs-12"><hr/><div/>',
        {
          name: y[0],
          procedure_template: y[1],
          encounter: y[2],
          consulting_practitioner: y[3],
          encounter_date: y[4],
          practitioner: y[5] ? y[5] : "",
          date: y[6] ? y[6] : "",
          department: y[7] ? y[7] : "",
          source: y[8] ? y[8] : "",
          referring_practitioner: y[9] ? y[9] : "",
        }
      )
    ).appendTo(html_field);
    row.find("a").click(function () {
      frm.doc.procedure_template = $(this).attr("data-procedure-template");
      frm.doc.procedure_prescription = $(this).attr("data-name");
      frm.doc.practitioner = $(this).attr("data-practitioner");
      frm.doc.appointment_date = $(this).attr("data-date");
      frm.doc.department = $(this).attr("data-department");
      frm.doc.source = $(this).attr("data-source");
      frm.set_df_property("source", "read_only", 1);
      frm.doc.referring_practitioner = $(this).attr(
        "data-referring-practitioner"
      );
      if (frm.doc.referring_practitioner) {
        frm.set_df_property("referring_practitioner", "hidden", 0);
        frm.set_df_property("referring_practitioner", "read_only", 1);
      }
      frm.refresh_field("procedure_template");
      frm.refresh_field("procedure_prescription");
      frm.refresh_field("appointment_date");
      frm.refresh_field("practitioner");
      frm.refresh_field("department");
      frm.refresh_field("source");
      frm.refresh_field("referring_practitioner");
      d.hide();
      return false;
    });
  });
  if (!result) {
    let msg = __("There are no procedure prescribed for ") + frm.doc.patient;
    $(
      repl(
        '<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>',
        { msg: msg }
      )
    ).appendTo(html_field);
  }
  d.show();
};

let show_therapy_types = function (frm, result) {
  var d = new frappe.ui.Dialog({
    title: __("Prescribed Therapies"),
    fields: [
      {
        fieldtype: "HTML",
        fieldname: "therapy_type",
      },
    ],
  });
  var html_field = d.fields_dict.therapy_type.$wrapper;
  $.each(result, function (x, y) {
    var row = $(
      repl(
        '<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-5"> %(encounter)s <br> %(practitioner)s <br> %(date)s </div>\
		<div class="col-xs-5"> %(therapy)s </div>\
		<div class="col-xs-2">\
		<a data-therapy="%(therapy)s" data-therapy-plan="%(therapy_plan)s" data-name="%(name)s"\
		data-encounter="%(encounter)s" data-practitioner="%(practitioner)s"\
		data-date="%(date)s"  data-department="%(department)s" data-source="%(source)s"\
		data-referring-practitioner="%(referring_practitioner)s"> <button class="btn btn-default btn-xs">Add\
		</button></a></div></div><div class="col-xs-12"><hr/><div/>',
        {
          therapy: y[0],
          name: y[1],
          encounter: y[2],
          practitioner: y[3],
          date: y[4],
          department: y[6] ? y[6] : "",
          therapy_plan: y[5],
          source: y[7] ? y[7] : "",
          referring_practitioner: y[8] ? y[8] : "",
        }
      )
    ).appendTo(html_field);

    row.find("a").click(function () {
      frm.doc.therapy_type = $(this).attr("data-therapy");
      frm.doc.practitioner = $(this).attr("data-practitioner");
      frm.doc.department = $(this).attr("data-department");
      frm.doc.therapy_plan = $(this).attr("data-therapy-plan");
      frm.doc.source = $(this).attr("data-source");
      frm.set_df_property("source", "read_only", 1);
      frm.doc.referring_practitioner = $(this).attr(
        "data-referring-practitioner"
      );
      if (frm.doc.referring_practitioner) {
        frm.set_df_property("referring_practitioner", "hidden", 0);
        frm.set_df_property("referring_practitioner", "read_only", 1);
      }
      frm.refresh_field("therapy_type");
      frm.refresh_field("practitioner");
      frm.refresh_field("department");
      frm.refresh_field("therapy-plan");
      frm.refresh_field("source");
      frm.refresh_field("referring_practitioner");
      frappe.db.get_value(
        "Therapy Type",
        frm.doc.therapy_type,
        "default_duration",
        (r) => {
          if (r.default_duration) {
            frm.set_value("duration", r.default_duration);
          }
        }
      );
      d.hide();
      return false;
    });
  });
  d.show();
};

let create_vital_signs = function (frm) {
  if (!frm.doc.patient) {
    frappe.throw(__("Please select patient"));
  }
  frappe.route_options = {
    patient: frm.doc.patient,
    appointment: frm.doc.name,
    company: frm.doc.company,
  };
  frappe.new_doc("Vital Signs");
};

let create_radiology_exam = function (frm) {
  var doc = frm.doc;
  frappe.call({
    method:
      "hms_tz.hms_tz.doctype.radiology_examination.radiology_examination.create_radiology_examination",
    args: { appointment: doc.name },
    callback: function (data) {
      if (!data.exc) {
        var doclist = frappe.model.sync(data.message);
        frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
      }
    },
  });
};

let update_status = function (frm, status) {
  let doc = frm.doc;
  frappe.confirm(
    __("Are you sure you want to cancel this appointment?"),
    function () {
      frappe.call({
        method:
          "hms_tz.hms_tz.doctype.patient_appointment.patient_appointment.update_status",
        args: { appointment_id: doc.name, status: status },
        callback: function (data) {
          if (!data.exc) {
            frm.reload_doc();
          }
        },
      });
    }
  );
};

frappe.ui.form.on("Patient Appointment", "practitioner", function (frm) {
  if (frm.doc.practitioner) {
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Healthcare Practitioner",
        name: frm.doc.practitioner,
      },
      callback: function (data) {
        frappe.model.set_value(
          frm.doctype,
          frm.docname,
          "department",
          data.message.department
        );
        frappe.model.set_value(
          frm.doctype,
          frm.docname,
          "paid_amount",
          data.message.op_consulting_charge
        );
        frappe.model.set_value(
          frm.doctype,
          frm.docname,
          "billing_item",
          data.message.op_consulting_charge_item
        );
      },
    });
  }
});

frappe.ui.form.on("Patient Appointment", "patient", function (frm) {
  if (frm.doc.patient) {
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Patient",
        name: frm.doc.patient,
      },
      callback: function (data) {
        let age = null;
        if (data.message.dob) {
          age = calculate_age(data.message.dob);
        }
        frappe.model.set_value(frm.doctype, frm.docname, "patient_age", age);
      },
    });
  }
});

frappe.ui.form.on("Patient Appointment", "appointment_type", function (frm) {
  if (frm.doc.appointment_type) {
    frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Appointment Type",
        name: frm.doc.appointment_type,
      },
      callback: function (data) {
        frappe.model.set_value(
          frm.doctype,
          frm.docname,
          "duration",
          data.message.default_duration
        );
      },
    });
  }
});

let calculate_age = function (birth) {
  let ageMS = Date.parse(Date()) - Date.parse(birth);
  let age = new Date();
  age.setTime(ageMS);
  let years = age.getFullYear() - 1970;
  return (
    years +
    " Year(s) " +
    age.getMonth() +
    " Month(s) " +
    age.getDate() +
    " Day(s)"
  );
};

let get_radiology_prescribed = function (frm) {
  if (frm.doc.patient) {
    frappe.call({
      method:
        "hms_tz.hms_tz.doctype.radiology_examination.radiology_examination.get_radiology_procedure_prescribed",
      args: { patient: frm.doc.patient },
      callback: function (r) {
        show_radiology_procedure(frm, r.message);
      },
    });
  } else {
    frappe.msgprint("Please select Patient to get prescribed procedure");
  }
};

let show_radiology_procedure = function (frm, result) {
  var d = new frappe.ui.Dialog({
    title: __("Radiology Procedure Prescriptions"),
    fields: [
      {
        fieldtype: "HTML",
        fieldname: "radiology_prescribed",
      },
    ],
  });
  var html_field = d.fields_dict.radiology_prescribed.$wrapper;
  html_field.empty();
  $.each(result, function (x, y) {
    var row = $(
      repl(
        '<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-2"> %(radiology_procedure)s </div>\
		<div class="col-xs-2"> %(encounter)s </div>\
		<div class="col-xs-3"> %(date)s </div>\
		<div class="col-xs-1">\
		<a data-name="%(name)s" data-radiology-procedure="%(radiology_procedure)s"\
		data-encounter="%(encounter)s"\
		data-invoiced="%(invoiced)s" data-source="%(source)s"\
		data-referring-practitioner="%(referring_practitioner)s" data-comments="%(comments)s" href="#">\
		<button class="btn btn-default btn-xs">Get Radiology\
		</button></a></div></div>',
        {
          name: y[0],
          radiology_procedure: y[1],
          encounter: y[2],
          invoiced: y[3],
          date: y[4],
          source: y[5],
          referring_practitioner: y[6],
          comments: y[9],
        }
      )
    ).appendTo(html_field);
    row.find("a").click(function () {
      frm.set_value(
        "radiology_examination_template",
        $(this).attr("data-radiology-procedure")
      );
      frm.set_value(
        "radiology_procedure_prescription",
        $(this).attr("data-name")
      );
      // frm.set_df_property('radiology_procedure', 'read_only', 1);
      frm.set_df_property("patient", "read_only", 1);
      frm.doc.invoiced = 0;
      if ($(this).attr("data-invoiced") == 1) {
        frm.doc.invoiced = 1;
      }
      if ($(this).attr("data-comments")) {
        frm.set_value("notes", $(this).attr("data-comments"));
      }
      frm.set_value("source", $(this).attr("data-source"));
      frm.set_value(
        "referring_practitioner",
        $(this).attr("data-referring-practitioner")
      );
      frappe.db.get_value(
        "Radiology Examination Template",
        frm.doc.radiology_examination_template,
        "modality_type",
        function (r) {
          if (r && r.modality_type) {
            frm.set_value("modality_type", r.modality_type);
          } else {
            frm.set_value("modality_type", "");
          }
        }
      );
      refresh_field("radiology_procedure_prescription");
      refresh_field("invoiced");
      refresh_field("radiology_examination_template");
      d.hide();
      return false;
    });
  });
  if (result == "") {
    var msg = "There are no Radiology prescribed for " + frm.doc.patient;
    $(
      repl(
        '<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>',
        { msg: msg }
      )
    ).appendTo(html_field);
  }
  d.show();
};

let set_source_referring_practitioner = function (frm) {
  if (frm.doc.source == "Direct") {
    frm.set_value("referring_practitioner", "");
    frm.set_df_property("referring_practitioner", "hidden", 1);
    frm.set_df_property("referring_practitioner", "reqd", 0);
  } else if (
    frm.doc.source == "External Referral" ||
    frm.doc.source == "Referral"
  ) {
    if (frm.doc.practitioner) {
      frm.set_df_property("referring_practitioner", "hidden", 0);
      if (frm.doc.source == "External Referral") {
        frappe.db.get_value(
          "Healthcare Practitioner",
          frm.doc.practitioner,
          "healthcare_practitioner_type",
          function (r) {
            if (
              r &&
              r.healthcare_practitioner_type &&
              r.healthcare_practitioner_type == "External"
            ) {
              frm.set_value("referring_practitioner", frm.doc.practitioner);
            } else {
              frm.set_value("referring_practitioner", "");
            }
          }
        );
        frm.set_df_property("referring_practitioner", "read_only", 0);
      } else {
        frappe.db.get_value(
          "Healthcare Practitioner",
          frm.doc.practitioner,
          "healthcare_practitioner_type",
          function (r) {
            if (
              r &&
              r.healthcare_practitioner_type &&
              r.healthcare_practitioner_type == "Internal"
            ) {
              frm.set_value("referring_practitioner", frm.doc.practitioner);
              frm.set_df_property("referring_practitioner", "read_only", 1);
            } else {
              frm.set_value("referring_practitioner", "");
              frm.set_df_property("referring_practitioner", "read_only", 0);
            }
          }
        );
      }
      frm.set_df_property("referring_practitioner", "reqd", 1);
    } else {
      frm.set_df_property("referring_practitioner", "read_only", 0);
      frm.set_df_property("referring_practitioner", "hidden", 0);
      frm.set_df_property("referring_practitioner", "reqd", 1);
    }
  }
};
