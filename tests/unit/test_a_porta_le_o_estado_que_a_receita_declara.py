"""A porta lê o estado que a receita declara (02/11/2026, ensaio).

O leitor (``integrations/leitor_do_estado.py``) lê só os endereços declarados de um processo
descendente dele, por ``process_vm_readv``. A trava vem antes de qualquer leitura: a chave
«Memória» do jogo, que só o Hefesto grava, o aviso do anticheat e a faixa do ``buildid``.
"""
from __future__ import annotations

import asyncio
import pathlib
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.integrations import leitor_do_estado as leitor
from hefesto_dualsense4unix.integrations.receitas_de_ambiente import override_do_carregador
from hefesto_dualsense4unix.mods.manifesto import TOPICOS_DE_LEITURA, o_que_a_permissao_deixa
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _entrar,
    _porta,
    curto,
)

VALOR = 0x5EED1234
FILHO = r"""
import ctypes, sys
v = ctypes.c_int32(VALOR)
p = ctypes.c_uint64(ctypes.addressof(v))
print(ctypes.addressof(v), ctypes.addressof(p), flush=True)
for linha in sys.stdin:
    v.value = int(linha)
    print("ok", flush=True)
""".replace("VALOR", str(VALOR))


@pytest.fixture
def filho() -> Iterator[tuple[subprocess.Popen[str], int, int]]:
    proc = subprocess.Popen([sys.executable, "-I", "-c", FILHO], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    valor, ponteiro = (int(x) for x in proc.stdout.readline().split())
    try:
        yield proc, valor, ponteiro
    finally:
        proc.kill()
        proc.wait()


def _mudar(proc: subprocess.Popen[str], valor: int) -> None:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(f"{valor}\n")
    proc.stdin.flush()
    assert proc.stdout.readline().strip() == "ok"


def _entrada(*cadeia: int, tipo: str = "i32") -> leitor.Entrada:
    return leitor.entradas_da_receita(
        [dict(nome="vida", modulo="", cadeia_de_ponteiros=list(cadeia), tipo=tipo, hz=10)])[0]


def test_o_leitor_publica_o_valor_declarado_de_um_filho(filho) -> None:
    proc, valor, ponteiro = filho
    direto = leitor.Leitor(proc.pid, [_entrada(valor)], chave_ligada=True,
                           relogio=lambda: 5.0).ler()
    assert direto == {"vida": VALOR, "t": 5.0}
    assert leitor.ler_valor(proc.pid, _entrada(ponteiro, 0)) == VALOR


def test_um_processo_que_nao_e_descendente_e_recusado() -> None:
    try:
        escopo = int(pathlib.Path("/proc/sys/kernel/yama/ptrace_scope").read_text())
    except (OSError, ValueError):
        pytest.skip("sem o Yama, o sistema não separa descendente de irmão")
    if escopo < 1:
        pytest.skip("ptrace_scope=0 deixa ler qualquer processo do mesmo usuário")
    import os

    with pytest.raises(leitor.LeituraRecusadaError, match="não nasceu do leitor"):
        leitor.ler_bytes(os.getppid(), 0x400000, 4)


def test_sem_a_chave_nenhuma_leitura_comeca(filho, monkeypatch) -> None:
    proc, valor, _ = filho
    lidas: list[int] = []
    monkeypatch.setattr(leitor, "ler_bytes", lambda *a: lidas.append(1) or b"\0" * 4)
    with pytest.raises(leitor.LeituraRecusadaError, match="desligada"):
        leitor.Leitor(proc.pid, [_entrada(valor)], chave_ligada=False)
    with pytest.raises(leitor.LeituraRecusadaError, match="desligada"):
        leitor.Varredura(proc.pid, "i32", chave_ligada=False, valor=VALOR)
    assert lidas == []


def test_o_buildid_fora_da_faixa_recusa_antes_de_ler(filho) -> None:
    proc, valor, _ = filho
    with pytest.raises(leitor.LeituraRecusadaError, match="fora da faixa"):
        leitor.Leitor(proc.pid, [_entrada(valor)], chave_ligada=True, buildid="900",
                      faixa={"min": 1000, "max": 2000})
    leitor.Leitor(proc.pid, [_entrada(valor)], chave_ligada=True, buildid="1500",
                  faixa={"min": 1000, "max": 2000})


def test_a_receita_fora_da_forma_e_recusada() -> None:
    base = dict(nome="vida", modulo="", cadeia_de_ponteiros=[16], tipo="i32")
    for errada in ({**base, "hz": 31}, {**base, "tipo": "str"}, {**base, "nome": "Vida!"},
                   {**base, "cadeia_de_ponteiros": []},
                   {**base, "cadeia_de_ponteiros": list(range(9))}):
        with pytest.raises(leitor.LeituraRecusadaError):
            leitor.entradas_da_receita([errada])
    with pytest.raises(leitor.LeituraRecusadaError, match="repete"):
        leitor.entradas_da_receita([base, base])


def test_a_varredura_devolve_contagem_e_token_e_o_endereco_so_quando_sobra_um(filho) -> None:
    proc, valor, _ = filho
    caca = leitor.Varredura(proc.pid, "i32", chave_ligada=True, valor=VALOR)
    assert caca.contagem >= 1 and set(caca.resumo()) == {"token", "contagem"}
    _mudar(proc, VALOR + 7)
    assert caca.refinar("subiu") == 1
    assert caca.endereco() == valor
    _mudar(proc, VALOR + 3)
    assert caca.refinar("desceu") == 1
    zeros = leitor.Varredura(proc.pid, "u8", chave_ligada=True, valor=0)
    assert zeros.contagem > 1
    with pytest.raises(leitor.LeituraRecusadaError, match="sobra um"):
        zeros.endereco()


def test_a_varredura_com_candidatos_de_mais_pede_um_valor(monkeypatch, filho) -> None:
    proc, _, _ = filho
    monkeypatch.setattr(leitor, "CANDIDATOS_SEM_VALOR", 10)
    with pytest.raises(leitor.LeituraRecusadaError, match="comece por um valor"):
        leitor.Varredura(proc.pid, "u8", chave_ligada=True)


def test_a_chave_nasce_desligada_e_o_anticheat_pede_o_aviso(tmp_path) -> None:
    chaves = leitor.ChavesDaMemoria(tmp_path / "chaves.json")
    assert not chaves.ligada("steam:1")
    with pytest.raises(leitor.AvisoDoAnticheatError, match="Easy Anti-Cheat"):
        chaves.gravar("steam:1", True, anticheat="Easy Anti-Cheat")
    assert not chaves.ligada("steam:1")
    chaves.gravar("steam:1", True, anticheat="Easy Anti-Cheat", aviso_visto=True)
    assert chaves.ligada("steam:1")
    chaves.gravar("steam:2", True)
    assert chaves.ligada("steam:2")


def test_o_anticheat_se_acha_pelos_marcadores_da_pasta(tmp_path) -> None:
    (tmp_path / "jogo" / "EasyAntiCheat").mkdir(parents=True)
    (tmp_path / "limpo").mkdir()
    assert leitor.anticheat_do_jogo(tmp_path / "jogo") == "Easy Anti-Cheat"
    assert leitor.anticheat_do_jogo(tmp_path / "limpo") == ""
    assert leitor.anticheat_do_jogo(None) == ""


def test_a_extensao_nao_consegue_gravar_a_chave(curto) -> None:  # noqa: F811
    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus())
        ext = await _entrar(curto, "ficha-a", {"ligado": True})
        try:
            return [await asyncio.to_thread(ext.pedir, metodo, {"jogo": "steam:1",
                                                                "ligada": True})
                    for metodo in ("memoria.chave", "jogo.memoria.chave", "memoria.ligar")]
        finally:
            await porta.parar()

    for resposta in asyncio.run(corrida()):
        assert "error" in resposta and "result" not in resposta, resposta


def test_o_override_do_carregador_so_da_lista_fechada_e_com_a_chave() -> None:
    assert override_do_carregador("ue4ss", chave_ligada=True) == "dwmapi=n,b"
    assert override_do_carregador("ue4ss", chave_ligada=False) == ""
    assert override_do_carregador("winmm", chave_ligada=True) == ""


def test_a_permissao_e_o_topico_da_memoria() -> None:
    assert TOPICOS_DE_LEITURA["jogo.memoria"] == (leitor.TOPICO_DA_MEMORIA,)
    frase = o_que_a_permissao_deixa("ler:jogo.memoria")
    assert "Memória" in frase and frase != "ler:jogo.memoria"


def test_o_leitor_e_pai_do_jogo_e_sem_permissao_o_argv_sai_igual() -> None:
    jogo = [sys.executable, "-I", "-c", "import os; print(os.getppid())"]
    assert leitor.argv_com_o_leitor(jogo, permitido=False) == jogo
    argv = leitor.argv_com_o_leitor(jogo, permitido=True)
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, text=True)
    saida, _ = proc.communicate(timeout=30)
    assert proc.returncode == 0
    assert int(saida.strip()) == proc.pid
