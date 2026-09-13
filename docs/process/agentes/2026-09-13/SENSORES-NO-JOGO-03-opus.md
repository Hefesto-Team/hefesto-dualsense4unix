# SENSORES-NO-JOGO-03 — opus

Agente IMPLEMENTA do lote 1309-onda3, na árvore `voo/SENSORES-NO-JOGO-03-opus`,
nascida de `onda/1309` (`b791d234`, conferido contra `git rev-parse --short
onda/1309`). **A sprint só troca um fato em texto:** nenhum aparelho tocado, a
bancada não foi reservada (`bancada: false`), o daemon não foi chamado, o piloto
não rodou. **A tela não muda:** nenhuma página regerada, e por isso nenhuma foto,
como a §V manda.

## O que mudou

**A frase, igual nos oito lugares** (a tabela está na
[SENSORES-NO-JOGO-02](../../sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md),
§1):

> o zero em Modo Virtual era da libSDL2 2.30.0 do sistema; nas bibliotecas dos
> runtimes da Steam o vpad expõe os dois sensores, e o SDL pareia o nó «Motion
> Sensors» pelo `uniq`

| lugar | o que mudou | linhas |
| --- | --- | --- |
| `src/hefesto_dualsense4unix/daemon/sensor_hub.py`, docstring de `_reconciliar_grabs` | o alcance do braço evdev passa a ser quem lê o nó do FÍSICO (`evtest`, emulador, quem abriu o físico), mais a frase | 4 por 4; o arquivo segue com 641 |
| `src/hefesto_dualsense4unix/daemon/ipc_handlers.py`, docstring de `_handle_sensor_set` | o primeiro item vira a frase, com os bytes do vpad sendo os deste daemon; o do Modo Nativo fica (o giro chega ao SDL pelo `hidraw` do físico, medido em 04/09 e 10/09) | 6 por 6; o arquivo segue com 6950 |
| `scripts/check_ate_onde_a_prova_chegou.py`, a razão do `sensor` em `A_PROVA_QUE_FALTA` | a hipótese sai; entram a frase, o que falta (o jogo aberto receber e reagir, da MESA-DE-QUATRO-01) e o precedente do touchpad que explica o destino | 6 por 6; o arquivo segue com 529 |
| `docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md` | o fim da §3.3 e a linha 1 da tabela da §4 — a busca achou o fato também na §4, que a §E da sprint não listava | +8 −4 |
| `docs/process/sprints/2026-09-05-ONDA-CINCO-INDICE.md` | o item do giroscópio sob a máscara Xbox: a frase, e a rota sob a máscara segue sem medição | +8 −4 |
| `docs/process/sprints/2026-09-11-AUDITORIA-SOM-GIRO-01-todas-as-features-por-controle-e-dentro-do-jogo.md` | a §1: a hipótese sai, a frase entra, e o jogo aberto segue sem medição | +7 −3 |
| `docs/process/agentes/2026-09-04/ONDA1-D3.md` | nota datada no topo; o corpo fica | +12 |
| `docs/process/agentes/2026-09-11/AUDITORIA-SOM-GIRO-01-opus.md` | nota datada no topo; o corpo fica | +11 |

Nos três documentos vivos a troca leva a marca **FATO SUBSTITUÍDO em
13/09/2026**, e nenhuma nota repete a frase caída.

**O que ficou igual de propósito:** o custo `grande` e a dona do `sensor` na
régua da quinta pergunta. O veredito foi conferido rodando a régua da base
(`git show b791d234:`, com o `__file__` da árvore) e a desta branch: as duas
saem `rc=0` e VERDE, e o `diff` das duas saídas é **uma linha**, a da razão.

### A busca da §I.5, antes e depois

Um script fora da árvore (`busca.py`, no scratchpad deste agente) lê os arquivos
versionados, `*.html` e `*.csv` incluídos, junta as linhas quebradas, tira
marcação de markdown e de comentário, e conta dezesseis formas: as quatro da §V
da SENSORES-NO-JOGO-02 e doze vizinhas, tiradas dos textos que esta sprint
trocou. A base é lida do objeto do git; o depois, do disco.

