import frappe
from frappe.tests.utils import FrappeTestCase


def insert_patient(name):
	frappe.get_doc(doctype="Patient", name=name, first_name=name).db_insert()


def get_next_name(first_name):
	return frappe.get_doc(doctype="Patient", first_name=first_name).get_patient_name()


class TestPatientNameCounter(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_new_name_has_no_counter(self):
		self.assertEqual(get_next_name("_Test Unused Name"), "_Test Unused Name")

	def test_longer_name_is_ignored(self):
		insert_patient("_Test John Doe")
		insert_patient("Big _Test John Doe - 99")

		self.assertEqual(get_next_name("_Test John Doe"), "_Test John Doe - 1")

	def test_counter_is_numeric_max(self):
		for name in ("_Test Jane Doe", "_Test Jane Doe - 2", "_Test Jane Doe - 10"):
			insert_patient(name)

		self.assertEqual(get_next_name("_Test Jane Doe"), "_Test Jane Doe - 11")

	def test_non_numeric_suffix_is_ignored(self):
		insert_patient("_Test Ann Doe")
		insert_patient("_Test Ann Doe - Smith - 7")

		self.assertEqual(get_next_name("_Test Ann Doe"), "_Test Ann Doe - 1")

	def test_like_wildcards_in_name_are_literal(self):
		insert_patient("_Test A_B")
		insert_patient("_Test AxB - 5")

		self.assertEqual(get_next_name("_Test A_B"), "_Test A_B - 1")
