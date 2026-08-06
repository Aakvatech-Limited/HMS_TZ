// Copyright (c) 2026, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Nurse Record", {
  setup: (frm) => {
    render_age(frm);
    render_vital_signs(frm);
  },

  refresh: (frm) => {
    set_queries(frm);
    render_consumables_placeholder(frm);
    render_unscheduled_medications(frm);
    render_pending_medications(frm);
    render_medication_progress(frm);
    render_completed_medications(frm);
    check_upcoming_medications(frm);
  },

  onload: (frm) => {
    render_age(frm);
    render_vital_signs(frm);
  },

  appointment: (frm) => {
    if (frm.doc.appointment) {
      render_vital_signs(frm);
      render_age(frm);
    }
  },

  record_vital_signs: (frm) => {
    if (frm.is_new() || frm.doc.docstatus === 2) return;

    show_vital_signs_dialog(frm);
  },
});

function set_queries(frm) {
  frm.set_query("nurse", () => {
    return {
      filters: {
        status: "Active",
        practitioner_role: "Nurse",
        hms_tz_company: frm.doc.company,
      },
    };
  });

  frm.set_query("acknowledged_by", () => {
    return {
      filters: {
        status: "Active",
        practitioner_role: "Nurse",
        hms_tz_company: frm.doc.company,
      },
    };
  });
  frm.set_query("room", () => {
    return {
      filters: {
        disabled: 0,
        is_group: 0,
        company: frm.doc.company,
      },
    };
  });

  frm.set_query("ward", () => {
    return {
      filters: {
        disabled: 0,
      },
    };
  });
}

function render_vital_signs(frm) {
  if (!frm.doc.patient) return;
  frappe.call({
    method: "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_vital_signs",
    args: {
      patient: frm.doc.patient,
      appointment: frm.doc.appointment || "",
    },
    callback: function (r) {
      if (r.message && r.message.length > 0) {
        render_vitals_chart_and_table(frm, r.message);
      } else {
        frm.fields_dict.vital_signs_html.$wrapper.html(
          '<div class="text-muted text-center p-4">' +
            __("No vital signs recorded for this patient episode.") +
            "</div>"
        );
      }
    },
  });
}

function render_vitals_chart_and_table(frm, vitals) {
  let $wrapper = frm.fields_dict.vital_signs_html.$wrapper;
  $wrapper.empty();

  // --- Chart Section ---
  let chart_id = "vitals-chart-" + frm.doc.name;
  $wrapper.append('<div class="mb-4"><div id="' + chart_id + '"></div></div>');

  let labels = vitals.map(function (v) {
    return v.signs_date;
  });
  let temp_data = vitals.map(function (v) {
    return parseFloat(v.temperature) || 0;
  });
  let pulse_data = vitals.map(function (v) {
    return parseFloat(v.pulse) || 0;
  });
  let rr_data = vitals.map(function (v) {
    return parseFloat(v.respiratory_rate) || 0;
  });
  let bp_sys_data = vitals.map(function (v) {
    return parseFloat(v.bp_systolic) || 0;
  });
  let bp_dia_data = vitals.map(function (v) {
    return parseFloat(v.bp_diastolic) || 0;
  });

  new frappe.Chart("#" + chart_id, {
    title: __("Vital Signs Trend"),
    data: {
      labels: labels,
      datasets: [
        { name: __("Temperature (°C)"), values: temp_data },
        { name: __("Pulse (bpm)"), values: pulse_data },
        { name: __("Respiratory Rate"), values: rr_data },
        { name: __("BP Systolic"), values: bp_sys_data },
        { name: __("BP Diastolic"), values: bp_dia_data },
      ],
    },
    type: "line",
    height: 280,
    colors: ["#ff6384", "#36a2eb", "#4bc0c0", "#ff9f40", "#9966ff"],
    lineOptions: {
      regionFill: 0,
      hideDots: 0,
    },
  });

  // --- Table Section ---
  let table_html = '<table class="table table-bordered table-sm mt-3">';
  table_html += "<thead><tr>";
  table_html += "<th>" + __("Date") + "</th>";
  table_html += "<th>" + __("Time") + "</th>";
  table_html += "<th>" + __("Temp (°C)") + "</th>";
  table_html += "<th>" + __("Pulse") + "</th>";
  table_html += "<th>" + __("RR") + "</th>";
  table_html += "<th>" + __("BP") + "</th>";
  table_html += "<th>" + __("SpO2") + "</th>";
  table_html += "<th>" + __("RBG") + "</th>";
  table_html += "<th>" + __("Height (cm)") + "</th>";
  table_html += "<th>" + __("Weight (kg)") + "</th>";
  table_html += "<th>" + __("BMI") + "</th>";
  // table_html += "<th>" + __("Notes") + "</th>";
  table_html += "</tr></thead><tbody>";

  vitals.forEach(function (v) {
    let bp_display = v.bp || v.bp_systolic + "/" + v.bp_diastolic;
    let time_display = v.signs_time ? v.signs_time.substring(0, 5) : "";
    table_html += "<tr>";
    table_html += "<td>" + (v.signs_date || "") + "</td>";
    table_html += "<td>" + time_display + "</td>";
    table_html += "<td>" + (v.temperature || "") + "</td>";
    table_html += "<td>" + (v.pulse || "") + "</td>";
    table_html += "<td>" + (v.respiratory_rate || "") + "</td>";
    table_html += "<td>" + bp_display + "</td>";
    table_html += "<td>" + (v.oxygen_saturation_spo2 || "") + "</td>";
    table_html += "<td>" + (v.rbg || "") + "</td>";
    table_html += "<td>" + (v.height_in_cm || "") + "</td>";
    table_html += "<td>" + (v.weight || "") + "</td>";
    table_html += "<td>" + (v.bmi || "") + "</td>";
    // table_html += "<td>" + (v.vital_signs_note || "") + "</td>";
    table_html += "</tr>";
  });

  table_html += "</tbody></table>";
  $wrapper.append(table_html);
}

