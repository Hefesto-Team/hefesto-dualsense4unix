# A manhã de 28/09: o modo com um dono, o som com um leitor, o Salvar que lê o perfil e a raiz limpa

Registro técnico da rodada de 28/09/2026: seis frentes (o modo, o pad do modo Xbox, o servidor de som, o Salvar, a raiz e o dono das formas do endereço), com o que se mediu, a causa, a cura e o que ficou aberto.

> Cada frente foi entregue e depois conferida por uma segunda passada, que
> refez as mordidas, procurou as que faltavam e corrigiu na mesma branch. Os
> números abaixo são das duas passadas. Nenhuma frente mexeu na tela, então
> não houve foto nem clique; a prova no aparelho ficou para depois do install.

| frente | sprint | o que muda para quem usa |
|---|---|---|
| o modo com um dono | `O-MODO-XBOX-NAO-E-QUEDA-02` | o P1 é o controle da carta 1; todo restart do pad diz quem pediu; o boot sobe no modo do perfil |
| o pad que o jogo vê | `NO-MODO-XBOX-TUDO-FUNCIONA-01` | no modo Xbox escolhido, todo pad nasce Xbox 360, de P1 a P4 |
| o som com um leitor | `O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01` | o daemon lê o servidor de som por um retrato só; no aparelho, a meta de menos de 1 `pactl` por segundo (hoje 23) ainda espera a prova |
| o Salvar lê o perfil | `O-SALVAR-E-O-APLICAR-LEEM-O-PERFIL-01` | o Salvar e o Aplicar deixam de gravar o que o aparelho está fazendo |
| a raiz limpa | `A-RAIZ-SO-COM-O-PRODUTO-01` | a raiz vai de 35 para 27 entradas; o atalho do menu abre pelo `run.sh --gui` |
| as formas do endereço | `O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01` | nasce o dono único da máscara do endereço (o produto passa a usá-lo na rodada seguinte) |

## 1. O modo tem um dono (`O-MODO-XBOX-NAO-E-QUEDA-02`)

**O defeito.** O modo do P1 (DualSense pelo uhid, Xbox pelo uinput) tinha
vários escritores, e oito caminhos recriavam o pad sem dizer por quê. O boot
subia no modo de fábrica e trocava depois, com dois `gamepad_emulation_started`
quando havia foco. O primário era «o primeiro que conectou», e não o controle
cuja lâmpada acende 1.

**A cura, por item:**

- **Um dono.** O slot da sessão é o dono do modo:
  `daemon/subsystems/gamepad.py:1515` (`caminho_da_sessao`). Todo restart do P1
  lê dele e grava no diário `p1_reerguido motivo=…` (`ordem_do_coop`,
  `revive_pos_falha_total`, `volta_do_steam_input`, `promocao_uhid`,
  `mascara_do_cartao`, `saida_do_modo_nativo`, `dois_controles_na_mesa`,
  `mascara_reconciliada`). O cartão escolhe máscara, não modo
  (`caminho_e_escolha=False`, `gamepad.py:1586`). O arquivo do modo passa a ser
  JSON `{caminho, origem, quando}`, lido por
  `utils/session.py:410` (`load_gamepad_caminho_com_origem`); o texto antigo é
  devolvido uma vez, com origem `migracao_unica`. O `load_gamepad_caminho`
  antigo saiu.
- **A máscara antes do modo.** `profiles/manager.py:507` (`apply_emulation`)
  aplica `apply_controller_mascaras` antes do aplicador do modo. O «por último»
  que o comentário antigo afirmava era falso. O P1 veste a máscara do perfil
  novo na mesma ativação, nas três origens (troca automática, manual e
  lançamento).
- **O boot no modo do perfil.** `daemon/connection.py:415`
  (`perfil_que_o_boot_restaura`) semeia caminho e máscara antes do primeiro
  pad: um `gamepad_emulation_started` só, com e sem foco.
- **O P1 é a carta 1.** O backend elege o primário pela carta menor (a lâmpada;
  no boot, a fila gravada, via `daemon/subsystems/identity.py:1583`,
  `posto_na_fila`). O posto ocupado só troca por carta estritamente menor
  (`core/backend_pydualsense.py:5640`), e o tique lento chama `seguir_a_carta`
  (`backend_pydualsense.py:5669`; `daemon/lifecycle.py:3250`). Controle novo
  entra no fim da fila e não rouba o posto. A sprint cita a frase dela de 27/09,
  23h40: «o led do player 1 não é simbólico».
