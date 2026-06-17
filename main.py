import os
import tkinter as tk
import sv_ttk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ErrorItem:
    line: int
    col: int
    kind: str
    message: str


@dataclass
class TokenItem:
    kind: str
    lexeme: str
    line: int
    col: int

@dataclass
class ParseNode:
    name: str
    children: list

class Parser:

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errors = []

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        tok = self.current()
        self.pos += 1
        return tok

    def match(self, lexeme=None, kind=None):
        tok = self.current()

        if tok is None:
            self.errors.append("Fin inesperado de archivo")
            return None

        if lexeme is not None and tok.lexeme != lexeme:
            self.errors.append(
                f"Se esperaba '{lexeme}' y se encontró '{tok.lexeme}'"
            )
            return None

        if kind is not None and tok.kind != kind:
            self.errors.append(
                f"Se esperaba {kind} y se encontró {tok.kind}"
            )
            return None

        self.advance()
        return tok

    def parse(self):
        tree = self.programa()

        if self.current() is not None:
            tok = self.current()
            self.errors.append(
                f"Token inesperado al final: '{tok.lexeme}'"
            )

        return tree, self.errors

    # programa → main { lista_declaracion }
    def programa(self):
        self.match("main")
        self.match("{")

        node = ParseNode("main", [])
        node.children.append(self.lista_declaracion())

        self.match("}")

        return node

    # lista_declaracion → lista_declaracion declaracion | declaracion
    def lista_declaracion(self):
        node = ParseNode("bloque", [])

        while self.current() and self.current().lexeme != "}":
            node.children.append(self.declaracion())

        return node

    # declaracion → declaracion_variable | lista_sentencias
    def declaracion(self):
        tok = self.current()

        if tok is None:
            self.errors.append("Fin inesperado en declaración")
            return ParseNode("ERROR", [])

        if tok.lexeme in ("int", "float", "bool"):
            return self.declaracion_variable()

        if (
            tok.lexeme in ("cin", "cout", "if", "while", "do")
            or tok.kind == "IDENTIFICADOR"
        ):
            return self.sentencia()

        self.errors.append(f"Declaración inválida: '{tok.lexeme}'")
        self.advance()
        return ParseNode("ERROR", [])

    # declaracion_variable → tipo identificador ;
    def declaracion_variable(self):
        tipo_node = self.tipo()
        ids_node = self.identificador()

        self.match(";")

        return ParseNode("decl", [tipo_node, ids_node])

    # identificador → id | identificador , id
    def identificador(self):
        ids = []

        ident = self.match(kind="IDENTIFICADOR")
        if ident:
            ids.append(ParseNode(ident.lexeme, []))

        while self.current() and self.current().lexeme == ",":
            self.match(",")

            ident = self.match(kind="IDENTIFICADOR")
            if ident:
                ids.append(ParseNode(ident.lexeme, []))

        if len(ids) == 1:
            return ids[0]

        return ParseNode("ids", ids)

    # tipo → int | float | bool
    def tipo(self):
        tok = self.current()

        if tok and tok.lexeme in ("int", "float", "bool"):
            self.advance()
            return ParseNode(tok.lexeme, [])

        self.errors.append(
            f"Tipo inválido: '{tok.lexeme if tok else 'EOF'}'"
        )
        return ParseNode("ERROR", [])

    # sentencia → seleccion | iteracion | repeticion | sent_in | sent_out | asignacion
    def sentencia(self):
        tok = self.current()

        if tok is None:
            self.errors.append("Fin inesperado en sentencia")
            return ParseNode("ERROR", [])

        match tok.lexeme:
            case "cin":
                return self.sent_in()

            case "cout":
                return self.sent_out()

            case "if":
                return self.seleccion()

            case "while":
                return self.iteracion()

            case "do":
                return self.repeticion()

            case _:
                if tok.kind == "IDENTIFICADOR":
                    siguiente = None

                    if self.pos + 1 < len(self.tokens):
                        siguiente = self.tokens[self.pos + 1]

                    if siguiente and siguiente.lexeme in ("++", "--"):
                        return self.incremento()

                    return self.asignacion()

                self.errors.append(f"Sentencia inválida: '{tok.lexeme}'")
                self.advance()
                return ParseNode("ERROR", [])

    # lista_sentencias → lista_sentencias sentencia | ε
    def lista_sentencias(self, stop_words=("}",)):
        node = ParseNode("bloque", [])

        while self.current() and self.current().lexeme not in stop_words:
            tok = self.current()

            if (
                tok.lexeme in ("cin", "cout", "if", "while", "do")
                or tok.kind == "IDENTIFICADOR"
            ):
                node.children.append(self.sentencia())
            else:
                self.errors.append(f"Sentencia inválida: '{tok.lexeme}'")
                self.advance()

        return node
    
    def bloque_llaves(self):
        self.match("{")

        node = self.lista_sentencias(stop_words=("}",))

        self.match("}")

        return node

    # asignacion → id = sent_expresion
    def asignacion(self):
        ident = self.match(kind="IDENTIFICADOR")

        left = ParseNode(ident.lexeme, []) if ident else ParseNode("ERROR", [])

        self.match("=")

        right = self.sent_expresion()

        return ParseNode("=", [left, right])

    # id++ ; / id-- ;
    def incremento(self):
        ident = self.match(kind="IDENTIFICADOR")
        left = ParseNode(ident.lexeme, []) if ident else ParseNode("ERROR", [])

        op = self.current()

        if op and op.lexeme in ("++", "--"):
            self.advance()
            op_node = ParseNode(op.lexeme, [left])
        else:
            self.errors.append("Se esperaba '++' o '--'")
            op_node = ParseNode("ERROR", [left])

        self.match(";")

        return op_node

    # sent_expresion → expresion ; | ;
    def sent_expresion(self):
        if self.current() and self.current().lexeme == ";":
            self.match(";")
            return ParseNode("ε", [])

        expr = self.expresion()

        self.match(";")

        return expr

    # seleccion → if expresion then lista_sentencias [ else lista_sentencias ] end
    def seleccion(self):
        self.match("if")

        condicion = self.expresion()

        self.match("then")

        entonces = self.bloque_llaves()

        children = [condicion, entonces]

        if self.current() and self.current().lexeme == "else":
            self.match("else")
            sino = self.bloque_llaves()
            children.append(sino)

        self.match("end")

        return ParseNode("if", children)

    # iteracion → while expresion lista_sentencias end
    def iteracion(self):
        self.match("while")

        condicion = self.expresion()

        cuerpo = self.bloque_llaves()

        return ParseNode("while", [condicion, cuerpo])

    # repeticion → do lista_sentencias while expresion
    def repeticion(self):
        self.match("do")

        cuerpo = self.bloque_llaves()

        self.match("while")

        condicion = self.expresion()

        return ParseNode("do-while", [cuerpo, condicion])

    # sent_in → cin >> id ;
    def sent_in(self):
        self.match("cin")
        self.match(">>")

        ident = self.match(kind="IDENTIFICADOR")
        var_node = ParseNode(ident.lexeme, []) if ident else ParseNode("ERROR", [])

        self.match(";")

        return ParseNode("cin", [var_node])

    # sent_out → cout << salida ;
    def sent_out(self):
        self.match("cout")
        self.match("<<")

        salida_node = self.salida()

        self.match(";")

        return ParseNode("cout", [salida_node])

    # salida → cadena | expresion | cadena << expresion | expresion << cadena
    def salida(self):
        if self.current() and self.current().kind == "CADENA":
            left = self.cadena()

            if self.current() and self.current().lexeme == "<<":
                self.match("<<")
                right = self.expresion()
                return ParseNode("<<", [left, right])

            return left

        left = self.expresion()

        if self.current() and self.current().lexeme == "<<":
            self.match("<<")

            if self.current() and self.current().kind == "CADENA":
                right = self.cadena()
                return ParseNode("<<", [left, right])

            self.errors.append("Se esperaba una cadena después de '<<'")
            return ParseNode("<<", [left, ParseNode("ERROR", [])])

        return left

    # cadena → "cualquier texto"
    def cadena(self):
        tok = self.match(kind="CADENA")

        if tok:
            return ParseNode(tok.lexeme, [])

        return ParseNode("ERROR", [])

    # expresion → expresion_simple [ rel_op expresion_simple ]
    def expresion(self):

        left = self.expresion_relacional()

        while (
            self.current()
            and self.current().kind == "OP_LOGICO"
            and self.current().lexeme in ("&&", "||")
        ):

            op = self.current()
            self.advance()

            right = self.expresion_relacional()

            left = ParseNode(
                op.lexeme,
                [left, right]
            )

        return left
    
    def expresion_relacional(self):

        left = self.expresion_simple()

        if (
            self.current()
            and self.current().kind == "OP_RELACIONAL"
        ):

            op = self.current()
            self.advance()

            right = self.expresion_simple()

            return ParseNode(
                op.lexeme,
                [left, right]
            )

        return left

    # expresion_simple → expresion_simple suma_op termino | termino
    def expresion_simple(self):
        left = self.termino()

        while self.current() and self.current().lexeme in ("+", "-", "++", "--"):
            op = self.current()
            self.advance()

            right = self.termino()

            left = ParseNode(op.lexeme, [left, right])

        return left

    # termino → termino mult_op factor | factor
    def termino(self):
        left = self.factor()

        while self.current() and self.current().lexeme in ("*", "/", "%"):
            op = self.current()
            self.advance()

            right = self.factor()

            left = ParseNode(op.lexeme, [left, right])

        return left

    # factor → factor pot_op componente | componente
    def factor(self):
        left = self.componente()

        while self.current() and self.current().lexeme == "^":
            op = self.current()
            self.advance()

            right = self.componente()

            left = ParseNode(op.lexeme, [left, right])

        return left

    # componente → ( expresion ) | número | id | bool | op_logico componente
    def componente(self):
        tok = self.current()

        if tok is None:
            self.errors.append("Fin inesperado en componente")
            return ParseNode("ERROR", [])

        if tok.lexeme == "(":
            self.match("(")
            node = self.expresion()
            self.match(")")
            return node

        if tok.kind in ("ENTERO", "REAL"):
            self.advance()
            return ParseNode(tok.lexeme, [])

        if tok.kind == "IDENTIFICADOR":
            self.advance()
            return ParseNode(tok.lexeme, [])

        if tok.lexeme in ("true", "false"):
            self.advance()
            return ParseNode(tok.lexeme, [])

        if tok.kind == "OP_LOGICO":
            op = self.current()
            self.advance()

            return ParseNode(op.lexeme, [self.componente()])

        self.errors.append(f"Componente inválido: '{tok.lexeme}'")
        self.advance()
        return ParseNode("ERROR", [])
    
    def optional_semicolon(self):
        if self.current() and self.current().lexeme == ";":
            self.match(";")

