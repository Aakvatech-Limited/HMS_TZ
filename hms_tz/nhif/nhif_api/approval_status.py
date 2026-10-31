import ast
import json
from collections import Counter, defaultdict

import frappe
from frappe.query_builder import DocType
from frappe.utils import cint, flt, get_datetime, get_fullname, getdate

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import get_childs_map
from hms_tz.nhif.nhif_api.pre_approval import get_service_item

DELIVERY_NOTE_ITEM = "Delivery Note Item"


def update_approval_status(doc, appointment, data, dni_id=None):
	"""Give each NHIF approval of the visit to the open restricted services it covers.

	NHIF returns every approval of the authorization number, so all open services
	of the appointment are matched, not only the one the user opened.
	"""
	# Lock the appointment row, not the unindexed service queries, so parallel updates of one visit wait
	insurance_company = frappe.db.get_value(
		"Patient Appointment", appointment, "insurance_company", for_update=True
	)
	restricted = get_restricted_documents(appointment)
	used_units = Counter(document.approval_number for document in restricted if document.approval_number)
	open_documents = [
		document for document in restricted if document.docstatus == 0 and not document.approval_number
	]
	documents = get_requested_documents(open_documents, doc.company, insurance_company)
	documents.sort(key=lambda document: (document.requested_at, document.creation))

	lines = sorted(data, key=lambda line: get_datetime(line.get("ApprovalDate") or "9999-12-31"))
	approved_lines = [line for line in lines if is_approved(line)]
	pending_lines = [line for line in lines if not is_approved(line)]

	approved = []
	for line in approved_lines:
		approved += give_approval(line, documents, used_units)

	for line in pending_lines:
		set_pending_status(line, documents)

	# Only the pharmacy acts on a short drug approval, so other departments do not see the warning
	if doc.doctype == "Delivery Note":
		for document in approved:
			if document.parent == doc.name and document.approved_qty < document.qty:
				frappe.msgprint(
					get_short_approval_message(
						f"{document.item_code} on {document.parent}", document.approved_qty, document.qty
					),
					indicator="orange",
				)

	show_approved_documents(approved)

	reference_no = frappe.db.get_value(
		DELIVERY_NOTE_ITEM if dni_id else doc.doctype, dni_id or doc.name, "approval_number"
	)
	return {"status": "success", "reference_no": reference_no}


def get_restricted_documents(appointment):
	"""Return the restricted services of the appointment that are not cancelled."""
	encounter_meta = frappe.get_meta("Patient Encounter")
	documents = []
	for child in get_childs_map():
		if child["lrpmt_doctype"] == DELIVERY_NOTE_ITEM:
			continue

		service = DocType(child["lrpmt_doctype"])
		rows = (
			frappe.qb.from_(service)
			.select(
				service.name,
				service.creation,
				service.docstatus,
				service.approval_number,
				service.hms_tz_ref_childname.as_("child_name"),
			)
			.where(
				(service.appointment == appointment) & (service.is_restricted == 1) & (service.docstatus != 2)
			)
			.run(as_dict=True)
		)
		child_doctype = encounter_meta.get_field(child["table"]).options
		documents += [
			frappe._dict(
				row,
				doctype=child["lrpmt_doctype"],
				child_doctype=child_doctype,
				template_doctype=child["doctype"],
				template_field=child["item"],
			)
			for row in rows
		]

	return documents + get_restricted_delivery_note_items(appointment)


def get_restricted_delivery_note_items(appointment):
	dn = DocType("Delivery Note")
	dni = DocType(DELIVERY_NOTE_ITEM)
	rows = (
		frappe.qb.from_(dni)
		.inner_join(dn)
		.on(dn.name == dni.parent)
		.select(
			dni.name,
			dni.creation,
			dn.docstatus,
			dni.approval_number,
			dni.parent,
			dni.item_code,
			dni.qty,
			dni.reference_doctype.as_("child_doctype"),
			dni.reference_name.as_("child_name"),
		)
		.where((dn.hms_tz_appointment_no == appointment) & (dn.docstatus != 2) & (dni.is_restricted == 1))
		.run(as_dict=True)
	)
	return [
		frappe._dict(
			row, doctype=DELIVERY_NOTE_ITEM, template_doctype="Medication", template_field="drug_code"
		)
		for row in rows
	]


