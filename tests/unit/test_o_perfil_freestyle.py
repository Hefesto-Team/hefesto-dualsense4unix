"""O-MODO-FREESTYLE-02 — o perfil de fora do jogo fica, e se chama «Freestyle».

A decisão, por delegação dela (`D-2409-O-PERFIL-DE-FORA-DO-JOGO-VIRA-FREESTYLE`):
o perfil que vale quando nenhum jogo casa FICA, com os ajustes dela, e passa a se
chamar «Freestyle». A palavra dela *"Personalizado sai"* vale para o nome e para o
preset.  (noqa-acento: citação literal dela)

O QUE CADUCOU, e a medição que o derrubou mora aqui como régua: a
O-MODO-FREESTYLE-01 escreveu um motor que TIRAVA o «Personalizado» e o deixou
dormente (`O_PERSONALIZADO_ESPERA_A_SESSAO_DELA`), porque sem ele do boot ao
primeiro jogo nenhum perfil vale e as abas 02 a 08 recusam o ajuste. O motor
saiu; `test_com_o_freestyle_as_abas_tem_onde_guardar` é a mesma medição com o
sinal que a decisão pediu.

Quatro partes:

1. **a migração**, com o disco de mentira: a cópia byte a byte no `.historico`,
   o `restaurar_do_historico` devolvendo o arquivo inteiro, e a segunda corrida
   sem efeito;
2. **a primeira carga**, o caminho que o daemon e a janela percorrem — com o
   `install_profiles.sh` de verdade rodando antes, como no `install.sh`;
3. **o boot**, e a matriz da sprint: os quatro controles com os ajustes, no USB
   e no BT; um jogo com perfil próprio que entra por cima; a volta ao Freestyle;
4. **as telas que dependem dele**: o topo, as abas que gravam no perfil ativo e o
   «Salvar Perfil» sem perfil ativo.

Os `uniq` são sintéticos (regra da casa: fixture usa faixa forjada).
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import connection
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

#: A mesa inteira: P1 e P3 no cabo, P2 e P4 no rádio — nunca só o P1.
QUATRO = {f"aabbcc00000{n}": {"leds": {"lightbar": [n * 40, 0, 255 - n * 40]}}
          for n in (1, 2, 3, 4)}

#: O `personalizado.json` DELA, na forma que a casa mediu em 11/09/2026: o
#: «Detectar» gravou a janela do PRÓPRIO Hefesto na regra, e os ajustes por
#: controle são dela.
PERFIL_DELA: dict[str, Any] = {
    "name": "Personalizado",
    "version": 1,
    "match": {"type": "criteria", "window_class": ["Hefesto-Dualsense4Unix"]},
    "priority": 1,
    "leds": {"lightbar": [255, 0, 0], "lightbar_brightness": 1.0},
    "controllers": QUATRO,
}


def _grava_dela(pasta: Path, dados: dict[str, Any] | None = None) -> bytes:
    """Grava o arquivo dela com a formatação dela e devolve os bytes exatos."""
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(dados or PERFIL_DELA, ensure_ascii=False, indent=4)
             + "\n").encode()
    (pasta / loader.ARQUIVO_DO_PERSONALIZADO).write_bytes(bruto)
    return bruto


def _copias(pasta: Path) -> list[Path]:
    return sorted((pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PERSONALIZADO)
                  .glob("*.json"))


def _freestyle(pasta: Path) -> dict[str, Any]:
    return dict(json.loads((pasta / loader.ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")))


# =============================================================================
# 1. A MIGRAÇÃO — o disco de mentira
# =============================================================================

def test_o_nome_e_o_arquivo_sao_do_freestyle() -> None:
    """O dono diz «Freestyle», e o asset versionado também."""
    assert loader.NOME_DO_PADRAO == "Freestyle"
    assert loader.ARQUIVO_DO_PADRAO == "freestyle.json"
    assert _freestyle(FABRICA)["name"] == loader.NOME_DO_PADRAO
    assert not (FABRICA / loader.ARQUIVO_DO_PERSONALIZADO).exists(), (
        "o preset «Personalizado» voltou à fábrica: a semeadura entregaria dois "
        "catch-all numa máquina nova")


def test_a_sanidade_nao_acusa_o_freestyle() -> None:
    """O catch-all de fábrica tem nome de perfil genérico, não de jogo perdido.

    `profiles.sanidade` acusa o catch-all cujo nome está fora do
    `VOCABULARIO_GENERICO` — é o padrão do `pragmata`, um perfil de UM programa
    que perdeu a regra. Sem «freestyle» na lista, o perfil de fora do jogo de
    toda máquina nasceria com um aviso na Saúde do sistema.

    MORDE: tire `"freestyle"` do `VOCABULARIO_GENERICO` e o aviso volta.
    """
    from hefesto_dualsense4unix.profiles.sanidade import verificar_perfis

    fabrica = Profile.model_validate(_freestyle(FABRICA))
    assert verificar_perfis([fabrica]) == []


def test_o_personalizado_dela_vira_freestyle_com_a_copia_byte_a_byte() -> None:
    """O caso dela, fim a fim: o nome muda, o conteúdo fica, e os bytes guardam.

    A comparação da cópia é de BYTES, não de dicionário: a volta tem de ser o
    arquivo dela, com a formatação dela. Os quatro controles vêm juntos.
    """
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)

    copia = loader.o_personalizado_vira_freestyle()

    assert copia is not None and copia.read_bytes() == bruto
    assert copia.parent == pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PERSONALIZADO
    assert not (pasta / loader.ARQUIVO_DO_PERSONALIZADO).exists()
    novo = _freestyle(pasta)
    assert novo["name"] == "Freestyle"
    assert novo["controllers"] == QUATRO
    assert novo["leds"] == PERFIL_DELA["leds"]
    assert novo["priority"] == PERFIL_DELA["priority"]
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]


def test_a_volta_existe_e_devolve_o_arquivo_inteiro() -> None:
    """Reversível: `restaurar_do_historico` é a volta que a casa já tinha."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    loader.o_personalizado_vira_freestyle()

    alvo, _versao = loader.restaurar_do_historico(loader.SLUG_DO_PERSONALIZADO)

    assert alvo == pasta / loader.ARQUIVO_DO_PERSONALIZADO
    assert alvo.read_bytes() == bruto


