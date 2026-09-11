#!/usr/bin/env python3
"""JOGOS-DOS-LANCADORES-01 — os jogos dos outros cinco chegam ao campo do jogo.

**A FRASE DELA, 09/09/2026** (noqa-acento: citação literal): *"aí a ideia é
cada um dos lançadores passarem a ter os jogos com perfis dentro da aba
perfis."*

**E A PREMISSA DA SPRINT CAIU NA MEDIÇÃO DE 10/09/2026, como o topo dela
previa.** O enunciado dizia que *"a Steam entrega uma CHAVE; os outros cinco
entregam um NOME"*, e que no Heroic não havia campo com `exe`/`executable`. Era
verdade sobre uma biblioteca com **zero** jogos baixados. Ela deixou um jogo
baixando (*"deixei baixando um jogo já"*), e com ele no disco o
`legendary_library.json` passou a trazer::  # noqa-acento: citação dela

    "is_installed": true,
    "install": {"executable": "retail/gotg.exe", "install_path": "…"}

O basename disso — ``gotg.exe`` — é a `wm_class`, que é o MESMO campo do perfil
que a Steam usa (`window_class`), pela sexta forma do `simple_match`.

**NENHUMA RÉGUA AQUI TOCA A BIBLIOTECA DELA.** Todas passam `lar=tmp_path` ou
substituem a fonte — a §4 da sprint exige isso com todas as letras, e o lar de
mentira da suíte é um ESPELHO por symlink, então `Path.home()` num teste
alcançaria o Heroic de verdade.
"""
from __future__ import annotations

import json
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import jogos_locais as jl

HEROIC_ID = "com.heroicgameslauncher.hgl"


def _heroic(lar: pathlib.Path, itens: list[dict[str, Any]]) -> pathlib.Path:
    """Uma biblioteca da Epic de mentira, na árvore de flatpak que é a dela."""
    pasta = lar / ".var/app" / HEROIC_ID / "config/heroic"
    alvo = pasta / "store_cache/legendary_library.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps({"library": itens}), encoding="utf-8")
    return pasta


#: O jogo baixado dela, com os campos EXATOS que o disco trouxe em 10/09/2026.
BAIXADO: dict[str, Any] = {
    "app_name": "63a665088eb1480298f1e57943b225d8",
    "title": "Marvel's Guardians of the Galaxy",
    "is_installed": True,
    "install": {"executable": "retail/gotg.exe",
                "install_path": "/casa/Games/Heroic/MarvelGOTG",
                "is_dlc": False},
}
#: A roupa que veio junto com ele — `is_dlc: true`, e INSTALADA.
A_ROUPA: dict[str, Any] = {
    "app_name": "9596620d263b40c083ddf1f0c662c8ff",
    "title": "Marvel's Guardians of the Galaxy: Social-Lord Outfit",
    "is_installed": True,
    "install": {"executable": "", "is_dlc": True},
}
#: Um jogo que ela tem na conta e não baixou — o caso dos outros 28.
SO_NA_CONTA: dict[str, Any] = {
    "app_name": "Catnip", "title": "Borderlands 3",
    "is_installed": False, "install": {"install_size": "0", "is_dlc": False},
}


# ---------------------------------------------------------------------------
# 1. O ACESSÓRIO NÃO É JOGO — e o campo que diz isso é declarado, não adivinhado
# ---------------------------------------------------------------------------
def test_o_dlc_e_o_redistribuivel_saem_da_contagem(
    tmp_path: pathlib.Path,
) -> None:
    """`install.is_dlc` é quem manda — nunca uma lista de nomes.

    Medido no disco dela em 10/09/2026: **8** acessórios, não o `gog-redist`
    sozinho que a §2 da sprint contava — sete DLC da Epic (trilha sonora, art
    book, roupa, wallpaper) mais o redistribuível da GOG, que também traz
    `is_dlc: true`. Sobram **29** jogos de 37.

    **MORDIDA:** tire o `if jogo.e_acessorio: continue` de `_heroic` e a roupa
    volta a contar como jogo INSTALADO — o cartão passa a prometer dois jogos
    jogáveis onde há um, e a lista oferece uma roupa como se fosse jogo.
    """
    _heroic(tmp_path, [BAIXADO, A_ROUPA, SO_NA_CONTA])

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert [j.nome for j in b.jogos] == [
        "Marvel's Guardians of the Galaxy", "Borderlands 3"]
    assert b.resumo == "2 jogos na biblioteca · 1 instalado"


def test_o_redistribuivel_da_gog_cai_pela_mesma_regua(
    tmp_path: pathlib.Path,
) -> None:
    """*Galaxy Common Redistributables* — `app_name: gog-redist`, `is_dlc: true`.

    Ele está no disco dela e é o item que a sprint nomeava. Cai pelo CAMPO, e
    não por um nome cravado — que é o que faz esta régua alcançar também os
    sete DLC da Epic que a sprint não tinha visto.
    """
    pasta = tmp_path / ".var/app" / HEROIC_ID / "config/heroic/store_cache"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "gog_library.json").write_text(json.dumps({"games": [
        {"app_name": "gog-redist", "title": "Galaxy Common Redistributables",
         "is_installed": True, "install": {"is_dlc": True}},
        {"app_name": "1421309312", "title": "Worms Revolution Gold Edition",
         "is_installed": False, "install": {"is_dlc": False}},
    ]}), encoding="utf-8")

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert [j.nome for j in b.jogos] == ["Worms Revolution Gold Edition"]


