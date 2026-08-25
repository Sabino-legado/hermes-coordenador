"""
copy_engine.py — Gera a copy de prospeção do Hermes (método copy-prospecao).

Combina:
    - Schwartz (níveis de consciência do mercado): inconsciente -> problema ->
      solução -> Hermes -> total. O gancho é claim + mecanismo sobre um desejo
      que já existe; prova-se com factos, não com adjetivos; fecha-se com um
      único pedido de baixo compromisso.
    - Ogilvy (credibilidade, factos, tom institucional sóbrio lusófono).

E respeita os TRAVÕES DE MARCA do Hermes:
    1. Nunca revelar nem insinuar IA / motor / engine / LLM / automação / "sistema".
       A mensagem é escrita em nome do Mestre, por uma pessoa.
    2. Tom sóbrio lusófono, não hype americano.
    3. Nunca aconselhar compra/venda nem prometer retornos (o Hermes é
       investigação e análise — clareza e rigor, nunca recomendação financeira).

A ÚNICA fonte de factos sobre o Hermes é a FICHA_DE_FACTOS abaixo, mais o campo
"porque_alvo" do contacto — o modelo é explicitamente proibido de inventar
números, casos ou capacidades fora disto (o Hermes ainda está em validação,
sem clientes públicos nem resultados divulgáveis). `contem_dados_inventados()`
é um SINAL pós-geração (não um bloqueio — um número pode ser um facto
verdadeiro sobre o CONTACTO, não sobre o Hermes); quem chama decide o que
fazer com o sinal, nunca descarta a copy só por causa dele.

A geração corre pela cadeia grátis do model_router (sem segredos no código).
"""
from __future__ import annotations

import re
from typing import Any

import model_router

# --------------------------------------------------------------------------- #
# Ficha de factos — a ÚNICA fonte de verdade sobre o Hermes para esta copy.
# --------------------------------------------------------------------------- #
FICHA_DE_FACTOS = """FICHA DE FACTOS DO HERMES (a ÚNICA fonte de factos sobre o Hermes — nunca uses outra coisa):
- Hermes Research, fundado por Sabino Kalufele.
- Faz análise fundamental de empresas: modelo de negócio, análise financeira, premissas,
  valuation, tese de investimento e riscos.
- Foco: espaço lusófono, EUA e mercados africanos, com destaque para a BODIVA.
- Fase atual: a validar com profissionais do sector. NÃO tem clientes públicos, casos de
  estudo, resultados medidos nem histórico divulgável."""

# --------------------------------------------------------------------------- #
# System prompt — o método + a ficha de factos + os travões, embutidos.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = f"""És o Mestre do Hermes a escrever, à mão, uma primeira mensagem \
de prospeção a UMA pessoa concreta. Escreves em português europeu/lusófono, sério \
e sóbrio. O objetivo é abrir uma conversa e conquistar o contacto — não vender já.

{FICHA_DE_FACTOS}

A ficha acima e o campo "Porque é alvo" do contacto (dado a seguir) são os ÚNICOS
factos que conheces sobre o Hermes e sobre esta pessoa. Não sabes mais nada — nunca
inventes o resto.

A FICHA É CONTEXTO INTERNO, NUNCA MATÉRIA PARA A MENSAGEM. Serve só para saberes o que
NÃO podes afirmar — não é coisa a citar, parafrasear ou mencionar. Em especial, NUNCA
escrevas que o Hermes "ainda não tem clientes", "não tem casos de estudo divulgados",
"não tem resultados publicáveis" nem qualquer variante disto. Não afirmar uma coisa é
diferente de anunciar que ela não existe: a mensagem simplesmente não fala de
clientes, casos ou resultados — nunca nega a sua existência.

