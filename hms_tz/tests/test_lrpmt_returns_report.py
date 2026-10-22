import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.report.lrpmt_returns.lrpmt_returns import execute

PRACTITIONER = "_Test LR Practitioner ID"
PRACTITIONER_NAME = "_Test LR Doctor"
ENCOUNTER = "_Test LR Encounter"
ITEM = "_Test LR Item"
TEMPLATE = "_Test LR Lab Template"
DRUG = "_Test LR Drug"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def insert_return(name, modified, item_name=TEMPLATE, drug_name=None):
	insert("LRPMT Returns", name, docstatus=1, creation=modified, modified=modified)
	child = {"parent": name, "parenttype": "LRPMT Returns", "encounter_no": ENCOUNTER}
	if drug_name:
		insert(
			"Medication Return",
			frappe.generate_hash(),
			parentfield="drug_items",
			drug_name=drug_name,
			quantity_to_return=1,
			**child,
		)
	else:
		insert(
			"Item Return",
			frappe.generate_hash(),
			parentfield="lrpt_items",
			item_name=item_name,
			reference_doctype="Lab Test",
			quantity=1,
			**child,
		)


def get_rows(**filters):
	return execute({"from_date": "2026-01-05", "to_date": "2026-01-06", **filters})[1]


class TestLRPMTReturnsReport(FrappeTestCase):
	def setUp(self):
		insert(
			"Patient Encounter",
			ENCOUNTER,
			practitioner=PRACTITIONER,
			practitioner_name=PRACTITIONER_NAME,
		)
		insert("Lab Test Template", TEMPLATE, item=ITEM)

	def tearDown(self):
		frappe.db.rollback()

	def test_return_later_on_to_date_is_included(self):
		insert_return("_Test LR Return To Date", "2026-01-06 10:00:00")
		insert_return("_Test LR Return After", "2026-01-07 00:00:00")

		self.assertEqual(len(get_rows()), 1)
		self.assertEqual(len(get_rows(from_date="2026-01-06")), 1)

	def test_practitioner_filter_matches_practitioner_id(self):
		insert_return("_Test LR Return", "2026-01-05 09:00:00")

		self.assertEqual(len(get_rows(practitioner=PRACTITIONER)), 1)
		self.assertEqual(len(get_rows(practitioner="_Test LR Other")), 0)

	def test_item_filter_matches_template_and_drug_item(self):
		insert_return("_Test LR Lab Return", "2026-01-05 09:00:00")
		insert_return("_Test LR Drug Return", "2026-01-05 09:00:00", drug_name=DRUG)
		insert_return("_Test LR Other Return", "2026-01-05 09:00:00", item_name="_Test LR Other Template")

		self.assertEqual([row.item_name for row in get_rows(item=ITEM)], [TEMPLATE])
		self.assertEqual([row.item_name for row in get_rows(item=DRUG)], [DRUG])

	def test_identical_rows_from_two_returns_are_both_shown(self):
		insert_return("_Test LR Return 1", "2026-01-05 09:00:00")
		insert_return("_Test LR Return 2", "2026-01-05 11:00:00")

		self.assertEqual(len(get_rows()), 2)
