# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

from frappe.model.document import Document

SETUP_DOCTYPES = (
	"HMS TZ Setting",
	"Healthcare Insurance Company",
	"Healthcare Insurance Coverage Plan",
	"Healthcare Practitioner",
	"Healthcare Service Unit",
	"Healthcare Service Unit Type",
	"Medical Department",
	"Healthcare Service Insurance Coverage",
	"Price List",
	"Item Price",
	"Mode of Payment",
	"Appointment Type",
	"Healthcare Card Verifier",
	"Lab Test Template",
	"Radiology Examination Template",
	"Clinical Procedure Template",
	"Medication",
	"Therapy Type",
	"Accounting Dimension",
)


class SetupStatus(Document):
	"""Setup steps completed for one HMS TZ Setting."""

	def before_insert(self):
		self.add_missing_steps()

	def add_missing_steps(self):
		"""Add an unticked row for each setup DocType not listed yet."""
		listed = {row.document_type for row in self.steps}
		missing = [document_type for document_type in SETUP_DOCTYPES if document_type not in listed]
		for document_type in missing:
			self.append("steps", {"document_type": document_type})
