"""A prova de que o porte não mudou o cálculo."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor

RAIZ = Path(__file__).resolve().parents[2]
ORACULO = RAIZ / "tests" / "fixtures" / "motor_do_arranjo_do_mockup.js"
OURO = RAIZ / "tests" / "fixtures" / "motor_do_arranjo_do_mockup.json"

OPCOES = {v.id: v.opcoes for v in motor.VARIANTES}


def _js(v: object) -> str:
    """A chave do cenário como o JavaScript a escreveu: ``null``, não ``None``."""
    return "null" if v is None else str(v)


DIVERGENCIA_DA_PALAVRA_MESA: dict[str, str] = {
    "entrada direta, mas na altura da mesa":
        "entrada direta, mas na altura da escrivaninha",
    "os dongles ficam na altura da mesa, não no alto do rack":
        "os dongles ficam na altura da escrivaninha, não no alto do rack",
}

_TRADUZIDAS: dict[str, int] = {frase: 0 for frase in DIVERGENCIA_DA_PALAVRA_MESA}


def ouro(chave: str) -> Any:
    """O que o mockup respondeu neste cenário, com ``Infinity`` de volta."""
    dados = json.loads(OURO.read_text(encoding="utf-8"))
    assert chave in dados, f"cenário ausente no oráculo: {chave}"
    return _numeros(dados[chave])


def _numeros(v: Any) -> Any:
    if v == "Infinity":
        return math.inf
    if v == "-Infinity":
        return -math.inf
    if isinstance(v, list):
        return [_numeros(x) for x in v]
    if isinstance(v, dict):
        return {k: _numeros(x) for k, x in v.items()}
    if isinstance(v, str) and v in DIVERGENCIA_DA_PALAVRA_MESA:
        _TRADUZIDAS[v] += 1
        return DIVERGENCIA_DA_PALAVRA_MESA[v]
    return v


def _razoes(razoes: tuple[motor.Razao, ...]) -> list[dict[str, str]]:
    return [{"selo": r.selo, "txt": r.texto} for r in razoes]


def _motivo(m: motor.Motivo) -> dict[str, Any]:
    return {"razoes": _razoes(m.razoes), "peso": m.peso, "ganho": m.ganho,
            "forcado": m.forcado, "essencial": m.essencial}


def como_o_mockup_planeja(p: motor.Plano) -> dict[str, Any]:
    return {"plano": dict(p.plano), "motivo": {k: _motivo(v) for k, v in p.motivo.items()}}


def como_o_mockup_receita(movs: list[motor.Movimento]) -> list[dict[str, Any]]:
    return [{"titulo": m.titulo,
             "linhas": [{"s": ln.selo, "t": ln.texto} for ln in m.linhas],
             "essencial": m.essencial, "ganho": m.ganho, "semNumero": m.sem_numero}
            for m in movs]


def _receita_do_ouro(chave: str) -> list[dict[str, Any]]:
    return [{"titulo": m["titulo"],
             "linhas": [{"s": ln["s"], "t": ln["t"]} for ln in m["linhas"]],
             "essencial": bool(m.get("essencial", False)),
             "ganho": m.get("ganho", 0), "semNumero": bool(m.get("semNumero", False))}
            for m in ouro(chave)]


def _veredito(v: motor.Veredito | None) -> dict[str, str] | None:
    return None if v is None else {"v": v.v, "txt": v.texto, "porque": v.porque}


def _controles(p: motor.PlanoDosControles) -> dict[str, Any]:
    return {"ads": [{"id": a.id, "entrada": a.entrada, "rotulo": a.rotulo}
                    for a in p.adaptadores],
            "carga": dict(p.carga), "destino": dict(p.destino),
            "cabe": p.cabe, "sobra": p.sobra}


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está nesta máquina")
def test_o_ouro_ainda_e_o_que_o_mockup_diz_hoje() -> None:
    """O JSON gravado é o que o mockup de HOJE produz — não uma cópia velha."""
    saida = subprocess.run(
        [shutil.which("node") or "node", str(ORACULO)],
        capture_output=True, text=True, check=True, cwd=RAIZ, timeout=120,
    )
    assert json.loads(saida.stdout) == json.loads(OURO.read_text(encoding="utf-8"))


def test_as_traducoes_da_palavra_mesa_ainda_disparam() -> None:
    """Toda tradução declarada tem de ser USADA, e nenhuma pode sobrar."""
    ouro("julgar/3/bt")
    ouro("consequencias/so-pc")

    mortas = [frase for frase, vezes in _TRADUZIDAS.items() if vezes == 0]
    assert not mortas, (
        "tradução declarada que nunca disparou — o oráculo já não diz esta "
        f"frase, então APAGUE a entrada: {mortas}"
    )


def test_nenhuma_traducao_muda_mais_do_que_a_palavra() -> None:
    """Uma tradução só pode trocar a PALAVRA, nunca o que a frase diz."""
    for antes, depois in DIVERGENCIA_DA_PALAVRA_MESA.items():
        assert "mesa" in antes, f"tradução que não é sobre a palavra: {antes!r}"
        assert "mesa" not in depois, f"a tradução mantém a palavra: {depois!r}"
        assert antes.replace("mesa", "escrivaninha") == depois, (
            "a tradução mudou mais do que a palavra — o oráculo é o juiz do "
            f"resto da frase:\n  antes:  {antes!r}\n  depois: {depois!r}"
        )
