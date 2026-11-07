"""O serviço guarda o próprio registro, sem depender do diário do sistema.

Em 06/11/2026 o diário do usuário começava às 05:13, com 90 % das linhas de outro programa, e as
paradas das 04:44 ficaram sem registro. Aqui o serviço escreve o próprio arquivo: depois da máscara,
fora do fio do laço, com teto e rotação, e a parada escoa a fila.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import stat
import subprocess
import sys
import textwrap
import threading
import time
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer

import hefesto_dualsense4unix
from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.daemon import main as daemon_main
from hefesto_dualsense4unix.daemon.subsystems.vigia_do_laco import VigiaDoLaco
from hefesto_dualsense4unix.utils import logging_config as lc
from hefesto_dualsense4unix.utils import memoria_dos_controles as memoria

ENDERECO = "aa:bb:cc:dd:ee:{:02x}"
MASCARADO = "aa:bb:cc:00:00:{:02x}"
MESAS = {
    "tres_cabos_e_um_radio": ("usb", "usb", "usb", "bt"),
    "um_cabo_e_tres_radios": ("usb", "bt", "bt", "bt"),
    "dois_e_dois": ("usb", "bt", "usb", "bt"),
    "quatro_cabos": ("usb", "usb", "usb", "usb"),
    "quatro_radios": ("bt", "bt", "bt", "bt"),
    "so_o_p3_no_cabo": (None, None, "usb", None),
    "so_o_p3_no_radio": (None, None, "bt", None),
}
MODOS = ("dualsense", "xbox", "mouse_e_teclado")


class _DiarioCurto(io.TextIOBase):
    """O diário do sistema: guarda poucas linhas, e quem escreve mais apaga as de todos."""

    def __init__(self, linhas: int) -> None:
        self.guardado: deque[str] = deque(maxlen=linhas)

    def write(self, texto: str) -> int:
        self.guardado.extend(linha for linha in texto.splitlines() if linha)
        return len(texto)


@pytest.fixture
def diario() -> _DiarioCurto:
    return _DiarioCurto(linhas=50)


@pytest.fixture
def arquivo(tmp_path: Path, diario: _DiarioCurto) -> Iterator[Path]:
    lc.reset_for_tests()
    lc.configure_logging(stream=diario)
    caminho = tmp_path / "estado" / lc.NOME_DO_REGISTRO
    lc.guardar_o_registro_do_servico(caminho)
    yield caminho
    lc.reset_for_tests()


def _no_disco(caminho: Path) -> str:
    assert lc._REGISTRO.escoar(5.0)
    return caminho.read_text(encoding="utf-8")


def test_a_linha_do_servico_segue_legivel_com_o_diario_inundado(
        arquivo: Path, diario: _DiarioCurto) -> None:
    lc.get_logger("t").warning("controle_caiu", jogador=1)
    assert any("controle_caiu" in linha for linha in diario.guardado)
    for numero in range(1000):
        diario.write(f"gilrs: Device event {numero}\n")
    assert not any("controle_caiu" in linha for linha in diario.guardado)

    texto = _no_disco(arquivo)

    assert "controle_caiu" in texto and "gilrs" not in texto


def test_a_parada_do_laco_entra_pelo_vigia_de_verdade(arquivo: Path) -> None:
    agora = [0.0]
    vigia = VigiaDoLaco(limite_s=10.0, relogio=lambda: agora[0])
    agora[0] = 11.0
    vigia.olhar()

    assert "laco_parado" in _no_disco(arquivo)


def test_a_linha_sem_hora_ganha_a_hora_e_a_cor_nao_entra(arquivo: Path) -> None:
    lc._REGISTRO.por("\x1b[31mlinha sem hora\x1b[0m")

    linha = _no_disco(arquivo).splitlines()[-1]

    assert lc._JA_TEM_HORA.match(linha.encode())
    assert linha.endswith(" linha sem hora")


def test_o_endereco_sai_mascarado_nas_tres_portas(arquivo: Path) -> None:
    lc.get_logger("t").warning("visto", uniq=ENDERECO.format(1))
    logging.getLogger("biblioteca").warning("aparelho %s", ENDERECO.format(2))
    lc._escrever_no_stderr(f"Exception in thread {ENDERECO.format(3)}:\n")

    texto = _no_disco(arquivo)

    for numero in (1, 2, 3):
        assert ENDERECO.format(numero) not in texto
        assert MASCARADO.format(numero) in texto


def test_a_linha_de_biblioteca_entra_uma_vez_so(arquivo: Path) -> None:
    logging.getLogger("biblioteca").warning("uma vez")
    lc.get_logger("t").warning("outra")

    texto = _no_disco(arquivo)

    assert texto.count("uma vez") == 1 and texto.count("outra") == 1


@pytest.mark.parametrize("modo", MODOS)
@pytest.mark.parametrize("mesa", MESAS.values(), ids=MESAS.keys())
def test_cada_controle_da_mesa_entra_sem_endereco(
        arquivo: Path, mesa: tuple[str | None, ...], modo: str) -> None:
    logger = lc.get_logger("t")
    presentes = [(n, via) for n, via in enumerate(mesa, start=1) if via is not None]
    for numero, via in presentes:
        logger.warning("controle_na_mesa", jogador=numero, transporte=via, modo=modo,
                       uniq=ENDERECO.format(numero))

    texto = _no_disco(arquivo)

    for numero, via in presentes:
        linha = next(x for x in texto.splitlines() if f"jogador={numero}" in x)
        assert f"transporte={via}" in linha and f"modo={modo}" in linha
        assert ENDERECO.format(numero) not in linha and MASCARADO.format(numero) in linha
    assert texto.count("controle_na_mesa") == len(presentes)


def test_a_rotacao_respeita_o_teto(arquivo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lc, "TETO_DO_REGISTRO", 2048)
    for numero in range(600):
        lc._REGISTRO.por(f"2026-11-07T10:00:00 linha {numero:04d} " + "x" * 40)
        assert lc._REGISTRO.escoar(5.0)

    geracoes = lc.geracoes_do_registro(arquivo)

    assert [c.name for c in sorted(arquivo.parent.iterdir())] == sorted(c.name for c in geracoes)
    assert all(c.stat().st_size <= 2048 for c in geracoes)
    assert "linha 0599" in geracoes[0].read_text(encoding="utf-8")
    assert "linha 0000" not in "".join(c.read_text(encoding="utf-8") for c in geracoes)
    numeros = [linha.split()[2] for c in reversed(geracoes)
               for linha in c.read_text(encoding="utf-8").splitlines()]
    assert numeros == sorted(numeros) and numeros[-1] == "0599"


def test_a_rotacao_que_nao_gira_nao_passa_do_teto(
        arquivo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def preso(_velho: Any, _novo: Any) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(lc, "TETO_DO_REGISTRO", 2048)
    monkeypatch.setattr(lc.os, "replace", preso)
    for numero in range(100):
        lc._REGISTRO.por(f"2026-11-07T10:00:00 linha {numero:04d} " + "x" * 40)
        assert lc._REGISTRO.escoar(5.0)
    assert arquivo.stat().st_size <= 2048
    monkeypatch.undo()

    monkeypatch.setattr(lc, "TETO_DO_REGISTRO", 2048)
    lc._REGISTRO.por("2026-11-07T10:00:01 voltou a girar")
    assert lc._REGISTRO.escoar(5.0)

    texto = arquivo.read_text(encoding="utf-8")
    assert "voltou a girar" in texto and "linhas saíram: o disco não acompanhou" in texto
    assert all(c.stat().st_size <= 2048 for c in lc.geracoes_do_registro(arquivo) if c.exists())


def test_o_arquivo_e_so_de_quem_usa_em_toda_geracao(
        arquivo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lc, "TETO_DO_REGISTRO", 256)
    for numero in range(40):
        lc._REGISTRO.por(f"2026-11-07T10:00:00 linha {numero:04d} " + "x" * 40)
        assert lc._REGISTRO.escoar(5.0)

    geracoes = lc.geracoes_do_registro(arquivo)

    assert all(c.exists() and stat.S_IMODE(c.stat().st_mode) == 0o600 for c in geracoes)


def test_a_soma_das_geracoes_cabe_no_disco() -> None:
    assert lc.TETO_DO_REGISTRO * (lc.GERACOES_DO_REGISTRO + 1) <= 16 << 20
    assert lc.TETO_DA_FILA_DO_REGISTRO < lc.TETO_DO_REGISTRO


def test_o_fio_que_chama_o_logger_nunca_escreve_no_disco(
        arquivo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    escreveram: list[int] = []
    real = os.write

    def lento(descritor: int, dados: Any) -> int:
        if descritor == lc._REGISTRO._arquivo:
            escreveram.append(threading.get_ident())
            time.sleep(0.05)
        return real(descritor, dados)

    monkeypatch.setattr(lc.os, "write", lento)
    logger = lc.get_logger("t")
    logger.warning("primeira")
    limite = time.monotonic() + 5.0
    while not escreveram and time.monotonic() < limite:
        time.sleep(0.001)
    assert escreveram

    comeco = time.perf_counter()
    for numero in range(200):
        logger.warning("laco_lento", ms=numero)
    gasto = time.perf_counter() - comeco

    assert gasto < 1.0
    assert threading.get_ident() not in escreveram
    assert _no_disco(arquivo).count("laco_lento") == 200


def test_a_fila_tem_teto_e_o_arquivo_conta_o_que_saiu(
        arquivo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    soltar = threading.Event()
    real = os.write

    def preso(descritor: int, dados: Any) -> int:
        if descritor == lc._REGISTRO._arquivo:
            soltar.wait(5.0)
        return real(descritor, dados)

    monkeypatch.setattr(lc.os, "write", preso)
    monkeypatch.setattr(lc, "TETO_DA_FILA_DO_REGISTRO", 4096)
    for numero in range(1000):
        lc._REGISTRO.por(f"2026-11-07T10:00:00 linha {numero:04d} " + "x" * 80)
    assert lc._REGISTRO._na_fila <= 4096
    soltar.set()

    texto = _no_disco(arquivo)

    assert "saíram: o disco não acompanhou" in texto
    assert "linha 0999" in texto


def test_o_disco_que_recusa_nao_sobe_a_quem_escreve(
        arquivo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def cheio(descritor: int, dados: Any) -> int:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(lc.os, "write", cheio)
    lc.get_logger("t").warning("sem_lugar")
    assert lc._REGISTRO.escoar(5.0)
    monkeypatch.undo()
    lc.get_logger("t").warning("voltou_o_lugar")

    texto = _no_disco(arquivo)
    assert "voltou_o_lugar" in texto and "1 linha saiu: o disco não acompanhou" in texto


def test_a_ressincronia_em_serie_nao_empurra_o_registro(arquivo: Path) -> None:
    """Máquina engasgada transborda a fila sem parar: a linha não pode encher os 12 MB."""
    logger = lc.get_logger("t")
    for _ in range(500):
        logger.info("evdev_ressincronizado", path="/dev/input/event7", botoes=0, mudou=False)
        logger.info("touchpad_ressincronizado", path="/dev/input/event8", dedo=False)
    logger.info("evdev_ressincronizado", path="/dev/input/event7", botoes=1, mudou=True)

    texto = _no_disco(arquivo)

    assert texto.count("evdev_ressincronizado") == 2
    assert texto.count("touchpad_ressincronizado") == 1


def test_a_pasta_que_nao_abre_vira_aviso_e_o_servico_segue(
        tmp_path: Path, diario: _DiarioCurto) -> None:
    lc.reset_for_tests()
    lc.configure_logging(stream=diario)
    bloqueio = tmp_path / "um-arquivo"
    bloqueio.write_text("", encoding="utf-8")
    try:
        lc.guardar_o_registro_do_servico(bloqueio / "servico.log")
        lc.get_logger("t").warning("segue")
    finally:
        lc.reset_for_tests()

    assert any("registro_do_servico_sem_arquivo" in x for x in diario.guardado)
    assert any("segue" in x for x in diario.guardado)


def test_quem_nao_e_o_servico_nao_cria_o_arquivo(
        tmp_path: Path, diario: _DiarioCurto, monkeypatch: pytest.MonkeyPatch) -> None:
    lc.reset_for_tests()
    lc.configure_logging(stream=diario)
    monkeypatch.setattr(lc, "caminho_do_registro", lambda: tmp_path / "servico.log")
    try:
        lc.get_logger("t").warning("da_linha_de_comando")
        assert lc._REGISTRO._na_fila == 0
    finally:
        lc.reset_for_tests()

    assert not (tmp_path / "servico.log").exists()


class _ParouError(Exception):
    pass


def _rodar_ate_o_controle(monkeypatch: pytest.MonkeyPatch, instancia: str) -> list[str]:
    from hefesto_dualsense4unix.utils import migrate_legacy_paths, single_instance

    feitos: list[str] = []

    def controle() -> Any:
        raise _ParouError

    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NICE", "0")
    monkeypatch.setattr(migrate_legacy_paths, "migrate_legacy_paths", lambda: None)
    monkeypatch.setattr(single_instance, "acquire_or_takeover", lambda nome: feitos.append(nome))
    monkeypatch.setattr(daemon_main, "single_instance_name", lambda: instancia)
    monkeypatch.setattr(daemon_main, "guardar_o_registro_do_servico",
                        lambda: feitos.append("registro"))
    monkeypatch.setattr(daemon_main, "build_controller", controle)
    with pytest.raises(_ParouError):
        daemon_main.run_daemon()
    return feitos


def test_o_servico_de_producao_liga_o_registro_depois_de_ser_o_unico(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert _rodar_ate_o_controle(monkeypatch, "daemon") == ["daemon", "registro"]


def test_a_instancia_isolada_nao_disputa_o_arquivo_do_servico(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert _rodar_ate_o_controle(monkeypatch, "daemon-fake") == ["daemon-fake"]


_A_PARADA = """
    import asyncio, logging, os, signal, sys, time
    from pathlib import Path
    from hefesto_dualsense4unix.utils import logging_config as lc

    lc.configure_logging(stream=open(os.devnull, "w"))
    lc.guardar_o_registro_do_servico(Path(sys.argv[1]))
    real = os.write

    def lento(descritor, dados):
        if descritor == lc._REGISTRO._arquivo:
            time.sleep(0.05)
        return real(descritor, dados)

    os.write = lento
    logger = lc.get_logger("t")

    async def principal():
        fim = asyncio.Event()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, fim.set)
        for numero in range(3000):
            logger.warning("linha_na_fila", numero=numero)
        for _ in range(3):
            logger.warning("ipc_lento", metodo="estado")
        os.kill(os.getpid(), signal.SIGTERM)
        await fim.wait()
        logger.warning("ultima_linha_do_servico")

    asyncio.run(principal())
