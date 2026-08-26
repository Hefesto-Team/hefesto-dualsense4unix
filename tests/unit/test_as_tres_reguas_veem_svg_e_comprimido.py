"""Os dois buracos que a conferência da LEVA-4-C achou, e nenhum agente vira.

**26/08/2026.** A frente LEVA-4-C tirou o ``.svg`` do ``EXCLUIR_SUFIXO`` do
``check_endereco_de_radio.py`` — e a conferência mediu que as OUTRAS DUAS
réguas da mesma regra continuavam cegas ao mesmo formato, **inclusive a
autoritativa**. Três réguas, o mesmo ponto cego, ao mesmo tempo: é exatamente o
que "duas réguas independentes" existe para impedir.

E achou um segundo, que ninguém tinha visto: o ``.gz``. A casa já tinha a cura
ESCRITA desde 23/08, no comentário do ``check_anonymity.sh`` — *"A cura NÃO é
acrescentar '.gz' ao PULA: isso cegaria o portão para um MAC de verdade dentro
de um comprimido. A cura é olhar o CONTEÚDO."* O irmão descomprimia; este
pulava. Um MAC em TEXTO dentro de um ``.gz`` não era visto por portão nenhum
desta casa: o ``check_anonymity.sh`` descomprime, mas só procura os oito OUIs da
bancada em BYTES CRUS.

Os dois buracos eram LATENTES — nenhum vazamento vivo foi medido. Este arquivo
existe para que continuem fechados.

**Nenhum endereço nem serial LITERAL mora aqui.** Os portões sob teste varrem
``tests/``, e um literal se acusaria. Tudo é montado em tempo de execução, e o
endereço plantado usa primeiro octeto ``06`` — faixa localmente administrada,
que a IEEE nunca atribui a fabricante.
"""

from __future__ import annotations

import gzip
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_endereco_de_radio.py"

#: Montado em tempo de execução: seis grupos hex separados por dois-pontos, com
#: o primeiro octeto na faixa localmente administrada.
_ENDERECO = ":".join(["06", "1B", "44", "11", "3A", "B7"])


def _repo(tmp: Path, arquivos: dict[str, bytes]) -> Path:
    """Um repositório de mentira com os arquivos já commitados."""
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp / "scripts" / "check_endereco_de_radio.py").write_bytes(
        PORTAO.read_bytes()
    )
    for rel, dados in arquivos.items():
        alvo = tmp / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", "commit", "-qm", "x", "--no-verify"],
        cwd=tmp, check=True,
    )
    return tmp


def _rodar(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/check_endereco_de_radio.py"],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def test_endereco_em_texto_dentro_de_gz_e_pego(tmp_path: Path) -> None:
    """O buraco que ninguém tinha visto: comprimido não é esconderijo.

    Arranque a cura devolvendo ``".gz"`` ao ``EXCLUIR_SUFIXO`` e este teste
    reprova nomeando o arquivo que passaria.
    """
    conteudo = f"data,adaptador\n2026-08-23,{_ENDERECO}\n".encode()
    repo = _repo(tmp_path, {"docs/dados.csv.gz": gzip.compress(conteudo)})
    r = _rodar(repo)
    assert r.returncode == 1, (
        "um endereço de rádio EM TEXTO dentro de um .csv.gz versionado passou "
        f"pelo portão: rc={r.returncode}, saída {r.stdout.strip()!r}. E a "
        "segunda régua não cobre esta — o check_anonymity.sh descomprime, mas "
        "só procura OUIs em bytes crus."
    )
    assert "dados.csv.gz" in r.stdout + r.stderr


def test_o_mesmo_conteudo_cru_continua_sendo_pego(tmp_path: Path) -> None:
    """A resposta contrária: sem ela, um portão que reprova TUDO passaria."""
    conteudo = f"data,adaptador\n2026-08-23,{_ENDERECO}\n".encode()
    r = _rodar(_repo(tmp_path, {"docs/dados.csv": conteudo}))
    assert r.returncode == 1


def test_gz_ilegivel_nao_derruba_a_varredura(tmp_path: Path) -> None:
    """Portão que morre no primeiro arquivo estranho é portão que se desliga."""
    lixo = b"isto " + b"nao" + b" e gzip"  # cru de propósito (noqa-acento)
    repo = _repo(tmp_path, {"docs/quebrado.csv.gz": lixo})
    r = _rodar(repo)
    assert r.returncode == 0, (
        f"um .gz ilegível derrubou a varredura inteira: {r.stderr.strip()!r}"
    )


def test_svg_e_varrido_pelas_tres_reguas() -> None:
    """As três listas de "pule este formato" não podem mais conter ``.svg``.

    É teste de DECLARAÇÃO de propósito, e mede as três de uma vez: o defeito
    não era uma régua cega, era **as três ao mesmo tempo**, e é essa
    simultaneidade que a conferência achou. Uma régua voltando a pular SVG
    sozinha já reprova aqui.
    """
    fontes = {
        "scripts/check_anonymity.sh": "PULA",
        "tests/unit/test_docs_mac_anonimato.py": "_SKIP_SUFFIXES",
        "scripts/check_endereco_de_radio.py": "EXCLUIR_SUFIXO",
    }
    cegas = []
    for rel, nome in fontes.items():
        fonte = (RAIZ / rel).read_text(encoding="utf-8")
        # A LISTA, e não a prosa em volta dela: o primeiro `nome = {...}` que é
        # ATRIBUIÇÃO. Uma varredura por linha leria a própria docstring que
        # explica por que o SVG saiu e acusaria a explicação — o defeito de
        # forma que esta casa chama de "a régua confunde a PALAVRA com o ATO".
        for linha in fonte.splitlines():
            crua = linha.lstrip()
            if crua.startswith(("#", "//", "*", '"""')):
                continue
            if not crua.startswith(f"{nome} =") and f"{nome} = " not in linha:
                continue
            i = fonte.index(linha)
            fim = fonte.index("}" if "{" in linha else ")", i)
            if ".svg" in fonte[i:fim]:
                cegas.append(f"{rel} :: {nome}")
            break
    assert not cegas, (
        "estas réguas voltaram a pular SVG, que é XML de TEXTO PURO: "
        f"{cegas}. Medido em 26/08/2026: um serial de fábrica dentro de um "
        "<text> de SVG commitado saía rc=0; o mesmo conteúdo num .md, rc=1. "
        "São 49 SVGs versionados, todos texto."
    )


@pytest.mark.parametrize("formato", [".png", ".mo", ".ico"])
def test_os_binarios_de_verdade_continuam_fora(formato: str) -> None:
    """A resposta contrária da anterior: a lista não podia esvaziar.

    Tirar o SVG é medição; tirar tudo seria a régua acusando três bytes que
    casam por acaso dentro de dado comprimido — que é o motivo pelo qual a
    lista existe.
    """
    fonte = (RAIZ / "scripts" / "check_endereco_de_radio.py").read_text(
        encoding="utf-8"
    )
    i = fonte.index("EXCLUIR_SUFIXO = {")
    assert formato in fonte[i : fonte.index("}", i)]