- **O número não pula.** `daemon/subsystems/coop.py:1850`
  (`_numeros_em_duas_passadas`): quem tem carta fica com ela; quem está fora
  (troca de transporte) vai para o assento guardado, o mesmo que dá nome ao
  microfone. `coop.py:1881` repinta a lâmpada pela camada do co-op quando o
  número muda, sem hotplug. É o caso do controle que acendia 5 e das lâmpadas
  que nunca se repintavam.

**O que a conferência achou e curou:**

- `perfil_que_o_boot_restaura` não seguia a ordem do restore: com o marcador
  apontando um perfil de janela e a sessão apontando outro, o P1 nascia no
  modo de um perfil que ninguém ativou.
- **A terceira porta do contágio (`CAMINHO-CONTAGIO-01`).** Um perfil `gamepad`
  sem `caminho`, ativado depois do Freestyle em Xbox, herdava o Xbox: se a
  máscara era igual, `apply_profile_mode` (`daemon/lifecycle.py:2033`) não
  pedia nada. As réguas de 17 a 19/09 chamavam o start direto, sem a ativação.
  Agora o perfil sem caminho volta ao de fábrica. Efeito colateral aceito: com
  jogo sem perfil já na autoridade, o modo padrão responde
  `ADIADO_JOGO_ABERTO`, porque a `R-04` segura o pad.
- Três réguas não mordiam o que diziam (a promoção não separava o dono do pad
  velho; nada olhava a máscara do boot; a carta 1 só era medida pelo rádio). A
  régua `tests/unit/test_o_modo_tem_um_dono.py` foi de 30 para 44 testes e
  cobre cabo, rádio e mesa mista, com e sem jogo.
- Um dublê de `save_gamepad_caminho` ficou mais estreito que o real (sem
  `origem=`): levantava `TypeError` a cada gesto, e o `suppress` do produto
  engolia.

**Escolha registrada, não decisão dela.** Dentro do prazo do lugar guardado
(30 s), quem sai não renumera os outros; depois dele, a `NUM-01` continua
valendo (`D-2409-O-ASSENTO-GUARDADO-NAO-ANDA`). A leitura literal da sprint
(«desligado não renumera os outros», também depois do prazo) revogaria essa decisão, custaria 21 arquivos
de réguas e pediria uma regra para a mesa vazia.

## 2. O pad que o jogo vê no modo Xbox (`NO-MODO-XBOX-TUDO-FUNCIONA-01`)

**Medido antes, na fábrica real com um evdev de mentira:** modo Xbox com
máscara DualSense dava o Edge (`054c:0df2`) no uinput, sem hidraw; com máscara
Nintendo, o Pro (`057e:2009`) no uinput. São os dois pads que o PRAGMATA e o
Future Knight não usaram sob o Proton.

**A cura.** Uma regra com um dono, `integrations/virtual_pad.py:91`
(`mascara_no_jogo(caminho, mascara)`): com o modo Xbox **escolhido**, o jogo vê
o Xbox 360 (`045e:028e`) em qualquer máscara; fora dele, vê a máscara. A
fábrica veste o pad antes do start (`integrations/uinput_gamepad.py:446`,
`vestir`): nome, VID/PID, 11 teclas, 8 eixos e a tabela de botões. O `flavor`
do pad continua sendo a máscara do cartão, porque é o que os juízes de
recriação comparam: trocar o `flavor` pelo aparelho faria o juiz do P1 recriar
o pad a cada compasso (13 testes reprovam nessa mordida). O mapa
(`plataforma.vpad` do DualSense, do Pro e do SN30 em
`docs/data/mapa-controles.csv`) diz isso, e a página do mapa
(`docs/specs.html`) foi regerada.

**O preço, medido e escrito.** A escolha contraria a letra da D-1309 («a
máscara … apesar do modo de conexão escolhido»). Num jogo nativo em modo Xbox,
o cartão DualSense perde os botões de PlayStation; eles voltam no modo
DualSense, pelo uhid. A linha da aba Controles («O que o jogo vê deste
controle») continua mostrando a máscara do cartão, enquanto o jogo passa a ver
o Xbox 360. Por isso a escolha só pode entrar no registro de decisões **como
escolha pendente da pergunta 4**, nunca como decisão dela; se ela escolher a
opção (a), a D-1309 ganha nota datada.

