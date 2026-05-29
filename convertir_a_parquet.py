"""Convierte CSV o Excel a Parquet para acelerar la carga en Streamlit.

Uso básico:
    python convertir_a_parquet.py ventas.csv ventas.parquet
    python convertir_a_parquet.py ventas.xlsx ventas.parquet

Parquet es muy recomendable para bases grandes porque Streamlit/pandas lo leen
más rápido que CSV o Excel.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

COLUMNAS_RECOMENDADAS = [
    "tran_date", "qty", "net_sale", "prod_nbr", "SKU", "costo2",
    "precio_base", "ingreso_base", "margen_unitario", "margen_total",
    "store_nm", "dept_nm", "subdept_nm", "marca", "tipo_marca",
    "categoria_est_socio", "estado", "key", "id_municipio", "ubica_geo",
]


def _read_csv_fast(path: Path) -> pd.DataFrame:
    """Lee CSV intentando primero PyArrow y después pandas tradicional."""
    ultimo_error = None
    for encoding in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
        try:
            return pd.read_csv(path, encoding=encoding, engine="pyarrow")
        except Exception as exc:
            ultimo_error = exc
            try:
                df = pd.read_csv(path, encoding=encoding, low_memory=False)
                if df.shape[1] == 1 and ";" in str(df.columns[0]):
                    df = pd.read_csv(path, encoding=encoding, sep=";", low_memory=False)
                return df
            except UnicodeDecodeError as exc2:
                ultimo_error = exc2
                continue
    raise ValueError(f"No se pudo leer el CSV. Último detalle: {ultimo_error}")


def main() -> None:
    if len(sys.argv) not in [3, 4]:
        print("Uso: python convertir_a_parquet.py archivo_entrada.csv archivo_salida.parquet [--solo-columnas]")
        raise SystemExit(1)

    entrada = Path(sys.argv[1])
    salida = Path(sys.argv[2])
    solo_columnas = len(sys.argv) == 4 and sys.argv[3] == "--solo-columnas"

    if not entrada.exists():
        print(f"No existe el archivo de entrada: {entrada}")
        raise SystemExit(1)

    print(f"Leyendo: {entrada}")

    if entrada.suffix.lower() == ".csv":
        df = _read_csv_fast(entrada)
    elif entrada.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(entrada)
    else:
        print("Formato no soportado. Usa CSV, XLSX o XLS.")
        raise SystemExit(1)

    df.columns = df.columns.astype(str).str.strip()

    if solo_columnas:
        cols = [c for c in COLUMNAS_RECOMENDADAS if c in df.columns]
        if cols:
            df = df[cols].copy()
            print(f"Se conservaron {len(cols)} columnas recomendadas.")
        else:
            print("No se encontraron columnas recomendadas; se conserva el archivo completo.")

    print(f"Filas: {len(df):,} | Columnas: {len(df.columns):,}")
    print(f"Guardando: {salida}")
    df.to_parquet(salida, index=False, compression="snappy")
    print("Listo. Sube el archivo .parquet en la app para que cargue más rápido.")


if __name__ == "__main__":
    main()