def get_requested_documents(documents, company, insurance_company):
	"""Add the item code and pre-approval request to each service; drop services never pre-approved."""
	rows = get_prescription_rows(documents)
	requests = get_preapproval_requests({row.parent for row in rows.values()})

	requested = []
	for document in documents:
		row = rows.get((document.child_doctype, document.child_name))
		if not row:
			continue

		ref_code, _item = get_service_item(
			document.template_doctype, row.get(document.template_field), company, insurance_company
		)
		if row.preapproval_no:
			request = requests.get(row.preapproval_no)
		else:
			request = get_pending_request(requests, row, ref_code)

		if not request:
			continue

		document.update(
			ref_code=ref_code,
			preapproval_no=row.preapproval_no,
			requested_at=request.timestamp,
			requested_qty=request.quantities.get(ref_code),
		)
		requested.append(document)

	return requested


def get_pending_request(requests, row, ref_code):
	"""Return the last request NHIF did not reject for a row that lost its preapproval_no.

	Sending a row again while NHIF still holds it pending returns REJECTED and clears the row's
	preapproval_no, although the earlier request goes on to be approved.
	"""
	if row.preapproval_status != "REJECTED":
		return None

	pending = [
		request
		for request in requests.values()
		if request.encounter == row.parent and request.statuses.get(ref_code) not in (None, "REJECTED")
	]
	return max(pending, key=lambda request: request.timestamp, default=None)


def get_prescription_rows(documents):
	"""Return the prescription rows behind the services, keyed by (child doctype, row name)."""
	names = defaultdict(set)
	for document in documents:
		if document.child_doctype and document.child_name:
			names[(document.child_doctype, document.template_field)].add(document.child_name)

	rows = {}
	for (child_doctype, template_field), child_names in names.items():
		for row in frappe.db.get_all(
			child_doctype,
			filters={"name": ["in", list(child_names)]},
			fields=["name", "parent", "preapproval_no", "preapproval_status", template_field],
		):
			rows[(child_doctype, row.name)] = row

	return rows


def get_preapproval_requests(encounters):
	"""Return the encounter, send time, requested quantities and NHIF statuses of each pre-approval, keyed by requestNo.

	A submitted Medication Change Request copies its rows, with their preapproval_no, into the
	encounter, so the request log of a row can belong to the encounter or to one of its change requests.
	"""
	if not encounters:
		return {}

	encounter_of = {encounter: encounter for encounter in encounters}
	for change_request in frappe.db.get_all(
		"Medication Change Request",
		filters={"patient_encounter": ["in", list(encounters)]},
		fields=["name", "patient_encounter"],
	):
		encounter_of[change_request.name] = change_request.patient_encounter

	# Filter on the indexed ref_docname only: request_type and status_code have few distinct values,
	# and the log table holds millions of rows
	logs = frappe.db.get_all(
		"NHIF Response Log",
		filters={"ref_docname": ["in", list(encounter_of)]},
		fields=["ref_docname", "request_type", "status_code", "timestamp", "request_body", "response_data"],
		order_by="creation asc",
	)

	requests = {}
	for log in logs:
		if log.request_type != "RequestServices" or log.status_code != "200":
			continue

		# add_log stores the response as str(dict)
		response = ast.literal_eval(log.response_data)
		quantities = Counter()
		for service in json.loads(log.request_body).get("requestedServices") or []:
			quantities[service.get("itemCode")] += cint(service.get("quantityRequested"))

		requests[response.get("requestNo")] = frappe._dict(
			encounter=encounter_of[log.ref_docname],
			timestamp=get_datetime(log.timestamp),
			quantities=quantities,
			statuses={
				service.get("itemCode"): service.get("status") for service in response.get("services") or []
			},
		)

	return requests


def is_approved(line):
	return line.get("ApprovalStatus") == "Approved" and bool(line.get("ReferenceNo"))


