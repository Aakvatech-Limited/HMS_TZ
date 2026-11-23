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


def add_missing_steps(doc, method=None):
	"""Add an unticked row for each setup DocType the status does not list yet."""
	listed = {row.document_type for row in doc.steps}
	for document_type in SETUP_DOCTYPES:
		if document_type not in listed:
			doc.append("steps", {"document_type": document_type})
