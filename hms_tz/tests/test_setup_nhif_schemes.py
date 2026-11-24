import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.setup_records import (
	download_records_template,
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)

SCREEN = "nhif_schemes"
COMPANY = "_Test Company"
SCHEME = "_TEST-SETUP-SCHEME"


class TestSetupNHIFSchemes(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("NHIF Scheme", {"name": ["like", f"{SCHEME}%"]})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		frappe.get_doc({"doctype": "NHIF Scheme", "scheme_id": SCHEME, "scheme_name": "Test Scheme"}).insert()
		self.labels = {field["fieldname"]: field["label"] for field in get_screen_fields(SCREEN)["fields"]}
		get_company_records(SCREEN, COMPANY)

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def test_scheme_fields_need_an_id_fixed_once_set_and_a_name(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual((screen["label"], screen["plural_label"]), ("NHIF scheme", "NHIF schemes"))
		self.assertEqual((fields["scheme_id"]["reqd"], fields["scheme_id"]["set_only_once"]), (1, 1))
		self.assertEqual(fields["scheme_name"]["reqd"], 1)
		self.assertFalse(screen["has_add_actions"])

	def test_schemes_are_listed_for_every_company(self):
		names = [record.name for record in get_company_records(SCREEN, "_Test Company 1")["records"]]
		self.assertIn(SCHEME, names)

	def test_changing_a_scheme_keeps_its_id(self):
		self.save({"scheme_id": f"{SCHEME}-2", "scheme_name": "Renamed Scheme"}, name=SCHEME)
		scheme = frappe.get_doc("NHIF Scheme", SCHEME)
		self.assertEqual((scheme.scheme_id, scheme.scheme_name), (SCHEME, "Renamed Scheme"))

	def test_a_scheme_needs_a_name(self):
		with self.assertRaisesRegex(frappe.ValidationError, self.labels["scheme_name"]):
			self.save({"scheme_id": SCHEME, "scheme_name": ""}, name=SCHEME)

	def test_schemes_are_not_added_imported_or_templated_here(self):
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			self.save({"scheme_id": f"{SCHEME}-NEW", "scheme_name": "New Scheme"})
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			import_company_records(SCREEN, COMPANY, "/private/files/nhif_schemes.csv")
		with self.assertRaisesRegex(frappe.ValidationError, "are not added on this screen"):
			download_records_template(SCREEN, COMPANY)
		self.assertFalse(frappe.db.exists("NHIF Scheme", f"{SCHEME}-NEW"))

	def test_schemes_stay_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		self.assertFalse(get_company_records(SCREEN, COMPANY)["settings_complete"])
		with self.assertRaises(frappe.ValidationError):
			self.save({"scheme_id": SCHEME, "scheme_name": "Test Scheme"}, name=SCHEME)
