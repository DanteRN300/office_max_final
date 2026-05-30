Actúa como ingeniero senior de datos, machine learning, pricing analytics y frontend. Necesito que audites y modifiques este repositorio de una app de pricing dinámico para retail de papelería tipo OfficeMax / Office Depot.

La app ya existe. Actualmente tiene una primera vista donde se cargan bases de datos, se cruza una base de ventas con una base de nivel socioeconómico, se hace limpieza de datos y se genera un diagnóstico de calidad de la base. También existe una lógica de elasticidad histórica y pricing dinámico, pero necesito reestructurar la arquitectura, mejorar la lógica de modelos, separar claramente pricing histórico de pricing futuro, agregar escenarios promocionales y mejorar el manejo de las bases NSE.

No reescribas todo desde cero. Primero audita el repositorio, identifica la tecnología usada, detecta archivos principales y después implementa cambios por fases. La prioridad es que la app quede correcta, robusta, explicable y eficiente.

============================================================
OBJETIVO GENERAL
================

Convertir la app actual en un motor de pricing dinámico basado en:

1. Calidad de datos.
2. Cruce robusto con nivel socioeconómico.
3. Bases NSE default precargadas.
4. Opción de subir bases NSE personalizadas.
5. Elasticidad histórica multi-periodo.
6. Simulación histórica de escenarios de precio.
7. Proyección futura de demanda base.
8. Simulación futura de pricing a 1 y 3 meses.
9. Recomendación explicable por SKU.
10. Escenarios promocionales como 2x1, 3x2 y segundo producto al 50%.
11. Exportables claros y válidos.
12. Filtros dependientes y dashboard ejecutivo.

La app debe quedar dividida conceptualmente en estos módulos:

1. Data Quality Engine.
2. NSE Configuration Engine.
3. Elasticity Engine.
4. Historical Pricing Simulator.
5. Demand Forecast Engine.
6. Future Pricing Simulator.
7. Recommendation Engine.
8. Executive Dashboard.
9. Exportables.

============================================================
FASE 0 — AUDITORÍA INICIAL DEL REPOSITORIO
==========================================

Antes de modificar código, revisa el repositorio completo e identifica:

* Tecnología usada: HTML/CSS/JS puro, React, Streamlit, Flask, Python u otra.
* Archivos principales.
* Archivos que controlan carga de datos.
* Archivos que hacen limpieza.
* Archivos que hacen cruce con nivel socioeconómico.
* Archivos que cargan las bases NSE actuales.
* Archivos que calculan elasticidad.
* Archivos que calculan pricing dinámico.
* Archivos que generan dashboards, filtros y descargas.
* Columnas reales disponibles en los datasets.
* Nombres reales de columnas para:

  * SKU
  * fecha
  * precio
  * unidades
  * ingreso
  * costo
  * margen
  * categoría
  * departamento
  * tienda
  * estado
  * municipio
  * nivel socioeconómico
  * categoría socioeconómica
  * tipo de marca
  * promociones
  * inventario, si existe

Detecta posibles errores por columnas faltantes, especialmente errores tipo:

* "SKU"
* "categoria_est_socio"
* "precio"
* "unidades"
* "costo_unitario"
* "margen"
* "store_nm"
* "estado"
* "municipio"

Entrega primero un resumen de auditoría con:

1. Tecnología detectada.
2. Archivos que se modificarían.
3. Columnas clave encontradas.
4. Riesgos actuales del código.
5. Cómo se están usando actualmente las bases NSE.
6. Plan de implementación por fases.

No implementes todo hasta haber identificado bien la estructura.

============================================================
FASE 1 — DATA QUALITY ENGINE
============================

La primera vista debe conservarse, pero mejorar su estructura interna.

Esta vista debe encargarse de:

* Cargar base de ventas.
* Cargar base de nivel socioeconómico / INEGI si existe.
* Cargar catálogo de productos si existe.
* Cargar costos unitarios si existe.
* Cargar promociones si existe.
* Cargar inventario si existe.
* Limpiar nombres de columnas.
* Normalizar nombres de columnas.
* Quitar espacios dobles.
* Quitar espacios al final de columnas de texto, especialmente store_nm o equivalentes.
* Convertir fechas a datetime.
* Crear variables de periodo.
* Cruzar correctamente con nivel socioeconómico.
* Evitar perder columnas importantes después del cruce.
* Crear una tabla final llamada conceptualmente ventas_limpias.

Crear estas variables de periodo:

* mes
* año
* trimestre
* semestre
* periodo_mensual
* periodo_trimestral
* periodo_semestral
* periodo_anual

El diagnóstico de calidad debe mostrar:

* registros iniciales
* registros finales
* registros eliminados
* porcentaje de registros eliminados
* nulos por columna
* duplicados eliminados
* SKUs únicos
* tiendas únicas
* categorías únicas
* departamentos únicos
* meses disponibles
* trimestres disponibles
* semestres disponibles
* años disponibles
* varianza de precio por SKU
* varianza de unidades por SKU
* SKUs con datos suficientes para elasticidad
* SKUs con datos insuficientes
* porcentaje de SKUs recomendables
* porcentaje de SKUs no recomendables
* semáforo general de calidad

Crear o mejorar una tabla interna llamada:

diagnostico_calidad

