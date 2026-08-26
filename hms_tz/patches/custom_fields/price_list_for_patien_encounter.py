from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Encounter": [
			{
				"fieldname": "price_list",
				"fieldtype": "Link",
				"options": "Price List",
				"label": "Price List",
				"insert_after": "encounter_mode_of_payment",
				"read_only": 1,
				"allow_on_submit": 0,
			}
		]
	}

	create_custom_fields(fields, update=True)
