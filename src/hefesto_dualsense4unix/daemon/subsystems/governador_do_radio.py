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

* há vaga em outro adaptador → :class:`Recusa` com a frase «A Entrada 3 já
  tem 2 controles com som ou vibração. Há vaga na Entrada 5.», e o pedido
  fica publicado para a tela PERGUNTAR (R3: sempre pedir mover). Ela escolhe
  «Ligar aqui» (:meth:`GovernadorDoRadio.ligar_aqui`) e a ponte sobe marcada
  «além do limite»;
* não há vaga em adaptador nenhum → a ponte sobe marcada «além do limite» e o
  diário diz o fato (R4: degrada e avisa). Nada é desligado;
* NÃO SEI se há vaga em outro adaptador (O-GOVERNADOR-COM-UM-ADAPTADOR-SO-01,
  28/09/2026) → :class:`Recusa` com :data:`MOTIVO_SEM_MEDIDA`, sem pedido
  publicado: a tela não pergunta nada, e a ponte espera a primeira janela do
  medidor, que acorda a volta do som (:attr:`GovernadorDoRadio.ao_autorizar`).
  «Não sei» é o daemon que acabou de subir (o medidor ainda sem amostra), o
  medidor que falhou, ou outro adaptador cuja leitura falhou. Passado
  :data:`TETO_DO_NAO_SEI_S` sem medida, vale a R4, e o diário diz «não sei se
  há vaga em outro adaptador» — nunca «não há», que seria um fato que ninguém
  mediu. Sem medidor (o modo falso) não há medida a esperar.

O TEMPO REAL, a cada :data:`PERIODO_S`
=====================================
O déficit é a FILA DO HOST crescendo: as escritas nossas aceitas pelo kernel
menos o que o adaptador pôs no ar (o Δ``acl_tx`` do ``ar_do_adaptador``, que só
sobe DEPOIS de haver crédito do controlador). Acima do limiar
(:data:`JANELAS_DO_LIMIAR` janelas de escrita de uma ponte, com
:data:`LIMIAR_DO_DEFICIT` pacotes de piso) começa um episódio de ceder NA
FONTE, antes da fila do kernel, se alguma ponte não couber; abaixo
de :data:`FOLGA_PARA_VOLTAR`, todas voltam a escrever. O diário registra só a
BORDA do episódio — e no máximo um por adaptador a cada
:data:`INTERVALO_DAS_BORDAS_NO_DIARIO_S`, com os calados contados.

CEDE SÓ QUEM NÃO CABE, E CADA UM NA SUA VEZ (O-GOVERNADOR-COM-UM-ADAPTADOR-SO-01,
28/09/2026). No episódio, a cada janela medida, o governador conta quantas
pontes COM ESCRITA cabem na saída da janela (a saída vezes a janela, dividida
pelo que uma ponte escreve — :meth:`GovernadorDoRadio._a_vez`) e cede o resto,
e só o resto: quando todas cabem, nenhuma cede, e uma ponte sozinha não cede a
si mesma enquanto o adaptador põe no ar pelo menos meia ponte
(O-GOVERNADOR-NAO-FAZ-UMA-PONTE-SO-CEDER-01, 03/10/2026);
a vez de ceder gira pela ORDEM DA VAGA, nunca pelo número do jogador. Três
pontes num adaptador que escoa duas cediam e voltavam juntas, e cada uma
ficava com metade; agora cada uma fica com dois terços. A ponte sem escrita na
janela (a bomba não escreve o silêncio) e que não estava cedendo fica fora da
vez. Quando não cabe nenhuma (o adaptador parado, o 2B: menos de
:data:`FRACAO_DO_ENGASGO` de uma ponte no ar na janela, ou a fila além de
:data:`FILA_DO_ENGASGO_EM_LIMIARES` limiares), cede o
adaptador inteiro, como antes, e só essas janelas andam o relógio do teto.

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
1. **«Ligar aqui» vale enquanto o CONTROLE ficar naquele adaptador.** REVISTO
   em 23/09 pela A-COSTURA-DA-ONDA-2-01, decisão registrada: a
   GOVERNADOR-02 dizia «enquanto a ponte estiver de pé», e o preço medido na
   conferência foi perguntar a ela no meio da partida — cada controle tem uma
   ponte só, a troca som → vibração derruba e sobe a ponte, e a ponte do som
   sob demanda desce sempre que o som para. A R3 (*sempre pedir mover*) vale a
   cada vez que o controle CHEGA ao adaptador cheio; a resposta de produto cai quando
   ele SAI — desconecta ou é movido (:meth:`GovernadorDoRadio.conferir_as_autorizacoes`).
