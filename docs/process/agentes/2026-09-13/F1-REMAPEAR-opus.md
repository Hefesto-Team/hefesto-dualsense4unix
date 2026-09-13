# F1-REMAPEAR — a entrega do agente IMPLEMENTA (13/09/2026)

Sprint: [F1-REMAPEAR](../../sprints/2026-09-11-F1-REMAPEAR-as-vinte-e-duas-linhas-e-o-motor-que-nao-existe.md),
lote `1309-onda1`, branch `voo/F1-REMAPEAR-opus`, nascida de `onda/1309` = `249af1f6`.
O estudo é o item F1-REMAPEAR da triagem das abertas, somado à ROTA CORRIGIDA
da própria sprint. Sem aparelho: bancada não exigida (`bancada: false`), toda
prova é com dublê.

## O que mudou

**O motor nasceu** — `src/hefesto_dualsense4unix/core/remapeamento_de_botao.py`,
puro, sem nenhum import do projeto no topo (o `acoes_de_botao` arrasta
`integrations/uinput_mouse`, e este módulo roda no caminho quente):

- `resolver(mapa)` devolve o mapa limpo ou `RemapeamentoRecusadoError` com o
  motivo e os botões: botão desconhecido; o PS em qualquer lado; linha fora do
  alcance (a direção dos dois analógicos e o clique do touchpad, nos dois
  lados); dois botões para o mesmo destino (nomeia os dois e o destino). A
  troca de um botão por ele mesmo some.
- `traduzir(apertados, l2, r2, mapa)` aplica o mapa sobre o RETRATO do tique,
  nunca em cadeia — é o que faz a troca dupla funcionar. Os gatilhos levam o
  eixo junto: gatilho → botão manda o bit; botão → gatilho manda força 255 e o
  bit; gatilho ↔ gatilho troca o eixo.
- `definir_ativo(store, mapa)` / `ativo(store)`: o mapa ativo mora CONGELADO
  (`MappingProxyType`) no `StateStore` do daemon. Por que o `store` e não um
  canal novo na fábrica do gerente: a rota do boot
  (`daemon/connection.py::restore_last_profile`) monta o `ProfileManager` à mão
  e não recebe canal nenhum, mas TODAS as rotas que ativam perfil passam
  `store=daemon.store`, e o poll loop já lê o `store` por tique.

**O que a troca alcança são 16 das 22 linhas** (`REMAPEAVEIS`): os quatro da face,
L1, R1, L2, R2, L3 e R3 (clique), o D-pad e Options e Share. A régua prende a
lista ao `BOTOES` do produto e ao vocabulário do `EvdevReader.BUTTON_MAP`.

**O campo** — `Profile.remapeamento: dict[str, str] | None` (`profiles/schema.py`),
global no perfil (D-0809-A-NAVEGACAO-E-GLOBAL-NO-PERFIL). O validador chama o
`resolver` do motor; `{}` vira `None`; e o serializador do `Profile` OMITE a
chave quando `None`, no mesmo molde do `ponte`, para todo caminho de dump e não
só o save.

**A aplicação** — `ProfileManager.apply_remapeamento` (`profiles/manager.py`),
chamado pelo `activate` logo depois do `apply_button_actions`. Deposita sempre,
inclusive `None`: o perfil sem troca apaga a do anterior. Um mapa torto que
chegue por `model_copy` sem validação não derruba a ativação — vira `falhou` no
relatório e aviso no journal.

**A tradução, nos dois pontos da ROTA CORRIGIDA e só neles:**

- `daemon/subsystems/gamepad.py::dispatch_gamepad` — o primário, logo antes do
  `forward_analog`/`forward_buttons`;
- `daemon/subsystems/coop.py::CoopManager.forward_all` — os secundários, o mapa
  lido uma vez por tique.

Nos dois arquivos o import do motor mora logo acima de quem o usa (antes do
`dispatch_gamepad`; depois da classe `CoopManager`), com `# noqa: E402` e a razão
escrita: no topo ele empurrava seis linhas das funções que o
`docs/data/mapa-controles.csv` cita por número, e aquele CSV não é desta sprint.

