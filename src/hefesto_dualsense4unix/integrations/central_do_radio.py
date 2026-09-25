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

UM POR VEZ, TAMBÉM NO ARRASTAR (A-COSTURA-DA-ONDA-2-01)
======================================================
Com um movimento em curso — no gesto, ou aplicado e ainda «esperando» a
conferência, já sem a trava —, nenhum outro começa: o pedido volta
:data:`MOTIVO_OCUPADO`, e o botão treme. A conferida é feita duas vezes, antes
e DEPOIS de pegar a trava, porque o outro pode nascer enquanto este espera.

O «CONECTAR» (D8) é o mesmo caminho sem alvo: a janela abre no destino com
mais vaga de ponte (:func:`plano_de_radio.ordem_dos_destinos`), e o controle
que aparecer nela é o que ela está segurando.

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

# --- o diário -----------------------------------------------------------------

#: O ``o_que`` da linha que a central deixa quando um movimento CHEGA.
MOVEU_O_APARELHO = "moveu um aparelho"
#: O ``o_que`` da linha quando ele acaba sem chegar. Nada foi apagado.
O_APARELHO_NAO_CHEGOU = "o aparelho não chegou"
#: O ``o_que`` da linha da FAXINA: a chave que ficou num adaptador em que o
#: controle não mora saiu.
ESQUECEU_A_SOBRA = "esqueceu a sobra de um bond"

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

#: De quanto em quanto tempo a faxina olha. A sobra não tem pressa (ela só
#: atrapalha a próxima reconexão), e cada olhada custa uma foto do BlueZ e uma
#: varredura do ``/sys/class/hidraw``.
INTERVALO_DA_FAXINA_S = 30.0

#: A chave do fio da faxina em ``_fios`` — não tem forma de endereço, então não
#: esbarra na de um movimento.
_FIO_DA_FAXINA = "faxina"


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


def _recusar_a_ponte_sob_a_suite(_argumentos: Sequence[str]) -> subprocess.Popen[str]:
    raise OSError("a suíte está no ar e esta é a ponte de verdade")


