"""A MÁSCARA DO GESTO VOLTA PARA O PERFIL (29/08/2026), e o degrau caro guarda.

DUAS FRENTES, um arquivo, porque as duas escrevem no MESMO perfil pelo MESMO
tique e um teste que só cobrisse uma delas deixaria a outra livre para desfazer
o que a primeira gravou.

O NÚMERO QUE AS MOTIVA, e ele é dela
------------------------------------
Os 23 perfis de jogo dela pedem ``mode.gamepad_flavor = "dualsense"``; ela joga
em ``xbox``. Todo lançamento armava o errado e ela apertava ``PS + R3``: **24
vezes em 7 dias**, contadas no journal. O carimbo da ponte não alcançava isso, e
o motivo é estrutural — ``launch_env.arm_launch_profile`` só LÊ o carimbo quando
``mode is None`` (*"o perfil manda"*). Carimbar ``xbox`` num perfil que pede
``dualsense`` deixava o próximo lançamento armando ``dualsense`` de novo,
gritando ``ponte_confirmada_diverge_do_perfil`` no journal, e ela apertando
outra vez.

O PERFIL DELA ENTRA COPIADO, NUNCA LIDO DE ONDE ELA USA
-------------------------------------------------------
``tests/fixtures/perfis/mullet_mad_jack-carimbo-que-ela-desmente.json`` é uma
cópia do ``mullet_mad_jack.json`` dela como estava em 29/08/2026: ``mode``
pedindo ``dualsense``, e um carimbo ``dualsense`` de 03:23:13 gravado
``por=silencio`` com ``gestos=0``. Entre 03:27:59 e 03:29:02 ela apertou o gesto
quatro vezes e parou no ``xbox`` — e o arquivo continuou dizendo ``dualsense``
nas duas linhas. É o estado exato que estas réguas partem.

O QUE CADA UMA MORDE está no docstring dela.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_sub
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.integrations import ponte_tentativa as pt
from hefesto_dualsense4unix.profiles.loader import load_all_profiles, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    CONFIRMADA_POR_GESTO,
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = (
    RAIZ / "tests" / "fixtures" / "perfis" / "mullet_mad_jack-carimbo-que-ela-desmente.json"
)
APPID = 2111190  # Mullet Mad Jack
EPOCH = 1000


def _perfil_dela() -> Profile:
    """O perfil dela, da CÓPIA. Nunca do diretório em que ela joga."""
    return Profile.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _no_disco() -> Profile:
    """O perfil como ficou em disco — releitura, não o objeto em memória."""
    perfis = [p for p in load_all_profiles() if p.name == "Mullet Mad Jack"]
    assert len(perfis) == 1, f"esperava um perfil no disco, achei {len(perfis)}"
    return perfis[0]


class _Daemon:
    """Um daemon só, porque as duas frentes atravessam o gesto E o lançamento.

    Junta o que `_DaemonDoGesto` e `_DaemonFalso` do
    `test_ponte_escada_laco_01_quem_sobe_a_escada.py` fazem separados: o
    `set_gamepad_emulation` do gesto e o `apply_profile_mode` do arming. Uma
    mesa só é o que permite medir a sequência inteira — gesto, tique, e o
    lançamento seguinte — sem trocar de dublê no meio.
    """

    def __init__(self, *, flavor: str = "dualsense") -> None:
        self.controller = SimpleNamespace()
        self.store = SimpleNamespace(
            native_mode_active=False,
            bump=lambda chave: None,
            window_detect_current_class=None,
            window_detect_last_class=None,
        )
        self.display_authority = "game"
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor=flavor
        )
        self._gamepad_device: Any = SimpleNamespace(backend="uhid", flavor=flavor)
        self._coop_manager = None
        self.pedidos: list[tuple[bool, str | None, str]] = []
        self.aplicados: list[Any] = []

    # --- o lado do gesto ---
    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def set_gamepad_emulation(
        self, enabled: bool, flavor: str | None = None, *, origin: str = "manual"
    ) -> bool:
        self.pedidos.append((enabled, flavor, origin))
        if enabled:
            self.config.gamepad_flavor = flavor
            self._gamepad_device = SimpleNamespace(backend="uhid", flavor=flavor)
        else:
            self._gamepad_device = None
        return True

    def set_mouse_emulation(self, enabled: bool, *, origin: str = "profile") -> bool:
        return enabled

    def set_keyboard_emulation(self, enabled: bool) -> bool:
        return enabled

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        return bool(value)

    # --- o lado do lançamento ---
    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append(mode)
        if getattr(mode, "kind", None) == "gamepad":
            self.config.gamepad_flavor = mode.gamepad_flavor
            self._gamepad_device = SimpleNamespace(
                backend="uhid", flavor=mode.gamepad_flavor
            )
        else:
            self._gamepad_device = None
            self.config.gamepad_emulation_enabled = False
        return "aplicado"


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zera a lightbar: estas réguas medem DECISÃO, não relógio."""
    monkeypatch.setattr(hotkey_sub, "PULSO_SEG", 0.0)


