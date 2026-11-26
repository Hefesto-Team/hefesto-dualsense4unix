"""O-NOME-LIVRE-E-O-ARQUIVO-TORTO-NAO-QUEBRAM-A-JANELA-01: o nome livre é texto na tela.

O nome que o usuário dá ao controle (`controles[<uniq>].cor` do `maquina.json`, o
`nome_declarado` do estado) chega à fita, às formas do `monta.rotulo` e aos rótulos da Conexões
escrito exatamente como foi dado, sem virar marcação; a dica do chip também. O `cor` ganha o
validador de tamanho e de caracteres. As preferências da janela em JSON que não é objeto voltam ao
padrão, e um `.json` que não é perfil na pasta não tira os outros da lista.

Mordidas: tirar o `html.escape` de `monta.rotulo` (forma «curta») ou da dica do chip faz as
réguas da fita reprovar; tirar o validador do `cor` faz a régua do `maquina.json` reprovar.
"""
from __future__ import annotations

import html
import json
import pathlib
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.app import gui_prefs
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.interface.pacotes import perfil
from hefesto_dualsense4unix.utils.maquina import ControleDeclarado

HOSTIL = 'x"><img src=x onerror=alert(1)>'
COM_SINAIS = 'Meu "Azul" & <Cia>'


def _monta() -> Any:
    from hefesto_dualsense4unix.interface import monta

    return monta


def _controle(nome: str, n: int = 1, via: str = "USB") -> dict[str, Any]:
    return {"pref": f"p{n}", "jogador": n, "cor": "", "nome": nome, "via": via,
            "transporte": "usb", "alvo": n == 1, "mascara": "DualSense", "conectado": True,
            "uniq": f"aa:bb:cc:00:00:0{n}"}


@pytest.mark.parametrize("nome", [HOSTIL, COM_SINAIS])
@pytest.mark.parametrize("forma", ["curta", "peca", "completa", "modelo"])
def test_cada_forma_do_rotulo_escreve_o_nome_como_texto(nome: str, forma: str) -> None:
    """Cada forma do rótulo leva o nome escapado: nenhuma marcação nasce do nome."""
    monta = _monta()
    c = {**_controle(nome), "dono": nome}
    saida = monta.rotulo(c, forma)
    assert "<img" not in saida and "<Cia>" not in saida, saida
    assert html.escape(nome, quote=forma == "modelo") in saida, saida


@pytest.mark.parametrize("nome", [HOSTIL, COM_SINAIS])
def test_a_fita_escreve_o_nome_e_a_dica_como_texto(nome: str) -> None:
    """O chip e a dica dele mostram o nome inteiro, sem tag viva nem aspas soltas no `title`."""
    monta = _monta()
    mesa = [_controle(nome, 1), _controle("Starlight Blue", 2, "BT")]
    saida = monta.fita(ativo="p1", mesa=mesa)
    assert "<img" not in saida and "<Cia>" not in saida, saida
    for resto in saida.split('title="')[1:]:
        valor = resto.split('"', 1)[0]
        assert "<" not in valor and ">" not in valor, valor
    assert html.escape(nome, quote=False) in saida


@pytest.mark.parametrize("nome", [HOSTIL, COM_SINAIS])
def test_os_rotulos_da_conexoes_escrevem_o_nome_como_texto(nome: str) -> None:
    """Os dois rótulos da Conexões usam o mesmo escape."""
    c = _controle(nome)
    for saida in (a08.rotulo_do_controle(c), a08.rotulo_do_controle(c, completo=False),
                  a08.rotulo_curto_do_controle(c)):
        assert "<img" not in saida and "<Cia>" not in saida, saida
        assert html.escape(nome, quote=False) in saida, saida


def test_o_apostrofo_do_modelo_fica_como_esta() -> None:
    """O texto só escapa `&`, `<` e `>`: o modelo «Marvel's Spider-Man 2» sai como é."""
    monta = _monta()
    assert "Marvel's Spider-Man 2" in monta.rotulo(_controle("Marvel's Spider-Man 2"), "curta")


def test_as_paginas_geradas_nao_mudam() -> None:
    """Os nomes e as vias do desenho não têm o que escapar: as páginas geradas saem iguais."""
    monta = _monta()
    for c in monta.MESA:
        for texto in (c["nome"], c["via"], f'P{c["jogador"]}', f'Player {c["jogador"]}'):
            assert html.escape(texto, quote=False) == texto, texto


def test_o_cor_do_maquina_json_tem_tamanho_e_caracteres() -> None:
    """O nome do plástico é aparado, cabe em 248 bytes e não traz caractere de controle."""
    assert ControleDeclarado(cor="  Azul do Rio  ").cor == "Azul do Rio"
    assert ControleDeclarado(cor="   ").cor is None
    assert ControleDeclarado(cor=COM_SINAIS).cor == COM_SINAIS
    for torto in ("a" * 249, "Azul\nVermelho", "Azul\x00"):
        with pytest.raises(ValidationError):
            ControleDeclarado(cor=torto)


@pytest.mark.parametrize("bruto", [b"null", b"[1, 2]", b'"x"', b"7", b"\xff\xfe{", b"{"])
def test_as_preferencias_tortas_voltam_ao_padrao(
        bruto: bytes, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON que não é objeto, bytes inválidos e JSON quebrado: vale o padrão, sem levantar."""
    arquivo = tmp_path / "gui_preferences.json"
    arquivo.write_bytes(bruto)
    monkeypatch.setattr(gui_prefs, "_prefs_file", lambda: arquivo)
    assert gui_prefs.load_gui_prefs() == gui_prefs._defaults()


def test_o_json_que_nao_e_perfil_nao_tira_os_outros_da_lista(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Um `[]` e um texto na pasta de perfis: a lista traz os perfis de verdade."""
    (tmp_path / "bom.json").write_text(json.dumps({"name": "Bom", "priority": 1}))
    (tmp_path / "lista.json").write_text("[]")
    (tmp_path / "texto.json").write_text('"só texto"')
    monkeypatch.setattr(perfil, "pasta", lambda: tmp_path)
    assert [x["nome"] for x in perfil.lista()] == ["Bom"]
