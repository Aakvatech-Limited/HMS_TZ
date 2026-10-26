import frappe

DOCTYPES = [
	"Lab Test",
	"Radiology Examination",
	"Clinical Procedure",
	"Delivery Note Item",
	"Therapy Session",
]
DEPENDS_ON = "eval: doc.is_restricted == 1 && !doc.approval_number"


def execute():
	"""NHIF now queues restricted items from encounter pre-approval, so request_approval_no is no longer used."""
	field_updates = {
		"request_approval_no": {"hidden": 1, "depends_on": DEPENDS_ON},
		"get_approval_status": {"fieldtype": "Button", "depends_on": DEPENDS_ON},
		"update_approval_request": {"depends_on": DEPENDS_ON},
	}

	for doctype in DOCTYPES:
		for fieldname, values in field_updates.items():
			# set_value because Custom Field validation blocks the Lab Test Barcode -> Button change
			frappe.db.set_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, values)

		frappe.clear_cache(doctype=doctype)
