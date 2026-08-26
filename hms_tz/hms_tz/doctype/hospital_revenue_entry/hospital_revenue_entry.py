# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import get_fullname, getdate, nowdate


class HospitalRevenueEntry(Document):
	def on_trash(self):
		"""
		On trash, update the status of the related LRPMT document
		"""
		msg = """<div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">\
                    <p class="text-center"><i>You cannot delete Hospital Revenue Entry record</i></p>
                </div>"""

		if self.source_doctype != "Inpatient Record":
			frappe.throw(
				title="Cannot Delete",
				msg=msg,
				exc=frappe.ValidationError,
			)

		elif not self.flags.is_unconfirmed:
			frappe.throw(
				title="Cannot Delete",
				msg=msg,
				exc=frappe.ValidationError,
			)


def create_revenue_entry(doc):
	"""
	Create Hospital Revenue Entry documents

	Args:
	    doc: Source document
	"""
	entries = []
	if doc.doctype == "Patient Appointment":
		entries = get_entry_from_appointment(doc)
	elif doc.doctype == "Delivery Note":
		entries = get_entry_from_dn(doc)
	elif doc.doctype in [
		"Lab Test",
		"Radiology Examination",
		"Clinical Procedure",
	]:
		entries = get_entry_from_lrp_docs(doc)
	elif doc.doctype == "Therapy Plan":
		entries = get_entry_from_plan(doc)

	if len(entries) == 0:
		return

	for entry in entries:
		hre = frappe.new_doc("Hospital Revenue Entry")
		hre.update(entry)
		hre.insert(ignore_permissions=True)
		hre.reload()


def create_revenue_entry_from_insurance_mcr(doc, ref_docnames=None):
	"""
	Create Hospital Revenue Entry documents from Medication Change Request

	Args:
	    doc: Source document
	    ref_docnames: List of reference document names to create entries for
	"""

	if ref_docnames is None:
		ref_docnames = []
	entries = build_insurance_drug_entry(doc, ref_docnames)

	if len(entries) == 0:
		return

	for entry in entries:
		hre = frappe.new_doc("Hospital Revenue Entry")
		hre.update(entry)
		hre.insert(ignore_permissions=True)
		hre.reload()


def create_revenue_entry_from_inpatient_cash_mcr(mcr_doc, ref_docnames):
	"""Create Hospital Revenue Entry for inpatient cash patients from MCR

	This function creates HRE entries for newly added drugs in MCR for inpatient cash patients
	who don't have Healthcare Service Request.

	Args:
	    mcr_doc: Medication Change Request document
	    ref_docnames: List of Drug Prescription reference names to create HRE for
	"""
	if not ref_docnames:
		return

	encounter_doc = frappe.get_doc("Patient Encounter", mcr_doc.patient_encounter)

	for ref_docname in ref_docnames:
		# Find the drug prescription row
		drug_row = None
		for d in encounter_doc.drug_prescription:
			if d.name == ref_docname:
				drug_row = d
				break

		if not drug_row:
			continue

		rate = drug_row.amount
		qty = drug_row.delivered_quantity or drug_row.quantity

		entry_dict = {
			"patient": mcr_doc.patient,
			"patient_name": mcr_doc.patient_name,
			"customer": frappe.get_cached_value("Patient", mcr_doc.patient, "customer"),
			"appointment": mcr_doc.appointment,
			"posting_date": encounter_doc.encounter_date,
			"created_by": get_fullname(frappe.session.user),
			"company": mcr_doc.company,
			"source_doctype": "Patient Encounter",
			"source_docname": mcr_doc.patient_encounter,
			"currency": frappe.get_cached_value("Company", mcr_doc.company, "default_currency"),
			"qty": qty,
			"rate": rate,
			"amount": rate * qty,
			"percent_covered": 100,
			"service_type": "Medication",
			"service_name": drug_row.drug_code,
			"is_cancelled": 0,
			"payment_type": "Cash",
			"mode_of_payment": "",
			"ref_doctype": drug_row.doctype,
			"ref_docname": drug_row.name,
			"lrpmt_doctype": "Delivery Note",
			"lrpmt_docname": drug_row.delivery_note,
			"dn_detail": drug_row.dn_detail,
			"lrpmt_status": "Draft",
			"healthcare_service_unit": drug_row.healthcare_service_unit,
			"healthcare_practitioner": mcr_doc.healthcare_practitioner,
			"updated_from_doctype": "Medication Change Request",
			"updated_from_docname": mcr_doc.name,
			"remarks": "Service Added from Medication Change Request",
		}

		hre = frappe.new_doc("Hospital Revenue Entry")
		hre.update(entry_dict)
		hre.insert(ignore_permissions=True)


