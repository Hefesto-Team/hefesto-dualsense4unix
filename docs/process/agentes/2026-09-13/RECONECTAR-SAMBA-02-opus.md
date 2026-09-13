# RECONECTAR-SAMBA-02 — entrega do agente IMPLEMENTA (opus)

Sprint: [RECONECTAR-SAMBA-02](../../sprints/2026-09-13-RECONECTAR-SAMBA-02-o-botao-que-ainda-muda-de-lugar-na-janela-dela.md).
Árvore `voo/RECONECTAR-SAMBA-02-opus`, nascida de `onda/1309` = `e1c7d96b`, com a
FRASES-E-DICAS-01 e a VAO-DO-ESQUELETO-01 dentro. Nenhum aparelho, nenhum gesto
contra o daemon dela: o serviço e a ponte foram dublês dentro do processo.

## O que mudou

**1. O chip do lugar vazio guarda o vão** — `aba01.py`, a regra S-04 esticada ao
chip: `display:none` → `visibility:hidden`. O comentário que afirmava *"a altura da
fileira não cai"* saiu, e no lugar dele está o número medido (fato errado
substituído). Nenhuma altura cravada: o chip continua medindo a fileira.

**2. A frase da mesa pousa por cima da fileira** — `aba01.py`, `.mesa-notas`: fora
do fluxo (`position:absolute` no meio da fileira, com o `div` que abraça a `.pecas`
virando `position:relative` por `:has(> .pecas)`), fundo do quadro para a borda dos
cartões não cortar a frase, e `pointer-events:none`. Apagada continua
`display:none`: a cena aprovada não muda. É a D-07, escolha dela em 04/09 —
*"Uma frase por cima dos lugares apagados."*
([AS DEZESSEIS DECISÕES, §D-07](../../2026-09-04-AS-DEZESSEIS-DECISOES-DELA-e-as-sprints-que-nascem.md)).
Regerado (`aba01.py`) e publicado (`check_o_desenho_aprovado.py --publicar 01`):
`mockup/01-jogar.html` e `interface/paginas/01-jogar.html`.

**3. O tique mudo repinta o último estado bom por uma folga medida** —
`hefesto_vivo.py`: `MUDOS_SEGUIDOS_QUE_VOLTARAM = 3`, `_o_servico_so_demorou` e a
classe `FolgaDoServicoMudo`, dona única do estado. No `_tique`, o `except` do
`estado_do_daemon()` deixou de pintar `{}` direto: `st = self._folga.mudo(e)`, e o
`else` guarda a resposta boa. O `[daemon mudo]` do diário fica.

* Só a DEMORA ganha folga: `DaemonMudo` com `TimeoutError` na causa (é a forma de
  `mesa_viva.estado_do_daemon`, que embrulha todo `OSError`), ou `TimeoutError`
  direto. Socket inexistente, conexão recusada ou fechada pintam `{}` na hora.
* Passada a folga, a verdade se pinta e o estado guardado é descartado: um mudo a
  mais não ressuscita o estado velho; só uma resposta nova.
* **O N saiu do diário dela** (`~/.local/state/hefesto-dualsense4unix/interface.log`,
  lido sem escrever, 28 janelas de 07 a 13/09): 17 tiques `timed out` em 15
  corridas; das 14 seguidas de um tique que respondeu, 13 tiveram UM tique e uma
  teve TRÊS (janela de 12/09 16:32, aba Controles). As 11 seguidas de 07/09 são
  `[Errno 2]`/`[Errno 104]` — serviço reiniciando, não demora.

**4. As réguas.** `tests/unit/test_o_reconectar_nao_muda_de_lugar.py` ganhou 12
casos: as duas cenas do estado no Chrome (1228 e 1300), o clique no centro do chip
escondido, a frase por cima que não rouba o clique dos cartões, três da
`FolgaDoServicoMudo` sozinha (mais os três tipos de serviço fora do ar) e três no
piloto de verdade (WebKit oculto, dublê de `TimeoutError`): dentro da folga os
lugares seguem cheios, depois dela a tela diz, e o y do botão não anda.

