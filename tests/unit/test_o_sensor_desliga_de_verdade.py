"""O interruptor de giroscópio/acelerômetro desliga DE VERDADE (SENSOR-DE-VERDADE-01)."""
from __future__ import annotations

import inspect
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.virtual_motion import (
    FAIXA_ACELEROMETRO,
    FAIXA_GIROSCOPIO,
    REGISTRO,
    TAMANHO_DA_JANELA,
    EstadoDosSensores,
    RegistroDeSensores,
    chave_de_sensor,
    janela_com_sensores,
    sensores_vivos_na_janela,
)
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    ControllerSensoresOverride,
    MatchAny,
    Profile,
)

PECA = "aa:bb:cc:00:00:01"
OUTRA = "aa:bb:cc:00:00:02"

JANELA_VIVA = bytes(range(1, TAMANHO_DA_JANELA + 1))


@pytest.fixture(autouse=True)
def _registro_limpo() -> Any:
    """O registro é do PROCESSO: um teste não pode vazar no outro."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


def test_desligar_o_giro_nao_toca_no_acelerometro() -> None:
    """*"ambos"* — e cada um por si. É a frase de produto, virada assertiva."""
    fora = janela_com_sensores(JANELA_VIVA, giroscopio=False)
    assert fora[FAIXA_GIROSCOPIO] == bytes(6)
    assert fora[FAIXA_ACELEROMETRO] == JANELA_VIVA[FAIXA_ACELEROMETRO]


def test_desligar_o_acelerometro_nao_toca_no_giro() -> None:
    fora = janela_com_sensores(JANELA_VIVA, acelerometro=False)
    assert fora[FAIXA_ACELEROMETRO] == bytes(6)
    assert fora[FAIXA_GIROSCOPIO] == JANELA_VIVA[FAIXA_GIROSCOPIO]


def test_o_touchpad_e_o_relogio_atravessam_o_interruptor() -> None:
    """Desligar sensor não pode apagar o dedo do usuário nem o `sensor_timestamp`."""
    fora = janela_com_sensores(JANELA_VIVA, giroscopio=False, acelerometro=False)
    assert fora[12:] == JANELA_VIVA[12:], "o timestamp/touchpad foi junto"


def test_com_os_dois_ligados_a_janela_volta_sem_copia() -> None:
    """O caminho quente roda a ~250 Hz: o caso normal não paga um `bytearray`."""
    assert janela_com_sensores(JANELA_VIVA) is JANELA_VIVA


def test_janela_de_tamanho_errado_volta_verbatim() -> None:
    """Quem recusa report torto é o vpad — duas políticas dariam duas respostas."""
    torta = b"\x01\x02\x03"
    assert janela_com_sensores(torta, giroscopio=False) is torta


def test_a_faixa_de_cada_sensor_casa_com_a_do_vpad() -> None:
    """As constantes daqui e as do `uhid_gamepad` descrevem a MESMA janela."""
    from hefesto_dualsense4unix.integrations import uhid_gamepad as ug

    assert TAMANHO_DA_JANELA == ug._MOTION_WINDOW_LEN
    assert FAIXA_GIROSCOPIO.start + ug._MOTION_WINDOW_START == 15
    assert FAIXA_ACELEROMETRO.start + ug._MOTION_WINDOW_START == 21
    assert FAIXA_ACELEROMETRO.stop + ug._MOTION_WINDOW_START == 27


def test_sem_entrada_os_dois_nascem_ligados() -> None:
    """`D-AUDIO-E-GIRO-NASCEM-LIGADOS`: ausência é o default dela, não "não sei"."""
    assert RegistroDeSensores().estado(PECA) == EstadoDosSensores(True, True)


def test_desligar_um_nao_liga_o_outro_de_volta() -> None:
    reg = RegistroDeSensores()
    reg.definir(PECA, giroscopio=False, acelerometro=False)
    assert reg.definir(PECA, giroscopio=True) == EstadoDosSensores(True, False)


def test_o_registro_e_por_peca() -> None:
    """Desligar o giro de UMA peça não pode calar o da vizinha."""
    reg = RegistroDeSensores()
    reg.definir(PECA, giroscopio=False)
    assert reg.estado(OUTRA).giroscopio is True


def test_voltar_a_tudo_ligado_apaga_a_entrada() -> None:
    """O default não ocupa lugar — o caminho quente vê um dicionário vazio."""
    reg = RegistroDeSensores()
    reg.definir(PECA, giroscopio=False)
    reg.definir(PECA, giroscopio=True)
    assert reg.desligados() == {}


def test_o_endereco_casa_em_maiuscula_e_minuscula() -> None:
    """O MAC chega do daemon em minúsculas e da tela como o usuário digitou."""
    reg = RegistroDeSensores()
    reg.definir(PECA.upper(), giroscopio=False)
    assert reg.estado(PECA).giroscopio is False


class _VpadDeMentira:
    """Guarda as janelas que recebeu. É o "jogo" desta régua."""

    def __init__(self) -> None:
        self.janelas: list[bytes] = []

    def forward_motion(self, window: bytes) -> None:
        self.janelas.append(bytes(window))


def _reader_com_peca(vpad: Any, uniq: str | None) -> Any:
    """Um `PhysicalReportReader` com a identidade já resolvida, sem hardware."""
    leitor = prr.PhysicalReportReader(path_provider=lambda: None, vpad=vpad)
    leitor._uniq_aberto = uniq
    return leitor


def test_a_janela_que_chega_ao_vpad_perde_o_giro() -> None:
    """**A MORDIDA.** Arranque o `REGISTRO.filtrar` do `_emit` e isto reprova."""
    vpad = _VpadDeMentira()
    leitor = _reader_com_peca(vpad, PECA)
    REGISTRO.definir(PECA, giroscopio=False)

    leitor._emit(JANELA_VIVA, 1.0)

    assert vpad.janelas, "o vpad não recebeu janela nenhuma"
    saiu = vpad.janelas[-1]
    assert sensores_vivos_na_janela(saiu) == EstadoDosSensores(False, True)
    assert saiu[FAIXA_ACELEROMETRO] == JANELA_VIVA[FAIXA_ACELEROMETRO]


def test_sem_saber_de_quem_e_a_janela_o_filtro_nao_age() -> None:
    """`uniq` desconhecido = não filtra. Errar para o lado de não desligar."""
    vpad = _VpadDeMentira()
    leitor = _reader_com_peca(vpad, None)
    REGISTRO.definir(PECA, giroscopio=False)

    leitor._emit(JANELA_VIVA, 1.0)

    assert vpad.janelas[-1] == JANELA_VIVA


def test_o_cache_do_reader_guarda_o_que_o_fisico_mandou() -> None:
    """O dedup é sobre o físico; o filtro é sobre o que SAI."""
    vpad = _VpadDeMentira()
    leitor = _reader_com_peca(vpad, PECA)
    REGISTRO.definir(PECA, giroscopio=False, acelerometro=False)

    leitor._emit(JANELA_VIVA, 1.0)

    assert leitor._last_window == JANELA_VIVA


def test_o_filtro_e_a_ultima_coisa_antes_do_vpad() -> None:
    """A ordem no `_emit` é o contrato, e ela é legível na fonte."""
    fonte = inspect.getsource(prr.PhysicalReportReader._emit)
    assert "REGISTRO.filtrar(self._uniq_aberto, window)" in fonte
    assert fonte.index("self._last_window = window") < fonte.index("REGISTRO.filtrar")


def test_uniq_do_hidraw_recusa_caminho_que_nao_e_hidraw() -> None:
    """`None` é "não sei de quem é" — e "não sei" tem de virar NÃO FILTRAR."""
    assert prr.uniq_do_hidraw("/dev/input/event22") is None
    assert prr.uniq_do_hidraw("") is None


def test_uniq_do_hidraw_le_o_hid_uniq_do_sysfs(tmp_path: Any) -> None:
    """A tradução caminho → peça, exercitada sobre um sysfs de mentira."""
    no = tmp_path / "hidraw9" / "device"
    no.mkdir(parents=True)
    (no / "uevent").write_text(
        f"DRIVER=playstation\nHID_UNIQ={PECA.upper()}\n", encoding="utf-8"
    )
    original = prr._RAIZ_HIDRAW
    try:
        prr._RAIZ_HIDRAW = str(tmp_path)
        assert prr.uniq_do_hidraw("/dev/hidraw9") == PECA
    finally:
        prr._RAIZ_HIDRAW = original


class _MotionDeMentira:
    """Reader de motion com a máquina de grab observável, sem `/dev/input`."""

    def __init__(self, uniq: str, node: Any) -> None:
        self.uniq = uniq
        self.grab_state = "off"
        self.parado = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def snapshot(self) -> Any:  # pragma: no cover - o hub o chama só em `leitura`
        raise AssertionError("esta régua não lê valor")


def _hub_com_dublês(relogio: Any) -> tuple[SensorHub, dict[str, _MotionDeMentira]]:
    criados: dict[str, _MotionDeMentira] = {}

    def fabrica(uniq: str, node: Any) -> _MotionDeMentira:
        criados[uniq] = _MotionDeMentira(uniq, node)
        return criados[uniq]

    hub = SensorHub(
        motion_factory=fabrica,
        touch_factory=lambda u, n: _MotionDeMentira(u, n),
        gamepad_factory=lambda u, n: _MotionDeMentira(u, n),
        descobrir_motion=lambda: {PECA: "/dev/input/event22", OUTRA: "/dev/x"},
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        relogio=relogio,
        auto_manutencao=False,
    )
    return hub, criados


def test_o_no_de_movimento_fica_exclusivo_quando_ela_desliga() -> None:
    """**A MORDIDA.** Arranque o `_reconciliar_grabs` e isto reprova."""
    agora = [100.0]
    hub, criados = _hub_com_dublês(lambda: agora[0])
    hub.leitura(PECA)
    hub.reconciliar()
    assert criados[PECA].grab_state == "off", "grab sem ela pedir nada"

    REGISTRO.definir(PECA, giroscopio=False)
    hub.reconciliar()

    assert criados[PECA].grab_state == "held"
    assert hub.grab_do_movimento(PECA) == "held"


def test_ligar_de_volta_solta_o_no() -> None:
    """O interruptor tem de andar nos dois sentidos, e soltar é metade dele."""
    agora = [100.0]
    hub, criados = _hub_com_dublês(lambda: agora[0])
    hub.leitura(PECA)
    REGISTRO.definir(PECA, giroscopio=False)
    hub.reconciliar()
    assert criados[PECA].grab_state == "held"

    REGISTRO.definir(PECA, giroscopio=True)
    hub.reconciliar()

    assert criados[PECA].grab_state == "off"


def test_desligar_uma_peca_nao_graba_o_no_da_vizinha() -> None:
    agora = [100.0]
    hub, criados = _hub_com_dublês(lambda: agora[0])
    hub.leitura(PECA)
    hub.leitura(OUTRA)
    REGISTRO.definir(PECA, giroscopio=False)
    hub.reconciliar()

    assert criados[PECA].grab_state == "held"
    assert criados[OUTRA].grab_state == "off"


def test_o_reader_do_movimento_sobrevive_a_gui_fechada() -> None:
    """**A MORDIDA.** Arranque o `| desligados` da união e isto reprova."""
    agora = [100.0]
    hub, criados = _hub_com_dublês(lambda: agora[0])
    hub.leitura(PECA)
    REGISTRO.definir(PECA, giroscopio=False)
    hub.reconciliar()
    reader = criados[PECA]

    agora[0] += SensorHub._DEMANDA_TTL_S + 60.0
    hub.reconciliar()

    assert not reader.parado, "o reader do sensor desligado foi podado"
    assert hub.grab_do_movimento(PECA) == "held"


def test_a_gui_fechada_ainda_poda_quem_esta_ligado() -> None:
    """A exceção é só para quem tem sensor desligado — o resto some como sempre."""
    agora = [100.0]
    hub, criados = _hub_com_dublês(lambda: agora[0])
    hub.leitura(OUTRA)
    hub.reconciliar()
    reader = criados[OUTRA]

    agora[0] += SensorHub._DEMANDA_TTL_S + 60.0
    hub.reconciliar()

    assert reader.parado
    assert hub.grab_do_movimento(OUTRA) == "sem_reader"


def test_o_reader_de_motion_de_verdade_sabe_grabar() -> None:
    """A máquina de EVIOCGRAB subiu para a base e alcança o nó de movimento."""
    from hefesto_dualsense4unix.core.evdev_reader import (
        EvdevReader,
        MotionSensorReader,
        TouchpadReader,
    )

    for classe in (MotionSensorReader, EvdevReader, TouchpadReader):
        leitor = classe(device_path=None, target_uniq=PECA)
        assert leitor.grab_state == "off"
        assert leitor.set_grab(True) is True
        assert leitor.grab_state == "pending", classe.__name__


def test_o_grab_volta_a_pendente_quando_o_no_cai() -> None:
    """Replug e troca de máscara passam por aqui — e o grab tem de voltar."""
    from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader

    leitor = MotionSensorReader(device_path=None, target_uniq=PECA)
    leitor.set_grab(True)
    leitor._grab_state = "held"
    leitor._reset_on_disconnect()
    assert leitor.grab_state == "pending"


class _StoreVazia:
    active_profile = None

    def snapshot(self) -> Any:  # pragma: no cover - o applier não a consulta
        raise AssertionError("o applier de sensor não lê o store")


def test_o_perfil_desliga_o_sensor_daquela_peca() -> None:
    """O degrau que faz a escolha do usuário sobreviver ao replug."""
    gerente = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreVazia(),  # type: ignore[arg-type]
    )
    perfil = Profile(
        name="uma_peca_so",
        match=MatchAny(),
        controllers={
            PECA: ControllerOverrides(
                sensores=ControllerSensoresOverride(giroscopio=False)
            )
        },
    )
    relatorio = gerente.apply_controller_sensores(perfil)

    assert REGISTRO.estado(PECA) == EstadoDosSensores(False, True)
    assert relatorio == {f"sensores:{chave_de_sensor(PECA)}": "giro=off accel=on"}
    assert REGISTRO.estado(OUTRA).giroscopio is True


def test_a_peneira_do_endereco_e_a_mesma_do_resto_da_casa() -> None:
    """`chave_de_sensor` e `norm_mac` têm de concordar — senão são dois donos."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    for endereco in (PECA, PECA.upper(), "aabbcc000001", "e8:47:3a:00:00:0f"):
        assert chave_de_sensor(endereco) == norm_mac(endereco)


