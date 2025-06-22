import streamlit as st
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import subprocess
import sys
import os

# --- Bloco de Verificação e Instalação do Playwright (NOVO) ---
# Este bloco tenta garantir que os navegadores Playwright estejam instalados.
# Ele será executado no início, antes de st.set_page_config.
# Use um arquivo temporário para marcar se a instalação já foi tentada.

PLAYWRIGHT_INSTALLED_FLAG = ".playwright_installed"

if not os.path.exists(PLAYWRIGHT_INSTALLED_FLAG):
    try:
        # Tenta executar o comando de instalação do Playwright
        # capture_output=True para não imprimir diretamente na saída padrão do Streamlit
        # text=True para decodificar a saída como texto
        # check=True para levantar uma exceção em caso de erro
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8' # Adicionado encoding para lidar com caracteres especiais
        )
        # Se a instalação for bem-sucedida, cria o arquivo de flag
        with open(PLAYWRIGHT_INSTALLED_FLAG, "w") as f:
            f.write("ok")
        print(f"Playwright install stdout: {result.stdout}") # Print para logs
        print(f"Playwright install stderr: {result.stderr}") # Print para logs
        print("Playwright Chromium instalado com sucesso via subprocess.")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao instalar Playwright Chromium via subprocess: {e.stderr}")
        # Considerar st.error aqui pode causar StreamlitAPIException se for antes de set_page_config
        # Por isso, apenas printamos para os logs.
    except Exception as e:
        print(f"Erro inesperado durante a instalação do Playwright: {e}")
        # A mesma consideração de st.error.
# --- Fim do Bloco de Verificação e Instalação do Playwright ---


# st.set_page_config deve ser a PRIMEIRA chamada Streamlit no seu script!
st.set_page_config(layout="wide")

# Resto do seu código permanece o mesmo...

# --- Funções para Auxílio ---

def obter_data_util_para_consulta(hoje=None):
    """
    Retorna a data útil para consulta, considerando fins de semana e segundas-feiras.
    """
    if hoje is None:
        hoje = datetime.today()
    dia_semana = hoje.weekday()
    if dia_semana == 0:  # Segunda-feira
        data_consulta = hoje - timedelta(days=3)
    elif dia_semana in [5, 6]:  # Sábado ou Domingo
        dias_para_voltar = dia_semana - 4
        data_consulta = hoje - timedelta(days=dias_para_voltar)
    else:  # Dias de semana normais
        data_consulta = hoje - timedelta(days=1)
    return data_consulta.strftime("%d/%m/%Y")

# --- Funções para Extração de Dados (Usando Playwright) ---