El semáforo de calidad debe funcionar así:

* Verde: base apta para pricing dinámico.
* Amarillo: base usable con restricciones.
* Rojo: base no confiable para recomendaciones automáticas.

No elimines funcionalidad actual de esta vista. Solo hazla más robusta, más ordenada y evita que columnas clave se pierdan.

============================================================
FASE 1.1 — NSE CONFIGURATION ENGINE
===================================

Actualmente el cruce con nivel socioeconómico utiliza dos archivos base para generar la asignación de NSE. Por facilidad de uso, la app debe incluir estas bases NSE precargadas por default, pero también debe permitir que el usuario suba una versión editada si el negocio quiere ajustar alguna asignación de NSE.

Objetivo:

La app debe funcionar aunque el usuario solo cargue la base de ventas. Las bases necesarias para el cruce NSE deben estar disponibles por default dentro del proyecto. Sin embargo, también debe existir la opción de reemplazarlas o editarlas mediante carga manual.

---

1. Bases NSE default

---

La app debe tener precargadas las bases necesarias para el cruce NSE.

Estas bases pueden estar guardadas en una carpeta del proyecto, por ejemplo:

* data/default_nse/
* static/data/default_nse/
* assets/nse/
* public/data/nse/

Usar la estructura que mejor se adapte al framework actual de la app.

La app debe cargar estas bases por default si el usuario no sube archivos NSE personalizados.

Agregar una variable o indicador llamado:

fuente_nse

Valores posibles:

* "default"
* "personalizada"

Si el usuario no sube base NSE, entonces:

fuente_nse = "default"

Si el usuario sube una base NSE editada, entonces:

fuente_nse = "personalizada"

---

2. Opción para subir base NSE personalizada

---

Agregar en la vista de carga de datos una sección llamada:

"Configuración de nivel socioeconómico"

Debe tener estas opciones:

* Usar base NSE default
* Subir base NSE personalizada

La opción default debe ser:

"Usar base NSE default"

Si el usuario elige subir base NSE personalizada, permitir subir los archivos necesarios para reemplazar las bases NSE default.

La app debe explicar brevemente:

"Usa esta opción si el negocio quiere ajustar la asignación de nivel socioeconómico por tienda, zona, municipio, AGEB, estado u otra unidad geográfica."

---

3. Validación de base NSE personalizada

---

Antes de usar una base NSE personalizada, validar:

* que el archivo no esté vacío
* que tenga las columnas necesarias para el cruce
* que no tenga claves duplicadas problemáticas
* que no tenga demasiados valores nulos en columnas clave
* que las columnas de unión coincidan con las columnas de la base de ventas
* que el formato sea compatible
* que el número de registros sea razonable
* que la asignación NSE tenga valores válidos

Si la base NSE personalizada no pasa la validación:

* mostrar advertencia clara
* no romper la app
* usar automáticamente la base NSE default como fallback
* indicar en el diagnóstico que la base personalizada fue rechazada

Agregar una columna o indicador:

estado_validacion_nse

Valores posibles:

* "válida"
* "inválida"
* "usada_default_por_fallback"

---

4. Cruce con NSE

---

El cruce con NSE debe funcionar con:

* bases NSE default
* bases NSE personalizadas

La lógica de cruce debe ser la misma, solamente cambia la fuente de datos.

Después del cruce, asegurar que no se pierdan columnas clave como:

* SKU
* fecha
* precio
* unidades
* ingreso
* costo
* margen
* categoría
* departamento
* tienda
* estado
* nivel socioeconómico
* categoria_est_socio, si existe

---

5. Diagnóstico del cruce NSE

---

Agregar al diagnóstico de calidad indicadores específicos del cruce NSE:

* fuente_nse usada: default o personalizada
* registros de ventas antes del cruce
* registros de ventas después del cruce
* porcentaje de registros con NSE asignado
* porcentaje de registros sin NSE asignado
* tiendas con NSE asignado
* tiendas sin NSE asignado
* categorías socioeconómicas detectadas
* valores nulos en NSE
* advertencias del cruce

Si hay registros sin NSE asignado, no eliminar automáticamente esos registros. Marcar como:

"NSE_no_asignado"

o equivalente.

---

6. Edición desde perspectiva de negocio

---

La base NSE personalizada debe permitir que el negocio modifique asignaciones cuando considere que la clasificación automática no representa bien la realidad comercial.

Ejemplo:

Una tienda puede estar ubicada en una zona con cierto NSE, pero por comportamiento de compra, ticket promedio o estrategia comercial, el negocio puede querer reclasificarla.

Por eso, el sistema debe permitir una base NSE personalizada sin cambiar el código.

---

7. Trazabilidad

---

Agregar en los resultados y exportables la fuente del NSE usado.

En ventas_limpias agregar, si aplica:

* fuente_nse
* nse_asignado
* categoria_est_socio
* nse_match_status

Valores sugeridos para nse_match_status:

* "match_default"
* "match_personalizado"
* "sin_match"
* "fallback_default"

En diagnostico_calidad agregar:

* fuente_nse_usada
* estado_validacion_nse
* porcentaje_match_nse
* registros_sin_match_nse
* advertencias_nse

---

8. Exportables NSE

---

Los exportables deben incluir información de NSE:

