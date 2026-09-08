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
adaptador para BT real (`broker/hidraw_broker.py:281`), e
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
3. **a porta da calibração.** ``app/widgets/calibrar_entradas.py`` nasceu
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

import contextlib
from collections.abc import Sequence
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import (
    QUANDO_VALE,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.integrations.apelido_do_dongle import (
    Dongle,
    ler_os_dongles,
    renomear_o_dongle,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    GRAU_LIDO,
    Censo,
    hub_em_comum,
    ler_o_barramento,
)
from hefesto_dualsense4unix.integrations.censo_do_gabinete import (
    contagens_declaradas,
    ler_do_disco,
    pergunta_pendente,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    Furo,
    NoDeEntrada,
    listar_entradas,
)
from hefesto_dualsense4unix.integrations.mapa_das_portas import (
    porta_de,
    resumo_do_mapa,
)
from hefesto_dualsense4unix.integrations.mesa_de_radio import (
    Adaptador,
    Mesa,
    RadioUsb,
    ler_a_mesa,
)
from hefesto_dualsense4unix.integrations.portas_do_barramento import (
    livres,
)
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    PALAVRA_FOLGADA,
    SEM_ADAPTADOR,
    Ocupacao,
    ocupacao_por_adaptador,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    carregar_maquina,
    fundir_declaracao,
)

logger = get_logger(__name__)

#: O título como ela o lê na tela.
#:
#: **"Conexões", e a palavra é dela** (LEX-1). A seção se chamava "A mesa" — a
#: metáfora da casa para o conjunto de controles —, e o título usava a mesma
#: palavra para outra coisa: os adaptadores, os rádios e as entradas do
#: gabinete. Duas coisas com um nome só é o que faz a pessoa procurar controle
#: aqui dentro.
#:
#: O rodapé acompanha sozinho: `ipc_bridge._rotulos_dos_campos` LÊ esta
#: constante (`ipc_bridge.py:851`), nunca a copia.
TITULO = "Conexões"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. Cabo, "
    "hub e altura mudam o alcance e não aparecem em lugar nenhum do sistema."
)

#: Os sete botões da coluna "O que é", na ordem do desenho. Os seis primeiros
#: são exatamente os `Literal` de `RadioDeclarado.tipo`; o sétimo é a ausência
#: de opinião, que o esquema representa como `None` e não como palavra.
#:
#: O "Outro" NÃO abre campo de texto aqui, e o desenho abria
#: (`mockup:1148`, "Fone sem fio da TV"). O `apelido` existe no esquema e é
#: entrega de outra leva: um `Gtk.Entry` por linha numa tabela que já tem três
#: colunas custaria a largura que esta janela não tem, e o apelido não muda uma
#: linha do que o exame consegue afirmar — o `tipo` muda.
_TIPOS_DE_RADIO: tuple[tuple[str, str], ...] = (
    ("wifi", "Wi-Fi"),
    ("teclado", "Teclado"),
    ("mouse", "Mouse"),
    ("webcam", "Webcam"),
    ("caixa_de_som", "Caixa de som"),
    ("outro", "Outro"),
    ("nao_sei", "Não sei"),
)

#: `id -> palavra de tela` dos tipos acima. Existe para que a linha que ELA
#: corrigiu mostre a palavra dela, e não o identificador do esquema.
_PALAVRA_DO_TIPO: dict[str, str] = dict(_TIPOS_DE_RADIO)

#: O selo de quem respondeu, na coluna "O que é". São os três degraus da
#: precedência, e cada um tem de ser distinguível do outro na tela: sem isso a
#: pessoa não sabe se está olhando o que ela disse ou o que a máquina deduziu.
#:
#: Começam por parêntese de propósito — o portão de maiúscula
#: (`validar-palavra-de-tela.py:174`) só olha a primeira LETRA, e uma palavra
#: solta em minúscula ao lado do valor é a gramática que a casa já usa no selo
#: do medidor ("derivado da especificação").
_SELO_LIDO = "(lido)"
_SELO_DECLARADO = "(você disse)"

#: A dica do selo `(lido)`. Ela é a única coisa na tela que diz DE ONDE veio a
#: palavra — sem ela, a classificação parece chute do produto.
_DICA_LIDO = (
    "O próprio aparelho informou ao sistema o que ele é. "
    'Se estiver errado, clique em "Corrigir".'
)

#: A dica do selo `(você disse)`.
_DICA_DECLARADO = (
    'Foi você quem respondeu isto. Clique em "Corrigir" para trocar a resposta.'
)

#: O botão que abre o seletor numa linha já respondida.
_BOTAO_CORRIGIR = "Corrigir"

#: A linha que aparece quando nem o sistema nem ela sabem o que é o aparelho.
#: Ela repete a palavra do subcabeçalho — *"o Hefesto encontra os aparelhos,
#: mas não sabe para que servem"* — de propósito: é a mesma frase, aplicada a
#: uma linha, e um vocabulário novo aqui faria parecer outro assunto.
_AVISO_NAO_SABE = "▲ O Hefesto não sabe"

#: A dica do `▲`. Diz o fato medido sem jargão: há aparelho que não se declara.
_DICA_NAO_SABE = (
    "Este aparelho não diz ao sistema para que serve. É a única linha que "
    "precisa de você."
)

#: O cabeçalho e a dica da coluna do nome de cada adaptador.
_COLUNA_NOME = "Nome"
_DICA_DO_NOME = (
    "Adaptadores iguais são idênticos no sistema. O nome é seu, e é ele que "
    "diz qual é qual."
)

#: O texto do campo vazio. Não é rótulo: é o cinza que o `Gtk.Entry` mostra
#: enquanto ninguém escreveu nada.
_NOME_EM_BRANCO = "Sem nome"

#: A frase que diz que ESTE campo não espera o rodapé.
#:
#: Ela não é o `moldura.VALE_JA`, e a diferença é deliberada: aquela frase fala
#: da SEÇÃO inteira, e nesta seção as três declarações continuam esperando o
#: "Aplicar". Uma seção que mostrasse as duas frases gerais se contradiria —
#: há portão que reprova (`test_as_duas_frases_nunca_aparecem_na_mesma_secao`).
#: Esta é por CAMPO, mora colada na tabela do campo, e diz o que acontece com
#: o gesto dele.
_NOME_VALE_JA = (
    "O nome vai para o Bluetooth do sistema assim que você aperta Enter."
)

#: A nota que explica o prefixo que ela nunca escreveu. Só aparece quando algum
#: adaptador da mesa hospeda um controle da linhagem Nintendo — em mesa sem Pro
#: ela seria uma explicação sobre coisa nenhuma.
_NOTA_DO_PREFIXO = (
    "▲ Um dos adaptadores guarda a palavra Nintendo por dentro do nome: é ela "
    "que impede o Pro Controller de cair sob carga. O Hefesto cuida disso "
    "sozinho, e o nome que você lê aqui é só o seu."
)

#: As SETE palavras do painel do gabinete, uma por valor de
#: `physical_location/panel` do kernel. O desenho só previa duas ("Frente" e
#: "Trás") e o kernel entrega sete — esta bancada mede `right`, que sem as
#: outras cinco cairia em "Não sei" justamente no único aparelho da casa que
#: SABE onde está. Decisão M2 de `DECISOES-DA-EXECUCAO.md`.
_PAINEL_EM_PORTUGUES: dict[str, str] = {
    "front": "Frente",
    "back": "Trás",
    "left": "Esquerda",
    "right": "Direita",
    "top": "Cima",
    "bottom": "Baixo",
}

#: A resposta quando o kernel não sabe — e ela é comum: o arquivo
#: `physical_location/panel` não existe em boa parte dos aparelhos, e some
#: sempre atrás de um hub. Chutar "Frente" aqui seria a tela afirmando o que
#: ninguém mediu.
_PAINEL_DESCONHECIDO = "Não sei"

# -- as duas perguntas que máquina nenhuma responde (LEX-9) -------------------
#
# A REDAÇÃO É DECIDIDA, e a decisão é `D-REDACAO-DAS-DUAS-PERGUNTAS-DE-RADIO`
# (`docs/data/decisoes-dela.csv:36`, decidida por delegação em 25/08/2026,
# marcada para o olho dela). A queixa que a derrubou é dela, de 24/08:
# *"Eu não sei o que é altura da antena. nem linha de visada. sinceramente não
# faço ideia."*
#
# O CONTEÚDO NÃO SAI — o `GUIA-RADIO-DA-SALA.md` §4.4 mede que subir 40 cm rende
# mais que aproximar 5 m, e é isso que as duas perguntas colhem. O que muda é a
# palavra: jargão que a pessoa teria de pesquisar é defeito, não precisão.
#
# **AS CHAVES E OS VALORES DO ESQUEMA NÃO MUDAM.** `MesaDeclarada` usa `Literal`
# com `extra="forbid"`: trocar `"acima"` por `"sim"` faria o pydantic recusar o
# DOCUMENTO INTEIRO de quem já declarou, e o sintoma seria "não consegui
# gravar" — a causa certa com o sintoma errado. Só o RÓTULO e a PALAVRA DO
# BOTÃO mudam; a tradução botão -> valor está na tupla de cada `_linha_declarada`.
#
# A INVERSÃO DA SEGUNDA É DE PROPÓSITO. "Linha de visada: Livre" virou "Tem
# gente sentada entre o dongle e o sofá? Não" — a pergunta trocou de sinal, e
# por isso "Sim" grava `com_gente` e "Não" grava `livre`. Manter a ordem antiga
# faria a tela gravar o oposto do que ela respondeu.

#: PROVISÓRIO — decisão dela (a redação está decidida; o olho dela não a viu).
_PERGUNTA_DA_ALTURA = "O dongle fica acima da cabeça de quem joga sentado?"

#: PROVISÓRIO — decisão dela.
_DICA_DA_ALTURA = (
    "Corpo humano absorve 2,4 GHz. Um dongle acima da linha das cabeças rende "
    "mais que um dongle perto. Isto nenhum sistema sabe — só você."
)

#: PROVISÓRIO — decisão dela.
_PERGUNTA_DA_VISADA = "Tem gente sentada entre o dongle e o sofá?"

#: PROVISÓRIO — decisão dela.
_DICA_DA_VISADA = (
    "Gente no caminho entre o dongle e quem joga custa alcance, e também não "
    "há como medir daqui."
)

#: A dica do par colado, literal do desenho aprovado (`TOOLTIPS.md`).
_DICA_COLADOS = (
    "Dois rádios encostados um no outro se atrapalham. Vale afastar em portas "
    "diferentes."
)

#: A dica do rádio USB 3.0 ao lado do adaptador, literal do mesmo desenho. Ela
#: afirma "USB 3.0", então só aparece onde `speed >= 5000` foi medido.
_DICA_USB3_AO_LADO = (
    "USB 3.0 emite ruído de banda larga bem em cima dos 2,4 GHz. Ao lado do "
    "adaptador Bluetooth, atrapalha."
)

#: Laranja de ATENÇÃO, `@orange` do `theme.css:27`. É a cor que a casa já usa
#: para `[WARN]` nesta mesma janela (`daemon_actions.py:754`) — o desenho da
#: leva dizia "amarelo", e o tema vence (F2).
_LARANJA = "#ffb86c"

#: Verde de "está folgado", `@green` do `theme.css:26`.
_VERDE = "#50fa7b"

#: A dica do rótulo do medidor, literal do desenho aprovado (`TOOLTIPS.md`).
#: Ela é a ÚNICA coisa na tela que declara de onde vêm as 1.600 fatias — e o
#: número não é medição desta máquina.
_DICA_DO_MEDIDOR = (
    "Aritmética da especificação do Bluetooth, não medição desta máquina: o "
    "rádio tem 1.600 fatias de tempo por segundo e todos os controles do mesmo "
    "adaptador as dividem."
)

#: O selo de procedência, montado em Python porque os dois números são
#: calculados. A frase depois do meio-ponto não muda nunca: é ela que impede a
#: barra de ser lida como medição.
_SELO_DE_PROCEDENCIA = "derivado da especificação"

#: O selo quando NINGUÉM respondeu — o par do `_PAINEL_DESCONHECIDO` na mesma
#: fileira. Sem daemon não há número, e "0/1600" seria afirmação numérica sobre
#: o que não se mediu. PROVISÓRIO: frase nova, pendente do olho dela.
_SEM_RESPOSTA_DO_DAEMON = "o daemon não respondeu"

