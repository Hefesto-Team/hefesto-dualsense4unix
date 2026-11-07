"""O «Editar» do ``meu.css`` não entrega ao editor o que a caixa plantou.

``<dados>/<id>`` é escrita pela caixa da extensão: ``meu.css`` pode ser pasta, FIFO, soquete ou
link. O gesto é conduzido de verdade (``editar_o_css_da_modificacao``), com só o ``xdg-open``
trocado por quem anota o que recebeu e o que estava no disco naquela hora.
"""
from __future__ import annotations

import json
import os
import re
import socket
import stat
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

import hefesto_dualsense4unix
from hefesto_dualsense4unix.mods import instalador, meu_css

INTERFACE = Path(hefesto_dualsense4unix.__file__).parent / "interface"
OPCAO_DO_CSS = {"id": "meu_css", "rotulo": "Usar o meu CSS", "tipo": "css",
                "padrao": False}  # (noqa-acento)
SEGREDO = "o que mora fora da caixa"


def _a07() -> Any:
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


def _instalada(lg: instalador.Lugares, mod_id: str) -> None:
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tema.css").write_text(":root{--green:#1d7a3c}", encoding="utf-8")
    manifesto = {"id": mod_id, "nome": mod_id, "api": ">=2,<3", "licenca": "MIT",
                 "versao": "1.0.0", "tipos": ["tema"],  # (noqa-acento)
                 "tema": {"arquivo": "tema.css"}, "permissoes": ["tema"],  # (noqa-acento)
                 "opcoes": [OPCAO_DO_CSS]}  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[mod_id] = instalador.Entrada(
        id=mod_id, nome=mod_id, versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=["tema"], ligada=True, ligada_em="2026-11-07T10:00:00")
    instalador.gravar_registro(lg.registro, registro)


class _Ponte:
    escolher_arquivo = None


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[instalador.Lugares]:
    lg = instalador.Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                            registro=tmp_path / "mods.json", estado=tmp_path / "estado.json")
    monkeypatch.setattr(instalador.Lugares, "do_xdg", classmethod(lambda cls: lg))
    a07 = _a07()
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    a07._ESCOLHA.limpar()
    yield lg
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    a07._ESCOLHA.limpar()


@pytest.fixture
def ctx() -> Any:
    sys.path.insert(0, str(INTERFACE))
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


@pytest.fixture
def editor(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, int]]:
    """O que o editor recebeu: o caminho e o modo que ele tinha, sem seguir link, naquela hora."""
    abertos: list[tuple[Path, int]] = []
    monkeypatch.setattr(_a07(), "_abrir_no_editor",
                        lambda alvo: abertos.append((alvo, os.lstat(alvo).st_mode)))
    return abertos


def _clicar(ctx: Any, mod_id: str = "tema-x") -> None:
    _a07().editar_o_css_da_modificacao(ctx, {"v": f"{mod_id}:meu_css"}, _Ponte())


def _pasta(alvo: Path, fora: Path) -> None:
    alvo.mkdir()
    (alvo / "dentro.txt").write_text("plantado", encoding="utf-8")


def _pasta_com_link(alvo: Path, fora: Path) -> None:
    alvo.mkdir()
    (alvo / "para-fora").symlink_to(fora)


def _fifo(alvo: Path, fora: Path) -> None:
    os.mkfifo(alvo)


def _soquete(alvo: Path, fora: Path) -> None:
    with socket.socket(socket.AF_UNIX) as servidor:
        servidor.bind(os.path.relpath(alvo))


def _link(alvo: Path, fora: Path) -> None:
    alvo.symlink_to(fora)


def _link_quebrado(alvo: Path, fora: Path) -> None:
    alvo.symlink_to(fora.parent / "nada-aqui")


PLANTIOS = {"pasta": _pasta, "pasta_com_link": _pasta_com_link, "fifo": _fifo,
            "soquete": _soquete, "link": _link, "link_quebrado": _link_quebrado}


