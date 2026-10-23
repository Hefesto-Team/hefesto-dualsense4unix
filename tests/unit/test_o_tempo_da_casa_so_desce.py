"""O tempo da casa só desce: a memória do rápido não vê o bytecode, e a catraca do tempo morde."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar(rel: str, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


RECIBO = _carregar("scripts/recibo_da_medida.py", "_recibo_do_tempo")


# --- a memória do rápido: o bytecode que os portões escrevem não muda a chave ---------------------


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Uma árvore git com `src/` e `scripts/` rastreados e o bytecode ignorado, como a da casa."""
    (tmp_path / "src/pacote").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src/pacote/a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "scripts/b.py").write_text("b = 2\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        "__pycache__/\n*.pyc\nscripts/dispositivo.txt\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "x")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "base")
    return tmp_path


def _chave(raiz: Path, entradas: list[str]) -> str | None:
    ent = RECIBO.Entradas(raiz)
    return RECIBO.chave_do_portao(ent, "ambiente", "um-portao", "pytest", "", entradas)


def _escreve_bytecode(raiz: Path) -> None:
    for pasta in ("src/pacote", "scripts"):
        alvo = raiz / pasta / "__pycache__"
        alvo.mkdir(exist_ok=True)
        (alvo / "x.cpython-312.pyc").write_bytes(b"\x00bytecode novo")


@pytest.mark.parametrize(
    "entradas", ([], ["src/**", "scripts/**"], ["src/pacote/*.py", "scripts/*"]),
    ids=("sem-quinta-coluna", "globs-largos", "globs-do-py-e-do-resto"))
def test_o_bytecode_escrito_durante_a_corrida_nao_muda_a_chave(
        arvore: Path, entradas: list[str]) -> None:
    antes = _chave(arvore, entradas)
    assert antes, "o portão tem de poder ser lembrado"
    _escreve_bytecode(arvore)
    assert _chave(arvore, entradas) == antes, (
        "o `.pyc` que o próprio portão escreve mudou a chave: todo verde se descarta "
        "(«a árvore mudou durante a corrida») e a memória nunca lembra")


def test_o_fonte_ignorado_de_scripts_continua_na_chave(arvore: Path) -> None:
    """Só o bytecode sai: o resto do ignorado de `scripts/` segue entrando."""
    ausente = _chave(arvore, [])
    (arvore / "scripts/dispositivo.txt").write_text("um\n", encoding="utf-8")
    um = _chave(arvore, [])
    (arvore / "scripts/dispositivo.txt").write_text("dois\n", encoding="utf-8")
    assert len({ausente, um, _chave(arvore, [])}) == 3


def test_o_py_mudado_continua_mudando_a_chave(arvore: Path) -> None:
    antes = _chave(arvore, ["src/**"])
    (arvore / "src/pacote/a.py").write_text("a = 2\n", encoding="utf-8")
    assert _chave(arvore, ["src/**"]) != antes


def test_mordida_com_o_bytecode_devolvido_a_chave_a_chave_muda(
        arvore: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RECIBO, "_BYTECODE", re.compile(r"(?!x)x"))
    antes = _chave(arvore, ["src/**", "scripts/**"])
    _escreve_bytecode(arvore)
    assert _chave(arvore, ["src/**", "scripts/**"]) != antes, (
        "a mordida não mordeu: com o bytecode na chave, o `.pyc` novo tinha de mudá-la")


# --- o ci-local lê a tabela e os workflows UMA vez ------------------------------------------------

CI_LOCAL = RAIZ / "scripts" / "ci-local.sh"


def _awks_da_corrida(tmp_path: Path, *args: str, script: Path = CI_LOCAL) -> int:
    """Quantos `awk` o script cria numa corrida: um `awk` de mentira os conta e passa adiante."""
    import os
    import shutil

    awk_real = shutil.which("awk")
    assert awk_real
    pasta = tmp_path / "shim"
    pasta.mkdir()
    registro = tmp_path / "awk.log"
    registro.write_text("")
    contador = pasta / "awk"
    contador.write_text(f'#!/bin/bash\necho x >> "{registro}"\nexec {awk_real} "$@"\n')
    contador.chmod(0o755)
    env = {**os.environ, "PATH": f"{pasta}{os.pathsep}{os.environ['PATH']}"}
    feito = subprocess.run(["bash", str(script), *args], capture_output=True, text=True,
                           env=env, check=False, timeout=60)
    assert feito.returncode in (0, 1), feito.stderr
    return len(registro.read_text().splitlines())