#: Quanto texto cabe numa linha de apoio desta seção antes de quebrar. Menor
#: que o padrão de 92 da moldura porque a seção já gasta largura com duas
#: tabelas, e a rolagem horizontal não existe nesta janela.
_LARGURA_DA_FRASE = 84


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.

    Os dois últimos gestos penduram coisas no hospedeiro, e nenhum é acidente:

    * `_reexaminar_a_mesa` é o nome que o `_REFRESH_POR_ABA` (`app/app.py`)
      procura para reler o barramento ao ENTRAR na aba. Ele nasce aqui, e não
      no `mixin.py`, porque o montador da aba não conhece uma linha do que há
      dentro de nenhuma seção — e é isso que deixa oito frentes crescerem no
      mesmo lugar sem se pisarem;
    * `_mesa_declarada` é o espelho de leitura das duas escolhas que barramento
      nenhum responde. Desde 22/08/2026 ele **não é mais o dono**: quem guarda
      é `host._maquina_pendente`, e quem grava é o "Aplicar" do rodapé. O
      dicionário fica porque é por onde um teste ou o retrato olha o estado da
      seção sem alcançar widget nenhum.
    """
    painel = _PainelDaMesa(host)
    painel.montar(caixa)
    host._reexaminar_a_mesa = painel.reexaminar
    host._mesa_declarada = painel.declarado


class _PainelDaMesa:
    """Os widgets da seção e a leitura que os preenche.

    Uma instância por montagem. As duas tabelas moram dentro de caixas que
    ficam: reexaminar esvazia a caixa e a preenche de novo, em vez de mexer na
    página — assim a ordem dos filhos da seção nunca muda, e a tela não pula.
    """

    def __init__(self, host: Any) -> None:
        self._host = host
        self._caixa_adaptadores: Any = None
        self._caixa_radios: Any = None
        self._caixa_medidores: Any = None
        #: A última mesa lida — o medidor precisa dela quando a resposta do
        #: daemon chega DEPOIS da leitura do barramento (é sempre o caso).
        self._mesa = Mesa()
        #: O barramento USB inteiro, na palavra do kernel. É ele que preenche a
        #: coluna "O que é" sem perguntar nada a ela. Censo vazio é resposta:
        #: toda linha cai em "não sei" e o seletor abre sozinho.
        self._censo = Censo()
        #: O gabinete que ELA desenhou — o disco com o rascunho por cima. Mapa
        #: vazio é o estado mais comum lá fora e não regride nada: sem ele a
        #: seção fala exatamente como falava antes desta leva.
        self._mapa = MapaDaMesa()
        #: A caixa da linha-resumo do mapa. Ela vive numa caixa própria pelo
        #: mesmo motivo das outras três: reexaminar esvazia e preenche de novo,
        #: e a ordem dos filhos da seção nunca muda.
        self._caixa_do_mapa: Any = None
        #: O `gabinete.json` que o install gravou — `{}` quando não há, que é a
        #: primeira instalação e todo install anterior a 25/08/2026. Vazio a
        #: seção fala exatamente como falava antes desta leva.
        self._gabinete: dict[str, Any] = {}
        #: Os nós de ENTRADA, inclusive os vazios. É a única leitura que alcança
        #: um buraco sem aparelho, e é dela que sai tanto o conselho do hub
        #: quanto o que a janela de calibração recebe pronto.
        self._entradas: tuple[NoDeEntrada, ...] = ()
        #: A caixa das contagens do gabinete mais o botão da calibração.
        self._caixa_do_gabinete: Any = None
        #: A caixa da linha do hub em comum. Ela fica colada na tabela dos
        #: adaptadores porque é sobre eles que ela fala.
        self._caixa_do_hub: Any = None
        #: Os adaptadores pela ótica do BlueZ — endereço, alias e quem hospeda
        #: Nintendo. Tupla vazia é o caso comum e legítimo: sem `busctl`, com o
        #: `bluetoothd` parado, no Flatpak, ou em máquina sem adaptador.
        self._dongles: tuple[Dongle, ...] = ()
        #: Impede empilhar leituras do BlueZ quando ela clica duas vezes.
        self._dongles_pedidos = False
        #: `vid:pid` das linhas em que ela abriu o seletor para corrigir. Vive
        #: só nesta montagem: corrigir é gesto, não declaração.
        self._corrigindo: set[str] = set()
        #: `endereço -> Gtk.Entry` do nome de cada adaptador. Existe para uma
        #: coisa só: não redesenhar a tabela por baixo de quem está digitando.
        self._campos_de_nome: dict[str, Any] = {}
        #: `state["controllers"]` da última resposta, e os `uniq` com ponte de
        #: microfone de pé. Nascem vazios, e barra em zero é o desenho certo
        #: enquanto ninguém respondeu: zero é o que se sabe.
        self._controles: list[dict[str, Any]] = []
        self._com_mic: frozenset[str] = frozenset()
        #: Impede empilhar pedidos ao daemon quando ela troca de aba rápido.
        self._estado_pedido = False
        #: `None` = ainda não perguntei, `True` = respondeu, `False` = não
        #: respondeu. Sem ele a tela do daemon fora do ar era byte a byte a de
        #: um rádio vazio — "Folgada", em verde, "0/1600" (medido em
        #: 23/08/2026) —, e quem entrava na aba para diagnosticar rádio cheio
        #: lia "está folgado" e ia procurar o defeito no controle.
        self._daemon_respondeu: bool | None = None
        #: A declaração dela nesta sessão, espelho de leitura do que já foi
        #: acumulado em `host._maquina_pendente`. Exposto no hospedeiro como
        #: `_mesa_declarada`.
        #:
        #: ELE NÃO É MAIS O DONO (22/08/2026). Até esta data o dicionário era o
        #: único lugar onde a escolha existia, e o TODO daqui dizia que o valor
        #: morria com a janela — mas a camada que faltava nasceu no MESMO dia
        #: (CONFIG-03, `utils/maquina.py` mais o `machine.declare` do IPC), e o
        #: TODO sobreviveu a ela. Foi a classe de defeito mais cara desta casa
        #: acontecendo dentro da leva que a documentou: a cura escrita e nunca
        #: ligada. Quem grava agora é o "Aplicar" do rodapé, pela mesma rota das
        #: outras seções — `host._maquina_pendente`.
        self.declarado: dict[str, str | None] = {
            "altura_da_antena": None,
            "linha_de_visada": None,
        }
        #: O tipo declarado de cada rádio vizinho, por `vid:pid`. Mesma rota.
        self.radios_declarados: dict[str, str | None] = {}

    # -- montagem ----------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        """Desenha a seção inteira e faz a primeira leitura."""
        from gi.repository import Gtk

        self._caixa_adaptadores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_adaptadores, False, False, 0)

        # O hub em comum fala dos ADAPTADORES, e por isso mora colado na tabela
        # deles — a linha responde a pergunta que a coluna "Em hub" levanta e
        # não responde. PROVISÓRIO — o lugar da linha é decisão dela.
        self._caixa_do_hub = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_do_hub, False, False, 0)

        # A linha do mapa fica colada na tabela que ela explica: é a coluna
        # "Onde está" que passa a falar o número dela. PROVISÓRIO — o lugar da
        # linha é decisão dela, e a prova de tela desta leva não fechou.
        self._caixa_do_mapa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_do_mapa, False, False, 0)

        # O gabinete que o install contou vem logo abaixo do mapa: as duas
        # falam de ENTRADA, e a cerimônia de calibração é o que preenche o mapa
        # com o que o desenho à mão não alcança — a entrada vazia.
        # PROVISÓRIO — o lugar do bloco é decisão dela.
        self._caixa_do_gabinete = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_do_gabinete, False, False, 0)

        caixa.pack_start(self._declaracoes(), False, False, 0)

        # O medidor fica ENTRE as declarações e os outros rádios, como no
        # desenho (`mockup/aba-configuracoes.html:365-373`), e a ordem faz
        # sentido de cima para baixo: primeiro quais adaptadores existem,
        # depois o que você declarou sobre eles, depois quanto do rádio deles
        # já está comprometido, e só então o que mais divide a faixa.
        self._caixa_medidores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.pack_start(self._caixa_medidores, False, False, 0)

        caixa.pack_start(
            self._subcabecalho(
                "Outros rádios que dividem a faixa",
                "Tudo aqui divide a faixa de 2,4 GHz com os controles. O "
                "Hefesto encontra os aparelhos, mas não sabe para que servem.",
            ),
            False,
            False,
            0,
        )

        self._caixa_radios = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_radios, False, False, 0)

        # LEX-2, ITEM 3 — A `QUANDO_VALE` SAIU DA PÁGINA (26/08/2026).
        #
        # As três declarações desta seção continuam DIFERIDAS e a frase
        # continua sendo a mesma constante do Desempenho e de Os controles
        # (`moldura.QUANDO_VALE`) — o que mudou é onde ela mora. Ela diria a
        # mesma coisa com a mesa vazia e com a mesa cheia, logo é EXPLICAÇÃO, e
        # explicação vai para o hover do widget que ela explica: as fileiras de
        # `_linha_declarada`, que são exatamente o que acumula no rascunho.
        caixa.pack_start(self._botao_de_reexame(), False, False, 0)
        # Montar lê o BARRAMENTO e nada mais. O `daemon.state_full` que
        # alimenta o medidor fica de fora daqui de propósito, pelo mesmo motivo
        # da decisão E6 do exame: `install_config_tab` roda no ARRANQUE da
        # janela (`app/app.py:1217` e `:1487`), inclusive por quem sobe
        # minimizado na bandeja, e é por esse caminho que o retrato passa. Uma
        # aba que ninguém abriu não fala com o daemon.
        self._reler_a_mesa()

    def _declaracoes(self) -> Any:
        """As duas perguntas que barramento nenhum responde.

        Elas ficam ENTRE as duas tabelas, como no desenho, e é o lugar certo:
        vêm logo depois do que a máquina soube dizer sozinha, e antes do que
        ela sabe menos ainda.
        """
        from gi.repository import Gtk

        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        caixa.set_margin_top(6)
        caixa.pack_start(
            self._linha_declarada(
                "altura_da_antena",
                _PERGUNTA_DA_ALTURA,
                _DICA_DA_ALTURA,
                [
                    ("acima", "Sim"),
                    ("abaixo", "Não"),
                    ("nao_sei", "Não sei"),
                ],
            ),
            False,
            False,
            0,
        )
        caixa.pack_start(
            self._linha_declarada(
                "linha_de_visada",
                _PERGUNTA_DA_VISADA,
                _DICA_DA_VISADA,
                [
                    ("com_gente", "Sim"),
                    ("livre", "Não"),
                    ("nao_sei", "Não sei"),
                ],
            ),
            False,
            False,
            0,
        )
        return caixa

    def _linha_declarada(
        self, chave: str, rotulo: str, dica: str, itens: list[tuple[str, str]]
    ) -> Any:
        """Rótulo com dica mais botões segmentados, numa fileira.

        `Gtk.ComboBox` está proibido nesta casa: o cosmic-comp rouba o foco no
        clique e FECHA o popup na hora (cosmic-epoch#2497), então a pessoa não
        consegue escolher. O `SegmentedSelector` não tem popup nenhum.

        A fileira NÃO é homogênea, e isso é regra medida: uma fileira homogênea
        com rótulo longo já custou 1004 dos 1066px da largura mínima da janela.
        """
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        texto = Gtk.Label(label=_(rotulo))
        texto.set_xalign(0.0)
        # A `QUANDO_VALE` viaja ANEXADA à dica da fileira, e não como parágrafo
        # (LEX-2, item 3). Aqui e não noutro widget porque É esta fileira que
        # acumula no rascunho: quem clica num destes botões e não vê nada
        # acontecer é quem precisa da frase, e ela está sob o cursor dele.
        texto.set_tooltip_text(f"{_(dica)} {_(QUANDO_VALE)}")
        with contextlib.suppress(Exception):
            texto.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(texto, False, False, 0)

        seletor = SegmentedSelector()
        # O `SegmentedSelector` nasce VERTICAL (`segmented_selector.py:204`) e o
        # modo sem `wrap` empacota os botões no próprio widget — medido em
        # 22/08/2026 na foto desta seção: "Acima", "Abaixo" e "Não sei" saíram
        # empilhados, três linhas onde o desenho tem uma. A fileira do desenho é
        # horizontal, e o pedido é DESTA tela: mudar o padrão do widget mexeria
        # em cinco outras.
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        seletor.set_items([(ident, _(nome)) for ident, nome in itens])
        # A pré-seleção vem ANTES do `connect`, e é a diferença entre mostrar o
        # que ela escolheu e re-escrever no rascunho tudo o que a tela desenhou:
        # `set_active_id` emite `changed`, e com o sinal já ligado o simples ato
        # de abrir a aba marcaria o rascunho como sujo. O rodapé passaria a ter
        # o que "Aplicar" sem ninguém ter clicado em nada.
        gravado = self._mesa_em_vigor().get(chave)
        if gravado is not None:
            self.declarado[chave] = str(gravado)
            with contextlib.suppress(Exception):
                seletor.set_active_id(str(gravado))
        seletor.connect("changed", self._ao_declarar, chave)
        fileira.pack_start(seletor, False, False, 0)
        return fileira

    def _subcabecalho(self, texto: str, dica: str) -> Any:
        """O rótulo da sub-seção mais o `?` que carrega a explicação."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        fileira.set_margin_top(6)
        rotulo = Gtk.Label(label=_(texto))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo-secao")
        fileira.pack_start(rotulo, False, False, 0)

        ajuda = Gtk.Label(label="?")
        ajuda.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            ajuda.get_style_context().add_class("dim-label")
        fileira.pack_start(ajuda, False, False, 0)
        return fileira

    def _botao_de_reexame(self) -> Any:
        """O botão que relê o barramento.

        Ele mora DENTRO da seção, e não no rodapé da aba como o desenho mostra,
        por dois motivos que apontam para o mesmo lado: o rodapé da janela é do
        "Aplicar" e é território de outra frente, e um botão que só relê a mesa
        se explica melhor colado na mesa que releu.
        """
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        fileira.set_margin_top(6)
        # A PALAVRA "mesa" SAIU DA TELA em 05/09/2026, ordem dela. O que este
        # botão relê é o BARRAMENTO — os adaptadores e os rádios —, e a própria
        # dica ao lado já dizia isso sem a palavra.
        botao = Gtk.Button(label=_("Reexaminar as conexões"))
        botao.set_tooltip_text(_("Relê os adaptadores e os rádios. Não muda nada."))
        botao.connect("clicked", self._ao_clicar_reexaminar)
        fileira.pack_start(botao, False, False, 0)
        return fileira

    # -- leitura -----------------------------------------------------------

    def reexaminar(self) -> None:
        """Relê tudo: o barramento agora, e quem está no rádio quando chegar.

        É o refresher da aba: `_REFRESH_POR_ABA` o chama ao ENTRAR na
        Configurações, e o botão o chama de novo. Nunca em tique — os tiques da
        casa são de 100 ms, 500 ms e 2 s, e uma varredura de barramento em
        qualquer um deles é gastar CPU relendo o que não muda entre dois
        quadros.

        As duas leituras são assimétricas de propósito: o barramento responde
        na hora, e o daemon responde por callback. É por isso que o medidor é
        desenhado DUAS vezes — uma com o que já se sabe, outra quando a
        resposta chega. Esperar a segunda para desenhar a primeira deixaria a
        seção em branco no gesto mais comum da aba.
        """
        self._reler_a_mesa()
        self._pedir_o_estado()
        self._pedir_os_dongles()

    def _reler_a_mesa(self) -> None:
        """A metade síncrona: `/sys` agora, as três caixas redesenhadas.

        Engole a própria exceção porque o chamador não a embrulha: `app.py`
        chama o refresher direto, e uma leitura de `/sys` que falhe não pode
        derrubar a troca de aba.
        """
        try:
            mesa = self._ler()
            self._mesa = mesa
            self._censo = self._ler_o_censo()
            self._entradas = self._ler_as_entradas()
            self._gabinete = self._ler_o_gabinete()
            self._mapa = self._mapa_em_vigor()
            self._ler_os_dongles_de_bancada()
            self._desenhar_adaptadores(mesa)
            self._desenhar_o_hub()
            self._desenhar_o_mapa()
            self._desenhar_o_gabinete()
            self._desenhar_radios(mesa)
            self._desenhar_medidores()
        except Exception:
            logger.warning("mesa_reexame_falhou", exc_info=True)

    def _ler(self) -> Mesa:
        """A leitura, ou a bancada de mentira que o retrato injetou.

        `_mesa_leitor` é O ponto de injeção da seção, e ele existe por um
        motivo só: a foto da aba entra em `docs/usage/assets` sem revisão
        humana, e nenhum portão desta casa varre imagem. Uma seção que lesse
        `/sys` de verdade durante a captura publicaria o barramento dela num
        PNG versionado — que é o incidente que a `test_retrato_das_abas_nao_
        vaza_dado_real` existe para não repetir, e que ela não pega.
        """
        leitor = getattr(self._host, "_mesa_leitor", None)
        if leitor is None:
            return ler_a_mesa()
        resultado = leitor()
        return resultado if isinstance(resultado, Mesa) else Mesa()

    def _ler_o_censo(self) -> Censo:
        """O barramento USB inteiro — ou a bancada de mentira do retrato.

        Duas varreduras de `/sys` por reexame, e não uma, porque as duas
        respondem perguntas diferentes: `ler_a_mesa` diz QUAIS aparelhos são
        rádio vizinho (e já exclui hub, adaptador e controle), e o censo diz o
        QUE cada aparelho é. Fundir os dois módulos faria a tabela de rádios
        depender de um leitor que não filtra nada.

        **A guarda do retrato é a mesma da mesa, e pelo mesmo motivo.** Sem o
        `_censo_leitor`, uma captura publicaria a espécie de cada aparelho DELA
        num PNG versionado. Censo vazio na foto seria pior que nada: a coluna
        inteira cairia em "não sei" e a documentação mostraria a tela errada —
        por isso o retrato injeta, e a ausência do dublê durante uma captura é
        censo vazio, nunca leitura viva.
        """
        leitor = getattr(self._host, "_censo_leitor", None)
        if leitor is not None:
            resultado = leitor()
            return resultado if isinstance(resultado, Censo) else Censo()
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return Censo()
        return ler_o_barramento()

    def _ler_as_entradas(self) -> tuple[NoDeEntrada, ...]:
        """Os nós de entrada, inclusive os VAZIOS — ou a bancada de mentira.

        Terceira varredura de `/sys` por reexame, e ela responde o que as outras
        duas não sabem responder: **uma entrada vazia não tem aparelho**, logo
        não aparece nem em `ler_a_mesa` nem em `ler_o_barramento`. É esta
        leitura que sustenta o "há entrada livre em outro caminho" do hub e é
        ela que a janela de calibração recebe pronta, sem reler.

        A guarda do retrato é a mesma das outras duas, e pelo mesmo motivo: sem
        dublê, durante uma captura, a resposta é tupla vazia — nunca leitura
        viva. Sem entradas o conselho do hub não nasce, que é o desenho certo:
        um conselho que não sabe para onde mandar não é conselho.
        """
        leitor = getattr(self._host, "_entradas_leitor", None)
        if leitor is not None:
            with contextlib.suppress(Exception):
                return tuple(leitor())
            return ()
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return ()
        return listar_entradas()

    def _ler_o_gabinete(self) -> dict[str, Any]:
        """O `gabinete.json` que o install gravou — `{}` quando não há.

        Ele é a ÚNICA fonte da tabela SMBIOS tipo 8 nesta janela: o arquivo do
        DMI é `400 root` e a janela é sudo-zero, então quem leu foi o install,
        uma vez, como root. Aqui só se abre o que ele deixou.

        `ler_do_disco` já engole arquivo ausente, truncado e de formato futuro —
        os três dão a mesma resposta honesta, e nenhum derruba a seção.

        A guarda do retrato existe para que a foto não publique a contagem da
        máquina de quem capturou: sem dublê, durante uma captura, o gabinete é
        vazio e o bloco não aparece.
        """
        leitor = getattr(self._host, "_gabinete_leitor", None)
        if leitor is not None:
            with contextlib.suppress(Exception):
                lido = leitor()
                return lido if isinstance(lido, dict) else {}
            return {}
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return {}
        return ler_do_disco()

    def _ler_os_dongles_de_bancada(self) -> None:
        """A leitura do BlueZ quando ela é de mentira — e só então.

        O dublê é de MEMÓRIA e responde na hora, então entra no caminho
        síncrono. A leitura de verdade não pode: ela é `busctl`, um subprocesso
        por propriedade e por adaptador, e este método roda dentro de `montar`.

        `montar` acontece no ARRANQUE da janela (`app/app.py:1217` e `:1487`),
        inclusive em quem sobe minimizado na bandeja — é a mesma decisão E6 que
        mantém o `daemon.state_full` fora daqui. Uma aba que ninguém abriu não
        fala com o BlueZ nem gasta treze subprocessos.
        """
        leitor = getattr(self._host, "_dongles_leitor", None)
        if leitor is None:
            return
        with contextlib.suppress(Exception):
            self._dongles = tuple(leitor())

    def _pedir_os_dongles(self) -> None:
        """Pede ao BlueZ o nome de cada adaptador — fora da thread da tela.

        Três guardas antes de gastar um subprocesso, e cada uma fecha um
        defeito diferente:

        * **dublê montado** — quem injetou já respondeu no caminho síncrono;
        * **retrato sem dublê** — o alias do BlueZ é texto que ELA escreveu, e
          a foto vai para `docs/usage/assets/` sem revisão humana (F5);
        * **mesa sem adaptador** — sem adaptador não há nome a dar, e é o caso
          mais comum lá fora. É esta guarda que mantém `busctl` fora de toda
          máquina que não tem Bluetooth, e fora da bateria de testes.

        `run_in_thread` e não `call_async`: isto não é IPC com o Hefesto, é
        subprocesso. Os dois compartilham o mesmo executor de um worker.
        """
        if getattr(self._host, "_dongles_leitor", None) is not None:
            return
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return
        if not self._mesa.adaptadores or self._dongles_pedidos:
            return

        from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread

        def _chegaram(resultado: Any) -> bool:
            self._dongles_pedidos = False
            if isinstance(resultado, tuple):
                self._dongles = resultado
                self._redesenhar_os_nomes()
            return False

        def _falhou(_exc: Exception) -> bool:
            self._dongles_pedidos = False
            # BlueZ mudo não é "adaptador sem nome": é "não sei o nome". A
            # coluna simplesmente não aparece, que é o que a tabela já faz
            # quando ninguém respondeu.
            return False

        self._dongles_pedidos = True
        run_in_thread(ler_os_dongles, _chegaram, _falhou)

    def _redesenhar_os_nomes(self) -> None:
        """Redesenha o que depende do BlueZ — a não ser que ela esteja digitando.

        A resposta chega dezenas de milissegundos depois de entrar na aba, e
        nesse instante ninguém está no campo. Mas "Reexaminar a mesa" pode ser
        clicado com um nome pela metade no campo ao lado, e redesenhar ali
        apagaria o que ela escreveu sem aviso.
        """
        digitando = any(
            campo.has_focus()
            for campo in self._campos_de_nome.values()
            if hasattr(campo, "has_focus")
        )
        if digitando:
            return
        self._desenhar_adaptadores(self._mesa)
        self._desenhar_medidores()

    def _pedir_o_estado(self) -> None:
        """Pede ao daemon quem está no rádio — sem bloquear a thread da tela.

        O medidor precisa de UMA coisa que o sysfs desta seção não tem: a lista
        de controles conectados, com transporte e `uniq`. Ela mora no
        `daemon.state_full`, e vem por `call_async` porque o refresher roda na
        thread do GTK ao trocar de aba: um IPC síncrono ali congelaria a janela
        no gesto mais comum da aba.

        **A foto não fala com o daemon, e a guarda é a mesma da mesa.** Quem
        injetou `_mesa_leitor` está capturando `docs/usage/assets/` — e o
        `state_full` desta máquina traz o `uniq` dos controles DELA, que é MAC.
        Nenhum portão de anonimato varre imagem (F5). Com o desvio de pé o
        medidor fica com o que já tem, que é zero, e a foto sai com a barra
        vazia — o resultado honesto de uma bancada sem rádio.
        """
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return
        if self._estado_pedido:
            return

        # O timeout é o MESMO de toda leitura de `daemon.state_full` da casa
        # (`mode_transition.py:43`, HARM-15: 1,0 s, porque sob hotplug o daemon
        # passa dos 0,25 s de padrão do `call_async` e a janela o declarava
        # morto estando vivo). Um número próprio aqui seria um segundo dono da
        # mesma folga.
        from hefesto_dualsense4unix.app.actions.mode_transition import (
            STATE_IPC_TIMEOUT_S,
        )
        from hefesto_dualsense4unix.app.ipc_bridge import call_async

        def _chegou(estado: Any) -> bool:
            self._estado_pedido = False
            self._daemon_respondeu = True
            self._aplicar_estado(estado if isinstance(estado, dict) else None)
            return False

        def _falhou(_exc: Exception) -> bool:
            self._estado_pedido = False
            # Daemon fora do ar é "não sei quem está no rádio", e zerar a barra
            # só basta se a PALAVRA e o SELO disserem que é não-sei: zero pinta
            # verde e "0/1600" é afirmação numérica.
            self._daemon_respondeu = False
            self._aplicar_estado(None)
            return False

        self._estado_pedido = True
        call_async(
            "daemon.state_full", None, _chegou, _falhou, timeout_s=STATE_IPC_TIMEOUT_S
        )

    def _aplicar_estado(self, estado: dict[str, Any] | None) -> None:
        """Guarda os controles e os `uniq` com microfone, e redesenha."""
        controles = (estado or {}).get("controllers")
        if isinstance(controles, list):
            self._controles = [c for c in controles if isinstance(c, dict)]
        else:
            self._controles = []
        # A TERCEIRA chave do bloco `bt_mic` — a lista de `uniq` com ponte de
        # microfone de pé. As outras duas (`enabled`, `running`) são do PROCESSO
        # e não do controle: com quatro controles e uma ponte elas diriam
        # `running: true` e pintariam áudio nos quatro.
        #
        # LIGADA em 22/08/2026 pela QUATRO-MICROFONES-01. A leitura tolerante
        # continua: um daemon mais velho que a janela (o caso normal num install
        # editable) não manda a chave, e ausência vira conjunto vazio — a barra
        # conta aquele controle como sem microfone em vez de cair.
        bloco = (estado or {}).get("bt_mic")
        uniqs = bloco.get("uniqs") if isinstance(bloco, dict) else None
        if isinstance(uniqs, list):
            self._com_mic = frozenset(u for u in uniqs if isinstance(u, str))
        else:
            self._com_mic = frozenset()
        self._desenhar_medidores()

    # -- desenho das tabelas -----------------------------------------------

    def _desenhar_adaptadores(self, mesa: Mesa) -> None:
        """A tabela de adaptadores — ou a frase de que não há nenhum."""
        if self._caixa_adaptadores is None:
            return
        self._esvaziar(self._caixa_adaptadores)
        if not mesa.adaptadores:
            # Decisão M5: tabela em branco parece defeito. Uma linha de texto
            # diz o mesmo sem culpa e sem jargão — e é o estado REAL desta
            # bancada, onde `/sys/class/bluetooth` está vazio.
            self._caixa_adaptadores.pack_start(
                rotulo_de_apoio(
                    "Nenhum adaptador Bluetooth encontrado. Os controles no "
                    "cabo continuam funcionando.",
                    largura_max=_LARGURA_DA_FRASE,
                ),
                False,
                False,
                0,
            )
            self._caixa_adaptadores.show_all()
            return

        por_interface = _dongle_por_interface(self._dongles)
        # A coluna do nome só existe quando o BlueZ respondeu por ALGUM
        # adaptador desta tabela. É a mesma régua que manteve "Firmware" fora
        # daqui: coluna que só sabe dizer "não sei" em toda linha ocupa
        # largura, que é o recurso escasso desta janela, e ensina a ignorar a
        # tabela. No Flatpak e com o `bluetoothd` parado ela não aparece.
        com_nome = any(
            adaptador.interface in por_interface for adaptador in mesa.adaptadores
        )
        self._campos_de_nome = {}

        cabecalhos = ["Adaptador", "Onde está"]
        if com_nome:
            cabecalhos.insert(0, _COLUNA_NOME)
        grade = self._grade(cabecalhos)
        if com_nome:
            with contextlib.suppress(Exception):
                grade.get_child_at(0, 0).set_tooltip_text(_(_DICA_DO_NOME))

        for linha, adaptador in enumerate(mesa.adaptadores, start=1):
            coluna = 0
            if com_nome:
                grade.attach(
                    self._campo_do_nome(por_interface.get(adaptador.interface)),
                    coluna,
                    linha,
                    1,
                    1,
                )
                coluna += 1
            grade.attach(
                self._celula_mono(_nome_do_adaptador(adaptador)), coluna, linha, 1, 1
            )
            texto, dica = _onde_esta_o_adaptador(adaptador, self._mapa)
            grade.attach(self._celula(texto, dica=dica), coluna + 1, linha, 1, 1)
        self._caixa_adaptadores.pack_start(grade, False, False, 0)

        if com_nome:
            self._caixa_adaptadores.pack_start(
                rotulo_de_apoio(_NOME_VALE_JA, largura_max=_LARGURA_DA_FRASE),
                False,
                False,
                0,
            )
            if any(d.hospeda_nintendo for d in self._dongles):
                self._caixa_adaptadores.pack_start(
                    rotulo_de_apoio(_NOTA_DO_PREFIXO, largura_max=_LARGURA_DA_FRASE),
                    False,
                    False,
                    0,
                )
        self._caixa_adaptadores.show_all()

    def _campo_do_nome(self, dongle: Dongle | None) -> Any:
        """O campo livre do nome de um adaptador — ou uma célula vazia.

        Vazia quando o BlueZ não respondeu por ESTE adaptador, mesmo tendo
        respondido pelos outros. Um campo que não sabe para onde escrever é
        pior que nenhum: ela digitaria e nada aconteceria.

        O texto do campo é `Dongle.nome`, que é o alias SEM a costura — o
        prefixo que segura o Pro nunca aparece aqui, e é isso que faz o nome na
        tela ser o dela.
        """
        from gi.repository import Gtk

        if dongle is None:
            return self._celula("")

        campo = Gtk.Entry()
        campo.set_text(dongle.nome)
        campo.set_placeholder_text(_(_NOME_EM_BRANCO))
        campo.set_width_chars(12)
        campo.set_max_width_chars(16)
        campo.set_hexpand(False)
        campo.set_tooltip_text(_(_DICA_DO_NOME))
        campo.connect("activate", self._ao_salvar_o_nome, dongle.endereco)
        # Sair do campo também salva: quem digita e clica noutro lugar espera
        # que o que escreveu tenha valido. `focus-out-event` devolve `False`
        # para que o GTK siga entregando o foco a quem o pediu.
        campo.connect("focus-out-event", self._ao_sair_do_nome, dongle.endereco)
        self._campos_de_nome[dongle.endereco] = campo
        return campo

    def _desenhar_radios(self, mesa: Mesa) -> None:
        """A tabela dos outros rádios — ou a frase de que não há nenhum."""
        if self._caixa_radios is None:
            return
        self._esvaziar(self._caixa_radios)
        if not mesa.radios:
            self._caixa_radios.pack_start(
                rotulo_de_apoio(
                    "Nenhum outro rádio espetado no computador.",
                    largura_max=_LARGURA_DA_FRASE,
                ),
                False,
                False,
                0,
            )
            self._caixa_radios.show_all()
            return

        avisos = _avisos_de_vizinhanca(mesa)
        em_vigor = self._mesa_em_vigor().get("radios")
        gravados: dict[str, Any] = em_vigor if isinstance(em_vigor, dict) else {}
        grade = self._grade(["Aparelho", "Onde", "O que é"])
        for linha, radio in enumerate(mesa.radios, start=1):
            chave = f"{radio.vid}:{radio.pid}"
            grade.attach(self._celula_mono(chave), 0, linha, 1, 1)
            aviso = avisos.get(radio.no)
            grade.attach(
                self._celula(
                    _onde_esta_o_radio(radio, aviso, self._mapa),
                    dica=None if aviso is None else aviso[1],
                    alerta=aviso is not None,
                ),
                1,
                linha,
                1,
                1,
            )
            declarado = gravados.get(chave)
            tipo = declarado.get("tipo") if isinstance(declarado, dict) else None
            # O espelho de leitura é preenchido AQUI, e não dentro do widget.
            # Enquanto ele morava no `_seletor_do_tipo`, o que a seção sabia
            # sobre a declaração dela dependia de QUAL widget tinha sido
            # desenhado — e a linha que o kernel já classificou não desenha
            # seletor nenhum. Medido em 22/08/2026: o tipo gravado sumia do
            # espelho na primeira linha que nascia preenchida.
            if tipo is not None:
                self.radios_declarados[chave] = str(tipo)
            grade.attach(
                self._celula_do_que_e(radio, chave, tipo),
                2,
                linha,
                1,
                1,
            )
        self._caixa_radios.pack_start(grade, False, False, 0)
        self._caixa_radios.show_all()

    def _celula_do_que_e(self, radio: RadioUsb, chave: str, gravado: Any) -> Any:
        """A coluna "O que é" — a resposta já pronta, ou o seletor.

        Os três degraus da precedência, na ordem em que são consultados:

        1. **ela respondeu** — mostra a palavra dela com o selo `(você disse)`.
           A correção vence o kernel, sempre: o kernel sabe a CLASSE do
           aparelho, ela sabe o aparelho;
        2. **o kernel leu** — mostra a palavra do kernel com o selo `(lido)`.
           É o que muda com esta leva: a linha nasce preenchida, e o gesto de
           responder some das linhas em que não havia pergunta;
        3. **ninguém sabe** — o seletor de sete botões, com o `▲` ao lado.

        Nos dois primeiros, "Corrigir" abre o seletor. Enquanto ele está aberto
        (`self._corrigindo`), a linha se comporta como o degrau 3 sem o `▲`:
        o aviso é sobre a AUSÊNCIA de resposta, e ali já há uma.
        """
        from gi.repository import Gtk

        if chave in self._corrigindo:
            return self._seletor_do_tipo(chave, gravado)

        if gravado is not None:
            palavra = _PALAVRA_DO_TIPO.get(str(gravado), str(gravado))
            return self._celula_respondida(
                palavra, _SELO_DECLARADO, _DICA_DECLARADO, chave
            )

        aparelho = self._censo.aparelho(radio.no)
        if aparelho is not None and aparelho.grau == GRAU_LIDO:
            return self._celula_respondida(
                aparelho.especie, _SELO_LIDO, _DICA_LIDO, chave
            )

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fileira.pack_start(self._seletor_do_tipo(chave, gravado), False, False, 0)
        aviso = Gtk.Label(label=_AVISO_NAO_SABE)
        aviso.set_xalign(0.0)
        aviso.set_tooltip_text(_(_DICA_NAO_SABE))
        with contextlib.suppress(Exception):
            aviso.get_style_context().add_class("dim-label")
        fileira.pack_start(aviso, False, False, 0)
        return fileira

    def _celula_respondida(
        self, palavra: str, selo: str, dica: str, chave: str
    ) -> Any:
        """Palavra, selo de procedência e o botão que reabre a pergunta.

        O selo não é enfeite: sem ele a tela afirma "Teclado" e não diz quem
        afirmou. Foi o que o medidor desta mesma seção já tinha aprendido — um
        número sem procedência é lido como medição.
        """
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        rotulo = Gtk.Label(label=_(palavra))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(rotulo, False, False, 0)

        marca = Gtk.Label(label=selo)
        marca.set_xalign(0.0)
        marca.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            marca.get_style_context().add_class("hefesto-valor-mono-peq")
            marca.get_style_context().add_class("dim-label")
        fileira.pack_start(marca, False, False, 0)

        botao = Gtk.Button(label=_(_BOTAO_CORRIGIR))
        botao.set_tooltip_text(_(dica))
        botao.connect("clicked", self._ao_corrigir, chave)
        fileira.pack_start(botao, False, False, 0)
        return fileira

    def _ao_corrigir(self, _botao: Any, chave: str) -> None:
        """Abre o seletor daquela linha. Não grava nada, não relê nada."""
        self._corrigindo.add(chave)
        self._desenhar_radios(self._mesa)

    def _seletor_do_tipo(self, chave_do_radio: str, gravado: Any) -> Any:
        """Os seis tipos mais "Não sei", em fileira única.

        POR QUE ESTE SELETOR EXISTE — e a frase que estava aqui antes estava
        ERRADA, medido em 22/08/2026. Ela dizia que *"um dongle de teclado e um
        de caixa de som são o mesmo `vid:pid` para o kernel"*, e o `vid:pid`
        nunca foi a fonte: o kernel classifica pela CLASSE DA INTERFACE, e
        `03/01/01` contra `03/01/02` separa teclado de mouse sem perguntar nada
        a ninguém (`integrations/censo_do_barramento`). A conclusão que saía
        dali — sete botões em TODA linha — fazia a tela perguntar o que a
        máquina já sabia.

        O que sobra para o seletor é o que o kernel de fato não responde: a
        classe `ff`, em que o fabricante declinou de classificar, e é dela que
        sai o Wi-Fi Realtek desta casa. Aí a resposta é a única coisa desta
        seção que só a pessoa tem, e é ela que deixa o exame dizer *"o engasgo
        pode ser a webcam ao lado do adaptador"* em vez de listar um endereço
        hexa e calar.

        O esquema (`RadioDeclarado.tipo`) existe desde CONFIG-03, no mesmo dia,
        e ficou SEM TELA até 22/08/2026 — a metade que faltava do mesmo
        defeito.

        HORIZONTAL, E O NÚMERO É MEDIDO. A primeira versão usava `wrap=True`,
        que é grade de três colunas FIXAS (`segmented_selector.py:32`) — sete
        botões viram TRÊS linhas, e com quatro rádios na mesa a seção cresceu
        384px de uma vez (1921 → 2305, medido na foto de 22/08). Em fileira
        única os sete ocupam ~595px; com "Aparelho" (~90) e "Onde" (~200) a
        tabela fica em ~885px, dentro dos 1066px de largura mínima da janela.
        A largura sobrava e a altura não — esta tabela tem três colunas num
        espaço de 1920px, e é a altura que custa numa aba que já rola.

        `set_hexpand(False)` porque o `SegmentedSelector` propaga a expansão
        horizontal para cima: sem isto a coluna come a largura da tabela
        inteira, que é o defeito que a seção "A janela" pagou em 22/08 (757px
        de vão). Curar dentro do widget quebraria a aba Início, que DEPENDE
        dessa expansão (`home_actions.py:2251`).
        """
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        seletor = SegmentedSelector()
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        seletor.set_items([(ident, _(nome)) for ident, nome in _TIPOS_DE_RADIO])
        seletor.set_hexpand(False)
        if gravado is not None:
            with contextlib.suppress(Exception):
                seletor.set_active_id(str(gravado))
        seletor.connect("changed", self._ao_declarar_o_radio, chave_do_radio)
        return seletor

    # -- desenho do medidor ------------------------------------------------

    def _desenhar_medidores(self) -> None:
        """Uma barra por adaptador — ou nenhuma, quando não há adaptador."""
        if self._caixa_medidores is None:
            return
        self._esvaziar(self._caixa_medidores)
        apelidos = _apelido_por_endereco(self._dongles)
        for nome, ocupacao in _medidores_da_mesa(
            self._mesa, self._ocupacoes(), _dongle_por_interface(self._dongles)
        ):
            self._caixa_medidores.pack_start(
                self._fileira_do_medidor(nome, ocupacao, apelidos),
                False,
                False,
                0,
            )
        self._caixa_medidores.show_all()

    def _ocupacoes(self) -> dict[str, Ocupacao]:
        """A conta, ou nada quando o sysfs não responde.

        Engole a exceção pelo mesmo motivo do `reexaminar`: uma varredura de
        `/sys` que falhe não pode apagar as duas tabelas que já foram
        desenhadas acima.
        """
        try:
            return ocupacao_por_adaptador(
                self._controles, com_ponte_de_mic=self._com_mic
            )
        except Exception:
            logger.warning("medidor_de_radio_falhou", exc_info=True)
            # Varredura que falhou é "não medi", nunca "medi zero" — o `{}`
            # sozinho voltaria a pintar "Folgada" em verde.
            self._daemon_respondeu = False
            return {}

    def _fileira_do_medidor(
        self, nome: str, ocupacao: Ocupacao, apelidos: dict[str, str] | None = None
    ) -> Any:
        """Rótulo, trilha de duas fatias, a palavra e o selo — nesta ordem.

        A ordem é a do desenho (`mockup/aba-configuracoes.html:365-372`) e ela
        conta uma frase: QUAL rádio, QUANTO dele, em UMA palavra, e DE ONDE
        veio o número. Trocar a ordem quebra a frase.
        """
        from gi.repository import Gtk
        from gi.repository.GLib import markup_escape_text

        from hefesto_dualsense4unix.app.widgets.sensor_widgets import MedidorDeRadio

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fileira.set_margin_top(4)

        rotulo = Gtk.Label(label=_(_rotulo_do_medidor(nome, apelidos)))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(_DICA_DO_MEDIDOR))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(rotulo, False, False, 0)

        medidor = MedidorDeRadio()
        medidor.set_ocupacao(ocupacao.fracao_input, ocupacao.fracao_audio)
        medidor.set_hexpand(True)
        medidor.set_valign(Gtk.Align.CENTER)
        # O trilho é a única coisa da fileira que pode crescer, e é ele que
        # come a largura sobrando. Sem o `hexpand` aqui e com um
        # `set_size_request` largo no widget, o mínimo da barra viraria o
        # mínimo da aba inteira — a janela abre com 1180px e não tem rolagem
        # horizontal.

        # Sem resposta do daemon a barra fica em zero — e só a palavra e o selo
        # separam esta tela da de um rádio de fato vazio.
        sabido = self._daemon_respondeu is True
        with contextlib.suppress(Exception):
            medidor.get_accessible().set_name(_texto_acessivel(ocupacao, sabido=sabido))
        fileira.pack_start(medidor, True, True, 0)

        palavra = Gtk.Label()
        # Duas cores, nunca três, e NUNCA vermelho (R3): rádio cheio se resolve
        # tirando um controle daquele adaptador, e o vermelho desta casa é para
        # o que destrói e não tem volta (`theme.css:13`).
        if sabido:
            dizer = ocupacao.rotulo
            cor = _VERDE if ocupacao.rotulo == PALAVRA_FOLGADA else _LARANJA
        else:
            dizer = _PAINEL_DESCONHECIDO
            cor = _LARANJA
        palavra.set_markup(
            f'<span foreground="{cor}">{markup_escape_text(_(dizer))}</span>'
        )
        palavra.set_xalign(0.0)
        with contextlib.suppress(Exception):
            palavra.get_style_context().add_class("hefesto-valor-mono-peq")
        fileira.pack_start(palavra, False, False, 0)

        selo = Gtk.Label(label=_selo_da_ocupacao(ocupacao, sabido=sabido))
        selo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            selo.get_style_context().add_class("hefesto-valor-mono-peq")
            selo.get_style_context().add_class("dim-label")
        fileira.pack_start(selo, False, False, 0)
        return fileira

    def _grade(self, cabecalhos: list[str]) -> Any:
        """Uma grade com a fileira de cabeçalhos já posta.

        Grade de rótulos e não `Gtk.TreeView`, e a razão é de portão: o
        `test_config_a_palavra_de_tela_da_aba_montada` anda a árvore de widgets
        e cobra maiúscula, jargão e acentuação de cada texto que encontra —
        e o cabeçalho de coluna de um `TreeView` não é widget da árvore, então
        nasceria fora do alcance dele. Tabela pequena e em somente leitura não
        precisa de modelo; precisa de estar sob o portão de redação.
        """
        from gi.repository import Gtk

        grade = Gtk.Grid()
        grade.set_column_spacing(18)
        grade.set_row_spacing(4)
        for coluna, texto in enumerate(cabecalhos):
            rotulo = Gtk.Label(label=_(texto))
            rotulo.set_xalign(0.0)
            with contextlib.suppress(Exception):
                rotulo.get_style_context().add_class("hefesto-rotulo-secao")
            grade.attach(rotulo, coluna, 0, 1, 1)
        return grade

    def _celula(self, texto: str, *, dica: str | None = None, alerta: bool = False) -> Any:
        """Uma célula de texto comum; em `@orange` quando é atenção."""
        from gi.repository import Gtk
        from gi.repository.GLib import markup_escape_text

        rotulo = Gtk.Label(label=texto)
        rotulo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        if alerta:
            rotulo.set_markup(
                f'<span foreground="{_LARANJA}">{markup_escape_text(texto)}</span>'
            )
        if dica is not None:
            rotulo.set_tooltip_text(_(dica))
        return rotulo

    def _celula_mono(self, texto: str) -> Any:
        """Uma célula de valor lido do barramento, em fonte monoespaçada."""
        from gi.repository import Gtk

        rotulo = Gtk.Label(label=texto)
        rotulo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-valor-mono-peq")
        return rotulo

    @staticmethod
    def _esvaziar(caixa: Any) -> None:
        """Tira e destrói os filhos — reexaminar redesenha do zero."""
        for filho in caixa.get_children():
            caixa.remove(filho)
            filho.destroy()

    # -- gestos ------------------------------------------------------------

    def _ao_declarar(self, seletor: Any, chave: str) -> None:
        """Acumula a escolha no rascunho da máquina. NÃO grava, NÃO manda IPC.

        `D-A4`, o mesmo contrato de `secao_controles` e `secao_orcamento`: o
        clique marca o rascunho e o efeito sai no "Aplicar" do rodapé. Chamar
        `machine.declare` daqui criaria um segundo dono do gesto de gravar, que
        é a classe de defeito que a `ABAS-01` curou.

        `"nao_sei"` vira `None` e não a string: o esquema
        (`MesaDeclarada.altura_da_antena`) só aceita os valores reais, e
        `extra="forbid"` mais `Literal` recusariam o DOCUMENTO INTEIRO — o
        sintoma na tela seria "não consegui gravar", não "valor inválido".
        `None` é a resposta que o esquema já tem para "não sei", e ela é
        preservada na fusão como qualquer outra.
        """
        escolha = self._valor_do_seletor(seletor)
        self.declarado[chave] = escolha
        self._acumular({chave: escolha})

    def _ao_declarar_o_radio(self, seletor: Any, chave_do_radio: str) -> None:
        """O mesmo gesto, para o `tipo` de um rádio vizinho.

        A chave é `vid:pid` em hexa minúsculo, e o esquema a valida por regex
        (`MesaDeclarada._chave_de_radio_e_vid_pid`). É de propósito que ela NÃO
        seja o nó do sysfs: o nó muda de nome quando o aparelho troca de porta,
        e a resposta "isto é um teclado" não muda com a porta.
        """
        escolha = self._valor_do_seletor(seletor)
        self.radios_declarados[chave_do_radio] = escolha
        self._acumular({"radios": {chave_do_radio: {"tipo": escolha}}})

    @staticmethod
    def _valor_do_seletor(seletor: Any) -> str | None:
        """O id ativo, com `"nao_sei"` traduzido para a ausência de opinião."""
        ativo = seletor.get_active_id()
        return None if ativo in (None, "nao_sei") else str(ativo)

    def _acumular(self, mesa: dict[str, Any]) -> None:
        """Funde o pedaço em `host._maquina_pendente`, sob a chave `mesa`.

        Fusão e não substituição pelo mesmo motivo de `gravar_maquina`: as cinco
        seções da aba escrevem no MESMO rascunho pelo mesmo gesto, e a última a
        clicar apagaria as outras quatro se cada uma trocasse o documento.
        """
        with contextlib.suppress(Exception):
            self._host._maquina_pendente = fundir_declaracao(
                getattr(self._host, "_maquina_pendente", None),
                {"mesa": mesa},
            )
        # A marca "há escolhas por aplicar" no rodapé (23/08/2026). Sem esta chamada
        # ela só acendia ao trocar de aba ou ao ir para a bandeja — quem declarava e
        # clicava direto no X via o diálogo de fechamento sem nunca ter visto o aviso.
        # `getattr` com guarda é o idioma da casa para fiação de aba: hospedeiro de
        # teste sem rodapé não pode derrubar a declaração.
        marcar = getattr(self._host, "_marcar_declaracao_por_aplicar", None)
        if marcar is not None:
            with contextlib.suppress(Exception):
                marcar()

    def _desenhar_o_mapa(self) -> None:
        """A linha-resumo do gabinete dela, mais o botão que abre o desenho.

        UMA linha de altura, e é o teto declarado da tarefa: a seção já pede
        2465 px numa janela de 1080, e uma grade de faces aqui dentro nasceria
        abaixo da dobra — que é construir a feature e escondê-la.
        """
        if self._caixa_do_mapa is None:
            return
        self._esvaziar(self._caixa_do_mapa)
        self._caixa_do_mapa.pack_start(
            _linha_do_mapa(self._mapa, self._censo, self._abrir_o_desenho),
            False,
            False,
            0,
        )
        self._caixa_do_mapa.show_all()

    def _desenhar_o_hub(self) -> None:
        """A linha do hub em comum — e o conselho, quando há para onde mandar.

        Some inteira quando não há hub em comum, quando há menos de dois
        adaptadores, ou quando a leitura de entradas não respondeu. Linha que só
        sabe dizer "não sei" ocupa a largura que esta janela não tem.
        """
        if self._caixa_do_hub is None:
            return
        from gi.repository import Gtk

        self._esvaziar(self._caixa_do_hub)
        fato, por_que, conselho = _frase_do_hub_em_comum(
            self._mesa, self._censo, self._entradas
        )
        if not fato:
            return
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.set_margin_top(6)
        for texto in (fato, por_que, conselho):
            if texto:
                caixa.pack_start(
                    rotulo_de_apoio(texto, largura_max=_LARGURA_DA_FRASE),
                    False,
                    False,
                    0,
                )
        self._caixa_do_hub.pack_start(caixa, False, False, 0)
        self._caixa_do_hub.show_all()

    def _desenhar_o_gabinete(self) -> None:
        """As contagens do gabinete, a pergunta, e o botão da calibração.

        O botão nasce SEMPRE — inclusive sem `gabinete.json`, que é o caso de
        quem nunca instalou desde 25/08/2026. Ele é a única porta da janela de
        calibração, e amarrá-lo ao censo esconderia a cerimônia de quem mais
        precisa dela.
        """
        if self._caixa_do_gabinete is None:
            return
        from gi.repository import Gtk

        self._esvaziar(self._caixa_do_gabinete)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.set_margin_top(6)
        for texto in _linhas_do_gabinete(self._gabinete):
            caixa.pack_start(
                rotulo_de_apoio(texto, largura_max=_LARGURA_DA_FRASE), False, False, 0
            )
        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        botao = Gtk.Button(label=_(_BOTAO_CALIBRAR))
        botao.set_tooltip_text(_(_DICA_CALIBRAR))
        botao.connect("clicked", self._abrir_a_calibracao)
        fileira.pack_start(botao, False, False, 0)
        caixa.pack_start(fileira, False, False, 0)
        self._caixa_do_gabinete.pack_start(caixa, False, False, 0)
        self._caixa_do_gabinete.show_all()

    def _abrir_a_calibracao(self, _botao: Any = None) -> None:
        """Abre a cerimônia de calibração — a janela que a leva 1 entregou.

        Ela recebe mapa, censo e entradas JÁ LIDOS: a seção acabou de varrer o
        `/sys` três vezes, e uma quarta varredura aqui mediria uma máquina
        levemente diferente da que está desenhada na tela.

        Grava a cada resposta, direto no disco, sem IPC — por isso o `ao_fechar`
        relê a mesa em vez de mexer no rascunho: o que ela ensinou já está
        gravado quando a janela fecha.
        """
        from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
            JanelaDeCalibrarEntradas,
        )

        janela = JanelaDeCalibrarEntradas(
            self._host, self._mapa, self._censo, self._entradas
        )
        with contextlib.suppress(Exception):
            janela.connect("destroy", lambda *_a: self.reexaminar())
        janela.show_all()

    def _abrir_o_desenho(self, _botao: Any = None) -> None:
        """Abre a janela do mapa 2D — e ela grava no rascunho, não no disco.

        Janela PRÓPRIA, e o número é que decide: a seção já pede 2465 px numa
        janela de 1080. O import é local pelo idioma da casa — a seção monta em
        ambiente sem GTK durante os testes puros.
        """
        from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (
            JanelaDoMapaDaMesa,
        )

        janela = JanelaDoMapaDaMesa(
            self._host, self._mapa, self._censo, ao_fechar=self.reexaminar
        )
        janela.show_all()

    def _mapa_em_vigor(self) -> MapaDaMesa:
        """O mapa do DISCO, com o rascunho que espera o "Aplicar" por cima.

        Mesma ordem de `_mesa_em_vigor`, e pelo mesmo motivo: o pendente é mais
        novo que o disco, e mostrar o antigo faria o desenho dela parecer
        perdido ao trocar de aba e voltar.
        """
        bruto: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            bruto = carregar_maquina().mapa.model_dump(mode="json")
        pendente = getattr(self._host, "_maquina_pendente", None)
        if isinstance(pendente, dict):
            mapa = pendente.get("mapa")
            if isinstance(mapa, dict):
                bruto = fundir_declaracao(bruto, mapa)
        try:
            return MapaDaMesa.model_validate(bruto)
        except Exception:
            # Rascunho torto não pode derrubar a seção: sem mapa a tela volta a
            # falar como falava antes desta leva, que é uma resposta.
            logger.debug("mapa_em_vigor_invalido", exc_info=True)
            return MapaDaMesa()

    def _mesa_em_vigor(self) -> dict[str, Any]:
        """O que está no DISCO, com o que ainda espera o "Aplicar" por cima.

        A ordem importa e é a mesma de `secao_controles._declarado_hoje`: o
        pendente é mais novo que o disco, e mostrar o valor antigo faria o
        clique dela parecer perdido ao trocar de aba e voltar.
        """
        gravado: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            gravado = carregar_maquina().mesa.model_dump(mode="json")
        pendente = getattr(self._host, "_maquina_pendente", None)
        if isinstance(pendente, dict):
            mesa = pendente.get("mesa")
            if isinstance(mesa, dict):
                gravado = fundir_declaracao(gravado, mesa)
        return gravado

    def _ao_clicar_reexaminar(self, _botao: Any) -> None:
        self.reexaminar()

    def _ao_sair_do_nome(self, campo: Any, _evento: Any, endereco: str) -> bool:
        """Sair do campo salva. Devolve `False` para não engolir o foco."""
        self._ao_salvar_o_nome(campo, endereco)
        return False

    def _ao_salvar_o_nome(self, campo: Any, endereco: str) -> None:
        """Escreve o nome no BlueZ — e só quando ele MUDOU.

        A comparação é contra `Dongle.nome`, que é o alias já limpo da costura.
        Sem ela, cada troca de aba reescreveria o alias dos três adaptadores
        com o valor que eles já têm — escrita à toa num barramento de sistema,
        e uma delas cairia bem em cima do prefixo que segura o Pro.

        Não relê para conferir, e é medido: a escrita do `Alias` é assíncrona,
        e ler logo depois devolve o valor ANTIGO
        (`integrations/apelido_do_dongle`). Uma conferência com espera dentro
        travaria a janela por um segundo a cada salvamento. Em vez disso a
        tabela guarda o que o BlueZ respondeu ao `set-property`, que é o que se
        pode afirmar.

        Roda na thread da tela de propósito: é UM `busctl` de escrita, no gesto
        dela, e o resultado tem de estar na mão antes de a linha ser redesenhada
        — ao contrário da leitura, que são treze e acontece sozinha.
        """
        alvo = next(
            (d for d in self._dongles if d.endereco == endereco),
            None,
        )
        if alvo is None:
            return
        novo = campo.get_text().strip()
        if novo == alvo.nome:
            return
        try:
            feito = renomear_o_dongle(endereco, novo, dongles=self._dongles)
        except Exception:
            logger.warning("apelido_do_dongle_falhou", exc_info=True)
            return
        if not feito.aplicado:
            with contextlib.suppress(Exception):
                campo.set_tooltip_text(_(feito.porque) if feito.porque else _(_DICA_DO_NOME))
            return
        # O espelho de memória substitui a releitura que não se pode fazer. Sem
        # ele, o próximo `focus-out` compararia contra o nome velho e mandaria
        # o mesmo alias de novo.
        self._dongles = tuple(
            Dongle(
                endereco=d.endereco,
                alias=feito.alias,
                nome_do_sistema=d.nome_do_sistema,
                hospeda_nintendo=d.hospeda_nintendo,
                ligado=d.ligado,
                objeto=d.objeto,
            )
            if d.endereco == endereco
            else d
            for d in self._dongles
        )
        with contextlib.suppress(Exception):
            campo.set_tooltip_text(_(_DICA_DO_NOME))
        self._desenhar_medidores()


