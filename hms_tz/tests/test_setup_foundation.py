from unittest.mock import patch

import frappe
from erpnext.accounts.utils import FiscalYearError
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.setup_status import foundation
from hms_tz.hms_tz.doctype.setup_status.foundation import INSURANCE_ACCOUNTS, Foundation
from hms_tz.hms_tz.doctype.setup_status.setup_runner import SETUP_RUNNER_STEPS
from hms_tz.tests.test_standard_records import FakeProgress

COMPANY = "_Test Company"
ACCOUNT_NAMES = [account["account_name"] for account in INSURANCE_ACCOUNTS.values()]


def get_leaf(doctype):
	return frappe.db.get_value(doctype, {"is_group": 0})


class TestSetupFoundation(FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value(
			"Selling Settings",
			{"customer_group": get_leaf("Customer Group"), "territory": get_leaf("Territory")},
		)
		self.add_cash_account()
		self.patch_fiscal_year = patch.object(foundation, "get_fiscal_year")
		self.get_fiscal_year = self.patch_fiscal_year.start()
		self.addCleanup(self.patch_fiscal_year.stop)

	def add_cash_account(self):
		cash = frappe.get_doc("Mode of Payment", "Cash")
		if not [row for row in cash.accounts if row.company == COMPANY and row.default_account]:
			account = frappe.db.get_value(
				"Account", {"company": COMPANY, "account_type": "Cash", "is_group": 0}
			)
			cash.append("accounts", {"company": COMPANY, "default_account": account})
			cash.save()

	def delete_insurance_accounts(self):
		frappe.db.delete("Account", {"company": COMPANY, "account_name": ["in", ACCOUNT_NAMES]})

	def check(self):
		progress = FakeProgress()
		result = Foundation(COMPANY, progress).check()
		return result, progress

	def test_foundation_is_the_first_setup_step(self):
		self.assertEqual(SETUP_RUNNER_STEPS[0]["key"], "foundation")
		self.assertFalse(SETUP_RUNNER_STEPS[0]["needs_rooms"])

	def test_missing_insurance_accounts_are_created_under_the_right_groups(self):
		self.delete_insurance_accounts()
		result, progress = self.check()
		self.assertEqual((progress.added, progress.done, progress.total), (3, 7, 7))
		self.assertIn("4 checks passed", result)
		receivable_group = frappe.db.get_value(
			"Account",
			frappe.get_cached_value("Company", COMPANY, "default_receivable_account"),
			"parent_account",
		)
		billed = frappe.db.get_value(
			"Account",
			{"company": COMPANY, "account_name": "Billed But Not Claimed"},
			["account_type", "parent_account", "root_type"],
			as_dict=True,
		)
		self.assertEqual(
			billed, {"account_type": "Receivable", "parent_account": receivable_group, "root_type": "Asset"}
		)
		rejected = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": "Rejected Claims"}, "root_type"
		)
		self.assertEqual(rejected, "Expense")

	def test_a_complete_foundation_adds_nothing(self):
		self.check()
		_result, progress = self.check()
		self.assertEqual((progress.added, progress.done), (0, 7))

	def test_missing_fiscal_year_stops_with_a_clear_message(self):
		self.get_fiscal_year.side_effect = FiscalYearError
		self.delete_insurance_accounts()
		with self.assertRaisesRegex(frappe.ValidationError, "Fiscal Year"):
			self.check()
		self.assertFalse(frappe.db.exists("Account", {"company": COMPANY, "account_name": "Rejected Claims"}))

	def test_missing_write_off_account_stops(self):
		with patch.object(frappe, "get_cached_value", return_value=("Debtors - _TC", None)):
			with self.assertRaisesRegex(frappe.ValidationError, "Write Off Account"):
				self.check()

	def test_group_customer_group_stops(self):
		root = frappe.db.get_value("Customer Group", {"is_group": 1})
		frappe.db.set_single_value("Selling Settings", "customer_group", root)
		with self.assertRaisesRegex(frappe.ValidationError, "Customer Group"):
			self.check()

	def test_missing_payment_method_stops(self):
		frappe.db.delete("Mode of Payment Account", {"company": COMPANY})
		with self.assertRaisesRegex(frappe.ValidationError, "Mode of Payment"):
			self.check()