def test_a_segunda_corrida_nao_faz_nada() -> None:
    """One-shot, pela marca: nem cópia nova, nem um byte do Freestyle mexido.

    E o `personalizado.json` que ela criar DEPOIS da marca é dela, e fica.
    """
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    assert loader.o_personalizado_vira_freestyle() is not None
    antes = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()

    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == antes
    assert len(_copias(pasta)) == 1

    loader.save_profile(Profile(name="Personalizado",
                                match=MatchCriteria(window_class=["firefox"])))
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).is_file()


def test_sem_copia_nada_muda_e_a_marca_nao_nasce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apagar sem volta é o único desfecho que a migração não tem.

    Com o histórico recusando (disco cheio, permissão), o arquivo FICA, o
    Freestyle não nasce e a marca não é escrita — a próxima carga tenta de novo.
    """
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    # `context()` e nunca `undo()`: o `undo` desfaria também o isolamento do
    # conftest, que usa o MESMO `monkeypatch`.
    with monkeypatch.context() as m:
        m.setattr(loader, "_arquivar_versao", lambda *a, **k: None)
        assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()
    assert not (pasta / loader._PERSONALIZADO_VIROU_FREESTYLE_MARKER).exists()

    assert loader.o_personalizado_vira_freestyle() is not None
    assert _freestyle(pasta)["controllers"] == QUATRO


def test_a_escrita_que_falha_deixa_o_arquivo_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ordem: a cópia, o novo, e SÓ ENTÃO o antigo sai.

    MORDE: troque a ordem em `_trocar_o_personalizado` (o `unlink` antes do
    `_atomic_write_json`) e o arquivo dela some com o disco cheio.
    """
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)

    def _disco_cheio(*_a: Any, **_k: Any) -> None:
        raise OSError(28, "No space left on device")

    with monkeypatch.context() as m:
        m.setattr(loader, "_atomic_write_json", _disco_cheio)
        with pytest.raises(OSError):
            loader.o_personalizado_vira_freestyle()
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert [c.read_bytes() for c in _copias(pasta)] == [bruto]
    assert not (pasta / loader._PERSONALIZADO_VIROU_FREESTYLE_MARKER).exists()


