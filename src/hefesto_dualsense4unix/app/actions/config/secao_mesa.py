"""Seção 2 da aba Configurações — os adaptadores, a vizinhança e o rádio.

O que a máquina responde sozinha (adaptadores, rádios vizinhos, hub, topologia
USB) é LIDO; o que nenhum barramento sabe (altura da antena, linha de visada) é
declarado. A ordem importa: onde a leitura acerta, ela pré-preenche.

TERRITÓRIO DE CONFIG-02, e do medidor de rádio de CONFIG-04. Quem trabalha
nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

DE ONDE VEM CADA COISA NA TELA
-------------------------------

A leitura inteira sai de `integrations/mesa_de_radio.ler_a_mesa` — sysfs, sem
root, sem subprocesso, sem IPC. Este módulo não lê arquivo nenhum: ele TRADUZ
o que o kernel respondeu para palavra de gente, e é só aqui que `right` vira
"Direita" e que a ausência de resposta vira "Não sei".

Uma coluna do desenho não está aqui, e o motivo é que não há fonte (F3 de
`DECISOES-DA-EXECUCAO.md`): **"Firmware"** — não existe check por adaptador em
`scripts/doctor.sh`; a leitura viria do registro do kernel, que é escopo de
CONFIG-09. Coluna que só sabe dizer "Não sei" em toda linha ocupa largura — o
recurso escasso desta janela — e ensina a ignorar a tabela.

A coluna **"Em uso"** também saiu da tabela, mas por outro motivo: ela virou o
MEDIDOR, mais abaixo nesta mesma seção, que é onde ela tem procedência.

O MEDIDOR DE RÁDIO (CONFIG-04)
-------------------------------

O limite que CONFIG-02 escreveu — *"o que amarra controle a adaptador é o bond,
em `/var/lib/bluetooth`, árvore 700, e a janela é sudo-zero"* — estava FALSO, e
foi derrubado em 22/08/2026: o uevent do nó hidraw publica `HID_PHYS` = MAC do
adaptador para BT real (`broker/hidraw_broker.py:318`), e
`/sys/class/hidraw/*/device/uevent` abre como uid 1000. É por aí que o medidor
sabe qual controle está em qual adaptador, sem tocar em `sudo`.

A conta, a procedência de cada número e a fronteira que a tela NÃO atravessa
(ocupação nunca é culpa) moram no cabeçalho de
`integrations/radio_da_mesa.py`. Aqui em cima ficam só as três coisas que são
de tela: o rótulo, a cor da palavra e o selo de procedência.

A COLUNA "O QUE É" É LIDA, E ELA SÓ CORRIGE (22/08/2026)
---------------------------------------------------------

Decisão dela: *"classifica sozinho, você só corrige"*. Até aqui a coluna
oferecia SETE botões por linha e perguntava à mão o que o kernel já responde:
`bInterfaceClass/SubClass/Protocol` da interface 0 distingue mouse de teclado
(`03/01/02` contra `03/01/01`) e Bluetooth de "sem fio" (`e0/01/01`). Quem lê
é `integrations/censo_do_barramento`, que nasceu em 22/08/2026 e ficou sem UM
consumidor em `app/` — a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` nascendo na mesma
sessão que a documentou.

A ordem de precedência tem três degraus, e ela é o desenho:

1. **a correção dela vence tudo** — `RadioDeclarado.tipo`, no `maquina.json`;
2. **o que o kernel leu vence o botão vazio** — a linha nasce preenchida, com
   o selo `(lido)`, e o seletor só aparece se ela clicar em "Corrigir";
3. **quando ninguém sabe** — classe `ff`, em que o fabricante declinou de
   classificar — a linha nasce com o seletor aberto e o `▲`. Na bancada dela,
   das quatro linhas de rádio vizinho, só UMA cai aqui.

A junção entre as duas leituras é o `no` — o caminho real no sysfs, a mesma
convenção nos dois módulos. Nunca o `vid:pid`, que é a chave do que ELA
declarou e que se repete quando há duas unidades do mesmo aparelho.

O NOME DE CADA ADAPTADOR (22/08/2026)
--------------------------------------

Decisão dela: *"você escreve, o produto protege o prefixo"*. Três adaptadores
`2357:0604` idênticos no barramento, e a única coisa que os separa é o BD
Address — que não é nome. Quem lê e escreve o `org.bluez.Adapter1.Alias` é
`integrations/apelido_do_dongle`, o segundo módulo que estava sem consumidor.

Duas coisas desta tela dependem dele, e as duas juntas são a razão de ele ser
lido aqui e não em outro lugar:

* a coluna **"Nome"** da tabela de adaptadores, que é um campo livre. O que a
  tela mostra é o nome DELA, limpo: o prefixo `Nintendo` que segura o Pro
  Controller fora do sniff frágil é costurado por baixo, e ela nunca precisa
  saber que existe;
* o **rótulo do medidor**, que passa a dizer `Rádio em uso · Sala` em vez de um
  endereço hexa. Essa junção é por ENDEREÇO dos dois lados (o `HID_PHYS` do
  controle contra o `Address` do BlueZ) e não tem chute nenhum dentro.

A junção da TABELA é outra, e ela é a única coisa aqui que usa `hciN`: o
`Adaptador.interface` do sysfs contra o `/org/bluez/hciN` do BlueZ. O índice
inverte entre boots e por isso ele nunca é guardado — a correspondência é
refeita a cada leitura, e as duas leituras acontecem no mesmo gesto. O que vai
para a escrita é sempre o BD Address.

AS TRÊS COSTURAS DE 26/08/2026 (L2-E)
--------------------------------------

As três fecham a mesma classe de defeito — a casa sabe e o produto não faz — e
cada uma tem o "porquê" inteiro junto da constante que a carrega:

1. **o gabinete que o install já contou.** O ``install.sh`` grava o
   ``gabinete.json`` em toda instalação desde 25/08/2026 e nenhuma linha de
   ``app/`` o abria. Agora a seção o publica — **as duas contagens lado a lado
   quando elas divergem, e nunca uma escolha** (:func:`_linhas_do_gabinete`);
2. **o hub em comum.** A coluna "Onde está" escrevia ``Em hub`` linha a linha e
   nunca comparava as linhas entre si; ``censo_do_barramento.hub_em_comum``
   respondia desde 22/08 e não tinha chamador (:func:`_frase_do_hub_em_comum`);
3. **a porta da calibração.** ``interface/calibracao_das_entradas.py`` nasceu
   inteira na leva 1 e nada a abria (:meth:`_PainelDaMesa._abrir_a_calibracao`).

Todo texto novo delas está marcado ``PROVISÓRIO — decisão dela``, e a prova de
tela não fechou: a palavra final é dela.

**O nome grava NA HORA**, e a frase ao lado do campo diz isso. As três
declarações desta seção esperam o "Aplicar" do rodapé porque moram no
`maquina.json`; o alias mora no BlueZ, que não passa pelo rascunho da máquina
nem pelo rodapé. Duas semânticas na mesma seção é dívida declarada — ver o
relatório da leva.
"""
from __future__ import annotations

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O rótulo da seção; `ipc_bridge._rotulos_dos_campos` lê esta constante, nunca a copia.
TITULO = "Conexões"

DICA: str | None = (
    "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. Cabo, "
    "hub e altura mudam o alcance e não aparecem em lugar nenhum do sistema."
)

_TIPOS_DE_RADIO: tuple[tuple[str, str], ...] = (
    ("wifi", "Wi-Fi"),
    ("teclado", "Teclado"),
    ("mouse", "Mouse"),
    ("webcam", "Webcam"),
    ("caixa_de_som", "Caixa de som"),
    ("outro", "Outro"),
    ("nao_sei", "Não sei"),
)


_PERGUNTA_DA_ALTURA = "O dongle fica acima da cabeça de quem joga sentado?"

_DICA_DA_ALTURA = (
    "Corpo humano absorve 2,4 GHz. Um dongle acima da linha das cabeças rende "
    "mais que um dongle perto. Isto nenhum sistema sabe — só você."
)

_PERGUNTA_DA_VISADA = "Tem gente sentada entre o dongle e o sofá?"

_DICA_DA_VISADA = (
    "Gente no caminho entre o dongle e quem joga custa alcance, e também não "
    "há como medir daqui."
)


_BOTAO_CALIBRAR = "Mapear Entrada a Entrada"


