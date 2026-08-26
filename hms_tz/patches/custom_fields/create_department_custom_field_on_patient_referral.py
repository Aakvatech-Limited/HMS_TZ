from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Referral": [
			{
				"fieldname": "department",
				"label": "Referred to Department",
				"fieldtype": "Link",
				"options": "Medical Department",
				"insert_after": "column_break_8",
			},
		],
	}

	create_custom_fields(fields, update=True)
