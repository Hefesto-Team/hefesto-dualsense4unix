# O registro técnico de 12/10/2026

O que se mediu, a causa achada, o que se decidiu e o que ficou aberto em
12/10/2026, para quem desenvolve o Hefesto. O dia teve cinco temas: o engasgo
que voltava em todos os jogos e a cura dele, o par entre o pad virtual e a
háptica; os dois fechos no `dev`; as quatro revisões dos desenhos de todas as
abas; o que a pesquisa apontou para a próxima etapa; e a fila que ficou, com as
medidas de bancada que essa fila pede.

## Como ler

- **A sprint e a decisão se citam pelo ID** (`A-PROVA-DO-PAR-NOS-JOGOS-DA-SONY-01`).
  O texto delas mora nos documentos de processo da casa, que não viajam com o
  clone; o ID é o que se procura lá.
- **O código se cita por `arquivo:linha`**, e a linha é a de 12/10, **antes** da
  cura do par: as curas moveram linhas. Na dúvida, procure o nome da função.
- **O grau de cada afirmação** vem marcado onde importa: MEDIDO (comando rodado,
  saída guardada), LIDO (código, binário, diário) ou SUPOSTO (conclusão sem
  medida direta).
- **Onde a árvore de hoje já difere, vale a árvore.**
  `git log --since=2026-10-12 --format='%h %s'` diz o que entrou depois.
- **Os controles se citam pela cor do plástico**: Starlight Blue, White, Cosmic
  Red e Galactic Purple.
- **Cada tema termina em «O que ficou aberto»**, e a seção 5 junta a fila.

## As páginas deste registro

| página | o que traz |
|---|---|
| [O antes e o depois das abas](paginas/todo-das-abas/index.html) | a página da revisão mais recente: o antes e o depois de cada aba, a lista riscada e um campo por aba |
| [A primeira revisão](paginas/todo-das-abas/rodada-1.html) | a montagem inicial, guardada como estava |
| [A conferência](paginas/todo-das-abas/todo/CONFERENCIA.md) | o que cada revisão riscou, aba por aba |
| [O plano do fim](paginas/plano-do-fim.html) | a ordem de trabalho até o produto fechar ([texto](paginas/PLANO-DO-FIM.md)) |
| [O índice das páginas](paginas/README.md) | o que cada arquivo de `paginas/` é |

---

## 1. O engasgo de todos os jogos e o par pad↔háptica

### 1.1 A resposta curta

O engasgo periódico do Sackboy não era do jogo nem do Vulkan: a biblioteca de
pad da Sony varre os dispositivos de áudio do prefixo, e cada varredura custa
memória proporcional ao número deles. A varredura só dispara quando um pad HID
não tem o áudio dele no **mesmo aparelho USB**. Basta um controle descasado entre
quatro. A cura casa cada pad virtual com o endpoint de háptica do mesmo gadget,
desde a primeira montagem. Entrou no `dev` em `0044399e9..d25958549`.

### 1.2 O sintoma, medido no Sackboy (MEDIDO)

Cada varredura deixa ~1,13 KiB por dispositivo num buffer contíguo que se realoca
a cada 64 KiB; a cópia da realocação é o tranco. A lei, provada em três rodadas e
seis janelas com desvio abaixo de 5%:

> crescimento = varreduras/s × dispositivos × ~1,13 KiB

| cenário | dispositivos | crescimento |
|---|---|---|
| dois jogadores (07/10) | 7 | 45,7 KiB/s |
| de dois a quatro jogadores (07/10) | 27 | 175 a 628 KiB/s |
| quatro jogadores pelo USB (07/10) | 39 | 776 KiB/s |

O tranco visível começa com o buffer acima de ~30 MiB. Os dispositivos subiram de
7 para 27–39 porque o Hefesto publica, por aparelho, o endpoint de háptica, o
alto-falante, o microfone e os monitores; e os GUIDs que já não existem continuam
no registro do prefixo.

### 1.3 As rodadas que separaram as causas (MEDIDO)

