"""Os números que a aba Gatilhos escreve sobre os modos são os do `PRESETS`.

Medido em 12/10/2026: o texto dizia «73 parâmetros» (a soma do `PRESETS` é 71) e
«`Machine` pede 6 barras» (ele tem 4); e o `install.sh` citava, num comentário,
`interface.hefesto_vivo:main` como alvo do console script, que o `pyproject.toml`
aponta para `interface.abrir:entrada`. Cada número agora é lido do fato.

Desde 15/10/2026 (a 03 do todo publicada) o pacote não escreve mais esses números: as
alavancas por parâmetro saíram com a página antiga. Quem os diz é a paridade (o CSV e o
documento do terceiro número), e a régua lê os três.

MORDIDAS: devolver «73 parâmetros», «Machine pede 6 barras» ou
`hefesto_vivo:main` reprova.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py"
INSTALL = RAIZ / "install.sh"
PYPROJECT = RAIZ / "pyproject.toml"
#: onde a casa escreve os números dos modos: o pacote da aba e a paridade com a GTK
FONTES = (
    PACOTE,
    RAIZ / "docs/data/paridade-gtk-html.csv",
    RAIZ / "docs/method/2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md",
)

POR_MODO = {s.name: len(s.params) for s in PRESETS}
SOMA = sum(POR_MODO.values())
COM_AJUSTE = sum(1 for n in POR_MODO.values() if n)


def _texto() -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in FONTES)


def test_a_soma_dos_parametros_escrita_e_a_do_presets() -> None:
    achados = re.findall(r"(\d+) parâmetros", _texto())
    assert achados, "nenhuma das fontes diz mais a soma dos parâmetros: ajuste a régua"
    errados = [n for n in achados if int(n) != SOMA]
    assert not errados, f"o texto diz {errados}; a soma do PRESETS é {SOMA}"


def test_quantos_modos_tem_ajuste_e_o_do_presets() -> None:
    achados = re.findall(r"(\d+) dos (\d+) modos", _texto())
    assert achados
    for com, de in achados:
        assert (int(com), int(de)) == (COM_AJUSTE, len(PRESETS)), (com, de)


def test_as_barras_de_cada_modo_citado_sao_as_do_presets() -> None:
    texto = _texto()
    citados = re.findall(r"`?(\w+)`? pede (\d+) barras", texto)
    citados += re.findall(r"\b(Rigid|Machine|MultiPositionFeedback|"
                          r"MultiPositionVibration) (\d+)\b", texto)
    # Sem `assert citados`: o «pede N barras» morava nas alavancas da página antiga, que
    # saíram em 15/10/2026, e hoje nenhuma fonte o escreve. A trava vale para quando voltar.
    for nome, n in citados:
        assert nome in POR_MODO, f"{nome} não é modo do PRESETS"
        assert POR_MODO[nome] == int(n), (
            f"o texto diz que {nome} tem {n}; o PRESETS tem {POR_MODO[nome]}")


def test_o_install_cita_o_alvo_de_entrada_do_pyproject() -> None:
    conf = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    alvo = conf["project"]["scripts"]["hefesto-dualsense4unix-gui"]
    modulo, _, funcao = alvo.rpartition(":")
    curto = ".".join(modulo.split(".")[-2:]) + ":" + funcao
    citados = re.findall(r"\binterface\.\w+:\w+", INSTALL.read_text(encoding="utf-8"))
    assert citados, "o install deixou de citar o alvo da interface: ajuste a régua"
    assert set(citados) == {curto}, (citados, curto)
