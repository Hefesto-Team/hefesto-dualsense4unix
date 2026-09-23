"""governador_do_radio.py — duas pontes por adaptador, e o adaptador que não escoa.

GOVERNADOR-DO-RADIO-01 (23/09/2026), decisões R2, R3 e R4 dela. O estudo de
23/09 mediu que o que transborda um adaptador são as saídas de RITMO FIXO — a
ponte de som (``0x35``) e a de vibração (``0x32``), 93,75 relatórios por
segundo cada, que não cedem sozinhas. A entrada do controle é elástica e não
entra nesta conta. Em 22/09 a terceira ponte num adaptador derrubou os quatro
controles em 11 a 89 segundos.

Todo escritor de ritmo fixo pede VAGA aqui, com o adaptador resolvido pelo
``HID_PHYS`` do controle. O governador faz duas coisas:

A ADMISSÃO (R3 e R4)
====================
Até :data:`~hefesto_dualsense4unix.integrations.radio_da_mesa.N_MAX_PONTES`
pontes por adaptador — o número tem UM dono, o ``radio_da_mesa``. A terceira
não é recusada calada:

* há vaga em outro adaptador → :class:`Recusa` com a frase «A Entrada 4.1.4 já
  tem 2 controles com som ou vibração. Há vaga na Entrada 1.4.», e o pedido
  fica publicado para a tela PERGUNTAR (R3: sempre pedir mover). Ela escolhe
  «Ligar aqui» (:meth:`GovernadorDoRadio.ligar_aqui`) e a ponte sobe marcada
  «além do limite»;
* não há vaga em adaptador nenhum → a ponte sobe marcada «além do limite» e o
  diário diz o fato (R4: degrada e avisa). Nada é desligado.

O TEMPO REAL, a cada :data:`PERIODO_S`
=====================================
O déficit é a FILA DO HOST crescendo: as escritas nossas aceitas pelo kernel
menos o que o adaptador pôs no ar (o Δ``acl_tx`` do ``ar_do_adaptador``, que só
sobe DEPOIS de haver crédito do controlador). Acima de :data:`LIMIAR_DO_DEFICIT`
pacotes, as pontes daquele adaptador cedem os quadros NA FONTE, antes da fila
do kernel; abaixo de :data:`FOLGA_PARA_VOLTAR`, voltam a escrever. O diário
registra só a BORDA — e no máximo um episódio por adaptador a cada
:data:`INTERVALO_DAS_BORDAS_NO_DIARIO_S`, com os calados contados.

**«NÃO SEI» NUNCA É ZERO.** ``saida_por_s`` ``None`` é o medidor dizendo que a
janela não deu taxa (o contador parado com enlace de pé, o adaptador que
reiniciou). Tratar como zero seria inventar um déficit do tamanho das nossas
escritas; tratar como folga seria inventar escoamento. O governador não muda
de ideia sem medida, e as escritas daquela janela não entram na conta.

E o relógio do teto também não anda sem medida (conferência de 23/09/2026):
ele soma só as janelas MEDIDAS em que as pontes seguiram cedendo. Contado no
relógio de parede, dois segundos de «não sei» logo depois de ceder derrubavam
as pontes e escreviam no diário «não drena» — a mesma conclusão de zero pacote
no ar, tirada de nenhum pacote medido.

E CEDER TEM O MESMO TETO DA FILA CHEIA (:data:`~hefesto_dualsense4unix.
integrations.alto_falante_bt.TETO_DE_CEDER_S`): um adaptador que não escoa por
mais que isso não está congestionado, está parado. As pontes dele caem com o
motivo dito, e o adaptador espera :data:`ESPERA_DA_FILA_PARADA_S` antes de
aceitar ponte de novo — a ponte sob demanda religa sozinha. A espera cresce a
cada queda seguida, até :data:`TETO_DA_ESPERA_DA_FILA_S` (o item 3 abaixo).

UM DONO DO AMOSTRADOR
=====================
O medidor de ar (``MedidorDeAr(janela_s=0.25)``) mora AQUI, e o ``state_full``
lê a amostra dele (:meth:`GovernadorDoRadio.ultima_amostra`) em vez de manter
um segundo medidor. No modo falso (a suíte, o smoke) o medidor não nasce, e
nada pergunta ao rádio de ninguém.

QUEM O LIGA
===========
O ``AltoFalanteSubsystem``, que é o dono das pontes: ele pede a vaga antes de
subir a ponte e a entrega a ela; a ponte diz ao governador quando subiu e
quando desceu (é o que o diário conta, e o que o ``storm_doctor`` lê no
instante de cada queda).

OS CINCO ACERTOS DA CONFERÊNCIA (GOVERNADOR-DO-RADIO-02, 23/09/2026)
====================================================================
1. **«Ligar aqui» vale enquanto a ponte estiver de pé.** A R3 é *sempre pedir
   mover*: a resposta dela autoriza AQUELA ponte, e quando ela desce a próxima
   subida no adaptador cheio pergunta de novo. Uma vaga que nunca subiu não
   gasta a resposta — ela respondeu e a ponte ainda não esteve no ar.
2. **A marca «além do limite» sai quando o adaptador volta a caber.** A cada
   descida, as :attr:`GovernadorDoRadio.n_max` primeiras vagas do adaptador,
   na ordem em que chegaram, cabem; só o resto segue marcado.
3. **Num 2B longo, a religação espera cada vez mais** — 5, 10, 20, 40 e 60 s
   (:data:`TETO_DA_ESPERA_DA_FILA_S`), e volta a 5 s quando a fila ANDA
   (:meth:`GovernadorDoRadio._a_fila_andou`). O diário diz a ESPERA, uma linha
   por degrau e uma quando a fila volta a andar; as tentativas do meio são
   contadas, não escritas.
4. **A frase da recusa diz o NOME, nunca o endereço.** O adaptador é dito como
   a tela o diz — «Entrada 4.1.4» —, por :func:`nome_da_porta`, que pergunta
   aos donos de hoje. Sem nome, a frase diz «este adaptador».
5. **Ponte fantasma não conta.** O daemon que morre sem ``stop()`` deixa no
   diário ``PONTE_SUBIU`` sem ``PONTE_DESCEU``. No arranque o governador fecha
   essas pontes com :data:`MOTIVO_DO_REINICIO`
   (:meth:`GovernadorDoRadio.fechar_as_pontes_fantasmas`). Ele é o único que
   escreve ponte no diário, e é por isso que o fecho é dele: o
   ``pontes_de_pe`` continua uma dobra pura de SUBIU e DESCEU, e todo leitor do
   diário — o sino, o ``storm_doctor``, quem vier — lê a mesma verdade sem
   precisar saber quando o daemon subiu.
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.integrations import diario_do_radio as diario
from hefesto_dualsense4unix.integrations.alto_falante_bt import TETO_DE_CEDER_S
from hefesto_dualsense4unix.integrations.ar_do_adaptador import (
    ADAPTADOR_DESLIGADO,
    ADAPTADOR_SUMIU,
    IOCTL_FALHOU,
    SEM_BLUETOOTH,
)
from hefesto_dualsense4unix.integrations.radio_da_mesa import N_MAX_PONTES
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: De quanto em quanto tempo o governador olha o ar. É a janela do medidor:
#: 250 ms são ~23 quadros de uma ponte.
PERIODO_S = 0.25

#: Acima disto (pacotes na fila do host) as pontes do adaptador cedem. ~200 ms
#: de uma ponte: sem o patch do bluetoothd, o socket de uma ponte enche em
#: ~1,8 s de crédito parado (estudo de 23/09, críticos) e o primeiro EAGAIN
#: derruba o controle — o governador tem de ceder na primeira janela.
LIMIAR_DO_DEFICIT = 20

#: Abaixo disto as pontes voltam a escrever. A metade do limiar: sem folga, o
#: governador alternaria ceder e escrever a cada janela sobre um adaptador que
#: escoa no limite.
FOLGA_PARA_VOLTAR = 10

#: Quanto um adaptador que parou de escoar espera antes de aceitar ponte de
#: novo. Uma volta do subsystem do som (``RECONCILIA_S``): a tentativa seguinte
#: é a prova de que ele voltou a drenar.
ESPERA_DA_FILA_PARADA_S = 5.0

#: O teto da espera crescente — GOVERNADOR-DO-RADIO-02. Cada queda seguida pela
#: fila parada dobra a espera a partir de :data:`ESPERA_DA_FILA_PARADA_S`
#: (5 → 10 → 20 → 40 → 60 s), e ela fica aqui até a fila andar. Sem teto a
#: religação de um 2B de horas viraria «nunca»; sem crescer, ela era uma
#: tentativa a cada 7 a 12 s, com ~4 linhas de diário por volta.
TETO_DA_ESPERA_DA_FILA_S = 60.0

#: Escritas aceitas pelo kernel que provam que a fila ANDA: o dobro da fila do
#: ``/dev/uhid`` (``UHID_BUFSIZE`` = 32, ``assets/dkms/uhid/uhid.c``). Com o
#: uhid que devolve ``EAGAIN`` de fila cheia, só o ``bluetoothd`` lendo deixa
#: uma ponte passar disso. É a prova que vale sem o medidor de ar; com ele, a
#: janela medida (:meth:`GovernadorDoRadio._medir`) chega antes.
ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA = 64

#: De quanto em quanto tempo um episódio de ceder entra no diário, por
#: adaptador. CONFERÊNCIA DE 23/09/2026: só a borda não bastava. Três pontes
#: num adaptador que escoa duas (a R4, que é o caso deste governador) alternam
#: ceder e voltar a cada janela — medido no dublê, 240 linhas por minuto, e o
#: diário de meio mega girava em minutos, levando junto o ``PONTE_SUBIU`` que o
#: ``storm_doctor.o_fato_da_queda`` precisa e as frases dos outros motores. O
#: episódio que não entra é CONTADO, e a próxima linha diz quantos foram.
INTERVALO_DAS_BORDAS_NO_DIARIO_S = 60.0

#: Um pedido que a tela não respondeu e que ninguém renovou some. O subsystem
#: renova a cada volta enquanto há som esperando; sem som, a pergunta perde o
#: sentido.
VALIDADE_DO_PEDIDO_S = 15.0

#: Uma vaga que não virou ponte neste tempo foi esquecida por quem pediu (uma
#: exceção entre o pedido e a subida). O governador a recolhe, para ela não
#: ocupar o adaptador para sempre.
PRAZO_PARA_SUBIR_S = 30.0

#: Os dois tipos que o diário conhece (``diario_do_radio.PONTE_SUBIU``).
TIPO_SOM = "som"
TIPO_VIBRACAO = "vibracao"

#: Quem escreve no diário.
QUEM = "governador"

# --- o vocabulário do governador no diário ---------------------------------
#: A terceira ponte pediu vaga num adaptador cheio, e há vaga em outro.
ADAPTADOR_CHEIO = "adaptador cheio"
#: As pontes do adaptador começaram a ceder na fonte (a borda de subida).
CEDEU_NA_FONTE = "cedeu na fonte"
#: E voltaram a escrever (a borda de descida).
VOLTOU_A_ESCREVER = "voltou a escrever"
#: Ceder passou do teto: o adaptador não escoa. A FAMÍLIA DEPENDE DE QUEM
#: MEDIU, e é o que :meth:`GovernadorDoRadio._fila_parada` escreve:
#:
#: * ``pelo="kernel"`` — o ``uhid`` com contrapressão devolveu ``EAGAIN`` por
#:   mais que o teto: a fila do ``/dev/uhid`` cheia é o ``bluetoothd`` sem ler,
#:   a família 2B, e é isso que o diário diz;
#: * ``pelo="governador"`` — o ``acl_tx`` não andou. Isso não separa o
#:   ``bluetoothd`` parado (2B) do controlador sem devolver crédito (o regime
#:   que antecede o 2A): o diário diz o que foi medido, o adaptador que não pôs
#:   no ar, na família 2 (enlace parado). Conferência de 23/09/2026: esta linha
#:   dizia «Família 2B» para os dois, e o ramo do governador afirmava o
#:   ``bluetoothd`` sem ter olhado para ele.
FILA_PARADA = "fila parada"
#: O adaptador que parou de escoar voltou a pôr no ar: acaba a espera
#: crescente, e o diário diz quantas tentativas ficaram caladas no meio.
FILA_ANDOU = "fila voltou a andar"

#: O ``por_que`` do ``PONTE_DESCEU`` que o arranque escreve pela ponte que o
#: daemon anterior deixou de pé no diário ao morrer sem ``stop()``.
MOTIVO_DO_REINICIO = "o daemon reiniciou"

#: Os motivos de uma :class:`Recusa`.
MOTIVO_CHEIO = "cheio"
MOTIVO_PARADO = "parado"

#: O que o medidor diz quando o adaptador não pode receber ponte — não é
#: «vaga», por mais que ele não tenha ponte nenhuma.
_ADAPTADOR_FORA = frozenset({ADAPTADOR_DESLIGADO, ADAPTADOR_SUMIU, IOCTL_FALHOU, SEM_BLUETOOTH})

#: A frase do adaptador que parou de escoar — a mesma na recusa e no diário.
FRASE_DA_FILA_PARADA = "Este adaptador parou de enviar. O som volta sozinho."

#: A palavra da tela para o lugar de um adaptador — a do desenho aprovado
#: (``mockup/mapa-do-radio.html``: ``'Entrada ' + lug.entrada``) e a da
#: decisão ``D-A-PALAVRA-ENTRADA``: «Entrada», nunca «porta».
PALAVRA_DA_ENTRADA = "Entrada"

#: Um endereço de rádio em qualquer grafia com dois-pontos. A frase de tela
#: NUNCA o leva (GOVERNADOR-DO-RADIO-02): um nome que vier com ele é «não sei».
_ENDERECO_DE_RADIO = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{2}(?::[0-9a-f]{2}){5}(?![0-9a-f])")


def nome_da_porta(endereco: str, *, amostra: Mapping[str, Any] | None = None) -> str:
    """O nome que a tela dá a este adaptador — «Entrada 4.1.4» —, ou ``""``.

    GOVERNADOR-DO-RADIO-02, item 4. O governador não inventa nome: ele pergunta
    aos donos que já existem, e a regra de composição é a do desenho aprovado
    (``'Entrada ' + lug.entrada``):

    * o ``hciN`` do endereço é o do KERNEL — a amostra do medidor de ar, que já
      traz ``hci`` e ``endereco`` da mesma leitura, e, sem ela,
      ``bluez_dbus.enderecos_pelo_kernel`` (o mesmo ioctl);
    * o lugar do ``hciN`` é o do ``mesa_de_radio.adaptadores_bluetooth`` — o
      ``devpath`` e o caminho de barramento;
    * se ELA declarou aquela entrada no mapa do gabinete, o número é o dela
      (``mapa_das_portas.porta_de``, o dono de «em qual entrada está este
      caminho»); senão, o ``devpath``, como no desenho.

    ``""`` é «não sei»: adaptador embutido (sem USB), endereço que o kernel não
    conhece, ou a suíte no ar — que não lê a mesa dela por aqui. Quem chama
    diz «este adaptador», nunca o endereço.

    QUANDO A ENTRADA-A-ENTRADA-01 DER NOME À PORTA (o arquivo chaveado pelo
    lugar, com a tradução em ``utils/maquina.py``), é ESTA a função que passa a
    perguntar a ela. Um lugar só a mudar.
    """
    try:
        from hefesto_dualsense4unix.integrations import bluez_dbus

        if not endereco or bluez_dbus.a_suite_esta_rodando():
            return ""
        alvo = endereco.lower()
        interface = ""
        for leitura in (amostra or {}).values():
            if str(getattr(leitura, "endereco", "") or "").lower() == alvo:
                hci = getattr(leitura, "hci", None)
                if isinstance(hci, int) and not isinstance(hci, bool):
                    interface = f"hci{hci}"
                break
        if not interface:
            pelo_kernel = bluez_dbus.enderecos_pelo_kernel() or {}
            interface = next(
                (h for h, e in sorted(pelo_kernel.items()) if str(e).lower() == alvo), ""
            )
        if not interface:
            return ""
        from hefesto_dualsense4unix.integrations.mesa_de_radio import adaptadores_bluetooth

        lugar = next((a for a in adaptadores_bluetooth() if a.interface == interface), None)
        if lugar is None or not lugar.devpath:
            return ""
        from hefesto_dualsense4unix.integrations.mapa_das_portas import porta_de
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina

        numero = porta_de(carregar_maquina().mapa, lugar.caminho)
        return f"{PALAVRA_DA_ENTRADA} {numero or lugar.devpath}"
    except Exception:  # o nome nunca derruba a recusa: sem ele, «este adaptador»
        logger.debug("governador_nome_da_porta_ilegivel", exc_info=True)
        return ""


def _o_lugar(nome: str, *, com_em: bool = False, maiuscula: bool = False) -> str:
    """O nome com o artigo do desenho (``comoSeChamaOLugar``): «a Entrada 4.1.4»,
    e «o <nome>» para o nome que ela deu. ``com_em`` contrai: «na», «no»."""
    feminino = nome.startswith(PALAVRA_DA_ENTRADA + " ")
    artigo = ("na" if feminino else "no") if com_em else ("a" if feminino else "o")
    if maiuscula:
        artigo = artigo[:1].upper() + artigo[1:]
    return f"{artigo} {nome}"


def _chave(uniq: str) -> str:
    """O ``uniq`` só em hex minúsculo — a mesma chave do ``state_full``."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or str(uniq or "").lower()