def test_perfil_sem_a_secao_nao_mexe_em_nada() -> None:
    """Sem opinião é silêncio, não ordem — a mesma regra do alto-falante."""
    REGISTRO.definir(PECA, giroscopio=False)
    gerente = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreVazia(),  # type: ignore[arg-type]
    )
    perfil = Profile(
        name="sem_opiniao",
        match=MatchAny(),
        controllers={PECA: ControllerOverrides()},
    )
    gerente.apply_controller_sensores(perfil)

    assert REGISTRO.estado(PECA).giroscopio is False, "o perfil religou por omissão"


def test_o_esquema_recusa_campo_que_ele_nao_aplica() -> None:
    """`extra="forbid"`: nada de campo aceito-e-ignorado na borda."""
    with pytest.raises(ValueError):
        ControllerSensoresOverride.model_validate({"touchpad": False})


@pytest.fixture
def perfis(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Diretório de perfis isolado — o mesmo molde do `isolated_profiles_dir`."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Any:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


class _StoreDeMentira:
    def __init__(self, ativo: str | None) -> None:
        self.active_profile = ativo


class _HubDeMentira:
    """Hub com a superfície que o handler consulta — e nada mais."""

    def __init__(self, grab: str = "held") -> None:
        self.grab = grab
        self.reconciliou = 0

    def reconciliar(self) -> None:
        self.reconciliou += 1

    def grab_do_movimento(self, uniq: str) -> str:
        return self.grab


def _handlers(*, ativo: str | None, primario: str | None, nativo: bool = False) -> Any:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _H(IpcHandlersMixin):
        def __init__(self) -> None:
            self.store = _StoreDeMentira(ativo)  # type: ignore[assignment]
            self.controller = SimpleNamespace(  # type: ignore[assignment]
                describe_controllers=lambda: (
                    [{"connected": True, "uniq": primario}] if primario else []
                )
            )
            self.daemon = SimpleNamespace(  # type: ignore[assignment]
                is_native_mode=lambda: nativo
            )
            self._sensor_hub = _HubDeMentira()

    return _H()


def _chamar(h: Any, **params: Any) -> dict[str, Any]:
    import asyncio

    return asyncio.run(h._handle_sensor_set(params))


def test_o_metodo_desliga_grava_e_diz_o_alcance(perfis: Any) -> None:
    """Do IPC ao disco: o giro cai, o disco guarda, e a resposta é honesta."""
    from hefesto_dualsense4unix.profiles import loader as loader_module
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

    save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _handlers(ativo="Bancada", primario=PECA)

    corpo = _chamar(h, uniq=PECA, giroscopio=False)

    assert corpo["status"] == "ok"
    assert corpo["giroscopio"] is False and corpo["acelerometro"] is True
    assert corpo["gravado"] is True
    assert corpo["alcance"] == {"report": "aplicado", "evdev": "held"}
    assert corpo["ressalva"] is None
    assert REGISTRO.estado(PECA).giroscopio is False
    dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[
        chave_de_sensor(PECA)
    ]
    assert dele.sensores is not None and dele.sensores.giroscopio is False


def test_em_modo_nativo_a_resposta_diz_o_que_nao_alcanca(perfis: Any) -> None:
    """A entrega mais importante desta frente, e é uma FRASE."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _handlers(ativo="Bancada", primario=PECA, nativo=True)

    corpo = _chamar(h, uniq=PECA, giroscopio=False)

    assert corpo["alcance"]["report"] == "nao_se_aplica"
    assert "hidraw" in (corpo["ressalva"] or "")
    assert "Nativo" in (corpo["ressalva"] or "")


def test_ligar_de_volta_nao_tem_ressalva(perfis: Any) -> None:
    """Ligar nunca é parcial — o dado volta por todos os caminhos de uma vez."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _handlers(ativo="Bancada", primario=PECA, nativo=True)
    _chamar(h, uniq=PECA, giroscopio=False)

    corpo = _chamar(h, uniq=PECA, giroscopio=True)

    assert corpo["giroscopio"] is True
    assert corpo["ressalva"] is None


def test_sem_perfil_ativo_o_interruptor_vale_e_vai_ao_computador(perfis: Any) -> None:
    """Sem perfil ativo, o interruptor vale e sobrevive: ele é do computador."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador

    h = _handlers(ativo=None, primario=PECA)

    corpo = _chamar(h, uniq=PECA, giroscopio=False)

    assert corpo["status"] == "ok" and corpo["gravado"] is True
    assert corpo["onde"] == "computador"
    assert REGISTRO.estado(PECA).giroscopio is False
    sensores = o_computador().controles[chave_de_sensor(PECA)].sensores
    assert sensores is not None and sensores.giroscopio is False


def test_a_mesa_vazia_recusa_dizendo(perfis: Any) -> None:
    """Cair no primeiro da lista é o que faria a mesa cheia desligar o mesmo."""
    h = _handlers(ativo="Bancada", primario=None)

    corpo = _chamar(h, giroscopio=False)

    assert corpo["status"] == "sem_controle"
    assert "POR PEÇA" in corpo["motivo"]


def test_endereco_que_nao_e_mac_recusa_antes_do_disco(perfis: Any) -> None:
    """`norm_mac` de um path devolve chave plausível — e gravar ali some calada."""
    h = _handlers(ativo="Bancada", primario=None)

    corpo = _chamar(h, uniq="path:/dev/input/event9", giroscopio=False)

    assert corpo["status"] == "sem_endereco"


def test_sem_nenhum_dos_dois_campos_levanta(perfis: Any) -> None:
    h = _handlers(ativo="Bancada", primario=PECA)
    with pytest.raises(ValueError, match="ao menos um"):
        _chamar(h, uniq=PECA)


@pytest.mark.parametrize("valor", [1, "true", None, 0.0])
def test_tipo_errado_levanta_antes_do_disco(perfis: Any, valor: Any) -> None:
    h = _handlers(ativo="Bancada", primario=PECA)
    with pytest.raises(ValueError, match="boolean"):
        _chamar(h, uniq=PECA, giroscopio=valor)


def test_o_metodo_esta_no_despacho() -> None:
    """Handler sem entrada na tabela é método inalcançável."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    fonte = inspect.getsource(IpcServer.__post_init__)
    assert '"sensor.set": self._handle_sensor_set' in fonte