def test_a_regra_da_nossa_janela_vira_any_e_a_dela_fica() -> None:
    """O Freestyle é o perfil de FORA do jogo: a regra que só mira o Hefesto sai.

    Com `Hefesto-Dualsense4Unix` na regra, o boot o pulava
    (`_escopado_a_janela`) e o autoswitch nunca o escolhia (a nossa janela é
    `OWN_GUI_WM_CLASSES`) — um perfil que nenhum caminho ativa. Uma regra que
    ela escreveu para outro programa é dela, e fica.
    """
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    loader.o_personalizado_vira_freestyle()
    assert _freestyle(pasta)["match"] == {"type": "any"}


def test_a_regra_dela_para_outro_programa_fica() -> None:
    pasta = profiles_dir(ensure=True)
    dela = dict(PERFIL_DELA, match={"type": "criteria", "window_class": ["firefox"]})
    _grava_dela(pasta, dela)
    loader.o_personalizado_vira_freestyle()
    assert _freestyle(pasta)["match"] == {"type": "criteria", "window_class": ["firefox"]}


def test_recusa_quando_ela_ja_tem_um_freestyle() -> None:
    """Um `freestyle.json` que não é o de fábrica é DELA: os dois ficam."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    dela = {"name": "Freestyle", "version": 1, "match": {"type": "any"}, "priority": 7}
    (pasta / loader.ARQUIVO_DO_PADRAO).write_text(json.dumps(dela), encoding="utf-8")

    assert loader.o_personalizado_vira_freestyle() is None

    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert _freestyle(pasta) == dela
    assert _copias(pasta) == []


def test_o_freestyle_de_fabrica_que_o_install_copiou_cede_o_lugar() -> None:
    """O `install_profiles.sh` roda ANTES de qualquer Python e copia a fábrica.

    Esse arquivo não é dela: ele cede o lugar ao Personalizado dela — senão
    ficariam DOIS padrões disputando (`profiles.sanidade`).
    """
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(
        (FABRICA / loader.ARQUIVO_DO_PADRAO).read_bytes())

    assert loader.o_personalizado_vira_freestyle() is not None
    assert _freestyle(pasta)["controllers"] == QUATRO


def test_recusa_quando_ela_renomeou_na_mao() -> None:
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta, dict(PERFIL_DELA, name="Sofá"))
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()


@pytest.mark.parametrize("bruto", [b"{ quebrado", b"[1, 2]"], ids=["texto", "lista"])
def test_json_que_nao_e_perfil_fica_como_esta(bruto: bytes) -> None:
    pasta = profiles_dir(ensure=True)
    (pasta / loader.ARQUIVO_DO_PERSONALIZADO).write_bytes(bruto)
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()


def test_sem_personalizado_nada_acontece_e_a_marca_nasce() -> None:
    pasta = profiles_dir(ensure=True)
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader._PERSONALIZADO_VIROU_FREESTYLE_MARKER).is_file()
    assert not (pasta / loader.HISTORICO_DIR_NAME).exists()


def test_a_copia_mora_na_pasta_que_a_migracao_recebeu(tmp_path: Path) -> None:
    """`dest_dir` injetado leva o histórico junto — nunca o `profiles_dir()`.

    MORDE: tire o `raiz=directory` da chamada ao `_arquivar_versao` e a cópia
    cai no histórico da pasta de sempre, longe do arquivo que saiu.
    """
    outra = tmp_path / "outra"
    bruto = _grava_dela(outra)

    copia = loader.o_personalizado_vira_freestyle(dest_dir=outra)

    assert copia is not None and copia.read_bytes() == bruto
    assert copia.parent == outra / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PERSONALIZADO
    assert not (profiles_dir() / loader.HISTORICO_DIR_NAME).exists()


def test_a_sessao_que_apontava_o_personalizado_aponta_o_freestyle() -> None:
    """Sem isto o boot procuraria um arquivo que virou outro, e ficaria sem perfil."""
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")

    loader.o_personalizado_vira_freestyle()

    assert session.load_last_profile() == "Freestyle"
    assert session.read_active_marker() == "Freestyle"
    assert session.resolve_boot_profile() == "Freestyle"


def test_a_sessao_que_aponta_outro_perfil_nao_e_tocada() -> None:
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Mullet Mad Jack")
    session.save_active_marker("Mullet Mad Jack")

    loader.o_personalizado_vira_freestyle()

    assert session.load_last_profile() == "Mullet Mad Jack"
    assert session.read_active_marker() == "Mullet Mad Jack"


# =============================================================================
# 2. A PRIMEIRA CARGA — o caminho que o produto percorre de verdade
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


def _install_profiles(home: Path) -> subprocess.CompletedProcess[str]:
    """O `scripts/install_profiles.sh` de VERDADE, num HOME de mentira."""
    return subprocess.run(
        ["bash", str(RAIZ / "scripts" / "install_profiles.sh"), str(RAIZ)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=False, timeout=60,
    )


def test_maquina_nova_abre_com_o_freestyle(semeadura_ligada: None) -> None:
    """A primeira carga de perfis do processo — o que o daemon e a janela fazem."""
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]
    assert loader.o_perfil_de_fora_do_jogo() == "Freestyle"


def test_o_disco_de_23_09_vira_freestyle_numa_carga(semeadura_ligada: None) -> None:
    """O disco dela hoje: o Personalizado com os quatro controles, ativo na sessão."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    assert _freestyle(pasta)["controllers"] == QUATRO
    assert [c.read_bytes() for c in _copias(pasta)] == [bruto]
    assert session.resolve_boot_profile() == "Freestyle"


