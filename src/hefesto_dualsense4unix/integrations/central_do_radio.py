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
  primeiro (é dele — a R6 revista permite); a janela de pareamento abre SÓ no
  destino, com ``Powered`` ligado se preciso e ``Pairable`` ligado SÓ durante a
  janela; o ``Pair`` é atendido pelo agente próprio (R5), e sem ele pelo piso;
  depois ``Trusted`` e ``Connect``.
* **CONFERIR** — o coração: até :data:`CONFERIR_S` lendo o ``HID_PHYS`` no
  adaptador pretendido e o movimento chegando. Só com os dois o estado vira
  :data:`CHEGOU`, e só então a conexão da ORIGEM é esquecida — pelo ``RemoveDevice``
  do dono e pelo verbo ``esquecer`` da ponte root (bond em disco, cache SDP e a
  LÁPIDE que impede o autorestore de ressuscitá-lo).

A ORDEM INTERNA É PAREAR → CONFERIR → ESQUECER (decisão de quem coordena, 23/09):
para ela nada muda — a janela e o «Segure PS + Create» são os da R1 —, e um
parear que falha não perde nada: a conexão velha continua lá, e o controle
volta para a origem com o PS.

OS TRÊS ESTADOS que a tela lê
=============================
:data:`ESPERANDO` (o gesto em curso, ou aplicado e ainda não conferido),
:data:`CHEGOU` e :data:`NAO_CHEGOU`. **Sem conferência o estado nunca é
«chegou»**: um aplicar que o BlueZ disse que deu, e que o ``HID_PHYS`` não
confirma, fica em «esperando» — e é vigiado, sem a trava, até
:data:`PRAZO_DO_PENDENTE_S`. Se o controle aparece no destino, a origem é
esquecida e vira «chegou»; se volta para a origem ou o prazo acaba, «não
chegou», e nada foi apagado.

IDEMPOTÊNCIA É REQUISITO
========================
Rodar duas vezes não move nada duas vezes: o mover em curso devolve o mesmo
movimento, e o aparelho que já está no destino, sem bond em outro lugar, volta
«chegou» sem uma escrita no rádio. Nada aqui cria nó de som.

O «CONECTAR» (D8) é o mesmo caminho sem alvo: a janela abre no destino com
mais vaga de ponte (:func:`plano_de_radio.ordem_dos_destinos`), e o controle
que aparecer nela é o que ela está segurando.

O «EQUILIBRAR» (R12) é :func:`plano_de_radio.ordem_de_redistribuicao` — dona
desde 20/09. Esta central só a chama, e só quando nenhum movimento está
«esperando»: um de cada vez.

