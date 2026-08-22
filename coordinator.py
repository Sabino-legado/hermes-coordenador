"""
coordinator.py — Ciclo do coordenador autónomo de prospeção/vendas do Hermes.

O que faz numa corrida:
    (a) lê prospeccao_inbox, prospeccao_metas e o funil (coluna estagio);
    (b) calcula o progresso do dia por canal vs metas (msgs_*_dia) e a % Angola;
    (c) identifica o que falta para as metas e os contactos que estão a arrefecer;
    (d) usa o model_router para gerar um comentário/decisão curta (best-effort);
    (e) escreve um resumo da corrida em prospeccao_log
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

# Estágios terminais: já não "arrefecem".
ESTAGIOS_TERMINAIS = {"Cliente", "Perdido"}
# Horas sem movimento a partir das quais um contacto está "a arrefecer".
HORAS_ARREFECER = float(os.environ.get("COORD_HORAS_ARREFECER", "24"))
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
    angola_ok: bool = True
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
    r.angola_pct = round(100.0 * ang / total, 1) if total else 0.0
    r.angola_meta = r.metas.get("angola_pct_min", 0.0)
    r.angola_ok = r.angola_pct >= r.angola_meta if total else True
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
# Corrida principal
# --------------------------------------------------------------------------- #
def correr() -> ResumoCorrida:
    """Executa uma corrida completa e regista em prospeccao_log."""
    with _ligar() as conn:
        with conn.cursor() as cur:
            resumo = calcular_resumo(cur)
        # Comentário fora do cursor de leitura (chamada de rede ao modelo).
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
        conn.commit()
    return resumo


def _imprimir(r: ResumoCorrida) -> None:
    """Resumo legível em stdout (para systemd/journalctl)."""
    print("=== Coordenador Hermes — corrida ===")
    print("Falta por canal:", r.falta_por_canal or "nada (metas cumpridas)")
    print(f"Angola: {r.angola_pct}% (meta {r.angola_meta}%) -> "
          f"{'OK' if r.angola_ok else 'ABAIXO'}")
    print("Funil:", r.funil)
    print(f"A arrefecer (>{HORAS_ARREFECER}h): {len(r.a_arrefecer)} contactos")
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
