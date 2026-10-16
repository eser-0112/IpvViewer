"""Interface GTK4 + libadwaita do Visualizador IPV."""
from __future__ import annotations

import os
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gsk", "4.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, GObject, Graphene, Gsk, Gtk  # noqa: E402

from . import __version__, ipv  # noqa: E402

APP_ID = "io.github.eser_0112.IpvViewer"
TAM_MINIATURA = 160

ROTULO = {
    "atual": "camada atual",
    "antigo": "estado antigo",
    "recorte": "recorte",
    "pronta": "imagem pronta",
    "vazia": "vazia",
}


def pixbuf_de_rgba(w: int, h: int, rgba: bytes) -> GdkPixbuf.Pixbuf:
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(rgba), GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)


def miniatura(w: int, h: int, rgba: bytes) -> GdkPixbuf.Pixbuf:
    """Miniatura já sobre um fundo xadrez (pra enxergar a transparência)."""
    esc = min(TAM_MINIATURA / w, TAM_MINIATURA / h)
    dw, dh = max(1, round(w * esc)), max(1, round(h * esc))
    modo = GdkPixbuf.InterpType.NEAREST if esc > 1 else GdkPixbuf.InterpType.BILINEAR
    return pixbuf_de_rgba(w, h, rgba).composite_color_simple(
        dw, dh, modo, 255, 8, 0xFFE3E6EF, 0xFFF7F8FB)