function show_vital_signs_dialog(frm) {
  let d = new frappe.ui.Dialog({
    title: __("Record Vital Signs"),
    fields: [
      {
        fieldname: "temperature",
        fieldtype: "Data",
        label: __("Temperature (°C)"),
      },
      {
        fieldname: "pulse",
        fieldtype: "Data",
        label: __("Pulse (bpm)"),
      },
      {
        fieldname: "respiratory_rate",
        fieldtype: "Data",
        label: __("Respiratory Rate"),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "bp_systolic",
        fieldtype: "Data",
        label: __("BP Systolic"),
      },
      {
        fieldname: "bp_diastolic",
        fieldtype: "Data",
        label: __("BP Diastolic"),
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "oxygen_saturation_spo2",
        fieldtype: "Data",
        label: __("SpO2 (%)"),
      },
      {
        fieldname: "rbg",
        fieldtype: "Float",
        label: __("Random Blood Glucose (RBG)"),
      },
      {
        fieldname: "abdomen",
        fieldtype: "Select",
        label: __("Abdomen"),
        options: "\nNormal\nBloated\nFull\nFluid\nConstipated",
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "weight",
        fieldtype: "Float",
        label: __("Weight (kg)"),
      },
      {
        fieldname: "height_in_cm",
        fieldtype: "Int",
        label: __("Height (cm)"),
      },
      {
        fieldname: "reflexes",
        fieldtype: "Select",
        label: __("Reflexes"),
        options: "\nNormal\nHyper\nVery Hyper\nOne Sided",
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "vital_signs_note",
        fieldtype: "Small Text",
        label: __("Notes"),
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "signs_date",
        fieldtype: "Date",
        label: __("Date Taken"),
        default: frappe.datetime.get_today(),
        reqd: 1,
      },
      {
        fieldname: "signs_time",
        fieldtype: "Time",
        label: __("Time Taken"),
        default: frappe.datetime.now_time(),
        reqd: 1,
      },
    ],
    primary_action_label: __("Save"),
    primary_action(values) {
      frappe.call({
        method:
          "hms_tz.hms_tz.doctype.nurse_record.nurse_record.create_vital_signs",
        args: {
          patient: frm.doc.patient,
          nurse_record: frm.doc.name,
          ...values,
        },
        callback: function (r) {
          if (r.message) {
            frappe.show_alert({
              message: __("Vital Signs {0} created and submitted", [
                r.message,
              ]),
              indicator: "green",
            });
            d.hide();
            render_vital_signs(frm);
          }
        },
      });
    },
  });

  d.show();
}

// ─── Unscheduled Medications (from Dispensed Medication records) ───

function render_unscheduled_medications(frm) {
  if (!frm.fields_dict.unscheduled_medications_html) return;
  if (!frm.doc.patient || !frm.doc.inpatient_record) {
    frm.fields_dict.unscheduled_medications_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Unscheduled medications will appear for admitted patients.") +
        "</div>"
    );
    return;
  }

  frappe.call({
    method:
      "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_dispensed_medications",
    args: {
      patient: frm.doc.patient,
      inpatient_record: frm.doc.inpatient_record || "",
    },
    callback: (r) => {
      if (r.message && r.message.length > 0) {
        render_unscheduled_meds_table(frm, r.message);
      } else {
        frm.fields_dict.unscheduled_medications_html.$wrapper.html(
          '<div class="text-muted text-center p-3">' +
            __(
              "No unscheduled medications. All dispensed drugs have been scheduled."
            ) +
            "</div>"
        );
      }
    },
  });
}

