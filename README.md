# Kibot V19

Build baseada diretamente na V17 de estabilidade, agora com expansão completa do Buckshot.

## Buckshot V18
- O **bot sempre começa** a primeira rodada, independentemente da dificuldade.
- Jogador e bot possuem **3 vidas**.
- Cada bala verdadeira causa **1 dano** ao alvo; a partida só termina quando as vidas do alvo chegam a zero.
- Tiro verdadeiro mantém a vez do atirador; tiro de festim passa a vez.
- No início de cada partida são sorteados **3 itens aleatórios e únicos** para o jogador.
- Pool de 8 itens: Lupa, Serra, Cigarro, Cerveja, Algemas, Telefone, Inversor e Adrenalina.
- Os itens aparecem como botões e são consumidos somente quando usados.
- Serra permite causar 2 de dano no próximo tiro verdadeiro.
- Adrenalina pode elevar o limite do jogador para 4 vidas.
- A composição do tambor continua sendo sorteada a cada partida.
- Os modos Normal, Difícil e V4I S3 FUD3R! continuam disponíveis.

## Estabilidade
- Todas as correções de SQLite, concorrência, economia e tratamento de erros da V17 foram preservadas.
- A Central de Comandos continua dinâmica.


## Boas-vindas V19
O comando `/config boasvindas` agora cria uma embed completa e configurável. Presets disponíveis: **Kiba Sombrio**, **Elegante**, **RPG / Aventura**, **Caos** e **Minimalista**. A mensagem pode usar `{membro}`, `{servidor}` e `{contagem}`. Também existe `K! boasvindas #canal [estilo] [mensagem]`.

## Anti-BetSpam V19
Configure um canal de quarentena com `/config autoban_bets` ou `K! autobanbets #canal on`. Qualquer mensagem ou arquivo enviado por usuário comum nesse canal gera **ban automático** e, em seguida, o Kibot percorre o histórico acessível dos canais de texto e threads ativas para apagar as mensagens daquele usuário. Administradores e usuários com **Gerenciar Servidor** ficam isentos para reduzir falsos positivos.

O bot precisa ter **Banir membros**, **Gerenciar mensagens** e **Ler histórico de mensagens**. A limpeza respeita as permissões de cada canal e não consegue remover mensagens de canais aos quais o Kibot não tenha acesso.


## V26 — Tags Automáticas Desativadas

- As respostas automáticas de tags foram desativadas para evitar mensagens duplicadas/conflitos com a IA.
- Menções em qualquer canal podem disparar respostas contextuais.
- Respostas aleatórias e cooldown individual reduzem repetição/spam.
- Os comandos de gerenciamento de tags continuam disponíveis por compatibilidade, mas nenhuma tag dispara resposta automaticamente.

## V20 — Perfil e Dinheiro Sujo
- O perfil (`K! perfil` / `/perfil`) agora mostra **Dinheiro Sujo**.
- O perfil identifica o **patamar atual** de cargo e destaca a **próxima recompensa de perfil**: o próximo cargo configurado por nível.
- Operações criminais bem-sucedidas passam a gerar **Dinheiro Sujo**, separado do CRW limpo.
- `lavagem` / `K! crime lavagem` converte uma parte do Dinheiro Sujo em CRW limpo, cobrando a taxa configurada e mantendo o risco da operação.
- O saldo econômico também exibe o Dinheiro Sujo para facilitar o acompanhamento.


## V22 — IA Conversacional
- Integração opcional com Google Gemini via `google-genai`.
- Configure `GEMINI_API_KEY` no `.env`.
- `GEMINI_MODEL` padrão: `gemini-3.5-flash-lite`.
- Mencionar o Kibot ou responder a uma mensagem dele ativa a conversa.
- `K! ia pergunta` e `/ia` também ativam.
- Memória curta persistente por canal (últimas 30 mensagens armazenadas; 12 usadas por resposta).
- `/ia_limpar_memoria` limpa a memória do canal para quem tem Gerenciar Servidor.
- Cooldown padrão: 8s por usuário/canal.


## V26 — Identidade por usuário e modo sério do dono
- A IA recebe explicitamente o autor da mensagem atual, com nome, username e ID.
- O histórico recente também é rotulado com o membro correspondente, reduzindo confusão entre participantes.
- Menções e respostas a mensagens são identificadas sem trocar a autoria da pergunta.
- O dono do servidor e os `OWNER_IDS` configurados são reconhecidos.
- Quando o próprio dono fala ou o assunto envolve o dono/criador, o Kibot entra em modo sério e respeitoso.
- A regra de identidade é enviada junto do contexto para impedir que a IA atribua a pergunta de um membro a outro.


