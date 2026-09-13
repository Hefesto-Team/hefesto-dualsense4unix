---
sprint: A-MARCA-DA-DEGRADACAO-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  A-MARCA-DA-DEGRADACAO-01:
    - src/hefesto_dualsense4unix/interface/aba01.py
    - src/hefesto_dualsense4unix/interface/aba02.py
    - src/hefesto_dualsense4unix/interface/aba03.py
    - src/hefesto_dualsense4unix/interface/aba04.py
    - src/hefesto_dualsense4unix/interface/aba05.py
    - src/hefesto_dualsense4unix/interface/aba06.py
    - src/hefesto_dualsense4unix/interface/aba07.py
    - src/hefesto_dualsense4unix/interface/aba08.py
    - src/hefesto_dualsense4unix/interface/aba09.py
    - src/hefesto_dualsense4unix/interface/aba10.py
    - src/hefesto_dualsense4unix/interface/pacotes/__init__.py
    - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
    - src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py
    - docs/process/sprints/2026-09-13-A-MARCA-DA-DEGRADACAO-01-o-asterisco-que-nunca-acende-e-o-gerador-que-escreve-antes-de-conferir.md
cria: []
bancada: false
depois_de: [MODO-DE-CONEXAO-01]
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/interface/topo.html
  - src/hefesto_dualsense4unix/app/widgets/controller_card.py
  - src/hefesto_dualsense4unix/daemon/
  - docs/data/
---

# A-MARCA-DA-DEGRADACAO-01 — o asterisco que nunca acende, e o gerador que escreve antes de conferir

Achados da validação da RESTOS-DA-ONDA-DOIS-01, na onda 3 da
[terceira lista](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md). Entra **depois da
[MODO-DE-CONEXAO-01](2026-09-13-MODO-DE-CONEXAO-01-o-degrau-xbox-que-diz-aplicado-e-nao-vale-e-o-texto-que-e-da-mascara.md)**:
as duas mexem na aba 01, e aquela muda o que «degradado» quer dizer (o canal
comum passa a ser um caminho escolhido, não uma queda).

## §E — O que se sabe

1. **A marca.** O cartão da 01 (`degradou-cartao`) e a máscara da 02
   (`mascara-degradou`) têm um `<sup class="degradou">*</sup>`. A pintura escreve
   no atributo `title` a frase de `pacotes.degradacao_de`, que é *«Emulação
   degradada (uinput): …»*. O CSS só mostra o `*` em `.degradou[title]`, e a
   camada de dicas leva o `title` para `data-hef-dica`: no WebKit o seletor nunca
   casa, e **o asterisco nunca acende**. Quando acendia, era uma frase de aviso
   numa dica, que a terceira lista dela manda tirar da tela (§1 do índice).
2. **A mesma forma já foi curada uma vez**, na guarda do alto-falante
   (RESTOS-DA-ONDA-DOIS-01, `data-apagado` em vez de `[title]`). Pode haver outros
   seletores `[title]` mortos nos geradores.
3. **O gerador que escreve antes de conferir.** Medido na validação da
   RESTOS-DA-ONDA-DOIS-01: com a autoconferência do `aba06.py` reprovando (rc=1), o
   `mockup/06` já estava escrito, e o `--publicar` seguinte publicou a página
   recusada. A autoconferência lê a página DEPOIS de escrevê-la
   (`_conferir(onde.pagina(...).read_text())`).

## §D — O que está decidido

1. **A marca sai inteira** (tirar pode): o `<sup>` nas duas abas, as regras de CSS
   dela, os dois campos dos pacotes e as réguas que a exigem; `degradacao_de` sai
   de `pacotes/__init__.py` se ninguém mais a ler. A queda para o canal comum sem
   ter sido escolhida fica no diário do daemon e no mapa — *«o layout não informa
   os nossos defeitos»*, palavra dela de 07/09 citada em `a01_jogar.py`.
2. **Todo seletor CSS `[title]` dos dez geradores** é conferido: o que decide
   pintura some (se for marca de aviso) ou passa a ler o endereço que existe no
   WebKit; o que está em `topo.html` (nao_toca) vai para a entrega.
3. **Gerador confere antes de escrever:** a autoconferência roda sobre o texto
   (ou sobre um arquivo provisório renomeado só se passar), e página recusada não
   chega ao `mockup/`. A cura cobre todos os geradores com a mesma forma, não só o
   da 06.

## §I — A implementação

1. Achar os leitores de `degradou-cartao`, `mascara-degradou` e `degradacao_de`
   (pacotes, geradores, réguas) e tirar a marca dos dois lados.
2. Listar os seletores `[title]` dos dez geradores e curar pelo §D.2.
3. Nos geradores com a forma do §E.3, trocar a ordem para conferir e só então
   escrever.
4. Regerar e publicar as abas tocadas na árvore da sprint; quem coordena regera as
   dez na costura.

## §V — A prova

* A 01 e a 02 publicadas sem `class="degradou"` e sem regra `.degradou`; a
  contagem de `data-gesto` e de botões igual antes e depois. **Mordida:**
  devolver o `<sup>` ao gerador reprova a régua.
* Um gerador sabotado para reprovar a autoconferência deixa o `mockup/` com o
  mesmo md5 de antes. **Mordida:** devolver a escrita antes da conferência
  reprova.
* Foto `--oculta` da 01 e da 02 antes e depois.
* Os portões até todos verdes.

## §0 — O processo

Os achados vieram medidos pela validação da onda 3 → IMPLEMENTA → VALIDA/CORRIGE,
despachada depois da costura da MODO-DE-CONEXAO-01.
