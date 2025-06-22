import streamlit as st
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time 

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

# --- Funções para Extração de Dados (Usando requests e BeautifulSoup) ---

def extrair_dados_b3(data_desejada):
    """
    Extrai taxas praticadas, volume contratado e valores liquidados da B3 para uma data específica
    usando requests, simulando a submissão do formulário.
    Retorna (df_tcam, df_volume, df_liquido) ou (None, None, None) se não houver dados.
    """
    url_base = "https://sistemaswebb3-clearing.b3.com.br/historicalForeignExchangePage/retroactive"
    
    params = {
        'initialDate': data_desejada,
        'language': 'pt-br'
    }
    
    try:
        # Tenta com uma requisição GET com os parâmetros da data
        response = requests.get(url_base, params=params, timeout=15) # Aumentei o timeout
        response.raise_for_status() # Lança um erro para status HTTP ruins (4xx, 5xx)
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Verificar a mensagem de "Não há registro"
        if soup.find("div", string=lambda text: text and "Não há registro" in text):
            st.warning(f"⚠️ Não há registro de dados da B3 para a data **{data_desejada}**.")
            return None, None, None

        # Extrair Taxas Praticadas (TCAM)
        tabela_tcam = soup.find("table", {"id": "ratesTable"})
        df_tcam = pd.DataFrame()
        if tabela_tcam:
            # Não tentar encontrar tbody se a tabela for diretamente preenchida,
            # ou ser mais flexível para evitar NoneType
            # Algumas tabelas podem não ter <tbody> se o JS as monta diretamente.
            linhas_tcam = tabela_tcam.find_all("tr") # Tenta direto nas TRs da tabela
            if linhas_tcam: # Verifica se encontrou alguma linha
                # Ignora a primeira linha se for cabeçalho
                if linhas_tcam[0].find('th'): # Se a primeira linha tem <th>, é cabeçalho
                    dados_tcam_str = [[td.text.strip() for td in linha.find_all("td")] for linha in linhas_tcam[1:]]
                else:
                    dados_tcam_str = [[td.text.strip() for td in linha.find_all("td")] for linha in linhas_tcam]
                
                # Garante que temos dados antes de criar o DataFrame
                if dados_tcam_str:
                    colunas_tcam = ["Data", "Fechamento", "Min Balcão", "Média Balcão", "Máx Balcão", "Min Pregão", "Média Pregão", "Máx Pregão"]
                    df_tcam = pd.DataFrame(dados_tcam_str, columns=colunas_tcam)
                    df_tcam["Data"] = pd.to_datetime(df_tcam["Data"], dayfirst=True).dt.date
                    
                    for col in ["Fechamento", "Min Balcão", "Média Balcão", "Máx Balcão"]:
                        df_tcam[col] = df_tcam[col].apply(tratar_valor_tcam_original)
                    
                    df_tcam = df_tcam.drop(columns=["Min Pregão", "Média Pregão", "Máx Pregão"]).rename(columns={
                        "Min Balcão": "Mínima", "Média Balcão": "Média", "Máx Balcão": "Máxima"
                    })
                else:
                    st.warning(f"Aviso: Nenhuma linha de dados encontrada na tabela TCAM para {data_desejada}.")
            else:
                st.warning(f"Aviso: Nenhuma linha (<tr>) encontrada na tabela 'ratesTable' para {data_desejada}.")
        else:
            st.warning(f"Aviso: Tabela 'ratesTable' não encontrada para {data_desejada}.")
            return None, None, None # Se a tabela principal não foi encontrada, os outros também não serão.


        # Extrair Volume Contratado
        tabela_volume = soup.find("table", {"id": "contractedVolume"})
        df_volume = pd.DataFrame() 
        if tabela_volume:
            linhas_volume = tabela_volume.find_all("tr")
            if linhas_volume:
                dados_volume = [[td.text.strip() for td in linha.find_all("td")] for linha in linhas_volume if linha.find('td')] # Filtra linhas vazias
                tfoot_volume = tabela_volume.find("tfoot")
                if tfoot_volume:
                    total_row_ths = tfoot_volume.find_all("th")
                    if total_row_ths:
                        total_data = [th.text.strip() for th in total_row_ths]
                        if total_data: # Verifica se a lista não está vazia antes de adicionar
                             dados_volume.append(total_data)

                if dados_volume: # Verifica se a lista não está vazia
                    colunas_volume = ["Data", "US$ Balcão", "R$ Balcão", "Negócios Balcão", "US$ Pregão", "R$ Pregão", "Negócios Pregão", "US$ Total", "R$ Total", "Negócios Total"]
                    # Ajusta o número de colunas do DataFrame se a lista de dados tiver colunas diferentes do cabeçalho
                    if dados_volume and len(dados_volume[0]) == len(colunas_volume):
                        df_volume = pd.DataFrame(dados_volume, columns=colunas_volume)
                    else:
                        st.warning(f"Aviso: Número de colunas inconsistente para Volume Contratado em {data_desejada}. Pode haver erro na extração.")
                        df_volume = pd.DataFrame(dados_volume) # Cria o DF mesmo com colunas diferentes para inspecao
                else:
                    st.warning(f"Aviso: Nenhuma linha de dados encontrada na tabela de Volume Contratado para {data_desejada}.")
            else:
                st.warning(f"Aviso: Nenhuma linha (<tr>) encontrada na tabela 'contractedVolume' para {data_desejada}.")

        # Extrair Valores Liquidados
        tabela_liquido = soup.find("table", {"id": "nettingTable"})
        df_liquido = pd.DataFrame() 
        if tabela_liquido:
            linhas_liquido = tabela_liquido.find_all("tr")
            if linhas_liquido:
                dados_liquido = [[td.text.strip() for td in linha.find_all("td")] for linha in linhas_liquido if linha.find('td')]
                if dados_liquido:
                    df_liquido = pd.DataFrame(dados_liquido, columns=["Data", "US$", "R$"])
                else:
                    st.warning(f"Aviso: Nenhuma linha de dados encontrada na tabela de Valores Liquidados para {data_desejada}.")
            else:
                st.warning(f"Aviso: Nenhuma linha (<tr>) encontrada na tabela 'nettingTable' para {data_desejada}.")

        if df_tcam.empty: # Se a TCAM não foi extraída com sucesso, retorne None para tudo
            return None, None, None

        return df_tcam, df_volume, df_liquido

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de requisição HTTP na B3 para {data_desejada}: {e}. Verifique a URL ou sua conexão.")
        return None, None, None
    except Exception as e:
        st.error(f"❌ Erro inesperado ao extrair dados da B3 para {data_desejada}: {e}. A estrutura da página pode ter mudado.")
        return None, None, None