2. **A marca «além do limite» sai quando o adaptador volta a caber.** A cada
   descida, as :attr:`GovernadorDoRadio.n_max` primeiras vagas do adaptador,
   na ordem em que chegaram, cabem; só o resto segue marcado.
3. **Num 2B longo, a religação espera cada vez mais** — 5, 10, 20, 40 e 60 s
   (:data:`TETO_DA_ESPERA_DA_FILA_S`), e volta a 5 s quando a fila ANDA
   (:meth:`GovernadorDoRadio._a_fila_andou`). O diário diz a ESPERA, uma linha
   por degrau e uma quando a fila volta a andar; as tentativas do meio são
   contadas, não escritas.
4. **A frase da recusa diz o NOME, nunca o endereço.** O adaptador é dito como
   a tela o diz, por :func:`nome_da_porta`, que pergunta ao DONO do nome da
   porta — o ``entrada_a_entrada`` (A-COSTURA-DA-ONDA-2-01). A porta que ela não
   nomeou é «Entrada 4.1.4», pelo dono (TRANSPLANTE-DA-SECAO-01); sem porta
   nenhuma — o adaptador embutido —, a frase diz «este adaptador».
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
import os
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
    TIPO_ACL,
)
from hefesto_dualsense4unix.integrations.radio_da_mesa import N_MAX_PONTES
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

PERIODO_S = 0.25

LIMIAR_DO_DEFICIT = 20

#: O limiar do déficit em janelas de escrita de UMA ponte (a média das pontes
#: de pé com escrita, `_Estado.por_ponte`), com :data:`LIMIAR_DO_DEFICIT` de
#: piso. O-GOVERNADOR-NAO-FAZ-UMA-PONTE-SO-CEDER-01 (03/10/2026): o limiar fixo
#: de 20 pacotes ficava colado nas ~23 escritas que uma ponte de 93,75/s faz
#: numa janela, e um engasgo de uma janela abria episódio. Duas janelas dão a
#: folga de um engasgo inteiro; por ponte, e não pela soma das pontes, para a
#: rajada de três pontes de vibração seguir cedendo cedo (a média segue a
#: rajada com atraso, e o piso vale no começo dela).
JANELAS_DO_LIMIAR = 2.0

#: A janela que pôs no ar pelo menos esta fração do que uma ponte escreve,
#: mas menos que uma ponte inteira, é ENGASGO, e uma ponte segue de pé. Menos
#: que isso é o adaptador parado (o ``acl_tx`` conta o adaptador inteiro, e um
#: pacote alheio na janela não prova que ele escoa), e vale o «cede o
#: adaptador inteiro», que anda o relógio do teto.
FRACAO_DO_ENGASGO = 0.5

#: Até quantos limiares de fila o engasgo deixa uma ponte de pé: a fila que
#: passa disto não é engasgo, é o adaptador que não dá conta de uma ponte.
FILA_DO_ENGASGO_EM_LIMIARES = 2.0

FOLGA_PARA_VOLTAR = 10

ESPERA_DA_FILA_PARADA_S = 5.0

TETO_DA_ESPERA_DA_FILA_S = 60.0

ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA = 64

INTERVALO_DAS_BORDAS_NO_DIARIO_S = 60.0

VALIDADE_DO_PEDIDO_S = 15.0

PRAZO_PARA_SUBIR_S = 30.0

INTERVALO_DAS_AUTORIZACOES_S = 1.0

TIPO_SOM = "som"
TIPO_VIBRACAO = "vibracao"

QUEM = "governador"

ADAPTADOR_CHEIO = "adaptador cheio"
CEDEU_NA_FONTE = "cedeu na fonte"
VOLTOU_A_ESCREVER = "voltou a escrever"
FILA_PARADA = "fila parada"
FILA_ANDOU = "fila voltou a andar"

MOTIVO_DO_REINICIO = "o daemon reiniciou"

MOTIVO_CHEIO = "cheio"
MOTIVO_PARADO = "parado"
MOTIVO_SEM_MEDIDA = "sem medida"

TETO_DO_NAO_SEI_S = 8 * PERIODO_S

POR_QUE_NAO_HA_VAGA = "não há vaga em outro adaptador"
POR_QUE_NAO_SEI_SE_HA_VAGA = "não sei se há vaga em outro adaptador"

PESO_DA_JANELA_NA_MEDIA = 0.25

_ADAPTADOR_FORA = frozenset({ADAPTADOR_DESLIGADO, ADAPTADOR_SUMIU, IOCTL_FALHOU, SEM_BLUETOOTH})

FRASE_DA_FILA_PARADA = "Este adaptador parou de enviar. O som volta sozinho."

_ENDERECO_DE_RADIO = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{2}(?::[0-9a-f]{2}){5}(?![0-9a-f])")


