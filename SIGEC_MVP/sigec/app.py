"""Rotas HTTP do SIGEC. Executado apenas em 127.0.0.1 pelo run.py."""
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from .db import get_db, close_db, init_db
from . import services as s
from .paths import get_paths


def create_app(test_config=None):
    app=Flask(__name__, static_folder='static', template_folder='templates')
    app.config.update(DATABASE=str(get_paths().database), JSON_AS_ASCII=False,
                      MAX_CONTENT_LENGTH=2*1024*1024, TEMPLATES_AUTO_RELOAD=False)
    if test_config: app.config.update(test_config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True,exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context(): init_db()

    @app.after_request
    def security_headers(resp):
        resp.headers['X-Content-Type-Options']='nosniff'
        resp.headers['X-Frame-Options']='DENY'
        resp.headers['Referrer-Policy']='no-referrer'
        resp.headers['Cache-Control']='no-store'
        resp.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        return resp

    @app.errorhandler(s.ValidationError)
    def failed(e): return jsonify(error=str(e)),e.status_code

    @app.errorhandler(HTTPException)
    def http_error(e): return jsonify(error=e.description),e.code

    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.exception('Falha interna')
        return jsonify(error='Erro interno. A operação não foi confirmada; confira os dados antes de tentar novamente.'),500

    def body():
        if request.mimetype!='application/json':
            raise s.ValidationError('Envie dados no formato JSON.')
        o=request.get_json(silent=True)
        if not isinstance(o,dict): raise s.ValidationError('Dados JSON inválidos.')
        return o

    @app.get('/')
    def index(): return render_template('index.html')

    @app.get('/api/health')
    def health(): return jsonify(status='ok',storage='SQLite local')

    @app.get('/api/dashboard')
    def dashboard(): return jsonify(s.dashboard())

    @app.get('/api/products')
    def products(): return jsonify(s.list_products(request.args.get('search',''),request.args.get('category',''),request.args.get('status','')))

    @app.post('/api/products')
    def create_product(): return jsonify(s.save_product(body())),201

    @app.put('/api/products/<int:pid>')
    def update_product(pid): return jsonify(s.save_product(body(),pid))

    @app.delete('/api/products/<int:pid>')
    def delete_product(pid): return jsonify(s.remove_product(pid))

    @app.post('/api/products/<int:pid>/entry')
    def entry(pid): return jsonify(s.stock_entry(pid,body()))

    @app.get('/api/shopping')
    def shopping(): return jsonify(s.list_shopping())

    @app.put('/api/shopping/<int:pid>')
    def shopping_edit(pid): return jsonify(s.edit_shopping(pid,body()))

    @app.get('/api/customers')
    def customers(): return jsonify(s.list_customers(request.args.get('search','')))

    @app.post('/api/customers')
    def customer_create(): return jsonify(s.add_customer(body())),201

    @app.get('/api/cash')
    def cash(): return jsonify(s.cash_status())

    @app.get('/api/cash/history')
    def cash_history(): return jsonify(s.cash_history())

    @app.post('/api/cash/open')
    def cash_open(): return jsonify(s.open_cash(body())),201

    @app.post('/api/cash/withdraw')
    def cash_withdraw(): return jsonify(s.withdraw_cash(body()))

    @app.post('/api/cash/close')
    def cash_close(): return jsonify(s.close_cash(body()))

    @app.get('/api/sales')
    def sales(): return jsonify(s.list_sales(request.args.get('search','')))

    @app.get('/api/sales/<int:sid>')
    def sale(sid): return jsonify(s.public_sale(sid))

    @app.post('/api/sales')
    def sale_create(): return jsonify(s.create_sale(body())),201

    @app.get('/api/sales/<int:sid>/cancel-preview')
    def cancel_preview(sid): return jsonify(s.cancel_preview(sid))

    @app.post('/api/sales/<int:sid>/cancel')
    def sale_cancel(sid): return jsonify(s.cancel_sale(sid,body()))

    @app.get('/api/credit')
    def debts(): return jsonify(s.list_debts(request.args.get('search','')))

    @app.post('/api/credit/<int:debt_id>/receive')
    def receive(debt_id): return jsonify(s.receive_credit(debt_id,body()))

    @app.get('/api/reports')
    def reports(): return jsonify(s.reports(request.args.get('period','day'),request.args.get('date')))

    return app
