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

A geração corre pela cadeia grátis do model_router (sem segredos no código).
"""
from __future__ import annotations

from typing import Any

import model_router

# --------------------------------------------------------------------------- #
# System prompt — o método + os travões, embutidos.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """És o Mestre do Hermes a escrever, à mão, uma primeira mensagem \
de prospeção a UMA pessoa concreta. Escreves em português europeu/lusófono, sério \
e sóbrio. O objetivo é abrir uma conversa e conquistar o contacto — não vender já.

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
4. Provar, não entusiasmar — troca adjetivos por FACTOS: um número, um caso curto, o
   mecanismo. Credibilidade sempre verdadeira e verificável; não inventes dados.
5. Tom e fecho — escreve simples, como o mercado da pessoa fala. Fecha com UM só pedido,
   claro e de baixo compromisso (uma pergunta, uma call de 15 min, "faz sentido falarmos?").

TRAVÕES DE MARCA (nunca os quebres):
- NUNCA reveles nem insinues IA, motor, engine, LLM, automação ou "sistema" por trás.
  A mensagem é tua, de uma pessoa.
- Tom sóbrio lusófono, não hype: sem "revolucionário/incrível", sem exclamações a cada
  linha, sem excesso de emojis.
- NUNCA aconselhes compra/venda nem prometas retornos. O Hermes é investigação e análise;
  fala de clareza e rigor, nunca de recomendação financeira ou resultado prometido.

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
    """
    mensagens = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _contexto_utilizador(contacto)},
    ]
    return model_router.chat(mensagens, tarefa="copy_prospecao").strip()


if __name__ == "__main__":
    # Exemplo manual (requer pelo menos uma env key configurada).
    exemplo = {
        "nome": "Nivaldo",
        "plataforma": "LinkedIn",
        "porque_alvo": "gere um family office em Luanda, publica sobre alocação de ativos",
        "accao": "DM",
    }
    try:
        print(gerar_copy(exemplo))
    except model_router.TodosProvedoresFalharam as e:
        print(f"Sem provedores para gerar copy: {e}")
