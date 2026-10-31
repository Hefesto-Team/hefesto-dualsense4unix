#!/usr/bin/env python3
"""check_texto_sem_pessoa.py — o projeto não fala de pessoa nem do posto de ensaio de alguém.

O produto é de quem usa. Nenhum arquivo versionado, no conteúdo nem no nome do
caminho, aponta para uma pessoa da casa. Quatro classes, sem catraca e com piso
zero, em qualquer caixa:

* ``pronome``: o pronome feminino de terceira pessoa e as contrações com «de» e
  «em», no singular e no plural, mesmo quando aponta para uma coisa. Julgar se o
  pronome é pessoa ou coisa foi o ponto cego que deixou milhares de linhas
  passarem; a régua não julga.
* ``posto``: o substantivo do posto de ensaio e todo composto dele (identificador,
  nome de arquivo, plural). O vocabulário é «ensaio», «ensaio no aparelho»,
  «máquina de teste» ou o nome do que se mede.
* ``nome``: o nome próprio e o apelido de conta, salvo a autoria legal.
* ``citacao``: a fala de uma pessoa entre aspas. A regra que a fala carregava
  vira prosa neutra; a origem fica pela data e pelo ID da decisão.

A fronteira é de LETRA, não de palavra: ``_`` e ``-`` separam (o identificador
``x_<pronome>_y`` casa), e uma letra colada não separa (as palavras que só
CONTÊM as letras do pronome, como as de cozinha e de tela, não casam). A caixa
camelo também separa (``servicoD…``).

As palavras moram montadas, nunca literais: assim esta régua não se isenta.

Uso::

    python3 scripts/check_texto_sem_pessoa.py               # rc=1 se houver ocorrência
    python3 scripts/check_texto_sem_pessoa.py --relatorio   # conta por área e por classe
    python3 scripts/check_texto_sem_pessoa.py --detalhe ARQ # grava cada ocorrência em ARQ

Os nomes que o disco de quem usa guardava migram na leitura e se montam por
partes onde moram (`utils/nomes_gravados.py`): a régua não tem formato isento.

A fala se pega por três sinais: o marcador de isenção de acento que se declara
citação, a gíria de chat entre «», e a fala apresentada (as palavras, a ordem,
a queixa ou a decisão atribuídas ao usuário ou ao produto) logo antes das aspas.

O que a régua NÃO alcança: a fala entre aspas sem nenhum dos três sinais (a
itálica entre aspas retas, a mais comum, casa também texto de fora); a paráfrase; o pronome masculino; o
substantivo comum do nome (minúsculo e acentuado, que é a palavra «triunfo»);
o arquivo binário por dentro; a história do git; e os ignorados de coordenação.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

_P = "e" + "la"
_POSTO = "ban" + "cada"
_NOME = "vit" + "oria"
_NOME_ACENTO = "Vit" + "ória"

_SEM_LETRA_ANTES = r"(?<![^\W\d_])"
_SEM_LETRA_DEPOIS = r"(?![^\W\d_])"

_PRONOME_CAIXA = re.compile(_SEM_LETRA_ANTES + r"[dn]?" + _P + r"s?" + _SEM_LETRA_DEPOIS, re.IGNORECASE)
_PRONOME_CAMELO = re.compile(r"(?<=[a-zà-ÿ])(?:[DN]" + _P + r"|E" + _P[1:] + r")s?(?![a-zà-ÿ])")
_NOME_SEM_ACENTO = re.compile(_NOME, re.IGNORECASE)
_NOME_PROPRIO = re.compile(_NOME_ACENTO + r"|" + _NOME_ACENTO.upper())

_MARCADOR = re.compile(r"noqa-acento\s*:\s*cita", re.IGNORECASE)
_FALA_APRESENTADA = re.compile(
    r"(?:palavras|frase|fala|pedido|ordem|pergunta|resposta|queixa|aceite|decisão)\s+(?:do usuário|de produto|de uso)"
    r"[^«\"“\n]{0,8}[*_]*[«\"“]",
    re.IGNORECASE,
)
_GIRIA = re.compile(r"«[^»\n]*?(?<![^\W\d_])(?:vc|vcs|pq|tb|tbm|n[ée]|t[aá]|pra)(?![^\W\d_])[^»\n]*»")

CLASSES = ("pronome", "posto", "nome", "citacao")


def _pronome(texto: str, baixo: str) -> bool:
    return _P in baixo and bool(_PRONOME_CAIXA.search(texto) or _PRONOME_CAMELO.search(texto))


def _nome(texto: str, baixo: str) -> bool:
    return "vit" in baixo and bool(_NOME_SEM_ACENTO.search(texto) or _NOME_PROPRIO.search(texto))


def _citacao(texto: str, baixo: str) -> bool:
    if "noqa-acento" in baixo and _MARCADOR.search(texto):
        return True
    if ("usuário" in baixo or "produto" in baixo or "de uso" in baixo) and _FALA_APRESENTADA.search(texto):
        return True
    return "«" in texto and bool(_GIRIA.search(texto))


def classes_da_linha(linha: str) -> list[str]:
    baixo = linha.lower()
    achadas = []
    if _pronome(linha, baixo):
        achadas.append("pronome")
    if _POSTO in baixo:
        achadas.append("posto")
    if _nome(linha, baixo):
        achadas.append("nome")
    if _citacao(linha, baixo):
        achadas.append("citacao")
    return achadas


def _tem_sinal(texto: str) -> bool:
    baixo = texto.lower()
    return any(sinal in baixo for sinal in (_P, _POSTO, "vit", "noqa-acento", "«", "usuário", "produto", "de uso"))


def classes_do_caminho(rel: str) -> list[str]:
    return [c for c in classes_da_linha(rel) if c != "citacao"]


ISENTOS: dict[str, str] = {
    "scripts/neutralizar-o-texto.py": "a régua que reescreve o pronome: as palavras são o dado da régua.",
    "scripts/o-texto-enxuto.py": "o gancho da escrita: caça o pronome e precisa dele como dado.",
    "scripts/neutralizar-os-nomes.py": "a tabela dos nomes velhos que a costura reaponta fora do git.",
    "tests/unit/test_o_neutralizador_nao_troca_o_que_nao_e_o_usuario.py": "a mordida do neutralizador.",
    "tests/unit/test_o_texto_enxuto_se_corrige_no_ato.py": "a mordida do gancho da escrita.",
}

_IDENTIDADE = re.compile(
    _NOME + r"(?:\"\s*\+\s*\")?mariadb|" + _NOME + r"maria\\?\.sds@|Vit[oó]ria Maria <", re.IGNORECASE
)

AUTORIA: dict[str, str] = {
    ".mailmap": "o mapa de autoria do git.",
    ".github/repositorio.yml": "a conta dona do repositório no GitHub.",
    "LICENSE": "a licença.",
    "NOTICE": "o aviso de autoria.",
    "pyproject.toml": "os autores do pacote.",
    "packaging/arch/PKGBUILD": "o mantenedor do pacote.",
    "packaging/fedora/*.spec": "o autor de cada entrada do changelog do pacote.",
    "packaging/debian/*": "o copyright e o changelog do pacote.",
    "po/*.po": "o tradutor no cabeçalho do catálogo.",
    "scripts/hooks/commit-msg": "o endereço de autoria que o gancho reconhece.",
    "scripts/github/aplicar.py": "a conta dona do repositório que o aplicador aceita.",
    "tests/fixtures/github/gh_de_mentira.py": "a conta dona do repositório no GitHub de mentira.",
    "tests/unit/test_a_release_sai_sozinha.py": "a conta dona do repositório que a release confere.",
}

_BINARIO = {".mo", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".gz", ".zip", ".zst", ".AppImage", ".webp", ".ttf", ".woff", ".woff2"}


@dataclass(frozen=True)
class Ocorrencia:
    rel: str
    linha: int
    classe: str
    trecho: str


def _autoria(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, padrao) for padrao in AUTORIA)


def _arquivos(raiz: Path) -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=raiz, capture_output=True, text=True, check=True,
    ).stdout
    return sorted({p for p in saida.split("\0") if p})


def _ler(caminho: Path) -> str | None:
    if caminho.suffix in _BINARIO:
        return None
    try:
        bruto = caminho.read_bytes()
    except OSError:
        return None
    if b"\0" in bruto:
        return None
    try:
        return bruto.decode("utf-8")
    except UnicodeDecodeError:
        return None


def varrer(raiz: Path, arquivos: list[str] | None = None) -> list[Ocorrencia]:
    achadas: list[Ocorrencia] = []
    for rel in arquivos if arquivos is not None else _arquivos(raiz):
        caminho = raiz / rel
        if not caminho.is_file():
            continue
        for classe in classes_do_caminho(rel):
            achadas.append(Ocorrencia(rel, 0, classe, "(no nome do caminho)"))
        if rel in ISENTOS:
            continue
        texto = _ler(caminho)
        if texto is None or not _tem_sinal(texto):
            continue
        autoria = _autoria(rel)
        for n, linha in enumerate(texto.splitlines(), 1):
            for classe in classes_da_linha(linha):
                if classe == "nome" and autoria and _IDENTIDADE.search(linha):
                    resto = _IDENTIDADE.sub("", linha)
                    if not _nome(resto, resto.lower()):
                        continue
                achadas.append(Ocorrencia(rel, n, classe, linha.strip()[:140]))
    return achadas


def area(rel: str) -> str:
    if rel.startswith("docs/"):
        return "docs"
    if rel.startswith("scripts/"):
        return "scripts"
    if rel.startswith("tests/unit/test_a"):
        return "tests-a"
    if rel.startswith("tests/unit/test_o"):
        return "tests-o"
    if rel.startswith("tests/"):
        return "tests-resto"
    return "produto"


AREAS = ("produto", "docs", "scripts", "tests-a", "tests-o", "tests-resto")


def isencoes_mortas(raiz: Path) -> list[str]:
    mortas = []
    for rel in ISENTOS:
        texto = _ler(raiz / rel)
        if texto is None:
            mortas.append(f"{rel}: o arquivo não existe mais")
        elif not any(classes_da_linha(linha) for linha in texto.splitlines()):
            mortas.append(f"{rel}: já não tem palavra nenhuma; a isenção venceu")
    return mortas


def relatorio(achadas: list[Ocorrencia]) -> list[str]:
    por_area: dict[str, Counter[str]] = {a: Counter() for a in AREAS}
    arquivos: dict[str, set[str]] = {a: set() for a in AREAS}
    for o in achadas:
        por_area[area(o.rel)][o.classe] += 1
        arquivos[area(o.rel)].add(o.rel)
    linhas = [f"{'área':<12} {'total':>6} {'arquivos':>8}  " + "  ".join(f"{c:>8}" for c in CLASSES)]
    for a in AREAS:
        cont = por_area[a]
        linhas.append(
            f"{a:<12} {sum(cont.values()):>6} {len(arquivos[a]):>8}  " + "  ".join(f"{cont[c]:>8}" for c in CLASSES)
        )
    total = Counter(o.classe for o in achadas)
    todos = {o.rel for o in achadas}
    linhas.append(f"{'total':<12} {len(achadas):>6} {len(todos):>8}  " + "  ".join(f"{total[c]:>8}" for c in CLASSES))
    caminhos = sum(1 for o in achadas if o.linha == 0)
    linhas.append(f"nomes de caminho com palavra: {caminhos}")
    return linhas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--relatorio", action="store_true", help="conta por área e por classe")
    ap.add_argument("--detalhe", help="arquivo onde cada ocorrência é gravada")
    ap.add_argument("--limite", type=int, default=40, help="quantas ocorrências imprimir (padrão 40)")
    args = ap.parse_args(argv)

    achadas = varrer(RAIZ)
    if args.detalhe:
        Path(args.detalhe).write_text(
            "".join(f"{o.rel}:{o.linha}: {o.classe}: {o.trecho}\n" for o in achadas), encoding="utf-8"
        )
    for aviso in isencoes_mortas(RAIZ):
        print(f"[AVISO] isenção morta: {aviso}")
    if args.relatorio:
        print("\n".join(relatorio(achadas)))
        return 0
    for o in achadas[: args.limite]:
        print(f"[FAIL] {o.rel}:{o.linha}: {o.classe}: {o.trecho}")
    if achadas:
        resto = len(achadas) - min(len(achadas), args.limite)
        if resto:
            print(f"... e mais {resto} (use --detalhe ARQ)")
        print(f"FALHA: {len(achadas)} ocorrência(s) em {len({o.rel for o in achadas})} arquivo(s); o piso é zero.")
        return 1
    print(
        f"OK: nenhum arquivo fala de pessoa ({len(ISENTOS)} isenções de régua, {len(AUTORIA)} de autoria)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
