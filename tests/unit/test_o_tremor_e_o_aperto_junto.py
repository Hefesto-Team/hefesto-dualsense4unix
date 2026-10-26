#!/usr/bin/env python3
"""O tremor e o aperto junto não decidem o botão (acessibilidade, 16/10/2026).

O motor (`core/filtro_de_botao.py`) com tempo falso; os dois caminhos do pad virtual
(`gamepad.dispatch_gamepad` do P1 e `coop.forward_all` de P2 a P4); a tabela de teclas com o
jogo; o PS travado do `HotkeyManager`; o depósito pelo perfil e a soltura na troca.

A MORDIDA, e cada uma foi rodada na entrega:

- filtre DEPOIS da troca de botões em `dispatch_gamepad` e
  :func:`test_o_filtro_mede_o_botao_da_mao_e_nao_o_da_troca` reprova;
- tire a chamada `filtrar_o_botao` do `coop.forward_all` e
  :func:`test_o_segundo_jogador_tem_o_filtro_dele_e_o_primeiro_nao` reprova;
- tire a chamada de `gamepad.dispatch_gamepad` e :func:`test_o_primeiro_ignora_o_tremor` reprova;
- tire o `esquecer` de `definir_ativo` e :func:`test_o_perfil_seguinte_solta_a_trava` reprova;
- tire o `or aperto.ps_virtual_ate is not None` de `combo_buttons_active` e
  :func:`test_o_segundo_botao_do_gesto_nao_vaza_ao_jogo` reprova;
- tire a abertura da janela do PS (o `espera > 0`) e :func:`test_o_ps_sozinho_espera_a_janela`
  reprova;
- tire o `virtual` do laço dos combos e :func:`test_o_ps_depois_o_outro_botao_dispara_o_gesto`
  reprova.
"""
from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import filtro_de_botao as fb
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyConfig, HotkeyManager

RAIZ = pathlib.Path(__file__).resolve().parents[2]
F = frozenset
P2 = "aabbcc000002"


def _rodar(
    filtro: fb.Filtro, quadros: list[tuple[set[str], int, int]], passo: float = 0.01
) -> list[tuple[float, frozenset[str], int, int]]:
    """Cada quadro `(botões, l2, r2)` um passo depois do outro; devolve `(t, botões, l2, r2)`."""
    estado = fb.FiltroDoControle()
    saida = []
    t = 100.0
    for botoes, l2, r2 in quadros:
        b, a, c, _ = estado.passo(filtro, F(botoes), l2, r2, t, F())
        saida.append((round(t - 100.0, 4), b, a, c))
        t += passo
    return saida


def _subidas(saida: list[tuple[float, frozenset[str], int, int]], botao: str) -> int:
    anterior: frozenset[str] = F()
    n = 0
    for _, agora, _, _ in saida:
        if botao in agora and botao not in anterior:
            n += 1
        anterior = agora
    return n


def test_o_tremor_dentro_do_repique_vira_um_aperto_so() -> None:
    filtro = fb.Filtro(repique_s=0.12)
    aperto, solto = ({"cross"}, 0, 0), (set(), 0, 0)
    quadros = [aperto] * 5 + [solto] * 8 + [aperto] * 5 + [solto] * 30
    saida = _rodar(filtro, quadros)
    assert _subidas(saida, "cross") == 1, "o segundo aperto, 80 ms depois, devia ser tremor"


def test_o_aperto_depois_do_repique_conta() -> None:
    filtro = fb.Filtro(repique_s=0.12)
    aperto, solto = ({"cross"}, 0, 0), (set(), 0, 0)
    quadros = [aperto] * 5 + [solto] * 20 + [aperto] * 5 + [solto] * 5
    assert _subidas(_rodar(filtro, quadros), "cross") == 2


def test_o_repique_de_um_botao_nao_prende_o_outro() -> None:
    filtro = fb.Filtro(repique_s=0.12)
    quadros = [({"cross"}, 0, 0)] * 3 + [(set(), 0, 0)] * 2 + [({"circle"}, 0, 0)] * 3
    saida = _rodar(filtro, quadros)
    assert _subidas(saida, "cross") == 1 and _subidas(saida, "circle") == 1


def test_o_aperto_mais_curto_que_o_minimo_nao_conta() -> None:
    filtro = fb.Filtro(aperto_minimo_s=0.05)
    saida = _rodar(filtro, [({"cross"}, 0, 0)] * 3 + [(set(), 0, 0)] * 10)
    assert all("cross" not in b for _, b, _, _ in saida), "30 ms são tropeço, não aperto"


