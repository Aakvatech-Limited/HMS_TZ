# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import dateutil
import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.query_builder import DocType
from frappe.utils import flt, get_fullname, getdate

from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import (
	create_revenue_entry,
	update_revenue_entry,
)
from hms_tz.nhif.api.healthcare_utils import create_delivery_note_from_LRPT
from hms_tz.nhif.utils import validate_issued_services, validate_point_of_care


def validate(doc, method):
	set_normals(doc)


def onload(doc, method):
	check_cash_payments_from_encounter(
		doc=doc,
		ref_doctype="ref_doctype",
		ref_docname_field="ref_docname",
		prescription_field="lab_test_prescription",
		item_name_field="lab_test_name",
		item_descriptor="Lab Tests",
	)


def after_insert(doc, method):
	create_sample_collection(doc)
	create_revenue_entry(doc)


def before_submit(doc, method):
	if doc.is_restricted and not doc.approval_number:
		frappe.throw(
			_(
				f"Approval number is required for <b>{doc.radiology_examination_template}</b>. Please set the Approval Number."
			)
		)

	validate_point_of_care(doc, "validate_poc_at_laboratory")
	validate_issued_services(doc.doctype, doc.name, is_restricted=doc.is_restricted, company=doc.company)

	doc.hms_tz_submitted_by = get_fullname(frappe.session.user)
	doc.hms_tz_user_id = frappe.session.user


def on_submit(doc, method):
	update_lab_prescription(doc)
	update_revenue_entry(
		"Lab Test",
		doc.name,
		"Lab Prescription",
		doc.hms_tz_ref_childname,
		lrpmt_status="Submitted",
	)
	send_sms_for_lab_results(doc)
	# create_delivery_note(doc)


def set_normals(doc):
	dob = frappe.get_cached_value("Patient", doc.patient, "dob")
	age = dateutil.relativedelta.relativedelta(getdate(), dob).years
	for row in doc.normal_test_items:
		normals = get_normals(row.lab_test_name, age, doc.patient_sex)
		if normals:
			row.min_normal = normals.get("min")
			row.max_normal = normals.get("max")
			row.text_normal = normals.get("text")

			if not row.result_value:
				continue

			try:
				float(row.result_value)
			except ValueError:
				row.detailed_normal_range = ""
				row.result_status = ""
				continue

			data_normals = calc_data_normals(normals, row.result_value)
			row.detailed_normal_range = data_normals["detailed_normal_range"]
			row.result_status = data_normals["result_status"]


def calc_data_normals(data, value):
	data = frappe._dict(data)
	value = flt(value)
	result = {"detailed_normal_range": "", "result_status": ""}

	if data.min and not data.max:
		result["detailed_normal_range"] = "> " + str(data.min)
		if value > data.min:
			result["result_status"] = "N"
		else:
			result["result_status"] = "L"
	elif not data.min and data.max:
		result["detailed_normal_range"] = "< " + str(data.max)
		if value < data.max:
			result["result_status"] = "N"
		else:
			result["result_status"] = "H"
	elif data.min and data.max:
		result["detailed_normal_range"] = str(data.min) + " - " + str(data.max)
		if value > data.min and value < data.max:
			result["result_status"] = "N"
		elif value < data.min:
			result["result_status"] = "L"
		elif value > data.max:
			result["result_status"] = "H"

	if data.text:
		if result["detailed_normal_range"]:
			result["detailed_normal_range"] += " / "

		result["detailed_normal_range"] += data.text

	return result


@frappe.whitelist()
def get_normals(lab_test_name, patient_age, patient_sex):
	data = {}
	doc = get_lab_test_template(lab_test_name)
	if not doc:
		return data
	if float(patient_age) < 3:
		data["min"] = doc.i_min_range
		data["max"] = doc.i_max_range
		data["text"] = doc.i_text
	elif float(patient_age) < 12:
		data["min"] = doc.c_min_range
		data["max"] = doc.c_max_range
		data["text"] = doc.c_text
	else:
		if patient_sex == "Male":
			data["min"] = doc.m_min_range
			data["max"] = doc.m_max_range
			data["text"] = doc.m_text
		elif patient_sex == "Female":
			data["min"] = doc.f_min_range
			data["max"] = doc.f_max_range
			data["text"] = doc.f_text

	return data


def get_lab_test_template(lab_test_name):
	template_id = frappe.db.exists("Lab Test Template", {"lab_test_code": lab_test_name})
	if template_id:
		return frappe.get_cached_doc("Lab Test Template", lab_test_name)
	return False


def create_delivery_note(doc):
	if doc.ref_doctype and doc.ref_docname and doc.ref_doctype == "Patient Encounter":
		patient_encounter_doc = frappe.get_cached_doc(doc.ref_doctype, doc.ref_docname)
		create_delivery_note_from_LRPT(doc, patient_encounter_doc)


def on_trash(doc, method):
	sample_list = frappe.get_all(
		"Sample Collection",
		filters={
			"ref_doctype": doc.doctype,
			"ref_docname": doc.name,
		},
	)
	for item in sample_list:
		frappe.delete_doc("Sample Collection", item.name)


def on_cancel(doc, method):
	doc.flags.ignore_links = True

	if doc.docstatus == 2:
		frappe.db.set_value("Lab Prescription", doc.hms_tz_ref_childname, "lab_test", "")

		new_lab_doc = frappe.copy_doc(doc)
		new_lab_doc.status = "Draft"
		new_lab_doc.workflow_state = None
		new_lab_doc.amended_from = doc.name
		new_lab_doc.save(ignore_permissions=True)

		url = frappe.utils.get_url_to_form(new_lab_doc.doctype, new_lab_doc.name)
		frappe.msgprint(
			f"Lab Test: <strong>{doc.name}</strong> is cancelled:<br>\
            New Lab Test: <a href='{url}'><strong>{new_lab_doc.name}</strong></a> is successful created"
		)


