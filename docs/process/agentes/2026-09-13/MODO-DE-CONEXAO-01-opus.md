# MODO-DE-CONEXAO-01 — o chip e o PS + R3 escolhem o caminho, e a máscara do cartão vale com o vpad de pé

**Branch:** `voo/MODO-DE-CONEXAO-01-opus` · nascida de `onda/1309` (`e2820f17`, conferido)
**Bancada:** não usada — `bancada: false`. Nenhum IPC no socket dela, nenhum nó de
kernel, nenhum perfil real: todo clique foi provado com os métodos REAIS do
`lifecycle.Daemon` e os handlers REAIS do IPC amarrados a um daemon dublado, ou
com o piloto `--oculta` num lar desviado cujo socket resolve dentro do próprio lar.
**A regra:** a de 13/09/2026, com as três mensagens dela citadas na própria
sprint (seção «A regra dela — 13/09/2026»): o modo é a base (o chip e o PS + R3
são o mesmo modo), a máscara vem por cima e independe dele, os dois valem com o
jogo aberto, e o que o PS + R3 escolhe fica no perfil.

---

## O que mudou

### 1. O caminho ganhou dono — daemon e perfil (§I, Passos 1 e 5)

* **Perfil:** `ProfileModeConfig.caminho` (`"dualsense"` · `"xbox"` · vazio). O
  `gamepad_flavor` continua sendo a máscara padrão, e o modo não o escreve mais. O
  serializador omite o `caminho` vazio: um perfil de antes sai byte a byte igual.
* **A regra do canal, num dono só** (`integrations/virtual_pad.py`):
  `caminho_resolvido`, `quer_uhid` e `caminho_do_vpad`. O `uhid` só nasce com
  caminho DualSense **e** máscara efetiva DualSense; perfil sem caminho sai de
  onde saía (§D.1).
* **A causa medida pelo estudo:** `start_gamepad_emulation_desfecho` passou a
  comparar (máscara efetiva, canal) no `ja_estava`. O chip «Xbox» com o cartão do
  P1 em DualSense caía ali e voltava antes de gravar qualquer coisa.
* **Config e sessão:** `DaemonConfig.gamepad_caminho`, escrito só depois de o vpad
  alcançar o pedido (`gamepad._guardar_o_caminho`); `session.save_gamepad_caminho`
  numa flag própria, ao lado da de emulação, sem mudar o formato dela; só o gesto
  manual persiste.
* **IPC:** `state_full.gamepad_emulation.caminho` (`_caminho_publicado`);
  `gamepad.emulation.set` aceita `caminho`, recusa nome desconhecido em voz alta, e
  só devolve o campo a quem o mandou — a resposta da CLI ficou a de sempre.
* **Co-op:** `vpad_ficou_para_tras` compara máscara e canal, e `_spawn_player`
  recebe o caminho.
* **Perfil ativado:** `apply_profile_mode` aplica o `mode.caminho`, e
  `_modo_seria_destrutivo` conta a troca de canal.

### 2. O chip escreve e lê o caminho, nunca a máscara (Passo 2)

* `painel.CHIPS_DA_ESCADA` ganhou `Chip.caminho`, e `painel.caminho_vivo` é quem
  acende o chip (o publicado; sem ele, só o `backend` `uhid` responde por si).
* `a01_jogar`: `_plano_do_chip`, `_lembrar_do_chip` (o eixo `caminho`, sem tocar o
  `mascara`), `_gravar_o_modo_do_chip`, `_estado_da_tela` e `_pendencia`;
  `home_actions.reconciliar_pendente` conhece o eixo novo.
* `perfil.secao_do_modo` delega a `manager.secao_do_modo_com_o_caminho` — o
  escritor único do caminho, usado pelo chip, pelo gesto e pela escada.

### 3. A máscara do cartão vale com o vpad de pé (Passo 3, §D.6)

`Daemon.vestir_a_mascara_do_aparelho(uniq)`: o P1 por
`set_gamepad_emulation_desfecho(True, origin="manual")`, os outros pelo
`coop.sync(force=True)`. O `gamepad.mask.set` chama o ato depois das duas escritas
e devolve `vestiu`.

### 4. O PS + R3 anda por caminhos e grava no perfil ativo (Passo 4, §D.4 e §D.5)

* `hotkey.ponte_atual` lê o caminho de pé; `_aplicar_ponte` manda `caminho=` com
  `flavor=None`; `_gravar_o_modo_do_gesto` grava no perfil ativo logo que o aparelho
  concorda (`manager.gravar_o_modo_no_perfil_ativo`). Quem acha o perfil é
  `manager.nome_do_perfil_que_grava`, as duas pernas da A-PERNA-QUE-FALTA-01 — o
  handler e o gesto perguntam ao mesmo dono.
