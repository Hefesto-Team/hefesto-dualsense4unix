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
