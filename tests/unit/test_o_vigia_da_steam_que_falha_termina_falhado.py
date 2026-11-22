"""O-VIGIA-DA-STEAM-QUE-FALHA-TERMINA-FALHADO-E-AINDA-RODA-OS-OUTROS-PASSOS-01: a falha chega.

Dois lugares calavam a falha do vigia: o ``|| true`` e a resposta «nada pendente» do
``disable_steam_input.sh`` quando a ponte nem respondia, e o ``-`` de cada ``ExecStart=`` da
unidade. Aqui o script roda com um ``python3`` de mentira no ``PATH`` (imprime um traceback e sai
com o código dado) e com ``pgrep``, ``pkill`` e ``steam`` de mentira que só anotam a chamada: nada
abre nem fecha a Steam. A unidade se prova pela forma do texto e pela lógica do passo e do fecho
rodada em ``bash``; o que o systemd faz com a unidade só o systemd prova.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "disable_steam_input.sh"
UNIDADE = RAIZ / "assets" / "hefesto-steam-input-guard.service"

FERRAMENTAS = (
    "awk", "basename", "bash", "cat", "cmp", "cp", "date", "dirname", "env", "grep", "head", "ls",
    "mkdir", "mktemp", "mv", "readlink", "rm", "sed", "sh", "sleep", "sort", "stat", "tee",
    "touch", "tr", "wc",
)
TRACEBACK = (
    "Traceback (most recent call last):\\n"
    "ModuleNotFoundError: No module named 'structlog'"
)


def _executavel(caminho: Path, corpo: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/bin/sh\n" + corpo, encoding="utf-8")
    caminho.chmod(0o755)
    return caminho


class Mesa:
    """Um lar de mentira, um `PATH` de dublês e ferramentas comuns, e o diário das chamadas."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.bin = raiz / "bin"
        self.lar = raiz / "lar"
        self.diario = raiz / "chamadas.log"
        self.viva = raiz / "steam-viva"
        self.bin.mkdir()
        for nome in FERRAMENTAS:
            achado = shutil.which(nome)
            if achado:
                (self.bin / nome).symlink_to(achado)
        diario = shlex.quote(str(self.diario))
        _executavel(
            self.bin / "pgrep",
            f'echo "pgrep $*" >> {diario}\n[ -e {shlex.quote(str(self.viva))} ]\n',
        )
        _executavel(self.bin / "pkill", f'echo "pkill $*" >> {diario}\nexit 0\n')
        _executavel(self.bin / "steam", f'echo "steam $*" >> {diario}\nexit 0\n')
        real = shlex.quote(shutil.which("python3") or "/usr/bin/python3")
        _executavel(
            self.bin / "python3",
            f'case "$1" in -c) exec {real} "$@" ;; esac\n'
            f'echo "python3 $*" >> {diario}\n'
            'rc="${RC_DA_PONTE:-0}"\n'
            'case "$*" in *"${FALHA_EM:-}"*) ;; *) rc=0 ;; esac\n'
            'if [ "$rc" = 0 ] || [ "$rc" = 3 ] || [ "$rc" = 4 ]; then\n'
            '  case "$*" in *--estado*) echo \'{"pendentes": []}\'; exit 0 ;; esac\n'
            '  echo "[steam-input-ponte] sem o que fazer"; exit "$rc"\n'
            "fi\n"
            f'printf "{TRACEBACK}\\n" >&2\n'
            'exit "$rc"\n',
        )
        self.vdf = (
            self.lar / ".local" / "share" / "Steam" / "userdata" / "1000" / "config"
            / "localconfig.vdf"
        )
        self.vdf.parent.mkdir(parents=True)
        self.vdf.write_text(
            '"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t}\n}\n', encoding="utf-8"
        )

    def com_o_vdf_a_corrigir(self) -> None:
        """O vdf passa a ter o PSSupport ligado: o `--apply` e o `--apply-quiet` vão escrever."""
        self.vdf.write_text(
            '"UserLocalConfigStore"\n{\n\t"SteamController_PSSupport"\t\t"1"\n}\n',
            encoding="utf-8",
        )

    def roda(
        self, modo: str, *, rc_da_ponte: int = 0, falha_em: str = ""
    ) -> subprocess.CompletedProcess[str]:
        ambiente = {
            "PATH": str(self.bin),
            "HOME": str(self.lar),
            "XDG_CONFIG_HOME": str(self.lar / ".config"),
            "RC_DA_PONTE": str(rc_da_ponte),
            "FALHA_EM": falha_em,
        }
        return subprocess.run(
            [shutil.which("bash") or "/bin/bash", str(SCRIPT), modo],
            capture_output=True,
            text=True,
            env=ambiente,
            cwd=str(self.lar),
            timeout=120,
        )

    def chamadas(self) -> list[str]:
        if not self.diario.exists():
            return []
        return self.diario.read_text(encoding="utf-8").splitlines()

    def tocou_na_steam(self) -> list[str]:
        return [c for c in self.chamadas() if c.startswith(("pkill", "steam"))]


