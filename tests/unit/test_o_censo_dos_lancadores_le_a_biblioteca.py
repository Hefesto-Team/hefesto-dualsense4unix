#!/usr/bin/env python3
"""LANCADORES-ZERO-01 — o censo lê a biblioteca dos cinco que não são a Steam.

**A QUEIXA DELA, 08/09/2026** — a digitação é dela, palavra por palavra
(noqa-acento: citação literal): *"a aba lançadores tá identificando nada."*

O produto ACHAVA os seis — o cabeçalho dizia *"6 encontrados"*. O que faltava
era o que o cartão da Steam faz e os outros cinco não faziam: **ler a
biblioteca**. Sem leitor, o selo caía em `NÃO SEI`, e um selo grande e negativo
sobre um lançador instalado lê-se como *"não identificou"*.

**O LAR É DE MENTIRA**, e é o que permite medir os CINCO leitores tendo UM
lançador instalado: cada caso monta no `tmp_path` a árvore exata que aquele
lançador escreve — a de flatpak, que é a dela.

**O CASO DELA ESTÁ AQUI, com os números medidos no disco em 09/09/2026:** 35
jogos da Epic e 2 da GOG, **zero instalados**, e nenhum `install_info`. Esse
estado parecia defeito e é leitura certa — a biblioteca lista o que a CONTA
tem, não o que está baixado.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

HEROIC_ID = "com.heroicgameslauncher.hgl"


def _flatpak(lar: pathlib.Path, app_id: str, sub: str) -> pathlib.Path:
    """A pasta de config de um flatpak — `~/.var/app/<id>/config/<sub>`."""
    p = lar / ".var/app" / app_id / "config" / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def _escrever(caminho: pathlib.Path, dado: object) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dado), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. NUNCA ABERTO é uma RESPOSTA — e melhor que "não sei"
# ---------------------------------------------------------------------------
def test_lancador_nunca_aberto_diz_o_que_fazer(tmp_path: pathlib.Path) -> None:
    """*"Abra o Lutris uma vez e eu leio a biblioteca"* — §3 da sprint.

    Não é dívida nossa: não há o que ler. O selo velho dizia `NÃO SEI`, que
    ela leu como *"não identificou"*.

    **A MORDIDA:** faça `_pasta_de_config` devolver a pasta mesmo sem ela
    existir e o estado vira `LIDO` com zero jogos — o cartão passa a dizer
    "biblioteca vazia" sobre um programa que nunca rodou.
    """
    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert b.estado == censo.NUNCA_ABERTO
    assert "Abra Lutris" in b.resumo
    assert b.jogos == []


def test_quem_nao_e_lancador_nao_ganha_a_frase_da_biblioteca(
    tmp_path: pathlib.Path,
) -> None:
    """O «Flatpak» é o RUNTIME dos outros cinco — §5.4 da sprint.

    **ACHADO NA PRIMEIRA CORRIDA NA MÁQUINA DELA, 09/09/2026:** ele caía em
    `NUNCA_ABERTO` e o cartão dizia *"Abra Flatpak uma vez e o Hefesto lê a
    biblioteca"* — uma frase falsa sobre um programa que ela não abre.

    **A MORDIDA:** devolva `NUNCA_ABERTO` no ramo sem leitor e a frase volta.
    """
    b = censo.biblioteca_de("Flatpak", lar=tmp_path)

    assert b.estado == censo.SEM_BIBLIOTECA
    assert b.resumo == ""
    assert not censo.sabe_ler("Flatpak")


# ---------------------------------------------------------------------------
# 2. O HEROIC — as três lojas, e o caso dela
# ---------------------------------------------------------------------------
def test_o_heroic_le_as_tres_lojas(tmp_path: pathlib.Path) -> None:
    """Epic (legendary), GOG e Amazon (nile) num cartão só.

    **A Epic fica dentro do Heroic**, decisão dela de 08/09 (*"dentro
    heróic"*) — ela não ganha cartão próprio.  # noqa-acento: citação dela

    **A MORDIDA:** tire uma das três tuplas de `_heroic` e a loja some da
    contagem sem nada reprovar em outro lugar.
    """
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": "a1", "title": "Um da Epic"}]})
    _escrever(p / "store_cache/gog_library.json",
              {"games": [{"app_name": "g1", "title": "Um da GOG"}]})
    _escrever(p / "store_cache/nile_library.json",
              {"library": [{"id": "n1", "product_title": "Um da Amazon"}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert {j.loja for j in b.jogos} == {"Epic", "GOG", "Amazon"}
    assert [j.nome for j in b.jogos if j.loja == "Amazon"] == ["Um da Amazon"]


def test_o_caso_dela_biblioteca_cheia_e_zero_instalados(
    tmp_path: pathlib.Path,
) -> None:
    """O disco dela em 09/09/2026: 37 na biblioteca, nenhum baixado.

    **Isso não é defeito, e a frase tem de dizer os DOIS números.** A
    biblioteca lista o que a CONTA tem; o `*_install_info.json` diz o que está
    no disco, e o dela não existe.

    **A MORDIDA:** faça `instalado=True` fixo e o resumo passa a prometer 37
    jogos jogáveis sobre uma pasta vazia.
    """
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": f"e{n}", "title": f"Epic {n}"}
                           for n in range(35)]})
    _escrever(p / "store_cache/gog_library.json",
              {"games": [{"app_name": f"g{n}", "title": f"GOG {n}"}
                         for n in range(2)]})
    # SEM `*_install_info.json` — é o disco dela

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert len(b.jogos) == 37
    assert b.instalados == []
    assert b.resumo == "37 jogos na biblioteca · 0 instalados"


def test_o_install_info_e_quem_diz_o_instalado(tmp_path: pathlib.Path) -> None:
    """A biblioteca não sabe o que está no disco — o `install_info` sabe.

    **A MORDIDA:** leia o instalado de um campo da biblioteca e este caso
    reprova: o jogo `e1` está no `install_info` e não tem campo nenhum que o
    diga na `library`.
    """
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": "e1", "title": "Baixado"},
                           {"app_name": "e2", "title": "Só na conta"}]})
    _escrever(p / "store_cache/legendary_install_info.json",
              {"e1": {"install": {"install_path": "/jogos/e1"}}})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert [j.nome for j in b.instalados] == ["Baixado"]
    assert b.resumo == "2 jogos na biblioteca · 1 instalado"


def test_o_singular_e_o_plural_da_frase(tmp_path: pathlib.Path) -> None:
    """"1 jogo · 1 instalado" — a tela dela não diz "1 jogos".

    **A MORDIDA:** cole um `s` fixo e esta linha reprova.
    """
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": "e1", "title": "Um só"}]})
    _escrever(p / "store_cache/legendary_install_info.json", {"e1": {}})

    assert censo.biblioteca_de("Heroic", lar=tmp_path).resumo == \
        "1 jogo na biblioteca · 1 instalado"


def test_biblioteca_vazia_nao_e_o_mesmo_que_nunca_aberto(
    tmp_path: pathlib.Path,
) -> None:
    """A pasta existe e a conta não tem jogo — são coisas diferentes.

    Confundir as duas é como *"ninguém pintou ainda"* vira *"pintei nada"*.

    **A MORDIDA:** devolva `NUNCA_ABERTO` quando a lista sai vazia e o cartão
    passa a mandar ela abrir um programa que ela já abriu.
    """
    _flatpak(tmp_path, HEROIC_ID, "heroic")

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert b.resumo == "A biblioteca está vazia."


# ---------------------------------------------------------------------------
# 3. OS OUTROS QUATRO
# ---------------------------------------------------------------------------
def test_o_lutris_le_um_yml_por_jogo(tmp_path: pathlib.Path) -> None:
    """O nome do arquivo É o slug — e é a chave que a §4 vai usar.

    **A MORDIDA:** troque o `p.stem` por `p.name` e a chave passa a levar o
    `.yml`, que não é o identificador de nada.
    """
    p = _flatpak(tmp_path, "net.lutris.Lutris", "lutris")
    (p / "games").mkdir()
    (p / "games/hollow-knight.yml").write_text("game: {}\n", encoding="utf-8")
    (p / "games/celeste.yml").write_text("game: {}\n", encoding="utf-8")

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert sorted(j.chave for j in b.jogos) == ["celeste", "hollow-knight"]
    assert b.resumo == "2 jogos na biblioteca · 2 instalados"


def test_o_retroarch_le_as_playlists(tmp_path: pathlib.Path) -> None:
    """Uma `.lpl` por console, com as ROMs dentro.

    **A MORDIDA:** ignore o `label` e o nome do jogo vira o caminho inteiro
    da ROM na tela dela.
    """
    p = _flatpak(tmp_path, "org.libretro.RetroArch", "retroarch")
    _escrever(p / "playlists/Nintendo - SNES.lpl",
              {"items": [{"path": "/roms/smw.sfc", "label": "Super Mario World"}]})

    b = censo.biblioteca_de("RetroArch", lar=tmp_path)

    assert [j.nome for j in b.jogos] == ["Super Mario World"]
    assert b.jogos[0].loja == "Nintendo - SNES"


def test_o_dolphin_conta_pastas_e_nao_mente_que_sao_jogos(
    tmp_path: pathlib.Path,
) -> None:
    """O Dolphin guarda o cache num binário; em texto há só as pastas.

    **Contar pastas e chamá-las de jogos seria mentir** — então elas saem com
    `instalado=False`, e o resumo diz "0 instalados" com honestidade.

    **A MORDIDA:** ponha `instalado=True` e o cartão promete jogos que este
    leitor nunca viu.
    """
    p = _flatpak(tmp_path, "org.DolphinEmu.dolphin-emu", "dolphin-emu")
    (p / "Dolphin.ini").write_text(
        "[General]\nISOPath0 = /jogos/gc\nISOPath1 = /jogos/wii\nISOPaths = 2\n",
        encoding="utf-8")

    b = censo.biblioteca_de("Dolphin", lar=tmp_path)

    assert sorted(j.chave for j in b.jogos) == ["/jogos/gc", "/jogos/wii"]
    assert b.instalados == []
    assert b.resumo == "2 jogos na biblioteca · 0 instalados"


# ---------------------------------------------------------------------------
# 4. NUNCA LEVANTA — a aba pinta a cada tique
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lancador,app_id,sub,arquivo", [
    ("Heroic", HEROIC_ID, "heroic", "store_cache/legendary_library.json"),
    ("RetroArch", "org.libretro.RetroArch", "retroarch", "playlists/x.lpl"),
])
def test_json_truncado_nao_derruba_a_leitura(
    tmp_path: pathlib.Path, lancador: str, app_id: str, sub: str, arquivo: str,
) -> None:
    """Um `.json` pela metade não pode apagar a coluna inteira.

    **A MORDIDA:** tire o `except (OSError, ValueError)` de `_json` e a aba
    para de pintar no tique em que o arquivo estiver sendo escrito.
    """
    p = _flatpak(tmp_path, app_id, sub)
    alvo = p / arquivo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text('{"library": [', encoding="utf-8")

    b = censo.biblioteca_de(lancador, lar=tmp_path)

    assert b.estado in (censo.LIDO, censo.ILEGIVEL)
    assert b.jogos == []


def test_o_nativo_tambem_e_lido(tmp_path: pathlib.Path) -> None:
    """`~/.config/<sub>` — quem não usa flatpak tem biblioteca igual.

    **A MORDIDA:** procure só no `.var/app` e toda instalação nativa passa a
    dizer "nunca aberto" sobre um lançador em uso.
    """
    p = tmp_path / ".config/heroic/store_cache"
    _escrever(p / "legendary_library.json",
              {"library": [{"app_name": "e1", "title": "Nativo"}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert [j.nome for j in b.jogos] == ["Nativo"]
