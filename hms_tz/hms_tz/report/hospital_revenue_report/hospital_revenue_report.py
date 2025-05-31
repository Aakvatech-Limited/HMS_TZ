# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    if not filters:
        return [], []

    validate_filters(filters)

    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    report_summary = get_report_summary(data, filters)

    return columns, data, None, chart, report_summary


def validate_filters(filters):
    """Validate the filters"""
    if not filters.get("company"):
        frappe.throw(_("Company is required"))

    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required"))

    if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
        frappe.throw(_("From Date cannot be greater than To Date"))


def get_columns(filters):
    """Get detailed report columns"""
    columns = [
        {
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "label": _("Date"),
            "width": 100,
        },
        {
            "fieldname": "patient",
            "fieldtype": "Link",
            "label": _("Patient"),
            "options": "Patient",
            "width": 120,
        },
        {
            "fieldname": "patient_name",
            "fieldtype": "Data",
            "label": _("Patient Name"),
            "width": 150,
        },
        {
            "fieldname": "patient_type",
            "fieldtype": "Data",
            "label": _("Patient Type"),
            "width": 100,
        },
        {
            "fieldname": "appointment",
            "fieldtype": "Link",
            "label": _("Appointment No"),
            "options": "Patient Appointment",
            "width": 120,
        },
        {
            "fieldname": "service_type",
            "fieldtype": "Data",
            "label": _("Service Type"),
            "width": 120,
        },
        {
            "fieldname": "service_name",
            "fieldtype": "Data",
            "label": _("Service Name"),
            "width": 150,
        },
        {
            "fieldname": "payment_type",
            "fieldtype": "Data",
            "label": _("Payment Type"),
            "width": 120,
        },
        {
            "fieldname": "insurance_company",
            "fieldtype": "Data",
            "label": _("Insurance Company"),
            "width": 150,
        },
        {
            "fieldname": "department",
            "fieldtype": "Data",
            "label": _("Department"),
            "width": 120,
        },
        {
            "fieldname": "healthcare_practitioner",
            "fieldtype": "Data",
            "label": _("Practitioner"),
            "width": 150,
        },
        {"fieldname": "qty", "fieldtype": "Float", "label": _("Qty"), "width": 80},
        {
            "fieldname": "rate",
            "fieldtype": "Currency",
            "label": _("Rate"),
            "width": 100,
        },
        {
            "fieldname": "amount",
            "fieldtype": "Currency",
            "label": _("Amount"),
            "width": 120,
        },
    ]

    return columns


def get_conditions(filters):
    """Build SQL conditions based on filters"""
    conditions = []

    conditions.append("hre.company = %(company)s")
    conditions.append("hre.posting_date BETWEEN %(from_date)s AND %(to_date)s")
    conditions.append("hre.is_cancelled = 0")

    if filters.get("payment_type"):
        if filters.get("payment_type") == "Cash":
            conditions.append("hre.payment_type = 'Cash'")
        elif filters.get("payment_type") != "Cash":
            # For insurance companies
            conditions.append("hre.insurance_company = %(payment_type)s")

    if filters.get("service_type"):
        conditions.append("hre.service_type = %(service_type)s")

    if filters.get("department"):
        conditions.append("hre.department = %(department)s")

    if filters.get("healthcare_practitioner"):
        conditions.append("hre.healthcare_practitioner = %(healthcare_practitioner)s")

    if filters.get("healthcare_service_unit"):
        conditions.append("hre.healthcare_service_unit = %(healthcare_service_unit)s")

    return " AND ".join(conditions)


def get_data(filters):
    """Get detailed report data"""
    return get_detailed_data(filters)


def get_detailed_data(filters):
    """Get detailed revenue data with patient information"""
    conditions = get_conditions(filters)

    query = """
        SELECT
            hre.posting_date,
            hre.patient,
            hre.patient_name,
            CASE
                WHEN hre.source_doctype = 'Patient Appointment' AND
                     EXISTS(SELECT 1 FROM `tabPatient Appointment` pa WHERE pa.name = hre.appointment AND pa.appointment_type LIKE '%%Emergency%%')
                THEN 'In-Patient'
                WHEN hre.source_doctype = 'Lab Test' AND
                     EXISTS(SELECT 1 FROM `tabLab Test` lt WHERE lt.name = hre.source_docname AND lt.inpatient_record IS NOT NULL)
                THEN 'In-Patient'
                WHEN hre.source_doctype = 'Radiology Examination' AND
                     EXISTS(SELECT 1 FROM `tabRadiology Examination` re WHERE re.name = hre.source_docname AND re.inpatient_record IS NOT NULL)
                THEN 'In-Patient'
                WHEN hre.source_doctype = 'Clinical Procedure' AND
                     EXISTS(SELECT 1 FROM `tabClinical Procedure` cp WHERE cp.name = hre.source_docname AND cp.inpatient_record IS NOT NULL)
                THEN 'In-Patient'
                ELSE 'Out-Patient'
            END as patient_type,
            hre.appointment,
            hre.service_type,
            hre.service_name,
            hre.payment_type,
            hre.insurance_company,
            hre.department,
            hre.healthcare_practitioner,
            hre.qty,
            hre.rate,
            hre.amount
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
        ORDER BY hre.posting_date DESC, hre.patient_name
    """.format(
        conditions=conditions
    )

    return frappe.db.sql(query, filters, as_dict=True)


