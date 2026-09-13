# LIGHTBAR-NA-STEAM-01 — a paleta do cliente Steam não vira camada do jogo

Agente: opus (IMPLEMENTA) · árvore `voo/LIGHTBAR-NA-STEAM-01-opus`, nascida de
`onda/1309` (`249af1f6`). Sprint:
`docs/process/sprints/2026-09-13-LIGHTBAR-NA-STEAM-01-a-luz-dentro-da-steam-e-as-guardas-que-se-autoaplicavam.md`.
O estudo que a precedeu mora na pasta do lote `1309-terceira`, fora da árvore.

## O que mudou

**A tela não muda.** Nenhum arquivo de `src/hefesto_dualsense4unix/interface/`
foi tocado, então não houve foto nem piloto: o "clique" desta sprint é o teste
dirigindo `replay_retained_game_outputs` e `reescrever_lightbar_por_hidraw` com
dublê. O daemon vivo não foi reiniciado nem consultado.

| arquivo | o que mudou |
| --- | --- |
| `src/hefesto_dualsense4unix/core/backend_pydualsense.py` | **§I.1** — `replay_retained_game_outputs` deixa de entregar a luz retida sob 'daemon' pelo `set_game_output_for`: descarta, loga `game_output_retido_descartado_na_abertura` e re-arma o log de retenção. Com isso a camada GAME só recebe luz escrita com a autoridade já em 'game' ou 'unknown' — o `_game_wins()` e o gate do `set_game_output_for` ficaram intactos, porque o furo era só o replay. **§I.2** — `game_output_retido_sem_jogo`, `game_output_retido_descartado_no_close` e o novo `game_output_replicado` (1x por categoria por sessão, a cadência do `uhid_replica_ativa`) carregam `cor`, `players` e `autoridade`, com os nomes de campo do `gatilho_da_cor_escrito` para o journal casar sem traduzir. Dois auxiliares novos: `_autoridade_de_exibicao` (só dá nome ao que o provider responde; `sem_provider`, `provider_falhou`) e `_luz_para_o_journal`. O comentário do `__init__` sobre `_retained_game_outputs` afirmava a entrega: o fato foi substituído no MESMO número de linhas, para não deslocar as citações anteriores a ele. Nota datada no docstring de `end_game_session_for`. |
| `tests/unit/test_lightbar_na_steam_01_a_paleta_do_cliente_nao_vira_camada_do_jogo.py` | **novo** — 11 casos. A régua da §V (retém `(64, 0, 0)` com `-x-x-` sob 'daemon', vira 'game', e o merge devolve o perfil); o `0x31` do gatilho da cor saindo com a cor e o número do perfil depois do replay; o caso irmão (escrita sob 'game' vence); 'unknown' mantém o gate aberto; o dublê de autoridade sabe recusar; o gatilho cru segue sob 'daemon'; e cinco casos de journal. |
| `tests/unit/test_game_output_replica.py` | lido: a classe `TestRetencaoNaoSobreviveAoClose` trava a REGRA (a retenção morre com a sessão que a gerou), não o sintoma — quem morde a purga é a asserção sobre `_retained_game_outputs`. Ganhou nota datada dizendo isso. Nenhuma asserção mudou. |
| `tests/unit/test_uhid_replica.py` | lido, sem mudança: mede o vpad (parser, posse da sessão, dedup), que é anterior à autoridade e não conhece o replay. |
| `docs/data/mapa-controles.csv` e `html/specs.html` | **§I.3** — seis citações reapontadas por símbolo, medidas com `grep -n` depois da cura: `_read_battery_opt` (linha 69, duas colunas) e `_key_to_uniq` (linhas 114 e 122, quatro colunas). O `specs.html` saiu do `scripts/gerar-mapa.py`, e o `--check` confere. A citação `:6026 (set_game_output_for)` da linha `luz.replica_output_jogo` não se moveu. |
| `src/hefesto_dualsense4unix/daemon/ipc_handlers.py`, `src/hefesto_dualsense4unix/daemon/subsystems/luz_do_mic.py`, `src/hefesto_dualsense4unix/daemon/subsystems/recado_do_microfone.py`, `src/hefesto_dualsense4unix/integrations/radio_da_mesa.py` | **fora da posse, só o NÚMERO de uma citação em comentário.** O portão `citacoes-no-codigo` reprovou nomeando os dois primeiros; os outros dois a régua não alcança, mas o deslocamento os tornou errados do mesmo jeito. Nenhum está em `nao_toca:`. O de `ipc_handlers.py` virou `2440`: a prosa promete `_merged_desired_for_key`, que mora ali — o número velho só casava por acaso com `reassert_resolved_outputs`, na linha de cima. |

O que o journal passa a dizer, na saída do pytest (dublê, controle de teste):

```
game_output_retido_sem_jogo    autoridade=daemon campos=['led', 'player_leds'] cor=(64, 0, 0) players=(False, True, False, True, False) uniq=aabbcc000001
game_output_retido_descartado_na_abertura autoridade=game campos=['led', 'player_leds'] cor=(64, 0, 0) players=(False, True, False, True, False) uniq=aabbcc000001
```

## Qual mordida prova

Três arrancadas, uma de cada vez, sempre no produto e nunca no teste. O arquivo
curado foi copiado antes, devolvido depois de cada uma, e o `git diff --stat`
saiu idêntico ao de antes da primeira.

**A — a entrega de volta no replay** (o laço `set_game_output_for(alvo, **campos)`
original):

