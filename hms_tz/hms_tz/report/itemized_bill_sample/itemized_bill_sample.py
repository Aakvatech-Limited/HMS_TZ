# Copyright (c) 2022, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder import functions as fn
from frappe.utils import flt
from pypika.terms import Criterion, ValueWrapper

from hms_tz.hms_tz.utils import get_union_all_query


def execute(filters=None):
	if not filters:
		return

	columns = get_columns(filters)

	data = []
	details = frappe.get_all(
		"Patient Appointment",
		filters=[
			["patient", "=", filters.patient],
			["name", "=", filters.patient_appointment],
		],
		fields=[
			"docstatus",
			"status",
		],
	)
	appointment_date = frappe.get_cached_value(
		"Patient Appointment", filters.patient_appointment, "appointment_date"
	)

	if details[0]["docstatus"] == 0 and details[0]["status"] != "Closed":
		frappe.throw(frappe.bold("This Appointment is not Closed..!!"))

	else:
		admitted_discharge_date = frappe.get_cached_value(
			"Inpatient Record",
			{"patient_appointment": filters.patient_appointment},
			[
				"admitted_datetime as admitted_date",
				"discharge_date",
				"scheduled_date",
			],
			as_dict=True,
		)

		_date = ""  # Initialize _date with an empty string
		if admitted_discharge_date:
			if admitted_discharge_date.admitted_date:
				_date = admitted_discharge_date.admitted_date.strftime("%Y-%m-%d")
			else:
				_date = admitted_discharge_date.scheduled_date

		if not filters.get("patient_type"):
			appointments_data = get_appointment_consultancy(filters)
			if appointments_data:
				data += appointments_data

			cash_lrpmt_data = get_cash_lrpmt_transaction(filters)
			if cash_lrpmt_data:
				data += cash_lrpmt_data

			insurance_lrpmt_data = get_insurance_lrpmt_transaction(filters)
			if insurance_lrpmt_data:
				data += insurance_lrpmt_data

			ipd_beds = get_ipd_occupancy_transactions(filters)
			if ipd_beds:
				data += ipd_beds

			ipd_cons = get_ipd_consultancy_transactions(filters)
			if ipd_cons:
				data += ipd_cons

			data = sorted(data, key=lambda d: (d["category"], d["date"]))

			if not data:
				frappe.throw(
					f"No Record found for the filters Patient: {frappe.bold(filters.patient)}, Appointment: {frappe.bold(filters.patient_appointment)},\
                    Patient Type: {frappe.bold(filters.patient_type)} From Date: {frappe.bold(filters.from_date)} and To Date: {frappe.bold(filters.to_date)} you specified..., \
                    Please change your filters and try again..!!"
				)

			total_amount = 0
			for n in range(0, len(data)):
				total_amount += data[n]["amount"]

			last_row = {
				"date": "Total",
				"category": "",
				"description": "",
				"quantity": "",
				"rate": "",
				"amount": total_amount,
				"patient": "",
				"patient_name": "",
				"appointment_type": "",
				"insurance_company": "",
				"coverage_plan_name": "",
				"authorization_number": "",
				"coverage_plan_card_number": "",
				"date_admitted": _date,
				"date_discharge": (admitted_discharge_date.discharge_date if admitted_discharge_date else ""),
				"appointment_date": appointment_date,
			}

			print_person = frappe.get_cached_value("User", frappe.session.user, "full_name")

			last_row["printed_by"] = print_person

			exceeded_items = get_daily_limit_exceeded_items(filters)
			if len(exceeded_items) > 0:
				last_row["limit_exceeded_items"] = exceeded_items
				last_row["total_limit_exceeded_amount"] = sum([d.amount for d in exceeded_items])
			data.append(last_row)

			return columns, data

		if filters.get("patient_type") == "Out-Patient":
			appointments_data = get_appointment_consultancy(filters)
			if appointments_data:
				data += appointments_data

			cash_lrpmt_data = get_cash_lrpmt_transaction(filters)
			if cash_lrpmt_data:
				data += cash_lrpmt_data

			insurance_lrpmt_data = get_insurance_lrpmt_transaction(filters)
			if insurance_lrpmt_data:
				data += insurance_lrpmt_data

			data = sorted(data, key=lambda d: (d["category"], d["date"]))

			if not data:
				frappe.throw(
					f"No Record found for the filters Patient: {frappe.bold(filters.patient)}, Appointment: {frappe.bold(filters.patient_appointment)},\
                    Patient Type: {frappe.bold(filters.patient_type)} From Date: {frappe.bold(filters.from_date)} and To Date: {frappe.bold(filters.to_date)} you specified..., \
                    Please change your filters and try again..!!"
				)

			total_amount = 0
			for n in range(0, len(data)):
				total_amount += data[n]["amount"]

			last_row = {
				"date": "Total",
				"category": "",
				"description": "",
				"quantity": "",
				"rate": "",
				"amount": total_amount,
				"patient": "",
				"patient_name": "",
				"appointment_type": "",
				"insurance_company": "",
				"coverage_plan_name": "",
				"authorization_number": "",
				"coverage_plan_card_number": "",
				"date_admitted": _date,
				"date_discharge": (admitted_discharge_date.discharge_date if admitted_discharge_date else ""),
				"appointment_date": appointment_date,
			}

			print_person = frappe.get_cached_value("User", frappe.session.user, "full_name")

			last_row["printed_by"] = print_person

			exceeded_items = get_daily_limit_exceeded_items(filters)
			if len(exceeded_items) > 0:
				last_row["limit_exceeded_items"] = exceeded_items
				last_row["total_limit_exceeded_amount"] = sum([d.amount for d in exceeded_items])

			data.append(last_row)

			return columns, data

		if filters.get("patient_type") == "In-Patient":
			cash_lrpmt_data = get_cash_lrpmt_transaction(filters)
			if cash_lrpmt_data:
				data += cash_lrpmt_data

			insurance_lrpmt_data = get_insurance_lrpmt_transaction(filters)
			if insurance_lrpmt_data:
				data += insurance_lrpmt_data

			ipd_beds = get_ipd_occupancy_transactions(filters)
			if ipd_beds:
				data += ipd_beds

			ipd_cons = get_ipd_consultancy_transactions(filters)
			if ipd_cons:
				data += ipd_cons

			data = sorted(data, key=lambda d: (d["category"], d["date"]))
			if not data:
				frappe.throw(
					f"No Record found for the filters Patient: {frappe.bold(filters.patient)}, Appointment: {frappe.bold(filters.patient_appointment)},\
                    Patient Type: {frappe.bold(filters.patient_type)} From Date: {frappe.bold(filters.from_date)} and To Date: {frappe.bold(filters.to_date)} you specified..., \
                    Please change your filters and try again..!!"
				)

			total_amount = 0
			for n in range(0, len(data)):
				total_amount += data[n]["amount"]

			last_row = {
				"date": "Total",
				"category": "",
				"description": "",
				"quantity": "",
				"rate": "",
				"amount": total_amount,
				"patient": "",
				"patient_name": "",
				"appointment_type": "",
				"insurance_company": "",
				"coverage_plan_name": "",
				"authorization_number": "",
				"coverage_plan_card_number": "",
				"date_admitted": _date,
				"date_discharge": (admitted_discharge_date.discharge_date if admitted_discharge_date else ""),
				"appointment_date": appointment_date,
			}

			print_person = frappe.get_cached_value("User", frappe.session.user, "full_name")

			last_row["printed_by"] = print_person

			data.append(last_row)
			# summary_view = get_report_summary(filters, total_amount)

			return columns, data  # , None, None, summary_view


