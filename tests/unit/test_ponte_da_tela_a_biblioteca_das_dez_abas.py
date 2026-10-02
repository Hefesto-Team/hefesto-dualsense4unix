"""A BIBLIOTECA DAS DEZ ABAS: a janela, as duas pontes e a guarda de carga."""
from __future__ import annotations

import ast
import os
import pathlib
import time
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("PONTE-DA-TELA-01 — a biblioteca das dez abas")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "janela.py"

if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
    pytest.skip(
        "PONTE-DA-TELA-01: sem servidor gráfico. `Gtk.OffscreenWindow` ainda "
        "precisa de um GDK display — sem ele não há WebView para medir.",
        allow_module_level=True,
    )

try:
    from hefesto_dualsense4unix.interface import janela as ponte_da_tela
except (ImportError, ValueError) as _erro:  # pragma: no cover — sem WebKit
    pytest.skip(
        f"PONTE-DA-TELA-01: a biblioteca não importou ({_erro}). Falta "
        "gir1.2-webkit2-4.1?",
        allow_module_level=True,
    )

from gi.repository import GLib

TITULO = "Hefesto — PÁGINA DE PROVA"

def _interpolacao_crua(valor: object) -> str:
    return "'" + str(valor) + "'"


VENENO = "O'Neill \"Midnight\" </script> \\ \u2028 \u2029 fim"

PAGINA = """<!doctype html>
<html><head><meta charset="utf-8"><title>{titulo}</title></head>
<body>
<p class="nota">um bilhete de projeto, que não é produto</p>
<select id="uma-caixa"><option>um</option></select>
<div id="alvo"></div>
<script>
window.PROVA = {{
  posto: function(v){{ document.getElementById('alvo').textContent = v.texto; }},
  direto: function(s){{ document.getElementById('alvo').textContent = s; }},
  guardar: function(o){{ window.RECEBIDO = o; }},
  mandar: function(bruto){{ window.webkit.messageHandlers.hefesto.postMessage(bruto); }}
}};
</script>
</body></html>
"""


def bombear(ate: Any, prazo: float = 10.0) -> bool:
    """Roda o laço GLib até `ate()` virar verdade, ou até o prazo. Devolve se deu."""
    contexto = GLib.MainContext.default()
    fim = time.monotonic() + prazo
    while True:
        while contexto.pending():
            contexto.iteration(False)
        if ate():
            return True
        if time.monotonic() >= fim:
            return False
        time.sleep(0.004)


class Banca:
    """Uma :class:`JanelaDaAba` aberta sobre uma página de três linhas, e o que"""

    def __init__(self, pagina: pathlib.Path, **kwargs: Any) -> None:
        self.carregou = 0
        self.falhou: list[str] = []
        self.saiu: list[str] = []
        self.recebidos: list[dict[str, Any]] = []
        self.janela = ponte_da_tela.JanelaDaAba(
            arquivo=pagina,
            titulo_esperado=kwargs.pop("titulo_esperado", TITULO),
            ao_carregar=self._carregou,
            ao_receber=self.recebidos.append,
            ao_sair_da_aba=self.saiu.append,
            ao_falhar=self.falhou.append,
            oculta=True,
            **kwargs,
        )

    def _carregou(self) -> None:
        self.carregou += 1

    def esperar_a_carga(self, prazo: float = 10.0) -> None:
        assert bombear(lambda: self.carregou or self.falhou, prazo), (
            "a página não confirmou nem falhou dentro do prazo — a guarda de "
            "carga ficou muda, que é o pior dos três estados"
        )

    def ler(self, expressao: str, prazo: float = 5.0) -> Any:
        """Pergunta à página e devolve a resposta como texto."""
        caixa: dict[str, Any] = {}

        def veio(valor: str | None, erro: Exception | None) -> None:
            caixa["v"], caixa["e"] = valor, erro

        self.janela.ponte.perguntar(expressao, veio)
        assert bombear(lambda: bool(caixa), prazo), f"a página não respondeu: {expressao}"
        assert caixa["e"] is None, f"o JavaScript levantou: {caixa['e']}"
        return caixa["v"]

    def fechar(self) -> None:
        self.janela.janela.destroy()
        bombear(lambda: False, 0.05)


@pytest.fixture
def pagina(tmp_path: pathlib.Path) -> pathlib.Path:
    alvo = tmp_path / "prova.html"
    alvo.write_text(PAGINA.format(titulo=TITULO), encoding="utf-8")
    return alvo


@pytest.fixture
def banca(pagina: pathlib.Path) -> Any:
    b = Banca(pagina)
    b.esperar_a_carga()
    yield b
    b.fechar()


def _arvore() -> ast.Module:
    return ast.parse(FONTE.read_text(encoding="utf-8"))


