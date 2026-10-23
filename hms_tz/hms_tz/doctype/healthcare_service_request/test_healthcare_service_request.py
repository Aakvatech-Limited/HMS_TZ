# Copyright (c) 2025, Aakvatech and Contributors
# See license.txt
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import set_approval_state
from hms_tz.jubilee.api.preauthorization import get_bill_no


def jubilee_rows(*amounts):
	"""Rows shaped like get_jubilee_payment_rows, for mocking the cross-HSR query."""
	return [frappe._dict({"amount": amount}) for amount in amounts]


def make_request(**overrides):
	"""Unsaved Healthcare Service Request, enough to exercise the controller guards."""
	hsr = frappe.new_doc("Healthcare Service Request")
	hsr.update(overrides)

	return hsr


def add_payment(hsr, **overrides):
	row = {
		"service_type": "Lab Test Template",
		"service_name": "Full Blood Picture",
		"ref_docname": "row-1",
		"payment_type": "Insurance",
		"percent_covered": 100,
		"qty": 1,
		"rate": 10000,
		"amount": 10000,
	}
	row.update(overrides)

	return hsr.append("payments", row)


class TestHealthcareServiceRequest(FrappeTestCase):
	def test_approval_guard_ignores_requests_without_approval(self):
		make_request(requires_approval=0).validate_approval_status()

	def test_approval_guard_blocks_unsent_request(self):
		hsr = make_request(requires_approval=1, submission_id="")

		with self.assertRaises(frappe.ValidationError) as error:
			hsr.validate_approval_status()

		self.assertIn("Approval has not been sent", str(error.exception))

	def test_approval_guard_blocks_pending_status(self):
		hsr = make_request(
			requires_approval=1,
			submission_id="SUB-1",
			approval_status="PENDING",
		)

		self.assertRaises(frappe.ValidationError, hsr.validate_approval_status)

	def test_approval_guard_blocks_error_status(self):
		hsr = make_request(
			requires_approval=1,
			submission_id="SUB-1",
			approval_status="ERROR",
		)

		self.assertRaises(frappe.ValidationError, hsr.validate_approval_status)

	def test_approval_guard_allows_approved_status(self):
		hsr = make_request(
			requires_approval=1,
			submission_id="SUB-1",
			approval_status="Approved",
		)

		hsr.validate_approval_status()

	def test_approval_guard_allows_rejected_status(self):
		"""Billing moves rejected services to cash rows, so rejection must not block."""
		hsr = make_request(
			requires_approval=1,
			submission_id="SUB-1",
			approval_status="REJECTED",
		)

		hsr.validate_approval_status()

	def test_approved_amount_guard_ignores_request_without_approval(self):
		hsr = make_request(requires_approval=0, approved_amount=10000)

		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows",
			return_value=jubilee_rows(50000),
		) as get_rows:
			hsr.validate_approved_amount()

		get_rows.assert_not_called()

	def test_approved_amount_guard_ignores_request_without_approved_amount(self):
		hsr = make_request(requires_approval=1, approved_amount=0)

		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows",
			return_value=jubilee_rows(50000),
		):
			hsr.validate_approved_amount()

	def test_approved_amount_guard_allows_total_within_approved_amount(self):
		hsr = make_request(requires_approval=1, approved_amount=20000, appointment="APT-1")

		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows",
			return_value=jubilee_rows(10000, 10000),
		) as get_rows:
			hsr.validate_approved_amount()

		get_rows.assert_called_once_with("APT-1")

	def test_approved_amount_guard_blocks_total_above_approved_amount(self):
		"""Total spans every Service Request on the appointment, not just this one."""
		hsr = make_request(requires_approval=1, approved_amount=20000, appointment="APT-1")

		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows",
			return_value=jubilee_rows(15000, 10000),
		):
			with self.assertRaises(frappe.ValidationError) as error:
				hsr.validate_approved_amount()

		self.assertIn("exceeds", str(error.exception))

	def test_service_percentage_accepts_insurance_and_cash_split(self):
		"""A 60/40 split is how a partial Jubilee approval gets paid."""
		hsr = make_request()
		add_payment(hsr, percent_covered=60, amount=6000)
		add_payment(hsr, payment_type="Cash", percent_covered=40, amount=4000)

		hsr.validate_service_percentage()

	def test_service_percentage_rejects_short_split(self):
		hsr = make_request()
		add_payment(hsr, percent_covered=60, amount=6000)

		self.assertRaises(frappe.ValidationError, hsr.validate_service_percentage)

	def test_approval_state_returns_false_without_flag(self):
		"""No flag means the normal auto-submit path is untouched."""
		frappe.flags.hsr_requires_approval = None

		self.assertFalse(set_approval_state(make_request(), ""))

	def test_approval_state_stamps_fields_from_flag(self):
		hsr = make_request()
		hsr.db_update = lambda: None
		frappe.flags.hsr_requires_approval = {
			"jubilee_benefit": None,
			"benefit_code": "7905",
		}

		try:
			pending = set_approval_state(hsr, "PROC-1")
		finally:
			frappe.flags.hsr_requires_approval = None

		self.assertTrue(pending)
		self.assertEqual(hsr.requires_approval, 1)
		self.assertEqual(hsr.benefit_code, "7905")
		self.assertEqual(hsr.jubilee_procedure, "PROC-1")

	def test_approval_guard_allows_email_approval_without_submission(self):
		"""An email approval never reaches the insurer API, so it has no Submission ID."""
		hsr = make_request(requires_approval=1, approval_method="Email", approval_status="Approved")

		hsr.validate_approval_status()

	def test_approved_amount_guard_enforces_email_approved_amount(self):
		hsr = make_request(
			requires_approval=1,
			approval_method="Email",
			approved_amount=20000,
			appointment="APT-1",
		)

		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows",
			return_value=jubilee_rows(15000, 10000),
		):
			self.assertRaises(frappe.ValidationError, hsr.validate_approved_amount)

	def test_api_calls_blocked_after_email_approval(self):
		"""A later API send or poll must not overwrite the amount approved by email."""
		from hms_tz.jubilee.api.preauthorization import (
			get_service_request_preauth_status,
			send_service_request_preauthorization,
		)

		hsr = make_request(approval_method="Email", insurance_company="Jubilee")

		with (
			patch("frappe.get_doc", return_value=hsr),
			patch("hms_tz.jubilee.api.preauthorization.requests") as requests,
		):
			for api_call in (get_service_request_preauth_status, send_service_request_preauthorization):
				self.assertRaises(frappe.ValidationError, api_call, "HSR-TEST-1")

		self.assertFalse(requests.method_calls)

	def test_system_manager_has_approval_method_permlevel(self):
		self.assertTrue(make_request().has_permlevel_access_to("approval_method", permission_type="write"))

	def test_email_approval_records_fields_and_comment(self):
		hsr = make_email_approval_request()

		with email_approval_patches(hsr) as add_comment:
			hsr.record_email_approval("Approved", "143000", DOCUMENT_URL, "Approved by <b>Jubilee</b>")

		self.assertEqual(hsr.approval_method, "Email")
		self.assertEqual(hsr.approval_status, "Approved")
		self.assertEqual(hsr.approved_amount, 143000)
		self.assertEqual(hsr.supportive_document, DOCUMENT_URL)
		hsr.save.assert_called_once()

		comment = add_comment.call_args.kwargs["text"]
		self.assertIn(f"href='{DOCUMENT_URL}'", comment)
		self.assertIn("&lt;b&gt;Jubilee&lt;/b&gt;", comment)

	def test_email_approval_requires_permlevel_access(self):
		hsr = make_email_approval_request()

		with email_approval_patches(hsr, has_access=False):
			self.assertRaises(
				frappe.PermissionError, hsr.record_email_approval, "Approved", 1000, DOCUMENT_URL
			)

		hsr.save.assert_not_called()

	def test_email_approval_requires_document_attached_to_request(self):
		hsr = make_email_approval_request()

		with email_approval_patches(hsr, is_attached=False):
			self.assertRaises(
				frappe.ValidationError, hsr.record_email_approval, "Approved", 1000, "javascript:alert(1)"
			)

	def test_email_approval_rejects_filter_shaped_document(self):
		"""A filter list would match any File on the request in the attachment check."""
		hsr = make_email_approval_request()

		with email_approval_patches(hsr):
			self.assertRaises(
				frappe.ValidationError, hsr.record_email_approval, "Approved", 1000, ["like", "%"]
			)

	def test_email_approval_rejects_unknown_status(self):
		hsr = make_email_approval_request()

		with email_approval_patches(hsr):
			self.assertRaises(
				frappe.ValidationError, hsr.record_email_approval, "PENDING", 1000, DOCUMENT_URL
			)

	def test_email_approval_rejects_submitted_request(self):
		hsr = make_email_approval_request(docstatus=1)

		with email_approval_patches(hsr):
			self.assertRaises(
				frappe.ValidationError, hsr.record_email_approval, "Approved", 1000, DOCUMENT_URL
			)


