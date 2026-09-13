---
sprint: JOGO-SEM-EXCLUSIVIDADE-01
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  JOGO-SEM-EXCLUSIVIDADE-01:
    - src/hefesto_dualsense4unix/integrations/steam_launch_options.py
    - src/hefesto_dualsense4unix/integrations/steam_input_ponte.py
    - scripts/disable_steam_input.sh
    # só a docstring de `classify`, cujo fato a medição derrubou
    - src/hefesto_dualsense4unix/daemon/subsystems/game_signal.py
    - tests/unit/test_ponte_steam_input_01_a_lista_que_so_preservava.py
    - tests/unit/test_o_vigia_do_steam_input_nao_nasce_morto.py
    - tests/unit/test_r06_allowlist_steam_input.py
    - docs/process/sprints/2026-09-13-JOGO-SEM-EXCLUSIVIDADE-01-nenhum-jogo-foge-do-modo-e-da-mascara-da-aba-jogar.md
cria:
  - tests/unit/test_o_install_script_nao_e_jogo_vivo.py
  - tests/unit/test_o_steam_input_por_jogo_segue_a_lista.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/daemon/launch_env.py
  - src/hefesto_dualsense4unix/integrations/ponte_tentativa.py
  - src/hefesto_dualsense4unix/integrations/ponte_escada.py
  - src/hefesto_dualsense4unix/integrations/prontuario_dos_jogos.py
  - src/hefesto_dualsense4unix/integrations/storm_doctor.py
  - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
  - src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py
  - src/hefesto_dualsense4unix/profiles/
  - src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py
  - install.sh
  - docs/data/mapa-controles.csv
---

# JOGO-SEM-EXCLUSIVIDADE-01 — nenhum jogo foge do modo e da máscara da aba Jogar

> **ESTADO 2026-09-13: feita** — o avaliador do install script deixou de ser jogo vivo (`steam_game_running_appid` devolve None para `Install=1`; `steam_game_running` continua contando), e a lista do Steam Input passou a valer nos dois sentidos: `steam_input_ponte.py --desligar-fora-da-lista`, chamado pelo vigia junto do `--ligar`. **Achado que pesa na costura:** lido sem escrever, o `localconfig.vdf` dela já tem `UseSteamControllerConfig "0"` na árvore viva nos quatro jogos da queixa desde pelo menos 11/09, e o log da Steam de 13/09 01:29 e 01:30 mostra o controle virtual do Sackboy criado mesmo assim — o passo 2 não muda o disco desses quatro. A entrega está em `docs/process/agentes/2026-09-13/JOGO-SEM-EXCLUSIVIDADE-01-opus.md`.

A palavra dela está no índice: o Sackboy *«não tá respeitando o modo e a máscara
setado na aba jogar… diferente do resto dos jogos»*, talvez também Pragmata e
Mullet Mad Jack, e *«nenhum jogo tem que ter esse tipo de exclusividade em
termos de config fora da interface»*.

**Regra da casa que vale aqui:** *o produto é para qualquer usuário* — a cura não
depende dos jogos dela nem tem lista de jogos.

## §E — O que o estudo mediu (13/09; perfis, estado, env, `localconfig.vdf` e journal lidos, nada gravado)

**Nenhuma exclusividade está no perfil.** O perfil do Sackboy não tem modo nem
máscara; os do Pragmata e do Mullet Mad Jack são iguais aos de jogos que se
comportam como os demais. As Opções de Inicialização são idênticas nos dez jogos
lidos. **São duas exclusividades, e as duas moram FORA da interface:**

1. **O Sackboy tem install script, e a Steam roda o avaliador dele antes do
   wrapper** (`reaper SteamLaunch AppId=… Install=1`). A agulha da casa conta essa
   linha como JOGO VIVO: a autoridade vira `game` 4 a 5 s antes do ping do
   wrapper, o lançamento cai no ramo `jogo_vivo`, a escada não arma o primeiro
   degrau, o env por jogo não nasce, e a confirmação por silêncio nunca carimba.
   **6 de 6 aberturas desde 30/08**; o Future Knight (2 de 2) e o Touhou (1 de 1)
   armaram pelo ping. O caminho: `steam_game_running_appid` em
   `steam_launch_options.py` → `classify` (evidência E4) em `game_signal.py` →
   `arm_launch_profile` em `launch_env.py` → `comecar` em `ponte_tentativa.py`. A
   docstring de `classify` afirma que `SteamLaunch AppId=` «só existe no launch
   de um jogo» — **fato que a medição derrubou**.
2. **Steam Input ligado POR JOGO pela própria Steam**, fora da lista do Hefesto e
   por cima de `UseSteamControllerConfig "0"`: a pasta `config/<appid>/` em
   `Steam Controller Configs/<conta>/` e o `configset_controller_ps5.vdf` com
   `autosave` — no Sackboy, no Pragmata, no Mullet Mad Jack e no DON'T SCREAM, e
   em nenhum dos outros cinco lidos. Em toda abertura do Sackboy em 13/09 a Steam
   criou controle virtual (`Created virtual controller at slot`), inclusive
   depois da troca para Xbox; nas do Future Knight, do Pro Jank Footy e do Avatar,
   nenhum. O jogo vê o espelho do Steam Input, não a máscara da Jogar. **O vigia,
   o doctor e o prontuário só leem `UseSteamControllerConfig`**, e ela já está
   em `"0"` nesses quatro jogos, na árvore viva (`UserLocalConfigStore/apps`),
   em todo backup do vdf de 11/09 a 13/09: são cegos a isto. (Medido pela
   implementação em 13/09; a leitura «a chave não existe» olhou as árvores
   `apps` que não a guardam.)

