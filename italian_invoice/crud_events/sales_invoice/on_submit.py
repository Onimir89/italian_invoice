import re

import frappe
from frappe.utils.file_manager import remove_file

from italian_invoice.utilities.fatture import get_prefixed_company_tax_id

# Same names as erpnext/regional/italy/utils.py, which decides whether the core attaches its XML.
ITALY = {"Italy", "Italia", "Italian Republic", "Repubblica Italiana"}


def execute(doc, method=None):
	"""Drop the XML that ERPNext core attaches on submit.

	erpnext/hooks.py registers erpnext.regional.italy.utils.sales_invoice_on_submit for every
	Sales Invoice: with company country Italy it attaches the core e-invoice, whose Natura is
	the generic N6 (SdI rejects it, check 00445). The e-invoice must come only from
	italian_invoice, generated on demand; this hook runs after the core one (app order).
	Only the core file name goes (#36): <tax id>_<counter>.xml, or with the 6 hex Frappe
	appends on a clash with an XML already on disk; a user attachment stays.
	"""
	if doc.is_opening == "Yes" or not is_italian(doc.company):
		return
	xml = frappe.get_all(
		"File",
		filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name, "file_name": ["like", "%.xml"]},
		fields=["name", "file_name"],
	)
	tax_id = frappe.get_cached_value("Company", doc.company, "tax_id")
	if not (xml and tax_id):
		return
	tax_id = get_prefixed_company_tax_id(tax_id)
	for attachment in xml:
		if is_core_xml_name(attachment.file_name, tax_id):
			remove_file(attachment.name, attached_to_doctype=doc.doctype, attached_to_name=doc.name)


def is_italian(company):
	return frappe.get_cached_value("Company", company, "country") in ITALY


def is_core_xml_name(file_name, tax_id):
	return bool(re.fullmatch(re.escape(tax_id) + r"_\d{5,}(?:[0-9a-f]{6})?\.xml", file_name or ""))
