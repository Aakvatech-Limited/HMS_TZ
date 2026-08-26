from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient": [
			{
				"fieldname": "codification_table",
				"label": "Codification Table",
				"fieldtype": "Table",
				"options": "Codification Table",
				"insert_after": "chronic_section",
			}
		],
		"Patient Encounter": [
			{
				"fieldname": "system_and_symptoms",
				"label": "",
				"fieldtype": "Table",
				"insert_after": "symptoms_and_signs",
				"options": "Patient Encounter Symptom",
			},
			{
				"fieldname": "patient_encounter_preliminary_diagnosis",
				"label": "Preliminary Diagnosis",
				"fieldtype": "Table",
				"insert_after": "hms_tz_section_break",
				"options": "Codification Table",
			},
			{
				"fieldname": "column_break_lygpq",
				"fieldtype": "Column Break",
				"insert_after": "patient_encounter_preliminary_diagnosis",
			},
			{
				"fieldname": "patient_encounter_final_diagnosis",
				"label": "Final Diagnosis",
				"fieldtype": "Table",
				"insert_after": "column_break_lygpq",
				"options": "Codification Table",
			},
		],
		"Healthcare Settings": [
			{
				"fieldname": "automate_appointment_invoicing",
				"label": "Automate Appointment Invoicing",
				"fieldtype": "Check",
				"insert_after": "show_payment_popup",
				"description": "Manage Appointment Invoice submit and cancel automatically for Patient Encounter",
			}
		],
		"Drug Prescription": [
			{
				"fieldname": "delivery_note",
				"label": "Delivery Note",
				"fieldtype": "Data",
				"read_only": 1,
				"insert_after": "dn_detail",
			}
		],
		"Lab Test": [
			{
				"fieldname": "appointment",
				"label": "Appointment",
				"fieldtype": "Data",
				"insert_after": "patient_sex",
				"read_only": 1,
			}
		],
		"Clinical Procedure": [
			{
				"fieldname": "workflow_state",
				"label": "Workflow State",
				"fieldtype": "Link",
				"options": "Workflow State",
				"hidden": 1,
			},
			{
				"fieldname": "is_restricted",
				"label": "Is Restricted",
				"fieldtype": "Check",
				"insert_after": "procedure_template",
				"read_only": 1,
			},
			{
				"fieldname": "approval_number",
				"label": "Approval Number",
				"fieldtype": "Data",
				"insert_after": "notes",
			},
			{
				"fieldname": "approval_type",
				"label": "Approval Type",
				"fieldtype": "Select",
				"insert_after": "approval_number",
				"options": "Local\nNHIF\nOther Insurance",
			},
			{
				"fieldname": "prescribe",
				"label": "Prescribe",
				"fieldtype": "Check",
				"insert_after": "invoiced",
				"read_only": 1,
			},
			{
				"fieldname": "service_comment",
				"label": "Service Comment",
				"fieldtype": "Text",
				"insert_after": "practitioner_name",
			},
			{
				"fieldname": "insurance_section",
				"label": "Insurance Section",
				"fieldtype": "Section Break",
				"insert_after": "sample",
				"depends_on": "eval:doc.prescribe == 1",
				"collapsible": 1,
			},
			{
				"fieldname": "insurance_subscription",
				"label": "Insurance Subscription",
				"fieldtype": "Link",
				"options": "Healthcare Insurance Subscription",
				"insert_after": "insurance_section",
				"read_only": 1,
				"translatable": 1,
			},
			{
				"fieldname": "hms_tz_insurance_coverage_plan",
				"fieldtype": "Data",
				"insert_after": "insurance_subscription",
				"label": "Insurance Coverage Plan",
				"fetch_if_empty": 1,
				"fetch_from": "insurance_subscription.healthcare_insurance_coverage_plan",
				"read_only": 1,
			},
			{
				"fieldname": "column_break_31",
				"fieldtype": "Column Break",
				"insert_after": "hms_tz_insurance_coverage_plan",
			},
			{
				"fieldname": "insurance_company",
				"label": "Insurance Company",
				"fieldtype": "Link",
				"options": "Healthcare Insurance Company",
				"insert_after": "column_break_31",
				"fetch_if_empty": 1,
				"fetch_from": "insurance_subscription.insurance_company",
				"read_only": 1,
			},
			{
				"fieldname": "section_break_38",
				"fieldtype": "Section Break",
				"insert_after": "insurance_company",
			},
			{
				"fieldname": "mtuha",
				"label": "MTUHA",
				"fieldtype": "Link",
				"insert_after": "section_break_38",
				"options": "MTUHA",
			},
			{
				"fieldname": "healthcare_notes_template",
				"label": "Healthcare Notes Template",
				"fieldtype": "Link",
				"insert_after": "mtuha",
				"options": "Healthcare Notes Template",
				"fetch_from": "procedure_template.healthcare_notes_template",
			},
			{
				"fieldname": "procedure_notes",
				"label": "Procedure Notes",
				"fieldtype": "Text Editor",
				"insert_after": "healthcare_notes_template",
				"fetch_from": "healthcare_notes_template.terms",
			},
			{
				"fieldname": "pre_operative_notes_template",
				"label": "Pre Operative Notes Template",
				"fieldtype": "Link",
				"insert_after": "procedure_notes",
				"options": "Healthcare Notes Template",
				"fetch_from": "procedure_template.healthcare_notes_template",
				"hidden": 1,
			},
			{
				"fieldname": "pre_operative_note",
				"label": "Pre Operative Note",
				"fieldtype": "Text Editor",
				"insert_after": "pre_operative_notes_template",
				"fetch_from": "pre_operative_notes_template.terms",
				"hidden": 1,
			},
			{
				"fieldname": "ref_doctype",
				"label": "Ref DocType",
				"fieldtype": "Link",
				"insert_after": "amended_from",
				"options": "DocType",
			},
			{
				"fieldname": "ref_docname",
				"label": "Ref DocName",
				"fieldtype": "Dynamic Link",
				"insert_after": "ref_doctype",
				"options": "ref_doctype",
			},
			{
				"fieldname": "hms_tz_ref_childname",
				"label": "Ref Childname",
				"fieldtype": "Data",
				"insert_after": "ref_docname",
				"read_only": 1,
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "patient",
				"label": "Patient",
				"fieldtype": "Link",
				"options": "Patient",
				"insert_after": "naming_series",
			},
			{
				"fieldname": "patient_name",
				"label": "Patient Name",
				"fieldtype": "Data",
				"insert_after": "patient",
				"read_only": 1,
				"fetch_from": "patient.patient_name",
			},
			{
				"fieldname": "service_unit",
				"label": "Service Unit",
				"fieldtype": "Link",
				"insert_after": "delivery_status",
				"options": "Healthcare Service Unit",
			},
		],
		"Sales Invoice Item": [
			{
				"fieldname": "reference_dt",
				"label": "Reference DocType",
				"fieldtype": "Link",
				"options": "DocType",
				"insert_after": "edit_references",
				"read_only": 1,
			},
			{
				"fieldname": "reference_dn",
				"label": "Reference Name",
				"fieldtype": "Dynamic Link",
				"options": "reference_dt",
				"insert_after": "reference_dt",
				"read_only": 1,
			},
			{
				"fieldname": "service_unit",
				"label": "Service Unit",
				"fieldtype": "Link",
				"insert_after": "page_break",
				"options": "Healthcare Service Unit",
			},
		],
	}

	create_custom_fields(fields, update=True)
