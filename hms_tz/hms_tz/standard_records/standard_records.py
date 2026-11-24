import os
from datetime import datetime, timedelta

import frappe
from frappe import _

DATA_DIR = os.path.dirname(__file__)

# Standard record groups in creation order: ward types come before the service unit types and
# NHIF schemes before the plans that link to them. Each group is one setup runner step. The name
# field sets each record's name explicitly, because some sites name insurers by naming series.
STANDARD_RECORDS = [
	{
		"doctype": "Healthcare Ward Type",
		"file": "ward_types.json",
		"name_field": "ward_type_name",
		"label": "ward types",
	},
	{
		"doctype": "Healthcare Service Unit Type",
		"file": "service_unit_types.json",
		"name_field": "service_unit_type",
		"label": "service unit types",
	},
	{
		"doctype": "Healthcare Room Type",
		"file": "room_types.json",
		"name_field": "room_type_name",
		"label": "room types",
	},
	{
		"doctype": "Healthcare Card Verifier",
		"file": "card_verifiers.json",
		"name_field": "card_type_name",
		"label": "card verifiers",
	},
	{
		"doctype": "Appointment Type",
		"file": "visit_types.json",
		"name_field": "appointment_type",
		"label": "visit types",
	},
	{
		"doctype": "Practitioner Schedule",
		"file": "practitioner_schedules.json",
		"name_field": "schedule_name",
		"label": "practitioner schedules",
	},
	{
		"doctype": "NHIF Scheme",
		"file": "nhif_schemes.json",
		"name_field": "scheme_id",
		"label": "NHIF schemes",
	},
	{
		"doctype": "Healthcare Insurance Company",
		"file": "insurance_companies.json",
		"name_field": "insurance_company_name",
		"label": "insurance companies",
	},
	{
		"doctype": "Healthcare Insurance Coverage Plan",
		"file": "coverage_plans.json",
		"name_field": "coverage_plan_name",
		"label": "coverage plans",
	},
]

INSURERS_FILE = "insurance_companies.json"
PLANS_FILE = "coverage_plans.json"


def get_standard_record_steps():
	"""One setup runner step per standard record group; none of them needs a room."""
	return [
		{
			"key": group["file"].removesuffix(".json"),
			"label": group["label"][0].upper() + group["label"][1:],
			"method": "hms_tz.hms_tz.standard_records.standard_records.create_standard_records",
			"kwargs": {"doctype": group["doctype"]},
			"needs_rooms": False,
		}
		for group in STANDARD_RECORDS
	]


def create_standard_records(setting, progress, doctype):
	"""Setup runner step: add the missing records of one standard group for the setting's company."""
	company = frappe.db.get_value("HMS TZ Setting", setting, "company")
	return StandardRecords(company, progress).create(doctype)


def get_group(doctype):
	return next(group for group in STANDARD_RECORDS if group["doctype"] == doctype)


def load_records(file_name):
	return frappe.get_file_json(os.path.join(DATA_DIR, file_name))


class StandardRecords:
	"""Creates the standard records of the data files; records that already exist are left as they are.

	Insurers and their plans belong to a company, so their names end with the company abbreviation.
	That keeps two clinics on one site apart.
	"""

	def __init__(self, company, progress):
		self.company = company
		self.abbr = frappe.get_cached_value("Company", company, "abbr")
		self.progress = progress

	def create(self, doctype):
		"""Create one group's missing records and return how many the group holds, for example "10 visit types"."""
		group = get_group(doctype)
		rows = load_records(group["file"])
		self.progress.set_total(len(rows))
		for row in rows:
			self.progress.advance(added=int(self.insert(doctype, self.get_values(doctype, row))))
		return f"{len(rows)} {group['label']}"

	def get_values(self, doctype, row):
		if doctype == "Healthcare Insurance Company":
			return self.get_insurer_values(row)
		if doctype == "Healthcare Insurance Coverage Plan":
			return self.get_plan_values(row)
		if doctype == "Practitioner Schedule":
			return get_schedule_values(row)
		return dict(row)

	def get_company_name(self, name):
		return f"{name} - {self.abbr}"

	def get_insurer_values(self, row):
		receivable, write_off = frappe.get_cached_value(
			"Company", self.company, ["default_receivable_account", "write_off_account"]
		)
		if not (receivable and write_off):
			frappe.throw(
				_("Set the Default Receivable Account and Write Off Account of {0} first.").format(
					self.company
				)
			)
		return {
			"insurance_company_name": self.get_company_name(row["insurance_company_name"]),
			"company": self.company,
			"billed_but_not_claimed_account": receivable,
			"approved_claim_receivable_account": receivable,
			"rejected_claims_account": write_off,
		}

	def get_plan_values(self, row):
		return {
			**row,
			"coverage_plan_name": self.get_company_name(row["coverage_plan_name"]),
			"insurance_company": self.get_company_name(row["insurance_company"]),
			"company": self.company,
			"is_active": 1,
		}

	def insert(self, doctype, values):
		"""Create the record when it is missing and return whether it was created; never change an existing one."""
		name = values[get_group(doctype)["name_field"]]
		if frappe.db.exists(doctype, name):
			return False
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True, set_name=name)
		return True


def get_schedule_values(row):
	"""A schedule row of the data file as Practitioner Schedule values, with one time slot per slot_minutes."""
	slot = timedelta(minutes=row["slot_minutes"])
	time_slots = []
	for hours in row["hours"]:
		start, end = (datetime.strptime(hours[key], "%H:%M:%S") for key in ("from_time", "to_time"))
		for day in hours["days"]:
			current = start
			while current < end:
				slot_end = min(current + slot, end)
				time_slots.append({"day": day, "from_time": current.time(), "to_time": slot_end.time()})
				current = slot_end
	return {"schedule_name": row["schedule_name"], "time_slots": time_slots}
