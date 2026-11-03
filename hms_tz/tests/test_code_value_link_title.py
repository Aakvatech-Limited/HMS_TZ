import frappe
from frappe.desk.search import get_link_title
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches.property_setter.create_property_setters import (
	create_property_setter_from_json,
	load_json,
)


class TestCodeValueLinkTitle(FrappeTestCase):
	def test_code_value_link_shows_name_after_property_setters_sync(self):
		frappe.get_doc(doctype="Code System", code_system="ICD-10", uri="http://test.local/icd").insert(
			ignore_if_duplicate=True
		)
		code_value = frappe.get_doc(doctype="Code Value", code_system="ICD-10", code_value="ZTL1").insert(
			ignore_if_duplicate=True
		)
		frappe.db.delete(
			"Property Setter", {"doc_type": "Code Value", "property": "show_title_field_in_link"}
		)
		frappe.clear_cache(doctype="Code Value")
		self.assertIsNone(get_link_title("Code Value", code_value.name))

		create_property_setter_from_json(load_json("25_code_value.json"))
		frappe.clear_cache(doctype="Code Value")

		self.assertEqual(get_link_title("Code Value", code_value.name), "ICD-10 ZTL1")
