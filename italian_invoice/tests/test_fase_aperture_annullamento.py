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

	def test_apertura_solo_per_accounts_manager(self):
		doc = self._fattura(is_opening="Yes")
		frappe.set_user("Guest")
		with self.assertRaisesRegex(frappe.ValidationError, "Accounts Manager"):
			before_submit.execute(doc)

	def test_apertura_con_accounts_manager_passa(self):
		before_submit.execute(self._fattura(is_opening="Yes"))  # Administrator has every role


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
		for stato in ("Inviata", "RC", "MC", "DT", "EC01", "EC02"):
			doc = self._confermata(stato)
			with self.assertRaisesRegex(frappe.ValidationError, "nota di credito"):
				doc.cancel()

	def test_scartata_o_non_inviata_si_annulla(self):
		for stato in ("Non Inviata", "NS"):
			doc = self._confermata(stato)
			doc.cancel()
			self.assertEqual(doc.docstatus, 2)


class TestPuliziaXmlCore(IntegrationTestCase):
	def test_solo_il_nome_dell_xml_del_core(self):
		self.assertTrue(on_submit.is_core_xml_name("IT01234567890_00012.xml", "IT01234567890"))
		self.assertFalse(on_submit.is_core_xml_name("IT01234567890_contratto.xml", "IT01234567890"))
		self.assertFalse(on_submit.is_core_xml_name("IT01234567890_00012.xml.p7m", "IT01234567890"))