def test_o_aperto_que_chega_ao_minimo_passa_a_partir_dele() -> None:
    filtro = fb.Filtro(aperto_minimo_s=0.05)
    saida = _rodar(filtro, [({"cross"}, 0, 0)] * 12 + [(set(), 0, 0)] * 5)
    primeiro = next(t for t, b, _, _ in saida if "cross" in b)
    assert primeiro == 0.05, f"o aperto só devia valer aos 50 ms, valeu aos {primeiro}"
    assert all("cross" not in b for _, b, _, _ in saida[12:]), "soltou com o botão"


def test_o_botao_que_trava_fica_preso_ate_o_proximo_e_solta_com_ele() -> None:
    filtro = fb.Filtro(travar=F({"l1"}))
    quadros = ([({"l1"}, 0, 0)] * 3 + [(set(), 0, 0)] * 3 + [({"cross"}, 0, 0)] * 4
               + [(set(), 0, 0)] * 4)
    saida = _rodar(filtro, quadros)
    assert all("l1" in b for _, b, _, _ in saida[:10]), "o L1 devia ficar preso até o próximo botão"
    assert all({"l1", "cross"} <= b for _, b, _, _ in saida[6:10]), "o L1 sai junto com a Cruz"
    assert all(b == F() for _, b, _, _ in saida[-3:]), "soltou o parceiro, solta a trava"


def test_reapertar_o_botao_travado_cancela() -> None:
    filtro = fb.Filtro(travar=F({"l1"}))
    um_aperto = [({"l1"}, 0, 0)] * 2 + [(set(), 0, 0)] * 2
    quadros = um_aperto + um_aperto
    quadros += [({"cross"}, 0, 0)] * 3 + [(set(), 0, 0)] * 3
    saida = _rodar(filtro, quadros)
    assert all("l1" in b for _, b, _, _ in saida[:6]), "o L1 fica preso até reapertar"
    assert all("l1" not in b for _, b, _, _ in saida[6:]), "reapertar o L1 devia soltar a trava"


def test_sem_filtro_o_tique_passa_o_mesmo_objeto() -> None:
    dono = SimpleNamespace()
    apertados = F({"cross"})
    saida = fb.traduzir(dono, None, apertados, 0, 0, 1.0)
    assert saida[0] is apertados


def test_a_peca_sobrepoe_o_perfil_campo_a_campo() -> None:
    perfil = SimpleNamespace(repique_ms=200, aperto_minimo_ms=0, travar=["l1"], ps_travado_ms=0)
    peca = SimpleNamespace(aperto_minimo_ms=60)
    montado = fb.montar(perfil, peca)
    assert montado is not None
    assert montado.repique_s == 0.2 and montado.aperto_minimo_s == 0.06
    assert montado.travar == F({"l1"})
    assert fb.montar(None) is None
    assert fb.montar(SimpleNamespace(repique_ms=0)) is None


def test_os_numeros_do_motor_sao_os_do_perfil() -> None:
    from hefesto_dualsense4unix.profiles.schema import ProfileAtivacaoConfig as C

    campos = C.model_fields
    assert campos["repique_ms"].default == 0 and campos["ps_travado_ms"].default == 0
    assert (campos["repique_ms"].metadata[0].ge,
            campos["repique_ms"].metadata[1].le) == (0, 1000)
    assert fb.REPIQUE_DE_FABRICA_MS == 120
    assert fb.APERTO_MINIMO_DE_FABRICA_MS == 50
    assert fb.PS_TRAVADO_DE_FABRICA_MS == 600


class _Device:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


def _estado(l2: int = 0, r2: int = 0) -> Any:
    return SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128, l2_raw=l2, r2_raw=r2)


