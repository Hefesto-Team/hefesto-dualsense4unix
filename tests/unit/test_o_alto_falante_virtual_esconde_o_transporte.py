"""O-ALTO-FALANTE-VIRTUAL-01 — o alto-falante virtual esconde o transporte.

**O pedido, 29/08/2026:** alto-falante virtual *"no estilo do gamepad
virtual"*, para o som do controle funcionar **independente da máscara e do
transporte**. O contrato é o mesmo do vpad: o jogo escolhe um gamepad, não um
transporte — aqui, quem escolhe a saída escolhe um CONTROLE, não um sink.

**O nome é do usuário** (`D-0909-OS-NOS-SE-CHAMAM-ALTO-FALANTE-E-MICROFONE-DO-CONTROLE-N`,
): «Alto-falante do Controle N», par de «Microfone do
Controle N», com o sufixo da Sony desde 23/09/2026. O `sink_name` segue o
APARELHO (`hefesto_som_<hex6>`), e por isso sobrevive à troca de assento tanto
quanto à troca de cabo.

UM DONO SÓ, DESDE 28/09/2026 (O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01)
-------------------------------------------------------------------
Até aqui este arquivo aferia o PLANO DA JANELA (`app/audio_saida.
plano_de_publicacao` e os irmãos): comandos que ninguém executava, escritos ao
lado do dono que de fato publica o nó. O plano saiu, e as mesmas invariantes
passaram a ser cobradas de quem faz: o `GerenciadorDeNosDeSom`
(`daemon/subsystems/alto_falante.py`), que sobe um
`integrations/alto_falante_bt.SinkVirtualPipeWire` por controle, com a rota de
`alto_falante_bt.rota_do_no`.

E ele é medido num SERVIDOR DE SOM DE MENTIRA (:class:`ServidorDeSomDeMentira`)
que guarda o que foi carregado e responde por isso — não num dublê que só
aceita. Nenhum módulo entra no PipeWire de ninguém.

**Esta régua não é a bancada desta casa.** Os endereços são das faixas
sintéticas (`02fe00`, `aabbcc`), e nada aqui depende dos DualSense daqui.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    ControleNaLista,
    GerenciadorDeNosDeSom,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic

_SONY = " (DualSense Wireless Controller)"


_UNIQ_P1 = "02fe0011a1b2"
_UNIQ_P2 = "02fe0011a1b3"
_UNIQ_P3 = "02fe0011a1b4"
_UNIQ_P4 = "02fe0011a1b5"
_UNIQ_NUNCA_VISTO = "aabbcc7f0e01"

_SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
_SINK_P2 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.analog-surround-40"
)
_HDMI = "alsa_output.pci-0000_0c_00.4.hdmi-stereo"

_USB_P1 = "/sys/devices/pci0000:00/usb3/3-1"
_USB_P2 = "/sys/devices/pci0000:00/usb3/3-2"

_ASSENTO = {_UNIQ_P1: 1, _UNIQ_P2: 2, _UNIQ_P3: 3, _UNIQ_P4: 4, _UNIQ_NUNCA_VISTO: 4}


class ServidorDeSomDeMentira:
    """O servidor de som de mentira: GUARDA o que foi carregado e responde por isso.

    Não é um dublê que só aceita: um `load-module` vira um módulo com id, a
    lista de sinks passa a mostrar o nó que ele criou, e um `unload-module`
    o tira. É o que deixa a régua perguntar AO SERVIDOR quantos nós existem,
    e não à lembrança de quem os pediu.

    ``placas`` são as placas USB de DualSense que o servidor tem, na ordem
    em que o PipeWire as desempata (`-00`, `-00.2`).
    """

    def __init__(self, placas: tuple[str, ...] = (_SINK_P1, _SINK_P2)) -> None:
        self.placas = placas
        self.modulos: dict[str, tuple[str, ...]] = {}
        self._proximo = 500

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "load-module"]:
            self._proximo += 1
            self.modulos[str(self._proximo)] = tuple(argv[2:])
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.modulos.pop(argv[2], None)
            return ""
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            linhas = [f"62\t{_HDMI}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED"]
            linhas += [
                f"{70 + i}\t{p}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED"
                for i, p in enumerate(self.placas)
            ]
            linhas += [
                f"{i}\t{nome}\tPipeWire\ts16le 2ch 48000Hz\tIDLE"
                for i, nome in self.nos().items()
            ]
            return "\n".join(linhas) + "\n"
        if argv[:3] == ["pactl", "list", "sinks"]:
            usb = {_SINK_P1: "3-1", _SINK_P2: "3-2"}
            return "".join(
                f"Sink #{70 + i}\n\tName: {p}\n\tProperties:\n"
                f'\t\tsysfs.path = "/devices/pci0000:00/usb3/{usb.get(p, "9-9")}/'
                f'{usb.get(p, "9-9")}:1.0/sound/card{3 + i}"\n'
                for i, p in enumerate(self.placas)
            )
        if "get-default-sink" in argv:
            return f"{_HDMI}\n"
        if argv[:2] == ["pactl", "info"]:
            return "Server Name: PulseAudio (on PipeWire 1.0.0)\n"
        return ""

    def nos(self) -> dict[str, str]:
        """`{id do módulo: sink_name}` de cada `module-null-sink` de pé."""
        saida: dict[str, str] = {}
        for ident, args in self.modulos.items():
            if args and args[0] == "module-null-sink":
                nome = next(a for a in args if a.startswith("sink_name="))
                saida[ident] = nome.split("=", 1)[1]
        return saida

    def rotulo(self, sink_name: str) -> str:
        """O `device.description` com que o nó foi carregado."""
        for args in self.modulos.values():
            if args and args[0] == "module-null-sink" and f"sink_name={sink_name}" in args:
                props = next(a for a in args if a.startswith("sink_properties="))
                return props.split("device.description='", 1)[1].split("'", 1)[0]
        return ""

    def lacos(self) -> list[tuple[str, str]]:
        """`(source, sink)` de cada `module-loopback` de pé."""
        saida: list[tuple[str, str]] = []
        for args in self.modulos.values():
            if args and args[0] == "module-loopback":
                campos = dict(a.split("=", 1) for a in args[1:] if "=" in a)
                saida.append((campos.get("source", ""), campos.get("sink", "")))
        return saida


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch) -> ServidorDeSomDeMentira:
    """O servidor de mentira no lugar do `_rodar` do dono, e o numerador de assento."""
    falso = ServidorDeSomDeMentira()
    monkeypatch.setattr(af, "_rodar", falso)
    anterior = mic.registrar_numerador_de_assento(lambda u: _ASSENTO.get(u))
    yield falso
    mic.registrar_numerador_de_assento(anterior)


@pytest.fixture
def usb_da_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O censo de USB que o `sink_do_controle` consulta, dublado."""
    from hefesto_dualsense4unix.integrations import usb_pai

    monkeypatch.setattr(
        usb_pai,
        "usb_pai_por_uniq",
        lambda uniqs, **_: {
            u: {_UNIQ_P1: _USB_P1, _UNIQ_P2: _USB_P2}.get(u, "") for u in uniqs
        },
    )
    monkeypatch.setattr(
        usb_pai,
        "usb_pai_por_no",
        lambda mapa, **_: {_SINK_P1: _USB_P1, _SINK_P2: _USB_P2},
    )


