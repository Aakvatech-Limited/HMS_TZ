import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.patient.patient import get_non_group_customer_group, get_patient_customer
from hms_tz.tests.utils import insert

PATIENT = "_Test Customer Link Patient"
PATIENT_NAME = "_Test Customer Link Patient Name"


class TestPatientCustomer(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def insert_patient(self, customer=None):
		insert(
			"Patient", PATIENT, first_name="Test", patient_name=PATIENT_NAME, sex="Male", customer=customer
		)

	def get_linked_customer(self):
		return frappe.db.get_value("Patient", PATIENT, "customer")

	def test_existing_customer_is_returned(self):
		insert("Customer", "_Test Linked Customer", customer_name="_Test Linked Customer")
		self.insert_patient(customer="_Test Linked Customer")

		self.assertEqual(get_patient_customer(PATIENT), "_Test Linked Customer")

	def test_deleted_customer_is_replaced_and_relinked(self):
		self.insert_patient(customer="_Test Deleted Customer")

		customer = get_patient_customer(PATIENT)

		self.assertNotEqual(customer, "_Test Deleted Customer")
		self.assertTrue(frappe.db.exists("Customer", customer))
		self.assertEqual(self.get_linked_customer(), customer)

	def test_group_type_customer_group_is_replaced_by_a_leaf_group(self):
		self.insert_patient()
		frappe.db.set_value("Patient", PATIENT, "customer_group", "All Customer Groups")

		customer = get_patient_customer(PATIENT)

		customer_group = frappe.db.get_value("Customer", customer, "customer_group")
		self.assertEqual(frappe.db.get_value("Customer Group", customer_group, "is_group"), 0)

	def test_missing_customer_is_created_and_linked(self):
		self.insert_patient()

		customer = get_patient_customer(PATIENT)

		self.assertEqual(frappe.db.get_value("Customer", customer, "customer_name"), PATIENT_NAME)
		self.assertEqual(self.get_linked_customer(), customer)

	def test_update_keeps_the_customer_group_when_the_patient_has_a_group(self):
		leaf_group = get_non_group_customer_group()
		self.insert_patient()
		customer = get_patient_customer(PATIENT)
		frappe.db.set_value("Patient", PATIENT, "customer_group", "All Customer Groups")

		frappe.get_doc("Patient", PATIENT).run_method("on_update")

		self.assertEqual(frappe.db.get_value("Customer", customer, "customer_group"), leaf_group)
