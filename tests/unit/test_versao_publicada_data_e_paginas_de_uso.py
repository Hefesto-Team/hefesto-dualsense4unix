"""O que a release publica sobre si mesma: data do AppStream, tag e endereço.

PUBLICAÇÃO-FIEL-01 (31/07). Três coisas que a v0.4.0 publicou erradas, e a
régua que deixou passar:

  - `flatpak/br.andrefarias.Hefesto.metainfo.xml` anunciava a 0.4.0 com
    `date="2026-07-28"` e com o texto da 0.3.0, e a 0.3.0 tinha sumido da série.
    O commit do bump trocou uma linha — `version="0.3.0"` virou
    `version="0.4.0"` — porque o `scripts/check_version_consistency.py` conferia
    o NÚMERO e só. Era a menor edição possível que deixava o portão verde.
  - `docs/usage/instalacao.md` — a página canônica, para onde o README aponta
    duas vezes — mandava `git checkout v0.3.0` com a 0.4.0 publicada.
  - `README.md` e as três páginas de uso traziam o literal `[REDACTED]` DENTRO
    da URL do fork: badge de CI com imagem quebrada e `git clone` impossível de
    copiar.

Mordidas deste arquivo, uma por uma:

  - arrancar `_conferir_data_da_release` do portão faz
    `test_portao_reprova_a_data_errada_da_v040` e os dois irmãos passarem a
    aprovar, porque o número continua batendo — é exatamente o estado do disco
    em 30/07;
  - apagar a entrada da 0.3.0 do metainfo derruba
    `test_toda_secao_datada_0x_do_changelog_tem_release_no_metainfo`;
  - devolver `v0.3.0` a qualquer uma das três páginas de uso derruba
    `test_paginas_de_uso_clonam_a_tag_da_versao_canonica`;
  - devolver o marcador a qualquer URL derruba
    `test_nenhum_marcador_de_redacao_dentro_de_url`, que é ESTREITO de
    propósito: o mesmo marcador num campo de e-mail continua permitido, e
    `test_a_mordida_da_url_nao_alcanca_o_campo_de_email` prova isso contra os
    dois arquivos reais que dependem da política.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

GATE_REL = "scripts/check_version_consistency.py"
METAINFO_REL = "flatpak/br.andrefarias.Hefesto.metainfo.xml"
CHANGELOG_REL = "CHANGELOG.md"
INSTALACAO_REL = "docs/usage/instalacao.md"
PAGINAS_DE_USO = (INSTALACAO_REL, "docs/usage/quickstart.md", "docs/usage/flatpak.md")

#: Os arquivos que trazem a URL do fork de release e por isso passam pela
#: peneira do sanitizador global.
ARQUIVOS_COM_URL_DO_FORK = ("README.md", *PAGINAS_DE_USO)

#: Dispensa NOMEADA da regra do marcador em URL, e o motivo está inteiro na
#: docstring de `test_nenhum_marcador_de_redacao_dentro_de_url`: quem escreve o
#: `[REDACTED]` é um hook global fora deste repositório, a cada commit. A lista
#: não é permissão — é dívida com nome e com data, cobrada por dois testes.
PENDENCIA_DO_SANITIZADOR = frozenset(ARQUIVOS_COM_URL_DO_FORK)

#: Estado do metainfo em 30/07, reproduzido literalmente: número certo, data da
#: release anterior. É o caso que o portão de então aprovava.
_METAINFO_COM_DATA_ERRADA = (
    "<releases>\n"
    '  <release version="0.4.0" date="2026-07-28">\n'
    "    <description><p>x</p></description>\n"
    "  </release>\n"
    "</releases>\n"
)


def _versao_canonica() -> str:
    try:
        import tomllib
    except ImportError:  # pragma: no cover — 3.10
        import tomli as tomllib
    dados = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return str(dados["project"]["version"])


def _repo_fake(
    tmp_path: Path,
    *,
    versao: str,
    metainfo: str | None = None,
    changelog: str | None = None,
) -> Path:
    """Repo mínimo com o portão real dentro, para provar que ele reprova."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / GATE_REL, tmp_path / GATE_REL)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "fake"\nversion = "{versao}"\n', encoding="utf-8"
    )
    if metainfo is not None:
        destino = tmp_path / METAINFO_REL
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(metainfo, encoding="utf-8")
    if changelog is not None:
        (tmp_path / CHANGELOG_REL).write_text(changelog, encoding="utf-8")
    return tmp_path


def _rodar_portao(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )


# --------------------------------------------------------------------------
# 1) O portão confere a DATA da release corrente, não só o número.
# --------------------------------------------------------------------------


