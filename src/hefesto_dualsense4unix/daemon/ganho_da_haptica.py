"""O dono do ganho da háptica por áudio — um por controle, em fator linear.

O-GANHO-DA-HAPTICA-TEM-DONO-01, 29/09/2026. Ela, depois da Forja com os quatro:
*«no cabo ficou muito baixo a vibração específica»*. Medido camada por camada,
do jogo à placa tudo já está em 0 dB e a placa não tem folga acima disso no
hardware: o que falta é ganho acima de 100 %, em software, antes da placa.

UMA pergunta, UM dono: *«qual o ganho da háptica deste controle agora?»*. As
duas portas perguntam aqui:

- **o cabo** — os traseiros da PLACA daquele controle (:meth:`escrever_nas_placas`),
  a única camada que alcança todo escritor (o jogo direto na placa e o laço do
  lugar). Os traseiros do endpoint ficam em 100 %: ganho ali somaria ao da placa;
- **o rádio** — o ``ganho`` do ``ConversorDeHaptica`` da ponte daquele
  controle, antes do int8 (:meth:`fator`, perguntado a cada bloco).

**A ECONOMIA CORTA TAMBÉM A HÁPTICA** (a resposta [25] dela, 29/09 ~21h50,
«Corta também»): com o orçamento da mesa em ``economia``, o fator que as duas
portas recebem é ``min(ganho, teto)``, pela regra do teto do rumble
(``core.rumble._sob_o_teto``), chamada e não copiada. O ``pct`` segue sendo o
que ela escolheu; o teto é leitura (:meth:`GanhoDaHaptica.pct_que_vale`).

**O ``%`` DO SERVIDOR DE SOM É CÚBICO.** 40 % no ``pactl`` é -23,88 dB, e o
WirePlumber o guarda como 0,063997 linear (0,4³). Um ganho de 150 % escrito
como ``150%`` viraria 3,375 vezes (+10,6 dB). A escrita vai em fator linear
(``1.5000``), que o ``pactl`` lê como amplitude, e a frente volta no fator
do inteiro cru que o servidor tinha.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O volume cru que o servidor chama de 100 % (``PA_VOLUME_NORM``).
VOLUME_NORMAL = 65536

#: Quanto o volume lido pode diferir do pedido sem nova escrita, em pontos do
#: `%` do servidor: o leitor da casa (`volumes_do_sink`) devolve o `%`
#: arredondado ao inteiro, e um ponto é o arredondamento.
TOLERANCIA_PCT = 1.0

Rodar = Callable[[list[str]], "str | None"]


def _chave(uniq: str | None) -> str | None:
    """A chave do perfil para este controle (o dono é ``norm_mac``)."""
    if not uniq:
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    with contextlib.suppress(Exception):
        return norm_mac(uniq) or None
    return None


def linear_do_cru(cru: int) -> float:
    """O fator de amplitude de um volume cru (a escala do servidor é cúbica)."""
    return float((max(cru, 0) / VOLUME_NORMAL) ** 3)


def linear_do_pct(pct: float) -> float:
    """O fator de amplitude do `%` do servidor (40 % → 0,064)."""
    return float((max(pct, 0.0) / 100.0) ** 3)


def pct_do_linear(fator: float) -> float:
    """O `%` do servidor de um fator de amplitude (1,5 → 114,5 %)."""
    return 100.0 * float(max(fator, 0.0) ** (1.0 / 3.0))


class GanhoDaHaptica:
    """O ganho por controle, lido do perfil que vale; um só no processo (:data:`GANHO`)."""

    def __init__(self) -> None:
        #: ``{chave: pct}`` de quem ESCREVEU o campo; o resto vale o padrão.
        self._escritos: dict[str, int] = {}
        #: As placas em que este dono escreveu, para o ``stop`` devolvê-las.
        self._placas: dict[str, float] = {}
        #: O perfil que só o carregador inteiro achou (fora do nome do arquivo):
        #: ele não se relê a cada volta, só quando o gravador pede.
        self._pelo_carregador: str | None = None
        #: O teto do orçamento da mesa, em fator (``None`` = sem teto). Relido
        #: com o perfil, a cada volta do som e no ato do pedido.
        self._teto: float | None = None
        #: As chaves dos controles que ligaram a SUA economia (o botão da linha
        #: do controle, ``maquina.json``), relidas junto com o teto da mesa.
        self._em_economia: frozenset[str] = frozenset()

    # -- a leitura ---------------------------------------------------------
    def ler_do_perfil(self, controllers: Any) -> None:
        """Troca o mapa pelo ``controllers`` de um perfil (``None`` = ninguém opinou)."""
        from hefesto_dualsense4unix.profiles.schema import pcts_da_haptica_dos_controles

        mapa: dict[str, int] = {}
        with contextlib.suppress(Exception):
            for uniq, pct in pcts_da_haptica_dos_controles(controllers).items():
                chave = _chave(uniq)
                if chave is not None:
                    mapa[chave] = pct
        self._escritos = mapa

    def ler_do_daemon(self, daemon: Any, *, forcar: bool = False) -> None:
        """Relê o perfil que vale agora, pelo mesmo resolvedor dos gravadores.

        O arquivo pelo nome (`perfil_em_disco`) é a leitura de cada volta; o
        perfil que só o carregador inteiro acha (`load_profile`, as quatro
        pernas) é lido uma vez e de novo quando quem grava pede (`forcar`).
        Nunca levanta: perfil ilegível é «ninguém opinou», e a háptica segue no
        padrão em vez de sumir por um JSON torto.
        """
        self.ler_o_teto(daemon)
        controllers: Any = None
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.profiles.loader import load_profile, perfil_em_disco
            from hefesto_dualsense4unix.profiles.manager import nome_do_perfil_que_grava

            store = getattr(daemon, "store", None)
            nome = nome_do_perfil_que_grava(getattr(store, "active_profile", None))
            perfil = perfil_em_disco(nome) if nome else None
            if perfil is None and nome:
                if not forcar and self._pelo_carregador == nome:
                    return
                self._pelo_carregador = nome
                perfil = load_profile(nome)
            else:
                self._pelo_carregador = None
            # O padrão do computador por baixo do perfil, e sozinho quando não
            # há perfil (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01).
            from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
                o_computador,
                o_que_vale,
            )

            controllers = (
                getattr(o_que_vale(perfil), "controllers", None)
                if perfil is not None else o_computador().controles or None
            )
        self.ler_do_perfil(controllers)

    def ler_o_teto(self, daemon: Any) -> None:
        """O teto da Economia de agora: o da mesa e o de cada controle que ligou a sua.

        O da mesa vem pela fonte que o funil do rumble lê; o de cada controle,
        pela declaração que a vibração dele já obedece
        (``profiles.schema.controles_em_economia``, a peça «Vibração» de
        ``A_ECONOMIA_EM_CADA_PECA``). Nunca levanta: sem config, sem a fonte ou
        com ela levantando, não há teto — nunca um teto inventado
        (``core.rumble._orcamento_declarado``).
        """
        teto: float | None = None
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.core.rumble import (
                _orcamento_declarado,
                teto_do_orcamento,
            )

            teto = teto_do_orcamento(_orcamento_declarado(getattr(daemon, "config", None)))
        self._teto = teto
        ligados: frozenset[str] = frozenset()
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.profiles.schema import controles_em_economia

            ligados = frozenset(c for c in (_chave(u) for u in controles_em_economia()) if c)
        self._em_economia = ligados

    def _teto_de(self, uniq: str | None) -> float | None:
        """O teto deste controle: o da mesa, ou o da economia que ELE ligou.

        A ECONOMIA DE UM CONTROLE CORTA A HÁPTICA DELE — 02/10/2026, pela
        resposta [25] dela («Corta também») e pela palavra dela de 29/09, *«todas
        as features são um por aparelho. sempre.»*.
        A regra entre os dois é a de ``profiles.schema.economia_vale`` (a mesa OU
        o controle), e o número é o mesmo degrau da mesa: um só teto da Economia.
        """
        if self._teto is not None:
            return self._teto
        chave = _chave(uniq)
        if chave is None or chave not in self._em_economia:
            return None
        from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO, teto_do_orcamento

        return teto_do_orcamento(_ORCAMENTO_COM_TETO)

    def pct(self, uniq: str | None) -> int:
        """O ganho que ela escolheu para este controle, em % (0 a ``HAPTICA_PCT_MAX``)."""
        from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

        chave = _chave(uniq)
        if chave is None:
            return HAPTICA_PCT_PADRAO
        return self._escritos.get(chave, HAPTICA_PCT_PADRAO)

    def fator(self, uniq: str | None) -> float:
        """O ganho que VALE em fator linear de amplitude (150 % → 1,5; na Economia, 0,3)."""
        from hefesto_dualsense4unix.core.rumble import _sob_o_teto

        return _sob_o_teto(self.pct(uniq) / 100.0, self._teto_de(uniq))

    def pct_que_vale(self, uniq: str | None) -> int:
        """O ganho que vale agora, em %: o escolhido sob o teto do orçamento."""
        return round(self.fator(uniq) * 100.0)

    # -- a porta do cabo ---------------------------------------------------
    def escrever_nas_placas(
        self,
        no_cabo: Iterable[str],
        na_mesa: Sequence[str],
        placas_com_motores: Iterable[str],
        *,
        runner: Rodar | None = None,
        placa_de: Callable[[str, Sequence[str]], str] | None = None,
    ) -> set[str]:
        """Os traseiros da placa de cada controle no cabo recebem o ganho dele.

        Devolve as placas que TÊM dono, para a varredura do piso pulá-las: dois
        escritores do mesmo volume brigariam a cada volta. A placa é a que o
        dono já responde (``sink_do_controle``), e só vale se for uma das
        placas de quatro canais da volta e não for um endpoint do Hefesto.

        Reescreve sempre que o volume lido difere do ganho, e não só quando o
        perfil muda: o WirePlumber guarda o volume pelo NOME da placa, e o
        ganho de um controle voltaria na placa de quem plugar primeiro amanhã.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import sink_do_controle
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import MARCA_DO_NOME

        achar: Any = placa_de or (lambda u, mesa: sink_do_controle(u, mesa, runner=runner))
        placas = set(placas_com_motores)
        com_dono: dict[str, str] = {}
        for uniq in no_cabo:
            if not uniq:
                continue
            placa = ""
            with contextlib.suppress(Exception):
                placa = str(achar(uniq, list(na_mesa)) or "")
            if not placa or placa not in placas or MARCA_DO_NOME in placa:
                continue
            com_dono[placa] = uniq
        for placa, uniq in com_dono.items():
            fator = self.fator(uniq)
            self._placas[placa] = fator
            self._escrever_traseiros(placa, fator, runner)
        return set(com_dono)

    def devolver_as_placas(self, *, runner: Rodar | None = None) -> None:
        """No ``stop``: os traseiros de toda placa escrita voltam a 1,0.

        O ganho não sobrevive ao Hefesto: sem isto, o WirePlumber guardaria o
        1,5 da placa, e o piso de 100 % de amanhã não o baixaria.
        """
        placas, self._placas = dict(self._placas), {}
        for placa in placas:
            with contextlib.suppress(Exception):
                self._escrever_traseiros(placa, 1.0, runner)

    @staticmethod
    def _escrever_traseiros(placa: str, fator: float, runner: Rodar | None) -> bool:
        """Escreve os traseiros em fator linear, a frente como estava. True = escreveu.

        A LEITURA É A DA CASA (`volumes_do_sink`, que passa pelo retrato do
        servidor de som): uma segunda pergunta `list sinks` aqui seria outro
        leitor do mesmo servidor.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            rodar_pactl,
            volumes_do_sink,
        )

        volumes = volumes_do_sink(placa, runner)
        if not volumes or len(volumes) < 4:
            return False  # placa estéreo ou servidor mudo: sem escrita
        alvo = pct_do_linear(fator)
        if all(abs(v - alvo) <= TOLERANCIA_PCT for v in volumes[2:4]):
            return False
        # OS QUATRO NA MESMA FORMA: o `pactl` recusa canais em formas
        # diferentes. A frente volta no fator do `%` que o servidor tinha, e o
        # alto-falante é dela.
        frente = [f"{linear_do_pct(v):.6f}" for v in volumes[:2]]
        correr: Any = runner or rodar_pactl
        correr([
            "pactl", "set-sink-volume", placa, *frente, f"{fator:.4f}", f"{fator:.4f}",
        ])
        logger.info(
            "haptica_ganho_na_placa",
            sink=placa, eram_pct=volumes[2:4], agora=round(fator, 4),
        )
        return True


#: O dono, um só no processo: o subsystem do som o relê a cada volta, o
#: ``rumble.motores.set`` o relê no mesmo ato em que grava, e a ponte do rádio
#: o pergunta a cada bloco.
GANHO = GanhoDaHaptica()


def placas_do_piso(lidos: Iterable[str], com_dono: Iterable[str]) -> list[str]:
    """As placas que a varredura do piso de 100 % ainda levanta: as SEM dono."""
    dono = set(com_dono)
    return [s for s in lidos if s not in dono]
