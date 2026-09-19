"""A ponte do rádio não atrasa o som em dois segundos — 18/09/2026.

MEDIDO com os três DualSense no rádio, um tom de 1 s tocando num nó
``hefesto_som_<hex6>`` só, e as escritas do daemon observadas com relógio: o
áudio saía nos relatórios ``0x35`` **1,79 a 2,04 s** depois de o tom começar,
e continuava ~2 s depois de ele acabar. O gravador do monitor era o ``parec``
sem ``--latency-msec``, que nasce com um fragmento de quase dois segundos — a
mesma forma que a casa já tinha medido e curado no microfone em 06/09
(``canal_do_microfone._LATENCIA_DO_ALIMENTADOR_MS``), e que ficou de fora
desta tabela.

A tabela é dona única: a ponte do alto-falante e a da vibração por áudio
passam por ela, e os dois gravadores (``pw-record`` e ``parec``) levam o
número explícito, para que o caminho escolhido não mude o atraso.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as afb


def _latencia_em_ms(argv: list[str]) -> int | None:
    for arg in argv:
        if arg.startswith("--latency-msec="):
            return int(arg.split("=", 1)[1])
        if arg.startswith("--latency=") and arg.endswith("ms"):
            return int(arg[len("--latency="):-2])
    return None


@pytest.mark.parametrize("gravador", ["pw-record", "parec"])
def test_os_dois_gravadores_pedem_latencia_curta(
    monkeypatch: pytest.MonkeyPatch, gravador: str
) -> None:
    """MORDIDA: tire o `--latency-msec` (ou o `--latency`) da tabela
    `GRAVADORES_DO_MONITOR` — o gravador volta ao fragmento padrão."""
    monkeypatch.setattr(
        afb.shutil, "which",
        lambda b: f"/usr/bin/{b}" if b == gravador else None)
    monkeypatch.setattr(afb, "o_servidor_e_o_pipewire", lambda *a, **k: True)
    monkeypatch.setattr(afb, "serial_do_no", lambda _nome: 75833)

    argv = afb.argv_do_gravador("hefesto_som_e64203.monitor", rotulo="hefesto-ponte-e64203")

    assert argv[0] == gravador, argv
    ms = _latencia_em_ms(argv)
    assert ms is not None, f"o {gravador} nasce sem latência pedida: {argv}"
    assert ms == afb.LATENCIA_DO_GRAVADOR_MS
    assert ms <= 100, "mais de 100 ms entre o jogo e o alto-falante se ouve"
