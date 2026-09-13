# RESTOS-DA-ONDA-TRES-01 — a guarda que a paridade não viu, a docstring da GUI, a dona do sensor e a ressalva da biblioteca (IMPLEMENTA, opus)

Sprint: [RESTOS-DA-ONDA-TRES-01](../../sprints/2026-09-13-RESTOS-DA-ONDA-TRES-01-a-guarda-que-a-paridade-nao-viu-a-docstring-da-gui-a-dona-do-sensor-e-a-ressalva-da-biblioteca.md)
· lote `1309-onda4` · branch `voo/RESTOS-DA-ONDA-TRES-01-opus` · base `a34ec006`
(conferida igual a `onda/1309`) · `bancada: false`. Nenhum aparelho, daemon,
piloto ou página tocados. **A tela não muda**, e por isso não há foto.

O python é o da venv da árvore principal, a mesma que os portões escolhem, com o
`PYTHONPATH` desta árvore. O import foi conferido em `…-opus/src`.

## O que mudou

| §I | arquivo | o que mudou |
| --- | --- | --- |
| 1 | `broker/hidraw_broker.py` | A docstring de `physical_nodes_exposure` deixa de dizer que «a GUI e o `doctor.sh` passam a consultar» e passa a dizer que quem consulta é o `doctor.sh` e que a interface deixou de consultar em 13/09/2026. Uma linha por uma: o arquivo segue com 1229 linhas. |
| 1 | `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py` | **A declaração em `_NAO_E_PROMESSA` fica, porque continua necessária** (mordida M4). A razão escrita ao lado dela deixa de dizer que a docstring caducou: agora diz que a docstring diz o mesmo desde esta sprint. Duas linhas por duas: o arquivo segue com 5410. |
| 2 | `docs/data/paridade-gtk-html.csv`, linha 57 | Medida de novo contra o código dos dois lados: de `FALTA_NO_HTML` para **`DIFERENTE`**. O sinal era `_pecas_que_escrevem_som`, símbolo da GTK que só cobra ausência. Agora é `data-apagado="sem-alvo"`, com escopo `interface/aba02.py`, a folha que apaga. O `html_onde` passa a apontar os símbolos da guarda de hoje: o campo `"alto-apagado"` e `def microfone_apagado` em `a02_controles.py`, e a primeira regra `sem-alvo` da folha em `aba02.py`. O `html_faz` descreve o que o código faz hoje. No `porque`, o bloco «DECIDIDO em 04/09» fica; o de 06/09, que dizia «não publicada» e citava o endereço `som-sem-endereco`, virou o bloco datado desta medição. O `gtk_onde` e o `gtk_faz` não mudaram. |
| 2 | `docs/process/2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md` | A tabela foi recontada do CSV: `02-controles` passa de `24 DIFER · 6 FALTA` para `25 · 5`, e `TODAS` de `159 · 30` para `160 · 29`. A paridade não se mexe. Ganhou a «Nota de verificação — 13/09/2026, a guarda sem endereço (linha 57)». |
| 3 | `scripts/check_ate_onde_a_prova_chegou.py` | A dona do `sensor` passa a ser a `MESA-DE-QUATRO-01`, a sprint que a razão já nomeava. A régua ganhou o caso: quando a razão diz «é da <SPRINT>», a dona tem de ser essa sprint (`dona_que_a_razao_nomeia`, `a_dona_e_a_sprint`, passo 2 do `main`). A razão não mudou. |
| 3 | `tests/unit/test_portao_a_quinta_pergunta_morde.py` | Mordida 4c (`test_morde_a_dona_que_nao_e_a_que_a_razao_nomeia`), com um dublê sobre a linha do `mudo`. A irmã lê o inventário de hoje: `test_toda_razao_que_nomeia_a_dona_concorda_com_a_coluna`. O item 4 do cabeçalho diz o caso novo. |
| 4 | `docs/data/mapa-controles.csv` | Nota datada na coluna `nota` de `movimento.giroscopio.jogo@dualsense` e de `movimento.acelerometro.jogo@dualsense`, que estavam vazias. A nota diz que o dado chega ao vpad e que o jogo só o recebe se a biblioteca SDL que ele carrega parear o nó «Motion Sensors». Traz os números da sonda da SENSORES-NO-JOGO-02: a 2.30.0 do sistema não pareia, e as nove bibliotecas dos runtimes entregam. Diz também que a prova no jogo é da MESA-DE-QUATRO-01, com a biblioteca lida em `/proc/<pid>/maps`, e dá os três endereços. **Nenhum veredito mudou.** Conferido com o `csv`: só a coluna `nota` mudou nos dois registros, e o arquivo tem as mesmas 312 linhas físicas. |
| 4 | `html/specs.html`, `docs/data/LEIA-PRIMEIRO.md` | Regerados por `scripts/gerar-mapa.py` e `scripts/check_paridade_transporte.py --leia-primeiro --escrever`. Mudaram quatro números: caracteres, tokens e bytes do mapa, e bytes do `specs.html`. |

