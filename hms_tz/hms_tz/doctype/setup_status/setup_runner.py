import frappe
from frappe import _
from frappe.utils.background_jobs import is_job_enqueued

from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

# Steps that Start setup runs in order. Each method takes (hms_tz_setting, progress) and returns
# a short text of what it created. A step must only add what is missing, so it is safe to run again.
SETUP_RUNNER_STEPS = []

ROOMS_STEP = "Healthcare Service Unit"


class StepProgress:
	"""Progress of one running step, committed so the setup page shows it while the job runs."""

	def __init__(self, row_name):
		self.row_name = row_name
		self.done = 0

	def set_total(self, total):
		set_run_step(self.row_name, total=total)

	def advance(self, count=1):
		self.done += count
		set_run_step(self.row_name, done=self.done)


def get_runner_step(key):
	for step in SETUP_RUNNER_STEPS:
		if step["key"] == key:
			return step
	frappe.throw(_("{0} is not a setup runner step").format(key))


def sync_run_steps(status):
	"""Keep one run step row per runner step, in runner order, without losing the results of earlier runs."""
	rows = {row.step: row for row in status.run_steps}
	before = [(row.step, row.label) for row in status.run_steps]
	status.set("run_steps", [])
	for step in SETUP_RUNNER_STEPS:
		row = rows.get(step["key"])
		status.append("run_steps", row.as_dict() if row else {"step": step["key"], "status": "Waiting"})
		status.run_steps[-1].update({"label": step["label"], "idx": len(status.run_steps)})
	if [(row.step, row.label) for row in status.run_steps] != before:
		status.save(ignore_permissions=True)


def get_job_id(setting):
	return f"hms_tz_setup::{setting}"


def is_setup_running(setting):
	return is_job_enqueued(get_job_id(setting))


def start_setup(setting, from_step=None):
	"""Queue the runner from the first step, or from from_step to try a failed step again."""
	status = get_setup_status(setting)
	status.validate_settings_complete()
	if not status.get_step(ROOMS_STEP).completed:
		frappe.throw(_("Add at least one room before running the setup."), title=_("No Rooms"))
	if is_setup_running(setting):
		frappe.throw(_("The setup of {0} is already running.").format(setting))
	if from_step:
		get_runner_step(from_step)

	sync_run_steps(status)
	keys = [row.step for row in status.run_steps]
	start = keys.index(from_step) if from_step else 0
	for row in status.run_steps[start:]:
		row.update({"status": "Waiting", "done": 0, "total": 0, "result": None, "error": None})
	status.save(ignore_permissions=True)
	frappe.enqueue(
		"hms_tz.hms_tz.doctype.setup_status.setup_runner.run_setup",
		queue="long",
		timeout=3600,
		job_id=get_job_id(setting),
		enqueue_after_commit=True,
		setting=setting,
		from_step=from_step,
	)


def run_setup(setting, from_step=None):
	"""Background job: run the waiting steps in order and stop at the first failure."""
	status = get_setup_status(setting)
	keys = [row.step for row in status.run_steps]
	start = keys.index(from_step) if from_step else 0
	for row in status.run_steps[start:]:
		if not run_step(setting, row):
			break


def run_step(setting, row):
	set_run_step(row.name, status="Running", done=0, total=0, result=None, error=None)
	try:
		result = frappe.get_attr(get_runner_step(row.step)["method"])(setting, StepProgress(row.name))
	except Exception as error:
		frappe.db.rollback()
		frappe.log_error(
			title=_("Setup step {0} failed").format(row.label),
			reference_doctype="Setup Status",
			reference_name=setting,
		)
		set_run_step(row.name, status="Failed", error=str(error) or type(error).__name__)
		return False
	set_run_step(row.name, status="Done", result=result)
	return True


def set_run_step(row_name, **values):
	frappe.db.set_value("Setup Run Step", row_name, values)
	frappe.db.commit()  # nosemgrep: the setup page reads step progress while the job runs
