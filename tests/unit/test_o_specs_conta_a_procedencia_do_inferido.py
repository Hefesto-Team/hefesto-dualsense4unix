"""O `specs.html` diz QUEM sustenta cada inferência — contando, não digitando.

Até 05/09/2026 a legenda do mapa dizia apenas *"inferido-do-codigo (alguém leu a
fonte)"*, e as 408 células assim marcadas ficavam todas no mesmo grau. Isso
nivelava por baixo o trabalho de cerca de trezentos agentes que leram os
repositórios externos: **201 dessas células apontam para o driver do kernel**
(`hid-playstation`, `hid-nintendo`, `xpadneo`), e a decisão dela em 05/09/2026
foi explícita — *"Sim o driver é espec"*.

A resposta já estava no mapa, na coluna `codigo_ref` que eles preencheram (507
células). Não se acrescentou coluna nenhuma: acrescentar seria pedir que
refizessem trabalho feito. O gerador passou a LER a que existe.

Esta régua prova as duas metades: que o número publicado é o número de agora, e
que a contagem responde ao conteúdo — não a um literal no fonte.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SPECS = RAIZ / "html" / "specs.html"


def _gerador():
    caminho = RAIZ / "scripts" / "gerar-mapa.py"
    spec = importlib.util.spec_from_file_location("gerar_mapa", caminho)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gerar_mapa"] = mod
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


def test_o_censo_le_o_mapa_e_o_driver_e_a_maioria():
    mod = _gerador()
    conta = mod.procedencia_do_inferido(mod.le_csv())
    assert sum(conta.values()) > 300, "o censo perdeu células pelo caminho"
    assert conta["driver"] > conta["nosso"], (
        "as células sustentadas pelo driver deixaram de ser a maioria — "
        f"driver={conta['driver']} nosso={conta['nosso']}: confira se alguém "
        "regenerou o mapa por cima do trabalho dos agentes"
    )
    assert conta["sem_referencia"] < conta["driver"], (
        "as células sem referência alguma passaram as sustentadas pelo driver"
    )


def test_o_numero_publicado_no_specs_e_o_numero_de_agora():
    """A régua LÊ os dois lados. Digitar 201 aqui seria a mentira que ela mata."""
    mod = _gerador()
    conta = mod.procedencia_do_inferido(mod.le_csv())
    pagina = SPECS.read_text(encoding="utf-8")
    trecho = re.search(
        r"E <em>inferido-do-codigo</em> não é um grau só.*?</p>", pagina, re.S
    )
    assert trecho, "a legenda da procedência sumiu do specs.html"
    nus = [int(n) for n in re.findall(r"<strong>(\d+)</strong>", trecho.group(0))]
    assert nus == [
        conta["driver"],
        conta["os_dois"],
        conta["nosso"],
        conta["sem_referencia"],
    ], (
        f"o specs.html publica {nus} e o mapa de agora diz "
        f"{[conta['driver'], conta['os_dois'], conta['nosso'], conta['sem_referencia']]}: "
        "rode `.venv/bin/python scripts/gerar-mapa.py`"
    )


def test_a_mordida_a_contagem_responde_ao_conteudo():
    """Troque a fonte citada e a conta tem de mudar de balde."""
    mod = _gerador()
    molde = {c: "" for c in ("cabo_de_onde_sei", "radio_de_onde_sei", "fonte_externa",
                             "cabo_codigo_ref", "radio_codigo_ref",
                             "cabo_evidencia", "radio_evidencia")}

    def conta(codigo_ref: str) -> dict[str, int]:
        lin = dict(molde, cabo_de_onde_sei="inferido-do-codigo",
                   cabo_codigo_ref=codigo_ref)
        return mod.procedencia_do_inferido([lin])

    assert conta("assets/dkms/hid-nintendo/hid-nintendo.c:120")["driver"] == 1
    assert conta("core/backend_pydualsense.py:780")["nosso"] == 1
    assert conta("assets/dkms/hid-nintendo/hid-nintendo.c; core/mouse_emulation.py")["os_dois"] == 1
    assert conta("")["sem_referencia"] == 1
