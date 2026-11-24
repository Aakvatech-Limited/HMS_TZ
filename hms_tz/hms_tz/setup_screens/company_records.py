from functools import cached_property

import frappe
from frappe import _
from frappe.core.doctype.data_import.exporter import Exporter
from frappe.core.doctype.data_import.importer import ImportFile
from frappe.utils import cint, strip_html

from hms_tz.api.setup import FIELD_KEYS, is_missing
from hms_tz.hms_tz.doctype.setup_status.setup_status import complete_setup_step, get_setup_status


class CompanyRecords:
	"""A setup screen of one company's records of one DocType: list, add, change, template and import.

	A screen subclass sets the DocType and its rules; the fields come from the DocType meta in form order.
	"""

	doctype = None
	company_field = "company"
	label = None
	plural_label = None
	# Fields asked besides the DocType's required ones, each with its screen rules, such as reqd or link_filters.
	extra_fields = {}
	# Values every record of the screen holds; they filter the list and are set on new records.
	fixed_values = {}
	# Field that finds an existing record when a template row is imported again.
	match_field = None

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
		return {self.company_field: self.company, **self.fixed_values}

	@property
	def title_field(self):
		return frappe.get_meta(self.doctype).title_field or "name"

	@property
	def records(self):
		return frappe.get_all(
			self.doctype,
			filters=self.filters,
			fields=list(dict.fromkeys(["name", self.title_field, *self.fieldnames])),
			order_by=f"{self.title_field} asc",
		)

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
		setting = self.unlocked_setting
		name = self.save_record(values, name)
		complete_setup_step(setting, self.doctype)
		return name

	def save_record(self, values, name=None):
		doc = frappe.get_doc(self.doctype, name) if name else frappe.new_doc(self.doctype)
		if name and any(doc.get(field) != value for field, value in self.filters.items()):
			frappe.throw(_("{0} is not a {1} of {2}.").format(name, self.label, self.company))
		# A template may leave out optional columns; those keep their current or default values.
		doc.update({fieldname: values[fieldname] for fieldname in self.fieldnames if fieldname in values})
		doc.update(self.filters)
		missing = [field["label"] for field in self.fields if is_missing(field, doc.as_dict())]
		if missing:
			frappe.throw(_("Fill in {0} before saving the {1}.").format(", ".join(missing), self.label))
		self.validate(doc)
		doc.save()
		return doc.name

	def validate(self, doc):
		"""Screen rules beyond the required fields; a subclass overrides it."""

	def download_template(self, samples="0", file_type="Excel"):
		"""Frappe's import template with the screen fields and, as samples, "all" or that many records."""
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
		setting = self.unlocked_setting
		import_file = ImportFile(self.doctype, file_url, import_type="Insert or Update Records")
		result = {"added": 0, "changed": 0, "errors": []}
		for payload in import_file.get_payloads_for_import():
			self.import_row(payload, result)
		if result["added"] or result["changed"]:
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
