#!/usr/bin/env python3
"""O item 3 do checklist de fim de leva, executável — FOTO-NO-GANCHO-01.

**O defeito, medido em 24/08/2026.** A regra "fotografe se a mudança tocou a
tela" está escrita em três lugares — `COMO-COORDENAR-UMA-LEVA.md` (checklist de
fim de leva, item 3), `OS-PAPEIS-DESTA-CASA.md` e `COMO-EXECUTAR-UMA-SPRINT.md`
— e é do coordenador. Na integração da Onda 0 o coordenador furou a ORDEM do
próprio checklist: commitou (passo 5) antes de fotografar (passo 3), e nove
branches de interface entraram em `dev` sem ninguém abrir a tela. Prosa não
impede.

**Por que o portão que já existia chegou tarde.** O
`tests/unit/test_as_fotos_acompanham_a_versao.py` PEGOU o erro — mas só roda na
suíte inteira, de ~8 min, que o coordenador roda DEPOIS de commitar. Portão
certo, hora errada. Este arquivo faz a MESMA pergunta no `pre-commit`, em ~25
ms, antes de o commit existir.

O QUE ELE MEDE, e por que são DUAS perguntas
--------------------------------------------

1. **Este commit mexe na tela sem levar a prova junto?** Mexe na tela = algum
   caminho do índice cai em `CODIGO_DA_TELA`; prova = algum caminho do índice
   cai em `FOTOS`.
2. **A dívida já está em `HEAD`?** A mesma topologia que o portão da suíte
   mede: o último commit que tocou o código da tela é ancestral do último que
   tocou as fotos?

A segunda pergunta existe porque a primeira, sozinha, **não teria pego a Onda
0**. MEDIDO: a Onda 0 entrou por NOVE commits de merge (`cf78346`, `0c99242`,
`f9240b5`, `15b5ff5`, `4f7cece`, `ed79255`, `2d83432`, `7bf4f25`, `9b4e5a0`),
e o git não roda `pre-commit` em commit de merge — roda `pre-merge-commit`,
que ninguém instalou. Um gancho que só olhasse o índice teria deixado passar
os nove e depois aprovado o commit de fim de leva, que não toca `app/`.

Com a segunda pergunta, os merges continuam passando **e a dívida é cobrada no
commit seguinte**, que é o passo 5 do checklist — exatamente onde o passo 3 foi
pulado.

O `PROVA-DA-FOTO.txt` mora dentro de `FOTOS` e carrega a data do ensaio, então
**rodar o retrato sempre produz a prova**, mesmo quando nenhum pixel se mexe.
Não existe estado sem saída aqui.

AS FAMÍLIAS DE FOTO SÃO DUAS — 11/09/2026, e a pergunta é uma por pasta
-----------------------------------------------------------------------

`docs/usage/assets/maximizada/` nasceu na PRINTS-DAS-DEZ-01 com as dez abas na
vista maximizada dela, e **abriu buraco nas duas perguntas acima**: as duas
casavam `docs/usage/assets` por PREFIXO, e a subpasta cai dentro. Medido pelo
conferente no mesmo dia, `julgar(['src/.../aba01.py',
'docs/usage/assets/maximizada/aba-01-jogar.png'])` devolvia `em-dia` — gravar
só na pasta nova QUITAVA a dívida das dez do README, que podiam apodrecer
caladas.

Cada família responde por si (`familias_sem_prova`, `_uma_familia_em_dia`), o
bloqueio NOMEIA a pasta devedora, e `_CURA` traz o comando daquela pasta — sem
ele quem apanhasse pela vista rodaria o comando do README, veria nada mudar, e
concluiria que o portão quebrou.

ONDE ELE SE CALA DE PROPÓSITO
-----------------------------

**Em worktree de agente.** Fotografar é de quem coordena (R4 de
COMO-REGER-AGENTES.md), e o agente de sprint tem o retratista na lista do
que **não** pode rodar (era `retratar_abas.py`, apagado com a janela GTK em
06/09/2026; hoje é `interface/olhar.py --todas --publicado --doc`). Cobrar foto
dele seria cobrar o que ele está proibido de fazer, e o preço seria o gancho
desinstalado. O gancho só fala na árvore
principal — a de quem integra. A distinção é `--git-dir` contra
`--git-common-dir`, que só divergem em worktree ligada.

O QUE ELE **NÃO** MEDE
----------------------

* **Não olha a foto.** Não diz que a imagem está certa, nem que o desenho novo
  presta — isso é o olho dela (PROVA-DE-TELA-01). É medida de PROCEDÊNCIA.
* **Não prova que o script rodou.** Uma linha escrita à mão no `CONFERIDO-EM.md`
  satisfaz o gancho. É deliberado: aquele arquivo É o registro de conferência
  desta casa, e fechar essa porta obrigaria a inventar outra.
* **Não impede o merge**, só cobra no commit seguinte. Entre um e outro a
  dívida existe e nada a segura — quem só faz merges e nunca commita passa
  inteiro por aqui.
* **Não vê `rebase` nem `cherry-pick`**, onde o git pula os ganchos; nem
  `--no-verify`; nem quem nunca rodou `scripts/instalar-hooks.sh`.
* **Foto suja na árvore desarma o bloqueio** (`CURA_EM_CURSO`), e quem deixar
  `docs/usage/assets` permanentemente sujo nunca apanha aqui. É o mesmo perdão
  — e o mesmo buraco — do `fotos_sendo_refeitas_agora` no portão da suíte;
  fechá-lo só aqui puniria justamente quem acabou de rodar o retrato.
* **Não cobre tela fora dos três diretórios** de `CODIGO_DA_TELA` (um texto de
  aba que morasse em `daemon/`, por exemplo).

Em todos esses buracos quem responde continua sendo o portão da suíte, que não
depende de gancho instalado nem de qual worktree é.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

#: As fotos que o `interface/olhar.py --todas --publicado --doc` grava, mais os dois
#: recibos que moram junto delas (`PROVA-DA-FOTO.txt`, `CONFERIDO-EM.md`).
FOTOS = "docs/usage/assets"

#: A SEGUNDA FAMÍLIA — 11/09/2026, e ela abriu buraco neste portão e no irmão.
#:
#: `docs/usage/assets/maximizada/` guarda as dez abas na vista maximizada dela
#: (`--vista dela`, 1918x840) e cai DENTRO de `FOTOS` quando a pergunta casa
#: por prefixo. Medido pelo conferente:
#: `julgar(['src/.../aba01.py', 'docs/usage/assets/maximizada/aba-01-jogar.png'])`
#: devolvia `em-dia` — gravar só na pasta nova QUITAVA a dívida das dez do
#: README, que podiam apodrecer caladas.
#:
#: A cura é a mesma dos dois lados: cada família responde por si, e foto de uma
#: nunca paga a dívida da outra. Cópia deliberada de `FAMILIAS_DE_FOTO` do
#: `test_as_fotos_acompanham_a_versao.py`, e
#: `test_as_duas_listas_de_codigo_de_tela_sao_a_mesma` tranca as duas juntas.
FOTOS_DA_VISTA = f"{FOTOS}/maximizada"

#: Toda família de foto desta casa, da mais externa para a mais interna.
FAMILIAS_DE_FOTO = (FOTOS, FOTOS_DA_VISTA)

#: O que, mudando, torna as fotos suspeitas. Cópia deliberada de
#: `CODIGO_DA_TELA` do `test_as_fotos_acompanham_a_versao.py`, e o
#: `test_o_gancho_cobra_a_foto_da_tela.py` tranca as duas juntas: um gancho
#: mais severo que o portão que ele antecipa reclamaria de commit que a suíte
#: aprova, e portão que reclama sem razão ensina a ignorar portão.
CODIGO_DA_TELA = (
    # A INTERFACE NOVA ENTROU EM 05/09/2026, e a ausência dela estava medida:
    # mexer nas dez abas que o lançador abre não tornava foto nenhuma suspeita,
    # e mexer no motor VELHO obrigava a refotografar a janela velha — o portão
    # cobrava a foto errada e era cego à certa. O irmão que cobra RÉGUA de tela
    # (`scripts/check_regua_de_tela.py`) recebeu esta mesma linha em 03/09 com a
    # mesma razão; o da FOTO não tinha ido junto.
    #
    # Quem tira a foto das dez é `interface/olhar.py --todas --publicado --doc`,
    # e ele mora DENTRO desta pasta: mudar o retratista torna as fotos suspeitas
    # sem precisar de uma quinta entrada.
    "src/hefesto_dualsense4unix/interface",
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/gui",
)

#: O `git` responde por esta árvore vazia quando ainda não há `HEAD`.
ARVORE_VAZIA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

EM_BRANCO = "em-branco"
"""Nada a cobrar: o commit não toca a tela e a história está em dia."""

EM_DIA = "em-dia"
"""O commit leva a prova junto. O caminho bom, e ele quita dívida herdada."""

CURA_EM_CURSO = "cura-em-curso"
"""Toca a tela, não leva a prova, mas as fotos estão sujas na árvore.