# ---------------------------------------------------------------------------
# 2. A CHAVE — e o basename, que é o que a janela anuncia
# ---------------------------------------------------------------------------
def test_a_chave_de_janela_e_o_basename_do_executavel(
    tmp_path: pathlib.Path,
) -> None:
    """``retail/gotg.exe`` → ``gotg.exe``, que é o que a `wm_class` traz.

    **MORDIDA:** devolva `self.executavel` inteiro em `classe_de_janela` e a
    regra do perfil vira `window_class=["retail/gotg.exe"]`, que **nunca** casa
    com janela nenhuma — o defeito R-12, com verde em toda a suíte.
    """
    _heroic(tmp_path, [BAIXADO])

    jogo = censo.biblioteca_de("Heroic", lar=tmp_path).instalados[0]

    assert jogo.executavel == "retail/gotg.exe"
    assert jogo.classe_de_janela == "gotg.exe"
    assert jogo.caminho == pathlib.Path("/casa/Games/Heroic/MarvelGOTG")


def test_quem_nao_tem_chave_nao_e_oferecido_mesmo_instalado(
    tmp_path: pathlib.Path,
) -> None:
    """Duas ausências diferentes, e nenhuma das duas vira oferta.

    * *Borderlands 3* — ela tem na conta e não baixou. É o caso dos outros 28.
    * o jogo da GOG — `is_installed: true` e **sem `executable`**. É uma forma
      real do disco dela: o `gog_library.json` marca instalado e a GOG não
      grava binário nenhum ali.

    É a metade honesta da §3: uma linha sem chave é uma linha que nunca
    reconhece jogo nenhum. Os dois continuam CONTANDO na biblioteca — o cartão
    da aba Lançadores diz os dois números —, e só não viram sugestão de campo.

    **MORDIDA:** tire o `and jogo.classe_de_janela` de
    `jogos_com_chave_de_janela` e o jogo da GOG passa a ser oferecido com
    `value=""` — o campo grava vazio e o Salvar recusa sem ela entender por quê.
    """
    _heroic(tmp_path, [BAIXADO, SO_NA_CONTA])
    gog = tmp_path / ".var/app" / HEROIC_ID / "config/heroic/store_cache"
    (gog / "gog_library.json").write_text(json.dumps({"games": [
        {"app_name": "1421309312", "title": "Worms Revolution Gold Edition",
         "is_installed": True, "install": {"is_dlc": False}}]}),
        encoding="utf-8")

    com_chave = censo.jogos_com_chave_de_janela(lar=tmp_path)

    assert [(lanc, j.classe_de_janela) for lanc, j in com_chave] == [
        ("Heroic", "gotg.exe")]
    assert len(censo.biblioteca_de("Heroic", lar=tmp_path).jogos) == 3


def test_o_emulador_nao_finge_ter_uma_janela_por_rom(
    tmp_path: pathlib.Path,
) -> None:
    """As 7 ROMs do RetroArch dela são UM processo — não sete janelas.

    O RetroArch marca `instalado=True` em toda ROM da playlist (o arquivo está
    no disco), e a `chave` dele é o CAMINHO da ROM. Se o caminho virasse chave
    de janela, sete perfis nasceriam mirando classes que não existem.

    **MORDIDA:** faça `classe_de_janela` cair para o `chave` quando não há
    executável e as ROMs voltam a ser oferecidas, cada uma com o basename do
    arquivo (`240pSuite.sfc`) no lugar de uma `wm_class`.
    """
    pasta = tmp_path / ".var/app/org.libretro.RetroArch/config/retroarch"
    (pasta / "playlists").mkdir(parents=True, exist_ok=True)
    (pasta / "playlists/Nintendo - SNES.lpl").write_text(json.dumps({"items": [
        {"path": "/casa/roms/240pSuite.sfc", "label": "240pSuite"}]}),
        encoding="utf-8")

    b = censo.biblioteca_de("RetroArch", lar=tmp_path)

    assert len(b.instalados) == 1
    assert b.instalados[0].classe_de_janela == ""
    assert censo.jogos_com_chave_de_janela(lar=tmp_path) == []


# ---------------------------------------------------------------------------
# 3. A SEGUNDA ORIGEM CHEGA AO CAMPO — e o que ela grava FUNCIONA
# ---------------------------------------------------------------------------
def test_o_jogo_do_lancador_vira_oferta_com_a_wm_class_no_value(
    tmp_path: pathlib.Path,
) -> None:
    """A mesma divisão da Steam: `value` é o ENDEREÇO, `label` é o que ela lê.

    **MORDIDA:** troque `jogo.valor` por `jogo.nome` no `<option>` de
    `_html_dos_jogos` e escolher a linha escreveria *Marvel's Guardians of the
    Galaxy* no campo, virando `window_class=["Marvel's Guardians…"]`.
    """
    _heroic(tmp_path, [BAIXADO, A_ROUPA, SO_NA_CONTA])

    ofertas = jl.jogos_dos_lancadores(lar=tmp_path)

    assert [(j.valor, j.rotulo, j.forma) for j in ofertas] == [
        ("gotg.exe", "Marvel's Guardians of the Galaxy (Heroic)", "janela")]


