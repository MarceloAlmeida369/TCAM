# Use a imagem base do Streamlit que já inclui Python e otimizações
FROM python:3.9-slim-buster # Você pode tentar python:3.10-slim-buster ou python:3.11-slim-buster

# Define o diretório de trabalho
WORKDIR /app

# Instala as dependências de sistema necessárias para Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    libwoff1 \
    libharfbuzz-icu \
    libwebp6 \
    libgl1 \
    libgbm1 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libfontconfig1 \
    libfreetype6 \
    libxshmfence-dev \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copia o arquivo requirements.txt para o contêiner
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala os navegadores do Playwright. ESTE É O PASSO CRÍTICO.
# Usamos o comando "playwright install" aqui.
RUN playwright install chromium

# Copia o restante do código da sua aplicação
COPY . .

# Expõe a porta que o Streamlit usa
EXPOSE 8501

# Define o comando para rodar sua aplicação Streamlit
ENTRYPOINT ["streamlit", "run", "set_pagina_tcam.py", "--server.port=8501", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]