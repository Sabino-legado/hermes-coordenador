"""
coordinator.py — Ciclo do coordenador autónomo de prospeção/vendas do Hermes.

O que faz numa corrida:
    (a) lê prospeccao_inbox, prospeccao_metas e o funil (coluna estagio);
    (b) calcula o progresso do dia por canal vs metas (msgs_*_dia) e a % Angola;
    (c) identifica o que falta para as metas e os contactos que estão a arrefecer;
    (d) usa o model_router para gerar um comentário/decisão curta (best-effort);
    (e) gera copy para a fila (DM, "Na fila", sem mensagem pronta):
        - marcador de template por preencher (ex.: "[Seu Nome]") NUNCA é legítimo
          → bloqueia, não grava em mensagem_pronta, regista (tipo='copy_erro')
          e passa ao contacto seguinte;
        - sinal de número concreto (percentagem/ano) PODE ser um facto verdadeiro
          sobre o CONTACTO, não sobre o Hermes → grava sempre em mensagem_pronta,
          só marca a linha para revisão humana em `notas` e regista
          (tipo='copy_marcada'), nunca bloqueia;
    (f) escreve um resumo da corrida em prospeccao_log
        (tipo='coordenador_run', dados jsonb com os números).

O que NUNCA faz:
    - Não envia mensagens nem contacta ninguém (o envio é manual / noutros agentes).
    - Não toca nas tabelas do produto Hermes
      (analyses, fmp_cache, watchlist, strategy_profiles, strategy_discoveries).

Ligação à base: env SUPABASE_DB_URL (connection string Postgres de um role
DEDICADO — NÃO a service_role). Nenhum segredo é escrito em código.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg  # psycopg v3

import model_router
import copy_engine

# Estágios terminais: já não "arrefecem".
ESTAGIOS_TERMINAIS = {"Cliente", "Perdido"}
# Horas sem movimento a partir das quais um contacto está "a arrefecer".
# .strip() or "<default>" porque os.environ.get(chave, default) só devolve o
# default quando a chave NÃO EXISTE — se existir mas estiver vazia (""), o
# get devolve "" e o float("") seguinte rebentava o contentor.
HORAS_ARREFECER = float(os.environ.get("COORD_HORAS_ARREFECER", "").strip() or "24")
# Máximo de copies geradas por corrida (protege a quota grátis).
COPY_MAX_POR_CORRIDA = int(os.environ.get("COPY_MAX_POR_CORRIDA", "").strip() or "15")
# Palavra-chave usada para inferir origem Angola (heurística sobre texto livre).
ALVO_ANGOLA = "angola"


def _ligar() -> psycopg.Connection:
    """Abre ligação à base pelo role dedicado (SUPABASE_DB_URL)."""
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url:
        raise RuntimeError("SUPABASE_DB_URL não definido no ambiente.")
    return psycopg.connect(url, connect_timeout=15)


# --------------------------------------------------------------------------- #
# Leitura de dados
# --------------------------------------------------------------------------- #
def ler_metas(cur: psycopg.Cursor) -> dict[str, float]:
    """Devolve {metrica: alvo} apenas para metas ativas."""
    cur.execute("SELECT metrica, alvo FROM prospeccao_metas WHERE ativo = true")
    return {m: float(a) for m, a in cur.fetchall()}


def progresso_por_canal(cur: psycopg.Cursor) -> dict[str, int]:
    """Nº de mensagens ENVIADAS hoje por plataforma (data_envio = hoje, UTC)."""
    cur.execute(
        "SELECT lower(plataforma), count(*) "
        "FROM prospeccao_inbox "
        "WHERE data_envio::date = (now() at time zone 'utc')::date "
        "GROUP BY lower(plataforma)"
    )
    return {p: int(n) for p, n in cur.fetchall()}


def percentagem_angola(cur: psycopg.Cursor) -> tuple[int, int]:
    """
    (nº Angola hoje, total enviado hoje). Angola é inferido por texto livre
    em origem/notas/porque_alvo (heurística — ajustar se houver coluna própria).
    """
    cur.execute(
        "SELECT "
        "  count(*) FILTER (WHERE lower(coalesce(origem,'') || ' ' || "
        "     coalesce(notas,'') || ' ' || coalesce(porque_alvo,'')) LIKE %s), "
        "  count(*) "
        "FROM prospeccao_inbox "
        "WHERE data_envio::date = (now() at time zone 'utc')::date",
        (f"%{ALVO_ANGOLA}%",),
    )
    ang, total = cur.fetchone()
    return int(ang), int(total)


def funil(cur: psycopg.Cursor) -> dict[str, int]:
    """Distribuição de contactos por estágio."""
    cur.execute(
        "SELECT coalesce(estagio,'(sem estágio)'), count(*) "
        "FROM prospeccao_inbox GROUP BY estagio"
    )
    return {e: int(n) for e, n in cur.fetchall()}


def a_arrefecer(cur: psycopg.Cursor) -> list[dict[str, Any]]:
    """
    Contactos com a 'bola do nosso lado' há mais de HORAS_ARREFECER:
    não terminais, já contactados, sem movimento recente.
    """
    cur.execute(
        "SELECT id_unico, nome, plataforma, estagio, "
        "       coalesce(data_resposta, data_envio) AS ultimo "
        "FROM prospeccao_inbox "
        "WHERE coalesce(estagio,'') NOT IN ('Novo', 'Cliente', 'Perdido') "
        "  AND data_envio IS NOT NULL "
        "  AND coalesce(data_resposta, data_envio) "
        "      < (now() at time zone 'utc') - (%s || ' hours')::interval "
        "ORDER BY ultimo ASC LIMIT 50",
        (str(HORAS_ARREFECER),),
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# --------------------------------------------------------------------------- #
# Cálculo do que falta
# --------------------------------------------------------------------------- #
@dataclass
class ResumoCorrida:
    metas: dict[str, float] = field(default_factory=dict)
    enviadas_por_canal: dict[str, int] = field(default_factory=dict)
    falta_por_canal: dict[str, int] = field(default_factory=dict)
    angola_pct: float = 0.0
    angola_meta: float = 0.0
    angola_ok: Optional[bool] = None   # None => sem dados do dia ainda
    total_dia: int = 0
    copies_geradas: int = 0
    funil: dict[str, int] = field(default_factory=dict)
    a_arrefecer: list[dict[str, Any]] = field(default_factory=list)
    comentario: str = ""

    def para_json(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        # Datas em a_arrefecer para string ISO.
        d["a_arrefecer"] = [
            {k: (v.isoformat() if isinstance(v, datetime) else v)
             for k, v in item.items()}
            for item in self.a_arrefecer
        ]
        return d


def calcular_resumo(cur: psycopg.Cursor) -> ResumoCorrida:
    """Junta leituras e calcula lacunas vs metas."""
    r = ResumoCorrida()
    r.metas = ler_metas(cur)
    r.enviadas_por_canal = progresso_por_canal(cur)
    r.funil = funil(cur)
    r.a_arrefecer = a_arrefecer(cur)

    # Falta por canal: metas do tipo msgs_<canal>_dia.
    for metrica, alvo in r.metas.items():
        m = re.fullmatch(r"msgs_([a-z]+)_dia", metrica)
        if not m:
            continue
        canal = m.group(1)
        feitas = r.enviadas_por_canal.get(canal, 0)
        r.falta_por_canal[canal] = max(0, int(alvo) - feitas)

    # % Angola vs meta angola_pct_min.
    ang, total = percentagem_angola(cur)
    r.total_dia = total
    r.angola_meta = r.metas.get("angola_pct_min", 0.0)
    if total:
        r.angola_pct = round(100.0 * ang / total, 1)
        r.angola_ok = r.angola_pct >= r.angola_meta
    else:
        # Sem envios hoje: não há base para dizer OK. Fica "sem dados" (None).
        r.angola_pct = 0.0
        r.angola_ok = None
    return r


# --------------------------------------------------------------------------- #
# Comentário/decisão via router (best-effort — nunca bloqueia a corrida)
# --------------------------------------------------------------------------- #
def gerar_comentario(r: ResumoCorrida) -> str:
    """Pede ao router uma leitura curta do estado. Falha em silêncio."""
    contexto = {
        "falta_por_canal": r.falta_por_canal,
        "angola_pct": r.angola_pct,
        "angola_meta": r.angola_meta,
        "a_arrefecer": len(r.a_arrefecer),
        "funil": r.funil,
    }
    mensagens = [
        {"role": "system",
         "content": "És o coordenador de prospeção do Hermes. Em 2-3 frases, "
                    "em português, diz a prioridade do dia. Não inventes números."},
        {"role": "user", "content": json.dumps(contexto, ensure_ascii=False)},
    ]
    try:
        return model_router.chat(mensagens, tarefa="coordenador_comentario").strip()
    except Exception as e:  # noqa: BLE001 — comentário é opcional
        return f"(sem comentário do modelo: {e})"


# --------------------------------------------------------------------------- #
# Geração de copy para a fila (DM, na fila, sem mensagem pronta)
# --------------------------------------------------------------------------- #
# Prefixo da nota de revisão — nunca entra na mensagem_pronta, só em notas.
NOTA_REVISAO_NUMERO = "REVER: contém número — confirmar antes de enviar."


def gerar_copies_em_falta(conn: psycopg.Connection) -> int:
    """
    Gera copy para as linhas da INBOX que precisam: accao='DM', estado='Na fila'
    e mensagem_pronta NULL/vazia. Dois sinais pós-geração, tratados de forma
    DIFERENTE de propósito:

    - Marcador de template por preencher (ex.: "[Seu Nome]") NUNCA é legítimo —
      é sempre um defeito. BLOQUEIA: não grava em mensagem_pronta, regista
      tipo='copy_erro' com o id_unico e o texto, e passa ao contacto seguinte.
    - Número/ano no texto não prova um dado inventado sobre o Hermes: pode ser
      um facto verdadeiro sobre o CONTACTO (ex.: "27 fundos desde 2016" do BFA),
      e a regex não distingue os dois casos. NÃO bloqueia — grava sempre em
      mensagem_pronta e só MARCA a linha para revisão humana, acrescentando
      NOTA_REVISAO_NUMERO à coluna `notas` (preservando o que já lá estiver) e
      registando tipo='copy_marcada'. A nota nunca entra na própria mensagem.

    NUNCA envia, nunca muda estado. Best-effort: se uma linha falhar a gerar, salta.
    Devolve o número de copies escritas (marcadas contam; bloqueadas não).
    Limite: COPY_MAX_POR_CORRIDA por corrida.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id_unico, nome, plataforma, porque_alvo, accao, notas "
            "FROM prospeccao_inbox "
            "WHERE accao = 'DM' AND estado = 'Na fila' "
            "  AND (mensagem_pronta IS NULL OR btrim(mensagem_pronta) = '') "
            "ORDER BY created_at ASC NULLS LAST "
            "LIMIT %s",
            (COPY_MAX_POR_CORRIDA,),
        )
        cols = [c.name for c in cur.description]
        pendentes = [dict(zip(cols, row)) for row in cur.fetchall()]

    escritas = 0
    for contacto in pendentes:
        try:
            texto = copy_engine.gerar_copy(contacto)
        except Exception as e:  # noqa: BLE001 — best-effort por linha
            print(f"[copy] falhou para {contacto.get('id_unico')}: {e}")
            continue
        if not texto:
            continue

        # Bloqueante: um marcador de template por preencher nunca é legítimo.
        if copy_engine.contem_marcador_template(texto):
            motivo = (
                "texto contém um marcador de template entre parênteses rectos "
                "(ex.: [Seu Nome]) — nunca legítimo, ao contrário de um número"
            )
            print(f"[copy] erro para {contacto.get('id_unico')}: {motivo}")
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO prospeccao_log (ts, tipo, modelo, detalhe, dados) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (datetime.now(timezone.utc), "copy_erro", None, motivo,
                     json.dumps({"id_unico": contacto.get("id_unico"), "texto": texto},
                                ensure_ascii=False)),
                )
            conn.commit()
            continue

        marcar_revisao = copy_engine.contem_dados_inventados(texto)

        if marcar_revisao:
            notas_antigas = (contacto.get("notas") or "").strip()
            notas_novas = (f"{NOTA_REVISAO_NUMERO} {notas_antigas}".strip()
                           if notas_antigas else NOTA_REVISAO_NUMERO)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE prospeccao_inbox SET mensagem_pronta = %s, notas = %s "
                    "WHERE id_unico = %s AND accao = 'DM' AND estado = 'Na fila' "
                    "  AND (mensagem_pronta IS NULL OR btrim(mensagem_pronta) = '')",
                    (texto, notas_novas, contacto["id_unico"]),
                )
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE prospeccao_inbox SET mensagem_pronta = %s "
                    "WHERE id_unico = %s AND accao = 'DM' AND estado = 'Na fila' "
                    "  AND (mensagem_pronta IS NULL OR btrim(mensagem_pronta) = '')",
                    (texto, contacto["id_unico"]),
                )
        conn.commit()
        escritas += 1

        if marcar_revisao:
            motivo = (
                "texto contém percentagem numérica ou ano — marcado para "
                "revisão humana em notas (pode ser um facto verdadeiro sobre "
                "o contacto; a copy não é bloqueada)"
            )
            print(f"[copy] marcada para revisão: {contacto.get('id_unico')}: {motivo}")
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO prospeccao_log (ts, tipo, modelo, detalhe, dados) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (datetime.now(timezone.utc), "copy_marcada", None, motivo,
                     json.dumps({"id_unico": contacto.get("id_unico"), "motivo": motivo},
                                ensure_ascii=False)),
                )
            conn.commit()
    return escritas


