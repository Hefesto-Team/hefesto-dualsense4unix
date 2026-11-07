"""O-DIARIO-DA-EXTENSAO-MORA-FORA-DA-CAIXA-01 — as réguas.

A caixa escreve em ``<dados>/<id>``, e o diário saiu dali. Os dois plantios (link e FIFO) vão de
dentro de um ``bwrap`` de verdade, no lar de mentira, e de novo direto no caminho do diário, para
a segunda barreira morder sozinha. Nada fala com o serviço real.

MORDIDAS, uma por cura: voltar o diário para ``<dados>/<id>``; tirar ``O_NOFOLLOW``, ``O_NONBLOCK``
ou o ``fstat``; voltar a poda da abertura ao ``to_thread`` sem teto; e tirar cada conferência do
``quer_parar`` de ``Supervisor._abrir``. Cada porta (``rb``, ``r+b``, ``ab``, a mudança) morde
sozinha: trocar uma só por ``Path.open`` reprova.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import stat
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import supervisor as supervisor_mod
from hefesto_dualsense4unix.mods.instalador import (
    Lugares,
    anotar_o_gesto,
    conferir_remocao,
    instalar,
    ligar,
    manifesto_instalado,
    remover,
)
from hefesto_dualsense4unix.mods.supervisor import diario_da_extensao
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit import test_o_diario_da_modificacao_tem_teto_enquanto_roda as teto

curto = teto.curto
lar = teto.lar

_ID = "plantador"
_TETO_DA_CORRIDA_S = 20.0
_FOLGA_DO_TETO_S = 1.5

_A_CAIXA_PLANTA = textwrap.dedent('''
    import os, sys
    aqui = os.path.dirname(os.path.abspath(__file__))
    dados = os.environ["HEFESTO_MOD_DADOS"]
    diario = os.path.join(dados, "diario.log")
    plantio, fala = open(os.path.join(aqui, "plantio")).read().split("|")
    if os.path.lexists(diario):
        os.unlink(diario)
    if plantio == "fifo":
        os.mkfifo(diario)
    else:
        os.symlink(plantio, diario)
    if fala == "fala":
        pasta = os.path.join(os.path.dirname(dados), ".diarios")
        print("a caixa ve a pasta dos diarios:", os.path.exists(pasta), flush=True)
    sys.exit(3)
''')

_FICA_DE_PE = textwrap.dedent('''
    import time
    print("de pe", flush=True)
    while True:
        time.sleep(1)
''')


class _Registro:
    """O ``logger`` do supervisor, com o que ele recusou na mão da régua."""

    def __init__(self) -> None:
        self.avisos: list[str] = []

    def warning(self, evento: str, **_campos: Any) -> None:
        self.avisos.append(evento)

    def info(self, *_a: Any, **_k: Any) -> None:
        return None


@pytest.fixture
def registro(monkeypatch: pytest.MonkeyPatch) -> _Registro:
    falso = _Registro()
    monkeypatch.setattr(supervisor_mod, "logger", falso)
    return falso


def _instalar(lugares: Lugares, curto: Path, filho: str, plantio: str = "") -> None:
    pasta = curto / "fonte"
    pasta.mkdir()
    manifesto = {
        "id": _ID,
        "nome": "Plantador",
        "versao": "0.1.0",  # (noqa-acento)
        "api": ">=1,<3",
        "licenca": "MIT",
        "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": ["ler:estado"],  # (noqa-acento)
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (pasta / "mod.py").write_text(filho, encoding="utf-8")
    (pasta / "plantio").write_text(plantio, encoding="utf-8")
    instalar(str(pasta), lugares=lugares)
    ligar(_ID, permissoes_vistas=manifesto_instalado(_ID, lugares=lugares).permissoes,
          lugares=lugares)


def _em_fio(tarefa: Callable[[], Any], teto_s: float = _TETO_DA_CORRIDA_S) -> Any:
    """Roda ``tarefa`` longe do fio do pytest: o travamento vira reprovação, nunca suíte parada."""
    saida: list[Any] = []
    erro: list[BaseException] = []

    def rodar() -> None:
        try:
            saida.append(tarefa())
        except BaseException as exc:
            erro.append(exc)

    fio = threading.Thread(target=rodar, daemon=True)
    fio.start()
    fio.join(teto_s)
    assert not fio.is_alive(), f"travou além de {teto_s} s"
    if erro:
        raise erro[0]
    return saida[0] if saida else None


def _copiar(diario: Path, texto: bytes) -> None:
    async def corrida() -> None:
        leitor = asyncio.StreamReader()
        leitor.feed_data(texto)
        leitor.feed_eof()
        await supervisor_mod._copiar_para_o_diario(leitor, diario)

    asyncio.run(corrida())


def _plantar_o_link(diario: Path, alvo: Path) -> None:
    diario.parent.mkdir(parents=True, exist_ok=True)
    diario.symlink_to(alvo)


def _fios_do_diario() -> list[str]:
    return [f.name for f in threading.enumerate() if f.name.startswith("mods-diario-")]


def test_o_diario_mora_fora_da_pasta_que_a_caixa_monta(lar: Lugares) -> None:
    diario = diario_da_extensao(lar, _ID)
    assert diario.name == supervisor_mod.DIARIO_DA_MODIFICACAO
    assert not diario.is_relative_to(lar.dados / _ID)
    assert diario_da_extensao(lar, "outra").parent != diario.parent


@pytest.mark.parametrize(("plantio", "fala"), [
    ("link", "fala"), ("fifo", "fala"), ("fifo", "muda"),
])
def test_o_plantio_de_dentro_da_caixa_nao_alcanca_a_pessoa(
    lar: Lugares, curto: Path, plantio: str, fala: str,
) -> None:
    exigir_caixa_do_bwrap()
    alvo = curto / "casa" / "da-pessoa.txt"
    conteudo = b"da pessoa, fora da caixa\n" * 8000
    alvo.write_bytes(conteudo)
    _instalar(lar, curto, _A_CAIXA_PLANTA,
              f"{alvo if plantio == 'link' else 'fifo'}|{fala}")
    voltas: list[int] = []

    async def corrida() -> tuple[str, str]:
        supervisor = teto._supervisor(lar, bwrap=shutil.which("bwrap"), esperas=(0.05,))
        assert supervisor.bwrap

        async def tique() -> None:
            while True:
                await asyncio.sleep(0.02)
                voltas.append(1)

        batida = asyncio.create_task(tique())
        await supervisor.iniciar()
        try:
            await teto._ate(lambda: getattr(supervisor.estado_de(_ID), "estado", "") == "parou")
            estado = supervisor.estado_de(_ID)
            assert estado is not None
            return estado.estado, estado.ultima_linha
        finally:
            batida.cancel()
            await supervisor.parar()

    estado, ultima = _em_fio(lambda: asyncio.run(corrida()))

    assert estado == "parou"
    assert alvo.read_bytes() == conteudo
    assert voltas
    plantado = os.lstat(lar.dados / _ID / supervisor_mod.DIARIO_DA_MODIFICACAO).st_mode
    assert (stat.S_ISLNK if plantio == "link" else stat.S_ISFIFO)(plantado)
    if fala == "fala":
        assert ultima == "a caixa ve a pasta dos diarios: False"
        assert "a caixa ve" in diario_da_extensao(lar, _ID).read_text(encoding="utf-8")


def test_o_link_no_caminho_do_diario_se_recusa_nas_tres_portas(
    tmp_path: Path, registro: _Registro,
) -> None:
    alvo = tmp_path / "da-pessoa.txt"
    conteudo = b"linha da pessoa\n" * (teto.TETO // 8)
    alvo.write_bytes(conteudo)
    diario = tmp_path / "ext" / "diario.log"
    _plantar_o_link(diario, alvo)

    _copiar(diario, b"linha que iria para fora\n" * 8)
    with pytest.raises(OSError):
        supervisor_mod._aparar_o_diario(diario, chegando=len(conteudo) * 4)

    assert supervisor_mod.ultima_linha_do_diario(diario) == ""
    assert alvo.read_bytes() == conteudo
    assert registro.avisos == ["mods_diario_recusado"]


def test_a_gravacao_recusa_o_link_sozinha_sem_a_poda_na_frente(
    tmp_path: Path, registro: _Registro, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A poda abre o arquivo antes e recusa primeiro: tirada a poda, responde a porta ``ab``."""
    monkeypatch.setattr(supervisor_mod, "_aparar_o_diario", lambda *_a: None)
    alvo = tmp_path / "da-pessoa.txt"
    alvo.write_bytes(b"da pessoa\n")
    diario = tmp_path / "ext" / "diario.log"
    _plantar_o_link(diario, alvo)

    _copiar(diario, b"linha que iria para fora\n")

    assert alvo.read_bytes() == b"da pessoa\n"
    assert registro.avisos == ["mods_diario_recusado"]


