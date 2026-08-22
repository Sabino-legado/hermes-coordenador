# Coordenador autónomo — Hermes

Coordenador 24/7 de prospeção/vendas. **Coordena, decide e regista — nunca envia mensagens
nem contacta ninguém.** O envio continua manual ou noutros agentes.

Nunca toca nas tabelas do produto (`analyses`, `fmp_cache`, `watchlist`,
`strategy_profiles`, `strategy_discoveries`). Só usa `prospeccao_inbox`,
`prospeccao_metas` e `prospeccao_log`.

## Ficheiros

- `model_router.py` — fallback automático de modelo (Groq → Cerebras → Gemini → DeepSeek;
  Claude só com `ALLOW_CLAUDE=1`). Interface única `chat(mensagens, tarefa)`.
- `coordinator.py` — corrida do coordenador: progresso por canal vs metas, % Angola,
  funil, contactos a arrefecer, e registo em `prospeccao_log`.
- `entrypoint.py` — arranque em contentor: modo `loop` (a cada `INTERVALO_MIN` min) ou `once`.
- `requirements.txt`, `Dockerfile`, `.env.example`, `.gitignore`.

## Segredos

Nenhuma chave está no código. Tudo é lido de variáveis de ambiente **por nome**.
Ver `.env.example` (só nomes). `SUPABASE_DB_URL` deve ser a connection string de um
**role dedicado** com acesso apenas às três tabelas `prospeccao_*` — **nunca** service_role.

## Variáveis de ambiente

| Variável | Para quê | Obrigatória |
|---|---|---|
| `SUPABASE_DB_URL` | ligação Postgres (role dedicado) | sim |
| `GROQ_API_KEY` | provedor 1 (Llama 3.3 70B) | opcional* |
| `CEREBRAS_API_KEY` | provedor 2 (Llama 3.3 70B) | opcional* |
| `GEMINI_API_KEY` | provedor 3 (Gemini 2.5 Flash) | opcional* |
| `DEEPSEEK_API_KEY` | provedor 4 (DeepSeek V3.2) | opcional* |
| `RUN_MODE` | `loop` (omissão) ou `once` | não |
| `INTERVALO_MIN` | minutos entre corridas no modo loop (omissão 30) | não |

\* Um provedor sem a sua env key é saltado em silêncio. Configura pelo menos um.

## Deploy no Coolify (contentor)

O `Dockerfile` corre `entrypoint.py` em modo loop (uma corrida a cada `INTERVALO_MIN`
minutos). No Coolify: New Resource → Application a partir deste repo (build por Dockerfile),
definir as variáveis de ambiente, e deploy. O contentor é resiliente: sem `SUPABASE_DB_URL`
ou chave, não rebenta — regista e tenta de novo no ciclo seguinte.

## Fallback de modelo

`chat()` tenta os provedores por ordem fixa. Em `429`, quota, timeout ou falha, passa ao
seguinte automaticamente e grava `tipo='modelo_troca'` em `prospeccao_log`. Se todos
falharem, levanta `TodosProvedoresFalharam` e regista `tipo='erro'`. Claude nunca é
chamado sem `ALLOW_CLAUDE=1`.
