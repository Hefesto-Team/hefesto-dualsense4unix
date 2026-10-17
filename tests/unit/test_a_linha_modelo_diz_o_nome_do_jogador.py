#!/usr/bin/env python3
"""A linha «Modelo» diz o nome do jogador — A-LINHA-MODELO-DIZ-O-NOME-DO-JOGADOR-01.

Pedido de 06/10/2026: *«em qualquer aba onde tivermos modelo tem que aparecer o nome do
jogador também.»* A linha existe na Iluminação (04) e na Vibração (05): «P1 • Vitória • Cosmic Red
• USB», e sem nome «P2 • Starlight Blue • BT». O nome tem UM dono (o `Alias` do BlueZ, lido por
`nome_do_jogador` com o filtro dele), e a 08 e as duas abas o dizem igual.

A régua roda os pacotes de verdade, com a leitura do BlueZ injetada onde a 08 a guarda (o fundo);
o esperado sai do que a régua escreveu, e nunca do que um pacote devolveu.

AS MORDIDAS (rodadas em 07/10/2026 e devolvidas):

* tirar o nome do `partes_do_modelo` → a régua do nome na 04 e na 05 reprova;
* o `e_nome_dela` aceitando o `Alias` de fábrica → a régua do filtro reprova (o nome de fábrica
  iria para a linha);
* o `e_nome_dela` aceitando o `Alias` que é o endereço → idem (o endereço iria para a tela);
* a 05 sem passar pelo `_identidade_do_modelo` → a 05 perde o nome e reprova;
* o gerador sem o `html.escape` no nome → a régua do escape reprova;
* a 04 sem o nome dela no pacote (`"dono": ""`) → a régua do nome e a dos quatro jogadores reprovam.
"""
from __future__ import annotations

import pathlib
import re
import sys
import time
import types
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import monta, onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04
from hefesto_dualsense4unix.interface.pacotes import em_fundo, nome_do_jogador

UNIQS = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))
MODELOS = ("Cosmic Red", "Starlight Blue", "Galactic Purple", "White")
SEP = " • "


def _aparelho(uniq: str, alias: str, *, conectado: bool = True) -> Any:
    return types.SimpleNamespace(nome=alias, endereco=uniq.upper(), conectado=conectado,
                                 icone="input-gaming", classe=None, modalias="")


