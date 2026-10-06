#!/usr/bin/env python3
"""versao.py — o dono da versão: propõe a próxima, grava em todos os alvos e confere a tag.

  versao.py atual                       a versão do `pyproject.toml`
  versao.py seguinte [--desde vX.Y.Z]    a próxima versão, pelo tipo dos commits desde a última tag da série
  versao.py gravar [VERSAO] [--data D]  grava a mesma versão em todos os alvos (padrão: a proposta)
  versao.py conferir-tag vX.Y.Z         a tag diz a versão que o pacote tem (o `release.yml` chama)
  versao.py hash ARQUIVO                grava no PKGBUILD o hash do tarball da tag

A SÉRIE mora numa linha de `.github/repositorio.yml` (`release: serie: "0.9"`): é o prefixo das versões que
esta série numera. O primeiro número depois do prefixo sobe com `feat` (0.9.4.5 -> 0.9.5), o seguinte com
`fix` ou `perf` (0.9.4.5 -> 0.9.4.6); `docs`, `test`, `chore` e afins sozinhos não lançam nada. Mudança
incompatível (`!` ou `BREAKING CHANGE`) sobe como `feat` e sai no resumo, para quem mantém decidir se ela
pede série nova. Trocar a série é trocar a linha: nenhum número é escolhido à mão.

Os alvos são os que o `scripts/check_version_consistency.py` já confere (a lista é a dele, lida de lá),
mais o `pyproject.toml`. Para a versão nova o AppStream ganha uma `<release>` com a data; a data da
seção do CHANGELOG tem de ser a mesma (a régua dele confere).

O CONTRATO: idempotente, `--conferir` (diz o que mudaria; sai 1 se mudaria algo), resumo numa linha e o
detalhe depois ou em `--detalhe ARQ`. Saída: 0 feito ou já feito; 1 `--conferir` com o que fazer, ou a tag
diverge; 2 uso ou a série não deixa.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comum

VALIDA = re.compile(r"^\d+(?:\.\d+){1,3}$")
COMMIT = re.compile(r"^(?P<tipo>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?:\s")
PYPROJECT = "pyproject.toml"
PKGBUILD = "packaging/arch/PKGBUILD"


def carregar_conferencia(raiz: Path):  # type: ignore[no-untyped-def]
    """O `check_version_consistency.py` da árvore, como módulo: a lista de alvos tem um dono só."""
    arq = raiz / "scripts" / "check_version_consistency.py"
    spec = importlib.util.spec_from_file_location("check_version_consistency_da_release", arq)
    if spec is None or spec.loader is None:
        raise SystemExit(f"sem {arq}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def versao_do_pyproject(raiz: Path) -> str:
    texto = (raiz / PYPROJECT).read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.MULTILINE)
    if not m:
        raise SystemExit(f"sem `version` em {PYPROJECT}")
    return m.group(1)


# ---------------------------------------------------------------- a proposta

def classificar(mensagem: str) -> tuple[str | None, bool]:
    """(nível, incompatível): `feat`, `fix` ou None para o que não lança nada."""
    assunto = mensagem.splitlines()[0] if mensagem.strip() else ""
    m = COMMIT.match(assunto)
    if not m:
        return None, False
    incompativel = bool(m.group("bang")) or "BREAKING CHANGE" in mensagem
    tipo = m.group("tipo")
    if tipo == "feat":
        return "feat", incompativel
    if tipo in ("fix", "perf"):
        return ("feat", incompativel) if incompativel else ("fix", False)
    return (("feat", True) if incompativel else (None, False))


def subir(partida: str, serie: str, nivel: str) -> str:
    """`feat` sobe o primeiro número depois da série; `fix`, o seguinte. Sempre com ao menos três números."""
    partes = list(_comum.como_tupla(partida))
    posicao = len(_comum.como_tupla(serie)) + (0 if nivel == "feat" else 1)
    partes += [0] * (posicao + 1 - len(partes))
    partes = [*partes[:posicao], partes[posicao] + 1]
    partes += [0] * (3 - len(partes))
    return ".".join(str(p) for p in partes)


def proposta(raiz: Path, desde: str | None = None) -> dict[str, Any]:
    serie = _comum.serie_do_arquivo(raiz)
    tags = _comum.tags_da_serie(raiz, serie)
    base = desde[1:] if desde and desde.startswith("v") else None
    partida = base or (tags[-1] if tags else versao_do_pyproject(raiz))
    if _comum.como_tupla(partida)[: len(_comum.como_tupla(serie))] != _comum.como_tupla(serie):
        raise SystemExit(f"a versão {partida} não é da série {serie} (`release.serie` em .github/repositorio.yml)")
    tag = f"v{partida}"
    tem_tag = bool(_comum.git(raiz, "tag", "--list", tag, ok=True).strip())
    intervalo = f"{tag}..HEAD" if tem_tag else "HEAD"
    bruto = _comum.git(raiz, "log", "--format=%B%x1e", intervalo, ok=True)
    contagem = {"feat": 0, "fix": 0}
    incompativeis = 0
    for mensagem in (m.strip() for m in bruto.split("\x1e")):
        nivel, incompativel = classificar(mensagem)
        if nivel:
            contagem[nivel] += 1
        incompativeis += int(incompativel)
    nivel = "feat" if contagem["feat"] else ("fix" if contagem["fix"] else None)
    return {
        "serie": serie, "partida": partida, "tag": tag if tem_tag else None, "contagem": contagem,
        "incompativeis": incompativeis,
        "seguinte": subir(partida, serie, nivel) if nivel else None,
    }


# ---------------------------------------------------------------- a gravação

def nova_release_no_metainfo(texto: str, numero: str, data: str, resumo: str | None) -> str:
    corpo = (f"\n      <description>\n        <p>{resumo}</p>\n      </description>\n    </release>" if resumo else "/>")
    abre = f'    <release version="{numero}" date="{data}"'
    bloco = f"{abre}>{corpo}\n" if resumo else f"{abre}{corpo}\n"
    return re.sub(r"(<releases>\n)", lambda m: m.group(1) + bloco, texto, count=1)


def resumo_do_changelog(raiz: Path, numero: str) -> str | None:
    """Os primeiros itens da seção da versão, sem formatação, para o AppStream (None se a seção não existe)."""
    arq = raiz / "CHANGELOG.md"
    if not arq.is_file():
        return None
    corpo: list[str] | None = None
    for linha in arq.read_text(encoding="utf-8").splitlines():
        if re.match(rf"^##\s*\[{re.escape(numero)}\]", linha):
            corpo = []
            continue
        if corpo is not None and linha.startswith("## ["):
            break
        if corpo is not None and linha.startswith("- "):
            corpo.append(linha[2:].strip().replace("`", ""))
    if not corpo:
        return None
    texto = " ".join(corpo[:3])
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def plano_de_gravacao(raiz: Path, numero: str, data: str) -> list[tuple[str, str, str]]:
    """(arquivo, texto atual, texto novo) de cada alvo que mudaria. Um arquivo com dois alvos (o README)
    recebe os dois: o segundo parte do texto que o primeiro já trocou."""
    conf = carregar_conferencia(raiz)
    originais: dict[str, str] = {}
    textos: dict[str, str] = {}

    def trocar(rel: str, rotulo: str, padrao: str, traduzir: bool = True) -> None:
        arq = raiz / rel
        if not arq.is_file():
            return
        originais.setdefault(rel, arq.read_text(encoding="utf-8"))
        atual = textos.get(rel, originais[rel])
        if rotulo.startswith("metainfo"):
            m = re.search(r'<release\s+version="([^"]+)"', atual)
            if m and m.group(1) == numero:
                return
            textos[rel] = nova_release_no_metainfo(atual, numero, data, resumo_do_changelog(raiz, numero))
            return
        m = re.search(padrao, atual, re.MULTILINE)
        if not m:
            raise SystemExit(f"{rel}: o padrão do alvo «{rotulo}» não casa; ajuste o check_version_consistency.py")
        alvo = conf._TRADUTORES.get(rel, lambda v: v)(numero) if traduzir else numero
        if m.group(1) != alvo:
            textos[rel] = atual[: m.start(1)] + alvo + atual[m.end(1):]

    trocar(PYPROJECT, "pyproject", r'^version\s*=\s*"([^"]+)"', traduzir=False)
    for rotulo, rel, padrao in conf._TARGETS:
        trocar(rel, rotulo, padrao)
    return [(rel, originais[rel], novo) for rel, novo in textos.items() if novo != originais[rel]]


# ---------------------------------------------------------------- a linha de comando

def hoje() -> str:
    return dt.date.today().isoformat()


def cmd_atual(a: argparse.Namespace, raiz: Path) -> int:
    print(f"versao.py atual: {versao_do_pyproject(raiz)}")
    return 0


def cmd_proxima(a: argparse.Namespace, raiz: Path) -> int:
    p = proposta(raiz, a.desde)
    c = p["contagem"]
    base = p["tag"] or f"{p['partida']} (sem tag: a história inteira)"
    aviso = f"; {p['incompativeis']} incompatível(is): decida se pede série nova" if p["incompativeis"] else ""
    if p["seguinte"] is None:
        print(f"versao.py seguinte: nada a lançar desde {base} (0 feat, 0 fix){aviso}")
    else:
        print(f"versao.py seguinte: {p['seguinte']} (série {p['serie']}; {c['feat']} feat, {c['fix']} fix desde {base}){aviso}")
        if a.so_o_numero:
            print(p["seguinte"])
    return 0


def cmd_gravar(a: argparse.Namespace, raiz: Path) -> int:
    numero = a.numero
    if numero is None:
        numero = proposta(raiz)["seguinte"]
        if numero is None:
            return _comum.encerrar("versao_gravar", raiz, 0, "versao.py gravar: nada a lançar; nada gravado", [], a.detalhe)
    numero = numero[1:] if numero.startswith("v") else numero
    if not VALIDA.match(numero):
        print(f"versao.py gravar: «{numero}» não é uma versão (X.Y.Z ou X.Y.Z.W)")
        return 2
    serie = _comum.serie_do_arquivo(raiz)
    if _comum.como_tupla(numero)[: len(_comum.como_tupla(serie))] != _comum.como_tupla(serie) and not a.fora_da_serie:
        print(f"versao.py gravar: {numero} não é da série {serie}; a série é a linha `release.serie` de .github/repositorio.yml")
        return 2
    data = a.data or hoje()
    plano = plano_de_gravacao(raiz, numero, data)
    detalhe = [f"{'mudaria' if a.conferir else 'gravou'}: {rel}" for rel, _a, _n in plano]
    if not plano:
        return _comum.encerrar("versao_gravar", raiz, 0, f"versao.py gravar: {numero} já está em todos os alvos", [], a.detalhe)
    if a.conferir:
        return _comum.encerrar("versao_gravar", raiz, 1, f"versao.py gravar: {numero} mudaria {len(plano)} arquivo(s)", detalhe, a.detalhe)
    for rel, _atual, novo in plano:
        (raiz / rel).write_text(novo, encoding="utf-8")
    return _comum.encerrar("versao_gravar", raiz, 0, f"versao.py gravar: {numero} gravada em {len(plano)} arquivo(s)", detalhe, a.detalhe)


def cmd_conferir_tag(a: argparse.Namespace, raiz: Path) -> int:
    m = _comum.TAG.match(a.tag.removeprefix("refs/tags/"))
    atual = versao_do_pyproject(raiz)
    if not m:
        print(f"versao.py conferir-tag: «{a.tag}» não é uma tag de versão (vX.Y.Z ou vX.Y.Z.W)")
        return 1
    if m.group(1) != atual:
        print(f"versao.py conferir-tag: a tag diz {m.group(1)} e o pacote tem {atual}; rode `versao.py gravar` antes de marcar")
        return 1
    print(f"versao.py conferir-tag: a tag {a.tag} e o pacote dizem {atual}")
    return 0


def sha256_de(arq: Path) -> str:
    h = hashlib.sha256()
    with arq.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def cmd_hash(a: argparse.Namespace, raiz: Path) -> int:
    arq = Path(a.arquivo)
    if not arq.is_file():
        print(f"versao.py hash: sem o arquivo {arq}")
        return 2
    alvo = raiz / (a.pkgbuild or PKGBUILD)
    if not alvo.is_file():
        print(f"versao.py hash: sem o PKGBUILD em {alvo}")
        return 2
    hexa = sha256_de(arq)
    texto = alvo.read_text(encoding="utf-8")
    novo, n = re.subn(r"^sha256sums=\(.*\)\s*$", f"sha256sums=('{hexa}')", texto, count=1, flags=re.MULTILINE)
    if n != 1:
        print("versao.py hash: o PKGBUILD não tem a linha sha256sums=(...)")
        return 2
    if novo == texto:
        return _comum.encerrar("hash", raiz, 0, f"versao.py hash: o PKGBUILD já tem {hexa[:12]}", [], a.detalhe)
    if a.conferir:
        return _comum.encerrar("hash", raiz, 1, f"versao.py hash: o PKGBUILD passaria a {hexa[:12]}", [], a.detalhe)
    alvo.write_text(novo, encoding="utf-8")
    return _comum.encerrar("hash", raiz, 0, f"versao.py hash: o PKGBUILD agora tem {hexa[:12]}", [], a.detalhe)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", help="a árvore (padrão: a deste script)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comum(p: argparse.ArgumentParser, conferir: bool = True) -> None:
        if conferir:
            p.add_argument("--conferir", action="store_true", help="diz o que faria; sai 1 se faria alguma coisa")
        p.add_argument("--detalhe", type=Path, help="o detalhe vai para este arquivo")

    sub.add_parser("atual").set_defaults(f=cmd_atual)
    p = sub.add_parser("seguinte")
    p.add_argument("--desde", help="a tag de partida (padrão: a última da série)")
    p.add_argument("--so-o-numero", action="store_true", help="imprime o número também numa linha à parte")
    p.set_defaults(f=cmd_proxima)
    p = sub.add_parser("gravar")
    p.add_argument("numero", nargs="?")
    p.add_argument("--data", help="AAAA-MM-DD da release (padrão: hoje)")
    p.add_argument("--fora-da-serie", action="store_true", help="aceita uma versão fora da série declarada")
    comum(p)
    p.set_defaults(f=cmd_gravar)
    p = sub.add_parser("conferir-tag")
    p.add_argument("tag")
    p.set_defaults(f=cmd_conferir_tag)
    p = sub.add_parser("hash")
    p.add_argument("arquivo")
    p.add_argument("--pkgbuild", help=f"o PKGBUILD (padrão: {PKGBUILD})")
    comum(p)
    p.set_defaults(f=cmd_hash)
    a = ap.parse_args(argv)
    return int(a.f(a, _comum.raiz_de(a.raiz)))


if __name__ == "__main__":
    sys.exit(main())
