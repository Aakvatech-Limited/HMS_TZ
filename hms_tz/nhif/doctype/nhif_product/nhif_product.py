# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class NHIFProduct(Document):
	pass


def add_product(company, id, name=None):
	if not id:
		return
	abbr = frappe.get_cached_value("Company", company, "abbr")
	product_id = str(id) + "-" + str(abbr)
	nhif_product_pr_key = frappe.get_cached_value(
		"NHIF Product", {"company": company, "nhif_product_code": id}
	)
	if not nhif_product_pr_key:
		nhif_product_pr_key = frappe.get_cached_value(
			"NHIF Product", {"company": "", "nhif_product_code": id}
		)

	if nhif_product_pr_key:
		if name and name != "null" and product_id != nhif_product_pr_key:
			doc = frappe.get_cached_doc("NHIF Product", nhif_product_pr_key)

			doc.product_id = product_id
			doc.product_name = name
			doc.company = company
			doc.save(ignore_permissions=True)
			frappe.db.commit()
	else:
		doc = frappe.new_doc("NHIF Product")
		doc.product_id = product_id
		doc.company = company
		doc.nhif_product_code = id
		if name and name != "null":
			doc.product_name = name
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	return id