**§I.2, a busca.** Nenhuma outra linha da paridade cita `som-sem-endereco`,
`_steam_input_excecao_status`, `physical_nodes_exposure` ou o `efetiva` da
varredura. A busca foi feita pelo `csv`, em todas as colunas, com
`exceç|excec|efetiv`. As que casaram falam de outras exceções (Modo Nativo,
máscara Xbox, lista de exceções da Steam) ou do perfil efetivo. Hoje
`git grep som-sem-endereco -- docs/data/` volta vazio.

**§I.5.** Não reapontei citação alheia. As três citações do `html_onde` novo são
desta sprint e apontam as linhas de hoje.
`scripts/validar-citacoes-de-linha.py --all` deu OK, com 3289 citações.

## Qual mordida prova

Roteiro `mordidas.sh` no rascunho. Cada mordida guarda o arquivo, sabota, roda a
régua e devolve por cópia, com o md5 conferido. O `sha256` do `git diff` antes
de todas as mordidas e depois delas é o mesmo:
`538384585fcc16f9…`, «git diff IDÊNTICO».

| | cura arrancada | a régua, com a cura fora | de volta |
| --- | --- | --- | --- |
| M1 | a tabela do TERCEIRO NÚMERO na contagem velha (2 linhas) | `check_paridade_gtk_html.py` **rc=1**: `numero-publicado … linha '02-controles': publicado (50, 16, 24, 6, 4, 0, 32) no CSV (50, 16, 25, 5, 4, 0, 32)`, e o mesmo em `TODAS` | rc=0, «145 IGUAL · 160 DIFERENTE · 29 FALTA_NO_HTML» |
| M1c | a linha 57 da base de volta, com a tabela nova | **rc=1**, `numero-publicado` em `02-controles` e `TODAS` | md5 confere |
| M1d | as 9 regras `[data-apagado="sem-alvo"]` da folha da 02 trocadas por outro valor | **rc=1**: `sinal-sumiu: paridade-gtk-html.csv:57 … o sinal 'data-apagado="sem-alvo"' não está mais em …/interface/aba02.py` | rc=0 |
| M2 | a dona velha do `sensor` (SENSORES-NO-JOGO-01) de volta, com a régua nova | script **rc=1**: `sensor: a razão diz que o resto é da MESA-DE-QUATRO-01, e a dona é 2026-09-08-SENSORES-NO-JOGO-01-…`; pytest **6 failed, 13 passed**: `test_o_inventario_de_hoje_passa` e `test_toda_razao_que_nomeia_a_dona_concorda_com_a_coluna` entre eles, e os outros quatro porque o `main` para no passo 2 | 19 passed |
| M2b | **a régua da base** (`git show HEAD:`), que tem a dona velha e não tem o caso | **rc=0, VERDE.** Esta é a razão do caso novo: com a dona velha a régua não reprovava, e o §V manda que ela ganhe o caso | md5 confere |
| M3 | o `specs.html` da base com o CSV novo | `gerar-mapa.py --check` **rc=1** («DESATUALIZADO»); `--leia-primeiro` **rc=1**: `FALHA numero-caduco: bytes:html/specs.html publica 2.262.107 e a medição de agora diz 2.259.535` | md5 confere |
| M3b | o CSV da base, sem as duas notas, com o `specs.html` novo | `gerar-mapa.py --check` **rc=1** | `--check` rc=0 e `--leia-primeiro` rc=0 |
| M4 | a declaração de `physical_nodes_exposure` arrancada de `_NAO_E_PROMESSA` (18 linhas) | **1 failed**: `test_toda_promessa_solta_esta_classificada`, com `assert not ['broker/hidraw_broker.py::physical_nodes_exposure']` | 1 passed |

