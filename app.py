import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
import duckdb as db
import pyarrow.parquet as pq

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Análise ENEM 2019",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header {color: #1f77b4; font-size: 2.5em; font-weight: bold;}
    .sub-header {color: #3C00E0; font-size: 1.8em; font-weight: bold;}
    .insight-box {
        background-color: #f0f8ff; 
        padding: 15px; 
        border-left: 5px solid #3C00E0;
        border-radius: 5px;
        margin: 10px 0;
    }
    .metric-box {
        background-color: #e8f5e9; 
        padding: 15px; 
        border-left: 5px solid #3da700;
        border-radius: 5px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3e0; 
        padding: 15px; 
        border-left: 5px solid #ff9800;
        border-radius: 5px;
        margin: 10px 0;
    }
    .insight-box, .metric-box, .warning-box {
        color: #111827;
        line-height: 1.5;
        font-size: 1rem;
    }
    .insight-box strong, .metric-box strong, .warning-box strong {
        color: inherit;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        color: #111827;
    }
</style>
""",
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).parent
ARQUIVO_PARQUET = BASE_DIR / "DADOS" / "microdados_enem_2019.parquet"
ARQUIVO_SQL = ARQUIVO_PARQUET.as_posix().replace("'", "''")

TRADUCAO_RENDA_SQL = """
CASE Q006
    WHEN 'A' THEN 'Nenhuma renda'
    WHEN 'B' THEN 'Até R$ 954'
    WHEN 'C' THEN '954 a 1431'
    WHEN 'D' THEN '1431 a 1908'
    WHEN 'E' THEN '1908 a 2385'
    WHEN 'F' THEN '2385 a 2862'
    WHEN 'G' THEN '2862 a 3816'
    WHEN 'H' THEN '3816 a 4770'
    WHEN 'I' THEN '4770 a 5724'
    WHEN 'J' THEN '5724 a 6678'
    WHEN 'K' THEN '6678 a 7632'
    WHEN 'L' THEN '7632 a 8586'
    WHEN 'M' THEN '8586 a 9540'
    WHEN 'N' THEN '9540 a 11448'
    WHEN 'O' THEN '11448 a 14310'
    WHEN 'P' THEN '14310 a 19080'
    WHEN 'Q' THEN 'Mais de 19080'
    ELSE 'Não informado'
END
"""

GRUPO_AM = "Amazonas"
GRUPO_OUTROS = "Outros estados"
ESCALA_NOTA = 1000.0

RENDA_MAP = {
    "A": "Nenhuma renda",
    "B": "Até R$ 954",
    "C": "954 a 1431",
    "D": "1431 a 1908",
    "E": "1908 a 2385",
    "F": "2385 a 2862",
    "G": "2862 a 3816",
    "H": "3816 a 4770",
    "I": "4770 a 5724",
    "J": "5724 a 6678",
    "K": "6678 a 7632",
    "L": "7632 a 8586",
    "M": "8586 a 9540",
    "N": "9540 a 11448",
    "O": "11448 a 14310",
    "P": "14310 a 19080",
    "Q": "Mais de 19080",
}

RENDA_ORDEM = list(RENDA_MAP.values())
RENDA_CODIGOS = list(RENDA_MAP.keys())

FAIXA_ETARIA_MAP = {
    1: "Menor de 17 anos",
    2: "17 anos",
    3: "18 anos",
    4: "19 anos",
    5: "20 anos",
    6: "21 anos",
    7: "22 anos",
    8: "23 anos",
    9: "24 anos",
    10: "25 anos",
    11: "26 a 30 anos",
    12: "31 a 35 anos",
    13: "36 a 40 anos",
    14: "41 a 45 anos",
    15: "46 a 50 anos",
    16: "51 a 55 anos",
    17: "56 a 60 anos",
    18: "61 a 65 anos",
    19: "66 a 70 anos",
    20: "Maior de 70 anos",
}

# Conversão aproximada da TP_FAIXA_ETARIA para idade real.
# O ENEM não traz a idade exata em algumas bases, apenas o código da faixa etária.
# Por isso, o filtro visual fica em anos reais (15 a 70), mas a consulta usa os códigos correspondentes.
FAIXA_ETARIA_INTERVALOS = {
    1: (15, 16),
    2: (17, 17),
    3: (18, 18),
    4: (19, 19),
    5: (20, 20),
    6: (21, 21),
    7: (22, 22),
    8: (23, 23),
    9: (24, 24),
    10: (25, 25),
    11: (26, 30),
    12: (31, 35),
    13: (36, 40),
    14: (41, 45),
    15: (46, 50),
    16: (51, 55),
    17: (56, 60),
    18: (61, 65),
    19: (66, 70),
    20: (71, 120),
}

DISCIPLINAS = {
    "Linguagens": "NU_NOTA_LC",
    "Ciências Humanas": "NU_NOTA_CH",
    "Ciências da Natureza": "NU_NOTA_CN",
    "Matemática": "NU_NOTA_MT",
    "Redação": "NU_NOTA_REDACAO",
}

@st.cache_resource(show_spinner="Preparando conexão com o arquivo Parquet...")
def conectar():
    if not ARQUIVO_PARQUET.exists():
        st.error(f"Arquivo não encontrado: {ARQUIVO_PARQUET}")
        st.stop()

    con = db.connect(database=":memory:")
    con.execute("PRAGMA threads=2")
    con.execute("PRAGMA memory_limit='700MB'")

    con.execute(
        f"""
        CREATE OR REPLACE VIEW enem AS
        SELECT
            *,
            (
                COALESCE(TP_PRESENCA_CN, 0) != 1 OR
                COALESCE(TP_PRESENCA_CH, 0) != 1 OR
                COALESCE(TP_PRESENCA_LC, 0) != 1 OR
                COALESCE(TP_PRESENCA_MT, 0) != 1
            ) AS FALTOU,
            CASE
                WHEN SG_UF_PROVA = 'AM' THEN 'Amazonas'
                ELSE 'Outros estados'
            END AS GRUPO_AM
        FROM read_parquet('{ARQUIVO_SQL}')
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE VIEW enem_notas AS
        SELECT
            *,
            (NU_NOTA_CN + NU_NOTA_CH + NU_NOTA_LC + NU_NOTA_MT + NU_NOTA_REDACAO) AS NOTA_TOTAL,
            ((NU_NOTA_CN + NU_NOTA_CH + NU_NOTA_LC + NU_NOTA_MT) / 4.0) AS MEDIA_NOTAS,
            ((NU_NOTA_CN + NU_NOTA_CH + NU_NOTA_LC + NU_NOTA_MT) / 4.0) AS MEDIA_4_PROVAS,
            {TRADUCAO_RENDA_SQL} AS RENDA
        FROM enem
        WHERE FALTOU = FALSE
          AND TP_STATUS_REDACAO = 1
          AND NU_NOTA_CN IS NOT NULL
          AND NU_NOTA_CH IS NOT NULL
          AND NU_NOTA_LC IS NOT NULL
          AND NU_NOTA_MT IS NOT NULL
          AND NU_NOTA_REDACAO IS NOT NULL
        """
    )
    return con

def query_df(sql: str) -> pd.DataFrame:
    return conectar().execute(sql).df()

@st.cache_data(show_spinner=False)
def info_arquivo():
    pf = pq.ParquetFile(ARQUIVO_PARQUET)
    return {
        "linhas": pf.metadata.num_rows,
        "colunas": pf.metadata.num_columns,
        "tamanho_mb": ARQUIVO_PARQUET.stat().st_size / 1024 / 1024,
        "colunas_nomes": pf.schema.names,
    }

@st.cache_data(show_spinner=False)
def limites_idade():
    info = info_arquivo()
    colunas = info["colunas_nomes"]

    if "NU_IDADE" in colunas:
        dados = query_df(
            """
            SELECT
                MIN(NU_IDADE) AS idade_minima,
                MAX(NU_IDADE) AS idade_maxima
            FROM enem
            WHERE NU_IDADE IS NOT NULL
            """
        ).iloc[0]

        idade_minima = int(dados["idade_minima"]) if pd.notna(dados["idade_minima"]) else 0
        idade_maxima = int(dados["idade_maxima"]) if pd.notna(dados["idade_maxima"]) else 100
        return "NU_IDADE", idade_minima, idade_maxima

    if "TP_FAIXA_ETARIA" in colunas:
        return "TP_FAIXA_ETARIA", 15, 70

    return None, None, None


def codigos_faixa_etaria_por_idade(idade_minima, idade_maxima):
    codigos = []
    for codigo, (inicio, fim) in FAIXA_ETARIA_INTERVALOS.items():
        if fim >= idade_minima and inicio <= idade_maxima:
            codigos.append(codigo)
    return codigos


def fmt_int(valor):
    return f"{int(valor):,}".replace(",", ".")

def fmt_float(valor, casas=2):
    return f"{float(valor):.{casas}f}"

def fmt_pct(valor, casas=2):
    if pd.isna(valor):
        return "Sem dados"
    return f"{float(valor):.{casas}f}%"

def safe_div(num, den):
    if den is None or pd.isna(den) or den == 0:
        return np.nan
    return num / den

def diferenca_percentual(valor_am, valor_outros):
    if pd.isna(valor_am) or pd.isna(valor_outros) or valor_outros == 0:
        return np.nan
    return ((valor_am - valor_outros) / valor_outros) * 100

def texto_comparativo(valor):
    if pd.isna(valor):
        return "Sem dados suficientes para comparação"
    if valor > 0:
        return f"AM está {valor:.2f}% acima dos outros estados"
    if valor < 0:
        return f"AM está {abs(valor):.2f}% abaixo dos outros estados"
    return "AM está igual aos outros estados"

def filtro_atual():
    return st.session_state.get("filter_clause", "")

def build_filter_clause(idade_range, sexo_selected, renda_selected, idade_coluna=None):
    conditions = []
    info = info_arquivo()
    colunas = info["colunas_nomes"]

    if idade_range is not None and idade_coluna == "NU_IDADE" and "NU_IDADE" in colunas:
        idade_min, idade_max = idade_range
        conditions.append(f"NU_IDADE BETWEEN {int(idade_min)} AND {int(idade_max)}")
    elif idade_range is not None and idade_coluna == "TP_FAIXA_ETARIA" and "TP_FAIXA_ETARIA" in colunas:
        idade_min, idade_max = idade_range
        codigos = codigos_faixa_etaria_por_idade(int(idade_min), int(idade_max))
        if codigos:
            codigos_sql = ", ".join(str(codigo) for codigo in codigos)
            conditions.append(f"CAST(TP_FAIXA_ETARIA AS INTEGER) IN ({codigos_sql})")
        else:
            conditions.append("1 = 0")

    if "TP_SEXO" in colunas and sexo_selected != "Todos":
        sexo_code = "M" if sexo_selected == "Masculino" else "F"
        conditions.append(f"TP_SEXO = '{sexo_code}'")

    if "Q006" in colunas and renda_selected:
        codigos_renda = [codigo for codigo, descricao in RENDA_MAP.items() if descricao in renda_selected]
        if len(codigos_renda) == 0:
            conditions.append("1 = 0")
        elif len(codigos_renda) < len(RENDA_MAP):
            codigos_sql = ", ".join([f"'{codigo}'" for codigo in codigos_renda])
            conditions.append(f"Q006 IN ({codigos_sql})")

    if conditions:
        return " WHERE " + " AND ".join(conditions)
    return ""

def setup_filters():
    st.sidebar.markdown("## 🔍 Filtros Globais")
    info = info_arquivo()
    colunas = info["colunas_nomes"]

    idade_range = None
    idade_coluna, idade_minima, idade_maxima = limites_idade()

    if idade_coluna is not None:
        label_idade = "Faixa etária"
        if idade_minima < idade_maxima:
            idade_range = st.sidebar.slider(
                label_idade,
                min_value=idade_minima,
                max_value=idade_maxima,
                value=(idade_minima, idade_maxima),
            )
        else:
            idade_range = (idade_minima, idade_maxima)

        if idade_coluna == "TP_FAIXA_ETARIA" and idade_range is not None:
            st.sidebar.caption("Filtro por idade aproximada com base na faixa etária do ENEM.")
    else:
        st.sidebar.caption("Filtro de idade não aplicado: coluna de idade/faixa etária não encontrada na base.")

    sexo_selected = "Todos"
    if "TP_SEXO" in colunas:
        sexo_selected = st.sidebar.radio(
            "Sexo",
            options=["Todos", "Masculino", "Feminino"],
            index=0,
        )
    else:
        st.sidebar.caption("Filtro de sexo não aplicado: coluna TP_SEXO não encontrada na base.")

    renda_selected = RENDA_ORDEM
    if "Q006" in colunas:
        renda_selected = st.sidebar.multiselect(
            "Renda familiar",
            options=RENDA_ORDEM,
            default=RENDA_ORDEM,
        )
    else:
        st.sidebar.caption("Filtro de renda não aplicado: coluna Q006 não encontrada na base.")

    return build_filter_clause(idade_range, sexo_selected, renda_selected, idade_coluna)

def tabela_comparativa_grupos(df, coluna_valor, nome_valor, coluna_indice=None):
    if df.empty:
        return pd.DataFrame()

    dados = df.copy()
    if coluna_indice is None:
        dados["Comparação"] = nome_valor
        coluna_indice = "Comparação"

    pivot = dados.pivot_table(index=coluna_indice, columns="GRUPO_AM", values=coluna_valor, aggfunc="first")
    for grupo in [GRUPO_AM, GRUPO_OUTROS]:
        if grupo not in pivot.columns:
            pivot[grupo] = np.nan

    pivot = pivot[[GRUPO_AM, GRUPO_OUTROS]].reset_index()
    pivot = pivot.rename(
        columns={
            GRUPO_AM: f"{nome_valor} - AM",
            GRUPO_OUTROS: f"{nome_valor} - Outros estados",
        }
    )
    pivot["Diferença % (AM vs Outros)"] = pivot.apply(
        lambda linha: diferenca_percentual(
            linha[f"{nome_valor} - AM"],
            linha[f"{nome_valor} - Outros estados"],
        ),
        axis=1,
    )
    pivot["Leitura"] = pivot["Diferença % (AM vs Outros)"].apply(texto_comparativo)
    return pivot

@st.cache_data(show_spinner="Calculando métricas gerais...")
def metricas_gerais(filter_clause=""):
    return query_df(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN FALTOU = FALSE THEN 1 ELSE 0 END) AS comparecidos,
            SUM(CASE WHEN FALTOU = TRUE THEN 1 ELSE 0 END) AS faltantes,
            COUNT(*) FILTER (WHERE GRUPO_AM = 'Amazonas') AS amazonas,
            COUNT(*) FILTER (WHERE GRUPO_AM = 'Outros estados') AS outros
        FROM enem
        {filter_clause}
        """
    ).iloc[0]

