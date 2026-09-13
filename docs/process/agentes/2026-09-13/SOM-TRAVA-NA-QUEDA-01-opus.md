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
thread curta, com o `prctl`, morreu com rc −9 2,1 ms depois de a thread
terminar (tempo remedido na validação). Sem o `prctl`, continuou vivo. Os dois filhos de vida longa nascem
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

Portões: `bash scripts/portoes.sh` completo, depois do `git add -A`. A primeira
corrida deu `REPROVOU: 1 vermelho(s) de 60 -> acentuacao`, com duas grafias de
«código» sem acento, uma na docstring de `ComoMorreu` e outra na chave do
diário do alimentador. Corrigidas em `14c74427`. A segunda corrida deu
`TODOS VERDES — 60 portões.` em 380 s.
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

## O que a validação refez e corrigiu

Agente VALIDA/CORRIGE, mesma árvore e mesma branch. Commits `e29f552e`
(docstring) e `9d8b002e` (réguas), mais este registro.

**As travas.** O servidor de som dela teve os mesmos quatro PIDs do começo ao
fim — `pipewire` 1939658 e 1939660, `wireplumber` 1939659, `pipewire-pulse`
1939661, nascidos às 17:26:32 —, com `timeout 3 pactl info` em rc=0 nas duas
pontas. Foi a única pergunta à sessão dela. Réguas, lotes vizinhos e portões
rodaram com `PULSE_SERVER`, `PIPEWIRE_REMOTE`, `PIPEWIRE_RUNTIME_DIR`,
`PULSE_RUNTIME_PATH`, `PULSE_CLIENTCONFIG` (`autospawn = no`) e
`DBUS_SESSION_BUS_ADDRESS` apontados para o rascunho, com uma guarda que sai se
o desvio não pegou. Nenhum dublê vivo e nenhum órfão no fim.

**O achado: quatro mordidas passavam com as réguas todas verdes**, e as quatro
arrancavam exatamente o que a rota manda conferir. O código estava certo;
nenhuma régua o pinava.

| mordida | o que se arrancou | antes | depois |
| --- | --- | --- | --- |
| M8 | `derrubar_leitor_de_pipe` fecha o `stdout` sem olhar o leitor, no primeiro fechamento | 12 passed | R7 reprova: `o descer fechou o stdout do gravador com o laço ainda vivo` |
| M8b | o mesmo, no último fechamento | 12 passed | R7 reprova, a mesma frase |
| M9 | `ponte.descer()` direto no `stop`, no lugar do `gather` de `to_thread` | 12 passed | R8 reprova: `o event loop ficou 1011 ms sem bater` |
| M11 | o `derrubar_leitor_de_pipe` do ramo `if fonte is None` de `_casar_as_pontes` | 12 passed | R9 reprova: `a fonte voltou sem PCM e o processo dela ficou vivo` |

As três réguas novas moram no mesmo arquivo. A R7 prende o laço no `write` de
um hidraw de cano cheio, e com isso o leitor fica vivo durante o `descer`: o
gravador tem de morrer pelo KILL com o cano ainda aberto, e o `descer` devolve
`False`. A R8 bate a cada 10 ms no event loop enquanto o `stop` desce um
teimoso que leva 1 s. A R9 dá ao subsystem uma fonte que devolve
`(None, processo, motivo)`.

**As outras mordidas, refeitas.** Onze sabotagens por troca exata de texto, com
a cura devolvida por `git checkout --`, `git diff` conferido vazio e nenhum
sobrevivente depois:

- M1 a M7 são as mesmas da tabela das sete mordidas, em «Qual mordida prova»,
  e reprovaram igual. Com as réguas
  novas, a M1 derruba 8 e a M2 derruba 3, porque R7 e R8 também dependem do KILL.
- M10, o `descer` tirado do ramo da ponte que não sobe: reprova
  `test_a_ponte_que_nao_sobe_colhe_o_gravador`.
- M12, o nome `_morrer_com_o_pai` tirado de `nivel_do_microfone` sem quebrar o
  `abrir_fluxo`: reprova o medidor com `AttributeError`.
- M13a, `fonte_do_monitor_do_no` voltando ao `Popen` cru: reprova R5
  `[gravador]`. M13b, `_lancar_processo` voltando ao `Popen` cru: reprova R5
  `[alimentador]`.

A régua com as nove verdes rodou três vezes seguidas, sem oscilar.

**Conferido lendo, sem mudança.**

- **Quem lança.** `fonte_do_monitor_do_no` só é chamada por `_casar_as_pontes`,
  que só roda na `hefesto-som-sup`. O alimentador com `fonte` só nasce de
  `BtMicSubsystem._abrir_os_canais_do_cabo`, na `hefesto-btmic-sup`. A
  `PonteMicBluetooth` abre o canal sem `fonte`, e portanto sem processo.
  Nenhum chamador de hoje lança leitor de uma thread curta.
- **O PDEATHSIG por thread, remedido.** Pelo dono, numa thread curta, o dublê
  morreu com rc −9 2,1 ms depois de a thread terminar. Sem o `prctl`, ficou
  vivo 2 s. Lançado da thread principal, ficou vivo.
- **A tela.** As páginas publicadas têm 276 `<button>` e 354 `data-gesto` na
  base e na ponta, e nenhum arquivo de tela entrou no diff. O `ComoMorreu` só
  vai para o `logger`.
- **A posse.** Os oito arquivos do diff cabem em `posse`/`cria`, na entrega e
  na sprint.
- **O oráculo.** `scripts/validar-citacoes-de-linha.py --all` dá
  `OK: 3288 citação(ões)`.

**Corrigido.** A docstring de `AltoFalanteSubsystem.stop` dizia que a ordem de
antes era «a mesma ordem da queda». Não era: na queda a ponte já descia antes
do nó. O comum às duas era o nó sair com o gravador vivo, e é isso que o texto
diz agora (`e29f552e`). Nesta entrega, «meio segundo» virou os 2,1 ms medidos.

**Os vizinhos.** Os 76 arquivos de `tests/unit` que citam os arquivos da posse
rodaram em seis lotes: 1515 passaram e 1 reprovou. O que reprovou foi
`test_o_no_de_som_nao_nasce_sumidouro.py::test_a_guarda_recusa_a_escrita_e_deixa_a_leitura_passar`,
que lê `pactl list sinks short` do servidor de verdade. Com o som desviado, ele
reprova igual na base `9639f1df` extraída no rascunho: quem reprova é o desvio,
não a branch. Não o rodei contra a sessão dela.

**Portões.** `bash scripts/portoes.sh` completo, depois do `git add -A`, sobre
`caa8a82f` e com o som desviado: `TODOS VERDES — 60 portões.` em 380 s. Nenhuma
célula de planilha andou.