function render_unscheduled_meds_table(frm, entries) {
  let $wrapper = frm.fields_dict.unscheduled_medications_html.$wrapper;
  $wrapper.empty();

  let html =
    '<div class="mb-2" style="padding: 8px; background: #fff8e1; border-left: 4px solid #ff9800; border-radius: 4px;">' +
    '<strong style="color: #e65100;">💊 ' +
    __("{0} medication(s) awaiting schedule from nurse", [entries.length]) +
    "</strong></div>" +
    '<table class="table table-sm table-bordered">' +
    "<thead><tr>" +
    "<th>" +
    __("Drug") +
    "</th>" +
    "<th>" +
    __("Form") +
    "</th>" +
    "<th>" +
    __("Dosage") +
    "</th>" +
    "<th>" +
    __("Period") +
    "</th>" +
    "<th>" +
    __("Qty Dispensed") +
    "</th>" +
    "<th>" +
    __("Dispensed Date") +
    "</th>" +
    '<th class="text-center">' +
    __("Action") +
    "</th>" +
    "</tr></thead><tbody>";

  entries.forEach((e) => {
    html +=
      "<tr>" +
      "<td><strong>" +
      (e.drug_name || e.drug) +
      "</strong></td>" +
      "<td>" +
      (e.dosage_form || "-") +
      "</td>" +
      "<td>" +
      (e.prescribed_dosage || "-") +
      "</td>" +
      "<td>" +
      (e.prescribed_period || "-") +
      "</td>" +
      "<td>" +
      (e.qty_dispensed || 0) +
      "</td>" +
      "<td>" +
      (e.posting_date || "") +
      "</td>" +
      '<td class="text-center">' +
      '<button class="btn btn-xs btn-warning btn-schedule-med" ' +
      'data-dm="' +
      e.name +
      '" ' +
      'data-drug="' +
      (e.drug_name || e.drug) +
      '" ' +
      'data-form="' +
      (e.dosage_form || "") +
      '" ' +
      'data-qty="' +
      (e.qty_dispensed || 0) +
      '" ' +
      'data-prescribed="' +
      (e.prescribed_dosage || "") +
      '" ' +
      'data-period="' +
      (e.prescribed_period || "") +
      '">' +
      __("Create Schedule") +
      "</button>" +
      "</td></tr>";
  });

  html += "</tbody></table>";
  $wrapper.html(html);

  $wrapper.find(".btn-schedule-med").on("click", function () {
    let dm_name = $(this).data("dm");
    let drug_name = $(this).data("drug");
    let dosage_form = $(this).data("form");
    let qty_dispensed = $(this).data("qty");
    let prescribed = $(this).data("prescribed");
    let period = $(this).data("period");
    show_schedule_medication_dialog(
      frm,
      dm_name,
      drug_name,
      dosage_form,
      qty_dispensed,
      prescribed,
      period
    );
  });
}

