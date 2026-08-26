# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe.query_builder import DocType
from pypika.functions import Date, IfNull
from pypika.terms import Case, Criterion, Not, ValueWrapper


def execute(filters=None):
	if (
		filters.get("show_only_ongoing_ipds") == 1
		and filters.get("show_only_prev_items_for_discharged_ipds") == 1
	):
		frappe.throw(
			"Cannot filter by both Ongoing IPDs and Discharged IPDs<br>\
            Uncheck one of the filters either 'Show Ongoing IPDs or Show prev items for discharged IPDs\
            and try again"
		)

	data = []
	columns = get_columns(filters)

	if filters.get("show_only_cancelled_items") == 1:
		data = get_cancelled_data(filters)
		return columns, data

	else:
		if not filters.payment_mode:
			data = get_cash_insurance_data(filters)
			return columns, data

		elif filters.payment_mode == "Cash":
			data = get_cash_data(filters)
			return columns, data

		else:
			data = get_insurance_data(filters)

		return columns, data


def get_columns(filters):
	columns = [
		{
			"fieldname": "date",
			"label": "Date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "patient",
			"label": "Patient",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "patient_name",
			"label": "PatientName/CustomerName",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "patient_type",
			"label": "Patient Type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "appointment_no",
			"label": "AppointmentNo",
			"fieldtype": "Link",
			"options": "Patient Appointment",
			"width": 120,
		},
	]
	if not filters.show_only_cancelled_items:
		columns += [
			{
				"fieldname": "bill_no",
				"label": "Bill No",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "service_type",
				"label": "Service Type",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "service_name",
				"label": "Service Name",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "qty",
				"label": "Qty",
				"fieldtype": "Int",
				"width": 50,
			},
			{
				"fieldname": "rate",
				"label": "Rate",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"fieldname": "discount_amount",
				"label": "Discount Amount",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"fieldname": "amount",
				"label": "Amount",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"fieldname": "payment_method",
				"label": "Payment Method",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "department",
				"label": "Department",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldnaeme": "practitioner",
				"label": "Practitioner",
				"fieldtype": "Link",
				"options": "Healthcare Practitioner",
				"width": 120,
			},
			{
				"fieldname": "service_unit",
				"label": "Service Unit",
				"fieldtype": "Link",
				"options": "Healthcare Service Unit",
				"width": 120,
			},
			{
				"fieldname": "sales_invoice",
				"label": "Sales Invoice",
				"fieldtype": "Link",
				"options": "Sales Invoice",
				"width": 120,
			},
			{
				"fieldname": "status",
				"label": "Status",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "date_modified",
				"label": "Date Modified",
				"fieldtype": "Datetime",
				"width": 120,
			},
		]

	elif filters.get("show_only_cancelled_items") == 1:
		columns += [
			{
				"fieldname": "encounter_no",
				"label": "Encounter No",
				"fieldtype": "Link",
				"options": "Patient Encounter",
				"width": 120,
			},
			{
				"fieldname": "bill_doctype",
				"label": "Bill Doctype",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "bill_no",
				"label": "Bill No",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "service_name",
				"label": "Service Name",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "qty",
				"label": "Qty",
				"fieldtype": "Int",
				"width": 50,
			},
			{
				"fieldname": "rate",
				"label": "Rate",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"fieldname": "amount",
				"label": "Amount",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"fieldname": "payment_method",
				"label": "Payment Method",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "reference_no",
				"label": "LRPMT Return No",
				"fieldtype": "Data",
				"width": 120,
			},
			# {
			#     "fieldnaeme": "requested_by",
			#     "label": "Requested By",
			#     "fieldtype": "Data",
			#     "width": 120,
			# },
			# {
			#     "fieldname": "approved_by",
			#     "label": "Approved By",
			#     "fieldtype": "Data",
			#     "width": 120,
			# },
			{
				"fieldname": "reason",
				"label": "Cancellation Reason",
				"fieldtype": "Data",
				"width": 120,
			},
			{
				"fieldname": "date_modified",
				"label": "Date Modified",
				"fieldtype": "Datetime",
				"width": 120,
			},
		]
	return columns


def get_cash_insurance_data(filters):
	cash_insurance_data = []

	appoints = get_prev_and_ongoing_ipds(filters)

	cash_insurance_data += get_insurance_appointment_data(filters, appoints)
	cash_insurance_data += get_cash_appointment_data(filters, appoints)
	cash_insurance_data += get_insurance_lab_data(filters, appoints)
	cash_insurance_data += get_cash_lab_data(filters, appoints)
	cash_insurance_data += get_insurance_radiology_data(filters, appoints)
	cash_insurance_data += get_cash_radiology_data(filters, appoints)
	cash_insurance_data += get_insurance_procedure_data(filters, appoints)
	cash_insurance_data += get_cash_procedure_data(filters, appoints)
	cash_insurance_data += get_insurance_drug_data(filters, appoints)
	cash_insurance_data += get_cash_drug_data(filters, appoints)
	cash_insurance_data += get_insurance_therapy_data(filters, appoints)
	cash_insurance_data += get_cash_therapy_data(filters, appoints)
	cash_insurance_data += get_insurance_ipd_beds_data(filters, appoints)
	cash_insurance_data += get_cash_ipd_beds_data(filters, appoints)
	cash_insurance_data += get_insurance_ipd_cons_data(filters, appoints)
	cash_insurance_data += get_cash_ipd_cons_data(filters, appoints)

	# Direct cash sales from sales order to sales invoice
	cash_insurance_data += get_direct_sales_from_invoices(filters)

	return cash_insurance_data


def get_cash_data(filters):
	cash_data = []

	appoints = get_prev_and_ongoing_ipds(filters)

	cash_data += get_cash_appointment_data(filters, appoints)
	cash_data += get_cash_lab_data(filters, appoints)
	cash_data += get_cash_radiology_data(filters, appoints)
	cash_data += get_cash_procedure_data(filters, appoints)
	cash_data += get_cash_drug_data(filters, appoints)
	cash_data += get_cash_therapy_data(filters, appoints)
	cash_data += get_cash_ipd_beds_data(filters, appoints)
	cash_data += get_cash_ipd_cons_data(filters, appoints)

	# Direct cash sales from sales order to sales invoice
	cash_data += get_direct_sales_from_invoices(filters)

	return cash_data


def get_insurance_data(filters):
	insurance_data = []

	appoints = get_prev_and_ongoing_ipds(filters)

	insurance_data += get_insurance_appointment_data(filters, appoints)
	insurance_data += get_insurance_lab_data(filters, appoints)
	insurance_data += get_insurance_radiology_data(filters, appoints)
	insurance_data += get_insurance_procedure_data(filters, appoints)
	insurance_data += get_insurance_drug_data(filters, appoints)
	insurance_data += get_insurance_therapy_data(filters, appoints)
	insurance_data += get_insurance_ipd_beds_data(filters, appoints)
	insurance_data += get_insurance_ipd_cons_data(filters, appoints)

	return insurance_data