def update_revenue_entry(
	lrpmt_doctype,
	lrpmt_docname,
	ref_doctype,
	ref_docname,
	lrpmt_status=None,
	is_cancelled=0,
	therapy_plan=None,
):
	hre = DocType("Hospital Revenue Entry")
	query = frappe.qb.update(hre).where((hre.ref_doctype == ref_doctype) & (hre.ref_docname == ref_docname))

	if lrpmt_status:
		query = query.set(hre.lrpmt_status, lrpmt_status)

	if is_cancelled == 1:
		query = query.set(hre.is_cancelled, 1)

	if therapy_plan and lrpmt_doctype == "Therapy Session":
		query = query.set(hre.lrpmt_doctype, lrpmt_doctype)
		query = query.set(hre.lrpmt_docname, lrpmt_docname)

		query = query.where((hre.lrpmt_doctype == "Therapy Plan") & (hre.lrpmt_docname == therapy_plan))
	else:
		query = query.where((hre.lrpmt_doctype == lrpmt_doctype) & (hre.lrpmt_docname == lrpmt_docname))

	query.run()


def update_returned_or_cancelled_revenue_entry(
	ref_docname, update_from_doctype, update_from_docname, is_cancelled=1, qty_returned=0, remarks=""
):
	hre = DocType("Hospital Revenue Entry")
	updated_by = get_fullname(frappe.session.user)

	if qty_returned > 0:
		hre_details = (
			frappe.qb.from_(hre)
			.select(hre.name, hre.qty, hre.rate, hre.percent_covered)
			.where(hre.ref_docname == ref_docname)
		).run(as_dict=True)

		for row in hre_details:
			new_qty = row.get("qty") - qty_returned
			new_amount = (row.get("percent_covered", 0) / 100) * new_qty * row.get("rate")

			update_query = (
				frappe.qb.update(hre)
				.set(hre.remarks, remarks)
				.set(hre.amount, new_amount)
				.set(hre.updated_by, updated_by)
				.set(hre.qty_returned, qty_returned)
				.set(hre.is_cancelled, is_cancelled)
				.set(hre.updated_from_doctype, update_from_doctype)
				.set(hre.updated_from_docname, update_from_docname)
				.where(hre.name == row.get("name"))
			)
			update_query.run()

	else:
		query = (
			frappe.qb.update(hre)
			.set(hre.remarks, remarks)
			.set(hre.updated_by, updated_by)
			.set(hre.is_cancelled, is_cancelled)
			.set(hre.updated_from_doctype, update_from_doctype)
			.set(hre.updated_from_docname, update_from_docname)
			.where(hre.ref_docname == ref_docname)
		)
		query.run()


def get_entry_from_appointment(doc):
	"""
	Get entry from the appointment document

	Args:
	    doc: Source document

	Returns:
	    list: List containing entry dictionary
	"""
	entry_dict = {
		"patient": doc.patient,
		"patient_name": doc.patient_name,
		"customer": frappe.get_cached_value("Patient", doc.patient, "customer"),
		"appointment": doc.name,
		"posting_date": doc.appointment_date,
		"created_by": get_fullname(frappe.session.user),
		"company": doc.company,
		"qty": 1,
		"rate": doc.paid_amount,
		"amount": doc.paid_amount,
		"percent_covered": 100,
		"source_doctype": doc.doctype,
		"source_docname": doc.name,
		"service_type": "Consultation Charges",
		"service_name": doc.billing_item,
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
		"payment_type": "Insurance" if doc.insurance_subscription else "Cash",
		"insurance_subscription": doc.insurance_subscription,
		"insurance_company": doc.insurance_company,
		"insurance_coverage_plan": doc.coverage_plan_name,
		"mode_of_payment": doc.mode_of_payment,
		"sales_invoice": doc.ref_sales_invoice,
		"department": doc.department,
		"healthcare_service_unit": doc.service_unit,
		"healthcare_practitioner": doc.practitioner,
	}
	return [entry_dict]