- **Dois controles no gadget USB (14h53–15h01):** liso até 1m30; o engasgo voltou
  aos ~2 min; do minuto 3 ao 7, 10,5 a 13,6 passos/s e p99 de 0,4 a 0,8 s por quadro.
  A primeira cura do gadget não bastava.
- **Dois pads de ensaio no gadget, sem endpoint de som (15h54–16h07):** 2,26
  passos/s, p99 de 16,8 ms, nenhum quadro acima de 50 ms. O pad do gadget sozinho
  não engasga.
- **A prova do par, com os quatro controles pelo rádio:**

| rodada | estado do par | resultado |
|---|---|---|
| A | três casados, o primeiro com âncora emprestada, três endpoints órfãos | 8,2 passos/s, 13,7 varreduras/s, 4 fps aos ~7 min |
| B | os quatro casados à mão | 0,00–0,07 passo/s por 10 min, 60 fps a 16,7 ms; háptica fina, giroscópio e touchpad vivos |
| C | só o White com âncora emprestada | ≈3,1 passos/s |

A conclusão de C: áudio sem HID não dispara a varredura, só aumenta o número de
dispositivos varridos; é o HID sem áudio no mesmo aparelho que dispara.

### 1.4 As causas no código (LIDO, linhas de 12/10)

- **O primeiro pad monta o gadget antes de a identidade existir.**
  `src/hefesto_dualsense4unix/integrations/uhid_gamepad.py`, `_vigiar_a_enumeracao`
  (~2457-2477), só registra o gadget `if gadget.identidade` (:2471), e a identidade
  sai de `pad.identity or ""` (:2431). Sem ela,
  `src/hefesto_dualsense4unix/integrations/endpoint_de_haptica.py`
  `ancora_do_gadget` (~256-268) devolve `None`, e `distribuir_ancoras` (~271-325)
  empresta uma interface USB qualquer da máquina.
- **O endpoint emprestado não se reancora com o jogo aberto:**
  `src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py` ~1818-1824.
- **O hidraw do gadget passava pelo filtro de aparelho.** `controles_na_lista`, no
  mesmo `alto_falante.py` (:561-604), só testava `HID_PHYS == "hefesto-vpad"` (:596); o resultado eram
  endpoints órfãos e o laço `som_no_sem_rota`. O dono certo da pergunta já existia:
  `pad_usb.e_hidraw_de_pad_nosso`.
- **O mecanismo:** a biblioteca da Sony casa o HID com o áudio pelo `ContainerId`.
  O `winebus` o calcula pelo `usb_device` pai do HID, e o `winepulse` pelo
  `sysfs.path` do sink. Âncora emprestada é contêiner diferente.

### 1.5 O alcance (LIDO nos binários)

O defeito atinge quem lê o pad pela biblioteca da Sony com a máscara DualSense: o
Sackboy (MEDIDO) e Minecraft Dungeons II, Black Myth: Wukong e PRAGMATA (SUPOSTO
forte), 4 dos 34 jogos instalados. O Guardians of the Galaxy escapa porque está no
caminho Xbox. Os outros 29 usam SDL, Unity, Rewired, InControl, XInput, GameMaker,
Chromium, shadPS4 ou são nativos, e não perguntam pelo áudio do pad.

### 1.6 A cura

**Bloco 1** (27 testes que mordem):

- a âncora se casa quando o dono do gadget chega ou muda;
- o endpoint espera o gadget que está a caminho, em vez de emprestar;
- o pad nosso sai da lista de aparelhos pelo dono único
  (`pad_usb.e_hidraw_de_pad_nosso`).

**Bloco 2:** o quinto pad, a numeração igual à do jogo, a entrada tardia e a troca
do primeiro controle. A numeração estava trocada: o diário mostrava
`o_numero_que_o_jogo_escreveu concorda=False hefesto=3 jogo=2`, e mais dois casos
(a linha nasce em `src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py:2198`).
O teto do gadget é `MAX_PADS_USB = 4`
(`src/hefesto_dualsense4unix/integrations/pad_usb.py:76`). O endpoint de mentira
continua para o pad sem gadget, porque é por ele que a RE Engine acha a háptica.