def test_o_que_o_campo_grava_casa_com_a_janela_de_verdade() -> None:
    """A PROVA QUE IMPORTA: a oferta vira regra, e a regra reconhece a janela.

    É o critério de pronto *"no perfil"* da sprint — **o MESMO campo**
    (`window_class`), nunca um campo novo. O caminho inteiro, sem tela:

        oferta  →  from_simple_choice(forma, valor)  →  MatchCriteria  →  matches

    **MORDIDA:** devolva ``"game"`` em `JogoLocal.forma` e a regra vira
    `process_name=["gotg.exe"]` — outro dado, que casa por acaso: esta linha
    reprova porque `matches` deixa de reconhecer a `wm_class`.
    """
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    jogo = jl.JogoLocal(appid="", nome="Marvel's Guardians of the Galaxy",
                        fonte="heroic", lancador="Heroic", chave="gotg.exe")

    regra = from_simple_choice(jogo.forma, jogo.valor)

    assert regra.window_class == ["gotg.exe"]
    assert regra.matches({"wm_class": "gotg.exe", "wm_name": "GOTG"})
    assert not regra.matches({"wm_class": "steam_app_1245620", "wm_name": ""})


def test_a_steam_desempata_quando_o_mesmo_jogo_vem_das_duas_origens() -> None:
    """Um jogo em duas lojas não pode virar duas linhas na sugestão.

    E a junção é PURA — recebe as duas listas, não lê disco: quem chama é a
    pintura da aba, dez vezes por segundo, e cada origem já vem memoizada pela
    assinatura da sua biblioteca.

    **MORDIDA:** tire o filtro `if chave_de_busca(j.nome) not in vistos` de
    `ofertas_do_campo_do_jogo` e a lista oferece o mesmo nome duas vezes, com
    endereços diferentes — e ela não tem como saber qual escolher.
    """
    steam = [jl.JogoLocal(appid="1245620", nome="ELDEN RING", fonte="steam")]
    dos_lancadores = [
        jl.JogoLocal(appid="", nome="Elden Ring", fonte="heroic",
                     lancador="Heroic", chave="eldenring.exe"),
        jl.JogoLocal(appid="", nome="Outro", fonte="heroic",
                     lancador="Heroic", chave="outro.exe"),
    ]

    ofertas = jl.ofertas_do_campo_do_jogo(steam, dos_lancadores)

    assert [j.valor for j in ofertas] == ["1245620", "outro.exe"]


# ---------------------------------------------------------------------------
# 4. O RÓTULO AO LADO DO CAMPO — a lista ofereceu, a tela confirma
# ---------------------------------------------------------------------------
def test_o_rotulo_diz_o_nome_do_jogo_do_lancador() -> None:
    """Escolher a linha e o campo ficar mudo é a lista mentindo por omissão.

    É a decisão 10-Q4 dela — *"à direita do campo aparece o nome do jogo"* — e
    até 10/09 ela valia só para a Steam.

    **MORDIDA:** tire o ramo `do_lancador` de `frase_do_campo_do_jogo` e a
    terceira asserção reprova: o rótulo volta ao silêncio sobre um valor que o
    próprio produto acabou de oferecer.
    """
    chaves = {"gotg.exe": "Marvel's Guardians of the Galaxy"}

    assert jl.frase_do_campo_do_jogo("gotg.exe", {}, chaves) == (
        "Marvel's Guardians of the Galaxy", False)
    # SEM as chaves, o silêncio continua sendo o certo: não há o que afirmar.
    assert jl.frase_do_campo_do_jogo("gotg.exe", {}) is None
    # E o alarme de endereço colado não muda — ele tem barra, o nome não tem.
    assert jl.frase_do_campo_do_jogo("https://x/y", {}, chaves) == (
        jl.MSG_NAO_RECONHECI, True)


def test_a_busca_do_campo_acha_pelo_endereco_do_lancador() -> None:
    """Depois de escolher, o campo tem `gotg.exe` — e a lista tem de segurá-lo.

    **MORDIDA:** volte `casa_com_o_que_ela_digitou` a olhar só `jogo.appid` e
    esta linha reprova: reabrir a lista com o campo preenchido não mostraria a
    linha que está escrita nele.
    """
    jogo = jl.JogoLocal(appid="", nome="Marvel's Guardians of the Galaxy",
                        fonte="heroic", lancador="Heroic", chave="gotg.exe")

    assert jl.casa_com_o_que_ela_digitou(jogo, "gotg")
    assert jl.casa_com_o_que_ela_digitou(jogo, "guardians")
    assert not jl.casa_com_o_que_ela_digitou(jogo, "elden")


def test_nenhum_lancador_instalado_e_lista_so_da_steam(
    tmp_path: pathlib.Path,
) -> None:
    """Máquina sem Heroic: a oferta é a de sempre, e nada quebra.

    É a exigência da §4 da sprint com todas as letras — *"nenhuma régua desta
    sprint pode depender de a máquina ter Heroic instalado"* —, e aqui ela é
    medida em vez de prometida: um `lar` vazio devolve lista vazia.
    """
    assert jl.jogos_dos_lancadores(lar=tmp_path) == []
    assert censo.jogos_com_chave_de_janela(lar=tmp_path) == []
    assert jl.jogos_com_janela(lar=tmp_path, pastas=[tmp_path]) == []


