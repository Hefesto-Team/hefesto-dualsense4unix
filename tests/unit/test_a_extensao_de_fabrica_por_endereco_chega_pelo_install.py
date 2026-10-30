"""A extensão que o install traz de um endereço git chega instalada e ligada, uma vez só.

A sprint é a O-GERENCIADOR-DE-TEMA-E-A-EXTENSAO-DE-FABRICA-01. A lista é dado
(``mods/de_fabrica_por_endereco.json``); o ``mod de-fabrica`` a traz sem perguntar. Extensões
FALSAS, de tema e sem processo, num repositório git de mentira servido por ``file://``.

MORDIDAS (30/10/2026, executadas sobre a cura e devolvidas):

- o ``ligar_`` arrancado do ``_uma`` reprova ``test_a_que_falta_chega_instalada_e_ligada``;
- o «já está» sem conferir o registro (sempre instala) reprova
  ``test_a_que_quem_usa_desligou_fica_desligada``;
- a troca do endereço antigo arrancada reprova ``test_o_endereco_antigo_passa_a_ser_o_novo``;
- o ``aviso_visto`` do ligar trocado pelo aviso do manifesto reprova
  ``test_o_aviso_nunca_se_aceita_por_quem_usa``.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.mods import de_fabrica_por_endereco as fabrica
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import Lugares, gravar_registro, ler_registro

NOVA, ANTIGA = "pintura-nova", "pintura-velha"
CODIGO = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


def _git(raiz: Path, *args: str) -> None:
    ambiente = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@exemplo.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@exemplo.invalid",
        "PATH": os.environ["PATH"], "HOME": str(raiz),
    }
    subprocess.run(["git", *args], cwd=raiz, env=ambiente, check=True, capture_output=True)


def _repo(raiz: Path, mod_id: str, **extra: Any) -> str:
    """Um repositório git com uma extensão de tema de mentira; devolve o endereço ``file://``."""
    pasta = raiz / "repos" / mod_id
    pasta.mkdir(parents=True)
    manifesto: dict[str, Any] = {
        "id": mod_id, "nome": mod_id.replace("-", " ").capitalize(),
        "versao": "1.0.0",  # (noqa-acento)
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"], "tema": {},
        "permissoes": ["tema"], "descricao": "Muda um detalhe.",  # (noqa-acento)
        "opcoes": [], **extra,  # (noqa-acento)
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    _git(pasta, "init", "-q")
    _git(pasta, "add", "hefesto-mod.json")
    _git(pasta, "commit", "-q", "-m", "um")
    return f"file://{pasta}"


def _lista(raiz: Path, *itens: dict[str, Any]) -> Path:
    arquivo = raiz / "lista.json"
    corpo = {"formato": 1, "extensoes": list(itens)}  # (noqa-acento)
    arquivo.write_text(json.dumps(corpo), encoding="utf-8")
    return arquivo


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    lugares = Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                      dados=tmp_path / "dados",
                      registro=tmp_path / "config" / "mods.json",
                      estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


def test_a_lista_do_pacote_se_le_e_aponta_para_o_time() -> None:
    lista = fabrica.ler()
    assert lista
    for item in lista:
        assert item.endereco.startswith("https://github.com/Hefesto-Team/")
        assert item.endereco not in item.enderecos_antigos


def test_o_produto_nao_conhece_o_nome_da_extensao() -> None:
    ids = [item.id for item in fabrica.ler()]
    for arquivo in (CODIGO / "mods" / "de_fabrica_por_endereco.py", CODIGO / "cli" / "cmd_mod.py"):
        texto = arquivo.read_text(encoding="utf-8")
        assert not [i for i in ids if i in texto], arquivo


def test_a_que_falta_chega_instalada_e_ligada(lg: Lugares, tmp_path: Path) -> None:
    endereco = _repo(tmp_path, NOVA)
    feitos = fabrica.trazer(lugares=lg, arquivo=_lista(tmp_path, {"id": NOVA,
                                                                  "endereco": endereco}))
    assert [(f.id, f.o_que) for f in feitos] == [(NOVA, "ligada")]
    entrada = ler_registro(lg.registro)[NOVA]
    assert entrada.ligada and entrada.endereco == endereco and entrada.origem != "local"


def test_a_que_quem_usa_desligou_fica_desligada(lg: Lugares, tmp_path: Path) -> None:
    lista = _lista(tmp_path, {"id": NOVA, "endereco": _repo(tmp_path, NOVA)})
    fabrica.trazer(lugares=lg, arquivo=lista)
    instalador.desligar(NOVA, lugares=lg)
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_o_endereco_antigo_passa_a_ser_o_novo(lg: Lugares, tmp_path: Path) -> None:
    endereco = _repo(tmp_path, NOVA)
    antigo = "https://github.com/Hefesto-Team/pintura-de-antes"
    fabrica.trazer(lugares=lg, arquivo=_lista(tmp_path, {"id": NOVA, "endereco": endereco}))
    registro = ler_registro(lg.registro)
    registro[NOVA].endereco = antigo + ".git"
    gravar_registro(lg.registro, registro)
    lista = _lista(tmp_path, {"id": NOVA, "endereco": endereco, "enderecos_antigos": [antigo]})
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["endereco_novo"]
    entrada = ler_registro(lg.registro)[NOVA]
    assert entrada.endereco == endereco and entrada.ligada
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]


