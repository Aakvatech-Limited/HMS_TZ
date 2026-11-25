from collections import Counter

import frappe
from frappe import _

from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_knowledge import (
	BED,
	CONSULTATION,
	ITEM_ONLY,
	TEMPLATE_DOCTYPES,
)
from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_template_mapping import create_mappings
from hms_tz.hms_tz.doctype.setup_action_run.setup_action_run import get_action_runs
from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords

MAPPING = "hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_template_mapping"
READ_ONLY = {"read_only": 1}
# The fields a user decides; the others come from NHIF and the classifier.
DECISION_FIELDS = ("proposed_doctype", "sub_kind", "medication_class", "modality_type")
# Statuses a user can still decide; Confirmed is being created and Created is done.
OPEN_STATUSES = ("Proposed", "Review", "Failed", "Ignored")
ACCEPT_DOCTYPES = (*TEMPLATE_DOCTYPES, CONSULTATION, BED, ITEM_ONLY)
ACCEPT_PREFIX = "accept:"
CLASSIFY_ACTION = {
	"key": "classify_nhif_codes",
	"label": "Classify new NHIF codes",
	"method": f"{MAPPING}.classify_new_nhif_items",
	"kwargs": {},
	"doctype": "NHIF Template Mapping",
}
RETRY_ACTION = {
	"key": "retry_failed_nhif_templates",
	"label": "Retry failed",
	"method": f"{MAPPING}.retry_failed",
	"kwargs": {},
	"doctype": "Item",
}


class NHIFTemplateMapping(CompanyRecords):
	"""Setup screen of the NHIF template mappings: what each NHIF code of the price package becomes.

	Saving a mapping confirms it with the chosen proposal and creates its records at once; Ignore creates
	nothing. The actions accept every open proposal of one doctype, retry failed mappings or classify new codes.
	"""

	doctype = "NHIF Template Mapping"
	company_field = None
	label = "NHIF template"
	plural_label = "NHIF templates"
	extra_fields = {
		"nhif_code": READ_ONLY,
		"nhif_item_name": READ_ONLY,
		"item_type_id": READ_ONLY,
		"service_type_id": READ_ONLY,
		"strength": READ_ONLY,
		"dosage": READ_ONLY,
		# No default, so the status filter starts empty instead of seeming to filter.
		"status": {**READ_ONLY, "default": None},
		"method": READ_ONLY,
		"score": READ_ONLY,
		"proposed_doctype": {},
		"sub_kind": {},
		"medication_class": {},
		"modality_type": {},
		"nearest_templates": READ_ONLY,
		"error": READ_ONLY,
	}
	list_filters = ("status", "proposed_doctype", "item_type_id", "nhif_item_name")
	page_length = 500
	has_setup_step = False
	has_add_actions = False
	# Review, Proposed, Ignored and Failed come before Created.
	order_by = "status desc, nhif_code asc"

	def save_record(self, values, name=None):
		"""Confirm the mapping with the user's decision, then create its records."""
		mapping = frappe.get_doc(self.doctype, name)
		if mapping.status not in OPEN_STATUSES:
			frappe.throw(_("NHIF code {0} is {1} and can no longer be changed.").format(name, mapping.status))
		decision = {field: values[field] for field in DECISION_FIELDS if field in values}
		if decision.get("proposed_doctype", mapping.proposed_doctype) != mapping.proposed_doctype:
			mapping.method = "Manual"
		mapping.update(decision)
		mapping.confirm()
		mapping.save()
		if mapping.status == "Confirmed":
			create_mappings(self.company, [name])
		return name

	@property
	def open_proposals(self):
		"""Open proposals per proposed doctype, for the accept actions."""
		return Counter(
			frappe.get_all(
				self.doctype, filters={"status": ["in", ["Proposed", "Review"]]}, pluck="proposed_doctype"
			)
		)

	@property
	def action_groups(self):
		"""Accept actions of the doctypes with open proposals, and of those that ran, so their last run shows."""
		counts = self.open_proposals
		runs = self.action_runs
		accept = [
			{"key": f"{ACCEPT_PREFIX}{doctype}", "label": f"{doctype} ({counts[doctype]})"}
			for doctype in ACCEPT_DOCTYPES
			if counts[doctype] or f"{ACCEPT_PREFIX}{doctype}" in runs
		]
		groups = [{"label": "Accept proposals", "actions": accept}] if accept else []
		other = [
			{"key": action["key"], "label": action["label"]} for action in (CLASSIFY_ACTION, RETRY_ACTION)
		]
		return [*groups, {"label": "NHIF codes", "actions": other}]

	@property
	def action_runs(self):
		keys = [f"{ACCEPT_PREFIX}{doctype}" for doctype in ACCEPT_DOCTYPES]
		return get_action_runs(self.company, [*keys, CLASSIFY_ACTION["key"], RETRY_ACTION["key"]])

	def get_action(self, key):
		if key in (CLASSIFY_ACTION["key"], RETRY_ACTION["key"]):
			return CLASSIFY_ACTION if key == CLASSIFY_ACTION["key"] else RETRY_ACTION
		doctype = key.removeprefix(ACCEPT_PREFIX)
		if not key.startswith(ACCEPT_PREFIX) or doctype not in ACCEPT_DOCTYPES:
			frappe.throw(_("{0} is not an action of the NHIF templates screen.").format(key))
		return {
			"key": key,
			"label": _("Accept {0} proposals").format(doctype),
			"method": f"{MAPPING}.accept_proposals",
			"kwargs": {"proposed_doctype": doctype},
			"doctype": doctype if doctype in TEMPLATE_DOCTYPES else "Item",
		}