def _cabo(uniq: str) -> ControleNaLista:
    return ControleNaLista(uniq=uniq, caminho="/dev/hidraw-de-mentira", transporte="cabo")


def _radio(uniq: str) -> ControleNaLista:
    return ControleNaLista(uniq=uniq, caminho="/dev/hidraw-de-mentira", transporte="rádio")


def _ponte_de_pe(_uniq: str) -> Any:
    return lambda: True


def test_o_mesmo_controle_no_cabo_e_no_radio_e_o_mesmo_no(
    servidor: ServidorDeSomDeMentira, usb_da_bancada: None
) -> None:
    """Trocar o cabo pelo rádio não pode trocar o nome nem o rótulo da saída."""
    ger = GerenciadorDeNosDeSom(ponte_do_radio_por_controle=_ponte_de_pe)
    ger.reconciliar([_cabo(_UNIQ_P1)])
    no_cabo = list(servidor.nos().values())
    rotulo_cabo = servidor.rotulo(af.nome_do_sink(_UNIQ_P1))
    ger.reconciliar([])
    assert servidor.nos() == {}
    ger.reconciliar([_radio(_UNIQ_P1)])
    no_radio = list(servidor.nos().values())

    assert no_cabo == no_radio == [af.nome_do_sink(_UNIQ_P1)]
    assert rotulo_cabo == servidor.rotulo(af.nome_do_sink(_UNIQ_P1))
    assert rotulo_cabo == "Alto-falante do Controle 1" + _SONY


def test_o_rotulo_e_o_do_assento_e_o_nome_e_o_do_aparelho() -> None:
    """Quatro assentos, quatro rótulos; o `sink_name` não muda com o assento."""
    assert [af.rotulo_do_alto_falante(n) for n in (1, 2, 3, 4)] == [
        "Alto-falante do Controle 1" + _SONY,
        "Alto-falante do Controle 2" + _SONY,
        "Alto-falante do Controle 3" + _SONY,
        "Alto-falante do Controle 4" + _SONY,
    ]
    anterior = mic.registrar_numerador_de_assento(lambda _u: 3)
    try:
        no_no_3 = af.SinkVirtualPipeWire(uniq=_UNIQ_P1)
    finally:
        mic.registrar_numerador_de_assento(anterior)
    assert no_no_3.nome == af.nome_do_sink(_UNIQ_P1)
    assert "11a1b2" not in no_no_3.nome, "o nome do nó voltou a levar o endereço"
    assert no_no_3.descricao == "Alto-falante do Controle 3" + _SONY


