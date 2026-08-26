import os
import sys

import frappe
from erpnext import get_default_company
from erpnext.setup.utils import before_tests as erpnext_before_tests
from healthcare.healthcare.utils import before_tests as healthcare_before_tests
from healthcare.setup import setup_healthcare

from hms_tz.patches.custom_fields.create_custom_fields import execute as create_custom_fields
from hms_tz.patches.property_setter.create_property_setters import execute as create_property_setters


def after_install():
	"""Hook called after hms_tz app installation on a site."""
	create_accounting_dimensions()
	frappe.db.commit()


def create_accounting_dimensions():
	"""Create Accounting Dimensions for Healthcare Practitioner and Healthcare Service Unit.

	These dimensions add corresponding custom fields on all applicable
	accounting doctypes (Sales Invoice, Purchase Invoice, Journal Entry, etc.).
	hms_tz code relies on these fields existing on transaction line items.
	"""
	dimensions = [
		{
			"document_type": "Healthcare Practitioner",
			"label": "Healthcare Practitioner",
		},
		{
			"document_type": "Healthcare Service Unit",
			"label": "Healthcare Service Unit",
		},
	]

	for dimension_data in dimensions:
		document_type = dimension_data["document_type"]

		if frappe.db.exists("Accounting Dimension", {"document_type": document_type}):
			continue

		try:
			doc = frappe.new_doc("Accounting Dimension")
			doc.document_type = document_type
			doc.label = dimension_data["label"]
			doc.disabled = 0
			doc.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			frappe.log_error(
				title=f"Error creating Accounting Dimension for '{document_type}'",
				message=frappe.get_traceback(),
			)
			frappe.db.rollback()


def before_tests():
	"""Setup required master data before running tests.

	When ``bench run-tests --app hms_tz`` is executed, Frappe's test runner
	only invokes ``before_tests`` hooks registered by *hms_tz* (because it
	passes ``app_name="hms_tz"`` to ``frappe.get_hooks``).  ERPNext's and
	Healthcare's ``before_tests`` hooks — which bootstrap the full setup
	wizard, fixture records, healthcare master data, etc. — are **not**
	called automatically.

	This function therefore delegates to the upstream apps first,
	ensuring the test database has all required master data (Company,
	Chart of Accounts, Warehouse Types, Genders, Medical Departments,
	Item Groups, etc.) before hms_tz's own test records are created.
	"""

	# 1. ERPNext: runs setup_complete() → install_fixtures (Warehouse Types,
	#    Genders, Item Groups, Territories, etc.), creates Company, Fiscal Year,
	#    enables all roles for Administrator, sets selling/stock defaults.
	erpnext_before_tests()

	# 2. Healthcare: creates Frappe Care LLC (if needed), Medical Departments,
	#    Antibiotics, Lab Test UOMs, Dosages, Prescription Durations,
	#    Healthcare Item Groups, Sensitivities, Healthcare Service Units, etc.
	#    NOTE: healthcare_before_tests() only calls setup_healthcare() when no
	#    Company exists.  Since erpnext_before_tests() already created one,
	#    we must call setup_healthcare() explicitly afterwards.
	healthcare_before_tests()
	setup_healthcare()

	# 3. Ensure a non-group Customer Group is available and set in Selling Settings.
	#    ERPNext's set_defaults_for_tests() sets Selling Settings.customer_group
	#    to the root "All Customer Groups" (is_group=1).  Newer ERPNext versions
	#    reject group-type Customer Groups during Customer.validate().  We must
	#    override it with a leaf node AFTER ERPNext's before_tests has run.
	_ensure_non_group_customer_group()

	# 4. hms_tz accounting dimensions (Healthcare Practitioner, Healthcare Service Unit)
	create_accounting_dimensions()

	# 5. hms_tz master data required by tests (lookup records for mandatory fields)
	create_test_master_data()

	# 6. hms_tz-specific setup: custom fields, property setters, etc.
	setup_hms_tz_test_data()

	frappe.db.commit()


