"""MESA-CHEIA-09 — "aplicado" sem byte nenhum.

O ponto único de silêncio era `apply_output_for`
(`core/backend_pydualsense.py`): quatro caminhos (spec vazio, sem MAC estável,
controle desconectado, escrita de verdade) e `return` seco nos quatro. Quem
chamou não tinha como saber se algum byte saiu — e daí descem as mentiras de
"aplicado" da janela.

Este arquivo prova as três entregas:

* **E1** — `apply_output_for` devolve o que fez (`ResultadoDeSaida`);
* **E2** — `trigger.set`/`trigger.reset` devolvem `aplicado_em`/`guardado_em`,
  espelho do `led.set` do mesmo arquivo;
* **E3** — os toasts da Lightbar e dos Gatilhos dizem a verdade, no
  vocabulário da **D-9** (*guardado*), que mora num lugar só
  (`app/textos_de_aplicacao.py`).

**O que este teste NÃO prova:** que o byte chegou ao aparelho. Ele prova que a
janela DIZ o que o daemon SABE — a distância entre o que o daemon sabe e o que
o aparelho recebeu é medida por ensaio (`docs/data/ensaios.csv`).

A mesa é a de 14/08: os MACs saem do payload real de quatro controles em
`tests/fixtures/state_full_quatro_controles.json`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import ControllerState, OutputSpec
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)
UNIQS: list[str] = [
    c["uniq"] for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["controllers"]
]
NA_MESA = UNIQS[0]
FORA_DA_MESA = UNIQS[1]


def _key_de(uniq: str) -> str:
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2)).upper()


class _FakeTrigger:
    """O par `triggerL`/`triggerR` do handle real.

    CONSERTO 1.3: o dublê não os tinha, e `_apply_trigger` levantava
    `AttributeError` a cada escrita de gatilho — que o `except` de
    `_write_partial_output` engolia. Com o retorno honesto do defeito B, o
    dublê mudo passou a REPROVAR os testes de gatilho desta mesma sprint: eles
    afirmavam "escreveu" sobre uma escrita que só o log sabia ter falhado.
    """

    def __init__(self) -> None:
        self.mode = 0
        self.forces = [0] * 7

    def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
        self.forces[idx] = value


class _FakeHandle:
    def __init__(self) -> None:
        self.connected = True
        self.conType = type("CT", (), {"name": "USB"})()
        self.light = type("L", (), {"setColorI": lambda self, r, g, b: None})()
        self.triggerL = _FakeTrigger()
        self.triggerR = _FakeTrigger()

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        return

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        return


class _FakeNodeSysfs:
    """O nó `sysfs` do kernel, só com o que a rota de LED usa.

    CONSERTO 1.3: existe para medir a PROMESSA de "registrado" no Modo Nativo
    — que o desmute re-escreve o que ficou guardado. É a única rota que
    restaura a cor ao sair do Modo Nativo, e sem um nó o teste mediria o
    caminho errado (o `handle.light`, que só mexe em estado interno).
    """

    def __init__(self) -> None:
        self.cores: list[tuple[int, int, int]] = []
        self.desenhos: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.desenhos.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        return


def _null_evdev() -> EvdevReader:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


def _backend_com_um_conectado() -> PyDualSenseController:
    """A mesa da mordida: UM handle aberto, e um segundo MAC que saiu da mesa."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    inst._handles = {_key_de(NA_MESA): _FakeHandle()}  # type: ignore[dict-item]
    inst._primary_key = _key_de(NA_MESA)
    return inst


@pytest.fixture
def servidor(tmp_path: Path) -> tuple[IpcServer, PyDualSenseController]:
    backend = _backend_com_um_conectado()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    server = IpcServer(
        controller=backend,
        store=store,
        profile_manager=ProfileManager(controller=backend, store=store),
        socket_path=tmp_path / "mesa_cheia_09.sock",
        daemon=None,
    )
    return server, backend


