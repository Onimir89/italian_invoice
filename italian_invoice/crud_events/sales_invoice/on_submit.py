import re

import frappe
from frappe.utils.file_manager import remove_file

from italian_invoice.utilities.fatture import get_company_data, get_prefixed_company_tax_id


def execute(doc, method=None):
	"""Drop the XML that ERPNext core attaches on submit.

	erpnext/hooks.py registers erpnext.regional.italy.utils.sales_invoice_on_submit for every
	Sales Invoice: with company country Italy it attaches the core e-invoice, whose Natura is
	the generic N6 (SdI rejects it, check 00445). The e-invoice must come only from
	italian_invoice, generated on demand; this hook runs after the core one (app order).
	Only the core file name (<tax id>_<5 digits>.xml) goes: a user attachment that merely
	starts with the tax id stays (#36).
	"""
	# The core attaches only for Italian companies; reading the company data needs its
	# address, so non-Italian companies and invoices without XML never get there.
	if frappe.get_cached_value("Company", doc.company, "country") != "Italy":
		return
	xml = frappe.get_all(
		"File",
		filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name, "file_name": ["like", "%.xml"]},
		fields=["name", "file_name"],
	)
	if not xml:
		return
	tax_id = get_prefixed_company_tax_id(get_company_data(doc)["tax_id"])
	for attachment in xml:
		if is_core_xml_name(attachment.file_name, tax_id):
			remove_file(attachment.name, attached_to_doctype=doc.doctype, attached_to_name=doc.name)


def is_core_xml_name(file_name, tax_id):
	return bool(re.fullmatch(re.escape(tax_id) + r"_\d{5}\.xml", file_name or ""))
