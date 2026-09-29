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

#: Quanto o fator lido pode diferir do pedido sem nova escrita: o servidor
#: guarda o volume como inteiro cru, e a volta pela raiz cúbica arredonda.
TOLERANCIA = 0.01

Rodar = Callable[[list[str]], "str | None"]


def _chave(uniq: str | None) -> str | None:
    """A chave do perfil para este controle (o dono é ``norm_mac``)."""
    if not uniq:
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    with contextlib.suppress(Exception):
        return norm_mac(uniq) or None
    return None


def volumes_crus(nome: str, saida: str) -> list[int] | None:
    """Os volumes crus (inteiros, 65536 = 100 %) por canal deste sink."""
    dentro = False
    for linha in saida.splitlines():
        crua = linha.strip()
        if crua.startswith("Name:"):
            dentro = crua.split(":", 1)[1].strip() == nome
            continue
        if dentro and crua.startswith("Volume:"):
            achados: list[int] = []
            for parte in crua.split(":", 1)[1].split(","):
                if ":" not in parte:
                    continue
                cru = parte.split(":", 1)[1].split("/", 1)[0].strip()
                with contextlib.suppress(ValueError):
                    achados.append(int(cru))
            return achados or None
    return None


def linear_do_cru(cru: int) -> float:
    """O fator de amplitude de um volume cru (a escala do servidor é cúbica)."""
    return float((max(cru, 0) / VOLUME_NORMAL) ** 3)


class GanhoDaHaptica:
    """O ganho por controle, lido do perfil que vale; um só no processo (:data:`GANHO`)."""

    def __init__(self) -> None:
        #: ``{chave: pct}`` de quem ESCREVEU o campo; o resto vale o padrão.
        self._escritos: dict[str, int] = {}
        #: As placas em que este dono escreveu, para o ``stop`` devolvê-las.
        self._placas: dict[str, float] = {}

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

    def ler_do_daemon(self, daemon: Any) -> None:
        """Relê o perfil que vale agora, pelo mesmo resolvedor dos gravadores.

        Nunca levanta: perfil ilegível é «ninguém opinou», e a háptica segue no
        padrão em vez de sumir por um JSON torto.
        """
        controllers: Any = None
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.profiles.loader import perfil_em_disco
            from hefesto_dualsense4unix.profiles.manager import nome_do_perfil_que_grava

            store = getattr(daemon, "store", None)
            nome = nome_do_perfil_que_grava(getattr(store, "active_profile", None))
            perfil = perfil_em_disco(nome) if nome else None
            controllers = getattr(perfil, "controllers", None)
        self.ler_do_perfil(controllers)

    def pct(self, uniq: str | None) -> int:
        """O ganho que vale para este controle, em % (0 a ``HAPTICA_PCT_MAX``)."""
        from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

        chave = _chave(uniq)
        if chave is None:
            return HAPTICA_PCT_PADRAO
        return self._escritos.get(chave, HAPTICA_PCT_PADRAO)

    def fator(self, uniq: str | None) -> float:
        """O mesmo ganho em fator linear de amplitude (150 % → 1,5)."""
        return self.pct(uniq) / 100.0

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
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            rodar_pactl,
            sink_do_controle,
        )
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import MARCA_DO_NOME

        correr: Any = runner or rodar_pactl
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
        if not com_dono:
            return set()
        longa = correr(["pactl", "list", "sinks"])
        if longa is None:
            return set(com_dono)  # servidor mudo: a placa segue com dono, sem escrita
        for placa, uniq in com_dono.items():
            fator = self.fator(uniq)
            self._placas[placa] = fator
            self._escrever_traseiros(placa, fator, longa, correr)
        return set(com_dono)

    def devolver_as_placas(self, *, runner: Rodar | None = None) -> None:
        """No ``stop``: os traseiros de toda placa escrita voltam a 1,0.

        O ganho não sobrevive ao Hefesto: sem isto, o WirePlumber guardaria o
        1,5 da placa, e o piso de 100 % de amanhã não o baixaria.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

        correr: Any = runner or rodar_pactl
        placas, self._placas = dict(self._placas), {}
        if not placas:
            return
        longa = correr(["pactl", "list", "sinks"])
        if longa is None:
            return
        for placa in placas:
            with contextlib.suppress(Exception):
                self._escrever_traseiros(placa, 1.0, longa, correr)

    @staticmethod
    def _escrever_traseiros(placa: str, fator: float, longa: str, correr: Any) -> bool:
        """Escreve os traseiros em fator linear, a frente como estava. True = escreveu."""
        crus = volumes_crus(placa, longa)
        if not crus or len(crus) < 4:
            return False
        traseiros = [linear_do_cru(c) for c in crus[2:4]]
        if all(abs(t - fator) <= TOLERANCIA * max(fator, 1.0) for t in traseiros):
            return False
        # OS QUATRO NA MESMA FORMA: o `pactl` recusa canais em formas
        # diferentes. A frente volta como o fator do inteiro cru que o servidor
        # tinha (o `%` que ele mostra é arredondado), e o alto-falante é dela.
        frente = [f"{linear_do_cru(c):.6f}" for c in crus[:2]]
        correr([
            "pactl", "set-sink-volume", placa, *frente, f"{fator:.4f}", f"{fator:.4f}",
        ])
        logger.info(
            "haptica_ganho_na_placa",
            sink=placa, eram=[round(t, 4) for t in traseiros], agora=round(fator, 4),
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
