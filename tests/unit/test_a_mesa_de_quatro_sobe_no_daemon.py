"""A cena dela, medida no daemon: 3 no rádio + 1 no cabo, cada um com o SEU som.

A CENA, com as palavras (10/09/2026)
------------------------------------------
    *"imagina que estejam jogando um fps com 4 players local (3 por bt … + um
    no cabo) … o canal de som sfx (a cada tiro dado o som do tiro efeito
    sonoro sai pra cada controle), e cada controle com seu microfone
    individual funcionando."*

Esta régua mede a metade de SAÍDA dessa cena no produto: sobe um `Daemon` de
verdade com quatro DualSense no sysfs, e olha o que chegou ao `pactl` e às
pontes de rádio. Não é bancada — nenhum byte vai a aparelho nenhum — mas é o
degrau que faltava depois de `MONTOU`: **existe linha de produção que constrói
uma ponte por controle.**

O QUE ELA TRAVA, e cada item já foi um defeito nesta casa
----------------------------------------------------------
1. **os QUATRO ganham nó** — não o primário, não "o que estiver no cabo";
2. **cada nó tem nome próprio** (`hefesto_som_<hex6>` do `uniq`): quatro
   entradas de nome igual na lista de som do usuário é o defeito de 07/09;
3. **os três do rádio ganham UMA ponte CADA**, com o hidraw daquele controle —
   uma ponte compartilhada manda o som do P2 no alto-falante do P1;
4. **o do cabo NÃO ganha ponte de rádio**, e ainda assim tem rota;
5. **nenhum nó nasce sumidouro**: todo `module-null-sink` publicado tem
   loopback (cabo) ou ponte (rádio) ao lado.

A MORDIDA
----------
Tire `self._casar_as_pontes(alvos)` de `AltoFalanteSubsystem._reconciliar` e o
item 3 reprova. Tire a guarda *sem rota, sem nó* de
`GerenciadorDeNosDeSom.reconciliar` e faça a ponte falhar: o item 5 reprova.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController

_MESA = (
    ("aa:bb:cc:00:00:a1", "radio"),
    ("aa:bb:cc:00:00:a2", "radio"),
    ("aa:bb:cc:00:00:a3", "radio"),
    ("aa:bb:cc:00:00:a4", "cabo"),
)
from tests.unit.o_alto_falante_que_toca import todo_alto_falante_toca

_BUS_BT = 0x05
_BUS_USB = 0x03
_VENDOR = 0x054C
_PRODUTO = 0x0CE6


def _forjar_sysfs(raiz: Path) -> Path:
    """Uma árvore `/sys/class/hidraw` com os quatro. Nada aqui existe no disco do usuário."""
    classe = raiz / "hidraw"
    classe.mkdir(parents=True)
    for n, (uniq, transporte) in enumerate(_MESA):
        no = classe / f"hidraw{n}"
        (no / "device").mkdir(parents=True)
        bus = _BUS_BT if transporte == "radio" else _BUS_USB
        (no / "device" / "uevent").write_text(
            f"HID_ID={bus:04X}:{_VENDOR:08X}:{_PRODUTO:08X}\n"
            f"HID_NAME=Wireless Controller\n"
            f"HID_PHYS=00:00:00:00:00:00\n"
            f"HID_UNIQ={uniq}\n",
            encoding="utf-8",
        )
    return classe


def _state() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config() -> DaemonConfig:
    return DaemonConfig(  # type: ignore[arg-type]
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Os quatro no sysfs, o `pactl` gravado e o rádio sem tocar em aparelho."""
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as entrada
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    monkeypatch.setattr(entrada, "_SYSFS_HIDRAW", str(_forjar_sysfs(tmp_path)))
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )

    mandados: list[list[str]] = []

    def _recorder(argv: list[str]) -> str | None:
        mandados.append(list(argv))
        return "77\n"

    monkeypatch.setattr(af, "_rodar", _recorder)
    monkeypatch.setattr(
        af, "sink_do_controle", lambda uniq, *a, **k: f"alsa_output.usb-{uniq[-2:]}"
    )
    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no",
        lambda id_do_no, **k: (
            (lambda n: b"\x00" * n), f"gravador:{id_do_no}", ""
        ),
    )

    abertos: list[str] = []
    fds: list[int] = []

    class _No:
        def __init__(self, caminho: str) -> None:
            abertos.append(caminho)
            self.fd = os.open(os.devnull, os.O_WRONLY)
            fds.append(self.fd)

    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **k: _No(no))
    verdadeira = af.PonteDeSomPorRadio

    def _ponte_seca(**kw: Any) -> Any:
        kw["seco"] = True
        return verdadeira(**kw)

    monkeypatch.setattr(af, "PonteDeSomPorRadio", _ponte_seca)
    todo_alto_falante_toca(monkeypatch)
    try:
        yield {"mandados": mandados, "abertos": abertos}
    finally:
        for fd in fds:
            with contextlib.suppress(OSError):
                os.close(fd)