function show_schedule_medication_dialog(
  frm,
  dm_name,
  drug_name,
  dosage_form,
  qty_dispensed,
  prescribed,
  period
) {
  let info_rows = [];
  if (dosage_form)
    info_rows.push(__("Form") + ": <strong>" + dosage_form + "</strong>");
  if (prescribed)
    info_rows.push(__("Dosage") + ": <strong>" + prescribed + "</strong>");
  if (period)
    info_rows.push(__("Period") + ": <strong>" + period + "</strong>");
  info_rows.push(
    __("Qty Dispensed") + ": <strong>" + qty_dispensed + "</strong>"
  );

  let d = new frappe.ui.Dialog({
    title: __("Create Medication Schedule"),
    size: "large",
    fields: [
      {
        fieldname: "drug_info",
        fieldtype: "HTML",
        options:
          '<div style="padding: 12px; background: var(--bg-light-gray); border-radius: 6px; margin-bottom: 12px;">' +
          '<div style="font-size: 15px; font-weight: 600; margin-bottom: 6px;">' +
          drug_name +
          "</div>" +
          '<div style="display: flex; flex-wrap: wrap; gap: 12px;">' +
          info_rows
            .map((r) => '<span style="font-size: 13px;">' + r + "</span>")
            .join('<span style="color: var(--gray-400)">|</span>') +
          "</div></div>",
      },
      {
        fieldtype: "Section Break",
        label: __("Schedule Details"),
      },
      {
        fieldname: "dose_uom",
        fieldtype: "Link",
        options: "UOM",
        label: __("Dose UOM"),
        description: __("e.g., Tablet, ml, mg, Drop, Puff, Unit"),
        reqd: 1,
      },
      {
        fieldname: "dose_per_administration",
        fieldtype: "Float",
        label: __("Dose(s) per Administration"),
        description: __("How much per dose (e.g., 2, 5)"),
        reqd: 1,
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "total_administrable_qty",
        fieldtype: "Float",
        label: __("Total Administrable Qty"),
        description: __(
          "Total usable quantity in the dose UOM (e.g., 100 for 100ml bottle, or same as Qty Dispensed for tablets)"
        ),
        reqd: 1,
        default: qty_dispensed,
      },
      {
        fieldname: "interval_hours",
        fieldtype: "Int",
        label: __("Interval (Hours)"),
        description: __("Interval in hours between each dose"),
        reqd: 1,
        default: 8,
      },
      { fieldtype: "Section Break", label: __("Schedule Timing") },
      {
        fieldname: "start_date",
        fieldtype: "Date",
        label: __("Start Date"),
        reqd: 1,
        default: (() => {
          // Round up to next whole hour; if that crosses midnight, bump date
          let now = frappe.datetime.now_datetime_as_moment
            ? moment()
            : moment(frappe.datetime.now_datetime());
          let next_hour = now.clone().startOf("hour");
          if (next_hour.isSameOrBefore(now)) {
            next_hour.add(1, "hour");
          }
          return next_hour.format("YYYY-MM-DD");
        })(),
      },
      { fieldtype: "Column Break" },
      {
        fieldname: "start_time",
        fieldtype: "Time",
        label: __("Start Time"),
        reqd: 1,
        default: (() => {
          let now = moment(frappe.datetime.now_datetime());
          let next_hour = now.clone().startOf("hour");
          if (next_hour.isSameOrBefore(now)) {
            next_hour.add(1, "hour");
          }
          return next_hour.format("HH:mm");
        })(),
      },
      { fieldtype: "Section Break" },
      {
        fieldname: "schedule_preview",
        fieldtype: "HTML",
        label: __("Preview"),
      },
    ],
    primary_action_label: __("Create Schedule"),
    primary_action(values) {
      if (values.dose_per_administration <= 0) {
        frappe.msgprint(
          __("Dose per administration must be greater than zero.")
        );
        return;
      }
      if (values.interval_hours <= 0) {
        frappe.msgprint(__("Interval must be greater than zero."));
        return;
      }
      if (values.total_administrable_qty <= 0) {
        frappe.msgprint(
          __("Total administrable quantity must be greater than zero.")
        );
        return;
      }

      let total_doses = Math.floor(
        values.total_administrable_qty / values.dose_per_administration
      );

      if (total_doses <= 0) {
        frappe.msgprint(
          __("Cannot create schedule: quantity is less than one dose.")
        );
        return;
      }

      frappe.call({
        method:
          "hms_tz.hms_tz.doctype.nurse_record.nurse_record.create_medication_schedule",
        args: {
          dispensed_medication: dm_name,
          total_administrable_qty: values.total_administrable_qty,
          dose_per_administration: values.dose_per_administration,
          dose_uom: values.dose_uom,
          start_date: values.start_date,
          start_time: values.start_time,
          interval_hours: values.interval_hours,
        },
        freeze: true,
        freeze_message: __("Creating medication schedule..."),
        callback: (r) => {
          if (r.message && r.message.status === "success") {
            let remainder_msg = "";
            if (r.message.remainder > 0) {
              remainder_msg =
                "<br><small>" +
                __("{0} remaining (less than one dose)", [
                  r.message.remainder,
                ]) +
                "</small>";
            }

            frappe.show_alert({
              message:
                __("Schedule created: {0} doses from {1} to {2}", [
                  r.message.total_doses,
                  values.start_date,
                  r.message.end_date,
                ]) + remainder_msg,
              indicator: "green",
            });

            d.hide();
            render_unscheduled_medications(frm);
            render_pending_medications(frm);
            render_medication_progress(frm);
          }
        },
      });
    },
  });

  // Live preview calculation
  function update_preview() {
    let vals = d.get_values(true);
    let $preview = d.fields_dict.schedule_preview.$wrapper;

    if (
      !vals.total_administrable_qty ||
      !vals.dose_per_administration ||
      !vals.interval_hours ||
      vals.dose_per_administration <= 0 ||
      vals.interval_hours <= 0
    ) {
      $preview.html(
        '<div class="text-muted p-2">' +
          __("Fill in all fields to see schedule preview.") +
          "</div>"
      );
      return;
    }

    let total_doses = Math.floor(
      vals.total_administrable_qty / vals.dose_per_administration
    );
    let remainder =
      vals.total_administrable_qty -
      total_doses * vals.dose_per_administration;

    if (total_doses <= 0) {
      $preview.html(
        '<div class="text-danger p-2">' +
          __("Quantity is less than one dose.") +
          "</div>"
      );
      return;
    }

    // Calculate end date/time
    let start_str =
      (vals.start_date || frappe.datetime.get_today()) +
      " " +
      (vals.start_time || "08:00");
    let start_moment = moment(start_str, "YYYY-MM-DD HH:mm");
    let end_moment = moment(start_moment).add(
      (total_doses - 1) * vals.interval_hours,
      "hours"
    );

    let doses_per_day = Math.floor(24 / vals.interval_hours);
    let total_days = Math.floor(total_doses / doses_per_day);

    let preview_html =
      '<div style="padding: 10px; background: #e8f5e9; border-radius: 4px;">' +
      "<strong>" +
      __("Schedule Summary") +
      "</strong><br>" +
      __("Total doses: {0}", ["<strong>" + total_doses + "</strong>"]) +
      "<br>" +
      __("Doses per day: ~{0} (every {1}h)", [
        doses_per_day,
        vals.interval_hours,
      ]) +
      "<br>" +
      __("Duration: ~{0} day(s)", [total_days]) +
      "<br>" +
      __("From: {0}", [start_moment.format("DD MMM YYYY HH:mm")]) +
      "<br>" +
      __("To: {0}", [end_moment.format("DD MMM YYYY HH:mm")]);

    if (remainder > 0) {
      preview_html +=
        '<br><span class="text-warning">' +
        __("Remainder: {0} (less than one dose)", [remainder.toFixed(2)]) +
        "</span>";
    }

    preview_html += "</div>";
    $preview.html(preview_html);
  }

  // Bind change events for live preview
  [
    "total_administrable_qty",
    "dose_per_administration",
    "interval_hours",
    "start_date",
    "start_time",
  ].forEach((field) => {
    d.fields_dict[field].$input.on("change", update_preview);
  });

  d.show();
  update_preview();
}

// ─── Pending Medications (HTML-based, from IMO Entry) ───

