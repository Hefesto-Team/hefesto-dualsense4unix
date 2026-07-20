"""Validador do broker hide-hidraw (BROKER-01, desenho 2026-07-20 §3) — hermético.

Prova, com árvore sysfs/dev FAKE (nunca /dev real), a tabela §3.4 completa:
- aceita SÓ DualSense físico 054c:0ce6, nos DOIS transportes (USB 0003 e BT
  0005), com o `HID_ID` no formato ZERO-PREENCHIDO real do kernel;
- ARMADILHA BLUEZ-UHID-01: aceita o BT real do BlueZ ≥5.73 que mora em
  `/devices/virtual/misc/uhid/` (evidência viva 2026-07-20: HID_PHYS = MAC do
  adaptador, HID_UNIQ = MAC do controle) — a regra parkada "rejeita
  /devices/virtual/" MATARIA os DualSense BT reais;
- rejeita o vpad 0df2, o vpad forjado anunciando 0ce6 (D2), o uhid forjado
  USB-sob-uhid (D1), UNIQ/PHYS não-MAC (D3) e PHYS ≠ address de hci* legível
  (D4 — que NUNCA decide com sysfs BT ilegível/vazio);
- rejeita caminho não-canônico, symlink plantado, (major,minor) divergente e
  uevent ilegível (fail-closed — o inverso deliberado do daemon).

Char device não dá para criar sem root — `stat_fn` é injetado com um stat
falso S_IFCHR (o validador aceita o injetável exatamente para isso).
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

from hefesto_dualsense4unix.broker.hidraw_broker import (
    VPAD_PHYS_PREFIX,
    VPAD_UNIQ_PREFIX,
    canonical_hidraw_base,
    validate_physical_node,
)

#: HID_IDs REAIS coletados na máquina de referência (2026-07-18/20, read-only).
HID_ID_USB = "HID_ID=0003:0000054C:00000CE6"
HID_ID_BT = "HID_ID=0005:0000054C:00000CE6"
HID_ID_VPAD = "HID_ID=0003:0000054C:00000DF2"
HID_ID_NINTENDO = "HID_ID=0003:0000057E:00002009"

#: Papel espelhado da evidência viva 2026-07-20 (uhid do BlueZ 5.85):
#: HID_PHYS = MAC do ADAPTADOR, HID_UNIQ = MAC do CONTROLE. Valores SINTÉTICOS
#: das faixas permitidas pela regra de anonimato (aa:bb:cc / e8:47:3a) — MAC
#: real em fixture é vazamento (test_anonimato_de_fixtures).
MAC_ADAPTADOR = "aa:bb:cc:00:00:01"
MAC_CONTROLE = "e8:47:3a:00:00:07"

_RDEV = os.makedev(237, 3)


def _chr_stat(rdev: int = _RDEV) -> Any:
    """stat falso de char device (S_IFCHR) — o que os testes não podem criar."""
    return SimpleNamespace(st_mode=stat.S_IFCHR | 0o660, st_rdev=rdev)


class _TreeKwargs(TypedDict):
    """Raízes fake injetadas no validador (o TypedDict deixa o `**` tipado)."""

    dev_root: str
    sys_class_hidraw: str
    sys_class_bluetooth: str


def _uevent_bt_uhid(
    *,
    hid_id: str = HID_ID_BT,
    phys: str | None = MAC_ADAPTADOR,
    uniq: str | None = MAC_CONTROLE,
) -> str:
    """uevent como o bluetoothd ≥5.73 (uhid) o expõe para um DualSense BT."""
    linhas = ["DRIVER=playstation", hid_id, "HID_NAME=DualSense Wireless Controller"]
    if phys is not None:
        linhas.append(f"HID_PHYS={phys}")
    if uniq is not None:
        linhas.append(f"HID_UNIQ={uniq}")
    return "\n".join(linhas) + "\n"


def _make_tree(
    tmp_path: Path,
    *,
    base: str = "hidraw3",
    hid_id: str = HID_ID_USB,
    dev: str = "237:3",
    parent: str = "real",
    uevent: str | None = None,
    adapters: list[str] | None = None,
    sem_uevent: bool = False,
) -> tuple[str, _TreeKwargs]:
    """Monta dev/ + sys/class/hidraw/<base>/ fake; devolve (node, kwargs).

    `parent`: "real" (dir comum — USB/BT clássico), "uhid" (symlink para
    /devices/virtual/misc/uhid/ — BlueZ ≥5.73 E uhid forjado) ou "virtual"
    (symlink para /devices/virtual/input/ — uinput puro).
    `adapters`: MACs em sys/class/bluetooth/hciN/address; None = diretório
    AUSENTE (sysfs BT ilegível); lista com "" = hci sem address legível.
    """
    dev_root = tmp_path / "dev"
    dev_root.mkdir(exist_ok=True)
    node = dev_root / base
    node.touch()
    sys_hidraw = tmp_path / "sys" / "class" / "hidraw"
    entry = sys_hidraw / base
    entry.mkdir(parents=True, exist_ok=True)
    (entry / "dev").write_text(dev + "\n", encoding="ascii")
    if parent == "uhid":
        target = tmp_path / "sys" / "devices" / "virtual" / "misc" / "uhid" / "0005:054C:0CE6.0006"
        target.mkdir(parents=True, exist_ok=True)
        (entry / "device").symlink_to(target)
    elif parent == "virtual":
        target = tmp_path / "sys" / "devices" / "virtual" / "input" / "input55"
        target.mkdir(parents=True, exist_ok=True)
        (entry / "device").symlink_to(target)
    else:
        (entry / "device").mkdir(exist_ok=True)
    conteudo = (
        uevent
        if uevent is not None
        else f"DRIVER=playstation\n{hid_id}\nHID_NAME=DualSense Wireless Controller\n"
    )
    if not sem_uevent:
        (entry / "device" / "uevent").write_text(conteudo, encoding="ascii")
    sys_bluetooth = tmp_path / "sys" / "class" / "bluetooth"
    if adapters is not None:
        for indice, endereco in enumerate(adapters):
            hci = sys_bluetooth / f"hci{indice}"
            hci.mkdir(parents=True, exist_ok=True)
            if endereco:
                (hci / "address").write_text(endereco + "\n", encoding="ascii")
    kwargs = _TreeKwargs(
        dev_root=str(dev_root),
        sys_class_hidraw=str(sys_hidraw),
        sys_class_bluetooth=str(sys_bluetooth),
    )
    return str(node), kwargs


def _valida(node: str, kwargs: _TreeKwargs) -> str | None:
    return validate_physical_node(node, stat_fn=lambda _p: _chr_stat(), **kwargs)


class TestCanonicalBase:
    def test_aceita_caminho_literal(self) -> None:
        assert canonical_hidraw_base("/dev/hidraw3") == "hidraw3"
        assert canonical_hidraw_base("/dev/hidraw13") == "hidraw13"

    def test_rejeita_traversal_e_lixo(self) -> None:
        assert canonical_hidraw_base("/dev/foo/../hidraw3") is None
        assert canonical_hidraw_base("/dev/../dev/hidraw3") is None
        assert canonical_hidraw_base("//dev/hidraw3") is None
        assert canonical_hidraw_base("/dev/hidraw") is None
        assert canonical_hidraw_base("/dev/hidrawX") is None
        assert canonical_hidraw_base("/dev/tty0") is None
        assert canonical_hidraw_base("/dev/hidraw3 ") is None
        assert canonical_hidraw_base("") is None
        assert canonical_hidraw_base(None) is None
        assert canonical_hidraw_base(3) is None

    def test_dev_root_injetavel(self) -> None:
        assert canonical_hidraw_base("/x/hidraw1", dev_root="/x") == "hidraw1"
        assert canonical_hidraw_base("/dev/hidraw1", dev_root="/x") is None


class TestValidateAceita:
    def test_dualsense_usb(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, hid_id=HID_ID_USB)
        assert _valida(node, kwargs) == "hidraw3"

    def test_dualsense_bt_classico(self, tmp_path: Path) -> None:
        # BT via hid nativo do kernel (BlueZ <5.73): pai HID fora do virtual.
        node, kwargs = _make_tree(tmp_path, base="hidraw7", hid_id=HID_ID_BT)
        assert _valida(node, kwargs) == "hidraw7"

    def test_bt_real_bluez585_sob_uhid(self, tmp_path: Path) -> None:
        # A ARMADILHA BLUEZ-UHID-01: físico REAL apesar de "virtual" no
        # caminho. A regra parkada rejeitaria — este teste trava a cura.
        node, kwargs = _make_tree(
            tmp_path,
            base="hidraw7",
            parent="uhid",
            uevent=_uevent_bt_uhid(),
            adapters=[MAC_ADAPTADOR],
        )
        assert _valida(node, kwargs) == "hidraw7"

    def test_bt_uhid_sem_sysfs_bluetooth(self, tmp_path: Path) -> None:
        # D4 é belt best-effort: sem /sys/class/bluetooth legível (rfkill,
        # adaptador down), NÃO decide — D1-D3 bastam para aceitar.
        node, kwargs = _make_tree(
            tmp_path, base="hidraw7", parent="uhid", uevent=_uevent_bt_uhid(), adapters=None
        )
        assert _valida(node, kwargs) == "hidraw7"

    def test_bt_uhid_hci_sem_address_legivel(self, tmp_path: Path) -> None:
        # Visto ao vivo nesta máquina: hci0 sem `address` legível ⇒ conjunto
        # vazio ⇒ D4 não decide ⇒ aceita pelas D1-D3.
        node, kwargs = _make_tree(
            tmp_path, base="hidraw7", parent="uhid", uevent=_uevent_bt_uhid(), adapters=[""]
        )
        assert _valida(node, kwargs) == "hidraw7"

    def test_uevent_real_completo(self, tmp_path: Path) -> None:
        # O uevent inteiro como o kernel emite (com MODALIAS etc.).
        uevent = (
            "DRIVER=playstation\n"
            f"{HID_ID_USB}\n"
            "HID_NAME=Sony Interactive Entertainment DualSense Wireless Controller\n"
            "HID_PHYS=usb-0000:2d:00.3-4/input3\n"
            "HID_UNIQ=e8:47:3a:aa:bb:cc\n"
            "MODALIAS=hid:b0003g0001v0000054Cp00000CE6\n"
        )
        node, kwargs = _make_tree(tmp_path, uevent=uevent)
        assert _valida(node, kwargs) == "hidraw3"


class TestValidateRejeitaIdentidade:
    def test_vpad_0df2(self, tmp_path: Path) -> None:
        # O vpad 0df2 JAMAIS é escondido/aberto — é por ele que o jogo fala.
        node, kwargs = _make_tree(tmp_path, base="hidraw6", hid_id=HID_ID_VPAD)
        assert _valida(node, kwargs) is None

    def test_vpad_0df2_sob_uhid(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(
            tmp_path,
            base="hidraw6",
            parent="uhid",
            uevent=_uevent_bt_uhid(
                hid_id=HID_ID_VPAD, phys="hefesto-vpad", uniq="02:fe:00:00:00:01"
            ),
        )
        assert _valida(node, kwargs) is None

    def test_nintendo_057e(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, base="hidraw13", hid_id=HID_ID_NINTENDO)
        assert _valida(node, kwargs) is None

    def test_bus_desconhecido(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, hid_id="HID_ID=0006:0000054C:00000CE6")
        assert _valida(node, kwargs) is None

    def test_vendor_errado(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, hid_id="HID_ID=0003:0000045E:00000CE6")
        assert _valida(node, kwargs) is None

    def test_uevent_sem_hid_id(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, uevent="DRIVER=playstation\n")
        assert _valida(node, kwargs) is None

    def test_uevent_ausente(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, sem_uevent=True)
        assert _valida(node, kwargs) is None


class TestValidateRejeitaUhidForjado:
    def test_d1_usb_sob_uhid_e_forjado(self, tmp_path: Path) -> None:
        # USB real NUNCA é uhid: bus 0003 sob /misc/uhid/ = processo forjando.
        node, kwargs = _make_tree(
            tmp_path,
            parent="uhid",
            uevent=_uevent_bt_uhid(hid_id=HID_ID_USB),
            adapters=[MAC_ADAPTADOR],
        )
        assert _valida(node, kwargs) is None

    def test_d2_vpad_anunciando_0ce6_pelo_phys(self, tmp_path: Path) -> None:
        # Vpad hipotético anunciando 0CE6: a identidade do vpad decide.
        node, kwargs = _make_tree(
            tmp_path,
            parent="uhid",
            uevent=_uevent_bt_uhid(phys="hefesto-vpad-p2", uniq=MAC_CONTROLE),
        )
        assert _valida(node, kwargs) is None

    def test_d2_vpad_anunciando_0ce6_pelo_uniq(self, tmp_path: Path) -> None:
        # 02:fe:...  é MAC bem-formado — a D3 sozinha NÃO pegaria; a D2 pega.
        node, kwargs = _make_tree(
            tmp_path,
            parent="uhid",
            uevent=_uevent_bt_uhid(phys=MAC_ADAPTADOR, uniq="02:fe:00:00:00:02"),
        )
        assert _valida(node, kwargs) is None

    def test_d3_uniq_nao_mac(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(
            tmp_path, parent="uhid", uevent=_uevent_bt_uhid(uniq="nao-e-mac")
        )
        assert _valida(node, kwargs) is None

    def test_d3_uniq_ausente(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, parent="uhid", uevent=_uevent_bt_uhid(uniq=None))
        assert _valida(node, kwargs) is None

    def test_d3_phys_nao_mac(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(
            tmp_path, parent="uhid", uevent=_uevent_bt_uhid(phys="usb-0000:2d:00.3-4/input3")
        )
        assert _valida(node, kwargs) is None

    def test_d3_phys_ausente(self, tmp_path: Path) -> None:
        node, kwargs = _make_tree(tmp_path, parent="uhid", uevent=_uevent_bt_uhid(phys=None))
        assert _valida(node, kwargs) is None

    def test_d4_phys_nao_casa_adaptador_legivel(self, tmp_path: Path) -> None:
        # SÓ rejeita porque a leitura dos adaptadores FUNCIONOU e nenhum casou.
        node, kwargs = _make_tree(
            tmp_path,
            parent="uhid",
            uevent=_uevent_bt_uhid(phys="aa:bb:cc:ff:ee:dd"),
            adapters=[MAC_ADAPTADOR],
        )
        assert _valida(node, kwargs) is None

    def test_virtual_puro_nao_uhid(self, tmp_path: Path) -> None:
        # uinput/virtual FORA de /misc/uhid/ jamais é físico — mesmo com
        # uevent perfeito de DualSense BT.
        node, kwargs = _make_tree(tmp_path, parent="virtual", uevent=_uevent_bt_uhid())
        assert _valida(node, kwargs) is None

    def test_uevent_ausente_sob_uhid_fail_closed(self, tmp_path: Path) -> None:
        # O inverso deliberado do daemon: ilegível ⇒ rejeita (não esconder/
        # abrir nó desconhecido), enquanto _is_virtual_hidraw trata como
        # virtual (o risco lá é auto-adoção).
        node, kwargs = _make_tree(tmp_path, parent="uhid", sem_uevent=True)
        assert _valida(node, kwargs) is None


class TestValidateRejeitaFs:
    def test_traversal(self, tmp_path: Path) -> None:
        _node, kwargs = _make_tree(tmp_path)
        fora = f"{kwargs['dev_root']}/../dev/hidraw3"
        assert _valida(fora, kwargs) is None

    def test_symlink_plantado(self, tmp_path: Path) -> None:
        # /dev/hidraw4 -> hidraw3: mesmo com sysfs válido para hidraw4, o
        # lstat pega o link e rejeita (nó plantado).
        node, kwargs = _make_tree(tmp_path, base="hidraw4")
        os.unlink(node)
        os.symlink("hidraw3", node)
        assert _valida(node, kwargs) is None

    def test_nao_char_device(self, tmp_path: Path) -> None:
        # stat REAL: o arquivo comum do tmp não é S_IFCHR → rejeita.
        node, kwargs = _make_tree(tmp_path)
        assert validate_physical_node(node, **kwargs) is None

    def test_major_minor_divergente(self, tmp_path: Path) -> None:
        # sysfs diz 237:4, o nó é 237:3 → symlink/nó plantado → rejeita.
        node, kwargs = _make_tree(tmp_path, dev="237:4")
        assert _valida(node, kwargs) is None

    def test_no_inexistente(self, tmp_path: Path) -> None:
        _node, kwargs = _make_tree(tmp_path)
        ausente = f"{kwargs['dev_root']}/hidraw9"
        assert _valida(ausente, kwargs) is None

    def test_nao_string(self, tmp_path: Path) -> None:
        _node, kwargs = _make_tree(tmp_path)
        assert validate_physical_node(None, **kwargs) is None
        assert validate_physical_node(42, **kwargs) is None


class TestParidadeComOFixBluezUhid01:
    """As constantes de identidade do vpad são ESPELHADAS do daemon.

    O broker é stdlib autocontido (não importa o pacote em runtime) — este
    teste trava a paridade com `_is_virtual_hidraw` (backend_pydualsense),
    dono canônico do fix BLUEZ-UHID-01. Se o blueprint do vpad mudar phys/
    uniq, os DOIS lados precisam mudar juntos.
    """

    def test_phys_prefix_igual_ao_backend(self) -> None:
        from hefesto_dualsense4unix.core.backend_pydualsense import _VPAD_PHYS

        assert VPAD_PHYS_PREFIX == _VPAD_PHYS

    def test_uniq_prefix_igual_ao_backend(self) -> None:
        from hefesto_dualsense4unix.core.backend_pydualsense import _VPAD_UNIQ_PREFIX

        assert VPAD_UNIQ_PREFIX == _VPAD_UNIQ_PREFIX
