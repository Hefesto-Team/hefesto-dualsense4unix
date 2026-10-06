# O perfil Freestyle: por cima de tudo e no ultra

O que se mediu e se desenhou na madrugada de 27/09/2026 para o Freestyle ficar «no ultra» e valer por cima dos perfis de jogo, e por que nada disso entrou no `dev`.

## O pedido

Duas falas dela, de 27/09, puxaram as duas rodadas:

- «no freestyle a ideia é tudo estar no ultra até vibração e afins.» <!-- noqa-acento: citação literal -->
- «no freestyle tem um problema que é. ao jogar qualquer que seja o jogo mesmo o botão ativado ele nunca tem prioridade. ter criado um perfil pra ele não foi a solução que eu havia pedido. a ideia é ele andar por cima do sistema de perfis. pq ao jogar qualquer jogo ele nunca fica ativado e sempre perde prioridade pra algum jogo (o que estpa certo.)» <!-- noqa-acento: citação literal -->

A segunda bate de frente com a `D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA` (o perfil próprio de um jogo entra por cima do Modo Freestyle, pela `LOCK-CEDE-01`, em `src/hefesto_dualsense4unix/profiles/autoswitch.py`).

## O que o Freestyle é hoje

É o perfil de reserva: `match any`, prioridade 1 (`assets/profiles_default/freestyle.json`), restaurado no boot. `seed_default_presets` (`src/hefesto_dualsense4unix/profiles/loader.py`) e `scripts/install_profiles.sh` o criam copiando o asset **só se ele faltar**. Quem já tem um perfil fica com o dele.

## A tabela do ultra (sprint `O-FREESTYLE-NO-ULTRA-01`)

Varreu-se o esquema inteiro do perfil: **83 campos**, dos quais 24 têm ultra, 12 são seções e 47 não mudam. O ultra de cada campo saiu do limite que o próprio produto aceita. Não se digitou valor nenhum:

| campo | ultra | de onde vem |
|---|---|---|
| gatilhos (modo/params) | `Off` vira `Rigid [5,255]`; os outros modos mantêm a forma e a força maior sobe ao topo que `build_from_name` aceita | índices de `FORCAS_DO_GATILHO` (`src/hefesto_dualsense4unix/profiles/schema.py`), topo sondado no código do gatilho |
| `lightbar_brightness` | 1.0 | o `le=` do campo |
| `player_led_brightness` | forte | o degrau mais forte de `BRILHOS_DAS_LUZES` (`src/hefesto_dualsense4unix/core/led_control.py`) |
| `rumble.passthrough` | ligado | — |
| `rumble.policy` (global e por controle) | `max` | o maior multiplicador de `RUMBLE_POLICY_MULT`, 1.5 (`src/hefesto_dualsense4unix/daemon/subsystems/rumble.py`) |
| `custom_mult` | nulo | o validador o recusa fora de `custom` |
| `motor_*_pct` | 100 | `MOTOR_PCT_MAX` (`src/hefesto_dualsense4unix/profiles/schema.py`) |
| alto-falante: volume / mudo | 102 / desligado | `volume_do_percentual(100)` (`src/hefesto_dualsense4unix/core/speaker_scale.py`): o esquema aceita até 255, mas acima de 102 o som já saturou |
| microfone: volume / ganho | 100 / 100 | o `le=` |
| microfone mudo, `button_toggles_system` | desligado / ligado | — |
| giroscópio / acelerômetro | ligado | — |

**Não mudam, e por quê:** cor, padrão do número, cor automática e a procedência da cor, modo, máscara e rota, a ponte, a rota e a fonte do som, os mapeamentos de tecla, remap e teclado. O mouse também fica: ligá-lo muda o desktop e derruba o controle virtual. A mira fica porque move a câmera. As sensibilidades ficam porque medem precisão, e não força. `match`, nome e prioridade ficam.

**Não há campo no perfil** para a força da háptica (o ganho é fixo em 1.0), para o touchpad nem para a economia de bateria (que mora no `maquina.json`).

Duas escolhas foram feitas na rodada:

- **A vibração no ultra é `max` (1.5), e não `custom` 200%.** Com 200%, metade da faixa satura e a vibração parece constante, que é a queixa dela de 10/08.
- **O som ficou fora do asset.** A seção global de alto-falante e microfone, na troca de perfil, só alcança um controle (`_handle_for`, `src/hefesto_dualsense4unix/core/backend_pydualsense.py`). Na chegada do controle, o alto-falante já vai a 102 nos quatro, o microfone nasce aberto e o ganho nasce no topo do firmware.