def get_date_wise_data(filters):
    """Get date-wise revenue data"""
    conditions = get_conditions(filters)

    query = f"""
        SELECT
            hre.posting_date,
            SUM(hre.amount) as total_revenue,
            SUM(CASE WHEN hre.payment_type = 'Cash' THEN hre.amount ELSE 0 END) as cash_revenue,
            SUM(CASE WHEN hre.payment_type = 'Insurance' THEN hre.amount ELSE 0 END) as insurance_revenue,
            SUM(CASE WHEN hre.service_type = 'Consultation Charges' THEN hre.amount ELSE 0 END) as consultation_revenue,
            SUM(CASE WHEN hre.service_type = 'Lab Test Template' THEN hre.amount ELSE 0 END) as lab_revenue,
            SUM(CASE WHEN hre.service_type = 'Radiology Examination Template' THEN hre.amount ELSE 0 END) as radiology_revenue,
            SUM(CASE WHEN hre.service_type = 'Clinical Procedure Template' THEN hre.amount ELSE 0 END) as procedure_revenue,
            SUM(CASE WHEN hre.service_type = 'Medication' THEN hre.amount ELSE 0 END) as medication_revenue,
            SUM(CASE WHEN hre.service_type = 'Therapy Type' THEN hre.amount ELSE 0 END) as therapy_revenue
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
        GROUP BY hre.posting_date
        ORDER BY hre.posting_date
    """

    return frappe.db.sql(query, filters, as_dict=True)


def get_service_type_wise_data(filters):
    """Get service type-wise revenue data"""
    conditions = get_conditions(filters)

    query = f"""
        SELECT
            hre.service_type,
            SUM(hre.amount) as total_revenue,
            SUM(CASE WHEN hre.payment_type = 'Cash' THEN hre.amount ELSE 0 END) as cash_revenue,
            SUM(CASE WHEN hre.payment_type = 'Insurance' THEN hre.amount ELSE 0 END) as insurance_revenue,
            SUM(hre.qty) as total_qty,
            AVG(hre.rate) as avg_rate
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
        GROUP BY hre.service_type
        ORDER BY total_revenue DESC
    """

    return frappe.db.sql(query, filters, as_dict=True)


def get_payment_type_wise_data(filters):
    """Get payment type-wise revenue data"""
    conditions = get_conditions(filters)

    # First get total revenue for percentage calculation
    total_query = f"""
        SELECT SUM(hre.amount) as total_amount
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
    """
    total_result = frappe.db.sql(total_query, filters, as_dict=True)
    total_revenue = total_result[0].total_amount if total_result else 0

    query = f"""
        SELECT
            hre.payment_type,
            SUM(hre.amount) as total_revenue,
            SUM(hre.qty) as total_qty,
            AVG(hre.rate) as avg_rate
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
        GROUP BY hre.payment_type
        ORDER BY total_revenue DESC
    """

    data = frappe.db.sql(query, filters, as_dict=True)

    # Calculate percentage
    for row in data:
        if total_revenue:
            row.percentage = (row.total_revenue / total_revenue) * 100
        else:
            row.percentage = 0

    return data


def get_department_wise_data(filters):
    """Get department-wise revenue data"""
    conditions = get_conditions(filters)

    query = f"""
        SELECT
            COALESCE(hre.department, 'Not Specified') as department,
            SUM(hre.amount) as total_revenue,
            SUM(CASE WHEN hre.payment_type = 'Cash' THEN hre.amount ELSE 0 END) as cash_revenue,
            SUM(CASE WHEN hre.payment_type = 'Insurance' THEN hre.amount ELSE 0 END) as insurance_revenue,
            SUM(hre.qty) as total_qty
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
        GROUP BY hre.department
        ORDER BY total_revenue DESC
    """

    return frappe.db.sql(query, filters, as_dict=True)