A M4 responde o «se» do §I.1. O portão acusa a função por falta de chamador
alcançado em produção, e não pelo que a docstring diz. Corrigir a promessa não
dá um chamador à função, então a declaração continua necessária e só a razão
mudou.

**As réguas na árvore curada:**

* `check_paridade_gtk_html.py`: rc=0, «396 features … 145 IGUAL · 160 DIFERENTE · 29 FALTA_NO_HTML · 58 SO_NO_HTML · 4 NAO_DA_PARA_SABER (37%)»;
* `check_ate_onde_a_prova_chegou.py`: rc=0, VERDE, com `dona: 2026-09-06-MESA-DE-QUATRO-01-…` na linha do `sensor`;
* `gerar-mapa.py --check`: «atualizado»; `check_paridade_transporte.py --leia-primeiro`: «os 36 números conferem»; `check_paridade_transporte.py` inteiro: rc=0;
* `test_portao_a_quinta_pergunta_morde.py`: 19 passed. Na base eram 17;
* `portao_a_casa_sabe_e_o_produto_nao_faz.py` e `test_portao_o_par_com_metade_ligada.py`: 58 passed. Na base, o casa-sabe e a quinta pergunta juntos davam 59;
* `validar-citacoes-de-linha.py --all`: OK, 3289 citações;
* `ruff check` nos quatro arquivos Python tocados: limpo.

## O que NÃO verifiquei

* **A tela.** O veredito novo da linha 57 vem da leitura do código dos dois
  lados. Não abri o piloto. O que viu a moldura apagar e o gesto recusar no
  WebKit foi a validação da RESTOS-DA-ONDA-DOIS-01, com um controle dublê sem
  endereço
  ([entrega](RESTOS-DA-ONDA-DOIS-01-opus.md), «O que a validação refez»), e a
  linha a cita.
* **O aparelho.** Nenhuma célula do mapa foi exercitada. Os números das duas
  notas (126 a 157 giros, 314 a 342 acelerômetros, a 2.30.0 sem parear) foram
  copiados da entrega da SENSORES-NO-JOGO-02 e não os medi de novo. A sonda
  daquela sprint viu só o vpad de um controle no rádio, e a nota diz isso.
* **A docstring não tem régua.** A frase velha saiu, conferida por
  `git grep "a GUI e o"`, que não acha nada em `hidraw_broker.py`. Nenhum teste
  reprova se ela voltar.
* **A citação `§2 02[04]` do bloco «DECIDIDO» da linha 57.** Ela veio da base e
  ficou. Um `grep -F "02[04]"` no `O-PO-DECIDE` não acha a marca, e só os
  documentos de 04/09 que o citam a trazem. Não fui procurar onde a decisão mora.
* **A suíte inteira**, por ordem do despacho. Rodei só os arquivos acima.

## O que sobrou para o próximo

