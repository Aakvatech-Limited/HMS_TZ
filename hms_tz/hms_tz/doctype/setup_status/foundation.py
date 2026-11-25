import frappe
from erpnext.accounts.utils import FiscalYearError, get_fiscal_year
from frappe import _
from frappe.utils import today

FOUNDATION_STEP = {
	"key": "foundation",
	"label": "Foundation",
	"method": "hms_tz.hms_tz.doctype.setup_status.foundation.check_foundation",
}

# Healthcare Insurance Company account field -> the account the foundation step creates for it,
# under the parent group of the named Company account.
INSURANCE_ACCOUNTS = {
	"billed_but_not_claimed_account": {
		"account_name": "Billed But Not Claimed",
		"account_type": "Receivable",
		"parent_of": "default_receivable_account",
	},
	"approved_claim_receivable_account": {
		"account_name": "Approved Claims Receivable",
		"account_type": "Receivable",
		"parent_of": "default_receivable_account",
	},
	"rejected_claims_account": {
		"account_name": "Rejected Claims",
		"account_type": "",
		"parent_of": "write_off_account",
	},
}


def check_foundation(setting, progress):
	"""Setup runner step: confirm what HMS TZ builds on and create the missing insurance accounts."""
	company = frappe.db.get_value("HMS TZ Setting", setting, "company")
	return Foundation(company, progress).check()


def get_insurance_accounts(company):
	"""The insurance account of each Healthcare Insurance Company account field, made by the foundation step."""
	accounts = {}
	for fieldname, account in INSURANCE_ACCOUNTS.items():
		name = frappe.db.get_value("Account", {"company": company, "account_name": account["account_name"]})
		if not name:
			frappe.throw(
				_("Run the Foundation step first: account {0} is missing.").format(account["account_name"])
			)
		accounts[fieldname] = name
	return accounts


class Foundation:
	"""Checks the company, fiscal year, chart of accounts, customer defaults and payment methods.

	It stops with a message on anything it cannot fix safely, and only creates the insurance accounts.
	"""

	def __init__(self, company, progress):
		self.company = company
		self.progress = progress

	def check(self):
		checks = [
			self.check_fiscal_year,
			self.check_chart_of_accounts,
			self.check_selling_defaults,
			self.check_payment_methods,
		]
		self.progress.set_total(len(checks) + len(INSURANCE_ACCOUNTS))
		for check in checks:
			check()
			self.progress.advance()
		for account in INSURANCE_ACCOUNTS.values():
			self.progress.advance(added=int(self.create_account(account)))
		return _("{0} checks passed, {1} insurance accounts").format(len(checks), len(INSURANCE_ACCOUNTS))

	def check_fiscal_year(self):
		try:
			get_fiscal_year(today(), company=self.company)
		except FiscalYearError:
			frappe.throw(
				_("Create a Fiscal Year that covers today for {0}, then try again.").format(self.company)
			)

	def check_chart_of_accounts(self):
		if not frappe.db.exists("Account", {"company": self.company, "is_group": 0}):
			frappe.throw(_("{0} has no chart of accounts. Set it up, then try again.").format(self.company))
		receivable, write_off = frappe.get_cached_value(
			"Company", self.company, ["default_receivable_account", "write_off_account"]
		)
		if not (receivable and write_off):
			frappe.throw(
				_("Set the Default Receivable Account and Write Off Account of {0}, then try again.").format(
					self.company
				)
			)

	def check_selling_defaults(self):
		for fieldname, doctype in (("customer_group", "Customer Group"), ("territory", "Territory")):
			value = frappe.db.get_single_value("Selling Settings", fieldname)
			if not value or frappe.db.get_value(doctype, value, "is_group"):
				frappe.throw(
					_("Set a default {0} that is not a group in Selling Settings, then try again.").format(
						_(doctype)
					)
				)

	def check_payment_methods(self):
		modes = frappe.get_all(
			"Mode of Payment",
			filters=[
				["enabled", "=", 1],
				["Mode of Payment Account", "company", "=", self.company],
				["Mode of Payment Account", "default_account", "is", "set"],
			],
			limit=1,
		)
		if not modes:
			frappe.throw(
				_("Give at least one Mode of Payment, such as Cash, a default account for {0}.").format(
					self.company
				)
			)

	def create_account(self, account):
		"""Create one insurance account when the company has none of that name; return whether it was created."""
		if frappe.db.exists("Account", {"company": self.company, "account_name": account["account_name"]}):
			return False
		sibling = frappe.get_cached_value("Company", self.company, account["parent_of"])
		frappe.get_doc(
			{
				"doctype": "Account",
				"company": self.company,
				"account_name": account["account_name"],
				"account_type": account["account_type"],
				"parent_account": frappe.db.get_value("Account", sibling, "parent_account"),
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		return True
