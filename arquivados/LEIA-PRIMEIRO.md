# `arquivados/` — o que saiu do produto e não foi apagado

**Nasceu em 19/09/2026**, das sprints `ORFAOS-DA-MIGRACAO-01` e
`TESTES-ARQUIVADOS-01`, por ordem dela de 17/09:

> *"migramos do gtk pro HTML. Não sei se migramos tudo, provavelmente sim. Mas
> se tivermos Scripts órfãos seria bom arquivarmos ele em uma pasta chamada
> Scripts arquivados ou algo assim."*

## A regra de entrada, e ela é estreita de propósito

Um módulo só entra aqui quando **as três fontes concordam** que ninguém o usa —
o critério que a `ORFAOS-DA-MIGRACAO-01` escreveu depois de duas medições
falharem:

| fonte | o que responde |
| --- | --- |
| 1 · import estático (AST, BFS das entradas) | o grosso das dependências |
| 2 · as bocas (`install.sh`, `.desktop`, unit, `subprocess`, carga por nome) | o que o import não vê |
| 3 · `sys.modules` numa **sessão real** do produto | **a autoridade** |

E a correção dela fecha o furo da fonte 3: *"Testes que olham só pra esses
módulos importados pro gtk são desconsiderados também né?"* — **sim**. Um
módulo morto com teste próprio aparece vivo em toda medição, porque o teste é o
importador. Por isso o teste vem junto quando o módulo sai.

**Quem MEDE não conta como vida.** Um portão que vigia um módulo morto também
é órfão: vigia de defunto é uso aparente.

## O que está aqui

| o quê | linhas | por que saiu |
| --- | ---: | --- |
| `src/app/compact_window.py` | 340 | a janela 320x90 *sempre-on-top* que era surrogate do tray quando o `StatusNotifierWatcher` não existia. A janela GTK saiu do disco em 06/09 (`GTK-3`, decisão `D-0609-GTK-LEVA-INTEIRA`); zero imports no produto, e as únicas bocas eram testes e dois portões que a VIGIAVAM. |
| `tests/test_compact_window.py` | 229 | o teste dela |
| `tests/test_compact_window_bebe_da_mesa.py` | — | o outro teste dela |

## O QUE **NÃO** ENTROU, e cada recusa é um achado

| módulo | por que FICOU |
| --- | --- |
| `app/arranque.py` | as quatro funções têm **zero chamadores**, mas uma delas (`forcar_xwayland_no_cosmic`) teve o trabalho assumido pelo `.desktop` — `gui/ponte_da_tela.py:565` diz *"sob o `GDK_BACKEND=x11` que o `.desktop` força"*. As outras três (`sanear_loaders_do_gdk_pixbuf`, `de_outro_confinamento`, `x11_alcancavel`) podem ser **cura perdida**, não código morto, e a diferença não se mede pelo grafo de imports. **Fica como achado, não como arquivo.** |
| `integrations/cura_por_estrada.py` | 483 linhas sem boca no produto — mas `interface/desenho_dos_lancadores.py:941` diz *"A LACUNA CONTINUA ABERTA"*. É **feature pendente**, não resto de migração. Arquivar seria apagar trabalho. |
| `core/faixa_sintetica.py` | só testes o importam, mas `scripts/check_faixa_sintetica.py --limpar` é um GESTO de trabalho (e é portão). Fica. |
| `tui/` | `cli/app.py:203` abre `hefesto-dualsense4unix tui`. Vivo. |

## Nada aqui é lixo

Esta casa não apaga decisão medida. O que está nesta pasta **saiu do caminho**,
não da história: continua legível, continua datado, e volta para `src/` no dia
em que alguém provar que precisa dele.