@pytest.fixture
def jogo_dela(monkeypatch: pytest.MonkeyPatch) -> int:
    """O appid que o wrapper diria estar rodando — o MESMO sinal do produto.

    `launch_session_appid` é o dono da pergunta *"que jogo é este"* nesta casa
    (`game_signal`, a exceção do R-06, o desvio da allowlist). O gesto o
    consulta pelo `_appid_do_jogo_do_wrapper`, e é ele que se dubla aqui — não
    um segundo caminho inventado para o teste.
    """
    monkeypatch.setattr(le, "launch_session_appid", lambda **kw: APPID)
    return APPID


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    (tmp_path / "last_run").write_text(
        f"appid={APPID}\nepoch={EPOCH}\npid=1\n", encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# S1 — A MÁSCARA DO GESTO VOLTA PARA O PERFIL
# ---------------------------------------------------------------------------
class TestOGestoDelaChegaAoPerfil:
    @pytest.mark.asyncio
    async def test_o_perfil_dela_vira_xbox_depois_do_silencio(
        self, jogo_dela: int
    ) -> None:
        """A sequência inteira, do arquivo dela até o arquivo dela.

        Gesto `PS + R3` com o jogo vivo → `SILENCIO_CONFIRMA_SEC` sem novo
        gesto → o disco diz `xbox` nas DUAS linhas, e o carimbo diz que foi
        `gesto`.

        MORDE, e são três curas independentes: o `gesto_deixou_de_pe` do
        `_ciclar_ponte` (sem ele nada é anotado e o disco fica `dualsense`); o
        `_tique_do_gesto` do `ponte_tentativa` (sem ele o anotado nunca é
        colhido); e o `alinhar_o_modo=` do `tique_da_escada` (sem ele o carimbo
        vira `xbox` e o `mode` fica `dualsense` — que é o estado exato do
        journal dela, com a divergência gritada e ela apertando de novo).
        """
        save_profile(_perfil_dela(), origem="teste")
        antes = _no_disco()
        assert antes.mode is not None and antes.mode.gamepad_flavor == "dualsense"
        assert antes.ponte is not None and antes.ponte.gamepad_flavor == "dualsense"

        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        assert d.pedidos == [(True, "xbox", "manual")], "o gesto tem de obedecer"

        gesto = pt.gesto_em_curso(d)
        assert gesto is not None, "o gesto dela não deixou rastro"
        assert gesto.appid == APPID
        assert gesto.ponte == pe.ESCADA[1].ponte

        # Antes do prazo, NADA é gravado — o silêncio é a confirmação, não o
        # gesto sozinho.
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC - 1)
        meio = _no_disco()
        assert meio.mode is not None and meio.mode.gamepad_flavor == "dualsense"

        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        depois = _no_disco()
        assert depois.mode is not None
        assert depois.mode.gamepad_flavor == "xbox", "a máscara do gesto não voltou"
        assert depois.ponte is not None
        assert depois.ponte.gamepad_flavor == "xbox", "o carimbo velho ficou"
        assert depois.ponte.confirmada_por == CONFIRMADA_POR_GESTO
        assert depois.ponte.confirmada_em != antes.ponte.confirmada_em

    @pytest.mark.asyncio
    async def test_o_resto_do_perfil_dela_nao_e_tocado(self, jogo_dela: int) -> None:
        """Alinhar a máscara não pode reescrever o perfil ao redor dela.

        MORDE um `ProfileModeConfig` construído do zero em
        `alinhar_o_modo_com_a_ponte`: o `coop` dela voltaria ao default e a
        prioridade, os gatilhos e a luz teriam de sobreviver por sorte.
        """
        save_profile(_perfil_dela(), origem="teste")
        antes = _no_disco()

        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        depois = _no_disco()
        assert depois.priority == antes.priority
        assert depois.match == antes.match
        assert depois.triggers == antes.triggers
        assert depois.leds == antes.leds
        assert depois.rumble == antes.rumble
        assert antes.mode is not None and depois.mode is not None
        assert depois.mode.coop == antes.mode.coop, "o coop dela voltou ao default"
        assert depois.mode.kind == antes.mode.kind

    @pytest.mark.asyncio
    async def test_o_lancamento_seguinte_arma_xbox_e_para_de_perguntar(
        self, jogo_dela: int, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A entrega vista do lado dela: o aperto seguinte não acontece.

        MORDE o alinhamento do `mode`: com só o carimbo gravado, este teste
        reprova com `dualsense` armado e `ponte_confirmada_diverge_do_perfil` no
        journal — que é literalmente o que o journal dela mostrava.
        """
        save_profile(_perfil_dela(), origem="teste")
        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        gravado = _no_disco()
        monkeypatch.setattr(le, "_steam_profiles", lambda dd: [(APPID, gravado)])
        outro = _Daemon(flavor="dualsense")
        outro.display_authority = "unknown"  # o jogo ainda não abriu

        resultado = le.arm_launch_profile(outro, base_dir=env_dir, now=EPOCH + 1.0)

        assert resultado is not None
        assert resultado["armado"] is True
        assert resultado["ponte"] == "gamepad/xbox"
        assert outro.config.gamepad_flavor == "xbox", "armou a máscara de novo errada"
        assert resultado["escada"] == pt.COMECO_PRODUTO_JA_SABE

    @pytest.mark.asyncio
    async def test_sem_jogo_do_wrapper_o_gesto_nao_escreve_em_perfil_nenhum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ela mexendo na mesa, fora de uma partida, não é opinião sobre jogo.

        MORDE a recusa por `appid is None` de `gesto_deixou_de_pe`: sem ela o
        gesto no desktop passaria a escrever no perfil do último jogo que
        rodou.
        """
        monkeypatch.setattr(le, "launch_session_appid", lambda **kw: None)
        save_profile(_perfil_dela(), origem="teste")

        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(True, "xbox", "manual")], "o gesto tem de obedecer"
        assert pt.gesto_em_curso(d) is None
        le.tique_da_escada(d, agora=time.monotonic() + 1e6)
        assert _no_disco().mode.gamepad_flavor == "dualsense"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_jogo_fechado_no_meio_nao_carimba_nada(
        self, jogo_dela: int
    ) -> None:
        """Silêncio com o jogo fechado é ela tendo ido embora, não aprovação.

        A mesma disciplina da tentativa, e ela vale para o registro do gesto.
        MORDE o ramo `not jogo_vivo` de `_tique_do_gesto`: sem ele o registro
        sobrevive ao jogo e carimba na sessão seguinte.
        """
        save_profile(_perfil_dela(), origem="teste")
        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None

        d.display_authority = "unknown"  # ela fechou o jogo
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        assert pt.gesto_em_curso(d) is None
        depois = _no_disco()
        assert depois.mode is not None and depois.mode.gamepad_flavor == "dualsense"
        assert depois.ponte is not None
        assert depois.ponte.confirmada_em == _perfil_dela().ponte.confirmada_em  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_mouse_teclado_nao_vira_modo_de_perfil_de_jogo(
        self, jogo_dela: int
    ) -> None:
        """A terceira ponte do ciclo não é degrau da escada, e não se grava.

        Gravar `mode.kind="desktop"` no perfil de um jogo porque ela passou por
        ali seria uma decisão de produto que ninguém pediu. MORDE a recusa por
        `mascara not in MASCARAS_AO_VIVO`.
        """
        save_profile(_perfil_dela(), origem="teste")
        d = _Daemon(flavor="xbox")  # o próximo do ciclo é mouse+teclado

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(False, None, "manual")], "premissa: foi para o desktop"
        assert pt.gesto_em_curso(d) is None
        le.tique_da_escada(d, agora=time.monotonic() + 1e6)
        assert _no_disco().mode.kind == "gamepad"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# S2 — DOIS APERTOS NÃO PODEM CUSTAR A PARTIDA
