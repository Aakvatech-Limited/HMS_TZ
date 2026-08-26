# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class HealthcarePackage(Document):
	pass


@frappe.whitelist()
def get_item_price(template_type, template, price_list, item_code=None):
	if not item_code:
		item_code = frappe.get_cached_value(template_type, template, "item")

	item_price = frappe.get_cached_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list},
		"price_list_rate",
	)

	if flt(item_price) == 0:
		frappe.throw(f"No Price settled for Item: <b>{template}</b> for price list: <b>{price_list}</b>")

	return item_price