def extrair_frp0():
    """Extrai dados do FRP0 (Forward Points) da BMF usando requests."""
    url_frp = (
        "https://www2.bmf.com.br/pages/portal/bmfbovespa/boletim1/"
        "SistemaPregao1.asp?pagetype=pop&caminho=Resumo%20Estat%EDstico%20-%20Sistema%20Preg%E3o"
        "&Data=&Mercadoria=FRP"
    )
    try:
        response = requests.get(url_frp, timeout=15) # Aumentei o timeout
        response.raise_for_status()
        soup_frp = BeautifulSoup(response.content, "html.parser")
        
        mercado2 = soup_frp.find(id="MercadoFut2")
        if not mercado2:
            st.error("❌ Erro: Bloco 'MercadoFut2' não encontrado na página do FRP0.")
            return pd.DataFrame()
            
        frp2_tbl = mercado2.find("table", class_="tabConteudo")
        if not frp2_tbl:
            st.error("❌ Erro: Tabela 'tabConteudo' dentro de 'MercadoFut2' não encontrada para FRP0.")
            return pd.DataFrame()

        rows = frp2_tbl.find_all("tr")

        if len(rows) >= 3: # Espera pelo menos 3 linhas (cabeçalho + 2 de dados)
            frp0_td = rows[2].find_all("td") # Assumindo que a 3ª linha (índice 2) é a do FRP0
            if frp0_td:
                valores = [td.get_text(strip=True) for td in frp0_td]
                colunas = [
                    "Abertura", "Mínimo", "Máximo", "Médio",
                    "Último Preço", "Últ. Of. Compra", "Últ. Of. Venda"
                ]
                if len(valores) == len(colunas): # Garante que as colunas batem
                    return pd.DataFrame([valores], columns=colunas)
                else:
                    st.warning(f"Aviso: Número de colunas para FRP0 inconsistente. Dados: {valores}")
                    return pd.DataFrame()
            else:
                st.warning("Aviso: Nenhuma célula de dados encontrada para FRP0 na linha esperada.")
                return pd.DataFrame()
        else:
            st.warning("Aviso: Dados de FRP0 não encontrados na estrutura esperada (menos de 3 linhas na tabela).")
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de requisição HTTP ao extrair FRP0: {e}. Verifique a URL ou sua conexão.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro inesperado ao extrair dados do FRP0: {e}. A estrutura da página pode ter mudado.")
        return pd.DataFrame()

