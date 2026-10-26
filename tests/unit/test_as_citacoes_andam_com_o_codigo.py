"""As citações `arquivo:linha` andam com o código — o `scripts/reapontar-citacoes.py`."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "reapontar-citacoes.py"
REGUA_DO_SRC = RAIZ / "tests" / "unit" / "test_portao_o_par_com_metade_ligada.py"

ALVO = '''"""O alvo de mentira."""

VALOR = 1


def primeira():
    return 1


def segunda():
    x = 2
    return x


def terceira():
    return 3
'''

CSV = (
    "id,prosa\n"
    'linha.um,"a conta em src/hefesto_dualsense4unix/alvo.py:10-12 (`segunda`, que soma)'
    ' · outra em src/hefesto_dualsense4unix/alvo.py:15 (`terceira`)"\n'
)
MD = "# Doc\n\nO `terceira` em `src/hefesto_dualsense4unix/alvo.py:15-16` responde.\n"
CITANTE = '"""Quem cita."""\n\n# `segunda` mora em `alvo.py:10-12`.\nVALOR = 2\n'


def _git(raiz: Path, *args: str) -> str:
    feito = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=régua",
            "-c",
            "user.email=regua@exemplo.invalid",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return feito.stdout


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    """Um repositório com o alvo, um CSV do mapa, um `.md` da canônica e um citante em src/."""
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (pacote / "citante.py").write_text(CITANTE, encoding="utf-8")
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "data" / "mapa.csv").write_text(CSV, encoding="utf-8")
    (raiz / "docs" / "protocol").mkdir(parents=True)
    (raiz / "docs" / "protocol" / "x.md").write_text(MD, encoding="utf-8")
    (raiz / "tests" / "unit").mkdir(parents=True)
    shutil.copy(REGUA_DO_SRC, raiz / "tests" / "unit" / REGUA_DO_SRC.name)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    yield raiz


def _script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("reapontar_citacoes", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["reapontar_citacoes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _inserir_no_topo(raiz: Path, linhas: int, *, commitar: bool) -> None:
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "alvo.py"
    texto = alvo.read_text(encoding="utf-8").split("\n")
    novo = texto[:2] + [f"EXTRA_{n} = {n}" for n in range(linhas)] + texto[2:]
    alvo.write_text("\n".join(novo), encoding="utf-8")
    if commitar:
        _git(raiz, "commit", "-q", "-am", "o código anda")


def _rodar(raiz: Path, *, escrever: bool = True) -> tuple[list[str], list[str]]:
    return _script().reapontar(raiz, escrever=escrever)  # type: ignore[no-any-return]


def _validar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts" / "validar-citacoes-de-linha.py"),
            "--all",
            "--root",
            str(raiz),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("commitar", [True, False], ids=["andou-num-commit", "andou-sem-commit"])
def test_o_codigo_anda_e_as_citacoes_vao_junto(repo: Path, commitar: bool) -> None:
    """O caso de toda costura: código inserido acima do que se cita."""
    _inserir_no_topo(repo, 3, commitar=commitar)
    assert _validar(repo).returncode == 1, "a premissa: as citações apodreceram"

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert _validar(repo).returncode == 0, _validar(repo).stdout
    csv = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert "alvo.py:13-15 (`segunda`" in csv and "alvo.py:18 (`terceira`)" in csv, csv
    md = (repo / "docs" / "protocol" / "x.md").read_text(encoding="utf-8")
    assert "alvo.py:18-19`" in md, md
    citante = (repo / "src" / "hefesto_dualsense4unix" / "citante.py").read_text(encoding="utf-8")
    assert "`alvo.py:13-15`" in citante, citante
    assert csv == CSV.replace(":10-12", ":13-15").replace(":15 (", ":18 ("), csv


def test_a_funcao_que_mudou_de_lugar_e_achada_pelo_bloco(repo: Path) -> None:
    """``segunda`` vai para o fim do arquivo: nenhum hunk a leva, o bloco idêntico sim."""
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    texto = alvo.read_text(encoding="utf-8")
    bloco = "def segunda():\n    x = 2\n    return x\n\n\n"
    alvo.write_text(texto.replace(bloco, "") + "\n\n" + bloco.rstrip("\n") + "\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "segunda muda de lugar")

    feitos, a_mao = _rodar(repo)

    assert _validar(repo).returncode == 0, (feitos, a_mao, _validar(repo).stdout)
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    onde = linhas.index("def segunda():") + 1
    csv = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert f"alvo.py:{onde}-{onde + 2} (`segunda`" in csv, csv


def test_o_que_sumiu_nao_se_chuta(repo: Path) -> None:
    """``segunda`` apagada: não há onde apontar, e o documento não muda."""
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("def segunda():\n    x = 2\n    return x\n", ""),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "segunda sai")
    antes = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")

    plano, _ = _rodar(repo, escrever=False)
    assert not any("alvo.py:10-12" in linha for linha in plano), plano

    _feitos, a_mao = _rodar(repo)

    assert any("segunda" in linha for linha in a_mao), a_mao
    depois = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert "alvo.py:10-12 (`segunda`" in depois, "a citação sem casa foi mexida"
    assert antes.count("\n") == depois.count("\n")


def test_endereco_que_serve_a_duas_promessas_volta_como_estava(repo: Path) -> None:
    """O mesmo endereço, escrito antes e depois de o código andar, com duas promessas."""
    md = repo / "docs" / "protocol" / "x.md"
    md.write_text(
        "# Doc\n\nO `primeira` em `src/hefesto_dualsense4unix/alvo.py:6`.\n", encoding="utf-8"
    )
    _git(repo, "commit", "-q", "-am", "a primeira promessa")
    _inserir_no_topo(repo, 3, commitar=True)
    md.write_text(
        md.read_text(encoding="utf-8")
        + "\nE o `VALOR` em `src/hefesto_dualsense4unix/alvo.py:6`.\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "a segunda promessa, no mesmo endereço")
    antes = md.read_text(encoding="utf-8")

    _feitos, a_mao = _rodar(repo)

    assert md.read_text(encoding="utf-8") == antes
    assert any("devolvido como estava" in linha for linha in a_mao), a_mao


def test_a_funcao_inteira_a_deriva_volta_ao_lugar(repo: Path) -> None:
    """A citação de ``segunda`` nasceu uma linha acima: 9-11, e a função é 10-12."""
    csv = repo / "docs" / "data" / "mapa.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace(
            "alvo.py:10-12 (`segunda`", "alvo.py:9-11 (`segunda`"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "a citação nasce à deriva")
    assert _validar(repo).returncode == 0, "a premissa: o validador não vê a deriva"

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert "alvo.py:10-12 (`segunda`" in csv.read_text(encoding="utf-8")


def test_a_funcao_que_cresceu_e_achada_no_historico(repo: Path) -> None:
    """``segunda`` ganha duas linhas por dentro e uma no topo: 11-15, com 10-12 ainda verde."""
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace(
            "    x = 2\n", "    x = 2\n    y = x\n    x = y\n"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "segunda cresce")
    _inserir_no_topo(repo, 1, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert "alvo.py:11-15 (`segunda`" in (repo / "docs" / "data" / "mapa.csv").read_text(
        encoding="utf-8"
    )


def test_o_trecho_de_dentro_da_funcao_nao_e_desta_pergunta(repo: Path) -> None:
    """Citar as duas primeiras linhas de ``segunda`` não é citar a função inteira."""
    csv = repo / "docs" / "data" / "mapa.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace(
            "alvo.py:10-12 (`segunda`", "alvo.py:10-11 (`segunda`"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "o trecho de dentro")

    feitos, _a_mao = _rodar(repo)

    assert not any("10-11" in linha for linha in feitos), feitos
    assert "alvo.py:10-11 (`segunda`" in csv.read_text(encoding="utf-8")


def test_o_trecho_que_abraca_o_def_de_fora_anda_com_a_funcao(repo: Path) -> None:
    """As duas primeiras linhas de ``segunda`` (10-11), e uma linha nasce em cima dela."""
    csv = repo / "docs" / "data" / "mapa.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace(
            "alvo.py:10-12 (`segunda`", "alvo.py:10-11 (`segunda`"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "o trecho do começo")
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("\ndef segunda", "\nOUTRO = 2\ndef segunda"),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "uma linha nasce em cima de segunda")
    assert _validar(repo).returncode == 1, "a premissa: a pergunta 3 do validador vê a deriva"

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert "alvo.py:11-12 (`segunda`" in csv.read_text(encoding="utf-8")
    assert _validar(repo).returncode == 0


MD_CURTA = (
    "# Doc\n\nO `segunda` em `src/hefesto_dualsense4unix/alvo.py:10-12`, "
    "e o `terceira` em `:15-16`.\n"
)


def test_a_forma_curta_da_mesma_linha_anda_junto(repo: Path) -> None:
    """A forma curta ``:N`` herda o arquivo da citação inteira da mesma linha."""
    doc = repo / "docs" / "protocol" / "curta.md"
    doc.write_text(MD_CURTA, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a forma curta")
    _inserir_no_topo(repo, 3, commitar=True)

    feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    texto = doc.read_text(encoding="utf-8")
    assert "alvo.py:13-15`" in texto and "`:18-19`" in texto, texto
    assert not any("(0x)" in f for f in feitos), feitos
    assert _validar(repo).returncode == 0, _validar(repo).stdout


def test_o_endereco_que_nao_esta_escrito_vai_para_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Troca que não escreveu nada não entra nos feitos."""
    doc = repo / "docs" / "protocol" / "curta.md"
    doc.write_text(MD_CURTA, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a forma curta")
    _inserir_no_topo(repo, 3, commitar=True)
    modulo = _script()
    monkeypatch.setattr(modulo, "_trocar_curta", lambda texto, _cit, _end: (texto, 0))

    feitos, a_mao = modulo.reapontar(repo, escrever=True)

    assert any("`:15-16`" not in f and "curta.md" in f and "forma curta" in f for f in a_mao), a_mao
    assert not any("curta.md" in f and "15-16" in f for f in feitos), feitos
    assert "`:15-16`" in doc.read_text(encoding="utf-8")


def test_sem_escrever_nada_muda(repo: Path) -> None:
    _inserir_no_topo(repo, 3, commitar=True)
    antes = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}

    feitos, _a_mao = _rodar(repo, escrever=False)

    assert feitos, "a seco, ele tem de dizer o que faria"
    depois = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert antes == depois


