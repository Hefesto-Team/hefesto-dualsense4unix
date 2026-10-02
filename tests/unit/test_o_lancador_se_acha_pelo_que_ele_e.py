#!/usr/bin/env python3
"""LANCADOR-ACHADO-01 §5 — o produto acha o lançador que ninguém digitou."""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import jogos_locais as jl


def _desktop(pasta: pathlib.Path, stem: str, **campos: str) -> pathlib.Path:
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = ["[Desktop Entry]", "Type=Application"]
    linhas += [f"{k}={v}" for k, v in campos.items()]
    p = pasta / f"{stem}.desktop"
    p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return p


def test_um_lancador_que_a_lista_nao_conhece_e_encontrado(
    tmp_path: pathlib.Path,
) -> None:
    """`Bottles`, `itch`, `ES-DE` — nenhum está nos seis de fábrica."""
    _desktop(tmp_path, "com.usebottles.bottles",
             Name="Bottles", Categories="Game;PackageManager;")
    _desktop(tmp_path, "org.es_de.frontend",
             Name="ES-DE", Categories="Game;Emulator;")

    achados = jl.lancadores_por_conteudo([tmp_path])

    assert set(achados) == {"com.usebottles.bottles", "org.es_de.frontend"}
    assert achados["com.usebottles.bottles"] == "Bottles"


def test_o_stem_diferente_entra_sozinho(tmp_path: pathlib.Path) -> None:
    """`net.lutris.Lutris-beta` — o caso da tabela da §2."""
    _desktop(tmp_path, "net.lutris.Lutris-beta",
             Name="Lutris (beta)", Categories="Game;PackageManager;")

    assert "net.lutris.Lutris-beta" in jl.lancadores_por_conteudo([tmp_path])


@pytest.mark.parametrize("stem,campos", [
    ("org.gnome.TextEditor", {"Name": "Editor", "Categories": "Utility;TextEditor;"}),
    ("meow-steam-851100", {"Name": "Um jogo", "Categories": "Game;"}),
    ("debian-uxterm", {"Name": "UXTerm", "Categories": "System;TerminalEmulator;"}),
    ("oculto", {"Name": "Escondido", "Categories": "Game;Emulator;",
                "NoDisplay": "true"}),
])
def test_o_que_nao_e_lancador_nao_vira_cartao(
    tmp_path: pathlib.Path, stem: str, campos: dict[str, str],
) -> None:
    """*Busca que acha tudo não achou nada* — §5 da sprint."""
    _desktop(tmp_path, stem, **campos)

    assert jl.lancadores_por_conteudo([tmp_path]) == {}


def test_um_terminal_ao_lado_de_um_lancador_nao_contamina(
    tmp_path: pathlib.Path,
) -> None:
    """Os dois na mesma pasta: um entra, o outro não."""
    _desktop(tmp_path, "debian-uxterm", Name="UXTerm",
             Categories="System;TerminalEmulator;")
    _desktop(tmp_path, "org.libretro.RetroArch", Name="RetroArch",
             Categories="Game;Emulator;")

    assert list(jl.lancadores_por_conteudo([tmp_path])) == ["org.libretro.RetroArch"]


def test_a_primeira_pasta_vence(tmp_path: pathlib.Path) -> None:
    """`~/.local/share` sobrepõe `/usr/share` — é o que a spec XDG manda."""
    dela, sistema = tmp_path / "dela", tmp_path / "sistema"
    _desktop(dela, "org.libretro.RetroArch", Name="O dela",
             Categories="Game;Emulator;")
    _desktop(sistema, "org.libretro.RetroArch", Name="O do sistema",
             Categories="Game;Emulator;")

    assert jl.lancadores_por_conteudo([dela, sistema]) == {
        "org.libretro.RetroArch": "O dela"}


def test_sem_nome_o_stem_serve(tmp_path: pathlib.Path) -> None:
    """Um `.desktop` sem `Name=` ainda é um lançador — e o cartão precisa de"""
    _desktop(tmp_path, "sem.nome", Categories="Game;Emulator;")

    assert jl.lancadores_por_conteudo([tmp_path]) == {"sem.nome": "sem.nome"}


def test_arquivo_ilegivel_nao_derruba_a_varredura(
    tmp_path: pathlib.Path,
) -> None:
    """A aba monta a cada tique; uma exceção aqui apagaria a grade inteira."""
    (tmp_path / "torto.desktop").write_bytes(b"\xff\xfe[Desktop Entry]\x00")
    _desktop(tmp_path, "bom", Name="Bom", Categories="Game;Emulator;")

    assert jl.lancadores_por_conteudo([tmp_path]) == {"bom": "Bom"}


def test_pasta_que_nao_existe_e_pulada(tmp_path: pathlib.Path) -> None:
    """`pastas_de_atalhos` já filtra, mas quem chama pode passar outra coisa."""
    assert jl.lancadores_por_conteudo([tmp_path / "nao-existe"]) == {}


def test_as_categorias_dos_cinco_da_lista_bastam() -> None:
    """Os cinco de fábrica se declaram, e nenhum precisa do nome digitado."""
    for cats in ("Game;Emulator;", "Game;PackageManager;"):
        assert jl.e_lancador_de_jogos(
            f"[Desktop Entry]\nName=X\nCategories={cats}\n"), cats


def test_um_lancador_desconhecido_vira_cartao(monkeypatch) -> None:
    """O que a máquina declara ser entra na lista de procurados."""
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: {"com.usebottles.bottles": "Bottles"})

    novos = a07._achados_por_conteudo()

    assert [n.nome for n in novos] == ["Bottles"]
    assert novos[0].atalhos == ("com.usebottles.bottles",)
    assert not novos[0].declarado


def test_o_que_ja_e_de_fabrica_nao_vira_segundo_cartao(monkeypatch) -> None:
    """Chave repetida ENSINA o primeiro cartão; não cria um segundo."""
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: {"net.lutris.Lutris": "Lutris",
                         "org.libretro.RetroArch": "RetroArch"})

    assert a07._achados_por_conteudo() == ()


def test_a_varredura_quebrada_nao_derruba_a_aba(monkeypatch) -> None:
    """A vigia da aba chama isto; uma pasta ilegível não pode levar a tela."""
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    def explode(*_a, **_k):
        raise OSError("o disco sumiu")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        explode)

    assert a07._achados_por_conteudo() == ()
