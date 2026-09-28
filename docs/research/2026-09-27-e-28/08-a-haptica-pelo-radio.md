# A háptica pelo rádio: o que sumiu no PRAGMATA e quem joga

Por que a vibração do PRAGMATA não chegou ao controle pelo Bluetooth na sessão de 26/09/2026, e a cura do portão «quem joga», escrita e conferida a partir da noite de 26/09/2026.

Graus usados abaixo: **medido** (comando com saída), **lido** (código, commit ou diário), **inferido** (conclusão sem medida direta).

## O sintoma

Na sessão de 26/09, das 18:35:30 às 18:43:04 (um DualSense pelo rádio, máscara DualSense, GE-Proton11-7), a vibração não chegou ao controle. O diário tem **zero** `som_radio_ponte_de_pe arranjo=0x32-háptica` e **zero** `vigia_do_modo_acordou_a_volta modo=haptica` nesse intervalo (medido). Nenhuma linha dizia por quê.

A contagem diária de subidas da ponte `0x32-háptica` (medida no diário): 7 em 18/09, 2 em 19/09, 4 em 20/09, 21 em 21/09, **0 de 22 a 26/09**. Parte dos zeros é só falta de jogo: entre 21/09 e 26/09 o PRAGMATA abriu uma vez (25/09), com máscara Xbox, em que a vibração é rumble HID e não passa pelo áudio.

## O caminho pelo rádio, e onde ele é mudo

Pelo rádio o controle não tem placa de som: o Hefesto publica um endpoint de 4 canais que o jogo reconhece como DualSense, lê o monitor dele e manda os canais 3-4 ao controle no report `0x32`. São nove elos, do wrapper (`assets/hefesto-launch.sh`) e do device KS no prefixo (`src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py`) até a bomba do `0x32` (`src/hefesto_dualsense4unix/integrations/alto_falante_bt.py`, `src/hefesto_dualsense4unix/integrations/haptica_bt.py`). **Quatro deles não deixam linha no diário quando quebram**, entre eles os dois suspeitos desta queixa:

- **o jogo abrir stream no endpoint** (fora do código da casa; só `LC_ALL=C pactl list short sink-inputs` com o jogo aberto responde);
- **o portão «o jogo lê este controle»** em `_casar_as_pontes` (`src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py`): entra em háptica só com endpoint existente, endpoint tocando **e** o controle entre os que o jogo lê. Com o conjunto vazio, o código caía em «som» sem escrever nada.

**No cabo os elos do portão, do governador e da ponte não existem**: o jogo toca direto na placa USB do controle. Vibrar no cabo e não no rádio aponta para um elo exclusivo do rádio (inferido do código).

Tudo o que fica **depois** da ponte está descartado: ela não subiu nenhuma vez. Também descartados com medida: o Perfil de Desempenho (`orcamento.teto=balanceado`, nenhum controle em economia, e o único ganho do caminho de áudio é o `ganho=1.0` fixo de `haptica_bt.py`), o Proton (GE-Proton11-7 em todas as aberturas desde 17/09), um install durante o jogo (nenhum reinício entre 16:12 e 18:39:57) e a renovação do rótulo do endpoint (zero no intervalo). O device KS foi gravado às 18:35:30 com o ContainerId batendo com a âncora do endpoint.

## A causa

**Com máscara DualSense, o portão saía vazio por construção.** Ele contava só os `/dev/input/eventN` segurados por processo com `STEAM_COMPAT_DATA_PATH`, e o winebus do GE-Proton11-7 **nunca mantém aberto o evdev de um DualSense**, nem do físico nem do vpad `0df2`: fica só com o `hidraw`. Provado três vezes na conferência:

- pelo fonte do GE-Proton11-7, fora deste repositório (o winebus fecha todo evdev; os patches `0014` e `0177` fecham todo DualSense no SDL, «hidraw handles native reports»);
- pelo rastro `+hid` do próprio PRAGMATA de 17/09 (evdev do físico «ignoring», evdev do vpad «deferring», `hidraw` do vpad aberto);
- por duas leituras de `/proc/<pid>/fd` com outro jogo na mesma máscara: o `winedevice.exe` segurava os `hidraw` dos dois vpads e **nenhum** processo do jogo segurava `eventN`. A medida da cura, com o jogo aberto, repetiu: 0 `eventN` e 2 `hidraw` de vpad.

O jogo usava o vpad pelo `hidraw` naquela sessão: às 18:35:47 ele escreveu gatilho no vpad (lido no diário), e o efeito de gatilho só existe por escrita crua no hidraw (inferido).