def get_practitioner_wise_data(filters):
    """Get practitioner-wise revenue data"""
    conditions = get_conditions(filters)

    query = f"""
        SELECT
            COALESCE(hre.healthcare_practitioner, 'Not Specified') as healthcare_practitioner,
            SUM(hre.amount) as total_revenue,
            SUM(CASE WHEN hre.payment_type = 'Cash' THEN hre.amount ELSE 0 END) as cash_revenue,
            SUM(CASE WHEN hre.payment_type = 'Insurance' THEN hre.amount ELSE 0 END) as insurance_revenue,
            SUM(hre.qty) as total_qty
        FROM `tabHospital Revenue Entry` hre
        WHERE {conditions}
        GROUP BY hre.healthcare_practitioner
        ORDER BY total_revenue DESC
    """

    return frappe.db.sql(query, filters, as_dict=True)


def get_chart_data(data, filters):
    """Generate chart data for detailed report"""
    if not data:
        return None

    # Create revenue trends chart from detailed data
    return get_revenue_trends_from_detailed_data(data)


def get_revenue_trends_from_detailed_data(data):
    """Generate revenue trends chart from detailed data"""
    # Group data by date
    date_wise_data = {}

    for row in data:
        date_key = row.get("posting_date")
        if isinstance(date_key, str):
            date_str = date_key
        else:
            date_str = date_key.strftime("%Y-%m-%d") if date_key else ""

        if date_str not in date_wise_data:
            date_wise_data[date_str] = {
                "total_revenue": 0,
                "cash_revenue": 0,
                "insurance_revenue": 0,
            }

        amount = flt(row.get("amount", 0))
        date_wise_data[date_str]["total_revenue"] += amount

        if row.get("payment_type") == "Cash":
            date_wise_data[date_str]["cash_revenue"] += amount
        else:
            date_wise_data[date_str]["insurance_revenue"] += amount

    # Sort by date
    sorted_dates = sorted(date_wise_data.keys())

    labels = sorted_dates
    total_revenue = [date_wise_data[date]["total_revenue"] for date in sorted_dates]
    cash_revenue = [date_wise_data[date]["cash_revenue"] for date in sorted_dates]
    insurance_revenue = [
        date_wise_data[date]["insurance_revenue"] for date in sorted_dates
    ]

    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Total Revenue"),
                    "values": total_revenue,
                    "chartType": "line",
                },
                {"name": _("Cash Revenue"), "values": cash_revenue, "chartType": "bar"},
                {
                    "name": _("Insurance Revenue"),
                    "values": insurance_revenue,
                    "chartType": "bar",
                },
            ],
        },
        "type": "axis-mixed",
        "colors": ["#36A2EB", "#4BC0C0", "#FF6384"],
        "barOptions": {"stacked": True},
        "lineOptions": {"regionFill": 1},
        "height": 350,
    }

    return chart


@frappe.whitelist()
def get_payment_types():
    """Get payment type options including insurance companies"""
    options = [{"value": "", "label": ""}]
    options.append({"value": "Cash", "label": "Cash"})

    # Get all insurance companies from Healthcare Insurance Company doctype
    insurance_companies = frappe.db.sql(
        """
        SELECT name, insurance_company_name
        FROM `tabHealthcare Insurance Company`
        WHERE disabled = 0
        ORDER BY insurance_company_name
    """,
        as_dict=True,
    )

    for company in insurance_companies:
        if company.name:
            options.append(
                {
                    "value": company.name,
                    "label": company.insurance_company_name or company.name,
                }
            )

    return options


def get_revenue_trends_chart(data):
    """Generate revenue trends chart for date-wise data"""
    labels = []
    total_revenue = []
    cash_revenue = []
    insurance_revenue = []

    for row in data:
        # Handle both string and date objects
        if row.posting_date:
            if isinstance(row.posting_date, str):
                labels.append(row.posting_date)
            else:
                labels.append(row.posting_date.strftime("%Y-%m-%d"))
        else:
            labels.append("")

        total_revenue.append(flt(row.get("total_revenue", 0), 2))
        cash_revenue.append(flt(row.get("cash_revenue", 0), 2))
        insurance_revenue.append(flt(row.get("insurance_revenue", 0), 2))

    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Total Revenue"),
                    "values": total_revenue,
                    "chartType": "line",
                },
                {"name": _("Cash Revenue"), "values": cash_revenue, "chartType": "bar"},
                {
                    "name": _("Insurance Revenue"),
                    "values": insurance_revenue,
                    "chartType": "bar",
                },
            ],
        },
        "type": "axis-mixed",
        "colors": ["#36A2EB", "#4BC0C0", "#FF6384"],
        "barOptions": {"stacked": True},
        "lineOptions": {"regionFill": 1},
        "height": 350,
    }

    return chart