# -- tradução do que o barramento respondeu ---------------------------------


def _nome_do_adaptador(adaptador: Adaptador) -> str:
    """O nome de tela — identidade física, NUNCA `hciN`.

    `hci0` e `hci1` invertem entre boots, e um nome que troca de dono é pior
    que nenhum: a pessoa mexe na porta errada. O sysfs também não entrega o
    endereço (medido: `/sys/class/bluetooth/hci0/` não tem `address`), então o
    que resta é o que basta — VID:PID mais a porta, na coluna ao lado. É a
    decisão M1.
    """
    if not adaptador.vid or not adaptador.pid:
        return "Adaptador embutido"
    return f"{adaptador.vid}:{adaptador.pid}"


#: A palavra da entrada do gabinete. "Entrada", nunca "porta" — é a decisão
#: `D-A-PALAVRA-ENTRADA`, e ela sai da frase dela: *"o número da entrada usb
#: salvaria muito como coluna"*. O identificador de código continua `porta`; o
#: que a tela mostra é isto.
#: PROVISÓRIO — decisão dela: a frase é nova e ainda não passou pelo olho dela.
_ENTRADA_DELA = "Entrada {numero}"

#: A dica da entrada declarada. Ela carrega a PROCEDÊNCIA, que é o padrão desta
#: casa: a tela afirma o número dela, e o hover diz de onde ele veio e como o
#: sistema chama o mesmo aparelho. Sem isto, quem procurar o aparelho num log
#: do sistema não acha o número que a tela mostrou.
#: PROVISÓRIO — decisão dela.
_PROCEDENCIA_DA_ENTRADA = (
    "Foi você quem desenhou este mapa: este aparelho está na entrada {numero}. "
    "O sistema o enumera como {caminho}."
)

