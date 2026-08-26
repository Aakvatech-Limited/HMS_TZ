from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient": [
			{
				"fieldname": "scheme_id",
				"fieldtype": "Data",
				"label": "Scheme ID",
				"insert_after": "product_code",
				"read_only": 1,
				"hidden": 1,
			}
		]
	}
	create_custom_fields(fields, update=True)