function render_pending_medications(frm) {
  if (!frm.fields_dict.pending_medications_html) return;
  if (!frm.doc.patient || !frm.doc.inpatient_record) {
    frm.fields_dict.pending_medications_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Pending medications will appear for admitted patients.") +
        "</div>"
    );
    return;
  }

  frappe.call({
    method:
      "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_pending_medications",
    args: {
      patient: frm.doc.patient,
      inpatient_record: frm.doc.inpatient_record,
    },
    callback: (r) => {
      if (r.message && r.message.length > 0) {
        render_pending_meds_table(frm, r.message);
        console.log();
      } else {
        frm.fields_dict.pending_medications_html.$wrapper.html(
          '<div class="text-muted text-center p-4">' +
            __("No pending medications.") +
            "</div>"
        );
      }
    },
  });
}

function render_pending_meds_table(frm, entries) {
  let $wrapper = frm.fields_dict.pending_medications_html.$wrapper;
  $wrapper.empty();

  let html =
    '<table class="table table-sm table-bordered">' +
    "<thead><tr>" +
    "<th>" +
    __("Drug") +
    "</th>" +
    "<th>" +
    __("Dose(s)") +
    "</th>" +
    "<th>" +
    __("Form") +
    "</th>" +
    "<th>" +
    __("Date") +
    "</th>" +
    "<th>" +
    __("Time") +
    "</th>" +
    "<th>" +
    __("Status") +
    "</th>" +
    '<th class="text-center">' +
    __("Action") +
    "</th>" +
    "</tr></thead><tbody>";

  entries.forEach((e) => {
    let held_badge =
      e.administration_status === "Held"
        ? ' <span class="badge badge-warning">' + __("Held") + "</span>"
        : "";

    let time_display = e.time ? e.time.substring(0, 5) : "";
    // Ensure HH:mm format for reliable comparison (pad single-digit hours)
    if (time_display.length === 5 && time_display.endsWith(":")) {
      time_display = "0" + time_display.substring(0, 4);
    }
    let now_time = frappe.datetime.now_time().substring(0, 5);
    let is_overdue =
      e.date < frappe.datetime.get_today() ||
      (e.date === frappe.datetime.get_today() && time_display < now_time);
    let overdue_style = is_overdue
      ? ' style="color: #e53935; font-weight: bold;"'
      : "";

    html +=
      "<tr>" +
      "<td>" +
      (e.drug_name || e.drug) +
      "</td>" +
      "<td>" +
      ((e.dosage || "") + (e.dose_uom ? " " + e.dose_uom : "")) +
      "</td>" +
      "<td>" +
      (e.dosage_form || "") +
      "</td>" +
      "<td>" +
      (e.date || "") +
      "</td>" +
      "<td" +
      overdue_style +
      ">" +
      time_display +
      (is_overdue ? " ⚠️" : "") +
      "</td>" +
      "<td" +
      overdue_style +
      ">" +
      (held_badge || (is_overdue ? __("Overdue") : __("Pending"))) +
      "</td>" +
      '<td class="text-center">' +
      '<button class="btn btn-xs btn-primary btn-update-med" ' +
      'data-entry="' +
      e.name +
      '" ' +
      'data-drug="' +
      (e.drug_name || e.drug) +
      '" ' +
      'data-time="' +
      time_display +
      '">' +
      __("Update") +
      "</button>" +
      "</td>" +
      "</tr>";
  });

  html += "</tbody></table>";
  $wrapper.html(html);

  // Bind click handlers
  $wrapper.find(".btn-update-med").on("click", function () {
    let entry_name = $(this).data("entry");
    let drug_name = $(this).data("drug");
    let sched_time = $(this).data("time");
    show_update_medication_dialog(frm, entry_name, drug_name, sched_time);
  });
}

function show_update_medication_dialog(
  frm,
  entry_name,
  drug_name,
  sched_time
) {
  let d = new frappe.ui.Dialog({
    title: __("Update Medication Status"),
    fields: [
      {
        fieldname: "drug_info",
        fieldtype: "HTML",
        options:
          '<div class="mb-3" style="padding: 8px; background: var(--bg-light-gray); border-radius: 4px;">' +
          "<strong>" +
          drug_name +
          "</strong>" +
          (sched_time
            ? " &mdash; " + __("Scheduled") + ": " + sched_time
            : "") +
          "</div>",
      },
      {
        fieldname: "status",
        fieldtype: "Select",
        label: __("Status"),
        options: "Administered\nSkipped\nRefused\nHeld",
        default: "Administered",
        reqd: 1,
      },
      {
        fieldname: "notes",
        fieldtype: "Small Text",
        label: __("Notes"),
        description: __(
          "Required when skipping, refusing, or holding a medication."
        ),
        mandatory_depends_on: 'eval:doc.status!="Administered"',
      },
    ],
    primary_action_label: __("Confirm"),
    primary_action(values) {
      if (values.status !== "Administered" && !values.notes) {
        frappe.msgprint(
          __("Please provide a reason in the Notes field for {0}.", [
            values.status,
          ])
        );
        return;
      }

      frappe.call({
        method:
          "hms_tz.hms_tz.doctype.nurse_record.nurse_record.update_medication_status",
        args: {
          imo_entry_name: entry_name,
          status: values.status,
          notes: values.notes || "",
          nurse_record: frm.doc.name,
        },
        callback: (r) => {
          if (r.message && r.message.status === "success") {
            let indicator =
              values.status === "Administered" ? "green" : "orange";
            frappe.show_alert({
              message: __("Medication marked as {0}", [values.status]),
              indicator: indicator,
            });
            d.hide();
            render_pending_medications(frm);
            render_medication_progress(frm);
            render_completed_medications(frm);
          }
        },
      });
    },
  });

  d.show();
}

