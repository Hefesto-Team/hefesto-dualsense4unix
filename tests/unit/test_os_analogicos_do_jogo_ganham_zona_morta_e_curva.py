#!/usr/bin/env python3
"""Os analógicos do jogo ganham zona morta, curva e uma mão (acessibilidade, 16/10/2026).

O motor puro (`core/curva_do_analogico.py`); os dois caminhos do pad virtual
(`gamepad.dispatch_gamepad` do P1 e `coop.forward_all` de P2 a P4); o giro feito analógico, que
passa pela mesma curva; as duas mãos; o depósito pelo perfil e o computador por baixo.

A MORDIDA, e cada uma foi rodada na entrega:

- tire a chamada `moldar_os_analogicos` do `coop.forward_all` e
  :func:`test_o_segundo_jogador_tem_a_curva_dele_e_o_primeiro_nao` reprova;
- tire a chamada de `gamepad.dispatch_gamepad` e :func:`test_o_primeiro_tem_a_zona_morta` reprova;
- tire o `lado_do_giro` de `aplicar_o_movimento` e
  :func:`test_a_mao_esquerda_olha_pelo_giro_e_anda_pelo_analogico_esquerdo` reprova;
- ponha a zona morta de volta numa constante (`zona_interna` fixa em zero em `montar`) e
  :func:`test_a_zona_morta_de_20_zera_10_e_nao_zera_30` reprova;
- tire o `definir_ativo` da curva de `apply_acessibilidade` e
  :func:`test_o_perfil_seguinte_larga_a_curva_do_anterior` reprova.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core import curva_do_analogico as cv
from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.profiles.schema import ProfileAnalogicosConfig

P2 = "aabbcc000002"
P1 = "aa:bb:cc:00:00:01"


def _curva(**campos: Any) -> cv.Curva:
    montada = cv.montar(SimpleNamespace(**campos))
    assert montada is not None, f"{campos} devia montar uma curva"
    return montada


def test_o_padrao_e_a_identidade_byte_a_byte() -> None:
    """Sem ajuste não há curva, e o que há de neutro devolve cada byte de 0 a 255.

    Prova da D-1610-OS-ANALOGICOS-DO-JOGO-GANHAM-ZONA-MORTA-CURVA-E-UMA-MAO.
    """
    assert cv.montar(None) is None
    assert cv.montar(SimpleNamespace()) is None
    assert cv.montar(SimpleNamespace(zona_morta=0, curva="linear", sensibilidade=100)) is None
    identidade = cv.Curva()
    for v in range(256):
        assert cv.moldar(identidade, v, 255 - v) == (v, 255 - v)
        assert cv.gatilho(identidade, v) == v
        assert cv.analogicos(identidade, v, 255 - v, (v * 7) % 256, (v * 3) % 256) == (
            v, 255 - v, (v * 7) % 256, (v * 3) % 256)
    store = SimpleNamespace()
    assert cv.aplicar(store, P1, 1, 2, 3, 4, 5, 6) == (1, 2, 3, 4, 5, 6)


def test_a_zona_morta_de_20_zera_10_e_nao_zera_30() -> None:
    curva = _curva(zona_morta=20)
    dez = 128 + round(0.10 * 127)
    trinta = 128 + round(0.30 * 127)
    assert cv.moldar(curva, dez, 128) == (128, 128), "10 % do curso devia cair na zona morta"
    x, _ = cv.moldar(curva, trinta, 128)
    assert x > 128, "30 % do curso está fora da zona morta de 20 % e devia passar"
    diag = 128 + round(0.15 * 127)
    assert cv.moldar(curva, diag, diag) != (128, 128)
    assert cv.moldar(curva, 255, 128)[0] == 255
    assert cv.moldar(curva, 0, 128)[0] == 0


def test_a_zona_externa_leva_o_fim_do_curso_ao_maximo() -> None:
    curva = _curva(zona_externa=20)
    assert cv.moldar(curva, 128 + round(0.80 * 127), 128)[0] == 255


def test_inverter_y_espelha_em_torno_do_centro() -> None:
    curva = _curva(inverter=["ly"])
    for v in range(1, 256):
        saida = cv.analogicos(curva, 100, v, 100, v)
        assert saida[0] == 100 and saida[2] == 100, "o X e o outro lado não mudam"
        assert saida[1] - 128 == -(v - 128) or v == 255, (v, saida)
        assert saida[3] == v, "o Y do analógico direito não foi pedido"
    assert cv.analogicos(curva, 0, 0, 0, 0)[1] == 255, "o zero espelha no fundo do outro lado"
    assert cv.analogicos(curva, 0, 128, 0, 128)[1] == 128


def test_a_troca_entrega_lx_no_rx() -> None:
    saida = cv.analogicos(_curva(trocar=True), 10, 20, 30, 40)
    assert saida == (30, 40, 10, 20)


def test_a_inversao_e_do_analogico_fisico_e_a_troca_vem_depois() -> None:
    saida = cv.analogicos(_curva(trocar=True, inverter=["lx"]), 10, 20, 30, 40)
    assert saida == (30, 40, 246, 20), "o lx físico inverte e SÓ ENTÃO vai ao lado direito"


def test_a_sensibilidade_escala_o_curso() -> None:
    metade = _curva(sensibilidade=50)
    assert abs(cv.moldar(metade, 255, 128)[0] - (128 + 64)) <= 1
    uma_vez_e_meia = _curva(sensibilidade=150)
    assert cv.moldar(uma_vez_e_meia, 255, 128)[0] == 255, "o curso satura, não passa de 255"
    assert abs(cv.moldar(uma_vez_e_meia, 128 + 64, 128)[0] - (128 + 96)) <= 1


def test_as_formas_da_curva() -> None:
    meio = 128 + 64
    linear = cv.moldar(_curva(curva="linear", sensibilidade=101), meio, 128)[0]
    precisa = cv.moldar(_curva(curva="precisa"), meio, 128)[0]
    digital_pouco = cv.moldar(_curva(curva="digital"), 128 + 50, 128)[0]
    digital_muito = cv.moldar(_curva(curva="digital"), 128 + 90, 128)[0]
    estavel = cv.moldar(_curva(curva="estavel"), 128 + 30, 128)[0]
    assert precisa < linear, "a precisa afina o começo do curso"
    assert abs(precisa - (128 + 32)) <= 2, "meio curso na precisa dá um quarto"
    assert digital_pouco == 128 and digital_muito == 255
    assert 128 < estavel < 128 + 30, "a estável suaviza o começo"


def test_o_gatilho_ganha_zona_de_inicio_e_de_fim() -> None:
    curva = _curva(gatilho_inicio=20, gatilho_fim=20)
    assert cv.gatilho(curva, 0) == 0 and cv.gatilho(curva, 50) == 0
    assert cv.gatilho(curva, 205) == 255 and cv.gatilho(curva, 255) == 255
    meio = cv.gatilho(curva, 128)
    assert 120 <= meio <= 135, "o meio do curso útil continua no meio"
    assert cv.gatilho(curva, 100) < cv.gatilho(curva, 150), "a resposta sobe sempre"


def test_a_peca_sobrepoe_o_perfil_campo_a_campo() -> None:
    perfil = SimpleNamespace(
        zona_morta=10, curva="precisa", model_fields_set={"zona_morta", "curva"})
    peca = SimpleNamespace(zona_morta=30, model_fields_set={"zona_morta"})
    junta = cv.montar(perfil, peca)
    assert junta is not None
    assert junta.zona_interna == pytest.approx(0.30) and junta.forma == "precisa"


def test_a_mao_e_a_troca_nao_se_pedem_juntas() -> None:
    with pytest.raises(ValidationError):
        ProfileAnalogicosConfig(mao="direita", trocar=True)
    perfil = SimpleNamespace(mao="direita", model_fields_set={"mao"})  # (noqa-acento)
    peca = SimpleNamespace(trocar=True, model_fields_set={"trocar"})
    junta = cv.montar(perfil, peca)
    assert junta is not None and junta.mao is None and junta.trocar, (
        "a soma que quebra a regra fica só com o que a peça escreveu")


def test_a_faixa_do_esquema_e_a_do_motor() -> None:
    for campo, valor in (("zona_morta", 51), ("zona_externa", 31), ("sensibilidade", 49),
                         ("sensibilidade", 151), ("gatilho_inicio", 41), ("gatilho_fim", -1)):
        with pytest.raises(ValidationError):
            ProfileAnalogicosConfig(**{campo: valor})
    with pytest.raises(ValidationError):
        ProfileAnalogicosConfig(curva="exponencial")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ProfileAnalogicosConfig(inverter=["lz"])  # type: ignore[list-item]
    assert ProfileAnalogicosConfig().model_dump(exclude_unset=True) == {}


class _Device:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


def _estado(lx: int = 128, ly: int = 128, rx: int = 128, ry: int = 128, l2: int = 0) -> Any:
    return SimpleNamespace(raw_lx=lx, raw_ly=ly, raw_rx=rx, raw_ry=ry, l2_raw=l2, r2_raw=0)


def _o_primeiro(monkeypatch: pytest.MonkeyPatch, store: Any, **extra: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    dev = _Device()
    daemon = SimpleNamespace(store=store, _gamepad_device=dev, **extra)

    def tique(estado: Any) -> dict[str, int]:
        gp.dispatch_gamepad(daemon, estado, frozenset())
        return dev.analog[-1]

    return SimpleNamespace(dev=dev, tique=tique, daemon=daemon)


def test_o_primeiro_tem_a_zona_morta(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    p1 = _o_primeiro(monkeypatch, store)
    pouco = 128 + round(0.10 * 127)
    assert p1.tique(_estado(lx=pouco))["lx"] == pouco, "sem curva o jogo vê o curso do controle"
    cv.definir_ativo(store, _curva(zona_morta=20))
    saida = p1.tique(_estado(lx=pouco, ly=pouco, rx=pouco, l2=30))
    assert (saida["lx"], saida["ly"], saida["rx"]) == (128, 128, 128)


def test_o_primeiro_recebe_a_troca_e_o_gatilho(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    cv.definir_ativo(store, _curva(trocar=True, gatilho_inicio=20))
    p1 = _o_primeiro(monkeypatch, store)
    saida = p1.tique(_estado(lx=10, ly=20, rx=30, ry=40, l2=40))
    assert (saida["lx"], saida["ly"], saida["rx"], saida["ry"]) == (30, 40, 10, 20)
    assert saida["l2"] == 0, "40 está dentro dos 20 % do começo do gatilho"


def _o_segundo(store: Any, snap: Any) -> tuple[Any, _Device]:
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None)
    mgr = CoopManager(daemon)
    vpad = _Device()
    leitor = SimpleNamespace(grab_state="held", snapshot=lambda: snap)
    mgr._players[P2] = _SecondaryPlayer(
        identity=P2, evdev_path="/dev/input/event9", reader=leitor, player_index=2,
        vpad=vpad)  # type: ignore[arg-type]
    return mgr, vpad


def _foto(lx: int, ly: int = 128, rx: int = 128, ry: int = 128, l2: int = 0) -> Any:
    return SimpleNamespace(lx=lx, ly=ly, rx=rx, ry=ry, l2_raw=l2, r2_raw=0,
                           buttons_pressed=frozenset())


def test_o_segundo_jogador_tem_a_curva_dele_e_o_primeiro_nao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    cv.definir_ativo(store, None, {P2: _curva(zona_morta=20, trocar=True)})
    pouco = 128 + round(0.10 * 127)
    mgr, vpad = _o_segundo(store, _foto(pouco, 128, 255, 128))
    mgr.forward_all()
    saida = vpad.analog[-1]
    assert (saida["lx"], saida["ly"]) == (255, 128), "o jogador 2 troca os lados"
    assert (saida["rx"], saida["ry"]) == (128, 128), "e a zona morta zera os 10 %"
    p1 = _o_primeiro(monkeypatch, store)
    assert p1.tique(_estado(lx=pouco))["lx"] == pouco, "a curva do jogador 2 não é a do 1"


def test_o_segundo_jogador_sem_curva_passa_o_curso() -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    cv.definir_ativo(store, _curva(zona_morta=40), {P2: None})
    mgr, vpad = _o_segundo(store, _foto(130, 131, 132, 133))
    mgr.forward_all()
    saida = vpad.analog[-1]
    assert (saida["lx"], saida["ly"], saida["rx"], saida["ry"]) == (130, 131, 132, 133)


class _Hub:
    def velocidade_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return (0.0, 120.0, 0.0)

    def angulo_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)


def _com_o_giro(monkeypatch: pytest.MonkeyPatch, store: Any, destino: str) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(REGISTRO, "estado", lambda _u: SimpleNamespace(
        giroscopio=True, acelerometro=False))
    rot.definir_ativo(store, rot.ArranjoDeMovimento(destino=destino))
    daemon = SimpleNamespace(_garantir_sensor_hub=lambda: _Hub(), store=store)

    def tique(lx: int, ly: int, rx: int, ry: int) -> tuple[int, int, int, int]:
        arranjo = rot.ativo(store)
        return gp.aplicar_o_movimento(
            daemon, arranjo, uniq=P1, lx=lx, ly=ly, rx=rx, ry=ry, botoes=frozenset())

    return tique


def test_o_giro_sem_mao_vai_onde_o_perfil_mandou(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace()
    tique = _com_o_giro(monkeypatch, store, rot.DESTINO_ANALOGICO_ESQUERDO)
    lx, ly, rx, ry = tique(128, 128, 128, 128)
    assert (lx, ly) != (128, 128) and (rx, ry) == (128, 128)


def test_a_mao_esquerda_olha_pelo_giro_e_anda_pelo_analogico_esquerdo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil mandou o giro ao esquerdo; a mão esquerda o leva ao lado que sobra."""
    store = SimpleNamespace()
    cv.definir_ativo(store, _curva(mao="esquerda"))
    tique = _com_o_giro(monkeypatch, store, rot.DESTINO_ANALOGICO_ESQUERDO)
    lx, ly, rx, ry = tique(200, 128, 128, 128)
    assert (lx, ly) == (200, 128), "o analógico esquerdo continua só da mão"
    assert (rx, ry) != (128, 128), "o olhar veio pelo giro, no analógico direito"
    jogo = cv.aplicar(store, P1, lx, ly, rx, ry, 0, 0)
    assert jogo[:2] == (200, 128) and jogo[2:4] == (rx, ry), "a mão esquerda não troca os lados"


