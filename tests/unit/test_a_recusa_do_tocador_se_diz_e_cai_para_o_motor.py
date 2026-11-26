"""A recusa do tocador se diz e cai para o motor (A-RECUSA-DO-TOCADOR-SE-DIZ-E-CAI-PARA-O-MOTOR-01).

O tocador da háptica fina que recusa (sem ``pw-cat``, processo que morre, nó errado) diz que
recusou: o corpo volta ``sem_tocador`` e cai para o motor, os lados do gatilho voltam ``False`` e
o padrão sai pelo motor enquanto a recusa vale. A morte do processo recua 1, 2, 4 s até 60 s; os
60 s de uma vez ficam para «não há tocador». O ``parar()`` no meio da escrita sai ``parado``, sem
recusa, e o nó que o próprio dono recria (a renovação do rótulo) não recusa.

O tocador e o alto-falante são os do produto; o processo do tocador e o relógio são de mentira.
Quatro controles, no cabo e no rádio com ponte: a recusa de um não cala os outros.

MORDIDAS: o ``TOCOU`` incondicional do ``o_que_recusa_o_corpo``; o ``not vista`` puro no
``escrever_o_bloco``; o recuo fixo de 60 s.
"""

from __future__ import annotations

import os
import threading
import time
from array import array
from collections.abc import Iterator
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon import ganho_da_haptica
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.daemon.subsystems import diario_do_corpo as dc
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj

P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(1, 5))
CABO, RADIO = "cabo", "radio"


class _Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class _Cano:
    """O ``stdin`` do processo de mentira: a ponta de escrita de um cano de verdade."""

    def __init__(self) -> None:
        self.leitura, self.escrita = os.pipe()

    def fileno(self) -> int:
        return self.escrita

    def close(self) -> None:
        for fd in (self.escrita, self.leitura):
            if fd >= 0:
                os.close(fd)
        self.escrita = self.leitura = -1


class _Processo:
    def __init__(self, *, morto: bool) -> None:
        self.stdin = _Cano()
        self.codigo: int | None = 1 if morto else None

    def poll(self) -> int | None:
        return self.codigo

    def kill(self) -> None:
        self.codigo = -9

    def wait(self, timeout: float | None = None) -> int | None:
        return self.codigo


class _Lancador:
    def __init__(self, *, morto: bool) -> None:
        self.morto = morto
        self.lancados: list[_Processo] = []

    def __call__(self, _argv: Any, **_kw: Any) -> _Processo:
        proc = _Processo(morto=self.morto)
        self.lancados.append(proc)
        return proc


@pytest.fixture
def relogio() -> _Relogio:
    return _Relogio()


def _sem_conferir(_rotulo: str) -> str | None:
    return None


def _sem_pw_cat(relogio: _Relogio) -> eh.TocadorDoRumble:
    return eh.TocadorDoRumble("m01", argv_de=lambda *_a: [], relogio=relogio)


def _esperar(condicao: Any, prazo_s: float = 3.0) -> bool:
    limite = time.monotonic() + prazo_s
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.005)
    return False


class _TocadorQueToca:
    recusado = False

    def __init__(self) -> None:
        self.corpos = 0
        self.lados: list[tuple[int, int]] = []

    def levar_o_corpo(self, *_a: Any, **_k: Any) -> None:
        self.corpos += 1

    def levar_os_lados(self, esquerdo: int, direito: int, **_k: Any) -> None:
        self.lados.append((esquerdo, direito))


class _Cabo:
    def __init__(self, donos: dict[str, str]) -> None:
        self.donos = donos

    def aparelhos(self) -> dict[str, Any]:
        return {m: SimpleNamespace(dono=d) for m, d in self.donos.items()}

    def leva_os_motores(self, _marca: str) -> bool:
        return True