**A dívida que ficou em régua.** Se o modo muda com um pad Nintendo de pé, o
Pro não é recriado: os dois juízes comparam o canal por `quer_uhid`, que é
sempre falso para o Pro (o `ja_estava` em `daemon/subsystems/gamepad.py` e
`daemon/subsystems/external_mask.py:613`, `vpad_ficou_para_tras`). Curar um
só faz o P1 pedir start a cada 2 s. Ficaram duas réguas `xfail(strict=True)`
em `tests/unit/test_no_modo_xbox_o_jogo_ve_o_pad.py`, que passam a reprovar no
dia da cura.

## 3. O servidor de som tem um leitor só (`O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01`)

**Medido.** Com um servidor de mentira que conta clientes, uma volta de cada
leitor com quatro controles: o canal do microfone abria 20 `pactl` (5 por
controle), a luz do mic 3, o vigia do alto-falante 2, o casamento das pontes
12 e o áudio do rádio 4. No servidor real, `pactl subscribe` por 30 s mostrou
685 pares new/remove de cliente e zero evento de nó: os clientes eram os
próprios `pactl` do daemon.

**A cura.**

- `src/hefesto_dualsense4unix/integrations/retrato_do_som.py` (novo): um
  retrato do servidor com um dono, um `pactl` por tipo (sinks, sources,
  sink-inputs, source-outputs, modules, info); a forma curta sai da longa,
  conferida byte a byte contra a saída real. Três estados: **solto** (janela,
  CLI e testes perguntam ao servidor como antes), **vivo** (responde pela
  foto) e **sem servidor** (responde «não sei», que cada executor devolve como
  a falha que já sabia ler, nunca «não há»).
- `daemon/subsystems/ouvinte_do_som.py` é o dono: lê tudo ao subir, escuta os
  eventos e, a cada rajada de 50 ms (`RAJADA_S`, linha 68), relê só o tipo que
  mudou. Evento de cliente não relê nada.
- Todo executor de `pactl` pergunta ao retrato antes (onze módulos). As
  escritas continuam pelo `pactl` e marcam o tipo como pendente.
- Os laços acordam pelo evento; os prazos de 2 s e 0,4 s viram teto.
- **Resultado:** 100 tiques dos cinco leitores sem evento = 0 `pactl`, com as
  mesmas respostas; um evento de source = 1 releitura.

A régua exaustiva mede **quem pergunta**, não a palavra: um censo por AST acha
toda pergunta de leitura em `src/` e exige que ela caia num executor conhecido.
Pergunta nova de outra sprint que não passe pelo retrato reprova de propósito
(`tests/unit/test_o_servidor_de_som_tem_um_leitor_so.py`, 42 testes).

**O que a conferência achou e curou:**

- **O microfone saía do ar rápido demais.** `LEITURAS_SEM_CANAL_ATE_SAIR`
  (`daemon/subsystems/hotkey.py:1531`) conta duas leituras sem canal, e o
  intervalo entre elas vinha do laço de 2 s. Acordando pelo evento, mediram-se
  cinco conferências em 40 ms: uma ponte do rádio que refaz o nó tiraria do ar
  um microfone ligado. Agora a conferência roda no máximo uma vez por
  `CANAL_TTL_S` (`hotkey.py:2130`, `_conferir_no_prazo`).
- **Vazamento no ouvinte:** cada rajada virava uma tarefa guardada até o
  subscribe cair (30 rajadas, 30 tarefas). `ouvinte_do_som.py:193` (`_podar`).
- **O laço do daemon parado:** `ler_o_padrao` (`ouvinte_do_som.py:46`)
  consultava o retrato dentro do asyncio, e uma releitura síncrona de até 4 s
  segurava o daemon inteiro (medido: 0 voltas). Agora roda em
  `asyncio.to_thread`.
- **O retrato que nunca assumia:** exigia os seis tipos na primeira leitura;
  num servidor em que um tipo não responde, ficava solto para sempre. Agora
  assume com o que respondeu e insiste só no que falta
  (`retrato_do_som.py:486`, `faltando`).
