"""O-MODO-FREESTYLE-01 — o «Personalizado» sai, e o cadeado vira «Modo Freestyle».

A palavra dela, 23/09/2026, com a foto da aba Jogar dizendo «Perfil ativo
Personalizado» no topo:

    *"Personalizado sai e o botão Trava o perfil Ativo na aba jogar. Vira Modo
    Freestyle o botão. E a fonte dele aumenta e a altura do botão aumenta também
    na hoje. O trava perfil ativo já faz isso."*  (noqa-acento: citação dela)

Este arquivo guarda as DUAS metades:

- **o motor** (vai ao produto): a semeadura não entrega mais o preset, e o
  `personalizado.json` que já está no disco sai com a cópia no `.historico`;
- **a tela** (para no desenho): o botão diz «Modo Freestyle», maior que hoje,
  na bancada — e a página publicada continua com a palavra de ontem até a
  sessão dela.

A MEDIÇÃO QUE A SPRINT PEDIU ANTES DO CÓDIGO também mora aqui, como régua:
*"Sem o Personalizado, o que fica ativo quando nenhum jogo casa?"* — nada troca;
o perfil que estava continua valendo, e o topo diz o nome dele.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"
JOGO = "steam_app_2111190"  # Mullet Mad Jack — o jogo sem perfil de 24/07

#: O `personalizado.json` DELA, na forma que a casa mediu em 11/09/2026: o
#: «Detectar» gravou a janela do PRÓPRIO Hefesto na regra, e os ajustes por
#: controle são dela. Os `uniq` são sintéticos (regra da casa: fixture usa
#: faixa forjada, nunca endereço real mascarado).
PERFIL_DELA: dict[str, Any] = {
    "name": "Personalizado",
    "version": 1,
    "match": {"type": "criteria", "window_class": ["Hefesto-Dualsense4Unix"]},
    "priority": 1,
    "leds": {"lightbar": [255, 0, 0], "lightbar_brightness": 1.0},
    "controllers": {
        "aabbcc000001": {"leds": {"lightbar": [255, 0, 0]}},
        "aabbcc000002": {"leds": {"lightbar": [0, 0, 255]}},
    },
}


def _grava_dela(pasta: Path) -> bytes:
    """Grava o arquivo dela com a formatação dela e devolve os bytes exatos."""
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(PERFIL_DELA, ensure_ascii=False, indent=4) + "\n").encode()
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(bruto)
    return bruto


def _copias(pasta: Path) -> list[Path]:
    return sorted((pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO)
                  .glob("*.json"))


# =============================================================================
# 1. A SEMEADURA — o preset não chega a máquina nenhuma
# =============================================================================

def test_a_fabrica_de_verdade_nao_semeia_o_personalizado(tmp_path: Path) -> None:
    """Contra a pasta VERSIONADA, não um dublê: o asset está lá e não é copiado.

    O arquivo continua na árvore porque o install o empacota (passo 4c); a
    régua mede o que o SEMEADOR faz com ele, que é o que muda nesta sprint.
    """
    assert (FABRICA / loader.ARQUIVO_DO_PADRAO).is_file(), (
        "o asset saiu da árvore — então a remoção pedida a quem coordena foi "
        "feita, e esta régua tem de passar a medir a pasta nova")
    destino = tmp_path / "perfis"

    copiados = loader.seed_default_presets(dest_dir=destino, source_dirs=[FABRICA])

    assert copiados == []
    assert not (destino / loader.ARQUIVO_DO_PADRAO).exists()
    marca = (destino / loader.SEED_MARKER_NAME).read_text(encoding="utf-8")
    assert loader.ARQUIVO_DO_PADRAO in marca.splitlines(), (
        "o semeador pulou o preset sem registrá-lo — o `install_profiles.sh` lê o "
        "mesmo marker e o traria de volta na próxima instalação")


def test_o_marker_fecha_a_porta_do_install_profiles_tambem(tmp_path: Path) -> None:
    """O contrato do marker, medido com o SHELL de verdade num HOME de mentira.

    Uma máquina em que o Python semeou primeiro (o .deb, o AppImage, o Flatpak,
    ou qualquer carga antes de um reinstall) não recebe o Personalizado quando o
    `install.sh` rodar depois — sem uma linha no install.
    """
    home = tmp_path / "home"
    destino = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    loader.seed_default_presets(dest_dir=destino, source_dirs=[FABRICA])

    feito = subprocess.run(
        ["bash", str(RAIZ / "scripts" / "install_profiles.sh"), str(RAIZ)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=False, timeout=60,
    )

    assert feito.returncode == 0, feito.stderr
    assert not (destino / loader.ARQUIVO_DO_PADRAO).exists(), (
        f"o install_profiles.sh copiou o Personalizado por cima do marker: "
        f"{feito.stdout!r}")


# =============================================================================
# 2. O ARQUIVO DELA — sai da lista, e não se perde
# =============================================================================

def test_o_personalizado_dela_sai_com_a_copia_byte_a_byte() -> None:
    """O caso dela, fim a fim: a lista perde a linha e o histórico ganha o arquivo.

    A comparação é de BYTES, não de dicionário: a cópia tem de ser o arquivo
    dela, com a formatação dela, para a volta ser exata.
    """
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)

    copia = loader.aposentar_o_personalizado()

    assert copia is not None
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()
    assert copia.read_bytes() == bruto
    assert copia.parent == pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO
    assert "Personalizado" not in [p.name for p in loader.load_all_profiles()]


def test_a_volta_existe_e_devolve_o_arquivo_inteiro() -> None:
    """Reversível: `restaurar_do_historico` é a volta que a casa já tinha."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    loader.aposentar_o_personalizado()

    alvo, _versao = loader.restaurar_do_historico(loader.SLUG_DO_PADRAO)

    assert alvo == pasta / loader.ARQUIVO_DO_PADRAO
    assert alvo.read_bytes() == bruto


