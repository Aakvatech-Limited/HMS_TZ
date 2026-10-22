import frappe
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Date, Sum
from frappe.utils import flt
from pypika.terms import Criterion, ValueWrapper

from hms_tz.hms_tz.utils import get_union_all_query


def execute(filters=None):
	args = frappe._dict(filters or {})
	if not args.patient:
		frappe.throw(_("Patient is required"))

	if filters.get("summarized_view") == 1:
		columns = get_summarized_columns()
		data, dashboard = get_summarized_data(args)
	else:
		columns = get_columns()
		data, dashboard = get_data(args)

	if not data:
		frappe.msgprint(
			_(
				"No records found for Patient: {0}, Appointment: {1}, Patient Type: {2}, From Date: {3} and To Date: {4}. Change the filters and try again."
			).format(
				frappe.bold(args.patient),
				frappe.bold(args.appointment_no),
				frappe.bold(args.patient_type),
				frappe.bold(args.from_date),
				frappe.bold(args.to_date),
			)
		)

	return columns, data, None, None, dashboard


def get_summarized_columns():
	columns = [
		{
			"fieldname": "date",
			"fieldtype": "date",
			"label": _("Date"),
			"width": 120,
		},
		{
			"fieldname": "service_unit",
			"fieldtype": "Data",
			"label": _("Service Unit"),
			"width": 120,
		},
		{
			"fieldname": "total_bed_charges",
			"fieldtype": "Currency",
			"label": _("Bed Charges"),
			"width": 120,
		},
		{
			"fieldname": "total_cons_charges",
			"fieldtype": "Currency",
			"label": _("Consultation Charges"),
			"width": 120,
		},
		{
			"fieldname": "total_lab_amount",
			"fieldtype": "Currency",
			"label": _("Lab Amount"),
			"width": 120,
		},
		{
			"fieldname": "total_radiology_amount",
			"fieldtype": "Currency",
			"label": _("Radiology Amount"),
			"width": 120,
		},
		{
			"fieldname": "total_procedure_amount",
			"fieldtype": "Currency",
			"label": _("Procedure Amount"),
			"width": 120,
		},
		{
			"fieldname": "total_drug_amount",
			"fieldtype": "Currency",
			"label": _("Medication Amount"),
			"width": 120,
		},
		{
			"fieldname": "total_therapy_amount",
			"fieldtype": "Currency",
			"label": _("Therapies Amount"),
			"width": 120,
		},
		{
			"fieldname": "total_consumable_amount",
			"fieldtype": "Currency",
			"label": _("Consumable Amount"),
			"width": 120,
		},
		{
			"fieldname": "total_amount",
			"fieldtype": "Currency",
			"label": _("Amount Used Per Day"),
			"width": 120,
		},
	]

	return columns


# itemized col report
def get_columns():
	columns = [
		{
			"fieldname": "date",
			"fieldtype": "date",
			"label": _("Date"),
			"width": 140,
		},
		{
			"fieldname": "category",
			"fieldtype": "Data",
			"label": _("Category"),
			"width": 170,
		},
		{
			"fieldname": "description",
			"fieldtype": "Data",
			"label": _("Description"),
			"width": 200,
		},
		{
			"fieldname": "quantity",
			"fieldtype": "Data",
			"label": _("Quantity"),
			"width": 100,
		},
		{
			"fieldname": "rate",
			"fieldtype": "Currency",
			"label": _("Rate"),
			"width": 130,
		},
		{
			"fieldname": "total_amount",
			"fieldtype": "Currency",
			"label": _("Amount"),
			"width": 130,
		},
	]
	return columns


