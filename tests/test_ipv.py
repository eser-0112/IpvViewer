"""Testes com um .ipv sintético (montado aqui, sem arquivos de ninguém).

Rodar:  python3 -m unittest discover -s tests -v   (precisa de PYTHONPATH=src)
"""
import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ipv_viewer.ipv import ArquivoIPV, ErroIPV  # noqa: E402


def png(w, h, linhas):
    """Codificador PNG RGBA mínimo. linhas: lista de listas de (r,g,b,a)."""
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    cru = b"".join(b"\0" + b"".join(bytes(p) for p in l) for l in linhas)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(cru)) + chunk(b"IEND", b""))


def texto(s):
    return struct.pack(">H", len(s)) + s.encode()


def bloco(camada, tam, x, y, trechos, png_bytes, pw, ph):
    campos = struct.pack(">9i", *camada, *tam, x, y, pw, ph, 0)
    return (b"RPNG" + struct.pack(">ii", 45, 0) + b"\x04" + campos + b"\xff\xff\xff\x00"
            + struct.pack(">I", 2 * len(trechos)) + struct.pack(">%dH" % len(trechos), *trechos)
            + struct.pack(">I", len(png_bytes)) + png_bytes)


def ipv(w, h, blocos, animacao=0):
    cab = (b"\x01\x00\x01\x00\x00\x00\x00\x1d" + struct.pack(">d", 1.7e9) + struct.pack(">II", w, h)
           + texto("projeto") + texto("ibisPaint X") + texto("ver.14.1.2") + texto("teste T1")
           + b"\0" * 11 + b"\x01" + bytes([animacao]) + b"\0\0")
    return cab + b"".join(blocos) + b"\0" * 8 + texto("12345678-1234-1234-1234-123456789abc")


R, G, B, K = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (0, 0, 0, 255)
T = (0, 0, 0, 0)


class Testes(unittest.TestCase):
    def test_cabecalho(self):
        a = ArquivoIPV(ipv(4, 4, []))
        c = a.cabecalho
        self.assertEqual((c.largura, c.altura, c.app, c.versao), (4, 4, "ibisPaint X", "ver.14.1.2"))
        self.assertEqual(c.uuid, "12345678-1234-1234-1234-123456789abc")
        self.assertFalse(a.animacao)
        self.assertTrue(ArquivoIPV(ipv(4, 4, [], animacao=1)).animacao)

    def test_camada_cheia_vai_pro_lugar_certo(self):
        # caixa 2x2 em x=1, y=1 (de baixo pra cima) numa tela 4x4; pixels de baixo pra cima: R G / B K
        # as linhas do PNG vêm viradas: primeiro a linha de cima da fila (B K), depois (R G)
        p = png(2, 2, [[B, K], [R, G]])
        a = ArquivoIPV(ipv(4, 4, [bloco((4, 4), (2, 2), 1, 1, (0, 4), p, 2, 2)]))
        self.assertEqual(len(a.blocos), 1)
        self.assertEqual(a.blocos[0].tipo, "atual")
        w, h, px = a.renderizar(a.blocos[0])
        self.assertEqual((w, h), (4, 4))
        pix = lambda x, y: tuple(px[(y * w + x) * 4:(y * w + x) * 4 + 4])
        self.assertEqual(pix(1, 1), B)
        self.assertEqual(pix(2, 1), K)
        self.assertEqual(pix(1, 2), R)
        self.assertEqual(pix(2, 2), G)
        self.assertEqual(pix(0, 0), T)
        self.assertEqual(pix(3, 3), T)

    def test_trechos_transparentes(self):
        # caixa 2x2: trechos vazio1, pintado2, vazio1 -> pintados são o 2º e 3º pixel (de baixo pra cima)
        p = png(2, 1, [[R, G]])
        a = ArquivoIPV(ipv(2, 2, [bloco((2, 2), (2, 2), 0, 0, (1, 2, 1), p, 2, 1)]))
        w, h, px = a.renderizar(a.blocos[0])
        pix = lambda x, y: tuple(px[(y * w + x) * 4:(y * w + x) * 4 + 4])
        # fila bottom-up: [T R] [G T] -> de cima pra baixo: linha0 = G T, linha1 = T R
        self.assertEqual([pix(0, 0), pix(1, 0), pix(0, 1), pix(1, 1)], [G, T, T, R])

    def test_vazia_e_recorte(self):
        p = png(1, 1, [[R]])
        vazio = bloco((4, 4), (1, 1), 0, 0, (1,), png(1, 1, [[T]]), 1, 1)
        recorte = bloco((2, 2), (1, 1), 0, 0, (0, 1), p, 1, 1)
        a = ArquivoIPV(ipv(4, 4, [vazio, recorte]))
        self.assertEqual([b.tipo for b in a.blocos], ["vazia", "recorte"])

    def test_antigo_e_atual(self):
        p = png(1, 1, [[R]])
        b1 = bloco((4, 4), (1, 1), 0, 0, (0, 1), p, 1, 1)
        peq = bloco((2, 2), (1, 1), 0, 0, (0, 1), p, 1, 1)
        a = ArquivoIPV(ipv(4, 4, [b1, peq, b1]))
        self.assertEqual([b.tipo for b in a.blocos], ["antigo", "recorte", "atual"])
        self.assertTrue(a.blocos[2].repetido)

    def test_lixo(self):
        with self.assertRaises(ErroIPV):
            ArquivoIPV(b"isto nao e um ipv" * 10)
        with self.assertRaises(ErroIPV):
            ArquivoIPV(b"")


if __name__ == "__main__":
    unittest.main()