**A prova ao vivo, sem jogo, depois do install (MEDIDO):** oito vagas no
`usbip_vudc`, quatro pads nas portas `5-1` a `5-4` com o serial de pad do Hefesto,
quatro endpoints de háptica.

### 1.7 O pad USB visto de perto (MEDIDO, 14h20–14h30)

- Os gadgets enumeram em série, ~5,5 s cada; o terceiro e o quarto passavam dos
  15 s de `_GADGET_ENUMERA_S` e caíam no uhid. A fila do hub passou a contar no
  prazo (`f7a55974f`), e depois do reinício das 21h03 os quatro enumeraram.
- Uma falha de enumeração fica gravada como `CONTRATO_DA_ENUMERACAO` até o daemon
  reiniciar, e condena todo pad seguinte ao uhid.
- Os quatro pads saíram com o mesmo endereço forjado.
- 22.155 linhas `pad_usb_leitura_falhou err=ENOMEM` em pouco mais de um segundo:
  o fio de leitura do gadget que cai não dorme.

### 1.8 O que ficou aberto

- O registro do prefixo do Sackboy com o par certo e o `concorda=True` no diário,
  com jogo.
- Os casos de bancada: a entrada tardia, dois controles no cabo e dois no rádio,
  as máscaras Xbox e Nintendo, o Modo Nativo.
- Os outros jogos da Sony: Minecraft Dungeons II, Wukong (um jogador numa partida
  longa: pela lei, de 15 a 20 min até o tranco), PRAGMATA (o device KS); o Pro Jank
  Footy, que engasga por outra causa em qualquer configuração; o Spirit Valley
  como controle de não-regressão. Tudo com a Steam aberta do zero.
- A trava da enumeração e o fio que gira viraram sprint (seção 4.2).

---

## 2. O fecho

### 2.1 A resposta curta

Dois fechos no `dev` no mesmo dia: o da integração anterior (~14h05) e o do par
do pad (~21h15). Os dois com portões 72/72 e a suíte nas 24 partes.

### 2.2 O primeiro fecho (~14h05)

`12c1060dd..0044399e9`: portões 72/72, suíte 24/24, merge fast-forward, install e
push. O push exigiu reescrever 135 commits por causa de um emoji numa mensagem de
commit, o que obrigou a reapontar 23 citações de commit em 5 arquivos. O CI de
`0044399e9` saiu vermelho e foi curado em 5 commits.

### 2.3 O fecho do par (~21h15)

`0044399e9..d25958549`: portões 72/72, suíte 24/24, merge fast-forward, install,
daemon reiniciado às 21h03, push.

- **O único vermelho que ficou já existia no `dev`:**
  `test_toda_excecao_tem_sprint_que_a_tira`. A fila marca como feitas quatro
  sprints cujo código mora em três ramos ainda não integrados; ele sai quando esse código entrar.
- **Curados no fecho:** o dublê do `rotulo_do_jogo` vazava para a sentinela da aba
  07 (o commit `d25958549` faz os leitores da Steam subirem antes dos dublês, e o
  teste da aba 07 morde com a cura arrancada); a prova das fotos ficou atrás das
  citações reapontadas (`249370851`); e o mapa do rádio desenhado ainda dizia o
  número velho da ponte que o produto já não diz (`1ee976592`).
- **A limpeza de texto** (`8b02cb8bd`, `0e6e5e9fc`, `cb26dfc5f`, `581ed3051`):
  comentários e páginas sem vocabulário de processo.

### 2.4 O que ficou aberto

- O teste da vaga que entrega os botões do segundo e do terceiro pad é intermitente sob carga,
  por causa de um `asyncio.sleep(0.15)` fixo.
- O laço de fecho repete as voltas diante de um vermelho determinístico, quando
  deveria parar na primeira.
- A publicação das páginas do primeiro fecho ficou por fazer.

---

## 3. As quatro revisões dos desenhos de todas as abas

### 3.1 A resposta curta