def test_o_disco_de_antes_de_05_09_vai_direto_ao_freestyle(semeadura_ligada: None) -> None:
    """`meu_perfil.json` ativo: a renomeação de 05/09 já leva ao nome de hoje."""
    pasta = profiles_dir(ensure=True)
    velho = dict(PERFIL_DELA, name="meu_perfil", match={"type": "any"})
    (pasta / loader.ARQUIVO_ANTIGO_DO_PADRAO).write_text(
        json.dumps(velho, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    session.save_last_profile("meu_perfil")
    session.save_active_marker("meu_perfil")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    assert (pasta / loader.BACKUP_DO_PADRAO).is_file()
    assert _freestyle(pasta)["controllers"] == QUATRO
    assert session.resolve_boot_profile() == "Freestyle"


def test_o_install_profiles_de_hoje_roda_antes_e_o_dela_vence(
    tmp_path: Path, semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MEDIDA DO ITEM 4: o `install.sh` chama o shell antes de qualquer Python.

    O shell de hoje não conhece o nome novo: ele copia o `freestyle.json` de
    fábrica AO LADO do `personalizado.json` dela. A primeira carga do Python
    resolve — a fábrica intocada cede o lugar — e a lista abre com UM Freestyle,
    o dela. O que o shell precisa para nem chegar a copiar está no relatório da
    sprint, para quem coordena o install.
    """
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    assert profiles_dir() == pasta
    _grava_dela(pasta)

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]
    assert _freestyle(pasta)["controllers"] == QUATRO
    assert not (pasta / loader.ARQUIVO_DO_PERSONALIZADO).exists()


def test_o_install_profiles_depois_do_python_nao_traz_um_segundo(
    tmp_path: Path, semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O marker é contrato dos dois semeadores: depois do Python, o shell não copia."""
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    _grava_dela(pasta)
    loader.load_all_profiles()
    antes = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    assert sorted(p.name for p in pasta.glob("*.json")) == [loader.ARQUIVO_DO_PADRAO]
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == antes


# =============================================================================
# 3. O BOOT — a matriz da sprint
# =============================================================================

class _ControleQueGuarda(FakeController):
    """O `FakeController` que GUARDA o mapa por controle que o perfil manda.

    A base (`IController.reset_output_overrides`) é no-op: um dublê que não
    guardasse nada responderia verde sobre um boot que não levou os ajustes.
    """

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.camada: dict[str, Any] = {}

    def reset_output_overrides(self, overrides: Any = None) -> None:
        self.camada = dict(overrides or {})


async def _bloqueante(fn: Any, *args: Any) -> Any:
    return fn(*args)


def _boot(controle: FakeController, store: StateStore) -> None:
    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante,
        _native_mode=False)))


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_boot_restaura_o_freestyle_com_os_quatro_controles(
    semeadura_ligada: None, transporte: str,
) -> None:
    """O disco dela, uma carga, e o boot: o Freestyle vale, com os quatro."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    loader.load_all_profiles()
    controle = _ControleQueGuarda(transport=transporte)
    controle.connect()
    store = StateStore()

    _boot(controle, store)

    assert store.active_profile == "Freestyle"
    assert len(controle.camada) == 4, controle.camada


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_sem_sessao_o_boot_cai_no_freestyle(semeadura_ligada: None, transporte: str) -> None:
    """Máquina nova, ninguém ativou nada na mão: o boot não fica sem perfil.

    Era o trecho do boot ao primeiro jogo, e com o Modo Freestyle ligado (ou sem
    leitor de janela) ele não acabava nunca: o autoswitch não troca por janela
    comum com a trava ligada.

    MORDE: tire o `o_perfil_de_fora_do_jogo()` de `restore_last_profile` e o
    boot volta a deixar `active_profile` vazio.
    """
    loader.load_all_profiles()
    controle = _ControleQueGuarda(transport=transporte)
    controle.connect()
    store = StateStore()
    store.set_autoswitch_locked(True)

    _boot(controle, store)

    assert store.active_profile == "Freestyle"
    assert session.load_last_profile() is None, (
        "o boot gravou a sessão: restauro de sistema não é gesto dela")


def test_sem_freestyle_no_disco_o_boot_nao_inventa(semeadura_ligada: None,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o arquivo (ela o apagou), o boot fica como sempre ficou: sem perfil."""
    loader.load_all_profiles()
    (profiles_dir() / loader.ARQUIVO_DO_PADRAO).unlink()
    store = StateStore()
    controle = _ControleQueGuarda()
    controle.connect()

    _boot(controle, store)

    assert store.active_profile is None