DOCUMENT_URL = "/private/files/jubilee-approval.pdf"


def make_email_approval_request(**overrides):
	hsr = make_request(name="HSR-TEST-1", requires_approval=1, **overrides)
	hsr.save = MagicMock()

	return hsr


@contextmanager
def email_approval_patches(hsr, has_access=True, is_attached=True):
	"""Stub the permlevel and File lookups so record_email_approval runs without real records."""
	with (
		patch.object(hsr, "has_permlevel_access_to", return_value=has_access),
		patch.object(hsr, "add_comment") as add_comment,
		patch("frappe.db.exists", return_value=is_attached),
	):
		yield add_comment


CYCLE_SUBMISSION = "SUB-CYCLE-1"
PREAUTH = "hms_tz.jubilee.api.preauthorization"


def insert_cycle_request(appointment, item_code, amount, submission_id=""):
	"""Real draft Service Request holding one Jubilee row, as the pre-auth flow leaves it."""
	hsr = frappe.new_doc("Healthcare Service Request")
	hsr.update(
		{
			"appointment": appointment,
			"payment_type": "Insurance",
			"insurance_company": "Jubilee Insurance",
			"posting_datetime": "2026-10-23 09:00:00",
			"requires_approval": 1,
			"submission_id": submission_id,
		}
	)
	hsr.append(
		"payments",
		{
			"payment_type": "Insurance",
			"insurance_company": "Jubilee Insurance",
			"item_code": item_code,
			"qty": 1,
			"rate": amount,
			"amount": amount,
			"percent_covered": 100,
		},
	)
	hsr.flags.ignore_links = True
	hsr.flags.ignore_mandatory = True
	hsr.insert(ignore_permissions=True)

	return hsr