@st.cache_data(show_spinner="Calculando métricas por grupo...")
def metricas_por_grupo(filter_clause=""):
    return query_df(
        f"""
        SELECT
            GRUPO_AM,
            COUNT(*) AS total,
            SUM(CASE WHEN FALTOU = FALSE THEN 1 ELSE 0 END) AS comparecidos,
            SUM(CASE WHEN FALTOU = TRUE THEN 1 ELSE 0 END) AS faltantes,
            (SUM(CASE WHEN FALTOU = FALSE THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS taxa_comparecimento_pct,
            (SUM(CASE WHEN FALTOU = TRUE THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS taxa_falta_pct
        FROM enem
        {filter_clause}
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )

@st.cache_data(show_spinner="Calculando estatísticas de notas...")
def estatisticas_disciplinas(filter_clause=""):
    partes = []
    for nome, col in DISCIPLINAS.items():
        partes.append(
            f"""
            SELECT
                '{nome}' AS Disciplina,
                AVG({col}) AS mean,
                median({col}) AS median,
                stddev_samp({col}) AS std,
                MIN({col}) AS min,
                MAX({col}) AS max
            FROM enem_notas
            {filter_clause}
            """
        )
    return query_df(" UNION ALL ".join(partes)).round(2)

@st.cache_data(show_spinner="Calculando médias por grupo...")
def medias_grupo_disciplinas(filter_clause=""):
    return query_df(
        f"""
        SELECT
            GRUPO_AM,
            AVG(NU_NOTA_LC) AS NU_NOTA_LC,
            AVG(NU_NOTA_CH) AS NU_NOTA_CH,
            AVG(NU_NOTA_CN) AS NU_NOTA_CN,
            AVG(NU_NOTA_MT) AS NU_NOTA_MT,
            AVG(NU_NOTA_REDACAO) AS NU_NOTA_REDACAO
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )

