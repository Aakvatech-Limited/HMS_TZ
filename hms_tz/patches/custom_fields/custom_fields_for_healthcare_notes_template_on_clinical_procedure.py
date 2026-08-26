from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Clinical Procedure": [
			{
				"label": "Healthcare Notes Template",
				"fieldname": "healthcare_notes_template",
				"insert_after": "mtuha",
				"fieldtype": "Link",
				"options": "Healthcare Notes Template",
				"fetch_from": "procedure_template.healthcare_notes_template",
				"fetch_if_empty": 1,
			}
		]
	}
	create_custom_fields(fields, update=True)
