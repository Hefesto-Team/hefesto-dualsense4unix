# DICA-DA-COR-01 — o X do vizinho ganha pixel

**Branch:** `voo/DICA-DA-COR-01-opus` · nascida de `onda/1309` (`e1c7d96b`)
**Bancada:** não pedida, não usada — `bancada: false` desde a nota de 13/09 da
sprint. O X é desenho de tela e não desce ao aparelho.
**Rota:** a ROTA CORRIGIDA da sprint. A entrega de 10/09 (`65838cf4`) **não foi
costurada**: a metade da dica fechou pela TOOLTIP-C1 (`b2ac44ce`, a camada
`DICA_DA_CASA` de `hefesto_vivo.py`), e só o X foi refeito, sobre a página 04
de hoje (paleta de 11 tons, altura que segue a vista).

---

## O que mudou

**Um bloco de CSS, em `aba04.CSS`** — a regra `.guia .tom.tomado::after`:

```css
/* antes */  content:"";position:absolute;inset:5px;
/* depois */ content:"";position:absolute;
             left:50%;top:50%;transform:translate(-50%,-50%);
             width:min(12px,calc(100% - 2px));height:auto;aspect-ratio:1;
```

O gradiente das duas hastes e o contorno branco de `drop-shadow` (decisão dela
de 09/09, a `COR-X-01`) ficaram como estavam. O comentário datado acima da
regra diz a medida, o teto, e por que a altura vem de `aspect-ratio` e não de
um segundo `min()` (medido na entrega de 10/09: `8,94 x 12` com `min()` nos
dois eixos).

**A página:** `python src/hefesto_dualsense4unix/interface/aba04.py` →
`mockup/04-iluminacao.html` → `scripts/check_o_desenho_aprovado.py --publicar 04`
→ `src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html`. As duas
páginas mudam só no bloco de CSS (20 linhas, as mesmas do gerador).

**A régua nova:** `tests/unit/test_o_x_do_vizinho_e_quadrado.py` — 11 casos.
Abre a 04 PUBLICADA num `WebKit2.WebView` offscreen, instala o `BOOTSTRAP` do
piloto, pinta a carga que `a04_iluminacao` emite para dois controles dublês
(traduzida por `pacotes.normalizar`, o mesmo despachante do `Piloto._tique`) e
lê do motor a geometria do `::after` de cada tom tomado, nas duas vistas
importadas: `ponte_da_tela.TAMANHO_OCULTA` (a janela ao abrir) e
`olhar.VISTA_DELA` (a TV dela maximizada). Cobra: um X por coluna ligada,
quadrado, com os dois lados ≥ 8 px, dentro do teto de 12 px e da pílula, e
centrado nos dois eixos.

**O que NÃO mudou:** o pacote da 04, o `topo.html`, as outras nove páginas. O
tom com X continua sem `data-gesto`, com `aria-disabled="true"` e com o `title`
nomeando o dono.

### A medida, antes e depois

`WebKit2.WebView` offscreen, página publicada, dois controles pintados pelo
pacote (`p1` e `p2`, cada um com o X na cor do outro):

| vista | pílula | X antes | X depois |
| --- | --- | --- | --- |
| 1212x809 — a janela como abre | 16,5 x 26 | **4,5 x 14** | **12 x 12**, centro 7,25 / 12 |
| 1600x809 | 25,3 x 26 | 13,3 x 14 | 12 x 12 |
| 1918x840 — a vista dela | 26,1 x 26 | 14,0 x 14 | 12 x 12 |

### A foto e o clique

**A foto** — as quatro ampliações (8x, vizinho mais próximo) estão ao lado
desta entrega:

* `DICA-DA-COR-01-ANTES-o-x-na-janela-1212x809.png` — um «I»: a tira vertical
  de 4,5 px, com o contorno branco nas pontas;
* `DICA-DA-COR-01-DEPOIS-o-x-na-janela-1212x809.png` — o X, centrado;
* `DICA-DA-COR-01-ANTES-o-x-na-vista-dela-1918x840.png` e o `DEPOIS` — de 14 x 14
  com as hastes tocando o recuo para 12 x 12.

