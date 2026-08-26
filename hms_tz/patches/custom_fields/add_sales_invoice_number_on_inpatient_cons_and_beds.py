from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Inpatient Occupancy": [
			{
				"fieldname": "sales_invoice_number",
				"fieldtype": "Data",
				"label": "Sales Invoice Number",
				"insert_after": "is_confirmed",
				"read_only": 1,
				"allow_on_submit": 1,
				"translatable": 1,
			}
		],
		"Inpatient Consultancy": [
			{
				"fieldname": "hms_tz_invoiced",
				"fieldtype": "Check",
				"label": "Invoiced",
				"insert_after": "healthcare_practitioner",
				"read_only": 1,
				"allow_on_submit": 1,
				"translatable": 1,
			},
			{
				"fieldname": "sales_invoice_number",
				"fieldtype": "Data",
				"label": "Sales Invoice Number",
				"insert_after": "is_confirmed",
				"read_only": 1,
				"allow_on_submit": 1,
				"translatable": 1,
			},
		],
	}
	create_custom_fields(fields)