1. **O LEIA-PRIMEIRO publica «`nota` (225 linhas)» duas vezes, e o número já
   estava errado antes desta sprint:** o mapa da base tem 228 linhas com `nota`,
   e depois dela tem 230. O número é prosa, declarado como número solto em
   `_MEDIDAS_QUE_NAO_SAO_DAQUI` de `scripts/check_paridade_transporte.py`, que
   está fora da posse. Escrever «230» sem tirar o «225 linhas» de lá seria um
   número solto novo, e a régua dele reprova. A cura é um marcador gerado
   (`<!--@…-->`) com a linha saindo daquela lista no mesmo commit.
2. **Outras três donas da quinta pergunta estão `feita`:** `mascara`
   (SENSORES-NO-JOGO-01), `mic-modo` (MIC-OS-QUATRO-01) e `volume`
   (MIC-VOLUME-02). A razão da `mascara` ainda diz que espera «o instrumento que
   a SENSORES-NO-JOGO-01 precisa escrever». Nenhuma das três razões diz «é da
   X», e por isso o caso novo não as alcança. Uma régua do tipo «a dona tem de
   estar aberta» deixaria as três vermelhas agora, e o estado delas é de outra
   sprint medir.
3. **As citações por linha das planilhas** continuam sendo de quem coordena. O
   roteiro da CITACOES-DAS-PLANILHAS-01 roda de novo na costura.
4. **Para a SPECS-A-PROCEDENCIA-01 e a MESA-DE-QUATRO-01**, pelas chaves
   `movimento.giroscopio.jogo` e `movimento.acelerometro.jogo`: a `nota` diz
   como escrever o degrau do jogo. Os vereditos (`MONTOU` nos dois transportes)
   ficaram.
5. **Registros que ainda falam da ressalva como pendente:** o item 2 de «O que
   sobrou» da entrega da SENSORES-NO-JOGO-02 e o item 3 da entrega da
   SENSORES-NO-JOGO-03. São registro, e não mexi.

## O que a validação refez e corrigiu

VALIDA/CORRIGE, opus. Mesma árvore e mesma branch; a correção é o commit
`b05e5114`. O python é o da venv da árvore principal com o `PYTHONPATH` desta
árvore, e o import foi conferido em `…-opus/src`.

### A posse e as páginas

* `git diff --name-only a34ec006..HEAD` dá os dez arquivos do `posse` e esta
  entrega. Nada fora.
* Nenhuma página publicada mudou: nenhum arquivo de `mockup/`,
  `interface/paginas/` ou `html/painel.html` no diff. Nos HTML versionados, 693
  `data-gesto` (17 arquivos) e 666 `<button` (32 arquivos), iguais em
  `a34ec006` e na branch. Sem foto, porque a tela não muda.

### As mordidas, refeitas

Cada uma sabota, roda a régua e devolve por `git checkout HEAD --`. Antes e
depois de cada roteiro, `git status --short` vazio e o `sha256` de
`git diff HEAD` igual ao do diff vazio.

| | cura arrancada | a régua | reprovou? |
| --- | --- | --- | --- |
| V1 | a tabela do TERCEIRO NÚMERO na contagem velha | `check_paridade_gtk_html.py` rc=1, `numero-publicado` em `02-controles` e `TODAS` | sim |
| V1b | a linha 57 da base, com a tabela nova | rc=1, `numero-publicado` nas duas linhas | sim |
| V1c | as nove regras `data-apagado="sem-alvo"` da folha da 02 trocadas | rc=1, `sinal-sumiu` na linha 57 | sim |
| **V1d** | **só as cinco regras do ALTO-FALANTE trocadas**, o microfone intacto | **rc=0, verde** | **não — achado 1** |
| V2 | a dona velha do `sensor`, com a régua nova | script rc=1 («a razão diz que o resto é da MESA-DE-QUATRO-01»); pytest 6 failed, 13 passed | sim |
| V2b | a régua da base, com a dona velha | rc=0: sem o caso novo a régua não via | (controle) |
| V2c | a régua nova com a leitura da razão cega (o regex nunca casa) | script rc=0; pytest 2 failed: a mordida 4c e a irmã do inventário | sim |
| V3 | o `specs.html` da base com o CSV novo | `gerar-mapa.py --check` rc=1; `--leia-primeiro` rc=1 (`bytes:html/specs.html`) | sim |
| V3b | o CSV da base com o `specs.html` novo | `--check` rc=1 | sim |
| V3c | o LEIA-PRIMEIRO da base com o CSV e o `specs.html` novos | `--leia-primeiro` rc=1, quatro `numero-caduco` | sim |
| V4 | a declaração de `physical_nodes_exposure` fora de `_NAO_E_PROMESSA` | 1 failed, `test_toda_promessa_solta_esta_classificada` | sim |
| **V5** | **a docstring da base de volta** («a GUI e o `doctor.sh` passam a consultar») | casa-sabe, restos da onda dois, R-06 e o veredito das três superfícies: **94 passed** | **não — achado 3** |