class IDE(tk.Tk):
    RESERVED = {
        "if", "else", "end", "do", "while", "switch", "case",
        "int", "float", "main", "cin", "cout", "until", "then",
        "bool", "true", "false"
    }

    ARITHMETIC_OPS = {"+", "-", "*", "/", "%", "^", "++", "--"}
    RELATIONAL_OPS = {"<", "<=", ">", ">=", "!=", "=="}
    LOGICAL_OPS = {"&&", "||", "!"}
    SYMBOLS = {"(", ")", "{", "}", ",", ";", '"', "'"}

    def __init__(self):
        super().__init__()

        # -------------------- Ventana principal --------------------
        self.title("Compiladores IDE")
        self.geometry("1200x720")

        try:
            self.state("zoomed")  # Windows
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)  # Linux
            except tk.TclError:
                pass

        sv_ttk.set_theme("light")

        self.current_file: Path | None = None

        self._layout_job = None
        self._applying_layout = False
        self._last_size = (0, 0)

        self._highlight_job = None
        self._internal_text_change = False

        self._load_icons()

        self._build_menu()
        self._build_toolbar()
        self._build_layout()
        self._setup_syntax_tags()
        self._bind_editor_events()
        self.protocol("WM_DELETE_WINDOW", self.exit_program)

        self._refresh_gutter_and_status()
        self.after(120, self._apply_layout_ratios)
        self.bind("<Configure>", self._on_root_configure)

    # -------------------------- ICONOS --------------------------
    def _load_icons(self):
        self.icons_menu: dict[str, tk.PhotoImage] = {}
        self.icons_toolbar: dict[str, tk.PhotoImage] = {}

        icon_map = {
            "nuevo": "iconos/nuevo_archivo.png",
            "abrir": "iconos/abrir_archivo.png",
            "cerrar": "iconos/cerrar_archivo.png",
            "guardar": "iconos/guardar_archivo.png",
            "guardar_como": "iconos/guardar_archivo_como.png",
            "salir": "iconos/salir.png"
        }

        def scaled(img: tk.PhotoImage, target_px: int) -> tk.PhotoImage:
            w, h = img.width(), img.height()
            factor = max(1, int(max(w, h) / target_px))
            return img.subsample(factor, factor)

        for key, rel in icon_map.items():
            if not os.path.exists(rel):
                continue
            try:
                base = tk.PhotoImage(file=rel)
                self.icons_menu[key] = scaled(base, 18)
                self.icons_toolbar[key] = scaled(base, 48)
            except tk.TclError:
                pass

    # -------------------------- MENÚ --------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(
            label="Nuevo",
            command=self.file_new,
            image=self.icons_menu.get("nuevo"),
            compound="left" if self.icons_menu.get("nuevo") else None
        )
        m_file.add_command(
            label="Abrir",
            command=self.file_open,
            image=self.icons_menu.get("abrir"),
            compound="left" if self.icons_menu.get("abrir") else None
        )
        m_file.add_command(
            label="Cerrar",
            command=self.file_close,
            image=self.icons_menu.get("cerrar"),
            compound="left" if self.icons_menu.get("cerrar") else None
        )

        m_file.add_separator()

        m_file.add_command(
            label="Guardar",
            command=self.file_save,
            image=self.icons_menu.get("guardar"),
            compound="left" if self.icons_menu.get("guardar") else None
        )
        m_file.add_command(
            label="Guardar como",
            command=self.file_save_as,
            image=self.icons_menu.get("guardar_como"),
            compound="left" if self.icons_menu.get("guardar_como") else None
        )

        m_file.add_separator()

        m_file.add_command(
            label="Salir",
            command=self.exit_program,
            image=self.icons_menu.get("salir"),
            compound="left" if self.icons_menu.get("salir") else None
        )

        menubar.add_cascade(label="Archivo", menu=m_file)

        m_compile = tk.Menu(menubar, tearoff=0)
        m_compile.add_command(label="Análisis Léxico", command=self.run_lex)
        m_compile.add_command(label="Análisis Sintáctico", command=self.run_parse)
        m_compile.add_command(label="Análisis Semántico", command=self.run_sem)
        m_compile.add_separator()
        m_compile.add_command(label="Generación Código Intermedio", command=self.run_ir)
        m_compile.add_command(label="Ejecución", command=self.run_exec)
        menubar.add_cascade(label="Compilar", menu=m_compile)

        self.config(menu=menubar)

    # -------------------------- TOOLBAR --------------------------
    def _build_toolbar(self):
        self.toolbar = ttk.Frame(self, padding=(6, 4))
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        def tool_btn(text, icon_key, cmd):
            img = self.icons_menu.get(icon_key)
            if img is not None:
                btn = ttk.Button(self.toolbar, text=text, image=img, compound="top", command=cmd)
            else:
                btn = ttk.Button(self.toolbar, text=text, command=cmd)
            btn.pack(side=tk.LEFT, padx=3)
            return btn

        tool_btn("Nuevo", "nuevo", self.file_new)
        tool_btn("Abrir", "abrir", self.file_open)
        tool_btn("Guardar", "guardar", self.file_save)
        tool_btn("Guardar como", "guardar_como", self.file_save_as)
        tool_btn("Cerrar", "cerrar", self.file_close)
        tool_btn("Salir", "salir", self.exit_program)

        ttk.Separator(self.toolbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Button(self.toolbar, text="Léxico", command=self.run_lex).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.toolbar, text="Sintáctico", command=self.run_parse).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.toolbar, text="Semántico", command=self.run_sem).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.toolbar, text="Intermedio", command=self.run_ir).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.toolbar, text="Ejecutar", command=self.run_exec).pack(side=tk.LEFT, padx=3)

        self.status = ttk.Label(self.toolbar, text="", anchor="w")
        self.status.pack(side=tk.RIGHT, padx=8)

    # -------------------------- LAYOUT --------------------------
    def _build_layout(self):
        self.root_v = tk.PanedWindow(self, orient=tk.VERTICAL, sashwidth=6)
        self.root_v.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(self.root_v)
        bottom = ttk.Frame(self.root_v)

        self.root_v.add(top, minsize=500)
        self.root_v.add(bottom, minsize=120)

        self.top_h = tk.PanedWindow(top, orient=tk.HORIZONTAL, sashwidth=6)
        self.top_h.pack(fill=tk.BOTH, expand=True)

        editor_wrap = ttk.Frame(self.top_h)
        panels_wrap = ttk.Frame(self.top_h)

        self.top_h.add(editor_wrap, minsize=900)
        self.top_h.add(panels_wrap, minsize=220)

        # Editor
        self.editor_frame = ttk.Frame(editor_wrap)
        self.editor_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.gutter = tk.Canvas(
            self.editor_frame,
            width=50,
            highlightthickness=0,
            bg="#f0f0f0"
        )
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)

        self.text = tk.Text(self.editor_frame, wrap="none", undo=True)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def on_scroll(*args):
            self.text.yview(*args)
            self._update_gutter()

        yscroll = ttk.Scrollbar(self.editor_frame, orient="vertical", command=on_scroll)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        def yscroll_set(*args):
            yscroll.set(*args)
            self._update_gutter()

        self.text.config(yscrollcommand=yscroll_set)

        # Paneles derecha
        self.nb_right = ttk.Notebook(panels_wrap)
        self.nb_right.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.out_tokens = self._make_readonly_text_tab(self.nb_right, "Tokens (Léxico)")
        self.out_parse = self._make_readonly_text_tab(self.nb_right, "Sintáctico")
        self.out_sem = self._make_readonly_text_tab(self.nb_right, "Semántico")
        self.out_ir = self._make_readonly_text_tab(self.nb_right, "Intermedio")
        self.out_sym = self._make_readonly_text_tab(self.nb_right, "Tabla Símbolos")

        # Árbol sintáctico
        self.tree_frame = ttk.Frame(self.nb_right)
        self.nb_right.add(self.tree_frame, text="Árbol Sintáctico")

        self.syntax_tree = ttk.Treeview(self.tree_frame)
        self.syntax_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(
            self.tree_frame,
            orient="vertical",
            command=self.syntax_tree.yview
        )
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.syntax_tree.configure(yscrollcommand=tree_scroll.set)

        # Paneles inferiores
        self.nb_bottom = ttk.Notebook(bottom)
        self.nb_bottom.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.out_err = self._make_readonly_text_tab(self.nb_bottom, "Errores")
        self.out_exec = self._make_readonly_text_tab(self.nb_bottom, "Ejecución")
        self.out_log = self._make_readonly_text_tab(self.nb_bottom, "Log")

    # -------------------------- RESIZE --------------------------
    def _on_root_configure(self, event):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last_size:
            return
        self._last_size = size

        if self._layout_job is not None:
            try:
                self.after_cancel(self._layout_job)
            except tk.TclError:
                pass

        self._layout_job = self.after(120, self._apply_layout_ratios)

    def _apply_layout_ratios(self):
        if self._applying_layout:
            return
        self._applying_layout = True
        try:
            if not self.winfo_ismapped():
                return

            self.root_v.update_idletasks()
            pv_h = self.root_v.winfo_height()
            if pv_h < 300:
                return

            top_h_px = int(pv_h * 0.70)
            top_h_px = max(250, min(top_h_px, pv_h - 120))
            try:
                self.root_v.sashpos(0, top_h_px)
            except tk.TclError:
                pass

            self.top_h.update_idletasks()
            ph_w = self.top_h.winfo_width()
            if ph_w < 500:
                return

            left_w_px = int(ph_w * 0.60)
            left_w_px = max(300, min(left_w_px, ph_w - 220))
            try:
                self.top_h.sashpos(0, left_w_px)
            except tk.TclError:
                pass

        finally:
            self._applying_layout = False
            self._layout_job = None

    # -------------------------- TABS SOLO LECTURA --------------------------
    def _make_readonly_text_tab(self, notebook: ttk.Notebook, title: str) -> tk.Text:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        txt = tk.Text(frame, wrap="none", state="disabled")
        txt.pack(fill=tk.BOTH, expand=True)
        return txt

    # -------------------------- EVENTOS DEL EDITOR --------------------------
    def _bind_editor_events(self):
        self.text.bind("<KeyRelease>", self._on_editor_change)
        self.text.bind("<ButtonRelease-1>", self._on_editor_change)
        self.text.bind("<Configure>", self._on_editor_change)
        self.text.bind("<MouseWheel>", self._on_editor_change)
        self.text.bind("<Return>", self._on_editor_change)
        self.text.bind("<BackSpace>", self._on_editor_change)
        self.text.bind("<Delete>", self._on_editor_change)

        self._refresh_gutter_and_status()
        self.highlight_syntax()

    def _on_editor_change(self, event=None):
        self.after_idle(self._refresh_gutter_and_status)

        if self._highlight_job is not None:
            try:
                self.after_cancel(self._highlight_job)
            except tk.TclError:
                pass
        self._highlight_job = self.after(80, self.highlight_syntax)

    def _refresh_gutter_and_status(self):
        self._update_gutter()
        self._update_status()

    # -------------------------- GUTTER --------------------------
    def _update_gutter(self):
        if not hasattr(self, "gutter"):
            return

        self.gutter.delete("all")
        i = self.text.index("@0,0")

        while True:
            dline = self.text.dlineinfo(i)
            if dline is None:
                break

            y = dline[1]
            line_number = i.split(".")[0]

            self.gutter.create_text(
                46, y,
                anchor="ne",
                text=line_number,
                fill="#444"
            )

            i = self.text.index(f"{i}+1line")

    # -------------------------- STATUS --------------------------
    def _update_status(self):
        idx = self.text.index(tk.INSERT)
        line, col = idx.split(".")
        fname = self.current_file.name if self.current_file else "(sin archivo)"
        self.status.config(text=f"{fname}  |  Ln {line}, Col {int(col) + 1}")

    # -------------------------- WRITE READONLY --------------------------
    def _write_readonly(self, widget: tk.Text, content: str):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.config(state="disabled")

    def _append_readonly(self, widget: tk.Text, content: str):
        widget.config(state="normal")
        prev = widget.get("1.0", "end-1c")
        if prev.strip():
            widget.insert("end", "\n" + content)
        else:
            widget.insert("1.0", content)
        widget.config(state="disabled")

    def _log(self, msg: str):
        prev = self.out_log.get("1.0", "end-1c")
        new = (prev + "\n" if prev.strip() else "") + msg
        self._write_readonly(self.out_log, new)

    # -------------------------- SINTAXIS / COLORES --------------------------
    def _setup_syntax_tags(self):
        self.text.tag_configure("tok_numero", foreground="#1f77b4")
        self.text.tag_configure("tok_identificador", foreground="#2ca02c")
        self.text.tag_configure("tok_comentario", foreground="#6a9955")
        self.text.tag_configure("tok_reservada", foreground="#d62728")
        self.text.tag_configure("tok_op_arit", foreground="#ff7f0e")
        self.text.tag_configure("tok_op_rel_log", foreground="#9467bd")
        self.text.tag_configure("tok_simbolo", foreground="#8c564b")
        self.text.tag_configure("tok_asignacion", foreground="#e377c2")
        self.text.tag_configure("tok_cadena", foreground="#bcbd22")
        self.text.tag_configure("tok_error", background="#ffb3b3")

        self.text.tag_configure("current_line", background="#eaf2ff")

    def highlight_current_line(self):
        self.text.tag_remove("current_line", "1.0", "end")
        self.text.tag_add("current_line", "insert linestart", "insert lineend+1c")

    def highlight_syntax(self):
        if self._internal_text_change:
            return

        self._highlight_job = None

        for tag in (
            "tok_numero", "tok_identificador", "tok_comentario", "tok_reservada",
            "tok_op_arit", "tok_op_rel_log", "tok_simbolo", "tok_asignacion",
            "tok_cadena", "tok_error", "current_line"
        ):
            self.text.tag_remove(tag, "1.0", "end")

        code = self.text.get("1.0", "end-1c")
        tokens, errors = self.lex_analysis(code)

        for token in tokens:
            start = f"{token.line}.{token.col - 1}"
            end = f"{start}+{len(token.lexeme)}c"

            if token.kind in ("ENTERO", "REAL"):
                self.text.tag_add("tok_numero", start, end)
            elif token.kind == "IDENTIFICADOR":
                self.text.tag_add("tok_identificador", start, end)
            elif token.kind in ("COMENTARIO_LINEA", "COMENTARIO_BLOQUE"):
                self.text.tag_add("tok_comentario", start, end)
            elif token.kind == "PALABRA_RESERVADA":
                self.text.tag_add("tok_reservada", start, end)
            elif token.kind == "OP_ARITMETICO":
                self.text.tag_add("tok_op_arit", start, end)
            elif token.kind in ("OP_RELACIONAL", "OP_LOGICO", "OP_ENTRADA", "OP_SALIDA"):
                self.text.tag_add("tok_op_rel_log", start, end)
            elif token.kind == "ASIGNACION":
                self.text.tag_add("tok_asignacion", start, end)
            elif token.kind in ("SIMBOLO",):
                self.text.tag_add("tok_simbolo", start, end)
            elif token.kind in ("CADENA", "CARACTER"):
                self.text.tag_add("tok_cadena", start, end)

        for err in errors:
            start = f"{err.line}.{max(0, err.col - 1)}"
            end = f"{start}+1c"
            self.text.tag_add("tok_error", start, end)

        self.highlight_current_line()

    # -------------------------- ANÁLISIS LÉXICO --------------------------
    def lex_analysis(self, code: str):
        tokens: list[TokenItem] = []
        errors: list[ErrorItem] = []

        i = 0
        line = 1
        col = 1
        n = len(code)

        def add_token(kind: str, lexeme: str, ln: int, cl: int):
            tokens.append(TokenItem(kind, lexeme, ln, cl))

        def add_error(kind: str, message: str, ln: int, cl: int):
            errors.append(ErrorItem(ln, cl, kind, message))

        def skip_blanks(idx, ln, cl):
            while idx < n and code[idx] in " \t\r\n":
                if code[idx] == "\n":
                    idx += 1
                    ln += 1
                    cl = 1
                else:
                    idx += 1
                    cl += 1
            return idx, ln, cl

        while i < n:
            ch = code[i]

            # Espacios
            if ch in " \t\r":
                i += 1
                col += 1
                continue

            # Nueva línea
            if ch == "\n":
                i += 1
                line += 1
                col = 1
                continue

            start_line = line
            start_col = col

            # Comentario de una línea //
            if code[i:i + 2] == "//":
                lex = ""
                while i < n and code[i] != "\n":
                    lex += code[i]
                    i += 1
                    col += 1
                add_token("COMENTARIO_LINEA", lex, start_line, start_col)
                continue

            # Comentario multilínea /* ... */
            if code[i:i + 2] == "/*":
                lex = "/*"
                i += 2
                col += 2
                closed = False

                while i < n:
                    if code[i:i + 2] == "*/":
                        lex += "*/"
                        i += 2
                        col += 2
                        closed = True
                        break

                    if code[i] == "\n":
                        lex += "\n"
                        i += 1
                        line += 1
                        col = 1
                    else:
                        lex += code[i]
                        i += 1
                        col += 1

                if closed:
                    add_token("COMENTARIO_BLOQUE", lex, start_line, start_col)
                else:
                    add_error("Léxico", "Comentario multilínea sin cerrar", start_line, start_col)
                continue

            # Cadena
            if ch == '"':
                lex = '"'
                i += 1
                col += 1
                closed = False

                while i < n:
                    if code[i] == '"':
                        lex += '"'
                        i += 1
                        col += 1
                        closed = True
                        break
                    if code[i] == "\n":
                        add_error("Léxico", "Cadena sin cerrar", start_line, start_col)
                        break
                    lex += code[i]
                    i += 1
                    col += 1

                if closed:
                    add_token("CADENA", lex, start_line, start_col)
                continue

            # Carácter
            if ch == "'":
                lex = "'"
                i += 1
                col += 1

                while i < n and code[i] != "'" and code[i] != "\n":
                    lex += code[i]
                    i += 1
                    col += 1

                if i < n and code[i] == "'":
                    lex += "'"
                    i += 1
                    col += 1
                    add_token("CARACTER", lex, start_line, start_col)
                else:
                    add_error("Léxico", "Constante de carácter sin cerrar", start_line, start_col)
                continue

            # Operadores de entrada/salida
            if code[i:i + 2] == ">>":
                add_token("OP_ENTRADA", ">>", start_line, start_col)
                i += 2
                col += 2
                continue

            if code[i:i + 2] == "<<":
                add_token("OP_SALIDA", "<<", start_line, start_col)
                i += 2
                col += 2
                continue

            # Operadores de dos caracteres
            if ch in {"+", "-", "<", ">", "!", "=", "&", "|"}:
                j, line2, col2 = skip_blanks(i + 1, line, col + 1)

                if ch == "+" and j < n and code[j] == "+":
                    add_token("OP_ARITMETICO", "++", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == "-" and j < n and code[j] == "-":
                    add_token("OP_ARITMETICO", "--", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == "<" and j < n and code[j] == "=":
                    add_token("OP_RELACIONAL", "<=", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == ">" and j < n and code[j] == "=":
                    add_token("OP_RELACIONAL", ">=", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == "!" and j < n and code[j] == "=":
                    add_token("OP_RELACIONAL", "!=", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == "=" and j < n and code[j] == "=":
                    add_token("OP_RELACIONAL", "==", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == "&" and j < n and code[j] == "&":
                    add_token("OP_LOGICO", "&&", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

                if ch == "|" and j < n and code[j] == "|":
                    add_token("OP_LOGICO", "||", start_line, start_col)
                    i = j + 1
                    line = line2
                    col = col2 + 1
                    continue

            # Número entero o real
            if ch.isdigit():
                lex = ""

                while i < n and code[i].isdigit():
                    lex += code[i]
                    i += 1
                    col += 1

                # Caso: número con punto
                if i < n and code[i] == ".":
                    lex += code[i]
                    i += 1
                    col += 1

                    if i < n and code[i].isdigit():
                        while i < n and code[i].isdigit():
                            lex += code[i]
                            i += 1
                            col += 1

                        # Validar que no siga letra
                        if i < n and (code[i].isalpha() or code[i] == "_"):
                            while i < n and (code[i].isalnum() or code[i] == "_"):
                                lex += code[i]
                                i += 1
                                col += 1
                            add_error("Léxico", f"Token inválido: {lex}", start_line, start_col)
                            continue

                        add_token("REAL", lex, start_line, start_col)
                        continue

                    else:
                        add_error("Léxico", f"Real inválido: {lex}", start_line, start_col)
                        continue

                # Validar letras después de entero
                if i < n and (code[i].isalpha() or code[i] == "_"):
                    while i < n and (code[i].isalnum() or code[i] == "_"):
                        lex += code[i]
                        i += 1
                        col += 1
                    add_error("Léxico", f"Token inválido: {lex}", start_line, start_col)
                    continue

                add_token("ENTERO", lex, start_line, start_col)
                continue

            # Identificadores / reservadas
            if ch.isalpha() or ch == "_":
                lex = ""
                while i < n and (code[i].isalnum() or code[i] == "_"):
                    lex += code[i]
                    i += 1
                    col += 1

                if lex in self.RESERVED:
                    add_token("PALABRA_RESERVADA", lex, start_line, start_col)
                else:
                    add_token("IDENTIFICADOR", lex, start_line, start_col)
                continue

            # Operadores de un caracter
            if ch in {"+", "-", "*", "/", "%", "^"}:
                add_token("OP_ARITMETICO", ch, start_line, start_col)
                i += 1
                col += 1
                continue

            if ch in {"<", ">"}:
                add_token("OP_RELACIONAL", ch, start_line, start_col)
                i += 1
                col += 1
                continue

            if ch == "!":
                add_token("OP_LOGICO", ch, start_line, start_col)
                i += 1
                col += 1
                continue

            # Asignación
            if ch == "=":
                add_token("ASIGNACION", ch, start_line, start_col)
                i += 1
                col += 1
                continue

            # Símbolos
            if ch in {"(", ")", "{", "}", ",", ";"}:
                add_token("SIMBOLO", ch, start_line, start_col)
                i += 1
                col += 1
                continue

            # Error léxico
            add_error("Léxico", f"Carácter inválido: {ch}", start_line, start_col)
            i += 1
            col += 1

        return tokens, errors

    # -------------------------- ARCHIVOS --------------------------
    def _confirm_discard(self) -> bool:
        return messagebox.askyesno("Confirmar", "¿Deseas continuar? Se perderán cambios no guardados.")

    def file_new(self):
        if self._confirm_discard():
            self.text.delete("1.0", "end")
            self.current_file = None
            self._refresh_gutter_and_status()
            self.highlight_syntax()
            self._log("Nuevo archivo.")

    def file_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("Archivos de texto", "*.txt *.src *.c *.py"), ("Todos", "*.*")]
        )
        if not path:
            return

        p = Path(path)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", p.read_text(encoding="utf-8", errors="replace"))
        self.current_file = p
        self._refresh_gutter_and_status()
        self.highlight_syntax()
        self._log(f"Abrir: {p}")

    def file_close(self):
        if self._confirm_discard():
            self.text.delete("1.0", "end")
            self.current_file = None
            self._refresh_gutter_and_status()
            self.highlight_syntax()
            self._log("Cerrar archivo.")

    def file_save(self):
        if self.current_file is None:
            return self.file_save_as()

        self.current_file.write_text(self.text.get("1.0", "end-1c"), encoding="utf-8")
        self._log(f"Guardar: {self.current_file}")
        self._update_status()

    def file_save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos", "*.*")]
        )
        if not path:
            return

        self.current_file = Path(path)
        self.file_save()

    # -------------------------- FASE LÉXICA --------------------------
    def run_lex(self):
        code = self.text.get("1.0", "end-1c")
        tokens, errors = self.lex_analysis(code)

        # ----------- FORMATO DE TOKENS -----------
        token_lines = []
        token_lines.append("No. | Tipo               | Lexema               | Línea | Columna")
        token_lines.append("-" * 75)

        filtered_tokens = [t for t in tokens if not t.kind.startswith("COMENTARIO")]

        for idx, t in enumerate(filtered_tokens, start=1):
            token_lines.append(
                f"{idx:03d} | {t.kind:<18} | {t.lexeme:<20} | {t.line:<5} | {t.col}"
            )

        # ----------- FORMATO DE ERRORES -----------
        error_lines = []
        error_lines.append("No. | Tipo    | Línea | Columna | Descripción")
        error_lines.append("-" * 75)

        for idx, e in enumerate(errors, start=1):
            error_lines.append(
                f"{idx:03d} | {e.kind:<7} | {e.line:<5} | {e.col:<7} | {e.message}"
            )

        # ----------- MOSTRAR EN EL IDE -----------
        self._write_readonly(
            self.out_tokens,
            "\n".join(token_lines) if filtered_tokens else "(sin tokens)"
        )

        self._write_readonly(
            self.out_err,
            "\n".join(error_lines) if errors else "(sin errores léxicos)"
        )

        # Cambiar pestañas automáticamente
        self.nb_right.select(self.out_tokens.master)
        self.nb_bottom.select(self.out_err.master)

        self._log("Análisis Léxico ejecutado.")

    # -------------------------- OTRAS FASES --------------------------
    def _show_parse_tree(self, root_node: ParseNode):
        self.syntax_tree.delete(*self.syntax_tree.get_children())

        root_id = self.syntax_tree.insert(
            "",
            "end",
            text=root_node.name,
            open=True
        )

        self._insert_parse_node(root_id, root_node)

        self._expand_all_tree_nodes()

    def _insert_parse_node(self, parent_id, node: ParseNode):
        for child in node.children:
            child_id = self.syntax_tree.insert(
                parent_id,
                "end",
                text=child.name,
                open=True
            )

            self._insert_parse_node(child_id, child)

    def _expand_all_tree_nodes(self):
        def expand(item):
            self.syntax_tree.item(item, open=True)
            for child in self.syntax_tree.get_children(item):
                expand(child)

        for item in self.syntax_tree.get_children():
            expand(item)

    def run_parse(self):
        code = self.text.get("1.0", "end-1c")
        tokens, lex_errors = self.lex_analysis(code)

        filtered_tokens = [
            t for t in tokens
            if not t.kind.startswith("COMENTARIO")
        ]

        # Si hay errores léxicos, no conviene hacer sintáctico
        if lex_errors:
            error_lines = []
            error_lines.append("No. | Tipo    | Línea | Columna | Descripción")
            error_lines.append("-" * 75)

            for idx, e in enumerate(lex_errors, start=1):
                error_lines.append(
                    f"{idx:03d} | {e.kind:<7} | {e.line:<5} | {e.col:<7} | {e.message}"
                )

            self._write_readonly(self.out_err, "\n".join(error_lines))
            self._write_readonly(
                self.out_parse,
                "No se puede generar árbol sintáctico porque existen errores léxicos."
            )

            try:
                self.syntax_tree.delete(*self.syntax_tree.get_children())
            except Exception:
                pass

            self.nb_bottom.select(self.out_err.master)
            self.nb_right.select(self.out_parse.master)
            return

        parser = Parser(filtered_tokens)
        tree, parse_errors = parser.parse()

        if tree:
            self._show_parse_tree(tree)
            self.nb_right.select(self.tree_frame)

        if parse_errors:
            self._write_readonly(
                self.out_parse,
                "\n".join(parse_errors)
            )
            self._log("Análisis Sintáctico ejecutado con errores.")
        else:
            self._write_readonly(
                self.out_parse,
                "Análisis sintáctico correcto."
            )
            self._log("Análisis Sintáctico correcto.")

    def show_tree_window(self, root_node):

        win = tk.Toplevel(self)

        win.title("Árbol Sintáctico")
        win.geometry("1000x700")

        tree = ttk.Treeview(win)
        tree.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            win,
            orient="vertical",
            command=tree.yview
        )

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tree.configure(
            yscrollcommand=scrollbar.set
        )

        def insert_node(parent, node):

            item = tree.insert(
                parent,
                "end",
                text=node.name,
                open=True
            )

            for child in node.children:
                insert_node(item, child)

        insert_node("", root_node)

    def run_sem(self):
        self._write_readonly(self.out_sem, "Validaciones semánticas simuladas.")
        self.nb_right.select(self.out_sem.master)
        self._log("Análisis Semántico simulado.")

    def run_ir(self):
        self._write_readonly(self.out_ir, "Código intermedio simulado.")
        self._write_readonly(self.out_sym, "Tabla de símbolos simulada.")
        self.nb_right.select(self.out_ir.master)
        self._log("Generación de Código Intermedio simulado.")

    def run_exec(self):
        self._write_readonly(self.out_exec, "Salida de ejecución simulada.")
        self.nb_bottom.select(self.out_exec.master)
        self._log("Ejecución simulada.")

    def exit_program(self):
        if self._confirm_discard():
            self.destroy()


if __name__ == "__main__":
    IDE().mainloop()