def test_sem_assento_sabido_nao_se_inventa_numero() -> None:
    """Dois «Alto-falante do Controle 1» mentem sobre qual é qual."""
    assert af.rotulo_do_alto_falante(None) == "Alto-falante do Controle" + _SONY
    assert af.rotulo_do_alto_falante(0) == "Alto-falante do Controle" + _SONY


def test_dois_controles_no_cabo_e_cada_no_entrega_no_sink_do_seu(
    servidor: ServidorDeSomDeMentira, usb_da_bancada: None
) -> None:
    """Dois DualSense no cabo: cada nó entrega no sink DAQUELE controle.

    Os dois nomes de sink diferem só por um `-00`/`-00.2`, que é desempate
    posicional do PipeWire e não identidade. Quem separa os dois é o dispositivo
    USB em que a placa e o HID penduram juntos.

    MORDIDA: troque a chamada a `sink_do_controle` dentro de `rota_do_no` por um
    casamento de texto —

        alvos = [s for s in sinks if s.startswith("alsa_output.usb-")]

    — e os DOIS laços passam a terminar em `_SINK_P1`: o som do P2 sai no
    alto-falante do P1.
    """
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar([_cabo(_UNIQ_P1), _cabo(_UNIQ_P2)])

    assert sorted(servidor.nos().values()) == sorted(
        [af.nome_do_sink(_UNIQ_P1), af.nome_do_sink(_UNIQ_P2)]
    )
    assert sorted(servidor.lacos()) == sorted([
        (f"{af.nome_do_sink(_UNIQ_P1)}.monitor", _SINK_P1),
        (f"{af.nome_do_sink(_UNIQ_P2)}.monitor", _SINK_P2),
    ])


def test_o_laco_do_cabo_usa_os_dois_canais_da_frente(
    servidor: ServidorDeSomDeMentira, usb_da_bancada: None
) -> None:
    """O mapa (`audio.alto_falante@dualsense`, `cabo_canal`) diz *canais 1-2*."""
    GerenciadorDeNosDeSom().reconciliar([_cabo(_UNIQ_P1)])
    lacos = [a for a in servidor.modulos.values() if a[0] == "module-loopback"]
    assert len(lacos) == 1
    assert "channel_map=front-left,front-right" in lacos[0]


def test_sem_placa_de_som_no_cabo_o_no_nao_nasce_e_a_rota_diz_por_que(
    servidor: ServidorDeSomDeMentira,
) -> None:
    """O `pactl` sem nenhum sink de DualSense é "não sei", e "não sei" se diz.

    O dono só publica quem tem rota (a trava de
    `test_o_no_de_som_nao_nasce_sumidouro.py`): sem placa, nenhum
    `module-null-sink` entra no servidor, e a frase mora em `rota.motivo`.

    MORDIDA: tire a guarda «SEM ROTA, SEM NÓ» de `GerenciadorDeNosDeSom._erguer`
    e um nó mudo entra na lista de som do usuário.
    """
    servidor.placas = ()
    GerenciadorDeNosDeSom().reconciliar([_cabo(_UNIQ_NUNCA_VISTO)])
    assert servidor.nos() == {}
    rota = af.rota_do_no(_UNIQ_NUNCA_VISTO, af.TRANSPORTE_CABO, (_UNIQ_NUNCA_VISTO,))
    assert rota.tem_rota is False
    assert rota.motivo == af.MOTIVO_NO_SEM_PLACA_NO_CABO


def test_no_radio_sem_ponte_a_rota_recusa_com_a_frase() -> None:
    """A queixa histórica dela."""
    for ponte in (None, lambda: False):
        rota = af.rota_do_no(_UNIQ_P2, af.TRANSPORTE_RADIO, ponte_do_radio=ponte)
        assert rota.tem_rota is False
        assert rota.motivo == af.MOTIVO_NO_SEM_PONTE_NO_RADIO
    com_ponte = af.rota_do_no(_UNIQ_P2, af.TRANSPORTE_RADIO, ponte_do_radio=lambda: True)
    assert com_ponte.por_onde == af.POR_RADIO
    assert com_ponte.sink == ""


