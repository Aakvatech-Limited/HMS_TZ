# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt
from unittest import skip
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from hms_tz.nhif import utils
from hms_tz.nhif.doctype.insurance_approval_log import insurance_approval_log
from hms_tz.nhif.doctype.insurance_approval_log.insurance_approval_log import (
	INSURANCE_APPROVAL_LOG,
	add_approval_usage,
	set_approval_number_from_log,
	upsert_approval_lines,
)
from hms_tz.nhif.nhif_api import approval_status
from hms_tz.nhif.nhif_api.approval_status import validate_approved_qty

COMPANY = "_Test IAL Company"
PATIENT = "_Test IAL Patient"
CARD_NO = "202300565410"
DIALYSIS = "_Test IAL Dialysis"
DRUG = "_Test IAL Erythropoietin"
CODES = {DIALYSIS: "6234", DRUG: "11291"}


def insert(doctype, name, **values):
	doc = frappe.new_doc(doctype)
	doc.update({"name": name, **values})
	doc.db_insert()
	return doc


def insert_appointment(name, card_no=CARD_NO, insurance_company="NHIF"):
	insert(
		"Patient Appointment",
		name,
		patient=PATIENT,
		company=COMPANY,
		insurance_company=insurance_company,
		coverage_plan_card_number=card_no,
	)


def approval_line(item_id, item_code, reference_no, approved, status="Approved", service_date=None):
	"""An approval line shaped like the NHIF GetApprovalStatus response."""
	return {
		"AuthorizedItemID": item_id,
		"ServiceAuthorizationID": f"SA-{item_id}",
		"ReferenceNo": reference_no,
		"ApprovalDate": f"{service_date or today()}T12:49:06.89",
		"QuantityRequested": approved,
		"QuantityApproved": approved,
		"ItemCode": item_code,
		"CardNo": CARD_NO,
		"ApprovalStatus": status,
		"ApprovedBy": "Kennedy D. Selestine",
		"PrescribedBy": "Chrispine Ernest Desiderius",
		"ServiceDate": f"{service_date or today()}T00:00:00",
		"Remarks": status,
	}


def get_log(authorized_item_id):
	return frappe.get_doc(INSURANCE_APPROVAL_LOG, {"authorized_item_id": authorized_item_id})


def new_procedure(appointment, approval_number=None):
	doc = frappe.new_doc("Clinical Procedure")
	doc.update(
		{
			"patient": PATIENT,
			"company": COMPANY,
			"appointment": appointment,
			"procedure_template": DIALYSIS,
			"is_restricted": 1,
			"approval_number": approval_number,
		}
	)
	return doc


