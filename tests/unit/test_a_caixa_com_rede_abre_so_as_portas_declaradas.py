"""A caixa com rede abre só as portas declaradas (A-CAIXA-COM-REDE-ABRE-SO-AS-PORTAS-DECLARADAS-01).

Com o ``pasta``, a caixa com rede ganha um espaço de rede próprio, e do ``127.0.0.1`` da casa só
as ``portas`` do manifesto: ``da_casa`` (o Intiface da máquina, que a extensão alcança) e
``para_a_casa`` (a ponte que os jogos da máquina alcançam). O resto do loopback, o socket abstrato
e o caminho do gateway até a casa ficam fechados. Sem o ``pasta``, a caixa fica no espaço de rede
da casa, e o «sim» diz isso. O ``pasta`` real vem do ``PATH`` ou de ``HEFESTO_PASTA``.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]

_PASTA_DE_MENTIRA = "/usr/bin/pasta"


def _manifesto(permissoes: list[str], portas: dict[str, Any] | None = None) -> Manifesto:
    bruto: dict[str, Any] = {
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": permissoes,  # (noqa-acento)
    }
    if portas is not None:
        bruto["portas"] = portas
    return Manifesto.model_validate(bruto)


def _lovense(intiface: int = 12345, ponte: tuple[int, ...] = (20010, 30010)) -> Manifesto:
    return _manifesto(["rede:internet"], {
        "da_casa": [{"porta": intiface, "nome": "o Intiface desta máquina"}],
        "para_a_casa": [{"porta": p, "nome": "a ponte que os jogos usam"} for p in ponte],
    })


def _caixa(base: Path, manifesto: Manifesto, comando: list[str], *, pasta: str | None,
           ocupada: Any = None) -> list[str]:
    fonte, dados, casa = base / "fonte", base / "dados", base / "casa"
    for pasta_ in (fonte, dados, casa):
        pasta_.mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    return sup.comando_na_caixa(bwrap=shutil.which("bwrap") or "bwrap", comando=comando,
                                codigo=fonte, dados=dados, porta=porta, manifesto=manifesto,
                                casa=casa, execucao=(), pasta=pasta,
                                ocupada=ocupada or (lambda _porta, _udp: False))


def _valores(argv: list[str], opcao: str) -> list[str]:
    fim = argv.index("--")
    return [argv[i + 1] for i in range(fim) if argv[i] == opcao]


def test_com_o_pasta_a_linha_abre_so_as_portas_declaradas(curto: Path) -> None:
    argv = _caixa(curto, _lovense(), ["true"], pasta=_PASTA_DE_MENTIRA)
    assert argv[0] == _PASTA_DE_MENTIRA
    assert _valores(argv, "-T") == ["12345"]
    assert _valores(argv, "-t") == ["127.0.0.1/20010", "127.0.0.1/30010"]
    assert _valores(argv, "-u") == ["none"] and _valores(argv, "-U") == ["none"]
    assert "--no-map-gw" in argv[:argv.index("--")]
    caixa = argv[argv.index("--") + 1:]
    assert caixa[0].endswith("bwrap") and "--unshare-net" not in caixa
    assert caixa[1:6] == ["--unshare-user", "--uid", str(os.getuid()), "--gid", str(os.getgid())]


def test_sem_portas_o_pasta_nao_abre_porta_nenhuma(curto: Path) -> None:
    argv = _caixa(curto, _manifesto(["rede:local"]), ["true"], pasta=_PASTA_DE_MENTIRA)
    for opcao in ("-t", "-u", "-T", "-U"):
        assert _valores(argv, opcao) == ["none"], opcao


def test_o_udp_declarado_vai_so_pelo_udp(curto: Path) -> None:
    manifesto = _manifesto(["rede:local"], {
        "da_casa": [{"porta": 6969, "nome": "o DSX", "udp": True}],
        "para_a_casa": [{"porta": 26760, "nome": "o DSU", "udp": True},
                        {"porta": 26760, "nome": "o DSU"}],
    })
    argv = _caixa(curto, manifesto, ["true"], pasta=_PASTA_DE_MENTIRA)
    assert _valores(argv, "-U") == ["6969"] and _valores(argv, "-T") == ["none"]
    assert _valores(argv, "-u") == ["127.0.0.1/26760"]
    assert _valores(argv, "-t") == ["127.0.0.1/26760"]


def test_a_ponte_ocupada_na_casa_fica_de_fora_e_a_extensao_abre(curto: Path) -> None:
    argv = _caixa(curto, _lovense(), ["true"], pasta=_PASTA_DE_MENTIRA,
                  ocupada=lambda porta, udp: porta == 20010)
    assert _valores(argv, "-t") == ["127.0.0.1/30010"]
    argv = _caixa(curto, _lovense(), ["true"], pasta=_PASTA_DE_MENTIRA,
                  ocupada=lambda porta, udp: True)
    assert _valores(argv, "-t") == ["none"] and _valores(argv, "-T") == ["12345"]


def test_ocupada_na_casa_ve_quem_escuta_no_loopback() -> None:
    with socket.socket() as tcp, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        tcp.bind(("127.0.0.1", 0))
        tcp.listen(1)
        udp.bind(("127.0.0.1", 0))
        assert sup.ocupada_na_casa(tcp.getsockname()[1], False)
        assert sup.ocupada_na_casa(udp.getsockname()[1], True)
        livre = tcp.getsockname()[1]
    assert not sup.ocupada_na_casa(livre, False)


def test_sem_o_pasta_ou_sem_rede_a_linha_e_a_de_antes(curto: Path) -> None:
    casa = _caixa(curto, _lovense(), ["true"], pasta=None)
    assert casa[0].endswith("bwrap") and "--unshare-net" not in casa
    assert "--unshare-user" not in casa
    nenhuma = _caixa(curto, _manifesto(["rede:nenhuma"]), ["true"], pasta=_PASTA_DE_MENTIRA)
    assert nenhuma[0].endswith("bwrap") and "--unshare-net" in nenhuma


@pytest.mark.parametrize("portas, motivo", [
    ({"da_casa": [{"porta": 0, "nome": "x"}]}, "porta"),
    ({"da_casa": [{"porta": 70000, "nome": "x"}]}, "porta"),
    ({"da_casa": [{"porta": "12345", "nome": "x"}]}, "porta"),
    ({"da_casa": [{"porta": True, "nome": "x"}]}, "porta"),
    ({"da_casa": [{"porta": 12345}]}, "nome"),
    ({"da_casa": [{"porta": 12345, "nome": "linha\nquebrada"}]}, "nome"),
    ({"da_casa": [{"porta": 12345, "nome": "x", "ip": "0.0.0.0"}]}, "ip"),
    ({"da_casa": [{"porta": 12345, "nome": "x"}],
      "para_a_casa": [{"porta": 12345, "nome": "y"}]}, "repetida"),
    ({"para_a_casa": [{"porta": 80, "nome": "x"}]}, "1024"),
    ({"da_casa": [{"porta": 1000 + n, "nome": "x"} for n in range(9)]}, "da_casa"),
    ({"todas": True}, "todas"),
])
def test_a_forma_das_portas_e_conferida(portas: dict[str, Any], motivo: str) -> None:
    with pytest.raises(ValueError, match=motivo):
        _manifesto(["rede:local"], portas)


def test_portas_sem_rede_se_recusam() -> None:
    with pytest.raises(ValueError, match="portas pede rede"):
        _manifesto(["rede:nenhuma"], {"da_casa": [{"porta": 12345, "nome": "x"}]})
    with pytest.raises(ValueError, match="portas pede rede"):
        _manifesto([], {"da_casa": [{"porta": 12345, "nome": "x"}]})


def test_o_sim_lista_as_portas_pelo_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: _PASTA_DE_MENTIRA)
    frase = sup.frase_da_rede(_lovense())
    assert frase.startswith(sup.A_REDE_INCLUI_A_INTERNET)
    assert "o Intiface desta máquina (12345)" in frase
    assert "a ponte que os jogos usam (20010, 30010)" in frase
    assert "DSX" not in frase
    assert sup.frase_da_rede(_manifesto(["rede:local"])) == sup.A_REDE_INCLUI_A_INTERNET
    assert sup.frase_da_rede(_manifesto(["rede:nenhuma"])) == ""
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    assert sup.frase_da_rede(_lovense()) == sup.A_REDE_INCLUI_A_MAQUINA


def _o_pasta() -> str:
    exigir_caixa_do_bwrap()
    pasta = os.environ.get("HEFESTO_PASTA") or shutil.which("pasta")
    if not pasta:
        pytest.skip("sem o pasta, a caixa com rede fica no espaço de rede da casa")
    return pasta


def _porta_livre(tipo: int = socket.SOCK_STREAM) -> int:
    with socket.socket(socket.AF_INET, tipo) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


_SONDA = """
import socket, sys
def tenta(familia, onde):
    s = socket.socket(familia); s.settimeout(1.5)
    try:
        s.connect(onde); return "atende"
    except OSError as exc:
        return type(exc).__name__
