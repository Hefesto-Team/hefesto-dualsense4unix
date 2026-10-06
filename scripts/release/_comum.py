"""O que os scripts de `scripts/release/` repartem: a raiz, o git e o fecho de cada corrida.

O contrato de toda ferramenta da casa: idempotente (a segunda corrida não muda nada), `--conferir`
(diz o que faria e sai 1 quando faria alguma coisa), o resumo numa linha na primeira linha da
saída e o detalhe depois (ou em `--detalhe ARQ`). Se `HEFESTO_RECIBOS` aponta uma pasta, a corrida
limpa grava ali um recibo `<passo>.<árvore>` com o resumo.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[2]
TAG = re.compile(r"^v(\d+(?:\.\d+){1,3})$")


def raiz_de(texto: str | None) -> Path:
    return Path(texto).resolve() if texto else RAIZ_PADRAO


def git(raiz: Path, *args: str, ok: bool = False) -> str:
    """A saída do git em `raiz`; falha com a mensagem dele, a não ser que `ok` aceite o erro."""
    r = subprocess.run(
        ["git", "-C", str(raiz), *args], capture_output=True, text=True, check=False
    )
    if r.returncode != 0 and not ok:
        raise SystemExit(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")
    return r.stdout if r.returncode == 0 else ""


def como_tupla(numero: str) -> tuple[int, ...]:
    return tuple(int(p) for p in numero.split("."))


def comparavel(numero: str) -> tuple[int, ...]:
    """A versão com zeros à direita até quatro casas: `0.9.5` e `0.9.5.0` valem o mesmo."""
    t = como_tupla(numero)
    return t + (0,) * (4 - len(t))


def tags_da_serie(raiz: Path, serie: str) -> list[str]:
    """As versões (sem o `v`) das tags que começam pela série, da menor para a maior."""
    prefixo = como_tupla(serie)
    achadas = []
    for linha in git(raiz, "tag", "--list", "v*").split():
        m = TAG.match(linha)
        if m and como_tupla(m.group(1))[: len(prefixo)] == prefixo and len(como_tupla(m.group(1))) > len(prefixo):
            achadas.append(m.group(1))
    return sorted(achadas, key=comparavel)


def serie_do_arquivo(raiz: Path) -> str:
    """A linha `serie:` do bloco `release:` de `.github/repositorio.yml` (a série é decisão de quem mantém)."""
    arq = raiz / ".github" / "repositorio.yml"
    if not arq.is_file():
        raise SystemExit(f"sem {arq}: a série da versão mora no bloco `release:` dele")
    dentro = False
    for linha in arq.read_text(encoding="utf-8").splitlines():
        if re.match(r"^release:\s*(#.*)?$", linha):
            dentro = True
            continue
        if dentro and re.match(r"^\S", linha):
            break
        m = re.match(r'^\s+serie:\s*"?([0-9]+(?:\.[0-9]+)*)"?\s*(#.*)?$', linha) if dentro else None
        if m:
            return m.group(1)
    raise SystemExit("sem `release:` com `serie:` em .github/repositorio.yml (por exemplo `serie: \"0.9\"`)")


def encerrar(passo: str, raiz: Path, codigo: int, resumo: str, detalhe: list[str], arquivo: Path | None) -> int:
    """O resumo numa linha; o detalhe em `arquivo` (ou depois do resumo); o recibo se a corrida foi limpa."""
    print(resumo)
    texto = "\n".join(detalhe)
    if arquivo is not None:
        arquivo.write_text(texto + ("\n" if texto else ""), encoding="utf-8")
    elif detalhe:
        # o terminal nunca recebe a lista inteira: o resto mora em `--detalhe`
        print("\n".join(detalhe[:5]) + (f"\n(mais {len(detalhe) - 5} em --detalhe ARQ)" if len(detalhe) > 5 else ""))
    pasta = os.environ.get("HEFESTO_RECIBOS")
    if pasta and codigo == 0:
        arvore = git(raiz, "rev-parse", "HEAD^{tree}", ok=True).strip()[:12] or "sem-git"
        try:
            Path(pasta).mkdir(parents=True, exist_ok=True)
            (Path(pasta) / f"{passo}.{arvore}").write_text(resumo + "\n", encoding="utf-8")
        except OSError as erro:
            print(f"aviso: o recibo não foi gravado ({erro})", file=sys.stderr)
    return codigo
