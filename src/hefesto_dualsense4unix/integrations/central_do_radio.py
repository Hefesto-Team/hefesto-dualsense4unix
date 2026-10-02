"""central_do_radio.py — mover, parear, equilibrar e conferir (MOVER-UM-POR-VEZ-01).

A palavra dela, 23/09/2026, e é a especificação: *"moveriamos por exemplo 1
controle por vez. Apagaria esse um controle, o user, aperta os botões do
controle pra sincronizar aquele controle e ele estaria no novo dispositivo. E
não apagar tudo."* <!-- noqa-acento: citação literal dela -->

O QUE O ESTUDO DE 23/09 DERRUBOU, e por isso o mover é este
===========================================================
* Copiar a chave do bond entre adaptadores NÃO move: a chave é presa aos dois
  endereços, e o controle guarda UM host. Mover é re-parear (R1).
* O host não liga o controle (``ReconnectMode="device"``): o adaptador só se
  escolhe no PAREAR (D8). Por isso o «Conectar» também passa por aqui.

LER → DECIDIR → APLICAR → CONFERIR
==================================
* **LER** pelo dono do BlueZ (``bluez_dbus``): em que adaptadores o aparelho
  tem objeto e bond, e quais adaptadores a mesa tem. Onde o controle ESTÁ vem
  do kernel — o ``HID_PHYS`` do hidraw (``radio_da_mesa.adaptador_por_uniq``).
* **DECIDIR**: o destino pedido, ou o da D8 (``plano_de_radio.ordem_dos_destinos``
  — uma regra só para «onde parear» e para o «Equilibrar»).
* **APLICAR**, TUDO dentro da trava comum (``diario_do_radio.trava_do_radio``,
  pela borda do dono): a conexão velha que o aparelho tenha no DESTINO sai
  primeiro (é dele — a R6 revista permite); o aparelho é DESLIGADO e a conexão
  dele em cada ORIGEM é esquecida — pelo ``RemoveDevice`` do dono e pelo verbo
  ``esquecer`` da ponte root (bond em disco, cache SDP e a LÁPIDE que impede o
  autorestore de ressuscitá-lo); só então a janela de pareamento abre SÓ no
  destino, com ``Powered`` ligado se preciso e ``Pairable`` ligado SÓ durante a
  janela; o ``Pair`` é atendido pelo agente próprio (R5), e sem ele pelo piso;
  depois o nome dela (o ``Alias``) vai junto, e ``Connect``.
* **CONFERIR** — o coração: até :data:`CONFERIR_S` lendo o ``HID_PHYS`` no
  adaptador pretendido e o movimento chegando. Só com os dois o estado vira
  :data:`CHEGOU`.

A ORDEM É DESLIGAR → ESQUECER A ORIGEM → PAREAR → CONFERIR, e é a R1 dela ao pé
da letra: *«Apagar a conexão no adaptador antigo, pedir PS + Create, e parear
só no destino.»* FATO SUBSTITUÍDO (A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01,
25/09/2026): de 23/09 a 25/09 a ordem foi parear → conferir → esquecer, por
decisão de quem coordena, para que um parear que falhasse não perdesse a
conexão velha. A lista dela de 25/09 mediu o preço (passos c1 e c2): com o
controle LIGADO na origem, o DualSense não entra em modo de parear — *«a
instrução "segure PS + Create" não faz sentido com ele ligado»* —, e o controle
que ainda tem a chave na origem volta para lá sozinho. O produto faz a parte
dele antes de pedir o gesto: desliga o controle e esquece a origem. Um parear
que falha deixa o controle sem casa, e o «Conectar» o traz de volta em qualquer
adaptador, com o mesmo PS + Create. <!-- noqa-acento: citação literal dela -->

OS TRÊS ESTADOS que a tela lê
=============================
:data:`ESPERANDO` (o gesto em curso, ou aplicado e ainda não conferido),
:data:`CHEGOU` e :data:`NAO_CHEGOU`. **Sem conferência o estado nunca é
«chegou»**: um aplicar que o BlueZ disse que deu, e que o ``HID_PHYS`` não
confirma, fica em «esperando» — e é vigiado, sem a trava, até
:data:`PRAZO_DO_PENDENTE_S`. Se o controle aparece no destino, vira «chegou»;
se o prazo acaba, «não chegou» — e a MEIA CHAVE que o ``Pair`` deixou no
destino sai antes do veredito (:meth:`CentralDoRadio._fechar_sem_chegar`), em
TODA saída sem chegada; sem a trava, ela fica devida e sai na primeira vez em
que a central a tem (:meth:`CentralDoRadio._pagar_as_meias_chaves`). O
prazo é UM, o da tela também, e o pedido seguinte não espera a vigia para
encontrá-lo vencido (:meth:`CentralDoRadio._vencer_os_prazos`).

O NOME DELA mora pelo endereço do controle, e não na chave
(:meth:`CentralDoRadio.cuidar_dos_nomes`, O-RADIO-CONECTA-ONDE-ELA-MANDA-02).

IDEMPOTÊNCIA É REQUISITO
========================
Rodar duas vezes não move nada duas vezes: o mover em curso devolve o mesmo
movimento, e o aparelho que já está no destino, sem bond em outro lugar, volta
«chegou» sem uma escrita no rádio. Nada aqui cria nó de som.

UM POR VEZ, TAMBÉM NO ARRASTAR (A-COSTURA-DA-ONDA-2-01)
======================================================
Com um movimento em curso — no gesto, ou aplicado e ainda «esperando» a
conferência, já sem a trava —, nenhum outro começa: o pedido volta
:data:`MOTIVO_OCUPADO`, e o botão treme. A conferida é feita duas vezes, antes
e DEPOIS de pegar a trava, porque o outro pode nascer enquanto este espera.

O DESTINO SEGUE A CAIXA QUE ELA ABRIU (O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01):
o pedido para o MESMO movimento, ainda antes de o aparelho aparecer na janela
(:data:`PASSOS_EM_QUE_O_DESTINO_MUDA`), não é outro movimento — é o chip dela
levando a busca junto. A janela fecha onde estava e recomeça no destino novo
(:meth:`CentralDoRadio._mudar_o_destino`), e um «Mover» segue «Mover» do
mesmo controle.

O «CONECTAR» (D8) é o mesmo caminho sem alvo: a janela abre no destino com
mais vaga de ponte (:func:`plano_de_radio.ordem_dos_destinos`), e NADA PAREIA
SEM O CLIQUE DELA (O-PAREAR-ESPERA-O-CLIQUE-01, D-3009-O-PAREAR-E-O-CLIQUE-DELA,
quem coordena, 30/09/2026, a validar por ela): a janela pareia o aparelho que
ela escolheu no «Parear» da linha dele (:meth:`CentralDoRadio._a_escolha_dela`),
e só um que a janela viu. Até 30/09 ela pareava o primeiro controle que
aparecesse, em meio segundo, antes de a tela o mostrar. E O CONTROLE QUE VOLTA PELO
PAREAMENTO ANTIGO também chega (a foto 2 da lista dela de 25/09: *«conectou com
algum mas não apareceu na lista»*): quem ela liga só com o PS reconecta no
adaptador que já tinha a chave dele, sem passar pela janela. O controle que se
conecta durante a janela e não estava conectado quando ela abriu é o dela; o
«Conectar» acaba «chegou» ONDE ele chegou (:data:`MOTIVO_PELO_PAREAMENTO_ANTIGO`),
e a tela o mostra chegando. <!-- noqa-acento: citação literal dela -->

O «EQUILIBRAR» (R12) é :func:`plano_de_radio.ordem_de_redistribuicao` — dona
desde 20/09. Esta central só a chama, e só quando nenhum movimento está
«esperando»: um de cada vez.

A FAXINA (A-SOBRA-DO-BOND-SAI-SOZINHA-01, 25/09/2026)
======================================================
O mover desta central esquece a origem no fim. Um mover feito à mão, ou antes
de ela existir, deixa a chave velha para trás: o controle fica com bond em dois
adaptadores, e na mesa dela o P2 ficou assim de 19/09 a 25/09, com o ``doctor``
acusando e ninguém arrumando. A pergunta dela, 25/09: *«A interface do app não
deveria corrigir isso automaticamente?»* Deveria, e a decisão é de quem
coordena: o controle guarda UM host, e quando o kernel o diz conectado num
adaptador (``HID_PHYS``) ele mesmo respondeu qual chave vale. A do outro
adaptador é sobra, e sai como sai a origem de um mover: ``RemoveDevice`` mais o
verbo ``esquecer`` da ponte, com lápide. :meth:`CentralDoRadio.esquecer_as_sobras`
faz UMA por volta, dentro da trava, e nunca com um movimento «esperando» (o mover
cuida da própria origem). Controle desligado, ou no cabo, não diz qual chave
vale, e aí nada sai: a sobra espera ele conectar pelo rádio.

O QUE ESTE MÓDULO NÃO FAZ
=========================
Não fala com a tela (nada de recado, R8), não move a webcam (não é do rádio)
e nunca apaga em lote. No «Conectar» pareia UM aparelho — o que ela escolheu
na lista —, e nenhum sem o clique dela.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    PONTE_INSTALADA,
    PedidoAPonte,
    mac_limpo,
    pedido_a_ponte,
)
from hefesto_dualsense4unix.integrations.gesto_de_pareamento import (
    ESTADO_JA_PAREADO,
    ESTADO_PAREOU,
    SEGUNDOS_DA_JANELA,
    SEGUNDOS_MAX,
    JanelaDeBusca,
    Resultado,
    e_controle,
)
from hefesto_dualsense4unix.integrations.gesto_de_reconexao import mascarar
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Como a central assina na trava e no diário comuns do rádio.
QUEM = "central"

# --- os três estados que a tela lê (chaves de máquina, não texto de tela) -----

ESPERANDO = "esperando"
CHEGOU = "chegou"
NAO_CHEGOU = "nao_chegou"  # (noqa-acento): chave de máquina
ESTADOS = (ESPERANDO, CHEGOU, NAO_CHEGOU)

#: A chave de um «Conectar» antes de o controle aparecer na janela: ainda não se
#: sabe QUEM vai chegar, só ONDE. Quando ele aparece, a chave vira o endereço.
CONECTANDO = ""

# --- os passos de um movimento, na ordem ------------------------------------

PASSO_PREPARANDO = "preparando"
#: O aparelho está sendo desligado e a conexão dele na origem, esquecida — ANTES
#: de pedir o gesto (R1 dela ao pé da letra; ver o cabeçalho).
PASSO_DESLIGANDO = "desligando"
#: A janela está aberta no destino e ela tem de segurar PS + Create.
PASSO_GESTO = "gesto"
PASSO_PAREANDO = "pareando"
PASSO_CONFERINDO = "conferindo"
PASSO_ESQUECENDO = "esquecendo"
PASSO_FIM = "fim"
#: Os passos ANTES de o aparelho aparecer na janela: nada foi pareado ainda, e o
#: destino muda no pedido dela (:meth:`CentralDoRadio._mudar_o_destino`).
PASSOS_EM_QUE_O_DESTINO_MUDA = frozenset({PASSO_PREPARANDO, PASSO_DESLIGANDO, PASSO_GESTO})

# --- por que um movimento acabou como acabou (chaves de máquina) ------------

#: O botão treme, sem recado, e nada mudou. Duas razões, e a tela não separa:
#: a trava do rádio não veio no prazo do gesto, ou OUTRO movimento está em curso
#: — um por vez vale também para o arrastar (A-COSTURA-DA-ONDA-2-01, a palavra
#: dela: *«moveriamos por exemplo 1 controle por vez»*). <!-- noqa-acento: citação literal dela -->
MOTIVO_OCUPADO = "ocupado"
#: O dono do BlueZ não conseguiu perguntar nada: não sei, e nada foi tocado.
MOTIVO_SEM_BLUEZ = "sem_bluez"
#: O aparelho não é do rádio (a webcam é USB) ou o endereço não tem forma.
MOTIVO_FORA_DO_RADIO = "fora_do_radio"
#: O destino não é um adaptador que a mesa tem agora.
MOTIVO_SEM_DESTINO = "sem_destino"
#: Já estava no destino, sem bond em outro adaptador: nada a fazer.
MOTIVO_JA_ESTAVA = "ja_estava"  # (noqa-acento): chave de máquina
#: A janela de pareamento não abriu no destino.
MOTIVO_SEM_JANELA = "sem_janela"
#: A janela fechou sem o aparelho aparecer — o PS + Create não veio.
MOTIVO_SEM_GESTO = "sem_gesto"
#: O ``Pair`` não deu.
MOTIVO_NAO_PAREOU = "nao_pareou"  # (noqa-acento): chave de máquina
#: Aplicado, e o ``HID_PHYS`` ainda não confirma — o estado segue «esperando».
MOTIVO_SEM_CONFIRMACAO = "sem_confirmacao"
#: Enquanto esperava, o controle reapareceu na ORIGEM.
MOTIVO_VOLTOU = "voltou"
#: O «esperando» passou do prazo sem confirmar.
MOTIVO_PRAZO = "prazo"
#: Um erro no meio do caminho: o movimento acaba aqui, com o que já estava
#: feito, e a central segue livre para o próximo pedido.
MOTIVO_FALHOU = "falhou"
#: O «Conectar» acabou «chegou» porque o controle voltou pelo pareamento antigo,
#: no adaptador que já tinha a chave dele — não pela janela.
MOTIVO_PELO_PAREAMENTO_ANTIGO = "pelo_pareamento_antigo"
#: Ela desligou o «Procurar» (``radio.busca.set``): a busca acabou a pedido, e
#: isso não é falha — a tela não faz «Não Conectou» dele
#: (O-CONECTAR-E-UM-INTERRUPTOR-01, D-3009-A-BUSCA-DESLIGADA-NAO-E-FALHA).
MOTIVO_DESLIGADA = "desligada"

# --- o diário -----------------------------------------------------------------

#: O ``o_que`` da linha que a central deixa quando um movimento CHEGA.
MOVEU_O_APARELHO = "moveu um aparelho"
#: O ``o_que`` da linha quando ele acaba sem chegar. Nada foi apagado.
O_APARELHO_NAO_CHEGOU = "o aparelho não chegou"
#: O ``o_que`` da linha da FAXINA: a chave que ficou num adaptador em que o
#: controle não mora saiu.
ESQUECEU_A_SOBRA = "esqueceu a sobra de um bond"
#: O ``o_que`` da linha quando a meia chave DEVIDA sai
#: (:meth:`CentralDoRadio._pagar_as_meias_chaves`): o «não chegou» dela saiu sem
#: a trava, e a chave, na primeira vez em que a central a teve.
ESQUECEU_A_MEIA_CHAVE = "esqueceu a meia chave de um pareamento que não chegou"
#: O ``o_que`` da linha quando o «Conectar» acaba pelo pareamento antigo.
VOLTOU_PELO_PAREAMENTO_ANTIGO = "o controle voltou pelo pareamento antigo"
#: O ``o_que`` da linha quando a limpeza achou uma sobra e NÃO a tirou: a ponte
#: não gravou a lápide, e sem ela nada sai (o autorestore a devolveria).
NAO_LIMPOU_SEM_LAPIDE = "não limpou: sem lápide"
#: O ``o_que`` da linha quando a central grava a lápide de um pareamento que
#: saiu do BlueZ por fora do Hefesto.
ENTERROU_O_QUE_SAIU_POR_FORA = "gravou a lápide de um pareamento tirado por fora"

# --- o que é controle, e qual o daemon mede -----------------------------------

#: O ``Icon`` que o BlueZ dá ao joystick e ao gamepad — da classe no rádio
#: clássico, da ``Appearance`` no de baixo consumo. O teclado é
#: ``input-keyboard``, o mouse ``input-mouse``: nenhum dos dois é controle.
ICONE_DE_CONTROLE = "input-gaming"

#: O ``Modalias`` do controle cujo movimento o daemon lê: o DualSense (Sony
#: ``054C``, ``0CE6``) e o Edge (``0DF2``).
_MODALIAS_QUE_O_DAEMON_MEDE = re.compile(r"v054Cp(0CE6|0DF2)", re.IGNORECASE)

# --- os prazos ----------------------------------------------------------------

#: Quanto um gesto de TELA espera a trava do rádio — decisão de quem coordena,
#: 23/09: no máximo 5 s, não os 30 do ``PRAZO_DA_TRAVA_S``. Estourou, o botão
#: treme (o ``recusar()`` do mockup), sem recado.
PRAZO_DA_TRAVA_DO_GESTO_S = 5.0

#: Quanto a CONFERÊNCIA lê o ``HID_PHYS`` e o movimento antes de desistir de
#: dizer «chegou» nesta volta. É o número da sprint.
CONFERIR_S = 10.0

#: De quanto em quanto tempo a conferência e a espera do gesto perguntam de novo.
PASSO_S = 0.5

#: Quanto um movimento fica «esperando», contado do COMEÇO dele, antes de virar
#: «não chegou». É também quanto a tela segura o «Segure PS + Create»
#: (``a08_conexoes.ESPERA_NA_TELA_S``): UM PRAZO, UM DONO, e o dono é este — o
#: nome é público e estável, e a tela passa a lê-lo daqui.
#:
#: FATO SUBSTITUÍDO (O-RADIO-CONECTA-ONDE-ELA-MANDA-02, 26/09/2026): eram 120 s,
#: «dois minutos cobrem ela apertar PS de novo com calma». A tela soltava o
#: «esperando» aos 60 s e a central recusava com «ocupado» até os 120: no
#: controle branco, «Tentar de Novo» e «Conectar» voltavam acesos e tremiam por
#: um minuto inteiro. Os 60 s são MEDIDOS no diário dela de 26/09: a janela da
#: busca (30 s) + o ``Pair`` mais lento da madrugada (o branco, 11 s) + a
#: conferência (10 s) somam 51 s.
PRAZO_DO_PENDENTE_S = 60.0

#: Quanto a central espera o objeto velho sumir da foto do dono depois de um
#: ``RemoveDevice`` — o sinal ``InterfacesRemoved`` chega pelo fio do barramento.
ESPERA_DO_SUMICO_S = 2.0

#: Quanto a central espera o controle desligar depois do ``Disconnect`` — o
#: ``HID_PHYS`` some quando o kernel tira o nó. Passou disso, segue: o
#: ``RemoveDevice`` da origem derruba a conexão do mesmo jeito.
ESPERA_DO_DESLIGAR_S = 3.0

#: A foto dos adaptadores para o «Equilibrar» vale este tanto: ele é perguntado a
#: cada ``state_full``, e pelo caminho de reserva (``busctl``) cada foto custa
#: vários subprocessos.
VALIDADE_DOS_ADAPTADORES_S = 2.0

#: O teto de fora do verbo ``esquecer`` da ponte: quem fica pendurado é ``sudo``.
ESPERA_DA_PONTE_S = 20.0

#: De quanto em quanto tempo a faxina olha. A sobra não tem pressa (ela só
#: atrapalha a próxima reconexão), e cada olhada custa uma foto do BlueZ e uma
#: varredura do ``/sys/class/hidraw``.
INTERVALO_DA_FAXINA_S = 30.0

#: A chave do fio da faxina em ``_fios`` — não tem forma de endereço, então não
#: esbarra na de um movimento.
_FIO_DA_FAXINA = "faxina"

#: De quanto em quanto tempo o fio da faxina cuida do NOME dela
#: (:meth:`CentralDoRadio.cuidar_dos_nomes`): é a demora entre ela renomear e o
#: nome ir ao ``maquina.json``, e entre o controle conectar e o nome voltar ao
#: objeto dele. Com o dono vivo cada volta é leitura da foto em memória; pelo
#: caminho de reserva (``busctl``), que custa subprocessos, a volta vai no passo
#: da faxina.
INTERVALO_DOS_NOMES_S = 2.0

#: Quanto um movimento ACABADO fica publicado, e quanto a tela lembra o «Não
#: Conectou» dele (ESQUECER-E-LIMPAR-AS-CONEXOES-01, cura 4: a constante morava
#: na tela, e quem corta a publicação é a central — a tela a lê daqui).
LEMBRA_O_NAO_CONECTOU_S = 600.0

#: Quanto a central espera, depois que um pareamento sai do BlueZ por fora (as
#: Configurações, o ``bluetoothctl``), antes de gravar a lápide dele (cura 5).
#: Em 15/08 os bonds comidos pelo crash do ``bluetoothd`` sumiram até ~48 s
#: antes do SIGABRT (``bt_bonds_autorestore.sh``, §1): uma lápide gravada nesse
#: meio enterraria o bond que o autorestore existe para devolver.
ESPERA_DA_LAPIDE_DE_FORA_S = 60.0

#: O teto de pares de UMA volta da limpeza: ela anda um par por chamada da
#: ponte (a R6 dela, nada em lote), e uma volta nunca é infinita.
PARES_POR_LIMPEZA = 32

#: Os três momentos em que a casa se limpa sozinha (D-3009-A-CASA-SE-LIMPA-SOZINHA,
#: pela resposta dela de 30/09, ~03h, na sprint):
#: *«limpar com frequencia a cada troca <!-- noqa-acento: citação literal dela -->
#: ou ao desligar os controles»*.
#: São o ``por_que`` da linha no diário.
DEPOIS_DE_UMA_TROCA = "depois de uma troca"
QUANDO_O_CONTROLE_DESLIGOU = "quando o controle desligou"
NA_VOLTA_DA_FAXINA = "na volta da faxina"


# ---------------------------------------------------------------------------
# O movimento — imutável, é uma foto do estado.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Movimento:
    """UM aparelho sendo movido para UM adaptador. Imutável: cada passo é outro."""

    #: O endereço do aparelho (minúsculo, com dois-pontos).
    aparelho: str
    #: O endereço do adaptador de destino ("" quando nem se decidiu).
    destino: str
    estado: str
    passo: str
    motivo: str = ""
    #: Os adaptadores em que ele tinha bond ANTES — os que saem no fim.
    origens: tuple[str, ...] = ()
    #: É controle (confere pelo ``HID_PHYS``) ou outro aparelho (pelo ``Connected``).
    #: UMA CHAVE, UM SENTIDO (A-COSTURA-DA-ONDA-2-01): no ``radio_central`` a chave
    #: ``controle`` é o ``uniq`` da ``proposta`` do «Equilibrar»; o booleano daqui
    #: se chama ``e_controle``, no campo e no publicado.
    e_controle: bool = True
    #: O ``Pair`` no destino deu — a conexão nova existe, confirmada ou não.
    pareou_no_destino: bool = False
    #: As conexões das ``origens`` já saíram (a R1: antes do gesto). Com isto o
    #: fim do mover não esquece de novo — uma segunda lápide seria outro verbo
    #: root por nada.
    origens_esquecidas: bool = False
    #: A *class of device* e o ``Modalias`` do aparelho, LIDOS ANTES de a
    #: origem ser esquecida: depois dela o BlueZ não tem mais objeto dele até a
    #: janela o achar, e a tela precisa saber O QUE está esperando — um teclado
    #: não se pareia com PS + Create (a lista dela de 25/09, passo c3).
    classe: int | None = None
    modalias: str = ""
    #: O ``Icon`` que o BlueZ deriva (da classe, ou da ``Appearance`` no de baixo
    #: consumo), lido junto: é o único tipo de um aparelho LE, que não tem classe
    #: — o «BT5.0 Keyboard» da lista dela (passos b7 e c3).
    icone: str = ""
    #: O nome que ela deu ao aparelho (o ``Alias``), lido na origem: ele é do
    #: APARELHO, e vai junto para o objeto novo no destino. ``""`` = o nome de
    #: fábrica, que o BlueZ dá sozinho.
    nome: str = ""
    #: Relógio monotônico do começo — para o prazo do «esperando».
    comecou: float = 0.0
    #: Hora de parede do começo — para a tela e o diário.
    quando: float = field(default_factory=time.time)

    @property
    def em_curso(self) -> bool:
        return self.estado == ESPERANDO

    def publicar(self) -> dict[str, Any]:
        """O que viaja no ``state_full`` — só tipos de JSON."""
        return {
            "aparelho": self.aparelho,
            "destino": self.destino,
            "estado": self.estado,
            "passo": self.passo,
            "motivo": self.motivo,
            "origens": list(self.origens),
            "e_controle": self.e_controle,
            "classe": self.classe,
            "modalias": self.modalias,
            "icone": self.icone,
            "nome": self.nome,
            "quando": round(self.quando, 3),
        }


# ---------------------------------------------------------------------------
# As costuras — o que a régua troca por dublê.
# ---------------------------------------------------------------------------

#: ``uniq`` (12 hex) → endereço do adaptador em que o kernel diz que ele está
#: (``HID_PHYS``), ou ``""`` quando não está no rádio.
OndeEsta = Callable[[str], str]

#: ``uniq`` → pacotes/s do nó de movimento AGORA, ou ``None`` (não sei).
Movimentacao = Callable[[str], "float | None"]

#: ``(adaptador, aparelho)`` → ``(fez, motivo)``: o verbo ``esquecer`` da ponte.
EsquecerNaPonte = Callable[[str, str], "tuple[bool, str]"]


class GuardaDosNomes(Protocol):
    """Onde mora o nome que ela deu a cada controle, pelo ENDEREÇO dele.

    No produto é o ``maquina.json`` (:class:`NomesNaMaquina`); a régua troca
    por um dublê que não é mais frouxo que ele.
    """

    def ler(self) -> Mapping[str, str] | None:
        """``{endereço aa:bb:…: nome}``; ``None`` = não deu para ler (não é «não há»)."""
        ...

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        """Grava o nome (``None`` esquece). ``False`` = não gravou."""
        ...


class NomesNaMaquina:
    """O nome dela no ``maquina.json`` (``ControleDeclarado.nome``) — o dono é
    ``utils/maquina``. Relido só quando o arquivo muda: a volta dos nomes
    pergunta a cada :data:`INTERVALO_DOS_NOMES_S`."""

    def __init__(self) -> None:
        self._lido: tuple[tuple[int, int] | None, dict[str, str]] | None = None

    def ler(self) -> Mapping[str, str] | None:
        from hefesto_dualsense4unix.utils import maquina

        try:
            estado = maquina.caminho_da_maquina().stat()
            marca: tuple[int, int] | None = (estado.st_mtime_ns, estado.st_size)
        except FileNotFoundError:
            marca = None
        except OSError:
            return None
        if self._lido is not None and self._lido[0] == marca:
            return dict(self._lido[1])
        nomes: dict[str, str] = {}
        for chave, nome in maquina.nomes_dos_controles(maquina.carregar_maquina()).items():
            endereco = endereco_de(chave)
            if endereco is not None:
                nomes[endereco] = nome
        self._lido = (marca, nomes)
        return dict(nomes)

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        from hefesto_dualsense4unix.utils.maquina import gravar_o_nome_do_controle

        return gravar_o_nome_do_controle(aparelho, nome)


class Janela(Protocol):
    """O que a central usa de uma :class:`gesto_de_pareamento.JanelaDeBusca`."""

    @property
    def aberta(self) -> bool: ...

    def abrir_a_janela(self) -> str: ...

    def candidatos(self) -> tuple[Any, ...]: ...

    def parear(self, endereco: str) -> Resultado: ...

    def fechar(self) -> None: ...


#: ``(destino, segundos, dono)`` → a janela de busca no destino.
AbrirJanela = Callable[[str, int, bluez_dbus.LeitorDoBluez], Janela]


def _hex12(endereco: str) -> str:
    """``aa:bb:…`` → ``aabb…`` — a forma do ``uniq`` do estado do daemon."""
    return endereco.replace(":", "").lower()


def _entrada(dono: bluez_dbus.LeitorDoBluez, objeto: bluez_dbus.AparelhoDoBluez) -> int:
    """Quantas vezes o objeto ENTROU no BlueZ desde a foto — o dono vivo conta
    (:meth:`bluez_dbus.DonoVivo.entrada`); o caminho de reserva não conta (0)."""
    contar = getattr(dono, "entrada", None)
    return int(contar(objeto.caminho)) if callable(contar) else 0


def endereco_de(valor: object) -> str | None:
    """O endereço do aparelho, pelas duas formas que circulam: com ``:`` ou 12 hex.

    Estrita como ``conexao_zumbi.mac_limpo``: o endereço vira dado da ponte
    root, e o que não tem forma de endereço sai ``None``.
    """
    if not isinstance(valor, str):
        return None
    texto = valor.strip().lower()
    if len(texto) == 12 and all(c in "0123456789abcdef" for c in texto):
        texto = ":".join(texto[i : i + 2] for i in range(0, 12, 2))
    return mac_limpo(texto)


def _onde_esta_pelo_hid_phys(uniq: str) -> str:
    """O adaptador em que o kernel diz que o controle está — pelo dono do número."""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import adaptador_por_uniq

    return adaptador_por_uniq([uniq]).get(uniq, "")


def esquecer_pela_ponte(
    adaptador: str,
    aparelho: str,
    *,
    caminho: str = PONTE_INSTALADA,
    correr: Callable[[PedidoAPonte], tuple[int, str]] | None = None,
) -> tuple[bool, str]:
    """O verbo ``esquecer`` da ponte root: bond em disco, cache SDP e a lápide.

    Sob a suíte recusa sem rodar nada — ``sudo`` contra a ponte instalada é o
    rádio dela. Quem chama já segura a trava; a ponte NUNCA a pede. Os dois
    endereços vão pelo stdin (:func:`conexao_zumbi.pedido_a_ponte`): o sudo
    registra só ``esquecer``.
    """
    try:
        pedido = pedido_a_ponte("esquecer", adaptador, aparelho, caminho=caminho)
    except ValueError:
        return False, "o endereço não tem forma de endereço"
    if correr is None:
        if bluez_dbus.a_suite_esta_rodando():
            return False, "a suíte está no ar e esta é a ponte de verdade"
        correr = _correr_a_ponte
    codigo, erro = correr(pedido)
    if codigo == 0:
        return True, ""
    return False, erro or f"a ponte saiu com {codigo}"


def _correr_a_ponte(pedido: PedidoAPonte) -> tuple[int, str]:
    """Roda o pedido até o fim, com os dados pelo stdin — nunca o de quem chamou."""
    try:
        feito = subprocess.run(
            list(pedido.argv),
            input=pedido.entrada,
            capture_output=True,
            text=True,
            timeout=ESPERA_DA_PONTE_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as erro:
        return 1, f"a ponte não respondeu: {erro}"
    return feito.returncode, (feito.stderr or "").strip()


def _janela_de_busca(
    destino: str, segundos: int, dono: bluez_dbus.LeitorDoBluez
) -> Janela:
    """A janela no destino: a do dono vivo, ou a da ponte root quando ele não há.

    A da ponte é ``sudo`` contra a ponte INSTALADA — o rádio dela, com a regra
    do sudoers que dispensa senha. Sob a suíte ela recusa sem rodar nada, como
    :func:`esquecer_pela_ponte`: o dono de mentira que não atende o próprio
    pareamento cairia nela.
    """
    if not dono.atende_o_proprio_pareamento and bluez_dbus.a_suite_esta_rodando():
        return JanelaDeBusca(
            destino, segundos, abrir=_recusar_a_ponte_sob_a_suite, correr=_nao_correr_sob_a_suite
        )
    return JanelaDeBusca(destino, segundos, dono=dono)


def _recusar_a_ponte_sob_a_suite(_pedido: PedidoAPonte) -> subprocess.Popen[str]:
    raise OSError("a suíte está no ar e esta é a ponte de verdade")


def _nao_correr_sob_a_suite(_pedido: PedidoAPonte) -> tuple[int, str]:
    return 1, "a suíte está no ar e esta é a ponte de verdade"


def _o_bluez_diz_controle(objetos: Iterable[bluez_dbus.AparelhoDoBluez]) -> bool | None:
    """A CLASSE decide quando algum objeto a tem; sem ela, o ``Icon`` que o
    BlueZ deriva; sem os dois, ``None`` (o BlueZ não diz). Nunca o nome."""
    vistos = tuple(objetos)
    for objeto in vistos:
        if objeto.classe is not None:
            return e_controle(objeto.classe)
    icones = {objeto.icone for objeto in vistos if objeto.icone}
    if icones:
        return ICONE_DE_CONTROLE in icones
    return None


# ---------------------------------------------------------------------------
# A foto que a central lê antes de decidir.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Foto:
    #: ``{endereço do adaptador: AdaptadorDoBluez}``.
    adaptadores: Mapping[str, bluez_dbus.AdaptadorDoBluez]
    #: ``{endereço do adaptador: o objeto DESTE aparelho naquele adaptador}``.
    do_aparelho: Mapping[str, bluez_dbus.AparelhoDoBluez]


def _ler(dono: bluez_dbus.LeitorDoBluez, aparelho: str) -> _Foto | None:
    """A mesa pelo dono. ``None`` = não deu para perguntar — nunca «não há»."""
    adaptadores = dono.adaptadores()
    if adaptadores is None:
        return None
    aparelhos = dono.aparelhos()
    if aparelhos is None:
        return None
    por_caminho = {a.caminho: a for a in adaptadores}
    do_aparelho = {
        por_caminho[a.adaptador].endereco: a
        for a in aparelhos
        if a.endereco == aparelho and a.adaptador in por_caminho
    }
    return _Foto({a.endereco: a for a in adaptadores}, do_aparelho)


def _controles_pelo_endereco(
    aparelhos: Iterable[bluez_dbus.AparelhoDoBluez],
) -> dict[str, list[bluez_dbus.AparelhoDoBluez]]:
    """Os objetos de cada CONTROLE, pelo endereço — um por adaptador que o conhece."""
    grupos: dict[str, list[bluez_dbus.AparelhoDoBluez]] = {}
    for objeto in aparelhos:
        grupos.setdefault(objeto.endereco, []).append(objeto)
    return {e: objs for e, objs in sorted(grupos.items()) if _o_bluez_diz_controle(objs)}


def _o_nome_que_vale(
    objetos: Sequence[bluez_dbus.AparelhoDoBluez],
    dados: Mapping[str, str],
    vistos_antes: Mapping[str, str],
    guardado: str,
) -> tuple[str, bool]:
    """``(o nome que vale depois desta volta, ela apagou?)`` — ver
    :meth:`CentralDoRadio.cuidar_dos_nomes`.

    ``dados`` é o nome dela em cada objeto (``""`` = o de fábrica);
    ``vistos_antes``, o ``Alias`` de cada objeto CONHECIDO na volta anterior.
    Só a mudança num objeto conhecido é gesto dela: o objeto que aparece (uma
    chave nova, o adaptador que volta à porta com o nome de antes) não fala
    por ela, e diante de um nome guardado ele RECEBE — não dá.

    «Ela apagou» só vale no objeto que AINDA TEM A CHAVE (conferência da
    O-RADIO-CONECTA-ONDE-ELA-MANDA-02, 26/09/2026): o X da TELA tira a chave
    por fora da central, e o objeto SEM chave que o BlueZ cria no mesmo caminho
    antes da volta seguinte (o controle que bate na porta de novo, a busca de
    outro programa, o «Conectar» que não pareou) nasce de fábrica — e era lido
    como ela apagando, o que tirava o nome dela do disco e de todo adaptador.
    """
    conhecidos = [o for o in objetos if o.caminho in vistos_antes]
    renomeados = [o for o in conhecidos
                  if dados[o.caminho] and vistos_antes[o.caminho] != _alias_de(o)]
    if renomeados:
        renomeados.sort(key=lambda o: o.conectado is not True)
        return dados[renomeados[0].caminho], False
    if guardado and any(vistos_antes[o.caminho] == guardado and not dados[o.caminho]
                        and o.pareado is True for o in conhecidos):
        return "", True
    if not guardado and not conhecidos:
        com_nome = sorted((o for o in objetos if dados[o.caminho]),
                          key=lambda o: o.conectado is not True)
        if com_nome:
            return dados[com_nome[0].caminho], False
    return guardado, False


def _alias_de(objeto: bluez_dbus.AparelhoDoBluez) -> str:
    return str(objeto.nome or "").strip()


# ---------------------------------------------------------------------------
# A central.
# ---------------------------------------------------------------------------


class CentralDoRadio:
    """O motor do mover, do parear e do «Equilibrar». Um por processo (o daemon).

    Tudo que escreve no rádio passa pelo dono do BlueZ e pela trava comum. As
    costuras (``dono``, ``onde_esta``, ``movimento``, ``esquecer_na_ponte``,
    ``abrir_janela``, o relógio) existem para a régua trocar o mundo por um
    dublê que não é mais frouxo que ele.
    """

    def __init__(
        self,
        *,
        dono: bluez_dbus.LeitorDoBluez | None = None,
        onde_esta: OndeEsta | None = None,
        movimento: Movimentacao | None = None,
        esquecer_na_ponte: EsquecerNaPonte | None = None,
        abrir_janela: AbrirJanela | None = None,
        nomes: GuardaDosNomes | None = None,
        sysfs: Mapping[str, Any] | None = None,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
        segundos_da_janela: int = SEGUNDOS_DA_JANELA,
        segundos_da_busca: int = SEGUNDOS_MAX,
        conferir_s: float = CONFERIR_S,
        prazo_do_pendente_s: float = PRAZO_DO_PENDENTE_S,
        prazo_da_trava_s: float = PRAZO_DA_TRAVA_DO_GESTO_S,
    ) -> None:
        self._dono_fixo = dono
        self._onde_esta = onde_esta or _onde_esta_pelo_hid_phys
        self._movimento = movimento
        self._esquecer_na_ponte = esquecer_na_ponte or esquecer_pela_ponte
        self._abrir_janela = abrir_janela or _janela_de_busca
        self._nomes: GuardaDosNomes = nomes if nomes is not None else NomesNaMaquina()
        #: ``{caminho do objeto: o Alias dele}`` na volta anterior dos nomes — é
        #: por ela que :meth:`cuidar_dos_nomes` separa «ela renomeou» (o
        #: ``Alias`` mudou) e «ela apagou o nome» (o MESMO objeto voltou ao de
        #: fábrica) de «o objeto é novo» (nasceu de fábrica, e o nome volta).
        self._alias_vistos: dict[str, str] = {}
        #: Sobe cada vez que a central tira ou recria um objeto
        #: (:meth:`_lembrar_o_alias`): a volta dos nomes que o atravessou não
        #: guarda o que viu, e a lembrança da central fica.
        self._geracao_dos_nomes = 0
        self._sysfs = dict(sysfs or {})
        self._relogio = relogio
        self._dormir = dormir
        self._segundos = int(segundos_da_janela)
        #: O TETO DA BUSCA do «Procurar» (D-3009-O-TETO-DA-BUSCA, quem coordena,
        #: 30/09/2026, a validar por ela): a janela do movimento SEM aparelho
        #: fica até ela desligar ou até o teto da ponte (``SEGUNDOS_MAX``,
        #: 120 s); a do «Mover» segue com ``_segundos``.
        self._segundos_da_busca = int(segundos_da_busca)
        self._conferir_s = float(conferir_s)
        self._prazo_do_pendente_s = float(prazo_do_pendente_s)
        self._prazo_da_trava_s = float(prazo_da_trava_s)
        self._tranca = threading.Lock()
        self._movimentos: dict[str, Movimento] = {}
        #: O destino que ela pediu por último para o movimento em curso, e que o
        #: fio dele ainda não atendeu (:meth:`_mudar_o_destino`). Um, como o
        #: movimento; ``None`` = nenhum.
        self._destino_pedido: str | None = None
        #: O «Parear» dela na lista do «Conectar» (:meth:`_a_escolha_dela`): o
        #: endereço que a janela de agora pareia, e os endereços que ela já viu
        #: (os VISTOS) — a escolha só vale para um deles. Os dois são da janela:
        #: ela fechou, ou foi para outro adaptador, e eles zeram.
        self._escolha: str | None = None
        self._vistos_na_janela: frozenset[str] = frozenset()
        #: A BUSCA DO «PROCURAR», PUBLICADA (O-CONECTAR-E-UM-INTERRUPTOR-01):
        #: ``{"adaptador", "desde", "ate"}`` enquanto a janela de um movimento
        #: SEM aparelho está aberta, e ``None`` fora dela. A janela dela, para o
        #: ``radio.busca.set`` a fechar de outro fio, e o pedido de desligar.
        self._busca: dict[str, Any] | None = None
        self._janela_da_busca: Janela | None = None
        self._desligar = False
        #: Quantas buscas abriram, e a última como abriu: o ``ligar_a_busca``
        #: responde pela que ELE abriu, mesmo que ela já tenha acabado (a
        #: escolha dela, ou o pareamento antigo, no meio da resposta).
        self._aberturas = 0
        self._ultima_busca: dict[str, Any] | None = None
        #: ``{(adaptador, aparelho)}``: as meias chaves que um «não chegou» não
        #: pôde tirar (a trava de outro motor, ou um erro no meio). Saem na
        #: primeira vez em que a central segura a trava (:meth:`_pagar_as_meias_chaves`).
        self._meias_chaves: set[tuple[str, str]] = set()
        self._fios: dict[str, threading.Thread] = {}
        #: A chave do último movimento que ESTE fio guardou — é por ela que um
        #: erro no meio acha o movimento a encerrar (o «Conectar» troca de chave).
        self._no_fio_atual = threading.local()
        self._parar = threading.Event()
        self._ultimos_controles: tuple[Mapping[str, Any], ...] = ()
        self._adaptadores_em_cache: tuple[float, tuple[bluez_dbus.AdaptadorDoBluez, ...]] | None = (
            None
        )
        self._refrescando = False
        #: O dono já foi aberto? Antes disso o ``state_full`` não o abre: o
        #: primeiro ``dono()`` paga o Gio de forma síncrona, e o tique não pode.
        self._ligada = dono is not None
        #: O último dono que :meth:`_dono` devolveu — é o que o tique usa, sem
        #: abrir nada (:meth:`_dono_sem_abrir`).
        self._dono_visto: bluez_dbus.LeitorDoBluez | None = dono
        #: A CASA SE LIMPA SOZINHA (ESQUECER-E-LIMPAR-AS-CONEXOES-01, cura 4). O
        #: fim de um movimento e o controle que desliga PEDEM uma volta da
        #: limpeza ao fio da faxina, que a roda assim que a trava sai; o
        #: ``por_que`` é o do primeiro pedido. Uma tranca só dela: o pedido chega
        #: do fio do barramento, no meio de qualquer escrita.
        self._tranca_da_limpeza = threading.Lock()
        self._limpeza_pedida = threading.Event()
        self._por_que_limpar = ""
        #: ONDE CADA CONTROLE COM A CHAVE DOBRADA ESTAVA NO AR, e as chaves dele
        #: naquele instante: ``{aparelho: (adaptador, {(adaptador, entrada)})}``.
        #: É a verdade que o ``HID_PHYS`` não dá mais depois que ele desliga
        #: (:meth:`_lembrar_onde_estao`, :meth:`_a_lembranca_que_vale`).
        self._lembrancas: dict[str, tuple[str, frozenset[tuple[str, int]]]] = {}
        #: Os pareamentos que saíram do BlueZ por fora, esperando a lápide (cura
        #: 5): ``[(adaptador, aparelho, hora no relógio, dono do org.bluez)]``.
        self._saidas_de_fora: list[tuple[str, str, float, str]] = []
        #: As sobras que a ponte não enterrou, já ditas no diário: uma linha por par.
        self._sem_lapide_dito: set[tuple[str, str]] = set()
        #: O dono cujos avisos esta central ouve (:meth:`_ouvir`).
        self._ouvindo: object | None = None
        if dono is not None:
            self._ouvir(dono)

    # -- ciclo ----------------------------------------------------------------

    def _dono(self) -> bluez_dbus.LeitorDoBluez:
        if self._dono_fixo is not None:
            return self._dono_fixo
        dono = bluez_dbus.dono()
        self._dono_visto = dono
        self._ouvir(dono)
        return dono

    def _ouvir(self, dono: bluez_dbus.LeitorDoBluez) -> None:
        """Assina os avisos do dono (o :class:`bluez_dbus.DonoVivo`): o controle
        que desligou e o pareamento que saiu. Só o dono do DAEMON tem quem ouça
        — a janela não sobe central —, e o caminho de reserva não avisa."""
        with self._tranca_da_limpeza:
            if dono is self._ouvindo:
                return
            self._ouvindo = dono
        ouvir = getattr(dono, "ouvir", None)
        if callable(ouvir):
            ouvir(self._ao_aviso_do_dono)

    def _ao_aviso_do_dono(self, aviso: str, dados: Mapping[str, Any]) -> None:
        """Chega no fio do barramento: só anota e pede — nada de D-Bus aqui."""
        if aviso == bluez_dbus.AVISO_DESLIGOU:
            self._pedir_a_limpeza(QUANDO_O_CONTROLE_DESLIGOU)
        elif aviso == bluez_dbus.AVISO_SAIU_PAREADO:
            adaptador = endereco_de(dados.get("adaptador"))
            aparelho = endereco_de(dados.get("aparelho"))
            # A remoção do Hefesto segura a trava comum do rádio (a janela, o
            # mover, a faxina): essa já tem a lápide da ponte.
            if dados.get("pela_trava") or adaptador is None or aparelho is None:
                return
            pendente = (adaptador, aparelho, self._relogio(), str(dados.get("dono") or ""))
            with self._tranca_da_limpeza:
                if not any(p[:2] == pendente[:2] for p in self._saidas_de_fora):
                    self._saidas_de_fora.append(pendente)

    def _pedir_a_limpeza(self, por_que: str) -> None:
        """Pede UMA volta da limpeza ao fio da faxina (:meth:`limpar`)."""
        with self._tranca_da_limpeza:
            if not self._por_que_limpar:
                self._por_que_limpar = por_que
        self._limpeza_pedida.set()

    def _dono_sem_abrir(self) -> bluez_dbus.LeitorDoBluez | None:
        """O último dono visto, se ainda pergunta — ``None`` sem abrir nada.

        É o do tique: sem dono vivo, ``bluez_dbus.dono()`` tenta o Gio de novo
        de forma síncrona (até ~5 s num barramento mudo), e o ``state_full``
        roda no laço do daemon.
        """
        visto = self._dono_visto
        return visto if visto is not None and visto.pode_perguntar() else None

    def ligar(self) -> bool:
        """Abre o dono do BlueZ — no arranque do daemon, fora de qualquer fio de tela.

        O primeiro ``dono()`` abre o Gio de forma síncrona (até ~5 s no pior
        caso): pagá-lo aqui é o que impede o primeiro gesto dela de pagá-lo.
        """
        dono = self._dono()
        vivo = dono.pode_perguntar()
        self._ligada = True
        logger.info("central_do_radio_ligada", vivo=vivo, pelo_dono=type(dono).__name__)
        return vivo

    def fechar(self, *, espera: float = 3.0) -> None:
        """Pede para os fios pararem e espera. Idempotente, nunca levanta."""
        self._parar.set()
        self._limpeza_pedida.set()  # acorda a faxina, que espera por ela
        with self._tranca:
            fios = list(self._fios.values())
        for fio in fios:
            if fio is not threading.current_thread():
                fio.join(timeout=espera)

    # -- o estado publicado ----------------------------------------------------

    def movimentos(self) -> tuple[Movimento, ...]:
        with self._tranca:
            return tuple(self._movimentos.values())

    def movimento_de(self, aparelho: str) -> Movimento | None:
        alvo = endereco_de(aparelho)
        if alvo is None:
            return None
        with self._tranca:
            return self._movimentos.get(alvo)

    @property
    def em_curso(self) -> bool:
        """Algum movimento está «esperando»? Então o «Equilibrar» não propõe nada."""
        return any(m.em_curso for m in self.movimentos())

    def _guardar(self, movimento: Movimento) -> Movimento:
        with self._tranca:
            self._movimentos[movimento.aparelho] = movimento
            self._mudou_o_movimento(movimento)
        self._no_fio_atual.chave = movimento.aparelho
        return movimento

    def _mudou_o_movimento(self, movimento: Movimento) -> None:
        """COM A ``_tranca`` NA MÃO. O movimento que começa tira a lembrança de
        onde aquele controle estava (é ele mudando de casa); o que acaba pede
        uma volta da limpeza (D-3009-A-CASA-SE-LIMPA-SOZINHA: depois de cada
        troca, e também do «não chegou»)."""
        if movimento.em_curso:
            self._lembrancas.pop(movimento.aparelho, None)
        else:
            self._pedir_a_limpeza(DEPOIS_DE_UMA_TROCA)

    def _comecar(self, movimento: Movimento) -> Movimento:
        """O «esperando» de um movimento novo — e nenhum destino pedido para o de antes.

        Um pedido que o movimento de antes não atendeu (ele achou o controle
        pelo pareamento antigo, ou acabou por outro caminho) não vale para este:
        é o chip de uma busca que já não existe.
        """
        with self._tranca:
            self._destino_pedido = None
            self._escolha, self._vistos_na_janela = None, frozenset()
            self._desligar = False
        return self._guardar(movimento)

    def _sair_do_gesto(self, movimento: Movimento, **mudancas: Any) -> Movimento | None:
        """O movimento deixa a espera do gesto — para o ``Pair`` ou para o «não
        chegou» — SE ela não pediu outro destino; com o pedido na fila, nada se
        guarda e volta ``None``: a janela fecha, e recomeça no destino novo.

        A pergunta e a troca vão de uma vez, sob a mesma tranca do
        :meth:`_mudar_o_destino`: ou o pedido chega antes e é atendido, ou chega
        depois e encontra o movimento fora do gesto (a recusa do um por vez). O
        pedido nunca é aceito para uma janela que já achou o controle.
        """
        feito = replace(movimento, **mudancas)
        with self._tranca:
            if self._destino_pedido is not None and not self._parar.is_set():
                return None
            if feito.aparelho != movimento.aparelho:
                self._movimentos.pop(movimento.aparelho, None)
            self._movimentos[feito.aparelho] = feito
            self._mudou_o_movimento(feito)
        self._no_fio_atual.chave = feito.aparelho
        return feito

    def _falhou(self, chave: str) -> Movimento:
        """Um erro no meio do mover: o movimento deste fio acaba «não chegou».

        Sem isto a promessa de nunca levantar caía, e o movimento ficava
        «esperando» para sempre — o «Equilibrar» mudo e o mesmo pedido
        devolvendo o movimento morto até o daemon reiniciar.

        Depois do ``Pair``, é um «não chegou» como os outros: a meia chave sai
        antes do veredito (:meth:`_fechar_sem_chegar`; quem chama já segura a
        trava). Se nem isso der, ela fica devida (:meth:`_acabou`).
        """
        logger.warning("central_mover_levantou", aparelho=mascarar(chave), exc_info=True)
        atual = self._pela_chave(getattr(self._no_fio_atual, "chave", chave))
        if atual is None or not atual.em_curso:
            return atual or Movimento(chave, "", NAO_CHEGOU, PASSO_FIM, MOTIVO_FALHOU)
        if atual.pareou_no_destino:
            try:
                return self._fechar_sem_chegar(atual, MOTIVO_FALHOU, self._dono())
            except Exception:
                logger.warning("central_meia_chave_levantou", aparelho=mascarar(atual.aparelho),
                               exc_info=True)
        return self._acabou(atual, NAO_CHEGOU, MOTIVO_FALHOU)

    def publicar(
        self,
        controles: Iterable[Mapping[str, Any]] | None = None,
        *,
        ar: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """``state_full["radio_central"]``: os movimentos e a proposta do «Equilibrar».

        Nunca levanta: a tela lê isto a cada volta, e uma falha aqui não pode
        apagar o resto do estado.
        """
        proposta: dict[str, Any] | None = None
        if controles is not None:
            self.conhecer(controles)
        if self._ligada:
            with contextlib.suppress(Exception):
                ordem = self.propor(ar=ar, esperar=False)
                proposta = ordem.publicar() if ordem is not None else None
        return {
            "movimentos": [m.publicar() for m in self._movimentos_publicados()],
            "em_curso": self.em_curso,
            "proposta": proposta,
            "busca": self._busca_publicada(),
        }

    def _busca_publicada(self) -> dict[str, Any] | None:
        """A busca do «Procurar» como a tela a lê, ou ``None``: com o chip dela
        pedindo outro adaptador, a busca JÁ é dele, como o destino do movimento
        (:meth:`_movimentos_publicados`)."""
        with self._tranca:
            if self._busca is None:
                return None
            busca = dict(self._busca)
            if self._destino_pedido is not None:
                busca["adaptador"] = self._destino_pedido
            return busca

    def ligar_a_busca(self, ligada: bool, destino: str | None = None) -> dict[str, Any]:
        """O «Procurar»: liga ou desliga a busca, com valor absoluto.

        O-CONECTAR-E-UM-INTERRUPTOR-01 (D-3009-O-CONECTAR-E-UM-INTERRUPTOR, quem
        coordena, 30/09/2026, a validar por ela). Até aqui a busca do rádio só
        nascia do clique que abre o painel do «+ Conectar» e não tinha verbo de
        parar: ficava os 30 s dela, e acabava «Não Conectou».

        * ``ligada``: o ``comecar_a_conectar`` de sempre — e, com a busca de pé
          noutro adaptador, a busca vai para o pedido (:meth:`_mudar_o_destino`).
          Volta quando a janela abriu, ou quando o movimento acabou sem abrir.
        * desligada: marca o pedido sob a tranca e FECHA a janela agora (a
          ``JanelaDeBusca.fechar`` é segura entre fios); o fio dela acaba o
          movimento em :data:`MOTIVO_DESLIGADA`, e o ``finally`` devolve o
          ``Pairable``. Volta quando a busca saiu do publicado.

        Pedir o estado que já vale responde ``ok`` sem tocar no rádio. Devolve
        ``{"status", "busca"}``, com a busca que ficou valendo. Bloqueia por
        até :data:`PRAZO_DA_TRAVA_DO_GESTO_S` e pouco: o tratador do daemon o
        roda num fio (``asyncio.to_thread``).
        """
        if not ligada:
            with self._tranca:
                janela = self._janela_da_busca
                conectando = self._movimentos.get(CONECTANDO)
                if janela is None and (conectando is None or not conectando.em_curso):
                    return {"status": "ok", "busca": None}
                self._desligar = True
                self._destino_pedido = None
            if janela is not None:
                with contextlib.suppress(Exception):
                    janela.fechar()
            busca = self._esperar_a_busca(lambda b: b is None)
            return {"status": "ok" if busca is None else "ocupado", "busca": busca}
        pedido = endereco_de(destino) if destino else None
        agora = self._busca_publicada()
        if agora is not None and (pedido is None or agora["adaptador"] == pedido):
            return {"status": "ok", "busca": agora}
        with self._tranca:
            antes = self._aberturas
        # Um «Mover» em curso não é levado pelo «Procurar», como seria pelo chip
        # (:meth:`_mudar_o_destino`): o interruptor só liga a busca SEM aparelho.
        # O que já venceu o prazo resolve antes (o «Tentar de Novo» aos 61 s).
        self._vencer_os_prazos()
        with self._tranca:
            mover = any(m.em_curso and m.aparelho != CONECTANDO
                        for m in self._movimentos.values())
        if mover:
            return {"status": MOTIVO_OCUPADO, "busca": agora}
        feito = self.comecar_a_conectar(destino)
        if feito.motivo:
            return {"status": feito.motivo, "busca": self._busca_publicada()}

        def no_pedido(busca: dict[str, Any] | None) -> bool:
            return busca is not None and (pedido is None or busca["adaptador"] == pedido)

        fim = time.monotonic() + self._prazo_da_trava_s + 1.0
        espera = threading.Event()
        while True:
            agora = self._busca_publicada()
            with self._tranca:
                aberta = dict(self._ultima_busca) if (
                    self._aberturas > antes and self._ultima_busca is not None) else None
            for busca in (agora, aberta):
                if no_pedido(busca):
                    return {"status": "ok", "busca": busca}
            conectando = self._pela_chave(CONECTANDO)
            if conectando is None or not conectando.em_curso or time.monotonic() >= fim:
                motivo = conectando.motivo if conectando is not None else ""
                return {"status": motivo or MOTIVO_SEM_JANELA, "busca": agora}
            espera.wait(0.01)

    def _esperar_a_busca(
        self, pronta: Callable[[dict[str, Any] | None], bool]
    ) -> dict[str, Any] | None:
        """Espera, no relógio de verdade, a busca publicada ficar como pedida —
        ou o «Conectar» acabar sem ela. Quem anda é o fio do movimento."""
        fim = time.monotonic() + self._prazo_da_trava_s + 1.0
        espera = threading.Event()
        while True:
            busca = self._busca_publicada()
            conectando = self._pela_chave(CONECTANDO)
            if pronta(busca) or conectando is None or not conectando.em_curso:
                return busca
            if time.monotonic() >= fim:
                return busca
            espera.wait(0.01)

    def _movimentos_publicados(self) -> tuple[Movimento, ...]:
        """Os movimentos como a tela os lê: o destino que ela pediu, e que o fio
        ainda não levou, JÁ é o destino (:meth:`_com_o_destino_pedido`).

        A conferência da O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01 (28/09/2026):
        entre o chip aceito e o fio atender (meio segundo no gesto; segundos no
        «Mover» que ainda desliga), o publicado dizia o destino de antes. A tela
        lê dali onde a busca está, e o chip desse adaptador só abre a caixa, sem
        pedir nada ao rádio: o clique de volta dela não desfazia o pedido, e a
        busca ia para o chip que ela deixou.
        """
        with self._tranca:
            pedido = self._destino_pedido
            return tuple(self._com_o_destino_pedido(m, pedido) for m in self._movimentos.values())

    @staticmethod
    def _com_o_destino_pedido(movimento: Movimento, pedido: str | None) -> Movimento:
        """O movimento no destino pedido — se ainda é um que muda de destino, e
        com o destino fora das ``origens``, como o fio o deixará."""
        if (pedido is None or not movimento.em_curso
                or movimento.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA):
            return movimento
        return replace(movimento, destino=pedido,
                       origens=tuple(o for o in movimento.origens if o != pedido))

    # -- DECIDIR: a D8 e o «Equilibrar» ----------------------------------------

    def _adaptadores(
        self, *, esperar: bool = True
    ) -> tuple[bluez_dbus.AdaptadorDoBluez, ...] | None:
        """Os adaptadores do dono, numa foto que vale :data:`VALIDADE_DOS_ADAPTADORES_S`.

        ``esperar=False`` é o caminho do ``state_full``: com o dono vivo a foto
        é memória e sai na hora; pelo caminho de reserva (``busctl``) ela custa
        subprocessos, e sem dono vivo abri-lo custa o Gio — nos dois casos ela
        se refaz num fio e o tique leva a última que havia.
        """
        agora = self._relogio()
        cache = self._adaptadores_em_cache
        if cache is not None and agora - cache[0] < VALIDADE_DOS_ADAPTADORES_S:
            return cache[1]
        if esperar:
            dono = self._dono()
        else:
            vivo = self._dono_sem_abrir()
            if vivo is None or not vivo.atende_o_proprio_pareamento:
                self._refrescar_os_adaptadores()
                return cache[1] if cache is not None else None
            dono = vivo
        lidos = dono.adaptadores()
        if lidos is not None:
            self._adaptadores_em_cache = (agora, tuple(lidos))
        return lidos

    def _refrescar_os_adaptadores(self) -> None:
        with self._tranca:
            if self._refrescando:
                return
            self._refrescando = True

        def rodar() -> None:
            try:
                lidos = self._dono().adaptadores()
                if lidos is not None:
                    self._adaptadores_em_cache = (self._relogio(), tuple(lidos))
            except Exception:
                logger.warning("central_adaptadores_nao_leu", exc_info=True)
            finally:
                with self._tranca:
                    self._refrescando = False

        threading.Thread(target=rodar, name="hefesto-central-adaptadores", daemon=True).start()

    def _planos(
        self, ar: Mapping[str, Any] | None = None, *, esperar: bool = True
    ) -> tuple[Any, frozenset[str] | None]:
        """Os planos por adaptador (o dono é ``plano_de_radio``) e quem varre."""
        from hefesto_dualsense4unix.integrations import plano_de_radio

        adaptadores = self._adaptadores(esperar=esperar)
        # A BUSCA DO PRÓPRIO HEFESTO NÃO É «OUTRO PROGRAMA PROCURANDO»
        # (O-CONECTAR-E-UM-INTERRUPTOR-01, cura 8): o ``Discovering`` do
        # adaptador do «Procurar» é ela, e ele não vai para o fim da D8 por isso.
        busca = self._busca_publicada()
        propria = busca["adaptador"] if busca is not None else None
        varrendo = (
            frozenset(a.endereco for a in adaptadores if a.varrendo and a.endereco != propria)
            if adaptadores is not None
            else None
        )
        planos = plano_de_radio.plano_por_adaptador(
            self._ultimos_controles,
            ar=ar,
            adaptadores=[a.endereco for a in adaptadores or ()],
            **self._sysfs,
        )
        return planos, varrendo

    def propor(
        self,
        controles: Iterable[Mapping[str, Any]] | None = None,
        *,
        ar: Mapping[str, Any] | None = None,
        esperar: bool = True,
    ) -> Any:
        """O «Equilibrar» (R12): UM movimento, ou ``None``.

        A régua é ``plano_de_radio.ordem_de_redistribuicao`` — esta central não
        escreve outra. Com um movimento «esperando», não propõe nada: o próximo
        só depois do «chegou». ``controles`` é o ``state["controllers"]`` (com
        ``adaptador`` e ``ponte_do_radio``); sem ele, vale o último que chegou.
        """
        from hefesto_dualsense4unix.integrations import plano_de_radio

        if controles is not None:
            self.conhecer(controles)
        if self.em_curso:
            return None
        planos, varrendo = self._planos(ar, esperar=esperar)
        return plano_de_radio.ordem_de_redistribuicao(planos, varrendo=varrendo)

    def conhecer(self, controles: Iterable[Mapping[str, Any]]) -> None:
        """Guarda o ``state["controllers"]`` de agora — é dele que a D8 e o
        «Equilibrar» leem as pontes e o adaptador de cada controle."""
        self._ultimos_controles = tuple(dict(c) for c in controles)

    def escolher_destino(
        self,
        aparelho: str | None = None,
        *,
        controles: Iterable[Mapping[str, Any]] | None = None,
    ) -> str | None:
        """A D8: onde parear. Mais vaga de ponte; no empate, menos controles; quem
        varre por último. O adaptador em que o aparelho já está não é destino."""
        from hefesto_dualsense4unix.integrations import plano_de_radio

        if controles is not None:
            self.conhecer(controles)
        planos, varrendo = self._planos()
        alvo = endereco_de(aparelho) if aparelho else None
        agora = self._onde_esta(_hex12(alvo)) if alvo else ""
        for plano in plano_de_radio.ordem_dos_destinos(planos, varrendo=varrendo, exceto=agora):
            return str(plano.endereco)
        return None

    # -- o mover ---------------------------------------------------------------

    def comecar_a_mover(self, aparelho: str, destino: str | None = None) -> Movimento:
        """O gesto da tela: começa o mover num fio e volta assim que a trava vier.

        Volta em no máximo :data:`PRAZO_DA_TRAVA_DO_GESTO_S` e um pouco: ou o
        movimento em curso («esperando»), ou a recusa (:data:`MOTIVO_OCUPADO`),
        que não fica guardada — o botão treme e nada mudou.

        UM POR VEZ (A-COSTURA-DA-ONDA-2-01): com QUALQUER movimento em curso — de
        outro aparelho, ou deste já depois do gesto — a recusa sai na hora, sem
        fio e sem esperar a trava. O mesmo pedido de novo devolve o mesmo
        movimento (a idempotência da MOVER); o deste aparelho para outro destino,
        ainda antes do gesto, leva a busca junto (:meth:`_mudar_o_destino`); e o
        de um aparelho que a busca do «Conectar» viu, no destino dela, é o
        «Parear» dela na lista (:meth:`_a_escolha_dela`).
        """
        alvo = endereco_de(aparelho)
        if alvo is None:
            return Movimento(str(aparelho), destino or "", NAO_CHEGOU, PASSO_FIM,
                             MOTIVO_FORA_DO_RADIO)
        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(alvo, destino)
        if mudou is not None:
            return mudou
        escolhido = self._a_escolha_dela(alvo, destino)
        if escolhido is not None:
            return escolhido
        repetido = self._o_mesmo_em_curso(alvo, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(alvo, destino)
        return self._no_fio(
            alvo, destino, lambda pronto: self.mover(alvo, destino, _ao_pegar_a_trava=pronto)
        )

    def comecar_a_conectar(self, destino: str | None = None) -> Movimento:
        """O «Conectar» da tela: o mesmo fio de :meth:`comecar_a_mover`, sem alvo.

        O movimento nasce com :data:`CONECTANDO` no lugar do endereço — ainda não
        se sabe QUEM vai chegar, só ONDE (a D8) — e ganha o endereço quando ela
        escolhe, na lista, um aparelho que a janela viu
        (:meth:`_a_escolha_dela`). Um por vez, como o :meth:`comecar_a_mover`.

        É também o pedido do CHIP do «Procurando» (a tela manda o mesmo
        ``radio.mover`` sem aparelho): com a busca de pé noutro adaptador, ela vai
        para o do chip (:meth:`_mudar_o_destino`) — seja um «Conectar», seja um
        «Mover» dela, que segue «Mover» do mesmo controle.
        """
        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(CONECTANDO, destino)
        if mudou is not None:
            return mudou
        repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(CONECTANDO, destino)
        return self._no_fio(
            CONECTANDO, destino, lambda pronto: self.conectar(destino, _ao_pegar_a_trava=pronto)
        )

    def _ocupada(self) -> bool:
        """Há movimento em curso, ou a central já fechou — então nada começa.

        Quem chama já descartou o MESMO pedido em curso (:meth:`_o_mesmo_em_curso`):
        o que sobra em curso é outro, e um por vez vale para ele também.
        Fechada (:meth:`fechar`, o desligamento do daemon), a central não abre
        janela nenhuma: o ``Pairable`` que ela ligasse não teria quem desligar.
        """
        return self._parar.is_set() or self.em_curso

    def _vencer_os_prazos(self) -> None:
        """O «esperando» que já passou do prazo resolve AGORA, antes do pedido.

        A tela solta o «esperando» no mesmo :data:`PRAZO_DO_PENDENTE_S`, contado
        do mesmo começo (o ``quando`` publicado) — e acende «Tentar de Novo» e
        «Conectar». A vigia só pergunta uma vez por segundo: sem esta volta, o
        clique que chega entre o prazo e a vigia seguinte encontrava a central
        «ocupada», e o botão aceso tremia (a zona morta da
        O-RADIO-CONECTA-ONDE-ELA-MANDA-02). Só o movimento vencido é vigiado
        aqui; o que ainda está no prazo segue com o fio dele.
        """
        agora = self._relogio()
        for movimento in self.movimentos():
            if (movimento.em_curso and movimento.passo == PASSO_CONFERINDO
                    and agora - movimento.comecou >= self._prazo_do_pendente_s):
                try:
                    self._vigiar_um(movimento)
                except Exception:
                    logger.warning("central_prazo_levantou",
                                   aparelho=mascarar(movimento.aparelho), exc_info=True)

    def _mudar_o_destino(self, chave: str, destino: str | None) -> Movimento | None:
        """O chip de outro adaptador com a busca de pé: a busca vai junto.

        A conferência da A-CAIXA-FICA-ONDE-ELA-ABRIU-01 (28/09/2026): o clique
        dela é o dono da caixa aberta, e o chip pede ao rádio que a busca o
        siga. Com o movimento em curso ainda ANTES do aparelho
        (:data:`PASSOS_EM_QUE_O_DESTINO_MUDA`), o destino muda: o fio dele fecha
        a janela onde estava e a abre no novo, com a janela e o prazo
        recomeçando (:meth:`_tomar_o_destino_pedido`). O último pedido vence, e pedir o destino
        de agora desfaz um pedido que ainda não andou.

        Só o MESMO movimento muda de destino: o pedido sem aparelho (o chip, o
        «Conectar») leva o que está em curso, e um «Mover» segue «Mover» do mesmo
        controle — nunca vira um «Conectar» anônimo por cima dele; o pedido com
        aparelho, só o movimento daquele aparelho. Outro aparelho, o movimento
        que já achou o seu, a central fechada ou um adaptador que não está na
        máquina: ``None``, e o pedido segue o caminho de sempre (o mesmo em curso,
        ou a recusa do um por vez).

        Devolve o movimento como ele fica, no destino pedido.
        """
        novo = endereco_de(destino) if destino else None
        if novo is None or self._parar.is_set():
            return None
        with self._tranca:
            atual = next((m for m in self._movimentos.values() if m.em_curso), None)
        if atual is None or atual.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA:
            return None
        if chave not in (CONECTANDO, atual.aparelho):
            return None
        adaptadores = self._adaptadores()
        if adaptadores is None or novo not in {a.endereco for a in adaptadores}:
            return None
        with self._tranca:
            # De novo, sob a tranca: é ela que o fio pega para sair do gesto
            # (:meth:`_sair_do_gesto`), e o pedido ou chega antes, ou não chega.
            agora = self._movimentos.get(atual.aparelho)
            if (agora is None or not agora.em_curso
                    or agora.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA):
                return None
            self._destino_pedido = None if novo == agora.destino else novo
        logger.info("central_o_destino_segue_a_caixa", aparelho=mascarar(agora.aparelho),
                    de=mascarar(agora.destino), para=mascarar(novo))
        return self._com_o_destino_pedido(agora, novo)

    def _a_escolha_dela(self, alvo: str, destino: str | None) -> Movimento | None:
        """O «Parear» dela na lista do «Conectar»: a escolha, e não outro movimento.

        O-PAREAR-ESPERA-O-CLIQUE-01 (D-3009-O-PAREAR-E-O-CLIQUE-DELA, quem
        coordena, 30/09/2026, a validar por ela). Com o «Conectar» em curso
        ainda antes do aparelho (:data:`PASSOS_EM_QUE_O_DESTINO_MUDA`), o pedido
        com aparelho, NO DESTINO DA BUSCA e de um endereço que a janela de agora
        já viu, é ela escolhendo quem a janela pareia: a escolha fica guardada
        (a última vence, como o último chip) e volta o movimento em curso. O fio
        da janela a atende (:meth:`_esperar_a_escolha_dela`).

        Outro destino, ou um endereço que a janela não viu, não é escolha: o
        pedido segue o caminho de sempre, e a recusa do um por vez fica. É o que
        impede um «Mover» ou um «Equilibrar» que chega entre dois tiques de
        virar, calado, a escolha de um controle que está ligado noutro adaptador
        e nunca vai aparecer nesta janela. ``None`` quando não é escolha.
        """
        pedido = endereco_de(destino) if destino else None
        if pedido is None or self._parar.is_set():
            return None
        with self._tranca:
            atual = self._movimentos.get(CONECTANDO)
            if (atual is None or not atual.em_curso
                    or atual.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA
                    or atual.destino != pedido or alvo not in self._vistos_na_janela):
                return None
            self._escolha = alvo
        logger.info("central_ela_escolheu", aparelho=mascarar(alvo), adaptador=mascarar(pedido))
        return atual

    def _tomar_o_destino_pedido(
        self, movimento: Movimento, *, recomecar: bool = False
    ) -> Movimento | None:
        """O fio atende o destino que ela pediu: o movimento vai para ele.

        Tirar o pedido da fila e guardar o destino novo são UM passo, sob a
        tranca do :meth:`_mudar_o_destino` — senão o clique de volta ao destino
        de agora, no meio, desfaria um pedido que o fio já levou. A janela
        recomeça inteira, e o prazo com ela: o ``comecou`` e o ``quando`` são de
        agora (a tela conta o «Segure PS + Create» do ``quando``). O destino
        novo deixa de ser origem. ``recomecar``: sem pedido, a janela recomeça
        onde estava. ``None`` quando não há nada a atender.
        """
        with self._tranca:
            novo, self._destino_pedido = self._destino_pedido, None
            if novo is None or novo == movimento.destino:
                if not recomecar:
                    return None
                novo = movimento.destino
            if self._busca is not None:
                self._busca = {**self._busca, "adaptador": novo}
            feito = replace(
                movimento, destino=novo, passo=PASSO_PREPARANDO,
                origens=tuple(o for o in movimento.origens if o != novo),
                comecou=self._relogio(), quando=time.time(),
            )
            self._movimentos[feito.aparelho] = feito
        self._no_fio_atual.chave = feito.aparelho
        logger.info("central_a_janela_foi_para_o_destino_pedido",
                    aparelho=mascarar(feito.aparelho), adaptador=mascarar(novo))
        return feito

    def _recusa_por_outro(self, chave: str, destino: str | None) -> Movimento:
        """A recusa do um por vez — a mesma forma da trava ocupada, e não guardada."""
        logger.info("central_um_por_vez", aparelho=mascarar(chave), fechada=self._parar.is_set())
        return Movimento(chave, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def _no_fio(
        self,
        chave: str,
        destino: str | None,
        trabalho: Callable[[Callable[[], None]], Movimento],
    ) -> Movimento:
        pronto = threading.Event()
        caixa: dict[str, Movimento] = {}

        def trabalhar() -> None:
            try:
                caixa["fim"] = trabalho(pronto.set)
            except Exception:
                logger.warning("central_mover_levantou", aparelho=mascarar(chave), exc_info=True)
            finally:
                pronto.set()
            fim = caixa.get("fim")
            if fim is not None and fim.motivo == MOTIVO_OCUPADO:
                # A recusa não começou nada: vigiar a chave dela vigiaria o
                # movimento de OUTRO pedido, num segundo fio.
                return
            self._vigiar_ate_resolver(fim.aparelho if fim is not None else chave)

        fio = threading.Thread(target=trabalhar, name="hefesto-central-mover", daemon=True)
        self._guardar_o_fio(chave, fio)
        fio.start()
        pronto.wait(self._prazo_da_trava_s + 1.0)
        if "fim" in caixa and caixa["fim"].motivo == MOTIVO_OCUPADO:
            return caixa["fim"]
        return self._pela_chave(chave) or Movimento(
            chave, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=self._relogio()
        )

    def _guardar_o_fio(self, chave: str, fio: threading.Thread) -> None:
        """Guarda o fio para o :meth:`fechar` — sem tirar da lista um que ainda vive.

        Conferência da A-COSTURA-DA-ONDA-2-01: dois pedidos quase juntos com a
        MESMA chave (dois «Conectar», ou o mesmo aparelho para dois destinos)
        passam os dois pela primeira olhada, e o segundo recusa já com a trava e
        morre na hora. Guardado POR CIMA do primeiro, ele fazia o ``fechar()``
        do desligamento esperar só o fio morto — e o que abriu a janela ficava
        sem ninguém esperando o ``Pairable`` do destino voltar. O fio vivo fica,
        e o novo entra ao lado, com a chave numerada.
        """
        with self._tranca:
            rotulo, n = chave, 1
            while (vivo := self._fios.get(rotulo)) is not None and vivo.is_alive():
                n += 1
                rotulo = f"{chave}#{n}"
            self._fios[rotulo] = fio

    def _pela_chave(self, chave: str) -> Movimento | None:
        with self._tranca:
            return self._movimentos.get(chave)

    def _o_mesmo_em_curso(self, alvo: str, destino: str | None) -> Movimento | None:
        atual = self._pela_chave(alvo)
        if atual is None or not atual.em_curso:
            return None
        pedido = endereco_de(destino) if destino else None
        if pedido is None or pedido == atual.destino:
            return atual
        return None

    def mover(
        self,
        aparelho: str,
        destino: str | None = None,
        *,
        _ao_pegar_a_trava: Callable[[], None] | None = None,
    ) -> Movimento:
        """UM aparelho para UM adaptador — síncrono, e bloqueia pelo gesto dela.

        Não existe para o tique: é o corpo do fio de :meth:`comecar_a_mover`, e
        é por aqui que a régua o exercita. Nunca levanta; volta o movimento no
        estado em que a volta terminou.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        alvo = endereco_de(aparelho)
        if alvo is None:
            return Movimento(str(aparelho), destino or "", NAO_CHEGOU, PASSO_FIM,
                             MOTIVO_FORA_DO_RADIO)
        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(alvo, destino)
        if mudou is not None:
            return mudou
        escolhido = self._a_escolha_dela(alvo, destino)
        if escolhido is not None:
            return escolhido
        repetido = self._o_mesmo_em_curso(alvo, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(alvo, destino)
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                # UM POR VEZ, DE NOVO, JÁ COM A TRAVA: o outro pode ter nascido
                # enquanto esta esperava, e soltado a trava ainda «esperando» a
                # conferência. Sem esta segunda olhada, dois pedidos quase juntos
                # abriam duas janelas, uma depois da outra.
                repetido = self._o_mesmo_em_curso(alvo, destino)
                if repetido is not None:
                    return repetido
                if self._ocupada():
                    return self._recusa_por_outro(alvo, destino)
                # O «esperando» nasce ANTES de avisar quem espera a trava: senão
                # o gesto da tela leria o movimento de ontem, já acabado.
                self._comecar(Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                try:
                    self._pagar_as_meias_chaves(self._dono())
                    return self._mover_na_trava(alvo, destino)
                except Exception:
                    return self._falhou(alvo)
        except TravaOcupadaError:
            logger.info("central_mover_trava_ocupada", aparelho=mascarar(alvo))
            return Movimento(alvo, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def conectar(
        self,
        destino: str | None = None,
        *,
        _ao_pegar_a_trava: Callable[[], None] | None = None,
    ) -> Movimento:
        """O «Conectar» (D8): um aparelho no destino com mais vaga de ponte.

        A janela abre no destino da D8 (ou no pedido), e pareia o aparelho que
        ela ESCOLHER na lista, entre os que a janela viu
        (:meth:`_a_escolha_dela`); sem o clique dela, nada pareia, e a janela
        acaba sem gesto. Se ele tinha bond em outro adaptador, é um mover: a
        origem sai depois do «chegou», como no :meth:`mover`. Síncrono, como o
        :meth:`mover`; nunca levanta.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(CONECTANDO, destino)
        if mudou is not None:
            return mudou
        repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(CONECTANDO, destino)
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                # Um por vez, de novo, já com a trava — a razão está no :meth:`mover`.
                repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
                if repetido is not None:
                    return repetido
                if self._ocupada():
                    return self._recusa_por_outro(CONECTANDO, destino)
                self._comecar(Movimento(CONECTANDO, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                try:
                    # A meia chave devida sai ANTES do ``antes``: o destino que
                    # ainda a guardasse «conheceria» o controle, e a janela o
                    # ignoraria.
                    self._pagar_as_meias_chaves(self._dono())
                    return self._conectar_na_trava(destino)
                except Exception:
                    return self._falhou(CONECTANDO)
        except TravaOcupadaError:
            logger.info("central_conectar_trava_ocupada")
            return Movimento(CONECTANDO, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def _conectar_na_trava(self, destino: str | None) -> Movimento:
        comeco = self._relogio()
        dono = self._dono()
        adaptadores = dono.adaptadores()
        movimento = Movimento(CONECTANDO, destino or "", ESPERANDO, PASSO_PREPARANDO,
                              comecou=comeco)
        if adaptadores is None:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_BLUEZ)
        pedido = endereco_de(destino) if destino else self.escolher_destino()
        por_endereco = {a.endereco: a for a in adaptadores}
        movimento = replace(movimento, destino=pedido or "")
        if pedido is None or pedido not in por_endereco:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_DESTINO)
        return self._parear_e_conferir(
            self._guardar(movimento), dono, por_endereco[pedido], conectar=True,
            ligados_antes=self._controles_conectados(dono),
        )

    def _mover_na_trava(self, alvo: str, destino: str | None) -> Movimento:
        comeco = self._relogio()
        dono = self._dono()
        foto = _ler(dono, alvo)
        if foto is None:
            return self._acabou(
                Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=comeco),
                NAO_CHEGOU, MOTIVO_SEM_BLUEZ,
            )
        if not foto.do_aparelho:
            # A webcam é USB, e um endereço que o BlueZ não conhece não se move.
            return self._acabou(
                Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=comeco),
                NAO_CHEGOU, MOTIVO_FORA_DO_RADIO,
            )
        pedido = endereco_de(destino) if destino else self.escolher_destino(alvo)
        e_controle = self._e_controle(foto, alvo)
        origens = tuple(sorted(
            e for e, a in foto.do_aparelho.items() if e != pedido and a.pareado
        ))
        movimento = Movimento(
            alvo, pedido or "", ESPERANDO, PASSO_PREPARANDO,
            origens=origens, e_controle=e_controle, comecou=comeco,
            **self._quem_e(foto, dono, exceto=pedido or ""),
        )
        if pedido is None or pedido not in foto.adaptadores:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_DESTINO)

        # IDEMPOTÊNCIA: já está lá. Sem bond em outro lugar, nada se escreve.
        if self._chegou(movimento, dono):
            if not origens:
                return self._guardar(replace(
                    movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_JA_ESTAVA
                ))
            return self._esquecer_as_origens(movimento, dono)

        # O KERNEL JÁ O DIZ NO DESTINO, e o movimento ainda é «não sei» (o
        # ``SensorHub`` responde ``None`` até o nó fechar uma janela). A conexão
        # do destino é a VIVA, não a «velha» da R6: esquecê-la e abrir a janela
        # deixava o controle sem bond em lugar nenhum se ela não apertasse
        # PS + Create. Nada se pareia nem se esquece aqui — só se confere, e o
        # «esperando» segue para a vigia como depois de um parear.
        if e_controle and self._onde_esta(_hex12(alvo)) == pedido:
            conferindo = self._guardar(replace(movimento, passo=PASSO_CONFERINDO))
            if self._conferir(conferindo, dono):
                return self._esquecer_as_origens(conferindo, dono)
            return self._guardar(replace(conferindo, motivo=MOTIVO_SEM_CONFIRMACAO))

        movimento = self._guardar(movimento)
        self._tirar_o_velho_do_destino(dono, alvo, pedido, foto.do_aparelho.get(pedido))
        movimento = self._desligar_e_esquecer_a_origem(movimento, dono, foto)
        return self._parear_e_conferir(movimento, dono, foto.adaptadores[pedido])

    def _tirar_o_velho_do_destino(
        self,
        dono: bluez_dbus.LeitorDoBluez,
        alvo: str,
        destino: str,
        velho: bluez_dbus.AparelhoDoBluez | None,
    ) -> None:
        """O objeto velho do aparelho no DESTINO sai antes de a janela abrir (R6
        revista: é dele). Com bond, o ``Pair`` responderia «já existe» sobre uma
        chave que o controle não tem mais — sai pela ponte, com lápide. Sem
        bond, é sobra de uma busca antiga, e a espera do gesto o leria como «ela
        apertou PS + Create» antes de ela apertar."""
        if velho is None:
            return
        if velho.pareado:
            self._esquecer(dono, destino, alvo)
        else:
            dono.remover_aparelho(velho.caminho, quem=QUEM)
        self._esperar_sumir(dono, alvo, destino)

    def _quem_e(
        self, foto: _Foto, dono: bluez_dbus.LeitorDoBluez, *, exceto: str = ""
    ) -> dict[str, Any]:
        """A classe, o ``Modalias``, o ``Icon`` e o nome dela, lidos ANTES de a origem sair.

        O nome é o ``Alias`` que difere do ``Name`` de fábrica — o do objeto
        CONECTADO primeiro, porque é nele que ela renomeou por último; sem ele,
        o de qualquer adaptador. Um ``Alias`` igual ao ``Name`` é o BlueZ
        repetindo a fábrica, e não vai junto (o destino já o terá). O objeto do
        DESTINO (``exceto``) não conta para o nome: ou é a sobra velha que a R6
        tira, ou é o recém-achado pela janela, que só tem o nome de fábrica.

        SEM ``Alias`` DELA EM OBJETO NENHUM, VALE O GUARDADO
        (O-RADIO-CONECTA-ONDE-ELA-MANDA-02, 26/09/2026): esquecida a última
        chave do controle, não sobra objeto de onde copiar, e o ``Pair``
        seguinte nascia com o nome de fábrica — o E3 dela. O nome mora no
        ``maquina.json`` pelo endereço (:class:`GuardaDosNomes`) e volta por
        aqui em todo ``Pair`` (:meth:`_dar_o_nome`).
        """
        pares = sorted(foto.do_aparelho.items(), key=lambda par: par[1].conectado is not True)
        objetos = [o for _e, o in pares]
        classe = next((o.classe for o in objetos if o.classe is not None), None)
        modalias = next((o.modalias for o in objetos if o.modalias), "")
        icone = next((o.icone for o in objetos if o.icone), "")
        dados = (self._nome_dado(dono, o) for e, o in pares if e != exceto)
        nome = next((dado for dado in dados if dado), "")
        if not nome and objetos:
            nome = self._nome_guardado(objetos[0].endereco)
        return {"classe": classe, "modalias": modalias, "icone": icone, "nome": nome}

    @staticmethod
    def _nome_dado(dono: bluez_dbus.LeitorDoBluez, objeto: bluez_dbus.AparelhoDoBluez) -> str:
        """O ``Alias`` DESTE objeto quando é um nome que ela deu; ``""`` quando é
        o de fábrica — igual ao ``Name``, ou o endereço que o BlueZ põe quando o
        aparelho ainda não disse o nome (``AA-BB-CC-…``)."""
        alias = str(objeto.nome or "").strip()
        if not alias:
            return ""
        fabrica = str(dono.propriedade(objeto.caminho, bluez_dbus.APARELHO, "Name") or "").strip()
        if alias == fabrica or alias.replace("-", ":").lower() == objeto.endereco:
            return ""
        return alias

    def _nome_guardado(self, aparelho: str) -> str:
        """O nome que ela deu a este aparelho, pelo endereço; ``""`` sem nome ou sem ler."""
        try:
            return str((self._nomes.ler() or {}).get(aparelho) or "")
        except Exception:
            logger.warning("central_nomes_nao_leu", exc_info=True)
            return ""

    def _desligar_e_esquecer_a_origem(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez, foto: _Foto
    ) -> Movimento:
        """A PARTE DO PRODUTO, antes de pedir o gesto — a R1 dela ao pé da letra.

        1. DESLIGA: ``Disconnect`` em todo adaptador em que o aparelho está
           conectado. É fora do ar que o PS + Create o põe em modo de parear —
           conectado, o gesto não faz nada (a lista dela, passo c1). O que
           ninguém mediu é se o controle APAGA quando o host solta o enlace ou
           fica procurando o host: o mapa diz o desligar por software «não
           localizado» (``energia.desligar@dualsense``). A cura não depende
           disso — pede o controle fora do ar (o ``HID_PHYS`` vazio), e com a
           chave da origem esquecida a procura dele não tem onde pousar.
        2. ESQUECE cada origem: ``RemoveDevice`` mais o verbo ``esquecer`` da
           ponte, com lápide. Sem a chave lá, o controle não tem para onde
           voltar sozinho (passo c2: *«muda de adaptador, fica um tempo, e volta
           para o anterior»*). <!-- noqa-acento: citação literal dela -->

        O destino não entra aqui: a conexão viva dele já foi tratada antes (o
        bloco do kernel), e a velha, pelo bloco da R6.
        """
        movimento = self._guardar(replace(movimento, passo=PASSO_DESLIGANDO))
        alvo = movimento.aparelho
        for endereco in sorted(foto.do_aparelho):
            if endereco == movimento.destino:
                continue
            caminho = foto.do_aparelho[endereco].caminho
            conectado = bluez_dbus.como_booleano(
                dono.propriedade(caminho, bluez_dbus.APARELHO, "Connected")
            )
            if conectado is True:
                dono.desconectar(caminho, quem=QUEM)
        self._esperar_desligar(movimento, dono)
        for origem in movimento.origens:
            self._esquecer(dono, origem, alvo)
            self._esperar_sumir(dono, alvo, origem)
        return self._guardar(replace(movimento, origens_esquecidas=True))

    def _esperar_desligar(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> None:
        """Até :data:`ESPERA_DO_DESLIGAR_S` pelo controle fora do ar: o
        ``HID_PHYS`` vazio (controle) ou nenhum ``Connected`` (o resto)."""
        fim = self._relogio() + ESPERA_DO_DESLIGAR_S
        while True:
            if movimento.e_controle:
                ainda = bool(self._onde_esta(_hex12(movimento.aparelho)))
            else:
                ainda = any(
                    bluez_dbus.como_booleano(
                        dono.propriedade(o.caminho, bluez_dbus.APARELHO, "Connected")
                    ) is True
                    for o in (dono.aparelhos() or ())
                    if o.endereco == movimento.aparelho
                )
            if not ainda or self._relogio() >= fim or self._parar.is_set():
                return
            self._dormir(PASSO_S)

    def _parear_e_conferir(
        self,
        movimento: Movimento,
        dono: bluez_dbus.LeitorDoBluez,
        adaptador: bluez_dbus.AdaptadorDoBluez,
        *,
        conectar: bool = False,
        ligados_antes: frozenset[str] = frozenset(),
    ) -> Movimento:
        """APLICAR e CONFERIR: a janela só no destino, o gesto, o ``Pair``, o
        nome dela, o ``Connect``; depois o ``HID_PHYS``. ``conectar`` diz que é
        um «Conectar»: o alvo é o aparelho que ela escolher na lista — ou o
        controle que voltar pelo pareamento antigo (``ligados_antes`` são os que
        já estavam conectados quando a janela abriu, e esses não são o dela).

        UMA JANELA POR DESTINO, E O DESTINO É O ÚLTIMO QUE ELA PEDIU
        (O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01): o pedido que chega antes de
        o aparelho aparecer fecha a janela onde ela está e a abre no destino
        novo (:meth:`_ir_para`), e a volta recomeça. A janela que fechou por um
        pedido que ela desfez no mesmo instante recomeça onde estava."""
        fechou = False
        while True:
            pedido = self._tomar_o_destino_pedido(movimento, recomecar=fechou)
            if pedido is not None:
                ida = self._ir_para(pedido, dono, conectar=conectar)
                if isinstance(ida, Movimento):
                    return ida
                movimento, adaptador = ida
            desfecho = self._uma_janela(movimento, dono, adaptador, conectar=conectar,
                                        ligados_antes=ligados_antes)
            fechou = desfecho is None
            if desfecho is None:
                continue
            if not desfecho.em_curso:
                return desfecho
            movimento = desfecho
            break

        movimento = self._guardar(replace(movimento, passo=PASSO_CONFERINDO))
        if not self._conferir(movimento, dono):
            logger.info("central_mover_sem_confirmacao", aparelho=mascarar(movimento.aparelho))
            pendente = self._guardar(replace(movimento, motivo=MOTIVO_SEM_CONFIRMACAO))
            if self._relogio() - pendente.comecou >= self._prazo_do_pendente_s:
                # O prazo venceu DENTRO da conferência: o «não chegou» sai já,
                # no mesmo instante em que a tela solta o «esperando».
                return self._fechar_sem_chegar(pendente, MOTIVO_PRAZO, dono)
            return pendente
        return self._esquecer_as_origens(movimento, dono)

    def _uma_janela(
        self,
        movimento: Movimento,
        dono: bluez_dbus.LeitorDoBluez,
        adaptador: bluez_dbus.AdaptadorDoBluez,
        *,
        conectar: bool,
        ligados_antes: frozenset[str],
    ) -> Movimento | None:
        """A janela num destino: o gesto, o ``Pair``, o nome dela e o ``Connect``.

        Devolve o movimento pareado (ainda «esperando», para o CONFERIR), o
        movimento acabado, ou ``None`` quando ela pediu outro destino antes de o
        aparelho aparecer — a janela daqui fecha no ``finally``, como fecha
        sempre, e a escolha e os VISTOS dela zeram junto.
        """
        restaurar = self._preparar_o_adaptador(dono, adaptador)
        with self._tranca:
            self._escolha, self._vistos_na_janela = None, frozenset()
        # A JANELA É DO MOVIMENTO (D-3009-O-TETO-DA-BUSCA): a busca do
        # «Procurar» vai até o teto da ponte; a do «Mover», os 30 s de sempre.
        segundos = self._segundos_da_busca if conectar else self._segundos
        janela = self._abrir_janela(adaptador.endereco, segundos, dono)
        # A busca segue publicada quando a janela fecha por um pedido do chip:
        # ela só muda de adaptador, e o interruptor não pisca no meio.
        segue = False
        try:
            motivo = janela.abrir_a_janela()
            if motivo:
                logger.warning("central_janela_nao_abriu", motivo=motivo[:200])
                return self._sem_chegar_do_gesto(movimento, MOTIVO_SEM_JANELA)
            movimento = self._guardar(replace(movimento, passo=PASSO_GESTO))
            comeco = self._relogio()
            if conectar:
                desde = time.time()
                with self._tranca:
                    self._busca = {"adaptador": adaptador.endereco, "desde": round(desde, 3),
                                   "ate": round(desde + segundos, 3)}
                    self._janela_da_busca = janela
                    self._aberturas += 1
                    self._ultima_busca = dict(self._busca)
                achado = self._esperar_a_escolha_dela(janela, dono, ligados_antes,
                                                      comeco=comeco, segundos=segundos)
                if achado is None:
                    fim = self._sem_gesto(movimento, janela, comeco, segundos)
                    segue = fim is None
                    return fim
                with self._tranca:
                    self._busca = None
                endereco, pelo_antigo = achado
                if pelo_antigo:
                    return self._voltou_pelo_antigo(movimento, endereco, dono)
                pareando = self._quem_chegou(movimento, endereco, dono)
            elif not self._esperar_o_gesto(janela, movimento.aparelho, comeco=comeco):
                return self._sem_gesto(movimento, janela, comeco, segundos)
            else:
                pareando = self._sair_do_gesto(movimento, passo=PASSO_PAREANDO)
            if pareando is None:
                return None
            movimento = pareando
            resultado = janela.parear(movimento.aparelho)
            if resultado.estado not in (ESTADO_PAREOU, ESTADO_JA_PAREADO):
                return self._acabou(movimento, NAO_CHEGOU, MOTIVO_NAO_PAREOU)
            movimento = self._guardar(replace(movimento, pareou_no_destino=True))
            self._dar_o_nome(dono, movimento)
            self._lembrar_o_alias(dono, movimento.aparelho, movimento.destino)
            self._conectar(dono, movimento.aparelho, movimento.destino)
            return movimento
        finally:
            with self._tranca:
                self._escolha, self._vistos_na_janela = None, frozenset()
                self._janela_da_busca, self._desligar = None, False
                if not segue:
                    self._busca = None
            janela.fechar()
            restaurar()

    def _sem_gesto(self, movimento: Movimento, janela: Janela, comeco: float,
                   segundos: float) -> Movimento | None:
        """A espera do gesto voltou sem o aparelho. Se a janela ainda estava de
        pé, quem a interrompeu foi um pedido de outro destino — e um pedido que
        ela desfez no mesmo instante não é «não chegou»: ``None``, e a janela
        recomeça. Acabada a janela, é o «não chegou» (ou o pedido, se veio); e,
        se foi ela que desligou o «Procurar», o fim é :data:`MOTIVO_DESLIGADA`."""
        if self._desligar:
            return self._sem_chegar_do_gesto(movimento, MOTIVO_DESLIGADA)
        if not (self._parar.is_set() or not janela.aberta
                or self._relogio() >= comeco + segundos):
            return None
        return self._sem_chegar_do_gesto(movimento, MOTIVO_SEM_GESTO)

    def _sem_chegar_do_gesto(self, movimento: Movimento, motivo: str) -> Movimento | None:
        """O «não chegou» de uma janela sem gesto — ou ``None``, com o pedido de
        outro destino na fila: aí não acabou, a janela vai para lá."""
        feito = self._sair_do_gesto(movimento, estado=NAO_CHEGOU, passo=PASSO_FIM, motivo=motivo)
        if feito is not None:
            self._no_diario_do_nao_chegou(feito)
        return feito

    def _ir_para(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez, *, conectar: bool
    ) -> Movimento | tuple[Movimento, bluez_dbus.AdaptadorDoBluez]:
        """O destino que ela pediu (:meth:`_tomar_o_destino_pedido`), antes da janela de lá.

        * No «Conectar», nada a fazer antes: a janela de lá recomeça a lista, e
          a escolha dela, do zero.
        * No «Mover», o objeto velho do controle no destino novo sai como sai no
          primeiro (a R6, :meth:`_tirar_o_velho_do_destino`); as origens já
          saíram antes da primeira janela.

        Devolve ``(movimento, adaptador)``, ou o movimento acabado quando o
        destino saiu da máquina no meio (:data:`MOTIVO_SEM_DESTINO`).
        """
        novo = movimento.destino
        adaptador = next((a for a in dono.adaptadores() or () if a.endereco == novo), None)
        if adaptador is None:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_DESTINO)
        if conectar:
            return movimento, adaptador
        foto = _ler(dono, movimento.aparelho)
        if foto is not None:
            self._tirar_o_velho_do_destino(dono, movimento.aparelho, novo,
                                           foto.do_aparelho.get(novo))
        return movimento, adaptador

    def _quem_chegou(
        self, movimento: Movimento, achado: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento | None:
        """O «Conectar» ganha o endereço e vai para o ``Pair``: sai a chave
        :data:`CONECTANDO`, entra o aparelho que ela escolheu, com as origens
        que ele tinha em OUTROS adaptadores. ``None`` se ela pediu outro destino
        antes (:meth:`_sair_do_gesto`).

        O QUE ELE É, A CLASSE DIZ (:meth:`_e_controle`): a escolha vale para
        qualquer aparelho da janela (a D6 de 22/09: todo aparelho Bluetooth age
        daqui), e o CONFERIR de quem não é controle é o do «Mover»
        (:meth:`_chegou`, pelo ``Connected`` do BlueZ). Até 30/09 ele nascia
        controle sempre, porque a janela só pegava controle."""
        foto = _ler(dono, achado)
        origens = tuple(sorted(
            e for e, a in (foto.do_aparelho.items() if foto is not None else ())
            if e != movimento.destino and a.pareado
        ))
        quem = self._quem_e(foto, dono, exceto=movimento.destino) if foto is not None else {}
        e_controle = self._e_controle(foto, achado) if foto is not None else True
        return self._sair_do_gesto(movimento, aparelho=achado, origens=origens,
                                   e_controle=e_controle, passo=PASSO_PAREANDO, **quem)

    def _voltou_pelo_antigo(
        self, movimento: Movimento, achado: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «Conectar» que acaba porque o controle voltou pelo pareamento antigo.

        Ela ligou o controle só com o PS (ou o PS com outro botão), e ele
        reconectou no adaptador que já tinha a chave dele — sem passar pela
        janela. O controle ESTÁ conectado, e é o dela: o movimento acaba
        «chegou» ONDE ele chegou, e a tela o mostra chegando. Nada se esquece:
        a chave de lá é a que vale agora, e a faxina cuida de sobra em outro
        adaptador. Chamado com a janela ainda aberta — quem a fecha é o
        ``finally`` de :meth:`_parear_e_conferir`.
        """
        onde = self._onde_esta(_hex12(achado))
        foto = _ler(dono, achado)
        quem = self._quem_e(foto, dono) if foto is not None else {}
        with self._tranca:
            self._movimentos.pop(CONECTANDO, None)
        feito = self._guardar(replace(
            movimento, aparelho=achado, destino=onde or movimento.destino, e_controle=True,
            estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_PELO_PAREAMENTO_ANTIGO, **quem,
        ))
        logger.info("central_conectar_pelo_pareamento_antigo", aparelho=mascarar(achado),
                    adaptador=mascarar(feito.destino))
        self._no_diario(
            VOLTOU_PELO_PAREAMENTO_ANTIGO,
            "ela ligou o controle e ele voltou para o adaptador que tinha a chave dele",
            feito,
            depois={"adaptador": feito.destino},
        )
        return feito

    def _dar_o_nome(self, dono: bluez_dbus.LeitorDoBluez, movimento: Movimento) -> None:
        """O nome dela vai junto: o ``Alias`` do objeto NOVO no destino.

        O nome é do APARELHO, e o BlueZ o guarda por objeto — um por adaptador.
        Sem esta escrita, mover o controle fazia o nome que ela deu sumir (a
        lista dela de 25/09, passo a2). Nada escreve quando o nome era o de
        fábrica. Uma escrita recusada não decide nada: o controle chegou igual.
        """
        if not movimento.nome:
            return
        no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
        if no is None:
            return
        dono.escrever_propriedade(no, bluez_dbus.APARELHO, "Alias", "s", movimento.nome,
                                  quem=QUEM)

    # -- os passos -------------------------------------------------------------

    def _e_controle(self, foto: _Foto, alvo: str) -> bool:
        """Pergunta à CLASSE do aparelho, nunca ao nome. Sem classe, ao ``Icon``
        que o próprio BlueZ deriva (da ``Appearance``, no de baixo consumo); sem
        os dois, ao daemon — o controle que ele publica é controle.

        FATO SUBSTITUÍDO (o conferente da A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01,
        25/09/2026): sem classe, a pergunta ia ao kernel — *«o aparelho que tem
        hidraw no rádio é controle»*. Todo aparelho HID pelo rádio tem hidraw, e
        o ``HID_PHYS`` dele é o adaptador: o teclado de baixo consumo, que não
        publica ``Class`` (o «BT5.0 Keyboard» da lista dela, passos b7 e c3),
        virava controle. A tela o vestia de DualSense com «Segure PS + Create»,
        e o CONFERIR esperava um movimento que teclado não tem até o prazo — com
        a origem já esquecida e a central ocupada por dois minutos.
        """
        pelo_bluez = _o_bluez_diz_controle(foto.do_aparelho.values())
        if pelo_bluez is not None:
            return pelo_bluez
        alvo12 = _hex12(alvo)
        return any(_hex12(str(c.get("uniq") or "")) == alvo12 for c in self._ultimos_controles)

    def _o_daemon_mede(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """O daemon mede o movimento DESTE controle? Só o do DualSense (Sony
        ``054C``, produtos ``0CE6`` e ``0DF2``), que é o controle que ele lê.

        O ``Modalias`` é o lido antes de a origem sair ou, no «Conectar» (que
        acha o controle ANTES de parear, quando o BlueZ ainda não tem o
        ``Modalias`` dele), o do objeto no destino. Sem ``Modalias`` nenhum é
        «não sei», e «não sei» não afrouxa o CONFERIR: vale o movimento.
        """
        modalias = movimento.modalias
        if not modalias:
            no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
            if no is not None:
                modalias = str(dono.propriedade(no, bluez_dbus.APARELHO, "Modalias") or "")
        if not modalias:
            return True
        return _MODALIAS_QUE_O_DAEMON_MEDE.search(modalias) is not None

    def _preparar_o_adaptador(
        self, dono: bluez_dbus.LeitorDoBluez, adaptador: bluez_dbus.AdaptadorDoBluez
    ) -> Callable[[], None]:
        """``Powered`` se preciso e ``Pairable`` SÓ durante a janela.

        Decisão de quem coordena (23/09): num computador de outra pessoa o
        adaptador pode nascer desligado. Devolve quem desfaz o ``Pairable`` —
        o ``Powered`` fica: o aparelho passa a morar ali.
        """
        caminho = adaptador.caminho
        if adaptador.ligado is False:
            dono.escrever_propriedade(caminho, bluez_dbus.ADAPTADOR, "Powered", "b", True,
                                      quem=QUEM)
        antes = bluez_dbus.como_booleano(
            dono.propriedade(caminho, bluez_dbus.ADAPTADOR, "Pairable")
        )
        if antes is True:
            return lambda: None
        escrita = dono.escrever_propriedade(caminho, bluez_dbus.ADAPTADOR, "Pairable", "b",
                                            True, quem=QUEM)
        if not escrita.feita or antes is None:
            # "Não sei" o de antes: devolver `False` poderia fechar o que já
            # estava aberto. Quem não sabe não desfaz.
            return lambda: None

        def devolver() -> None:
            dono.escrever_propriedade(caminho, bluez_dbus.ADAPTADOR, "Pairable", "b", False,
                                      quem=QUEM)

        return devolver

    def _esperar_o_gesto(self, janela: Janela, alvo: str, *, comeco: float) -> bool:
        """Espera o aparelho aparecer na janela — ela segurando PS + Create."""
        fim = comeco + self._segundos
        while True:
            if any(getattr(c, "endereco", "") == alvo for c in janela.candidatos()):
                return True
            if (self._parar.is_set() or self._relogio() >= fim or not janela.aberta
                    or self._destino_pedido is not None):
                return False
            self._dormir(PASSO_S)

    def _esperar_a_escolha_dela(
        self,
        janela: Janela,
        dono: bluez_dbus.LeitorDoBluez,
        ligados_antes: frozenset[str],
        *,
        comeco: float,
        segundos: float,
    ) -> tuple[str, bool] | None:
        """O «Conectar»: ``(endereço, pelo_antigo)`` do aparelho dela, ou ``None``.

        Dois jeitos de ele chegar:

        * na JANELA, pelo clique dela — o «Parear» (ou o «Conectar», de quem o
          destino já conhece) da linha dele, que :meth:`_a_escolha_dela` guarda;
          vale quando o endereço escolhido está entre os que a janela viu
          (``pelo_antigo`` falso). Para ele, os filtros de adivinhar de antes
          (o que o destino já conhecia, o já pareado, a classe) não valem: ela
          disse quem é;
        * CONECTADO em qualquer adaptador, sem ter estado conectado quando a
          janela abriu — ela o ligou só com o PS, e ele voltou pelo pareamento
          antigo (``pelo_antigo`` verdadeiro). Quem diz que ele chegou é o
          kernel (``HID_PHYS``), como no CONFERIR. Isso não é parear: é ele
          ligando onde já tem a chave dele.

        NADA PAREIA SEM O CLIQUE DELA (O-PAREAR-ESPERA-O-CLIQUE-01): até 30/09
        este fio devolvia o primeiro controle que a busca achasse, a cada meio
        segundo, e a tela, que lê o BlueZ a cada 3 s, nunca o mostrava na lista
        — e o controle com a chave só do lado dele, que chama o adaptador
        sozinho, era pareado de novo sem modo de parear (o 01:23:40 da madrugada
        dela). Cada volta guarda os VISTOS da janela, para a escolha. Ela acaba
        também quando ela desliga o «Procurar» (:meth:`ligar_a_busca`).
        """
        fim = comeco + segundos
        while True:
            vistos = frozenset(str(getattr(c, "endereco", "") or "")
                               for c in janela.candidatos()) - {""}
            with self._tranca:
                self._vistos_na_janela = vistos
                escolha = self._escolha
            if escolha is not None and escolha in vistos:
                return escolha, False
            voltou = self._quem_voltou_sozinho(dono, ligados_antes)
            if voltou:
                return voltou, True
            if (self._parar.is_set() or self._desligar or self._relogio() >= fim
                    or not janela.aberta or self._destino_pedido is not None):
                return None
            self._dormir(PASSO_S)

    def _controles_conectados(self, dono: bluez_dbus.LeitorDoBluez) -> frozenset[str]:
        """Os controles (pela classe) que o BlueZ diz conectados agora, em qualquer adaptador."""
        return frozenset(
            o.endereco for o in (dono.aparelhos() or ())
            if o.conectado is True and e_controle(o.classe)
        )

    def _quem_voltou_sozinho(
        self, dono: bluez_dbus.LeitorDoBluez, ligados_antes: frozenset[str]
    ) -> str:
        """O controle que se conectou depois de a janela abrir — com o kernel confirmando."""
        for endereco in sorted(self._controles_conectados(dono) - ligados_antes):
            if self._onde_esta(_hex12(endereco)):
                return endereco
        return ""

    def _conectar(self, dono: bluez_dbus.LeitorDoBluez, alvo: str, destino: str) -> None:
        """``Connect`` no destino se o BlueZ ainda não o diz conectado.

        Um ``Connect`` recusado não decide nada: quem decide é o CONFERIR.
        """
        no = dono.caminho_do_aparelho(alvo, adaptador=destino)
        if no is None:
            return
        conectado = bluez_dbus.como_booleano(dono.propriedade(no, bluez_dbus.APARELHO, "Connected"))
        if conectado is not True:
            dono.conectar(no, quem=QUEM)

    def _chegou(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """A pergunta do CONFERIR, UMA vez. Controle: ``HID_PHYS`` no destino E o
        movimento chegando. Outro aparelho: o BlueZ o diz conectado no destino.

        O CONTROLE QUE O DAEMON NÃO LÊ (um 8BitDo, um DualShock 4 — o controle
        desconhecido da régua dela de 25/09) nunca terá movimento medido: para
        ele, o ``HID_PHYS`` no destino é a confirmação, que é a do kernel. Sem
        isto o mover dele esperava o prazo inteiro, dizia «não chegou» com o
        controle lá, e a central ficava ocupada dois minutos.
        """
        if movimento.e_controle:
            uniq = _hex12(movimento.aparelho)
            if self._onde_esta(uniq) != movimento.destino:
                return False
            if self._movimento is None:
                return True
            hz = self._movimento(uniq)
            if hz is not None:
                return hz > 0
            return not self._o_daemon_mede(movimento, dono)
        no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
        if no is None:
            return False
        return bluez_dbus.como_booleano(
            dono.propriedade(no, bluez_dbus.APARELHO, "Connected")
        ) is True

    def _conferir(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """Até :data:`CONFERIR_S` perguntando — e nunca além do
        :data:`PRAZO_DO_PENDENTE_S` do movimento, que é o da tela. Sem
        confirmação, nunca «chegou»."""
        fim = min(self._relogio() + self._conferir_s,
                  movimento.comecou + self._prazo_do_pendente_s)
        while True:
            if self._chegou(movimento, dono):
                return True
            if self._parar.is_set() or self._relogio() >= fim:
                return False
            self._dormir(PASSO_S)

    def _esquecer(self, dono: bluez_dbus.LeitorDoBluez, adaptador: str, aparelho: str) -> bool:
        """Esquece UM aparelho em UM adaptador: ``RemoveDevice`` do dono mais o
        verbo ``esquecer`` da ponte (disco, cache SDP, lápide). Nunca em lote."""
        no = dono.caminho_do_aparelho(aparelho, adaptador=adaptador)
        if no is not None:
            dono.remover_aparelho(no, quem=QUEM)
            self._lembrar_o_alias(dono, aparelho, adaptador, caminho=no, sumiu=True)
        fez, motivo = self._esquecer_na_ponte(adaptador, aparelho)
        if not fez:
            logger.warning(
                "central_esquecer_sem_lapide",
                adaptador=mascarar(adaptador),
                aparelho=mascarar(aparelho),
                motivo=motivo[:200],
            )
        return fez

    def _esperar_sumir(self, dono: bluez_dbus.LeitorDoBluez, aparelho: str, adaptador: str) -> None:
        fim = self._relogio() + ESPERA_DO_SUMICO_S
        while dono.caminho_do_aparelho(aparelho, adaptador=adaptador) is not None:
            if self._relogio() >= fim:
                return
            self._dormir(0.05)

    def _esquecer_as_origens(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O fim do mover: a conexão de cada ORIGEM sai, uma por uma, com lápide.

        Desde 25/09 a origem sai ANTES do gesto (:meth:`_desligar_e_esquecer_a_origem`),
        e aqui ela não sai de novo. Quem ainda passa por aqui esquecendo é o
        controle que o kernel já dizia no destino (o bloco do kernel e a
        idempotência): ele não desligou, porque já estava onde devia.

        Sem origem e sem parear nada, não houve movimento: ele já estava lá, e o
        diário não ganha uma linha de «moveu».
        """
        if not movimento.origens and not movimento.pareou_no_destino:
            return self._guardar(replace(
                movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_JA_ESTAVA
            ))
        movimento = self._guardar(replace(movimento, passo=PASSO_ESQUECENDO))
        sem_lapide = [] if movimento.origens_esquecidas else [
            origem for origem in movimento.origens
            if not self._esquecer(dono, origem, movimento.aparelho)
        ]
        feito = self._guardar(replace(movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=""))
        self._no_diario(
            MOVEU_O_APARELHO,
            "ela moveu com PS + Create, e o HID_PHYS confirmou",
            feito,
            depois={"adaptador": feito.destino, "sem_lapide": sem_lapide or None},
        )
        return feito

    def _acabou(self, movimento: Movimento, estado: str, motivo: str) -> Movimento:
        """O fim do movimento. O «não chegou» que chega aqui depois do ``Pair``
        não tirou a meia chave (um erro no meio), e ela fica DEVIDA."""
        feito = self._guardar(replace(movimento, estado=estado, passo=PASSO_FIM, motivo=motivo))
        if estado == NAO_CHEGOU:
            self._dever_a_meia_chave(feito)
            self._no_diario_do_nao_chegou(feito)
        return feito

    def _dever_a_meia_chave(self, movimento: Movimento) -> None:
        """A chave que ESTE movimento pode ter deixado no destino entra na fila
        do :meth:`_pagar_as_meias_chaves` — só depois do ``Pair`` dele."""
        if movimento.pareou_no_destino and movimento.destino:
            with self._tranca:
                self._meias_chaves.add((movimento.destino, movimento.aparelho))

    def _pagar_as_meias_chaves(self, dono: bluez_dbus.LeitorDoBluez) -> tuple[tuple[str, str], ...]:
        """COM A TRAVA NA MÃO: cada meia chave devida sai — se ainda é meia chave.

        A pergunta é feita ao rádio agora (:meth:`_esquecer_se_meia_chave`): o
        controle que conectou naquele adaptador depois não perde a chave, e a
        dívida sai da fila do mesmo jeito. Ficam, para a próxima vez, a que
        levantou e a que o rádio não soube responder («não sei» não é «não é
        mais meia chave»). Devolve ``(adaptador, aparelho)`` de cada chave que
        saiu. Nunca levanta.
        """
        with self._tranca:
            devidas = sorted(self._meias_chaves)
        pagas: list[tuple[str, str]] = []
        for adaptador, aparelho in devidas:
            try:
                saiu = self._esquecer_se_meia_chave(dono, adaptador, aparelho)
            except Exception:
                logger.warning("central_meia_chave_levantou", aparelho=mascarar(aparelho),
                               adaptador=mascarar(adaptador), exc_info=True)
                continue
            if saiu is None:
                continue
            if saiu:
                pagas.append((adaptador, aparelho))
            with self._tranca:
                self._meias_chaves.discard((adaptador, aparelho))
        if pagas:
            self._no_diario_das_meias_chaves(pagas)
        return tuple(pagas)

    def tirar_as_meias_chaves(self) -> tuple[tuple[str, str], ...]:
        """UMA volta da faxina sobre as meias chaves devidas: pega a trava e as tira.

        ``()`` quando não havia dívida, quando um movimento está em curso (o
        começo dele já as pagou, antes da janela), ou quando a trava não veio no
        prazo — a próxima volta tenta de novo. Nunca levanta.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        with self._tranca:
            devendo = bool(self._meias_chaves)
        if not devendo or self._ocupada():
            return ()
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                if self._ocupada():
                    return ()
                return self._pagar_as_meias_chaves(self._dono())
        except TravaOcupadaError:
            logger.info("central_meias_chaves_trava_ocupada")
        except Exception:
            logger.warning("central_meias_chaves_levantou", exc_info=True)
        return ()

    def _no_diario_das_meias_chaves(self, pagas: Sequence[tuple[str, str]]) -> None:
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            for adaptador, aparelho in pagas:
                diario_do_radio.registrar(
                    QUEM, ESQUECEU_A_MEIA_CHAVE,
                    "o pareamento não chegou, e a chave que ficou no destino saiu quando "
                    "a central teve a trava",
                    depois={"adaptador": adaptador}, controle=aparelho, adaptador=adaptador,
                )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)

    def _no_diario_do_nao_chegou(self, feito: Movimento, *, meia_chave: bool = False) -> None:
        self._no_diario(O_APARELHO_NAO_CHEGOU, feito.motivo, feito,
                        depois={"pareou_no_destino": feito.pareou_no_destino,
                                "origens_esquecidas": feito.origens_esquecidas,
                                "meia_chave_esquecida": meia_chave or None})

    def _fechar_sem_chegar(
        self, movimento: Movimento, motivo: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «não chegou» da vigia e do prazo — com a MEIA CHAVE saindo antes.

        A MEIA CHAVE DO LADO DO DAEMON (O-RADIO-CONECTA-ONDE-ELA-MANDA-02,
        26/09/2026). O controle branco, MEDIDO no diário dela: o ``Pair`` deu, a
        busca de serviços caiu em ``Host is down``, e ele ficou ``Paired`` sem
        nunca ficar ``Connected`` no destino. Até aqui quem tirava essa chave
        era a TELA, e só com a janela aberta — com ela fechada, a chave ficava,
        e o próximo «Conectar» naquele adaptador nem o via (o destino já o
        «conhecia»). Agora ela sai aqui, SÓ naquele adaptador, pelo mesmo
        ``_esquecer`` do mover (``RemoveDevice`` e a lápide da ponte), e ANTES
        de o «não chegou» ser publicado: a tela, que só apaga depois do
        veredito, encontra o adaptador limpo.

        Um de cada vez: a trava e a conferida de que o movimento ainda é este
        impedem a vigia do fio e a do pedido (:meth:`_vencer_os_prazos`) de
        fecharem duas vezes. Sem a trava no prazo do gesto, o «não chegou» sai
        do mesmo jeito — a central não fica «ocupada» por uma chave —, e a
        chave fica DEVIDA (O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01): a tela não
        a tira mais desde a A-CAIXA-FICA-ONDE-ELA-ABRIU-01, e ela sai na primeira
        vez em que a central segura a trava — o começo do próximo movimento,
        antes da janela dele, ou a volta da faxina (:meth:`tirar_as_meias_chaves`).
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                if self._pela_chave(movimento.aparelho) != movimento:
                    return self._pela_chave(movimento.aparelho) or movimento
                esquecida = self._esquecer_a_meia_chave(movimento, dono)
                movimento = self._esquecer_as_origens_mortas(movimento, dono)
                # «Não sei» (o rádio mudo, a chave que não sumiu) também deve.
                return self._acabou_se_ainda(movimento, motivo, meia_chave=esquecida is True,
                                             devida=esquecida is None)
        except TravaOcupadaError:
            logger.warning("central_meia_chave_sem_trava", aparelho=mascarar(movimento.aparelho))
            return self._acabou_se_ainda(movimento, motivo, meia_chave=False, devida=True)

    def _esquecer_as_origens_mortas(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «Conectar» que PAREOU no destino e não conferiu: o ``Pair`` trocou o
        host que o controle guarda (ele guarda UM), e as chaves dele nos outros
        adaptadores morreram com isso — saem pelo mesmo ``_esquecer`` do mover,
        com lápide (cura 4 da ESQUECER-E-LIMPAR-AS-CONEXOES-01). Sem ``Pair``, o
        controle nem entrou em modo de parear, e a chave dele continua a que
        vale. O «Mover» já esqueceu as dele antes do gesto.

        Com o controle NO AR (o «voltou» para a origem), o host que ele guarda
        não trocou: a chave por onde ele voltou é a que vale, e nenhuma origem
        sai — esquecer ali o obrigaria a parear de novo."""
        if (not movimento.pareou_no_destino or movimento.origens_esquecidas
                or not movimento.origens or self._onde_esta(_hex12(movimento.aparelho))):
            return movimento
        for origem in movimento.origens:
            self._esquecer(dono, origem, movimento.aparelho)
        return self._guardar(replace(movimento, origens_esquecidas=True))

    def _acabou_se_ainda(
        self, movimento: Movimento, motivo: str, *, meia_chave: bool, devida: bool = False
    ) -> Movimento:
        """«Não chegou» só se o movimento guardado ainda é ESTE — conferido e
        trocado de uma vez, sob a tranca. ``devida``: a meia chave não pôde sair
        agora, e entra na fila junto com o veredito."""
        feito = replace(movimento, estado=NAO_CHEGOU, passo=PASSO_FIM, motivo=motivo)
        with self._tranca:
            atual = self._movimentos.get(movimento.aparelho)
            if atual != movimento:
                return atual or movimento
            self._movimentos[movimento.aparelho] = feito
            self._mudou_o_movimento(feito)
        if devida:
            self._dever_a_meia_chave(feito)
        self._no_diario_do_nao_chegou(feito, meia_chave=meia_chave)
        return feito

    def _esquecer_a_meia_chave(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> bool | None:
        """A chave que ESTE movimento criou no destino e que nunca conectou sai
        — só quando o ``Pair`` deste movimento deu (``pareou_no_destino``).
        As três respostas são as do :meth:`_esquecer_se_meia_chave`."""
        if not movimento.pareou_no_destino or not movimento.destino:
            return False
        return self._esquecer_se_meia_chave(dono, movimento.destino, movimento.aparelho)

    def _esquecer_se_meia_chave(
        self, dono: bluez_dbus.LeitorDoBluez, adaptador: str, aparelho: str
    ) -> bool | None:
        """A meia chave de ``aparelho`` em ``adaptador`` sai — se ainda é meia chave.

        O BlueZ diz o objeto ``Paired`` e não ``Connected``, e o kernel não o
        diz naquele adaptador. Quem está no ar nunca sai por aqui, e nenhum
        outro adaptador é tocado. UM dono para a pergunta: o «não chegou» de
        agora e a dívida paga depois (:meth:`_pagar_as_meias_chaves`).

        ``True``: saiu. ``False``: não é, ou não é mais, meia chave. ``None``:
        NÃO SEI — o rádio não respondeu, o adaptador não está na máquina (a
        chave volta com ele), ou o esquecer não a tirou. Quem pergunta a deixa
        devida: «não sei» nunca vira «não há» (a conferência de 28/09/2026 —
        com o ``bluetoothd`` fora do barramento, a dívida saía da fila sem a
        chave sair do adaptador).
        """
        adaptadores = dono.adaptadores()
        if adaptadores is None or adaptador not in {a.endereco for a in adaptadores}:
            return None
        no = dono.caminho_do_aparelho(aparelho, adaptador=adaptador)
        if no is None:
            return None if dono.caminhos() is None else False
        pareado = bluez_dbus.como_booleano(dono.propriedade(no, bluez_dbus.APARELHO, "Paired"))
        conectado = bluez_dbus.como_booleano(
            dono.propriedade(no, bluez_dbus.APARELHO, "Connected"))
        if pareado is None:
            return None
        if pareado is not True or conectado is True:
            return False
        if self._onde_esta(_hex12(aparelho)) == adaptador:
            return False
        logger.info("central_esquece_a_meia_chave", aparelho=mascarar(aparelho),
                    adaptador=mascarar(adaptador))
        self._esquecer(dono, adaptador, aparelho)
        self._esperar_sumir(dono, aparelho, adaptador)
        if (dono.caminho_do_aparelho(aparelho, adaptador=adaptador) is not None
                or dono.caminhos() is None):
            logger.warning("central_meia_chave_nao_sumiu", aparelho=mascarar(aparelho),
                           adaptador=mascarar(adaptador))
            return None
        return True

    def _no_diario(
        self, o_que: str, por_que: str, movimento: Movimento, *, depois: Mapping[str, Any]
    ) -> None:
        """Uma linha no diário comum. Nunca levanta: o gesto já aconteceu."""
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM,
                o_que,
                por_que,
                antes={"adaptadores": list(movimento.origens)},
                depois=dict(depois),
                controle=movimento.aparelho,
                adaptador=movimento.destino or None,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)

    # -- o «esperando» depois da conferência -----------------------------------

    def vigiar(self) -> None:
        """UMA volta sobre os movimentos aplicados e ainda não confirmados.

        Sem a trava para olhar; com ela para esquecer a origem. Chegou no
        destino → esquece a origem e «chegou»; voltou para a origem → «não
        chegou»; passou do prazo → «não chegou». Nada se apaga sem o «chegou».

        Nunca levanta: ela roda num fio, e uma exceção ali matava o fio com o
        movimento «esperando» para sempre. Um erro numa volta é «não sei» — e o
        prazo continua valendo.
        """
        pendentes = [
            m for m in self.movimentos()
            if m.em_curso and m.passo == PASSO_CONFERINDO
        ]
        for movimento in pendentes:
            try:
                self._vigiar_um(movimento)
            except Exception:
                logger.warning(
                    "central_vigia_levantou", aparelho=mascarar(movimento.aparelho), exc_info=True
                )
                if (
                    self._relogio() - movimento.comecou >= self._prazo_do_pendente_s
                    and self.movimento_de(movimento.aparelho) == movimento
                ):
                    self._acabou(movimento, NAO_CHEGOU, MOTIVO_PRAZO)

    def _vigiar_um(self, movimento: Movimento) -> None:
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        dono = self._dono()
        if self._chegou(movimento, dono):
            with contextlib.suppress(TravaOcupadaError), bluez_dbus.na_trava(
                QUEM, prazo_s=self._prazo_da_trava_s
            ):
                if self.movimento_de(movimento.aparelho) == movimento:
                    self._esquecer_as_origens(movimento, dono)
            return
        if movimento.e_controle and movimento.origens:
            onde = self._onde_esta(_hex12(movimento.aparelho))
            if onde and onde in movimento.origens:
                self._fechar_sem_chegar(movimento, MOTIVO_VOLTOU, dono)
                return
        if self._relogio() - movimento.comecou >= self._prazo_do_pendente_s:
            self._fechar_sem_chegar(movimento, MOTIVO_PRAZO, dono)

    def _vigiar_ate_resolver(self, alvo: str) -> None:
        """O fio do gesto, depois do mover: vigia o «esperando» até resolver."""
        while not self._parar.is_set():
            atual = self.movimento_de(alvo)
            if atual is None or not atual.em_curso or atual.passo != PASSO_CONFERINDO:
                return
            self._dormir(1.0)
            self.vigiar()

    # -- a faxina: a sobra do bond sai sozinha ---------------------------------

    def sobras(self, dono: bluez_dbus.LeitorDoBluez) -> tuple[tuple[str, str, str], ...] | None:
        """``(adaptador que sai, controle, adaptador em que ele está)``, em ordem.

        Só LÊ. Uma sobra é a CHAVE (``Paired``) de um controle num adaptador
        em que o kernel não o diz conectado, quando ele está conectado, pelo
        rádio, em OUTRO adaptador que também tem a chave dele. Fica de fora:

        * o objeto sem chave — o BlueZ guarda um para todo aparelho que uma
          busca achou, e o vizinho visto por dois adaptadores não é bond;
        * o controle desligado ou no cabo (``HID_PHYS`` sem endereço de
          adaptador), a não ser pela LEMBRANÇA de onde ele estava no ar
          (:meth:`_a_lembranca_que_vale`, ESQUECER-E-LIMPAR-AS-CONEXOES-01):
          saem as chaves que já eram sobra no último instante em que ele foi
          visto no ar, e só elas;
        * o aparelho que a classe não diz controle — um teclado de vários
          hosts pode querer as duas chaves;
        * o controle conectado num adaptador em que o BlueZ não mostra chave
          dele: é estado que esta central não entende, e ela não mexe.

        ``None`` = não deu para perguntar, nunca «não há».
        """
        chaves = self._chaves_dobradas(dono)
        if chaves is None:
            return None
        achadas: list[tuple[str, str, str]] = []
        for aparelho, onde_tem in sorted(chaves.items()):
            agora = self._onde_esta(_hex12(aparelho))
            if agora:
                if agora in onde_tem:
                    achadas.extend(
                        (sai, aparelho, agora) for sai in sorted(onde_tem) if sai != agora)
                continue
            lembrada = self._a_lembranca_que_vale(aparelho, onde_tem, dono)
            if lembrada is None:
                continue
            onde, eram = lembrada
            achadas.extend(
                (sai, aparelho, onde) for sai in sorted(onde_tem)
                if sai != onde and (sai, _entrada(dono, onde_tem[sai])) in eram)
        return tuple(achadas)

    def _chaves_dobradas(
        self, dono: bluez_dbus.LeitorDoBluez
    ) -> dict[str, dict[str, bluez_dbus.AparelhoDoBluez]] | None:
        """``{controle: {adaptador: objeto}}`` de quem tem CHAVE (``Paired``) em dois
        ou mais adaptadores da máquina. Só lê; ``None`` = não deu para perguntar."""
        adaptadores = dono.adaptadores()
        aparelhos = dono.aparelhos()
        if adaptadores is None or aparelhos is None:
            return None
        por_caminho = {a.caminho: a.endereco for a in adaptadores}
        chaves: dict[str, dict[str, bluez_dbus.AparelhoDoBluez]] = {}
        for objeto in aparelhos:
            if objeto.pareado is not True or objeto.adaptador not in por_caminho:
                continue
            chaves.setdefault(objeto.endereco, {})[por_caminho[objeto.adaptador]] = objeto
        return {aparelho: onde_tem for aparelho, onde_tem in chaves.items()
                if len(onde_tem) >= 2 and any(e_controle(o.classe) for o in onde_tem.values())}

    def _lembrar_onde_estao(self) -> None:
        """Onde cada controle com a chave dobrada está no ar AGORA, e as chaves
        dele neste instante — a cada passo do fio, com o dono vivo (a foto em
        memória e o ``HID_PHYS``; não escreve nada).

        É o que a limpeza usa quando ele desliga ou passa para o cabo e o
        ``HID_PHYS`` não diz mais nada (cura 4 da ESQUECER-E-LIMPAR-AS-CONEXOES-01).
        Conectado num adaptador sem chave dele, a lembrança cai: é estado que a
        central não entende. Nunca levanta.
        """
        try:
            dono = self._dono_sem_abrir()
            if dono is None or not dono.atende_o_proprio_pareamento:
                return
            chaves = self._chaves_dobradas(dono)
            if chaves is None:
                return
            for aparelho, onde_tem in chaves.items():
                agora = self._onde_esta(_hex12(aparelho))
                if not agora:
                    continue
                with self._tranca:
                    if any(m.em_curso and m.aparelho == aparelho
                           for m in self._movimentos.values()):
                        continue
                    if agora in onde_tem:
                        self._lembrancas[aparelho] = (agora, frozenset(
                            (onde, _entrada(dono, objeto)) for onde, objeto in onde_tem.items()))
                    else:
                        self._lembrancas.pop(aparelho, None)
        except Exception:
            logger.warning("central_lembranca_levantou", exc_info=True)

    def _a_lembranca_que_vale(
        self,
        aparelho: str,
        onde_tem: Mapping[str, bluez_dbus.AparelhoDoBluez],
        dono: bluez_dbus.LeitorDoBluez,
    ) -> tuple[str, frozenset[tuple[str, int]]] | None:
        """A lembrança de onde ``aparelho`` estava no ar — se ela ainda vale.

        Cai (e sai) quando a chave de onde ele estava saiu, ou quando uma chave
        dele nasceu DEPOIS dela: um adaptador novo, ou o mesmo com o objeto
        recriado (o dono conta cada entrada, e o objeto que saiu e voltou é
        outro). Uma chave nova é um pareamento dela, e nunca é sobra.
        """
        with self._tranca:
            lembrada = self._lembrancas.get(aparelho)
        if lembrada is None:
            return None
        onde, eram = lembrada
        agora = {(ad, _entrada(dono, objeto)) for ad, objeto in onde_tem.items()}
        if onde not in onde_tem or not agora <= eram:
            with self._tranca:
                if self._lembrancas.get(aparelho) == lembrada:
                    del self._lembrancas[aparelho]
            return None
        return lembrada

    def esquecer_as_sobras(self, por_que: str = NA_VOLTA_DA_FAXINA) -> tuple[str, str] | None:
        """Esquece UMA sobra e devolve ``(adaptador, controle)``.

        A LÁPIDE VEM PRIMEIRO (ESQUECER-E-LIMPAR-AS-CONEXOES-01, cura 4): a
        limpeza que ninguém pediu chama o verbo ``esquecer`` da ponte — o
        ``RemoveDevice`` como root, o disco, o cache e a lápide —, e só com ele
        feito o objeto que sobrar na foto sai pelo dono. Sem a ponte (não
        instalada, recusando, ou sob a suíte) nada sai, e o diário diz uma vez
        por par que não limpou: uma limpeza que o autorestore pode desfazer não é
        limpeza. ``por_que`` é o momento, e vai ao diário.

        ``None`` quando não havia sobra, quando um movimento está «esperando»
        (o mover esquece a própria origem, e dois motores na mesma chave é o
        defeito que a trava existe para impedir), quando a trava não veio no
        prazo — a próxima volta tenta de novo — ou quando algo levantou. Nunca
        levanta: roda num fio, e o rádio estranho é justamente quando ela é útil.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        if self._ocupada():
            return None
        try:
            dono = self._dono()
            if not self.sobras(dono):
                return None
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                # De novo, já com a trava: o mover pode ter nascido enquanto
                # esta esperava, e a foto de antes pode ter envelhecido.
                if self._ocupada():
                    return None
                achadas = self.sobras(dono)
                if not achadas:
                    return None
                sai, aparelho, fica = achadas[0]
                no = dono.caminho_do_aparelho(aparelho, adaptador=sai)
                fez, motivo = self._esquecer_na_ponte(sai, aparelho)
                if not fez:
                    self._nao_limpou(sai, aparelho, fica, motivo)
                    return None
                resto = dono.caminho_do_aparelho(aparelho, adaptador=sai)
                if resto is not None:
                    dono.remover_aparelho(resto, quem=QUEM)
                self._lembrar_o_alias(dono, aparelho, sai, caminho=no, sumiu=True)
                self._esperar_sumir(dono, aparelho, sai)
        except TravaOcupadaError:
            logger.info("central_faxina_trava_ocupada")
            return None
        except Exception:
            logger.warning("central_faxina_levantou", exc_info=True)
            return None
        with self._tranca:
            self._sem_lapide_dito.discard((sai, aparelho))
        logger.info(
            "central_esqueceu_a_sobra",
            aparelho=mascarar(aparelho),
            adaptador=mascarar(sai),
            fica=mascarar(fica),
            por_que=por_que,
        )
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM,
                ESQUECEU_A_SOBRA,
                por_que,
                antes={"adaptadores": sorted({sai, fica})},
                depois={"adaptador": fica},
                controle=aparelho,
                adaptador=sai,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)
        return sai, aparelho

    def _nao_limpou(self, sai: str, aparelho: str, fica: str, motivo: str) -> None:
        """A ponte não enterrou a sobra: nada sai, e o diário diz UMA vez por par."""
        logger.warning("central_sobra_sem_lapide", aparelho=mascarar(aparelho),
                       adaptador=mascarar(sai), motivo=str(motivo)[:200])
        with self._tranca:
            if (sai, aparelho) in self._sem_lapide_dito:
                return
            self._sem_lapide_dito.add((sai, aparelho))
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM, NAO_LIMPOU_SEM_LAPIDE, str(motivo)[:200] or "a ponte não respondeu",
                antes={"adaptadores": sorted({sai, fica})}, depois={"adaptador": fica},
                controle=aparelho, adaptador=sai,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)

    def limpar(self, por_que: str = NA_VOLTA_DA_FAXINA) -> tuple[tuple[str, str], ...]:
        """UMA volta da limpeza: as sobras, um par por vez, até não haver
        nenhuma; e os movimentos acabados que não dizem mais nada saem da
        publicação (:meth:`_tirar_os_acabados`).

        A mesma volta nos três momentos (D-3009-A-CASA-SE-LIMPA-SOZINHA): depois
        de cada troca, quando um controle desliga, e na volta da faxina. Cada
        chamada pega a trava, relê a foto, esquece UM par e a solta — a R6 dela,
        nunca em lote. Nunca levanta.
        """
        feitas: list[tuple[str, str]] = []
        for _ in range(PARES_POR_LIMPEZA):
            feito = self.esquecer_as_sobras(por_que)
            if feito is None:
                break
            feitas.append(feito)
        self._tirar_os_acabados()
        return tuple(feitas)

    def _no_ar(self, aparelho: str, dono: bluez_dbus.LeitorDoBluez | None) -> bool:
        """``aparelho`` está no ar por algum transporte: o ``HID_PHYS`` no rádio,
        o ``Connected`` do BlueZ, ou o daemon o publicando (o cabo também)."""
        u = _hex12(aparelho)
        if self._onde_esta(u):
            return True
        if any(_hex12(str(c.get("uniq") or "")) == u and c.get("connected", True) is not False
               for c in self._ultimos_controles):
            return True
        if dono is not None:
            return any(o.conectado is True and _hex12(o.endereco) == u
                       for o in dono.aparelhos() or ())
        return False

    def _tirar_os_acabados(self) -> tuple[Movimento, ...]:
        """Os movimentos acabados que não dizem mais nada saem da publicação: o
        «não chegou» de um aparelho que já está no ar, e todo acabado com mais
        de :data:`LEMBRA_O_NAO_CONECTOU_S`. O «chegou» fica até lá, para a tela
        o mostrar chegando; o «esperando» nunca sai. Nunca levanta."""
        try:
            dono = self._dono_sem_abrir()
            agora = time.time()
            with self._tranca:
                acabados = [m for m in self._movimentos.values() if not m.em_curso]
            sair = [m for m in acabados
                    if agora - m.quando > LEMBRA_O_NAO_CONECTOU_S
                    or (m.estado == NAO_CHEGOU and m.aparelho and self._no_ar(m.aparelho, dono))]
            with self._tranca:
                for m in sair:
                    if self._movimentos.get(m.aparelho) == m:
                        del self._movimentos[m.aparelho]
            return tuple(sair)
        except Exception:
            logger.warning("central_acabados_levantou", exc_info=True)
            return ()

    def dispensar(self, aparelho: str) -> Movimento | None:
        """O X do «Não Conectou»: o movimento ACABADO de ``aparelho`` sai da
        publicação — e toda janela que abrir depois lê a mesma coisa (cura 2 da
        ESQUECER-E-LIMPAR-AS-CONEXOES-01: a dispensa morava na janela, e voltava
        quando ela fechava e abria o Hefesto). Nunca um «esperando». Devolve o
        que saiu, ou ``None``."""
        alvo = endereco_de(aparelho)
        if alvo is None:
            return None
        with self._tranca:
            atual = self._movimentos.get(alvo)
            if atual is None or atual.em_curso:
                return None
            del self._movimentos[alvo]
        return atual

    def gravar_as_lapides_de_fora(self) -> tuple[tuple[str, str], ...]:
        """A LÁPIDE DE QUEM SAIU POR FORA (cura 5 da ESQUECER-E-LIMPAR-AS-CONEXOES-01).

        O pareamento que saiu do BlueZ sem a trava do Hefesto (as
        Configurações, o ``bluetoothctl``) ganha a lápide pelo mesmo verbo da
        ponte — mas só ao fim de :data:`ESPERA_DA_LAPIDE_DE_FORA_S`, e só se
        três coisas forem verdade: o dono do ``org.bluez`` é o mesmo (um
        ``bluetoothd`` que morreu e voltou é o crash que come bonds, e a
        lápide enterraria o que o autorestore devolve), o adaptador continua na
        máquina (o desplugue não é esquecer), e a chave não voltou. Sem a ponte,
        o par espera a volta seguinte. Devolve os pares enterrados.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        with self._tranca_da_limpeza:
            pendentes = list(self._saidas_de_fora)
        if not pendentes:
            return ()
        agora = self._relogio()
        dono = self._dono_sem_abrir()
        resolvidos: list[tuple[str, str, float, str]] = []
        enterrados: list[tuple[str, str]] = []
        for pendente in pendentes:
            adaptador, aparelho, quando, dono_de_entao = pendente
            if agora - quando < ESPERA_DA_LAPIDE_DE_FORA_S or dono is None:
                continue
            try:
                adaptadores = dono.adaptadores()
                if (dono.dono_do_bluez() != dono_de_entao or adaptadores is None
                        or adaptador not in {a.endereco for a in adaptadores}):
                    resolvidos.append(pendente)
                    continue
                with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                    if dono.caminho_do_aparelho(aparelho, adaptador=adaptador) is not None:
                        resolvidos.append(pendente)
                        continue
                    fez, motivo = self._esquecer_na_ponte(adaptador, aparelho)
            except TravaOcupadaError:
                continue
            except Exception:
                logger.warning("central_lapide_de_fora_levantou", exc_info=True)
                continue
            if not fez:
                logger.warning("central_lapide_de_fora_sem_ponte", aparelho=mascarar(aparelho),
                               adaptador=mascarar(adaptador), motivo=str(motivo)[:200])
                continue
            resolvidos.append(pendente)
            enterrados.append((adaptador, aparelho))
            try:
                from hefesto_dualsense4unix.integrations import diario_do_radio

                diario_do_radio.registrar(
                    QUEM, ENTERROU_O_QUE_SAIU_POR_FORA,
                    "o pareamento saiu do BlueZ por fora do Hefesto, com o serviço vivo",
                    depois={"adaptador": adaptador}, controle=aparelho, adaptador=adaptador,
                )
            except Exception:
                logger.warning("central_diario_nao_gravou", exc_info=True)
        with self._tranca_da_limpeza:
            self._saidas_de_fora = [p for p in self._saidas_de_fora if p not in resolvidos]
        return tuple(enterrados)

    def comecar_a_faxina(
        self, intervalo_s: float = INTERVALO_DA_FAXINA_S, *, passo_s: float | None = None
    ) -> None:
        """Sobe o fio da faxina — uma volta a cada ``intervalo_s``. Idempotente.

        A primeira volta espera um intervalo inteiro: no arranque os controles
        ainda estão conectando, e o ``HID_PHYS`` de quem não chegou é «não
        sei». O :meth:`fechar` o para como para os fios do mover.

        O MESMO FIO CUIDA DO NOME DELA (:meth:`cuidar_dos_nomes`), a cada
        :data:`INTERVALO_DOS_NOMES_S` com o dono vivo, e no passo da faxina
        pelo caminho de reserva; e, no mesmo ritmo, da MEIA CHAVE DEVIDA
        (:meth:`tirar_as_meias_chaves`) — só pega a trava quando há dívida.

        A CASA SE LIMPA SOZINHA (ESQUECER-E-LIMPAR-AS-CONEXOES-01, cura 4): o
        mesmo fio atende os pedidos de limpeza (:meth:`_pedir_a_limpeza`) assim
        que chegam, guarda a cada passo, com o dono vivo, onde está quem tem a
        chave dobrada (:meth:`_lembrar_onde_estao`), e grava a lápide de quem
        saiu por fora (:meth:`gravar_as_lapides_de_fora`). ``passo_s`` é o passo
        do fio; sem ele, o dos nomes.
        """
        with self._tranca:
            vivo = self._fios.get(_FIO_DA_FAXINA)
            if vivo is not None and vivo.is_alive():
                return
            fio = threading.Thread(
                target=self._faxinar_sempre,
                args=(float(intervalo_s), passo_s),
                name="hefesto-central-faxina",
                daemon=True,
            )
            self._fios[_FIO_DA_FAXINA] = fio
        fio.start()

    def _faxinar_sempre(self, intervalo_s: float, passo_s: float | None = None) -> None:
        passo = min(intervalo_s, INTERVALO_DOS_NOMES_S) if passo_s is None else float(passo_s)
        desde_a_faxina = 0.0
        while not self._parar.is_set():
            pedida = self._limpeza_pedida.wait(passo)
            if self._parar.is_set():
                return
            if pedida:
                with self._tranca_da_limpeza:
                    por_que, self._por_que_limpar = self._por_que_limpar, ""
                    self._limpeza_pedida.clear()
                self.limpar(por_que or NA_VOLTA_DA_FAXINA)
                continue
            desde_a_faxina += passo
            faxina = desde_a_faxina >= intervalo_s
            vivo = self._o_dono_e_a_foto_viva()
            if vivo:
                self._lembrar_onde_estao()
            self.gravar_as_lapides_de_fora()
            if faxina or vivo:
                # A meia chave devida não espera a faxina inteira: ela é o que
                # faz o próximo «Conectar» naquele adaptador não ver o controle.
                # Pelo caminho de reserva (subprocessos) ela vai no passo da
                # faxina, como o nome: a dívida que o rádio não sabe responder
                # (o adaptador fora da máquina) fica na fila, e perguntaria de
                # novo a cada passo.
                self.tirar_as_meias_chaves()
                self.cuidar_dos_nomes()
            if faxina:
                desde_a_faxina = 0.0
                self.limpar(NA_VOLTA_DA_FAXINA)

    def _o_dono_e_a_foto_viva(self) -> bool:
        """O dono de agora lê da foto em memória (o Gio), e não de subprocessos."""
        visto = self._dono_sem_abrir()
        return visto is not None and visto.atende_o_proprio_pareamento

    # -- o nome dela: mora pelo endereço, e não depende da chave ---------------

    def _lembrar_o_alias(
        self,
        dono: bluez_dbus.LeitorDoBluez,
        aparelho: str,
        adaptador: str,
        *,
        caminho: str | None = None,
        sumiu: bool = False,
    ) -> None:
        """A central tirou ou recriou o objeto: a volta dos nomes fica sabendo.

        Um ``Pair`` recria o objeto no MESMO caminho de um que o X tirou, e com
        o nome de fábrica se o ``Alias`` do :meth:`_dar_o_nome` foi recusado.
        Sem isto a volta o leria como o objeto de antes voltando ao de fábrica —
        «ela apagou o nome» — e apagaria o dela. A volta em curso descarta o que
        viu (a geração sobe), para não devolver a lembrança velha.
        """
        no = caminho or dono.caminho_do_aparelho(aparelho, adaptador=adaptador)
        if no is None:
            return
        with self._tranca:
            if sumiu:
                self._alias_vistos.pop(no, None)
            else:
                self._alias_vistos[no] = str(
                    dono.propriedade(no, bluez_dbus.APARELHO, "Alias") or "").strip()
            self._geracao_dos_nomes += 1

    def cuidar_dos_nomes(self) -> tuple[tuple[str, str], ...] | None:
        """UMA volta do NOME DELA: guarda o que ela deu, e o devolve a todo objeto.

        O-RADIO-CONECTA-ONDE-ELA-MANDA-02 (26/09/2026), o item 4 da lista dela:
        *«Eu mudei o nome do dispositivo quando eu conectar os dispositivos bt
        novamente eu quero que o nome deles sejam lidos novamente»*. O BlueZ
        guarda o nome (o ``Alias``) POR OBJETO, e o objeto morre com a chave.
        O nome passa a morar pelo ENDEREÇO do controle
        (:class:`GuardaDosNomes`, o ``maquina.json`` no produto), e o ``Alias``
        é a projeção dele. Para cada controle que o BlueZ conhece, pela classe:
        <!-- noqa-acento: citação literal dela -->

        * **ela renomeou** — um objeto CONHECIDO (visto na volta anterior)
          trouxe um ``Alias`` que não é o de fábrica e que mudou (pela tela,
          pelo ``bluetoothctl``, pelo sistema: o produto é para qualquer
          computador): ele é guardado. Entre dois que mudaram juntos, vale o
          conectado;
        * **ela apagou o nome** — o MESMO objeto que tinha o nome guardado
          voltou ao de fábrica, com a chave ainda nele: o guardado sai, o
          objeto que ainda o tinha volta ao de fábrica também, e a tela volta
          ao «Player N»;
        * **o objeto é novo** (um ``Pair`` feito fora da central, uma chave
          nova, o adaptador que volta à porta com um nome velho) ou perdeu o
          nome: o guardado volta a ele. É o «reaplicado em toda conexão»; o
          ``Pair`` da central já nasce com ele (:meth:`_quem_e` e
          :meth:`_dar_o_nome`). Sem nada guardado, o controle que a volta vê
          pela primeira vez ENSINA o nome que já tem — é assim que os nomes
          de antes do install passam a morar no disco.

        Só controle (``ControleDeclarado``), e só objeto com chave recebe o
        nome. Com um movimento em curso a volta não roda: ele tira e recria os
        objetos, e o que ela visse lá no meio é o movimento, não ela.

        O QUE ELA NÃO ALCANÇA, e é escolha: o nome dado POR FORA do produto com
        o daemon parado, sobre um controle que já tinha nome guardado — sem
        ter visto a mudança, a volta não a distingue de um objeto velho, e o
        guardado vence.

        Devolve ``(endereço, nome)`` de cada escrita — no disco ou no
        ``Alias`` —, ou ``None`` quando não rodou. Nunca levanta.
        """
        if self._ocupada():
            return None
        try:
            with self._tranca:
                geracao = self._geracao_dos_nomes
                vistos_antes = dict(self._alias_vistos)
            dono = self._dono()
            aparelhos = dono.aparelhos()
            guardados = self._nomes.ler()
            if aparelhos is None or guardados is None:
                return None
            vistos: dict[str, str] = {}
            feitos: list[tuple[str, str]] = []
            for endereco, objetos in _controles_pelo_endereco(aparelhos).items():
                dados = {o.caminho: self._nome_dado(dono, o) for o in objetos}
                guardado = str(guardados.get(endereco) or "")
                vale, apagou = _o_nome_que_vale(objetos, dados, vistos_antes, guardado)
                gravou = vale == guardado or self._nomes.gravar(endereco, vale or None)
                if not gravou:
                    # A gravação não deu: a volta seguinte tem de ver a MESMA
                    # mudança, então a lembrança deste controle fica a de antes.
                    vistos.update({o.caminho: vistos_antes[o.caminho]
                                   for o in objetos if o.caminho in vistos_antes})
                    continue
                if vale != guardado:
                    logger.info("central_guardou_o_nome", aparelho=mascarar(endereco),
                                apagou=apagou)
                    feitos.append((endereco, vale))
                for objeto in objetos:
                    alias = _alias_de(objeto)
                    vistos[objeto.caminho] = alias
                    if objeto.pareado is not True:
                        continue
                    if vale and alias != vale:
                        novo = vale
                    elif apagou and dados[objeto.caminho] == guardado:
                        novo = ""
                    else:
                        continue
                    escrita = dono.escrever_propriedade(
                        objeto.caminho, bluez_dbus.APARELHO, "Alias", "s", novo, quem=QUEM)
                    if escrita.feita:
                        logger.info("central_devolveu_o_nome", aparelho=mascarar(endereco),
                                    fabrica=not novo)
                        feitos.append((endereco, novo))
            with self._tranca:
                if geracao == self._geracao_dos_nomes:
                    self._alias_vistos = vistos
            return tuple(feitos)
        except Exception:
            logger.warning("central_nomes_levantou", exc_info=True)
            return None


__all__ = [
    "CHEGOU",
    "CONECTANDO",
    "CONFERIR_S",
    "ESPERANDO",
    "ESPERA_DO_DESLIGAR_S",
    "ESQUECEU_A_MEIA_CHAVE",
    "ESQUECEU_A_SOBRA",
    "ESTADOS",
    "ICONE_DE_CONTROLE",
    "INTERVALO_DA_FAXINA_S",
    "INTERVALO_DOS_NOMES_S",
    "MOTIVO_FALHOU",
    "MOTIVO_FORA_DO_RADIO",
    "MOTIVO_JA_ESTAVA",
    "MOTIVO_NAO_PAREOU",
    "MOTIVO_OCUPADO",
    "MOTIVO_PELO_PAREAMENTO_ANTIGO",
    "MOTIVO_PRAZO",
    "MOTIVO_SEM_BLUEZ",
    "MOTIVO_SEM_CONFIRMACAO",
    "MOTIVO_SEM_DESTINO",
    "MOTIVO_SEM_GESTO",
    "MOTIVO_SEM_JANELA",
    "MOTIVO_VOLTOU",
    "MOVEU_O_APARELHO",
    "NAO_CHEGOU",
    "O_APARELHO_NAO_CHEGOU",
    "PASSOS_EM_QUE_O_DESTINO_MUDA",
    "PASSO_CONFERINDO",
    "PASSO_DESLIGANDO",
    "PASSO_ESQUECENDO",
    "PASSO_FIM",
    "PASSO_GESTO",
    "PASSO_PAREANDO",
    "PASSO_PREPARANDO",
    "PRAZO_DA_TRAVA_DO_GESTO_S",
    "PRAZO_DO_PENDENTE_S",
    "QUEM",
    "VOLTOU_PELO_PAREAMENTO_ANTIGO",
    "CentralDoRadio",
    "GuardaDosNomes",
    "Movimento",
    "NomesNaMaquina",
    "endereco_de",
    "esquecer_pela_ponte",
]