Sem troca, o `if troca:` pula e o jogo recebe o MESMO objeto — nada é alocado.
O PS, os gestos, o atalho e o teclado e o mouse emulados continuam lendo o
`buttons_pressed` original no laço do daemon.

**O Salvar da aba Perfis não apaga a troca** — `app/draft_config.py` ganhou
`source_remapeamento` (passthrough, no molde do `source_button_actions`).
`to_profile` reconstrói o perfil do zero, e sem isto todo "Salvar Perfil"
zeraria a troca que ela acabou de guardar. **Arquivo fora da `posse:` da
sprint** — ver o último cabeçalho.

**A tela "Trocar os botões"** (aba 06), sem botão novo e sem frase nova:

- `pacotes/a06_navegacao.py`: `PREFIXO_DA_TROCA`, `SEM_TROCA`, `ROTULOS_DA_TROCA`
  (rótulo da `<option>` → id do botão); a pintura das 16 linhas
  (`troca-<botão>`) com a trava `_TROCANDO`, irmã do `_MEXENDO`; e os quatro
  gestos: `linha-de-troca` (anota; recusa na hora o PS e o que está fora do
  alcance), `fechar-troca` (larga), `guardar-remapeamento`
  (`grava="gravar_e_reaplicar"`, com a trava contra o apagador do
  `guardar-definicoes`) e `padrao-remapeamento` (zera só `remapeamento`). Os
  dois do rodapé saíram do `SEM_GESTO` (de seis para quatro) e os quatro entraram
  no `SEM_ECO`, com a razão escrita.
- `interface/aba06.py`: as 22 listas ganharam `data-gesto="linha-de-troca"` e
  `data-linha`; as 16 que a troca alcança ganharam `data-campo`; o `×` e o
  «Cancelar» ganharam `fechar-troca`. O gerador PARA se a lista de destinos que
  ele deriva do CSV das peças divergir de `ROTULOS_DA_TROCA`, e a
  autoconferência cobra os três endereços.
- **A única mudança visível**: a dica `?` da tela perdeu a frase *"Valem para o
  controle que navega o PC: o P1…"*. Ela é verdade sobre as Definições e FALSA
  sobre a troca, que vale nos quatro controles. Tirar, sem frase nova.
- `mockup/06-navegacao.html` e `interface/paginas/06-navegacao.html` regerados
  pelo gerador e publicados com `check_o_desenho_aprovado.py --publicar 06`.
  Pelo `o_que_se_ve` do portão do desenho, a diferença visível entre as duas
  páginas antes da publicação era uma linha: a da dica.

**Fatos substituídos**, em todos os lugares onde estavam:

- *"o primário não passa por `forward_buttons`"* — na §2 e na §4 da sprint, e na
  entrada do `SEM_GESTO` que saiu;
- *"os Guardar das outras duas telas não têm dono"* — nos docstrings de `drop()`
  e `tela_de_botoes` do gerador;
- a linha 228 da paridade (`docs/data/paridade-gtk-html.csv`), que dizia
  `SEM_GESTO`, agora aponta o gesto `guardar-remapeamento`; as linhas 226 e 227
  apontavam o `SEM_GESTO` num docstring do gerador que mudou, e passaram a
  apontar o dono dele, o pacote.

**Réguas vizinhas acertadas pela mudança, com nota datada em cada uma:**

- `test_a_06_a_identidade_vem_de_cima.py` e a autoconferência do gerador: o
  `quem-navega` está numa dica, não em duas;
- `test_a_06_o_duble_decide_o_indecidivel.py`: o dublê ganhou uma RODA de troca
  sobre `REMAPEAVEIS`, para os 16 endereços novos discordarem do desenho, e a
  conta de endereços soma as linhas da troca lendo o dono da lista;
- `test_perfil_salva_tudo_cobertura_das_secoes.py`: `remapeamento` em `ISENTOS`,
  com a razão (isenção do instrumento GTK, como a do `button_actions`);
- `scripts/check_cabo_bt_perfil_controle.py`: `linha-de-troca` e `fechar-troca`
  classificados como gestos de tela.

