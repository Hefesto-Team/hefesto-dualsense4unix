"""O ``ligada_em`` sobrevive à atualização (O-LIGADA-EM-SOBREVIVE-A-ATUALIZACAO-01).

Medido em 21/11/2026: a extensão atualizada saía do instalador com ``ligada_em`` vazio, e a
ordem dos temas (``tema.py``, chave ``(ligada_em, id)``) mandava a atualizada para o começo da
fila: com dois temas ligados, o que valia deixava de valer. A ordem é a do gesto de ligar, e
atualizar não é ligar. O instalador, o registro e a ordem dos temas são os de verdade, num lar
de mentira; nada toca o ``~/.config`` de quem roda.

MORDIDA: sem a herança do ``ligada_em`` no bloco de ``anterior`` do ``instalar``, os três testes
reprovam.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.mods import instalador, tema


def _lugares(raiz: Path) -> instalador.Lugares:
    return instalador.Lugares(codigo=raiz / "codigo", dados=raiz / "dados",  # (noqa-acento)
                              registro=raiz / "mods.json", estado=raiz / "estado.json")


def _fonte(raiz: Path, mod_id: str, lado: str) -> Path:
    pasta = raiz / "fonte" / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = {"id": mod_id, "nome": f"Tema {mod_id}", "versao": "1.0.0",  # (noqa-acento)
             "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"],
             "permissoes": ["tema"], "tema": {"botoes": lado},  # (noqa-acento)
             "descricao": "Muda um detalhe.", "opcoes": []}  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    return pasta


def _versao(pasta: Path, versao: str) -> None:
    arquivo = pasta / "hefesto-mod.json"
    corpo = json.loads(arquivo.read_text(encoding="utf-8"))
    corpo["versao"] = versao  # (noqa-acento)
    arquivo.write_text(json.dumps(corpo), encoding="utf-8")


def _dois_ligados(raiz: Path, lg: instalador.Lugares) -> tuple[Path, Path]:
    uma = _fonte(raiz, "uma", "esquerda")
    outra = _fonte(raiz, "outra", "direita")
    for pasta, mod_id in ((uma, "uma"), (outra, "outra")):
        instalador.instalar(str(pasta), lugares=lg)
        instalador.ligar(mod_id, permissoes_vistas=["tema"], lugares=lg)
    return uma, outra


def _ordem(lg: instalador.Lugares) -> list[str]:
    registro = instalador.ler_registro(lg.registro)
    ligadas = [e for e in registro.values() if e.ligada]
    return [e.id for e in sorted(ligadas, key=lambda e: (e.ligada_em, e.id))]


def test_atualizar_o_tema_que_vale_nao_muda_qual_vale(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _uma, outra = _dois_ligados(tmp_path, lg)
    antes = instalador.ler_registro(lg.registro)["outra"].ligada_em
    assert antes and tema.tema_da_casa(lg).de == "outra"
    _versao(outra, "1.0.1")
    instalador.instalar(str(outra), lugares=lg)
    entrada = instalador.ler_registro(lg.registro)["outra"]
    assert entrada.versao == "1.0.1" and entrada.ligada_em == antes
    assert tema.tema_da_casa(lg).de == "outra"
    assert _ordem(lg) == ["uma", "outra"]


def test_atualizar_o_primeiro_guarda_o_campo_e_a_ordem(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    uma, _outra = _dois_ligados(tmp_path, lg)
    antes = instalador.ler_registro(lg.registro)["uma"].ligada_em
    _versao(uma, "1.0.1")
    instalador.instalar(str(uma), lugares=lg)
    assert instalador.ler_registro(lg.registro)["uma"].ligada_em == antes
    assert _ordem(lg) == ["uma", "outra"]
    assert tema.tema_da_casa(lg).de == "outra"


def test_a_extensao_desligada_que_se_atualiza_guarda_o_campo_e_segue_desligada(
        tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _uma, outra = _dois_ligados(tmp_path, lg)
    instalador.desligar("outra", lugares=lg)
    antes = instalador.ler_registro(lg.registro)["outra"].ligada_em
    assert antes
    _versao(outra, "1.0.1")
    instalador.instalar(str(outra), lugares=lg)
    entrada = instalador.ler_registro(lg.registro)["outra"]
    assert entrada.versao == "1.0.1"
    assert entrada.ligada_em == antes and not entrada.ligada
