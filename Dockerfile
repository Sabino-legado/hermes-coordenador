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

CMD ["python", "entrypoint.py"]
