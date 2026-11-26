"""A caixa com rede abre só as portas declaradas (A-CAIXA-COM-REDE-ABRE-SO-AS-PORTAS-DECLARADAS-01).

Com o ``pasta``, a caixa com rede ganha um espaço de rede próprio, e do ``127.0.0.1`` da casa só
as ``portas`` do manifesto: ``da_casa`` (o Intiface da máquina, que a extensão alcança) e
``para_a_casa`` (a ponte que os jogos da máquina alcançam). O resto do loopback, o socket abstrato
e o caminho do gateway até a casa ficam fechados. Sem o ``pasta``, a caixa fica no espaço de rede
da casa, e o «sim» diz isso. O ``pasta`` real vem do ``PATH`` ou de ``HEFESTO_PASTA``.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.instalador import Lugares, instalar, ligar, manifesto_instalado
from hefesto_dualsense4unix.mods.manifesto import Manifesto, pedidos_do_sim
from hefesto_dualsense4unix.mods.supervisor import Supervisor
from hefesto_dualsense4unix.utils import xdg_paths
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto, lar

__all__ = ["curto", "lar"]

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
    assert "--uid" not in casa and "--gid" not in casa
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
    monkeypatch.setattr(sup, "o_pasta_entrega_a_ponte", lambda _pasta: True)
    frase = sup.frase_da_rede(_lovense())
    assert frase.startswith(sup.A_REDE_INCLUI_A_INTERNET)
    assert "o Intiface desta máquina (12345)" in frase
    assert "a ponte que os jogos usam (20010, 30010)" in frase
    assert "DSX" not in frase
    assert sup.frase_da_rede(_manifesto(["rede:local"])) == ""
    assert sup.frase_da_rede(_manifesto(["rede:nenhuma"])) == ""
    monkeypatch.setattr(sup, "o_pasta_entrega_a_ponte", lambda _pasta: False)
    assert sup.frase_da_rede(_lovense()) == sup.A_REDE_INCLUI_A_MAQUINA
    assert sup.frase_da_rede(_manifesto(["rede:local"])) == ""
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
    if not sup.sondar_o_pasta(pasta):
        pytest.skip("este pasta não entrega o -t: a sonda do supervisor tira a ponte dele")
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


_PASTA_QUE_NAO_ENTREGA = """
import ctypes, fcntl, os, socket, struct, sys
comando = sys.argv[sys.argv.index("--") + 1:]
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chamadas"), "a") as f:
    f.write(("sonda" if "-c" in comando[:3] else "caixa") + "\\n")
uid, gid = os.getuid(), os.getgid()
filho = os.fork()
if filho == 0:
    if ctypes.CDLL(None, use_errno=True).unshare(0x10000000 | 0x40000000) != 0:
        os._exit(97)
    for nome, texto in (("setgroups", "deny"), ("uid_map", f"0 {uid} 1"),
                        ("gid_map", f"0 {gid} 1")):
        with open(f"/proc/self/{nome}", "w") as f:
            f.write(texto)
    s = socket.socket()
    bandeiras = struct.unpack("16sH", fcntl.ioctl(s, 0x8913, struct.pack("16sH", b"lo", 0)))[1]
    fcntl.ioctl(s, 0x8914, struct.pack("16sH", b"lo", bandeiras | 1))
    os.execvp(comando[0], comando)
_, status = os.waitpid(filho, 0)
sys.exit(os.waitstatus_to_exitcode(status))
"""

_A_EXTENSAO_DA_PONTE = """
import os, socket, time
aqui = os.path.dirname(os.path.abspath(__file__))
porta = int(open(os.path.join(aqui, "porta")).read())
modo = open(os.path.join(aqui, "modo")).read().strip()
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
if modo != "calada":
    s.bind(("127.0.0.1", porta))
    s.listen(8)
print("ouvindo", flush=True)
if modo == "larga":
    time.sleep(0.3)
    s.close()
while modo != "atende":
    time.sleep(1)
while True:
    c, _ = s.accept()
    with c:
        c.sendall(b"ponte")