def cor(texto: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(texto)
    return c


# --------------------------------------------------------------- área da imagem
class AreaImagem(Gtk.Widget):
    """Mostra uma imagem com zoom e fundo xadrez/branco/preto."""

    __gtype_name__ = "IpvAreaImagem"

    def __init__(self):
        super().__init__()
        self.textura: Gdk.Texture | None = None
        self.zoom: float | None = None  # None = ajustar à janela
        self.fundo = "xadrez"
        self.set_hexpand(True)
        self.set_vexpand(True)

    def definir(self, textura=None, zoom=..., fundo=None):
        if textura is not None:
            self.textura = textura
        if zoom is not ...:
            self.zoom = zoom
        if fundo is not None:
            self.fundo = fundo
        self.queue_resize()
        self.queue_draw()

    def do_measure(self, orientation, para_tamanho):
        if self.textura is None or self.zoom is None:
            return 80, 80, -1, -1
        t = self.textura.get_width() if orientation == Gtk.Orientation.HORIZONTAL \
            else self.textura.get_height()
        n = max(1, int(t * self.zoom))
        return n, n, -1, -1

    def _xadrez(self, snap, x, y, w, h):
        """Fundo xadrez feito com quadradinhos (sem 'repeat', que deixa riscos em
        alguns renderizadores). Em imagens enormes os quadrados ficam maiores,
        pra não desenhar milhares deles."""
        quadro = 16
        while (w / quadro) * (h / quadro) / 2 > 3000:
            quadro *= 2
        snap.append_color(cor("#f4f5f9"), Graphene.Rect().init(x, y, w, h))
        escuro = cor("#d5d8e3")
        for j in range(0, (h + quadro - 1) // quadro):
            for i in range(j % 2, (w + quadro - 1) // quadro, 2):
                snap.append_color(escuro, Graphene.Rect().init(
                    x + i * quadro, y + j * quadro,
                    min(quadro, w - i * quadro), min(quadro, h - j * quadro)))

    def do_snapshot(self, snap):
        W, H = self.get_width(), self.get_height()
        cores = {"xadrez": "#2b2d36", "branco": "#ffffff", "preto": "#000000"}
        snap.append_color(cor(cores.get(self.fundo, "#2b2d36")),
                          Graphene.Rect().init(0, 0, W, H))
        if self.textura is None:
            return
        tw, th = self.textura.get_width(), self.textura.get_height()
        esc = min(W / tw, H / th) if self.zoom is None else self.zoom
        iw, ih = tw * esc, th * esc
        x, y = (W - iw) / 2, (H - ih) / 2
        if self.fundo == "xadrez":
            self._xadrez(snap, round(x), round(y), int(iw) + 1, int(ih) + 1)
        if esc >= 2:
            filtro = Gsk.ScalingFilter.NEAREST  # pixels bem definidos ao ampliar
        elif esc < 1:
            filtro = Gsk.ScalingFilter.TRILINEAR
        else:
            filtro = Gsk.ScalingFilter.LINEAR
        snap.append_scaled_texture(self.textura, filtro,
                                   Graphene.Rect().init(x, y, iw, ih))


# --------------------------------------------------------------------- página
class PaginaImagem(Adw.NavigationPage):
    """Tela com uma imagem grande, zoom, fundo e botão de salvar."""

    def __init__(self, janela: "Janela", indice: int):
        super().__init__(title="Imagem")
        self.janela = janela
        self.lista = janela.itens_visiveis()
        self.indice = indice

        self.area = AreaImagem()
        rolagem = Gtk.ScrolledWindow(child=self.area, hexpand=True, vexpand=True)

        cab = Adw.HeaderBar()
        anterior = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Anterior")
        proxima = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Próxima")
        anterior.connect("clicked", lambda *_: self.ir(self.indice - 1))
        proxima.connect("clicked", lambda *_: self.ir(self.indice + 1))
        cab.pack_start(anterior)
        cab.pack_start(proxima)
        salvar = Gtk.Button(icon_name="document-save-symbolic",
                            tooltip_text="Salvar esta imagem como PNG")
        salvar.connect("clicked", self.ao_salvar)
        cab.pack_end(salvar)

        barra = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6,
                        margin_start=12, margin_end=12)
        zoom = Gtk.Box(css_classes=["linked"])
        primeiro = None
        for rotulo, valor in (("Ajustar", None), ("100%", 1.0), ("200%", 2.0), ("400%", 4.0)):
            b = Gtk.ToggleButton(label=rotulo, active=valor is None)
            if primeiro is None:
                primeiro = b
            else:
                b.set_group(primeiro)
            b.connect("toggled", self.ao_zoom, valor)
            zoom.append(b)
        fundo = Gtk.Box(css_classes=["linked"])
        pri = None
        for rotulo, valor in (("Xadrez", "xadrez"), ("Branco", "branco"), ("Preto", "preto")):
            b = Gtk.ToggleButton(label=rotulo, active=valor == "xadrez")
            if pri is None:
                pri = b
            else:
                b.set_group(pri)
            b.connect("toggled", self.ao_fundo, valor)
            fundo.append(b)
        self.info = Gtk.Label(xalign=1, hexpand=True, css_classes=["dim-label", "caption"],
                              ellipsize=3)
        barra.append(zoom)
        barra.append(fundo)
        barra.append(self.info)

        vista = Adw.ToolbarView(content=rolagem)
        vista.add_top_bar(cab)
        vista.add_bottom_bar(barra)
        self.set_child(vista)

        ctl = Gtk.EventControllerKey()
        ctl.connect("key-pressed", self.ao_tecla)
        self.add_controller(ctl)
        self.ir(indice)

    def ao_tecla(self, _c, tecla, *_):
        if tecla == Gdk.KEY_Left:
            self.ir(self.indice - 1)
        elif tecla == Gdk.KEY_Right:
            self.ir(self.indice + 1)
        else:
            return False
        return True

    def ir(self, i: int):
        if not self.lista:
            return
        self.indice = i % len(self.lista)
        item = self.lista[self.indice]
        w, h, rgba = self.janela.arquivo.renderizar(item)
        self.rgba = (w, h, rgba)
        tex = Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.R8G8B8A8,
                                    GLib.Bytes.new(rgba), w * 4)
        self.area.definir(textura=tex)
        self.set_title(f"{ROTULO[item.tipo].capitalize()} {self.indice + 1} de {len(self.lista)}")
        extra = ""
        if isinstance(item, ipv.Bloco):
            extra = f" · conteúdo {item.tam[0]}×{item.tam[1]} em ({item.x}, {item.y})"
        self.info.set_label(f"{w}×{h}{extra}")

    def ao_zoom(self, botao, valor):
        if botao.get_active():
            self.area.definir(zoom=valor)

    def ao_fundo(self, botao, valor):
        if botao.get_active():
            self.area.definir(fundo=valor)

    def ao_salvar(self, *_):
        dlg = Gtk.FileDialog(title="Salvar imagem", initial_name=f"imagem_{self.indice + 1:03d}.png")
        dlg.save(self.janela, None, self.salvar_pronto)

    def salvar_pronto(self, dlg, res):
        try:
            arq = dlg.save_finish(res)
        except GLib.Error:
            return  # cancelou
        w, h, rgba = self.rgba
        try:
            pixbuf_de_rgba(w, h, rgba).savev(arq.get_path(), "png", [], [])
            self.janela.aviso(f"Salvo em {arq.get_basename()}")
        except GLib.Error as e:
            self.janela.aviso(f"Não consegui salvar: {e.message}")


# --------------------------------------------------------------------- janela
class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Visualizador IPV",
                         default_width=1100, default_height=760)
        self.arquivo: ipv.ArquivoIPV | None = None
        self.cartoes: list[Gtk.FlowBoxChild] = []
        self.filtro = "atual"
        self._token = 0

        self.avisos = Adw.ToastOverlay()
        self.nav = Adw.NavigationView()
        self.avisos.set_child(self.nav)
        self.set_content(self.avisos)

        # --- cabeçalho
        cab = Adw.HeaderBar()
        abrir = Gtk.Button(label="Abrir…", tooltip_text="Abrir um arquivo .ipv (Ctrl+O)")
        abrir.set_action_name("app.abrir")
        cab.pack_start(abrir)
        self.botao_ficha = Gtk.ToggleButton(icon_name="sidebar-show-symbolic", active=True,
                                            tooltip_text="Mostrar/esconder a ficha do arquivo",
                                            visible=False)
        cab.pack_start(self.botao_ficha)
        menu = Gio.Menu()
        menu.append("Salvar todas as imagens visíveis…", "app.salvar_todas")
        menu.append("Sobre", "app.sobre")
        cab.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                    primary=True))

        # --- tela vazia
        self.vazio = Adw.StatusPage(
            icon_name="image-x-generic-symbolic", title="Abra um arquivo .ipv",
            description="Arraste um projeto do ibisPaint X pra cá, ou clique em Abrir.\n"
                        "As camadas (ou os quadros da animação) aparecem em uma galeria.")
        b = Gtk.Button(label="Abrir arquivo…", halign=Gtk.Align.CENTER,
                       css_classes=["suggested-action", "pill"])
        b.set_action_name("app.abrir")
        self.vazio.set_child(b)

        # --- galeria
        self.caixa = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                 min_children_per_line=2, max_children_per_line=12,
                                 column_spacing=10, row_spacing=10, margin_top=12,
                                 margin_bottom=12, margin_start=12, margin_end=12,
                                 valign=Gtk.Align.START, activate_on_single_click=True)
        self.caixa.set_filter_func(self.passa_no_filtro)
        self.caixa.set_sort_func(lambda a, b: a.item.pos - b.item.pos)
        self.caixa.connect("child-activated", self.ao_ativar)
        rolagem = Gtk.ScrolledWindow(child=self.caixa, vexpand=True, hexpand=True)

        self.botoes_filtro = {}
        faixa = Gtk.Box(spacing=12, margin_top=8, margin_start=12, margin_end=12)
        grupo = Gtk.Box(css_classes=["linked"])
        primeiro = None
        for chave, rotulo in (("atual", "Camadas atuais"), ("antigo", "Estados antigos"),
                              ("recorte", "Recortes"), ("pronta", "Imagens prontas"),
                              ("todas", "Todas")):
            t = Gtk.ToggleButton(label=rotulo, active=chave == "atual")
            if primeiro is None:
                primeiro = t
            else:
                t.set_group(primeiro)
            t.connect("toggled", self.ao_filtro, chave)
            grupo.append(t)
            self.botoes_filtro[chave] = t
        self.repetidas = Gtk.CheckButton(label="Ocultar repetidas", active=True)
        self.repetidas.connect("toggled", lambda *_: self.caixa.invalidate_filter())
        self.contagem = Gtk.Label(css_classes=["dim-label"], hexpand=True, xalign=1)
        faixa.append(grupo)
        faixa.append(self.repetidas)
        faixa.append(self.contagem)
        self.progresso = Gtk.ProgressBar(visible=False, margin_start=12, margin_end=12)
        self.nota = Gtk.Label(xalign=0, wrap=True, css_classes=["dim-label", "caption"],
                              margin_start=12, margin_end=12, margin_top=4)
        centro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for w in (faixa, self.nota, self.progresso, rolagem):
            centro.append(w)

        # --- ficha do arquivo (lateral)
        self.ficha = Adw.PreferencesGroup(title="Ficha do arquivo", margin_top=12,
                                          margin_bottom=12, margin_start=12, margin_end=12)
        lateral = Gtk.ScrolledWindow(child=self.ficha, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.divisao = Adw.OverlaySplitView(sidebar=lateral, content=centro,
                                            sidebar_width_fraction=0.3,
                                            min_sidebar_width=260, max_sidebar_width=380)
        self.botao_ficha.bind_property(
            "active", self.divisao, "show-sidebar",
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.pilha = Gtk.Stack()
        self.pilha.add_named(self.vazio, "vazio")
        self.pilha.add_named(self.divisao, "conteudo")
        vista = Adw.ToolbarView(content=self.pilha)
        vista.add_top_bar(cab)
        self.nav.add(Adw.NavigationPage(title="Visualizador IPV", tag="lista", child=vista))

        # arrastar e soltar
        alvo = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        alvo.connect("drop", self.ao_soltar)
        self.add_controller(alvo)

    # ---------------------------------------------------------------- carregar
    def aviso(self, texto: str):
        self.avisos.add_toast(Adw.Toast(title=texto, timeout=4))

    def ao_soltar(self, _alvo, arquivo, *_):
        self.carregar(arquivo.get_path())
        return True

    def carregar(self, caminho: str):
        self._token += 1
        token = self._token
        self.arquivo = None
        self.cartoes.clear()
        while (c := self.caixa.get_first_child()) is not None:
            self.caixa.remove(c)
        self.progresso.set_visible(True)
        self.progresso.set_fraction(0)
        self.contagem.set_label("lendo…")
        self.pilha.set_visible_child_name("conteudo")
        self.nav.pop_to_tag("lista")
        threading.Thread(target=self._trabalho, args=(caminho, token), daemon=True).start()

    def _trabalho(self, caminho: str, token: int):
        try:
            arq = ipv.ArquivoIPV.abrir(caminho)
        except (OSError, ipv.ErroIPV) as e:
            GLib.idle_add(self._erro, token, str(e))
            return
        GLib.idle_add(self._mostrar_ficha, token, arq)
        # camadas atuais e imagens prontas primeiro; o resto em ordem de arquivo
        ordem = sorted(arq.itens, key=lambda i: (i.tipo not in ("atual", "pronta"), i.pos))
        for n, item in enumerate(ordem, 1):
            if token != self._token:
                return
            try:
                w, h, rgba = arq.renderizar(item)
                if w * h == 0:
                    continue
                mini = miniatura(w, h, rgba)
            except Exception as e:  # um bloco ruim não derruba o resto
                print("aviso:", e, file=sys.stderr)
                continue
            GLib.idle_add(self._novo_cartao, token, item, mini, w, h, n, len(ordem))
        GLib.idle_add(self._fim, token)

    def _erro(self, token, msg):
        if token != self._token:
            return
        self.progresso.set_visible(False)
        self.pilha.set_visible_child_name("vazio")
        self.aviso(msg or "Não consegui abrir esse arquivo.")

    def _mostrar_ficha(self, token, arq: ipv.ArquivoIPV):
        if token != self._token:
            return
        self.arquivo = arq
        c = arq.cabecalho
        linhas = [("Arquivo", arq.nome), ("Tamanho", tamanho(len(arq.dados))),
                  ("App", f"{c.app} {c.versao}"), ("Aparelho", c.aparelho),
                  ("Canvas", f"{c.largura} × {c.altura} px"),
                  ("Tipo", "Animação" if arq.animacao else "Desenho"),
                  ("Criado", time.strftime("%d/%m/%Y %H:%M", time.localtime(c.criado))),
                  ("Camadas" if not arq.animacao else "Quadros", self.resumo_camadas()),
                  ("ID do projeto", c.id_projeto)]
        n, t0, t1 = arq.pontos_de_caneta()
        if n:
            linhas.insert(7, ("Pontos de caneta", f"{n:,}".replace(",", ".")))
        if c.uuid:
            linhas.append(("UUID", c.uuid))
        # recria o grupo inteiro para não acumular linhas de arquivos anteriores
        novo = Adw.PreferencesGroup(title="Ficha do arquivo", margin_top=12, margin_bottom=12,
                                    margin_start=12, margin_end=12)
        for titulo, valor in linhas:
            novo.add(Adw.ActionRow(title=titulo, subtitle=GLib.markup_escape_text(str(valor)),
                                   subtitle_selectable=True, css_classes=["property"]))
        self.divisao.get_sidebar().set_child(novo)
        self.ficha = novo
        self.botao_ficha.set_visible(True)
        anim = arq.animacao
        self.botoes_filtro["atual"].set_label("Quadros" if anim else "Camadas atuais")
        self.botoes_filtro["antigo"].set_visible(not anim)
        self.nota.set_label(
            "Cada quadro é uma imagem do tamanho do canvas, na ordem do arquivo."
            if anim else
            "“Camadas atuais” é o último grupo de camadas salvo no arquivo. "
            "Os recortes e estados antigos são o histórico de desfazer do app.")
        self.set_title(f"{arq.nome} — Visualizador IPV")

    def resumo_camadas(self) -> str:
        a = self.arquivo
        atuais = sum(1 for i in a.blocos if i.tipo == "atual")
        antigos = sum(1 for i in a.blocos if i.tipo == "antigo")
        if a.animacao:
            return f"{atuais} quadros ({a.imagens_inteiras_distintas} imagens inteiras diferentes)"
        return f"{atuais} atuais, {antigos} estados antigos"

    def _novo_cartao(self, token, item, mini, w, h, n, total):
        if token != self._token:
            return
        textura = Gdk.Texture.new_for_pixbuf(mini)
        quadro = Gtk.Picture(paintable=textura, can_shrink=False, content_fit=Gtk.ContentFit.CONTAIN)
        quadro.set_size_request(TAM_MINIATURA, TAM_MINIATURA)
        rotulo = Gtk.Label(label=f"{w}×{h} · {ROTULO[item.tipo]}", css_classes=["caption", "dim-label"],
                           ellipsize=3, margin_bottom=4)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["card"])
        caixa.append(quadro)
        caixa.append(rotulo)
        filho = Gtk.FlowBoxChild(child=caixa)
        filho.item = item
        self.cartoes.append(filho)
        self.caixa.append(filho)
        self.progresso.set_fraction(n / total)
        self.atualizar_contagem()

    def _fim(self, token):
        if token == self._token:
            self.progresso.set_visible(False)
            self.atualizar_contagem()

    # ----------------------------------------------------------------- filtros
    def passa_no_filtro(self, filho) -> bool:
        item = filho.item
        if self.repetidas.get_active() and item.repetido:
            return False
        return self.filtro == "todas" or item.tipo == self.filtro

    def ao_filtro(self, botao, chave):
        if botao.get_active():
            self.filtro = chave
            self.caixa.invalidate_filter()
            self.atualizar_contagem()

    def itens_visiveis(self):
        return [c.item for c in sorted(self.cartoes, key=lambda c: c.item.pos)
                if self.passa_no_filtro(c)]

    def atualizar_contagem(self):
        self.contagem.set_label(f"{len(self.itens_visiveis())} de {len(self.cartoes)}")

    def ao_ativar(self, _caixa, filho):
        visiveis = self.itens_visiveis()
        if filho.item in visiveis:
            self.nav.push(PaginaImagem(self, visiveis.index(filho.item)))

    # ------------------------------------------------------ salvar tudo (pasta)
    def salvar_todas(self):
        if self.arquivo is None:
            self.aviso("Abra um arquivo primeiro.")
            return
        Gtk.FileDialog(title="Escolha a pasta onde salvar").select_folder(
            self, None, self._pasta_escolhida)

    def _pasta_escolhida(self, dlg, res):
        try:
            pasta = dlg.select_folder_finish(res).get_path()
        except GLib.Error:
            return
        itens, arq = self.itens_visiveis(), self.arquivo
        self.aviso(f"Salvando {len(itens)} imagens…")

        def trabalho():
            erros = 0
            for n, item in enumerate(itens, 1):
                try:
                    w, h, rgba = arq.renderizar(item)
                    pixbuf_de_rgba(w, h, rgba).savev(
                        os.path.join(pasta, f"{n:03d}_{item.tipo}.png"), "png", [], [])
                except Exception:
                    erros += 1
            msg = f"{len(itens) - erros} imagens salvas em {os.path.basename(pasta)}"
            GLib.idle_add(self.aviso, msg + (f" ({erros} com erro)" if erros else ""))

        threading.Thread(target=trabalho, daemon=True).start()


def tamanho(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB".replace(".", ",")
    return f"{n / 1024 ** 2:.1f} MB".replace(".", ",")


# ------------------------------------------------------------------ aplicação
class Aplicacao(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.janela: Janela | None = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        for nome, funcao, atalho in (("abrir", self.acao_abrir, "<Primary>o"),
                                     ("salvar_todas", lambda *_: self.janela.salvar_todas(), None),
                                     ("sobre", self.acao_sobre, None),
                                     ("sair", lambda *_: self.quit(), "<Primary>q")):
            a = Gio.SimpleAction.new(nome, None)
            a.connect("activate", funcao)
            self.add_action(a)
            if atalho:
                self.set_accels_for_action(f"app.{nome}", [atalho])

    def _janela(self) -> Janela:
        if self.janela is None:
            self.janela = Janela(self)
        return self.janela

    def do_activate(self):
        self._janela().present()

    def do_open(self, arquivos, n, dica):
        j = self._janela()
        j.present()
        if arquivos:
            j.carregar(arquivos[0].get_path())

    def acao_abrir(self, *_):
        filtro = Gtk.FileFilter(name="Projetos do ibisPaint X (*.ipv)")
        filtro.add_pattern("*.ipv")
        filtro.add_pattern("*.IPV")
        todos = Gtk.FileFilter(name="Todos os arquivos")
        todos.add_pattern("*")
        lista = Gio.ListStore.new(Gtk.FileFilter)
        lista.append(filtro)
        lista.append(todos)
        dlg = Gtk.FileDialog(title="Abrir arquivo .ipv", filters=lista, default_filter=filtro)
        dlg.open(self._janela(), None, self._aberto)

    def _aberto(self, dlg, res):
        try:
            arq = dlg.open_finish(res)
        except GLib.Error:
            return
        self._janela().carregar(arq.get_path())

    def acao_sobre(self, *_):
        sobre = Adw.AboutDialog(
            application_name="Visualizador IPV", application_icon=APP_ID,
            version=__version__, developer_name="Eser",
            comments="Abre projetos do ibisPaint X (.ipv) e mostra as camadas ou os quadros "
                     "da animação.\n\nO formato foi decifrado por engenharia reversa, "
                     "então pode haver arquivos que ainda não funcionam.",
            license_type=Gtk.License.MIT_X11)
        sobre.present(self._janela())


def main(argv=None) -> int:
    return Aplicacao().run(argv if argv is not None else sys.argv)
