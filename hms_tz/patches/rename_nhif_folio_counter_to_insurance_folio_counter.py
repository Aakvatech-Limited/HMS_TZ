# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""PRE-MODEL-SYNC: Rename NHIF Folio Counter → Insurance Folio Counter and backfill records.

	All three steps run before model sync:

	Step A — Rename the DocType (idempotent, guarded by existence check):
	    frappe.rename_doc() handles:
	      - Renaming the row in tabDocType
	      - Renaming the DB table (tabNHIF Folio Counter → tabInsurance Folio Counter)
	      - Updating all Link field values pointing to the old name

	Step B — Add the insurance_provider column manually:
	    Since this patch runs before model sync, the new column from
	    insurance_folio_counter.json does not exist yet. We add it here so
	    the backfill in Step C can succeed immediately.
	    Model sync will later sync the full column definition (label, options,
	    reqd, etc.) — adding a column that already exists is a no-op.

	Step C — Backfill insurance_provider = 'NHIF' on all pre-existing records:
	    Every record that existed before this rename was created by the NHIF
	    integration, so all of them receive insurance_provider = 'NHIF'.

	Idempotent: all steps are guarded so repeated bench migrate is safe.
	"""
	if frappe.db.exists("DocType", "NHIF Folio Counter"):
		frappe.rename_doc(
			"DocType",
			"NHIF Folio Counter",
			"Insurance Folio Counter",
			force=True,
		)
		frappe.db.commit()

	if not frappe.db.has_column("Insurance Folio Counter", "insurance_provider"):
		frappe.db.sql(
			"""
            ALTER TABLE `tabInsurance Folio Counter`
            ADD COLUMN `insurance_provider` VARCHAR(140) DEFAULT NULL
            """
		)
		frappe.db.commit()

	frappe.db.sql(
		"""
        UPDATE `tabInsurance Folio Counter`
        SET insurance_provider = 'NHIF'
        WHERE (insurance_provider IS NULL OR insurance_provider = '')
        """
	)
	frappe.db.commit()
