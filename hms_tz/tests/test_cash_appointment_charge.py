from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import appointment as appointment_api

PRACTITIONER = "_Test Cash Charge Practitioner"
COMPANY = "_Test Cash Charge Clinic"
CHARGE_ITEM = "_Test Cash Consultation"
CASH = frappe._dict(mode_of_payment="_Test Cash", type="Cash")


def charge(has_no_consultation_charges=0):
	return appointment_api.get_cash_charge(
		PRACTITIONER, "Consultation", COMPANY, has_no_consultation_charges=has_no_consultation_charges
	)


@patch.object(appointment_api, "get_mode_of_payment", new=lambda: [CASH])
class TestCashAppointmentCharge(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: None)
	def test_refuses_a_practitioner_without_consulting_charge_item(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no OPD consulting charge item"):
			charge()

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: CHARGE_ITEM)
	@patch.object(appointment_api, "get_cash_amount", new=lambda *args, **kwargs: 0)
	def test_refuses_a_charge_item_without_price(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no price for mode of payment _Test Cash"):
			charge()

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: CHARGE_ITEM)
	@patch.object(appointment_api, "get_cash_amount", new=lambda *args, **kwargs: 0)
	def test_no_consultation_charges_allows_zero(self):
		self.assertEqual(charge(has_no_consultation_charges=1)["paid_amount"], 0)

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: CHARGE_ITEM)
	@patch.object(appointment_api, "get_cash_amount", new=lambda *args, **kwargs: 7000)
	def test_returns_item_mode_of_payment_and_amount(self):
		self.assertEqual(
			charge(),
			{"billing_item": CHARGE_ITEM, "mode_of_payment": "_Test Cash", "paid_amount": 7000},
		)

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: None)
	def test_create_refuses_cash_booking_and_creates_nothing(self):
		count = frappe.db.count("Patient Appointment")
		data = {
			"company": COMPANY,
			"practitioner": PRACTITIONER,
			"appointment_type": "Consultation",
			"appointment_date": add_days(nowdate(), 1),
			"appointment_time": "10:00:00",
			"payment_mode": "Cash",
		}

		with self.assertRaisesRegex(frappe.ValidationError, "has no OPD consulting charge item"):
			appointment_api.create_appointment(data)
		self.assertEqual(frappe.db.count("Patient Appointment"), count)
