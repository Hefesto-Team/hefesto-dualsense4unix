#!/usr/bin/env python3
"""A RÉGUA DA RÉGUA: o portão da moldura reprova de verdade.

`scripts/check_a_janela_nao_confessa.py` nasceu em 08/09/2026 porque ela leu na
barra de título do produto instalado::

    Hefesto
    as dez abas, vivas

Este arquivo é a MORDIDA daquele portão, e ele existe porque *"uma régua que só
sabe passar foi o que deixou este defeito chegar aos olhos dela"* — a própria
sprint pediu esta prova, com esta frase.

O QUE ELE PROVA, e o par é o ponto
-----------------------------------
1. Com a moldura de hoje, o portão passa.
2. Com `subtitulo="a onda 5 fechou"` no `hefesto_vivo.py` — a frase que a sprint
   escolheu — ele REPROVA, com `rc=1` e o nome do arquivo na saída.
3. Com o texto ORIGINAL que ela leu (`"as dez abas, vivas"`) ele também reprova,
   e por outra peneira. Sem este terceiro caso a régua poderia estar pegando só
   a palavra `onda` e continuar cega justamente ao defeito que a fez nascer.
4. E com a segunda ocorrência, a que ele achou sozinho na primeira corrida: a
   dica do `.desktop`, que a dock mostra antes de a janela existir.

A MORDIDA É NUMA CÓPIA, e nunca na árvore. O portão lê caminhos relativos à raiz
do repositório, então cada caso monta uma árvore de mentira num diretório
temporário — os arquivos que ele lê, e mais nada. Uma régua que edita o produto
para se provar já quebrou a mesa dela uma vez.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_janela_nao_confessa.py"

#: O que o portão lê. Copiar só isto mantém a árvore de mentira pequena e diz,
#: por construção, qual é a superfície dele — se ele passar a ler outra coisa,
#: este teste quebra e alguém tem de vir atualizar a lista, que é o que se quer.
O_QUE_ELE_LE = (
    "scripts/check_a_janela_nao_confessa.py",
    "scripts/check_a_tela_nao_confessa.py",
    "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py",
    # A MOLDURA DO PRODUTO
    "src/hefesto_dualsense4unix/interface/hefesto_vivo.py",
    "src/hefesto_dualsense4unix/gui/ponte_da_tela.py",
    "src/hefesto_dualsense4unix/app/tray.py",
    "src/hefesto_dualsense4unix/app/compact_window.py",
    "src/hefesto_dualsense4unix/utils/identidade.py",
    "packaging/hefesto-dualsense4unix.desktop",
    "assets/hefesto-dualsense4unix.service",
    # OS PILOTOS DE BANCADA, que ele LÊ para imprimir a isenção com o texto de
    # hoje. Eles entram na cópia porque o portão PARA se um deles sumir — e
    # parar é o que se quer: uma isenção apontando para arquivo que não existe
    # isenta nada, e o vermelho que ela deveria causar não acontece.
    "src/hefesto_dualsense4unix/interface/controles_vivos.py",
    "src/hefesto_dualsense4unix/interface/jogar_vivo.py",
    "src/hefesto_dualsense4unix/interface/conexoes_vivas.py",
    "src/hefesto_dualsense4unix/interface/sistema_viva.py",
    "src/hefesto_dualsense4unix/interface/perfis_vivos.py",
    "src/hefesto_dualsense4unix/interface/ver.py",
)


def _arvore_de_mentira(destino: pathlib.Path) -> pathlib.Path:
    for rel in O_QUE_ELE_LE:
        origem = RAIZ / rel
        assert origem.is_file(), (
            f"{rel} não existe — a superfície do portão mudou, e esta régua "
            f"está medindo uma árvore que não é a dele")
        alvo = destino / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
    return destino


def _rodar(raiz: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(raiz / "scripts" / "check_a_janela_nao_confessa.py")],
        capture_output=True, text=True, cwd=raiz)


@pytest.fixture
def arvore(tmp_path: pathlib.Path) -> pathlib.Path:
    return _arvore_de_mentira(tmp_path / "casa")


def test_a_moldura_de_hoje_passa(arvore: pathlib.Path) -> None:
    """Com o que está na árvore agora, o portão fecha verde."""
    r = _rodar(arvore)
    assert r.returncode == 0, (
        f"o portão da moldura reprovou a árvore de hoje:\n{r.stdout}\n{r.stderr}")
    assert "OK:" in r.stdout


@pytest.mark.parametrize(
    "frase, peneira",
    [
        # a que a sprint escolheu para a mordida
        ("a onda 5 fechou", "a língua da obra"),
        # a que ELA leu na barra de título do produto instalado
        ("as dez abas, vivas", "o apelido que esta casa deu ao piloto"),
        # a família que a conferência já proíbe no corpo das dez páginas
        ("montado em 39fa440d", "um hash de commit"),
        # a palavra que ela baniu da tela em 06/09 — lida do dono, não copiada
        ("a mesa de verdade", "palavra que ela baniu da tela"),
        # a forma de confissão, emprestada do irmão `check_a_tela_nao_confessa`
        ("o Hefesto ainda não lê tudo", "forma de confissão"),
    ],
)
def test_o_subtitulo_que_fala_a_lingua_de_dentro_reprova(
        arvore: pathlib.Path, frase: str, peneira: str) -> None:
    """Cada peneira do portão morde, e o vermelho DIZ qual delas foi.

    O `parametrize` cobre as quatro peneiras uma a uma de propósito: um caso só,
    com uma frase que casasse em duas, deixaria as outras podendo estar mortas
    sem ninguém ver — que é como um portão passa a dar verde sobre nada.
    """
    alvo = arvore / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
    texto = alvo.read_text(encoding="utf-8")
    marca = "            oculta=args.oculta,\n"
    assert texto.count(marca) == 1, (
        "não achei onde a janela é montada no `hefesto_vivo.py` — a mordida "
        "precisa pousar na chamada de verdade, senão ela não prova nada")
    alvo.write_text(
        texto.replace(marca, marca + f'            subtitulo="{frase}",\n'),
        encoding="utf-8")

    r = _rodar(arvore)
    assert r.returncode == 1, (
        f"o portão PASSOU com `subtitulo={frase!r}` na moldura do produto.\n"
        f"{r.stdout}\n{r.stderr}")
    assert "hefesto_vivo.py" in r.stdout, r.stdout
    assert peneira in r.stdout, (
        f"o portão reprovou, mas não pela peneira esperada ({peneira}):\n{r.stdout}")


def test_a_dica_do_desktop_tambem_e_medida(arvore: pathlib.Path) -> None:
    """A segunda ocorrência, que o portão achou sozinho na primeira corrida.

    O `.desktop` é o que a dock e o menu do sistema mostram ANTES de a janela
    existir. Ele dizia *"Gerenciador de DualSense para Linux. As dez abas, com o
    dado do aparelho."* — o mesmo apelido da casa que ela leu na barra de
    título, num lugar que nenhuma régua olhava.
    """
    alvo = arvore / "packaging/hefesto-dualsense4unix.desktop"
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    achou = False
    for i, linha in enumerate(linhas):
        if linha.startswith("Comment="):
            linhas[i] = "Comment=Gerenciador de DualSense para Linux. As dez abas."
            achou = True
    assert achou, "o `.desktop` ficou sem `Comment=` — o alvo desta mordida sumiu"
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    r = _rodar(arvore)
    assert r.returncode == 1, (
        f"o portão PASSOU com o apelido da casa na dica do `.desktop`:\n{r.stdout}")
    assert ".desktop" in r.stdout, r.stdout


def test_a_isencao_da_bancada_e_lida_e_nao_digitada(arvore: pathlib.Path) -> None:
    """O texto dos pilotos isentos sai do ARQUIVO, e a isenção não pode emudecer.

    DUAS METADES, e a segunda é o ponto:

    1. o que a régua imprime tem de ser o que o arquivo diz HOJE — troque o
       subtítulo de um piloto de bancada e a saída acompanha. Uma lista com as
       frases DIGITADAS envelheceria calada, que é a forma de instrumento falso
       que esta casa mais pagou: *a régua digitava o que devia LER*;
    2. um piloto isento que perca o texto de moldura PARA o portão. Isenção que
       isenta nada é pior que isenção nenhuma — o vermelho que ela deveria
       causar simplesmente não acontece.
    """
    alvo = arvore / "src/hefesto_dualsense4unix/interface/perfis_vivos.py"
    texto = alvo.read_text(encoding="utf-8")
    assert 'subtitulo="Perfis — os do disco"' in texto, (
        "o piloto de bancada dos perfis mudou de subtítulo — esta régua está "
        "medindo uma árvore que não é a dele")

    # 1. o texto acompanha o arquivo
    alvo.write_text(
        texto.replace('subtitulo="Perfis — os do disco"',
                      'subtitulo="Perfis — a leva sete"'),
        encoding="utf-8")
    r = _rodar(arvore)
    assert r.returncode == 0, (
        f"a bancada é ISENTA: mudar o subtítulo de um piloto dela não pode "
        f"reprovar o portão do produto.\n{r.stdout}")
    assert "Perfis — a leva sete" in r.stdout, (
        f"a régua imprimiu o texto velho — ela está digitando em vez de ler:\n"
        f"{r.stdout}")
    assert "a língua da obra: 'leva'" in r.stdout, (
        f"a régua listou o piloto e não disse o que há de errado nele:\n{r.stdout}")

    # 2. e um isento sem moldura nenhuma PARA o portão
    alvo.write_text("# este piloto deixou de abrir janela\n", encoding="utf-8")
    r = _rodar(arvore)
    assert r.returncode != 0, (
        f"o portão passou com um isento que não tem mais texto de moldura:\n"
        f"{r.stdout}")
    assert "A_BANCADA" in (r.stdout + r.stderr), (r.stdout, r.stderr)


def test_a_lista_de_palavras_banidas_vem_do_dono(arvore: pathlib.Path) -> None:
    """Se o dono da lista sumir, o portão PARA — não segue com uma peneira a menos.

    É a diferença entre um portão que perde a fonte e o instrumento falso que
    esta casa mais paga: aquele daria verde sobre tudo, calado, medindo três
    peneiras onde deveria medir quatro.
    """
    dono = arvore / "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py"
    dono.write_text("# o dono da lista mudou de nome\n", encoding="utf-8")

    r = _rodar(arvore)
    assert r.returncode != 0, (
        f"o portão passou sem conseguir ler `PALAVRAS_BANIDAS`:\n{r.stdout}")
    assert "PALAVRAS_BANIDAS" in (r.stdout + r.stderr), (r.stdout, r.stderr)