def setup_hms_tz_test_data():
	"""Create all hms_tz custom fields and property setters.

	The test runner does not trigger migrations or after_migrate hooks,
	so we must apply all custom fields and property setters explicitly.

	Ordering is critical:
	1. Custom fields must be created FIRST (both Python patches and JSON).
	2. Property setters run AFTER, because some set doctype-level properties
	   like ``image_field`` to a custom fieldname. If that fieldname doesn't
	   exist yet, Frappe's field validation fails on the next custom field
	   insert for that doctype.

	Fault tolerance:
	During test setup we temporarily replace Frappe's ``create_custom_fields``
	and ``make_property_setter`` with wrappers that catch errors per-field /
	per-setter.  This means a single bad definition never blocks the remaining
	fields in the same patch file.
	"""
	import frappe.custom.doctype.custom_field.custom_field as cf_module
	import frappe.custom.doctype.property_setter.property_setter as ps_module

	_original_create_custom_fields = cf_module.create_custom_fields
	_original_make_property_setter = ps_module.make_property_setter

	# ── fault-tolerant wrapper for create_custom_fields ──────────────
	def _safe_create_custom_fields(custom_fields, ignore_validate=False, update=True):
		"""Try batch first; on failure, fall back to per-field creation."""
		try:
			_original_create_custom_fields(custom_fields, ignore_validate=ignore_validate, update=update)
		except Exception:
			# Batch failed — retry each field individually so one bad
			# field does not block the rest.
			for doctypes, fields in custom_fields.items():
				if isinstance(fields, dict):
					fields = (fields,)
				if isinstance(doctypes, str):
					doctypes = (doctypes,)
				for doctype in doctypes:
					for df in fields:
						fieldname = df.get("fieldname") or frappe.scrub(df.get("label", "")) or "unknown"
						try:
							_original_create_custom_fields(
								{doctype: [df]},
								ignore_validate=ignore_validate,
								update=update,
							)
						except Exception as e:
							print(
								f"WARNING [hms_tz]: custom field '{doctype}.{fieldname}' skipped: {e}",
								file=sys.stderr,
							)

	# ── fault-tolerant wrapper for make_property_setter ──────────────
	def _safe_make_property_setter(*args, **kwargs):
		"""Wrap make_property_setter so one failure never stops the loop."""
		try:
			_original_make_property_setter(*args, **kwargs)
		except Exception as e:
			doctype = args[0] if args else kwargs.get("doctype", "?")
			fieldname = args[1] if len(args) > 1 else kwargs.get("fieldname", "?")
			prop = args[2] if len(args) > 2 else kwargs.get("property", "?")
			print(
				f"WARNING [hms_tz]: property setter '{doctype}.{fieldname}.{prop}' skipped: {e}",
				file=sys.stderr,
			)

	# ── install the wrappers ──────────────────────────────────────────
	cf_module.create_custom_fields = _safe_create_custom_fields
	ps_module.make_property_setter = _safe_make_property_setter

	try:
		_run_patches_and_json_loaders()
	finally:
		# Always restore original functions, even if something goes wrong
		cf_module.create_custom_fields = _original_create_custom_fields
		ps_module.make_property_setter = _original_make_property_setter


def _run_patches_and_json_loaders():
	"""Execute all custom field / property setter patches and JSON loaders."""
	patches_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patches.txt")

	with open(patches_file) as f:
		patches = f.read().splitlines()

	custom_field_patches = []
	property_setter_patches = []

	for patch_path in patches:
		patch_path = patch_path.strip()
		if not patch_path or patch_path.startswith("[") or patch_path.startswith("#"):
			continue

		if ".custom_fields." in patch_path:
			custom_field_patches.append(patch_path)
		elif ".property_setter." in patch_path:
			property_setter_patches.append(patch_path)

	# Phase 1: Create all custom fields (Python patches then JSON-based)
	for patch_path in custom_field_patches:
		try:
			frappe.get_attr(patch_path + ".execute")()
		except Exception as e:
			print(
				f"WARNING [hms_tz before_tests]: custom field patch failed - {patch_path}: {e}",
				file=sys.stderr,
			)

	try:
		create_custom_fields()
	except Exception as e:
		print(
			f"WARNING [hms_tz before_tests]: JSON custom fields creation failed: {e}",
			file=sys.stderr,
		)

	# Commit and clear cache so DocType meta objects are rebuilt with
	# the newly created custom fields before property setters run.
	frappe.db.commit()
	frappe.clear_cache()

	# Phase 2: Apply all property setters (Python patches then JSON-based)
	for patch_path in property_setter_patches:
		try:
			frappe.get_attr(patch_path + ".execute")()
		except Exception as e:
			print(
				f"WARNING [hms_tz before_tests]: property setter patch failed - {patch_path}: {e}",
				file=sys.stderr,
			)

	try:
		create_property_setters()
	except Exception as e:
		print(
			f"WARNING [hms_tz before_tests]: JSON property setters creation failed: {e}",
			file=sys.stderr,
		)


