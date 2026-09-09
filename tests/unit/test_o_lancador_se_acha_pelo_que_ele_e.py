#!/usr/bin/env python3
"""LANCADOR-ACHADO-01 §5 — o produto acha o lançador que ninguém digitou.

**A FRASE QUE ORIGINOU A SPRINT foi dela, e ela classificou errado a culpa:**
*"isso é uma falha de produto e a culpa é minha."*

**A culpa NÃO é dela.** Um produto que exige de quem usa a forma certa de
instalar terceiriza uma pergunta que ele mesmo deveria responder. Ela instalou
o Lutris de algum jeito e o Hefesto disse NÃO ACHEI — o defeito nasceu ali.

## O que a busca fazia

`desenho_dos_lancadores.SemCenso` traz duas listas ADIVINHADAS na hora em que
alguém escreveu o arquivo::

    SemCenso("lutris", "Lutris", ("net.lutris.Lutris", "lutris"), ("lutris",))

**O produto não procurava "um lançador de jogos". Procurava cinco strings.** E
a assimetria que prova o ponto está no próprio arquivo: o cartão do Flatpak
procura o COMANDO `flatpak` e acha; o do Lutris procura o NOME
`net.lutris.Lutris`. *Só o primeiro é uma pergunta sobre o mundo.*

## O que estas réguas medem

As duas mordidas que a §5 encomenda, e as duas com casa de mentira:

* um `.desktop` de um lançador que a lista **não conhece** tem de aparecer;
* um `.desktop` que **não é lançador** (um editor de texto) não pode virar
  cartão. *Busca que acha tudo não achou nada.*

E a armadilha que a máquina dela trouxe de graça: `debian-uxterm` declara
`Categories=System;TerminalEmulator;`, e uma busca por substring o
transformaria num lançador de jogos.
"""
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


# ---------------------------------------------------------------------------
# 1. A MORDIDA DA §5 — o lançador que a lista NÃO conhece
# ---------------------------------------------------------------------------
def test_um_lancador_que_a_lista_nao_conhece_e_encontrado(
    tmp_path: pathlib.Path,
) -> None:
    """`Bottles`, `itch`, `ES-DE` — nenhum está nos seis de fábrica.

    Com a busca de hoje eles não aparecem, e o cartão diria NÃO LOCALIZADO
    sobre um programa instalado e funcionando.

    **A MORDIDA:** troque `e_lancador_de_jogos` por um casamento com a lista
    de nomes e esta linha reprova — que é o estado do produto até 09/09/2026.
    """
    _desktop(tmp_path, "com.usebottles.bottles",
             Name="Bottles", Categories="Game;PackageManager;")
    _desktop(tmp_path, "org.es_de.frontend",
             Name="ES-DE", Categories="Game;Emulator;")

    achados = jl.lancadores_por_conteudo([tmp_path])

    assert set(achados) == {"com.usebottles.bottles", "org.es_de.frontend"}
    assert achados["com.usebottles.bottles"] == "Bottles"


def test_o_stem_diferente_entra_sozinho(tmp_path: pathlib.Path) -> None:
    """`net.lutris.Lutris-beta` — o caso da tabela da §2.

    **A MORDIDA:** a mesma de cima; por nome, `-beta` some.
    """
    _desktop(tmp_path, "net.lutris.Lutris-beta",
             Name="Lutris (beta)", Categories="Game;PackageManager;")

    assert "net.lutris.Lutris-beta" in jl.lancadores_por_conteudo([tmp_path])


