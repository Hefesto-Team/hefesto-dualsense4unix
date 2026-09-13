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

**2. A frase da mesa pousa por cima dos lugares apagados** — `aba01.py`,
`.mesa-notas`: fora do fluxo (`position:absolute` no meio da fileira, com o `div` que
abraça a `.pecas` virando `position:relative` por `:has(> .pecas)`), e com o fundo do
quadro para a borda dos cartões não cortar a frase. Só quando nenhum lugar está
cheio: com mais controles que lugares ela fica acima da fileira, como na base
(correção da validação, no fim). Apagada continua `display:none`: a cena aprovada
não muda. É a D-07, escolha dela em 04/09 —
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

**4. As réguas.** `tests/unit/test_o_reconectar_nao_muda_de_lugar.py` ganhou 13
casos: as duas cenas do estado no Chrome (1228 e 1300), o clique no centro do chip
escondido, a frase do quinto controle que não cobre cartão cheio (nas duas larguras, desde a
validação), três da
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
chips); antes da cura devolvia `BODY`, porque o chip não tinha caixa. Com cinco
controles a frase fica acima da fileira e não cobre cartão (ver a validação).

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
* **O quinto controle no WebKit** — medido pela validação: a frase cobria a máscara
  de dois cartões cheios, e foi corrigida (ver abaixo).
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

## O que a validação refez e corrigiu

Agente VALIDA/CORRIGE, 13/09/2026, na mesma árvore e na mesma branch. Rascunho em
`valida/`, dentro da pasta `RECONECTAR-SAMBA-02/` do scratchpad. Nada no aparelho: o
serviço e a ponte foram dublês dentro do processo (`estado_do_daemon`,
`ponte.resultado`, `ponte.chamar`, `ponte.chamar_detalhado` e o `_safe_call` do
bridge por baixo deles).

### O achado e a correção (`b27b63da`)

**A frase do quinto controle cobria a máscara de dois cartões cheios.** A entrega
pôs `.mesa-notas` por cima da fileira em TODO estado. A mesma linha acende com mais
controles que lugares (`a01_jogar._frase_da_mesa`: *«Há 5 controles ligados e esta
tela mostra 4…»*), e aí os quatro lugares estão cheios. Com o fundo do quadro, a
frase pousava sobre o chip «DualSense» da máscara do P2 e do P3:

* no piloto oculto (WebKit), com cinco controles no dublê, a caixa da frase cruza a
  máscara do P2 e a do P3 (`webkit-ramo-cinco.png`);
* no Chrome, a 1228 e 1300, o clique a 2, 25, 75 e 98 % da largura da frase cai no
  chip da máscara. Clicar na frase trocava a máscara de um cartão cujo chip ela
  escondia.

A régua da entrega, `test_a_frase_por_cima_nao_rouba_o_clique_dos_cartoes`, aceitava
essa cena: ela media só o MEIO da frase, e o meio cai no vão entre dois cartões.

**A correção:** a linha só sai do fluxo quando nenhum lugar da fileira está cheio
(um `:not(:has(…))` nas duas regras de `.mesa-notas` em `aba01.py`). Com um lugar
cheio, ela fica acima da fileira, como na base. É o que a D-07 diz, *«uma frase por
cima dos lugares apagados»*
([AS DEZESSEIS DECISÕES](../../2026-09-04-AS-DEZESSEIS-DECISOES-DELA-e-as-sprints-que-nascem.md)),
e com cinco controles não há lugar apagado.

O `pointer-events:none` saiu. Por cima dos lugares apagados não há gesto embaixo da
frase (o `elementsFromPoint` devolve `.mascara`, `.cartao off` e `.pecas`, nenhum
`[data-gesto]`), então ele não protegia nada.

**O preço, declarado:** com o quinto controle o botão desce 27 px, como na base (y
463 → 490 no WebKit). Isso acontece quando um controle entra, e não no tique que
samba: sem estado, `_frase_da_mesa` devolve `""` e a frase apaga.

A régua nova é `test_a_frase_do_quinto_controle_nao_cobre_cartao_cheio`, a 1228 e
1300. Ela acende a frase com o texto do pacote sobre os quatro cartões cheios e
reprova se a caixa dela cruzar um `[data-gesto]` visível de cartão.

### As medidas, refeitas

Piloto oculto (WebKitGTK, vista de 1212 px de largura), y do topo do botão, com a
sonda da validação. As três colunas são:

* **antes**: a página de `e1c7d96b`, com a folga desligada no processo (o `_tique` da
  base);
* **entrega**: `290eb555`;
* **validação**: `b27b63da`.

| estado | antes | entrega | validação |
| --- | --- | --- | --- |
| repouso, 2 controles | 463 | 463 | 463 |
| 2º tique mudo | **402**, os quatro apagados | 463, P1 e P2 cheios | 463, P1 e P2 cheios |
| 4º tique mudo em diante | **402** | 462, apagados | 462, apagados |
| lista vazia, frase acesa | **429** | 462 | 462 |
| cinco controles, frase acesa | 490, frase acima | 462, **frase sobre P2 e P3** | 490, frase acima, nada coberto |

