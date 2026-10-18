#!/usr/bin/env python3
"""A FORMA DA 07 NÃO DEPENDE DO ESTADO — aba 07, Lançadores (Experimental no desenho do todo).

A régua mora no gerador (`interface/aba07.py`, `_confere_a_forma`), e roda a cada `import aba07`
sem tocar a bancada: o gerador só escreve dentro do `if __name__ == "__main__"`. Este teste a
morde pela porta do import, como o `test_a_palavra_do_transporte_tem_um_dono_so`.

17/10/2026: o cartão por lançador (e as réguas `_INSTAVEIS` e `_SEM_OBRIGATORIOS` do endereço por
selo) saiu do desenho com o cartão, e a fila do todo o substituiu: sete lançadores, e em todos os
mesmos três botões (Identificar, Criar o perfil de um jogo, Configurar), achado ou não. O endereço
`data-campo` por estado volta a ter régua quando o pacote passar a pintar a fila (segunda
passagem); até lá o par pacote e página publicada é medido por
`test_a_aba_lancadores_diz_a_verdade`.

O DEFEITO DE ORIGEM (07/09/2026), que continua valendo para a aba por controle: a página mostra
um número de cartões e o daemon manda outro, porque um ramo largou o endereço. Esta aba não tem
cartão por controle: `data-controle` não aparece no gerador nem na página publicada.
"""
import io
import pathlib
import subprocess
import sys
import tokenize

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

VELHA = "endereço(s) que o pacote pinta não existem no"


def _importar(veneno: str) -> subprocess.CompletedProcess[str]:
    """Importa o gerador com `fila_html` envenenada, e devolve o que ele disse."""
    programa = (
        "import desenho_da_experimental as exp\n"
        "_orig = exp.fila_html\n"
        f"{veneno}\n"
        "exp.fila_html = quebrada\n"
        "import aba07\n"
    )
    return subprocess.run([sys.executable, "-c", programa],
                          capture_output=True, text=True,
                          cwd=str(INTERFACE), check=False)


def test_a_pagina_de_hoje_passa():
    """Sem veneno o gerador importa limpo — a régua não reprova o que está certo."""
    r = subprocess.run([sys.executable, "-c", "import aba07"],
                       capture_output=True, text=True,
                       cwd=str(INTERFACE), check=False)
    assert r.returncode == 0, (
        "o gerador da aba 07 reprovou a si mesmo sem veneno nenhum:\n"
        f"{r.stderr}{r.stdout}")


def test_a_regua_morde_a_fila_que_perde_um_botao():
    """17/10/2026: o cartão deu lugar à fila do desenho do todo, com os mesmos três botões em
    todo lançador, achado ou não. A régua da forma vive no gerador e roda a cada `import aba07`."""
    r = _importar(
        "def quebrada(f):\n"
        "    h = _orig(f)\n"
        "    if f.chave == 'heroic':\n"
        "        h = h.replace('data-gesto=\"identificar-lancador\"', 'data-x=\"1\"')\n"
        "    return h")
    assert r.returncode != 0, (
        "tirei o gesto do Heroic e o gerador passou — a régua da fila não mede nada")
    assert "lançador sem os 3 botões" in (r.stderr + r.stdout), (
        f"reprovou por outra coisa que não a régua da fila:\n{r.stderr}")


def test_a_regua_morde_o_span_ajuda_que_volta():
    r = _importar(
        "def quebrada(f):\n"
        "    return _orig(f) + '<span class=\"ajuda\">?</span>'")
    assert r.returncode != 0, "devolvi o `span.ajuda` à fila e o gerador passou"
    assert "span.ajuda" in (r.stderr + r.stdout), r.stderr


def test_esta_aba_nao_tem_cartao_por_controle():
    """A evidência de por que a régua daqui não é a das abas 01-06 e 08."""
    pasta = INTERFACE / "paginas"  # (noqa-acento) a PASTA
    pagina = (pasta / "07-lancadores.html").read_text(encoding="utf-8")
    assert 'data-controle="p' not in pagina, (
        "a página 07 ganhou cartão por controle — ver o docstring")

    fonte = (INTERFACE / "aba07.py").read_text(encoding="utf-8")
    sem_prosa = "".join(
        "" if tok.type == tokenize.COMMENT else tok.string
        for tok in tokenize.generate_tokens(io.StringIO(fonte).readline))
    assert "data-controle" not in sem_prosa, (
        "o gerador da aba 07 passou a emitir `data-controle` — ver o docstring")
