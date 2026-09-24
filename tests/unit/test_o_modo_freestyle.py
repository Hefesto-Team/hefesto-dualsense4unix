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
o perfil que estava continua valendo, e o topo diz o nome dele. E do boot ao
primeiro jogo não há perfil nenhum, e as abas ficam sem onde guardar o ajuste —
por isso o motor espera a sessão dela (`loader.O_PERSONALIZADO_ESPERA_A_SESSAO_DELA`).
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


@pytest.fixture
def saida_liberada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O motor como fica no dia do `--publicar 01`: a saída deixa de esperar.

    O produto de hoje espera a sessão dela (`test_a_saida_espera_a_sessao_dela`);
    as réguas do motor medem o que ele faz quando ligar.
    """
    monkeypatch.setattr(loader, "O_PERSONALIZADO_ESPERA_A_SESSAO_DELA", False)


# =============================================================================
# 1. A SEMEADURA — o preset não chega a máquina nenhuma
# =============================================================================

def test_a_fabrica_de_verdade_nao_semeia_o_personalizado(
    tmp_path: Path, saida_liberada: None,
) -> None:
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


def test_o_marker_fecha_a_porta_do_install_profiles_tambem(
    tmp_path: Path, saida_liberada: None,
) -> None:
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


def test_a_copia_mora_na_pasta_que_a_migracao_recebeu(tmp_path: Path) -> None:
    """`dest_dir` injetado leva o histórico junto — nunca o `profiles_dir()`.

    MORDE: tire o `raiz=directory` da chamada ao `_arquivar_versao` e a cópia
    cai no histórico da pasta de sempre, longe do arquivo que saiu.
    """
    outra = tmp_path / "outra"
    bruto = _grava_dela(outra)

    copia = loader.aposentar_o_personalizado(dest_dir=outra)

    assert copia is not None and copia.read_bytes() == bruto
    assert copia.parent == outra / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO
    assert not (profiles_dir() / loader.HISTORICO_DIR_NAME).exists()


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
    """Liga a semeadura (o conftest a desliga) contra a FÁBRICA versionada.

    Sem mexer na espera: quem mede o motor pede também `saida_liberada`.
    """
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    # O censo dos jogos não é assunto desta régua, e a máquina de quem roda a
    # suíte não pode decidir o resultado.
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


def test_maquina_nova_abre_sem_o_personalizado(
    semeadura_ligada: None, saida_liberada: None,
) -> None:
    """A MORDIDA DA SPRINT: devolva o preset ao semeador e esta régua reprova.

    Máquina nova, a primeira carga de perfis do processo — o que o daemon e a
    interface fazem ao abrir. Nenhuma linha «Personalizado» nasce.
    """
    assert "Personalizado" not in [p.name for p in loader.load_all_profiles()]
    assert not (profiles_dir() / loader.ARQUIVO_DO_PADRAO).exists()


def test_o_que_o_install_semeou_sai_na_primeira_carga(
    semeadura_ligada: None, saida_liberada: None,
) -> None:
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
    semeadura_ligada: None, saida_liberada: None,
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
    """O boot, o desktop, um jogo com perfil próprio, e o desktop de novo.

    O `restore_last_profile`, o `AutoSwitcher` e o `ProfileManager` são os
    REAIS. O BOOT ENTRA NA CENA, e é a perna que a primeira versão desta régua
    não tinha: o Personalizado da máquina dela não chega pela janela, chega pela
    SESSÃO (`session.json` e `active_profile.txt` o apontam), e o restauro de
    boot ignora o cadeado (`test_autoswitch_lock`). Sem ela, a cena começava com
    o estado vazio e respondia sobre o autoswitch, não sobre o produto.

    Devolve o perfil ativo depois do boot e ao fim de cada uma das três janelas.
    """
    loader.save_profile(Profile(name="Mullet Mad Jack",
                                match=MatchCriteria(window_class=[JOGO]),
                                priority=80))
    if com_personalizado:
        loader.save_profile(Profile.model_validate(json.loads(
            (FABRICA / loader.ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))))
        session.save_last_profile("Personalizado")
        session.save_active_marker("Personalizado")
    store = StateStore()
    store.set_autoswitch_locked(travado)
    controle = FakeController()
    controle.connect()

    async def bloqueante(fn: Any, *args: Any) -> Any:
        return fn(*args)

    asyncio.run(connection.restore_last_profile(SimpleNamespace(
        controller=controle, store=store, _run_blocking=bloqueante,
        _native_mode=False)))
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


@pytest.mark.parametrize("travado", [False, True], ids=["freestyle-desligado",
                                                         "freestyle-ligado"])
def test_sem_o_personalizado_nada_troca_quando_nenhum_jogo_casa(travado: bool) -> None:
    """A resposta da medição: o perfil que estava continua valendo.

    Do boot ao primeiro jogo não há perfil nenhum; o jogo entra; e voltar ao
    desktop NÃO troca — não há candidato, e o autoswitch não ativa ninguém sem
    candidato. Igual com o Modo Freestyle ligado ou desligado.
    """
    assert _cena(com_personalizado=False, travado=travado) == [
        None, None, "Mullet Mad Jack", "Mullet Mad Jack"]


def test_a_trava_faz_metade_do_que_o_personalizado_fazia() -> None:
    """A frase dela, medida: *"O trava perfil ativo já faz isso."* — em parte.

    Com a trava LIGADA (o disco dela), nenhuma janela comum devolve o
    Personalizado depois do jogo: essa metade a trava já fazia. A outra metade
    ela não faz: o boot o reativa pela sessão, e ele vale no desktop até o
    primeiro jogo — o trecho que, sem ele, fica sem perfil nenhum.
    """
    assert _cena(com_personalizado=True, travado=True) == [
        "Personalizado", "Personalizado", "Mullet Mad Jack", "Mullet Mad Jack"]
    for arquivo in profiles_dir().glob("*.json"):
        arquivo.unlink()
    assert _cena(com_personalizado=True, travado=False) == [
        "Personalizado", "Personalizado", "Mullet Mad Jack", "Personalizado"]


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


def test_sem_o_personalizado_as_abas_ficam_sem_onde_guardar(
    saida_liberada: None,
) -> None:
    """A metade que a trava não faz, medida numa tela: do boot ao primeiro jogo.

    No disco dela, antes da saída, o ajuste tem alvo (o Personalizado, pela
    sessão) e o brilho só recusa porque o controle da cena não está ligado.
    Depois, o mesmo clique recusa por falta de perfil. É a pergunta que o
    desenho leva à sessão dela, e a razão de a saída esperar por ela.
    """
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    assert "não há perfil ativo" not in _brilho_sem_daemon()

    loader.aposentar_o_personalizado()

    assert "não há perfil ativo" in _brilho_sem_daemon()


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


# =============================================================================
# 5. A MATRIZ — o Modo Freestyle é um só, para os quatro, nos dois transportes
# =============================================================================

class _Ponte:
    """Responde ao `autoswitch_lock_set` como `ipc_bridge` responde: o estado
    que ficou valendo. Nada mais frouxo que o real — um `True` para tudo
    mentiria sobre um pedido de soltar."""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def autoswitch_lock_set(self, locked: bool | None = None) -> bool | None:
        self.chamadas.append({"locked": locked})
        return locked


def _mesa_de_quatro() -> list[dict[str, Any]]:
    """P1 e P3 no cabo, P2 e P4 no rádio — a mesa inteira, não só o P1."""
    return [{"uniq": f"aa:bb:cc:00:00:0{n}", "player": n, "connected": True,
             "transport": "usb" if n % 2 else "bluetooth"} for n in (1, 2, 3, 4)]


@pytest.mark.parametrize("caminho", ["dualsense", "xbox", "steam_input"])
@pytest.mark.parametrize("travado", [False, True], ids=["liga", "desliga"])
def test_o_freestyle_e_um_so_para_a_mesa_inteira(caminho: str, travado: bool) -> None:
    """Um clique, UMA chamada, com o valor absoluto — em qualquer caminho.

    O Modo Freestyle trava a TROCA DE PERFIL, que é da máquina inteira: o gesto
    não lê o controle escolhido na fita, nem o transporte, nem o caminho. Se um
    dia ele virar por controle, esta régua reprova e a decisão volta a ela.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba

    mesa = _mesa_de_quatro()
    estado = {"controllers": mesa, "autoswitch_locked": travado,
              "gamepad_emulation": {"caminho": caminho}}
    ponte = _Ponte()

    aba.cadeado(Contexto(state=estado, mesa=mesa, conectados=mesa),
                {"evento": "click"}, ponte)

    assert ponte.chamadas == [{"locked": not travado}]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_com_o_freestyle_ligado_a_janela_de_jogo_nao_troca_o_perfil(
    transporte: str,
) -> None:
    """A prova da sprint, no motor: liga o modo e abre uma janela de jogo.

    Nos dois transportes, com o controle de mentira no cabo e no rádio: a trava
    é da máquina, e o transporte não pode decidir o resultado.

    O jogo aqui não tem perfil próprio — e é o caso em que a trava segura. O
    jogo COM perfil próprio entra por cima (LOCK-CEDE-01, decisão dela de
    24/07), e isso não mudou: `test_autoswitch_lock` guarda aquela metade.
    """
    loader.save_profile(Profile(name="Navegação",
                                match=MatchCriteria(window_class=["steam"]),
                                priority=50))
    store = StateStore()
    store.set_active_profile("Mullet Mad Jack")
    store.set_autoswitch_locked(True)
    controle = FakeController(transport=transporte)
    controle.connect()
    sw = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                      window_reader=lambda: {}, store=store)

    for janela in ({"wm_class": JOGO, "wm_name": "Mullet Mad Jack"},
                   {"wm_class": "steam", "wm_name": "Steam"}):
        for t in (0.0, 0.6, 30.0, 60.0):
            sw._tick(janela, t)

    assert store.active_profile == "Mullet Mad Jack"


