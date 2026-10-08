"""A luz do mic pisca com quem ouve de fora, no canal OU na placa que o alimenta.

No cabo o mesmo microfone tem dois nós: o canal `hefesto_mic_<marca>` e a placa
física que o alimenta. Um app que grava a placa ouve a voz do controle, e a peça
A (`ler_quem_ouve`) somava um nó só. A mesa é toda de mentira: o `pactl` é texto,
o casamento USB é um dublê (o real lê o /sys) e o /proc é uma árvore em `tmp_path`.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import types
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from hefesto_dualsense4unix.integrations import quem_ouve_o_microfone as qom
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    CasamentoUSB,
    fontes_dualsense,
)
from tests.unit import pactl_json_de_mentira as pj
from tests.unit.test_a_luz_do_mic_diz_quem_te_escuta import _Controle, _Daemon, _MedidorFalso

UM = "aabbcc0000f1"
OUTRO = "aabbcc0000f2"
RADIO = "aabbcc0000f3"

_ALSA = "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller"
PLACA_UM = f"{_ALSA}-00.iec958-stereo"
PLACA_OUTRO = f"{_ALSA}-00.2.iec958-stereo"
PLACA_DE_FORA_DA_MESA = f"{_ALSA}-00.3.iec958-stereo"

CANAL_UM = canal.nome_do_canal(UM)
CANAL_OUTRO = canal.nome_do_canal(OUTRO)
CANAL_RADIO = canal.nome_do_canal(RADIO)

USB_DA_MESA = CasamentoUSB(
    por_uniq={UM: "1-1", OUTRO: "1-2"},
    por_no={PLACA_UM: "1-1", PLACA_OUTRO: "1-2"},
)


def _short(nos: dict[int, str]) -> str:
    """`pactl list sources short` com a forma medida: índice, nome, driver, formato, estado."""
    return "".join(
        f"{indice}\t{nome}\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n" for indice, nome in nos.items()
    )


def _bloco(indice: int, fonte: int, props: dict[str, str], *, corked: bool = False) -> str:
    """Um `Source Output` do texto longo, com a forma medida."""
    linhas = [
        f"Source Output #{indice}",
        "\tDriver: PipeWire",
        f"\tSource: {fonte}",
        f"\tCorked: {'yes' if corked else 'no'}",
        "\tProperties:",
    ]
    linhas += [f'\t\t{chave} = "{valor}"' for chave, valor in props.items()]
    return "\n".join(linhas) + "\n"


def _de_fora(nome: str, pid: int) -> dict[str, str]:
    """As propriedades de um gravador alheio ao Hefesto."""
    return {
        "client.api": "pipewire-pulse",
        "application.name": nome,
        "application.process.id": str(pid),
        "application.process.binary": "gravador",
        "node.name": nome,
    }


def _o_alimentador(uniq: str, pid: int) -> dict[str, str]:
    """O gravador do próprio Hefesto: o `pacat` que enche o canal, com as propriedades dele."""
    return {
        **canal.propriedades_do_canal(uniq),
        "application.name": "hefesto-canal-do-microfone",
        "application.process.id": str(pid),
        "application.process.binary": "pacat",
    }


@pytest.fixture
def proc(tmp_path: Path) -> Path:
    """Um /proc de mentira: cada pid filho do 1, com a linha de comando do gravador."""
    raiz = tmp_path / "proc"
    for pid in (4001, 4002, 4003):
        pasta = raiz / str(pid)
        pasta.mkdir(parents=True)
        (pasta / "cmdline").write_bytes(b"gravador\0--ao-vivo")
        (pasta / "stat").write_text(f"{pid} (gravador) S 1 0 0 0 -1 0\n", encoding="utf-8")
    return raiz


def _mesa_de_mentira(
    monkeypatch: pytest.MonkeyPatch,
    nos: dict[int, str],
    streams: list[str],
    usb: CasamentoUSB | None,
) -> None:
    """Põe o servidor de som e o casamento USB de mentira atrás do `pactl` e do /sys."""

    def pactl(argv: list[str]) -> tuple[int, str]:
        chave = " ".join(argv[1:])
        if chave == "--format=json list source-outputs":
            return (0, pj.json_do_longo("".join(streams)))
        if chave == "list sources short":
            return (0, _short(nos))
        return (127, "")

    monkeypatch.setattr(qom, "_rodar", pactl)
    monkeypatch.setattr(qom, "casamento_usb_agora", lambda _uniqs: usb)
    monkeypatch.setattr(elm, "casamento_usb_agora", lambda _uniqs: usb)
    monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: fontes_dualsense(_short(nos)))


NOS_DOS_DOIS = {
    700: CANAL_UM,
    701: CANAL_OUTRO,
    710: PLACA_UM,
    711: PLACA_OUTRO,
}


def test_o_gravador_na_placa_do_a_acende_o_a_e_so_o_a(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 1: o canal de pé, o gravador de fora na PLACA do A. Pausado entra no pausados."""
    _mesa_de_mentira(
        monkeypatch,
        NOS_DOS_DOIS,
        [
            _bloco(1500, 710, _de_fora("Gravador de fora", 4001)),
            _bloco(1501, 710, _de_fora("Gravador parado", 4002), corked=True),
        ],
        USB_DA_MESA,
    )

    leitura = qom.ler_quem_ouve([UM, OUTRO], proc)

    assert leitura.por_uniq == {UM: ["Gravador de fora"], OUTRO: []}
    assert leitura.pausados_por_uniq == {UM: ["Gravador parado"], OUTRO: []}
    assert leitura.alguem_ouve(UM) is True
    assert leitura.alguem_ouve(OUTRO) is False


