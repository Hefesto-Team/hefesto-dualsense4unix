---
sprint: MODO-DE-CONEXAO-01
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  MODO-DE-CONEXAO-01:
    # tela
    - src/hefesto_dualsense4unix/interface/aba01.py
    - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
    - src/hefesto_dualsense4unix/interface/pacotes/perfil.py
    - src/hefesto_dualsense4unix/app/actions/jogar/painel.py
    - src/hefesto_dualsense4unix/app/actions/mode_transition.py
    - src/hefesto_dualsense4unix/app/actions/home_actions.py
    # daemon
    - src/hefesto_dualsense4unix/daemon/lifecycle.py
    - src/hefesto_dualsense4unix/daemon/protocols.py
    - src/hefesto_dualsense4unix/daemon/ipc_handlers.py
    - src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py
    - src/hefesto_dualsense4unix/daemon/subsystems/coop.py
    - src/hefesto_dualsense4unix/daemon/subsystems/external_mask.py
    - src/hefesto_dualsense4unix/daemon/subsystems/hotkey.py
    - src/hefesto_dualsense4unix/daemon/launch_env.py
    - src/hefesto_dualsense4unix/integrations/virtual_pad.py
    - src/hefesto_dualsense4unix/integrations/ponte_escada.py
    - src/hefesto_dualsense4unix/integrations/ponte_tentativa.py
    - src/hefesto_dualsense4unix/utils/session.py
    # perfil
    - src/hefesto_dualsense4unix/profiles/schema.py
    - src/hefesto_dualsense4unix/profiles/manager.py
    # as réguas que a regra dela muda
    - tests/unit/test_a_aba01_le_o_estado_em_vez_de_cravar.py
    - tests/unit/test_a_faixa_de_pendencia_da_jogar.py
    - tests/unit/test_hotkey_ponte_cycle.py
    - tests/unit/test_o_gesto_da_ponte_e_universal.py
    - tests/unit/test_a_mascara_do_gesto_volta_para_o_perfil.py
    - tests/unit/test_ponte_escada.py
    - tests/unit/test_ponte_escada_laco_01_quem_sobe_a_escada.py
    - tests/unit/test_ponte_gravada_no_launch.py
    - tests/unit/test_a_aba_01_jogar_fecha_as_linhas.py
    - tests/unit/test_mascara_por_controle_manda_no_vpad.py
    - tests/unit/test_a_mascara_mora_no_perfil.py
    - tests/unit/test_profile_mode.py
    - tests/unit/test_verdade01_o_retorno_que_mentia.py
    - tests/unit/test_a_mascara_persiste_ate_ela_mudar.py
    - docs/process/sprints/2026-09-13-MODO-DE-CONEXAO-01-o-degrau-xbox-que-diz-aplicado-e-nao-vale-e-o-texto-que-e-da-mascara.md
cria:
  - tests/unit/test_o_modo_nao_escreve_a_mascara.py
  - tests/unit/test_a_dica_do_modo_nao_fala_da_mascara.py
  - tests/unit/test_o_ps_r3_anda_por_caminhos_e_grava_no_perfil.py
  - tests/unit/test_a_mascara_do_cartao_vale_com_o_vpad_de_pe.py
bancada: false
depois_de: [SENSORES-NO-JOGO-03]
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/interface/topo.html
  - src/hefesto_dualsense4unix/daemon/subsystems/sensor_hub.py
  - src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py
  - src/hefesto_dualsense4unix/cli/cmd_gamepad.py
  - docs/data/
---

# MODO-DE-CONEXAO-01 — o degrau Xbox que diz «aplicado» e não vale, e o texto que é da máscara

> **ESTADO 2026-09-13: feita** — o chip de modo e o PS + R3 escolhem o CAMINHO
> (`mode.caminho`), e a máscara do cartão fica como estava; a máscara do cartão
> passa a valer com o vpad de pé; o PS + R3 grava no perfil ativo na hora; e as
> dicas do modo pararam de falar da máscara. Quatro réguas novas, cada uma com a
> mordida medida. O que só o jogo aberto responde continua na §B, da
> MESA-DE-QUATRO-01, e as linhas de `docs/data/` são da costura. A entrega está em
> `docs/process/agentes/2026-09-13/MODO-DE-CONEXAO-01-opus.md`.

## A palavra dela — 13/09/2026, à tarde

> *"o modo de conexão do conexão da aba jogar nao ta funcionando.  o texto do modo do xbox tá errado aquilo é o texto da mascara do xbox"* <!-- noqa-acento: citação literal dela -->