O mesmo perdão que `fotos_sendo_refeitas_agora` dá no portão da suíte: quem
acabou de rodar o retrato ainda não commitou as imagens. Avisa e deixa passar.
"""

BLOQUEADO = "bloqueado"
"""Toca a tela, não leva a prova, e não há foto nenhuma em curso."""

DIVIDA_HERDADA = "divida-herdada"
"""O commit não toca a tela, mas `HEAD` já está devendo foto.

É o caso da Onda 0: nove merges trouxeram interface, nenhum passou por gancho
nenhum, e o commit de fim de leva não toca `app/`. Sem isto, o gancho aprovaria
o commit que fecha a leva com a foto atrasada — que é o defeito inteiro.
"""


def _toca(caminho: str, prefixos: Iterable[str]) -> bool:
    return any(caminho == p or caminho.startswith(p + "/") for p in prefixos)


def familia_de(caminho: str) -> str | None:
    """A família de foto a que este caminho pertence — a MAIS INTERNA que o cobre.

    `docs/usage/assets/maximizada/aba-01-jogar.png` é da família da VISTA, não
    da do README, e é essa distinção que fecha o buraco de 11/09/2026: sem ela
    a foto da pasta nova contava como prova das dez do README.
    """
    cobrem = [f for f in FAMILIAS_DE_FOTO if _toca(caminho, (f,))]
    return max(cobrem, key=len) if cobrem else None


def _pathspec(familia: str) -> list[str]:
    """Os caminhos que são DESTA família e de nenhuma outra, para o `git log`.

    Quem recorta é o `:(exclude)` do git, e não um filtro escrito à mão — um
    segundo recorte escrito à mão é uma segunda régua a divergir.
    """
    return [familia] + [
        f":(exclude){outra}"
        for outra in FAMILIAS_DE_FOTO
        if outra != familia and outra.startswith(familia + "/")
    ]


def familias_sem_prova(no_indice: Iterable[str]) -> list[str]:
    """As famílias de foto que este commit NÃO carrega — o buraco de 11/09/2026.

    Antes desta função a pergunta era uma só (*"tem alguma coisa em
    `docs/usage/assets`?"*), e a pasta `maximizada/` cai dentro dela por
    prefixo: uma foto da vista quitava a dívida das dez do README. Agora cada
    família precisa da sua própria prova, e o bloqueio NOMEIA a que falta.

    **Não é severidade a mais: é a mesma pergunta que o portão da suíte passou
    a fazer** (`test_as_fotos_acompanham_a_versao.fotos_em_dia`, por família).
    Um gancho mais frouxo que o portão que ele antecipa promete cobrir o que
    não cobre, e deixaria a dívida aparecer só no vermelho da suíte — que é o
    defeito que este arquivo inteiro existe para adiantar.
    """
    com_prova = {familia_de(c) for c in no_indice} - {None}
    return [f for f in FAMILIAS_DE_FOTO if f not in com_prova]


def comando_da_familia(familia: str) -> str:
    """O gesto EXATO que refaz aquela pasta — sem ele o bloqueio não é acionável."""
    sufixo = " --vista dela" if familia == FOTOS_DA_VISTA else ""
    return (
        f"    src/hefesto_dualsense4unix/interface/olhar.py "
        f"--todas --publicado --doc{sufixo}\n    git add {familia}"
    )


def julgar(
    no_indice: Iterable[str],
    fotos_sujas: bool,
    historia_em_dia: bool | None,
) -> tuple[str, list[str]]:
    """O veredito, sem git nenhum: só caminhos e dois estados.

    `historia_em_dia` é `None` quando não dá para saber (sem `HEAD`, clone
    raso, ou um dos dois lados nunca commitado) — e aí a segunda pergunta se
    cala, como no portão da suíte.

    Devolve o veredito e a lista de arquivos de tela que o motivaram, que é o
    que a mensagem precisa mostrar para ser acionável.
    """
    caminhos = list(no_indice)
    de_tela = sorted(c for c in caminhos if _toca(c, CODIGO_DA_TELA))

    if not familias_sem_prova(caminhos):
        return EM_DIA, de_tela
    if de_tela:
        return (CURA_EM_CURSO if fotos_sujas else BLOQUEADO), de_tela
    if historia_em_dia is False and not fotos_sujas:
        return DIVIDA_HERDADA, []
    return EM_BRANCO, []


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(
        ["git", *args], cwd=str(raiz), capture_output=True, text=True
    )
    if saida.returncode != 0:
        return ""
    return saida.stdout.strip()


def na_arvore_principal(raiz: Path) -> bool:
    """Esta é a árvore de quem coordena, ou uma worktree de agente?

    Em worktree ligada o `--git-dir` aponta para `.git/worktrees/<nome>` e o
    `--git-common-dir` para o `.git` de origem; na principal os dois são o
    mesmo diretório.
    """
    proprio = _git(raiz, "rev-parse", "--absolute-git-dir")
    comum = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not proprio or not comum:
        return True  # na dúvida, fala: calar é que seria o buraco
    return Path(proprio).resolve() == Path(comum).resolve()


def caminhos_no_indice(raiz: Path) -> list[str]:
    """O que este commit vai carregar. Sem `HEAD`, compara com a árvore vazia."""
    contra = "HEAD" if _git(raiz, "rev-parse", "--verify", "HEAD") else ARVORE_VAZIA
    saida = _git(raiz, "diff", "--cached", "--name-only", contra)
    return [linha for linha in saida.splitlines() if linha]


def fotos_sujas(raiz: Path) -> bool:
    """Alguma imagem está modificada na árvore? `--porcelain` responde por conteúdo."""
    return bool(_git(raiz, "status", "--porcelain", "--", FOTOS))


def _uma_familia_em_dia(raiz: Path, familia: str) -> bool | None:
    """A topologia de UMA família: a foto dela veio depois da mexida na tela?"""
    das_fotos = _git(raiz, "log", "-1", "--format=%H", "--", *_pathspec(familia))
    do_codigo = _git(raiz, "log", "-1", "--format=%H", "--", *CODIGO_DA_TELA)
    if not das_fotos or not do_codigo:
        return None
    if das_fotos == do_codigo:
        return True
    pergunta = subprocess.run(
        ["git", "merge-base", "--is-ancestor", do_codigo, das_fotos],
        cwd=str(raiz),
        capture_output=True,
    )
    return pergunta.returncode == 0


def historia_em_dia(raiz: Path) -> bool | None:
    """`HEAD` já deve foto? A MESMA topologia do portão da suíte, POR FAMÍLIA.

    Data de commit mentiria — um `rebase` reescreve a ordem sem reescrever os
    carimbos, e dois commits podem carregar o mesmo segundo. A pergunta certa é
    "o commit do código é ancestral do commit das fotos?".

    **E ela é uma por PASTA desde 11/09/2026.** Perguntada sobre
    `docs/usage/assets` inteiro, o `git log` responde com o commit que tocou
    `docs/usage/assets/maximizada/` — e a dívida das dez do README ficava
    quitada por foto que não é delas, para sempre e sem ninguém ver. Uma
    família atrasada reprova por todas; uma que não dá para medir se cala.
    """
    vereditos = [_uma_familia_em_dia(raiz, f) for f in FAMILIAS_DE_FOTO]
    if any(v is False for v in vereditos):
        return False
    if all(v is None for v in vereditos):
        return None
    return True


_CURA = (
    "  Cure rodando o retrato — uma execução por família, nenhum clique:\n"
    + "\n".join(comando_da_familia(f) for f in FAMILIAS_DE_FOTO)
    + "\n"
    "\n  Se as imagens saírem iguais, o recibo `PROVA-DA-FOTO.txt` muda "
    "sozinho\n"
    "  e já serve de prova; se saírem diferentes, OLHE-AS antes de commitar —\n"
    "  mudança de desenho é palavra dela (PROVA-DE-TELA-01).\n"
    "\n  Este gancho não tem chave própria de propósito. `git commit "
    "--no-verify`\n"
    "  passa, e aí quem cobra é `test_as_fotos_acompanham_a_versao.py` na "
    "suíte."
)


def main(argv: list[str] | None = None) -> int:
    del argv
    raiz_texto = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if not raiz_texto:
        return 0  # fora de repositório não há índice para julgar
    raiz = Path(raiz_texto)

    if not na_arvore_principal(raiz):
        return 0  # worktree de agente: fotografar é de quem coordena

    veredito, de_tela = julgar(
        caminhos_no_indice(raiz), fotos_sujas(raiz), historia_em_dia(raiz)
    )

    if veredito in (EM_BRANCO, EM_DIA):
        return 0

    if veredito == CURA_EM_CURSO:
        print(
            "portão das fotos: este commit mexe na tela e não leva foto — mas "
            f"há imagem modificada em `{FOTOS}`.\n"
            "  Passando: a cura está em curso. Mas ela está FORA deste "
            f"commit —\n    git add {FOTOS}\n"
            "  antes de commitar, ou a foto fica para trás e a suíte cobra.",
            file=sys.stderr,
        )
        return 0

    if veredito == DIVIDA_HERDADA:
        atrasadas = [
            f for f in FAMILIAS_DE_FOTO if _uma_familia_em_dia(raiz, f) is False
        ]
        das_fotos = _git(
            raiz, "log", "-1", "--format=%h", "--", *_pathspec(atrasadas[0])
        )
        do_codigo = _git(raiz, "log", "-1", "--format=%h", "--", *CODIGO_DA_TELA)
        print(
            "pre-commit: BLOQUEADO — a tela mudou em "
            f"{do_codigo} e as fotos de `{'`, `'.join(atrasadas)}` "
            f"são de {das_fotos}, que veio ANTES.\n"
            "  Este commit não tem culpa, mas a dívida é de agora: os merges "
            "de leva\n"
            "  não passam por gancho nenhum, e este é o primeiro commit "
            "depois deles.\n",
            file=sys.stderr,
        )
        print(_CURA, file=sys.stderr)
        return 1

    faltando = familias_sem_prova(caminhos_no_indice(raiz))
    print(
        "pre-commit: BLOQUEADO — este commit mexe no código da tela e não leva "
        f"a foto de `{'`, `'.join(faltando)}`.\n",
        file=sys.stderr,
    )
    for caminho in de_tela[:10]:
        print(f"    {caminho}", file=sys.stderr)
    if len(de_tela) > 10:
        print(f"    ... e mais {len(de_tela) - 10}", file=sys.stderr)
    print("", file=sys.stderr)
    print(_CURA, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