- **Uma mordida que não mordia:** a exclusão do `Client Index` do `pactl info`
  (`retrato_do_som.py:283`) passava com a cura arrancada, porque o servidor de
  mentira nunca muda esse número. No real ele muda a cada pergunta, e sem a
  exclusão toda releitura acordaria o canal dos quatro controles.

**Não medido:** o boot sem servidor de som deixa o retrato solto até a
primeira leitura boa; e um programa que cria um fluxo por efeito sonoro pode
fazer o ouvinte reler ~15 a 20 vezes por segundo. A prova 1 no aparelho decide.

## 4. O Salvar e o Aplicar leem o perfil (`O-SALVAR-E-O-APLICAR-LEEM-O-PERFIL-01`)

**O defeito.** O Salvar de cada aba montava o rascunho sobrepondo o estado
vivo do aparelho (luz acesa, economia, microfone, sensores, teto de força,
mouse da mesa inteira). Gravava no perfil o que o aparelho estava fazendo, e
não o que ela escolheu.

**A cura.** Em toda aba, o Salvar e o Aplicar leem só o disco:
`DraftConfig.from_profile(load_profile(nome))`, por
`interface/pacotes/rodape.py:96` (`_draft_do_ativo`). O Aplicar manda esse
rascunho; o Salvar regrava o mesmo rascunho, normalizado, com a prioridade que
o disco já tinha, o que o torna idempotente (salvar duas vezes dá o mesmo
sha256). Os símbolos da sobreposição saíram e o `rodape.py` foi de 735 para
340 linhas. O editor da aba 10 grava o campo editado sobre o disco
(`interface/pacotes/a10_perfis.py:1496`, `_o_perfil_no_disco`).

**As réguas.** `tests/unit/test_o_salvar_e_o_aplicar_leem_so_o_perfil.py`
monta P1 a P4 (dois no cabo, dois no rádio) com o aparelho divergindo do disco
em tudo. `tests/unit/test_todo_gesto_que_muda_escolha_grava.py` é exaustiva
sobre `pacotes.GESTOS`: todo gesto tem um veredito só (`grava=`, protegido,
grava sem declarar, ou ato, com a razão escrita). Ela importa o piloto, porque
um gesto só entra no registro quando o piloto é importado: sem isso, o
resultado dependia da ordem dos arquivos.

**O que a conferência achou e curou:**

- **Um Salvar que não grava nada passava.** Com o `save_profile` desligado, a
  régua nova e as doze da posse deram 464 verdes: o disco «como estava» é
  também o disco de quem não fez nada. Nasceu
  `test_o_salvar_regrava_o_arquivo_na_forma_de_hoje`.
- A comparação pelo esquema (`model_dump`) enchia os overrides com o padrão, e
  um Salvar que grava a luz densa passava nas dez abas. Nos overrides
  compara-se o JSON cru.
- Um gesto que grava pelo daemon (o sensor, via `sensor_set_detalhado`) podia
  se declarar ato. A régua agora vê as duas pontas.

**A premissa que já tinha caído.** O botão do microfone grava no perfil pelo
daemon desde 25/09 (`O-BOTAO-DO-MIC-GRAVA-NO-PERFIL-01`); o Salvar só deixou
de ser o segundo escritor.

**A decisão.** A linha `D-2709-O-SALVAR-LE-O-PERFIL`, revogando
`D-2609-O-SALVAR-GRAVA-A-SECAO-DA-ABA`, é citada pelo código, pelas réguas e
por `docs/data/paridade-gtk-html.csv`, mas ainda não está em
`docs/data/decisoes-dela.csv`.

## 5. A raiz só com o produto (`A-RAIZ-SO-COM-O-PRODUTO-01`)

Pela frase dela de 27/09, «a raiz do repo tem que ser limpa», a raiz foi de 35
para 27 entradas:

- o código aposentado (`arquivados/`) sai e fica no histórico;
- a configuração do indexador de código sai do git e fica no disco;
- `requirements.txt` sai: o `pyproject.toml` é a fonte;
- as três capturas `.bin` vão para `tests/fixtures/hid/`, e a régua do `0x09`
  passa a exigir a pasta (antes passava vazia);
