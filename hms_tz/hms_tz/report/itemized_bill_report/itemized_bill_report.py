# Copyright (c) 2022, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt


def execute(filters=None):
    if not filters:
        return

    # Validate required filters
    if not filters.get("patient"):
        frappe.throw("Patient is required")

    if not filters.get("patient_appointment"):
        frappe.throw("Patient Appointment is required")

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

    # Check if appointment exists
    if not details:
        frappe.throw(
            f"Patient Appointment {frappe.bold(filters.patient_appointment)} not found for Patient {frappe.bold(filters.patient)}. "
            "Please check your filters and try again."
        )

    appointment_date = frappe.get_cached_value("Patient Appointment", filters.patient_appointment, "appointment_date")

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
                    Please change your filters and try again..!!")

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
                    Please change your filters and try again..!!")

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
                    Please change your filters and try again..!!")

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

    hsr = DocType("Healthcare Service Request")

    # Get Healthcare Service Requests for the patient and appointment
    hsr_query = (
        frappe.qb.from_(hsr)
        .select("name")
        .where(
            (hsr.patient == filters.patient)
            & (hsr.appointment == filters.patient_appointment)
            & (hsr.docstatus == 1)
        )
    )

    if filters.get("from_date"):
        hsr_query.where((hsr.posting_datetime >= filters.from_date))

    if filters.get("to_date"):
        hsr_query.where((hsr.posting_datetime <= filters.to_date))

    hsr_names = [d.name for d in hsr_query.run(as_dict=True)]

    if not hsr_names or len(hsr_names) == 0:
        return []

    data = get_exceeded_hsr_items(hsr_names)
    return data


def get_exceeded_hsr_items(hsr_names):
    """Get exceeded items from Healthcare Service Request"""
    # Query to get exceeded items from Healthcare Service Request
    exceeded_items = frappe.db.sql(
        """
        SELECT
            DATE(hsr.posting_datetime) AS date,
            CASE
                WHEN hsri.service_type = 'Lab Test Template' THEN
                    (SELECT lab_test_group FROM `tabLab Test Template` WHERE name = hsri.service_name)
                WHEN hsri.service_type = 'Radiology Examination Template' THEN
                    (SELECT item_group FROM `tabRadiology Examination Template` WHERE name = hsri.service_name)
                WHEN hsri.service_type = 'Clinical Procedure Template' THEN
                    (SELECT item_group FROM `tabClinical Procedure Template` WHERE name = hsri.service_name)
                WHEN hsri.service_type = 'Medication' THEN
                    (SELECT item_group FROM `tabMedication` WHERE name = hsri.service_name)
                WHEN hsri.service_type = 'Therapy Type' THEN
                    (SELECT item_group FROM `tabTherapy Type` WHERE name = hsri.service_name)
                ELSE 'Other'
            END AS category,
            hsri.service_name AS description,
            hsri.qty AS quantity,
            hsri.rate AS rate,
            hsri.amount AS amount
        FROM `tabHealthcare Service Request Item` hsri
        INNER JOIN `tabHealthcare Service Request` hsr ON hsri.parent = hsr.name
        WHERE hsr.name IN %(hsr_names)s
        AND hsri.is_cancelled = 0
        AND hsri.is_restricted = 1
        ORDER BY hsr.posting_datetime, hsri.service_type, hsri.service_name
        """,
        {"hsr_names": hsr_names},
        as_dict=True
    )

    return exceeded_items


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


def get_conditions(filters):
    conditions = ""

    if filters.get("patient"):
        conditions = " and pa.patient = %(patient)s"

    if filters.get("patient_appointment"):
        conditions += " and pa.name = %(patient_appointment)s"

    if filters.get("from_date"):
        conditions += " and pa.appointment_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " and pa.appointment_date <= %(to_date)s"

    return conditions


def get_hsr_conditions(filters):
    """Get conditions for Healthcare Service Request queries"""
    conditions = ""

    if filters.get("patient"):
        conditions = " and hsr.patient = %(patient)s"

    if filters.get("patient_appointment"):
        conditions += " and hsr.appointment = %(patient_appointment)s"

    if filters.get("from_date"):
        conditions += " and DATE(hsr.posting_datetime) >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " and DATE(hsr.posting_datetime) <= %(to_date)s"

    return conditions


def get_enc_conditions(filters):
    """Legacy function - kept for backward compatibility if needed"""
    conditions = ""

    if filters.get("patient"):
        conditions = " and pe.patient = %(patient)s"

    if filters.get("patient_appointment"):
        conditions += " and pe.appointment = %(patient_appointment)s"

    if filters.get("patient_type") == "Out-Patient":
        conditions += " and pe.inpatient_record is null "

    if filters.get("patient_type") == "In-Patient":
        conditions += " and pe.inpatient_record is not null "

    if filters.get("from_date"):
        conditions += " and pe.encounter_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " and pe.encounter_date <= %(to_date)s"

    return conditions


