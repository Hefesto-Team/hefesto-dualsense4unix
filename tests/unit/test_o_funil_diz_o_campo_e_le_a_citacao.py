"""O FUNIL DIZ O CAMPO, E O DIÁRIO É CITAÇÃO — O-FUNIL-DIZ-O-CAMPO-E-O-DIARIO-E-CITACAO-01."""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(INTERFACE))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK e o WebKit")

import hefesto_vivo as hv

from hefesto_dualsense4unix.interface import frases_que_ela_baniu as fb
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

PAGINA = "09-sistema.html"
CAMPO = a09.REGISTRO

FIXTURE = RAIZ / "tests/fixtures/state_full_quatro_controles.json"

STATUS = ("● hefesto-dualsense4unix.service - Hefesto\n"
          "     Loaded: loaded\n"
          "     Active: active (running)")


def _diario_sintetico(modo: str) -> str:
    """As linhas que o daemon escreve, nos dois modos e para os quatro controles.

    No modo DualSense o pad é uhid, e o diário tem `mac=` e `uniq=`; no Xbox o
    pad é uinput, não há `mac=`, e a palavra que o funil acusaria é `uniq` (e o
    `uinput` do backend).
    """
    linhas = []
    for n, via in ((1, "usb"), (2, "usb"), (3, "bt"), (4, "bt")):
        endereco = f"aa:bb:cc:00:00:0{n}"
        linhas.append(f"backend_conectado uniq={endereco} transport={via} player={n}")
        if modo == "dualsense":
            linhas.append(f"uhid_device_created mac={endereco} transport={via}")
        else:
            linhas.append(f"gamepad_emulado backend=uinput uniq={endereco} modo=xbox")
    return "\n".join(linhas)


@pytest.fixture
def limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A memória do funil e o registro das citações nascem vazios em cada régua."""
    monkeypatch.setattr(hv, "_TEXTOS_LIDOS_PELO_FUNIL", {})
    monkeypatch.setattr(hv, "_BANIDAS_JA_DENUNCIADAS", set())
    monkeypatch.setattr(fb, "_CITADOS", {})


@pytest.fixture
def servico(monkeypatch: pytest.MonkeyPatch, limpo: None) -> dict[str, Any]:
    """O `journalctl` e o `systemctl` de mentira. Qualquer outro comando reprova."""
    estado: dict[str, Any] = {"modo": "dualsense", "comandos": []}

    def run(argv: Any, *a: Any, **k: Any) -> Any:
        estado["comandos"].append(list(argv))
        if not argv or argv[0] != "journalctl":
            raise AssertionError(f"a régua chamou um comando de verdade: {argv}")
        return SimpleNamespace(stdout=_diario_sintetico(estado["modo"]) + "\n",
                               stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(a09, "_matriz", lambda: SimpleNamespace(
        _systemctl_status_text=lambda unidade: STATUS))
    return estado


def _estado() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _painel() -> str:
    return a09._repouso_do_painel(_estado())


@pytest.mark.parametrize("modo", ["dualsense", "xbox"])
def test_o_diario_citado_nao_denuncia(servico: dict[str, Any], modo: str,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    """O painel inteiro passa pelo funil sem `[texto banido]`.

    A MORDIDA: tire o `citar(` do `a09_sistema._diario` e `'MAC'` (no modo
    DualSense) ou `'uinput'` (no Xbox) volta ao diário da janela.
    """
    servico["modo"] = modo
    painel = _painel()
    assert "Registro do serviço" in painel and "uniq=aa:bb:cc" in painel, painel
    hv._json({"mesa": {CAMPO: painel}}, pagina=PAGINA)
    erro = capsys.readouterr().err
    assert "[texto banido]" not in erro, erro
    assert [c[0] for c in servico["comandos"]] == ["journalctl"]


def test_a_frase_do_produto_no_mesmo_campo_continua_lida(
        servico: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Uma resposta de gesto com `uinput`, fora do citado, é denunciada."""
    diario = a09._diario()
    painel = "O gesto mexeu no uinput do controle.\n\nRegistro do serviço\n" + diario
    hv._json({"mesa": {CAMPO: painel}}, pagina=PAGINA)
    erro = capsys.readouterr().err
    assert f"[texto banido] 'uinput' em {PAGINA} · {CAMPO}" in erro, erro
    assert "'MAC'" not in erro and "'uniq'" not in erro, erro


