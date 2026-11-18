// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Inpatient Record", {
  setup: function (frm) {
    frm.get_field("drug_prescription").grid.editable_fields = [
      { fieldname: "drug_code", columns: 2 },
      { fieldname: "drug_name", columns: 2 },
      { fieldname: "dosage", columns: 2 },
      { fieldname: "period", columns: 2 },
    ];
  },

  onload: function (frm) {
    if (frm.doc.source) {
      set_source_referring_practitioner(frm);
    }
  },

  refresh: function (frm) {
    // if (!frm.doc.__islocal && (frm.doc.status == 'Admission Scheduled' || frm.doc.status == 'Admitted')) {
    frm.enable_save();
    // } else {
    // 	frm.disable_save();
    // }

    if (
      frm.doc.patient &&
      frm.doc.patient_appointment &&
      frappe.user.has_role("Healthcare Receptionist")
    ) {
      frm.add_custom_button(__("Itemized Bill"), function () {
        frappe.route_options = {
          patient: frm.doc.patient,
          patient_appointment: frm.doc.patient_appointment,
        };
        frappe.set_route("query-report", "Itemized Bill Report");
      });
    }

    if (
      !frm.doc.insurance_subscription &&
      frm.doc.patient &&
      frm.doc.patient_appointment
    ) {
      frm.add_custom_button(__("IPD Billing Report"), function () {
        frappe.route_options = {
          inpatient_record: frm.doc.name,
          patient: frm.doc.patient,
          appointment_no: frm.doc.patient_appointment,
          company: frm.doc.company,
        };
        frappe.set_route("query-report", "IPD Billing Report");
      });
    }

    if (!frm.doc.__islocal && frm.doc.status == "Admission Scheduled") {
      frm.add_custom_button(__("Admit"), function () {
        admit_patient_dialog(frm);
      });
    }

    if (!frm.doc.__islocal && frm.doc.status == "Discharge Scheduled") {
      frm.add_custom_button(__("Discharge"), function () {
        discharge_patient_dialog(frm);
      });
      frm.add_custom_button(__("Add Bed"), function () {
        add_bed_dialog(frm);
      });
    }

    if (frm.doc.patient && frappe.user.has_role("Physician")) {
      frm.add_custom_button(__("Patient History"), function () {
        frappe.route_options = { patient: frm.doc.patient };
        frappe.set_route("tz-patient-history");
      });
    }
    if (!frm.doc.__islocal && frm.doc.status != "Admitted") {
      // frm.disable_save();
      frm.set_df_property("btn_transfer", "hidden", 1);
    } else {
      frm.set_df_property("btn_transfer", "hidden", 0);
    }

    frm.set_query("primary_practitioner", function () {
      return {
        filters: {
          practitioner_role: "Doctor",
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
    frm.set_query("insurance_subscription", function () {
      return {
        filters: {
          patient: frm.doc.patient,
          docstatus: 1,
        },
      };
    });
  },
  btn_transfer: function (frm) {
    transfer_patient_dialog(frm);
  },

  source: function (frm) {
    if (frm.doc.source) {
      set_source_referring_practitioner(frm);
    }
  },
});

let discharge_patient_dialog = (frm) => {
  let d = new frappe.ui.Dialog({
    title: "Discharge Patient",
    width: 100,
    fields: [
      {
        fieldtype: "Link",
        label: "Discharge Type",
        fieldname: "discharge_type",
        options: "Healthcare Discharge Type",
        reqd:
          frm.doc.insurance_company &&
          frm.doc.insurance_company.includes("NHIF")
            ? 1
            : 0,
      },
    ],
    primary_action_label: __("Discharge"),
    primary_action: async () => {
      let discharge_type = d.get_value("discharge_type");

      if (
        frm.doc.insurance_company &&
        frm.doc.insurance_company.includes("NHIF") &&
        frm.doc.admission_no
      ) {
        frappe.db.get_value(
          "HMS TZ Setting",
          frm.doc.company,
          "enable_nhif_api",
          async (r) => {
            if (r.enable_nhif_api) {
              if (!discharge_type) {
                frappe.msgprint({
                  title: __("Discharge Type Required"),
                  message: __(
                    "Please select a discharge type before proceeding."
                  ),
                  indicator: "red",
                });

                return;
              }

              await nhif_discharge_patient(frm, discharge_type);

              frm.refresh_fields();
              d.hide();
            } else {
              discharge_patient(frm, discharge_type);

              frm.refresh_fields();
              d.hide();
            }
          }
        );
      } else {
        discharge_patient(frm, discharge_type);

        frm.refresh_fields();
        d.hide();
      }
    },
  });

  d.show();
};

let nhif_discharge_patient = (frm, discharge_type) => {
  frappe.call({
    method: "hms_tz.nhif.nhif_api.admission.discharge_patient",
    args: {
      discharge_type: discharge_type,
      ref_doctype: frm.doc.doctype,
      ref_docname: frm.doc.name,
    },
    freeze: true,
    freeze_message: __("Sending Data to NHIF"),
    callback: (r) => {
      if (r.message) {
        let data = r.message;

        discharge_patient(frm, discharge_type);
      }
    },
  });
};

let discharge_patient = (frm, discharge_type) => {
  frm.call("discharge", { discharge_type: discharge_type }).then((r) => {
    if (r.message) {
      frappe.show_alert(
        {
          message: __("Patient discharged successfully"),
          indicator: "green",
        },
        10
      );
      frm.reload_doc();
    }
  });
};

let admit_patient_dialog = (frm) => {
  let dialog = new frappe.ui.Dialog({
    title: "Admit Patient",
    width: 150,
    fields: [
      {
        fieldtype: "Link",
        label: "Service Unit Type",
        fieldname: "service_unit_type",
        options: "Healthcare Service Unit Type",
        default: frm.doc.admission_service_unit_type,
        reqd: 1,
      },
      {
        fieldtype: "Link",
        label: "Admission Type",
        fieldname: "admission_type",
        options: "Healthcare Admission Type",
        reqd: 1,
      },
      {
        fieldtype: "Column Break",
      },
      {
        fieldtype: "Link",
        label: "Service Unit",
        fieldname: "service_unit",
        options: "Healthcare Service Unit",
        reqd: 1,
      },
      {
        fieldtype: "Datetime",
        label: "Admission Datetime",
        fieldname: "check_in",
        reqd: 1,
        default: frappe.datetime.now_datetime(),
      },
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
        reqd:
          frm.doc.insurance_company &&
          frm.doc.insurance_company.includes("NHIF")
            ? 1
            : 0,
        hidden:
          frm.doc.insurance_company &&
          frm.doc.insurance_company.includes("NHIF")
            ? 0
            : 1,
      },
    ],
    primary_action_label:
      frm.doc.insurance_company &&
      frm.doc.insurance_company.includes("NHIF") &&
      !frm.doc.admission_no
        ? __("Next")
        : __("Admit"),
    primary_action: async () => {
      let admission_type = dialog.get_value("admission_type");
      let service_unit = dialog.get_value("service_unit");
      let check_in = dialog.get_value("check_in");
      let biometric_method = dialog.get_value("biometric_method");
      if (!service_unit && !check_in) {
        return;
      }

      dialog.disable_primary_action();

      try {
        if (
          frm.doc.insurance_company &&
          frm.doc.insurance_company.includes("NHIF") &&
          !frm.doc.admission_no
        ) {
          let enable_nhif_api = false;
          await frappe.call({
            method: "frappe.client.get_value",
            args: {
              doctype: "HMS TZ Setting",
              name: frm.doc.company,
              fieldname: "enable_nhif_api",
            },
            callback: (r) => {
              if (r.message && r.message.enable_nhif_api) {
                enable_nhif_api = r.message.enable_nhif_api;
              }
            },
          });

          if (enable_nhif_api) {
            await nhif_admit_patient(
              frm,
              dialog,
              admission_type,
              service_unit,
              check_in,
              biometric_method
            );
          } else {
            await admit_patient(
              frm,
              service_unit,
              check_in,
              null,
              admission_type
            );
            dialog.hide();
          }
        }
        // else if (
        //   frm.doc.insurance_company &&
        //   frm.doc.insurance_company.includes("Jubilee")
        // ) {
        //   frappe.db.get_value(
        //     "HMS TZ Setting",
        //     frm.doc.company,
        //     "enable_jubilee_api",
        //     (r) => {
        //       if (r.enable_jubilee_api) {
        //         jubilee_admit_patient(
        //           frm,
        //           dialog,
        //           admission_type,
        //           service_unit,
        //           check_in
        //         );
        //       } else {
        //         admit_patient(frm, service_unit, check_in, admission_type);
        //         dialog.hide();
        //       }
        //     }
        //   );
        // }
        else {
          await admit_patient(
            frm,
            service_unit,
            check_in,
            null,
            admission_type
          );
          dialog.hide();
        }
      } catch (e) {
        dialog.enable_primary_action();
        frappe.msgprint({
          title: __("Admission Error"),
          message: __(e.message || e),
          indicator: "red",
        });
      }
    },
  });

  dialog.fields_dict["service_unit_type"].get_query = function () {
    return {
      filters: {
        inpatient_occupancy: 1,
        allow_appointments: 0,
      },
    };
  };
  dialog.fields_dict["service_unit"].get_query = function () {
    return {
      filters: {
        is_group: 0,
        company: frm.doc.company,
        service_unit_type: dialog.get_value("service_unit_type"),
        occupancy_status: "Vacant",
      },
    };
  };

  dialog.show();
};

let nhif_admit_patient = async (
  frm,
  dialog,
  admission_type,
  service_unit,
  check_in,
  biometric_method
) => {
  const biometricData = await captureBiometric(biometric_method, "Admit");
  if (!biometricData) {
    dialog.enable_primary_action();
    return;
  }

  dialog.hide();

  let r;
  try {
    r = await frappe.call({
      method: "hms_tz.nhif.nhif_api.admission.admit_patient",
      args: {
        admission_type: admission_type,
        service_unit: service_unit,
        date_admitted: check_in,
        fingerprint: biometricData.Data,
        fpcode: biometricData.fpCode,
        biometric_method: biometric_method,
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
      },
      freeze: true,
      freeze_message: __("Sending Data to NHIF"),
      callback: (r) => {
        if (r && r.message && r.message.admitted) {
          frappe.utils.play_sound("success");
          frappe.show_alert({
            message: __("Patient admitted successfully"),
            indicator: "green",
          });
          frm.reload_doc();
        } else if (r && r.message && !r.message.admission_no) {
          frappe.utils.play_sound("error");
          frappe.msgprint({
            title: __("NHIF Admission Incomplete"),
            message: __(
              "NHIF did not return an Admission Number. Please try again."
            ),
            indicator: "red",
          });
        }
      },
    });
  } catch (nhif_error) {
    await frm.reload_doc();

    console.error("NHIF admission API error:", nhif_error);

    if (frm.doc.status === "Admitted") {
      frappe.utils.play_sound("success");
      frappe.show_alert({
        message: __("Patient admitted successfully"),
        indicator: "green",
      });
    } else {
      frappe.utils.play_sound("error");
      frappe.msgprint({
        title: __("NHIF Admission Error"),
        message: __(
          "An error occurred while communicating with NHIF. Please try again."
        ),
        indicator: "red",
      });
    }
    return;
  }
};

let jubilee_admit_patient = (
  frm,
  dialog,
  admission_type,
  service_unit,
  check_in
) => {
  dialog.hide();

  frappe.call({
    method: "hms_tz.jubilee.api.api.get_inpatient_admission_status",
    args: {
      inpatient_record_name: frm.doc.name,
    },
    freeze: true,
    freeze_message: __("Checking Jubilee Admission Status..."),
    callback: (r) => {
      if (r.message && r.message.status === "OK") {
        let data = r.message.description || {};
        frappe.show_alert({
          message: __(
            `Jubilee Admission Confirmed — Approval No: ${
              data.approvalNumber || ""
            }, Approved: TZS ${data.approvedAmount || "N/A"}`
          ),
          indicator: "green",
        });
        admit_patient(frm, service_unit, check_in, admission_type);
      }
    },
    onerror: () => {
      frappe.utils.play_sound("error");
      frappe.msgprint({
        title: __("Jubilee Admission Error"),
        indicator: "red",
        message: __(
          "An unexpected error occurred while fetching the Jubilee admission status."
        ),
      });
    },
  });
};

let admit_patient = (
  frm,
  service_unit,
  check_in,
  admission_no = null,
  admission_type = null,
  poc_reference_no = null
) => {
  return frm
    .call("admit", {
      service_unit: service_unit,
      check_in: check_in,
      admission_no: admission_no,
      admission_type: admission_type,
      poc_reference_no: poc_reference_no,
    })
    .then((r) => {
      if (r.message) {
        frappe.show_alert({
          message: __("Patient admitted successfully"),
          indicator: "green",
        });
        frm.reload_doc();
      }
    });
};

let add_bed_dialog = (frm) => {
  let dialog = new frappe.ui.Dialog({
    title: "Add Remaining Bed",
    width: 100,
    fields: [
      {
        fieldtype: "Link",
        label: "Service Unit Type",
        fieldname: "service_unit_type",
        options: "Healthcare Service Unit Type",
        reqd: 1,
      },
      {
        fieldtype: "Link",
        label: "Service Unit",
        fieldname: "service_unit",
        options: "Healthcare Service Unit",
        reqd: 1,
      },
      {
        fieldtype: "Datetime",
        label: "Check In",
        fieldname: "check_in",
        reqd: 1,
      },
      { fieldtype: "Check", label: "Left", fieldname: "left", reqd: 1 },
      {
        fieldtype: "Datetime",
        label: "Check Out",
        fieldname: "check_out",
        reqd: 1,
      },
    ],
    primary_action_label: __("Add"),
    primary_action: function () {
      let service_unit = dialog.get_value("service_unit");
      let check_in = dialog.get_value("check_in");
      let check_out = dialog.get_value("check_out");
      let left = dialog.get_value("left");
      if (check_out && !left) {
        left = 1;
      }

      if (!service_unit && !check_in && !check_out) {
        return;
      }

      if (check_in) {
        let check_in_time = new Date(check_in);
        let date_time = new Date();
        if (check_in_time.getTime() > date_time.getTime()) {
          frappe.throw({
            title: __("Check In Date Error"),
            message: __("Check In Date cannot be future date or time"),
            indicator: "red",
          });
          return;
        }
      }

      let check_out_time = new Date(check_out);
      let check_in_time = new Date(check_in);
      let date_time_out = new Date();
      if (check_out_time.getTime() > date_time_out.getTime()) {
        frappe.throw({
          title: __("Check Out Date Error"),
          message: __("Check Out Date cannot be future date or time"),
          indicator: "red",
        });
        return;
      }
      if (check_out_time.getTime() <= check_in_time.getTime()) {
        frappe.throw({
          title: __("Check Out Date Error"),
          message: __(
            "Check Out Date cannot before or equal to Check In Date"
          ),
          indicator: "red",
        });
        return;
      }

      frappe.call({
        doc: frm.doc,
        method: "add_bed",
        args: {
          service_unit: service_unit,
          check_in: check_in,
          check_out: check_out,
          left: left,
        },
        callback: function (data) {
          if (!data.exc) {
            frm.reload_doc();
          }
        },
      });

      frm.reload_doc();
      frm.refresh_fields();
      dialog.hide();
    },
  });

  dialog.fields_dict["service_unit_type"].get_query = function () {
    return {
      filters: {
        inpatient_occupancy: 1,
        allow_appointments: 0,
      },
    };
  };

  dialog.fields_dict["service_unit"].get_query = function () {
    return {
      filters: {
        is_group: 0,
        company: frm.doc.company,
        service_unit_type: dialog.get_value("service_unit_type"),
        //'occupancy_status': 'Vacant'
      },
    };
  };
  dialog.show();
};

let transfer_patient_dialog = (frm) => {
  let dialog = new frappe.ui.Dialog({
    title: "Transfer Patient",
    width: 100,
    fields: [
      {
        fieldtype: "Link",
        label: "Leave From",
        fieldname: "leave_from",
        options: "Healthcare Service Unit",
        reqd: 1,
        read_only: 1,
      },
      {
        fieldtype: "Link",
        label: "Service Unit Type",
        fieldname: "service_unit_type",
        options: "Healthcare Service Unit Type",
        reqd: 1,
      },
      {
        fieldtype: "Column Break",
      },
      {
        fieldtype: "Link",
        label: "Transfer To",
        fieldname: "service_unit",
        options: "Healthcare Service Unit",
        reqd: 1,
      },
      {
        fieldtype: "Datetime",
        label: "Check In",
        fieldname: "check_in",
        reqd: 1,
        default: frappe.datetime.now_datetime(),
      },
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
        reqd:
          frm.doc.insurance_company &&
          frm.doc.insurance_company.includes("NHIF")
            ? 1
            : 0,
        hidden:
          frm.doc.insurance_company &&
          frm.doc.insurance_company.includes("NHIF")
            ? 0
            : 1,
      },
    ],
    primary_action_label:
      frm.doc.insurance_company && frm.doc.insurance_company.includes("NHIF")
        ? __("Next")
        : __("Transfer"),
    primary_action: async () => {
      let service_unit = null;
      let leave_from = null;
      let check_in = dialog.get_value("check_in");
      let service_unit_type = dialog.get_value("service_unit_type");
      let biometric_method = dialog.get_value("biometric_method");
      if (dialog.get_value("leave_from")) {
        leave_from = dialog.get_value("leave_from");
      }
      if (dialog.get_value("service_unit")) {
        service_unit = dialog.get_value("service_unit");
      }
      if (check_in > frappe.datetime.now_datetime()) {
        frappe.msgprint({
          title: __("Not Allowed"),
          message: __("Check-in time cannot be greater than the current time"),
          indicator: "red",
        });
        return;
      }

      if (
        frm.doc.insurance_company &&
        frm.doc.insurance_company.includes("NHIF")
      ) {
        frappe.db.get_value(
          "HMS TZ Setting",
          frm.doc.company,
          "enable_nhif_api",
          async (r) => {
            if (r.enable_nhif_api) {
              await nhif_transfer_patient(
                frm,
                dialog,
                service_unit_type,
                service_unit,
                check_in,
                leave_from,
                biometric_method
              );
            } else {
              transfer_patient(frm, service_unit, check_in, leave_from);
              dialog.hide();
            }
          }
        );
      } else {
        transfer_patient(frm, service_unit, check_in, leave_from);
        dialog.hide();
      }
    },
  });

  dialog.fields_dict["leave_from"].get_query = function () {
    return {
      query:
        "hms_tz.hms_tz.doctype.inpatient_record.inpatient_record.get_leave_from",
      filters: { docname: frm.doc.name },
    };
  };
  dialog.fields_dict["service_unit_type"].get_query = function () {
    return {
      filters: {
        inpatient_occupancy: 1,
        allow_appointments: 0,
      },
    };
  };
  dialog.fields_dict["service_unit"].get_query = function () {
    return {
      filters: {
        is_group: 0,
        service_unit_type: dialog.get_value("service_unit_type"),
        occupancy_status: "Vacant",
        company: frm.doc.company,
      },
    };
  };

  let not_left_service_unit = null;
  for (let inpatient_occupancy in frm.doc.inpatient_occupancies) {
    if (frm.doc.inpatient_occupancies[inpatient_occupancy].left != 1) {
      not_left_service_unit =
        frm.doc.inpatient_occupancies[inpatient_occupancy].service_unit;
    }
  }
  dialog.set_values({
    leave_from: not_left_service_unit,
  });

  dialog.show();
};

