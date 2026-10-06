#!/usr/bin/env python3
"""publico.py — o bloco `publico` da sprint: o que se escreve para quem usa, lido e conferido num lugar só.

A sprint inteira fica em casa. O que chega ao GitHub (a issue, a nota da release, o CHANGELOG) é só este
bloco, um trecho cercado no corpo da sprint:

    ```publico
    titulo: O microfone de cada controle liga sozinho
    tipo: adicionado          # adicionado | mudado | removido | corrigido
    area: tela                # opcional; uma das áreas do rótulo «área: …» de .github/repositorio.yml
    marco: Primeira versão pública   # opcional; um dos marcos (`milestones`) de .github/repositorio.yml
    muda: O botão do microfone liga e desliga só o microfone daquele controle.
    pronto: Ao apertar o botão, só o microfone daquele controle muda.
    ```

(o frontmatter da sprint é estrito e não aceita campo novo; o corpo, sim). Uma linha que começa com espaço
continua o campo anterior. `muda` vira a linha do CHANGELOG e o corpo da issue; `pronto` é o critério dela.

A RÉGUA: todo campo passa pelas palavras que o texto público não pode ter (as de `check_texto_publico.py`,
mais as do trabalho em equipe: mesa, agente, leva, worktree) e, quando o `check_autoria.py` existe na árvore,
pelo `check_autoria.py texto`, que nunca imprime o termo que casou. Sem a lista de termos, ele sai «não
medido» e o bloco é reprovado: o que não se mediu não se publica.

    publico.py ARQUIVO...          confere o bloco de cada sprint (saída 1 se algum reprova)
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comum

BLOCO = re.compile(r"^```publico[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
CAMPO = re.compile(r"^([a-z]+):[ \t]*(.*)$")
CAMPOS = ("titulo", "tipo", "area", "muda", "pronto", "marco")
OBRIGATORIOS = ("titulo", "tipo", "muda", "pronto")
TIPOS = ("adicionado", "mudado", "removido", "corrigido")
MARCADOR = "A-PREENCHER"  # o do molde da sprint: o bloco que ainda o traz não vai a ninguém
LIMITES = {"titulo": 80, "muda": 400, "pronto": 400}
# O que o texto de quem usa não diz, além do que o `check_texto_publico.py` já barra.
DA_CASA = (
    ("mesa", re.compile(r"\bmesa\b", re.IGNORECASE)),
    ("agente", re.compile(r"\bagentes?\b", re.IGNORECASE)),
    ("leva", re.compile(r"\blevas?\b", re.IGNORECASE)),
    ("worktree", re.compile(r"\bworktrees?\b", re.IGNORECASE)),
)


def extrair(texto: str) -> dict[str, str] | None:
    """Os campos do primeiro bloco `publico` do texto (ou None se não há bloco)."""
    achado = BLOCO.search(texto)
    if not achado:
        return None
    campos: dict[str, str] = {}
    atual: str | None = None
    for linha in achado.group(1).splitlines():
        if not linha.strip():
            continue
        if linha[0] in " \t" and atual:
            campos[atual] = (campos[atual] + " " + linha.strip()).strip()
            continue
        m = CAMPO.match(linha)
        if not m:
            campos["_erro"] = f"linha que não é «campo: valor»: {linha[:60]}"
            continue
        atual = m.group(1)
        campos[atual] = re.sub(r"\s+#\s.*$", "", m.group(2)).strip()
    return campos


def areas_do_arquivo(raiz: Path) -> list[str]:
    """As áreas que o arquivo do repositório declara (o que vem depois de «área: » nos rótulos)."""
    arq = raiz / ".github" / "repositorio.yml"
    if not arq.is_file():
        return []
    return re.findall(r'nome:\s*"área: ([^"]+)"', arq.read_text(encoding="utf-8"))


def _expressoes_da_casa(raiz: Path) -> list[tuple[str, re.Pattern[str]]]:
    lista = list(DA_CASA)
    arq = raiz / "scripts" / "check_texto_publico.py"
    if arq.is_file():
        spec = importlib.util.spec_from_file_location("check_texto_publico_do_publico", arq)
        if spec and spec.loader:
            modulo = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = modulo  # o @dataclass dele procura o próprio módulo aqui
            spec.loader.exec_module(modulo)
            lista += list(modulo.EXPRESSOES)
    return lista


def passa_pela_autoria(raiz: Path, texto: str) -> str | None:
    """None se a régua de autoria aceita o texto (ou não existe na árvore); senão, o motivo curto."""
    script = raiz / "scripts" / "check_autoria.py"
    if not script.is_file():
        return None
    r = subprocess.run([sys.executable, str(script), "texto"], input=texto, capture_output=True, text=True, check=False)
    if r.returncode == 0:
        return None
    primeira = (r.stdout.strip() or r.stderr.strip()).splitlines()
    return "a régua de autoria recusou o texto" + (f": {primeira[0][:120]}" if primeira else "")


def marcos_do_arquivo(raiz: Path) -> list[str]:
    arq = raiz / ".github" / "repositorio.yml"
    if not arq.is_file():
        return []
    return re.findall(r'^\s+- titulo:\s*"([^"]+)"', arq.read_text(encoding="utf-8"), re.MULTILINE)


def erros_de_texto(texto: str, raiz: Path, autoria: bool = True) -> list[str]:
    """Os defeitos de um texto solto que vai a quem usa (o comentário de entrega, por exemplo)."""
    erros: list[str] = []
    for nome, padrao in _expressoes_da_casa(raiz):
        if padrao.search(texto):
            erros.append(f"tem uma palavra da casa («{nome}»): escreva para quem usa")
    if autoria and not erros:
        motivo = passa_pela_autoria(raiz, texto)
        if motivo:
            erros.append(motivo)
    return erros


def validar(bloco: dict[str, str], raiz: Path, autoria: bool = True) -> list[str]:
    """Os defeitos do bloco; lista vazia quando ele pode ir a quem usa."""
    erros: list[str] = []
    if "_erro" in bloco:
        erros.append(bloco["_erro"])
    erros += [f"falta o campo `{c}`" for c in OBRIGATORIOS if not bloco.get(c)]
    erros += [f"campo desconhecido `{c}`" for c in bloco if c not in CAMPOS and c != "_erro"]
    erros += [f"`{c}` ainda traz o marcador do molde ({MARCADOR}): escreva o texto" for c in CAMPOS if MARCADOR in bloco.get(c, "")]
    if bloco.get("tipo") and bloco["tipo"] not in TIPOS:
        erros.append(f"`tipo` é um destes: {', '.join(TIPOS)}")
    areas = areas_do_arquivo(raiz)
    if bloco.get("area") and areas and bloco["area"] not in areas:
        erros.append(f"`area` é uma destas (os rótulos «área: …» do repositório): {', '.join(areas)}")
    marcos = marcos_do_arquivo(raiz)
    if bloco.get("marco") and marcos and bloco["marco"] not in marcos:
        erros.append(f"`marco` é um destes (os `milestones` do repositório): {', '.join(marcos)}")
    for campo, limite in LIMITES.items():
        if len(bloco.get(campo, "")) > limite:
            erros.append(f"`{campo}` passa de {limite} caracteres")
    for campo in CAMPOS:
        for nome, padrao in _expressoes_da_casa(raiz):
            if padrao.search(bloco.get(campo, "")):
                erros.append(f"`{campo}` tem uma palavra da casa («{nome}»): escreva para quem usa")
    if autoria and not erros:
        motivo = passa_pela_autoria(raiz, "\n".join(bloco.get(c, "") for c in CAMPOS))
        if motivo:
            erros.append(motivo)
    return erros


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    raiz = _comum.RAIZ_PADRAO
    if not args:
        print("publico.py: diga os arquivos de sprint")
        return 2
    ruins = 0
    for nome in args:
        texto = Path(nome).read_text(encoding="utf-8")
        bloco = extrair(texto)
        if bloco is None:
            print(f"{nome}: sem bloco `publico` (a sprint não vai a quem usa)")
            continue
        for erro in validar(bloco, raiz):
            print(f"{nome}: {erro}")
            ruins += 1
    print(f"publico.py: {ruins} defeito(s) em {len(args)} arquivo(s)")
    return 1 if ruins else 0


if __name__ == "__main__":
    sys.exit(main())
