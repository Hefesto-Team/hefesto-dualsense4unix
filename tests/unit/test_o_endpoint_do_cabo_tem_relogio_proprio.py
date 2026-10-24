"""O-ENDPOINT-DO-CABO-TEM-RELOGIO-PROPRIO-COMO-O-DO-RADIO-01 — o endpoint dá o passo do grafo dele.

A medida (24/10/2026, r02 do Sackboy, um DualSense no cabo): os fluxos de háptica do
jogo no nosso endpoint andavam com ``node.driver-id`` da placa USB do controle, o
mesmo do laço ``hefesto-haptica-do-cabo-<marca>``. No rádio o endpoint é o único
driver do grafo dele.

A forma da cura saiu de uma bancada de PipeWire própria (servidor, WirePlumber e
``pipewire-pulse`` no runtime de mentira, a placa como ``null-audio-sink`` com o
``priority.driver`` 1009 de uma placa ALSA): o ``pw-loopback`` 1.6.9 põe os dois
lados no MESMO ``node.group`` mesmo com ``--capture-props``/``--playback-props``
diferentes e com ``-g ""``, então o laço não separa os relógios. O driver de um grupo
é o nó de maior ``priority.driver``: o endpoint sem o campo perdia para a placa, e
com 3000 o jogo, os dois lados do laço e a placa passam a andar no passo dele, com o
som chegando à placa.

A régua vale para os quatro jogadores em qualquer transporte, porque o endpoint é o
mesmo no cabo e no rádio. Os ``uniq`` são da faixa sintética ``aa:bb:cc``.

AS MORDIDAS:

1. tire o ``priority.driver`` de ``propriedades_do_endpoint`` → reprovam os casos da mesa;
2. tire ``nasceu_com_o_relogio`` da adoção em ``iniciar`` → o nó herdado sem o campo
   fica de pé, e o som do jogo continua no passo da placa até o servidor reiniciar.
"""

from __future__ import annotations

import shlex
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import pad_usb

#: A faixa que o WirePlumber 0.5 dá às placas ALSA (``monitors/alsa.lua``): 1000 no
#: device 0, mais 1000 na captura, mais 500 no perfil «pro». O endpoint fica acima.
_TETO_DAS_PLACAS_ALSA = 1000 + 1000 + 500

_P1, _P2, _P3, _P4 = (f"aa:bb:cc:00:00:{n}{n}" for n in (1, 2, 3, 4))

MESAS = {
    "p1-usb,p2-bt,p3-usb,p4-bt": [(_P1, "usb"), (_P2, "bt"), (_P3, "usb"), (_P4, "bt")],
    "tres-no-radio-um-no-cabo": [(_P1, "usb"), (_P2, "bt"), (_P3, "bt"), (_P4, "bt")],
    "todos-no-cabo": [(_P1, "usb"), (_P2, "usb"), (_P3, "usb"), (_P4, "usb")],
    "todos-no-radio": [(_P1, "bt"), (_P2, "bt"), (_P3, "bt"), (_P4, "bt")],
    "um-so": [(_P1, "usb")],
}


def _ancora(i: int) -> eh.Ancora:
    return eh.Ancora(
        syspath=f"/devices/pci0000:00/usb3/3-{i}",
        declarado=f"/devices/pci0000:00/usb3/3-{i}/3-{i}:1.0",
    )


_ANCORAS = {u: _ancora(i) for i, u in enumerate((_P1, _P2, _P3, _P4), start=1)}