def nome_da_porta(endereco: str, *, amostra: Mapping[str, Any] | None = None) -> str:
    """O nome que a tela dá a este adaptador — o que ela deu, «Entrada 3» ou"""
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
        if lugar is None or not lugar.caminho:
            return ""
        from hefesto_dualsense4unix.integrations import entrada_a_entrada

        return entrada_a_entrada.nome_da_porta(lugar.caminho) or ""
    except Exception:
        logger.debug("governador_nome_da_porta_ilegivel", exc_info=True)
        return ""


def _o_lugar(nome: str, *, com_em: bool = False, maiuscula: bool = False) -> str:
    """O nome com o artigo: «a Entrada 3», «na entrada Meio».

    O ARTIGO É SEMPRE FEMININO, porque concorda com «entrada» e não com o nome
    (O-MAPA-QUE-ELA-CORRIGE-01, D-2609-O-NOME-E-DA-POSICAO). Aqui se adivinhava
    o gênero pelo nome, e a tela dizia «O 13 já tem…» e «no Meio». A frase e
    o artigo são do dono da grafia (``utils/rotulo_da_entrada``); este
    governador não compõe nada.
    """
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
        com_artigo,
        na_frase_do_rotulo,
    )

    return com_artigo(na_frase_do_rotulo(nome), em=com_em, maiuscula=maiuscula)