def test_o_script_roda_pela_linha_de_comando(repo: Path) -> None:
    _inserir_no_topo(repo, 2, commitar=True)
    feito = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(repo), "--escrever"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "reapontada(s)" in feito.stdout
    assert _validar(repo).returncode == 0


END = "src/hefesto_dualsense4unix/alvo.py"


def _escrever_e_commitar(raiz: Path, relativo: str, texto: str, mensagem: str) -> Path:
    arquivo = raiz / relativo
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    _git(raiz, "add", relativo)
    _git(raiz, "commit", "-q", "-m", mensagem)
    return arquivo


def _alvo_de(raiz: Path) -> Path:
    return raiz / "src" / "hefesto_dualsense4unix" / "alvo.py"


def test_a_crua_que_andou_doze_linhas_e_reapontada_no_md_e_no_csv(repo: Path) -> None:
    """Sem `em`/`no` + símbolo antes, o endereço não promete nada: só o histórico o leva."""
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/crua.md",
        f"# Crua\n\nA constante vale `{END}:3` e o corpo, `{END}:11-12`; de novo `{END}:3`.\n",
        "a crua nasce",
    )
    planilha = repo / "docs" / "data" / "mapa.csv"
    planilha.write_text(
        planilha.read_text(encoding="utf-8") + f'linha.dois,"o corpo em {END}:11-12 é lido"\n',
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "a crua nasce na planilha")
    _inserir_no_topo(repo, 12, commitar=True)

    plano, a_mao = _rodar(repo, escrever=False)
    assert a_mao == [], a_mao
    assert any("crua.md" in f and f"{END}:3` ->" in f and "(2x)" in f for f in plano), plano
    assert md.read_text(encoding="utf-8").count(f"{END}:3") == 2, "a seco, nada se escreve"

    modulo = _script()
    _feitos, a_mao = modulo.reapontar(repo, escrever=True)

    assert a_mao == [], a_mao
    texto = md.read_text(encoding="utf-8")
    assert texto.count(f"{END}:15") == 2 and f"{END}:23-24" in texto, texto
    assert f"{END}:3`" not in texto and f"{END}:11-12" not in texto, texto
    assert f"{END}:23-24 é lido" in planilha.read_text(encoding="utf-8")
    assert modulo.ESTATISTICA["andaram"] >= 3, modulo.ESTATISTICA