@pytest.fixture(autouse=True)
def _cada_um_na_porta_dele(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo pad tem a porta dele, no cabo e no rádio (D-1410-TODO-PAD-TEM-PORTA-PROPRIA)."""
    portas = {u: a.declarado for u, a in _ANCORAS.items()}
    monkeypatch.setattr(pad_usb, "interface_do_aparelho", lambda uniq: portas.get(uniq))


class _Servidor:
    """Um ``pipewire-pulse`` de mentira: guarda o argv de cada ``load-module``."""

    def __init__(self) -> None:
        self.modulos: dict[str, str] = {}
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        self.mudo = False
        self._proximo = 536870912

    def __call__(self, argv: list[str]) -> str | None:
        if self.mudo:
            return None
        if argv[:2] == ["pactl", "load-module"]:
            self._proximo += 1
            mid = str(self._proximo)
            self.modulos[mid] = " ".join(argv[2:])
            self.cargas.append(mid)
            return mid + "\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.modulos.pop(argv[2], None)
            self.quedas.append(argv[2])
            return ""
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            linhas = ["1\tmodule-native-protocol-unix\t\t"]
            for mid, args in self.modulos.items():
                modulo, _, resto = args.partition(" ")
                linhas.append(f"{mid}\t{modulo}\t{resto}\t")
            return "\n".join(linhas) + "\n"
        return ""

    def propriedades(self, mid: str) -> dict[str, str]:
        """O ``sink_properties=`` do módulo ``mid``, como o servidor o lê."""
        args = self.modulos[mid]
        miolo = args.split('sink_properties="', 1)[1].rsplit('"', 1)[0]
        campos: dict[str, str] = {}
        for pedaco in shlex.split(miolo):
            nome, igual, resto = pedaco.partition("=")
            if igual:
                campos[nome] = resto
        return campos


def _no(uniq: str, servidor: _Servidor) -> Any:
    return eh.EndpointDeHaptica(uniq=uniq, ancora=_ANCORAS[uniq], runner=servidor)


@pytest.mark.parametrize("mesa", list(MESAS), ids=list(MESAS))
def test_todo_endpoint_nasce_dando_o_passo_do_grafo(mesa: str) -> None:
    # D-2410-O-ENDPOINT-DO-CABO-TEM-RELOGIO-PROPRIO
    """No cabo e no rádio, P1 a P4: o endpoint ganha da placa na eleição do driver."""
    servidor = _Servidor()
    for uniq, _transporte in MESAS[mesa]:
        no = _no(uniq, servidor)
        assert no.iniciar() is True
        props = servidor.propriedades(servidor.cargas[-1])
        assert int(props.get("priority.driver", "0")) > _TETO_DAS_PLACAS_ALSA, (
            f"{uniq}: sem priority.driver acima das placas, o laço põe o endpoint no passo da placa"
        )
        assert props["priority.session"] == "0", "o endpoint não pode virar a saída padrão"
    assert len(servidor.cargas) == len(MESAS[mesa])


def test_o_no_herdado_sem_o_relogio_nasce_de_novo() -> None:
    """O nó que o daemon de antes deixou sem o campo cai, e o novo nasce com ele."""
    servidor = _Servidor()
    no = _no(_P1, servidor)
    velho = eh.propriedades_do_endpoint(_P1, _ANCORAS[_P1]).replace(
        f" priority.driver={eh.PRIORIDADE_DO_RELOGIO}", ""
    )
    assert "priority.driver" not in velho
    herdado = servidor(["pactl", "load-module", "module-null-sink", f"sink_name={no.nome}", velho])
    assert herdado is not None
    servidor.cargas.clear()

    assert no.iniciar() is True
    assert servidor.quedas == [herdado.strip()]
    (novo,) = servidor.cargas
    assert int(servidor.propriedades(novo)["priority.driver"]) > _TETO_DAS_PLACAS_ALSA


def test_o_no_herdado_com_o_relogio_se_adota() -> None:
    """O nó que já nasceu com o campo fica: adotar não derruba nem carrega."""
    servidor = _Servidor()
    _no(_P2, servidor).iniciar()
    servidor.cargas.clear()

    outro_daemon = _no(_P2, servidor)
    assert outro_daemon.iniciar() is True
    assert servidor.cargas == []
    assert servidor.quedas == []


def test_sem_resposta_do_servidor_nao_se_derruba() -> None:
    """Não saber o argv do módulo não é motivo para derrubar o nó de pé."""
    assert eh.nasceu_com_o_relogio("536870913", lambda _a: None) is True