# ---------------------------------------------------------------------------
def _perfil_antes_do_gesto() -> Profile:
    """O estado dos três casos do journal, e é o dela: o ARQUIVO diz
    `dualsense`, e ela subiu até `xbox` com dois gestos. Sem carimbo.

    O arquivo TEM de dizer `dualsense` aqui. Uma versão anterior desta régua o
    fazia já dizer `xbox` — e com isso as duas asserções de disco passavam com
    a cura arrancada, porque o valor esperado já estava no arquivo antes de
    qualquer gravação. Medido em 29/08/2026 pelo arrancamento: a régua não
    mordia.
    """
    return Profile(
        name="Mullet Mad Jack",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )


class TestODegrauCaroNaoCustaAPartida:
    @pytest.mark.asyncio
    async def test_a_sequencia_do_journal_termina_em_xbox_gravado(
        self, jogo_dela: int
    ) -> None:
        """As quatro linhas do journal, reproduzidas, e o desfecho trocado.

        Medida três vezes (Sackboy 26/08 03:40:45, Mullet 29/08 00:26:17,
        Touhou 29/08 03:19:14), sempre igual:

            ponte_escada_parou_no_degrau_caro  de=gamepad/xbox proximo=native/-
            ponte_escada_encerrada             degrau=gamepad/xbox gestos=2
            ponte_troca_pedida_por_gesto       de=xbox ... para=mouse_teclado

        Terminava em `mouse_teclado` — o gamepad sumindo no meio da partida — e
        sem nada gravado: o `xbox` a que ela chegou com dois gestos evaporava
        com a tentativa.

        MORDE as duas curas: o ramo `PASSO_PAROU` de `_ciclar_ponte` (sem ele
        volta o `mouse_teclado` no mesmo aperto) e o `_anotar_o_gesto` antes do
        `encerrar` (sem ele o `xbox` não chega ao perfil).
        """
        save_profile(_perfil_antes_do_gesto(), origem="teste")
        d = _Daemon(flavor="xbox")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[1],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=2,
        )

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [], "o gamepad sumiu no meio da partida"
        assert d.config.gamepad_flavor == "xbox", "a máscara dela mudou"
        assert pt.em_curso(d) is None, "a tentativa tinha de ser encerrada"

        le.tique_da_escada(d)

        gravado = _no_disco()
        assert gravado.mode is not None
        assert gravado.mode.gamepad_flavor == "xbox", "o degrau de pé evaporou"

    @pytest.mark.asyncio
    async def test_o_degrau_caro_nao_carimba_e_a_escada_continua_aberta(
        self, jogo_dela: int, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O CUIDADO da frente: não matar o caminho para o Nativo.

        Carimbar ali seria o conserto que vira regressão — `proximo_degrau`
        recusa rodar havendo carimbo, e o degrau que ela ainda pode querer
        nunca mais seria sequer nomeado. Alinhando só o `mode`, o lançamento
        seguinte entrega `xbox`, a tentativa reabre NELE, e o degrau seguinte
        que a escada tem para oferecer continua sendo o Nativo.

        MEDIDO E DECLARADO, 29/08/2026 — o que esta régua **não** pode afirmar:
        o Nativo não é ARMADO sozinho no lançamento. `ponte_tentativa.comecar`
        só devolve `armar` no ramo *"ninguém opinou"*, e ali o degrau é sempre
        o primeiro; no ramo *"o perfil manda"* ele devolve `armar=None` de
        propósito. Logo `SUBIR_REABRINDO_O_JOGO` é calculado, vai ao journal, e
        nenhum caminho o executa — um *"a casa sabe e o produto não faz"*
        ANTERIOR a esta leva, e que só se fecha mudando o ramo *"o perfil
        manda"*, que é decisão dela. O que esta frente entrega é o degrau não
        evaporar; chegar ao Nativo sozinho é outra frente.

        MORDE um `confirmar_ponte` no lugar do `alinhar_o_modo_do_appid`: com
        carimbo, `proximo_degrau` devolve `None`, a linha do `escada` vira
        `produto_ja_sabe` e o Nativo some da conta.
        """
        save_profile(_perfil_antes_do_gesto(), origem="teste")
        d = _Daemon(flavor="xbox")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[1],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=2,
        )
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        le.tique_da_escada(d)

        gravado = _no_disco()
        assert gravado.ponte is None, "carimbou o degrau que ela acabou de recusar"

        # ===== O TIQUE NÃO É UM SÓ, E A VIDA NÃO PARA =====================
        # Esta régua rodava `tique_da_escada` UMA VEZ e afirmava que o degrau
        # caro não carimba. MEDIDO em 29/08/2026: carimbava — 181 segundos
        # depois. O ramo `a_registrar` marcava o gesto como registrado e o
        # deixava VIVO, então os tiques seguintes caíam em
        # `confirmacao_por_silencio(confirmada=None, gestos=N)` e carimbavam
        # POR_GESTO o degrau que ela acabou de recusar. No lançamento seguinte
        # a escada via `produto_ja_sabe` e O CAMINHO PARA O NATIVO MORRIA.
        #
        # Os 67 testes da leva que introduziu o ramo passavam com o defeito de
        # pé. É o que esta extensão existe para impedir: a régua tem de viver
        # mais que o primeiro tique, porque a pessoa vive.
        #
        # MORDE: tire o `esquecer_o_gesto(daemon)` do ramo `a_registrar` em
        # `ponte_tentativa` e o carimbo nasce aqui.
        for adiante in (60.0, 120.0, 181.0):
            le.tique_da_escada(d, agora=EPOCH + adiante)
            depois = _no_disco()
            assert depois.ponte is None, (
                f"{adiante:.0f}s depois do degrau caro, o produto carimbou "
                f"sozinho o degrau que ela recusou: {depois.ponte}"
            )
            assert depois.mode is not None and depois.mode.gamepad_flavor == "xbox", (
                "o alinhamento do mode não sobreviveu ao tique seguinte — "
                "alinhar NÃO é confirmar, e o mode é o que vale no próximo "
                "lançamento"
            )

        monkeypatch.setattr(le, "_steam_profiles", lambda dd: [(APPID, gravado)])
        outro = _Daemon(flavor="dualsense")
        outro.display_authority = "unknown"  # o jogo ainda não abriu

        resultado = le.arm_launch_profile(outro, base_dir=env_dir, now=EPOCH + 1.0)

        assert resultado is not None
        assert pe.ESCADA[2].ponte.kind == pe.KIND_NATIVE, "premissa do teste"
        assert resultado["ponte"] == "gamepad/xbox", "o degrau dela não voltou"
        assert outro.config.gamepad_flavor == "xbox"
        assert resultado["escada"] == pt.COMECO_PERFIL_MANDA
        tentativa = pt.em_curso(outro)
        assert tentativa is not None, "a escada fechou num jogo sem carimbo"
        assert tentativa.degrau == pe.ESCADA[1], "a tentativa recomeçou de baixo"
        assert (
            pe.proximo_degrau(ponte_atual=tentativa.ponte) == pe.ESCADA[2]
        ), "o Nativo deixou de ser o próximo"

    @pytest.mark.asyncio
    async def test_o_alinhamento_sobrevive_ao_jogo_fechando(
        self, jogo_dela: int
    ) -> None:
        """Alinhar o `mode` NÃO é confirmar, e por isso não espera silêncio.

        É o que separa esta gravação do carimbo: o defeito medido era o `xbox`
        evaporar quando ela fecha o jogo, e um alinhamento que exigisse três
        minutos de silêncio evaporaria igual. MORDE a ordem de
        `_tique_do_gesto`: mover o `a_registrar` para depois do `not jogo_vivo`
        reprova aqui.
        """
        save_profile(_perfil_antes_do_gesto(), origem="teste")
        d = _Daemon(flavor="xbox")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[1],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=2,
        )
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        d.display_authority = "unknown"  # ela fechou o jogo antes do tique
        le.tique_da_escada(d)

        gravado = _no_disco()
        assert gravado.mode is not None
        assert gravado.mode.gamepad_flavor == "xbox"
        assert gravado.ponte is None


# ---------------------------------------------------------------------------
# A FRONTEIRA que as duas frentes compartilham
# ---------------------------------------------------------------------------
class TestOQueNenhumaDasDuasFaz:
    @pytest.mark.asyncio
    async def test_jogo_sem_perfil_nao_ganha_arquivo(
        self, jogo_dela: int
    ) -> None:
        """Criar perfil nas costas dela tem uma porta só, e é o editor.

        MORDE qualquer atalho que invente um `Profile` em
        `_gravar_no_perfil_do_appid`.
        """
        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None

        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        assert load_all_profiles() == []

    @pytest.mark.asyncio
    async def test_o_silencio_sem_gesto_continua_carimbando_por_silencio(
        self, jogo_dela: int
    ) -> None:
        """A escada sem gesto nenhum não muda de origem NEM alinha o `mode`.

        `POR_SILENCIO` continua sendo o que o produto escreve quando ninguém
        apertou nada, e ali o carimbo basta: `arm_launch_profile` lê o carimbo
        justamente no perfil que não opina. MORDE um `alinhar` incondicional no
        `tique` — ele passaria a escrever `mode` em perfil que ela deixou sem
        opinião de propósito (R-02).
        """
        sem_modo = Profile(
            name="Mullet Mad Jack",
            match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
            priority=80,
        )
        save_profile(sem_modo, origem="teste")
        d = _Daemon(flavor="dualsense")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[0],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=0,
        )

        le.tique_da_escada(d, agora=pe.SILENCIO_CONFIRMA_SEC + 1)

        gravado = _no_disco()
        assert gravado.ponte is not None
        assert gravado.ponte.confirmada_por == "silencio"
        assert gravado.mode is None, "escreveu `mode` num perfil sem opinião"

    def test_a_fixture_e_o_estado_dela_de_29_08(self) -> None:
        """A régua da própria régua: se a cópia mudar, o teste deixa de medir
        o que diz medir."""
        perfil = _perfil_dela()
        assert perfil.mode is not None
        assert perfil.mode.gamepad_flavor == "dualsense"
        assert perfil.ponte == PonteConfirmada(
            kind="gamepad",
            gamepad_flavor="dualsense",
            steam_input=False,
            confirmada_em="2026-08-29T03:23:13-03:00",
            confirmada_por="silencio",
        )
