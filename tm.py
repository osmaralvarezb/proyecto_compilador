"""Traducción a Python de tm.c (Louden, versión del aula): simulador de la Tiny Machine.

Mismo conjunto de instrucciones, mismos tamaños de memoria y mismos mensajes que tm.c.
La TM sólo maneja enteros.

Uso por consola (igual que tm.exe):  python tm.py programa.tm
"""

import os
import re
import sys

IADDR_SIZE = 1024
DADDR_SIZE = 1024
NO_REGS = 8
PC_REG = 7

# opCodeTab: RR, RM y RA
OPS_RR = ("HALT", "IN", "OUT", "ADD", "SUB", "MUL", "DIV")
OPS_RM = ("LD", "ST")
OPS_RA = ("LDA", "LDC", "JLT", "JLE", "JGT", "JGE", "JEQ", "JNE")

# STEPRESULT
srOKAY, srHALT, srIMEM_ERR, srDMEM_ERR, srZERODIVIDE = range(5)
stepResultTab = ["Correcto", "Ejecucion finalizada (HALT)", "Error: memoria de instrucciones",
                 "Error: memoria de datos", "Error: division entre cero"]

_LINEA = re.compile(r"^\s*(\d+)\s*:\s*([A-Za-z]+)\s*(.*)$")
_RR = re.compile(r"^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
_RM = re.compile(r"^\s*(\d+)\s*,\s*([+-]?\d+)\s*[(,]\s*(\d+)")
_NUM = re.compile(r"^\s*[+-]?\d+\s*$")


class TMError(Exception):
    pass


def op_class(op):
    if op in OPS_RR:
        return "RR"
    if op in OPS_RM:
        return "RM"
    return "RA"


def c_div(a, b):
    """División entera de C: trunca hacia cero."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


class TM:
    def __init__(self, text):
        self.iMem = [("HALT", 0, 0, 0)] * IADDR_SIZE
        self.readInstructions(text)
        self.clear()

    def clear(self):
        self.reg = [0] * NO_REGS
        self.dMem = [0] * DADDR_SIZE
        self.dMem[0] = DADDR_SIZE - 1

    def readInstructions(self, text):
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip() or line.lstrip().startswith("*"):
                continue
            m = _LINEA.match(line)
            if not m:
                raise TMError(f"Line {line_no}   Bad location")
            loc, op, rest = int(m.group(1)), m.group(2).upper(), m.group(3)
            if loc >= IADDR_SIZE:
                raise TMError(f"Line {line_no} (Instruction {loc})   Location too large")
            if op not in OPS_RR + OPS_RM + OPS_RA:
                raise TMError(f"Line {line_no} (Instruction {loc})   Illegal opcode")
            a = (_RR if op_class(op) == "RR" else _RM).match(rest)
            if not a:
                raise TMError(f"Line {line_no} (Instruction {loc})   Bad operands")
            r, d, s = (int(x) for x in a.groups())
            if r >= NO_REGS or s >= NO_REGS or (op_class(op) == "RR" and d >= NO_REGS):
                raise TMError(f"Line {line_no} (Instruction {loc})   Bad register")
            self.iMem[loc] = (op, r, d, s)

    def writeInstruction(self, loc):
        op, r, a2, a3 = self.iMem[loc]
        if op_class(op) == "RR":
            return f"{loc:5d}: {op:>6}{r:3d},{a2},{a3}"
        return f"{loc:5d}: {op:>6}{r:3d},{a2:3d}({a3})"

    def stepTM(self, input_fn, output_fn):
        """Ejecuta una instrucción. input_fn(prompt) -> str | None; output_fn(texto)."""
        reg, dMem = self.reg, self.dMem
        pc = reg[PC_REG]
        if not (0 <= pc < IADDR_SIZE):
            return srIMEM_ERR
        reg[PC_REG] = pc + 1
        op, r, a2, a3 = self.iMem[pc]
        cls = op_class(op)
        if cls == "RR":
            s, t = a2, a3
        else:
            s = a3
            m = a2 + reg[s]
            if cls == "RM" and not (0 <= m < DADDR_SIZE):
                return srDMEM_ERR

        if op == "HALT":
            output_fn(f"HALT: {r},{s},{t}\n")
            return srHALT
        if op == "IN":
            while True:
                dato = input_fn("Ingrese un numero entero (IN): ")
                if dato is None:
                    return srHALT
                if _NUM.match(dato):
                    reg[r] = int(dato)
                    break
                output_fn("Illegal value\n")
        elif op == "OUT":
            output_fn(f"Resultado del programa (OUT): {reg[r]}\n")
        elif op == "ADD":
            reg[r] = reg[s] + reg[t]
        elif op == "SUB":
            reg[r] = reg[s] - reg[t]
        elif op == "MUL":
            reg[r] = reg[s] * reg[t]
        elif op == "DIV":
            if reg[t] == 0:
                return srZERODIVIDE
            reg[r] = c_div(reg[s], reg[t])
        elif op == "LD":
            reg[r] = dMem[m]
        elif op == "ST":
            dMem[m] = reg[r]
        elif op == "LDA":
            reg[r] = m
        elif op == "LDC":
            reg[r] = a2
        elif (op == "JLT" and reg[r] < 0) or (op == "JLE" and reg[r] <= 0) \
                or (op == "JGT" and reg[r] > 0) or (op == "JGE" and reg[r] >= 0) \
                or (op == "JEQ" and reg[r] == 0) or (op == "JNE" and reg[r] != 0):
            reg[PC_REG] = m
        return srOKAY

    def go(self, input_fn, output_fn, max_steps=1_000_000, trace_fn=None):
        """Comando 'g': ejecuta hasta HALT o error. Regresa (resultado, instrucciones ejecutadas).

        max_steps no existe en tm.c; evita que un ciclo infinito congele el IDE.
        """
        result, count = srOKAY, 0
        while result == srOKAY and count < max_steps:
            if trace_fn:
                trace_fn(self.writeInstruction(self.reg[PC_REG]) if 0 <= self.reg[PC_REG] < IADDR_SIZE else "")
            result = self.stepTM(input_fn, output_fn)
            count += 1
        return result, count


def run(text, input_fn, output_fn, max_steps=1_000_000):
    """Carga el .tm y lo ejecuta completo (lo que hace el IDE)."""
    return TM(text).go(input_fn, output_fn, max_steps)


# ---------------- doCommand: modo interactivo de tm.c ----------------
AYUDA = """
COMANDOS DE LA MAQUINA TM:
 h        Mostrar esta ayuda
 v        Ver codigo intermedio (.ci) generado desde el compilador
 i b n    Ver n instrucciones TM desde la direccion b
 d b n    Ver n posiciones de memoria de datos desde b
 r        Ver el contenido de los registros
 s [n]    Ejecutar n instrucciones (por defecto 1)
 g        Ejecutar el programa hasta HALT
 t        Activar/desactivar rastreo de instrucciones
 p        Activar/desactivar contador de instrucciones
 c        Reiniciar registros y memoria de datos
 q        Salir del simulador
"""


def main(pgm_name):
    if not os.path.splitext(os.path.basename(pgm_name))[1]:
        pgm_name += ".tm"
    try:
        with open(pgm_name, encoding="utf-8") as f:
            machine = TM(f.read())
    except FileNotFoundError:
        print(f"file '{pgm_name}' not found")
        return 1
    except TMError as ex:
        print(ex)
        return 1

    def leer(prompt):
        try:
            return input(prompt)
        except EOFError:
            return None

    def escribir(s):
        print(s, end="", flush=True)

    trace = icount = False
    iloc = dloc = 0
    print("Simulador TM listo. Escriba h para ver la ayuda.")
    while True:
        linea = leer("Comando TM (h=ayuda): ")
        if linea is None:
            break
        partes = linea.split()
        if not partes:
            continue
        cmd, args = partes[0][0], partes[1:]
        nums = [int(x) for x in args if _NUM.match(x)]
        if cmd == "q":
            break
        elif cmd == "h":
            print(AYUDA)
        elif cmd == "t":
            trace = not trace
            print("Tracing now " + ("on." if trace else "off."))
        elif cmd == "p":
            icount = not icount
            print("Printing instruction count now " + ("on." if icount else "off."))
        elif cmd == "v":
            ci = os.path.splitext(pgm_name)[0] + ".ci"
            if os.path.exists(ci):
                print(f"\n======= CODIGO INTERMEDIO: {ci} =======")
                print(open(ci, encoding="utf-8").read())
                print("======= FIN DEL CODIGO INTERMEDIO =======\n")
            else:
                print(f"\nNo se encontro el codigo intermedio: {ci}\n")
        elif cmd == "r":
            for i in range(NO_REGS):
                print(f"{i}: {machine.reg[i]:4d}    ", end="\n" if i % 4 == 3 else "")
        elif cmd == "i":
            if nums:
                iloc = nums[0]
            n = nums[1] if len(nums) > 1 else 1
            while 0 <= iloc < IADDR_SIZE and n > 0:
                print(machine.writeInstruction(iloc))
                iloc += 1
                n -= 1
        elif cmd == "d":
            if nums:
                dloc = nums[0]
            n = nums[1] if len(nums) > 1 else 1
            while 0 <= dloc < DADDR_SIZE and n > 0:
                print(f"{dloc:5d}: {machine.dMem[dloc]:5d}")
                dloc += 1
                n -= 1
        elif cmd == "c":
            iloc = dloc = 0
            machine.clear()
        elif cmd in ("g", "s"):
            tr = print if trace else None
            if cmd == "g":
                result, count = machine.go(leer, escribir, max_steps=10**9, trace_fn=tr)
                if icount:
                    print(f"Number of instructions executed = {count}")
            else:
                result, n = srOKAY, abs(nums[0]) if nums else 1
                while n > 0 and result == srOKAY:
                    if tr:
                        tr(machine.writeInstruction(machine.reg[PC_REG]))
                    result = machine.stepTM(leer, escribir)
                    n -= 1
            print(stepResultTab[result])
        else:
            print(f"Command {cmd} unknown.")
    print("Fin de la simulacion TM.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <filename>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
