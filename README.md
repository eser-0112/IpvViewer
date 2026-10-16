# Visualizador IPV

Abre projetos `.ipv` do ibisPaint X e mostra as camadas (ou os quadros, se for animação).
App nativo GTK4 + libadwaita, pronto pra virar Flatpak.

O formato foi decifrado por engenharia reversa: veja `docs/FORMATO.md`.
**Ainda não lê:** nome das camadas, opacidade, camada oculta. A ordem das camadas sai certa na prática (a ordem em que ficam salvas no arquivo), mas não sei se isso vale pra todo arquivo.

## 1. Rodar direto da pasta (mais fácil, teste primeiro)

```fish
sudo pacman -S python-gobject gtk4 libadwaita
./bin/ipv-viewer meu-arquivo.ipv
```

Sem argumento ele abre vazio; use "Abrir…" ou arraste o arquivo pra janela.
(Em Debian/Ubuntu: `sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1`.)

## 1b. Colocar no menu de aplicativos 

```fish
sh tools/instalar-local.sh
```

Copia o app pra `~/.local/share/ipv-viewer`, cria o atalho "Visualizador IPV" e registra o
tipo `.ipv` (aí o gerenciador de arquivos passa a oferecer "Abrir com Visualizador IPV").
Não precisa de sudo. Pra desfazer: `sh tools/instalar-local.sh remover`.


### O que cada parte da receita faz

- `app-id`: o nome único do app. Precisa seguir o padrão de domínio invertido.
- `runtime`/`sdk`: o "Linux de bolso" com GTK, libadwaita e Python que o app usa.
- `finish-args`: permissões. Só janela e GPU. **Sem acesso a pastas**: os arquivos
  chegam pelo seletor de arquivos do sistema (portal), então é seguro.
- `modules`: copia o código pra `/app/share/ipv-viewer` e instala launcher, ícone,
  `.desktop`, metainfo e o tipo MIME de `*.ipv`.

## 3. Trocar o ID (obrigatório pra publicar)

O ID atual (`io.github.eser_0112.IpvViewer`) é só um chute. Pro Flathub ele precisa ser
`io.github.eser_0112_DO_GITHUB.IpvViewer` (ou um domínio que seja seu):

```fish
python3 tools/trocar-id.py io.github.eser_0112.IpvViewer
```

Ele troca o ID dentro dos arquivos e renomeia os arquivos de `data/` e o `.yml`.
Depois confira o `<developer id=...>` e o nome do autor em `data/*.metainfo.xml`,
e o nome no `LICENSE`.

## Testes

```fish
python3 -m unittest discover -s tests -v
```

## Licença

MIT
