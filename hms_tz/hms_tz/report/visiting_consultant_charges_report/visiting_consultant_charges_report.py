import frappe
from frappe import _
from frappe.query_builder import DocType as dt
from frappe.query_builder.functions import Count, Sum
from frappe.utils import flt
from pypika import Case


def execute(filters=None):
	if not filters:
		return

	data = []

	(
		commission_doc,
		excluded_services_map,
		vc_lab_users,
		vc_radiology_users,
		vc_practitioners,
	) = get_commission_doc_details(filters)

	data += get_opd_commissions(
		filters,
		commission_doc.cash_rates,
		commission_doc.insurance_rates,
		vc_practitioners,
		commission_doc.practitioners,
	)
	data += get_procedure_commissions(
		filters,
		commission_doc.cash_rates,
		commission_doc.insurance_rates,
		excluded_services_map,
		vc_practitioners,
		commission_doc.practitioners,
	)
	data += get_lab_commissions(
		filters,
		commission_doc.cash_rates,
		commission_doc.insurance_rates,
		excluded_services_map,
		vc_lab_users,
		commission_doc.lab_users,
	)
	data += get_radiology_commissions(
		filters,
		commission_doc.cash_rates,
		commission_doc.insurance_rates,
		excluded_services_map,
		vc_radiology_users,
		commission_doc.radiology_users,
	)
	if len(data) == 0:
		frappe.msgprint("No records found")
		return []

	columns = get_columns(filters)
	dashboard = get_report_summary(filters, data)

	return columns, data, None, None, dashboard


def get_columns(filters):
	columns = []
	if filters.get("practitioner") and not filters.get("vc_technician"):
		columns.append(
			{
				"fieldname": "practitioner",
				"fieldtype": "Data",
				"label": _("Healthcare Practitioner"),
				"width": "150px",
			}
		)
	elif filters.get("vc_technician") and not filters.get("practitioner"):
		columns.append(
			{
				"fieldname": "vc_technician",
				"fieldtype": "Data",
				"label": _("VC Technician"),
				"width": "150px",
			}
		)
	else:
		columns += [
			{
				"fieldname": "practitioner",
				"fieldtype": "Data",
				"label": _("Healthcare Practitioner"),
				"width": "150px",
			},
			{
				"fieldname": "vc_technician",
				"fieldtype": "Data",
				"label": _("VC Technician"),
				"width": "150px",
			},
		]
	columns += [
		{
			"fieldname": "billing_item",
			"fieldtype": "Data",
			"label": _("Item"),
			"width": "150px",
		},
		{
			"fieldname": "patient_count",
			"fieldtype": "Int",
			"label": _("Patient Count"),
			"width": "90px",
		},
		{
			"fieldname": "item_count",
			"fieldtype": "Int",
			"label": _("Item Count"),
			"width": "90px",
		},
		{
			"fieldname": "mode",
			"fieldtype": "Data",
			"label": _("Mode"),
			"width": "150px",
		},
		{
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"label": _("Paid Amount"),
			"width": "120px",
		},
		{
			"fieldname": "company_amount",
			"fieldtype": "Currency",
			"label": _("Company Amount"),
			"width": "120px",
		},
		{
			"fieldname": "vc_amount",
			"fieldtype": "Currency",
			"label": _("Vc Amount"),
			"width": "120px",
		},
		{
			"fieldname": "vc_wtax_amount",
			"fieldtype": "Currency",
			"label": _("Vc Wtax Amount"),
			"width": "120px",
		},
		{
			"fieldname": "vc_net_amount",
			"fieldtype": "Currency",
			"label": _("Vc Net Amount"),
			"width": "120px",
		},
	]
	return columns


def get_commission_doc_details(filters):
	vc_lab_users = []
	vc_radiology_users = []
	vc_practitioners = []

	commission_list = frappe.get_all(
		"Visiting Comission",
		filters={
			"company": filters.get("company"),
			"valid_from": ["<=", filters.get("to_date")],
		},
		fields=["name"],
		order_by="valid_from desc",
		limit=1,
	)
	commission_doc = frappe.get_cached_doc("Visiting Comission", commission_list[0].name)
	excluded_services_map = {}
	for row in commission_doc.excluded_service_rates:
		excluded_services_map.setdefault(row.document_type, []).append(row)

	vc_lab_users = [row.user_field for row in commission_doc.lab_users]
	vc_radiology_users = [row.user_field for row in commission_doc.radiology_users]
	vc_practitioners = [row.healathcare_practitioner for row in commission_doc.practitioners]

	return (
		commission_doc,
		excluded_services_map,
		vc_lab_users,
		vc_radiology_users,
		vc_practitioners,
	)