# A tabela da casa tem dezenas de jobs. Lida uma vez, a conferência gasta ~23 `awk` e o preço não
# cresce com a tabela; relida a cada pergunta, eram 749 (0,8 s só para listar) e crescia com ela.
TETO_DE_AWK = 60


@pytest.mark.parametrize("args", (["--listar"], ["--rapido", "--conferir"]),
                         ids=("listar", "conferir-rapido"))
def test_o_ci_de_casa_le_a_tabela_e_os_workflows_uma_vez(tmp_path: Path, args: list[str]) -> None:
    quantos = _awks_da_corrida(tmp_path, *args)
    assert 0 < quantos <= TETO_DE_AWK, (
        f"o ci-local criou {quantos} `awk` (teto {TETO_DE_AWK}): a tabela ou os workflows "
        "voltaram a ser relidos a cada pergunta")


def test_mordida_o_ci_de_casa_que_rele_a_cada_pergunta_estoura_o_teto(tmp_path: Path) -> None:
    """A versão de antes da cura (cada pergunta relê os workflows) tem de passar do teto."""
    texto = CI_LOCAL.read_text(encoding="utf-8")
    trocas = (
        ('jobs_do_yaml() { [ -z "$_JOBS_YAML" ] || printf \'%s\\n\' "$_JOBS_YAML"; }',
         "jobs_do_yaml() { _jobs_do_yaml_lidos; }"),
        ('arquivo_do_job() { [ -z "${ARQUIVO_DO_JOB[$1]:-}" ] || printf \'%s\\n\' '
         '"${ARQUIVO_DO_JOB[$1]}"; }',
         "arquivo_do_job() { jobs_do_yaml | awk -v j=\"$1\" '$2==j {print $1; exit}'; }"),
        ('[ "$tipo" = EM-TAG ] || [ -n "${ARQUIVO_DO_JOB[$j]:-}" ]',
         '[ "$tipo" = EM-TAG ] || jobs_do_yaml | awk -v j="$j" \'$2==j {ok=1} END{exit !ok}\''),
    )
    torto = texto
    for antes, depois in trocas:
        assert antes in torto, antes
        torto = torto.replace(antes, depois)
    raiz = tmp_path / "raiz"  # o script acha a raiz pelo próprio caminho: uma raiz de mentira
    (raiz / "scripts").mkdir(parents=True)
    (raiz / ".github").symlink_to(RAIZ / ".github")
    (raiz / "scripts" / "ci-local").symlink_to(RAIZ / "scripts" / "ci-local")
    copia = raiz / "scripts" / "ci-local.sh"
    copia.write_text(torto, encoding="utf-8")
    quantos = _awks_da_corrida(tmp_path, "--listar", script=copia)
    assert quantos > TETO_DE_AWK, f"a mordida não mordeu: só {quantos} `awk` sem a cura"


# --- a catraca do tempo: tempo é ruído, então o piso tem folga; sobe pago, desce sozinho -------

TEMPO = _carregar("scripts/o-tempo-da-casa.py", "_o_tempo_da_casa")
CADERNO_DO_TEMPO = TEMPO.CADERNO

_QUEM = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t", "GIT_COMMITTER_NAME": "t",
         "GIT_COMMITTER_EMAIL": "t@t.t", "GIT_CONFIG_NOSYSTEM": "1"}


_MARCA = "        corrida árvore=t1 arquivos=72 partição=p1\n"


def _parte(n: int, segundos: float, marca: str = _MARCA, total: int = 72) -> str:
    """Uma `parte-NN.txt` como o `rodar-a-suite.sh` escreve: o cabeçalho, a marca e o sumário."""
    return (f"suíte — {total} arquivos em 24 partes\n{marca}"
            f"  parte-{n:02d} (3 arq): 10 passed in {segundos:.2f}s (0:01:40)\n")


def _escreve_casa(casa: Path, suite_s: float = 2400.0, rapido_s: int = 40, completo_s: int = 60,
                  com_rapido: bool = True) -> None:
    """Os registros do fecho, de mentira: 24 partes de uma corrida que somam `suite_s`, rápidos e um
    completo."""
    suite = casa / "fecho" / "suite"
    suite.mkdir(parents=True, exist_ok=True)
    for n in range(TEMPO.PARTES):
        (suite / f"parte-{n:02d}.txt").write_text(_parte(n, suite_s / TEMPO.PARTES),
                                                   encoding="utf-8")
    if com_rapido:
        for i in range(7):
            log = casa / f"rapido-{i:04d}.log"
            log.write_text(f"tempo: {rapido_s} s de parede; 90 s de portão somados.\n",
                           encoding="utf-8")
            os.utime(log, (1_000_000 + i, 1_000_000 + i))
    (casa / "fecho" / "portoes-1.out").write_text(
        f"portões — árvore x\n         camadas rapido completo\ntempo: {completo_s} s de parede; "
        "400 s de portão somados; 0 lembrado(s) sem rodar.\n", encoding="utf-8")


