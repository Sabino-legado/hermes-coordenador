hermes-coordenador — manual de operações
Coordenador autónomo de prospeção do Hermes Research. Corre 24/7 em contentor, uma corrida a cada 30 minutos. Este ficheiro é o manual da casa: lê-o antes de mexer em qualquer coisa.
O que este sistema é — e o que nunca é
É: um coordenador que LÊ, DECIDE e REGISTA. Lê o estado da prospeção, calcula o que falta face às metas, escreve mensagens de primeira abordagem para contactos que ainda não têm texto, e regista tudo em prospeccao_log.

Nunca é: um sistema que envia. Não envia DMs, não envia emails, não publica comentários, não contacta ninguém. O envio é manual e é sempre do Mestre. Se alguma vez te parecer boa ideia acrescentar envio aqui, não é — pergunta primeiro.

Linhas vermelhas, sem excepção:

Só toca em prospeccao_inbox, prospeccao_metas e prospeccao_log.
Nunca toca nas tabelas do produto: analyses, fmp_cache, watchlist, strategy_profiles, strategy_discoveries.
Nenhum segredo em ficheiros. Só NOMES de variáveis de ambiente. Ver .env.example.
SUPABASE_DB_URL deve ser um role dedicado às três tabelas prospeccao_*, nunca service_role nem postgres.
Em prospeccao_inbox só escreve mensagem_pronta e notas, e só em linhas com accao='DM', estado='Na fila' e mensagem_pronta vazia. Nunca mexe em estado, estagio, data_envio ou data_resposta — esses são de quem envia.
prospeccao_log é append-only. Só INSERT.
Os quatro ficheiros
Ficheiro
O que faz
model_router.py
Cadeia de modelos com fallback automático. Interface única: chat(mensagens, tarefa).
copy_engine.py
O prompt e os guardas que produzem as mensagens de prospeção.
coordinator.py
A corrida: lê, calcula, gera copy, regista.
entrypoint.py
Arranque em contentor. Modo loop (omissão) ou once.

Produção
Coolify em http://2.28.21.174:8000 → projeto "My first project" → recurso hermes-coordenador. Build por Dockerfile, branch main.

Um agente a trabalhar neste repositório NÃO vê o Coolify. Vê o origin/main e mais nada. Nunca afirmes o que está ou não está em produção — pergunta ao Mestre qual é o commit deployado. Assumir que "nada foi deployado" já causou confusão e trabalho repetido.

Alterar código não muda produção. É preciso um redeploy, e esse é feito por outra pessoa.
O motor de copy — as regras que não se negoceiam
A ficha de factos é a única fonte de verdade sobre o Hermes
Está embutida no SYSTEM_PROMPT de copy_engine.py. O modelo só conhece o que lá está, mais o campo porque_alvo do contacto. Tudo o resto não existe.

A ficha é contexto interno, nunca matéria para a mensagem. Serve para o modelo saber o que NÃO pode afirmar. Nunca a cita, nunca a parafraseia, e sobretudo nunca escreve que o Hermes "ainda não tem clientes" ou "não tem casos de estudo". Não afirmar uma coisa é diferente de anunciar que ela não existe.
Tom e língua
Português europeu. Sem brasileirismos: "modelo de negócio" e não "modelagem"; "junto de" e não "junto a"; "sector" e não "setor".
Sempre "o Hermes Research" e "fundado por Sabino Kalufele". Masculino, sem excepção.
Tratamento consistente do princípio ao fim de cada mensagem: "você" em LinkedIn e contactos institucionais (empresas, jornais, SGOIC, SDVM); "tu" só em Instagram e TikTok de criadores individuais. Nunca misturar os dois na mesma mensagem.
Sem bloco de assinatura em DMs — a plataforma já identifica quem envia.
O fecho é sempre uma oferta concreta e de baixo custo para o contacto: propor que ele escolha um emitente ou empresa e receba a análise. Nunca um pedido de opinião, de validação, de crítica ou de feedback. Nunca uma promessa de resultado.
Os dois guardas fazem coisas diferentes — e é de propósito
Guarda
O que apanha
O que faz
Porquê
contem_marcador_template()
[Nome], [Seu Nome], [empresa]
Bloqueia. Não grava, regista copy_erro.
Um marcador por preencher nunca é legítimo. Se sai, a pessoa percebe em dois segundos que ninguém releu.
contem_dados_inventados()
\d+\s*% ou um ano
Marca. Grava na mesma e acrescenta REVER: a notas, regista copy_marcada.
Números costumam ser factos VERDADEIROS sobre o contacto. Apagá-los perde copy boa em silêncio.