```
E       AssertionError: a cor que o cliente Steam deixou no vpad virou camada do jogo
E       assert (64, 0, 0) == (0, 0, 255)
...
>       assert escrita[0]["cor"] == COR_DO_PERFIL
E       assert (64, 0, 0) == (0, 0, 255)
...
4 failed, 7 passed
```

As quatro que reprovam: a régua da §V, o `0x31` do gatilho da cor (pintaria a
paleta), o descarte na abertura (voltaria a sair `game_output_replicado`) e o caso
irmão — este último pela metade do número: a cor do jogo venceu, mas a camada
ficou com o padrão `-x-x-` da paleta. A REPLICA-03 fica de pé nos dois lados.

**B — os campos fora do log de retenção:** `1 failed, 10 passed`
(`test_o_log_de_retencao_carrega_a_cor_o_padrao_e_a_autoridade`).

**C — os campos fora do log de réplica:** `2 failed, 9 passed`
(`test_o_log_de_replica_carrega_a_cor_e_a_autoridade` e
`test_sem_provider_o_journal_diz_que_nao_ha_fiacao_de_autoridade`).

**Devolvida:** `11 passed`. Os três arquivos da posse: `62 passed`. Os vizinhos
que tocam a autoridade e o replay (`test_game_output_replica`,
`test_led_set_broadcast`, `test_corretora_final_cross_cutting_20260720`,
`test_fecha_iluminacao_01_duas_pecas_nunca_tem_a_mesma_cor`,
`test_game_signal_wiring`, `test_sinal_de_jogo_perfil_por_titulo`,
`test_a_iluminacao_diz_o_numero_certo`, `test_troca_de_player_01_a_escolha_sobrepoe`,
`test_janela_cega_01_o_detector_que_adoece`): `185 passed`.

**As réguas das citações foram o oráculo do §I.3:** logo depois da cura,
`validar-citacoes-de-linha.py --all` acusou 6 podres no mapa e
`test_portao_o_par_com_metade_ligada.py` acusou 2 em comentário; depois do
reapontamento, `OK: 3298 citação(ões)` e `16 passed`.

Os portões: `git add -A && bash scripts/portoes.sh`, e o commit só existe porque
fecharam todos verdes.

## O que NÃO verifiquei

- **Nada no aparelho.** `bancada: false`, o daemon dela não foi tocado e nenhum
  IPC foi chamado. Se o plástico mostra a cor do perfil no Sackboy com a cura é a
  pergunta 1 da MESA-DE-QUATRO-01, e continua aberta.
- **O journal real.** Os campos novos só aparecem depois de install e reinício do
  daemon, que são de quem coordena. Vi as linhas no stderr do pytest, não na unit.
- **O preço declarado no §R.** A escrita única de LED de jogador que um jogo faça
  ANTES de o sinal virar 'game' (FATO 0) agora se perde. Não medi se algum jogo da
  biblioteca depende dela.
- **A transição `daemon -> unknown`** (detector de janela cego) passa pelo mesmo
  replay e agora também descarta. Não a exercitei com o `Daemon` inteiro e o
  backend real; o `test_game_signal_wiring` usa `FakeController`.
- **O casamento 16/16 com a tabela de jogador do SDL** não foi reaberto no fonte:
  herdei a medição do estudo.
- **A origem dos dois `(0, 0, 0)`** do journal continua sem dono.
- A suíte inteira não rodou (ordem da leva: só arquivos pontuais).

## O que sobrou para o próximo

- **Fato que ficou velho fora da posse, em prosa sem portão.** Três lugares dizem
  que a transição de autoridade REPINTA a lightbar com o que ficou retido:
  o docstring de `window_detect_healthy` em
  `src/hefesto_dualsense4unix/daemon/state_store.py`, o de
  `test_aba_de_navegador_com_titulo_de_jogo_sobe_a_autoridade` em
  `tests/unit/test_sinal_de_jogo_perfil_por_titulo.py`, e o item 3 do cabeçalho
  mais `test_healthy_continua_sendo_trinco_de_mao_unica_de_proposito` em
  `tests/unit/test_janela_cega_01_o_detector_que_adoece.py`. Desde esta sprint a
  transição não repinta com o retido; o que ela ainda muda é a camada GAME velha
  voltando ao merge. A razão da JANELA-CEGA-01 para manter `healthy` como trinco
  enfraqueceu — decidir se ela ainda vale é leva própria.
- **Para a MESA-DE-QUATRO-01**, além das perguntas da sprint: com a unit
  reinstalada, procurar `game_output_replicado` logo depois de um `game_signal
  daemon->game`. Se a paleta do SDL chegar JÁ com `autoridade=game`, a
  alternativa larga do §I.4 (o perfil vencendo a camada GAME para a luz) vira a
  próxima sprint; se chegar só como `game_output_retido_descartado_na_abertura`,
  esta cura basta.
- **Costura.** Quatro arquivos fora da posse mudaram um número de comentário; se
  outra sprint do lote mexer nas mesmas linhas, o conflito é esse. E se a
  JOGO-SEM-EXCLUSIVIDADE-01 também deslocar o backend, as citações se remedem
  depois da costura — as duas réguas nomeiam cada uma.
- `_retained_game_outputs` agora serve só à telemetria e ao disparo da defesa
  (NUMA-03). Se o journal mostrar que ninguém precisa do valor descartado, uma
  sprint futura pode enxugá-lo.
