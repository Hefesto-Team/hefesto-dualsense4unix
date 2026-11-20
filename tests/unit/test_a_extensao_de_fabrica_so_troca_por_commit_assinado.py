"""A extensão de fábrica só troca o código por commit assinado por uma chave da lista.

Repositórios ``git init`` locais (``file://``), chaves ssh geradas no lar de mentira e a lista de
fábrica apontada para o repositório de mentira: nada fala com a rede.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import de_fabrica_por_endereco, instalador
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    atualizar,
    instalar,
    ler_registro,
    manifesto_instalado,
)
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

curto, lar = _base.curto, _base.lar
_git, _chave = _base._git, _base._chave


def _manifesto(versao: str) -> str:
    return json.dumps({
        "id": "exemplo", "nome": "Exemplo", "versao": versao,  # (noqa-acento)
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"], "tema": {},
        "permissoes": []})  # (noqa-acento)


def _publicar(origem: Path, versao: str, chave: Path | None = None) -> str:
    (origem / "hefesto-mod.json").write_text(_manifesto(versao), encoding="utf-8")
    _git(origem, "add", ".")
    assinar = (["-c", "gpg.format=ssh", "-c", f"user.signingkey={chave}", "commit", "-S"]
               if chave else ["commit"])
    _git(origem, *assinar, "-q", "-m", f"a {versao}")
    return _git(origem, "rev-parse", "HEAD")


@pytest.fixture
def mesa(curto: Path, lar: Lugares, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """O repositório de fábrica de mentira, instalado na 1.0.0, e as duas chaves."""
    if shutil.which("ssh-keygen") is None:
        pytest.skip("sem ssh-keygen")
    origem = curto / "Time" / "hefesto-mod-exemplo"
    origem.mkdir(parents=True)
    _git(origem, "init", "-q", "-b", "principal")
    do_time, linha_do_time = _chave(curto, "chave-do-time")
    de_outro, _linha_de_outro = _chave(curto, "chave-de-outro")
    _publicar(origem, "1.0.0", do_time)
    lista = curto / "de-fabrica.json"
    lista.write_text(json.dumps({"formato": 1, "extensoes": [  # (noqa-acento)
        {"id": "exemplo", "endereco": f"file://{origem}"}]}), encoding="utf-8")
    monkeypatch.setattr(de_fabrica_por_endereco, "ARQUIVO", lista)
    chaves = (linha_do_time,)
    instalar(f"file://{origem}", lugares=lar, chaves=chaves)
    return {"origem": origem, "do_time": do_time, "de_outro": de_outro, "chaves": chaves}


def _versao(lar: Lugares) -> str:
    return manifesto_instalado("exemplo", lugares=lar).versao


def test_o_commit_sem_assinatura_nao_troca_e_a_linha_diz_o_motivo(
        lar: Lugares, mesa: dict[str, object]) -> None:
    """D-1911-A-EXTENSAO-DE-FABRICA-SO-TROCA-POR-COMMIT-ASSINADO: sem assinatura, espera."""
    novo = _publicar(mesa["origem"], "1.1.0")  # type: ignore[arg-type]
    feito = atualizar("exemplo", lugares=lar, chaves=mesa["chaves"],  # type: ignore[arg-type]
                      sozinha=True)
    assert not feito.trocou and _versao(lar) == "1.0.0"
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.versao_esperando == "1.1.0" and entrada.commit_esperando == novo
    assert entrada.motivo_da_espera == "A versão 1.1.0 não traz a assinatura do Hefesto."
    with pytest.raises(InstalacaoRecusadaError, match="não traz a assinatura"):
        atualizar("exemplo", lugares=lar, chaves=mesa["chaves"])  # type: ignore[arg-type]
    assert _versao(lar) == "1.0.0"


def test_o_commit_assinado_por_chave_da_lista_troca(lar: Lugares,
                                                    mesa: dict[str, object]) -> None:
    _publicar(mesa["origem"], "1.1.0", mesa["do_time"])  # type: ignore[arg-type]
    feito = atualizar("exemplo", lugares=lar, chaves=mesa["chaves"],  # type: ignore[arg-type]
                      sozinha=True)
    assert feito.trocou and _versao(lar) == "1.1.0"


def test_o_commit_assinado_por_chave_de_fora_nao_troca(lar: Lugares,
                                                       mesa: dict[str, object]) -> None:
    _publicar(mesa["origem"], "1.1.0", mesa["de_outro"])  # type: ignore[arg-type]
    feito = atualizar("exemplo", lugares=lar, chaves=mesa["chaves"],  # type: ignore[arg-type]
                      sozinha=True)
    assert not feito.trocou and _versao(lar) == "1.0.0"


def test_a_de_comunidade_segue_subindo_sem_assinatura(lar: Lugares, mesa: dict[str, object],
                                                      curto: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(de_fabrica_por_endereco, "ARQUIVO", curto / "nenhuma.json")
    _publicar(mesa["origem"], "1.1.0")  # type: ignore[arg-type]
    feito = atualizar("exemplo", lugares=lar, chaves=mesa["chaves"],  # type: ignore[arg-type]
                      sozinha=True)
    assert feito.trocou and _versao(lar) == "1.1.0"


def test_as_chaves_oficiais_sao_as_da_lista_que_a_instalacao_carrega() -> None:
    lista = Path(__file__).resolve().parents[2] / "assets" / "assinaturas" / "quem-assina"
    linhas = [x.strip() for x in lista.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert tuple(linhas) == instalador.CHAVES_OFICIAIS and linhas
