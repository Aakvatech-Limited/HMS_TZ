# Copyright (c) 2025, Aakvatech and contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.jubilee.api.preauthorization import (
	get_bill_no,
	get_jubilee_payment_rows,
	get_normalized_disease_code,
	get_preauth_endpoint,
	get_preauth_entities,
	get_service_request_items,
	get_source_encounters,
	get_source_from_approval_request,
)


def _insert_hsr(appointment, payments):
	"""Real Healthcare Service Request, saved with just enough to hold payment rows."""
	hsr = frappe.new_doc("Healthcare Service Request")
	hsr.appointment = appointment
	hsr.payment_type = "Insurance"
	for row in payments:
		hsr.append("payments", row)
	hsr.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return hsr


def make_source(**overrides):
	"""Minimal normalized pre-auth source, as the adapters produce."""
	source = frappe._dict(
		{
			"claim_year": 2026,
			"claim_month": 7,
			"card_no": " CARD-1 ",
			"first_name": "Amina",
			"last_name": "Juma",
			"gender": "Female",
			"date_of_birth": "1990-01-01",
			"telephone_no": "0700000000",
			"patient": "HLC-PAT-0001",
			"authorization_no": "AUTH-1",
			"attendance_date": "2026-07-27 09:00:00",
			"patient_type_code": "OP",
			"admitted_date": None,
			"discharge_date": None,
			"practitioner": None,
			"practitioner_no": "MCT-1",
			"provider_id": "PROV-1",
			"posting_date": "2026-07-27",
			"total_amount": 30000,
			"jubilee_procedure": "PROC-1",
			"benefit_code": "7905",
			"bill_no": "202600001",
			"folio_diseases": [],
			"folio_items": [],
		}
	)
	source.update(overrides)

	return source


