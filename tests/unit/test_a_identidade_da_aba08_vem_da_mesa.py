#!/usr/bin/env python3
"""A IDENTIDADE DA ABA 08 VEM DA MESA, nunca do mockup."""
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
REGUA = RAIZ / "scripts/check_identidade_vem_de_cima.py"


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


@pytest.mark.skipif(not REGUA.exists(), reason="a régua de identidade não está nesta árvore")
def test_sem_congelado_na_bancada_da_08() -> None:
    """A régua da sprint, chamada como a sprint manda, tem de devolver zero."""
    saida = subprocess.run(
        [sys.executable, str(REGUA), "--bancada", "--aba", "08"],
        capture_output=True, text=True, cwd=str(RAIZ), check=False)
    assert saida.returncode == 0, (
        "a `08-conexoes` voltou a ter identidade congelada na bancada:\n"
        + saida.stdout + saida.stderr)


def test_os_enderecos_da_identidade_existem_na_bancada() -> None:
    """Os quatro endereços desta cura, no arquivo que o produto vai renderizar."""
    html = BANCADA.read_text(encoding="utf-8")
    for endereco in ('data-campo="nome" data-hef-alvo="html"',
                     'data-campo="plastico" data-hef-alvo="cor"',
                     'data-campo="radio-sala" data-hef-alvo="html"',
                     'data-campo="aparelhos" data-hef-alvo="html"'):
        assert endereco in html, (
            f"o endereço `{endereco}` sumiu da bancada da 08 — sem ele o produto "
            f"não tem onde escrever, e a tela volta ao desenho")


def test_os_chips_da_fita_tem_endereco() -> None:
    """Todo chip de plástico da fita tem endereço, e nenhum sobra sem."""
    html = BANCADA.read_text(encoding="utf-8")
    tags = re.findall(r"<label[^>]*\bclass=\"chip plastico[^>]*>", html)
    endereçados = [t for t in tags if 'data-campo="fita-chip"' in t]
    assert tags and len(tags) == len(endereçados), (
        f"a fita da 08 tem {len(tags)} chips de plástico e "
        f"{len(endereçados)} com endereço")
    for t in tags:
        assert t.count('data-campo="fita-chip"') == 1, (
            f"um chip da fita traz o endereço mais de uma vez: {t}")


ADAPTADOR = "aa:bb:cc:00:00:09"


def _ctx(cor_do_p2: str = "galactic-purple") -> Any:
    """Uma mesa de dois: um no cabo com cor lida, um no rádio (cor variável)."""
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
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64,
         "adaptador": ADAPTADOR},
    ]
    return Contexto(state={"controllers": conectados,
                           "radio_ar": {ADAPTADOR: {"pontes": [], "n_max": 2}}},
                    mesa=mesa, conectados=conectados, estados={})


def test_o_pacote_escreve_o_rotulo_da_mesa() -> None:
    """O rótulo de cada linha vem da MESA, e nomeia o controle que está lá."""
    pac = _pacote().pacote(_ctx())
    nomes = [c.get("nome", "") for c in pac["colunas"].values()]
    assert any("White" in n for n in nomes), (
        f"o pacote não escreveu o White da mesa — escreveu {nomes!r}")
    assert any("Galactic Purple" in n for n in nomes)
    for n in nomes:
        for do_desenho in ("Cosmic Red", "Starlight Blue"):
            assert do_desenho not in n, (
                f"o pacote escreveu `{do_desenho}`, que é do MOCKUP e não da mesa")


def test_o_pacote_escreve_a_cor_do_plastico() -> None:
    """A barra da linha recebe o hex do MAPA, e nunca um hex digitado."""
    import monta

    pac = _pacote().pacote(_ctx())
    cores = [c.get("plastico", "") for c in pac["colunas"].values()]
    assert monta.cor_da_zona("white") in cores, (
        f"o pacote não escreveu a cor do White — escreveu {cores!r}")
    assert monta.cor_da_zona("galactic-purple") in cores


def test_sem_cor_lida_nao_se_inventa_nem_se_escreve_nao_sei() -> None:
    """Regra de produto: campo sem informação NÃO MOSTRA NADA."""
    pac = _pacote().pacote(_ctx(cor_do_p2=""))
    do_radio = [c for c in pac["colunas"].values() if c.get("via") == "BT"]
    assert do_radio, "a mesa de prova perdeu o controle de rádio"
    for c in do_radio:
        assert c["plastico"] == "", (
            f"sem cor lida a barra recebeu {c['plastico']!r} — isso é inventar")
        assert "Não sei" not in c["nome"], (
            f"a palavra interna da mesa vazou para a tela: {c['nome']!r}")
        for do_desenho in ("Cosmic Red", "Starlight Blue", "Galactic Purple"):
            assert do_desenho not in c["nome"]
    inteiro = c["nome"] + str(pac.get("radio-sala") or "")
    assert "Não sei" not in inteiro, (
        "`Não sei` apareceu na sala do rádio — foi o vazamento medido em 03/09, "
        "no `title` da régua antiga: *'Não sei — 260,4 turnos de entrada'*")


def test_a_sala_do_radio_e_um_bloco_e_nomeia_quem_esta_na_mesa() -> None:
    """A sala do rádio nasce do produto, com os controles da mesa."""
    html = str(_pacote().pacote(_ctx()).get("radio-sala") or "")
    assert 'class="lugar' in html and 'class="linha' in html, (
        "a sala do rádio saiu sem o cartão do adaptador ou sem a linha do controle")
    assert "Galactic Purple" in html, (
        "a sala do rádio não nomeou o controle que está NO rádio")
    for do_desenho in ("Cosmic Red", "Starlight Blue"):
        assert do_desenho not in html, (
            f"a sala do rádio trouxe `{do_desenho}`, que é do desenho")


def test_o_rotulo_tem_um_dono_so() -> None:
    """O gerador e o pacote escrevem o MESMO rótulo, porque é a mesma função."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(
        encoding="utf-8")
    for linha in ("rotulo = _pacote08.rotulo_do_controle",):
        assert linha in fonte, (
            f"`{linha}` sumiu do gerador — o rótulo do plástico voltou a ter "
            f"duas escritas, e duas escritas divergem caladas")
    assert "def rotulo(" not in fonte, (
        "o gerador voltou a definir o próprio `rotulo` ao lado do do pacote")