def get_entry_from_lrp_docs(doc):
	"""
	Get entries from the source document

	Args:
	    doc: Source document

	Returns:
	    list: List of entry dictionaries
	"""
	entries = []

	if doc.get("insurance_subscription"):
		entries = get_entry_from_insurance_lrp(doc)
	else:
		entries = get_entry_from_cash_lrp(doc)

	return entries


def get_entry_from_insurance_lrp(doc):
	"""
	Get entry from the LRP document

	Args:

	    doc: Source document

	Returns:
	    List: List of entry dictionaries
	"""
	entries = []

	hsrp = DocType("Healthcare Service Request Payment")

	hsrp_items = (
		frappe.qb.from_(hsrp)
		.select(
			hsrp.qty,
			hsrp.rate,
			hsrp.amount,
			hsrp.qty_returned,
			hsrp.price_list,
			hsrp.percent_covered,
			hsrp.is_cancelled,
			hsrp.insurance_subscription,
			hsrp.insurance_company,
			hsrp.payor_plan,
			hsrp.dn_detail,
			hsrp.ref_docname,
			hsrp.ref_doctype,
			hsrp.service_name,
			hsrp.service_type,
			hsrp.sales_invoice_number,
			hsrp.payment_type,
			hsrp.department_hsu,
		)
		.where(hsrp.ref_docname == doc.hms_tz_ref_childname)
	).run(as_dict=True)

	if len(hsrp_items) == 0:
		return entries

	for row in hsrp_items:
		entry_dict = {
			"patient": doc.patient,
			"patient_name": doc.patient_name,
			"customer": frappe.get_cached_value("Patient", doc.patient, "customer"),
			"appointment": doc.appointment,
			"posting_date": nowdate(),
			"created_by": get_fullname(frappe.session.user),
			"company": doc.company,
			"source_doctype": doc.ref_doctype,
			"source_docname": doc.ref_docname,
			"price_list": row.get("price_list"),
			"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"percent_covered": row.percent_covered,
			"service_type": row.get("service_type"),
			"service_name": row.get("service_name"),
			"is_cancelled": row.get("is_cancelled"),
			"payment_type": row.get("payment_type"),
			"insurance_subscription": row.get("insurance_subscription"),
			"insurance_company": row.get("insurance_company"),
			"insurance_coverage_plan": row.get("payor_plan"),
			"mode_of_payment": "",
			"sales_invoice": row.get("sales_invoice_number"),
			"ref_doctype": row.get("ref_doctype"),
			"ref_docname": row.get("ref_docname"),
			"lrpmt_doctype": doc.doctype,
			"lrpmt_docname": doc.name,
			"lrpmt_status": ("Draft" if doc.get("docstatus") == 0 else "Submitted"),
			"department": doc.get("department"),
			"healthcare_service_unit": row.get("department_hsu"),
			"healthcare_practitioner": doc.practitioner,
		}
		entries.append(entry_dict)

	return entries