def test_os_quatro_pinos_e_o_gdk_depois_do_gtk() -> None:
    """Os quatro `gi.require_version`, na ordem, num lugar só."""
    pinos = [
        (no.args[0].value, no.args[1].value)
        for no in ast.walk(_arvore())
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "require_version"
        and len(no.args) == 2
        and all(isinstance(a, ast.Constant) for a in no.args)
    ]
    assert pinos == [
        ("Gtk", "3.0"),
        ("Gdk", "3.0"),
        ("GdkPixbuf", "2.0"),
        ("WebKit2", "4.1"),
    ], (
        "os quatro pinos, nesta ordem, com o Gdk DEPOIS do Gtk. O que se leu "
        f"foi {pinos}"
    )


def test_o_handler_da_4_1_leva_um_argumento() -> None:
    """Na série 4.1 `register_script_message_handler` leva UM argumento."""
    chamadas = [
        no
        for no in ast.walk(_arvore())
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "register_script_message_handler"
    ]
    assert chamadas, "a ponte tela → Python sumiu do arquivo"
    for chamada in chamadas:
        assert len(chamada.args) == 1 and not chamada.keywords, (
            "a série 4.1 leva UM argumento; a forma da 6.0 (dois) faz o gesto "
            f"sumir calado. Esta chamada leva {len(chamada.args)}"
        )


def test_as_quatro_armadilhas_estao_escritas_em_codigo() -> None:
    """O conhecimento pago viaja com o módulo, não numa página que ninguém abre."""
    armadilhas = ponte_da_tela.AS_QUATRO_ARMADILHAS
    assert len(armadilhas) == 4, f"são quatro, e vieram {len(armadilhas)}"
    inteiro = " ".join(armadilhas)
    for palavra in ("FINISHED", "get_title", "Promise", "4.1"):
        assert palavra in inteiro, f"a armadilha de {palavra!r} não está escrita"


def test_o_valor_atravessa_como_dado_nunca_como_texto(banca: Banca) -> None:
    """O apóstrofo, a aspa, `</script>`, a barra e o U+2028 chegam inteiros."""
    banca.janela.ponte.dizer("PROVA.direto", VENENO)
    assert bombear(
        lambda: banca.ler("document.getElementById('alvo').textContent") == VENENO
    ), "a página parou de responder depois da pintura"
    chegou = banca.ler("document.getElementById('alvo').textContent")
    assert chegou == VENENO, (
        "o que chegou ao DOM não é o que saiu do Python — o valor foi "
        f"interpolado em vez de serializado. Veio {chegou!r}"
    )


