# O `wpctl` pendurado e a Steam que não fecha: o metadata do PipeWire até a 1.6.8

**Medido em 14/10/2026**, no PipeWire 1.6.8 e no WirePlumber 0.5.12 (os do Pop!_OS 24.04). A reprodução rodou num
PipeWire privado (`XDG_RUNTIME_DIR` próprio), sem tocar o áudio da sessão.

## A resposta

1. **O defeito é do PipeWire, e o upstream já o curou:** o commit `06de0ed` («metadata: remove pending pong on
   unbind», 07/09/2026, issue #5445), que entrou na **1.6.9** (17/09/2026). Até a 1.6.8, todo cliente que faz bind num
   metadata no instante em que o dono do metadata (o WirePlumber) está saindo fica sem ser lido pelo servidor, para
   sempre.
2. **O gatilho é o reinício do WirePlumber**, e não a rotatividade de nós: 0 pendurados em 450 `wpctl settings`
   lançados no meio de nós nascendo e morrendo em rajada (`pw-loopback`).
3. **O install do Hefesto abre essa janela a cada instalação:** o `fix_wireplumber_default_source.sh --install`
   reinicia o WirePlumber mesmo com o drop-in igual. Dos 13 reinícios do WirePlumber desde 07/10 na máquina medida, pelo
   menos 6 casam com um log de install que diz «WirePlumber reiniciado», e o do caso medido é um deles.
4. **O cliente que pendura é qualquer um:** a Steam roda `wpctl settings monitor.alsa.enable-external-volume-control`, e
   ela fica em `do_wait` esperando o `wpctl` para sempre. A Steam não fecha até alguém matar o `wpctl`.
5. **A cura que vale para qualquer usuário é o PipeWire ≥ 1.6.9.** No ensaio do jogo, o `steam.py --fechar` diz
   qual filho prende a Steam, sem matar nada.

## A causa, no fonte da 1.6.8

As linhas são as da tag 1.6.8 do PipeWire e da 0.5.12 do WirePlumber.

- No `metadata.c` do módulo de metadata, o `global_bind` marca como *busy* o cliente que faz bind (linha 178) e pinga
  o dono do metadata (linha 189, `pw_resource_ping(impl->resource, …)`). Só o `remove_pending` (linha 122) solta o
  *busy*, pelo pong (`impl_resource_pong`) ou pela destruição do recurso do dono (`impl_resource_destroy`, linha 131).
- Quando o dono sai antes de responder, o `global_resource_destroy` (linha 224) chama o `pw_global_destroy` (linha
  232). Ele destrói o recurso de quem fez bind, e o `global_unbind` (linha 106) tira o ouvinte do dono (linha 113)
  **sem chamar o `remove_pending`**. O `impl_resource_destroy` daquele bind nunca roda.
- O *busy* é um booleano (o `pw_impl_client_set_busy` do `impl-client.c`, linha 795). Com ele ligado, o
  `client_busy_changed` do `module-protocol-native.c` (linha 455) tira o `SPA_IO_IN` do socket, e o
  `process_messages` (linha 354) para de ler. O cliente espera em `poll`, e o Recv-Q do lado do servidor só cresce.
- A janela é a saída do WirePlumber: o `SIGTERM` só para o laço (o `main.c` do WirePlumber, linha 65), e o
  `wp_core_disconnect` (linha 256) roda fora dele. Nesse intervalo, nenhum ping recebe pong.

## A reprodução

| rodada | lançados | pendurados |
| --- | --- | --- |
| o WirePlumber congelado (`SIGSTOP`) recebe o bind e morre (`SIGKILL`); um novo sobe | 20 | **20** (após 11 s, com o WirePlumber novo de pé) |
| o mesmo, mas o WirePlumber volta (`SIGCONT`) em vez de morrer | 15 | 0 |
| o mesmo do primeiro, com o `metadata.c` curado (o `remove_pending` no `global_unbind`) | 15 | 0 |
| 20 reinícios graciosos (`SIGTERM`), 12 `wpctl` espalhados em cada um | 240 | 0 |
| 4 paradas pelo `SIGTERM` (o caminho do `systemctl restart`), alongadas a ~255 ms (`strace` atrasando cada `close`), `wpctl` a cada 20 ms durante a parada | 48 | **8** (2 por parada) |
| 3 paradas alongadas com a mesma compilação, sem a cura | 36 | **6** |
| 3 paradas alongadas com o `metadata.c` curado | 36 | 0 |
| nós e laços nascendo e morrendo em rajada, sem reinício | 450 | 0 |

- O pendurado da reprodução é igual ao da máquina: `wchan=poll_schedule_timeout`, cliente `unrestricted` com `rwxm`, o
  Send-Q do lado do `wpctl` cheio (5.888 bytes no privado, 213.248 na máquina) e o Recv-Q do lado do servidor parado
  (~1 KB no privado, 34.592 bytes na máquina) só no socket dele. A diferença de tamanho não foi medida; a hipótese é o
  grafo, com 472 objetos na máquina e uma dúzia no privado.
- O `SIGTERM` pendura quando a parada é longa: o WirePlumber privado sai em ~1 ms, e por isso as 240 tentativas sem
  alongar deram 0. Alongada a ~255 ms, cada parada prende 2 dos 12 `wpctl` (os que fizeram o bind depois de o laço
  parar). Na máquina, a parada normal leva de 10 a 60 ms, e a do caso medido levou **665 ms**.
- No caso medido, o `wpctl` nasceu às 20:14:35,01, 74 ms antes de o systemd começar a parar o WirePlumber
  (20:14:35,084). O mesmo install tinha reiniciado o daemon do Hefesto às 20:14:32, e entre 20:14:34,89 e 20:14:34,95
  o daemon novo tirou e republicou as fontes de microfone dos controles. Ainda falta provar que a Steam roda o `wpctl`
  porque os nós de som mudaram. Se roda, o install pôs as duas pontas da janela a 150 ms uma da outra: o nó que muda e
  o WirePlumber que para.
- O módulo curado foi compilado da tag 1.6.8 contra os cabeçalhos do sistema e carregado por `PIPEWIRE_MODULE_DIR`. A
  cura testada é a mesma do `06de0ed`. A mesma compilação, sem a cura, pendura 5 em 5 (5 dos 20 da primeira linha).

A receita, para quem quiser repetir: um `pipewire` com `protocol-native`, `access`, `metadata`, `client-node`,
`adapter` e `session-manager`, um `wireplumber` com só os componentes de metadata e settings, e então:

```bash
kill -STOP "$WP"; wpctl settings monitor.alsa.enable-external-volume-control &   # o bind fica à espera do pong
sleep 1; kill -KILL "$WP"; wireplumber &                                         # o dono sai sem responder
sleep 10; kill -0 $! && echo pendurado                                           # e o wpctl não sai nunca
```

## A cura da casa

- **O PipeWire 1.6.9 da casa** (15/10/2026) é a cura de qualquer usuário enquanto o Pop!_OS entrega a 1.6.8: a 1.6.9
  do upstream com o `debian/` do Pop e o WirePlumber 0.5.18, em
  [receita-backport-pipewire.md](../usage/receita-backport-pipewire.md). A receita acima virou
  `assets/pipewire-backport/prova/reproduzir.sh`, e o `scripts/construir_pipewire_backport.sh --prova` a roda sobre o
  servidor que vai ser empacotado: com a cura, 0 pendurados em 20; o mesmo servidor sem a linha do `06de0ed`, 20 em 20.
  O doctor (`check_pipewire_cura_do_metadata`) avisa abaixo da 1.6.9 e aponta a receita.
- **O install só reinicia o WirePlumber quando um drop-in ou o state mudou** (`a1ed1a7e5`): quem reabre a janela sem
  mudar nada não abre a janela do defeito.
- **Não há relato novo a fazer ao upstream:** o #5445 já cobre o defeito. Se a distribuição demorar, o pedido é ao
  pacote do Pop!_OS:

```text
pipewire 1.6.8 in Pop!_OS 24.04 is affected by upstream #5445 (fixed by 06de0ed, released in 1.6.9):
a client that binds a metadata object while its exporter (wireplumber) is shutting down is left
busy forever and is never read again (e.g. `wpctl settings`, spawned by Steam, hangs and Steam
cannot exit). Reproduced on 1.6.8 by SIGSTOP/SIGKILL of wireplumber during the bind; gone with
the one-line change from 06de0ed. Could 1.6.9 be packaged?
```