def _alto(via: str, tocadores: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(ganho_da_haptica.GANHO, "pct", lambda _u: 80)
    alto = af.AltoFalanteSubsystem()
    aparelhos = {u: f"m{u[-2:]}" for u in P}
    for uniq, marca in aparelhos.items():
        nome = f"hefesto_haptica_{marca}"
        alto._endpoints[marca] = SimpleNamespace(module_id=1, nome=nome, marca=marca)
        if via == RADIO:
            alto._pontes[uniq] = SimpleNamespace(esta_de_pe=lambda: True)
            alto._leva_da_ponte = MappingProxyType({**alto._leva_da_ponte, uniq: True})
            alto._endpoint_da_ponte = MappingProxyType({**alto._endpoint_da_ponte, uniq: nome})
    alto._aparelho_de = MappingProxyType(aparelhos)
    alto._tocadores = MappingProxyType({aparelhos[u]: t for u, t in tocadores.items()})
    alto._cabo = _Cabo({aparelhos[u]: u for u in P} if via == CABO else {})
    return alto


@pytest.fixture
def recusado(relogio: _Relogio) -> Iterator[eh.TocadorDoRumble]:
    tocador = _sem_pw_cat(relogio)
    tocador.levar_os_lados(200, 0, sink="hefesto_haptica_m01", dono=P[0])
    assert _esperar(lambda: tocador.recusado), "o tocador sem pw-cat não recusou"
    try:
        yield tocador
    finally:
        tocador.parar()


def test_sem_tocador_instalado_recusa_o_teto_e_diz_o_motivo(
    recusado: eh.TocadorDoRumble, relogio: _Relogio
) -> None:
    assert recusado.motivo_da_recusa == "sem_tocador"
    relogio.t += eh.RECUSA_DO_TOCADOR_S - 0.1
    assert recusado.recusado
    relogio.t += 0.2
    assert not recusado.recusado and recusado.motivo_da_recusa == ""


@pytest.mark.parametrize("via", [CABO, RADIO])
@pytest.mark.parametrize("qual", range(4))
def test_com_o_tocador_recusado_o_corpo_os_lados_e_o_padrao_vao_ao_motor(
    via: str, qual: int, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    tocador = _sem_pw_cat(relogio)
    tocador.levar_os_lados(200, 0, sink="s", dono=P[qual])
    try:
        assert _esperar(lambda: tocador.recusado)
        outros = {u: _TocadorQueToca() for u in P if u != P[qual]}
        alto = _alto(via, {P[qual]: tocador, **outros}, monkeypatch)
        desfecho = alto.tocar_o_corpo(P[qual], array("f", [0.5] * 64))
        assert not desfecho and desfecho.motivo == dc.RECUSA_SEM_TOCADOR
        assert alto.o_que_recusa_o_corpo(P[qual]).motivo == dc.RECUSA_SEM_TOCADOR
        assert alto.levar_os_lados(P[qual], 200, 0) is False
        assert alto.rota_do_padrao(P[qual]) == pv.ROTA_MOTOR
        assert not tocador.tocando_o_corpo, "o corpo da recusa ficou na fila para tocar velho"
        for uniq, outro in outros.items():
            assert alto.tocar_o_corpo(uniq, array("f", [0.5] * 64))
            assert alto.levar_os_lados(uniq, 200, 0) is True
            assert alto.rota_do_padrao(uniq) == pv.ROTA_AUDIO
            assert outro.corpos == 1 and outro.lados
        relogio.t += eh.RECUSA_DO_TOCADOR_S + 1
        assert alto.rota_do_padrao(P[qual]) == pv.ROTA_AUDIO, "a recusa vencida segue no motor"
    finally:
        tocador.parar()


def test_a_recusa_do_tocador_chama_a_queda_pelo_motor() -> None:
    ouvidos: list[str] = []
    passo = SimpleNamespace(
        queda_do_corpo=SimpleNamespace(ouvir=lambda uniq, *_a: ouvidos.append(uniq)),
        _agora_da_continua=0.0,
    )
    assert dc.RECUSA_SEM_TOCADOR not in tv.RECUSAS_SEM_QUEDA
    tv.Passo._cair_pelo_motor(  # type: ignore[arg-type]
        passo, P[2], array("f", [0.4]), dc.DesfechoDoCorpo(dc.RECUSA_SEM_TOCADOR), True)
    assert ouvidos == [P[2]]


def test_o_processo_que_morre_recua_um_dois_quatro_ate_o_teto(relogio: _Relogio) -> None:
    lancar = _Lancador(morto=True)
    tocador = eh.TocadorDoRumble(
        "m01", argv_de=lambda *_a: ["pw-cat"], lancar=lancar, conferir=_sem_conferir,
        relogio=relogio)
    tocador._nivel, tocador._sink = (200, 200), "s"
    esperas: list[float] = []
    for _ in range(8):
        assert not tocador.recusado
        tocador._tocar("s")
        assert tocador.recusado and tocador.motivo_da_recusa == "morreu"
        esperas.append(round(tocador._recuo.ate - relogio.t, 3))
        relogio.t = tocador._recuo.ate
    assert esperas == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]
    assert len(lancar.lancados) == 8, "a tentativa depois do recuo não aconteceu"


def test_o_processo_que_morre_uma_vez_volta_em_ate_dois_segundos(relogio: _Relogio) -> None:
    lancar = _Lancador(morto=True)
    tocador = eh.TocadorDoRumble(
        "m01", argv_de=lambda *_a: ["pw-cat"], lancar=lancar, conferir=_sem_conferir,
        relogio=relogio)
    tocador._nivel, tocador._sink = (200, 200), "s"
    tocador._tocar("s")
    relogio.t += 2.0
    assert not tocador.recusado, "o processo que morreu uma vez tirou mais de 2 s da háptica"


def test_quem_tocou_o_bastante_volta_ao_primeiro_degrau() -> None:
    recuo = eh.RecuoDoTocador(lambda: 0.0)
    for _ in range(4):
        recuo.recusar("morreu")
    assert eh.motivo_da_saida(
        "morreu", parado=False, renovado=False, vivo_s=eh.VIVO_QUE_ZERA_O_RECUO_S, recuo=recuo
    ) == "morreu"
    assert recuo.recusar("morreu") == eh.RECUO_INICIAL_DO_TOCADOR_S


def _tocador_no_cano_cheio(relogio: _Relogio) -> tuple[eh.TocadorDoRumble, threading.Thread]:
    lancar = _Lancador(morto=False)
    tocador = eh.TocadorDoRumble(
        "m01", argv_de=lambda *_a: ["pw-cat"], lancar=lancar, conferir=_sem_conferir,
        relogio=relogio)
    tocador._nivel = (255, 255)
    tocador._sink = "s"
    fio = threading.Thread(target=tocador._tocar, args=("s",), daemon=True)
    fio.start()
    assert _esperar(lambda: tocador._vivo), "o tocador nem chegou a escrever"
    time.sleep(0.2)
    return tocador, fio


def test_parar_no_meio_da_escrita_sai_parado_sem_recusa(relogio: _Relogio) -> None:
    with structlog.testing.capture_logs() as linhas:
        tocador, fio = _tocador_no_cano_cheio(relogio)
        tocador.parar()
        fio.join(3.0)
    assert not fio.is_alive()
    saidas = [x["motivo"] for x in linhas if x["event"] == "haptica_fina_saiu"]
    assert saidas == ["parado"]
    assert not [x for x in linhas if x["event"] == "haptica_fina_recusada"]
    assert not tocador.recusado


def test_o_cano_parado_com_o_fim_armado_diz_parado_e_sem_ele_parou_de_ler() -> None:
    leitura, escrita = os.pipe()
    os.set_blocking(escrita, False)
    try:
        while True:
            os.write(escrita, b"\0" * 65536)
    except BlockingIOError:
        pass
    try:
        fim = threading.Event()
        threading.Timer(0.1, fim.set).start()
        assert eh.escrever_o_bloco(
            escrita, b"\0" * 4096, fim, time.monotonic, continuar_no_cheio=True) == "parado"
        os.close(leitura)
        assert eh.escrever_o_bloco(
            escrita, b"\0" * 4096, threading.Event(), time.monotonic,
            continuar_no_cheio=True) == "parou_de_ler"
    finally:
        os.close(escrita)


def test_a_renovacao_do_rotulo_com_o_tocador_de_pe_nao_recusa(
    relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    tocador, fio = _tocador_no_cano_cheio(relogio)
    try:
        alto = _alto(CABO, {P[0]: tocador}, monkeypatch)
        monkeypatch.setattr(alto, "_a_haptica_esta_em_uso", lambda _e: False)
        processo = tocador._proc

        def renovar() -> None:
            processo.codigo = 0
            os.close(processo.stdin.leitura)
            processo.stdin.leitura = -1

        endpoint = SimpleNamespace(
            marca="m01", module_id=1, rotulo_envelheceu=lambda: True, renovar_o_rotulo=renovar)
        with structlog.testing.capture_logs() as linhas:
            alto._renovar_o_rotulo_da_haptica(endpoint)
            fio.join(3.0)
        assert [x["motivo"] for x in linhas if x["event"] == "haptica_fina_saiu"] == [
            "no_renovado"]
        assert not tocador.recusado, "a renovação do rótulo virou um minuto sem háptica"
    finally:
        tocador.parar()


def test_o_estalo_sem_tocador_recusa_e_o_alto_falante_diz_que_nao_tocou(
    relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    estalo = tj.TocadorDoEstalo("hefesto_som_m01", argv_de=lambda *_a: [], relogio=relogio)
    try:
        estalo.tocar(SimpleNamespace())
        assert _esperar(lambda: estalo.recusado)
        assert estalo.motivo_da_recusa == "sem_tocador"
        alto = _alto(CABO, {}, monkeypatch)
        monkeypatch.setattr(alto, "uniqs_com_no", lambda: [P[0]])
        monkeypatch.setattr(alto, "_tocador_do_estalo", lambda _s: estalo)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.alto_falante_bt.nome_do_sink",
            lambda _u: "hefesto_som_m01")
        assert alto.tocar_o_estalo(P[0], SimpleNamespace()) is False
    finally:
        estalo.parar()


def test_o_estalo_que_morre_recua_como_o_tocador(relogio: _Relogio) -> None:
    lancar = _Lancador(morto=True)
    estalo = tj.TocadorDoEstalo(
        "hefesto_som_m01", argv_de=lambda *_a: ["pw-cat"], lancar=lancar,
        conferir=_sem_conferir, relogio=relogio)
    estalo._tocar()
    assert estalo.recusado and estalo.motivo_da_recusa == "morreu"
    relogio.t += eh.RECUO_INICIAL_DO_TOCADOR_S
    assert not estalo.recusado