def get_summarized_data(args):
	service_list = []
	date_list = []
	single_transaction_per_day = []
	mult_transaction_per_day = []

	transactions = get_transaction_data(args)
	if len(transactions) == 0:
		return [], []

	for record in transactions:
		total_amount = (
			flt(record["bed_charges"])
			+ flt(record["cons_charges"])
			+ flt(record["lab_amount"])
			+ flt(record["radiology_amount"])
			+ flt(record["procedure_amount"])
			+ flt(record["drug_amount"])
			+ flt(record["therapy_amount"])
			+ flt(record["consumable_amount"])
		)

		date_d = record["date"].strftime("%Y-%m-%d")
		if date_d not in date_list:
			date_list.append(date_d)
			record.update({"total_amount": total_amount})
			single_transaction_per_day.append(record)
		else:
			record.update({"total_amount": total_amount})
			mult_transaction_per_day.append(record)

	for single_transaction in single_transaction_per_day:
		service_unit = ""
		mult_bed_charges = 0
		mult_cons_charges = 0
		mult_lab_amount = 0
		mult_radiology_amount = 0
		mult_procedure_amount = 0
		mult_drug_amount = 0
		mult_therapy_amount = 0
		mult_consumable_amount = 0
		mult_total_amount = 0

		single_transaction_date = single_transaction["date"].strftime("%Y-%m-%d")

		for mult_transaction in mult_transaction_per_day:
			mult_transaction_date = mult_transaction["date"].strftime("%Y-%m-%d")

			if single_transaction_date == mult_transaction_date:
				mult_bed_charges += flt(mult_transaction["bed_charges"])
				mult_cons_charges += flt(mult_transaction["cons_charges"])
				mult_lab_amount += flt(mult_transaction["lab_amount"])
				mult_radiology_amount += flt(mult_transaction["radiology_amount"])
				mult_procedure_amount += flt(mult_transaction["procedure_amount"])
				mult_drug_amount += flt(mult_transaction["drug_amount"])
				mult_therapy_amount += flt(mult_transaction["therapy_amount"])
				mult_consumable_amount += flt(mult_transaction["consumable_amount"])
				mult_total_amount += flt(mult_transaction["total_amount"])

				service_unit += mult_transaction["service_unit"]

		service_list.append(
			{
				"date": single_transaction_date,
				"service_unit": single_transaction["service_unit"] or service_unit,
				"total_bed_charges": flt(single_transaction["bed_charges"]) + mult_bed_charges,
				"total_cons_charges": flt(single_transaction["cons_charges"]) + mult_cons_charges,
				"total_lab_amount": flt(single_transaction["lab_amount"]) + mult_lab_amount,
				"total_radiology_amount": flt(single_transaction["radiology_amount"]) + mult_radiology_amount,
				"total_procedure_amount": flt(single_transaction["procedure_amount"]) + mult_procedure_amount,
				"total_drug_amount": flt(single_transaction["drug_amount"]) + mult_drug_amount,
				"total_therapy_amount": flt(single_transaction["therapy_amount"]) + mult_therapy_amount,
				"total_consumable_amount": flt(single_transaction["consumable_amount"])
				+ mult_consumable_amount,
				"total_amount": flt(single_transaction["total_amount"]) + mult_total_amount,
			}
		)

	return get_report_summary(args, service_list, is_summary=True)


TRANSACTION_COLUMNS = (
	"lab_amount",
	"radiology_amount",
	"procedure_amount",
	"drug_amount",
	"therapy_amount",
	"date",
	"service_unit",
	"bed_charges",
	"cons_charges",
	"consumable_amount",
)


def get_transaction_data(args):
	lab = DocType("Lab Prescription")
	radiology = DocType("Radiology Procedure Prescription")
	procedure = DocType("Procedure Prescription")
	drug = DocType("Drug Prescription")
	therapy = DocType("Therapy Plan Detail")

	queries = [
		get_encounter_service_query(args, lab, "lab_amount", Sum(lab.amount)),
		get_encounter_service_query(args, radiology, "radiology_amount", Sum(radiology.amount)),
		get_encounter_service_query(args, procedure, "procedure_amount", Sum(procedure.amount)),
		get_encounter_service_query(
			args, drug, "drug_amount", Sum(drug.amount * (drug.quantity - drug.quantity_returned))
		),
		get_encounter_service_query(
			args,
			therapy,
			"therapy_amount",
			Sum(therapy.amount * (therapy.no_of_sessions - therapy.sessions_cancelled)),
		),
		get_occupancy_charges_query(args),
		get_consultancy_charges_query(args),
		get_consumable_amount_query(args),
	]

	return get_union_all_query(queries).run(as_dict=True)