def test_o_bloco_que_se_repete_hoje_vai_para_a_mao_com_o_motivo(repo: Path) -> None:
    """O corpo de ``segunda`` ganha uma cópia: qual das duas era a citada?"""
    md = _escrever_e_commitar(
        repo, "docs/protocol/crua.md", f"# Crua\n\nO corpo, `{END}:11-12`.\n", "a crua nasce"
    )
    alvo = _alvo_de(repo)
    alvo.write_text(
        alvo.read_text(encoding="utf-8") + "\n\ndef outra():\n    x = 2\n    return x\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "o corpo ganha uma cópia")
    _inserir_no_topo(repo, 3, commitar=True)
    antes = md.read_text(encoding="utf-8")

    feitos, a_mao = _rodar(repo)

    assert any("crua.md" in f and "aparece 2 vezes" in f for f in a_mao), a_mao
    assert not any("crua.md" in f for f in feitos), feitos
    assert md.read_text(encoding="utf-8") == antes


def test_o_arquivo_que_encolheu_vai_para_a_mao(repo: Path) -> None:
    """A função citada saiu do arquivo, que agora tem menos linhas que o endereço."""
    md = _escrever_e_commitar(
        repo, "docs/protocol/crua.md", f"# Crua\n\nO fim, `{END}:15-16`.\n", "a crua nasce"
    )
    alvo = _alvo_de(repo)
    alvo.write_text(
        alvo.read_text(encoding="utf-8").split("def terceira")[0].rstrip("\n") + "\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "o arquivo encolhe")
    antes = md.read_text(encoding="utf-8")

    _feitos, a_mao = _rodar(repo)

    assert any("crua.md" in f and "nenhuma cópia intacta" in f for f in a_mao), a_mao
    assert md.read_text(encoding="utf-8") == antes


def test_a_crua_que_ja_nasceu_errada_nao_e_levada(repo: Path) -> None:
    """Além do fim, em branco e curta demais: o histórico prova que NUNCA apontou o citado."""
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/crua.md",
        f"# Crua\n\nAlém, `{END}:40`. Branco, `{END}:13`. Curta, `{END}:4-5`.\n",
        "a crua nasce errada",
    )
    _inserir_no_topo(repo, 3, commitar=True)
    antes = md.read_text(encoding="utf-8")

    feitos, a_mao = _rodar(repo)

    crua = [f for f in a_mao if "crua.md" in f]
    assert any("já nascia errado" in f for f in crua), crua
    assert any("em branco" in f for f in crua), crua
    assert not any("crua.md" in f for f in feitos), feitos
    assert md.read_text(encoding="utf-8") == antes


def test_o_limite_da_crua_esta_escrito_no_help() -> None:
    """A citação que nasceu apontando o lugar errado anda errada: o `--help` diz."""
    feito = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False
    )
    ajuda = " ".join(feito.stdout.split())
    assert "já nasceu errada anda errada" in ajuda and "rumble.ff" in ajuda, ajuda


