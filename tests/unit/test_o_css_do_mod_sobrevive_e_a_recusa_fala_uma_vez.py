"""O CSS de quem usa sobrevive à remoção, e a recusa fala uma vez só
(O-CSS-DO-MOD-SOBREVIVE-A-REMOCAO-E-A-RECUSA-FALA-UMA-VEZ-01).

Medido em 23/10/2026 (D-2210-O-CSS-DE-QUEM-USA-ENTRA-POR-CIMA-DO-TEMA): o ``meu.css`` recusava
``@container`` e ``@layer`` («usa @container, que o Hefesto não aplica»); o ``mod remover`` apagava
``<dados>/<id>`` inteiro, e com ele o CSS que a pessoa escreveu; e três eventos do vigia sobre o
mesmo arquivo recusado punham seis linhas ``[tema]`` no diário (a recusa do tema e a do CSS, a
cada evento). Agora os dois agrupam como ``@media``, a remoção deixa o ``meu.css`` (reinstalar o
encontra), e cada leitor lembra a última frase e só a diz quando ela muda.

Tudo em lugares de mentira no ``tmp_path``; a sonda abre uma ``PonteDaTela`` de verdade na tela
de mentira, para provar que o WebKit pinta o que a régua deixa passar.

MORDIDAS (23/10/2026, executadas sobre a cura e devolvidas, md5 conferido):
- ``_AGRUPAM`` só com os dois de antes reprova ``test_container_e_layer_com_bloco_...``
  e a sonda;
- ``_apagar_os_dados`` de volta ao ``rmtree`` inteiro reprova ``test_remover_deixa_o_meu_css...``,
  ``test_reinstalar_encontra_o_mesmo_meu_css``, ``test_a_frase_do_mod_remover_...`` e, ao lado,
  ``test_as_modificacoes_rodam_fora_do_daemon.py::test_remover_para_o_processo_...``;
- ``_dizer_uma_vez`` sem a memória (sempre imprime) reprova os três testes do diário.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador, meu_css
from hefesto_dualsense4unix.mods import tema as tm

TEMA_CLARO = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
              "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486;"
              "--fundo-da-pagina:#dde1ea;--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;"
              "--orange:#a35200;--pink:#ad2f6c;--red:#c01f2e;--yellow:#7a6400}")
MANIFESTO = {"id": "tema-z", "nome": "Tema Z", "api": ">=2,<3", "licenca": "MIT",
             "versao": "1.0.0",  # (noqa-acento): chave
             "tipos": ["tema"], "tema": {"arquivo": "tema.css"},
             "permissoes": ["tema"],  # (noqa-acento): chave
             "opcoes": [{"id": "meu_css",  # (noqa-acento): chave
                         "rotulo": "Usar o meu CSS", "tipo": "css",
                         "padrao": False}]}  # (noqa-acento): chave
ESCRITO = "/* o meu */\n.a{color:red}\n"


@pytest.fixture
def lg(tmp_path: Path) -> instalador.Lugares:
    return instalador.Lugares(codigo=tmp_path / "codigo",  # (noqa-acento): argumento
                              dados=tmp_path / "dados",
                              registro=tmp_path / "mods.json", estado=tmp_path / "estado.json")


def _fonte(tmp_path: Path) -> Path:
    pasta = tmp_path / "fonte" / "tema-z"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tema.css").write_text(TEMA_CLARO, encoding="utf-8")
    (pasta / "hefesto-mod.json").write_text(json.dumps(MANIFESTO), encoding="utf-8")
    return pasta


def _instalada_com_o_css(lg: instalador.Lugares, tmp_path: Path) -> Path:
    instalador.instalar(str(_fonte(tmp_path)), lugares=lg)
    alvo = meu_css.garantir("tema-z", lg)
    alvo.write_text(ESCRITO, encoding="utf-8")
    (lg.dados / "tema-z" / "opcoes.json").write_text('{"meu_css": true}', encoding="utf-8")
    (lg.dados / "tema-z" / "cache").mkdir()
    (lg.dados / "tema-z" / "cache" / "x.bin").write_bytes(b"x")
    return alvo


# --- as at-rules que agrupam --------------------------------------------------------------


@pytest.mark.parametrize(("texto", "saida"), [
    ("@container (min-width: 1px) { .x { color: red } }",
     "@container (min-width: 1px){.x{color:red !important;}}"),
    ("@container cartao (min-width: 300px){.x{width:10px}}",
     "@container cartao (min-width: 300px){.x{width:10px !important;}}"),
    ("@layer base { .x { color: red } }", "@layer base{.x{color:red !important;}}"),
    ("@layer { .x { margin: 0 } }", "@layer{.x{margin:0 !important;}}"),
    (".a{color:red;@container (min-width:1px){color:blue}}",
     ".a{color:red !important;@container (min-width:1px){color:blue !important;}}"),
])
def test_container_e_layer_com_bloco_agrupam_como_media(texto: str, saida: str) -> None:
    assert meu_css.aplicar(texto) == saida


@pytest.mark.parametrize(("texto", "frase", "curta"), [
    ("@import 'x.css';", "a linha 1 usa @import", "Linha 1: @import"),
    ("\n@layer a, b;", "a linha 2 tem «@layer a, b», e fora de uma regra",
     "Linha 2: fora de regra"),
    (".a{color:red}\n@layer base;", "a linha 2 tem «@layer base»", "Linha 2: fora de regra"),
    ("@font-face{font-family:x}", "a linha 1 usa @font-face", "Linha 1: @font-face"),
])
def test_import_e_layer_sem_bloco_seguem_recusados_com_o_motivo(
        texto: str, frase: str, curta: str) -> None:
    with pytest.raises(meu_css.CssRecusadoError) as erro:
        meu_css.aplicar(texto)
    assert frase in erro.value.frase and erro.value.curta == curta


# --- a remoção: o meu.css é da pessoa -----------------------------------------------------


def test_remover_deixa_o_meu_css_e_apaga_o_resto(lg: instalador.Lugares, tmp_path: Path) -> None:
    alvo = _instalada_com_o_css(lg, tmp_path)
    assert instalador.remover("tema-z", lugares=lg, prazo=0.1) == []
    assert alvo.read_text(encoding="utf-8") == ESCRITO, "a remoção apagou o CSS da pessoa"
    assert sorted(p.name for p in (lg.dados / "tema-z").iterdir()) == ["meu.css"]
    assert not (lg.codigo / "tema-z").exists()
    assert "tema-z" not in instalador.ler_registro(lg.registro)
    assert instalador.conferir_remocao("tema-z", lugares=lg) == []
    assert instalador.o_css_que_fica("tema-z", lugares=lg) == alvo
    with pytest.raises(instalador.InstalacaoRecusadaError, match="não está instalada"):
        instalador.remover("tema-z", lugares=lg, prazo=0.1)


def test_sem_meu_css_a_pasta_dos_dados_sai_inteira(lg: instalador.Lugares, tmp_path: Path) -> None:
    instalador.instalar(str(_fonte(tmp_path)), lugares=lg)
    (lg.dados / "tema-z").mkdir(parents=True, exist_ok=True)
    (lg.dados / "tema-z" / "opcoes.json").write_text("{}", encoding="utf-8")
    assert instalador.remover("tema-z", lugares=lg, prazo=0.1) == []
    assert not (lg.dados / "tema-z").exists()
    assert instalador.o_css_que_fica("tema-z", lugares=lg) is None


def test_o_que_sobra_alem_do_meu_css_ainda_e_resto(
        lg: instalador.Lugares, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _instalada_com_o_css(lg, tmp_path)
    monkeypatch.setattr(instalador, "_apagar_os_dados", lambda lg, mod_id: None)
    assert instalador.remover("tema-z", lugares=lg, prazo=0.1) == [str(lg.dados / "tema-z")]


def test_reinstalar_encontra_o_mesmo_meu_css(lg: instalador.Lugares, tmp_path: Path) -> None:
    alvo = _instalada_com_o_css(lg, tmp_path)
    assert instalador.remover("tema-z", lugares=lg, prazo=0.1) == []
    instalador.instalar(str(_fonte(tmp_path)), lugares=lg)
    assert meu_css.garantir("tema-z", lg) == alvo
    assert alvo.read_text(encoding="utf-8") == ESCRITO, "reinstalar não achou o CSS da pessoa"
    assert meu_css.ler("tema-z", lg).folha == ".a{color:red !important;}"


def test_a_frase_do_mod_remover_diz_onde_o_css_ficou(
        lg: instalador.Lugares, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from hefesto_dualsense4unix.cli import cmd_mod

    monkeypatch.setattr(instalador.Lugares, "do_xdg", classmethod(lambda cls: lg))
    monkeypatch.setenv("COLUMNS", "400")
    alvo = _instalada_com_o_css(lg, tmp_path)
    saida = CliRunner().invoke(cmd_mod.app, ["remover", "tema-z"])
    assert saida.exit_code == 0, saida.output
    frase = " ".join(saida.output.split())
    assert f"O seu CSS ficou em {alvo}" in frase, frase
    instalador.instalar(str(_fonte(tmp_path)), lugares=lg)
    alvo.unlink()
    saida = CliRunner().invoke(cmd_mod.app, ["remover", "tema-z"])
    assert saida.exit_code == 0 and "CSS" not in saida.output, saida.output


# --- o diário: a recusa fala uma vez ------------------------------------------------------


def _janela(monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa a `interface.janela`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import janela

    monkeypatch.setattr(janela, "_DITO", {})
    return janela


def _eventos(janela: Any, casa: tm.TemaDaCasa, monkeypatch: pytest.MonkeyPatch,
             vezes: int) -> list[tuple[str, str]]:
    monkeypatch.setattr(tm, "tema_da_casa", lambda lugares=None: casa)
    trocas: list[tuple[str, str]] = []
    falsa = SimpleNamespace(ponte=SimpleNamespace(tema_de_cores="", meu_css=""),
                            trocar_o_tema=lambda folha, meu: trocas.append((folha, meu)))
    for _ in range(vezes):
        janela.JanelaDaAba._o_registro_das_extensoes_mudou(falsa)
    return trocas


def _linhas(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return [linha for linha in capsys.readouterr().err.splitlines() if linha.startswith("[tema]")]


RECUSA = ("«Tema Z»: O seu CSS não foi aplicado: a linha 2 usa url(), e nada busca arquivo nem "
          "endereço.")
OUTRA = "«Tema Z»: O seu CSS não foi aplicado: a linha 5 tem uma chave sem seletor antes."


def test_tres_eventos_do_vigia_sobre_o_mesmo_recusado_dizem_uma_linha(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    janela = _janela(monkeypatch)
    capsys.readouterr()
    _eventos(janela, tm.TemaDaCasa(folha=":root{--fg:#fff}", recusa_do_css=RECUSA),
             monkeypatch, 3)
    assert _linhas(capsys) == [f"[tema] {RECUSA}"]


def test_a_recusa_que_muda_volta_a_ser_dita_e_a_que_some_e_esquecida(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    janela = _janela(monkeypatch)
    capsys.readouterr()
    _eventos(janela, tm.TemaDaCasa(recusa_do_css=RECUSA), monkeypatch, 2)
    _eventos(janela, tm.TemaDaCasa(recusa_do_css=OUTRA), monkeypatch, 2)
    _eventos(janela, tm.TemaDaCasa(css=".a{color:red !important;}"), monkeypatch, 2)
    _eventos(janela, tm.TemaDaCasa(recusa_do_css=RECUSA), monkeypatch, 2)
    assert _linhas(capsys) == [f"[tema] {RECUSA}", f"[tema] {OUTRA}", f"[tema] {RECUSA}"]


def test_a_recusa_do_tema_e_os_avisos_tambem_falam_uma_vez(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    janela = _janela(monkeypatch)
    capsys.readouterr()
    casa = tm.TemaDaCasa(recusa="O tema de «X» não ligou.", avisos=("«Y» também tem tema.",),
                         recusa_do_css=RECUSA)
    _eventos(janela, casa, monkeypatch, 3)
    assert _linhas(capsys) == ["[tema] O tema de «X» não ligou.", "[tema] «Y» também tem tema.",
                               f"[tema] {RECUSA}"]


def test_a_folha_que_muda_ainda_troca_o_tema(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Calar a frase não cala a troca: a folha diferente da que está na ponte troca sempre."""
    janela = _janela(monkeypatch)
    trocas = _eventos(janela, tm.TemaDaCasa(folha=":root{--fg:#fff}", recusa_do_css=RECUSA),
                      monkeypatch, 3)
    assert trocas == [(":root{--fg:#fff}", "")] * 3


