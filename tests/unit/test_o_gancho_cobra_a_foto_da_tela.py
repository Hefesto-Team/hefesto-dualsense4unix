"""O item 3 do checklist virou executável — FOTO-NO-GANCHO-01.

A regra "fotografe se a mudança tocou a tela" era prosa em três documentos, e
prosa não impediu o coordenador de integrar nove branches de interface sem
abrir a tela uma vez. O portão que existia — `test_as_fotos_acompanham_a_versao`
— pegou o erro, mas só na suíte inteira, de ~8 min, rodada DEPOIS do commit.

`scripts/check_fotos_da_tela.py` faz a mesma pergunta no `pre-commit`.
Este arquivo é a mordida dele, e a trava contra os dois jeitos de esvaziá-lo:

* **reprovar sempre** — `test_nao_reclama_de_commit_que_nao_toca_a_tela` e
  `test_deixa_passar_quem_leva_a_foto_junto` seguram esse lado, que é o pior:
  portão que reclama sem razão ensina a ignorar portão;
* **desligar** — `test_o_gancho_chama_o_portao` reprova se o `pre-commit`
  parar de invocar o script.

E `test_as_duas_listas_de_codigo_de_tela_sao_a_mesma` tranca as duas cópias de
`CODIGO_DA_TELA` juntas: o gancho não pode ficar mais severo nem mais frouxo
que o portão da suíte que ele antecipa.
"""

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
#: 06/09/2026 (`GTK-3`): as DUAS entradas mudaram de arquivo, e a regra não.
#: Eram `gui/main.glade` e `scripts/gui-captura/retratar_abas.py` — o XML da
#: janela GTK e o retratista dela, apagados por decisão dela
#: (`D-0609-GTK-LEVA-INTEIRA`). O que a tela declara hoje é uma das dez páginas;
#: quem a fotografa é `interface/olhar.py`. `gui/` continua na lista por causa
#: do `theme.css`, que é a fonte das cores da casa.
UMA_PAGINA = "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"
O_RETRATO = "src/hefesto_dualsense4unix/interface/olhar.py"
UMA_FOTO = "docs/usage/assets/readme_inicio.png"
O_RECIBO = "docs/usage/assets/PROVA-DA-FOTO.txt"

#: A SEGUNDA FAMÍLIA — 11/09/2026. `docs/usage/assets/maximizada/` guarda as
#: dez abas na vista maximizada dela, e o gancho passou a cobrar as DUAS
#: pastas: uma foto da vista não paga a dívida das dez do README, e vice-versa.
#: Ver `test_a_foto_da_vista_nao_paga_a_divida_das_dez_do_readme`.
A_FOTO_DA_VISTA = "docs/usage/assets/maximizada/aba-01-jogar.png"
O_RECIBO_DA_VISTA = "docs/usage/assets/maximizada/PROVA-DA-FOTO.txt"

#: A prova COMPLETA: uma por família. É o que um commit de tela precisa levar.
AS_DUAS_PROVAS = [UMA_FOTO, A_FOTO_DA_VISTA]


# ---------------------------------------------------------------- a mordida


@pytest.mark.parametrize("arquivo_de_tela", [UMA_ABA, UMA_PAGINA, O_RETRATO])
def test_bloqueia_codigo_de_tela_sem_foto(arquivo_de_tela: str) -> None:
    """A MORDIDA: mexer na tela sem levar foto tem de BLOQUEAR o commit.

    É a situação exata de 24/08/2026 — nove branches de interface commitadas
    sem ninguém abrir a tela. Os três casos são o motor da aba, a PÁGINA que a
    pessoa lê, e o INSTRUMENTO que decide o que a foto mostra.
    """
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
    """O caminho bom: tela mexida e foto na mesma leva.

    Sem este, "bloquear sempre" satisfaria a mordida — e portão que reprova
    sempre é desinstalado na primeira semana.

    **A prova são as DUAS famílias desde 11/09/2026** — as dez do README e as
    dez da vista maximizada. Não é severidade a mais: é a mesma pergunta que o
    portão da suíte faz, e um gancho mais frouxo que ele promete cobrir o que
    não cobre.
    """
    veredito, _ = portao.julgar(
        [UMA_ABA, *AS_DUAS_PROVAS], fotos_sujas=False, historia_em_dia=True
    )
    assert veredito == portao.EM_DIA


def test_o_recibo_sozinho_basta_de_prova() -> None:
    """Mudança de tela que não move pixel: o recibo é a saída, e tem de servir.

    `PROVA-DA-FOTO.txt` carrega a data do ensaio, então **toda** execução do
    retrato o modifica, mesmo com as dez abas byte a byte idênticas. Se o
    portão não aceitasse o recibo, existiria commit sem saída — o defeito que
    o `CONFERIDO-EM.md` foi criado para resolver, reinventado no gancho.

    Cada família tem o SEU recibo, e é o de cada pasta que vale por ela.
    """
    veredito, _ = portao.julgar(
        [UMA_ABA, O_RECIBO, O_RECIBO_DA_VISTA],
        fotos_sujas=False,
        historia_em_dia=True,
    )
    assert veredito == portao.EM_DIA


