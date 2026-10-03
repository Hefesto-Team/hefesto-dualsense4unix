#!/usr/bin/env python3
"""O gancho pergunta pela RÉGUA quando o commit mexe na tela — REGUA-NO-GANCHO-01."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

GRAU = 1

TELA = (
    "src/hefesto_dualsense4unix/interface",
    "src/hefesto_dualsense4unix/app",
)

NAO_E_DESENHO = (
    "layout/screenshots",
    "layout/uploads",
)

PREFIXOS_DE_REGUA = ("regua", "conferir", "olhar", "medir")

PASTAS_DE_REGUA = ("src/hefesto_dualsense4unix/interface", "scripts")

A_PONTE_JS = "src/hefesto_dualsense4unix/interface/controles_vivos.py"

FERRAMENTAS = "src/hefesto_dualsense4unix/interface"

PAGINAS = "src/hefesto_dualsense4unix/interface/paginas"

O_INSTRUMENTO = "scripts/regua_de_tela.py"

O_MANUAL = "docs/method/2026-08-29-A-REGUA-DE-TELA-como-se-prova-a-interface.md"

ARVORE_VAZIA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

VEREDITO_REPROVA = 2

EM_BRANCO = "em-branco"
"""O commit não toca a tela. Nada a dizer, e é o caso da maioria."""

COM_REGUA = "com-regua"
"""Toca a tela e traz régua junto. O caminho bom; cala."""

SO_REGUA = "so-regua"
"""Só mexe em régua. É trabalho de régua, e ele não se cobra a si mesmo."""

SEM_REGUA = "sem-regua"
"""Toca a tela e não traz régua nenhuma. É aqui que ele fala."""

SEM_REGUA_DE_NOVO = "sem-regua-de-novo"
"""O mesmo, e o `HEAD` já levou o aviso pelas mesmas abas. Sai UMA linha."""


def e_regua(caminho: str) -> bool:
    """Este caminho é uma RÉGUA DE TELA?"""
    if caminho == A_PONTE_JS:
        return True
    p = PurePosixPath(caminho)
    if p.match("tests/unit/test_*.py"):
        return True
    if str(p.parent) not in PASTAS_DE_REGUA:
        return False
    return any(p.name.startswith(pref) for pref in PREFIXOS_DE_REGUA)


def e_tela(caminho: str) -> bool:
    """Este caminho é DESENHO — o que, mudando, pede régua?"""
    if caminho.endswith(".md"):
        return False
    if any(_sob(caminho, p) for p in NAO_E_DESENHO):
        return False
    return any(_sob(caminho, p) for p in TELA)


def _sob(caminho: str, prefixo: str) -> bool:
    return caminho == prefixo or caminho.startswith(prefixo + "/")


def aba_de(caminho: str) -> str | None:
    """O número da aba que este caminho mexe, ou `None`."""
    p = PurePosixPath(caminho)
    if p.parent == PurePosixPath(PAGINAS) and p.suffix == ".html":
        cabeca = p.name[:2]
        return cabeca if cabeca.isdigit() else None
    if str(p.parent) == FERRAMENTAS and p.name.startswith("aba"):
        cabeca = p.stem[3:5]
        return cabeca if cabeca.isdigit() else None
    return None


def julgar(
    no_indice: Iterable[str],
    abas_ja_devendo: Iterable[str] = (),
) -> tuple[str, list[str], list[str], list[str]]:
    """O veredito, sem git nenhum: só caminhos."""
    caminhos = list(no_indice)
    reguas = sorted(c for c in caminhos if e_regua(c))
    desenho = sorted(c for c in caminhos if not e_regua(c) and e_tela(c))
    abas = sorted({a for c in desenho if (a := aba_de(c))})

    if not desenho:
        return (SO_REGUA if reguas else EM_BRANCO), [], reguas, []
    if reguas:
        return COM_REGUA, desenho, reguas, abas

    ja = set(abas_ja_devendo)
    if abas and set(abas) <= ja:
        return SEM_REGUA_DE_NOVO, desenho, [], abas
    return SEM_REGUA, desenho, [], abas


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(["git", *args], cwd=str(raiz), capture_output=True, text=True)
    return saida.stdout.strip() if saida.returncode == 0 else ""


def caminhos_no_indice(raiz: Path) -> list[str]:
    """O que este commit vai carregar. Sem `HEAD`, compara com a árvore vazia."""
    contra = "HEAD" if _git(raiz, "rev-parse", "--verify", "HEAD") else ARVORE_VAZIA
    return [ln for ln in _git(raiz, "diff", "--cached", "--name-only", contra).splitlines() if ln]


def caminhos_do_commit(raiz: Path, sha: str) -> list[str]:
    """O que um commit já feito carregou. Vazio para merge, que não tem gancho."""
    if len(_git(raiz, "rev-list", "--parents", "-n", "1", sha).split()) > 2:
        return []
    return [ln for ln in _git(raiz, "show", "--name-only", "--format=", sha).splitlines() if ln]


def abas_devidas_pelo_head(raiz: Path) -> list[str]:
    """Pelas quais abas o `HEAD` já levou este aviso? É o que cala a repetição."""
    veredito, _, _, abas = julgar(caminhos_do_commit(raiz, "HEAD"))
    return abas if veredito in (SEM_REGUA, SEM_REGUA_DE_NOVO) else []


def reguas_no_disco(raiz: Path) -> list[str]:
    """As réguas que EXISTEM, descobertas por varredura — nunca por lista."""
    achadas: list[str] = []
    for nome_da_pasta in PASTAS_DE_REGUA:
        pasta = raiz / nome_da_pasta
        if not pasta.is_dir():
            continue
        achadas += [
            f"{nome_da_pasta}/{f.name}"
            for f in sorted(pasta.iterdir())
            if f.is_file()
            and f.suffix == ".py"
            and any(f.name.startswith(p) for p in PREFIXOS_DE_REGUA)
        ]
    if (raiz / A_PONTE_JS).is_file():
        achadas.append(A_PONTE_JS)
    return achadas


def na_arvore_principal(raiz: Path) -> bool:
    """Árvore principal ou worktree ligada?"""
    proprio = _git(raiz, "rev-parse", "--absolute-git-dir")
    comum = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not proprio or not comum:
        return True
    return Path(proprio).resolve() == Path(comum).resolve()


def _bloco(raiz: Path, desenho: list[str], abas: list[str]) -> str:
    quais = ", ".join(abas) if abas else "—"
    linhas = [
        "",
        "régua de tela: este commit MEXE NA TELA e não traz régua nenhuma.",
        "",
    ]
    for c in desenho[:8]:
        linhas.append(f"    {c}")
    if len(desenho) > 8:
        linhas.append(f"    ... e mais {len(desenho) - 8}")
    linhas += [
        "",
        f"  Abas tocadas: {quais}",
        "",
        "  A pergunta, e ela é dela (29/08/2026): existe validação que prove que",
        "  isto ficou de pé — e que avise se amanhã alguém o desfizer?",
        "",
        "  A interface nova roda num `WebKit2.WebView`, então ela é DIRIGÍVEL por",
        "  dentro: `run_javascript` clica com `el.click()` (o mesmo caminho de",
        "  eventos de um clique real), lê o DOM e mede geometria; o",
        "  `register_script_message_handler` traz a resposta ao Python. Validar",
        "  comportamento é clicar e conferir, não fotografar.",
        "",
    ]
    if (raiz / O_MANUAL).is_file():
        linhas += [
            "  POR ONDE COMEÇAR — o vocabulário, os dois instrumentos e os sete",
            "  defeitos de tela que esta casa já pagou, cada um virando um caso:",
            f"    {O_MANUAL}",
            "",
        ]
    disco = reguas_no_disco(raiz)
    biblioteca = [r for r in disco if r == O_INSTRUMENTO]
    do_mockup = [r for r in disco if r != O_INSTRUMENTO]
    if biblioteca:
        linhas.append(
            "  A BIBLIOTECA — importe-a de um `tests/unit/test_*.py` e dirija o"
        )
        linhas.append("  motor que ela vai usar (`Tela.abrir`, `clicar_e_ouvir`):")
        linhas += [f"    {r}" for r in biblioteca]
        linhas.append("")
    if do_mockup:
        linhas.append(
            "  AS RÉGUAS DO MOCKUP — Playwright/Chrome sobre o desenho, para"
        )
        linhas.append("  layout e `:hover`. Não alcançam o WebView do produto:")
        linhas += [f"    {r}" for r in do_mockup]
    if not disco:
        linhas.append("  Não achei régua nenhuma em `src/hefesto_dualsense4unix/interface/`.")
    linhas += [
        "",
        "  E ela precisa MORDER: régua desta casa já nasceu falsa duas vezes (as",
        "  cicatrizes do `src/hefesto_dualsense4unix/interface/LEIA-ME.md`), e em 29/08 o",
        "  `--prova-gesto` deu VERDE sobre dois botões que nunca clicava. Arranque",
        "  a cura, veja a régua reprovar, devolva.",
        "",
        "  Este aviso NÃO segura o commit (grau 1). Ele volta calado no próximo",
        "  commit que trouxer régua.",
        "",
    ]
    return "\n".join(linhas)


def _o_ponto_cego(raiz: Path) -> None:
    """O que gancho NENHUM pode ver — e por que calar sobre isso seria mentir."""
    ignorada = (
        subprocess.run(
            ["git", "check-ignore", "-q", "layout"],
            cwd=str(raiz),
            capture_output=True,
        ).returncode
        == 0
    )
    if not ignorada:
        return
    conhecidos = len([x for x in _git(raiz, "ls-files", "layout").splitlines() if x])
    if conhecidos:
        return
    print("PONTO CEGO, e ele é maior que este portão:")
    print("  `layout/` é `.gitignore:108` — o git conhece 0 arquivo lá e")
    print("  0 commit da história tocou a pasta. O mockup, os geradores `abaNN.py`,")
    print("  as réguas do Playwright e o piloto da ponte JS NUNCA entram num")
    print("  índice, e um `pre-commit` só julga o índice.")
    print()
    print("  Então este portão cobre o lado VERSIONADO da tela — `src/…/app`,")
    print("  `src/…/interface`, `src/…/gui` — e credita a régua versionada")
    print("  `scripts/regua_de_tela.py`. Sobre o mockup ele é mudo, e nenhum")
    print("  gancho pode deixar de ser.")
    print()
    print("  A saída, se ela quiser cobertura ali, é DELA e é de versionamento,")
    print("  não de gancho: tirar `layout/` do `.gitignore`, ou mover para")
    print("  `scripts/` o que for instrumento permanente — que foi exatamente o")
    print("  argumento com que `scripts/regua_de_tela.py` nasceu fora da pasta.")
    print()


def _diagnostico(raiz: Path) -> int:
    """O gancho deste repositório RODA nesta árvore? A resposta costuma ser não."""
    principal = na_arvore_principal(raiz)
    comum = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    local = raiz / ".git" / "hooks" / "pre-commit"
    encadeado = local.is_file() and __import__("os").access(local, __import__("os").X_OK)

    print(f"árvore .......... {raiz}")
    print(f"tipo ............ {'principal' if principal else 'worktree ligada'}")
    print(f"git-common-dir .. {comum}")
    print(f"o global procura  {local}")
    print(f"e acha? ......... {'SIM' if encadeado else 'NÃO'}")
    print()
    _o_ponto_cego(raiz)
    if encadeado:
        print("O gancho do repositório RODA nesta árvore.")
        return 0
    print("O gancho do repositório NÃO RODA nesta árvore, e nada avisa disso.")
    print()
    print("  Numa worktree ligada o `.git` é um ARQUIVO (`gitdir: …`), então o")
    print("  caminho que o gancho global testa não pode existir. Cai fora TODO o")
    print("  gancho deste repositório: o mapa de canais (docs/specs.html), o contrato")
    print("  IPC, as citações `arquivo:linha` e o portão da foto.")
    print()
    print("  O conserto é de UMA linha, e é DELA: o arquivo é global e vale para")
    print("  todo repositório dela. Em ~/.config/git/hooks/pre-commit:")
    print()
    print('    -LOCAL_HOOK="$REPO_ROOT/.git/hooks/pre-commit"')
    print('    +LOCAL_HOOK="$(git rev-parse --path-format=absolute'
          ' --git-common-dir)/hooks/pre-commit"')
    print()
    print("  Na árvore principal os dois dão o MESMO caminho — medido — então a")
    print("  troca não muda nada do que já funciona.")
    return 0


def _censo(raiz: Path, quantos: int = 50) -> int:
    """O número que autoriza subir de degrau. Ver "A ESCADA" no topo."""
    shas = [s for s in _git(raiz, "log", "--format=%H", f"-{quantos}").splitlines() if s]
    tocam = com = 0
    for sha in shas:
        veredito, _, _, _ = julgar(caminhos_do_commit(raiz, sha))
        if veredito == COM_REGUA:
            tocam += 1
            com += 1
        elif veredito in (SEM_REGUA, SEM_REGUA_DE_NOVO):
            tocam += 1
    print(f"últimos {len(shas)} commits (merges não contam: o git não lhes roda `pre-commit`)")
    print(f"  tocam a tela .......... {tocam}")
    print(f"  destes, com régua ..... {com}")
    if tocam:
        print(f"  proporção ............. {100 * com // tocam}%")
        print()
        print(f"  Grau atual: {GRAU}. O grau 3 (reprovar) pede que a MAIORIA já")
        print("  traga régua — reprovar a maioria é o portão que morre na segunda.")
    else:
        print("  nenhum commit da janela tocou a tela; sem número para decidir.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    raiz_texto = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if not raiz_texto:
        return 0
    raiz = Path(raiz_texto)

    if "--diagnostico" in args:
        return _diagnostico(raiz)
    if "--censo" in args:
        return _censo(raiz)

    verboso = "--verboso" in args
    veredito, desenho, reguas, abas = julgar(
        caminhos_no_indice(raiz), abas_devidas_pelo_head(raiz)
    )

    if veredito in (EM_BRANCO, SO_REGUA):
        return 0

    if veredito == COM_REGUA:
        if verboso:
            print(
                "régua de tela: o commit mexe na tela e traz régua — "
                + ", ".join(reguas[:3]),
                file=sys.stderr,
            )
        return 0

    if veredito == SEM_REGUA_DE_NOVO:
        print(
            "régua de tela: as abas "
            + ", ".join(abas)
            + " seguem sem régua (o aviso inteiro saiu no commit anterior).",
            file=sys.stderr,
        )
        return 0

    print(_bloco(raiz, desenho, abas), file=sys.stderr)
    return VEREDITO_REPROVA if GRAU >= 3 else 0


if __name__ == "__main__":
    raise SystemExit(main())
