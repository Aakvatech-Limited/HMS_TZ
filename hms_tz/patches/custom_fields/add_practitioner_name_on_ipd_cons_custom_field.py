from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Inpatient Consultancy": [
			{
				"fieldname": "healthcare_practitioner",
				"label": "Healthcare Practitioner",
				"fieldtype": "Link",
				"options": "Healthcare Practitioner",
				"insert_after": "encounter",
				"read_only": 1,
				"fetch_from": "encounter.practitioner",
				"fetch_if_empty": 1,
			},
			{
				"label": "Invoiced",
				"fieldname": "hms_tz_invoiced",
				"fieldtype": "Check",
				"insert_after": "healthcare_practitioner",
			},
		]
	}
	create_custom_fields(fields, update=True)
