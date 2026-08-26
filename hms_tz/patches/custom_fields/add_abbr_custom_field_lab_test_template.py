from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = {
		"Lab Test Template": [
			{
				"fieldname": "abbr",
				"label": "Abbr",
				"fieldtype": "Data",
				"insert_after": "lab_test_name",
				"reqd": 1,
			}
		]
	}

	create_custom_fields(fields, update=True)
