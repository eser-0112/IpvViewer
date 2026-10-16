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

## 1b. Colocar no menu de aplicativos (sem Flatpak)

```fish
sh tools/instalar-local.sh
```

Copia o app pra `~/.local/share/ipv-viewer`, cria o atalho "Visualizador IPV" e registra o
tipo `.ipv` (aí o gerenciador de arquivos passa a oferecer "Abrir com Visualizador IPV").
Não precisa de sudo. Pra desfazer: `sh tools/instalar-local.sh remover`.

## 2. Montar o Flatpak

```fish
sudo pacman -S flatpak flatpak-builder
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo

# descubra qual versão do runtime GNOME existe e confira a linha runtime-version
# do arquivo io.github.eser_0112.IpvViewer.yml (hoje está '50')
flatpak remote-ls flathub --runtime | grep org.gnome.Platform

flatpak install --user flathub org.gnome.Platform//50 org.gnome.Sdk//50
flatpak-builder --user --install --force-clean build-dir io.github.eser_0112.IpvViewer.yml
flatpak run io.github.eser_0112.IpvViewer
```

Se a versão '50' não existir, troque no `.yml` pela que apareceu no `grep` e refaça.
Depois de instalado, ele aparece no menu de apps e o gerenciador de arquivos passa a
oferecê-lo para `.ipv`.

Pra gerar um arquivo `.flatpak` e mandar pra alguém:

```fish
flatpak-builder --force-clean --repo=repo build-dir io.github.eser_0112.IpvViewer.yml
flatpak build-bundle repo ipv-viewer.flatpak io.github.eser_0112.IpvViewer
# quem recebe instala com: flatpak install ipv-viewer.flatpak
```

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

## 4. Publicar no Flathub

Guia oficial: https://docs.flathub.org/docs/for-app-authors/submission
Regras: https://docs.flathub.org/docs/for-app-authors/requirements

**Aviso sobre IA:** o Flathub exige que você avise quando partes do projeto foram geradas
por IA (código, documentação, empacotamento) e **não aceita manifesto gerado ou ajudado por
IA**. Também não aceita IA abrindo o PR nem escrevendo commit/descrição do PR. Este projeto
foi feito com ajuda de IA, então: avise isso na descrição do PR, e escreva o manifesto que vai
no PR você mesmo (o `.yml` deste repositório serve só pra testar aqui).

Resumo:

1. Suba este projeto num repositório público no GitHub, com o nome batendo com o ID
   (`io.github.USUARIO.IpvViewer` -> `github.com/USUARIO/IpvViewer`). Rode antes
   `python3 tools/trocar-id.py io.github.USUARIO.IpvViewer`.
2. No `data/*.metainfo.xml` coloque `<url type="homepage">` com o link do repositório e um
   bloco `<screenshots>` com prints do app (as imagens ficam no repositório; use a URL "raw").
3. Crie uma tag de versão (`git tag v0.1.0 && git push --tags`).
4. Escreva o manifesto do Flathub: igual ao daqui, mas com fonte `type: git`
   (`url`, `tag`, `commit`) em vez de `type: dir`, e instalando o `LICENSE` em
   `/app/share/licenses/$FLATPAK_ID`.
5. Teste e rode o linter:
   `flatpak install -y flathub org.flatpak.Builder`
   `flatpak run --command=flathub-build org.flatpak.Builder --install io.github.USUARIO.IpvViewer.yml`
   `flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest io.github.USUARIO.IpvViewer.yml`
6. Faça fork de `flathub/flathub` (sem marcar "copy master branch only"), clone a branch
   `new-pr`, crie uma branch nova a partir dela, adicione **só o manifesto**, dê push e abra o
   PR com base em `new-pr`, título `Add io.github.USUARIO.IpvViewer`.
7. Responda os comentários dos revisores e, quando estiver tudo resolvido, comente
   `bot, build` no PR.

## Testes

```fish
python3 -m unittest discover -s tests -v
```

## Licença

MIT