def _o_primeiro(monkeypatch: pytest.MonkeyPatch, store: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    relogio = [200.0]
    monkeypatch.setattr(gp, "_agora", lambda: relogio[0])
    dev = _Device()
    daemon = SimpleNamespace(store=store, _gamepad_device=dev)

    def tique(botoes: set[str], l2: int = 0, r2: int = 0, passo: float = 0.01) -> None:
        relogio[0] += passo
        gp.dispatch_gamepad(daemon, _estado(l2, r2), F(botoes))

    return SimpleNamespace(dev=dev, tique=tique)


def test_o_primeiro_ignora_o_tremor(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    fb.definir_ativo(store, fb.Filtro(repique_s=0.12))
    p1 = _o_primeiro(monkeypatch, store)
    for botoes in ([{"cross"}] * 4 + [set()] * 3 + [{"cross"}] * 4 + [set()] * 4):
        p1.tique(botoes)
    subidas = sum(1 for antes, agora in zip([F(), *p1.dev.buttons], p1.dev.buttons, strict=False)
                  if "cross" in agora and "cross" not in antes)
    assert subidas == 1, f"o jogo viu {subidas} apertos de um tremor"


def test_sem_filtro_o_jogo_recebe_o_mesmo_objeto(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    p1 = _o_primeiro(monkeypatch, store)
    apertados = F({"cross", "l1"})
    gp.dispatch_gamepad(SimpleNamespace(store=store, _gamepad_device=p1.dev), _estado(), apertados)
    assert p1.dev.buttons[-1] is apertados


def test_o_filtro_mede_o_botao_da_mao_e_nao_o_da_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Cruz travada e trocada pelo Círculo: o jogo vê o Círculo preso, não a Cruz."""
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    fb.definir_ativo(store, fb.Filtro(travar=F({"cross"})))
    remap.definir_ativo(store, {"cross": "circle"})
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique({"cross"})
    p1.tique(set())
    p1.tique(set())
    assert p1.dev.buttons[-1] == F({"circle"}) or "circle" in p1.dev.buttons[-1], (
        f"o jogo devia ver o Círculo da troca preso, viu {p1.dev.buttons[-1]}")
    assert fb.preso(store, None)


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


def _foto(botoes: set[str], l2: int = 0) -> Any:
    return SimpleNamespace(lx=1, ly=2, rx=3, ry=4, l2_raw=l2, r2_raw=0,
                           buttons_pressed=F(botoes))


def test_o_segundo_jogador_tem_o_filtro_dele_e_o_primeiro_nao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    fb.definir_ativo(store, None, {P2: fb.Filtro(aperto_minimo_s=0.05)})
    relogio = [300.0]
    monkeypatch.setattr(gp, "_agora", lambda: relogio[0])
    snap = _foto({"cross"})
    mgr, vpad = _o_segundo(store, snap)
    mgr.forward_all()
    snap.buttons_pressed = F()
    relogio[0] += 0.01
    mgr.forward_all()
    assert all("cross" not in b for b in vpad.buttons), (
        f"o jogador 2 apertou 10 ms e o jogo viu {vpad.buttons}")
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique({"cross"})
    assert "cross" in p1.dev.buttons[-1], "o filtro do jogador 2 calou o jogador 1"


def test_o_segundo_jogador_sem_filtro_passa_o_mesmo() -> None:
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    fb.definir_ativo(store, fb.Filtro(aperto_minimo_s=0.05), {P2: None})
    mgr, vpad = _o_segundo(store, _foto({"cross"}))
    mgr.forward_all()
    assert vpad.buttons[-1] == F({"cross"})


def test_o_perfil_seguinte_solta_a_trava(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente
    from hefesto_dualsense4unix.profiles.schema import Profile

    store = StateStore()
    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    for nome_do_metodo in ("apply", "apply_keyboard", "apply_button_actions", "apply_emulation"):
        monkeypatch.setattr(m, nome_do_metodo, lambda *a, **k: None)
    com = Profile.model_validate({
        "name": "Com Trava", "match": {"type": "any"},
        "ativacao": {"travar": ["l1"], "repique_ms": 120}})  # (noqa-acento)
    sem = Profile.model_validate({"name": "Sem Trava", "match": {"type": "any"}})
    monkeypatch.setattr(gerente, "load_profile", lambda nome: com)
    relatorio: dict[str, str] = {}
    m.activate("Com Trava", origin="system", relatorio=relatorio)
    assert relatorio["acessibilidade"] == "aplicado"
    p1 = _o_primeiro(monkeypatch, store)
    p1.tique({"l1"})
    p1.tique(set())
    p1.tique({"cross"})
    assert p1.dev.buttons[-1] == F({"l1", "cross"})
    assert fb.preso(store, None)
    monkeypatch.setattr(gerente, "load_profile", lambda nome: sem)
    m.activate("Sem Trava", origin="system")
    assert not fb.preso(store, None), "o perfil seguinte deixou a trava presa"
    p1.tique({"cross"})
    assert p1.dev.buttons[-1] == F({"cross"}), "o jogo ainda via o L1 do perfil anterior"


def test_parar_o_pad_ou_a_sessao_do_jogador_solta() -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    store = SimpleNamespace()
    fb.definir_ativo(store, fb.Filtro(travar=F({"l1"})))
    store._filtro_de_botao_estados = {("", P2): fb.FiltroDoControle(),
                                      ("", "ff"): fb.FiltroDoControle()}
    daemon = SimpleNamespace(store=store, controller=SimpleNamespace())
    gp.end_game_output_session(daemon, target_uniq=P2)  # type: ignore[arg-type]
    assert list(store._filtro_de_botao_estados) == [("", "ff")]
    gp.soltar_a_ativacao(daemon)
    assert not store._filtro_de_botao_estados


def test_a_tabela_com_o_jogo_ignora_o_tremor(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import mouse

    relogio = [50.0]
    monkeypatch.setattr(mouse, "_agora", lambda: relogio[0])
    store = SimpleNamespace()
    fb.definir_ativo(store, fb.Filtro(aperto_minimo_s=0.05))
    tabela = mouse.TabelaNoJogo(None, None, ligada=True)
    visto: list[frozenset[str]] = []
    tabela._mouse = SimpleNamespace(dispatch=lambda **kw: visto.append(kw["buttons"]))
    tabela._teclado = SimpleNamespace(dispatch=lambda b: None)
    daemon = SimpleNamespace(store=store, controller=SimpleNamespace(primary_uniq=None))
    for botoes in ({"cross"}, set()):
        relogio[0] += 0.01
        tabela.tick(daemon, _estado(), F(botoes))
    assert all("cross" not in b for b in visto), f"a tabela viu {visto} num aperto de 10 ms"


def _gestos(espera_ms: dict[str | None, int] | None = None) -> tuple[HotkeyManager, list[str]]:
    visto: list[str] = []
    gerente = HotkeyManager(
        on_next=lambda: visto.append("next"),
        on_prev=lambda: visto.append("prev"),
        on_ps_solo=lambda: visto.append("ps_solo"),
        config=HotkeyConfig(ps_toque_curto_teto_ms=700),
        ps_travado_de=(lambda de: (espera_ms or {}).get(de, 0)) if espera_ms is not None else None,
    )
    return gerente, visto


def _toque_no_ps(gerente: HotkeyManager, de: str | None = None, t: float = 0.0) -> float:
    """O PS apertado por 100 ms e solto; devolve o instante da soltura."""
    gerente.observe({"ps"}, now=t, de=de)
    gerente.observe({"ps"}, now=t + 0.1, de=de)
    gerente.observe(set(), now=t + 0.15, de=de)
    return t + 0.15


def test_o_ps_depois_o_outro_botao_dispara_o_gesto() -> None:
    """Prova da D-1610-O-TREMOR-E-O-APERTO-JUNTO-NAO-DECIDEM-O-BOTAO."""
    gerente, visto = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    assert gerente.observe({"dpad_up"}, now=solto + 0.25) == "next"
    gerente.observe({"dpad_up"}, now=solto + 0.3)
    gerente.observe(set(), now=solto + 0.35)
    gerente.observe(set(), now=solto + 2.0)
    assert visto == ["next"], f"o gesto saiu como {visto}"


def test_sem_o_ps_travado_o_outro_botao_depois_nao_dispara() -> None:
    gerente, visto = _gestos()
    solto = _toque_no_ps(gerente)
    gerente.observe({"dpad_up"}, now=solto + 0.25)
    gerente.observe({"dpad_up"}, now=solto + 0.45)
    gerente.observe(set(), now=solto + 0.5)
    assert "next" not in visto
    assert visto == ["ps_solo"], "o PS sozinho dispara na soltura, como sempre"


def test_o_ps_sozinho_espera_a_janela() -> None:
    gerente, visto = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    assert gerente.observe(set(), now=solto + 0.3) is None and visto == []
    assert gerente.observe(set(), now=solto + 0.61) == "ps_solo"
    gerente.observe(set(), now=solto + 1.5)
    assert visto == ["ps_solo"], "o PS sozinho dispara uma vez só"


def test_o_gesto_que_saiu_pela_janela_nao_vira_ps_sozinho_depois() -> None:
    gerente, visto = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    gerente.observe({"dpad_down"}, now=solto + 0.1)
    gerente.observe(set(), now=solto + 0.2)
    gerente.observe(set(), now=solto + 1.0)
    assert visto == ["prev"]


def test_o_botao_segurado_estende_a_janela() -> None:
    """Quem demora a soltar o segundo botão não perde o gesto nem dispara o PS sozinho."""
    gerente, visto = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    for dt in (0.5, 0.8, 1.2):
        gerente.observe({"dpad_up"}, now=solto + dt)
    gerente.observe(set(), now=solto + 1.3)
    gerente.observe(set(), now=solto + 3.0)
    assert visto == ["next"]


def test_o_segundo_botao_do_gesto_nao_vaza_ao_jogo() -> None:
    gerente, _ = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    gerente.observe({"dpad_up"}, now=solto + 0.2)
    assert gerente.combo_buttons_active({"dpad_up"}) == F({"dpad_up"}), (
        "o cima do gesto chegaria ao jogo")


def test_um_botao_fora_do_gesto_nao_estende_nem_dispara() -> None:
    gerente, visto = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    gerente.observe({"cross"}, now=solto + 0.2)
    gerente.observe(set(), now=solto + 0.7)
    assert visto == ["ps_solo"]


def test_o_ps_travado_e_de_cada_controle() -> None:
    gerente, visto = _gestos({"aa:00": 600, "bb:00": 0})
    _toque_no_ps(gerente, de="bb:00")
    assert visto == ["ps_solo"], "o controle sem PS travado dispara o PS na soltura"
    visto.clear()
    solto = _toque_no_ps(gerente, de="aa:00", t=10.0)
    assert visto == [], "o controle com PS travado espera"
    gerente.observe({"dpad_up"}, now=solto + 0.2, de="bb:00")
    assert "next" not in visto, "o PS travado de um controle não vale para o outro"


def test_o_ps_apertado_de_verdade_na_janela_solta_o_toque_anterior() -> None:
    gerente, visto = _gestos({None: 600})
    solto = _toque_no_ps(gerente)
    assert gerente.observe({"ps"}, now=solto + 0.2) == "ps_solo"
    assert visto == ["ps_solo"]


def test_o_gesto_dos_dois_botoes_apertados_juntos_segue_como_antes() -> None:
    gerente, visto = _gestos({None: 600})
    gerente.observe({"ps", "dpad_up"}, now=0.0)
    assert gerente.observe({"ps", "dpad_up"}, now=0.2) == "next"
    assert visto == ["next"]


def test_o_gerente_do_daemon_pergunta_ao_filtro_do_controle(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    store = SimpleNamespace()
    fb.definir_ativo(store, None, {P2: fb.Filtro(ps_travado_s=0.6)})
    daemon = SimpleNamespace(
        store=store, _hotkey_manager=None, _tasks=[],
        config=SimpleNamespace(ps_long_press_ms=0, ps_button_action="steam"))
    hotkey.start_hotkey_manager(daemon)  # type: ignore[arg-type]
    pergunta = daemon._hotkey_manager.ps_travado_de
    assert pergunta("AA:BB:CC:00:00:02") == 600
    assert pergunta("AA:BB:CC:00:00:03") == 0


def _chama(arquivo: str, funcao: str, nome: str) -> bool:
    caminho = RAIZ / "src/hefesto_dualsense4unix/daemon/subsystems" / arquivo
    arvore = ast.parse(caminho.read_text())
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == funcao:
            return any(
                isinstance(c, ast.Call) and getattr(c.func, "id", None) == nome
                for c in ast.walk(no))
    return False


def test_os_dois_caminhos_chamam_o_dono_unico() -> None:
    assert _chama("gamepad.py", "dispatch_gamepad", "filtrar_o_botao")
    assert _chama("coop.py", "forward_all", "filtrar_o_botao")


@pytest.mark.parametrize("secao", [
    {"travar": ["l1"], "alternar": ["l1"]},
    {"travar": ["botao_que_nao_existe"]},
    {"repique_ms": 5000},
    {"aperto_minimo_ms": 900},
    {"ps_travado_ms": 9000},
])
def test_o_perfil_recusa_o_filtro_que_o_motor_recusa(secao: dict[str, Any]) -> None:
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import Profile

    with pytest.raises(ValidationError):
        Profile.model_validate({
            "name": "X", "match": {"type": "any"},
            "ativacao": secao})  # (noqa-acento)


def test_o_perfil_sem_os_campos_nao_grava_a_chave_e_com_eles_volta_igual() -> None:
    from hefesto_dualsense4unix.profiles.schema import Profile

    vazio = Profile.model_validate({"name": "Vazio", "match": {"type": "any"}})
    assert "ativacao" not in vazio.model_dump(mode="json")  # (noqa-acento)
    cheio = Profile.model_validate({
        "name": "Cheio", "match": {"type": "any"},
        "ativacao": {"repique_ms": 120, "aperto_minimo_ms": 50,  # (noqa-acento)
                     "travar": ["l1", "r1"], "ps_travado_ms": 600},
        "controllers": {P2: {"ativacao": {"repique_ms": 200}}}})  # (noqa-acento)
    volta = Profile.model_validate(cheio.model_dump(mode="json"))
    assert volta.ativacao is not None and volta.ativacao.travar == ["l1", "r1"]
    assert volta.controllers is not None
    assert volta.controllers[P2].ativacao.repique_ms == 200  # type: ignore[union-attr]
