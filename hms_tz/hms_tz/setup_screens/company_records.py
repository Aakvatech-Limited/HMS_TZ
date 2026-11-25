from functools import cached_property

import frappe
from frappe import _
from frappe.core.doctype.data_import.exporter import Exporter
from frappe.core.doctype.data_import.importer import ImportFile
from frappe.utils import cint, strip_html

from hms_tz.api.setup import FIELD_KEYS, is_missing
from hms_tz.hms_tz.doctype.setup_action_run.setup_action_run import queue_action_run
from hms_tz.hms_tz.doctype.setup_status.setup_status import complete_setup_step, get_setup_status


class CompanyRecords:
	"""A setup screen of one company's records of one DocType: list, add, change, template and import.

	A screen subclass sets the DocType and its rules; the fields come from the DocType meta in form order.
	"""

	doctype = None
	# None for a DocType shared by all companies; the company then only unlocks the screen.
	company_field = "company"
	label = None
	plural_label = None
	# Fields asked besides the DocType's required ones, each with its screen rules, such as reqd, link_filters
	# or set_only_once for a field that names the record and stays fixed once it exists.
	extra_fields = {}
	# Values every record of the screen holds; they filter the list and are set on new records.
	fixed_values = {}
	# Field that finds an existing record when a template row is imported again.
	match_field = None
	# Fields the list can be filtered by, shown above it; a screen with many records sets them and page_length.
	list_filters = ()
	# Most records the list shows at once; None shows all.
	page_length = None
	# Whether saving ticks the Setup Status step named after the DocType; False for a DocType with no step.
	has_setup_step = True
	# Whether users add records here, by hand or by template; False when records only come from an API.
	has_add_actions = True
	# Whether records are only viewed here, never added or changed; such a screen also sets has_add_actions False.
	is_read_only = False
	# List order; None sorts by the title field.
	order_by = None
	# Child table shown, read only, when a record is viewed, with the child fields it shows.
	child_table = None
	child_fields = ()
	child_page_length = 500

	def __init__(self, company):
		self.company = company

	@cached_property
	def fields(self):
		hidden = {self.company_field, *self.fixed_values}
		fields = []
		for docfield in frappe.get_meta(self.doctype).fields:
			if docfield.fieldname in hidden or not (docfield.reqd or docfield.fieldname in self.extra_fields):
				continue
			field = {key: docfield.get(key) for key in FIELD_KEYS}
			field.update(self.extra_fields.get(docfield.fieldname, {}), doctype=self.doctype)
			if isinstance(field["link_filters"], list):
				field["link_filters"] = frappe.as_json(field["link_filters"], indent=None)
			fields.append(field)
		return fields

	@cached_property
	def fieldnames(self):
		return [field["fieldname"] for field in self.fields]

	@property
	def filters(self):
		if not self.company_field:
			return dict(self.fixed_values)
		return {self.company_field: self.company, **self.fixed_values}

	@property
	def title_field(self):
		return frappe.get_meta(self.doctype).title_field or "name"

	@property
	def list_filter_fields(self):
		return [{**field, "reqd": 0} for field in self.fields if field["fieldname"] in self.list_filters]

	def get_records(self, list_filters=None):
		"""The company's records matching the list filters, at most page_length, and whether more match."""
		values = {field: value for field, value in (list_filters or {}).items() if value}
		unknown = set(values) - set(self.list_filters)
		if unknown:
			frappe.throw(
				_("{0} cannot filter the {1}.").format(", ".join(sorted(unknown)), self.plural_label)
			)
		conditions = {field: self.get_filter_condition(field, value) for field, value in values.items()}
		records = frappe.get_all(
			self.doctype,
			filters={**conditions, **self.filters},
			fields=list(dict.fromkeys(["name", self.title_field, *self.fieldnames])),
			order_by=self.order_by or f"{self.title_field} asc",
			limit_page_length=(self.page_length + 1) if self.page_length else 0,
		)
		has_more = bool(self.page_length) and len(records) > self.page_length
		return {"records": records[: self.page_length] if has_more else records, "has_more": has_more}

	def get_filter_condition(self, fieldname, value):
		"""A text filter matches any part of the field, so a name or code can be searched; others match exactly."""
		if frappe.get_meta(self.doctype).get_field(fieldname).fieldtype == "Data":
			return ["like", f"%{value}%"]
		return value

	@property
	def unlocked_setting(self):
		"""The company's HMS TZ Setting once its settings page is complete; records stay locked before that."""
		setting = frappe.db.get_value("HMS TZ Setting", {"company": self.company})
		if not setting:
			frappe.throw(_("Create the HMS TZ Setting of {0} first.").format(self.company))
		get_setup_status(setting).validate_settings_complete()
		return setting

	def save(self, values, name=None):
		"""Add a record, or change one of the company's records, and tick the DocType's setup step."""
		if self.is_read_only:
			frappe.throw(_("{0} are not changed on this screen.").format(self.plural_label))
		setting = self.unlocked_setting
		if not name:
			self.validate_add_actions()
		name = self.save_record(values, name)
		if self.has_setup_step:
			complete_setup_step(setting, self.doctype)
		return name

	def save_record(self, values, name=None):
		doc = frappe.get_doc(self.doctype, name) if name else frappe.new_doc(self.doctype)
		if name and any(doc.get(field) != value for field, value in self.filters.items()):
			frappe.throw(_("{0} is not one of the {1} of {2}.").format(name, self.plural_label, self.company))
		# A template may leave out optional columns; those keep their current or default values.
		fixed = {field["fieldname"] for field in self.fields if name and field.get("set_only_once")}
		doc.update(
			{field: values[field] for field in self.fieldnames if field in values and field not in fixed}
		)
		doc.update(self.filters)
		missing = [field["label"] for field in self.fields if is_missing(field, doc.as_dict())]
		if missing:
			frappe.throw(_("Fill in {0} before saving the {1}.").format(", ".join(missing), self.label))
		self.validate(doc)
		doc.save()
		return doc.name

	@property
	def action_groups(self):
		"""Dropdowns of actions the screen offers for the company, as [{"label", "actions": [{"key", "label"}]}]."""
		return []

	@property
	def action_runs(self):
		"""The latest background run of each action of the screen, keyed by action."""
		return {}

	def get_action(self, key):
		"""One action of action_groups with its method, kwargs and doctype; a screen with actions overrides it."""
		frappe.throw(_("The {0} screen has no action {1}.").format(self.plural_label, key))

	def run_action(self, key):
		"""Queue one action as a background job; its run is kept on the company's Setup Status."""
		queue_action_run(self.company, self.get_action(key))

	def validate(self, doc):
		"""Screen rules beyond the required fields; a subclass overrides it."""

	def get_child_rows(self, name, start=0):
		"""One page of a record's child table rows, read only, with their fields and the total row count."""
		if not self.child_table:
			frappe.throw(_("{0} have no rows to view.").format(self.plural_label))
		if not frappe.db.exists(self.doctype, {**self.filters, "name": name}):
			frappe.throw(_("{0} is not one of the {1} of {2}.").format(name, self.plural_label, self.company))
		child_doctype = frappe.get_meta(self.doctype).get_field(self.child_table).options
		child_meta = frappe.get_meta(child_doctype)
		filters = {"parenttype": self.doctype, "parentfield": self.child_table, "parent": name}
		return {
			"fields": [
				{
					"fieldname": field,
					"label": child_meta.get_label(field),
					"fieldtype": child_meta.get_field(field).fieldtype,
				}
				for field in self.child_fields
			],
			"rows": frappe.get_all(
				child_doctype,
				filters=filters,
				fields=list(self.child_fields),
				order_by="idx asc",
				limit_start=cint(start),
				limit_page_length=self.child_page_length,
			),
			"total": frappe.db.count(child_doctype, filters),
		}

	def validate_add_actions(self):
		if not self.has_add_actions:
			frappe.throw(_("{0} are not added on this screen.").format(self.plural_label))

	def download_template(self, samples="0", file_type="Excel"):
		"""Frappe's import template with the screen fields and, as samples, "all" or that many records."""
		self.validate_add_actions()
		exporter = Exporter(
			self.doctype,
			export_fields={self.doctype: self.fieldnames},
			export_data=samples == "all" or cint(samples) > 0,
			export_filters=self.filters,
			export_page_length=None if samples == "all" else cint(samples),
			file_type=file_type,
		)
		exporter.build_response()

	def import_file(self, file_url):
		"""Add or change records from a filled template; a failed row is reported and skipped."""
		self.validate_add_actions()
		setting = self.unlocked_setting
		import_file = ImportFile(self.doctype, file_url, import_type="Insert or Update Records")
		result = {"added": 0, "changed": 0, "errors": []}
		for payload in import_file.get_payloads_for_import():
			self.import_row(payload, result)
		if self.has_setup_step and (result["added"] or result["changed"]):
			complete_setup_step(setting, self.doctype)
		return result

	def import_row(self, payload, result):
		frappe.db.savepoint("setup_import_row")
		try:
			name = self.get_existing_name(payload.doc)
			self.save_record(payload.doc, name)
			result["changed" if name else "added"] += 1
		except frappe.ValidationError as error:
			frappe.db.rollback(save_point="setup_import_row")
			result["errors"].append({"row": payload.rows[0].row_number, "message": strip_html(str(error))})
		finally:
			frappe.clear_messages()

	def get_existing_name(self, values):
		"""The company's record with the row's match field value, so a re-import changes it."""
		value = self.match_field and values.get(self.match_field)
		if not value:
			return None
		return frappe.db.get_value(self.doctype, {**self.filters, self.match_field: value})