@pytest.fixture
def mesa(tmp_path: Path) -> Mesa:
    return Mesa(tmp_path)


MODOS = ["--apply-quiet", "--apply", "--status"]


@pytest.mark.parametrize("modo", MODOS)
def test_a_ponte_que_cai_nao_vira_nada_a_fazer(mesa: Mesa, modo: str) -> None:
    """MORDIDA: o `|| true` e o «nada pendente» à falha de perguntar devolvem o `nada-a-fazer`."""
    proc = mesa.roda(modo, rc_da_ponte=1)
    saida = proc.stdout + proc.stderr
    assert "resultado=erro" in saida, saida
    assert "nada-a-fazer" not in saida, saida
    assert proc.returncode != 0, saida
    assert mesa.tocou_na_steam() == []


@pytest.mark.parametrize(
    ("modo", "gesto"),
    [
        ("--status", "--estado"),
        ("--apply", "--estado"),
        ("--status", "--dry-run"),
        ("--apply", "--dry-run"),
        ("--apply-quiet", "--ligar"),
        ("--apply-quiet", "--desligar-fora-da-lista"),
    ],
)
def test_cada_pergunta_e_cada_escrita_da_ponte_conta_sozinha(
    mesa: Mesa, modo: str, gesto: str
) -> None:
    """MORDIDA: a pergunta que cai sozinha, com as outras respondendo, ainda é erro."""
    proc = mesa.roda(modo, rc_da_ponte=1, falha_em=gesto)
    saida = proc.stdout + proc.stderr
    assert "resultado=erro" in saida, saida
    assert "nada-a-fazer" not in saida, saida
    assert proc.returncode != 0, saida


@pytest.mark.parametrize("modo", ["--apply-quiet", "--apply"])
def test_o_texto_da_ponte_que_cai_segue_para_o_diario(mesa: Mesa, modo: str) -> None:
    proc = mesa.roda(modo, rc_da_ponte=1)
    assert "No module named 'structlog'" in proc.stdout + proc.stderr


@pytest.mark.parametrize(
    ("modo", "gesto"),
    [("--apply", "--estado"), ("--status", "--estado"), ("--apply", "--dry-run")],
)
def test_a_queixa_da_pergunta_que_cai_segue_para_o_diario(
    mesa: Mesa, modo: str, gesto: str
) -> None:
    """MORDIDA: a pergunta do `--apply` com a saída inteira em `/dev/null` cala o traceback."""
    proc = mesa.roda(modo, rc_da_ponte=1, falha_em=gesto)
    assert "No module named 'structlog'" in proc.stdout + proc.stderr