#: A linha-resumo do mapa dentro de "Conexões", e o botão que abre o desenho.
#: UMA linha de altura, e é o teto: a seção já pede 2465 px numa janela de
#: 1080 (`CONFIGURAÇÕES-FECHA-01` §2.4), e qualquer grade de quadrados aqui
#: dentro nasceria abaixo da dobra — construir a feature e escondê-la.
#: PROVISÓRIO — decisão dela: texto novo, e o lugar da linha é escolha dela.
_RESUMO_DO_MAPA = "Mapa: {faces} faces, {entradas} entradas, {colocados} aparelhos colocados."

#: O que a linha diz para quem nunca desenhou. Ela é o estado mais comum lá
#: fora, e diz o preço de não desenhar em vez de cobrar o desenho.
#:
#: A SEGUNDA METADE É O JUÍZO QUE O PRODUTO DEIXA DE FAZER, e ela entrou em
#: 25/08/2026 junto com a decisão dela de tirar o `peer` do `/sys` de
#: `mapa_das_portas.irmas_de`. Sem o desenho, `irmas_de` devolve `{}`, o motor do
#: arranjo fica sem `Entrada.par`, e as três penalidades de vizinho rádio (-30 no
#: teclado, -45 no Bluetooth, -40 no mouse) nunca disparam. Calar sobre isso faria
#: a tela publicar juízo otimista silencioso — "aqui fica bem" onde ela não tem
#: como saber —, que é o defeito de forma que esta casa persegue. O "o que fazer"
#: não está na frase de propósito: ele é o botão ao lado, que diz "Mapear
#: Entradas".
#: PROVISÓRIO — decisão dela.
#:
#: A PRIMEIRA FRASE MUDOU EM 05/09/2026: dizia *"Você ainda não desenhou a sua
#: mesa"*, e a palavra saiu da interface por ordem dela. O verbo acompanhou o
#: botão ao lado — que é o "o que fazer" desta frase e passou a chamar-se
#: **Mapear Entradas** (`D-MAPEAR-ENTRADAS-E-NAO-PORTAS`, 28/08).
_SEM_MAPA = (
    "Você ainda não mapeou as suas entradas. Enquanto isso o Hefesto diz o caminho "
    "do sistema (3-1.1.4) em vez do número da sua entrada, e não sabe quais "
    "entradas ficam coladas no metal — então ele não avisa quando dois "
    "receptores sem fio estão encostados. Não é que esteja tudo bem: ele não "
    "sabe."
)