def get_insurance_appointment_data(filters, appoints):
	pa = DocType("Patient Appointment")
	item = DocType("Item")

	insurance_appointment_query = (
		frappe.qb.from_(pa)
		.inner_join(item)
		.on(pa.billing_item == item.name)
		.select(
			pa.appointment_date.as_("date"),
			pa.name.as_("appointment_no"),
			pa.name.as_("bill_no"),
			pa.patient.as_("patient"),
			pa.patient_name.as_("patient_name"),
			Case()
			.when(pa.appointment_type.like("Emergency"), "In-Patient")
			.else_("Out-Patient")
			.as_("patient_type"),
			item.item_group.as_("service_type"),
			pa.billing_item.as_("service_name"),
			pa.coverage_plan_name.as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			pa.paid_amount.as_("rate"),
			pa.paid_amount.as_("amount"),
			Case().when(pa.status == "Closed", "Submitted").else_("Draft").as_("status"),
			pa.practitioner.as_("practitioner"),
			pa.department.as_("department"),
			pa.service_unit.as_("service_unit"),
			pa.modified.as_("date_modified"),
		)
		.where(
			(pa.company == filters.company)
			& (pa.status != "Cancelled")
			& (pa.follow_up == 0)
			& (pa.has_no_consultation_charges == 0)
			& ((pa.insurance_subscription.isnotnull()) & (pa.insurance_subscription != ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_appointment_query = insurance_appointment_query.where(
			(pa.appointment_date < filters.from_date) & (pa.name.isin(appoints))
		)
	else:
		insurance_appointment_query = insurance_appointment_query.where(
			pa.appointment_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_appointment_query = insurance_appointment_query.where(
			item.item_group == filters.service_type
		)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_appointment_query = insurance_appointment_query.where(
			pa.insurance_company == filters.payment_mode
		)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_appointment_query = insurance_appointment_query.where(pa.name.isin(appoints))

	insurance_appointment_data = insurance_appointment_query.run(as_dict=True)

	return insurance_appointment_data


def get_cash_appointment_data(filters, appoints):
	pa = DocType("Patient Appointment")
	item = DocType("Item")
	sii = DocType("Sales Invoice Item")

	cash_appointment_query = (
		frappe.qb.from_(pa)
		.inner_join(item)
		.on(pa.billing_item == item.name)
		.inner_join(sii)
		.on(pa.name == sii.reference_dn)
		.select(
			pa.appointment_date.as_("date"),
			pa.name.as_("appointment_no"),
			pa.name.as_("bill_no"),
			pa.patient.as_("patient"),
			pa.patient_name.as_("patient_name"),
			Case()
			.when(pa.appointment_type.like("Emergency"), "In-Patient")
			.else_("Out-Patient")
			.as_("patient_type"),
			item.item_group.as_("service_type"),
			pa.billing_item.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			pa.paid_amount.as_("rate"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			sii.net_amount.as_("amount"),
			Case().when(pa.status == "Closed", "Submitted").else_("Draft").as_("status"),
			pa.practitioner.as_("practitioner"),
			pa.department.as_("department"),
			pa.service_unit.as_("service_unit"),
			pa.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(pa.company == filters.company)
			& (pa.status != "Cancelled")
			& (pa.follow_up == 0)
			& (pa.has_no_consultation_charges == 0)
			& ((pa.ref_sales_invoice.isnotnull()) & (pa.ref_sales_invoice != ""))
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		cash_appointment_query = cash_appointment_query.where(
			(pa.appointment_date < filters.from_date) & (pa.name.isin(appoints))
		)
	else:
		cash_appointment_query = cash_appointment_query.where(
			pa.appointment_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		cash_appointment_query = cash_appointment_query.where(item.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		cash_appointment_query = cash_appointment_query.where(pa.name.isin(appoints))

	cash_appointment_data = cash_appointment_query.run(as_dict=True)

	return cash_appointment_data


def get_insurance_lab_data(filters, appoints):
	lab = DocType("Lab Test")
	lab_prescription = DocType("Lab Prescription")
	template = DocType("Lab Test Template")
	pe = DocType("Patient Encounter")

	insurance_lab_query = (
		frappe.qb.from_(lab)
		.inner_join(lab_prescription)
		.on(lab.hms_tz_ref_childname == lab_prescription.name)
		.inner_join(template)
		.on(lab.template == template.name)
		.inner_join(pe)
		.on(lab.ref_docname == pe.name)
		.select(
			lab.result_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			lab.name.as_("bill_no"),
			lab.patient.as_("patient"),
			lab.patient_name.as_("patient_name"),
			Case().when(lab.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			template.lab_test_group.as_("service_type"),
			lab.template.as_("service_name"),
			lab.hms_tz_insurance_coverage_plan.as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			lab_prescription.amount.as_("rate"),
			lab_prescription.amount.as_("amount"),
			Case().when(lab.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			lab.practitioner.as_("practitioner"),
			lab.department.as_("department"),
			lab_prescription.department_hsu.as_("service_unit"),
			lab.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& (lab.hms_tz_insurance_coverage_plan.isnotnull() & (lab.hms_tz_insurance_coverage_plan != ""))
			& (lab.docstatus != 2)
			& (lab.ref_doctype == "Patient Encounter")
			& (lab.ref_docname == lab_prescription.parent)
			& (lab.prescribe == 0)
			& (lab_prescription.prescribe == 0)
			& (lab_prescription.is_cancelled == 0)
			& (lab_prescription.is_not_available_inhouse == 0)
		)
	)
	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_lab_query = insurance_lab_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		insurance_lab_query = insurance_lab_query.where(
			pe.encounter_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_lab_query = insurance_lab_query.where(template.lab_test_group == filters.service_type)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_lab_query = insurance_lab_query.where(lab.insurance_company == filters.payment_mode)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_lab_query = insurance_lab_query.where(pe.appointment.isin(appoints))

	insurance_lab_data = insurance_lab_query.run(as_dict=True)

	return insurance_lab_data


def get_cash_lab_data(filters, appoints):
	lab = DocType("Lab Test")
	lab_prescription = DocType("Lab Prescription")
	template = DocType("Lab Test Template")
	sii = DocType("Sales Invoice Item")
	DocType("Sales Invoice")
	pe = DocType("Patient Encounter")

	# Paid Lab Data for OPD Patients, Admitted and Discharged Patients
	# Link to Sales invoice
	paid_cash_lab_query = (
		frappe.qb.from_(lab)
		.inner_join(lab_prescription)
		.on(lab.hms_tz_ref_childname == lab_prescription.name)
		.inner_join(template)
		.on(lab.template == template.name)
		.inner_join(sii)
		.on(lab.hms_tz_ref_childname == sii.reference_dn)
		# .inner_join(si)
		# .on(sii.parent == si.name)
		.inner_join(pe)
		.on(lab.ref_docname == pe.name)
		.select(
			lab.result_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			lab.name.as_("bill_no"),
			lab.patient.as_("patient"),
			lab.patient_name.as_("patient_name"),
			Case().when(lab.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			template.lab_test_group.as_("service_type"),
			lab.template.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			lab_prescription.amount.as_("rate"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			sii.net_amount.as_("amount"),
			Case().when(lab.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			lab.practitioner.as_("practitioner"),
			lab.department.as_("department"),
			lab_prescription.department_hsu.as_("service_unit"),
			lab.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(lab.company == filters.company)
			& (lab.docstatus != 2)
			& (lab.ref_doctype == "Patient Encounter")
			& (lab.ref_docname == lab_prescription.parent)
			& (lab_prescription.prescribe == 1)
			& (lab_prescription.invoiced == 1)
			& (lab_prescription.is_cancelled == 0)
			& (lab_prescription.is_not_available_inhouse == 0)
			& (lab_prescription.lab_test_created == 1)
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
			# & Not(si.status.isin(["Credit Note Issued", "Return"]))
			# & (si.docstatus == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_cash_lab_query = paid_cash_lab_query.where(
			(lab.result_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		paid_cash_lab_query = paid_cash_lab_query.where(
			lab.result_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		paid_cash_lab_query = paid_cash_lab_query.where(template.lab_test_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_cash_lab_query = paid_cash_lab_query.where(pe.appointment.isin(appoints))

	paid_cash_lab_data = paid_cash_lab_query.run(as_dict=True)

	# Unpaid Lab Data for ongoing Admitted Patients
	# No link to Sales invoice
	unpaid_cash_lab_query = (
		frappe.qb.from_(lab)
		.inner_join(lab_prescription)
		.on(lab.hms_tz_ref_childname == lab_prescription.name)
		.inner_join(template)
		.on(lab.template == template.name)
		.inner_join(pe)
		.on(lab.ref_docname == pe.name)
		.select(
			lab.result_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			lab.name.as_("bill_no"),
			lab.patient.as_("patient"),
			lab.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			template.lab_test_group.as_("service_type"),
			lab.template.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			lab_prescription.amount.as_("rate"),
			lab_prescription.amount.as_("amount"),
			Case().when(lab.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			lab.practitioner.as_("practitioner"),
			lab.department.as_("department"),
			lab_prescription.department_hsu.as_("service_unit"),
			lab.modified.as_("date_modified"),
			lab_prescription.sales_invoice_number.as_("sales_invoice"),
		)
		.where(
			(lab.company == filters.company)
			& (lab.docstatus != 2)
			& (lab.ref_doctype == "Patient Encounter")
			& (lab.ref_docname == lab_prescription.parent)
			& (lab_prescription.prescribe == 1)
			& (lab_prescription.invoiced == 0)
			& (lab_prescription.is_cancelled == 0)
			& (lab_prescription.is_not_available_inhouse == 0)
			& (lab_prescription.lab_test_created == 1)
			& ((lab.inpatient_record.isnotnull()) & (lab.inpatient_record != ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_cash_lab_query = unpaid_cash_lab_query.where(
			(lab.result_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		unpaid_cash_lab_query = unpaid_cash_lab_query.where(
			lab.result_date.between(filters.from_date, filters.to_date)
		)
	if filters.service_type:
		unpaid_cash_lab_query = unpaid_cash_lab_query.where(template.lab_test_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_cash_lab_query = unpaid_cash_lab_query.where(pe.appointment.isin(appoints))

	unpaid_cash_lab_data = unpaid_cash_lab_query.run(as_dict=True)

	return paid_cash_lab_data + unpaid_cash_lab_data


def get_insurance_radiology_data(filters, appoints):
	rad = DocType("Radiology Examination")
	rad_prescription = DocType("Radiology Procedure Prescription")
	template = DocType("Radiology Examination Template")
	pe = DocType("Patient Encounter")

	insurance_rad_query = (
		frappe.qb.from_(rad)
		.inner_join(rad_prescription)
		.on(rad.hms_tz_ref_childname == rad_prescription.name)
		.inner_join(template)
		.on(rad.radiology_examination_template == template.name)
		.inner_join(pe)
		.on(rad.ref_docname == pe.name)
		.select(
			rad.start_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			rad.name.as_("bill_no"),
			rad.patient.as_("patient"),
			rad.patient_name.as_("patient_name"),
			Case().when(rad.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			template.item_group.as_("service_type"),
			rad.radiology_examination_template.as_("service_name"),
			rad.hms_tz_insurance_coverage_plan.as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			rad_prescription.amount.as_("rate"),
			rad_prescription.amount.as_("amount"),
			Case().when(rad.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			rad.practitioner.as_("practitioner"),
			rad.medical_department.as_("department"),
			rad_prescription.department_hsu.as_("service_unit"),
			rad.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& ((rad.hms_tz_insurance_coverage_plan.isnotnull()) & (rad.hms_tz_insurance_coverage_plan != ""))
			& (rad.docstatus != 2)
			& (rad.ref_doctype == "Patient Encounter")
			& (rad.ref_docname == rad_prescription.parent)
			& (rad.prescribe == 0)
			& (rad_prescription.prescribe == 0)
			& (rad_prescription.is_cancelled == 0)
			& (rad_prescription.is_not_available_inhouse == 0)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_rad_query = insurance_rad_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		insurance_rad_query = insurance_rad_query.where(
			pe.encounter_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_rad_query = insurance_rad_query.where(template.item_group == filters.service_type)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_rad_query = insurance_rad_query.where(rad.insurance_company == filters.payment_mode)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_rad_query = insurance_rad_query.where(pe.appointment.isin(appoints))

	insurance_rad_data = insurance_rad_query.run(as_dict=True)

	return insurance_rad_data


def get_cash_radiology_data(filters, appoints):
	rad = DocType("Radiology Examination")
	rad_prescription = DocType("Radiology Procedure Prescription")
	template = DocType("Radiology Examination Template")
	sii = DocType("Sales Invoice Item")
	DocType("Sales Invoice")
	pe = DocType("Patient Encounter")

	# Paid Radiology Data for OPD Patients, Admitted and Discharged Patients
	# Link to Sales invoice
	paid_cash_rad_query = (
		frappe.qb.from_(rad)
		.inner_join(rad_prescription)
		.on(rad.hms_tz_ref_childname == rad_prescription.name)
		.inner_join(template)
		.on(rad.radiology_examination_template == template.name)
		.inner_join(sii)
		.on(rad.hms_tz_ref_childname == sii.reference_dn)
		# .inner_join(si)
		# .on(sii.parent == si.name)
		.inner_join(pe)
		.on(rad.ref_docname == pe.name)
		.select(
			rad.start_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			rad.name.as_("bill_no"),
			rad.patient.as_("patient"),
			rad.patient_name.as_("patient_name"),
			Case().when(rad.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			template.item_group.as_("service_type"),
			rad.radiology_examination_template.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			rad_prescription.amount.as_("rate"),
			sii.net_amount.as_("amount"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			Case().when(rad.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			rad.practitioner.as_("practitioner"),
			rad.medical_department.as_("department"),
			rad_prescription.department_hsu.as_("service_unit"),
			rad.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(rad.company == filters.company)
			& (rad.docstatus != 2)
			& (rad.ref_doctype == "Patient Encounter")
			& (rad.ref_docname == rad_prescription.parent)
			& (rad_prescription.invoiced == 1)
			& (rad_prescription.prescribe == 1)
			& (rad_prescription.is_cancelled == 0)
			& (rad_prescription.is_not_available_inhouse == 0)
			& (rad_prescription.radiology_examination_created == 1)
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
			# & Not(si.status.isin(["Credit Note Issued", "Return"]))
			# & (si.docstatus == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_cash_rad_query = paid_cash_rad_query.where(
			(rad.start_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		paid_cash_rad_query = paid_cash_rad_query.where(
			rad.start_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		paid_cash_rad_query = paid_cash_rad_query.where(template.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_cash_rad_query = paid_cash_rad_query.where(pe.appointment.isin(appoints))

	paid_cash_rad_data = paid_cash_rad_query.run(as_dict=True)

	# Unpaid Radiology Data for ongoing Admitted Patients
	# No link to Sales invoice
	unpaid_cash_rad_query = (
		frappe.qb.from_(rad)
		.inner_join(rad_prescription)
		.on(rad.hms_tz_ref_childname == rad_prescription.name)
		.inner_join(template)
		.on(rad.radiology_examination_template == template.name)
		.inner_join(pe)
		.on(rad.ref_docname == pe.name)
		.select(
			rad.start_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			rad.name.as_("bill_no"),
			rad.patient.as_("patient"),
			rad.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			template.item_group.as_("service_type"),
			rad.radiology_examination_template.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			rad_prescription.amount.as_("rate"),
			rad_prescription.amount.as_("amount"),
			Case().when(rad.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			rad.practitioner.as_("practitioner"),
			rad.medical_department.as_("department"),
			rad_prescription.department_hsu.as_("service_unit"),
			rad.modified.as_("date_modified"),
			rad_prescription.sales_invoice_number.as_("sales_invoice"),
		)
		.where(
			(rad.company == filters.company)
			& (rad.docstatus != 2)
			& (rad.ref_doctype == "Patient Encounter")
			& (rad.ref_docname == rad_prescription.parent)
			& ((rad.inpatient_record.isnotnull()) & (rad.inpatient_record != ""))
			& (rad_prescription.prescribe == 1)
			& (rad_prescription.invoiced == 0)
			& (rad_prescription.is_cancelled == 0)
			& (rad_prescription.is_not_available_inhouse == 0)
			& (rad_prescription.radiology_examination_created == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_cash_rad_query = unpaid_cash_rad_query.where(
			(rad.start_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		unpaid_cash_rad_query = unpaid_cash_rad_query.where(
			rad.start_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		unpaid_cash_rad_query = unpaid_cash_rad_query.where(template.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_cash_rad_query = unpaid_cash_rad_query.where(pe.appointment.isin(appoints))

	unpaid_cash_rad_data = unpaid_cash_rad_query.run(as_dict=True)

	return paid_cash_rad_data + unpaid_cash_rad_data


def get_insurance_procedure_data(filters, appoints):
	procedure = DocType("Clinical Procedure")
	pp = DocType("Procedure Prescription")
	template = DocType("Clinical Procedure Template")
	pe = DocType("Patient Encounter")

	insurance_procedure_query = (
		frappe.qb.from_(procedure)
		.inner_join(pp)
		.on(procedure.hms_tz_ref_childname == pp.name)
		.inner_join(template)
		.on(procedure.procedure_template == template.name)
		.inner_join(pe)
		.on(procedure.ref_docname == pe.name)
		.select(
			procedure.start_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			procedure.name.as_("bill_no"),
			procedure.patient.as_("patient"),
			procedure.patient_name.as_("patient_name"),
			Case()
			.when(procedure.inpatient_record.isnull(), "Out-Patient")
			.else_("In-Patient")
			.as_("patient_type"),
			template.item_group.as_("service_type"),
			procedure.procedure_template.as_("service_name"),
			procedure.hms_tz_insurance_coverage_plan.as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			pp.amount.as_("rate"),
			pp.amount.as_("amount"),
			Case().when(procedure.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			procedure.practitioner.as_("practitioner"),
			procedure.medical_department.as_("department"),
			pp.department_hsu.as_("service_unit"),
			procedure.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& (
				(procedure.hms_tz_insurance_coverage_plan.isnotnull())
				& (procedure.hms_tz_insurance_coverage_plan != "")
			)
			& (procedure.docstatus != 2)
			& (procedure.ref_doctype == "Patient Encounter")
			& (procedure.ref_docname == pp.parent)
			& (procedure.prescribe == 0)
			& (pp.prescribe == 0)
			& (pp.is_cancelled == 0)
			& (pp.is_not_available_inhouse == 0)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_procedure_query = insurance_procedure_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		insurance_procedure_query = insurance_procedure_query.where(
			pe.encounter_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_procedure_query = insurance_procedure_query.where(
			template.item_group == filters.service_type
		)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_procedure_query = insurance_procedure_query.where(
			pe.insurance_company == filters.payment_mode
		)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_procedure_query = insurance_procedure_query.where(pe.appointment.isin(appoints))

	insurance_procedure_data = insurance_procedure_query.run(as_dict=True)

	return insurance_procedure_data


def get_cash_procedure_data(filters, appoints):
	procedure = DocType("Clinical Procedure")
	pp = DocType("Procedure Prescription")
	template = DocType("Clinical Procedure Template")
	sii = DocType("Sales Invoice Item")
	DocType("Sales Invoice")
	pe = DocType("Patient Encounter")

	# Paid Procedure Data for OPD Patients, Admitted and Discharged Patients
	# Link to Sales invoice
	paid_procedure_query = (
		frappe.qb.from_(procedure)
		.inner_join(pp)
		.on(procedure.hms_tz_ref_childname == pp.name)
		.inner_join(template)
		.on(procedure.procedure_template == template.name)
		.inner_join(sii)
		.on(procedure.hms_tz_ref_childname == sii.reference_dn)
		# .inner_join(si)
		# .on(sii.parent == si.name)
		.inner_join(pe)
		.on(procedure.ref_docname == pe.name)
		.select(
			procedure.start_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			procedure.name.as_("bill_no"),
			procedure.patient.as_("patient"),
			procedure.patient_name.as_("patient_name"),
			Case()
			.when(procedure.inpatient_record.isnull(), "Out-Patient")
			.else_("In-Patient")
			.as_("patient_type"),
			template.item_group.as_("service_type"),
			procedure.procedure_template.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			pp.amount.as_("rate"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			sii.net_amount.as_("amount"),
			Case().when(procedure.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			procedure.practitioner.as_("practitioner"),
			procedure.medical_department.as_("department"),
			pp.department_hsu.as_("service_unit"),
			procedure.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(procedure.company == filters.company)
			& (procedure.docstatus != 2)
			& (procedure.ref_doctype == "Patient Encounter")
			& (procedure.ref_docname.isnotnull())
			& (procedure.ref_docname == pp.parent)
			& (pp.invoiced == 1)
			& (pp.prescribe == 1)
			& (pp.is_cancelled == 0)
			& (pp.is_not_available_inhouse == 0)
			& (pp.procedure_created == 1)
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
			# & Not(si.status.isin(["Credit Note Issued", "Return"]))
			# & (si.docstatus == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_procedure_query = paid_procedure_query.where(
			(procedure.start_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		paid_procedure_query = paid_procedure_query.where(
			procedure.start_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		paid_procedure_query = paid_procedure_query.where(template.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_procedure_query = paid_procedure_query.where(pe.appointment.isin(appoints))

	paid_procedure_data = paid_procedure_query.run(as_dict=True)

	# Unpaid Radiology Data for ongoing Admitted Patients
	# No link to Sales invoice
	unpaid_procedure_query = (
		frappe.qb.from_(procedure)
		.inner_join(pp)
		.on(procedure.hms_tz_ref_childname == pp.name)
		.inner_join(template)
		.on(procedure.procedure_template == template.name)
		.inner_join(pe)
		.on(procedure.ref_docname == pe.name)
		.select(
			procedure.start_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			procedure.name.as_("bill_no"),
			procedure.patient.as_("patient"),
			procedure.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			template.item_group.as_("service_type"),
			procedure.procedure_template.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			pp.amount.as_("rate"),
			pp.amount.as_("amount"),
			Case().when(procedure.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			procedure.practitioner.as_("practitioner"),
			procedure.medical_department.as_("department"),
			pp.department_hsu.as_("service_unit"),
			procedure.modified.as_("date_modified"),
			pp.sales_invoice_number.as_("sales_invoice"),
		)
		.where(
			(procedure.company == filters.company)
			& (procedure.docstatus != 2)
			& (procedure.ref_doctype == "Patient Encounter")
			& (procedure.ref_docname.isnotnull())
			& (procedure.ref_docname == pp.parent)
			& ((procedure.inpatient_record.isnotnull()) & (procedure.inpatient_record != ""))
			& (pp.prescribe == 1)
			& (pp.invoiced == 0)
			& (pp.is_cancelled == 0)
			& (pp.is_not_available_inhouse == 0)
			& (pp.procedure_created == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_procedure_query = unpaid_procedure_query.where(
			(procedure.start_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		unpaid_procedure_query = unpaid_procedure_query.where(
			procedure.start_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		unpaid_procedure_query = unpaid_procedure_query.where(template.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_procedure_query = unpaid_procedure_query.where(pe.appointment.isin(appoints))

	unpaid_procedure_data = unpaid_procedure_query.run(as_dict=True)

	return paid_procedure_data + unpaid_procedure_data


def get_insurance_drug_data(filters, appoints):
	pe = DocType("Patient Encounter")
	dp = DocType("Drug Prescription")
	dn = DocType("Delivery Note")
	md = DocType("Medication")

	insurance_drug_query = (
		frappe.qb.from_(dp)
		.inner_join(md)
		.on(dp.drug_code == md.name)
		.inner_join(pe)
		.on(dp.parent == pe.name)
		.inner_join(dn)
		.on(pe.name == dn.reference_name)
		.select(
			pe.encounter_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			dn.name.as_("bill_no"),
			pe.patient.as_("patient"),
			pe.patient_name.as_("patient_name"),
			Case().when(pe.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			md.item_group.as_("service_type"),
			dp.drug_code.as_("service_name"),
			pe.insurance_coverage_plan.as_("payment_method"),
			(dp.quantity - dp.quantity_returned).as_("qty"),
			dp.amount.as_("rate"),
			((dp.quantity - dp.quantity_returned) * dp.amount).as_("amount"),
			Case().when(dn.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			pe.practitioner.as_("practitioner"),
			md.healthcare_service_order_category.as_("department"),
			pe.healthcare_service_unit.as_("service_unit"),
			dn.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& (dp.prescribe == 0)
			& (dp.is_cancelled == 0)
			& (dp.is_not_available_inhouse == 0)
			& (dn.docstatus != 2)
			& (dn.is_return == 0)
			& (dn.reference_doctype == "Patient Encounter")
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_drug_query = insurance_drug_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		insurance_drug_query = insurance_drug_query.where(
			pe.encounter_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_drug_query = insurance_drug_query.where(md.item_group == filters.service_type)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_drug_query = insurance_drug_query.where(pe.insurance_company == filters.payment_mode)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_drug_query = insurance_drug_query.where(pe.appointment.isin(appoints))

	insurance_drug_data = insurance_drug_query.run(as_dict=True)

	return insurance_drug_data


def get_cash_drug_data(filters, appoints):
	pe = DocType("Patient Encounter")
	dp = DocType("Drug Prescription")
	dn = DocType("Delivery Note")
	md = DocType("Medication")
	sii = DocType("Sales Invoice Item")
	DocType("Sales Invoice")

	# Paid Drug Data for OPD Patients, Admitted and Discharged Patients
	# Link to Sales invoice
	paid_drug_query = (
		frappe.qb.from_(pe)
		.inner_join(dp)
		.on(dp.parent == pe.name)
		.inner_join(md)
		.on(dp.drug_code == md.name)
		.inner_join(dn)
		.on(dp.delivery_note == dn.name)
		.inner_join(sii)
		.on(dp.name == sii.reference_dn)
		# .inner_join(si)
		# .on(sii.parent == si.name)
		.select(
			pe.encounter_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			dn.name.as_("bill_no"),
			pe.patient.as_("patient"),
			pe.patient_name.as_("patient_name"),
			Case().when(pe.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			md.item_group.as_("service_type"),
			dp.drug_code.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			(dp.quantity - dp.quantity_returned).as_("qty"),
			dp.amount.as_("rate"),
			(((dp.quantity - dp.quantity_returned) * dp.amount) - sii.net_amount).as_("discount_amount"),
			((dp.quantity - dp.quantity_returned) * sii.net_rate).as_("amount"),
			Case().when(dn.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			pe.practitioner.as_("practitioner"),
			md.healthcare_service_order_category.as_("department"),
			pe.healthcare_service_unit.as_("service_unit"),
			dn.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& (dp.prescribe == 1)
			& (dp.invoiced == 1)
			& (dp.is_cancelled == 0)
			& (dp.is_not_available_inhouse == 0)
			& (dn.docstatus != 2)
			& (dn.is_return == 0)
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
			# & (si.docstatus == 1)
			# & Not(si.status.isin(["Credit Note Issued", "Return"]))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_drug_query = paid_drug_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		paid_drug_query = paid_drug_query.where(pe.encounter_date.between(filters.from_date, filters.to_date))

	if filters.service_type:
		paid_drug_query = paid_drug_query.where(md.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_drug_query = paid_drug_query.where(pe.appointment.isin(appoints))

	paid_drug_data = paid_drug_query.run(as_dict=True)

	# Unpaid Drug Data for ongoing Admitted Patients
	# No link to Sales invoice
	unpaid_drug_query = (
		frappe.qb.from_(pe)
		.inner_join(dp)
		.on(dp.parent == pe.name)
		.inner_join(md)
		.on(dp.drug_code == md.name)
		.inner_join(dn)
		.on(
			pe.name == dn.reference_name
		)  # reference to encounter since every inpatient encounter will have a delivery note created
		.select(
			pe.encounter_date.as_("date"),
			pe.appointment.as_("appointment_no"),
			dn.name.as_("bill_no"),
			pe.patient.as_("patient"),
			pe.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			md.item_group.as_("service_type"),
			dp.drug_code.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			(dp.quantity - dp.quantity_returned).as_("qty"),
			dp.amount.as_("rate"),
			((dp.quantity - dp.quantity_returned) * dp.amount).as_("amount"),
			Case().when(dn.docstatus == 1, "Submitted").else_("Draft").as_("status"),
			pe.practitioner.as_("practitioner"),
			md.healthcare_service_order_category.as_("department"),
			pe.healthcare_service_unit.as_("service_unit"),
			dn.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& ((pe.inpatient_record.isnotnull()) & (pe.inpatient_record != ""))
			& (dp.prescribe == 1)
			& (dp.invoiced == 0)
			& (dp.is_cancelled == 0)
			& (dp.is_not_available_inhouse == 0)
			& (dp.drug_prescription_created == 1)
			& (dn.docstatus != 2)
			& (dn.is_return == 0)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_drug_query = unpaid_drug_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		unpaid_drug_query = unpaid_drug_query.where(
			pe.encounter_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		unpaid_drug_query = unpaid_drug_query.where(md.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_drug_query = unpaid_drug_query.where(pe.appointment.isin(appoints))

	unpaid_drug_data = unpaid_drug_query.run(as_dict=True)

	return paid_drug_data + unpaid_drug_data


def get_insurance_therapy_data(filters, appoints):
	tp = DocType("Therapy Plan")
	tpd = DocType("Therapy Plan Detail")
	tt = DocType("Therapy Type")
	pe = DocType("Patient Encounter")

	insurance_therapy_query = (
		frappe.qb.from_(tp)
		.inner_join(pe)
		.on(tp.ref_docname == pe.name)
		.inner_join(tpd)
		.on(pe.name == tpd.parent)
		.inner_join(tt)
		.on(tpd.therapy_type == tt.name)
		.select(
			tp.start_date.as_("date"),
			tp.hms_tz_appointment.as_("appointment_no"),
			tp.name.as_("bill_no"),
			tp.patient.as_("patient"),
			tp.patient_name.as_("patient_name"),
			Case().when(pe.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			tt.item_group.as_("service_type"),
			tpd.therapy_type.as_("service_name"),
			tp.hms_tz_insurance_coverage_plan.as_("payment_method"),
			(tpd.no_of_sessions - tpd.sessions_cancelled).as_("qty"),
			tpd.amount.as_("rate"),
			((tpd.no_of_sessions - tpd.sessions_cancelled) * tpd.amount).as_("amount"),
			Case().when(tp.status == "Completed", "Submitted").else_("Draft").as_("status"),
			pe.practitioner.as_("practitioner"),
			tt.medical_department.as_("department"),
			tpd.department_hsu.as_("service_unit"),
			tp.modified.as_("date_modified"),
		)
		.where(
			(pe.company == filters.company)
			& (tpd.is_cancelled == 0)
			& (tpd.is_not_available_inhouse == 0)
			& (tpd.invoiced == 0)
			& ((tp.hms_tz_insurance_coverage_plan.isnotnull()) & (tp.hms_tz_insurance_coverage_plan != ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_therapy_query = insurance_therapy_query.where(
			(pe.encounter_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		insurance_therapy_query = insurance_therapy_query.where(
			pe.encounter_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_therapy_query = insurance_therapy_query.where(tt.item_group == filters.service_type)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_therapy_query = insurance_therapy_query.where(pe.insurance_company == filters.payment_mode)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_therapy_query = insurance_therapy_query.where(pe.appointment.isin(appoints))

	insurance_therapy_data = insurance_therapy_query.run(as_dict=True)

	return insurance_therapy_data


def get_cash_therapy_data(filters, appoints):
	tp = DocType("Therapy Plan")
	tpd = DocType("Therapy Plan Detail")
	tt = DocType("Therapy Type")
	sii = DocType("Sales Invoice Item")
	DocType("Sales Invoice")
	pe = DocType("Patient Encounter")

	# Paid Therapy Data for OPD Patients, Admitted and Discharged Patients
	# Link to Sales invoice
	paid_therapy_query = (
		frappe.qb.from_(tp)
		.inner_join(pe)
		.on(tp.ref_docname == pe.name)
		.inner_join(tpd)
		.on(pe.name == tpd.parent)
		.inner_join(tt)
		.on(tpd.therapy_type == tt.name)
		.inner_join(sii)
		.on(tpd.name == sii.reference_dn)
		# .inner_join(si)
		# .on(sii.parent == si.name)
		.select(
			tp.start_date.as_("date"),
			tp.hms_tz_appointment.as_("appointment_no"),
			tp.name.as_("bill_no"),
			tp.patient.as_("patient"),
			tp.patient_name.as_("patient_name"),
			Case().when(pe.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			tt.item_group.as_("service_type"),
			tpd.therapy_type.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			(tpd.no_of_sessions - tpd.sessions_cancelled).as_("qty"),
			tpd.amount.as_("rate"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			sii.net_amount.as_("amount"),
			Case().when(tp.status == "Completed", "Submitted").else_("Draft").as_("status"),
			pe.practitioner.as_("practitioner"),
			tt.medical_department.as_("department"),
			tpd.department_hsu.as_("service_unit"),
			tp.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(tp.company == filters.company)
			& (tpd.prescribe == 1)
			& (tpd.is_cancelled == 0)
			& (tpd.is_not_available_inhouse == 0)
			& (tpd.invoiced == 1)
			& (tpd.therapy_plan_created == 1)
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
			# & Not(si.status.isin(["Credit Note Issued", "Return"]))
			# & (si.docstatus == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_therapy_query = paid_therapy_query.where(
			(tp.start_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		paid_therapy_query = paid_therapy_query.where(
			tp.start_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		paid_therapy_query = paid_therapy_query.where(tt.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_therapy_query = paid_therapy_query.where(pe.appointment.isin(appoints))

	paid_therapy_data = paid_therapy_query.run(as_dict=True)

	# Unpaid Therapy Data for ongoing Admitted Patients
	# No link to Sales invoice
	unpaid_therapy_query = (
		frappe.qb.from_(tp)
		.inner_join(pe)
		.on(tp.ref_docname == pe.name)
		.inner_join(tpd)
		.on(pe.name == tpd.parent)
		.inner_join(tt)
		.on(tpd.therapy_type == tt.name)
		.select(
			tp.start_date.as_("date"),
			tp.hms_tz_appointment.as_("appointment_no"),
			tp.name.as_("bill_no"),
			tp.patient.as_("patient"),
			tp.patient_name.as_("patient_name"),
			Case().when(pe.inpatient_record.isnull(), "Out-Patient").else_("In-Patient").as_("patient_type"),
			tt.item_group.as_("service_type"),
			tpd.therapy_type.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			(tpd.no_of_sessions - tpd.sessions_cancelled).as_("qty"),
			tpd.amount.as_("rate"),
			((tpd.no_of_sessions - tpd.sessions_cancelled) * tpd.amount).as_("amount"),
			Case().when(tp.status == "Completed", "Submitted").else_("Draft").as_("status"),
			pe.practitioner.as_("practitioner"),
			tt.medical_department.as_("department"),
			tpd.department_hsu.as_("service_unit"),
			tp.modified.as_("date_modified"),
			tpd.sales_invoice_number.as_("sales_invoice"),
		)
		.where(
			(tp.company == filters.company)
			& (tpd.prescribe == 1)
			& (tpd.is_cancelled == 0)
			& (tpd.is_not_available_inhouse == 0)
			& (tpd.invoiced == 0)
			& ((pe.inpatient_record.isnotnull()) & (pe.inpatient_record != ""))
			& (tpd.therapy_plan_created == 1)
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_therapy_query = unpaid_therapy_query.where(
			(tp.start_date < filters.from_date) & (pe.appointment.isin(appoints))
		)
	else:
		unpaid_therapy_query = unpaid_therapy_query.where(
			tp.start_date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		unpaid_therapy_query = unpaid_therapy_query.where(tt.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_therapy_query = unpaid_therapy_query.where(pe.appointment.isin(appoints))

	unpaid_therapy_data = unpaid_therapy_query.run(as_dict=True)

	return paid_therapy_data + unpaid_therapy_data


def get_insurance_ipd_beds_data(filters, appoints):
	io = DocType("Inpatient Occupancy")
	ip = DocType("Inpatient Record")
	hsu = DocType("Healthcare Service Unit")
	hsut = DocType("Healthcare Service Unit Type")

	insurance_ipd_beds_query = (
		frappe.qb.from_(io)
		.inner_join(ip)
		.on(io.parent == ip.name)
		.inner_join(hsu)
		.on(io.service_unit == hsu.name)
		.inner_join(hsut)
		.on(hsu.service_unit_type == hsut.name)
		.select(
			Date(io.check_in).as_("date"),
			ip.patient_appointment.as_("appointment_no"),
			ip.name.as_("bill_no"),
			ip.patient.as_("patient"),
			ip.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			hsut.item_group.as_("service_type"),
			hsu.service_unit_type.as_("service_name"),
			ip.insurance_coverage_plan.as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			io.amount.as_("rate"),
			io.amount.as_("amount"),
			hsu.service_unit_type.as_("department"),
			hsu.parent_healthcare_service_unit.as_("service_unit"),
			io.modified.as_("date_modified"),
		)
		.where(
			(ip.company == filters.company)
			& (io.is_confirmed == 1)
			& ((ip.insurance_coverage_plan.isnotnull()) & (ip.insurance_coverage_plan != ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_ipd_beds_query = insurance_ipd_beds_query.where(
			(io.check_in < filters.from_date) & (ip.patient_appointment.isin(appoints))
		)
	else:
		insurance_ipd_beds_query = insurance_ipd_beds_query.where(
			io.check_in.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_ipd_beds_query = insurance_ipd_beds_query.where(hsut.item_group == filters.service_type)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_ipd_beds_query = insurance_ipd_beds_query.where(
			ip.insurance_company == filters.payment_mode
		)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_ipd_beds_query = insurance_ipd_beds_query.where(ip.patient_appointment.isin(appoints))

	insurance_ipd_beds_data = insurance_ipd_beds_query.run(as_dict=True)

	return insurance_ipd_beds_data


def get_cash_ipd_beds_data(filters, appoints):
	io = DocType("Inpatient Occupancy")
	ip = DocType("Inpatient Record")
	hsu = DocType("Healthcare Service Unit")
	hsut = DocType("Healthcare Service Unit Type")
	sii = DocType("Sales Invoice Item")

	# Paid Beds Data for Admitted and Discharged Patients
	# Link to Sales invoice
	paid_cash_ipd_beds_query = (
		frappe.qb.from_(io)
		.inner_join(ip)
		.on(io.parent == ip.name)
		.inner_join(hsu)
		.on(io.service_unit == hsu.name)
		.inner_join(hsut)
		.on(hsu.service_unit_type == hsut.name)
		.inner_join(sii)
		.on(io.name == sii.reference_dn)
		.select(
			Date(io.check_in).as_("date"),
			ip.patient_appointment.as_("appointment_no"),
			ip.name.as_("bill_no"),
			ip.patient.as_("patient"),
			ip.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			hsut.item_group.as_("service_type"),
			hsu.service_unit_type.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			io.amount.as_("rate"),
			sii.net_amount.as_("amount"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			hsu.service_unit_type.as_("department"),
			hsu.parent_healthcare_service_unit.as_("service_unit"),
			io.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(ip.company == filters.company)
			& (io.is_confirmed == 1)
			& (io.invoiced == 1)
			& (ip.insurance_coverage_plan.isnull() | (ip.insurance_coverage_plan == ""))
			& (sii.docstatus == 1)
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_cash_ipd_beds_query = paid_cash_ipd_beds_query.where(
			(Date(io.check_in) < filters.from_date) & (ip.patient_appointment.isin(appoints))
		)
	else:
		paid_cash_ipd_beds_query = paid_cash_ipd_beds_query.where(
			Date(io.check_in).between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		paid_cash_ipd_beds_query = paid_cash_ipd_beds_query.where(hsut.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_cash_ipd_beds_query = paid_cash_ipd_beds_query.where(ip.patient_appointment.isin(appoints))

	paid_cash_ipd_beds_data = paid_cash_ipd_beds_query.run(as_dict=True)

	# UnPaid Beds Data for ongoing Admitted Patients
	# No Link to Sales invoice
	unpaid_cash_ipd_beds_query = (
		frappe.qb.from_(io)
		.inner_join(ip)
		.on(io.parent == ip.name)
		.inner_join(hsu)
		.on(io.service_unit == hsu.name)
		.inner_join(hsut)
		.on(hsu.service_unit_type == hsut.name)
		.select(
			Date(io.check_in).as_("date"),
			ip.patient_appointment.as_("appointment_no"),
			ip.name.as_("bill_no"),
			ip.patient.as_("patient"),
			ip.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			hsut.item_group.as_("service_type"),
			hsu.service_unit_type.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			io.amount.as_("rate"),
			io.amount.as_("amount"),
			hsu.service_unit_type.as_("department"),
			hsu.parent_healthcare_service_unit.as_("service_unit"),
			io.modified.as_("date_modified"),
			io.sales_invoice_number.as_("sales_invoice"),
		)
		.where(
			(ip.company == filters.company)
			& (ip.status != "Discharged")
			& (io.is_confirmed == 1)
			& (io.invoiced == 0)
			& (ip.insurance_coverage_plan.isnull() | (ip.insurance_coverage_plan == ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_cash_ipd_beds_query = unpaid_cash_ipd_beds_query.where(
			(Date(io.check_in) < filters.from_date) & (ip.patient_appointment.isin(appoints))
		)
	else:
		unpaid_cash_ipd_beds_query = unpaid_cash_ipd_beds_query.where(
			Date(io.check_in).between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		unpaid_cash_ipd_beds_query = unpaid_cash_ipd_beds_query.where(hsut.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_cash_ipd_beds_query = unpaid_cash_ipd_beds_query.where(ip.patient_appointment.isin(appoints))

	unpaid_cash_ipd_beds_data = unpaid_cash_ipd_beds_query.run(as_dict=True)

	return paid_cash_ipd_beds_data + unpaid_cash_ipd_beds_data


def get_insurance_ipd_cons_data(filters, appoints):
	ic = DocType("Inpatient Consultancy")
	ip = DocType("Inpatient Record")
	it = DocType("Item")
	pe = DocType("Patient Encounter")

	insurance_ipd_cons_query = (
		frappe.qb.from_(ic)
		.inner_join(ip)
		.on(ic.parent == ip.name)
		.inner_join(it)
		.on(ic.consultation_item == it.name)
		.inner_join(pe)
		.on(ic.encounter == pe.name)
		.select(
			ic.date.as_("date"),
			ip.patient_appointment.as_("appointment_no"),
			ip.name.as_("bill_no"),
			ip.patient.as_("patient"),
			ip.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			it.item_group.as_("service_type"),
			ic.consultation_item.as_("service_name"),
			ip.insurance_coverage_plan.as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			ic.rate.as_("rate"),
			ic.rate.as_("amount"),
			pe.medical_department.as_("department"),
			ic.healthcare_practitioner.as_("practitioner"),
			pe.healthcare_service_unit.as_("service_unit"),
			ic.modified.as_("date_modified"),
		)
		.where(
			(ip.company == filters.company)
			& (ic.is_confirmed == 1)
			& ((ip.insurance_coverage_plan.isnotnull()) & (ip.insurance_coverage_plan != ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		insurance_ipd_cons_query = insurance_ipd_cons_query.where(
			(ic.date < filters.from_date) & (ip.patient_appointment.isin(appoints))
		)
	else:
		insurance_ipd_cons_query = insurance_ipd_cons_query.where(
			ic.date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		insurance_ipd_cons_query = insurance_ipd_cons_query.where(it.item_group == filters.service_type)

	if filters.payment_mode and filters.payment_mode != "Cash":
		insurance_ipd_cons_query = insurance_ipd_cons_query.where(
			ip.insurance_company == filters.payment_mode
		)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		insurance_ipd_cons_query = insurance_ipd_cons_query.where(ip.patient_appointment.isin(appoints))

	insurance_ipd_cons_data = insurance_ipd_cons_query.run(as_dict=True)

	return insurance_ipd_cons_data


def get_cash_ipd_cons_data(filters, appoints):
	ic = DocType("Inpatient Consultancy")
	ip = DocType("Inpatient Record")
	it = DocType("Item")
	pe = DocType("Patient Encounter")
	sii = DocType("Sales Invoice Item")

	# Paid IPD Cons Data for Admitted and Discharged Patients
	# Link to Sales invoice
	paid_cash_ipd_cons_query = (
		frappe.qb.from_(ic)
		.inner_join(ip)
		.on(ic.parent == ip.name)
		.inner_join(it)
		.on(ic.consultation_item == it.name)
		.inner_join(pe)
		.on(ic.encounter == pe.name)
		.inner_join(sii)
		.on(ic.name == sii.reference_dn)
		.select(
			ic.date.as_("date"),
			ip.patient_appointment.as_("appointment_no"),
			ip.name.as_("bill_no"),
			ip.patient.as_("patient"),
			ip.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			it.item_group.as_("service_type"),
			ic.consultation_item.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			ic.rate.as_("rate"),
			sii.net_amount.as_("amount"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			pe.medical_department.as_("department"),
			ic.healthcare_practitioner.as_("practitioner"),
			pe.healthcare_service_unit.as_("service_unit"),
			ic.modified.as_("date_modified"),
			sii.parent.as_("sales_invoice"),
		)
		.where(
			(ip.company == filters.company)
			& (ic.is_confirmed == 1)
			& (ic.hms_tz_invoiced == 1)
			& ((ip.insurance_coverage_plan.isnull()) | (ip.insurance_coverage_plan == ""))
			& ((sii.sales_invoice_item.isnull()) | (sii.sales_invoice_item == ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		paid_cash_ipd_cons_query = paid_cash_ipd_cons_query.where(
			(ic.date < filters.from_date) & (ip.patient_appointment.isin(appoints))
		)
	else:
		paid_cash_ipd_cons_query = paid_cash_ipd_cons_query.where(
			ic.date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		paid_cash_ipd_cons_query = paid_cash_ipd_cons_query.where(it.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		paid_cash_ipd_cons_query = paid_cash_ipd_cons_query.where(ip.patient_appointment.isin(appoints))

	paid_cash_ipd_cons_data = paid_cash_ipd_cons_query.run(as_dict=True)

	# Unpaid IPD Cons Data for Admitted and Discharged Patients
	# No Link to Sales invoice
	unpaid_cash_ipd_cons_query = (
		frappe.qb.from_(ic)
		.inner_join(ip)
		.on(ic.parent == ip.name)
		.inner_join(it)
		.on(ic.consultation_item == it.name)
		.inner_join(pe)
		.on(ic.encounter == pe.name)
		.select(
			ic.date.as_("date"),
			ip.patient_appointment.as_("appointment_no"),
			ip.name.as_("bill_no"),
			ip.patient.as_("patient"),
			ip.patient_name.as_("patient_name"),
			ValueWrapper("In-Patient").as_("patient_type"),
			it.item_group.as_("service_type"),
			ic.consultation_item.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			ValueWrapper(1).as_("qty"),
			ic.rate.as_("rate"),
			ic.rate.as_("amount"),
			pe.medical_department.as_("department"),
			ic.healthcare_practitioner.as_("practitioner"),
			pe.healthcare_service_unit.as_("service_unit"),
			ic.modified.as_("date_modified"),
			ic.sales_invoice_number.as_("sales_invoice"),
		)
		.where(
			(ip.company == filters.company)
			& (ip.status != "Discharged")
			& (ic.is_confirmed == 1)
			& (ic.hms_tz_invoiced == 0)
			& ((ip.insurance_coverage_plan.isnull()) | (ip.insurance_coverage_plan == ""))
		)
	)

	if filters.show_only_prev_items_for_discharged_ipds == 1 and len(appoints) > 0:
		unpaid_cash_ipd_cons_query = unpaid_cash_ipd_cons_query.where(
			(ic.date < filters.from_date) & (ip.patient_appointment.isin(appoints))
		)
	else:
		unpaid_cash_ipd_cons_query = unpaid_cash_ipd_cons_query.where(
			ic.date.between(filters.from_date, filters.to_date)
		)

	if filters.service_type:
		unpaid_cash_ipd_cons_query = unpaid_cash_ipd_cons_query.where(it.item_group == filters.service_type)

	if filters.show_only_ongoing_ipds == 1 and len(appoints) > 0:
		unpaid_cash_ipd_cons_query = unpaid_cash_ipd_cons_query.where(ip.patient_appointment.isin(appoints))

	unpaid_cash_ipd_cons_data = unpaid_cash_ipd_cons_query.run(as_dict=True)

	return paid_cash_ipd_cons_data + unpaid_cash_ipd_cons_data


def get_direct_sales_from_invoices(filters):
	si = DocType("Sales Invoice")
	sii = DocType("Sales Invoice Item")

	invoice_query = (
		frappe.qb.from_(si)
		.inner_join(sii)
		.on(si.name == sii.parent)
		.select(
			si.posting_date.as_("date"),
			si.name.as_("bill_no"),
			IfNull(si.patient, "Outsider Customer").as_("patient"),
			IfNull(si.patient_name, si.customer_name).as_("patient_name"),
			ValueWrapper("Out-Patient").as_("patient_type"),
			sii.item_group.as_("service_type"),
			sii.item_code.as_("service_name"),
			ValueWrapper("Cash").as_("payment_method"),
			sii.qty.as_("qty"),
			sii.rate.as_("rate"),
			sii.net_amount.as_("amount"),
			(sii.amount - sii.net_amount).as_("discount_amount"),
			ValueWrapper("Submitted").as_("status"),
			si.modified.as_("date_modified"),
			si.name.as_("sales_invoice"),
		)
		.where(
			(si.company == filters.company)
			& (si.posting_date.between(filters.from_date, filters.to_date))
			& Not(si.status.isin(["Credit Note Issued", "Return"]))
			& (si.docstatus == 1)
			& (si.is_return == 0)
			& ((sii.reference_dn.isnull()) | (sii.reference_dn == ""))
			& ((sii.sales_order.isnotnull()) & (sii.sales_order != ""))
		)
	)

	if filters.service_type:
		invoice_query = invoice_query.where(sii.item_group == filters.service_type)

	invoice_data = invoice_query.run(as_dict=True)

	return invoice_data


def get_cancelled_lab_items(filters):
	lreturn = DocType("LRPMT Returns")
	ireturn = DocType("Item Return")
	pe = DocType("Patient Encounter")
	lp = DocType("Lab Prescription")

	lab_item_query = (
		frappe.qb.from_(lreturn)
		.inner_join(ireturn)
		.on(lreturn.name == ireturn.parent)
		.inner_join(lp)
		.on(ireturn.child_name == lp.name)
		.inner_join(pe)
		.on(ireturn.encounter_no == pe.name)
		.select(
			Date(lreturn.modified).as_("date"),
			lreturn.patient.as_("patient"),
			lreturn.patient_name.as_("patient_name"),
			Case()
			.when(lreturn.inpatient_record.isnull(), "Out-Patient")
			.else_("In-Patient")
			.as_("patient_type"),
			ireturn.item_name.as_("service_name"),
			Case()
			.when(
				(pe.insurance_coverage_plan.isnull()) | (pe.insurance_coverage_plan == ""),
				"Cash",
			)
			.else_(pe.insurance_coverage_plan)
			.as_("payment_method"),
			ireturn.quantity.as_("qty"),
			lp.amount.as_("rate"),
			lp.amount.as_("amount"),
			ireturn.reference_doctype.as_("bill_doctype"),
			ireturn.reference_docname.as_("bill_no"),
			ireturn.encounter_no.as_("encounter_no"),
			ireturn.reason.as_("reason"),
			lreturn.name.as_("reference_no"),
			lreturn.appointment.as_("appointment_no"),
			lreturn.requested_by.as_("requested_by"),
			lreturn.approved_by.as_("approved_by"),
			lreturn.modified.as_("date_modified"),
		)
		.where(
			(lreturn.company == filters.company)
			& (lreturn.modified.between(filters.from_date, filters.to_date))
			& (lreturn.docstatus == 1)
			& (lp.is_cancelled == 1)
			& (ireturn.reference_doctype == "Lab Test")
			& (ireturn.encounter_no.isnotnull())
		)
	)

	if filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
		lab_item_query = lab_item_query.where(
			(pe.insurance_company == filters.get("payment_mode")) & (lp.prescribe == 0)
		)

	if filters.get("payment_mode") and filters.get("payment_mode") == "Cash":
		lab_item_query = lab_item_query.where(
			# pick only prescribed items so as to include uncovered items from
			# insurance encounters
			lp.prescribe == 1
		)

	lab_item_data = lab_item_query.run(as_dict=True)

	return lab_item_data


def get_cancelled_radiology_items(filters):
	lreturn = DocType("LRPMT Returns")
	ireturn = DocType("Item Return")
	pe = DocType("Patient Encounter")
	rpp = DocType("Radiology Procedure Prescription")

	radiology_item_query = (
		frappe.qb.from_(lreturn)
		.inner_join(ireturn)
		.on(lreturn.name == ireturn.parent)
		.inner_join(rpp)
		.on(ireturn.child_name == rpp.name)
		.inner_join(pe)
		.on(ireturn.encounter_no == pe.name)
		.select(
			Date(lreturn.modified).as_("date"),
			lreturn.patient.as_("patient"),
			lreturn.patient_name.as_("patient_name"),
			Case()
			.when(lreturn.inpatient_record.isnull(), "Out-Patient")
			.else_("In-Patient")
			.as_("patient_type"),
			ireturn.item_name.as_("service_name"),
			Case()
			.when(
				(pe.insurance_coverage_plan.isnull()) | (pe.insurance_coverage_plan == ""),
				"Cash",
			)
			.else_(pe.insurance_coverage_plan)
			.as_("payment_method"),
			ireturn.quantity.as_("qty"),
			rpp.amount.as_("rate"),
			rpp.amount.as_("amount"),
			ireturn.reference_doctype.as_("bill_doctype"),
			ireturn.reference_docname.as_("bill_no"),
			ireturn.encounter_no.as_("encounter_no"),
			ireturn.reason.as_("reason"),
			lreturn.name.as_("reference_no"),
			lreturn.appointment.as_("appointment_no"),
			lreturn.requested_by.as_("requested_by"),
			lreturn.approved_by.as_("approved_by"),
			lreturn.modified.as_("date_modified"),
		)
		.where(
			(lreturn.company == filters.company)
			& (lreturn.modified.between(filters.from_date, filters.to_date))
			& (lreturn.docstatus == 1)
			& (rpp.is_cancelled == 1)
			& (ireturn.reference_doctype == "Radiology Examination")
			& (ireturn.encounter_no.isnotnull())
		)
	)

	if filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
		radiology_item_query = radiology_item_query.where(
			(pe.insurance_company == filters.get("payment_mode")) & (rpp.prescribe == 0)
		)

	if filters.get("payment_mode") and filters.get("payment_mode") == "Cash":
		radiology_item_query = radiology_item_query.where(
			# pick only prescribed items so as to include uncovered items from
			# insurance encounters
			rpp.prescribe == 1
		)

	radiology_item_data = radiology_item_query.run(as_dict=True)

	return radiology_item_data


def get_cancelled_procedure_items(filters):
	lreturn = DocType("LRPMT Returns")
	ireturn = DocType("Item Return")
	pe = DocType("Patient Encounter")
	pp = DocType("Procedure Prescription")

	precedure_item_query = (
		frappe.qb.from_(lreturn)
		.inner_join(ireturn)
		.on(lreturn.name == ireturn.parent)
		.inner_join(pp)
		.on(ireturn.child_name == pp.name)
		.inner_join(pe)
		.on(ireturn.encounter_no == pe.name)
		.select(
			Date(lreturn.modified).as_("date"),
			lreturn.patient.as_("patient"),
			lreturn.patient_name.as_("patient_name"),
			Case()
			.when(lreturn.inpatient_record.isnull(), "Out-Patient")
			.else_("In-Patient")
			.as_("patient_type"),
			ireturn.item_name.as_("service_name"),
			Case()
			.when(
				(pe.insurance_coverage_plan.isnull()) | (pe.insurance_coverage_plan == ""),
				"Cash",
			)
			.else_(pe.insurance_coverage_plan)
			.as_("payment_method"),
			ireturn.quantity.as_("qty"),
			pp.amount.as_("rate"),
			pp.amount.as_("amount"),
			ireturn.reference_doctype.as_("bill_doctype"),
			ireturn.reference_docname.as_("bill_no"),
			ireturn.encounter_no.as_("encounter_no"),
			ireturn.reason.as_("reason"),
			lreturn.name.as_("reference_no"),
			lreturn.appointment.as_("appointment_no"),
			lreturn.requested_by.as_("requested_by"),
			lreturn.approved_by.as_("approved_by"),
			lreturn.modified.as_("date_modified"),
		)
		.where(
			(lreturn.company == filters.company)
			& (lreturn.modified.between(filters.from_date, filters.to_date))
			& (lreturn.docstatus == 1)
			& (pp.is_cancelled == 1)
			& (ireturn.reference_doctype == "Clinical Procedure")
			& (ireturn.encounter_no.isnotnull())
		)
	)
	if filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
		precedure_item_query = precedure_item_query.where(
			(pe.insurance_company == filters.get("payment_mode")) & (pp.prescribe == 0)
		)

	if filters.get("payment_mode") and filters.get("payment_mode") == "Cash":
		precedure_item_query = precedure_item_query.where(
			# pick only prescribed items so as to include uncovered items from
			# insurance encounters
			pp.prescribe == 1
		)

	procedure_item_data = precedure_item_query.run(as_dict=True)

	return procedure_item_data


def get_cancelled_drug_items(filters):
	lreturn = DocType("LRPMT Returns")
	mreturn = DocType("Medication Return")
	pe = DocType("Patient Encounter")
	dp = DocType("Drug Prescription")

	drug_item_query = (
		frappe.qb.from_(lreturn)
		.inner_join(mreturn)
		.on(lreturn.name == mreturn.parent)
		.inner_join(dp)
		.on(mreturn.child_name == dp.name)
		.inner_join(pe)
		.on(mreturn.encounter_no == pe.name)
		.select(
			Date(lreturn.modified).as_("date"),
			lreturn.patient.as_("patient"),
			lreturn.patient_name.as_("patient_name"),
			Case()
			.when(lreturn.inpatient_record.isnull(), "Out-Patient")
			.else_("In-Patient")
			.as_("patient_type"),
			mreturn.drug_name.as_("service_name"),
			Case()
			.when(
				(pe.insurance_coverage_plan.isnull()) | (pe.insurance_coverage_plan == ""),
				"Cash",
			)
			.else_(pe.insurance_coverage_plan)
			.as_("payment_method"),
			mreturn.quantity_prescribed.as_("qty"),
			dp.amount.as_("rate"),
			(mreturn.quantity_prescribed * dp.amount).as_("amount"),
			ValueWrapper("Delivery Note").as_("bill_doctype"),
			mreturn.delivery_note_no.as_("bill_no"),
			mreturn.encounter_no.as_("encounter_no"),
			mreturn.reason.as_("reason"),
			lreturn.name.as_("reference_no"),
			lreturn.appointment.as_("appointment_no"),
			lreturn.requested_by.as_("requested_by"),
			lreturn.approved_by.as_("approved_by"),
			lreturn.modified.as_("date_modified"),
		)
		.where(
			(lreturn.company == filters.company)
			& (lreturn.modified.between(filters.from_date, filters.to_date))
			& (lreturn.docstatus == 1)
			& (dp.is_cancelled == 1)
			& (mreturn.encounter_no.isnotnull())
		)
	)

	if filters.get("payment_mode") and filters.get("payment_mode") != "Cash":
		drug_item_query = drug_item_query.where(
			(pe.insurance_company == filters.get("payment_mode")) & (dp.prescribe == 0)
		)

	if filters.get("payment_mode") and filters.get("payment_mode") == "Cash":
		drug_item_query = drug_item_query.where(
			# pick only prescribed items so as to include uncovered items from
			# insurance encounters
			dp.prescribe == 1
		)

	drug_item_data = drug_item_query.run(as_dict=True)

	return drug_item_data


def get_cancelled_data(filters):
	cancelled_data = []

	if not filters.get("bill_doctype"):
		cancelled_data += get_cancelled_lab_items(filters)
		cancelled_data += get_cancelled_radiology_items(filters)
		cancelled_data += get_cancelled_procedure_items(filters)
		cancelled_data += get_cancelled_drug_items(filters)

	elif filters.get("bill_doctype") == "Lab Test":
		cancelled_data += get_cancelled_lab_items(filters)

	elif filters.get("bill_doctype") == "Radiology Examination":
		cancelled_data += get_cancelled_radiology_items(filters)

	elif filters.get("bill_doctype") == "Clinical Procedure":
		cancelled_data += get_cancelled_procedure_items(filters)

	elif filters.get("bill_doctype") == "Delivery Note":
		cancelled_data += get_cancelled_drug_items(filters)

	return cancelled_data


def get_prev_and_ongoing_ipds(filters):
	ip = DocType("Inpatient Record")
	ipd_query = (
		frappe.qb.from_(ip)
		.select(
			ip.patient_appointment.as_("patient_appointment"),
		)
		.where(ip.company == filters.company)
	)

	if filters.payment_mode and filters.payment_mode == "Cash":
		ipd_query = ipd_query.where((ip.insurance_subscription.isnull()) | (ip.insurance_subscription == ""))

	if filters.payment_mode and filters.payment_mode != "Cash":
		ipd_query = ipd_query.where(ip.insurance_company == filters.payment_mode)

	if filters.get("show_only_ongoing_ipds") == 1:
		ipd_query = ipd_query.where(
			Criterion.any(
				[
					# Get all inpatient records that are not discharged within
					# filters selected date range:
					((ip.scheduled_date <= filters.to_date) & (ip.status != "Discharged")),
					# Get all inpatient records that were discharged next month of the filters selected date range:
					# Assumption: Filters date range is always for a month
					(
						(ip.scheduled_date <= filters.to_date)
						& (ip.discharge_date > filters.to_date)
						& (ip.status == "Discharged")
					),
				]
			)
		)

	if filters.get("show_only_prev_items_for_discharged_ipds") == 1:
		ipd_query = ipd_query.where(
			(ip.scheduled_date < filters.from_date)
			& (ip.discharge_date <= filters.to_date)
			& (ip.status == "Discharged")
		)

	inpatient_records = ipd_query.run(as_dict=True)

	appoints = list(set([d.patient_appointment for d in inpatient_records]))

	return appoints


@frappe.whitelist()
def get_payment_modes(company):
	payment_modes = ["", "Cash"]
	if not company:
		return payment_modes

	insurance_companies = frappe.get_all(
		"Healthcare Insurance Company",
		filters={"company": company, "disabled": 0},
		pluck="name",
	)

	return payment_modes + sorted(insurance_companies)