function render_medication_progress(frm) {
  if (!frm.fields_dict.medication_progress_html) return;
  if (!frm.doc.patient || !frm.doc.inpatient_record) {
    frm.fields_dict.medication_progress_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Medication progress will appear once medications are ordered.") +
        "</div>"
    );
    return;
  }

  frappe.call({
    method:
      "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_medication_progress",
    args: {
      patient: frm.doc.patient,
      inpatient_record: frm.doc.inpatient_record,
    },
    callback: (r) => {
      if (r.message && r.message.length > 0) {
        render_med_progress_chart(frm, r.message);
      } else {
        frm.fields_dict.medication_progress_html.$wrapper.html(
          '<div class="text-muted text-center p-4">' +
            __("No medication orders found for this patient.") +
            "</div>"
        );
      }
    },
  });
}

function render_med_progress_chart(frm, data) {
  let $wrapper = frm.fields_dict.medication_progress_html.$wrapper;
  $wrapper.empty();

  let chart_id = "med-progress-chart-" + frm.doc.name;
  $wrapper.append('<div class="mb-3"><div id="' + chart_id + '"></div></div>');

  let labels = data.map((d) => d.drug_name);
  let completed_values = data.map((d) => d.completed);
  let pending_values = data.map((d) => d.pending);

  new frappe.Chart("#" + chart_id, {
    title: __("Medication Administration Progress"),
    data: {
      labels: labels,
      datasets: [
        {
          name: __("Administered"),
          values: completed_values,
          chartType: "bar",
        },
        {
          name: __("Pending"),
          values: pending_values,
          chartType: "bar",
        },
      ],
    },
    type: "bar",
    height: 250,
    colors: ["#36a2eb", "#ff6384"],
    barOptions: {
      stacked: 1,
      spaceRatio: 0.4,
    },
  });

  // Summary table below chart
  // let summary_html =
  //   '<table class="table table-sm table-bordered mt-2">' +
  //   "<thead><tr>" +
  //   "<th>" +
  //   __("Drug") +
  //   "</th>" +
  //   "<th class='text-center'>" +
  //   __("Total") +
  //   "</th>" +
  //   "<th class='text-center'>" +
  //   __("Administered") +
  //   "</th>" +
  //   "<th class='text-center'>" +
  //   __("Pending") +
  //   "</th>" +
  //   "</tr></thead><tbody>";

  // data.forEach((d) => {
  //   let pct = d.total > 0 ? Math.round((d.completed / d.total) * 100) : 0;
  //   let badge_class =
  //     pct === 100
  //       ? "badge-success"
  //       : pct > 50
  //         ? "badge-warning"
  //         : "badge-danger";

  //   summary_html +=
  //     "<tr>" +
  //     "<td>" +
  //     d.drug_name +
  //     "</td>" +
  //     '<td class="text-center">' +
  //     d.total +
  //     "</td>" +
  //     '<td class="text-center">' +
  //     d.completed +
  //     "</td>" +
  //     '<td class="text-center">' +
  //     '<span class="badge ' +
  //     badge_class +
  //     '">' +
  //     d.pending +
  //     "</span>" +
  //     "</td></tr>";
  // });

  // summary_html += "</tbody></table>";
  // $wrapper.append(summary_html);
}

function render_completed_medications(frm) {
  if (!frm.fields_dict.completed_medications_html) return;
  if (!frm.doc.patient || !frm.doc.inpatient_record) {
    frm.fields_dict.completed_medications_html.$wrapper.html("");
    return;
  }

  frappe.call({
    method:
      "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_completed_medications",
    args: {
      patient: frm.doc.patient,
      inpatient_record: frm.doc.inpatient_record,
    },
    callback: (r) => {
      if (r.message && r.message.length > 0) {
        render_completed_meds_table(frm, r.message);
      } else {
        frm.fields_dict.completed_medications_html.$wrapper.html(
          '<div class="text-muted text-center p-3">' +
            __("No completed medications yet.") +
            "</div>"
        );
      }
    },
  });
}

