"""A extensão do Modo imersão entra na lista de fábrica (02/11/2026).

A lista de fábrica (``mods/de_fabrica_por_endereco.json``) tinha só o gerenciador de tema. Agora
traz também a extensão ``imersao``, do repositório ``Hefesto-Team/hefesto-mod-imersao``, ligada.
O ``id`` da lista é o do manifesto publicado: o ``trazer`` confere o registro por ele.

A régua instala, num lar de mentira, um repositório ``file://`` com o mesmo formato do manifesto
publicado (processo, as permissões, o ``modos_de_aba``). Um campo desconhecido no manifesto é
recusado no install.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from hefesto_dualsense4unix.mods import de_fabrica_por_endereco as fabrica
from hefesto_dualsense4unix.mods.instalador import Lugares, ler_registro
from tests.unit.test_a_extensao_de_fabrica_por_endereco_chega_pelo_install import _git, _lista

ID = "imersao"
ENDERECO = "https://github.com/Hefesto-Team/hefesto-mod-imersao"


def _manifesto(**extra: Any) -> dict[str, Any]:
    return {
        "id": ID, "nome": "Modo imersão", "versao": "0.4.1",  # (noqa-acento)
        "api": ">=2,<3", "licenca": "GPL-3.0-or-later", "tipos": ["processo"],
        "processo": {"executar": ["python3", "-I", "servidor.py"]},
        "permissoes": ["ler:conexao", "ler:perfil.jogo", "ler:jogo.vibracao",  # (noqa-acento)
                       "ler:entradas", "ler:botoes", "ler:movimento", "escrever:luz",
                       "escrever:vibracao", "escrever:gatilho", "publicar:acessorios.estado",
                       "rede:nenhuma"],
        "descricao": "O controle reage ao que acontece no jogo.",  # (noqa-acento)
        "opcoes": [], "agora": ["perfil"],  # (noqa-acento)
        "modos_de_aba": [{"id": ID, "rotulo": "Modo imersão",
                          "dica": "A receita do jogo comanda a vibração, os gatilhos e a luz",
                          "abas": ["02", "03", "04", "05", "10"]}],
        **extra,
    }


def _repo(raiz: Path, **extra: Any) -> str:
    pasta = raiz / "repos" / ID
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(**extra)), encoding="utf-8")
    (pasta / "servidor.py").write_text("", encoding="utf-8")
    _git(pasta, "init", "-q")
    _git(pasta, "add", "hefesto-mod.json", "servidor.py")
    _git(pasta, "commit", "-q", "-m", "um")
    return f"file://{pasta}"


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    lugares = Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                      dados=tmp_path / "dados",
                      registro=tmp_path / "config" / "mods.json",
                      estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


def _a_da_fabrica() -> fabrica.DeFabrica:
    achadas = [item for item in fabrica.ler() if item.id == ID]
    assert len(achadas) == 1, "a lista de fábrica não traz a extensão do Modo imersão"
    return achadas[0]


def test_a_lista_de_fabrica_traz_a_extensao_ligada() -> None:
    item = _a_da_fabrica()
    assert item.endereco == ENDERECO
    assert item.ligar is True
    assert len({i.id for i in fabrica.ler()}) == len(fabrica.ler()), "id repetido na lista"


def test_todo_endereco_de_fabrica_e_https_do_hefesto_team() -> None:
    for item in fabrica.ler():
        for endereco in (item.endereco, *item.enderecos_antigos):
            partes = urlparse(endereco)
            assert partes.scheme == "https", endereco
            assert partes.netloc == "github.com", endereco
            assert partes.path.split("/")[1] == "Hefesto-Team", endereco


def test_o_install_traz_a_extensao_e_a_liga(lg: Lugares, tmp_path: Path) -> None:
    item = _a_da_fabrica()
    lista = _lista(tmp_path, {**item.model_dump(), "endereco": _repo(tmp_path)})
    feitos = fabrica.trazer(lugares=lg, arquivo=lista)
    assert [(f.id, f.o_que) for f in feitos] == [(ID, "ligada")], feitos
    assert ler_registro(lg.registro)[ID].ligada


def test_o_campo_desconhecido_no_manifesto_e_recusado_no_install(lg: Lugares,
                                                                   tmp_path: Path) -> None:
    item = _a_da_fabrica()
    lista = _lista(tmp_path, {**item.model_dump(),
                              "endereco": _repo(tmp_path, campo_que_nao_existe=1)})
    feitos = fabrica.trazer(lugares=lg, arquivo=lista)
    assert [(f.id, f.o_que) for f in feitos] == [(ID, "recusada")], feitos
    assert ID not in ler_registro(lg.registro)


def test_o_aviso_do_manifesto_deixa_a_extensao_desligada(lg: Lugares, tmp_path: Path) -> None:
    item = _a_da_fabrica()
    lista = _lista(tmp_path, {**item.model_dump(),
                              "endereco": _repo(tmp_path, aviso="Extensão independente.")})
    feitos = fabrica.trazer(lugares=lg, arquivo=lista)
    assert [(f.id, f.o_que) for f in feitos] == [(ID, "instalada")], feitos
    assert not ler_registro(lg.registro)[ID].ligada
