# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif import utils
from hms_tz.nhif.doctype.insurance_approval_log import insurance_approval_log
from hms_tz.nhif.doctype.insurance_approval_log.insurance_approval_log import (
	INSURANCE_APPROVAL_LOG,
	add_approval_usage,
)

COMPANY = "_Test VA Company"
PATIENT = "_Test VA Patient"
APPOINTMENT = "_Test VA Visit"
CARD_NO = "110900292954"
DIALYSIS = "_Test VA Dialysis"
EARLIER_DIALYSIS = {
	"CardNo": CARD_NO,
	"ItemCode": "6234",
	"QuantityRequested": 12,
	"QuantityIssued": 1,
	"QuantityRemains": 11,
	"ApprovalReferenceNo": "701627864200",
	"ApprovalStatus": "Approved",
	"ApprovalDate": "2026-10-29T08:37:33.64",
	"DateRequested": "2026-10-29T08:32:46.537",
}


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def insert_procedure(name, **values):
	defaults = {
		"company": COMPANY,
		"patient": PATIENT,
		"appointment": APPOINTMENT,
		"procedure_template": DIALYSIS,
		"insurance_company": "NHIF",
		"is_restricted": 1,
	}
	insert("Clinical Procedure", name, **{**defaults, **values})


class TestNHIFVisitApprovals(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TVA", default_currency="TZS")
		if not frappe.db.exists("Healthcare Insurance Company", "NHIF"):
			insert("Healthcare Insurance Company", "NHIF", insurance_company_name="NHIF")
		insert("Patient", PATIENT, first_name="Sophia", patient_name="Sophia Wilson")
		insert("Clinical Procedure Template", DIALYSIS, template=DIALYSIS)
		insert(
			"Patient Appointment",
			APPOINTMENT,
			patient=PATIENT,
			company=COMPANY,
			insurance_company="NHIF",
			coverage_plan_card_number=CARD_NO,
		)

	def setUp(self):
		frappe.db.savepoint("visit_approvals_test")
		self.addCleanup(frappe.db.rollback, save_point="visit_approvals_test")
		get_cached_doc = frappe.get_cached_doc
		patches = {
			"request": patch.object(utils, "request_unissued_services", return_value=[EARLIER_DIALYSIS]),
			"status": patch.object(utils, "get_approval_status"),
			"log_error": patch.object(utils.frappe, "log_error"),
		}
		for patcher in (
			*patches.values(),
			patch.object(utils, "get_item_refcode", return_value="6234"),
			patch.object(insurance_approval_log, "get_item_refcode", return_value="6234"),
			patch.object(
				utils.frappe,
				"get_cached_doc",
				side_effect=lambda doctype, *args: MagicMock()
				if doctype == "HMS TZ Setting"
				else get_cached_doc(doctype, *args),
			),
		):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.request, self.status = utils.request_unissued_services, utils.get_approval_status

	def test_approval_of_earlier_visit_is_given_and_its_issue_counted(self):
		insert_procedure("_Test VA Procedure")

		utils.get_visit_approvals("Clinical Procedure", "_Test VA Procedure")

		self.assertEqual(self.request.call_args.args[1], CARD_NO)
		self.status.assert_not_called()
		procedure = frappe.get_doc("Clinical Procedure", "_Test VA Procedure")
		self.assertEqual((procedure.approval_number, procedure.approval_status), ("701627864200", "Approved"))

		add_approval_usage(procedure, procedure.approval_number, 1, "411627875553")

		log = frappe.get_doc(INSURANCE_APPROVAL_LOG, {"reference_no": "701627864200"})
		self.assertEqual((log.service_name, log.qty_issued, log.qty_remaining), (DIALYSIS, 2, 10))

	def test_service_left_without_approval_asks_nhif_for_status(self):
		insert_procedure("_Test VA Procedure")
		self.request.return_value = []

		utils.get_visit_approvals("Clinical Procedure", "_Test VA Procedure")

		self.status.assert_called_once_with("Clinical Procedure", "_Test VA Procedure")

	def test_failed_unissued_request_is_logged_and_status_still_asked(self):
		insert_procedure("_Test VA Procedure")
		self.request.side_effect = frappe.ValidationError("NHIF down")

		utils.get_visit_approvals("Clinical Procedure", "_Test VA Procedure")

		self.assertEqual(utils.frappe.log_error.call_args.kwargs["reference_name"], "_Test VA Procedure")
		self.status.assert_called_once()

	def test_visit_without_open_drafts_does_not_ask_nhif(self):
		insert_procedure("_Test VA Numbered", approval_number="TYPED-1")

		utils.get_visit_approvals("Clinical Procedure", "_Test VA Numbered")

		self.request.assert_not_called()
		self.status.assert_not_called()

	def test_open_drafts_of_visit_include_delivery_notes_once(self):
		insert_procedure("_Test VA Open")
		insert_procedure("_Test VA Submitted", docstatus=1)
		insert_procedure("_Test VA Not Serviced", workflow_state="Not Serviced")
		insert("Delivery Note", "_Test VA DN", company=COMPANY, hms_tz_appointment_no=APPOINTMENT)
		for idx in (1, 2):
			insert(
				"Delivery Note Item",
				f"_Test VA DN Item {idx}",
				parent="_Test VA DN",
				parenttype="Delivery Note",
				parentfield="items",
				idx=idx,
				is_restricted=1,
			)

		drafts = utils.get_open_drafts_of_visit(APPOINTMENT)

		self.assertEqual(
			[(draft.doctype, draft.name) for draft in drafts],
			[("Clinical Procedure", "_Test VA Open"), ("Delivery Note", "_Test VA DN")],
		)