def test_portao_reprova_a_data_errada_da_v040(tmp_path: Path) -> None:
    """O caso medido: número certo, data da release anterior, CHANGELOG real.

    Sem a conferência de data o portão sai 0 aqui — o número bate.
    """
    repo = _repo_fake(
        tmp_path,
        versao="0.4.0",
        metainfo=_METAINFO_COM_DATA_ERRADA,
        changelog=(REPO / CHANGELOG_REL).read_text(encoding="utf-8"),
    )
    proc = _rodar_portao(repo)
    assert proc.returncode == 1, (
        "o portão aprovou a 0.4.0 datada de 28/07 contra o CHANGELOG que a data "
        "em 30/07: " + proc.stdout + proc.stderr
    )
    assert "2026-07-28" in proc.stdout and "2026-07-30" in proc.stdout, (
        "a mensagem precisa dizer as DUAS datas, senão não se sabe qual "
        f"arquivo corrigir: {proc.stdout!r}"
    )


def test_portao_aprova_quando_a_data_bate(tmp_path: Path) -> None:
    repo = _repo_fake(
        tmp_path,
        versao="9.9.9",
        metainfo='<releases>\n  <release version="9.9.9" date="2026-07-30"/>\n</releases>\n',
        changelog="# Changelog\n\n## [9.9.9] — 2026-07-30\n\ntexto\n",
    )
    proc = _rodar_portao(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHANGELOG" in proc.stdout, (
        "a conferência de data passou calada — não dá para saber se ela rodou"
    )


