import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"Inpatient Occupancy",
		"invoiced",
		"read_only",
		1,
		"Check",
		for_doctype=False,
		validate_fields_for_doctype=True,
	)
	frappe.db.commit()
