# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.hms_tz_setting.hms_tz_setting import is_cash_inpatient_deposit_allowed
from hms_tz.nhif.api import healthcare_utils, patient_encounter, sales_invoice, sales_order

COMPANY = "_Test Deposit Company"
PATIENT = "_Test Deposit Patient"
INPATIENT_RECORD = "_Test Deposit IP"


def set_deposit_allowed(allowed):
	frappe.db.set_value("HMS TZ Setting", COMPANY, "allow_cash_inpatient_deposit", allowed)


def make_encounter(**values):
	return frappe._dict(
		{
			"name": "_Test Deposit PE",
			"company": COMPANY,
			"patient": PATIENT,
			"patient_name": PATIENT,
			"appointment": "_Test Deposit Appointment",
			"inpatient_record": INPATIENT_RECORD,
			"mode_of_payment": "Cash",
			"insurance_subscription": None,
			"healthcare_package_order": None,
			**values,
		}
	)


class TestCashInpatientDeposit(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setting = frappe.new_doc("HMS TZ Setting")
		setting.name = COMPANY
		setting.company = COMPANY
		setting.db_insert()

		patient = frappe.new_doc("Patient")
		patient.name = PATIENT
		patient.first_name = PATIENT
		patient.inpatient_record = INPATIENT_RECORD
		patient.db_insert()

	def test_missing_setting_keeps_deposit_flow(self):
		self.assertTrue(is_cash_inpatient_deposit_allowed("_Test Company Without Setting"))

	def test_setting_controls_deposit_flow(self):
		set_deposit_allowed(1)
		self.assertTrue(is_cash_inpatient_deposit_allowed(COMPANY))
		set_deposit_allowed(0)
		self.assertFalse(is_cash_inpatient_deposit_allowed(COMPANY))

	@patch.object(patient_encounter, "update_inpatient_record_consultancy")
	@patch.object(patient_encounter, "create_service_request")
	@patch.object(patient_encounter, "on_submit_validation")
	@patch.object(patient_encounter, "inpatient_billing")
	@patch.object(patient_encounter, "validate_patient_balance_vs_patient_costs")
	def test_deposit_flow_creates_services_on_submit(self, balance, billing, validation, service_request, _):
		set_deposit_allowed(1)
		patient_encounter.on_submit(make_encounter(), "on_submit")

		balance.assert_called_once()
		billing.assert_called_once()
		validation.assert_not_called()
		service_request.assert_not_called()

	@patch.object(patient_encounter, "update_inpatient_record_consultancy")
	@patch.object(patient_encounter, "create_service_request")
	@patch.object(patient_encounter, "on_submit_validation")
	@patch.object(patient_encounter, "inpatient_billing")
	@patch.object(patient_encounter, "validate_patient_balance_vs_patient_costs")
	def test_no_deposit_flow_waits_for_invoice(self, balance, billing, validation, service_request, _):
		set_deposit_allowed(0)
		patient_encounter.on_submit(make_encounter(), "on_submit")

		balance.assert_not_called()
		billing.assert_not_called()
		validation.assert_called_once()
		service_request.assert_called_once()

	def test_no_deposit_flow_skips_cash_limit_alert(self):
		set_deposit_allowed(0)
		frappe.db.set_value("HMS TZ Setting", COMPANY, "hms_tz_has_cash_limit_alert", 1)
		with patch.object(patient_encounter, "get_patient_encounters") as encounters:
			result = patient_encounter.validate_patient_balance_vs_patient_costs(
				PATIENT, PATIENT, "_Test Deposit Appointment", INPATIENT_RECORD, COMPANY
			)

		self.assertIsNone(result)
		encounters.assert_not_called()

	@patch.object(sales_order, "get_items_from_encounter", return_value=([], []))
	def test_deposit_flow_skips_sales_order(self, get_items):
		set_deposit_allowed(1)
		sales_order.create_sales_order(make_encounter(), "on_submit")
		get_items.assert_not_called()

	@patch.object(sales_order, "get_items_from_encounter", return_value=([], []))
	def test_no_deposit_flow_creates_sales_order(self, get_items):
		set_deposit_allowed(0)
		frappe.db.set_value(
			"HMS TZ Setting",
			COMPANY,
			{"auto_create_sales_order_from_encounter": 1, "sales_order_ipd_pharmacy": "_Test IPD Store"},
		)
		sales_order.create_sales_order(make_encounter(), "on_submit")
		get_items.assert_called_once()
		self.assertEqual(get_items.call_args.args[1], "_Test IPD Store")

	def test_deposit_flow_disables_invoice_delivery_notes(self):
		set_deposit_allowed(1)
		invoice = self.make_invoice()
		sales_invoice.validate_create_delivery_note(invoice)
		self.assertEqual(invoice.enabled_auto_create_delivery_notes, 0)

	def test_no_deposit_flow_keeps_invoice_delivery_notes(self):
		set_deposit_allowed(0)
		invoice = self.make_invoice()
		sales_invoice.validate_create_delivery_note(invoice)
		self.assertEqual(invoice.enabled_auto_create_delivery_notes, 1)

	def test_deposit_flow_marks_encounter_on_deposit(self):
		set_deposit_allowed(1)
		self.assertTrue(healthcare_utils.is_cash_inpatient_on_deposit(make_encounter()))
		self.assertFalse(
			healthcare_utils.is_cash_inpatient_on_deposit(make_encounter(insurance_subscription="_Test Sub"))
		)
		self.assertFalse(healthcare_utils.is_cash_inpatient_on_deposit(make_encounter(inpatient_record=None)))

	@patch.object(healthcare_utils, "create_individual_lab_test")
	def test_deposit_flow_creates_lab_test_for_converted_encounter(self, create_lab_test):
		set_deposit_allowed(1)
		healthcare_utils.create_lrp_docs(self.make_submitted_encounter())
		create_lab_test.assert_called_once()

	@patch.object(healthcare_utils, "create_individual_lab_test")
	def test_no_deposit_flow_skips_lab_test_for_converted_encounter(self, create_lab_test):
		set_deposit_allowed(0)
		healthcare_utils.create_lrp_docs(self.make_submitted_encounter())
		create_lab_test.assert_not_called()

	@patch.object(healthcare_utils, "create_plan")
	def test_deposit_flow_creates_therapy_plan_for_converted_encounter(self, create_plan):
		set_deposit_allowed(1)
		healthcare_utils.create_therapy_plan(enc_doc=self.make_therapy_encounter())
		create_plan.assert_called_once()

	@patch.object(healthcare_utils, "create_plan")
	def test_no_deposit_flow_skips_therapy_plan_for_converted_encounter(self, create_plan):
		set_deposit_allowed(0)
		healthcare_utils.create_therapy_plan(enc_doc=self.make_therapy_encounter())
		create_plan.assert_not_called()

	def test_no_deposit_flow_holds_consumable_delivery_note(self):
		set_deposit_allowed(0)
		record = self.make_consumable_record(invoiced=0)
		with patch.object(record, "db_set"), patch.object(record, "_create_delivery_note") as create_dn:
			record.try_create_delivery_note()
		create_dn.assert_not_called()

	def test_no_deposit_flow_delivers_invoiced_consumable(self):
		set_deposit_allowed(0)
		record = self.make_consumable_record(invoiced=1)
		with patch.object(record, "db_set"), patch.object(record, "_create_delivery_note") as create_dn:
			record.try_create_delivery_note()
		create_dn.assert_called_once()

	def test_deposit_flow_delivers_consumable_at_once(self):
		set_deposit_allowed(1)
		record = self.make_consumable_record(invoiced=0)
		with patch.object(record, "db_set"), patch.object(record, "_create_delivery_note") as create_dn:
			record.try_create_delivery_note()
		create_dn.assert_called_once()

	def make_submitted_encounter(self):
		lab_row = frappe._dict(
			doctype="Lab Prescription",
			lab_test_code="_Test Lab",
			prescribe=1,
			is_cancelled=0,
			is_not_available_inhouse=0,
			hms_tz_is_limit_exceeded=0,
		)
		return make_encounter(docstatus=1, lab_test_prescription=[lab_row])

	def make_therapy_encounter(self):
		therapy_row = frappe._dict(
			therapy_type="_Test Therapy",
			prescribe=1,
			is_cancelled=0,
			is_not_available_inhouse=0,
			hms_tz_is_limit_exceeded=0,
			therapy_plan_created=0,
		)
		return make_encounter(docstatus=1, drug_prescription=[], therapies=[therapy_row])

	def make_consumable_record(self, invoiced):
		record = frappe.new_doc("Consumable Record")
		record.company = COMPANY
		record.patient = PATIENT
		record.inpatient_record = INPATIENT_RECORD
		record.payment_type = "Cash"
		record.append(
			"items",
			{"item_code": "_Test Item", "payment_type": "Cash", "is_billable": 1, "invoiced": invoiced},
		)
		return record

	def make_invoice(self):
		invoice = frappe.new_doc("Sales Invoice")
		invoice.company = COMPANY
		invoice.patient = PATIENT
		invoice.enabled_auto_create_delivery_notes = 1
		return invoice
