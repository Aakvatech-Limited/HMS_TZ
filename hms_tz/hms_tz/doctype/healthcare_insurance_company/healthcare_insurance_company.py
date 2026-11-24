# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.model.document import Document


class HealthcareInsuranceCompany(Document):
	def autoname(self):
		"""Name a new insurer "<name> - <company abbr>", like the standard insurers; inserts with a set name keep it."""
		if not self.company:
			frappe.throw(_("Set the Company of {0} before saving it.").format(self.insurance_company_name))
		suffix = f" - {frappe.get_cached_value('Company', self.company, 'abbr')}"
		name = self.insurance_company_name
		self.name = name if name.endswith(suffix) else f"{name}{suffix}"
		if frappe.db.exists("Healthcare Insurance Company", self.name):
			frappe.throw(
				_("{0} already has an insurance company named {1}.").format(self.company, self.name),
				frappe.DuplicateEntryError,
			)

	def after_insert(self):
		create_customer(self)
		self.reload()

	def onload(self):
		load_address_and_contact(self)


def create_customer(doc):
	customer_group = frappe.db.exists(
		"Customer Group",
		{"customer_group_name": "Healthcare Insurance Company"},
	)
	if not customer_group:
		customer_group = (
			frappe.get_doc(
				{
					"customer_group_name": "Healthcare Insurance Company",
					"parent_customer_group": "All Customer Groups",
					"doctype": "Customer Group",
				}
			)
			.insert()
			.name
		)
	territory = frappe.get_cached_value("Selling Settings", None, "territory")
	if not (territory):
		territory = "Rest Of The World"
		frappe.msgprint(_("Please set default  territory in Selling Settings"), alert=True)
	customer = frappe.new_doc("Customer")
	customer.customer_name = doc.insurance_company_name
	customer.customer_group = customer_group
	customer.territory = territory
	customer.customer_type = "Company"
	if doc.approved_claim_receivable_account:
		accounts = []
		accounts.append(
			{
				"account": doc.approved_claim_receivable_account,
				"company": doc.company,
			}
		)
		customer.set("accounts", accounts)
	customer.save(ignore_permissions=True)
	frappe.db.set_value("Healthcare Insurance Company", doc.name, "customer", customer.name)
	frappe.msgprint(_(f"Customer {customer.name} is created."), alert=True)
