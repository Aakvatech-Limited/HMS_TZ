import frappe

from hms_tz.api.setup import get_company_setup
from hms_tz.hms_tz.doctype.setup_status.setup_runner import (
	ROOMS_STEP,
	is_setup_running,
	start_setup,
	sync_run_steps,
)
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

STEP_FIELDS = ("step", "label", "status", "done", "total", "added", "result", "error")


@frappe.whitelist()
def get_setup_run(company):
	"""The setup page banner, whether the runner is unlocked, and each runner step with its progress."""
	setup = get_company_setup(company)
	run = {"setting": setup["setting"], "settings_complete": setup["settings_complete"]}
	run.update(rooms=frappe.db.count("Healthcare Service Unit", {"company": company, "is_group": 0}))
	run.update(standard_records=get_standard_record_counts(company), steps=[], is_running=False)
	if not setup["setting"]:
		return run

	status = get_setup_status(setup["setting"])
	sync_run_steps(status)
	run["has_rooms"] = bool(status.get_step(ROOMS_STEP).completed)
	run["is_running"] = is_setup_running(setup["setting"])
	run["steps"] = [{field: row.get(field) for field in STEP_FIELDS} for row in status.run_steps]
	return run


@frappe.whitelist(methods=["POST"])
def start_company_setup(company, from_step=None):
	"""Start setup, or try again from a failed step."""
	frappe.has_permission("HMS TZ Setting", "write", throw=True)
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		frappe.throw(frappe._("Create the HMS TZ Setting of {0} first.").format(company))
	start_setup(setting, from_step)


def get_standard_record_counts(company):
	"""Counts of the standard records that HMS TZ creates in stage 1."""
	return {
		"insurers": frappe.db.count("Healthcare Insurance Company", {"company": company}),
		"plans": frappe.db.count("Healthcare Insurance Coverage Plan", {"company": company}),
		"schedules": frappe.db.count("Practitioner Schedule"),
		"room_types": frappe.db.count("Healthcare Room Type"),
	}
