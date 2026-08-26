import frappe
from frappe.utils import add_days, nowdate


def execute():
	before_4_days_date = add_days(nowdate(), -4)
	delivery_notes = frappe.get_all(
		"Delivery Note",
		filters={"docstatus": 0, "posting_date": [">=", before_4_days_date]},
	)

	if not delivery_notes:
		return

	for dn in delivery_notes:
		dn_doc = frappe.get_cached_doc("Delivery Note", dn.name)

		if len(dn_doc.hms_tz_original_items) > 0:
			continue

		try:
			set_original_item(dn_doc)

		except Exception:
			frappe.log_error(frappe.get_traceback(), "Update original items via Patch")


def set_original_item(doc):
	for item in doc.items:
		new_row = item.as_dict()
		for fieldname in get_fields_to_clear():
			new_row[fieldname] = None

		new_row.update(
			{
				"parent": doc.name,
				"parentfield": "hms_tz_original_items",
				"parenttype": "Delivery Note",
				"doctype": "Original Delivery Note Item",
			}
		)
		doc.append("hms_tz_original_items", new_row)
	doc.save(ignore_permissions=True)


def get_fields_to_clear():
	return [
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
	]