def get_transaction_columns(columns):
	values = {column: ValueWrapper(0) for column in TRANSACTION_COLUMNS}
	values["service_unit"] = ValueWrapper("")
	values.update(columns)

	return [value.as_(column) for column, value in values.items()]


def get_encounter_service_query(args, service, amount_column, amount):
	encounter = DocType("Patient Encounter")

	return (
		frappe.qb.from_(service)
		.inner_join(encounter)
		.on(service.parent == encounter.name)
		.select(*get_transaction_columns({amount_column: amount, "date": Date(encounter.encounter_date)}))
		.where(encounter.inpatient_record == args.get("inpatient_record"))
		.where(encounter.appointment == args.get("appointment_no"))
		.where(encounter.patient == args.get("patient"))
		.where(encounter.company == args.get("company"))
		.where(encounter.docstatus == 1)
		.where(service.prescribe == 1)
		.where(service.is_not_available_inhouse == 0)
		.where(service.is_cancelled == 0)
		.where(service.invoiced == 0)
		.groupby(Date(encounter.encounter_date))
	)


def get_occupancy_charges_query(args):
	occupancy = DocType("Inpatient Occupancy")
	columns = {
		"date": Date(occupancy.check_in),
		"service_unit": occupancy.service_unit,
		"bed_charges": Sum(occupancy.amount),
	}

	return (
		frappe.qb.from_(occupancy)
		.select(*get_transaction_columns(columns))
		.where(occupancy.is_confirmed == 1)
		.where(occupancy.invoiced == 0)
		.where(occupancy.parent == args.get("inpatient_record"))
		.groupby(Date(occupancy.check_in))
	)


def get_consultancy_charges_query(args):
	consultancy = DocType("Inpatient Consultancy")
	columns = {"date": Date(consultancy.date), "cons_charges": Sum(consultancy.rate)}

	return (
		frappe.qb.from_(consultancy)
		.select(*get_transaction_columns(columns))
		.where(consultancy.is_confirmed == 1)
		.where(consultancy.hms_tz_invoiced == 0)
		.where(consultancy.parent == args.get("inpatient_record"))
		.groupby(Date(consultancy.date))
	)


def get_consumable_amount_query(args):
	item = DocType("Consumable Item")
	record = DocType("Consumable Record")
	columns = {"date": Date(record.posting_date), "consumable_amount": Sum(item.amount)}

	return (
		frappe.qb.from_(item)
		.inner_join(record)
		.on(item.parent == record.name)
		.select(*get_transaction_columns(columns))
		.where(record.docstatus == 1)
		.where(record.payment_type == "Cash")
		.where(item.invoiced == 0)
		.where(record.inpatient_record == args.get("inpatient_record"))
		.groupby(Date(record.posting_date))
	)


