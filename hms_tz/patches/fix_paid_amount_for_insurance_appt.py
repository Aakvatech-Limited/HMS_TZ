# Copyright (c) 2021, Aakvatech and Contributors
# License: GNU General Public License v3. See license.txt


import frappe

from hms_tz.nhif.api.patient_appointment import get_insurance_amount

# one-off 2021 patch, not registered in patches.txt
appointment_list = frappe.db.sql(  # nosemgrep
    "SELECT name, insurance_subscription, billing_item, company, insurance_company FROM `tabPatient Appointment` WHERE paid_amount = 0 AND insurance_subscription IS NOT NULL AND billing_item IS NOT NULL AND appointment_date BETWEEN '2021-03-23' AND '2021-04-05",
    as_dict=1,
)
for appointment in appointment_list:
    paid_amount = get_insurance_amount(
        appointment.insurance_subscription,
        appointment.billing_item,
        appointment.company,
        appointment.insurance_company,
    )
    frappe.db.sql(f"UPDATE `tabPatient Appointment` SET paid_amount = {paid_amount} WHERE name = '{appointment.name}'")
frappe.db.commit()
