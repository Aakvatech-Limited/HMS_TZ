from unittest.mock import patch

import frappe
from frappe.permissions import add_user_permission
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import appointment as appointment_api
from hms_tz.api import practitioner as practitioner_api
from hms_tz.nhif.api import patient_appointment as nhif_appointment
from hms_tz.tests.utils import insert

USER = "_test_appointment_receptionist@example.com"
COMPANY = "_Test Appointment Clinic"
OTHER_COMPANY = "_Test Appointment Other Clinic"
PRACTITIONER = "_Test Appointment Practitioner"
APPOINTMENT = "_Test Appointment API"


def insert_user():
	"""A desk user limited to COMPANY by a User Permission, with no read access to Company itself."""
	insert("User", USER, email=USER, first_name="Receptionist", enabled=1, user_type="System User")
	for idx, role in enumerate(["Nursing User"], start=1):
		insert(
			"Has Role",
			f"{USER}-{role}",
			parent=USER,
			parenttype="User",
			parentfield="roles",
			idx=idx,
			role=role,
		)
	add_user_permission("Company", COMPANY, USER, is_default=1)
	frappe.clear_cache(user=USER)


def future_appointment_data(company):
	return {"company": company, "appointment_date": add_days(nowdate(), 1), "appointment_time": "10:00:00"}


class TestAppointmentApiPermissions(FrappeTestCase):
	def setUp(self):
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TAC", default_currency="TZS")
		insert("Company", OTHER_COMPANY, company_name=OTHER_COMPANY, abbr="_TAO", default_currency="TZS")
		insert_user()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.clear_cache(user=USER)

	def test_user_companies_follow_user_permissions(self):
		frappe.set_user(USER)

		self.assertFalse(frappe.has_permission("Company", "read"))
		self.assertEqual(
			appointment_api.get_user_companies(),
			{"companies": [COMPANY], "default_company": COMPANY},
		)

	def test_user_without_company_permissions_gets_every_company(self):
		companies = appointment_api.get_user_companies()["companies"]

		self.assertIn(COMPANY, companies)
		self.assertIn(OTHER_COMPANY, companies)

	def test_create_rejects_company_outside_user_permissions(self):
		frappe.set_user(USER)

		with self.assertRaises(frappe.PermissionError):
			appointment_api.create_appointment(future_appointment_data(OTHER_COMPANY))

	def test_create_rejects_user_without_create_permission(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			appointment_api.create_appointment(future_appointment_data(COMPANY))

	def test_create_rejects_past_time(self):
		data = {**future_appointment_data(COMPANY), "appointment_date": add_days(nowdate(), -1)}

		with self.assertRaisesRegex(frappe.ValidationError, "in the past"):
			appointment_api.create_appointment(data)

	def test_update_rejects_moving_to_past_time(self):
		insert(
			"Patient Appointment",
			APPOINTMENT,
			company=COMPANY,
			practitioner=PRACTITIONER,
			appointment_type="Consultation",
			appointment_date=add_days(nowdate(), -1),
			appointment_time="10:00:00",
			status="Open",
		)

		with self.assertRaisesRegex(frappe.ValidationError, "in the past"):
			appointment_api.update_appointment(APPOINTMENT, PRACTITIONER, "11:00:00", "Consultation")

	def test_cancel_rejects_user_without_write_permission(self):
		insert(
			"Patient Appointment",
			APPOINTMENT,
			company=COMPANY,
			appointment_date=nowdate(),
			status="Open",
		)
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			appointment_api.cancel_appointment(APPOINTMENT)

	def test_details_reject_appointment_of_other_company(self):
		insert(
			"Patient Appointment",
			APPOINTMENT,
			company=OTHER_COMPANY,
			appointment_date=nowdate(),
			status="Open",
		)
		frappe.set_user(USER)

		with self.assertRaises(frappe.PermissionError):
			appointment_api.get_appointment_details(APPOINTMENT)

	def test_practitioners_follow_user_permissions(self):
		insert(
			"Healthcare Practitioner",
			PRACTITIONER,
			first_name="Test",
			practitioner_name="Test Practitioner",
			status="Active",
			hms_tz_company=COMPANY,
		)
		frappe.set_user(USER)

		practitioners = practitioner_api.get_practioner_list(COMPANY, nowdate())["practitioners"]
		self.assertEqual([practitioner["name"] for practitioner in practitioners], [PRACTITIONER])

		self.assertEqual(practitioner_api.get_practioner_list(OTHER_COMPANY, nowdate())["practitioners"], [])

	def test_save_tells_grids_the_company_and_date(self):
		appointment = frappe._dict(doctype="Patient Appointment", company=COMPANY, appointment_date=nowdate())

		with patch.object(frappe, "publish_realtime") as publish_realtime:
			nhif_appointment.publish_grid_update(appointment, "on_update")

		publish_realtime.assert_called_once_with(
			"patient_appointment_update",
			{"company": COMPANY, "appointment_date": nowdate(), "user": "Administrator"},
			room="doctype:Patient Appointment",
			after_commit=True,
		)