O QUE ESTE MÓDULO NÃO FAZ
=========================
Não fala com a tela (nada de recado, R8), não move a webcam (não é do rádio)
e nunca apaga em lote. No «Conectar» pareia UM controle — o primeiro que
aparece na janela, pela classe —, e o segundo fica para a próxima.
"""

from __future__ import annotations

import contextlib
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.conexao_zumbi import PONTE_INSTALADA, mac_limpo
from hefesto_dualsense4unix.integrations.gesto_de_pareamento import (
    ESTADO_JA_PAREADO,
    ESTADO_PAREOU,
    SEGUNDOS_DA_JANELA,
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
#: A janela está aberta no destino e ela tem de segurar PS + Create.
PASSO_GESTO = "gesto"
PASSO_PAREANDO = "pareando"
PASSO_CONFERINDO = "conferindo"
PASSO_ESQUECENDO = "esquecendo"
PASSO_FIM = "fim"

# --- por que um movimento acabou como acabou (chaves de máquina) ------------

#: A trava do rádio não veio no prazo do gesto — o botão treme, sem recado.
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

# --- o diário -----------------------------------------------------------------

#: O ``o_que`` da linha que a central deixa quando um movimento CHEGA.
MOVEU_O_APARELHO = "moveu um aparelho"
#: O ``o_que`` da linha quando ele acaba sem chegar. Nada foi apagado.
O_APARELHO_NAO_CHEGOU = "o aparelho não chegou"

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

#: Quanto um movimento aplicado e não confirmado fica «esperando», vigiado sem a
#: trava, antes de virar «não chegou». Dois minutos cobrem ela apertar PS de novo
#: com calma; mais que isso seguraria o «Equilibrar» sem motivo.
PRAZO_DO_PENDENTE_S = 120.0

#: Quanto a central espera o objeto velho sumir da foto do dono depois de um
#: ``RemoveDevice`` — o sinal ``InterfacesRemoved`` chega pelo fio do barramento.
ESPERA_DO_SUMICO_S = 2.0

#: A foto dos adaptadores para o «Equilibrar» vale este tanto: ele é perguntado a
#: cada ``state_full``, e pelo caminho de reserva (``busctl``) cada foto custa
#: vários subprocessos.
VALIDADE_DOS_ADAPTADORES_S = 2.0

#: O teto de fora do verbo ``esquecer`` da ponte: quem fica pendurado é ``sudo``.
ESPERA_DA_PONTE_S = 20.0


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
    controle: bool = True
    #: O ``Pair`` no destino deu — a conexão nova existe, confirmada ou não.
    pareou_no_destino: bool = False
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
            "controle": self.controle,
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


def endereco_de(valor: object) -> str | None:
    """O endereço do aparelho, pelas duas formas que circulam: com ``:`` ou 12 hex.

    Estrita como ``conexao_zumbi.mac_limpo``: o endereço vira argumento da
    ponte root, e o que não tem forma de endereço sai ``None``.
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
    correr: Callable[[Sequence[str]], tuple[int, str]] | None = None,
) -> tuple[bool, str]:
    """O verbo ``esquecer`` da ponte root: bond em disco, cache SDP e a lápide.

    Sob a suíte recusa sem rodar nada — ``sudo`` contra a ponte instalada é o
    rádio dela. Quem chama já segura a trava; a ponte NUNCA a pede.
    """
    alvo_adaptador = mac_limpo(adaptador)
    alvo = mac_limpo(aparelho)
    if alvo_adaptador is None or alvo is None:
        return False, "o endereço não tem forma de endereço"
    argumentos = ["sudo", "-n", "--", caminho, "esquecer", alvo_adaptador, alvo]
    if correr is None:
        if bluez_dbus.a_suite_esta_rodando():
            return False, "a suíte está no ar e esta é a ponte de verdade"
        correr = _correr_a_ponte
    codigo, erro = correr(argumentos)
    if codigo == 0:
        return True, ""
    return False, erro or f"a ponte saiu com {codigo}"


