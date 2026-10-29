"""O broker que reinicia no install não abre o físico que o anterior escondia.

O-BROKER-NOVO-HERDA-OS-NOS-ESCONDIDOS-01: em 28/10, às 01:26:50, o broker novo serviu o nó
do físico com `state=exposed` até o hide do daemon novo, nove segundos depois. No modo padrão
era só o rótulo do `open`; no modo histórico (`--no-fechar-o-no`) o cinto e o repouso do
começo abriam o nó de verdade.

A MORDIDA: devolva o `no_nasce_fechado and` à condição do cinto em `hidraw_broker.main`
(ou do `restore_everything`), e o modo histórico abre o nó no reinício pedido; devolva o
`"hidden" if canon in self.hidden else "exposed"` ao `_cmd_open`, e o rótulo volta a mentir;
faça o `herdar_no_reinicio`, que o `main` chama, não herdar, e o histórico expõe o físico.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import BrokerState

UID = os.getuid()
NO = "/dev/hidraw3"
MODOS = {"padrão": True, "histórico": False}


class _Disco:
    """O hidraw e os nós de entrada de mentira, com o diário de cada abertura."""

    def __init__(self, *, aberto: bool) -> None:
        self.fechados: set[str] = set() if aberto else {NO}
        self.aberturas: list[str] = []

    def hide(self, node: str, base: str) -> None:
        self.fechados.add(node)

    def restore(self, node: str, base: str, uid: int) -> None:
        self.aberturas.append(node)
        self.fechados.discard(node)

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return node not in self.fechados

    def open_node(self, node: str, base: str) -> int:
        return os.open(os.devnull, os.O_RDONLY | os.O_CLOEXEC)

    def fechar_entradas(self, base: str) -> tuple[list[str], list[str]]:
        return ([], [])

    def abrir_entradas(self, base: str, uid: int) -> tuple[list[str], list[str]]:
        return ([], [])

    def entradas_abertas(self, base: str) -> list[str]:
        return []

    def entradas_fechadas_para(self, base: str, uid: int) -> list[str]:
        return []


def _estado(tmp_path: Path, disco: _Disco, *, no_nasce_fechado: bool, pedido: bool) -> BrokerState:
    lista = tmp_path / "sys-class-hidraw"
    (lista / "hidraw3").mkdir(parents=True, exist_ok=True)
    return BrokerState(
        allowed_uid=UID,
        ops=disco,
        validator=lambda n: n.rsplit("/", 1)[-1] if n == NO else None,
        dev_root="/dev",
        sys_class_hidraw=str(lista),
        log=lambda *_a, **_k: None,
        sleep_fn=lambda _s: None,
        no_nasce_fechado=no_nasce_fechado,
        reinicio_sem_abrir=lambda: pedido,
    )


def _pede(st: BrokerState, conn: int, payload: dict[str, Any]) -> dict[str, Any]:
    resposta, fd = st.handle_line(conn, UID, json.dumps(payload).encode())
    if fd is not None:
        os.close(fd)
    return dict(resposta)


def _cinto(monkeypatch: pytest.MonkeyPatch, disco: _Disco, *, no_nasce_fechado: bool) -> None:
    """O `ExecStopPost` do broker morto e o `ExecStartPre` do novo, com o disco de mentira."""

    def _abrir_tudo(**_kw: Any) -> list[str]:
        for no in sorted(disco.fechados):
            disco.restore(no, no.rsplit("/", 1)[-1], UID)
        return [NO]

    monkeypatch.setenv(hb.ALLOWED_UID_ENV, str(UID))
    monkeypatch.setenv(hb.NO_NASCE_FECHADO_ENV, "1" if no_nasce_fechado else "0")
    monkeypatch.setattr(hb, "reinicio_sem_abrir_pedido", lambda *a, **k: True)
    monkeypatch.setattr(hb, "restore_all_physical", _abrir_tudo)
    monkeypatch.setattr(hb, "fechar_todo_fisico", lambda **_kw: [])
    monkeypatch.setattr(hb, "entrega_herdada", lambda *_a: False)
    assert hb.main(["--restore-all-and-exit"]) == 0


@pytest.mark.parametrize("modo", sorted(MODOS))
def test_o_reinicio_pedido_nao_abre_o_no_ate_o_hide_do_daemon_novo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modo: str
) -> None:
    fechado_de_nascenca = MODOS[modo]
    disco = _Disco(aberto=not fechado_de_nascenca)
    velho = _estado(tmp_path, disco, no_nasce_fechado=fechado_de_nascenca, pedido=True)
    assert _pede(velho, 1, {"cmd": "hide", "node": NO})["state"] == "hidden"
    disco.aberturas.clear()

    _cinto(monkeypatch, disco, no_nasce_fechado=fechado_de_nascenca)
    herdar = hb.o_reinicio_herda(no_nasce_fechado=fechado_de_nascenca)
    assert herdar is (not fechado_de_nascenca)
    repouso = hb._o_repouso_do_inicio(UID, no_nasce_fechado=fechado_de_nascenca, herdar=herdar)
    assert repouso is False
    novo = _estado(tmp_path, disco, no_nasce_fechado=fechado_de_nascenca, pedido=True)
    broker = hb.Broker(novo, None, log=lambda *_a, **_k: None)
    herdados = hb.herdar_no_reinicio(novo, broker, herdar=herdar)
    assert herdados == ([] if fechado_de_nascenca else [NO])
    assert (broker._sem_cliente_desde is not None) is bool(herdados)

    aberto = _pede(novo, 7, {"cmd": "open", "node": NO})
    assert aberto["ok"] is True and aberto["state"] == "fechado"
    assert _pede(novo, 7, {"cmd": "hide", "node": NO})["state"] == "hidden"
    assert disco.aberturas == [], "o nó abriu entre a morte do broker velho e o hide do novo"
    assert NO in disco.fechados


def test_sem_cliente_na_graca_o_historico_devolve_o_herdado(tmp_path: Path) -> None:
    disco = _Disco(aberto=False)
    novo = _estado(tmp_path, disco, no_nasce_fechado=False, pedido=True)
    assert novo.herdar_os_escondidos() == [NO]
    assert novo.entregar_ao_linux() == [NO]
    assert NO not in disco.fechados and not novo.herdados
    assert _pede(novo, 9, {"cmd": "open", "node": NO})["state"] == "exposed"
    assert novo.entregar_ao_linux() == []
    assert disco.aberturas == [NO]


def test_o_herdado_que_o_daemon_adota_nao_volta_na_graca(tmp_path: Path) -> None:
    disco = _Disco(aberto=False)
    novo = _estado(tmp_path, disco, no_nasce_fechado=False, pedido=True)
    novo.herdar_os_escondidos()
    _pede(novo, 3, {"cmd": "hide", "node": NO})
    assert novo.herdados == set()
    assert novo.entregar_ao_linux() == []
    assert disco.aberturas == []


@pytest.mark.parametrize("modo", sorted(MODOS))
def test_a_parada_de_verdade_abre_nos_dois_modos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modo: str
) -> None:
    disco = _Disco(aberto=False)
    _cinto(monkeypatch, disco, no_nasce_fechado=MODOS[modo])
    assert disco.aberturas == []
    monkeypatch.setattr(hb, "reinicio_sem_abrir_pedido", lambda *a, **k: False)
    assert hb.main(["--restore-all-and-exit"]) == 0
    assert disco.aberturas == [NO]
