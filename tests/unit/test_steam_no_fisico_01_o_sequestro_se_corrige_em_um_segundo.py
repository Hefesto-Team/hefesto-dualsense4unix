"""STEAM-NO-FISICO-01 — um sequestro se corrige em até um segundo.

A PALAVRA DELA, 23/09/2026: *"steam sequestrou hefesto corrigiu ao no segundo
após"* — e, escrita na sprint, a segunda obrigação: *"se outro processo escreve
no físico (o escritor_cru já detecta), o Hefesto reescreve a barra e o número em
até 1 s, quantas vezes for preciso."*

O QUE HAVIA: o produto reafirmava a cor UMA vez, 1,5 s depois de a rajada
sossegar (GATILHO-DA-COR-01), e o Modo Nativo era no-op total. A Steam que
reescrevesse a barra depois disso ganhava até o próximo evento — e o 19/09
mediu que só reconectar o controle curava.

A MATRIZ (regra dela, 23/09): vale nos dois transportes — o `0x31` mínimo pelo
rádio, a classe LED pelo cabo —, nos quatro jogadores, e no Modo Nativo também:
*"no Nativo o jogo recebe o físico, e mesmo assim o número e a barra são do
Hefesto"*.

AS MORDIDAS, exercidas uma a uma e devolvidas: (1) a vigia sem a reescrita
periódica (só na borda) deixa um buraco de mais de um segundo; (2) o
`reafirmar_barra_e_numero` com o portão do `_output_mute` cala o Modo Nativo;
(3) a fatia que não encolhe deixa o laço dormir dois segundos com o nó
sequestrado; (4) sem a FIRMA do nó, a vigia que só varre com o nó alcançável
nunca vê o fd que a Steam abriu ANTES de o broker fechar — o mecanismo inteiro
da sprint (conferência de 23/09/2026).
"""
from __future__ import annotations

import asyncio
import itertools
from types import SimpleNamespace
from typing import Any

import pytest
import structlog
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import escritor_cru as ec
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    COMMON_LIGHTBAR_B,
    COMMON_LIGHTBAR_G,
    COMMON_LIGHTBAR_R,
    COMMON_PLAYER_LEDS,
    mascara_de_player_leds,
)
from hefesto_dualsense4unix.daemon import connection as conn

NO_1 = "/dev/hidraw5"
NO_2 = "/dev/hidraw6"
STEAM = 4242
JOGO = 5151

MAC_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"
MAC_2 = "AA:BB:CC:00:00:02"
UNIQ_2 = "aabbcc000002"

NUMERO_1 = (False, False, True, False, False)
COR_DO_NUMERO_1 = (0, 90, 255)
NUMERO_2 = (False, True, False, True, False)
COR_DO_NUMERO_2 = (255, 40, 40)


# ---------------------------------------------------------------------------
# A vigia, pura — relógio, sonda e permissão de mentira
# ---------------------------------------------------------------------------


class _Mesa:
    """O `/proc` e o `/dev` de mentira que a vigia consulta."""

    def __init__(self) -> None:
        self.donos: dict[str, list[int]] = {}
        self.abertos: set[str] = set()
        self.vivos: set[int] = set()
        self.sondas = 0
        self.falhar = False
        #: nó -> firma (inode, ctime). Todo nó da mesa existe e nasce com uma;
        #: `mexer` é o broker fechando/expondo (o `chmod` anda o ctime).
        self.firmas: dict[str, tuple[int, int]] = {}

    def sonda(self, nos: Any) -> dict[str, list[int]]:
        self.sondas += 1
        if self.falhar:
            raise OSError("varredura interrompida")
        return {n: list(p) for n, p in self.donos.items() if n in set(nos) and p}

    def alcancavel(self, no: str) -> bool:
        return no in self.abertos

    def vivo(self, pid: int) -> bool:
        return pid in self.vivos

    def firma(self, no: str) -> tuple[int, int]:
        return self.firmas.setdefault(no, (int(no.rsplit("hidraw", 1)[-1]), 0))

    def mexer(self, no: str) -> None:
        ino, ctime = self.firma(no)
        self.firmas[no] = (ino, ctime + 1)

    def segurar(self, no: str, pid: int) -> None:
        self.donos.setdefault(no, []).append(pid)
        self.vivos.add(pid)

    def soltar(self, no: str, pid: int) -> None:
        self.donos[no] = [p for p in self.donos.get(no, []) if p != pid]