def get_daily_limit_exceeded_items(filters):
	if filters.get("patient_type") == "In-Patient":
		return []

	pe = DocType("Patient Encounter")

	encounters_query = (
		frappe.qb.from_(pe)
		.select("name")
		.where(
			(pe.patient == filters.patient)
			& (pe.appointment == filters.patient_appointment)
			& (pe.inpatient_record.isnull() | pe.inpatient_record == "")
		)
	)

	if filters.get("from_date"):
		encounters_query.where(pe.encounter_date >= filters.from_date)

	if filters.get("to_date"):
		encounters_query.where(pe.encounter_date <= filters.to_date)
	encounters = [d.name for d in encounters_query.run(as_dict=True)]

	if not encounters or len(encounters) == 0:
		return []

	data = get_exceeded_lab_items(encounters)
	data += get_exceeded_radiology_items(encounters)
	data += get_exceeded_procedure_items(encounters)
	data += get_exceeded_drug_items(encounters)
	data += get_exceeded_therapy_items(encounters)
	return data


def get_exceeded_lab_items(encounters):
	lab = DocType("Lab Prescription")
	temp = DocType("Lab Test Template")
	lab_items = (
		frappe.qb.from_(lab)
		.inner_join(temp)
		.on(lab.lab_test_code == temp.name)
		.select(
			fn.Date(lab.creation).as_("date"),
			temp.lab_test_group.as_("category"),
			lab.lab_test_name.as_("description"),
			ValueWrapper(1).as_("quantity"),
			lab.amount.as_("rate"),
			lab.amount.as_("amount"),
		)
		.where((lab.prescribe == 0) & (lab.hms_tz_is_limit_exceeded == 1) & (lab.parent.isin(encounters)))
	).run(as_dict=True)
	return lab_items


