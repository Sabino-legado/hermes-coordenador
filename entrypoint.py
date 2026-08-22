"""
entrypoint.py — Arranque do coordenador Hermes em contentor (Coolify) ou avulso.

Modos (env RUN_MODE):
    loop  (omissão) — corre correr() a cada INTERVALO_MIN minutos, para sempre.
    once            — corre uma vez e sai (útil com systemd timer ou cron).

Resiliência:
    - Se faltarem chaves/env (ex.: SUPABASE_DB_URL), o contentor NÃO rebenta:
      regista o erro, espera o próximo ciclo e volta a tentar.
    - SIGTERM/SIGINT (stop do Coolify) terminam o loop de forma limpa.
"""
from __future__ import annotations

import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone

import coordinator
import model_router

# Configuração por ambiente (com valores por omissão seguros).
# .strip() or "<default>" porque os.environ.get(chave, default) só devolve o
# default quando a chave NÃO EXISTE — se existir mas estiver vazia (""), o
# get devolve "" e o float("") seguinte rebenta o contentor.
RUN_MODE = (os.environ.get("RUN_MODE", "").strip() or "loop").lower()
INTERVALO_MIN = float(os.environ.get("INTERVALO_MIN", "").strip() or "30")

_a_correr = True


def _parar(signum, _frame):
    """Marca paragem limpa em SIGTERM/SIGINT."""
    global _a_correr
    _a_correr = False
    print(f"[{_agora()}] sinal {signum} recebido — a terminar depois do ciclo.")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uma_corrida() -> None:
    """Uma corrida do coordenador, com todos os erros contidos."""
    try:
        resumo = coordinator.correr()
        coordinator._imprimir(resumo)
    except Exception as e:  # noqa: BLE001 — nunca deixar o contentor cair
        print(f"[{_agora()}] corrida falhou: {e}")
        traceback.print_exc()
        # Best-effort: tenta registar no log (também tolerante a falhas).
        try:
            model_router.registar_log(
                "erro", None, f"entrypoint: corrida falhou: {e}",
                {"run_mode": RUN_MODE},
            )
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    signal.signal(signal.SIGTERM, _parar)
    signal.signal(signal.SIGINT, _parar)

    if RUN_MODE == "once":
        print(f"[{_agora()}] RUN_MODE=once — uma corrida e sai.")
        _uma_corrida()
        return 0

    print(f"[{_agora()}] RUN_MODE=loop — corrida a cada {INTERVALO_MIN} min.")
    while _a_correr:
        _uma_corrida()
        if not _a_correr:
            break
        # Espera o intervalo, mas acorda a cada segundo para responder a sinais.
        restante = INTERVALO_MIN * 60.0
        while _a_correr and restante > 0:
            time.sleep(min(1.0, restante))
            restante -= 1.0
    print(f"[{_agora()}] terminado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
