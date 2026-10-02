"""O MOVEDOR DE SPRINTS FECHADAS — e a trava que a leva de 20/09 não tinha."""

from __future__ import annotations

import importlib.util
import re
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


def test_a_citada_pelo_caminho_nao_desce_e_a_recusa_nomeia_o_citador(tmp_path):
    sprints = _arvore(tmp_path)
    _cita_pelo_caminho(tmp_path)

    pronto = _roda(tmp_path, "--mover")

    assert pronto.returncode == 0, pronto.stderr
    assert (sprints / NOME).is_file(), "a citada desceu — a trava não segurou"
    assert not (sprints / "arquivados" / NOME).exists()
    assert "PRESAS pela citação: 1" in pronto.stdout
    assert "docs/process/UM-INDICE.md:3" in pronto.stdout, pronto.stdout


def test_sem_a_citacao_ela_desce_para_a_gaveta_ao_lado(tmp_path):
    sprints = _arvore(tmp_path)

    pronto = _roda(tmp_path, "--mover")

    assert pronto.returncode == 0, pronto.stderr
    assert not (sprints / NOME).exists(), pronto.stdout
    assert (sprints / "arquivados" / NOME).is_file(), pronto.stdout
    assert "LIVRES para descer: 1" in pronto.stdout


def test_com_a_trava_arrancada_a_citada_desce(tmp_path, monkeypatch, capsys):
    """Arrancar a varredura de citação faz a presa do caso 1 descer."""
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


def test_a_citacao_so_pelo_nome_nao_trava(tmp_path):
    """Sem pasta antes do nome, a citação sobrevive à mudança."""
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


def test_o_movedor_nao_move_teste_nenhum(tmp_path):
    """`--testes` mede e recusa. Mover teste é ato de quem coordena."""
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
    """Clone limpo não tem `docs/process/`, e a esteira tem de subir assim."""
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


def test_exigir_nao_reprova_a_fechada_que_a_citacao_segura(tmp_path):
    """A presa por caminho NÃO reprova, e sai nomeada."""
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
    """Uma livre entre presas ainda reprova, e SÓ ela é listada para descer."""
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
    """Sem `docs/process/` no disco, o portão declara que NÃO MEDIU."""
    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 0, pronto.stderr
    assert "NÃO MEDIDO" in pronto.stdout, pronto.stdout
    assert "OK:" not in pronto.stdout, (
        "o portão disse OK sobre uma árvore que não leu — é verde sobre "
        f"nada:\n{pronto.stdout}")


def test_exigir_nao_move_um_byte(tmp_path):
    """O portão é LEITURA PURA. Quem move é a pessoa que vê o vermelho."""
    sprints = _arvore(tmp_path)

    pronto = _roda(tmp_path, "--exigir")

    assert pronto.returncode == 1, pronto.stdout
    assert (sprints / NOME).is_file(), "o portão moveu a sprint"
    assert not (sprints / "arquivados").exists(), "o portão criou a gaveta"


def test_o_movedor_esta_ligado_ao_portoes_sh():
    """O movedor é portão declarado, senão a narrativa volta a crescer sozinha."""
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


SO_NOME = "2026-01-04-A-TERCEIRA-DE-MENTIRA-03-so-o-nome-a-cita.md"
LIVRE = "2026-01-05-A-QUARTA-DE-MENTIRA-04-ninguem-a-cita.md"


def _as_tres(tmp_path):
    """Uma presa por caminho, uma citada só pelo nome, e uma sem citação."""
    sprints = _arvore(tmp_path)
    _cita_pelo_caminho(tmp_path)
    for nome in (SO_NOME, LIVRE):
        (sprints / nome).write_text(
            f"---\nsprint: {nome[:40]}\nestado: feita\n---\n\n# X\n",
            encoding="utf-8")
    (tmp_path / "docs" / "process" / "UMA-LISTA.md").write_text(
        f"A sprint `{SO_NOME}` fechou, e esta linha não diz pasta nenhuma.\n",
        encoding="utf-8")
    return sprints


def _os_md_do_bloco(saida: str, abertura: str, fechamento: str) -> set[str]:
    depois = saida.split(abertura)
    assert len(depois) == 2, f"«{abertura}» não saiu uma vez só:\n{saida}"
    corpo = depois[1].split(fechamento)[0]
    return {p.strip() for p in re.findall(r"\S+\.md", corpo)}


def test_a_fronteira_do_exigir_e_a_mesma_que_o_seco_usa(tmp_path):
    """O que o portão manda descer é, nome por nome, o que o `--seco` solta."""
    _as_tres(tmp_path)

    seco = _roda(tmp_path, "--seco")
    exigir = _roda(tmp_path, "--exigir")

    soltas = {Path(p).name for p in _os_md_do_bloco(
        seco.stdout, "LIVRES para descer:", "SECO:")}
    descem = {Path(p).name for p in _os_md_do_bloco(
        exigir.stdout, "podem descer AGORA:", "Rode scripts/")}

    assert soltas, f"o `--seco` não soltou nenhuma — o caso perdeu o sentido:\n{seco.stdout}"
    assert descem == soltas, (
        "o `--exigir` e o `--seco` discordam sobre quem pode descer — são "
        "duas fronteiras onde a docstring promete uma:\n"
        f"  --seco solta:    {sorted(soltas)}\n"
        f"  --exigir manda:  {sorted(descem)}\n{exigir.stdout}")
    assert SO_NOME in descem, (
        "a citada só pelo nome sumiu da lista do portão, e o `--mover` vai "
        "descê-la assim mesmo — é o arranjo difícil, e é onde as duas "
        f"fronteiras discordam:\n{exigir.stdout}")


def test_o_exigir_reprova_exatamente_quando_o_mover_teria_o_que_fazer(tmp_path):
    """rc=1 ⇔ o `--mover` desce alguma coisa. Medido MOVENDO, não lendo."""
    sprints = _as_tres(tmp_path)
    antes = {p.name for p in sprints.glob("*.md")}

    exigir = _roda(tmp_path, "--exigir")
    _roda(tmp_path, "--mover")

    desceram = antes - {p.name for p in sprints.glob("*.md")}
    assert (exigir.returncode == 1) == bool(desceram), (
        f"o portão devolveu rc={exigir.returncode} e o `--mover` desceu "
        f"{len(desceram)}: {sorted(desceram)}\n{exigir.stdout}")
    descem = {Path(p).name for p in _os_md_do_bloco(
        exigir.stdout, "podem descer AGORA:", "Rode scripts/")}
    assert descem == desceram, (
        "o portão nomeou uma lista e o disco recebeu outra:\n"
        f"  portão: {sorted(descem)}\n  disco:  {sorted(desceram)}")