def approve_by_email(hsr, approved_amount):
	"""Attach a real File and record the email approval through the whitelisted method."""
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{hsr.name}-approval.txt",
			"content": "Jubilee approval email",
			"is_private": 1,
			"attached_to_doctype": hsr.doctype,
			"attached_to_name": hsr.name,
		}
	).insert(ignore_permissions=True)

	hsr.record_email_approval("Approved", approved_amount, file_doc.file_url, "Approved by email")


def send_with_mocked_jubilee(hsr_name):
	"""Run the real send writer with only the network and logging stubbed; return what was sent."""
	from hms_tz.jubilee.api.preauthorization import send_service_request_preauthorization

	response = MagicMock(status_code=200, text='{"Status": "OK", "Description": "Received"}')
	with (
		patch(f"{PREAUTH}.get_jubilee_setting"),
		patch(
			f"{PREAUTH}.get_preauth_endpoint",
			side_effect=lambda setting, submission_id: (
				"UpdatePreauthorization" if submission_id else "SendPreauthorization",
				"https://jubilee.test",
				{},
			),
		) as get_endpoint,
		patch(f"{PREAUTH}.get_preauth_entities", return_value={}) as get_entities,
		patch(f"{PREAUTH}.requests.post", return_value=response),
		patch(f"{PREAUTH}.log_preauth"),
		patch(f"{PREAUTH}.get_encounter_diseases", return_value=[]),
		patch("frappe.get_cached_doc", return_value=frappe._dict()),
		patch("frappe.get_cached_value", return_value=""),
	):
		send_service_request_preauthorization(hsr_name)

	return get_endpoint.call_args.args[1], get_entities.call_args.args[0]


