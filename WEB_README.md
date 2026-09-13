# Kibot V51 — Site + Dashboard conectado

Esta versão usa o V50 como base e conecta o dashboard ao `database/db.py` do Kibot.

## O que funciona
- Login Discord via OAuth2 com `state` protegido.
- Lista de servidores em que o usuário é dono ou administrador.
- Seleção de servidor.
- Leitura das configurações reais de `guild_config`.
- Alteração real pelo dashboard de:
  - sistema de XP;
  - confirmação de moderação;
  - Auto-ban bets;
  - canal de Auto-ban bets;
  - mensagem de boas-vindas;
  - canal de boas-vindas.
- O backend valida novamente se o usuário administra a guild antes de ler/escrever.
- Bot e site podem rodar no mesmo processo quando `WEB_ENABLED=1`, compartilhando o SQLite.

## Rodar no computador
1. Instale as dependências:
   `pip install -r requirements.txt -r requirements-web.txt`
2. Configure as variáveis do `.env`.
3. No Discord Developer Portal, em OAuth2, adicione exatamente:
   `https://SEU-DOMINIO/oauth/callback`
4. Inicie com `WEB_ENABLED=1 python main.py`.
5. Abra o endereço público configurado em `WEB_PUBLIC_URL`.

## Pelo celular
A opção mais simples é colocar o projeto em um repositório GitHub e conectar esse repositório a um serviço de hospedagem que execute Python. O arquivo `render.yaml` já deixa o comando de build/start preparado para um serviço web único (bot + dashboard).

Depois da primeira publicação:
1. Copie a URL pública recebida pela hospedagem.
2. Cadastre `https://SUA-URL/oauth/callback` no OAuth2 do Discord.
3. Configure `WEB_PUBLIC_URL` com essa mesma URL.
4. Defina `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` e `WEB_SESSION_SECRET` como variáveis secretas.
5. Reinicie/republique o serviço.

## Importante sobre SQLite
O dashboard e o bot precisam acessar o mesmo arquivo `kibot.db`. Por isso o modo recomendado nesta versão é bot + web no mesmo serviço/processo. Não coloque o bot em um host e o dashboard em outro esperando que ambos compartilhem um SQLite local.
