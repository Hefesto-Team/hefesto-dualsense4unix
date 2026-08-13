"""As fotos da documentação defasaram em silêncio — FOTOS-DA-VERSAO-01.

O `CLAUDE.md` manda, com todas as letras: *"Antes de gerar release, rode de
novo: as imagens acompanham a versão"*. Não havia portão nenhum segurando isso,
e o resultado, medido em 13/08/2026 sobre a tag `v0.9.4.2`:

* último commit que tocou `docs/usage/assets/`: `0c4164e`, 12/08 00:38:35;
* commits que tocaram `app/` ou `gui/` DEPOIS dele: `f1279a1` (12/08 00:49),
  `0b010bd` (13/08 00:41) e `973c92c` (13/08 02:00);
* e a tag saiu às 02:26.

Ou seja: a release foi publicada com fotos anteriores a três levas de
interface. Ninguém percebeu porque nada mede isto — o script grava dez PNGs e
não reclama de nada.

O QUE ESTE TESTE **NÃO** AFIRMA
-------------------------------

Ele não diz que a foto está errada — diz que ela não foi **conferida** depois da
última mexida na interface. É medida de PROCEDÊNCIA, não de conteúdo: as duas
coisas se separam, e a diferença foi medida no mesmo dia. Regeradas com o
código de `cc768d4`, NOVE das dez imagens saíram **byte a byte idênticas** às
commitadas — os três commits acima não mudaram um pixel de aba nenhuma. A
defasagem era real e o dano, nenhum. Mas isso só se sabe **depois** de rodar o
script, que é exatamente o gesto que este teste cobra.

Comparar o conteúdo em vez da procedência não serve como portão: a `readme_inicio.png`
sai com ~45 mil pixels diferentes entre DUAS execuções seguidas do mesmo
script, no mesmo processo e no mesmo tema (ruído de gradiente nos botões
segmentados, invisível a olho). Um portão sobre bytes de PNG seria vermelho
sem defeito.

A MORDIDA
---------

Está no `test_o_portao_acusa_foto_atrasada`, que constrói um repositório de
mentira em `tmp_path` com a ordem errada e exige que o comparador o reprove.
Arrancando a comparação (fazendo-a devolver sempre "em dia"), esse teste
reprova — e as fotos voltam a defasar em silêncio, que é como chegaram aqui.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: As fotos que o `scripts/gui-captura/retratar_abas.py` grava.
FOTOS = "docs/usage/assets"

#: O que, mudando, torna as fotos suspeitas. `app/` é o código das abas;
#: `gui/` é o `main.glade` e o `theme.css`. Mudança em qualquer um dos dois
#: pode mover um pixel.
CODIGO_DA_TELA = (
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/gui",
)


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(
        ["git", *args],
        cwd=str(raiz),
        capture_output=True,
        text=True,
    )
    if saida.returncode != 0:
        return ""
    return saida.stdout.strip()


def _ultimo_commit(raiz: Path, *caminhos: str) -> str:
    return _git(raiz, "log", "-1", "--format=%H", "--", *caminhos)


def fotos_em_dia(raiz: Path, fotos: str, codigo: tuple[str, ...]) -> bool | None:
    """As fotos foram tiradas DEPOIS da última mexida na tela?

    `True` = sim; `False` = não; `None` = não dá para saber aqui (sem git, ou
    num clone raso, ou porque um dos dois lados nunca foi commitado).

    O critério é a TOPOLOGIA, não o relógio: `merge-base --is-ancestor` responde
    "o commit do código é ancestral do commit das fotos?". Data de commit
    mentiria — um `rebase` reescreve a ordem sem reescrever os carimbos, e dois
    commits podem carregar o mesmo segundo.
    """
    commit_das_fotos = _ultimo_commit(raiz, fotos)
    commit_do_codigo = _ultimo_commit(raiz, *codigo)
    if not commit_das_fotos or not commit_do_codigo:
        return None
    if commit_das_fotos == commit_do_codigo:
        # A mesma leva mexeu na tela e refotografou. É o caminho bom.
        return True
    pergunta = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_do_codigo, commit_das_fotos],
        cwd=str(raiz),
        capture_output=True,
    )
    return pergunta.returncode == 0


def fotos_sendo_refeitas_agora(raiz: Path, fotos: str) -> bool:
    """As fotos estão MODIFICADAS na árvore de trabalho ou no índice?

    Refotografar é o conserto deste portão, e o conserto acontece **antes** do
    commit. Enquanto as imagens estiverem sujas, a cura está em curso e a
    topologia ainda não pode enxergá-la — o commit que as carrega não existe.

    Medido em 13/08/2026: a leva que refez as fotos deixava
    `test_as_fotos_nao_ficam_atras_do_codigo_da_tela` vermelho até o instante do
    commit, ou seja, a suíte reprovava **por causa da própria cura**. O
    `--porcelain` responde por CONTEÚDO, não por relógio, então tocar o mtime de
    um PNG não engana esta pergunta.

    Isto não afrouxa a regra: mexer só no código da tela e **não** refotografar
    continua reprovando, porque aqui só a sujeira das FOTOS conta. E a mordida
    do portão não passa por aqui — `test_o_portao_acusa_foto_atrasada` chama
    `fotos_em_dia` direto, num repositório de mentira.
    """
    return bool(_git(raiz, "status", "--porcelain", "--", fotos))


def _sem_historico(raiz: Path) -> bool:
    """Clone raso ou pasta sem git: aqui não há o que medir, e não há defeito."""
    if not (raiz / ".git").exists():
        return True
    if (raiz / ".git" / "shallow").exists():
        return True
    return not _git(raiz, "rev-parse", "HEAD")


def test_as_fotos_nao_ficam_atras_do_codigo_da_tela() -> None:
    """As imagens do README acompanham a versão — a regra escrita no `CLAUDE.md`."""
    if _sem_historico(RAIZ):
        pytest.skip("sem histórico git completo (clone raso ou pasta sem git)")

    if fotos_sendo_refeitas_agora(RAIZ, FOTOS):
        return  # a cura está em curso: as imagens novas ainda não têm commit

    veredito = fotos_em_dia(RAIZ, FOTOS, CODIGO_DA_TELA)
    if veredito is None:
        pytest.skip("as fotos ou o código da tela ainda não têm commit próprio")

    commit_das_fotos = _ultimo_commit(RAIZ, FOTOS)[:7]
    commit_do_codigo = _ultimo_commit(RAIZ, *CODIGO_DA_TELA)[:7]

    assert veredito, (
        f"a interface mudou em {commit_do_codigo} e as fotos de `{FOTOS}` são "
        f"de {commit_das_fotos}, que veio ANTES. As imagens do `README.md` e do "
        "`docs/usage/interface.md` documentam uma tela que pode não existir "
        "mais.\n\n"
        "    scripts/gui-captura/retratar_abas.py\n\n"
        "Uma execução, nenhum clique. Se as imagens saírem iguais, ótimo — "
        "custou dez segundos e agora está PROVADO. Se saírem diferentes, "
        "olhe-as antes de commitar: mudança de DESENHO é palavra dela "
        "(PROVA-DE-TELA-01), não de quem tirou a foto."
    )


def _repo_de_mentira(tmp_path: Path, fotos_por_ultimo: bool) -> Path:
    """Um repositório com dois commits, na ordem pedida."""
    raiz = tmp_path / ("em_dia" if fotos_por_ultimo else "atrasado")
    (raiz / FOTOS).mkdir(parents=True)
    (raiz / CODIGO_DA_TELA[0]).mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    subprocess.run(
        ["git", "config", "user.email", "portao@exemplo.invalido"],
        cwd=str(raiz),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Portão"], cwd=str(raiz), check=True
    )
    # O sandbox não pode herdar os hooks da MÁQUINA. Nesta aqui há um
    # `core.hooksPath` global que recusa commit com identidade diferente da
    # dela — e o commit deste repositório de mentira é justamente com outra.
    # Medido em 13/08/2026: sem esta linha, `git commit` sai com
    # "[BLOQUEIO] Identidade incorreta" e o teste reprova por motivo nenhum.
    sem_hooks = tmp_path / "sem_hooks"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)],
        cwd=str(raiz),
        check=True,
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    primeiro = (
        (f"{CODIGO_DA_TELA[0]}/home_actions.py", "a aba mudou")
        if fotos_por_ultimo
        else (f"{FOTOS}/readme_inicio.png", "a foto")
    )
    segundo = (
        (f"{FOTOS}/readme_inicio.png", "a foto nova")
        if fotos_por_ultimo
        else (f"{CODIGO_DA_TELA[0]}/home_actions.py", "a aba mudou depois")
    )
    _commitar(primeiro[0], primeiro[1], "primeiro")
    _commitar(segundo[0], segundo[1], "segundo")
    return raiz


def test_o_portao_acusa_foto_atrasada(tmp_path: Path) -> None:
    """A MORDIDA: com a tela mexida depois da foto, o comparador tem de reprovar."""
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "o comparador aceitou um repositório em que a interface mudou DEPOIS "
        "da última foto. É a situação exata de 13/08/2026, com três commits de "
        "`app/`/`gui/` entre a foto e a tag — e é o que este arquivo existe "
        "para não deixar acontecer de novo."
    )


def test_o_portao_aprova_foto_em_dia(tmp_path: Path) -> None:
    """E o outro lado: fotografar depois de mexer na tela tem de passar.

    Sem este, "reprovar sempre" satisfaria o teste de cima — e um portão que
    reprova sempre é desligado na primeira semana.
    """
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=True)

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is True, (
        "o comparador reprovou um repositório em que a foto veio DEPOIS da "
        "mudança de tela, que é o caminho bom."
    )


def test_sem_historico_o_portao_se_cala(tmp_path: Path) -> None:
    """Clone raso não é defeito de foto — e não pode virar vermelho no CI."""
    assert _sem_historico(tmp_path), (
        "uma pasta sem `.git` foi tratada como repositório com histórico. No "
        "CI, com `actions/checkout` raso, isto viraria um vermelho que não "
        "aponta defeito nenhum."
    )