def extrair_dados_b3_playwright(data_desejada):
    """
    Extrai taxas praticadas, volume contratado e valores liquidados da B3 para uma data específica
    usando Playwright para lidar com JavaScript.
    Retorna (df_tcam, df_volume, df_liquido) ou (None, None, None) se não houver dados.
    """
    url_base = "https://sistemaswebb3-clearing.b3.com.br/historicalForeignExchangePage/retroactive"
    
    df_tcam = None
    df_volume = None
    df_liquido = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # Executa em modo headless
            page = browser.new_page()
            page.set_default_timeout(60000) # Aumenta o timeout para 60 segundos
            
            # Navegando para B3 Câmbio Histórico
            page.goto(url_base, wait_until="domcontentloaded")

            # Preencher o campo de data
            page.fill('input[name="initialDate"]', data_desejada)
            
            # Clicar no botão de busca
            page.click('button:has-text("Buscar")')

            # Esperar a tabela carregar.
            try:
                page.wait_for_selector("table#ratesTable", timeout=30000) # Espera a tabela TCAM aparecer
            except Exception as e:
                # Aviso interno (não exibido via st.warning aqui para evitar StreamlitAPIException)
                browser.close()
                return None, None, None

            # Obter o HTML da página após o JavaScript ter carregado o conteúdo
            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            # Verificar a mensagem de "Não há registro"
            if soup.find("div", string=lambda text: text and "Não há registro" in text):
                st.warning(f"⚠️ Não há registro de dados da B3 para a data **{data_desejada}**.")
                browser.close()
                return None, None, None

            # Extrair Taxas Praticadas (TCAM)
            tabela_tcam = soup.find("table", {"id": "ratesTable"})
            if tabela_tcam:
                linhas_tcam = tabela_tcam.find_all("tr")
                if linhas_tcam:
                    dados_tcam_str = []
                    start_row = 0
                    if linhas_tcam and linhas_tcam[0].find('th'):
                        start_row = 1
                    
                    for linha in linhas_tcam[start_row:]:
                        cols = [td.text.strip() for td in linha.find_all("td")]
                        if cols and len(cols) == 8:
                            dados_tcam_str.append(cols)

                    if dados_tcam_str:
                        colunas_tcam = ["Data", "Fechamento", "Min Balcão", "Média Balcão", "Máx Balcão", "Min Pregão", "Média Pregão", "Máx Pregão"]
                        df_tcam = pd.DataFrame(dados_tcam_str, columns=colunas_tcam)
                        df_tcam["Data"] = pd.to_datetime(df_tcam["Data"], dayfirst=True).dt.date
                        
                        for col in ["Fechamento", "Min Balcão", "Média Balcão", "Máx Balcão"]:
                            df_tcam[col] = df_tcam[col].apply(tratar_valor_tcam_original)
                        
                        df_tcam = df_tcam.drop(columns=["Min Pregão", "Média Pregão", "Máx Pregão"]).rename(columns={
                            "Min Balcão": "Mínima", "Média Balcão": "Média", "Máx Balcão": "Máxima"
                        })
            
            # Extrair Volume Contratado
            tabela_volume = soup.find("table", {"id": "contractedVolume"})
            df_volume = pd.DataFrame() 
            if tabela_volume:
                linhas_volume = tabela_volume.find_all("tr")
                if linhas_volume:
                    dados_volume = []
                    start_row = 0
                    if linhas_volume and linhas_volume[0].find('th'):
                        start_row = 1
                    
                    for linha in linhas_volume[start_row:]:
                        cols = [td.text.strip() for td in linha.find_all("td")]
                        if cols:
                            dados_volume.append(cols)

                    tfoot_volume = tabela_volume.find("tfoot")
                    if tfoot_volume:
                        total_row_ths = tfoot_volume.find_all("th")
                        if total_row_ths:
                            total_data = [th.text.strip() for th in total_row_ths]
                            if total_data: 
                                dados_volume.append(total_data)

                    if dados_volume:
                        colunas_volume = ["Data", "US$ Balcão", "R$ Balcão", "Negócios Balcão", "US$ Pregão", "R$ Pregão", "Negócios Pregão", "US$ Total", "R$ Total", "Negócios Total"]
                        if dados_volume and len(dados_volume[0]) == len(colunas_volume):
                            df_volume = pd.DataFrame(dados_volume, columns=colunas_volume)
            
            # Extrair Valores Liquidados
            tabela_liquido = soup.find("table", {"id": "nettingTable"})
            df_liquido = pd.DataFrame() 
            if tabela_liquido:
                linhas_liquido = tabela_liquido.find_all("tr")
                if linhas_liquido:
                    dados_liquido = []
                    start_row = 0
                    if linhas_liquido and linhas_liquido[0].find('th'):
                        start_row = 1
                    
                    for linha in linhas_liquido[start_row:]:
                        cols = [td.text.strip() for td in linha.find_all("td")]
                        if cols:
                            dados_liquido.append(cols)

                    if dados_liquido:
                        df_liquido = pd.DataFrame(dados_liquido, columns=["Data", "US$", "R$"])
            
            browser.close()
            
            if df_tcam is None or df_tcam.empty:
                return None, None, None

            return df_tcam, df_volume, df_liquido

    except Exception as e:
        st.error(f"❌ Erro ao extrair dados da B3 para {data_desejada} com Playwright: {e}")
        return None, None, None


