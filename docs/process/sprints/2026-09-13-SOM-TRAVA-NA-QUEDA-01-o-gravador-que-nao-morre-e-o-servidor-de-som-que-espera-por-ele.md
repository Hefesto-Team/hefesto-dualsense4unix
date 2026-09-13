---
sprint: SOM-TRAVA-NA-QUEDA-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  SOM-TRAVA-NA-QUEDA-01:
    # PROVISÓRIA — o ESTUDO escreve a posse real antes de qualquer implementação.
    - src/hefesto_dualsense4unix/integrations/alto_falante_bt.py
    - src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py
    - src/hefesto_dualsense4unix/integrations/dualsense_bt_audio.py
    - src/hefesto_dualsense4unix/daemon/subsystems/bt_mic.py
    - docs/process/sprints/2026-09-13-SOM-TRAVA-NA-QUEDA-01-o-gravador-que-nao-morre-e-o-servidor-de-som-que-espera-por-ele.md
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/daemon/lifecycle.py
  - src/hefesto_dualsense4unix/interface/
  - docs/data/
---

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

## §E — O que quem coordena mediu (13/09, só leitura na máquina dela)

1. **Duas vezes no mesmo dia, a mesma sequência**, lida no diário do daemon e do
   `pipewire-pulse`:

   | | madrugada | tarde |
   | --- | --- | --- |
   | o nó do controle no rádio some (`bt_mic_hidraw_perdido`, erro de E/S) | 01:53:43 | 13:42:00 |
   | o PS segurado, no mesmo instante (`ps_solo_ignorado_hold_longo`) | 5,0 s | 9,2 s |
   | a ponte do alto-falante desce e o nó sai (`som_ponte_derrubada`, `som_sink_removido`) | 01:53:44 | 13:42:02 |
   | o primeiro `pactl` sem resposta | 01:53:54 | 13:42:07 |
   | o servidor de som parado até o reinício dos três serviços | 47 min | 3 h 44 min |

   À tarde o `pipewire-pulse` logou `mod.pipe-tunnel: out of buffers: Pipe
   quebrado` às 13:42:01. A Steam ficou sem janela, com um `wpctl` filho preso
   desde 13:42:02, e o COSMIC ficou com cinco `wpctl set-default` presos de
   quando ela tentou trocar a saída. O reinício de `pipewire`, `pipewire-pulse` e
   `wireplumber` às 17:26 curou em um segundo, e a Steam voltou sozinha.
2. **A cura instalada não impede o travamento.** A
   [MIC-O-CANAL-DO-OUTRO-01](2026-09-13-MIC-O-CANAL-DO-OUTRO-01-o-no-orfao-o-pactl-que-trava-e-a-voz-picotada.md)
   (Defeito 3, feita, no `dev` instalado) deu recuo ao `pactl`: o daemon para de
   perguntar ao servidor mudo. A causa ficou «não medida» lá, e o travamento
   voltou com ela instalada.
3. **O suspeito, vivo na máquina às 17:29:** um `pw-record
   --target=hefesto_som_<hex6>.monitor`, filho do daemon, nascido às 05:29:54 com
   a ponte do rádio, que sobreviveu à ponte derrubada das 13:42:02. Ele dorme em
   `anon_pipe_write` (escrevendo num pipe cheio), o daemon ainda segura a ponta de
   leitura desse pipe, e ele tem `signalfd`.
4. **O fonte.** `PonteDeSomPorRadio.descer` (`integrations/alto_falante_bt.py`)
   só chama `gravador.terminate()`: não fecha o `stdout`, não espera e não mata. O
   laço que lia o pipe já parou. `fonte_do_monitor_do_no`, no mesmo arquivo, diz
   na docstring que um `pw-record` órfão continua lendo o monitor depois de a
   ponte cair. Em `_casar_as_pontes` (`daemon/subsystems/alto_falante.py`) a
   ponte desce e, no mesmo segundo, o nó é descarregado.
5. **Hipótese, NÃO medida:** o `pw-record` recebe o SIGTERM pelo `signalfd`, mas o
   laço dele está parado no `write` do pipe cheio e nunca volta para ler o sinal
   nem para responder ao servidor. Quando o nó que ele grava é descarregado, o
   servidor espera a resposta de um cliente que não responde, e para de atender
   todos. A outra metade possível é o `module-pipe-source` do microfone, que logou
   `Pipe quebrado` um segundo antes.

## §D — O que está decidido

1. **O servidor de som dela não é bancada.** Todo experimento roda numa instância
   isolada do PipeWire, com diretório de execução próprio no rascunho, e cada
   comando confere antes que não fala com a sessão dela. Travar o som dela de novo
   para medir é o defeito que a sprint existe para matar.
2. **Quem sobe um processo derruba o processo.** A cura cobre todo filho do daemon
   que conversa com o servidor de som (gravador, `pactl`, o que o estudo achar),
   não só este `pw-record`.
3. **O filho morre antes de o nó sair.** A ordem de desligar é parte da cura, e a
   régua a confere.
4. Nada de botão novo, nada de frase na tela: o defeito é do daemon.

## §2 — As perguntas do ESTUDO, nesta ordem

1. **Reproduzir fora da sessão dela.** Na instância isolada: um nó igual ao do
   Hefesto, um `pw-record` lendo o monitor com o `stdout` num pipe que ninguém lê
   (cheio), SIGTERM nele, e o nó descarregado. O `pw-record` morre? O `pactl info`
   da instância continua respondendo? O mesmo com o pipe fechado antes do SIGTERM,
   e com o gravador morto antes do descarregamento. Tempos medidos.
2. **Separar o microfone.** O `module-pipe-source` do microfone com a ponta de
   escrita fechada («Pipe quebrado») e descarregado: trava sozinho, ou só junto do
   gravador?
3. **O inventário.** Todo processo que o daemon abre contra o servidor de som, com
   o endereço de quem sobe e de quem derruba, e se a derrubada pode deixar um
   cliente preso. Inclua o caminho da morte do daemon, que o `lifecycle.py` cita
   (cada ponte segura um fd de hidraw e um `pw-record`).
4. **A cura, a posse real e as réguas.** A ordem de desligar, o que fecha o pipe,
   quanto espera e quando mata; a posse arquivo por arquivo, dizendo se precisa do
   `lifecycle.py` (hoje da MODO-DE-CONEXAO-01); uma régua com um processo dublê que
   ignora SIGTERM preso num `write`, e a mordida de cada uma.

## §B — O que só o aparelho responde (vai para a MESA-DE-QUATRO-01)

Com a cura instalada: um DualSense no rádio com o «Alto-falante do Controle N» de
pé e um jogo tocando som. Desligar o controle segurando o PS, três vezes, com
`timeout 3 pactl info` em laço noutro terminal: o servidor responde em todas? A
Steam continua com janela? E o mesmo com o microfone do controle ligado.

## §0 — O processo

ESTUDO (só leitura na árvore, experimento só na instância isolada) → quem coordena
escreve aqui a rota e a posse → IMPLEMENTA → VALIDA/CORRIGE.
