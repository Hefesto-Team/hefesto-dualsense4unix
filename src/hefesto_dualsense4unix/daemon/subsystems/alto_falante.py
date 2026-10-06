"""Subsystem: o nó de som de CADA DualSense — e ele não sabe o que é transporte.

SOM-QUE-SAI-01. Embrulha :mod:`integrations.alto_falante_bt` no contrato
``Subsystem`` do daemon (``start``/``stop``/``is_enabled``). É fino de
propósito: toda a lógica de PipeWire, Opus e protocolo mora no módulo de
integração, que roda igual pelo CLI, pela interface ou por aqui. Espelho de
``daemon/subsystems/bt_mic.py``, a metade de ENTRADA, que **não é tocada**.

O DEFEITO QUE ELE EXISTE PARA MATAR
------------------------------------
A placa ALSA do DualSense é do **TRANSPORTE**, não da unidade — medido por
INVERSÃO em 15/08/2026, com os quatro aparelhos trocados de braço: quem foi
para o fio ganhou placa, quem foi para o ar perdeu. A consequência para quem
joga é a que esta sprint ataca: **ela tira o cabo no meio da partida e o
dispositivo de saída que o jogo escolheu desaparece do sistema.** Não é o som
que fica ruim — é a rota que some debaixo do jogo.

Depois deste subsystem, o jogo aponta para **um nó que não sai do lugar**: o
nome vem do ``uniq`` do controle (``hefesto_som_<marca>``), e o cabo, o rádio e
o "não tem para onde ir" acontecem por baixo dele. É o mesmo contrato do
gamepad virtual, que é o precedente que ela citou: *o jogo escolhe um
dispositivo, não um transporte* (``integrations/virtual_pad.py``).

AS TRÊS DECISÕES DE PRODUTO, E ELAS SÃO CURTAS
-----------------------------------------
``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE`` (06/09/2026, por delegação,
reversível numa frase — ``docs/data/decisoes-de-produto.csv:213``):

1. **REVERTIDA POR ELA EM 08/09/2026.** Dizia *"o nó vive só enquanto há
   controle"* — decisão por DELEGAÇÃO, e declarada reversível numa frase. Ela
   reverteu com todas as letras em `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-
   SEMPRE` (*"concordo com as 5"*): **nó que some quebra o jogo que o
   escolheu.** O que vai e volta é a ROTA, e o nó fica;
2. **no cabo ele não vira saída padrão.** ``priority.session`` baixa
   (``integrations.alto_falante_bt.PRIORIDADE_SESSAO_DO_SOM``). Publicar o nó
   é uma coisa; mandar o som do sistema para ele é outra, e a segunda é do usuário;
3. **o degrau é o ``0x36`` combinado desde 03/10/2026**: o som e a háptica do
   controle num relatório só, com o ``0x10`` em todo quadro (provado na bancada), e é ele que a
   ``PonteDeSomPorRadio`` que este subsystem sobe por
   controle no rádio escreve.

O QUE ELE NÃO FAZ, E É METADE DO VALOR DE LER ISTO
---------------------------------------------------
* **não escreve no aparelho do cabo.** No cabo o som é da placa USB do
  próprio controle; no rádio, :meth:`AltoFalanteSubsystem._casar_as_pontes`
  sobe uma ``PonteDeSomPorRadio`` por controle, e é ela que escreve o
  ``0x36`` no hidraw. A régua que fica é a da
  **FALÁCIA DO CANAL QUE RESPONDE** — concluir que, porque um canal
  responde, ele FAZ o que se esperava dele: o mapa segura o degrau em
  ``MONTOU`` até a orelha do usuário ouvir o caminho inteiro do produto
  (``audio.saida_dedicada@dualsense``, AS-FRASES-QUE-A-BANCADA-ACHOU-01);
* **PASSOU A LIGAR — 09/09/2026, SOM-POR-CONTROLE-01.** Esta linha dizia *"não
  liga o monitor ao sink USB do controle no cabo"*, e era verdade: o
  ``module-loopback`` e o casamento por dispositivo USB estavam fora da posse
  daquela sprint. Estão dentro desta. Quem resolve a rota é
  ``integrations.alto_falante_bt.rota_do_no`` — uma pergunta, um dono;
* **não escolhe o número do rótulo.** O «Controle N» de «Alto-falante do
  Controle N» é a conta DA CASA, e este subsystem só a alcança — ver
  :meth:`AltoFalanteSubsystem.numero_do_assento` e
  ``daemon/subsystems/base.numero_do_assento_na_mesa``.

UM DONO DO CICLO DE VIDA — 28/09/2026 (O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01)
--------------------------------------------------------------------------
O nó de som de cada controle, no cabo e no rádio, de um a quatro, nasce e
morre AQUI (:class:`GerenciadorDeNosDeSom`), por
:class:`~integrations.alto_falante_bt.SinkVirtualPipeWire`. O segundo
publicador que existia — o plano da janela em ``app/audio_saida``
(``plano_de_publicacao``, ``argv_para_publicar_o_no``) — nunca foi executado
por ninguém e saiu; as invariantes dele são cobradas deste gerenciador em
``tests/unit/test_o_alto_falante_virtual_esconde_o_transporte.py``, contra um
servidor de som de mentira.

O ÓRFÃO GANHOU A ROTA, E DEPOIS GANHOU AS TRÊS LINHAS DO REGISTRO
------------------------------------------------------------------
**As duas razões de 07/09 para não o ligar caíram em 09/09**, e as duas eram
razões de verdade:

* *"sem o ``module-loopback``, o nó publicado é um sumidouro"* — agora
  :class:`~integrations.alto_falante_bt.SinkVirtualPipeWire` sobe o loopback
  junto, e a pergunta *"onde este nó entrega?"* passou a ter **um** dono
  (``integrations.alto_falante_bt.rota_do_no``). Eram duas respostas
  escritas; ficou uma;
* *"os quatro nascem com o MESMO rótulo"* — agora cada um nasce «Alto-falante
  do Controle N», com o número do ASSENTO, pelo mesmo gancho do «Microfone do
  Controle N» (decisão de 09/09, *"4a"*).

**ELE DEIXOU DE SER ÓRFÃO EM 10/09/2026 — SOM-FIADO-01.** As três linhas do
registro existem, e são as três que a receita exige:
``daemon/subsystems/__init__.py`` (a lista), ``daemon/lifecycle.py``
(o ``_safe_start("alto_falante", …)`` no ``run()``) e ``daemon/connection.py``
(o ``_stop_alto_falante`` no ``shutdown()``). Fazer só duas é a armadilha que o
``subsystems/__init__.py`` nomeia: sobe o subsystem e nunca o para, e o nó fica
na lista de saída dela **depois de o daemon morrer**.

**E EM 12/09/2026 O DAEMON PASSOU A ENTRAR PELO CONSTRUTOR** (TRES-CONTAS-PARA-
UM-NUMERO-01): é por ele que o «Controle N» do rótulo chega ao mesmo número do
cartão dela, perguntando o ``player_slot`` ao ``identity_registry``.

A régua que trava o par continua sendo
``tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`` — e ela sempre permitiu
esta cura: *"ela NÃO proíbe ligar o subsystem; ela trava o PAR — se ele subir,
o nó tem de ter rota"*.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO, placas_do_piso
from hefesto_dualsense4unix.daemon.subsystems.base import numero_do_assento_na_mesa
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


def _mesmo_controle(a: object, b: object) -> bool:
    """Os dois endereços são o mesmo controle, pelos dígitos (``norm_mac``, o dono da chave)."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    if not a or not b:
        return False
    return (norm_mac(str(a)) or str(a).lower()) == (norm_mac(str(b)) or str(b).lower())


RECONCILIA_S = 5.0

_O_QUE_A_VOLTA_OUVE: tuple[str, ...] = ("sinks", "sink-inputs")

RECUSA_DA_PONTE_S = 60.0

PAR_DO_TESTE_DA_HAPTICA: tuple[int, int] = (127, 127)

_UNIQ_HEX = 12

TRANSPORTE_CABO = "usb"


@dataclass(frozen=True)
class ControleNaLista:
    """Um DualSense visto pelo sysfs, com o transporte AO LADO e nunca DENTRO.

    O ``transporte`` existe para o diagnóstico e para o relatório — **nunca
    para o nome do nó**. Se algum dia ele entrar na identidade, o defeito que
    este subsystem existe para matar volta com outra roupa.
    """

    uniq: str
    caminho: str
    transporte: str