class TestE1ApplyOutputForDeixaDeSerSilenciosa:
    """MORDIDA 1 — o retorno que não distingue."""

    def test_conectado_escreveu_e_ausente_ficou_registrado(self) -> None:
        backend = _backend_com_um_conectado()
        assert backend.apply_output_for(NA_MESA, OutputSpec(led=(9, 8, 7))) == "escreveu"
        assert (
            backend.apply_output_for(FORA_DA_MESA, OutputSpec(led=(9, 8, 7)))
            == "registrado"
        ), "um retorno constante não distingue o caso em que a tela mente"

    def test_registrado_quer_dizer_guardado_de_verdade(self) -> None:
        """A palavra só vale se o override ficar mesmo no mapa do hotplug."""
        backend = _backend_com_um_conectado()
        backend.apply_output_for(FORA_DA_MESA, OutputSpec(led=(1, 2, 3)))
        assert backend._desired_by_uniq[FORA_DA_MESA].led == (1, 2, 3)

    def test_sem_mac_estavel_nao_guardou_nada(self) -> None:
        backend = _backend_com_um_conectado()
        assert backend.apply_output_for("/dev/hidraw9", OutputSpec(led=(1, 2, 3))) == (
            "sem_alvo"
        )
        assert "/dev/hidraw9" not in backend._desired_by_uniq

    def test_spec_vazio_nao_e_sem_alvo(self) -> None:
        """Duas coisas diferentes não podem ter a mesma palavra."""
        backend = _backend_com_um_conectado()
        assert backend.apply_output_for(NA_MESA, OutputSpec()) == "nada_a_fazer"

    def test_a_base_do_icontroller_tambem_separa_spec_vazio(self) -> None:
        """CONSERTO 1.3/C — a base juntava o que o vocabulário separa.

        `IController.apply_output_for` devolvia "sem_alvo" até para spec vazio,
        enquanto a subclasse devolvia "nada_a_fazer": o mesmo pedido, duas
        palavras, dependendo do backend.
        """
        from hefesto_dualsense4unix.testing import FakeController

        fc = FakeController(transport="usb")
        assert fc.apply_output_for(NA_MESA, OutputSpec()) == "nada_a_fazer"
        assert fc.apply_output_for(NA_MESA, OutputSpec(led=(1, 2, 3))) == "sem_alvo"

    def test_o_vocabulario_e_nome_publico_do_modulo(self) -> None:
        """CONSERTO 1.3/C — era o único nome público fora do `__all__`."""
        from hefesto_dualsense4unix.core import controller as mod

        assert "ResultadoDeSaida" in mod.__all__