def test_a_foto_da_vista_nao_paga_a_divida_das_dez_do_readme() -> None:
    """A MORDIDA DA PASTA NOVA — a simulação do conferente, 11/09/2026.

    `docs/usage/assets/maximizada/` cai DENTRO de `docs/usage/assets` quando a
    pergunta casa por prefixo, e era assim que ela casava: este commit — a aba
    01 mexida, e como prova só a foto da VISTA — devolvia `em-dia`. A dívida
    das dez do README ficava paga por foto que não é delas, e elas podiam
    apodrecer caladas. É o defeito que a PRINTS-DAS-DEZ-01 tinha acabado de
    achar (as do README paradas em 08/09), reaberto numa família ainda menos
    coberta.

    **Para morder:** troque `familias_sem_prova` por
    `any(_toca(c, (FOTOS,)) for c in caminhos)` e este teste reprova.
    """
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
    """O falso positivo que mataria o portão.

    A maioria dos commits desta casa não toca a tela. Se o gancho pedisse foto
    a eles, alguém desinstalaria o gancho — e esta casa já mediu isso.
    """
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
    """`app` e `gui` são diretórios, não pedaços de nome.

    Um `casamento_por_prefixo` cru acusaria `app_de_outra_coisa.py` e
    `gui-captura-de-outra-coisa/`, que é falso positivo puro.
    """
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
    """Foto suja na árvore = retrato acabou de rodar. Mesmo perdão da suíte.

    O portão da suíte tem `fotos_sendo_refeitas_agora` por isto: entre rodar o
    retrato e commitar as imagens, a cura existe e ainda não tem commit. Se o
    gancho bloqueasse aqui, bloquearia justamente quem obedeceu.
    """
    veredito, _ = portao.julgar([UMA_ABA], fotos_sujas=True, historia_em_dia=True)
    assert veredito == portao.CURA_EM_CURSO


# ------------------------------------ a segunda pergunta: a dívida que os merges deixam


def test_cobra_a_divida_que_os_merges_deixaram() -> None:
    """A MORDIDA que importa: a Onda 0 entrou por MERGE, e merge não tem gancho.

    MEDIDO em 24/08/2026: os nove branches entraram por nove commits de merge
    (`cf78346`, `0c99242`, `f9240b5`, `15b5ff5`, `4f7cece`, `ed79255`,
    `2d83432`, `7bf4f25`, `9b4e5a0`). O git não roda `pre-commit` em commit de
    merge. Um gancho que só olhasse o índice teria deixado passar os nove e
    depois aprovado o commit de fim de leva, que mexe em `SPRINT_ORDER.md` e
    `ONDE-PARAMOS` e não toca `app/` — ou seja, não teria pego nada.

    A segunda pergunta é a que morde: `HEAD` já deve foto, então o PRÓXIMO
    commit para, seja ele qual for.
    """
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
    """Quem paga a dívida tem de conseguir commitar — senão o portão é uma parede.

    O commit que carrega a foto chega com `historia_em_dia=False` (a foto ainda
    não tem commit). Se a segunda pergunta vencesse a primeira, o conserto
    seria impossível.
    """
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
    """O falso positivo que desinstalaria o gancho na primeira hora.

    Agente de sprint commita `app/` o dia inteiro na SUA árvore e tem o
    retratista na lista do que NÃO pode rodar (COMO-EXECUTAR-UMA-SPRINT §5; R4
    de COMO-REGER-AGENTES.md) — era `retratar_abas.py`, apagado com a janela
    GTK em 06/09/2026; hoje é `interface/olhar.py --todas --publicado --doc`.
    Cobrar foto dele é cobrar o que ele está proibido de fazer — e os ganchos
    são compartilhados com a árvore principal, então isto não é hipótese.
    """
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
    """A dívida dos merges, de ponta a ponta: história vermelha, commit inocente.

    A função pura pode estar certa e a leitura da topologia errada — foi assim
    que a AUDITORIA-DE-PERDA-01 achou instrumento medindo o lugar errado.
    """
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


# ------------------------------------------------- as duas travas de esvaziar


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
    """O gancho e o portão da suíte fazem a MESMA pergunta, ou um dos dois mente.

    Mais severo, o gancho reclama de commit que a suíte aprova — falso positivo.
    Mais frouxo, ele promete cobrir o que não cobre. Quem acrescentar um
    diretório de tela tem de acrescentar nos dois.
    """
    from tests.unit.test_as_fotos_acompanham_a_versao import (
        CODIGO_DA_TELA as DA_SUITE,
        FAMILIAS_DE_FOTO as FAMILIAS_DA_SUITE,
        FOTOS as FOTOS_DA_SUITE,
    )

    assert portao.CODIGO_DA_TELA == DA_SUITE
    assert portao.FOTOS == FOTOS_DA_SUITE
    # E AS FAMÍLIAS DE FOTO TAMBÉM — 11/09/2026. Quem criar uma terceira pasta
    # de foto num lado só recria, num nível acima, o buraco que a `maximizada/`
    # abriu: a pasta nova cairia dentro da velha por prefixo e quitaria a
    # dívida dela.
    assert portao.FAMILIAS_DE_FOTO == FAMILIAS_DA_SUITE


# ----------------------------------------------------- o portão de verdade, e2e


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
    # Os ganchos GLOBAIS desta máquina recusam commit com identidade diferente
    # da dela — o mesmo motivo medido em 13/08/2026 no portão da suíte.
    sem_hooks = tmp_path / "sem_hooks"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)], cwd=str(raiz), check=True
    )
    (raiz / "docs" / "usage" / "assets").mkdir(parents=True)
    (raiz / "docs" / "usage" / "assets" / "readme_inicio.png").write_text("a foto")
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
    """A MORDIDA de ponta a ponta: índice real, `git` real, saída 1.

    A função pura pode estar certa e a leitura do índice errada — foi assim que
    a AUDITORIA-DE-PERDA-01 achou instrumento medindo o lugar errado. Aqui o
    script roda como o gancho o roda.
    """
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
