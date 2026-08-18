"""ESCONDER-EM-VEZ-DE-SAIR-01 — a marca esconde o FÍSICO e deixa o co-op vivo.

Decisão dela, 09/08/2026, no desenho
`docs/process/sprints/2026-08-09-ESCONDER-EM-VEZ-DE-SAIR-01-o-duplicado-cura-pelo-outro-lado.md`:

    "a allowlist do Steam Input NÃO tira o Hefesto da frente."

O DEFEITO, MEDIDO
=================
Marcar um jogo fazia o daemon soltar o grab do físico, mandar o broker
`restore_all` e **suspender os gamepads virtuais**. Curava o controle dobrado
com UM controle na mesa — e derrubava o jogador 2 junto, porque **o jogador 2 é
um gamepad virtual**. No journal dela, em 08/08:
`coop_derrubado_pela_excecao_steam_input`, vinte ocorrências.

OS DOIS LADOS QUE ESTE ARQUIVO TRAVA
====================================
1. **o co-op sobrevive**: com o jogo marcado e DOIS controles na mesa, os vpads
   continuam de pé e ninguém é derrubado;
2. **o físico fica escondido enquanto o jogo marcado está na frente**, e volta
   ao estado canônico quando ele sai.

A MORDIDA de cada um está escrita no docstring do teste: qual linha arrancar
para vê-lo reprovar. Foram arrancadas de verdade antes desta leva entrar.

O QUE ESTE ARQUIVO NÃO PROVA, DE PROPÓSITO
==========================================
Que o JOGO lista dois jogadores. Isso é medição dela no aparelho (§6 do
desenho) — aqui se prova o que o produto faz, que é manter os dois vpads de pé
e o físico escondido. Prometer o resto seria inventar.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon import launch_env as le

#: Mullet Mad Jack — um dos dois appids que entraram na lista dela com
#: duplicado real medido. O outro é o 3357650 (Pragmata).
MMJ = 2111190

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"


class _VpadFalso:
    def __init__(self, flavor: str = "dualsense", backend: str = "uhid") -> None:
        self.flavor = flavor
        self.backend = backend
        self._started = True
        self.parado = False

    def stop(self) -> None:
        self.parado = True
        self._started = False


class _CoopFalso:
    """Co-op com N secundários de pé, contando quem manda derrubá-los."""

    def __init__(self, jogadores: int) -> None:
        self._players: dict[str, Any] = {
            f"AA:BB:CC:00:00:0{i}": SimpleNamespace(
                vpad=_VpadFalso(), player_index=i + 2
            )
            for i in range(jogadores)
        }
        self.desligado = 0

    def disable(self) -> None:
        self.desligado += 1
        self._players.clear()

    def sync(self, *, force: bool = False) -> None:
        return None


class _DaemonFalso:
    """O mínimo que a borda da exceção toca — grab, broker, vpad e co-op."""

    def __init__(self, *, jogadores: int = 0, nativo: bool = False) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = _VpadFalso()
        self._coop_manager = _CoopFalso(jogadores)
        self._tasks: list[Any] = []
        self._nativo = nativo
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self.store = SimpleNamespace(
            window_detect_current_class=None, bump=lambda chave: None
        )
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        # `hidraw_path(identity)` devolve um nó por controle: o primário sem
        # argumento, cada secundário pelo MAC. Sem isso o teste do co-op não
        # distinguiria "escondi o físico do P1" de "escondi os dois".
        def _hidraw(identity: str | None = None) -> str:
            if identity is None:
                return "/dev/hidraw0"
            return f"/dev/hidraw{1 + int(identity[-1])}"

        self.controller = SimpleNamespace(
            _evdev=_Evdev(),
            hidraw_path=_hidraw,
            set_rumble=lambda **k: None,
            primary_uniq="AA:BB:CC:00:00:FF",
        )

    def is_native_mode(self) -> bool:
        return self._nativo

    def _is_stopping(self) -> bool:
        return False


@pytest.fixture()
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cliente do broker dublado — nenhum socket real, nenhum chmod real."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(bc, "broker_call_nonblocking", lambda daemon, fn: fn())


@pytest.fixture()
def _sem_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A borda regrava a `.env` do wrapper; aqui isso não pode tocar o disco."""
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)


