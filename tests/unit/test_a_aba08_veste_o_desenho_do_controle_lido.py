#!/usr/bin/env python3
"""O DESENHO DA ABA 08 É O CONTROLE DELA, e não o do mockup."""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/08-conexoes.html"
REGUA = RAIZ / "scripts/check_a_cor_vem_do_aparelho.py"

DESENHO_DA_LINHA = re.compile(r"<svg\b[^>]*\bclass=\"ds-svg ds-mini\"[^>]*>")

FOLHA = re.compile(r'<style id="([^"]*cores-do-dualsense-folha)">(.*?)</style>', re.S)

REGRA_DE_COLORWAY = re.compile(r'svg\[data-colorway="([^"]+)"\]')


def _html() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _modelos_do_mapa() -> set[str]:
    """Os 28 slugs que a mesa pode emitir, pelo dono deles."""
    from hefesto_dualsense4unix.interface import mesa_viva

    return {slug for slug, _nome in mesa_viva.CORES.values() if slug}


def test_todo_desenho_da_aba_tem_o_endereco_do_colorway() -> None:
    """Nenhum `<svg>` da linha nasce sem por onde o produto trocar a cor."""
    tags = DESENHO_DA_LINHA.findall(_html())
    assert tags, "a bancada da 08 não tem mais nenhum desenho `.ds-mini`"
    for tag in tags:
        assert 'data-hef-alvo="atributo"' in tag, (
            f"um desenho da 08 perdeu o alvo de atributo — sem ele o "
            f"`escrever()` cai no ramo padrão e escreve a cor como TEXTO por "
            f"cima do desenho: {tag[:160]}")
        assert 'data-hef-atributo="data-colorway"' in tag, (
            f"o alvo não NOMEIA o atributo certo — `data-hef-atributo` com "
            f"outro nome escreve outra coisa e deixa o colorway cravado: "
            f"{tag[:160]}")
        assert 'data-campo="desenho"' in tag, (
            f"o desenho tem alvo e não tem ENDEREÇO: o `achar()` do piloto "
            f"procura por `data-campo`, e sem ele o alvo nunca é alcançado: "
            f"{tag[:160]}")


def test_so_uma_folha_de_cores_e_ela_nao_esta_dentro_de_um_desenho() -> None:
    """A folha é UMA, da página, e não uma cópia podada por desenho."""
    folhas = FOLHA.findall(_html())
    assert len(folhas) == 1, (
        f"a 08 tem {len(folhas)} folhas de cores: "
        f"{[i for i, _ in folhas]}. Ela é UMA, da página.")
    ident, _css = folhas[0]
    assert ident == "cores-do-dualsense-folha", (
        f"a folha da 08 está dentro de um desenho (`id={ident}`) — o `svg()` "
        f"prefixa o `id` por controle, e é ele que a poda para um modelo só")


def test_todo_modelo_do_mapa_dela_tem_regra_na_pagina() -> None:
    """Os VINTE E OITO, e não os dois da mesa de hoje."""
    declarados = set(REGRA_DE_COLORWAY.findall(_html()))
    faltam = _modelos_do_mapa() - declarados
    assert not faltam, (
        f"faltam {len(faltam)} modelos do mapa dela na folha da 08: "
        f"{sorted(faltam)[:6]}… Quem tiver um deles vê um controle cinza.")


def test_a_hachura_e_os_gradientes_chegam_junto_com_a_folha() -> None:
    """Toda tinta que a folha REFERENCIA existe na página, com o `id` que ela cita."""
    html = _html()
    _ident, css = FOLHA.search(html).groups()  # type: ignore[union-attr]
    citados = set(re.findall(r"url\(#([^)]+)\)", css))
    assert citados, (
        "a folha da 08 não cita tinta nenhuma por `url(#…)` — se o mapa dela "
        "deixou de usar hachura, esta régua perdeu o sujeito")
    for ident in sorted(citados):
        assert f'id="{ident}"' in html, (
            f"a folha pinta com `url(#{ident})` e a página não define esse "
            f"`id`. Os modelos que dependem dele ficam SEM TINTA, e ninguém que "
            f"não tenha um deles na mão vê o defeito.")


def test_a_folha_nao_e_digitada_no_gerador() -> None:
    """A tabela da página é LIDA do desenho, nunca escrita à mão."""
    import monta

    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(
        encoding="utf-8")
    hexes = set(re.findall(r"--z-[a-z0-9_-]+\s*:\s*#[0-9a-fA-F]{3,8}", fonte))
    assert not hexes, (
        f"o gerador da 08 digitou hex de zona: {sorted(hexes)[:4]} — a folha "
        f"tem dono, e ele não é esta aba")
    do_desenho = FOLHA.search(monta.DS)
    assert do_desenho, "a folha sumiu do `ds_limpo.svg`"
    na_pagina = FOLHA.search(_html())
    assert na_pagina and na_pagina.group(2).strip() == do_desenho.group(2).strip(), (
        "a folha da página não é a do `ds_limpo.svg` — alguém a editou no meio "
        "do caminho, e a partir daqui as duas divergem caladas")