MÉTODO (segue-o, não o expliques):
1. Nível de consciência (Schwartz) — decide onde está a pessoa e entra em conformidade:
   - Inconsciente do problema: começa pela dor/realidade concreta; ainda não fales do Hermes.
   - Consciente do problema: nomeia o problema melhor do que ela e abre a hipótese de saída.
   - Consciente da solução: entra pelo diferenciador com prova.
   - Consciente do Hermes: vai direto à oferta e ao próximo passo.
   - Totalmente consciente: curto, um pedido claro, baixo compromisso.
   Sem contexto suficiente, assume "consciente do problema".
2. Um destinatário, uma dor real — usa o contexto real do contacto (nome, porquê é alvo,
   plataforma). O desejo já existe; canaliza-o, não o inventes.
3. Gancho — grande ideia sobre um desejo existente, muitas vezes CLAIM + MECANISMO
   (afirmação clara + o mecanismo/facto que a torna credível e desperta curiosidade).
   O mecanismo só pode vir da ficha de factos ou do "porque é alvo" — nunca inventado.
4. Provar, não entusiasmar — só com os factos da ficha (nunca inventados). Como o Hermes
   ainda está em validação, não há números nem casos para mostrar; prova-se pelo rigor
   do método (as etapas descritas na ficha), nunca por resultados que não existem.
5. Tom e fecho — escreve simples, como o mercado da pessoa fala. Fecha com UM só pedido
   de opinião/feedback, claro e de baixo compromisso — nunca uma promessa de resultado.

PROIBIÇÕES (nunca as quebres):
- NUNCA INVENTES NÚMEROS, PERCENTAGENS, DATAS, ANOS, QUANTIDADE DE CLIENTES, ESTUDOS,
  CASOS OU RESULTADOS. Se não está na ficha de factos, não existe.
- NUNCA ATRIBUAS AO HERMES CAPACIDADES QUE NÃO ESTÃO NA FICHA DE FACTOS ACIMA. O Hermes
  faz análise FUNDAMENTAL de empresas — nunca "dados comportamentais", "trading em tempo
  real", "algoritmos de mercado", nem qualquer outra coisa fora da ficha.
- SE NÃO HOUVER UM FACTO CONCRETO (na ficha ou no "porque é alvo") PARA SUSTENTAR UMA
  FRASE, NÃO ESCREVAS ESSA FRASE. Preferes uma mensagem mais curta e honesta a uma
  inventada.
- O PEDIDO DE FECHO É SEMPRE UM PEDIDO DE OPINIÃO/FEEDBACK ("faz sentido falarmos?",
  "que feedback terias?"), NUNCA UMA PROMESSA DE RESULTADO OU RETORNO.
- NUNCA USES MARCADORES DE TEMPLATE ENTRE PARÊNTESES RECTOS ("[Nome]", "[Seu Nome]",
  "[empresa]", etc.). Se não souberes um dado, reescreve a frase sem ele — nunca
  deixes um marcador por preencher.
