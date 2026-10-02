#!/usr/bin/env python3
"""A coluna "Ajuste próprio" mostra TUDO o que o perfil guarda — na célula certa."""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.perfis_web`, que carrega o GTK")

if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

CHROME = pathlib.Path("/usr/bin/google-chrome")

MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "BT", "transporte": "bt", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "USB", "transporte": "usb", "alvo": False,
     "mascara": "DualSense"},
]

#: ``_secoes_do_controle`` pergunta ``is not None`` sobre a SEÇÃO, não sobre o
MENOR_CORPO: dict[str, Any] = {
    "leds": {}, "triggers": {}, "rumble": {}, "speaker": {"volume": 40},
    "mic": {}, "sensores": {}, "mascara": "xbox", "movimento": {},
}

LER_OS_PONTOS = """
() => {
  const linhas = [];
  for (const tr of document.querySelectorAll(
         'tbody[data-hef="guarda.linhas"] tr')) {
    linhas.push([...tr.querySelectorAll('.gc')].map(gc => [
      gc.querySelector('[data-hef="guarda.secao"]').dataset.hefSecao,
      gc.querySelector('[data-hef="guarda.proprio"]').classList.contains('on')]));
  }
  return linhas;
}
"""


def _bootstrap() -> str:
    """O ``BOOTSTRAP`` do piloto, lido do FONTE — sem importar ``gi``."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


def _perfil(uniq: str, **overrides: Any) -> Any:
    """Um perfil de disco com ajuste próprio de UM controle só.

    O DISCO NÃO SERVE: a ``tests/conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em todo teste e
    ``load_all_profiles()`` devolve **zero** perfis nesta suíte — sem dublê,
    ``pacote_da_aba`` devolveria ``guarda=[]`` e a tabela nunca seria medida.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(name="régua", match=MatchAny(),
                   controllers={uniq: ControllerOverrides(**overrides)})


def _emitidos(
    monkeypatch: pytest.MonkeyPatch, uniq: str, **overrides: Any,
) -> dict[str, Any]:
    """O que ``a10_perfis.pacote()`` manda pintar, com a mesa de dois."""
    from hefesto_dualsense4unix.profiles import loader

    alvo = _perfil(uniq, **overrides)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [alvo])
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return a10_perfis.pacote(ctx)


@pytest.fixture(autouse=True)
def _lar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de módulo zerado — sem isto um caso herda a resposta do anterior."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_SECAO_POR_CLASSE", True, raising=False)


def test_toda_secao_do_esquema_tem_celula_na_pagina() -> None:
    """Um campo de ``ControllerOverrides`` sem célula é ajuste que a tela ESCONDE."""
    html = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    na_pagina = {m for m in re.findall(r'data-hef-secao="([^"]+)"', html)}
    faltando = [s for s in perfis_web.SECOES_POR_CONTROLE if s not in na_pagina
                and s not in perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA]
    assert not faltando, (
        f"o perfil guarda {faltando} por controle e a página publicada não tem "
        f"célula para essas seções — ajuste guardado no disco que a tela esconde. "
        f"Acrescente a seção a `aba10.SECOES` e a `a10_perfis.SECOES_DA_COLUNA`, "
        f"regere e publique a aba 10.")


def test_a_pagina_nao_inventa_secao_que_o_esquema_nao_guarda() -> None:
    """O sentido contrário: célula sem campo acende sobre nada."""
    html = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    na_pagina = {m for m in re.findall(r'data-hef-secao="([^"]+)"', html)}
    sobrando = sorted(
        na_pagina - set(perfis_web.SECOES_POR_CONTROLE)
        - set(a10_perfis.ESPERANDO_O_ESQUEMA))
    assert not sobrando, (
        f"a página tem célula para {sobrando} e o esquema não guarda esses "
        f"campos — a coluna acenderia sobre nada. Declare em "
        f"`a10_perfis.ESPERANDO_O_ESQUEMA` ou tire a célula do desenho.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
@pytest.mark.parametrize("linha", [0, 1])
@pytest.mark.parametrize("secao", list(perfis_web.SECOES_POR_CONTROLE))
def test_uma_secao_guardada_acende_uma_celula_so_e_na_linha_dela(
    monkeypatch: pytest.MonkeyPatch, linha: int, secao: str,
) -> None:
    """Um ajuste, um controle: acende UMA célula, na linha e na coluna dele."""
    from playwright.sync_api import sync_playwright

    assert secao in MENOR_CORPO, (
        f"o esquema ganhou `{secao}` e esta régua não sabe montar o corpo mínimo "
        f"dessa seção — acrescente-a a `MENOR_CORPO`, senão a coluna nova "
        f"atravessa este arquivo sem ser medida")
    fora = _emitidos(monkeypatch, str(MESA[linha]["uniq"]),
                     **{secao: MENOR_CORPO[secao]})
    carga = {"mesa": {"guarda.proprio": fora["guarda.proprio"]}}

    pagina = onde.pagina(
        "10-perfis.html",
        publicado="guarda.proprio" not in a10_perfis.ESPERANDO_A_PUBLICACAO)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(pagina.as_uri())
            pg.evaluate(
                "window.webkit = {messageHandlers: {hefesto: "
                "{postMessage: function(){}}}};")
            pg.evaluate(_bootstrap())
            pg.evaluate("(p) => window.__hef.pintar(p)", carga)
            linhas = pg.evaluate(LER_OS_PONTOS)
        finally:
            navegador.close()

    acesas = [(i, nome) for i, celulas in enumerate(linhas)
              for nome, on in celulas if on]
    if secao in perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA:
        assert acesas == [], (
            f"`{secao}` espera a sessão dela e acendeu {acesas} na página "
            f"publicada — a distribuição casou a célula com uma vizinha")
        return
    assert acesas == [(linha, secao)], (
        f"com só `{secao}` guardado do controle da linha {linha}, a tela acendeu "
        f"{acesas} — o esperado é exatamente [({linha}, {secao!r})]. "
        f"Duas acesas na mesma linha, ou uma acesa na linha errada, é a coluna "
        f"casando célula com vizinha.")


def test_o_cabecalho_e_a_dica_da_linha_contam_o_mesmo_numero() -> None:
    """Dois números para o mesmo fato, na mesma tela, é a divergência que ela viu."""
    html = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    extenso = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco",
               6: "seis", 7: "sete", 8: "oito"}
    quantas = len(perfis_web.SECOES_NA_TELA)
    esperado = extenso.get(quantas, str(quantas))
    assert f"São {esperado}:" in html, (
        f"o esquema guarda {quantas} seções por controle e a dica do cabeçalho "
        f"não diz `{esperado}` — a linha ao lado já conta o número do esquema "
        f"(`{quantas} de {quantas} ajustes só deste controle`), e as duas frases "
        f"ficam na mesma tela discordando.")


def test_a_linha_sem_controle_nao_mostra_glifo_nenhum(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """*"os svgs não deveriam aparecer prós demais controles desconectados"*."""
    from playwright.sync_api import sync_playwright

    fora = _emitidos(monkeypatch, str(MESA[0]["uniq"]), leds={})
    carga = {"mesa": {chave: fora[chave] for chave in
                      ("guarda.secao", "guarda.vazio", "guarda.nome")}}

    pagina = onde.pagina("10-perfis.html", publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(pagina.as_uri())
            pg.evaluate(
                "window.webkit = {messageHandlers: {hefesto: "
                "{postMessage: function(){}}}};")
            pg.evaluate(_bootstrap())
            pg.evaluate("(p) => window.__hef.pintar(p)", carga)
            visto = pg.evaluate("""() => {
              const ls = [...document.querySelectorAll('.tab.miuda tbody tr')];
              return ls.map(tr => ({
                nome: (tr.querySelector('[data-hef="guarda.nome"]')||{}).textContent,
                fora: tr.classList.contains('fora'),
                glifos: [...tr.querySelectorAll('.gr')].map(
                    g => getComputedStyle(g).visibility),
              }));
            }""")
        finally:
            navegador.close()

    assert len(visto) == a10_perfis.LUGARES_DA_TABELA, (
        f"a tabela tem {len(visto)} linhas e a régua espera "
        f"{a10_perfis.LUGARES_DA_TABELA} — a medição perdeu o objeto")

    for n, linha in enumerate(visto[:len(MESA)], start=1):
        assert not linha["fora"], (
            f"a linha {n} TEM controle e foi marcada como vazia")
        assert set(linha["glifos"]) == {"visible"}, (
            f"a linha {n} tem controle e os glifos dela sumiram: "
            f"{linha['glifos']}")

    for n, linha in enumerate(visto[len(MESA):], start=len(MESA) + 1):
        assert linha["fora"], (
            f"a linha {n} não tem controle e o produto não a marcou — sem a "
            f"marca o CSS não tem em que se pendurar. Nome na tela: "
            f"{linha['nome']!r}")
        assert linha["glifos"], (
            f"a linha {n} não tem glifo nenhum no desenho — a régua mediria o "
            "vazio e ficaria verde por ausência de dado")
        assert set(linha["glifos"]) == {"hidden"}, (
            f"a linha {n} não tem controle e ainda desenha os glifos: "
            f"{linha['glifos']}. É a tela mostrando um aparelho que não está "
            f"aqui — a queixa dela de 05/09.")