def extrair_dif_oper_casada():
    """
    Extrai o indicador 'DIF OPER CASADA - COMPRA' usando requests.
    Este é o mais propenso a falhar sem JS, pois o valor pode ser injetado dinamicamente.
    Adiciona um alerta mais claro se o dado não for encontrado.
    """
    url = "https://sistemaswebb3-derivativos.b3.com.br/financialIndicatorsPage/?language=pt-br"
    try:
        response = requests.get(url, timeout=15) # Aumentei o timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # A B3 está usando React/JS para renderizar.
        # A simples requisição HTTP GET não trará o conteúdo completo.
        # Precisaríamos de uma API interna ou de uma biblioteca que execute JS.
        # Por enquanto, esta função provavelmente retornará None, None.
        
        bloco = soup.find("p", string=lambda text: text and "DIF OPER CASADA - COMPRA" in text)

        if bloco:
            div_mae = bloco.find_parent("div")
            if div_mae:
                valor_tag = div_mae.find("h4")
                data_tag = div_mae.find("small")
                if valor_tag and data_tag:
                    valor = valor_tag.text.strip()
                    data_atualizacao = data_tag.text.strip()
                    return valor, data_atualizacao
        
        st.info("ℹ️ O indicador 'DIF OPER CASADA - COMPRA' provavelmente é carregado via JavaScript. A extração com `requests` puro pode não ser suficiente para este dado.")
        return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de requisição HTTP ao extrair DIF OPER CASADA: {e}. Verifique a URL ou sua conexão.")
        return None, None
    except Exception as e:
        st.error(f"❌ Erro inesperado ao extrair DIF OPER CASADA: {e}. A estrutura da página pode ter mudado.")
        return None, None

# --- Funções de Formatação (Mantidas como estavam) ---

def tratar_valor_tcam_original(valor_str):
    """
    Trata string de valor TCAM conforme a lógica original do código para conversão.
    Assume que a última casa é decimal.
    """
    valor_limpo = ''.join(filter(str.isdigit, valor_str))
    if valor_limpo:
        if len(valor_limpo) >= 2:
            return float(valor_limpo[:-1] + '.' + valor_limpo[-1])
        else: # Ex: "5" -> "0.5"
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

st.set_page_config(layout="wide")
aba = st.tabs(["🏠 PRINCIPAL", "📊 DADOS BRUTOS", "🔗 LINKS"])

# Obter datas para as consultas
hoje = datetime.today()
# Define a data_base como a data útil para TCAM01
data_base_obj = datetime.strptime(obter_data_util_para_consulta(hoje), "%d/%m/%Y").date()

# Define as datas para TCAM01, TCAM02 e TCAM03
data_tcam1_str = data_base_obj.strftime("%d/%m/%Y")
data_tcam2_str = (data_base_obj - timedelta(days=1)).strftime("%d/%m/%Y")
data_tcam3_str = (data_base_obj - timedelta(days=2)).strftime("%d/%m/%Y")


# Dicionários para armazenar os dados de cada TCAM
dados_tcam = {}
dados_volume = {}
dados_liquido = {}
frp0_data = {}
dif_oper_data = {}

with st.spinner("Carregando dados... Isso pode levar alguns segundos devido à extração web."):
    
    # --- Extração para TCAM 01 (data útil padrão) ---
    df_tcam1, df_volume1, df_liquido1 = extrair_dados_b3(data_tcam1_str)
    if df_tcam1 is not None:
        dados_tcam[data_tcam1_str] = df_tcam1
        dados_volume[data_tcam1_str] = df_volume1
        dados_liquido[data_tcam1_str] = df_liquido1
    
    # --- Extração para TCAM 02 (data útil - 1) ---
    df_tcam2, df_volume2, df_liquido2 = extrair_dados_b3(data_tcam2_str)
    if df_tcam2 is not None:
        dados_tcam[data_tcam2_str] = df_tcam2
        dados_volume[data_tcam2_str] = df_volume2
        dados_liquido[data_tcam2_str] = df_liquido2

    # --- Extração para TCAM 03 (data útil - 2) ---
    df_tcam3, df_volume3, df_liquido3 = extrair_dados_b3(data_tcam3_str)
    if df_tcam3 is not None:
        dados_tcam[data_tcam3_str] = df_tcam3
        dados_volume[data_tcam3_str] = df_volume3
        dados_liquido[data_tcam3_str] = df_liquido3

    # --- Extração de FRP0 (apenas para a data TCAM 01) ---
    df_frp_extracted = extrair_frp0()
    if not df_frp_extracted.empty:
        frp0_data = {
            "ultimo_preco_str": df_frp_extracted["Último Preço"].iloc[0],
            "ultimo_preco_float": tratar_valor_frp0_dif_original(df_frp_extracted["Último Preço"].iloc[0])
        }
    else:
        frp0_data = {"ultimo_preco_str": "N/A", "ultimo_preco_float": 0.0}
        st.error("❌ Não foi possível extrair os dados do FRP0.")

    # --- Extração de DIF OPER CASADA (apenas para a data TCAM 01) ---
    dif_valor_raw, dif_data = extrair_dif_oper_casada()
    if dif_valor_raw:
        dif_oper_data = {
            "valor_str": dif_valor_raw.split()[0],
            "valor_float": tratar_valor_frp0_dif_original(dif_valor_raw.split()[0]),
            "data_atualizacao": dif_data
        }
    else:
        dif_oper_data = {"valor_str": "N/A", "valor_float": 0.0, "data_atualizacao": "N/A"}