# =============================================================================
# 6. A TELA — o desenho diz «Modo Freestyle», e a publicada espera a sessão dela
# =============================================================================

def _rotulo_do_botao(html: str) -> str:
    import re

    achado = re.search(r'<button class="cadeado"[^>]*><span class="p"></span>([^<]+)</button>',
                       html)
    assert achado, "a página não tem o botão do canto do bloco Modo"
    return achado.group(1).strip()


def test_o_desenho_diz_modo_freestyle() -> None:
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes.a01_jogar import CADEADO_ROTULO

    assert CADEADO_ROTULO == "Modo Freestyle"
    assert _rotulo_do_botao(onde.pagina("01-jogar.html").read_text()) == CADEADO_ROTULO


def test_a_palavra_de_ontem_tem_prazo() -> None:
    """A isenção morre no `--publicar 01`, e esta régua é o prazo dela.

    Enquanto a publicada disser a palavra de ontem, a constante que a declara
    tem de existir e casar com ela. No dia em que a publicada disser «Modo
    Freestyle», esta régua reprova até a constante sair — no mesmo commit.
    """
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba

    publicado = _rotulo_do_botao(onde.pagina("01-jogar.html", publicado=True).read_text())
    assert publicado != aba.CADEADO_ROTULO, (
        "a aba 01 foi publicada com «Modo Freestyle»: apague "
        "`a01_jogar.CADEADO_ROTULO_ESPERANDO_A_SESSAO_DELA`, a isenção em "
        "`test_o_cadeado_mora_no_canto_do_bloco`, e esta régua")
    assert publicado == aba.CADEADO_ROTULO_ESPERANDO_A_SESSAO_DELA