def get_exceeded_radiology_items(encounters):
	rad = DocType("Radiology Procedure Prescription")
	temp = DocType("Radiology Examination Template")
	rad_items = (
		frappe.qb.from_(rad)
		.inner_join(temp)
		.on(rad.radiology_examination_template == temp.name)
		.select(
			fn.Date(rad.creation).as_("date"),
			temp.item_group.as_("category"),
			rad.radiology_procedure_name.as_("description"),
			ValueWrapper(1).as_("quantity"),
			rad.amount.as_("rate"),
			rad.amount.as_("amount"),
		)
		.where((rad.prescribe == 0) & (rad.hms_tz_is_limit_exceeded == 1) & (rad.parent.isin(encounters)))
	).run(as_dict=True)
	return rad_items


def get_exceeded_procedure_items(encounters):
	proc = DocType("Procedure Prescription")
	temp = DocType("Clinical Procedure Template")
	proc_items = (
		frappe.qb.from_(proc)
		.inner_join(temp)
		.on(proc.procedure == temp.name)
		.select(
			fn.Date(proc.creation).as_("date"),
			temp.item_group.as_("category"),
			proc.procedure_name.as_("description"),
			ValueWrapper(1).as_("quantity"),
			proc.amount.as_("rate"),
			proc.amount.as_("amount"),
		)
		.where((proc.prescribe == 0) & (proc.hms_tz_is_limit_exceeded == 1) & (proc.parent.isin(encounters)))
	).run(as_dict=True)
	return proc_items


def get_exceeded_drug_items(encounters):
	drug = DocType("Drug Prescription")
	temp = DocType("Medication")
	drug_items = (
		frappe.qb.from_(drug)
		.inner_join(temp)
		.on(drug.drug_code == temp.name)
		.select(
			fn.Date(drug.creation).as_("date"),
			temp.item_group.as_("category"),
			drug.drug_name.as_("description"),
			(drug.quantity - drug.quantity_returned).as_("quantity"),
			drug.amount.as_("rate"),
			((drug.quantity - drug.quantity_returned) * drug.amount).as_("amount"),
		)
		.where((drug.prescribe == 0) & (drug.hms_tz_is_limit_exceeded == 1) & (drug.parent.isin(encounters)))
	).run(as_dict=True)
	return drug_items