- `interface.sh` sai. O `Exec=` do atalho e o `_EXEC_LINE` do `install.sh`
  (linhas 3209 e 3212) viram `env HEFESTO_NA_TELA=1 … run.sh --gui`; o
  lançador da bandeja usa `${HEFESTO_NA_TELA:-1}`, para a bancada poder
  desligar com `=0`. O `run.sh` não declara a variável (há régua que reprova);
- a bancada do mapa vai para `scripts/bancada_do_mapa.py`, com as dependências
  num extra `bancada` (`pyproject.toml:68`), fora do `[dev]` e do CI;
- o lançador da mesa de medição vai para `scripts/mesa-de-medicao.sh`, e não
  `validar-mesa.sh`: o prefixo `validar-` é forma de portão, e o portão
  «todo portão tem chamador» o acusou;
- o guia do rádio da sala vira `docs/usage/bluetooth-varios-adaptadores.md`,
  com cinco seções e sem nada da máquina de ninguém;
- as exportações da ferramenta de desenho (`.dc.html`) e a pasta de colagem
  saem do pacote: o wheel de `git archive` foi de 403 para 389 arquivos;
- o sdist declara o que entra (`only-include`, `pyproject.toml:93`), sem
  depender do que o `.gitignore` esconde. Medido em clone: com o `.gitignore`
  encolhido e sem o `only-include`, dois arquivos de ferramenta local
  entrariam no sdist; com ele, zero.

**A conferência** curou a régua do lançador da mesa, que podia falhar sob
carga: `select()` no descritor seguido de `readline()` no fluxo com buffer
puxava o endereço para o buffer, e o laço esperava 60 s por uma linha já lida
(`tests/unit/test_a_mesa_de_medicao.py`, agora lê em bytes pelo descritor).

**Aviso que a sprint deve a ela.** O `interface.sh` foi pedido por ela em
29/08, para clicar na raiz; a frase de 27/09 não o nomeia. Depois do merge,
quem abre na tela é o menu, a dock ou `HEFESTO_NA_TELA=1 ./run.sh --gui`; o
`./run.sh` sozinho abre numa tela invisível, pela guarda `TELA-DELA-02`. Entre
o merge e o install, o atalho do menu e o «Abrir painel» da bandeja apontam
para um arquivo que não existe: o install tem de rodar no mesmo fecho.

## 6. O dono das formas do endereço (`O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01`)

Entregue antes da rodada seguinte, só o dono; os seis mascaradores, o diário e
o «Copiar» passam a chamá-lo depois.
`src/hefesto_dualsense4unix/core/formas_do_endereco.py`:

- `mascarar(texto, conhecidos=())` (linha 363), em duas camadas: primeiro os
  endereços e seriais conhecidos, em qualquer grafia e nas duas ordens de
  byte, inclusive colados dentro de uma corrida hex; depois as formas
  genéricas (a separada, a colada de 12 hex, `_<6 hex>`, `HEFESTO<6 hex>`,
  `hefesto-<palavra>-<6 hex>`). O serial de fábrica mantém os seis primeiros
  caracteres. Juntam-se todas as posições a zerar antes de escrever: zerar
  janela a janela deixava sobrar um octeto no despejo invertido com espaço.
- `mascarar_endereco(valor)` (linha 383) descarta o valor em vez de peneirar
  os dígitos; `formas_do_endereco` (linha 193) serve às réguas.
- O topo importa só a biblioteca padrão, para o `logging_config` poder
  importá-lo sem ciclo.

**A conferência** achou que a forma `_<6 hex>` estragava linhas reais do
diário de 27/09 que não são endereço: 2 de 2 `steam_app_<N>` de seis
algarismos e 11 de 11 carimbos de versão do perfil. Os dois passaram a ser
guardados como o UUID (linhas 101 e 103); nas 632.156 linhas medidas, a saída
muda em 13, todas dentro do guardado. Também: um endereço passado como `str`
solto era iterado letra a letra e a camada dos conhecidos ficava calada (o
tipo aceita `str` como `Iterable[str]`); agora vale como um conhecido. A régua
`tests/unit/test_o_registro_copiado_nao_entrega_o_endereco.py` tem 133 testes.

**Custo medido:** 16 a 22 µs por linha sem conhecidos; um painel de 80 linhas
com oito conhecidos, ~10 ms.

## O que vale para as seis

