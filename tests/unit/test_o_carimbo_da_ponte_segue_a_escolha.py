"""O-CARIMBO-DA-PONTE-SEGUE-A-ESCOLHA-DELA-01 — a escolha do usuário carimba a ponte.

Medido no diário de 01/10 (Pro Jank Footy): às 19h04 ela trocou o modo para
Xbox pela janela, o escritor único gravou `mode.caminho="xbox"` e deixou o
carimbo `dualsense` onde a escada o tinha posto; às 19h17 o serviço avisou
`ponte_confirmada_diverge_do_perfil` sobre a escolha do usuário. Havia dois
escritores da mesma escolha: o modo (na troca) e o carimbo (a escada, no
tique), e a troca à mão só passava pelo primeiro.

A cura: o escritor único do modo (`Daemon.gravar_o_modo_escolhido` →
`manager.gravar_o_modo_no_perfil_ativo`) grava o `mode` e o `ponte` NA MESMA
gravação, com `por=escolha_dela`, quando o perfil que grava é o do jogo que o
wrapper lançou e que ainda roda. Fora de jogo, nada de carimbo. E a escada não
rebaixa a escolha do usuário para «silêncio» nem para «gesto» quando a ponte é a
mesma (`ProfileManager.confirmar_ponte`).

A BANCADA: o `Daemon` é o real, os perfis moram no `XDG_CONFIG_HOME` do teste
(o `conftest` isola), e só a borda que diz «há jogo do wrapper vivo» e «este
jogo está na allowlist do Steam Input» é dublada (`launch_env`). O disco é lido
pelo `loader`, nunca pelo retorno do escritor. A MORDIDA de cada régua está no
docstring dela.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.integrations import ponte_escada, ponte_tentativa
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ligar_o_freestyle
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.profiles.slug import slugify
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

APPID = 1234560
JANELA = f"steam_app_{APPID}"
JOGO = "Jogo da Régua do Carimbo"
FREESTYLE = loader.NOME_DO_PADRAO
CARIMBO_DE_ANTES = "2026-10-01T19:00:00-03:00"


@pytest.fixture
def jogo_vivo(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """O jogo do wrapper rodando e com o controle (a borda do `launch_env`), fora da allowlist."""
    borda: dict[str, object] = {"appid": APPID, "allowlist": set()}
    monkeypatch.setattr(
        launch_env, "launch_session_appid", lambda **_kw: borda["appid"]
    )
    monkeypatch.setattr(launch_env, "_jogo_na_autoridade", lambda _d: True)
    monkeypatch.setattr(
        launch_env, "steam_input_appids", lambda *_a, **_kw: set(borda["allowlist"])  # type: ignore[call-overload]
    )
    return borda


def _daemon() -> Daemon:
    return Daemon(controller=FakeController(transport="bt"), config=DaemonConfig())


def _perfil_do_jogo_carimbado_por_silencio() -> None:
    loader.save_profile(
        Profile(
            name=JOGO,
            match=MatchCriteria(window_class=[JANELA]),
            mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
            ponte=PonteConfirmada(
                kind="gamepad",
                gamepad_flavor="dualsense",
                confirmada_por="silencio",
                confirmada_em=CARIMBO_DE_ANTES,
            ),
        ),
        origem="régua",
    )


def _arquivo(nome: str) -> Path:
    return profiles_dir() / f"{slugify(nome)}.json"


def _sha(nome: str) -> str:
    return hashlib.sha256(_arquivo(nome).read_bytes()).hexdigest()


def _versoes(nome: str) -> int:
    return len(loader.listar_historico(nome))


def _no_disco(nome: str) -> Profile:
    return loader.load_profile(nome)


def _divergencia(nome: str) -> tuple[str, str, str] | None:
    perfil = _no_disco(nome)
    return ponte_escada.divergencia_com_o_carimbo(
        perfil, ponte_escada.ponte_do_carimbo(perfil.ponte), na_allowlist=False
    )


def _escolher_xbox(d: Daemon, *, porta: str = "ipc") -> str | None:
    return d.gravar_o_modo_escolhido("gamepad", caminho="xbox", porta=porta)  # type: ignore[arg-type]


def test_a_escolha_carimba(jogo_vivo: dict[str, object]) -> None:
    """Régua 1: o Xbox escolhido com o jogo valendo carimba `escolha_dela`.

    MORDIDA: tire o carimbo de `gravar_o_modo_no_perfil_ativo` (o `ponte` fora
    do `mudou`) e o disco mostra o par `xbox`/`dualsense`, como às 19h17.
    """
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    d.store.set_active_profile(JOGO)

    assert _escolher_xbox(d) == JOGO

    perfil = _no_disco(JOGO)
    assert perfil.mode is not None and perfil.mode.caminho == "xbox"
    assert perfil.ponte is not None
    par = (perfil.ponte.gamepad_flavor, perfil.ponte.confirmada_por)
    assert par == ("xbox", "escolha_dela"), (
        f"a escolha dela trocou o modo e o carimbo seguiu {par!r}: o aviso das 19h17")
    assert perfil.ponte.kind == "gamepad" and perfil.ponte.steam_input is False
    assert _divergencia(JOGO) is None, f"o perfil diverge do carimbo: {_divergencia(JOGO)}"


def test_o_steam_input_vivo_vai_no_carimbo(jogo_vivo: dict[str, object]) -> None:
    """O jogo na allowlist do Steam Input: o carimbo leva `steam_input=True`.

    É a mesma pergunta que a escada faz (`appid in steam_input_appids()`); sem
    ela, o carimbo nasceria divergente no termo `steam_input`.
    """
    jogo_vivo["allowlist"] = {APPID}
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    d.store.set_active_profile(JOGO)

    _escolher_xbox(d)

    perfil = _no_disco(JOGO)
    assert perfil.ponte is not None and perfil.ponte.steam_input is True
    assert ponte_escada.divergencia_com_o_carimbo(
        perfil, ponte_escada.ponte_do_carimbo(perfil.ponte), na_allowlist=True
    ) is None


def test_fora_de_jogo_sem_carimbo(jogo_vivo: dict[str, object]) -> None:
    """Régua 2: com o Freestyle valendo, o perfil do jogo não muda.

    E sem jogo do wrapper vivo, o perfil do jogo ativo à mão ganha o modo e
    não ganha carimbo: o carimbo é «confirmada NESTE jogo».

    MORDIDA: carimbar sempre (sem a conferência de que o perfil que grava é o
    do jogo vivo) e o perfil do jogo muda, ou o Freestyle ganha carimbo.
    """
    _perfil_do_jogo_carimbado_por_silencio()
    loader.save_profile(
        Profile(
            name=FREESTYLE,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
        ),
        origem="régua",
    )
    d = _daemon()
    ligar_o_freestyle(d.store, True)
    d.store.set_active_profile(FREESTYLE)
    do_jogo_antes = _sha(JOGO)

    assert _escolher_xbox(d) == FREESTYLE

    assert _sha(JOGO) == do_jogo_antes, "a escolha no Freestyle mexeu no perfil do jogo"
    freestyle = _no_disco(FREESTYLE)
    assert freestyle.mode is not None and freestyle.mode.caminho == "xbox"
    assert freestyle.ponte is None, "o Freestyle ganhou um carimbo de jogo"

    ligar_o_freestyle(d.store, False)
    d.store.set_active_profile(JOGO)
    jogo_vivo["appid"] = None
    _escolher_xbox(d)
    perfil = _no_disco(JOGO)
    assert perfil.mode is not None and perfil.mode.caminho == "xbox"
    assert perfil.ponte is not None and perfil.ponte.confirmada_por == "silencio", (
        "sem jogo vivo a escolha carimbou o perfil do jogo")


def test_uma_gravacao(jogo_vivo: dict[str, object]) -> None:
    """Régua 3: o `.historico` ganha UMA versão por escolha, não duas.

    E a escolha repetida, com nada a mudar, não grava de novo.

    MORDIDA: gravar o carimbo num segundo `save_profile` (pelo
    `confirmar_ponte`, depois do modo) e o histórico ganha duas versões.
    """
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    d.store.set_active_profile(JOGO)
    versoes = _versoes(JOGO)

    _escolher_xbox(d)
    assert _versoes(JOGO) == versoes + 1, (
        f"uma escolha deixou {_versoes(JOGO) - versoes} versões no `.historico`")

    _escolher_xbox(d)
    assert _versoes(JOGO) == versoes + 1, "a escolha repetida gravou de novo"


def test_a_escolha_repetida_conserta_o_carimbo_divergente(
    jogo_vivo: dict[str, object],
) -> None:
    """O modo já em Xbox e o carimbo em DualSense (o disco das 19h04 a 19h18).

    Ela escolhe Xbox de novo: o modo não muda, e o carimbo se alinha. Sem isto,
    um perfil que já divergiu antes da cura seguiria divergente até a volta
    dela ao modo antigo, que foi como o aviso sumiu em 01/10.
    """
    _perfil_do_jogo_carimbado_por_silencio()
    perfil = _no_disco(JOGO)
    loader.save_profile(
        perfil.model_copy(
            update={"mode": ProfileModeConfig(kind="gamepad", caminho="xbox")}
        ),
        origem="régua",
    )
    assert _divergencia(JOGO) == ("caminho", "xbox", "dualsense"), "premissa"
    d = _daemon()
    d.store.set_active_profile(JOGO)

    _escolher_xbox(d)

    assert _divergencia(JOGO) is None
    assert _no_disco(JOGO).ponte.confirmada_por == "escolha_dela"  # type: ignore[union-attr]


def test_o_controle_tambem(jogo_vivo: dict[str, object]) -> None:
    """Régua 4: a porta do PS + R3 (`controle`) carimba igual, sem os 180 s.

    MORDIDA: carimbar só com `porta="ipc"` e o carimbo segue `dualsense`.
    """
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    d.store.set_active_profile(JOGO)

    _escolher_xbox(d, porta="controle")

    perfil = _no_disco(JOGO)
    assert perfil.ponte is not None
    assert (perfil.ponte.gamepad_flavor, perfil.ponte.confirmada_por) == (
        "xbox", "escolha_dela")


def test_todo_modo_leva_o_kind(jogo_vivo: dict[str, object]) -> None:
    """O Mouse e Teclado (`kind=desktop`) carimba `desktop`, sem máscara."""
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    d.store.set_active_profile(JOGO)

    d.gravar_o_modo_escolhido("desktop", porta="ipc")

    perfil = _no_disco(JOGO)
    assert perfil.ponte is not None
    assert (perfil.ponte.kind, perfil.ponte.gamepad_flavor, perfil.ponte.confirmada_por) == (
        "desktop", None, "escolha_dela")
    assert _divergencia(JOGO) is None


@pytest.mark.parametrize("gestos", [0, 1], ids=["silencio", "gesto"])
def test_a_escada_nao_desfaz_a_escolha(
    jogo_vivo: dict[str, object], gestos: int
) -> None:
    """Régua 5: um tique da escada com a mesma ponte não rebaixa `escolha_dela`.

    O caminho medido é o do PS + R3: o escritor carimba na hora, e o gesto fica
    anotado (`ponte_tentativa.gesto_deixou_de_pe`). Depois do silêncio, o tique
    de 1 Hz pede o carimbo da MESMA ponte, `por=gesto` (ou `por=silencio`, sem
    gesto contado). A escolha do usuário fica, e nada se grava.

    MORDIDA: tire a guarda de `ProfileManager.confirmar_ponte` e o carimbo
    vira `gesto`/`silencio` por cima da escolha.
    """
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    d.store.set_active_profile(JOGO)
    _escolher_xbox(d, porta="controle")
    versoes = _versoes(JOGO)
    ponte_tentativa._guardar_o_gesto(
        d,
        ponte_tentativa.GestoDela(
            appid=APPID,
            ponte=ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, "xbox"),
            ultimo_gesto=0.0,
            gestos=gestos,
        ),
    )

    launch_env.tique_da_escada(d, agora=ponte_escada.SILENCIO_CONFIRMA_SEC + 1.0)

    assert ponte_tentativa.gesto_em_curso(d) is None, "premissa: o tique colheu o gesto"
    perfil = _no_disco(JOGO)
    assert perfil.ponte is not None
    assert (perfil.ponte.gamepad_flavor, perfil.ponte.confirmada_por) == (
        "xbox", "escolha_dela"), (
        f"a escada regravou a escolha dela como {perfil.ponte.confirmada_por!r}")
    assert _versoes(JOGO) == versoes, "a escada gravou uma versão sem nada a mudar"


def test_a_escada_ainda_carimba_onde_a_escolha_nao_carimbou(
    jogo_vivo: dict[str, object],
) -> None:
    """A guarda é só da MESMA ponte: outra ponte de pé, a escada carimba como antes."""
    _perfil_do_jogo_carimbado_por_silencio()
    d = _daemon()
    ponte_tentativa._guardar_o_gesto(
        d,
        ponte_tentativa.GestoDela(
            appid=APPID,
            ponte=ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, "xbox"),
            ultimo_gesto=0.0,
            gestos=1,
        ),
    )

    launch_env.tique_da_escada(d, agora=ponte_escada.SILENCIO_CONFIRMA_SEC + 1.0)

    perfil = _no_disco(JOGO)
    assert perfil.ponte is not None
    assert (perfil.ponte.gamepad_flavor, perfil.ponte.confirmada_por) == ("xbox", "gesto")