class TestJubileePreauthorization(FrappeTestCase):
	def test_normalized_disease_code_variants(self):
		self.assertEqual(get_normalized_disease_code("A123"), "A12.3")
		self.assertEqual(get_normalized_disease_code("A1234"), "A12.3")
		self.assertEqual(get_normalized_disease_code("A12"), "A12")
		self.assertEqual(get_normalized_disease_code("A12.3"), "A12.3")
		self.assertEqual(get_normalized_disease_code(""), "")
		self.assertEqual(get_normalized_disease_code(None), "")

	def test_normalized_disease_code_pads_missing_subcode(self):
		"""A four-plus char code with no dot gets a dotted subcode."""
		self.assertEqual(get_normalized_disease_code("B999"), "B99.9")

	def test_entities_strips_card_no_and_defaults_patient_type(self):
		entities = get_preauth_entities(make_source(patient_type_code=None))

		self.assertEqual(entities.CardNo, "CARD-1")
		self.assertEqual(entities.PatientTypeCode, "OP")
		self.assertEqual(entities.AmountClaimed, 30000)
		self.assertEqual(entities.jubileeBenefits, "7905")
		self.assertEqual(entities.BillNo, "202600001")

	def test_entities_maps_folio_items(self):
		source = make_source(
			folio_items=[
				frappe._dict(
					{
						"item_code": "REF-1",
						"item_name": "Full Blood Picture",
						"item_quantity": 2,
						"unit_price": 5000,
						"amount_claimed": 10000,
						"created_by": "Doctor",
						"date_created": "2026-07-27",
					}
				)
			]
		)

		item = get_preauth_entities(source).FolioItems[0]

		self.assertEqual(item["ItemCode"], "REF-1")
		self.assertEqual(item["OtherDetails"], "Full Blood Picture")
		self.assertEqual(item["ItemQuantity"], 2)
		self.assertEqual(item["UnitPrice"], 5000)
		self.assertEqual(item["AmountClaimed"], 10000)

	def test_entities_maps_folio_diseases(self):
		source = make_source(
			folio_diseases=[
				frappe._dict(
					{
						"disease_code": "A12.3",
						"status": "Final",
						"description": "Some finding",
						"created_by": "Doctor",
						"date_created": "2026-07-27",
					}
				)
			]
		)

		disease = get_preauth_entities(source).FolioDiseases[0]

		self.assertEqual(disease["DiseaseCode"], "A12.3")
		self.assertEqual(disease["Status"], "Final")
		self.assertEqual(disease["Remarks"], "Some finding")

	def test_entities_defaults_disease_status_to_provisional(self):
		source = make_source(folio_diseases=[frappe._dict({"disease_code": "A12.3", "status": ""})])

		self.assertEqual(get_preauth_entities(source).FolioDiseases[0]["Status"], "Provisional")

	def test_entities_omits_qualification_without_practitioner(self):
		"""The qualification lookup throws, so it must not run unasked."""
		self.assertIsNone(get_preauth_entities(make_source()).get("QualificationID"))

	def test_service_request_items_map_from_payment_rows(self):
		"""Payment rows from get_jubilee_payment_rows carry the insurer ref code, qty, rate, amount."""
		hsr = frappe._dict({"appointment": "APT-1"})
		rows = [
			frappe._dict(
				{
					"parent": "HSR-1",
					"idx": 1,
					"item_code": "REF-1",
					"service_name": "Full Blood Picture",
					"qty": 2,
					"rate": 5000,
					"amount": 10000,
				}
			)
		]

		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows", return_value=rows
		) as get_rows:
			items = get_service_request_items(hsr)

		get_rows.assert_called_once_with("APT-1")
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0].item_code, "REF-1")
		self.assertEqual(items[0].item_name, "Full Blood Picture")
		self.assertEqual(items[0].item_quantity, 2)
		self.assertEqual(items[0].unit_price, 5000)
		self.assertEqual(items[0].amount_claimed, 10000)

	def test_jubilee_payment_rows_span_multiple_service_requests(self):
		"""The Jubilee claim spans every HSR on the appointment; other insurers, cash,
		and cancelled rows do not count against it."""
		# service_name is left unset: before_save's set_service_price_rate() only
		# recomputes rate/amount when service_name is set, which would otherwise
		# require a price_list and full rate lookup unrelated to this test.
		appointment = "TEST-APT-JUBILEE-ROWS"
		_insert_hsr(
			appointment,
			[
				{
					"payor_plan": "P1",
					"qty": 1,
					"payment_type": "Insurance",
					"insurance_company": "Jubilee Insurance",
					"is_cancelled": 0,
					"item_code": "REF-1",
					"rate": 6000,
					"amount": 6000,
				}
			],
		)
		_insert_hsr(
			appointment,
			[
				{
					"payor_plan": "P1",
					"qty": 1,
					"payment_type": "Insurance",
					"insurance_company": "Jubilee Insurance",
					"is_cancelled": 0,
					"item_code": "REF-2",
					"rate": 4000,
					"amount": 4000,
				},
				{
					"payor_plan": "P1",
					"qty": 1,
					"payment_type": "Insurance",
					"insurance_company": "Jubilee Insurance",
					"is_cancelled": 1,
					"item_code": "REF-3",
					"rate": 9999,
					"amount": 9999,
				},
				{
					"payor_plan": "P1",
					"qty": 1,
					"payment_type": "Insurance",
					"insurance_company": "NHIF",
					"is_cancelled": 0,
					"item_code": "REF-4",
					"rate": 9999,
					"amount": 9999,
				},
				{
					"payor_plan": "P1",
					"qty": 1,
					"payment_type": "Cash",
					"insurance_company": "",
					"is_cancelled": 0,
					"item_code": "REF-5",
					"rate": 9999,
					"amount": 9999,
				},
			],
		)

		rows = get_jubilee_payment_rows(appointment)

		self.assertEqual({row.item_code for row in rows}, {"REF-1", "REF-2"})
		self.assertEqual(sum(row.amount for row in rows), 10000)

	def test_amount_claimed_sums_only_the_items_being_sent(self):
		"""The claimed total is derived from folio_items, so it cannot drift."""
		source = make_source(
			folio_items=[
				frappe._dict({"item_code": "REF-1", "amount_claimed": 10000}),
				frappe._dict({"item_code": "REF-2", "amount_claimed": 4000}),
			]
		)
		source.total_amount = sum(d.amount_claimed or 0 for d in source.folio_items)

		self.assertEqual(get_preauth_entities(source).AmountClaimed, 14000)

	def test_amount_claimed_is_zero_without_items(self):
		source = make_source(folio_items=[])
		source.total_amount = sum(d.amount_claimed or 0 for d in source.folio_items)

		self.assertEqual(get_preauth_entities(source).AmountClaimed, 0)

	def test_service_request_items_throws_on_missing_ref_code(self):
		"""Sending a blank ItemCode would fail confusingly at the insurer instead."""
		hsr = frappe._dict({"appointment": "APT-1"})
		rows = [
			frappe._dict(
				{
					"parent": "HSR-1",
					"idx": 1,
					"item_code": "",
					"service_name": "Full Blood Picture",
					"qty": 1,
					"rate": 100,
					"amount": 100,
				}
			)
		]

		with patch("hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows", return_value=rows):
			self.assertRaises(frappe.ValidationError, get_service_request_items, hsr)

	def test_source_encounters_only_for_patient_encounter(self):
		hsr = frappe._dict({"source_doctype": "Patient Encounter", "source_docname": "PE-1"})
		self.assertEqual(get_source_encounters(hsr), ["PE-1"])

		hsr = frappe._dict({"source_doctype": "Lab Test", "source_docname": "LT-1"})
		self.assertEqual(get_source_encounters(hsr), [])

	def test_approval_request_adapter_exposes_items_and_diseases(self):
		"""The JAR adapter is a pass-through; its child rows keep their fieldnames."""
		jar = frappe.new_doc("Jubilee Approval Request")
		jar.card_no = "CARD-9"
		jar.total_amount = 500
		jar.append("diseases", {"disease_code": "A12.3", "status": "Final"})
		jar.append(
			"items",
			{
				"item_code": "REF-9",
				"item_name": "Item",
				"item_quantity": 1,
				"unit_price": 500,
				"amount_claimed": 500,
			},
		)

		source = get_source_from_approval_request(jar)

		self.assertEqual(source.card_no, "CARD-9")
		self.assertEqual(source.total_amount, 500)
		self.assertEqual(source.folio_items[0].item_code, "REF-9")
		self.assertEqual(source.folio_diseases[0].disease_code, "A12.3")

	def test_bill_no_strips_the_naming_series_prefix(self):
		self.assertEqual(get_bill_no("HSR-2026-00001"), "202600001")

	def test_endpoint_sends_without_a_cycle_and_updates_with_one(self):
		"""The appointment's first Service Request sends; later ones update."""
		setting = frappe._dict(
			{
				"jubilee_url": "https://jubilee.test",
				"get_jubilee_token": lambda: "token",
			}
		)

		request_type, url, _headers = get_preauth_endpoint(setting, None)
		self.assertEqual(request_type, "SendPreauthorization")
		self.assertTrue(url.endswith("/jubileeapi/SendPreauthorization"))

		request_type, url, _headers = get_preauth_endpoint(setting, "SUB-1")
		self.assertEqual(request_type, "UpdatePreauthorization")
		self.assertTrue(url.endswith("/jubileeapi/UpdatePreauthorization"))

	def test_later_service_request_reuses_the_first_bill_no(self):
		"""UpdatePreauthorization must carry the BillNo of the original send."""
		hsr = frappe._dict(
			{
				"name": "HSR-2026-00002",
				"appointment": "APT-1",
				"patient": "HLC-PAT-0001",
				"posting_datetime": "2026-07-27 09:00:00",
				"practitioner": None,
				"company": "TestCo",
				"card_no": "CARD-1",
				"jubilee_procedure": "PROC-1",
				"benefit_code": "7905",
				"source_doctype": "Patient Encounter",
				"source_docname": "PE-1",
			}
		)
		cycle_reference = frappe._dict({"name": "HSR-2026-00001", "submission_id": "SUB-1"})

		with (
			patch("hms_tz.jubilee.api.preauthorization.get_service_request_items", return_value=[]),
			patch("hms_tz.jubilee.api.preauthorization.get_encounter_diseases", return_value=[]),
			patch("frappe.get_cached_doc", return_value=frappe._dict()),
			patch("frappe.get_cached_value", return_value=""),
		):
			from hms_tz.jubilee.api.preauthorization import get_source_from_service_request

			source = get_source_from_service_request(hsr, cycle_reference)

		self.assertEqual(source.bill_no, get_bill_no("HSR-2026-00001"))
		self.assertNotEqual(source.bill_no, get_bill_no("HSR-2026-00002"))

	def test_first_service_request_uses_its_own_bill_no(self):
		"""With no cycle open yet, the sending Service Request supplies the BillNo."""
		hsr = frappe._dict(
			{
				"name": "HSR-2026-00001",
				"appointment": "APT-1",
				"patient": "HLC-PAT-0001",
				"posting_datetime": "2026-07-27 09:00:00",
				"practitioner": None,
				"company": "TestCo",
				"card_no": "CARD-1",
				"jubilee_procedure": "PROC-1",
				"benefit_code": "7905",
				"source_doctype": "Patient Encounter",
				"source_docname": "PE-1",
			}
		)

		with (
			patch("hms_tz.jubilee.api.preauthorization.get_service_request_items", return_value=[]),
			patch("hms_tz.jubilee.api.preauthorization.get_encounter_diseases", return_value=[]),
			patch(
				"hms_tz.jubilee.api.preauthorization.get_preauth_cycle_reference",
				return_value=None,
			),
			patch("frappe.get_cached_doc", return_value=frappe._dict()),
			patch("frappe.get_cached_value", return_value=""),
		):
			from hms_tz.jubilee.api.preauthorization import get_source_from_service_request

			source = get_source_from_service_request(hsr)

		self.assertEqual(source.bill_no, get_bill_no("HSR-2026-00001"))

	def test_jar_and_hsr_items_build_identical_folio_items(self):
		"""Both paths must send the same FolioItems shape, or payloads drift."""
		row = {
			"item_code": "REF-1",
			"item_name": "Full Blood Picture",
			"item_quantity": 2,
			"unit_price": 5000,
			"amount_claimed": 10000,
			"created_by": "Doctor",
			"date_created": "2026-07-27",
		}
		jar_items = get_preauth_entities(make_source(folio_items=[frappe._dict(row)])).FolioItems

		hsr = frappe._dict({"appointment": "APT-1"})
		payment_rows = [
			frappe._dict(
				{
					"parent": "HSR-1",
					"idx": 1,
					"item_code": "REF-1",
					"service_name": "Full Blood Picture",
					"qty": 2,
					"rate": 5000,
					"amount": 10000,
				}
			)
		]
		with patch(
			"hms_tz.jubilee.api.preauthorization.get_jubilee_payment_rows",
			return_value=payment_rows,
		):
			hsr_items = get_preauth_entities(
				make_source(folio_items=get_service_request_items(hsr))
			).FolioItems

		for field in ("ItemCode", "OtherDetails", "ItemQuantity", "UnitPrice", "AmountClaimed"):
			self.assertEqual(jar_items[0][field], hsr_items[0][field])
