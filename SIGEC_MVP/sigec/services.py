"""Regras centrais do SIGEC: Decimal, centavos, gramas, integridade e auditoria."""
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sqlite3
from .db import get_db, atomic, rowdict

CENT = Decimal('0.01')
PERMITTED_METHODS = ('CASH', 'PIX', 'CARD', 'CREDIT')


class ValidationError(Exception):
    status_code = 400


class ConflictError(ValidationError):
    status_code = 409


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def parse_decimal(value, field):
    if isinstance(value, (bool, type(None), float)):
        raise ValidationError(f'{field}: informe um número decimal válido.')
    s = str(value).strip().replace('R$', '').replace(' ', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        x = Decimal(s)
    except (InvalidOperation, ValueError):
        raise ValidationError(f'{field}: valor inválido.')
    if not x.is_finite():
        raise ValidationError(f'{field}: número inválido.')
    if abs(x) > Decimal('100000000'):
        raise ValidationError(f'{field}: valor fora do limite.')
    return x


def money(value, field='Valor', allow_zero=True):
    d = parse_decimal(value, field)
    if d < 0 or (not allow_zero and d == 0):
        raise ValidationError(f'{field}: informe um valor positivo.')
    if d != d.quantize(CENT):
        raise ValidationError(f'{field}: use no máximo duas casas decimais.')
    return int(d * 100)


def quantity(value, unit, field='Quantidade', allow_zero=True):
    d = parse_decimal(value, field)
    if d < 0 or (d == 0 and not allow_zero):
        raise ValidationError(f'{field}: informe uma quantidade positiva.')
    if unit == 'UN':
        if d != d.to_integral_value():
            raise ValidationError(f'{field}: produto UN aceita apenas inteiros.')
        return int(d)
    if unit == 'KG':
        if d != d.quantize(Decimal('0.001')):
            raise ValidationError(f'{field}: produto KG aceita no máximo três casas decimais.')
        return int(d * 1000)
    raise ValidationError('Unidade inválida (UN ou KG).')


def qty_label(base, unit):
    if unit == 'UN':
        return str(base)
    return f'{base // 1000},{base % 1000:03d}'


def row_or_404(table, id):
    if table not in ('products', 'customers', 'cash_sessions', 'sales', 'debts'):
        raise ValidationError('Consulta inválida.')
    row = get_db().execute(f'SELECT * FROM {table} WHERE id=?', (id,)).fetchone()
    if row is None:
        raise ValidationError('Registro não encontrado.')
    return row


def current_cash():
    return get_db().execute("SELECT * FROM cash_sessions WHERE status='OPEN' LIMIT 1").fetchone()


def require_cash():
    row = current_cash()
    if row is None:
        raise ConflictError('Abra o caixa antes de registrar operações financeiras.')
    return row


def cash_balance(session_id):
    return get_db().execute('SELECT COALESCE(SUM(amount_cents),0) FROM cash_movements WHERE session_id=?', (session_id,)).fetchone()[0]


def cash_movement(db, session_id, kind, cents, note='', sale_id=None, receipt_id=None):
    db.execute('''INSERT INTO cash_movements(session_id,kind,amount_cents,note,sale_id,receipt_id,created_at)
                  VALUES(?,?,?,?,?,?,?)''', (session_id,kind,cents,note,sale_id,receipt_id,now()))


def product_view(p):
    d = dict(p)
    d['active'] = bool(d['active'])
    d['stock_label'] = qty_label(d['stock_base'],d['unit'])
    d['minimum_label'] = qty_label(d['minimum_base'],d['unit'])
    d['stock_status'] = 'INACTIVE' if not d['active'] else 'EMPTY' if d['stock_base']==0 else 'LOW' if d['stock_base']<d['minimum_base'] else 'OK'
    return d


def list_products(search='', category='', status=''):
    rows = get_db().execute('SELECT * FROM products ORDER BY active DESC, name COLLATE NOCASE').fetchall()
    results=[]
    for p in rows:
        d=product_view(p)
        if search and search.casefold() not in (' '.join([p['name'],p['brand'],p['presentation'],p['barcode'] or ''])).casefold():
            continue
        if category and category != p['category']:
            continue
        if status and d['stock_status']!=status:
            continue
        results.append(d)
    return results


def save_product(data, product_id=None):
    name=str(data.get('name','')).strip()
    if not name: raise ValidationError('Informe o nome do produto.')
    if len(name)>160: raise ValidationError('Nome do produto muito longo.')
    brand=str(data.get('brand','')).strip()[:100]
    presentation=str(data.get('presentation','')).strip()[:100]
    category=str(data.get('category','')).strip()[:80]
    barcode=str(data.get('barcode') or '').strip() or None
    unit=str(data.get('unit','')).upper()
    if unit not in ('UN','KG'): raise ValidationError('Unidade deve ser UN ou KG.')
    price=money(data.get('price',''), 'Preço de venda')
    purchase=money(data.get('purchase_price','0'), 'Preço de compra')
    min_stock=quantity(data.get('minimum','0'),unit,'Estoque mínimo')
    active=data.get('active', True)
    if type(active) is not bool: raise ValidationError('Situação do produto inválida.')
    db=get_db()
    try:
        with atomic():
            if product_id is None:
                stock=quantity(data.get('stock','0'),unit,'Estoque inicial')
                cur=db.execute('''INSERT INTO products(name,brand,presentation,category,barcode,unit,
                            purchase_price_cents,price_cents,stock_base,minimum_base,active)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                            (name,brand,presentation,category,barcode,unit,purchase,price,stock,min_stock,int(active)))
                product_id=cur.lastrowid
            else:
                p=row_or_404('products',product_id)
                if p['unit']!=unit:
                    linked=db.execute('SELECT 1 FROM sale_items WHERE product_id=? UNION SELECT 1 FROM stock_movements WHERE product_id=?', (product_id,product_id)).fetchone()
                    if linked or p['stock_base']!=0:
                        raise ConflictError('Não é possível trocar unidade com estoque ou histórico. Crie outro produto.')
                db.execute('''UPDATE products SET name=?,brand=?,presentation=?,category=?,barcode=?,unit=?,
                            purchase_price_cents=?,price_cents=?,minimum_base=?,active=? WHERE id=?''',
                            (name,brand,presentation,category,barcode,unit,purchase,price,min_stock,int(active),product_id))
    except sqlite3.IntegrityError as e:
        raise ConflictError('Código de barras já cadastrado ou dados inválidos.') from e
    return product_view(row_or_404('products',product_id))


def remove_product(product_id):
    db=get_db()
    with atomic():
        p=row_or_404('products',product_id)
        hist=db.execute('SELECT 1 FROM sale_items WHERE product_id=? UNION SELECT 1 FROM stock_movements WHERE product_id=?', (product_id,product_id)).fetchone()
        if hist:
            db.execute('UPDATE products SET active=0 WHERE id=?',(product_id,))
            return {'action':'INACTIVATED','message':'Produto inativado. Histórico preservado.'}
        db.execute('DELETE FROM products WHERE id=?',(product_id,))
        return {'action':'DELETED','message':'Produto sem movimentações excluído.'}


def stock_entry(product_id,data):
    db=get_db()
    with atomic():
        p=row_or_404('products',product_id)
        q=quantity(data.get('quantity',''),p['unit'],allow_zero=False)
        next_stock=p['stock_base']+q
        note=str(data.get('note','')).strip()[:300]
        db.execute('UPDATE products SET stock_base=? WHERE id=?',(next_stock,product_id))
        db.execute('''INSERT INTO stock_movements(product_id,kind,quantity_base,stock_after_base,note,created_at)
                      VALUES(?,'ENTRY',?,?,?,?)''',(product_id,q,next_stock,note,now()))
    return product_view(row_or_404('products',product_id))


def list_shopping():
    db=get_db()
    entries={r['product_id']:dict(r) for r in db.execute('SELECT * FROM shopping_entries')}
    result=[]
    for p in db.execute('SELECT * FROM products WHERE active=1 ORDER BY name COLLATE NOCASE'):
        e=entries.get(p['id'])
        low=p['stock_base']<p['minimum_base']
        if not low and not (e and e['manual']): continue
        suggested=max(p['minimum_base']-p['stock_base'],0)
        count=e['quantity_base'] if e else suggested
        result.append({**product_view(p),'buy_base':count,'buy_label':qty_label(count,p['unit']),
                       'checked':bool(e['checked']) if e else False,'manual':bool(e['manual']) if e else False,
                       'estimated_cents':(p['purchase_price_cents']*count + (500 if p['unit']=='KG' else 0))//(1000 if p['unit']=='KG' else 1)})
    return result


def edit_shopping(product_id, data):
    p=row_or_404('products',product_id)
    if not p['active']: raise ValidationError('Produto inativo.')
    qty=quantity(data.get('quantity','0'),p['unit'],'Quantidade a comprar')
    checked=data.get('checked',False)
    manual=data.get('manual',True)
    if not isinstance(checked,bool) or not isinstance(manual,bool):
        raise ValidationError('Estado da lista inválido.')
    with atomic():
        get_db().execute('''INSERT INTO shopping_entries(product_id,quantity_base,checked,manual)
          VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET quantity_base=excluded.quantity_base,
          checked=excluded.checked,manual=excluded.manual''',(product_id,qty,int(checked),int(manual)))
    return list_shopping()


def list_customers(search=''):
    return [dict(x) for x in get_db().execute('SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name COLLATE NOCASE',('%'+search+'%','%'+search+'%'))]


def add_customer(data):
    name=str(data.get('name','')).strip()
    if not name: raise ValidationError('Nome do cliente é obrigatório.')
    if len(name)>150: raise ValidationError('Nome de cliente muito longo.')
    phone=str(data.get('phone','')).strip()[:40]
    with atomic():
        id=get_db().execute('INSERT INTO customers(name,phone) VALUES(?,?)',(name,phone)).lastrowid
    return rowdict(row_or_404('customers',id))


def cash_status():
    sess=current_cash()
    if sess:
        return {**dict(sess),'expected_cents':cash_balance(sess['id']), 'movements':[
            dict(x) for x in get_db().execute('SELECT * FROM cash_movements WHERE session_id=? ORDER BY id DESC LIMIT 100',(sess['id'],))]}
    closed=get_db().execute('SELECT * FROM cash_sessions ORDER BY id DESC LIMIT 1').fetchone()
    return {'status':'CLOSED','last_session':rowdict(closed),'expected_cents':None,'movements':[]}


def open_cash(data):
    opening=money(data.get('opening','0'),'Fundo de troco')
    note=str(data.get('note','')).strip()[:300]
    with atomic():
        if current_cash(): raise ConflictError('Já existe caixa aberto.')
        db=get_db()
        id=db.execute("INSERT INTO cash_sessions(opened_at,opening_cents,opening_note,status) VALUES(?,?,?,'OPEN')",(now(),opening,note)).lastrowid
        cash_movement(db,id,'OPENING',opening,note)
    return cash_status()


def withdraw_cash(data):
    cents=money(data.get('amount',''),'Sangria',allow_zero=False)
    note=str(data.get('reason','')).strip()
    if not note: raise ValidationError('A sangria exige justificativa.')
    with atomic():
        session=require_cash()
        if cash_balance(session['id'])<cents: raise ConflictError('Sangria maior que o dinheiro esperado na gaveta.')
        cash_movement(get_db(),session['id'],'WITHDRAW',-cents,note[:300])
    return cash_status()


def close_cash(data):
    counted=money(data.get('counted',''),'Dinheiro contado')
    note=str(data.get('note','')).strip()[:300]
    with atomic():
        session=require_cash()
        expected=cash_balance(session['id'])
        difference=counted-expected
        if difference != 0 and not note:
            raise ValidationError('Justifique a diferença entre valor contado e esperado.')
        get_db().execute("""UPDATE cash_sessions SET status='CLOSED', closed_at=?,expected_cents=?,
            counted_cents=?,difference_cents=?,closing_note=? WHERE id=?""",
            (now(),expected,counted,difference,note,session['id']))
    return dict(row_or_404('cash_sessions',session['id']))


def cash_history():
    return [dict(r) for r in get_db().execute('SELECT * FROM cash_sessions ORDER BY id DESC LIMIT 60')]


def calc_line(price,qty,unit):
    factor=1000 if unit=='KG' else 1
    return int((Decimal(price)*Decimal(qty)/factor).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def discounts(subtotal,pct_input,fixed_input):
    pct=parse_decimal(pct_input,'Desconto percentual')
    if pct<0 or pct>100: raise ValidationError('Desconto percentual precisa estar entre 0 e 100.')
    fixed=money(fixed_input,'Desconto em reais')
    pct_cents=int((Decimal(subtotal)*pct/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    total=subtotal-pct_cents-fixed
    if total<0: raise ValidationError('Desconto ultrapassa o subtotal da venda.')
    return pct,pct_cents,fixed,total


def public_sale(sale_id):
    db=get_db()
    sale=row_or_404('sales',sale_id)
    d=dict(sale)
    d['items']=[dict(x) for x in db.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale_id,))]
    d['payments']=[dict(x) for x in db.execute('SELECT * FROM sale_payments WHERE sale_id=?',(sale_id,))]
    d['debts']=[dict(x) for x in db.execute('SELECT * FROM debts WHERE sale_id=?',(sale_id,))]
    d['refunds']=[dict(x) for x in db.execute('SELECT * FROM refunds WHERE sale_id=?',(sale_id,))]
    return d


def create_sale(data):
    raw_items=data.get('items',[])
    raw_payments=data.get('payments',[])
    if not isinstance(raw_items,list) or not raw_items:
        raise ValidationError('Adicione produtos à venda.')
    if len(raw_items)>150: raise ValidationError('Muitos itens nesta venda.')
    if not isinstance(raw_payments,list): raise ValidationError('Pagamentos inválidos.')
    token=str(data.get('token','')).strip()
    if not 8<=len(token)<=120: raise ValidationError('Identificador da operação inválido.')
    db=get_db()
    with atomic():
        existing=db.execute('SELECT id FROM sales WHERE client_token=?',(token,)).fetchone()
        if existing: return public_sale(existing['id'])
        session=require_cash()
        quantities={}
        for raw in raw_items:
            if not isinstance(raw,dict): raise ValidationError('Item de venda inválido.')
            try: pid=int(raw.get('product_id'))
            except (TypeError,ValueError): raise ValidationError('Produto inválido.')
            product=row_or_404('products',pid)
            if not product['active']: raise ConflictError(f"Produto inativo: {product['name']}")
            q=quantity(raw.get('quantity',''),product['unit'],allow_zero=False)
            quantities[pid]=quantities.get(pid,0)+q
        items=[]
        subtotal=0
        for pid,q in quantities.items():
            p=row_or_404('products',pid)
            if p['stock_base']<q: raise ConflictError(f"Estoque insuficiente para {p['name']} (disponível: {qty_label(p['stock_base'],p['unit'])} {p['unit']}).")
            line=calc_line(p['price_cents'],q,p['unit'])
            items.append((p,q,line))
            subtotal+=line
        pct,pct_cents,fixed,total=discounts(subtotal,data.get('discount_percent','0'),data.get('discount_fixed','0'))
        # Não permitir que descontos de 100% ou valores arredondados zerem a venda.
        # Validar antes de gravar qualquer item, pagamento ou movimentação de estoque.
        if total <= 0:
            raise ValidationError('O total da venda deve ser maior que R$ 0,00. Reduza os descontos ou revise os produtos antes de concluir.')
        payment_rows=[]
        total_applied=0
        credit_customer_id=None
        credit_total=0
        for raw in raw_payments:
            if not isinstance(raw,dict): raise ValidationError('Pagamento inválido.')
            method=str(raw.get('method','')).upper()
            if method not in PERMITTED_METHODS: raise ValidationError('Forma de pagamento inválida.')
            applied=money(raw.get('applied',''),'Valor aplicado',allow_zero=False)
            tendered=0
            change=0
            customer_id=None
            if method=='CASH':
                tendered=money(raw.get('tendered',raw.get('applied')),'Dinheiro entregue')
                if tendered<applied: raise ValidationError('Dinheiro entregue menor que dinheiro aplicado.')
                change=tendered-applied
            elif method=='CREDIT':
                try: customer_id=int(raw.get('customer_id'))
                except (TypeError,ValueError): raise ValidationError('Selecione o cliente para o fiado.')
                row_or_404('customers',customer_id)
                if credit_customer_id is not None and credit_customer_id != customer_id:
                    raise ValidationError('Use um único cliente para a caderneta desta venda.')
                credit_customer_id=customer_id
                credit_total+=applied
            total_applied+=applied
            payment_rows.append((method,applied,tendered,change,customer_id))
        if total_applied!=total:
            raise ValidationError(f'Pagamentos somam {total_applied/100:.2f}; total da venda é {total/100:.2f}.')
        sid=db.execute('''INSERT INTO sales(created_at,status,subtotal_cents,discount_percent,
              discount_percent_cents,discount_fixed_cents,total_cents,session_id,client_token)
              VALUES(?,'COMPLETED',?,?,?,?,?,?,?)''',
              (now(),subtotal,str(pct),pct_cents,fixed,total,session['id'],token)).lastrowid
        for p,q,line in items:
            stock=p['stock_base']-q
            db.execute('''INSERT INTO sale_items(sale_id,product_id,name_snapshot,unit,quantity_base,price_cents,line_total_cents,cost_cents)
                          VALUES(?,?,?,?,?,?,?,?)''',(sid,p['id'],p['name'],p['unit'],q,p['price_cents'],line,
                              calc_line(p['purchase_price_cents'],q,p['unit']) if p['purchase_price_cents'] > 0 else None))
            db.execute('UPDATE products SET stock_base=? WHERE id=?',(stock,p['id']))
            db.execute('''INSERT INTO stock_movements(product_id,sale_id,kind,quantity_base,stock_after_base,note,created_at)
                     VALUES(?,?,'SALE',?,?,?,?)''',(p['id'],sid,-q,stock,'Venda',now()))
        for method,applied,tendered,change,customer_id in payment_rows:
            db.execute('''INSERT INTO sale_payments(sale_id,method,applied_cents,tendered_cents,change_cents,customer_id)
                          VALUES(?,?,?,?,?,?)''',(sid,method,applied,tendered,change,customer_id))
            if method=='CASH':
                cash_movement(db,session['id'],'SALE_CASH',applied,'Dinheiro líquido da venda',sid)
        if credit_total:
            db.execute('''INSERT INTO debts(sale_id,customer_id,original_cents,outstanding_cents,status)
                          VALUES(?,?,?,?,'OPEN')''',(sid,credit_customer_id,credit_total,credit_total))
    return public_sale(sid)


def list_sales(search=''):
    rows=get_db().execute('SELECT * FROM sales ORDER BY id DESC LIMIT 200').fetchall()
    return [dict(r) for r in rows if not search or search in str(r['id']) or search in r['created_at']]


def cancel_preview(sale_id):
    sale=row_or_404('sales',sale_id)
    if sale['status']!='COMPLETED': raise ConflictError('Venda já cancelada.')
    db=get_db()
    amounts={}
    for r in db.execute("SELECT method,SUM(applied_cents) AS amount FROM sale_payments WHERE sale_id=? AND method<>'CREDIT' GROUP BY method",(sale_id,)):
        amounts[r['method']]=r['amount']
    for r in db.execute('''SELECT cr.method,SUM(cr.amount_cents) AS amount FROM credit_receipts cr
      JOIN debts d ON d.id=cr.debt_id WHERE d.sale_id=? GROUP BY cr.method''',(sale_id,)):
        amounts[r['method']]=amounts.get(r['method'],0)+r['amount']
    debt=db.execute('SELECT * FROM debts WHERE sale_id=?',(sale_id,)).fetchone()
    return {'sale_id':sale_id,'refunds':[{'method':k,'amount_cents':v} for k,v in amounts.items() if v],
            'total_refund_cents':sum(amounts.values()),'outstanding_credit_cents':debt['outstanding_cents'] if debt else 0}


def cancel_sale(sale_id,data):
    reason=str(data.get('reason','')).strip()
    if not reason: raise ValidationError('Informe o motivo do cancelamento.')
    if data.get('confirm_refunds') is not True:
        raise ValidationError('Confirme que as devoluções financeiras foram efetuadas antes de cancelar.')
    db=get_db()
    with atomic():
        session=require_cash()
        sale=row_or_404('sales',sale_id)
        if sale['status']!='COMPLETED': raise ConflictError('Esta venda já foi cancelada.')
        preview=cancel_preview(sale_id)
        cash_return=sum(x['amount_cents'] for x in preview['refunds'] if x['method']=='CASH')
        if cash_return>cash_balance(session['id']):
            raise ConflictError('Dinheiro esperado insuficiente para as devoluções em espécie. Regularize o caixa.')
        for it in db.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale_id,)).fetchall():
            product=row_or_404('products',it['product_id'])
            next_stock=product['stock_base']+it['quantity_base']
            db.execute('UPDATE products SET stock_base=? WHERE id=?',(next_stock,it['product_id']))
            db.execute('''INSERT INTO stock_movements(product_id,sale_id,kind,quantity_base,stock_after_base,note,created_at)
                          VALUES(?,?,'CANCEL',?,?,?,?)''',(it['product_id'],sale_id,it['quantity_base'],next_stock,reason[:300],now()))
        for refund in preview['refunds']:
            method=refund['method']; amount=refund['amount_cents']
            db.execute('''INSERT INTO refunds(sale_id,session_id,method,amount_cents,note,created_at)
                          VALUES(?,?,?,?,?,?)''',(sale_id,session['id'],method,amount,reason[:300],now()))
            if method=='CASH':
                cash_movement(db,session['id'],'REFUND_CASH',-amount,'Devolução venda #'+str(sale_id),sale_id)
        db.execute("UPDATE debts SET outstanding_cents=0,status='CANCELED' WHERE sale_id=?",(sale_id,))
        db.execute("UPDATE sales SET status='CANCELED',canceled_at=?,cancel_reason=? WHERE id=?",(now(),reason[:400],sale_id))
    return public_sale(sale_id)


def list_debts(search=''):
    db=get_db()
    rows=db.execute('''SELECT d.*,c.name AS customer_name,c.phone,s.created_at AS sale_date
      FROM debts d JOIN customers c ON c.id=d.customer_id JOIN sales s ON s.id=d.sale_id
      ORDER BY CASE d.status WHEN 'OPEN' THEN 0 ELSE 1 END,d.id DESC''').fetchall()
    return [dict(r) for r in rows if not search or search.casefold() in (r['customer_name']+' '+r['phone']+' '+str(r['sale_id'])).casefold()]


def receive_credit(debt_id,data):
    cents=money(data.get('amount',''),'Valor recebido',allow_zero=False)
    method=str(data.get('method','')).upper()
    if method not in ('CASH','PIX','CARD'): raise ValidationError('Recebimento deve ser Dinheiro, Pix ou Cartão.')
    db=get_db()
    with atomic():
        session=require_cash()
        debt=row_or_404('debts',debt_id)
        if debt['status']!='OPEN': raise ConflictError('Débito não está aberto.')
        if cents>debt['outstanding_cents']: raise ValidationError('Recebimento maior que o saldo pendente.')
        remaining=debt['outstanding_cents']-cents
        db.execute('UPDATE debts SET outstanding_cents=?,status=? WHERE id=?',
                   (remaining,'PAID' if remaining==0 else 'OPEN',debt_id))
        rid=db.execute('''INSERT INTO credit_receipts(debt_id,session_id,amount_cents,method,created_at)
                     VALUES(?,?,?,?,?)''',(debt_id,session['id'],cents,method,now())).lastrowid
        if method=='CASH':
            cash_movement(db,session['id'],'RECEIPT_CASH',cents,'Recebimento caderneta #'+str(debt_id),receipt_id=rid)
    return dict(row_or_404('debts',debt_id))


def dashboard():
    db=get_db()
    today=datetime.now().astimezone().date().isoformat()
    sales=db.execute("SELECT COUNT(*) AS count,COALESCE(SUM(total_cents),0) AS revenue FROM sales WHERE status='COMPLETED' AND substr(created_at,1,10)=?",(today,)).fetchone()
    debt=db.execute("SELECT COALESCE(SUM(outstanding_cents),0) FROM debts WHERE status='OPEN'").fetchone()[0]
    low=db.execute('SELECT COUNT(*) FROM products WHERE active=1 AND stock_base<minimum_base').fetchone()[0]
    cash=current_cash()
    return {'sales_today':sales['count'],'revenue_today_cents':sales['revenue'],
            'credit_pending_cents':debt,'low_stock_count':low,'cash_open':cash is not None,
            'cash_expected_cents':cash_balance(cash['id']) if cash else None,
            'low_products':list_shopping()[:6]}


def reports(period='day', date_value=None):
    if period not in ('day','month'): raise ValidationError('Período inválido.')
    if date_value is None or date_value=='': date_value=datetime.now().astimezone().date().isoformat()
    try: when=datetime.strptime(date_value,'%Y-%m-%d')
    except (TypeError,ValueError): raise ValidationError('Data inválida (AAAA-MM-DD).')
    prefix=when.strftime('%Y-%m-%d' if period=='day' else '%Y-%m')
    db=get_db()
    s=db.execute('''SELECT COUNT(*) AS count,COALESCE(SUM(total_cents),0) AS revenue,
      COALESCE(SUM(subtotal_cents),0) AS subtotal,
      COALESCE(SUM(discount_percent_cents+discount_fixed_cents),0) AS discounts
      FROM sales WHERE status='COMPLETED' AND substr(created_at,1,?)=?''',(len(prefix),prefix)).fetchone()
    receipt=db.execute('''SELECT COALESCE(SUM(amount_cents),0) FROM credit_receipts
      WHERE substr(created_at,1,?)=?''',(len(prefix),prefix)).fetchone()[0]
    canceled=db.execute('''SELECT COUNT(*) FROM sales WHERE status='CANCELED' AND substr(canceled_at,1,?)=?''',(len(prefix),prefix)).fetchone()[0]
    ref=db.execute('''SELECT COALESCE(SUM(amount_cents),0) FROM refunds
      WHERE substr(created_at,1,?)=?''',(len(prefix),prefix)).fetchone()[0]
    ranked=db.execute('''SELECT si.product_id,si.name_snapshot AS name,si.unit,
       SUM(si.quantity_base) AS quantity_base,SUM(si.line_total_cents) AS gross_cents
       FROM sale_items si JOIN sales s ON s.id=si.sale_id
       WHERE s.status='COMPLETED' AND substr(s.created_at,1,?)=?
       GROUP BY si.product_id,si.unit ORDER BY si.unit,quantity_base DESC LIMIT 50''',(len(prefix),prefix)).fetchall()
    # Valores de vendas por método no período da VENDA, sem misturar crédito pendente com caixa.
    sales_by_method = {method: 0 for method in PERMITTED_METHODS}
    for row in db.execute('''SELECT sp.method, SUM(sp.applied_cents) AS amount FROM sale_payments sp
          JOIN sales sa ON sa.id=sp.sale_id WHERE substr(sa.created_at,1,?)=? GROUP BY sp.method''',(len(prefix),prefix)):
        sales_by_method[row['method']] = row['amount']
    # Recebimentos de caderneta contam pela data do recebimento, nunca como nova venda.
    credit_by_method = {method: 0 for method in ('CASH','PIX','CARD')}
    for row in db.execute('''SELECT method,SUM(amount_cents) AS amount FROM credit_receipts
          WHERE substr(created_at,1,?)=? GROUP BY method''',(len(prefix),prefix)):
        credit_by_method[row['method']] = row['amount']
    refunds_by_method = {method: 0 for method in ('CASH','PIX','CARD')}
    for row in db.execute('''SELECT method,SUM(amount_cents) AS amount FROM refunds
          WHERE substr(created_at,1,?)=? GROUP BY method''',(len(prefix),prefix)):
        refunds_by_method[row['method']] = row['amount']
    # Fluxo financeiro recebido no período: pagamentos das vendas válidas +
    # quitação de fiado - devoluções realizadas no período. Faturamento é conceito separado.
    received_by_method = {method: sales_by_method[method] + credit_by_method[method] - refunds_by_method[method]
                          for method in ('CASH','PIX','CARD')}
    # Custo armazenado no momento de vender. Vendas antigas sem snapshot não têm lucro calculável.
    cost = db.execute('''SELECT COUNT(*) AS qty,
          COALESCE(SUM(CASE WHEN si.cost_cents IS NULL THEN 1 ELSE 0 END),0) AS unknown,
          COALESCE(SUM(si.cost_cents),0) AS cost
          FROM sale_items si JOIN sales sa ON sa.id=si.sale_id
          WHERE sa.status='COMPLETED' AND substr(sa.created_at,1,?)=?''',(len(prefix),prefix)).fetchone()
    cost_complete = cost['qty'] > 0 and cost['unknown'] == 0
    profit = s['revenue'] - cost['cost'] if cost_complete else None
    return {'period':period,'date':date_value,'sales_count':s['count'],'revenue_cents':s['revenue'],
            'subtotal_cents':s['subtotal'],'discounts_cents':s['discounts'],
            'credit_receipts_cents':receipt,'refunds_cents':ref,'cancellations_count':canceled,
            'sale_payments_by_method_cents':sales_by_method,
            'credit_receipts_by_method_cents':credit_by_method,
            'refunds_by_method_cents':refunds_by_method,
            'received_by_method_cents':received_by_method,
            'received_total_cents':sum(received_by_method.values()),
            'cost_cents':cost['cost'] if cost_complete else None,
            'gross_profit_cents':profit,
            'profit_available':cost_complete,'cost_missing_items':cost['unknown'],
            'ranking':[{**dict(r),'quantity_label':qty_label(r['quantity_base'],r['unit'])} for r in ranked]}
