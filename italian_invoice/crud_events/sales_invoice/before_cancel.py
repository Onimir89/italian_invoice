import frappe
from frappe import _

# SDI states in which the invoice is legally not issued: it can be cancelled and redone.
# NS = rejected by SDI; Annullata = transaction voided for technical reasons.
ANNULLABILI = {None, "", "Non Inviata", "Non inviata", "NS", "Annullata", "Inviata (Test)"}


def execute(doc, method=None):
	"""Fase #36: an invoice delivered to SDI is never cancelled (the core on_cancel would drop
	the sent XML and on_cancel here would reset its SDI state): a credit note is due."""
	if doc.get("custom_stato_invio") not in ANNULLABILI:
		frappe.throw(
			_("Sales Invoice {0}: già trasmessa allo SDI (stato {1}), non si annulla: emetti una nota di credito.").format(
				doc.name, doc.custom_stato_invio
			)
		)