| arquivo | `b791d234` | agora |
| --- | --- | --- |
| `docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-...` | 2 | 0 |
| `docs/process/sprints/2026-09-05-ONDA-CINCO-INDICE.md` | 1 | 0 |
| `docs/process/sprints/2026-09-11-AUDITORIA-SOM-GIRO-01-...` | 1 | 0 |
| `scripts/check_ate_onde_a_prova_chegou.py` | 1 | 0 |
| `src/hefesto_dualsense4unix/daemon/ipc_handlers.py` | 3 | 0 |
| `src/hefesto_dualsense4unix/daemon/sensor_hub.py` | 1 | 0 |
| `docs/process/agentes/2026-09-04/ONDA1-D3.md` | 3 | 3 — corpo sob a nota datada |
| `docs/process/agentes/2026-09-11/AUDITORIA-SOM-GIRO-01-opus.md` | 1 | 1 — corpo sob a nota datada |
| `docs/process/sprints/2026-09-13-SENSORES-NO-JOGO-02-...` | 1 | 1 — a nota FATO SUBSTITUÍDO da §1 |
| `docs/process/sprints/2026-09-13-SENSORES-NO-JOGO-03-...` | 3 | 3 — a §E, que enumera onde o fato ficou |
| `docs/process/agentes/2026-09-13/SENSORES-NO-JOGO-02-opus.md` | 5 | 5 — registro, fora da posse (item 1 abaixo) |
| `docs/process/sprints/2026-09-12-OS-QUATRO-ORFAOS-DE-1009-...` | 1 | 1 — título de commit de 10/09, fora da posse |
| **total** | **23 em 12 arquivos** | **14 em 6** |

Uma forma vizinha foi apertada depois da primeira corrida: a frase do Modo
Nativo em `profiles/schema.py` casava com ela e é verdadeira.

## Qual mordida prova

Duas, e os dois lados arrancados foram devolvidos a partir de uma cópia, com o
`md5` conferido.

**1. A busca vê o texto velho.** O `sensor_hub.py` da base devolvido ao disco:

```
== CURA ARRANCADA
  1  src/hefesto_dualsense4unix/daemon/sensor_hub.py
TOTAL 15 em 7 arquivo(s)
== CURA DEVOLVIDA
TOTAL 14 em 6 arquivo(s)
```

**2. O número de linhas é o que segura as citações.** Uma linha a mais na
docstring do `sensor.set`, logo abaixo do cabeçalho da medição:

```
== CURA ARRANCADA (ipc_handlers.py com 6951 linhas)
scripts/validar-citacoes-de-linha.py --all  rc=1
  18 citação(ões) de linha podre(s) em 21 documento(s) e 9 planilha(s):
  docs/protocol/ipc-unix-socket.md:72: `daemon/ipc_handlers.py:5681` -- a faixa não contém `_handle_daemon_reload`, que a citação promete
  docs/protocol/ipc-unix-socket.md:76: `daemon/ipc_handlers.py:5747` -- a faixa não contém `_handle_speaker_set`, que a citação promete
  (...)
tests/unit/test_portao_o_par_com_metade_ligada.py  rc=1
  FAILED ...::TestTodaCitacaoDeLinhaConfere::test_toda_citacao_de_linha_em_comentario_de_codigo_confere
  (a:02 e a:09 citando linhas de ipc_handlers.py que andaram uma)
  1 failed, 15 passed
== CURA DEVOLVIDA
sensor_hub.py: SUCESSO · ipc_handlers.py: SUCESSO · check_ate_onde_a_prova_chegou.py: SUCESSO
scripts/validar-citacoes-de-linha.py --all  rc=0
  OK: 3288 citação(ões) de linha conferida(s) em 21 documento(s) e 9 planilha(s)
tests/unit/test_portao_o_par_com_metade_ligada.py  rc=0
  16 passed
git diff --numstat: 4 4 sensor_hub.py · 6 6 ipc_handlers.py · 6 6 check_ate_onde_a_prova_chegou.py
```

**As réguas vizinhas, com a cura:** `ruff check` nos três arquivos de código,
verde; `test_portao_a_quinta_pergunta_morde.py`,
`test_perfil_por_controle_o_campo_espera_o_caminho.py` (que lê o corpo do
`sensor.set` por `inspect`), `test_o_sensor_desliga_de_verdade.py` e
`test_portao_o_par_com_metade_ligada.py`: **96 passed**.