gw = None
for linha in open("/proc/net/route").read().splitlines()[1:]:
    c = linha.split()
    if c[1] == "00000000":
        gw = socket.inet_ntoa(bytes.fromhex(c[2])[::-1])
declarada, outra, udp, abstrato = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
import os
print("uid", os.getuid())
print("declarada", tenta(socket.AF_INET, ("127.0.0.1", declarada)))
print("outra", tenta(socket.AF_INET, ("127.0.0.1", outra)))
print("abstrato", tenta(socket.AF_UNIX, "\\0" + abstrato))
print("gateway", tenta(socket.AF_INET, (gw, declarada)) if gw else "sem gateway")
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.sendto(b"da-caixa", ("127.0.0.1", udp))
"""


def test_com_o_pasta_real_a_caixa_alcanca_so_a_porta_declarada(curto: Path) -> None:
    pasta = _o_pasta()
    servicos = [socket.socket() for _ in range(2)]
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    abstrato = socket.socket(socket.AF_UNIX)
    nome = f"hefesto-teste-x11-{os.getpid()}"
    try:
        for servico in servicos:
            servico.bind(("127.0.0.1", 0))
            servico.listen(4)
        udp.bind(("127.0.0.1", 0))
        udp.settimeout(1.5)
        abstrato.bind("\0" + nome)
        abstrato.listen(1)
        declarada, outra = (s.getsockname()[1] for s in servicos)
        argv = _caixa(curto, _lovense(intiface=declarada, ponte=(_porta_livre(),)),
                      ["/usr/bin/python3", "-c", _SONDA, str(declarada), str(outra),
                       str(udp.getsockname()[1]), nome], pasta=pasta)
        feito = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
        assert feito.returncode == 0, feito.stderr
        visto = dict(linha.split(" ", 1) for linha in feito.stdout.splitlines())
        assert visto["uid"] == str(os.getuid()), "o barramento do sistema recusa o uid 0"
        assert visto["declarada"] == "atende", visto
        assert visto["outra"] == "ConnectionRefusedError", visto
        assert visto["abstrato"] == "ConnectionRefusedError", visto
        assert visto["gateway"] != "atende", visto
        with pytest.raises(TimeoutError):
            chegou, _de = udp.recvfrom(32)
            pytest.fail(f"o UDP da caixa chegou ao loopback da casa: {chegou!r}")
    finally:
        for s in (*servicos, udp, abstrato):
            s.close()


_PONTE = """
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", int(sys.argv[1])))
s.listen(1)
print("ouvindo", flush=True)
s.settimeout(15)
try:
    c, _ = s.accept()
    c.sendall(b"ponte")
    print("o jogo chegou", flush=True)
