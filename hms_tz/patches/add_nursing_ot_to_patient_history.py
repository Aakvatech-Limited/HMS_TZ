"""Add Nursing & OT DocTypes to Patient History Settings.

Registers Nurse Record, Preoperative Assessment, Anesthesia Record,
Postoperative Recovery, and Implant Registry as custom doctypes
in Patient History Settings so they appear in tz_patient_history.

Also updates Clinical Procedure's standard_doctypes entry with
newly added OT fields (intraoperative, WHO checklist, post-op, etc.).
"""

import json

import frappe


def execute():
	settings = frappe.get_single("Patient History Settings")

	_add_nursing_ot_doctypes(settings)

	_update_clinical_procedure_fields(settings)

	settings.save(ignore_permissions=True)
	frappe.db.commit()


def _add_nursing_ot_doctypes(settings):
	"""Add new doctypes to custom_doctypes table."""
	new_doctypes = get_nursing_ot_history_config()
	existing = {d.document_type for d in settings.custom_doctypes}

	for dt, config in new_doctypes.items():
		if dt not in existing:
			settings.append(
				"custom_doctypes",
				{
					"document_type": dt,
					"date_fieldname": config[0],
					"selected_fields": json.dumps(config[1]),
				},
			)


def _update_clinical_procedure_fields(settings):
	"""Update Clinical Procedure entry in standard_doctypes with new OT fields."""
	new_fields = get_clinical_procedure_ot_fields()

	for entry in settings.standard_doctypes:
		if entry.document_type == "Clinical Procedure":
			existing_fields = json.loads(entry.selected_fields) if entry.selected_fields else []
			existing_fieldnames = {f["fieldname"] for f in existing_fields}

			for nf in new_fields:
				if nf["fieldname"] not in existing_fieldnames:
					existing_fields.append(nf)

			entry.selected_fields = json.dumps(existing_fields)
			break


def get_nursing_ot_history_config():
	"""Return configuration for new Nursing/OT doctypes.

	Format: {DocType: (date_fieldname, [selected_fields])}
	"""
	return {
		"Nurse Record": (
			"posting_date",
			[
				{"label": "Patient", "fieldname": "patient", "fieldtype": "Link"},
				{"label": "Patient Name", "fieldname": "patient_name", "fieldtype": "Data"},
				{"label": "Gender", "fieldname": "patient_sex", "fieldtype": "Link"},
				{"label": "Nurse", "fieldname": "nurse", "fieldtype": "Link"},
				{"label": "Inpatient Record", "fieldname": "inpatient_record", "fieldtype": "Link"},
				{"label": "Service Unit", "fieldname": "service_unit", "fieldtype": "Link"},
				{"label": "Service Unit Type", "fieldname": "service_unit_type", "fieldtype": "Link"},
				{"label": "Observations", "fieldname": "observations", "fieldtype": "Table"},
				{"label": "Patient Progress", "fieldname": "patient_progress", "fieldtype": "Table"},
			],
		),
		"Preoperative Assessment": (
			"posting_date",
			[
				{"label": "Patient", "fieldname": "patient", "fieldtype": "Link"},
				{"label": "Patient Name", "fieldname": "patient_name", "fieldtype": "Data"},
				{"label": "OT Schedule", "fieldname": "ot_schedule", "fieldtype": "Link"},
				{"label": "Clinical Procedure", "fieldname": "clinical_procedure", "fieldtype": "Link"},
				{
					"label": "Fasting Status Verified",
					"fieldname": "fasting_status_verified",
					"fieldtype": "Check",
				},
				{
					"label": "Blood Crossmatch Available",
					"fieldname": "blood_crossmatch_available",
					"fieldtype": "Check",
				},
				{"label": "Consent Signed", "fieldname": "consent_signed", "fieldtype": "Check"},
				{
					"label": "Site Marking Verified",
					"fieldname": "site_marking_verified",
					"fieldtype": "Check",
				},
				{"label": "IV Access Secured", "fieldname": "iv_access_secured", "fieldtype": "Check"},
				{"label": "Pre-Op Labs Reviewed", "fieldname": "pre_op_labs_reviewed", "fieldtype": "Check"},
				{"label": "Mallampati Score", "fieldname": "mallampati_score", "fieldtype": "Select"},
				{"label": "Blood Group", "fieldname": "blood_group", "fieldtype": "Select"},
				{
					"label": "Pre Operative Note",
					"fieldname": "pre_operative_note",
					"fieldtype": "Text Editor",
				},
				{"label": "Chronic Medications", "fieldname": "chronic_medications", "fieldtype": "Table"},
				{"label": "Allergies", "fieldname": "allergies", "fieldtype": "Small Text"},
				{"label": "Surgical History", "fieldname": "surgical_history", "fieldtype": "Text"},
			],
		),
		"Anesthesia Record": (
			"posting_date",
			[
				{"label": "Patient", "fieldname": "patient", "fieldtype": "Link"},
				{"label": "Patient Name", "fieldname": "patient_name", "fieldtype": "Data"},
				{"label": "OT Schedule", "fieldname": "ot_schedule", "fieldtype": "Link"},
				{"label": "Clinical Procedure", "fieldname": "clinical_procedure", "fieldtype": "Link"},
				{
					"label": "Pre Induction Vitals",
					"fieldname": "pre_induction_vitals",
					"fieldtype": "Small Text",
				},
				{
					"label": "Post Induction Vitals",
					"fieldname": "post_induction_vitals",
					"fieldtype": "Small Text",
				},
				{"label": "Notes", "fieldname": "notes", "fieldtype": "Small Text"},
				{"label": "Complications", "fieldname": "complications", "fieldtype": "Small Text"},
				{"label": "Drugs Administered", "fieldname": "drugs_administered", "fieldtype": "Table"},
				{"label": "Start Time", "fieldname": "start_time", "fieldtype": "Time"},
				{"label": "End Time", "fieldname": "end_time", "fieldtype": "Time"},
				{"label": "ASA Grade", "fieldname": "asa_grade", "fieldtype": "Select"},
				{"label": "Anesthesia Type", "fieldname": "anesthesia_type", "fieldtype": "Select"},
				{"label": "Anesthetist", "fieldname": "anesthetist", "fieldtype": "Link"},
			],
		),
		"Postoperative Recovery": (
			"posting_date",
			[
				{"label": "Patient", "fieldname": "patient", "fieldtype": "Link"},
				{"label": "Patient Name", "fieldname": "patient_name", "fieldtype": "Data"},
				{"label": "Recovery Nurse", "fieldname": "recovery_nurse", "fieldtype": "Link"},
				{"label": "OT Schedule", "fieldname": "ot_schedule", "fieldtype": "Link"},
				{"label": "Clinical Procedure", "fieldname": "clinical_procedure", "fieldtype": "Link"},
				{"label": "Status", "fieldname": "status", "fieldtype": "Select"},
				{"label": "Pain Level", "fieldname": "pain_level", "fieldtype": "Int"},
				{"label": "Admission to Recovery", "fieldname": "admission_time", "fieldtype": "Datetime"},
				{"label": "Discharge from Recovery", "fieldname": "discharge_time", "fieldtype": "Datetime"},
				{
					"label": "Discharge Criteria Met",
					"fieldname": "discharge_criteria_met",
					"fieldtype": "Check",
				},
				{"label": "Recovery Scores", "fieldname": "recovery_scores", "fieldtype": "Table"},
				{"label": "Complications", "fieldname": "complications", "fieldtype": "Small Text"},
				{"label": "Notes", "fieldname": "notes", "fieldtype": "Small Text"},
			],
		),
		"Implant Registry": (
			"implant_date",
			[
				{"label": "Patient", "fieldname": "patient", "fieldtype": "Link"},
				{"label": "Patient Name", "fieldname": "patient_name", "fieldtype": "Data"},
				{"label": "Implant Type", "fieldname": "implant_type", "fieldtype": "Data"},
				{"label": "Manufacturer", "fieldname": "manufacturer", "fieldtype": "Data"},
				{"label": "Lot Number", "fieldname": "lot_number", "fieldtype": "Data"},
				{"label": "Serial Number", "fieldname": "serial_number", "fieldtype": "Data"},
				{"label": "Expiry Date", "fieldname": "expiry_date", "fieldtype": "Date"},
				{"label": "Anatomical Location", "fieldname": "anatomical_location", "fieldtype": "Data"},
				{"label": "Implanted By", "fieldname": "implanted_by", "fieldtype": "Link"},
				{"label": "Status", "fieldname": "status", "fieldtype": "Select"},
				{"label": "Clinical Procedure", "fieldname": "clinical_procedure", "fieldtype": "Link"},
				{"label": "Notes", "fieldname": "notes", "fieldtype": "Small Text"},
			],
		),
	}


