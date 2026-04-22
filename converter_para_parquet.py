import pandas as pd
from pathlib import Path

caminho_csv = Path(__file__).parent / "DADOS" / "microdados_enem_2019.csv"
caminho_parquet = Path(__file__).parent / "DADOS" / "microdados_enem_2019.parquet"

print("Lendo CSV...")
df = pd.read_csv(
    caminho_csv,
    sep=';',
    encoding='latin-1',
    low_memory=False
)

print("Convertendo para Parquet...")
df.to_parquet(
    caminho_parquet,
    engine="pyarrow",
    index=False
)

print("Conversão concluída com sucesso.")
print(f"Arquivo salvo em: {caminho_parquet}")