# ---------------------------------------------------------------------------
# 5. O ALVO DE 11/09 — o «Detectar» que acha jogo de fora da Steam
#
# A FOTO DELA: o botão responde `PRAGMATA` para `steam_app_3357650` e **não
# responde nada** para um jogo que não é da Steam. *"em perfil falta detectar
# os jogos dos demais lançadores. dando exemplo do guardi]ães da galáxia."*
# (noqa-acento: citação literal dela, com a digitação dela)
# ---------------------------------------------------------------------------
LUTRIS_ID = "net.lutris.Lutris"

#: As 23 colunas do `pga.db` dela, medidas em 11/09/2026. A régua cria a tabela
#: INTEIRA de propósito: um `SELECT` por nome de coluna tem de sobreviver a
#: colunas que ele não pede, que é o caso real.
_ESQUEMA_LUTRIS = (
    "CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, sortname TEXT, "
    "slug TEXT, installer_slug TEXT, parent_slug TEXT, platform TEXT, "
    "runner TEXT, executable TEXT, directory TEXT, updated TEXT, "
    "lastplayed INTEGER, installed INTEGER, installed_at INTEGER, "
    "year INTEGER, configpath TEXT, has_custom_banner INTEGER, "
    "has_custom_icon INTEGER, has_custom_coverart_big INTEGER, "
    "playtime REAL, service TEXT, service_id TEXT, discord_id TEXT)"
)


def _lutris(lar: pathlib.Path, linhas: list[tuple[str, str, str, int]]) -> None:
    """Um `pga.db` de mentira na árvore de flatpak que é a dela."""
    import sqlite3

    pasta = lar / ".var/app" / LUTRIS_ID / "config/lutris"
    pasta.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(pasta / "pga.db")
    with con:
        con.execute(_ESQUEMA_LUTRIS)
        con.executemany(
            "INSERT INTO games (name, slug, executable, installed) "
            "VALUES (?, ?, ?, ?)", linhas)
    con.close()


def _atalho(pasta: pathlib.Path, arquivo: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / arquivo).write_text(corpo, encoding="utf-8")


def test_a_biblioteca_do_lutris_sai_do_banco_e_nao_da_pasta_vazia(
    tmp_path: pathlib.Path,
) -> None:
    """O LEITOR OLHAVA O ARQUIVO ERRADO, e o sintoma era a AUSÊNCIA de dado.

    Medido no disco dela em 11/09/2026: `config/lutris` é symlink para
    `data/lutris`, `games/` tem **0** arquivos e a biblioteca inteira mora no
    `pga.db`. O cartão dizia *"A biblioteca está vazia"* sobre um Lutris que
    podia estar cheio — e, pior para esta sprint, o `.yml` não traz
    `executable`, que é a ETIQUETA que o perfil precisa.

    **MORDIDA:** volte `_lutris` a ler só `games/*.yml` e as três asserções
    reprovam: zero jogos, zero chaves, e o «Detectar» continua sem nome para
    um jogo do Lutris.
    """
    _lutris(tmp_path, [
        ("Celeste", "celeste", "/casa/Games/celeste/Celeste.bin.x86_64", 1),
        ("Hollow Knight", "hollow-knight", "/casa/Games/hk/hollow_knight.x86_64", 1),
        ("Só na conta", "so-na-conta", "", 0),
    ])

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert [j.nome for j in b.jogos] == ["Celeste", "Hollow Knight", "Só na conta"]
    assert b.resumo == "3 jogos na biblioteca · 2 instalados"
    assert [(lanc, j.classe_de_janela)
            for lanc, j in censo.jogos_com_chave_de_janela(lar=tmp_path)] == [
        ("Lutris", "Celeste.bin.x86_64"),
        ("Lutris", "hollow_knight.x86_64")]


def test_o_yml_de_configuracao_propria_nao_some_com_a_leitura_nova(
    tmp_path: pathlib.Path,
) -> None:
    """A leitura nova não pode ENCOLHER o que já funcionava.

    Um jogo configurado à mão tem `.yml` e pode não estar no banco. Ele
    continua entrando, e não duplica quando está nos dois.

    **MORDIDA:** tire o bloco do `games/*.yml` de `_lutris` e o jogo só de
    `.yml` some da biblioteca — uma regressão silenciosa contra o leitor velho.
    """
    _lutris(tmp_path, [("Celeste", "celeste", "/casa/celeste/Celeste", 1)])
    games = tmp_path / ".var/app" / LUTRIS_ID / "config/lutris/games"
    games.mkdir(parents=True, exist_ok=True)
    (games / "celeste.yml").write_text("game: {}\n", encoding="utf-8")
    (games / "so-no-yml.yml").write_text("game: {}\n", encoding="utf-8")

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert [j.chave for j in b.jogos] == ["celeste", "so-no-yml"]


