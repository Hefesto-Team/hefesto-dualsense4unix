# SOM-TRAVA-NA-QUEDA-01 — o gravador que não morre (agente IMPLEMENTA)

**Árvore:** `hefesto-voo/SOM-TRAVA-NA-QUEDA-01-opus` · branch
`voo/SOM-TRAVA-NA-QUEDA-01-opus` · base `9639f1df` (= `onda/1309`) · **aparelho:
não usei, e servidor de som também não.** Tudo aqui é dublê de processo em
Python. O ensaio isolado do §V (opcional) não foi feito. A rota seguida é a do
§D, §I e §V da sprint.

## O que mudou

**`integrations/filho_de_som.py` (novo) — o dono único.**

- `morrer_com_o_pai()`: o `PR_SET_PDEATHSIG` que morava em `nivel_do_microfone`.
  O `prctl` da libc é resolvido uma vez, no pai, e o filho só chama. Assim não
  há `dlopen` entre o `fork` e o `exec`.
- `lancar_leitor(argv)`: o `Popen` de leitor de som (`stdout=PIPE`,
  `stderr=DEVNULL`, `preexec_fn=morrer_com_o_pai`).
- `derrubar_leitor_de_pipe(proc, *, leitor, junta_s, espera_s)`: faz TERM →
  `join` da thread que lê → fecha o `stdout` **só se o leitor já parou** →
  `wait` → KILL e `wait` → `join` de novo → só então fecha o `stdout`. Devolve
  `ComoMorreu` (código, ms, se insistiu), que vai para o diário. Aceita dublê
  sem `terminate`, `wait` ou `stdout`.

**`integrations/alto_falante_bt.py`**

- `fonte_do_monitor_do_no`: lança por `lancar_leitor`, com PDEATHSIG. No ramo
  sem `stdout`, colhe o processo e devolve `(None, None, motivo)`.
- `PonteDeSomPorRadio.descer`: chama `derrubar_leitor_de_pipe(gravador,
  leitor=self._thread, junta_s=esperar_s)`, registra `som_radio_gravador_colhido`
  e guarda `como_morreu_o_gravador`. Sem gravador, faz o `join` de sempre.
- Import tardio, dentro das duas funções. As âncoras do mapa (`:276`, `:501`,
  `:605`) e a de `ensaios.csv` (`:1516`) ficam acima e não andaram.

**`daemon/subsystems/alto_falante.py`**

- `AltoFalanteSubsystem.stop`: para a reconciliação e faz `join`. Depois desce
  as pontes, juntas (`asyncio.gather` de `to_thread(ponte.descer)`), e **só
  então** chama `gerenciador.parar()`. Antes a ordem era a inversa: os nós saíam
  primeiro.
- `_casar_as_pontes`: a fonte sem `stdout` que ainda devolver processo é colhida
  ali. A ponte que não sobe é colhida pelo próprio `descer`. Um comentário pina
  a ordem da queda (pontes antes de `gerenciador.reconciliar`), e a R3 também.

**`integrations/canal_do_microfone.py`**

- `_lancar_processo` passa a chamar `lancar_leitor`.
- `_Alimentador.parar` usa o dono único, com `junta_s=0,5 s`
  (`_JUNTA_DO_BOMBEADOR_S`) e `espera_s=2 s`. O import de `contextlib` saiu.

**`integrations/nivel_do_microfone.py`**

- `_morrer_com_o_pai` é o do dono, reexportado pelo import do topo. A `def` e o
  `import signal` saíram. O `abrir_fluxo` segue com
  `preexec_fn=_morrer_com_o_pai`, como manda o §I.6.

**Um fato medido nesta sprint, e ele muda como se usa o dono:** o PDEATHSIG é
da **thread** que lançou, não do processo. Um dublê ocioso lançado de uma
thread curta, com o `prctl`, morreu com rc −9 meio segundo depois de a thread
terminar. Sem o `prctl`, continuou vivo. Os dois filhos de vida longa nascem
das threads de reconciliação (`hefesto-som-sup` e `hefesto-btmic-sup`), que
vivem tanto quanto eles. A consequência está no cabeçalho do dono: no `stop`,
quando a `hefesto-som-sup` termina, o `pw-record` já leva SIGKILL antes do
`descer`, e o diário vai dizer `SIGKILL` nesse caminho. Os nós continuam saindo
por último.

## Qual mordida prova

Réguas em `tests/unit/test_o_gravador_da_ponte_morre_antes_do_no.py`. A ponte é
a de verdade, com o laço de verdade. Só o codificador Opus e o hidraw são dublês:
o hidraw é um cano com a ponta de leitura fechada, e a escrita recusada tira o
laço como na queda. O gravador é um `python -c` com TERM bloqueado, SIGPIPE no
padrão e escrevendo até `wchan == anon_pipe_write`.

**Verde, com a cura:**