function render_completed_meds_table(frm, entries) {
  let $wrapper = frm.fields_dict.completed_medications_html.$wrapper;
  $wrapper.empty();

  let html =
    '<table class="table table-sm table-bordered">' +
    "<thead><tr>" +
    "<th>" +
    __("Drug") +
    "</th>" +
    "<th>" +
    __("Dose(s)") +
    "</th>" +
    "<th>" +
    __("Form") +
    "</th>" +
    "<th>" +
    __("Date") +
    "</th>" +
    "<th>" +
    __("Time") +
    "</th>" +
    "<th>" +
    __("Status") +
    "</th>" +
    "<th>" +
    __("Given By") +
    "</th>" +
    "<th>" +
    __("Notes") +
    "</th>" +
    "</tr></thead><tbody>";

  entries.forEach((e) => {
    let status = e.administration_status || __("Administered");
    let status_color =
      status === "Administered"
        ? "green"
        : status === "Held"
        ? "orange"
        : "red";

    html +=
      "<tr>" +
      "<td>" +
      (e.drug_name || e.drug) +
      "</td>" +
      "<td>" +
      ((e.dosage || "") + (e.dose_uom ? " " + e.dose_uom : "")) +
      "</td>" +
      "<td>" +
      (e.dosage_form || "") +
      "</td>" +
      "<td>" +
      (e.date || "") +
      "</td>" +
      "<td>" +
      (e.time || "") +
      "</td>" +
      '<td><span class="indicator-pill ' +
      status_color +
      '">' +
      status +
      "</span></td>" +
      "<td>" +
      (e.administered_by_name || "") +
      "</td>" +
      "<td>" +
      (e.administration_notes || "") +
      "</td>" +
      "</tr>";
  });

  html += "</tbody></table>";
  $wrapper.append(html);
}

function check_upcoming_medications(frm) {
  if (!frm.doc.nurse || frm.is_new()) return;

  frappe.call({
    method:
      "hms_tz.hms_tz.doctype.nurse_record.nurse_record.get_upcoming_medications",
    args: {
      nurse: frm.doc.nurse,
      within_minutes: 60,
    },
    callback: (r) => {
      if (r.message && r.message.length > 0) {
        show_medication_alert_banner(frm, r.message);
      }
    },
  });
}

function show_medication_alert_banner(frm, medications) {
  let total_count = medications.length;

  // Add dashboard indicator pill with icon
  frm.dashboard.add_indicator(
    "💊 " + __("{0} Upcoming Medication(s) within next 1 hour", [total_count]),
    total_count > 5 ? "red" : "orange"
  );

  // Build the medication table HTML
  let rows = medications
    .map((med) => {
      let url = frappe.utils.get_form_link(
        "Nurse Record",
        med.nurse_record_name
      );
      let time_display = med.scheduled_time
        ? med.scheduled_time.substring(0, 5)
        : "";

      return (
        "<tr>" +
        '<td><a href="' +
        url +
        '">' +
        frappe.utils.escape_html(med.patient_name) +
        "</a></td>" +
        "<td>" +
        frappe.utils.escape_html(med.drug_name || "") +
        "</td>" +
        "<td>" +
        frappe.utils.escape_html(
          (med.dosage || "") + (med.dose_uom ? " " + med.dose_uom : "")
        ) +
        "</td>" +
        "<td>" +
        frappe.utils.escape_html(med.dosage_form || "") +
        "</td>" +
        "<td><strong>" +
        time_display +
        "</strong></td>" +
        "</tr>"
      );
    })
    .join("");

  let section_html =
    '<div style="background: #fff8e1; border-left: 4px solid #ff9800; ' +
    'border-radius: 4px; padding: 8px; max-height: 250px; overflow-y: auto;">' +
    '<table class="table table-sm mb-0" ' +
    'style="background: transparent; margin: 0;">' +
    "<thead>" +
    '<tr style="font-size: 11px; text-transform: uppercase; ' +
    'color: #6d4c00; border-bottom: 2px solid #ffe0b2;">' +
    "<th>" +
    __("Patient") +
    "</th>" +
    "<th>" +
    __("Drug") +
    "</th>" +
    "<th>" +
    __("Dose(s)") +
    "</th>" +
    "<th>" +
    __("Dosage Form") +
    "</th>" +
    "<th>" +
    __("Scheduled Time") +
    "</th>" +
    "</tr>" +
    "</thead>" +
    "<tbody>" +
    rows +
    "</tbody>" +
    "</table>" +
    "</div>";

  frm.dashboard.add_section(section_html);
  frm.dashboard.show();
}

