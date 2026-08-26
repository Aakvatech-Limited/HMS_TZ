from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Sample Collection": [
			{
				"fieldname": "lab_tests",
				"label": "Lab Tests",
				"fieldtype": "Table",
				"options": "Sample Collection Lab Test Details",
				"insert_after": "section_break_20",
			}
		]
	}

	create_custom_fields(fields, update=True)