def get_entry_from_cash_lrp(doc):
	"""
	Get entry from the LRP document

	Args:

	    doc: Source document

	Returns:
	    List: List of entry dictionaries
	"""
	entries = []

	si = DocType("Sales Invoice")
	sii = DocType("Sales Invoice Item")

	si_items = (
		frappe.qb.from_(si)
		.inner_join(sii)
		.on(si.name == sii.parent)
		.select(
			sii.qty,
			sii.rate,
			sii.amount,
			si.selling_price_list,
			sii.reference_dt,
			sii.parent.as_("sales_invoice_number"),
		)
		.where(
			(si.docstatus == 1) & (si.patient == doc.patient) & (sii.reference_dn == doc.hms_tz_ref_childname)
		)
	).run(as_dict=True)

	if len(si_items) == 0:
		return entries

	service_type = ""
	service_name = ""
	if doc.doctype == "Lab Test":
		service_type = "Lab Test Template"
		service_name = doc.template
	elif doc.doctype == "Radiology Examination":
		service_type = "Radiology Examination Template"
		service_name = doc.radiology_examination_template
	elif doc.doctype == "Clinical Procedure":
		service_type = "Clinical Procedure Template"
		service_name = doc.procedure_template

	for row in si_items:
		entry_dict = {
			"patient": doc.patient,
			"patient_name": doc.patient_name,
			"customer": frappe.get_cached_value("Patient", doc.patient, "customer"),
			"appointment": doc.appointment,
			"posting_date": nowdate(),
			"created_by": get_fullname(frappe.session.user),
			"company": doc.company,
			"source_doctype": doc.ref_doctype,
			"source_docname": doc.ref_docname,
			"price_list": row.get("selling_price_list"),
			"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"service_type": service_type,
			"service_name": service_name,
			"is_cancelled": 0,
			"payment_type": "Cash",
			"mode_of_payment": "",
			"sales_invoice": row.get("sales_invoice_number"),
			"ref_doctype": row.get("reference_dt"),
			"ref_docname": doc.hms_tz_ref_childname,
			"lrpmt_status": ("Draft" if doc.get("docstatus") == 0 else "Submitted"),
			"department": doc.get("department"),
			"healthcare_service_unit": frappe.get_cached_value(
				row.get("reference_dt"),
				doc.hms_tz_ref_childname,
				"department_hsu",
			),
			"healthcare_practitioner": doc.practitioner,
		}
		entries.append(entry_dict)

	return entries


def get_entry_from_dn(doc):
	"""
	Get entry from the Delivery Note document

	Args:
	    doc: Source document

	Returns:
	    List: List of entry dictionaries
	"""

	entries = []

	if doc.coverage_plan_name:
		insurance_ref_docnams = [d.reference_name for d in doc.items if d.reference_name]
		entries += build_insurance_drug_entry(doc, insurance_ref_docnams)
	else:
		entries += build_cash_drug_entry(doc)

	return entries


def build_insurance_drug_entry(doc, ref_docnames):
	entries = []

	if len(ref_docnames) == 0:
		return entries

	hsrp = DocType("Healthcare Service Request Payment")

	hsrp_items = (
		frappe.qb.from_(hsrp)
		.select(
			hsrp.qty,
			hsrp.rate,
			hsrp.amount,
			hsrp.qty_returned,
			hsrp.price_list,
			hsrp.percent_covered,
			hsrp.is_cancelled,
			hsrp.insurance_subscription,
			hsrp.insurance_company,
			hsrp.payor_plan,
			hsrp.dn_detail,
			hsrp.lrpmt_doctype,
			hsrp.lrpmt_docname,
			hsrp.ref_docname,
			hsrp.ref_doctype,
			hsrp.service_name,
			hsrp.service_type,
			hsrp.sales_invoice_number,
			hsrp.payment_type,
			hsrp.department_hsu,
		)
		.where((hsrp.ref_doctype == "Drug Prescription") & (hsrp.ref_docname.isin(ref_docnames)))
	).run(as_dict=True)

	if len(hsrp_items) == 0:
		return entries

	for row in hsrp_items:
		entry_dict = {
			"patient": doc.get("patient"),
			"patient_name": doc.get("patient_name"),
			"customer": doc.get("customer") or frappe.get_cached_value("Patient", doc.patient, "customer"),
			"appointment": doc.get("hms_tz_appointment_no") or doc.get("appointment"),
			"posting_date": nowdate(),
			"created_by": get_fullname(frappe.session.user),
			"company": doc.company,
			"source_doctype": doc.get("reference_doctype") or "Patient Encounter",
			"source_docname": doc.get("reference_name") or doc.get("patient_encounter"),
			"price_list": row.get("price_list"),
			"currency": doc.get("currency")
			or frappe.get_cached_value("Company", doc.company, "default_currency"),
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"percent_covered": row.percent_covered,
			"service_type": row.get("service_type"),
			"service_name": row.get("service_name"),
			"is_cancelled": row.get("is_cancelled"),
			"payment_type": row.get("payment_type"),
			"insurance_subscription": row.get("insurance_subscription"),
			"insurance_company": row.get("insurance_company"),
			"insurance_coverage_plan": row.get("payor_plan"),
			"mode_of_payment": "",
			"sales_invoice": row.get("sales_invoice_number"),
			"ref_doctype": row.get("ref_doctype"),
			"ref_docname": row.get("ref_docname"),
			"lrpmt_doctype": row.get("lrpmt_doctype"),
			"lrpmt_docname": row.get("lrpmt_docname"),
			"dn_detail": row.get("dn_detail"),
			"lrpmt_status": "Draft"
			if (doc.get("docstatus") == 0 or doc.get("doctype") == "Medication Change Request")
			else "Submitted",
			"department": doc.get("department"),
			"healthcare_service_unit": row.get("department_hsu"),
			"healthcare_practitioner": doc.get("healthcare_practitioner"),
		}

		if doc.get("doctype") == "Medication Change Request":
			entry_dict["updated_from_doctype"] = doc.doctype
			entry_dict["updated_from_docname"] = doc.name
			entry_dict["remarks"] = "Service Added from Medication Change Request"

		entries.append(entry_dict)

	return entries