O estudo inteiro fica na pasta do lote `1309-terceira`.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| O Steam Input de cada jogo obedece à lista do Hefesto nos dois sentidos: fora dela, desligado; dentro, ligado | a palavra dela no índice; a PONTE-STEAM-INPUT-01, «o produto obedece à lista, não a adivinha» (`prontuario_dos_jogos.py`); o contrato de `scripts/disable_steam_input.sh`; a D-VIGIA-DO-STEAM-INPUT em `docs/data/decisoes-dela.csv` |
| Sem lista de jogos: a detecção é por assinatura — `Install=1` na linha de comando, e configuração por appid na árvore da própria Steam | D-A-REGUA-E-QUALQUER-MESA-NAO-A-DELA; «o produto é para qualquer usuário» |
| O install script não é jogo para a autoridade, mas continua processo da Steam para quem pensa em fechá-la | DEDUP-05 (fechar a Steam com jogo aberto mata o jogo), em `steam_game_running` |
| Nenhum perfil migra; nenhum campo é apagado | MASCARA-QUE-GRUDA-01, §E3 |
| Nenhum botão novo: para religar o Steam Input num jogo, o caminho é o que existe, «Este jogo não funciona» na aba Lançadores | índice, §0 item 4 |

## §I — IMPLEMENTA

1. `steam_game_running_appid`: uma linha de comando com o token `Install=1`
   devolve `None`. `steam_game_running()` continua contando essa linha. A
   docstring de `classify` ganha o fato certo, com nota datada — só a docstring.
2. `steam_input_ponte.py` ganha uma função pura e uma bandeira nova, SEPARADA do
   `--ligar`: lê da própria Steam quais appids têm configuração de Steam Input por
   jogo (entradas com `autosave` nos `configset_*.vdf` e pastas `config/<appid>/`),
   e para cada um FORA da lista garante `UseSteamControllerConfig "0"` em
   `apps/<appid>` do `localconfig.vdf`. Os da lista continuam em "2" pelo
   `--ligar`. A leitura falha fechada: arquivo ilegível → zero escritas. Nome de
   configset com id de aparelho nunca vai a log nem a teste.
3. `scripts/disable_steam_input.sh` chama a bandeira nova no mesmo instante em que
   já chama o `--ligar` — Steam fechada, acordado pelo vigia que já está
   instalado.
4. **Nenhum agente escreve no `localconfig.vdf` real, nem com a Steam fechada.**
   Tudo em lar de mentira.

## §V — VALIDA/CORRIGE — o que morde

* A linha real do log (`reaper SteamLaunch AppId=N Install=1 -- …`):
  `steam_game_running_appid()` é `None` e `steam_game_running()` é `True`;
  `classify` não dá `game`; o armar do lançamento com dublê dá o motivo
  `primeiro_degrau`. **Arrancar a exclusão → `jogo_vivo`, que é a linha do journal
  das 05:00:20, e reprova.**
* Lar de mentira com três appids com `autosave` fora da lista, um na lista e um
  sem configuração: os três ficam com "0", o da lista com "2", o sem configuração
  sem chave; o arquivo relido pelo parser antes e depois. Tirar o ramo do "0" →
  reprova; ler a lista errada → reprova; configset ilegível → zero escritas.
* Um perfil de jogo de mentira relido byte a byte antes e depois do vigia.
* As três réguas do vigia e da lista continuam verdes, ou mudam de contrato com
  data.
* Portões verdes.

## §R — Riscos declarados

* **O DON'T SCREAM e o Mullet Mad Jack podem perder o controle ou os gatilhos**
  quando o vigia gravar "0": a casa registrou que o DON'T SCREAM não via controle
  sem Steam Input, e a lista dela não existe. A saída é o botão que existe; quem
  coordena avisa na entrega.
* A Steam regrava o `localconfig.vdf` ao sair: só o vigia, na saída da Steam,
  escreve.
* Uma corrida fica aberta: a evidência E3 do wrapper pode subir a autoridade se um
  tique cair entre o `last_run` e o arming. Nenhum caso perdido foi medido.
* O formato dos `configset_*.vdf` não é documentado.

**Só o aparelho responde (MESA-DE-QUATRO-01):** se o "0" vence a configuração
autosave (a próxima abertura do Sackboy sem `Created virtual controller`) — e o
disco já responde contra: o `"0"` estava lá quando a Steam criou o controle
virtual do Sackboy às 01:29 e às 01:30 de 13/09; se o
Sackboy passa a mostrar a máscara da Jogar; se o DON'T SCREAM e o Mullet continuam
com controle; se a escada arma pelo primeiro degrau e confirma por silêncio.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | a agulha e o vigia não dependem de transporte |
| **no perfil** | nenhum campo novo; nada migra |
| **por controle** | o Steam Input é por jogo, não por controle |
