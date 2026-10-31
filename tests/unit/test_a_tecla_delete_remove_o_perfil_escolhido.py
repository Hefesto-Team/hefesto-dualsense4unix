"""A-ABA-PERFIS-SO-MOSTRA-O-JOGO-INSTALADO-01: o Delete sobre o perfil escolhido é o «Remover».

A tecla aciona o MESMO botão `data-hef-gesto="remover"`, logo a mesma pergunta (o armamento do
`a10_perfis.remover`) e as mesmas recusas. Dentro de um campo de texto, o Delete é do campo.

A MORDIDA: tire o ouvinte do `keydown` do Delete do `aba10.ROTEIRO`, regere o mockup, e a régua
reprova.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

RAIZ = Path(__file__).resolve().parents[2]

ESCUTAR = """
(function(){
  window.__remover = 0;
  var b = document.querySelector('[data-hef-gesto="remover"]');
  b.addEventListener('click', function(){ window.__remover += 1; }, true);
  return 'ok';
})()
"""


def _apertar(seletor: str) -> str:
    return (
        "(function(){"
        f"var alvo = document.querySelector({json.dumps(seletor)});"
        "if(alvo.focus) alvo.focus();"
        "var ev = new KeyboardEvent('keydown', {key: 'Delete', bubbles: true, cancelable: true});"
        "alvo.dispatchEvent(ev);"
        "return JSON.stringify([window.__remover, ev.defaultPrevented]);"
        "})()")


def _escolher(nome: str | None) -> str:
    return (
        "(function(){"
        "document.querySelectorAll('tr[data-hef-perfil]').forEach(function(tr){"
        f"tr.setAttribute('aria-selected', tr.dataset.hefPerfil === {json.dumps(nome)}"
        " ? 'true' : 'false');});"
        "return 'ok';})()")


@pytest.fixture()
def tela() -> Any:
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    pytest.importorskip("gi")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    t = regua_de_tela.Tela(onde.ENSAIO / "10-perfis.html", titulo_esperado="Hefesto")
    t.executar(ESCUTAR)
    yield t
    t.fechar()


def test_delete_com_perfil_escolhido_aciona_o_remover_duas_vezes_pergunta_e_confirma(
        tela: Any) -> None:
    tela.executar(_escolher("Elden Ring"))
    assert json.loads(tela.executar(_apertar("body"))) == [1, True]
    assert json.loads(tela.executar(_apertar("body"))) == [2, True]


def test_delete_dentro_do_campo_de_texto_e_do_campo(tela: Any) -> None:
    tela.executar(_escolher("Elden Ring"))
    assert json.loads(tela.executar(_apertar("input.procura"))) == [0, False]


def test_delete_sem_perfil_escolhido_nao_aciona_nada(tela: Any) -> None:
    tela.executar(_escolher(None))
    assert json.loads(tela.executar(_apertar("body"))) == [0, False]


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        self.chamadas.append(metodo)
        return True


def test_o_gesto_que_a_tecla_aciona_pergunta_antes_e_recusa_o_que_vale(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    save_profile(Profile(name="Pragmata", match=MatchAny(), priority=90))
    save_profile(Profile(name="Sackboy", match=MatchAny(), priority=80))
    ponte = _Ponte()

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Pragmata")
    ctx = Contexto(state={"active_profile": "Pragmata"}, mesa=[], conectados=[], estados={})
    with pytest.raises(RuntimeError):
        a10_perfis.remover(ctx, {}, ponte)
    assert load_profile("Pragmata").name == "Pragmata"

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Sackboy")
    with pytest.raises(RuntimeError, match="Apagar “Sackboy”"):
        a10_perfis.remover(ctx, {}, ponte)
    assert load_profile("Sackboy").name == "Sackboy"
    a10_perfis.remover(ctx, {}, ponte)
    with pytest.raises(FileNotFoundError):
        load_profile("Sackboy")
