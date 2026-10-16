#!/usr/bin/env python3
"""Extrai as camadas (ou quadros) de um arquivo .ipv do ibisPaint X.

Uso:  python3 ipv_layers.py arquivo.ipv pasta_de_saida
Precisa de:  pip install pillow numpy
"""
import io
import os
import struct
import sys

import numpy as np
from PIL import Image

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def ler_cabecalho(dados):
    """Largura/altura do canvas e o byte que diz se é animação ou desenho."""
    largura, altura = struct.unpack(">II", dados[0x10:0x18])
    # depois do id vêm 3 textos com tamanho de 2 bytes: app, versão, aparelho
    pos = dados.find(b"ibisPaint") - 2
    textos = []
    for _ in range(3):
        tam = struct.unpack(">H", dados[pos:pos + 2])[0]
        textos.append(dados[pos + 2:pos + 2 + tam].decode("latin-1"))
        pos += 2 + tam
    modo_animacao = None
    if dados[pos + 11] == 1:
        modo_animacao = dados[pos + 12] == 1
    return largura, altura, textos, modo_animacao


def achar_blocos_rpng(dados):
    """Procura todos os blocos 'RPNG' (um por imagem de camada guardada)."""
    blocos = []
    pos = 0
    while True:
        a = dados.find(b"RPNG", pos)
        if a < 0:
            break
        pos = a + 1
        campos = struct.unpack(">9i", dados[a + 13:a + 49])
        larg_camada, alt_camada, larg, alt, x, y = campos[:6]
        q = a + 49                                    # 4 bytes de marcador
        n = struct.unpack(">I", dados[q + 4:q + 8])[0]  # tamanho da lista, em bytes
        if n % 2 or larg <= 0 or alt <= 0:
            continue
        trechos = struct.unpack(">%dH" % (n // 2), dados[q + 8:q + 8 + n])
        if sum(trechos) != larg * alt:                # conferência de segurança
            continue
        r = q + 8 + n
        tam_png = struct.unpack(">I", dados[r:r + 4])[0]
        png = dados[r + 4:r + 4 + tam_png]
        if not png.startswith(PNG_SIG):
            continue
        blocos.append(dict(pos=a, camada=(larg_camada, alt_camada),
                           tam=(larg, alt), x=x, y=y, trechos=trechos, png=png))
    return blocos


def montar_camada(b, imagem_inteira=True):
    """Desfaz o 'empacotamento' e devolve uma imagem RGBA."""
    larg, alt = b["tam"]
    pilha = np.asarray(Image.open(io.BytesIO(b["png"])).convert("RGBA"))
    pixels = pilha[::-1].reshape(-1, 4)               # 1) linhas do PNG de baixo pra cima
    mascara = np.zeros(larg * alt, bool)              # 2) quais posições foram pintadas
    pos = 0
    for i, n in enumerate(b["trechos"]):
        if i % 2 == 1:                                # trechos ímpares = pintado
            mascara[pos:pos + n] = True
        pos += n
    saida = np.zeros((larg * alt, 4), np.uint8)
    saida[mascara] = pixels[:mascara.sum()]           # 3) encaixa os pixels nos buracos
    saida = saida.reshape(alt, larg, 4)[::-1]         # 4) linhas do recorte, de cima pra baixo
    img = Image.fromarray(saida, "RGBA")
    if not imagem_inteira:
        return img
    lw, lh = b["camada"]
    tela = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    tela.alpha_composite(img, (b["x"], lh - b["y"] - alt))   # y conta de baixo pra cima
    return tela


def main(caminho, pasta):
    dados = open(caminho, "rb").read()
    cw, ch, textos, anim = ler_cabecalho(dados)
    print("canvas %dx%d | %s | animação: %s" % (cw, ch, textos, anim))
    blocos = achar_blocos_rpng(dados)
    # "camadas atuais" = último grupo de blocos que têm o tamanho da tela inteira
    k = len(blocos) - 1
    while k >= 0 and blocos[k]["camada"] == (cw, ch):
        k -= 1
    os.makedirs(pasta, exist_ok=True)
    for i, b in enumerate(blocos):
        tela_inteira = b["camada"] == (cw, ch)
        tipo = ("atual" if i > k else "antigo") if tela_inteira else "recorte"
        montar_camada(b, tela_inteira).save(
            os.path.join(pasta, "%03d_%s.png" % (i, tipo)))
    print(len(blocos), "imagens salvas em", pasta)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
