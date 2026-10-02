#!/usr/bin/env python3
"""A RÉGUA DA RÉGUA: o portão da moldura reprova de verdade."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_janela_nao_confessa.py"

O_QUE_ELE_LE = (
    "scripts/check_a_janela_nao_confessa.py",
    "scripts/check_a_tela_nao_confessa.py",
    "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py",
    "src/hefesto_dualsense4unix/interface/hefesto_vivo.py",
    "src/hefesto_dualsense4unix/gui/ponte_da_tela.py",
    "src/hefesto_dualsense4unix/app/tray.py",
    "src/hefesto_dualsense4unix/utils/identidade.py",
    "packaging/hefesto-dualsense4unix.desktop",
    "assets/hefesto-dualsense4unix.service",
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
        ("a onda 5 fechou", "a língua da obra"),
        ("as dez abas, vivas", "o apelido que esta casa deu ao piloto"),
        ("montado em 39fa440d", "um hash de commit"),
        ("a mesa de verdade", "palavra que ela baniu da tela"),
        ("o Hefesto ainda não lê tudo", "forma de confissão"),
    ],
)
def test_o_subtitulo_que_fala_a_lingua_de_dentro_reprova(
        arvore: pathlib.Path, frase: str, peneira: str) -> None:
    """Cada peneira do portão morde, e o vermelho DIZ qual delas foi."""
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
    """O texto dos pilotos isentos sai do ARQUIVO, e a isenção não pode emudecer."""
    alvo = arvore / "src/hefesto_dualsense4unix/interface/perfis_vivos.py"
    texto = alvo.read_text(encoding="utf-8")
    assert 'subtitulo="Perfis — os do disco"' in texto, (
        "o piloto de bancada dos perfis mudou de subtítulo — esta régua está "
        "medindo uma árvore que não é a dele")

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

    alvo.write_text("# este piloto deixou de abrir janela\n", encoding="utf-8")
    r = _rodar(arvore)
    assert r.returncode != 0, (
        f"o portão passou com um isento que não tem mais texto de moldura:\n"
        f"{r.stdout}")
    assert "A_BANCADA" in (r.stdout + r.stderr), (r.stdout, r.stderr)


def test_a_lista_de_palavras_banidas_vem_do_dono(arvore: pathlib.Path) -> None:
    """Se o dono da lista sumir, o portão PARA — não segue com uma peneira a menos."""
    dono = arvore / "src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py"
    dono.write_text("# o dono da lista mudou de nome\n", encoding="utf-8")

    r = _rodar(arvore)
    assert r.returncode != 0, (
        f"o portão passou sem conseguir ler `PALAVRAS_BANIDAS`:\n{r.stdout}")
    assert "PALAVRAS_BANIDAS" in (r.stdout + r.stderr), (r.stdout, r.stderr)
