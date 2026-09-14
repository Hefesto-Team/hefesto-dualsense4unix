"""TROCA-DENTRO-DO-JOGO-01 — dois combos no mesmo aperto não viram rajada.

Achado da conferência de 14/09/2026, e ele é da classe "o produto age sozinho no
meio do jogo dela": os combos do Hefesto são todos `PS + alguma coisa`, e o
casamento é por SUBCONJUNTO. Afundar os dois analógicos com o PS pressionado —
`{ps, l3, r3}` — contém o `ps+r3` (próximo MODO) e o `ps+l3` (próxima MÁSCARA).

O laço de despacho travava só o ÚLTIMO combo que disparou, então a cada tique ele
disparava o outro. Medido aqui, com o `HotkeyManager` isolado e o aperto
segurado: 25 disparos em 0,4 s, alternando modo e máscara. O daemon lê o controle
a 60 Hz (`lifecycle`), e cada disparo desses recria o vpad e grava o perfil no
meio da partida. `{ps, dpad_up, r3}` fazia o mesmo desde antes de a máscara
existir.

MORDE: devolver `if self._last_fired == combo` ao laço de `observe`.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager


def _gerente(eventos: list[str]) -> HotkeyManager:
    return HotkeyManager(
        on_next=lambda: eventos.append("next"),
        on_prev=lambda: eventos.append("prev"),
        on_next_bridge=lambda: eventos.append("ponte"),
        on_next_mask=lambda: eventos.append("mascara"),
    )


def _segurar(mgr: HotkeyManager, botoes: list[str], *, tiques: int = 25) -> None:
    """O aperto segurado, como o laço do daemon o vê: 60 Hz, ~16,7 ms."""
    for n in range(tiques):
        mgr.observe(botoes, now=n * 0.0167)


def test_os_dois_analogicos_com_o_ps_disparam_uma_vez_so() -> None:
    eventos: list[str] = []
    mgr = _gerente(eventos)

    _segurar(mgr, ["ps", "l3", "r3"])

    assert len(eventos) == 1, f"rajada: {eventos}"
    assert eventos[0] in ("ponte", "mascara")


def test_o_ps_mais_cima_mais_r3_tambem_dispara_uma_vez_so() -> None:
    """A classe do defeito é anterior à máscara — `{ps, dpad_up, r3}`."""
    eventos: list[str] = []
    mgr = _gerente(eventos)

    _segurar(mgr, ["ps", "dpad_up", "r3"])

    assert len(eventos) == 1, f"rajada: {eventos}"


def test_soltar_um_botao_destrava_o_gesto_seguinte() -> None:
    """Ela solta o R3 e continua com PS + L3: a máscara anda UMA vez."""
    eventos: list[str] = []
    mgr = _gerente(eventos)

    _segurar(mgr, ["ps", "l3", "r3"], tiques=20)
    primeiro = list(eventos)
    _segurar(mgr, ["ps", "l3"], tiques=20)

    assert primeiro == eventos[:1], "o primeiro aperto disparou mais de uma vez"
    assert len(eventos) == 2, f"esperava um por aperto: {eventos}"
    assert eventos[1] == "mascara", "com o R3 solto, o que sobra é o PS + L3"


def test_o_toque_repetido_do_perfil_continua_repetindo() -> None:
    """PS segurado e cima TOCADO três vezes = três perfis. Não pode travar."""
    eventos: list[str] = []
    mgr = _gerente(eventos)

    for volta in range(3):
        base = volta * 1.0
        mgr.observe(["ps", "dpad_up"], now=base)
        mgr.observe(["ps", "dpad_up"], now=base + 0.2)
        mgr.observe(["ps"], now=base + 0.4)

    assert eventos == ["next", "next", "next"]