# --- Funções para exibir tabela de TCAM + Indicadores ---
def exibir_tcam_com_indicadores(label, df_tcam, frp0_data, dif_oper_data):
    st.subheader(f"📌 {label}")
    if df_tcam is not None and not df_tcam.empty:
        fechamento_tcam = df_tcam["Fechamento"].iloc[0]
        minimo_tcam = df_tcam["Mínima"].iloc[0]
        media_tcam = df_tcam["Média"].iloc[0]
        maximo_tcam = df_tcam["Máxima"].iloc[0]

        # TCAM + FRP0
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

        # TCAM + DIF OPER CASADA
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

    # TCAM 01
    exibir_tcam_com_indicadores(f"TCAM 01 ({data_tcam1_str})", dados_tcam.get(data_tcam1_str), frp0_data, dif_oper_data)

    # TCAM 02
    exibir_tcam_com_indicadores(f"TCAM 02 ({data_tcam2_str})", dados_tcam.get(data_tcam2_str), frp0_data, dif_oper_data)

    # TCAM 03
    exibir_tcam_com_indicadores(f"TCAM 03 ({data_tcam3_str})", dados_tcam.get(data_tcam3_str), frp0_data, dif_oper_data)

# --- Aba DADOS BRUTOS ---
with aba[1]:
    st.title("📊 Dados Brutos - B3")
    st.success(f"Dados brutos da B3 para as datas consultadas.")
    st.markdown("---")

    # TCAM 01
    st.subheader(f"Dados Brutos - TCAM 01 ({data_tcam1_str})")
    if dados_tcam.get(data_tcam1_str) is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Taxas Praticadas (TCAM)**")
            st.dataframe(dados_tcam[data_tcam1_str], use_container_width=True)
        with col2:
            st.markdown("**Valores Liquidados**")
            st.dataframe(dados_liquido.get(data_tcam1_str, pd.DataFrame()), use_container_width=True) # Usa .get com default
        st.markdown("**Volume Contratado**")
        st.dataframe(dados_volume.get(data_tcam1_str, pd.DataFrame()), use_container_width=True) # Usa .get com default
    else:
        st.info(f"Não há dados brutos para TCAM 01 ({data_tcam1_str}) ou a extração falhou.")
    st.markdown("---")

    # TCAM 02
    st.subheader(f"Dados Brutos - TCAM 02 ({data_tcam2_str})")
    if dados_tcam.get(data_tcam2_str) is not None:
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
    if dados_tcam.get(data_tcam3_str) is not None:
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
        st.error("❌ Não foi possível extrair os dados do FRP0. Verifique as mensagens de erro acima.")

    st.markdown("---")
    st.subheader("📉 DIF OPER CASADA - COMPRA (Data Principal)")
    if dif_oper_data["valor_str"] != "N/A":
        st.metric(label="Valor Atual", value=dif_oper_data["valor_str"], delta=None)
        st.caption(f"Última atualização: {dif_oper_data['data_atualizacao']}")
    else:
        st.error("❌ Indicador 'DIF OPER CASADA - COMPRA' não disponível ou não pôde ser extraído via requisição estática. Veja a mensagem de informação acima.")


# --- Aba LINKS ---
with aba[2]:
    st.title("🔗 Links Úteis")
    st.markdown("---") 
    st.markdown("- [Página da B3 - Câmbio Histórico](https://sistemaswebb3-clearing.b3.com.br/historicalForeignExchangePage/retroactive?language=pt-br)")
    st.markdown("- [Página BMF - Boletim de Câmbio (FRP0)](https://www2.bmf.com.br/pages/portal/bmfbovespa/boletim1/SistemaPregao1.asp?pagetype=pop&caminho=Resumo%20Estat%EDstico%20-%20Sistema%20Preg%E3o&Data=&Mercadoria=FRP)")
    st.markdown("- [Página da B3 - Indicadores Financeiros (DIF OPER CASADA)](https://sistemaswebb3-derivativos.b3.com.br/financialIndicatorsPage/?language=pt-br)")