**A régua nova** — `tests/unit/test_migra_navegacao_13_o_remapeamento_botao_a_botao.py`,
30 casos: o motor; os dois `forward_buttons`; o jogo recebendo o mesmo objeto
sem troca; a tradução morando em dois lugares só (por AST sobre `src/`); o campo
omitido; a ativação depositando e apagando; o Salvar da aba Perfis; os quatro
gestos; a página publicada; e o clique na página publicada num Chrome com o
`BOOTSTRAP` do piloto, até o disco de mentira.

## Qual mordida prova

As oito, rodadas pelo roteiro `mordidas.py` do scratchpad. Cada caso arranca a
cura, roda só os testes que devem reprovar, DEVOLVE o arquivo e confere o
sha256. No fim, o `git diff` inteiro da árvore saiu idêntico ao de antes das
mordidas. A saída abaixo é da última volta, depois de o import mudar de lugar.

**O INSTRUMENTO MENTIU UMA VEZ, e a cura é dele.** Rodadas de novo depois da
mudança do import, as mordidas deram 7 de 8: a M2 DEVOLVIDA reprovou, com o sha
da fonte certo. A causa, medida lendo o cabeçalho do `.pyc`: a mutilação
`if troca:` para `if False:` tem o mesmo tamanho, a gravação caiu no mesmo
segundo, e o `.pyc` só guarda mtime em segundos e tamanho, então o Python rodou
o bytecode da versão mutilada. Com um `touch` a régua passou; numa terceira
volta, a M1 ARRANCADA passou pelo mesmo motivo, no sentido contrário. O roteiro
passou a dar a cada pytest um `PYTHONPYCACHEPREFIX` vazio, e a quarta volta deu
8 de 8. Quem escrever mordida que troca palavra de mesmo tamanho cai nisso.

```
M1 a troca arrancada do primário (gamepad.py: if troca -> if False)
   arrancada: rc=1  E AssertionError: o jogo recebeu [frozenset({'cross'})] — a troca
                    do perfil não chegou ao `forward_buttons` do primário
   devolvida: rc=0  2 passed
M2 a troca arrancada do co-op (coop.py)
   arrancada: rc=1  E AssertionError: o jogador 2 mandou [frozenset({'cross', 'l2_btn'})] ao jogo
   devolvida: rc=0  1 passed
M3 o mapa aplicado em cadeia (remapeamento_de_botao.traduzir)
   arrancada: rc=1  E AssertionError: assert frozenset({'cross'}) == {'circle'}
   devolvida: rc=0  1 passed
M4 a trava do apagador arrancada (a06_navegacao.guardar_remapeamento)
   arrancada: rc=1  E Failed: DID NOT RAISE RuntimeError
   devolvida: rc=0  1 passed
M5 o transporte do Salvar arrancado (draft_config.to_profile)
   arrancada: rc=1  E AssertionError: assert None == {'cross': 'circle'}
   devolvida: rc=0  1 passed
M6 o vazio deixa de virar None (schema._validate_remapeamento)
   arrancada: rc=1  E AssertionError: assert {} is None
   devolvida: rc=0  1 passed
M7 a ativação sem o depósito (manager.activate)
   arrancada: rc=1  E AssertionError: a ativação não depositou a troca no `store`
   devolvida: rc=0  1 passed
M8 a página publicada sem o data-linha da Cruz
   arrancada: rc=1  E AttributeError: 'NoneType' object has no attribute 'group'
                    E playwright ... Failed to find element matching selector
                      "#remapeamento select[data-linha="cross"]"
   devolvida: rc=0  2 passed
RESULTADO: 8 de 8 · problemas=0
```

**Réguas afetadas, com tudo devolvido** — 14 arquivos, rodados juntos depois do
último conserto (a régua nova, a da saída de agente, as de gamepad e co-op, o
`draft_config`, a fábrica do gerente, quem-é-quem, a cobertura do perfil, duas
da 06, o que cada botão faz, os LEDs do co-op, o sabor do gamepad e as linhas da
06): `1083 passed in 29.46s`. `mypy` nos sete arquivos de produto: `Success: no
issues found in 7 source files`. `ruff check src/ tests/`: `All checks passed!`.
`check_paridade_gtk_html.py` rc=0 e `check_cabo_bt_perfil_controle.py` rc=0.

