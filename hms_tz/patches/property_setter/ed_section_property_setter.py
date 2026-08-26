import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	properties = [
		{
			"property": "label",
			"value": "ED Section",
			"property_type": "Data",
		},
		{
			"property": "collapsible",
			"value": 1,
			"property_type": "Check",
		},
	]

	for prop in properties:
		make_property_setter(
			"Patient Encounter",
			"section_break_33",
			prop["property"],
			prop["value"],
			prop["property_type"],
			for_doctype=False,
			validate_fields_for_doctype=True,
		)
	frappe.db.commit()