#: O botão que abre a janela do desenho.
#: PROVISÓRIO — decisão dela.
#:
#: O NOME NOVO É DELA E ESPERAVA DESDE 28/08/2026 —
#: `D-MAPEAR-ENTRADAS-E-NAO-PORTAS` (`docs/data/decisoes-dela.csv`), que decide
#: com todas as letras: *"Desenhar a minha mesa" vira "Mapear Entradas"*. A
#: decisão nomeava este arquivo e esta linha e nunca tinha sido cumprida; a
#: ordem de 05/09 sobre a palavra "mesa" só a alcançou. O par
#: (`_BOTAO_CALIBRAR` -> "Mapear Entrada a Entrada") NÃO entra aqui: não diz a
#: palavra, e trocá-lo é da frente daquela decisão.
_BOTAO_DESENHAR = "Mapear Entradas"

# -- o gabinete que o install já contou (26/08/2026) -------------------------
#
# O `install.sh` grava o `gabinete.json` em TODA instalação
# (`install_censo_do_gabinete_host()`, `:1305`, chamado em `:1878` e `:2559`) e
# até 26/08/2026 nenhuma linha de `app/` o abria. As três frases abaixo são o
# consumidor que faltava.
#
# A REGRA QUE ELAS CARREGAM: **quando as fontes divergem, a aba mostra a
# divergência; ela nunca escolhe.** A BIOS desta placa declara 5 conectores USB
# onde a traseira entrega 8 — gabarito de fabricante copiado sem ajustar —, e o
# censo já grava `divergem=true` com a pergunta pronta. Publicar só um dos dois
# números desenharia um gabinete que ninguém tem, e ela confiaria nele.

