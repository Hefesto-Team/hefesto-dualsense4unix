"""A fila confere tomada e disco antes de trocar, e segura o desligar enquanto troca.

A-FILA-CONFERE-ENERGIA-E-ESPACO-E-SEGURA-O-DESLIGAR-01 (19/11/2026). TUDO É DE MENTIRA: o lar é
``tmp_path`` com ``XDG_*`` desviados, a ``/sys/class/power_supply`` é uma árvore de mentira, o
espaço livre e o inibidor do logind são dublês; o ajudante roda sem root, com ``systemd-run`` e
``apt-get`` dublês num ``PATH`` próprio. Nenhum caso fala com o logind nem roda o apt.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): a conferência da tomada
arrancada reprova o caso da bateria; a do disco, o caso do ``/boot``; o ``with`` do inibidor
arrancado reprova o caso do inibidor; o ``main`` sem ligar a máquina reprova o caso do
``--rodar``; o ``_apt`` sem a unidade própria reprova o caso do ajudante.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "hefesto_atualizador_raiz.sh"


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


def _fonte(raiz: Path, nome: str, **campos: str) -> None:
    pasta = raiz / nome
    pasta.mkdir(parents=True)
    for campo, valor in campos.items():
        (pasta / campo).write_text(f"{valor}\n", encoding="utf-8")


@pytest.fixture
def energia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "power_supply"
    raiz.mkdir()
    monkeypatch.setattr(at, "ENERGIA", raiz)
    return raiz


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    livre: dict[str, int] = {}
    monkeypatch.setattr(at, "_livre_em", lambda caminho: livre.get(str(caminho), 50 * at.GB))
    return livre


def _peca(ident: str, feito: list[str], instalar: Any = None) -> at.Peca:
    def etapa(nome: str) -> Any:
        def fazer(passo: at.Passo, _dados: dict[str, Any]) -> None:
            feito.append(f"{ident}:{nome}")
            passo.fracao(1.0)
        return fazer

    return at.Peca(ident, ident.upper(), "dica", "todos",
                   lambda rede: at.Versoes("1.0", "1.1" if rede else None),
                   etapa("baixar"), instalar or etapa("instalar"), etapa("aplicar"))


def _linha(ident: str) -> dict[str, Any]:
    andamento = at._ler_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO)
    return next(p for p in andamento["pecas"] if p["id"] == ident)


def _rodar(lista: list[at.Peca], **kw: Any) -> int:
    at.conferir(rede=True, lista=lista)
    padrao: dict[str, Any] = {"jogo_aberto": lambda: False, "reiniciar": lambda: True,
                              "reabrir": lambda: True, "maquina": at.conferir_a_maquina,
                              "inibidor": lambda _p: contextlib.nullcontext()}
    return at.rodar([p.id for p in lista], lista=lista, **{**padrao, **kw})


def test_a_bateria_baixa_sem_tomada_espera_com_a_frase(energia: Path, disco: dict[str, int],
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-FILA-ESPERA-A-TOMADA-E-SEGURA-O-DESLIGAR: a bateria a 15% sem tomada espera."""
    _fonte(energia, "AC", type="Mains", online="0")
    _fonte(energia, "BAT0", type="Battery", status="Discharging", capacity="15")
    _fonte(energia, "ps-controller-battery-02:fe:00:00:00:01", type="Battery", scope="Device",
           status="Discharging", capacity="90")
    feito: list[str] = []
    voltas = [0]

    def dormir(_s: float) -> None:
        voltas[0] += 1
        assert _linha("a")["selo"] == at.ESPERANDO
        assert _linha("a")["motivo"] == "ligue na tomada: a bateria está em 15%"
        if voltas[0] == 2:
            (energia / "AC" / "online").write_text("1\n", encoding="utf-8")

    assert _rodar([_peca("a", feito)], dormir=dormir) == 0
    assert feito == ["a:baixar", "a:instalar", "a:aplicar"]
    assert voltas[0] == 2


def test_so_a_bateria_do_controle_ou_a_tomada_nao_seguram(energia: Path) -> None:
    _fonte(energia, "ps-controller-battery-02:fe:00:00:00:01", type="Battery", scope="Device",
           status="Discharging", capacity="5")
    assert at.falta_energia() == ""
    _fonte(energia, "BAT0", type="Battery", status="Discharging", capacity="80")
    assert at.falta_energia() == ""
    (energia / "BAT0" / "capacity").write_text("20\n", encoding="utf-8")
    assert at.falta_energia() == "ligue na tomada: a bateria está em 20%"
    _fonte(energia, "ucsi-source-psy-USBC000:001", type="USB", online="1")
    assert at.falta_energia() == ""


def test_o_boot_abaixo_do_piso_falha_com_o_numero(energia: Path, disco: dict[str, int]) -> None:
    """D-1911-A-FILA-ESPERA-A-TOMADA-E-SEGURA-O-DESLIGAR: o /boot abaixo do piso falha com quanto
    falta, antes de instalar; a peça que não troca kernel não olha o /boot."""
    disco["/boot"] = at.PISO_DO_BOOT - at.GB // 10
    feito: list[str] = []
    assert _rodar([_peca("kernel", feito), _peca("proton", feito)]) == 1
    assert feito == ["kernel:baixar", "proton:baixar", "proton:instalar", "proton:aplicar"]
    assert _linha("kernel")["selo"] == at.FALHOU
    assert _linha("kernel")["motivo"] == "faltam 0,1 GB em /boot"
    assert _linha("proton")["selo"] == at.PRONTA