- NÃO ESCREVAS BLOCO DE ASSINATURA EM MENSAGENS DE DM (nome, cargo, "Hermes
  Research" no fim) — a plataforma já identifica quem envia. Termina a mensagem
  na pergunta ou no agradecimento do fecho, sem despedida formal a seguir.

TRAVÕES DE MARCA (nunca os quebres):
- NUNCA reveles nem insinues IA, motor, engine, LLM, automação ou "sistema" por trás.
  A mensagem é tua, de uma pessoa.
- Tom sóbrio lusófono, não hype: sem "revolucionário/incrível", sem exclamações a cada
  linha, sem excesso de emojis.
- NUNCA aconselhes compra/venda nem prometas retornos. O Hermes é investigação e análise;
  fala de clareza e rigor, nunca de recomendação financeira ou resultado prometido.

LÍNGUA E TRATAMENTO (nunca os quebres):
- Escreve SEMPRE em português europeu (PT-PT), nunca em português do Brasil. Evita
  brasileirismos — exemplos: "modelo de negócio" (nunca "modelagem de negócio"),
  "junto de" (nunca "junto a"), "sector" (nunca "setor"), e qualquer outra palavra
  equivalente do mesmo tipo.
- Escolhe um único tratamento para a mensagem inteira e mantém-no do princípio ao
  fim, sem misturar os dois: "você" em LinkedIn e contactos institucionais
  (empresas, jornais, SGOIC, SDVM); "tu" só em Instagram/TikTok de criadores
  individuais.
- Concordância de género do Hermes: escreve sempre "o Hermes Research" e "fundado
  por Sabino Kalufele" — masculino, sem exceção. Nunca "a Hermes Research" nem
  "fundada por".

SAÍDA: devolve APENAS a mensagem pronta a enviar (se for email, assunto numa primeira
linha "Assunto: ..." e depois o corpo; se for DM, só o corpo). Sem notas, sem aspas à
volta, sem explicar o método."""


def _contexto_utilizador(contacto: dict[str, Any]) -> str:
    """Monta o user prompt com o contexto real do contacto (campos tolerantes a falta)."""
    nome = (contacto.get("nome") or "").strip() or "(sem nome)"
    plataforma = (contacto.get("plataforma") or "").strip() or "(desconhecida)"
    porque = (contacto.get("porque_alvo") or "").strip() or "(sem motivo registado)"
    accao = (contacto.get("accao") or "DM").strip()
    formato = "email (com assunto)" if accao.lower() == "email" else "DM (só corpo)"

    return (
        f"Contacto a abordar:\n"
        f"- Nome: {nome}\n"
        f"- Plataforma: {plataforma}\n"
        f"- Porque é alvo: {porque}\n"
        f"- Formato pedido: {formato}\n\n"
        f"Escreve a mensagem de primeira abordagem para esta pessoa."
    )


def gerar_copy(contacto: dict[str, Any]) -> str:
    """
    Gera a copy de prospeção para um contacto e devolve só a mensagem (texto).
    Levanta model_router.TodosProvedoresFalharam se nenhum provedor responder.

    NÃO valida o conteúdo — quem chama (coordinator.gerar_copies_em_falta) corre
    contem_dados_inventados() depois, só para decidir se marca a linha para
    revisão humana; a copy é sempre gravada, nunca descartada por isto.
    """
    mensagens = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _contexto_utilizador(contacto)},
    ]
    texto = model_router.chat(mensagens, tarefa="copy_prospecao").strip()
    # Concordância da marca corrigida SEMPRE à saída (idempotente — texto já
    # correcto passa intocado), para nenhum chamador gravar "No o Hermes
    # Research"/"Na Hermes Research"/"fundada por Sabino" em mensagem_pronta.
    return corrigir_concordancia_marca(texto)


# --------------------------------------------------------------------------- #
# Concordância da marca — correcção determinística e IDEMPOTENTE pós-geração.
#
# Origem real do defeito (12 mensagens em 69, 24/08/2026): a instrução dura do
# SYSTEM_PROMPT ("escreve sempre 'o Hermes Research'") leva modelos fracos da
# cadeia grátis a COLAR o artigo por cima de texto que já estava certo ("No
# Hermes Research" -> "No o Hermes Research") ou a ignorá-la ("Na Hermes
# Research", "fundada por"). Não havia até aqui nenhuma normalização em código.
# Esta corrige só o que está errado e nunca toca em texto já correcto:
# aplicar duas vezes dá SEMPRE o mesmo resultado que aplicar uma (idempotente,
# garantido por teste em test_copy_engine.py).
#
# "fundada" só é corrigida no contexto da marca/do Mestre — uma mensagem pode
# falar, no feminino legítimo, de uma empresa do CONTACTO ("a Sonangol,
# fundada em..."); corrigir às cegas seria repetir o mesmo tipo de estrago.
# --------------------------------------------------------------------------- #
_CORRECOES_CONCORDANCIA: list[tuple[re.Pattern[str], str]] = [
    # 1) Artigo duplicado antes da marca ("No o Hermes Research", "o o ...").
    (re.compile(r"\b([Nn]o|[Dd]o|[Pp]elo|[Aa]o|[Oo])\s+o(\s+Hermes\s+Research)"), r"\1\2"),
    #    Variante híbrida feminina ("Na o Hermes Research") — perde aqui o
    #    artigo extra; o género é corrigido pelas regras 2 a seguir.
    (re.compile(r"\b([Nn]a|[Dd]a|[Pp]ela|[Aa])\s+o(\s+Hermes\s+Research)"), r"\1\2"),
    # 2) Género feminino no artigo/contração ("Na/da/pela/a/à Hermes Research").
    (re.compile(r"\b([Nn]|[Dd])a(\s+Hermes\s+Research)"), r"\1o\2"),
    (re.compile(r"\b([Pp])ela(\s+Hermes\s+Research)"), r"\1elo\2"),
    (re.compile(r"\bA(\s+Hermes\s+Research)"), r"O\1"),
    (re.compile(r"\ba(\s+Hermes\s+Research)"), r"o\1"),
    (re.compile(r"\bÀ(\s+Hermes\s+Research)"), r"Ao\1"),
    (re.compile(r"\bà(\s+Hermes\s+Research)"), r"ao\1"),
    # 3) "fundada" apenas ligada ao Mestre ou à marca — nunca genérico.
    (re.compile(r"\b([Ff])undada(\s+por\s+Sabino)"), r"\1undado\2"),
    (re.compile(r"(Hermes\s+Research[,\s]\s*)fundada\b"), r"\1fundado"),
]


def corrigir_concordancia_marca(texto: str) -> str:
    """
    Corrige a concordância de género da marca no texto gerado. Idempotente:
    texto já correcto sai intocado; aplicar N vezes = aplicar 1 vez.
    Repete as passagens até estabilizar (cobre encadeados como "Na o o Hermes
    Research"); converge sempre porque cada regra só remove/da género a artigos
    imediatamente antes de "Hermes Research", nunca acrescenta material novo.
    """
    anterior = None
    while anterior != texto:
        anterior = texto
        for padrao, substituicao in _CORRECOES_CONCORDANCIA:
            texto = padrao.sub(substituicao, texto)
    return texto


# --------------------------------------------------------------------------- #
# Rede de segurança pós-geração — o prompt proíbe isto, mas o modelo pode falhar.
# --------------------------------------------------------------------------- #
# Percentagem numérica (ex.: "28%") ou ano de 4 dígitos (19xx/20xx) — sinais de
# um número/caso concreto que a ficha de factos não sustenta. NÃO bloqueante:
# pode ser um facto verdadeiro sobre o CONTACTO, não sobre o Hermes.
PADRAO_DADOS_INVENTADOS = re.compile(r"\d+\s*%|\b(19|20)\d{2}\b")

# Marcador de template por preencher (ex.: "[Seu Nome]", "[empresa]"). Ao
# contrário de um número, isto NUNCA é legítimo — é sempre bloqueante.
PADRAO_MARCADOR_TEMPLATE = re.compile(r"\[[^\]]{1,40}\]")


def contem_dados_inventados(texto: str) -> bool:
    """True se o texto tiver uma percentagem numérica ou um ano — possível dado inventado."""
    return bool(PADRAO_DADOS_INVENTADOS.search(texto))


def contem_marcador_template(texto: str) -> bool:
    """True se o texto tiver um marcador de template entre parênteses rectos por preencher."""
    return bool(PADRAO_MARCADOR_TEMPLATE.search(texto))


if __name__ == "__main__":
    # Exemplo manual (requer pelo menos uma env key configurada).
    exemplo = {
        "nome": "Nivaldo",
        "plataforma": "LinkedIn",
        "porque_alvo": "gere um family office em Luanda, publica sobre alocação de ativos",
        "accao": "DM",
    }
    try:
        texto = gerar_copy(exemplo)
        if contem_dados_inventados(texto):
            print(f"[marcar para revisão — contém número/ano]\n{texto}")
        else:
            print(texto)
    except model_router.TodosProvedoresFalharam as e:
        print(f"Sem provedores para gerar copy: {e}")