#: A contagem que veio da tabela SMBIOS tipo 8, lida com root pelo install.
#: PROVISÓRIO — decisão dela.
_GABINETE_FIRMWARE = "A BIOS desta placa conta {numero} entradas USB."

#: A contagem que o kernel dá de graça, sem root. A palavra "buraco" é a do
#: censo; na tela ela vira "entrada", que é a decisão `D-A-PALAVRA-ENTRADA`.
#: PROVISÓRIO — decisão dela.
_GABINETE_SISTEMA = "Contando pelo que o sistema enxerga, são {numero}."

#: O que ELA respondeu, quando respondeu. Vem do mesmo arquivo, com o selo
#: `declarado-por-ela`, e sobrevive a reinstalar (`preservar_o_que_ela_disse`).
#: PROVISÓRIO — decisão dela.
_GABINETE_DELA = "Você disse que a sua traseira tem {numero}."

#: O botão que abre a cerimônia de calibração — a janela que a leva 1 entregou
#: inteira e que até 26/08/2026 não tinha porta nenhuma.
#:
#: O NOME É DELA E ESPERAVA DESDE 28/08/2026 — a outra metade da
#: `D-MAPEAR-ENTRADAS-E-NAO-PORTAS`, cumprida em 05/09. Ela pediu "Mapear
#: Portas" e "Mapear Porta a Porta"; vista a colisão com a `D-A-PALAVRA-ENTRADA`
#: (que diz que esta aba fala **entrada**, nunca **porta**, para não colidir com
#: porta de rede), ela escolheu manter "entrada": *"Ensinar as minhas entradas"*
#: vira **Mapear Entrada a Entrada**. O par `_BOTAO_DESENHAR` já tinha sido
#: cumprido na ordem de 05/09 sobre a palavra "mesa"; este ficou porque não
#: dizia a palavra.
_BOTAO_CALIBRAR = "Mapear Entrada a Entrada"

