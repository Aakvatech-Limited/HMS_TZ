from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Medication": [
			{
				"fieldname": "allowed_price_lists",
				"fieldtype": "Table",
				"options": "Allowed Price List",
				"label": "Allowed Price Lists",
				"insert_after": "staff_role",
				"read_only": 0,
				"allow_on_submit": 0,
			}
		],
	}

	create_custom_fields(fields, update=True)