def _nenhum_diario() -> list[dict[str, Any]]:
    """O leitor do governador de régua: não há diário dela para ler."""
    return []


def _tipo(tipo: str) -> str:
    """``som`` ou ``vibracao`` — o subsystem diz ``haptica``, o diário não."""
    return TIPO_VIBRACAO if tipo in ("haptica", "háptica", TIPO_VIBRACAO) else TIPO_SOM


def _adaptador_pelo_hid_phys(uniq: str) -> str:
    """O endereço do adaptador do controle, pelo ``HID_PHYS`` — ``""`` = não sei.

    A raiz do sysfs é a MESMA da varredura do som e do microfone
    (``dualsense_bt_audio._SYSFS_HIDRAW``), lida na CHAMADA: é ela que a suíte
    aponta para o vazio, e um default resolvido no import leria o hidraw da
    mesa dela no meio de um teste.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio
    from hefesto_dualsense4unix.integrations.radio_da_mesa import adaptador_por_uniq

    raiz = str(getattr(dualsense_bt_audio, "_SYSFS_HIDRAW", "") or "/sys/class/hidraw")
    return adaptador_por_uniq([uniq], raiz=raiz).get(uniq, "")


@dataclass(eq=False)
class Vaga:
    """A licença de UMA ponte para escrever num adaptador.

    A bomba lê :attr:`cedendo` e :attr:`derrubar` a cada quadro e chama
    :meth:`contar_escrita` a cada escrita aceita; a ponte chama :meth:`subiu` e
    :meth:`soltar`. Os campos que a bomba lê são escritos só pelo governador, e
    :attr:`escritas` só pela bomba — um escritor por campo, sem trava no
    caminho de 93,75 quadros por segundo.
    """

    uniq: str
    adaptador: str
    tipo: str
    alem_do_limite: bool = False
    #: «Além do limite» porque ELA respondeu «Ligar aqui» (R3 → R4), e não
    #: porque não havia vaga em outro adaptador (R4 sozinha). O diário não
    #: pode atribuir a ela uma escolha que ela não fez.
    por_escolha_dela: bool = False
    pedida_em: float = 0.0
    #: Escritas aceitas pelo kernel — o lado «nosso» do déficit.
    escritas: int = 0
    #: O governador mandou ceder na fonte.
    cedendo: bool = False
    #: O governador mediu o adaptador parado além do teto: a ponte cai.
    derrubar: bool = False
    subiu_em: float | None = None
    solta: bool = False
    _vistas: int = 0
    #: Subiu durante a espera crescente de uma fila parada (item 3 da
    #: GOVERNADOR-DO-RADIO-02): é uma TENTATIVA, e o ``PONTE_SUBIU`` dela só vai
    #: ao diário se a fila andar. Calada na subida, calada na descida — o par
    #: SUBIU/DESCEU nunca fica pela metade.
    _calada: bool = False
    _dono: Any = field(default=None, repr=False)

    def contar_escrita(self) -> None:
        self.escritas += 1
        # A PROVA DE QUE A FILA ANDA, pelo kernel: uma vez por vaga, no número
        # exato — uma comparação por quadro, e nada mais no caminho da bomba.
        if self.escritas == ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA and self._dono is not None:
            try:
                self._dono._a_fila_andou(self.adaptador)
            except Exception:  # o governador nunca derruba a bomba
                logger.debug("governador_fila_andou_falhou", exc_info=True)

    def subiu(self, tipo: str | None = None) -> None:
        """A ponte está no ar. Registra :data:`diario_do_radio.PONTE_SUBIU`."""
        if self._dono is not None:
            self._dono._subiu(self, tipo)

    def soltar(self, por_que: str = "a ponte desceu") -> None:
        """A ponte saiu do ar. Idempotente."""
        if self._dono is not None:
            self._dono._soltar(self, por_que)

    def fila_parada(self, cedendo_s: float) -> None:
        """A bomba bateu no teto da fila cheia do kernel."""
        if self._dono is not None:
            self._dono._fila_parada(self.adaptador, [self], cedendo_s, pelo="kernel")


@dataclass(frozen=True)
class Recusa:
    """A ponte não sobe agora. ``vagas`` são os adaptadores onde caberia.

    ``adaptador`` e ``vagas`` são ENDEREÇOS: dado para quem chama (a tela
    endereça o pedido por eles). A :attr:`frase` não os leva — ela pergunta o
    nome a ``nomear`` (GOVERNADOR-DO-RADIO-02, item 4), na hora em que é lida.
    """

    uniq: str
    adaptador: str
    tipo: str
    motivo: str
    vagas: tuple[str, ...] = ()
    n_max: int = N_MAX_PONTES
    #: Quem diz o nome de tela de um adaptador (:func:`nome_da_porta`).
    #: ``None`` = ninguém: a frase diz «este adaptador».
    nomear: Callable[[str], str] | None = field(default=None, repr=False, compare=False)

    def nome_de(self, endereco: str) -> str:
        """O nome de tela deste adaptador, ou ``""``. NUNCA o endereço: um nome
        que traga um endereço de rádio é «não sei», venha de quem vier."""
        if self.nomear is None or not endereco:
            return ""
        try:
            nome = str(self.nomear(endereco) or "").strip()
        except Exception:  # o nome nunca derruba a recusa
            return ""
        if not nome or _ENDERECO_DE_RADIO.search(nome):
            return ""
        return nome

    @property
    def frase(self) -> str:
        """O que a tela diz — curto, sem culpa, e só o que foi medido.

        As palavras são as da pergunta do desenho aprovado (R3): «A Entrada
        4.1.4 já tem 2 controles com som ou vibração.» E a vaga, pelo nome.
        """
        if self.motivo == MOTIVO_PARADO:
            return FRASE_DA_FILA_PARADA
        nome = self.nome_de(self.adaptador)
        sujeito = _o_lugar(nome, maiuscula=True) if nome else "Este adaptador"
        cheio = f"{sujeito} já tem {self.n_max} controles com som ou vibração."
        onde = [_o_lugar(n, com_em=True) for n in dict.fromkeys(map(self.nome_de, self.vagas)) if n]
        if onde:
            juntos = onde[0] if len(onde) == 1 else f"{', '.join(onde[:-1])} e {onde[-1]}"
            return f"{cheio} Há vaga {juntos}."
        if self.vagas:
            return f"{cheio} Há vaga em outro adaptador."
        return cheio


@dataclass
class _Estado:
    """O que o governador sabe de UM adaptador entre dois tiques."""

    fila: float = 0.0
    cedendo: bool = False
    cedendo_desde: float | None = None
    #: Segundos de janela MEDIDA em que as pontes seguiram cedendo — o relógio
    #: do teto. Janela de «não sei» não soma: ela não mediu parada nenhuma.
    cedendo_medido_s: float = 0.0
    #: O episódio de agora entrou no diário? O «voltou» só entra se o «cedeu»
    #: entrou (:data:`INTERVALO_DAS_BORDAS_NO_DIARIO_S`).
    episodio_escrito: bool = False
    ultimo_ar: Any = None
    deficit_medido: bool = False


@dataclass
class _BordasNoDiario:
    """Quando a última borda de um adaptador entrou no diário, e quantos
    episódios ficaram calados desde então. Fora do :class:`_Estado` de
    propósito: o estado sai quando o adaptador fica sem ponte, e a ponte que
    cai e religa não pode zerar a conta do diário a cada volta."""

    escrita_em: float | None = None
    calados: int = 0


@dataclass
class _Pedido:
    uniq: str
    tipo: str
    adaptador: str
    vagas: tuple[str, ...]
    renovado_em: float


@dataclass
class _EpisodioDaFila:
    """Um adaptador que parou de escoar e ainda não provou que voltou a andar.

    Fora do :class:`_Estado` pelo mesmo motivo do :class:`_BordasNoDiario`: o
    estado sai quando o adaptador fica sem ponte — e é exatamente isso que a
    fila parada faz com ele a cada tentativa.
    """

    espera_s: float
    desde: float
    tentativas: int = 0


class GovernadorDoRadio:
    """Admissão por adaptador e contrapressão pelo contador ``acl_tx``.

    Tudo é injetável — o medidor, o relógio, o diário e quem diz o adaptador —
    e a suíte não toca rádio, sysfs nem o diário dela.
    """

    def __init__(
        self,
        *,
        medidor: Any = None,
        n_max: int = N_MAX_PONTES,
        adaptador_de: Callable[[str], str] | None = None,
        registrar: Callable[..., Any] | None = None,
        relogio: Callable[[], float] = time.monotonic,
        periodo_s: float = PERIODO_S,
        nomear: Callable[[str], str] | None = None,
        ler_o_diario: Callable[[], Iterable[dict[str, Any]]] | None = None,
    ) -> None:
        self._medidor = medidor
        self.n_max = int(n_max)
        self._adaptador_de = adaptador_de or _adaptador_pelo_hid_phys
        self._registrar = registrar or diario.registrar
        self._relogio = relogio
        self._periodo_s = periodo_s
        #: Quem diz o nome de tela de um adaptador (item 4). O padrão pergunta
        #: aos donos, com a amostra DESTE governador — o ``hciN`` já lido.
        self._nomear: Callable[[str], str] = nomear or (
            lambda endereco: nome_da_porta(endereco, amostra=self.ultima_amostra())
        )
        #: Quem lê o diário no arranque (item 5). O MESMO diário em que
        #: ``registrar`` escreve: com ``registrar`` injetado e sem leitor, não
        #: há o que fechar — um governador de régua nunca lê o diário dela.
        if ler_o_diario is not None:
            self._ler_o_diario: Callable[[], Iterable[dict[str, Any]]] = ler_o_diario
        elif registrar is None:
            self._ler_o_diario = diario.ler
        else:
            self._ler_o_diario = _nenhum_diario
        self._fantasmas_fechadas = False
        self._trava = threading.RLock()
        self._vagas: list[Vaga] = []
        self._estados: dict[str, _Estado] = {}
        self._pedidos: dict[str, _Pedido] = {}
        #: ``(chave do controle, adaptador)`` que ela mandou «Ligar aqui». Sai
        #: quando a ponte daquele controle naquele adaptador DESCE (item 1).
        self._autorizados: set[tuple[str, str]] = set()
        self._parado_ate: dict[str, float] = {}
        #: A espera crescente de cada adaptador que parou de escoar (item 3).
        self._episodios: dict[str, _EpisodioDaFila] = {}
        self._bordas_no_diario: dict[str, _BordasNoDiario] = {}
        self._amostra: dict[str, Any] | None = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        #: Quem quer saber que ela respondeu «Ligar aqui» — o subsystem do
        #: som, para acordar a volta em vez de esperar os cinco segundos dela.
        self.ao_autorizar: Callable[[str], None] | None = None

    # -- o medidor, que é um só ----------------------------------------------

    @classmethod
    def de_producao(cls) -> GovernadorDoRadio:
        """O governador do daemon: com o medidor de ar, fora do modo falso."""
        from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

        medidor = None
        if not fake_mode_enabled():
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import MedidorDeAr

            medidor = MedidorDeAr(janela_s=PERIODO_S)
        return cls(medidor=medidor)

    def ultima_amostra(self) -> dict[str, Any] | None:
        """``{endereço: ArDoAdaptador}`` da última janela — ``None`` = não medi."""
        with self._trava:
            return None if self._amostra is None else dict(self._amostra)

    def iniciar(self) -> None:
        """Sobe o tique numa thread — que, antes do primeiro tique, fecha as
        pontes fantasmas (:meth:`fechar_as_pontes_fantasmas`).

        Na thread, e não aqui: quem chama é o ``start()`` assíncrono do som, e
        ler dois diários de meio mega seguraria o laço de eventos do daemon.

        Sem medidor não há o que medir — e não há o que fechar: sem medidor é o
        modo falso (a suíte, o smoke), e um daemon de mentira rodando ao lado do
        dela veria as pontes VIVAS do dela como fantasmas.
        """
        if self._medidor is None:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._laco, name="hefesto-governador", daemon=True
        )
        self._thread.start()
        logger.info("governador_do_radio_iniciado", n_max=self.n_max)

    def parar(self, esperar_s: float = 1.0) -> None:
        self._parar.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=esperar_s)

    def _laco(self) -> None:
        try:
            self.fechar_as_pontes_fantasmas()
        except Exception:  # o arranque nunca derruba o governador
            logger.debug("governador_fantasmas_falhou", exc_info=True)
        while not self._parar.wait(self._periodo_s):
            try:
                self.tique()
            except Exception:  # o governador nunca derruba o daemon
                logger.debug("governador_tique_falhou", exc_info=True)

    # -- o arranque: a ponte fantasma não conta (item 5) ----------------------

    def fechar_as_pontes_fantasmas(self) -> int:
        """``PONTE_DESCEU`` «o daemon reiniciou» por ponte que o diário diz de pé
        e que este governador não tem. Uma vez por governador; devolve quantas.

        O daemon que morre sem ``stop()`` (um ``SIGKILL``, a sessão que caiu)
        não escreve o ``PONTE_DESCEU``, e o ``diario_do_radio.pontes_de_pe``
        passaria a contar, no fato de toda queda seguinte, pontes que não
        existem. POR QUE AQUI, E NÃO NO LEITOR: o governador é o único escritor
        de ponte no diário. Fechando no arranque, o diário diz a verdade e o
        ``pontes_de_pe`` segue uma dobra pura de SUBIU e DESCEU — o sino, o
        ``storm_doctor`` e quem vier leem a mesma coisa. Ensinar o leitor a
        ignorar o que veio antes do arranque daria a cada leitor a MESMA regra
        para repetir, e o diário continuaria dizendo que a ponte está de pé.
        """
        with self._trava:
            if self._fantasmas_fechadas:
                return 0
            self._fantasmas_fechadas = True
        try:
            de_pe = diario.pontes_de_pe(list(self._ler_o_diario()), math.inf)
        except Exception:  # diário ilegível: não há o que fechar, e o daemon sobe
            logger.debug("governador_diario_ilegivel_no_arranque", exc_info=True)
            return 0
        # AS NOSSAS SÃO LIDAS DEPOIS DO DIÁRIO: a ponte que subir no meio marca o
        # ``subiu_em`` ANTES de escrever o SUBIU, então toda subida nova que a
        # leitura viu já está aqui. E a chave é a do ``pontes_de_pe`` — o texto
        # do ``controle`` como foi escrito, não os dígitos: uma subida velha
        # grafada de outro jeito é OUTRA ponte para o leitor, e ficaria de pé.
        with self._trava:
            nossas = {(v.uniq, v.tipo) for v in self._vagas if v.subiu_em is not None}
        fechadas = 0
        for adaptador, pontes in sorted(de_pe.items()):
            for controle, tipo in sorted(pontes):
                if (controle, tipo) in nossas:
                    continue
                self._escrever(
                    diario.PONTE_DESCEU,
                    MOTIVO_DO_REINICIO,
                    adaptador=adaptador or None,
                    controle=controle,
                    tipo=tipo,
                )
                fechadas += 1
        if fechadas:
            logger.info("governador_fechou_pontes_fantasmas", pontes=fechadas)
        return fechadas

    # -- a admissão ----------------------------------------------------------

    def _adaptadores_com_vaga(self, exceto: str) -> tuple[str, ...]:
        """Os adaptadores de pé onde uma ponte a mais ainda cabe."""
        conhecidos: set[str] = {v.adaptador for v in self._vagas if v.adaptador}
        for endereco, ar in (self._amostra or {}).items():
            if endereco and str(getattr(ar, "motivo", "") or "") not in _ADAPTADOR_FORA:
                conhecidos.add(endereco)
        agora = self._relogio()
        livres = [
            endereco
            for endereco in sorted(conhecidos)
            if endereco != exceto
            and self._parado_ate.get(endereco, 0.0) <= agora
            and sum(1 for v in self._vagas if v.adaptador == endereco) < self.n_max
        ]
        return tuple(livres)

    def pedir_vaga(self, uniq: str, tipo: str) -> Vaga | Recusa:
        """Uma vaga para a ponte deste controle, ou a :class:`Recusa` dita."""
        adaptador = ""
        try:
            adaptador = str(self._adaptador_de(uniq) or "").lower()
        except Exception:  # sysfs some sob a mão: é «não sei»
            logger.debug("governador_adaptador_ilegivel", uniq=uniq, exc_info=True)
        tipo = _tipo(tipo)
        chave = _chave(uniq)
        agora = self._relogio()
        with self._trava:
            self._recolher(agora)
            if not adaptador:
                # Sem casa não há adaptador a proteger: a ponte sobe como
                # sempre subiu, e o diário a conta sem adaptador.
                return self._conceder(uniq, "", tipo, alem=False, agora=agora)
            if self._parado_ate.get(adaptador, 0.0) > agora:
                return Recusa(uniq, adaptador, tipo, MOTIVO_PARADO)
            ocupadas = [
                v for v in self._vagas if v.adaptador == adaptador and _chave(v.uniq) != chave
            ]
            if len(ocupadas) < self.n_max:
                self._pedidos.pop(chave, None)
                return self._conceder(uniq, adaptador, tipo, alem=False, agora=agora)
            vagas = self._adaptadores_com_vaga(exceto=adaptador)
            autorizado = (chave, adaptador) in self._autorizados
            if autorizado or not vagas:
                # R4: ela escolheu «Ligar aqui», ou não há para onde mover.
                self._pedidos.pop(chave, None)
                vaga = self._conceder(uniq, adaptador, tipo, alem=True, agora=agora)
                vaga.por_escolha_dela = autorizado
                return vaga
            recusa = Recusa(
                uniq, adaptador, tipo, MOTIVO_CHEIO, vagas, n_max=self.n_max, nomear=self._nomear
            )
            anterior = self._pedidos.get(chave)
            self._pedidos[chave] = _Pedido(uniq, tipo, adaptador, vagas, agora)
            pergunta_nova = anterior is None or anterior.adaptador != adaptador
            ocupadas_n = len(ocupadas)
        # O diário e o NOME saem FORA da trava: a frase pergunta o nome aos donos
        # (sysfs, o mapa dela), e o tique não espera por isso.
        if pergunta_nova:
            self._escrever(
                ADAPTADOR_CHEIO,
                f"a ponte número {ocupadas_n + 1} pediu vaga num adaptador "
                f"que comporta {self.n_max}",
                antes={"pontes": ocupadas_n},
                depois={"vagas": list(vagas)},
                adaptador=adaptador,
                controle=uniq,
                tipo=tipo,
                frase=recusa.frase,
            )
            logger.info(
                "governador_adaptador_cheio",
                adaptador=adaptador,
                uniq=uniq,
                vagas=list(vagas),
            )
        return recusa

    def _conceder(
        self, uniq: str, adaptador: str, tipo: str, *, alem: bool, agora: float
    ) -> Vaga:
        vaga = Vaga(
            uniq=uniq,
            adaptador=adaptador,
            tipo=tipo,
            alem_do_limite=alem,
            pedida_em=agora,
            _dono=self,
        )
        estado = self._estados.get(adaptador)
        if estado is not None and estado.cedendo:
            vaga.cedendo = True
        self._vagas.append(vaga)
        return vaga

    def ligar_aqui(self, uniq: str) -> bool:
        """«Ligar aqui» (R3 → R4): a próxima ponte deste controle sobe além do limite.

        Vale para o controle NESTE adaptador, e ENQUANTO A PONTE ESTIVER DE PÉ
        (GOVERNADOR-DO-RADIO-02, item 1): quando ela desce, a próxima subida
        naquele adaptador cheio pergunta de novo — a R3 é *sempre pedir mover*.
        Movido, a pergunta volta no adaptador novo. ``False`` = o adaptador
        dele não se lê.
        """
        chave = _chave(uniq)
        with self._trava:
            pedido = self._pedidos.pop(chave, None)
        adaptador = pedido.adaptador if pedido is not None else ""
        if not adaptador:
            try:
                adaptador = str(self._adaptador_de(uniq) or "").lower()
            except Exception:
                adaptador = ""
        if not adaptador:
            return False
        with self._trava:
            self._autorizados.add((chave, adaptador))
        logger.info("governador_ligar_aqui", uniq=uniq, adaptador=adaptador)
        avisar = self.ao_autorizar
        if avisar is not None:
            try:
                avisar(uniq)
            except Exception:  # quem escuta nunca desfaz a resposta dela
                logger.debug("governador_aviso_falhou", uniq=uniq, exc_info=True)
        return True

    # -- a ponte diz: subiu, desceu ------------------------------------------

    def _subiu(self, vaga: Vaga, tipo: str | None) -> None:
        with self._trava:
            if vaga.solta or vaga.subiu_em is not None:
                return
            if tipo:
                vaga.tipo = _tipo(tipo)
            vaga.subiu_em = self._relogio()
            episodio = self._episodios.get(vaga.adaptador) if vaga.adaptador else None
            if episodio is not None:
                # UMA TENTATIVA DURANTE A ESPERA CRESCENTE (item 3): contada, não
                # escrita. Se a fila andar, o `_a_fila_andou` escreve a subida.
                vaga._calada = True
                episodio.tentativas += 1
                logger.debug(
                    "governador_tentativa", adaptador=vaga.adaptador, n=episodio.tentativas
                )
                return
            no_adaptador = self._pontes_no_adaptador(vaga.adaptador)
        self._escrever_a_subida(vaga, no_adaptador)

    def _pontes_no_adaptador(self, adaptador: str) -> int:
        """Quantas vagas o adaptador tem agora. Chamado com a trava."""
        return sum(1 for v in self._vagas if v.adaptador == adaptador and v.adaptador)

    def _escrever_a_subida(self, vaga: Vaga, no_adaptador: int) -> None:
        """O ``PONTE_SUBIU`` de uma vaga — na subida, ou quando a fila andou."""
        campos: dict[str, Any] = {}
        if vaga.alem_do_limite:
            campos["alem_do_limite"] = True
            campos["frase"] = f"{no_adaptador} pontes num adaptador (limite {self.n_max})."
        if not vaga.alem_do_limite:
            por_que = "há som para mandar"
        elif vaga.por_escolha_dela:
            por_que = "ela ligou além do limite"
        else:
            por_que = "não há vaga em outro adaptador"
        self._escrever(
            diario.PONTE_SUBIU,
            por_que,
            depois={"pontes": no_adaptador},
            adaptador=vaga.adaptador or None,
            controle=vaga.uniq,
            tipo=vaga.tipo,
            **campos,
        )

    def _soltar(self, vaga: Vaga, por_que: str) -> None:
        with self._trava:
            if vaga.solta:
                return
            vaga.solta = True
            if vaga in self._vagas:
                self._vagas.remove(vaga)
            subiu = vaga.subiu_em is not None
            calada = vaga._calada
            if subiu:
                # ITEM 1: o «Ligar aqui» valia enquanto a ponte estava de pé. Ela
                # desceu: a próxima subida naquele adaptador cheio pergunta de
                # novo. A vaga que NUNCA subiu não gasta a resposta dela.
                self._autorizados.discard((_chave(vaga.uniq), vaga.adaptador))
            self._recalcular_o_limite(vaga.adaptador)
        if subiu and not calada:
            self._escrever(
                diario.PONTE_DESCEU,
                por_que,
                adaptador=vaga.adaptador or None,
                controle=vaga.uniq,
                tipo=vaga.tipo,
            )

    def _recalcular_o_limite(self, adaptador: str) -> None:
        """ITEM 2: a marca «além do limite» sai de quem voltou a caber.

        As :attr:`n_max` primeiras vagas do adaptador, na ordem em que chegaram,
        cabem; só as que passam delas seguem marcadas. Só TIRA a marca — quem a
        põe é a admissão. Sem isto a tela mostraria «além do limite» com 2 de 2.
        Chamado com a trava, a cada descida.
        """
        if not adaptador:
            return
        no_adaptador = [v for v in self._vagas if v.adaptador == adaptador]
        for vaga in no_adaptador[: self.n_max]:
            if vaga.alem_do_limite:
                vaga.alem_do_limite = False
                logger.info("governador_voltou_a_caber", adaptador=adaptador, uniq=vaga.uniq)

    def _recolher(self, agora: float) -> None:
        """Vagas esquecidas e pedidos velhos saem. Chamado com a trava."""
        esquecidas = [
            v
            for v in self._vagas
            if v.subiu_em is None and agora - v.pedida_em > PRAZO_PARA_SUBIR_S
        ]
        for vaga in esquecidas:
            vaga.solta = True
            self._vagas.remove(vaga)
            logger.debug("governador_vaga_esquecida", uniq=vaga.uniq)
        for adaptador in {v.adaptador for v in esquecidas}:
            self._recalcular_o_limite(adaptador)
        for chave in [
            c for c, p in self._pedidos.items() if agora - p.renovado_em > VALIDADE_DO_PEDIDO_S
        ]:
            self._pedidos.pop(chave, None)

    # -- o tempo real --------------------------------------------------------

    def tique(self) -> None:
        """Uma janela: amostra o ar e decide, por adaptador, ceder ou escrever."""
        amostra: dict[str, Any] | None = None
        if self._medidor is not None:
            try:
                amostra = {e: a for e, a in dict(self._medidor.amostrar()).items() if e}
            except Exception:  # medidor que falhou é «não sei», não zero
                logger.debug("governador_medidor_falhou", exc_info=True)
        agora = self._relogio()
        bordas: list[tuple[str, dict[str, Any]]] = []
        paradas: list[tuple[str, list[Vaga], float]] = []
        andaram: list[str] = []
        with self._trava:
            if amostra is not None:
                self._amostra = amostra
            self._recolher(agora)
            por_adaptador: dict[str, list[Vaga]] = {}
            for vaga in self._vagas:
                if vaga.adaptador and vaga.subiu_em is not None:
                    por_adaptador.setdefault(vaga.adaptador, []).append(vaga)
            for endereco in [e for e in self._estados if e not in por_adaptador]:
                self._estados.pop(endereco, None)
            for endereco, vagas in por_adaptador.items():
                estado = self._estados.setdefault(endereco, _Estado())
                ar = (amostra or {}).get(endereco)
                if self._medir(estado, vagas, ar, endereco, agora, bordas) and (
                    endereco in self._episodios
                ):
                    andaram.append(endereco)
                if estado.cedendo and estado.cedendo_medido_s > TETO_DE_CEDER_S:
                    paradas.append((endereco, list(vagas), estado.cedendo_medido_s))
        for o_que, dados in bordas:
            self._escrever(o_que, **dados)
        for endereco in andaram:
            self._a_fila_andou(endereco)
        for endereco, vagas, cedendo_s in paradas:
            self._fila_parada(endereco, vagas, cedendo_s, pelo="governador")

    def _medir(
        self,
        estado: _Estado,
        vagas: list[Vaga],
        ar: Any,
        endereco: str,
        agora: float,
        bordas: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        """O déficit de uma janela e as duas bordas. Chamado com a trava.

        Devolve ``True`` quando a janela MEDIDA provou que a fila ANDA: as
        pontes escreveram nela ao menos o :data:`LIMIAR_DO_DEFICIT` — o que
        faria o adaptador parado ceder — e a fila ficou na folga. Janela de
        «não sei» nunca prova nada.

        CONFERÊNCIA DE 23/09/2026: a prova era «um pacote no ar e as pontes sem
        ceder», e o contador é do ADAPTADOR inteiro. Num 2B com um fio de ar
        alheio (um pacote por janela), a primeira janela de cada tentativa —
        meia janela, dez escritas — passava por prova: 77 «fila voltou a andar»
        em dez minutos, e a espera nunca saiu dos 5 s, que é o defeito que a
        espera crescente existe para curar.
        """
        if ar is None or ar is estado.ultimo_ar:
            if ar is None:
                # «NÃO SEI»: as escritas desta janela não têm com o que se
                # comparar, e não viram déficit nem folga.
                for vaga in vagas:
                    vaga._vistas = vaga.escritas
                estado.deficit_medido = False
            return False
        estado.ultimo_ar = ar
        escritas = 0
        for vaga in vagas:
            escritas += vaga.escritas - vaga._vistas
            vaga._vistas = vaga.escritas
        saida = getattr(ar, "saida_por_s", None)
        janela = float(getattr(ar, "janela_s", 0.0) or 0.0)
        if saida is None or janela <= 0:
            estado.deficit_medido = False
            return False
        estado.deficit_medido = True
        estado.fila = max(0.0, estado.fila + escritas - float(saida) * janela)
        self._as_bordas(estado, vagas, endereco, agora, janela, bordas)
        return (
            escritas >= LIMIAR_DO_DEFICIT
            and estado.fila <= FOLGA_PARA_VOLTAR
            and not estado.cedendo
        )

    def _as_bordas(
        self,
        estado: _Estado,
        vagas: list[Vaga],
        endereco: str,
        agora: float,
        janela: float,
        bordas: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Ceder e voltar, pela fila da janela medida. Chamado com a trava."""
        if estado.cedendo and estado.fila > FOLGA_PARA_VOLTAR:
            # Seguiu cedendo numa janela MEDIDA: só esta anda o relógio do teto.
            estado.cedendo_medido_s += janela
        if not estado.cedendo and estado.fila > LIMIAR_DO_DEFICIT:
            estado.cedendo = True
            estado.cedendo_desde = agora
            estado.cedendo_medido_s = 0.0
            for vaga in vagas:
                vaga.cedendo = True
            diario_das_bordas = self._bordas_no_diario.setdefault(endereco, _BordasNoDiario())
            # Durante a espera crescente de uma fila parada (item 3), ceder é a
            # TENTATIVA falhando de novo: o diário já disse a espera, e a borda
            # é contada com os calados em vez de escrita.
            estado.episodio_escrito = endereco not in self._episodios and (
                diario_das_bordas.escrita_em is None
                or agora - diario_das_bordas.escrita_em >= INTERVALO_DAS_BORDAS_NO_DIARIO_S
            )
            if not estado.episodio_escrito:
                diario_das_bordas.calados += 1
                logger.debug("governador_cedeu", adaptador=endereco, fila=round(estado.fila))
                return
            calados, diario_das_bordas.calados = diario_das_bordas.calados, 0
            diario_das_bordas.escrita_em = agora
            logger.info(
                "governador_cedeu", adaptador=endereco, fila=round(estado.fila), calados=calados
            )
            bordas.append(
                (
                    CEDEU_NA_FONTE,
                    {
                        "por_que": "o adaptador não escoou o que as pontes escreveram",
                        "antes": {"fila": round(estado.fila), "episodios_calados": calados},
                        "adaptador": endereco,
                        "controles": sorted(v.uniq for v in vagas),
                    },
                )
            )
        elif estado.cedendo and estado.fila <= FOLGA_PARA_VOLTAR:
            estado.cedendo = False
            segundos = agora - (estado.cedendo_desde or agora)
            estado.cedendo_desde = None
            estado.cedendo_medido_s = 0.0
            for vaga in vagas:
                vaga.cedendo = False
            if not estado.episodio_escrito:
                logger.debug("governador_voltou", adaptador=endereco, segundos=round(segundos, 2))
                return
            estado.episodio_escrito = False
            logger.info("governador_voltou", adaptador=endereco, segundos=round(segundos, 2))
            bordas.append(
                (
                    VOLTOU_A_ESCREVER,
                    {
                        "por_que": "o adaptador escoou a fila",
                        "depois": {"cedeu_s": round(segundos, 3)},
                        "adaptador": endereco,
                    },
                )
            )

    def _fila_parada(
        self, adaptador: str, vagas: Iterable[Vaga], cedendo_s: float, *, pelo: str
    ) -> None:
        """Ceder passou do teto: as pontes caem e o adaptador espera.

        A ESPERA CRESCE a cada queda seguida (item 3 da GOVERNADOR-DO-RADIO-02):
        5, 10, 20, 40 e 60 s, até a fila andar (:meth:`_a_fila_andou`). O diário
        ganha uma linha por DEGRAU — a espera, não a tentativa; no teto, as
        tentativas seguem contadas e caladas.
        """
        vagas = list(vagas)
        agora = self._relogio()
        escrever = not adaptador  # sem casa não há espera: diz a cada queda, como antes
        espera_s, tentativas = ESPERA_DA_FILA_PARADA_S, 0
        with self._trava:
            ja_parado = self._parado_ate.get(adaptador, 0.0) > agora
            if adaptador and not ja_parado:
                episodio = self._episodios.get(adaptador)
                if episodio is None:
                    episodio = _EpisodioDaFila(espera_s=ESPERA_DA_FILA_PARADA_S, desde=agora)
                    self._episodios[adaptador] = episodio
                    escrever = True
                else:
                    anterior = episodio.espera_s
                    episodio.espera_s = min(anterior * 2, TETO_DA_ESPERA_DA_FILA_S)
                    escrever = episodio.espera_s != anterior
                self._parado_ate[adaptador] = agora + episodio.espera_s
                espera_s, tentativas = episodio.espera_s, episodio.tentativas
            estado = self._estados.get(adaptador)
            if estado is not None:
                estado.cedendo = False
                estado.cedendo_desde = None
                estado.cedendo_medido_s = 0.0
                estado.fila = 0.0
            for vaga in vagas:
                vaga.derrubar = True
                vaga.cedendo = False
        logger.warning(
            "governador_fila_parada",
            adaptador=adaptador,
            pelo=pelo,
            cedendo_s=round(cedendo_s, 3),
            espera_s=espera_s,
        )
        if not escrever:
            return
        onde = adaptador or "deste controle"
        if pelo == "kernel":
            por_que, familia = f"o bluetoothd não drena o adaptador {onde}", "2B"
        else:
            por_que = f"o adaptador {onde} não pôs no ar o que as pontes escreveram"
            familia = "2"
        depois: dict[str, Any] = {"cedeu_s": round(cedendo_s, 3), "pelo": pelo}
        if adaptador:
            depois["espera_s"] = espera_s
            depois["tentativas"] = tentativas
        self._escrever(
            FILA_PARADA,
            por_que,
            depois=depois,
            adaptador=adaptador or None,
            controles=sorted(v.uniq for v in vagas),
            familia=familia,
            frase=FRASE_DA_FILA_PARADA,
        )

    def _a_fila_andou(self, adaptador: str) -> None:
        """A fila do adaptador ANDA: acaba a espera crescente dele (item 3).

        Duas provas chegam aqui, e as duas são medida, nunca relógio: a janela do
        medidor em que as pontes escreveram o limiar e a fila ficou na folga
        (:meth:`_medir`), e a ponte que passou de
        :data:`ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA` escritas aceitas
        (:meth:`Vaga.contar_escrita`). A próxima queda volta a esperar 5 s.

        As tentativas que estão de pé ganham AGORA o ``PONTE_SUBIU`` que ficou
        calado: a ponte está no ar, e o fato de uma queda tem de contá-la.
        """
        if not adaptador:
            return
        agora = self._relogio()
        with self._trava:
            episodio = self._episodios.pop(adaptador, None)
            if episodio is None:
                return
            caladas = [
                v
                for v in self._vagas
                if v.adaptador == adaptador and v._calada and v.subiu_em is not None
            ]
            for vaga in caladas:
                vaga._calada = False
            no_adaptador = self._pontes_no_adaptador(adaptador)
        parada_s = round(agora - episodio.desde, 3)
        logger.info(
            "governador_fila_andou",
            adaptador=adaptador,
            tentativas=episodio.tentativas,
            parada_s=parada_s,
        )
        self._escrever(
            FILA_ANDOU,
            "o adaptador voltou a pôr no ar o que as pontes escrevem",
            antes={"espera_s": episodio.espera_s},
            depois={"tentativas": episodio.tentativas, "parada_s": parada_s},
            adaptador=adaptador,
        )
        for vaga in caladas:
            self._escrever_a_subida(vaga, no_adaptador)

    # -- o que a tela lê -----------------------------------------------------

    def publicar(self) -> dict[str, Any]:
        """``state_full["radio_governador"]``: o que o governador decidiu agora.

        Por adaptador: as pontes com a marca «além do limite», se está cedendo,
        se parou de escoar, e os pedidos que a tela tem de PERGUNTAR (R3).
        """
        agora = self._relogio()
        with self._trava:
            self._recolher(agora)
            enderecos = (
                {v.adaptador for v in self._vagas if v.adaptador}
                | {p.adaptador for p in self._pedidos.values()}
                | {e for e, ate in self._parado_ate.items() if ate > agora}
            )
            saida: dict[str, Any] = {}
            for endereco in sorted(enderecos):
                estado = self._estados.get(endereco)
                saida[endereco] = {
                    "n_max": self.n_max,
                    "pontes": [
                        {
                            "uniq": v.uniq,
                            "tipo": v.tipo,
                            "alem_do_limite": v.alem_do_limite,
                        }
                        for v in self._vagas
                        if v.adaptador == endereco and v.subiu_em is not None
                    ],
                    "cedendo": bool(estado and estado.cedendo),
                    "fila": (
                        round(estado.fila)
                        if estado is not None and estado.deficit_medido
                        else None
                    ),
                    "parado": self._parado_ate.get(endereco, 0.0) > agora,
                    "pedidos": [
                        {"uniq": p.uniq, "tipo": p.tipo, "vagas": list(p.vagas)}
                        for p in self._pedidos.values()
                        if p.adaptador == endereco
                    ],
                }
            return saida

    def _escrever(self, o_que: str, por_que: str = "", **campos: Any) -> None:
        try:
            self._registrar(QUEM, o_que, por_que, **campos)
        except Exception:  # o diário nunca derruba o governador
            logger.debug("governador_diario_falhou", o_que=o_que, exc_info=True)


__all__ = [
    "ADAPTADOR_CHEIO",
    "CEDEU_NA_FONTE",
    "ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA",
    "ESPERA_DA_FILA_PARADA_S",
    "FILA_ANDOU",
    "FILA_PARADA",
    "FOLGA_PARA_VOLTAR",
    "FRASE_DA_FILA_PARADA",
    "INTERVALO_DAS_BORDAS_NO_DIARIO_S",
    "LIMIAR_DO_DEFICIT",
    "MOTIVO_CHEIO",
    "MOTIVO_DO_REINICIO",
    "MOTIVO_PARADO",
    "PALAVRA_DA_ENTRADA",
    "PERIODO_S",
    "PRAZO_PARA_SUBIR_S",
    "QUEM",
    "TETO_DA_ESPERA_DA_FILA_S",
    "TIPO_SOM",
    "TIPO_VIBRACAO",
    "VALIDADE_DO_PEDIDO_S",
    "VOLTOU_A_ESCREVER",
    "GovernadorDoRadio",
    "Recusa",
    "Vaga",
    "nome_da_porta",
]
