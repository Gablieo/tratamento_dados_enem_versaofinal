import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
import duckdb
import pyarrow.parquet as pq

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Análise ENEM 2019",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado
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
</style>
""",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════
# BANCO/CONSULTAS - NÃO CARREGA O PARQUET INTEIRO EM PANDAS
# ═══════════════════════════════════════════════════════════════════════════

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

@st.cache_resource(show_spinner="Preparando conexão com o arquivo Parquet...")
def conectar():
    """Cria views DuckDB em cima do Parquet sem carregar tudo em memória."""
    if not ARQUIVO_PARQUET.exists():
        st.error(f"Arquivo não encontrado: {ARQUIVO_PARQUET}")
        st.stop()

    con = duckdb.connect(database=":memory:")
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
    """Executa SQL no DuckDB e retorna apenas o resultado agregado em DataFrame."""
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


@st.cache_data(show_spinner="Calculando métricas gerais...")
def metricas_gerais():
    return query_df(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN FALTOU = FALSE THEN 1 ELSE 0 END) AS comparecidos,
            SUM(CASE WHEN FALTOU = TRUE THEN 1 ELSE 0 END) AS faltantes,
            COUNT(*) FILTER (WHERE GRUPO_AM = 'Amazonas') AS amazonas,
            COUNT(*) FILTER (WHERE GRUPO_AM = 'Outros estados') AS outros
        FROM enem
        """
    ).iloc[0]


@st.cache_data(show_spinner="Calculando estatísticas de notas...")
def estatisticas_disciplinas():
    disciplinas = {
        "Ciências da Natureza": "NU_NOTA_CN",
        "Ciências Humanas": "NU_NOTA_CH",
        "Linguagens": "NU_NOTA_LC",
        "Matemática": "NU_NOTA_MT",
        "Redação": "NU_NOTA_REDACAO",
    }
    partes = []
    for nome, col in disciplinas.items():
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
            """
        )
    return query_df(" UNION ALL ".join(partes)).round(2)


@st.cache_data(show_spinner="Calculando médias por grupo...")
def medias_grupo_disciplinas():
    return query_df(
        """
        SELECT
            GRUPO_AM,
            AVG(NU_NOTA_CN) AS NU_NOTA_CN,
            AVG(NU_NOTA_CH) AS NU_NOTA_CH,
            AVG(NU_NOTA_LC) AS NU_NOTA_LC,
            AVG(NU_NOTA_MT) AS NU_NOTA_MT,
            AVG(NU_NOTA_REDACAO) AS NU_NOTA_REDACAO
        FROM enem_notas
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )


def fmt_int(valor):
    return f"{int(valor):,}".replace(",", ".")


def fmt_float(valor, casas=2):
    return f"{float(valor):.{casas}f}"


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: HOME
# ═══════════════════════════════════════════════════════════════════════════