def _ctx(cor_do_p2: str = "galactic-purple") -> Any:
    """A mesa dela: o White no cabo, e um no rádio com a cor variável."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": cor_do_p2,
         "nome": "Galactic Purple" if cor_do_p2 else "Não sei",
         "via": "BT", "transporte": "bt", "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_pacote_escreve_o_modelo_que_a_mesa_leu() -> None:
    """Por controle, o SLUG do mapa — nunca o do desenho."""
    colunas = _pacote().pacote(_ctx())["colunas"]
    modelos = [c.get("desenho", "") for c in colunas.values()]
    assert "white" in modelos, (
        f"o pacote não escreveu o modelo do White — escreveu {modelos!r}")
    assert "galactic-purple" in modelos
    for m in modelos:
        assert m not in ("cosmic-red", "starlight-blue"), (
            f"o pacote escreveu `{m}`, que é do MOCKUP e não da mesa")


def test_o_pacote_fala_a_lingua_do_atributo_e_nao_a_do_hex() -> None:
    """O desenho escolhe por NOME de modelo; a barra da linha, por hex."""
    import monta

    for coluna in _pacote().pacote(_ctx())["colunas"].values():
        assert not coluna["desenho"].startswith("#"), (
            f"o pacote mandou um hex para o `data-colorway`: {coluna['desenho']!r}")
        assert coluna["plastico"] == monta.cor_da_zona(coluna["desenho"]), (
            "a barra e o desenho deixaram de falar do mesmo modelo — a linha "
            "mostraria uma cor na aresta e outra no controle")


def test_o_modelo_sem_hex_medido_nao_derruba_a_aba() -> None:
    """OITO dos 28 modelos não têm hex, e isso derrubava a `08` inteira."""
    import monta

    sem_hex = [m for m in sorted(_modelos_do_mapa())
               if not monta.cor_da_zona(m).startswith("#")]
    assert sem_hex, (
        "nenhum modelo do mapa usa a hachura — se ela mediu os 28, esta régua "
        "perdeu o alvo e vira teste sem sujeito")
    for modelo in sem_hex:
        colunas = _pacote().pacote(_ctx(cor_do_p2=modelo))["colunas"]
        do_radio = [c for c in colunas.values() if c.get("via") == "BT"]
        assert do_radio, f"a mesa de prova perdeu o rádio com `{modelo}`"
        for c in do_radio:
            assert c["desenho"] == modelo, (
                f"o desenho perdeu o modelo `{modelo}` — a hachura É a resposta "
                f"certa para ele, e o SVG sabe desenhá-la")
            assert c["plastico"] == "", (
                f"a barra recebeu {c['plastico']!r} para `{modelo}` — uma "
                f"hachura não é uma cor, e `tinta_legivel` morre com ela")


def test_todo_modelo_que_o_pacote_pode_emitir_e_pintavel() -> None:
    """Os 28 caminhos, e não só os dois da mesa de prova."""
    declarados = set(REGRA_DE_COLORWAY.findall(_html()))
    for modelo in sorted(_modelos_do_mapa()):
        colunas = _pacote().pacote(_ctx(cor_do_p2=modelo))["colunas"]
        emitidos = {c.get("desenho", "") for c in colunas.values()}
        assert modelo in emitidos, (
            f"o pacote engoliu o modelo `{modelo}` — emitiu {emitidos!r}")
        assert modelo in declarados, (
            f"a página não tem regra para `{modelo}`, que o pacote emite")


def test_sem_cor_lida_o_desenho_fica_sem_identidade() -> None:
    """Regra dela: campo sem informação NÃO MOSTRA NADA."""
    colunas = _pacote().pacote(_ctx(cor_do_p2=""))["colunas"]
    do_radio = [c for c in colunas.values() if c.get("via") == "BT"]
    assert do_radio, "a mesa de prova perdeu o controle de rádio"
    for c in do_radio:
        assert c["desenho"] == "", (
            f"sem cor lida o desenho recebeu {c['desenho']!r} — isso é inventar")


@pytest.mark.skipif(not REGUA.exists(),
                    reason="o portão da cor ainda não chegou a esta árvore")
def test_a_bancada_da_08_nao_tem_mais_cor_cravada() -> None:
    """A régua da leva, chamada como a leva manda, tem de devolver zero."""
    saida = subprocess.run(
        [sys.executable, str(REGUA), "--bancada", "--aba", "08"],
        capture_output=True, text=True, cwd=str(RAIZ), check=False)
    assert saida.returncode == 0, (
        "a `08-conexoes` voltou a ter cor de aparelho cravada na bancada:\n"
        + saida.stdout + saida.stderr)