@pytest.mark.parametrize(
    ("modo", "gesto"),
    [
        ("--apply-quiet", "--ligar"),
        ("--apply-quiet", "--desligar-fora-da-lista"),
        ("--apply", "--ligar"),
        ("--apply", "--estado"),
        ("--apply", "--dry-run"),
    ],
)
def test_com_o_vdf_a_corrigir_a_ponte_que_cai_ainda_e_erro(
    mesa: Mesa, modo: str, gesto: str
) -> None:
    """MORDIDA: o `rc` zerado antes dos vdfs, ou a ponte e a pergunta esquecidas no `--apply`."""
    mesa.com_o_vdf_a_corrigir()
    proc = mesa.roda(modo, rc_da_ponte=1, falha_em=gesto)
    saida = proc.stdout + proc.stderr
    assert "resultado=erro" in saida, saida
    assert "resultado=aplicado" not in saida, saida
    assert proc.returncode != 0, saida
    assert mesa.tocou_na_steam() == []


@pytest.mark.parametrize("modo", ["--apply-quiet", "--apply"])
def test_com_o_vdf_a_corrigir_e_a_ponte_de_rotina_aplica(mesa: Mesa, modo: str) -> None:
    """O lar de mentira chega à escrita: sem isto o teste de cima passaria sem escrever nada."""
    mesa.com_o_vdf_a_corrigir()
    proc = mesa.roda(modo, rc_da_ponte=0)
    saida = proc.stdout + proc.stderr
    assert "resultado=aplicado" in saida, saida
    assert proc.returncode == 0, saida
    assert any("--gravar-vdf" in c for c in mesa.chamadas()), mesa.chamadas()
    assert mesa.tocou_na_steam() == []


@pytest.mark.parametrize("rc_da_ponte", [0, 3, 4])
@pytest.mark.parametrize("modo", MODOS)
def test_a_ponte_de_rotina_segue_como_antes(mesa: Mesa, modo: str, rc_da_ponte: int) -> None:
    """O 0, o 3 (adiada) e o 4 (incerta) não são falha: o resultado e o código seguem iguais."""
    proc = mesa.roda(modo, rc_da_ponte=rc_da_ponte)
    saida = proc.stdout + proc.stderr
    assert "resultado=nada-a-fazer" in saida, saida
    assert proc.returncode == 0, saida
    assert mesa.tocou_na_steam() == []


def test_com_a_steam_viva_o_vigia_adia_e_sai_zero(mesa: Mesa) -> None:
    """O adiado é rotina: a Steam aberta não chama a ponte nem vira falha."""
    mesa.viva.touch()
    proc = mesa.roda("--apply-quiet", rc_da_ponte=1)
    saida = proc.stdout + proc.stderr
    assert "resultado=adiado-steam-aberta" in saida, saida
    assert proc.returncode == 0
    assert not [c for c in mesa.chamadas() if c.startswith("python3")]
    assert mesa.tocou_na_steam() == []


def _palavras(valor: str) -> list[str]:
    """As palavras de um `ExecStart=` como o systemd as lê: aspas simples e `$$` é o `$`."""
    return [p.replace("\0", "$") for p in shlex.split(valor.replace("$$", "\0"))]


def _execs() -> list[str]:
    return [
        linha.split("=", 1)[1]
        for linha in UNIDADE.read_text(encoding="utf-8").splitlines()
        if linha.startswith("ExecStart=")
    ]


def _passos() -> list[list[str]]:
    return [_palavras(valor) for valor in _execs()[:-1]]


def test_a_unidade_tem_a_pasta_da_partida_e_o_fecho_no_fim() -> None:
    """MORDIDA: apague o fecho ou a pasta e a falha de um passo volta a terminar como concluída."""
    texto = UNIDADE.read_text(encoding="utf-8")
    assert "\nRuntimeDirectory=hefesto-steam-input-guard\n" in texto
    assert "SuccessExitStatus" not in texto
    fecho = _execs()[-1]
    assert "falhas" in fecho and "exit 1" in fecho
    assert "__" not in fecho


def test_a_espera_da_subida_segue_com_o_menos() -> None:
    texto = UNIDADE.read_text(encoding="utf-8")
    assert "\nExecStartPre=-/usr/bin/env python3 __SENTINELA__ --esperar-a-calma\n" in texto