def test_o_gravador_no_canal_do_b_nao_acende_o_a(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 2: ouvinte alheio não acende este controle, em qualquer dos dois nós."""
    _mesa_de_mentira(
        monkeypatch,
        NOS_DOS_DOIS,
        [_bloco(1500, 701, _de_fora("Gravador de fora", 4001))],
        USB_DA_MESA,
    )

    leitura = qom.ler_quem_ouve([UM, OUTRO], proc)

    assert leitura.por_uniq == {UM: [], OUTRO: ["Gravador de fora"]}


def test_o_alimentador_do_canal_na_placa_nao_acende_ninguem(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 3: o `hefesto-canal-do-microfone` lê a placa do A e não conta como ouvinte."""
    _mesa_de_mentira(
        monkeypatch,
        NOS_DOS_DOIS,
        [_bloco(1500, 710, _o_alimentador(UM, 4003))],
        USB_DA_MESA,
    )

    leitura = qom.ler_quem_ouve([UM, OUTRO], proc)

    assert leitura.por_uniq == {UM: [], OUTRO: []}
    assert leitura.alguem_ouve(UM) is False


def test_o_laco_inteiro_pisca_o_a_pelo_gravador_da_placa(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 4: `luz_do_mic_loop` com a peça A de verdade escreve PISCANDO no A, e só nele."""
    _mesa_de_mentira(
        monkeypatch,
        NOS_DOS_DOIS,
        [_bloco(1500, 710, _de_fora("Gravador de fora", 4001))],
        USB_DA_MESA,
    )
    real = qom.quem_ouve_agora
    monkeypatch.setattr(qom, "quem_ouve_agora", lambda uniqs: real(uniqs, proc))
    medidor = _MedidorFalso(lambda seguidos: dict.fromkeys(seguidos, True))
    peca_b = types.ModuleType(luz.MODULO_DO_NIVEL)
    peca_b.NivelDoMicrofone = lambda: medidor  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, luz.MODULO_DO_NIVEL, peca_b)
    for nome, valor in (
        ("INTERVALO_S", 0.001),
        ("INTERVALO_DE_QUEM_OUVE_S", 0.0),
        ("ESPERA_DO_REPORT_S", 0.001),
        ("SEM_RESPOSTA_ATE_SOLTAR_S", 0.05),
    ):
        monkeypatch.setattr(luz, nome, valor)
    controle = _Controle(uniqs=[UM, OUTRO], mudo={UM: False, OUTRO: False})

    async def correr() -> list[tuple[str | None, int | None]]:
        tarefa = asyncio.create_task(
            luz.luz_do_mic_loop(_Daemon(controle))  # type: ignore[arg-type]
        )
        try:
            while controle.voltas < 12:
                await asyncio.sleep(0.002)
            return list(controle.escritas)
        finally:
            tarefa.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarefa

    escritas = asyncio.run(correr())

    ultima = {uniq: valor for uniq, valor in escritas}
    assert ultima[UM] == luz.PISCANDO
    assert ultima[OUTRO] == luz.ACESA


def test_no_radio_o_canal_e_o_unico_no_e_a_conta_e_a_de_sempre(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 5: sem placa nenhuma, o gravador no canal acende o controle como antes."""
    _mesa_de_mentira(
        monkeypatch,
        {700: CANAL_RADIO},
        [_bloco(1500, 700, _de_fora("Gravador de fora", 4001))],
        CasamentoUSB(),
    )

    leitura = qom.ler_quem_ouve([RADIO], proc)

    assert leitura.por_uniq == {RADIO: ["Gravador de fora"]}
    assert leitura.sem_canal == ()


def test_a_placa_de_outro_aparelho_nao_acende_o_do_radio(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 6a: o veto do USB. A placa de um aparelho que não está na mesa não é do rádio."""
    _mesa_de_mentira(
        monkeypatch,
        {700: CANAL_RADIO, 710: PLACA_DE_FORA_DA_MESA},
        [_bloco(1500, 710, _de_fora("Gravador de fora", 4001))],
        CasamentoUSB(por_uniq={RADIO: ""}, por_no={PLACA_DE_FORA_DA_MESA: "1-9"}),
    )

    leitura = qom.ler_quem_ouve([RADIO], proc)

    assert leitura.por_uniq == {RADIO: []}


def test_dois_nos_do_kernel_sem_dono_nao_acendem_um_controle_so(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 6b: sem USB e sem identidade no nome, dois nós do kernel não casam com ninguém."""
    nos = {700: CANAL_RADIO, 710: f"{_ALSA}-00.a", 711: f"{_ALSA}-00.b"}
    _mesa_de_mentira(
        monkeypatch,
        nos,
        [
            _bloco(1500, 710, _de_fora("Gravador um", 4001)),
            _bloco(1501, 711, _de_fora("Gravador dois", 4002)),
        ],
        None,
    )

    leitura = qom.ler_quem_ouve([RADIO], proc)

    assert leitura.por_uniq == {RADIO: []}


def test_antes_do_canal_subir_a_placa_entra_uma_vez_so(
    monkeypatch: pytest.MonkeyPatch, proc: Path
) -> None:
    """Régua 7: só a placa (o «Nativo», ou o canal ainda não subiu). Um gravador, uma vez."""
    _mesa_de_mentira(
        monkeypatch,
        {710: PLACA_UM},
        [_bloco(1500, 710, _de_fora("Gravador de fora", 4001))],
        USB_DA_MESA,
    )

    leitura = qom.ler_quem_ouve([UM], proc)

    assert leitura.por_uniq == {UM: ["Gravador de fora"]}
