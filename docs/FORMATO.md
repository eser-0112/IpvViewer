# O formato .IPV do ibisPaint X, explicado

Este documento conta **como o arquivo `.ipv` do ibisPaint X é organizado por dentro** e **como eu consegui descobrir isso** sem ter nenhuma documentação oficial. Foi escrito para quem nunca mexeu com "engenharia reversa": os termos difíceis são explicados no caminho e há um glossário no final.

> **Aviso importante.** Isto é engenharia reversa, não documentação oficial. Tudo aqui vem da análise de **4 arquivos** (duas versões do app: 13.1.19 e 14.1.2, os dois feitos num Samsung SM-A256E). O que está marcado como **confirmado** foi testado e bate com os arquivos. O que está marcado como **palpite** pode estar errado. Outras versões do app ou outros aparelhos podem ter diferenças.

---

## 1. O resumo em 30 segundos

- O `.ipv` é o **arquivo de projeto** do ibisPaint X: guarda o desenho inteiro, com camadas, histórico e a gravação dos traços.
- Dentro dele há **imagens PNG**, mas elas **não são imagens normais**. Cada PNG é uma "caixa" com os pixels pintados de uma camada, **empilhados um atrás do outro, de cabeça pra baixo**. Se você abrir esse PNG direto, parece um rabisco sem sentido.
- Junto de cada PNG existe uma **lista de números** do tipo "pula 4, pinta 5, pula 8, pinta 10...". Essa lista diz **onde** cada pixel da caixa devia ficar na camada.
- Com a lista + o PNG de cabeça pra baixo, dá pra **remontar a camada exatamente como ela era** (testei: diferença de zero pixels).
- Um byte do cabeçalho diz se o arquivo é **animação** ou **desenho normal**.

---

## 2. Antes de começar: o que é "olhar dentro de um arquivo"?

Todo arquivo de computador é só uma **fila enorme de números de 0 a 255**. Cada número é um **byte**. Um programa decide uma "receita": "os 4 primeiros bytes são a largura, os próximos 4 são a altura, depois vem um texto..." e assim por diante. Sem a receita, o arquivo parece lixo.

Engenharia reversa é **descobrir a receita olhando só o resultado**. É como receber um bolo e tentar descobrir os ingredientes e a ordem do preparo, provando e comparando com outros bolos.

Para ler os bytes usamos o **hexadecimal**: em vez de escrever 0 a 255, escrevemos de `00` a `ff` (dois caracteres por byte). Por exemplo, `00 00 01 e0` é o número 480.

Dois detalhes que aparecem o tempo todo:

- **Big-endian**: números que ocupam vários bytes são escritos "do maior pro menor", como lemos: `00 00 01 e0` = 480 (e não 0xe0010000). Esse arquivo usa sempre esse jeito.
- **Textos com tamanho na frente**: um texto vem como `00 0b` (tamanho = 11) seguido de 11 letras (`ibisPaint X`).

---

## 3. O mapa do arquivo

De forma simplificada, o arquivo é assim, de cima pra baixo:

| Parte | O que tem | Estado |
|---|---|---|
| Cabeçalho | datas, tamanho do desenho, nome do app, versão, aparelho, modo (animação/desenho) | confirmado |
| Registros da caneta | os pontos (x, y, tempo) de cada traço | só parcialmente entendido |
| Blocos de imagem (`RPNG`) | uma imagem por camada/quadro/recorte, no formato "caixa" | **confirmado** (o grosso deste documento) |
| Final do arquivo | nome do projeto, um UUID (código único), um texto curto que parece ser o nome do autor (no teste era `eu`), e tabelas de camadas e ajustes (palpite) | só olhei por cima |

### 3.1 O cabeçalho (confirmado)

| Posição (hex) | Tamanho | O que é |
|---|---|---|
| `0x00` | 8 bytes | começo sempre igual nos 4 arquivos (`01 00 01 00 00 00 00 1d`); não sei a função |
| `0x08` | 8 bytes | data de criação, como número decimal de 8 bytes (segundos desde 1970) |
| `0x10` | 4 bytes | **largura** do desenho em pixels |
| `0x14` | 4 bytes | **altura** do desenho em pixels |
| `0x18` | 2 + texto | ID do projeto (ex.: `E1WJJDEVYP`) |
| em seguida | 3 textos | `ibisPaint X`, a versão (`ver.14.1.2`) e o aparelho (`samsung SM-A256E`) |
| depois do aparelho | 11 bytes `00`, um `01` e **o byte de modo** | **1 = animação, 0 = desenho** |

