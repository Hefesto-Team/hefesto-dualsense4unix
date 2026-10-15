"""O vigia do zumbi lê os enlaces pelo kernel, sem o ``hcitool``.

O-VIGIA-DO-ZUMBI-LE-OS-ENLACES-PELO-KERNEL-01. O ``hcitool`` só se compila com
``--enable-deprecated``, e o Arch e o Fedora o deixam fora do pacote que o
instalador põe: ali o vigia ficava cego. O ``HCIGETCONNLIST`` e o
``HCIGETDEVINFO``, que o ``hcitool con`` e o ``hcitool dev`` fazem por baixo, o
``LeitorDoKernel`` já lê pelo socket HCI cru, sem root. Todo caso aqui roda com
um ``PATH`` sem ``hcitool``, e o ioctl é de mentira: nada toca o rádio.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import conexao_zumbi as cz
from tests.unit.test_o_ar_do_adaptador import KernelDeMentira

DONGLE_A = "aa:bb:cc:00:00:11"
DONGLE_B = "aa:bb:cc:00:00:33"
SAO = "aa:bb:cc:00:00:22"
OUTRO = "aa:bb:cc:00:00:55"
FONE = "aa:bb:cc:00:00:66"
ZUMBI = "aa:bb:cc:00:00:44"

TIPO_SCO = 0x00


@pytest.fixture(autouse=True)
def _sem_hcitool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O cenário sob teste: a máquina sem a ferramenta depreciada."""
    vazio = tmp_path / "bin-sem-hcitool"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    assert shutil.which("hcitool") is None


def _mesa() -> tuple[KernelDeMentira, ar.LeitorDoKernel]:
    """Dois ACL e um SCO no ``hci0``, um ACL no ``hci1``."""
    kernel = KernelDeMentira()
    kernel.por(0, DONGLE_A)["enlaces"] = [
        (5, SAO, ar.TIPO_ACL),
        (6, OUTRO, ar.TIPO_ACL),
        (7, FONE, TIPO_SCO),
    ]
    kernel.por(1, DONGLE_B)["enlaces"] = [(9, ZUMBI, ar.TIPO_ACL)]
    return kernel, ar.LeitorDoKernel(ioctl=kernel.ioctl)


def _mudo(tmp_path: Path) -> Path:
    """O sysfs desta máquina: os nós existem e o ``address`` não (kernel 7.1.5)."""
    raiz = tmp_path / "bluetooth"
    (raiz / "hci0").mkdir(parents=True)
    (raiz / "hci0:5").mkdir()
    return raiz


def test_os_enlaces_acl_saem_do_kernel_cada_um_no_seu_adaptador() -> None:
    """MORDIDA: com o ``hcitool -i hciN con`` de volta, a lista sai vazia sem ele no PATH."""
    _kernel, leitor = _mesa()

    achados, impedimentos = cz.links_de_pe({"hci0": DONGLE_A, "hci1": DONGLE_B}, leitor=leitor)

    assert impedimentos == []
    assert sorted((link.hci, link.adaptador, link.controle) for link in achados) == [
        ("hci0", DONGLE_A, SAO),
        ("hci0", DONGLE_A, OUTRO),
        ("hci1", DONGLE_B, ZUMBI),
    ]


def test_o_sco_nao_e_controle() -> None:
    """MORDIDA: sem o filtro do ``Enlace.tipo``, o áudio do fone entra como enlace de controle."""
    _kernel, leitor = _mesa()

    achados, _ = cz.links_de_pe({"hci0": DONGLE_A}, leitor=leitor)

    assert FONE not in {link.controle for link in achados}


def test_o_kernel_que_nao_responde_e_impedimento_e_nao_lista_vazia() -> None:
    """«Não sei» vai ao diário com o adaptador; «nenhum enlace» não."""
    kernel, leitor = _mesa()
    kernel.falhar.add(ar.HCIGETCONNLIST)

    achados, impedimentos = cz.links_de_pe({"hci0": DONGLE_A, "hci1": DONGLE_B}, leitor=leitor)

    assert achados == []
    assert impedimentos == [
        "o kernel não listou as conexões de rádio de hci0",
        "o kernel não listou as conexões de rádio de hci1",
    ]

    vazio = KernelDeMentira()
    vazio.por(0, DONGLE_A)
    assert cz.links_de_pe({"hci0": DONGLE_A}, leitor=ar.LeitorDoKernel(ioctl=vazio.ioctl)) == (
        [],
        [],
    )


def test_os_adaptadores_descem_para_o_kernel_quando_o_sysfs_cala(tmp_path: Path) -> None:
    """MORDIDA: com o ``hcitool dev`` de volta, o sysfs mudo deixa a mesa sem adaptador."""
    kernel, leitor = _mesa()
    kernel.por(2, "aa:bb:cc:00:00:77", ligado=False)

    assert cz.adaptadores_na_mesa(_mudo(tmp_path), leitor=leitor) == {
        "hci0": DONGLE_A,
        "hci1": DONGLE_B,
    }


def test_o_sysfs_que_responde_nao_pergunta_ao_kernel(tmp_path: Path) -> None:
    kernel, leitor = _mesa()
    raiz = tmp_path / "bluetooth"
    (raiz / "hci0").mkdir(parents=True)
    (raiz / "hci0" / "address").write_text(DONGLE_A.upper() + "\n", encoding="utf-8")

    assert cz.adaptadores_na_mesa(raiz, leitor=leitor) == {"hci0": DONGLE_A}
    assert kernel.pedidos == []


def test_a_mesa_inteira_acha_o_zumbi_sem_o_hcitool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De ponta a ponta: ACL no kernel, sem objeto no BlueZ, sem ``hidraw`` com o endereço."""
    _kernel, leitor = _mesa()
    monkeypatch.setattr(
        cz,
        "enderecos_que_o_bluez_conhece",
        lambda **_k: {("hci0", SAO), ("hci0", OUTRO)},
    )

    links, com_hid, conhecidos, impedimentos = cz.olhar_a_mesa(
        raiz_adaptadores=_mudo(tmp_path),
        raiz_hidraw=tmp_path / "hidraw-vazio",
        leitor=leitor,
    )

    assert impedimentos == []
    assert cz.zumbis(links, com_hid, conhecidos) == [
        cz.LinkDeRadio(hci="hci1", adaptador=DONGLE_B, controle=ZUMBI)
    ]


def test_o_vigia_nao_cita_mais_o_hcitool() -> None:
    """O contato com a ferramenta depreciada sai do código, e por isso sai do censo."""
    fonte = Path(cz.__file__).read_text(encoding="utf-8")
    assert '"hcitool"' not in fonte
    censo = Path(__file__).resolve().parents[2] / "docs" / "data" / "contratos-de-fora.csv"
    assert "conexao_zumbi.py,cmd:hcitool" not in censo.read_text(encoding="utf-8")