def test_a_frase_do_radio_diz_as_tres_coisas() -> None:
    """O quê, por quê, e o que fazer — e sem palavra de dentro da máquina."""
    frase = af.MOTIVO_NO_SEM_PONTE_NO_RADIO

    assert "som" in frase.lower()
    assert "rádio" in frase.lower()
    assert "falta" in frase.lower() or "não está" in frase.lower()
    assert "Ligue-o no cabo" in frase
    for proibida in ("hidraw", "uniq", "MAC", "sink", "mesa"):
        assert proibida not in frase
    assert "não sabe montar" not in frase
    assert af.a_ponte_do_radio_sabe_montar() is True


@pytest.mark.parametrize(
    "mesa",
    [
        [_cabo(_UNIQ_P1)],
        [_radio(_UNIQ_P1)],
        [_cabo(_UNIQ_P1), _radio(_UNIQ_P3)],
        [_radio(_UNIQ_P3), _cabo(_UNIQ_P2), _radio(_UNIQ_P4)],
        [_cabo(_UNIQ_P1), _cabo(_UNIQ_P2), _radio(_UNIQ_P3), _radio(_UNIQ_P4)],
    ],
    ids=["um-no-cabo", "um-no-radio", "dois-misturados", "três", "quatro"],
)
def test_um_no_por_controle_no_servidor(
    mesa: list[ControleNaLista],
    servidor: ServidorDeSomDeMentira,
    usb_da_bancada: None,
) -> None:
    """O servidor tem UM nó por controle, com o rótulo do assento, e mais nada."""
    ger = GerenciadorDeNosDeSom(ponte_do_radio_por_controle=_ponte_de_pe)
    ger.reconciliar(mesa)
    ger.reconciliar(mesa)

    esperados = sorted(af.nome_do_sink(c.uniq) for c in mesa)
    assert sorted(servidor.nos().values()) == esperados
    for controle in mesa:
        nome = af.nome_do_sink(controle.uniq)
        assert servidor.rotulo(nome) == af.rotulo_do_alto_falante(_ASSENTO[controle.uniq])
    placa = {_UNIQ_P1: _SINK_P1, _UNIQ_P2: _SINK_P2}
    assert sorted(servidor.lacos()) == sorted(
        (f"{af.nome_do_sink(c.uniq)}.monitor", placa[c.uniq])
        for c in mesa
        if not af.e_radio(c.transporte)
    )


def test_quem_sai_da_mesa_leva_so_o_seu_no(
    servidor: ServidorDeSomDeMentira, usb_da_bancada: None
) -> None:
    """Tirar um controle derruba o nó DELE — e a rota antes do nó."""
    ger = GerenciadorDeNosDeSom(ponte_do_radio_por_controle=_ponte_de_pe)
    ger.reconciliar([_cabo(_UNIQ_P1), _cabo(_UNIQ_P2), _radio(_UNIQ_P3)])
    ger.reconciliar([_cabo(_UNIQ_P1), _radio(_UNIQ_P3)])

    assert sorted(servidor.nos().values()) == sorted(
        [af.nome_do_sink(_UNIQ_P1), af.nome_do_sink(_UNIQ_P3)]
    )
    assert servidor.lacos() == [(f"{af.nome_do_sink(_UNIQ_P1)}.monitor", _SINK_P1)]
    ger.parar()
    assert servidor.modulos == {}


def test_a_mascara_nao_entra_em_assinatura_nenhuma_do_dono() -> None:
    """Som não é entrada, e a máscara é do gamepad — pedido, literal."""
    for alvo in (
        af.nome_do_sink,
        af.descricao_do_alto_falante,
        af.rotulo_do_alto_falante,
        af.rota_do_no,
        af.SinkVirtualPipeWire.__init__,
        GerenciadorDeNosDeSom.reconciliar,
    ):
        parametros = inspect.signature(alvo).parameters
        assert "flavor" not in parametros, alvo
        assert "mascara" not in parametros, alvo
    assert "flavor" not in {f.name for f in ControleNaLista.__dataclass_fields__.values()}


def test_um_controle_que_nunca_esteve_aqui_ganha_o_mesmo_no(
    servidor: ServidorDeSomDeMentira,
) -> None:
    """Nenhum passo desta régua depende dos DualSense desta bancada.

    O `_UNIQ_NUNCA_VISTO` é de outra faixa sintética: pelo rádio, com a ponte
    de pé, ele ganha o nó de nome normal.

    MORDIDA: amarre o nome ao endereço de um controle conhecido e este teste
    passa a exigir um aparelho específico para dar verde.
    """
    GerenciadorDeNosDeSom(ponte_do_radio_por_controle=_ponte_de_pe).reconciliar(
        [_radio(_UNIQ_NUNCA_VISTO)]
    )
    assert list(servidor.nos().values()) == [af.nome_do_sink(_UNIQ_NUNCA_VISTO)]
    rotulo = servidor.rotulo(af.nome_do_sink(_UNIQ_NUNCA_VISTO))
    assert rotulo == "Alto-falante do Controle 4" + _SONY