def test_o_jogo_direto_traz_a_etiqueta_do_proprio_atalho(
    tmp_path: pathlib.Path,
) -> None:
    """`StartupWMClass=` é a etiqueta — e não é invenção nossa, é a spec XDG.

    Medido nas quatro pastas dela em 11/09/2026: 221 `.desktop`, 59 com
    `StartupWMClass`, 31 com `Categories=Game` — e **23 desses 31 são os
    `meow-steam-*.desktop` dela, que escrevem `StartupWMClass=steam_app_<id>`**.
    É a prova de que este campo é o MESMO endereço que o perfil da Steam já
    guarda.

    **MORDIDA:** tire o `if steam_appid_de_texto(classe) is not None: continue`
    e a segunda asserção reprova — os 23 jogos da Steam voltam pela porta dos
    fundos, com o nome CORTADO do atalho (medido: `ORPHEUS` no lugar de
    `ORPHEUS: TO HELL AND BACK`) e sem o appid que o produto inteiro usa.
    """
    _atalho(tmp_path, "celeste.desktop",
            "[Desktop Entry]\nType=Application\nName=Celeste\n"
            "Exec=/casa/celeste/Celeste\nCategories=Game;\n"
            "StartupWMClass=Celeste\n")
    _atalho(tmp_path, "meow-steam-4145130.desktop",
            "[Desktop Entry]\nType=Application\nName=ORPHEUS\n"
            "Exec=/usr/games/steam steam://rungameid/4145130\n"
            "Categories=Game;\nStartupWMClass=steam_app_4145130\n")
    _atalho(tmp_path, "com.heroicgameslauncher.hgl.desktop",
            "[Desktop Entry]\nType=Application\nName=Heroic Games Launcher\n"
            "Exec=/usr/bin/flatpak run com.heroicgameslauncher.hgl\n"
            "Categories=Game;PackageManager;\nStartupWMClass=heroic\n")
    _atalho(tmp_path, "org.libretro.RetroArch.desktop",
            "[Desktop Entry]\nType=Application\nName=RetroArch\n"
            "Exec=/usr/bin/flatpak run org.libretro.RetroArch\n"
            "Categories=Game;Emulator;\nStartupWMClass=retroarch\n")
    _atalho(tmp_path, "escondido.desktop",
            "[Desktop Entry]\nType=Application\nName=Escondido\n"
            "Exec=/bin/true\nCategories=Game;\nStartupWMClass=escondido\n"
            "NoDisplay=true\n")
    _atalho(tmp_path, "gedit.desktop",
            "[Desktop Entry]\nType=Application\nName=Editor\n"
            "Exec=/bin/true\nCategories=Utility;\nStartupWMClass=gedit\n")

    diretos = jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])

    # O EMULADOR FICA: ele é UM processo para todas as ROMs (§4 da sprint), e
    # a linha por emulador é a única que existe — e é a certa.
    assert [(j.chave, j.nome) for j in diretos] == [
        ("Celeste", "Celeste"), ("retroarch", "RetroArch")]
    assert all(j.appid == "" for j in diretos)
    assert diretos[0].lancador == jl.LANCADOR_DIRETO


def test_o_detectar_acha_o_jogo_do_heroic_do_lutris_e_o_direto(
    tmp_path: pathlib.Path,
) -> None:
    """**A FALTA QUE ELA NOMEOU, medida nas três origens de uma vez.**

    `steam_appid_from_wm_class("steam_app_3357650")` já devolvia `3357650`, e
    daí o botão dizia `PRAGMATA`. Do outro lado não havia função nenhuma: a
    regra era gravada certa (forma "janela", ONDA5-10-01) e o NOME ficava em
    branco — que é o que ela leu como *"não acha"*.

    **MORDIDA:** faça `jogo_da_janela` devolver `None` sempre (ou compare com
    `==` sem `casefold`) e o `GOTG.EXE` do `pga.db` deixa de reconhecer a
    janela `gotg.exe` do Heroic — o mesmo jogo deixa de se reconhecer conforme
    o lançador por onde ela o abriu.
    """
    _heroic(tmp_path, [BAIXADO])
    _lutris(tmp_path, [("Celeste", "celeste", "/casa/celeste/Celeste.x86_64", 1)])
    _atalho(tmp_path, "super-zsnes.desktop",
            "[Desktop Entry]\nType=Application\nName=Super ZSNES\n"
            "Exec=/casa/zsnes/rodar.sh\nCategories=Game;Emulator;\n"
            "StartupWMClass=SUPERZSNES\n")

    jogos = jl.jogos_com_janela(lar=tmp_path, pastas=[tmp_path])
    achar = lambda c: jl.jogo_da_janela(c, jogos)  # noqa: E731

    assert achar("gotg.exe").nome == "Marvel's Guardians of the Galaxy"
    assert achar("gotg.exe").lancador == "Heroic"
    assert achar("Celeste.x86_64").lancador == "Lutris"
    assert achar("SUPERZSNES").lancador == jl.LANCADOR_DIRETO
    # A CAIXA DOBRA DOS DOIS LADOS, e não é gosto: `MatchCriteria.matches` já
    # compara `window_class` sem caixa (`_casa_sem_caixa`), e o `pga.db` guarda
    # `GOTG.exe` onde a janela anuncia `gotg.exe`.
    assert achar("GOTG.EXE").nome == "Marvel's Guardians of the Galaxy"
    # A STEAM TEM DONO, e não é este: quem traduz appid é `catalogo_de_jogos`.
    assert achar("steam_app_3357650") is None
    # AS DUAS RECUSAS HONESTAS do «Detectar» continuam de pé.
    assert achar("unknown") is None
    assert achar("") is None
    assert achar(None) is None


