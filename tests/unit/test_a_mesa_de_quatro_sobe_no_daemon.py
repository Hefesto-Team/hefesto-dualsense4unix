"""A cena dela, medida no daemon: 3 no rádio + 1 no cabo, cada um com o SEU som.

A CENA, com as palavras dela (10/09/2026)
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
   entradas de nome igual na lista de som dela é o defeito de 07/09;
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

#: MACs FORJADOS, da faixa sintética que o portão de fixtures permite. Nem
#: mascarado se usa o OUI real da bancada dela — a régua pega por FORMA.
_MESA = (
    ("aa:bb:cc:00:00:a1", "radio"),
    ("aa:bb:cc:00:00:a2", "radio"),
    ("aa:bb:cc:00:00:a3", "radio"),
    ("aa:bb:cc:00:00:a4", "cabo"),
)

_BUS_BT = 0x05
_BUS_USB = 0x03
_VENDOR = 0x054C
_PRODUTO = 0x0CE6


def _forjar_sysfs(raiz: Path) -> Path:
    """Uma árvore `/sys/class/hidraw` com os quatro. Nada aqui existe no disco dela."""
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
    # O CABO tem placa: cada `uniq` resolve para o SEU sink USB. Sem isto o do
    # cabo não teria rota e a guarda «sem rota, sem nó» o deixaria de fora —
    # medindo três, não quatro.
    monkeypatch.setattr(
        af, "sink_do_controle", lambda uniq, *a, **k: f"alsa_output.usb-{uniq[-2:]}"
    )
    # O RÁDIO não toca no aparelho: a fonte de PCM é muda e o hidraw é um fd
    # inventado. O que se mede aqui é a FIAÇÃO, não o protocolo — o protocolo
    # tem régua própria em `test_o_produto_monta_o_report_que_tocou.py`.
    # A fonte devolve SILÊNCIO DO TAMANHO PEDIDO, e não `b""`: uma fonte vazia
    # é «a fonte secou» para a bomba, e o laço morre no primeiro quadro. A
    # ponte subia e caía antes de o nó nascer — e a rota do rádio saía
    # «recusada» com a ponte de pé no log, uma linha acima.
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
            # UM FD DE VERDADE, PARA `/dev/null`. A ponte precisa de um
            # descritor para montar a bomba, e um `None` aqui a faria recusar
            # com "não consegui abrir o hidraw" — a régua mediria o dublê, não
            # o produto. Escrever em `/dev/null` é inofensivo, e o `seco`
            # abaixo garante que nem isso acontece.
            self.fd = os.open(os.devnull, os.O_WRONLY)
            fds.append(self.fd)

    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **k: _No(no))
    # A ponte responde «de pé» sem mandar byte nenhum: é o `seco`, que existe
    # no produto exatamente para este uso.
    verdadeira = af.PonteDeSomPorRadio

    def _ponte_seca(**kw: Any) -> Any:
        kw["seco"] = True
        return verdadeira(**kw)

    monkeypatch.setattr(af, "PonteDeSomPorRadio", _ponte_seca)
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
    # Uma varredura do som já rodou no `start()`; o laço reconcilia sozinho.
    for _ in range(200):
        sub = getattr(daemon, "_alto_falante_subsystem", None)
        ger = getattr(sub, "_gerenciador", None) if sub is not None else None
        if ger is not None and ger.nos:
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
    """Item 5, e é a invariante 4 de `app/audio_saida.py` com quatro na mesa.

    A conta de 07/09 era `sinks <= loopbacks`, e ela média o mundo do CABO: no
    rádio a rota **não é** um `module-loopback` — é a ponte lendo o monitor do
    nó e escrevendo o report `0x35` no controle. Contar só loopback aqui
    reprovaria a cena que a casa passou meses tentando entregar.
    """
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
    """A terceira ponta da receita: quem sobe subsystem e não o para, vaza.

    No caso do som o preço é visível para ela: o nó fica na lista de saída
    depois de o daemon morrer, e cada ponte segura um fd e um `pw-record`.
    """
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
    """A GUARDA *sem rota, sem nó*, com a máquina que não tem `pw-record`.

    É o caso real de quem instala o produto numa máquina sem PipeWire-utils:
    `fonte_do_monitor_do_no` recusa com a frase honesta, a ponte não sobe, e o
    rádio fica sem rota. **O que não pode acontecer é o nó ir para a lista de
    som dela assim mesmo** — três entradas mudas com nome de controle, e ela
    escolhe uma e o som some.

    O do CABO continua ganhando nó: a rota dele não depende de ponte nenhuma.
    Uma guarda que derrubasse os quatro seria pior que o defeito.

    MORDIDA: troque a guarda de `GerenciadorDeNosDeSom.reconciliar` por `if
    False:` e este teste conta quatro nós, três deles sumidouros.
    """
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