async def _subir_o_daemon(mesa: dict[str, Any]) -> tuple[Any, list[str]]:
    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_state()]),
        bus=EventBus(), store=store, config=_config(),
    )
    run_task = asyncio.create_task(daemon.run())
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    for _ in range(200):
        sub = getattr(daemon, "_alto_falante_subsystem", None)
        ger = getattr(sub, "_gerenciador", None) if sub is not None else None
        if ger is not None and len(ger.nos) >= len(_MESA):
            break
        await asyncio.sleep(0.01)
    return daemon, run_task  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_os_quatro_ganham_no_com_nome_proprio(mesa: dict[str, Any]) -> None:
    """Item 1 e 2: quatro nós, quatro nomes — nenhum deles genérico."""
    from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

    daemon, run_task = await _subir_o_daemon(mesa)
    try:
        sub = daemon._alto_falante_subsystem
        assert sub is not None, (
            "o `AltoFalanteSubsystem` não subiu no daemon — SOM-FIADO-01 pede "
            "as TRÊS pontas: o registry, o `_safe_start` e o `_stop_*`"
        )
        nos = sub._gerenciador.nos
        assert sorted(nos) == sorted(u for u, _ in _MESA), (
            f"os quatro DualSense não viraram quatro nós: {sorted(nos)}"
        )
        nomes = {no.nome for no in nos.values()}
        assert len(nomes) == 4, f"dois controles dividem o mesmo nó: {nomes}"
        assert nomes == {nome_do_sink(u) for u, _ in _MESA}
    finally:
        daemon.stop()
        await run_task


@pytest.mark.asyncio
async def test_cada_um_do_radio_tem_a_sua_ponte(mesa: dict[str, Any]) -> None:
    """Item 3 e 4 — e é este que a fiação de SOM-FIADO-01 acende."""
    daemon, run_task = await _subir_o_daemon(mesa)
    try:
        pontes = daemon._alto_falante_subsystem._pontes
        assert sorted(pontes) == [u for u, t in _MESA if t == "radio"], (
            f"as pontes não casam com quem está no rádio: {sorted(pontes)}"
        )
        assert len(set(id(p) for p in pontes.values())) == 3, (
            "os três do rádio dividem a MESMA ponte — o som do P2 sairia no "
            "alto-falante do P1"
        )
        assert all(p.uniq == u for u, p in pontes.items()), (
            "uma ponte está registrada sob o `uniq` de outro controle"
        )
        for n, (uniq, transporte) in enumerate(_MESA):
            if transporte == "radio":
                assert f"/dev/hidraw{n}" in mesa["abertos"], (
                    f"a ponte de {uniq} não pediu o hidraw dele"
                )
    finally:
        daemon.stop()
        await run_task


@pytest.mark.asyncio
async def test_nenhum_no_da_mesa_nasce_sumidouro(mesa: dict[str, Any]) -> None:
    """Item 5, e é a invariante 4 de `app/audio_saida.py` com quatro na mesa."""
    daemon, run_task = await _subir_o_daemon(mesa)
    try:
        carregados = [
            " ".join(a) for a in mesa["mandados"] if "load-module" in " ".join(a)
        ]
        sinks = [linha for linha in carregados if "module-null-sink" in linha]
        loopbacks = [linha for linha in carregados if "module-loopback" in linha]
        pontes = daemon._alto_falante_subsystem._pontes

        assert len(sinks) == 4, f"esperava quatro nós publicados: {sinks}"
        assert len(sinks) <= len(loopbacks) + len(pontes), (
            "algum `module-null-sink` foi publicado sem rota NENHUMA — nem "
            "loopback no cabo, nem ponte no rádio. É o sink que aceita o áudio "
            f"e o joga fora. sinks={len(sinks)} loopbacks={len(loopbacks)} "
            f"pontes={len(pontes)}"
        )
        for uniq, transporte in _MESA:
            if transporte == "cabo":
                assert any(f"usb-{uniq[-2:]}" in linha for linha in loopbacks), (
                    f"o do cabo ({uniq}) não teve o loopback para a placa dele"
                )
    finally:
        daemon.stop()
        await run_task