* A escada: `ponte_tentativa.CAMINHOS_AO_VIVO` e `Passo.caminho`; o alinhamento
  (`alinhar_o_modo_com_a_ponte`, `alinhar_o_modo_do_appid`, `confirmar_ponte`)
  escreve `mode.caminho`; `launch_env._modo_da_ponte` arma o caminho do mesmo nome.
  O carimbo `PonteConfirmada` ficou intocado.

### 5. O texto (Passo 6, §D.9)

`aba01.MODOS` com as três dicas da tabela; o «?» do quadro Modo; a legenda perdeu
«o chip mostra a escolha» e «Clicar em Sony DualSense, Xbox ou Steam Input hoje não
muda nada no daemon». Regerada e publicada com `--publicar 01`. **Contagem da 01
publicada: 23 `data-gesto` e 5 botões, antes e depois.** Nenhuma frase nova na tela.

### 6. As réguas novas — 4 arquivos, 8 casos, verdes

| régua | o que cobra |
| --- | --- |
| `test_o_modo_nao_escreve_a_mascara.py` | cartão do P1 em DualSense, «Xbox» pelo gesto real: vpad recriado no `uinput` vestindo DualSense, caminho publicado `xbox`, chip «Xbox» aceso, cartão em DualSense, pendência vazia, `mode.caminho = "xbox"` e `gamepad_flavor` intocado; e o cartão em Xbox 360 com «Sony DualSense»: chip aceso pelo escolhido, vpad NÃO recriado (mesmo canal) |
| `test_a_dica_do_modo_nao_fala_da_mascara.py` | na página PUBLICADA, o `title` dos quatro `[data-gesto^="modo-"]` e o «?» do quadro Modo sem o vocabulário da máscara; o «?» dos cartões ainda com ele |
| `test_o_ps_r3_anda_por_caminhos_e_grava_no_perfil.py` | três apertos pelo callback real: `dualsense → xbox → mouse_teclado → dualsense`, máscara sempre DualSense, nenhum pulso vermelho, perfil ativo gravado a cada aperto, sem jogo e sem espera |
| `test_a_mascara_do_cartao_vale_com_o_vpad_de_pe.py` | jogo aberto, `gamepad.mask.set {P1, xbox}` recria o vpad do P1 vestindo Xbox 360; com o P2 e o P3 num `CoopManager` REAL, o cartão do P2 recria só o P2 |

### 7. As réguas vizinhas — o que conferiam antes e o que conferem agora

Toda mudança leva uma nota «AJUSTADA À REGRA DELA — MODO-DE-CONEXAO-01» no
próprio arquivo.

| régua | antes | agora |
| --- | --- | --- |
| `test_hotkey_ponte_cycle.py` | o gesto pedia `flavor="xbox"` e o dublê trocava a máscara do device | o gesto pede `caminho=` com `flavor=None`; a máscara do device fica |
| `test_a_aba_01_jogar_fecha_as_linhas.py` | o chip clicado gravava `gamepad_flavor == "xbox"` | grava `caminho == "xbox"`, com `gamepad_flavor` vazio |
| `test_mascara_por_controle_manda_no_vpad.py` | o `_try_uhid` recebia `"xbox"` e recusava sozinho | o gate `quer_uhid` vem antes e o `_try_uhid` nem é chamado; o dublê do churn aceita os argumentos novos |
| `test_o_gesto_da_ponte_e_universal.py` | o dublê trocava a máscara pelo `flavor` pedido | o dublê guarda o caminho na config; as sequências cobradas são as mesmas |
| `test_a_mascara_do_gesto_volta_para_o_perfil.py` | o `xbox` do gesto voltava em `mode.gamepad_flavor`, e o arming armava `config.gamepad_flavor` | volta em `mode.caminho` (a máscara padrão fica), o arming arma `config.gamepad_caminho`, e o «nada gravado» cobra também o caminho vazio |
| `test_ponte_escada_laco_01_quem_sobe_a_escada.py` | trilha de três posições; `passo.mascara` | a quarta posição é o caminho; `passo.caminho` |
| `test_a_aba01_le_o_estado_em_vez_de_cravar.py` | trocava `mascara_do_aparelho` e cobrava o chip de modo pela máscara | troca `painel.caminho_vivo`, e uma máscara trocada não acende chip de modo; o estado Xbox publica o caminho |
| `test_a_faixa_de_pendencia_da_jogar.py` | o chip «Xbox» anotava o eixo `mascara` | anota o eixo `caminho`; os estados vivos publicam o caminho |

