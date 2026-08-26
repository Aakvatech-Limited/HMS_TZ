# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class NHIFScheme(Document):
	pass


def add_scheme(id, name=None):
	if frappe.db.exists("NHIF Scheme", id):
		if name and name != "null":
			doc = frappe.get_cached_doc("NHIF Scheme", id)
			if not doc.scheme_name:
				doc.scheme_name = name
				doc.save(ignore_permissions=True)
				frappe.db.commit()
	else:
		doc = frappe.new_doc("NHIF Scheme")
		doc.scheme_id = id
		if name and name != "null":
			doc.scheme_name = name
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	return id
