from italian_invoice.utilities.fatture import remove_e_invoice_attachments


def execute(doc, method=None):
	"""Drop the XML that ERPNext core attaches on submit.

	erpnext/hooks.py registers erpnext.regional.italy.utils.sales_invoice_on_submit for every
	Sales Invoice: with company country Italy it attaches the core e-invoice, whose Natura is
	the generic N6 (SdI rejects it, check 00445). The e-invoice must come only from
	italian_invoice, generated on demand; this hook runs after the core one (app order).
	"""
	remove_e_invoice_attachments(doc)
