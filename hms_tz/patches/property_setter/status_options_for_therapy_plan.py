import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	make_property_setter(
		"Therapy Plan",
		"status",
		"options",
		"Not Started\nIn Progress\nCompleted\nCancelled\nNot Serviced",
		"Text",
		for_doctype=False,
		validate_fields_for_doctype=False,
	)
	frappe.db.commit()
