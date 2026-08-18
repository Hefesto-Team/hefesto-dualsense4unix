"""O contrato IPC sai do DISPATCHER — IPC-DOC-GERADO-01.

O defeito, medido em 13/08/2026: `docs/protocol/ipc-unix-socket.md` trazia uma
tabela "Métodos v1" com DEZ linhas escritas à mão, e o dicionário `_handlers` de
`daemon/ipc_server.py` registrava TRINTA E SETE métodos. Faltava a família
inteira do rumble, mais `plugin.list`, `plugin.reload`, `daemon.pause`,
`daemon.resume` e `profile.apply_draft`.

O QUE ESTE ARQUIVO DEFENDE NÃO É A TABELA — É O NÚMERO
-------------------------------------------------------
A contagem de métodos ausentes do documento já saiu 15, 17, 18 e 14 em
levantamentos do mesmo dia, sem commit no meio: cada régua contava de um jeito e
todas escreviam o resultado como fato. Um número que quatro medições não
reproduzem não é fato. Por isso a entrega é um GERADOR com `--check`, e não uma
tabela nova: escrito à mão, o número volta a divergir na próxima leitura.

PROVA DE QUE MORDE (13/08/2026) — em `scripts/gerar-contrato-ipc.py`, trocado o
corpo de `divergencias` por `return []` (o jeito mais barato de desligar um
`--check` de conteúdo sem mexer no resto): caíram os quatro testes que cobram a
comparação — `test_metodo_novo_no_dispatcher_faz_o_check_reprovar`,
`test_bloco_editado_a_mao_e_acusado`,
`test_o_bloco_desatualizado_com_mtime_mais_novo_e_acusado` e
`test_documentar_o_metodo_na_prosa_muda_a_coluna_de_contrato` —, todos com
`saiu 0`. Cura devolvida, os oito verdes.

A árvore de brinquedo tem a mesma FORMA da real (um `_handlers` num
`__post_init__`, um mixin com `async def _handle_*`, um documento com os
marcadores) e não a real por um motivo: o número da árvore real muda a cada
método novo, e um teste que o fixasse mediria a data da última leva.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
GERADOR = RAIZ_REAL / "scripts" / "gerar-contrato-ipc.py"
CI = RAIZ_REAL / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = RAIZ_REAL / ".pre-commit-config.yaml"

COMANDO = "scripts/gerar-contrato-ipc.py --check"

ABRE = "<!-- BLOCO GERADO por scripts/gerar-contrato-ipc.py — não edite à mão -->"
FECHA = "<!-- FIM DO BLOCO GERADO -->"

DISPATCHER = """\
class IpcServer:
    def __post_init__(self) -> None:
        self._handlers = {
            "profile.switch": self._handle_profile_switch,
            "rumble.set": self._handle_rumble_set,
        }
"""

MIXIN = '''\
class IpcHandlersMixin:
    async def _handle_profile_switch(self, params):
        """Aplica perfil escolhido pela usuária."""

    async def _handle_rumble_set(self, params):
        """Aplica rumble com política de intensidade."""
'''

DOCUMENTO = f"""\
# Protocolo IPC

O `profile.switch` troca o perfil ativo, e é o único com contrato em prosa aqui.

{ABRE}
{FECHA}
"""


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Árvore de brinquedo, já com o bloco recém-gerado nela."""
    (tmp_path / "scripts").mkdir()
    daemon = tmp_path / "src" / "hefesto_dualsense4unix" / "daemon"
    daemon.mkdir(parents=True)
    (tmp_path / "docs" / "protocol").mkdir(parents=True)

    shutil.copy(GERADOR, tmp_path / "scripts" / GERADOR.name)
    (daemon / "ipc_server.py").write_text(DISPATCHER, encoding="utf-8")
    (daemon / "ipc_handlers.py").write_text(MIXIN, encoding="utf-8")
    documento(tmp_path).write_text(DOCUMENTO, encoding="utf-8")

    gerado = roda(tmp_path)
    assert gerado.returncode == 0, gerado.stderr
    return tmp_path


def documento(arvore: Path) -> Path:
    return arvore / "docs" / "protocol" / "ipc-unix-socket.md"


def roda(arvore: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(arvore / "scripts" / GERADOR.name), *args],
        capture_output=True, text=True, cwd=arvore, check=False)


def confere(arvore: Path) -> subprocess.CompletedProcess[str]:
    return roda(arvore, "--check")


def envelhece_as_fontes(arvore: Path) -> None:
    """Deixa o documento mais NOVO que as fontes — o verde falso do mtime.

    É o estado em que o `--check` do mapa passava sempre até 12/08, e é o estado
    natural de um runner: o `actions/checkout` escreve a árvore em ordem de
    caminho, e `docs/` sai depois de `src/`.
    """
    ontem = time.time() - 86400
    for fonte in (arvore / "src").rglob("*.py"):
        os.utime(fonte, (ontem, ontem))
    agora = time.time()
    os.utime(documento(arvore), (agora, agora))


def test_o_bloco_recem_gerado_passa_no_check(arvore: Path) -> None:
    """O controle. Sem ele, os outros sete poderiam estar reprovando por nada."""
    saida = confere(arvore)
    assert saida.returncode == 0, saida.stderr
    assert "atualizado" in saida.stdout


def test_o_bloco_traz_o_metodo_o_endereco_do_handler_e_a_contagem(
    arvore: Path,
) -> None:
    """As quatro colunas saem do código, e a contagem sai com elas."""
    texto = documento(arvore).read_text(encoding="utf-8")
    assert "**2 métodos**" in texto, "a contagem gerada sumiu do bloco"
    assert "`rumble.set`" in texto
    assert "(`_handle_rumble_set`)" in texto
    assert "daemon/ipc_handlers.py:5" in texto, (
        "o endereço do handler não é o do `async def` — endereço gerado é a "
        "única espécie que não apodrece")


