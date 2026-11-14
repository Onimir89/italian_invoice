import frappe
from frappe import _

# SDI states in which the invoice is legally not issued: it can be cancelled and redone.
# NS = rejected by SDI (provv. 89757/2018). Any other state, known or not, needs a credit note.
ANNULLABILI = {None, "", "Non Inviata", "Non inviata", "NS", "Inviata (Test)"}


def execute(doc, method=None):
	"""Fase #36: an invoice delivered to SDI is never cancelled (the core on_cancel would drop
	the sent XML and on_cancel here would reset its SDI state): a credit note is due."""
	# The SDI transaction is the source; the copy on the invoice is editable after submit.
	stato = doc.get("custom_stato_invio")
	if doc.get("custom_transazione_sdi"):
		stato = frappe.db.get_value("Transazione SDI", doc.custom_transazione_sdi, "stato_invio")
	if stato not in ANNULLABILI:
		frappe.throw(
			_("Sales Invoice {0}: già trasmessa allo SDI (stato {1}), non si annulla: emetti una nota di credito.").format(
				doc.name, stato
			)
		)