As dez abas e as janelas auxiliares foram montadas de uma vez, com todos os
ajustes de tela das sprints abertas, e passaram por quatro revisões no mesmo dia.
Cada revisão riscou a própria lista por medida, não por olho. **Nada disto está no
produto ainda:** a direção é desenho → produto, e a publicação vem depois das
sprints de tela.

As páginas: [as dez abas](paginas/todo-das-abas/todo/01-jogar.html) (de
[01](paginas/todo-das-abas/todo/01-jogar.html) a
[10](paginas/todo-das-abas/todo/10-perfis.html)), os mapas
([controle](paginas/todo-das-abas/todo/mapa-do-controle.html),
[portas](paginas/todo-das-abas/todo/mapa-das-portas.html),
[rádio](paginas/todo-das-abas/todo/mapa-do-radio.html)) e a janela
[calibrar sensores](paginas/todo-das-abas/todo/calibrar-sensores.html). Cada uma
tem ao lado o `NN-mudancas.json` com a sua lista de mudanças.

### 3.2 A primeira revisão

A montagem inicial ([guardada](paginas/todo-das-abas/rodada-1.html)): 96 mudanças,
64 delas com escolha, conferidas em 1212x809, 1212x740 e 1918x840, sem rolagem
vertical. Entraram as ordens da tarde: um botão só, «Modo automático»; a aba 05
preenchendo o quadro; a dica do Desligar no menu; uma foto de estado para cada
mudança que a foto da aba não mostra. A página refeita ficou com 101 mudanças e
28 fotos de estado. Voltaram 102 respostas.

### 3.3 A segunda revisão (141 de 144 itens riscados)

- Sai todo «?»; a dica passa ao hover. Menos texto, mais respiro, e uma base comum
  idêntica em toda aba, com o menu do botão direito em todas.
- O Modo automático sai da 01 e fica de 02 a 05; o Freestyle volta à 01.
- 02: «Usar giroscópio como analógico», três rotas de alto-falante, e o touchpad
  acende só a terça tocada.
- 03: «Modo» vira «Efeito de acionamento», «Efeito pronto» vira «Efeito de
  imersão»; «Criar efeitos novos» entra de 02 a 05. 04: doze cores, com magenta.
- 06 redesenhada (os botões do DualSense primeiro; Steam com Big Picture ou Steam
  padrão; Acessibilidade). 07 vira «Experimental» (Extensões em cima, Lançadores
  embaixo; Identificar, Criar perfis e Configurar), e «Meus toques» vai para a
  engrenagem da Lovense.
- 09: «Funcionamento do app», a coluna Interface, «Permitir correções
  automáticas», «Restaurar de fábrica» com borda vermelha. 10: Visual novel e
  Adulto como estilos, clique para ativar, duplo clique para ordenar, datas,
  «Aplicar em» e Eventos.

### 3.4 A terceira revisão (177/177)

O alinhamento passou a ser medido com `getBoundingClientRect` no Chrome headless,
e o portão é zero divergência acima de 1 px.

- 05: a Força ganha o desenho do controle inteiro e começa e termina com as barras
  de baixo; a última coluna passa de 14 contra 26 px para 14 px. 04: as colunas a
  14 px dos dois lados.
- 08 e mapa do rádio: as barras na mesma reta. Mapa do controle: os quatro
  controles com a mesma largura, o seletor pela cor do plástico.
- 07: o aparelho Lovense de dois motores se chama Nora. 09: o registro diz Cosmic
  Red e Starlight Blue, nunca um número de jogador.
- Mapa das portas: a cadeia fala com quem usa, sem nome de driver. 06 e 10:
  margens e larguras acertadas.

### 3.5 A quarta revisão (188/188)

- 01: o Reconectar vai para o canto superior direito, e ele e o Freestyle ficam
  com o mesmo tamanho (166×34). 02: «Calibrar giroscópio» com a letra do Modo automático.
- 03: o L2 e o R2 desenhados à esquerda do Modelo, e a linha divisória de ponta a
  ponta.
- 07: cada extensão com uma descrição curta; os lançadores em cartões 2×4; o
  «Quando» da Lovense começa em «Os jogos que eu escolher».
