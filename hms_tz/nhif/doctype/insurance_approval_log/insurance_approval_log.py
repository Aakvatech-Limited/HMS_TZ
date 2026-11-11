# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, now_datetime

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import get_item_refcode
from hms_tz.nhif.api.healthcare_utils import get_appointment

INSURANCE_APPROVAL_LOG = "Insurance Approval Log"
# The insurer does not return an expiry date
APPROVAL_VALIDITY_DAYS = 30
USAGE_FIELDS = ("ref_doctype", "ref_docname", "appointment", "qty", "service_reference_no", "issued_on")


class InsuranceApprovalLog(Document):
	"""One approval line from the insurer; its units are used across visits until issued or expired."""

	def validate(self):
		self.qty_issued = sum(flt(row.qty) for row in self.usages)
		self.qty_remaining = flt(self.qty_approved) - self.qty_issued
		# NHIF does not return an expiry date, so it is not set until it does
		# if self.date_requested:
		# 	self.expiry_date = add_days(self.date_requested, APPROVAL_VALIDITY_DAYS)

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
				"appointment": get_appointment(document),
				"qty": qty,
				"service_reference_no": service_reference_no,
				"issued_on": now_datetime(),
			},
		)
		self.save(ignore_permissions=True)

	def merge(self, name):
		"""Take over the usages of the log `name` and delete it."""
		for usage in frappe.get_doc(INSURANCE_APPROVAL_LOG, name).usages:
			self.append("usages", {field: usage.get(field) for field in USAGE_FIELDS})
		frappe.delete_doc(INSURANCE_APPROVAL_LOG, name, ignore_permissions=True)


def get_visit_values(appointment):
	return frappe.db.get_value(
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


def upsert_approval_lines(lines, appointment, services):
	"""Keep one log per approval line, so a pending line becomes approved in place.

	`services` maps the insurer item code to its (service type, service name).
	"""
	visit = get_visit_values(appointment)
	for line in lines:
		if line.get("AuthorizedItemID"):
			get_approval_log(line, visit, services).save(ignore_permissions=True)


def log_unissued_lines(lines, approvals, appointment, services):
	"""Log the unissued approvals of a card under the AuthorizedItemID that GetApprovals gives their reference no.

	`approvals` is the GetApprovals response of the card. A line it does not list is not logged.
	NHIF counts units issued before the log existed; they are kept as one usage row without a document.
	"""
	visit = get_visit_values(appointment)
	approval_of_reference = {
		approval.get("ApprovalReferenceNo"): approval
		for approval in approvals
		if approval.get("ApprovalReferenceNo") and approval.get("AuthorizedItemID")
	}
	missing = []
	for line in lines:
		approval = approval_of_reference.get(line.get("ApprovalReferenceNo"))
		if not approval:
			missing.append(line.get("ApprovalReferenceNo"))
			continue

		log = get_approval_log({**approval, "ReferenceNo": approval["ApprovalReferenceNo"]}, visit, services)
		if not log.usages and flt(line.get("QuantityIssued")):
			log.append("usages", {"qty": flt(line.get("QuantityIssued"))})
		log.save(ignore_permissions=True)

	if missing:
		frappe.log_error(
			title=_("NHIF unissued approvals missing from GetApprovals"),
			message=_("Reference nos not logged: {0}").format(", ".join(map(str, missing))),
		)


def get_approval_log(line, visit, services):
	"""Return the log of an approval line updated from it, found by AuthorizedItemID or new.

	A log of the same reference no without an AuthorizedItemID is from before both writers shared it;
	it is taken over, or merged in when the line already has a log.
	"""
	name = frappe.db.get_value(INSURANCE_APPROVAL_LOG, {"authorized_item_id": line["AuthorizedItemID"]})
	unclaimed = line.get("ReferenceNo") and frappe.db.get_value(
		INSURANCE_APPROVAL_LOG,
		{
			"reference_no": line["ReferenceNo"],
			"item_code": line.get("ItemCode"),
			"authorized_item_id": ["is", "not set"],
		},
	)
	if name or unclaimed:
		log = frappe.get_doc(INSURANCE_APPROVAL_LOG, name or unclaimed)
	else:
		log = frappe.new_doc(INSURANCE_APPROVAL_LOG)
		log.update(visit)

	if name and unclaimed:
		log.merge(unclaimed)

	log.authorized_item_id = line["AuthorizedItemID"]
	log.update_from_line(line)
	if service := services.get(line.get("ItemCode")):
		log.service_type, log.service_name = service

	return log


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
			# NHIF does not return an expiry date, so the 30 days are not enforced until it does
			# "expiry_date": [">=", today()],
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
	A service the log cannot cover asks NHIF for the approval status in the background when it is created.
	"""
	# nhif.utils imports this module
	from hms_tz.nhif.utils import (
		get_nhif_visit,
		get_services_needing_approval,
		needs_approval_number,
		queue_approval_status,
	)

	rows = doc.items if doc.doctype == "Delivery Note" else [doc]
	if doc.docstatus != 0 or not any(needs_approval_number(row) for row in rows):
		return

	visit = get_nhif_visit(doc)
	if not visit:
		return

	is_covered = [
		set_approval_number(doc, visit, target, service_type, service_name)
		for target, service_type, service_name in get_services_needing_approval(doc)
	]
	# Therapy Session becomes restricted in after_insert
	if not all(is_covered) and (doc.is_new() or doc.has_value_changed("is_restricted")):
		queue_approval_status(doc)


def get_open_approval_of_service(doc, visit, service_type, service_name):
	if not service_name:
		return None

	item_code = get_item_refcode(service_type, service_name, doc.company, visit.insurance_company)
	return get_open_approval(doc.patient, visit.coverage_plan_card_number, item_code)


def get_approval_values(approval, target):
	"""Return the approval fields to set on `target` from an open log."""
	values = {
		"approval_number": approval.reference_no,
		"approval_status": approval.approval_status,
		"approval_date": getdate(approval.date_approved) if approval.date_approved else None,
		"service_authorization_id": approval.service_authorization_id,
		"authorized_item_id": approval.authorized_item_id,
	}
	if target.doctype == "Delivery Note Item":
		values["approved_qty"] = approval.qty_remaining

	return values


def set_approval_number(doc, visit, target, service_type, service_name):
	"""Set the approval number of an open log on `target`; return False when the log has none."""
	approval = get_open_approval_of_service(doc, visit, service_type, service_name)
	if not approval:
		return False

	target.update(get_approval_values(approval, target))
	frappe.msgprint(
		_("Approval No {0} for {1} is set from Insurance Approval Log, {2} remaining").format(
			frappe.bold(approval.reference_no), service_name, approval.qty_remaining
		),
		alert=True,
	)
	return True


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
