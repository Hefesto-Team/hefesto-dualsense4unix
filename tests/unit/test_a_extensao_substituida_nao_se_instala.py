"""A extensão que outra instalada substitui não se instala por cima.

Extensões FALSAS, de tema e sem processo, num lar de mentira no ``tmp_path``: a substituta declara
``substitui: [antiga]``, e a antiga volta a ser instalada depois de a substituta tomar o lugar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    ler_registro,
    remover,
)

ANTIGA, SUBSTITUTA, OUTRA = "a-antiga", "a-substituta", "uma-outra"
NOMES = {ANTIGA: "A antiga", SUBSTITUTA: "A substituta", OUTRA: "Uma outra"}


def _pasta(raiz: Path, mod_id: str, *, substitui: tuple[str, ...] = ()) -> Path:
    pasta = raiz / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto: dict[str, Any] = {
        "id": mod_id, "nome": NOMES[mod_id], "versao": "1.0.0",  # (noqa-acento)
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"], "tema": {},
        "permissoes": [], "descricao": "Muda um detalhe.", "opcoes": [],  # (noqa-acento)
    }
    if substitui:
        manifesto["substitui"] = list(substitui)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


@pytest.fixture
def lg(tmp_path: Path) -> Lugares:
    return Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                   dados=tmp_path / "dados",
                   registro=tmp_path / "config" / "mods.json",
                   estado=tmp_path / "run" / "mods-estado.json")


def _a_substituta_ja_instalada(lg: Lugares, raiz: Path) -> None:
    instalador.instalar(str(_pasta(raiz, SUBSTITUTA, substitui=(ANTIGA,))), lugares=lg)


def test_a_substituida_recusa_com_o_nome_de_quem_a_substituiu(lg: Lugares, tmp_path: Path) -> None:
    """D-2611-A-EXTENSAO-SUBSTITUIDA-NAO-SE-INSTALA:
    a antiga recusa, e a substituta fica inteira."""
    _a_substituta_ja_instalada(lg, tmp_path / "autor")
    antes = ler_registro(lg.registro)[SUBSTITUTA].model_dump()
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalador.instalar(str(_pasta(tmp_path / "autor", ANTIGA)), lugares=lg)
    assert "substituída por «A substituta»" in recusa.value.frase
    registro = ler_registro(lg.registro)
    assert set(registro) == {SUBSTITUTA}
    assert registro[SUBSTITUTA].model_dump() == antes
    assert not (lg.codigo / ANTIGA).exists()


def test_sem_a_substituta_a_antiga_instala(lg: Lugares, tmp_path: Path) -> None:
    """D-2611-A-EXTENSAO-SUBSTITUIDA-NAO-SE-INSTALA:
    sem a substituta instalada, nada recusa a antiga."""
    feito = instalador.instalar(str(_pasta(tmp_path / "autor", ANTIGA)), lugares=lg)
    assert feito.entrada.id == ANTIGA
    assert set(ler_registro(lg.registro)) == {ANTIGA}


def test_removida_a_substituta_a_antiga_volta_a_instalar(lg: Lugares, tmp_path: Path) -> None:
    """D-2611-A-EXTENSAO-SUBSTITUIDA-NAO-SE-INSTALA:
    a recusa vale enquanto a substituta está instalada."""
    _a_substituta_ja_instalada(lg, tmp_path / "autor")
    remover(SUBSTITUTA, lugares=lg)
    instalador.instalar(str(_pasta(tmp_path / "autor", ANTIGA)), lugares=lg)
    assert set(ler_registro(lg.registro)) == {ANTIGA}


def test_a_recusa_vale_para_toda_extensao_e_so_para_o_id_nomeado(lg: Lugares,
                                                                 tmp_path: Path) -> None:
    """D-2611-A-EXTENSAO-SUBSTITUIDA-NAO-SE-INSTALA: outra extensão qualquer segue instalando."""
    _a_substituta_ja_instalada(lg, tmp_path / "autor")
    instalador.instalar(str(_pasta(tmp_path / "autor", OUTRA)), lugares=lg)
    assert set(ler_registro(lg.registro)) == {SUBSTITUTA, OUTRA}


def test_a_substituida_que_ja_estava_instalada_nao_se_atualiza_por_cima(lg: Lugares,
                                                                       tmp_path: Path) -> None:
    """D-2611-A-EXTENSAO-SUBSTITUIDA-NAO-SE-INSTALA:
    a antiga que convive com a substituta recusa o «Atualizar», e o código e o registro ficam."""
    autor = tmp_path / "autor"
    instalador.instalar(str(_pasta(autor, ANTIGA)), lugares=lg)
    instalador.instalar(str(_pasta(autor, SUBSTITUTA)), lugares=lg)
    instalada = lg.codigo / SUBSTITUTA / "hefesto-mod.json"
    manifesto = json.loads(instalada.read_text(encoding="utf-8"))
    manifesto["substitui"] = [ANTIGA]
    instalada.chmod(0o644)
    instalada.write_text(json.dumps(manifesto), encoding="utf-8")
    nova = json.loads((autor / ANTIGA / "hefesto-mod.json").read_text(encoding="utf-8"))
    nova["versao"] = "1.0.1"  # (noqa-acento)
    (autor / ANTIGA / "hefesto-mod.json").write_text(json.dumps(nova), encoding="utf-8")
    antes = ler_registro(lg.registro)[ANTIGA].model_dump()
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalador.atualizar(ANTIGA, lugares=lg)
    assert "substituída por «A substituta»" in recusa.value.frase
    assert ler_registro(lg.registro)[ANTIGA].model_dump() == antes
    codigo = json.loads((lg.codigo / ANTIGA / "hefesto-mod.json").read_text(encoding="utf-8"))
    assert codigo["versao"] == "1.0.0"  # (noqa-acento)


def test_reinstalar_a_propria_substituta_segue_valendo(lg: Lugares, tmp_path: Path) -> None:
    """D-2611-A-EXTENSAO-SUBSTITUIDA-NAO-SE-INSTALA:
    a extensão nunca é recusada por causa do próprio ``substitui``."""
    _a_substituta_ja_instalada(lg, tmp_path / "autor")
    feito = instalador.instalar(str(_pasta(tmp_path / "autor", SUBSTITUTA, substitui=(ANTIGA,))),
                                lugares=lg)
    assert feito.entrada.id == SUBSTITUTA