**5. Fora da posse, declarado:** `tests/unit/test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio.py`
(portão `gesto-em-lugar-vazio`). `test_o_lugar_vazio_nem_desenha_o_gesto` cobrava a
caixa ZERADA do chip, que é o que o `display:none` dava e o que o §D desta sprint
troca. Passou a cobrar *desenhado* = caixa **e** `visibility` visível; a pergunta
(o lugar vazio mostra a escolha?) é a mesma, e o texto da mordida (i) diz a regra
nova. Nenhuma régua exigia o literal.

**6. Fora da posse, declarado:** `interface/pacotes/a06_navegacao.py`, uma linha de
comentário. As linhas novas do `hefesto_vivo.py` deslocaram a citação
`hefesto_vivo.py:4241` para uma linha em branco, e o
`test_portao_o_par_com_metade_ligada.py` reprovou (*"cita a linha 4241, que está EM
BRANCO"*). Na base ela já apontava para um `return False` de `_proximo_da_fila`, e
não para o rótulo que cita; foi reapontada pelo SÍMBOLO,
`hefesto_vivo.Piloto._depois_do_gesto`, que é quem imprime *"DISSE APLICADO E NADA
MUDOU"*.

### As medidas, antes e depois

Piloto oculto, WebKitGTK, vista de 1212x809, página publicada desta árvore. Amostra
do retângulo do botão a cada 100 ms: 50 em repouso, 30 com o serviço mudo, 20 com a
lista vazia.

| estado | antes (`e1c7d96b`) | depois |
| --- | --- | --- |
| repouso, 2 controles | y 463 · cartão 128 | y 463 · cartão 128 |
| mudo, tiques 1 a 3 | **y 402** · os quatro lugares apagados | y 463 · P1 e P2 cheios (a folga) |
| mudo, do 4º em diante | **y 402** · cartão 67 | y 462 · cartão 127 · os quatro apagados |
| lista vazia, frase acesa | **y 429** · frase acima dos cartões | y 462 · frase por cima da fileira |
| x, em todo estado | 1017,7 | 1017,7 |

Chrome headless, página publicada, com a folha do piloto por cima:

| cena | 1228 antes → depois | 1300 antes → depois |
| --- | --- | --- |
| como nasce | y 464 | y 464 |
| os quatro lugares apagados | **403** → 463 | **403** → 463 |
| lista vazia, frase acesa | **430** → 463 | **430** → 463 |

**O resíduo de 1 px** (cartão 129 → 128 no Chrome, 128 → 127 no WebKit) fica dentro
da tolerância declarada de ±2 (`TOLERANCIA_DO_ESTADO`). Não achei o pixel.

### A foto, o clique

Fotos no rascunho do agente (`RECONECTAR-SAMBA-02/` do scratchpad da sessão), não no
repositório:

* **repouso, antes e depois** — Chrome: `chrome-base-*-repouso.png` e
  `chrome-depois-*-repouso.png` são **byte a byte idênticas** nas duas larguras.
  WebKit: `webkit-antes-repouso.png` × `webkit-depois-repouso.png` diferem em 37
  pixels, todos de 1 a 18 níveis de cor — 13 nos quatro cantos arredondados da
  janela (y 17–21) e o resto no serrilhado de bordas de chip e do desenho do P1. A
  foto de volta ao repouso, no fim da mesma corrida, difere nos mesmos 13 dos
  cantos. Nenhum é de lugar.
* **serviço mudo** — `webkit-antes-mudo.png` (quatro «Desconectado», botão alto) e
  `webkit-depois-mudo-na-folga.png` (P1 e P2 cheios) / `webkit-depois-mudo.png`
  (quatro apagados, botão no lugar).
* **lista vazia** — `webkit-antes-vazia.png` (frase acima, cartões empurrados) e
  `webkit-depois-vazia.png` (frase centrada sobre os quatro lugares).

**O clique:** a sonda clicou o «Reconectar controles» no repouso (ponte dublê para
`coop.sync` e `identity.renumber`): desfecho `aplicou`, e o y não se moveu durante
o voo nem depois. No centro do chip do lugar vazio, o `elementFromPoint` devolve
`DIV.mascara` no WebKit (P1 e P3, no mudo e na lista vazia) e no Chrome (os doze
chips); antes da cura devolvia `BODY`, porque o chip não tinha caixa. No meio da
frase acesa sobre quatro cartões cheios, o ponto é do cartão.

**Perfis:** `~/.config/hefesto-dualsense4unix/profiles/` copiados antes (159
arquivos) e conferidos por md5 depois das duas corridas do piloto: idênticos.

## Qual mordida prova

Cada cura arrancada sozinha, a régua rodada, a cura devolvida e conferida.

**(a) A folga** — `st = self._folga.mudo(e)` → `st = {}` no `_tique`:

```
E       AssertionError: o serviço demorou 1 tique(s) e os lugares já apagaram — a folga de 3 não segurou: [{'y': 462, 'p1': 'nao', 'frase': False, 'fase': 'mudo', 'mudos': 1}, ...]
FAILED tests/unit/test_o_reconectar_nao_muda_de_lugar.py::test_no_webkit_o_tique_mudo_repinta_o_ultimo_estado_bom
1 failed, 6 passed, 17 deselected in 4.80s
```

Devolvida: `git diff | cmp - diff-da-cura` → idêntico.

**(b) O vão do chip** — a regra S-04 de volta a `display:none`, regerada e
publicada:

```
E           AssertionError: 1228px · o serviço não respondeu: os quatro lugares apagam: o botão subiu 61 px — y 464.0 → 403.0, x 1018.7 → 1018.7
E           AssertionError: 1300px · o serviço não respondeu: os quatro lugares apagam: o botão subiu 61 px — y 464.0 → 403.0, x 1090.7 → 1090.7
E       AssertionError: o chip do lugar vazio saiu do fluxo de novo — a fileira volta a cair e o botão sobe: p1 · DualSense, p1 · Xbox 360, …
E           AssertionError: no WebKit, com os lugares apagados, o botão subiu 61 px — y 463.0 → 402.0
4 failed, 2 passed, 25 deselected in 14.25s
```

Devolvida, regerada e publicada: `aba01.py`, `mockup/01-jogar.html` e
`paginas/01-jogar.html` com `cmp` idêntico às cópias curadas.

**(c) O «por cima»** — `.mesa-notas` de volta ao fluxo (`margin:0 0 6px`), regerada
e publicada:

```
E           AssertionError: 1228px · a lista vem vazia: os lugares apagam e a frase da mesa acende: o botão desceu 26 px — y 464.0 → 490.0, x 1018.7 → 1018.7
E           AssertionError: 1300px · a lista vem vazia: os lugares apagam e a frase da mesa acende: o botão desceu 26 px — y 464.0 → 490.0, x 1090.7 → 1090.7
E       AssertionError: a frase por cima dos cartões recebe o clique (DIV.mesa-notas ha) — o cartão embaixo dela deixou de ser clicável
E           AssertionError: no WebKit, com a lista vazia e a frase acesa, o botão desceu 26 px — y 463.0 → 489.0
4 failed, 2 passed, 18 deselected in 16.33s
```

O terceiro reprova aqui porque a linha no fluxo recebe o próprio clique; ele morde
de verdade o `pointer-events:none`, que saiu junto nesta mordida. Devolvida,
regerada e publicada: `cmp` idêntico às cópias curadas.

**Com as três curas no lugar:** `tests/unit/test_o_reconectar_nao_muda_de_lugar.py`
— 24 passed; `test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio.py` e
`test_a01_a_mesa_vazia_fala.py` — 14 passed.

E `test_portao_o_par_com_metade_ligada.py` — 16 passed, depois do reaponte do item 6.

**Portões:** `bash scripts/portoes.sh` completo, depois do `git add -A`, com esta
entrega e a sprint já escritas — todos verdes.

## O que NÃO verifiquei

* **O aparelho.** Nenhum controle, nenhum gesto contra o daemon dela: se o
  Reconectar faz o daemon passar dos 2 s na máquina dela, quatro controles no cabo
  e no rádio, e o ladrilho do COSMIC ficam como o §R da sprint os deixou.
* **O olho dela sobre a frase por cima.** O desenho é novo: a frase centrada sobre a
  fileira, com o fundo do quadro. É a D-07 dela em palavra; em pixel, só ela aprova.
* **A folga fora da aba Jogar.** O `_tique` é das dez abas, e a folga vale em todas;
  medi só na 01. Nas outras nove, um tique mudo também repinta o último estado bom
  até três vezes.
* **Quanto tempo a folga dura na máquina dela.** Com o socket real, cada tique mudo
  segura o laço do GTK até 2 s e o seguinte é pulado: três tiques mudos são uns 6 s
  de estado velho antes da verdade. A sonda levantou o erro na hora.
* **O quinto controle no WebKit.** A frase por cima de quatro cartões cheios foi
  medida só no Chrome (o clique cai no cartão).
* **As duas linhas acesas juntas.** A ressalva da máscara e a frase da mesa dividem o
  mesmo lugar; hoje a ressalva sai vazia em todo modo, então não se sobrepõem. Se
  alguém a religar, as duas se cobrem.
* **O resíduo de 1 px**, e a fonte do Google sem rede.
* **A suíte inteira** (não é minha).

## O que sobrou para o próximo

* **O laço do GTK preso no tique mudo** (até 2 s por tique, `hefesto_vivo.py`,
  `Piloto._tique`): a folga esconde o pulo, não o engasgo. É a outra metade do
  samba, e o dono é quem tirar o IPC síncrono do tique.
* **O ladrilho do COSMIC que ignora o mínimo**, e os três fatos errados que o estudo
  achou fora desta posse: a ALTURA-DA-VISTA-01 §2.2, o comentário do
  `set_size_request` em `gui/ponte_da_tela.py` e o de `.janela` em
  `interface/topo.html` («quem segura o piso é o `set_size_request`»).
* **O topo com o serviço mudo afirma o perfil do disco.** Na foto
  `webkit-antes-mudo.png` (e na `webkit-depois-mudo.png`, depois da folga), com o
  estado `{}` o cabeçalho diz como «Perfil ativo» o perfil gravado no disco dela (o
  de um jogo), enquanto o dublê dizia `sonda`. Não medi se é desenho ou defeito;
  a folga só adia esse momento três tiques.
* **Citações velhas no próprio `aba01.py`**: o comentário da S-04 cita
  `hefesto_vivo.py:1362` e `:1380` para os passos `1b` e `1c`, que moram hoje no
  `BOOTSTRAP` perto da linha 1250 (`dataset.conectado`). Não reapontei: nenhuma
  régua as lê e esta sprint não as deslocou.
* **Quem costurar** regera a 01: esta sprint mexe no CSS de `aba01.py`, e a página
  gerada muda em outras sprints da leva.
* **Colisão possível com a F1-REMAPEAR-02**, dona de `a06_navegacao.py` nesta mesma
  onda: esta sprint mudou ali UMA linha de comentário (o reaponte da citação, item 6
  de «O que mudou»). Se a costura conflitar, fica o texto da F1 com a citação pelo
  símbolo, e o `test_portao_o_par_com_metade_ligada.py` diz se sobrou endereço
  deslocado.