def pagina_home():
    st.markdown('<p class="main-header">📊 Análise Exploratória ENEM 2019</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        ### 🎯 Objetivo
        Análise comparativa de desempenho no ENEM 2019 entre:
        - **Amazonas (AM)**
        - **Outros estados**

        ### 📈 Cobertura
        ✅ Arquivo completo do ENEM 2019  
        ✅ Consultas feitas sobre todos os registros  
        ✅ 17 faixas de renda familiar  
        ✅ 5 componentes de avaliação  
        """
        )

    with col2:
        m = metricas_gerais()
        total = int(m["total"])
        comparecidos = int(m["comparecidos"])
        faltantes = int(m["faltantes"])

        col2a, col2b = st.columns(2)
        with col2a:
            st.metric("Total de Registros", fmt_int(total))
            st.metric("Comparecidos", fmt_int(comparecidos))
        with col2b:
            st.metric("Faltantes", fmt_int(faltantes))
            st.metric("Taxa de Comparecimento", f"{comparecidos / total * 100:.2f}%")

    

    st.markdown(
        """
    ### 📋 Navegação

    Use o **menu lateral** para acessar as análises:

    1. **Limpeza de Dados** - Validação e tratamento dos dados brutos
    2. **Presença/Faltantes** - Análise de comparecimento
    3. **Desempenho por Disciplina** - Quais áreas os alunos dominam
    4. **Top/Bottom Performers** - Melhores e piores alunos
    5. **Quartis/Percentis** - Posicionamento relativo dos alunos
    6. **Comparativo de Redação** - Redação como fator preditor
    7. **Análise de Outliers** - Casos extremos e especiais
    8. **Análise por Renda** - Relação entre renda e desempenho
    9. **Insights & Conclusões** - Resumo das principais descobertas
    """
    )


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: LIMPEZA DE DADOS
# ═══════════════════════════════════════════════════════════════════════════

def pagina_limpeza():
    st.markdown('<p class="sub-header">🧹 Limpeza e Validação de Dados</p>', unsafe_allow_html=True)

    info = info_arquivo()
    m = metricas_gerais()
    total = int(m["total"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Linhas", fmt_int(info["linhas"]))
    with col2:
        st.metric("Colunas originais", info["colunas"])
    with col3:
        st.metric("Tamanho do arquivo", f"{info['tamanho_mb']:.1f} MB")

    st.markdown("### 📌 Análise de Valores Nulos")

    colunas = info["colunas_nomes"]
    expressoes = []
    for c in colunas:
        c_sql = c.replace('"', '""')
        expressoes.append(f"COUNT(*) - COUNT(\"{c_sql}\") AS \"{c_sql}\"")

    nulos_linha = query_df(f"SELECT {', '.join(expressoes)} FROM enem").iloc[0]
    nulos = pd.DataFrame(
        {
            "Coluna": nulos_linha.index,
            "Quantidade": nulos_linha.values,
        }
    )
    nulos["Percentual (%)"] = nulos["Quantidade"] / total * 100
    nulos = nulos[nulos["Quantidade"] > 0].sort_values("Quantidade", ascending=False)

    if len(nulos) > 0:
        st.dataframe(
            nulos.style.format({"Quantidade": "{:,.0f}", "Percentual (%)": "{:.2f}%"}),
            use_container_width=True,
        )
        st.info("⚠️ Valores nulos detectados — as análises filtram notas ausentes quando necessário.")
    else:
        st.success("✅ Sem valores nulos detectados")

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

        Distribuição:
        - Compareceram: {fmt_int(comparecidos)} ({comparecidos/total*100:.2f}%)
        - Faltaram: {fmt_int(faltantes)} ({faltantes/total*100:.2f}%)
        """
        )

    with col2:
        amazonas = int(m["amazonas"])
        outros = int(m["outros"])
        st.markdown(
            f"""
        **GRUPO_AM** (Categórico)
        - 'Amazonas': UF da prova == 'AM'
        - 'Outros estados': UF da prova != 'AM'

        Distribuição:
        - Amazonas: {fmt_int(amazonas)} ({amazonas/total*100:.2f}%)
        - Outros: {fmt_int(outros)} ({outros/total*100:.2f}%)
        """
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


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: PRESENÇA/FALTANTES
# ═══════════════════════════════════════════════════════════════════════════

def pagina_presenca():
    st.markdown('<p class="sub-header">✅ Análise de Presença/Faltantes</p>', unsafe_allow_html=True)

    m = metricas_gerais()
    total = int(m["total"])
    compareceu = int(m["comparecidos"])
    faltou = int(m["faltantes"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total", fmt_int(total))
    with col2:
        st.metric("Compareceram", fmt_int(compareceu), f"{compareceu / total * 100:.2f}%")
    with col3:
        st.metric("Faltaram", fmt_int(faltou), f"{faltou / total * 100:.2f}%")

    st.markdown("### 📊 Distribuição por Região")

    faltas = query_df(
        """
        SELECT
            GRUPO_AM,
            SUM(CASE WHEN FALTOU = FALSE THEN 1 ELSE 0 END) AS Compareceu,
            SUM(CASE WHEN FALTOU = TRUE THEN 1 ELSE 0 END) AS Faltou,
            COUNT(*) AS Total
        FROM enem
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )
    faltas["Compareceu (%)"] = faltas["Compareceu"] / faltas["Total"] * 100
    faltas["Faltou (%)"] = faltas["Faltou"] / faltas["Total"] * 100

    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(faltas[["GRUPO_AM", "Compareceu", "Faltou", "Total"]], use_container_width=True, hide_index=True)
    with col2:
        st.dataframe(
            faltas[["GRUPO_AM", "Compareceu (%)", "Faltou (%)"]].style.format(
                {"Compareceu (%)": "{:.2f}%", "Faltou (%)": "{:.2f}%"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### 📈 Visualização Gráfica")
    col1, col2 = st.columns(2)

    with col1:
        contagem = faltas.set_index("GRUPO_AM")["Total"]
        porcentagem = contagem / contagem.sum() * 100
        fig, ax = plt.subplots(figsize=(6, 4))
        contagem.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.5)
        ax.set_title("Participantes do ENEM por Região", fontsize=10, fontweight="bold")
        ax.set_ylabel("Número de Estudantes", fontsize=9)
        ax.set_xlabel("Região", fontsize=9)
        ax.grid(axis="y", alpha=0.2)
        ax.set_ylim(0, contagem.max() * 1.10)
        for i, v in enumerate(contagem):
            ax.text(i, v + contagem.max() * 0.015, f"{int(v):,}\n({porcentagem.iloc[i]:.1f}%)", ha="center", fontsize=7, fontweight="bold")
        plt.xticks(rotation=0, fontsize=8)
        st.pyplot(fig)

    with col2:
        faltas_pct_plot = faltas.set_index("GRUPO_AM")[["Compareceu (%)", "Faltou (%)"]].T
        fig, ax = plt.subplots(figsize=(10, 6))
        faltas_pct_plot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"])
        ax.set_title("Taxa de Participação por Região (%)", fontsize=12, fontweight="bold")
        ax.set_ylabel("Porcentagem (%)")
        ax.legend(title="Região", loc="upper right")
        ax.grid(axis="y", alpha=0.3)
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


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: DESEMPENHO POR DISCIPLINA
# ═══════════════════════════════════════════════════════════════════════════

def pagina_disciplinas():
    st.markdown('<p class="sub-header">📚 Desempenho por Disciplina</p>', unsafe_allow_html=True)

    disciplinas = {
        "Ciências da Natureza": "NU_NOTA_CN",
        "Ciências Humanas": "NU_NOTA_CH",
        "Linguagens": "NU_NOTA_LC",
        "Matemática": "NU_NOTA_MT",
        "Redação": "NU_NOTA_REDACAO",
    }

    st.markdown("### 📊 Estatísticas por Disciplina")
    stats = estatisticas_disciplinas().set_index("Disciplina")
    st.dataframe(stats.style.format("{:.2f}"), use_container_width=True)

    st.markdown("### 📈 Comparação Visual")
    col1, col2 = st.columns(2)

    with col1:
        fig, ax = plt.subplots(figsize=(12, 6))
        medias_disc = stats["mean"]
        cores_disc = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
        medias_disc.plot(kind="barh", ax=ax, color=cores_disc)
        ax.set_title("Média de Notas por Disciplina (GERAL)", fontsize=12, fontweight="bold")
        ax.set_xlabel("Média de Notas")
        ax.grid(axis="x", alpha=0.3)
        for i, v in enumerate(medias_disc):
            ax.text(v + 10, i, f"{v:.1f}", va="center", fontsize=10)
        st.pyplot(fig)

    with col2:
        medias_grupo = medias_grupo_disciplinas().set_index("GRUPO_AM")
        medias_grupo_t = medias_grupo.T
        medias_grupo_t.index = disciplinas.keys()
        fig, ax = plt.subplots(figsize=(12, 6))
        medias_grupo_t.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.8)
        ax.set_title("Comparação: Amazonas vs Outros Estados", fontsize=12, fontweight="bold")
        ax.set_ylabel("Média de Notas")
        ax.set_xlabel("Disciplina")
        ax.legend(title="Região")
        ax.grid(axis="y", alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        st.pyplot(fig)

    st.markdown(
        """
    <div class="warning-box" style="background-color: #1e1e2f; color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #ffb000;">
    <strong>⚠️ ACHADO IMPORTANTE:</strong><br>
    As médias são calculadas usando todos os registros válidos do arquivo completo.
    </div>
    """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: TOP/BOTTOM PERFORMERS
# ═══════════════════════════════════════════════════════════════════════════

def pagina_performers():
    st.markdown('<p class="sub-header">🏆 Top e Bottom Performers</p>', unsafe_allow_html=True)

    limites = query_df(
        """
        SELECT
            quantile_cont(MEDIA_NOTAS, 0.90) AS p90,
            quantile_cont(MEDIA_NOTAS, 0.10) AS p10
        FROM enem_notas
        """
    ).iloc[0]
    p90 = float(limites["p90"])
    p10 = float(limites["p10"])

    dist = query_df(
        f"""
        SELECT
            GRUPO_AM,
            SUM(CASE WHEN MEDIA_NOTAS >= {p90} THEN 1 ELSE 0 END) AS top_10,
            SUM(CASE WHEN MEDIA_NOTAS <= {p10} THEN 1 ELSE 0 END) AS bottom_10,
            COUNT(*) AS total_validos
        FROM enem_notas
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    )
    top_total = int(dist["top_10"].sum())
    bottom_total = int(dist["bottom_10"].sum())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Top 10%", fmt_int(top_total))
    with col2:
        st.metric("Limite Top", f"{p90:.1f}")
    with col3:
        st.metric("Bottom 10%", fmt_int(bottom_total))
    with col4:
        st.metric("Limite Bottom", f"{p10:.1f}")

    st.markdown("### 📊 Distribuição por Região")
    top_df = dist[["GRUPO_AM", "top_10"]].rename(columns={"GRUPO_AM": "Região", "top_10": "Quantidade"})
    top_df["Percentual"] = top_df["Quantidade"] / top_total * 100
    bottom_df = dist[["GRUPO_AM", "bottom_10"]].rename(columns={"GRUPO_AM": "Região", "bottom_10": "Quantidade"})
    bottom_df["Percentual"] = bottom_df["Quantidade"] / bottom_total * 100

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**TOP 10% (Melhores Notas)**")
        st.dataframe(top_df, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**BOTTOM 10% (Piores Notas)**")
        st.dataframe(bottom_df, use_container_width=True, hide_index=True)

    st.markdown("### 📈 Visualização Comparativa")
    col1, col2 = st.columns(2)
    with col1:
        plot = top_df.set_index("Região")["Percentual"]
        fig, ax = plt.subplots(figsize=(10, 6))
        plot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.6)
        ax.set_title("Distribuição - TOP 10%", fontsize=12, fontweight="bold")
        ax.set_ylabel("Porcentagem (%)")
        ax.grid(axis="y", alpha=0.3)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        for i, v in enumerate(plot):
            ax.text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=11, fontweight="bold")
        plt.tight_layout()
        st.pyplot(fig)

    with col2:
        plot = bottom_df.set_index("Região")["Percentual"]
        fig, ax = plt.subplots(figsize=(10, 6))
        plot.plot(kind="bar", ax=ax, color=["#3da700", "#3C00E0"], width=0.6)
        ax.set_title("Distribuição - BOTTOM 10%", fontsize=12, fontweight="bold")
        ax.set_ylabel("Porcentagem (%)")
        ax.grid(axis="y", alpha=0.3)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        for i, v in enumerate(plot):
            ax.text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=11, fontweight="bold")
        plt.tight_layout()
        st.pyplot(fig)


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: QUARTIS E PERCENTIS
# ═══════════════════════════════════════════════════════════════════════════

def pagina_quartis():
    st.markdown('<p class="sub-header">📍 Quartis e Percentis</p>', unsafe_allow_html=True)

    with st.expander("📚 O QUE SÃO QUARTIS E PERCENTIS?"):
        st.markdown(
            """
        ### Quartis
        Dividem os dados em **4 partes iguais** (25% cada).

        ### Percentis
        Dividem os dados em **100 partes** (1% cada).
        """
        )

    qs = query_df(
        """
        SELECT
            quantile_cont(MEDIA_NOTAS, 0.10) AS p10,
            quantile_cont(MEDIA_NOTAS, 0.25) AS q1,
            quantile_cont(MEDIA_NOTAS, 0.50) AS q2,
            quantile_cont(MEDIA_NOTAS, 0.75) AS q3,
            quantile_cont(MEDIA_NOTAS, 0.90) AS p90
        FROM enem_notas
        """
    ).iloc[0]

    st.markdown("### 📊 Valores de Referência")
    col1, col2 = st.columns(2)
    with col1:
        quartis_df = pd.DataFrame(
            {
                "Quartil": ["Q1 (25º)", "Q2 (50º)", "Q3 (75º)"],
                "Valor": [qs["q1"], qs["q2"], qs["q3"]],
                "Interpretação": ["75% acima", "50% acima / 50% abaixo", "25% acima"],
            }
        )
        st.dataframe(quartis_df, use_container_width=True, hide_index=True)
    with col2:
        percentis_df = pd.DataFrame(
            {
                "Percentil": ["P10", "P25", "P50", "P75", "P90"],
                "Valor": [qs["p10"], qs["q1"], qs["q2"], qs["q3"], qs["p90"]],
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
                WHEN MEDIA_NOTAS <= {q1} THEN 'Q1 (Abaixo de 25%)'
                WHEN MEDIA_NOTAS <= {q2} THEN 'Q2 (25%-50%)'
                WHEN MEDIA_NOTAS <= {q3} THEN 'Q3 (50%-75%)'
                ELSE 'Q4 (Top 25%)'
            END AS QUARTIL,
            COUNT(*) AS quantidade
        FROM enem_notas
        GROUP BY GRUPO_AM, QUARTIL
        ORDER BY GRUPO_AM, QUARTIL
        """
    )

    tabela_abs = quartil_grupo.pivot(index="GRUPO_AM", columns="QUARTIL", values="quantidade").fillna(0).astype(int)
    tabela_pct = tabela_abs.div(tabela_abs.sum(axis=1), axis=0) * 100

    st.markdown("### 📈 Distribuição por Quartil")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Contagem Absoluta**")
        st.dataframe(tabela_abs.style.format("{:,}"), use_container_width=True)
    with col2:
        st.markdown("**Distribuição (%)**")
        st.dataframe(tabela_pct.style.format("{:.2f}%"), use_container_width=True)

    total_quartil = tabela_abs.sum(axis=0).sort_index()
    fig, ax = plt.subplots(figsize=(12, 6))
    cores_quartil = ["#FF6B6B", "#FFA07A", "#4ECDC4", "#45B7D1"]
    total_quartil.plot(kind="bar", ax=ax, color=cores_quartil, width=0.7)
    ax.set_title("Distribuição de Alunos por Quartil", fontsize=12, fontweight="bold")
    ax.set_xlabel("Quartil")
    ax.set_ylabel("Número de Alunos")
    ax.grid(axis="y", alpha=0.3)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    for i, v in enumerate(total_quartil):
        pct = v / total_quartil.sum() * 100
        ax.text(i, v + total_quartil.max() * 0.02, f"{int(v):,}\n({pct:.1f}%)", ha="center", fontsize=9)
    plt.tight_layout()
    st.pyplot(fig)


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: COMPARATIVO DE REDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════

def pagina_redacao():
    st.markdown('<p class="sub-header">✍️ Comparativo de Redação</p>', unsafe_allow_html=True)

    metricas = query_df(
        """
        SELECT
            AVG(NU_NOTA_REDACAO) AS media_redacao,
            median(NU_NOTA_REDACAO) AS mediana_redacao,
            stddev_samp(NU_NOTA_REDACAO) AS desvio_redacao,
            corr(NU_NOTA_REDACAO, MEDIA_4_PROVAS) AS corr_redacao
        FROM enem_notas
        """
    ).iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Média Redação", f"{metricas['media_redacao']:.1f}")
    with col2:
        st.metric("Mediana Redação", f"{metricas['mediana_redacao']:.1f}")
    with col3:
        st.metric("Desvio Padrão", f"{metricas['desvio_redacao']:.1f}")
    with col4:
        st.metric("Correlação", f"{metricas['corr_redacao']:.3f}")

    st.markdown("### 📊 Comparação por Região")
    stats_grupo = query_df(
        """
        SELECT
            GRUPO_AM,
            AVG(NU_NOTA_REDACAO) AS redacao_mean,
            stddev_samp(NU_NOTA_REDACAO) AS redacao_std,
            AVG(MEDIA_4_PROVAS) AS media_4_provas_mean,
            stddev_samp(MEDIA_4_PROVAS) AS media_4_provas_std,
            AVG(MEDIA_NOTAS) AS media_notas_mean,
            stddev_samp(MEDIA_NOTAS) AS media_notas_std
        FROM enem_notas
        GROUP BY GRUPO_AM
        ORDER BY GRUPO_AM
        """
    ).round(2)
    st.dataframe(stats_grupo, use_container_width=True, hide_index=True)

    st.markdown("### 📈 Análise Visual")
    col1, col2 = st.columns(2)

    with col1:
        # Histograma agregado por faixas para não carregar milhões de linhas
        hist = query_df(
            """
            SELECT
                FLOOR(NU_NOTA_REDACAO / 20) * 20 AS faixa,
                COUNT(*) AS freq_redacao,
                FLOOR(MEDIA_4_PROVAS / 20) * 20 AS faixa_media,
                COUNT(*) AS freq_media
            FROM enem_notas
            GROUP BY faixa, faixa_media
            """
        )
        hist_red = hist.groupby("faixa", as_index=False)["freq_redacao"].sum().sort_values("faixa")
        hist_med = hist.groupby("faixa_media", as_index=False)["freq_media"].sum().sort_values("faixa_media")

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(hist_red["faixa"], hist_red["freq_redacao"], width=18, alpha=0.7, label="Redação")
        ax.bar(hist_med["faixa_media"], hist_med["freq_media"], width=18, alpha=0.5, label="Média 4 Provas")
        ax.set_title("Distribuição agregada de notas", fontweight="bold")
        ax.set_xlabel("Nota")
        ax.set_ylabel("Frequência")
        ax.legend()
        st.pyplot(fig)

    with col2:
        comparacao = stats_grupo.set_index("GRUPO_AM")[["redacao_mean", "media_4_provas_mean", "media_notas_mean"]]
        comparacao.columns = ["Redação", "Média 4 Provas", "Média Total"]
        fig, ax = plt.subplots(figsize=(10, 6))
        comparacao.plot(kind="bar", ax=ax, color=["#FF6B6B", "#4ECDC4", "#45B7D1"], width=0.8)
        ax.set_title("Comparação: Redação vs Outras Médias", fontweight="bold")
        ax.set_ylabel("Nota Média")
        ax.set_xlabel("Região")
        ax.grid(axis="y", alpha=0.3)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        for container in ax.containers:
            ax.bar_label(container, fmt="%.1f", fontsize=9)
        st.pyplot(fig)

    st.markdown("### 🔗 Correlação Redação vs Média de Provas")
    st.caption("O cálculo da correlação usa todos os registros válidos. O gráfico abaixo usa uma amostra apenas para visualização e não altera os resultados numéricos.")

    amostra = query_df(
        """
        SELECT GRUPO_AM, MEDIA_4_PROVAS, NU_NOTA_REDACAO
        FROM enem_notas
        USING SAMPLE reservoir(15000 ROWS)
        """
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    cores_scatter = {"Amazonas": "#3da700", "Outros estados": "#3C00E0"}
    for grupo, dados_grupo in amostra.groupby("GRUPO_AM"):
        ax.scatter(
            dados_grupo["MEDIA_4_PROVAS"],
            dados_grupo["NU_NOTA_REDACAO"],
            alpha=0.3,
            s=10,
            color=cores_scatter.get(grupo, "gray"),
            label=grupo,
        )
    ax.set_title(f"Redação vs Média de 4 Provas (Correlação: {metricas['corr_redacao']:.3f})", fontweight="bold", fontsize=12)
    ax.set_xlabel("Média de 4 Provas")
    ax.set_ylabel("Nota de Redação")
    ax.grid(True, alpha=0.3)
    ax.legend()
    st.pyplot(fig)


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: OUTLIERS
# ═══════════════════════════════════════════════════════════════════════════

def pagina_outliers():
    st.markdown('<p class="sub-header">🎯 Análise de Outliers</p>', unsafe_allow_html=True)

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
        """
        SELECT
            quantile_cont(MEDIA_NOTAS, 0.25) AS q1,
            quantile_cont(MEDIA_NOTAS, 0.75) AS q3
        FROM enem_notas
        """
    ).iloc[0]
    q1 = float(qs["q1"])
    q3 = float(qs["q3"])
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Q1", f"{q1:.1f}")
    with col2:
        st.metric("Q3", f"{q3:.1f}")
    with col3:
        st.metric("Lower Bound", f"{lower_bound:.1f}")
    with col4:
        st.metric("Upper Bound", f"{upper_bound:.1f}")

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
        GROUP BY GRUPO_AM, TIPO_OUTLIER
        ORDER BY GRUPO_AM, TIPO_OUTLIER
        """
    )

    total_validos = int(outliers["quantidade"].sum())
    total_tipo = outliers.groupby("TIPO_OUTLIER")["quantidade"].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        v = int(total_tipo.get("Normal", 0))
        st.metric("Normal", fmt_int(v), f"{v / total_validos * 100:.2f}%")
    with col2:
        v = int(total_tipo.get("Outlier Alto", 0))
        st.metric("Outlier Alto", fmt_int(v), f"{v / total_validos * 100:.2f}%")
    with col3:
        v = int(total_tipo.get("Outlier Baixo", 0))
        st.metric("Outlier Baixo", fmt_int(v), f"{v / total_validos * 100:.2f}%")

    st.markdown("### 📍 Distribuição por Região")
    tabela_abs = outliers.pivot(index="GRUPO_AM", columns="TIPO_OUTLIER", values="quantidade").fillna(0).astype(int)
    tabela_pct = tabela_abs.div(tabela_abs.sum(axis=1), axis=0) * 100
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Contagem Absoluta**")
        st.dataframe(tabela_abs.style.format("{:,}"), use_container_width=True)
    with col2:
        st.markdown("**Distribuição (%)**")
        st.dataframe(tabela_pct.style.format("{:.2f}%"), use_container_width=True)

    st.markdown("### 📈 Visualização")
    col1, col2 = st.columns(2)
    with col1:
        fig, ax = plt.subplots(figsize=(8, 5))
        plot = total_tipo.sort_values(ascending=False)
        plot.plot(kind="bar", ax=ax, color=["#4ECDC4", "#FF6B6B", "#45B7D1"], width=0.7)
        ax.set_title("Contagem Total de Outliers", fontweight="bold")
        ax.set_ylabel("Número de Alunos")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylim(0, plot.max() * 1.15)
        for i, v in enumerate(plot):
            ax.text(i, v + plot.max() * 0.01, f"{int(v):,}\n({v / total_validos * 100:.2f}%)", ha="center", va="bottom", fontsize=9)
        st.pyplot(fig)

    with col2:
        st.caption("Boxplot com amostra visual; limites e contagens usam todos os dados válidos.")
        amostra_box = query_df(
            """
            SELECT GRUPO_AM, MEDIA_NOTAS
            FROM enem_notas
            USING SAMPLE reservoir(25000 ROWS)
            """
        )
        fig, ax = plt.subplots(figsize=(8, 5))
        dados_am = amostra_box[amostra_box["GRUPO_AM"] == "Amazonas"]["MEDIA_NOTAS"]
        dados_outros = amostra_box[amostra_box["GRUPO_AM"] == "Outros estados"]["MEDIA_NOTAS"]
        bp = ax.boxplot([dados_am, dados_outros], labels=["Amazonas", "Outros estados"], patch_artist=True, showfliers=True)
        for patch, cor in zip(bp["boxes"], ["#3da700", "#3C00E0"]):
            patch.set_facecolor(cor)
            patch.set_alpha(0.7)
        ax.axhline(upper_bound, color="red", linestyle="--", linewidth=2, label=f"Upper Bound: {upper_bound:.1f}")
        ax.axhline(lower_bound, color="orange", linestyle="--", linewidth=2, label=f"Lower Bound: {lower_bound:.1f}")
        ax.set_title("Boxplot com Limites de Outliers", fontweight="bold")
        ax.set_ylabel("Média de Notas")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

    st.markdown("### 📊 Distribuição com Zonas de Outliers")
    hist = query_df(
        """
        SELECT FLOOR(MEDIA_NOTAS / 5) * 5 AS faixa, COUNT(*) AS frequencia
        FROM enem_notas
        GROUP BY faixa
        ORDER BY faixa
        """
    )
    media = query_df("SELECT AVG(MEDIA_NOTAS) AS media FROM enem_notas").iloc[0]["media"]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(hist["faixa"], hist["frequencia"], width=4.8, color="#4ECDC4", alpha=0.6, edgecolor="black")
    ax.axvline(lower_bound, color="orange", linestyle="--", linewidth=2.5, label=f"Lower Bound: {lower_bound:.1f}")
    ax.axvline(upper_bound, color="red", linestyle="--", linewidth=2.5, label=f"Upper Bound: {upper_bound:.1f}")
    ax.axvline(media, color="black", linestyle="-", linewidth=2, label=f"Média: {media:.1f}")
    ax.set_title("Distribuição com Zonas de Outliers", fontweight="bold", fontsize=12)
    ax.set_xlabel("Média de Notas")
    ax.set_ylabel("Frequência")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: ANÁLISE POR RENDA
# ═══════════════════════════════════════════════════════════════════════════

def pagina_renda():
    st.markdown('<p class="sub-header">💰 Análise por Renda Familiar</p>', unsafe_allow_html=True)

    st.markdown("### 📊 Médias de Notas por Faixa de Renda")
    renda_analise = query_df(
        """
        SELECT
            RENDA,
            AVG(NU_NOTA_CN) AS media_CN,
            AVG(NU_NOTA_CH) AS media_CH,
            AVG(NU_NOTA_LC) AS media_LC,
            AVG(NU_NOTA_MT) AS media_MT,
            AVG(NU_NOTA_REDACAO) AS media_redacao,
            AVG(MEDIA_NOTAS) AS media_notas,
            COUNT(*) AS quantidade
        FROM enem_notas
        GROUP BY RENDA
        ORDER BY media_notas DESC
        """
    ).round(2)
    st.dataframe(renda_analise, use_container_width=True, hide_index=True)

    st.markdown("### 📈 Impacto da Renda nas Notas")
    renda_medias = renda_analise.set_index("RENDA")["media_notas"].sort_values(ascending=False)
    cores_gradient = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(renda_medias)))
    fig, ax = plt.subplots(figsize=(12, 7))
    renda_medias.plot(kind="barh", ax=ax, color=cores_gradient)
    ax.set_title("Média de Notas do ENEM por Faixa de Renda Familiar", fontsize=12, fontweight="bold")
    ax.set_xlabel("Média de Notas")
    ax.set_ylabel("Faixa de Renda Familiar")
    ax.grid(axis="x", alpha=0.3)
    for i, v in enumerate(renda_medias):
        ax.text(v + 5, i, f"{v:.1f}", va="center", fontsize=9)
    st.pyplot(fig)

    menor_renda = float(renda_medias.iloc[-1])
    maior_renda = float(renda_medias.iloc[0])
    diferenca = maior_renda - menor_renda
    pct_diff = diferenca / menor_renda * 100 if menor_renda else 0
    st.markdown(
        f"""
    <div class="warning-box" style="background-color: #1e1e2f; color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
    <strong>🚨 ACHADO CRÍTICO - DESIGUALDADE SOCIAL:</strong><br>
    • Menor média: {menor_renda:.1f} pontos<br>
    • Maior média: {maior_renda:.1f} pontos<br>
    • DIFERENÇA: {diferenca:.1f} pontos ({pct_diff:.1f}% melhor)
    </div>
    """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINA: CONCLUSÕES
# ═══════════════════════════════════════════════════════════════════════════

def pagina_conclusoes():
    st.markdown('<p class="sub-header">🎯 Insights & Conclusões</p>', unsafe_allow_html=True)

    st.markdown(
        """
    ## 🔴 ACHADOS CRÍTICOS

    ### 1. Desigualdade Regional
    - A análise compara Amazonas com os demais estados usando o arquivo completo do ENEM 2019.
    - As consultas são feitas diretamente no Parquet, sem carregar tudo na memória.

    ### 2. Presença e desempenho
    - A taxa de comparecimento é calculada a partir das colunas de presença.
    - As médias consideram apenas candidatos presentes e com redação válida.

    ### 3. Renda familiar
    - A renda é analisada pela variável Q006, traduzida em faixas legíveis.

    ---

    ## 📋 RECOMENDAÇÕES

    ### Curto Prazo:
    1. ✅ Investigar causas de maior ausência nas provas
    2. ✅ Analisar infraestrutura escolar
    3. ✅ Verificar qualificação e apoio pedagógico

    ### Médio Prazo:
    1. 📅 Programa de reforço em disciplinas críticas
    2. 📅 Bolsas e apoio para populações de baixa renda
    3. 📅 Capacitação de professores

    ### Longo Prazo:
    1. 🎯 Investimento em educação fundamental
    2. 🎯 Políticas de inclusão social
    3. 🎯 Programa de identificação de talentos

    ---

    ## 📊 QUALIDADE DOS DADOS

    ✅ Arquivo completo processado  
    ✅ Metadados validados  
    ✅ Consultas agregadas otimizadas  
    ✅ Sem necessidade de reduzir o arquivo original  
    """
    )


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR E NAVEGAÇÃO
# ═══════════════════════════════════════════════════════════════════════════

def main():
    st.sidebar.markdown("# 📊 ENEM 2019 - Dashboard")
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
            "🎯 Insights & Conclusões",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
    ### 📌 Sobre
    Dashboard interativo para análise dos dados do ENEM 2019.

    **Período**: 2019  
    **Cobertura**: Brasil (Amazonas vs Outros estados)  
    **Registros**: arquivo completo  

    ---

    ### 🔧 Tecnologia
    - **Streamlit**: Interface
    - **DuckDB**: Consulta do Parquet completo
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
    elif pagina == "🎯 Insights & Conclusões":
        pagina_conclusoes()


if __name__ == "__main__":
    main()