**O perfil dela abaixo do ultra:** na parte global, gatilhos `Off`, luzes do número fracas e vibração `balanceado`. Por controle, o volume do microfone está abaixo do topo nos quatro (de 23 a 64), o brilho da barra em dois, a força do gatilho em dois, e num deles as luzes do número estão fracas e o alto-falante em 101. Os mudos dela (microfone em dois controles, alto-falante em um) ficam, a não ser que ela peça outra coisa. Levar o perfil dela ao ultra ficou para um passo à parte, com cópia antes, escrita pelo `save_profile`, modo seco e guarda de `HOME`. No lar de mentira, o modo seco mostrou 18 campos subindo, e o disco dela não foi tocado.

**As réguas** (num teste novo, `test_o_freestyle_nasce_no_ultra`, que não entrou), com 14 mordidas de 14:

- campo novo no esquema sem linha na tabela reprova;
- o validador recusa um passo acima de cada ultra;
- no fio, os quatro controles, por cabo e por BT, recebem o gatilho e as luzes no topo, e a vibração recebe `max`;
- um perfil de quatro controles só sobe o que está abaixo e não toca cor, rota, forma da curva nem mudo.

Uma das mordidas pegou a própria régua. Ela lia o byte das luzes do número no fluxo, que fica em 0 quando o fluxo não mexe nas luzes; como 0 é «forte», a régua passava com o asset em «fraco». Ela passou a usar o instrumento de `tests/unit/test_o_brilho_das_luzes_de_numero.py`.

A medida: 63 portões verdes e 1.708 testes do território verdes sob `xvfb-run`.

## O desenho que veio depois: camada, e não perfil (sprint `O-FREESTYLE-POR-CIMA-01`)

A segunda fala mudou o alvo. O desenho proposto a partir dela:

- o perfil do jogo continua ganhando dos perfis comuns;
- o Modo Freestyle **não é perfil**. É uma camada por cima do perfil que estiver valendo. Ligada, todo campo de intensidade e de liga/desliga vai ao ultra nos quatro controles, por cabo e por BT, e cor, máscara, mapeamento e rota vêm do perfil que vale. Desligada, vale o perfil puro;
- a camada sobrevive à troca automática de perfil, ao jogo abrir e fechar, à reconexão e ao restart do daemon;
- o perfil «Freestyle» de fora do jogo não se renomeia nesta leva.

Com isso, o asset no ultra e a decisão `D-2709-O-FREESTYLE-NASCE-NO-ULTRA` passaram a seguir o desenho errado e ficaram de fora. Da primeira rodada, só se aproveitaria a tabela do ultra, com a correção da régua das luzes. A decisão prevista era `D-2709-O-FREESTYLE-ANDA-POR-CIMA`, revogando a `D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA`.

## O que ficou aberto

- **Nada destas duas rodadas está no `dev`.** As duas foram interrompidas: a da tabela durante a conferência, que não devolveu nada, e a da camada ainda no estudo, sem sprint devolvida. Nem o módulo da tabela (`o_ultra`), nem o teste das réguas, nem as decisões `D-2709-O-FREESTYLE-NASCE-NO-ULTRA` e `D-2709-O-FREESTYLE-ANDA-POR-CIMA` existem na árvore.
- O desenho da camada também não durou. Na tarde de 27/09, `docs/data/decisoes-de-produto.csv` passou a trazer a `D-2709-O-FREESTYLE-E-UM-PERFIL-QUE-MANDA` (sprint `O-FREESTYLE-E-UMA-CAMADA-SO-01`), decidida por ela contra a camada fixa: o Freestyle é um perfil que ela ajusta nas abas, nasce com tudo no ultra e, ligado, o autoswitch não o troca por perfil de jogo nenhum. A decisão também revoga a `D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA`.
- O volume de captura do microfone não tem valor por controle no nascimento.
- A seção global de som não alcança os quatro controles na troca de perfil.
- A háptica não tem campo de força no perfil.
- A vibração no ultra (`max` contra 200%) é escolha dela a confirmar ou derrubar.
- O perfil «Freestyle» que ela já tem no disco continua abaixo do ultra: nestas rodadas, o disco dela não foi tocado.