* ventas_limpias debe incluir la categoría NSE asignada
* diagnostico_calidad debe incluir fuente_nse y calidad del cruce
* recomendaciones_sku debe conservar variables NSE si se usan en filtros o análisis
* si se usa base NSE personalizada, indicar en el exportable que los resultados dependen de una asignación personalizada

---

9. UX recomendada

---

En la primera vista de carga de datos, mostrar:

Sección: "Nivel socioeconómico"

Opciones:

[●] Usar base NSE default
[ ] Subir base NSE personalizada

Si se selecciona "Subir base NSE personalizada", mostrar uploader de archivos.

Después del cruce, mostrar una tarjeta resumen:

* Fuente NSE usada: Default / Personalizada
* % registros con NSE asignado
* Tiendas sin NSE asignado
* Advertencias del cruce

---

10. Criterios de aceptación específicos NSE

---

La implementación es correcta si:

* La app funciona sin que el usuario suba bases NSE.
* La app usa bases NSE default automáticamente.
* El usuario puede subir bases NSE personalizadas.
* La app valida las bases NSE personalizadas.
* Si la base personalizada falla, la app usa default como fallback.
* El diagnóstico indica claramente si se usó NSE default o personalizado.
* El cruce NSE no rompe columnas clave.
* Los registros sin match NSE no se eliminan automáticamente.
* Los exportables indican la fuente NSE usada.

============================================================
FASE 2 — ELASTICITY ENGINE MULTI-PERIODO
========================================

Actualmente la elasticidad solo se calcula trimestralmente. Necesito que el sistema pueda calcular elasticidad en varios niveles:

* mensual
* trimestral
* semestral
* anual
* global por SKU
* fallback por categoría/departamento

La elasticidad será la base para el pricing dinámico, pero no debe confundirse con la proyección futura de ventas.

Crea una función general que permita calcular elasticidad usando un parámetro periodo_tipo.

periodo_tipo puede ser:

* "mensual"
* "trimestral"
* "semestral"
* "anual"
* "global_sku"
* "categoria_departamento"

La tabla resultante debe llamarse conceptualmente:

elasticidades_periodo

Debe incluir, si las columnas están disponibles:

* SKU
* categoria
* departamento
* periodo_tipo
* periodo
* fecha_inicio
* fecha_fin
* elasticidad
* r2
* p_value
* num_observaciones
* num_precios_distintos
* precio_promedio
* unidades_promedio
* ingreso_promedio
* margen_promedio
* confianza_elasticidad
* recomendable_elasticidad
* razon_no_recomendable

Reglas mínimas de confianza de elasticidad:

* Si no hay suficientes observaciones, marcar como "No usable".
* Si hay menos de 3 precios distintos, marcar como "No usable" o "Baja".
* Si la elasticidad es positiva, cero sospechosa, NaN o infinita, marcar como "No usable" o "Baja".
* Si el R2 es muy bajo, marcar como "Baja".
* Si hay suficientes datos, buena variación de precio y elasticidad negativa razonable, marcar como "Alta".
* Si hay datos aceptables pero con ruido, marcar como "Media".

Importante:

* Mantén la elasticidad trimestral actual, pero refactorízala para que use la misma lógica general.
* Evita que las elasticidades den NaN por errores de datos.
* Controla valores infinitos.
* Controla divisiones inválidas.
* Antes de modelar, elimina o corrige valores NaN, infinitos o no numéricos.
* Si no se puede calcular elasticidad para un SKU, usa fallback por categoría/departamento si existe suficiente información.
* Si tampoco existe fallback confiable, marca "No recomendar".

============================================================
FASE 3 — HISTORICAL PRICING SIMULATOR
=====================================

El pricing dinámico actual es histórico. Actualmente responde algo como:

"Si en el trimestre ene-mar 2024 hubieras subido X% el precio de X SKU, el ingreso, unidades o margen hubieran cambiado X."

Esto debe conservarse, pero debe separarse claramente como una vista o módulo de Pricing Histórico.

Esta vista debe responder:

"¿Qué habría pasado en un periodo pasado si hubiera cambiado el precio?"

Debe usar datos reales del periodo histórico seleccionado y aplicar la elasticidad correspondiente.

Filtros recomendados:

* categoría
* departamento
* periodo_tipo: mensual, trimestral, semestral, anual
* periodo
* SKU
* tipo de elasticidad usada
* escenario de precio

Escenarios simples mínimos:

* bajar precio 20%
* bajar precio 15%
* bajar precio 10%
* bajar precio 5%
* mantener precio
* subir precio 5%
* subir precio 10%
* subir precio 15%
* subir precio 20%

Escenarios promocionales adicionales:

* 2x1
* 3x2
* segundo producto al 50% de descuento

Para cada escenario calcular:

* precio_real
* precio_lista
* precio_efectivo
* descuento_efectivo
* cambio_precio_pct
* unidades_reales
* unidades_simuladas
* ingreso_real
* ingreso_simulado
* margen_real
* margen_simulado
* variacion_unidades
* variacion_ingreso
* variacion_margen
* tipo_escenario
* nombre_escenario
* mejor_escenario_historico
* recomendacion_historica
* confianza
* razon_recomendacion

La tabla interna debe llamarse conceptualmente:

pricing_historico_escenarios