def build_cash_drug_entry(doc):
	entries = []

	for item in doc.items:
		entry_dict = {
			"patient": doc.get("patient"),
			"patient_name": doc.get("patient_name"),
			"customer": doc.customer,
			"appointment": doc.get("hms_tz_appointment_no"),
			"posting_date": nowdate(),
			"created_by": get_fullname(frappe.session.user),
			"company": doc.company,
			"source_doctype": doc.get("reference_doctype") or "Sales Invoice",
			"source_docname": doc.get("reference_name") or doc.get("form_sales_invoice"),
			"price_list": doc.get("selling_price_list"),
			"currency": doc.currency,
			"qty": item.qty,
			"rate": item.rate,
			"amount": item.amount,
			"service_type": "Medication",
			"service_name": item.item_code,
			"is_cancelled": 0,
			"payment_type": "Cash",
			# "insurance_subscription": row.get("insurance_subscription"),
			# "insurance_company": row.get("insurance_company"),
			# "insurance_coverage_plan": row.get("payor_plan"),
			"mode_of_payment": "",
			"sales_invoice": doc.get("form_sales_invoice"),
			"ref_doctype": item.get("reference_doctype"),
			"ref_docname": item.get("reference_name"),
			"lrpmt_doctype": doc.doctype,
			"lrpmt_docname": doc.name,
			"dn_detail": item.name,
			"lrpmt_status": ("Draft" if doc.get("docstatus") == 0 else "Submitted"),
			"department": doc.get("department"),
			"healthcare_service_unit": doc.get("healthcare_service_unit"),
			"healthcare_practitioner": doc.get("healthcare_practitioner"),
		}
		entries.append(entry_dict)

	return entries


def get_entry_from_plan(doc):
	"""
	Get entry from the Therapy Plan document

	Args:
	    doc: Source document

	Returns:
	    List: List of entry dictionaries
	"""
	entries = []
	if doc.get("insurance_company"):
		entries = get_entry_from_insurance_plan(doc)
	else:
		entries = get_entry_from_cash_plan(doc)

	return entries