def create_sample_collection(doc):
	if not doc.template:
		return
	template = frappe.get_cached_doc("Lab Test Template", doc.template)
	if not template.sample_qty or not template.sample:
		return

	sample = DocType("Sample Collection")
	sample_docname = (
		frappe.qb.from_(sample)
		.select(sample.name)
		.where(
			(sample.ref_doctype == doc.ref_doctype)
			& (sample.ref_docname == doc.ref_docname)
			& (sample.sample == template.sample)
		)
		.run(as_dict=True)
	)

	if len(sample_docname) > 0:
		sample_doc = frappe.get_cached_doc("Sample Collection", sample_docname[0].name)
		sample_doc.append(
			"lab_tests",
			{
				"lab_test": doc.name,
				"lab_test_tempate": template.name,
				"test_abbr": template.abbr,
			},
		)
		sample_doc.save(ignore_permissions=True)
		doc.sample = sample_doc.name
		doc.save(ignore_permissions=True)
		frappe.msgprint(_(f"Sample Collection: {sample_doc.name} updated"), alert=True)
		return

	sample_doc = frappe.new_doc("Sample Collection")
	sample_doc.patient = doc.patient
	sample_doc.patient_name = doc.patient_name
	sample_doc.patient_age = doc.patient_age
	sample_doc.patient_sex = doc.patient_sex
	sample_doc.company = doc.company
	sample_doc.sample = template.sample
	sample_doc.sample_uom = template.sample_uom
	sample_doc.sample_qty = template.sample_qty
	sample_doc.sample_details = template.sample_details
	sample_doc.ref_doctype = doc.ref_doctype
	sample_doc.ref_docname = doc.ref_docname
	sample_doc.append(
		"lab_tests",
		{
			"lab_test": doc.name,
			"lab_test_tempate": template.name,
			"test_abbr": template.abbr,
		},
	)

	sample_doc.flags.ignore_permissions = True
	sample_doc.insert()
	sample_doc.reload()
	doc.sample = sample_doc.name
	doc.save(ignore_permissions=True)
	frappe.msgprint(_(f"Sample Collection created {sample_doc.name}"), alert=True)


def update_lab_prescription(doc):
	if doc.ref_doctype == "Patient Encounter":
		hsrp = DocType("Healthcare Service Request Payment")
		(
			frappe.qb.update(hsrp)
			.set(hsrp.lrpmt_status, "Submitted")
			.where(hsrp.ref_docname == doc.hms_tz_ref_childname)
		).run()


def send_sms_for_lab_results(doc):
	if doc.ref_doctype == "Patient Encounter":
		(
			allow_send_sms_for_multiple_labs,
			lab_result_sms_template,
		) = frappe.get_cached_value(
			"HMS TZ Setting",
			doc.company,
			["allow_send_sms_for_multiple_labs", "lab_result_sms_template"],
		)

		if allow_send_sms_for_multiple_labs == 0:
			return

		if not lab_result_sms_template:
			return

		all_labs_per_encounter = frappe.get_all(
			"Lab Test",
			filters={
				"ref_doctype": "Patient Encounter",
				"ref_docname": doc.ref_docname,
				"sms_sent": 0,
			},
			fields=["name", "docstatus"],
		)
		sms_sent = False
		if len(all_labs_per_encounter) > 0:
			draft_labs = [lab for lab in all_labs_per_encounter if lab.docstatus == 0]
			if len(draft_labs) == 0:
				phone_number = [doc.mobile]
				if lab_result_sms_template and phone_number:
					# admin template
					msg = frappe.render_template(lab_result_sms_template, {"doc": doc})  # nosemgrep
					send_sms(phone_number, msg, success_msg=False)
					sms_sent = True
					frappe.msgprint(
						_(f"SMS sent to Patient: {doc.patient_name}, PhoneNo: {doc.mobile}"),
						alert=True,
					)

		if sms_sent:
			for row in all_labs_per_encounter:
				frappe.db.set_value("Lab Test", row.name, "sms_sent", 1)


def check_cash_payments_from_encounter(
	doc,
	ref_doctype,
	ref_docname_field,
	prescription_field,
	item_name_field,
	item_descriptor,
	additional_checks=None,
):
	# Ensure there is a valid reference to an encounter
	if getattr(doc, ref_docname_field) and getattr(doc, ref_doctype) == "Patient Encounter":
		encounter_doc = frappe.get_cached_doc("Patient Encounter", getattr(doc, ref_docname_field))

		# Check for insurance subscription
		if encounter_doc.insurance_subscription:
			# Filter items based on prescription details and additional checks
			cash_items = [
				getattr(row, item_name_field)
				for row in getattr(encounter_doc, prescription_field)
				if (
					row.prescribe == 1
					and row.invoiced == 0
					and row.is_cancelled == 0
					and (additional_checks(row) if additional_checks else True)
				)
			]

			# If there are any items to be paid in cash, display a message
			if len(cash_items) > 0:
				items_list = ", ".join(cash_items)
				msg = f"""<div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
                    <h4 style="font-weight: bold; color: #856404;"><i class="fa fa-exclamation-triangle" aria-hidden="true"></i> Payment Alert</h4>
                    <p style="font-size: 16px;">This patient: <strong>{doc.patient}</strong> has <strong>{len(cash_items)}</strong> more {item_descriptor} to be paid in cash:</p>
                    <h4 style="font-style: italic; font-weight: bold; color: #856404;">{items_list}</h4>
                    <p style="font-size: 16px;">Please inform the patient to pay in cash for these {item_descriptor}.</p>
                </div>"""

				frappe.msgprint(msg)