@pytest.mark.asyncio
async def test_o_shutdown_leva_no_e_ponte_junto(mesa: dict[str, Any]) -> None:
    """A terceira ponta da receita: quem sobe subsystem e não o para, vaza."""
    daemon, run_task = await _subir_o_daemon(mesa)
    sub = daemon._alto_falante_subsystem
    pontes = list(sub._pontes.values())
    assert pontes, "sem ponte não há o que medir neste teste"

    daemon.stop()
    await run_task

    assert getattr(daemon, "_alto_falante_subsystem", None) is None, (
        "o `shutdown()` não chamou `_stop_alto_falante` — ver `connection.py`"
    )
    assert sub._pontes == {}, "sobraram pontes depois do shutdown"
    assert not any(p.esta_de_pe() for p in pontes), "alguma ponte ficou de pé"
    descarregados = [
        " ".join(a) for a in mesa["mandados"] if "unload-module" in " ".join(a)
    ]
    assert descarregados, "nenhum módulo foi descarregado — os nós ficaram nela"


@pytest.mark.asyncio
async def test_quem_nao_tem_ponte_nao_ganha_no_mudo(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A GUARDA *sem rota, sem nó*, com a máquina que não tem `pw-record`."""
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no",
        lambda id_do_no, **k: (None, None, "nem `pw-record` nem `parec` nesta máquina"),
    )

    daemon, run_task = await _subir_o_daemon(mesa)
    try:
        sub = daemon._alto_falante_subsystem
        assert sub._pontes == {}, (
            "subiu ponte sem fonte de PCM — ela entregaria silêncio para sempre"
        )
        nos = sub._gerenciador.nos
        assert sorted(nos) == ["aa:bb:cc:00:00:a4"], (
            "os do RÁDIO viraram nó sem rota nenhuma: cada um é um "
            f"`module-null-sink` que aceita o áudio e o joga fora. nós={sorted(nos)}"
        )
    finally:
        daemon.stop()
        await run_task


@pytest.mark.asyncio
async def test_o_mix_de_um_nao_vira_o_mix_do_vizinho(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """SFX-POR-CONTROLE-01 no DAEMON: a fonte é de cada um."""
    import json

    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    p1 = _MESA[0][0]
    nome = "mesa-de-quatro"
    pasta = Path(profiles_dir(ensure=True))
    (pasta / f"{nome}.json").write_text(
        json.dumps(
            {
                "name": nome,
                "match": {"type": "any"},
                "controllers": {
                    "".join(c for c in p1.lower() if c in "0123456789abcdef")[:12]: {
                        "speaker": {"volume": 180, "fonte": "mix"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile", lambda: nome
    )
    monkeypatch.setattr(
        af, "monitor_da_saida_padrao", lambda **k: "alsa_output.hdmi.monitor"
    )

    daemon, run_task = await _subir_o_daemon(mesa)
    try:
        nos = daemon._alto_falante_subsystem._gerenciador.nos
        fontes = {u: no.rota.fonte for u, no in nos.items()}
        assert fontes[p1] == "mix", (
            f"o P1 pediu o mix inteiro e o nó dele nasceu com {fontes[p1]!r}"
        )
        for uniq, _ in _MESA[1:]:
            assert fontes[uniq] == af.FONTE_PADRAO, (
                f"o {uniq} herdou a fonte do P1 ({fontes[uniq]!r}) — a escolha "
                "de um jogador mudou o som do vizinho"
            )
        assert nos[p1].rota.monitor_do_mix, (
            "o nó do P1 está em `mix` e não sabe de qual monitor puxar"
        )
        for uniq, _ in _MESA[1:]:
            assert not nos[uniq].rota.monitor_do_mix, (
                f"o {uniq} ficou com o monitor do sistema sem ter pedido"
            )
    finally:
        daemon.stop()
        await run_task
