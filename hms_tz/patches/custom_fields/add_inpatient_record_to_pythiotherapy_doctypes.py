from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Therapy Plan": [
			{
				"fieldname": "inpatient_record",
				"label": "Inpatient Record",
				"fieldtype": "Link",
				"options": "Inpatient Record",
				"insert_after": "patient",
				"fecth_from": "patient.inpatient_record",
				"fetch_if_empty": 1,
			}
		],
		"Patient Assessment": [
			{
				"fieldname": "inpatient_record",
				"label": "Inpatient Record",
				"fieldtype": "Link",
				"options": "Inpatient Record",
				"insert_after": "patient",
				"fecth_from": "patient.inpatient_record",
				"fetch_if_empty": 1,
			}
		],
	}
	create_custom_fields(fields, update=True)