"""


def test_o_sigterm_com_a_fila_cheia_nao_perde_a_ultima_linha(tmp_path: Path) -> None:
    caminho = tmp_path / lc.NOME_DO_REGISTRO
    ambiente = {**os.environ, "PYTHONPATH": str(Path(hefesto_dualsense4unix.__file__).parents[1])}

    subprocess.run([sys.executable, "-c", textwrap.dedent(_A_PARADA), str(caminho)],
                   check=True, env=ambiente, timeout=30)

    texto = caminho.read_text(encoding="utf-8")
    assert "ultima_linha_do_servico" in texto
    assert "vezes=2" in texto


def _gravar(caminho: Path, *linhas: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("".join(f"{linha}\n" for linha in linhas), encoding="utf-8")


def test_o_doctor_diz_ate_onde_o_registro_alcanca(tmp_path: Path) -> None:
    atual = tmp_path / lc.NOME_DO_REGISTRO
    _gravar(atual, "2026-11-07T10:00:00.1 [warning  ] laco_parado segundos=10",
            "2026-11-07T10:00:01.1 [info     ] laco_voltou")
    _gravar(atual.with_name(f"{atual.name}.2"),
            "2026-11-02T05:13:00.1 [error    ] controle_caiu jogador=3")

    linhas = cmd_doctor._linhas_do_registro(atual)

    assert linhas[0][0] == "[ OK ]"
    assert "desde 2026-11-02 05:13" in linhas[0][1] and str(atual) in linhas[0][1]
    assert [marca for marca, _ in linhas] == ["[ OK ]", "[INFO]", "[INFO]"]
    assert "controle_caiu" in linhas[1][1] and "laco_parado" in linhas[2][1]


def test_o_doctor_mostra_os_avisos_mais_novos_e_para_no_teto(tmp_path: Path) -> None:
    atual = tmp_path / lc.NOME_DO_REGISTRO
    _gravar(atual, *(f"2026-11-07T10:00:{n:02d}.1 [warning  ] aviso_{n}" for n in range(8)))

    linhas = cmd_doctor._linhas_do_registro(atual)

    assert [linha.split()[-1] for _, linha in linhas[1:]] == [f"aviso_{n}" for n in range(3, 8)]


def test_o_doctor_le_a_linha_que_o_servico_escreveu_de_verdade(arquivo: Path) -> None:
    lc.get_logger("t").warning("laco_parado", segundos=10)
    lc.get_logger("t").info("sem_novidade")

    linhas = cmd_doctor._linhas_do_registro(arquivo) if _no_disco(arquivo) else []

    assert [marca for marca, _ in linhas] == ["[ OK ]", "[INFO]"]
    assert "laco_parado" in linhas[1][1]


def test_o_doctor_com_o_arquivo_recem_criado_nao_diz_desde_vazio(tmp_path: Path) -> None:
    atual = tmp_path / lc.NOME_DO_REGISTRO
    atual.write_bytes(b"")

    linhas = cmd_doctor._linhas_do_registro(atual)

    assert linhas == [("[ OK ]", f"registro do serviço: 0,0 MB em {atual}")]


def test_o_doctor_sem_arquivo_nao_e_aviso(tmp_path: Path) -> None:
    linhas = cmd_doctor._linhas_do_registro(tmp_path / lc.NOME_DO_REGISTRO)

    assert [marca for marca, _ in linhas] == ["[INFO]"]


def test_o_doctor_diz_o_arquivo_que_nao_abre(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    atual = tmp_path / lc.NOME_DO_REGISTRO
    _gravar(atual, "2026-11-07T10:00:00.1 [warning  ] x")

    def recusa(*_a: Any, **_k: Any) -> str:
        raise PermissionError(13, "Permissão negada")

    monkeypatch.setattr(Path, "read_text", recusa)

    linhas = cmd_doctor._linhas_do_registro(atual)

    assert [marca for marca, _ in linhas] == ["[WARN]"]


def test_o_doctor_inteiro_imprime_o_bloco_com_o_colchete_da_linha(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    async def sem_daemon() -> list[tuple[str, str]]:
        return []

    atual = tmp_path / lc.NOME_DO_REGISTRO
    _gravar(atual, "2026-11-07T10:00:00.1 [warning  ] laco_parado segundos=10")
    for bloco in ("_print_storm_block", "_print_bloco_contratos", "_print_bloco_proton_fixado",
                  "_print_bloco_entrada"):
        monkeypatch.setattr(cmd_doctor, bloco, lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: None)
    monkeypatch.setattr(cmd_doctor, "_avisar_ausente", lambda *a, **k: None)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", sem_daemon)
    monkeypatch.setattr(lc, "caminho_do_registro", lambda: atual)

    with pytest.raises(typer.Exit) as saiu:
        cmd_doctor.doctor_cmd()

    assert saiu.value.exit_code == 0
    saida = capsys.readouterr().out
    assert "== registro do serviço ==" in saida
    assert "[warning  ] laco_parado segundos=10" in saida


def test_o_arquivo_entra_na_classificacao_da_casa() -> None:
    classe, razao = memoria.CLASSIFICACAO[lc.NOME_DO_REGISTRO]

    assert classe == memoria.CASA and "máscara" in razao


def test_o_escoar_nao_espera_com_o_registro_fechado() -> None:
    registro = lc.RegistroDoServico()

    comeco = time.perf_counter()
    assert asyncio.run(asyncio.to_thread(registro.escoar, 5.0))
    assert time.perf_counter() - comeco < 1.0