**Os portões:** `git add -A && bash scripts/portoes.sh` → **TODOS VERDES — 60
portões**, com `citacoes-de-linha`, `citacoes-no-codigo`,
`ate-onde-a-prova-chegou`, `referencias-docs`, `acentuacao` e `ruff` entre eles.

## O que NÃO verifiquei

* **O fato não foi remedido.** A frase vem da §1 da SENSORES-NO-JOGO-02 e da
  seção 5-bis de `docs/protocol/pilha-steam-input-xpad-sdl.md`, medidas pela
  onda 2. Nenhuma célula do mapa foi exercitada.
* **O alcance do grab no nó do físico** («quem abriu o físico») vem do
  cabeçalho de `core/virtual_motion.py`, reescrito pela onda 2; não o medi.
* **O giroscópio sob a máscara Xbox pelo nó do físico.** Os três documentos
  dizem «sem medição», e é o que se sabe.
* **A suíte inteira**, que é de quem coordena. Rodei só os quatro arquivos
  acima.
* **Os links novos renderizados.** O `referencias-docs` confere que o arquivo
  existe; não abri as páginas.

## O que sobrou para o próximo

1. **Dois registros fora da posse ainda contêm as formas antigas, e nenhum é
   afirmação:** a entrega `docs/process/agentes/2026-09-13/SENSORES-NO-JOGO-02-opus.md`
   (as formas que ela buscou, em «A frase caída», e o item 1 de «O que sobrou»,
   que esta sprint fecha — quem tocar nela pode anotar isso), e a tabela de
   `docs/process/sprints/2026-09-12-OS-QUATRO-ORFAOS-DE-1009-a-costura-que-regride-a-tela.md`,
   que cita o título de um commit de 10/09.
2. **A dona do `sensor` e da `mascara` na régua da quinta pergunta é a
   SENSORES-NO-JOGO-01, que está `feita`.** A razão do `sensor` agora diz que o
   resto é da MESA-DE-QUATRO-01 (`aberta`); trocar a dona ficou fora do §I, e a
   régua só exige que ela exista no disco.
3. **O mapa e o `specs.html`** seguem em `nao_toca`: as células
   `movimento.giroscopio.jogo@dualsense` e `movimento.acelerometro.jogo@dualsense`
   ainda esperam a ressalva de biblioteca, como a entrega da onda 2 já dizia.

## O que a validação refez e corrigiu

Agente VALIDA/CORRIGE, na mesma árvore e na mesma branch. Nenhum aparelho, daemon
ou piloto tocado; a tela não muda, e por isso nenhuma foto.

### Refeito, e conferiu

* **Posse:** os dez arquivos de `git diff --name-only b791d234..HEAD` cabem no
  `posse:` mais esta entrega; os três que a validação tocou também estão nele.
* **Tela:** nenhuma página tocada. Nas 20 páginas publicadas (`mockup/NN` e
  `interface/paginas/NN`), 708 `data-gesto` e 506 `<button` na `b791d234` e na
  branch.
* **O número de linhas:** 641, 6950 e 529 na base e na branch; `numstat` 4/4,
  6/6 e 6/6; `ruff check` verde nos três.
* **O veredito da régua da quinta pergunta:** a da base, posta no disco e
  devolvida, e a da branch saem `rc=0`; o `diff` das saídas, com e sem
  `--tabela`, é uma linha em cada, a da razão.
* **A busca, refeita com expressões próprias** (dezesseis, mais largas que as
  frases do implementador: pegam «não recebe giroscópio», «não enumera o nó» e
  «não a um jogo de Steam» em qualquer arquivo versionado, `*.csv` e `*.html`
  incluídos): **76 achados em 24 arquivos** na `b791d234`, **61 em 19** na
  branch. Os que sobram, lidos um a um, não afirmam o fato caído: a frase da
  máscara Xbox e Nintendo, que é verdadeira (em `app/actions/home_actions.py`,
  `app/widgets/controller_card.py`, `docs/usage/interface.md`, na paridade e em
  seis documentos que a citam), a do Modo Nativo em `profiles/schema.py`, os
  corpos sob as notas datadas, as notas FATO SUBSTITUÍDO, a §E desta sprint e
  os dois registros fora da posse do item 1 acima.