def get_entry_from_insurance_plan(doc):
	"""
	Get entry from the Therapy Plan document

	Args:
	    doc: Source document

	Returns:
	    List: List of entry dictionaries
	"""
	entries = []

	refs = [d.hms_tz_ref_childname for d in doc.therapy_plan_details if d.hms_tz_ref_childname]
	if len(refs) == 0:
		return entries

	tpd = DocType("Therapy Plan Detail")
	hsrp = DocType("Healthcare Service Request Payment")

	hsrp_items = (
		frappe.qb.from_(hsrp)
		.inner_join(tpd)
		.on(hsrp.ref_docname == tpd.hms_tz_ref_childname)
		.select(
			hsrp.qty,
			hsrp.rate,
			hsrp.amount,
			hsrp.qty_returned,
			hsrp.price_list,
			hsrp.percent_covered,
			hsrp.is_cancelled,
			hsrp.insurance_subscription,
			hsrp.insurance_company,
			hsrp.payor_plan,
			hsrp.dn_detail,
			hsrp.ref_doctype,
			hsrp.ref_docname,
			hsrp.service_name,
			hsrp.service_type,
			hsrp.sales_invoice_number,
			hsrp.payment_type,
			hsrp.department_hsu,
		)
		.where((hsrp.ref_docname.isin(refs)) & (tpd.parent == doc.name))
	).run(as_dict=True)

	if len(hsrp_items) == 0:
		return entries

	for row in hsrp_items:
		entry_dict = {
			"patient": doc.get("patient"),
			"patient_name": doc.get("patient_name"),
			"customer": frappe.get_cached_value("Patient", doc.patient, "customer"),
			"appointment": doc.hms_tz_appointment,
			"posting_date": nowdate(),
			"created_by": get_fullname(frappe.session.user),
			"company": doc.company,
			"source_doctype": doc.ref_doctype,
			"source_docname": doc.ref_docname,
			"price_list": row.get("price_list"),
			"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"percent_covered": row.percent_covered,
			"service_type": row.get("service_type"),
			"service_name": row.get("service_name"),
			"is_cancelled": row.get("is_cancelled"),
			"payment_type": row.get("payment_type"),
			"insurance_subscription": row.get("insurance_subscription"),
			"insurance_company": row.get("insurance_company"),
			"insurance_coverage_plan": row.get("payor_plan"),
			"mode_of_payment": "",
			"sales_invoice": row.get("sales_invoice_number"),
			"ref_doctype": row.get("ref_doctype"),
			"ref_docname": row.get("ref_docname"),
			"lrpmt_doctype": doc.doctype,
			"lrpmt_docname": doc.name,
			"dn_detail": row.get("dn_detail"),
			"lrpmt_status": ("Draft" if doc.get("docstatus") == 0 else "Submitted"),
			"department": doc.get("department"),
			"healthcare_service_unit": row.get("department_hsu"),
			"healthcare_practitioner": frappe.get_cached_value(
				doc.ref_doctype, doc.ref_docname, "practitioner"
			),
		}
		entries.append(entry_dict)

	return entries


def get_entry_from_cash_plan(doc):
	"""
	Get entry from the Therapy Plan document

	Args:
	    doc: Source document

	Returns:
	    List: List of entry dictionaries
	"""
	entries = []

	refs = [
		d.hms_tz_ref_childname
		for d in doc.therapy_plan_details
		if d.hms_tz_ref_childname and d.parent == doc.name
	]
	if len(refs) == 0:
		return entries

	si = DocType("Sales Invoice")
	sii = DocType("Sales Invoice Item")

	si_items = (
		frappe.qb.from_(si)
		.inner_join(sii)
		.on(si.name == sii.parent)
		.select(
			sii.qty,
			sii.rate,
			sii.amount,
			sii.item_code,
			si.selling_price_list,
			si.customer,
			sii.reference_dt,
			sii.reference_dn,
			sii.parent.as_("sales_invoice_number"),
		)
		.where((si.docstatus == 1) & (si.patient == doc.patient) & (sii.reference_dn.isin(refs)))
	).run(as_dict=True)

	if len(si_items) == 0:
		return entries

	for row in si_items:
		entry_dict = {
			"patient": doc.get("patient"),
			"patient_name": doc.get("patient_name"),
			"customer": row.get("customer"),
			"appointment": doc.hms_tz_appointment,
			"posting_date": nowdate(),
			"created_by": get_fullname(frappe.session.user),
			"company": doc.company,
			"source_doctype": doc.ref_doctype,
			"source_docname": doc.ref_docname,
			"price_list": row.get("selling_price_list"),
			"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
			"qty": row.qty,
			"rate": row.rate,
			"amount": row.amount,
			"service_type": "Therapy Type",
			"service_name": row.get("item_code"),
			"is_cancelled": 0,
			"payment_type": "Cash",
			"mode_of_payment": "",
			"sales_invoice": row.get("sales_invoice_number"),
			"ref_doctype": row.get("reference_dt"),
			"ref_docname": row.get("reference_dn"),
			"lrpmt_doctype": doc.doctype,
			"lrpmt_docname": doc.name,
			"dn_detail": "",
			"lrpmt_status": ("Draft" if doc.get("docstatus") == 0 else "Submitted"),
			"department": doc.get("department"),
			"healthcare_service_unit": frappe.get_cached_value(
				row.get("reference_dt"),
				row.get("reference_dn"),
				"department_hsu",
			),
			"healthcare_practitioner": frappe.get_cached_value(
				doc.ref_doctype, doc.ref_docname, "practitioner"
			),
		}
		entries.append(entry_dict)

	return entries