def get_clinical_procedure_ot_fields():
	"""Return additional OT fields for Clinical Procedure patient history."""
	return [
		{"label": "OT Schedule", "fieldname": "ot_schedule", "fieldtype": "Link"},
		{"label": "Anesthesia Type", "fieldname": "anesthesia_type", "fieldtype": "Select"},
		{"label": "Estimated Blood Loss (ml)", "fieldname": "estimated_blood_loss", "fieldtype": "Float"},
		{"label": "Incision Time", "fieldname": "incision_time", "fieldtype": "Time"},
		{"label": "Closure Time", "fieldname": "closure_time", "fieldtype": "Time"},
		{"label": "WHO Sign In", "fieldname": "who_sign_in", "fieldtype": "Check"},
		{"label": "WHO Time Out", "fieldname": "who_time_out", "fieldtype": "Check"},
		{"label": "WHO Sign Out", "fieldname": "who_sign_out", "fieldtype": "Check"},
		{"label": "Swab Count Before", "fieldname": "swab_count_before", "fieldtype": "Int"},
		{"label": "Swab Count After", "fieldname": "swab_count_after", "fieldtype": "Int"},
		{"label": "Instrument Count Before", "fieldname": "instrument_count_before", "fieldtype": "Int"},
		{"label": "Instrument Count After", "fieldname": "instrument_count_after", "fieldtype": "Int"},
		{"label": "Post-Op Instructions", "fieldname": "postop_instructions", "fieldtype": "Text"},
		{"label": "Recovery Location", "fieldname": "recovery_location", "fieldtype": "Link"},
		{"label": "Surgical Team", "fieldname": "surgical_team", "fieldtype": "Table"},
		{"label": "Pre-Operative Note", "fieldname": "pre_operative_note", "fieldtype": "Text Editor"},
		{"label": "Procedure Notes", "fieldname": "procedure_notes", "fieldtype": "Text Editor"},
	]
