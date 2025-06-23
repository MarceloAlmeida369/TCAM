# Use uma imagem base do Python. É bom usar uma versão que você testou localmente.
# python:3.9-slim-buster é geralmente estável. Você pode tentar 3.10 ou 3.11 também.
FROM python:3.9-slim-buster

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Instala as dependências de sistema necessárias para o Playwright no Linux
# Estas são bibliotecas que o Chromium precisa para rodar em um ambiente Linux.
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

# Instala as dependências Python listadas em requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Instala os navegadores do Playwright (especificamente o Chromium).
# Este é o passo crucial que garante que o executável exista no ambiente do Streamlit Cloud.
RUN playwright install chromium

# Copia todos os outros arquivos do seu projeto para o contêiner
COPY . .

# Expõe a porta que o Streamlit usa (padrão é 8501)
EXPOSE 8501

# Define o comando que será executado quando o contêiner iniciar,
# que é o comando para rodar sua aplicação Streamlit.
ENTRYPOINT ["streamlit", "run", "set_pagina_tcam.py", "--server.port=8501", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