def extrair_frp0_playwright():
    """Extrai dados do FRP0 (Forward Points) da BMF usando Playwright."""
    url_frp = (
        "https://www2.bmf.com.br/pages/portal/bmfbovespa/boletim1/"
        "SistemaPregao1.asp?pagetype=pop&caminho=Resumo%20Estat%EDstico%20-%20Sistema%20Preg%E3o"
        "&Data=&Mercadoria=FRP"
    )
    df_frp = pd.DataFrame()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            
            # Navegando para BMF FRP0
            page.goto(url_frp, wait_until="domcontentloaded")
            
            try:
                page.wait_for_selector("#MercadoFut2", timeout=15000)
            except Exception as e:
                browser.close()
                return pd.DataFrame()

            content = page.content()
            soup_frp = BeautifulSoup(content, "html.parser")
            
            mercado2 = soup_frp.find(id="MercadoFut2")
            if not mercado2:
                browser.close()
                return pd.DataFrame()
                
            frp2_tbl = mercado2.find("table", class_="tabConteudo")
            if not frp2_tbl:
                browser.close()
                return pd.DataFrame()

            rows = frp2_tbl.find_all("tr")

            if len(rows) >= 3:
                frp0_td = rows[2].find_all("td")
                if frp0_td:
                    valores = [td.get_text(strip=True) for td in frp0_td]
                    colunas = [
                        "Abertura", "Mínimo", "Máximo", "Médio",
                        "Último Preço", "Últ. Of. Compra", "Últ. Of. Venda"
                    ]
                    if len(valores) == len(colunas):
                        df_frp = pd.DataFrame([valores], columns=colunas)
            
            browser.close()
            return df_frp
    except Exception as e:
        st.error(f"❌ Erro ao extrair dados do FRP0 com Playwright: {e}")
        return pd.DataFrame()

def extrair_dif_oper_casada_playwright():
    """
    Extrai o indicador 'DIF OPER CASADA - COMPRA' usando Playwright.
    """
    url = "https://sistemaswebb3-derivativos.b3.com.br/financialIndicatorsPage/?language=pt-br"
    valor = None
    data_atualizacao = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            
            # Navegando para B3 Indicadores Financeiros
            page.goto(url, wait_until="domcontentloaded")
            
            try:
                page.wait_for_selector("p:has-text('DIF OPER CASADA - COMPRA')", timeout=20000)
            except Exception as e:
                browser.close()
                return None, None

            content = page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            bloco = soup.find("p", string=lambda text: text and "DIF OPER CASADA - COMPRA" in text)

            if bloco:
                div_mae = bloco.find_parent("div")
                if div_mae:
                    valor_tag = div_mae.find("h4")
                    data_tag = div_mae.find("small")
                    if valor_tag and data_tag:
                        valor = valor_tag.text.strip()
                        data_atualizacao = data_tag.text.strip()
            
            browser.close()
            return valor, data_atualizacao
    except Exception as e:
        st.error(f"❌ Erro ao extrair DIF OPER CASADA com Playwright: {e}")
        return None, None

# --- Funções de Formatação ---

def tratar_valor_tcam_original(valor_str):
    """
    Trata string de valor TCAM conforme a lógica original do código para conversão.
    Assume que a última casa é decimal.
    """
    valor_limpo = ''.join(filter(str.isdigit, valor_str))
    if valor_limpo:
        if len(valor_limpo) >= 2:
            return float(valor_limpo[:-1] + '.' + valor_limpo[-1])
        else:
            return float("0." + valor_limpo) if valor_limpo else 0.0
    return 0.0

def tratar_valor_frp0_dif_original(valor_str):
    """
    Trata strings de valor FRP0 e DIF OPER CASADA.
    Substitui vírgula por ponto para permitir a conversão para float.
    """
    try:
        return float(valor_str.replace(",", "."))
    except ValueError:
        return 0.0

def somar_formatar_original(tcam_val, outro_val):
    """
    Soma um valor TCAM (já como float) com outro valor (já como float)
    e formata o resultado no padrão brasileiro (vírgula como decimal), com uma casa decimal.
    """
    resultado = tcam_val + outro_val
    return f"{resultado:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_tcam_original_exibicao(valor):
    """
    Formata um valor float TCAM no padrão brasileiro (vírgula como decimal), com uma casa decimal.
    Isso é para a exibição na tabela, diferente do tratamento para cálculo.
    """
    return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- Streamlit App ---

# st.set_page_config deve ser a PRIMEIRA chamada Streamlit no seu script!
st.set_page_config(layout="wide")

