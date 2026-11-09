# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.nhif import utils
from hms_tz.nhif.doctype.insurance_approval_log import insurance_approval_log
from hms_tz.nhif.doctype.insurance_approval_log.insurance_approval_log import (
	INSURANCE_APPROVAL_LOG,
	insert_unissued_lines,
	upsert_approval_lines,
)
from hms_tz.patches import log_unissued_services_of_open_drafts as job

COMPANY = "_Test LU Company"
PATIENT = "_Test LU Patient"
APPOINTMENT = "_Test LU Visit"
CARD_NO = "110900292954"
DIALYSIS = "_Test LU Dialysis"
UNISSUED_DIALYSIS = {
	"CardNo": CARD_NO,
	"ItemCode": "6234",
	"ItemName": "Haemodialysis per session (Maximum 12 sessions per month)",
	"QuantityRequested": 12,
	"QuantityIssued": 2,
	"QuantityRemains": 10,
	"ApprovalReferenceNo": "901626062560",
	"ApprovalStatus": "Approved",
	"ApprovalDate": "2026-10-29T08:37:33.64",
	"Remarks": "Approved",
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


def patch_settings():
	"""Answer HMS TZ Setting with an NHIF-enabled mock and leave other cached docs alone."""
	settings = MagicMock(enable_nhif_api=1)
	get_cached_doc = frappe.get_cached_doc
	return patch.object(
		job.frappe,
		"get_cached_doc",
		side_effect=lambda doctype, *args: settings
		if doctype == "HMS TZ Setting"
		else get_cached_doc(doctype, *args),
	)


def get_log(reference_no):
	return frappe.get_doc(INSURANCE_APPROVAL_LOG, {"reference_no": reference_no})


class TestLogUnissuedServices(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TLU", default_currency="TZS")
		insert("Healthcare Insurance Company", "NHIF", insurance_company_name="NHIF")
		insert("Patient", PATIENT, first_name="Daniel", patient_name="Daniel Shillinde")
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
		frappe.db.savepoint("log_unissued_test")
		self.addCleanup(frappe.db.rollback, save_point="log_unissued_test")
		for patcher in (
			patch.object(utils.frappe, "enqueue"),
			patch.dict(frappe.flags, {"queued_approval_status": set()}),
		):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.enqueue = utils.frappe.enqueue
		for patcher in (
			patch.object(utils, "get_item_refcode", return_value="6234"),
			patch.object(insurance_approval_log, "get_item_refcode", return_value="6234"),
		):
			patcher.start()
			self.addCleanup(patcher.stop)

	def test_unissued_line_keeps_units_issued_before_the_log(self):
		insert_unissued_lines(
			[UNISSUED_DIALYSIS], APPOINTMENT, {"6234": ("Clinical Procedure Template", DIALYSIS)}
		)
		insert_unissued_lines([UNISSUED_DIALYSIS], APPOINTMENT, {})

		log = get_log("901626062560")
		self.assertEqual(frappe.db.count(INSURANCE_APPROVAL_LOG, {"reference_no": "901626062560"}), 1)
		self.assertEqual((log.qty_approved, log.qty_issued, log.qty_remaining), (12, 2, 10))
		self.assertEqual(
			(log.patient, log.service_name, str(log.date_requested)), (PATIENT, DIALYSIS, "2026-10-29")
		)
		self.assertFalse(log.usages[0].ref_docname)

	def test_approval_status_line_takes_over_the_unissued_log(self):
		insert_unissued_lines([UNISSUED_DIALYSIS], APPOINTMENT, {})

		upsert_approval_lines(
			[
				{
					"AuthorizedItemID": "AI-DIALYSIS",
					"ReferenceNo": "901626062560",
					"CardNo": CARD_NO,
					"ItemCode": "6234",
					"ApprovalStatus": "Approved",
					"QuantityApproved": 12,
					"ServiceDate": "2026-10-29T00:00:00",
				}
			],
			APPOINTMENT,
			{},
		)

		log = get_log("901626062560")
		self.assertEqual(frappe.db.count(INSURANCE_APPROVAL_LOG, {"reference_no": "901626062560"}), 1)
		self.assertEqual((log.authorized_item_id, log.qty_remaining), ("AI-DIALYSIS", 10))

	def test_open_restricted_drafts_are_found(self):
		insert_procedure("_Test LU Open")
		insert_procedure("_Test LU Numbered", approval_number="APR-1")
		insert_procedure("_Test LU Submitted", docstatus=1)
		insert_procedure("_Test LU Jubilee", insurance_company="Jubilee")
		insert_procedure("_Test LU Not Serviced", workflow_state="Not Serviced")
		insert(
			"Delivery Note",
			"_Test LU DN",
			company=COMPANY,
			customer="NHIF",
			hms_tz_appointment_no=APPOINTMENT,
		)
		insert(
			"Delivery Note",
			"_Test LU DN Not Serviced",
			company=COMPANY,
			customer="NHIF",
			workflow_state="Not Serviced",
		)
		rows = (("_Test LU DN", 1, "APR-2"), ("_Test LU DN", 2, None), ("_Test LU DN Not Serviced", 1, None))
		for parent, idx, approval_number in rows:
			insert(
				"Delivery Note Item",
				f"{parent} Item {idx}",
				parent=parent,
				parenttype="Delivery Note",
				parentfield="items",
				idx=idx,
				is_restricted=1,
				approval_number=approval_number,
			)

		drafts = set(job.get_open_restricted_drafts())

		self.assertIn(("Clinical Procedure", "_Test LU Open"), drafts)
		self.assertIn(("Delivery Note", "_Test LU DN"), drafts)
		self.assertNotIn(("Delivery Note", "_Test LU DN Not Serviced"), drafts)
		for name in ("_Test LU Numbered", "_Test LU Submitted", "_Test LU Jubilee", "_Test LU Not Serviced"):
			self.assertNotIn(("Clinical Procedure", name), drafts)

	@patch.object(job.frappe.db, "commit")
	def test_job_logs_each_card_once_and_sets_its_drafts(self, commit):
		insert_procedure("_Test LU Open 1")
		insert_procedure("_Test LU Open 2")
		with (
			patch.object(
				job,
				"get_open_restricted_drafts",
				return_value=[
					("Clinical Procedure", "_Test LU Open 1"),
					("Clinical Procedure", "_Test LU Open 2"),
				],
			),
			patch_settings(),
			patch.object(job, "request_unissued_services", return_value=[UNISSUED_DIALYSIS]) as request,
		):
			job.log_unissued_services_of_open_drafts()

		request.assert_called_once()
		self.assertEqual(request.call_args.args[1], CARD_NO)
		self.assertEqual(get_log("901626062560").service_name, DIALYSIS)
		for name in ("_Test LU Open 1", "_Test LU Open 2"):
			self.assertEqual(
				frappe.db.get_value("Clinical Procedure", name, "approval_number"), "901626062560"
			)
		self.assertEqual(commit.call_count, 3)

	@patch.object(job.frappe.db, "rollback")
	@patch.object(job.frappe.db, "commit")
	def test_failed_card_is_logged_and_skipped(self, commit, rollback):
		insert_procedure("_Test LU Open 1")
		with (
			patch.object(
				job,
				"get_open_restricted_drafts",
				return_value=[("Clinical Procedure", "_Test LU Open 1")],
			),
			patch_settings(),
			patch.object(job, "request_unissued_services", side_effect=frappe.ValidationError("NHIF down")),
			patch.object(job.frappe, "log_error") as log_error,
		):
			job.log_unissued_services_of_open_drafts()

		rollback.assert_called_once()
		commit.assert_not_called()
		self.assertIn(CARD_NO, log_error.call_args.kwargs["title"])

	@patch.object(job.frappe.db, "rollback")
	@patch.object(job.frappe.db, "commit")
	def test_failed_draft_keeps_the_log_and_other_drafts(self, commit, rollback):
		insert_procedure("_Test LU Open 1")
		insert_procedure("_Test LU Open 2")
		set_approval_numbers = job.set_approval_numbers_of_draft

		def set_draft(draft):
			if draft.name == "_Test LU Open 1":
				raise frappe.ValidationError("broken draft")
			return set_approval_numbers(draft)

		drafts = [("Clinical Procedure", "_Test LU Open 1"), ("Clinical Procedure", "_Test LU Open 2")]
		with (
			patch.object(job, "get_open_restricted_drafts", return_value=drafts),
			patch_settings(),
			patch.object(job, "request_unissued_services", return_value=[UNISSUED_DIALYSIS]),
			patch.object(job, "set_approval_numbers_of_draft", side_effect=set_draft),
			patch.object(job.frappe, "log_error") as log_error,
		):
			job.log_unissued_services_of_open_drafts()

		self.assertTrue(frappe.db.exists(INSURANCE_APPROVAL_LOG, {"reference_no": "901626062560"}))
		self.assertEqual(
			frappe.db.get_value("Clinical Procedure", "_Test LU Open 2", "approval_number"), "901626062560"
		)
		self.assertEqual((rollback.call_count, commit.call_count), (1, 2))
		self.assertEqual(log_error.call_args.kwargs["reference_name"], "_Test LU Open 1")

	def test_delivery_note_item_gets_approval_number_and_remaining_qty(self):
		insert_unissued_lines([UNISSUED_DIALYSIS], APPOINTMENT, {})
		insert("Drug Prescription", "_Test LU Drug Row", drug_code=DIALYSIS)
		insert(
			"Delivery Note",
			"_Test LU DN",
			company=COMPANY,
			patient=PATIENT,
			hms_tz_appointment_no=APPOINTMENT,
		)
		for idx, approval_number in ((1, "APR-2"), (2, None)):
			insert(
				"Delivery Note Item",
				f"_Test LU DN Item {idx}",
				parent="_Test LU DN",
				parenttype="Delivery Note",
				parentfield="items",
				idx=idx,
				qty=10,
				is_restricted=1,
				approval_number=approval_number,
				reference_doctype="Drug Prescription",
				reference_name="_Test LU Drug Row",
			)

		job.set_approval_numbers_of_draft(frappe.get_doc("Delivery Note", "_Test LU DN"))

		values = frappe.db.get_value(
			"Delivery Note Item", "_Test LU DN Item 2", ["approval_number", "approved_qty"], as_dict=True
		)
		self.assertEqual((values.approval_number, values.approved_qty), ("901626062560", 10))
		self.assertEqual(
			frappe.db.get_value("Delivery Note Item", "_Test LU DN Item 1", "approval_number"), "APR-2"
		)

	@patch.object(job.frappe.db, "commit")
	def test_drafts_left_without_number_ask_nhif_for_status(self, commit):
		insert_procedure("_Test LU Open 1")
		insert_procedure("_Test LU Open 2")
		open_1, open_2 = ("Clinical Procedure", "_Test LU Open 1"), ("Clinical Procedure", "_Test LU Open 2")
		cached_value = frappe.get_cached_value

		def get_cached_value(doctype, *args, **kwargs):
			return 1 if doctype == "HMS TZ Setting" else cached_value(doctype, *args, **kwargs)

		with (
			patch.object(job, "get_open_restricted_drafts", side_effect=[[open_1, open_2], [open_2]]),
			patch.object(utils.frappe, "get_cached_value", side_effect=get_cached_value),
			patch_settings(),
			patch.object(job, "request_unissued_services", return_value=[UNISSUED_DIALYSIS]),
		):
			job.log_unissued_services_of_open_drafts()

		self.enqueue.assert_called_once()
		self.assertEqual(self.enqueue.call_args.kwargs["ref_docname"], "_Test LU Open 2")
