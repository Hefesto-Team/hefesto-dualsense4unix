"""O instrumento do ABBA — O-ENGASGO-DO-JOGO-LEVE-SE-SEPARA-EM-ABBA-01."""
from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "quadros_do_jogo", RAIZ / "scripts" / "ensaios" / "quadros_do_jogo.py")
assert _spec is not None and _spec.loader is not None
qj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qj)

PROTON = "/home/x/.steam/debian-installation/compatibilitytools.d/GE-Proton11-7-x86_64"
MAPS = "\n".join([
    "10000000-10020000 r--p 00000000 103:02 1234 "
    "/usr/lib/x86_64-linux-gnu/libvulkan.so.1.4.309",
    f"20000000-20080000 r-xp 00010000 103:02 5678 "
    f"{PROTON}/files/lib/wine/x86_64-unix/winevulkan.so",
    f"30000000-30010000 r--p 00000000 103:02 9999 "
    f"{PROTON}/files/lib/wine/x86_64-windows/winevulkan.dll",
]) + "\n"

BPFTRACE = """\
Attaching 3 probes...
q 1000016600000 16600
q 1000033200000 16600
q 1000054200000 21000
q 1000080200000 26000
q 1000341200000 261000
q 1000357800000 16600
"""


def test_acha_o_winevulkan_do_lado_linux() -> None:
    caminho = qj.achar_winevulkan(1, MAPS)
    assert caminho is not None
    assert caminho.endswith("/x86_64-unix/winevulkan.so")


def test_sem_winevulkan_nao_ha_alvo() -> None:
    assert qj.achar_winevulkan(1, MAPS.splitlines()[0] + "\n") is None


def test_le_os_quadros_com_a_hora() -> None:
    quadros = qj.ler_saida(BPFTRACE, inicio_mono_ns=1_000_000_000_000,
                           inicio_wall=1_700_000_000.0)
    assert [round(q, 1) for _t, q in quadros] == [16.6, 16.6, 21.0, 26.0, 261.0, 16.6]
    assert round(quadros[4][0] - 1_700_000_000.0, 3) == 0.341


def test_o_balde_de_20_ms_conta_o_jitter() -> None:
    quadros = qj.ler_saida(BPFTRACE, 1_000_000_000_000, 1_700_000_000.0)
    rodada = qj.resumir_rodada(quadros, 180)
    assert rodada["quadros"] == 6
    assert rodada["acima_20"] == 3
    assert rodada["acima_50"] == 1
    assert len(rodada["picos"]) == 1 and rodada["picos"][0][1] == 261.0


def test_o_resumo_junta_as_repeticoes_da_mesma_celula() -> None:
    def rodada(rotulo: str, segundos: int, a20: int, a50: int, p99: float) -> dict[str, object]:
        return {"rotulo": rotulo, "segundos": segundos, "acima_20": a20,
                "acima_50": a50, "p99_ms": p99}

    linhas = [
        rodada("virtual-livre-1", 60, 30, 2, 25.0),
        rodada("virtual-livre-2", 60, 10, 0, 21.0),
        rodada("virtual-travado-1", 120, 8, 0, 17.0),
    ]
    texto = qj.resumo(linhas)
    assert "virtual-livre         2        20.0         1.0" in texto
    assert "virtual-travado       1         4.0         0.0" in texto