## Dados recentes — V28

O Kibot agora possui uma camada de dados externos para clima, futebol e notícias.

- `K! clima <cidade>` / `/clima`: Open-Meteo, sem chave.
- `K! futebol` / `/futebol`: football-data.org; configure `FOOTBALL_DATA_API_KEY`.
- `K! noticias [tema]` / `/noticias`: GNews; configure `GNEWS_API_KEY`.
- A IA tenta consultar esses dados automaticamente quando a pergunta pede informação atual.
- Respostas externas ficam em cache por `REALTIME_CACHE_SECONDS` (padrão: 60s) para evitar spam de API.


## V29 — Ações do dono via linguagem natural
- O dono reconhecido por `OWNER_IDS` ou como dono da guild pode pedir ações administrativas diretamente à IA.
- Exemplos: `Kibot, muta @Usuário por 10 minutos`, `Kibot, desmuta @Usuário`, `Kibot, expulsa @Usuário`.
- A execução é feita por código, não pelo Gemini, e continua limitada às permissões/hierarquia do Discord.
- Membros comuns nunca podem acionar essa ponte administrativa.


## V30 — Respostas direcionadas

Quando a IA é acionada por uma mensagem normal, o Kibot responde usando `Message.reply()`, mantendo a resposta visualmente vinculada à mensagem/pergunta do usuário. Ações administrativas do dono e mensagens de erro da IA também usam resposta direcionada. `mention_author=False` evita pingar novamente o autor.


## V31 — Correção de conflito de alias
A extensão de dados recentes não registra mais `jogos` como alias de `K! futebol`, pois esse alias já pertence ao comando `K! arcade` do módulo de jogos. `K! futebol` mantém o alias `partidas`, eliminando o `CommandRegistrationError` que impedia `cogs.realtime_data` de carregar.


## V33 — Notícias verificadas e fontes

A IA não trata mais notícias como conhecimento livre. Quando uma pergunta pede notícias ou fatos recentes, o Kibot consulta o módulo de dados recentes/GNews e só envia o pedido ao Gemini quando recebeu artigos reais com título, veículo, data, resumo e URL. A resposta final inclui automaticamente as fontes consultadas em links clicáveis. Se a consulta falhar ou não houver fontes verificáveis, o Kibot informa que não conseguiu confirmar em vez de inventar uma notícia.

Também foram reforçadas as instruções da personalidade para impedir que o Gemini invente títulos, veículos, datas, números, acontecimentos ou URLs em consultas de notícias.


## V34 — Code Guard, fontes resilientes e fallback de moderação

- **Code Guard:** o Kibot monitora erros de comandos e falhas de carregamento, localiza arquivo/linha, coleta contexto sanitizado do código e usa o Gemini como engenheiro de diagnóstico. O resultado é enviado por DM aos IDs de `OWNER_IDS` e ao dono da guild.
- `K! diagnostico` / `K! diagnosticar` / `K! codecheck`: executa uma varredura estática dos arquivos Python e manda o resultado por DM.
- O diagnóstico nunca inclui tokens, senhas ou chaves conhecidas.
- **Notícias:** GNews continua sendo a fonte primária quando `GNEWS_API_KEY` está configurada. Se a chave estiver ausente ou o GNews falhar, o Kibot tenta **Google News RSS**, mantendo título, veículo, data e URL da matéria.
- A IA só responde perguntas de notícias quando conseguiu fontes verificáveis e acrescenta automaticamente **📰 Fontes consultadas** com links reais.
- **Mute:** se o bot não tiver `Moderar Membros`, pode usar um cargo `Muted`/`Silenciado` configurado em `MUTE_ROLE_ID`, desde que tenha `Gerenciar Cargos` e a hierarquia permita. Isso não burla as permissões do Discord.

### Variáveis novas
```env
MUTE_ROLE_ID=
```

> O Discord não permite que um bot execute moderação sem as permissões necessárias. O fallback por cargo apenas usa a permissão alternativa de Gerenciar Cargos; não existe bypass legítimo da API.


## V35 — Correção de alvo das ações de moderação
- Corrigido um bug importante no fluxo de moderação por linguagem natural: ao mencionar `@Kibot` e também o usuário alvo, a lista `message.mentions` continha o próprio Kibot primeiro, fazendo o executor interpretar o bot como alvo e recusar a ação.
- Agora a menção do próprio Kibot é removida antes da resolução do alvo.
- Adicionados aliases naturais como `muta`, `desmuta`, `expulse` e `adverte`.
- O executor registra no log a ação detectada, alvo textual e IDs das menções para facilitar diagnóstico.
- Build: `2026-09-13-KIBOT-XP-JACKPOT-ASSETS-MINES-v43`.