# ---------------------------------------------------------------------------
# 2. O NEGATIVO QUE IMPORTA — busca que acha tudo não achou nada
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("stem,campos", [
    ("org.gnome.TextEditor", {"Name": "Editor", "Categories": "Utility;TextEditor;"}),
    # O JOGO não é lançador: `Game` sozinho não decide. Medido na máquina dela
    # em 09/09/2026 — 23 dos 32 `.desktop` de `~/.local/share/applications`
    # trazem `Categories=Game`, e quase todos são jogos instalados. Um cartão
    # por jogo daria 23 onde ela espera seis.
    ("meow-steam-851100", {"Name": "Um jogo", "Categories": "Game;"}),
    # A ARMADILHA DA MÁQUINA DELA: `TerminalEmulator` contém "Emulator".
    ("debian-uxterm", {"Name": "UXTerm", "Categories": "System;TerminalEmulator;"}),
    # Escondido do menu não é cartão.
    ("oculto", {"Name": "Escondido", "Categories": "Game;Emulator;",
                "NoDisplay": "true"}),
])
def test_o_que_nao_e_lancador_nao_vira_cartao(
    tmp_path: pathlib.Path, stem: str, campos: dict[str, str],
) -> None:
    """*Busca que acha tudo não achou nada* — §5 da sprint.

    **A MORDIDA de cada linha:**

    * tire o `"Game" not in cats` e o editor de texto vira cartão;
    * tire o `cats & _CATEGORIAS_DE_LANCADOR` e os 23 jogos dela viram 23
      cartões;
    * compare `Categories` por SUBSTRING e o `debian-uxterm` vira lançador;
    * tire a guarda do `NoDisplay` e o que a spec manda esconder aparece.
    """
    _desktop(tmp_path, stem, **campos)

    assert jl.lancadores_por_conteudo([tmp_path]) == {}


def test_um_terminal_ao_lado_de_um_lancador_nao_contamina(
    tmp_path: pathlib.Path,
) -> None:
    """Os dois na mesma pasta: um entra, o outro não.

    É o arranjo real da máquina dela, e o caso que uma régua com UM arquivo
    por vez não pega.
    """
    _desktop(tmp_path, "debian-uxterm", Name="UXTerm",
             Categories="System;TerminalEmulator;")
    _desktop(tmp_path, "org.libretro.RetroArch", Name="RetroArch",
             Categories="Game;Emulator;")

    assert list(jl.lancadores_por_conteudo([tmp_path])) == ["org.libretro.RetroArch"]


# ---------------------------------------------------------------------------
# 3. O CONTRATO DA VARREDURA
# ---------------------------------------------------------------------------
def test_a_primeira_pasta_vence(tmp_path: pathlib.Path) -> None:
    """`~/.local/share` sobrepõe `/usr/share` — é o que a spec XDG manda.

    **A MORDIDA:** tire o `if arq.stem in achados: continue` e o nome do
    sistema sobrescreve o que ela instalou por cima.
    """
    dela, sistema = tmp_path / "dela", tmp_path / "sistema"
    _desktop(dela, "org.libretro.RetroArch", Name="O dela",
             Categories="Game;Emulator;")
    _desktop(sistema, "org.libretro.RetroArch", Name="O do sistema",
             Categories="Game;Emulator;")

    assert jl.lancadores_por_conteudo([dela, sistema]) == {
        "org.libretro.RetroArch": "O dela"}


def test_sem_nome_o_stem_serve(tmp_path: pathlib.Path) -> None:
    """Um `.desktop` sem `Name=` ainda é um lançador — e o cartão precisa de
    alguma palavra.

    **A MORDIDA:** devolva `""` e o cartão nasce sem título.
    """
    _desktop(tmp_path, "sem.nome", Categories="Game;Emulator;")

    assert jl.lancadores_por_conteudo([tmp_path]) == {"sem.nome": "sem.nome"}


def test_arquivo_ilegivel_nao_derruba_a_varredura(
    tmp_path: pathlib.Path,
) -> None:
    """A aba monta a cada tique; uma exceção aqui apagaria a grade inteira.

    **A MORDIDA:** tire o `errors="replace"` / o `except OSError` e um byte
    torto leva a aba junto.
    """
    (tmp_path / "torto.desktop").write_bytes(b"\xff\xfe[Desktop Entry]\x00")
    _desktop(tmp_path, "bom", Name="Bom", Categories="Game;Emulator;")

    assert jl.lancadores_por_conteudo([tmp_path]) == {"bom": "Bom"}


