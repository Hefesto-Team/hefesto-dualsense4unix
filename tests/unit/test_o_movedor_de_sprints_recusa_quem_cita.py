"""O MOVEDOR DE SPRINTS FECHADAS — e a trava que a leva de 20/09 não tinha.

Mover sprint fechada JÁ APAGOU o gesto de 199 testes, calado: a leva que tirou
as 732 fechadas da pasta viva levou junto os dois donos do gesto da mesa de
medição, `scripts/mesa_de_medicao.py` digitava o caminho, não achava e devolvia
`{}` sem uma linha de aviso. Sete réguas ficaram vermelhas e nenhuma sabia
dizer por quê. A raiz está curada em `06396e232`; esta régua cobre a OUTRA
ponta — a ferramenta que move não pode mover o que alguém ainda alcança.

O QUE SE COBRA AQUI, e é o desenho, não o código:

  - a sprint fechada que alguém cita **pelo caminho** não desce, e a recusa
    **nomeia quem cita**, com `arquivo:linha` — senão o conserto vira caça;
  - tirada a citação, ela desce, e vai para `arquivados/` ao lado — o mesmo
    lugar onde `mesa_de_medicao._o_dono_do_gesto` procura;
  - `aberta` e sprint sem frontmatter nunca descem;
  - **a MORDIDA**: com a trava arrancada, a citada desce. É o que prova que
    quem a segura é a trava, e não o acaso do caso de teste.

Tudo em `tmp_path`. Esta régua NÃO lê `docs/process/` — ela é versionada e
aquela pasta é `.gitignore:178`, então lê-la faria o lote inteiro reprovar num
clone limpo por ausência de ambiente.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "mover-sprints-fechadas.py"

_spec = importlib.util.spec_from_file_location("_movedor", SCRIPT)
assert _spec and _spec.loader
movedor = importlib.util.module_from_spec(_spec)
sys.modules["_movedor"] = movedor
_spec.loader.exec_module(movedor)

NOME = "2026-01-01-UMA-SPRINT-DE-MENTIRA-01-o-caso-desta-regua.md"


def _arvore(tmp_path: Path, estado: str = "feita") -> Path:
    """Uma árvore de mentira com UMA sprint no estado pedido."""
    sprints = tmp_path / "docs" / "process" / "sprints"
    sprints.mkdir(parents=True)
    (sprints / NOME).write_text(
        f"---\nsprint: UMA-SPRINT-DE-MENTIRA-01\nestado: {estado}\n---\n\n"
        "# Uma sprint de mentira\n",
        encoding="utf-8",
    )
    return sprints


def _cita_pelo_caminho(tmp_path: Path) -> Path:
    citador = tmp_path / "docs" / "process" / "UM-INDICE.md"
    citador.write_text(
        "# O índice\n\n"
        f"| 1 | [UMA-SPRINT](sprints/{NOME}) | o que ela fez |\n",
        encoding="utf-8",
    )
    return citador


def _roda(tmp_path: Path, *argumentos: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(tmp_path), *argumentos],
        capture_output=True, text=True, check=False,
    )


# ---------------------------------------------------------------------------
# 1 — a citada pelo caminho não desce, e a recusa diz QUEM cita
# ---------------------------------------------------------------------------

def test_a_citada_pelo_caminho_nao_desce_e_a_recusa_nomeia_o_citador(tmp_path):
    sprints = _arvore(tmp_path)
    _cita_pelo_caminho(tmp_path)

    pronto = _roda(tmp_path, "--mover")

    assert pronto.returncode == 0, pronto.stderr
    assert (sprints / NOME).is_file(), "a citada desceu — a trava não segurou"
    assert not (sprints / "arquivados" / NOME).exists()
    assert "PRESAS pela citação: 1" in pronto.stdout
    assert "docs/process/UM-INDICE.md:3" in pronto.stdout, pronto.stdout


# ---------------------------------------------------------------------------
# 2 — tirada a citação, ela desce
# ---------------------------------------------------------------------------

def test_sem_a_citacao_ela_desce_para_a_gaveta_ao_lado(tmp_path):
    sprints = _arvore(tmp_path)

    pronto = _roda(tmp_path, "--mover")

    assert pronto.returncode == 0, pronto.stderr
    assert not (sprints / NOME).exists(), pronto.stdout
    assert (sprints / "arquivados" / NOME).is_file(), pronto.stdout
    assert "LIVRES para descer: 1" in pronto.stdout


# ---------------------------------------------------------------------------
# 3 — A MORDIDA: com a trava arrancada, a citada desce
# ---------------------------------------------------------------------------

def test_com_a_trava_arrancada_a_citada_desce(tmp_path, monkeypatch, capsys):
    """Arrancar a varredura de citação faz a presa do caso 1 descer.

    É a prova de que quem segura é a trava. Sem esta régua, o caso 1 poderia
    estar passando por acaso — porque nada tentou mover, por exemplo.
    """
    sprints = _arvore(tmp_path)
    _cita_pelo_caminho(tmp_path)

    monkeypatch.setattr(movedor, "quem_cita",
                        lambda raiz, nomes: {nome: [] for nome in nomes})
    movedor.main(["--raiz", str(tmp_path), "--mover"])
    capsys.readouterr()

    assert not (sprints / NOME).exists(), (
        "com a trava arrancada a citada continuou parada — então não é a "
        "trava que a segura, e o caso 1 dá verde sobre nada")
    assert (sprints / "arquivados" / NOME).is_file()


# ---------------------------------------------------------------------------
# 4 — o que nunca desce
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("estado", ["aberta", "Aberta"])
def test_a_aberta_nunca_desce(tmp_path, estado):
    sprints = _arvore(tmp_path, estado=estado)

    pronto = _roda(tmp_path, "--mover")

    assert (sprints / NOME).is_file(), pronto.stdout
    assert "nada a mover." in pronto.stdout


def test_sem_frontmatter_nunca_desce(tmp_path):
    sprints = tmp_path / "docs" / "process" / "sprints"
    sprints.mkdir(parents=True)
    (sprints / NOME).write_text("# Sem frontmatter nenhum\n", encoding="utf-8")

    pronto = _roda(tmp_path, "--mover")

    assert (sprints / NOME).is_file(), pronto.stdout
    assert "0 fechada(s)" in pronto.stdout


# ---------------------------------------------------------------------------
# 5 — o padrão é seco, e `--seco` ganha de `--mover`
# ---------------------------------------------------------------------------

def test_sem_argumento_nenhum_nada_se_move(tmp_path):
    sprints = _arvore(tmp_path)

    pronto = _roda(tmp_path)

    assert (sprints / NOME).is_file()
    assert "SECO: nada foi movido." in pronto.stdout


def test_seco_ganha_de_mover(tmp_path):
    """Quem escreve os dois está em dúvida, e em dúvida não se move nada."""
    sprints = _arvore(tmp_path)

    pronto = _roda(tmp_path, "--mover", "--seco")

    assert (sprints / NOME).is_file(), pronto.stdout
    assert "SECO: nada foi movido." in pronto.stdout


# ---------------------------------------------------------------------------
# 6 — as duas classes de citação, que é o que separa travar de avisar
# ---------------------------------------------------------------------------

def test_a_citacao_so_pelo_nome_nao_trava(tmp_path):
    """Sem pasta antes do nome, a citação sobrevive à mudança.

    A conferência de referência desta casa aceita SUFIXO, e
    `arquivados/<nome>` termina no mesmo `<nome>`. Travar aqui seria prender
    toda sprint que aparece numa lista de nomes, e um movedor que nunca move
    é um movedor que alguém desliga.
    """
    sprints = _arvore(tmp_path)
    (tmp_path / "docs" / "process" / "UMA-LISTA.md").write_text(
        f"A sprint `{NOME}` fechou.\n", encoding="utf-8")

    pronto = _roda(tmp_path, "--mover")

    assert (sprints / "arquivados" / NOME).is_file(), pronto.stdout
    assert "só pelo nome" in pronto.stdout


def test_quem_ja_aponta_para_a_gaveta_nao_trava(tmp_path):
    sprints = _arvore(tmp_path)
    (tmp_path / "docs" / "process" / "UM-INDICE.md").write_text(
        f"[já reapontado](sprints/arquivados/{NOME})\n", encoding="utf-8")

    pronto = _roda(tmp_path, "--mover")

    assert (sprints / "arquivados" / NOME).is_file(), pronto.stdout
    assert "PRESAS pela citação: 0" in pronto.stdout


# ---------------------------------------------------------------------------
# 7 — o que o movedor NUNCA faz
# ---------------------------------------------------------------------------

def test_o_movedor_nao_move_teste_nenhum(tmp_path):
    """`--testes` mede e recusa. Mover teste é ato de quem coordena.

    Um teste não morre porque a sprint dele fechou: ele passa a ser a única
    coisa que impede a regressão daquele trabalho.
    """
    _arvore(tmp_path)
    testes = tmp_path / "tests" / "unit"
    testes.mkdir(parents=True)
    alvo = testes / "test_de_mentira.py"
    alvo.write_text("def test_nada():\n    assert True\n", encoding="utf-8")

    pronto = _roda(tmp_path, "--testes")

    assert pronto.returncode == 0, pronto.stderr
    assert alvo.is_file()
    assert not (testes / "arquivados").exists()
    assert "NADA FOI MOVIDO EM tests/" in pronto.stdout


def test_sem_a_pasta_das_sprints_nao_e_defeito(tmp_path):
    """Clone limpo não tem `docs/process/`, e a esteira tem de subir assim.

    É a lição do `release.yml`, que já caiu uma vez porque 129 réguas leem uma
    pasta que o git não carrega.
    """
    pronto = _roda(tmp_path, "--mover")

    assert pronto.returncode == 0, pronto.stderr
    assert "nada a medir" in pronto.stdout


def test_a_gaveta_ocupada_grita_em_vez_de_sobrescrever(tmp_path):
    sprints = _arvore(tmp_path)
    (sprints / "arquivados").mkdir()
    (sprints / "arquivados" / NOME).write_text("# outra\n", encoding="utf-8")

    pronto = _roda(tmp_path, "--mover")

    assert pronto.returncode != 0, pronto.stdout
    assert "já existe na gaveta" in (pronto.stderr + pronto.stdout)
    assert (sprints / "arquivados" / NOME).read_text(encoding="utf-8") == "# outra\n"


# ---------------------------------------------------------------------------
# 8 — `--exigir`, para quem quiser isto como portão
# ---------------------------------------------------------------------------

def test_exigir_reprova_enquanto_houver_fechada_na_pasta_viva(tmp_path):
    _arvore(tmp_path)

    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 1
    assert NOME in pronto.stdout


def test_exigir_passa_com_a_pasta_viva_so_de_abertas(tmp_path):
    _arvore(tmp_path, estado="aberta")

    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 0
    assert "OK:" in pronto.stdout


# ---------------------------------------------------------------------------
# 9 — `--exigir` COMO PORTÃO, e o arranjo DIFÍCIL é o que faltava
#
# Os dois casos da seção 8 cobrem o arranjo FÁCIL: uma fechada sem citação
# nenhuma, e uma pasta só de abertas. Na árvore viva de 20/09/2026 o arranjo
# fácil era MINORIA — 8 de 21 fechadas estavam livres, e as outras 13 estavam
# presas por citação de caminho, seguradas de propósito pela trava.
#
# É a pergunta que esta casa aprendeu a fazer: *a régua cobre o arranjo
# difícil ou só o fácil?* A régua do rótulo do gravador conferia dois nomes de
# SOM e nunca os da HÁPTICA, que eram os que colidiam. Aqui era o mesmo: a
# régua conferia a livre e nunca a presa, que é a maioria.
# ---------------------------------------------------------------------------

def test_exigir_nao_reprova_a_fechada_que_a_citacao_segura(tmp_path):
    """A presa por caminho NÃO reprova, e sai nomeada.

    A MORDIDA ARRANCA: faça `_exige` contar toda fechada — que é o que ele
    fazia até 20/09/2026 — e este teste reprova com `rc=1`. É o vermelho
    eterno: a trava segura a sprint DE PROPÓSITO (soltá-la quebraria o
    citador), e um portão que reprova o estado certo não tem conserto. Portão
    sem conserto é portão que alguém desliga.
    """
    sprints = _arvore(tmp_path)
    _cita_pelo_caminho(tmp_path)

    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 0, (
        "a presa reprovou o portão — e ela não tem conserto do lado de quem "
        f"vê o vermelho:\n{pronto.stdout}")
    assert "presas pela citação, e FICAM: 1" in pronto.stdout, pronto.stdout
    assert NOME in pronto.stdout, "a presa não foi nomeada"
    assert (sprints / NOME).is_file()


def test_exigir_reprova_a_livre_mesmo_no_meio_das_presas(tmp_path):
    """Uma livre entre presas ainda reprova, e SÓ ela é listada para descer.

    A MORDIDA ARRANCA: se `_exige` deixar de separar e passar a devolver 0
    sempre que houver qualquer presa, este teste reprova — seria a cura
    passando do ponto, trocando o vermelho eterno por um portão cego.
    """
    sprints = _arvore(tmp_path)
    _cita_pelo_caminho(tmp_path)
    livre = "2026-01-02-OUTRA-SPRINT-DE-MENTIRA-02-a-que-ninguem-cita.md"
    (sprints / livre).write_text(
        "---\nsprint: OUTRA-SPRINT-DE-MENTIRA-02\nestado: absorvida\n---\n\n"
        "# Outra\n", encoding="utf-8")

    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 1, pronto.stdout
    descem = pronto.stdout.split("podem descer AGORA:")[-1]
    assert livre in descem, pronto.stdout
    assert NOME not in descem, (
        "a presa entrou na lista do que desce — a separação não é a mesma "
        f"que o `--seco` usa:\n{pronto.stdout}")


def test_exigir_sem_a_pasta_diz_nao_medido_e_nunca_ok(tmp_path):
    """Sem `docs/process/` no disco, o portão declara que NÃO MEDIU.

    Clone limpo nunca tem a pasta — ela é `.gitignore:178`. Até 20/09/2026
    este caminho imprimia *"OK: nenhuma sprint fechada na pasta viva"* e
    devolvia 0: afirmava sobre 46 sprints que não tinha lido.

    A MORDIDA ARRANCA: devolva a linha `OK: nenhuma sprint fechada na pasta
    viva` ao ramo da pasta ausente e este teste reprova. É *ausência é
    resposta* — sem o dado, diga "não sei" e por quê, nunca "nenhum".
    """
    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 0, pronto.stderr
    assert "NÃO MEDIDO" in pronto.stdout, pronto.stdout
    assert "OK:" not in pronto.stdout, (
        "o portão disse OK sobre uma árvore que não leu — é verde sobre "
        f"nada:\n{pronto.stdout}")


def test_exigir_nao_move_um_byte(tmp_path):
    """O portão é LEITURA PURA. Quem move é a pessoa que vê o vermelho.

    A MORDIDA ARRANCA: faça `--exigir` chamar `mover()` e este teste reprova.
    Portão que reescreve artefato não roda em árvore de agente — é a razão
    declarada que mantém o `i18n_compile.sh` fora do `portoes.sh`.
    """
    sprints = _arvore(tmp_path)

    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 1, pronto.stdout
    assert (sprints / NOME).is_file(), "o portão moveu a sprint"
    assert not (sprints / "arquivados").exists(), "o portão criou a gaveta"


def test_o_movedor_esta_ligado_ao_portoes_sh():
    """O movedor é portão declarado, senão a narrativa volta a crescer sozinha.

    A ordem dela, 17 e 20/09/2026, é que isto rode sem ninguém lembrar. Um
    script que só existe no disco é um script que ninguém roda — foi o que
    deixou a regra *fato errado se SUBSTITUI* sem instrumento desde 11/08.

    A MORDIDA ARRANCA: tire a linha `sprints-fechadas` da tabela de
    `portoes.sh` e este teste reprova. Ele lê o arquivo em vez de rodá-lo,
    igual ao portão do portão, para valer sem venv nem árvore de git.
    """
    tabela = (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    linhas = [ln.strip() for ln in tabela.splitlines()
              if ln.strip().startswith(("rapido|", "completo|"))]
    minhas = [ln for ln in linhas if "mover-sprints-fechadas.py" in ln]

    assert minhas, (
        "o movedor não está na tabela de portoes.sh — sem isso ele só roda "
        "quando alguém lembra, que é o estado que a sprint veio curar")
    assert all("--exigir" in ln for ln in minhas), (
        f"o movedor está declarado sem `--exigir`: {minhas}. Sem a forma de "
        "leitura pura, o portão moveria arquivo por trás de quem trabalha")
    assert all("--mover" not in ln for ln in minhas), (
        f"o portão foi declarado com `--mover`: {minhas}")
