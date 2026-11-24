# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Setup DocType -> (DocType holding its company link, company field). None counts any record.
SETUP_STEPS = {
	"HMS TZ Setting": ("HMS TZ Setting", "company"),
	"Healthcare Insurance Company": ("Healthcare Insurance Company", "company"),
	"Healthcare Insurance Coverage Plan": ("Healthcare Insurance Coverage Plan", "company"),
	"Healthcare Practitioner": ("Healthcare Practitioner", "hms_tz_company"),
	"Healthcare Service Unit": ("Healthcare Service Unit", "company"),
	"Healthcare Service Unit Type": None,
	"Medical Department": None,
	"Healthcare Service Insurance Coverage": ("Healthcare Service Insurance Coverage", "company"),
	"Price List": None,
	"Item Price": None,
	"Mode of Payment": ("Mode of Payment Account", "company"),
	"Appointment Type": None,
	"Healthcare Card Verifier": None,
	"Lab Test Template": ("Healthcare Company Option", "company"),
	"Radiology Examination Template": ("Healthcare Company Option", "company"),
	"Clinical Procedure Template": ("Healthcare Company Option", "company"),
	"Medication": ("Healthcare Company Option", "company"),
	"Therapy Type": ("Healthcare Company Option", "company"),
	"Accounting Dimension": None,
}

# Each company gets a root group automatically, so only rooms count.
STEP_FILTERS = {"Healthcare Service Unit": [["is_group", "=", 0]]}


class SetupStatus(Document):
	"""Setup steps completed for one HMS TZ Setting."""

	def before_insert(self):
		self.add_missing_steps()

	def add_missing_steps(self):
		"""Add an unticked row for each setup DocType not listed yet."""
		listed = {row.document_type for row in self.steps}
		for document_type in SETUP_STEPS:
			if document_type not in listed:
				self.append("steps", {"document_type": document_type})

	def get_step(self, document_type):
		for row in self.steps:
			if row.document_type == document_type:
				return row
		frappe.throw(_("{0} is not a setup step").format(document_type))

	def set_settings_complete(self, is_complete):
		if self.settings_complete != int(is_complete):
			self.settings_complete = int(is_complete)
			self.save(ignore_permissions=True)

	def validate_settings_complete(self):
		"""Gate for every setup stage after the settings page."""
		if not self.settings_complete:
			frappe.throw(
				_("Complete the settings page of {0} before the next setup stage.").format(
					self.hms_tz_setting
				),
				title=_("Settings Page Incomplete"),
			)

	def mark_steps_with_records(self):
		"""Tick each open step whose DocType already has a record for the setting's company."""
		company = frappe.db.get_value("HMS TZ Setting", self.hms_tz_setting, "company")
		open_steps = [row for row in self.steps if not row.completed]
		for row in open_steps:
			row.completed = int(has_company_records(row.document_type, company))
		if any(row.completed for row in open_steps):
			self.save(ignore_permissions=True)


def has_company_records(document_type, company):
	company_link = SETUP_STEPS[document_type]
	filters = [[*company_link, "=", company]] if company_link else []
	filters += STEP_FILTERS.get(document_type, [])
	return bool(frappe.get_all(document_type, filters=filters, limit=1, pluck="name"))


def get_setup_status(hms_tz_setting):
	"""The Setup Status of a setting, created with every step when it is missing."""
	if frappe.db.exists("Setup Status", hms_tz_setting):
		return frappe.get_doc("Setup Status", hms_tz_setting)
	return frappe.get_doc({"doctype": "Setup Status", "hms_tz_setting": hms_tz_setting}).insert(
		ignore_permissions=True
	)


def mark_company_status(company, fieldname):
	"""Tick one check of the company's Setup Status, such as nhif_prices_processed."""
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		return
	status = get_setup_status(setting)
	if not status.get(fieldname):
		status.set(fieldname, 1)
		status.save(ignore_permissions=True)


def complete_setup_step(hms_tz_setting, document_type):
	"""Tick one setup step of a setting."""
	status = get_setup_status(hms_tz_setting)
	step = status.get_step(document_type)
	if not step.completed:
		step.completed = 1
		status.save(ignore_permissions=True)