class TestEmailApprovalInPreauthCycle(FrappeTestCase):
	"""Jubilee approves the whole bill of the appointment each time, by API or by email,
	so every approval is checked against the running total of all Service Requests."""

	def setUp(self):
		# Rows from one test must not count in another test's appointment total.
		self.appointment = f"TEST-APT-{frappe.generate_hash(length=8)}"

	def make_cycle(self):
		"""HSR1 opens the cycle by API, HSR2 updates it, HSR3 waits for approval."""
		hsr1 = insert_cycle_request(self.appointment, "REF-1", 10000, CYCLE_SUBMISSION)
		hsr2 = insert_cycle_request(self.appointment, "REF-2", 20000, CYCLE_SUBMISSION)
		hsr3 = insert_cycle_request(self.appointment, "REF-3", 30000, CYCLE_SUBMISSION)

		return hsr1, hsr2, hsr3

	def test_email_dialog_requested_amount_is_the_whole_bill(self):
		_hsr1, _hsr2, hsr3 = self.make_cycle()

		self.assertEqual(hsr3.get_jubilee_total_amount(), 60000)

	def test_email_approval_of_whole_bill_lets_request_submit(self):
		_hsr1, _hsr2, hsr3 = self.make_cycle()

		approve_by_email(hsr3, 60000)
		hsr3.reload()

		self.assertEqual(hsr3.approval_method, "Email")
		hsr3.validate_approval_status()
		hsr3.validate_approved_amount()

	def test_email_approval_below_whole_bill_blocks_submit(self):
		_hsr1, _hsr2, hsr3 = self.make_cycle()

		approve_by_email(hsr3, 30000)
		hsr3.reload()

		self.assertRaises(frappe.ValidationError, hsr3.validate_approved_amount)

	def test_api_request_after_email_updates_cycle_with_every_item(self):
		"""HSR4 updates HSR1's submission and resends HSR3's email-approved items too."""
		hsr1, _hsr2, hsr3 = self.make_cycle()
		approve_by_email(hsr3, 60000)
		hsr4 = insert_cycle_request(self.appointment, "REF-4", 40000)

		submission_id, source = send_with_mocked_jubilee(hsr4.name)

		self.assertEqual(submission_id, CYCLE_SUBMISSION)
		self.assertEqual(source.bill_no, get_bill_no(hsr1.name))
		self.assertEqual(
			{item.item_code for item in source.folio_items}, {"REF-1", "REF-2", "REF-3", "REF-4"}
		)
		self.assertEqual(source.total_amount, 100000)
		self.assertEqual(
			frappe.db.get_value("Healthcare Service Request", hsr4.name, "submission_id"),
			CYCLE_SUBMISSION,
		)

	def test_api_approval_after_email_must_cover_whole_bill(self):
		_hsr1, _hsr2, hsr3 = self.make_cycle()
		approve_by_email(hsr3, 60000)
		hsr4 = insert_cycle_request(self.appointment, "REF-4", 40000, CYCLE_SUBMISSION)
		hsr4.approval_status = "1"

		hsr4.approved_amount = 100000
		hsr4.validate_approval_status()
		hsr4.validate_approved_amount()

		hsr4.approved_amount = 70000
		self.assertRaises(frappe.ValidationError, hsr4.validate_approved_amount)

	def test_api_status_check_works_on_later_request_after_email(self):
		"""Only the email-approved request is locked; HSR4 still polls Jubilee."""
		from hms_tz.jubilee.api.preauthorization import get_service_request_preauth_status

		_hsr1, _hsr2, hsr3 = self.make_cycle()
		approve_by_email(hsr3, 60000)
		hsr4 = insert_cycle_request(self.appointment, "REF-4", 40000, CYCLE_SUBMISSION)

		response = MagicMock(
			status_code=200,
			text='{"Status": "OK", "Description": {"preathorizationStatus": "1", '
			'"amount": "100000", "approvedAmount": "100000", "details": []}}',
		)
		with (
			patch(f"{PREAUTH}.get_jubilee_setting"),
			patch(f"{PREAUTH}.requests.get", return_value=response),
			patch(f"{PREAUTH}.log_preauth"),
		):
			get_service_request_preauth_status(hsr4.name)
			self.assertRaises(frappe.ValidationError, get_service_request_preauth_status, hsr3.name)

		hsr4.reload()
		self.assertEqual(hsr4.approved_amount, 100000)
		hsr4.validate_approved_amount()

	def test_email_approval_without_send_lets_next_request_open_cycle(self):
		"""HSR1 never reached Jubilee, so HSR2 sends a new bill that still carries HSR1's items."""
		hsr1 = insert_cycle_request(self.appointment, "REF-1", 10000)
		approve_by_email(hsr1, 10000)
		hsr2 = insert_cycle_request(self.appointment, "REF-2", 20000)

		submission_id, source = send_with_mocked_jubilee(hsr2.name)

		self.assertIsNone(submission_id)
		self.assertEqual(source.bill_no, get_bill_no(hsr2.name))
		self.assertEqual({item.item_code for item in source.folio_items}, {"REF-1", "REF-2"})