**O clique** — nas três vistas, antes e depois, o primeiro `.guia .tom.tomado`
foi clicado por `el.click()` e relido 1,5 s depois: `data-gesto` nulo,
`aria-disabled="true"`, sem `data-hef-voo`, zero `.hef-recado`. A cura mexeu só
no desenho do X; o tom com X continua não sendo gesto.

**O piloto do produto:** `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1
hefesto_vivo.py --oculta --abre 04 --segundos 6 --foto …`, com a cura publicada
e o daemon dela no ar: a 04 abriu, pintou e fechou `rc=0`. Havia **um** controle
ligado (P1, pelo rádio), então a foto não tem X — o X precisa de dois. Os
perfis dela foram copiados antes para o rascunho e o md5 dos 159 arquivos saiu
idêntico depois.

## Qual mordida prova

**Arranquei a cura** — devolvi `content:"";position:absolute;inset:5px;` ao
`::after` em `aba04.CSS`, regerei a 04 e `--publicar 04`:

```
E       AssertionError: o X não é quadrado na vista janela:
E         p1: X 4.50 x 14.00 px numa pílula 16.50 x 26.00
E         p2: X 4.50 x 14.00 px numa pílula 16.50 x 26.00
E       AssertionError: o X tem menos de 8 px num dos lados na vista janela:
E         p1: X 4.50 x 14.00 px numa pílula 16.50 x 26.00
E       AssertionError: o X passa do teto de 12 px ou vaza da pílula na vista dela:
E         p1: X 14.05 x 14.00 px numa pílula 26.05 x 26.00 · canto 5.00,5.00 · caixa 24.05 x 24.00
E       AssertionError: o X passa do teto de 12 px ou vaza da pílula na vista janela:
E         p1: X 4.50 x 14.00 px numa pílula 16.50 x 26.00 · canto 5.00,5.00 · caixa 14.50 x 24.00
FAILED tests/unit/test_o_x_do_vizinho_e_quadrado.py::test_o_x_e_quadrado[janela]
FAILED tests/unit/test_o_x_do_vizinho_e_quadrado.py::test_o_x_tem_corpo[janela]
FAILED tests/unit/test_o_x_do_vizinho_e_quadrado.py::test_o_x_cabe_no_teto_e_na_pilula[dela]
FAILED tests/unit/test_o_x_do_vizinho_e_quadrado.py::test_o_x_cabe_no_teto_e_na_pilula[janela]
4 failed, 7 passed in 3.74s
```

**O que a mordida ensinou:** na vista dela o X recuado sai `14,05 x 14` — quase
quadrado, dentro da folga de 0,5 px. Sem o teto, a TV dela passaria verde sobre
a mesma folha que faz a tira na janela ao abrir. A docstring da régua diz isso.

**Devolvi a cura**, regerei e republiquei, e conferi contra os md5 guardados
antes de morder: `aba04.py`, `mockup/04` e `paginas/04` — `SUCESSO` nos três.

```
tests/unit/test_o_x_do_vizinho_e_quadrado.py   11 passed in 3.10s
tests/unit/test_fecha_iluminacao_01_duas_pecas_nunca_tem_a_mesma_cor.py
  + test_a_recusa_pisca_no_botao.py::test_a_casa_tomada_diz_de_quem_e_sem_a_regra
                                                36 passed in 5.28s
```

## O que NÃO verifiquei

* **O X no compositor dela, com o olho dela** (PROVA-DE-TELA-01). As fotos são
  de uma `Gtk.OffscreenWindow` num Xvfb; a TV é 4K sob COSMIC + XWayland.
* **O X com três ou quatro controles** — a régua pinta dois dublês. Com o daemon
  dela havia um só, e a foto do piloto não tem X nenhum.
* **O pisca da janelinha nativa**, que era a outra metade da sprint: fechou pela
  TOOLTIP-C1 e não foi remedido aqui.
* **O Chrome headless** (`olhar.py`): não rodei, e as fotos de
  `docs/usage/assets/` não foram refeitas — quem fotografa é quem coordena,
  depois da costura. Os números da triagem eram de Chrome (4,17 x 14 a
  1212x809); no WebKit são 4,5 x 14.