**V1d, medido na história:** o `aba02.py` de `b791d234`, a árvore em que a guarda
do alto-falante nunca acendia, já tinha quatro `data-apagado="sem-alvo"`, todos
do microfone (MIC-SEM-FONTE-01, `053a346c`), e nenhuma regra do alto-falante. Com
aquele arquivo e o sinal do implementador, a paridade dá **rc=0** (V1g). O sinal
passava sobre o defeito que a linha descreve.

### Os fatos, conferidos

* **A linha 57, contra os dois lados.** GTK: `_pecas_que_escrevem_som` e
  `_update_guarda_de_audio` deixam as peças insensíveis, põem a
  `DICA_AUDIO_SEM_ENDERECO` nas duas molduras e mostram o `_audio_aviso`. HTML:
  `alto-apagado` e `microfone_apagado` escrevem `data-apagado`, a folha esmaece o
  volume e a rota e põe `cursor:not-allowed`, `porques_do_som` leva a mesma
  `DICA_AUDIO_SEM_ENDERECO` ao `?`, e o gesto `volume` levanta `ValueError` sem
  `uniq`. `DIFERENTE` cabe na régua firmada em 06/09: a mesma resposta por outro
  caminho, com endereço, e sem o aviso.
* **A citação «§2 `02[04]`»** do bloco DECIDIDO existe: é a pergunta 04 da
  tabela `02-controles` na §2 do O-PO-DECIDE, «O botão apaga e a dica diz por
  quê. É a D-03 aplicada a esta aba.» A notação é aba[pergunta], e a tabela a
  escreve em colunas; por isso o `grep` literal volta vazio. Fecha o item do
  «não verifiquei» acima.
* **A docstring, contra quem chama hoje.** `git grep physical_nodes_exposure`: a
  única chamada viva fora dos testes é o `_censo_de_fisicos` de
  `scripts/doctor.sh`. A menção em `emulation_actions._steam_input_excecoes` é
  docstring e já diz o mesmo. Confere.
* **A dona do sensor, contra a razão.** A razão diz «é da MESA-DE-QUATRO-01». A
  SENSORES-NO-JOGO-01 está `feita` e diz no topo que o passo do jogo reagindo é
  da MESA-DE-QUATRO-01, e a seção «O que só a MESA-DE-QUATRO-01 responde» da
  SENSORES-NO-JOGO-02 inclui o jogo reagindo à mira. Confere.
* **A ressalva, contra a SENSORES-NO-JOGO-02.** Os números batem com a tabela
  das nove bibliotecas da entrega (126 a 157 giros, 314 a 342 acelerômetros) e
  com a 2.30.0 sem a variável (`False, 0`). **Mas a tabela das nove foi medida
  com `SDL_ACCELEROMETER_AS_JOYSTICK=0` e o HIDAPI do SDL desligado** (a
  entrega, «O ensaio contra as nove bibliotecas»; a pilha, 5-bis.1 e a régua da
  5-bis), e a nota dava os números sem a condição, logo depois da 2.30.0 no
  padrão. Lida assim, a nota dizia que as nove entregam em qualquer ambiente, e
  a 5-bis.2 mede o contrário para a 2.32.10 com a dica em 1. Achado 2.
