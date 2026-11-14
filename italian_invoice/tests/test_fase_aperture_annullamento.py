"""Fase #36: opening invoices on their own series, no cancel of an invoice sent to SDI,
the on-submit cleanup removes only the core XML name."""

import frappe
from frappe.tests import IntegrationTestCase

from italian_invoice.crud_events.sales_invoice import before_submit, on_submit
from italian_invoice.tests.fixtures import TEST_COMPANY as COMPANY
from italian_invoice.tests.test_numerazione import CUSTOMER, ITEM, _crea_anagrafiche, _serie_corrente


class TestAperture(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_crea_anagrafiche()
		cls.customer = frappe.db.get_value("Customer", {"customer_name": CUSTOMER}, "name")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _fattura(self, **valori):
		return frappe.get_doc({
			"doctype": "Sales Invoice", "company": COMPANY, "customer": self.customer, "currency": "EUR",
			"items": [{"item_code": ITEM, "qty": 1, "rate": 100}], **valori,
		})

	def test_apertura_su_serie_propria_sinv_intatta(self):
		frappe.db.set_value("Company", COMPANY, "custom_numero_alla_conferma", 0)
		_, sinv_prima = _serie_corrente("SINV/.YY./")
		doc = self._fattura(is_opening="Yes").insert(ignore_permissions=True)
		self.assertEqual(doc.naming_series, "APERT/.YY./")
		self.assertTrue(doc.name.startswith("APERT/"), doc.name)
		self.assertEqual(_serie_corrente("SINV/.YY./")[1], sinv_prima)

	def test_fattura_normale_resta_sinv(self):
		doc = self._fattura().insert(ignore_permissions=True)
		self.assertEqual(doc.naming_series, "SINV/.YY./")

	def _utente(self, email, ruolo):
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": ruolo, "send_welcome_email": 0,
				"roles": [{"role": ruolo}]}).insert(ignore_permissions=True)
		return email

	def test_apertura_negata_a_chi_non_tiene_la_contabilita(self):
		doc = self._fattura(is_opening="Yes")
		frappe.set_user(self._utente("fase36-sales@example.com", "Sales User"))
		with self.assertRaisesRegex(frappe.ValidationError, "Accounts Manager"):
			before_submit.execute(doc)

	def test_apertura_permessa_ad_accounts_manager_e_system_manager(self):
		for email, ruolo in (("fase36-am@example.com", "Accounts Manager"), ("fase36-sm@example.com", "System Manager")):
			frappe.set_user(self._utente(email, ruolo))
			before_submit.execute(self._fattura(is_opening="Yes"))

	def test_apertura_non_si_cambia_dopo_il_salvataggio(self):
		frappe.db.set_value("Company", COMPANY, "custom_numero_alla_conferma", 0)
		doc = self._fattura().insert(ignore_permissions=True)
		doc.is_opening = "Yes"
		with self.assertRaisesRegex(frappe.ValidationError, "apertura"):
			doc.save()


class TestAnnullamento(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_crea_anagrafiche()
		cls.customer = frappe.db.get_value("Customer", {"customer_name": CUSTOMER}, "name")

	def _confermata(self, stato):
		frappe.db.set_value("Company", COMPANY, "custom_numero_alla_conferma", 0)
		doc = frappe.get_doc({
			"doctype": "Sales Invoice", "company": COMPANY, "customer": self.customer, "currency": "EUR",
			"items": [{"item_code": ITEM, "qty": 1, "rate": 100}],
		}).insert(ignore_permissions=True)
		doc.submit()
		doc.db_set("custom_stato_invio", stato)
		return doc

	def test_trasmessa_non_si_annulla(self):
		for stato in ("Inviata", "RC", "MC", "DT", "EC01", "EC02", "Annullata"):
			doc = self._confermata(stato)
			with self.assertRaisesRegex(frappe.ValidationError, "nota di credito"):
				doc.cancel()

	def test_scartata_o_non_inviata_si_annulla(self):
		for stato in ("Non Inviata", "NS"):
			doc = self._confermata(stato)
			doc.cancel()
			self.assertEqual(doc.docstatus, 2)


IT_COMPANY = "_Test Fase36 Italia"


class TestPuliziaXmlCore(IntegrationTestCase):
	"""on_submit on an Italian company with real File rows: the core XML goes, also when Frappe
	renamed it after a name clash with an XML already on disk; anything else stays."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_crea_anagrafiche()
		if not frappe.db.exists("Company", IT_COMPANY):
			frappe.get_doc({"doctype": "Company", "company_name": IT_COMPANY, "abbr": "_TF36", "default_currency": "EUR",
				"country": "Italy", "tax_id": "01234567890", "custom_codice_sistema_interscambio": "0000000"}).insert(ignore_permissions=True)
		cls.customer = frappe.db.get_value("Customer", {"customer_name": CUSTOMER}, "name")

	def test_toglie_l_xml_del_core_anche_rinominato(self):
		frappe.db.set_value("Company", COMPANY, "custom_numero_alla_conferma", 0)
		fattura = frappe.get_doc({
			"doctype": "Sales Invoice", "company": COMPANY, "customer": self.customer, "currency": "EUR",
			"items": [{"item_code": ITEM, "qty": 1, "rate": 100}],
		}).insert(ignore_permissions=True)
		nomi = ["IT01234567890_00012.xml", "IT01234567890_00012a1b2c3.xml", "IT01234567890_contratto.xml", "nota.xml"]
		for nome in nomi:
			frappe.get_doc({"doctype": "File", "file_name": nome, "content": "<x/>", "is_private": 1,
				"attached_to_doctype": "Sales Invoice", "attached_to_name": fattura.name}).insert(ignore_permissions=True)
		on_submit.execute(frappe._dict(doctype="Sales Invoice", name=fattura.name, company=IT_COMPANY, is_opening="No"))
		rimasti = sorted(frappe.get_all("File", filters={"attached_to_name": fattura.name}, pluck="file_name"))
		self.assertEqual(rimasti, ["IT01234567890_contratto.xml", "nota.xml"])

	def test_societa_estera_non_tocca_nulla(self):
		self.assertFalse(on_submit.is_italian(COMPANY))
		self.assertTrue(on_submit.is_italian(IT_COMPANY))
