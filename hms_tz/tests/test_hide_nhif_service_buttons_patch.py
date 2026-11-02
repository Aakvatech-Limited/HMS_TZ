# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches.custom_fields.hide_nhif_service_buttons_once_referenced import (
	FIELDNAMES,
	execute,
	get_button_fields,
)

DOCTYPES = ["Lab Test", "Radiology Examination", "Clinical Procedure", "Therapy Session", "Delivery Note"]


class TestHideNhifServiceButtonsPatch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.expected = {
			(field["dt"], field["fieldname"]): field["depends_on"] for field in get_button_fields()
		}

	def setUp(self):
		# live sites have no depends_on on these buttons
		for doctype, fieldname in self.expected:
			frappe.db.set_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "depends_on", None)

		for doctype in DOCTYPES:
			frappe.clear_cache(doctype=doctype)

	def test_json_covers_both_buttons_on_all_five_doctypes(self):
		expected_keys = {(doctype, fieldname) for doctype in DOCTYPES for fieldname in FIELDNAMES}
		self.assertEqual(set(self.expected), expected_keys)

	def test_patch_copies_depends_on_from_json(self):
		execute()

		for (doctype, fieldname), depends_on in self.expected.items():
			field = frappe.get_meta(doctype).get_field(fieldname)
			self.assertEqual(field.depends_on, depends_on, f"{doctype}.{fieldname}")

	def test_json_hides_buttons_once_references_are_set(self):
		for (doctype, fieldname), depends_on in self.expected.items():
			if fieldname == "get_poc_reference_no":
				self.assertIn("!doc.poc_reference_no", depends_on, doctype)
			elif doctype == "Delivery Note":
				self.assertIn(
					"doc.items.some((row) => row.is_restricted && !row.service_reference_no)", depends_on
				)
			else:
				self.assertIn("!doc.service_reference_no", depends_on, doctype)