class TestConserto13OQueDizEscreveuSemByteNenhum:
    """MORDIDA NOVA — os dois estados em que "escreveu" mentia.

    O Modo Nativo é a TERCEIRA condição da tabela de mentiras da sprint
    (`docs/process/sprints/2026-08-13-MESA-CHEIA-09-aplicado-sem-byte-nenhum.md`,
    §1). A primeira leva matou as duas primeiras e deu afirmação POSITIVA a
    esta: `apply_output_for` lia `muted` e não o usava no retorno.
    """

    def test_modo_nativo_nao_pode_dizer_que_escreveu(self) -> None:
        """Mutado: sysfs desabilitado, `0x31` pulado, report_thread calado.

        A palavra é "registrado" porque o caso é semanticamente IDÊNTICO ao do
        controle fora da mesa — o desejado fica guardado e o `set_output_mute`
        o re-escreve ao desmutar; o que muda é só o evento que o libera.
        """
        backend = _backend_com_um_conectado()
        backend.set_output_mute(True)
        assert backend.apply_output_for(NA_MESA, OutputSpec(led=(9, 8, 7))) == (
            "registrado"
        ), "em Modo Nativo o dono do hidraw é o jogo: nenhum byte nosso sai"

    def test_modo_nativo_guarda_de_verdade_o_que_promete(self) -> None:
        """"Registrado" é promessa: o desejado tem de estar no mapa."""
        backend = _backend_com_um_conectado()
        backend.set_output_mute(True)
        backend.apply_output_for(NA_MESA, OutputSpec(led=(9, 8, 7)))
        assert backend._desired_by_uniq[NA_MESA].led == (9, 8, 7)

    def test_o_desmute_paga_a_promessa_do_guardado(self) -> None:
        """A prova que ESCOLHE a palavra, e que faltava.

        "Registrado" não diz só "ficou no mapa" — diz **vale quando o evento
        que o segura passar**. Para o controle fora da mesa, quem paga é o
        hotplug, e há teste. Para o Modo Nativo, quem paga é o desmute, e a
        entrega escolheu a palavra sobre uma afirmação que nenhum teste
        cobria: sem esta mordida, trocar `set_output_mute` para NÃO re-aplicar
        deixaria a suíte inteira verde com a janela prometendo o que o backend
        não cumpre — e "guardado" viraria a quinta mentira, pior que
        "aplicado", porque manda ela esperar.

        A rota medida é a do `sysfs`, que é a ÚNICA que restaura a cor ao sair
        do Modo Nativo (o `report_thread` não pinta LED de controle coberto
        por nó — `_suppress_leds`).
        """
        backend = _backend_com_um_conectado()
        node = _FakeNodeSysfs()
        backend._sysfs = {_key_de(NA_MESA): node}  # type: ignore[dict-item]

        backend.set_output_mute(True)
        assert backend.apply_output_for(NA_MESA, OutputSpec(led=(9, 8, 7))) == (
            "registrado"
        )
        assert node.cores == [], (
            "mutado, a rota sysfs está desabilitada por `not muted` — se algo "
            "escrevesse aqui, o dono do hidraw não seria o jogo"
        )

        backend.set_output_mute(False)
        assert node.cores == [(9, 8, 7)], (
            "o desmute tem de RE-ESCREVER o que ficou guardado; sem isso a "
            "palavra certa não seria 'registrado'"
        )

    def test_o_desmute_rearma_o_report_para_gatilho_e_mic(self) -> None:
        """A outra metade da promessa: o que não passa pelo `sysfs`.

        Gatilho e LED do mic só saem pelo `report_thread`, que deduplica pelo
        último report enviado (`_last_out_report`). Guardado em Modo Nativo, o
        estado interno já é o desejado — e sem limpar o cache o report novo
        seria idêntico ao último e NÃO sairia: o guardado nunca chegaria ao
        aparelho, mesmo com o Modo Nativo já desligado.
        """
        backend = _backend_com_um_conectado()
        handle = next(iter(backend._handles.values()))
        backend.set_output_mute(True)
        backend.apply_output_for(
            NA_MESA, OutputSpec(trigger_right=build_from_name("Rigid", [5, 200]))
        )
        handle._last_out_report = b"o report de antes do Modo Nativo"  # type: ignore[attr-defined]

        backend.set_output_mute(False)
        assert handle._last_out_report is None, (  # type: ignore[attr-defined]
            "sem rearmar a deduplicação, o gatilho guardado morre no cache"
        )

    def test_desmutado_volta_a_escrever_de_verdade(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        backend = _backend_com_um_conectado()
        backend.set_output_mute(True)
        backend.set_output_mute(False)
        assert backend.apply_output_for(NA_MESA, OutputSpec(led=(9, 8, 7))) == (
            "escreveu"
        )

    def test_escrita_que_levanta_nao_pode_dizer_que_escreveu(self) -> None:
        """DEFEITO B — `_write_partial_output` engole a exceção e loga.

        O `hidraw` que some debaixo da escrita levantava `OSError`, o `except`
        registrava `reapply_perfil_no_hotplug_falhou` e o caminho seguia para
        "escreveu": a janela dizia "aplicado" por causa da MESMA falha que o
        log denunciava.
        """
        backend = _backend_com_um_conectado()
        handle = next(iter(backend._handles.values()))

        def _hidraw_sumiu(_r: int, _g: int, _b: int) -> None:
            raise OSError("read error")

        handle.light.setColorI = _hidraw_sumiu  # type: ignore[method-assign]
        assert backend.apply_output_for(NA_MESA, OutputSpec(led=(9, 8, 7))) == (
            "falhou"
        )

    @pytest.mark.asyncio
    async def test_o_daemon_diz_guardado_em_modo_nativo(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        """O outro lado do fio: `_destinos_por_uniq` já dava o destino certo."""
        server, backend = servidor
        backend.set_output_mute(True)
        resposta = await server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [5, 200], "uniq": NA_MESA}
        )
        assert resposta["aplicado_em"] == [], (
            "com o output mutado nenhum byte sai, e a aba Gatilhos repetia "
            "esta lista como 'Rigido aplicado'"
        )
        assert resposta["guardado_em"] == [NA_MESA]

    @pytest.mark.asyncio
    async def test_escrita_que_falha_nao_vira_guardado_no_daemon(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        """"Falhou" não é "guardado": não há promessa a fazer à usuária."""
        server, backend = servidor
        handle = next(iter(backend._handles.values()))

        def _hidraw_sumiu(_r: int, _g: int, _b: int) -> None:
            raise OSError("read error")

        handle.light.setColorI = _hidraw_sumiu
        resposta = await server._handle_led_set({"rgb": [255, 0, 0], "uniq": NA_MESA})
        assert resposta["aplicado_em"] == []
        assert resposta["guardado_em"] == []


class TestE2OTriggerDizOndePegou:
    """MORDIDA 2 — o `aplicado_em` que mente por construção."""

    @pytest.mark.asyncio
    async def test_trigger_set_no_conectado_diz_aplicado(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        server, _backend = servidor
        resposta = await server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [5, 200], "uniq": NA_MESA}
        )
        assert resposta["aplicado_em"] == [NA_MESA]
        assert resposta["guardado_em"] == []

    @pytest.mark.asyncio
    async def test_trigger_set_no_ausente_nao_diz_aplicado(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        server, _backend = servidor
        resposta = await server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [5, 200], "uniq": FORA_DA_MESA}
        )
        assert resposta["aplicado_em"] == [], (
            "copiar o nome do campo sem a semântica é o pior dos dois mundos: "
            "o cliente passa a confiar num campo falso"
        )
        assert resposta["guardado_em"] == [FORA_DA_MESA]

    @pytest.mark.asyncio
    async def test_trigger_reset_no_ausente_tambem_e_guardado(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        server, _backend = servidor
        resposta = await server._handle_trigger_reset(
            {"side": "both", "uniq": FORA_DA_MESA}
        )
        assert resposta["aplicado_em"] == []
        assert resposta["guardado_em"] == [FORA_DA_MESA]

    @pytest.mark.asyncio
    async def test_sem_uniq_diz_em_quem_a_escrita_global_pegou(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        """Rota clássica (CONSERTO 1.4): dizia "[]" mesmo tendo escrito.

        Era o "não sei em quem" — e o `led.set` irmão, no mesmo arquivo e sem
        `uniq`, já respondia a mesa inteira. Duas rotas irmãs, respostas
        opostas, e a tela lê as duas ("Todos" no seletor manda sem `uniq`).
        O que a rota clássica continua NÃO fazendo está em
        `test_conserto_1_4_a_rota_classica_diz_onde_pegou.py`.
        """
        server, _backend = servidor
        resposta = await server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [5, 200]}
        )
        assert resposta["aplicado_em"] == [NA_MESA]
        assert resposta["guardado_em"] == []

    @pytest.mark.asyncio
    async def test_led_set_no_ausente_para_de_dizer_aplicado(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        """O `led.set` tinha o campo e ele mentia no ramo por-MAC."""
        server, _backend = servidor
        resposta = await server._handle_led_set(
            {"rgb": [255, 0, 0], "uniq": FORA_DA_MESA}
        )
        assert resposta["aplicado_em"] == []
        assert resposta["guardado_em"] == [FORA_DA_MESA]

    @pytest.mark.asyncio
    async def test_led_player_set_no_ausente_tambem(
        self, servidor: tuple[IpcServer, Any]
    ) -> None:
        server, _backend = servidor
        resposta = await server._handle_led_player_set(
            {"bits": [True, False, False, False, False], "uniq": FORA_DA_MESA}
        )
        assert resposta["aplicado_em"] == []
        assert resposta["guardado_em"] == [FORA_DA_MESA]

    @pytest.mark.asyncio
    async def test_backend_que_nao_sabe_dizer_mantem_a_resposta_historica(
        self, tmp_path: Path
    ) -> None:
        """Dublê que devolve None não vira "guardado" — vira o de sempre."""
        from hefesto_dualsense4unix.testing import FakeController

        class _MudoMasAplicador(FakeController):
            def apply_output_for(self, uniq: str, spec: OutputSpec) -> Any:
                return None

        fc = _MudoMasAplicador(transport="usb")
        fc.connect()
        store = StateStore()
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=ProfileManager(controller=fc, store=store),
            socket_path=tmp_path / "mudo.sock",
            daemon=None,
        )
        resposta = await server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [5, 200], "uniq": NA_MESA}
        )
        assert resposta["aplicado_em"] == [NA_MESA]
        assert resposta["guardado_em"] == []


class TestOEfeitoRealmenteSai:
    """Hipótese tem de explicar o que JÁ funcionava: o gatilho ainda escreve."""

    def test_o_efeito_fica_registrado_no_desejado_do_controle(self) -> None:
        backend = _backend_com_um_conectado()
        efeito = build_from_name("Rigid", [5, 200])
        assert (
            backend.apply_output_for(NA_MESA, OutputSpec(trigger_left=efeito))
            == "escreveu"
        )
        assert backend._desired_by_uniq[NA_MESA].trigger_left == efeito