def _cena(travado: bool) -> list[str | None]:
    """O boot, o desktop, um jogo com perfil próprio, e o desktop de novo.

    O `restore_last_profile`, o `AutoSwitcher` e o `ProfileManager` são os REAIS.
    Devolve o perfil ativo depois do boot e ao fim de cada uma das três janelas.
    """
    loader.load_all_profiles()
    loader.save_profile(Profile(name="Mullet Mad Jack",
                                match=MatchCriteria(window_class=[JOGO]),
                                priority=80))
    store = StateStore()
    store.set_autoswitch_locked(travado)
    controle = _ControleQueGuarda()
    controle.connect()
    _boot(controle, store)
    ativos: list[str | None] = [store.active_profile]
    sw = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                      window_reader=lambda: {}, store=store)
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


def test_com_o_modo_freestyle_ligado_o_jogo_entra_por_cima_e_fica(
    semeadura_ligada: None,
) -> None:
    """`D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA`: o perfil do jogo entra.

    E a trava faz o que o nome diz: ao voltar ao desktop, janela comum nenhuma
    troca o perfil — o do jogo fica até ela desligar o Modo Freestyle.
    """
    assert _cena(travado=True) == ["Freestyle", "Freestyle", "Mullet Mad Jack",
                                   "Mullet Mad Jack"]


def test_com_o_modo_freestyle_desligado_a_volta_e_ao_freestyle(
    semeadura_ligada: None,
) -> None:
    assert _cena(travado=False) == ["Freestyle", "Freestyle", "Mullet Mad Jack",
                                    "Freestyle"]


# =============================================================================
# 4. AS TELAS QUE DEPENDEM DELE
# =============================================================================

def _brilho_sem_daemon() -> str:
    """O brilho da aba 04 com o daemon calado: o que o gesto responde.

    É o caminho de toda aba que grava no perfil ativo (02 a 08): o alvo vem de
    `perfil.nome_do_ativo`, que pergunta ao daemon e depois ao disco.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    try:
        a04.brilho(Contexto(state={"active_profile": None, "controllers": []}),
                   {"uniq": "aa:bb:cc:00:00:01", "valor": "50"}, None)
    except RuntimeError as recusa:
        return str(recusa)
    return ""


def test_com_o_freestyle_as_abas_tem_onde_guardar(semeadura_ligada: None) -> None:
    """A medição que derrubou o motor da 01, com o sinal que a decisão pediu.

    No disco dela, depois da migração, o ajuste tem alvo — o Freestyle, pela
    sessão — e o brilho só recusa porque o controle da cena não está ligado.
    """
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    loader.load_all_profiles()

    assert "não há perfil ativo" not in _brilho_sem_daemon()


def test_o_topo_diz_freestyle(semeadura_ligada: None) -> None:
    """Fora do jogo, o chip «Perfil ativo» diz «Freestyle» — nunca o nome que saiu."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto, topo

    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    loader.load_all_profiles()

    ctx = Contexto(state={"active_profile": None, "controllers": []})
    assert topo(ctx)["perfil"] == "Freestyle"