def test_o_nome_da_janela_chega_ao_rotulo_sem_a_tela_ler_disco_duas_vezes(
    tmp_path: pathlib.Path,
) -> None:
    """A PONTA: `nomes_das_janelas` + `frase_do_campo_do_jogo` = o nome do jogo.

    É o caminho inteiro que a aba Perfis vai chamar numa linha, e ele responde
    ao `gotg.exe` exatamente como responde ao `3357650`: com o NOME.

    **E ELE É MEMOIZADO**, porque quem chama é PINTURA — dez vezes por
    segundo, sobre um `pga.db` e 221 `.desktop`.

    **MORDIDA:** tire o freio da assinatura de `nomes_das_janelas` e a última
    asserção reprova — o segundo `dict` deixa de ser o MESMO objeto, que é o
    sinal de que o disco foi relido sem nada ter mudado.
    """
    jl._NOMES_DAS_JANELAS = None
    _heroic(tmp_path, [BAIXADO])

    chaves = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])

    assert chaves == {"gotg.exe": "Marvel's Guardians of the Galaxy"}
    assert jl.frase_do_campo_do_jogo("gotg.exe", {}, chaves) == (
        "Marvel's Guardians of the Galaxy", False)
    # O QUE O DETECTOR ENTREGA vem como o compositor anunciou; a consulta dobra.
    assert jl.frase_do_campo_do_jogo("GOTG.exe", {}, chaves) == (
        "Marvel's Guardians of the Galaxy", False)
    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) is chaves