class GerenciadorDeNosDeSom:
    """Sobe/derruba um :class:`SinkVirtualPipeWire` por controle na lista."""

    def __init__(
        self,
        *,
        fabrica: Any = None,
        fonte_por_controle: Any = None,
        ponte_do_radio_por_controle: Any = None,
    ) -> None:
        self._fabrica = fabrica
        self._fonte_por_controle = fonte_por_controle
        self._ponte_do_radio_por_controle = ponte_do_radio_por_controle
        self._nos: dict[str, Any] = {}
        self._acordar = threading.Event()

    @property
    def nos(self) -> dict[str, Any]:
        return dict(self._nos)

    def _construir(
        self,
        uniq: str,
        transporte: str,
        mesa: tuple[str, ...],
        *,
        descricao: str | None = None,
    ) -> Any:
        """O nó daquele controle, JÁ com rótulo próprio e rota resolvida.

        O rótulo e a rota nascem aqui e não dentro do nó porque quem sabe a
        MESA é este gerenciador: ``sink_do_controle`` precisa da lista inteira
        de ``uniq`` para casar a placa USB certa. Com um só, dois DualSense no
        cabo entregam o som do P2 no alto-falante do P1.

        O parâmetro ``descricao``  (noqa-acento) nome de parâmetro
        existe para UM chamador — a VOLTA de :meth:`_republicar`,
        que precisa reerguer o nó com o rótulo que estava no ar, e não com o de
        agora. Sem ela a volta seria uma segunda tentativa do mesmo ato que
        acabou de falhar, e não um desfazer.
        """
        if self._fabrica is not None:
            return self._fabrica(uniq)
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            SinkVirtualPipeWire,
            descricao_do_alto_falante,
        )

        return SinkVirtualPipeWire(
            uniq=uniq,
            descricao=(
                descricao_do_alto_falante(uniq) if descricao is None else descricao
            ),
            rota=self._rota_de_agora(uniq, transporte, mesa),
        )

    def _rota_de_agora(self, uniq: str, transporte: str, mesa: tuple[str, ...]) -> Any:
        """A rota que este controle teria se o nó nascesse AGORA."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rota_do_no

        return rota_do_no(
            uniq,
            transporte,
            mesa,
            fonte=self._fonte_do_no(uniq),
            ponte_do_radio=self._ponte_do_radio(uniq),
        )

    # som via canal de audio externo do controle"*.  # (noqa-acento): a digitação é do usuário

    def _reafinar(
        self, uniq: str, no: Any, transporte: str, mesa: tuple[str, ...]
    ) -> None:
        """A rota do nó VIVO passa a ser a de agora — e o nó não sai do lugar.

        **O QUE ISTO CUSTA, medido e escrito para ninguém se assustar depois:**
        um :func:`rota_do_no` por nó de pé, por varredura. No cabo isso é um
        ``pactl list sinks short`` (mais o longo, quando há placa de DualSense
        na lista) e, em ``mix``, um ``pactl get-default-sink``. Com a mesa de
        quatro cheia e :data:`RECONCILIA_S` em 5 s, são menos de um subprocesso
        por segundo. **Não é a tempestade de syscalls do mapa de motores do
        `gamepad.py`**, e o preço de não pagá-lo é a escolha do usuário presa até o
        daemon reiniciar, que é o defeito que esta sprint fechou.

        O que NÃO se lê aqui é o perfil: a fonte vem do cache por
        ``(nome, mtime)`` de :meth:`AltoFalanteSubsystem._fontes_do_perfil`.
        """
        religar = getattr(no, "religar", None)
        if self._fabrica is not None or not callable(religar):
            return
        try:
            rota = self._rota_de_agora(uniq, transporte, mesa)
        except Exception:
            logger.debug("som_rota_de_agora_ilegivel", uniq=uniq, exc_info=True)
            return
        if not self._vale_religar(uniq, rota):
            return
        try:
            religar(rota)
        except Exception:
            logger.debug("som_religacao_falhou", uniq=uniq, exc_info=True)

    def _vale_religar(self, uniq: str, rota: Any) -> bool:
        """Esta rota nova merece encostar num nó que está tocando?"""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        if rota is None or not getattr(rota, "tem_rota", False):
            return False
        alvo = str(getattr(rota, "sink", "") or "")
        if alvo and alvo == nome_do_sink(uniq):
            logger.debug("som_rota_para_si_mesma", uniq=uniq, sink=alvo)
            return False
        return True


    def _o_rotulo_envelheceu(self, uniq: str, no: Any) -> bool:
        """O nome que este nó VIVO carrega ficou para trás do assento de agora?"""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            descricao_do_alto_falante,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            rotulo_envelheceu,
        )

        no_ar = getattr(no, "descricao", None)  # (noqa-acento) nome de atributo
        if not isinstance(no_ar, str) or not no_ar:
            return False
        try:
            de_agora = descricao_do_alto_falante(uniq)
        except Exception:
            logger.debug("som_rotulo_de_agora_ilegivel", uniq=uniq, exc_info=True)
            return False
        if not rotulo_envelheceu(no_ar, de_agora):
            return False
        if self._esta_tocando(no):
            logger.info(
                "som_rotulo_velho_espera_o_silencio",
                uniq=uniq,
                no_ar=no_ar,
                de_agora=de_agora,
            )
            return False
        logger.info(
            "som_rotulo_envelheceu", uniq=uniq, no_ar=no_ar, de_agora=de_agora
        )
        return True

    def _esta_tocando(self, no: Any) -> bool:
        """Alguém está mandando som para este nó AGORA — ou não dá para saber."""
        estado = getattr(no, "estado", None)
        if not callable(estado):
            return False
        try:
            atual = estado()
        except Exception:  # pragma: no cover - defensivo
            return True
        if atual is None:
            return True
        return str(atual).strip().upper() == "RUNNING"

    def _ponte_do_radio(self, uniq: str) -> Any:
        """O callable que diz se a ponte DESTE controle está no ar — ou `None`."""
        if self._ponte_do_radio_por_controle is None:
            return None
        try:
            return self._ponte_do_radio_por_controle(uniq)
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_ponte_do_radio_ilegivel", uniq=uniq, exc_info=True)
            return None

    def _fonte_do_no(self, uniq: str) -> str:
        """``mix`` ou ``sfx`` para este controle — o padrão de produto quando ninguém disse."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_PADRAO

        if self._fonte_por_controle is None:
            return FONTE_PADRAO
        try:
            return self._fonte_por_controle(uniq) or FONTE_PADRAO
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_fonte_ilegivel", uniq=uniq, exc_info=True)
            return FONTE_PADRAO

    def reconciliar(self, controles: list[Any] | None = None) -> None:
        """Casa os nós vivos com a lista de controles recebida."""
        vistos: dict[str, str] = {}
        for item in controles or []:
            uniq = item if isinstance(item, str) else str(getattr(item, "uniq", ""))
            if not uniq or uniq in vistos:
                continue
            transporte = (
                "" if isinstance(item, str) else str(getattr(item, "transporte", ""))
            )
            vistos[uniq] = transporte
        alvos = list(vistos)
        mesa = tuple(alvos)
        for uniq in list(self._nos):
            if uniq not in alvos:
                self._derrubar(uniq)
        for uniq in alvos:
            transporte = vistos[uniq] or TRANSPORTE_CABO
            if uniq in self._nos and self._o_rotulo_envelheceu(uniq, self._nos[uniq]):
                self._republicar(uniq, transporte, mesa)
            if uniq in self._nos:
                self._reafinar(uniq, self._nos[uniq], transporte, mesa)
                continue
            no = self._erguer(uniq, transporte, mesa)
            if no is not None:
                self._nos[uniq] = no

    def _erguer(
        self,
        uniq: str,
        transporte: str,
        mesa: tuple[str, ...],
        *,
        descricao: str | None = None,
    ) -> Any:
        """Constrói e SOBE o nó daquele controle. `None` = não subiu."""
        no = self._construir(uniq, transporte, mesa, descricao=descricao)
        # aqui poria uma entrada MUDA por DualSense na lista de som do usuário;
        rota = getattr(no, "rota", None)
        if rota is not None and not getattr(rota, "tem_rota", True):
            logger.info(
                "som_no_sem_rota",
                uniq=uniq,
                motivo=str(getattr(rota, "motivo", "")),
            )
            return None
        try:
            subiu = bool(no.iniciar())
        except Exception as exc:
            logger.debug("som_no_falhou", uniq=uniq, err=str(exc))
            return None
        if not subiu:
            logger.info("som_no_nao_subiu", uniq=uniq)
            return None
        return no

    def _republicar(self, uniq: str, transporte: str, mesa: tuple[str, ...]) -> bool:
        """O nó renasce com o rótulo de agora. False = ficou exatamente como estava."""
        velho = self._nos.get(uniq)
        if velho is None:
            return False
        no_ar = getattr(velho, "descricao", None)  # (noqa-acento) nome de atributo
        try:
            novo = self._construir(uniq, transporte, mesa)
        except Exception:
            logger.debug("som_rotulo_novo_ilegivel", uniq=uniq, exc_info=True)
            return False
        rota = getattr(novo, "rota", None)
        if rota is not None and not getattr(rota, "tem_rota", True):
            logger.info(
                "som_rotulo_velho_espera_a_rota",
                uniq=uniq,
                motivo=str(getattr(rota, "motivo", "")),
            )
            return False
        self._derrubar(uniq)
        try:
            subiu = bool(novo.iniciar())
        except Exception as exc:
            logger.debug("som_no_falhou", uniq=uniq, err=str(exc))
            subiu = False
        if subiu:
            self._nos[uniq] = novo
            return True
        logger.warning("som_rotulo_velho_nao_renasceu", uniq=uniq, no_ar=str(no_ar or ""))
        de_volta = self._erguer(
            uniq, transporte, mesa, descricao=str(no_ar) if no_ar else None
        )
        if de_volta is not None:
            self._nos[uniq] = de_volta
            logger.info("som_no_voltou_com_o_rotulo_velho", uniq=uniq)
        else:
            logger.warning("som_no_sumiu_ao_republicar", uniq=uniq)
        return False

    def _derrubar(self, uniq: str) -> None:
        no = self._nos.pop(uniq, None)
        if no is None:
            return
        with contextlib.suppress(Exception):
            no.parar()
        logger.info("som_no_derrubado", uniq=uniq)

    def dormir(self, segundos: float) -> bool:
        """True quando é para parar. Bloqueia num Event, nunca num sleep."""
        return self._acordar.wait(segundos)

    def parar(self) -> None:
        """Derruba todos os nós. Idempotente."""
        for uniq in list(self._nos):
            self._derrubar(uniq)
        self._acordar.set()


def _uniq_de_perfil(uniq: str) -> str:
    """O `uniq` na grafia que o PERFIL usa: doze hex minúsculos, sem separador."""
    return "".join(c for c in uniq.lower() if c in "0123456789abcdef")[:12]


def _carimbo_do_perfil(nome: str) -> Any:
    """`(mtime_ns do perfil, selo do maquina.json)` — `None` quando não dá para saber."""
    try:
        from hefesto_dualsense4unix.profiles.loader import _profile_path
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            selo_da_maquina,
        )

        return (Path(_profile_path(nome)).stat().st_mtime_ns, selo_da_maquina())
    except Exception:
        return None


def _fontes_por_controle(nome: str) -> dict[str, str]:
    """`{uniq: "mix"|"sfx"}` dos overrides daquele perfil. `{}` é honesto."""
    try:
        from hefesto_dualsense4unix.profiles.loader import load_profile
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        perfil = o_que_vale(load_profile(nome))
    except Exception:
        logger.debug("som_perfil_ilegivel", perfil=nome, exc_info=True)
        return {}

    fontes: dict[str, str] = {}
    for chave, override in (getattr(perfil, "controllers", None) or {}).items():
        alto_falante = getattr(override, "speaker", None)
        fonte = getattr(alto_falante, "fonte", None)
        if fonte:
            fontes[_uniq_de_perfil(str(chave))] = str(fonte)
    return fontes