def test_o_fifo_no_caminho_do_diario_nao_trava_nenhuma_das_tres_portas(
    tmp_path: Path, registro: _Registro,
) -> None:
    diario = tmp_path / "ext" / "diario.log"
    diario.parent.mkdir()
    os.mkfifo(diario)

    assert _em_fio(lambda: supervisor_mod.ultima_linha_do_diario(diario), 3.0) == ""
    _em_fio(lambda: _copiar(diario, b"sem ninguem na outra ponta\n"), 3.0)
    assert not _fios_do_diario()

    def aparar() -> None:
        with pytest.raises(OSError):
            supervisor_mod._aparar_o_diario(diario, chegando=teto.TETO * 2)

    _em_fio(aparar, 3.0)
    assert registro.avisos == ["mods_diario_recusado"]


@pytest.mark.parametrize("modo", ["rb", "r+b", "ab"])
def test_o_que_nao_e_arquivo_regular_se_recusa_com_o_leitor_do_outro_lado(
    tmp_path: Path, modo: str,
) -> None:
    """Com alguém lendo, o ``O_NONBLOCK`` abre o FIFO: quem recusa é o ``fstat``."""
    fifo = tmp_path / "diario.log"
    os.mkfifo(fifo)
    leitor = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)

    def abrir() -> None:
        with pytest.raises(OSError, match="regular"):
            supervisor_mod._abrir_o_diario(fifo, modo)

    try:
        _em_fio(abrir, 3.0)
    finally:
        os.close(leitor)


