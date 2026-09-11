"""Z6-05 — a regra 16 (`causa-nao-declarada`) e o domínio novo de
`*_por_que_nao_aciona`.

A mordida 1 da sprint: "Esvaziar uma célula `*_por_que_nao_aciona` numa linha
com `aciona=não` e `de_onde_sei=medido` → reprova."

Segue o molde de `test_check_paridade_transporte.py`: CSV de mentira, CLI de
verdade, subprocesso — nunca importa o script (a razão está no cabeçalho
daquele arquivo).
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

def _specs_de(raiz: Path) -> Path:
    """O caminho do `specs.html` numa árvore de brinquedo, com a pasta criada.

    A página mudou da raiz para `html/` em 25/08/2026, e as árvores de teste
    passaram a precisar da pasta ANTES do `write_text` — senão o erro é um
    `FileNotFoundError` de diretório, que não diz nada sobre o que se testa.

    Existe como função, e não como duas linhas repetidas em cada caso, pelo
    motivo de sempre nesta casa: no dia em que o caminho mudar de novo, muda
    num lugar só.
    """
    pasta = raiz / "html"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "specs.html"


RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_paridade_transporte.py"

CABECALHO = [
    "chave",
    "controle",
    "existe",
    "cabo_aciona",
    "radio_aciona",
    "cabo_de_onde_sei",
    "radio_de_onde_sei",
    "cabo_por_que_nao_aciona",
    "radio_por_que_nao_aciona",
    "cabo_canal",
    "radio_canal",
    "cabo_ate_onde_foi",
    "radio_ate_onde_foi",
    "ponte_alcanca",
    "teste_que_morde",
    "provado_em",
    "validade_dias",
    "assimetria_declarada",
    "id",
]

TESTE_FALSO = '''\
"""Arquivo de teste de mentira, só para o índice por AST ter o que ler."""


def test_a_lightbar_acende():
    assert True
'''


def escreve_mapa(caminho: Path, linhas: list[dict[str, str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in CABECALHO})


def monta_arvore(tmp_path: Path, linhas: list[dict[str, str]]) -> Path:
    caminho_csv = tmp_path / "docs" / "data" / "mapa-controles.csv"
    escreve_mapa(caminho_csv, linhas)
    pasta_de_testes = tmp_path / "tests" / "unit"
    pasta_de_testes.mkdir(parents=True, exist_ok=True)
    (pasta_de_testes / "test_exemplo.py").write_text(TESTE_FALSO, encoding="utf-8")
    publicados = [linha.get("id", "") for linha in linhas]
    _specs_de(tmp_path).write_text(
        "<html><body>" + " ".join(publicados) + "</body></html>", encoding="utf-8"
    )
    return caminho_csv


def rodar(caminho_csv: Path, raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--csv", str(caminho_csv)],
        capture_output=True,
        text=True,
        check=False,
    )


def _linha(**mudancas: str) -> dict[str, str]:
    base = {
        "chave": "identidade.cor_do_aparelho",
        "controle": "dualsense",
        "existe": "tem",
        "cabo_aciona": "sim",
        "radio_aciona": "não",
        "cabo_de_onde_sei": "medido",
        "radio_de_onde_sei": "medido",
        "radio_por_que_nao_aciona": "o-aparelho-recusa",
        "cabo_canal": "hidraw",
        "teste_que_morde": "tests/unit/test_exemplo.py::test_a_lightbar_acende",
        "id": "identidade.cor_do_aparelho@dualsense",
    }
    base.update(mudancas)
    return base


def test_causa_preenchida_passa(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [_linha()])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "causa-nao-declarada" not in processo.stdout


def test_causa_vazia_com_aciona_nao_medido_reprova(tmp_path: Path) -> None:
    """MORDIDA 1 de Z6-05."""
    caminho = monta_arvore(tmp_path, [_linha(radio_por_que_nao_aciona="")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1
    assert "causa-nao-declarada" in processo.stdout
    assert "identidade.cor_do_aparelho@dualsense" in processo.stdout


def test_a_causa_nao_depende_do_de_onde_sei(tmp_path: Path) -> None:
    """Todo `aciona = não` diz por quê — inclusive o que ninguém mediu.

    **O PORTÃO VENCEU ESTE TESTE, e a data está no dono.** Ele dizia *"só
    `de_onde_sei = medido` cobra causa — inferência ainda é dívida geral"*, e
    em 06/09/2026 a regra 16 perdeu essa metade de propósito:
    `check_paridade_transporte` declara, no comentário do próprio `if`, que
    *"ELA VALIA SÓ PARA O `medido` ATÉ 06/09/2026, e era essa metade que
    faltava"*. A razão medida está lá: um `não` de célula NÃO medida era o
    mais ambíguo de todos — podia querer dizer *"o aparelho recusa"* ou
    *"ninguém olhou"* —, e **foi lendo um desses que o coordenador mandou um
    agente PARAR um passo que funciona.**

    **O QUE SOBROU DA PERGUNTA ANTIGA, e é o que se mede aqui:** o
    `de_onde_sei` responde OUTRA coisa — *como se soube* —, e por isso ele saiu
    da condição em vez de ganhar um segundo valor. Então a régua cobra os DOIS
    sentidos sobre o MESMO `inferido-do-codigo`: com a causa preenchida passa,
    com a causa vazia reprova. Um lado só continuaria a medir um portão que
    não existe mais.

    Para o caso de ninguém ter olhado existe a palavra que o diz —
    `nao-medido` —, e ela não autoriza afirmar que o aparelho não faz.
    """
    inferido = {"radio_de_onde_sei": "inferido-do-codigo"}

    com_causa = monta_arvore(
        tmp_path / "com-causa",
        [_linha(radio_por_que_nao_aciona="nao-medido", **inferido)],
    )
    passou = rodar(com_causa, tmp_path / "com-causa")
    assert "causa-nao-declarada" not in passou.stdout, (
        "a causa declarada num lado inferido reprovou — a regra 16 passou a "
        f"cobrar o `de_onde_sei`, que não é a pergunta dela:\n{passou.stdout}"
    )

    sem_causa = monta_arvore(
        tmp_path / "sem-causa",
        [_linha(radio_por_que_nao_aciona="", **inferido)],
    )
    reprovou = rodar(sem_causa, tmp_path / "sem-causa")
    assert reprovou.returncode == 1
    assert "causa-nao-declarada" in reprovou.stdout, (
        "um `aciona = não` sem causa passou porque o lado era inferido — é a "
        f"metade que a regra 16 ganhou em 06/09/2026:\n{reprovou.stdout}"
    )


def test_valor_o_aparelho_recusa_e_aceito_no_dominio(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [_linha(radio_por_que_nao_aciona="o-aparelho-recusa")])
    processo = rodar(caminho, tmp_path)
    assert "integridade" not in processo.stdout or "por_que_nao_aciona" not in processo.stdout


def test_valor_fora_do_dominio_reprova_por_integridade(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [_linha(radio_por_que_nao_aciona="astrologia")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1
    assert "integridade" in processo.stdout
    assert "por_que_nao_aciona" in processo.stdout
