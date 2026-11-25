from functools import cached_property

import frappe

from hms_tz.hms_tz.setup_screens.company_records import CompanyRecords


class NHIFItem(CompanyRecords):
	"""Read-only setup screen of the NHIF Items, the NHIF catalogue that all companies share.

	The Get NHIF Items action of the Insurers screen downloads them, so they are only viewed here. The list
	shows the item type and service type names next to their NHIF IDs.
	"""

	doctype = "NHIF Item"
	company_field = None
	label = "NHIF item"
	plural_label = "NHIF items"
	extra_fields = {
		"itemcode": {},
		"itemtypeid": {},
		"itemname": {},
		"strength": {},
		"dosage": {},
		"isactive": {},
		"isrestricted": {},
		"servicetypeid": {},
		"commonprice": {},
	}
	list_filters = ("itemcode", "itemtypeid", "itemname", "isactive", "servicetypeid")
	page_length = 500
	has_setup_step = False
	has_add_actions = False
	is_read_only = True
	order_by = "itemcode asc"
	# NHIF Item is named by hash, so the item name titles the view.
	title_field = "itemname"
	# Name columns shown after the NHIF ID they describe; they come from the type DocTypes, not NHIF Item.
	type_name_fields = {
		"itemtypeid": {"fieldname": "item_type", "label": "Item type"},
		"servicetypeid": {"fieldname": "service_type", "label": "Service type"},
	}

	@cached_property
	def fields(self):
		fields = []
		for field in super().fields:
			fields.append(field)
			if field["fieldname"] in self.type_name_fields:
				name_field = self.type_name_fields[field["fieldname"]]
				fields.append({**field, **name_field, "fieldtype": "Data", "options": None})
		return fields

	@cached_property
	def fieldnames(self):
		name_fields = {field["fieldname"] for field in self.type_name_fields.values()}
		return [field["fieldname"] for field in self.fields if field["fieldname"] not in name_fields]

	def get_records(self, list_filters=None):
		result = super().get_records(list_filters)
		item_types = dict(
			frappe.get_all("NHIF Item Type", fields=["item_type_id", "type_name"], as_list=True)
		)
		service_types = dict(
			frappe.get_all("NHIF Service Type", fields=["service_type_id", "service_type_name"], as_list=True)
		)
		for record in result["records"]:
			record.item_type = item_types.get(record.itemtypeid)
			record.service_type = service_types.get(str(record.servicetypeid))
		return result
