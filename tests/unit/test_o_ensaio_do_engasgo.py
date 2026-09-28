"""O ensaio do engasgo — `scripts/ensaio-do-engasgo.sh`, a ferramenta dos ensaios 1 a 4.

O-ENGASGO-SE-CURA-PELO-QUE-CHEGA-AO-JOGO-01, §4: cada ensaio é a mesma fase,
jogada por ela, e o script grava por minuto os picos, o `allocstall`, o `NVRM` e
o `Output queue is full`. O MangoHud entra pela Steam (pedido dela, 27/09:
*«usa o mango hud na steam»*), pelo dono das Opções de Inicialização, e sai do
mesmo jeito — conferido. <!-- noqa-acento: citação literal dela -->

Tudo aqui roda num lar de mentira, com um dono de mentira: a régua nunca fala
com a Steam de quem a roda.

AS MORDIDAS: faça o `devolver` pular o `devolver_a_tabela` e
`test_preparar_e_devolver_deixam_a_opcao_como_era` reprova; tire o filtro de
hora do `resumo` e `test_o_resumo_conta_por_minuto_so_o_que_e_da_volta`
reprova; faça o `cabe` do `resumo` imprimir o número sempre e
`test_o_que_nao_foi_medido_sai_como_traco_e_nunca_como_zero` reprova.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ENSAIO = RAIZ / "scripts" / "ensaio-do-engasgo.sh"

#: O dono de mentira: a tabela é um JSON; `--aplicar` sai 3 (a Steam aberta)
#: quando o lar tem o arquivo `steam-aberta`.
_DONO = '''#!/usr/bin/env python3
import json, sys
from pathlib import Path
casa = Path(__file__).parent
tabela = casa / "tabela.json"
t = json.loads(tabela.read_text()) if tabela.exists() else {}
a = sys.argv[1:]
with (casa / "chamadas.log").open("a") as f:
    f.write(" ".join(a) + "\\n")
if a[0] == "--json":
    print(json.dumps(t))
elif a[0] == "--definir":
    t[a[1]] = a[2]
elif a[0] == "--tirar":
    t.pop(a[1], None)
elif a[0] == "--aplicar":
    sys.exit(3 if (casa / "steam-aberta").exists() else 0)
tabela.write_text(json.dumps(t))
'''


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    dono = tmp_path / "dono.py"
    dono.write_text(_DONO, encoding="utf-8")
    dono.chmod(0o755)
    assert not str(tmp_path).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    return tmp_path


def _rodar(lar: Path, *args: str) -> subprocess.CompletedProcess[str]:
    ambiente = {
        "HOME": str(lar / "casa"),
        "XDG_STATE_HOME": str(lar / "estado"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HEFESTO_OPCOES_POR_JOGO": str(lar / "dono.py"),
        "LANG": "C.UTF-8",
    }
    return subprocess.run(["bash", str(ENSAIO), *args], env=ambiente,
                          capture_output=True, text=True, timeout=120, check=False)


def _tabela(lar: Path) -> dict[str, str]:
    return json.loads((lar / "tabela.json").read_text()) if (lar / "tabela.json").exists() else {}


def _pasta(lar: Path) -> Path:
    return lar / "estado" / "hefesto-dualsense4unix" / "ensaio-do-engasgo"


# ---------------------------------------------------------------------------
# 1. A OPÇÃO DO JOGO VAI E VOLTA PELO DONO
# ---------------------------------------------------------------------------


def test_preparar_e_devolver_deixam_a_opcao_como_era(lar: Path) -> None:
    original = "VKD3D_CONFIG=no_upload_hvv %command%"
    (lar / "tabela.json").write_text(json.dumps({"3357650": original}))
    r = _rodar(lar, "preparar", "3357650")
    assert r.returncode == 0, r.stderr
    opcao = _tabela(lar)["3357650"]
    assert opcao.startswith(
        "VKD3D_CONFIG=no_upload_hvv MANGOHUD=1 MANGOHUD_CONFIG=no_display=1,"), opcao
    assert f"output_folder={_pasta(lar) / 'mangohud'} %command%" in opcao, opcao
    assert opcao.count("%command%") == 1

    r = _rodar(lar, "devolver")
    assert r.returncode == 0, r.stderr
    assert _tabela(lar) == {"3357650": original}
    assert not (_pasta(lar) / "antes.json").exists()


def test_o_jogo_fora_da_tabela_sai_dela_no_devolver(lar: Path) -> None:
    assert _rodar(lar, "preparar", "1599660").returncode == 0
    assert _tabela(lar)["1599660"].startswith("MANGOHUD=1 ")
    assert _rodar(lar, "devolver").returncode == 0
    assert _tabela(lar) == {}


def test_com_a_steam_aberta_o_preparar_recusa_e_nao_deixa_rastro(lar: Path) -> None:
    (lar / "tabela.json").write_text(json.dumps({"3357650": "X=1 %command%"}))
    (lar / "steam-aberta").touch()
    r = _rodar(lar, "preparar", "3357650")
    assert r.returncode != 0
    assert "Steam" in r.stderr
    assert _tabela(lar) == {"3357650": "X=1 %command%"}
    assert not (_pasta(lar) / "antes.json").exists()


def test_sem_preparar_a_volta_recusa(lar: Path) -> None:
    r = _rodar(lar, "volta", "um", "1")
    assert r.returncode != 0 and "preparar" in r.stderr


# ---------------------------------------------------------------------------
# 2. A VOLTA E O RESUMO
# ---------------------------------------------------------------------------


def test_a_volta_grava_a_memoria_e_so_le_a_maquina(lar: Path) -> None:
    assert _rodar(lar, "preparar", "1599660").returncode == 0
    r = _rodar(lar, "volta", "um", "0.03")
    assert r.returncode == 0, r.stderr
    volta = _pasta(lar) / "voltas" / "um"
    amostras = [json.loads(x) for x in (volta / "memoria.jsonl").read_text().splitlines()]
    assert len(amostras) >= 2
    assert {"ts", "vmstat", "ordem_7_a_10"} <= set(amostras[0])
    assert (volta / "kernel.txt").exists()
    assert _rodar(lar, "volta", "um", "0.01").returncode != 0, "a volta repetida sobrescreveria"


def test_o_resumo_conta_por_minuto_so_o_que_e_da_volta(lar: Path) -> None:
    """Os quadros de antes da volta (o menu, o carregamento) ficam fora da conta."""
    voltas = _pasta(lar) / "voltas"
    volta = voltas / "sackboy-ligado"
    volta.mkdir(parents=True)
    comeco = datetime(2026, 9, 28, 14, 0, 0)
    (volta / "inicio").write_text(comeco.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    t0 = comeco.timestamp()
    amostras = [
        {"ts": t0 + 5, "vmstat": {"allocstall_normal": 10, "compact_stall": 3}, "ordem_7_a_10": 40},
        {"ts": t0 + 65, "vmstat": {"allocstall_normal": 12, "compact_stall": 3}, "ordem_7_a_10": 0},
        {"ts": t0 + 119, "vmstat": {"allocstall_normal": 12, "compact_stall": 5},
         "ordem_7_a_10": 7},
    ]
    (volta / "memoria.jsonl").write_text("".join(json.dumps(a) + "\n" for a in amostras))
    # O jogo abriu 30 s antes da volta: os 30 primeiros segundos ficam fora.
    partida = datetime.fromtimestamp(t0 - 30)
    linhas = ["os,cpu", "x,y", "fps,frametime,cpu_load,elapsed", "0,49000000,0,0"]
    for segundo, ms in ((10, 16.7), (20, 80.0), (40, 16.7), (50, 40.0), (70, 60.0), (95, 16.7),
                        (150, 90.0), (200, 90.0)):
        linhas.append(f"60,{ms},1,{int(segundo * 1e9)}")
    (volta / f"Jogo_{partida:%Y-%m-%d_%H-%M-%S}.csv").write_text("\n".join(linhas) + "\n")
    (volta / "kernel.txt").write_text(
        "2026-09-28T14:01:03-0300 maquina kernel: NVRM: Out of memory\n"
        "2026-09-28T14:01:09-0300 maquina kernel: sony 0005:054C:0CE6.0001: Output queue is full\n")
    r = _rodar(lar, "resumo")
    assert r.returncode == 0, r.stderr
    saida = r.stdout.splitlines()
    assert saida[0] == "== sackboy-ligado", saida
    # 14:00: os quadros dos segundos 40, 50 e 70 (16,7, 40 e 60 ms) e uma
    # amostra só — a ordem é retrato e vale, a diferença do `allocstall` não
    # existe ainda, e sai «-»; 14:01: o do segundo 95, duas amostras, e o
    # kernel. O de 150 s passa da última amostra, e sai.
    assert saida[1] == ("14:00 quadros=3 >33ms=2 >50ms=1 allocstall=- compact_stall=- "
                        "ordem7-10_min=40 NVRM=0 fila_cheia=0"), saida
    assert saida[2] == ("14:01 quadros=1 >33ms=0 >50ms=0 allocstall=2 compact_stall=2 "
                        "ordem7-10_min=0 NVRM=1 fila_cheia=1"), saida
    assert len(saida) == 3, saida


def test_o_que_nao_foi_medido_sai_como_traco_e_nunca_como_zero(lar: Path) -> None:
    """Sem o CSV do MangoHud e sem o diário do kernel, a volta não tem pico medido.

    O MangoHud pode não estar instalado, ou a opção pode não ter chegado ao
    jogo; o diário do kernel pode estar fechado para quem roda. Um «>50ms=0»
    ali se leria como a volta limpa — e o ensaio 1 decide o botão por essa
    conta. MORDIDA: faça o `cabe` devolver sempre o número e esta régua reprova.
    """
    volta = _pasta(lar) / "voltas" / "sem-mangohud"
    volta.mkdir(parents=True)
    comeco = datetime(2026, 9, 28, 15, 0, 0)
    (volta / "inicio").write_text(comeco.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    t0 = comeco.timestamp()
    amostras = [
        {"ts": t0 + 5, "vmstat": {"allocstall_normal": 1, "compact_stall": 0}, "ordem_7_a_10": 9},
        {"ts": t0 + 15, "vmstat": {"allocstall_normal": 4, "compact_stall": 0}, "ordem_7_a_10": 8},
    ]
    (volta / "memoria.jsonl").write_text("".join(json.dumps(a) + "\n" for a in amostras))
    (volta / "kernel.txt").write_text("")
    (volta / "kernel-sem-acesso").touch()
    r = _rodar(lar, "resumo")
    assert r.returncode == 0, r.stderr
    saida = r.stdout.splitlines()
    assert saida[0] == (
        "== sem-mangohud (sem quadros do MangoHud; sem acesso ao diário do kernel)"), saida
    assert saida[1] == ("15:00 quadros=- >33ms=- >50ms=- allocstall=3 compact_stall=0 "
                        "ordem7-10_min=8 NVRM=- fila_cheia=-"), saida


def test_o_csv_que_o_jogo_fechou_depois_vai_para_a_volta_certa(lar: Path) -> None:
    """O MangoHud pode fechar o arquivo só quando o jogo sai."""
    assert _rodar(lar, "preparar", "1599660").returncode == 0
    voltas = _pasta(lar) / "voltas"
    for nome, atras in (("a", 600), ("b", 60)):
        (voltas / nome).mkdir(parents=True)
        inicio = datetime.fromtimestamp(time.time() - atras)
        (voltas / nome / "inicio").write_text(f"{inicio:%Y-%m-%d %H:%M:%S}\n")
    csv = _pasta(lar) / "mangohud" / "Jogo_2026-09-28_14-00-00.csv"
    csv.write_text("fps,frametime,elapsed\n")
    resumo_ = _pasta(lar) / "mangohud" / "Jogo_2026-09-28_14-00-00_summary.csv"
    resumo_.write_text("x\n")
    assert _rodar(lar, "resumo").returncode == 0
    assert (voltas / "b" / csv.name).exists()
    assert resumo_.exists(), "o resumo do próprio MangoHud não é quadro"