#: A dica do botão. Diz o que a cerimônia faz e o que ela custa, porque a fase
#: em pé manda a pessoa para trás do gabinete e isso não pode ser surpresa.
#: PROVISÓRIO — decisão dela.
_DICA_CALIBRAR = (
    "Um toque por aparelho, sentado, e o Hefesto aprende em que entrada cada "
    "um está. As entradas vazias só o computador não alcança — essas você "
    "ensina de pé, se quiser, e pode parar em qualquer passo."
)

# -- o hub que está acima de TODOS os adaptadores (26/08/2026) ---------------
#
# A coluna "Onde está" escreve "Em hub" LINHA A LINHA, a partir do
# `adaptador.atras_de_hub`, e nunca compara as linhas entre si. Hub em comum é
# disputa de barramento, que é causa de engasgo — e o produto já sabia
# responder: `censo_do_barramento.hub_em_comum` existe desde 22/08/2026.
#
# **Comparar o pai NÃO responde.** Medido em 22/08: os três adaptadores desta
# casa têm dois pais diferentes (`3-3.1` e `3-3`) e um único hub em comum, o
# `3-3`. Quem compara pai diz que não estão juntos, e diz errado.

#: O FATO, e ele nasce sempre que há hub em comum. Nunca acusa um adaptador de
#: atrapalhar outro — é a contra-regra obrigatória de R3 da
#: `ORDEM-DE-SERVICO-01`, e três adaptadores no mesmo hub é o arranjo que o
#: próprio `GUIA-RADIO-DA-SALA.md` manda comprar.
#: PROVISÓRIO — decisão dela.
_HUB_EM_COMUM = (
    "Os {numero} adaptadores chegam ao computador por dentro do mesmo hub."
)

#: POR QUE O FATO IMPORTA — e ele fala do hub, nunca de um dos adaptadores.
#: PROVISÓRIO — decisão dela.
_HUB_POR_QUE = (
    "Tudo que passa por esse hub divide o mesmo caminho com o que mais estiver "
    "nele."
)

#: O CONSELHO, e ele só nasce quando há para onde mandar: buraco livre, que uma
#: pessoa alcança com a mão, numa controladora DIFERENTE. Sem destino a seção
#: fica no fato e cala sobre o que fazer, porque não há o que fazer — mandar
#: mudar de buraco dentro do mesmo hub não muda o caminho que ele divide.
#: PROVISÓRIO — decisão dela.
_HUB_CONSELHO_UMA = (
    "Há 1 entrada livre num caminho diferente do computador: levar um dos "
    "adaptadores para lá tira o hub do caminho dele."
)

#: O mesmo conselho no plural.
#: PROVISÓRIO — decisão dela.
_HUB_CONSELHO_VARIAS = (
    "Há {numero} entradas livres num caminho diferente do computador: levar um "
    "dos adaptadores para lá tira o hub do caminho dele."
)


def _linha_do_mapa(
    mapa: MapaDaMesa, censo: Censo, ao_clicar: Any
) -> Any:
    """A linha-resumo mais o botão, numa fileira — o widget que a seção ganha.

    Função de MÓDULO e não método porque é o que a régua de altura mede: o
    teste monta a seção duas vezes, uma com esta linha e outra com ela trocada
    por uma caixa vazia, e a diferença é exatamente o que a tarefa gastou.
    """
    from gi.repository import Gtk

    resumo = resumo_do_mapa(mapa, censo)
    fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    fileira.set_margin_top(6)
    texto = (
        _SEM_MAPA
        if resumo.vazio
        else _RESUMO_DO_MAPA.format(
            faces=resumo.faces,
            entradas=resumo.entradas,
            colocados=resumo.colocados,
        )
    )
    fileira.pack_start(
        rotulo_de_apoio(texto, largura_max=_LARGURA_DA_FRASE), False, False, 0
    )
    botao = Gtk.Button(label=_(_BOTAO_DESENHAR))
    botao.connect("clicked", ao_clicar)
    fileira.pack_start(botao, False, False, 0)
    return fileira


def _linhas_do_gabinete(gabinete: dict[str, Any]) -> tuple[str, ...]:
    """As contagens de entrada lado a lado, mais a pergunta — nunca uma escolha.

    **A CURA, e é a primeira mordida.** Com o censo desta bancada — BIOS a
    declarar 5 conectores USB e o barramento a contar 8 buracos — saem TRÊS
    frases: os dois números e a pergunta que o censo já traz pronta. Arrancada
    a regra (deixando o firmware vencer, ou o kernel vencer), a aba desenha um
    gabinete que ninguém tem e a pessoa procura na traseira buracos que o mapa
    não mostra. Mordida:
    ``test_a_aba_mostra_a_divergencia_em_vez_de_escolher``.

    Sem ``gabinete.json`` — primeira instalação, ou install de antes de 25/08 —
    a resposta é tupla vazia, e a seção fala exatamente como falava antes desta
    leva. Firmware é FONTE, nunca premissa.

    O desempacotamento do par ``{valor, de_onde_sei}`` NÃO acontece aqui: quem
    o faz é ``censo_do_gabinete.contagens_declaradas``, que é o dono do formato.
    Repetir a forma do JSON em código de tela seria a segunda verdade de sempre.
    """
    numeros = contagens_declaradas(gabinete)
    frases = {
        "firmware": _GABINETE_FIRMWARE,
        "kernel_buracos": _GABINETE_SISTEMA,
        "declarado_por_ela": _GABINETE_DELA,
    }
    linhas = [
        frases[fonte].format(numero=numero)
        for fonte, numero in numeros.items()
        if fonte in frases
    ]
    pergunta = pergunta_pendente(gabinete)
    if pergunta:
        linhas.append(pergunta)
    return tuple(linhas)


def _frase_do_hub_em_comum(
    mesa: Mesa, censo: Censo, entradas: Sequence[NoDeEntrada]
) -> tuple[str, str, str]:
    """`(fato, por quê, conselho)` do hub que está acima de TODOS os adaptadores.

    **A CURA, e é a segunda mordida.** A coluna "Onde está" escreve "Em hub"
    linha a linha e nunca compara as linhas entre si; quem compara é
    ``hub_em_comum``, e ela sobe a cadeia em vez de olhar o pai. Trocada por uma
    comparação de pai, os três adaptadores desta casa param de aparecer juntos —
    eles têm dois pais (``3-3.1`` e ``3-3``) e um só hub em comum.

    **O conselho é a metade opcional, e a contra-regra R3 é quem o segura.**
    Três adaptadores no mesmo hub é o arranjo que o próprio
    ``GUIA-RADIO-DA-SALA.md`` manda comprar: o fato sozinho não é queixa. O
    conselho só nasce quando há para onde mandar — buraco livre, alcançável com
    a mão, numa controladora DIFERENTE. E nenhuma das três frases acusa um
    adaptador de atrapalhar outro; o que elas contam é que o caminho até o
    computador passa por um hub. Mordida:
    ``test_o_hub_em_comum_so_vira_conselho_com_buraco_livre_em_outra_pci``.

    Menos de dois adaptadores não tem "em comum" nenhum, e a resposta é o
    silêncio das três.
    """
    nos = [adaptador.no for adaptador in mesa.adaptadores if adaptador.no]
    if len(nos) < 2:
        return "", "", ""
    hub = hub_em_comum(censo, nos)
    if not hub:
        return "", "", ""
    fato = _HUB_EM_COMUM.format(numero=len(nos))
    quantos = len(_livres_em_outra_controladora(censo, entradas, hub))
    if quantos == 0:
        return fato, _HUB_POR_QUE, ""
    if quantos == 1:
        return fato, _HUB_POR_QUE, _HUB_CONSELHO_UMA
    return fato, _HUB_POR_QUE, _HUB_CONSELHO_VARIAS.format(numero=quantos)