@pytest.fixture
def mundo(tmp_path: Path) -> tuple[Path, Path]:
    """`(raiz, casa)`: uma raiz git com o caderno do tempo (piso 2400/40/60) e a casa de mentira."""
    raiz, casa = tmp_path / "raiz", tmp_path / "casa"
    raiz.mkdir()
    casa.mkdir()
    _escreve_casa(casa)
    assert TEMPO.main(["--raiz", str(raiz), "--casa", str(casa), "--aceitar"]) == 0
    arquivo = raiz / CADERNO_DO_TEMPO
    caderno = json.loads(arquivo.read_text(encoding="utf-8"))
    for nome, folga in ((TEMPO.SUITE, 10), (TEMPO.RAPIDO, 15), (TEMPO.COMPLETO, 20)):
        caderno["medidas"][nome]["folga"] = folga
    arquivo.write_text(json.dumps(caderno, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    _git(raiz, "init", "-q", "-b", "dev")
    _git(raiz, "add", ".")
    _commit(raiz, "base")
    return raiz, casa


def _commit(raiz: Path, mensagem: str) -> None:
    subprocess.run(["git", "-C", str(raiz), "commit", "-q", "--allow-empty", "-m", mensagem],
                   check=True, capture_output=True, env={**os.environ, **_QUEM})


def _topo(raiz: Path) -> str:
    return subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def _piso(raiz: Path, nome: str) -> dict:
    return json.loads((raiz / CADERNO_DO_TEMPO).read_text(encoding="utf-8"))["medidas"][nome]


def _roda(raiz: Path, casa: Path, *args: str, base: str | None = None) -> int:
    extra = ["--base", base] if base else []
    return TEMPO.main(["--raiz", str(raiz), "--casa", str(casa), *extra, *args])


def test_dentro_da_folga_nada_muda(
        mundo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    # D-1610-O-TEMPO-DA-CASA-SO-DESCE
    raiz, casa = mundo
    antes = (raiz / CADERNO_DO_TEMPO).read_bytes()
    _escreve_casa(casa, suite_s=2600.0, rapido_s=44, completo_s=70)  # +8% / +10% / +17%: ruído
    assert _roda(raiz, casa) == 0
    assert _roda(raiz, casa, "--fechar") == 0
    assert (raiz / CADERNO_DO_TEMPO).read_bytes() == antes, "o ruído mexeu no piso"
    assert "dentro da folga" in capsys.readouterr().out


def test_subir_alem_da_folga_sem_tempo_reprova_e_diz_a_medida(
        mundo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    raiz, casa = mundo
    _escreve_casa(casa, suite_s=2800.0)  # +16,7%, folga de 10%
    assert _roda(raiz, casa) == 1
    saida = capsys.readouterr().out
    assert "suite-pytest-s" in saida and "folga de 10%" in saida
    assert _roda(raiz, casa, "--fechar", base=_topo(raiz)) == 1
    assert _piso(raiz, TEMPO.SUITE)["piso"] == 2400, "reprovado não sobe piso"


def test_subir_com_tempo_na_faixa_paga_e_o_piso_sobe_com_a_razao(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    base = _topo(raiz)
    _commit(raiz, "chore(x): testes novos\n\nTempo: suite-pytest-s trinta testes novos da onda")
    _escreve_casa(casa, suite_s=2800.0)
    assert _roda(raiz, casa, "--fechar", "--conferir", base=base) == 0
    assert _piso(raiz, TEMPO.SUITE)["piso"] == 2400, "--conferir gravou"
    assert _roda(raiz, casa, "--fechar", base=base) == 0
    registro = _piso(raiz, TEMPO.SUITE)
    assert registro["piso"] == 2800
    assert registro["razao"] == "trinta testes novos da onda"
    assert registro["subidas"][-1]["de"] == 2400 and registro["subidas"][-1]["para"] == 2800
    assert registro["folga"] == 10, "a subida apagou a folga do caderno"


def test_tempo_sem_razao_ou_de_outra_medida_nao_paga(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    base = _topo(raiz)
    _commit(raiz, "chore(x): a\n\nTempo: suite-pytest-s")
    _commit(raiz, "chore(x): b\n\nTempo: rapido-mediana-s razão de outra medida")
    _escreve_casa(casa, suite_s=2800.0)
    assert _roda(raiz, casa, "--fechar", base=base) == 1
    assert _piso(raiz, TEMPO.SUITE)["piso"] == 2400


def test_descer_alem_da_folga_baixa_o_piso_e_so_o_dele(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    _escreve_casa(casa, suite_s=1800.0, rapido_s=40)  # a suíte desce 25%; o rápido não se mexe
    antes_rapido = _piso(raiz, TEMPO.RAPIDO)
    assert _roda(raiz, casa, "--fechar", "--conferir") == 0
    assert _piso(raiz, TEMPO.SUITE)["piso"] == 2400, "--conferir gravou"
    assert _roda(raiz, casa, "--fechar") == 0
    assert _piso(raiz, TEMPO.SUITE)["piso"] == 1800
    assert _piso(raiz, TEMPO.SUITE)["folga"] == 10
    assert _piso(raiz, TEMPO.RAPIDO) == antes_rapido


def test_descer_dentro_da_folga_nao_regrava(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    antes = (raiz / CADERNO_DO_TEMPO).read_bytes()
    _escreve_casa(casa, suite_s=2250.0)  # -6%: dentro de 10%
    assert _roda(raiz, casa, "--fechar") == 0
    assert (raiz / CADERNO_DO_TEMPO).read_bytes() == antes


def test_a_mediana_ignora_uma_corrida_lenta(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    lenta = casa / "rapido-0099.log"
    lenta.write_text("tempo: 400 s de parede; 900 s de portão somados.\n", encoding="utf-8")
    os.utime(lenta, (2_000_000, 2_000_000))
    censo = TEMPO.censo_do_rapido(casa)
    assert censo.numero == 40 and censo.universo == 8
    assert _roda(raiz, casa) == 0


def test_medida_sem_dado_avisa_no_fecho_e_reprova_no_modo_simples(
        mundo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    raiz, casa = mundo
    for log in casa.glob("rapido-*.log"):
        log.unlink()
    assert _roda(raiz, casa, "--fechar") == 0
    assert "AVISO rapido-mediana-s" in capsys.readouterr().out
    assert _roda(raiz, casa) == 1, "piso numérico sobre o que não se mede é piso falso"
    assert _piso(raiz, TEMPO.RAPIDO)["piso"] == 40


def test_suite_com_parte_faltando_nao_vira_zero(tmp_path: Path) -> None:
    _escreve_casa(tmp_path)
    (tmp_path / "fecho" / "suite" / "parte-07.txt").unlink()
    censo = TEMPO.censo_da_suite(tmp_path)
    assert censo.numero is None and "parte-07" in (censo.indisponivel or "")
    (tmp_path / "fecho" / "suite" / "parte-07.txt").write_text("sem sumário\n", encoding="utf-8")
    assert TEMPO.censo_da_suite(tmp_path).numero is None


def test_o_processo_proprio_do_webkit_entra_na_soma(tmp_path: Path) -> None:
    _escreve_casa(tmp_path, suite_s=2400.0)
    base = TEMPO.censo_da_suite(tmp_path).numero
    parte = tmp_path / "fecho" / "suite" / "parte-00.txt"
    parte.write_text(parte.read_text(encoding="utf-8")
                     + "    test_a, em processo próprio: 14 passed in 50.00s\n", encoding="utf-8")
    assert TEMPO.censo_da_suite(tmp_path).numero == base + 50


def test_medida_sem_piso_e_sem_piso_nunca_verde(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    arquivo = raiz / CADERNO_DO_TEMPO
    caderno = json.loads(arquivo.read_text(encoding="utf-8"))
    del caderno["medidas"][TEMPO.COMPLETO]
    arquivo.write_text(json.dumps(caderno), encoding="utf-8")
    assert _roda(raiz, casa) == 1
    assert _roda(raiz, casa, "--fechar") == 1


def test_sem_folga_no_caderno_a_catraca_recusa(mundo: tuple[Path, Path]) -> None:
    raiz, casa = mundo
    arquivo = raiz / CADERNO_DO_TEMPO
    caderno = json.loads(arquivo.read_text(encoding="utf-8"))
    del caderno["medidas"][TEMPO.SUITE]["folga"]
    arquivo.write_text(json.dumps(caderno), encoding="utf-8")
    assert _roda(raiz, casa) == 2


def test_o_caderno_da_casa_tem_as_tres_medidas_com_folga_e_piso() -> None:
    caderno = json.loads((RAIZ / CADERNO_DO_TEMPO).read_text(encoding="utf-8"))["medidas"]
    assert set(caderno) == {TEMPO.SUITE, TEMPO.RAPIDO, TEMPO.COMPLETO}
    for nome, registro in caderno.items():
        assert isinstance(registro["piso"], int) and registro["piso"] > 0, nome
        assert isinstance(registro["folga"], int) and 0 < registro["folga"] <= 30, nome


def test_mordida_sem_a_folga_o_ruido_reprova(
        mundo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Com a folga zerada, o mesmo +8% do caso «dentro da folga» reprova: o caso depende dela."""
    raiz, casa = mundo
    _escreve_casa(casa, suite_s=2600.0)
    assert _roda(raiz, casa) == 0
    monkeypatch.setattr(TEMPO.CatracaDoTempo, "folga", lambda self, nome: 0)
    assert _roda(raiz, casa) == 1, "a mordida não mordeu: a folga não decide nada"


def test_mordida_sem_o_pagamento_a_subida_com_tempo_reprova(
        mundo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    raiz, casa = mundo
    base = _topo(raiz)
    _commit(raiz, "chore(x): a\n\nTempo: suite-pytest-s uma razão")
    _escreve_casa(casa, suite_s=2800.0)
    monkeypatch.setattr(TEMPO, "pagamentos_da_faixa", lambda *_a, **_k: {})
    assert _roda(raiz, casa, "--fechar", base=base) == 1, "sem o trailer a subida não passa"


# --- a suíte só soma uma corrida (O-TEMPO-DA-SUITE-SO-SOMA-UMA-CORRIDA-01) ------------------------


def test_uma_parte_de_outra_corrida_deixa_a_suite_indisponivel(tmp_path: Path) -> None:
    _escreve_casa(tmp_path)
    assert TEMPO.censo_da_suite(tmp_path).numero == 2400
    parte = tmp_path / "fecho" / "suite" / "parte-05.txt"
    parte.write_text(_parte(5, 100.0, "        corrida árvore=t0 arquivos=70 partição=p0\n", 70),
                     encoding="utf-8")
    censo = TEMPO.censo_da_suite(tmp_path)
    assert censo.numero is None
    assert (censo.indisponivel or "").startswith("partes de 2 corridas"), censo.indisponivel
    assert "70 arquivos, partição p0 (partes 05)" in (censo.indisponivel or "")


def test_a_pasta_sem_a_marca_diz_quantas_corridas_o_cabecalho_separa(tmp_path: Path) -> None:
    """As partes de antes da marca (23/10): o cabeçalho separa as partições; sem ele, nada prova."""
    pasta = tmp_path / "fecho" / "suite"
    pasta.mkdir(parents=True)
    for n in range(TEMPO.PARTES):
        total = 2051 if n < 18 else 2043 if n == 18 else 2044
        (pasta / f"parte-{n:02d}.txt").write_text(_parte(n, 100.0, "", total), encoding="utf-8")
    censo = TEMPO.censo_da_suite(tmp_path)
    assert censo.numero is None and (censo.indisponivel or "").startswith("partes de 3 corridas")
    for n in range(TEMPO.PARTES):
        (pasta / f"parte-{n:02d}.txt").write_text(_parte(n, 100.0, ""), encoding="utf-8")
    censo = TEMPO.censo_da_suite(tmp_path)
    assert censo.numero is None and "não trazem a marca da corrida" in (censo.indisponivel or "")


def test_o_fecho_que_reaproveitou_recibo_nao_alimenta_o_piso(tmp_path: Path) -> None:
    _escreve_casa(tmp_path)
    reaproveitadas = tmp_path / "fecho" / "suite" / TEMPO.REAPROVEITADAS
    reaproveitadas.write_text("partes com o recibo de antes: 00 01\n", encoding="utf-8")
    censo = TEMPO.censo_da_suite(tmp_path)
    assert censo.numero is None and "reaproveitou o recibo" in (censo.indisponivel or "")
    reaproveitadas.write_text("partes com o recibo de antes:\n", encoding="utf-8")
    assert TEMPO.censo_da_suite(tmp_path).numero == 2400


def test_a_parte_trocada_vira_aviso_no_fecho_e_o_piso_fica(
        mundo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    raiz, casa = mundo
    _escreve_casa(casa, suite_s=4800.0)  # o dobro: sem a conferência, reprovaria
    (casa / "fecho" / "suite" / "parte-23.txt").write_text(
        _parte(23, 200.0, "        corrida árvore=t9 arquivos=72 partição=p9\n"), encoding="utf-8")
    assert _roda(raiz, casa, "--fechar") == 0
    saida = capsys.readouterr().out
    assert "AVISO suite-pytest-s: sem dado hoje" in saida and "partes de 2 corridas" in saida, saida
    assert _piso(raiz, TEMPO.SUITE)["piso"] == 2400


def test_mordida_sem_a_conferencia_da_marca_a_parte_trocada_entra_na_soma(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _escreve_casa(tmp_path)
    (tmp_path / "fecho" / "suite" / "parte-05.txt").write_text(
        _parte(5, 1100.0, "        corrida árvore=t0 arquivos=70 partição=p0\n", 70),
        encoding="utf-8")
    assert TEMPO.censo_da_suite(tmp_path).numero is None
    monkeypatch.setattr(TEMPO, "_corrida", lambda _texto: "árvore t1, 72 arquivos, partição p1")
    assert TEMPO.censo_da_suite(tmp_path).numero == 3400, "a mordida não mordeu: a marca não decide"


def _arvore_da_suite(tmp_path: Path, arquivos: int) -> Path:
    """Uma árvore git de mentira com o `rodar-a-suite.sh` de verdade e `arquivos` testes."""
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True, exist_ok=True)
    (raiz / "scripts" / "rodar-a-suite.sh").write_bytes(
        (RAIZ / "scripts" / "rodar-a-suite.sh").read_bytes())
    unit = raiz / "tests" / "unit"
    unit.mkdir(parents=True, exist_ok=True)
    for n in range(arquivos):
        (unit / f"test_conta_{n}.py").write_text(f"def test_{n}():\n    assert True\n")
    if not (raiz / ".git").exists():
        _git(raiz, "init", "-q", "-b", "dev")
    _git(raiz, "add", ".")
    return raiz


def _marca_da_suite(raiz: Path, tmp_path: Path) -> str:
    """A linha da marca que o script imprime a seco (sem rodar pytest), em duas partes."""
    py = tmp_path / "py-de-mentira"
    py.write_text("#!/bin/bash\nexit 0\n")
    py.chmod(0o755)
    fora = ("PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD", "PARTIDO", "LOTE",
            "PARTES_EM_PARALELO", "LISTAR_O_WEBKIT", "CSV_DOS_TEMPOS")
    env = {k: v for k, v in os.environ.items() if k not in fora}
    env.update({"PY": str(py), "A_SECO": "1", "PARTES": "2", "SAIDA": str(tmp_path / "saida"),
                "PARTES_EM_PARALELO": "0"})
    feito = subprocess.run(["bash", str(raiz / "scripts" / "rodar-a-suite.sh")], cwd=raiz,
                           capture_output=True, text=True, timeout=120, check=False, env=env)
    assert feito.returncode == 0, feito.stdout[-800:] + feito.stderr[-800:]
    achado = TEMPO._MARCA.search(feito.stdout)
    assert achado, f"o script não imprimiu a marca que o censo lê: {feito.stdout[:400]}"
    return str(achado[0]).strip()


def test_o_script_da_suite_marca_a_arvore_os_arquivos_e_a_particao(tmp_path: Path) -> None:
    raiz = _arvore_da_suite(tmp_path, 3)
    primeira = _marca_da_suite(raiz, tmp_path)
    assert "arquivos=3 " in primeira
    assert _marca_da_suite(raiz, tmp_path) == primeira, "a mesma árvore deu duas marcas"
    (raiz / "tests" / "unit" / "test_conta_0.py").write_text("def test_0():\n    assert 1\n")
    _git(raiz, "add", ".")
    outra_arvore = _marca_da_suite(raiz, tmp_path)
    assert outra_arvore != primeira and "arquivos=3 " in outra_arvore
    assert outra_arvore.split()[-1] == primeira.split()[-1], "a partição mudou sem mudar a lista"
    _arvore_da_suite(tmp_path, 4)
    mais_um = _marca_da_suite(raiz, tmp_path)
    assert "arquivos=4 " in mais_um and mais_um.split()[-1] != primeira.split()[-1]