def test_a_saida_espera_a_sessao_dela() -> None:
    """O motor liga no mesmo commit do `--publicar 01`, com a resposta dela.

    Tirar o Personalizado muda o que o topo diz do boot ao primeiro jogo, e o
    que o topo diz ali é o que o desenho propõe e ela aprova. Enquanto a
    publicada disser a palavra de ontem, a saída espera; no dia em que disser
    «Modo Freestyle», esta régua reprova até a linha da espera ser decidida.
    """
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba

    publicado = _rotulo_do_botao(onde.pagina("01-jogar.html", publicado=True).read_text())
    esperando = publicado == aba.CADEADO_ROTULO_ESPERANDO_A_SESSAO_DELA
    assert loader.O_PERSONALIZADO_ESPERA_A_SESSAO_DELA is esperando, (
        "a aba 01 e a saída do Personalizado andam juntas: com a publicada "
        f"dizendo {publicado!r}, `loader.O_PERSONALIZADO_ESPERA_A_SESSAO_DELA` "
        f"tem de ser {esperando} — ou o motor sai, se ela escolheu outra coisa "
        "para o trecho do boot ao primeiro jogo")


def test_enquanto_espera_o_disco_dela_fica_como_esta(semeadura_ligada: None) -> None:
    """O produto de hoje: a primeira carga não toca o Personalizado dela.

    MORDE: vire a espera para `False` e o arquivo dela sai antes da sessão —
    com a sessão limpa e o brilho recusando por falta de perfil.
    """
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")

    nomes = [p.name for p in loader.load_all_profiles()]

    assert "Personalizado" in nomes
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
    assert not (pasta / loader._PERSONALIZADO_SAIU_MARKER).exists()
    assert session.resolve_boot_profile() == "Personalizado"
    assert "não há perfil ativo" not in _brilho_sem_daemon()


