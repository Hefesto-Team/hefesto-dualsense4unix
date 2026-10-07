"""A régua dos contratos de fora morde: ponto de contato sem linha reprova, e a catraca só desce."""

from __future__ import annotations

import csv
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = RAIZ / "scripts" / "check_os_contratos_de_fora.py"
_spec = importlib.util.spec_from_file_location("check_os_contratos_de_fora", _SCRIPT)
assert _spec and _spec.loader
regua = importlib.util.module_from_spec(_spec)
sys.modules["check_os_contratos_de_fora"] = regua
_spec.loader.exec_module(regua)

PACOTE = "src/hefesto_dualsense4unix/integrations"
DOCTOR = '''"""doctor de mentira."""
Contrato(id="bluez-dbus", dono="bluez")
'''


def _arvore(tmp_path: Path, fontes: dict[str, str], linhas: list[dict[str, str]]) -> Path:
    for rel, texto in {f"{PACOTE}/contratos_de_fora.py": DOCTOR, **fontes}.items():
        destino = tmp_path / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
    (tmp_path / "docs/data").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "docs/data/contratos-de-fora.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        w = csv.DictWriter(fh, fieldnames=regua.COLUNAS, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    return tmp_path


def _linha(arquivo: str, alvo: str, **mais: str) -> dict[str, str]:
    base = {
        "dono": "bluez",
        "arquivo": arquivo,
        "alvo": alvo,
        "onde": "*",
        "porta": "oficial",
        "pergunta": "capacidade",
        "forma": "converge",
        "o_que_quebra_se_mudar": "o contato some",
        "como_o_doctor_ve": "contrato:bluez-dbus",
        "motivo": "",
        "sprint_filha": "",
    }
    base.update(mais)
    return base


LE_O_BOND = (
    'from pathlib import Path\n\ndef ler():\n    return Path("/var/lib/bluetooth").exists()\n'
)
CHAMA_BUSCTL = 'import subprocess\n\ndef ver():\n    return subprocess.run(["busctl", "tree"])\n'


def test_o_censo_real_diz_o_que_o_codigo_faz():
    assert regua.julgar(RAIZ) == []


def test_leitura_nova_de_var_lib_bluetooth_sem_linha_reprova(tmp_path):
    arq = f"{PACOTE}/novo.py"
    raiz = _arvore(tmp_path, {arq: LE_O_BOND}, [])
    queixas = regua.julgar(raiz)
    assert any("SEM LINHA" in q and "/var/lib/bluetooth" in q and arq in q for q in queixas)


def test_com_a_linha_a_mesma_leitura_passa(tmp_path):
    arq = f"{PACOTE}/novo.py"
    linha = _linha(
        arq,
        "path:/var/lib/bluetooth",
        porta="interna",
        forma="comando",
        motivo="o BlueZ não expõe o bond",
        sprint_filha="QUALQUER-01",
    )
    raiz = _arvore(tmp_path, {arq: LE_O_BOND}, [linha])
    assert regua.julgar(raiz) == []


def test_linha_morta_e_linha_duplicada_reprovam(tmp_path):
    arq = f"{PACOTE}/novo.py"
    morta = _linha(arq, "cmd:pactl")
    raiz = _arvore(
        tmp_path, {arq: CHAMA_BUSCTL}, [_linha(arq, "cmd:busctl"), _linha(arq, "cmd:busctl"), morta]
    )
    queixas = regua.julgar(raiz)
    assert any("DUPLICADA" in q for q in queixas)
    assert any("MORTA" in q and "cmd:pactl" in q for q in queixas)


def test_linha_fragil_sem_motivo_ou_sem_filha_reprova(tmp_path):
    arq = f"{PACOTE}/novo.py"
    linha = _linha(arq, "path:/var/lib/bluetooth", porta="interna")
    raiz = _arvore(tmp_path, {arq: LE_O_BOND}, [linha])
    queixas = regua.julgar(raiz)
    assert any("sem `motivo`" in q for q in queixas)
    assert any("sem `sprint_filha`" in q for q in queixas)


def test_contrato_que_o_doctor_nao_declara_reprova(tmp_path):
    arq = f"{PACOTE}/novo.py"
    raiz = _arvore(
        tmp_path,
        {arq: CHAMA_BUSCTL},
        [_linha(arq, "cmd:busctl", como_o_doctor_ve="contrato:que-nao-existe")],
    )
    assert any("que-nao-existe" in q for q in regua.julgar(raiz))


def test_comentario_e_docstring_nao_contam(tmp_path):
    arq = f"{PACOTE}/calado.py"
    fonte = '"""Fala de /var/lib/bluetooth e de busctl."""\n# /var/lib/bluetooth\nX = 1\n'
    raiz = _arvore(tmp_path, {arq: fonte}, [])
    assert regua.julgar(raiz) == []


def test_a_catraca_so_desce(tmp_path, capsys):
    arq = f"{PACOTE}/novo.py"
    frag = _linha(arq, "path:/var/lib/bluetooth", porta="interna", motivo="m", sprint_filha="X-01")
    raiz = _arvore(tmp_path, {arq: LE_O_BOND}, [frag])
    # sem sprints no tmp, a filha não se confere (clone limpo); o piso nasce em 1.
    assert regua.main(["--raiz", str(raiz), "--aceitar", regua.FRAGEIS]) == 0
    assert regua.main(["--raiz", str(raiz)]) == 0
    # uma segunda leitura frágil SOBE o número: reprova.
    outro = f"{PACOTE}/outro.py"
    (raiz / outro).write_text(LE_O_BOND, encoding="utf-8")
    frag2 = _linha(
        outro, "path:/var/lib/bluetooth", porta="interna", motivo="m", sprint_filha="X-01"
    )
    _arvore(raiz, {outro: LE_O_BOND}, [frag, frag2])
    capsys.readouterr()
    assert regua.main(["--raiz", str(raiz)]) == 1
    # a cura (a leitura vira porta oficial) faz o piso descer sozinho.
    ok = _linha(arq, "path:/var/lib/bluetooth", motivo="", sprint_filha="")
    _arvore(raiz, {outro: "X = 1\n"}, [ok])
    assert regua.main(["--raiz", str(raiz)]) == 0
    assert '"piso": 0' in (raiz / regua.CADERNO).read_text(encoding="utf-8")


def test_universo_vazio_nao_e_verde(tmp_path):
    raiz = _arvore(tmp_path, {}, [])
    assert regua.main(["--raiz", str(raiz)]) != 0


@pytest.mark.skipif(not (RAIZ / "scripts/portoes.sh").exists(), reason="sem portoes.sh")
def test_o_portao_esta_na_lista():
    texto = (RAIZ / "scripts/portoes.sh").read_text(encoding="utf-8")
    assert "rapido|contratos-de-fora|py|scripts/check_os_contratos_de_fora.py" in texto
    assert "check_os_contratos_de_fora.py" in (RAIZ / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )
    assert shutil.which("python3")