def test_o_inibidor_segura_o_instalar_e_solta_na_falha_e_no_parar(
        energia: Path, disco: dict[str, int]) -> None:
    """D-1911-A-FILA-ESPERA-A-TOMADA-E-SEGURA-O-DESLIGAR: o desligar fica seguro durante o
    instalar e o aplicar, e solto na falha e no «Parar»."""
    diario: list[str] = []

    @contextlib.contextmanager
    def inibidor(por_que: str) -> Iterator[None]:
        diario.append(f"toma {por_que}")
        try:
            yield
        finally:
            diario.append("solta")

    def instalar_que_falha(_passo: at.Passo, _dados: dict[str, Any]) -> None:
        diario.append("instala")
        raise at.EtapaFalhouError("o apt não instalou")

    feito: list[str] = []
    assert _rodar([_peca("a", feito, instalar_que_falha)], inibidor=inibidor) == 1
    assert diario == ["toma A: instalar", "instala", "solta"]

    def instalar_que_para(_passo: at.Passo, _dados: dict[str, Any]) -> None:
        diario.append("instala")
        raise at.FilaParadaError

    diario.clear()
    assert _rodar([_peca("b", feito, instalar_que_para)], inibidor=inibidor) == 2
    assert diario == ["toma B: instalar", "instala", "solta"]

    diario.clear()
    assert _rodar([_peca("c", feito)], inibidor=inibidor) == 0
    assert diario == ["toma C: instalar", "solta", "toma C: aplicar", "solta"]


def test_o_rodar_de_verdade_liga_a_maquina_e_o_inibidor(monkeypatch: pytest.MonkeyPatch) -> None:
    recebido: dict[str, Any] = {}
    monkeypatch.setattr(at, "rodar", lambda ids, **kw: recebido.update(kw, ids=ids) or 0)
    assert at.main(["--rodar", "kernel"]) == 0
    assert recebido["ids"] == ["kernel"]
    assert recebido["maquina"] is at.conferir_a_maquina
    assert recebido["inibidor"] is at.segurar_o_desligar


def test_o_inibidor_que_nao_vem_nao_trava_e_fica_no_registro(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(at, "_tomar_o_inibidor", lambda _p: None)
    with at.segurar_o_desligar("x"):
        pass
    leitura, escrita = os.pipe()
    os.close(leitura)
    monkeypatch.setattr(at, "_tomar_o_inibidor", lambda _p: escrita)
    with at.segurar_o_desligar("x"):
        os.fstat(escrita)
    with pytest.raises(OSError):
        os.fstat(escrita)


def test_o_apt_do_ajudante_roda_numa_unidade_de_sistema_propria(tmp_path: Path) -> None:
    """D-1911-A-FILA-ESPERA-A-TOMADA-E-SEGURA-O-DESLIGAR: o apt do ajudante não cai com a sessão."""
    if os.geteuid() == 0:
        pytest.skip("o ajudante como root usa os caminhos de verdade")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    chamadas = tmp_path / "chamadas.log"
    sufixos = tmp_path / "sufixos"
    sufixos.write_text("~hefesto\n", encoding="utf-8")
    sufixos.chmod(0o644)
    dubles = {
        "systemd-run": (
            'out=""; err=""\n'
            'while [ "$1" != "--" ]; do case "$1" in StandardOutput=append:*) '
            'out="${1#StandardOutput=append:}";; StandardError=append:*) '
            'err="${1#StandardError=append:}";; esac; shift; done; shift\n'
            '"$@" >>"$out" 2>>"$err"'),
        "apt-get": 'echo "pmstatus:x:42:instalando"; echo "aviso do apt" >&2; exit 7',
        "apt-mark": "exit 0",
        "dpkg-query": 'printf "curl\\tii \\t8.5\\n"',
    }
    for nome, corpo in dubles.items():
        arq = bin_ / nome
        arq.write_text(f'#!/bin/sh\necho "{nome} $*" >> "{chamadas}"\n{corpo}\n',
                       encoding="utf-8")
        arq.chmod(0o755)
    ambiente = {"PATH": f"{bin_}:{os.environ['PATH']}", "HOME": str(tmp_path),
                "HEFESTO_ATUALIZADOR_CACHE": str(tmp_path / "cache"),
                "HEFESTO_ATUALIZADOR_SUFIXOS": str(sufixos),
                "HEFESTO_ATUALIZADOR_DONO": subprocess.run(
                    ["id", "-un"], capture_output=True, text=True, check=True).stdout.strip(),
                "HEFESTO_ATUALIZADOR_UNIDADE": "1", "TMPDIR": str(tmp_path)}
    feito = subprocess.run(["bash", str(SCRIPT), "apt-instalar", "sistema"], env=ambiente,
                           capture_output=True, text=True, timeout=60, check=False)
    assert feito.returncode == 7, feito.stderr
    assert "pmstatus:x:42:instalando" in feito.stdout
    assert "aviso do apt" in feito.stderr
    lidas = chamadas.read_text(encoding="utf-8").splitlines()
    unidade = [linha for linha in lidas if linha.startswith("systemd-run ")]
    assert unidade and all(" -- apt-get " in linha for linha in unidade), lidas
    assert "-E DEBIAN_FRONTEND=noninteractive" in unidade[-1]
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("tmp.")]
