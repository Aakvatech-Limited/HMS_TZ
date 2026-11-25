from rapidfuzz import fuzz, process

from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_knowledge import (
	BED,
	CONSULTATION,
	CONSUMABLE,
	IGNORE,
	ITEM_ONLY,
	MEDICATION,
	RADIOLOGY,
	get_knowledge,
	get_row_name,
	normalise,
)

# A name match is sure from this score when it leads the next template type by the margin.
SURE_SCORE = 70
SURE_MARGIN = 12
MATCH_LIMIT = 15
NEAREST_COUNT = 3
# A label's best name score counts 60%, plus up to 40% for how often its NHIF type pair holds that label.
NAME_WEIGHT = 0.6
CAPITATION_TYPE = 19
CONSULTATION_TYPE = 1
BED_TYPE = 2
# NHIF item type and service type pairs that NHIF itself groups as imaging.
RULE_MODALITIES = {(5, 4): "MRI", (5, 10): "CT Scan"}


class NHIFClassifier:
	"""Proposes what an NHIF item becomes, in this order: an ignored type, a known code, a type rule, a name match.

	A proposal is sure (status Proposed) when it comes from a known code or a rule, or when its name match
	reaches the score and leads the next template type by the margin; otherwise it waits for Review.
	"""

	def __init__(self, extra_entries=()):
		self.knowledge = get_knowledge()
		self.entries = [*self.knowledge.match_entries, *extra_entries]
		self.names = [entry.name for entry in self.entries]

	def classify(self, item):
		"""Mapping values for an NHIF item with itemcode, itemname, itemtypeid, servicetypeid and dosage."""
		if item.itemtypeid == CAPITATION_TYPE:
			return get_result(IGNORE, "Ignored", "Rule")
		if item.itemcode in self.knowledge.rows_by_code:
			return self.get_known(item.itemcode)
		if item.itemtypeid == CONSULTATION_TYPE:
			return get_result(CONSULTATION, "Proposed", "Rule")
		if item.itemtypeid == BED_TYPE:
			return get_result(BED, "Review", "Rule")
		modality = RULE_MODALITIES.get((item.itemtypeid, item.servicetypeid))
		if modality:
			return get_result(RADIOLOGY, "Proposed", "Rule", modality_type=modality)
		return self.match(item)

	def get_known(self, code):
		"""The proposal of a code the shipped rows know, with the values of its first row of that doctype."""
		rows = self.knowledge.rows_by_code[code]
		proposal = self.knowledge.get_known_proposal(code)
		values = next((row.get("values", {}) for row in rows if row["doctype"] == proposal), {})
		medication_class = values.get("medication_class")
		return get_result(
			proposal,
			"Proposed",
			"Known code",
			score=100,
			matched_template_name="\n".join(get_row_name(row) for row in rows),
			medication_class=medication_class,
			sub_kind=self.knowledge.get_sub_kind(medication_class) if proposal == MEDICATION else None,
			modality_type=values.get("modality_type"),
		)

	def match(self, item):
		ranked = self.rank(item)
		if not ranked:
			return get_result(ITEM_ONLY, "Review", "Name match", score=0)
		score, (doctype, sub_kind), entry = ranked[0]
		values = {"matched_template_name": entry.template, "nearest_templates": get_nearest(ranked)}
		if doctype == RADIOLOGY:
			values["modality_type"] = self.knowledge.get_modality(item.itemname)
		if doctype == MEDICATION:
			values["medication_class"] = entry.medication_class
			values["sub_kind"] = sub_kind if item.dosage else CONSUMABLE
		second = ranked[1][0] if len(ranked) > 1 else 0
		is_sure = score >= SURE_SCORE and score - second >= SURE_MARGIN
		if doctype == RADIOLOGY and not values["modality_type"]:
			is_sure = False
		return get_result(
			doctype, "Proposed" if is_sure else "Review", "Name match", score=round(score), **values
		)

	def rank(self, item):
		"""Each template label's weighted score with its nearest entry, best first."""
		hits = process.extract(
			normalise(item.itemname), self.names, scorer=fuzz.token_set_ratio, limit=MATCH_LIMIT
		)
		best = {}
		for _name, score, index in hits:
			entry = self.entries[index]
			if entry.label not in best or score > best[entry.label][0]:
				best[entry.label] = (score, entry)
		shares = self.knowledge.type_shares.get((item.itemtypeid, item.servicetypeid), {})
		ranked = [
			(score * (NAME_WEIGHT + (1 - NAME_WEIGHT) * shares.get(label, 0)), label, entry)
			for label, (score, entry) in best.items()
		]
		return sorted(ranked, key=lambda row: row[0], reverse=True)


def get_nearest(ranked):
	return "\n".join(
		f"{label[0]}: {entry.template} ({round(score)})" for score, label, entry in ranked[:NEAREST_COUNT]
	)


def get_result(proposed_doctype, status, method, **values):
	return {"proposed_doctype": proposed_doctype, "status": status, "method": method, **values}