def controles_na_lista(raiz: str | None = None) -> list[ControleNaLista]:
    """Todo DualSense que o sysfs mostra, **nos dois transportes**.

    A metade de entrada só precisa dos de Bluetooth (o microfone no cabo já
    funciona sozinho); aqui a pergunta é outra e a resposta tem de ser dos
    dois lados, porque o nó existe justamente para não mudar quando o controle
    troca de braço.

    Reusa a leitura de ``uevent`` e as constantes de identidade da ENTRADA em
    vez de reimplementá-las — três instrumentos respondendo *"isto é um
    DualSense?"* de três jeitos é como esta casa já fabricou uma resposta
    errada, e o precedente tem nome (``identidade_do_vpad.py``). Os nomes com
    ``_`` são privados daquele módulo: a alternativa seria redigitar o vendor,
    os dois produtos e o parser aqui, que é a duplicação que a regra proíbe.
    Import tardio para que importar o subsystem não arraste a libopus nem o
    ``pactl`` — mesma razão do import tardio da metade de entrada.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as entrada

    achados: list[ControleNaLista] = []
    try:
        entradas = sorted(Path(raiz or entrada._SYSFS_HIDRAW).iterdir())
    except OSError:
        return achados
    for item in entradas:
        info = entrada._uevent(item)
        partes = info.get("HID_ID", "").split(":")
        if len(partes) != 3:
            continue
        try:
            bus, vendor, produto = (int(p, 16) for p in partes)
        except ValueError:
            continue
        if vendor != entrada._VENDOR_SONY or produto not in entrada._PRODUTOS_DUALSENSE:
            continue
        if info.get("HID_PHYS", "") == entrada._PHYS_VPAD:
            continue
        achados.append(
            ControleNaLista(
                uniq=info.get("HID_UNIQ", ""),
                caminho=f"/dev/{item.name}",
                transporte="rádio" if bus == entrada._BUS_BLUETOOTH else "cabo",
            )
        )
    return achados


class AltoFalanteSubsystem:
    """Mantém um nó de som por DualSense presente, em qualquer transporte."""

    name = "alto_falante"

    _retrato_do_jogo: Any = None
    _lidos_pelo_evdev: frozenset[str] = frozenset()
    _portao_fechado: Mapping[str, str] = MappingProxyType({})
    _donos_da_volta: frozenset[str] | None = None
    _no_radio: frozenset[str] = frozenset()
    _o_que_a_volta_viu: frozenset[str] | None = None
    _volta_pedida: bool = False
    #: ``{uniq: marca do aparelho}`` de cada DualSense da mesa na última volta
    _aparelho_de: Mapping[str, str] = MappingProxyType({})
    _endpoint_da_ponte: Mapping[str, str] = MappingProxyType({})
    #: ``{uniq: o bloco da háptica vai ao fio}`` de cada ponte do rádio, relido
    #: a cada volta e lido pela ponte a cada quadro (sem derrubá-la).
    _leva_da_ponte: Mapping[str, bool] = MappingProxyType({})
    _cabo: Any = None
    _ouvidos_das_placas: Mapping[str, Any] = MappingProxyType({})
    _tocadores: Mapping[str, Any] = MappingProxyType({})
    _rumble_vivo: Mapping[str, tuple[Any, tuple[str | None, bool, bool]]] = MappingProxyType({})
    _clientes_do_rumble: frozenset[str] = frozenset()
    _aparelhos_com_jogo: frozenset[str] = frozenset()
    _sem_registro_no_jogo: frozenset[str] = frozenset()
    _teste_da_haptica: Mapping[str, float] = MappingProxyType({})
    _com_haptica_de_audio: frozenset[str] = frozenset()
    _trava_do_rumble = threading.Lock()

    #: O ``state_full`` lê a amostra de ar DELE — um medidor só no daemon.
    governador: Any = None
    _esperando_vaga: frozenset[tuple[str, str]] = frozenset()

    def __init__(
        self,
        *,
        gerenciador: Any = None,
        fonte_de_controles: Any = None,
        daemon: Any = None,
        governador: Any = None,
    ) -> None:
        self._daemon: Any = daemon
        self._governador_injetado = governador
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        self._pontes: dict[str, Any] = {}
        #: DualSense da mesa, nos dois transportes, desde a
        self._endpoints: dict[str, Any] = {}
        self._modo_da_ponte: dict[str, str] = {}
        self._ponte_recusada: dict[str, float] = {}
        self._faltam_ancoras = 0
        self._fontes_em_cache: tuple[dict[str, str], Any] = ({}, None)
        self._fonte_viva: dict[str, str] = {}
        self._store: Any = None
        self._fonte = fonte_de_controles or controles_na_lista
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._backend: Any = None
        self._numerador_anterior: Any = Ellipsis
        self._dizedor_anterior: Any = None
        self._acordar = threading.Event()
        self._ouvinte: threading.Thread | None = None
        from hefesto_dualsense4unix.integrations.alto_falante_bt import OUVIDO

        OUVIDO.escutar(self._acordar_a_volta)


    def is_enabled(self, config: DaemonConfig) -> bool:
        """Sempre. O nó tem de estar no ar antes de o jogo escolher a saída."""
        del config
        return True

    def alvos(self, controles: list[Any]) -> list[Any]:
        """Os controles que ganham nó — os que têm identidade legível."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        vistos: list[Any] = []
        conhecidos: set[str] = set()
        for controle in controles:
            uniq = str(getattr(controle, "uniq", "") or "")
            if not nome_do_sink(uniq) or uniq in conhecidos:
                continue
            conhecidos.add(uniq)
            vistos.append(controle)
        return vistos

    def _controles_da_mesa(self) -> list[dict[str, Any]]:
        """``describe_controllers()`` do backend, ou ``[]`` quando ele não sabe."""
        descrever = getattr(self._backend, "describe_controllers", None)
        if not callable(descrever):
            return []
        try:
            itens = descrever()
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_mesa_ilegivel", exc_info=True)
            return []
        if not isinstance(itens, list):
            return []
        return [item for item in itens if isinstance(item, dict)]

    def numero_do_assento(self, uniq: str) -> int | None:
        """O «Controle N» deste controle — o MESMO que a tela imprime no cartão.

        **A DÍVIDA DAS DUAS IMPLEMENTAÇÕES MORREU EM 12/09/2026**
        (TRES-CONTAS-PARA-UM-NUMERO-01). Esta função e a
        ``BtMicSubsystem.numero_do_assento`` eram a MESMA regra escrita duas
        vezes, e a régua que as amarrava era o que sobrava por não haver um dono
        só. Agora as duas chamam
        ``subsystems/base.numero_do_assento_na_mesa`` — e aquela função não
        conta nada: **ela pergunta o ``player_slot`` ao dono**, o
        ``identity_registry``, e aplica a regra da casa.

        Os dois rótulos que ela lê — «Alto-falante do Controle N» e «Microfone
        do Controle N» — continuam obrigados a dizer o MESMO número sobre o
        MESMO aparelho, lado a lado na mesma lista de som. Agora eles o dizem
        porque é o mesmo código, não porque duas cópias combinaram.

        E o número passou a ser o da TELA. Antes era a posição entre os
        conectados, que é a ordem dos HANDLES — na bancada, às 22h de 09/09,
        isso batizou de «Microfone do Controle 2» o aparelho cujo cartão dizia
        P1.

        **CONTINUA NÃO SENDO ``coop.resolve_player_numbers``:** com o co-op
        desligado ele responde ``1`` para todos, e a lista dela ganharia quatro
        «Alto-falante do Controle 1».

        Sem daemon vivo não há número: ``None`` é *"não sei"*, e o rótulo nasce
        sem número — nunca com um inventado.
        """
        return numero_do_assento_na_mesa(
            [i for i in self._controles_da_mesa() if i.get("connected")],
            uniq,
            daemon=self._daemon,
        )

    def uniqs_com_no(self) -> frozenset[str]:
        """Os ``uniq`` cujo nó está DE PÉ agora — o efeito, não o pedido."""
        gerenciador = self._gerenciador
        if gerenciador is None:
            return frozenset()
        try:
            return frozenset(gerenciador.nos)
        except Exception:  # best-effort: o relato nunca derruba o state_full
            logger.debug("som_nos_ilegiveis", exc_info=True)
            return frozenset()

    def pontes_de_pe(self) -> dict[str, str]:
        """``{uniq: "som" | "haptica"}`` das pontes do rádio NO AR agora."""
        try:
            pontes = dict(self._pontes)
            modos = dict(self._modo_da_ponte)
        except RuntimeError:
            return {}
        saida: dict[str, str] = {}
        for uniq, ponte in pontes.items():
            modo = modos.get(uniq)
            if modo not in ("som", "haptica"):
                continue
            try:
                de_pe = bool(ponte.esta_de_pe())
            except Exception:  # best-effort: o relato nunca derruba o state_full
                continue
            if de_pe:
                saida[uniq] = modo
        return saida


    def _fonte_do_controle(self, uniq: str) -> str:
        """`mix` ou `sfx` para ESTE controle, lido do perfil ativo dela."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_PADRAO

        viva = self._fonte_viva.get(_uniq_de_perfil(uniq))
        if viva:
            return viva
        fontes = self._fontes_do_perfil()
        return fontes.get(_uniq_de_perfil(uniq)) or FONTE_PADRAO

    def escolher_a_fonte(self, uniq: str, fonte: str) -> bool:
        """`mix` ou `sfx` para ESTE controle, valendo no nó que já está de pé."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            FONTE_MIX,
            FONTE_SFX,
        )

        if fonte not in (FONTE_MIX, FONTE_SFX):
            return False
        self._fonte_viva[_uniq_de_perfil(uniq)] = fonte
        logger.info("som_fonte_escolhida", uniq=uniq, fonte=fonte)
        return True

    def fonte_escolhida(self, uniq: str) -> str:
        """A fonte que vale para este controle AGORA — a viva, ou a do perfil."""
        return self._fonte_do_controle(uniq)

    def _fontes_do_perfil(self) -> dict[str, str]:
        """`{uniq: fonte}` do perfil ativo — e `{}` é resposta honesta."""
        from hefesto_dualsense4unix.utils.session import load_last_profile

        try:
            nome = (
                getattr(getattr(self, "_store", None), "active_profile", None)
                or load_last_profile()
            )
        except Exception:  # pragma: no cover - defensivo
            nome = None
        if not nome:
            self._fontes_em_cache = ({}, None)
            return {}

        carimbo = _carimbo_do_perfil(nome)
        cacheado, chave = self._fontes_em_cache
        if chave == (nome, carimbo):
            return cacheado

        fontes = _fontes_por_controle(nome)
        self._fontes_em_cache = (fontes, (nome, carimbo))
        logger.debug("som_fontes_relidas", perfil=nome, controles=len(fontes))
        return fontes


    def _ponte_do_radio_de(self, uniq: str) -> Any:
        """O callable que diz se este controle TEM CAMINHO pelo rádio."""
        ponte = self._pontes.get(uniq)
        if ponte is not None:
            return ponte.esta_de_pe
        quando = self._ponte_recusada.get(uniq)
        if quando is not None:
            if time.monotonic() - quando < RECUSA_DA_PONTE_S:
                return None
            self._ponte_recusada.pop(uniq, None)
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            a_ponte_do_radio_pode_subir,
            ha_gravador_de_monitor,
        )

        pode, _porque = a_ponte_do_radio_pode_subir()
        if not pode or not ha_gravador_de_monitor():
            return None
        return lambda: True

    def _renovar_o_rotulo_da_haptica(self, endpoint: Any) -> None:
        """O «Háptica do Controle N» segue o número — e NUNCA com jogo aberto."""
        envelheceu = getattr(endpoint, "rotulo_envelheceu", None)
        renovar = getattr(endpoint, "renovar_o_rotulo", None)
        if not callable(envelheceu) or not callable(renovar):
            return
        try:
            if not envelheceu():
                return
            if self._a_haptica_esta_em_uso(endpoint):
                logger.debug("haptica_rotulo_velho_espera_o_jogo_fechar")
                return
            renovar()
        except Exception:
            logger.debug("haptica_rotulo_nao_renovou", exc_info=True)
        if getattr(endpoint, "module_id", "") is None:
            self._endpoints.pop(str(getattr(endpoint, "marca", "") or ""), None)

    def _a_haptica_esta_em_uso(self, endpoint: Any) -> bool:
        """Há jogo usando — ou podendo usar — o endpoint de háptica agora?"""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            sink_esta_tocando,
        )

        nome = str(getattr(endpoint, "nome", "") or "")
        if nome and nome in {self._endpoint_da_ponte.get(u) for u in self._pontes}:
            return True
        if sink_esta_tocando(nome, na_duvida=True):
            return True
        return self._ha_jogo_aberto()

    def _ha_jogo_aberto(self) -> bool:
        """Algum processo da máquina é um jogo, pelo ambiente e não pelo nome.

        É a pergunta de ``quem_o_jogo_le.pids_de_jogo``, e ela não depende de
        lista de jogos nem de lançador.
        """
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import pids_de_jogo

        try:
            return bool(pids_de_jogo())
        except Exception:  # pragma: no cover - defensivo: na dúvida, há jogo
            return True

    def _aparelhos_da_mesa(self, controles: list[Any]) -> dict[str, str]:
        """``{uniq: marca}`` de cada DualSense da mesa. Um aparelho por controle.

        A-HAPTICA-E-POR-APARELHO-01, 02/10/2026: a marca é a do aparelho
        (``dualsense_bt_audio.marca_do_aparelho``), e não o número dele. De
        28/09 a 02/10 aqui morava o ``_lugares_da_mesa``, que sentava cada
        controle num dos quatro lugares pelo número do dono; o número anda com
        a mesa, e a háptica do aparelho não anda junto. Quem não dá identidade
        (sem ``uniq`` de seis hex) fica fora: um endpoint anônimo seria de dois.
        """
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            marca_do_aparelho,
        )

        postos: dict[str, str] = {}
        tomadas: set[str] = set()
        for uniq in sorted({str(getattr(c, "uniq", "") or "") for c in controles} - {""}):
            marca = marca_do_aparelho(uniq)
            if marca and marca not in tomadas:
                postos[uniq] = marca
                tomadas.add(marca)
        self._aparelho_de = MappingProxyType(dict(postos))
        return postos

    def _endpoint_de(self, uniq: str) -> Any:
        """O endpoint do aparelho deste controle, ou ``None``."""
        marca = self._aparelho_de.get(uniq)
        return None if marca is None else self._endpoints.get(marca)

    def _aparelhos_de_pe(self, aparelho_de: Mapping[str, str]) -> dict[str, str]:
        """``{marca: uniq}`` dos endpoints que ficam de pé nesta volta.

        Um por DualSense da mesa, em qualquer transporte; e o do aparelho que
        SAIU fica enquanto um jogo toca nele: o nó que some debaixo do jogo
        leva a háptica da partida junto (a decisão de 08/09, «nó que some
        quebra o jogo que o escolheu»). Servidor mudo é «toca» — na dúvida, o
        nó fica.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import sink_esta_tocando

        de_pe = {marca: uniq for uniq, marca in aparelho_de.items()}
        for marca, endpoint in list(self._endpoints.items()):
            if marca in de_pe:
                continue
            if sink_esta_tocando(str(getattr(endpoint, "nome", "") or ""), na_duvida=True):
                de_pe[marca] = str(getattr(endpoint, "uniq", "") or "")
        return de_pe

    def _avisar_quem_o_jogo_nao_conhece(self, marca: str) -> None:
        """O endpoint que nasce com um jogo tocando: o registro do lançamento não o tem.

        A-HAPTICA-E-POR-APARELHO-01, item 5 — o preço que o usuário aceitou na
        pergunta [27]: o device KS se grava no lançamento, e o aparelho que
        chega com o jogo aberto ganha um endpoint que o jogo não conhece até
        reabrir. Uma linha por aparelho e partida, para a bancada e o doctor
        saberem por quê. A partida é a da volta anterior: algum jogo dono de
        fluxo nos endpoints (:meth:`_donos_dos_fluxos`).
        """
        if not self._donos_da_volta or marca in self._sem_registro_no_jogo:
            return
        self._sem_registro_no_jogo = self._sem_registro_no_jogo | {marca}
        logger.info("haptica_aparelho_sem_registro_no_jogo", controle=marca)

    def _o_cabo(self) -> Any:
        """O dono dos laços do cabo, criado na primeira vez que se pede."""
        if self._cabo is None:
            from hefesto_dualsense4unix.integrations.haptica_do_cabo import HapticaDoCabo

            self._cabo = HapticaDoCabo()
        return self._cabo


    def levar_o_rumble(
        self,
        uniq: str,
        fraco: int,
        forte: int,
        *,
        reaplicar: Callable[[], object] | None = None,
    ) -> bool:
        """O rumble de um pad sem háptica vira háptica no endpoint do aparelho de ``uniq``."""
        if not self._tocadores and not (fraco or forte):
            return False
        chave = self._chave_do_rumble(uniq)
        quer = chave is not None and self._quer_a_haptica_fina(chave)
        marca = self._aparelho_de.get(chave) if chave is not None else None
        for outro, tocador in list(self._tocadores.items()):
            if any(tocador.nivel) and _mesmo_controle(tocador.dono, uniq) and (
                not quer or outro != marca
            ):
                tocador.calar()
        if not quer or chave is None or marca is None:
            self._esquecer_o_rumble(uniq)
            return False
        endpoint = self._endpoints.get(marca)
        self._tocador_do_aparelho(marca).levar(
            fraco, forte, sink=str(getattr(endpoint, "nome", "") or ""), dono=chave
        )
        retrato = self._retrato_do_rumble(chave)
        with self._trava_do_rumble:
            vivos = {u: v for u, v in self._rumble_vivo.items() if u != chave}
            if fraco or forte:
                vivos[chave] = (reaplicar, retrato)
            self._rumble_vivo = MappingProxyType(vivos)
        return retrato[2]

    def testar_a_haptica(self, uniq: str, ligado: bool) -> dict[str, Any]:
        """O botão «Háptica» da aba Vibração: o par de teste no tocador DESTE controle."""
        chave = self._chave_do_rumble(uniq)
        if chave is None:
            return {
                "status": "sem_controle",
                "motivo": "este controle não está na mesa, ou não tem háptica",
            }
        if not ligado:
            self._soltar_o_teste_da_haptica(chave)
            return {"status": "ok", "uniq": chave, "ligado": False, "leva": False}
        with self._trava_do_rumble:
            self._teste_da_haptica = MappingProxyType(
                {**self._teste_da_haptica, chave: time.monotonic()}
            )
        leva = self.levar_o_rumble(chave, *PAR_DO_TESTE_DA_HAPTICA)
        self._acordar_a_volta()
        return {
            "status": "ok",
            "uniq": chave,
            "ligado": True,
            "leva": bool(leva),
            "par": list(PAR_DO_TESTE_DA_HAPTICA),
        }

    def _soltar_o_teste_da_haptica(self, chave: str) -> None:
        """O tocador deste controle cala, e o teste sai da lista."""
        with self._trava_do_rumble:
            self._teste_da_haptica = MappingProxyType(
                {u: t for u, t in self._teste_da_haptica.items() if u != chave}
            )
        self.levar_o_rumble(chave, 0, 0)

    def _conferir_o_teste_da_haptica(self) -> None:
        """O teste que a janela deixou de rebater solta: o tocador não fica preso ligado."""
        if not self._teste_da_haptica:
            return
        from hefesto_dualsense4unix.daemon.subsystems.rumble import TETO_DO_RUMBLE_FIXADO_S

        agora = time.monotonic()
        for chave, quando in list(self._teste_da_haptica.items()):
            if agora - quando > TETO_DO_RUMBLE_FIXADO_S:
                logger.info("haptica_teste_solto_sem_rebate", controle=self._aparelho_de.get(chave))
                self._soltar_o_teste_da_haptica(chave)

    def _retrato_do_rumble(self, chave: str) -> tuple[str | None, bool, bool]:
        """``(marca, quer a háptica fina, a háptica leva)`` deste controle agora."""
        return (
            self._aparelho_de.get(chave),
            self._quer_a_haptica_fina(chave),
            self._a_haptica_leva(chave),
        )

    def _esquecer_o_rumble(self, uniq: str) -> None:
        with self._trava_do_rumble:
            if any(_mesmo_controle(u, uniq) for u in self._rumble_vivo):
                self._rumble_vivo = MappingProxyType({
                    u: v for u, v in self._rumble_vivo.items() if not _mesmo_controle(u, uniq)
                })

    def _chave_do_rumble(self, uniq: str) -> str | None:
        """O ``uniq`` na grafia da mesa (a chave de :attr:`_aparelho_de`), pelos dígitos."""
        if uniq in self._aparelho_de:
            return uniq
        for chave in list(self._aparelho_de):
            if _mesmo_controle(chave, uniq):
                return chave
        return None

    def _tocador_do_aparelho(self, marca: str) -> Any:
        """O tocador do aparelho, criado no primeiro rumble que o pede."""
        tocador = self._tocadores.get(marca)
        if tocador is not None:
            return tocador
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica

        with self._trava_do_rumble:
            tocador = self._tocadores.get(marca)
            if tocador is None:
                tocador = endpoint_de_haptica.TocadorDoRumble(
                    marca, ao_mudar=self._acordar_a_volta
                )
                self._tocadores = MappingProxyType({**self._tocadores, marca: tocador})
        return tocador

    def _parar_o_tocador(self, marca: str) -> None:
        """O tocador sai ANTES do endpoint do aparelho, como o laço e a ponte."""
        tocador = self._tocadores.get(marca)
        if tocador is None:
            return
        with self._trava_do_rumble:
            self._tocadores = MappingProxyType(
                {n: t for n, t in self._tocadores.items() if n != marca}
            )
        tocador.parar()

    def _quer_a_haptica_fina(self, chave: str) -> bool:
        """O aparelho tem endpoint, o jogo não toca nele, e a háptica dele não está em 0."""
        marca = self._aparelho_de.get(chave)
        if marca is None or marca in self._aparelhos_com_jogo:
            return False
        endpoint = self._endpoints.get(marca)
        return bool(
            endpoint is not None and GANHO.pct(chave) > 0
            and getattr(endpoint, "module_id", None) is not None
            and getattr(endpoint, "nome", "")
        )

    def _recebe_o_rumble(self, uniq: str) -> bool:
        """O tocador do aparelho deste controle está de pé tocando o rumble DELE."""
        if not self._tocadores:
            return False
        chave = self._chave_do_rumble(uniq)
        if chave is None or not self._quer_a_haptica_fina(chave):
            return False
        marca = self._aparelho_de.get(chave)
        tocador = self._tocadores.get(marca) if marca is not None else None
        return bool(tocador is not None and tocador.vivo and tocador.dono == chave)

    def _a_haptica_leva(self, chave: str) -> bool:
        """O caminho do tocador ao controle está de pé AGORA, e é o deste controle."""
        if not self._recebe_o_rumble(chave):
            return False
        marca = self._aparelho_de.get(chave)
        cabo = self._cabo
        if cabo is not None and marca is not None:
            rota = cabo.aparelhos().get(marca)
            if rota is not None and getattr(rota, "dono", "") == chave:
                return cabo.portao(marca) is True
        ponte = self._pontes.get(chave)
        endpoint = self._endpoints.get(marca) if marca is not None else None
        if ponte is None or endpoint is None:
            return False
        if not self._a_ponte_leva_a_haptica(chave):
            return False
        if self._endpoint_da_ponte.get(chave) != getattr(endpoint, "nome", None):
            return False
        de_pe = getattr(ponte, "esta_de_pe", None)
        try:
            return bool(de_pe()) if callable(de_pe) else False
        except Exception:
            return False

    def _ver_quem_toca_nos_endpoints(self) -> None:
        """Quem toca nos endpoints além dos nossos tocadores — só com tocador na mesa."""
        if not self._tocadores:
            self._clientes_do_rumble = frozenset()
            return
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
            fluxos_nos_endpoints,
        )

        nomes = {
            marca: str(getattr(ep, "nome", "") or "")
            for marca, ep in list(self._endpoints.items())
        }
        try:
            lido = fluxos_nos_endpoints([n for n in nomes.values() if n])
        except Exception as exc:
            logger.debug("haptica_fina_fluxos_ilegiveis", err=str(exc))
            lido = None
        if lido is None:
            return
        nossos, com_outro = lido
        self._clientes_do_rumble = nossos
        self._aparelhos_com_jogo = frozenset(
            marca for marca, nome in nomes.items() if nome and nome in com_outro
        )

    def _conferir_os_tocadores(self, aparelho_de: Mapping[str, str]) -> None:
        """O tocador cujo dono saiu da mesa cala: não há controle a quem levá-lo."""
        for marca, tocador in list(self._tocadores.items()):
            dono = tocador.dono
            if dono and any(tocador.nivel) and aparelho_de.get(dono) != marca:
                tocador.calar()

    def _conferir_o_rumble(self) -> None:
        """Quem tem rumble vivo e viu o caminho abrir, fechar ou trocar reaplica."""
        from hefesto_dualsense4unix.daemon.battery_journal import mascarar_endereco

        for chave, (reaplicar, antes) in dict(self._rumble_vivo).items():
            agora = self._retrato_do_rumble(chave)
            if agora == antes or not callable(reaplicar):
                continue
            logger.info(
                "haptica_fina_do_rumble_mudou",
                uniq=mascarar_endereco(chave),
                controle=agora[0],
                leva=agora[2],
            )
            try:
                reaplicar()
            except Exception as exc:
                logger.debug("haptica_fina_reaplicar_falhou", err=str(exc))

    def _o_jogo_manda_nos_motores(self) -> bool:
        """No Modo Nativo o dono dos motores é o jogo, no cabo E no rádio."""
        from hefesto_dualsense4unix.daemon.subsystems import rumble

        return rumble.modo_nativo_manda_nos_motores(getattr(self, "_daemon", None))

    def _casar_o_cabo(
        self,
        controles: list[Any],
        jogando: set[str],
        motores: list[str] | None,
    ) -> None:
        """Um laço por DualSense no cabo, do endpoint do aparelho à placa dele.

        A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01, itens 3 e 4, pelo aparelho desde
        a A-HAPTICA-E-POR-APARELHO-01 (02/10/2026). Os motores do laço
        (os traseiros) abrem só para quem joga — a escolha (b) dela, a mesma
        do rádio; a frente (o alto-falante) passa sempre. A placa é a do dono
        (``alto_falante_bt.sink_do_controle``), e só vale se for uma placa de
        quatro canais que não é nossa (``motores``, a leitura da volta): sem
        ela o controle segue pela placa, sem laço, e o registro lhe dá o bloco
        pelo ``BUSNUM-DEVNUM`` (``audio_ks_dualsense.controles_do_registro``).

        ``motores`` ``None`` é o servidor que não respondeu: o laço de quem
        segue no cabo FICA como está — ele é um processo do
        PipeWire, e não depende do ``pipewire-pulse`` que travou. Só cai o de
        quem saiu do cabo, que o ``/sys`` diz sem perguntar ao servidor.

        **NO MODO NATIVO O DONO DOS MOTORES É O JOGO** (NO-MODO-XBOX-TUDO-
        FUNCIONA-01, parte 4, 29/09/2026): o co-op desmonta e o daemon só lê o
        físico do posto (o limite de ``quem_mexe.py``), e a (b) fechava os
        motores dos secundários, que vibravam direto pela placa até 28/09. O
        laço abre os motores de todo controle no cabo, e quem responde é o
        mesmo dono das três portas do rumble
        (``rumble.modo_nativo_manda_nos_motores``), a cada volta.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            e_radio,
            sink_do_controle,
            sink_esta_tocando,
        )
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import MARCA_DO_NOME
        from hefesto_dualsense4unix.integrations.haptica_do_cabo import (
            RotaDoCabo,
            alvo_do_no,
        )

        o_jogo_manda = self._o_jogo_manda_nos_motores()

        def _abre(uniq: str) -> bool:
            return o_jogo_manda or uniq.lower() in jogando or self._recebe_o_rumble(uniq)

        na_mesa = [str(getattr(c, "uniq", "") or "") for c in controles]
        na_mesa = [u for u in na_mesa if u]
        no_cabo = [
            str(getattr(c, "uniq", "") or "")
            for c in controles
            if not e_radio(str(getattr(c, "transporte", "") or ""))
        ]
        cabo = self._cabo
        if not [u for u in no_cabo if u] and (cabo is None or not cabo.aparelhos()):
            self._casar_os_ouvidos_das_placas({})
            return
        rotas: dict[str, Any] = {}
        abertos: set[str] = set()
        if motores is None:
            antes = cabo.aparelhos() if cabo is not None else {}
            for marca, rota in antes.items():
                dono = str(getattr(rota, "dono", "") or "")
                if dono in no_cabo and self._aparelho_de.get(dono) == marca:
                    rotas[marca] = rota
                    if _abre(dono):
                        abertos.add(marca)
            logger.debug("haptica_do_cabo_servidor_mudo", ficam=sorted(rotas))
            self._o_cabo().casar(rotas, abertos)
            return
        placas = set(motores)
        ouvir: dict[str, str] = {}
        for uniq in no_cabo:
            placa = sink_do_controle(uniq, na_mesa) if uniq else ""
            if not placa or placa not in placas or MARCA_DO_NOME in placa:
                continue
            ouvir[uniq] = placa
            marca = self._aparelho_de.get(uniq)
            endpoint = self._endpoint_de(uniq)
            if marca is None or endpoint is None or getattr(endpoint, "module_id", None) is None:
                continue
            captura, destino = alvo_do_no(str(endpoint.nome)), alvo_do_no(placa)
            if not captura or not destino:
                continue
            rotas[marca] = RotaDoCabo(
                captura=captura, destino=destino, origem=str(endpoint.nome), dono=uniq
            )
            este_joga = _abre(uniq)
            if este_joga:
                abertos.add(marca)
            sinal = self._o_no_tem_sinal(str(endpoint.nome))
            self._vigiar_o_portao(
                uniq,
                fechado=(
                    sink_esta_tocando(str(endpoint.nome)) if sinal is None else sinal
                ) and not este_joga,
                controles=controles,
            )
        self._o_cabo().casar(rotas, abertos)
        self._casar_os_ouvidos_das_placas(ouvir)

    def _casar_os_ouvidos_das_placas(self, ouvir: Mapping[str, str]) -> None:
        """Um ouvido por controle no cabo, na placa dele; quem saiu ou trocou de placa desce."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import OuvidoDaPlaca

        vivos = dict(self._ouvidos_das_placas)
        for uniq, ouvido in list(vivos.items()):
            if ouvir.get(uniq) != getattr(ouvido, "placa", None) or not ouvido.vivo:
                vivos.pop(uniq)
                ouvido.descer()
        for uniq, placa in ouvir.items():
            if uniq in vivos:
                continue
            ouvido = OuvidoDaPlaca(placa=placa, uniq=uniq)
            if ouvido.subir():
                vivos[uniq] = ouvido
            else:
                logger.debug("haptica_ouvido_da_placa_sem_fonte", motivo=ouvido.motivo)
        self._ouvidos_das_placas = MappingProxyType(vivos)

    def haptica_no_ar(self, uniq: str) -> bool:
        """Há háptica chegando a ESTE controle agora? LEITURA pura, nunca levanta."""
        try:
            if GANHO.fator(uniq) <= 0:
                return False
            for dono, ouvido in dict(self._ouvidos_das_placas).items():
                if _mesmo_controle(dono, uniq):
                    return self._o_no_tem_sinal(str(ouvido.placa)) is True
            for dono in list(self._pontes):
                if not _mesmo_controle(dono, uniq):
                    continue
                lendo = self._endpoint_da_ponte.get(dono) or ""
                return self._a_ponte_leva_a_haptica(dono) and bool(lendo) and (
                    self._o_no_tem_sinal(lendo) is True
                )
        except Exception:
            logger.debug("haptica_no_ar_ilegivel", exc_info=True)
        return False

    def _o_ganho_nas_placas(self, controles: list[Any], placas: list[str]) -> set[str]:
        """Relê o ganho do perfil e o escreve na placa de cada controle no cabo."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import e_radio

        GANHO.ler_do_daemon(getattr(self, "_daemon", None))
        na_mesa = [u for u in (str(getattr(c, "uniq", "") or "") for c in controles) if u]
        no_cabo = [
            str(getattr(c, "uniq", "") or "")
            for c in controles
            if not e_radio(str(getattr(c, "transporte", "") or ""))
        ]
        return GANHO.escrever_nas_placas(no_cabo, na_mesa, placas)

    def _avisar_ancoras_que_faltam(self, faltam: int, aparelhos: int) -> None:
        """O aparelho sem âncora USB fica sem endpoint — e diz isso.

        **POR APARELHO DESDE 02/10/2026** (A-HAPTICA-E-POR-APARELHO-01; de 28/09
        a 02/10 a conta era por lugar): um endpoint por DualSense da mesa, nos
        dois transportes. O controle sem âncora segue pela placa no cabo e fica
        sem vibração no rádio.

        **INSTALL-UNIVERSAL, 18/09/2026.** O endpoint da háptica precisa de uma
        âncora por controle (um aparelho USB com interface e sem placa de som),
        e o :func:`distribuir_ancoras` só entrega enquanto houver: o que sobra
        era pulado por um ``continue`` mudo. Num desktop sobram âncoras; num
        notebook com a mesa de quatro, podem faltar — e a vibração de um
        jogador sumia sem rastro.

        O aviso sai **na mudança**, porque esta volta roda a cada
        :data:`RECONCILIA_S`, e um aviso por volta encheria o journal. Nada vai
        para a tela (a dívida é nossa, não dela): o ``doctor.sh`` conta as
        mesmas âncoras e diz o gesto.
        """
        if faltam == self._faltam_ancoras:
            return
        if faltam > 0:
            logger.warning("haptica_sem_ancora", faltam=faltam, aparelhos=aparelhos)
        else:
            logger.info("haptica_ancoras_bastam", aparelhos=aparelhos)
        self._faltam_ancoras = faltam

    def _quem_o_jogo_le(self, controles: list[Any]) -> set[str]:
        """Os ``uniq`` (em minúsculas) cujo evdev algum processo de jogo segura. PISTA, NÃO VOTO.

        QUEM-JOGA-E-QUEM-VIBRA-01 (20/09) fez disto o voto do portão da
        háptica. A A-HAPTICA-QUEM-JOGA-02 (26/09) o tirou de lá: o GE não segura
        evdev de DualSense nenhum, e em 21/09 o evdev deixou os QUATRO entrarem
        num jogo de um jogador. **E DESDE 28/09 A PARTIDA TAMBÉM NÃO SAI DAQUI**
        (A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01): quem a abre é o dono
        do fluxo no endpoint (:meth:`_quem_mexeu_na_partida`), e esta
        varredura de ``/proc`` deixou de rodar a cada volta. Ela roda só quando
        a linha ``haptica_portao_fechado`` vai sair (:meth:`_vigiar_o_portao`),
        para dizer o que o jogo segura — é por ela que o detentor de 21/09, se
        voltar, aparece no diário.

        Devolve conjunto VAZIO quando não há jogo, quando `/proc` não se lê, ou
        quando o que o jogo abriu não se traduz em controle nenhum.

        A lista de físicos vem de TODOS os controles da mesa, e não só dos do
        rádio: com máscara, o evdev que o jogo seguraria é o do vpad, e quem o
        alimenta pode ser o do cabo. Quem diz QUEM ALIMENTA cada vpad é o
        co-op, e não a forja do MAC (A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01):
        o MAC diz de quem o vpad nasceu, e o posto troca de mão sem renascer.

        **A pergunta ao co-op tem ``try`` próprio** (A-HAPTICA-QUEM-JOGA-02): ela
        só serve para traduzir o evdev de um vpad, e o erro dela não pode levar
        junto a varredura inteira. Sem tradutor, o vpad não se traduz: nunca se
        chuta um físico.
        """
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import (
            dono_do_vpad_pelo_coop,
            quem_o_jogo_le,
        )

        self._retrato_do_jogo = None
        fisicos = [str(getattr(c, "uniq", "") or "") for c in controles]
        fisicos = [u for u in fisicos if u]
        if not fisicos:
            return set()
        coop = getattr(getattr(self, "_daemon", None), "_coop_manager", None)
        dono: Any = None
        try:
            dono = dono_do_vpad_pelo_coop(coop, fisicos)
        except Exception as erro:
            logger.info("haptica_nao_sei_quem_joga", motivo=str(erro))
        try:
            return quem_o_jogo_le(
                fisicos=fisicos, dono_do_vpad=dono, ao_ver_o_jogo=self._ver_o_jogo
            )
        except Exception as erro:
            logger.info("haptica_nao_sei_quem_joga", motivo=str(erro))
            return set()

    def _ver_o_jogo(self, retrato: Any) -> None:
        """Guarda o que a varredura da pista viu do jogo (ver ``_retrato_do_jogo``)."""
        self._retrato_do_jogo = retrato

    def _donos_dos_fluxos(self) -> frozenset[str] | None:
        """Os clientes do servidor de som que tocam nos endpoints de háptica. ``None`` = não sei."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import donos_dos_fluxos

        nomes = [str(getattr(ep, "nome", "") or "") for ep in self._endpoints.values()]
        nomes = [n for n in nomes if n]
        if not nomes:
            return frozenset()
        try:
            donos = donos_dos_fluxos(nomes)
        except Exception as erro:
            logger.debug("haptica_donos_ilegiveis", err=str(erro))
            return None
        nossos = self._clientes_do_rumble
        if donos is not None and nossos:
            donos = frozenset(d for d in donos if d not in nossos)
        return donos

    def _clientes_vivos(self, donos: frozenset[Any]) -> frozenset[Any] | None:
        """Dos donos de fluxo de antes, os que seguem conectados ao servidor de som."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import clientes_conectados

        try:
            conectados = clientes_conectados()
        except Exception as erro:
            logger.debug("haptica_clientes_ilegiveis", err=str(erro))
            return None
        if conectados is None:
            return None
        return frozenset(d for d in donos if str(d) in conectados)

    def _quem_mexeu_na_partida(self, controles: list[Any]) -> set[str]:
        """Os ``uniq`` (em minúsculas) de quem teve entrada desde que o jogo abriu."""
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import quem_mexe_de
        from hefesto_dualsense4unix.integrations.quem_o_jogo_le import _digitos

        marcas = quem_mexe_de(getattr(self, "_daemon", None))
        if marcas is None:
            return set()
        donos = self._donos_dos_fluxos()
        self._donos_da_volta = donos
        if donos is not None:
            marcas.acompanhar_o_jogo(donos, vivos=self._clientes_vivos)
        mexeram = marcas.quem_joga()
        if not mexeram:
            return set()
        uniqs = (str(getattr(c, "uniq", "") or "") for c in controles)
        return {u.lower() for u in uniqs if u and _digitos(u) in mexeram}

    def _por_que_o_portao_fecha(self) -> str:
        """O motivo de um controle estar fora de quem joga, pela partida da volta."""
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import marcas_da_partida

        if self._donos_da_volta is None:
            return "nao_sei"
        if marcas_da_partida(getattr(self, "_daemon", None)) is None:
            return "sem_jogo"
        return "nao_mexeu"

    def _vigiar_o_portao(self, uniq: str, *, fechado: bool, controles: list[Any]) -> None:
        """A linha ``haptica_portao_fechado``, SÓ quando o estado anômalo muda."""
        anterior = self._portao_fechado.get(uniq)
        if not fechado:
            if anterior is not None:
                self._portao_fechado = {
                    u: m for u, m in self._portao_fechado.items() if u != uniq
                }
            return
        motivo = self._por_que_o_portao_fecha()
        if anterior == motivo:
            return
        self._portao_fechado = {**self._portao_fechado, uniq: motivo}
        from hefesto_dualsense4unix.daemon.battery_journal import mascarar_endereco

        self._lidos_pelo_evdev = frozenset(self._quem_o_jogo_le(controles))
        evdev, hidraw = self._o_que_o_jogo_segura()
        logger.info(
            "haptica_portao_fechado",
            uniq=mascarar_endereco(uniq),
            motivo=motivo,
            evdev_do_jogo=evdev,
            hidraw_de_vpad=hidraw,
            evdev_le_este=uniq.lower() in self._lidos_pelo_evdev,
        )

    def _o_que_o_jogo_segura(self) -> tuple[int | None, int | None]:
        """``(eventN, hidrawN de vpad)`` que o jogo segura, do retrato da pista."""
        retrato = self._retrato_do_jogo
        if retrato is None:
            return None, None
        try:
            from hefesto_dualsense4unix.integrations.quem_o_jogo_le import hidraws_de_vpad

            return len(retrato.eventos), len(hidraws_de_vpad(retrato.hidraws))
        except Exception as exc:
            logger.debug("haptica_portao_sem_contagem", err=str(exc))
            return None, None

    def _casar_as_pontes(self, controles: list[Any]) -> None:
        """Os endpoints dos aparelhos, a ponte de cada controle no rádio e o laço do cabo.

        Roda na thread de reconciliação, junto com os nós — as duas coisas
        respondem à mesma lista, e separá-las abriria a janela em que o nó
        existe e a ponte não (ou o contrário). ``controles`` são os DualSense
        da mesa nos DOIS transportes: cada um tem o endpoint dele
        (A-HAPTICA-E-POR-APARELHO-01, 02/10/2026).
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            CANAIS_DA_HAPTICA,
            PonteDeSomPorRadio,
            e_radio,
            fonte_do_monitor_do_no,
            garantir_motores_audiveis,
            nome_do_sink,
            rodar_pactl,
            sink_esta_tocando,
            sinks_com_motores,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            o_microfone_esta_no_ar,
        )
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
            EndpointDeHaptica,
            ancoras,
            distribuir_ancoras,
            endpoints_de_pe,
            varrer_endpoints_orfaos,
        )

        vivos: dict[str, str] = {}
        for c in controles:
            uniq = str(getattr(c, "uniq", "") or "")
            if uniq and e_radio(str(getattr(c, "transporte", "") or "")):
                vivos[uniq] = str(getattr(c, "caminho", "") or "")

        from hefesto_dualsense4unix.integrations.filho_de_som import (
            derrubar_leitor_de_pipe,
        )

        for uniq in [u for u in self._pontes if u not in vivos]:
            ponte = self._pontes.pop(uniq, None)
            if ponte is not None:
                ponte.descer()
                logger.info("som_ponte_derrubada", uniq=uniq)
        aparelho_de = self._aparelhos_da_mesa(controles)
        de_pe_agora = self._aparelhos_de_pe(aparelho_de)
        self._conferir_os_tocadores(aparelho_de)

        for marca in [m for m in self._endpoints if m not in de_pe_agora]:
            self._o_cabo().soltar(marca)
            self._parar_o_tocador(marca)
            endpoint = self._endpoints.pop(marca, None)
            if endpoint is not None:
                endpoint.parar()
        de_pe: dict[str, list[tuple[str, str]]] | None = None
        with contextlib.suppress(Exception):
            de_pe = endpoints_de_pe()
        with contextlib.suppress(Exception):
            varrer_endpoints_orfaos(de_pe_agora, de_pe=de_pe)

        postas = distribuir_ancoras(
            de_pe_agora, ancoras(), de_pe,
            ja_postas={m: e.ancora for m, e in self._endpoints.items()},
            ocupados=set(aparelho_de.values()),
        )
        for marca, uniq in de_pe_agora.items():
            posta = postas.get(marca)
            atual = self._endpoints.get(marca)
            if atual is not None:
                if posta is None:
                    continue
                if posta.syspath == atual.ancora.syspath:
                    self._renovar_o_rotulo_da_haptica(atual)
                    continue
                lido = {self._endpoint_da_ponte.get(u) for u in self._pontes}
                if atual.nome in lido or sink_esta_tocando(atual.nome, na_duvida=True):
                    continue
                self._o_cabo().soltar(marca)
                self._parar_o_tocador(marca)
                self._endpoints.pop(marca, None)
                atual.parar()
                logger.info("haptica_endpoint_reancorado", controle=marca, ancora=posta.syspath)
            if posta is None or not uniq:
                continue
            endpoint = EndpointDeHaptica(uniq=uniq, ancora=posta)
            if endpoint.iniciar():
                self._endpoints[marca] = endpoint
                if atual is None and getattr(endpoint, "module_id", None) is not None:
                    self._avisar_quem_o_jogo_nao_conhece(marca)
        if not self._donos_da_volta:
            self._sem_registro_no_jogo = frozenset()
        self._avisar_ancoras_que_faltam(
            sum(1 for m in de_pe_agora if m not in self._endpoints and m not in postas),
            len(de_pe_agora),
        )

        motores: list[str] | None = None
        with contextlib.suppress(Exception):
            respostas: list[bool] = []

            def _perguntar(argv: list[str]) -> str | None:
                saida = rodar_pactl(argv)
                respostas.append(saida is not None)
                return saida

            lidos = list(sinks_com_motores(_perguntar))
            motores = lidos if all(respostas) else None
            com_dono = self._o_ganho_nas_placas(controles, lidos)
            for sink_com_motor in placas_do_piso(lidos, com_dono):
                garantir_motores_audiveis(sink_com_motor)

        # PRAGMATA de 26/09 ficou sem ninguém), e em 21/09 o evdev pôs os QUATRO
        self._ver_quem_toca_nos_endpoints()
        jogando = self._quem_mexeu_na_partida(controles)

        self._portao_fechado = {
            u: m for u, m in self._portao_fechado.items() if u in aparelho_de
        }
        # um laço por DualSense no cabo, do endpoint dele à placa, com os
        try:
            self._casar_o_cabo(controles, jogando, motores)
        except Exception:
            logger.warning("haptica_do_cabo_falhou", exc_info=True)

        governador = self.governador
        esperando: set[tuple[str, str]] = set()
        o_jogo_manda = self._o_jogo_manda_nos_motores()
        leva_de: dict[str, bool] = {}
        for uniq, caminho in vivos.items():
            morta = self._pontes.get(uniq)
            terminou = getattr(morta, "terminou_sozinha", None)
            if morta is not None and callable(terminou) and terminou() is True:
                self._pontes.pop(uniq, None)
                self._modo_da_ponte.pop(uniq, None)
                logger.info("som_ponte_terminou_sozinha", uniq=uniq, motivo=morta.motivo)
            endpoint = self._endpoint_de(uniq)
            este_joga = o_jogo_manda or uniq.lower() in jogando
            pelo_rumble = not este_joga and self._recebe_o_rumble(uniq)
            endpoint_aberto = endpoint is not None and sink_esta_tocando(endpoint.nome)
            # O-SOM-E-A-HAPTICA-NUM-RELATORIO-SO-01: a háptica vai ao fio com o som
            # de pé ou sem ele; o portão (quem joga, ou o rumble deste controle) e
            # o ganho dela decidem, e nunca o alto-falante.
            leva = bool(
                endpoint_aberto and (este_joga or pelo_rumble) and GANHO.pct(uniq) > 0
            )
            leva_de[uniq] = leva
            self._leva_da_ponte = MappingProxyType({**self._leva_da_ponte, uniq: leva})
            self._vigiar_o_portao(
                uniq,
                fechado=endpoint_aberto and not este_joga and not pelo_rumble,
                controles=controles,
            )
            som_toca = sink_esta_tocando(
                nome_do_sink(uniq), na_duvida=uniq in self._pontes
            )
            if not som_toca and not leva:
                self._descer_ponte_ociosa(uniq)
                continue
            tipo = "som" if som_toca else "haptica"
            lendo = endpoint.nome if (endpoint_aberto and endpoint is not None) else ""
            if uniq in self._pontes:
                # A ponte só sobe de novo quando o endpoint que ela LÊ muda: para
                # ganhar a háptica, trocar de endpoint ou soltá-lo quando o jogo o
                # fecha (o gravador preso nele seguraria o endpoint, que não
                # se reancora com leitor). Ligar e desligar o bloco é `leva`.
                lia = self._endpoint_da_ponte.get(uniq, "")
                if lia == lendo:
                    self._modo_da_ponte[uniq] = tipo
                    continue
                anterior = self._pontes.pop(uniq)
                anterior.descer()
                if lia and lendo:
                    logger.info("som_ponte_troca_de_endpoint", uniq=uniq)
                elif lendo:
                    logger.info("som_ponte_ganha_a_haptica", uniq=uniq)
                else:
                    logger.info("som_ponte_solta_a_haptica", uniq=uniq)
            if not caminho:
                continue
            vaga: Any = None
            if governador is not None:
                from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import (
                    Recusa,
                )

                try:
                    vaga = governador.pedir_vaga(uniq, tipo)
                except Exception:
                    logger.warning(
                        "governador_pedido_de_vaga_falhou", uniq=uniq, modo=tipo, exc_info=True
                    )
                    vaga = None
                if isinstance(vaga, Recusa):
                    esperando.add((uniq, tipo))
                    continue
            fonte, gravador, motivo = fonte_do_monitor_do_no(
                nome_do_sink(uniq), uniq=uniq, papel="som"
            )
            if fonte is None:
                if vaga is not None:
                    vaga.soltar("o som não teve fonte")
                if gravador is not None:
                    derrubar_leitor_de_pipe(gravador)
                self._ponte_recusada[uniq] = time.monotonic()
                logger.info("som_ponte_sem_fonte", uniq=uniq, motivo=motivo)
                continue
            fonte_h: Any = None
            gravador_h: Any = None
            if lendo:
                fonte_h, gravador_h, motivo_h = fonte_do_monitor_do_no(
                    lendo,
                    uniq=uniq,
                    papel="haptica",
                    canais=CANAIS_DA_HAPTICA,
                )
                if fonte_h is None:
                    if gravador_h is not None:
                        derrubar_leitor_de_pipe(gravador_h)
                    gravador_h = None
                    lendo = ""
                    logger.info("haptica_sem_fonte", uniq=uniq, motivo=motivo_h)
                    if not som_toca:
                        derrubar_leitor_de_pipe(gravador)
                        if vaga is not None:
                            vaga.soltar("a vibração não teve fonte")
                        self._descer_ponte_ociosa(uniq)
                        continue
            ponte = PonteDeSomPorRadio(
                uniq=uniq,
                abrir_hidraw=functools.partial(self._abrir_hidraw, caminho),
                fonte_de_pcm=fonte,
                com_microfone=functools.partial(o_microfone_esta_no_ar, uniq),
                gravador=gravador,
                fonte_de_haptica=fonte_h,
                gravador_da_haptica=gravador_h,
                leva_a_haptica=functools.partial(self._a_ponte_leva_a_haptica, uniq),
                vaga=vaga,
                tipo=tipo,
                no_do_som=nome_do_sink(uniq),
                no_da_haptica=lendo,
                ganho_da_haptica=functools.partial(GANHO.fator, uniq),
            )
            if ponte.subir():
                self._pontes[uniq] = ponte
                self._modo_da_ponte[uniq] = tipo
                self._endpoint_da_ponte = MappingProxyType({
                    **self._endpoint_da_ponte, uniq: lendo,
                })
                self._ponte_recusada.pop(uniq, None)
            else:
                ponte.descer()
                self._ponte_recusada[uniq] = time.monotonic()
                logger.info("som_ponte_nao_subiu", uniq=uniq, motivo=ponte.motivo)
        self._leva_da_ponte = MappingProxyType(leva_de)
        self._esperando_vaga = frozenset(esperando)
        self._conferir_o_teste_da_haptica()
        self._conferir_o_rumble()
        self._dizer_a_haptica_aos_controles(controles)

    def _dizer_a_haptica_aos_controles(self, controles: list[Any]) -> None:
        """Quem tem a háptica por áudio tocando AGORA, dito ao controlador.

        A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01 (03/10/2026): com a háptica
        tocando, o rumble do controle sai sem `HAPTICS_SELECT`, o bit que
        cala a háptica (`_PinnedPyDualSense.set_haptica_de_audio`). Tocando
        quer dizer o endpoint do aparelho com fluxo E o caminho dele ao
        controle de pé: a ponte do rádio levando a háptica, o laço com o portão aberto no
        cabo. Só a BORDA vai ao controlador, nos dois sentidos; o servidor de
        som que não respondeu deixa tudo como estava.
        """
        definir = getattr(self._backend, "set_haptica_de_audio_for", None)
        if not callable(definir):
            return
        from hefesto_dualsense4unix.integrations.alto_falante_bt import sinks_que_tocam

        caminhos: dict[str, tuple[str, str, str]] = {}
        for controle in controles:
            uniq = str(getattr(controle, "uniq", "") or "")
            chave = self._chave_do_rumble(uniq) if uniq else None
            marca = self._aparelho_de.get(chave) if chave is not None else None
            endpoint = self._endpoints.get(marca) if marca is not None else None
            nome = str(getattr(endpoint, "nome", "") or "")
            if chave is not None and marca is not None and nome:
                caminhos[uniq] = (chave, marca, nome)
        tocando: set[str] | None = set()
        if caminhos:
            try:
                tocando = sinks_que_tocam({n for _c, _m, n in caminhos.values()})
            except Exception:
                tocando = None
        if tocando is None:
            return
        ativos = {
            uniq
            for uniq, (chave, marca, nome) in caminhos.items()
            if nome in tocando and self._a_haptica_chega_ao_controle(uniq, chave, marca, nome)
        }
        antes = self._com_haptica_de_audio
        for uniq in sorted({*antes, *ativos}):
            if (uniq in ativos) == (uniq in antes):
                continue
            try:
                definir(uniq, uniq in ativos)
            except Exception as exc:
                logger.debug("haptica_de_audio_nao_chegou_ao_controle", err=str(exc))
        self._com_haptica_de_audio = frozenset(ativos)

    def _a_haptica_chega_ao_controle(
        self, uniq: str, chave: str, marca: str, nome: str
    ) -> bool:
        """O caminho do endpoint ``nome`` ao controle está de pé: o laço ou a ponte."""
        cabo = self._cabo
        if cabo is not None:
            rota = cabo.aparelhos().get(marca)
            if rota is not None and getattr(rota, "dono", "") == chave:
                return cabo.portao(marca) is True
        dono = uniq if uniq in self._pontes else chave
        ponte = self._pontes.get(dono)
        if ponte is None or not self._a_ponte_leva_a_haptica(dono):
            return False
        if self._endpoint_da_ponte.get(dono) != nome:
            return False
        de_pe = getattr(ponte, "esta_de_pe", None)
        try:
            return bool(de_pe()) if callable(de_pe) else False
        except Exception:
            return False

    def _esquecer_a_espera(self, uniq: str) -> None:
        """Ela respondeu «Ligar aqui»: quem esperava vaga deixa de esperar."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq) or uniq.lower()
        self._esperando_vaga = frozenset(
            (u, m) for u, m in self._esperando_vaga if (norm_mac(u) or u.lower()) != alvo
        )
        self._acordar_a_volta()

    def _acordar_a_volta(self, _por_quem: str = "") -> None:
        """Pede a volta AGORA, sem esperar o relógio. Nunca levanta."""
        self._volta_pedida = True
        acordar = getattr(self, "_acordar", None)
        if acordar is not None:
            acordar.set()

    def _o_no_tem_sinal(self, nome: str) -> bool | None:
        """O nó tem sinal agora? ``None`` = ninguém o escuta. Nunca levanta."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import OUVIDO

        try:
            return OUVIDO.tem_sinal(nome)
        except Exception:
            logger.debug("som_ouvido_ilegivel", no=nome, exc_info=True)
            return None

    def _a_ponte_leva_a_haptica(self, uniq: str) -> bool:
        """O bloco da háptica vai ao fio na ponte de ``uniq``? Lido a cada quadro."""
        return self._leva_da_ponte.get(uniq) is True

    def _descer_ponte_ociosa(self, uniq: str) -> None:
        """A ponte de quem não tem o que tocar desce. Idempotente."""
        ponte = self._pontes.pop(uniq, None)
        self._modo_da_ponte.pop(uniq, None)
        if ponte is not None:
            ponte.descer()
            logger.info("som_ponte_ociosa_descida", uniq=uniq)

    def _abrir_hidraw(self, caminho: str) -> int | None:
        """O fd de escrita daquele nó, pelo BROKER — nunca por `os.open` cru."""
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            abrir_hidraw,
        )

        try:
            return abrir_hidraw(caminho, escrita=True).fd
        except Exception:
            logger.debug("som_hidraw_nao_abriu", caminho=caminho, exc_info=True)
            return None

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            registrar_dizedor_da_fonte,
        )

        self._backend = getattr(ctx, "controller", None)
        if self._thread is not None and self._thread.is_alive():
            return
        self._instalar_o_numerador()
        self._store = getattr(ctx, "store", None)
        self._gerenciador = self._gerenciador_injetado or GerenciadorDeNosDeSom(
            ponte_do_radio_por_controle=self._ponte_do_radio_de,
            fonte_por_controle=self._fonte_do_controle,
        )
        self._dizedor_anterior = registrar_dizedor_da_fonte(self._fonte_do_controle)
        if self.governador is None:
            try:
                if self._governador_injetado is not None:
                    self.governador = self._governador_injetado
                else:
                    from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import (
                        GovernadorDoRadio,
                    )

                    self.governador = GovernadorDoRadio.de_producao()
                self.governador.ao_autorizar = self._esquecer_a_espera
                self.governador.iniciar()
            except Exception:
                logger.warning("governador_do_radio_nao_subiu", exc_info=True)
                self.governador = None
        self._parar.clear()
        self._acordar.clear()
        self._ouvir_quem_entra_na_partida(self._acordar_a_volta)
        self._ouvinte = threading.Thread(
            target=self._ouvir_o_retrato, name="hefesto-som-fluxos", daemon=True
        )
        self._ouvinte.start()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-som-sup", daemon=True
        )
        self._thread.start()
        logger.info("som_subsystem_iniciado")

    def _ouvir_quem_entra_na_partida(self, aviso: Any) -> None:
        """Liga (ou desliga, com ``None``) o aviso do controle que entra na partida."""
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import (
            ATRIBUTO,
            QuemMexe,
            quem_mexe_de,
        )

        daemon = getattr(self, "_daemon", None)
        if aviso is None:
            marcas = getattr(daemon, ATRIBUTO, None)
            if isinstance(marcas, QuemMexe):
                marcas.ao_marcar = None
            return
        marcas = quem_mexe_de(daemon)
        if marcas is not None:
            marcas.ao_marcar = aviso

    async def stop(self) -> None:
        """Derruba as pontes, e SÓ ENTÃO os nós. Idempotente."""
        self._parar.set()
        self._ouvir_quem_entra_na_partida(None)
        from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

        self._acordar.set()
        RETRATO.acordar()
        thread, ouvinte = self._thread, self._ouvinte
        self._thread = self._ouvinte = None
        for fio in (thread, ouvinte):
            if fio is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(fio.join, 2.0)
        pontes = list(self._pontes.items())
        if pontes:
            await asyncio.gather(
                *(asyncio.to_thread(ponte.descer) for _uniq, ponte in pontes),
                return_exceptions=True,
            )
        for uniq, _ponte in pontes:
            self._pontes.pop(uniq, None)
        tocadores = list(self._tocadores.values())
        self._tocadores = MappingProxyType({})
        self._rumble_vivo = MappingProxyType({})
        if tocadores:
            await asyncio.gather(
                *(asyncio.to_thread(t.parar) for t in tocadores), return_exceptions=True
            )
        cabo = self._cabo
        if cabo is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(cabo.parar)
        ouvidos = list(self._ouvidos_das_placas.values())
        self._ouvidos_das_placas = MappingProxyType({})
        if ouvidos:
            await asyncio.gather(
                *(asyncio.to_thread(o.descer) for o in ouvidos), return_exceptions=True
            )
        with contextlib.suppress(Exception):
            await asyncio.to_thread(GANHO.devolver_as_placas)
        governador, self.governador = self.governador, None
        if governador is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(governador.parar)
        gerenciador = self._gerenciador
        if gerenciador is not None:
            with contextlib.suppress(Exception):
                gerenciador.parar()
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            registrar_dizedor_da_fonte,
        )

        self._gerenciador = None
        self._desinstalar_o_numerador()
        registrar_dizedor_da_fonte(self._dizedor_anterior)
        self._dizedor_anterior = None
        # as pontes e os laços desceram: a háptica parou de tocar em todos
        self._dizer_a_haptica_aos_controles([])
        self._backend = None
        logger.info("som_subsystem_parado")


    def _instalar_o_numerador(self) -> None:
        """Instala o numerador de assento **só se ninguém o estiver atendendo**."""
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        anterior = registrar_numerador_de_assento(self.numero_do_assento)
        if anterior is not None:
            registrar_numerador_de_assento(anterior)
            self._numerador_anterior = Ellipsis
            return
        self._numerador_anterior = anterior

    def _desinstalar_o_numerador(self) -> None:
        """Devolve o numerador anterior — e só se tiver sido ELE a instalar."""
        if self._numerador_anterior is Ellipsis:
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        with contextlib.suppress(Exception):
            registrar_numerador_de_assento(self._numerador_anterior)
        self._numerador_anterior = Ellipsis


    def _loop(self) -> None:
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        while not self._parar.is_set():
            try:
                self._reconciliar(gerenciador)
            except Exception as exc:
                logger.debug("som_reconciliacao_falhou", err=str(exc))
            if self._esperar_a_mesa_do_som(gerenciador):
                return

    def _ouvir_o_retrato(self) -> None:
        """O ouvinte: o retrato do som mudou nas saídas ou nos fluxos, e o laço acorda."""
        from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

        marca = RETRATO.marca(_O_QUE_A_VOLTA_OUVE)
        while not self._parar.is_set():
            nova = RETRATO.esperar(marca, RECONCILIA_S, _O_QUE_A_VOLTA_OUVE)
            if nova != marca:
                marca = nova
                self._acordar.set()

    def _esperar_a_mesa_do_som(self, gerenciador: Any) -> bool:
        """Espera até a próxima volta, e volta CEDO se o que a volta leu mudou. True = parar."""
        fim = time.monotonic() + RECONCILIA_S
        acordar = self._acordar
        while True:
            falta = fim - time.monotonic()
            if falta <= 0:
                return False
            avisado = acordar.wait(falta)
            if self._parar.is_set() or gerenciador.dormir(0.0):
                return True
            if not avisado:
                return False
            acordar.clear()
            if self._volta_pedida:
                self._volta_pedida = False
                return False
            if self._a_mesa_do_som_mudou():
                return False

    def _o_que_a_mesa_do_som_diz(self) -> frozenset[str] | None:
        """Quais nós dos controles do rádio têm fluxo agora. ``None`` = não sei."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            nome_do_sink,
            sinks_que_tocam,
        )

        nomes = [str(getattr(ep, "nome", "") or "") for ep in self._endpoints.values()]
        nomes += [nome_do_sink(u) for u in self._no_radio]
        nomes = [n for n in nomes if n]
        if not nomes:
            return frozenset()
        try:
            tocando = sinks_que_tocam(nomes)
        except Exception as exc:
            logger.debug("som_mesa_ilegivel_no_retrato", err=str(exc))
            return None
        return None if tocando is None else frozenset(tocando)

    def _a_mesa_do_som_mudou(self) -> bool:
        """Algum nó dos controles do rádio abriu ou fechou fluxo desde que a volta começou?"""
        agora = self._o_que_a_mesa_do_som_diz()
        if agora is None:
            return False
        if agora == self._o_que_a_volta_viu:
            return False
        logger.debug(
            "som_volta_acordada_pelo_fluxo",
            antes=len(self._o_que_a_volta_viu or ()),
            agora=len(agora),
        )
        return True

    def _reconciliar(self, gerenciador: Any) -> None:
        """Uma varredura: quem está na lista ganha nó, quem saiu perde."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import e_radio

        alvos = self.alvos(list(self._fonte()))
        self._no_radio = frozenset(
            str(getattr(c, "uniq", "") or "")
            for c in alvos
            if e_radio(str(getattr(c, "transporte", "") or ""))
        )
        self._o_que_a_volta_viu = self._o_que_a_mesa_do_som_diz()
        self._casar_as_pontes(alvos)
        gerenciador.reconciliar(alvos)


__all__ = [
    "RECONCILIA_S",
    "AltoFalanteSubsystem",
    "ControleNaLista",
    "GerenciadorDeNosDeSom",
    "controles_na_lista",
]
