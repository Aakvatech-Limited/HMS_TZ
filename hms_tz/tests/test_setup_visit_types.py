import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.csvutils import to_csv

from hms_tz.api.setup_records import (
	get_company_records,
	get_screen_fields,
	import_company_records,
	save_company_record,
)
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

SCREEN = "visit_types"
COMPANY = "_Test Company"
VISIT = "_Test Setup Visit"
STEP = "Appointment Type"


class TestSetupVisitTypes(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Appointment Type", {"name": ["like", f"{VISIT}%"]})
		frappe.delete_doc_if_exists("Setup Status", COMPANY)
		frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
		frappe.db.set_single_value(
			"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
		)
		frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
		self.labels = {field["fieldname"]: field["label"] for field in get_screen_fields(SCREEN)["fields"]}
		get_company_records(SCREEN, COMPANY)

	def save(self, values, name=None):
		return save_company_record(SCREEN, COMPANY, frappe.as_json(values), name=name)

	def visit_values(self, name=VISIT, **values):
		return {"appointment_type": name, "source": "Direct", "visit_type_id": "1", **values}

	def upload(self, *rows):
		fieldnames = ("appointment_type", "source", "visit_type_id")
		content = to_csv([[self.labels[fieldname] for fieldname in fieldnames], *[list(row) for row in rows]])
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "visit_types.csv", "content": content, "is_private": 1}
		)
		return file.insert().file_url

	def test_visit_type_fields_need_a_name_source_and_nhif_visit_type_id(self):
		screen = get_screen_fields(SCREEN)
		fields = {field["fieldname"]: field for field in screen["fields"]}
		self.assertEqual((screen["label"], screen["plural_label"]), ("visit type", "visit types"))
		self.assertEqual(fields["appointment_type"]["set_only_once"], 1)
		self.assertEqual(fields["source"]["fieldtype"], "Select")
		for fieldname in ("source", "visit_type_id", "allow_booking_for"):
			self.assertEqual(fields[fieldname]["reqd"], 1)
		for fieldname in ("default_duration", "has_no_consultation_charges_for_cash", "disabled"):
			self.assertIn(fieldname, fields)

	def test_list_shows_visit_types_of_all_companies(self):
		self.save(self.visit_values())
		names = [record.name for record in get_company_records(SCREEN, COMPANY)["records"]]
		self.assertIn(VISIT, names)

	def test_a_new_visit_type_ticks_the_step(self):
		name = self.save(self.visit_values(has_no_consultation_charges_for_cash=1))
		visit = frappe.get_doc("Appointment Type", name)
		self.assertEqual((visit.name, visit.visit_type_id), (VISIT, "1"))
		self.assertEqual(visit.has_no_consultation_charges_for_cash, 1)
		self.assertTrue(get_setup_status(COMPANY).get_step(STEP).completed)

	def test_changing_a_visit_type_keeps_its_name(self):
		name = self.save(self.visit_values())
		self.save(self.visit_values(name=f"{VISIT} Renamed", visit_type_id="9", disabled=1), name=name)
		visit = frappe.get_doc("Appointment Type", name)
		self.assertEqual((visit.appointment_type, visit.visit_type_id, visit.disabled), (VISIT, "9", 1))

	def test_a_visit_type_needs_an_nhif_visit_type_id(self):
		with self.assertRaisesRegex(frappe.ValidationError, self.labels["visit_type_id"]):
			self.save(self.visit_values(visit_type_id=""))

	def test_visit_types_stay_locked_until_settings_are_complete(self):
		frappe.db.set_value("HMS TZ Setting", COMPANY, "enable_nhif_api", 1)
		self.assertFalse(get_company_records(SCREEN, COMPANY)["settings_complete"])
		with self.assertRaises(frappe.ValidationError):
			self.save(self.visit_values())

	def test_import_adds_visit_types_reports_bad_rows_and_changes_them_again(self):
		rows = [(f"{VISIT} A", "Direct", "1"), (f"{VISIT} B", "Direct", "")]
		result = import_company_records(SCREEN, COMPANY, self.upload(*rows))
		self.assertEqual(result["added"], 1)
		self.assertEqual([error["row"] for error in result["errors"]], [3])
		result = import_company_records(SCREEN, COMPANY, self.upload((f"{VISIT} A", "Referral", "3")))
		self.assertEqual((result["added"], result["changed"], result["errors"]), (0, 1, []))
		self.assertEqual(frappe.db.get_value("Appointment Type", f"{VISIT} A", "source"), "Referral")
