"""A-ABA-PERFIS-SO-MOSTRA-O-JOGO-INSTALADO-01: a lista mostra só o perfil cujo jogo está instalado.

O disco é o de verdade, no lar isolado da suíte: a biblioteca da Steam com um `appmanifest` e
quatro perfis (um de jogo instalado, um de jogo desinstalado, o ativo de jogo desinstalado e um sem
jogo). O arquivo do desinstalado fica no disco e volta à lista quando o jogo volta.

AS MORDIDAS: troque o `_so_os_instalados` do `pacote` pelos perfis do disco, e o desinstalado volta;
troque o do `_alvo_do_editor`, e o editor abre no perfil que a lista não mostra; tire o
`bool(foto.nomes)`, e a leitura da Steam que falha esconde todo jogo do usuário.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import jogos_locais
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for var, rel in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_STATE_HOME", ".local/state")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    for nome in ("_ESCOLHIDO", "_PROCURA"):
        monkeypatch.setattr(a10_perfis, nome, "", raising=False)
    for nome in ("_NOMES_DOS_JOGOS", "_FORA_DO_DISCO"):
        monkeypatch.setattr(a10_perfis, nome, None, raising=False)
    monkeypatch.setattr(jogos_locais, "_NOMES_DAS_JANELAS", None, raising=False)


def _steamapps() -> Path:
    from hefesto_dualsense4unix.integrations.proton_pin import default_steam_root

    pasta = default_steam_root() / "steamapps"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _instalar(appid: str, nome: str) -> Path:
    manifesto = _steamapps() / f"appmanifest_{appid}.acf"
    manifesto.write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
        encoding="utf-8")
    return manifesto


def _perfis() -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile

    save_profile(Profile(name="Instalado", priority=90,
                         match=MatchCriteria(window_class=["steam_app_9100001"])))
    save_profile(Profile(name="Desinstalado", priority=80,
                         match=MatchCriteria(window_class=["steam_app_9100002"])))
    save_profile(Profile(name="Ativo fora", priority=70,
                         match=MatchCriteria(window_class=["steam_app_9100003"])))
    save_profile(Profile(name="Sem jogo", priority=60, match=MatchAny()))


def _nomes(valendo: str = "Ativo fora") -> list[str]:
    ctx = Contexto(state={"active_profile": valendo}, mesa=[], conectados=[], estados={})
    return sorted(a10_perfis.pacote(ctx)["perfis.linha.nome"])


def test_a_lista_traz_o_instalado_o_ativo_e_o_sem_jogo_e_o_arquivo_fica() -> None:
    """Prova da D-3110-A-ABA-PERFIS-SO-MOSTRA-O-JOGO-INSTALADO."""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    _instalar("9100001", "Jogo Instalado")
    _perfis()
    assert _nomes() == ["Ativo fora", "Instalado", "Sem jogo"]
    assert load_profile("Desinstalado").name == "Desinstalado"


def test_o_jogo_que_volta_traz_o_perfil_de_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    assert "Desinstalado" not in _nomes()
    _instalar("9100002", "Jogo Que Volta")
    monkeypatch.setattr(a10_perfis, "_NOMES_DOS_JOGOS", None)
    assert "Desinstalado" in _nomes()


def test_sem_a_biblioteca_da_steam_nada_se_esconde() -> None:
    _perfis()
    assert not _steamapps_existe()
    assert _nomes() == ["Ativo fora", "Desinstalado", "Instalado", "Sem jogo"]


def _steamapps_existe() -> bool:
    from hefesto_dualsense4unix.integrations.proton_pin import default_steam_root

    return (default_steam_root() / "steamapps").is_dir()


def test_o_jogo_de_outro_lancador_so_sai_quando_o_censo_o_sabe_desinstalado(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    save_profile(Profile(name="Do Heroic", priority=50,
                         match=MatchCriteria(window_class=["jogo-fora.exe"])))
    save_profile(Profile(name="Do emulador", priority=40,
                         match=MatchCriteria(window_class=["emulador-qualquer"])))
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    monkeypatch.setattr(censo, "chaves_de_janela_fora_do_disco",
                        lambda lar=None: frozenset({"jogo-fora.exe"}))
    assert _nomes(valendo="") == ["Do emulador"]


def test_o_censo_responde_so_pelo_que_a_biblioteca_conhece(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    def jogo(chave: str, instalado: bool) -> Any:
        return censo.JogoDoLancador(chave=chave, nome=chave, instalado=instalado,
                                    janela=chave)

    biblioteca = censo.BibliotecaDoLancador(
        "Heroic", censo.LIDO, None,
        [jogo("fora.exe", False), jogo("dentro.exe", True)], [])
    monkeypatch.setattr(censo, "biblioteca_de", lambda nome, lar=None: biblioteca)
    fora = censo.chaves_de_janela_fora_do_disco()
    assert {"dentro.exe"}.isdisjoint(fora)
    assert all(not j.instalado for j in biblioteca.jogos
               if j.classe_de_janela.casefold() in fora)


def test_o_editor_nunca_abre_no_perfil_que_a_lista_nao_mostra(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    _instalar("9100001", "Jogo Instalado")
    _perfis()
    save_profile(Profile(name="Antes de todos", priority=100,
                         match=MatchCriteria(window_class=["steam_app_9100004"])))
    ctx = Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})
    visiveis = a10_perfis.pacote(ctx)["perfis.linha.nome"]
    assert a10_perfis._alvo_do_editor(ctx).name in visiveis
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Desinstalado")
    assert a10_perfis._alvo_do_editor(ctx).name in visiveis


def test_a_leitura_da_steam_que_falha_nao_esconde_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()

    def falha() -> dict[str, str]:
        raise OSError("biblioteca ilegível")

    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", falha)
    assert _nomes() == ["Ativo fora", "Desinstalado", "Instalado", "Sem jogo"]
