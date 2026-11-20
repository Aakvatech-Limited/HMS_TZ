from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import practitioner as practitioner_api
from hms_tz.tests.utils import insert

PRACTITIONER = "_Test Availability Doctor"
HOLIDAY_LIST = "_Test Availability Holidays"
AVAILABLE = "_Test Available Employee"
ON_HOLIDAY = "_Test Holiday Employee"
ON_LEAVE = "_Test Leave Employee"
NO_USER = "_Test No User Employee"
USER = "_test_availability_doctor@example.com"


def insert_employee(name, **values):
	insert("Employee", name, first_name=name, employee_name=name, status="Active", **values)


def insert_leave(name, employee, status):
	insert(
		"Leave Application",
		name,
		employee=employee,
		docstatus=1,
		status=status,
		from_date=nowdate(),
		to_date=nowdate(),
	)


def is_available(employee=None, user_id=None):
	return practitioner_api.check_practitioner_employee_availability(
		PRACTITIONER, nowdate(), employee=employee, user_id=user_id
	)


class TestPractitionerAvailability(FrappeTestCase):
	def setUp(self):
		insert(
			"Holiday List",
			HOLIDAY_LIST,
			holiday_list_name=HOLIDAY_LIST,
			from_date=add_days(nowdate(), -30),
			to_date=add_days(nowdate(), 30),
		)
		insert(
			"Holiday",
			"_Test Availability Holiday Today",
			parent=HOLIDAY_LIST,
			parenttype="Holiday List",
			parentfield="holidays",
			holiday_date=nowdate(),
			description="Test holiday",
		)
		insert_employee(AVAILABLE)
		insert_employee(ON_HOLIDAY, holiday_list=HOLIDAY_LIST)
		insert_employee(ON_LEAVE)
		insert_employee(NO_USER, holiday_list=HOLIDAY_LIST)

	def tearDown(self):
		frappe.db.rollback()

	def test_practitioner_without_employee_is_available(self):
		self.assertTrue(is_available())

	def test_no_user_does_not_match_an_employee_with_a_blank_user(self):
		# NO_USER has no user_id and is on holiday; a practitioner without a user must not pick it up.
		self.assertTrue(is_available(user_id=None))

	def test_available_employee_is_available(self):
		self.assertIs(is_available(employee=AVAILABLE), True)

	def test_employee_found_by_user_is_checked(self):
		frappe.db.set_value("Employee", ON_HOLIDAY, "user_id", USER)
		self.assertFalse(is_available(user_id=USER))

	def test_employee_on_holiday_is_not_available(self):
		self.assertFalse(is_available(employee=ON_HOLIDAY))

	def test_employee_on_approved_leave_is_not_available(self):
		insert_leave("_Test Approved Leave", ON_LEAVE, "Approved")
		self.assertFalse(is_available(employee=ON_LEAVE))

	def test_rejected_leave_keeps_the_employee_available(self):
		insert_leave("_Test Rejected Leave", ON_LEAVE, "Rejected")
		self.assertTrue(is_available(employee=ON_LEAVE))

	def test_failed_check_is_logged_and_keeps_the_practitioner(self):
		with patch.object(practitioner_api, "is_holiday", side_effect=frappe.ValidationError("broken")):
			self.assertTrue(is_available(employee=AVAILABLE))
		self.assertTrue(
			frappe.db.exists(
				"Error Log",
				{"reference_doctype": "Healthcare Practitioner", "reference_name": PRACTITIONER},
			)
		)