def _correr_a_ponte(argumentos: Sequence[str]) -> tuple[int, str]:
    try:
        feito = subprocess.run(
            list(argumentos),
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
    return JanelaDeBusca(destino, segundos, dono=dono)


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
        sysfs: Mapping[str, Any] | None = None,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
        segundos_da_janela: int = SEGUNDOS_DA_JANELA,
        conferir_s: float = CONFERIR_S,
        prazo_do_pendente_s: float = PRAZO_DO_PENDENTE_S,
        prazo_da_trava_s: float = PRAZO_DA_TRAVA_DO_GESTO_S,
    ) -> None:
        self._dono_fixo = dono
        self._onde_esta = onde_esta or _onde_esta_pelo_hid_phys
        self._movimento = movimento
        self._esquecer_na_ponte = esquecer_na_ponte or esquecer_pela_ponte
        self._abrir_janela = abrir_janela or _janela_de_busca
        self._sysfs = dict(sysfs or {})
        self._relogio = relogio
        self._dormir = dormir
        self._segundos = int(segundos_da_janela)
        self._conferir_s = float(conferir_s)
        self._prazo_do_pendente_s = float(prazo_do_pendente_s)
        self._prazo_da_trava_s = float(prazo_da_trava_s)
        self._tranca = threading.Lock()
        self._movimentos: dict[str, Movimento] = {}
        self._fios: dict[str, threading.Thread] = {}
        self._parar = threading.Event()
        self._ultimos_controles: tuple[Mapping[str, Any], ...] = ()
        self._adaptadores_em_cache: tuple[float, tuple[bluez_dbus.AdaptadorDoBluez, ...]] | None = (
            None
        )
        self._refrescando = False
        #: O dono já foi aberto? Antes disso o ``state_full`` não o abre: o
        #: primeiro ``dono()`` paga o Gio de forma síncrona, e o tique não pode.
        self._ligada = dono is not None

    # -- ciclo ----------------------------------------------------------------

    def _dono(self) -> bluez_dbus.LeitorDoBluez:
        return self._dono_fixo if self._dono_fixo is not None else bluez_dbus.dono()

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
        return movimento

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
            "movimentos": [m.publicar() for m in self.movimentos()],
            "em_curso": self.em_curso,
            "proposta": proposta,
        }

    # -- DECIDIR: a D8 e o «Equilibrar» ----------------------------------------

    def _adaptadores(
        self, *, esperar: bool = True
    ) -> tuple[bluez_dbus.AdaptadorDoBluez, ...] | None:
        """Os adaptadores do dono, numa foto que vale :data:`VALIDADE_DOS_ADAPTADORES_S`.

        ``esperar=False`` é o caminho do ``state_full``: com o dono vivo a foto
        é memória e sai na hora; pelo caminho de reserva (``busctl``) ela custa
        subprocessos, e então se refaz num fio e o tique leva a última que havia.
        """
        agora = self._relogio()
        cache = self._adaptadores_em_cache
        if cache is not None and agora - cache[0] < VALIDADE_DOS_ADAPTADORES_S:
            return cache[1]
        dono = self._dono()
        if not esperar and not dono.atende_o_proprio_pareamento:
            self._refrescar_os_adaptadores(dono)
            return cache[1] if cache is not None else None
        lidos = dono.adaptadores()
        if lidos is not None:
            self._adaptadores_em_cache = (agora, tuple(lidos))
        return lidos

    def _refrescar_os_adaptadores(self, dono: bluez_dbus.LeitorDoBluez) -> None:
        with self._tranca:
            if self._refrescando:
                return
            self._refrescando = True

        def rodar() -> None:
            try:
                lidos = dono.adaptadores()
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
        varrendo = (
            frozenset(a.endereco for a in adaptadores if a.varrendo)
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
        """
        alvo = endereco_de(aparelho)
        if alvo is None:
            return Movimento(str(aparelho), destino or "", NAO_CHEGOU, PASSO_FIM,
                             MOTIVO_FORA_DO_RADIO)
        repetido = self._o_mesmo_em_curso(alvo, destino)
        if repetido is not None:
            return repetido
        return self._no_fio(
            alvo, destino, lambda pronto: self.mover(alvo, destino, _ao_pegar_a_trava=pronto)
        )

    def comecar_a_conectar(self, destino: str | None = None) -> Movimento:
        """O «Conectar» da tela: o mesmo fio de :meth:`comecar_a_mover`, sem alvo.

        O movimento nasce com :data:`CONECTANDO` no lugar do endereço — ainda não
        se sabe QUEM vai chegar, só ONDE (a D8) — e ganha o endereço quando o
        controle aparece na janela.
        """
        repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
        if repetido is not None:
            return repetido
        return self._no_fio(
            CONECTANDO, destino, lambda pronto: self.conectar(destino, _ao_pegar_a_trava=pronto)
        )

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
            self._vigiar_ate_resolver(fim.aparelho if fim is not None else chave)

        fio = threading.Thread(target=trabalhar, name="hefesto-central-mover", daemon=True)
        with self._tranca:
            self._fios[chave] = fio
        fio.start()
        pronto.wait(self._prazo_da_trava_s + 1.0)
        if "fim" in caixa and caixa["fim"].motivo == MOTIVO_OCUPADO:
            return caixa["fim"]
        return self._pela_chave(chave) or Movimento(
            chave, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=self._relogio()
        )

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
        repetido = self._o_mesmo_em_curso(alvo, destino)
        if repetido is not None:
            return repetido
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                # O «esperando» nasce ANTES de avisar quem espera a trava: senão
                # o gesto da tela leria o movimento de ontem, já acabado.
                self._guardar(Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                return self._mover_na_trava(alvo, destino)
        except TravaOcupadaError:
            logger.info("central_mover_trava_ocupada", aparelho=mascarar(alvo))
            return Movimento(alvo, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def conectar(
        self,
        destino: str | None = None,
        *,
        _ao_pegar_a_trava: Callable[[], None] | None = None,
    ) -> Movimento:
        """O «Conectar» (D8): um controle NOVO no destino com mais vaga de ponte.

        A janela abre no destino da D8 (ou no pedido), e o controle que aparecer
        nela — um controle pela CLASSE, que não estava lá antes da janela, sem
        bond ali — é o que ela está segurando em PS + Create. Se ele tinha bond
        em outro adaptador, é um mover: a origem sai depois do «chegou», como no
        :meth:`mover`. Síncrono, como o :meth:`mover`; nunca levanta.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
        if repetido is not None:
            return repetido
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                self._guardar(Movimento(CONECTANDO, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                return self._conectar_na_trava(destino)
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
        adaptador = por_endereco[pedido]
        # O que o destino JÁ conhecia antes da janela não é quem ela está
        # segurando: a busca de agora é que o faz aparecer.
        antes = frozenset(a.endereco for a in dono.aparelhos(adaptador=adaptador.caminho) or ())
        return self._parear_e_conferir(self._guardar(movimento), dono, adaptador, antes=antes)

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
        controle = self._e_controle(foto, alvo)
        origens = tuple(sorted(
            e for e, a in foto.do_aparelho.items() if e != pedido and a.pareado
        ))
        movimento = Movimento(
            alvo, pedido or "", ESPERANDO, PASSO_PREPARANDO,
            origens=origens, controle=controle, comecou=comeco,
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
        if controle and self._onde_esta(_hex12(alvo)) == pedido:
            conferindo = self._guardar(replace(movimento, passo=PASSO_CONFERINDO))
            if self._conferir(conferindo, dono):
                return self._esquecer_as_origens(conferindo, dono)
            return self._guardar(replace(conferindo, motivo=MOTIVO_SEM_CONFIRMACAO))

        movimento = self._guardar(movimento)
        velho = foto.do_aparelho.get(pedido)
        if velho is not None:
            # O objeto velho no DESTINO sai antes de a janela abrir (R6 revista:
            # é dele). Com bond, o `Pair` responderia «já existe» sobre uma
            # chave que o controle não tem mais — sai pela ponte, com lápide.
            # Sem bond, é sobra de uma busca antiga, e a espera do gesto o leria
            # como «ela apertou PS + Create» antes de ela apertar.
            if velho.pareado:
                self._esquecer(dono, pedido, alvo)
            else:
                dono.remover_aparelho(velho.caminho, quem=QUEM)
            self._esperar_sumir(dono, alvo, pedido)

        return self._parear_e_conferir(movimento, dono, foto.adaptadores[pedido])

    def _parear_e_conferir(
        self,
        movimento: Movimento,
        dono: bluez_dbus.LeitorDoBluez,
        adaptador: bluez_dbus.AdaptadorDoBluez,
        *,
        antes: frozenset[str] | None = None,
    ) -> Movimento:
        """APLICAR e CONFERIR: a janela só no destino, o gesto, o ``Pair``, o
        ``Connect``; depois o ``HID_PHYS``. ``antes`` diz que é um «Conectar»:
        o alvo é o controle novo que aparecer."""
        restaurar = self._preparar_o_adaptador(dono, adaptador)
        janela = self._abrir_janela(adaptador.endereco, self._segundos, dono)
        try:
            motivo = janela.abrir_a_janela()
            if motivo:
                logger.warning("central_janela_nao_abriu", motivo=motivo[:200])
                return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_JANELA)
            movimento = self._guardar(replace(movimento, passo=PASSO_GESTO))
            if antes is not None:
                achado = self._esperar_um_controle_novo(janela, antes, comeco=self._relogio())
                if achado is None:
                    return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_GESTO)
                movimento = self._quem_chegou(movimento, achado, dono)
            elif not self._esperar_o_gesto(janela, movimento.aparelho, comeco=self._relogio()):
                return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_GESTO)
            movimento = self._guardar(replace(movimento, passo=PASSO_PAREANDO))
            resultado = janela.parear(movimento.aparelho)
            if resultado.estado not in (ESTADO_PAREOU, ESTADO_JA_PAREADO):
                return self._acabou(movimento, NAO_CHEGOU, MOTIVO_NAO_PAREOU)
            movimento = self._guardar(replace(movimento, pareou_no_destino=True))
            self._conectar(dono, movimento.aparelho, movimento.destino)
        finally:
            janela.fechar()
            restaurar()

        movimento = self._guardar(replace(movimento, passo=PASSO_CONFERINDO))
        if not self._conferir(movimento, dono):
            logger.info("central_mover_sem_confirmacao", aparelho=mascarar(movimento.aparelho))
            return self._guardar(replace(movimento, motivo=MOTIVO_SEM_CONFIRMACAO))
        return self._esquecer_as_origens(movimento, dono)

    def _quem_chegou(
        self, movimento: Movimento, achado: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «Conectar» ganha o endereço: sai a chave :data:`CONECTANDO`, entra o
        controle, com as origens que ele tinha em OUTROS adaptadores."""
        foto = _ler(dono, achado)
        origens = tuple(sorted(
            e for e, a in (foto.do_aparelho.items() if foto is not None else ())
            if e != movimento.destino and a.pareado
        ))
        with self._tranca:
            self._movimentos.pop(CONECTANDO, None)
        return self._guardar(replace(movimento, aparelho=achado, origens=origens, controle=True))

    # -- os passos -------------------------------------------------------------

    def _e_controle(self, foto: _Foto, alvo: str) -> bool:
        """Pergunta à CLASSE do aparelho, nunca ao nome. Sem classe publicada,
        pergunta ao kernel: o aparelho que tem hidraw no rádio é controle."""
        for objeto in foto.do_aparelho.values():
            if objeto.classe is not None:
                return e_controle(objeto.classe)
        return bool(self._onde_esta(_hex12(alvo)))

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
            if self._parar.is_set() or self._relogio() >= fim or not janela.aberta:
                return False
            self._dormir(PASSO_S)

    def _esperar_um_controle_novo(
        self, janela: Janela, antes: frozenset[str], *, comeco: float
    ) -> str | None:
        """O «Conectar»: o primeiro CONTROLE (pela classe) que a janela achou e que
        o destino não conhecia antes dela. Um por vez: o segundo fica para a
        próxima."""
        fim = comeco + self._segundos
        while True:
            for candidato in janela.candidatos():
                endereco = getattr(candidato, "endereco", "")
                if (
                    endereco
                    and endereco not in antes
                    and not getattr(candidato, "ja_pareado", False)
                    and e_controle(getattr(candidato, "classe", None))
                ):
                    return str(endereco)
            if self._parar.is_set() or self._relogio() >= fim or not janela.aberta:
                return None
            self._dormir(PASSO_S)

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
        movimento chegando. Outro aparelho: o BlueZ o diz conectado no destino."""
        if movimento.controle:
            uniq = _hex12(movimento.aparelho)
            if self._onde_esta(uniq) != movimento.destino:
                return False
            if self._movimento is None:
                return True
            hz = self._movimento(uniq)
            return hz is not None and hz > 0
        no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
        if no is None:
            return False
        return bluez_dbus.como_booleano(
            dono.propriedade(no, bluez_dbus.APARELHO, "Connected")
        ) is True

    def _conferir(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """Até :data:`CONFERIR_S` perguntando. Sem confirmação, nunca «chegou»."""
        fim = self._relogio() + self._conferir_s
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

        Sem origem e sem parear nada, não houve movimento: ele já estava lá, e o
        diário não ganha uma linha de «moveu».
        """
        if not movimento.origens and not movimento.pareou_no_destino:
            return self._guardar(replace(
                movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_JA_ESTAVA
            ))
        movimento = self._guardar(replace(movimento, passo=PASSO_ESQUECENDO))
        sem_lapide = [
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
        feito = self._guardar(replace(movimento, estado=estado, passo=PASSO_FIM, motivo=motivo))
        if estado == NAO_CHEGOU:
            self._no_diario(O_APARELHO_NAO_CHEGOU, motivo, feito,
                            depois={"pareou_no_destino": feito.pareou_no_destino})
        return feito

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
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        pendentes = [
            m for m in self.movimentos()
            if m.em_curso and m.passo == PASSO_CONFERINDO
        ]
        for movimento in pendentes:
            dono = self._dono()
            if self._chegou(movimento, dono):
                try:
                    with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                        if self.movimento_de(movimento.aparelho) == movimento:
                            self._esquecer_as_origens(movimento, dono)
                except TravaOcupadaError:
                    continue
                continue
            if movimento.controle and movimento.origens:
                onde = self._onde_esta(_hex12(movimento.aparelho))
                if onde and onde in movimento.origens:
                    self._acabou(movimento, NAO_CHEGOU, MOTIVO_VOLTOU)
                    continue
            if self._relogio() - movimento.comecou >= self._prazo_do_pendente_s:
                self._acabou(movimento, NAO_CHEGOU, MOTIVO_PRAZO)

    def _vigiar_ate_resolver(self, alvo: str) -> None:
        """O fio do gesto, depois do mover: vigia o «esperando» até resolver."""
        while not self._parar.is_set():
            atual = self.movimento_de(alvo)
            if atual is None or not atual.em_curso or atual.passo != PASSO_CONFERINDO:
                return
            self._dormir(1.0)
            self.vigiar()


__all__ = [
    "CHEGOU",
    "CONECTANDO",
    "CONFERIR_S",
    "ESPERANDO",
    "ESTADOS",
    "MOTIVO_FORA_DO_RADIO",
    "MOTIVO_JA_ESTAVA",
    "MOTIVO_NAO_PAREOU",
    "MOTIVO_OCUPADO",
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
    "PASSO_CONFERINDO",
    "PASSO_ESQUECENDO",
    "PASSO_FIM",
    "PASSO_GESTO",
    "PASSO_PAREANDO",
    "PASSO_PREPARANDO",
    "PRAZO_DA_TRAVA_DO_GESTO_S",
    "PRAZO_DO_PENDENTE_S",
    "QUEM",
    "CentralDoRadio",
    "Movimento",
    "endereco_de",
    "esquecer_pela_ponte",
]
