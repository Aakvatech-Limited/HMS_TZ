import frappe


def insert(doctype, name, **values):
	"""Insert a row directly, without controller validation, for test fixtures."""
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