def test_sem_copia_o_arquivo_fica_e_a_marca_nao_nasce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apagar sem volta é o único desfecho que a migração não tem.

    Com o histórico recusando (disco cheio, permissão), o arquivo FICA e a
    marca não é escrita — a próxima carga tenta de novo.
    """
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    # `context()` e nunca `undo()`: o `undo` desfaria também o isolamento do
    # conftest, que usa o MESMO `monkeypatch`, e o resto do caso mediria o lar
    # da sessão em vez do deste teste.
    with monkeypatch.context() as m:
        m.setattr(loader, "_arquivar_versao", lambda *a, **k: None)
        assert loader.aposentar_o_personalizado() is None
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
    assert not (pasta / loader._PERSONALIZADO_SAIU_MARKER).exists()

    assert loader.aposentar_o_personalizado() is not None
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()


def test_e_uma_vez_so_o_personalizado_que_ela_criar_depois_fica() -> None:
    """One-shot, como as vizinhas: depois da marca, o nome é dela."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    assert loader.aposentar_o_personalizado() is not None

    loader.save_profile(Profile(name="Personalizado",
                                match=MatchCriteria(window_class=["firefox"])))
    assert loader.aposentar_o_personalizado() is None
    assert (pasta / loader.ARQUIVO_DO_PADRAO).is_file()


def test_sem_personalizado_no_disco_nada_acontece_e_a_marca_nasce() -> None:
    pasta = profiles_dir(ensure=True)

    assert loader.aposentar_o_personalizado() is None
    assert (pasta / loader._PERSONALIZADO_SAIU_MARKER).is_file()
    assert not (pasta / loader.HISTORICO_DIR_NAME).exists()


def test_a_sessao_que_apontava_o_personalizado_fica_vazia() -> None:
    """Sem isto o topo diria «Personalizado» sobre um arquivo que saiu.

    `perfil_que_ela_ativou` lê `session.json` e `active_profile.txt` — a segunda
    perna do dono do «Perfil ativo». Vazio é o que os dois leitores entendem
    como "não há".
    """
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")

    loader.aposentar_o_personalizado()

    assert session.load_last_profile() is None
    assert session.read_active_marker() is None
    assert session.resolve_boot_profile() is None


def test_a_sessao_que_aponta_outro_perfil_nao_e_tocada() -> None:
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Mullet Mad Jack")
    session.save_active_marker("Mullet Mad Jack")

    loader.aposentar_o_personalizado()

    assert session.load_last_profile() == "Mullet Mad Jack"
    assert session.read_active_marker() == "Mullet Mad Jack"


# =============================================================================
# 3. A PRIMEIRA CARGA — o caminho que o produto percorre de verdade
# =============================================================================

@pytest.fixture
def semeadura_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura (o conftest a desliga) contra a FÁBRICA versionada."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    # O censo dos jogos não é assunto desta régua, e a máquina de quem roda a
    # suíte não pode decidir o resultado.
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


def test_maquina_nova_abre_sem_o_personalizado(semeadura_ligada: None) -> None:
    """A MORDIDA DA SPRINT: devolva o preset ao semeador e esta régua reprova.

    Máquina nova, a primeira carga de perfis do processo — o que o daemon e a
    interface fazem ao abrir. Nenhuma linha «Personalizado» nasce.
    """
    assert "Personalizado" not in [p.name for p in loader.load_all_profiles()]
    assert not (profiles_dir() / loader.ARQUIVO_DO_PADRAO).exists()


def test_o_que_o_install_semeou_sai_na_primeira_carga(semeadura_ligada: None) -> None:
    """Máquina nova pelo `install.sh`: o shell copia antes de qualquer Python.

    A primeira carga recolhe o arquivo, com a cópia, e a lista abre sem ele.
    """
    pasta = profiles_dir(ensure=True)
    fabrica = (FABRICA / loader.ARQUIVO_DO_PADRAO).read_bytes()
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(fabrica)
    (pasta / loader.SEED_MARKER_NAME).write_text(
        loader.ARQUIVO_DO_PADRAO + "\n", encoding="utf-8")

    nomes = [p.name for p in loader.load_all_profiles()]

    assert "Personalizado" not in nomes
    assert [c.read_bytes() for c in _copias(pasta)] == [fabrica]