- **O `portoes.sh --rapido` não é o portão.** Em cinco das seis frentes o
  completo reprovou o que o rápido deixava passar: o `casa-sabe` em quatro
  (função pública sem chamador em produção: `load_gamepad_caminho`,
  `mascara_no_jogo_do_vpad`, `interessa`, `descricoes_da_lista`, as três do
  dono do endereço), a `acentuacao` em três (o modo, o som e a raiz) e o
  «todo portão tem chamador» na raiz. Os três só rodam na camada completa.
- **Código novo no fim do módulo.** No `hotkey.py` e no `dualsense_bt_audio.py`
  isso manteve as 3.625 citações `arquivo:linha` no lugar sem reapontar. Onde
  o código andou (`lifecycle.py`, `gamepad.py`, `connection.py`,
  `manager.py`), 34 citações em `docs/` ficaram para o reapontamento.
- **A mordida que faltava achou régua que não mordia** em quatro frentes: o
  Salvar que não grava (464 verdes), o `Client Index`, a promoção que não
  separava o dono do pad velho e a paridade ímpar dos conhecidos (115 de 115
  verdes). No modo Xbox, a régua que faltava (a troca de modo com o pad de pé)
  achou a dívida do Pro.

## O que ficou aberto

- **Modo:** o PS, o PS + R3 e as combinações em qualquer controle (item 5 da
  `-02`). A `R-04` no arme: com o jogo na autoridade antes do `exec`, a troca de
  máscara continua recusada, e o caso de 27/09 em que nenhum controle jogava
  não está provado curado. `_seguir_a_carta` roda síncrono no laço (risco
  plausível, não provado). A renumeração depois do prazo pede decisão. O
  `gamepad.emulation.set` sem caminho (o chip «Jogar pelo Hefesto» saindo do
  Modo Nativo) segue subindo DualSense com o perfil ativo em Xbox.
- **Modo Xbox:** o juiz de recriação pelo aparelho (as duas `xfail`);
  `launch_env._mascara_do_primario` ainda lê a máscara do cartão, e não o
  aparelho; o PS + L3 no modo Xbox recria um Xbox 360 idêntico; a háptica fina
  no modo Xbox não existe; o touchpad e o acelerômetro como fonte esperam as
  perguntas 1 a 3; a pergunta
  4 (o que o cartão mostra no modo Xbox) é da sessão dos desenhos; o mapa não
  sabe declarar uma linha com duas pontes (`vibracao.rumble.ff`).
- **Som:** as quatro provas no aparelho (menos de 1 `pactl`/s contra 23 hoje;
  todas as features juntas, P1 a P4, sem atraso de mais de 1 s; tirar e pôr
  um controle em menos de 1 s; reiniciar o servidor de som e ver «não sei» e a
  reconstrução). O processo da janela continua perguntando direto.
- **Salvar:** gravar `D-2709-O-SALVAR-LE-O-PERFIL`. O mudo do microfone é do
  controle (resposta 9 dela: «do controle, vale em todo jogo»), mas ainda mora
  no perfil, e o `_lembrar_do_som` (`interface/pacotes/a02_controles.py:2177`)
  ainda o grava no perfil ativo em vez de deixá-lo ao daemon. O
  Aplicar leva menos da metade do que a ativação leva (sprint proposta
  `O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01`). `_secao_do_mouse`
  (`interface/pacotes/a06_navegacao.py:1453`) faz nascer `mouse.enabled` do
  estado vivo quando o perfil não tem a seção.
- **Raiz:** encolher o `.gitignore` espera a confirmação de um dos
  mantenedores; o `traduzivel.json` a regerar; nomes velhos (`bancada.py`,
  `GUIA-RADIO-DA-SALA`, `interface.sh`) em notas de `docs/data/`, em
  `scripts/doctor.sh` e na guarda de
  `tests/unit/test_o_tray_e_o_rico_e_abre_o_painel.py`, que ainda procura
  `interface.sh` e ficou cega nessa metade.
- **Endereço:** ligar os seis mascaradores, o diário e o «Copiar» ao dono; o
  `logging_config` tem de guardar o processador contra exceção do dono; a forma
  colada também come números de 12 algarismos (o tempo em ns do MangoHud),
  então o CSV cru do MangoHud não passa pelo dono.
