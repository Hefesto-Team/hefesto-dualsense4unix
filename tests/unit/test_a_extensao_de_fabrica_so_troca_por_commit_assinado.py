"""A extensão de fábrica só troca o código por commit assinado por uma chave da lista.

Repositórios ``git init`` locais (``file://``), chaves ssh geradas no lar de mentira e a lista de
fábrica apontada para o repositório de mentira: nada fala com a rede.
"""
from __future__ import annotations

import json
import shutil
import sys
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

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

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


def test_a_lista_de_quem_assina_viaja_no_pacote() -> None:
    """D-1911-A-EXTENSAO-DE-FABRICA-SO-TROCA-POR-COMMIT-ASSINADO: a lista vai no pacote."""
    raiz = Path(__file__).resolve().parents[2]
    alvos = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"]["hatch"]["build"]["targets"]
    lista = instalador.LISTA_DE_QUEM_ASSINA
    assert alvos["wheel"]["shared-data"].get(lista) == f"share/hefesto-dualsense4unix/{lista}"
    assert lista in alvos["sdist"]["only-include"]


_CHAVE_DO_PACOTE = "pacote@hefesto.invalid ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAApacote"
_CHAVE_PLANTADA = "plantada@hefesto.invalid ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAplantada"


def _escrever_a_lista(base: Path, linha: str) -> None:
    lista = base / instalador.LISTA_DE_QUEM_ASSINA
    lista.parent.mkdir(parents=True, exist_ok=True)
    lista.write_text(f"# quem assina\n{linha}\n", encoding="utf-8")


@pytest.mark.parametrize("forma", [
    "checkout", "site-packages", "dist-packages", "user", "pacote-sem-a-lista"])
def test_a_lista_plantada_na_pasta_de_dados_nao_vale(
        curto: Path, monkeypatch: pytest.MonkeyPatch, forma: str) -> None:
    """D-1911-A-EXTENSAO-DE-FABRICA-SO-TROCA-POR-COMMIT-ASSINADO: a lista se lê só de onde o
    pacote que roda a pôs (a raiz do checkout, o ``share`` do prefixo do wheel); a da pasta de
    dados, ao lado do código das extensões e ao alcance do ``preparar``, nunca vale, e sem a do
    pacote nenhuma chave confere e a recusa vai ao diário."""
    from hefesto_dualsense4unix.utils import repo_files, xdg_paths

    prefixo = curto / "prefixo"
    casa = {"checkout": prefixo / "src", "site-packages": prefixo / "lib/python3.12/site-packages",
            "dist-packages": prefixo / "lib/python3/dist-packages",
            "user": prefixo / "lib/python3.12/site-packages",
            "pacote-sem-a-lista": prefixo / "lib/python3.12/site-packages"}[forma]
    pacote = casa / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    dados = curto / "dados"
    monkeypatch.setenv("XDG_DATA_HOME", str(prefixo / "share" if forma == "user" else dados))
    monkeypatch.setattr(instalador, "SHARE_DO_SISTEMA", (curto / "usr/share/hefesto",))
    monkeypatch.setattr(repo_files, "bases_de_instalacao",
                        lambda: (pacote.parents[1], xdg_paths.data_dir()))
    do_pacote = {"checkout": prefixo}.get(forma, prefixo / "share" / repo_files.NOME_NO_SHARE)
    if forma == "pacote-sem-a-lista":
        do_pacote.mkdir(parents=True)
    else:
        _escrever_a_lista(do_pacote, _CHAVE_DO_PACOTE)
    if forma != "user":
        _escrever_a_lista(xdg_paths.data_dir(), _CHAVE_PLANTADA)
    avisos: list[dict[str, object]] = []
    monkeypatch.setattr(instalador.logger, "warning",
                        lambda evento, **campos: avisos.append({"evento": evento, **campos}))

    chaves = instalador.chaves_da_lista(pacote=pacote)

    assert _CHAVE_PLANTADA not in chaves
    if forma == "pacote-sem-a-lista":
        assert chaves == ()
        assert [a["evento"] for a in avisos] == ["instalador_sem_a_lista_de_quem_assina"]
        assert str(xdg_paths.data_dir()) not in avisos[0]["procurada_em"]  # type: ignore[operator]
    else:
        assert chaves == (_CHAVE_DO_PACOTE,) and not avisos


@pytest.mark.parametrize("onde", ["pacote", "dados"])
def test_a_de_fabrica_so_troca_pela_chave_da_lista_do_pacote(
        lar: Lugares, mesa: dict[str, object], curto: Path,
        monkeypatch: pytest.MonkeyPatch, onde: str) -> None:
    """D-1911-A-EXTENSAO-DE-FABRICA-SO-TROCA-POR-COMMIT-ASSINADO: o commit assinado troca a de
    fábrica com a chave na lista que o pacote trouxe, e não troca com a mesma chave plantada na
    pasta de dados de uma instalação cujo pacote veio sem a lista."""
    from hefesto_dualsense4unix.utils import repo_files, xdg_paths

    prefixo = curto / "prefixo"
    pacote = prefixo / "lib/python3.12/site-packages/hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(curto / "dados"))
    monkeypatch.setattr(instalador, "SHARE_DO_SISTEMA", ())
    monkeypatch.setattr(repo_files, "bases_de_instalacao", lambda: (xdg_paths.data_dir(),))
    base = {"pacote": prefixo / "share" / repo_files.NOME_NO_SHARE,
            "dados": xdg_paths.data_dir()}[onde]
    _escrever_a_lista(base, *mesa["chaves"])  # type: ignore[arg-type]
    _publicar(mesa["origem"], "1.1.0", mesa["do_time"])  # type: ignore[arg-type]
    feito = atualizar("exemplo", lugares=lar, chaves=instalador.chaves_da_lista(pacote=pacote),
                      sozinha=True)
    assert feito.trocou is (onde == "pacote")
    assert _versao(lar) == {"pacote": "1.1.0", "dados": "1.0.0"}[onde]
