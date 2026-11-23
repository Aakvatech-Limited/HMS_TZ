import frappe


def execute():
	"""NHIF sends plain visit type IDs such as "1" and "9", so Visit Type ID is free text, not the old "1-Normal Visit" options."""
	name = "Appointment Type-visit_type_id"
	if frappe.db.get_value("Custom Field", name, "fieldtype") != "Select":
		return
	field = frappe.get_doc("Custom Field", name)
	field.fieldtype = "Data"
	field.options = ""
	field.save()