@pytest.mark.parametrize("plantio", PLANTIOS.values(), ids=PLANTIOS.keys())
def test_o_plantio_sai_do_caminho_e_o_editor_recebe_o_exemplo(
        lar: instalador.Lugares, ctx: Any, editor: list[tuple[Path, int]], tmp_path: Path,
        plantio: Callable[[Path, Path], None], monkeypatch: pytest.MonkeyPatch) -> None:
    _instalada(lar, "tema-x")
    fora = tmp_path / "segredo.txt"
    fora.write_text(SEGREDO, encoding="utf-8")
    alvo = meu_css.caminho("tema-x", lar)
    alvo.parent.mkdir(parents=True)
    monkeypatch.chdir(alvo.parent)
    plantio(alvo, fora)
    assert not stat.S_ISREG(os.lstat(alvo).st_mode)

    _clicar(ctx)

    assert [caminho for caminho, _ in editor] == [alvo]
    assert stat.S_ISREG(editor[0][1])
    assert alvo.read_text(encoding="utf-8") == meu_css.EXEMPLO
    assert fora.read_text(encoding="utf-8") == SEGREDO
    assert [p.name for p in alvo.parent.iterdir()] == [meu_css.NOME_DO_ARQUIVO]
    assert meu_css.ler("tema-x", lar).recusa == ""


def test_o_plantio_de_uma_extensao_nao_mexe_na_folha_da_outra(
        lar: instalador.Lugares, ctx: Any, editor: list[tuple[Path, int]]) -> None:
    _instalada(lar, "tema-x")
    _instalada(lar, "tema-y")
    plantada = meu_css.caminho("tema-x", lar)
    plantada.mkdir(parents=True)
    da_outra = meu_css.caminho("tema-y", lar)
    da_outra.parent.mkdir(parents=True)
    da_outra.write_text(".b{color:red}", encoding="utf-8")

    _clicar(ctx, "tema-x")
    _clicar(ctx, "tema-y")

    assert [caminho for caminho, _ in editor] == [plantada, da_outra]
    assert da_outra.read_text(encoding="utf-8") == ".b{color:red}"


def test_o_arquivo_grande_demais_continua_sendo_da_pessoa(
        lar: instalador.Lugares, ctx: Any, editor: list[tuple[Path, int]]) -> None:
    """O arquivo que passou do teto é o que a pessoa precisa abrir para encurtar."""
    _instalada(lar, "tema-x")
    alvo = meu_css.caminho("tema-x", lar)
    alvo.parent.mkdir(parents=True)
    texto = ".a{color:red}\n" * 2000
    alvo.write_text(texto, encoding="utf-8")

    _clicar(ctx)

    assert [caminho for caminho, _ in editor] == [alvo]
    assert alvo.read_text(encoding="utf-8") == texto


def test_o_arquivo_que_nao_abre_se_diz_e_nao_se_reescreve(
        lar: instalador.Lugares, ctx: Any, editor: list[tuple[Path, int]]) -> None:
    """Arquivo comum sem leitura é da pessoa: a tela diz, o editor não abre e o texto fica."""
    if os.geteuid() == 0:
        pytest.skip("root abre arquivo sem permissão")
    _instalada(lar, "tema-x")
    alvo = meu_css.caminho("tema-x", lar)
    alvo.parent.mkdir(parents=True)
    alvo.write_text(".a{color:red}", encoding="utf-8")
    alvo.chmod(0)

    with pytest.raises(RuntimeError, match="O seu CSS não abriu"):
        _clicar(ctx)

    alvo.chmod(0o600)
    assert editor == [] and alvo.read_text(encoding="utf-8") == ".a{color:red}"
    assert re.search(r'class="[^"]*recusa[^"]*"[^>]*>O seu CSS não abriu\.',
                     _a07()._MEXIDA.html_mod)

    _clicar(ctx)

    assert "O seu CSS não abriu" not in _a07()._MEXIDA.html_mod
    assert [caminho for caminho, _ in editor] == [alvo]


def test_a_pasta_que_nao_aceita_escrita_se_diz_sem_abrir_nada(
        lar: instalador.Lugares, ctx: Any, editor: list[tuple[Path, int]]) -> None:
    if os.geteuid() == 0:
        pytest.skip("root escreve em pasta sem permissão")
    _instalada(lar, "tema-x")
    alvo = meu_css.caminho("tema-x", lar)
    alvo.parent.mkdir(parents=True)
    alvo.parent.chmod(0o500)
    try:
        with pytest.raises(RuntimeError, match="O seu CSS não abriu"):
            _clicar(ctx)
    finally:
        alvo.parent.chmod(0o700)
    assert editor == [] and "O seu CSS não abriu" in _a07()._MEXIDA.html_mod
