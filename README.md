# FS25 Serviços Agrícolas

Catálogo, calculadora de orçamento e bot do Discord para uma empreiteira agrícola no Farming Simulator 25.

## O que já funciona

- catálogo oficial com busca e filtros;
- 38 serviços e 7 pacotes;
- orçamento por hectare, hora ou viagem;
- desconto progressivo de 5%, 8% e 10%;
- cobrança mínima de $ 5.000 nos serviços por hectare;
- cálculo opcional de insumos com taxa de fornecimento de 10%;
- botão para copiar o orçamento para o Discord;
- gerador de OS com cliente, fazenda, campo, cultura e observações;
- histórico local de pedidos no navegador;
- comandos `/orcamento`, `/solicitar`, `/minhas-os`, `/fila` e `/stats`;
- fluxo de aprovação, início, conclusão e cancelamento de OS;
- armazenamento das ordens em SQLite.

## Fluxo recomendado

1. O jogador consulta ou calcula o serviço no site.
2. Pode gerar uma OS local e copiar a mensagem para o Discord.
3. Com o bot ativo, usa `/solicitar` para registrar a ordem oficial.
4. A equipe aprova, inicia ou conclui pelos botões do canal de pedidos.
5. `/minhas-os` mostra o histórico do cliente, `/fila` mostra os próximos trabalhos e `/stats` resume a operação.

## Publicar o site no GitHub Pages

O conteúdo da pasta `web` é o site. Como ele compartilha os arquivos da pasta `data`, publique a raiz do projeto por uma GitHub Action ou copie `data` para dentro do diretório publicado. Para testar localmente, sirva a raiz do projeto e abra `/web/`.

## Configurar o bot

1. Instale Python 3.11 ou superior.
2. Na pasta `bot`, instale as dependências de `requirements.txt`.
3. Copie `.env.example` para `.env`.
4. Preencha o token, o ID do servidor e o ID do canal privado de pedidos.
5. Ative os escopos `bot` e `applications.commands` ao convidar o bot.
6. Execute `bot.py`.

O arquivo `.env` não deve ser enviado ao GitHub.

## Próximas etapas previstas

- formulários guiados com menus e botões no Discord;
- negociação de valores em threads;
- cadastro de fazendas e culturas;
- frota e disponibilidade de máquinas;
- fila operacional e agenda;
- estatísticas e histórico por cliente;
- imagens reais do servidor.