def _vigia(mesa: _Mesa) -> ec.VigiaDoSequestro:
    return ec.VigiaDoSequestro(
        sonda=mesa.sonda, alcancavel=mesa.alcancavel, vivo=mesa.vivo, firma=mesa.firma
    )


def _passo(vigia: ec.VigiaDoSequestro, nos: list[str], agora: float) -> ec.PassoDaVigia:
    """Um passo inteiro, como o daemon o dá: pergunta, varre se precisar, marca."""
    passo = vigia.passo(nos, agora, sondar=vigia.quer_sondar(nos, agora))
    vigia.reafirmado(passo.a_reafirmar, agora)
    return passo


class TestEmRepousoNaoCustaNada:
    def test_no_fechado_e_ninguem_segurando_varre_uma_vez_so(self) -> None:
        """Com a regra udev da cura, o nó é `0600 root`: ninguém NOVO entra.
        A vigia olha UMA vez, na primeira vista, e depois só com a firma nova."""
        mesa = _Mesa()
        vigia = _vigia(mesa)

        for passo_n in range(20):
            passo = _passo(vigia, [NO_1, NO_2], passo_n * 2.0)
            assert passo.a_reafirmar == ()

        assert mesa.sondas == 1
        assert vigia.vigilante is False

    def test_no_que_nao_existe_nao_custa_varredura(self) -> None:
        """Firma `None` (o nó sumiu): ninguém segura o que não está lá."""
        mesa = _Mesa()
        vigia = ec.VigiaDoSequestro(
            sonda=mesa.sonda, alcancavel=mesa.alcancavel, vivo=mesa.vivo,
            firma=lambda _no: None,
        )

        for passo_n in range(5):
            _passo(vigia, [NO_1], passo_n * 2.0)

        assert mesa.sondas == 0

    def test_a_firma_real_anda_com_o_chmod(self, tmp_path: Any) -> None:
        """`firma_do_no` pergunta ao kernel (`stat`): o `chmod` do broker anda
        o ctime, e o nó que não existe não tem firma."""
        no = tmp_path / "hidraw-de-mentira"
        no.write_bytes(b"")
        antes = ec.firma_do_no(str(no))
        assert antes is not None
        assert ec.firma_do_no(str(no)) == antes
        no.chmod(0o600)
        depois = ec.firma_do_no(str(no))
        assert depois is not None and depois[0] == antes[0]
        if depois == antes:
            pytest.skip("o relógio do sistema de arquivos não andou entre os dois stat")
        assert ec.firma_do_no(str(tmp_path / "nao-existe")) is None

    def test_no_real_fechado_e_inalcancavel(self, tmp_path: Any) -> None:
        """`no_alcancavel` pergunta ao kernel (`access(2)`), sem abrir nada."""
        no = tmp_path / "hidraw-de-mentira"
        no.write_bytes(b"")
        no.chmod(0o600)
        assert ec.no_alcancavel(str(no)) is True
        no.chmod(0o000)
        try:
            if ec.no_alcancavel(str(no)):
                pytest.skip("rodando como root: access(2) não recusa nada")
            assert ec.no_alcancavel(str(no)) is False
        finally:
            no.chmod(0o600)


