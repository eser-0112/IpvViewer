#!/usr/bin/env python3
"""Troca o ID do app (ex.: io.github.eser_0112.IpvViewer) em todos os arquivos e nomes.

Uso:  python3 tools/trocar-id.py io.github.eser_0112.IpvViewer
"""
import os
import re
import sys

ANTIGO = "io.github.eser_0112.IpvViewer"
raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

if len(sys.argv) != 2 or not re.fullmatch(r"[A-Za-z][\w-]*(\.[A-Za-z][\w-]*){2,}", sys.argv[1]):
    sys.exit(__doc__)
novo = sys.argv[1]
ignorar = {".git", ".flatpak-builder", "build-dir", "repo", "__pycache__"}

for pasta, dirs, arquivos in os.walk(raiz):
    dirs[:] = [d for d in dirs if d not in ignorar]
    for nome in arquivos:
        caminho = os.path.join(pasta, nome)
        try:
            txt = open(caminho, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        if ANTIGO in txt:
            open(caminho, "w", encoding="utf-8").write(txt.replace(ANTIGO, novo))
            print("atualizado:", os.path.relpath(caminho, raiz))
        if ANTIGO in nome:
            os.rename(caminho, os.path.join(pasta, nome.replace(ANTIGO, novo)))
            print("renomeado: ", nome, "->", nome.replace(ANTIGO, novo))
# o ID do "developer" no metainfo usa só o começo (io.github.usuario)
print("\nPronto. Confira também o <developer id=...> em data/*.metainfo.xml.")