Chegou com a onda 3 da [terceira lista](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)
em voo, e segue o processo dela (§0 do índice): esta sprint nasce antes de
qualquer agente, e são no máximo três agentes.

## A regra dela — 13/09/2026, minutos depois (DECIDIDA)

Três mensagens seguidas, com o estudo já em voo:

> *"o modo é base (ele o ps + r3) aí ap´os o modo de conexão, independente do escolhido anteriormente temos a máscara que é como o jogo se apresenta em termos de inputs apesar do modo de conexão escolhido. pode executar ela enquanto os demais trampam ali."* <!-- noqa-acento: citação literal dela -->
>
> *"eles precisam funcionar durante o jogo tá bom?"*
>
> *"inclusive o ps +r3 e isso fica setado no perfil"*

A regra que sai delas, e o estudo não escolhe mais:

1. **O MODO é a base:** o caminho de conexão (Sony DualSense · Xbox · Steam
   Input · Navegação). O chip e o **PS + R3** são o MESMO modo, um pela tela e o
   outro pelo controle.
2. **A MÁSCARA vem por cima, independente do modo:** é como o jogo vê a
   entrada, qualquer que seja o modo. O chip de modo não escreve nem lê a
   máscara, e o texto do modo não fala de como o jogo desenha os botões.
3. **Os dois valem DURANTE O JOGO**, com o jogo aberto, inclusive o PS + R3.
4. **O que o PS + R3 escolhe fica gravado no perfil**, como o clique no chip.

E a ordem de execução também é dela: esta sprint roda **junto com a onda 3**,
não depois. A costura é que entra depois da SENSORES-NO-JOGO-03 (`depois_de`),
porque as duas mexem em `daemon/ipc_handlers.py`.

## §E — O que o estudo mediu

O estudo inteiro, com as cenas, os dois roteiros de medição e as duas saídas,
fica fora da árvore, no lote `1309-modo` da pasta `_lotes` ao lado da árvore de
integração. Medido com dublês num lar de mentira, sem o daemon nem os perfis
dela.

1. **A causa.** O degrau «Xbox» é uma MÁSCARA, não um caminho: o plano do chip
   manda `gamepad.emulation.set {flavor: "xbox"}`, que no daemon é só o padrão
   da máscara. Com máscara escolhida no cartão, `mascara_efetiva` dá a do
   cartão, e `start_gamepad_emulation_desfecho` responde `ja_estava` antes de
   gravar qualquer coisa. O piloto escreve «aplicado», o perfil ativo recebe
   `mode.gamepad_flavor = "xbox"` e o jogo continua recebendo DualSense. A cena
   reproduz o diário dela byte a byte, com a pendência «● Vai mudar para: Xbox».
   Sem máscara no cartão, o chip funciona.
2. **A luz mente:** `_estado_da_tela` acende o chip de modo pela máscara, e
   `mascara_do_aparelho` no canal uinput cai no `flavor` da sessão. Com o cartão
   em Xbox 360, o chip «Sony DualSense» fica aceso com o jogo vendo Xbox 360.
3. **O PS + R3 trava com máscara no cartão:** o ciclo é de máscaras
   (`CICLO_DE_PONTES`, `ponte_atual` lê `device.flavor`), e todo aperto pede uma
   máscara que o cartão vence — cinco pulsos vermelhos e o ciclo parado. Sem
   cartão ele anda, mas só grava depois de 180 s de jogo aberto, e grava a
   máscara no perfil **do jogo**, nunca no ativo.
4. **A máscara do cartão não chega ao vpad vivo:** `gamepad.mask.set` grava e não
   recria; reativar o perfil também não (`apply_profile_mode` compara
   `mode.gamepad_flavor` com o `flavor` do vpad). Hoje nada a aplica com o jogo
   aberto.
5. **O que o modo passa a ser como caminho** — o único eixo além da máscara é o
   backend do vpad: «Sony DualSense» = o vpad **uhid** (o relatório do DualSense,
   por onde voltam gatilho, luz e LED de jogador); «Xbox» = o vpad **uinput**, o
   canal comum e o piso de compatibilidade; «Steam Input» = a Steam entrega a
   entrada e o Hefesto fica na saída; «Navegação» = teclado e mouse. O uhid só se
   constrói com máscara DualSense (`make_virtual_pad`): com máscara Xbox 360 ou
   Nintendo Pro, os dois primeiros modos dão o mesmo aparelho.
