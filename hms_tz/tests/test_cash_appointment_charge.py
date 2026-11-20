from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from hms_tz.api import appointment as appointment_api
from hms_tz.nhif.api import patient_appointment as nhif_appointment
from hms_tz.tests.utils import insert

PRACTITIONER = "_Test Cash Charge Practitioner"
COMPANY = "_Test Cash Charge Clinic"
CHARGE_ITEM = "_Test Cash Consultation"
FREE_VISIT_TYPE = "_Test Cash Free Visit"
CHARGED_VISIT_TYPE = "_Test Cash Charged Visit"
PATIENT = "_Test Cash Follow Up Patient"
DEPARTMENT = "_Test Cash Department"
CASH = frappe._dict(mode_of_payment="_Test Cash", type="Cash")


def booking(**values):
	defaults = {
		"practitioner": PRACTITIONER,
		"billing_item": CHARGE_ITEM,
		"mode_of_payment": "_Test Cash",
		"paid_amount": 7000,
		"invoiced": 0,
	}
	return frappe._dict({**defaults, **values})


def check_new_patient(visit_type):
	appointment_api.validate_new_patient_cash_booking(PRACTITIONER, visit_type, COMPANY)


class TestCashBillingRule(FrappeTestCase):
	def test_charged_booking_needs_a_consulting_charge_item(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no OPD consulting charge item"):
			nhif_appointment.validate_cash_billing(booking(billing_item=None, paid_amount=0))

	def test_charged_booking_needs_a_price(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no price for mode of payment _Test Cash"):
			nhif_appointment.validate_cash_billing(booking(paid_amount=0))

	def test_priced_booking_passes(self):
		nhif_appointment.validate_cash_billing(booking())

	def test_free_booking_needs_no_item_or_price(self):
		nhif_appointment.validate_cash_billing(booking(billing_item=None, paid_amount=0, invoiced=1))


class TestCashFollowUp(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_free_follow_up_without_charge_item_is_not_refused(self):
		frappe.db.set_single_value("Healthcare Settings", "valid_days", 7)
		insert(
			"Patient Appointment",
			"_Test Cash Earlier Visit",
			patient=PATIENT,
			department=DEPARTMENT,
			status="Closed",
			mode_of_payment="_Test Cash",
			invoiced=1,
			appointment_date=add_days(nowdate(), -2),
		)
		appointment = frappe.new_doc("Patient Appointment")
		appointment.update(
			{
				"patient": PATIENT,
				"department": DEPARTMENT,
				"appointment_date": nowdate(),
				"mode_of_payment": "_Test Cash",
				"practitioner": PRACTITIONER,
				"paid_amount": 0,
			}
		)

		nhif_appointment.validate_has_no_consultation(appointment, "validate")
		nhif_appointment.validate_cash_billing(appointment)

		self.assertEqual((appointment.follow_up, appointment.invoiced, appointment.paid_amount), (1, 1, 0))


@patch.object(appointment_api, "get_mode_of_payment", new=lambda: [CASH])
class TestNewPatientCashBooking(FrappeTestCase):
	def setUp(self):
		insert(
			"Appointment Type",
			FREE_VISIT_TYPE,
			appointment_type=FREE_VISIT_TYPE,
			has_no_consultation_charges_for_cash=1,
		)
		insert("Appointment Type", CHARGED_VISIT_TYPE, appointment_type=CHARGED_VISIT_TYPE)

	def tearDown(self):
		frappe.db.rollback()

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: None)
	def test_visit_type_without_cash_charges_needs_no_item(self):
		check_new_patient(FREE_VISIT_TYPE)

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: None)
	def test_charged_visit_type_needs_a_consulting_charge_item(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no OPD consulting charge item"):
			check_new_patient(CHARGED_VISIT_TYPE)

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: CHARGE_ITEM)
	@patch.object(appointment_api, "get_cash_amount", new=lambda *args, **kwargs: 0)
	def test_charged_visit_type_needs_a_price(self):
		with self.assertRaisesRegex(frappe.ValidationError, "has no price for mode of payment _Test Cash"):
			check_new_patient(CHARGED_VISIT_TYPE)

	@patch.object(appointment_api, "get_consulting_charge_item", new=lambda *args: None)
	def test_create_refuses_before_inserting(self):
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TCC", default_currency="TZS")
		insert("Mode of Payment", CASH.mode_of_payment, mode_of_payment=CASH.mode_of_payment, type="Cash")
		insert(
			"Healthcare Practitioner",
			PRACTITIONER,
			first_name=PRACTITIONER,
			practitioner_name=PRACTITIONER,
			status="Active",
		)
		insert(
			"Patient", PATIENT, first_name="Cash", patient_name="Cash Patient", sex="Male", status="Active"
		)
		count = frappe.db.count("Patient Appointment")
		data = {
			"company": COMPANY,
			"practitioner": PRACTITIONER,
			"patient": PATIENT,
			"appointment_type": CHARGED_VISIT_TYPE,
			"appointment_date": add_days(nowdate(), 1),
			"appointment_time": "10:00:00",
			"payment_mode": "Cash",
		}

		with self.assertRaisesRegex(frappe.ValidationError, "has no OPD consulting charge item"):
			appointment_api.create_appointment(data)
		self.assertEqual(frappe.db.count("Patient Appointment"), count)