**Os portões inteiros**, com `git add -A` antes e esperados pelo PID:
`TODOS VERDES — 60 portões.` Foi a segunda volta; a primeira deu os três
vermelhos descritos logo abaixo. Depois do verde, esta entrega ganhou só este
parágrafo, e a régua de glifo, a de acento e a de citação de linha rodaram de
novo sobre ela.

**Os três vermelhos que a primeira volta deu, e o que cada um era:**

- `test_quem_e_quem_02…` (129 casos): o dump do `Profile` passou a ter
  `remapeamento: null`, e a tupla de registro do loader não o conhece. Curado no
  ESQUEMA, no molde do `ponte` — o serializador omite a chave. O loader não foi
  tocado;
- `test_a_06_o_duble_decide_o_indecidivel.py`: `conferi 49 endereço(s) … e a
  aba tem 33`. Eram os 16 novos, e a conta passou a lê-los do dono;
- a paridade: `sinal-sumiu` nas linhas 226 e 227 (ver acima).

**Os três vermelhos da primeira volta dos portões inteiros**
(`REPROVOU: 3 vermelho(s) de 60`), e o que cada um era:

- `citacoes-de-linha`: 8 células do `docs/data/mapa-controles.csv` citavam
  `gamepad.py:1292` (`apply_game_rumble`), `gamepad.py:1400`
  (`apply_game_lightbar`), `coop.py:940` (`_spawn_player`) e `coop.py:950`
  (`EvdevReader`), e o import no topo empurrava as quatro seis linhas. As
  chaves: `combinacao.rumble_simultaneo@pro`, `luz.replica_output_jogo@dualsense`,
  `plataforma.vigia_zumbi@pro`, `plataforma.vpad@sn30` e
  `vibracao.rumble.passthrough@dualsense`. Curado mudando o import de lugar; o
  CSV não foi tocado, e as quatro âncoras voltaram à linha citada;
- `citacoes-no-codigo`: dez comentários de `src/` citavam por número linhas do
  `profiles/manager.py` e do `profiles/schema.py` que a sprint deslocou.
  Reapontados um a um pelo símbolo, medido com `grep -n`, e conferidos pela
  própria régua (`enderecos_envelhecidos()`: zero vivas);
- `saida-de-agente`: esta entrega tinha o glifo da Cruz do controle, que o hook
  bloqueia. Trocado pelo nome do botão.

**A foto** — a tela `#remapeamento` da página publicada, num Chrome headless,
com a dica aberta:
[antes](F1-REMAPEAR-ANTES-troca-de-botoes.png) ·
[depois](F1-REMAPEAR-DEPOIS-troca-de-botoes.png). As 22 listas, os botões e o
rodapé são os mesmos; a dica perdeu a frase de quem navega. Os atributos lidos
no DOM dizem: antes, 22 listas sem gesto, sem linha e sem campo; depois, 22 com
`linha-de-troca`, 22 com `data-linha`, 16 com `data-campo`, e dois
`fechar-troca`.

**O clique** — no Chrome, com o `BOOTSTRAP` do piloto injetado: escolher
«Círculo» na linha da Cruz manda `linha-de-troca` com `linha=cross`; o «Guardar»
manda a `forma` com as 22 linhas; e essa forma, entregue ao gesto com um disco de
mentira, grava `{"cross": "circle"}`. De ponta a ponta, com dublê nos dois
pontos: a tela manda «Cruz passa a ser Círculo», o «Guardar» grava, a ativação
deposita, e o `forward_buttons` do dublê recebe `circle`.