- 08: saem os botões Econômico e Máximo. 09: «Parar o serviço» vira «Parar».

### 3.6 O que ficou aberto

- Aprovadas sem ajuste: 04, 06 e o mapa do controle. Sem resposta: 05, 10, mapa
  das portas, mapa do rádio e calibrar sensores.
- Os desenhos aprovados viram sprints de tela e só então chegam ao produto, pelo
  `scripts/check_o_desenho_aprovado.py --publicar`.

---

## 4. O que a pesquisa apontou para a próxima etapa

### 4.1 O MI_03 do composto da Sony

**O que o GE-Proton faz (LIDO, no fonte dos patches e nos binários instalados).**
Dos 182 patches do GE-Proton11-7, só dois olham o número da interface, e os dois
exigem `mi_03`: o 0098 (`sechost`, `is_sony_usb_audio_hid`) segura a chegada de um
HID Sony com PID 05C4, 09CC, 0CE6 ou 0DF2 até o alto-falante do mesmo contêiner
existir, com teto de 3 s; o 0125 (`setupapi`) espera o mesmo evento na enumeração.

**O nosso pad é `MI_00`** (MEDIDO): o gadget tem uma função só. O registro do
Sackboy tem 32 linhas `MI_00` do gadget e 2 `MI_03` de uma prova antiga com
`uac2`. O DualSense pelo cabo é `MI_00` a `MI_03`: áudio nas interfaces 0 a 2, HID
na 3. Logo, a garantia «o HID aparece depois do áudio» não vale para o pad que
chega com o jogo aberto: a entrada tardia, a troca do primeiro controle, o
controle que cai no rádio e volta.

**O limite já medido:** o sinal do 0098 só dispara para nós cujo nome case com
«DualSense» **e** «Internal Mono Speaker» (patch 0003), e os nossos nós não têm o
segundo. Com `MI_03` e os nomes de hoje, cada chegada esperaria os 3 s e sairia
por «Timed out». Por isso a sprint mede isso na bancada **antes** de escrever
código.

**A proposta:** `O-PAD-VIRTUAL-SE-APRESENTA-COMO-O-COMPOSTO-DA-SONY-01`. O gadget
ganha a `uac2.usb0` antes da `hid.usb0` (o HID vira a interface 3), e nenhum
isócrono passa pelo `vhci`: o host só autoriza a interface 3 de cada pad, porque a
`uac2` com o host transmitindo congelou o jogo em medidas anteriores (6.781 ms num
quadro). Sem o módulo `usb_f_uac2`, o pad nasce só HID, como hoje.

### 4.2 O gadget que não enumera

`UM-GADGET-QUE-NAO-ENUMERA-NAO-CONDENA-OS-OUTROS-01`. A falha de enumeração de uma
porta é um fato daquela porta, e não um contrato do kernel: guardá-la no processo
transforma um atraso numa sentença para o dia (MEDIDO às 14h26, 14h31 e 20h02).
A cura: a falha fica no gadget dele, a porta sai do rodízio só depois de duas
falhas seguidas, a leitura que falha pergunta se o gadget existe e dorme, e o
doctor lê do diário quem está no uhid e por quê, dizendo «não sei» com o diário
vazio.

### 4.3 O registro do prefixo

`O-REGISTRO-DO-PREFIXO-PERDE-O-SOM-QUE-NAO-EXISTE-MAIS-01`: podar os dispositivos
de áudio ausentes do registro, que a varredura também percorre. A contagem
(MEDIDO):

| prefixo | Render | Capture | ausentes |
|---|---|---|---|
| Sackboy | 17 | 30 | 6 |
| Minecraft Dungeons II | 15 | 24 | 0 |
| Guardians of the Galaxy | 12 | 18 | 13 |
| PRAGMATA | 10 | 15 | 8 |
| Wukong | 9 | 13 | 5 |

### 4.4 A prova nos jogos da Sony

`A-PROVA-DO-PAR-NOS-JOGOS-DA-SONY-01` junta a lista da seção 1.8 num roteiro só:
cada jogo com a Steam aberta do zero, o tempo que a lei da seção 1.2 prevê para o
tranco, e o registro do prefixo lido depois de fechar.