def test_pasta_que_nao_existe_e_pulada(tmp_path: pathlib.Path) -> None:
    """`pastas_de_atalhos` já filtra, mas quem chama pode passar outra coisa."""
    assert jl.lancadores_por_conteudo([tmp_path / "nao-existe"]) == {}


# ---------------------------------------------------------------------------
# 4. O QUE A MÁQUINA DELA DIZ HOJE — a prova de que os cinco entram sozinhos
# ---------------------------------------------------------------------------
def test_as_categorias_dos_cinco_da_lista_bastam() -> None:
    """Os cinco de fábrica se declaram, e nenhum precisa do nome digitado.

    Medido em `~/.local/share/flatpak/exports/share/applications` em
    09/09/2026 — as `Categories` são as que os próprios programas publicam:

    ==============================  ====================
    `org.DolphinEmu.dolphin-emu`    `Game;Emulator;`
    `io.mgba.mGBA`                  `Game;Emulator;`
    `org.libretro.RetroArch`        `Game;Emulator;`
    `com.heroicgameslauncher.hgl`   `Game;PackageManager;`
    `net.lutris.Lutris`             `Game;PackageManager;`
    ==============================  ====================

    **A MORDIDA:** tire `PackageManager` de `_CATEGORIAS_DE_LANCADOR` e o
    Heroic e o Lutris — os dois que ela mais usa — somem da aba.
    """
    for cats in ("Game;Emulator;", "Game;PackageManager;"):
        assert jl.e_lancador_de_jogos(
            f"[Desktop Entry]\nName=X\nCategories={cats}\n"), cats


# ---------------------------------------------------------------------------
# 5. A LIGAÇÃO COM A ABA — o achado entra pela porta que já existe
# ---------------------------------------------------------------------------
def test_um_lancador_desconhecido_vira_cartao(monkeypatch) -> None:
    """O que a máquina declara ser entra na lista de procurados.

    **A MORDIDA:** faça `_achados_por_conteudo` devolver `()` e o Bottles
    instalado volta a não existir para o produto.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: {"com.usebottles.bottles": "Bottles"})

    novos = a07._achados_por_conteudo()

    assert [n.nome for n in novos] == ["Bottles"]
    assert novos[0].atalhos == ("com.usebottles.bottles",)
    #: ELA NÃO DECLAROU NADA — então não há declaração a esquecer, e o cartão
    #: não ganha o botão «Tirar».
    assert not novos[0].declarado


def test_o_que_ja_e_de_fabrica_nao_vira_segundo_cartao(monkeypatch) -> None:
    """Chave repetida ENSINA o primeiro cartão; não cria um segundo.

    Dois cartões com a mesma chave seriam pior que inúteis: os endereços do
    desenho levam a chave como prefixo (`data-campo="retroarch-selo"`), e o
    piloto pintaria o valor de um nos DOIS.

    **MEDIDO NA MÁQUINA DELA, 09/09/2026:** os cinco lançadores achados por
    conteúdo são exatamente os cinco de fábrica — e o resultado é **zero**
    cartões novos, que é a resposta certa.

    **A MORDIDA:** tire o `if stem not in de_fabrica` e a aba ganha cinco
    cartões duplicados.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: {"net.lutris.Lutris": "Lutris",
                         "org.libretro.RetroArch": "RetroArch"})

    assert a07._achados_por_conteudo() == ()


def test_a_varredura_quebrada_nao_derruba_a_aba(monkeypatch) -> None:
    """A vigia da aba chama isto; uma pasta ilegível não pode levar a tela.

    **A MORDIDA:** tire o `except Exception` e a aba morre com o disco dela.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    def explode(*_a, **_k):
        raise OSError("o disco sumiu")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        explode)

    assert a07._achados_por_conteudo() == ()