## V36 — Acesso à IA por cargo
A conversa com a IA agora é restrita a membros que possuam um cargo chamado exatamente `ia` (comparação sem diferenciar maiúsculas/minúsculas). Isso vale para menções/respostas, `K! ia`, `/ia` e `ia_limpar_memoria`. Os demais comandos do Kibot continuam acessíveis conforme suas próprias permissões.


## V37 — Fontes de notícias mais limpas
As respostas de notícias agora exibem uma lista numerada com veículo e manchete, escondendo URLs longas no Markdown do Discord. Quando possível, o Kibot tenta resolver o redirecionamento do Google News para apontar diretamente para o veículo.


## V38 — Redesign global dos embeds
Todos os embeds usados pelos comandos do Kibot foram centralizados em `KibotEmbed`, aplicando uma identidade visual consistente: timestamp automático, rodapé padronizado e melhor tratamento de conteúdo dos campos. A alteração cobre todos os módulos que utilizavam `discord.Embed`, sem remover os conteúdos, botões, campos ou funções existentes.


## V39 — Redesign global de espaçamento dos Embeds

Todos os embeds que usam `KibotEmbed` agora seguem um layout vertical e espaçado: campos não ficam mais em colunas apertadas, valores recebem respiro visual, e a descrição ganha separação do conteúdo. O padrão fica centralizado em `cogs/embed_style.py`, preservando cores, títulos, componentes e lógica dos comandos.

## V40 — Redesign real de organização dos embeds
- Corrigido o problema da V39 que forçava todos os campos para uma única coluna.
- `KibotEmbed` agora respeita `inline=True`/`inline=False`, permitindo grades de 2/3 colunas para estatísticas e blocos de largura total para textos longos.
- Adicionados cabeçalhos de seção e separadores reutilizáveis.
- O `K!perfil` foi reorganizado em seções: Identidade, Progresso, Economia, Recompensas e Cargos.
- O conteúdo dos comandos foi preservado; a alteração é de apresentação/layout.

## V42 — XP 2x, Jackpot universal e informações internas do dono
- Dono do bot (IDs em `OWNER_IDS`) e cargo Booster (`XP_BOOSTER_ROLE_ID`) recebem 2x XP.
- Jackpot universal nos jogos de aposta: vitória especial garante pelo menos 3x a aposta (sem reduzir prêmios-base maiores).
- Blackjack tem jackpot garantido para Blackjack natural e chance de jackpot nas demais vitórias.
- Todos os jogos do Arcade aceitam aposta em CRW ou XP (`xp:100`, `xp100` ou `100xp`).
- Ganhos em XP também respeitam o bônus 2x de dono/Booster.
- Perguntas sobre build, linguagem, bibliotecas, arquitetura, código e configuração interna são respondidas diretamente apenas ao dono do bot. Segredos como tokens e chaves nunca são exibidos.


## V43 — Emojis, figurinhas e Mines configurável
- Painel `K! addemoji` / `/addemoji` com botões para arquivo, URL e emoji personalizado já existente.
- Painel `K! addfigurinha` / `/addfigurinha` com botões para arquivo, URL e figurinha já existente.
- Ambos exigem a permissão **Gerenciar Expressões** e verificam a permissão correspondente do Kibot.
- `K! mines aposta [bombas]` e `/mines` agora aceitam de **1 a 19 bombas** em 20 casas; 4 bombas continuam sendo o padrão.
- A progressão de multiplicador do Mines passa a considerar a quantidade de bombas escolhida.
- Central de ajuda e tutorial atualizados.

## V44 — Correção do botão Todos
- Corrigida a falha da página `📋 Todos` da Central de Comandos.
- A lista dinâmica agora é paginada para nunca ultrapassar o limite de 25 fields do Discord.
- ◀️/▶️ navegam entre as páginas internas de `Todos`.
- A seleção de outra categoria reseta a paginação.
- Cada bloco fica abaixo do limite de caracteres de field do Discord.


## V47 — Correção do limite de Slash Commands
- `cogs.admin_economy` mantém os comandos administrativos via prefixo e deixa de registrar os 10 duplicados como Slash Commands.
- Isso evita ultrapassar o limite global de 100 comandos Slash.
- Corrigido também o campo `moderation_confirmations_enabled` na lista de configurações permitidas do banco.


## V49 — GIFs Anime
Os GIFs decorativos do Kibot são exclusivamente anime/SFW e escolhidos por categoria conforme o comando (kiss, hug, pat, slap, punch, blush, cry, spin, think, shake, shocked, shoot, dance etc.). O Kibot consulta a API pública NekosBest sem chave e usa cache curto para reduzir chamadas.
