# App de Pricing Dinámico, Elasticidad y Proyección de Ventas

Aplicación web en **Streamlit** para retail mexicano. Permite cargar ventas, limpiar datos, cruzar NSE, diagnosticar calidad, calcular elasticidad por SKU-trimestre, simular escenarios de pricing y descargar recomendaciones.

## Estructura del repositorio

```text
pricing-dinamico-retail/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── convertir_a_parquet.py
│
├── .streamlit/
│   └── config.toml
│
├── modules/
│   ├── __init__.py
│   ├── config.py
│   ├── utils.py
│   ├── quality.py
│   ├── elasticity.py
│   └── pricing.py
│
├── data/       # opcional, no subir bases grandes a GitHub
└── assets/     # opcional
```

## Columnas mínimas esperadas en ventas

La base de ventas debe incluir como mínimo:

- `tran_date`
- `qty`
- `net_sale`
- `prod_nbr`
- `costo2`

Columnas recomendadas para enriquecer análisis:

- `dept_nm`
- `subdept_nm`
- `marca`
- `tipo_marca`
- `store_nm`
- `estado`
- `key`
- `categoria_est_socio`

## Optimización de velocidad incluida

Esta versión está optimizada para bases grandes y deploy:

1. **Solo corre una vista a la vez.** El router de `app.py` ejecuta únicamente la vista activa.
2. **No calcula todo al abrir.** La app solo procesa ventas cuando presionas **Procesar / actualizar datos**.
3. **Elasticidad bajo demanda.** La vista 2 calcula elasticidad únicamente al presionar **Calcular / actualizar elasticidad**.
4. **Pricing bajo demanda.** La vista 3 calcula simulaciones únicamente al presionar **Calcular / actualizar pricing**.
5. **Caché de sesión para cálculos pesados.** Limpieza, NSE, elasticidad y pricing se guardan en `st.session_state` con firmas de archivo para no recalcular al mover filtros.
6. **`st.cache_data` para lectura y gráficas.** La lectura de archivos y agregaciones visuales usan caché.
7. **Fecha corregida y más rápida.** `tran_date` se parsea con formato mexicano `dd/mm/YYYY` y fallbacks seguros, evitando el warning de pandas.
8. **Lectura por columnas necesarias.** Por defecto solo carga columnas usadas por limpieza, NSE, elasticidad, pricing, filtros y descargas.
9. **CSV más rápido con PyArrow.** Intenta leer CSV con `engine="pyarrow"`; si falla, usa pandas tradicional.
10. **Pricing vectorizado.** La simulación de escenarios usa cross join vectorizado en lugar de loops fila por fila.
11. **Random Forest desactivado por defecto.** Para rendimiento, la categoría se calcula con reglas del notebook. Puedes activarlo en `modules/config.py`.

## Recomendación más importante para bases grandes

Convierte tu base de ventas a **Parquet** una sola vez. Parquet suele cargar mucho más rápido que CSV o Excel.

```powershell
python convertir_a_parquet.py ventas.csv ventas.parquet
```

Luego sube `ventas.parquet` en la app.

## Cómo correr localmente en PowerShell

```powershell
cd "C:\Users\Lenovo\Desktop\TEC\6to semestre\pricing_turbo"
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
streamlit run app.py
```

Si PowerShell no activa el entorno, usa CMD:

```cmd
cd "C:\Users\Lenovo\Desktop\TEC\6to semestre\pricing_turbo"
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
streamlit run app.py
```

## Flujo recomendado dentro de la app

1. Entra a la vista **Carga y diagnóstico de datos**.
2. Sube ventas, promociones opcionales y NSE opcional.
3. Presiona **Procesar / actualizar datos**.
4. Entra a **Elasticidad** y presiona **Calcular / actualizar elasticidad**.
5. Entra a **Pricing dinámico + proyección de ventas** y presiona **Calcular / actualizar pricing**.
6. Ya puedes mover filtros sin recalcular los modelos completos.

## Variables de configuración útiles

En `modules/config.py`:

```python
LEER_SOLO_COLUMNAS_NECESARIAS = True
USE_RANDOM_FOREST_CLASSIFIER = False
MAX_SKUS_CURVA_ELASTICIDAD = 8
MAX_ROWS_PREVIEW = 30
```

Para más velocidad, deja `LEER_SOLO_COLUMNAS_NECESARIAS=True` y `USE_RANDOM_FOREST_CLASSIFIER=False`.

## Librerías usadas

- `streamlit`: interfaz web.
- `pandas` y `numpy`: manipulación de datos.
- `plotly`: visualizaciones interactivas.
- `statsmodels`: regresión OLS log-log para elasticidad.
- `scikit-learn`: disponible si activas Random Forest.
- `openpyxl`: lectura de Excel.
- `pyarrow`: lectura/escritura rápida de CSV/Parquet.

## Notas importantes

La app mantiene la lógica analítica central:

- Limpieza crítica de ventas.
- Limpieza de `store_nm`.
- Creación de precio unitario, ingreso y margen.
- Semáforo de calidad.
- Cruce NSE flexible.
- Elasticidad log-log por SKU y trimestre.
- Fallback de elasticidad por SKU global, subdepartamento, departamento y total trimestre.
- Simulación con fórmula exponencial de elasticidad.
- Selección de mejor escenario por categoría.

Cuando una columna no existe, la app muestra errores o advertencias claras en lugar de romperse.