@pytest.fixture(autouse=True)
def _o_bluez_e_o_da_regua(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O fundo da 08 começa limpo e é a régua quem o enche: nenhum BlueZ de verdade."""
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(em_fundo, "_FUNDO_EM_VOO", set())
    return {}


def _com_aliases(aliases: dict[str, str], *, no_cabo: frozenset[str] = frozenset()) -> None:
    """Põe no fundo o que o BlueZ diria: um aparelho por controle com o `Alias` dado."""
    aparelhos = tuple(_aparelho(u, alias, conectado=u not in no_cabo)
                      for u, alias in aliases.items())
    em_fundo._FUNDO["bluez"] = (time.monotonic() + 1e6, ((), aparelhos))


def _contexto(quantos: int, *, via: tuple[str, ...] | None = None) -> Any:
    via = via or ("usb", "bt", "bt", "usb")
    conectados, mesa = [], []
    for n in range(1, quantos + 1):
        uniq = UNIQS[n - 1]
        conectados.append({
            "uniq": uniq, "player": n, "player_slot": n, "connected": True,
            "transport": via[n - 1], "battery_pct": 90, "is_primary": n == 1, "inputs": {},
            "lightbar_rgb": [255, 255, 255], "lightbar_on": True, "brilho_da_barra": 1.0,
            "modelo": MODELOS[n - 1]})
        mesa.append({"pref": f"p{n}", "jogador": n, "uniq": uniq, "nome": MODELOS[n - 1],
                     "via": via[n - 1].upper(), "transporte": via[n - 1],
                     "cor": MODELOS[n - 1].lower().replace(" ", "-"),
                     "plastico": "#123456", "conectado": True})
    return pacotes.Contexto(
        state={"active_profile": "regua", "rumble_policy": "max", "rumble_mult_applied": 1.5,
               "native_mode": False},
        mesa=mesa, conectados=conectados, estados={})


def _linhas(monkeypatch: pytest.MonkeyPatch, página: str, ctx: Any) -> dict[str, str]:
    """A linha «Modelo» de cada controle, como o pacote da aba a manda: `{uniq: texto}`."""
    from hefesto_dualsense4unix.app.telas import vibracao as _tela

    monkeypatch.setattr(a04.perfil, "ativo",
                        lambda _n: {"leds": {"auto_player_colors": True,
                                             "lightbar_brightness": 1.0}})
    monkeypatch.setattr(_tela, "_orcamento_da_maquina", lambda: None)
    carga = pacotes.pacote_da_pagina(página, ctx) or {}
    return {u: str(c["identidade"]) for u, c in (carga.get("colunas") or {}).items()}


def _esperada(n: int, quem: str, separador: str) -> str:
    partes = [f"P{n}", quem, MODELOS[n - 1], ("USB", "BT", "BT", "USB")[n - 1]]
    return separador.join(p for p in partes if p)


PAGINAS = [("04-iluminacao.html", SEP), ("05-vibracao.html", " · ")]


@pytest.mark.parametrize(("página", "sep"), PAGINAS)
def test_com_nome_a_linha_diz_o_nome_antes_do_modelo(
        monkeypatch: pytest.MonkeyPatch, página: str, sep: str) -> None:
    """MORDIDAS: o `partes_do_modelo` sem o `dono`; a 05 sem o `_identidade_do_modelo`."""
    _com_aliases({UNIQS[0]: "Vitória", UNIQS[1]: "Amiga"})
    linhas = _linhas(monkeypatch, página, _contexto(2))
    assert linhas[UNIQS[0]] == _esperada(1, "Vitória", sep), linhas
    assert linhas[UNIQS[1]] == _esperada(2, "Amiga", sep), linhas


@pytest.mark.parametrize(("página", "sep"), PAGINAS)
def test_sem_nome_a_linha_fica_como_era_e_nunca_diz_pn_duas_vezes(
        monkeypatch: pytest.MonkeyPatch, página: str, sep: str) -> None:
    _com_aliases({})
    linhas = _linhas(monkeypatch, página, _contexto(2))
    assert linhas[UNIQS[0]] == _esperada(1, "", sep), linhas
    assert linhas[UNIQS[1]] == _esperada(2, "", sep), linhas
    assert not any(re.search(r"P(\d).*P\1\b", v) for v in linhas.values()), linhas


@pytest.mark.parametrize(("página", "sep"), PAGINAS)
def test_os_quatro_jogadores_cada_um_com_o_proprio_nome_e_o_cabo_pareado_antes(
        monkeypatch: pytest.MonkeyPatch, página: str, sep: str) -> None:
    """P1 a P4, em cabo e rádio: o `Alias` é do ENDEREÇO. O P4 (cabo, nunca pareou) não tem nome;
    o P1 (cabo, pareou antes e hoje está desconectado do rádio) tem."""
    _com_aliases({UNIQS[0]: "Vitória", UNIQS[1]: "Amiga", UNIQS[2]: "Primo"},
                 no_cabo=frozenset({UNIQS[0]}))
    linhas = _linhas(monkeypatch, página, _contexto(4))
    for n, quem in ((1, "Vitória"), (2, "Amiga"), (3, "Primo"), (4, "")):
        assert linhas[UNIQS[n - 1]] == _esperada(n, quem, sep), (n, linhas)


@pytest.mark.parametrize("página", [p for p, _ in PAGINAS])
@pytest.mark.parametrize("alias", ["DualSense Wireless Controller", "Wireless Controller",
                                   "AA:BB:CC:00:00:02", "aa-bb-cc-00-00-02"])
def test_o_alias_de_fabrica_ou_o_endereco_nao_vira_nome(
        monkeypatch: pytest.MonkeyPatch, página: str, alias: str) -> None:
    """MORDIDAS: o `e_nome_dela` aceitando o de fábrica; aceitando o que é o endereço."""
    _com_aliases({UNIQS[1]: alias})
    linhas = _linhas(monkeypatch, página, _contexto(2))
    for v in linhas.values():
        assert alias.lower() not in v.lower(), linhas
        assert "wireless" not in v.lower(), linhas
        assert "aa:bb" not in v.lower() and "aa-bb" not in v.lower(), linhas


def test_a_08_e_as_duas_abas_dizem_o_mesmo_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    """O dono é um: o nome do campo «dono» da Conexões é o que entra na linha da 04 e da 05."""
    _com_aliases({UNIQS[0]: "vitória", UNIQS[1]: "Amiga"})
    ctx = _contexto(2)
    # o campo «dono» da 08 é `dono_na_linha(nome_do_jogador.nomes_dos_donos(), uniq, jogador)`
    nomes_da_08 = nome_do_jogador.nomes_dos_donos()
    da_08 = {u: monta.dono_na_linha(nomes_da_08, u, n) for n, u in enumerate(UNIQS[:2], start=1)}
    for página, sep in PAGINAS:
        linhas = _linhas(monkeypatch, página, ctx)
        for u in UNIQS[:2]:
            assert da_08[u] and da_08[u] in linhas[u].split(sep), (página, da_08[u], linhas[u])
    assert da_08[UNIQS[0]] == "Vitória", "a primeira letra maiúscula é regra dela"


def test_o_leitor_filtra_o_alias_de_fabrica_e_o_endereco() -> None:
    """O leitor é UM (`nome_do_jogador`): só o nome dela passa, com a primeira maiúscula."""
    aparelhos = (_aparelho(UNIQS[0], "vitória"), _aparelho(UNIQS[1], "DualSense Wireless"),
                 _aparelho(UNIQS[2], "AA:BB:CC:00:00:03"))
    esperado = {nome_do_jogador.mac(UNIQS[0]): "Vitória"}
    assert nome_do_jogador.nomes_por_endereco(aparelhos) == esperado


# ---- O DONO É UM SÓ: a régua mede o FONTE, nunca a saída (O-NOME-DO-JOGADOR-TEM-UM-DONO-SO-01)

PACOTES = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"

#: o que SAIU da 08 para o `em_fundo` (o cache em fundo e o leitor do BlueZ) e para o
#: `nome_do_jogador` (o nome e o filtro dele), e como cada um se chama no dono novo
SAIRAM_DA_08 = frozenset({
    "_mac", "nome_dado", "_e_nome_de_fabrica", "_ALIAS_QUE_E_ENDERECO", "_nomes_por_endereco",
    "_nomes_dos_donos", "_FUNDO", "_FUNDO_EM_VOO", "_TRAVA_DO_FUNDO", "_GERACAO",
    "LER_NA_HORA", "VENCIDA", "_em_fundo", "_esquecer", "_ler_o_bluez", "_e_controle_do_bluez",
})
#: os dois donos: remendar o nome neles é o certo
OS_DONOS = frozenset({"em_fundo", "nome_do_jogador"})


def _ast(caminho: pathlib.Path) -> Any:
    import ast

    return ast.parse(caminho.read_text(encoding="utf-8"))


def _nomes_que_o_modulo_define(arvore: Any) -> set[str]:
    """Todo nome que o módulo LIGA: def, class, atribuição e import (com o `as`), em todo nível."""
    import ast

    achados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            achados.add(no.name)
        elif isinstance(no, ast.Name) and isinstance(no.ctx, ast.Store):
            achados.add(no.id)
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            achados.update((a.asname or a.name).split(".")[0] for a in no.names)
    return achados


def test_a_08_nao_define_nenhum_simbolo_do_que_saiu_dela() -> None:
    """A 08 chama o dono de cada um, sem alias nem cópia: nenhum nome do conjunto é ligado nela.

    MORDIDA: devolva `_mac = nome_do_jogador.mac` (ou qualquer `def _esquecer`) à 08 → reprova.
    """
    ligados = _nomes_que_o_modulo_define(_ast(PACOTES / "a08_conexoes.py"))
    assert not (SAIRAM_DA_08 & ligados), sorted(SAIRAM_DA_08 & ligados)


def test_nem_o_nome_do_jogador_nem_o_em_fundo_importam_a_08() -> None:
    """Sem import tardio: o ciclo some, em qualquer fundo (também dentro de função).

    MORDIDA: devolva `from . import a08_conexoes` dentro de uma função do `nome_do_jogador`.
    """
    import ast

    for arquivo in ("nome_do_jogador.py", "em_fundo.py"):
        for no in ast.walk(_ast(PACOTES / arquivo)):
            if isinstance(no, ast.ImportFrom):
                vistos = [no.module or "", *(a.name for a in no.names)]
            elif isinstance(no, ast.Import):
                vistos = [a.name for a in no.names]
            else:
                continue
            assert not any("a08_conexoes" in v for v in vistos), (arquivo, no.lineno)
    assert "nome_do_jogador" not in {
        a.name for no in ast.walk(_ast(PACOTES / "em_fundo.py"))
        if isinstance(no, ast.ImportFrom) for a in no.names}, "o em_fundo não importa o nome"


def test_so_o_em_fundo_cria_a_trava_do_fundo() -> None:
    """Uma trava e um cache só: nenhum outro pacote liga `_TRAVA_DO_FUNDO` nem um `Lock()` de fundo.

    MORDIDA: uma segunda `_TRAVA_DO_FUNDO = threading.Lock()` na 08 → reprova.
    """
    import ast

    donos = []
    for arquivo in sorted(PACOTES.glob("*.py")):
        for no in ast.walk(_ast(arquivo)):
            if isinstance(no, (ast.Assign, ast.AnnAssign)):
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                nomes = [a.id for a in alvos if isinstance(a, ast.Name)]
                chama_lock = isinstance(no.value, ast.Call) and "Lock" in ast.unparse(no.value.func)
                if any("FUNDO" in n.upper() for n in nomes) and chama_lock:
                    donos.append(arquivo.name)
    assert donos == ["em_fundo.py"], donos


def _os_remendos_na_08_que_saiu() -> list[str]:
    """Todo arquivo de `tests/` que atribui, remenda ou lê, num OUTRO módulo, um nome que saiu."""
    import ast

    maus: list[str] = []
    for arquivo in sorted((RAIZ / "tests").rglob("test_*.py")):
        if arquivo == pathlib.Path(__file__).resolve():
            continue
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            ruim = ""
            if isinstance(no, ast.Attribute) and no.attr in SAIRAM_DA_08:
                # `self._mac` é atributo da classe do próprio teste, não nome de outro módulo
                if isinstance(no.value, ast.Name) and no.value.id not in OS_DONOS | {"self"}:
                    ruim = f"{no.value.id}.{no.attr}"
            elif (isinstance(no, ast.Call) and len(no.args) >= 2
                  and isinstance(no.func, ast.Attribute) and no.func.attr == "setattr"
                  and isinstance(no.args[1], ast.Constant) and no.args[1].value in SAIRAM_DA_08
                  and not (isinstance(no.args[0], ast.Name) and no.args[0].id in OS_DONOS)):
                ruim = f"setattr(..., {no.args[1].value!r})"
            elif (isinstance(no, (ast.Tuple, ast.List)) and len(no.elts) >= 2
                  and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in no.elts)
                  and SAIRAM_DA_08 & {e.value for e in no.elts}):
                ruim = f"lista de nomes {sorted(SAIRAM_DA_08 & {e.value for e in no.elts})}"
            if ruim:
                maus.append(f"{arquivo.relative_to(RAIZ)}:{no.lineno} {ruim}")
    return maus


def test_nenhum_teste_remenda_na_08_um_nome_que_saiu_dela() -> None:
    """O remendo vai ao dono (`em_fundo` ou `nome_do_jogador`); na 08 ele remendaria o nada.

    A atribuição direta (`pac._nomes_dos_donos = ...`) não reprova sozinha, por isso o fonte.
    MORDIDA: volte um `pac._nomes_dos_donos = lambda: {}` a um teste → reprova.
    """
    assert _os_remendos_na_08_que_saiu() == []


def test_o_gerador_escapa_o_nome_dela_e_o_pacote_nao_o_transforma() -> None:
    """O nome é texto dela: no HTML do gerador sai escapado; no que o piloto pinta, o texto cru."""
    c = {"jogador": 1, "nome": "Cosmic Red", "via": "USB", "dono": "<b>Vi</b> & Cia"}
    html = monta.rotulo(c, "modelo")
    assert "<b>" not in html and "&lt;b&gt;Vi&lt;/b&gt; &amp; Cia" in html, html
    assert monta.partes_do_modelo(c)[1] == "<b>Vi</b> & Cia"


def test_o_desenho_aprovado_diz_o_nome_na_04_e_na_05() -> None:
    """A BANCADA (o que o `--publicar` copia): o P1 do desenho tem nome, o P2 não, o vazio não."""
    for página, rotulo in (("04-iluminacao.html", r'data-campo="identidade"'),
                           ("05-vibracao.html", r'data-hef="identidade"')):
        texto = onde.pagina(página, publicado=False).read_text(encoding="utf-8")
        linhas = [re.sub(r"<[^>]+>", "", m).split() for m in
                  re.findall(rf'{rotulo}>(.*?)</div>', texto, re.S)]
        juntas = [" ".join(p) for p in linhas]
        assert juntas[0] == "P1 • Vitória • Cosmic Red • USB", (página, juntas)
        assert juntas[1] == "P2 • Starlight Blue • BT", (página, juntas)
        assert all("Desconectado" in j for j in juntas[2:]), (página, juntas)
