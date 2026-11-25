import frappe
from frappe import _

from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_knowledge import (
	BED,
	CONSULTATION,
	ITEM_ONLY,
	LAB,
	MEDICATION,
	PROCEDURE,
	RADIOLOGY,
	TEMPLATE_DOCTYPES,
	THERAPY,
	get_knowledge,
)
from hms_tz.hms_tz.standard_records.standard_records import create_template_masters

# Fields each template takes from its name; its controller names the Item after the first item code field.
NAME_FIELDS = {
	LAB: ("lab_test_name", "lab_test_code", "abbr"),
	RADIOLOGY: ("procedure_name", "item_code", "abbr", "description"),
	PROCEDURE: ("template", "item_code", "description"),
	MEDICATION: ("medication_name", "item_code", "description"),
	THERAPY: ("therapy_type", "item_code", "item_name"),
}
# The item group field of each template; Lab Test Template names it differently.
ITEM_GROUP_FIELDS = {LAB: "lab_test_group"}
DEFAULT_UOM = "Nos"
MAX_NAME_LENGTH = 140


class NHIFTemplateCreator:
	"""Creates what a confirmed NHIF Template Mapping proposes, and puts the NHIF code on each Item.

	A template or Item that already exists is only given the NHIF code; nothing else of it changes. Templates
	are inserted with missing mandatory values, which users complete on the template screens.
	"""

	def __init__(self, company):
		self.knowledge = get_knowledge()
		self.customer = frappe.db.get_value("HMS TZ Setting", {"company": company}, "nhif_customer_name")
		if not self.customer:
			frappe.throw(_("Set the NHIF customer of {0} in its HMS TZ Setting first.").format(company))
		create_template_masters(company)

	def create(self, mapping):
		"""Create or map the mapping's records and return them as created_records rows."""
		if self.is_known(mapping):
			return [self.add_known(row, mapping) for row in self.knowledge.rows_by_code[mapping.nhif_code]]
		if mapping.proposed_doctype in TEMPLATE_DOCTYPES:
			name = self.get_new_name(mapping)
			values = self.get_new_values(mapping)
			return [self.add_template(mapping.proposed_doctype, name, values, mapping.nhif_code)]
		if mapping.proposed_doctype == CONSULTATION:
			links = filter(None, [self.knowledge.get_consultation_link(mapping.nhif_item_name)])
			return [self.add_item(self.get_new_name(mapping), mapping.nhif_code, links)]
		if mapping.proposed_doctype in (BED, ITEM_ONLY):
			return [self.add_item(self.get_new_name(mapping), mapping.nhif_code)]
		frappe.throw(_("{0} creates nothing.").format(mapping.proposed_doctype))

	def is_known(self, mapping):
		"""Whether the shipped rows of the code apply: the user has not proposed something else for it."""
		return mapping.proposed_doctype == self.knowledge.get_known_proposal(mapping.nhif_code)

	def add_known(self, row, mapping):
		"""Create a shipped row's record, named after the NHIF item unless the row has a name of its own."""
		code = mapping.nhif_code
		if row["doctype"] in TEMPLATE_DOCTYPES:
			name = row.get("name") or self.get_new_name(mapping)
			values = {
				**row["values"],
				**{key: value for key, value in self.get_new_values(mapping).items() if value},
			}
			return self.add_template(row["doctype"], name, values, code)
		if row["doctype"] == "Item":
			return self.add_item(self.get_new_name(mapping), code, row.get("links", []))
		item = frappe.db.get_value(row["doctype"], row["name"], "item")
		if not item:
			frappe.throw(
				_("{0} {1} has no Item for the NHIF code {2}.").format(row["doctype"], row["name"], code)
			)
		self.add_code(item, code)
		return get_record(row["doctype"], row["name"], "Mapped")

	def add_template(self, doctype, name, values, code):
		if frappe.db.exists(doctype, name):
			self.add_code(frappe.db.get_value(doctype, name, "item"), code)
			return get_record(doctype, name, "Mapped")
		template = frappe.get_doc({"doctype": doctype, **self.get_template_values(doctype, name, values)})
		template.flags.ignore_mandatory = True
		template.insert(ignore_permissions=True)
		item = frappe.db.get_value(doctype, template.name, "item")
		if not item:
			frappe.throw(
				_("{0} {1} was created without its Item; see the Error Log.").format(doctype, template.name)
			)
		self.add_code(item, code)
		return get_record(doctype, template.name, "Created")

	def get_template_values(self, doctype, name, values):
		names = dict.fromkeys(NAME_FIELDS[doctype], name)
		group_field = ITEM_GROUP_FIELDS.get(doctype, "item_group")
		defaults = {group_field: self.knowledge.get_item_group(doctype), "is_billable": 0}
		if doctype == MEDICATION:
			defaults["stock_uom"] = DEFAULT_UOM
		return {**names, **defaults, **values}

	def get_new_values(self, mapping):
		"""Template values from the NHIF item and the mapping's proposal."""
		if mapping.proposed_doctype == RADIOLOGY:
			return {"modality_type": mapping.modality_type}
		if mapping.proposed_doctype == MEDICATION:
			return {
				"medication_class": mapping.medication_class,
				"strength_text": mapping.strength,
				**self.knowledge.get_dosage(mapping.dosage),
			}
		return {}

	def get_new_name(self, mapping):
		"""The NHIF item name, with the strength for a medication; the code is added when another code has the name."""
		name = " ".join((mapping.nhif_item_name or mapping.nhif_code).split())
		strength = (mapping.strength or "").strip()
		if mapping.proposed_doctype == MEDICATION and strength and strength.lower() not in name.lower():
			name = f"{name} {strength}"
		name = name[:MAX_NAME_LENGTH]
		doctype = mapping.proposed_doctype if mapping.proposed_doctype in TEMPLATE_DOCTYPES else "Item"
		if self.can_take_code(doctype, name, mapping.nhif_code):
			return name
		return f"{name[: MAX_NAME_LENGTH - len(mapping.nhif_code) - 3]} ({mapping.nhif_code})"

	def can_take_code(self, doctype, name, code):
		"""Whether the name is free, or names a record of the doctype whose Item has no other NHIF code yet."""
		if doctype != "Item" and frappe.db.exists(doctype, name):
			item = frappe.db.get_value(doctype, name, "item")
		elif frappe.db.exists("Item", name):
			if doctype != "Item":
				return False
			item = name
		else:
			return True
		return set(self.get_codes(item)) <= {code}

	def add_item(self, name, code, links=()):
		"""A service Item for consultations and charges, filling the empty visit type fields it belongs to."""
		action = "Mapped"
		if not frappe.db.exists("Item", name):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": name,
					"item_name": name,
					"description": name,
					"item_group": self.knowledge.get_item_group("Item"),
					"stock_uom": DEFAULT_UOM,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"include_item_in_manufacturing": 0,
				}
			).insert(ignore_permissions=True)
			action = "Created"
		self.add_code(name, code)
		for link in links:
			if frappe.db.exists(link["doctype"], link["name"]) and not frappe.db.get_value(
				link["doctype"], link["name"], link["field"]
			):
				frappe.db.set_value(link["doctype"], link["name"], link["field"], name)
		return get_record("Item", name, action)

	def get_codes(self, item):
		"""The NHIF codes the Item holds for the NHIF customer."""
		codes = frappe.get_all(
			"Item Customer Detail",
			filters={"parenttype": "Item", "parent": item, "customer_name": self.customer},
			pluck="ref_code",
		)
		return [code for code in codes if code]

	def add_code(self, item, code):
		"""Put the NHIF code on the Item for the NHIF customer; an Item holds one NHIF code."""
		if not item:
			frappe.throw(_("There is no Item to hold the NHIF code {0}.").format(code))
		codes = self.get_codes(item)
		if code in codes:
			return
		if codes:
			frappe.throw(_("Item {0} already has the NHIF code {1}.").format(item, ", ".join(codes)))
		item_doc = frappe.get_doc("Item", item)
		item_doc.append("customer_items", {"customer_name": self.customer, "ref_code": code})
		item_doc.save(ignore_permissions=True)


def get_record(doctype, name, action):
	return {"reference_doctype": doctype, "reference_name": name, "action": action}