def test_metodo_novo_no_dispatcher_faz_o_check_reprovar(arvore: Path) -> None:
    """A MORDIDA do item: é assim que o documento chegou ao estado de 13/08.

    Registrar um método e não escrever contrato nenhum era, até hoje, uma
    operação silenciosa. A partir daqui ela reprova, e o erro nomeia o método.
    """
    servidor = arvore / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_server.py"
    servidor.write_text(
        servidor.read_text(encoding="utf-8").replace(
            '"rumble.set": self._handle_rumble_set,',
            '"rumble.set": self._handle_rumble_set,\n'
            '            "plugin.reload": self._handle_plugin_reload,'),
        encoding="utf-8")
    envelhece_as_fontes(arvore)   # e ainda assim tem de reprovar

    saida = confere(arvore)
    assert saida.returncode == 1, (
        "um método novo entrou no dispatcher e o contrato não reclamou — é "
        f"exatamente como o documento ficou com dez linhas. Disse: {saida.stdout!r}")
    assert "DESATUALIZADO" in saida.stderr
    assert "plugin.reload" in saida.stderr, (
        "o erro não diz QUAL método apareceu")


def test_bloco_editado_a_mao_e_acusado(arvore: Path) -> None:
    """O inverso: mexer no bloco sem mexer no código também é divergência."""
    alvo = documento(arvore)
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("**2 métodos**", "**9 métodos**"),
        encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode == 1, (
        f"o número foi editado à mão e o portão passou. Disse: {saida.stdout!r}")
    assert "9 métodos" in saida.stderr, "o erro não mostra a linha que divergiu"


def test_o_bloco_desatualizado_com_mtime_mais_novo_e_acusado(arvore: Path) -> None:
    """O CORAÇÃO: a comparação é de CONTEÚDO, nunca de relógio.

    Comparar mtime deu verde falso das duas maneiras possíveis no `gerar-mapa.py`
    (MAPA-CONTEUDO-01, 12/08). Este nasce do lado certo, e é este teste que o
    segura lá.
    """
    alvo = documento(arvore)
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace(
            "Aplica rumble com política de intensidade.", "outra coisa qualquer"),
        encoding="utf-8")
    envelhece_as_fontes(arvore)

    saida = confere(arvore)
    assert saida.returncode == 1, (
        "o bloco divergia do código e o portão passou porque o mtime do "
        f"documento era o mais novo. Disse: {saida.stdout!r}")
    assert "outra coisa qualquer" in saida.stderr


def test_documentar_o_metodo_na_prosa_muda_a_coluna_de_contrato(
    arvore: Path,
) -> None:
    """A coluna que conta a dívida — e ela reage a quem paga a dívida.

    `rumble.set` nasce `**não**` porque a prosa do brinquedo só cita
    `profile.switch`. Escrever uma linha sobre ele na prosa muda a coluna: o
    `--check` reprova até alguém regerar, e depois de regerar a dívida caiu.
    """
    alvo = documento(arvore)
    assert "| `rumble.set` |" in alvo.read_text(encoding="utf-8")
    assert alvo.read_text(encoding="utf-8").count("| **não** |") == 1

    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace(
            "e é o único com contrato em prosa aqui.",
            "e o `rumble.set` liga a vibração."),
        encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode == 1, (
        "a prosa ganhou o contrato do método e o bloco continuou dizendo que "
        f"ele não tem. Disse: {saida.stdout!r}")

    assert roda(arvore).returncode == 0
    assert "| **não** |" not in alvo.read_text(encoding="utf-8"), (
        "a dívida foi paga na prosa e a coluna não caiu")


def test_marcadores_apagados_reprovam_em_voz_alta(arvore: Path) -> None:
    """Apagar os marcadores é o jeito de voltar a escrever a lista à mão."""
    alvo = documento(arvore)
    texto = alvo.read_text(encoding="utf-8")
    alvo.write_text(texto[:texto.index(ABRE)], encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode == 1
    assert "SEM BLOCO GERADO" in saida.stderr


def test_a_arvore_de_verdade_esta_atualizada() -> None:
    """Contra a árvore REAL: o publicado é o que o dispatcher produz hoje."""
    saida = subprocess.run(
        [sys.executable, str(GERADOR), "--check"],
        capture_output=True, text=True, cwd=RAIZ_REAL, check=False)
    assert saida.returncode == 0, (
        "o contrato IPC publicado não reflete o dispatcher — rode "
        f"`python3 scripts/gerar-contrato-ipc.py`:\n{saida.stderr}")


def test_o_portao_esta_ligado_no_ci_e_no_pre_commit() -> None:
    """PORTÃO-VIVO-01: gate que ninguém roda não é gate, é arquivo."""
    yaml = pytest.importorskip("yaml")

    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    passos = [
        {**passo, "__job__": nome}
        for nome, job in (dados.get("jobs") or {}).items()
        for passo in job.get("steps") or []
    ]
    rodam = [p for p in passos if COMANDO in " ".join(str(p.get("run", "")).split())]
    assert rodam, f"o CI não chama `{COMANDO}`"
    for passo in rodam:
        assert not passo.get("continue-on-error"), (
            f"o passo '{passo.get('name', passo['__job__'])}' relata, não protege")

    hooks = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    entradas = [
        hook.get("entry", "")
        for repositorio in hooks.get("repos") or []
        for hook in repositorio.get("hooks") or []
    ]
    assert any(COMANDO in entrada for entrada in entradas), (
        f"nenhum hook do pre-commit roda `{COMANDO}`")
