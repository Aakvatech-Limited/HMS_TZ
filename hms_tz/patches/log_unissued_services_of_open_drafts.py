from collections import defaultdict

import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull

from hms_tz.nhif.api.healthcare_utils import get_appointment
from hms_tz.nhif.nhif_api.approval import get_logged_unissued_services
from hms_tz.nhif.utils import (
	NOT_SERVICED_STATES,
	SERVICE_FIELDS,
	get_nhif_visit,
	get_services_of_drafts,
	queue_approval_status,
	set_approval_numbers_of_draft,
)


def execute():
	"""Fill Insurance Approval Log with the NHIF approvals given before it existed."""
	frappe.enqueue(
		"hms_tz.patches.log_unissued_services_of_open_drafts.log_unissued_services_of_open_drafts",
		queue="long",
		job_id="log_unissued_services_of_open_drafts",
		deduplicate=True,
		enqueue_after_commit=True,
	)


def log_unissued_services_of_open_drafts():
	"""Log the NHIF unissued approvals of the cards on open restricted drafts, then set their approval numbers.

	Run once from a patch: approvals given before Insurance Approval Log existed are not in the log.
	Drafts still without an approval number then ask NHIF for the approval status of their visit.
	"""

	drafts_of_card = defaultdict(list)
	for doctype, name in get_open_restricted_drafts():
		doc = frappe.get_doc(doctype, name)
		visit = get_nhif_visit(doc)
		if visit:
			drafts_of_card[visit.coverage_plan_card_number].append(doc)

	# one commit per card and per draft, so a failure does not undo the work before it
	logged_drafts = []
	for card_no, drafts in drafts_of_card.items():
		if run_and_commit(
			log_unissued_services_of_card, card_no, drafts, title=f"unissued services of card {card_no}"
		):
			for draft in drafts:
				run_and_commit(
					set_approval_numbers_of_draft, draft, title=f"approval number of {draft.name}", doc=draft
				)
			logged_drafts += drafts

	still_open = set(get_open_restricted_drafts())
	for draft in logged_drafts:
		if (draft.doctype, draft.name) in still_open:
			queue_approval_status(draft)


def log_unissued_services_of_card(card_no, drafts):
	doc = drafts[0]
	settings_doc = frappe.get_cached_doc("HMS TZ Setting", doc.company)
	if not settings_doc.enable_nhif_api:
		return False

	services = get_services_of_drafts(drafts, get_nhif_visit(doc).insurance_company)
	get_logged_unissued_services(settings_doc, card_no, get_appointment(doc), services, doc.doctype, doc.name)
	return True


def run_and_commit(method, *args, title, doc=None, **kwargs):
	"""Commit after `method` and return its result, or roll back, log the error and return False."""
	try:
		result = method(*args, **kwargs)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=f"Insurance Approval Log: {title} failed",
			reference_doctype=doc.doctype if doc else None,
			reference_name=doc.name if doc else None,
		)
		return False

	frappe.db.commit()  # nosemgrep
	return result


def get_open_restricted_drafts():
	"""Yield (doctype, name) of serviceable NHIF drafts with a restricted service that has no approval number."""

	for doctype in SERVICE_FIELDS:
		for name in frappe.get_all(
			doctype,
			filters={
				"docstatus": 0,
				"is_restricted": 1,
				"approval_number": ["is", "not set"],
				"insurance_company": ["like", "%NHIF%"],
				"workflow_state": ["not in", NOT_SERVICED_STATES],
			},
			pluck="name",
		):
			yield doctype, name

	dn = DocType("Delivery Note")
	dni = DocType("Delivery Note Item")
	for row in (
		frappe.qb.from_(dn)
		.inner_join(dni)
		.on(dni.parent == dn.name)
		.select(dn.name)
		.distinct()
		.where(
			(dn.docstatus == 0)
			& (IfNull(dn.workflow_state, "").notin(NOT_SERVICED_STATES))
			& (dn.customer.like("%NHIF%"))
			& (dni.is_restricted == 1)
			& (IfNull(dni.approval_number, "") == "")
		)
		.run(as_dict=True)
	):
		yield "Delivery Note", row.name