* **A vista de 1600 px** foi medida pelo rascunho, e não está na régua.
* **Portões:** `bash scripts/portoes.sh` completo, depois do `git add -A`:
  **TODOS VERDES — 60 portões.** A primeira volta reprovou dois, e os dois eram
  desta entrega: `acentuacao` (uma chave `conteudo` na régua, que virou
  `content`) e `nada-aponta-para-a-janela` (a importação nova de
  `gui.ponte_da_tela`, agora declarada — ver a seção de baixo). Na volta do
  inventário o portão de acento ainda leu o verbo «media» como «média», e a
  frase mudou. Esta linha foi escrita depois da corrida verde; `acentuacao` e
  `saida-de-agente` rodaram de novo sobre ela antes do commit.
* **A suíte inteira** não rodou — é de quem coordena. Rodaram a régua nova e as
  duas vizinhas que leem o X (36 casos).

## O que sobrou para o próximo

* **A prova de tela é dela:** abrir a 04 com dois controles ou mais e olhar o X
  na TV. É a única coisa que a régua não alcança.
* **Na costura, regerar a 04** sobre o que as outras sprints deixarem na página:
  esta entrega só mexe no CSS de `aba04.py`, e o HTML se resolve regerando.
* **`docs/data/o-que-ainda-aponta-para-a-janela.csv` ganhou uma linha**, fora
  da posse desta sprint: a régua importa `gui.ponte_da_tela.TAMANHO_OCULTA`, e o
  portão `nada-aponta-para-a-janela` manda declarar toda importação nova. A
  linha é `MOTOR-MUDA-DE-CASA`, a mesma de `test_o_aviso_da_vibracao_cabe_na_aba`
  e de `test_a_janela_estica_com_teto`, que leem o mesmo dono. Se outra sprint
  mexer no inventário, o conflito é de uma linha.
* **O `cria:` da sprint ainda declara `scripts/ensaios/a_dica_da_cor_nao_e_do_gtk.py`**,
  que não nasceu — a nota de 13/09 do frontmatter já diz por quê. Deixei como
  estava.
* **Os números das §2 e §3 do corpo da sprint são de 09/09**, antes da paleta de
  11 tons: *"0px × 14 px a 1222"*, *"5,23 px a 1600"* e *"8,9 × 8,9 na janela ao
  abrir"* depois da cura. Hoje são 4,5 x 14 antes e 12 x 12 depois, nas duas
  vistas. Ficaram no corpo como medida datada; a ROTA CORRIGIDA e a linha de
  ESTADO dizem o número de hoje.

## O que a validação refez e corrigiu

Refeito por outro agente, na mesma árvore e na mesma branch, sem confiar no
relato acima.

**A posse.** `git diff --name-only e1c7d96b..HEAD` cabe no `posse`/`cria` da
sprint, nas duas páginas 04 geradas, na sprint e nesta entrega (o texto e as
quatro ampliações). Sobra um arquivo, `docs/data/o-que-ainda-aponta-para-a-janela.csv`,
e a razão foi medida: com a linha da régua arrancada, o
`scripts/check_nada_aponta_para_a_janela.py` sai `rc=1` com
*"tests/unit/test_o_x_do_vizinho_e_quadrado.py:55: CITAÇÃO NOVA para a janela
(gui.ponte_da_tela)"*. Com a linha devolvida (md5 idêntico), sai `rc=0`.
`TAMANHO_OCULTA` só tem dono em `gui/ponte_da_tela.py`.

**Nenhum botão novo.** Nas duas páginas 04, a de `e1c7d96b` e a da branch têm
os mesmos 66 `data-gesto`, 60 `<button` e 81 `title`. No DOM pintado com dois
controles são 63 `data-gesto` e 60 botões, antes e depois. O que muda nas
páginas é a regra do `::after` e comentário de CSS, que não chega à tela.

**As mordidas, refeitas uma a uma.** Em cada uma: trecho trocado em
`aba04.CSS`, 04 regerada e `--publicar 04`, régua rodada, trecho devolvido,
04 regerada e publicada de novo. `md5sum -c` deu SUCESSO nos três arquivos,
`git diff` saiu vazio e a régua voltou a 11 passed.