def get_exceeded_therapy_items(encounters):
	therapy = DocType("Therapy Plan Detail")
	temp = DocType("Therapy Type")
	therapy_items = (
		frappe.qb.from_(therapy)
		.inner_join(temp)
		.on(therapy.therapy_type == temp.name)
		.select(
			fn.Date(therapy.creation).as_("date"),
			temp.item_group.as_("category"),
			therapy.therapy_type.as_("description"),
			(therapy.no_of_sessions - therapy.sessions_cancelled).as_("quantity"),
			therapy.amount.as_("rate"),
			((therapy.no_of_sessions - therapy.sessions_cancelled) * therapy.amount).as_("amount"),
		)
		.where(
			(therapy.prescribe == 0)
			& (therapy.hms_tz_is_limit_exceeded == 1)
			& (therapy.parent.isin(encounters))
		)
	).run(as_dict=True)
	return therapy_items


def get_columns(filters):
	columns = [
		{"fieldname": "date", "fieldtype": "date", "label": _("Date")},
		{"fieldname": "category", "fieldtype": "Data", "label": _("Category")},
		{
			"fieldname": "description",
			"fieldtype": "Data",
			"label": _("Description"),
		},
		{"fieldname": "quantity", "fieldtype": "Data", "label": _("Quantity")},
		{"fieldname": "rate", "fieldtype": "Currency", "label": _("Rate")},
		{"fieldname": "amount", "fieldtype": "Currency", "label": _("Amount")},
	]
	return columns


def get_conditions(pa, filters):
	conditions = []
	if filters.get("patient"):
		conditions.append(pa.patient == filters.patient)

	if filters.get("patient_appointment"):
		conditions.append(pa.name == filters.patient_appointment)

	if filters.get("from_date"):
		conditions.append(pa.appointment_date >= filters.from_date)

	if filters.get("to_date"):
		conditions.append(pa.appointment_date <= filters.to_date)

	return Criterion.all(conditions)


def get_enc_conditions(pe, filters):
	conditions = []
	if filters.get("patient"):
		conditions.append(pe.patient == filters.patient)

	if filters.get("patient_appointment"):
		conditions.append(pe.appointment == filters.patient_appointment)

	if filters.get("patient_type") == "Out-Patient":
		conditions.append(pe.inpatient_record.isnull())

	if filters.get("patient_type") == "In-Patient":
		conditions.append(pe.inpatient_record.isnotnull())

	if filters.get("from_date"):
		conditions.append(pe.encounter_date >= filters.from_date)

	if filters.get("to_date"):
		conditions.append(pe.encounter_date <= filters.to_date)

	return Criterion.all(conditions)


def get_ipd_conditions(ipd_rec, filters):
	conditions = []
	if filters.get("patient"):
		conditions.append(ipd_rec.patient == filters.patient)

	if filters.get("patient_appointment"):
		conditions.append(ipd_rec.patient_appointment == filters.patient_appointment)

	if filters.get("from_date"):
		conditions.append(fn.Date(ipd_rec.admitted_datetime) >= filters.from_date)

	if filters.get("to_date"):
		conditions.append(fn.Date(ipd_rec.admitted_datetime) <= filters.to_date)

	return Criterion.all(conditions)


def get_encounters_query(filters):
	pe = DocType("Patient Encounter")
	return frappe.qb.from_(pe).select(pe.name).where(pe.docstatus == 1).where(get_enc_conditions(pe, filters))


def get_appointment_fields(pa, ipd_rec):
	return [
		pa.patient.as_("patient"),
		pa.patient_name.as_("patient_name"),
		pa.appointment_type.as_("appointment_type"),
		pa.insurance_company.as_("insurance_company"),
		pa.coverage_plan_name.as_("coverage_plan_name"),
		pa.authorization_number.as_("authorization_number"),
		pa.coverage_plan_card_number.as_("coverage_plan_card_number"),
		fn.Date(ipd_rec.admitted_datetime).as_("admitted_date"),
		ipd_rec.discharge_date.as_("discharge_date"),
	]