def _livres_em_outra_controladora(
    censo: Censo, entradas: Sequence[NoDeEntrada], hub: str
) -> tuple[Furo, ...]:
    """Os buracos livres que NÃO pendem da mesma controladora deste hub.

    **Não conta buraco nenhum por conta própria**: quem responde "quais buracos
    estão vazios e uma pessoa alcança" é ``portas_do_barramento.livres``, que é
    a dona declarada dessa régua (o C5 da ``ORDEM-DE-SERVICO-01``). Aqui só mora
    o filtro por controladora, e o filtro é a contra-regra em forma de função:
    mudar o adaptador para outro buraco da MESMA controladora não muda o caminho
    que ele divide.

    Sem ``controlador_pci`` legível nenhum buraco é oferecido — silêncio é
    melhor que um destino que não ajuda, e é a mesma escolha de
    ``ordens_da_mesa._livres_fora_da_controladora``, que faz esta conta para os
    cards do exame. **As duas convivem porque as posses são de frentes
    diferentes nesta leva**; unificá-las é conserto de quem tiver as duas.
    """
    aparelho = censo.aparelho(hub)
    controlador = aparelho.controlador_pci if aparelho is not None else ""
    if not controlador:
        return ()
    controlador_por_hub = {
        atual.nome_do_kernel: atual.controlador_pci for atual in censo.aparelhos
    }
    return tuple(
        furo
        for furo in livres(entradas)
        if controlador
        not in {controlador_por_hub.get(no.hub, "") for no in furo.entradas}
    )


def _onde_esta_o_adaptador(
    adaptador: Adaptador, mapa: MapaDaMesa | None = None
) -> tuple[str, str | None]:
    """`(texto, dica)` da coluna "Onde está".

    COM o mapa dela, a coluna diz o número que ela escreveu no gabinete —
    "Entrada 9" — e o caminho do sistema desce para a dica, que é onde a
    procedência mora nesta casa. SEM o mapa, o texto é exatamente o de hoje,
    sem uma vírgula de diferença: quem nunca desenhou a mesa não pode perder o
    pouco que a tela já sabia dizer.
    """
    if not adaptador.no:
        # Sem nó USB o adaptador não pendura em entrada nenhuma: é PCIe, UART
        # ou SDIO, ou seja, faz parte da máquina. Não há o que trocar de lugar.
        return "Dentro da máquina", None
    numero = None if mapa is None else porta_de(mapa, adaptador.caminho)
    if numero is not None:
        return _ENTRADA_DELA.format(numero=numero), _PROCEDENCIA_DA_ENTRADA.format(
            numero=numero, caminho=adaptador.caminho
        )
    partes = [
        f"Barramento {adaptador.busnum}, porta {adaptador.devpath}",
        _painel_em_portugues(adaptador.painel),
    ]
    if not adaptador.atras_de_hub:
        return " · ".join(partes), None
    partes.append("Em hub")
    # A dica do desenho dizia "...e se ele tem fonte própria". A segunda metade
    # saiu: `bMaxPower` NÃO distingue hub alimentado — medido, o hub USB 3.1
    # com fonte reporta 0mA e o USB 2.1 sem fonte reporta 100mA, o oposto do
    # palpite. Afirmar "com fonte" seria a tela inventando uma medição.
    # LEX-11 PARADA AQUI, E A PARADA É MEDIDA. Esta frase e o
    # `f"Barramento {busnum}, porta {devpath}"` acima são as duas últimas das
    # cinco que dizem "barramento" na tela. Trocá-las reprova
    # `test_a_porta_dela_chega_na_frase.py::test_sem_mapa_a_frase_e_a_de_hoje`
    # (`:141-151`), que prende as duas letra por letra — e aquele arquivo não
    # está na posse desta frente (R-A). Ver a entrega da LEVA-4-A.
    return " · ".join(partes), "Lido do barramento USB: o Hefesto reconhece o hub."


def _medidores_da_mesa(
    mesa: Mesa,
    ocupacoes: dict[str, Ocupacao],
    por_interface: dict[str, Dongle] | None = None,
) -> list[tuple[str, Ocupacao]]:
    """`[(nome do rádio, ocupação)]` — a lista de barras a desenhar.

    Duas fontes respondem "quais adaptadores existem", e elas não casam: a
    tabela acima vem do sysfs e conhece VID:PID e porta, mas **não conhece o
    endereço** (medido em 22/08: `/sys/class/bluetooth/hci0/` não publica
    `address`); o medidor vem do `HID_PHYS` dos controles e conhece só o
    endereço. Sem um lado que tenha os dois, casar linha com barra seria chute.

    A regra que sai daí tem uma frase: **quem manda é quem sabe.**

    * há controle no rádio -> uma barra por ENDEREÇO, que é o que o desenho
      pede (`Rádio em uso · AA:BB:CC:11:22:33`). Com dois adaptadores e
      controles só num deles, aparece uma barra — a do que está em uso, com
      nome verdadeiro;
    * não há controle nenhum no rádio -> uma barra em ZERO por adaptador da
      tabela, nomeada **pelo nome dela** quando o BlueZ respondeu, e pela
      identidade física quando não. É o caso de todos os controles no cabo, e é
      o que mais aparece: com três adaptadores iguais a versão anterior
      desenhava `2357:0604` três vezes — três barras com o mesmo rótulo, que é
      exatamente o problema que os nomes vieram resolver;
    * não há nem controle nem adaptador -> nenhuma barra. A linha "Nenhum
      adaptador Bluetooth encontrado" já disse tudo, e uma barra vazia embaixo
      dela só ocuparia altura.

    O que a regra NUNCA faz é somar a ocupação de um endereço numa linha da
    tabela por posição. Emprestar o adaptador do vizinho é o erro que a chave
    de ausência existe para impedir — e o nome, que vem do `hciN` da MESMA
    leitura, não muda isso: ele só troca o rótulo de uma barra que já era
    daquele adaptador.
    """
    if ocupacoes:
        return [(endereco, ocupacoes[endereco]) for endereco in sorted(ocupacoes)]
    nomes = por_interface or {}
    return [
        (
            (dongle.nome if (dongle := nomes.get(a.interface)) and dongle.nome else "")
            or _nome_do_adaptador(a),
            Ocupacao(),
        )
        for a in mesa.adaptadores
    ]


def _rotulo_do_medidor(nome: str, apelidos: dict[str, str] | None = None) -> str:
    """O rótulo da barra. Endereço ausente vira "Não sei", nunca `hciN`.

    `hci0` e `hci1` invertem entre boots — é a mesma decisão M1 que tirou o
    `hciN` da tabela acima, e vale em dobro aqui: uma barra que troca de dono
    entre boots faz a pessoa mexer na porta errada.

    Quando o BlueZ deu um nome àquele endereço, é o NOME que aparece. A junção
    é endereço contra endereço — o `HID_PHYS` do controle de um lado, o
    `Address` do adaptador do outro —, então não há chute nenhum aqui: ou o
    endereço bate, ou a barra continua se chamando pelo endereço.
    """
    if nome == SEM_ADAPTADOR:
        return f"Rádio em uso · {_PAINEL_DESCONHECIDO}"
    apelido = (apelidos or {}).get(nome.upper(), "")
    return f"Rádio em uso · {apelido or nome}"


def _dongle_por_interface(dongles: Sequence[Dongle]) -> dict[str, Dongle]:
    """`hciN -> Dongle`, refeito a cada leitura e NUNCA guardado.

    É a única junção desta seção que passa por `hciN`, e ela existe porque os
    dois lados só têm esse campo em comum: o sysfs conhece porta e `vid:pid` e
    **não publica o endereço** (medido em 22/08/2026 —
    `/sys/class/bluetooth/hci0/` não tem `address`); o BlueZ conhece o endereço
    e não conhece a porta.

    O índice inverte entre boots, e por isso o que se guarda dele é NADA: as
    duas leituras acontecem no mesmo gesto, e o que segue para a escrita é
    sempre o BD Address, que não inverte.
    """
    achados: dict[str, Dongle] = {}
    for dongle in dongles:
        interface = dongle.objeto.rsplit("/", 1)[-1]
        if interface.startswith("hci"):
            achados[interface] = dongle
    return achados


def _apelido_por_endereco(dongles: Sequence[Dongle]) -> dict[str, str]:
    """`ENDEREÇO -> nome dela`, só para quem tem nome. Maiúsculas dos dois lados."""
    return {d.endereco.upper(): d.nome for d in dongles if d.nome}


def _selo_da_ocupacao(ocupacao: Ocupacao, *, sabido: bool = True) -> str:
    """`831/1600 · derivado da especificação` — o selo mono, montado aqui.

    Montado em Python, e não declarado no Glade, por dois motivos: os dois
    números são calculados, e um rótulo estático começando por "derivado"
    reprovaria no `validar-palavra-de-tela.py` por primeira letra minúscula
    (`:174-186`). Aqui a primeira coisa é um dígito, e o portão de maiúscula
    pula o que não começa por letra.

    A frase depois do meio-ponto não é enfeite: as 1.600 fatias vêm da
    especificação do Bluetooth Classic e **nunca foram medidas nesta máquina**.
    Sem ela, a barra seria lida como medição.
    """
    if not sabido:
        return f"— · {_SEM_RESPOSTA_DO_DAEMON}"
    return (
        f"{round(ocupacao.slots_total)}/{ocupacao.slots_teto} "
        f"· {_SELO_DE_PROCEDENCIA}"
    )


def _texto_acessivel(ocupacao: Ocupacao, *, sabido: bool = True) -> str:
    """O que o leitor de tela lê na trilha — o `aria-label` do desenho.

    A barra é desenhada em Cairo: sem isto ela é um retângulo sem nome nenhum
    para quem não a enxerga, e a informação inteira do medidor ficaria só na
    cor.
    """
    if not sabido:
        return f"{_PAINEL_DESCONHECIDO} — {_SEM_RESPOSTA_DO_DAEMON}"
    return f"{round(ocupacao.slots_total)} de {ocupacao.slots_teto}"


def _onde_esta_o_radio(
    radio: RadioUsb,
    aviso: tuple[str, str] | None,
    mapa: MapaDaMesa | None = None,
) -> str:
    """O painel do rádio, mais o aviso de vizinhança quando há um.

    Com o mapa, o painel do kernel dá lugar ao número dela — que é a diferença
    entre "Direita" e "Entrada 7". Sem o mapa, o texto é o de hoje.
    """
    numero = None if mapa is None else porta_de(mapa, radio.caminho)
    onde = (
        _painel_em_portugues(radio.painel)
        if numero is None
        else _ENTRADA_DELA.format(numero=numero)
    )
    return onde if aviso is None else f"{onde} · {aviso[0]}"


def _painel_em_portugues(painel: str) -> str:
    """A palavra do kernel virando palavra de tela — ausência é "Não sei"."""
    return _PAINEL_EM_PORTUGUES.get(painel, _PAINEL_DESCONHECIDO)


def _avisos_de_vizinhanca(mesa: Mesa) -> dict[str, tuple[str, str]]:
    """`{nó do rádio: (sufixo, dica)}` — no máximo um aviso por rádio.

    Duas leituras diferentes saem do MESMO par de nós colados:

    * rádio colado em rádio — o aviso vai numa das duas linhas, não nas duas:
      são dois aparelhos e UM problema, e marcar os dois leria como dois;
    * rádio colado no adaptador — aqui o aviso vai sempre no RÁDIO, porque é
      ele que tem coluna de aviso e é ele que a pessoa vai mudar de porta.

    A dica do USB 3.0 só aparece quando o rádio É USB 3.0 (`speed >= 5000`).
    A frase do desenho afirma "USB 3.0 emite ruído de banda larga", e mostrá-la
    sobre um receptor USB 2.0 seria explicar o problema errado.
    """
    posicao_do_adaptador = {
        adaptador.no: numero
        for numero, adaptador in enumerate(mesa.adaptadores, start=1)
        if adaptador.no
    }
    radios = {radio.no: radio for radio in mesa.radios}
    avisos: dict[str, tuple[str, str]] = {}
    for primeiro, segundo in mesa.apertadas:
        numero = posicao_do_adaptador.get(primeiro) or posicao_do_adaptador.get(segundo)
        if numero is not None:
            alvo = segundo if primeiro in posicao_do_adaptador else primeiro
            radio = radios.get(alvo)
            if radio is None or alvo in avisos:
                continue
            avisos[alvo] = (
                f"vizinho do adaptador {numero}",
                _DICA_USB3_AO_LADO if radio.usb3 else _DICA_COLADOS,
            )
            continue
        if primeiro in radios and segundo in radios and segundo not in avisos:
            avisos[segundo] = ("colado no vizinho", _DICA_COLADOS)
    return avisos