Este módulo no debe predecir el futuro. Solo debe ser backtesting o simulación histórica.

============================================================
FASE 4 — DEMAND FORECAST ENGINE
===============================

Necesito agregar una nueva lógica para pricing futuro.

Importante:

El pricing futuro NO debe recalcular la elasticidad. La elasticidad ya viene del Elasticity Engine.

El pricing futuro debe estimar primero la demanda base futura:

"Con el precio actual, ¿cuántas unidades vendería este SKU en el próximo mes o en los próximos 3 meses si no cambio el precio?"

Después se aplica la elasticidad para simular escenarios de precio.

El sistema debe permitir dos horizontes futuros:

* 1 mes
* 3 meses

Para horizonte de 1 mes, la demanda base debe poder calcularse con estos enfoques:

* últimos 3 meses
* últimos 12 meses
* mismo mes histórico de años anteriores
* método híbrido recomendado

Para horizonte de 3 meses, la demanda base debe poder calcularse con estos enfoques:

* últimos 6 meses
* últimos 12 meses
* últimos 24 meses
* mismos trimestres históricos de años anteriores
* método híbrido recomendado

El método default debe ser:

Automático recomendado

Lógica inicial para horizonte de 1 mes:

demanda_base_1m =
0.50 * promedio_ultimos_3_meses

* 0.30 * promedio_ultimos_12_meses
* 0.20 * promedio_mismo_mes_historico

Lógica inicial para horizonte de 3 meses:

demanda_base_3m =
0.40 * promedio_ultimos_6_meses

* 0.30 * promedio_ultimos_24_meses
* 0.30 * promedio_mismo_trimestre_historico

Importante sobre los pesos:

Estos pesos son una heurística inicial, no una regla definitiva. Implementa la lógica para que los pesos puedan modificarse fácilmente desde una configuración. Si alguna ventana no tiene datos suficientes, redistribuye su peso proporcionalmente entre las ventanas disponibles y marca la confianza como media o baja.

Más adelante, la app debería poder optimizar estos pesos mediante backtesting histórico. Por ahora, deja la estructura preparada para que los pesos sean configurables.

La tabla interna debe llamarse conceptualmente:

demanda_base_futura

Debe incluir:

* SKU
* categoria
* departamento
* horizonte
* metodo_proyeccion
* fecha_inicio_proyeccion
* fecha_fin_proyeccion
* demanda_base
* promedio_ultimos_3_meses
* promedio_ultimos_6_meses
* promedio_ultimos_12_meses
* promedio_ultimos_24_meses
* promedio_mismo_mes_historico
* promedio_mismo_trimestre_historico
* pesos_usados
* confianza_demanda
* razon_confianza_demanda

Reglas para confianza de demanda:

* Alta: hay historia suficiente reciente y estacional.
* Media: hay historia reciente pero poca historia estacional.
* Baja: hay pocos datos o demanda muy volátil.
* No usable: no hay datos suficientes para estimar demanda base.

No uses semestre como base principal de pricing futuro. Puede quedar como referencia, pero no como método principal.

============================================================
FASE 5 — FUTURE PRICING SIMULATOR
=================================

Este nuevo módulo debe responder:

"Para el próximo mes o los próximos 3 meses, ¿qué estrategia de precio conviene para cada SKU?"

Debe tomar:

* precio_actual
* costo_unitario, si existe
* demanda_base_futura
* elasticidad ya calculada
* escenario de cambio de precio
* escenario promocional, si aplica

Para cada escenario calcular:

* precio_actual
* precio_lista
* precio_efectivo
* descuento_efectivo
* cambio_precio_pct
* demanda_base
* unidades_simuladas
* ingreso_base
* ingreso_simulado
* margen_base
* margen_simulado
* variacion_unidades
* variacion_ingreso
* variacion_margen
* elasticidad_usada
* confianza_elasticidad
* confianza_demanda
* confianza_final
* riesgo
* recomendacion
* razon_recomendacion

La fórmula conceptual para escenarios de cambio simple de precio es:

cambio_porcentual_unidades = elasticidad * cambio_porcentual_precio

unidades_simuladas = demanda_base * (1 + cambio_porcentual_unidades)

Controla que:

* no haya unidades negativas
* no haya precios negativos
* no haya márgenes inválidos
* no haya NaN
* no haya infinitos
* escenarios sospechosos se marquen como baja confianza o no recomendables

La tabla interna debe llamarse conceptualmente:

pricing_futuro_escenarios

Escenarios simples mínimos:

* -20%
* -15%
* -10%
* -5%
* 0%
* +5%
* +10%
* +15%
* +20%

============================================================
FASE 6 — ESCENARIOS PROMOCIONALES
=================================

Además de los escenarios simples de cambio porcentual de precio, la app debe simular promociones comunes en retail de papelería:

* 2x1
* 3x2
* segundo producto al 50% de descuento

Estos escenarios deben integrarse en:

1. Pricing Histórico.
2. Pricing Futuro.
3. Recommendation Engine.
4. Exportables.

---

## ESCENARIO 2x1

Interpretación:

El cliente paga 1 unidad y recibe 2 unidades.

Precio efectivo por unidad:

precio_efectivo = precio_actual / 2

Descuento efectivo aproximado:

descuento_efectivo = 50%

Cambio porcentual de precio:

cambio_precio_pct = -0.50

Unidades simuladas:

cambio_unidades_pct = elasticidad * cambio_precio_pct

unidades_simuladas = demanda_base * (1 + cambio_unidades_pct)

Ingreso simulado:

ingreso_simulado = precio_efectivo * unidades_simuladas

Margen simulado:

margen_simulado = (precio_efectivo - costo_unitario) * unidades_simuladas

Si no hay costo_unitario disponible, calcular solo ingreso_simulado y marcar margen_simulado como no disponible.

---

## ESCENARIO 3x2

Interpretación:

El cliente paga 2 unidades y recibe 3 unidades.

Precio efectivo por unidad:

precio_efectivo = precio_actual * (2 / 3)

Descuento efectivo aproximado:

descuento_efectivo = 33.33%

Cambio porcentual de precio:

cambio_precio_pct = -0.3333

Unidades simuladas:

cambio_unidades_pct = elasticidad * cambio_precio_pct

unidades_simuladas = demanda_base * (1 + cambio_unidades_pct)

Ingreso simulado:

ingreso_simulado = precio_efectivo * unidades_simuladas

Margen simulado:

margen_simulado = (precio_efectivo - costo_unitario) * unidades_simuladas

---

## ESCENARIO SEGUNDO PRODUCTO AL 50%

Interpretación:

El cliente compra 2 unidades. La primera va a precio completo y la segunda al 50%.

Precio efectivo promedio por unidad:

precio_efectivo = precio_actual * 0.75

Descuento efectivo aproximado:

descuento_efectivo = 25%

Cambio porcentual de precio:

cambio_precio_pct = -0.25

Unidades simuladas:

cambio_unidades_pct = elasticidad * cambio_precio_pct

unidades_simuladas = demanda_base * (1 + cambio_unidades_pct)

Ingreso simulado:

ingreso_simulado = precio_efectivo * unidades_simuladas

Margen simulado:

margen_simulado = (precio_efectivo - costo_unitario) * unidades_simuladas

---

## COLUMNAS PARA PROMOCIONES

Agregar estas columnas a pricing_historico_escenarios y pricing_futuro_escenarios:

* tipo_escenario
* nombre_escenario
* precio_lista
* precio_efectivo
* descuento_efectivo
* cambio_precio_pct
* elasticidad_usada
* demanda_base
* unidades_simuladas
* ingreso_simulado
* margen_simulado
* variacion_unidades
* variacion_ingreso
* variacion_margen
* riesgo_promocion
* recomendacion
* razon_recomendacion

No usar simplemente "precio_simulado" para promociones. Usar dos columnas separadas:

* precio_lista: precio visible o precio original del SKU.
* precio_efectivo: precio promedio real por unidad después de la promoción.

Esto es importante porque una promoción como 2x1 no necesariamente cambia el precio de lista, sino el precio efectivo por unidad.

---

## REGLAS DE NEGOCIO PARA PROMOCIONES

No recomendar 2x1 si:

* margen_simulado es negativo
* costo_unitario >= precio_efectivo
* elasticidad es baja en magnitud y no compensa el descuento
* la mejora en ingreso no supera claramente al escenario base
* la caída de margen es demasiado alta
* demanda_base es demasiado baja
* confianza de elasticidad es baja o no usable
* confianza de demanda es baja o no usable

No recomendar 3x2 si:

* margen_simulado es negativo
* el incremento estimado de unidades no compensa el descuento efectivo
* el SKU tiene baja confianza de demanda
* el SKU tiene baja confianza de elasticidad
* la mejora vs escenario base es pequeña

No recomendar segundo producto al 50% si:

* margen_simulado es negativo
* la promoción no mejora ingreso ni margen
* la demanda base es demasiado baja
* el SKU tiene datos insuficientes

Priorizar promociones si:

* el SKU tiene elasticidad elástica menor a -1
* el aumento esperado de unidades compensa el descuento
* el margen total mejora o la caída de margen es aceptable por objetivo comercial
* hay inventario alto, si existe columna de inventario
* el producto pertenece a una categoría de alta rotación
* el escenario promocional supera a los escenarios simples de descuento

Si no existe costo_unitario:

* elegir mejor escenario con base en ingreso_simulado
* marcar confianza_final como media o baja
* agregar razón: "No se cuenta con costo unitario, por lo que la recomendación se basa en ingreso y no en margen."

Si sí existe costo_unitario:

* elegir mejor escenario principalmente con base en margen_simulado
* usar ingreso_simulado como métrica secundaria

============================================================
FASE 7 — RECOMMENDATION ENGINE
==============================

Actualmente la app usa un Random Forest que categoriza cada SKU por trimestre en:

* subir precio
* bajar precio
* mantener precio
* no recomendar

Necesito cambiar la lógica para que el Random Forest no sea el corazón de la recomendación si solo está aprendiendo etiquetas creadas por reglas.

El corazón del Recommendation Engine debe ser:

* calidad de datos
* confianza de elasticidad
* demanda base proyectada
* simulación financiera
* impacto en ingreso
* impacto en margen
* riesgo de caída de unidades
* reglas de negocio

El Random Forest puede conservarse, pero como apoyo para riesgo/confianza o probabilidad de éxito, no como única fuente de decisión.