"""


def _pasta_que_nao_entrega(curto: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    exigir_caixa_do_bwrap()
    pasta = curto / "pasta"
    pasta.write_text(f"#!{sys.executable}\n{_PASTA_QUE_NAO_ENTREGA}", encoding="utf-8")
    pasta.chmod(0o755)
    feito = subprocess.run([str(pasta), "--", "true"], capture_output=True, timeout=30,
                           check=False)
    (curto / "chamadas").unlink(missing_ok=True)
    if feito.returncode != 0:
        pytest.skip("sem espaço de usuário próprio, o pasta de mentira não sobe a caixa")
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: str(pasta))
    monkeypatch.setattr(sup, "_SONDAS", {}, raising=False)
    return pasta


def _instalar_a_ponte(lar: Lugares, curto: Path, ponte: int, modo: str = "atende") -> Path:
    fonte = curto / "fonte-da-ponte"
    fonte.mkdir()
    bruto = {
        "id": "ponte", "nome": "Ponte", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": ["rede:internet"],  # (noqa-acento)
        "portas": {"para_a_casa": [{"porta": ponte, "nome": "a ponte que os jogos usam"}]},
    }
    (fonte / "hefesto-mod.json").write_text(json.dumps(bruto), encoding="utf-8")
    (fonte / "m.py").write_text(_A_EXTENSAO_DA_PONTE, encoding="utf-8")
    (fonte / "porta").write_text(str(ponte), encoding="utf-8")
    (fonte / "modo").write_text(modo, encoding="utf-8")
    instalar(str(fonte), lugares=lar)
    ligar("ponte", permissoes_vistas=pedidos_do_sim(manifesto_instalado("ponte", lugares=lar)),
          lugares=lar)
    return sup.diario_da_extensao(lar, "ponte")


def _supervisor_com_caixa(lar: Lugares) -> Supervisor:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    return Supervisor(EventBus(), escritor=escritor, o_jogo_escreve=lambda uniq, canal: False,
                      uniq_do_posto=lambda: "aa:bb:cc:00:00:01", lugares=lar,
                      bwrap=shutil.which("bwrap"))


def _a_ponte_atende(ponte: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", ponte), timeout=1) as jogo:
            jogo.settimeout(2)
            return jogo.recv(5) == b"ponte"
    except OSError:
        return False


async def _ate(condicao: Any, prazo: float = 30.0) -> None:
    fim = time.monotonic() + prazo
    while not await asyncio.to_thread(condicao):
        if time.monotonic() > fim:
            raise AssertionError("o prazo passou sem a condição")
        await asyncio.sleep(0.1)


def _texto(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError:
        return ""


def _roda_pelo(supervisor: Supervisor, programa: str) -> bool:
    pid = getattr(supervisor.estado_de("ponte"), "pid", None)
    linha = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[:2] if pid else []
    return programa.encode() in linha


def _rodando_sem_queda(supervisor: Supervisor) -> None:
    estado = supervisor.estado_de("ponte")
    assert estado is not None and estado.estado == "rodando", estado
    assert estado.quedas == 0, estado


def test_a_sonda_diz_que_o_pasta_nao_entrega_e_a_caixa_abre_sem_pasta_ja_na_abertura(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1411-A-PONTE-QUE-O-PASTA-NAO-ENTREGA-VOLTA-AO-ESPACO-DA-CASA."""
    pasta = _pasta_que_nao_entrega(curto, monkeypatch)
    ponte = _porta_livre()
    _instalar_a_ponte(lar, curto, ponte)

    async def corrida() -> None:
        supervisor = _supervisor_com_caixa(lar)
        await supervisor.iniciar()
        try:
            await _ate(lambda: _a_ponte_atende(ponte))
            _rodando_sem_queda(supervisor)
            assert not _roda_pelo(supervisor, str(pasta))
            assert _texto(curto / "chamadas").splitlines() == ["sonda"]
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_com_o_pasta_que_entrega_a_extensao_que_larga_a_ponte_segue_no_pasta(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_que_nao_entrega(curto, monkeypatch)
    monkeypatch.setattr(sup, "o_pasta_entrega_a_ponte", lambda _pasta: True, raising=False)
    ponte = _porta_livre()
    diario = _instalar_a_ponte(lar, curto, ponte, "larga")

    async def corrida() -> None:
        supervisor = _supervisor_com_caixa(lar)
        await supervisor.iniciar()
        try:
            await _ate(lambda: "ouvindo" in _texto(diario))
            antes = getattr(supervisor.estado_de("ponte"), "pid", None)
            await asyncio.sleep(1.5)
            _rodando_sem_queda(supervisor)
            assert getattr(supervisor.estado_de("ponte"), "pid", None) == antes
            assert _roda_pelo(supervisor, str(pasta))
            assert _texto(curto / "chamadas").splitlines() == ["caixa"]
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_a_ponte_calada_vai_ao_diario_e_a_extensao_segue_na_caixa(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_que_nao_entrega(curto, monkeypatch)
    monkeypatch.setattr(sup, "o_pasta_entrega_a_ponte", lambda _pasta: True)
    monkeypatch.setattr(sup, "PRAZO_PARA_A_PONTE_OUVIR_S", 1.0)
    ponte = _porta_livre()
    diario = _instalar_a_ponte(lar, curto, ponte, "calada")

    async def corrida() -> None:
        supervisor = _supervisor_com_caixa(lar)
        await supervisor.iniciar()
        try:
            await _ate(lambda: sup.frase_da_ponte_calada(ponte) in _texto(diario))
            _rodando_sem_queda(supervisor)
            assert _roda_pelo(supervisor, str(pasta))
            assert _texto(curto / "chamadas").splitlines() == ["caixa"]
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_a_sonda_roda_uma_vez_por_binario(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_que_nao_entrega(curto, monkeypatch)
    guardado = xdg_paths.state_dir() / sup.SONDA_DO_PASTA
    assert sup.o_pasta_entrega_a_ponte(str(pasta)) is False
    medido = guardado.read_text()
    assert list(json.loads(medido).values()) == [False]
    guardado.unlink()
    assert sup.o_pasta_entrega_a_ponte(str(pasta)) is False
    guardado.write_text(medido)
    monkeypatch.setattr(sup, "_SONDAS", {})
    assert sup.o_pasta_entrega_a_ponte(str(pasta)) is False
    assert _texto(curto / "chamadas").splitlines() == ["sonda"]
    visto = pasta.stat()
    os.utime(pasta, ns=(visto.st_atime_ns, visto.st_mtime_ns + 1_000_000_000))
    assert sup.o_pasta_entrega_a_ponte(str(pasta)) is False
    assert _texto(curto / "chamadas").splitlines() == ["sonda", "sonda"]


def test_a_ponte_ocupada_na_casa_nao_conta_como_ponte_que_nao_atende(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_que_nao_entrega(curto, monkeypatch)
    monkeypatch.setattr(sup, "o_pasta_entrega_a_ponte", lambda _pasta: True)
    monkeypatch.setattr(sup, "PRAZO_PARA_A_PONTE_OUVIR_S", 1.0)
    outro = socket.socket()
    outro.bind(("127.0.0.1", 0))
    outro.listen(4)
    ponte = int(outro.getsockname()[1])
    diario = _instalar_a_ponte(lar, curto, ponte, "calada")

    async def corrida() -> None:
        supervisor = _supervisor_com_caixa(lar)
        await supervisor.iniciar()
        try:
            await _ate(lambda: "ouvindo" in _texto(diario))
            await asyncio.sleep(2)
            _rodando_sem_queda(supervisor)
            assert sup.frase_da_ponte_calada(ponte) not in _texto(diario)
            assert _roda_pelo(supervisor, str(pasta))
            assert _texto(curto / "chamadas").splitlines() == ["caixa"]
        finally:
            await supervisor.parar()
            outro.close()

    asyncio.run(corrida())


def test_com_o_pasta_real_a_ponte_fica_onde_a_sonda_do_supervisor_diz(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _o_pasta()
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: pasta)
    monkeypatch.setattr(sup, "_SONDAS", {})
    ponte = _porta_livre()
    _instalar_a_ponte(lar, curto, ponte)

    async def corrida() -> None:
        supervisor = _supervisor_com_caixa(lar)
        await supervisor.iniciar()
        try:
            await _ate(lambda: _a_ponte_atende(ponte))
            _rodando_sem_queda(supervisor)
            guardado = json.loads((xdg_paths.state_dir() / sup.SONDA_DO_PASTA).read_text())
            assert len(guardado) == 1
            entrega = next(iter(guardado.values()))
            assert isinstance(entrega, bool)
            assert bool(_roda_pelo(supervisor, pasta)) is entrega
        finally:
            await supervisor.parar()

    asyncio.run(corrida())
