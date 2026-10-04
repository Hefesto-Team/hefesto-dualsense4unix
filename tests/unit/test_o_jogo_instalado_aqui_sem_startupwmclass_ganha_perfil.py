"""O-JOGO-INSTALADO-AQUI-SEM-STARTUPWMCLASS-APARECE-E-GANHA-PERFIL-01 (03/10/2026).

Muito jogo nativo traz um `.desktop` `Categories=Game;` SEM `StartupWMClass`
(o caso medido é o Forja, de janela `FORJA`). A terceira origem o descartava, e
como a semeadura só lia a segunda origem, ele nunca ganhava perfil: o perfil do
jogo anterior ficava. A chave agora é o id do atalho (`forja`), que a janela
`FORJA` casa sem distinguir maiúscula.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.integrations import jogos_locais as jl
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile

FORJA = (
    "[Desktop Entry]\nType=Application\nName=FORJA\n"
    "Exec=/casa/forja/dist/forja.x86_64\nIcon=forja\nCategories=Game;\n"
)


def _atalho(pasta: Path, arquivo: str, texto: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / arquivo).write_text(texto, encoding="utf-8")


def test_o_atalho_de_jogo_sem_startupwmclass_aparece(tmp_path: Path) -> None:
    _atalho(tmp_path, "forja.desktop", FORJA)

    diretos = jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])

    assert [(j.chave, j.nome, j.lancador) for j in diretos] == [
        ("forja", "FORJA", jl.LANCADOR_DIRETO)
    ]
    # a janela real do jogo (`FORJA`, em XWayland) o reconhece
    assert jl.jogo_da_janela("FORJA", diretos) is diretos[0]


def test_o_que_ja_ficava_fora_segue_fora(tmp_path: Path) -> None:
    _atalho(tmp_path, "escondido.desktop", FORJA.replace("Game;", "Game;\nNoDisplay=true"))
    _atalho(
        tmp_path, "gestor.desktop",
        "[Desktop Entry]\nName=Gestor\nExec=/bin/gestor\nCategories=Game;PackageManager;\n",
    )
    _atalho(
        tmp_path, "editor.desktop",
        "[Desktop Entry]\nName=Editor\nExec=/bin/editor\nCategories=Utility;\n",
    )

    assert jl.jogos_diretos_dos_atalhos(pastas=[tmp_path]) == []


def test_o_que_nao_e_jogo_com_janela_propria_fica_fora_sem_a_classe(
    tmp_path: Path,
) -> None:
    corpo = "[Desktop Entry]\nName={n}\nExec={e}\nCategories={c}\n"
    casos = {
        # ferramenta que se diz de jogo
        "pupgui2.desktop": ("ProtonUp", "/usr/bin/flatpak run pupgui2", "Game;Utility;"),
        # emulador/lançador: tem a aba dele
        "dolphin.desktop": ("Dolphin", "/usr/bin/flatpak run dolphin", "Game;Emulator;"),
        # só manda OUTRO programa abrir o jogo
        "meow-heroic-legendary-abc.desktop": (
            "GOTG", 'xdg-open "heroic://launch?appName=abc"', "Game;"),
        "atalho-de-esquema.desktop": ("Outro", "/usr/bin/lancador steam://run/9", "Game;"),
        # cliente de loja
        "steam.desktop": ("Steam", "/usr/games/steam %U", "Game;"),
        "net.lutris.Lutris.desktop": ("Lutris", "lutris %U", "Game;"),
    }
    for arquivo, (n, e, c) in casos.items():
        _atalho(tmp_path, arquivo, corpo.format(n=n, e=e, c=c))

    assert jl.jogos_diretos_dos_atalhos(pastas=[tmp_path]) == []


def test_o_atalho_com_a_classe_declarada_segue_com_ela(tmp_path: Path) -> None:
    texto = FORJA.replace("FORJA", "Celeste") + "StartupWMClass=CelesteWin\n"
    _atalho(tmp_path, "celeste.desktop", texto)

    achados = jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])

    assert [j.chave for j in achados] == ["CelesteWin"]


def test_a_semeadura_le_a_terceira_origem_e_o_perfil_nasce_padrao(tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    _atalho(casa / ".local/share/applications", "forja.desktop", FORJA)
    destino = tmp_path / "perfis"

    resultado = loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    assert resultado.criados == ("forja.json",)
    dados = json.loads((destino / "forja.json").read_text(encoding="utf-8"))
    # o perfil padrão: nome, o que casa e a prioridade — e NADA mais
    assert set(dados) <= set(loader.CHAVES_DO_PERFIL_DE_JOGO)
    perfil = Profile.model_validate(dados)
    assert perfil.name == "FORJA"
    assert perfil.matches({"wm_class": "FORJA"}) is True
    assert perfil.matches({"wm_class": "outro_jogo"}) is False


def test_a_semeadura_nao_le_os_atalhos_desta_maquina_quando_o_home_e_dado(
    tmp_path: Path, monkeypatch
) -> None:
    de_fora = tmp_path / "de_fora"
    _atalho(de_fora, "forja.desktop", FORJA)
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [de_fora])

    resultado = loader.semear_perfis_dos_jogos(
        dest_dir=tmp_path / "perfis", home=tmp_path / "casa-vazia"
    )

    assert resultado.criados == ()


def test_a_varredura_automatica_acorda_com_o_atalho_novo(
    tmp_path: Path, monkeypatch
) -> None:
    """Atalho novo, sem lançador novo e sem jogo novo na Steam, semeia o perfil."""
    import os

    atalhos = tmp_path / "atalhos"
    atalhos.mkdir()
    destino = tmp_path / "perfis"
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)
    monkeypatch.setattr(loader, "_assinatura_da_biblioteca_vista", None, raising=False)
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [atalhos])
    monkeypatch.setattr(jl, "assinatura_da_biblioteca", lambda home=None: (("/x", 1),))
    monkeypatch.setattr(jl, "jogos_da_biblioteca_steam", lambda home=None: [])
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.censo_dos_lancadores."
        "assinatura_das_bibliotecas",
        lambda *_a, **_k: (),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.censo_dos_lancadores."
        "jogos_com_chave_de_janela",
        lambda *_a, **_k: [],
    )

    loader._talvez_semear_jogos()
    assert list(destino.glob("*.json")) == []

    _atalho(atalhos, "forja.desktop", FORJA)
    # a pasta mudou de data (arquivo novo), e o piso de tempo já passou
    st = atalhos.stat()
    os.utime(atalhos, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None, raising=False)

    loader._talvez_semear_jogos()

    assert [p.name for p in destino.glob("*.json")] == ["forja.json"]


def test_o_atalho_do_lutris_e_de_outro_programa_e_fica_fora(tmp_path: Path) -> None:
    """O atalho que o Lutris escreve no menu chama o PRÓPRIO Lutris.

    `lutris:rungameid/<N>` não tem `://`, e o comando começa por `env`: sem
    olhar o esquema nem o programa depois do `env`, o atalho entrava como jogo
    «instalado aqui» com a chave errada (`net.lutris.<slug>-<N>`), ao lado do
    mesmo jogo que a segunda origem já lê pelo Lutris.
    """
    _atalho(
        tmp_path, "net.lutris.celeste-12.desktop",
        "[Desktop Entry]\nType=Application\nName=Celeste\nIcon=lutris_celeste\n"
        "Exec=env LUTRIS_SKIP_INIT=1 lutris lutris:rungameid/12\nCategories=Game\n",
    )
    _atalho(
        tmp_path, "garrafa.desktop",
        "[Desktop Entry]\nName=Jogo na garrafa\nCategories=Game;\n"
        "Exec=flatpak run --command=bottles-cli com.usebottles.bottles run -p Jogo -b B\n",
    )

    assert jl.jogos_diretos_dos_atalhos(pastas=[tmp_path]) == []


def test_o_jogo_nativo_com_env_e_caminho_segue_dentro(tmp_path: Path) -> None:
    """A metade honesta: `env` e um caminho com `:` não fazem do jogo um atalho alheio."""
    _atalho(
        tmp_path, "jogo-nativo.desktop",
        "[Desktop Entry]\nName=Nativo\nCategories=Game;\n"
        "Exec=env LD_LIBRARY_PATH=/opt/n/lib:/usr/lib /opt/n/nativo.x86_64 --tela=C:\n",
    )

    assert [j.chave for j in jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])] == [
        "jogo-nativo"
    ]


def test_a_janela_do_jogo_instalado_aqui_troca_para_o_perfil_dele(
    tmp_path: Path, monkeypatch
) -> None:
    """A régua 3 da sprint, pelo seletor REAL: do jogo com perfil para o Forja.

    Sem o perfil semeado, a janela `FORJA` não tem candidato (o perfil do jogo
    anterior ficava); com ele, o seletor escolhe o do Forja.
    """
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from hefesto_dualsense4unix.testing import FakeController

    casa = tmp_path / "casa"
    _atalho(casa / ".local/share/applications", "forja.desktop", FORJA)
    destino = tmp_path / "perfis"
    destino.mkdir()
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: destino)
    loader.save_profile(
        Profile(
            name="Avatar Legends",
            match=MatchCriteria(window_class=["steam_app_2111190"]),
            priority=80,
        ),
        origem="teste",
    )
    loader.semear_perfis_dos_jogos(dest_dir=destino, home=casa)

    fc = FakeController()
    fc.connect()
    gerente = ProfileManager(controller=fc)
    assert gerente.select_for_window({"wm_class": "steam_app_2111190"}).name == (
        "Avatar Legends"
    )
    escolhido = gerente.select_for_window({"wm_class": "FORJA"})

    assert escolhido is not None
    assert escolhido.name == "FORJA"