`test_ponte_escada.py`, `test_ponte_gravada_no_launch.py`,
`test_a_mascara_mora_no_perfil.py`, `test_profile_mode.py`,
`test_verdade01_o_retorno_que_mentia.py` e `test_a_mascara_persiste_ate_ela_mudar.py`
passaram sem mudança. Os 14 da posse: **135 + 100 verdes**, os mesmos números da
base.

**Fora da posse, e declarado:**

* `tests/unit/test_o_reconectar_nao_muda_de_lugar.py` — dois casos conferiam a
  regra velha (o chip pedia `flavor: "xbox"` e acendia pelo `flavor`); agora pedem e
  acendem pelo caminho, com a nota.
* `test_a_perna_que_falta_01_a_segunda_perna_do_perfil_ativo.py` (o censo de quem lê
  `store.active_profile`) e `test_ipc_gamepad.py` (a resposta exata) ficaram
  intocados: curei no código — `_perfil_que_grava` volta a ler o store e passa o
  nome ao dono, e o `caminho` só volta a quem o pediu.
* **Citações de linha que a mudança deslocou:** 32 trocas em 16 arquivos de
  `src/`, cada uma conferida pelo símbolo (ou pelo conteúdo que a base
  `e2820f17` apontava); e a tabela gerada de `docs/protocol/ipc-unix-socket.md`
  regerada por `scripts/gerar-contrato-ipc.py`. As duas réguas de citação estavam
  verdes na base extraída do git, então o que ficou vermelho era deslocamento meu.

---

## Qual mordida prova

Cada mordida arrancou UM trecho, rodou só a régua dela, devolveu os bytes e
conferiu o md5 (a da dica regerou e publicou a 01 nos dois sentidos; as duas
páginas voltaram idênticas).

| mordida | régua | reprovou | devolvida |
| --- | --- | --- | --- |
| `_plano_do_chip` manda a máscara (`mascara=` no lugar de `caminho=`) | `test_o_modo_nao_escreve_a_mascara` | **2 de 2** — «o vpad não foi recriado: o daemon respondeu `ja_estava`», e «o caminho escolhido não ficou» | sim |
| idempotência só por máscara (sem o `mesmo_canal`) | `test_o_modo_nao_escreve_a_mascara` | **1 de 2** — o chip «Xbox» com o cartão em DualSense (o outro caso é o mesmo canal, e não depende desta cura) | sim |
| a dica antiga volta a `aba01.MODOS` e a 01 é publicada | `test_a_dica_do_modo_nao_fala_da_mascara` | **1 de 3** — `modo-dualsense: ['desenha', 'botões do', 'PlayStation']` | sim, páginas idênticas |
| `ponte_atual` volta a ler `device.flavor` | `test_o_ps_r3_anda_por_caminhos_e_grava_no_perfil` | «aperto 1: o ciclo andou ['dualsense']» | sim |
| sem a chamada `_gravar_o_modo_do_gesto` | `test_o_ps_r3_anda_por_caminhos_e_grava_no_perfil` | «aperto 1: o perfil ativo ficou em `caminho=None`» | sim |
| o `gamepad.mask.set` sem chamar o ato (`vestiu: None`) | `test_a_mascara_do_cartao_vale_com_o_vpad_de_pe` | **2 de 2** — «o vpad do P1 continuou o mesmo», e `None == 'coop'` | sim |

### A foto e o clique

* **As fotos**, nesta pasta: `MODO-DE-CONEXAO-01-ANTES-01-publicado.png` e
  `MODO-DE-CONEXAO-01-DEPOIS-01-publicado.png` (`olhar.py --publicado`), e
  `MODO-DE-CONEXAO-01-ANTES-01-vivo-no-lar-desviado.png` e
  `MODO-DE-CONEXAO-01-DEPOIS-01-vivo-no-lar-desviado.png` (`hefesto_vivo.py
  --oculta`, com `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`). O layout é o mesmo
  antes e depois: o texto novo mora no `title` e no «?». No lar o daemon é mudo
  (o socket resolveu dentro do lar); o «Perfil ativo: Bancada» da foto de depois é
  o marcador que o roteiro do clique gravou naquele lar.
* **O clique**, com o roteiro no molde do `medir.py` do estudo (daemon dublado com os
  métodos reais, lar desviado, HOME e os cinco `XDG_*` conferidos antes):
  * **cartão do P1 em DualSense, «Xbox»:** `gamepad.emulation.set {caminho: xbox}` →
    vpad recriado no `uinput` vestindo `054c:0df2`, caminho publicado `xbox`, chip
    «Xbox» aceso, cartão em DualSense, pendência vazia, perfil `caminho: xbox` com
    `gamepad_flavor: dualsense`. «Sony DualSense» devolve o `uhid`.
  * **cartão do P1 em Xbox 360, «Sony DualSense»:** vpad NÃO recriado (mesmo canal),
    chip «Sony DualSense» aceso, cartão em Xbox 360.
  * **cartão do P1 → Xbox 360 com o jogo aberto:** `vestiu: aplicado`, vpad recriado
    vestindo `045e:028e`; e de volta ao DualSense, o `uhid` de novo.
  * **PS + R3 com o cartão em DualSense:** `dualsense → xbox → mouse_teclado →
    dualsense`, `054c:0df2` em todo aperto, nenhum pulso vermelho, o perfil ativo
    gravado a cada aperto (origem `ps_r3`). Com o cartão em Xbox 360: `xbox →
    mouse_teclado → dualsense → xbox → mouse_teclado`, sem pulso vermelho.