def test_a_mao_direita_anda_pelo_analogico_direito_e_olha_pelo_giro(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A mão direita toca o analógico direito, que sai como movimento; o giro sai como olhar."""
    store = SimpleNamespace()
    cv.definir_ativo(store, _curva(mao="direita"))
    tique = _com_o_giro(monkeypatch, store, rot.DESTINO_ANALOGICO_DIREITO)
    lx, ly, rx, ry = tique(128, 128, 200, 128)
    assert (rx, ry) == (200, 128), "o giro foi ao esquerdo, e o direito é o da mão"
    jogo_lx, jogo_ly, jogo_rx, jogo_ry, _, _ = cv.aplicar(store, P1, lx, ly, rx, ry, 0, 0)
    assert (jogo_lx, jogo_ly) == (200, 128), "o movimento do jogo veio da mão direita"
    assert (jogo_rx, jogo_ry) != (128, 128), "o olhar do jogo veio do giro"


def test_o_giro_no_cursor_nao_muda_de_lado_com_a_mao() -> None:
    store = SimpleNamespace()
    cv.definir_ativo(store, _curva(mao="direita"))
    assert cv.lado_do_giro(store, P1, rot.DESTINO_MOUSE) == rot.DESTINO_MOUSE
    assert cv.lado_do_giro(store, P1, rot.DESTINO_NENHUM) == rot.DESTINO_NENHUM
    assert cv.lado_do_giro(store, P1, rot.DESTINO_ANALOGICO_DIREITO) == (
        rot.DESTINO_ANALOGICO_ESQUERDO)
    cv.definir_ativo(store, _curva(mao="esquerda"))
    assert cv.lado_do_giro(store, P1, rot.DESTINO_ANALOGICO_ESQUERDO) == (
        rot.DESTINO_ANALOGICO_DIREITO)
    cv.definir_ativo(store, None)
    assert cv.lado_do_giro(store, P1, rot.DESTINO_ANALOGICO_ESQUERDO) == (
        rot.DESTINO_ANALOGICO_ESQUERDO)


def test_o_giro_feito_analogico_passa_pela_mesma_curva(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace()
    tique = _com_o_giro(monkeypatch, store, rot.DESTINO_ANALOGICO_DIREITO)
    cru = tique(128, 128, 128, 128)
    assert cru[2:] != (128, 128)
    cv.definir_ativo(store, _curva(zona_morta=50, sensibilidade=50))
    moldado = cv.aplicar(store, P1, *cru, 0, 0)
    assert moldado[:4] != cru, "o giro feito analógico ganha a curva do analógico"


def test_o_perfil_seguinte_larga_a_curva_do_anterior(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente
    from hefesto_dualsense4unix.profiles.schema import Profile

    store = StateStore()
    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    for nome_do_metodo in ("apply", "apply_keyboard", "apply_button_actions", "apply_emulation"):
        monkeypatch.setattr(m, nome_do_metodo, lambda *a, **k: None)
    com = Profile.model_validate({
        "name": "Com Curva", "match": {"type": "any"},
        "analogicos": {"zona_morta": 20, "mao": "direita"},  # (noqa-acento)
        "controllers": {P2: {"analogicos": {"zona_morta": 5}}},
    })
    sem = Profile.model_validate({"name": "Sem Curva", "match": {"type": "any"}})
    monkeypatch.setattr(gerente, "load_profile", lambda nome: com)
    relatorio: dict[str, str] = {}
    m.activate("Com Curva", origin="system", relatorio=relatorio)
    assert relatorio["acessibilidade"] == "aplicado"
    assert cv.alguma(store)
    da_mesa = cv.da_peca(store, "outro")
    da_peca = cv.da_peca(store, P2)
    assert da_mesa is not None and da_mesa.zona_interna == pytest.approx(0.20)
    assert da_peca is not None and da_peca.zona_interna == pytest.approx(0.05)
    assert da_peca.mao == "direita", "a peça herda o resto do perfil, campo a campo"
    monkeypatch.setattr(gerente, "load_profile", lambda nome: sem)
    m.activate("Sem Curva", origin="system")
    assert not cv.alguma(store), "o perfil seguinte deixou a curva do anterior"
    assert cv.da_peca(store, P2) is None


def test_o_computador_vale_por_baixo_e_o_conflito_fica_com_o_jogo() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import perfil_que_vale
    from hefesto_dualsense4unix.profiles.schema import Profile
    from hefesto_dualsense4unix.utils.maquina import ComputadorDeclarado

    computador = ComputadorDeclarado.model_validate({
        "global": {"analogicos": {"zona_morta": 15, "mao": "direita"}}})  # (noqa-acento)
    sem_nada = Profile.model_validate({"name": "Jogo", "match": {"type": "any"}})
    vale = perfil_que_vale(sem_nada, computador)
    assert vale.analogicos is not None
    assert (vale.analogicos.zona_morta, vale.analogicos.mao) == (
        15, "direita")
    do_jogo = Profile.model_validate({
        "name": "Jogo", "match": {"type": "any"},
        "analogicos": {"zona_morta": 30, "trocar": True}})
    vale = perfil_que_vale(do_jogo, computador)
    assert vale.analogicos is not None
    assert vale.analogicos.zona_morta == 30 and vale.analogicos.trocar
    assert vale.analogicos.mao is None, "a mão do computador quebra a troca e cai"
