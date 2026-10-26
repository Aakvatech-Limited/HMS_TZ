# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches.custom_fields.hide_request_approval_no_on_lrpt_docs import (
	DEPENDS_ON,
	DOCTYPES,
	execute,
)

OLD_FIELDS = {
	"request_approval_no": {
		"fieldtype": "Button",
		"hidden": 0,
		"depends_on": "eval: doc.is_restricted == 1 && !doc.approval_number && !doc.service_authorization_id",
	},
	"get_approval_status": {
		"fieldtype": "Button",
		"hidden": 0,
		"depends_on": "eval: doc.service_authorization_id && !doc.approval_number",
	},
	"update_approval_request": {
		"fieldtype": "Button",
		"hidden": 0,
		"depends_on": "eval: doc.is_restricted == 1 && !doc.approval_number && doc.service_authorization_id",
	},
}


def set_old_state():
	"""Put the fields back to the shape that sites had before the patch, with Lab Test get_approval_status as Barcode."""
	for doctype in DOCTYPES:
		for fieldname, values in OLD_FIELDS.items():
			if doctype == "Lab Test" and fieldname == "get_approval_status":
				values = {**values, "fieldtype": "Barcode"}

			if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
				frappe.db.set_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, values)
			else:
				create_custom_fields({doctype: [{"fieldname": fieldname, "label": fieldname, **values}]})

		frappe.clear_cache(doctype=doctype)


class TestHideRequestApprovalNoPatch(FrappeTestCase):
	def setUp(self):
		set_old_state()

	def test_patch_hides_request_and_shows_status_buttons_on_restricted_docs(self):
		execute()

		for doctype in DOCTYPES:
			meta = frappe.get_meta(doctype)
			request_field = meta.get_field("request_approval_no")
			self.assertEqual(request_field.hidden, 1, doctype)

			for fieldname in OLD_FIELDS:
				field = meta.get_field(fieldname)
				self.assertEqual(field.depends_on, DEPENDS_ON, f"{doctype}.{fieldname}")
				self.assertNotIn("service_authorization_id", field.depends_on)

			status_field = meta.get_field("get_approval_status")
			self.assertEqual(status_field.fieldtype, "Button", doctype)
			self.assertEqual(status_field.hidden, 0, doctype)

	def test_lab_test_barcode_column_with_data_survives_patch_and_schema_sync(self):
		self.assertTrue(frappe.db.has_column("Lab Test", "get_approval_status"))
		lab_test = frappe.db.get_value("Lab Test", {}, "name")
		self.assertTrue(lab_test, "test site needs one Lab Test")
		frappe.db.set_value("Lab Test", lab_test, "get_approval_status", "old-barcode", update_modified=False)

		execute()
		frappe.db.updatedb("Lab Test")

		self.assertTrue(frappe.db.has_column("Lab Test", "get_approval_status"))
		self.assertEqual(frappe.db.get_value("Lab Test", lab_test, "get_approval_status"), "old-barcode")
		self.assertEqual(frappe.get_doc("Lab Test", lab_test).name, lab_test)

	def test_patch_is_safe_to_run_twice(self):
		execute()
		execute()

		field = frappe.get_meta("Lab Test").get_field("get_approval_status")
		self.assertEqual(field.fieldtype, "Button")
		self.assertEqual(field.depends_on, DEPENDS_ON)
