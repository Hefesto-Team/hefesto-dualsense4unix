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

* há vaga em outro adaptador → :class:`Recusa` com a frase «Este adaptador está
  cheio. Há vaga em X.», e o pedido fica publicado para a tela PERGUNTAR (R3:
  sempre pedir mover). Ela escolhe «Ligar aqui» (:meth:`GovernadorDoRadio.ligar_aqui`)
  e a ponte sobe marcada «além do limite»;
* não há vaga em adaptador nenhum → a ponte sobe marcada «além do limite» e o
  diário diz o fato (R4: degrada e avisa). Nada é desligado.

O TEMPO REAL, a cada :data:`PERIODO_S`
=====================================
O déficit é a FILA DO HOST crescendo: as escritas nossas aceitas pelo kernel
menos o que o adaptador pôs no ar (o Δ``acl_tx`` do ``ar_do_adaptador``, que só
sobe DEPOIS de haver crédito do controlador). Acima de :data:`LIMIAR_DO_DEFICIT`
pacotes, as pontes daquele adaptador cedem os quadros NA FONTE, antes da fila
do kernel; abaixo de :data:`FOLGA_PARA_VOLTAR`, voltam a escrever. O diário
registra só a BORDA.

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
aceitar ponte de novo — a ponte sob demanda religa sozinha.

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
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
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
#: Ceder passou do teto: o adaptador não escoa. Família 2B.
FILA_PARADA = "fila parada"

#: Os motivos de uma :class:`Recusa`.
MOTIVO_CHEIO = "cheio"
MOTIVO_PARADO = "parado"

#: O que o medidor diz quando o adaptador não pode receber ponte — não é
#: «vaga», por mais que ele não tenha ponte nenhuma.
_ADAPTADOR_FORA = frozenset({ADAPTADOR_DESLIGADO, ADAPTADOR_SUMIU, IOCTL_FALHOU, SEM_BLUETOOTH})

#: A frase do adaptador que parou de escoar — a mesma na recusa e no diário.
FRASE_DA_FILA_PARADA = "Este adaptador parou de enviar. O som volta sozinho."


