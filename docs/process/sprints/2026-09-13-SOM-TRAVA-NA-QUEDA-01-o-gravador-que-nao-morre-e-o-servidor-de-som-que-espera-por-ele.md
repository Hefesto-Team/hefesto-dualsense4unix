---
sprint: SOM-TRAVA-NA-QUEDA-01
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  SOM-TRAVA-NA-QUEDA-01:
    - src/hefesto_dualsense4unix/integrations/alto_falante_bt.py
    - src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py
    - src/hefesto_dualsense4unix/integrations/canal_do_microfone.py
    - src/hefesto_dualsense4unix/integrations/nivel_do_microfone.py
    - tests/unit/test_o_medidor_de_som_nao_vaza_orfao.py
    - docs/process/sprints/2026-09-13-SOM-TRAVA-NA-QUEDA-01-o-gravador-que-nao-morre-e-o-servidor-de-som-que-espera-por-ele.md
cria:
  - src/hefesto_dualsense4unix/integrations/filho_de_som.py
  - tests/unit/test_o_gravador_da_ponte_morre_antes_do_no.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/daemon/lifecycle.py
  - src/hefesto_dualsense4unix/daemon/connection.py
  - src/hefesto_dualsense4unix/integrations/dualsense_bt_audio.py
  - src/hefesto_dualsense4unix/daemon/subsystems/bt_mic.py
  - src/hefesto_dualsense4unix/interface/
  - docs/data/
  - tests/conftest.py
---

> **ESTADO 2026-09-13: feita** — o `pw-record` da ponte deixou de sobreviver à queda. `integrations/filho_de_som.py` é o dono único do `PR_SET_PDEATHSIG` e da ordem que derruba um leitor de cano cheio (TERM, `join`, `stdout` fechado só com o leitor parado, `wait`, KILL), e os três filhos de som passaram a usá-lo: a ponte colhe o gravador no `descer`, o `stop` desce as pontes antes de tirar os nós, e o alimentador do cabo fecha em milissegundos com o bombeador morto. Seis réguas (R1–R6) e duas portas do órfão, com dublê de processo e a mordida de cada uma medida. Sem aparelho e sem servidor de som: a §B fica para a MESA-DE-QUATRO-01. A entrega está em `docs/process/agentes/2026-09-13/SOM-TRAVA-NA-QUEDA-01-opus.md`.

# SOM-TRAVA-NA-QUEDA-01 — o gravador que não morre, e o servidor de som que espera por ele

## A palavra dela — 13/09/2026, 17h

> *"a steam e os jogos dela voltaram a ficarem invisiveis e o som voltou a não sair no pc."* <!-- noqa-acento: citação literal dela -->
>
> *"nenhuma chance de ser nosssas configs do hefesto na aba controles na parte do som e microfone? algum bug que causa isso?"* <!-- noqa-acento: citação literal dela -->

Chegou com a validação da
[MODO-DE-CONEXAO-01](2026-09-13-MODO-DE-CONEXAO-01-o-degrau-xbox-que-diz-aplicado-e-nao-vale-e-o-texto-que-e-da-mascara.md)
em voo, e segue o processo dela (§0 do
[índice](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)): sprint escrita antes de
qualquer agente, no máximo três agentes.

## §E — O que se mediu

### Na máquina dela (quem coordena, 13/09, só leitura)

1. **Duas vezes no mesmo dia, a mesma sequência**, lida no diário do daemon e do
   `pipewire-pulse`:

   | | madrugada | tarde |
   | --- | --- | --- |
   | o nó do controle no rádio some (`bt_mic_hidraw_perdido`, erro de E/S) | 01:53:43 | 13:42:00 |
   | o PS segurado, no mesmo instante (`ps_solo_ignorado_hold_longo`) | 5,0 s | 9,2 s |
   | a ponte do alto-falante desce e o nó sai (`som_ponte_derrubada`, `som_sink_removido`) | 01:53:44 | 13:42:02 |
   | o primeiro `pactl` sem resposta | 01:53:54 | 13:42:07 |
   | o servidor de som parado até o reinício dos três serviços | 47 min | 3 h 44 min |

   A Steam ficou sem janela, com um `wpctl` filho preso desde 13:42:02, e o COSMIC
   ficou com cinco `wpctl set-default` presos de quando ela tentou trocar a saída.
   O reinício de `pipewire`, `pipewire-pulse` e `wireplumber` às 17:26 curou em um
   segundo, e a Steam voltou sozinha.
2. **A cura instalada não impede o travamento.** A
   [MIC-O-CANAL-DO-OUTRO-01](2026-09-13-MIC-O-CANAL-DO-OUTRO-01-o-no-orfao-o-pactl-que-trava-e-a-voz-picotada.md)
   (Defeito 3) deu recuo ao `pactl`, e o travamento voltou com ela instalada.
