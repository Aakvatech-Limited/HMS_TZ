from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Healthcare Insurance Coverage Plan": [
			{
				"fieldname": "hms_tz_submit_encounter_on_limit_exceed",
				"fieldtype": "Check",
				"label": "Submit Encounter on Limit Exceed",
				"insert_after": "daily_limit",
				"description": "If ticked, Practitioner will be able to submit encounter even if the Daily Limit is exceeded",
			}
		],
		"Lab Prescription": [
			{
				"fieldname": "hms_tz_is_limit_exceeded",
				"fieldtype": "Check",
				"label": "Is Limit Exceeded",
				"insert_after": "reference_journal_entry",
				"read_only": 1,
				"allow_on_submit": 1,
			}
		],
		"Radiology Procedure Prescription": [
			{
				"fieldname": "hms_tz_is_limit_exceeded",
				"fieldtype": "Check",
				"label": "Is Limit Exceeded",
				"insert_after": "reference_journal_entry",
				"read_only": 1,
				"allow_on_submit": 1,
			}
		],
		"Procedure Prescription": [
			{
				"fieldname": "hms_tz_is_limit_exceeded",
				"fieldtype": "Check",
				"label": "Is Limit Exceeded",
				"insert_after": "reference_journal_entry",
				"read_only": 1,
				"allow_on_submit": 1,
			}
		],
		"Drug Prescription": [
			{
				"fieldname": "hms_tz_is_limit_exceeded",
				"fieldtype": "Check",
				"label": "Is Limit Exceeded",
				"insert_after": "reference_journal_entry",
				"read_only": 1,
				"allow_on_submit": 1,
			}
		],
		"Therapy Plan Detail": [
			{
				"fieldname": "hms_tz_is_limit_exceeded",
				"fieldtype": "Check",
				"label": "Is Limit Exceeded",
				"insert_after": "reference_journal_entry",
				"read_only": 1,
				"allow_on_submit": 1,
			}
		],
	}

	create_custom_fields(fields, update=True)
