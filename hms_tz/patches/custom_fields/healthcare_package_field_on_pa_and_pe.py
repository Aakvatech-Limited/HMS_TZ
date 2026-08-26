from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Patient Appointment": [
			{
				"fieldname": "healthcare_package_order",
				"fieldtype": "Link",
				"label": "Healthcare Package Order",
				"options": "Healthcare Package Order",
				"insert_after": "hms_tz_is_discount_applied",
				"read_only": 1,
			}
		],
		"Patient Encounter": [
			{
				"fieldname": "healthcare_package_order",
				"fieldtype": "Link",
				"label": "Healthcare Package Order",
				"options": "Healthcare Package Order",
				"insert_after": "inpatient_status",
				"read_only": 1,
			}
		],
	}

	create_custom_fields(fields, update=True)
