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
    """Get report columns based on group_by filter"""
    group_by = filters.get("group_by", "Date")

    columns = []

    if group_by == "Date":
        columns = [
            {
                "fieldname": "posting_date",
                "fieldtype": "Date",
                "label": _("Date"),
                "width": 100,
            },
            {
                "fieldname": "total_revenue",
                "fieldtype": "Currency",
                "label": _("Total Revenue"),
                "width": 120,
            },
            {
                "fieldname": "cash_revenue",
                "fieldtype": "Currency",
                "label": _("Cash Revenue"),
                "width": 120,
            },
            {
                "fieldname": "insurance_revenue",
                "fieldtype": "Currency",
                "label": _("Insurance Revenue"),
                "width": 120,
            },
            {
                "fieldname": "consultation_revenue",
                "fieldtype": "Currency",
                "label": _("Consultation"),
                "width": 100,
            },
            {
                "fieldname": "lab_revenue",
                "fieldtype": "Currency",
                "label": _("Lab Tests"),
                "width": 100,
            },
            {
                "fieldname": "radiology_revenue",
                "fieldtype": "Currency",
                "label": _("Radiology"),
                "width": 100,
            },
            {
                "fieldname": "procedure_revenue",
                "fieldtype": "Currency",
                "label": _("Procedures"),
                "width": 100,
            },
            {
                "fieldname": "medication_revenue",
                "fieldtype": "Currency",
                "label": _("Medication"),
                "width": 100,
            },
            {
                "fieldname": "therapy_revenue",
                "fieldtype": "Currency",
                "label": _("Therapy"),
                "width": 100,
            },
        ]
    elif group_by == "Service Type":
        columns = [
            {
                "fieldname": "service_type",
                "fieldtype": "Data",
                "label": _("Service Type"),
                "width": 150,
            },
            {
                "fieldname": "total_revenue",
                "fieldtype": "Currency",
                "label": _("Total Revenue"),
                "width": 120,
            },
            {
                "fieldname": "cash_revenue",
                "fieldtype": "Currency",
                "label": _("Cash Revenue"),
                "width": 120,
            },
            {
                "fieldname": "insurance_revenue",
                "fieldtype": "Currency",
                "label": _("Insurance Revenue"),
                "width": 120,
            },
            {
                "fieldname": "total_qty",
                "fieldtype": "Float",
                "label": _("Total Quantity"),
                "width": 100,
            },
            {
                "fieldname": "avg_rate",
                "fieldtype": "Currency",
                "label": _("Average Rate"),
                "width": 100,
            },
        ]
    elif group_by == "Payment Type":
        columns = [
            {
                "fieldname": "payment_type",
                "fieldtype": "Data",
                "label": _("Payment Type"),
                "width": 120,
            },
            {
                "fieldname": "total_revenue",
                "fieldtype": "Currency",
                "label": _("Total Revenue"),
                "width": 120,
            },
            {
                "fieldname": "total_qty",
                "fieldtype": "Float",
                "label": _("Total Quantity"),
                "width": 100,
            },
            {
                "fieldname": "avg_rate",
                "fieldtype": "Currency",
                "label": _("Average Rate"),
                "width": 100,
            },
            {
                "fieldname": "percentage",
                "fieldtype": "Percent",
                "label": _("Percentage"),
                "width": 100,
            },
        ]
    elif group_by == "Department":
        columns = [
            {
                "fieldname": "department",
                "fieldtype": "Data",
                "label": _("Department"),
                "width": 150,
            },
            {
                "fieldname": "total_revenue",
                "fieldtype": "Currency",
                "label": _("Total Revenue"),
                "width": 120,
            },
            {
                "fieldname": "cash_revenue",
                "fieldtype": "Currency",
                "label": _("Cash Revenue"),
                "width": 120,
            },
            {
                "fieldname": "insurance_revenue",
                "fieldtype": "Currency",
                "label": _("Insurance Revenue"),
                "width": 120,
            },
            {
                "fieldname": "total_qty",
                "fieldtype": "Float",
                "label": _("Total Quantity"),
                "width": 100,
            },
        ]
    elif group_by == "Practitioner":
        columns = [
            {
                "fieldname": "healthcare_practitioner",
                "fieldtype": "Data",
                "label": _("Healthcare Practitioner"),
                "width": 180,
            },
            {
                "fieldname": "total_revenue",
                "fieldtype": "Currency",
                "label": _("Total Revenue"),
                "width": 120,
            },
            {
                "fieldname": "cash_revenue",
                "fieldtype": "Currency",
                "label": _("Cash Revenue"),
                "width": 120,
            },
            {
                "fieldname": "insurance_revenue",
                "fieldtype": "Currency",
                "label": _("Insurance Revenue"),
                "width": 120,
            },
            {
                "fieldname": "total_qty",
                "fieldtype": "Float",
                "label": _("Total Quantity"),
                "width": 100,
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
        conditions.append("hre.payment_type = %(payment_type)s")

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
    """Get report data based on group_by filter"""
    group_by = filters.get("group_by", "Date")

    if group_by == "Date":
        return get_date_wise_data(filters)
    elif group_by == "Service Type":
        return get_service_type_wise_data(filters)
    elif group_by == "Payment Type":
        return get_payment_type_wise_data(filters)
    elif group_by == "Department":
        return get_department_wise_data(filters)
    elif group_by == "Practitioner":
        return get_practitioner_wise_data(filters)

    return []


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
    """Generate chart data based on chart_type filter"""
    if not data:
        return None

    chart_type = filters.get("chart_type", "Revenue Trends")
    group_by = filters.get("group_by", "Date")

    if chart_type == "Revenue Trends" and group_by == "Date":
        return get_revenue_trends_chart(data)
    elif chart_type == "Service Type Analysis":
        return get_service_type_chart(data, filters)
    elif chart_type == "Payment Type Analysis":
        return get_payment_type_chart(data, filters)
    elif chart_type == "Department Analysis":
        return get_department_chart(data, filters)

    return None


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
    """Generate report summary"""
    if not data:
        return None

    group_by = filters.get("group_by", "Date")

    # Calculate totals based on group_by
    if group_by == "Date":
        total_revenue = sum(flt(row.get("total_revenue", 0), 2) for row in data)
        cash_revenue = sum(flt(row.get("cash_revenue", 0), 2) for row in data)
        insurance_revenue = sum(flt(row.get("insurance_revenue", 0), 2) for row in data)

        # Calculate averages
        avg_daily_revenue = total_revenue / len(data) if data else 0

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

    else:
        # For other groupings, show total revenue and count
        total_revenue = sum(flt(row.get("total_revenue", 0), 2) for row in data)
        total_qty = sum(
            flt(row.get("total_qty", 0), 2)
            for row in data
            if row.get("total_qty") is not None
        )

        summary = [
            {
                "value": total_revenue,
                "label": _("Total Revenue"),
                "datatype": "Currency",
                "indicator": "Green",
            },
            {
                "value": len(data),
                "label": _(f"Total {group_by}s"),
                "datatype": "Int",
                "indicator": "Blue",
            },
        ]

        if total_qty > 0:
            summary.append(
                {
                    "value": total_qty,
                    "label": _("Total Quantity"),
                    "datatype": "Float",
                    "indicator": "Orange",
                }
            )

            avg_rate = total_revenue / total_qty if total_qty > 0 else 0
            summary.append(
                {
                    "value": avg_rate,
                    "label": _("Average Rate"),
                    "datatype": "Currency",
                    "indicator": "Purple",
                }
            )

    return summary