def get_appointment_consultancy(filters):
	pa = DocType("Patient Appointment")
	it = DocType("Item")
	ipd_rec = DocType("Inpatient Record")

	return (
		frappe.qb.from_(pa)
		.inner_join(it)
		.on(pa.billing_item == it.item_name)
		.left_join(ipd_rec)
		.on(pa.name == ipd_rec.patient_appointment)
		.select(
			pa.appointment_date.as_("date"),
			it.item_group.as_("category"),
			pa.billing_item.as_("description"),
			ValueWrapper(1).as_("quantity"),
			pa.paid_amount.as_("rate"),
			pa.paid_amount.as_("amount"),
			*get_appointment_fields(pa, ipd_rec),
		)
		.where((pa.status == "Closed") & (pa.follow_up == 0))
		.where(get_conditions(pa, filters))
	).run(as_dict=True)


def get_ipd_occupancy_transactions(filters):
	ipd_occ = DocType("Inpatient Occupancy")
	ipd_rec = DocType("Inpatient Record")
	hsu = DocType("Healthcare Service Unit")
	hsut = DocType("Healthcare Service Unit Type")
	pa = DocType("Patient Appointment")

	return (
		frappe.qb.from_(ipd_occ)
		.inner_join(ipd_rec)
		.on(ipd_occ.parent == ipd_rec.name)
		.inner_join(hsu)
		.on(ipd_occ.service_unit == hsu.name)
		.inner_join(hsut)
		.on(hsu.service_unit_type == hsut.name)
		.inner_join(pa)
		.on(ipd_rec.patient_appointment == pa.name)
		.select(
			fn.Date(ipd_occ.check_in).as_("date"),
			hsut.item_group.as_("category"),
			ipd_occ.service_unit.as_("description"),
			ValueWrapper(1).as_("quantity"),
			ipd_occ.amount.as_("rate"),
			ipd_occ.amount.as_("amount"),
			*get_appointment_fields(pa, ipd_rec),
		)
		.where(ipd_occ.is_confirmed == 1)
		.where(ipd_rec.admission_encounter.isin(get_encounters_query(filters)))
		.where(get_ipd_conditions(ipd_rec, filters))
	).run(as_dict=True)


def get_ipd_consultancy_transactions(filters):
	ipd_cons = DocType("Inpatient Consultancy")
	ipd_rec = DocType("Inpatient Record")
	pa = DocType("Patient Appointment")
	it = DocType("Item")

	return (
		frappe.qb.from_(ipd_cons)
		.inner_join(ipd_rec)
		.on(ipd_cons.parent == ipd_rec.name)
		.inner_join(pa)
		.on(ipd_rec.patient_appointment == pa.name)
		.inner_join(it)
		.on(ipd_cons.consultation_item == it.item_name)
		.select(
			ipd_cons.date.as_("date"),
			it.item_group.as_("category"),
			ipd_cons.consultation_item.as_("description"),
			ValueWrapper(1).as_("quantity"),
			ipd_cons.rate.as_("rate"),
			ipd_cons.rate.as_("amount"),
			*get_appointment_fields(pa, ipd_rec),
		)
		.where(ipd_cons.is_confirmed == 1)
		.where(ipd_cons.encounter.isin(get_encounters_query(filters)))
		.where(get_ipd_conditions(ipd_rec, filters))
	).run(as_dict=True)


def get_cash_lrpmt_transaction(filters):
	return get_lrpmt_query(filters, is_insurance=False).run(as_dict=True)


def get_insurance_lrpmt_transaction(filters):
	return get_lrpmt_query(filters, is_insurance=True).run(as_dict=True)