def test_a_crua_nao_encadeia_um_endereco_no_outro(repo: Path) -> None:
    """``:3`` vai para ``:10`` e ``:10`` vai para ``:17``: o 10 novo não pode andar de novo."""
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/cascata.md",
        f"# Cascata\n\nA constante `{END}:3`, e a função `{END}:10`.\n",
        "dois endereços encadeados",
    )
    _inserir_no_topo(repo, 7, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert md.read_text(encoding="utf-8") == (
        f"# Cascata\n\nA constante `{END}:10`, e a função `{END}:17`.\n"
    )


def test_o_mesmo_endereco_de_duas_epocas_vai_para_a_mao(repo: Path) -> None:
    """Escrito antes e depois de o código andar: não há como saber qual cópia vale por qual."""
    md = _escrever_e_commitar(
        repo, "docs/protocol/crua.md", f"# Crua\n\nA constante `{END}:3`.\n", "a primeira época"
    )
    _inserir_no_topo(repo, 3, commitar=True)
    md.write_text(md.read_text(encoding="utf-8") + f"\nOutra coisa, `{END}:3`.\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "a segunda época, o mesmo número")
    antes = md.read_text(encoding="utf-8")

    _feitos, a_mao = _rodar(repo)

    assert any("crua.md" in f and "épocas diferentes" in f for f in a_mao), a_mao
    assert md.read_text(encoding="utf-8") == antes


def test_a_crua_recem_escrita_e_confiada_e_a_inexistente_nao(repo: Path) -> None:
    """Sem commit ainda: vale como está. Linha que não existe, não."""
    md = repo / "docs" / "protocol" / "nova.md"
    md.write_text(f"# Nova\n\nBoa `{END}:3`. Má `{END}:90`.\n", encoding="utf-8")

    feitos, a_mao = _rodar(repo, escrever=False)

    assert not feitos, feitos
    assert any("nova.md" in f and "a linha não existe" in f for f in a_mao), a_mao
    assert not any("nova.md" in f and f"{END}:3`" in f for f in a_mao), a_mao


CITANTE_CURTO = (
    '"""Quem cita as duas, a inteira e a curta."""\n\n'
    "# O `primeira` nasce em `alvo.py:6`, e a constante fica em `:3`.\nVALOR = 2\n"
)


def test_a_forma_curta_em_prosa_de_src_e_reconhecida_e_levada(repo: Path) -> None:
    """O modelo do `luz_do_mic.py:554`: a inteira andava e a curta, ao lado, ficava."""
    citante = _escrever_e_commitar(
        repo,
        "src/hefesto_dualsense4unix/citante_curto.py",
        CITANTE_CURTO,
        "a curta nasce ao lado da inteira",
    )
    _inserir_no_topo(repo, 3, commitar=True)

    _feitos, a_mao = _rodar(repo)

    texto = citante.read_text(encoding="utf-8")
    assert "`alvo.py:9`" in texto and "`:6`" in texto, (texto, a_mao)
    assert not any("citante_curto" in f for f in a_mao), a_mao


def test_a_forma_curta_de_src_fica_no_lugar_quando_o_codigo_nao_andou(repo: Path) -> None:
    citante = _escrever_e_commitar(
        repo, "src/hefesto_dualsense4unix/citante_curto.py", CITANTE_CURTO, "a curta nasce"
    )

    feitos, a_mao = _rodar(repo)

    assert citante.read_text(encoding="utf-8") == CITANTE_CURTO
    assert not any("citante_curto" in f for f in (*feitos, *a_mao)), (feitos, a_mao)


def test_a_crase_ao_lado_confirma_ou_desmente_o_endereco_antes_de_andar(repo: Path) -> None:
    """Sem símbolo prometido, o identificador em crase colado ao endereço ainda é pista: o
    trecho do commit em que o endereço entrou tem de mostrá-lo, ou o endereço já nascia errado
    (foi o caso do `_CALIBRATION_FEATURE_ID` citado na linha de um comentário)."""
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/crua.md",
        f"# Crua\n\nCerta, `{END}:10`, onde a `segunda` começa.\n"
        f"Errada, `{END}:3`, onde a `segunda` começa.\n",
        "uma pista que confere e outra que não",
    )
    _inserir_no_topo(repo, 4, commitar=True)

    feitos, a_mao = _rodar(repo)

    texto = md.read_text(encoding="utf-8")
    assert f"`{END}:14`, onde" in texto, (texto, feitos, a_mao)
    assert f"`{END}:3`, onde" in texto, "a que nasceu errada não anda"
    assert any("já nascia errado" in f and "`segunda`" in f for f in a_mao), a_mao


def test_a_crase_da_linha_de_cima_tambem_e_pista(repo: Path) -> None:
    """O documento quebra a frase em linhas: a crase fica numa e o endereço na seguinte
    (foi o caso do `_PLAYER_LED_OVERFLOW`, cuja citação já nascia 6 linhas errada)."""
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/quebrada.md",
        f"# Quebrada\n\n> a figura é a de `segunda`, citada em\n> `{END}:3`, que não é ela.\n",
        "a crase na linha de cima",
    )
    _inserir_no_topo(repo, 4, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert f"`{END}:3`, que" in md.read_text(encoding="utf-8"), "nasceu errada: não anda"
    assert any("já nascia errado" in f and "`segunda`" in f for f in a_mao), a_mao


def test_o_validador_diz_que_nao_ve_a_crua_errada(repo: Path) -> None:
    """A crua que aponta uma linha que existe passa pelo validador; ele tem de dizer isso e
    apontar o instrumento que a pega, para o verde dele não valer por mais do que mede."""
    _escrever_e_commitar(
        repo, "docs/protocol/crua.md", f"# Crua\n\nSai de `{END}:3`.\n", "uma crua que abre"
    )
    saida = _validar(repo)
    assert saida.returncode == 0, saida.stdout
    assert "reapontar-citacoes.py" in saida.stdout, saida.stdout
    assert "só o histórico a pega" in saida.stdout, saida.stdout


def test_o_endereco_reescrito_numa_varredura_vai_para_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um commit que mexe em centenas de arquivos e reescreve o endereço de um documento que já
    existia não prova onde a linha estava (foi o `aba02.py:1702`, que a varredura de 02/10 deixou
    em branco). O documento que NASCE na varredura, esse, foi escrito olhando o código dela."""
    mod = _script()
    monkeypatch.setattr(mod, "VARREDURA_DE_ARQUIVOS", 3)
    velho = _escrever_e_commitar(
        repo, "docs/protocol/velho.md", "# Velho\n\nSai de `x`.\n", "um documento que já existia"
    )
    velho.write_text(f"# Velho\n\nA `segunda` está em `{END}:10`.\n", encoding="utf-8")
    nasce = repo / "docs" / "protocol" / "nasce.md"
    nasce.write_text(f"# Nasce\n\nA `segunda` está em `{END}:10`.\n", encoding="utf-8")
    for i in range(3):
        (repo / "docs" / f"outro{i}.txt").write_text("varrido\n", encoding="utf-8")
    _git(repo, "add", "docs")
    _git(repo, "commit", "-q", "-m", "a varredura")
    _inserir_no_topo(repo, 4, commitar=True)

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert f"`{END}:10`" in velho.read_text(encoding="utf-8"), "a varredura não prova: fica"
    assert f"`{END}:14`" in nasce.read_text(encoding="utf-8"), "o que nasce na varredura anda"
    assert any("varredura" in f and "velho.md" in f for f in a_mao), a_mao


def test_o_documento_renomeado_guarda_o_historico_de_antes_do_nome_novo(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Renomear o documento não o faz nascer de novo: o endereço entrou ANTES do nome novo.

    Medido em 08/10/2026: a `docs/data/decisoes-de-produto.csv` foi renomeada num commit de 279
    arquivos (380f46749), e sem seguir o nome o script tomava esse commit como o nascimento do
    documento: lia o código citado no instante errado e pulava a recusa da varredura que, no
    histórico inteiro, reescreveu o endereço (8002c142c)."""
    mod = _script()
    monkeypatch.setattr(mod, "VARREDURA_DE_ARQUIVOS", 3)
    _escrever_e_commitar(
        repo, "docs/protocol/antigo.md", f"# Doc\n\nO corpo, `{END}:11-12`.\n", "o endereço entra"
    )
    _inserir_no_topo(repo, 12, commitar=True)
    _git(repo, "mv", "docs/protocol/antigo.md", "docs/protocol/novo.md")
    for i in range(3):
        (repo / "docs" / f"outro{i}.txt").write_text("renomeado junto\n", encoding="utf-8")
    _git(repo, "add", "docs")
    _git(repo, "commit", "-q", "-m", "a renomeação, numa varredura")

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    novo = (repo / "docs" / "protocol" / "novo.md").read_text(encoding="utf-8")
    assert f"`{END}:23-24`" in novo, (novo, a_mao)
    assert not any("novo.md" in f for f in a_mao), a_mao


def test_a_linha_curta_demais_nao_identifica_o_citado(repo: Path) -> None:
    """Um `)` sozinho é único no arquivo de mentira, mas não diz o que foi citado: vai à mão."""
    curto = _escrever_e_commitar(
        repo, "src/hefesto_dualsense4unix/curto.py", "X = dict(\n    a=1,\n)\n", "o curto nasce"
    )
    md = _escrever_e_commitar(
        repo,
        "docs/protocol/curta.md",
        "# Curta\n\nO fecho, `src/hefesto_dualsense4unix/curto.py:3`.\n",
        "a crua nasce",
    )
    curto.write_text("A = 1\nB = 2\n" + curto.read_text(encoding="utf-8"), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "o curto anda")
    antes = md.read_text(encoding="utf-8")

    feitos, a_mao = _rodar(repo)

    assert any("curta.md" in f and "curta demais" in f for f in a_mao), a_mao
    assert not any("curta.md" in f for f in feitos), feitos
    assert md.read_text(encoding="utf-8") == antes


def test_o_endereco_que_um_reapontamento_em_massa_deixou_anda_pelo_endereco_de_antes(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O commit que troca dezenas de endereços de um documento que já existia é um reapontamento:
    o endereço que ele deixou foi calculado, e a linha dele não prova o que a frase citou.

    Medido em 08/10/2026: o 719e58a46 (13/09) reapontou 1629 endereços de uma vez, e 83 das 182
    trocas desta régua vinham dele; entre elas o `02-controles.html:2358` de uma frase sobre o
    quadradinho `--plastico`, que seguia para o link da aba Lançadores. Poucos arquivos tocados:
    a recusa da varredura não o pega. O endereço que ele deixou não anda; o de ANTES dele, que tem
    entrada própria, anda (a segunda chance). O documento que muda UM endereço anda direto.

    Os esperados saem do fixture: as linhas 3 (`VALOR`), 10 (`segunda`) e 15 (`terceira`) do
    ALVO andam 12 para baixo, e o reapontamento deixou `:1`, `:2` e `:4`, que não dizem nada."""
    mod = _script()
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    massa = _escrever_e_commitar(
        repo,
        "docs/protocol/massa.md",
        f"# Massa\n\nUm, `{END}:3`. Dois, `{END}:10`. Quatro, `{END}:15`.\n",
        "o documento já existia",
    )
    uma = _escrever_e_commitar(
        repo, "docs/protocol/uma.md", f"# Uma\n\nO valor, `{END}:1`.\n", "o outro também"
    )
    massa.write_text(
        f"# Massa\n\nUm, `{END}:1`. Dois, `{END}:2`. Quatro, `{END}:4`.\n", encoding="utf-8"
    )
    uma.write_text(f"# Uma\n\nO valor, `{END}:3`.\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "o reapontamento")
    _inserir_no_topo(repo, 12, commitar=True)

    feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert massa.read_text(encoding="utf-8") == (
        f"# Massa\n\nUm, `{END}:15`. Dois, `{END}:22`. Quatro, `{END}:27`.\n"
    ), (feitos, a_mao)
    assert f"`{END}:15`." in uma.read_text(encoding="utf-8"), (feitos, a_mao)
    assert not any("massa.md" in f for f in a_mao), a_mao


def test_o_endereco_de_antes_que_tambem_e_massa_fica_a_mao_com_o_motivo(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Três reapontamentos em massa em fila: a segunda chance dá duas voltas e para (o `--help`).
    O que ficou depois do terceiro vai à mão, e o motivo diz que o de antes também é massa."""
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    cadeia = _escrever_e_commitar(
        repo,
        "docs/protocol/cadeia.md",
        f"# Cadeia\n\nUm, `{END}:3`. Dois, `{END}:10`. Quatro, `{END}:15`.\n",
        "o documento já existia",
    )
    for um, dois, quatro in ((4, 5, 6), (7, 8, 9), (1, 2, 13)):
        cadeia.write_text(
            f"# Cadeia\n\nUm, `{END}:{um}`. Dois, `{END}:{dois}`. Quatro, `{END}:{quatro}`.\n",
            encoding="utf-8",
        )
        _git(repo, "commit", "-q", "-am", f"o reapontamento em massa {um}")
    _inserir_no_topo(repo, 12, commitar=True)
    antes = cadeia.read_text(encoding="utf-8")

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert cadeia.read_text(encoding="utf-8") == antes
    mao = [f for f in a_mao if "cadeia.md" in f]
    assert len(mao) == 3, a_mao
    assert all("reapontamento em massa" in f and "segunda chance" in f for f in mao), mao
