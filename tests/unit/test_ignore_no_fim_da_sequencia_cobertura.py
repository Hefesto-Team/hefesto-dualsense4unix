"""IGNORE-NO-FIM-DA-SEQUENCIA-01 (12/08/2026) — a decisão do IGNORE espera a mesa.

O defeito, medido no journal dela com quatro DualSense e o Sackboy aberto: o
produto decidia o `SDL_GAMECONTROLLER_IGNORE_DEVICES` **durante** a subida dos
gamepads virtuais, uma vez por borda, e nada reavaliava a decisão quando a
subida terminava.

    00:15:31.430  vpad P1 sobe
    00:15:31.432  launch_env_ignore_omitido_sem_cobertura  fisicos=4 vpads=1
    00:15:32.047  coop_player_grab_pending  x3   <- registrados, SEM vpad
    ...           dez segundos com fisicos=4 e vpads=1, e nada reavaliando
    00:15:42.218  vpad P2   -> ignore omitido de novo
    00:15:42.313  vpad P3   -> omitido
    00:15:42.401  vpad P4   -> só AGORA a cobertura fica completa

É o terceiro defeito de TEMPO do mesmo dia, e os três têm a mesma forma: o
produto decide durante a sequência em vez de esperar ela sossegar. A cura
desenhada por ela é sempre a mesma — **armar a cada evento, disparar quando
sossega, agir sobre tudo**.

Estes testes cobrem os três estados que a sprint exige, e cada um MORDE numa
linha diferente do produto:

1. **cobertura incompleta durante a subida** — o arquivo POR APPID, que é o que
   um jogo com perfil realmente lê (o caso dela: `steam_app_1599660.env`), tem
   de obedecer à mesma cobertura por físico que o `default.env`. Mordida:
   `_env_for_profile` sem o `fisicos` (como estava até 12/08);
2. **cobertura completa no fim** — nada disso pode virar "o dedup parou de
   funcionar" com a mesa inteira de pé;
3. **a rematerialização no sossego** — a mesa muda SEM borda que materialize
   (o `coop_player_grab_pending` do journal: mais um físico, nenhum vpad novo),
   e é o vigia que reabre a conta. Mordida: `vigiar_a_mesa` /
   `rematerializar_se_sossegou` arrancados de `_reconciliar_launch`.

E o que estes testes NÃO podem prometer, porque o produto não entrega: o jogo lê
estas variáveis UMA vez, no `exec env "$@"` do wrapper. Regravar o arquivo não
alcança processo que já subiu. `TestOAvisoHonesto` existe para que essa metade
seja dita em voz alta no journal em vez de ficar escondida atrás de uma
regravação bem-sucedida.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
DISABLE = "PROTON_DISABLE_HIDRAW"

#: O appid do Sackboy, que é o jogo do ensaio `coop-ignore-avaliado-cedo`.
APPID_SACKBOY = 1599660


# --- instrumentos ------------------------------------------------------------


class _LoggerEspiao:
    """Registra `(evento, campos)` de cada chamada — sem tocar no structlog real."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def _grava(self, evento: str, **campos: Any) -> None:
        self.eventos.append((evento, campos))

    info = warning = debug = _grava

    def chaves(self) -> list[str]:
        return [nome for nome, _ in self.eventos]

    def campos(self, evento: str) -> dict[str, Any]:
        for nome, campos in self.eventos:
            if nome == evento:
                return campos
        raise AssertionError(f"{evento} não foi registrado: {self.chaves()}")


def _daemon(*, vpads: int, fisicos: int, flavor: str = "dualsense") -> Any:
    """Daemon dublê com N vpads uhid vivos e M DualSense físicos na mesa.

    `vpads` conta o P1 junto (é como o `_snapshot` conta): `vpads=1` é só o
    primário; `vpads=4` é o primário mais três jogadores de co-op promovidos.
    """
    players = {
        f"mac{i}": SimpleNamespace(vpad=SimpleNamespace(backend="uhid"))
        for i in range(2, vpads + 1)
    }
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor=flavor),
        _gamepad_device=SimpleNamespace(backend="uhid") if vpads >= 1 else None,
        _coop_manager=SimpleNamespace(_players=players),
        controller=SimpleNamespace(
            describe_controllers=lambda: [{"connected": True}] * fisicos
        ),
    )