def test_o_diario_velho_vem_uma_vez_e_inteiro(tmp_path: Path) -> None:
    velho = tmp_path / "dados" / "ext" / "diario.log"
    velho.parent.mkdir(parents=True)
    velho.write_bytes(b"2026-11-07 10:00:00 a primeira noite\n")
    inode_velho = velho.stat().st_ino
    diario = tmp_path / "diarios" / "ext" / "diario.log"
    diario.parent.mkdir(parents=True)

    supervisor_mod._preparar_na_vez_do_arquivo(velho, diario, 1.0)

    assert diario.read_bytes() == b"2026-11-07 10:00:00 a primeira noite\n"
    assert not velho.exists()
    assert diario.stat().st_ino != inode_velho

    velho.write_bytes(b"linha forjada pela caixa\n")
    supervisor_mod._preparar_na_vez_do_arquivo(velho, diario, 1.0)

    assert b"forjada" not in diario.read_bytes()


@pytest.mark.parametrize("plantio", ["link", "fifo"])
def test_o_velho_que_nao_e_arquivo_regular_nao_se_move_e_a_recusa_fica_no_registro(
    tmp_path: Path, registro: _Registro, plantio: str,
) -> None:
    alvo = tmp_path / "da-pessoa.txt"
    alvo.write_bytes(b"da pessoa\n")
    velho = tmp_path / "dados" / "ext" / "diario.log"
    velho.parent.mkdir(parents=True)
    if plantio == "link":
        velho.symlink_to(alvo)
    else:
        os.mkfifo(velho)
    diario = tmp_path / "diarios" / "ext" / "diario.log"
    diario.parent.mkdir(parents=True)

    _em_fio(lambda: supervisor_mod._preparar_na_vez_do_arquivo(velho, diario, 1.0), 3.0)

    assert alvo.read_bytes() == b"da pessoa\n"
    assert not diario.exists()
    assert os.path.lexists(velho)
    assert registro.avisos == ["mods_diario_recusado"]


