from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api import healthcare_utils

ENABLED = "_Test NHIF Enabled Company"
DISABLED = "_Test NHIF Disabled Company"
AUTO_CREATE_DISABLED = "_Test NHIF Auto Create Disabled Company"
TODAY = "2026-01-15"
YESTERDAY = "2026-01-14"


def make_setting(company, enable_nhif_api, enable_auto_create_of_claims=1):
	frappe.get_doc(
		doctype="HMS TZ Setting",
		name=company,
		company=company,
		enable_nhif_api=enable_nhif_api,
		enable_auto_create_of_claims=enable_auto_create_of_claims,
	).db_insert()


def make_appointment(company, insurance_company="NHIF", appointment_date=YESTERDAY):
	name = frappe.generate_hash()
	frappe.get_doc(
		doctype="Patient Appointment",
		name=name,
		company=company,
		status="Closed",
		insurance_company=insurance_company,
		appointment_date=appointment_date,
	).db_insert()
	frappe.get_doc(
		doctype="Patient Encounter", name=frappe.generate_hash(), appointment=name, docstatus=1, duplicated=0
	).db_insert()
	return name


def make_inpatient(company, appointment, status, discharge_date=None):
	frappe.get_doc(
		doctype="Inpatient Record",
		name=frappe.generate_hash(),
		company=company,
		insurance_company="NHIF",
		patient_appointment=appointment,
		status=status,
		discharge_date=discharge_date,
	).db_insert()


class TestAutoCreateNHIFPatientClaims(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("HMS TZ Setting", {"enable_nhif_api": 1})
		make_setting(ENABLED, 1)
		make_setting(DISABLED, 0)
		make_setting(AUTO_CREATE_DISABLED, 1, enable_auto_create_of_claims=0)

	def tearDown(self):
		frappe.db.rollback()

	def get_claimed_appointments(self):
		with (
			patch.object(healthcare_utils, "nowdate", return_value=TODAY),
			patch.object(healthcare_utils, "create_nhif_patient_claims") as create_claims,
		):
			healthcare_utils.auto_create_nhif_patient_claims()
		return set().union(*(call.args[0] for call in create_claims.call_args_list))

	def test_claims_only_companies_with_nhif_api_and_auto_create_enabled(self):
		enabled_appointment = make_appointment(ENABLED)
		make_appointment(DISABLED)
		make_appointment(AUTO_CREATE_DISABLED)

		self.assertEqual(self.get_claimed_appointments(), {enabled_appointment})

	def test_matches_insurance_companies_starting_with_nhif(self):
		nhif_branch = make_appointment(ENABLED, insurance_company="NHIF - Dar es Salaam")
		make_appointment(ENABLED, insurance_company="Other Insurance")

		self.assertEqual(self.get_claimed_appointments(), {nhif_branch})

	def test_skips_ongoing_and_claims_discharged_inpatients(self):
		ongoing = make_appointment(ENABLED)
		make_inpatient(ENABLED, ongoing, "Admitted")
		discharged = make_appointment(ENABLED, appointment_date="2025-12-20")
		make_inpatient(ENABLED, discharged, "Discharged", discharge_date=YESTERDAY)

		self.assertEqual(self.get_claimed_appointments(), {discharged})
