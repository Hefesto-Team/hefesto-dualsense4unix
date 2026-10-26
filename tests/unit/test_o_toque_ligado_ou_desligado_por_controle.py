"""O toque é Ligado ou Desligado em cada controle, e o Desligado cala o touchpad no jogo."""
from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.virtual_motion import (
    CONTATOS_DO_TOQUE,
    FAIXA_GIROSCOPIO,
    REGISTRO,
    TAMANHO_DA_JANELA,
    TOQUE_INATIVO,
    chave_de_sensor,
)
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    ControllerSensoresOverride,
    MatchAny,
    Profile,
)

_PECAS = [
    ("aa:bb:cc:00:00:01", "usb"),
    ("aa:bb:cc:00:00:02", "bt"),
    ("aa:bb:cc:00:00:03", "usb"),
    ("aa:bb:cc:00:00:04", "bt"),
]
_P1, _P2 = _PECAS[0][0], _PECAS[1][0]
_JANELA = bytes(range(1, TAMANHO_DA_JANELA + 1))


@pytest.fixture(autouse=True)
def _registro_limpo() -> Any:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Cena:
    """O que o hub pergunta ao daemon: há jogo aberto, e o jogo tem toque próprio?"""

    def __init__(self) -> None:
        self.jogo = False
        self.com_toque_proprio: set[str] = set()


class _LeitorDoToque:
    def __init__(self) -> None:
        self.grab_state = "off"
        self.grabs: list[bool] = []

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.grab_state = "off"

    def touch_state(self) -> Any:
        return SimpleNamespace(touching=False, fingers=())

    def regions_pressed(self) -> frozenset[str]:
        return frozenset()

    def set_grab(self, querido: bool) -> bool:
        self.grabs.append(querido)
        self.grab_state = "held" if querido else "off"
        return True