---

## O que NÃO verifiquei

* **Nada com o jogo aberto nem com o controle na mão** — é a §B da sprint, da
  MESA-DE-QUATRO-01: se o jogo sobrevive à recriação no outro canal, os prompts, a
  vibração no caminho Xbox com máscara DualSense, o P2 jogando enquanto o P1 troca.
* **O daemon real:** nenhum IPC no socket dela; o boot lendo a flag do caminho só
  foi exercitado pelo código, não num daemon de pé.
* **A suíte inteira:** só réguas pontuais, em lotes — os 14 da posse, as 4 novas e
  os 161 arquivos que citam os símbolos mexidos.
* **As 17 citações de `docs/data/mapa-controles.csv`** que a mudança deslocou, sem
  tocar a planilha (é da onda 3). Pelo símbolo, onde cada coisa está hoje:
  * linha 23 (`audio.microfone@dualsense`, `radio_codigo_ref`): `apply_profile_mic`,
    def na linha 3477 de `daemon/lifecycle.py` (a planilha cita 3343);
  * linha 23 (`radio_detalhe`): `_metade_do_canal`, def na linha 1514 de
    `daemon/subsystems/hotkey.py` (cita 1444);
  * linhas 57 e 256 (cabo e rádio): `_next_player_index`, def na linha 837 de
    `daemon/subsystems/coop.py` (cita a faixa 823-833);
  * linhas 87 e 88 (`cabo_evidencia` e `cabo_codigo_ref`): `_dispatch_mouse_emulation`,
    def na linha 4097 de `daemon/lifecycle.py` (cita a faixa 3963-3974); e as duas
    `nota`, que citam a faixa 4905-4915 — a chamada
    `self._dispatch_mouse_emulation(state, emu_buttons)` do laço, hoje na linha 5039;
  * linha 275 (`plataforma.vigia_zumbi@pro`): o `EvdevReader(` do `_spawn_player`,
    na linha 969 de `daemon/subsystems/coop.py` (cita 950);
  * linha 279 (`plataforma.vpad@sn30`, cabo e rádio): `_spawn_player`, def na linha
    954 de `daemon/subsystems/coop.py` (cita 940).
* **`test_daemon_reconnect_loop.py::test_run_inicia_ipc_antes_de_conectar`** está
  vermelho, e vermelho igual na base `e2820f17` extraída do git (o `join` da thread
  do microfone por rádio estoura os 2 s do desligamento). Não é desta sprint.

## O que sobrou para o próximo

* **A Navegação poda a máscara padrão do perfil:** a regra da seção `mode` zera o
  `gamepad_flavor` fora do modo jogo (o «JSON limpo» da `secao_do_modo`, travado por
  `test_o_quadro_do_modo_grava_no_perfil.py`). Medido no clique: passar pela
  Navegação e voltar deixa `gamepad_flavor` vazio — o caminho sobrevive, e a máscara
  do cartão também. Mudar isso é decidir o que o perfil guarda fora do modo jogo.
* **O carimbo por jogo não tem campo de caminho:** `PonteConfirmada.gamepad_flavor`
  guarda o nome do caminho, e `mesma_ponte` o compara com o `mode.gamepad_flavor`.
  Os nomes coincidem hoje; um campo próprio é o passo seguinte se um dia não
  coincidirem.
* **O caminho que vem do perfil não vai à flag** — só o gesto manual persiste, pela
  mesma regra da flag de emulação.
* **A gravação do PS + R3 no perfil é síncrona** dentro do callback do gesto (um
  `load` + `save` por aperto que muda alguma coisa).
* **Reativar o perfil não veste a máscara do cartão:** `apply_profile_mode` continua
  sem recriar pela máscara efetiva; quem veste com o vpad de pé é o gesto do
  cartão (§D.6).
* **Da costura (§D.8):** a célula `uhid` + outra máscara no mapa, a decisão nova em
  `decisoes-dela.csv`, a nota em `D-O-QUINTO-DEGRAU-DA-RODA`, a paridade de modo e
  máscara, e as 17 citações acima.
