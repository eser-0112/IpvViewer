#!/bin/sh
# Instala o app só pro seu usuário (sem Flatpak, sem sudo) e põe no menu de aplicativos.
# Uso:  sh tools/instalar-local.sh            (instala)
#       sh tools/instalar-local.sh remover    (desinstala)
set -e
ID=io.github.eser_0112.IpvViewer
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
DADOS=${XDG_DATA_HOME:-$HOME/.local/share}
DEST=$DADOS/ipv-viewer

if [ "$1" = "remover" ]; then
  rm -rf "$DEST" "$DADOS/applications/$ID.desktop" "$DADOS/mime/packages/$ID.xml" \
         "$DADOS/icons/hicolor/scalable/apps/$ID.svg"
  echo "Removido."
else
  mkdir -p "$DEST" "$DADOS/applications" "$DADOS/mime/packages" "$DADOS/icons/hicolor/scalable/apps"
  rm -rf "$DEST/src" "$DEST/bin"
  cp -r "$RAIZ/src" "$RAIZ/bin" "$DEST/"
  find "$DEST" -name __pycache__ -type d -prune -exec rm -rf {} +
  chmod +x "$DEST/bin/ipv-viewer"
  # o .desktop precisa do caminho completo do launcher
  sed "s|^Exec=.*|Exec=$DEST/bin/ipv-viewer %f|" "$RAIZ/data/$ID.desktop" > "$DADOS/applications/$ID.desktop"
  cp "$RAIZ/data/$ID.xml" "$DADOS/mime/packages/$ID.xml"
  cp "$RAIZ/data/$ID.svg" "$DADOS/icons/hicolor/scalable/apps/$ID.svg"
  echo "Instalado em $DEST"
fi

command -v update-mime-database >/dev/null && update-mime-database "$DADOS/mime" || true
command -v update-desktop-database >/dev/null && update-desktop-database "$DADOS/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$DADOS/icons/hicolor" 2>/dev/null || true
echo "Pronto. Procure por \"Visualizador IPV\" no menu de aplicativos (se não aparecer, saia e entre na sessão)."