### A explicação que caiu

A primeira síntese dizia que em 20 e 21/09 funcionava porque o jogo segurava o evdev do **físico**, e que o `849adc061` (24/09, evdev do físico nascendo `0600 root`) tirou esse sinal. **Derrubada quanto ao jogo**: o winebus fecha também o evdev do físico, e o papel do `849adc061` ficou sem prova. Em 21/09, das 01:51:05 às 01:51:46, a ponte `0x32` subiu nos **quatro** controles num jogo de um jogador. A última prova de «funcionava» é, portanto, o próprio defeito espelhado de 20/09, relatado assim: «o player 3 tava recebendo a vibração de forma espelhada». O portão **nunca discriminou numa sessão real**: em 21/09 entraram todos, em 26/09 ninguém. Quem segurava os `eventN` em 21/09 **não se sabe**.

A contraprova antiga, «em 20/09 o PRAGMATA tinha `event21/264/265` do vpad», também caiu: no `017d72d1c` a mesma docstring dizia «Um jogo com máscara **Xbox** abre esse»; o «DualSense» entrou em 25/09 (`2cd10061a`). O fato foi substituído em `src/hefesto_dualsense4unix/integrations/quem_o_jogo_le.py:67-71`.

### Nenhum sinal que o jogo deixa separa quem joga

| sinal | separa? | por quê |
|---|---|---|
| `eventN` do vpad | não aparece | o GE não o segura |
| `fd` do `hidraw` do vpad | não | o `winedevice` segura o de **todos** os vpads |
| report de saída no vpad («o ato do jogo») | não | em 21/09 o jogo escreveu gatilho em três vpads; a Steam escreve LED nos vpads antes de o jogo abrir; o uhid não diz quem escreveu |
| stream no endpoint | não | em 21/09 havia stream nos quatro |

Contar o `hidraw` curaria o caso de um controle e **devolveria o espelhado** com dois ou mais. A régua proposta na primeira síntese («um jogador, quatro vpads, o jogo escreve em um») mediria um mundo que a bancada não tem.

## A cura: quem joga é quem mexeu desde que o jogo abriu

Decisão **`D-2609-QUEM-JOGA-E-QUEM-MEXE`** (em `docs/data/decisoes-dela.csv`, por delegação), sprints `A-HAPTICA-QUEM-JOGA-01` e `A-HAPTICA-QUEM-JOGA-02`.

- **O sinal:** o controle físico que teve entrada (botão, gatilho ou eixo fora da zona morta) desde que o jogo abriu. O daemon já lê essa entrada a cada tique para mandá-la ao vpad: o laço lê a do posto, `CoopManager.forward_all` lê a de cada secundário. A marca vive em `src/hefesto_dualsense4unix/daemon/subsystems/quem_mexe.py` e reusa essa leitura. Custo medido: 0,16 µs por tique sem jogo, no máximo 1,49 µs com jogo.
- **A janela:** da abertura ao fechamento do jogo (o mesmo `pids_de_jogo` por `STEAM_COMPAT_DATA_PATH`); a marca zera nas duas pontas, e um conjunto de pids sem nada em comum com o anterior conta como outro jogo. A varredura de `/proc` custou 8 ms mais 15 ms com o jogo aberto.
- **O portão** usa `jogando = quem mexeu na partida` (`alto_falante.py:1345`, `:1616`). O vigia olha a marca viva e acorda a volta no primeiro toque.
- **O evdev não vota.** A primeira versão somava `evdev ∪ quem mexeu`; a conferência montou o mundo de 21/09 (o jogo segurando o evdev dos quatro, só o P2 mexendo) e viu os quatro entrarem. Na `-02` o evdev virou só pista na linha do portão. A interseção também foi recusada: se o detentor desconhecido de 21/09 segurar o vpad de um só jogador, ela cala quem joga.
- **O portão diz por que fechou** (`alto_falante.py:1373-1416`): `haptica_portao_fechado uniq=<mascarado> motivo=sem_jogo|nao_mexeu|nao_sei evdev_do_jogo=N hidraw_de_vpad=M evdev_le_este=…`, uma linha por controle, só quando o estado anômalo (endpoint tocando e controle fora de quem joga) começa ou muda de motivo; o repouso não loga. No PRAGMATA de 26/09, uma linha dessas teria dito a causa sem ninguém medir. A contagem nunca derruba a thread do som: se falhar, sai `None`.
- **Cobertura:** o cabo não passa pelo portão; de 1 a 4 jogadores entra exatamente quem mexeu; não depende de jogo nem de lançador. O vpad Xbox é uinput, sem `uniq`, e nunca entrou por evdev.

