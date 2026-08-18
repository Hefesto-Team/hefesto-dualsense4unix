"""R-06 (auditoria 23/07) — a allowlist do Steam Input deixa de ser inerte.

`steam_input_apps.txt` (com o appid 2111190 do Mullet Mad Jack) era respeitada
SÓ pelo guard de VDF. Nada no caminho de LANÇAMENTO a consultava — o jogo caía
no `default.env`, que carrega o dedup (`SDL_GAMECONTROLLER_IGNORE_DEVICES` +
`PROTON_DISABLE_HIDRAW`) — e o daemon continuava fazendo EVIOCGRAB no evdev e
mandando o broker esconder o hidraw do controle físico. Ou seja: o jogo cuja
via oficial de DualSense é a API Steamworks (`SetDualSenseTriggerEffect`, que
só funciona com o Steam Input DAQUELE jogo ligado) não achava controle nenhum
da Sony, e a exceção que ela configurou não mudava absolutamente nada.

Contradição 11 da §5 do plano: R-05 empurra o dedup para os `.env` por appid;
R-06 exige `.env` SEM dedup para os appids da allowlist. A allowlist é opt-in
EXPLÍCITO e VENCE para os appids listados; para todos os outros vale o R-05.

SUPERADO em 25/07 pela JOGO-01 — este arquivo dizia aqui que o preço aceito era
"para esses appids o jogo passa a ver o físico E o vpad". Não era preço, era o
defeito: medido com UM DualSense no cabo, o Mullet Mad Jack enumerava js0=vpad
e js2=físico, dava jogador 1 a um e jogador 2 ao outro, e metade dos comandos
dela ia para o controle que o jogo não lia. "Opt-in" não significa dois
dispositivos onde existe um controle — significa trocar QUAL dispositivo o jogo
vê. A JOGO-01 fechou o par: a exceção passou a retirar TAMBÉM o gamepad virtual
de cena.

NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela)
===================================================================
**As quatro travas do MECANISMO deste arquivo caducaram, e o desenho delas foi
invertido, não apagado.** A palavra dela, de 08/08: *"a allowlist do Steam Input
NÃO tira o Hefesto da frente"*. O que a matou é uma medição, não uma
preferência: suspender os gamepads virtuais para curar o controle dobrado
derruba o jogador 2 junto, porque **o jogador 2 é um gamepad virtual** —
`coop_derrubado_pela_excecao_steam_input`, vinte ocorrências no journal dela em
08/08.

A marca passou a significar *"esconda o controle FÍSICO neste jogo"*. Então:

- a **env sem dedup** virou a **ausência de ramo** (o jogo marcado recebe a env
  de qualquer outro jogo) — `TestEnvPorAppidDaAllowlist`;
- o **grab solto e o hidraw exposto** viraram **grab dado e hidraw escondido** —
  `TestModoNativoPorAppid`;
- o **rehide que não desfazia a exceção** virou o **rehide que a SUSTENTA**: é
  ele que reesconde o nó que o replug/wake BT recria visível no meio da partida.

O que NÃO caducou, e por isso segue intacto abaixo: a leitura do
`steam_input_apps.txt` e a decisão de sessão (`TestAllowlistNoArquivo` e
`TestSessaoDaExcecao`). QUANDO a marca vale continua sendo exatamente o que o
R-06 estabeleceu; só mudou O QUE ela faz. O desenho inteiro está em
`docs/process/sprints/2026-08-09-ESCONDER-EM-VEZ-DE-SAIR-01-o-duplicado-cura-pelo-outro-lado.md`
e o outro lado da cura em `test_esconder_em_vez_de_sair_01.py`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon import launch_env as le

MMJ = 2111190
_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
_DISABLE = "PROTON_DISABLE_HIDRAW"


def _env_do_arquivo(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        out[chave] = valor
    return out


def _daemon_falso() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="dualsense"
        ),
        _gamepad_device=SimpleNamespace(backend="uhid", _started=True),
        _coop_manager=None,
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=None),
    )


class TestAllowlistNoArquivo:
    def test_le_appids_do_arquivo_xdg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "steam_input_apps.txt").write_text(
            "# comentário\n2111190\n\nlixo\n620 \n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.xdg_paths.config_dir",
            lambda ensure=False: tmp_path,
        )
        assert le.steam_input_appids() == {MMJ, 620}

    def test_arquivo_ausente_nao_levanta(self, tmp_path: Path) -> None:
        assert le.steam_input_appids(tmp_path / "nao-existe.txt") == set()


class TestEnvPorAppidDaAllowlist:
    """NOTA DATADA — 09/08/2026: as duas travas foram INVERTIDAS, não apagadas.

    Elas afirmavam que o appid marcado ganhava uma env PRÓPRIA e SEM dedup — em
    português, *"jogo, olhe para o controle físico"* — e que essa env vencia até
    o perfil do mesmo appid (contradição 11 da §5 do plano). Estava certo
    enquanto a OUTRA metade da marca retirava o gamepad virtual de cena: sem
    vpad, esconder o físico seria deixá-la com ZERO controles.

    A marca inverteu de lado, e o par tem de continuar sendo par. Uma env que
    mande o jogo olhar para o físico enquanto o daemon o graba e esconde o
    hidraw dele produz exatamente o "Jogador 3" fantasma que ela fotografou no
    Sackboy em 08/08: um controle enumerado que não responde a nada. As travas
    passam a afirmar a AUSÊNCIA do ramo.
    """

    def test_appid_marcado_nao_ganha_mais_env_propria(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA: devolva o laço da allowlist a `materialize_launch_env` e o
        `steam_app_<appid>.env` renasce sem dedup — o físico que o daemon acabou
        de agarrar volta a ser enumerado pelo SDL, e o fantasma com ele.
        """
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})

        le.materialize_launch_env(_daemon_falso())

        assert not (tmp_path / f"steam_app_{MMJ}.env").exists(), (
            "o jogo marcado ganhou desvio próprio de lançamento de novo"
        )
        # Sem env própria, ele cai no `default.env` — o MESMO de qualquer outro
        # jogo, e é isso que a decisão dela quer dizer por inteiro.
        env = _env_do_arquivo(tmp_path / "default.env")
        assert _IGNORE in env, "sem o dedup o jogo marcado volta a ver os dois"
        assert env["__GL_SHADER_DISK_CACHE"] == "1"  # o preload inócuo segue

    def test_o_perfil_do_appid_marcado_deixa_de_ser_atropelado(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A contradição 11 virou do avesso: quem vence agora é o PERFIL.

        A marca deixou de ser um desvio do lançamento, então ela não tem mais o
        que sobrescrever — e a máscara que ela escolheu para aquele jogo (aqui,
        Xbox) chega ao `.env` como chegaria em qualquer outro appid.
        """
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        perfil = SimpleNamespace(
            name="mmj",
            mode=SimpleNamespace(kind="gamepad", gamepad_flavor="xbox"),
        )
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(MMJ, perfil)])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})

        le.materialize_launch_env(_daemon_falso())

        env = _env_do_arquivo(tmp_path / f"steam_app_{MMJ}.env")
        assert _IGNORE in env, "a env do perfil dela voltou a ser atropelada"
        assert _DISABLE in env


class TestSessaoDaExcecao:
    def test_marker_do_wrapper_liga_a_excecao(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "last_run").write_text(
            f"appid={MMJ}\nepoch=1000\npid=1\n", encoding="utf-8"
        )
        monkeypatch.setattr(le, "pid_is_alive", lambda pid: True)
        assert (
            le.steam_input_exception_appid(
                _daemon_falso(), base_dir=tmp_path, now=1010.0, allowlist={MMJ}
            )
            == MMJ
        )

    def test_janela_em_foco_liga_a_excecao_sem_wrapper(
        self, tmp_path: Path
    ) -> None:
        """Jogo aberto sem as LaunchOptions do Hefesto também conta."""
        daemon = _daemon_falso()
        daemon.store.window_detect_current_class = f"steam_app_{MMJ}"
        assert (
            le.steam_input_exception_appid(
                daemon, base_dir=tmp_path, now=1.0, allowlist={MMJ}
            )
            == MMJ
        )

    def test_jogo_fora_da_allowlist_nao_liga(self, tmp_path: Path) -> None:
        daemon = _daemon_falso()
        daemon.store.window_detect_current_class = "steam_app_1599660"
        assert (
            le.steam_input_exception_appid(
                daemon, base_dir=tmp_path, now=1.0, allowlist={MMJ}
            )
            is None
        )

    def test_allowlist_vazia_nunca_liga(self, tmp_path: Path) -> None:
        daemon = _daemon_falso()
        daemon.store.window_detect_current_class = f"steam_app_{MMJ}"
        assert (
            le.steam_input_exception_appid(
                daemon, base_dir=tmp_path, now=1.0, allowlist=set()
            )
            is None
        )


class _DaemonComGrab:
    """Daemon falso que observa grab do evdev e chamadas ao broker."""

    def __init__(self, *, appid_ativo: int | None) -> None:
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self._appid_ativo = appid_ativo
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="dualsense"
        )
        self._gamepad_device = SimpleNamespace(backend="uhid", _started=True)
        self._coop_manager = None
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        self.controller = SimpleNamespace(
            _evdev=_Evdev(), hidraw_path=lambda *a: "/dev/hidraw0"
        )

    def is_native_mode(self) -> bool:
        return False


@pytest.fixture
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Substitui o cliente do broker; nada de socket real no teste."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(
        bc, "broker_call_nonblocking", lambda daemon, fn: fn()
    )


@pytest.fixture
def _sem_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A borda de entrada regrava a `.env` do wrapper; aqui isso não interessa.

    ESCONDER-EM-VEZ-DE-SAIR-01: `esconder_o_fisico_para_o_jogo` chama
    `_materialize_launch_env` de propósito (a env do appid tem de estar gravada
    com a verdade de agora antes do próximo `exec` do wrapper) — e quem trava
    esse lado é `TestEnvPorAppidDaAllowlist`, com o diretório sob `tmp_path`.
    """
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)


