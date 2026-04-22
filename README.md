# 📊 Análise Exploratória ENEM 2019

Dashboard interativo para análise comparativa de desempenho no ENEM 2019 entre **Amazonas (AM)** e **Outros Estados**.

---

## 🎯 Objetivo

Realizar análise exploratória profunda dos dados do ENEM 2019 com foco em:
- ✅ Validação e limpeza de dados
- ✅ Análise de presença/faltantes
- ✅ Desempenho por disciplina
- ✅ Identificação de top/bottom performers
- ✅ Análise de quartis e percentis
- ✅ Comparativo de redação
- ✅ Detecção de outliers
- ✅ Impacto da renda familiar

---

## 📈 Principais Descobertas

### 🔴 ACHADOS CRÍTICOS

| Achado | Impacto | Status |
|--------|--------|--------|
| Amazonas com 36.87% de falta vs 27.12% | Diferença de 9.75pp | 🚨 Crítico |
| Amazonas = 0.7% dos top 10% | Déficit de 141x | 🚨 Crítico |
| Diferença de renda = 30% de gap | 142.7 pontos | 🚨 Crítico |
| Ciências da Natureza = disciplina fraca | ~479.4 pontos | 🟡 Importante |
| Redação corr=0.626 com média | Fator preditor | 🟢 Positivo |

---

## 📁 Estrutura do Projeto

```
microdados_enem_2019/
│
├── app.py                          # Aplicação Streamlit (ESTE ARQUIVO)
├── requirements.txt                # Dependências Python
├── README.md                       # Este arquivo
│
├── DADOS/
│   ├── microdados_enem_2019.csv   # Dataset bruto (~600MB)
│   ├── ITENS_PROVA_2019.csv       # Dados dos itens
│   └── microdados.ipynb           # Análise em Jupyter
│
├── DICIONÁRIO/                     # Documentação dos dados
├── INPUTS/                         # Scripts R/SAS/SPSS
├── LEIA-ME E DOCUMENTOS TÉCNICOS/  # Documentação oficial
└── PROVAS E GABARITOS/             # Provas e soluções
```

---

## 🚀 Como Executar

### 1️⃣ Pré-requisitos

- **Python 3.8+**
- **Pip** (gestor de pacotes)
- **~600MB** de espaço em disco (para o dataset)

### 2️⃣ Instalação

**Clone ou baixe o repositório:**
```bash
cd d:\PROJETOS\Limpeza de dados\microdados_enem_2019
```

**Crie um ambiente virtual (recomendado):**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

**Instale as dependências:**
```bash
pip install -r requirements.txt
```

### 3️⃣ Executar a Aplicação

```bash
streamlit run app.py
```

A aplicação abrirá em `http://localhost:8501` no seu navegador.

---

## 📋 Navegação do Dashboard

| Seção | Descrição |
|-------|-----------|
| **🏠 Home** | Visão geral e estatísticas iniciais |
| **🧹 Limpeza de Dados** | Validação, valores nulos, qualidade |
| **✅ Presença/Faltantes** | Análise de comparecimento por região |
| **📚 Desempenho por Disciplina** | Quais áreas os alunos dominam melhor |
| **🏆 Top/Bottom Performers** | Identificação de melhores/piores alunos |
| **📍 Quartis/Percentis** | Posicionamento relativo + explicação |
| **✍️ Comparativo de Redação** | Redação como indicador de desempenho |
| **🎯 Análise de Outliers** | Casos extremos e especiais |
| **💰 Análise por Renda** | Impacto da renda familiar nas notas |
| **🎯 Insights & Conclusões** | Sumário executivo e recomendações |

---

## 🔍 Análises Disponíveis

### 1. Limpeza de Dados
- ✅ Verificação de duplicatas
- ✅ Identificação de valores nulos
- ✅ Análise de tipos de dados
- ✅ Criação de variáveis derivadas (FALTOU, GRUPO_AM, RENDA)
- ✅ Validação com assert statements

### 2. Análise de Presença
- Estatísticas gerais (total, comparecidos, faltantes)
- Distribuição por região
- Taxa de comparecimento
- Gráficos de participantes

**Validação Crítica:**
- Soma de comparecidos + faltantes = Total ✅

### 3. Desempenho por Disciplina
- Médias, medianas, desvios padrão por área
- Ranking de dificuldade
- Comparação Amazonas vs Outros Estados
- Identificação de áreas críticas

### 4. Top/Bottom Performers
- Identificação do top 10% (acima do P90)
- Identificação do bottom 10% (abaixo do P10)
- Distribuição por região
- Análise de disparidades

### 5. Quartis e Percentis
- **Q1 (25º percentil)**: 25% abaixo
- **Q2 (50º percentil)**: Mediana
- **Q3 (75º percentil)**: 25% acima
- **P10, P25, P50, P75, P90**: Percentis específicos
- Visualização de distribuição

### 6. Comparativo de Redação
- Correlação redação vs média de provas (0.626)
- Distribuição de notas
- Scatter plot de relação
- Comparação por região

### 7. Análise de Outliers
- **Método IQR**: Q1 - 1.5×IQR até Q3 + 1.5×IQR
- Identificação de casos extremos
- Distribuição por tipo (Alto/Baixo/Normal)
- Comparação por região

### 8. Análise por Renda
- 17 faixas de renda familiar
- Média de notas por faixa
- Impacto na desigualdade
- Ranking de benefício de renda

---

## 📊 Dados Utilizados