def test_a_abertura_traz_o_diario_velho_para_a_pasta_do_supervisor(
    lar: Lugares, curto: Path,
) -> None:
    _instalar(lar, curto, _FICA_DE_PE)
    velho = lar.dados / _ID / supervisor_mod.DIARIO_DA_MODIFICACAO
    velho.parent.mkdir(parents=True, exist_ok=True)
    velho.write_bytes(b"2026-11-07 10:00:00 a noite de antes\n")
    diario = diario_da_extensao(lar, _ID)

    async def corrida() -> None:
        supervisor = teto._supervisor(lar)
        await supervisor.iniciar()
        try:
            await teto._ate(lambda: "de pe" in teto._texto(diario))
        finally:
            await supervisor.parar()

    _em_fio(lambda: asyncio.run(corrida()))

    assert not os.path.lexists(velho)
    assert teto._texto(diario).startswith("2026-11-07 10:00:00 a noite de antes\n")
    assert stat.S_IMODE(diario.parent.stat().st_mode) == 0o700


def test_o_velho_enorme_traz_so_o_teto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(supervisor_mod, "TETO_DO_DIARIO_BYTES", 1024)
    velho = tmp_path / "velho.log"
    velho.write_bytes(b"x" * 4096 + b"o fim\n")
    diario = tmp_path / "novo.log"

    supervisor_mod._mudar_o_diario_velho(velho, diario)

    assert diario.stat().st_size == 1024
    assert diario.read_bytes().endswith(b"o fim\n")


def test_a_abertura_nao_espera_a_poda_alem_do_teto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    solta = threading.Event()
    monkeypatch.setattr(supervisor_mod, "_aparar_o_diario", lambda *_a: solta.wait(30))
    prazo = 0.2

    async def corrida() -> tuple[float, list[str]]:
        t0 = time.monotonic()
        await supervisor_mod._preparar_com_teto(
            tmp_path / "velho.log", tmp_path / "diario.log", prazo)
        return time.monotonic() - t0, [f.name for f in threading.enumerate()]

    try:
        gasto, fios = _em_fio(lambda: asyncio.run(corrida()), 3.0)
    finally:
        solta.set()

    assert gasto < prazo + _FOLGA_DO_TETO_S
    assert not [nome for nome in fios if nome.startswith("asyncio_")], fios