def get_lrpmt_query(filters, is_insurance):
	lab = DocType("Lab Prescription")
	lab_template = DocType("Lab Test Template")
	radiology = DocType("Radiology Procedure Prescription")
	radiology_template = DocType("Radiology Examination Template")
	procedure = DocType("Procedure Prescription")
	procedure_template = DocType("Clinical Procedure Template")
	drug = DocType("Drug Prescription")
	medication = DocType("Medication")
	therapy = DocType("Therapy Plan Detail")
	therapy_type = DocType("Therapy Type")
	pe = DocType("Patient Encounter")

	encounters_query = get_encounters_query(filters)
	if is_insurance:
		encounters_query = encounters_query.where(pe.insurance_coverage_plan != "")
	else:
		encounters_query = encounters_query.where(pe.mode_of_payment != "")

	drug_query = get_prescription_query(
		encounters_query,
		is_insurance,
		drug,
		medication,
		drug.drug_code,
		[
			medication.item_group.as_("category"),
			drug.drug_name.as_("description"),
			(drug.quantity - drug.quantity_returned).as_("quantity"),
			drug.amount.as_("rate"),
			((drug.quantity - drug.quantity_returned) * drug.amount).as_("amount"),
		],
	)
	if not is_insurance:
		drug_query = drug_query.where(drug.docstatus == 1)

	queries = [
		get_prescription_query(
			encounters_query,
			is_insurance,
			lab,
			lab_template,
			lab.lab_test_code,
			[
				lab_template.lab_test_group.as_("category"),
				lab.lab_test_name.as_("description"),
				ValueWrapper(1).as_("quantity"),
				lab.amount.as_("rate"),
				lab.amount.as_("amount"),
			],
		),
		get_prescription_query(
			encounters_query,
			is_insurance,
			radiology,
			radiology_template,
			radiology.radiology_examination_template,
			[
				radiology_template.item_group.as_("category"),
				radiology.radiology_procedure_name.as_("description"),
				ValueWrapper(1).as_("quantity"),
				radiology.amount.as_("rate"),
				radiology.amount.as_("amount"),
			],
		),
		get_prescription_query(
			encounters_query,
			is_insurance,
			procedure,
			procedure_template,
			procedure.procedure,
			[
				procedure_template.item_group.as_("category"),
				procedure.procedure_name.as_("description"),
				ValueWrapper(1).as_("quantity"),
				procedure.amount.as_("rate"),
				procedure.amount.as_("amount"),
			],
		),
		drug_query,
		get_prescription_query(
			encounters_query,
			is_insurance,
			therapy,
			therapy_type,
			therapy.therapy_type,
			[
				therapy_type.item_group.as_("category"),
				therapy.therapy_type.as_("description"),
				(therapy.no_of_sessions - therapy.sessions_cancelled).as_("quantity"),
				therapy.amount.as_("rate"),
				((therapy.no_of_sessions - therapy.sessions_cancelled) * therapy.amount).as_("amount"),
			],
		),
	]

	return get_union_all_query(queries)


def get_prescription_query(encounters_query, is_insurance, lrpmt, template, template_link, columns):
	pe = DocType("Patient Encounter")
	pa = DocType("Patient Appointment")
	ipd_rec = DocType("Inpatient Record")

	return (
		frappe.qb.from_(lrpmt)
		.inner_join(template)
		.on(template_link == template.name)
		.inner_join(pe)
		.on(lrpmt.parent == pe.name)
		.inner_join(pa)
		.on(pe.appointment == pa.name)
		.left_join(ipd_rec)
		.on((pa.name == ipd_rec.patient_appointment) & (pe.name == ipd_rec.admission_encounter))
		.select(
			fn.Date(lrpmt.creation).as_("date"),
			*columns,
			*get_appointment_fields(pa, ipd_rec),
		)
		.where(lrpmt.prescribe == (0 if is_insurance else 1))
		.where((lrpmt.is_not_available_inhouse == 0) & (lrpmt.is_cancelled == 0))
		.where(lrpmt.parent.isin(encounters_query))
	)


def get_report_summary(filters, total_amount):
	customer = frappe.get_cached_value("Patient", filters.get("patient"), "customer")
	company = frappe.get_cached_value("Patient Appointment", filters.get("patient_appointment"), "company")

	deposit_balance = -1 * get_balance_on(party_type="Customer", party=customer, company=company)

	current_balance = flt(flt(deposit_balance) - flt(total_amount))

	currency = frappe.get_cached_value("Company", company, "default_currency")

	return [
		{
			"value": deposit_balance,
			"label": _("Total Deposited Amount"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_amount,
			"label": _("Total Amount Used"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": current_balance,
			"label": _("Current Balance"),
			"datatype": "Currency",
			"currency": currency,
		},
	]
