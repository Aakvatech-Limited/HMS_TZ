import re
from collections import Counter, defaultdict
from functools import cache, cached_property

import frappe

from hms_tz.hms_tz.standard_records.standard_records import load_records

LAB = "Lab Test Template"
RADIOLOGY = "Radiology Examination Template"
PROCEDURE = "Clinical Procedure Template"
MEDICATION = "Medication"
THERAPY = "Therapy Type"
TEMPLATE_DOCTYPES = (LAB, RADIOLOGY, PROCEDURE, MEDICATION, THERAPY)
CONSULTATION = "Consultation Item"
BED = "Bed Item"
ITEM_ONLY = "Item Only"
IGNORE = "Ignore"
CONSUMABLE = "Consumable"
DRUG = "Drug"
# Shipped rows that are not templates, and the proposal they stand for.
KNOWN_PROPOSALS = {"Item": CONSULTATION, "Healthcare Service Unit Type": BED}


def normalise(text):
	"""Lower-case words without punctuation, for name matching."""
	return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


@cache
def get_knowledge():
	"""The shipped knowledge; the files only change with the app, so one copy serves the process."""
	return NHIFKnowledge()


class NHIFKnowledge:
	"""NHIF template rows exported from a reference site, and the rules that turn NHIF items into templates.

	Each row ties an NHIF code to a template, a consultation Item or a bed service unit type. Records are named
	after the NHIF item, so a row has a name only where NHIF cannot give one: a bed row names its service unit
	type, and each physiotherapy Therapy Type that shares one NHIF code has its own name.
	"""

	def __init__(self):
		self.rows = load_records("nhif_template_codes.json")
		self.rules = load_records("nhif_template_rules.json")

	@cached_property
	def rows_by_code(self):
		rows = defaultdict(list)
		for row in self.rows:
			rows[row["nhif_code"]].append(row)
		return dict(rows)

	def get_known_proposal(self, code):
		"""What the shipped rows of a code mostly are, or None for a code the reference site did not use."""
		rows = self.rows_by_code.get(code)
		if not rows:
			return None
		proposals = Counter(KNOWN_PROPOSALS.get(row["doctype"], row["doctype"]) for row in rows)
		return proposals.most_common(1)[0][0]

	def get_sub_kind(self, medication_class):
		return CONSUMABLE if medication_class in self.rules["consumable_classes"] else DRUG

	@cached_property
	def match_entries(self):
		"""Name match pool: each template row under its own name, or else its NHIF item name."""
		return [
			get_entry(row["doctype"], get_row_name(row), row["values"].get("medication_class"), self)
			for row in self.rows
			if row["doctype"] in TEMPLATE_DOCTYPES
		]

	@cached_property
	def type_shares(self):
		"""Share of each template label among the known codes of an NHIF item type and service type pair."""
		counts = defaultdict(Counter)
		for rows in self.rows_by_code.values():
			row = rows[0]
			if row["doctype"] in TEMPLATE_DOCTYPES:
				label = get_label(row["doctype"], row["values"].get("medication_class"), self)
				counts[(row["item_type_id"], row["service_type_id"])][label] += 1
		return {
			pair: {label: count / sum(labels.values()) for label, count in labels.items()}
			for pair, labels in counts.items()
		}

	def get_modality(self, name):
		"""Modality from the keywords of an NHIF item name, or None when no keyword matches."""
		text = (name or "").lower()
		return next(
			(modality for pattern, modality in self.rules["modalities"] if re.search(pattern, text)), None
		)

	def get_dosage(self, dosage):
		"""Dosage form and stock UOM of an NHIF dosage text; empty for text the rules do not know."""
		return self.rules["dosages"].get((dosage or "").strip().lower(), {})

	def get_item_group(self, doctype):
		return self.rules["item_groups"][doctype]

	def get_consultation_link(self, name):
		"""The visit type field a consultation Item fills, such as gp_followup_item, from its NHIF name."""
		rules = self.rules["consultations"]
		text = (name or "").lower()
		level = next((level for pattern, level in rules["levels"] if re.search(pattern, text)), None)
		kinds = [kind for pattern, kind in rules["kinds"] if re.search(pattern, text)]
		if not level or len(kinds) != 1:
			return None
		return {
			"doctype": "Appointment Type",
			"name": rules["appointment_type"],
			"field": f"{level}_{kinds[0]}_item",
		}


def get_row_name(row):
	return row.get("name") or row["nhif_item_name"]


def get_label(doctype, medication_class, knowledge):
	"""Template doctype and, for Medication, whether it is a drug or a consumable."""
	sub_kind = knowledge.get_sub_kind(medication_class) if doctype == MEDICATION else None
	return (doctype, sub_kind)


def get_entry(doctype, template, medication_class, knowledge):
	return frappe._dict(
		name=normalise(template),
		label=get_label(doctype, medication_class, knowledge),
		template=template,
		medication_class=medication_class,
	)