def _nao_correr_sob_a_suite(_argumentos: Sequence[str]) -> tuple[int, str]:
    return 1, "a suíte está no ar e esta é a ponte de verdade"


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

    # -- ciclo ----------------------------------------------------------------

    def _dono(self) -> bluez_dbus.LeitorDoBluez:
        if self._dono_fixo is not None:
            return self._dono_fixo
        dono = bluez_dbus.dono()
        self._dono_visto = dono
        return dono

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
        self._no_fio_atual.chave = movimento.aparelho
        return movimento

    def _falhou(self, chave: str) -> Movimento:
        """Um erro no meio do mover: o movimento deste fio acaba «não chegou».

        Sem isto a promessa de nunca levantar caía, e o movimento ficava
        «esperando» para sempre — o «Equilibrar» mudo e o mesmo pedido
        devolvendo o movimento morto até o daemon reiniciar.
        """
        logger.warning("central_mover_levantou", aparelho=mascarar(chave), exc_info=True)
        atual = self._pela_chave(getattr(self._no_fio_atual, "chave", chave))
        if atual is None or not atual.em_curso:
            return atual or Movimento(chave, "", NAO_CHEGOU, PASSO_FIM, MOTIVO_FALHOU)
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

        UM POR VEZ (A-COSTURA-DA-ONDA-2-01): com QUALQUER movimento em curso — de
        outro aparelho, ou deste para outro destino — a recusa sai na hora, sem
        fio e sem esperar a trava. O mesmo pedido de novo devolve o mesmo
        movimento (a idempotência da MOVER).
        """
        alvo = endereco_de(aparelho)
        if alvo is None:
            return Movimento(str(aparelho), destino or "", NAO_CHEGOU, PASSO_FIM,
                             MOTIVO_FORA_DO_RADIO)
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
        se sabe QUEM vai chegar, só ONDE (a D8) — e ganha o endereço quando o
        controle aparece na janela. Um por vez, como o :meth:`comecar_a_mover`.
        """
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
                self._guardar(Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                try:
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
                self._guardar(Movimento(CONECTANDO, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                try:
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
        e_controle = self._e_controle(foto, alvo)
        origens = tuple(sorted(
            e for e, a in foto.do_aparelho.items() if e != pedido and a.pareado
        ))
        movimento = Movimento(
            alvo, pedido or "", ESPERANDO, PASSO_PREPARANDO,
            origens=origens, e_controle=e_controle, comecou=comeco,
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
        return self._guardar(
            replace(movimento, aparelho=achado, origens=origens, e_controle=True)
        )

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
        if movimento.e_controle:
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
                self._acabou(movimento, NAO_CHEGOU, MOTIVO_VOLTOU)
                return
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

    # -- a faxina: a sobra do bond sai sozinha ---------------------------------

    def sobras(self, dono: bluez_dbus.LeitorDoBluez) -> tuple[tuple[str, str, str], ...] | None:
        """``(adaptador que sai, controle, adaptador em que ele está)``, em ordem.

        Só LÊ. Uma sobra é a CHAVE (``Paired``) de um controle num adaptador
        em que o kernel não o diz conectado, quando ele está conectado, pelo
        rádio, em OUTRO adaptador que também tem a chave dele. Fica de fora:

        * o objeto sem chave — o BlueZ guarda um para todo aparelho que uma
          busca achou, e o vizinho visto por dois adaptadores não é bond;
        * o controle desligado ou no cabo (``HID_PHYS`` sem endereço de
          adaptador): ele ainda não disse qual chave vale;
        * o aparelho que a classe não diz controle — um teclado de vários
          hosts pode querer as duas chaves;
        * o controle conectado num adaptador em que o BlueZ não mostra chave
          dele: é estado que esta central não entende, e ela não mexe.

        ``None`` = não deu para perguntar, nunca «não há».
        """
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
        achadas: list[tuple[str, str, str]] = []
        for aparelho, onde_tem in sorted(chaves.items()):
            if len(onde_tem) < 2:
                continue
            if not any(e_controle(o.classe) for o in onde_tem.values()):
                continue
            agora = self._onde_esta(_hex12(aparelho))
            if not agora or agora not in onde_tem:
                continue
            achadas.extend((sai, aparelho, agora) for sai in sorted(onde_tem) if sai != agora)
        return tuple(achadas)

    def esquecer_as_sobras(self) -> tuple[str, str] | None:
        """UMA volta da faxina: esquece UMA sobra e devolve ``(adaptador, controle)``.

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
                fez = self._esquecer(dono, sai, aparelho)
                self._esperar_sumir(dono, aparelho, sai)
        except TravaOcupadaError:
            logger.info("central_faxina_trava_ocupada")
            return None
        except Exception:
            logger.warning("central_faxina_levantou", exc_info=True)
            return None
        logger.info(
            "central_esqueceu_a_sobra",
            aparelho=mascarar(aparelho),
            adaptador=mascarar(sai),
            fica=mascarar(fica),
            lapide=fez,
        )
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM,
                ESQUECEU_A_SOBRA,
                "o controle está conectado em outro adaptador, e guarda um host só: "
                "a chave deste era sobra de um mover feito pela metade",
                antes={"adaptadores": sorted({sai, fica})},
                depois={"adaptador": fica, "sem_lapide": None if fez else [sai]},
                controle=aparelho,
                adaptador=sai,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)
        return sai, aparelho

    def comecar_a_faxina(self, intervalo_s: float = INTERVALO_DA_FAXINA_S) -> None:
        """Sobe o fio da faxina — uma volta a cada ``intervalo_s``. Idempotente.

        A primeira volta espera um intervalo inteiro: no arranque os controles
        ainda estão conectando, e o ``HID_PHYS`` de quem não chegou é «não
        sei». O :meth:`fechar` o para como para os fios do mover.
        """
        with self._tranca:
            vivo = self._fios.get(_FIO_DA_FAXINA)
            if vivo is not None and vivo.is_alive():
                return
            fio = threading.Thread(
                target=self._faxinar_sempre,
                args=(float(intervalo_s),),
                name="hefesto-central-faxina",
                daemon=True,
            )
            self._fios[_FIO_DA_FAXINA] = fio
        fio.start()

    def _faxinar_sempre(self, intervalo_s: float) -> None:
        while not self._parar.wait(intervalo_s):
            self.esquecer_as_sobras()


__all__ = [
    "CHEGOU",
    "CONECTANDO",
    "CONFERIR_S",
    "ESPERANDO",
    "ESQUECEU_A_SOBRA",
    "ESTADOS",
    "INTERVALO_DA_FAXINA_S",
    "MOTIVO_FALHOU",
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