def _hub(
    cena: _Cena, relogio: _Relogio, transportes: dict[str, str] | None = None
) -> tuple[SensorHub, dict[str, _LeitorDoToque]]:
    leitores = {u: _LeitorDoToque() for u, _ in _PECAS}
    nos = transportes or {u: t for u, t in _PECAS}
    hub = SensorHub(
        motion_factory=lambda uniq, node: SimpleNamespace(
            start=lambda: True, stop=lambda: None
        ),
        touch_factory=lambda uniq, node: leitores[uniq],
        gamepad_factory=lambda uniq, node: SimpleNamespace(
            start=lambda: True, stop=lambda: None
        ),
        descobrir_motion=dict,
        descobrir_touch=lambda: {u: Path(f"/dev/input/event-{nos[u]}-{u}") for u in leitores},
        descobrir_gamepad=dict,
        relogio=relogio,
        auto_manutencao=False,
        ha_jogo=lambda: cena.jogo,
        toque_proprio_do_jogo=lambda uniq: uniq in cena.com_toque_proprio,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    for uniq in leitores:
        hub.leitura(uniq)
    hub.reconciliar()
    return hub, leitores


class TestODesligadoCalaNoJogo:
    @pytest.mark.parametrize(("uniq", "transporte"), _PECAS)
    def test_desligado_com_jogo_agarra_o_no_e_zera_os_pontos(
        self, uniq: str, transporte: str
    ) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        REGISTRO.definir_touchpad(uniq, ligado=False)
        cena.jogo = True
        hub.reconciliar()

        assert leitores[uniq].grab_state == "held", f"o nó ({transporte}) ficou com o sistema"
        saida = REGISTRO.filtrar(uniq, _JANELA)
        for contato in CONTATOS_DO_TOQUE:
            assert saida[contato] & TOQUE_INATIVO, "o vpad ainda recebe o dedo"
        assert saida[FAIXA_GIROSCOPIO] == _JANELA[FAIXA_GIROSCOPIO], "o Desligado mexeu no giro"
        outros = [u for u, _ in _PECAS if u != uniq]
        assert all(leitores[u].grabs == [] for u in outros), "o Desligado vazou para outra peça"
        assert REGISTRO.filtrar(outros[0], _JANELA) is _JANELA

    def test_desligado_sem_jogo_deixa_o_cursor_com_o_sistema(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        REGISTRO.definir_touchpad(_P1, ligado=False)
        hub.reconciliar()
        assert leitores[_P1].grabs == []
        assert REGISTRO.filtrar(_P1, _JANELA) is _JANELA

    def test_o_parametro_mudo_cala_tambem_fora_do_jogo(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        REGISTRO.desligado_fora_do_jogo = "mudo"
        REGISTRO.definir_touchpad(_P1, ligado=False)
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held"
        assert REGISTRO.filtrar(_P1, _JANELA)[CONTATOS_DO_TOQUE[0]] & TOQUE_INATIVO

    def test_o_jogo_que_fecha_devolve_o_no_ao_sistema(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        REGISTRO.definir_touchpad(_P1, ligado=False)
        cena.jogo = True
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held"
        cena.jogo = False
        hub.reconciliar()
        assert leitores[_P1].grab_state == "off"
        assert REGISTRO.filtrar(_P1, _JANELA) is _JANELA

    def test_religar_solta_o_no_com_o_jogo_aberto(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        REGISTRO.definir_touchpad(_P1, ligado=False)
        cena.jogo = True
        hub.reconciliar()
        REGISTRO.definir_touchpad(_P1, ligado=True)
        hub.reconciliar()
        assert leitores[_P1].grab_state == "off"


class TestOLigadoSegueOJogo:
    @pytest.mark.parametrize(("uniq", "transporte"), _PECAS)
    def test_ligado_sem_toque_proprio_nao_agarra(self, uniq: str, transporte: str) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        cena.jogo = True
        hub.reconciliar()
        assert leitores[uniq].grabs == [], f"o nó ({transporte}) foi tomado do sistema"
        assert REGISTRO.filtrar(uniq, _JANELA) is _JANELA

    @pytest.mark.parametrize(("uniq", "transporte"), _PECAS)
    def test_ligado_com_mascara_dualsense_agarra_e_nao_zera(
        self, uniq: str, transporte: str
    ) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        cena.jogo = True
        cena.com_toque_proprio = {uniq}
        hub.reconciliar()
        assert leitores[uniq].grab_state == "held", f"o toque ({transporte}) não foi ao jogo"
        assert REGISTRO.filtrar(uniq, _JANELA) is _JANELA, "o dedo foi zerado antes do jogo"
        outros = [u for u, _ in _PECAS if u != uniq]
        assert all(leitores[u].grabs == [] for u in outros)

    def test_toque_proprio_sem_jogo_aberto_nao_agarra(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        cena.com_toque_proprio = {_P1}
        hub.reconciliar()
        assert leitores[_P1].grabs == []

    def test_a_pergunta_do_jogo_que_quebra_nao_derruba_o_hub(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)

        def _quebra() -> bool:
            raise RuntimeError("daemon fora do ar")

        hub._ha_jogo = _quebra
        REGISTRO.definir_touchpad(_P1, ligado=False)
        hub.reconciliar()
        assert leitores[_P1].grabs == []


class TestAUniaoDasDemandas:
    def test_o_dsu_e_o_desligado_de_outra_peca_nao_se_soltam(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        cena.jogo = True
        REGISTRO.definir_touchpad(_P2, ligado=False)
        hub.segurar_o_dedo(_P1)
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held" and leitores[_P2].grab_state == "held"

        relogio.agora += 6.0
        hub.reconciliar()
        assert leitores[_P1].grab_state == "off", "o DSU vencido segurou o nó"
        assert leitores[_P2].grab_state == "held", "o DSU soltou o grab do Desligado"

        hub.segurar_o_dedo(_P1)
        REGISTRO.definir_touchpad(_P2, ligado=True)
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held", "religar o P2 soltou o DSU do P1"
        assert leitores[_P2].grab_state == "off"

    def test_na_mesma_peca_cada_demanda_segura_ate_a_ultima(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        cena.jogo = True
        REGISTRO.definir_touchpad(_P1, ligado=False)
        hub.toque_da_peca(_P1)
        hub.segurar_o_dedo(_P1)
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held"

        relogio.agora += 6.0
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held", "o Desligado perdeu o nó para a rota que parou"

        cena.jogo = False
        hub.reconciliar()
        assert leitores[_P1].grab_state == "off"

    def test_a_rota_sozinha_continua_a_prender_e_a_soltar(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        hub.toque_da_peca(_P1)
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held"
        relogio.agora += 3.0
        hub.reconciliar()
        assert leitores[_P1].grab_state == "off"

    def test_o_reader_do_desligado_sobrevive_ao_prazo_da_tela(self) -> None:
        """Sem ninguém pedindo, o reader do touchpad morria em 5 s e levava o grab junto."""
        cena, relogio = _Cena(), _Relogio()
        hub, leitores = _hub(cena, relogio)
        cena.jogo = True
        REGISTRO.definir_touchpad(_P1, ligado=False)
        hub.reconciliar()
        relogio.agora += 60.0
        hub.reconciliar()
        assert leitores[_P1].grab_state == "held"
        assert hub.grab_do_toque(_P1) == "held"
        assert hub.grab_do_toque(_P2) == "sem_reader", "o Desligado de uma peça abriu a vizinha"

    def test_o_jogo_chega_ao_report_pelo_registro(self) -> None:
        cena, relogio = _Cena(), _Relogio()
        hub, _ = _hub(cena, relogio)
        assert REGISTRO.jogo_aberto() is False
        cena.jogo = True
        hub.reconciliar()
        assert REGISTRO.jogo_aberto() is True


class TestOHubVigiaSemATela:
    """O Desligado do perfil vale com a interface fechada: ninguém precisa pedir leitura ao hub."""

    def test_o_arranque_do_ipc_poe_o_hub_a_vigiar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.daemon import ipc_server
        from hefesto_dualsense4unix.daemon.subsystems import ipc
        from hefesto_dualsense4unix.profiles import manager

        vigias: list[int] = []

        class _Servidor:
            def __init__(self, **_: Any) -> None:
                pass

            async def start(self) -> None:
                return None

            def _garantir_sensor_hub(self) -> Any:
                return SimpleNamespace(vigiar=lambda: vigias.append(1))

        monkeypatch.setattr(ipc_server, "IpcServer", _Servidor)
        monkeypatch.setattr(manager, "gerente_do_daemon", lambda *_a, **_k: None)
        daemon = SimpleNamespace(controller=None, store=None)
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_FAKE", raising=False)
        asyncio.run(ipc.start_ipc(daemon))  # type: ignore[arg-type]
        assert vigias == [1], "o daemon subiu sem o hub vigiar: o Desligado espera a tela abrir"
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
        asyncio.run(ipc.start_ipc(daemon))  # type: ignore[arg-type]
        assert vigias == [1], "no modo de mentira o hub abriu o /dev/input de verdade"

    def test_vigiar_sobe_a_manutencao_sem_pedido_de_leitura(self) -> None:
        cena = _Cena()
        hub = SensorHub(
            motion_factory=lambda uniq, node: _LeitorDoToque(),
            touch_factory=lambda uniq, node: _LeitorDoToque(),
            gamepad_factory=lambda uniq, node: _LeitorDoToque(),
            descobrir_motion=dict,
            descobrir_touch=dict,
            descobrir_gamepad=dict,
            ha_jogo=lambda: cena.jogo,
        )
        hub._watch = SimpleNamespace(poll=lambda: False)
        try:
            hub.vigiar()
            assert hub._thread is not None and hub._thread.is_alive()
        finally:
            hub.stop_all()

    def test_o_hub_do_ipc_pergunta_ao_daemon_pelo_jogo_e_pela_mascara(self) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _H(IpcHandlersMixin):
            def __init__(self) -> None:
                self.store = SimpleNamespace(window_detect_current_class="steam_app_1")
                self.daemon = SimpleNamespace(
                    display_authority="game",
                    config=SimpleNamespace(gamepad_flavor="dualsense"),
                    is_native_mode=lambda: False,
                )
                self._sensor_hub = None

        h = _H()
        hub = h._garantir_sensor_hub()
        try:
            assert hub._ha_jogo is not None and hub._ha_jogo() is True, "o hub não sabe do jogo"
            perguntar = hub._toque_proprio_do_jogo
            assert perguntar is not None and perguntar(_P1) is True
            h.store.window_detect_current_class = "steam"
            assert perguntar(_P1) is False, "a janela da Steam tomou o cursor do touchpad"
            h.store.window_detect_current_class = "steam_app_1"
            h.daemon.config.gamepad_flavor = "xbox"
            assert perguntar(_P1) is False, "a máscara Xbox recebeu o toque pelo vpad"
            h.daemon.display_authority = "desktop"
            assert hub._ha_jogo() is False
        finally:
            hub.stop_all()


class TestOPerfil:
    def test_o_perfil_velho_sem_o_campo_carrega_ligado(self) -> None:
        secao = ControllerSensoresOverride.model_validate({"giroscopio": False})
        assert secao.touchpad == "ligado"
        assert "touchpad" not in secao.model_fields_set
        assert "touchpad" not in secao.model_dump(exclude_unset=True)

    def test_o_campo_recusa_o_que_nao_e_ligado_ou_desligado(self) -> None:
        with pytest.raises(ValueError):
            ControllerSensoresOverride.model_validate({"touchpad": "cursor"})

    def test_o_perfil_desliga_o_toque_daquela_peca(self) -> None:
        gerente = ProfileManager(controller=object(), store=SimpleNamespace())  # type: ignore[arg-type]
        perfil = Profile(
            name="Quatro",
            match=MatchAny(),
            controllers={
                _P1: ControllerOverrides(
                    sensores=ControllerSensoresOverride(touchpad="desligado")
                ),
                _P2: ControllerOverrides(sensores=ControllerSensoresOverride(giroscopio=False)),
            },
        )
        relato = gerente.apply_controller_sensores(perfil)
        assert REGISTRO.touchpad_ligado(_P1) is False
        assert REGISTRO.touchpad_ligado(_P2) is True
        chave1, chave2 = list(perfil.controllers or {})
        assert "touchpad=off" in relato[f"sensores:{chave1}"]
        assert "touchpad" not in relato[f"sensores:{chave2}"]

    def test_o_perfil_que_so_fala_do_giro_nao_religa_o_toque(self) -> None:
        gerente = ProfileManager(controller=object(), store=SimpleNamespace())  # type: ignore[arg-type]
        REGISTRO.definir_touchpad(_P1, ligado=False)
        perfil = Profile(
            name="So giro",
            match=MatchAny(),
            controllers={
                _P1: ControllerOverrides(sensores=ControllerSensoresOverride(giroscopio=False))
            },
        )
        gerente.apply_controller_sensores(perfil)
        assert REGISTRO.touchpad_ligado(_P1) is False

    def test_a_chave_do_registro_ignora_maiuscula_e_dois_pontos(self) -> None:
        REGISTRO.definir_touchpad(_P1.upper(), ligado=False)
        assert REGISTRO.touchpad_ligado(_P1) is False
        assert chave_de_sensor(_P1) in REGISTRO.touchpad_desligados()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


class _HubDeMentira:
    def __init__(self) -> None:
        self.reconciliou = 0

    def reconciliar(self) -> None:
        self.reconciliou += 1

    def grab_do_movimento(self, uniq: str) -> str:
        return "off"

    def grab_do_toque(self, uniq: str) -> str:
        return "held"


def _handlers(*, nativo: bool = False, steam_input: bool = False) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _H(IpcHandlersMixin):
        def __init__(self) -> None:
            self.store = SimpleNamespace(active_profile="Bancada")
            self.controller = SimpleNamespace(
                describe_controllers=lambda: [{"connected": True, "uniq": _P1}]
            )
            self.daemon = SimpleNamespace(
                is_native_mode=lambda: nativo, _steam_input_excecao=steam_input
            )
            self._sensor_hub = _HubDeMentira()

    return _H()


def _chamar(h: Any, **params: Any) -> dict[str, Any]:
    return asyncio.run(h._handle_sensor_set(params))


class TestOMetodoDoIpc:
    def test_desligar_escreve_o_registro_o_perfil_e_diz_o_alcance(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles import loader as loader_module
        from hefesto_dualsense4unix.profiles.loader import save_profile
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _handlers()

        corpo = _chamar(h, uniq=_P1, touchpad="desligado")

        assert corpo["status"] == "ok" and corpo["gravado"] is True
        assert corpo["touchpad"] == "desligado"
        assert corpo["touchpad_alcance"] == "vpad"
        assert corpo["touchpad_grab"] == "held"
        assert corpo["giroscopio"] is True, "o toque mexeu no giro"
        assert REGISTRO.touchpad_ligado(_P1) is False
        assert h._sensor_hub.reconciliou == 1, "o pedido de grab não chegou ao hub"
        dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[
            chave_de_sensor(_P1)
        ]
        assert dele.sensores is not None and dele.sensores.touchpad == "desligado"

    def test_ligar_de_volta_apaga_o_campo_do_perfil(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles import loader as loader_module
        from hefesto_dualsense4unix.profiles.loader import save_profile
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _handlers()
        _chamar(h, uniq=_P1, touchpad="desligado")
        corpo = _chamar(h, uniq=_P1, touchpad="ligado")

        assert corpo["touchpad"] == "ligado"
        assert REGISTRO.touchpad_ligado(_P1) is True
        perfil = o_que_vale(loader_module.load_profile("Bancada"))
        dele = (perfil.controllers or {}).get(chave_de_sensor(_P1))
        assert dele is None or dele.sensores is None

    def test_no_nativo_e_com_o_steam_input_o_jogo_le_o_hidraw(self, perfis: Path) -> None:
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(Profile(name="Bancada", match=MatchAny()))
        assert _chamar(_handlers(nativo=True), uniq=_P1, touchpad="desligado")[
            "touchpad_alcance"
        ] == "hidraw"
        assert _chamar(_handlers(steam_input=True), uniq=_P1, touchpad="desligado")[
            "touchpad_alcance"
        ] == "hidraw"

    def test_valor_que_nao_e_ligado_ou_desligado_e_recusado(self, perfis: Path) -> None:
        with pytest.raises(ValueError, match="ligado"):
            _chamar(_handlers(), uniq=_P1, touchpad="cursor")
        with pytest.raises(ValueError, match="touchpad"):
            _chamar(_handlers(), uniq=_P1)

    def test_o_estado_vivo_diz_o_toque_e_o_alcance(self) -> None:
        h = _handlers()
        REGISTRO.definir_touchpad(_P1, ligado=False)
        entry: dict[str, Any] = {"inputs": {}}
        h._merge_sensores(entry, _P1)
        assert entry["sensores"]["touchpad"] == "desligado"
        assert entry["sensores"]["touchpad_alcance"] == "vpad"


class TestNenhumEstiloEscreveOToque:
    def test_a_receita_do_estilo_nao_tem_campo_de_giro_nem_de_toque(self) -> None:
        from hefesto_dualsense4unix.profiles.estilos_de_jogo import Receita

        campos = {f.name for f in dataclasses.fields(Receita)}
        proibidos = {c for c in campos if "giro" in c or "sensor" in c or "touchpad" in c}
        assert not proibidos, f"a receita do estilo passou a escrever {sorted(proibidos)}"

    def test_o_fps_nao_escreve_os_sensores_do_controle(self) -> None:
        """MORDIDA: faça o estilo FPS escrever `sensores` e esta régua reprova."""
        from hefesto_dualsense4unix.profiles import estilos_de_jogo

        fonte = Path(estilos_de_jogo.__file__).read_text(encoding="utf-8")
        for palavra in ("ControllerSensoresOverride", "sensores=", "touchpad="):
            assert palavra not in fonte, f"o catálogo de estilos escreve {palavra!r}"