# --------------------------------------------------------------------------- #
# Corrida principal
# --------------------------------------------------------------------------- #
def correr() -> ResumoCorrida:
    """Executa uma corrida completa e regista em prospeccao_log."""
    with _ligar() as conn:
        with conn.cursor() as cur:
            resumo = calcular_resumo(cur)

        # Gera copy para a fila que precisa (DM, na fila, sem mensagem pronta) —
        # PRIMEIRO, para sabermos se houve trabalho novo antes de decidir gastar
        # (ou não) uma chamada ao modelo no comentário abaixo.
        resumo.copies_geradas = gerar_copies_em_falta(conn)

        # Comentário (chamada de rede ao modelo): só vale a pena quando há algo
        # de novo a comentar. Uma corrida sem copy nenhuma gerada e sem nenhuma
        # meta de canal em falta (falta_por_canal vazio — hoje é sempre o caso,
        # com as metas placeholder msgs_*_dia desactivadas) não tem nada de novo
        # para o modelo dizer; gastar uma chamada só para confirmar o óbvio é
        # desperdício. Best-effort continua igual quando HÁ trabalho.
        if resumo.copies_geradas == 0 and not resumo.falta_por_canal:
            resumo.comentario = "(corrida sem trabalho novo — modelo não chamado)"
        else:
            resumo.comentario = gerar_comentario(resumo)

        # Regista a corrida no log.
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO prospeccao_log (ts, tipo, modelo, detalhe, dados) "
                "VALUES (%s, %s, %s, %s, %s)",
                (datetime.now(timezone.utc), "coordenador_run", None,
                 "corrida do coordenador", json.dumps(resumo.para_json(),
                                                      ensure_ascii=False)),
            )
            # Regista quantas copies foram geradas nesta corrida.
            cur.execute(
                "INSERT INTO prospeccao_log (ts, tipo, modelo, detalhe, dados) "
                "VALUES (%s, %s, %s, %s, %s)",
                (datetime.now(timezone.utc), "copy_gerada", None,
                 f"copies geradas nesta corrida: {resumo.copies_geradas}",
                 json.dumps({"copies_geradas": resumo.copies_geradas,
                             "limite": COPY_MAX_POR_CORRIDA}, ensure_ascii=False)),
            )
        conn.commit()
    return resumo


def _imprimir(r: ResumoCorrida) -> None:
    """Resumo legível em stdout (para systemd/journalctl)."""
    if r.angola_ok is None:
        angola_estado = "sem dados ainda"
    else:
        angola_estado = "OK" if r.angola_ok else "ABAIXO"
    print("=== Coordenador Hermes — corrida ===")
    print("Falta por canal:", r.falta_por_canal or "nada (metas cumpridas)")
    print(f"Angola: {r.angola_pct}% (meta {r.angola_meta}%) -> {angola_estado}")
    print("Funil:", r.funil)
    print(f"A arrefecer (>{HORAS_ARREFECER}h): {len(r.a_arrefecer)} contactos")
    print(f"Copies geradas: {r.copies_geradas} (limite {COPY_MAX_POR_CORRIDA})")
    print("Comentário:", r.comentario)


if __name__ == "__main__":
    try:
        _imprimir(correr())
    except Exception as e:  # noqa: BLE001
        # Erros de corrida também vão para o log, sem parar o serviço a meio.
        model_router.registar_log("erro", None, f"coordenador falhou: {e}",
                                   {"onde": "correr"})
        print(f"ERRO na corrida do coordenador: {e}")
        raise