Sobre o byte de modo: nos meus arquivos, o de animação tem `1` e os dois desenhos têm `0`. Com tão poucos exemplos, isso é **muito provável, mas não 100% garantido**.

---

## 4. As camadas: o truque principal

### 4.1 O que parecia estar errado

Quando extraí os PNGs de dentro do arquivo, muitos pareciam **rabiscos de linhas horizontais**, mesmo sendo PNGs perfeitamente válidos. Eles não tinham nada a ver com o desenho.

A explicação é que **esses PNGs não são a camada em si**. O app usa o formato PNG como uma "caixa de compressão": ele pega só os pixels que foram pintados, junta todos em fila e embrulha a fila num PNG. Para saber onde cada pixel mora de verdade, é preciso a **lista de trechos** que fica antes do PNG.

### 4.2 A receita em 4 passos

Para cada camada o arquivo guarda:

1. **A caixa**: o menor retângulo que contém tudo o que foi pintado na camada (tamanho `largura x altura` e posição `x, y`).
2. **A lista de trechos**: números que alternam **"quantos pixels vazios"**, **"quantos pixels pintados"**, **"vazios"**, **"pintados"**... andando pela caixa linha por linha. A soma de todos os números dá exatamente `largura x altura` (isso serve de conferência).
3. **O PNG**: os pixels pintados, um atrás do outro, em ordem. Como não sobra um retângulo certinho, o fim vem com alguns **pixels de enchimento** transparentes.
4. **Um detalhe que enganou muito**: tanto a lista quanto a fila de pixels andam **de baixo pra cima** (a primeira linha é a de baixo). O PNG é gravado com as linhas **na ordem inversa**, ou seja, **de cabeça pra baixo**. E a posição `y` também conta **a partir de baixo** da tela.

### 4.3 Exemplo de brinquedo

Imagine uma caixa de 4 x 3 com este desenho (`X` = pintado, `.` = vazio):

```
linha de cima:   . X X .
linha do meio:   X X X X
linha de baixo:  . X X .
```

Andando **de baixo pra cima**, linha por linha, a sequência fica:

```
(baixo)  . X X .   X X X X   . X X .  (cima)
```

Contando os grupos: 1 vazio, 2 pintados, 1 vazio, 4 pintados, 1 vazio, 2 pintados, 1 vazio.
A **lista de trechos** é então `1, 2, 1, 4, 1, 2, 1` (soma = 12 = 4 x 3).

Os 8 pixels pintados, em ordem, são `a b | c d e f | g h`. Para guardá-los num PNG de 3 de largura, o app faz:

```
linha A:  a b c
linha B:  d e f
linha C:  g h (enchimento)
```

e grava o PNG com **as linhas na ordem C, B, A** (de cabeça pra baixo). Por isso, quem abre o PNG vê `g h _ / d e f / a b c`, que não parece nada com o desenho.

Para desfazer, o programa:

1. vira o PNG de cabeça pra baixo (volta para A, B, C);
2. lê os pixels em fila: `a b c d e f g h` (ignora o enchimento);
3. caminha pela lista `1, 2, 1, 4, 1, 2, 1`: pula 1 posição, coloca 2 pixels, pula 1, coloca 4, e assim por diante;
4. vira o resultado de novo, porque a caixa foi montada de baixo pra cima.

### 4.4 Exemplo real (o pontinho preto do arquivo de teste)

No arquivo de 100 x 100 com 4 camadas, o pontinho preto tem:

- caixa de **14 x 14** (196 posições), no ponto `x = 45, y = 48`;
- lista de trechos: `4, 5, 8, 10, 3, 110, 1, 12, 2, 12, 2, 11, 4, 9, 3, 0`, que soma **196** (exatamente 14 x 14);
- pixels pintados (os trechos de posição ímpar): 5 + 10 + 110 + 12 + 12 + 11 + 9 + 0 = **169**;
- PNG de **16 x 11 = 176** pixels, ou seja, **7 pixels de enchimento** (169 + 7 = 176).