class TestInsuranceApprovalLog(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		insert("Company", COMPANY, company_name=COMPANY, abbr="_TIAL", default_currency="TZS")
		insert("Healthcare Insurance Company", "NHIF", insurance_company_name="NHIF")
		insert("Patient", PATIENT, first_name="Halima", patient_name="Halima Mhando")
		insert("Clinical Procedure Template", DIALYSIS, template=DIALYSIS)
		insert("Medication", DRUG)
		insert_appointment("_Test IAL Visit 1")

	def setUp(self):
		getattr(frappe.local, "request_cache", {}).clear()
		frappe.db.savepoint("approval_log_test")
		self.addCleanup(frappe.db.rollback, save_point="approval_log_test")
		refcode = patch.object(
			insurance_approval_log, "get_item_refcode", side_effect=lambda doctype, name, *args: CODES[name]
		)
		refcode.start()
		self.addCleanup(refcode.stop)
		get_cached_value = frappe.get_cached_value
		for patcher in (
			patch.object(utils.frappe, "enqueue"),
			patch.object(
				utils.frappe,
				"get_cached_value",
				side_effect=lambda doctype, *args, **kwargs: 1
				if doctype == "HMS TZ Setting"
				else get_cached_value(doctype, *args, **kwargs),
			),
			patch.dict(frappe.flags, {"queued_approval_status": set()}),
		):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.enqueue = utils.frappe.enqueue

	def log_dialysis(self, approved=12, service_date=None):
		upsert_approval_lines(
			[approval_line("AI-DIALYSIS", "6234", "211626100436", approved, service_date=service_date)],
			"_Test IAL Visit 1",
			{"6234": ("Clinical Procedure Template", DIALYSIS)},
		)
		return get_log("AI-DIALYSIS")

	def test_line_is_logged_once_with_patient_and_service(self):
		self.log_dialysis()
		log = self.log_dialysis()

		self.assertEqual(frappe.db.count(INSURANCE_APPROVAL_LOG, {"authorized_item_id": "AI-DIALYSIS"}), 1)
		self.assertEqual((log.patient, log.patient_name, log.card_no), (PATIENT, "Halima Mhando", CARD_NO))
		self.assertEqual((log.service_type, log.service_name), ("Clinical Procedure Template", DIALYSIS))
		# expiry_date is not set until NHIF returns one
		self.assertIsNone(log.expiry_date)
		self.assertEqual((log.qty_approved, log.qty_issued, log.qty_remaining), (12, 0, 12))

	def test_pending_line_is_approved_in_place(self):
		lines = [approval_line("AI-EPO", "11291", None, 12, status="Pending")]
		upsert_approval_lines(lines, "_Test IAL Visit 1", {})
		lines[0].update(ReferenceNo="911626101649", ApprovalStatus="Approved")
		upsert_approval_lines(lines, "_Test IAL Visit 1", {})

		values = frappe.db.get_value(
			INSURANCE_APPROVAL_LOG,
			{"authorized_item_id": "AI-EPO"},
			["reference_no", "approval_status"],
			as_dict=True,
		)
		self.assertEqual((values.reference_no, values.approval_status), ("911626101649", "Approved"))

	def test_get_approval_status_logs_every_line(self):
		lines = [
			approval_line("AI-EPO-12", "11291", "911626101649", 12),
			approval_line("AI-EPO-1", "11291", None, 1, status="Rejected"),
			approval_line("AI-DIALYSIS", "6234", "211626100436", 1),
		]
		doc = frappe._dict(doctype="Clinical Procedure", name="_Test IAL Missing", company=COMPANY)
		with patch.object(approval_status.frappe, "msgprint"):
			approval_status.update_approval_status(doc, "_Test IAL Visit 1", lines)

		logs = frappe.get_all(
			INSURANCE_APPROVAL_LOG,
			filters={"patient": PATIENT},
			fields=["authorized_item_id", "reference_no", "approval_status"],
			order_by="authorized_item_id",
		)
		self.assertEqual(
			[(log.authorized_item_id, log.reference_no, log.approval_status) for log in logs],
			[
				("AI-DIALYSIS", "211626100436", "Approved"),
				("AI-EPO-1", None, "Rejected"),
				("AI-EPO-12", "911626101649", "Approved"),
			],
		)

	def test_rejected_line_is_not_given(self):
		upsert_approval_lines(
			[approval_line("AI-DIALYSIS", "6234", None, 12, status="Rejected")], "_Test IAL Visit 1", {}
		)
		doc = new_procedure("_Test IAL Visit 1")

		set_approval_number_from_log(doc)

		self.assertFalse(doc.approval_number)

	def test_dialysis_approval_is_used_on_later_visits_until_sessions_end(self):
		log = self.log_dialysis(approved=3)

		for number in range(1, 4):
			appointment = f"_Test IAL Visit Day {number}"
			insert_appointment(appointment)
			doc = new_procedure(appointment)
			set_approval_number_from_log(doc)
			self.assertEqual((doc.approval_number, doc.authorized_item_id), ("211626100436", "AI-DIALYSIS"))
			doc.name = f"_Test IAL Procedure {number}"
			doc.db_insert()
			add_approval_usage(doc, doc.approval_number, 1, f"SR-{number}")

		insert_appointment("_Test IAL Visit Day 4")
		fourth = new_procedure("_Test IAL Visit Day 4")
		set_approval_number_from_log(fourth)
		self.assertFalse(fourth.approval_number)

		log.reload()
		self.assertEqual((log.qty_issued, log.qty_remaining), (3, 0))
		self.assertEqual(
			[row.appointment for row in log.usages],
			["_Test IAL Visit Day 1", "_Test IAL Visit Day 2", "_Test IAL Visit Day 3"],
		)

	def test_draft_without_issue_does_not_use_a_unit(self):
		self.log_dialysis(approved=1)
		first, second = new_procedure("_Test IAL Visit 1"), new_procedure("_Test IAL Visit 1")

		set_approval_number_from_log(first)
		set_approval_number_from_log(second)

		self.assertEqual(second.approval_number, "211626100436")

	@skip("Expiry filter is off until NHIF returns an expiry date")
	def test_expired_approval_is_not_given(self):
		self.log_dialysis(service_date=add_days(today(), -31))
		doc = new_procedure("_Test IAL Visit 1")

		set_approval_number_from_log(doc)

		self.assertFalse(doc.approval_number)

	def test_approval_of_another_card_is_not_given(self):
		self.log_dialysis()
		insert_appointment("_Test IAL New Card", card_no="999900000001")
		doc = new_procedure("_Test IAL New Card")

		set_approval_number_from_log(doc)

		self.assertFalse(doc.approval_number)

	def test_service_with_approval_number_is_kept(self):
		self.log_dialysis()
		doc = new_procedure("_Test IAL Visit 1", approval_number="TYPED-1")

		set_approval_number_from_log(doc)

		self.assertEqual(doc.approval_number, "TYPED-1")

	def test_typed_approval_number_counts_on_issue(self):
		log = self.log_dialysis()
		typed = insert(
			"Clinical Procedure", "_Test IAL Typed", patient=PATIENT, appointment="_Test IAL Visit 1"
		)
		unknown = insert(
			"Clinical Procedure", "_Test IAL Unknown", patient=PATIENT, appointment="_Test IAL Visit 1"
		)

		add_approval_usage(typed, "211626100436", 1, "SR-TYPED")
		add_approval_usage(unknown, "NOT-IN-LOG", 1, "SR-UNKNOWN")

		log.reload()
		self.assertEqual((log.qty_issued, log.usages[0].ref_docname), (1, "_Test IAL Typed"))

	def test_approval_of_another_insurer_is_not_given(self):
		self.log_dialysis()
		insert_appointment("_Test IAL Jubilee", insurance_company="Jubilee")
		doc = new_procedure("_Test IAL Jubilee")

		set_approval_number_from_log(doc)

		self.assertFalse(doc.approval_number)

	def test_delivery_note_item_gets_short_approval_and_is_stopped(self):
		upsert_approval_lines(
			[approval_line("AI-SITAGLIPTIN", "11291", "611626102638", 180)],
			"_Test IAL Visit 1",
			{"11291": ("Medication", DRUG)},
		)
		log = get_log("AI-SITAGLIPTIN")
		log.add_usage(frappe._dict(doctype="Delivery Note", name=None), 90, "SR-FIRST")
		insert("Drug Prescription", "_Test IAL Drug Row", drug_code=DRUG)
		doc = frappe.new_doc("Delivery Note")
		doc.update({"patient": PATIENT, "company": COMPANY, "hms_tz_appointment_no": "_Test IAL Visit 1"})
		item = doc.append(
			"items",
			{
				"qty": 180,
				"is_restricted": 1,
				"reference_doctype": "Drug Prescription",
				"reference_name": "_Test IAL Drug Row",
			},
		)

		set_approval_number_from_log(doc)

		self.assertEqual((item.approval_number, item.approved_qty), ("611626102638", 90))
		self.assertRaises(frappe.ValidationError, validate_approved_qty, item, "Sitagliptin")

	def test_new_service_not_in_log_asks_nhif_in_background(self):
		doc = new_procedure("_Test IAL Visit 1")
		doc.name = "_Test IAL New"

		set_approval_number_from_log(doc)

		self.enqueue.assert_called_once_with(
			"hms_tz.nhif.utils.get_visit_approvals",
			job_id="nhif_approval_status::_Test IAL Visit 1",
			deduplicate=True,
			enqueue_after_commit=True,
			ref_doctype="Clinical Procedure",
			ref_docname="_Test IAL New",
		)

	def test_service_covered_by_log_does_not_ask_nhif(self):
		self.log_dialysis()

		set_approval_number_from_log(new_procedure("_Test IAL Visit 1"))

		self.enqueue.assert_not_called()

	def test_saved_service_asks_nhif_only_when_it_becomes_restricted(self):
		for was_restricted, is_queued in ((0, True), (1, False)):
			self.enqueue.reset_mock()
			name = f"_Test IAL Saved {was_restricted}"
			insert(
				"Clinical Procedure",
				name,
				patient=PATIENT,
				company=COMPANY,
				appointment="_Test IAL Visit 1",
				procedure_template=DIALYSIS,
				is_restricted=was_restricted,
			)
			doc = frappe.get_doc("Clinical Procedure", name)
			doc.load_doc_before_save()
			doc.is_restricted = 1

			set_approval_number_from_log(doc)

			self.assertEqual(self.enqueue.called, is_queued)

	def test_service_of_another_insurer_does_not_ask_nhif(self):
		insert_appointment("_Test IAL Jubilee", insurance_company="Jubilee")

		set_approval_number_from_log(new_procedure("_Test IAL Jubilee"))

		self.enqueue.assert_not_called()

	def test_visit_is_queued_once_per_transaction(self):
		for name in ("_Test IAL First", "_Test IAL Second"):
			doc = new_procedure("_Test IAL Visit 1")
			doc.name = name
			set_approval_number_from_log(doc)

		self.enqueue.assert_called_once()
