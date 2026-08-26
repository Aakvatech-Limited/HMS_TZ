import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	for doctype in [
		"Lab Prescription",
		"Radiology Procedure Prescription",
		"Procedure Prescription",
		"Drug Prescription",
		"Therapy Plan Detail",
		"Diet Recommendation",
	]:
		custom_field_name = frappe.get_cached_value("Custom Field", f"{doctype}-medical_code", "name")
		if custom_field_name:
			frappe.db.set_value("Custom Field", f"{doctype}-medical_code", "reqd", 0)

	# frappe.reload_doc("custom", "doctype", "custom_field")
	# frappe.reload_doc("hms_tz", "doctype", "patient_encounter")

	fields = {
		"Healthcare Settings": [
			{
				"fieldname": "validate_medical_code_for_cash_patients",
				"label": "Validate Medical Code for Cash Patients",
				"fieldtype": "Check",
				"insert_after": "valid_days",
				"default": 1,
				"description": "If checked, system will validate medical code for cash patients on patient encounter",
			}
		],
		"Healthcare Insurance Company": [
			{
				"fieldname": "validate_medical_code_for_insurance_patients",
				"label": "Validate Medical Code for Insurance Patients",
				"fieldtype": "Check",
				"insert_after": "facility_code",
				"default": 1,
				"description": "If checked, system will validate medical code for insurance patients on patient encounter",
			}
		],
	}

	create_custom_fields(fields, update=True)