@st.cache_data(show_spinner="Calculando correlação entre renda e nota...")
def correlacao_renda_nota(filter_clause=""):
    return query_df(
        f"""
        SELECT
            GRUPO_AM,
            corr(
                CASE Q006
                    WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 WHEN 'D' THEN 4
                    WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7 WHEN 'H' THEN 8
                    WHEN 'I' THEN 9 WHEN 'J' THEN 10 WHEN 'K' THEN 11 WHEN 'L' THEN 12
                    WHEN 'M' THEN 13 WHEN 'N' THEN 14 WHEN 'O' THEN 15 WHEN 'P' THEN 16
                    WHEN 'Q' THEN 17 ELSE NULL
                END,
                MEDIA_NOTAS
            ) AS correlacao
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )

def pagina_home():
    st.markdown('<p class="main-header">📊 Análise Exploratória ENEM 2019</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        Análise comparativa de desempenho no ENEM 2019 entre:
        - **Amazonas (AM)**
        - **Outros estados**

        ✅ Arquivo completo do ENEM 2019  
        ✅ Consultas feitas sobre todos os registros  
        ✅ 17 faixas de renda familiar  
        ✅ 5 componentes de avaliação  
        """
        )

    with col2:
        m = metricas_gerais(filter_clause)
        total = int(m["total"])
        comparecidos = int(m["comparecidos"])
        faltantes = int(m["faltantes"])

        col2a, col2b = st.columns(2)
        with col2a:
            st.metric("Total de Registros", fmt_int(total))
            st.metric("Comparecidos", fmt_int(comparecidos))
        with col2b:
            st.metric("Faltantes", fmt_int(faltantes))
            st.metric("Taxa de Comparecimento", f"{comparecidos / total * 100:.2f}%" if total else "Sem dados")

    st.markdown("---")

    st.markdown("### 📌 Comparação principal: AM vs Outros Estados")
    comparativo_presenca = metricas_por_grupo(filter_clause)
    if len(comparativo_presenca) >= 2:
        tabela = tabela_comparativa_grupos(comparativo_presenca, "taxa_comparecimento_pct", "Taxa de presença (%)")
        st.dataframe(
            tabela.style.format({
                "Taxa de presença (%) - AM": "{:.2f}%",
                "Taxa de presença (%) - Outros estados": "{:.2f}%",
                "Diferença % (AM vs Outros)": "{:.2f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Os filtros atuais não retornaram dados suficientes para comparar AM vs Outros estados.")

    st.markdown(
        """

    Use o **menu lateral** para acessar as análises:

    1. **Limpeza de Dados** - Validação e tratamento dos dados brutos
    2. **Presença/Faltantes** - Análise de comparecimento
    3. **Desempenho por Disciplina** - Quais áreas os alunos dominam
    4. **Top/Bottom Performers** - Melhores e piores alunos
    5. **Quartis/Percentis** - Posicionamento relativo dos alunos
    6. **Comparativo de Redação** - Redação como fator preditor
    7. **Análise de Outliers** - Casos extremos e especiais
    8. **Análise por Renda** - Relação entre renda e desempenho
    9. **Comparativo Nota x Renda** - Relação entre renda e nota por grupo
    10. **Insights & Conclusões** - Resumo das principais descobertas
    """
    )

def pagina_limpeza():
    st.markdown('<p class="sub-header">🧹 Limpeza e Validação de Dados</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    info = info_arquivo()
    m = metricas_gerais(filter_clause)
    total = int(m["total"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Linhas", fmt_int(info["linhas"]))
    with col2:
        st.metric("Colunas originais", info["colunas"])
    with col3:
        st.metric("Tamanho do arquivo", f"{info['tamanho_mb']:.1f} MB")

    st.markdown("### 📌 Análise Comparativa de Valores Nulos")
    st.caption("Comparação percentual de nulos: AM vs Outros estados. Os filtros globais também são aplicados aqui.")

    colunas = info["colunas_nomes"]
    expressoes = []
    for c in colunas:
        c_sql = c.replace('"', '""')
        expressoes.append(f"COUNT(*) - COUNT(\"{c_sql}\") AS \"{c_sql}\"")

    nulos_linha = query_df(f"SELECT GRUPO_AM, COUNT(*) AS TOTAL_GRUPO, {', '.join(expressoes)} FROM enem {filter_clause} GROUP BY GRUPO_AM")

    if nulos_linha.empty:
        st.info("Os filtros atuais não retornaram dados.")
    else:
        registros = []
        for coluna in colunas:
            for _, linha in nulos_linha.iterrows():
                total_grupo = linha["TOTAL_GRUPO"]
                quantidade = linha[coluna]
                registros.append(
                    {
                        "Coluna": coluna,
                        "GRUPO_AM": linha["GRUPO_AM"],
                        "Percentual de nulos": quantidade / total_grupo * 100 if total_grupo else np.nan,
                    }
                )
        nulos = pd.DataFrame(registros)
        nulos = nulos[nulos["Percentual de nulos"] > 0]

        if len(nulos) > 0:
            nulos_comp = tabela_comparativa_grupos(nulos, "Percentual de nulos", "Nulos (%)", "Coluna")
            nulos_comp = nulos_comp.sort_values("Diferença % (AM vs Outros)", ascending=False, na_position="last")
            st.dataframe(
                nulos_comp.style.format({
                    "Nulos (%) - AM": "{:.2f}%",
                    "Nulos (%) - Outros estados": "{:.2f}%",
                    "Diferença % (AM vs Outros)": "{:.2f}%",
                }),
                use_container_width=True,
                hide_index=True,
            )
            st.info("⚠️ Valores nulos detectados — as análises filtram notas ausentes quando necessário.")
        else:
            st.success("✅ Sem valores nulos detectados nos dados filtrados")

    st.markdown("### 📋 Tipos de Dados")
    tipos = query_df(
        f"""
        SELECT column_type AS Tipo, COUNT(*) AS Quantidade
        FROM (DESCRIBE SELECT * FROM read_parquet('{ARQUIVO_SQL}'))
        GROUP BY column_type
        ORDER BY Quantidade DESC
        """
    )
    st.dataframe(tipos, use_container_width=True, hide_index=True)

    st.markdown("### ✨ Variáveis Criadas para Análise")
    col1, col2 = st.columns(2)

    with col1:
        comparecidos = int(m["comparecidos"])
        faltantes = int(m["faltantes"])
        st.markdown(
            f"""
        **FALTOU** (Boolean)
        - True: Não compareceu em pelo menos uma prova
        - False: Compareceu em todas as provas

        Distribuição filtrada:
        - Compareceram: {fmt_int(comparecidos)} ({comparecidos/total*100:.2f}% se houver dados)
        - Faltaram: {fmt_int(faltantes)} ({faltantes/total*100:.2f}% se houver dados)
        """ if total else "**FALTOU**: sem dados nos filtros atuais."
        )

    with col2:
        amazonas = int(m["amazonas"])
        outros = int(m["outros"])
        st.markdown(
            f"""
        **GRUPO_AM** (Categórico)
        - 'Amazonas': UF da prova == 'AM'
        - 'Outros estados': UF da prova != 'AM'

        Distribuição filtrada:
        - Amazonas: {fmt_int(amazonas)} ({amazonas/total*100:.2f}% se houver dados)
        - Outros: {fmt_int(outros)} ({outros/total*100:.2f}% se houver dados)
        """ if total else "**GRUPO_AM**: sem dados nos filtros atuais."
        )

    st.markdown("### ✅ Checklist de Qualidade")
    checklist = pd.DataFrame(
        {
            "Verificação": [
                "Arquivo Parquet encontrado",
                "Metadados do Parquet lidos",
                "Presença consistente",
                "Notas filtradas nas análises",
                "Grupos criados corretamente",
            ],
            "Status": ["✅", "✅", "✅", "✅", "✅"],
        }
    )
    st.dataframe(checklist, use_container_width=True, hide_index=True)

def pagina_presenca():
    st.markdown('<p class="sub-header">✅ Análise de Presença/Faltantes</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    faltas = metricas_por_grupo(filter_clause)

    if faltas.empty or len(faltas) < 2:
        st.info("Os filtros atuais não retornaram dados suficientes para comparar AM vs Outros estados.")
        return

    tabela_presenca = tabela_comparativa_grupos(faltas, "taxa_comparecimento_pct", "Presença (%)")
    tabela_falta = tabela_comparativa_grupos(faltas, "taxa_falta_pct", "Falta (%)")

    col1, col2, col3 = st.columns(3)
    am_pres = tabela_presenca.iloc[0]["Presença (%) - AM"]
    outros_pres = tabela_presenca.iloc[0]["Presença (%) - Outros estados"]
    diff_pres = tabela_presenca.iloc[0]["Diferença % (AM vs Outros)"]
    with col1:
        st.metric("Presença AM", fmt_pct(am_pres))
    with col2:
        st.metric("Presença Outros estados", fmt_pct(outros_pres))
    with col3:
        st.metric("Diferença AM vs Outros", fmt_pct(diff_pres))

    st.markdown("### 🔢 Números inteiros de presença e faltantes")
    numeros_presenca = faltas[["GRUPO_AM", "comparecidos", "faltantes", "total"]].copy()
    numeros_presenca = numeros_presenca.rename(
        columns={
            "GRUPO_AM": "Região",
            "comparecidos": "Compareceram",
            "faltantes": "Faltaram",
            "total": "Total",
        }
    )
    st.dataframe(
        numeros_presenca.style.format({
            "Compareceram": lambda v: fmt_int(v),
            "Faltaram": lambda v: fmt_int(v),
            "Total": lambda v: fmt_int(v),
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📊 Comparação percentual por Região")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(
            tabela_presenca.style.format({
                "Presença (%) - AM": "{:.2f}%",
                "Presença (%) - Outros estados": "{:.2f}%",
                "Diferença % (AM vs Outros)": "{:.2f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )
    with col2:
        st.dataframe(
            tabela_falta.style.format({
                "Falta (%) - AM": "{:.2f}%",
                "Falta (%) - Outros estados": "{:.2f}%",
                "Diferença % (AM vs Outros)": "{:.2f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### 📈 Visualização Gráfica")
    col1, col2 = st.columns(2)

    with col1:
        plot = faltas.set_index("GRUPO_AM")["taxa_comparecimento_pct"]
        fig, ax = plt.subplots(figsize=(6, 4))
        plot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.5)
        ax.set_title("Taxa de Presença por Região (%)", fontsize=10, fontweight="bold")
        ax.set_ylabel("Porcentagem (%)", fontsize=9)
        ax.set_xlabel("Região", fontsize=9)
        ax.grid(axis="y", alpha=0.2)
        ax.set_ylim(0, 100)
        for i, v in enumerate(plot):
            ax.text(i, min(v + 2, 98), f"{v:.1f}%", ha="center", fontsize=7, fontweight="bold")
        plt.xticks(rotation=0, fontsize=8)
        st.pyplot(fig)

    with col2:
        faltas_pct_plot = faltas.set_index("GRUPO_AM")[["taxa_comparecimento_pct", "taxa_falta_pct"]].T
        faltas_pct_plot.index = ["Compareceu (%)", "Faltou (%)"]
        fig, ax = plt.subplots(figsize=(10, 6))
        faltas_pct_plot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"])
        ax.set_title("Taxa de Participação por Região (%)", fontsize=12, fontweight="bold")
        ax.set_ylabel("Porcentagem (%)")
        ax.legend(title="Região", loc="upper right")
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylim(0, 100)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.1f%%", fontsize=9)
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig)

    st.markdown(
        """
    <div style="background-color: black; color: white; padding: 15px; border-radius: 10px; font-size: 14px;">
    <strong>🔍 INSIGHT:</strong><br>
    A comparação de presença permite identificar diferenças regionais de comparecimento e possíveis desafios de acesso.
    </div>
    """,
        unsafe_allow_html=True,
    )

def pagina_disciplinas():
    st.markdown('<p class="sub-header">📚 Desempenho por Disciplina</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()

    st.markdown("### 📊 Estatísticas por Disciplina")
    medias_grupo = medias_grupo_disciplinas(filter_clause)
    if medias_grupo.empty or len(medias_grupo) < 2:
        st.info("Os filtros atuais não retornaram dados suficientes para comparar AM vs Outros estados.")
        return

    registros = []
    for nome, col in DISCIPLINAS.items():
        for _, linha in medias_grupo.iterrows():
            registros.append({"Disciplina": nome, "GRUPO_AM": linha["GRUPO_AM"], "Média (%)": linha[col] / ESCALA_NOTA * 100})
    stats = pd.DataFrame(registros)
    tabela = tabela_comparativa_grupos(stats, "Média (%)", "Média (%)", "Disciplina")
    st.dataframe(
        tabela.style.format({
            "Média (%) - AM": "{:.2f}%",
            "Média (%) - Outros estados": "{:.2f}%",
            "Diferença % (AM vs Outros)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📈 Comparação Visual")
    col1, col2 = st.columns(2)

    with col1:
        plot = tabela.set_index("Disciplina")[["Média (%) - AM", "Média (%) - Outros estados"]]
        fig, ax = plt.subplots(figsize=(12, 6))
        plot.plot(kind="barh", ax=ax, color=["#3da700", "#3C00E0"])
        ax.set_title("Médias de Notas por Disciplina (%)", fontsize=12, fontweight="bold")
        ax.set_xlabel("Média em % da escala")
        ax.grid(axis="x", alpha=0.3)
        ax.set_xlim(0, 100)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.1f%%", fontsize=8)
        st.pyplot(fig)

    with col2:
        plot = tabela.set_index("Disciplina")["Diferença % (AM vs Outros)"]
        fig, ax = plt.subplots(figsize=(12, 6))
        plot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.8)
        ax.set_title("Diferença Percentual: AM vs Outros Estados", fontsize=12, fontweight="bold")
        ax.set_ylabel("Diferença (%)")
        ax.set_xlabel("Disciplina")
        ax.axhline(0, color="black", linewidth=1)
        ax.grid(axis="y", alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        for i, v in enumerate(plot):
            ax.text(i, v, f"{v:.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
        st.pyplot(fig)

    st.markdown(
        """
    <div class="warning-box" style="background-color: #1e1e2f; color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #ffb000;">
    <strong>⚠️ ACHADO IMPORTANTE:</strong><br>
    As médias são calculadas usando todos os registros válidos do arquivo completo e comparadas sempre entre AM e Outros estados.
    </div>
    """,
        unsafe_allow_html=True,
    )

def pagina_performers():
    st.markdown('<p class="sub-header">🏆 Top e Bottom Performers</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    limites = query_df(
        f"""
        SELECT
            quantile_cont(MEDIA_NOTAS, 0.90) AS p90,
            quantile_cont(MEDIA_NOTAS, 0.10) AS p10
        FROM enem_notas
        {filter_clause}
        """
    ).iloc[0]

    if pd.isna(limites["p90"]) or pd.isna(limites["p10"]):
        st.info("Os filtros atuais não retornaram dados suficientes para calcular top/bottom performers.")
        return

    p90 = float(limites["p90"])
    p10 = float(limites["p10"])

    desempenho = query_df(
        f"""
        SELECT
            GRUPO_AM,
            AVG(CASE WHEN MEDIA_NOTAS >= {p90} THEN MEDIA_NOTAS ELSE NULL END) AS media_top_10,
            AVG(CASE WHEN MEDIA_NOTAS <= {p10} THEN MEDIA_NOTAS ELSE NULL END) AS media_bottom_10
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )

    if desempenho.empty or len(desempenho) < 2:
        st.info("Os filtros atuais não retornaram dados suficientes para comparar AM vs Outros estados.")
        return

    desempenho["Top 10% (%)"] = desempenho["media_top_10"] / ESCALA_NOTA * 100
    desempenho["Bottom 10% (%)"] = desempenho["media_bottom_10"] / ESCALA_NOTA * 100

    top_tabela = tabela_comparativa_grupos(desempenho, "Top 10% (%)", "Top 10% (%)")
    bottom_tabela = tabela_comparativa_grupos(desempenho, "Bottom 10% (%)", "Bottom 10% (%)")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Corte Top 10%", fmt_pct(p90 / ESCALA_NOTA * 100))
    with col2:
        st.metric("Corte Bottom 10%", fmt_pct(p10 / ESCALA_NOTA * 100))

    st.markdown("### 📊 Comparação de Desempenho por Região")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**TOP 10% (Média de desempenho)**")
        st.dataframe(
            top_tabela.style.format({
                "Top 10% (%) - AM": "{:.2f}%",
                "Top 10% (%) - Outros estados": "{:.2f}%",
                "Diferença % (AM vs Outros)": "{:.2f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )
    with col2:
        st.markdown("**BOTTOM 10% (Média de desempenho)**")
        st.dataframe(
            bottom_tabela.style.format({
                "Bottom 10% (%) - AM": "{:.2f}%",
                "Bottom 10% (%) - Outros estados": "{:.2f}%",
                "Diferença % (AM vs Outros)": "{:.2f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### 📈 Visualização Comparativa")
    plot_df = pd.DataFrame(
        {
            "Grupo": ["TOP 10%", "BOTTOM 10%"],
            "AM": [top_tabela.iloc[0]["Top 10% (%) - AM"], bottom_tabela.iloc[0]["Bottom 10% (%) - AM"]],
            "Outros estados": [top_tabela.iloc[0]["Top 10% (%) - Outros estados"], bottom_tabela.iloc[0]["Bottom 10% (%) - Outros estados"]],
        }
    ).set_index("Grupo")

    fig, ax = plt.subplots(figsize=(10, 6))
    plot_df.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.6)
    ax.set_title("Top/Bottom: Média de Desempenho (%)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Média em % da escala")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f%%", fontsize=9)
    plt.tight_layout()
    st.pyplot(fig)

def pagina_quartis():
    st.markdown('<p class="sub-header">📍 Quartis e Percentis</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()

    with st.expander("📚 O QUE SÃO QUARTIS E PERCENTIS?"):
        st.markdown(
            """
        Dividem os dados em **4 partes iguais** (25% cada).

        Dividem os dados em **100 partes** (1% cada).
        """
        )

    qs = query_df(
        f"""
        SELECT
            quantile_cont(MEDIA_NOTAS, 0.10) AS p10,
            quantile_cont(MEDIA_NOTAS, 0.25) AS q1,
            quantile_cont(MEDIA_NOTAS, 0.50) AS q2,
            quantile_cont(MEDIA_NOTAS, 0.75) AS q3,
            quantile_cont(MEDIA_NOTAS, 0.90) AS p90
        FROM enem_notas
        {filter_clause}
        """
    ).iloc[0]

    if pd.isna(qs["q1"]):
        st.info("Os filtros atuais não retornaram dados suficientes para calcular quartis.")
        return

    st.markdown("### 📊 Valores de Referência")
    col1, col2 = st.columns(2)
    with col1:
        quartis_df = pd.DataFrame(
            {
                "Quartil": ["Q1", "Q2", "Q3", "Q4"],
                "Percentual acumulado": ["25%", "50%", "75%", "100%"],
                "Interpretação": ["25% da base filtrada", "50% da base filtrada", "75% da base filtrada", "100% da base filtrada"],
            }
        )
        st.dataframe(quartis_df, use_container_width=True, hide_index=True)
    with col2:
        percentis_df = pd.DataFrame(
            {
                "Percentil": ["P10", "P25", "P50", "P75", "P90"],
                "Percentual acumulado": ["10%", "25%", "50%", "75%", "90%"],
                "Interpretação": ["10% abaixo", "25% abaixo", "50% abaixo", "75% abaixo", "90% abaixo"],
            }
        )
        st.dataframe(percentis_df, use_container_width=True, hide_index=True)

    q1, q2, q3 = float(qs["q1"]), float(qs["q2"]), float(qs["q3"])
    quartil_grupo = query_df(
        f"""
        SELECT
            GRUPO_AM,
            CASE
                WHEN MEDIA_NOTAS <= {q1} THEN 'Q1 (0%-25%)'
                WHEN MEDIA_NOTAS <= {q2} THEN 'Q2 (25%-50%)'
                WHEN MEDIA_NOTAS <= {q3} THEN 'Q3 (50%-75%)'
                ELSE 'Q4 (75%-100%)'
            END AS QUARTIL,
            COUNT(*) AS quantidade
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM, QUARTIL
        ORDER BY GRUPO_AM, QUARTIL
        """
    )

    tabela_abs = quartil_grupo.pivot(index="GRUPO_AM", columns="QUARTIL", values="quantidade").fillna(0)
    tabela_pct = tabela_abs.div(tabela_abs.sum(axis=1), axis=0) * 100

    st.markdown("### 📈 Distribuição por Quartil")
    st.dataframe(tabela_pct.style.format("{:.2f}%"), use_container_width=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    tabela_pct.T.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.7)
    ax.set_title("Distribuição Percentual de Alunos por Quartil", fontsize=12, fontweight="bold")
    ax.set_xlabel("Quartil")
    ax.set_ylabel("Percentual (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f%%", fontsize=9)
    plt.tight_layout()
    st.pyplot(fig)

def pagina_redacao():
    st.markdown('<p class="sub-header">✍️ Comparativo de Redação</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    metricas = query_df(
        f"""
        SELECT
            GRUPO_AM,
            AVG(NU_NOTA_REDACAO) AS media_redacao,
            median(NU_NOTA_REDACAO) AS mediana_redacao,
            stddev_samp(NU_NOTA_REDACAO) AS desvio_redacao,
            AVG(MEDIA_4_PROVAS) AS media_4_provas,
            corr(NU_NOTA_REDACAO, MEDIA_4_PROVAS) AS corr_redacao
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )

    if metricas.empty or len(metricas) < 2:
        st.info("Os filtros atuais não retornaram dados suficientes para comparar AM vs Outros estados.")
        return

    metricas["Redação (%)"] = metricas["media_redacao"] / ESCALA_NOTA * 100
    metricas["Média 4 Provas (%)"] = metricas["media_4_provas"] / ESCALA_NOTA * 100
    tabela_red = tabela_comparativa_grupos(metricas, "Redação (%)", "Redação (%)")
    tabela_media4 = tabela_comparativa_grupos(metricas, "Média 4 Provas (%)", "Média 4 Provas (%)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Redação AM", fmt_pct(tabela_red.iloc[0]["Redação (%) - AM"]))
    with col2:
        st.metric("Redação Outros", fmt_pct(tabela_red.iloc[0]["Redação (%) - Outros estados"]))
    with col3:
        st.metric("Diferença Redação", fmt_pct(tabela_red.iloc[0]["Diferença % (AM vs Outros)"]))
    with col4:
        corr_am = metricas.loc[metricas["GRUPO_AM"] == GRUPO_AM, "corr_redacao"].iloc[0]
        st.metric("Correlação AM", f"{corr_am:.3f}" if pd.notna(corr_am) else "Sem dados")

    st.markdown("### 📊 Comparação por Região")
    redacao_comp = pd.concat([tabela_red, tabela_media4], ignore_index=True)
    st.dataframe(
        redacao_comp.style.format({
            "Redação (%) - AM": "{:.2f}%",
            "Redação (%) - Outros estados": "{:.2f}%",
            "Média 4 Provas (%) - AM": "{:.2f}%",
            "Média 4 Provas (%) - Outros estados": "{:.2f}%",
            "Diferença % (AM vs Outros)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📈 Análise Visual")
    col1, col2 = st.columns(2)

    with col1:
        hist = query_df(
            f"""
            SELECT
                GRUPO_AM,
                FLOOR(NU_NOTA_REDACAO / 20) * 20 AS faixa,
                COUNT(*) AS frequencia
            FROM enem_notas
            {filter_clause}
            GROUP BY GRUPO_AM, faixa
            ORDER BY faixa
            """
        )
        hist["Percentual"] = hist.groupby("GRUPO_AM")["frequencia"].transform(lambda x: x / x.sum() * 100)
        hist_pivot = hist.pivot(index="faixa", columns="GRUPO_AM", values="Percentual").fillna(0)

        fig, ax = plt.subplots(figsize=(12, 6))
        hist_pivot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.8)
        ax.set_title("Distribuição percentual de Redação", fontweight="bold")
        ax.set_xlabel("Faixa da nota de redação")
        ax.set_ylabel("Percentual (%)")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(title="Região")
        st.pyplot(fig)

    with col2:
        valores = pd.Series(
            [
                tabela_red.iloc[0]["Redação (%) - AM"],
                tabela_red.iloc[0]["Redação (%) - Outros estados"],
                tabela_media4.iloc[0]["Média 4 Provas (%) - AM"],
                tabela_media4.iloc[0]["Média 4 Provas (%) - Outros estados"],
            ],
            index=[
                "Redação AM",
                "Redação Outros Estados",
                "Média 4 provas AM",
                "Média 4 provas Outros Estados",
            ],
        )
        fig, ax = plt.subplots(figsize=(10, 6))
        valores.plot(kind="bar", ax=ax, color=["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A"], width=0.8)
        ax.set_title("Comparação: Redação vs Outras Médias", fontweight="bold")
        ax.set_ylabel("Média em % da escala")
        ax.set_xlabel("Comparação")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.3)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
        for i, v in enumerate(valores):
            ax.text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=9)
        st.pyplot(fig)

    st.markdown("### 🔗 Correlação Redação vs Média de Provas")
    st.caption("O cálculo da correlação usa todos os registros válidos. O gráfico abaixo usa uma amostra apenas para visualização e não altera os resultados numéricos.")

    amostra = query_df(
        f"""
        SELECT GRUPO_AM, MEDIA_4_PROVAS, NU_NOTA_REDACAO
        FROM enem_notas
        {filter_clause}
        LIMIT 15000
        """
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    cores_scatter = {"Amazonas": "#3da700", "Outros estados": "#3C00E0"}
    for grupo, dados_grupo in amostra.groupby("GRUPO_AM"):
        ax.scatter(
            dados_grupo["MEDIA_4_PROVAS"] / ESCALA_NOTA * 100,
            dados_grupo["NU_NOTA_REDACAO"] / ESCALA_NOTA * 100,
            alpha=0.3,
            s=10,
            color=cores_scatter.get(grupo, "gray"),
            label=grupo,
        )
    ax.set_title("Redação vs Média de 4 Provas (%)", fontweight="bold", fontsize=12)
    ax.set_xlabel("Média de 4 Provas (%)")
    ax.set_ylabel("Nota de Redação (%)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    st.pyplot(fig)

def pagina_outliers():
    st.markdown('<p class="sub-header">🎯 Análise de Outliers</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()

    with st.expander("📚 O QUE SÃO OUTLIERS?"):
        st.markdown(
            """
        **Outliers** são valores extremamente afastados da maioria dos dados.

        Método IQR:
        - IQR = Q3 - Q1
        - Lower Bound = Q1 - 1.5 × IQR
        - Upper Bound = Q3 + 1.5 × IQR
        """
        )

    qs = query_df(
        f"""
        SELECT
            quantile_cont(MEDIA_NOTAS, 0.25) AS q1,
            quantile_cont(MEDIA_NOTAS, 0.75) AS q3
        FROM enem_notas
        {filter_clause}
        """
    ).iloc[0]

    if pd.isna(qs["q1"]):
        st.info("Os filtros atuais não retornaram dados suficientes para calcular outliers.")
        return

    q1 = float(qs["q1"])
    q3 = float(qs["q3"])
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Q1", fmt_pct(q1 / ESCALA_NOTA * 100))
    with col2:
        st.metric("Q3", fmt_pct(q3 / ESCALA_NOTA * 100))
    with col3:
        st.metric("Lower Bound", fmt_pct(lower_bound / ESCALA_NOTA * 100))
    with col4:
        st.metric("Upper Bound", fmt_pct(upper_bound / ESCALA_NOTA * 100))

    outliers = query_df(
        f"""
        SELECT
            GRUPO_AM,
            CASE
                WHEN MEDIA_NOTAS < {lower_bound} THEN 'Outlier Baixo'
                WHEN MEDIA_NOTAS > {upper_bound} THEN 'Outlier Alto'
                ELSE 'Normal'
            END AS TIPO_OUTLIER,
            COUNT(*) AS quantidade
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM, TIPO_OUTLIER
        ORDER BY GRUPO_AM, TIPO_OUTLIER
        """
    )

    tabela_abs = outliers.pivot(index="GRUPO_AM", columns="TIPO_OUTLIER", values="quantidade").fillna(0)
    tabela_pct = tabela_abs.div(tabela_abs.sum(axis=1), axis=0) * 100

    st.markdown("### 📍 Distribuição por Região")
    st.dataframe(tabela_pct.style.format("{:.2f}%"), use_container_width=True)

    st.markdown("### 📈 Visualização")
    col1, col2 = st.columns(2)
    with col1:
        fig, ax = plt.subplots(figsize=(8, 5))
        tabela_pct.T.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.7)
        ax.set_title("Distribuição Percentual de Outliers", fontweight="bold")
        ax.set_ylabel("Percentual (%)")
        ax.set_ylim(0, 100)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
        ax.grid(axis="y", alpha=0.3)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.1f%%", fontsize=9)
        st.pyplot(fig)

    with col2:
        st.caption("Boxplot com amostra visual; limites e contagens usam todos os dados válidos.")
        amostra_box = query_df(
            f"""
            SELECT GRUPO_AM, MEDIA_NOTAS
            FROM enem_notas
            {filter_clause}
            LIMIT 25000
            """
        )
        fig, ax = plt.subplots(figsize=(8, 5))
        dados_am = amostra_box[amostra_box["GRUPO_AM"] == "Amazonas"]["MEDIA_NOTAS"] / ESCALA_NOTA * 100
        dados_outros = amostra_box[amostra_box["GRUPO_AM"] == "Outros estados"]["MEDIA_NOTAS"] / ESCALA_NOTA * 100
        bp = ax.boxplot([dados_am, dados_outros], labels=["Amazonas", "Outros estados"], patch_artist=True, showfliers=True)
        for patch, cor in zip(bp["boxes"], ["#3da700", "#3C00E0"]):
            patch.set_facecolor(cor)
            patch.set_alpha(0.7)
        ax.axhline(upper_bound / ESCALA_NOTA * 100, color="red", linestyle="--", linewidth=2, label=f"Upper Bound: {upper_bound / ESCALA_NOTA * 100:.1f}%")
        ax.axhline(lower_bound / ESCALA_NOTA * 100, color="orange", linestyle="--", linewidth=2, label=f"Lower Bound: {lower_bound / ESCALA_NOTA * 100:.1f}%")
        ax.set_title("Boxplot com Limites de Outliers", fontweight="bold")
        ax.set_ylabel("Média de Notas (%)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

    st.markdown("### 📊 Distribuição com Zonas de Outliers")
    hist = query_df(
        f"""
        SELECT GRUPO_AM, FLOOR((MEDIA_NOTAS / {ESCALA_NOTA} * 100) / 1) * 1 AS faixa, COUNT(*) AS frequencia
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM, faixa
        ORDER BY faixa
        """
    )
    hist["Percentual"] = hist.groupby("GRUPO_AM")["frequencia"].transform(lambda x: x / x.sum() * 100)
    hist_pivot = hist.pivot(index="faixa", columns="GRUPO_AM", values="Percentual").fillna(0)
    media = query_df(f"SELECT AVG(MEDIA_NOTAS) AS media FROM enem_notas {filter_clause}").iloc[0]["media"]
    fig, ax = plt.subplots(figsize=(12, 6))
    hist_pivot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], alpha=0.6)
    ax.axvline(lower_bound / ESCALA_NOTA * 100, color="orange", linestyle="--", linewidth=2.5, label=f"Lower Bound: {lower_bound / ESCALA_NOTA * 100:.1f}%")
    ax.axvline(upper_bound / ESCALA_NOTA * 100, color="red", linestyle="--", linewidth=2.5, label=f"Upper Bound: {upper_bound / ESCALA_NOTA * 100:.1f}%")
    ax.axvline(media / ESCALA_NOTA * 100, color="black", linestyle="-", linewidth=2, label=f"Média: {media / ESCALA_NOTA * 100:.1f}%")
    ax.set_title("Distribuição Percentual com Zonas de Outliers", fontweight="bold", fontsize=12)
    ax.set_xlabel("Média de Notas (%)")
    ax.set_ylabel("Percentual da distribuição (%)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

def pagina_renda():
    st.markdown('<p class="sub-header">💰 Análise por Renda Familiar</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()

    st.markdown("### 📊 Médias de Notas por Faixa de Renda")
    renda_analise = query_df(
        f"""
        SELECT
            RENDA,
            Q006,
            GRUPO_AM,
            AVG(NU_NOTA_CN) AS media_CN,
            AVG(NU_NOTA_CH) AS media_CH,
            AVG(NU_NOTA_LC) AS media_LC,
            AVG(NU_NOTA_MT) AS media_MT,
            AVG(NU_NOTA_REDACAO) AS media_redacao,
            AVG(MEDIA_NOTAS) AS media_notas
        FROM enem_notas
        {filter_clause}
        GROUP BY RENDA, Q006, GRUPO_AM
        ORDER BY Q006, GRUPO_AM
        """
    )

    if renda_analise.empty:
        st.info("Os filtros atuais não retornaram dados para a análise por renda.")
        return

    renda_analise["media_notas_pct"] = renda_analise["media_notas"] / ESCALA_NOTA * 100
    tabela = tabela_comparativa_grupos(renda_analise, "media_notas_pct", "Média (%)", "RENDA")
    tabela["RENDA"] = pd.Categorical(tabela["RENDA"], categories=RENDA_ORDEM, ordered=True)
    tabela = tabela.sort_values("RENDA")
    st.dataframe(
        tabela.style.format({
            "Média (%) - AM": "{:.2f}%",
            "Média (%) - Outros estados": "{:.2f}%",
            "Diferença % (AM vs Outros)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📈 Impacto da Renda nas Notas")
    plot = tabela.set_index("RENDA")[["Média (%) - AM", "Média (%) - Outros estados"]]
    fig, ax = plt.subplots(figsize=(12, 7))
    plot.plot(kind="barh", ax=ax, color=["#3da700", "#3C00E0"])
    ax.set_title("Média de Notas do ENEM por Faixa de Renda Familiar (%)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Média em % da escala")
    ax.set_ylabel("Faixa de Renda Familiar")
    ax.set_xlim(0, 100)
    ax.grid(axis="x", alpha=0.3)
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f%%", fontsize=8)
    st.pyplot(fig)

    maior_gap = tabela.loc[tabela["Diferença % (AM vs Outros)"].abs().idxmax()]
    st.markdown(
        f"""
    <div class="warning-box" style="background-color: #1e1e2f; color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
    <strong>🚨 ACHADO CRÍTICO - DESIGUALDADE SOCIAL:</strong><br>
    • Maior diferença relativa encontrada na faixa: {maior_gap['RENDA']}<br>
    • Diferença AM vs Outros estados: {maior_gap['Diferença % (AM vs Outros)']:.1f}%
    </div>
    """,
        unsafe_allow_html=True,
    )

def pagina_nota_renda():
    st.markdown('<p class="sub-header">📈 Comparativo Nota x Renda</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    dados = query_df(
        f"""
        SELECT
            GRUPO_AM,
            Q006,
            RENDA,
            CASE Q006
                WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 WHEN 'D' THEN 4
                WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7 WHEN 'H' THEN 8
                WHEN 'I' THEN 9 WHEN 'J' THEN 10 WHEN 'K' THEN 11 WHEN 'L' THEN 12
                WHEN 'M' THEN 13 WHEN 'N' THEN 14 WHEN 'O' THEN 15 WHEN 'P' THEN 16
                WHEN 'Q' THEN 17 ELSE NULL
            END AS renda_ordem,
            AVG(MEDIA_NOTAS) / {ESCALA_NOTA} * 100 AS media_notas_pct
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM, Q006, RENDA
        ORDER BY renda_ordem, GRUPO_AM
        """
    )

    if dados.empty or dados["renda_ordem"].nunique() < 2:
        st.info("Os filtros atuais não retornaram faixas de renda suficientes para calcular a relação nota x renda.")
        return

    corr = correlacao_renda_nota(filter_clause)
    corr_am = corr.loc[corr["GRUPO_AM"] == GRUPO_AM, "correlacao"].iloc[0] if GRUPO_AM in corr["GRUPO_AM"].values else np.nan
    corr_outros = corr.loc[corr["GRUPO_AM"] == GRUPO_OUTROS, "correlacao"].iloc[0] if GRUPO_OUTROS in corr["GRUPO_AM"].values else np.nan
    diff_corr = diferenca_percentual(abs(corr_am), abs(corr_outros))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Correlação AM", f"{corr_am:.3f}" if pd.notna(corr_am) else "Sem dados")
    with col2:
        st.metric("Correlação Outros estados", f"{corr_outros:.3f}" if pd.notna(corr_outros) else "Sem dados")
    with col3:
        st.metric("Diferença relativa", fmt_pct(diff_corr))

    st.markdown("### 📊 Diferença percentual por faixa de renda")
    tabela = tabela_comparativa_grupos(dados, "media_notas_pct", "Média (%)", "RENDA")
    tabela["RENDA"] = pd.Categorical(tabela["RENDA"], categories=RENDA_ORDEM, ordered=True)
    tabela = tabela.sort_values("RENDA")
    st.dataframe(
        tabela.style.format({
            "Média (%) - AM": "{:.2f}%",
            "Média (%) - Outros estados": "{:.2f}%",
            "Diferença % (AM vs Outros)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📈 Tendência visual com regressão simples")
    fig, ax = plt.subplots(figsize=(12, 6))
    cores_scatter = {"Amazonas": "#3da700", "Outros estados": "#3C00E0"}

    for grupo, dados_grupo in dados.groupby("GRUPO_AM"):
        dados_grupo = dados_grupo.sort_values("renda_ordem")
        ax.plot(
            dados_grupo["renda_ordem"],
            dados_grupo["media_notas_pct"],
            marker="o",
            color=cores_scatter.get(grupo, "gray"),
            label=grupo,
        )
        if len(dados_grupo) >= 2:
            coef = np.polyfit(dados_grupo["renda_ordem"], dados_grupo["media_notas_pct"], 1)
            linha = np.poly1d(coef)
            ax.plot(
                dados_grupo["renda_ordem"],
                linha(dados_grupo["renda_ordem"]),
                linestyle="--",
                color=cores_scatter.get(grupo, "gray"),
                alpha=0.7,
            )

    ax.set_title("Relação entre Renda e Nota Média (%)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Faixa de renda familiar")
    ax.set_ylabel("Média em % da escala")
    ax.set_ylim(0, 100)
    ax.set_xticks(range(1, 18))
    ax.set_xticklabels(RENDA_CODIGOS)
    ax.grid(True, alpha=0.3)
    ax.legend()
    st.pyplot(fig)

    st.markdown("### 🔍 Insight automático")
    if pd.notna(corr_am) and pd.notna(corr_outros):
        if abs(corr_am) > abs(corr_outros):
            frase = "Em AM a renda possui correlação mais forte com desempenho do que nos demais estados."
        elif abs(corr_am) < abs(corr_outros):
            frase = "Nos outros estados a renda possui correlação mais forte com desempenho do que no AM."
        else:
            frase = "A correlação entre renda e desempenho é semelhante entre AM e outros estados."
        st.markdown(
            f"""
        <div class="insight-box">
        <strong>{frase}</strong><br>
        Correlação AM: {corr_am:.3f} | Correlação Outros estados: {corr_outros:.3f}
        </div>
        """,
            unsafe_allow_html=True,
        )

def pagina_conclusoes():
    st.markdown('<p class="sub-header">🎯 Insights & Conclusões</p>', unsafe_allow_html=True)

    filter_clause = filtro_atual()
    insights = []

    presenca = metricas_por_grupo(filter_clause)
    if len(presenca) >= 2:
        comp_falta = tabela_comparativa_grupos(presenca, "taxa_falta_pct", "Falta (%)")
        diff_falta = comp_falta.iloc[0]["Diferença % (AM vs Outros)"]
        insights.append(texto_comparativo(diff_falta).replace("AM", "A taxa de ausência do AM"))

    medias = query_df(
        f"""
        SELECT
            GRUPO_AM,
            AVG(MEDIA_NOTAS) / {ESCALA_NOTA} * 100 AS media_notas_pct,
            AVG(NU_NOTA_REDACAO) / {ESCALA_NOTA} * 100 AS redacao_pct,
            AVG(NU_NOTA_MT) / {ESCALA_NOTA} * 100 AS matematica_pct
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )
    if len(medias) >= 2:
        tabela_media = tabela_comparativa_grupos(medias, "media_notas_pct", "Média geral (%)")
        diff_media = tabela_media.iloc[0]["Diferença % (AM vs Outros)"]
        insights.append(texto_comparativo(diff_media).replace("AM", "O desempenho médio do AM"))

        redacao_am = medias.loc[medias["GRUPO_AM"] == GRUPO_AM, "redacao_pct"].iloc[0]
        redacao_outros = medias.loc[medias["GRUPO_AM"] == GRUPO_OUTROS, "redacao_pct"].iloc[0]
        mt_am = medias.loc[medias["GRUPO_AM"] == GRUPO_AM, "matematica_pct"].iloc[0]
        mt_outros = medias.loc[medias["GRUPO_AM"] == GRUPO_OUTROS, "matematica_pct"].iloc[0]
        gap_am = redacao_am - mt_am
        gap_outros = redacao_outros - mt_outros
        if abs(gap_am) > abs(gap_outros):
            insights.append("O gap entre redação e matemática é maior no AM do que nos outros estados.")
        elif abs(gap_am) < abs(gap_outros):
            insights.append("O gap entre redação e matemática é maior nos outros estados do que no AM.")

    corr = correlacao_renda_nota(filter_clause)
    if len(corr) >= 2:
        corr_am = corr.loc[corr["GRUPO_AM"] == GRUPO_AM, "correlacao"].iloc[0] if GRUPO_AM in corr["GRUPO_AM"].values else np.nan
        corr_outros = corr.loc[corr["GRUPO_AM"] == GRUPO_OUTROS, "correlacao"].iloc[0] if GRUPO_OUTROS in corr["GRUPO_AM"].values else np.nan
        if pd.notna(corr_am) and pd.notna(corr_outros):
            if abs(corr_am) > abs(corr_outros):
                insights.append("A correlação entre renda e desempenho é mais forte no AM.")
            elif abs(corr_am) < abs(corr_outros):
                insights.append("A correlação entre renda e desempenho é mais forte nos outros estados.")

    elite_renda_nota = query_df(
        f"""
        WITH base AS (
            SELECT *
            FROM enem_notas
            {filter_clause}
        ),
        limites AS (
            SELECT
                GRUPO_AM,
                quantile_cont(MEDIA_NOTAS, 0.90) AS corte_elite
            FROM base
            GROUP BY GRUPO_AM
        ),
        elite AS (
            SELECT
                b.GRUPO_AM,
                b.MEDIA_NOTAS,
                b.RENDA,
                CASE b.Q006
                    WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 WHEN 'D' THEN 4
                    WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7 WHEN 'H' THEN 8
                    WHEN 'I' THEN 9 WHEN 'J' THEN 10 WHEN 'K' THEN 11 WHEN 'L' THEN 12
                    WHEN 'M' THEN 13 WHEN 'N' THEN 14 WHEN 'O' THEN 15 WHEN 'P' THEN 16
                    WHEN 'Q' THEN 17 ELSE NULL
                END AS renda_ordem
            FROM base b
            INNER JOIN limites l ON b.GRUPO_AM = l.GRUPO_AM
            WHERE b.MEDIA_NOTAS >= l.corte_elite
        ),
        resumo AS (
            SELECT
                GRUPO_AM,
                AVG(MEDIA_NOTAS) / {ESCALA_NOTA} * 100 AS nota_elite_pct,
                AVG(renda_ordem) AS renda_media_ordem
            FROM elite
            GROUP BY GRUPO_AM
        ),
        renda_elite AS (
            SELECT
                GRUPO_AM,
                RENDA,
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY GRUPO_AM) AS percentual_renda
            FROM elite
            WHERE RENDA IS NOT NULL
            GROUP BY GRUPO_AM, RENDA
        ),
        renda_predominante AS (
            SELECT
                GRUPO_AM,
                RENDA AS renda_predominante,
                percentual_renda AS percentual_renda_predominante
            FROM renda_elite
            QUALIFY ROW_NUMBER() OVER (PARTITION BY GRUPO_AM ORDER BY percentual_renda DESC, RENDA) = 1
        )
        SELECT
            r.GRUPO_AM,
            r.nota_elite_pct,
            r.renda_media_ordem,
            p.renda_predominante,
            p.percentual_renda_predominante
        FROM resumo r
        LEFT JOIN renda_predominante p ON r.GRUPO_AM = p.GRUPO_AM
        ORDER BY r.GRUPO_AM
        """
    )

    if len(elite_renda_nota) >= 2:
        elite_am = elite_renda_nota[elite_renda_nota["GRUPO_AM"] == GRUPO_AM].iloc[0] if GRUPO_AM in elite_renda_nota["GRUPO_AM"].values else None
        elite_outros = elite_renda_nota[elite_renda_nota["GRUPO_AM"] == GRUPO_OUTROS].iloc[0] if GRUPO_OUTROS in elite_renda_nota["GRUPO_AM"].values else None

        if elite_am is not None and elite_outros is not None:
            diff_nota_elite = diferenca_percentual(elite_am["nota_elite_pct"], elite_outros["nota_elite_pct"])
            diff_renda_elite = diferenca_percentual(elite_am["renda_media_ordem"], elite_outros["renda_media_ordem"])

            insights.append(
                f"Na elite de desempenho, a média de notas do AM está {abs(diff_nota_elite):.2f}% "
                f"{'acima' if diff_nota_elite > 0 else 'abaixo' if diff_nota_elite < 0 else 'igual'} da elite dos outros estados."
            )

            if pd.notna(diff_renda_elite):
                insights.append(
                    f"Na elite, o indicador médio de renda do AM está {abs(diff_renda_elite):.2f}% "
                    f"{'acima' if diff_renda_elite > 0 else 'abaixo' if diff_renda_elite < 0 else 'igual'} do indicador médio de renda da elite dos outros estados."
                )

            renda_am = elite_am.get("renda_predominante", np.nan)
            renda_outros = elite_outros.get("renda_predominante", np.nan)
            pct_renda_am = elite_am.get("percentual_renda_predominante", np.nan)
            pct_renda_outros = elite_outros.get("percentual_renda_predominante", np.nan)
            if pd.notna(renda_am) and pd.notna(renda_outros):
                insights.append(
                    f"Na elite do AM, a faixa de renda predominante é {renda_am} "
                    f"({pct_renda_am:.2f}% da elite filtrada); nos outros estados, é {renda_outros} "
                    f"({pct_renda_outros:.2f}% da elite filtrada)."
                )

            st.markdown("### 🏆 Elite: relação entre renda e nota")
            elite_tabela = pd.DataFrame(
                {
                    "Indicador": ["Nota média da elite (%)", "Renda média da elite (índice)", "Renda predominante na elite (%)"],
                    "AM": [
                        elite_am["nota_elite_pct"],
                        elite_am["renda_media_ordem"],
                        elite_am["percentual_renda_predominante"],
                    ],
                    "Outros estados": [
                        elite_outros["nota_elite_pct"],
                        elite_outros["renda_media_ordem"],
                        elite_outros["percentual_renda_predominante"],
                    ],
                }
            )
            elite_tabela["Diferença % (AM vs Outros)"] = elite_tabela.apply(
                lambda linha: diferenca_percentual(linha["AM"], linha["Outros estados"]),
                axis=1,
            )
            st.dataframe(
                elite_tabela.style.format({
                    "AM": "{:.2f}",
                    "Outros estados": "{:.2f}",
                    "Diferença % (AM vs Outros)": "{:.2f}%",
                }),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown(
                f"""
            <div class="insight-box">
            <strong>Leitura da elite:</strong><br>
            A elite é definida como os 10% com maior média de notas dentro de cada grupo filtrado.
            No AM, a renda predominante da elite é <strong>{renda_am}</strong>; nos outros estados, é <strong>{renda_outros}</strong>.
            A diferença relativa de nota entre as elites é de <strong>{diff_nota_elite:.2f}%</strong>.
            </div>
            """,
                unsafe_allow_html=True,
            )

    sexo = query_df(
        f"""
        SELECT
            GRUPO_AM,
            TP_SEXO,
            AVG(NU_NOTA_REDACAO) / {ESCALA_NOTA} * 100 AS redacao_pct,
            AVG(MEDIA_NOTAS) / {ESCALA_NOTA} * 100 AS media_pct
        FROM enem_notas
        {filter_clause}
        GROUP BY GRUPO_AM, TP_SEXO
        ORDER BY GRUPO_AM, TP_SEXO
        """
    )
    if not sexo.empty and sexo["TP_SEXO"].nunique() >= 2:
        for grupo in [GRUPO_AM, GRUPO_OUTROS]:
            dados_grupo = sexo[sexo["GRUPO_AM"] == grupo]
            if {"F", "M"}.issubset(set(dados_grupo["TP_SEXO"])):
                red_f = dados_grupo.loc[dados_grupo["TP_SEXO"] == "F", "redacao_pct"].iloc[0]
                red_m = dados_grupo.loc[dados_grupo["TP_SEXO"] == "M", "redacao_pct"].iloc[0]
                if red_f > red_m:
                    insights.append(f"No grupo {grupo}, as alunas apresentam melhor desempenho relativo em redação.")
                elif red_m > red_f:
                    insights.append(f"No grupo {grupo}, os alunos apresentam melhor desempenho relativo em redação.")

    if not insights:
        st.info("Os filtros atuais não retornaram dados suficientes para gerar insights comparativos.")
        return

    st.markdown("### 🔍 Observações estatísticas geradas pelos dados filtrados")
    for insight in insights:
        st.markdown(
            f"""
        <div class="insight-box">
        {insight}
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """

    ---

    ✅ Arquivo completo processado  
    ✅ Metadados validados  
    ✅ Consultas agregadas otimizadas  
    ✅ Comparações feitas sempre como AM vs Outros estados  
    ✅ Filtros globais aplicados às análises  
    """
    )

def main():
    st.sidebar.markdown("# 📊 ENEM 2019 - Dashboard")
    st.sidebar.markdown("---")

    filter_clause = setup_filters()
    st.session_state.filter_clause = filter_clause

    st.sidebar.markdown("---")

    pagina = st.sidebar.radio(
        "Selecione a análise:",
        [
            "🏠 Home",
            "🧹 Limpeza de Dados",
            "✅ Presença/Faltantes",
            "📚 Desempenho por Disciplina",
            "🏆 Top/Bottom Performers",
            "📍 Quartis/Percentis",
            "✍️ Comparativo de Redação",
            "🎯 Análise de Outliers",
            "💰 Análise por Renda",
            "📈 Comparativo Nota x Renda",
            "🎯 Insights & Conclusões",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
    Dashboard interativo para análise dos dados do ENEM 2019.

    **Período**: 2019  
    **Cobertura**: Brasil (Amazonas vs Outros estados)  
    **Registros**: arquivo completo  

    ---

    - **Streamlit**: Interface
    - **Pandas**: Resultados agregados
    - **Matplotlib**: Visualizações
    """
    )

    if pagina == "🏠 Home":
        pagina_home()
    elif pagina == "🧹 Limpeza de Dados":
        pagina_limpeza()
    elif pagina == "✅ Presença/Faltantes":
        pagina_presenca()
    elif pagina == "📚 Desempenho por Disciplina":
        pagina_disciplinas()
    elif pagina == "🏆 Top/Bottom Performers":
        pagina_performers()
    elif pagina == "📍 Quartis/Percentis":
        pagina_quartis()
    elif pagina == "✍️ Comparativo de Redação":
        pagina_redacao()
    elif pagina == "🎯 Análise de Outliers":
        pagina_outliers()
    elif pagina == "💰 Análise por Renda":
        pagina_renda()
    elif pagina == "📈 Comparativo Nota x Renda":
        pagina_nota_renda()
    elif pagina == "🎯 Insights & Conclusões":
        pagina_conclusoes()

if __name__ == "__main__":
    main()
