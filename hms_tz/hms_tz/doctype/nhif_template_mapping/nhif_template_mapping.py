# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import now_datetime

from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_classifier import NHIFClassifier
from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_knowledge import (
	IGNORE,
	TEMPLATE_DOCTYPES,
	get_entry,
	get_knowledge,
)
from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_template_creator import NHIFTemplateCreator
from hms_tz.hms_tz.standard_records.standard_records import create_template_masters

NHIF_ITEM_FIELDS = ("itemcode", "itemname", "itemtypeid", "servicetypeid", "strength", "dosage")


class NHIFTemplateMapping(Document):
	"""What one NHIF code becomes on the site: the proposal, the user's decision and the records it made."""

	def confirm(self):
		"""Accept the proposal; Ignore needs no records, anything else waits to be created."""
		self.status = "Ignored" if self.proposed_doctype == IGNORE else "Confirmed"
		self.confirmed_by = frappe.session.user
		self.confirmed_on = now_datetime()

	def set_created(self, records):
		self.status = "Created"
		self.error = None
		self.set("created_records", records)
		self.save(ignore_permissions=True)

	def set_failed(self, error):
		self.status = "Failed"
		self.error = error
		self.save(ignore_permissions=True)


def classify_new_nhif_items(company):
	"""Add a mapping for each active NHIF item of the company's price package that has none yet."""
	create_template_masters(company)
	classifier = NHIFClassifier(extra_entries=get_confirmed_entries())
	items = get_new_nhif_items(company)
	for item in items:
		frappe.get_doc(
			{
				"doctype": "NHIF Template Mapping",
				"nhif_code": item.itemcode,
				"nhif_item_name": item.itemname,
				"item_type_id": item.itemtypeid,
				"service_type_id": item.servicetypeid,
				"strength": item.strength,
				"dosage": item.dosage,
				**classifier.classify(item),
			}
		).insert(ignore_permissions=True)
	return len(items)


def get_new_nhif_items(company):
	"""Active NHIF items priced for the company that have no mapping, one per code."""
	nhif_item = DocType("NHIF Item")
	package = DocType("NHIF Price Package")
	mapping = DocType("NHIF Template Mapping")
	rows = (
		frappe.qb.from_(nhif_item)
		.select(*[nhif_item[field] for field in NHIF_ITEM_FIELDS])
		.where(nhif_item.isactive == 1)
		.where(
			nhif_item.itemcode.isin(
				frappe.qb.from_(package).select(package.itemcode).where(package.company == company)
			)
		)
		.where(nhif_item.itemcode.notin(frappe.qb.from_(mapping).select(mapping.nhif_code)))
		.orderby(nhif_item.itemcode)
	).run(as_dict=True)
	return list({row.itemcode: row for row in rows}.values())


def get_confirmed_entries():
	"""Name match entries of the templates users confirmed on this site, so later downloads need less review."""
	knowledge = get_knowledge()
	rows = frappe.get_all(
		"NHIF Template Mapping",
		filters={"confirmed_by": ["is", "set"], "proposed_doctype": ["in", TEMPLATE_DOCTYPES]},
		fields=["nhif_item_name", "proposed_doctype", "medication_class"],
	)
	return [
		get_entry(row.proposed_doctype, row.nhif_item_name, row.medication_class, knowledge) for row in rows
	]


def create_mappings(company, names):
	"""Create the records of the mappings; a failed mapping keeps its error and the others go on."""
	creator = NHIFTemplateCreator(company)
	return [create_mapping(creator, name) for name in names]


def create_mapping(creator, name):
	mapping = frappe.get_doc("NHIF Template Mapping", name)
	frappe.db.savepoint("nhif_template_mapping")
	try:
		mapping.set_created(creator.create(mapping))
	except Exception as error:
		frappe.db.rollback(save_point="nhif_template_mapping")
		frappe.log_error(
			title=_("NHIF template creation failed for {0}").format(name),
			reference_doctype="NHIF Template Mapping",
			reference_name=name,
		)
		mapping.reload()
		mapping.set_failed(str(error))
	finally:
		frappe.clear_messages()
	return mapping.status


def confirm_and_create(company, filters):
	"""Confirm the mappings that match the filters, then create their records."""
	names = frappe.get_all("NHIF Template Mapping", filters=filters, pluck="name", order_by="nhif_code asc")
	to_create = []
	for name in names:
		mapping = frappe.get_doc("NHIF Template Mapping", name)
		mapping.confirm()
		mapping.save(ignore_permissions=True)
		if mapping.status == "Confirmed":
			to_create.append(name)
	return create_mappings(company, to_create)


def accept_proposals(company, proposed_doctype):
	"""Screen action: accept every proposed or review mapping of one proposed doctype and create its records."""
	confirm_and_create(
		company, {"status": ["in", ["Proposed", "Review"]], "proposed_doctype": proposed_doctype}
	)


def retry_failed(company):
	"""Screen action: confirm and create again every failed mapping."""
	confirm_and_create(company, {"status": "Failed"})


def create_nhif_templates(setting, progress):
	"""Setup runner step: classify the company's NHIF items, then create every sure proposal."""
	company = frappe.db.get_value("HMS TZ Setting", setting, "company")
	if not frappe.db.get_value("HMS TZ Setting", setting, "enable_nhif_api"):
		return _("NHIF is off")
	if not frappe.db.exists("NHIF Price Package", {"company": company}) or not frappe.db.count("NHIF Item"):
		frappe.throw(
			_("Get the NHIF items and the NHIF price package of {0} on the Insurers screen first.").format(
				company
			)
		)
	classify_new_nhif_items(company)
	names = frappe.get_all(
		"NHIF Template Mapping", filters={"status": "Proposed"}, pluck="name", order_by="nhif_code asc"
	)
	progress.set_total(len(names))
	creator = NHIFTemplateCreator(company)
	for name in names:
		progress.advance(added=int(create_mapping(creator, name) == "Created"))
	return get_summary()


def get_summary():
	"""Mappings per status, for example "120 created, 30 review"."""
	counts = Counter(frappe.get_all("NHIF Template Mapping", pluck="status"))
	return ", ".join(f"{count} {status.lower()}" for status, count in sorted(counts.items()))