function render_consumables_placeholder(frm) {
  if (!frm.fields_dict.consumables_html) return;

  if (frm.is_new() || !frm.doc.patient) {
    frm.fields_dict.consumables_html.$wrapper.html(
      '<div class="text-muted text-center p-4">' +
        __("Save the Nurse Record first to add consumables.") +
        "</div>"
    );
    return;
  }

  // Add the "Add Consumables" button
  const $wrapper = frm.fields_dict.consumables_html.$wrapper;
  $wrapper.empty();

  if (frm.doc.docstatus < 2) {
    const $btn_container = $(
      '<div class="d-flex justify-content-end mb-3" style="gap: 8px;"></div>'
    ).appendTo($wrapper);

    // "Add Consumables" button
    $('<button class="btn btn-primary btn-sm">')
      .html('<i class="fa fa-plus mr-1"></i>' + __("Add Consumables"))
      .on("click", () => {
        if (!window.hms_tz || !hms_tz.open_consumable_dialog) {
          frappe.msgprint(
            __("Consumable dialog not loaded. Please reload the page.")
          );
          return;
        }
        hms_tz.open_consumable_dialog({
          patient: frm.doc.patient,
          patient_name: frm.doc.patient_name,
          appointment: frm.doc.appointment,
          company: frm.doc.company,
          payment_type: frm.doc.payment_type || "Cash",
          insurance_subscription: frm.doc.insurance_subscription || "",
          insurance_company: frm.doc.insurance_company || "",
          insurance_coverage_plan: frm.doc.insurance_coverage_plan || "",
          prescribed_by: frm.doc.nurse || "",
          source_doctype: "",
          source_docname: "",
          on_success: () => {
            frm.reload_doc();
          },
        });
      })
      .appendTo($btn_container);
  }

  // Fetch and display existing consumable records
  frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Consumable Record",
      filters: {
        appointment: frm.doc.appointment,
      },
      fields: [
        "name",
        "posting_date",
        "status",
        "total_amount",
        "payment_type",
        "delivery_note",
        "docstatus",
      ],
      order_by: "creation desc",
      limit_page_length: 50,
    },
    callback: (r) => {
      if (!r.message || r.message.length === 0) {
        $('<div class="text-muted text-center p-3">')
          .text(__("No consumable records yet."))
          .appendTo($wrapper);
        return;
      }

      const records = r.message;
      let table_html =
        '<div class="table-responsive"><table class="table table-bordered table-sm">';
      table_html += "<thead><tr>";
      table_html += '<th class="text-left">' + __("Record") + "</th>";
      table_html += '<th class="text-left">' + __("Date") + "</th>";
      table_html += '<th class="text-left">' + __("Payment") + "</th>";
      table_html += '<th class="text-right">' + __("Total") + "</th>";
      table_html += '<th class="text-center">' + __("Status") + "</th>";
      table_html += '<th class="text-left">' + __("Delivery Note") + "</th>";
      table_html += '<th class="text-center">' + __("Action") + "</th>";
      table_html += "</tr></thead><tbody>";

      records.forEach((rec) => {
        const status_color = {
          Draft: "orange",
          Submitted: "blue",
          "Pending Payment": "red",
          Dispensed: "green",
          Finalized: "darkgreen",
          Billed: "purple",
        };
        const color = status_color[rec.status] || "gray";

        table_html += "<tr>";
        table_html +=
          '<td><a href="/app/consumable-record/' +
          rec.name +
          '">' +
          rec.name +
          "</a></td>";
        table_html += "<td>" + (rec.posting_date || "") + "</td>";
        table_html += "<td>" + (rec.payment_type || "") + "</td>";
        table_html +=
          '<td class="text-right">' +
          format_currency(rec.total_amount || 0) +
          "</td>";
        table_html +=
          '<td class="text-center"><span class="indicator-pill ' +
          color +
          '">' +
          (rec.status || "Draft") +
          "</span></td>";
        table_html +=
          "<td>" +
          (rec.delivery_note
            ? '<a href="/app/delivery-note/' +
              rec.delivery_note +
              '">' +
              rec.delivery_note +
              "</a>"
            : "-") +
          "</td>";

        // Action column — Submit button for draft records
        if (rec.docstatus === 0) {
          table_html +=
            '<td class="text-center">' +
            '<button class="btn btn-xs btn-primary btn-submit-consumable" data-name="' +
            rec.name +
            '">' +
            __("Submit") +
            "</button></td>";
        } else {
          table_html += '<td class="text-center">-</td>';
        }

        table_html += "</tr>";
      });

      table_html += "</tbody></table></div>";
      const $table = $(table_html).appendTo($wrapper);

      // Wire submit buttons
      $table.find(".btn-submit-consumable").on("click", function () {
        const consumable_name = $(this).data("name");
        frappe.confirm(
          __("Are you sure you want to submit Consumable Record {0}?", [
            consumable_name,
          ]),
          () => {
            frappe.call({
              method:
                "hms_tz.hms_tz.doctype.consumable_record.consumable_api.submit_consumable_record",
              args: { consumable_record: consumable_name },
              freeze: true,
              freeze_message: __("Submitting..."),
              callback: (r) => {
                if (!r.exc) {
                  frappe.show_alert({
                    message: __("Consumable Record {0} submitted.", [
                      consumable_name,
                    ]),
                    indicator: "green",
                  });
                  frm.reload_doc();
                }
              },
            });
          }
        );
      });
    },
  });
}

function render_age(frm) {
  if (!frm.fields_dict.age || !frm.fields_dict.age.$wrapper) return;

  if (!frm.doc.patient) {
    frm.fields_dict.age.$wrapper.html("");
    return;
  }

  frappe.call({
    method: "frappe.client.get_value",
    args: {
      doctype: "Patient",
      filters: { name: frm.doc.patient },
      fieldname: "dob",
    },
    callback: (r) => {
      if (r.message && r.message.dob) {
        const age_str = get_age(r.message.dob);
        frm.fields_dict.age.$wrapper.html(
          `<div class="clearfix"><span class="text-muted">${__(
            "AGE"
          )} : ${age_str}</span></div>`
        );
      } else {
        frm.fields_dict.age.$wrapper.html("");
      }
    },
  });
}

const get_age = function (birth) {
  let birth_moment = moment(birth);
  let current_moment = moment(Date());
  let diff = moment.duration(current_moment.diff(birth_moment));
  return `${diff.years()} ${__("Year(s)")} ${diff.months()} ${__(
    "Month(s)"
  )} ${diff.days()} ${__("Day(s)")}`;
};