def create_inpatient_revenue_entries(doc):
	"""
	Get entry from the Inpatient record document

	Args:
	    doc: Source document
	"""

	old_occupancy_map = {}
	old_consultancy_map = {}
	entries_to_be_created = []
	entries_to_be_deleted = []

	old_doc = doc.get_doc_before_save()
	if len(old_doc.inpatient_occupancies) > 0:
		old_occupancy_map = {row.name: row for row in old_doc.inpatient_occupancies}

	if len(old_doc.inpatient_consultancy) > 0:
		old_consultancy_map = {row.name: row for row in old_doc.inpatient_consultancy}

	for row in doc.inpatient_occupancies:
		old_row = old_occupancy_map.get(row.name)

		if old_row and old_row.is_confirmed == 0 and row.is_confirmed == 0:
			continue

		elif old_row and row.hre_created == 0 and old_row.is_confirmed == 0 and row.is_confirmed == 1:
			entry_dict = get_entry_from_occupancy(doc, row)
			entries_to_be_created.append(entry_dict)
			row.hre_created = 1

		elif old_row and row.hre_created == 1 and old_row.is_confirmed == 1 and row.is_confirmed == 0:
			row.hre_created = 0
			entries_to_be_deleted.append(
				{
					"patient": doc.patient,
					"appointment": doc.patient_appointment,
					"source_doctype": doc.doctype,
					"source_docname": doc.name,
					"lrpmt_doctype": row.doctype,
					"lrpmt_docname": row.name,
				}
			)

		elif not old_row and row.hre_created == 0 and row.is_confirmed == 1:
			entry_dict = get_entry_from_occupancy(doc, row)
			entries_to_be_created.append(entry_dict)
			row.hre_created = 1

		elif not old_row and row.hre_created == 1 and row.is_confirmed == 0:
			row.hre_created = 0
			entries_to_be_deleted.append(
				{
					"patient": doc.patient,
					"appointment": doc.patient_appointment,
					"source_doctype": doc.doctype,
					"source_docname": doc.name,
					"lrpmt_doctype": row.doctype,
					"lrpmt_docname": row.name,
				}
			)

	for row in doc.inpatient_consultancy:
		old_row = old_consultancy_map.get(row.name)

		if old_row and old_row.is_confirmed == 0 and row.is_confirmed == 0:
			continue

		elif old_row and row.hre_created == 0 and old_row.is_confirmed == 0 and row.is_confirmed == 1:
			entry_dict = get_entry_from_consultancy(doc, row)
			entries_to_be_created.append(entry_dict)
			row.hre_created = 1

		elif old_row and row.hre_created == 1 and old_row.is_confirmed == 1 and row.is_confirmed == 0:
			row.hre_created = 0
			entries_to_be_deleted.append(
				{
					"patient": doc.patient,
					"appointment": doc.patient_appointment,
					"source_doctype": doc.doctype,
					"source_docname": doc.name,
					"lrpmt_doctype": row.doctype,
					"lrpmt_docname": row.name,
				}
			)

		elif not old_row and row.hre_created == 0 and row.is_confirmed == 1:
			entry_dict = get_entry_from_consultancy(doc, row)
			entries_to_be_created.append(entry_dict)
			row.hre_created = 1

		elif not old_row and row.hre_created == 1 and row.is_confirmed == 0:
			row.hre_created = 0
			entries_to_be_deleted.append(
				{
					"patient": doc.patient,
					"appointment": doc.patient_appointment,
					"source_doctype": doc.doctype,
					"source_docname": doc.name,
					"lrpmt_doctype": row.doctype,
					"lrpmt_docname": row.name,
				}
			)

	if len(entries_to_be_created) == 0 and len(entries_to_be_deleted) == 0:
		return

	for entry in entries_to_be_created:
		hre = frappe.new_doc("Hospital Revenue Entry")
		hre.update(entry)
		hre.insert(ignore_permissions=True)
		hre.reload()

		# frappe.db.set_value(
		#     entry.get("lrpmt_doctype"),
		#     entry.get("lrpmt_docname"),
		#     "hre_created",
		#     1
		# )

	for entry in entries_to_be_deleted:
		hre_docname = frappe.get_cached_value("Hospital Revenue Entry", entry, "name")
		if not hre_docname:
			continue

		frappe.delete_doc(
			"Hospital Revenue Entry",
			hre_docname,
			force=True,
			delete_permanently=True,
			flags={"ignore_permissions": True, "is_unconfirmed": True},
		)
		# frappe.db.set_value(
		#     entry.get("lrpmt_doctype"),
		#     entry.get("lrpmt_docname"),
		#     "hre_created",
		#     0
		# )


