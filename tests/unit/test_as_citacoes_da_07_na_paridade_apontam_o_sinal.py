"""As citações da 07 na paridade apontam o sinal (AS-CITACOES-DA-07-NA-PARIDADE-APONTAM-O-SINAL-01).

A célula `html_onde` de `docs/data/paridade-gtk-html.csv` guarda `a07_lancadores.py:N`. O
`validar-citacoes-de-linha.py` só prova que a linha existe, e uma varredura em massa deixou doze de
treze citações longe do próprio `sinal`, com tudo verde. O
`conferir-as-citacoes-da-07-na-paridade.py` pergunta pelo sinal da MESMA linha do CSV: ele está a
até três linhas da linha citada?
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "conferir-as-citacoes-da-07-na-paridade.py"
CSV = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
A07 = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes" / "a07_lancadores.py"
A07_CITADO = "interface/pacotes/a07_lancadores.py"


def _roda(csv: Path = CSV, arquivo: Path = A07) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--conferir", "--csv", str(csv), "--arquivo", str(arquivo)],
        capture_output=True, text=True, encoding="utf-8", check=False)


def _linha_do_sinal(sinal: str) -> int:
    for n, texto in enumerate(A07.read_text(encoding="utf-8").split("\n"), start=1):
        if sinal in texto:
            return n
    raise AssertionError(f"{sinal} não está no a07")


def test_toda_citacao_da_07_na_paridade_cai_perto_do_sinal() -> None:
    feito = _roda()
    assert feito.returncode == 0, feito.stdout + feito.stderr
    conferidas = int(feito.stdout.rsplit(" de ", 1)[1].split()[0])
    assert conferidas >= 5, "a régua não pode passar vazia: o CSV perdeu as citações da 07?"


def test_o_numero_velho_reprova(tmp_path: Path) -> None:
    """A mordida: devolver uma citação ao número de antes da cura, e a régua acusa a linha dela."""
    texto = CSV.read_text(encoding="utf-8")
    certo = f"{A07_CITADO}:{_linha_do_sinal('pastas = jl.pastas_de_atalhos()')}"
    assert texto.count(certo) == 1, certo
    velho = tmp_path / "paridade.csv"
    velho.write_text(texto.replace(certo, f"{A07_CITADO}:184"), encoding="utf-8")
    feito = _roda(velho)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "Achar Heroic" in feito.stdout and "pastas_de_atalhos" in feito.stdout


def test_o_codigo_que_anda_reprova_a_citacao_parada(tmp_path: Path) -> None:
    """Dez linhas a mais no topo do arquivo e nenhuma citação se mexe: o desvio é pego."""
    andou = tmp_path / "a07_lancadores.py"
    andou.write_text("\n" * 10 + A07.read_text(encoding="utf-8"), encoding="utf-8")
    feito = _roda(arquivo=andou)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "longe-do-sinal" in feito.stdout


def test_citar_a_07_numa_linha_cujo_sinal_mora_em_outro_arquivo_reprova(tmp_path: Path) -> None:
    cabecalho = ("aba,feature,veredito,sinal,sinal_espera,sinal_escopo,gtk_onde,html_onde,"
                 "gtk_faz,html_faz,porque\n")
    linha = f"07-lancadores,uma,IGUAL,SINAL_DE_OUTRO,PRESENTE,x.py,,{A07_CITADO}:10,a,b,c\n"
    outro = tmp_path / "p.csv"
    outro.write_text(cabecalho + linha, encoding="utf-8")
    feito = _roda(outro)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "sem-sinal" in feito.stdout