def get_opd_commissions(filters, cash_rates, insurance_rates, vc_practitioners, practitioner_list):
	if filters.get("vc_technician"):
		return []

	appointment = dt("Patient Appointment")
	encounter = dt("Patient Encounter")
	case_wh = None
	if filters.get("practitioner"):
		case_wh = appointment.practitioner == filters.get("practitioner")
	else:
		case_wh = appointment.practitioner.isnotnull()

	appointment_records = (
		frappe.qb.from_(appointment)
		.inner_join(encounter)
		.on(appointment.name == encounter.appointment)
		.select(
			appointment.practitioner,
			appointment.billing_item,
			appointment.coverage_plan_name,
			appointment.insurance_subscription,
			appointment.paid_amount,
			Sum(appointment.paid_amount).as_("amount"),
			Count(appointment.patient).distinct().as_("patient_count"),
			Count(appointment.billing_item).as_("item_count"),
			Case()
			.when(
				appointment.insurance_subscription != "",
				appointment.coverage_plan_name,
			)
			.else_("CASH")
			.as_("mode"),
		)
		.where(
			(appointment.status == "Closed")
			& (appointment.follow_up == 0)
			& (encounter.follow_up == 0)
			& (encounter.duplicated == 0)
			& (encounter.encounter_type == "Final")
		)
		.where(
			(appointment.appointment_date >= filters.get("from_date"))
			& (appointment.appointment_date <= filters.get("to_date"))
			& (appointment.company == filters.get("company"))
			& (appointment.practitioner == encounter.practitioner)
			& case_wh
		)
		.groupby(
			Case()
			.when(
				appointment.insurance_subscription != "",
				appointment.coverage_plan_name,
			)
			.else_("CASH")
			.as_("mode"),
			appointment.practitioner,
			appointment.billing_item,
		)
	).run(as_dict=1)

	appointment_list = []
	for row in appointment_records:
		if row.practitioner not in vc_practitioners:
			continue

		if row.mode == "CASH":
			for rate_row in cash_rates:
				if rate_row.document_type == "Patient Appointment":
					for prac in practitioner_list:
						if row.practitioner == prac.healathcare_practitioner:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (prac.wtax / 100)
							appointment_list.append(
								{
									"practitioner": row.practitioner,
									"vc_technician": "",
									"billing_item": row.billing_item,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

		elif row.mode != "CASH":
			coverage_plan = frappe.get_cached_value(
				"Healthcare Insurance Coverage Plan",
				{"coverage_plan_name": row.mode},
				"name",
			)
			for rate_row in insurance_rates:
				if (
					rate_row.coverage_plan == coverage_plan
					and rate_row.document_type == "Patient Appointment"
				):
					for prac in practitioner_list:
						if row.practitioner == prac.healathcare_practitioner:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (prac.wtax / 100)
							appointment_list.append(
								{
									"practitioner": row.practitioner,
									"vc_technician": "",
									"billing_item": row.billing_item,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

	return appointment_list


def get_lab_commissions(
	filters,
	cash_rates,
	insurance_rates,
	excluded_services_map,
	vc_lab_users,
	lab_tech_list,
):
	if filters.get("practitioner"):
		return []

	lab = dt("Lab Test")
	prescription = dt("Lab Prescription")
	case_wh = None
	if filters.get("vc_technician"):
		case_wh = lab.hms_tz_user_id == filters.get("vc_technician")
	else:
		case_wh = lab.hms_tz_user_id.isnotnull()

	lab_records = (
		frappe.qb.from_(lab)
		.inner_join(prescription)
		.on(
			lab.hms_tz_ref_childname == prescription.name
			and lab.ref_docname == prescription.parent
			and lab.template == prescription.lab_test_code
		)
		.select(
			lab.template,
			lab.hms_tz_submitted_by,
			lab.hms_tz_user_id,
			prescription.prescribe,
			Sum(prescription.amount).as_("amount"),
			Count(lab.patient).distinct().as_("patient_count"),
			Count(lab.template).as_("item_count"),
			Case()
			.when(prescription.prescribe == 0, lab.hms_tz_insurance_coverage_plan)
			.else_("CASH")
			.as_("mode"),
		)
		.where(
			(lab.ref_doctype == "Patient Encounter")
			& (lab.ref_docname == prescription.parent)
			& (lab.hms_tz_ref_childname == prescription.name)
			& (lab.submitted_date >= filters.get("from_date"))
			& (lab.submitted_date <= filters.get("to_date"))
			& (lab.company == filters.get("company"))
			& (prescription.is_cancelled == 0)
			& (lab.docstatus == 1)
			& case_wh
		)
		.groupby(
			Case()
			.when(prescription.prescribe == 0, lab.hms_tz_insurance_coverage_plan)
			.else_("CASH")
			.as_("mode"),
			lab.hms_tz_user_id,
			lab.template,
		)
	).run(as_dict=1)

	lab_list = []
	excluded_lab_tests = excluded_services_map.get("Lab Test Template", [])
	lab_test_templates = [row.healthcare_service for row in excluded_lab_tests]

	for row in lab_records:
		if row.hms_tz_user_id not in vc_lab_users:
			continue

		if row.template in lab_test_templates:
			for excluded_lab_test in excluded_lab_tests:
				if row.template == excluded_lab_test.healthcare_service:
					for lab_tech in lab_tech_list:
						if row.hms_tz_user_id == lab_tech.user_field:
							vc_amount = flt(row.amount * flt(excluded_lab_test.vc_rate / 100))
							vc_wtax_amount = vc_amount * (lab_tech.wtax / 100)
							lab_list.append(
								{
									"practitioner": "",
									"vc_technician": row.hms_tz_submitted_by,
									"billing_item": row.template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(
										row.amount * flt(excluded_lab_test.company_rate / 100)
									),
								}
							)

		elif row.prescribe == 1 and row.mode == "CASH":
			for rate_row in cash_rates:
				if rate_row.document_type == "Lab Test":
					for lab_tech in lab_tech_list:
						if row.hms_tz_user_id == lab_tech.user_field:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (lab_tech.wtax / 100)
							lab_list.append(
								{
									"practitioner": "",
									"vc_technician": row.hms_tz_submitted_by,
									"billing_item": row.template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

		elif row.prescribe == 0 and row.mode != "CASH":
			coverage_plan_name = None
			if row.mode == "NH001~":
				coverage_plan_name = frappe.get_cached_value(
					"Healthcare Insurance Coverage Plan",
					{"name": row.mode},
					"coverage_plan_name",
				)
			for rate_row in insurance_rates:
				if rate_row.coverage_plan == row.mode and rate_row.document_type == "Lab Test":
					for lab_tech in lab_tech_list:
						if row.hms_tz_user_id == lab_tech.user_field:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (lab_tech.wtax / 100)
							lab_list.append(
								{
									"practitioner": "",
									"vc_technician": row.hms_tz_submitted_by,
									"billing_item": row.template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": (coverage_plan_name if coverage_plan_name else row.mode),
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

	return lab_list


def get_radiology_commissions(
	filters,
	cash_rates,
	insurance_rates,
	excluded_services_map,
	vc_radiology_users,
	rad_tech_list,
):
	if filters.get("practitioner"):
		return []

	radiology = dt("Radiology Examination")
	prescription = dt("Radiology Procedure Prescription")
	case_wh = None
	if filters.get("vc_technician"):
		case_wh = radiology.hms_tz_user_id == filters.get("vc_technician")
	else:
		case_wh = radiology.hms_tz_user_id.isnotnull()

	radiology_records = (
		frappe.qb.from_(radiology)
		.inner_join(prescription)
		.on(
			radiology.hms_tz_ref_childname == prescription.name
			and radiology.ref_docname == prescription.parent
			and radiology.radiology_examination_template == prescription.radiology_examination_template
		)
		.select(
			radiology.radiology_examination_template,
			radiology.hms_tz_submitted_by,
			radiology.hms_tz_user_id,
			prescription.prescribe,
			Sum(prescription.amount).as_("amount"),
			Count(radiology.patient).distinct().as_("patient_count"),
			Count(radiology.radiology_examination_template).as_("item_count"),
			Case()
			.when(
				prescription.prescribe == 0,
				radiology.hms_tz_insurance_coverage_plan,
			)
			.else_("CASH")
			.as_("mode"),
		)
		.where(
			(radiology.ref_doctype == "Patient Encounter")
			& (radiology.ref_docname == prescription.parent)
			& (radiology.hms_tz_ref_childname == prescription.name)
			& (radiology.hms_tz_submitted_date >= filters.get("from_date"))
			& (radiology.hms_tz_submitted_date <= filters.get("to_date"))
			& (radiology.company == filters.get("company"))
			& (prescription.is_cancelled == 0)
			& (radiology.docstatus == 1)
			& case_wh
		)
		.groupby(
			Case()
			.when(
				prescription.prescribe == 0,
				radiology.hms_tz_insurance_coverage_plan,
			)
			.else_("CASH")
			.as_("mode"),
			radiology.hms_tz_user_id,
			radiology.radiology_examination_template,
		)
	).run(as_dict=1)

	radiology_list = []
	excluded_radiologies = excluded_services_map.get("Radiology Examination Template", [])
	radiology_templates = [row.healthcare_service for row in excluded_radiologies]

	for row in radiology_records:
		if row.hms_tz_user_id not in vc_radiology_users:
			continue

		if row.radiology_examination_template in radiology_templates:
			for excluded_radiology in excluded_radiologies:
				if row.radiology_examination_template == excluded_radiology.healthcare_service:
					for rad_tech in rad_tech_list:
						if row.hms_tz_user_id == rad_tech.user_field:
							vc_amount = flt(row.amount * flt(excluded_radiology.vc_rate / 100))
							vc_wtax_amount = vc_amount * (rad_tech.wtax / 100)
							radiology_list.append(
								{
									"practitioner": "",
									"vc_technician": row.hms_tz_submitted_by,
									"billing_item": row.radiology_examination_template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(
										row.amount * flt(excluded_radiology.company_rate / 100)
									),
								}
							)

		elif row.prescribe == 1 and row.mode == "CASH":
			for rate_row in cash_rates:
				if rate_row.document_type == "Radiology Examination":
					for rad_tech in rad_tech_list:
						if row.hms_tz_user_id == rad_tech.user_field:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (rad_tech.wtax / 100)
							radiology_list.append(
								{
									"practitioner": "",
									"vc_technician": row.hms_tz_submitted_by,
									"billing_item": row.radiology_examination_template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

		elif row.prescribe == 0 and row.mode != "CASH":
			coverage_plan_name = None
			if row.mode == "NH001~":
				coverage_plan_name = frappe.get_cached_value(
					"Healthcare Insurance Coverage Plan",
					{"name": row.mode},
					"coverage_plan_name",
				)
			for rate_row in insurance_rates:
				if rate_row.coverage_plan == row.mode and rate_row.document_type == "Radiology Examination":
					for rad_tech in rad_tech_list:
						if row.hms_tz_user_id == rad_tech.user_field:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (rad_tech.wtax / 100)
							radiology_list.append(
								{
									"practitioner": "",
									"vc_technician": row.hms_tz_submitted_by,
									"billing_item": row.radiology_examination_template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": (coverage_plan_name if coverage_plan_name else row.mode),
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

	return radiology_list


def get_procedure_commissions(
	filters,
	cash_rates,
	insurance_rates,
	excluded_services_map,
	vc_practitioners,
	practitioner_list,
):
	if filters.get("vc_technician"):
		return []

	procedure = dt("Clinical Procedure")
	prescription = dt("Procedure Prescription")
	case_wh = None
	if filters.get("practitioner"):
		case_wh = procedure.practitioner == filters.get("practitioner")
	else:
		case_wh = procedure.practitioner.isnotnull()

	procedure_records = (
		frappe.qb.from_(procedure)
		.inner_join(prescription)
		.on(
			procedure.hms_tz_ref_childname == prescription.name
			and procedure.ref_docname == prescription.parent
			and procedure.procedure_template == prescription.procedure
		)
		.select(
			procedure.procedure_template,
			procedure.practitioner,
			prescription.prescribe,
			Sum(prescription.amount).as_("amount"),
			Count(procedure.patient).distinct().as_("patient_count"),
			Count(procedure.procedure_template).as_("item_count"),
			Case()
			.when(
				prescription.prescribe == 0,
				procedure.hms_tz_insurance_coverage_plan,
			)
			.else_("CASH")
			.as_("mode"),
		)
		.where(
			(procedure.ref_doctype == "Patient Encounter")
			& (procedure.ref_docname == prescription.parent)
			& (procedure.hms_tz_ref_childname == prescription.name)
			& (procedure.hms_tz_submitted_date >= filters.get("from_date"))
			& (procedure.hms_tz_submitted_date <= filters.get("to_date"))
			& (procedure.company == filters.get("company"))
			& (prescription.is_cancelled == 0)
			& (procedure.docstatus == 1)
			& case_wh
		)
		.groupby(
			Case()
			.when(
				prescription.prescribe == 0,
				procedure.hms_tz_insurance_coverage_plan,
			)
			.else_("CASH")
			.as_("mode"),
			procedure.practitioner,
			procedure.procedure_template,
		)
	).run(as_dict=1)

	procedure_list = []
	excluded_procedures = excluded_services_map.get("Clinical Procedure Template", [])
	excluded_procedure_templates = [row.healthcare_service for row in excluded_procedures]

	for row in procedure_records:
		if row.practitioner not in vc_practitioners:
			continue

		if row.procedure_template in excluded_procedure_templates:
			for excluded_procedure in excluded_procedures:
				if row.procedure_template == excluded_procedure.healthcare_service:
					for prac in practitioner_list:
						if row.practitioner == prac.healathcare_practitioner:
							vc_amount = flt(row.amount * flt(excluded_procedure.vc_rate / 100))
							vc_wtax_amount = vc_amount * (prac.wtax / 100)
							procedure_list.append(
								{
									"practitioner": row.practitioner,
									"vc_technician": "",
									"billing_item": row.procedure_template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(
										row.amount * flt(excluded_procedure.company_rate / 100)
									),
								}
							)

		elif row.prescribe == 1 and row.mode == "CASH":
			for rate_row in cash_rates:
				if rate_row.document_type == "Clinical Procedure":
					for prac in practitioner_list:
						if row.practitioner == prac.healathcare_practitioner:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (prac.wtax / 100)
							procedure_list.append(
								{
									"practitioner": row.practitioner,
									"vc_technician": "",
									"billing_item": row.procedure_template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": row.mode,
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

		elif row.prescribe == 0 and row.mode != "CASH":
			coverage_plan_name = None
			if row.mode == "NH001~":
				coverage_plan_name = frappe.get_cached_value(
					"Healthcare Insurance Coverage Plan",
					{"name": row.mode},
					"coverage_plan_name",
				)
			for rate_row in insurance_rates:
				if rate_row.coverage_plan == row.mode and rate_row.document_type == "Clinical Procedure":
					for prac in practitioner_list:
						if row.practitioner == prac.healathcare_practitioner:
							vc_amount = flt(row.amount * flt(rate_row.vc_rate / 100))
							vc_wtax_amount = vc_amount * (prac.wtax / 100)
							procedure_list.append(
								{
									"practitioner": row.practitioner,
									"vc_technician": "",
									"billing_item": row.procedure_template,
									"patient_count": row.patient_count,
									"item_count": row.item_count,
									"mode": (coverage_plan_name if coverage_plan_name else row.mode),
									"paid_amount": row.amount,
									"vc_amount": vc_amount,
									"vc_wtax_amount": vc_wtax_amount,
									"vc_net_amount": vc_amount - vc_wtax_amount,
									"company_amount": flt(row.amount * flt(rate_row.company_rate / 100)),
								}
							)

	return procedure_list


def get_report_summary(args, summary_data):
	total_paid_amount = sum([flt(row.get("paid_amount")) for row in summary_data if row.get("paid_amount")])
	total_vc_amount = sum([flt(row.get("vc_amount")) for row in summary_data if row.get("vc_amount")])
	total_company_amount = sum(
		[flt(row.get("company_amount")) for row in summary_data if row.get("company_amount")]
	)
	total_vc_wtax_amount = sum(
		[flt(row.get("vc_wtax_amount")) for row in summary_data if row.get("vc_wtax_amount")]
	)
	total_vc_net_amount = sum(
		[flt(row.get("vc_net_amount")) for row in summary_data if row.get("vc_net_amount")]
	)

	currency = frappe.get_cached_value("Company", args.company, "default_currency")
	return [
		{
			"value": total_paid_amount,
			"label": _("Total Paid Amount"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_company_amount,
			"label": _("Total Company Amount"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_vc_amount,
			"label": _("Total VC Amount"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_vc_wtax_amount,
			"label": _("Total VC w/Tax"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_vc_net_amount,
			"label": _("Total VC Net Amount"),
			"datatype": "Currency",
			"currency": currency,
		},
	]