def is_for_request(line, document, approved=True):
	"""NHIF lines carry no request number: match on item code, the request day and approval after sending."""
	if line.get("ItemCode") != document.ref_code or not line.get("ServiceDate"):
		return False

	if getdate(line.get("ServiceDate")) != getdate(document.requested_at):
		return False

	return not approved or get_datetime(line.get("ApprovalDate")) > document.requested_at


def give_approval(line, documents, used_units):
	"""Set the approval number on as many matching services as the approval has free units.

	Units held by services of any encounter count as used. A drug approval covers one item.
	"""
	candidates = [document for document in documents if is_for_request(line, document)]
	if not candidates:
		return []

	candidates.sort(key=lambda document: document.requested_qty != cint(line.get("QuantityRequested")))
	reference_no = line.get("ReferenceNo")
	if candidates[0].doctype == DELIVERY_NOTE_ITEM:
		free_units = 0 if used_units[reference_no] else 1
	else:
		free_units = max(cint(line.get("QuantityApproved")) - used_units[reference_no], 0)

	given = candidates[:free_units]
	used_units[reference_no] += len(given)

	for unit, document in enumerate(given, start=1):
		documents.remove(document)
		set_line_values(document, line, get_approval_values(document, line))
		add_approval_comment(document, line, unit, len(given))

	return given


def get_short_approval_message(item, approved_qty, qty):
	return (
		f"Approved quantity for <b>{item}</b> is <b>{approved_qty:g}</b> but the quantity is <b>{qty:g}</b>. "
		"Ask the practitioner to change the quantity through a Medication Change Request. "
		f"The practitioner may prescribe the other <b>{qty - approved_qty:g}</b> as a new drug prescription "
		"paid by cash or by another payment method."
	)


def set_pending_status(line, documents):
	for document in documents:
		if is_for_request(line, document, approved=False):
			set_line_values(document, line)


def get_approval_values(document, line):
	values = {"approval_number": line.get("ReferenceNo"), "approval_date": getdate(line.get("ApprovalDate"))}
	if document.doctype == DELIVERY_NOTE_ITEM:
		values["approved_qty"] = flt(line.get("QuantityApproved"))
	return values


def set_line_values(document, line, approval_values=None):
	values = {
		"approval_status": line.get("ApprovalStatus"),
		"service_authorization_id": line.get("ServiceAuthorizationID"),
		"authorized_item_id": line.get("AuthorizedItemID"),
		**(approval_values or {}),
	}
	frappe.db.set_value(document.doctype, document.name, values)
	document.update(values)


def add_approval_comment(document, line, unit, units_given):
	text = (
		f"Approval status: <b>{line.get('ApprovalStatus')}</b><br>ReferenceNo: <b>{line.get('ReferenceNo')}</b>"
		f"<br>Unit: <b>{unit} of {units_given}</b> given in this update"
		f"<br>QuantityRequested: <b>{line.get('QuantityRequested')}</b>"
		f"<br>QuantityApproved: <b>{line.get('QuantityApproved')}</b>"
		f"<br>Remarks: <b>{line.get('Remarks') or line.get('SummaryRemarks')}</b>"
	)
	reference = (document.doctype, document.name)
	if document.doctype == DELIVERY_NOTE_ITEM:
		text = f"Item: <b>{document.item_code}</b><br>{text}"
		reference = ("Delivery Note", document.parent)

	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": reference[0],
			"reference_name": reference[1],
			"comment_email": frappe.session.user,
			"comment_by": get_fullname(),
			"content": text,
		}
	).insert(ignore_permissions=True)


def show_approved_documents(approved):
	if not approved:
		return

	rows = "".join(
		f"<tr><td>{document.doctype}</td><td>{document.parent or document.name}</td>"
		f"<td>{document.approval_number}</td></tr>"
		for document in approved
	)
	frappe.msgprint(
		"<table class='table table-condensed table-bordered'>"
		f"<tr><th>Document Type</th><th>Document</th><th>Approval Number</th></tr>{rows}</table>",
		title="NHIF Approval Numbers Set",
		indicator="green",
	)
