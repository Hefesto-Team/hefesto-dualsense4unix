"""MASCARA-PERSISTE-01 — a máscara fica, até ELA mudar na interface.

Decisão dela, 22/08/2026: *"a máscara deveria ficar independente do jogo, até
que eu mude na interface novamente."*

**E «ELA MUDAR» NÃO É «UM PERFIL PASSAR» — corrigido em 21/09/2026.** A leitura
de 22/08 fez o perfil de um jogo escrever o padrão da MÁQUINA, e o preço está
no §1 de `test_a_mascara_do_perfil_nao_vira_o_padrao_da_maquina`: um perfil
entre 29 levou a máquina inteira para Xbox, e ela perdeu giroscópio,
acelerômetro e touchpad em todos os jogos. A decisão dela não mudou; o que
mudou foi quem conta como «ela».

Medido no journal da máquina dela no mesmo dia, e o que foi medido derruba a
hipótese óbvia: **não é fechar o jogo que reverte a máscara**. A máscara viva
ficou em `dualsense` das 19:02 às 19:41, com jogo abrindo e fechando e com o
autoswitch passando pelo perfil "Navegação" no meio. Quem reverte é a **borda
de processo** — `gamepad_emulation.flag` guardava o `xbox` do último gesto
manual (03:37), e todo restart do daemon relia o disco:

    19:41:33 pid=833705 ... mascara=dualsense ... gamepad_emulation_stopped
    19:41:35 pid=926017 gamepad_emulation_started      flavor=xbox

Com `xbox` não existem touchpad, giroscópio nem acelerômetro — eles só existem
no descritor DualSense. Era isso que sumia.

O segundo revertedor, do mesmo tronco: o stash do Modo Nativo capturava a
máscara do DISCO (`load_gamepad_emulation`), não a do vpad vivo. Entrar e sair
do Modo Nativo devolvia o `xbox` do flag por cima do `dualsense` do perfil.

Estes testes olham o ARQUIVO, de propósito — a suíte monkeypatcha
`save_gamepad_emulation` em vários lugares e não enxergaria a regressão. É a
mesma escolha, e pelo mesmo motivo, de `test_gamepad_persist_so_manual.py`,
que guarda a metade LIGA/DESLIGA da R-07 e continua valendo inteira.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    EMU_APLICADO,
    EMU_BLOQUEADO_POR_JOGO,
    EMU_DESLIGADO,
)
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils.session import (
    _GAMEPAD_DISABLED_FLAG_FILE,
    _GAMEPAD_EMULATION_FLAG_FILE,
    load_gamepad_emulation,
    save_gamepad_emulation,
)


@pytest.fixture
def flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola o config_dir e devolve o caminho do flag da máscara."""
    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path / _GAMEPAD_EMULATION_FLAG_FILE


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


class _Vpad:
    def __init__(self, flavor: str) -> None:
        self.flavor = flavor
        self.backend = "uhid"

    def stop(self) -> None:  # pragma: no cover - simetria
        return


def _perfil_de_jogo(flavor: str | None) -> Profile:
    """Perfil COM opinião (criteria), como o Sackboy dela."""
    mode: dict[str, Any] = {"kind": "gamepad"}
    if flavor is not None:
        mode["gamepad_flavor"] = flavor
    return Profile.model_validate(
        {
            "name": "Sackboy",
            "version": 1,
            "match": {"type": "criteria", "window_class": ["steam_app_1599660"]},
            "priority": 97,
            "mode": mode,
        }
    )


