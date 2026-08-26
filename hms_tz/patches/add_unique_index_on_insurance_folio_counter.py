"""Add a unique index to Insurance Folio Counter.

One counter row per company, period and insurance provider is what keeps
folio numbers sequential. Without the constraint two concurrent claims can
each create a counter for the same period and both reserve folio 1.
"""

import frappe


def execute():
	frappe.db.add_unique(
		"Insurance Folio Counter",
		["company", "claim_year", "claim_month", "insurance_provider"],
		constraint_name="unique_folio_counter_period",
	)