**Dataset Principal**: `DADOS/microdados_enem_2019.csv`

### Características:
- **Registros**: 5.095.171 linhas
- **Colunas**: 136 variáveis
- **Período**: Participantes do ENEM 2019
- **Codificação**: Latin-1
- **Separador**: Ponto-e-vírgula (;)

### Variáveis Principais:
- `TP_PRESENCA_CN/CH/LC/MT`: Presença por disciplina
- `NU_NOTA_CN/CH/LC/MT`: Notas por disciplina (0-1000)
- `NU_NOTA_REDACAO`: Nota de redação (0-1000)
- `SG_UF_PROVA`: Unidade federativa
- `Q006`: Renda familiar
- `TP_STATUS_REDACAO`: Status da redação

---

## 💻 Tecnologia

```
Streamlit          1.28+      # Interface interativa
Pandas             2.0+       # Manipulação de dados
NumPy              1.24+      # Computação numérica
Matplotlib         3.7+       # Visualizações
Seaborn            0.12+      # Gráficos estatísticos
```

---

## 🎨 Customizações

### Página Streamlit Customizada

```python
st.set_page_config(
    page_title="Análise ENEM 2019",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

### Cores Utilizadas
- **Amazonas**: Verde (`#3da700`)
- **Outros Estados**: Azul (`#3C00E0`)
- **Desempenho+**: Ciano/Verde
- **Desempenho-**: Vermelho/Laranja

---

## 🔐 Validações Implementadas

✅ **Assert Statements**:
```python
assert compareceu + faltou == total
# Validar que soma de categorias = total
```

✅ **Checklist de Qualidade**:
- Sem duplicatas
- Sem valores nulos críticos
- Presença consistente
- Notas válidas (0-1000)
- Grupos criados corretamente

✅ **Sincronização de Dados**:
- Mesmos dados em todas as análises
- Cache Streamlit para performance
- Sem reprocessamento desnecessário

---

## 📈 Métricas Principais

| Métrica | Valor |
|---------|-------|
| Total de Registros | 5.095.171 |
| Comparecidos | 3.701.910 (72.66%) |
| Faltantes | 1.393.261 (27.34%) |
| Amazonas | 118.144 (2.32%) |
| Outros Estados | 4.977.027 (97.68%) |
| Taxa Falta AM | 36.87% |
| Taxa Falta Outros | 27.12% |

---

## 🎯 Insights Principais

### 1. Desigualdade Regional
Amazonas está **SIGNIFICATIVAMENTE ATRÁS** em todos os indicadores:
- `Gap de 9.75pp` em presença
- `Gap de -29 pontos` em média de disciplinas
- `Gap de -54 pontos` em redação

### 2. Top Performers
- Apenas `0.7%` dos top 10% são de Amazonas
- `Esperado: 3.2%` (proporcional)
- `Déficit de 141x`

### 3. Impacto da Renda
- Sem renda: `468.0 pontos`
- Maior renda: `610.7 pontos`
- `Diferença de 30%` no desempenho

### 4. Disciplinas Críticas
- **Ciências Natureza**: `479.4` (MÁS FRACA)
- **Redação**: `596.8` (MÁS FORTE)
- **Gap médio AM**: `-27 pontos`

---

## 🛠️ Troubleshooting

### Erro: "Arquivo não encontrado"
```
FileNotFoundError: filepath_or_buffer
```
**Solução**: Certifique-se que `DADOS/microdados_enem_2019.csv` existe no caminho correto.

### Erro: "MemoryError"
```
MemoryError: Unable to allocate...
```
**Solução**: O arquivo é grande (~600MB). Aumente RAM disponível ou use filtros de dados.

### Página branca no Streamlit
**Solução**: 
```bash
streamlit cache clear
streamlit run app.py
```

### Gráficos não aparecem
**Solução**: Atualizar matplotlib e Streamlit:
```bash
pip install --upgrade streamlit matplotlib
```

---

## 📚 Referências

- [Documentação Streamlit](https://docs.streamlit.io)
- [Pandas Documentation](https://pandas.pydata.org/docs)
- [ENEM - INEP](http://inep.gov.br)

---

## 📝 Notas Importantes

⚠️ **Performance**:
- Primeira execução carrega dados (~15-30 segundos)
- Execuções posteriores usam cache (instantâneo)

⚠️ **Dados**:
- Dataset original baixado do INEP
- Processamento realizado com validações
- Sem dados sensíveis de alunos

⚠️ **Reprodutibilidade**:
- Seed fixo para gráficos
- Cache determinístico
- Resultados consistentes

---

## 👤 Autor

**Análise realizada com fins educacionais e de pesquisa**

Desenvolvido em **Python 3.x** com **Streamlit**

---

## 📄 Licença

Este projeto utiliza dados públicos do INEP/MEC.
Acesso em conformidade com legislação brasileira.

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique o `Troubleshooting` acima
2. Consulte documentação do Streamlit
3. Revise os dados em `DADOS/microdados.ipynb`

---

## ✅ Checklist de Instalação

- [ ] Python 3.8+ instalado
- [ ] Ambiente virtual criado e ativado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Dataset em `DADOS/microdados_enem_2019.csv`
- [ ] Arquivo `app.py` no diretório correto
- [ ] Executar: `streamlit run app.py`
- [ ] Browser abre em `localhost:8501`

---

**Versão**: 1.0  
**Data**: Abril/2026  
**Status**: ✅ Pronto para Produção




Atualizações para .parquet 