def test_o_arquivo_preso_pelo_escritor_nao_segura_a_abertura(
    lar: Lugares, curto: Path, registro: _Registro, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O escritor anterior com a trava na mão: a extensão abre, e a poda fica com ele."""
    monkeypatch.setattr(supervisor_mod, "ESPERA_DA_PODA_S", 0.2)
    _instalar(lar, curto, _FICA_DE_PE)
    trava = supervisor_mod._TRAVAS_DOS_DIARIOS.setdefault(
        str(diario_da_extensao(lar, _ID)), threading.Lock())

    async def corrida() -> str:
        supervisor = teto._supervisor(lar)
        await supervisor.iniciar()
        try:
            await teto._ate(lambda: getattr(supervisor.estado_de(_ID), "estado", "") == "rodando",
                            prazo=5.0)
            estado = supervisor.estado_de(_ID)
            assert estado is not None
            return estado.estado
        finally:
            await supervisor.parar()

    assert trava.acquire(timeout=1.0)
    try:
        estado = _em_fio(lambda: asyncio.run(corrida()))
    finally:
        trava.release()

    assert estado == "rodando"
    assert "mods_diario_sem_a_vez" in registro.avisos


def test_a_pasta_do_diario_que_nao_abre_nao_segura_a_extensao(
    lar: Lugares, curto: Path, registro: _Registro,
) -> None:
    _instalar(lar, curto, _FICA_DE_PE)
    lar.dados.mkdir(parents=True, exist_ok=True)
    (lar.dados / ".diarios").write_bytes(b"um arquivo no lugar da pasta\n")

    async def corrida() -> str:
        supervisor = teto._supervisor(lar)
        await supervisor.iniciar()
        try:
            await teto._ate(lambda: getattr(supervisor.estado_de(_ID), "estado", "") == "rodando",
                            prazo=5.0)
            estado = supervisor.estado_de(_ID)
            assert estado is not None
            return estado.estado
        finally:
            await supervisor.parar()

    assert _em_fio(lambda: asyncio.run(corrida())) == "rodando"
    assert "mods_diario_recusado" in registro.avisos


def test_a_parada_durante_a_poda_nao_abre_o_processo(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _instalar(lar, curto, _FICA_DE_PE)
    na_poda = threading.Event()
    solta = threading.Event()

    def poda_presa(*_a: Any) -> None:
        na_poda.set()
        solta.wait(5.0)

    monkeypatch.setattr(supervisor_mod, "_aparar_o_diario", poda_presa)
    abertos: list[Any] = []
    abrir = asyncio.create_subprocess_exec

    async def contar(*argv: Any, **kw: Any) -> Any:
        processo = await abrir(*argv, **kw)
        abertos.append(processo)
        return processo

    monkeypatch.setattr(asyncio, "create_subprocess_exec", contar)

    async def corrida() -> int:
        supervisor = teto._supervisor(lar)
        await supervisor.iniciar()
        try:
            await teto._ate(na_poda.is_set, prazo=5.0)
            await supervisor._parar_uma(_ID)
            solta.set()
            await asyncio.sleep(0.3)
            return len(supervisor.porta._fichas)
        finally:
            await supervisor.parar()

    fichas = _em_fio(lambda: asyncio.run(corrida()))

    assert not abertos
    assert fichas == 0


def test_a_parada_durante_a_abertura_mata_o_grupo_antes_de_registrar(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _instalar(lar, curto, _FICA_DE_PE)
    abertos: list[Any] = []
    abrir = asyncio.create_subprocess_exec

    async def corrida() -> tuple[int, int | None]:
        supervisor = teto._supervisor(lar)

        async def parada_no_meio(*argv: Any, **kw: Any) -> Any:
            processo = await abrir(*argv, **kw)
            abertos.append(processo)
            await supervisor._parar_uma(_ID)
            return processo

        monkeypatch.setattr(asyncio, "create_subprocess_exec", parada_no_meio)
        await supervisor.iniciar()
        try:
            await teto._ate(lambda: bool(abertos), prazo=5.0)
            await teto._ate(lambda: abertos[0].returncode is not None, prazo=5.0)
            await asyncio.sleep(0.1)
            return len(supervisor.porta._fichas), abertos[0].returncode
        finally:
            await supervisor.parar()
            for processo in abertos:
                if processo.returncode is None:
                    os.killpg(processo.pid, signal.SIGKILL)

    fichas, saiu = _em_fio(lambda: asyncio.run(corrida()))

    assert saiu is not None
    assert fichas == 0


def test_remover_leva_o_diario_e_a_conferencia_ve_o_que_sobrou(
    lar: Lugares, curto: Path,
) -> None:
    _instalar(lar, curto, _FICA_DE_PE)
    diario = diario_da_extensao(lar, _ID)
    diario.parent.mkdir(parents=True)
    diario.write_bytes(b"uma linha\n")
    assert not conferir_remocao("outra", lugares=lar)

    anotar_o_gesto(lar, "remover", [_ID])
    assert str(diario.parent) in lar.diario_dos_gestos.read_text(encoding="utf-8")

    assert remover(_ID, lugares=lar, prazo=0.1) == []
    assert not diario.parent.exists()

    diario.parent.mkdir(parents=True)
    assert conferir_remocao(_ID, lugares=lar) == [str(diario.parent)]