**As réguas** estão em `tests/unit/test_a_haptica_quem_joga_e_quem_mexe.py`: o mundo medido (quatro vpads presos só por hidraw, stream nos quatro endpoints, só o P2 mexe: só o P2 entra), os arranjos de 1 a 4 jogadores (o P1, o P3, o P2 com o P4, três e os quatro), a marca que zera quando o jogo fecha, reabre ou troca, uma linha por mudança com o endereço mascarado, o evdev cheio nos dois mundos, o co-op que falha na abertura e a fiação real do laço e do `forward_all`. Mordidas: 14 na `-01` e 10 na `-02`, todas reprovando com a cura arrancada; 63 portões verdes nas duas.

**Risco aceito na decisão:** quem mexer num controle que o jogo não lê vibra, se o endpoint dele tiver stream.

## Lateral: o «Salvar» que reescrevia outra seção

Na mesma sessão, o «Salvar Perfil» da aba Vibração ligou o microfone do controle (`mic.muted` de true para false) e apagou o `speaker.fonte` dele (medido pelo diff dos backups do perfil). Causa: o rodapé punha o que o aparelho publicava por cima do disco em **todas** as seções e remontava o alto-falante sem a `fonte`; o editor da aba Perfis tinha o mesmo molde, e a conferência achou o microfone no mesmo molde (apagava `gain` e `volume`). A primeira cura, **`D-2609-O-SALVAR-GRAVA-A-SECAO-DA-ABA`** (sprint `O-SALVAR-DA-VIBRACAO-01`), limitava o vivo às seções da aba do clique. Ela foi revogada pela `D-2709-O-SALVAR-LE-O-PERFIL`: o Salvar e o Aplicar passaram a ler só o disco, em toda aba (ver [a manhã de 28/09, §4](01-a-onda-de-28-09-o-modo-o-som-o-salvar-e-a-raiz.md)). O caso das 18:38:37 continua guardado em `tests/unit/test_o_salvar_de_uma_aba_nao_mexe_na_outra.py`.

## O que ficou aberto

- **A prova com a mão:** o PRAGMATA com um controle só pelo rádio, máscara DualSense, 30 a 60 s numa cena que vibra, sem «Reiniciar», sem PS+R3 e sem desligar o controle. Leitura que decide: `LC_ALL=C timeout 3 pactl list short sink-inputs`. Stream no endpoint seguida de `som_radio_ponte_de_pe arranjo=0x32-háptica` = curado; stream com `haptica_portao_fechado motivo=nao_mexeu` = defeito na fiação da marca; nenhuma stream = a hipótese abaixo.
- **O jogo pode não abrir stream no endpoint.** Independe do portão e só apareceria depois dele curado. Os suspeitos são o nó do alto-falante de dois canais que passou a se chamar «… (DualSense Wireless Controller)» (`2f11c3f84`), casando os predicados de **nome** do mmdevapi do GE (patches `0019`, `0086`, `0168`, `0187`), e o rótulo novo do endpoint (`8beb01489`, `65555bada`). O fluxo inteiro não foi lido.
- **Quem segurava os `eventN` em 21/09.** Na medida de 26/09, nem o daemon nem o gerente do systemd tinham `STEAM_COMPAT_DATA_PATH`; se o daemon a herdasse, o portão antigo devolveria a mesa inteira, que é o quadro de 21/09. Sem prova.
- **Modo Nativo com mais de um controle:** o daemon só lê o físico do posto, então os secundários não entram por este sinal e não vibram pelo rádio.
- **Um laço de custo agora alcançável:** se a ponte não sobe para quem mexeu (`haptica_sem_fonte`, `som_ponte_nao_subiu`), o vigia acorda a volta a cada 0,4 s e cada volta tenta subir os gravadores `pw-record` de novo.
- **Com o jogo aberto, «Reiniciar o serviço» e PS+R3 recriam o vpad, e desligar o controle derruba o endpoint**, que volta como nó novo; o GE trata a saída de um nó Sony como desconexão (patch `0086`), e um jogo que já vibrava perde o stream.
- **Os blocos mudos da bomba** (`hapticos_mudos`, `pico_haptico`) não são publicados: um jogo que manda zeros não se distingue de um que vibra.
- **Dois vpads se anunciam «(Hefesto P1)»** com `nome_divergente=true` na mesa do co-op (medido).