def test_o_disco_velho_vai_do_meu_perfil_ao_historico_numa_carga(
    semeadura_ligada: None,
) -> None:
    """O disco de antes de 05/09: `meu_perfil.json` ativo na sessão.

    A renomeação de 05/09 ainda roda primeiro (e guarda o backup dela); esta
    recolhe o resultado no mesmo processo. Nada se perde nos dois passos.
    """
    pasta = profiles_dir(ensure=True)
    velho = dict(PERFIL_DELA, name="meu_perfil", match={"type": "any"})
    (pasta / loader.ARQUIVO_ANTIGO_DO_PADRAO).write_text(
        json.dumps(velho, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    session.save_last_profile("meu_perfil")
    session.save_active_marker("meu_perfil")

    assert loader.load_all_profiles() == []

    assert (pasta / loader.BACKUP_DO_PADRAO).is_file()
    [copia] = _copias(pasta)
    guardado = json.loads(copia.read_text(encoding="utf-8"))
    assert guardado["name"] == "Personalizado"
    assert guardado["controllers"] == PERFIL_DELA["controllers"]
    assert session.resolve_boot_profile() is None


# =============================================================================
# 4. A MEDIÇÃO — sem o Personalizado, o que fica ativo quando nenhum jogo casa
# =============================================================================

def _cena(com_personalizado: bool, travado: bool) -> list[str | None]:
    """Boot no desktop, um jogo com perfil próprio, e o desktop de novo.

    O `AutoSwitcher` e o `ProfileManager` são os REAIS — é o `select_for_window`
    de verdade que diz se há candidato. Devolve o perfil ativo ao fim de cada
    uma das três janelas.
    """
    loader.save_profile(Profile(name="Mullet Mad Jack",
                                match=MatchCriteria(window_class=[JOGO]),
                                priority=80))
    if com_personalizado:
        loader.save_profile(Profile.model_validate(json.loads(
            (FABRICA / loader.ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))))
    store = StateStore()
    store.set_autoswitch_locked(travado)
    controle = FakeController()
    controle.connect()
    sw = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                      window_reader=lambda: {}, store=store)
    ativos: list[str | None] = []
    agora = 0.0
    for info, segundos in (({"wm_class": "firefox", "wm_name": "Mozilla"}, 20),
                           ({"wm_class": JOGO, "wm_name": "Mullet Mad Jack"}, 5),
                           ({"wm_class": "firefox", "wm_name": "Mozilla"}, 30)):
        fim = agora + segundos
        while agora <= fim:
            sw._tick(info, agora)
            agora += 0.5
        ativos.append(store.active_profile)
    return ativos


@pytest.mark.parametrize("travado", [False, True], ids=["freestyle-desligado",
                                                         "freestyle-ligado"])
def test_sem_o_personalizado_nada_troca_quando_nenhum_jogo_casa(travado: bool) -> None:
    """A resposta da medição: o perfil que estava continua valendo.

    Antes do primeiro jogo não há perfil nenhum; o jogo entra; e voltar ao
    desktop NÃO troca — não há candidato, e o autoswitch não ativa ninguém sem
    candidato. Igual com o Modo Freestyle ligado ou desligado.
    """
    assert _cena(com_personalizado=False, travado=travado) == [
        None, "Mullet Mad Jack", "Mullet Mad Jack"]


def test_a_trava_ja_fazia_o_que_o_personalizado_fazia() -> None:
    """A frase dela, medida: *"O trava perfil ativo já faz isso."*

    Com o Personalizado no disco e a trava LIGADA, o desfecho é exatamente o de
    não haver Personalizado; só com a trava DESLIGADA ele entrava no desktop.
    """
    assert _cena(com_personalizado=True, travado=True) == [
        None, "Mullet Mad Jack", "Mullet Mad Jack"]
    for arquivo in profiles_dir().glob("*.json"):
        arquivo.unlink()
    assert _cena(com_personalizado=True, travado=False) == [
        "Personalizado", "Mullet Mad Jack", "Personalizado"]


def test_o_topo_diz_travessao_e_nao_o_nome_que_saiu() -> None:
    """Sem perfil nenhum, o chip «Perfil ativo» diz «—», como já dizia.

    O caso que importa é o DELA: a sessão apontava o Personalizado, e sem a
    limpeza da migração a segunda perna do dono (o disco) devolveria o nome de
    um arquivo que saiu.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto, topo

    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    loader.aposentar_o_personalizado()

    ctx = Contexto(state={"active_profile": None, "controllers": []})
    assert topo(ctx)["perfil"] == "—"