def _chave(uniq: str) -> str:
    """O ``uniq`` só em hex minúsculo — a mesma chave do ``state_full``."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or str(uniq or "").lower()


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
    _dono: Any = field(default=None, repr=False)

    def contar_escrita(self) -> None:
        self.escritas += 1

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

    @property
    def frase(self) -> str:
        """O que a tela diz — curto, sem culpa, e só o que foi medido."""
        if self.motivo == MOTIVO_PARADO:
            return FRASE_DA_FILA_PARADA
        if self.vagas:
            return f"Este adaptador está cheio. Há vaga em {', '.join(self.vagas)}."
        return "Este adaptador está cheio."


@dataclass
class _Estado:
    """O que o governador sabe de UM adaptador entre dois tiques."""

    fila: float = 0.0
    cedendo: bool = False
    cedendo_desde: float | None = None
    #: Segundos de janela MEDIDA em que as pontes seguiram cedendo — o relógio
    #: do teto. Janela de «não sei» não soma: ela não mediu parada nenhuma.
    cedendo_medido_s: float = 0.0
    cedidos_na_borda: int = 0
    ultimo_ar: Any = None
    deficit_medido: bool = False


@dataclass
class _Pedido:
    uniq: str
    tipo: str
    adaptador: str
    vagas: tuple[str, ...]
    renovado_em: float


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
    ) -> None:
        self._medidor = medidor
        self.n_max = int(n_max)
        self._adaptador_de = adaptador_de or _adaptador_pelo_hid_phys
        self._registrar = registrar or diario.registrar
        self._relogio = relogio
        self._periodo_s = periodo_s
        self._trava = threading.RLock()
        self._vagas: list[Vaga] = []
        self._estados: dict[str, _Estado] = {}
        self._pedidos: dict[str, _Pedido] = {}
        #: ``(chave do controle, adaptador)`` que ela mandou «Ligar aqui».
        self._autorizados: set[tuple[str, str]] = set()
        self._parado_ate: dict[str, float] = {}
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
        """Sobe o tique numa thread. Sem medidor não há o que medir."""
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
        while not self._parar.wait(self._periodo_s):
            try:
                self.tique()
            except Exception:  # o governador nunca derruba o daemon
                logger.debug("governador_tique_falhou", exc_info=True)

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
            if (chave, adaptador) in self._autorizados or not vagas:
                # R4: ela escolheu «Ligar aqui», ou não há para onde mover.
                self._pedidos.pop(chave, None)
                return self._conceder(uniq, adaptador, tipo, alem=True, agora=agora)
            recusa = Recusa(uniq, adaptador, tipo, MOTIVO_CHEIO, vagas)
            anterior = self._pedidos.get(chave)
            self._pedidos[chave] = _Pedido(uniq, tipo, adaptador, vagas, agora)
            if anterior is None or anterior.adaptador != adaptador:
                self._escrever(
                    ADAPTADOR_CHEIO,
                    f"a ponte número {len(ocupadas) + 1} pediu vaga num adaptador "
                    f"que comporta {self.n_max}",
                    antes={"pontes": len(ocupadas)},
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

        Vale para o controle NESTE adaptador: se ele for movido, a pergunta
        volta no adaptador novo. ``False`` = o adaptador dele não se lê.
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
            no_adaptador = sum(
                1 for v in self._vagas if v.adaptador == vaga.adaptador and v.adaptador
            )
        campos: dict[str, Any] = {}
        if vaga.alem_do_limite:
            campos["alem_do_limite"] = True
            campos["frase"] = f"{no_adaptador} pontes num adaptador (limite {self.n_max})."
        self._escrever(
            diario.PONTE_SUBIU,
            "ela ligou além do limite" if vaga.alem_do_limite else "há som para mandar",
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
        if subiu:
            self._escrever(
                diario.PONTE_DESCEU,
                por_que,
                adaptador=vaga.adaptador or None,
                controle=vaga.uniq,
                tipo=vaga.tipo,
            )

    def _recolher(self, agora: float) -> None:
        """Vagas esquecidas e pedidos velhos saem. Chamado com a trava."""
        for vaga in [
            v
            for v in self._vagas
            if v.subiu_em is None and agora - v.pedida_em > PRAZO_PARA_SUBIR_S
        ]:
            vaga.solta = True
            self._vagas.remove(vaga)
            logger.debug("governador_vaga_esquecida", uniq=vaga.uniq)
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
                self._medir(estado, vagas, ar, endereco, agora, bordas)
                if estado.cedendo and estado.cedendo_medido_s > TETO_DE_CEDER_S:
                    paradas.append((endereco, list(vagas), estado.cedendo_medido_s))
        for o_que, dados in bordas:
            self._escrever(o_que, **dados)
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
    ) -> None:
        """O déficit de uma janela e as duas bordas. Chamado com a trava."""
        if ar is None or ar is estado.ultimo_ar:
            if ar is None:
                # «NÃO SEI»: as escritas desta janela não têm com o que se
                # comparar, e não viram déficit nem folga.
                for vaga in vagas:
                    vaga._vistas = vaga.escritas
                estado.deficit_medido = False
            return
        estado.ultimo_ar = ar
        escritas = 0
        for vaga in vagas:
            escritas += vaga.escritas - vaga._vistas
            vaga._vistas = vaga.escritas
        saida = getattr(ar, "saida_por_s", None)
        janela = float(getattr(ar, "janela_s", 0.0) or 0.0)
        if saida is None or janela <= 0:
            estado.deficit_medido = False
            return
        estado.deficit_medido = True
        estado.fila = max(0.0, estado.fila + escritas - float(saida) * janela)
        if estado.cedendo and estado.fila > FOLGA_PARA_VOLTAR:
            # Seguiu cedendo numa janela MEDIDA: só esta anda o relógio do teto.
            estado.cedendo_medido_s += janela
        if not estado.cedendo and estado.fila > LIMIAR_DO_DEFICIT:
            estado.cedendo = True
            estado.cedendo_desde = agora
            estado.cedendo_medido_s = 0.0
            for vaga in vagas:
                vaga.cedendo = True
            logger.info("governador_cedeu", adaptador=endereco, fila=round(estado.fila))
            bordas.append(
                (
                    CEDEU_NA_FONTE,
                    {
                        "por_que": "o adaptador não escoou o que as pontes escreveram",
                        "antes": {"fila": round(estado.fila)},
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
        with self._trava:
            ja_parado = self._parado_ate.get(adaptador, 0.0) > agora
            if adaptador:
                self._parado_ate[adaptador] = agora + ESPERA_DA_FILA_PARADA_S
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
            "governador_fila_parada", adaptador=adaptador, pelo=pelo, cedendo_s=round(cedendo_s, 3)
        )
        if ja_parado:
            return
        self._escrever(
            FILA_PARADA,
            f"o bluetoothd não drena o adaptador {adaptador or 'deste controle'}",
            depois={"cedeu_s": round(cedendo_s, 3), "pelo": pelo},
            adaptador=adaptador or None,
            controles=sorted(v.uniq for v in vagas),
            familia="2B",
            frase=FRASE_DA_FILA_PARADA,
        )

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
    "ESPERA_DA_FILA_PARADA_S",
    "FILA_PARADA",
    "FOLGA_PARA_VOLTAR",
    "FRASE_DA_FILA_PARADA",
    "LIMIAR_DO_DEFICIT",
    "MOTIVO_CHEIO",
    "MOTIVO_PARADO",
    "PERIODO_S",
    "PRAZO_PARA_SUBIR_S",
    "QUEM",
    "TIPO_SOM",
    "TIPO_VIBRACAO",
    "VALIDADE_DO_PEDIDO_S",
    "VOLTOU_A_ESCREVER",
    "GovernadorDoRadio",
    "Recusa",
    "Vaga",
]
