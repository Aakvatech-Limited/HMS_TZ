"""Set the inpatient status of each Inpatient Record's latest encounter.

Before, only the admission and discharge encounters got a status, so the
current encounter kept "Admission Scheduled" after the discharge.
"""

import frappe

from hms_tz.nhif.api.inpatient_record import update_latest_encounter_status


def execute():
	for record in frappe.get_all("Inpatient Record", fields=["name", "status"]):
		update_latest_encounter_status(record.name, record.status)