def test_o_rotulo_nunca_derruba_a_aba_por_causa_de_um_disco_torto(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isto é PINTURA sobre o disco dela — e o contrato é não levantar NUNCA.

    **MORDIDA:** tire o `try/except` de `nomes_das_janelas` e o `OSError` sobe
    até `a10_perfis._jogo_reconhecido`, que o converte em tarja de recusa — a
    aba Perfis inteira para de pintar por causa de um rótulo.
    """
    def _explode(*_a: object, **_k: object) -> list[Any]:
        raise OSError("um `pga.db` com byte torto")

    jl._NOMES_DAS_JANELAS = None
    monkeypatch.setattr(jl, "jogos_com_janela", _explode)

    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) == {}


# ---------------------------------------------------------------------------
# 5. O REPARO DE 11/09 — as quatro réguas que o conferente cobrou
# ---------------------------------------------------------------------------
def test_o_caderno_releu_o_disco_quando_ela_instalou_o_segundo_jogo(
    tmp_path: pathlib.Path,
) -> None:
    """**A TRAVA MEDIDA CONTRA A PRÓPRIA SAÍDA, e ela atravessou 17 réguas.**

    A única asserção de assinatura desta suíte era o caderno BATENDO
    (``nomes_das_janelas(...) is chaves``) — o ACERTO. Um caderno que nunca
    mais relê o disco passa nela, e passava: `assinatura_das_bibliotecas`
    fazia `os.stat()` na RAIZ de configuração do lançador, e a biblioteca do
    Heroic mora em `store_cache/legendary_library.json`. **O `mtime` de um
    diretório não muda quando um arquivo de um SUBdiretório é reescrito.**

    O que isso custava na tela dela: a aba Perfis é PINTURA num processo
    longo, então a resposta CONGELAVA até ela reiniciar o produto — e o
    gatilho era exatamente o passo que a sprint manda ela dar, *instalar um
    jogo do Heroic*.

    **MORDIDA:** troque o corpo de `censo._FONTES["Heroic"]` por `()` — a
    assinatura volta a ser só a pasta de cima, e as três últimas asserções
    reprovam: o segundo jogo existe no disco, `jogos_com_janela` o vê, e o
    caderno continua devolvendo o primeiro sozinho.
    """
    jl._NOMES_DAS_JANELAS = None
    _heroic(tmp_path, [BAIXADO])

    antes = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])
    assert antes == {"gotg.exe": "Marvel's Guardians of the Galaxy"}
    # O MESMO DISCO DUAS VEZES continua sendo o MESMO objeto — o freio existe.
    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) is antes

    #: Ela instala o segundo jogo: o Heroic REESCREVE o mesmo arquivo, dentro
    #: do mesmo `store_cache`, sem criar nem apagar nada na pasta de cima.
    segundo = dict(BAIXADO, app_name="outro", title="Hades II",
                   install={"executable": "bin/hades2.exe", "is_dlc": False})
    _heroic(tmp_path, [BAIXADO, segundo])

    depois = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])

    assert depois is not antes
    assert depois == {"gotg.exe": "Marvel's Guardians of the Galaxy",
                      "hades2.exe": "Hades II"}
    assert jl.frase_do_campo_do_jogo("hades2.exe", {}, depois) == (
        "Hades II", False)


def test_o_caderno_releu_quando_o_lutris_ganhou_uma_linha_no_banco(
    tmp_path: pathlib.Path,
) -> None:
    """O `pga.db` é um ARQUIVO dentro da pasta — a pasta não muda de `mtime`.

    Mesma forma do defeito do Heroic, e a segunda metade da cura: o sqlite
    reescreve o banco NO LUGAR (e, em modo WAL, escreve num `pga.db-wal` que
    a assinatura também precisa ver — por isso os dois estão em `_FONTES`).

    **O `journal_mode=MEMORY` É A RÉGUA, e não um detalhe do Lutris.** No
    modo padrão o sqlite cria e apaga um `pga.db-journal` DENTRO da pasta, e
    isso muda o `mtime` do diretório sozinho: a régua passaria pelo caminho
    errado e não mediria nada — que é exatamente o defeito que ela existe para
    fechar. Com o diário na memória, o único byte que muda no disco é o do
    `pga.db`, e é ele que a assinatura tem de enxergar.

    **MORDIDA:** tire `"pga.db"` de `censo._FONTES["Lutris"]` e a última
    asserção reprova — a segunda linha do banco nunca chega ao campo.
    """
    jl._NOMES_DAS_JANELAS = None
    _lutris(tmp_path, [("Celeste", "celeste", "/casa/celeste/Celeste.x86_64", 1)])

    antes = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])
    assert antes == {"celeste.x86_64": "Celeste"}

    import sqlite3
    pasta = tmp_path / ".var/app" / LUTRIS_ID / "config/lutris"
    antes_da_pasta = pasta.stat().st_mtime_ns
    con = sqlite3.connect(pasta / "pga.db")
    con.execute("PRAGMA journal_mode=MEMORY")
    with con:
        con.execute("INSERT INTO games (name, slug, executable, installed) "
                    "VALUES (?, ?, ?, ?)",
                    ("Hollow Knight", "hk", "/casa/hk/hollow_knight.x86_64", 1))
    con.close()
    # A PROVA DE QUE A RÉGUA MEDE O ARQUIVO: a pasta de cima não se mexeu.
    assert pasta.stat().st_mtime_ns == antes_da_pasta

    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) == {
        "celeste.x86_64": "Celeste",
        "hollow_knight.x86_64": "Hollow Knight"}


def test_o_cliente_de_loja_nao_entra_na_lista_de_jogos_e_o_emulador_entra(
    tmp_path: pathlib.Path,
) -> None:
    """**O QUE A TERCEIRA ORIGEM ACHA NO DISCO DELA HOJE É ZERO JOGO.**

    Medido em 11/09/2026, e corrige o que esta entrega publicou primeiro: os
    cinco `.desktop` que passavam eram `azahar`, `mGBA`, `retroarch`,
    `SUPERZSNES` — quatro EMULADORES — e `rare`, que é o cliente alternativo
    da Epic e escapava por declarar só `Categories=Game;`. Nenhum jogo.

    * **o Rare SAI** (`_CLIENTES_DE_LOJA`): a biblioteca que ele abre é a
      MESMA que `censo._heroic` já lê pelo `legendary_library.json`, jogo por
      jogo — deixá-lo entrar é oferecer a VITRINE no campo «Nome do Jogo»;
    * **o emulador FICA**, e é decisão com razão escrita: ele é UM processo
      para todas as ROMs, então a janela dele é a única que existe.

    **MORDIDA:** tire o `if classe.casefold() in _CLIENTES_DE_LOJA` e a
    primeira asserção reprova — o `rare` volta à lista de jogos dela.
    """
    _atalho(tmp_path, "io.github.dummerle.rare.desktop",
            "[Desktop Entry]\nType=Application\nName=Rare\n"
            "Exec=/usr/bin/flatpak run io.github.dummerle.rare\n"
            "Categories=Game;\nStartupWMClass=rare\n"
            "Comment=Open source alternative for Epic Games Launcher\n")
    _atalho(tmp_path, "super-zsnes.desktop",
            "[Desktop Entry]\nType=Application\nName=Super ZSNES\n"
            "Exec=/casa/zsnes/rodar.sh\nCategories=Game;Emulator;\n"
            "StartupWMClass=SUPERZSNES\n")

    diretos = jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])

    assert [j.chave for j in diretos] == ["SUPERZSNES"]
    assert diretos[0].lancador == jl.LANCADOR_DIRETO


def test_a_aba_perfis_responde_o_nome_do_jogo_do_heroic(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A PONTA, e ela é a queixa dela — medida nas funções REAIS da aba.**

    Até o reparo de 11/09/2026 nada em `src/` alcançava o motor desta sprint:
    o «Detectar» respondia `PRAGMATA` a um jogo da Steam e **NADA** a um do
    Heroic, que é a foto que ela mandou. As quatro respostas abaixo são as
    quatro pontas, e cada uma tem a sua mordida:

    * arranque o 3º argumento de `frase_do_campo_do_jogo`
      (`_jogo_reconhecido`) → o rótulo ao lado do campo volta a `("", False)`;
    * arranque a `classe` de `_agora_vale_em(prof, classe)` (`detectar`) → o
      desfecho para de nomear o jogo (ver a régua logo abaixo, que o prova
      pelo GESTO);
    * arranque `ofertas_do_campo_do_jogo` de `_html_dos_jogos` → o
      `<datalist>` deixa de oferecer `gotg.exe`;
    * arranque `_forma_do_que_ela_escolheu` de `editor_jogo` → a `wm_class`
      que a própria lista ofereceu é gravada como `process_name`.

    A FONTE É SUBSTITUÍDA, e não a `HOME`: o lar de mentira da suíte é um
    espelho por symlink, e `Path.home()` aqui alcançaria o Heroic DELA.
    """
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    jl._NOMES_DAS_JANELAS = None
    _heroic(tmp_path, [BAIXADO])
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: de_verdade(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: assinar(
        lar=tmp_path, pastas=[tmp_path]))
    #: A OUTRA ORIGEM É DUBLÊ porque ela é da Steam e já tem régua própria —
    #: o que se mede aqui é o lado que NÃO tinha caminho.
    monkeypatch.setattr(a10, "_nomes_dos_jogos", lambda: {"3357650": "PRAGMATA"})

    # 1. O RÓTULO ao lado do campo (`a10_perfis.py`, dentro de `_jogo_reconhecido`)
    assert a10._jogo_reconhecido("gotg.exe") == (
        "Marvel's Guardians of the Galaxy", False)
    assert a10._jogo_reconhecido("3357650") == ("PRAGMATA", False)

    # 2. O DESFECHO do «Detectar» (o último `return` de `detectar`)
    prof = SimpleNamespace(name="Perfil",
                           match=from_simple_choice("janela", "gotg.exe"))
    assert a10._agora_vale_em(prof, "gotg.exe").endswith(
        "· Marvel's Guardians of the Galaxy")

    # 3. O `<datalist>` do campo «Nome do Jogo» — as DUAS origens
    html = a10._html_dos_jogos()
    #: O APÓSTROFO NÃO É ESCAPADO, e é o `_atr` que manda: escapar o que o
    #: serializador do navegador não escapa faria a tela reescrever o bloco a
    #: cada 500 ms para sempre. `DON'T SCREAM` está no catálogo desta casa.
    assert ('<option value="gotg.exe" '
            'label="Marvel\'s Guardians of the Galaxy (Heroic)"></option>'
            ) in html
    assert '<option value="3357650" label="PRAGMATA (appid 3357650)">' in html

    # 4. A FORMA que o Salvar grava para o que a lista ofereceu
    assert a10._forma_do_que_ela_escolheu("gotg.exe") == "janela"
    assert a10._forma_do_que_ela_escolheu("GOTG.EXE") == "janela"
    assert a10._forma_do_que_ela_escolheu("3357650") == "steam_game"
    assert a10._forma_do_que_ela_escolheu("Cyberpunk2077.exe") == "game"
    assert from_simple_choice("janela", "gotg.exe").window_class == ["gotg.exe"]


def test_o_botao_detectar_nomeia_o_jogo_do_heroic_que_acabou_de_gravar(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**O GESTO INTEIRO, pelo botão — e é a foto dela, com o outro desfecho.**

    A régua acima mede as quatro pontas uma a uma; esta chama o GESTO
    `a10_perfis.detectar`, que é o que o dedo dela aciona, e confere as duas
    coisas que ele devolve: a regra gravada e a frase.

    Até o reparo de 11/09/2026 a frase era *"«Perfil» agora vale em: Só neste
    programa"* e parava ali — sobre uma `wm_class` que ela não digitou, vinda
    de uma janela que ela não está mais olhando. Que é a mesma coisa que não
    achar o jogo.

    **MORDIDA:** devolva `_agora_vale_em(prof)` sem a `classe` no último
    `return` de `detectar` e a última asserção reprova — a regra continua
    certa e a tela volta a calar o nome.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    jl._NOMES_DAS_JANELAS = None
    _heroic(tmp_path, [BAIXADO])
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: de_verdade(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: assinar(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos", lambda: {})
    monkeypatch.setattr(a10, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(a10, "_ESCOLHIDO", "", raising=False)

    #: A pasta de perfis, sem escrever no disco — mesmo dublê da régua irmã.
    todos = [Profile(name="Perfil", match=MatchAny(), priority=100)]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(loader, "load_profile", lambda *a, **k: todos[0])
    monkeypatch.setattr(loader, "save_profile", lambda p, *a, **k: todos.__setitem__(0, p))

    class _Ponte:
        def profile_switch(self, nome: str) -> bool:
            return True

        def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
            return True

    ctx = Contexto(state={"active_profile": "Perfil",
                          "window_detect_last_class": "gotg.exe"},
                   mesa=[], conectados=[], estados={})

    fora = a10.detectar(ctx, {}, _Ponte())

    # A REGRA continua a que a ONDA5-10-01 gravava — nada regrediu.
    assert list(todos[0].match.window_class) == ["gotg.exe"]
    # O CAMPO se corrige com o endereço, e não com o nome: é ele que grava.
    assert fora["mesa"]["editor.jogo"] == "gotg.exe"
    # E A FRASE nomeia o jogo, que é a queixa dela de 11/09/2026.
    frase = str(fora["mesa"].get("perfis.desfecho") or "")
    assert frase.endswith("· Marvel's Guardians of the Galaxy"), frase