class TestModoNativoPorAppid:
    """NOTA DATADA — 09/08/2026: o "Modo Nativo por appid" acabou.

    As duas primeiras travas desta classe afirmavam o que a marca fazia com a
    ENTRADA: soltar o grab do evdev, mandar o broker reexpor o hidraw e nunca
    deixar a reconciliação online reesconder nada. Era o Hefesto saindo da
    frente, e é exatamente o que a decisão dela de 09/08 desfez. Elas continuam
    aqui invertidas, com a mesma pergunta e a resposta de hoje; as duas últimas
    (fora da marca nada muda; sair da marca retoma o canônico) nunca dependeram
    do desvio e passam sem tocar em uma linha.
    """

    def test_entrar_na_marca_esconde_o_fisico_em_vez_de_expor(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None, _sem_env: None
    ) -> None:
        """A MORDIDA: troque `esconder_o_fisico_para_o_jogo` pelo par antigo
        (`_set_evdev_grab(daemon, False)` + `client.restore_all`) e as três
        asserções caem juntas. É a inversão inteira, numa linha.
        """
        daemon = _DaemonComGrab(appid_ativo=MMJ)
        monkeypatch.setattr(
            le, "steam_input_exception_appid", lambda d, **k: MMJ
        )

        assert gp.sync_steam_input_exception(daemon) is True

        assert daemon.grabs == [True], "soltar o grab é o jogo vendo o físico"
        assert daemon.hides == ["/dev/hidraw0"], "o hidraw do físico tem de sumir"
        assert daemon.restores == 0, "`restore_all` é a direção contrária da dela"
        assert gp.steam_input_excecao_ativa(daemon) is True

    def test_com_a_marca_ativa_o_broker_reesconde(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        """De gate a aliado: a reconciliação online passou a SUSTENTAR a marca.

        A trava antiga dizia *"sem este gate a reconciliação online (≤30 s)
        desfaria a exceção no meio do jogo — o físico voltaria a 0600"*. Com a
        inversão não há mais nada a desfazer, e o serviço que ela presta virou o
        oposto: o nó recriado por replug/wake BT NASCE VISÍVEL (BROKER-01 §2.2)
        e é este caminho que o esconde de novo, sem esperar o jogo fechar.

        A MORDIDA: devolva o `if steam_input_excecao_ativa(daemon): return` a
        `rehide_physical_hidraw` (e o irmão dele em `_broker_sync_grab`).
        """
        daemon = _DaemonComGrab(appid_ativo=MMJ)
        daemon._steam_input_excecao = True

        gp._broker_sync_grab(daemon, True)
        gp.rehide_physical_hidraw(daemon)
        gp._set_controller_grab(daemon, True)

        assert daemon.hides == ["/dev/hidraw0"] * 3, (
            "os três caminhos do esconde-esconde têm de convergir para o mesmo "
            "estado dentro do jogo marcado — é a idempotência que faz a "
            "reconciliação a cada ≤30 s ser de graça"
        )
        assert daemon.grabs == [True]

    def test_sem_excecao_o_hide_e_o_grab_seguem_iguais(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        """Sanidade: o gate não pode desligar o comportamento default."""
        daemon = _DaemonComGrab(appid_ativo=None)

        gp._set_controller_grab(daemon, True)

        assert daemon.grabs == [True]
        assert daemon.hides == ["/dev/hidraw0"]

    def test_sair_da_excecao_retoma_grab_e_hide(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        daemon = _DaemonComGrab(appid_ativo=None)
        daemon._steam_input_excecao = True
        monkeypatch.setattr(
            le, "steam_input_exception_appid", lambda d, **k: None
        )

        assert gp.sync_steam_input_exception(daemon) is False

        assert daemon.grabs == [True]
        assert daemon.hides == ["/dev/hidraw0"]

    def test_sem_borda_nao_toca_em_nada(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        """A reconciliação roda a 1 Hz: sem borda tem de ser uma comparação."""
        daemon = _DaemonComGrab(appid_ativo=None)
        monkeypatch.setattr(
            le, "steam_input_exception_appid", lambda d, **k: None
        )

        gp.sync_steam_input_exception(daemon)
        gp.sync_steam_input_exception(daemon)

        assert daemon.grabs == []
        assert daemon.hides == []
        assert daemon.restores == 0
