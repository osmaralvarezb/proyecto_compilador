"""Equivalente en Python de intermedio.h / intermedio.c: código intermedio de tres direcciones (.ci).

Salida didáctica: se genera desde el mismo árbol que el .tm, pero NO es la entrada de la TM.
Los temporales t1, t2... y las etiquetas L1, L2... son simbólicos.
"""

ENCABEZADO = (
    "# CODIGO INTERMEDIO DE TRES DIRECCIONES\n"
    "# Extension didactica: NO es la entrada de la TM (esa es el archivo .tm).\n"
    "# Los temporales t1, t2... y etiquetas L1, L2... son simbolicos.\n\n"
)


class ContextoIR:
    def __init__(self):
        self.lineas = []
        self.temporal = 0
        self.etiqueta = 0

    def temp(self):
        self.temporal += 1
        return f"t{self.temporal}"

    def label(self):
        self.etiqueta += 1
        return f"L{self.etiqueta}"

    def emit(self, s):
        self.lineas.append(s)

    # postorden: t = izq OP der; regresa el nombre que contiene el resultado
    def expresion(self, n):
        if n.kind in ("ENTERO", "REAL", "IDENTIFICADOR", "CADENA") or n.name in ("true", "false"):
            return n.name
        if len(n.children) == 1:  # operador unario (!)
            a = self.expresion(n.children[0])
            t = self.temp()
            self.emit(f"{t} = {n.name} {a}")
            return t
        izq = self.expresion(n.children[0])
        der = self.expresion(n.children[1])
        t = self.temp()
        self.emit(f"{t} = {izq} {n.name} {der}")
        return t

    def sentencias(self, n):
        nombre = n.name
        if nombre == "main":
            self.sentencias(n.children[0])
        elif nombre == "bloque":
            for hijo in n.children:
                self.sentencias(hijo)
        elif nombre == "decl":
            pass
        elif nombre == "cin":
            self.emit(f"read {n.children[0].name}")
        elif nombre == "cout":
            salida = n.children[0]
            for parte in (salida.children if salida.name == "<<" else [salida]):
                self.emit(f"write {self.expresion(parte)}")
            self.emit("writeln")
        elif nombre == "=":
            if n.children[1].name != "ε":
                self.emit(f"{n.children[0].name} = {self.expresion(n.children[1])}")
        elif nombre in ("++", "--"):
            x = n.children[0].name
            self.emit(f"{x} = {x} {nombre[0]} 1")
        elif nombre == "if":
            cond = self.expresion(n.children[0])
            l1 = self.label()
            self.emit(f"if_false {cond} goto {l1}")
            self.sentencias(n.children[1])
            if len(n.children) > 2:
                l2 = self.label()
                self.emit(f"goto {l2}")
                self.emit(f"label {l1}")
                self.sentencias(n.children[2])
                self.emit(f"label {l2}")
            else:
                self.emit(f"label {l1}")
        elif nombre == "while":
            l1, l2 = self.label(), self.label()
            self.emit(f"label {l1}")
            cond = self.expresion(n.children[0])
            self.emit(f"if_false {cond} goto {l2}")
            self.sentencias(n.children[1])
            self.emit(f"goto {l1}")
            self.emit(f"label {l2}")
        elif nombre in ("do-while", "do-until"):
            l1 = self.label()
            self.emit(f"label {l1}")
            self.sentencias(n.children[0])
            cond = self.expresion(n.children[1])
            salto = "if_true" if nombre == "do-while" else "if_false"
            self.emit(f"{salto} {cond} goto {l1}")


def generarCodigoIntermedio(raiz):
    """Regresa el texto del archivo .ci para el árbol validado."""
    ctx = ContextoIR()
    ctx.sentencias(raiz)
    ctx.emit("halt")
    return ENCABEZADO + "\n".join(ctx.lineas) + "\n"