Não uniformizes estes dois guardas. Já houve a tentação de os tornar ambos bloqueantes, e a revisão de cinco mensagens reais mostrou que teria destruído as cinco: "27 fundos desde 2016" (facto verdadeiro sobre o BFA), "100% manual" (expressão), "melhores podcasts de 2026" (cita uma lista real). O perigo nunca foi conter um número — foi atribuir ao Hermes um facto que não existe. A regex não distingue as duas coisas; uma pessoa distingue.

A marca REVER: vai para a coluna notas, nunca para dentro da mensagem_pronta — se lá fosse, um dia saía no texto da DM.
Lições dos erros — coisas que já correram mal
O modelo inventa factos se o deixares. A primeira versão escreveu "Em 2023, aplicámos este processo a 12 iniciativas em Angola, obtendo 28% de retenção e 15% de performance". Nada disso existiu. Também descreveu o Hermes como "análise de dados comportamentais para trading em tempo real", que é outra empresa. Daí a ficha de factos e as proibições.

Os IDs de modelo morrem sem aviso. O llama-3.3-70b-versatile do Groq foi descontinuado a 16/08/2026 e o sistema foi construído com ele seis dias depois. Os três provedores devolveram 404 ao mesmo tempo. Antes de escrever ou corrigir um ID de modelo, consulta o Context7 ou a documentação oficial — nunca de memória. Hoje existe deteção: um 404 com sinais de descontinuação regista modelo_caducado no log.

os.environ.get(K, "30") devolve '' quando a variável existe mas está vazia. O default nunca entra e o float('') rebenta o contentor. Aconteceu: dez reinícios seguidos até o Coolify desistir. Usa sempre os.environ.get(K, "").strip() or "30".

Nada pode rebentar o contentor. Falta de variável, falha de modelo, erro de rede: regista e tenta na corrida seguinte. Um coordenador morto é pior do que um coordenador sem dados.
Dívidas conhecidas
A marca REVER: só é escrita, não é lida. Quem envia (a skill /enviar-dms, que vive do lado do Cowork e não neste disco) tem de parar nos contactos cuja notas comece por REVER: e mostrá-los antes de enviar. Enquanto não estiver feito, a regra é humana: ler antes de enviar.
prospeccao_metas tem 50 mensagens/dia por canal, cinco canais — 250/dia. Colide com a regra do Mestre de ritmo humano e nunca automação em massa. O motor não envia, portanto não faz mal directo, mas o número aparece em todas as corridas e no comentário do modelo.
As linhas accao='Comentário' (79) têm mensagem_pronta preenchida e não foi este código a escrevê-las. Outro processo escreve na mesma tabela, sem ficha de factos nem guardas — e esse conteúdo vai a público. Por identificar.
Gerar muitas mensagens de uma vez esgota os planos grátis. Ao gerar 72, o Groq deu 429 e a Cerebras 402; o Gemini aguentou o resto. O limite é 15 por corrida por esta razão.
Ao trabalhar aqui
Antes de mexer no SYSTEM_PROMPT, lê mensagens reais geradas em produção. Três defeitos seguidos só apareceram assim — nenhum era visível a ler o código.
Não "endureças" guardas sem perceber porque estão como estão. A tabela acima explica.
Se uma correcção te parecer errada ou arriscada, diz antes de a fazer.