def _chave(uniq: str) -> str:
    """O ``uniq`` só em hex minúsculo — a mesma chave do ``state_full``."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or str(uniq or "").lower()


def _nada_a_listar(_raiz: str) -> list[str]:
    """A ordem das vagas não relê o sysfs: todo controle chega com o adaptador."""
    return []


def _nenhum_diario() -> list[dict[str, Any]]:
    """O leitor do governador de régua: não há diário dela para ler."""
    return []


def _tipo(tipo: str) -> str:
    """``som`` ou ``vibracao`` — o subsystem diz ``haptica``, o diário não."""
    return TIPO_VIBRACAO if tipo in ("haptica", "háptica", TIPO_VIBRACAO) else TIPO_SOM


class _HidrawIlegivelError(RuntimeError):
    """A raiz do ``hidraw`` no ``/sys`` não se leu: onde o controle está é «não sei»."""


def _listar_o_hidraw(raiz: str) -> list[str]:
    """``os.listdir`` que não engole o erro — ver :class:`_HidrawIlegivelError`."""
    try:
        return os.listdir(raiz)
    except OSError as erro:
        raise _HidrawIlegivelError(raiz) from erro


def _adaptador_pelo_hid_phys(uniq: str) -> str:
    """O endereço do adaptador do controle, pelo ``HID_PHYS`` — ``""`` = não está no rádio."""
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio
    from hefesto_dualsense4unix.integrations.radio_da_mesa import adaptador_por_uniq

    raiz = str(getattr(dualsense_bt_audio, "_SYSFS_HIDRAW", "") or "/sys/class/hidraw")
    return adaptador_por_uniq([uniq], raiz=raiz, listar=_listar_o_hidraw).get(uniq, "")


@dataclass(eq=False)
class Vaga:
    """A licença de UMA ponte para escrever num adaptador."""

    uniq: str
    adaptador: str
    tipo: str
    alem_do_limite: bool = False
    por_escolha_dela: bool = False
    #: (:data:`TETO_DO_NAO_SEI_S`): o diário diz «não sei», nunca «não há».
    sem_medida: bool = False
    pedida_em: float = 0.0
    escritas: int = 0
    cedendo: bool = False
    derrubar: bool = False
    subiu_em: float | None = None
    solta: bool = False
    _vistas: int = 0
    _calada: bool = False
    _dono: Any = field(default=None, repr=False)

    def contar_escrita(self) -> None:
        self.escritas += 1
        if self.escritas == ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA and self._dono is not None:
            try:
                self._dono._a_fila_andou(self.adaptador)
            except Exception:
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
    """A ponte não sobe agora. ``vagas`` são os adaptadores onde caberia."""

    uniq: str
    adaptador: str
    tipo: str
    motivo: str
    vagas: tuple[str, ...] = ()
    n_max: int = N_MAX_PONTES
    nomear: Callable[[str], str] | None = field(default=None, repr=False, compare=False)

    def nome_de(self, endereco: str) -> str:
        """O nome de tela deste adaptador, ou ``""``. NUNCA o endereço: um nome"""
        if self.nomear is None or not endereco:
            return ""
        try:
            nome = str(self.nomear(endereco) or "").strip()
        except Exception:
            return ""
        if not nome or _ENDERECO_DE_RADIO.search(nome):
            return ""
        return nome

    @property
    def frase(self) -> str:
        """O que a tela diz — curto, sem culpa, e só o que foi medido."""
        if self.motivo == MOTIVO_PARADO:
            return FRASE_DA_FILA_PARADA
        nome = self.nome_de(self.adaptador)
        sujeito = _o_lugar(nome, maiuscula=True) if nome else "Este adaptador"
        cheio = f"{sujeito} já tem {self.n_max} controles com som ou vibração."
        if self.motivo == MOTIVO_SEM_MEDIDA:
            return cheio
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
    cedendo_medido_s: float = 0.0
    episodio_escrito: bool = False
    ultimo_ar: Any = None
    deficit_medido: bool = False
    por_ponte: float | None = None
    vez: int = 0
    inteiro: bool = False


@dataclass
class _JanelaMedida:
    """O que uma janela medida disse de um adaptador — a entrada da vez."""

    com_escrita: list[Any]
    no_ar: float
    janela_s: float
    por_ponte_na_janela: float = 0.0


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
class _EsperaDaMedida:
    """Uma ponte que ouviu :data:`MOTIVO_SEM_MEDIDA` e espera a medida."""

    uniq: str
    adaptador: str
    renovada_em: float


@dataclass
class _EpisodioDaFila:
    """Um adaptador que parou de escoar e ainda não provou que voltou a andar."""

    espera_s: float
    desde: float
    tentativas: int = 0


class GovernadorDoRadio:
    """Admissão por adaptador e contrapressão pelo contador ``acl_tx``."""

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
        self._nomear: Callable[[str], str] = nomear or (
            lambda endereco: nome_da_porta(endereco, amostra=self.ultima_amostra())
        )
        if ler_o_diario is not None:
            self._ler_o_diario: Callable[[], Iterable[dict[str, Any]]] = ler_o_diario
        elif registrar is None:
            self._ler_o_diario = diario.ler
        else:
            self._ler_o_diario = _nenhum_diario
        self._fantasmas_fechadas = False
        self._trava = threading.RLock()
        self._trava_do_par = threading.RLock()
        self._vagas: list[Vaga] = []
        self._estados: dict[str, _Estado] = {}
        self._pedidos: dict[str, _Pedido] = {}
        self._autorizados: dict[tuple[str, str], str] = {}
        self._autorizacoes_vistas_em = -math.inf
        self._parado_ate: dict[str, float] = {}
        self._episodios: dict[str, _EpisodioDaFila] = {}
        self._bordas_no_diario: dict[str, _BordasNoDiario] = {}
        self._amostra: dict[str, Any] | None = None
        self._lista_lida = True
        #: :data:`TETO_DO_NAO_SEI_S`. Volta a ``None`` quando a medida chega.
        self._nao_sei_desde: float | None = None
        self._esperando_medida: dict[str, _EsperaDaMedida] = {}
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self.ao_autorizar: Callable[[str], None] | None = None


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
        """Sobe o tique numa thread — que, antes do primeiro tique, fecha as"""
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
        except Exception:
            logger.debug("governador_fantasmas_falhou", exc_info=True)
        while not self._parar.wait(self._periodo_s):
            try:
                self.tique()
            except Exception:
                logger.debug("governador_tique_falhou", exc_info=True)


    def fechar_as_pontes_fantasmas(self) -> int:
        """``PONTE_DESCEU`` «o daemon reiniciou» por ponte que o diário diz de pé"""
        with self._trava:
            if self._fantasmas_fechadas:
                return 0
            self._fantasmas_fechadas = True
        try:
            de_pe = diario.pontes_de_pe(list(self._ler_o_diario()), math.inf)
        except Exception:
            logger.debug("governador_diario_ilegivel_no_arranque", exc_info=True)
            return 0
        fechadas = 0
        with self._trava_do_par:
            with self._trava:
                nossas = {(v.uniq, v.tipo) for v in self._vagas if v.subiu_em is not None}
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
        return self._na_ordem_da_d8(livres, exceto)

    def _nao_sei_se_ha_vaga(self, exceto: str) -> bool:
        """«Não sei» se há vaga em outro adaptador. Chamado com a trava."""
        if self._medidor is None:
            return False
        if self._amostra is None or not self._lista_lida:
            return True
        return any(
            endereco != exceto and str(getattr(ar, "motivo", "") or "") == IOCTL_FALHOU
            for endereco, ar in self._amostra.items()
        )

    def _na_ordem_da_d8(self, livres: list[str], exceto: str) -> tuple[str, ...]:
        """As vagas na ordem de ``plano_de_radio.ordem_dos_destinos`` — a D8 dela.

        A-COSTURA-DA-ONDA-2-01, item 5: a tela pergunta «Mover para ...?» pela
        PRIMEIRA vaga, e a central escolhe o destino pela mesma função. Por
        endereço, as duas divergiam sobre «para onde» na primeira mesa em que o
        endereço menor não fosse o de mais vaga.

        Os planos saem do mesmo ``plano_de_radio.plano_por_adaptador`` que a
        central usa, com o que o governador sabe sem ler nada: as pontes são as
        vagas dele, e os controles de cada adaptador são os enlaces ACL que o
        kernel mede (a amostra do medidor de ar). DUAS DIFERENÇAS DECLARADAS com a
        central, que lê o ``state_full``: um fone no rádio conta aqui como
        controle, e quem VARRE não é sabido (``varrendo=None`` — a função não
        penaliza ninguém, em vez de chutar). Chamado com a trava, sem sysfs:
        todo controle chega com o adaptador dito.
        """
        from hefesto_dualsense4unix.integrations import plano_de_radio

        controles: dict[str, dict[str, Any]] = {}
        for endereco, ar in (self._amostra or {}).items():
            enlaces = getattr(ar, "conexoes", None)  # (noqa-acento): nome do campo
            for enlace in enlaces or ():
                chave = _chave(str(getattr(enlace, "endereco", "") or ""))
                if chave and getattr(enlace, "tipo", None) == TIPO_ACL:
                    controles.setdefault(chave, {"uniq": chave, "adaptador": endereco})
        for vaga in self._vagas:
            if vaga.adaptador:
                chave = _chave(vaga.uniq)
                controles[chave] = {
                    "uniq": chave,
                    "adaptador": vaga.adaptador,
                    "ponte_do_radio": "haptica" if vaga.tipo == TIPO_VIBRACAO else "som",
                }
        planos = plano_de_radio.plano_por_adaptador(
            [{"transport": "bt", "connected": True, **c} for c in controles.values()],
            adaptadores=[*livres, exceto],
            n_max=self.n_max,
            listar=_nada_a_listar,
        )
        ordem = [
            str(p.endereco)
            for p in plano_de_radio.ordem_dos_destinos(planos, exceto=exceto)
            if p.endereco in livres
        ]
        return (*ordem, *(e for e in livres if e not in ordem))

    def pedir_vaga(self, uniq: str, tipo: str) -> Vaga | Recusa:
        """Uma vaga para a ponte deste controle, ou a :class:`Recusa` dita."""
        adaptador = ""
        try:
            adaptador = str(self._adaptador_de(uniq) or "").lower()
        except Exception:
            logger.debug("governador_adaptador_ilegivel", uniq=uniq, exc_info=True)
        tipo = _tipo(tipo)
        chave = _chave(uniq)
        agora = self._relogio()
        with self._trava:
            self._recolher(agora)
            if not adaptador:
                return self._conceder(uniq, "", tipo, alem=False, agora=agora)
            for par in [p for p in self._autorizados if p[0] == chave and p[1] != adaptador]:
                self._autorizados.pop(par, None)
            if self._parado_ate.get(adaptador, 0.0) > agora:
                return Recusa(uniq, adaptador, tipo, MOTIVO_PARADO)
            ocupadas = [
                v for v in self._vagas if v.adaptador == adaptador and _chave(v.uniq) != chave
            ]
            if len(ocupadas) < self.n_max:
                self._pedidos.pop(chave, None)
                self._esperando_medida.pop(chave, None)
                return self._conceder(uniq, adaptador, tipo, alem=False, agora=agora)
            vagas = self._adaptadores_com_vaga(exceto=adaptador)
            autorizado = (chave, adaptador) in self._autorizados
            sem_medida = False
            if not autorizado and not vagas and self._nao_sei_se_ha_vaga(adaptador):
                if self._nao_sei_desde is None:
                    self._nao_sei_desde = agora
                if agora - self._nao_sei_desde < TETO_DO_NAO_SEI_S:
                    self._pedidos.pop(chave, None)
                    self._esperando_medida[chave] = _EsperaDaMedida(uniq, adaptador, agora)
                    logger.debug("governador_espera_a_medida", adaptador=adaptador, uniq=uniq)
                    return Recusa(
                        uniq, adaptador, tipo, MOTIVO_SEM_MEDIDA, n_max=self.n_max,
                        nomear=self._nomear,
                    )
                sem_medida = True
            if autorizado or not vagas:
                # R4: o usuário escolheu «Ligar aqui», ou não há para onde mover —
                # medido, ou dito «não sei» depois do teto.
                self._pedidos.pop(chave, None)
                self._esperando_medida.pop(chave, None)
                vaga = self._conceder(uniq, adaptador, tipo, alem=True, agora=agora)
                vaga.por_escolha_dela = autorizado
                vaga.sem_medida = sem_medida
                return vaga
            self._esperando_medida.pop(chave, None)
            recusa = Recusa(
                uniq, adaptador, tipo, MOTIVO_CHEIO, vagas, n_max=self.n_max, nomear=self._nomear
            )
            anterior = self._pedidos.get(chave)
            self._pedidos[chave] = _Pedido(uniq, tipo, adaptador, vagas, agora)
            pergunta_nova = anterior is None or anterior.adaptador != adaptador
            ocupadas_n = len(ocupadas)
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
        """«Ligar aqui» (R3 → R4): a ponte deste controle sobe além do limite."""
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
            self._autorizados[(chave, adaptador)] = uniq
        logger.info("governador_ligar_aqui", uniq=uniq, adaptador=adaptador)
        avisar = self.ao_autorizar
        if avisar is not None:
            try:
                avisar(uniq)
            except Exception:
                logger.debug("governador_aviso_falhou", uniq=uniq, exc_info=True)
        return True

    def conferir_as_autorizacoes(self) -> int:
        """O «Ligar aqui» cai do controle que SAIU do adaptador. Devolve quantos."""
        with self._trava:
            autorizados = dict(self._autorizados)
        if not autorizados:
            return 0
        sairam: list[tuple[tuple[str, str], str]] = []
        for par, uniq in autorizados.items():
            try:
                onde = str(self._adaptador_de(uniq) or "").lower()
            except Exception:
                logger.debug("governador_autorizacao_ilegivel", uniq=uniq, exc_info=True)
                continue
            if onde != par[1]:
                sairam.append((par, onde))
        with self._trava:
            for par, _onde in sairam:
                self._autorizados.pop(par, None)
        for par, onde in sairam:
            logger.info(
                "governador_ligar_aqui_caiu",
                uniq=autorizados[par],
                adaptador=par[1],
                agora_em=onde or None,
            )
        return len(sairam)


    def _subiu(self, vaga: Vaga, tipo: str | None) -> None:
        with self._trava_do_par:
            with self._trava:
                if vaga.solta or vaga.subiu_em is not None:
                    return
                if tipo:
                    vaga.tipo = _tipo(tipo)
                vaga.subiu_em = self._relogio()
                episodio = self._episodios.get(vaga.adaptador) if vaga.adaptador else None
                if episodio is not None:
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
        elif vaga.sem_medida:
            por_que = POR_QUE_NAO_SEI_SE_HA_VAGA
        else:
            por_que = POR_QUE_NAO_HA_VAGA
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
        with self._trava_do_par:
            with self._trava:
                if vaga.solta:
                    return
                vaga.solta = True
                if vaga in self._vagas:
                    self._vagas.remove(vaga)
                subiu = vaga.subiu_em is not None
                calada = vaga._calada
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
        """ITEM 2: a marca «além do limite» sai de quem voltou a caber."""
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
        for chave in [
            c
            for c, e in self._esperando_medida.items()
            if agora - e.renovada_em > VALIDADE_DO_PEDIDO_S
        ]:
            self._esperando_medida.pop(chave, None)

    def _quem_a_medida_acorda(self, agora: float) -> list[str]:
        """As pontes que esperavam a medida e já têm resposta. Chamado com a trava."""
        teto_passou = (
            self._nao_sei_desde is not None
            and agora - self._nao_sei_desde >= TETO_DO_NAO_SEI_S
        )
        prontas = [
            chave
            for chave, espera in self._esperando_medida.items()
            if teto_passou or not self._nao_sei_se_ha_vaga(espera.adaptador)
        ]
        return [self._esperando_medida.pop(chave).uniq for chave in prontas]


    def tique(self) -> None:
        """Uma janela: amostra o ar e decide, por adaptador, ceder ou escrever."""
        amostra: dict[str, Any] | None = None
        lista_lida = True
        if self._medidor is not None:
            try:
                crua = dict(self._medidor.amostrar())
                lista_lida = not any(
                    str(getattr(a, "motivo", "") or "") == SEM_BLUETOOTH for a in crua.values()
                )
                amostra = {e: a for e, a in crua.items() if e}
            except Exception:
                logger.debug("governador_medidor_falhou", exc_info=True)
        agora = self._relogio()
        bordas: list[tuple[str, dict[str, Any]]] = []
        paradas: list[tuple[str, list[Vaga], float]] = []
        andaram: list[str] = []
        with self._trava:
            if amostra is not None:
                self._amostra = amostra
                self._lista_lida = lista_lida
                if lista_lida and not any(
                    str(getattr(a, "motivo", "") or "") == IOCTL_FALHOU for a in amostra.values()
                ):
                    self._nao_sei_desde = None
            self._recolher(agora)
            acordar = self._quem_a_medida_acorda(agora)
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
            cedendo = {e for e, s in self._estados.items() if s.cedendo}
            for vaga in self._vagas:
                if vaga.cedendo and vaga.adaptador not in cedendo:
                    vaga.cedendo = False
        for o_que, dados in bordas:
            self._escrever(o_que, **dados)
        avisar = self.ao_autorizar
        for uniq in acordar:
            if avisar is not None:
                try:
                    avisar(uniq)
                except Exception:
                    logger.debug("governador_aviso_da_medida_falhou", uniq=uniq, exc_info=True)
        for endereco in andaram:
            self._a_fila_andou(endereco)
        for endereco, vagas, cedendo_s in paradas:
            self._fila_parada(endereco, vagas, cedendo_s, pelo="governador")
        if agora - self._autorizacoes_vistas_em >= INTERVALO_DAS_AUTORIZACOES_S:
            self._autorizacoes_vistas_em = agora
            self.conferir_as_autorizacoes()

    def _medir(
        self,
        estado: _Estado,
        vagas: list[Vaga],
        ar: Any,
        endereco: str,
        agora: float,
        bordas: list[tuple[str, dict[str, Any]]],
    ) -> bool:
        """O déficit de uma janela e as duas bordas. Chamado com a trava."""
        if ar is None or ar is estado.ultimo_ar:
            if ar is None:
                for vaga in vagas:
                    vaga._vistas = vaga.escritas
                estado.deficit_medido = False
            return False
        estado.ultimo_ar = ar
        escritas = 0
        com_escrita: list[Vaga] = []
        for vaga in vagas:
            desta = vaga.escritas - vaga._vistas
            vaga._vistas = vaga.escritas
            escritas += desta
            if desta > 0:
                com_escrita.append(vaga)
        saida = getattr(ar, "saida_por_s", None)
        janela = float(getattr(ar, "janela_s", 0.0) or 0.0)
        if saida is None or janela <= 0:
            estado.deficit_medido = False
            return False
        estado.deficit_medido = True
        estado.fila = max(0.0, estado.fila + escritas - float(saida) * janela)
        media = escritas / len(com_escrita) if com_escrita else 0.0
        if com_escrita:
            estado.por_ponte = (
                media
                if estado.por_ponte is None
                else estado.por_ponte + PESO_DA_JANELA_NA_MEDIA * (media - estado.por_ponte)
            )
        janela_medida = _JanelaMedida(
            com_escrita=com_escrita,
            no_ar=float(saida) * janela,
            janela_s=janela,
            por_ponte_na_janela=media,
        )
        self._as_bordas(estado, vagas, janela_medida, endereco, agora, bordas)
        return (
            escritas >= LIMIAR_DO_DEFICIT
            and estado.fila <= FOLGA_PARA_VOLTAR
            and not estado.cedendo
        )

    @staticmethod
    def _limiar(estado: _Estado, janela: _JanelaMedida) -> float:
        """A fila que abre um episódio: :data:`JANELAS_DO_LIMIAR` janelas de uma ponte.

        A janela que não pôs no ar nem a :data:`FRACAO_DO_ENGASGO` de uma ponte
        fica com o piso, :data:`LIMIAR_DO_DEFICIT`: o ``acl_tx`` preso cede na
        primeira janela, como sempre (a folga é para o engasgo, não para o
        adaptador parado).
        """
        por_ponte = estado.por_ponte or 0.0
        if janela.no_ar < FRACAO_DO_ENGASGO * por_ponte or por_ponte <= 0:
            return float(LIMIAR_DO_DEFICIT)
        return max(float(LIMIAR_DO_DEFICIT), JANELAS_DO_LIMIAR * por_ponte)

    def _a_vez(self, estado: _Estado, vagas: list[Vaga], janela: _JanelaMedida) -> None:
        """Cede só quem não cabe, e cada um na sua vez. Chamado com a trava.

        O-GOVERNADOR-NAO-FAZ-UMA-PONTE-SO-CEDER-01 (03/10/2026): cede
        ``n - cabem``, e não ``max(1, n - cabem)``. O ``max(1, …)`` fazia uma
        ponte ceder em todo episódio mesmo quando todas cabiam, e uma ponte
        sozinha no adaptador cedia a si mesma. E a janela que pôs algum pacote
        no ar :data:`FRACAO_DO_ENGASGO` de uma ponte, mas não uma inteira,
        deixa UMA de pé enquanto a fila não passa de
        :data:`FILA_DO_ENGASGO_EM_LIMIARES` limiares: é engasgo. Menos no ar,
        ou a fila além disso, é o adaptador parado, e cede inteiro.

        O episódio que cedeu inteiro segue inteiro até a fila escoar
        (:data:`FOLGA_PARA_VOLTAR`): sem isso, o adaptador que põe no ar só
        2/3 de uma ponte, sempre, ficava com a fila parada perto do teto do
        engasgo (perto de um segundo de som atrasado), o episódio nunca
        fechava, o relógio do teto nunca zerava, e a ponte sozinha caía, onde
        o código de antes a deixava de pé, cedendo em rodízio consigo mesma.
        """
        com_escrita = janela.com_escrita
        na_vez = [v for v in vagas if v.cedendo or any(v is e for e in com_escrita)]
        por_ponte = max(estado.por_ponte or 0.0, janela.por_ponte_na_janela)
        cabem = int(janela.no_ar / por_ponte) if por_ponte > 0 else 0
        if (
            cabem <= 0
            and por_ponte > 0
            and not estado.inteiro
            and janela.no_ar >= FRACAO_DO_ENGASGO * por_ponte
            and estado.fila
            <= FILA_DO_ENGASGO_EM_LIMIARES * JANELAS_DO_LIMIAR * por_ponte
        ):
            cabem = 1
        if cabem <= 0 or not na_vez:
            estado.inteiro = True
            for vaga in vagas:
                vaga.cedendo = True
            return
        estado.inteiro = False
        ceder = min(len(na_vez), max(0, len(na_vez) - cabem))
        inicio = estado.vez % len(na_vez)
        cedem = [na_vez[(inicio + i) % len(na_vez)] for i in range(ceder)]
        estado.vez = inicio + ceder
        for vaga in vagas:
            vaga.cedendo = any(vaga is c for c in cedem)

    def _as_bordas(
        self,
        estado: _Estado,
        vagas: list[Vaga],
        janela: _JanelaMedida,
        endereco: str,
        agora: float,
        bordas: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Ceder e voltar, pela fila da janela medida. Chamado com a trava."""
        if estado.cedendo and estado.fila > FOLGA_PARA_VOLTAR:
            por_ponte = estado.por_ponte or 0.0
            if estado.inteiro:
                estado.cedendo_medido_s += janela.janela_s
            elif por_ponte > 0 and janela.no_ar >= por_ponte:
                estado.cedendo_medido_s = 0.0
        if estado.cedendo and estado.fila > FOLGA_PARA_VOLTAR:
            self._a_vez(estado, vagas, janela)
        if not estado.cedendo and estado.fila > self._limiar(estado, janela):
            self._a_vez(estado, vagas, janela)
            if not any(vaga.cedendo for vaga in vagas):
                # todas cabem: não há episódio, e o diário não diz «cedeu»
                return
            estado.cedendo = True
            estado.cedendo_desde = agora
            estado.cedendo_medido_s = 0.0
            diario_das_bordas = self._bordas_no_diario.setdefault(endereco, _BordasNoDiario())
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
            estado.inteiro = False
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
        """Ceder passou do teto: as pontes caem e o adaptador espera."""
        vagas = list(vagas)
        agora = self._relogio()
        escrever = not adaptador
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
                estado.inteiro = False
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
        """A fila do adaptador ANDA: acaba a espera crescente dele (item 3)."""
        if not adaptador:
            return
        agora = self._relogio()
        with self._trava_do_par:
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
        except Exception:
            logger.debug("governador_diario_falhou", o_que=o_que, exc_info=True)