def test_a_que_veio_de_uma_pasta_fica_como_esta(lg: Lugares, tmp_path: Path) -> None:
    pasta = Path(_repo(tmp_path, NOVA).removeprefix("file://"))
    instalador.instalar(str(pasta), lugares=lg)
    lista = _lista(tmp_path, {"id": NOVA, "endereco": "https://exemplo.invalid/x",
                              "enderecos_antigos": [str(pasta)]})
    assert [f.o_que for f in fabrica.trazer(lugares=lg, arquivo=lista)] == ["ja_estava"]
    assert ler_registro(lg.registro)[NOVA].endereco == str(pasta.resolve())


def test_o_aviso_nunca_se_aceita_por_quem_usa(lg: Lugares, tmp_path: Path) -> None:
    endereco = _repo(tmp_path, NOVA, aviso="Troca as cores.")
    feitos = fabrica.trazer(lugares=lg, arquivo=_lista(tmp_path, {"id": NOVA,
                                                                  "endereco": endereco}))
    assert feitos[0].o_que == "instalada" and "Troca as cores." in feitos[0].frase
    assert not ler_registro(lg.registro)[NOVA].ligada


def test_a_que_substitui_manda_a_antiga_embora(lg: Lugares, tmp_path: Path) -> None:
    instalador.instalar(_repo(tmp_path, ANTIGA), lugares=lg)
    endereco = _repo(tmp_path, NOVA, substitui=[ANTIGA])
    fabrica.trazer(lugares=lg, arquivo=_lista(tmp_path, {"id": NOVA, "endereco": endereco}))
    registro = ler_registro(lg.registro)
    assert ANTIGA not in registro and registro[NOVA].ligada


def test_a_que_falha_nao_segura_as_outras_e_a_cli_sai_com_erro(
        lg: Lugares, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lista = _lista(tmp_path, {"id": ANTIGA, "endereco": f"file://{tmp_path}/nao-existe"},
                   {"id": NOVA, "endereco": _repo(tmp_path, NOVA)})
    monkeypatch.setattr(fabrica, "ARQUIVO", lista)
    monkeypatch.setattr(fabrica.trazer, "__kwdefaults__",
                        {**(fabrica.trazer.__kwdefaults__ or {}), "arquivo": lista})
    saiu = CliRunner().invoke(cmd_mod.app, ["de-fabrica"])
    assert saiu.exit_code == 1, saiu.output
    assert f"{ANTIGA}: recusada" in saiu.output and f"{NOVA}: ligada" in saiu.output
    assert ler_registro(lg.registro)[NOVA].ligada
