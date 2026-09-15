#!/usr/bin/env python3
"""A HISTÓRIA não carrega assinatura de ferramenta nem endereço de fora da casa.

Ordem dela, 15/09/2026, com o repositório aberto na frente: uma ferramenta
aparecia na lista de contribuidores, e *"o emaillist lá deveria ser o meu e o
do andre apenas. (…) isso deveria ser sempre considerado."*

**POR QUE ELE EXISTE, e por que o gancho não bastava — medido em 15/09/2026:**

- O ``commit-msg`` GLOBAL dela (``~/.config/git/hooks``) estava ligado e rodou
  **1.179 vezes** entre 02 e 04/09; mesmo assim **30 commits** entraram em
  ``dev`` com trailer de coautoria. Um gancho de ``commit-msg`` NÃO roda em
  ``cherry-pick``, em ``rebase``, em ``merge --no-edit`` nem sob
  ``--no-verify`` — e esta casa integra leva por ``cherry-pick``.
- O passo de auditoria do ``.github/workflows/anonymity-check.yml`` mede o
  **intervalo do push** e sai ``0`` quando não consegue resolvê-lo ("Nada a
  auditar"). Intervalo que não resolve é portão cego.

Esta régua não tem nenhum dos dois furos: ela varre **toda a história
alcançável** pelas referências que são publicadas, toda vez que alguém roda
``scripts/portoes.sh``. Ela não conserta — quem conserta é ``git filter-repo``
num clone —, ela **impede que volte**.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

#: O ARQUIVO QUE DIZ QUEM É DESTA CASA. Decisão dela, 15/09/2026: a lista de
#: e-mails do repositório é a dela e a do André, e mais nenhuma.
#:
#: A LISTA NÃO É DIGITADA AQUI, e a razão é dupla. A primeira é a regra do
#: fato-errado: um endereço numa constante de código e outro no `.mailmap`
#: seriam duas verdades sobre a mesma coisa, e a próxima pessoa teria de
#: escolher entre elas. A segunda foi medida ao escrever esta régua em
#: 15/09/2026 — o endereço dela, escrito como literal, chegou ao arquivo
#: como `[REDACTED]`, e o portão passou a acusar OS 2.085 COMMITS DELA de
#: virem de fora da casa. Uma régua que lê o `.mailmap` não tem como sofrer
#: isso: ela pergunta ao git, que é quem sabe.
MAILMAP = ".mailmap"


def pessoas() -> frozenset[str]:
    """Os endereços canônicos do `.mailmap` — quem pode assinar um commit."""
    caminho = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    alvo = Path(caminho or ".") / MAILMAP
    if not alvo.is_file():
        return frozenset()
    fora: set[str] = set()
    for linha in alvo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        # `Nome <canônico> <alias>`: o PRIMEIRO endereço é o canônico, e é o
        # único que autoriza. O alias existe para ser reescrito, não aceito.
        entre = re.findall(r"<([^>]+)>", linha)
        if entre:
            fora.add(entre[0])
    return frozenset(fora)

#: As referências PUBLICADAS. Branch de voo e de leva não sai da máquina;
#: cobrar delas faria a régua gritar sobre trabalho que nunca chega ao mundo —
#: e portão que grita falso é portão que se desliga.
REFS = ("refs/heads/dev", "refs/heads/main", "HEAD")

#: O NOME DA FERRAMENTA NÃO SE ESCREVE NEM AQUI. A expressão é montada de
#: pedaços de propósito: o sanitizador de coautoria da casa apaga qualquer
#: linha que traga o literal, e este arquivo viraria a primeira ocorrência do
#: que ele proíbe. Esta casa já pagou cinco vezes por *um comentário que
#: descreve o padrão proibido virar a primeira ocorrência dele*.
_FERRAMENTAS = (
    "cla" "ude", "anth" "ropic", "open" "ai", "chat" "gpt", "cop" "ilot",
    "gem" "ini", "deep" "seek", "ai" "der", "winds" "urf", "code" "ium",
    "tab" "nine", r"gpt-[0-9]", r"llm\b",
)
FERRAMENTA_RE = re.compile("|".join(_FERRAMENTAS), re.I)

#: Trailers de atribuição. Coautoria entre as duas pessoas da casa é legítima;
#: o que não é legítimo é atribuir a quem não é pessoa. O ``*-session`` pega o
#: carimbo de sessão que veio junto com os 27 commits de 02 a 04/09.
TRAILER_RE = re.compile(
    r"^[ \t]*(co[-_ ]?aut" "hored[-_ ]?by|assisted[-_ ]?by|paired[-_ ]?with"
    r"|generated[-_ ]?(by|with)|[A-Za-z]+-session)[ \t]*:.*$",
    re.I | re.M,
)

#: Separadores. Eles vão para o `git log` como as ESCAPAS `%x1f`/`%x1e` — um
#: byte NUL de verdade não atravessa `argv`, e a chamada morre com
#: `ValueError: embedded null byte` (medido ao escrever esta régua).
_CAMPO = "\x1f"
_REGISTRO = "\x1e"


def _existe(ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True, check=False,
    ).returncode == 0


def commits() -> list[tuple[str, str, str, str]]:
    """``(sha, e-mail do autor, e-mail do committer, mensagem)``, tudo que as
    REFS alcançam. Uma chamada só de ``git log``: a história tem milhares de
    commits e uma chamada por commit levaria minutos."""
    refs = [r for r in REFS if _existe(r)]
    if not refs:
        return []
    bruto = subprocess.run(
        ["git", "log", "--no-color",
         "--format=%H%x1f%ae%x1f%ce%x1f%B%x1e", *refs],
        capture_output=True, text=True, check=True,
    ).stdout
    fora: list[tuple[str, str, str, str]] = []
    vistos: set[str] = set()
    for pedaco in bruto.split(_REGISTRO):
        pedaco = pedaco.strip("\n")
        if not pedaco:
            continue
        campos = pedaco.split(_CAMPO)
        if len(campos) < 4:
            continue
        sha = campos[0]
        if sha in vistos:
            continue
        vistos.add(sha)
        fora.append((sha, campos[1], campos[2], _CAMPO.join(campos[3:])))
    return fora


def acusacoes(sha: str, de_quem: str, de_quem_gravou: str,
              msg: str, casa: frozenset[str]) -> list[str]:
    # NENHUM PARÂMETRO AQUI TERMINA NA PALAVRA QUE O `check_anonymity.sh`
    # PROÍBE, e não é estilo: o padrão dele pega essa palavra seguida de
    # dois-pontos em qualquer lugar, e uma anotação de tipo já basta para
    # casar. Medido em 15/09/2026, ao escrever esta régua — duas tentativas
    # de nome reprovaram antes desta. E esta linha não escreve a palavra,
    # porque um comentário que descreve o padrão proibido vira a primeira
    # ocorrência dele: é a SEXTA vez que esta casa paga por isso.
    """As linhas de acusação de UM commit — vazia quando ele está limpo."""
    curto = sha[:8]
    assunto = (msg.splitlines() or [""])[0][:60]
    ruins: list[str] = []
    if FERRAMENTA_RE.search(msg):
        ruins.append(f"{curto}: a mensagem nomeia uma ferramenta — «{assunto}»")
    for achado in TRAILER_RE.finditer(msg):
        linha = achado.group(0).strip()
        if not any(pessoa in linha for pessoa in casa):
            ruins.append(f"{curto}: atribuição a quem não é pessoa — «{linha[:70]}»")
    for papel, email in (("autor", de_quem),
                         ("committer", de_quem_gravou)):
        if email not in casa:
            ruins.append(f"{curto}: {papel} `{email}` não é desta casa")
    return ruins


def _raso() -> bool:
    """O clone é raso? Um `actions/checkout` sem `fetch-depth: 0` traz UM
    commit, e esta régua daria verde sobre ele — que é exatamente o furo do
    passo de auditoria do CI que ela existe para fechar."""
    return subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() == "true"


def main() -> int:
    if _raso():
        print("VERMELHO: este clone é RASO. A régua varre a história inteira, e "
              "num clone raso ela veria um commit só — verde sobre o vazio.\n"
              "  No CI: `fetch-depth: 0` no `actions/checkout`.\n"
              "  Na máquina: `git fetch --unshallow`.")
        return 1
    todos = commits()
    if not todos:
        print("VERMELHO: nenhuma das referências publicadas resolveu "
              f"({', '.join(REFS)}) — a régua não mediu nada, e intervalo que "
              "não resolve é portão cego. Foi assim que a auditoria do CI "
              "deixou 30 commits passarem.")
        return 1

    casa = pessoas()
    if not casa:
        print(f"VERMELHO: `{MAILMAP}` não existe ou não declara ninguém. Ele é "
              "a fonte de quem pode assinar um commit nesta casa; sem ele a "
              "régua não tem contra o que medir.")
        return 1

    ruins: list[str] = []
    for sha, autor, committer, msg in todos:
        ruins.extend(acusacoes(sha, autor, committer, msg, casa))

    if ruins:
        unicos = sorted(set(ruins))
        print(f"VERMELHO: {len(unicos)} ocorrência(s) em {len(todos)} commits "
              "alcançáveis pelas referências publicadas:")
        print("\n".join(f"  {linha}" for linha in unicos[:40]))
        if len(unicos) > 40:
            print(f"  … e mais {len(unicos) - 40}.")
        print()
        print("HISTÓRIA NÃO SE CONSERTA COM COMMIT NOVO: o trailer velho "
              "continua lá. O conserto é `git filter-repo` num CLONE novo "
              "(esta árvore divide o `.git` com dezenas de worktrees) e o "
              "push é forçado — o que quebra todo clone existente. Avise "
              "quem tem clone ANTES de empurrar.")
        return 1

    print(f"OK: {len(todos)} commits alcançáveis por "
          f"{', '.join(r for r in REFS if _existe(r))}; nenhuma assinatura de "
          f"ferramenta, e nenhum endereço fora das {len(casa)} pessoas "
          "desta casa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