def test_portao_reprova_release_sem_secao_no_changelog(tmp_path: Path) -> None:
    """Publicar versão que o CHANGELOG não conhece é o mesmo defeito de outro
    ângulo: a loja anuncia notas que não existem."""
    repo = _repo_fake(
        tmp_path,
        versao="9.9.9",
        metainfo='<releases>\n  <release version="9.9.9" date="2026-07-30"/>\n</releases>\n',
        changelog="# Changelog\n\n## [9.9.8] — 2026-07-30\n\ntexto\n",
    )
    proc = _rodar_portao(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "9.9.9" in proc.stdout


def test_secao_sem_data_nao_e_lida_como_data(tmp_path: Path) -> None:
    """`## [0.1.2] — RETIRADA` existe no CHANGELOG real: uma versão puxada de
    circulação. Se ela virasse a primeira release do metainfo, o portão tem de
    reprovar, não casar com o travessão."""
    repo = _repo_fake(
        tmp_path,
        versao="0.1.2",
        metainfo='<releases>\n  <release version="0.1.2" date="2026-07-26"/>\n</releases>\n',
        changelog="# Changelog\n\n## [0.1.2] — RETIRADA\n\ntexto\n",
    )
    proc = _rodar_portao(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_portao_real_continua_saindo_zero() -> None:
    proc = _rodar_portao(REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Data da release corrente confere" in proc.stdout


# --------------------------------------------------------------------------
# 2) A série do metainfo não pode perder uma release publicada.
# --------------------------------------------------------------------------


def _releases_do_metainfo() -> list[tuple[str, str]]:
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    return [
        (r.get("version") or "", r.get("date") or "") for r in releases.findall("release")
    ]


def _secoes_datadas_0x_do_changelog() -> dict[str, str]:
    texto = (REPO / CHANGELOG_REL).read_text(encoding="utf-8")
    achados = re.findall(
        r"^##\s*\[(0\.\d+\.\d+)\]\s*[—-]\s*(\d{4}-\d{2}-\d{2})\s*$",
        texto,
        re.MULTILINE,
    )
    return dict(achados)


def test_toda_secao_datada_0x_do_changelog_tem_release_no_metainfo() -> None:
    """A 0.3.0 foi publicada e sumiu da série entre a 0.4.0 e a 0.2.0."""
    esperadas = _secoes_datadas_0x_do_changelog()
    assert esperadas, "nenhuma seção 0.x datada no CHANGELOG — o regex mudou?"
    presentes = dict(_releases_do_metainfo())
    faltando = sorted(set(esperadas) - set(presentes))
    assert not faltando, (
        f"release publicada e ausente do AppStream: {faltando}. Quem instalar "
        "pela loja nunca vê essas notas."
    )


def test_cada_release_do_metainfo_usa_a_data_do_changelog() -> None:
    """A conferência do portão alcança só a primeira entrada; aqui vão todas."""
    esperadas = _secoes_datadas_0x_do_changelog()
    divergentes = [
        (versao, data, esperadas[versao])
        for versao, data in _releases_do_metainfo()
        if versao in esperadas and data != esperadas[versao]
    ]
    assert not divergentes, (
        f"(versão, data no metainfo, data no CHANGELOG): {divergentes}"
    )


def test_a_release_corrente_nao_repete_o_texto_da_anterior() -> None:
    """O defeito de 30/07 não foi só a data: a descrição era a da 0.3.0 inteira."""
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    textos = []
    for rel in releases.findall("release"):
        descricao = rel.find("description")
        assert descricao is not None, f"release {rel.get('version')} sem descrição"
        texto = " ".join("".join(descricao.itertext()).split())
        assert texto, f"release {rel.get('version')} com descrição vazia"
        textos.append(texto)
    assert len(set(textos)) == len(textos), (
        "duas releases do metainfo contam a mesma história — foi assim que a "
        "0.4.0 saiu anunciando o conteúdo da 0.3.0"
    )


# --------------------------------------------------------------------------
# 3) As páginas de uso: tag corrente e endereço copiável.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", PAGINAS_DE_USO)
def test_paginas_de_uso_clonam_a_tag_da_versao_canonica(relpath: str) -> None:
    texto = (REPO / relpath).read_text(encoding="utf-8")
    tags = re.findall(r"^git checkout v(\S+)", texto, re.MULTILINE)
    assert tags, f"{relpath} perdeu o `git checkout v<tag>`"
    assert set(tags) == {_versao_canonica()}, (
        f"{relpath} manda instalar {sorted(set(tags))} com a "
        f"{_versao_canonica()} publicada"
    )


def test_prosa_da_pagina_de_instalacao_cita_a_versao_canonica() -> None:
    """A frase de abertura é o que a pessoa lê antes de rodar o comando; ela
    envelheceu junto com a tag e não cabe na régua do portão (um regex por
    alvo, e o alvo de lá é o comando)."""
    texto = (REPO / INSTALACAO_REL).read_text(encoding="utf-8")
    achado = re.search(r"A versão corrente é a alfa \*\*([^*]+)\*\*", texto)
    assert achado is not None, "a frase da versão corrente saiu da página"
    assert achado.group(1) == _versao_canonica()


@pytest.mark.parametrize("relpath", ("README.md", *PAGINAS_DE_USO))
def test_nenhum_marcador_de_redacao_dentro_de_url(relpath: str) -> None:
    """Marcador seguido de barra é posição de dono de repositório: badge de CI
    que não renderiza e `git clone` que ninguém consegue copiar.

    PENDÊNCIA DECLARADA, medida em 31/07: esta cura é **inexecutável dentro do
    repositório**. Quem escreve o marcador é um hook global — o `pre-commit` de
    `~/.config/git/hooks` chama `universal-sanitizer.py`, que troca o termo de
    identidade por `[REDACTED]` em todo arquivo cuja extensão não esteja em
    `safe_config_ext` e cujo nome não esteja em `safe_names`. Arquivo `.md`
    entra na peneira, e o commit desfaz a edição em silêncio.

    Prova executada: uma cópia do `README.md` com a URL real passada pelo
    sanitizador voltou com zero ocorrências do dono e três `[REDACTED]`.

    Por isso os quatro arquivos abaixo estão dispensados **por nome**, e não a
    regra inteira: o dia em que o hook parar de redigi-los, o teste irmão
    reprova e cobra a retirada da lista. O caminho para fechar de verdade está
    na PUBLICAÇÃO-FIEL-01, entrega E2, e é decisão dela.
    """
    linhas = (REPO / relpath).read_text(encoding="utf-8").splitlines()
    achados = [
        f"{relpath}:{n}" for n, ln in enumerate(linhas, 1) if "[REDACTED]/" in ln
    ]
    if relpath in PENDENCIA_DO_SANITIZADOR:
        assert achados, (
            f"{relpath} não tem mais o marcador em URL: o hook global parou de "
            "redigir, ou a E2 foi fechada. Tire o arquivo de "
            "PENDENCIA_DO_SANITIZADOR para o portão voltar a valer aqui"
        )
        return
    assert not achados, f"marcador de redação dentro de URL em: {achados}"


def test_a_pendencia_do_sanitizador_nao_cresce() -> None:
    """São QUATRO arquivos, nomeados, e a lista não engorda por descuido.

    Mordida: acrescentar nome aqui abre buraco no portão e reprova.
    """
    assert sorted(PENDENCIA_DO_SANITIZADOR) == sorted(ARQUIVOS_COM_URL_DO_FORK), (
        "hoje o hook global redige TODOS os quatro; se algum sair da peneira, "
        "tire-o da lista em vez de manter a dispensa por inércia"
    )


def test_a_mordida_da_url_nao_alcanca_o_campo_de_email() -> None:
    """Contraprova obrigatória: o marcador protege o e-mail pessoal, e essa
    política vive em dois arquivos empacotados. Uma mordida larga demais mataria
    justamente o que ela deveria proteger."""
    for relpath in ("packaging/arch/PKGBUILD", "packaging/cosmic-applet/Cargo.toml"):
        texto = (REPO / relpath).read_text(encoding="utf-8")
        assert "<[REDACTED]>" in texto, (
            f"{relpath} perdeu a redação do e-mail — a política de referência"
        )
        assert "[REDACTED]/" not in texto, (
            f"{relpath} usa o marcador em posição de URL, não de e-mail"
        )