def get_service_type_chart(data, filters):
    """Generate service type analysis chart"""
    # Get service type data if not already grouped by service type
    if filters.get("group_by") != "Service Type":
        data = get_service_type_wise_data(filters)

    if not data:
        return None

    labels = []
    values = []

    for row in data:
        labels.append(row.get("service_type") or "Not Specified")
        values.append(flt(row.get("total_revenue", 0), 2))

    chart = {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Revenue by Service Type"), "values": values}],
        },
        "type": "bar",
        "colors": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40"],
        "height": 350,
    }

    return chart


def get_payment_type_chart(data, filters):
    """Generate payment type analysis chart"""
    # Get payment type data if not already grouped by payment type
    if filters.get("group_by") != "Payment Type":
        data = get_payment_type_wise_data(filters)

    if not data:
        return None

    labels = []
    values = []

    for row in data:
        labels.append(row.get("payment_type") or "Not Specified")
        values.append(flt(row.get("total_revenue", 0), 2))

    chart = {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Revenue by Payment Type"), "values": values}],
        },
        "type": "donut",
        "colors": ["#4BC0C0", "#FF6384"],
        "height": 350,
    }

    return chart


def get_department_chart(data, filters):
    """Generate department analysis chart"""
    # Get department data if not already grouped by department
    if filters.get("group_by") != "Department":
        data = get_department_wise_data(filters)

    if not data:
        return None

    # Limit to top 10 departments for better visualization
    data = data[:10]

    labels = []
    values = []

    for row in data:
        labels.append(row.get("department") or "Not Specified")
        values.append(flt(row.get("total_revenue", 0), 2))

    chart = {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Revenue by Department"), "values": values}],
        },
        "type": "bar",
        "colors": [
            "#36A2EB",
            "#FF6384",
            "#FFCE56",
            "#4BC0C0",
            "#9966FF",
            "#FF9F40",
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#96CEB4",
        ],
        "height": 350,
    }

    return chart


def get_report_summary(data, filters):
    """Generate report summary from detailed data"""
    if not data:
        return None

    # Calculate totals from detailed data
    total_revenue = sum(flt(row.get("amount", 0), 2) for row in data)
    cash_revenue = sum(
        flt(row.get("amount", 0), 2)
        for row in data
        if row.get("payment_type") == "Cash"
    )
    insurance_revenue = sum(
        flt(row.get("amount", 0), 2)
        for row in data
        if row.get("payment_type") == "Insurance"
    )

    # Get unique dates for average calculation
    unique_dates = set()
    for row in data:
        date_key = row.get("posting_date")
        if isinstance(date_key, str):
            unique_dates.add(date_key)
        elif date_key:
            unique_dates.add(date_key.strftime("%Y-%m-%d"))

    avg_daily_revenue = total_revenue / len(unique_dates) if unique_dates else 0

    summary = [
        {
            "value": total_revenue,
            "label": _("Total Revenue"),
            "datatype": "Currency",
            "indicator": "Green" if total_revenue > 0 else "Red",
        },
        {
            "value": cash_revenue,
            "label": _("Cash Revenue"),
            "datatype": "Currency",
            "indicator": "Blue",
        },
        {
            "value": insurance_revenue,
            "label": _("Insurance Revenue"),
            "datatype": "Currency",
            "indicator": "Orange",
        },
        {
            "value": avg_daily_revenue,
            "label": _("Average Daily Revenue"),
            "datatype": "Currency",
            "indicator": "Purple",
        },
        {
            "value": len(data),
            "label": _("Total Transactions"),
            "datatype": "Int",
            "indicator": "Green",
        },
    ]

    # Add cash vs insurance percentage
    if total_revenue > 0:
        cash_percentage = (cash_revenue / total_revenue) * 100
        insurance_percentage = (insurance_revenue / total_revenue) * 100

        summary.extend(
            [
                {
                    "value": cash_percentage,
                    "label": _("Cash %"),
                    "datatype": "Percent",
                    "indicator": "Green",
                },
                {
                    "value": insurance_percentage,
                    "label": _("Insurance %"),
                    "datatype": "Percent",
                    "indicator": "Blue",
                },
            ]
        )

    return summary