class TestOSequestroVisto:
    def test_a_borda_reescreve_na_hora(self) -> None:
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        vigia = _vigia(mesa)
        assert _passo(vigia, [NO_1], 0.0).a_reafirmar == ()

        mesa.segurar(NO_1, STEAM)
        passo = _passo(vigia, [NO_1], 0.5)

        assert passo.novos == (NO_1,)
        assert passo.a_reafirmar == (NO_1,)
        assert passo.pids[NO_1] == (STEAM,)

    def test_quantas_vezes_for_preciso_e_nunca_mais_de_um_segundo_sem(self) -> None:
        """A MORDIDA (1): a reescrita não pode ser só na borda. Dez segundos de
        sequestro, fatias de `PASSO_DA_VIGIA_S`: o maior intervalo entre duas
        reescritas tem de caber em um segundo."""
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        reescritas: list[float] = []

        agora = 0.0
        while agora <= 10.0:
            if _passo(vigia, [NO_1], agora).a_reafirmar:
                reescritas.append(agora)
            agora = round(agora + ec.PASSO_DA_VIGIA_S, 6)

        intervalos = [b - a for a, b in itertools.pairwise(reescritas)]
        assert len(reescritas) >= 10
        assert max(intervalos) <= 1.0 + 1e-9, intervalos
        assert vigia.reescritas(NO_1) == len(reescritas)

    def test_o_fd_aberto_antes_de_o_no_fechar_e_visto_na_primeira_olhada(
        self,
    ) -> None:
        """A MORDIDA (4), e é o mecanismo da sprint: a Steam abriu o nó na janela
        em que ele estava exposto, o broker fechou (`0600`), e a vigia olha só
        DEPOIS. `access(2)` responde «inalcançável» — e a Steam segura o fd."""
        mesa = _Mesa()
        mesa.segurar(NO_1, STEAM)  # o fd entrou pela janela; o nó já fechou

        vigia = _vigia(mesa)
        passo = _passo(vigia, [NO_1], 0.0)

        assert passo.novos == (NO_1,)
        assert passo.a_reafirmar == (NO_1,)
        assert _passo(vigia, [NO_1], 1.0).a_reafirmar == (NO_1,)

    def test_a_janela_que_abre_e_fecha_depois_da_primeira_olhada(self) -> None:
        """O `_open_one` expõe o nó para o `hidapi` e fecha — ou o `rehide` da
        reconciliação. A firma anda, e a vigia varre UMA vez: vê quem entrou."""
        mesa = _Mesa()
        vigia = _vigia(mesa)
        _passo(vigia, [NO_1], 0.0)
        _passo(vigia, [NO_1], 2.0)
        assert mesa.sondas == 1

        mesa.segurar(NO_1, STEAM)  # entrou pela janela...
        mesa.mexer(NO_1)  # ...que o broker fechou
        passo = _passo(vigia, [NO_1], 4.0)

        assert mesa.sondas == 2
        assert passo.a_reafirmar == (NO_1,)

    def test_o_no_fechado_com_dono_antigo_continua_vigiado(self) -> None:
        """O descritor aberto ANTES de o nó fechar (a Steam das quatro noites)
        não se fecha sozinho: com o nó `0600` a vigia continua reescrevendo."""
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        _passo(vigia, [NO_1], 0.0)

        mesa.abertos.clear()  # o broker fechou o nó; o fd da Steam ficou
        assert _passo(vigia, [NO_1], 1.0).a_reafirmar == (NO_1,)
        assert vigia.vigilante is True

    def test_com_sequestro_conhecido_a_varredura_espaca(self) -> None:
        """Visto o sequestro, a varredura só procura o FIM dele — a cada 2 s."""
        mesa = _Mesa()
        mesa.segurar(NO_1, STEAM)
        mesa.abertos.add(NO_1)
        vigia = _vigia(mesa)
        _passo(vigia, [NO_1], 0.0)
        antes = mesa.sondas

        for n in range(1, 9):  # 4 segundos em fatias de meio
            _passo(vigia, [NO_1], n * 0.5)

        assert mesa.sondas - antes == 2