Essa conta fechou em **todas as 4 camadas** do arquivo de teste e nas **152 camadas** do desenho grande. Foi essa conferência que me deu certeza de que a lista era mesmo o que eu achava.

### 4.5 A estrutura do bloco `RPNG`

Cada imagem de camada começa com o rótulo `RPNG` escrito no arquivo. Depois dele:

| Parte | Tamanho | Significado |
|---|---|---|
| `RPNG` | 4 bytes | rótulo |
| (?) | 4 + 4 + 1 bytes | não entendi (vi `45`, `0` e `4` ou `0`) |
| 9 números | 36 bytes | largura da área de origem, altura da área de origem, **largura da caixa**, **altura da caixa**, **x**, **y** (de baixo pra cima), largura do PNG, altura do PNG, pixels de enchimento |
| marcador | 4 bytes | `ff ff ff 00` ou `00 00 00 00` (não entendi a diferença) |
| tamanho da lista | 4 bytes | em bytes (2 bytes por número) |
| lista de trechos | N bytes | os números "pula / pinta" |
| tamanho do PNG | 4 bytes | quantos bytes tem o PNG |
| o PNG | variável | começa com `89 50 4e 47` ("PNG") |

---

## 5. Camadas atuais, estados antigos e recortes

O desenho grande que analisei tinha **152 blocos `RPNG`**, mas só **7 camadas** no desenho. O resto eu interpretei assim (**palpite**):

- **Camadas atuais**: o último grupo de blocos que têm o tamanho da tela inteira. Nos dois desenhos funcionou.
- **Estados antigos**: blocos do tamanho da tela inteira que aparecem antes, no meio do histórico.
- **Recortes**: blocos menores, que parecem ser o **histórico de desfazer** do app (pedaços de camada guardados antes de cada alteração).

Não achei a **tabela de camadas** (nome, ordem de empilhamento, opacidade, se está escondida). Por isso a regra "camadas atuais" é um palpite que funcionou, e **a ordem real de empilhamento ainda é desconhecida**.

### Animação

Na animação que analisei (480 x 640), os blocos são **os quadros**: 168 imagens, 109 diferentes. Antes de eu decifrar o formato, os quadros pareciam rabisco, como as camadas.

---

## 6. Os pontos da caneta (parcialmente entendido)

Na animação (app 13.1.19), cada ponto de um traço é um registro de **28 bytes**:

| Parte | Tamanho | Significado |
|---|---|---|
| `02 00 03 01 00 00 00 10` | 8 bytes | marcador |
| tempo | 8 bytes | momento do ponto (segundos desde 1970, com casas decimais) |
| x | 4 bytes | posição horizontal (número decimal) |
| y | 4 bytes | posição vertical |
| (?) | 4 bytes | não entendi |

Isso permitiu achar **253.390 pontos** nesse arquivo, de 29/01 a 18/02/2026. Dois problemas impedem de refazer a animação do desenho:

- os pontos incluem **gestos** (zoom e arrastar a tela), então desenhar todos dá uma bagunça;
- falta decifrar **cor, espessura, pincel e a que camada** cada traço pertence.

No app 14.1.2 o registro dos pontos é diferente, e eu não decifrei.

---

## 7. Como eu descobri (a história)

