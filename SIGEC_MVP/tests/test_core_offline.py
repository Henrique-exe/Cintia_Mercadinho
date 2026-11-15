"""Testes de regras e SQLite sem depender de Flask; execução: python -m unittest discover -s tests -p test_core_offline.py."""
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load_core():
    # As funções de teste substituem get_db. Não use os módulos reais do
    # aplicativo, nem deixe um Flask falso visível aos testes do instalador.
    namespace='_sigec_offline_test'
    package=types.ModuleType(namespace)
    package.__path__=[str(ROOT/'sigec')]
    sys.modules[namespace]=package
    stub_flask='flask' not in sys.modules
    if stub_flask:
        dummy_flask=types.ModuleType('flask')
        dummy_flask.current_app=None
        dummy_flask.g=None
        sys.modules['flask']=dummy_flask
    loaded=[]
    try:
        for name in ('db','services'):
            spec=importlib.util.spec_from_file_location(namespace+'.'+name,ROOT/'sigec'/f'{name}.py')
            module=importlib.util.module_from_spec(spec)
            sys.modules[spec.name]=module
            spec.loader.exec_module(module)
            loaded.append(module)
    finally:
        for name in (namespace+'.services',namespace+'.db',namespace):
            sys.modules.pop(name,None)
        if stub_flask:
            sys.modules.pop('flask',None)
    return tuple(loaded)


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.db_mod,cls.s=load_core()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.conn=sqlite3.connect(str(Path(self.tmp.name)/'test.sqlite3'),isolation_level=None)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(self.db_mod.SCHEMA)
        self.db_mod.get_db=lambda:self.conn
        self.s.get_db=lambda:self.conn

    def tearDown(self): self.conn.close();self.tmp.cleanup()

    def product(self,name='Arroz',unit='UN',stock='12',price='6.00',minimum='2'):
        return self.s.save_product({'name':name,'unit':unit,'stock':stock,'price':price,'minimum':minimum})

    def test_product_validations(self):
        with self.assertRaises(self.s.ValidationError):self.product(name='')
        with self.assertRaises(self.s.ValidationError):self.product(stock='-1')
        with self.assertRaises(self.s.ValidationError):self.product(unit='UN',stock='1.5')
        with self.assertRaises(self.s.ValidationError):self.product(unit='KG',stock='1.0001')
        self.assertEqual(self.product(unit='KG',stock='1.250')['stock_base'],1250)

    def test_product_persistence_and_deletion(self):
        p=self.product();self.assertEqual(self.s.list_products()[0]['name'],'Arroz')
        self.assertEqual(self.s.remove_product(p['id'])['action'],'DELETED')
        self.assertFalse(self.s.list_products())

    def test_cash_cannot_double_open(self):
        self.s.open_cash({'opening':'100.00'})
        with self.assertRaises(self.s.ConflictError):self.s.open_cash({'opening':'1.00'})
        self.assertEqual(self.s.cash_status()['expected_cents'],10000)

    def test_mixed_payment_and_discounts(self):
        a=self.product(name='Arroz',stock='10',price='6.00')
        b=self.product(name='Salsicha',unit='KG',stock='1.000',price='20.00')
        self.s.open_cash({'opening':'100.00'})
        sale=self.s.create_sale({'token':'unique-test-001','items':[{'product_id':a['id'],'quantity':'2'},
                   {'product_id':b['id'],'quantity':'0.350'}],
                   'discount_percent':'10','discount_fixed':'10.00','payments':[
                   {'method':'PIX','applied':'5.00'},
                   {'method':'CASH','applied':'2.10','tendered':'5.00'}]})
        self.assertEqual(sale['subtotal_cents'],1900)
        self.assertEqual(sale['discount_percent_cents'],190)
        self.assertEqual(sale['discount_fixed_cents'],1000)
        self.assertEqual(sale['total_cents'],710)
        self.assertEqual(sale['payments'][1]['change_cents'],290)
        self.assertEqual(self.s.cash_status()['expected_cents'],10210)
        self.assertEqual(self.s.row_or_404('products',b['id'])['stock_base'],650)
        # Retry by idempotency token is not a second sale.
        duplicate=self.s.create_sale({'token':'unique-test-001','items':[{'product_id':a['id'],'quantity':'2'}],'payments':[]})
        self.assertEqual(sale['id'],duplicate['id'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0],1)
        self.s.cancel_sale(sale['id'],{'reason':'Lançamento duplicado','confirm_refunds':True})
        self.assertEqual(self.s.row_or_404('products',b['id'])['stock_base'],1000)
        self.assertEqual(self.s.cash_status()['expected_cents'],10000)
        with self.assertRaises(self.s.ConflictError):
            self.s.cancel_sale(sale['id'],{'reason':'Duas vezes','confirm_refunds':True})

    def test_zero_value_sales_are_blocked_without_stock_deduction(self):
        p=self.product(name='Desconto total',stock='5',price='10.00')
        self.s.open_cash({'opening':'20.00'})
        scenarios=(
            {'discount_percent':'100','discount_fixed':'0'},
            {'discount_percent':'0','discount_fixed':'10.00'},
        )
        for index, discounts in enumerate(scenarios, 1):
            with self.subTest(scenario=index):
                with self.assertRaisesRegex(self.s.ValidationError, r'maior que R\$ 0,00'):
                    self.s.create_sale({
                        'token':f'zero-value-test-{index}',
                        'items':[{'product_id':p['id'],'quantity':'1'}],
                        **discounts, 'payments':[],
                    })
                self.assertEqual(self.s.row_or_404('products',p['id'])['stock_base'],5)
                self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0],0)
                self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM stock_movements WHERE kind=\'SALE\'').fetchone()[0],0)
        # Valor pequeno que arredonda a zero também é inválido.
        kg=self.product(name='Fração',unit='KG',stock='1.000',price='1.00')
        with self.assertRaises(self.s.ValidationError):
            self.s.create_sale({'token':'zero-value-test-tiny',
                'items':[{'product_id':kg['id'],'quantity':'0.001'}],
                'discount_percent':'0','discount_fixed':'0','payments':[]})
        self.assertEqual(self.s.row_or_404('products',kg['id'])['stock_base'],1000)

    def test_atomic_rollback_when_payment_invalid(self):
        p=self.product(stock='1');self.s.open_cash({'opening':'0'})
        with self.assertRaises(self.s.ValidationError):
            self.s.create_sale({'token':'unique-test-002','items':[{'product_id':p['id'],'quantity':'1'}],
                                'payments':[{'method':'PIX','applied':'5.00'}]})
        self.assertEqual(self.s.row_or_404('products',p['id'])['stock_base'],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0],0)

    def test_credit_partial_and_cancel_received(self):
        p=self.product(stock='5',price='10.00')
        client=self.s.add_customer({'name':'Maria'})
        self.s.open_cash({'opening':'50.00'})
        sale=self.s.create_sale({'token':'unique-test-003','items':[{'product_id':p['id'],'quantity':'2'}],
                'payments':[{'method':'CREDIT','customer_id':client['id'],'applied':'20.00'}]})
        d=self.s.list_debts()[0]
        self.assertEqual(d['outstanding_cents'],2000)
        self.s.receive_credit(d['id'],{'amount':'7.00','method':'CASH'})
        self.assertEqual(self.s.list_debts()[0]['outstanding_cents'],1300)
        self.assertEqual(self.s.cash_status()['expected_cents'],5700)
        preview=self.s.cancel_preview(sale['id'])
        self.assertEqual(preview['total_refund_cents'],700)
        self.assertEqual(preview['outstanding_credit_cents'],1300)
        self.s.cancel_sale(sale['id'],{'reason':'Estorno com devolução','confirm_refunds':True})
        self.assertEqual(self.s.list_debts()[0]['status'],'CANCELED')
        self.assertEqual(self.s.cash_status()['expected_cents'],5000)

    def test_stock_entry_then_inactivate_historical(self):
        p=self.product(stock='0')
        self.s.stock_entry(p['id'],{'quantity':'3','note':'Reposição'})
        self.assertEqual(self.s.remove_product(p['id'])['action'],'INACTIVATED')
        self.assertFalse(self.s.row_or_404('products',p['id'])['active'])

    def test_close_cash_requires_note_when_different(self):
        self.s.open_cash({'opening':'20.00'})
        with self.assertRaises(self.s.ValidationError):self.s.close_cash({'counted':'19.00','note':''})
        closed=self.s.close_cash({'counted':'19.00','note':'Conferido manualmente'})
        self.assertEqual(closed['difference_cents'],-100)
        self.assertEqual(self.s.cash_status()['status'],'CLOSED')

    def test_transaction_rolls_back_on_database_failure(self):
        p=self.product(stock='3',price='6.00')
        self.s.open_cash({'opening':'10.00'})
        self.conn.execute("CREATE TRIGGER fail_items BEFORE INSERT ON sale_items BEGIN SELECT RAISE(ABORT,'Falha de simulação'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.create_sale({'token':'unique-test-crash','items':[{'product_id':p['id'],'quantity':'1'}],
                                'payments':[{'method':'CASH','applied':'6.00'}]})
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0],0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM cash_movements WHERE kind='SALE_CASH'").fetchone()[0],0)
        self.assertEqual(self.s.row_or_404('products',p['id'])['stock_base'],3)

    def test_sales_without_open_cash(self):
        p=self.product()
        with self.assertRaises(self.s.ConflictError):self.s.create_sale({'token':'unique-test-004','items':[{'product_id':p['id'],'quantity':'1'}], 'payments':[{'method':'CASH','applied':'6.00'}]})

    def test_reports_dont_count_canceled(self):
        p=self.product(stock='5',price='5.00');self.s.open_cash({'opening':'50.00'})
        sale=self.s.create_sale({'token':'unique-test-005','items':[{'product_id':p['id'],'quantity':'1'}],
                          'payments':[{'method':'PIX','applied':'5.00'}]})
        self.assertEqual(self.s.reports()['revenue_cents'],500)
        self.s.cancel_sale(sale['id'],{'reason':'Erro','confirm_refunds':True})
        self.assertEqual(self.s.reports()['revenue_cents'],0)

if __name__=='__main__':unittest.main()
