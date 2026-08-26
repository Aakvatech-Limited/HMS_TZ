from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Appointment": [
			{
				"fieldname": "daily_limit",
				"fieldtype": "Float",
				"label": "Daily Limit",
				"insert_after": "insurance_subscription",
				"fetch_from": "appointment.daily_limit",
				"depends_on": "eval:doc.insurance_company != 'NHIF' ",
				"read_only": 1,
			}
		]
	}

	create_custom_fields(fields, update=True)