def test_enquanto_espera_a_maquina_nova_recebe_o_personalizado(
    semeadura_ligada: None,
) -> None:
    """Máquina nova, primeira carga: o preset chega, como em 23/09.

    MORDE: tire a condição da espera do semeador e a máquina nova abre sem ele.
    """
    assert "Personalizado" in [p.name for p in loader.load_all_profiles()]


_MEDE = """() => {
  const cad = document.querySelector('.cadeado');
  const cs = getComputedStyle(cad), b = cad.getBoundingClientRect();
  const texto = [...cad.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
  const r = document.createRange(); r.selectNodeContents(texto);
  const jan = document.querySelector('.janela');
  return {fonte: parseFloat(cs.fontSize), altura: b.height,
          escolha: parseFloat(getComputedStyle(document.documentElement)
                              .getPropertyValue('--h-escolha')),
          linhas: r.getClientRects().length,
          no_topo: cad.closest('.quadro-topo') !== null,
          a_direita: Math.round(cad.closest('.quadro').getBoundingClientRect().right - b.right),
          rola: jan.scrollHeight > jan.clientHeight + 1
                || document.documentElement.scrollHeight > innerHeight + 1};
}"""


@pytest.fixture(scope="module")
def as_duas_paginas() -> dict[str, dict[str, Any]]:
    """O desenho e a publicada, no Chrome, na vista mais apertada (1212x809)."""
    chrome = Path("/usr/bin/google-chrome")
    if not chrome.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    # O QUE O PRODUTO ESCONDE, perguntado ao dono: a legenda do desenho (`.nota`)
    # mora fora da janela e faria o DOCUMENTO rolar numa página que o produto
    # nunca mostra assim.
    esconde = "".join(f"{s}{{display:none}}" for s in seletores_escondidos())
    saida: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(chrome), args=["--no-sandbox"])
        try:
            for nome, publicado in (("desenho", False), ("publicada", True)):
                pg = nav.new_page(viewport={"width": 1212, "height": 809})
                pg.goto(onde.pagina("01-jogar.html", publicado=publicado).as_uri())
                pg.wait_for_load_state("networkidle")
                pg.add_style_tag(content=esconde)
                pg.wait_for_timeout(200)
                saida[nome] = dict(pg.evaluate(_MEDE))
                pg.close()
        finally:
            nav.close()
    return saida


def test_o_botao_do_desenho_tem_letra_e_altura_maiores(
    as_duas_paginas: dict[str, dict[str, Any]],
) -> None:
    """O pedido dela, em pixels: maior que hoje, e ainda um botão de canto.

    MORDE: devolva o `height:17px`/`font-size:10.5px` ao `.cadeado` do
    `aba01.py`, regere o desenho, e esta régua reprova.
    """
    desenho, hoje = as_duas_paginas["desenho"], as_duas_paginas["publicada"]
    assert desenho["fonte"] > hoje["fonte"], (desenho, hoje)
    assert desenho["altura"] > hoje["altura"], (desenho, hoje)
    # Menor que um botão de escolha: da altura dos chips de modo ele voltaria
    # a ler como um quinto modo (o motivo de ter subido ao canto em 08/09).
    assert desenho["altura"] < desenho["escolha"], desenho
    assert desenho["linhas"] == 1, desenho
    assert desenho["no_topo"] and desenho["a_direita"] < 20, desenho


def test_a_aba_continua_sem_rolar(as_duas_paginas: dict[str, dict[str, Any]]) -> None:
    """A conta de altura, paga: a linha do título cresceu e a aba não rola."""
    assert not as_duas_paginas["desenho"]["rola"], as_duas_paginas["desenho"]
