from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif.nhif_api import reference
from hms_tz.nhif.nhif_api.reference import sync_stg_records

NHIF_CUSTOMER = "_Test STG NHIF"


def add_ref_code(item, ref_code):
	frappe.get_doc(
		doctype="Item Customer Detail",
		parent=item,
		parenttype="Item",
		parentfield="customer_items",
		customer_name=NHIF_CUSTOMER,
		ref_code=ref_code,
	).db_insert()


def get_stg_rows():
	return frappe.get_all(
		"NHIF STG",
		fields=["stg_type", "code", "code_value", "item_code", "service_type", "service_name", "disabled"],
		order_by="stg_type, service_name",
	)


def diagnosis(code, item_code):
	return {"DiseaseCode": code, "Diagnoses": [{"ItemCode": item_code}]}


class TestNHIFSTGSync(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.delete("NHIF STG")
		frappe.get_doc(doctype="Code System", code_system="ICD-10", uri="http://test.local/icd").insert(
			ignore_if_duplicate=True
		)
		frappe.get_doc(doctype="Code Value", code_system="ICD-10", code_value="ZST1").insert(
			ignore_if_duplicate=True
		)
		cls.lab = frappe.get_value(
			"Lab Test Template", {"item": ["is", "set"]}, ["name", "item"], as_dict=True
		)
		cls.therapy = frappe.get_value(
			"Therapy Type", {"item": ["is", "set"]}, ["name", "item"], as_dict=True
		)
		add_ref_code(cls.lab.item, "STG-LAB")
		add_ref_code(cls.therapy.item, "STG-THERAPY")

	def tearDown(self):
		frappe.db.delete("NHIF STG")

	def test_creates_diagnosis_and_treatment_rows_for_mapped_item_codes(self):
		stg_data = [
			{
				"DiseaseCode": "ZST1",
				"Diagnoses": [{"ItemCode": "STG-LAB"}, {"ItemCode": "STG-UNMAPPED"}],
				"Treatments": [{"ItemCode": "STG-THERAPY", "TreatmentID": 1}],
			}
		]

		sync_stg_records(stg_data, NHIF_CUSTOMER)

		self.assertEqual(
			[tuple(row.values()) for row in get_stg_rows()],
			[
				("Diagnosis", "ZST1", "ICD-10 ZST1", "STG-LAB", "Lab Test Template", self.lab.name, 0),
				("Treatment", "ZST1", "ICD-10 ZST1", "STG-THERAPY", "Therapy Type", self.therapy.name, 0),
			],
		)

	def test_second_run_creates_only_new_rows(self):
		sync_stg_records([diagnosis("ZST1", "STG-LAB")], NHIF_CUSTOMER)

		sync_stg_records([diagnosis("ZST1", "STG-LAB"), diagnosis("ZST2", "STG-LAB")], NHIF_CUSTOMER)

		rows = get_stg_rows()
		self.assertEqual(sorted(row.code for row in rows), ["ZST1", "ZST2"])
		self.assertIsNone(next(row for row in rows if row.code == "ZST2").code_value)

	def test_disables_and_comments_stg_removed_by_moh(self):
		sync_stg_records([diagnosis("ZST1", "STG-LAB"), diagnosis("ZST2", "STG-LAB")], NHIF_CUSTOMER)

		sync_stg_records([diagnosis("ZST1", "STG-LAB")], NHIF_CUSTOMER)

		removed = frappe.get_value("NHIF STG", {"code": "ZST2"}, ["name", "disabled"], as_dict=True)
		self.assertEqual(removed.disabled, 1)
		self.assertEqual(frappe.get_value("NHIF STG", {"code": "ZST1"}, "disabled"), 0)
		comment = frappe.get_value(
			"Comment",
			{"reference_doctype": "NHIF STG", "reference_name": removed.name, "comment_type": "Comment"},
			"content",
		)
		self.assertIn("MoH removed Diagnosis item code STG-LAB for disease code ZST2", comment)

	def test_empty_response_disables_nothing(self):
		sync_stg_records([diagnosis("ZST1", "STG-LAB")], NHIF_CUSTOMER)

		sync_stg_records([], NHIF_CUSTOMER)

		self.assertEqual(frappe.get_value("NHIF STG", {"code": "ZST1"}, "disabled"), 0)

	def test_sync_auto_commits_many_writes_only_while_running(self):
		flags = []
		with patch.object(
			reference,
			"create_stg_records",
			side_effect=lambda *args: flags.append(frappe.db.auto_commit_on_many_writes),
		):
			sync_stg_records([diagnosis("ZST1", "STG-LAB")], NHIF_CUSTOMER)

		self.assertEqual(flags, [True])
		self.assertFalse(frappe.db.auto_commit_on_many_writes)

	def test_skips_service_types_outside_stg(self):
		service_map = {
			"STG-UNIT": [frappe._dict(service_type="Healthcare Service Unit Type", service_name="Ward")]
		}
		with patch.object(reference, "get_insurance_items", return_value=service_map):
			sync_stg_records([diagnosis("ZST1", "STG-UNIT")], NHIF_CUSTOMER)

		self.assertEqual(get_stg_rows(), [])

	def test_failed_fetch_creates_no_rows(self):
		settings = MagicMock(nhif_claim_url="http://nhif.test", nhif_customer_name=NHIF_CUSTOMER)
		settings.name = "_Test Company"
		response = MagicMock(status_code=500, text="error")
		with (
			patch.object(reference.frappe, "get_cached_doc", return_value=settings),
			patch.object(reference.requests, "request", return_value=response),
			patch.object(reference, "add_log"),
			patch.object(reference, "sync_stg_records") as sync_records,
		):
			reference.get_stg_records("_Test Company")

		sync_records.assert_not_called()