aba = st.tabs(["🏠 PRINCIPAL", "📊 DADOS BRUTOS", "🔗 LINKS"])

# Obter datas para as consultas
hoje = datetime.today()
data_base_obj = datetime.strptime(obter_data_util_para_consulta(hoje), "%d/%m/%Y").date()

data_tcam1_str = data_base_obj.strftime("%d/%m/%Y")
data_tcam2_str = (data_base_obj - timedelta(days=1)).strftime("%d/%m/%Y")
data_tcam3_str = (data_base_obj - timedelta(days=2)).strftime("%d/%m/%Y")


dados_tcam = {}
dados_volume = {}
dados_liquido = {}
frp0_data = {}
dif_oper_data = {}

with st.spinner("Carregando dados... Isso pode levar alguns segundos devido à extração web (com Playwright)."):
    
    # --- Extração para TCAM 01 (data útil padrão) ---
    df_tcam1, df_volume1, df_liquido1 = extrair_dados_b3_playwright(data_tcam1_str)
    if df_tcam1 is not None and not df_tcam1.empty:
        dados_tcam[data_tcam1_str] = df_tcam1
        dados_volume[data_tcam1_str] = df_volume1
        dados_liquido[data_tcam1_str] = df_liquido1
    else:
        st.warning(f"Não foi possível obter dados de TCAM para {data_tcam1_str}.")
    
    # --- Extração para TCAM 02 (data útil - 1) ---
    df_tcam2, df_volume2, df_liquido2 = extrair_dados_b3_playwright(data_tcam2_str)
    if df_tcam2 is not None and not df_tcam2.empty:
        dados_tcam[data_tcam2_str] = df_tcam2
        dados_volume[data_tcam2_str] = df_volume2
        dados_liquido[data_tcam2_str] = df_liquido2
    else:
        st.warning(f"Não foi possível obter dados de TCAM para {data_tcam2_str}.")

    # --- Extração para TCAM 03 (data útil - 2) ---
    df_tcam3, df_volume3, df_liquido3 = extrair_dados_b3_playwright(data_tcam3_str)
    if df_tcam3 is not None and not df_tcam3.empty:
        dados_tcam[data_tcam3_str] = df_tcam3
        dados_volume[data_tcam3_str] = df_volume3
        dados_liquido[data_tcam3_str] = df_liquido3
    else:
        st.warning(f"Não foi possível obter dados de TCAM para {data_tcam3_str}.")

    # --- Extração de FRP0 (apenas para a data TCAM 01) ---
    df_frp_extracted = extrair_frp0_playwright()
    if not df_frp_extracted.empty:
        frp0_data = {
            "ultimo_preco_str": df_frp_extracted["Último Preço"].iloc[0],
            "ultimo_preco_float": tratar_valor_frp0_dif_original(df_frp_extracted["Último Preço"].iloc[0])
        }
    else:
        frp0_data = {"ultimo_preco_str": "N/A", "ultimo_preco_float": 0.0}
        st.error("❌ Não foi possível extrair os dados do FRP0. Verifique as mensagens de erro/aviso acima.")

    # --- Extração de DIF OPER CASADA (apenas para a data TCAM 01) ---
    dif_valor_raw, dif_data = extrair_dif_oper_casada_playwright()
    if dif_valor_raw:
        dif_oper_data = {
            "valor_str": dif_valor_raw.split()[0],
            "valor_float": tratar_valor_frp0_dif_original(dif_valor_raw.split()[0]),
            "data_atualizacao": dif_data
        }
    else:
        dif_oper_data = {"valor_str": "N/A", "valor_float": 0.0, "data_atualizacao": "N/A"}
        st.error("❌ Indicador 'DIF OPER CASADA - COMPRA' não disponível ou não pôde ser extraído. Veja a mensagem de informação acima.")


