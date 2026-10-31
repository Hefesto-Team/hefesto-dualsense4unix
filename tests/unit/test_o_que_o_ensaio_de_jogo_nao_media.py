"""O ensaio de jogo sem régua devolve ``ok`` ou ``reprovou`` certo, com números de mentira.

`scripts/ensaios/o_que_o_ensaio_de_jogo_nao_media.py` (31/10/2026) mede cinco notas de sessão de
jogo. Aqui ele roda sem jogo e sem aparelho: os instantes do quadro, as amostras da CPU, os
``input_event`` do teclado, as linhas do diário e o ``/proc`` e o ``/sys`` são montados pela
régua, um pouco acima e um pouco abaixo de cada limite.

MORDIDA: inverta a comparação de ``dentro_do_limite`` e os vereditos reprovam.
"""
from __future__ import annotations

import importlib.util
import os
import struct
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "ensaios" / "o_que_o_ensaio_de_jogo_nao_media.py"


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("o_que_o_ensaio_de_jogo_nao_media", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


E = _carregar()


def _instantes(quadros_ms: list[float]) -> list[str]:
    agora = 5_000_000_000
    linhas = ["Attaching 1 probe...", str(agora)]
    for ms in quadros_ms:
        agora += int(ms * 1e6)
        linhas.append(str(agora))
    return linhas


def _amostras(pcts: list[float], hz: int = 100) -> list[str]:
    ticks, t, linhas = 0, 0.0, ["0.000 0"]
    for pct in pcts:
        t += 1.0
        ticks += round(pct / 100.0 * hz)
        linhas.append(f"{t:.3f} {ticks}")
    return linhas


def _evento(tipo: int, codigo: int, valor: int) -> bytes:
    return struct.pack(E.FORMATO_DO_EVENTO, 1, 0, tipo, codigo, valor)


def _diario(*eventos: str) -> list[str]:
    cabeca = "out 31 06:04:33 maquina hefesto-dualsense4unix[100]: 2026-10-31T06:04:33.256808"
    return [f"{cabeca} [info     ] {evento}" for evento in eventos]


ARME_0CE6 = "launch_arm_roupa               appid=1000 roupa=0ce6 vestem=['p1']"
ARME_EDGE = "launch_arm_roupa               appid=2000 roupa=0df2 vestem=['p1']"
RECRIOU_P1 = "gamepad_emulation_started      caminho=dualsense identity=aabbcc000001"
RECRIOU_P2 = "coop_player_roupa_trocada      identity=aabbcc000002"
ROUPA = "roupa_do_pad                   pedida=0ce6 veste=0ce6"


@pytest.mark.parametrize(
    ("medido", "limite", "sentido", "esperado"),
    [
        (4.9, 5.0, "<=", True),
        (5.0, 5.0, "<=", True),
        (5.1, 5.0, "<=", False),
        (1.0, 1.0, ">=", True),
        (0.0, 1.0, ">=", False),
    ],
)
def test_o_limite_se_le_no_sentido_dele(
    medido: float, limite: float, sentido: str, esperado: bool,
) -> None:
    assert E.dentro_do_limite(medido, limite, sentido) is esperado


def test_o_sentido_desconhecido_sai() -> None:
    with pytest.raises(ValueError, match="sentido desconhecido"):
        E.dentro_do_limite(1.0, 1.0, "<")


@pytest.mark.parametrize(
    ("com_ms", "sem_ms", "veredito"),
    [
        (99.0, 95.0, "ok"),
        (100.5, 95.0, "reprovou"),
        (94.0, 95.0, "ok"),
    ],
)
def test_o_quadro_mediano_com_o_hefesto(com_ms: float, sem_ms: float, veredito: str) -> None:
    com = E.quadros_em_ms(E.instantes_do_quadro(_instantes([com_ms] * 9 + [400.0])))
    sem = E.quadros_em_ms(E.instantes_do_quadro(_instantes([sem_ms] * 9 + [10.0])))
    linha = E.linha_do_quadro(com, sem)
    assert linha.item == 1
    assert linha.veredito == veredito
    assert linha.medido == pytest.approx((com_ms / sem_ms - 1) * 100, abs=0.01)


def test_o_quadro_sem_instante_e_sem_medida() -> None:
    assert E.linha_do_quadro([], [95.0]).veredito == "sem-medida"


@pytest.mark.parametrize(
    ("pico_com", "pico_sem", "veredito"),
    [
        (105.0, 100.0, "ok"),
        (120.0, 100.0, "reprovou"),
    ],
)
def test_o_pico_da_cpu_com_o_hefesto(pico_com: float, pico_sem: float, veredito: str) -> None:
    com = E.cpu_por_intervalo(E.amostras_da_cpu(_amostras([30.0, pico_com, 40.0])), 100)
    sem = E.cpu_por_intervalo(E.amostras_da_cpu(_amostras([20.0, pico_sem, 50.0])), 100)
    linha = E.linha_da_cpu(com, sem)
    assert linha.item == 6
    assert max(com) == pytest.approx(pico_com)
    assert linha.veredito == veredito


@pytest.mark.parametrize(("apertos", "veredito"), [(3, "ok"), (4, "ok"), (2, "reprovou")])
def test_as_teclas_que_chegaram_ao_evdev(apertos: int, veredito: str) -> None:
    esc = 1
    bruto = b"".join(
        _evento(E.EV_KEY, esc, 1) + _evento(0, 0, 0) + _evento(E.EV_KEY, esc, 0)
        for _ in range(apertos)
    )
    bruto += _evento(E.EV_KEY, 28, 1) + _evento(E.EV_KEY, esc, 2)
    chegaram = E.teclas_que_chegaram(bruto, esc)
    assert chegaram == apertos
    assert E.linha_do_teclado(chegaram, 3).veredito == veredito


def test_o_diario_se_le_no_formato_do_journal() -> None:
    eventos = E.eventos_do_diario([*_diario(ARME_0CE6, RECRIOU_P1), "linha sem evento"])
    campos = {"appid": "1000", "roupa": "0ce6", "vestem": "['p1']"}
    assert eventos[0] == ("launch_arm_roupa", campos)
    assert eventos[1][0] == "gamepad_emulation_started"
    assert len(eventos) == 2


@pytest.mark.parametrize(
    ("entre", "recriacoes", "veredito"),
    [
        ([RECRIOU_P1], 1, "ok"),
        ([RECRIOU_P1, ROUPA, RECRIOU_P1], 2, "reprovou"),
        ([RECRIOU_P2, RECRIOU_P1], 2, "reprovou"),
        ([], 0, "ok"),
    ],
)
def test_as_recriacoes_entre_dois_lancamentos_da_mesma_roupa(
    entre: list[str], recriacoes: int, veredito: str,
) -> None:
    linhas = _diario(RECRIOU_P1, RECRIOU_P1, ARME_0CE6, ARME_EDGE, *entre, ARME_0CE6, RECRIOU_P1)
    contagem = E.contar_a_roupa(E.eventos_do_diario(linhas))
    assert contagem is not None
    assert contagem["recriacoes"] == recriacoes
    assert contagem["launch_arm_roupa"] == 2
    linha = E.linha_da_roupa(contagem)
    assert linha.item == 4
    assert linha.veredito == veredito


def test_um_lancamento_so_e_sem_medida() -> None:
    contagem = E.contar_a_roupa(E.eventos_do_diario(_diario(ARME_0CE6, RECRIOU_P1, RECRIOU_P1)))
    assert contagem is None
    assert E.linha_da_roupa(contagem).veredito == "sem-medida"


def _mesa_do_jogo(tmp_path: Path, nos: dict[str, str]) -> tuple[Path, Path]:
    proc, sysfs = tmp_path / "proc", tmp_path / "sys"
    fds = proc / "4242" / "fd"
    fds.mkdir(parents=True)
    for i, (no, nome) in enumerate(nos.items()):
        os.symlink(no, fds / str(10 + i))
        base = os.path.basename(no)
        if base.startswith("event"):
            casa = sysfs / "class" / "input" / base / "device"
            casa.mkdir(parents=True)
            (casa / "name").write_text(nome + "\n", encoding="utf-8")
        else:
            casa = sysfs / "class" / "hidraw" / base / "device"
            casa.mkdir(parents=True)
            (casa / "uevent").write_text(f"HID_ID=0003:0000054C:00000CE6\nHID_NAME={nome}\n",
                                         encoding="utf-8")
    os.symlink("/dev/null", fds / "3")
    os.symlink("/dev/input/event5", fds / "99")
    return proc, sysfs


@pytest.mark.parametrize(
    ("nos", "veredito"),
    [
        ({"/dev/input/event5": "Hefesto P1", "/dev/hidraw9": "Hefesto P3"}, "ok"),
        ({"/dev/input/event5": "Hefesto P1", "/dev/input/event7": "Hefesto P3"}, "ok"),
        ({"/dev/input/event5": "Hefesto P1", "/dev/hidraw9": "Hefesto P2"}, "reprovou"),
    ],
)
def test_o_jogo_gdk_abre_o_vpad_do_p3(
    tmp_path: Path, nos: dict[str, str], veredito: str,
) -> None:
    proc, sysfs = _mesa_do_jogo(tmp_path, nos)
    abertos = E.nos_abertos([4242, 31337], proc, sysfs)
    assert sorted(no for _pid, no, _nome in abertos) == sorted(nos)
    assert E.linha_do_gdk(abertos).veredito == veredito


def test_os_ticks_do_stat_somam_usuario_e_sistema(tmp_path: Path) -> None:
    casa = tmp_path / "4242"
    casa.mkdir()
    campos = ["S"] + ["0"] * 10 + ["700", "45"] + ["0"] * 30
    (casa / "stat").write_text("4242 (jogo (x).exe) " + " ".join(campos) + "\n", encoding="utf-8")
    assert E.ticks_do_processo(4242, tmp_path) == 745
    assert E.ticks_do_processo(31337, tmp_path) is None


def test_a_receita_do_quadro_so_se_imprime() -> None:
    receita = E.receita_do_quadro(4242, "/x/files/lib/wine/x86_64-unix/winevulkan.so")
    assert "uprobe:/proc/4242/root/x/files/lib/wine/x86_64-unix/winevulkan.so" in receita
    assert ":thunk64_vkQueuePresentKHR /pid == 4242/" in receita


@pytest.mark.parametrize(("roupa_igual", "rc"), [(False, 0), (True, 1)])
def test_a_linha_de_comando_devolve_o_veredito(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], roupa_igual: bool, rc: int,
) -> None:
    entre = [RECRIOU_P1, RECRIOU_P1] if roupa_igual else [RECRIOU_P1]
    diario = tmp_path / "diario.txt"
    diario.write_text("\n".join(_diario(ARME_0CE6, *entre, ARME_0CE6)) + "\n", encoding="utf-8")
    assert E.main(["roupa", "--diario", str(diario)]) == rc
    saida = capsys.readouterr().out.strip()
    assert saida.startswith("item 4  recriacoes-entre-dois-0ce6  medido=")
    assert saida.split("  ")[4] == ("reprovou" if rc else "ok")