def test_todo_passo_leva_o_seu_comando_pelo_passo_sem_o_menos() -> None:
    """MORDIDA: o `-` de volta apaga o código do passo; o passo sem `bash -c` o perde."""
    passos = _passos()
    assert len(passos) == 4, passos
    comandos = []
    for palavras in passos:
        assert palavras[:3] == ["/usr/bin/env", "bash", "-c"], palavras
        assert palavras[4] == "--", palavras
        assert not palavras[0].startswith("-")
        comandos.append(palavras[6:])
    assert comandos[0] == ["/usr/bin/env", "bash", "__SCRIPT__", "--apply-quiet"]
    assert comandos[1] == ["/usr/bin/env", "python3", "__SENTINELA__", "--reparar"]
    assert comandos[2] == ["__PYTHON_DO_PINO__", "__PROTON_PIN__", "--manter"]
    assert comandos[3] == ["/usr/bin/env", "python3", "__OPCOES_POR_JOGO__", "--aplicar"]


def _roda_a_partida(tmp_path: Path, saidas: list[int]) -> tuple[int, list[str], str]:
    """Roda os quatro passos e o fecho da unidade em `bash`, com comandos que saem com `saidas`.

    Devolve o código do fecho, a ordem em que os passos rodaram e o que ficou em `falhas`.
    """
    pasta = tmp_path / "partida"
    pasta.mkdir()
    ordem = tmp_path / "ordem.txt"
    ambiente = {**os.environ, "RUNTIME_DIRECTORY": str(pasta)}
    for numero, (palavras, codigo) in enumerate(zip(_passos(), saidas, strict=True), 1):
        falso = ["bash", "-c", f"echo passo-{numero} >> {shlex.quote(str(ordem))}; exit {codigo}"]
        comando = [*palavras[:6], *falso]
        feito = subprocess.run(
            comando, capture_output=True, text=True, env=ambiente, timeout=60, check=False
        )
        assert feito.returncode == 0, (numero, feito.stderr)
    fecho = subprocess.run(
        _palavras(_execs()[-1]),
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=60,
        check=False,
    )
    falhas = pasta / "falhas"
    return (
        fecho.returncode,
        ordem.read_text(encoding="utf-8").split() if ordem.exists() else [],
        falhas.read_text(encoding="utf-8") if falhas.exists() else "",
    )


@pytest.mark.parametrize(
    "saidas",
    [[0, 0, 0, 0], [0, 3, 0, 3], [3, 3, 4, 3], [0, 0, 2, 0], [0, 0, 7, 0]],
)
def test_a_partida_de_rotina_termina_bem_e_roda_os_quatro(
    tmp_path: Path, saidas: list[int]
) -> None:
    fecho, ordem, falhas = _roda_a_partida(tmp_path, saidas)
    assert fecho == 0
    assert falhas == ""
    assert ordem == ["passo-1", "passo-2", "passo-3", "passo-4"]


@pytest.mark.parametrize(
    ("saidas", "quem"),
    [
        ([1, 0, 0, 0], "passo-1"),
        ([0, 1, 0, 0], "passo-2"),
        ([0, 0, 5, 0], "passo-3"),
        ([0, 0, 0, 1], "passo-4"),
        ([0, 127, 0, 0], "passo-2"),
    ],
)
def test_a_falha_de_um_passo_falha_a_partida_e_os_outros_rodam(
    tmp_path: Path, saidas: list[int], quem: str
) -> None:
    """MORDIDA: sem o fecho a partida termina bem; o passo que sai com o código pula os outros."""
    fecho, ordem, falhas = _roda_a_partida(tmp_path, saidas)
    assert fecho == 1
    assert ordem == ["passo-1", "passo-2", "passo-3", "passo-4"]
    assert quem in falhas
    assert falhas.count("rc=") == 1


def test_duas_falhas_aparecem_as_duas(tmp_path: Path) -> None:
    fecho, ordem, falhas = _roda_a_partida(tmp_path, [1, 0, 6, 1])
    assert fecho == 1
    assert len(ordem) == 4
    assert falhas.count("rc=") == 3
