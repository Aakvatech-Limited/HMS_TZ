# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif import utils

COMPANY = "_Test POC Company"
TEMPLATE = "_Test POC Xray"
POINT_OF_CARE = "_Test POC Radiology"


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()


def issue(doctype, name, service_type, service_name):
	return utils.issue_nhif_service(
		doctype, name, service_type, service_name, "image", "fp", biometric_method="NONE"
	)


def issue_radiology(name):
	return issue("Radiology Examination", name, "Radiology Examination Template", TEMPLATE)


class TestIssueServicePocReference(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("HMS TZ Setting", COMPANY, company=COMPANY, enable_nhif_api=1)
		insert("Radiology Examination Template", TEMPLATE, item=TEMPLATE, points_of_care=POINT_OF_CARE)

	def setUp(self):
		self.calls = Mock()
		self.calls.get_poc_reference_no.return_value = {"ReferenceNo": "POC-1"}
		self.calls.issue_approved_service.return_value = {"ServiceReferenceNo": "SRV-1"}
		for name in ("get_poc_reference_no", "issue_approved_service"):
			patcher = patch.object(utils, name, getattr(self.calls, name))
			patcher.start()
			self.addCleanup(patcher.stop)
		patcher = patch.object(frappe.db, "commit", self.calls.commit)
		patcher.start()
		self.addCleanup(patcher.stop)

	def insert_radiology(self, name, poc_reference_no=None, approval_number="APR-1"):
		insert(
			"Radiology Examination",
			name,
			company=COMPANY,
			radiology_examination_template=TEMPLATE,
			insurance_company="NHIF",
			approval_number=approval_number,
			is_restricted=1,
			poc_reference_no=poc_reference_no,
		)

	def test_missing_poc_is_generated_after_issue(self):
		self.insert_radiology("_Test POC RE 1")

		data = issue_radiology("_Test POC RE 1")

		self.assertEqual(
			[call[0] for call in self.calls.mock_calls],
			["issue_approved_service", "commit", "get_poc_reference_no"],
		)
		self.assertEqual(self.calls.get_poc_reference_no.call_args.kwargs["fingerprint"], "image")
		self.assertEqual(
			frappe.db.get_value("Radiology Examination", "_Test POC RE 1", "poc_reference_no"), "POC-1"
		)
		self.assertEqual(data["ServiceReferenceNo"], "SRV-1")

	def test_existing_poc_is_not_regenerated(self):
		self.insert_radiology("_Test POC RE 2", poc_reference_no="POC-OLD")

		issue_radiology("_Test POC RE 2")

		self.calls.get_poc_reference_no.assert_not_called()
		self.calls.issue_approved_service.assert_called_once()

	def test_failed_issue_skips_poc(self):
		self.insert_radiology("_Test POC RE 4")
		self.calls.issue_approved_service.return_value = None

		issue_radiology("_Test POC RE 4")

		self.calls.get_poc_reference_no.assert_not_called()

	def test_missing_approval_number_throws_before_poc(self):
		self.insert_radiology("_Test POC RE 3", approval_number=None)

		with self.assertRaises(frappe.ValidationError):
			issue_radiology("_Test POC RE 3")

		self.calls.get_poc_reference_no.assert_not_called()

	def test_delivery_note_uses_pharmacy_point_of_care(self):
		insert("Delivery Note", "_Test POC DN 1", company=COMPANY, customer="NHIF")
		insert(
			"Delivery Note Item",
			"_Test POC DN Item 1",
			parent="_Test POC DN 1",
			parenttype="Delivery Note",
			parentfield="items",
			item_code="_Test POC Drug",
			is_restricted=1,
			approval_number="APR-2",
			qty=1,
		)

		issue("Delivery Note", "_Test POC DN 1", "Medication", "")

		self.assertEqual(self.calls.get_poc_reference_no.call_args.kwargs["point_of_care"], "Pharmacy")
		self.assertEqual(frappe.db.get_value("Delivery Note", "_Test POC DN 1", "poc_reference_no"), "POC-1")
		self.calls.issue_approved_service.assert_called_once()

	def test_delivery_note_without_restricted_items_skips_poc(self):
		insert("Delivery Note", "_Test POC DN 2", company=COMPANY, customer="NHIF")

		issue("Delivery Note", "_Test POC DN 2", "Medication", "")

		self.calls.get_poc_reference_no.assert_not_called()