No Chrome, na página publicada com a folha do piloto, a 1228 e 1300 (antes /
entrega / validação), o botão nasce em 464 nas três. Os lugares apagados dão 403 /
463 / 463, a lista vazia 430 / 463 / 463 e os cinco controles 491 / 464 / 491.

As fotos em repouso, antes × validação, têm **0 pixel diferente**. As de cinco
controles, antes × validação, também.

**O clique:** nas três corridas o «Reconectar controles» foi clicado em repouso, com
dublê de `coop.sync` e `identity.renumber`. O desfecho foi `aplicou`, a classe
`hef-deu-certo` acendeu, e o y ficou em 463 durante o voo. No centro do chip de cada
lugar apagado, o WebKit devolve `DIV.mascara`; na base devolvia `BODY`, porque o chip
não tinha caixa.

**O N da folga, recontado** com um contador escrito sem ler o da entrega. O diário
tem 28 `[daemon mudo]`, 17 deles `timed out`, em 15 corridas. Das 14 que têm um tique
bom provado depois, 13 duraram um tique e uma durou três. O número da entrega se
confirma.

**Posse.** Os dois arquivos de fora se sustentam:

* `a06_navegacao.py` muda uma linha de comentário. `Piloto._depois_do_gesto` existe e
  é quem imprime *«DISSE APLICADO E NADA MUDOU»*. A `F1-REMAPEAR-02`, dona do arquivo
  nesta onda, acrescenta 14 linhas noutro trecho.
* `test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio.py`: a mordida (e), abaixo, prova
  que ele reprovava com a cura.

**Botões:** a 01 tem 5 `<button` e 23 `data-gesto`, antes e depois. As dez páginas
publicadas somam 277 e 361, antes e depois. Nenhuma frase nova: as duas linhas são as
mesmas do pacote.

### As mordidas, refeitas

Cada uma foi devolvida com `git status` limpo em `b27b63da`.

| mordida | reprovou |
| --- | --- |
| (a) `st = self._folga.mudo(e)` → `st = {}` | a do WebKit: *«o serviço demorou 1 tique(s) e os lugares já apagaram»* |
| (f1) a fronteira da folga, `<=` → `<` | a folga sozinha (*«o 3º tique mudo seguido já apagou os lugares»*) e a do WebKit |
| (f2) `_o_servico_so_demorou` sempre verdadeiro | os três casos de serviço fora do ar (*«FileNotFoundError ganhou folga»*) |
| (b) a regra S-04 de volta a `display:none`, regerada e publicada | as duas cenas do Chrome (*«o botão subiu 61 px — y 464.0 → 403.0»*), o chip escondido e a do WebKit (*«subiu 61 px — y 463.0 → 402.0»*) |
| (c) sem `position:absolute` na frase, regerada e publicada | as duas cenas da lista vazia e a do WebKit (*«desceu 20 px — y 463.0 → 483.0»*) |
| (d) sem o `:not(:has(…))`, regerada e publicada | a régua nova, nas duas larguras: a frase cobre a máscara do P2 e do P3 |
| (e) a régua de fora da posse volta a cobrar só a caixa | `test_o_lugar_vazio_nem_desenha_o_gesto` |

**Réguas vizinhas, depois da correção**, em três lotes:

* 46 verdes: a régua da sprint, `test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio`,
  `test_a01_a_mesa_vazia_fala` e `test_a_linha_de_ressalva_so_nasce_quando_ha`;
* 188 verdes: catorze arquivos que leem a 01 ou o `aba01.py`, entre eles
  `test_a_aba_01_jogar_fecha_as_linhas`, `test_a_tela_nao_samba`,
  `test_o_casamento_das_dez` e `test_portao_o_par_com_metade_ligada`;
* 214 verdes: onze que dirigem o `_tique` ou calam o serviço, entre eles
  `test_agora_e_depois_01`, `test_a_recusa_chega_ao_cartao` e
  `test_os_dez_geradores_rodam`.

**Perfis:** 159 arquivos, com md5 idêntico depois de cada uma das cinco corridas do
piloto.

**Portões:** `bash scripts/portoes.sh` completo, depois do `git add -A`, com esta
seção já escrita. Todos verdes.

### O que a validação não verificou

* O aparelho, e quanto a folga dura com o socket real.
* O olho dela sobre a frase centrada por cima dos quatro lugares apagados
  (`webkit-fix-vazia.png`), e sobre os 27 px que o botão desce quando o quinto
  controle entra.
* O topo com o serviço calado depois da folga: ele ainda mostra como «Perfil ativo» o
  perfil gravado no disco (`webkit-fix-mudo-depois-da-folga.png`). Na base é igual.
