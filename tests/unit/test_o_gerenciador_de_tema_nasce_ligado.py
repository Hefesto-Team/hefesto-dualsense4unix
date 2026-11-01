"""A extensão de fábrica com ``ligar: true`` nasce ligada, mesmo quando substitui uma desligada.

A sprint é a O-GERENCIADOR-DE-TEMA-NASCE-LIGADO-E-VESTE-OS-BOTOES-DA-JANELA-01. Medido em
01/11/2026: o gerenciador de tema substitui o tema claro, que fica desligado no tema Escuro, e a
regra do substituto desligado o deixava desligado justamente no tema normal. A regra agora só olha
o registro DESTA extensão: a que quem usa desligou fica desligada; a que nasceu desligada pela
regra velha se liga uma vez, no install seguinte.

MORDIDAS (01/11/2026, executadas sobre a cura e devolvidas):

- a regra velha (``desligadas`` do substituto) devolvida ao ``_trazer_uma`` reprova
  ``test_a_que_substitui_uma_desligada_nasce_ligada``;
- a revisão da que nasceu desligada arrancada reprova
  ``test_a_que_nasceu_desligada_pela_regra_velha_se_liga_uma_vez``;
- a revisão sem a anotação das revistas reprova
  ``test_a_que_nasceu_desligada_pela_regra_velha_se_liga_uma_vez`` (a atualização zera o
  ``ligada_em``, e a desligada depois da atualização voltaria ligada);
- a revisão sem conferir o ``ligada_em`` reprova
  ``test_a_que_quem_usa_desligou_antes_da_cura_fica_desligada``.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.mods import de_fabrica_por_endereco as fabrica
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import Lugares, gravar_registro, ler_registro
from tests.unit.test_a_extensao_de_fabrica_por_endereco_chega_pelo_install import (
    ANTIGA,
    NOVA,
    _lista,
    _repo,
    lg,
)

__all__ = ["lg"]


def _a_substituta(tmp_path: Path, **item: object) -> Path:
    endereco = _repo(tmp_path, NOVA, substitui=[ANTIGA])
    return _lista(tmp_path, {"id": NOVA, "endereco": endereco, **item})


def _como_a_regra_velha_deixou(lg: Lugares, tmp_path: Path, *, ligada_em: str = "") -> Path:
    """O registro de quem fez o install antes da cura: instalada, desligada, já anotada."""
    endereco = _repo(tmp_path, NOVA)
    lista = _lista(tmp_path, {"id": NOVA, "endereco": endereco})
    instalador.instalar(endereco, lugares=lg)
    registro = ler_registro(lg.registro)
    registro[NOVA].ligada_em = ligada_em
    gravar_registro(lg.registro, registro)
    lg.registro.with_name(fabrica.TRAZIDAS).write_text(json.dumps({"trazidas": [NOVA]}))
    return lista


def test_a_que_substitui_uma_desligada_nasce_ligada(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    feitos = fabrica.trazer(lugares=lg, arquivo=_a_substituta(tmp_path))
    registro = ler_registro(lg.registro)
    assert ANTIGA not in registro and registro[NOVA].ligada
    assert [f.o_que for f in feitos] == ["ligada"]


def test_a_que_a_lista_nao_manda_ligar_fica_desligada(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    feitos = fabrica.trazer(lugares=lg, arquivo=_a_substituta(tmp_path, ligar=False))
    assert [f.o_que for f in feitos] == ["instalada"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_quem_usa_desligou_depois_fica_desligada(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    lista = _a_substituta(tmp_path)
    fabrica.trazer(lugares=lg, arquivo=lista)
    instalador.desligar(NOVA, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_nasceu_desligada_pela_regra_velha_se_liga_uma_vez(
        lg: Lugares, tmp_path: Path) -> None:
    lista = _como_a_regra_velha_deixou(lg, tmp_path)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ligada"]
    assert ler_registro(lg.registro)[NOVA].ligada
    instalador.atualizar(NOVA, lugares=lg)
    assert ler_registro(lg.registro)[NOVA].ligada_em == ""
    instalador.desligar(NOVA, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_quem_usa_desligou_antes_da_cura_fica_desligada(
        lg: Lugares, tmp_path: Path) -> None:
    lista = _como_a_regra_velha_deixou(lg, tmp_path, ligada_em="2026-10-31T10:00:00+00:00")
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_quem_usa_instalou_sem_a_lista_fica_como_esta(lg: Lugares, tmp_path: Path) -> None:
    endereco = _repo(tmp_path, NOVA)
    lista = _lista(tmp_path, {"id": NOVA, "endereco": endereco})
    instalador.instalar(endereco, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_lista_do_pacote_manda_ligar_cada_extensao() -> None:
    assert all(item.ligar for item in fabrica.ler())