class TestOSequestroAcaba:
    def test_o_processo_que_solta_encerra_a_vigia(self) -> None:
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        _passo(vigia, [NO_1], 0.0)

        mesa.soltar(NO_1, STEAM)
        passo = _passo(vigia, [NO_1], 2.0)

        assert passo.soltos == (NO_1,)
        assert passo.pids[NO_1] == (STEAM,)
        # A MORDIDA (5): a reescrita FINAL. Quem larga o nó pode ter escrito
        # depois da última reescrita; sem esta, o último a escrever é ele.
        assert passo.a_reafirmar == (NO_1,)
        assert _passo(vigia, [NO_1], 3.0).a_reafirmar == ()
        assert vigia.encerrar(NO_1) == 1  # a final não entra na conta

    def test_o_processo_que_morre_solta_sem_esperar_a_varredura(self) -> None:
        mesa = _Mesa()
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        mesa.abertos.add(NO_1)
        _passo(vigia, [NO_1], 0.0)
        mesa.abertos.clear()

        mesa.vivos.discard(STEAM)  # SIGTERM na Steam
        passo = _passo(vigia, [NO_1], 0.5)

        assert passo.soltos == (NO_1,)
        assert passo.a_reafirmar == (NO_1,)  # a reescrita final
        assert vigia.vigilante is False

    def test_o_controle_que_sai_da_mesa_sai_da_vigia(self) -> None:
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        _passo(vigia, [NO_1], 0.0)

        passo = _passo(vigia, [], 0.5)

        assert passo.soltos == (NO_1,)
        assert passo.a_reafirmar == ()  # saiu da mesa: não há a quem escrever
        assert vigia.sequestrados == {}

    def test_sonda_que_falha_nao_vira_ninguem_segura(self) -> None:
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        _passo(vigia, [NO_1], 0.0)

        mesa.falhar = True
        passo = _passo(vigia, [NO_1], 2.5)

        assert passo.soltos == ()
        assert passo.a_reafirmar == (NO_1,)


class TestOsQuatroJogadores:
    def test_cada_no_tem_o_seu_relogio(self) -> None:
        """A vigia não é do P1: dois sequestros em nós diferentes, cada um
        reescrito no seu passo."""
        mesa = _Mesa()
        mesa.abertos.update({NO_1, NO_2})
        mesa.segurar(NO_1, STEAM)
        vigia = _vigia(mesa)
        assert _passo(vigia, [NO_1, NO_2], 0.0).a_reafirmar == (NO_1,)

        mesa.segurar(NO_2, JOGO)
        passo = _passo(vigia, [NO_1, NO_2], 0.5)

        assert passo.novos == (NO_2,)
        assert passo.a_reafirmar == (NO_2,)
        assert _passo(vigia, [NO_1, NO_2], 1.0).a_reafirmar == (NO_1,)


# ---------------------------------------------------------------------------
# O backend: o que sai no fio, nos dois transportes, e no Modo Nativo
# ---------------------------------------------------------------------------


class _NoDeLed:
    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []
        self.invalidacoes = 0

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        self.invalidacoes += 1


def _handle(transporte: str) -> SimpleNamespace:
    escritos: list[list[int]] = []
    handle = SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
        transporte=transporte,
        escritos=escritos,
    )
    handle.writeReport = lambda r: escritos.append(list(r)) or len(r)
    return handle


def _numero(uniq: str) -> bp._DesiredOutput:
    if uniq == UNIQ_2:
        return bp._DesiredOutput(led=COR_DO_NUMERO_2, player_leds=NUMERO_2)
    return bp._DesiredOutput(led=COR_DO_NUMERO_1, player_leds=NUMERO_1)


def _backend(*, nativo: bool) -> tuple[bp.PyDualSenseController, SimpleNamespace, _NoDeLed]:
    """P1 no rádio, P2 no cabo; `nativo` liga o `_output_mute` do Modo Nativo."""
    ctl = bp.PyDualSenseController()
    radio = _handle("bt")
    cabo = _handle("usb")
    no_do_cabo = _NoDeLed()
    ctl._handles = {MAC_1: radio, MAC_2: cabo}
    ctl._sysfs = {MAC_2: no_do_cabo}
    ctl._detect_transport = lambda h: h.transporte  # type: ignore[method-assign]
    ctl.set_auto_output_provider(_numero)
    ctl._output_mute = nativo
    return ctl, radio, no_do_cabo


