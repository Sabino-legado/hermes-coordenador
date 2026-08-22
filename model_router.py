"""
model_router.py — Camada de fallback automático de modelo do coordenador Hermes.

Ordem FIXA (do grátis ao caro):
    1. Groq       (GPT-OSS 120B)    env GROQ_API_KEY
    2. Cerebras   (GPT-OSS 120B)    env CEREBRAS_API_KEY
    3. Gemini     (3.6 Flash)       env GEMINI_API_KEY
    4. DeepSeek   (V3.2)            env DEEPSEEK_API_KEY   (só se todos os grátis falharem)
    5. Claude/Anthropic             env ANTHROPIC_API_KEY  (PROIBIDO por omissão;
                                    só se ALLOW_CLAUDE=1)

Regras:
    - Interface única: chat(mensagens, tarefa) -> texto.
    - Em 429 / quota / timeout / falha, passa AUTOMATICAMENTE ao provedor seguinte.
    - Provedor sem env key -> salta em silêncio (não é erro, não gera log).
    - Cada troca de provedor grava uma linha em prospeccao_log
      (tipo='modelo_troca', modelo=novo, detalhe=motivo).
    - Se TODOS falharem: levanta TodosProvedoresFalharam e regista tipo='erro'.

NUNCA há chaves/segredos no código: tudo é lido de variáveis de ambiente POR NOME.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

# Tempo (s) máximo por pedido HTTP e pausa curta entre tentativas.
# .strip() or "<default>" porque os.environ.get(chave, default) só devolve o
# default quando a chave NÃO EXISTE — se existir mas estiver vazia (""), o
# get devolve "" e o float("") seguinte rebenta o contentor.
TIMEOUT_S = float(os.environ.get("ROUTER_TIMEOUT_S", "").strip() or "30")
BACKOFF_S = float(os.environ.get("ROUTER_BACKOFF_S", "").strip() or "1.0")


# --------------------------------------------------------------------------- #
# Exceções
# --------------------------------------------------------------------------- #
class ErroProvedor(Exception):
    """Falha genérica (rede, 5xx, resposta inválida) — deve tentar o seguinte."""


class RateLimitProvedor(ErroProvedor):
    """HTTP 429 ou quota esgotada — deve tentar o seguinte."""


class TodosProvedoresFalharam(Exception):
    """Nenhum provedor disponível conseguiu responder."""


# --------------------------------------------------------------------------- #
# Definição dos provedores (endpoints compatíveis com OpenAI, exceto Claude)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Provedor:
    nome: str
    env_key: str          # NOME da variável de ambiente com a chave
    modelo: str
    endpoint: str
    estilo: str = "openai"          # 'openai' | 'anthropic'
    protegido: bool = False          # True => só corre com ALLOW_CLAUDE=1

    def tem_chave(self) -> bool:
        """Só está disponível se a env var existir e não estiver vazia."""
        return bool(os.environ.get(self.env_key, "").strip())


# Ordem é significativa: do grátis ao caro.
PROVEDORES: list[Provedor] = [
    Provedor("Groq", "GROQ_API_KEY", "openai/gpt-oss-120b",
             "https://api.groq.com/openai/v1/chat/completions"),
    Provedor("Cerebras", "CEREBRAS_API_KEY", "gpt-oss-120b",
             "https://api.cerebras.ai/v1/chat/completions"),
    Provedor("Gemini", "GEMINI_API_KEY", "gemini-3.6-flash",
             "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
    Provedor("DeepSeek", "DEEPSEEK_API_KEY", "deepseek-chat",
             "https://api.deepseek.com/v1/chat/completions"),
    # Claude fica sempre em último e só corre com ALLOW_CLAUDE=1.
    Provedor("Claude", "ANTHROPIC_API_KEY", "claude-sonnet-5",
             "https://api.anthropic.com/v1/messages",
             estilo="anthropic", protegido=True),
]


def _claude_permitido() -> bool:
    return os.environ.get("ALLOW_CLAUDE", "").strip() == "1"


# --------------------------------------------------------------------------- #
# Registo em prospeccao_log (pode ser monkeypatched nos testes)
# --------------------------------------------------------------------------- #
def registar_log(tipo: str, modelo: Optional[str], detalhe: str,
                 dados: Optional[dict] = None) -> None:
    """
    Insere uma linha em prospeccao_log. Nunca deixa o router rebentar:
    se a base não estiver acessível, apenas avisa em stderr.

    Ligação por env SUPABASE_DB_URL (role dedicado, NÃO service_role).
    """
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url:
        # Sem base configurada: não falha, apenas informa.
        print(f"[log:{tipo}] modelo={modelo} :: {detalhe}")
        return
    try:
        import psycopg  # psycopg v3
        with psycopg.connect(url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO prospeccao_log (ts, tipo, modelo, detalhe, dados) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (datetime.now(timezone.utc), tipo, modelo, detalhe,
                     json.dumps(dados or {})),
                )
            conn.commit()
    except Exception as e:  # noqa: BLE001 — logar nunca deve parar o router
        print(f"[log:ERRO] não gravou ({e}) :: tipo={tipo} modelo={modelo} {detalhe}")


# --------------------------------------------------------------------------- #
# Execução HTTP (isolada para ser facilmente mockada nos testes)
# --------------------------------------------------------------------------- #
def _executar_http(prov: Provedor, mensagens: list[dict], timeout: float) -> str:
    """
    Faz o pedido real ao provedor e devolve o texto da resposta.
    Levanta RateLimitProvedor em 429/quota e ErroProvedor no resto.
    A chave é lida aqui, no momento do uso, a partir da env var por nome.
    """
    api_key = os.environ[prov.env_key]  # garantido por tem_chave()

    try:
        if prov.estilo == "anthropic":
            resp = requests.post(
                prov.endpoint,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": prov.modelo, "max_tokens": 1024, "messages": mensagens},
                timeout=timeout,
            )
        else:  # openai-compatível
            resp = requests.post(
                prov.endpoint,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": prov.modelo, "messages": mensagens},
                timeout=timeout,
            )
    except requests.Timeout as e:
        raise ErroProvedor(f"timeout: {e}") from e
    except requests.RequestException as e:
        raise ErroProvedor(f"rede: {e}") from e

    if resp.status_code == 429:
        raise RateLimitProvedor("HTTP 429 (rate limit)")
    if resp.status_code >= 400:
        # Quota costuma vir como 402/403 com 'quota' no corpo.
        corpo = (resp.text or "").lower()
        if "quota" in corpo or "insufficient" in corpo:
            raise RateLimitProvedor(f"quota HTTP {resp.status_code}")
        raise ErroProvedor(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
        if prov.estilo == "anthropic":
            return data["content"][0]["text"]
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise ErroProvedor(f"resposta inválida: {e}") from e


# --------------------------------------------------------------------------- #
# Interface pública
# --------------------------------------------------------------------------- #
def chat(mensagens: list[dict], tarefa: str = "geral",
         timeout: float = TIMEOUT_S, backoff: float = BACKOFF_S) -> str:
    """
    Envia `mensagens` (formato [{'role':..., 'content':...}]) ao primeiro
    provedor disponível; em falha, desce a cadeia automaticamente.

    Devolve o texto da resposta do primeiro provedor que responder.
    Levanta TodosProvedoresFalharam se nenhum conseguir.
    """
    ultimo_erro: str = "sem provedores disponíveis"
    ja_tentou = False

    for prov in PROVEDORES:
        # Claude é proibido por omissão.
        if prov.protegido and not _claude_permitido():
            continue
        # Sem chave => salta em silêncio (não é erro, não gera log).
        if not prov.tem_chave():
            continue

        # A partir da 2.ª tentativa real, cada mudança é uma "troca".
        if ja_tentou:
            registar_log(
                "modelo_troca", prov.modelo,
                f"troca para {prov.nome} ({tarefa}): {ultimo_erro}",
                {"provedor": prov.nome, "tarefa": tarefa, "motivo": ultimo_erro},
            )
        ja_tentou = True

        try:
            return _executar_http(prov, mensagens, timeout)
        except RateLimitProvedor as e:
            ultimo_erro = f"{prov.nome}: {e}"
        except ErroProvedor as e:
            ultimo_erro = f"{prov.nome}: {e}"
        # Backoff curto antes do próximo provedor.
        time.sleep(backoff)

    registar_log("erro", None, f"todos os provedores falharam ({tarefa}): {ultimo_erro}",
                 {"tarefa": tarefa, "ultimo_erro": ultimo_erro})
    raise TodosProvedoresFalharam(ultimo_erro)


if __name__ == "__main__":
    # Execução manual mínima (requer pelo menos uma env key configurada).
    try:
        print(chat([{"role": "user", "content": "Responde só 'ok'."}], tarefa="teste"))
    except TodosProvedoresFalharam as e:
        print(f"Nenhum provedor respondeu: {e}")
