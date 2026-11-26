"""Equivalente en Python de cgen.h / cgen.c (Louden): recorre el árbol anotado y emite código TM.

Correspondencia árbol TINY -> árbol de este compilador (ParseNode):
  StmtK IfK      -> "if"        [condición, bloque_then, bloque_else?]
  StmtK RepeatK  -> "do-until"  [bloque, condición]   (+ "do-while" y "while", que TINY no tiene)
  StmtK AssignK  -> "="         [id, expresión]        (+ "++" / "--" [id])
  StmtK ReadK    -> "cin"       [id]
  StmtK WriteK   -> "cout"      [salida]  (salida puede llevar cadenas unidas con "<<")
  ExpK  ConstK   -> hoja ENTERO / REAL / true / false
  ExpK  IdK      -> hoja IDENTIFICADOR
  ExpK  OpK      -> nodo operador binario (+ - * / % ^ < <= > >= == != && ||) o unario (!)
  sibling        -> hijos de un nodo "bloque"

Extensiones a la TM de Louden (implementadas en tm.py):
  DIVF  división real (DIV es entera, truncada como en C)
  INF   lectura de un valor real (IN lee entero)
  OUTC  escribe el carácter cuyo código está en el registro (para cadenas y salto de línea)
  OUT   escribe el número sin salto de línea; cada cout termina con OUTC 10.
"""

from tm_code import CodeEmitter, pc, mp, gp, ac, ac1, ac2

COMPARACIONES = {"<": "JLT", "<=": "JLE", ">": "JGT", ">=": "JGE", "==": "JEQ", "!=": "JNE"}
BINARIOS = set(COMPARACIONES) | {"+", "-", "*", "/", "%", "^", "&&", "||"}
SENTENCIAS = {"main", "bloque", "decl", "=", "++", "--", "if", "while", "do-while", "do-until", "cin", "cout"}