6. **O que já concorda com a regra dela:** a tela em duas camadas de 31/08
   (`aba01.py`); o glossário, onde **Modo** é *«como o controle chega ao jogo»*
   ([A LÍNGUA DESTA CASA](../../A-LINGUA-DESTA-CASA-o-glossario-que-a-tela-e-o-codigo-falam.md));
   o «um modo para todos» de 08/09; a máscara por controle de 03/09; a máscara no
   perfil de 08/09; o «nenhuma feature cai por modo» de 31/08 e 05/09; o PS + R3
   que troca dentro do jogo (19/08) e é universal (30/08).

## §D — O que quem coordena decidiu (13/09/2026)

Pela regra dela e pelo estudo; ela delegou as decisões desta leva.

1. **O caminho mora num campo NOVO do perfil**, `mode.caminho`
   (`"dualsense"` · `"xbox"`, ou vazio). `mode.gamepad_flavor` fica como a
   máscara padrão que os perfis já têm, e o modo não o escreve mais. Reaproveitar
   o campo mudaria em silêncio a máscara dos jogos que ela já alinhou.
   **Perfil sem `caminho`:** o caminho sai de onde sai hoje (a máscara padrão
   dualsense dá uhid; as outras, uinput), para nenhum jogo mudar no dia da cura.
2. **Modo «Sony DualSense» com máscara que não é DualSense:** o modo fica gravado
   e aceso, e o aparelho sai no canal comum. A falta do canal é dívida no mapa,
   escrita na costura, nunca frase na tela.
3. **Steam Input** fica fora do PS + R3 e sem troca com o jogo aberto: a Steam
   regrava a configuração dela ao sair (`ponte_escada`). O chip continua como está.
4. **O PS + R3 grava o caminho no perfil ATIVO** logo que o aparelho confirma, sem
   esperar os 180 s e sem precisar de jogo. O carimbo por jogo da escada (19/08)
   continua separado e intocado.
5. **O ciclo do PS + R3 é de caminhos:** Sony DualSense → Xbox → Navegação →
   Sony DualSense. A máscara do vpad não muda em aperto nenhum.
6. **A máscara do cartão vale na hora:** depois de gravar, o daemon recria o vpad
   daquele controle, com origem manual. O ato mora num método do daemon; o
   handler só o chama.
7. **A CLI** (`cli/cmd_gamepad.py`): o `--flavor` continua sendo máscara.
8. **Notas datadas, nada se apaga:** a D-5 (cai só a metade em que o modo servia
   de padrão da máscara); a ordem da MASCARA-NO-PERFIL-01 em `mascara_efetiva` (o
   degrau 2 continua lido e deixa de ser escrito pelo modo); o «Vale no próximo
   jogo que abrir» do «?» do quadro Modo caduca pela palavra de hoje. **Fatos
   errados saem de todos os lugares:** «clicar em Sony DualSense, Xbox ou Steam
   Input não muda nada no daemon» (`painel.py` e a legenda do gerador em
   `aba01.py`), «o chip mostra a escolha» (`a01_jogar.py`), «a ordem mora na dica
   de cada modo» (comentário de `aba01.py`). As linhas de planilha (`docs/data/`:
   a decisão nova em `decisoes-dela.csv`, a nota em `D-O-QUINTO-DEGRAU-DA-RODA`, a
   paridade de modo e máscara, a célula uhid + outra máscara no mapa) são de quem
   coordena, na costura, depois da onda 3.
9. **Os textos da tela** (a dica fica no `title`; o assunto da máscara continua só
   no «?» do cartão):

   | onde | texto |
   | --- | --- |
   | «Sony DualSense» | O Hefesto entrega o controle ao jogo pelo canal próprio do DualSense. |
   | «Xbox» | O Hefesto entrega o controle ao jogo pelo canal comum, o mesmo do controle de Xbox. |
   | «Steam Input» | A Steam entrega os comandos ao jogo; a luz, os gatilhos e o número do jogador ficam com o Hefesto. |
   | «Navegação» | fica como está |
   | «?» do quadro Modo | Como o controle chega ao jogo. O Hefesto tenta na ordem desta lista e para no primeiro que der certo. **PS + R3** pula para o próximo. |

   Sai do «?» do quadro: o «Vale no próximo jogo que abrir», o «como o jogo
   desenha os botões» e a lista de features «do Hefesto em todos», que não tem
   medição hoje.

## §I — A implementação, por símbolo

