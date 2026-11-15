/* SIGEC — interface 100% local, sem CDN ou dependências externas. */
'use strict';
const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => [...root.querySelectorAll(sel)];
const localDateISO = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
const state = {
  tab: 'dashboard', data: {}, cart: [], payments: [], discountPct: '0', discountFixed: '0',
  reportPeriod: 'day', reportDate: localDateISO(), sending: false, saleToken: null
};
const names = {dashboard:'Visão geral',sales:'Vendas / PDV',products:'Produtos e estoque',shopping:'Lista de compras',credit:'Caderneta',cash:'Caixa',reports:'Relatórios'};
const methods = {CASH:'Dinheiro',PIX:'Pix',CARD:'Cartão',CREDIT:'Fiado'};
const brl = n => (Number(n || 0)/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const esc = val => String(val ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = val => Number(String(val||'0').trim().includes(',') ? String(val).replace(/\./g,'').replace(',','.') : val) || 0;
const cleanMoney = cents => (Number(cents)/100).toFixed(2);
const fmtDate = val => val ? new Date(val).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}) : '—';
const pill = (value, map) => { let [kind,label]=map[value]||['gray',value]; return `<span class="tag ${kind}"><span class="dot"></span>${esc(label)}</span>`; };
const productPill = value => pill(value,{OK:['ok','Disponível'],LOW:['warn','Estoque baixo'],EMPTY:['bad','Em falta'],INACTIVE:['gray','Inativo']});
const salePill = value => pill(value,{COMPLETED:['ok','Concluída'],CANCELED:['bad','Cancelada']});
const cashPill = value => pill(value,{OPEN:['ok','Aberto'],CLOSED:['gray','Fechado']});
const empty = (message='Nenhum registro encontrado.',sub='') => `<div class="empty"><span class="empty-icon">◎</span><strong>${esc(message)}</strong><p>${esc(sub)}</p></div>`;
const head = (title, sub, actions='') => `<div class="page-head"><div><div class="eyebrow">SIGEC / GESTÃO LOCAL</div><h1>${title}</h1><p>${sub}</p></div><div class="actions">${actions}</div></div>`;
const kpi = (label,val,foot,icon='▦',tone='') => `<div class="kpi"><div class="kpi-top"><span class="kpi-label">${label}</span><span class="kpi-icon ${tone}">${icon}</span></div><div class="kpi-value">${val}</div><div class="kpi-foot">${foot}</div></div>`;
const input = (name,label,type='text',value='',extra='') => `<div class="field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}></div>`;
const choice = (name,label,values,selected) => `<div class="field"><label for="${name}">${label}</label><select id="${name}" name="${name}">${values.map(([v,t])=>`<option value="${esc(v)}" ${v===selected?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`;

async function api(path,method='GET',payload){
  const options={method,headers:{}};
  if(payload!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(payload);}
  const response=await fetch('/api'+path,options);
  let data;try{data=await response.json();}catch{throw Error('Resposta inválida do sistema.');}
  if(!response.ok)throw Error(data.error||'Não foi possível concluir a operação.');
  return data;
}
function toast(message,error=false){
  const root=$('#toastRoot'),el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;
  root.append(el);setTimeout(()=>el.remove(),5200);
}
function failure(e){console.error(e);toast(e.message||'Ocorreu um erro.',true);}
async function load(){
  try{
    const endpoints={dashboard:'/dashboard',products:'/products',cash:'/cash',customers:'/customers',sales:'/sales',shopping:'/shopping',credit:'/credit',reports:'/reports?period='+encodeURIComponent(state.reportPeriod)+'&date='+encodeURIComponent(state.reportDate)};
    const data=await Promise.all(Object.entries(endpoints).map(async ([key,path])=>[key,await api(path)]));
    Object.assign(state.data,Object.fromEntries(data));
    render();
  }catch(e){failure(e);$('#main').innerHTML=empty('Não foi possível carregar o sistema',e.message);}
}
function render(){
  const view={dashboard:dashboard,products:products,shopping:shopping,credit:credit,cash:cash,sales:sales,reports:reports}[state.tab]||dashboard;
  $$('#navigation [data-tab]').forEach(el=>el.classList.toggle('active',el.dataset.tab===state.tab));
  $('#breadcrumbs').textContent='Painel / '+names[state.tab];
  $('#todayLabel').textContent=new Date().toLocaleDateString('pt-BR',{weekday:'short',day:'2-digit',month:'short',year:'numeric'});
  const c=state.data.cash||{};
  $('#cashPill').textContent=c.status==='OPEN'?'● Caixa aberto':'○ Caixa fechado';
  $('#cashPill').classList.toggle('open',c.status==='OPEN');
  $('#main').innerHTML=view();
}
async function go(tab){state.tab=tab;render();window.scrollTo({top:0,behavior:'smooth'});}

function dashboard(){
  const d=state.data.dashboard||{},low=d.low_products||[];
  return `${head('Bem-vindo ao SIGEC','Controle do mercadinho em um só lugar. Simples, prático e sempre disponível.',`<button class="btn btn-primary" data-tab="sales">＋ Nova venda</button>`)}
  <div class="grid-kpis">
    ${kpi('Vendas de hoje',brl(d.revenue_today_cents),'Total de '+(d.sales_today||0)+' vendas válidas','▥')}
    ${kpi('Dinheiro esperado',d.cash_open?brl(d.cash_expected_cents):'—',d.cash_open?'Caixa aberto neste momento':'Abra o caixa para iniciar','◈','orange')}
    ${kpi('Caderneta pendente',brl(d.credit_pending_cents),'Saldo total a receber','◫')}
    ${kpi('Produtos para reposição',String(d.low_stock_count||0),'Itens abaixo do estoque mínimo','▤','red')}
  </div>
  <div class="section-grid">
    <section class="panel"><div class="panel-header"><div><h2>Estoque que precisa de atenção</h2><p>Produtos com reposição sugerida</p></div><button class="btn-link" data-tab="shopping">Ver lista de compras →</button></div>
      ${low.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Produto</th><th>Estoque</th><th>Mínimo</th><th>Situação</th></tr></thead><tbody>${low.map(p=>`<tr><td class="strong">${esc(p.name)}</td><td>${esc(p.stock_label)} ${p.unit}</td><td>${esc(p.minimum_label)} ${p.unit}</td><td>${productPill(p.stock_status)}</td></tr>`).join('')}</tbody></table></div>`:empty('Tudo em dia!','Nenhum produto abaixo do estoque mínimo.')}
    </section>
    <section class="panel"><div class="panel-header"><div><h2>Acesso rápido</h2><p>Seu trabalho, em menos cliques.</p></div></div>
      <div class="quicklinks"><button class="quicklink" data-tab="sales"><b>▣</b> Registrar venda</button><button class="quicklink" data-tab="products"><b>▤</b> Cadastrar produto</button><button class="quicklink" data-tab="cash"><b>◈</b> Consultar caixa</button><button class="quicklink" data-tab="credit"><b>◫</b> Ver caderneta</button></div>
      <div class="panel-body"><div class="notification note-green">✓ <strong>Funcionamento local.</strong> Todas as operações são armazenadas no SQLite, sem conexão obrigatória com a internet.</div></div>
    </section>
  </div>`;
}

function products(){
  const rows=state.data.products||[],cats=[...new Set(rows.map(p=>p.category).filter(Boolean))].sort();
  return `${head('Produtos e estoque','Cadastre, acompanhe e atualize as mercadorias do seu negócio.',
  `<button class="btn btn-outline" data-tab="shopping">☷ Lista de compras</button><button class="btn btn-primary" data-action="new-product">＋ Novo produto</button>`)}
  <section class="panel"><div class="toolbar"><input class="search" placeholder="⌕ Buscar por nome ou código..." id="productSearch" aria-label="Buscar produto">
  <div class="actions"><select id="categoryFilter" class="search" aria-label="Categoria"><option value="">Todas as categorias</option>${cats.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('')}</select>
  <select id="stockFilter" class="search" aria-label="Situação"><option value="">Todo o estoque</option><option value="LOW">Estoque baixo</option><option value="EMPTY">Em falta</option><option value="OK">Disponível</option><option value="INACTIVE">Inativos</option></select></div></div>
  ${rows.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Produto</th><th>Categoria</th><th>Estoque</th><th>Preço de venda</th><th>Situação</th><th>Ações</th></tr></thead><tbody id="productRows">${rows.map(p=>`<tr data-name="${esc([p.name,p.brand,p.barcode||''].join(' ').toLocaleLowerCase())}" data-category="${esc(p.category)}" data-status="${p.stock_status}"><td><div class="strong">${esc(p.name)}</div><div class="subtle">${esc(p.presentation||p.brand||'Código: '+(p.barcode||'—'))}</div></td><td>${esc(p.category||'—')}</td><td>${esc(p.stock_label)} ${p.unit}</td><td class="strong">${brl(p.price_cents)}${p.unit==='KG'?'/kg':''}</td><td>${productPill(p.stock_status)}</td><td><div class="actions"><button class="btn btn-outline btn-sm" data-action="edit-product" data-id="${p.id}">Editar</button><button class="btn btn-ghost btn-sm" data-action="stock-entry" data-id="${p.id}">Entrada</button><button class="btn btn-danger btn-sm" data-action="delete-product" data-id="${p.id}">${p.active?'Excluir / inativar':'Excluir'}</button></div></td></tr>`).join('')}</tbody></table></div>`:empty('Nenhum produto cadastrado','Cadastre seu primeiro produto para começar.')}
  </section>`;
}
function productModal(p=null){
  const edit=!!p;
  openModal(edit?'Editar produto':'Novo produto',`<form id="productForm" data-id="${p?.id||''}" class="form-stack">
    ${input('name','Nome do produto *','text',p?.name||'','required maxlength="160"')}
    <div class="field-row">${input('brand','Marca','text',p?.brand||'')}${input('presentation','Apresentação / tamanho','text',p?.presentation||'')}</div>
    <div class="field-row">${input('category','Categoria','text',p?.category||'')}${input('barcode','Código de barras (opcional)','text',p?.barcode||'')}</div>
    <div class="field-row">${choice('unit','Unidade de venda *',[['UN','Unidade (UN)'],['KG','Quilograma (KG)']],p?.unit||'UN')}${input('price','Preço de venda (R$) *','text',p?cleanMoney(p.price_cents):'0.00','required inputmode="decimal"')}</div>
    <div class="field-row">${input('purchase_price','Preço de compra (R$)','text',p?cleanMoney(p.purchase_price_cents):'0.00','inputmode="decimal"')}${input('minimum','Estoque mínimo','text',p?p.minimum_label:'0','inputmode="decimal"')}</div>
    <div class="field-row">${edit?`<div class="field"><label>Estoque atual (consulta)</label><input readonly value="${esc(p.stock_label)} ${p.unit}"><small class="caption">Use Registrar entrada para aumentar o estoque.</small></div>`:input('stock','Estoque inicial','text','0','inputmode="decimal"')}
    <div class="field"><label>Situação</label><div class="checkbox-row" style="margin-top:10px"><input type="checkbox" id="active" name="active" ${p?.active!==false?'checked':''}><label for="active">Produto ativo para vendas</label></div></div></div>
  </form>`, `<button class="btn btn-ghost" data-action="close-modal">Voltar</button><button class="btn btn-primary" type="submit" form="productForm">Salvar produto</button>`);
}
function stockModal(p){
  openModal('Registrar entrada de mercadoria',`<form id="entryForm" data-id="${p.id}" class="form-stack">
    <div class="notification note-green">${esc(p.name)} • Saldo atual: <strong>${esc(p.stock_label)} ${p.unit}</strong></div>
    ${input('quantity',`Quantidade recebida (${p.unit}) *`,'text','','required inputmode="decimal"')}
    <div class="field"><label for="note">Observação ou referência</label><textarea name="note" id="note" placeholder="Ex.: Reposição semanal"></textarea></div>
  </form>`,`<button class="btn btn-ghost" data-action="close-modal">Cancelar</button><button class="btn btn-primary" type="submit" form="entryForm">Confirmar entrada</button>`);
}

function shopping(){
  const rows=state.data.shopping||[],productList=(state.data.products||[]).filter(p=>p.active);
  const estimate=rows.reduce((a,p)=>a+p.estimated_cents,0);
  return `${head('Lista de compras','Sugestões de reposição com base no estoque mínimo. Nenhuma compra é realizada automaticamente.',`<button class="btn btn-outline" data-tab="products">▤ Ver produtos</button>`)}
  <div class="grid-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:20px">${kpi('Itens na lista',rows.length,'Estoque baixo e adições manuais','☷')}${kpi('Custo estimado',brl(estimate),'Referência a partir do preço de compra','◈','orange')}</div>
  <div class="section-grid" style="grid-template-columns:minmax(0,2fr) minmax(240px,1fr);align-items:start">
    <section class="panel"><div class="panel-header"><div><h2>Produtos a repor</h2><p>Altere quantidades e marque os itens já conferidos</p></div></div>
    ${rows.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Produto</th><th>Tenho</th><th>Mínimo</th><th>Comprar</th><th>Conferido</th><th>Ação</th></tr></thead><tbody>${rows.map(p=>`<tr><td><div class="strong">${esc(p.name)}</div><div class="subtle">${brl(p.purchase_price_cents)}/${p.unit}</div></td><td>${esc(p.stock_label)} ${p.unit}</td><td>${esc(p.minimum_label)} ${p.unit}</td><td><form id="shop-${p.id}" data-id="${p.id}" class="shoppingForm"><input name="quantity" class="search pill-input" style="width:110px" value="${esc(p.buy_label)}" aria-label="Quantidade a comprar de ${esc(p.name)}"><input type="hidden" name="manual" value="true"></form></td><td><input type="checkbox" form="shop-${p.id}" name="checked" ${p.checked?'checked':''} aria-label="Conferido"></td><td><button type="submit" form="shop-${p.id}" class="btn btn-outline btn-sm">Salvar</button></td></tr>`).join('')}</tbody></table></div>`:empty('Lista vazia','Nenhum produto está abaixo do mínimo nem foi adicionado manualmente.')}
    </section><section class="panel"><div class="panel-header"><h2>Adicionar à lista</h2></div><div class="panel-body"><form id="shopAddForm" class="form-stack">
       ${choice('shop_product','Produto',productList.map(p=>[String(p.id),p.name]),String(productList[0]?.id||''))}
       ${input('quantity','Quantidade que deseja comprar','text','1','required')}
       <button class="btn btn-primary" type="submit" ${productList.length?'':'disabled'}>＋ Adicionar produto</button>
       <p class="caption">Use números inteiros para UN e até três casas decimais para KG.</p>
    </form></div></section>
  </div>`;
}

function cartTotals(){
  let subtotal=0;
  for(const item of state.cart){const p=(state.data.products||[]).find(x=>x.id===item.product_id);if(!p)continue;const q=num(item.quantity);subtotal+=Math.round(p.price_cents*q);}
  const pct=num(state.discountPct),fixed=Math.round(num(state.discountFixed)*100);
  const percentage=Math.round(subtotal*pct/100),total=subtotal-percentage-fixed;
  const allocated=state.payments.reduce((sum,p)=>sum+Math.round(num(p.applied)*100),0);
  const change=state.payments.filter(p=>p.method==='CASH').reduce((sum,p)=>sum+Math.round((num(p.tendered)-num(p.applied))*100),0);
  return {subtotal,pct,percentage,fixed,total,allocated,remaining:total-allocated,change};
}
function saleBlockers(t){
  const reasons=[];
  const pctText=String(state.discountPct??'0').trim();
  const fixedText=String(state.discountFixed??'0').trim();
  // Decimais nos campos devem seguir a mesma precisão do cálculo no servidor.
  const validDecimal=v=>/^-?\d+(?:[.,]\d{1,2})?$/.test(v);
  if(!validDecimal(pctText))reasons.push('O desconto percentual deve ser um número com até duas casas decimais.');
  if(!validDecimal(fixedText))reasons.push('O desconto em reais deve ser um número com até duas casas decimais.');
  if(!state.cart.length)reasons.push('Adicione pelo menos um produto ao carrinho.');
  if(state.data.cash?.status!=='OPEN')reasons.push('Abra o caixa na seção Caixa para registrar vendas.');
  if(!Number.isFinite(t.pct)||t.pct<0||t.pct>100)reasons.push('Informe um desconto percentual entre 0% e 100%.');
  if(!Number.isFinite(t.fixed)||t.fixed<0)reasons.push('O desconto em reais precisa ser zero ou positivo.');
  if(t.total<0)reasons.push('Os descontos ultrapassam o subtotal. Reduza um dos descontos.');
  if(t.total===0)reasons.push('Venda de R$ 0,00 não permitida. Reduza os descontos ou revise os produtos para que o total seja maior que zero.');
  if(t.total>=0 && t.remaining>0)reasons.push('Faltam '+brl(t.remaining)+' em pagamentos. Adicione o valor restante na seção Pagamento dividido.');
  if(t.total>=0 && t.remaining<0)reasons.push('Há '+brl(-t.remaining)+' em pagamentos a mais. Remova ou ajuste os pagamentos aplicados.');
  if(state.sending)reasons.push('A confirmação está sendo processada.');
  return reasons;
}
function blockersMarkup(t){
  const reasons=saleBlockers(t);
  const last=state.payments[state.payments.length-1];
  const lastApplied=last?Math.round(num(last.applied)*100):0;
  const quickFix=t.remaining>0?`<button class="btn btn-outline btn-sm" type="button" data-action="focus-payment">Adicionar ${brl(t.remaining)} em pagamento</button>`:
    t.remaining<0 && lastApplied>-t.remaining?`<button class="btn btn-outline btn-sm" type="button" data-action="adjust-last-payment">Ajustar último pagamento para fechar o total</button>`:'';
  return reasons.length?`<div class="sale-blockers" role="status" aria-live="polite"><strong>⛔ O que falta para concluir?</strong><ul>${reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>${quickFix?`<div class="blocker-actions">${quickFix}</div>`:''}</div>`:
    '<div class="sale-ready" role="status" aria-live="polite">✓ Pronto: os pagamentos correspondem ao total. Você pode concluir a venda.</div>';
}
function sales(){
  const p=(state.data.products||[]).filter(x=>x.active&&x.stock_base>0),customers=state.data.customers||[],tot=cartTotals(),recent=state.data.sales||[];
  return `${head('Vendas / PDV','Registre vendas por unidade ou peso, com descontos e pagamento dividido.',`<button class="btn btn-outline" data-action="new-customer">＋ Novo cliente</button>`)}
  ${state.data.cash?.status!=='OPEN'?`<div class="notification notice-row" style="margin-bottom:20px"><strong>◈</strong><span>O caixa está fechado. <button class="btn-link" data-tab="cash">Abra o caixa</button> antes de concluir uma venda.</span></div>`:''}
  <div class="split">
   <div>
    <section class="panel"><div class="panel-header"><div><h2>Itens da venda</h2><p>Adicione os produtos ao carrinho</p></div><span class="tag gray">${state.cart.length} item(ns)</span></div><div class="panel-body">
      <form id="cartForm" class="form-stack"><div class="field-row">
        ${choice('product_id','Produto',p.map(x=>[String(x.id),x.name+' — '+brl(x.price_cents)+'/'+x.unit+' (saldo '+x.stock_label+')']),String(p[0]?.id||''))}
        ${input('quantity','Quantidade (UN ou KG)','text','1','required inputmode="decimal"')}
      </div><button type="submit" class="btn btn-dark" ${p.length?'':'disabled'}>＋ Adicionar ao carrinho</button></form>
      <div class="divider"></div>
      ${state.cart.length?state.cart.map((it,i)=>{const product=(state.data.products||[]).find(x=>x.id===it.product_id);return `<div class="sale-item"><div><strong>${esc(product?.name||'Produto indisponível')}</strong><small>${esc(it.quantity)} ${product?.unit||''} × ${brl(product?.price_cents)}${product?.unit==='KG'?'/kg':''}</small></div><div class="sale-actions"><strong>${brl(Math.round((product?.price_cents||0)*num(it.quantity)))}</strong><button class="btn btn-danger btn-sm" data-action="remove-cart" data-index="${i}">✕</button></div></div>`;}).join(''):empty('Carrinho vazio','Escolha um produto e a quantidade para começar.')}
      ${state.cart.length?'<div class="row-end section-spacer"><button class="btn btn-ghost btn-sm" data-action="clear-cart">Limpar carrinho</button></div>':''}
    </div></section>
    <section class="panel section-spacer"><div class="panel-header"><div><h2>Pagamento dividido</h2><p>Dinheiro, Pix, cartão ou caderneta</p></div></div><div class="panel-body">
      <form id="paymentForm" class="form-stack"><div class="field-row three">
       ${choice('method','Forma de pagamento',Object.entries(methods).map(([k,v])=>[k,v]),'CASH')}
       ${input('applied','Valor aplicado (R$)','text',cleanMoney(Math.max(0,tot.remaining)),'required inputmode="decimal"')}
       ${input('tendered','Dinheiro entregue (R$)','text','','inputmode="decimal" placeholder="Só para dinheiro"')}
      </div>${choice('customer_id','Cliente para o fiado (se necessário)',[['','Selecione um cliente'],...customers.map(x=>[String(x.id),x.name])],'')}
      <div class="actions"><button class="btn btn-outline" type="submit">＋ Adicionar pagamento</button><button class="btn-link" type="button" data-action="new-customer">Cadastrar cliente</button></div>
      </form><div class="divider"></div>
      ${state.payments.length?state.payments.map((pay,i)=>`<div class="payment-item"><div><strong>${methods[pay.method]}</strong>${pay.method==='CASH'?`<div class="subtle">Entregue ${brl(Math.round(num(pay.tendered)*100))} • Troco ${brl(Math.round((num(pay.tendered)-num(pay.applied))*100))}</div>`:''}${pay.method==='CREDIT'?`<div class="subtle">${esc(customers.find(c=>c.id===pay.customer_id)?.name||'Cliente')}</div>`:''}</div><div class="sale-actions"><strong>${brl(Math.round(num(pay.applied)*100))}</strong><button class="btn btn-danger btn-sm" data-action="remove-payment" data-index="${i}">✕</button></div></div>`).join(''):empty('Nenhum pagamento adicionado','Adicione uma ou mais formas de pagamento.')}
      <div class="notification" style="margin-top:14px">O total dos valores <strong>aplicados à venda</strong> deve ser igual ao total a pagar. O troco é calculado apenas a partir do dinheiro entregue.</div>
    </div></section>
   </div>
   <div>
    <section class="panel sales-summary"><div class="panel-header"><div><h2>Resumo da venda</h2><p>Valores calculados antes da confirmação</p></div></div><div class="panel-body">
      <div class="form-stack"><div class="field-row">${input('discountPercent','Desconto (%)','text',state.discountPct,'inputmode="decimal"')}${input('discountFixed','Desconto (R$)','text',state.discountFixed,'inputmode="decimal"')}</div>
       <button class="btn btn-ghost btn-sm" data-action="remove-discounts">Remover os dois descontos</button></div>
      <div class="totals" id="saleTotals">${totalsMarkup(tot)}</div>
      ${tot.total<0||tot.pct>100||tot.pct<0||tot.fixed<0?`<p class="caption text-orange">Os descontos são inválidos. Corrija antes de concluir.</p>`:''}
      <div id="saleBlockers">${blockersMarkup(tot)}</div>
      <button class="btn btn-primary" style="width:100%;margin-top:14px" data-action="conclude-sale" ${saleBlockers(tot).length?'disabled':''}>✓ Concluir venda</button>
      <p class="caption" style="text-align:center;margin-top:10px">Tudo é validado novamente no servidor.</p>
    </div></section>
   </div>
  </div>
  <section class="panel section-spacer"><div class="panel-header"><div><h2>Histórico de vendas</h2><p>Consulte detalhes e cancele com motivo obrigatório</p></div></div>
    ${recent.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Nº</th><th>Data</th><th>Total</th><th>Situação</th><th></th></tr></thead><tbody>${recent.slice(0,30).map(v=>`<tr><td class="strong">#${v.id}</td><td>${fmtDate(v.created_at)}</td><td class="strong">${brl(v.total_cents)}</td><td>${salePill(v.status)}</td><td><button class="btn btn-outline btn-sm" data-action="view-sale" data-id="${v.id}">Detalhes</button></td></tr>`).join('')}</tbody></table></div>`:empty('Nenhuma venda registrada')}</section>`;
}
function totalsMarkup(t){return `<div class="total-line"><span>Subtotal</span><strong>${brl(t.subtotal)}</strong></div>
   <div class="total-line"><span>Desconto percentual (${t.pct}%)</span><strong>− ${brl(t.percentage)}</strong></div>
   <div class="total-line"><span>Desconto fixo</span><strong>− ${brl(t.fixed)}</strong></div>
   <div class="total-line big"><span>TOTAL</span><strong>${brl(t.total)}</strong></div>
   <div class="divider" style="margin:14px 0"></div><div class="total-line"><span>Pagamentos aplicados</span><strong>${brl(t.allocated)}</strong></div>
   <div class="total-line"><span>Restante</span><strong>${brl(t.remaining)}</strong></div><div class="total-line"><span>Troco em espécie</span><strong>${brl(t.change)}</strong></div>`;}

function credit(){
 const debts=state.data.credit||[],open=debts.filter(x=>x.status==='OPEN'),remaining=open.reduce((sum,x)=>sum+x.outstanding_cents,0);
 return `${head('Caderneta','Acompanhe dívidas e registre recebimentos parciais ou totais.',`<button class="btn btn-primary" data-action="new-customer">＋ Novo cliente</button>`)}
 <div class="grid-kpis credit-summary" style="grid-template-columns:repeat(2,minmax(0,1fr))">${kpi('Saldo pendente',brl(remaining),'Valores ainda não recebidos','◫','orange')}${kpi('Débitos em aberto',open.length,'Registros com saldo pendente','▤')}</div>
 <section class="panel"><div class="panel-header"><div><h2>Débitos registrados</h2><p>Recebimentos não geram novas vendas nem faturamento</p></div></div>
 ${debts.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Cliente</th><th>Venda</th><th>Valor original</th><th>Saldo pendente</th><th>Situação</th><th></th></tr></thead><tbody>${debts.map(d=>`<tr><td><div class="strong">${esc(d.customer_name)}</div><div class="subtle">${esc(d.phone||'Sem contato')}</div></td><td>#${d.sale_id}</td><td>${brl(d.original_cents)}</td><td class="strong">${brl(d.outstanding_cents)}</td><td>${pill(d.status,{OPEN:['warn','Em aberto'],PAID:['ok','Quitado'],CANCELED:['gray','Cancelado']})}</td><td>${d.status==='OPEN'?`<button class="btn btn-primary btn-sm" data-action="receive-credit" data-id="${d.id}">Receber</button>`:'—'}</td></tr>`).join('')}</tbody></table></div>`:empty('Nenhum débito cadastrado','As vendas com pagamento fiado aparecem aqui.')}</section>`;
}
function customerModal(){openModal('Cadastrar cliente',`<form id="customerForm" class="form-stack">${input('name','Nome do cliente *','text','','required')}${input('phone','Telefone / contato (opcional)','text','','placeholder="(75) 90000-0000"')}</form>`,`<button class="btn btn-ghost" data-action="close-modal">Cancelar</button><button class="btn btn-primary" type="submit" form="customerForm">Salvar cliente</button>`);}
function receiveModal(d){openModal('Receber pagamento da caderneta',`<form id="receiveForm" data-id="${d.id}" class="form-stack"><div class="notification note-green"><strong>${esc(d.customer_name)}</strong><br>Venda #${d.sale_id} • Saldo pendente: <strong>${brl(d.outstanding_cents)}</strong></div>${input('amount','Valor recebido (R$) *','text',cleanMoney(d.outstanding_cents),'required inputmode="decimal"')}${choice('method','Forma de recebimento',[['CASH','Dinheiro'],['PIX','Pix'],['CARD','Cartão']],'CASH')}</form>`,`<button class="btn btn-ghost" data-action="close-modal">Voltar</button><button class="btn btn-primary" type="submit" form="receiveForm">Registrar recebimento</button>`);}

function cash(){
 const c=state.data.cash||{},history=state.data.cashHistory||[],open=c.status==='OPEN';
 return `${head('Gestão de caixa','Abra, acompanhe movimentações, registre sangrias e faça o fechamento do dia.',open?cashPill('OPEN'):cashPill('CLOSED'))}
 <div class="split"><div>
 ${open?`<div class="balance-hero"><small>Saldo esperado em espécie</small><strong>${brl(c.expected_cents)}</strong><p>Sessão #${c.id} • Aberta em ${fmtDate(c.opened_at)}</p></div>
  <section class="panel"><div class="panel-header"><div><h2>Movimentações da sessão</h2><p>Abertura, vendas, caderneta, sangrias e devoluções</p></div></div>
  ${(c.movements||[]).length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Data</th><th>Movimento</th><th>Observação</th><th class="right">Valor</th></tr></thead><tbody>${c.movements.map(m=>`<tr><td>${fmtDate(m.created_at)}</td><td class="strong">${esc(({OPENING:'Abertura',SALE_CASH:'Venda em dinheiro',RECEIPT_CASH:'Recebimento fiado',WITHDRAW:'Sangria',REFUND_CASH:'Devolução'})[m.kind]||m.kind)}</td><td class="muted">${esc(m.note||'—')}</td><td class="right cash-move ${m.amount_cents<0?'negative':''}">${m.amount_cents>=0?'+':'−'} ${brl(Math.abs(m.amount_cents))}</td></tr>`).join('')}</tbody></table></div>`:empty('Sem movimentações')}</section>`:
  `<section class="panel"><div class="panel-header"><h2>Abrir caixa</h2></div><div class="panel-body"><div class="notification" style="margin-bottom:20px">Para fazer vendas, sangrias ou receber a caderneta, abra uma sessão de caixa.</div><form id="cashOpenForm" class="form-stack">${input('opening','Fundo de troco inicial (R$) *','text','0.00','required inputmode="decimal"')}${input('note','Observação (opcional)','text','')}
   <button class="btn btn-primary" type="submit">◈ Confirmar abertura de caixa</button></form></div></section>`}
 </div><div>${open?`<section class="panel"><div class="panel-header"><h2>Retirada / sangria</h2></div><div class="panel-body"><form id="withdrawForm" class="form-stack">${input('amount','Valor da retirada (R$) *','text','','required inputmode="decimal"')}${input('reason','Justificativa *','text','','required')}<button type="submit" class="btn btn-outline">Registrar sangria</button></form></div></section>
 <section class="panel section-spacer"><div class="panel-header"><h2>Fechamento de caixa</h2></div><div class="panel-body"><div class="notification note-green">Dinheiro esperado: <strong>${brl(c.expected_cents)}</strong>. Pix, cartão e fiado não entram no dinheiro da gaveta.</div><form id="closeCashForm" class="form-stack" style="margin-top:17px">${input('counted','Dinheiro contado na gaveta (R$) *','text',cleanMoney(c.expected_cents),'required inputmode="decimal"')}<div class="field"><label for="note">Justificativa (obrigatória se houver diferença)</label><textarea id="note" name="note" placeholder="Ex.: diferença identificada na conferência"></textarea></div><button type="submit" class="btn btn-dark">✓ Fechar caixa</button></form></div></section>`:
 `<section class="panel"><div class="panel-header"><h2>Último fechamento</h2></div><div class="panel-body">${c.last_session?`<p class="caption">Sessão #${c.last_session.id} • ${fmtDate(c.last_session.closed_at||c.last_session.opened_at)}</p><div class="totals"><div class="total-line"><span>Dinheiro esperado</span><strong>${brl(c.last_session.expected_cents)}</strong></div><div class="total-line"><span>Dinheiro contado</span><strong>${brl(c.last_session.counted_cents)}</strong></div><div class="total-line"><span>Diferença</span><strong>${brl(c.last_session.difference_cents)}</strong></div></div>`:empty('Nenhuma sessão anterior','Abra seu primeiro caixa para começar.')}</div></section>`}
 <section class="panel section-spacer"><div class="panel-header"><h2>Histórico de sessões</h2></div>${history.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Sessão</th><th>Status</th><th>Diferença</th></tr></thead><tbody>${history.slice(0,8).map(h=>`<tr><td>#${h.id}<div class="subtle">${fmtDate(h.opened_at)}</div></td><td>${cashPill(h.status)}</td><td>${h.difference_cents===null?'—':brl(h.difference_cents)}</td></tr>`).join('')}</tbody></table></div>`:empty('Sem histórico')}</section>
 </div></div>`;
}

function reports(){
 const r=state.data.reports||{},rows=r.ranking||[],units=rows.filter(x=>x.unit==='UN'),kgs=rows.filter(x=>x.unit==='KG');
 const table=arr=>arr.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Produto</th><th>Quantidade</th><th>Valor bruto</th></tr></thead><tbody>${arr.map(x=>`<tr><td class="strong">${esc(x.name)}</td><td>${esc(x.quantity_label)} ${x.unit}</td><td>${brl(x.gross_cents)}</td></tr>`).join('')}</tbody></table></div>`:empty('Sem movimentação no período');
 return `${head('Relatórios','Consulte resultados diários e mensais sem misturar vendas com recebimentos de fiado.')}
 <section class="panel" style="margin-bottom:19px"><div class="toolbar"><form id="reportForm" class="actions" style="align-items:flex-end">
 ${choice('period','Período',[['day','Diário'],['month','Mensal']],state.reportPeriod)}${input('date','Data de referência','date',state.reportDate,'required')}<button type="submit" class="btn btn-dark">Aplicar filtro</button></form></div></section>
 <div class="grid-kpis">${kpi('Faturamento de vendas',brl(r.revenue_cents),'Somente vendas válidas','▥')}${kpi('Vendas concluídas',r.sales_count||0,'Canceladas fora do faturamento','▣')}${kpi('Descontos concedidos',brl(r.discounts_cents),'Percentual e valor fixo','◈','orange')}${kpi('Recebimentos da caderneta',brl(r.credit_receipts_cents),'Valor recebido, não é nova venda','◫')}</div>
 <section class="panel section-spacer"><div class="panel-header"><div><h2>Recebimentos por forma de pagamento</h2><p>Dinheiro, Pix e cartão separados; fiado pendente não é dinheiro recebido</p></div></div>
 <div class="panel-body"><div class="grid-kpis report-payment-grid">
  ${kpi('Dinheiro recebido',brl(r.received_by_method_cents?.CASH),'Vendas + caderneta − devoluções','◈')}
  ${kpi('Pix recebido',brl(r.received_by_method_cents?.PIX),'Vendas + caderneta − devoluções','▣')}
  ${kpi('Cartão recebido',brl(r.received_by_method_cents?.CARD),'Vendas + caderneta − devoluções','▥')}
  ${kpi('Total recebido',brl(r.received_total_cents),'Somente dinheiro, Pix e cartão','◫','orange')}
 </div><div class="table-wrap" style="margin-top:16px"><table class="data-table"><thead><tr><th>Forma</th><th>Pagamentos de vendas</th><th>Caderneta recebida</th><th>Devoluções</th><th>Recebido líquido</th></tr></thead><tbody>
 ${['CASH','PIX','CARD'].map(m=>`<tr><td class="strong">${methods[m]}</td><td>${brl(r.sale_payments_by_method_cents?.[m])}</td><td>${brl(r.credit_receipts_by_method_cents?.[m])}</td><td>${brl(r.refunds_by_method_cents?.[m])}</td><td class="strong">${brl(r.received_by_method_cents?.[m])}</td></tr>`).join('')}
 </tbody></table></div><p class="caption">Fluxo de caixa por data: inclui pagamentos de vendas que venham a ser canceladas, e registra a devolução na data efetiva do estorno. O faturamento acima considera apenas vendas válidas. Fiado pendente não conta como recebido.</p></div></section>
 <section class="panel section-spacer"><div class="panel-header"><div><h2>Resultado das vendas (lucro bruto)</h2><p>Separado do dinheiro recebido por forma de pagamento</p></div></div><div class="panel-body"><div class="statbar"><div><small>Faturamento de vendas válidas</small><strong>${brl(r.revenue_cents)}</strong></div><div><small>Custo dos produtos vendidos</small><strong>${r.profit_available?brl(r.cost_cents):'Indisponível'}</strong></div><div><small>Lucro bruto estimado</small><strong>${r.profit_available?brl(r.gross_profit_cents):'Indisponível'}</strong></div></div><p class="caption">Lucro bruto = faturamento após descontos − custo dos produtos vendido no momento de cada venda. Não inclui despesas operacionais, impostos ou taxas de cartão. ${r.profit_available?'Custos de todos os itens válidos deste período foram registrados.':'Não é possível calcular lucro confiável: '+(r.cost_missing_items||0)+' item(ns) de venda sem custo histórico registrado. Preencha o preço de compra nos novos cadastros; vendas antigas não são recalculadas com o custo atual.'}</p></div></section>
 <div class="section-grid"><section class="panel"><div class="panel-header"><h2>Ranking — produtos por unidade</h2></div>${table(units)}</section><section class="panel"><div class="panel-header"><h2>Ranking — produtos por peso (KG)</h2></div>${table(kgs)}</section></div>
 <div class="panel section-spacer"><div class="panel-header"><h2>Conciliação do período</h2></div><div class="panel-body"><div class="statbar"><div><small>Subtotal antes de descontos</small><strong>${brl(r.subtotal_cents)}</strong></div><div><small>Devoluções registradas</small><strong>${brl(r.refunds_cents)}</strong></div><div><small>Cancelamentos efetuados</small><strong>${r.cancellations_count||0}</strong></div></div><p class="caption">Cancelamentos excluem a venda original do faturamento, independentemente da data do cancelamento. Recebimentos de caderneta e devoluções aparecem separadamente.</p></div></div>`;
}

function openModal(title,body,foot=''){ $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-action="modal-backdrop"><div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-head"><h2>${esc(title)}</h2><button class="close-x" data-action="close-modal" aria-label="Fechar">×</button></div><div class="modal-body">${body}</div>${foot?`<div class="modal-foot">${foot}</div>`:''}</div></div>`;}
function closeModal(){ $('#modalRoot').innerHTML=''; }

async function saleModal(id){
 const [sale,preview]=await Promise.all([api('/sales/'+id),api('/sales/'+id+'/cancel-preview').catch(e=>({refunds:[],error:e.message}))]);
 const itemHTML=sale.items.map(i=>`<div class="mini-list-item"><div><strong>${esc(i.name_snapshot)}</strong><br><span>${i.unit==='KG'?`${Math.trunc(i.quantity_base/1000)},${String(i.quantity_base%1000).padStart(3,'0')}`:i.quantity_base} ${i.unit} × ${brl(i.price_cents)}</span></div><strong>${brl(i.line_total_cents)}</strong></div>`).join('');
 const pays=sale.payments.map(p=>`${methods[p.method]}: ${brl(p.applied_cents)}`).join(' • ')||'Sem pagamento';
 const refunds=(preview.refunds||[]).map(p=>`<div class="mini-list-item"><strong>${methods[p.method]}</strong><strong>${brl(p.amount_cents)}</strong></div>`).join('');
 openModal('Venda #'+id,`<div class="form-stack"><div class="actions">${salePill(sale.status)}<span class="caption">${fmtDate(sale.created_at)}</span></div>
    <div class="line-box">${itemHTML}<div class="divider"></div><div class="total-line"><span>Subtotal</span><strong>${brl(sale.subtotal_cents)}</strong></div><div class="total-line"><span>Descontos</span><strong>− ${brl(sale.discount_percent_cents+sale.discount_fixed_cents)}</strong></div><div class="total-line big"><span>Total</span><strong>${brl(sale.total_cents)}</strong></div><p class="caption">Pagamento: ${esc(pays)}</p></div>
    ${sale.status==='COMPLETED'?`<div class="notification"><strong>Cancelar venda</strong><br>O estoque será reposto, a dívida pendente cancelada e os pagamentos recebidos deverão ser devolvidos. Não há integração automática com bancos ou cartões.</div>
    <form id="cancelSaleForm" data-id="${id}" class="form-stack">${input('reason','Motivo obrigatório *','text','','required maxlength="400"')}
      <div class="line-box"><strong>Devoluções necessárias</strong>${refunds||'<p class="caption">Nenhum valor já recebido.</p>'}<p class="caption">Fiado ainda pendente: ${brl(preview.outstanding_credit_cents||0)} (será anulado).</p></div>
      <div class="checkbox-row"><input id="confirm_refunds" type="checkbox" name="confirm_refunds" required><label for="confirm_refunds">Confirmo que efetuei as devoluções financeiras indicadas, quando aplicáveis.</label></div>
      <button class="btn btn-danger" type="submit">Confirmar cancelamento</button></form>`:`<p class="notification">Cancelada em ${fmtDate(sale.canceled_at)}. Motivo: ${esc(sale.cancel_reason)}</p>`}
 </div>`,`<button class="btn btn-ghost" data-action="close-modal">Fechar</button>`);
}

function filterProducts(){
 const query=($('#productSearch')?.value||'').toLocaleLowerCase(),cat=$('#categoryFilter')?.value||'',status=$('#stockFilter')?.value||'';
 $$('#productRows tr').forEach(row=>{row.hidden=!!((query&&!row.dataset.name.includes(query))||(cat&&row.dataset.category!==cat)||(status&&row.dataset.status!==status));});
}
function syncTotals(){
 const t=cartTotals();$('#saleTotals').innerHTML=totalsMarkup(t);
 const feedback=$('#saleBlockers');if(feedback)feedback.innerHTML=blockersMarkup(t);
 const button=$('[data-action="conclude-sale"]');if(button)button.disabled=saleBlockers(t).length>0;
}
async function actionClick(button){
 const a=button.dataset.action,id=Number(button.dataset.id),i=Number(button.dataset.index);
 if(a==='close-modal'){closeModal();return;}
 if(a==='modal-backdrop'){if(button.classList.contains('modal-backdrop'))closeModal();return;}
 if(a==='new-product'){productModal();return;}
 if(a==='edit-product'){productModal(state.data.products.find(p=>p.id===id));return;}
 if(a==='stock-entry'){stockModal(state.data.products.find(p=>p.id===id));return;}
 if(a==='delete-product'){
  const p=state.data.products.find(x=>x.id===id);
  if(!confirm('Confirma a exclusão/inativação de "'+p.name+'"? Se houver movimentações, será inativado para preservar o histórico.'))return;
  const response=await api('/products/'+id,'DELETE');toast(response.message);await load();return;
 }
 if(a==='new-customer'){customerModal();return;}
 if(a==='remove-cart'){state.cart.splice(i,1);state.saleToken=null;render();return;}
 if(a==='focus-payment'){
   const field=$('#applied'); if(field){field.value=cleanMoney(Math.max(0,cartTotals().remaining));field.scrollIntoView({behavior:'smooth',block:'center'});field.focus();field.select();}
   return;
 }
 if(a==='adjust-last-payment'){
   const t=cartTotals(); const last=state.payments[state.payments.length-1];
   if(!last||t.remaining>=0){return;}
   const updated=Math.round(num(last.applied)*100)+t.remaining;
   if(updated<=0){toast('Remova o último pagamento e registre o valor correto.',true);return;}
   last.applied=cleanMoney(updated);state.saleToken=null;render();toast('Último pagamento ajustado para '+brl(updated)+'.');return;
 }
 if(a==='remove-payment'){state.payments.splice(i,1);state.saleToken=null;render();return;}
 if(a==='clear-cart'){if(confirm('Limpar itens e pagamentos desta venda?')){state.cart=[];state.payments=[];state.saleToken=null;render();}return;}
 if(a==='remove-discounts'){state.discountPct='0';state.discountFixed='0';state.saleToken=null;render();return;}
 if(a==='receive-credit'){receiveModal((state.data.credit||[]).find(d=>d.id===id));return;}
 if(a==='view-sale'){await saleModal(id);return;}
 if(a==='conclude-sale'){
    if(state.sending)return;
    const t=cartTotals();
    if(saleBlockers(t).length){toast(saleBlockers(t)[0],true);return;}
    // Proteção extra na confirmação: o servidor também valida essa regra.
    if(t.total<=0){toast('Venda de R$ 0,00 não permitida. Revise os descontos.',true);return;}
    if(!confirm('Concluir venda de '+brl(t.total)+' e dar baixa no estoque?'))return;
    state.sending=true;syncTotals();
    try{
       state.saleToken ??= globalThis.crypto?.randomUUID?.()||String(Date.now())+'-'+Math.random();
       const sale=await api('/sales','POST',{token:state.saleToken,
          items:state.cart,discount_percent:state.discountPct,discount_fixed:state.discountFixed,payments:state.payments});
       state.cart=[];state.payments=[];state.discountPct='0';state.discountFixed='0';state.saleToken=null;
       await load();toast('Venda #'+sale.id+' concluída e estoque atualizado.');
       openModal('Venda registrada',`<div class="notification note-green">✓ Venda <strong>#${sale.id}</strong> confirmada com sucesso!<br>Valor total: <strong>${brl(sale.total_cents)}</strong>. A baixa de estoque e os pagamentos foram registrados em conjunto.</div>`,`<button class="btn btn-primary" data-action="close-modal">Entendi</button>`);
    }finally{state.sending=false;syncTotals();}
    return;
 }
}

async function actionSubmit(form){
 const formId=form.id,v=Object.fromEntries(new FormData(form));
 if(formId==='productForm'){
  v.active=$('#active',form).checked;
  await api('/products'+(form.dataset.id?'/'+form.dataset.id:''),form.dataset.id?'PUT':'POST',v);
  closeModal();toast('Produto salvo.');await load();return;
 }
 if(formId==='entryForm'){await api('/products/'+form.dataset.id+'/entry','POST',v);closeModal();toast('Entrada de estoque registrada.');await load();return;}
 if(formId==='customerForm'){await api('/customers','POST',v);closeModal();toast('Cliente cadastrado.');await load();return;}
 if(formId==='cashOpenForm'){await api('/cash/open','POST',v);toast('Caixa aberto.');await load();return;}
 if(formId==='withdrawForm'){if(!confirm('Confirmar sangria de R$ '+v.amount+'?'))return;await api('/cash/withdraw','POST',v);toast('Sangria registrada.');await load();return;}
 if(formId==='closeCashForm'){if(!confirm('Confirmar o fechamento da sessão de caixa?'))return;const result=await api('/cash/close','POST',v);toast('Caixa fechado. Diferença: '+brl(result.difference_cents));await load();return;}
 if(formId==='receiveForm'){if(!confirm('Confirmar recebimento de R$ '+v.amount+'?'))return;await api('/credit/'+form.dataset.id+'/receive','POST',v);closeModal();toast('Recebimento de caderneta registrado.');await load();return;}
 if(formId==='cartForm'){
   const pid=Number(v.product_id),p=state.data.products.find(x=>x.id===pid),n=num(v.quantity);
   if(!p||!n||n<=0||!Number.isFinite(n)){toast('Selecione um produto e quantidade válida.',true);return;}
   if(p.unit==='UN'&&!Number.isInteger(n)){toast('Produto UN exige quantidade inteira.',true);return;}
   if(p.unit==='KG'&&!Number.isInteger(Math.round(n*10000)/10)){toast('KG aceita até três casas decimais.',true);return;}
   const existing=state.cart.find(x=>x.product_id===pid);
   if(existing){existing.quantity=p.unit==='UN'?String(num(existing.quantity)+n):(num(existing.quantity)+n).toFixed(3);}else state.cart.push({product_id:pid,quantity:p.unit==='UN'?String(n):n.toFixed(3)});
   const q=num(state.cart.find(x=>x.product_id===pid).quantity),base=p.unit==='KG'?q*1000:q;
   if(base>p.stock_base){if(existing){existing.quantity=p.unit==='UN'?String(q-n):(q-n).toFixed(3);}else state.cart=state.cart.filter(x=>x.product_id!==pid);toast('Quantidade supera o estoque disponível.',true);return;}
   state.saleToken=null;render();return;
 }
 if(formId==='paymentForm'){
   const applied=num(v.applied);if(!Number.isFinite(applied)||applied<=0){toast('Informe um pagamento maior que zero.',true);return;}
   if(v.method==='CREDIT'&&!v.customer_id){toast('Selecione o cliente do fiado.',true);return;}
   const p={method:v.method,applied:applied.toFixed(2)};
   if(v.method==='CASH'){
     const tendered=v.tendered.trim()?num(v.tendered):applied;
     if(tendered<applied){toast('Dinheiro entregue menor que o aplicado.',true);return;}
     p.tendered=tendered.toFixed(2);
   }
   if(v.method==='CREDIT')p.customer_id=Number(v.customer_id);
   if(Math.round(applied*100)>cartTotals().remaining){toast('O pagamento supera o valor restante ('+brl(Math.max(0,cartTotals().remaining))+'). Ajuste o valor.',true);return;}
   state.payments.push(p);state.saleToken=null;render();return;
 }
 if(formId==='reportForm'){state.reportPeriod=v.period;state.reportDate=v.date;await load();return;}
 if(formId==='shopAddForm'){
   const p=state.data.products.find(x=>x.id===Number(v.shop_product));if(!p){toast('Produto inválido.',true);return;}
   await api('/shopping/'+p.id,'PUT',{quantity:v.quantity,checked:false,manual:true});toast('Produto adicionado à lista.');await load();return;
 }
 if(form.classList.contains('shoppingForm')){
   await api('/shopping/'+form.dataset.id,'PUT',{quantity:v.quantity,checked:!!form.querySelector('input[name=checked]').checked,manual:true});toast('Lista de compras atualizada.');await load();return;
 }
 if(formId==='cancelSaleForm'){
   if(!confirm('CONFIRMAR CANCELAMENTO: devolver estoque e registrar reversões financeiras?'))return;
   await api('/sales/'+form.dataset.id+'/cancel','POST',{reason:v.reason,confirm_refunds:!!$('#confirm_refunds',form).checked});
   closeModal();toast('Venda cancelada, estoque reposto e reversões registradas.');await load();return;
 }
}

document.addEventListener('click',async e=>{
 const nav=e.target.closest('[data-tab]');if(nav){e.preventDefault();go(nav.dataset.tab);return;}
 const button=e.target.closest('[data-action]');if(!button)return;
 if(button.dataset.action==='modal-backdrop'&&e.target!==button)return;
 e.preventDefault();try{await actionClick(button);}catch(err){failure(err);}
});
document.addEventListener('submit',async e=>{
 const form=e.target;if(!(form instanceof HTMLFormElement))return;
 e.preventDefault();if(form.dataset.busy==='1')return;
 form.dataset.busy='1';const submits=$$('button[type=submit]',form);submits.forEach(el=>el.disabled=true);
 try{await actionSubmit(form);}catch(err){failure(err);}finally{form.dataset.busy='0';submits.forEach(el=>el.disabled=false);}
});
document.addEventListener('input',e=>{
 if(e.target.matches('#productSearch'))filterProducts();
 if(e.target.matches('#discountPercent,#discountFixed')){
  state.discountPct=$('#discountPercent').value;state.discountFixed=$('#discountFixed').value;state.saleToken=null;syncTotals();
 }
});
document.addEventListener('change',e=>{if(e.target.matches('#categoryFilter,#stockFilter'))filterProducts();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
load();
