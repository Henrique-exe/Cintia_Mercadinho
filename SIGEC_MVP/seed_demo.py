"""Adiciona APENAS dados fictícios; não altera produtos reais preexistentes."""
from sigec import create_app
from sigec.db import get_db
from sigec.services import save_product, add_customer

app=create_app()
with app.app_context():
    db=get_db()
    if db.execute('SELECT 1 FROM products LIMIT 1').fetchone():
        print('Banco já tem produtos. Nada foi substituído.')
    else:
        for p in [
            dict(name='Arroz Marca A 1 kg',brand='Marca A',presentation='Pacote 1 kg',category='Mercearia',unit='UN',barcode='7890000000011',purchase_price='4.50',price='6.00',stock='3',minimum='5',active=True),
            dict(name='Salsicha a granel',brand='',presentation='A granel',category='Carnes',unit='KG',barcode='',purchase_price='14.00',price='20.00',stock='1.200',minimum='2.000',active=True),
            dict(name='Feijão Marca C 1 kg',brand='Marca C',presentation='Pacote 1 kg',category='Mercearia',unit='UN',barcode='',purchase_price='5.00',price='8.00',stock='10',minimum='5',active=True),
            dict(name='Refrigerante B 2 L',brand='Marca B',presentation='Garrafa 2 L',category='Bebidas',unit='UN',barcode='',purchase_price='6.00',price='9.00',stock='0',minimum='6',active=True),
        ]: save_product(p)
        print('4 produtos fictícios cadastrados.')
    if not db.execute('SELECT 1 FROM customers LIMIT 1').fetchone():
        add_customer({'name':'Maria (exemplo fictício)','phone':'(75) 90000-0000'})
        add_customer({'name':'João (exemplo fictício)','phone':'(75) 90000-0001'})
        print('2 clientes fictícios cadastrados.')
