"""Equivalente en Python de tm.c (Louden): simulador de la Tiny Machine.

Carga un archivo .tm (texto) y lo ejecuta. Registros y memoria guardan int o float.
Uso por consola:  python tm.py programa.tm
"""

import re
import sys

IADDR_SIZE = 8192   # tm.c usa 1024; se amplía porque las cadenas de cout ocupan 2 instrucciones por carácter
DADDR_SIZE = 1024
NO_REGS = 8
PC_REG = 7

OPS_RO = {"HALT", "IN", "INF", "OUT", "OUTC", "ADD", "SUB", "MUL", "DIV", "DIVF"}
OPS_RM = {"LD", "ST"}
OPS_RA = {"LDA", "LDC", "JLT", "JLE", "JGT", "JGE", "JEQ", "JNE"}

_LINEA = re.compile(r"^\s*(\d+):\s*([A-Z]+)\s+(\S+)")
_RO = re.compile(r"^(\d+),(\d+),(\d+)$")
_RM = re.compile(r"^(\d+),(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\((\d+)\)$")


class TMError(Exception):
    pass


def read_instructions(text):
    """readInstructions: regresa la memoria de instrucciones como dict {loc: (op, a1, a2, a3)}."""
    imem = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        m = _LINEA.match(line)
        if not m:
            raise TMError(f"Línea {line_no}: instrucción mal formada: {line.strip()}")
        loc, op, args = int(m.group(1)), m.group(2), m.group(3)
        if loc >= IADDR_SIZE:
            raise TMError(f"Línea {line_no}: ubicación demasiado grande ({loc})")
        if op in OPS_RO:
            a = _RO.match(args)
        elif op in OPS_RM or op in OPS_RA:
            a = _RM.match(args)
        else:
            raise TMError(f"Línea {line_no}: opcode ilegal '{op}'")
        if not a:
            raise TMError(f"Línea {line_no}: operandos inválidos '{args}'")
        r, d, s = a.groups()
        d = float(d) if any(c in d for c in ".e") else int(d)
        imem[loc] = (op, int(r), d, int(s))
    return imem


def format_value(v):
    if isinstance(v, float):
        return repr(round(v, 6))
    return str(v)


def run(text, input_fn, output_fn, max_steps=2_000_000):
    """Ejecuta el código TM hasta HALT.

    input_fn(prompt) -> str | None  (None cancela la ejecución)
    output_fn(texto)                (sin salto de línea automático)
    Regresa (estado, pasos). estado: "HALT", "ZERO_DIVIDE", "DMEM_ERR", "IMEM_ERR",
    "STEP_LIMIT" o "INPUT_CANCEL".
    """
    imem = read_instructions(text)
    reg = [0] * NO_REGS
    dmem = [0] * DADDR_SIZE
    dmem[0] = DADDR_SIZE - 1

    for steps in range(1, max_steps + 1):
        pc = reg[PC_REG]
        if not (0 <= pc < IADDR_SIZE):
            return "IMEM_ERR", steps
        reg[PC_REG] = pc + 1
        op, r, b, c = imem.get(pc, ("HALT", 0, 0, 0))

        if op in OPS_RO:
            s, t = b, c
            if op == "HALT":
                return "HALT", steps
            if op in ("IN", "INF"):
                tipo = int if op == "IN" else float
                while True:
                    dato = input_fn("Ingrese un número entero (IN): " if op == "IN" else "Ingrese un número real (INF): ")
                    if dato is None:
                        return "INPUT_CANCEL", steps
                    try:
                        reg[r] = tipo(dato.strip())
                        break
                    except ValueError:
                        output_fn(f"Valor ilegal: {dato!r}\n")
            elif op == "OUT":
                output_fn(format_value(reg[r]))
            elif op == "OUTC":
                output_fn(chr(int(reg[r])))
            elif op == "ADD":
                reg[r] = reg[s] + reg[t]
            elif op == "SUB":
                reg[r] = reg[s] - reg[t]
            elif op == "MUL":
                reg[r] = reg[s] * reg[t]
            elif op in ("DIV", "DIVF"):
                if reg[t] == 0:
                    return "ZERO_DIVIDE", steps
                if op == "DIV" and isinstance(reg[s], int) and isinstance(reg[t], int):
                    reg[r] = int(reg[s] / reg[t])  # truncada hacia cero, como en C
                else:
                    reg[r] = reg[s] / reg[t]
        else:
            m = b + reg[c]
            if op in OPS_RM:
                if not (0 <= m < DADDR_SIZE):
                    return "DMEM_ERR", steps
                if op == "LD":
                    reg[r] = dmem[m]
                else:
                    dmem[m] = reg[r]
            elif op == "LDA":
                reg[r] = m
            elif op == "LDC":
                reg[r] = b
            elif (op == "JLT" and reg[r] < 0) or (op == "JLE" and reg[r] <= 0) \
                    or (op == "JGT" and reg[r] > 0) or (op == "JGE" and reg[r] >= 0) \
                    or (op == "JEQ" and reg[r] == 0) or (op == "JNE" and reg[r] != 0):
                reg[PC_REG] = m
    return "STEP_LIMIT", max_steps


MENSAJES = {
    "HALT": "Programa terminado (HALT).",
    "ZERO_DIVIDE": "Error de ejecución: división entre cero.",
    "DMEM_ERR": "Error de ejecución: acceso fuera de la memoria de datos.",
    "IMEM_ERR": "Error de ejecución: acceso fuera de la memoria de instrucciones.",
    "STEP_LIMIT": "Ejecución detenida: se alcanzó el límite de pasos (¿ciclo infinito?).",
    "INPUT_CANCEL": "Ejecución cancelada por el usuario.",
}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python tm.py programa.tm")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    def _leer(prompt):
        try:
            return input(prompt)
        except EOFError:
            return None

    estado, pasos = run(codigo, _leer, lambda s: print(s, end="", flush=True))
    print(f"{MENSAJES[estado]} ({pasos} instrucciones)")