def _vpad_obedece(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """Dublê do seam de emulação que TROCA A MÁSCARA VIVA de verdade.

    O que o código sob teste lê é `self._gamepad_device.flavor` — o EFEITO, não
    o desfecho (ELO-MUDO-01). Um dublê que só devolvesse `EMU_APLICADO` sem
    mexer no device não mediria nada, e é por isso que existe o companheiro
    `_vpad_desobedece`.
    """
    pedidos: list[str | None] = []

    def _desfecho(
        enabled: bool, flavor: str | None = None, *, origin: str = "manual"
    ) -> str:
        pedidos.append(flavor)
        daemon.config.gamepad_emulation_enabled = enabled
        if not enabled:
            daemon._gamepad_device = None
            return EMU_DESLIGADO
        alvo = flavor or daemon.config.gamepad_flavor
        daemon.config.gamepad_flavor = alvo
        daemon._gamepad_device = _Vpad(alvo)
        return EMU_APLICADO

    monkeypatch.setattr(daemon, "set_gamepad_emulation_desfecho", _desfecho)
    return pedidos


def _vpad_desobedece(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch, *, desfecho: str
) -> None:
    """Dublê que responde `desfecho` e NÃO troca a máscara viva.

    É o retrato de dois casos reais: `falhou` (a factory não devolveu device) e
    `recusado_steam_input`. Nenhum dos dois é `bloqueado_por_jogo`, ou seja: os
    dois atravessam o filtro do chamador e chegariam ao disco se a guarda
    olhasse o transporte em vez do efeito.
    """

    def _fixo(
        enabled: bool, flavor: str | None = None, *, origin: str = "manual"
    ) -> str:
        return desfecho

    monkeypatch.setattr(daemon, "set_gamepad_emulation_desfecho", _fixo)


def test_a_regua_ve_o_arquivo(flag: Path) -> None:
    """Sanidade do arranjo: sem isolar o config_dir, o resto não prova nada."""
    assert not flag.exists()
    save_gamepad_emulation(True, "xbox")
    assert flag.read_text(encoding="utf-8").strip() == "xbox"
    assert load_gamepad_emulation() == (True, "xbox")


def test_a_mascara_do_perfil_nao_vira_o_padrao_da_maquina(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**ESTA RÉGUA MEDIA A CAUSA DO DEFEITO DELA, e foi invertida em
    21/09/2026 — MASCARA-CONTAGIO-01.**

    Ela cobrava o contrário: que aplicar um perfil com `gamepad_flavor`
    ESCREVESSE aquele valor no `gamepad_emulation.flag`, que é o padrão da
    MÁQUINA. A intenção de 22/08 era boa e a leitura da decisão dela era pela
    metade — *"a máscara deveria ficar independente do jogo, até que eu mude na
    interface novamente"*. O que ela chama de *"eu mudar"* é o GESTO dela, e o
    perfil de um jogo não é gesto de ninguém.

    **O PREÇO, medido no disco dela em 21/09:** de 29 perfis, UM
    (`future_knight.json`) tinha `mode.gamepad_flavor: "xbox"`. Bastou aquele
    jogo abrir uma vez para o `xbox` virar o padrão da máquina — e ali ele
    ficava, porque perfil com `null` retorna cedo e nunca desfaz. Daí em diante
    TODO controle sem entrada no registro nascia Xbox, sem touchpad, sem
    giroscópio e sem acelerômetro. A queixa dela chegou como *"O PERFIL
    PRAGMATA (…) ALGO O MUDA NOVAMENTE PRA XBOX SEMPRE QUE EU O INICIO"* — e o
    PRAGMATA nunca pediu Xbox. É a mesma família do CAMINHO-CONTAGIO-01.

    **O QUE CONTINUA VALENDO da medição de 22/08:** a borda de processo É o
    revertedor, e o disco É o que o boot lê. Por isso o conserto não foi
    deixar o perfil escrever menos — foi tirar dele a caneta e dar ao boot a
    devolução do vazamento (`_a_mascara_dela_sem_o_vazamento`).

    MORDIDA: devolva o corpo de `_gravar_mascara_do_perfil`. A linha do disco
    reprova, e com ela volta o defeito que ela relatou.
    """
    save_gamepad_emulation(True, "xbox")
    _vpad_obedece(daemon, monkeypatch)

    perfil = _perfil_de_jogo("dualsense")
    assert daemon.apply_profile_mode(perfil.mode, profile=perfil) == "aplicado"

    # O VPAD OBEDECE AO PERFIL — isto não mudou, e é o que o jogo vê.
    assert daemon._gamepad_device is not None
    assert daemon._gamepad_device.flavor == "dualsense"
    # E O PADRÃO DA MÁQUINA NÃO SE MEXE: só o gesto dela o escreve.
    assert flag.read_text(encoding="utf-8").strip() == "xbox", (
        "o perfil de um jogo voltou a promover a máscara dele a padrão da "
        "máquina — é o contágio que tirou o giroscópio do PRAGMATA dela")


def test_o_boot_devolve_o_xbox_que_o_vazamento_deixou(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A outra metade: o arquivo dela JÁ está com o `xbox` do contágio.

    Fechar as portas conserta o amanhã; o disco dela continuaria com o valor
    que ninguém pediu. `_a_mascara_dela_sem_o_vazamento` o devolve ao default —
    UMA vez, e não a cada boot: quem devolve grava, e a volta seguinte lê
    `dualsense` e não faz nada.

    MORDIDA: faça a função devolver `lido` sem gravar. A segunda linha reprova
    e o `xbox` fica no disco para sempre.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import (
        _a_mascara_dela_sem_o_vazamento,
    )

    save_gamepad_emulation(True, "xbox")

    assert _a_mascara_dela_sem_o_vazamento("xbox") == "dualsense"
    assert flag.read_text(encoding="utf-8").strip() == "dualsense"
    # E O QUE ELA ESCOLHEU DE PROPÓSITO FICA: `dualsense` no arquivo não é
    # vazamento, e a função não tem o que consertar.
    assert _a_mascara_dela_sem_o_vazamento("dualsense") == "dualsense"


def test_perfil_sem_opiniao_de_mascara_nao_escreve_nada(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`gamepad_flavor: null` é ausência de pedido (E1 da ESCOLHA-DELA-VENCE-01).

    Um perfil que só diz `kind: gamepad` mantém a máscara vigente. Deixar isso
    virar escrita em disco faria a máscara vigente ser recarimbada por qualquer
    perfil que passasse — e a origem dela se perderia.
    """
    save_gamepad_emulation(True, "xbox")
    _vpad_obedece(daemon, monkeypatch)

    perfil = _perfil_de_jogo(None)
    daemon.apply_profile_mode(perfil.mode, profile=perfil)

    assert flag.read_text(encoding="utf-8").strip() == "xbox"


def test_sem_opiniao_e_sem_vpad_de_pe_nao_carimba_o_default(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso que faz a guarda de `flavor` vazio valer a linha que ocupa.

    Sem vpad de pé E sem opinião de máscara, "a máscara viva" e "a pedida" são
    ambas `None` — a comparação de efeito, sozinha, deixaria passar. E o que
    passaria é o pior: `save_gamepad_emulation(True, None)` grava o DEFAULT do
    escritor (`dualsense`), ou seja, a escolha dela viraria outra coisa porque
    um vpad não subiu.

    Alcançável de verdade: com o gamepad desligado, `apply_profile_mode` chama
    o pedido mesmo sem flavor (`not gamepad_on`), e a factory pode falhar.
    """
    save_gamepad_emulation(True, "xbox")
    daemon.config.gamepad_emulation_enabled = False
    daemon._gamepad_device = None
    _vpad_desobedece(daemon, monkeypatch, desfecho="falhou")

    perfil = _perfil_de_jogo(None)
    daemon.apply_profile_mode(perfil.mode, profile=perfil)

    assert daemon._gamepad_device is None
    assert flag.read_text(encoding="utf-8").strip() == "xbox"


def test_o_desligado_de_proposito_dela_nao_e_ressuscitado(
    daemon: Daemon, tmp_path: Path, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metade da R-07 que NÃO mudou: o eixo do LIGA/DESLIGA.

    Com o opt-out gravado (AUTO-01.1), perfil nenhum pode criar o flag — criar
    o flag é ligar o vpad no próximo boot, decisão que é só dela. A máscara não
    tem onde morar aqui, e é o preço certo: sem vpad não há máscara.
    """
    save_gamepad_emulation(False)
    assert (tmp_path / _GAMEPAD_DISABLED_FLAG_FILE).exists()
    _vpad_obedece(daemon, monkeypatch)

    perfil = _perfil_de_jogo("dualsense")
    daemon.apply_profile_mode(perfil.mode, profile=perfil)

    assert not flag.exists(), (
        "um perfil ressuscitou o vpad que ela desligou de propósito"
    )
    assert (tmp_path / _GAMEPAD_DISABLED_FLAG_FILE).exists()


@pytest.mark.parametrize("desfecho", ["falhou", "recusado_steam_input"])
def test_so_grava_o_que_o_vpad_vestiu_de_verdade(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch, desfecho: str
) -> None:
    """ELO-MUDO-01: a gravação responde pelo EFEITO, não pelo transporte.

    `falhou` e `recusado_steam_input` não são `bloqueado_por_jogo`, então o
    chamador os trata como "não adiado" e segue. Se a guarda olhasse só isso, o
    disco passaria a jurar `dualsense` num daemon que nunca conseguiu vestir a
    máscara — e o próximo boot nasceria mentindo.
    """
    save_gamepad_emulation(True, "xbox")
    daemon.config.gamepad_emulation_enabled = True
    daemon._gamepad_device = _Vpad("xbox")
    _vpad_desobedece(daemon, monkeypatch, desfecho=desfecho)

    perfil = _perfil_de_jogo("dualsense")
    daemon.apply_profile_mode(perfil.mode, profile=perfil)

    assert flag.read_text(encoding="utf-8").strip() == "xbox"


def test_mascara_adiada_por_jogo_aberto_nao_chega_ao_disco(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O gate R-04 recusou: nada mudou, nem na mão dela nem no disco.

    Recriar vpad com jogo aberto arranca o controle da mão dela, e por isso o
    gate existe. Persistir a máscara não pode virar um jeito enviesado de a
    troca acontecer mesmo assim — nem no boot seguinte, sem ela pedir.
    """
    save_gamepad_emulation(True, "xbox")
    daemon.config.gamepad_emulation_enabled = True
    daemon._gamepad_device = _Vpad("xbox")
    # `display_authority` é propriedade só-leitura (NUMA-01): quem a produz é o
    # `GameSignal`. O dublê entra por ali, e não por um setter que não existe.
    daemon._game_signal = type("Sinal", (), {"authority": "game"})()
    _vpad_desobedece(daemon, monkeypatch, desfecho=EMU_BLOQUEADO_POR_JOGO)

    perfil = _perfil_de_jogo("dualsense")
    assert (
        daemon.apply_profile_mode(perfil.mode, profile=perfil) == "adiado_jogo_aberto"
    )

    assert flag.read_text(encoding="utf-8").strip() == "xbox"
    assert daemon._gamepad_device.flavor == "xbox"


def test_a_mascara_do_perfil_atravessa_o_modo_nativo(
    daemon: Daemon, flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O segundo revertedor: o stash do Modo Nativo lia a máscara do DISCO.

    O par ligado/máscara vinha inteiro de `load_gamepad_emulation`, e o disco só
    conhece o gesto manual. Com o flag em `xbox` e o vpad vivo em `dualsense`, a
    volta do Modo Nativo devolvia `xbox` — a máscara do perfil morria numa
    transição que ela nem pediu.

    O teste ARRANCA a persistência de propósito (o flag continua `xbox`) para
    que a segunda cura seja medida sozinha: as duas são independentes.
    """
    save_gamepad_emulation(True, "xbox")
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.gamepad_flavor = "dualsense"
    daemon._gamepad_device = _Vpad("dualsense")

    monkeypatch.setattr(daemon, "_release_controller_to_game", lambda: None)
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    monkeypatch.setattr(daemon, "_zero_rumble_motors", lambda: None)
    monkeypatch.setattr(session_mod, "save_native_mode", lambda *a, **k: None)

    daemon.set_native_mode(True, origin="profile")
    assert daemon._native_emu_stash["gamepad"] == [True, "dualsense"], (
        "o stash guardou a máscara do disco, não a que o jogo estava vendo"
    )

    pedidos: list[tuple[bool, str | None]] = []

    def _voltou(
        enabled: bool, flavor: str | None = None, *, origin: str = "manual"
    ) -> bool:
        pedidos.append((enabled, flavor))
        return enabled

    monkeypatch.setattr(daemon, "set_gamepad_emulation", _voltou)
    daemon.set_native_mode(False, reapply=False, restore_stash=True, origin="profile")

    assert pedidos == [(True, "dualsense")], (
        "sair do Modo Nativo devolveu a máscara do último gesto manual por cima "
        "da máscara do perfil"
    )
