#!/usr/bin/env python3
"""AS SEIS LINHAS QUE A TROCA NÃO ALCANÇA FICAM APAGADAS — F1-REMAPEAR-02, 13/09/2026.

O DEFEITO, medido pela F1-REMAPEAR: a direção do L3 e do R3, o PS e as três
regiões do touchpad tinham lista clicável na tela "Trocar os botões". Escolher
algo nelas era recusado na hora, mas a lista continuava mostrando a escolha
recusada, e ela ia na `forma` (`forma["ps"]` saiu `"Cruz"`): todo «Guardar»
seguinte era recusado até ela devolver a linha a «— Sem troca —». Desde a
FRASES-E-DICAS-01 a recusa não tem frase — o botão pisca, e nada diz qual linha
segura o Guardar.

A CURA (§D da sprint, decisão de quem coordena por delegação, sobre a regra do
apagado da 06-Q1): as seis nascem apagadas — `disabled`, só «— Sem troca —»,
sem gesto e sem endereço de pintura —, e o pacote só as aceita em «— Sem troca
—». O motor continua recusando as seis.

O QUE ESTA RÉGUA COBRA:

1. na página, bancada e publicada: dezesseis listas com o gesto e o endereço da
   troca, e as seis de fora apagadas, com o `data-linha` e uma opção só;
2. a folha da 06 veste a lista apagada com a cara do apagado da casa;
3. num Chrome com o `BOOTSTRAP` do piloto: o clique de ponteiro nas seis não
   chega ao Python, o da Cruz chega, e a `forma` do «Guardar» traz as seis em
   «— Sem troca —»;
4. no pacote, com um disco de mentira: a forma com as seis em «— Sem troca —»
   grava; qualquer outra coisa nelas recusa sem gravar — inclusive a troca por
   si mesmo, que o motor deixa passar;
5. o motor recusa as seis.

AS MORDIDAS, rodadas na entrega da sprint:

* tire o `apagado=True` de `aba06._lista_da_troca` — a geração PARA na
  autoconferência;
* tire o `disabled` da linha do PS na página publicada — reprovam os casos 1
  (publicado) e 3;
* tire a guarda das seis de `a06_navegacao.guardar_remapeamento` — o caso 4
  reprova nas duas trocas por si mesmo.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"
INTERFACE = SRC / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(SRC), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
CHROME = pathlib.Path("/usr/bin/google-chrome")
NOME = "Régua das Seis"

#: AS SEIS, lidas dos donos: o que o produto lista e o motor não alcança.
FORA_DA_TROCA = tuple(b for b in acoes.BOTOES if b not in remap.REMAPEAVEIS)

_SELECT = re.compile(r"<select(?P<attrs>[^>]*)>(?P<miolo>.*?)</select>", re.S)
_OPCAO = re.compile(r"<option[^>]*>(.*?)</option>", re.S)


def _documento(publicado: bool) -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")


def _listas_da_troca(publicado: bool) -> dict[str, dict[str, Any]]:
    """`{data-linha: {gesto, campo, apagada, rotulos}}` da tela "Trocar os botões"."""
    tela = _documento(publicado).split('id="remapeamento"', 1)[1].split(
        'class="tela-nova"', 1)[0]
    fora: dict[str, dict[str, Any]] = {}
    for m in _SELECT.finditer(tela):
        attrs = m.group("attrs")
        linha = re.search(r'data-linha="([^"]+)"', attrs)
        assert linha, f"uma lista da troca sem `data-linha`: {attrs}"
        gesto = re.search(r'data-gesto="([^"]+)"', attrs)
        campo = re.search(r'data-campo="([^"]+)"', attrs)
        fora[linha.group(1)] = {
            "gesto": gesto.group(1) if gesto else "",
            "campo": campo.group(1) if campo else "",
            "apagada": re.search(r"\sdisabled(\s|$)", attrs) is not None,
            "rotulos": [o.strip() for o in _OPCAO.findall(m.group("miolo"))],
        }
    return fora


# ---------------------------------------------------------------------------
# 1. a página
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_as_seis_nascem_apagadas_e_as_dezesseis_trocam(publicado: bool) -> None:
    from pacotes.a06_navegacao import PREFIXO_DA_TROCA, SEM_TROCA

    listas = _listas_da_troca(publicado)
    assert sorted(listas) == sorted(acoes.BOTOES), sorted(listas)
    for botao in FORA_DA_TROCA:
        lista = listas[botao]
        assert lista["apagada"], (
            f"a linha {botao!r} da troca voltou a ser clicável — escolher algo nela "
            "é recusado, fica na lista e segura todo Guardar sem dizer qual")
        assert lista["gesto"] == "" and lista["campo"] == "", (botao, lista)
        assert lista["rotulos"] == [SEM_TROCA], (
            f"a linha apagada {botao!r} oferece {lista['rotulos']} — o estado real "
            "dela é sempre sem troca")
    for botao in remap.REMAPEAVEIS:
        lista = listas[botao]
        assert not lista["apagada"], f"a linha {botao!r}, que a troca alcança, apagou"
        assert lista["gesto"] == "linha-de-troca", (botao, lista)
        assert lista["campo"] == f"{PREFIXO_DA_TROCA}{botao}", (botao, lista)
        assert len(lista["rotulos"]) > 1, (botao, lista)


# ---------------------------------------------------------------------------
# 2. a folha
# ---------------------------------------------------------------------------
def test_a_folha_veste_a_lista_apagada_como_o_apagado_da_casa() -> None:
    doc = _documento(publicado=True)
    regra = re.search(r"\.campo-linha:disabled\{([^}]*)\}", doc)
    assert regra, "a folha da 06 perdeu a regra da lista apagada"
    for pedaco in ("var(--border-sutil)", "var(--texto-mudo)", "cursor:not-allowed"):
        assert pedaco in regra.group(1), (pedaco, regra.group(1))
    acesa = re.search(r"\.campo-linha:disabled:hover\{([^}]*)\}", doc)
    assert acesa and "var(--border-sutil)" in acesa.group(1), (
        "a lista apagada acende a borda roxa no ponteiro — promete o clique que "
        "não existe")


# ---------------------------------------------------------------------------
# 3. o navegador, com o BOOTSTRAP do piloto
# ---------------------------------------------------------------------------
def _bootstrap() -> str:
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto"
    return m.group(1)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema")
def test_no_navegador_as_seis_nao_recebem_o_clique() -> None:
    """O clique de PONTEIRO, forçado: quem recusa é o navegador, não a régua.

    `force=True` pula a espera do Playwright e manda o `mousedown`/`click` no
    centro da lista. A Cruz é o controle do instrumento: se ela não chegasse,
    a ausência das seis não provaria nada.
    """
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde
    from pacotes.a06_navegacao import SEM_TROCA

    pagina = onde.pagina(PAGINA, publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 1000})
            pg.goto(pagina.as_uri() + "#remapeamento")
            pg.evaluate("""
                window.__recebido = [];
                window.webkit = {messageHandlers: {hefesto: {
                    postMessage: function(s){ window.__recebido.push(s); }}}};
            """)
            pg.evaluate(_bootstrap())
            habilitadas = {}
            for botao in (*FORA_DA_TROCA, "cross"):
                seletor = f'#remapeamento select[data-linha="{botao}"]'
                habilitadas[botao] = pg.is_enabled(seletor)
                pg.click(seletor, force=True, timeout=2000)
                pg.keyboard.press("Escape")
            pg.eval_on_selector('[data-gesto="guardar-remapeamento"]', "el => el.click()")
            crus = [json.loads(s) for s in pg.evaluate("window.__recebido")]
        finally:
            navegador.close()
    linhas = [o.get("linha") for o in crus if o.get("gesto") == "linha-de-troca"]
    assert "cross" in linhas, (
        f"o clique na Cruz não chegou ({crus}) — sem ele o instrumento não prova "
        "a ausência das outras")
    assert habilitadas["cross"] is True
    for botao in FORA_DA_TROCA:
        assert habilitadas[botao] is False, f"a lista {botao!r} está habilitada"
        assert botao not in linhas, (
            f"o clique na linha apagada {botao!r} chegou ao Python como `linha-de-troca`")
    guardar = [o for o in crus if o.get("gesto") == "guardar-remapeamento"]
    assert guardar, crus
    forma = guardar[-1]["forma"]
    assert set(acoes.BOTOES) <= set(forma), sorted(forma)
    assert {b: forma[b] for b in FORA_DA_TROCA} == dict.fromkeys(FORA_DA_TROCA, SEM_TROCA)


# ---------------------------------------------------------------------------
# 4. o pacote, com um disco de mentira
# ---------------------------------------------------------------------------
class _PonteMuda:
    """Aceita tudo e não fala com daemon nenhum — mesma das réguas irmãs da 06."""

    def __getattr__(self, _nome: str) -> Any:
        return lambda *a, **k: True


UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "bt",
         "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "BT", "cor": "starlight-blue", "mascara": "DualSense"}]
ESTADO = {"active_profile": NOME, "controllers": [FALSO]}


def _perfil(**campos: Any) -> Any:
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile(name=NOME, match={"type": "any"}, **campos)


@pytest.fixture
def aba() -> Any:
    from pacotes import a06_navegacao

    a06_navegacao._TROCANDO.clear()
    yield a06_navegacao
    a06_navegacao._TROCANDO.clear()


@pytest.fixture
def ctx() -> Any:
    import pacotes

    return pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], list[Any]]:
    from hefesto_dualsense4unix.profiles import loader

    estado: dict[str, Any] = {}
    gravados: list[Any] = []
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n])
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof))
    return estado, gravados


def _forma(**linhas: str) -> dict[str, str]:
    """As 22 linhas como a página publicada as manda."""
    from pacotes.a06_navegacao import SEM_TROCA

    forma = dict.fromkeys(acoes.BOTOES, SEM_TROCA)
    forma.update(linhas)
    return forma


def test_as_seis_sem_troca_passam_e_o_guardar_grava(
    aba: Any, ctx: Any, disco: Any,
) -> None:
    estado, gravados = disco
    estado[NOME] = _perfil()
    aba.guardar_remapeamento(ctx, {"forma": _forma(cross="Círculo")}, _PonteMuda())
    assert [g.remapeamento for g in gravados] == [{"cross": "circle"}]


@pytest.mark.parametrize(("linha", "rotulo"), [
    ("ps", "PS"),
    ("l3_direcao", "L3 (direção)"),
    ("ps", "Cruz"),
    ("touchpad_left_press", "Cruz"),
], ids=["ps-por-si-mesmo", "l3-direcao-por-si-mesma", "ps-vira-cruz", "touchpad-vira-cruz"])
def test_qualquer_outra_coisa_nas_seis_recusa_sem_gravar(
    aba: Any, ctx: Any, disco: Any, linha: str, rotulo: str,
) -> None:
    """As duas primeiras o motor deixava passar: a troca por si mesmo some nele."""
    estado, gravados = disco
    estado[NOME] = _perfil()
    assert linha in FORA_DA_TROCA and rotulo in aba.ROTULOS_DA_TROCA
    with pytest.raises(RuntimeError, match="não guardei"):
        aba.guardar_remapeamento(
            ctx, {"forma": _forma(cross="Círculo", **{linha: rotulo})}, _PonteMuda())
    assert not gravados, (
        f"a forma com {linha}={rotulo!r} gravou {[g.remapeamento for g in gravados]}")


# ---------------------------------------------------------------------------
# 5. o motor
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("botao", FORA_DA_TROCA)
def test_o_motor_continua_recusando_as_seis(botao: str) -> None:
    assert len(FORA_DA_TROCA) == 6, FORA_DA_TROCA
    with pytest.raises(remap.RemapeamentoRecusadoError):
        remap.resolver({botao: "cross"})