* **Outras linhas das planilhas.** Em todo `docs/data/*.csv`, por
  `physical_nodes_exposure`, `_steam_input_excecao_status`, `som-sem-endereco`,
  `_pecas_que_escrevem_som`, «recebe zero», «2.30», «Modo Virtual»,
  `SENSORES-NO-JOGO-0[123]` e «a GUI e o»: só as duas notas desta sprint. «a GUI
  e o» casa na bateria, com outra frase.

### Corrigido, em `b05e5114`

1. **O sinal da linha 57** passa a ser a regra do alto-falante,
   `.moldura[data-bloco="alto-falante"][data-apagado="sem-alvo"]`, com o mesmo
   escopo. Com a borda de palavra do `prosa_do_codigo.agulha`, a forma sem o
   `.moldura` não casaria. O `porque` da linha e a nota de 13/09 do TERCEIRO
   NÚMERO dizem por que o solto não serve. Mordidas: V1d' (só o alto-falante
   trocado) e V1f (o `aba02.py` de `b791d234`) dão **rc=1** em `sinal-sumiu`; o
   mesmo arquivo com o sinal solto, V1g, dá rc=0. Veredito e contagem não mudam.
2. **A condição da ressalva** nas duas notas: «com o HIDAPI do SDL desligado» na
   sonda, e «com a dica em 0» nas nove; na do giroscópio, também o controle que
   a própria entrega mediu, a 2.32.10 do scout sem a variável entregando 145.
   Vereditos intactos. `specs.html` e LEIA-PRIMEIRO regerados, com `--check`,
   `--leia-primeiro` e o `check_paridade_transporte.py` inteiro em rc=0.

### Réguas vizinhas

Os 151 arquivos de `tests/unit` que citam algum arquivo mudado, em seis lotes em
primeiro plano, na branch corrigida: 483, 417, 499, 496 (mais 2 xfailed), 477
(mais 4 skipped) e 348 passed. Nenhum vermelho. E também:
`check_paridade_gtk_html.py`, `check_ate_onde_a_prova_chegou.py`,
`validar-citacoes-de-linha.py --all` (3289 citações) e o `ruff` nos quatro
arquivos Python da sprint.

### Os portões

`bash scripts/portoes.sh`, completo, sobre `340c4246`, depois do `git add -A`:
**TODOS VERDES — 60 portões.** Esta seção entrou depois, e `acentuacao`,
`anonimato` e `referencias-docs` rodaram de novo sobre ela.

### O que fica, sem cura aqui

* **Achado 3: a docstring não tem régua** (V5). Nenhum arquivo de teste da posse
  é lugar para essa pergunta, e a sprint tem `cria: []`. Quem segura o
  comportamento é `test_a_07_a_leitura_do_steam_input_nao_varre_hidraw`.
* **A metade do microfone, no gerador.** Com só as quatro regras `sem-alvo` do
  microfone trocadas no `aba02.py` (V1e), a paridade e o
  `test_o_cartao_diz_se_o_som_tem_para_onde_ir.py` passam (48 passed). O sinal
  novo vigia a metade que faltava; a do microfone é da MIC-SEM-FONTE-01, cujas
  réguas leem a página publicada, e aqui nada foi regerado nem publicado.
* **MESA-DE-QUATRO-01, cabeçalho de 08/09:** «O giroscópio não tem linha neste
  roteiro: é a SENSORES-NO-JOGO-01». A nota de 13/09, logo abaixo, já diz como
  a bancada escreve as células. O arquivo é de outra sprint.
* **O LEIA-PRIMEIRO publica «`nota` (225 linhas)»**, item 1 acima. Medido agora:
  230 de 311 linhas.

### O que a validação não verificou

* A tela e o aparelho: nenhum piloto, nenhuma sonda, nenhuma página regerada.
* A suíte inteira, por ordem do despacho.
