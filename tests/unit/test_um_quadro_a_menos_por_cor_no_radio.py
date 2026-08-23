"""LUZ-CEGA-01/F3 — trocar a cor custava DOIS quadros de rádio; agora custa um.

`set_rgb` escrevia `brightness` e `multi_intensity` sempre, e cada escrita na
classe LED faz o kernel montar um output report. O `btmon` mediu os dois no
mesmo milissegundo, com bytes idênticos::

    t=19.320  hci0  vf1=0x04  RGB=(0,0,153)     <- brightness
    t=19.320  hci0  vf1=0x04  RGB=(0,0,153)     <- multi_intensity (idêntico)

O report leva o estado INTEIRO do LED, então o quadro do `brightness` já
carregava a cor nova: ele não acrescentava nada ao aparelho e custava um quadro
por controle por reconciliação, numa mesa cujo `dmesg` já mostra
`DualSense input CRC's check failed`.

O que este arquivo trava, e é a condição que a leva exigia para mexer na rota
quente: **o estado que o kernel enxerga no fim é BYTE A BYTE o mesmo**. O que
sai é um quadro a menos, nunca uma cor diferente.

MORDIDA (conferida nos dois sentidos, 22/08/2026, com o `src/` copiado para
fora da árvore e `PYTHONPATH` apontado para a cópia):

- devolvendo a escrita incondicional (`ok = self._write(brightness, "255")`):
  reprovam **2 de 7** — os dois casos que contam quadros no estado de regime;
- arrancando a escrita de vez (nunca escrever `brightness`): reprovam
  **2 de 7** — a barra apagada por um terceiro nunca mais reacenderia, que é o
  defeito que a leitura prévia existe para não criar;
- e a régua da leitura tem caso próprio: fazendo `_brightness_lido` devolver
  `0` (em vez de `None`) para valor ilegível, reprova **mais 1** — "não sei"
  colapsado em "está apagado" é o erro que esta casa persegue desde o
  ELO-MUDO-01.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import SysfsLedNode

#: Cores assimétricas em R e B — cinza (r == g == b) passaria com os canais
#: trocados e não provaria nada (mesma disciplina do PARIDADE-BYTE-01).
COR_A = (0x2A, 0x40, 0xC8)
COR_B = (0xC8, 0x40, 0x2A)


@pytest.fixture()
def no_e_gravacoes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SysfsLedNode, list[tuple[str, str]], Path]:
    """Um nó de LED em disco de verdade + o diário das escritas que saíram."""
    indicador = tmp_path / "input259:rgb:indicator"
    indicador.mkdir()
    (indicador / "multi_intensity").write_text("0 0 0")
    (indicador / "brightness").write_text("255")

    gravacoes: list[tuple[str, str]] = []
    original = SysfsLedNode._write

    def espiao(path: str, data: str) -> bool:
        gravacoes.append((os.path.basename(path), data))
        return bool(original(path, data))

    monkeypatch.setattr(SysfsLedNode, "_write", staticmethod(espiao))
    return SysfsLedNode(str(indicador), []), gravacoes, indicador


def _estado(indicador: Path) -> tuple[str, str]:
    return (
        (indicador / "brightness").read_text().strip(),
        (indicador / "multi_intensity").read_text().strip(),
    )


def test_com_o_brilho_ja_em_255_sai_um_quadro_so(
    no_e_gravacoes: tuple[SysfsLedNode, list[tuple[str, str]], Path],
) -> None:
    """O caso de REGIME: 255 já está lá, e reescrevê-lo é um quadro à toa."""
    no, gravacoes, indicador = no_e_gravacoes
    assert no.set_rgb(*COR_A) is True
    assert gravacoes == [("multi_intensity", "42 64 200")], gravacoes
    # E o kernel enxerga exatamente o mesmo estado de antes da cura.
    assert _estado(indicador) == ("255", "42 64 200")


def test_o_estado_final_e_byte_a_byte_o_de_antes(
    no_e_gravacoes: tuple[SysfsLedNode, list[tuple[str, str]], Path],
) -> None:
    """Paridade: dois `set_rgb` seguidos deixam o nó no MESMO estado de sempre.

    É a condição que a leva impôs para tocar a rota quente da luz — o que muda
    é a CONTAGEM de quadros, nunca o conteúdo.
    """
    no, gravacoes, indicador = no_e_gravacoes
    no.set_rgb(*COR_A)
    no.set_rgb(*COR_B)
    assert _estado(indicador) == ("255", "200 64 42")
    # Duas trocas de cor = dois quadros (um por cor), não quatro.
    assert len(gravacoes) == 2, gravacoes


def test_brilho_zerado_por_terceiro_volta_a_255_antes_da_cor(
    no_e_gravacoes: tuple[SysfsLedNode, list[tuple[str, str]], Path],
) -> None:
    """Um terceiro apagou pela classe LED: a cura NÃO pode deixar a barra apagada.

    E a ORDEM importa — `brightness` antes de `multi_intensity`, como sempre
    foi: acender depois de pôr a cor mostraria a cor VELHA por um quadro.
    """
    no, gravacoes, indicador = no_e_gravacoes
    (indicador / "brightness").write_text("0")
    assert no.set_rgb(*COR_A) is True
    assert gravacoes == [
        ("brightness", "255"),
        ("multi_intensity", "42 64 200"),
    ], gravacoes
    assert _estado(indicador) == ("255", "42 64 200")


def test_brilho_ilegivel_escreve_como_sempre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nó sumindo num replug: "não sei" leva a ESCREVER, nunca a pular.

    É a mesma regra do `verify=True` (veto 5 da síntese NUMA-03): ausência de
    leitura não é prova de estado.
    """
    indicador = tmp_path / "input262:rgb:indicator"
    indicador.mkdir()
    (indicador / "multi_intensity").write_text("0 0 0")
    # Sem arquivo `brightness` nenhum: a leitura devolve None.
    gravacoes: list[tuple[str, str]] = []
    original = SysfsLedNode._write

    def espiao(path: str, data: str) -> bool:
        gravacoes.append((os.path.basename(path), data))
        return bool(original(path, data))

    monkeypatch.setattr(SysfsLedNode, "_write", staticmethod(espiao))
    no = SysfsLedNode(str(indicador), [])
    no.set_rgb(*COR_A)
    assert [nome for nome, _ in gravacoes] == ["brightness", "multi_intensity"]