```
test_o_gravador_da_ponte_morre_antes_do_no.py      10 passed in 1.64s
test_o_medidor_de_som_nao_vaza_orfao.py             2 passed
lote vizinho 1 (ponte, subsystem, mesa de quatro, nó, medidor)   243 passed in 12.95s
lote vizinho 2 (canal e microfone)                                189 passed in 14.99s
som_radio_gravador_colhido codigo=-13 por=SIGPIPE ms=1.1          (R1, R3, R4 na queda)
som_radio_gravador_colhido codigo=-9  por=SIGKILL ms=1001.2 insistiu=True   (R2)
som_radio_gravador_colhido codigo=-15 por=SIGTERM ms=1.1          (R4 tocando)
```

**As sete mordidas.** Em cada uma a cura foi arrancada no produto, as réguas
rodaram, e a cura voltou por `git checkout` do arquivo, com `git diff` vazio.
Nenhum dublê ficou vivo depois de nenhuma corrida.

| mordida | o que se arrancou | o que reprovou |
| --- | --- | --- |
| M1 | `descer` de antes (só `terminate`) | 6 failed: R1 `o gravador … continua vivo depois do descer, com wchan='anon_pipe_write'`; R2; R3; R4 `[na_queda]` e `[tocando]`; a ponte que não sobe |
| M2 | o `kill` em `derrubar_leitor_de_pipe` | 1 failed: R2 `o teimoso … sobreviveu ao descer` |
| M3 | `gerenciador.reconciliar` antes de `_casar_as_pontes` em `_reconciliar` | 1 failed: R3 `o nó saiu com o gravador da ponte ainda vivo` |
| M4 | `stop` com `gerenciador.parar()` antes das pontes | 2 failed: R4 `[na_queda]` e `[tocando]` |
| M5 | o `preexec_fn` de `lancar_leitor` | 2 failed: R5 `[gravador]` e `[alimentador]`, `o filho … SOBREVIVEU ao SIGKILL do pai, agora com ppid 1` |
| M6 | `_Alimentador.parar` de antes | 1 failed: R6 `fechar o canal levou 2001 ms com o bombeador já morto` |
| M7 | o ramo sem `stdout` sem colher | 1 failed: `o gravador sem stdout ficou vivo` |

Na M1, a R4 `[tocando]` reprovou com o gravador **são**: ele morre no TERM, mas
o `descer` de antes não dá `wait`, e o nó sai sem que alguém o tenha colhido. É
leitura, e o instante exato não foi medido.

Portões: `bash scripts/portoes.sh` completo, depois do `git add -A` desta
entrega. O resultado está no fim desta seção de fechamento, no commit.
`scripts/validar-citacoes-de-linha.py --all`: `OK: 3288 citação(ões) … em 21
documento(s) e 9 planilha(s)`. Nenhuma célula de planilha andou.

## O que NÃO verifiquei

- **Nada no aparelho, nada no servidor de som.** Não rodei `pw-record` real,
  `parec` real nem PipeWire, e o ensaio isolado não foi feito. Não sei se a cura
  impede o travamento da sessão dela: isso é a §B, na MESA-DE-QUATRO-01.
- **O elo do wireplumber** (§D.6): não medido.
- **O `parec` real com o cano cheio:** o dublê do alimentador é o do
  `pw-record`, com TERM bloqueado, que é o pior caso. Não medi se o `parec`
  ignora TERM parado no `write`.
- **O PDEATHSIG disparado pela saída da thread dentro do daemon:** medido só
  com um dublê num processo avulso, não no `stop` do daemon.
- **A chave do mapa para o canal do cabo:** nenhuma linha de
  `docs/data/mapa-controles.csv` cita `canal_do_microfone.py`, e não inventei
  chave.
- **A suíte inteira**, que não é minha. Rodei a régua nova, a do medidor e os
  dois lotes vizinhos acima.

## O que sobrou para o próximo

- **VALIDA/CORRIGE:** refazer as sete mordidas. Se quiser, fazer o ensaio isolado
  (o roteiro do produto do estudo, contra o código curado, na instância isolada).
- **MESA-DE-QUATRO-01:** a §B inteira, com a cura instalada. São três quedas com
  o PS segurado, `timeout 3 pactl info` em laço, e a Steam com janela, com e sem
  o microfone do controle.
- **`nivel_do_microfone._FluxoParec.parar`** segue com a ordem própria
  (`terminate` → `wait(2 s)` → `kill`), porque o §I.6 manda só trocar o import.
  Ele é o terceiro filho, e passar ao dono único é uma troca de três linhas numa
  sprint futura.
- **Quem lançar leitor de som fora das threads de reconciliação** precisa ler o
  cabeçalho de `filho_de_som.py`: numa thread curta, o PDEATHSIG mata o filho
  logo depois de nascer.
- **Citação histórica que andou:** `docs/process/2026-09-10-AS-FRASES-QUE-MENTEM-a-tela-medida-contra-o-produto.md`
  cita `_sink_proprio_vivo` numa linha de `alto_falante_bt.py` que desceu cerca
  de 45 linhas. É registro de `docs/process/`, fora do oráculo e fora da posse,
  e não foi reapontado.