__all__ = [
    "ADAPTADOR_CHEIO",
    "CEDEU_NA_FONTE",
    "ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA",
    "ESPERA_DA_FILA_PARADA_S",
    "FILA_ANDOU",
    "FILA_DO_ENGASGO_EM_LIMIARES",
    "FILA_PARADA",
    "FOLGA_PARA_VOLTAR",
    "FRACAO_DO_ENGASGO",
    "FRASE_DA_FILA_PARADA",
    "INTERVALO_DAS_AUTORIZACOES_S",
    "INTERVALO_DAS_BORDAS_NO_DIARIO_S",
    "JANELAS_DO_LIMIAR",
    "LIMIAR_DO_DEFICIT",
    "MOTIVO_CHEIO",
    "MOTIVO_DO_REINICIO",
    "MOTIVO_PARADO",
    "MOTIVO_SEM_MEDIDA",
    "PERIODO_S",
    "POR_QUE_NAO_HA_VAGA",
    "POR_QUE_NAO_SEI_SE_HA_VAGA",
    "PRAZO_PARA_SUBIR_S",
    "QUEM",
    "TETO_DA_ESPERA_DA_FILA_S",
    "TETO_DO_NAO_SEI_S",
    "TIPO_SOM",
    "TIPO_VIBRACAO",
    "VALIDADE_DO_PEDIDO_S",
    "VOLTOU_A_ESCREVER",
    "GovernadorDoRadio",
    "Recusa",
    "Vaga",
    "nome_da_porta",
]
