"""Integração HTTP — executar após instalar Flask: python -m unittest discover -s tests -v."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HAS_FLASK = importlib.util.find_spec('flask') is not None


@unittest.skipUnless(HAS_FLASK,'Flask não instalado no ambiente de teste')
class HTTPTests(unittest.TestCase):
    def setUp(self):
        from sigec import create_app
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'DATABASE':str(Path(self.temp.name)/'db.sqlite3')})
        self.client=self.app.test_client()

    def tearDown(self): self.temp.cleanup()

    def post(self,path,body):return self.client.post('/api'+path,json=body)

    def test_health_products_and_restart(self):
        self.assertEqual(self.client.get('/api/health').json['status'],'ok')
        r=self.post('/products',{'name':'Arroz','unit':'UN','stock':'7','minimum':'10','price':'6.00'})
        self.assertEqual(r.status_code,201)
        self.assertEqual(r.json['stock_base'],7)
        self.assertEqual(self.client.get('/api/products').json[0]['name'],'Arroz')
        self.assertEqual(self.client.get('/api/shopping').json[0]['buy_base'],3)
        from sigec import create_app
        second=create_app({'TESTING':True,'DATABASE':self.app.config['DATABASE']}).test_client()
        self.assertEqual(len(second.get('/api/products').json),1)

    def test_sale_flow_and_cancel(self):
        p=self.post('/products',{'name':'Arroz','unit':'UN','price':'6.00','stock':'4'}).json
        self.assertEqual(self.post('/sales',{'items':[]}).status_code,400)
        self.assertEqual(self.post('/cash/open',{'opening':'20.00'}).status_code,201)
        sale=self.post('/sales',{'token':'http-test-001','items':[{'product_id':p['id'],'quantity':'2'}],
              'discount_percent':'0','discount_fixed':'0',
              'payments':[{'method':'CASH','applied':'12.00','tendered':'20.00'}]})
        self.assertEqual(sale.status_code,201)
        self.assertEqual(sale.json['payments'][0]['change_cents'],800)
        self.assertEqual(self.client.get('/api/cash').json['expected_cents'],3200)
        self.assertEqual(self.client.get('/api/products').json[0]['stock_base'],2)
        canceled=self.post('/sales/'+str(sale.json['id'])+'/cancel',{'reason':'Erro de registro','confirm_refunds':True})
        self.assertEqual(canceled.status_code,200)
        self.assertEqual(self.client.get('/api/products').json[0]['stock_base'],4)
        self.assertEqual(self.client.get('/api/cash').json['expected_cents'],2000)
        self.assertEqual(self.post('/sales/'+str(sale.json['id'])+'/cancel',{'reason':'repetido','confirm_refunds':True}).status_code,409)

    def test_zero_total_rejected_by_http_without_changes(self):
        p=self.post('/products',{'name':'Teste zero','unit':'UN','price':'10.00','stock':'3'}).json
        self.post('/cash/open',{'opening':'0'})
        sale=self.post('/sales',{'token':'http-zero-test-01',
            'items':[{'product_id':p['id'],'quantity':'1'}],
            'discount_percent':'100','discount_fixed':'0','payments':[]})
        self.assertEqual(sale.status_code,400)
        self.assertIn('maior que R$ 0,00',sale.json['error'])
        self.assertEqual(self.client.get('/api/products').json[0]['stock_base'],3)
        self.assertEqual(self.client.get('/api/sales').json,[])

    def test_validation_is_server_side(self):
        p=self.post('/products',{'name':'Salsicha','unit':'KG','price':'20.00','stock':'1.000'}).json
        self.post('/cash/open',{'opening':'0'})
        r=self.post('/sales',{'token':'http-test-002','items':[{'product_id':p['id'],'quantity':'1.001'}],
                        'payments':[{'method':'PIX','applied':'20.02'}]})
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.client.get('/api/products').json[0]['stock_base'],1000)


if __name__=='__main__':unittest.main()