def test_a_mordida_do_literal_a_interpolacao_crua_quebra_a_pintura(
    banca: Banca, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA, aplicada aqui dentro: sem o JSON, o valor não chega."""
    monkeypatch.setattr(ponte_da_tela, "literal_js", _interpolacao_crua)
    banca.janela.ponte.dizer("PROVA.direto", VENENO)
    bombear(lambda: False, 0.3)
    chegou = banca.ler("document.getElementById('alvo').textContent")
    assert chegou != VENENO, (
        "com `literal_js` arrancado o veneno CHEGOU inteiro — então o JSON não "
        "estava segurando nada, e esta régua não mede o que promete"
    )


def test_uma_chamada_por_tique_nao_por_valor(banca: Banca) -> None:
    """Vinte e nove valores custam UMA travessia de fronteira, não 29."""
    pacote = {"texto": "x", **{f"v{i}": i for i in range(29)}}
    antes = banca.janela.ponte.chamadas
    banca.janela.ponte.dizer("PROVA.guardar", pacote)
    gastou = banca.janela.ponte.chamadas - antes
    assert gastou == 1, (
        "um pacote inteiro tem de custar UMA chamada. Com 29 valores por "
        f"controle e quatro controles, uma por valor seriam 1.160 por segundo "
        f"— esta gastou {gastou}"
    )
    assert bombear(lambda: banca.ler("String(Object.keys(window.RECEBIDO||{}).length)") == "30"), (
        "a chamada única não levou o pacote inteiro: o que chegou à página foi "
        + str(banca.ler("String(Object.keys(window.RECEBIDO||{}).length)"))
        + " chave(s) de 30"
    )


def test_o_gesto_bem_formado_chega_inteiro(banca: Banca) -> None:
    banca.janela.ponte.rodar("""PROVA.mandar(JSON.stringify({gesto:'mudo', bloco:"O'Neill"}))""")
    assert bombear(lambda: banca.recebidos), "o gesto não chegou ao Python"
    assert banca.recebidos == [{"gesto": "mudo", "bloco": "O'Neill"}]
    assert banca.janela.ponte.recusas == []


@pytest.mark.parametrize(
    ("carga", "pedaco_do_motivo"),
    [
        ("'{'", "não é JSON"),
        ("'[]'", "não é objeto"),
        ("'3'", "não é objeto"),
        ("'null'", "não é objeto"),
    ],
)
def test_o_gesto_malformado_e_recusado_com_motivo(
    banca: Banca, carga: str, pedaco_do_motivo: str
) -> None:
    """Nunca engolido. O piloto original fazia `except Exception: return`."""
    banca.janela.ponte.rodar(f"PROVA.mandar({carga})")
    assert bombear(lambda: banca.janela.ponte.recusas), (
        f"{carga} atravessou sem recusa — a ponte engoliu a mensagem, que é o "
        "silêncio lido como sucesso"
    )
    motivo, bruto = banca.janela.ponte.recusas[0]
    assert pedaco_do_motivo in motivo, f"o motivo não diz o que houve: {motivo!r}"
    assert bruto, "a recusa tem de carregar o texto cru que veio"
    assert banca.recebidos == [], "uma mensagem recusada não pode chegar a quem chama"


def test_a_guarda_mata_a_primeira_carga_errada(tmp_path: pathlib.Path) -> None:
    """`FINISHED` mente; quem confirma a carga é a PÁGINA."""
    outra = tmp_path / "outra.html"
    outra.write_text(PAGINA.format(titulo="uma página qualquer"), encoding="utf-8")
    b = Banca(outra)
    b.esperar_a_carga()
    try:
        assert b.carregou == 0, "a guarda aceitou uma página que não é a aba"
        assert b.falhou, "a guarda não disse nada sobre a página errada"
        assert "OUTRA página" in b.falhou[0]
    finally:
        b.fechar()


def test_a_guarda_nao_mata_quando_ela_clica_na_tira(
    banca: Banca, tmp_path: pathlib.Path
) -> None:
    """O defeito de 29/08: a janela dela fechou sozinha em ~12 s."""
    vizinha = tmp_path / "vizinha.html"
    vizinha.write_text(PAGINA.format(titulo="Hefesto — aba CONEXÕES"), encoding="utf-8")
    assert banca.carregou == 1 and banca.janela.na_aba

    banca.janela.view.load_uri(vizinha.as_uri())
    assert bombear(lambda: banca.saiu or banca.falhou), "a navegação não produziu notícia"

    assert not banca.falhou, (
        "a guarda MATOU a janela por causa de uma navegação legítima — é o "
        f"defeito de 29/08 de volta: {banca.falhou}"
    )
    assert banca.saiu == ["Hefesto — aba CONEXÕES"], (
        "sair da aba tem de avisar QUEM entrou, para a pintura pausar"
    )
    assert banca.janela.na_aba is False
    assert banca.janela.janela.get_visible(), "a janela morreu numa navegação legítima"


def test_voltar_para_a_aba_religa_a_pintura(banca: Banca, pagina: pathlib.Path) -> None:
    """Ida e volta pela tira: a janela sobrevive e `ao_carregar` é chamado de novo."""
    vizinha = pagina.parent / "vizinha2.html"
    vizinha.write_text(PAGINA.format(titulo="Hefesto — aba SISTEMA"), encoding="utf-8")
    banca.janela.view.load_uri(vizinha.as_uri())
    assert bombear(lambda: bool(banca.saiu))
    banca.janela.view.load_uri(pagina.as_uri())
    assert bombear(lambda: banca.carregou == 2), (
        "voltar para a aba tem de religar a pintura — sem isso a tela dela fica "
        "parada depois de um passeio pela tira"
    )
    assert not banca.falhou
    assert banca.janela.na_aba is True


def test_a_folha_da_casa_esconde_a_nota_e_desenha_o_select(banca: Banca) -> None:
    """`.nota{display:none}` e `select{appearance:none}` chegam na página."""
    assert banca.ler("getComputedStyle(document.querySelector('.nota')).display") == "none"
    assert banca.ler("getComputedStyle(document.getElementById('uma-caixa')).appearance") == "none"


def test_a_mordida_da_folha_sem_ela_o_select_volta_ao_tema_do_sistema(
    pagina: pathlib.Path,
) -> None:
    """A MORDIDA da folha: sem ela, os dois valores mudam."""
    b = Banca(pagina, folha=None)
    b.esperar_a_carga()
    try:
        assert b.ler("getComputedStyle(document.querySelector('.nota')).display") != "none", (
            "sem a folha, o bilhete de projeto continuou escondido — então não "
            "era a folha que o escondia, e esta régua não mede o que promete"
        )
        assert (
            b.ler("getComputedStyle(document.getElementById('uma-caixa')).appearance") != "none"
        ), "sem a folha, o select continuou sem `appearance` — a cura não era dela"
    finally:
        b.fechar()
