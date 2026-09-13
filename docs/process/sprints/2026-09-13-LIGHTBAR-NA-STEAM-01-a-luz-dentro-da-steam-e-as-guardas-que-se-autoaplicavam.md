---
sprint: LIGHTBAR-NA-STEAM-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  LIGHTBAR-NA-STEAM-01:
    - src/hefesto_dualsense4unix/core/backend_pydualsense.py
    - tests/unit/test_game_output_replica.py
    - tests/unit/test_uhid_replica.py
    - docs/data/mapa-controles.csv
    - html/specs.html
    - docs/process/sprints/2026-09-13-LIGHTBAR-NA-STEAM-01-a-luz-dentro-da-steam-e-as-guardas-que-se-autoaplicavam.md
cria:
  - tests/unit/test_lightbar_na_steam_01_a_paleta_do_cliente_nao_vira_camada_do_jogo.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/core/lightbar_gatilho.py
  - src/hefesto_dualsense4unix/core/gatilho_fim_de_sequencia.py
  - src/hefesto_dualsense4unix/daemon/connection.py
  - src/hefesto_dualsense4unix/daemon/lifecycle.py
  - src/hefesto_dualsense4unix/core/escritor_cru.py
  - src/hefesto_dualsense4unix/core/sysfs_leds.py
  - src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py
  - src/hefesto_dualsense4unix/app/actions/carona_do_wrapper.py
  - src/hefesto_dualsense4unix/integrations/uhid_gamepad.py
  - src/hefesto_dualsense4unix/profiles/manager.py
  - src/hefesto_dualsense4unix/daemon/launch_env.py
  - install.sh
  - scripts/doctor.sh
  - src/hefesto_dualsense4unix/interface/
---

# LIGHTBAR-NA-STEAM-01 — a luz dentro da Steam, as guardas que se autoaplicavam, e as features que talvez não cheguem ao jogo

A palavra dela está no índice: *«ler sobre como descobrimos como funcionava a
escrita do lightbar dentro da steam e como fizemos os guards funcionarem lá pra
isso sempre se autoaplicar. tenho receio que nossas features não cheguem aos
jogos pelo mesmo motivo ou semelhantes. inclusive acho que o lightbar perdeu
essas qualidades… ou foi desligado recentemente. Preciso que a auditoria revele
isso.»*

## §E — A resposta da auditoria (13/09; git, journal desde 01/09 e `systemctl --user`, só leitura)

**A luz NÃO foi desligada, e nenhuma guarda perdeu a fiação.** Todas existem, são
chamadas e estão ligadas por padrão — sem flag, sem `default.env`, sem opção de
install:

| guarda | nasceu | o que a dispara | medido de 01/09 a 13/09 |
| --- | --- | --- | --- |
| gatilho da cor (GATILHO-DA-COR-01) | `496ba056`, 12/08 | conexão nova pelo rádio e sinal de jogo; dispara 1,5 s depois de sossegar e escreve cor e número pelo 0x31 em todos do rádio | 157 disparos, 169 escritas enviadas, zero falhas |
| a rota 0x31 em regime (ROTA-BT-EM-REGIME-01) | `aba7f008`, 13/08 | toda troca de luz e todo perfil | viva |
| escritor cru (ESCRITOR-CRU-01) | `82ecd1ca`, 16/08 | sonda dos descritores abertos a cada 30 s | 9 detectados, 26 pinturas com escritor cru |
| a carona no vigia (CARONA-NO-GUARD-01) | `ff506370`, 16/08 | a cada 30 min e a cada escrita no userdata da Steam | 96 execuções por dia; às 05:46 de hoje, «COM o wrapper: 66» |
| repintura do cabo e pela numeração | `512830d8`, 07/09 | renumeração | viva |

Os commits desde 01/09 nesses símbolos só AMPLIAM ou mudam o conteúdo
(`489477eb`, `512830d8`, `510da716`, `d10c5426`, `a3081004`).

**O que tira a qualidade da luz no jogo é o CONTEÚDO que a guarda reafirma.**
Enquanto o jogo tem a autoridade, o merge põe no topo a camada GAME, que é a
réplica do que se escreve no vpad (REPLICA-03, 19/07). Na passagem de `daemon`
para `game`, `replay_retained_game_outputs` reentrega o último valor RETIDO sob a
autoridade do daemon — e o próprio código admite que ele pode ser do CLIENTE
Steam. **Dezesseis escritas do gatilho (07, 08, 10 e 13/09) pintaram exatamente
os pares cor e padrão da paleta de jogador do SDL**, a 0x40 ou 0x20 — a última às
05:00:16 de hoje, no Sackboy, logo depois do sinal de jogo. A guarda reafirma com
fidelidade a cor fosca da Steam no lugar da cor do perfil. Houve também duas
escritas de preto sem origem identificada.

**O periódico não salva o rádio:** `reassert_resolved_outputs` e `defend_display`
escrevem só pelo sysfs, a rota que perde para a Steam no rádio; a cor só volta
pelo rádio num EVENTO.