def get_report_summary(args, summary_data, is_summary=False):
	customer = frappe.get_cached_value("Patient", {"name": args.patient}, "customer")
	cash_limit = frappe.get_cached_value("Inpatient Record", args.inpatient_record, "cash_limit")

	deposit_balance = get_balance_on(party_type="Customer", party=customer, company=args.company)
	sorted_data = sorted(summary_data, key=lambda x: x["date"])

	total_amount_used = 0
	for entry in sorted_data:
		total_amount_used += entry["total_amount"]

	total_deposited_amount = -1 * deposit_balance
	current_balance = total_deposited_amount - total_amount_used

	if is_summary:
		total_beds = 0
		total_cons = 0
		total_labs = 0
		total_radiology = 0
		total_procedure = 0
		total_drug = 0
		total_therapy = 0
		total_consumable = 0
		total_amount = 0

		sorted_data = sorted(summary_data, key=lambda x: x["date"])

		for n in range(0, len(sorted_data)):
			total_beds += sorted_data[n]["total_bed_charges"]
			total_cons += sorted_data[n]["total_cons_charges"]
			total_labs += sorted_data[n]["total_lab_amount"]
			total_radiology += sorted_data[n]["total_radiology_amount"]
			total_procedure += sorted_data[n]["total_procedure_amount"]
			total_drug += sorted_data[n]["total_drug_amount"]
			total_therapy += sorted_data[n]["total_therapy_amount"]
			total_consumable += sorted_data[n]["total_consumable_amount"]
			total_amount += sorted_data[n]["total_amount"]

		sorted_data.append(
			{
				"date": "Total",
				"service_unit": "",
				"total_bed_charges": total_beds,
				"total_cons_charges": total_cons,
				"total_lab_amount": total_labs,
				"total_radiology_amount": total_radiology,
				"total_procedure_amount": total_procedure,
				"total_drug_amount": total_drug,
				"total_therapy_amount": total_therapy,
				"total_consumable_amount": total_consumable,
				"total_amount": total_amount,
				"total_deposited_amount": total_deposited_amount,
				"total_amount_used": total_amount_used,
				"current_balance": current_balance,
				"printed_by": frappe.utils.get_fullname(frappe.session.user),
			}
		)

	if not is_summary:
		last_row = {
			"date": "Total",
			"category": "",
			"description": "",
			"quantity": "",
			"rate": "",
			"total_amount": total_amount_used,
			"patient": "",
			"patient_name": "",
			"appointment_type": "",
			"insurance_company": "",
			"coverage_plan_name": "",
			"authorization_number": "",
			"coverage_plan_card_number": "",
			"admitted_date": "",
			"discharge_date": "",
		}
		last_row["printed_by"] = frappe.utils.get_fullname(frappe.session.user)
		last_row["total_deposited_amount"] = total_deposited_amount
		last_row["total_amount_used"] = total_amount_used
		last_row["current_balance"] = current_balance
		sorted_data.append(last_row)

	currency = frappe.get_cached_value("Company", args.company, "default_currency")

	return sorted_data, [
		{
			"value": cash_limit,
			"label": _("Current Cash Limit"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_deposited_amount,
			"label": _("Total Deposited Amount"),
			"datatype": "Currency",
			"currency": currency,
			"color": "blue",
		},
		{
			"value": total_amount_used,
			"label": _("Total Amount Used"),
			"datatype": "Currency",
			"currency": currency,
			"color": "blue",
		},
		{
			"value": current_balance,
			"label": _("Current Balance"),
			"datatype": "Currency",
			"currency": currency,
			"color": "blue",
		},
	]


# itemized data report for only ipd items
def get_data(args):
	data = []
	if args.get("patient_type") == "In-Patient":
		cash_lrpmt_data = get_cash_lrpmt_transaction(args)
		if len(cash_lrpmt_data) > 0:
			data += cash_lrpmt_data

		ipd_beds = get_ipd_occupancy_transactions(args)
		if len(ipd_beds) > 0:
			data += ipd_beds
		ipd_cons = get_ipd_consultancy_transactions(args)
		if len(ipd_cons) > 0:
			data += ipd_cons
		consumables = get_consumable_transactions(args)
		if len(consumables) > 0:
			data += consumables

	if len(data) == 0:
		return [], []

	return get_report_summary(args, data, is_summary=False)


def get_enc_conditions(filters, encounter):
	conditions = []
	if filters.get("patient"):
		conditions.append(encounter.patient == filters.get("patient"))

	if filters.get("appointment_no"):
		conditions.append(encounter.appointment == filters.get("appointment_no"))

	if filters.get("patient_type") == "Out-Patient":
		conditions.append(encounter.inpatient_record.isnull())

	if filters.get("patient_type") == "In-Patient":
		conditions.append(encounter.inpatient_record.isnotnull())

	if filters.get("from_date"):
		conditions.append(encounter.encounter_date >= filters.get("from_date"))

	if filters.get("to_date"):
		conditions.append(encounter.encounter_date <= filters.get("to_date"))

	return Criterion.all(conditions)


def get_ipd_conditions(filters, inpatient_record):
	conditions = []
	if filters.get("patient"):
		conditions.append(inpatient_record.patient == filters.get("patient"))

	if filters.get("appointment_no"):
		conditions.append(inpatient_record.patient_appointment == filters.get("appointment_no"))

	if filters.get("from_date"):
		conditions.append(Date(inpatient_record.admitted_datetime) >= filters.get("from_date"))

	if filters.get("to_date"):
		conditions.append(Date(inpatient_record.admitted_datetime) <= filters.get("to_date"))

	return Criterion.all(conditions)


def get_consumable_conditions(filters, record):
	conditions = []
	if filters.get("patient"):
		conditions.append(record.patient == filters.get("patient"))

	if filters.get("appointment_no"):
		conditions.append(record.appointment == filters.get("appointment_no"))

	if filters.get("from_date"):
		conditions.append(record.posting_date >= filters.get("from_date"))

	if filters.get("to_date"):
		conditions.append(record.posting_date <= filters.get("to_date"))

	return Criterion.all(conditions)


def get_encounter_subquery(filters):
	encounter = DocType("Patient Encounter")
	return (
		frappe.qb.from_(encounter)
		.select(encounter.name)
		.where(encounter.docstatus == 1)
		.where(get_enc_conditions(filters, encounter))
	)


def get_appointment_columns(appointment, inpatient_record):
	return [
		appointment.patient.as_("patient"),
		appointment.patient_name.as_("patient_name"),
		appointment.appointment_type.as_("appointment_type"),
		appointment.insurance_company.as_("insurance_company"),
		appointment.coverage_plan_name.as_("coverage_plan_name"),
		appointment.authorization_number.as_("authorization_number"),
		appointment.coverage_plan_card_number.as_("coverage_plan_card_number"),
		Date(inpatient_record.admitted_datetime).as_("admitted_date"),
		inpatient_record.discharge_date.as_("discharge_date"),
	]


def get_ipd_occupancy_transactions(filters):
	occupancy = DocType("Inpatient Occupancy")
	inpatient_record = DocType("Inpatient Record")
	service_unit = DocType("Healthcare Service Unit")
	service_unit_type = DocType("Healthcare Service Unit Type")
	appointment = DocType("Patient Appointment")

	return (
		frappe.qb.from_(occupancy)
		.inner_join(inpatient_record)
		.on(occupancy.parent == inpatient_record.name)
		.inner_join(service_unit)
		.on(occupancy.service_unit == service_unit.name)
		.inner_join(service_unit_type)
		.on(service_unit.service_unit_type == service_unit_type.name)
		.inner_join(appointment)
		.on(inpatient_record.patient_appointment == appointment.name)
		.select(
			Date(occupancy.check_in).as_("date"),
			service_unit_type.item_group.as_("category"),
			occupancy.service_unit.as_("description"),
			ValueWrapper(1).as_("quantity"),
			occupancy.amount.as_("rate"),
			occupancy.amount.as_("total_amount"),
			*get_appointment_columns(appointment, inpatient_record),
		)
		.where(occupancy.is_confirmed == 1)
		.where(occupancy.invoiced == 0)
		.where(inpatient_record.admission_encounter.isin(get_encounter_subquery(filters)))
		.where(get_ipd_conditions(filters, inpatient_record))
		.run(as_dict=True)
	)


def get_ipd_consultancy_transactions(filters):
	consultancy = DocType("Inpatient Consultancy")
	inpatient_record = DocType("Inpatient Record")
	appointment = DocType("Patient Appointment")
	item = DocType("Item")

	return (
		frappe.qb.from_(consultancy)
		.inner_join(inpatient_record)
		.on(consultancy.parent == inpatient_record.name)
		.inner_join(appointment)
		.on(inpatient_record.patient_appointment == appointment.name)
		.inner_join(item)
		.on(consultancy.consultation_item == item.item_name)
		.select(
			consultancy.date.as_("date"),
			item.item_group.as_("category"),
			consultancy.consultation_item.as_("description"),
			ValueWrapper(1).as_("quantity"),
			consultancy.rate.as_("rate"),
			consultancy.rate.as_("total_amount"),
			*get_appointment_columns(appointment, inpatient_record),
		)
		.where(consultancy.is_confirmed == 1)
		.where(consultancy.hms_tz_invoiced == 0)
		.where(consultancy.encounter.isin(get_encounter_subquery(filters)))
		.where(get_ipd_conditions(filters, inpatient_record))
		.run(as_dict=True)
	)


def get_consumable_transactions(filters):
	"""Fetch non-invoiced consumable items for cash IPD patients."""
	item = DocType("Consumable Item")
	record = DocType("Consumable Record")
	inpatient_record = DocType("Inpatient Record")
	appointment = DocType("Patient Appointment")

	return (
		frappe.qb.from_(item)
		.inner_join(record)
		.on(item.parent == record.name)
		.inner_join(inpatient_record)
		.on(record.inpatient_record == inpatient_record.name)
		.inner_join(appointment)
		.on(inpatient_record.patient_appointment == appointment.name)
		.select(
			record.posting_date.as_("date"),
			ValueWrapper("Consumables").as_("category"),
			item.item_name.as_("description"),
			item.qty_requested.as_("quantity"),
			item.rate.as_("rate"),
			item.amount.as_("total_amount"),
			*get_appointment_columns(appointment, inpatient_record),
		)
		.where(record.docstatus == 1)
		.where(record.payment_type == "Cash")
		.where(item.invoiced == 0)
		.where(item.is_billable == 1)
		.where(get_consumable_conditions(filters, record))
		.run(as_dict=True)
	)


def get_cash_lrpmt_transaction(filters):
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
	encounter = DocType("Patient Encounter")

	encounters = get_encounter_subquery(filters).where(encounter.mode_of_payment != "")

	queries = [
		get_prescription_query(
			encounters,
			lab,
			lab_template,
			lab.lab_test_code,
			[
				lab_template.lab_test_group.as_("category"),
				lab.lab_test_name.as_("description"),
				ValueWrapper(1).as_("quantity"),
				lab.amount.as_("rate"),
				lab.amount.as_("total_amount"),
			],
		),
		get_prescription_query(
			encounters,
			radiology,
			radiology_template,
			radiology.radiology_examination_template,
			[
				radiology_template.item_group.as_("category"),
				radiology.radiology_procedure_name.as_("description"),
				ValueWrapper(1).as_("quantity"),
				radiology.amount.as_("rate"),
				radiology.amount.as_("total_amount"),
			],
		),
		get_prescription_query(
			encounters,
			procedure,
			procedure_template,
			procedure.procedure,
			[
				procedure_template.item_group.as_("category"),
				procedure.procedure_name.as_("description"),
				ValueWrapper(1).as_("quantity"),
				procedure.amount.as_("rate"),
				procedure.amount.as_("total_amount"),
			],
		),
		get_prescription_query(
			encounters,
			drug,
			medication,
			drug.drug_code,
			[
				medication.item_group.as_("category"),
				drug.drug_name.as_("description"),
				(drug.quantity - drug.quantity_returned).as_("quantity"),
				drug.amount.as_("rate"),
				((drug.quantity - drug.quantity_returned) * drug.amount).as_("total_amount"),
			],
		),
		get_prescription_query(
			encounters,
			therapy,
			therapy_type,
			therapy.therapy_type,
			[
				therapy_type.item_group.as_("category"),
				therapy.therapy_type.as_("description"),
				(therapy.no_of_sessions - therapy.sessions_cancelled).as_("quantity"),
				therapy.amount.as_("rate"),
				((therapy.no_of_sessions - therapy.sessions_cancelled) * therapy.amount).as_("total_amount"),
			],
		),
	]

	return get_union_all_query(queries).run(as_dict=True)


def get_prescription_query(encounters, prescription, template, template_link, columns):
	encounter = DocType("Patient Encounter")
	appointment = DocType("Patient Appointment")
	inpatient_record = DocType("Inpatient Record")

	return (
		frappe.qb.from_(prescription)
		.inner_join(template)
		.on(template_link == template.name)
		.inner_join(encounter)
		.on(prescription.parent == encounter.name)
		.inner_join(appointment)
		.on(encounter.appointment == appointment.name)
		.left_join(inpatient_record)
		.on(
			(appointment.name == inpatient_record.patient_appointment)
			& (encounter.name == inpatient_record.admission_encounter)
		)
		.select(
			Date(prescription.creation).as_("date"),
			*columns,
			*get_appointment_columns(appointment, inpatient_record),
		)
		.where(prescription.prescribe == 1)
		.where(prescription.is_cancelled == 0)
		.where(prescription.is_not_available_inhouse == 0)
		.where(prescription.invoiced == 0)
		.where(prescription.parent.isin(encounters))
	)