def test_a_denuncia_diz_a_pagina_e_o_campo(
        limpo: None, capsys: pytest.CaptureFixture[str]) -> None:
    """`[texto banido] 'hidraw' em 02-controles.html · aviso-texto`."""
    hv._json({"colunas": {"p1": {"aviso-texto": ["o hidraw caiu"]}}},
             pagina="02-controles.html")
    erro = capsys.readouterr().err
    assert "[texto banido] 'hidraw' em 02-controles.html · aviso-texto" in erro, erro


def test_dois_trechos_no_mesmo_valor_saem_os_dois(
        limpo: None, capsys: pytest.CaptureFixture[str]) -> None:
    """`MAC` vem antes de `uniq` na lista, e não o esconde mais."""
    hv._json({"mesa": {"aviso": "o MAC e o uniq do controle"}}, pagina=PAGINA)
    erro = capsys.readouterr().err
    assert f"'MAC' em {PAGINA} · aviso" in erro, erro
    assert f"'uniq' em {PAGINA} · aviso" in erro, erro


def test_dois_donos_da_mesma_palavra_saem_os_dois(
        limpo: None, capsys: pytest.CaptureFixture[str]) -> None:
    """`'MAC'` no campo A e depois no B: duas linhas; o mesmo dono de novo: nada."""
    hv._json({"mesa": {"a": "o MAC do controle"}}, pagina=PAGINA)
    hv._json({"mesa": {"b": "outro MAC"}}, pagina=PAGINA)
    hv._json({"mesa": {"b": "outro MAC, de novo"}}, pagina=PAGINA)
    erro = capsys.readouterr().err
    assert f"'MAC' em {PAGINA} · a" in erro, erro
    assert f"'MAC' em {PAGINA} · b" in erro, erro
    assert erro.count("[texto banido]") == 2, erro


def test_a_citacao_nao_muda_um_byte(servico: dict[str, Any],
                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """O painel, o JSON e o «Copiar» saem iguais com e sem a marca."""
    marcado = _painel()
    carga = {"mesa": {CAMPO: marcado}}
    assert hv._json(carga, pagina=PAGINA) == json.dumps(
        carga, ensure_ascii=False, default=str)

    copiado: list[str] = []
    monkeypatch.setattr(a09, "_por_na_area_de_transferencia",
                        lambda texto: copiado.append(texto) or True)
    monkeypatch.setattr(a09, "_faixa_lenta", lambda *a, **k: (
        None, None, None, None, _painel()))
    monkeypatch.setattr(a09, "_PAINEL", [None])
    ctx = Contexto(state=_estado(), mesa=[], conectados=[], estados={})
    a09.copiar_registro(ctx, {}, None)

    monkeypatch.setattr(fb, "citar", lambda texto: texto)
    sem_marca = _painel()
    assert marcado == sem_marca
    a09.copiar_registro(ctx, {}, None)
    assert len(copiado) == 2 and copiado[0] == copiado[1], copiado


def test_as_frases_do_produto_no_diario_nao_sao_citacao(
        servico: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """«…está vazio.» é frase do produto: fica fora do registro das citações."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout="", stderr="", returncode=0))
    vazio = a09._diario()
    assert vazio.endswith("está vazio."), vazio
    assert vazio not in fb.citados()


def test_todo_chamador_do_piloto_passa_a_pagina() -> None:
    """Por AST: toda chamada de `_json` dentro de `class Piloto` leva a página (`pagina=`)."""
    arvore = ast.parse((INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8"))
    piloto = next(no for no in arvore.body
                  if isinstance(no, ast.ClassDef) and no.name == "Piloto")
    chamadas = [no for no in ast.walk(piloto)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id == "_json"]
    assert len(chamadas) >= 7, f"o Piloto chama `_json` {len(chamadas)} vezes"
    argumento = "pagina"  # (noqa-acento) nome do argumento do `_json`
    sem_pagina = [no.lineno for no in chamadas
                  if not any(k.arg == argumento for k in no.keywords)]
    assert sem_pagina == [], (
        f"chamadas de `_json` sem a página nas linhas {sem_pagina}: a denúncia "
        "dali sai sem dizer de onde veio")


def test_o_funil_sem_pagina_continua_devolvendo_o_mesmo_json(limpo: None) -> None:
    """O contrato com a A-JANELA: `_json(carga)` com um argumento só, igual."""
    carga = {"mesa": {"a": "é", "b": [1, None, "x"]}, "fita": ""}
    assert hv._json(carga) == json.dumps(carga, ensure_ascii=False, default=str)
