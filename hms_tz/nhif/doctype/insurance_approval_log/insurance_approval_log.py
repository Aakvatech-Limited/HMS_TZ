# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, get_datetime, getdate, now_datetime, today

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import get_item_refcode

INSURANCE_APPROVAL_LOG = "Insurance Approval Log"
# The insurer does not return an expiry date
APPROVAL_VALIDITY_DAYS = 30
SERVICE_FIELDS = {
	"Lab Test": ("Lab Test Template", "template"),
	"Radiology Examination": ("Radiology Examination Template", "radiology_examination_template"),
	"Clinical Procedure": ("Clinical Procedure Template", "procedure_template"),
	"Therapy Session": ("Therapy Type", "therapy_type"),
}


class InsuranceApprovalLog(Document):
	"""One approval line from the insurer; its units are used across visits until issued or expired."""

	def validate(self):
		self.qty_issued = sum(flt(row.qty) for row in self.usages)
		self.qty_remaining = flt(self.qty_approved) - self.qty_issued
		if self.date_requested:
			self.expiry_date = add_days(self.date_requested, APPROVAL_VALIDITY_DAYS)

	def update_from_line(self, line):
		self.update(
			{
				"card_no": line.get("CardNo"),
				"reference_no": line.get("ReferenceNo"),
				"approval_status": line.get("ApprovalStatus"),
				"service_authorization_id": line.get("ServiceAuthorizationID"),
				"approved_by": line.get("ApprovedBy"),
				"prescribed_by": line.get("PrescribedBy"),
				"remarks": line.get("Remarks") or line.get("SummaryRemarks"),
				"item_code": line.get("ItemCode"),
				"date_requested": getdate(line.get("ServiceDate")) if line.get("ServiceDate") else None,
				"date_approved": get_datetime(line.get("ApprovalDate")) if line.get("ApprovalDate") else None,
				"qty_requested": flt(line.get("QuantityRequested")),
				"qty_approved": flt(line.get("QuantityApproved")),
			}
		)

	def add_usage(self, document, qty, service_reference_no):
		self.append(
			"usages",
			{
				"ref_doctype": document.doctype,
				"ref_docname": document.name,
				"appointment": document.get("appointment") or document.get("hms_tz_appointment_no"),
				"qty": qty,
				"service_reference_no": service_reference_no,
				"issued_on": now_datetime(),
			},
		)
		self.save(ignore_permissions=True)


def upsert_approval_lines(lines, appointment, services):
	"""Keep one log per approval line, so a pending line becomes approved in place.

	`services` maps the insurer item code to its (service type, service name).
	"""
	visit = frappe.db.get_value(
		"Patient Appointment",
		appointment,
		[
			"patient",
			"insurance_company",
			"insurance_subscription",
			"coverage_plan_name as coverage_plan",
			"company",
		],
		as_dict=True,
	)
	for line in lines:
		authorized_item_id = line.get("AuthorizedItemID")
		if not authorized_item_id:
			continue

		name = frappe.db.get_value(INSURANCE_APPROVAL_LOG, {"authorized_item_id": authorized_item_id})
		if name:
			log = frappe.get_doc(INSURANCE_APPROVAL_LOG, name)
		else:
			log = frappe.new_doc(INSURANCE_APPROVAL_LOG)
			log.update({"authorized_item_id": authorized_item_id, **visit})

		log.update_from_line(line)
		service = services.get(line.get("ItemCode"))
		if service:
			log.service_type, log.service_name = service

		log.save(ignore_permissions=True)


def get_open_approval(patient, card_no, item_code):
	"""Return the oldest approval of the item that has units left and has not expired."""
	return frappe.db.get_value(
		INSURANCE_APPROVAL_LOG,
		{
			"patient": patient,
			"card_no": card_no,
			"item_code": item_code,
			"approval_status": "Approved",
			"reference_no": ["is", "set"],
			"expiry_date": [">=", today()],
			"qty_remaining": [">", 0],
		},
		[
			"reference_no",
			"approval_status",
			"date_approved",
			"service_authorization_id",
			"authorized_item_id",
			"qty_remaining",
		],
		order_by="date_approved asc",
		as_dict=True,
	)


def set_approval_number_from_log(doc, method=None):
	"""Give a restricted draft NHIF service the approval number of an earlier visit that has units left.

	A Delivery Note item gets the remaining qty as approved qty, so a short approval is stopped by
	`validate_approved_qty` like a short approval from Get Approval Status.
	"""
	if doc.docstatus != 0:
		return

	if doc.doctype == "Delivery Note":
		items = [item for item in doc.items if needs_approval_number(item) and item.reference_name]
		visit = items and get_nhif_visit(doc)
		if not visit:
			return

		for item in items:
			drug_code = frappe.db.get_value(item.reference_doctype, item.reference_name, "drug_code")
			set_approval_number(doc, visit, item, "Medication", drug_code)
		return

	if needs_approval_number(doc):
		service_type, service_field = SERVICE_FIELDS[doc.doctype]
		visit = get_nhif_visit(doc)
		if visit:
			set_approval_number(doc, visit, doc, service_type, doc.get(service_field))


def needs_approval_number(target):
	return target.is_restricted and not target.approval_number


def get_nhif_visit(doc):
	"""Return the card no and insurance company of an NHIF visit; other insurers have no approval API yet."""
	appointment = doc.get("appointment") or doc.get("hms_tz_appointment_no")
	if not appointment:
		return None

	visit = frappe.get_cached_value(
		"Patient Appointment", appointment, ["coverage_plan_card_number", "insurance_company"], as_dict=True
	)
	if not visit or "NHIF" not in (visit.insurance_company or "") or not visit.coverage_plan_card_number:
		return None

	return visit


def set_approval_number(doc, visit, target, service_type, service_name):
	if not service_name:
		return

	item_code = get_item_refcode(service_type, service_name, doc.company, visit.insurance_company)
	approval = get_open_approval(doc.patient, visit.coverage_plan_card_number, item_code)
	if not approval:
		return

	target.update(
		{
			"approval_number": approval.reference_no,
			"approval_status": approval.approval_status,
			"approval_date": getdate(approval.date_approved) if approval.date_approved else None,
			"service_authorization_id": approval.service_authorization_id,
			"authorized_item_id": approval.authorized_item_id,
		}
	)
	if target.doctype == "Delivery Note Item":
		target.approved_qty = approval.qty_remaining

	frappe.msgprint(
		_("Approval No {0} for {1} is set from Insurance Approval Log, {2} remaining").format(
			frappe.bold(approval.reference_no), service_name, approval.qty_remaining
		),
		alert=True,
	)


def add_approval_usage(document, reference_no, qty, service_reference_no):
	"""Count an issued service against its approval; approvals not in the log are skipped."""
	if not reference_no or not document.patient:
		return

	name = frappe.db.get_value(
		INSURANCE_APPROVAL_LOG,
		{"reference_no": reference_no, "patient": document.patient},
		"name",
		for_update=True,
	)
	if name:
		frappe.get_doc(INSURANCE_APPROVAL_LOG, name).add_usage(document, qty, service_reference_no)
