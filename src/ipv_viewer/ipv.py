"""Leitor de arquivos .ipv do ibisPaint X.

O formato não é documentado: tudo aqui vem de engenharia reversa (veja
docs/FORMATO.md). Este módulo não depende de numpy nem de Pillow. Para ler os
PNGs ele usa o GdkPixbuf (que já vem no GNOME/Flatpak) e, se não houver GTK,
cai para o Pillow.
"""
from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass, field

PNG_SIG = b"\x89PNG\r\n\x1a\n"
MARCADOR_PONTO = b"\x02\x00\x03\x01\x00\x00\x00\x10"


class ErroIPV(Exception):
    """O arquivo não parece (ou não pôde ser lido como) um .ipv."""


# ---------------------------------------------------------------- PNG -> RGBA
try:  # caminho normal: GdkPixbuf (já vem junto com o GTK)
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    def decodificar_png(png: bytes):
        """Devolve (largura, altura, bytes RGBA sem linhas de enchimento)."""
        carregador = GdkPixbuf.PixbufLoader.new_with_type("png")
        carregador.write(png)
        carregador.close()
        pb = carregador.get_pixbuf()
        if pb is None:
            raise ErroIPV("PNG inválido")
        if not pb.get_has_alpha() or pb.get_n_channels() != 4:
            pb = pb.add_alpha(False, 0, 0, 0)
        w, h, passo = pb.get_width(), pb.get_height(), pb.get_rowstride()
        px = pb.get_pixels()
        if passo != w * 4:  # tira o enchimento no fim de cada linha
            px = b"".join(px[i * passo:i * passo + w * 4] for i in range(h))
        return w, h, bytes(px)

except (ImportError, ValueError):  # sem GTK: usa Pillow
    from PIL import Image

    def decodificar_png(png: bytes):
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        return im.width, im.height, im.tobytes()


# ------------------------------------------------------------------- modelos
@dataclass
class Cabecalho:
    largura: int
    altura: int
    id_projeto: str
    app: str
    versao: str
    aparelho: str
    criado: float
    modo_animacao: bool | None  # None = não deu pra saber
    uuid: str | None


@dataclass
class Bloco:
    """Um bloco 'RPNG': a imagem de uma camada (ou de um quadro/recorte)."""

    pos: int
    camada: tuple[int, int]  # tamanho da área de origem
    tam: tuple[int, int]     # tamanho da caixa com o conteúdo
    x: int
    y: int                   # conta de baixo pra cima
    trechos: tuple[int, ...]  # vazio, pintado, vazio, pintado...
    png: bytes
    tipo: str = "recorte"    # atual | antigo | recorte | vazia
    repetido: bool = False

    @property
    def opacos(self) -> int:
        return sum(self.trechos[1::2])


@dataclass
class ImagemPronta:
    """Um PNG comum guardado no arquivo (imagem final, miniaturas...)."""

    pos: int
    png: bytes
    largura: int
    altura: int
    tipo: str = "pronta"
    repetido: bool = False


Item = Bloco | ImagemPronta


# ------------------------------------------------------------ leitura do .ipv
def _ler_cabecalho(d: bytes) -> Cabecalho:
    k = d.find(b"ibisPaint", 0, 400)
    if len(d) < 64 or k < 2:
        raise ErroIPV("Isso não parece um arquivo .ipv do ibisPaint X.")
    try:
        criado = struct.unpack(">d", d[8:16])[0]
        largura, altura = struct.unpack(">II", d[0x10:0x18])
        tam = struct.unpack(">H", d[0x18:0x1A])[0]
        id_projeto = d[0x1A:0x1A + tam].decode("latin-1")
        pos = k - 2
        textos = []
        for _ in range(3):
            n = struct.unpack(">H", d[pos:pos + 2])[0]
            textos.append(d[pos + 2:pos + 2 + n].decode("latin-1"))
            pos += 2 + n
    except (struct.error, UnicodeDecodeError) as e:
        raise ErroIPV("Cabeçalho do .ipv ilegível.") from e
    modo = None
    if len(d) > pos + 13 and d[pos + 11] == 1:
        modo = d[pos + 12] == 1
    achado = None
    resto = d[-160:].decode("latin-1")
    import re

    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", resto)
    if m:
        achado = m.group(0)
    return Cabecalho(largura, altura, id_projeto, textos[0], textos[1], textos[2],
                     criado, modo, achado)


