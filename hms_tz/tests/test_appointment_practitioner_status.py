from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import appointment as appointment_api
from hms_tz.api import practitioner as practitioner_api
from hms_tz.tests.utils import insert

COMPANY = "_Test Practitioner Status Clinic"
ACTIVE = "_Test Status Active Practitioner"
DISABLED = "_Test Status Disabled Practitioner"
APPOINTMENT = "_Test Status Appointment"


def insert_practitioner(name, status):
	insert(
		"Healthcare Practitioner",
		name,
		first_name=name,
		practitioner_name=name,
		status=status,
		hms_tz_company=COMPANY,
	)


def listed(status):
	practitioners = practitioner_api.get_practioner_list(COMPANY, nowdate(), status)["practitioners"]
	return {practitioner["name"]: practitioner for practitioner in practitioners}


# Leave and holiday checks are covered elsewhere; these tests are about the status filter only.
@patch.object(practitioner_api, "check_practitioner_employee_availability", new=lambda *args, **kwargs: True)
class TestAppointmentPractitionerStatus(FrappeTestCase):
	def setUp(self):
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TPS", default_currency="TZS")
		insert_practitioner(ACTIVE, "Active")
		insert_practitioner(DISABLED, "Disabled")

	def tearDown(self):
		frappe.db.rollback()

	def test_active_is_the_default(self):
		practitioners = practitioner_api.get_practioner_list(COMPANY, nowdate())["practitioners"]

		self.assertEqual([practitioner["name"] for practitioner in practitioners], [ACTIVE])

	def test_disabled_lists_only_disabled_practitioners_as_unavailable(self):
		practitioners = listed("Disabled")

		self.assertEqual(list(practitioners), [DISABLED])
		self.assertEqual(practitioners[DISABLED]["status"], "Disabled")
		self.assertFalse(practitioners[DISABLED]["is_available"])

	def test_all_lists_both(self):
		practitioners = listed("All")

		self.assertEqual(sorted(practitioners), sorted([ACTIVE, DISABLED]))
		self.assertTrue(practitioners[ACTIVE]["is_available"])
		self.assertFalse(practitioners[DISABLED]["is_available"])

	def test_unknown_status_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Practitioner status must be one of"):
			practitioner_api.get_practioner_list(COMPANY, nowdate(), "Inactive")

	def test_create_refuses_disabled_practitioner(self):
		data = {
			"company": COMPANY,
			"practitioner": DISABLED,
			"appointment_date": add_days(nowdate(), 1),
			"appointment_time": "10:00:00",
		}

		with self.assertRaisesRegex(frappe.ValidationError, "is disabled"):
			appointment_api.create_appointment(data)

	def test_update_refuses_appointment_of_disabled_practitioner(self):
		insert_appointment(DISABLED)

		with self.assertRaisesRegex(frappe.ValidationError, "is disabled"):
			appointment_api.update_appointment(APPOINTMENT, DISABLED, "11:00:00", "Consultation")

	def test_update_refuses_moving_to_disabled_practitioner(self):
		insert_appointment(ACTIVE)

		with self.assertRaisesRegex(frappe.ValidationError, "is disabled"):
			appointment_api.update_appointment(APPOINTMENT, DISABLED, "10:00:00", "Consultation")


def insert_appointment(practitioner):
	insert(
		"Patient Appointment",
		APPOINTMENT,
		company=COMPANY,
		practitioner=practitioner,
		appointment_type="Consultation",
		appointment_date=add_days(nowdate(), 1),
		appointment_time="10:00:00",
		status="Scheduled",
	)
