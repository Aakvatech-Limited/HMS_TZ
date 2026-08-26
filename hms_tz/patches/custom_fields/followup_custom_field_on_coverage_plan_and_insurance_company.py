from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Healthcare Insurance Company": [
			{
				"fieldname": "no_of_days_for_follow_up",
				"label": "Valid Number of Days for Follow Up",
				"fieldtype": "Int",
				"insert_after": "hms_tz_price_discount",
			}
		],
	}
	create_custom_fields(fields, update=True)