def _achar_blocos(d: bytes) -> list[Bloco]:
    blocos = []
    pos = 0
    while True:
        a = d.find(b"RPNG", pos)
        if a < 0:
            break
        pos = a + 1
        try:
            campos = struct.unpack(">9i", d[a + 13:a + 49])
            q = a + 49
            n = struct.unpack(">I", d[q + 4:q + 8])[0]
            if n % 2 or n > 4_000_000:
                continue
            lw, lh, bw, bh, x, y = campos[:6]
            if bw <= 0 or bh <= 0 or bw * bh > 100_000_000:
                continue
            trechos = struct.unpack(">%dH" % (n // 2), d[q + 8:q + 8 + n])
            if sum(trechos) != bw * bh:  # conferência: tem que fechar certinho
                continue
            r = q + 8 + n
            tam_png = struct.unpack(">I", d[r:r + 4])[0]
            png = d[r + 4:r + 4 + tam_png]
        except struct.error:
            continue
        if len(png) != tam_png or not png.startswith(PNG_SIG):
            continue
        blocos.append(Bloco(a, (lw, lh), (bw, bh), x, y, trechos, png))
    return blocos


def _fim_do_png(d: bytes, p: int) -> int:
    q = p + 8
    while q + 12 <= len(d):
        n = struct.unpack(">I", d[q:q + 4])[0]
        tipo = d[q + 4:q + 8]
        if not tipo.isalpha() or n > len(d) - q - 12:
            return -1
        q += 12 + n
        if tipo == b"IEND":
            return q
    return -1


def _achar_pngs_soltos(d: bytes, ocupados: set[int]) -> list[ImagemPronta]:
    out = []
    p = 0
    while True:
        p = d.find(PNG_SIG, p)
        if p < 0:
            break
        e = _fim_do_png(d, p)
        if e < 0:
            p += 1
            continue
        if p not in ocupados:
            w, h = struct.unpack(">II", d[p + 16:p + 24])
            out.append(ImagemPronta(p, d[p:e], w, h))
        p = e
    return out


def _chave(item: Item) -> bytes:
    h = hashlib.blake2b(digest_size=12)
    h.update(item.png)
    if isinstance(item, Bloco):
        h.update(repr((item.camada, item.tam, item.x, item.y)).encode())
        h.update(struct.pack(">%dH" % len(item.trechos), *item.trechos))
    return h.digest()


class ArquivoIPV:
    """Um arquivo .ipv aberto, com as imagens já separadas por tipo."""

    def __init__(self, dados: bytes, nome: str = ""):
        self.dados = dados
        self.nome = nome
        self.cabecalho = _ler_cabecalho(dados)
        c = self.cabecalho
        self.blocos = _achar_blocos(dados)
        soltos = _achar_pngs_soltos(dados, {self._pos_png(b) for b in self.blocos})
        self._classificar(soltos)
        self.itens: list[Item] = sorted([*self.blocos, *soltos], key=lambda i: i.pos)
        vistos = set()
        for i in self.itens:
            k = _chave(i)
            i.repetido = k in vistos
            vistos.add(k)
        inteiros = {
            _chave(i) for i in self.itens
            if (isinstance(i, Bloco) and i.camada == (c.largura, c.altura)
                and i.tipo != "vazia")
            or (isinstance(i, ImagemPronta) and (i.largura, i.altura) == (c.largura, c.altura))
        }
        self.imagens_inteiras_distintas = len(inteiros)
        self.animacao = (c.modo_animacao if c.modo_animacao is not None
                         else len(inteiros) >= 3)
        self._pontos = None

    @staticmethod
    def _pos_png(b: Bloco) -> int:
        return b.pos + 49 + 8 + 2 * len(b.trechos) + 4

    @classmethod
    def abrir(cls, caminho: str) -> "ArquivoIPV":
        with open(caminho, "rb") as f:
            return cls(f.read(), caminho.replace("\\", "/").rsplit("/", 1)[-1])

    def _classificar(self, soltos):
        c = self.cabecalho
        tela = (c.largura, c.altura)
        # "camadas atuais" = último grupo seguido de blocos do tamanho da tela
        k = len(self.blocos) - 1
        while k >= 0 and self.blocos[k].camada == tela:
            k -= 1
        for i, b in enumerate(self.blocos):
            if b.opacos == 0:
                b.tipo = "vazia"
            elif b.camada == tela:
                b.tipo = "atual" if i > k else "antigo"
            else:
                b.tipo = "recorte"

    # -- informações extras
    def pontos_de_caneta(self):
        """(quantidade, primeiro_instante, ultimo_instante) dos pontos da caneta.

        Só entendi esse registro no app 13.x; em outras versões pode dar 0.
        """
        if self._pontos is None:
            d, n, t0, t1, p = self.dados, 0, None, None, 0
            while True:
                p = d.find(MARCADOR_PONTO, p)
                if p < 0 or p + 24 > len(d):
                    break
                t = struct.unpack(">d", d[p + 8:p + 16])[0]
                if 1.4e9 < t < 2.5e9:
                    n += 1
                    t0 = t if t0 is None else min(t0, t)
                    t1 = t if t1 is None else max(t1, t)
                p += 28
            self._pontos = (n, t0, t1)
        return self._pontos

    # -- montagem das imagens
    def renderizar(self, item: Item, tela_inteira: bool | None = None):
        """Devolve (largura, altura, bytes RGBA) da imagem do item."""
        if isinstance(item, ImagemPronta):
            return decodificar_png(item.png)
        if tela_inteira is None:
            tela_inteira = item.tipo in ("atual", "antigo")
        return _montar_camada(item, tela_inteira)


def _montar_camada(b: Bloco, tela_inteira: bool):
    bw, bh = b.tam
    w, h, px = decodificar_png(b.png)
    if b.opacos > w * h:
        raise ErroIPV("PNG menor do que a lista de trechos pede.")
    # 1) as linhas do PNG estão de cabeça pra baixo: vira de volta e lê em fila
    linhas = [px[i * w * 4:(i + 1) * w * 4] for i in range(h)]
    fila = b"".join(reversed(linhas))
    # 2) encaixa os pixels pintados nos lugares dados pela lista de trechos
    caixa = bytearray(bw * bh * 4)  # linhas de baixo pra cima
    pos = lido = 0
    for i, n in enumerate(b.trechos):
        if i & 1 and n:
            caixa[pos * 4:(pos + n) * 4] = fila[lido * 4:(lido + n) * 4]
            lido += n
        pos += n
    # 3) a caixa foi montada de baixo pra cima: vira pra ficar de cima pra baixo
    linhas_caixa = [bytes(caixa[r * bw * 4:(r + 1) * bw * 4]) for r in range(bh)][::-1]
    if not tela_inteira:
        return bw, bh, b"".join(linhas_caixa)
    lw, lh = b.camada
    tela = bytearray(lw * lh * 4)
    topo = lh - b.y - bh  # o y do arquivo conta de baixo pra cima
    for j, linha in enumerate(linhas_caixa):
        dy = topo + j
        if not 0 <= dy < lh:
            continue
        x0, x1 = max(b.x, 0), min(b.x + bw, lw)
        if x1 <= x0:
            continue
        tela[(dy * lw + x0) * 4:(dy * lw + x1) * 4] = linha[(x0 - b.x) * 4:(x1 - b.x) * 4]
    return lw, lh, bytes(tela)