except OSError as exc:
    print(type(exc).__name__, flush=True)
"""


_SEM_ENDERECO = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")


def _o_pasta_falando(argv: list[str]) -> list[str]:
    fim = argv.index("--")
    return [("--debug" if i < fim and arg == "--quiet" else arg) for i, arg in enumerate(argv)]


def _o_que_o_pasta_disse(pasta: str, filho: subprocess.Popen[str]) -> str:
    if filho.poll() is None:
        filho.kill()
    _, erros = filho.communicate(timeout=10)
    versao = subprocess.run([pasta, "--version"], capture_output=True, text=True, timeout=10)
    return (f"\n{pasta} --version: {(versao.stdout or versao.stderr).strip()}"
            f"\no stderr do pasta, com o --debug no lugar do --quiet:\n"
            f"{_SEM_ENDERECO.sub('xx:xx:xx:xx:xx:xx', erros)[-6000:]}")


def test_com_o_pasta_real_o_jogo_da_casa_alcanca_a_ponte_declarada(curto: Path) -> None:
    pasta = _o_pasta()
    ponte = _porta_livre()
    filho = subprocess.Popen(
        _o_pasta_falando(_caixa(curto, _lovense(intiface=_porta_livre(), ponte=(ponte,)),
                                     ["/usr/bin/python3", "-c", _PONTE, str(ponte)],
                                     pasta=pasta)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "ouvindo"
        prazo = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection(("127.0.0.1", ponte), timeout=1) as jogo:
                    jogo.settimeout(2)
                    if jogo.recv(5) == b"ponte":
                        break
            except OSError:
                pass
            if time.monotonic() > prazo:
                pytest.fail("o jogo da casa não alcança a ponte declarada"
                            + _o_que_o_pasta_disse(pasta, filho))
            time.sleep(0.1)
        saida, erros = filho.communicate(timeout=20)
        assert "o jogo chegou" in saida, saida + erros
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait()


def test_com_o_pasta_real_a_ponte_nao_se_abre_para_a_rede_da_casa(curto: Path) -> None:
    pasta = _o_pasta()
    ponte = _porta_livre()
    filho = subprocess.Popen(
        _caixa(curto, _lovense(intiface=_porta_livre(), ponte=(ponte,)),
               ["/usr/bin/python3", "-c", "import time; print('ouvindo', flush=True); "
                "time.sleep(8)"], pasta=pasta),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "ouvindo"
        escutando = subprocess.run(["ss", "-Hltn", f"sport = :{ponte}"], capture_output=True,
                                   text=True, check=False).stdout.split()
        locais = [c for c in escutando if c.endswith(f":{ponte}")]
        assert locais == [f"127.0.0.1:{ponte}"], escutando
    finally:
        filho.kill()
        filho.wait()