def get_ipd_conditions(filters):
    conditions = ""

    if filters.get("patient"):
        conditions = " and ipd_rec.patient = %(patient)s"

    if filters.get("patient_appointment"):
        conditions += " and ipd_rec.patient_appointment = %(patient_appointment)s"

    if filters.get("from_date"):
        conditions += " and DATE(ipd_rec.admitted_datetime) >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " and DATE(ipd_rec.admitted_datetime) <= %(to_date)s"

    return conditions


def get_appointment_consultancy(filters):
    conditions = get_conditions(filters)

    data = frappe.db.sql(
        f"""
		SELECT
			pa.appointment_date AS date,
			it.item_group AS category,
			pa.billing_item AS description,
			1 AS quantity,
			pa.paid_amount AS rate,
			pa.paid_amount AS amount,
			pa.patient AS patient,
			pa.patient_name AS patient_name,
			pa.appointment_type AS appointment_type,
			pa.insurance_company AS insurance_company,
			pa.coverage_plan_name AS coverage_plan_name,
			pa.authorization_number AS authorization_number,
			pa.coverage_plan_card_number AS coverage_plan_card_number,
			DATE(ipd_rec.admitted_datetime) as admitted_date,
			ipd_rec.discharge_date as discharge_date
		FROM `tabPatient Appointment` pa
			INNER JOIN `tabItem` it ON pa.billing_item = it.item_name
			LEFT JOIN `tabInpatient Record` ipd_rec ON pa.name = ipd_rec.patient_appointment
		WHERE pa.status = "Closed"
		AND pa.follow_up = 0 {conditions}
	""",
        filters,
        as_dict=1,
    )
    return data


def get_ipd_occupancy_transactions(filters):
    ipd_conditions = get_ipd_conditions(filters)
    pe_conditions = get_enc_conditions(filters)

    data = frappe.db.sql(
        f"""
		SELECT
			DATE(ipd_occ.check_in) AS date,
			hsut.item_group AS category,
			ipd_occ.service_unit AS description,
			1 AS quantity,
			ipd_occ.amount AS rate,
			ipd_occ.amount AS amount,
			pa.patient AS patient,
			pa.patient_name AS patient_name,
			pa.appointment_type AS appointment_type,
			pa.insurance_company AS insurance_company,
			pa.coverage_plan_name AS coverage_plan_name,
			pa.authorization_number AS authorization_number,
			pa.coverage_plan_card_number AS coverage_plan_card_number,
			DATE(ipd_rec.admitted_datetime) as admitted_date,
			ipd_rec.discharge_date as discharge_date
		FROM `tabInpatient Occupancy` ipd_occ
			INNER JOIN `tabInpatient Record` ipd_rec ON ipd_occ.parent = ipd_rec.name
			INNER JOIN `tabHealthcare Service Unit` hsu ON ipd_occ.service_unit = hsu.name
			INNER JOIN `tabHealthcare Service Unit Type` hsut ON hsu.service_unit_type = hsut.name
			INNER JOIN `tabPatient Appointment` pa ON ipd_rec.patient_appointment = pa.name
		WHERE ipd_occ.is_confirmed = 1
		AND ipd_rec.admission_encounter IN (
			SELECT pe.name FROM `tabPatient Encounter` pe
			WHERE pe.docstatus = 1 {pe_conditions}
			ORDER BY pe.creation desc
		) {ipd_conditions}
	""",
        filters,
        as_dict=1,
    )

    return data


def get_ipd_consultancy_transactions(filters):
    ipd_conditions = get_ipd_conditions(filters)
    pe_conditions = get_enc_conditions(filters)

    data = frappe.db.sql(
        f"""
		SELECT
			ipd_cons.date AS date,
			it.item_group AS category,
			ipd_cons.consultation_item AS description,
			1 AS quantity,
			ipd_cons.rate AS rate,
			ipd_cons.rate AS amount,
			pa.patient AS patient,
			pa.patient_name AS patient_name,
			pa.appointment_type AS appointment_type,
			pa.insurance_company AS insurance_company,
			pa.coverage_plan_name AS coverage_plan_name,
			pa.authorization_number AS authorization_number,
			pa.coverage_plan_card_number AS coverage_plan_card_number,
			DATE(ipd_rec.admitted_datetime) as admitted_date,
			ipd_rec.discharge_date as discharge_date
		FROM `tabInpatient Consultancy` ipd_cons
			INNER JOIN `tabInpatient Record` ipd_rec ON ipd_cons.parent = ipd_rec.name
			INNER JOIN `tabPatient Appointment` pa ON ipd_rec.patient_appointment = pa.name
			INNER JOIN `tabItem` it ON ipd_cons.consultation_item = it.item_name
		WHERE ipd_cons.is_confirmed = 1
		AND ipd_cons.encounter IN (
			SELECT pe.name FROM `tabPatient Encounter` pe
			WHERE pe.docstatus = 1 {pe_conditions}
			ORDER BY pe.creation desc
		) {ipd_conditions}
	""",
        filters,
        as_dict=1,
    )
    return data


