"""O item 3 do checklist virou executável — FOTO-NO-GANCHO-01."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_fotos_da_tela.py"
GANCHO = RAIZ / "scripts" / "hooks" / "pre-commit"


def _carregar():
    espec = importlib.util.spec_from_file_location("check_fotos_da_tela", PORTAO)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


portao = _carregar()

UMA_ABA = "src/hefesto_dualsense4unix/app/widgets/controller_card.py"
UMA_PAGINA = "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"
O_RETRATO = "src/hefesto_dualsense4unix/interface/olhar.py"
UMA_FOTO = "docs/usage/assets/aba-01-jogar.png"
O_RECIBO = "docs/usage/assets/PROVA-DA-FOTO.txt"

A_FOTO_DA_VISTA = "docs/usage/assets/maximizada/aba-01-jogar.png"
O_RECIBO_DA_VISTA = "docs/usage/assets/maximizada/PROVA-DA-FOTO.txt"

AS_DUAS_PROVAS = [UMA_FOTO, A_FOTO_DA_VISTA]


@pytest.mark.parametrize("arquivo_de_tela", [UMA_ABA, UMA_PAGINA, O_RETRATO])
def test_bloqueia_codigo_de_tela_sem_foto(arquivo_de_tela: str) -> None:
    """A MORDIDA: mexer na tela sem levar foto tem de BLOQUEAR o commit."""
    veredito, culpados = portao.julgar(
        [arquivo_de_tela, "docs/process/uma-sprint.md"],
        fotos_sujas=False,
        historia_em_dia=True
    )

    assert veredito == portao.BLOQUEADO, (
        f"o portão deixou passar um commit que mexe em `{arquivo_de_tela}` sem "
        "foto nenhuma. É o furo da integração da Onda 0: prosa em três "
        "documentos, e o commit saiu antes da foto."
    )
    assert culpados == [arquivo_de_tela], (
        "a mensagem de bloqueio precisa nomear o arquivo de tela; sem isso "
        "quem apanha não sabe por quê."
    )


def test_deixa_passar_quem_leva_a_foto_junto() -> None:
    """O caminho bom: tela mexida e foto na mesma leva."""
    veredito, _ = portao.julgar(
        [UMA_ABA, *AS_DUAS_PROVAS], fotos_sujas=False, historia_em_dia=True
    )
    assert veredito == portao.EM_DIA


def test_o_recibo_sozinho_basta_de_prova() -> None:
    """Mudança de tela que não move pixel: o recibo é a saída, e tem de servir."""
    veredito, _ = portao.julgar(
        [UMA_ABA, O_RECIBO, O_RECIBO_DA_VISTA],
        fotos_sujas=False,
        historia_em_dia=True,
    )
    assert veredito == portao.EM_DIA


def test_a_foto_da_vista_nao_paga_a_divida_das_dez_do_readme() -> None:
    """A MORDIDA DA PASTA NOVA — a simulação do conferente, 11/09/2026."""
    veredito, culpados = portao.julgar(
        [UMA_ABA, A_FOTO_DA_VISTA], fotos_sujas=False, historia_em_dia=True
    )

    assert veredito == portao.BLOQUEADO, (
        "o gancho aceitou a foto da vista como prova das dez do README. A "
        "partir daí, gravar só em `maximizada/` quitaria a dívida delas para "
        "sempre, sem uma linha de aviso."
    )
    assert culpados == [UMA_ABA]
    assert portao.familias_sem_prova([UMA_ABA, A_FOTO_DA_VISTA]) == [portao.FOTOS], (
        "o bloqueio precisa NOMEAR a pasta que está devendo. Sem isso quem "
        "apanha roda o comando da outra família, vê nada mudar, e conclui que "
        "o portão quebrou."
    )
    assert portao.familias_sem_prova([UMA_ABA, UMA_FOTO]) == [
        portao.FOTOS_DA_VISTA
    ], "e o inverso também: a foto do README não paga a dívida da vista."


def test_nao_reclama_de_commit_que_nao_toca_a_tela() -> None:
    """O falso positivo que mataria o portão."""
    veredito, culpados = portao.julgar(
        [
            "src/hefesto_dualsense4unix/daemon/ipc_handlers.py",
            "docs/protocol/dualsense-referencia-canonica.md",
            "tests/unit/test_qualquer_coisa.py",
        ],
        fotos_sujas=False,
        historia_em_dia=True,
    )
    assert veredito == portao.EM_BRANCO
    assert culpados == []


def test_prefixo_parecido_nao_conta_como_tela() -> None:
    """`app` e `gui` são diretórios, não pedaços de nome."""
    veredito, _ = portao.julgar(
        [
            "src/hefesto_dualsense4unix/appimage_notas.py",
            "scripts/gui-captura-antiga/coisa.py",
        ],
        fotos_sujas=False,
        historia_em_dia=True,
    )
    assert veredito == portao.EM_BRANCO


def test_a_cura_em_curso_avisa_mas_nao_bloqueia() -> None:
    """Foto suja na árvore = retrato acabou de rodar. Mesmo perdão da suíte."""
    veredito, _ = portao.julgar([UMA_ABA], fotos_sujas=True, historia_em_dia=True)
    assert veredito == portao.CURA_EM_CURSO


def test_cobra_a_divida_que_os_merges_deixaram() -> None:
    """A MORDIDA que importa: a Onda 0 entrou por MERGE, e merge não tem gancho."""
    veredito, _ = portao.julgar(
        ["docs/process/SPRINT_ORDER.md", "docs/process/2026-08-24-ONDE-PARAMOS.md"],
        fotos_sujas=False,
        historia_em_dia=False,
    )
    assert veredito == portao.DIVIDA_HERDADA, (
        "o portão aprovou o commit de fim de leva com `HEAD` devendo foto. É "
        "exatamente o que aconteceu na integração da Onda 0, e olhar só o "
        "índice não vê isso, porque merge não passa por `pre-commit`."
    )


def test_a_foto_no_commit_quita_a_divida_herdada() -> None:
    """Quem paga a dívida tem de conseguir commitar — senão o portão é uma parede."""
    veredito, _ = portao.julgar(
        [O_RECIBO, UMA_FOTO, O_RECIBO_DA_VISTA, A_FOTO_DA_VISTA],
        fotos_sujas=True,
        historia_em_dia=False,
    )
    assert veredito == portao.EM_DIA


def test_sem_historia_a_segunda_pergunta_se_cala() -> None:
    """Clone raso ou repositório novo não é defeito de foto."""
    veredito, _ = portao.julgar(
        ["docs/process/uma-sprint.md"], fotos_sujas=False, historia_em_dia=None
    )
    assert veredito == portao.EM_BRANCO


def test_worktree_de_agente_nao_e_cobrada(tmp_path: Path) -> None:
    """O falso positivo que desinstalaria o gancho na primeira hora."""
    raiz = _repo_de_mentira(tmp_path)
    galho = tmp_path / "sprint-Z9"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "sprint-Z9", str(galho)],
        cwd=str(raiz),
        check=True,
    )
    alvo = galho / "src" / "hefesto_dualsense4unix" / "app"
    alvo.mkdir(parents=True)
    (alvo / "app.py").write_text("o agente mexeu na aba dele")
    subprocess.run(["git", "add", "-A"], cwd=str(galho), check=True)

    assert portao.na_arvore_principal(galho) is False, (
        "o portão não distinguiu worktree ligada de árvore principal."
    )
    saida = _rodar(galho)
    assert saida.returncode == 0, (
        "o portão cobrou foto de um agente em worktree, que é justamente quem "
        f"não pode fotografar. stderr={saida.stderr!r}"
    )
    assert portao.na_arvore_principal(raiz) is True


def test_no_git_de_verdade_a_divida_herdada_para_o_commit(tmp_path: Path) -> None:
    """A dívida dos merges, de ponta a ponta: história vermelha, commit inocente."""
    raiz = _repo_de_mentira(tmp_path)
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "app"
    alvo.mkdir(parents=True)
    (alvo / "app.py").write_text("a fita do cabeçalho mudou")
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "merge de leva, sem gancho"],
        cwd=str(raiz),
        check=True,
    )
    assert portao.historia_em_dia(raiz) is False

    (raiz / "docs" / "SPRINT_ORDER.md").write_text("a leva fechou")
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)

    saida = _rodar(raiz)
    assert saida.returncode == 1, (
        "o commit de fim de leva passou com a história devendo foto. "
        f"stderr={saida.stderr!r}"
    )
    assert "olhar.py" in saida.stderr


def test_o_gancho_chama_o_portao() -> None:
    """Portão desligado protege menos que nenhum — porque ninguém confere."""
    texto = GANCHO.read_text(encoding="utf-8")
    assert "scripts/check_fotos_da_tela.py" in texto, (
        "o `pre-commit` parou de invocar `scripts/check_fotos_da_tela.py`. O "
        "portão vira arquivo morto e a regra volta a ser prosa."
    )
    assert "falhou=1" in texto.split("check_fotos_da_tela.py")[-1], (
        "o `pre-commit` chama o portão mas não usa o resultado dele: o commit "
        "sairia mesmo com o bloqueio."
    )


def test_as_duas_listas_de_codigo_de_tela_sao_a_mesma() -> None:
    """O gancho e o portão da suíte fazem a MESMA pergunta, ou um dos dois mente."""
    from tests.unit.test_as_fotos_acompanham_a_versao import (
        CODIGO_DA_TELA as DA_SUITE,
        FAMILIAS_DE_FOTO as FAMILIAS_DA_SUITE,
        FOTOS as FOTOS_DA_SUITE,
    )

    assert portao.CODIGO_DA_TELA == DA_SUITE
    assert portao.FOTOS == FOTOS_DA_SUITE
    assert portao.FAMILIAS_DE_FOTO == FAMILIAS_DA_SUITE


def _repo_de_mentira(tmp_path: Path) -> Path:
    """Um repositório com um commit, para exercitar o git de verdade."""
    raiz = tmp_path / "repo"
    raiz.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    for chave, valor in (
        ("user.email", "portao@exemplo.invalido"),
        ("user.name", "Portão"),
    ):
        subprocess.run(["git", "config", chave, valor], cwd=str(raiz), check=True)
    sem_hooks = tmp_path / "sem_hooks"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)], cwd=str(raiz), check=True
    )
    (raiz / "docs" / "usage" / "assets").mkdir(parents=True)
    (raiz / "docs" / "usage" / "assets" / "aba-01-jogar.png").write_text("a foto")
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "a foto"], cwd=str(raiz), check=True)
    return raiz


def _rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PORTAO)],
        cwd=str(raiz),
        capture_output=True,
        text=True,
    )


def test_no_git_de_verdade_o_portao_reprova_e_ensina(tmp_path: Path) -> None:
    """A MORDIDA de ponta a ponta: índice real, `git` real, saída 1."""
    raiz = _repo_de_mentira(tmp_path)
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "app"
    alvo.mkdir(parents=True)
    (alvo / "app.py").write_text("a fita do cabeçalho mudou")
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)

    saida = _rodar(raiz)

    assert saida.returncode == 1, (
        "o script aceitou um índice com mudança de tela e nenhuma foto. "
        f"stdout={saida.stdout!r} stderr={saida.stderr!r}"
    )
    assert "olhar.py" in saida.stderr, (
        "a mensagem de bloqueio não diz o comando que cura. Portão que reprova "
        "sem ensinar o conserto vira portão que se desliga."
    )


def test_no_git_de_verdade_o_portao_se_cala_quando_a_foto_vem_junto(
    tmp_path: Path,
) -> None:
    """E o outro lado, também de ponta a ponta."""
    raiz = _repo_de_mentira(tmp_path)
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "app"
    alvo.mkdir(parents=True)
    (alvo / "app.py").write_text("a fita do cabeçalho mudou")
    (raiz / "docs" / "usage" / "assets" / "PROVA-DA-FOTO.txt").write_text(
        "ensaio: 2026-08-24 12:00"
    )
    subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)

    saida = _rodar(raiz)

    assert saida.returncode == 0, (
        "o portão bloqueou um commit que leva a tela E o recibo do ensaio — "
        f"o caminho bom. stderr={saida.stderr!r}"
    )