Implementa un motor híbrido:

---

1. Reglas de exclusión

---

Clasificar como "No recomendar" si:

* datos insuficientes
* elasticidad NaN
* elasticidad infinita
* elasticidad cero sospechosa
* elasticidad positiva
* confianza de elasticidad es "No usable"
* confianza de demanda es "No usable"
* no hay precio actual válido
* no hay unidades base válidas
* demanda_base <= 0
* precio_actual <= 0

---

2. Evaluación de escenarios

---

Comparar todos los escenarios:

* cambios simples de precio
* mantener precio
* 2x1
* 3x2
* segundo producto al 50%

Si hay costo_unitario:

* elegir el escenario que maximice margen_simulado
* usar ingreso_simulado como métrica secundaria
* evitar escenarios con margen negativo
* evitar escenarios con caída extrema de unidades

Si no hay costo_unitario:

* elegir el escenario que maximice ingreso_simulado
* marcar confianza_final como media o baja
* explicar que no se evaluó margen real por falta de costo

---

3. Clasificación final

---

La recomendación final debe tener dos niveles:

1. categoria_recomendacion:

* Subir precio
* Bajar precio / promover
* Mantener precio
* No recomendar

2. estrategia_especifica:

* Subir precio 5%
* Subir precio 10%
* Subir precio 15%
* Subir precio 20%
* Bajar precio 5%
* Bajar precio 10%
* Bajar precio 15%
* Bajar precio 20%
* 2x1
* 3x2
* Segundo producto al 50%
* Mantener precio
* No recomendar

Mapeo:

* Si el mejor escenario implica aumento de precio: categoria_recomendacion = "Subir precio".
* Si el mejor escenario implica reducción de precio o promoción: categoria_recomendacion = "Bajar precio / promover".
* Si ningún escenario mejora claramente ingreso o margen: categoria_recomendacion = "Mantener precio".
* Si los datos no son confiables: categoria_recomendacion = "No recomendar".

---

4. Explicabilidad

---

Cada recomendación debe incluir una razón textual.

Ejemplos:

* "Se recomienda subir precio porque la elasticidad es inelástica, la demanda proyectada es estable y el margen esperado mejora."
* "Se recomienda bajar precio/promover porque el SKU es elástico y el descuento aumenta unidades e ingreso esperado."
* "Se recomienda 3x2 porque el aumento estimado de unidades compensa el descuento efectivo y mejora el margen total."
* "Se recomienda mantener precio porque ningún escenario mejora margen o ingreso de forma significativa."
* "No se recomienda acción porque la elasticidad es positiva o la base tiene datos insuficientes."
* "No se recomienda 2x1 porque el margen simulado sería negativo."

La tabla final debe llamarse conceptualmente:

recomendaciones_sku

Debe incluir:

* SKU
* categoria
* departamento
* horizonte
* metodo_proyeccion
* precio_actual
* costo_unitario
* elasticidad_usada
* demanda_base
* mejor_escenario_precio
* precio_recomendado
* precio_efectivo
* descuento_efectivo
* unidades_esperadas
* ingreso_esperado
* margen_esperado
* categoria_recomendacion
* estrategia_especifica
* confianza_final
* riesgo
* razon_recomendacion
* modelo_apoyo_usado
* probabilidad_exito_si_existe

---

5. Uso del Random Forest

---

Si el Random Forest se conserva:

* No usarlo para imitar reglas.
* No usarlo como única fuente de recomendación.
* Reentrenarlo o ajustarlo solo si hay etiquetas históricas reales.
* Puede usarse para estimar:

  * probabilidad de éxito
  * riesgo
  * confianza
  * probabilidad de que una estrategia mejore margen o ingreso
* Mostrar feature importance si existe.
* Evitar sobreajuste.
* Separar train/test.
* Validar que no exista target leakage.
* Si no hay suficientes datos reales para entrenar bien, desactivar el modelo ML y usar reglas + simulación financiera.

============================================================
FASE 8 — INTERFAZ / UX
======================

La app debe tener vistas o secciones claras:

---

## Vista 1: Diagnóstico de base

Debe incluir:

* carga de archivos
* configuración de NSE
* opción de usar NSE default
* opción de subir NSE personalizada
* limpieza
* cruce NSE
* semáforo de calidad
* resumen de registros eliminados
* resumen de varianza
* nulos
* cobertura histórica
* resumen de calidad del cruce NSE

---

## Vista 2: Elasticidades

Debe incluir:

* tabla de elasticidades
* filtros por periodo_tipo
* comparación mensual/trimestral/semestral/anual
* confianza de elasticidad
* SKUs recomendables vs no recomendables

---

## Vista 3: Pricing histórico

Debe incluir:

* simulador "qué hubiera pasado si..."
* selector de periodo histórico
* selector de escenario
* comparación real vs simulado
* escenarios simples
* promociones 2x1, 3x2 y segundo al 50%

---

## Vista 4: Pricing futuro

Debe incluir:

* horizonte: 1 mes / 3 meses
* método de proyección:

  * Automático recomendado
  * Reciente
  * Estacional
  * Histórico amplio
  * Manual avanzado
* tabla de demanda base futura
* tabla de escenarios futuros
* recomendación final por SKU

---

## Vista 5: Recomendaciones ejecutivas