1. **O que é esse arquivo?** O comando `file` só diz "data". Mas listar os textos legíveis dentro dele mostrou `ibisPaint X`, a versão e o aparelho. Primeira pista: o dono do formato.
2. **Procurar PNGs escondidos.** Todo PNG começa com os mesmos 8 bytes (`89 50 4e 47 0d 0a 1a 0a`). Procurando por eles achei 181 PNGs no primeiro arquivo, e todos abriam. Antes de cada um havia 4 bytes com o **tamanho** dele.
3. **A primeira ideia errada.** Muitos PNGs pareciam rabisco. Achei que fosse uma imagem com a **largura errada** e testei centenas de larguras para ver se alguma alinhava as linhas. Nenhuma funcionou, porque a fila de pixels **não é uma imagem completa**.
4. **A pista que mudou tudo: um arquivo pequeno.** Você criou um desenho de 100 x 100 com 4 camadas simples (um ponto preto, um vermelho, um verde e um anel azul). Com pouca coisa dentro, dá pra **comparar byte a byte**. Isso é o método de toda engenharia reversa: mudar **uma coisa por vez** e ver o que mudou no arquivo.
5. **Os números antes do PNG.** Antes de cada PNG havia números que batiam com o que eu via: o pontinho preto aparecia como `16 x 11` (tamanho do PNG), `45, 48` (posição) e `14 x 14` (tamanho da caixa).
6. **A lista que soma certinho.** A lista `4, 5, 8, 10, 3, 110...` somava **196 = 14 x 14**. Não podia ser coincidência: era uma lista de "pula / pinta" sobre a caixa. Conferi nas outras 3 camadas e nas 152 do desenho grande: sempre a soma bateu.
7. **Achar a ordem dos pixels.** Mesmo sabendo **onde** pintar, os pixels saíam embaralhados. Peguei a imagem final do próprio arquivo (que já vem pronta) como **gabarito** e usei valores raros de transparência nas bordas do pontinho (29, 81, 94, 98...) como "impressões digitais", para achar onde cada pixel do PNG deveria ir. O padrão era saltos de **16** (a largura do PNG) em ordem inversa: o PNG estava de cabeça pra baixo.
8. **A prova.** Aplicando a receita, a composição das 4 camadas ficou **idêntica pixel a pixel** à imagem final guardada no arquivo (diferença zero).
9. **Os arquivos grandes.** Aplicando a mesma receita no desenho da personagem e na animação, os "rabiscos" viraram **camadas e quadros de verdade**: contorno, cores, a foto do rascunho, os quadros da animação.

**Lição:** o que mais ajudou foi um **arquivo de teste mínimo e controlado**, junto com **um gabarito para comparar** (a imagem final que o próprio arquivo guarda).

---

## 8. O que eu ainda não sei

- A **tabela de camadas**: nomes, ordem de empilhamento, opacidade, modo de mistura, camada escondida.
- Como os **traços** se ligam a cor, espessura, pincel e camada (necessário para refazer a animação do desenho).
- O formato dos pontos no app **14.1.2**.
- O significado dos bytes marcados com "(?)" nas tabelas acima.
- Se o byte de modo (animação/desenho) é mesmo isso em todas as versões do app.
- Se os "recortes" são mesmo o histórico de desfazer.

Se você quiser ajudar a descobrir mais, o melhor caminho é criar **arquivos de teste mínimos**, mudando uma coisa por vez: renomear uma camada, esconder uma camada, mudar a opacidade, mudar a ordem, e comparar com o arquivo anterior.

---

## 9. Código de exemplo

O código abaixo lê um `.ipv` e salva cada camada ou quadro como PNG. Testei em 3 arquivos: no de 4 camadas, a composição reproduz a imagem final do arquivo (diferença zero).

Instalação no CachyOS/Arch (shell fish):

```fish
sudo pacman -S python-pillow python-numpy
python3 ipv_layers.py meu_arquivo.ipv saida
```

Os arquivos saem com nomes como `000_atual.png`, `001_antigo.png` e `002_recorte.png`.

```python
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
```

---

## 10. Glossário

- **Byte**: um número de 0 a 255; é a unidade básica de um arquivo.
- **Hexadecimal**: jeito de escrever bytes com dois caracteres (`00` a `ff`).
- **Big-endian**: números de vários bytes escritos do maior para o menor, como lemos.
- **PNG**: formato de imagem comum, que aceita transparência.
- **Canal alfa**: a "transparência" de cada pixel (0 = invisível, 255 = totalmente visível).
- **Camada**: uma folha transparente do desenho; várias camadas empilhadas formam a imagem final.
- **Caixa (bounding box)**: o menor retângulo que contém tudo o que foi pintado.
- **Engenharia reversa**: descobrir como algo funciona olhando só o resultado.
- **Gabarito**: um resultado que já se sabe estar certo, para comparar com o seu.
