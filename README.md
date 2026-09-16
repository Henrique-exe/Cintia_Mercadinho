# Cintia Mercadinho

Sistema de gestão comercial para o **Mercadinho da Cíntia**, desenvolvido como Projeto Integrador de Extensão (PIE) do curso de Engenharia de Software da UNIFAN.

O objetivo é unificar em uma única plataforma web o **cadastro de produtos**, o **controle de estoque**, a **frente de caixa (PDV)** e o **fluxo de caixa** do estabelecimento, eliminando o uso de planilhas e anotações manuais desconectadas.

## Sumário

- [Contexto e problema](#contexto-e-problema)
- [Objetivos](#objetivos)
- [Escopo](#escopo)
- [Requisitos](#requisitos)
- [Arquitetura e stack](#arquitetura-e-stack)
- [Estrutura de módulos](#estrutura-de-módulos)
- [Modelo de dados](#modelo-de-dados)
- [Equipe e papéis](#equipe-e-papéis)
- [Metodologia](#metodologia)
- [Fluxo de trabalho com Git](#fluxo-de-trabalho-com-git)
- [Cronograma e marcos do PIE](#cronograma-e-marcos-do-pie)
- [Documentação relacionada](#documentação-relacionada)

## Contexto e problema

O projeto atende **Dona Emanuela**, proprietária do Mercadinho da Cíntia, um estabelecimento varejista de pequeno porte. O levantamento de necessidades (entrevista realizada em 12/09/2026) identificou três gargalos principais na operação atual:

- **Retrabalho operacional** — fechamento de caixa e cadastro de mercadorias são feitos manualmente em papel e depois reeditados em planilhas semanais.
- **Discrepâncias financeiras** — divergências de caixa causadas majoritariamente pelo esquecimento pontual do registro de vendas no momento em que ocorrem (não por erro de precificação).
- **Controle empírico de estoque** — a conferência é feita semanalmente por inspeção visual das prateleiras, comparando com uma planilha Excel, o que consome tempo e é sujeito a falhas.

A maior dificuldade relatada pela cliente, e a área mais crítica do negócio, é o **controle de estoque**.

## Objetivos

**Objetivo geral:** desenvolver e implantar um sistema web que integre estoque, PDV e fluxo de caixa, reduzindo o trabalho manual e aumentando a confiabilidade das informações do negócio.

**Objetivos específicos:**
- Unificar cadastro de produtos, movimentação de estoque e caixa em um único sistema.
- Eliminar o uso de papéis e planilhas paralelas para o apontamento diário de caixa.
- Automatizar a baixa de itens do estoque no momento da venda, com alerta de saldo baixo.
- Disponibilizar relatórios simplificados de fluxo de caixa e lucratividade.

## Escopo

**Dentro do escopo**
- Cadastro de produtos (descrição, preço de compra/venda, quantidade, fornecedor).
- Controle de estoque com atualização automática a cada venda.
- Frente de caixa (PDV) com lançamento ágil de vendas e diferentes formas de pagamento.
- Registro de entradas/saídas financeiras diárias e demonstrativo de lucratividade.

**Fora do escopo (nesta versão)**
- Emissão de nota fiscal eletrônica (NFC-e/SAT).
- Aplicativo mobile dedicado.
- Integração com e-commerce ou delivery — o sistema atende somente vendas presenciais de balcão.
- Gestão financeira completa (contas a pagar/receber além do fluxo de caixa operacional).
- Módulo de controle rígido de validade de produtos (baixo volume de estoque, sem histórico de perdas por vencimento).
- Autenticação multiusuário ou controle de permissões por papel — o sistema é de **usuário único** (operador de caixa).

## Requisitos

### Funcionais (RF)

| Código | Nome | Descrição |
| --- | --- | --- |
| RF-01 | Cadastro de Produtos | Cadastro, edição, exclusão e consulta de itens (descrição, preço de compra/venda, quantidade inicial). |
| RF-02 | Controle de Estoque | Atualização automática da quantidade a cada venda + alerta de saldo baixo. |
| RF-03 | Frente de Caixa (PDV) | Lançamento rápido de vendas diárias, aceitando diferentes formas de pagamento. |
| RF-04 | Fluxo de Caixa | Registro de entradas/saídas diárias e demonstrativo de lucratividade acumulada. |

### Não funcionais (RNF)

| Código | Nome | Descrição |
| --- | --- | --- |
| RNF-01 | Usabilidade Simplificada | Interface minimalista, poucos cliques, sem exigir treinamento avançado. |
| RNF-02 | Desempenho e Agilidade | Tempo de resposta no registro de vendas inferior a 2 segundos. |
| RNF-03 | Integridade dos Dados | Persistência e consistência dos dados mesmo em fechamento repentino do sistema. |

### Hipótese do MVP

Um sistema simples que reúna estoque, PDV e caixa em um único lugar, reduzindo o retrabalho manual e dando visibilidade real da lucratividade. Escopo mínimo: cadastro de produtos, PDV com baixa automática de estoque, fechamento de caixa diário automático e um relatório simplificado (fluxo de caixa + produtos mais vendidos).

## Arquitetura e stack

| Camada | Tecnologia |
| --- | --- |
| Linguagem | Python |
| Framework web | Flask (recomendado pela simplicidade; Django como alternativa mais completa) |
| Banco de dados | Relacional — SQLite em desenvolvimento, podendo migrar para PostgreSQL/MySQL |
| ORM | SQLAlchemy (ou ORM nativo do Django, se essa opção for adotada) |
| Front-end | HTML, CSS e JavaScript, renderizados via templates Jinja2 |
| Controle de versão | Git + GitHub |

## Estrutura de módulos
