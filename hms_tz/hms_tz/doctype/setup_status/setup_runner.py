import frappe
from frappe import _
from frappe.utils.background_jobs import is_job_enqueued

from hms_tz.hms_tz.doctype.setup_status.foundation import FOUNDATION_STEP
from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status
from hms_tz.hms_tz.standard_records.standard_records import get_standard_record_steps

# Steps that Start setup runs in order. Each method takes (hms_tz_setting, progress, **kwargs) and
# returns a short text of what it holds. A step must only add what is missing and never change
# existing records, so it is safe to run again; it counts what it adds with progress.advance(added=).
# A step runs only once a room exists unless it sets "needs_rooms": False.
SETUP_RUNNER_STEPS = [FOUNDATION_STEP, *get_standard_record_steps()]

# Other installed apps add steps of the same shape to their hooks.py; they run after the HMS TZ steps:
# hms_tz_setup_steps = [{"key": "clinic_rules", "label": "Clinic rules", "method": "app.setup.set_rules"}]
STEPS_HOOK = "hms_tz_setup_steps"

ROOMS_STEP = "Healthcare Service Unit"
PROGRESS_EVENT = "hms_tz_setup_progress"


class StepProgress:
	"""Progress of one running step, committed so the setup page shows it while the job runs."""

	def __init__(self, row):
		self.row = row
		self.done = 0
		self.added = 0

	def set_total(self, total):
		set_run_step(self.row, total=total)

	def advance(self, count=1, added=0):
		"""Move on by count records, of which added were missing and created now."""
		self.done += count
		self.added += added
		set_run_step(self.row, done=self.done, added=self.added)


def get_runner_steps():
	"""The HMS TZ steps, then the steps each other installed app registers, each marked with its app."""
	steps = [{**step, "app": "hms_tz"} for step in SETUP_RUNNER_STEPS]
	for app in frappe.get_installed_apps():
		if app != "hms_tz":
			steps += [{**step, "app": app} for step in frappe.get_hooks(STEPS_HOOK, app_name=app)]
	keys = [step["key"] for step in steps]
	duplicates = sorted({key for key in keys if keys.count(key) > 1})
	if duplicates:
		frappe.throw(_("Setup steps registered more than once: {0}").format(", ".join(duplicates)))
	return steps


def get_runner_step(key):
	for step in get_runner_steps():
		if step["key"] == key:
			return step
	frappe.throw(_("{0} is not a setup runner step").format(key))


def sync_run_steps(status):
	"""Keep one run step row per runner step, in runner order, without losing the results of earlier runs."""
	rows = {row.step: row for row in status.run_steps}
	before = [(row.step, row.label, row.app) for row in status.run_steps]
	status.set("run_steps", [])
	for step in get_runner_steps():
		row = rows.get(step["key"])
		status.append("run_steps", row.as_dict() if row else {"step": step["key"], "status": "Waiting"})
		status.run_steps[-1].update(
			{"label": step["label"], "app": step["app"], "idx": len(status.run_steps)}
		)
	if [(row.step, row.label, row.app) for row in status.run_steps] != before:
		status.save(ignore_permissions=True)


def get_job_id(setting):
	return f"hms_tz_setup::{setting}"


def is_setup_running(setting):
	return is_job_enqueued(get_job_id(setting))


def start_setup(setting, from_step=None):
	"""Queue the runner from the first step, or from from_step to try a failed step again."""
	status = get_setup_status(setting)
	status.validate_settings_complete()
	if is_setup_running(setting):
		frappe.throw(_("The setup of {0} is already running.").format(setting))
	if from_step:
		get_runner_step(from_step)

	sync_run_steps(status)
	keys = [row.step for row in status.run_steps]
	start = keys.index(from_step) if from_step else 0
	for row in status.run_steps[start:]:
		row.update({"status": "Waiting", "done": 0, "total": 0, "added": 0, "result": None, "error": None})
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
	set_run_step(row, status="Running", done=0, total=0, added=0, result=None, error=None)
	step = get_runner_step(row.step)
	try:
		if step.get("needs_rooms", True) and not get_setup_status(setting).get_step(ROOMS_STEP).completed:
			frappe.throw(_("Add at least one room on the rooms screen, then try again."))
		result = frappe.get_attr(step["method"])(setting, StepProgress(row), **step.get("kwargs", {}))
	except Exception as error:
		frappe.db.rollback()
		frappe.log_error(
			title=_("Setup step {0} failed").format(row.label),
			reference_doctype="Setup Status",
			reference_name=setting,
		)
		set_run_step(row, status="Failed", error=str(error) or type(error).__name__)
		return False
	set_run_step(row, status="Done", result=result)
	return True


def set_run_step(row, **values):
	"""Save a step's progress and push it to the setup page of the user who started the run."""
	frappe.db.set_value("Setup Run Step", row.name, values)
	frappe.db.commit()  # nosemgrep: the setup page reads step progress while the job runs
	message = {"setting": row.parent, "step": row.step, **values}
	frappe.publish_realtime(PROGRESS_EVENT, message, user=frappe.session.user)
