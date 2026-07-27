# Copyright (c) 2025, Aakvatech and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
    set_approval_state,
)


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
        hsr = make_request(
            requires_approval=1, submission_id=""
        )

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