class CodeGenerator:
    def __init__(self, symtab, trace_code=True):
        # symtab: {nombre: dirección} tomado de la tabla de símbolos del análisis semántico
        self.symtab = symtab
        self.e = CodeEmitter(trace_code)
        self.tmp_offset = 0

    def st_lookup(self, name):
        return self.symtab[name]

    # ---------------- sentencias ----------------
    def genStmt(self, t):
        e = self.e
        n = t.name

        if n == "main":
            self.cGen(t.children[0])

        elif n == "bloque":
            for hijo in t.children:
                self.cGen(hijo)

        elif n == "decl":
            pass  # las declaraciones sólo reservan memoria (ya asignada en la tabla de símbolos)

        elif n == "if":
            e.emitComment("-> if")
            cond, entonces = t.children[0], t.children[1]
            sino = t.children[2] if len(t.children) > 2 else None
            self.cGen(cond)
            saved1 = e.emitSkip(1)
            e.emitComment("if: jump to else belongs here")
            self.cGen(entonces)
            saved2 = e.emitSkip(1)
            e.emitComment("if: jump to end belongs here")
            current = e.emitSkip(0)
            e.emitBackup(saved1)
            e.emitRM_Abs("JEQ", ac, current, "if: jmp to else")
            e.emitRestore()
            if sino is not None:
                self.cGen(sino)
            current = e.emitSkip(0)
            e.emitBackup(saved2)
            e.emitRM_Abs("LDA", pc, current, "jmp to end")
            e.emitRestore()
            e.emitComment("<- if")

        elif n == "while":
            e.emitComment("-> while")
            inicio = e.emitSkip(0)
            e.emitComment("while: jump back to test comes here")
            self.cGen(t.children[0])
            saved = e.emitSkip(1)
            e.emitComment("while: jump to end belongs here")
            self.cGen(t.children[1])
            e.emitRM_Abs("LDA", pc, inicio, "while: jmp back to test")
            current = e.emitSkip(0)
            e.emitBackup(saved)
            e.emitRM_Abs("JEQ", ac, current, "while: jmp to end")
            e.emitRestore()
            e.emitComment("<- while")

        elif n in ("do-while", "do-until"):
            e.emitComment(f"-> {n}")
            inicio = e.emitSkip(0)
            e.emitComment(f"{n}: jump after body comes back here")
            self.cGen(t.children[0])
            self.cGen(t.children[1])
            if n == "do-while":   # repite mientras la condición sea verdadera
                e.emitRM_Abs("JNE", ac, inicio, "do-while: jmp back to body")
            else:                 # repeat-until de TINY: repite mientras sea falsa
                e.emitRM_Abs("JEQ", ac, inicio, "do-until: jmp back to body")
            e.emitComment(f"<- {n}")

        elif n == "=":
            id_node, expr = t.children
            if expr.name == "ε":
                return  # "x = ;" no tiene valor que asignar
            e.emitComment("-> assign")
            self.cGen(expr)
            e.emitRM("ST", ac, self.st_lookup(id_node.name), gp, "assign: store value")
            e.emitComment("<- assign")

        elif n in ("++", "--"):
            loc = self.st_lookup(t.children[0].name)
            e.emitComment(f"-> {n}")
            e.emitRM("LD", ac, loc, gp, "load id value")
            e.emitRM("LDA", ac, 1 if n == "++" else -1, ac, f"op {n}")
            e.emitRM("ST", ac, loc, gp, f"{n}: store value")
            e.emitComment(f"<- {n}")

        elif n == "cin":
            id_node = t.children[0]
            if id_node.attrs.get("tipo") == "float":
                e.emitRO("INF", ac, 0, 0, "read float value")
            else:
                e.emitRO("IN", ac, 0, 0, "read integer value")
            e.emitRM("ST", ac, self.st_lookup(id_node.name), gp, "read: store value")

        elif n == "cout":
            e.emitComment("-> write")
            salida = t.children[0]
            partes = salida.children if salida.name == "<<" else [salida]
            for parte in partes:
                if parte.kind == "CADENA":
                    for ch in parte.name[1:-1]:
                        e.emitRM("LDC", ac, ord(ch), 0, f"char '{ch}'")
                        e.emitRO("OUTC", ac, 0, 0, "write char")
                else:
                    self.cGen(parte)
                    e.emitRO("OUT", ac, 0, 0, "write ac")
            e.emitRM("LDC", ac, 10, 0, "newline")
            e.emitRO("OUTC", ac, 0, 0, "write newline")
            e.emitComment("<- write")

    # ---------------- expresiones ----------------
    def genExp(self, t):
        e = self.e

        if t.kind in ("ENTERO", "REAL") or t.name in ("true", "false"):
            e.emitComment("-> Const")
            valor = t.attrs.get("valor", t.name)
            if isinstance(valor, bool):
                valor = int(valor)
            e.emitRM("LDC", ac, valor, 0, "load const")
            e.emitComment("<- Const")

        elif t.kind == "IDENTIFICADOR":
            e.emitComment("-> Id")
            e.emitRM("LD", ac, self.st_lookup(t.name), gp, "load id value")
            e.emitComment("<- Id")

        elif t.name == "!":
            e.emitComment("-> Op !")
            self.cGen(t.children[0])
            self._booleano("JEQ", "op !")
            e.emitComment("<- Op")

        elif t.name in BINARIOS:
            e.emitComment("-> Op")
            self.cGen(t.children[0])
            e.emitRM("ST", ac, self.tmp_offset, mp, "op: push left")
            self.tmp_offset -= 1
            self.cGen(t.children[1])
            self.tmp_offset += 1
            e.emitRM("LD", ac1, self.tmp_offset, mp, "op: load left")
            op = t.name
            if op == "+":
                e.emitRO("ADD", ac, ac1, ac, "op +")
            elif op == "-":
                e.emitRO("SUB", ac, ac1, ac, "op -")
            elif op == "*":
                e.emitRO("MUL", ac, ac1, ac, "op *")
            elif op == "/":
                if t.attrs.get("tipo") == "float":
                    e.emitRO("DIVF", ac, ac1, ac, "op / (real)")
                else:
                    e.emitRO("DIV", ac, ac1, ac, "op / (entera)")
            elif op == "%":
                # a % b = a - (a / b) * b
                e.emitRO("DIV", ac2, ac1, ac, "op %: a / b")
                e.emitRO("MUL", ac2, ac2, ac, "op %: (a / b) * b")
                e.emitRO("SUB", ac, ac1, ac2, "op %: a - (a / b) * b")
            elif op == "^":
                # ac1 = base, ac = exponente; ac2 acumula el producto
                e.emitRM("LDC", ac2, 1, 0, "op ^: result = 1")
                e.emitRM("JLE", ac, 3, pc, "op ^: exit if exponent <= 0")
                e.emitRO("MUL", ac2, ac2, ac1, "op ^: result *= base")
                e.emitRM("LDA", ac, -1, ac, "op ^: exponent--")
                e.emitRM("LDA", pc, -4, pc, "op ^: loop")
                e.emitRM("LDA", ac, 0, ac2, "op ^: ac = result")
            elif op in COMPARACIONES:
                e.emitRO("SUB", ac, ac1, ac, f"op {op}")
                self._booleano(COMPARACIONES[op], "br if true")
            elif op == "&&":
                e.emitRO("MUL", ac, ac1, ac, "op && (1*1 = 1)")
            elif op == "||":
                e.emitRO("ADD", ac, ac1, ac, "op ||")
                self._booleano("JNE", "br if true")
            e.emitComment("<- Op")

        else:
            e.emitComment(f"BUG: nodo desconocido '{t.name}'")

    # deja 1 en ac si el salto se cumple, 0 si no (patrón de cgen.c para < y ==)
    def _booleano(self, salto, comentario):
        e = self.e
        e.emitRM(salto, ac, 2, pc, comentario)
        e.emitRM("LDC", ac, 0, ac, "false case")
        e.emitRM("LDA", pc, 1, pc, "unconditional jmp")
        e.emitRM("LDC", ac, 1, ac, "true case")

    def cGen(self, t):
        if t is None:
            return
        if t.name in SENTENCIAS and not (t.name in ("++", "--") and len(t.children) != 1):
            self.genStmt(t)
        else:
            self.genExp(t)


def codeGen(syntax_tree, symtab, codefile, trace_code=True):
    """Genera el texto del archivo .tm para el árbol anotado (ya validado semánticamente)."""
    g = CodeGenerator(symtab, trace_code)
    e = g.e
    e.emitComment("TINY Compilation to TM Code")
    e.emitComment(f"File: {codefile}")
    e.emitComment("Standard prelude:")
    e.emitRM("LD", mp, 0, ac, "load maxaddress from location 0")
    e.emitRM("ST", ac, 0, ac, "clear location 0")
    e.emitComment("End of standard prelude.")
    g.cGen(syntax_tree)
    e.emitComment("End of execution.")
    e.emitRO("HALT", 0, 0, 0, "")
    return e.text()
