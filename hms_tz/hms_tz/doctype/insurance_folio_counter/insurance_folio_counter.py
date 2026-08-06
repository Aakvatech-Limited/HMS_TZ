# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.utils import cint, now_datetime

ifc = DocType("Insurance Folio Counter")


class InsuranceFolioCounter(Document):
    pass


def get_or_create_folio_counter(doc, insurance_provider: str) -> int:
    """Reserve the next folio number for an insurance claim.

    The counter is advanced by a single `folio_no = folio_no + 1` statement.
    Reading the value first and writing back the increment would let two
    concurrent claims reserve the same folio number, because a plain SELECT
    takes no row lock and both would read the same value before either wrote.

    Args:
        doc: The parent claim document (must have company, claim_year,
             claim_month attributes).
        insurance_provider: One of 'NHIF', 'Jubilee', 'Strategies',
                            'Assembly'.

    Returns:
        int: The folio number reserved for this claim.
    """
    counter_name = get_folio_counter_name(doc, insurance_provider)

    (
        frappe.qb.update(ifc)
        .set(ifc.folio_no, ifc.folio_no + 1)
        .set(ifc.posting_date, now_datetime())
        .set(ifc.modified, now_datetime())
        .where(ifc.name == counter_name)
    ).run()

    # The update above holds an exclusive lock on the row until this
    # transaction commits, so no other claim can change it before this read.
    return cint(frappe.db.get_value("Insurance Folio Counter", counter_name, "folio_no"))


def get_folio_counter_name(doc, insurance_provider: str) -> str:
    """Return the counter for this company, period and provider, creating it if missing.

    New counters start at zero so that the increment above issues folio 1 to
    the first claim of the period.
    """
    filters = {
        "company": doc.company,
        "claim_year": doc.claim_year,
        "claim_month": doc.claim_month,
        "insurance_provider": insurance_provider,
    }

    counter_name = frappe.db.get_value("Insurance Folio Counter", filters, "name")
    if counter_name:
        return counter_name

    try:
        counter = frappe.get_doc(
            {
                "doctype": "Insurance Folio Counter",
                "posting_date": now_datetime(),
                "folio_no": 0,
                **filters,
            }
        )
        counter.insert(ignore_permissions=True)
        return counter.name

    except frappe.UniqueValidationError:
        # A concurrent claim created the counter first, so use that one.
        return frappe.db.get_value("Insurance Folio Counter", filters, "name")