**O piloto no WebKit, oculto** — `hefesto_vivo.py --oculta --abre 06 --segundos 8`
com `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, contra o daemon vivo. O
resultado: `06-navegacao.html  79 tiques  1 pintura  33 valores`, sem Traceback.
Nenhum gesto foi clicado. Os perfis dela foram copiados antes e o md5 dos 159
arquivos saiu IGUAL depois.

## O que NÃO verifiquei

- **Nada no aparelho nem no jogo.** Os dois `forward_buttons` foram exercidos com
  dublê. O vpad uhid e o uinput de verdade, a máscara Xbox/Nintendo e um jogo
  lendo o Círculo no lugar da Cruz ficam para a bancada (MESA-DE-QUATRO-01).
- **O clique no WebKitGTK.** O clique foi dirigido no Chrome, que mede o contrato
  do bootstrap. O piloto WebKit rodou só o passeio da aba, sem clicar gesto
  nenhum, porque o «Guardar» grava no perfil real dela.
- **A rota do boot com o daemon de pé.** Que `restore_last_profile` deposita a
  troca decorre de ele passar `store=daemon.store` e chamar `activate`, e o
  `activate` foi medido com dublê. Não subi daemon nenhum.
- **O gatilho → botão no jogo.** A tradução usa o bit digital `l2_btn` que o
  firmware manda, e não o limiar do eixo. Não medi em que força o bit acende.
- **O custo por tique COM troca.** A régua cobre o caso sem troca (o mesmo
  objeto, sem alocar); com troca, o `traduzir` monta um conjunto e um dicionário
  pequenos por tique, e não medi o custo.
- **As seis linhas sem endereço de pintura** (a direção dos dois analógicos, o
  PS e as três regiões do touchpad): escolher algo nelas é recusado na hora, mas
  a lista continua mostrando a escolha recusada até a página ser recarregada —
  nada as repinta.
- **A suíte inteira** não foi rodada, por ordem do despacho.

## O que sobrou para o próximo

- **Arquivos fora da `posse:` da sprint que a cura exigiu**, para quem costura:
  - `src/hefesto_dualsense4unix/app/draft_config.py` (o transporte do Salvar);
  - `docs/data/paridade-gtk-html.csv` (linhas 226 a 228);
  - `scripts/check_cabo_bt_perfil_controle.py` (dois gestos classificados);
  - três réguas existentes: `test_a_06_a_identidade_vem_de_cima.py`,
    `test_a_06_o_duble_decide_o_indecidivel.py` e
    `test_perfil_salva_tudo_cobertura_das_secoes.py`;
  - `mockup/06-navegacao.html` e `interface/paginas/06-navegacao.html`, que se
    REGERAM na costura e nunca se mesclam à mão;
  - só o número de linha dentro de um comentário, reapontado pelo símbolo:
    `core/acoes_de_botao.py`, `core/rumble.py`, `daemon/ipc_handlers.py`,
    `daemon/subsystems/hotkey.py`, `interface/aba10.py` e
    `interface/pacotes/a08_conexoes.py`. Se outra sprint do lote mexer no
    `manager.py` ou no `schema.py`, esses números mudam de novo na costura, e a
    régua `citacoes-no-codigo` diz quais.
- **Colisão provável na costura**: `profiles/schema.py` e `profiles/manager.py`
  com a JOGO-SEM-EXCLUSIVIDADE-01; as páginas 06 com ALTURA-DA-VISTA-01 e
  DICA-DA-COR-01 (regerar depois delas).
- **A dica da troca não diz mais onde a troca vale.** Dizer *"vale nos quatro
  controles, no que o jogo vê"* é texto novo de tela, e ficou de fora de
  propósito.
- **Achado de passagem, não medido rodando**: a rota do boot
  (`daemon/connection.py::restore_last_profile`) monta o gerente à mão SEM o
  `ps_action_sink`. Pela leitura, a escolha que o perfil dá ao botão PS não
  chega ao `ps_solo` no boot, só na primeira troca de perfil. É a mesma forma de
  defeito que me fez pôr a troca no `store`.
- **Descrição errada, não tocada**: `check_cabo_bt_perfil_controle.py` descreve
  `linha-de-botao` como *"escolhe a linha do botão a remapear"*, e esse gesto é o
  da tela de Definições, não o da troca.
- **Para a SPECS-A-PROCEDENCIA-01**, pela chave do mapa: `entrada.botoes` e
  `entrada.bruta` do DualSense ganharam um passo entre a entrada e o gamepad
  virtual (a troca do perfil). Medido só no degrau MONTOU, com dublê, sem
  transporte.
