# SIGEC — Mercadinho da Cíntia

**Versão 1.0** · Projeto Integrador de Extensão (PIE) · Engenharia de Software, UNIFAN.

O SIGEC foi desenvolvido para reunir cadastro de produtos, estoque, vendas e caixa em um só lugar. O sistema funciona no computador do mercadinho, pelo navegador. Os dados ficam armazenados localmente em SQLite e o uso diário não depende de internet.

## O que foi feito

- **Produtos e estoque:** cadastro, consulta, edição, entradas de mercadoria e lista de compras baseada no estoque mínimo. A venda concluída dá baixa no estoque.
- **Vendas e caderneta:** ponto de venda com itens por unidade ou peso, descontos, pagamentos em dinheiro, Pix, cartão e fiado, cálculo do troco e histórico de vendas.
- **Caixa e relatórios:** abertura, retiradas, fechamento e acompanhamento de vendas, recebimentos e devoluções. Os relatórios separam as formas de pagamento e apresentam o lucro bruto quando há custo registrado para todos os itens do período.
- **Regras de venda:** o sistema impede fechar vendas com pagamento insuficiente ou total zerado. No cancelamento, a venda continua no histórico e o estoque é devolvido.
- **Instalação no Windows:** foi criado um instalador que adiciona um atalho na área de trabalho. Ao clicar no ícone **SIGEC**, o sistema inicia e abre no navegador padrão. O instalador já traz as dependências, então não é necessário instalar Python à parte.

## Como usar no Windows

1. No GitHub, abra a aba **Actions** e selecione a execução concluída de **Gerar instalador SIGEC (Windows x64)**.
2. Em **Artifacts**, baixe `SIGEC-instalador-Windows-x64` e extraia o ZIP.
3. Execute `Instalar SIGEC.exe`. Depois da instalação, clique no ícone **SIGEC** na área de trabalho.

O instalador e o atalho foram verificados em ambiente Windows de teste no GitHub Actions. A validação no computador do mercadinho é uma etapa separada. Para testar antes de usar dados reais, cadastre um produto fictício, faça uma venda e reabra o SIGEC para conferir o histórico e o estoque.

O sistema registra pagamentos e devoluções, mas não realiza transações bancárias.

## Código-fonte

O MVP está em [`SIGEC_MVP/`](SIGEC_MVP/), com backend em Python e Flask, banco SQLite e interface em HTML, CSS e JavaScript. O [`SIGEC_Ambiente/`](SIGEC_Ambiente/) preserva o ambiente de testes inicial do projeto. Os executáveis gerados ficam no GitHub Actions, fora do código-fonte.
