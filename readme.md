# Compiladores IDE

Proyecto académico desarrollado en Python para la asignatura de Compiladores.

## Características

* Análisis léxico.
* Identificación y clasificación de tokens.
* Detección de errores léxicos.
* Análisis sintáctico basado en gramática libre de contexto.
* Generación de Árbol Sintáctico Abstracto (AST).
* Visualización gráfica del árbol sintáctico mediante una interfaz desarrollada con Tkinter.
* Soporte para estructuras de control, expresiones aritméticas, declaraciones de variables y operaciones de entrada/salida.

## Tecnologías utilizadas

* Python 3
* Tkinter
* ttk / sv_ttk

## Ejecución

1. Instalar dependencias:

```bash
pip install sv-ttk
```

2. Ejecutar la aplicación:

```bash
python main.py
```

## Autor

Osmar Álvarez

## Propósito

Este proyecto fue desarrollado con fines académicos para la implementación práctica de las fases de análisis léxico y sintáctico de un compilador.

## Fase 4: generación de código y ejecución en TM

Traducción a Python de los módulos del compilador TINY de referencia:

| Archivo C | Archivo Python | Función |
|---|---|---|
| code.h / code.c | tm_code.py | Registros (pc, mp, gp, ac, ac1) y funciones emitRO, emitRM, emitSkip, emitBackup, emitRestore, emitRM_Abs |
| cgen.h / cgen.c | cgen.py | `codeGen`: recorre el árbol anotado y emite el archivo `.tm` |
| intermedio.h / intermedio.c | intermedio.py | `generarCodigoIntermedio`: código de tres direcciones (`.ci`) |
| tm.c | tm.py | Simulador de la Tiny Machine (`python tm.py programa.tm`) |

En el IDE, **Intermedio** genera `.tm` y `.ci` junto al archivo fuente (o `programa.tm` si no se ha guardado) y los muestra en las pestañas
"Código Intermedio" y "Código intermedio de tres direcciones". **Ejecutar** recompila el fuente actual y corre el `.tm` en la TM;
las entradas `IN` se piden en un cuadro de diálogo y la salida aparece en la pestaña "Ejecución".

Extensiones a la TM de Louden para cubrir el lenguaje: `DIVF` (división real), `INF` (lectura real),
`OUTC` (escribir un carácter, para cadenas y saltos de línea). `%` y `^` se generan con DIV/MUL/SUB y un ciclo.
El lenguaje no tiene menos unario: `-1` se escribe `0 - 1`.
