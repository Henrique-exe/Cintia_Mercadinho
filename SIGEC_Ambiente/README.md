# SIGEC | Ambiente reproduzível
PIE – UNIFAN | Grupo 2 | Preparação do ambiente de desenvolvimento

Objetivo: um segundo integrante deve conseguir iniciar uma página Flask local que consulta produtos e clientes fictícios no SQLite. Este pacote é uma base independente para verificar o ambiente; a integração com as branches do projeto e o acesso ao GitHub devem ser confirmados pela equipe. Não implementa o PDV completo.

## Antes de começar
Instale Python 3.12 com suporte a venv e pip. Extraia TODO o ZIP em uma pasta gravável. Abra o terminal na pasta que contém app.py. A primeira instalação baixa dependências e requer internet. Depois disso, a página e o banco funcionam sem internet. Não é necessário instalar um servidor SQLite. Os comandos abaixo não exigem ativar o ambiente virtual.

## Windows (PowerShell ou Prompt)
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe verificar_web.py
    .\.venv\Scripts\python.exe app.py

## Linux ou macOS
    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python verificar_web.py
    .venv/bin/python app.py

## Conferir no navegador
Abra http://127.0.0.1:5000 no mesmo computador. Devem aparecer “Arroz 1 kg” com 8 unidades, “Mortadela” com 2,500 kg e um cliente fictício. O servidor é apenas para desenvolvimento, sem depuração, e só escuta no próprio computador. Encerre com Ctrl+C. Reinicie com o último comando: os dados continuam no arquivo dados/ambiente_demo.sqlite3. Executar novamente não duplica os cadastros nem restaura por cima de saldos já alterados.

## O que os testes verificam
verificar_banco.py usa somente a biblioteca padrão: cria uma base temporária, altera um saldo, fecha, reabre e verifica que a alteração persiste e a carga não duplica registros. verificar_web.py também faz requisições à rota Flask usando seu cliente de teste e confere os valores exibidos. Ambos usam bases temporárias; não mexem no banco da demonstração. O preço está em centavos; quantidades em KG são guardadas em gramas.

## Entrega da atividade de 05/11
1. Um segundo integrante extrai o mesmo ZIP (ou baixa a versão correspondente do repositório após integração) e segue o procedimento acima.
2. Confere a mensagem OK de verificar_web.py, abre a página, encerra e reinicia sem internet. Guarda uma captura da página e a saída do teste.
3. Registra nome, data real, sistema operacional, versão do Python, versão do código e resultado. Se falhar, registra o erro sem marcar como concluído.
4. Confere o acesso dos integrantes ao repositório https://github.com/Henrique-exe/Cintia_Mercadinho e vincula a evidência na linha 28 da aba Atividades MVP.

Para integrar: manter o código existente da equipe e revisar os arquivos em uma branch. Se o projeto já usa Poetry, seguir o gerenciador e o lock do repositório; não substituir sua configuração por este pacote. Não versionar .venv, dados locais nem informações reais da cliente.

## Problemas comuns
Se o terminal não localizar app.py, abra a pasta extraída que contém este README. Se Flask não for encontrado, refaça a instalação usando o mesmo executável da .venv dos comandos acima. Se a porta 5000 estiver ocupada, encerre a instância anterior ou ajuste a porta em app.py e no endereço do navegador.