def get_cash_lrpmt_transaction(filters):
    conditions = get_hsr_conditions(filters)

    data = frappe.db.sql(
        f"""
		SELECT
			DATE(hsr.posting_datetime) AS date,
			CASE
				WHEN hsri.service_type = 'Lab Test Template' THEN
					(SELECT lab_test_group FROM `tabLab Test Template` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Radiology Examination Template' THEN
					(SELECT item_group FROM `tabRadiology Examination Template` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Clinical Procedure Template' THEN
					(SELECT item_group FROM `tabClinical Procedure Template` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Medication' THEN
					(SELECT item_group FROM `tabMedication` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Therapy Type' THEN
					(SELECT item_group FROM `tabTherapy Type` WHERE name = hsri.service_name)
				ELSE 'Other'
			END AS category,
			hsri.service_name AS description,
			hsri.qty AS quantity,
			hsri.rate AS rate,
			hsri.amount AS amount,
			pa.patient AS patient,
			pa.patient_name AS patient_name,
			pa.appointment_type AS appointment_type,
			pa.insurance_company AS insurance_company,
			pa.coverage_plan_name AS coverage_plan_name,
			pa.authorization_number AS authorization_number,
			pa.coverage_plan_card_number AS coverage_plan_card_number,
			DATE(ipd_rec.admitted_datetime) as admitted_date,
			ipd_rec.discharge_date as discharge_date
		FROM `tabHealthcare Service Request Item` hsri
			INNER JOIN `tabHealthcare Service Request` hsr ON hsri.parent = hsr.name
			INNER JOIN `tabPatient Appointment` pa ON hsr.appointment = pa.name
			LEFT JOIN `tabInpatient Record` ipd_rec ON pa.name = ipd_rec.patient_appointment
		WHERE hsri.is_cancelled = 0
		AND hsr.payment_type = 'Cash'
		AND hsr.docstatus = 1 {conditions}

		""",
        filters,
        as_dict=1,
    )

    return data


def get_insurance_lrpmt_transaction(filters):
    conditions = get_hsr_conditions(filters)

    data = frappe.db.sql(
        f"""
		SELECT
			DATE(hsr.posting_datetime) AS date,
			CASE
				WHEN hsri.service_type = 'Lab Test Template' THEN
					(SELECT lab_test_group FROM `tabLab Test Template` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Radiology Examination Template' THEN
					(SELECT item_group FROM `tabRadiology Examination Template` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Clinical Procedure Template' THEN
					(SELECT item_group FROM `tabClinical Procedure Template` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Medication' THEN
					(SELECT item_group FROM `tabMedication` WHERE name = hsri.service_name)
				WHEN hsri.service_type = 'Therapy Type' THEN
					(SELECT item_group FROM `tabTherapy Type` WHERE name = hsri.service_name)
				ELSE 'Other'
			END AS category,
			hsri.service_name AS description,
			hsri.qty AS quantity,
			hsri.rate AS rate,
			hsri.amount AS amount,
			pa.patient AS patient,
			pa.patient_name AS patient_name,
			pa.appointment_type AS appointment_type,
			pa.insurance_company AS insurance_company,
			pa.coverage_plan_name AS coverage_plan_name,
			pa.authorization_number AS authorization_number,
			pa.coverage_plan_card_number AS coverage_plan_card_number,
			DATE(ipd_rec.admitted_datetime) as admitted_date,
			ipd_rec.discharge_date as discharge_date
		FROM `tabHealthcare Service Request Item` hsri
			INNER JOIN `tabHealthcare Service Request` hsr ON hsri.parent = hsr.name
			INNER JOIN `tabPatient Appointment` pa ON hsr.appointment = pa.name
			LEFT JOIN `tabInpatient Record` ipd_rec ON pa.name = ipd_rec.patient_appointment
		WHERE hsri.is_cancelled = 0
		AND hsr.payment_type = 'Insurance'
		AND hsr.docstatus = 1 {conditions}

		""",
        filters,
        as_dict=1,
    )

    return data


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