def _perfil_do_jogo(flavor: str = "dualsense") -> Any:
    """Perfil com máscara igual à vigente — o ramo dos backends REAIS."""
    return SimpleNamespace(
        name="Sackboy",
        mode=SimpleNamespace(kind="gamepad", gamepad_flavor=flavor),
        match=SimpleNamespace(
            window_class=[f"steam_app_{APPID_SACKBOY}"],
            window_title_regex=None,
            process_name=[],
        ),
    )


def _env_do_arquivo(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        out[chave] = valor
    return out


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`launch_env/` hermético e o perfil do Sackboy no lugar do disco dela."""
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [_perfil_do_jogo()])
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    return tmp_path


# --- 1. cobertura incompleta DURANTE a subida --------------------------------


class TestCoberturaIncompletaDuranteASubida:
    """O instante 00:15:42.219 do journal: `fisicos=4 vpads=2`."""

    def test_o_arquivo_por_appid_obedece_a_cobertura(self, mesa: Path) -> None:
        """A MORDIDA. Tire o `fisicos=fisicos` do `_env_for_profile` e reprova.

        Até 12/08 o `materialize_launch_env` chamava `_env_for_profile` sem o
        número de físicos. O default 0 significa "NÃO SEI", e "não sei" AUTORIZA
        o IGNORE — logo o `steam_app_1599660.env`, o arquivo que o jogo COM
        perfil de fato lê, saía escondendo os quatro DualSense numa mesa com
        dois vpads vivos. Dois jogadores dela ficariam com zero controle, que é
        exatamente o desfecho que a doutrina desta casa proíbe por escrito.

        O `default.env` do MESMO instante já omitia (é o
        `launch_env_ignore_omitido_sem_cobertura` do journal) — o defeito era a
        divergência entre os dois arquivos.
        """
        le.materialize_launch_env(_daemon(vpads=2, fisicos=4))

        por_appid = _env_do_arquivo(mesa / f"steam_app_{APPID_SACKBOY}.env")
        default = _env_do_arquivo(mesa / "default.env")
        assert IGNORE not in por_appid, (
            "o arquivo por appid escondeu 4 DualSense com 2 vpads vivos"
        )
        assert IGNORE not in default
        # O DISABLE continua saindo: ele impede o winebus de entregar o hidraw
        # do físico e não esconde nada do SDL (GUERRA-01, defeito já pago).
        assert DISABLE in por_appid

    def test_o_prognostico_de_outra_mascara_segue_intacto(self, mesa: Path) -> None:
        """R-05 não pode ser reaberto pela cura.

        Quando o perfil pede máscara DIFERENTE da vigente, a lista de backends é
        um símbolo de TIPO (`["uhid"]`), não um censo de vpads. Exigir cobertura
        contra ela diria "sem cobertura" sobre uma mesa que ainda nem existe, e
        o arquivo por appid voltaria a ficar PIOR que o `default.env` — o
        defeito que o prognóstico foi escrito para curar.
        """
        env, motivo = le._env_for_profile(
            _perfil_do_jogo("dualsense"),
            flavor_atual="xbox",
            backends=["uinput"],
            permite_uhid=True,
            fisicos=4,
        )
        assert "prognóstico" in motivo
        assert IGNORE in env


# --- 2. cobertura completa no FIM --------------------------------------------


class TestCoberturaCompletaNoFim:
    """00:15:42.401: o quarto vpad sobe e a mesa fecha."""

    def test_os_dois_arquivos_escondem_o_fisico(self, mesa: Path) -> None:
        le.materialize_launch_env(_daemon(vpads=4, fisicos=4))

        for nome in ("default.env", f"steam_app_{APPID_SACKBOY}.env"):
            env = _env_do_arquivo(mesa / nome)
            assert IGNORE in env, nome
            assert DISABLE in env, nome

    def test_a_conta_da_cobertura_e_uma_so(self) -> None:
        """`cobertura_total` é a função que o `compose_env` e o vigia leem.

        Duas cópias da mesma conta é como esta casa reintroduz defeito pago.
        """
        assert le.cobertura_total(backends=["uhid"] * 4, fisicos=4) is True
        assert le.cobertura_total(backends=["uhid"], fisicos=4) is False
        # "NÃO SEI" (backend sem `describe_controllers`) é permissivo por
        # decisão de 03/08 — apertar sem informação é regressão, não cura.
        assert le.cobertura_total(backends=["uhid"], fisicos=0) is True


# --- 3. a rematerialização quando a mesa sossega -----------------------------


class TestRematerializacaoNoSossego:
    """A mesa muda SEM borda que materialize — e alguém tem de reabrir a conta."""

    def test_mais_um_fisico_sem_vpad_novo_derruba_o_ignore(
        self, mesa: Path
    ) -> None:
        """A MORDIDA. Arranque `vigiar_a_mesa`/`rematerializar_se_sossegou` e reprova.

        A sequência é a do journal, com os números reduzidos: três controles com
        três vpads (cobertura completa, IGNORE gravado), e então um quarto
        DualSense chega. O `_spawn_player` registra o jogador com o grab
        PENDENTE — nenhum vpad nasce, nada materializa —, e a mesa fica com
        quatro físicos escondidos por um arquivo que só devolve três.

        Sem o vigia esse desequilíbrio dura até a próxima borda de vpad, que
        pode não vir nunca (foi o que durou dez segundos em 12/08).
        """
        daemon = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(daemon)
        assert IGNORE in _env_do_arquivo(mesa / "default.env")

        # O quarto controle chega; nenhuma borda de vpad acontece.
        daemon.controller.describe_controllers = lambda: [{"connected": True}] * 4
        assert IGNORE in _env_do_arquivo(mesa / "default.env"), (
            "pré-condição: o arquivo ainda afirma a cobertura antiga"
        )

        le.vigiar_a_mesa(daemon, agora=100.0)
        assert daemon._launch_env_sossego_em == 100.0 + le.JANELA_DE_SOSSEGO_SEC

        regravou = le.rematerializar_se_sossegou(
            daemon, agora=100.0 + le.JANELA_DE_SOSSEGO_SEC
        )
        assert regravou is True
        assert IGNORE not in _env_do_arquivo(mesa / "default.env"), (
            "quatro físicos escondidos com três vpads = uma pessoa sem controle"
        )
        assert IGNORE not in _env_do_arquivo(mesa / f"steam_app_{APPID_SACKBOY}.env")

    def test_o_disparo_espera_o_ultimo_evento_da_rajada(self, mesa: Path) -> None:
        """"Agir sobre TUDO": rearmar empurra o vencimento para a frente.

        A rajada medida de P2→P3→P4 durou 183 ms. Decidir no primeiro evento
        dela é o defeito inteiro; o relógio tem de andar a cada evento e vencer
        depois do último.
        """
        daemon = _daemon(vpads=1, fisicos=4)
        janela = le.JANELA_DE_SOSSEGO_SEC

        le.armar_rematerializacao(daemon, motivo="P2", agora=0.0)
        le.armar_rematerializacao(daemon, motivo="P3", agora=0.1)
        le.armar_rematerializacao(daemon, motivo="P4", agora=0.2)

        assert le.rematerializar_se_sossegou(daemon, agora=janela) is False, (
            "venceu contando do PRIMEIRO evento — a rajada não sossegou ainda"
        )
        assert le.rematerializar_se_sossegou(daemon, agora=0.2 + janela) is True

    def test_mesa_parada_nao_regrava_nada(self, mesa: Path) -> None:
        """Sem mudança de assinatura, o vigia cala — senão é churn, não cura."""
        daemon = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(daemon)
        antes = (mesa / "default.env").read_text(encoding="utf-8")

        le.vigiar_a_mesa(daemon, agora=10.0)
        assert getattr(daemon, "_launch_env_sossego_em", None) is None, (
            "armou sem a mesa ter mudado"
        )

        le.armar_rematerializacao(daemon, motivo="borda qualquer", agora=10.0)
        regravou = le.rematerializar_se_sossegou(
            daemon, agora=10.0 + le.JANELA_DE_SOSSEGO_SEC
        )
        assert regravou is False
        assert (mesa / "default.env").read_text(encoding="utf-8") == antes

    def test_o_vigia_nao_empurra_o_proprio_vencimento(self, mesa: Path) -> None:
        """Rearmar a cada tique de 1 Hz faria o disparo nunca acontecer.

        O vigia só arma quando NÃO há relógio andando. Quem rearma numa rajada
        são as bordas de vpad, que é o lugar certo.
        """
        daemon = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(daemon)
        daemon.controller.describe_controllers = lambda: [{"connected": True}] * 4

        le.vigiar_a_mesa(daemon, agora=0.0)
        prazo = daemon._launch_env_sossego_em
        le.vigiar_a_mesa(daemon, agora=0.5)
        assert daemon._launch_env_sossego_em == prazo


# --- a fiação: a reconciliação de 1 Hz é quem consome o vencimento -----------


class TestFiacaoNaReconciliacaoDeUmHertz:
    def test_reconciliar_launch_regrava_quando_a_mesa_sossega(
        self, mesa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA da fiação: tire as duas chamadas de `_reconciliar_launch`.

        Sem elas nada consome o vencimento e o arquivo fica rançoso para sempre.
        """
        monkeypatch.setattr(le, "JANELA_DE_SOSSEGO_SEC", 0.0)
        daemon = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(daemon)
        daemon.controller.describe_controllers = lambda: [{"connected": True}] * 4

        gp._reconciliar_launch(daemon)  # tique 1: nota a mudança e ARMA
        daemon._launch_reconcile_next_at = 0.0  # solta o throttle de 1 Hz
        gp._reconciliar_launch(daemon)  # tique 2: sossegou -> regrava

        assert IGNORE not in _env_do_arquivo(mesa / "default.env")

    def test_borda_de_vpad_escreve_agora_e_arma_o_sossego(self, mesa: Path) -> None:
        """A borda continua escrevendo NA HORA — deixar o arquivo velho durante
        a subida faria um jogo lançado no meio dela ler outra sessão."""
        daemon = _daemon(vpads=1, fisicos=4)
        gp._materialize_launch_env(daemon)

        assert (mesa / "default.env").exists()
        assert daemon._launch_env_sossego_em is not None


class TestFiacaoNoCoop:
    def test_jogador_com_grab_pendente_arma_o_sossego(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`coop_player_grab_pending` é o ramo que não materializa NADA.

        E é o ramo em que a mesa fica desequilibrada: mais um físico, nenhum
        vpad novo. Sem armar aqui, ninguém reabre a conta.
        """
        from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

        class _ReaderPendente:
            def __init__(self, device_path: Any = None, target_uniq: Any = None) -> None:
                self.grab_state = "off"

            def start(self) -> bool:
                return True

            def set_grab(self, grab: bool) -> bool:
                self.grab_state = "pending"
                return True

            def stop(self) -> None:
                return None

        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _ReaderPendente
        )
        daemon = _daemon(vpads=1, fisicos=2)
        mgr = CoopManager(daemon)
        mgr._spawn_player("mac_do_p2", "/dev/input/event7")

        assert mgr._players["mac_do_p2"].vpad is None
        assert getattr(daemon, "_launch_env_sossego_em", None) is not None, (
            "o físico entrou na mesa e ninguém reabriu a conta do IGNORE"
        )


# --- o que a cura NÃO conserta, dito em voz alta -----------------------------


class TestOAvisoHonesto:
    """O jogo congela a env no `exec`; regravar o arquivo não o alcança."""

    def test_cobertura_que_muda_com_jogo_de_pe_vira_aviso(
        self, mesa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        espiao = _LoggerEspiao()
        monkeypatch.setattr(le, "logger", espiao)
        # Marker do wrapper: launch NOSSO, deste segundo, com pid vivo.
        (mesa / "last_run").write_text(
            f"appid={APPID_SACKBOY}\nepoch={int(le.time.time())}\npid={os.getpid()}\n",
            encoding="utf-8",
        )
        daemon = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(daemon)
        daemon.controller.describe_controllers = lambda: [{"connected": True}] * 4

        le.armar_rematerializacao(daemon, motivo="teste", agora=0.0)
        le.rematerializar_se_sossegou(daemon, agora=le.JANELA_DE_SOSSEGO_SEC)

        campos = espiao.campos("launch_env_mudou_depois_do_exec")
        assert campos["appid"] == APPID_SACKBOY
        assert campos["cobertura_no_arquivo_antigo"] is True
        assert campos["cobertura_agora"] is False

    def test_sem_jogo_do_wrapper_de_pe_ninguem_e_acordado(
        self, mesa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aviso que aparece sem jogo aberto vira ruído, e ruído esconde sinal."""
        espiao = _LoggerEspiao()
        monkeypatch.setattr(le, "logger", espiao)
        daemon = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(daemon)
        daemon.controller.describe_controllers = lambda: [{"connected": True}] * 4

        le.armar_rematerializacao(daemon, motivo="teste", agora=0.0)
        le.rematerializar_se_sossegou(daemon, agora=le.JANELA_DE_SOSSEGO_SEC)

        assert "launch_env_mudou_depois_do_exec" not in espiao.chaves()
        assert "launch_env_rematerializado_no_sossego" in espiao.chaves()


class TestNuncaDerruba:
    """`launch_env` é best-effort integral: nunca pode derrubar quem o chama."""

    def test_daemon_dublado_sem_superficie_nao_levanta(self) -> None:
        le.armar_rematerializacao(object(), motivo="dublê")
        assert le.rematerializar_se_sossegou(object()) is False
        le.vigiar_a_mesa(object())
