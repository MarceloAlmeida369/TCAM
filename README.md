## **Projeto: Monitoramento de Taxas de Câmbio e Indicadores Financeiros da B3/BMF**

### **Visão Geral**

Este projeto consiste em um aplicativo web interativo, desenvolvido com Streamlit e Python, que tem como objetivo monitorar e apresentar de forma organizada as taxas de câmbio (TCAM) e indicadores financeiros relevantes extraídos diretamente das plataformas da B3 (Bolsa, Brasil, Balcão) e BMF (Bolsa de Mercadorias e Futuros). O aplicativo é projetado para fornecer dados do dia útil atual (TCAM 01) e dos dois dias úteis imediatamente anteriores (TCAM 02 e TCAM 03), combinando-os com informações de mercado como o FRP0 (Forward Points) e o indicador "DIF OPER CASADA - COMPRA".

### **Funcionalidades Principais**

O aplicativo é dividido em três abas principais para facilitar a navegação e a visualização dos dados:

1.  **🏠 PRINCIPAL:**
    * **TCAM (Taxa de Câmbio):** Exibe as taxas de câmbio (Fechamento, Mínima, Média, Máxima) para o Balcão, referentes ao dia útil mais recente (TCAM 01) e aos dois dias úteis anteriores (TCAM 02 e TCAM 03).
    * **FRP0 (Forward Points):** Apresenta o "Último Preço" do Contrato de Forward Points (FRP0) da BMF, um indicador crucial para operações de câmbio futuro.
    * **DIF OPER CASADA - COMPRA:** Mostra o valor atual deste indicador específico da B3, que pode ser relevante para estratégias de mercado.
    * **Somas Calculadas:** Para cada TCAM (01, 02, 03) e para cada uma de suas taxas (Fechamento, Mínima, Média, Máxima), o aplicativo calcula e exibe a soma com o valor do FRP0 e, separadamente, com o valor do "DIF OPER CASADA - COMPRA". Isso permite uma análise rápida da relação entre as taxas históricas de câmbio e esses indicadores.
    * **Tratamento de Dados Ausentes:** Em caso de não haver dados para uma TCAM específica em determinada data, o aplicativo exibe uma mensagem clara de aviso, em vez de retornar um erro, garantindo uma experiência de usuário robusta.

2.  **📊 DADOS BRUTOS:**
    * Esta aba fornece as tabelas completas e não processadas de onde os dados são extraídos, para cada uma das TCAMs (01, 02, 03).
    * **Taxas Praticadas (TCAM):** Tabela detalhada das taxas de câmbio.
    * **Valores Liquidados:** Detalhes dos valores de câmbio liquidados.
    * **Volume Contratado:** Informações sobre o volume de contratos de câmbio.
    * **FRP0 e DIF OPER CASADA:** Os dados brutos destes indicadores são exibidos de forma clara, complementando as informações calculadas na aba principal.
    * A exibição é organizada por data, facilitando a verificação e auditoria dos dados extraídos.

3.  **🔗 LINKS:**
    * Contém links diretos para as fontes oficiais dos dados, permitindo que o usuário acesse as páginas originais da B3 e BMF para verificação ou exploração adicional.

### **Tecnologia Utilizada**

* **Python:** Linguagem de programação principal.
* **Streamlit:** Framework de código aberto para criação rápida de aplicativos web interativos em Python, responsável pela interface do usuário.
* **Selenium WebDriver:** Ferramenta de automação de navegador utilizada para navegar nas páginas web da B3 e BMF, preencher formulários (como campos de data) e simular interações de usuário para extrair os dados. A execução é feita em modo *headless*, o que significa que o navegador opera em segundo plano sem uma interface gráfica visível, ideal para ambientes de servidor.
* **BeautifulSoup4 (bs4):** Biblioteca Python para *parsing* de HTML e XML. Após o Selenium carregar a página, o BeautifulSoup é usado para extrair os dados específicos das tabelas e elementos desejados de forma eficiente.
* **Pandas:** Biblioteca para manipulação e análise de dados. Fundamental para organizar os dados extraídos em DataFrames, realizar cálculos e preparar as informações para exibição.
* **`datetime` e `timedelta`:** Módulos padrão do Python utilizados para o cálculo de datas úteis, garantindo que o aplicativo sempre consulte os dias de negociação corretos, mesmo em fins de semana ou feriados.

### **Fontes de Dados (Links Referenciados)**

Os dados são extraídos de fontes públicas e oficiais da B3 e BMF:

* **Dados de Câmbio Histórico (TCAM, Volume Contratado, Valores Liquidados):**
    * **Link:** `https://sistemaswebb3-clearing.b3.com.br/historicalForeignExchangePage/retroactive?language=pt-br`
    * **Descrição:** Esta página da B3 permite a consulta retroativa de taxas de câmbio praticadas, volume de contratos negociados e valores liquidados no mercado de câmbio.

* **Contrato de Forward Points (FRP0):**
    * **Link:** `https://www2.bmf.com.br/pages/portal/bmfbovespa/boletim1/SistemaPregao1.asp?pagetype=pop&caminho=Resumo%20Estat%EDstico%20-%20Sistema%20Preg%E3o&Data=&Mercadoria=FRP`
    * **Descrição:** Seção do portal da BMF que apresenta o boletim de negociação de contratos de Forward Points, com informações sobre o último preço negociado.

* **Indicador "DIF OPER CASADA - COMPRA":**
    * **Link:** `https://sistemaswebb3-derivativos.b3.com.br/financialIndicatorsPage/?language=pt-br`
    * **Descrição:** Página de indicadores financeiros de derivativos da B3, onde o valor do "DIF OPER CASADA - COMPRA" é exibido.