Debe incluir:

* ranking de SKUs
* recomendación final
* estrategia específica
* impacto esperado
* margen esperado
* ingreso esperado
* riesgo
* confianza
* razón de recomendación
* filtros por categoría, departamento, horizonte, recomendación y confianza

---

## Vista 6: Exportables

Debe incluir descargas para:

* ventas_limpias
* diagnostico_calidad
* elasticidades_periodo
* pricing_historico_escenarios
* demanda_base_futura
* pricing_futuro_escenarios
* recomendaciones_sku

---

## Selector para proyección futura

Implementa la interfaz así:

Primero:

Horizonte de pricing:

* botón o segmented control: "1 mes" y "3 meses"

Segundo:

Método de proyección:

Dropdown con:

* Automático recomendado
* Reciente
* Estacional
* Histórico amplio
* Manual avanzado

Si el usuario elige "Automático recomendado":

Para 1 mes usar:

* últimos 3 meses
* últimos 12 meses
* mismo mes histórico

Para 3 meses usar:

* últimos 6 meses
* últimos 24 meses
* mismos trimestres históricos

Si el usuario elige "Reciente":

* Para 1 mes usar últimos 3 meses.
* Para 3 meses usar últimos 6 meses.

Si el usuario elige "Estacional":

* Para 1 mes usar mismo mes histórico.
* Para 3 meses usar mismos trimestres históricos.

Si el usuario elige "Histórico amplio":

* Para 1 mes usar últimos 12 meses.
* Para 3 meses usar últimos 24 meses.

Si el usuario elige "Manual avanzado":

Mostrar checkboxes para:

* último mes registrado
* últimos 3 meses
* últimos 6 meses
* últimos 12 meses
* últimos 24 meses
* mismo mes histórico
* mismo trimestre histórico

El default debe ser:

Automático recomendado

Debajo del dropdown, muestra un texto explicativo:

"El sistema calculará la demanda base usando las ventanas históricas seleccionadas y después aplicará la elasticidad estimada para simular escenarios de precio."

============================================================
FASE 9 — FILTROS DEPENDIENTES
=============================

Los filtros dependientes deben funcionar así:

1. Categoría.
2. Departamento.
3. Periodo u horizonte.
4. SKU.

Cada filtro debe limitar las opciones disponibles de los filtros posteriores.

Ejemplo:

* Al elegir categoría, se actualizan departamentos disponibles.
* Al elegir departamento, se actualizan periodos u horizontes disponibles.
* Al elegir periodo/horizonte, se actualizan SKUs disponibles.
* Al elegir SKU, se actualizan gráficos y tablas.

No recalcular elasticidad ni escenarios cada vez que cambia un filtro visual. Los filtros deben operar sobre tablas ya calculadas.

============================================================
FASE 10 — PERFORMANCE
=====================

La app actualmente puede tardar mucho. Optimiza:

* No recalcular elasticidad cada vez que cambia un filtro.
* No recalcular escenarios cada vez que cambia un filtro visual.
* Precalcular tablas intermedias después de cargar y limpiar los datos.
* Cachear resultados pesados si el stack lo permite.
* Separar datos procesados de visualización.
* Si la app es estática en GitHub Pages, generar tablas JSON/CSV internas o procesar una sola vez en memoria y luego filtrar en frontend.
* Si hay Python/Streamlit, usar caché para funciones pesadas.
* Si hay JavaScript, evitar loops innecesarios sobre toda la base cada vez que cambia un selector.
* Para filtros dependientes, filtrar sobre tablas ya agregadas/precalculadas, no sobre raw data completa.
* Evitar recalcular el cruce con NSE si la base no cambió.
* Evitar recalcular demanda futura si el horizonte y método no cambiaron.

============================================================
FASE 11 — EXPORTABLES
=====================

Arregla el archivo descargable que actualmente no abre o sale vacío.

Debe poder descargarse, como mínimo, en CSV:

* diagnóstico de calidad
* elasticidades
* pricing histórico
* demanda base futura
* pricing futuro
* recomendaciones finales

Si se exporta Excel, asegurar que el archivo sea válido y abra correctamente.

Cada exportable debe tener nombres de columnas claros.

Evita objetos complejos que rompan el archivo.

Si una columna contiene diccionarios como pesos_usados, convertirla a string JSON antes de exportar.

Los exportables deben incluir escenarios simples y promocionales.

En pricing_historico_escenarios y pricing_futuro_escenarios deben aparecer:

* tipo_escenario
* nombre_escenario
* precio_lista
* precio_efectivo
* descuento_efectivo
* cambio_precio_pct
* unidades_simuladas
* ingreso_simulado
* margen_simulado
* categoria_recomendacion
* estrategia_especifica
* razon_recomendacion

Los exportables también deben incluir información de NSE cuando aplique:

* fuente_nse
* nse_asignado
* categoria_est_socio
* nse_match_status

============================================================
FASE 12 — VALIDACIONES Y EDGE CASES
===================================

Agregar validaciones para:

* SKU faltante
* fecha faltante
* precio faltante
* precio cero
* precio negativo
* unidades negativas
* unidades cero
* costo faltante
* costo mayor que precio
* margen negativo
* elasticidad NaN
* elasticidad infinita
* elasticidad positiva
* demanda base cero
* demanda base negativa
* periodo sin datos
* categoría sin SKUs
* SKU sin variación de precio
* SKU con pocos registros
* promociones extremas
* outliers extremos de precio
* outliers extremos de unidades
* archivos vacíos
* columnas con nombres distintos a los esperados
* base NSE default no encontrada
* base NSE personalizada inválida
* columnas NSE faltantes
* registros sin match NSE

Nunca dejar que la app truene por uno de estos casos.

Debe mostrar advertencia, clasificar como baja confianza o clasificar como "No recomendar".

Validaciones especiales para promociones:

* No permitir precio_efectivo menor o igual a cero.
* No permitir unidades_simuladas negativas.
* No recomendar promociones con margen negativo salvo que se marque explícitamente como estrategia de liquidación.
* Si costo_unitario falta, advertir que la evaluación promocional está incompleta.
* Si elasticidad es positiva, NaN o infinita, no recomendar promoción.
* Si la demanda base es muy baja, no recomendar promoción agresiva como 2x1.
* Si la confianza de elasticidad o demanda es baja, marcar promoción como alto riesgo.
* Si el descuento efectivo es muy agresivo y la mejora esperada es pequeña, no recomendar.

============================================================
CRITERIOS DE ACEPTACIÓN
=======================

La implementación se considera correcta si:

1. La vista de carga, limpieza y diagnóstico sigue funcionando.
2. El cruce con NSE no rompe columnas clave.
3. Existe una salida clara de ventas_limpias.
4. Existe diagnostico_calidad con semáforo.
5. La app funciona con bases NSE default precargadas.
6. El usuario puede subir bases NSE personalizadas.
7. La app valida la base NSE personalizada antes de usarla.
8. Si la base NSE personalizada falla, la app usa la default como fallback.
9. El diagnóstico indica si se usó NSE default o personalizada.
10. El cruce NSE no elimina registros sin match; los marca como NSE_no_asignado.
11. Los exportables incluyen la fuente NSE usada.
12. La elasticidad puede calcularse por mes, trimestre, semestre, año y global SKU.
13. La elasticidad trimestral actual se conserva.
14. Se separa claramente Pricing Histórico de Pricing Futuro.
15. Pricing Histórico permite simular escenarios pasados.
16. Pricing Histórico incluye 2x1, 3x2 y segundo al 50%.
17. Pricing Futuro permite elegir horizonte de 1 mes o 3 meses.
18. Pricing Futuro permite elegir método de proyección.
19. El método default es Automático recomendado.
20. La demanda base futura se calcula antes de aplicar elasticidad.
21. Los escenarios futuros calculan unidades, ingreso y margen simulados.
22. Pricing Futuro incluye 2x1, 3x2 y segundo al 50%.
23. La recomendación final no depende únicamente del Random Forest.
24. El Random Forest, si se conserva, funciona como apoyo para riesgo/confianza o probabilidad de éxito.
25. Cada recomendación tiene explicación textual.
26. Existen categoria_recomendacion y estrategia_especifica.
27. Los filtros dependientes funcionan en orden categoría → departamento → periodo/horizonte → SKU.
28. Los exportables descargan archivos válidos.
29. La app no recalcula procesos pesados innecesariamente.
30. No hay errores por columnas faltantes tipo "SKU".
31. La app maneja NaN, infinitos y datos insuficientes sin romperse.
32. El código queda organizado y comentado.
33. La app corre localmente.
34. La app sigue funcionando en el entorno de despliegue actual.

============================================================
FORMA DE TRABAJO
================

No implementes todo al mismo tiempo.

Trabaja por fases.

Antes de modificar código:

1. Audita el repo.
2. Resume qué archivos modificarás.
3. Identifica la tecnología usada.
4. Identifica los nombres reales de columnas.
5. Identifica cómo se cargan actualmente las bases NSE.
6. Propón un plan de cambios por fases.

Después:

1. Implementa una fase a la vez.
2. Mantén compatibilidad con la app actual.
3. No elimines funcionalidad sin justificarlo.
4. Agrega comentarios donde cambie la lógica de negocio.
5. Verifica que la app corra localmente.
6. Verifica que los exportables funcionen.
7. Verifica que no haya errores de columnas faltantes.
8. Genera un resumen final de archivos modificados y cambios aplicados.

Prioridad de implementación:

Fase 0: auditar repositorio.
Fase 1: estabilizar carga, limpieza, cruce NSE y diagnóstico.
Fase 1.1: agregar NSE default y NSE personalizada.
Fase 2: refactorizar elasticidad multi-periodo.
Fase 3: separar pricing histórico.
Fase 4: agregar demanda base futura.
Fase 5: agregar pricing futuro a 1 y 3 meses.
Fase 6: agregar escenarios promocionales.
Fase 7: cambiar Recommendation Engine a reglas + simulación financiera + ML de apoyo.
Fase 8: mejorar interfaz.
Fase 9: filtros dependientes.
Fase 10: optimizar rendimiento.
Fase 11: arreglar exportables.
Fase 12: agregar validaciones y edge cases.

No hagas cambios cosméticos innecesarios antes de estabilizar la lógica del modelo.

Prioriza que el modelo sea:

* correcto
* explicable
* robusto
* eficiente
* defendible en presentación ejecutiva
