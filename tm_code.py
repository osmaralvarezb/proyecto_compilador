"""Equivalente en Python de code.h / code.c (Louden): utilidades para emitir instrucciones TM.

Se llama tm_code.py (y no code.py) para no ocultar el módulo estándar `code` de Python.
"""

# ---- code.h: convenciones de registros ----
pc = 7   # contador del programa
mp = 6   # "memory pointer": apunta al tope de memoria, para temporales
gp = 5   # "global pointer": base de las variables globales
ac = 0   # acumulador
ac1 = 1  # segundo acumulador
ac2 = 2  # registro auxiliar (sólo para % y ^, que la TM no trae como instrucción)


class CodeEmitter:
    """code.c: guarda las líneas del archivo .tm y maneja emitLoc / highEmitLoc."""

    def __init__(self, trace_code=True):
        self.trace_code = trace_code   # TraceCode del compilador TINY
        self.lines = []                # contenido del archivo .tm, en orden de emisión
        self.emit_loc = 0              # posición TM de la instrucción actual
        self.high_emit_loc = 0         # posición más alta emitida hasta ahora

    def emitComment(self, c):
        if self.trace_code:
            self.lines.append(f"* {c}")

    def _emit(self, loc, text, c):
        line = f"{loc:3d}:  {text}"
        if self.trace_code and c:
            line += f" \t{c}"
        self.lines.append(line)

    # instrucción de registros: op r,s,t
    def emitRO(self, op, r, s, t, c=""):
        self._emit(self.emit_loc, f"{op:>5}  {r},{s},{t}", c)
        self.emit_loc += 1
        self.high_emit_loc = max(self.high_emit_loc, self.emit_loc)

    # instrucción registro-memoria: op r,d(s)
    def emitRM(self, op, r, d, s, c=""):
        self._emit(self.emit_loc, f"{op:>5}  {r},{d}({s})", c)
        self.emit_loc += 1
        self.high_emit_loc = max(self.high_emit_loc, self.emit_loc)

    # reserva posiciones para completar saltos después; regresa la posición actual
    def emitSkip(self, how_many):
        i = self.emit_loc
        self.emit_loc += how_many
        self.high_emit_loc = max(self.high_emit_loc, self.emit_loc)
        return i

    def emitBackup(self, loc):
        if loc > self.high_emit_loc:
            self.emitComment("BUG in emitBackup")
        self.emit_loc = loc

    def emitRestore(self):
        self.emit_loc = self.high_emit_loc

    # convierte una dirección absoluta a un desplazamiento relativo a pc
    def emitRM_Abs(self, op, r, a, c=""):
        self._emit(self.emit_loc, f"{op:>5}  {r},{a - (self.emit_loc + 1)}({pc})", c)
        self.emit_loc += 1
        self.high_emit_loc = max(self.high_emit_loc, self.emit_loc)

    def text(self):
        return "\n".join(self.lines) + "\n"