**As outras features, no jogo:**

| feature | guarda | o que o estudo viu |
| --- | --- | --- |
| máscara, lista IGNORE, hidraw escondido do Proton | só pelo wrapper; o vigia o repõe com a Steam fechada, por desenho | Avatar Legends e Pro Jank Footy foram jogados às 03:41–04:18 sem o atalho (vigia: adiado, Steam aberta); às 05:46 os 66 jogos estavam com ele — a autocorreção funcionou quando a Steam fechou |
| vibração | RUMBLE-SEM-DONO-01 | 111 avisos de vibração sem dono |
| gatilhos | a camada do jogo é re-pendurada na reconexão | sem reafirmação depois da rajada da Steam |
| microfone | MIC-BT-DONO-01, no hotplug | sem reafirmação depois da rajada |
| som | só nas bordas de conexão | — |
| Sackboy | — | a luz e os gatilhos do perfil de lançamento cederam à trava manual; é a trava, não a Steam (ver JOGO-SEM-EXCLUSIVIDADE-01) |

O estudo inteiro fica na pasta do lote `1309-terceira`.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| Nada a religar: gatilho, escritor cru e vigia ficam como estão | a medição acima; «hipótese tem de explicar o que JÁ funcionava» |
| A cor que o cliente Steam deixou no vpad antes do jogo não vira camada do jogo | a regra dela de 12/08, em `docs/protocol/pilha-steam-input-xpad-sdl.md` («no modo nativo devolvemos o controle pra steam e no modo conexão também, todo o resto é o hefesto»); o risco admitido na docstring de `replay_retained_game_outputs` |
| Gatilhos, microfone e som NÃO ganham reafirmação às cegas | o conteúdo da rajada da Steam nunca foi decodificado (a pilha, §7); reafirmar em regime já zerou motor alheio (RUMBLE-SEM-DONO-01) |
| O reparo do wrapper continua só com a Steam fechada, e sem botão | a palavra dela, «nem precisa ter um botão na gui, mas ele se auto corrigir», citada em `carona_do_wrapper.py`; índice, §0 item 4 |

## §I — IMPLEMENTA

1. `replay_retained_game_outputs` deixa de reentregar a cor e o padrão de jogador
   retidos sob a autoridade `daemon`; os gatilhos crus continuam. Em
   `set_game_output_for`, a camada GAME só recebe luz escrita com a autoridade já
   em `game` ou `unknown`.
2. Os logs de réplica e de retenção passam a carregar o VALOR (cor, padrão de
   jogador) e a autoridade — para o journal separar a paleta do SDL de pintura
   legítima de jogo.
3. Reapontar as citações de linha do backend deslocadas, perguntando ao dono, e
   regenerar `html/specs.html` se o mapa mudar.
4. **Não fazer agora:** o override do perfil vencendo a camada GAME para a luz (a
   alternativa larga) — só se a telemetria do passo 2 mostrar a paleta chegando
   já sob `game`. Fica escrito para a MESA-DE-QUATRO-01.

## §V — VALIDA/CORRIGE — o que morde

* Dublê do provedor de autoridade: retém (64,0,0) com padrão de jogador sob
  `daemon`, vira `game`, e o merge devolve a cor do perfil, não a retida.
  **Arrancar a cura → (64,0,0) e reprova.** Caso irmão: escrita sob `game`
  continua vencendo (REPLICA-03 intacta).
* O log de retenção sem jogo e o de réplica carregam a cor e a autoridade;
  arrancar → reprova.
* `tests/unit/test_game_output_replica.py` e `tests/unit/test_uhid_replica.py`:
  ler antes; se travam a semântica velha, decidir se travam a regra ou o sintoma,
  com nota.
* O portão das citações de linha verde.

## §R — Riscos declarados

* A cura pode engolir a escrita única de luz de jogador que um jogo faz nos ~2 s
  antes de o sinal virar `game` — é a razão declarada do replay.
* Linhas novas no backend deslocam citações no mapa e nas docs.

## Só o aparelho responde — para a MESA-DE-QUATRO-01

1. Num jogo com Steam Input, o plástico mostra a cor fosca de jogador em vez da
   cor do perfil? Ela some com a cura?
2. Quem manda preto? A barra apagou de fato?
3. A rajada de 98 pacotes da Steam leva bits de gatilho, do mudo do microfone ou
   de áudio?
4. A Steam repinta a luz em regime sem borda nova de descritor, e a barra fica na
   cor dela até o próximo evento?
5. Os efeitos de gatilho do perfil sobrevivem a uma reconexão pelo rádio com a
   Steam aberta?

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | o replay e o merge são os mesmos nos dois; o gatilho da cor é do rádio |
| **no perfil** | a cor do perfil deixa de perder para a cor retida do cliente |
| **por controle** | a camada é por controle; a cura vale para cada um |
