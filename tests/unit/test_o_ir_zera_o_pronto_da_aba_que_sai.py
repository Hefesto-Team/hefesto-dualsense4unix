"""O `_ir` ZERA O `pronto` DA ABA QUE SAI — O-PILOTO-QUE-TROCA-DE-ABA-ZERA-O-PRONTO-DA-QUE-SAI-01.

Medido em 02/11/2026: o `pronto` da primeira aba seguia verdadeiro enquanto a aba pedida pelo `_ir`
carregava, e a régua da aba 09 lia o DOM no meio da navegação (página em branco, 2 em 3 corridas).
O piloto é o dono: o `_ir` zera o `pronto` antes do `load_uri`, e só a ponte instalada na aba
pedida o devolve.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

ABA_QUE_SAI = "01-jogar.html"
ABA_PEDIDA = "03-gatilhos.html"


@pytest.fixture
def hv(monkeypatch: pytest.MonkeyPatch) -> Any:
    pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    import hefesto_vivo

    monkeypatch.setattr(hefesto_vivo, "_soltar_as_ondas", lambda: None)
    monkeypatch.setattr(hefesto_vivo.pacotes, "largar_o_que_as_abas_seguram",
                        lambda *a, **k: None)
    return hefesto_vivo


def _piloto(hv: Any, *, pronto: bool) -> tuple[Any, list[str]]:
    carregou: list[str] = []
    view = SimpleNamespace(
        load_uri=carregou.append,
        get_uri=lambda: (hv.onde.pagina(ABA_QUE_SAI, publicado=True)).as_uri())
    piloto = object.__new__(hv.Piloto)
    piloto.view = view
    piloto.tela = SimpleNamespace(primeira_carga=False, _morrer=lambda m: None)
    piloto.ponte = SimpleNamespace(perguntar=lambda *a, **k: None)
    piloto._mesa_de_agora = []
    piloto.pronto = pronto
    piloto._trocando = False
    return piloto, carregou


def test_o_ir_zera_o_pronto_antes_de_carregar_a_aba_pedida(hv: Any) -> None:
    """A aba que sai estava pronta; a que entra ainda carrega: o piloto não está pronto."""
    piloto, carregou = _piloto(hv, pronto=True)
    visto: dict[str, bool] = {}
    original = piloto.view.load_uri

    def espiar(uri: str) -> None:
        visto["pronto_na_hora_de_carregar"] = piloto.pronto
        original(uri)

    piloto.view.load_uri = espiar
    piloto._ir(ABA_PEDIDA)
    assert carregou and carregou[0].endswith(ABA_PEDIDA)
    assert visto["pronto_na_hora_de_carregar"] is False
    assert piloto.pronto is False, "o pronto da aba que saiu seguiu valendo para a que carrega"


def test_o_instalado_atrasado_da_aba_que_saiu_nao_devolve_o_pronto(hv: Any) -> None:
    """A ponte instalada na aba que saiu responde depois do `_ir`: a carga ainda não terminou."""
    piloto, _ = _piloto(hv, pronto=True)
    piloto._ir(ABA_PEDIDA)
    piloto._instalado(None, None)
    assert piloto.pronto is False


def test_a_ponte_instalada_na_aba_pedida_devolve_o_pronto(
        hv: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O fim da carga solta a trava, e a ponte instalada na aba pedida devolve o `pronto`."""
    piloto, _ = _piloto(hv, pronto=True)
    piloto._ir(ABA_PEDIDA)
    piloto._trocando = False
    piloto._estado_vivo = SimpleNamespace(comecar=lambda: None)
    piloto.pagina = ABA_PEDIDA
    piloto.agendado = True
    piloto._tique = lambda: True
    monkeypatch.setattr(hv, "_esquecer_a_pintura", lambda *_a, **_k: None)
    monkeypatch.setattr(hv.pacotes, "a_aba_abriu", lambda *_a, **_k: None)
    piloto._instalado(None, None)
    assert piloto.pronto is True


def test_o_fim_da_carga_da_aba_pedida_devolve_o_pronto_pela_ponte_instalada(
        hv: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho inteiro: `_ir`, `_carregou` (o FINISHED da aba pedida) e a ponte da aba pedida.

    O `_instalado` da aba que saiu, atrasado, não devolve o `pronto`; o FINISHED solta a trava,
    e a ponte instalada na aba pedida o devolve. Sem soltar a trava no `_carregou`, o piloto
    ficaria sem `pronto` para sempre depois da primeira troca."""
    from gi.repository import WebKit2

    piloto, _ = _piloto(hv, pronto=True)
    perguntas: list[Any] = []
    piloto.ponte = SimpleNamespace(perguntar=lambda js, cb: perguntas.append(cb),
                                   rodar=lambda *_a: None)
    piloto.args = SimpleNamespace(oculta=True, prova_de_mockup=False)
    piloto.pagina = ABA_QUE_SAI
    piloto.visitadas = [ABA_QUE_SAI]
    piloto._estado_vivo = SimpleNamespace(comecar=lambda: None)
    piloto._tique = lambda: True
    monkeypatch.setattr(hv, "_esquecer_a_pintura", lambda *_a, **_k: None)
    monkeypatch.setattr(hv.pacotes, "a_aba_abriu", lambda *_a, **_k: None)

    piloto._ir(ABA_PEDIDA)
    piloto._instalado(None, None)
    assert piloto.pronto is False, "o `_instalado` atrasado da aba que saiu devolveu o pronto"
    piloto.view.get_uri = lambda: hv.onde.pagina(ABA_PEDIDA, publicado=True).as_uri()
    piloto._carregou(None, WebKit2.LoadEvent.FINISHED)
    assert piloto.pagina == ABA_PEDIDA
    assert piloto.pronto is False, "a aba pedida carregou, mas a ponte ainda não se instalou"
    instalado = perguntas[-1]
    instalado(None, None)
    assert piloto.pronto is True, "a ponte instalada na aba pedida não devolveu o pronto"