# --- o WebKit pinta o que a régua deixa passar --------------------------------------------

_SONDA = r"""
import json
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PonteDaTela
from hefesto_dualsense4unix.mods import meu_css

try:
    MEU = meu_css.aplicar(
        "#caixa{container-type:inline-size}"
        "@container (min-width: 1px){#dentro{width:150px}}"
        "@layer base{#outra{width:120px}}")
except meu_css.CssRecusadoError as exc:
    print(json.dumps({"recusa": exc.frase, "lido": None}))
    raise SystemExit(0)
PAGINA = ("<html><head><style>#caixa{width:300px}#dentro,#outra{width:10px;height:10px}"
          "</style></head><body><div id='caixa'><div id='dentro'></div></div>"
          "<div id='outra'></div></body></html>")
ponte = PonteDaTela(folha=None, tema_de_cores="", meu_css=MEU)
janela = Gtk.OffscreenWindow()
janela.set_default_size(400, 200)
janela.add(ponte.view)
janela.show_all()
ponte.view.load_html(PAGINA, "file:///sonda/")

def ler():
    caixa = {}
    ponte.perguntar(
        "JSON.stringify([document.getElementById('dentro').offsetWidth,"
        "document.getElementById('outra').offsetWidth])",
        lambda valor, erro: caixa.update(valor=valor))
    fim = GLib.get_monotonic_time() + 5_000_000
    while "valor" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)
    return json.loads(caixa.get("valor") or "[null, null]")

lido = [None, None]
for _ in range(60):
    lido = ler()
    if lido == [150, 120]:
        break
    fim = GLib.get_monotonic_time() + 50_000
    while GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)
print(json.dumps({"meu": MEU, "lido": lido}))
"""


def test_o_webkit_pinta_o_container_e_o_layer_do_meu_css() -> None:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a PonteDaTela, que carrega o GTK")
    filho = subprocess.run([sys.executable, "-c", _SONDA], env=dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True, timeout=180)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    saida = json.loads(filho.stdout.strip().splitlines()[-1])
    assert saida["lido"] == [150, 120], f"o WebKit não aplicou o @container/@layer: {saida}"