# --- Funções para exibir tabela de TCAM + Indicadores ---
def exibir_tcam_com_indicadores(label, df_tcam, frp0_data, dif_oper_data):
    st.subheader(f"📌 {label}")
    if df_tcam is not None and not df_tcam.empty:
        if "Fechamento" in df_tcam.columns and "Mínima" in df_tcam.columns and \
           "Média" in df_tcam.columns and "Máxima" in df_tcam.columns:
            fechamento_tcam = df_tcam["Fechamento"].iloc[0]
            minimo_tcam = df_tcam["Mínima"].iloc[0]
            media_tcam = df_tcam["Média"].iloc[0]
            maximo_tcam = df_tcam["Máxima"].iloc[0]
        else:
            st.error(f"Erro: Colunas esperadas (Fechamento, Mínima, Média, Máxima) não encontradas no DataFrame TCAM para {label}.")
            st.dataframe(df_tcam)
            st.markdown("---")
            return

        st.markdown(f"**TCAM {label.split(' ')[1]} + FRP0**")
        df_resultado_frp = pd.DataFrame({
            "Indicador": ["Fechamento", "Mínimo", "Média", "Máximo"],
            "TCAM (Balcão)": [
                formatar_tcam_original_exibicao(fechamento_tcam),
                formatar_tcam_original_exibicao(minimo_tcam),
                formatar_tcam_original_exibicao(media_tcam),
                formatar_tcam_original_exibicao(maximo_tcam)
            ],
            "FRP0 (Último Preço)": [frp0_data["ultimo_preco_str"]] * 4,
            "Soma (TCAM + FRP0)": [
                somar_formatar_original(fechamento_tcam, frp0_data["ultimo_preco_float"]),
                somar_formatar_original(minimo_tcam, frp0_data["ultimo_preco_float"]),
                somar_formatar_original(media_tcam, frp0_data["ultimo_preco_float"]),
                somar_formatar_original(maximo_tcam, frp0_data["ultimo_preco_float"])
            ]
        })
        st.dataframe(df_resultado_frp, use_container_width=True, hide_index=True)
        st.markdown("---")

        st.markdown(f"**TCAM {label.split(' ')[1]} + DIF OPER CASADA**")
        df_resultado_dif = pd.DataFrame({
            "Indicador": ["Fechamento", "Mínimo", "Média", "Máximo"],
            "TCAM (Balcão)": [
                formatar_tcam_original_exibicao(fechamento_tcam),
                formatar_tcam_original_exibicao(minimo_tcam),
                formatar_tcam_original_exibicao(media_tcam),
                formatar_tcam_original_exibicao(maximo_tcam)
            ],
            "DIF OPER CASADA (Compra)": [dif_oper_data["valor_str"]] * 4,
            "Soma (TCAM + DIF)": [
                somar_formatar_original(fechamento_tcam, dif_oper_data["valor_float"]),
                somar_formatar_original(minimo_tcam, dif_oper_data["valor_float"]),
                somar_formatar_original(media_tcam, dif_oper_data["valor_float"]),
                somar_formatar_original(maximo_tcam, dif_oper_data["valor_float"])
            ]
        })
        st.dataframe(df_resultado_dif, use_container_width=True, hide_index=True)
        st.markdown("---")
    else:
        data_do_label = label.split('(')[1].replace(')', '') 
        st.warning(f"⚠️ Não há dados de TCAM para a data **{data_do_label}** ou a extração falhou.")
        st.markdown("---")


# --- Aba PRINCIPAL ---
with aba[0]:
    st.title("📈 Painel B3 - TCAMs Calculadas")
    st.success(f"Dados calculados com base na data útil principal: **{data_tcam1_str}**")
    st.markdown(f"Com a data vigente sendo **{data_tcam1_str}**:")
    st.markdown("---") 

    exibir_tcam_com_indicadores(f"TCAM 01 ({data_tcam1_str})", dados_tcam.get(data_tcam1_str), frp0_data, dif_oper_data)
    exibir_tcam_com_indicadores(f"TCAM 02 ({data_tcam2_str})", dados_tcam.get(data_tcam2_str), frp0_data, dif_oper_data)
    exibir_tcam_com_indicadores(f"TCAM 03 ({data_tcam3_str})", dados_tcam.get(data_tcam3_str), frp0_data, dif_oper_data)

