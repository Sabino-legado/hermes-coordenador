# Dockerfile — coordenador Hermes para Coolify (contentor de longa duração).
FROM python:3.11-slim

# Boa prática: não escrever .pyc, output sem buffer (logs em tempo real).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências primeiro (melhor cache de camadas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código.
COPY model_router.py coordinator.py copy_engine.py entrypoint.py ./

# Corre como utilizador sem privilégios.
RUN useradd -r -u 10001 hermes
USER hermes

# Modo por omissão: loop interno a cada 30 min (sem systemd).
# As chaves vêm das variáveis de ambiente do Coolify — NUNCA da imagem.
ENV RUN_MODE=loop \
    INTERVALO_MIN=30

# V-F22: sem isto o Coolify mostrava "Running (unknown)" mesmo com o
# processo travado — nenhum sinal externo distinguia "loop vivo" de
# "contentor pendurado". entrypoint.py::_uma_corrida toca /tmp/heartbeat no
# fim de CADA ciclo (sucesso OU falha contida) — este comando falha se o
# ficheiro não existir ou for mais velho que 2×INTERVALO_MIN + 5 min de
# folga (65 min com o INTERVALO_MIN=30 por omissão). stdlib só, sem
# dependência nova. --start-period dá tempo à 1ª corrida (rede + modelo)
# antes de o healthcheck poder falhar a sério.
HEALTHCHECK --interval=300s --timeout=10s --start-period=180s --retries=3 \
  CMD python -c "import os,sys,time; c='/tmp/heartbeat'; i=float(os.environ.get('INTERVALO_MIN','').strip() or '30'); sys.exit(0 if os.path.exists(c) and (time.time()-os.path.getmtime(c))<(i*2+5)*60 else 1)"

CMD ["python", "entrypoint.py"]