### 4.5 O estilo do jogo governa o automático

A sprint-índice é `O-ESTILO-DO-JOGO-GOVERNA-O-AUTOMATICO-EM-TODAS-AS-ABAS-01`. As
filhas:

- `O-EFEITO-DE-ACIONAMENTO-GANHA-A-VARIANTE-DE-CADA-ESTILO-01`
- `O-ESTILO-TERROR-SOBE-O-ALTO-FALANTE-E-LIGA-O-MICROFONE-NO-AUTOMATICO-01`
- `O-ALTO-FALANTE-SEGUE-O-ESTILO-E-O-RITMO-NUNCA-DUPLICA-01`,
  `A-VIBRACAO-DE-CADA-ESTILO-SEGUE-O-GESTO-DO-GENERO-01` e
  `A-LUZ-DE-CADA-ESTILO-REAGE-AO-GESTO-DO-GENERO-01`
- `OS-ACESSORIOS-SEGUEM-OS-JOGOS-ESCOLHIDOS-COM-A-FORCA-NO-DESLIZANTE-01`
- `AS-MARCAS-VIRAM-OS-ESTILOS-VISUAL-NOVEL-E-ADULTO-01` e
  `O-POINT-AND-CLICK-SERVE-A-VISUAL-NOVEL-01`

A ordem do código: acionamento → Terror → alto-falante → vibração → luz.

**A tabela estilo × recurso** (gatilho na escala da Sony: posição 0–9, força 0–8):

| estilo | gatilho | luz | vibração e som |
|---|---|---|---|
| Nativo | nada; o jogo decide | o jogo | o jogo |
| Personalizado | o da aba | o da aba | o da aba |
| FPS | R2 arma 3→6 f5 no tiro espaçado, vibração a 20 Hz na rajada; L2 ponto duro 3 f3 | vermelha, pulsa no tiro, até 3/s | degrau máximo |
| Corrida | R2 ponto duro 2 f2; L2 rampa 2→8 f2→6 | laranja, parada | balanceado, sem toque por tiro, sem lado do som |
| Ação | R2 arma 3→6 f5, com rajada; L2 ponto duro 4 f3 | roxa, pulsa no tiro | máximo |
| Arco | arco 1→7 f6, disparo em 7 | âmbar, pulsa na soltura | balanceado |
| Aventura | ponto duro 4 f3 nos dois | verde, parada | balanceado |
| Esportes | R2 ponto duro 2 f3; L2 desligado | azul, parada | balanceado |
| Point and click | desligado (L2 e R2 viram clique) | ciano, parada | economia |
| Visual novel | desligado (L2 e R2 viram clique) | ciano, brilho 0,5, parada | economia |
| Adulto | o do jogo | família própria, parada | máximo |
| Terror | R2 arma 4→7 f6; L2 ponto duro 3 f4, com rajada | vermelho-escura, brilho 0,7, pisca 2/s | máximo, 400 ms, toque de 60 ms; o som do jogo também no controle; microfone aberto com ou sem fone |
| Luta | desligado: o gatilho é botão de golpe | rosa, pulsa no golpe | máximo |
| Ritmo | desligado | magenta, segue a batida, até 3/s | máximo, sem lado do som; o alto-falante nunca duplica |
| Simulação | rampa 1→8 f2→6 nos dois | azul-clara, parada | economia, sem toque por tiro, sem lado do som |
| Maratona | desligado | cinza a 0,25, nunca apaga | economia |
| Plataforma | desligado | amarela, parada | balanceado |
| Retrô | desligado | verde-tubo, parada | economia |

Os degraus de vibração são os do Hefesto: máximo 1,0, balanceado 0,6, economia
0,35. Em nenhum estilo o giroscópio entra, e o touchpad fica Ligado em todos. Na
Navegação, o Point and click usa o molde «Só mouse», e a Visual novel, as teclas
do Ren'Py.

**O que o Kyty, o shadPS4 e o anyPS5 ensinaram (LIDO, no fonte):**