* **As mordidas**, cada sabotagem devolvida por `git checkout HEAD --` e
  conferida por `md5` e `git diff` vazio:

  | sabotagem | régua | reprovou? |
  | --- | --- | --- |
  | `sensor_hub.py` da base no disco | a busca: 62 em 20, com `sensor_hub.py` nomeado; devolvida, 61 em 19 | sim |
  | uma linha a mais na docstring do `sensor.set` | `validar-citacoes-de-linha.py --all` `rc=1`, 18 podres; `test_portao_o_par_com_metade_ligada.py` 1 failed, 15 passed; devolvida, 3288 OK e 16 passed | sim |
  | a razão da base na régua da quinta pergunta | a busca nomeia `check_ate_onde_a_prova_chegou.py` | sim |
  | a A-MASCARA-NAO-CUSTA-FEATURE da base | a busca: 8 achados no arquivo, com «o SDL não enumera aquele nó» | sim |
  | uma linha a mais na docstring de `_reconciliar_grabs`, e outra na razão da régua | as duas réguas de citação ficam verdes | **não** |

  A última não reprova, e não é defeito: as 29 citações de `sensor_hub.py`
  param na linha 339, antes da docstring, e `check_ate_onde_a_prova_chegou.py`
  não tem citação por linha. O mesmo número de linhas vale nos três arquivos,
  mas hoje só o do `ipc_handlers.py` tem régua que o segure.
* **Réguas vizinhas:** os 135 arquivos de `tests/unit` que citam os arquivos ou
  os símbolos mudados (`sensor_hub`, `ipc_handlers`, `_reconciliar_grabs`,
  `_handle_sensor_set`, `sensor.set`, a régua da quinta pergunta e os documentos
  tocados), em quatro lotes: 382, 708, 648 e 662 verdes, 3 `xfailed`, nenhum
  vermelho.

### Corrigido

1. **A §3.3 da A-MASCARA-NAO-CUSTA-FEATURE dava ao nó do FÍSICO um alcance que
   ninguém mediu.** «O canal alcança `evtest`, emuladores e o SDL»: o canal
   daquele parágrafo é o nó do físico, e o vpad carimba um `uniq` próprio
   (`vpad_mac`, derivado do aparelho e diferente do dele, porque o
   `hid_playstation` recusa MAC repetido). O SDL que abriu o vpad casa
   o nó do vpad; o do físico só chega a quem abriu o físico, que é o que o item
   1 do cabeçalho de `core/virtual_motion.py` diz. A frase passou a dizer isso.
2. **A nota da AUDITORIA-SOM-GIRO-01-opus repetia o mesmo alcance** («além de
   `evtest` e emuladores, o SDL o pareia», sobre o nó do físico do reparo da
   §5). Agora cai a razão dada sobre o SDL, e o nó do físico alcança `evtest`,
   emuladores e quem abriu o físico.
3. **A nota da ONDA1-D3 se contradizia:** o item 2 de «O que sobrou» «cai
   inteiro» e, na mesma frase, a hipótese dele «se confirmou». Cai o achado; a
   hipótese se confirmou para o HIDAPI da SDL2 clássica e não era a causa do
   zero — a §2 da SENSORES-NO-JOGO-02 põe a causa na classe udev que a 2.30.0
   exige do nó, e com a dica em 0 a mesma biblioteca entrega pelo evdev.

### Os portões

`git add -A && bash scripts/portoes.sh`, com o `PYTHONPATH` desta árvore no
cabeçalho, sobre as três correções e esta seção: **TODOS VERDES — 60 portões**,
com `citacoes-de-linha`, `citacoes-no-codigo`, `ate-onde-a-prova-chegou` e a
mordida dele, `referencias-docs`, `anonimato`, `colisao-de-sprints` e
`acentuacao` entre eles.

### O que a validação não refez

* **O fato no aparelho**, e nada do que «O que NÃO verifiquei» já declara.
* **A dona do `sensor`** (item 2 de «O que sobrou»): a razão nomeia a
  MESA-DE-QUATRO-01 e a coluna da dona segue na SENSORES-NO-JOGO-01. Trocar a
  dona muda a linha que a régua imprime, e o §I.3 manda não mexer no veredito.
* **A suíte inteira**, que é de quem coordena.