3. **O órfão vivo:** um `pw-record --target=hefesto_som_<hex6>.monitor`, filho do
   daemon, nascido às 05:29:54 com a ponte do rádio, que sobreviveu à ponte
   derrubada das 13:42:02. Ele dorme em `anon_pipe_write`, e o daemon ainda segura a
   ponta de leitura do pipe dele.

### No estudo (instância isolada do PipeWire 1.6.8, sem wireplumber)

O estudo inteiro, com a matriz de cenários, os roteiros da instância isolada, dos
cenários, do produto e da régua prévia, e os resultados crus, fica no rascunho de
quem coordena, na pasta da sprint. A sessão dela ficou intacta do
começo ao fim: os mesmos três PIDs e o canário `pactl info` com rc=0.

4. **O gravador não morre — medido.** O `pw-record` tem uma thread só, recebe o
   SIGTERM por `signalfd`, e o laço está no `write` do pipe que ninguém lê (enche
   em cerca de 0,34 s). O SIGTERM fica pendente para sempre. A
   `PonteDeSomPorRadio` da árvore faz igual na instância: `descer()` volta em 0 ms
   com o gravador vivo. **Fechar a ponta de leitura** o derruba por SIGPIPE em
   1,1 ms; um teimoso cai por KILL; sem `wait` fica zumbi.
5. **O servidor sozinho não trava — medido.** Em 18 cenários (o nó descarregado
   debaixo do gravador preso, o microfone, o nível, as duas linhas do tempo do
   diário), `pactl info` e `pw-cli info 0` responderam sempre em 2 a 7 ms. **Fato
   substituído:** a hipótese que este §E dizia, «o servidor espera um cliente que
   não responde e para de atender todos», não se sustenta no servidor sozinho.
6. **Trava quem MUDA um parâmetro do nó do gravador preso — medido.** `pw-cli set`,
   `pactl set-source-output-volume` e `wpctl set-volume` esperam (rc=124 em 3 s,
   contra 3 ms com o gravador são), e voltam no milissegundo em que o órfão morre.
7. **O diário amarra o resto, sem fechar a causa.** De oito quedas com gravador
   preso em 12 e 13/09, quatro travaram: o órfão parece necessário e não basta. Os
   três travamentos longos só acabaram quando o órfão perdeu a conexão (a morte do
   daemon em 12/09; o reinício do `pipewire` duas vezes em 13/09; reiniciar só o
   pulse não bastou). Em 12/09 16:35:18 o wireplumber registrou `link failed: item
   deactivated before format was set`. **A leitura mais provável, não medida:** o
   wireplumber mexe no stream órfão quando o alvo some, fica esperando por ele, e
   arrasta a sessão.
8. **O microfone não trava** sozinho nem junto do gravador, e a linha `Pipe
   quebrado` aparece no diário sem travamento: não é marcador.
9. **O inventário dos filhos de som do daemon:** o `pw-record` da ponte (só
   `terminate`, sem `wait`, sem fechar o pipe, sem `PR_SET_PDEATHSIG`); o `parec` do
   medidor de nível (já certo: `terminate` → `wait` → `kill`, com PDEATHSIG); o
   `parec` do canal do cabo (`terminate` → `wait(2 s)` → `kill`, sem PDEATHSIG, e
   preso se o bombeador morrer). Os `pactl` são `run` com prazo e colhidos.
10. **As quatro portas do órfão:** a queda; a ponte que não sobe
    (`fonte_do_monitor_do_no` já lançou o gravador e `subir()` falha); a fonte sem
    `stdout` (o processo nunca é derrubado); e a morte do daemon, onde
    `AltoFalanteSubsystem.stop` tira os nós ANTES de descer as pontes.

## §D — O que está decidido

1. **O servidor de som dela não é bancada.** Todo experimento roda numa instância
   isolada do PipeWire, e cada comando confere antes que não fala com a sessão
   dela.
2. **Quem sobe um processo derruba o processo, e a cura cobre os três filhos de
   som**, não só o `pw-record`.
3. **O filho morre antes de o nó sair**, na queda e no desligamento, e a régua
   confere a ordem.
4. Nada de botão novo, nada de frase na tela: o defeito é do daemon, e o jeito
   como o filho morreu vai só para o diário.
5. **Um dono só (quem coordena, 13/09):** `integrations/filho_de_som.py` guarda o
   `PR_SET_PDEATHSIG` e o «derrubar um leitor de pipe». Os três filhos passam a
   usá-lo. O nome `_morrer_com_o_pai` continua em `nivel_do_microfone`,
   reexportado, porque uma régua o chama por lá.
6. **O elo do wireplumber fica para a bancada**, não para o código: a cura tira o
   órfão, que o diário mostra ser necessário ao travamento.

## §I — A implementação, por símbolo