**Passo 1 — o caminho ganha dono no daemon.**
* `daemon/lifecycle.py`: `DaemonConfig` ganha o caminho ao lado de
  `gamepad_flavor`; `set_gamepad_emulation` e o `_desfecho` aceitam `caminho`
  sem mudar o `flavor` de quem não o manda (a CLI). `apply_profile_mode` aplica o
  caminho do perfil; `_gravar_mascara_do_perfil` ganha nota datada.
* `daemon/subsystems/gamepad.py`: `start_gamepad_emulation_desfecho` compara
  (máscara efetiva, caminho) na idempotência, passa o caminho à fábrica, deixa de
  chamar de degradado o uinput ESCOLHIDO e grava o caminho, não a máscara do chip.
* `integrations/virtual_pad.py`: `make_virtual_pad` só tenta o uhid com caminho
  DualSense **e** máscara efetiva DualSense.
* `daemon/subsystems/coop.py`: `_spawn_player` passa o caminho, e o laço recria
  quem ficou no caminho antigo. `external_mask.vpad_ficou_para_tras` compara
  também o backend; nota datada no degrau 2 de `mascara_efetiva`.
* `daemon/protocols.py`: `DaemonProtocol.set_gamepad_emulation`.
* `utils/session.py`: o caminho persiste **ao lado** da flag, sem mudar o formato
  dela, que o boot lê.
* `daemon/ipc_handlers.py`: `_handle_gamepad_emulation_set` aceita e repassa
  `caminho`; `_handle_gamepad_mask_set` chama o ato do §D.6 depois de gravar;
  o bloco `gamepad_emulation` do `state_full` publica o caminho.

**Passo 2 — o chip escreve e lê o caminho, nunca a máscara.**
* `app/actions/mode_transition.py`: o passo gamepad carrega `caminho`.
* `app/actions/jogar/painel.py`: `CHIPS_DA_ESCADA` nomeia o caminho, com um
  leitor do caminho vivo; sai o fato errado do cabeçalho.
* `interface/pacotes/a01_jogar.py`: `_plano_do_chip`, `_gravar_o_modo_do_chip`,
  `_lembrar_do_chip` (campo próprio, sem mexer no `"mascara"`), `_estado_da_tela`
  (acende pelo caminho publicado), as docstrings de `modo_dualsense` e
  `modo_xbox`; sai «o chip mostra a escolha».
* `interface/pacotes/perfil.py`: `secao_do_modo` grava o caminho sem tocar
  `gamepad_flavor`.
* `app/actions/home_actions.py`: `reconciliar_pendente` conhece o campo novo;
  `mascara_do_aparelho` fica para a máscara.

**Passo 3 — a máscara do cartão vale com o vpad de pé** (§D.6): o P1 por
`start_gamepad_emulation_desfecho` com origem manual, os outros por
`coop.sync(force=True)`.

**Passo 4 — o PS + R3 anda por caminhos e grava no perfil ativo** (§D.4 e §D.5).
* `daemon/subsystems/hotkey.py`: `CICLO_DE_PONTES`, `ponte_atual` (lê o caminho,
  não `device.flavor`) e `_aplicar_ponte` (manda o caminho); gravação no perfil
  ativo depois de o aparelho concordar.
* `integrations/ponte_tentativa.py`: `MASCARAS_AO_VIVO` vira caminhos;
  `gesto_deixou_de_pe` e o tique deixam de alinhar a máscara.
* `integrations/ponte_escada.py`: vocabulário e nota datada na `Ponte`.
* `daemon/launch_env.py`: `arm_launch_profile` e `tique_da_escada` armam e gravam
  o caminho.
* `profiles/manager.py`: `alinhar_o_modo_com_a_ponte`, `confirmar_ponte` e **um
  escritor só** do caminho no perfil ativo, usado pelo chip e pelo gesto.

**Passo 5 — o perfil guarda o caminho.** `profiles/schema.py`:
`ProfileModeConfig.caminho` e, se o PS + R3 carimbar caminho, `PonteConfirmada`.

**Passo 6 — o texto** (§D.9) em `interface/aba01.py`: `MODOS`, o «?» do quadro
Modo, os comentários e a legenda. Regerar e publicar a 01 **na árvore da
sprint** para medir e fotografar; quem coordena regera as dez na costura.

**Planilhas:** `docs/data/` é da onda 3. Se um portão ficar vermelho SÓ por
citação de linha dentro de `docs/data/*.csv` que a sua mudança deslocou, não
toque na planilha: liste cada uma na entrega, com a linha nova pelo símbolo, e
quem coordena reaponta na costura.