let nhif_transfer_patient = async (
  frm,
  dialog,
  service_unit_type,
  service_unit,
  check_in,
  leave_from,
  biometric_method
) => {
  const biometricData = await captureBiometric(biometric_method, "Transfer");
  if (!biometricData) return;

  dialog.hide();

  frappe.call({
    method: "hms_tz.nhif.nhif_api.admission.transfer_patient",
    args: {
      service_unit_type: service_unit_type,
      service_unit: service_unit,
      date_transferred: check_in,
      fingerprint: biometricData.Data,
      fpcode: biometricData.fpCode,
      biometric_method: biometric_method,
      ref_doctype: frm.doc.doctype,
      ref_docname: frm.doc.name,
    },
    freeze: true,
    freeze_message: __("Sending Data to NHIF"),
    callback: (r) => {
      if (r.message) {
        let data = r.message;

        transfer_patient(
          frm,
          service_unit,
          check_in,
          leave_from,
          data.poc_reference_no
        );
      }
    },
  });
};

let transfer_patient = (
  frm,
  service_unit,
  check_in,
  leave_from,
  poc_reference_no = ""
) => {
  frm
    .call("transfer", {
      service_unit: service_unit,
      check_in: check_in,
      leave_from: leave_from,
      poc_reference_no: poc_reference_no,
    })
    .then((r) => {
      if (!r.exc) {
        frappe.show_alert(
          {
            message: __("Patient transferred successfully"),
            indicator: "green",
          },
          10
        );

        frm.reload_doc();
      }
    });
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
    if (frm.doc.primary_practitioner) {
      frm.set_df_property("referring_practitioner", "hidden", 0);
      if (frm.doc.source == "External Referral") {
        frappe.db.get_value(
          "Healthcare Practitioner",
          frm.doc.primary_practitioner,
          "healthcare_practitioner_type",
          function (r) {
            if (
              r &&
              r.healthcare_practitioner_type &&
              r.healthcare_practitioner_type == "External"
            ) {
              frm.set_value(
                "referring_practitioner",
                frm.doc.primary_practitioner
              );
            } else {
              frm.set_value("referring_practitioner", "");
            }
          }
        );
        frm.set_df_property("referring_practitioner", "read_only", 0);
      } else {
        frappe.db.get_value(
          "Healthcare Practitioner",
          frm.doc.primary_practitioner,
          "healthcare_practitioner_type",
          function (r) {
            if (
              r &&
              r.healthcare_practitioner_type &&
              r.healthcare_practitioner_type == "Internal"
            ) {
              frm.set_value(
                "referring_practitioner",
                frm.doc.primary_practitioner
              );
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
