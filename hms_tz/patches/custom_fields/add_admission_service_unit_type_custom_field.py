from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Encounter": [
			{
				"fieldname": "admission_service_unit_type",
				"label": "Admission Service Unit Type",
				"fieldtype": "Link",
				"options": "Healthcare Service Unit Type",
				"insert_after": "inpatient_status",
				"read_only": 1,
				"in_standard_filter": 1,
			},
		]
	}

	create_custom_fields(fields, update=True)
