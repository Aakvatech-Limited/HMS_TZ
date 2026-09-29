# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.patient import check_card_number


def insert_patient(name, insurance_card_detail):
	"""Insert without validation so the test needs no Patient masters."""
	patient = frappe.new_doc("Patient")
	patient.name = name
	patient.first_name = name
	patient.insurance_card_detail = insurance_card_detail
	patient.db_insert()
	return patient.name


class TestCheckCardNumber(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.nhif_patient = insert_patient("_Test Card NHIF", "01-99282742, ")
		cls.multi_card_patient = insert_patient("_Test Card Multi", "JUB-77, 55282742")
		cls.spaced_card_patient = insert_patient("_Test Card Spaced", "44 28 27")

	def test_card_inside_another_card_is_not_a_match(self):
		"""Jubilee 99282742 must not match NHIF 01-99282742."""
		self.assertFalse(check_card_number("99282742", is_new=True))

	def test_exact_card_matches(self):
		self.assertEqual(check_card_number("01-99282742", is_new=True), self.nhif_patient)

	def test_card_in_list_matches(self):
		self.assertEqual(check_card_number("55282742", is_new=True), self.multi_card_patient)
		self.assertEqual(check_card_number(" JUB-77 ", is_new=True), self.multi_card_patient)

	def test_spaces_inside_card_are_ignored(self):
		self.assertEqual(check_card_number("44 28 27", is_new=True), self.spaced_card_patient)

	def test_blank_card_matches_nothing(self):
		self.assertFalse(check_card_number("   ", is_new=True))

	def test_own_card_is_ignored_for_existing_patient(self):
		self.assertFalse(check_card_number("01-99282742", patient=self.nhif_patient))

	def test_error_names_patient_holding_card(self):
		with self.assertRaisesRegex(frappe.ValidationError, self.nhif_patient):
			check_card_number("01-99282742", is_new=True, caller="validate")