- a biblioteca de pad tem só 7 modos de gatilho (o anyPS5 recusa `mode > 6`), e as
  faixas do Kyty são Weapon 2..7, força até 8, Rampa 1..8;
- o volume padrão do alto-falante no PS5 é 11626/32768 ≈ −9 dB (igual no
  shadPS4); o Hefesto já sai a 100%, então o «mais alto» do Terror vem da rota que
  duplica o som do jogo, não do registrador;
- os passos de acessibilidade (1,0/0,66/0,33) batem com máxima/balanceada/economia
  do Hefesto (1,0/0,6/0,35);
- a luz é uma chamada por evento, sem restauração;
- existe uma função que enfraquece vibração e gatilho com o microfone aberto (é um
  stub), e o Hefesto não a imita: no Terror a vibração nunca enfraquece pelo
  microfone;
- nenhum dos três guarda uma tabela «o que cada gênero manda»; ela é nossa.

**As decisões do dia:** Visual novel e Adulto são estilos (não há dado a migrar);
os acessórios valem nos jogos escolhidos numa caixa de marcar na engrenagem da
extensão, com um deslizante por canal por aparelho (Vibração, Gatilho e Háptica,
de 0 a 20), e o aparelho recebe o maior dos três. FPS a 20 Hz, Luta sem
resistência, Ritmo sem som em dobro. Ficaram como ponto de partida, até a bancada
confirmar: os deslizantes começam em 50%, a lista de jogos nasce vazia, e no
Terror com fone o som do jogo não se duplica (o microfone abre igual).

### 4.6 O que ficou aberto

As quatro sprints de 4.1 a 4.4 e a família de 4.5 estão escritas e abertas; o
número de cada estilo que a tabela traz é o ponto de partida, e as medidas que
podem mudá-lo estão na seção 5.

---

## 5. O que ficou aberto, com as medidas de bancada

### 5.1 As medidas do estilo (L1 a L11)

| nº | o que se mede |
|---|---|
| L1 | a vibração do gatilho a 20, 30, 40 e 60 Hz: acima de ~36 Hz fica irregular, e a arma automática de fábrica manda 60 Hz |
| L2 | o nível do alto-falante no Terror |
| L3 | qual microfone abre com fone, e se o som duplicado volta por ele |
| L4 | se a resistência no gatilho atrasa o golpe na Luta (20 apertos lidos no evdev) |
| L5 | o arco do firmware contra a rampa oficial, às cegas |
| L6 | se o pique dos Esportes com força 6 cansa o dedo (10 min, contra força 3) |
| L7 | o registro por gênero no Kyty |
| L8 | o atraso do alto-falante pelo rádio |
| L9 | o pisca a 2/s |
| L10 | o touchpad como cursor no point and click e na visual novel |
| L11 | o ronco do motor tomado por estalo, e o toque de 40 contra 60 ms |

### 5.2 A prova nos jogos

A lista da seção 1.8, num roteiro só (`A-PROVA-DO-PAR-NOS-JOGOS-DA-SONY-01`).

### 5.3 A bancada da volta (D1 a D8)

- D2: o Pro Jank Footy. D3: o ambiente do processo do Minecraft Dungeons II.
- D4: a máscara Nintendo Pro. D5: a velocidade 12 e a piscada.
- D6: a Lovense. D7: o Kyty com um e com dois controles.
- D8: o cache fantasma e a pulsação.
- E as avulsas: o toque com o jogo aberto, o jogo novo, o login, o envelope da
  háptica, o toque por controle, o registro, a captura de botão e o USB.

### 5.4 Sem dono ainda

- O resíduo do alto-falante e o conflito entre dois adaptadores Bluetooth.
- O quinto pad numa máquina sem os módulos do gadget: o doctor deveria avisar.
- O Guardians of the Galaxy no Heroic (GE-Proton10-34, sem device KS).
- O Modo Nativo pelo rádio, onde o par é impossível por construção, e uma rodada
  mista com um controle no cabo e três no rádio.
- Fundir o som e a háptica num nó de quatro canais, depois do par provado nos
  jogos.