# --- Aba DADOS BRUTOS ---
with aba[1]:
    st.title("📊 Dados Brutos - B3")
    st.success(f"Dados brutos da B3 para as datas consultadas.")
    st.markdown("---")

    # TCAM 01
    st.subheader(f"Dados Brutos - TCAM 01 ({data_tcam1_str})")
    if data_tcam1_str in dados_tcam and dados_tcam[data_tcam1_str] is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Taxas Praticadas (TCAM)**")
            st.dataframe(dados_tcam[data_tcam1_str], use_container_width=True)
        with col2:
            st.markdown("**Valores Liquidados**")
            st.dataframe(dados_liquido.get(data_tcam1_str, pd.DataFrame()), use_container_width=True)
        st.markdown("**Volume Contratado**")
        st.dataframe(dados_volume.get(data_tcam1_str, pd.DataFrame()), use_container_width=True)
    else:
        st.info(f"Não há dados brutos para TCAM 01 ({data_tcam1_str}) ou a extração falhou.")
    st.markdown("---")

    # TCAM 02
    st.subheader(f"Dados Brutos - TCAM 02 ({data_tcam2_str})")
    if data_tcam2_str in dados_tcam and dados_tcam[data_tcam2_str] is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Taxas Praticadas (TCAM)**")
            st.dataframe(dados_tcam[data_tcam2_str], use_container_width=True)
        with col2:
            st.markdown("**Valores Liquidados**")
            st.dataframe(dados_liquido.get(data_tcam2_str, pd.DataFrame()), use_container_width=True)
        st.markdown("**Volume Contratado**")
        st.dataframe(dados_volume.get(data_tcam2_str, pd.DataFrame()), use_container_width=True)
    else:
        st.info(f"Não há dados brutos para TCAM 02 ({data_tcam2_str}) ou a extração falhou.")
    st.markdown("---")

    # TCAM 03
    st.subheader(f"Dados Brutos - TCAM 03 ({data_tcam3_str})")
    if data_tcam3_str in dados_tcam and dados_tcam[data_tcam3_str] is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Taxas Praticadas (TCAM)**")
            st.dataframe(dados_tcam[data_tcam3_str], use_container_width=True)
        with col2:
            st.markdown("**Valores Liquidados**")
            st.dataframe(dados_liquido.get(data_tcam3_str, pd.DataFrame()), use_container_width=True)
        st.markdown("**Volume Contratado**")
        st.dataframe(dados_volume.get(data_tcam3_str, pd.DataFrame()), use_container_width=True)
    else:
        st.info(f"Não há dados brutos para TCAM 03 ({data_tcam3_str}) ou a extração falhou.")
    st.markdown("---")

    # FRP0 e DIF OPER CASADA (continuam únicos para a data principal)
    st.subheader("📊 FRP0 – Contrato de Forward Points (Data Principal)")
    if frp0_data["ultimo_preco_str"] != "N/A":
        st.dataframe(df_frp_extracted, use_container_width=True)
    else:
        st.error("❌ Não foi possível extrair os dados do FRP0. Verifique as mensagens de erro/aviso acima.")

    st.markdown("---")
    st.subheader("📉 DIF OPER CASADA - COMPRA (Data Principal)")
    if dif_oper_data["valor_str"] != "N/A":
        st.metric(label="Valor Atual", value=dif_oper_data["valor_str"], delta=None)
        st.caption(f"Última atualização: {dif_oper_data['data_atualizacao']}")
    else:
        st.error("❌ Indicador 'DIF OPER CASADA - COMPRA' não disponível ou não pôde ser extraído. Veja a mensagem de informação acima.")


# --- Aba LINKS ---
with aba[2]:
    st.title("🔗 Links Úteis")
    st.markdown("---") 
    st.markdown("- [Página da B3 - Câmbio Histórico](https://sistemaswebb3-clearing.b3.com.br/historicalForeignExchangePage/retroactive?language=pt-br)")
    st.markdown("- [Página BMF - Boletim de Câmbio (FRP0)](https://www2.bmf.com.br/pages/portal/bmfbovespa/boletim1/SistemaPregao1.asp?pagetype=pop&caminho=Resumo%20Estat%EDstico%20-%20Sistema%20Preg%E3o&Data=&Mercadoria=FRP)")
    st.markdown("- [Página da B3 - Indicadores Financeiros (DIF OPER CASADA)](https://sistemaswebb3-derivativos.b3.com.br/financialIndicatorsPage/?language=pt-br)")