def get_entry_from_occupancy(doc, row):
	"""
	Get entry from the Inpatient Occupancy row

	Args:
	    doc: Source document
	    row: Inpatient Occupancy row

	Returns:
	    dict: Entry dictionary
	"""
	entry_dict = {
		"patient": doc.patient,
		"patient_name": doc.patient_name,
		"customer": frappe.get_cached_value("Patient", doc.patient, "customer"),
		"appointment": doc.patient_appointment,
		"posting_date": getdate(row.check_in),
		"created_by": get_fullname(frappe.session.user),
		"company": doc.company,
		"source_doctype": doc.doctype,
		"source_docname": doc.name,
		"price_list": "",
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
		"qty": 1,
		"rate": row.amount,
		"amount": row.amount,
		"service_type": row.doctype,
		"service_name": frappe.get_cached_value(
			"Healthcare Service Unit", row.service_unit, "service_unit_type"
		),
		"is_cancelled": 0,
		"payment_type": "Insurance" if doc.insurance_subscription else "Cash",
		"insurance_subscription": doc.insurance_subscription or "",
		"insurance_company": doc.insurance_company or "",
		"insurance_coverage_plan": doc.insurance_coverage_plan or "",
		"mode_of_payment": "",
		"sales_invoice": row.sales_invoice_number if row.sales_invoice_number else "",
		"ref_doctype": "",
		"ref_docname": "",
		"lrpmt_doctype": row.doctype,
		"lrpmt_docname": row.name,
		"dn_detail": "",
		"lrpmt_status": "",
		"department": doc.medical_department,
		"healthcare_service_unit": row.service_unit,
		"healthcare_practitioner": "",
	}

	return entry_dict


def get_entry_from_consultancy(doc, row):
	"""
	Get entry from the Inpatient Consultancy row

	Args:
	    doc: Source document
	    row: Inpatient Consultancy row

	Returns:
	    dict: Entry dictionary
	"""
	entry_dict = {
		"patient": doc.patient,
		"patient_name": doc.patient_name,
		"customer": frappe.get_cached_value("Patient", doc.patient, "customer"),
		"appointment": doc.patient_appointment,
		"posting_date": getdate(row.date),
		"created_by": get_fullname(frappe.session.user),
		"company": doc.company,
		"source_doctype": doc.doctype,
		"source_docname": doc.name,
		"price_list": "",
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
		"qty": 1,
		"rate": row.rate,
		"amount": row.rate,
		"service_type": row.doctype,
		"service_name": row.consultation_item,
		"is_cancelled": 0,
		"payment_type": "Insurance" if doc.insurance_subscription else "Cash",
		"insurance_subscription": doc.insurance_subscription or "",
		"insurance_company": doc.insurance_company or "",
		"insurance_coverage_plan": doc.insurance_coverage_plan or "",
		"mode_of_payment": "",
		"sales_invoice": row.sales_invoice_number if row.sales_invoice_number else "",
		"ref_doctype": "",
		"ref_docname": "",
		"lrpmt_doctype": row.doctype,
		"lrpmt_docname": row.name,
		"dn_detail": "",
		"lrpmt_status": "",
		"department": doc.medical_department,
		"healthcare_service_unit": "",
		"healthcare_practitioner": row.healthcare_practitioner,
	}

	return entry_dict