def test_o_cache_de_cor_igual_continua_valendo(
    no_e_gravacoes: tuple[SysfsLedNode, list[tuple[str, str]], Path],
) -> None:
    """GUERRA-01 item 3 não foi arranhado: cor repetida não sai no fio."""
    no, gravacoes, _indicador = no_e_gravacoes
    no.set_rgb(*COR_A)
    gravacoes.clear()
    assert no.set_rgb(*COR_A) is True
    assert gravacoes == []


def test_o_brilho_lido_nao_confunde_apagado_com_ilegivel(tmp_path: Path) -> None:
    """A régua do `_brightness_lido`: 0 é um NÚMERO, ausência é None.

    Sem este caso, um leitor que devolvesse 0 para arquivo ausente passaria
    despercebido — e 0 != 255 escreveria, mascarando o defeito no caso feliz.
    """
    indicador = tmp_path / "input266:rgb:indicator"
    indicador.mkdir()
    no = SysfsLedNode(str(indicador), [])
    assert no._brightness_lido() is None
    (indicador / "brightness").write_text("0")
    assert no._brightness_lido() == 0
    (indicador / "brightness").write_text("255")
    assert no._brightness_lido() == 255
    (indicador / "brightness").write_text("não é número")
    assert no._brightness_lido() is None


def test_o_is_on_le_pelo_mesmo_lugar_que_a_escrita(tmp_path: Path) -> None:
    """Uma régua só para o mesmo nó — duas que discordam já custaram caro aqui."""
    indicador = tmp_path / "input270:rgb:indicator"
    indicador.mkdir()
    no = SysfsLedNode(str(indicador), [])
    assert no.is_on() is False  # sem arquivo: "não sei" nunca vira "aceso"
    (indicador / "brightness").write_text("0")
    assert no.is_on() is False
    (indicador / "brightness").write_text("255")
    assert no.is_on() is True
    (indicador / "brightness").write_text("lixo")
    assert no.is_on() is False
