# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


from frappe.utils import nowtime


def before_insert(doc, method):
	if doc.default_strength:
		doc.append(
			"dosage_strength",
			{
				"strength": abs(doc.default_strength),
				"strength_time": nowtime(),
			},
		)
