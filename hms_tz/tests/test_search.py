import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api.search import search_patients_and_appointments
from hms_tz.tests.test_appointment_api_permissions import COMPANY, OTHER_COMPANY, USER, insert_user
from hms_tz.tests.utils import insert

PATIENT = "_Test Search Patient"


def insert_appointment(name, company=COMPANY, days=0):
	insert(
		"Patient Appointment",
		name,
		patient=PATIENT,
		patient_name="Zawadi Testsearch",
		company=company,
		appointment_date=add_days(nowdate(), days),
		appointment_time="09:05:00",
		status="Open",
	)


def found_appointments(txt):
	return [row.name for row in search_patients_and_appointments(txt)["appointments"]]


class TestSearchPatientsAndAppointments(FrappeTestCase):
	def setUp(self):
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TAC", default_currency="TZS")
		insert("Company", OTHER_COMPANY, company_name=OTHER_COMPANY, abbr="_TAO", default_currency="TZS")
		insert(
			"Patient",
			PATIENT,
			patient_name="Zawadi Testsearch",
			first_name="Zawadi",
			mobile="255719000123",
			card_no="_TEST-SEARCH-CARD",
			status="Active",
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.clear_cache(user=USER)

	def test_finds_patient_by_name_id_local_mobile_and_card(self):
		for txt in ["Zawadi Testsearch", PATIENT, "0719000123", "_TEST-SEARCH-CARD"]:
			patients = search_patients_and_appointments(txt)["patients"]
			self.assertEqual([patient.value for patient in patients], [PATIENT], txt)

	def test_lists_recent_and_upcoming_appointments_latest_first(self):
		insert_appointment("_Test Search Upcoming", days=2)
		insert_appointment("_Test Search Recent", days=-5)
		insert_appointment("_Test Search Old", days=-60)

		self.assertEqual(found_appointments("Zawadi"), ["_Test Search Upcoming", "_Test Search Recent"])

	def test_appointments_follow_user_permissions(self):
		insert_appointment("_Test Search Own Company")
		insert_appointment("_Test Search Other Company", company=OTHER_COMPANY)
		insert_user()
		frappe.set_user(USER)

		self.assertEqual(found_appointments("Zawadi"), ["_Test Search Own Company"])

	def test_no_patient_gives_no_appointments(self):
		self.assertEqual(
			search_patients_and_appointments("_no such patient_"), {"patients": [], "appointments": []}
		)
