# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import get_fullname, nowdate

from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import (
	create_revenue_entry,
	update_revenue_entry,
)
from hms_tz.nhif.api.healthcare_utils import create_delivery_note_from_LRPT
from hms_tz.nhif.api.lab_test import check_cash_payments_from_encounter
from hms_tz.nhif.utils import validate_issued_services, validate_point_of_care


def after_insert(doc, method):
	create_revenue_entry(doc)


def onload(doc, method):
	check_cash_payments_from_encounter(
		doc=doc,
		ref_doctype="ref_doctype",
		ref_docname_field="ref_docname",
		prescription_field="radiology_procedure_prescription",
		item_name_field="radiology_procedure_name",
		item_descriptor="Radiology Examinations",
	)


def before_submit(doc, method):
	if doc.is_restricted and not doc.approval_number:
		frappe.throw(
			_(
				f"Approval number is required for <b>{doc.radiology_examination_template}</b>. Please set the Approval Number."
			)
		)

	validate_point_of_care(doc, "validate_poc_at_radiology")
	validate_issued_services(doc.doctype, doc.name, is_restricted=doc.is_restricted, company=doc.company)

	doc.hms_tz_submitted_by = get_fullname(frappe.session.user)
	doc.hms_tz_user_id = frappe.session.user
	doc.hms_tz_submitted_date = nowdate()


def on_submit(doc, method):
	update_radiology_procedure_prescription(doc)
	update_revenue_entry(
		"Radiology Examination",
		doc.name,
		"Radiology Procedure Prescription",
		doc.hms_tz_ref_childname,
		lrpmt_status="Submitted",
	)


def on_cancel(doc, method):
	doc.flags.ignore_links = True

	if doc.docstatus == 2:
		frappe.db.set_value(
			"Radiology Procedure Prescription",
			doc.hms_tz_ref_childname,
			"radiology_examination",
			"",
		)

		new_radiology_doc = frappe.copy_doc(doc)
		new_radiology_doc.workflow_state = None
		new_radiology_doc.amended_from = doc.name
		new_radiology_doc.save(ignore_permissions=True)

		url = frappe.utils.get_url_to_form(new_radiology_doc.doctype, new_radiology_doc.name)
		frappe.msgprint(
			f"Radiology Examination: <strong>{doc.name}</strong> is cancelled:<br>\
            New Radiology Examination: <a href='{url}'><strong>{new_radiology_doc.name}</strong></a> is successful created"
		)


def create_delivery_note(doc):
	if doc.ref_doctype and doc.ref_docname and doc.ref_doctype == "Patient Encounter":
		patient_encounter_doc = frappe.get_cached_doc(doc.ref_doctype, doc.ref_docname)
		create_delivery_note_from_LRPT(doc, patient_encounter_doc)


def update_radiology_procedure_prescription(doc):
	if doc.ref_doctype == "Patient Encounter":
		hsrp = DocType("Healthcare Service Request Payment")
		(
			frappe.qb.update(hsrp)
			.set(hsrp.lrpmt_status, "Submitted")
			.where(hsrp.ref_docname == doc.hms_tz_ref_childname)
		).run()