class TestOQueSaiNoFio:
    @pytest.mark.parametrize("nativo", [False, True])
    def test_o_radio_leva_o_report_minimo_com_cor_e_numero(self, nativo: bool) -> None:
        """A MORDIDA (2): com o portão do `_output_mute`, o Modo Nativo cala."""
        ctl, radio, _ = _backend(nativo=nativo)

        resultado = ctl.reafirmar_barra_e_numero([UNIQ_1])

        assert resultado == {MAC_1: True}
        assert len(radio.escritos) == 1
        report = radio.escritos[0]
        common = report[3:50]
        assert report[0] == 0x31
        assert tuple(common[COMMON_LIGHTBAR_R : COMMON_LIGHTBAR_B + 1]) == COR_DO_NUMERO_1
        assert common[COMMON_PLAYER_LEDS] == mascara_de_player_leds(NUMERO_1)
        assert COMMON_LIGHTBAR_G == COMMON_LIGHTBAR_R + 1
        # Só a barra e o número: vibração, gatilhos e áudio continuam do jogo.
        assert common[0] == 0, "valid_flag0 pede vibração/gatilho/áudio"
        assert common[38] == 0, "valid_flag2 religaria o setup da barra"
        assert common[2] == common[3] == 0, "motores"

    @pytest.mark.parametrize("nativo", [False, True])
    def test_o_cabo_vai_pela_classe_led_sem_cache(self, nativo: bool) -> None:
        ctl, _, no = _backend(nativo=nativo)

        resultado = ctl.reafirmar_barra_e_numero([UNIQ_2])

        assert resultado == {MAC_2: True}
        assert no.invalidacoes == 1
        assert no.rgb_calls == [COR_DO_NUMERO_2]
        assert no.player_calls == [NUMERO_2]

    def test_e_mirado_so_no_sequestrado(self) -> None:
        ctl, radio, no = _backend(nativo=False)

        ctl.reafirmar_barra_e_numero([UNIQ_2])

        assert radio.escritos == []
        assert no.rgb_calls == [COR_DO_NUMERO_2]

    def test_o_numero_do_jogo_nao_volta_pela_reescrita(self) -> None:
        """As duas obrigações juntas: o jogo numerou o vpad, a vigia reescreve —
        e o que sai é o número da mesa."""
        ctl, radio, _ = _backend(nativo=False)
        ctl.set_game_authority_provider(lambda: "game")
        ctl.set_game_output_for(MAC_1, led=(64, 0, 0), player_leds=(True, True, False, True, True))

        ctl.reafirmar_barra_e_numero([UNIQ_1])

        common = radio.escritos[-1][3:50]
        assert common[COMMON_PLAYER_LEDS] == mascara_de_player_leds(NUMERO_1)
        assert tuple(common[COMMON_LIGHTBAR_R : COMMON_LIGHTBAR_B + 1]) == COR_DO_NUMERO_1

    def test_nao_conta_como_pintura(self) -> None:
        """Se contasse, cada reescrita armaria o gatilho do fim da sequência."""
        ctl, _, _ = _backend(nativo=False)

        ctl.reafirmar_barra_e_numero([UNIQ_1, UNIQ_2])

        assert ctl.consumir_pinturas_de_lightbar() == 0


# ---------------------------------------------------------------------------
# O daemon: a fatia que encolhe e o diário que conta
# ---------------------------------------------------------------------------


class _Controle:
    def __init__(self, nos: dict[str, str]) -> None:
        self.nos = nos
        self.reescritos: list[list[str]] = []

    def nos_hidraw_por_uniq(self) -> dict[str, str]:
        return dict(self.nos)

    def reafirmar_barra_e_numero(self, uniqs: list[str]) -> dict[str, bool]:
        self.reescritos.append(list(uniqs))
        return dict.fromkeys(uniqs, True)


def _daemon(controle: _Controle, mesa: _Mesa, *, nativo: bool = True) -> SimpleNamespace:
    async def _run_blocking(fn: Any, *args: Any) -> Any:
        return fn(*args)

    daemon = SimpleNamespace(
        controller=controle,
        _run_blocking=_run_blocking,
        is_native_mode=lambda: nativo,
        _is_stopping=lambda: False,
        _stop_event=None,
    )
    daemon._vigia_do_sequestro = _vigia(mesa)
    return daemon


