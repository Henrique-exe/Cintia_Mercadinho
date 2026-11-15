"""Regressão do detalhamento financeiro e custo histórico da versão 1.1."""
import unittest
import sqlite3
import tempfile
from pathlib import Path
from test_core_offline import load_core

class FinanceReportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.db_mod, cls.s=load_core()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.conn=sqlite3.connect(str(Path(self.tmp.name)/'test.sqlite3'),isolation_level=None)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(self.db_mod.SCHEMA)
        self.db_mod.get_db=lambda:self.conn
        self.s.get_db=lambda:self.conn

    def tearDown(self):
        self.conn.close();self.tmp.cleanup()

    def product(self,name='Arroz',unit='UN',stock='12',price='6.00',minimum='2'):
        return self.s.save_product({'name':name,'unit':unit,'stock':stock,'price':price,'minimum':minimum})

    def test_methods_profit_cancellation_and_credit_are_separated(self):
        p=self.s.save_product({'name':'Produto A','unit':'UN','stock':'10','price':'20.00','purchase_price':'8.00'})
        cust=self.s.add_customer({'name':'Pessoa teste'})
        self.s.open_cash({'opening':'100.00'})
        sale=self.s.create_sale({'token':'profit-test-001','items':[{'product_id':p['id'],'quantity':'2'}],
            'discount_percent':'10','discount_fixed':'6.00',
            'payments':[{'method':'PIX','applied':'10.00'}, {'method':'CARD','applied':'5.00'},
                        {'method':'CASH','applied':'5.00','tendered':'10.00'},
                        {'method':'CREDIT','customer_id':cust['id'],'applied':'10.00'}]})
        self.assertEqual(sale['total_cents'],3000)
        r=self.s.reports()
        self.assertEqual(r['sale_payments_by_method_cents'],{'CASH':500,'PIX':1000,'CARD':500,'CREDIT':1000})
        self.assertEqual(r['received_by_method_cents'],{'CASH':500,'PIX':1000,'CARD':500})
        self.assertEqual(r['received_total_cents'],2000)
        self.assertEqual(r['cost_cents'],1600)
        self.assertEqual(r['gross_profit_cents'],1400)
        debt=self.s.list_debts()[0]
        self.s.receive_credit(debt['id'],{'amount':'4.00','method':'CASH'})
        r=self.s.reports()
        self.assertEqual(r['received_by_method_cents']['CASH'],900)
        self.assertEqual(r['received_total_cents'],2400)
        self.assertEqual(r['revenue_cents'],3000)
        self.s.cancel_sale(sale['id'],{'reason':'Cancelamento com devolução','confirm_refunds':True})
        r=self.s.reports()
        self.assertEqual(r['revenue_cents'],0)
        self.assertEqual(r['received_total_cents'],0)
        self.assertEqual(r['refunds_by_method_cents'],{'CASH':900,'PIX':1000,'CARD':500})
        self.assertFalse(r['profit_available'])

    def test_missing_purchase_price_does_not_invent_profit(self):
        p=self.product(stock='5',price='12.00')
        self.s.open_cash({'opening':'0'})
        self.s.create_sale({'token':'profit-test-002','items':[{'product_id':p['id'],'quantity':'1'}],
            'payments':[{'method':'CASH','applied':'12.00'}]})
        r=self.s.reports()
        self.assertIsNone(r['gross_profit_cents'])
        self.assertEqual(r['cost_missing_items'],1)

    def test_weight_cost_snapshot_and_price_changes(self):
        p=self.s.save_product({'name':'A granel','unit':'KG','stock':'1.000','price':'20.00','purchase_price':'12.00'})
        self.s.open_cash({'opening':'0'})
        sale=self.s.create_sale({'token':'profit-test-003','items':[{'product_id':p['id'],'quantity':'0.350'}],
            'payments':[{'method':'PIX','applied':'7.00'}]})
        self.assertEqual(sale['items'][0]['cost_cents'],420)
        self.s.save_product({'name':'A granel','unit':'KG','price':'25.00','purchase_price':'16.00','minimum':'0','active':True},p['id'])
        r=self.s.reports()
        self.assertEqual(r['gross_profit_cents'],280)

    def test_legacy_schema_migrates_without_losing_data(self):
        self.conn.execute('CREATE TABLE legacy_sale_items (id INTEGER PRIMARY KEY, price_cents INTEGER)')
        # Test real upgrade in an isolated file, with Flask globals mocked.
        import sqlite3, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            c=sqlite3.connect(str(Path(folder)/'legacy.sqlite3'),isolation_level=None)
            c.row_factory=sqlite3.Row
            c.execute('CREATE TABLE sale_items (id INTEGER PRIMARY KEY, price_cents INTEGER)')
            c.execute('INSERT INTO sale_items (id,price_cents) VALUES(1,500)')
            previous=self.db_mod.get_db
            try:
                self.db_mod.get_db=lambda:c
                self.db_mod.init_db()
                self.assertIn('cost_cents',[r['name'] for r in c.execute('PRAGMA table_info(sale_items)')])
                self.assertEqual(c.execute('SELECT price_cents FROM sale_items WHERE id=1').fetchone()[0],500)
            finally:
                self.db_mod.get_db=previous
                c.close()

if __name__=='__main__': unittest.main()
