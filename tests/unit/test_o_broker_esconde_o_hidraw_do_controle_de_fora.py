"""O-BROKER-ESCONDE-O-HIDRAW-DO-CONTROLE-DE-FORA-01.

O broker esconde o hidraw do controle de fora (Pro Controller, 8BitDo, qualquer controle de jogo
que não é DualSense) pelo que o aparelho É no ``/sys``: barramento USB ou Bluetooth e um nó de
entrada com tecla de controle de jogo. Esconder guarda o modo e a ACL de antes; devolver põe
exatamente aquilo de volta, e só no MESMO aparelho.

A MORDIDA: faça o ``_cmd_hide_externo`` devolver ``None`` sempre, e o hide do Pro Controller
volta a ``reject_not_physical_dualsense``; tire o ``_tem_entrada_de_controle`` do
``_pai_hid_e_controle_de_fora``, e o receptor do mouse passa a ser escondido; troque o modo
guardado por ``0o660`` fixo, e o controle volta com permissão que nunca teve.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import (
    VPAD_PHYS_PREFIX,
    BrokerState,
    FsAclOps,
    validate_external_node,
)

UID = os.getuid()
TECLAS_DE_CONTROLE = "7fdb000000000000 0 0 0 0"
TECLAS_DE_MOUSE = "1f0000 0 0 0 0"
MAC_ADAPTADOR = "aa:bb:cc:00:00:01"
MAC_CONTROLE = "e8:47:3a:00:00:07"


def _chr_stat(_caminho: str) -> Any:
    return SimpleNamespace(st_mode=stat.S_IFCHR | 0o660, st_rdev=os.makedev(237, 3))


def _arvore(
    tmp_path: Path,
    *,
    hid_id: str = "0003:0000057E:00002009",
    pai: str = "real",
    teclas: str | None = TECLAS_DE_CONTROLE,
    phys: str = "usb-0000:00:14.0-1/input0",
    uniq: str = "",
    adaptadores: tuple[str, ...] = (MAC_ADAPTADOR,),
) -> tuple[str, dict[str, str]]:
    dev = tmp_path / "dev"
    dev.mkdir()
    (dev / "hidraw3").touch()
    classe = tmp_path / "sys" / "class" / "hidraw" / "hidraw3"
    classe.mkdir(parents=True)
    (classe / "dev").write_text("237:3\n", encoding="ascii")
    if pai == "real":
        alvo = tmp_path / "sys" / "devices" / "pci0000:00" / "usb1" / "0003:057E:2009.0001"
    elif pai == "uhid":
        alvo = tmp_path / "sys" / "devices" / "virtual" / "misc" / "uhid" / "0005:057E:2009.0002"
    else:
        alvo = tmp_path / "sys" / "devices" / "virtual" / "input" / "input55"
    alvo.mkdir(parents=True)
    (classe / "device").symlink_to(alvo)
    (alvo / "uevent").write_text(
        f"DRIVER=nintendo\nHID_ID={hid_id}\nHID_NAME=Controle\nHID_PHYS={phys}\nHID_UNIQ={uniq}\n",
        encoding="ascii",
    )
    if teclas is not None:
        capacidades = alvo / "input" / "input20" / "capabilities"
        capacidades.mkdir(parents=True)
        (capacidades / "key").write_text(teclas + "\n", encoding="ascii")
    bluetooth = tmp_path / "sys" / "class" / "bluetooth"
    for indice, endereco in enumerate(adaptadores):
        (bluetooth / f"hci{indice}").mkdir(parents=True)
        (bluetooth / f"hci{indice}" / "address").write_text(endereco + "\n", encoding="ascii")
    return str(dev / "hidraw3"), {
        "dev_root": str(dev),
        "sys_class_hidraw": str(tmp_path / "sys" / "class" / "hidraw"),
        "sys_class_bluetooth": str(bluetooth),
    }


def _valida(no: str, raizes: dict[str, str]) -> str | None:
    return validate_external_node(
        no,
        dev_root=raizes["dev_root"],
        sys_class_hidraw=raizes["sys_class_hidraw"],
        sys_class_bluetooth=raizes["sys_class_bluetooth"],
        stat_fn=_chr_stat,
    )


@pytest.mark.parametrize(
    "hid_id",
    ["0003:0000057E:00002009", "0005:0000057E:00002009", "0003:00002DC8:00003106"],
)
def test_o_controle_de_fora_pelo_cabo_e_pelo_radio_e_aceito(tmp_path: Path, hid_id: str) -> None:
    no, raizes = _arvore(tmp_path, hid_id=hid_id)
    assert _valida(no, raizes) == "hidraw3"


def test_o_controle_de_fora_pelo_uhid_do_radio_e_aceito(tmp_path: Path) -> None:
    no, raizes = _arvore(
        tmp_path, hid_id="0005:0000057E:00002009", pai="uhid", phys=MAC_ADAPTADOR, uniq=MAC_CONTROLE
    )
    assert _valida(no, raizes) == "hidraw3"


@pytest.mark.parametrize(
    ("motivo", "kwargs"),
    [
        ("mouse sem tecla de controle", {"teclas": TECLAS_DE_MOUSE}),
        ("sem nó de entrada", {"teclas": None}),
        ("o DualSense é do outro validador", {"hid_id": "0003:0000054C:00000CE6"}),
        ("barramento fora do USB e do rádio", {"hid_id": "0018:0000057E:00002009"}),
        ("entrada virtual do kernel", {"pai": "virtual"}),
        ("uhid que diz cabo", {"pai": "uhid", "phys": MAC_ADAPTADOR, "uniq": MAC_CONTROLE}),
        (
            "uhid com a marca do pad do Hefesto",
            {
                "hid_id": "0005:0000057E:00002009",
                "pai": "uhid",
                "phys": f"{VPAD_PHYS_PREFIX}0",
                "uniq": MAC_CONTROLE,
            },
        ),
        (
            "uhid sem endereço de rádio",
            {"hid_id": "0005:0000057E:00002009", "pai": "uhid", "phys": "x", "uniq": "y"},
        ),
        (
            "uhid de adaptador que não existe",
            {
                "hid_id": "0005:0000057E:00002009",
                "pai": "uhid",
                "phys": "aa:bb:cc:00:00:09",
                "uniq": MAC_CONTROLE,
            },
        ),
    ],
)
def test_o_que_nao_e_controle_de_fora_e_recusado(
    tmp_path: Path, motivo: str, kwargs: dict[str, Any]
) -> None:
    no, raizes = _arvore(tmp_path, **kwargs)
    assert _valida(no, raizes) is None, motivo


class _Disco:
    """O hidraw do controle de fora de mentira: o modo, a ACL e o aparelho que o nome é agora."""

    def __init__(self) -> None:
        self.modo = 0o660
        self.acl: bytes | None = b"acl-de-antes"
        self.pai = "/sys/devices/pro-controller"
        self.toques = 0

    def pai_hid_do_no(self, base: str) -> str:
        return self.pai

    def esconder_externo(self, node: str, base: str, pai: str) -> tuple[int, bytes | None]:
        if pai != self.pai:
            raise FileNotFoundError(node)
        antes = (self.modo, self.acl)
        self.modo, self.acl = 0o600, None
        self.toques += 1
        return antes

    def devolver_externo(
        self, node: str, base: str, pai: str, modo: int, acl: bytes | None
    ) -> None:
        if pai != self.pai:
            raise FileNotFoundError(node)
        self.modo, self.acl = modo, acl
        self.toques += 1


def _o_no(disco: _Disco) -> tuple[int, bytes | None]:
    return disco.modo, disco.acl


def _estado(tmp_path: Path, disco: _Disco, **kwargs: Any) -> BrokerState:
    lista = tmp_path / "sys-class-hidraw"
    (lista / "hidraw3").mkdir(parents=True, exist_ok=True)
    return BrokerState(
        allowed_uid=UID,
        ops=disco,
        validator=lambda _n: None,
        validator_externo=lambda n: "hidraw3" if n == "/dev/hidraw3" else None,
        externos_path=str(tmp_path / "externos"),
        dev_root="/dev",
        sys_class_hidraw=str(lista),
        log=lambda *_a, **_k: None,
        sleep_fn=lambda _s: None,
        **kwargs,
    )


def _pede(st: BrokerState, conn: int, cmd: str) -> dict[str, Any]:
    pedido = json.dumps({"cmd": cmd, "node": "/dev/hidraw3"}).encode()
    resposta, fd = st.handle_line(conn, UID, pedido)
    assert fd is None
    return dict(resposta)


def test_o_hide_fecha_e_o_ultimo_restore_devolve_o_que_havia(tmp_path: Path) -> None:
    disco = _Disco()
    st = _estado(tmp_path, disco)
    assert _pede(st, 1, "hide") == {
        "ok": True, "cmd": "hide", "node": "/dev/hidraw3", "state": "hidden"
    }
    assert (disco.modo, disco.acl) == (0o600, None)
    assert _pede(st, 2, "hide")["state"] == "hidden"
    assert _pede(st, 1, "restore")["state"] == "hidden"
    assert (disco.modo, disco.acl) == (0o600, None)
    assert _pede(st, 2, "restore")["state"] == "exposed"
    assert (disco.modo, disco.acl) == (0o660, b"acl-de-antes")
    assert not (tmp_path / "externos").exists()


def test_o_hide_repetido_fecha_de_novo_sem_trocar_o_que_havia(tmp_path: Path) -> None:
    disco = _Disco()
    st = _estado(tmp_path, disco)
    _pede(st, 1, "hide")
    disco.modo, disco.acl = 0o660, b"acl-que-o-udev-repos"
    _pede(st, 1, "hide")
    assert _o_no(disco) == (0o600, None)
    _pede(st, 1, "restore")
    assert (disco.modo, disco.acl) == (0o660, b"acl-de-antes")


def test_a_conexao_que_fecha_devolve_o_controle(tmp_path: Path) -> None:
    disco = _Disco()
    st = _estado(tmp_path, disco)
    _pede(st, 7, "hide")
    st.on_conn_closed(7)
    assert (disco.modo, disco.acl) == (0o660, b"acl-de-antes")
    assert st.externos == {}


def test_o_nome_reciclado_por_outro_aparelho_nao_e_tocado(tmp_path: Path) -> None:
    disco = _Disco()
    st = _estado(tmp_path, disco)
    _pede(st, 1, "hide")
    disco.pai, disco.modo, disco.acl = "/sys/devices/outro-aparelho", 0o600, b"do-outro"
    toques = disco.toques
    assert _pede(st, 1, "restore")["state"] == "gone"
    assert (disco.modo, disco.acl, disco.toques) == (0o600, b"do-outro", toques)
    assert st.externos == {}


def test_o_broker_novo_herda_a_lista_e_devolve_o_que_ficou_sem_dono(tmp_path: Path) -> None:
    disco = _Disco()
    velho = _estado(tmp_path, disco)
    _pede(velho, 1, "hide")
    gravado = json.loads((tmp_path / "externos").read_text(encoding="utf-8"))
    assert gravado["/dev/hidraw3"]["modo"] == 0o660
    novo = _estado(tmp_path, disco)
    assert sorted(novo.externos) == ["/dev/hidraw3"]
    assert novo.devolver_os_externos_sem_dono() == ["/dev/hidraw3"]
    assert (disco.modo, disco.acl) == (0o660, b"acl-de-antes")
    assert not (tmp_path / "externos").exists()


def test_o_desligar_do_broker_devolve_e_o_reinicio_pedido_nao(tmp_path: Path) -> None:
    disco = _Disco()
    st = _estado(tmp_path, disco, reinicio_sem_abrir=lambda: True)
    _pede(st, 1, "hide")
    st.restore_everything()
    assert disco.modo == 0o600
    assert sorted(_estado(tmp_path, disco).externos) == ["/dev/hidraw3"]
    st = _estado(tmp_path, disco, reinicio_sem_abrir=lambda: False)
    assert st.restore_everything() == ["/dev/hidraw3"]
    assert (disco.modo, disco.acl) == (0o660, b"acl-de-antes")


def test_o_cinto_do_broker_morto_devolve_a_lista(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disco = _Disco()
    caminho = tmp_path / "externos"
    _pede(_estado(tmp_path, disco), 1, "hide")
    monkeypatch.setenv(hb.ALLOWED_UID_ENV, str(UID))
    monkeypatch.setattr(hb, "EXTERNOS_PATH", str(caminho))
    monkeypatch.setattr(hb, "DEV_ROOT", "/dev")
    monkeypatch.setattr(hb, "FsAclOps", lambda **_kw: disco)
    monkeypatch.setattr(hb, "reinicio_sem_abrir_pedido", lambda *a, **k: False)
    monkeypatch.setattr(hb, "restore_all_physical", lambda **_kw: [])
    monkeypatch.setattr(hb, "fechar_todo_fisico", lambda **_kw: [])
    monkeypatch.setattr(hb, "entrega_herdada", lambda *_a: False)
    assert hb.main(["--restore-all-and-exit"]) == 0
    assert (disco.modo, disco.acl) == (0o660, b"acl-de-antes")
    assert not caminho.exists()


def test_o_dualsense_continua_no_caminho_dele(tmp_path: Path) -> None:
    disco = _Disco()
    st = _estado(tmp_path, disco)
    st._validator_externo = lambda _n: None
    resposta = _pede(st, 1, "hide")
    assert resposta["ok"] is False
    assert resposta["error"] == "reject_not_physical_dualsense"
    assert st.externos == {}


def test_as_operacoes_reais_guardam_e_devolvem_o_modo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    no = tmp_path / "hidraw3"
    no.touch()
    os.chmod(no, 0o664)
    classe = tmp_path / "classe" / "hidraw3"
    classe.mkdir(parents=True)
    (classe / "dev").write_text("0:0\n", encoding="ascii")
    ops = FsAclOps(sys_class_hidraw=str(tmp_path / "classe"))
    monkeypatch.setattr(FsAclOps, "_e_char_device", staticmethod(lambda _m: True))
    pai = {"agora": "/sys/devices/pro-controller"}
    monkeypatch.setattr(ops, "pai_hid_do_no", lambda _b: pai["agora"])
    modo, acl = ops.esconder_externo(str(no), "hidraw3", "/sys/devices/pro-controller")
    assert (modo, acl) == (0o664, None)
    assert stat.S_IMODE(no.stat().st_mode) == 0o600
    pai["agora"] = "/sys/devices/outro"
    with pytest.raises(FileNotFoundError):
        ops.devolver_externo(str(no), "hidraw3", "/sys/devices/pro-controller", modo, acl)
    assert stat.S_IMODE(no.stat().st_mode) == 0o600
    pai["agora"] = "/sys/devices/pro-controller"
    ops.devolver_externo(str(no), "hidraw3", "/sys/devices/pro-controller", modo, acl)
    assert stat.S_IMODE(no.stat().st_mode) == 0o664
