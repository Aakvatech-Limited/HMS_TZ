import frappe
from frappe.utils.global_search import rebuild_for_doctype

DOCTYPE = "Healthcare Insurance Subscription"


def execute():
	"""Let global search find a subscription by patient name, mobile and card no."""
	frappe.db.set_value("Custom Field", f"{DOCTYPE}-coverage_plan_card_number", "in_global_search", 1)
	frappe.clear_cache(doctype=DOCTYPE)

	# Saving Global Search Settings loads the meta of every listed doctype, and sites still list removed
	# ones (e.g. Loan), so only the new row is inserted.
	if not frappe.db.exists("Global Search DocType", {"document_type": DOCTYPE}):
		frappe.get_doc(
			{
				"doctype": "Global Search DocType",
				"parent": "Global Search Settings",
				"parenttype": "Global Search Settings",
				"parentfield": "allowed_in_global_search",
				"document_type": DOCTYPE,
				"idx": frappe.db.count("Global Search DocType") + 1,
			}
		).db_insert()
		frappe.cache.hdel("global_search", "search_priorities")

	rebuild_for_doctype(DOCTYPE)
