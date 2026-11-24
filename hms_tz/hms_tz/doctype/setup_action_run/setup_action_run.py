# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.background_jobs import is_job_enqueued

from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

RUN_FIELDS = ("action", "label", "status", "started_on", "finished_on", "result", "error", "error_log")


class SetupActionRun(Document):
	"""The latest background run of one setup screen action, such as an NHIF download."""


def get_job_id(company, key):
	return f"hms_tz_setup_action::{company}::{key}"


def get_setting(company):
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		frappe.throw(_("Create the HMS TZ Setting of {0} first.").format(company))
	return setting


def queue_action_run(company, action):
	"""Queue one action as a background job and mark its run row Queued.

	An action is a dict with key, label, method, kwargs and doctype, the DocType whose records it changes.
	"""
	if is_job_enqueued(get_job_id(company, action["key"])):
		frappe.throw(_("{0} is already running for {1}.").format(action["label"], company))
	row = get_run_row(get_setting(company), action)
	set_run(
		row,
		status="Queued",
		started_on=now_datetime(),
		finished_on=None,
		result=None,
		error=None,
		error_log=None,
	)
	frappe.enqueue(
		"hms_tz.hms_tz.doctype.setup_action_run.setup_action_run.run_action_job",
		queue="long",
		timeout=10800,
		job_id=get_job_id(company, action["key"]),
		enqueue_after_commit=True,
		company=company,
		row=row,
		action=action,
	)


def get_run_row(setting, action):
	"""The run row of the action on the Setup Status, added without saving the parent a parallel job may hold."""
	status = get_setup_status(setting)
	row = frappe.db.get_value("Setup Action Run", {"parent": status.name, "action": action["key"]})
	if row:
		return row
	return (
		frappe.get_doc(
			{
				"doctype": "Setup Action Run",
				"parent": status.name,
				"parenttype": "Setup Status",
				"parentfield": "action_runs",
				"action": action["key"],
				"label": action["label"],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def run_action_job(company, row, action):
	"""Background job: run the action and keep when it ran and how many records of its DocType it changed."""
	set_run(row, status="Running", started_on=now_datetime())
	before = count_records(action["doctype"], company)
	try:
		frappe.get_attr(action["method"])(company=company, **action["kwargs"])
	except Exception as error:
		frappe.db.rollback()
		error_log = frappe.log_error(
			title=_("{0} failed for {1}").format(action["label"], company),
			reference_doctype="HMS TZ Setting",
			reference_name=get_setting(company),
		)
		set_run(row, status="Failed", finished_on=now_datetime(), error=str(error), error_log=error_log.name)
		return
	after = count_records(action["doctype"], company)
	result = _("{0}: {1} → {2} ({3:+})").format(action["doctype"], before, after, after - before)
	set_run(row, status="Done", finished_on=now_datetime(), result=result)


def count_records(doctype, company):
	"""Records of the DocType, only the company's when the DocType has a company field."""
	filters = {"company": company} if frappe.get_meta(doctype).has_field("company") else {}
	return frappe.db.count(doctype, filters)


def set_run(row, **values):
	frappe.db.set_value("Setup Action Run", row, values)
	frappe.db.commit()  # nosemgrep: the screen reads the run while the job runs


def get_action_runs(company, keys):
	"""The latest run of each of the actions, keyed by action."""
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		return {}
	rows = frappe.get_all(
		"Setup Action Run",
		filters={"parent": setting, "parenttype": "Setup Status", "action": ["in", keys]},
		fields=list(RUN_FIELDS),
	)
	return {row.action: row for row in rows}
