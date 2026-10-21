import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.api.patient_encounter import get_filterd_drug


def insert_medication(name, price_lists):
	frappe.get_doc(doctype="Medication", name=name, generic_name=name).db_insert()
	for price_list in price_lists:
		frappe.get_doc(
			doctype="Allowed Price List",
			name=frappe.generate_hash(),
			parent=name,
			parenttype="Medication",
			parentfield="allowed_price_lists",
			price_list=price_list,
		).db_insert()


def search(filters, page_len=20):
	rows = get_filterd_drug("Medication", "_Test Search Drug", "name", 0, page_len, filters)
	return [row[0] for row in rows]


class TestFilteredDrugSearch(FrappeTestCase):
	def setUp(self):
		insert_medication("_Test Search Drug A", ["_Test PL 1", "_Test PL 2", "_Test PL 3"])
		insert_medication("_Test Search Drug B", ["_Test PL 1", "_Test PL 2"])

	def tearDown(self):
		frappe.db.rollback()

	def test_drug_appears_once_without_price_list(self):
		self.assertEqual(search({}), ["_Test Search Drug A", "_Test Search Drug B"])

	def test_page_length_counts_drugs_not_price_lists(self):
		self.assertEqual(search({}, page_len=2), ["_Test Search Drug A", "_Test Search Drug B"])

	def test_price_list_filter_keeps_only_allowed_drugs(self):
		insert_medication("_Test Search Drug C", ["_Test PL 3"])

		self.assertEqual(search({"price_list": "_Test PL 3"}), ["_Test Search Drug A", "_Test Search Drug C"])