1. **`integrations/filho_de_som.py` (novo):** lançar com `PR_SET_PDEATHSIG` e
   derrubar um processo leitor de pipe nesta ordem: `terminate`; se quem lê já
   parou, fechar o `stdout`; `wait` com prazo; `kill` e `wait` se o prazo passar.
   Devolve como morreu (código de saída e milissegundos) para o diário.
2. **`PonteDeSomPorRadio.descer`** (`integrations/alto_falante_bt.py`), a ordem
   medida: `parar.set()` → `terminate` do gravador → `join` da thread com
   `esperar_s` → se o laço já saiu, fechar o `stdout` (se ainda vive, NÃO fechar:
   o fd seria reaproveitado debaixo do `read` dele, o cuidado que a docstring já
   registra para o hidraw) → `wait` → `kill` → `join` de novo → só então fechar o
   `stdout`. Registrar no diário como o gravador morreu.
3. **`fonte_do_monitor_do_no`:** lançar pelo dono único (com PDEATHSIG) e, no ramo
   sem `stdout`, derrubar o processo antes de devolver.
4. **`AltoFalanteSubsystem`** (`daemon/subsystems/alto_falante.py`): no `stop`,
   parar a reconciliação, descer as pontes (fora do event loop, colhendo os
   gravadores) e **só então** `gerenciador.parar()`; em `_casar_as_pontes`, o ramo
   em que `subir()` falha e o da fonte sem `stdout` também derrubam o processo.
   A ordem de hoje na queda (pontes antes de `gerenciador.reconciliar`) fica, e a
   régua a pina.
5. **`integrations/canal_do_microfone.py`:** `_lancar_processo` pelo dono único;
   `_Alimentador.parar` na ordem do §I.1, sem esperar 2 s quando o bombeador já
   morreu.
6. **`integrations/nivel_do_microfone.py`:** só o import do dono único, com
   `_morrer_com_o_pai` reexportado.
7. Nenhum `import` novo no topo dos módulos citados por linha nas planilhas:
   import tardio dentro da função, como os módulos já fazem. Conferir com
   `scripts/validar-citacoes-de-linha.py --all`.

## §V — A prova

**As réguas, todas com dublê de processo e sem servidor de som**, em
`tests/unit/test_o_gravador_da_ponte_morre_antes_do_no.py`. O dublê é Python e
reproduz o `pw-record` medido: SIGTERM bloqueado, SIGPIPE no padrão, escrevendo até
o pipe encher, com espera por `/proc/<pid>/wchan == anon_pipe_write`. O molde que
já morde contra a árvore é o roteiro da régua prévia do estudo.

| régua | afirma | mordida |
| --- | --- | --- |
| R1 | o gravador preso morre no `descer`, por SIGPIPE, em até 200 ms | o `descer` de hoje deixa o dublê vivo |
| R2 | o teimoso (ignora SIGPIPE) morre por KILL em até 1,5 s | tirar o `kill` da cura deixa vivo |
| R3 | na queda, o gravador já foi colhido quando o nó sai | trocar a ordem entre pontes e `gerenciador.reconciliar` |
| R4 | no `stop`, o gravador é colhido antes de `gerenciador.parar()` | o `stop` de hoje reprova |
| R5 | o filho ocioso morre com o pai morto por SIGKILL | tirar o PDEATHSIG deixa o filho com `ppid 1` |
| R6 | o alimentador do cabo com o bombeador morto é colhido em menos de 100 ms | a ordem de hoje leva 2 s |

**O ensaio fora da suíte (recomendado, não obrigatório):** o roteiro do produto do
estudo, contra o código curado, na instância isolada do estudo, com as mesmas
travas; o gravador tem de ser colhido antes de o nó sair e nenhum cliente fica
esperando. Nunca contra a sessão dela.

`tests/unit/test_o_medidor_de_som_nao_vaza_orfao.py` continua verde. Os portões até
todos verdes.

## §B — O que só o aparelho responde (vai para a MESA-DE-QUATRO-01)

Com a cura instalada: um DualSense no rádio com o «Alto-falante do Controle N» de
pé e um jogo tocando som. Desligar o controle segurando o PS, três vezes, com
`timeout 3 pactl info` em laço noutro terminal: o servidor responde em todas? A
Steam continua com janela? E o mesmo com o microfone do controle ligado.

**Se travar de novo ANTES de a cura estar instalada** (gesto de quem coordena, na
máquina dela): sem reiniciar serviço nenhum, achar o filho do daemon em
`anon_pipe_write` (`ps -o pid,wchan:22,cmd --ppid <pid do daemon>`), matá-lo por
PID conferido e cronometrar `timeout 3 pactl info`. Voltar no mesmo segundo prova
que o órfão segura a sessão; o `journalctl --user -u wireplumber` diz se o elo é o
wireplumber.

## §0 — O processo

ESTUDO (feito, 13/09) → quem coordena escreveu a rota e a posse (§D, §I, §V) →
IMPLEMENTA → VALIDA/CORRIGE.