@pytest.fixture()
def _jogo_marcado_na_frente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: MMJ)


async def _encerrar_vigia(daemon: Any) -> Any:
    """Cancela a task-vigia (se nasceu) e a DEVOLVE para inspeção.

    Nestes testes o que interessa é justamente ela NÃO ter nascido — mas
    cancelar mesmo assim é obrigatório: uma task viva num teste que passa vaza
    para o próximo, e o defeito aparece longe daqui.
    """
    vigia = getattr(daemon, "_steam_input_vigia", None)
    if vigia is not None:
        vigia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vigia
    return vigia


# ---------------------------------------------------------------------------
# LADO 1 — o co-op não é derrubado
# ---------------------------------------------------------------------------


async def test_com_dois_controles_a_marca_nao_derruba_o_jogador_2(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """A MORDIDA: devolva `suspend_vpads_for_steam_input(daemon, appid=appid)`
    à borda de entrada de `sync_steam_input_exception` e este teste reprova em
    cinco asserções de uma vez — era exatamente o estado que produzia
    `coop_derrubado_pela_excecao_steam_input` vinte vezes num dia.

    ASSÍNCRONO por obrigação, e a razão é uma armadilha medida: a suspensão
    antiga ABORTAVA sozinha sem event loop rodando
    (`steam_input_vigia_sem_event_loop` — não se suspende sem quem devolva).
    Escrito de forma síncrona, este teste passaria COM a cura arrancada, que é
    a definição de teste que não morde. Com o loop de pé, a borda antiga
    suspende de verdade e as linhas abaixo caem juntas.
    """
    daemon = _DaemonFalso(jogadores=1)  # ela + o jogador 2
    vpad_do_p1 = daemon._gamepad_device

    assert gp.sync_steam_input_exception(daemon) is True
    vigia = await _encerrar_vigia(daemon)

    assert daemon._gamepad_device is vpad_do_p1, "o vpad do P1 tem de ficar de pé"
    assert vpad_do_p1.parado is False
    assert daemon._coop_manager.desligado == 0, (
        "o co-op foi desligado — é este teardown que derrubava o jogador 2"
    )
    assert len(daemon._coop_manager._players) == 1, "o jogador 2 saiu da mesa"
    assert gp.steam_input_vpad_suspenso(daemon) is False
    assert gp.steam_input_coop_derrubados(daemon) == 0
    assert vigia is None, (
        "nasceu a task-vigia da suspensão — ela só existe para desfazer uma "
        "suspensão, e a marca não suspende mais nada"
    )


async def test_a_marca_nao_arma_vigia_porque_nao_ha_o_que_devolver(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """Sem suspensão não nasce task-vigia — e isso é a prova de que a borda
    deixou de ser destrutiva. A vigia existia SÓ para desfazer a suspensão
    (`_armar_vigia_da_excecao`: não se suspende sem quem devolva).

    A MORDIDA é a mesma do teste acima, pelo outro lado: com a borda antiga e o
    loop de pé, a vigia NASCE e ainda se pendura em `daemon._tasks`.
    """
    daemon = _DaemonFalso(jogadores=1)

    assert gp.sync_steam_input_exception(daemon) is True
    vigia = await _encerrar_vigia(daemon)

    assert vigia is None
    assert daemon._tasks == [], "a marca pendurou task no daemon dela"
    assert daemon._gamepad_device is not None


def test_o_perfil_do_jogo_marcado_volta_a_poder_criar_o_vpad(
    _broker_falso: None, _sem_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: devolva `if origin != "manual": return False` ao gate de
    `start_gamepad_emulation` e o autoswitch volta a ser recusado no jogo
    marcado — que é o dispositivo que a marca agora PROMETE entregar.
    """
    import hefesto_dualsense4unix.integrations.virtual_pad as vp

    monkeypatch.setattr(vp, "make_virtual_pad", lambda key, **kw: _VpadFalso(flavor=key))
    monkeypatch.setattr(gp, "start_motion_reader", lambda daemon, device: None)
    daemon = _DaemonFalso()
    daemon._gamepad_device = None
    daemon._steam_input_excecao = True

    assert gp.start_gamepad_emulation(daemon, "dualsense", origin="profile") is True
    assert daemon._gamepad_device is not None


def test_a_rede_de_seguranca_do_vpad_vale_dentro_do_jogo_marcado(
    _broker_falso: None, _sem_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VPAD-09 dispara na reconexão BT — o evento mais frequente desta máquina.

    Com o físico escondido, um vpad morto e não ressuscitado é ZERO controles
    na mão dela. A MORDIDA: devolva o `if steam_input_excecao_ativa(daemon):
    return False` a `upgrade_primary_vpad_to_uhid`.
    """
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda d: True)
    monkeypatch.setattr(gp, "start_gamepad_emulation", lambda *a, **k: True)
    daemon = _DaemonFalso()
    daemon._gamepad_device = None
    daemon._steam_input_excecao = True

    assert gp.upgrade_primary_vpad_to_uhid(daemon) is True


# ---------------------------------------------------------------------------
# LADO 2 — o físico fica escondido enquanto o jogo marcado está na frente
# ---------------------------------------------------------------------------


def test_entrar_no_jogo_marcado_esconde_o_fisico_em_vez_de_expor(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """A MORDIDA: troque a chamada de `esconder_o_fisico_para_o_jogo` pelo par
    antigo (`_set_evdev_grab(daemon, False)` + `client.restore_all`) e as três
    asserções abaixo caem juntas. É a inversão inteira, numa linha.
    """
    daemon = _DaemonFalso()

    assert gp.sync_steam_input_exception(daemon) is True

    assert daemon.grabs == [True], "soltar o grab é o jogo vendo o físico de novo"
    assert daemon.hides == ["/dev/hidraw0"], "o hidraw do físico tem de sumir"
    assert daemon.restores == 0, "`restore_all` é a direção contrária da decisão dela"


def test_com_dois_controles_esconde_os_dois_fisicos(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """Um vpad vivo por controle ⇒ um hidraw escondido por controle.

    É a metade que faz o co-op funcionar no jogo marcado: o jogador 2 vê o vpad
    dele e não vê o aparelho dele.
    """
    daemon = _DaemonFalso(jogadores=1)

    gp.sync_steam_input_exception(daemon)

    assert daemon.hides == ["/dev/hidraw0", "/dev/hidraw1"]


def test_a_reconciliacao_online_reesconde_no_meio_da_partida(
    _broker_falso: None, _sem_env: None
) -> None:
    """A MORDIDA: devolva o `if steam_input_excecao_ativa(daemon): return` a
    `rehide_physical_hidraw`.

    O nó recriado por replug/wake BT NASCE VISÍVEL (BROKER-01 §2.2). Com o gate
    antigo, o físico voltava a aparecer no meio da partida do jogo marcado e
    nada o escondia de novo até o jogo fechar.
    """
    daemon = _DaemonFalso()
    daemon._steam_input_excecao = True

    gp.rehide_physical_hidraw(daemon)

    assert daemon.hides == ["/dev/hidraw0"]


def test_sair_do_jogo_marcado_mantem_o_estado_canonico(
    _broker_falso: None, _sem_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reversibilidade: a saída não pode deixar nada pendurado nem estragado.

    Nada foi suspenso na entrada, então a saída é idempotente — grab de pé e
    físico escondido, que é o estado de qualquer outro jogo.
    """
    daemon = _DaemonFalso()
    daemon._steam_input_excecao = True
    monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: None)

    assert gp.sync_steam_input_exception(daemon) is False

    assert gp.steam_input_excecao_ativa(daemon) is False
    assert gp.steam_input_vpad_suspenso(daemon) is False
    assert daemon.grabs == [True] and daemon.hides == ["/dev/hidraw0"]
    assert daemon._gamepad_device is not None


# ---------------------------------------------------------------------------
# O invariante que a inversão NÃO pode atropelar: duplicado > zero controles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("preparar", "motivo"),
    [
        (lambda d: setattr(d, "_nativo", True), "modo_nativo"),
        (
            lambda d: setattr(d.config, "gamepad_emulation_enabled", False),
            "emulacao_desligada",
        ),
        (lambda d: setattr(d, "_gamepad_device", None), "sem_vpad_vivo"),
    ],
)
def test_sem_vpad_para_devolver_o_controle_a_marca_nao_esconde_nada(
    preparar: Any,
    motivo: str,
    _broker_falso: None,
    _sem_env: None,
    _jogo_marcado_na_frente: None,
) -> None:
    """Esconder o físico sem um virtual vivo é ZERO controles na mão dela.

    A MORDIDA: apague qualquer um dos três gates de `esconder_o_fisico_para_o_
    jogo` e a linha correspondente reprova. O invariante é o mais velho desta
    casa e não é dispensável por opt-in — uma caixinha marcada semanas atrás não
    pode deixá-la sem controle nenhum hoje.
    """
    daemon = _DaemonFalso()
    preparar(daemon)

    gp.sync_steam_input_exception(daemon)

    assert daemon.hides == []
    assert daemon.grabs == []


def test_o_vpad_morto_nao_autoriza_esconder(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """VIDA do vpad, não existência (lição 6/#17): um uhid derrubado por
    UHID_STOP mantém o objeto Python de pé e não devolve controle nenhum."""
    daemon = _DaemonFalso()
    daemon._gamepad_device._started = False

    gp.sync_steam_input_exception(daemon)

    assert daemon.hides == []


# ---------------------------------------------------------------------------
# A OUTRA METADE — a env que o jogo lê na abertura
# ---------------------------------------------------------------------------


def test_o_jogo_marcado_recebe_a_mesma_env_de_qualquer_outro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: devolva o laço da allowlist a `materialize_launch_env`.

    A env do appid marcado omitia `SDL_GAMECONTROLLER_IGNORE_DEVICES` — em
    português, *"jogo, olhe para o controle físico"*. Com o daemon escondendo o
    físico, essa env produz um controle enumerado que não responde a nada: o
    "Jogador 3" fantasma que ela viu no Sackboy em 08/08.
    """
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
    monkeypatch.setattr(le, "_fisicos_na_mesa", lambda daemon: 1)

    le.materialize_launch_env(_DaemonFalso())

    assert not (tmp_path / f"steam_app_{MMJ}.env").exists(), (
        "o jogo marcado ganhou env própria de novo — a marca não é mais um "
        "desvio do lançamento"
    )
    assert _IGNORE in (tmp_path / "default.env").read_text(encoding="utf-8")


def test_a_env_velha_do_appid_marcado_e_apagada_sozinha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nada à mão (regra de 08/08): o arquivo sem dedup que as versões antigas
    gravaram na máquina dela some na primeira materialização, sem passo dela."""
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
    velho = tmp_path / f"steam_app_{MMJ}.env"
    velho.write_text(
        f"# estado: {le.ESTADO_ALLOWLIST_STEAM_INPUT}\n__GL_SHADER_DISK_CACHE=1\n",
        encoding="utf-8",
    )

    le.materialize_launch_env(_DaemonFalso())

    assert not velho.exists()


# ---------------------------------------------------------------------------
# LADO 3 — a JANELA não pode seguir contando a história velha
# ---------------------------------------------------------------------------
#
# A regra dela, de 09/08: *"tudo tem que focar em funcionar na interface do app
# e no install"*. A caixinha é o gesto pelo qual esta cura chega a ela; se o
# texto continuar prometendo o comportamento antigo, a cura não foi entregue —
# foi escondida no daemon. Os dois lugares da janela que falam da marca são a
# caixinha do editor de perfil e o botão "Este jogo não funciona" da aba
# Sistema, e eles marcam a MESMA coisa: têm de dizer a mesma coisa.

#: O que a janela dizia até 08/08 e não pode voltar a dizer. Cada trecho era
#: verdadeiro quando a marca tirava o Hefesto da frente, e hoje é o contrário do
#: que o produto faz.
_FRASES_QUE_MORRERAM = (
    "deixar a steam entregar",
    "entregue pela steam",
    "o jogo passa a ver o controle de verdade",
    "quem manda na luz e nos gatilhos passa a ser o jogo",
)


def _textos_do_objeto(alvo: str) -> str:
    """Rótulo + tooltip + nome/descrição de acessibilidade, num texto só.

    Ler os quatro juntos é de propósito: o defeito que esta trava cobre é a
    janela dizer duas coisas diferentes sobre o mesmo clique, e o leitor de tela
    é a única voz da janela para quem não enxerga o rótulo.
    """
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    raiz = ET.parse(str(MAIN_GLADE)).getroot()
    achados = [o for o in raiz.iter("object") if o.get("id") == alvo]
    assert achados, f"o objeto {alvo!r} sumiu do glade"
    return " ".join(
        (prop.text or "")
        for obj in achados[0].iter("object")
        for prop in obj.findall("property")
        if prop.get("name")
        in (
            "label",
            "tooltip-text",
            "AtkObject::accessible-name",
            "AtkObject::accessible-description",
        )
    )


@pytest.mark.parametrize(
    "alvo", ["profile_steam_input_check", "btn_steam_game_broken"]
)
def test_a_janela_nao_promete_mais_que_o_hefesto_sai_da_frente(alvo: str) -> None:
    """A MORDIDA: devolva qualquer uma das frases de `_FRASES_QUE_MORRERAM` ao
    glade e este teste reprova apontando a frase.

    Elas descreviam a IMPLEMENTAÇÃO antiga ("deixar a Steam entregar") e o
    preço que vinha com ela ("quem manda na luz e nos gatilhos passa a ser o
    jogo"). Com a inversão de 09/08 as duas coisas são falsas: quem entrega o
    controle ao jogo marcado é o Hefesto, e a luz e os gatilhos nunca saem da
    mão dela.
    """
    textos = _textos_do_objeto(alvo).lower()

    for morta in _FRASES_QUE_MORRERAM:
        assert morta not in textos, (
            f"{alvo}: a janela voltou a dizer {morta!r}, que descreve o produto "
            "de antes de 09/08 — a tela promete o contrário do que o daemon faz."
        )


@pytest.mark.parametrize(
    "alvo", ["profile_steam_input_check", "btn_steam_game_broken"]
)
def test_a_janela_diz_o_efeito_e_manda_relancar(alvo: str) -> None:
    """O texto tem de dizer o EFEITO (esconder o físico), o que ela NÃO perde e
    que a marca só vale inteira no próximo lançamento.

    O léxico é decisão dela (a memória de como propor interface): o nome novo
    deriva do que já existia — *"o controle dobrado"* — e descreve o que
    acontece, não como está implementado.
    """
    textos = _textos_do_objeto(alvo).lower()

    assert "esconde" in textos or "escondido" in textos, (
        f"{alvo}: a janela não diz que o controle físico fica escondido, que é "
        "o que a marca passou a fazer"
    )
    assert "dobrado" in textos, (
        f"{alvo}: sumiu o nome do defeito na palavra dela — é por 'dobrado' que "
        "ela reconhece o problema que veio resolver"
    )
    assert "hefesto" in textos, (
        f"{alvo}: a janela não diz de quem passa a ser o controle que o jogo vê"
    )
    assert "feche e abra o jogo" in textos, (
        f"{alvo}: sumiu a instrução sem a qual a marca não vale inteira — a env "
        "do dedup é lida UMA vez, na abertura do jogo"
    )


def test_a_caixinha_e_o_botao_contam_a_mesma_historia() -> None:
    """Duas telas, o mesmo clique: o que uma promete a outra não pode negar.

    A caixinha (aba Perfis) e o botão "Este jogo não funciona" (aba Sistema)
    escrevem no MESMO `steam_input_apps.txt`. Enquanto a caixinha dizia
    "esconder" e o botão dizia "a Steam entrega", a janela dava duas respostas
    para a mesma pergunta — e ela decide vendo a tela.
    """
    caixinha = _textos_do_objeto("profile_steam_input_check").lower()
    botao = _textos_do_objeto("btn_steam_game_broken").lower()

    for fato in ("dobrado", "hefesto", "vibração", "feche e abra o jogo"):
        assert fato in caixinha and fato in botao, (
            f"{fato!r} está numa das duas telas e não na outra — o mesmo clique "
            "está sendo descrito de dois jeitos."
        )
