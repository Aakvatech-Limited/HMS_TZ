import frappe


def execute():
	"""Duplicating a Delivery Note copied its original items, and after_insert appended them again,
	so the table grew with every generation of duplicates."""
	frappe.db.set_value(
		"Custom Field",
		{"dt": "Delivery Note", "fieldname": "hms_tz_original_items"},
		"no_copy",
		1,
	)
	frappe.clear_cache(doctype="Delivery Note")
