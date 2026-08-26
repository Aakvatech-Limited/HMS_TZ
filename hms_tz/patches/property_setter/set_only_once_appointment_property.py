import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"Clinical Procedure",
		"appointment",
		"set_only_once",
		0,
		"Check",
		for_doctype=False,
		validate_fields_for_doctype=False,
	)
	frappe.db.commit()