## §V — A prova

**As quatro réguas novas, cada uma com a mordida:**

1. `test_o_modo_nao_escreve_a_mascara.py` — cartão do P1 em DualSense; clicar
   «Xbox» pelo gesto real até o handler e o `lifecycle` reais. Exige: vpad
   recriado no uinput, máscara ainda `dualsense`, caminho publicado `xbox`, chip
   «Xbox» aceso, cartão em DualSense, pendência vazia, `mode.caminho = "xbox"` e
   `mode.gamepad_flavor` intocado. Repete com o cartão em Xbox 360 clicando «Sony
   DualSense»: o chip acende o escolhido, nunca a máscara.
   **Morde:** devolver `ponte.mascara` ao `_plano_do_chip`, ou a idempotência só
   por máscara, dá `ja_estava` e «● Vai mudar para: Xbox».
2. `test_a_dica_do_modo_nao_fala_da_mascara.py` — lê o `title` de todo
   `[data-gesto^="modo-"]` e o «?» do quadro Modo **na página publicada** e proíbe
   o vocabulário da máscara (`desenha`, `botões do`, `formato`, `PlayStation`,
   `Xbox 360`, `Nintendo`, `△ ○ ✕ ▢`, `Y B A X`); exige que esse vocabulário
   continue no «?» do cartão.
   **Morde:** devolver a dica de hoje a `aba01.MODOS` e regerar.
3. `test_o_ps_r3_anda_por_caminhos_e_grava_no_perfil.py` — cartão do P1 em
   DualSense, três apertos pelo callback real: `dualsense → xbox → navegação →
   dualsense` no caminho, máscara do vpad sempre `dualsense`, zero
   `ponte_nao_subiu`, e o perfil ativo com o caminho gravado depois de cada
   aperto, sem 180 s e sem jogo.
   **Morde:** `ponte_atual` lendo `device.flavor` trava o ciclo; tirar a gravação
   imediata deixa o perfil ativo intacto.
4. `test_a_mascara_do_cartao_vale_com_o_vpad_de_pe.py` — vpad de pé,
   `display_authority="game"`, `gamepad.mask.set {P1, xbox}`: o vpad do P1 é
   recriado vestindo Xbox 360; com o P2 em co-op, o ciclo forçado recria só o P2.
   **Morde:** tirar a chamada do ato do handler.

**As réguas vizinhas** listadas na posse mudam para a regra dela; cada mudança
diz na entrega o que a régua conferia antes e o que confere agora. Régua que
conferia a regra velha não se apaga sem nota.

**A tela:** foto `--oculta` da 01 antes e depois; clicar os três chips com o
cartão em DualSense e depois em Xbox 360; a contagem de `data-gesto` e de botões
da 01 publicada é a mesma antes e depois. Nenhuma frase nova chega à tela.

**Os portões** até todos verdes (ressalva das planilhas no §I).

## §B — O que só o jogo aberto responde (vai para a MESA-DE-QUATRO-01)

Depois da cura, um DualSense no cabo e, na segunda volta, no rádio; um jogo pela
Steam com as Opções de Inicialização do Hefesto.

1. Cartão do P1 em DualSense, jogo aberto, chip «Xbox»: o controle continua
   mexendo o personagem? Os prompts continuam de PlayStation? A vibração chega?
   Depois «Sony DualSense», e as mesmas três perguntas.
2. Cartão do P1 → «Xbox 360» com o jogo aberto: o controle continua? Os prompts
   viram Y B A X? O chip de modo não muda?
3. PS + R3 quatro vezes dentro do jogo, esperando a luz parar a cada uma: o
   controle responde? Na Navegação o cursor anda? No quarto aperto o jogo retoma?
   Nenhum aperto dá os cinco pulsos vermelhos.
4. Parar no «Xbox» pelo PS + R3, fechar o jogo na hora e abrir a aba Jogar: o
   «Xbox» está aceso? Reabrir o jogo: ele nasce no Xbox?
5. P1 com cartão DualSense e P2 com cartão Xbox 360: trocar o modo pelo chip e
   pelo PS + R3 do P1. Os dois continuam jogando, cada um com os seus prompts?
6. O caminho Xbox com máscara DualSense (uinput vestindo DualSense): o jogo vê o
   controle e a vibração?

## §0 — O processo

ESTUDO (feito, 13/09) → quem coordena escreveu a rota e a posse (§D, §I, §V) →
IMPLEMENTA → VALIDA/CORRIGE. Nada de botão novo; tirar e enxugar pode.