| arranquei | a régua |
| --- | --- |
| a cura inteira, com `inset:5px` de volta | **4 failed**: quadrado e corpo na janela (4,50 x 14), teto nas duas vistas (14,05 x 14 na dela). É o número do relato |
| só o `aspect-ratio:1` | **4 failed**: X de 12,00 x **0,00** px, quadrado e corpo nas duas vistas |
| só o `transform:translate(-50%,-50%)` | **3 failed**: centro nas duas vistas (13,25 / 18 contra 7,25 / 12 na janela), e vaza da pílula na janela |
| só o teto (`width:calc(100% - 2px)`) | **1 failed**: teto na vista dela, 22,05 x 22,05. Na janela a pílula já limita o X a 12,5 px, dentro da folga |

**A tela.** As fotos foram tiradas num `WebKit2.WebView` offscreen sob `xvfb-run`,
com a página de `e1c7d96b` (lida por `git show`) e a da branch, o `BOOTSTRAP`
e a `DICA_DA_CASA` do piloto instalados e a carga do pacote da 04 para dois
controles sintéticos:

| vista | X antes | X depois |
| --- | --- | --- |
| 1212x809 | 4,5 x 14, canto 5 / 5 | 12 x 12, canto 1,25 / 6 (centro 7,25 / 12 = centro da pílula) |
| 1918x840 | 14,05 x 14, canto 5 / 5 | 12 x 12, canto 6,02 / 6 |

As ampliações a 8x mostram o «I» antes e o X depois, iguais às desta entrega.
**No clique no tom tomado**, antes e depois: `data-gesto` nulo,
`aria-disabled="true"`, zero `.hef-recado` e zero `.hef-recusou` 1,5 s depois.
**Com o ponteiro parado sobre ele** (`mousemove`), a dica da casa abre com
«P2 (DualSense)» nas duas versões e na mesma caixa (107,8 x 37 em 290 / 380, na
janela). O X novo não mexe na dica. **O piloto**
(`HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1 hefesto_vivo.py --oculta --abre 04
--segundos 6`) saiu com `rc=0` e zero `Traceback`. Os 159 arquivos de perfil
tinham o mesmo md5 da cópia antes e depois da corrida. Havia um controle ligado,
então não aparece X.

**As réguas vizinhas**, em lotes pontuais: 17 arquivos que leem a 04 (295
passed, 2 skipped). Depois da correção abaixo, mais 24 (590 passed, 4 xfailed),
incluindo as três que citam o portão `nada-aponta-para-a-janela`, a
`test_a_recusa_pisca_no_botao.py` e a própria régua.
`scripts/validar-citacoes-de-linha.py --all`: 3291 citações, OK.

### O que corrigi — `ee6b4951`

Três comentários de CSS em `aba04.py`, todos na posse. A 04 foi regerada e
publicada, e só comentário muda:

1. **A nota do `.luz-grade .ctrl.off`** dizia que
   `hefesto_vivo._recusou_dizendo` «só leva `RuntimeError` à tela». Isso vale
   no presente para um canal que a onda 1 tirou: hoje as duas exceções vão ao
   diário e o botão pisca (a docstring de `_recusou_dizendo`). O verbo foi para
   o passado, e uma frase diz o canal de hoje.
2. **A nota do `.players button.fora`** dizia «quem insistir ouve a recusa em
   vez de nada». Agora diz que o botão pisca a recusa e que a frase vai ao
   diário. As duas notas estavam declaradas pendentes «na posse da
   DICA-DA-COR-01» na entrega da FRASES-E-DICAS-01
   (`docs/process/agentes/2026-09-13/FRASES-E-DICAS-01-opus.md`, o item «Prosa
   fora da posse que ainda descreve o canal que saiu»), e a implementação não
   as tocou. Os números de linha que aquela entrega cita para elas andaram 18
   com o comentário do X. Aqui elas são nomeadas pela regra.
3. **A nota do X** atribuía o `8,94 x 12` de `min()` nos dois eixos a caixas de
   «26 de altura, 14 de largura», que são as da pílula de hoje. Só que com a
   pílula de hoje (14,5 px por dentro) os dois `min()` dariam 12. O número foi
   medido na pílula de 10,94 px de 10/09, a 1222 px, e é o que diz a mensagem
   de `65838cf4`. A nota agora diz isso.

### O que a validação também não verificou

* A janela mais estreita que 1212 px, em que o `aspect-ratio` passaria a
  decidir: a régua mede as duas vistas importadas, e nenhuma delas deixa a
  pílula abaixo do teto.
* A dica da casa com três ou quatro controles e o olho dela na TV
  (PROVA-DE-TELA-01).