def create_test_master_data():
	"""Create lookup records needed by mandatory custom fields on Patient, etc.

	These are hms_tz doctypes whose records must exist before test Patient
	documents can be saved (the custom fields are reqd=1).
	"""
	master_records = [
		{"doctype": "Occupation", "occupation": "Secretary"},
		{"doctype": "Ethnicity", "ethnicity": "African"},
		{"doctype": "Demography", "demography": "City Centre"},
		{"doctype": "Healthcare Ward Type", "ward_type_name": "General Ward"},
		{"doctype": "Healthcare Points of Care", "point_of_care_name": "Phisiotherapy"},
		{"doctype": "Healthcare Points of Care", "point_of_care_name": "Laboratory"},
		{"doctype": "Healthcare Points of Care", "point_of_care_name": "Pharmacy"},
		{"doctype": "Healthcare Points of Care", "point_of_care_name": "Radiology"},
		{"doctype": "Healthcare Points of Care", "point_of_care_name": "Procedure"},
	]

	# Appointment Type is mandatory on Patient Appointment (healthcare doctype)
	for appt_type in ["Normal Visit", "Direct Cash"]:
		if not frappe.db.exists("Appointment Type", appt_type):
			try:
				frappe.get_doc(
					{
						"doctype": "Appointment Type",
						"appointment_type": appt_type,
						"default_duration": 15,
					}
				).insert(ignore_permissions=True)
			except Exception:
				pass

	# Campaign is a Frappe/CRM doctype used by how_did_you_hear_about_us
	if not frappe.db.exists("Campaign", "I know you"):
		try:
			frappe.get_doc({"doctype": "Campaign", "campaign_name": "I know you"}).insert(
				ignore_permissions=True
			)
		except Exception:
			pass

	for record in master_records:
		dt = record["doctype"]
		# The name is derived from the naming field; use the first non-doctype value
		name_value = list(record.values())[1]
		if not frappe.db.exists(dt, name_value):
			try:
				frappe.get_doc(record).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(
					title=f"hms_tz before_tests: failed to create {dt} '{name_value}'",
					message=frappe.get_traceback(),
				)

	# Ensure a non-group Healthcare Service Unit exists for company_options
	# child table rows on Lab Test Template, Therapy Type, etc.
	create_test_healthcare_service_unit()


def create_test_healthcare_service_unit():
	"""Ensure at least one non-group Healthcare Service Unit exists.

	Many template doctypes (Therapy Type, Lab Test Template, Clinical Procedure
	Template) have a mandatory ``company_options`` child table that requires a
	Healthcare Service Unit Link.  Healthcare's ``before_tests`` only creates
	the group root node "All Healthcare Service Units" — we need a leaf node.
	"""
	company = get_default_company()
	# Check if any non-group service unit already exists
	existing = frappe.db.get_value("Healthcare Service Unit", {"is_group": 0, "company": company}, "name")
	if existing:
		return

	parent = frappe.db.get_value("Healthcare Service Unit", {"is_group": 1, "company": company}, "name")
	# Ensure Healthcare Room Type exists (room_type is mandatory on HSU)
	room_type = _ensure_room_type()
	# Ensure Healthcare Ward Type exists (ward_type is mandatory on HSUT via custom field)
	_ensure_ward_type()

	try:
		su = frappe.new_doc("Healthcare Service Unit")
		su.healthcare_service_unit_name = "_Test Service Unit"
		su.company = company
		su.is_group = 0
		su.room_type = room_type
		if parent:
			su.parent_healthcare_service_unit = parent
		su.save(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		pass
	except Exception:
		frappe.log_error(
			title="hms_tz before_tests: failed to create Healthcare Service Unit",
			message=frappe.get_traceback(),
		)


def _ensure_room_type():
	"""Ensure a Healthcare Room Type exists and return its name."""
	room_type = frappe.db.get_value("Healthcare Room Type", {}, "name")
	if not room_type:
		try:
			frappe.get_doc(
				{
					"doctype": "Healthcare Room Type",
					"room_type_name": "General Ward",
				}
			).insert(ignore_permissions=True)
			room_type = "General Ward"
		except frappe.DuplicateEntryError:
			room_type = "General Ward"
		except Exception:
			pass
	return room_type


def _ensure_ward_type():
	"""Ensure Healthcare Ward Type 'General Ward' exists."""
	if not frappe.db.exists("Healthcare Ward Type", "General Ward"):
		try:
			frappe.get_doc(
				{
					"doctype": "Healthcare Ward Type",
					"ward_type_name": "General Ward",
				}
			).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			pass
		except Exception:
			pass


def _ensure_non_group_customer_group():
	"""Ensure a non-group (leaf) Customer Group exists and is the Selling default.

	Problem:
	  ERPNext's ``set_defaults_for_tests()`` sets Selling Settings
	  ``customer_group`` to ``get_root_of("Customer Group")`` which is
	  "All Customer Groups" (is_group=1).  Newer ERPNext versions added
	  ``Customer.validate_customer_group()`` that rejects group-type nodes.

	Solution:
	  1. Find or create a leaf-level Customer Group ("Individual").
	  2. Override Selling Settings ``customer_group`` to point to it.
	  3. Set the global default so ``frappe.defaults.get_global_default``
	     also returns the leaf node.
	"""
	from frappe.utils.nestedset import get_root_of

	# Step 1: find an existing non-group Customer Group
	leaf = frappe.db.get_value("Customer Group", {"is_group": 0}, "name", order_by="name asc")

	# Step 2: if none exists, create one
	if not leaf:
		root = get_root_of("Customer Group")
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": "Individual",
					"parent_customer_group": root,
					"is_group": 0,
				}
			)
			doc.insert(ignore_permissions=True)
			leaf = doc.name
		except frappe.DuplicateEntryError:
			leaf = "Individual"

	# Step 3: set as Selling Settings default so get_non_group_customer_group()
	# in patient.py returns it immediately (step 1 fast-path)
	frappe.db.set_single_value("Selling Settings", "customer_group", leaf)
	frappe.db.set_default("customer_group", leaf)