class TestNoDaemon:
    def test_o_modo_nativo_tambem_e_vigiado_e_o_diario_conta(self) -> None:
        """A MATRIZ: no Nativo o jogo recebe o físico, e o número e a barra
        continuam do Hefesto."""
        mesa = _Mesa()
        mesa.abertos.add(NO_1)  # Modo Nativo: o broker expôs o nó ao jogo
        controle = _Controle({UNIQ_1: NO_1})
        daemon = _daemon(controle, mesa, nativo=True)

        async def _roteiro() -> list[dict[str, Any]]:
            with structlog.testing.capture_logs() as registros:
                await conn.vigiar_o_sequestro(daemon, agora=0.0)
                mesa.segurar(NO_1, JOGO)
                await conn.vigiar_o_sequestro(daemon, agora=0.5)
                await conn.vigiar_o_sequestro(daemon, agora=1.0)
                await conn.vigiar_o_sequestro(daemon, agora=1.5)
                mesa.soltar(NO_1, JOGO)
                await conn.vigiar_o_sequestro(daemon, agora=2.5)
                await conn.vigiar_o_sequestro(daemon, agora=3.0)
            return registros

        registros = asyncio.run(_roteiro())

        # Duas durante o sequestro e a FINAL, quando o jogo larga o nó.
        assert controle.reescritos == [[UNIQ_1], [UNIQ_1], [UNIQ_1]]
        eventos = [r["event"] for r in registros]
        assert eventos.count("sequestro_detectado") == 1
        assert eventos.count("sequestro_corrigido") == 1
        encerrado = [r for r in registros if r["event"] == "sequestro_encerrado"]
        assert encerrado and encerrado[0]["reescritas"] == 2
        detectado = next(r for r in registros if r["event"] == "sequestro_detectado")
        assert detectado["pids"] == [JOGO]
        assert detectado["modo_nativo"] is True

    def test_a_fatia_encolhe_enquanto_ha_o_que_vigiar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA (3): sem a fatia curta, o laço dorme 2 s com o nó
        sequestrado, e «em até um segundo» vira «em até dois». E a vigia olha
        ANTES da primeira fatia: a primeira já nasce curta."""
        mesa = _Mesa()
        mesa.abertos.add(NO_1)
        mesa.segurar(NO_1, STEAM)
        controle = _Controle({UNIQ_1: NO_1})
        daemon = _daemon(controle, mesa)
        passos: list[float] = []

        async def _dorme(_daemon: Any, passo: float) -> None:
            passos.append(passo)

        async def _nada(*_a: Any, **_k: Any) -> int:
            return 0

        monkeypatch.setattr(conn, "_wait_or_stop", _dorme)
        monkeypatch.setattr(conn, "vigiar_escritor_cru", _nada)
        monkeypatch.setattr(conn, "disparar_gatilhos_devidos", _nada)
        watch = SimpleNamespace(poll=lambda: False)

        asyncio.run(conn._wait_online_or_hotplug(daemon, watch))

        assert set(passos) == {ec.PASSO_DA_VIGIA_S}
        assert controle.reescritos[0] == [UNIQ_1]

    def test_em_repouso_a_fatia_e_a_de_sempre(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mesa = _Mesa()  # nó fechado, ninguém segurando
        controle = _Controle({UNIQ_1: NO_1})
        daemon = _daemon(controle, mesa)
        passos: list[float] = []

        async def _dorme(_daemon: Any, passo: float) -> None:
            passos.append(passo)

        async def _nada(*_a: Any, **_k: Any) -> int:
            return 0

        monkeypatch.setattr(conn, "_wait_or_stop", _dorme)
        monkeypatch.setattr(conn, "vigiar_escritor_cru", _nada)
        monkeypatch.setattr(conn, "disparar_gatilhos_devidos", _nada)
        watch = SimpleNamespace(poll=lambda: False)

        asyncio.run(conn._wait_online_or_hotplug(daemon, watch))

        assert set(passos) == {conn.RECONNECT_HOTPLUG_POLL_INTERVAL_SEC}
        assert mesa.sondas == 1  # a primeira vista do nó, e nenhuma depois
        assert controle.reescritos == []
