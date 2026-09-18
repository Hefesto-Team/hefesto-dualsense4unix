"""HAPTICA-POR-RADIO-01 (P3b) — o device KS quando o endpoint é um nó nosso.

Pelo rádio o controle não tem placa de som: quem publica o endpoint é o produto,
com um ``module-null-sink`` vestido de DualSense. O ``ContainerId`` então não
sai do controle — sai do ``usb_device`` que o nó declara em ``sysfs.path``, a
ÂNCORA. É a conta do ``winepulse`` (``get_container_id``, ``pulse.c:608``) com a
mesma entrada, e é por isso que ninguém precisa combinar a escolha da âncora
entre o daemon e o lançador.

Nenhuma régua daqui toca aparelho: o sysfs é de mentira e o ``pactl`` é dublê.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

_SINK = """Sink #61764
\tState: SUSPENDED
\tName: {nome}
\tSample Specification: float32le 4ch 48000Hz
\tProperties:
\t\tdevice.bus = "usb"
\t\tdevice.vendor.id = "{vid}"
\t\tdevice.product.id = "{pid}"
\t\t{sysfs}
\t\taudio.channels = "4"
"""

_OUTRO = """Sink #37984
\tState: IDLE
\tName: alsa_output.pci-0000_0c_00.4.iec958-stereo
\tProperties:
\t\tdevice.bus = "pci"
\t\tsysfs.path = "/devices/pci0000:00/0000:0c:00.4/sound/card1"
"""

#: O `USEC_INITIALIZED` da âncora, e o NÚMERO É ESCOLHIDO: os oito bytes dele
#: viram os últimos campos do GUID, e um valor qualquer sai como doze hex
#: seguidos — que a régua do anonimato lê como endereço de rádio, com razão.
#: Este cai na faixa sintética da casa (`aabbcc…`) e continua sendo um tempo de
#: máquina plausível (≈10 dias de `uptime` em µs).
_USEC_DA_ANCORA = 0xCCBBAA0000

_NOME_DO_NO = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTOaabbcc-00.HiFi__Speaker__sink"
)
_CAMINHO_DA_ANCORA = "/devices/pci0000:00/0000:00:08.1/usb3/3-4"


def _sinks(
    *,
    vid: str = "054c",
    pid: str = "0ce6",
    caminho: str | None = _CAMINHO_DA_ANCORA,
    nome: str = _NOME_DO_NO,
) -> str:
    sysfs = f'sysfs.path = "{caminho}"' if caminho is not None else 'device.icon_name = "x"'
    return _OUTRO + "\n" + _SINK.format(nome=nome, vid=vid, pid=pid, sysfs=sysfs)


def _dubles(saida: str):
    def runner(argv: list[str]) -> str | None:
        assert argv[:3] == ["pactl", "list", "sinks"]
        return saida

    return runner


@pytest.fixture
def sysfs(tmp_path: Path) -> Path:
    """Um sysfs de mentira com a âncora (um hub, sem placa de som)."""
    raiz = tmp_path / "sys"
    ancora = raiz / _CAMINHO_DA_ANCORA.lstrip("/")
    ancora.mkdir(parents=True)
    (ancora / "idVendor").write_text("2357\n")
    (ancora / "idProduct").write_text("0604\n")
    (ancora / "busnum").write_text("3\n")
    (ancora / "devnum").write_text("29\n")
    (ancora / "dev").write_text("189:284\n")
    return raiz


@pytest.fixture
def udev(tmp_path: Path) -> Path:
    banco = tmp_path / "udev"
    banco.mkdir()
    (banco / "c189:284").write_text(f"I:{_USEC_DA_ANCORA}\nE:FOO=1\n")
    return banco


# -- a leitura dos nós --------------------------------------------------------


def test_o_no_vestido_de_dualsense_e_lido() -> None:
    assert ks.endpoints_de_mentira(_dubles(_sinks())) == [(0x0CE6, _CAMINHO_DA_ANCORA)]


def test_o_no_sem_sysfs_path_fica_de_fora() -> None:
    """Sem ele o Wine tira GUID_NULL, que é o ContainerId da caixa de som dela."""
    assert ks.endpoints_de_mentira(_dubles(_sinks(caminho=None))) == []


def test_so_o_vid_pid_da_sony_conta() -> None:
    assert ks.endpoints_de_mentira(_dubles(_sinks(vid="1532"))) == []
    assert ks.endpoints_de_mentira(_dubles(_sinks(pid="0001"))) == []


def test_sem_pactl_nao_ha_endpoint() -> None:
    assert ks.endpoints_de_mentira(lambda _argv: None) == []


# -- a subida até o usb_device ------------------------------------------------


def test_o_pai_usb_device_e_o_primeiro_com_busnum_e_devnum(sysfs: Path) -> None:
    fundo = sysfs / _CAMINHO_DA_ANCORA.lstrip("/") / "3-4:1.0" / "sound" / "card9"
    fundo.mkdir(parents=True)
    achado = ks.pai_usb_device(f"{_CAMINHO_DA_ANCORA}/3-4:1.0/sound/card9", sysfs)
    assert achado == (sysfs / _CAMINHO_DA_ANCORA.lstrip("/")).resolve()


def test_caminho_sem_pai_usb_nao_inventa_ancora(sysfs: Path) -> None:
    solto = sysfs / "devices" / "pci0000:00" / "0000:0c:00.4"
    solto.mkdir(parents=True)
    assert ks.pai_usb_device("/devices/pci0000:00/0000:0c:00.4", sysfs) is None


def test_caminho_fora_do_sysfs_e_recusado(sysfs: Path) -> None:
    """`sysfs.path` vem de um proplist, que é texto de fora: não se confia."""
    assert ks.pai_usb_device("/../../etc", sysfs) is None


# -- o ContainerId ------------------------------------------------------------


def test_o_container_id_e_o_da_ancora_nao_o_do_controle(sysfs: Path, udev: Path) -> None:
    (controle,) = ks.controles_no_radio(sysfs, udev, _dubles(_sinks()))
    # `Data1 = MAKELONG(vid, pid)` da ÂNCORA (2357/0604), não da Sony.
    assert controle.prefixo_do_container() == "{06042357-0003-001d-"
    assert controle.pid == 0x0CE6, "o nome e o HardwareID continuam do controle"
    assert controle.usec == _USEC_DA_ANCORA


def test_a_conta_bate_com_a_do_wine_byte_a_byte(sysfs: Path, udev: Path) -> None:
    (controle,) = ks.controles_no_radio(sysfs, udev, _dubles(_sinks()))
    d4 = (_USEC_DA_ANCORA).to_bytes(8, "little")
    assert ks.container_id(controle, d4) == "{06042357-0003-001d-0000-aabbcc000000}"


def test_o_barramento_acima_de_255_dobra_como_no_c(sysfs: Path, udev: Path) -> None:
    """Na origem `bus_num` e `dev_num` são `uint8_t`. 260 & 0xFF == 4."""
    (sysfs / _CAMINHO_DA_ANCORA.lstrip("/") / "devnum").write_text("260\n")
    (controle,) = ks.controles_no_radio(sysfs, udev, _dubles(_sinks()))
    assert controle.prefixo_do_container().endswith("-0004-")


def test_sem_o_banco_do_udev_o_data4_e_zero(sysfs: Path, tmp_path: Path) -> None:
    """O runtime da Steam pode não enxergar /run/udev — e aí o campo sai zero."""
    (controle,) = ks.controles_no_radio(sysfs, tmp_path / "vazio", _dubles(_sinks()))
    assert controle.usec is None
    assert ks.variantes_de_data4(controle, []) == [bytes(8)]


def test_as_duas_variantes_de_data4_saem_no_radio(sysfs: Path, udev: Path) -> None:
    (controle,) = ks.controles_no_radio(sysfs, udev, _dubles(_sinks()))
    assert ks.variantes_de_data4(controle, []) == [
        bytes(8),
        (_USEC_DA_ANCORA).to_bytes(8, "little"),
    ]


# -- a fronteira com o cabo ---------------------------------------------------


def test_ancora_com_placa_de_som_e_o_cabo_e_nao_entra(sysfs: Path, udev: Path) -> None:
    """O `sysfs.path` de um DualSense no cabo sobe ao PRÓPRIO controle.

    Sem esta recusa o mesmo aparelho sairia nas duas listas, e as duas
    gravariam a MESMA chave do registro.
    """
    (sysfs / _CAMINHO_DA_ANCORA.lstrip("/") / "3-4:1.0" / "sound" / "card3").mkdir(parents=True)
    assert ks.controles_no_radio(sysfs, udev, _dubles(_sinks())) == []


def test_o_registro_do_radio_tem_o_hardware_id_da_sony(sysfs: Path, udev: Path) -> None:
    (controle,) = ks.controles_no_radio(sysfs, udev, _dubles(_sinks()))
    texto = "\n".join(ks.blocos_do_controle(controle, [bytes(8)], 1758000000))
    assert "USB\\\\VID_054C&PID_0CE6" in texto
    assert '"ContainerId"="{06042357-0003-001d-0000-000000000000}"' in texto
    assert f'"FriendlyName"="{ks.MODELOS[0x0CE6]}"' in texto


def test_a_instancia_do_radio_e_reconhecida_como_nossa(sysfs: Path, udev: Path) -> None:
    """Sem isso a rodada seguinte não apagaria a instância velha."""
    (controle,) = ks.controles_no_radio(sysfs, udev, _dubles(_sinks()))
    for bloco in ks.blocos_do_controle(controle, [bytes(8)], 1758000000):
        assert ks.e_bloco_nosso(bloco), bloco.split("\n", 1)[0]
