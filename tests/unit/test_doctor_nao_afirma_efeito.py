"""LED-QUE-NÃO-AFIRMA-01 — o diagnóstico que dizia OK para o que não mediu.

O `check_led_sysfs_gravavel` do `scripts/doctor.sh` faz UMA coisa só: um
`[[ -w "${node}/multi_intensity" ]]`. O comentário do próprio check declara,
em letra do autor, *"Só `test -w`: este check NUNCA escreve no nó"* — e ainda
assim o `pass` dele anunciava **"cor por-controle via sysfs OK"**, que é
afirmação de EFEITO.

Por que isso custa caro nesta casa: ela abre o doctor exatamente quando a cor
**não** está saindo. Um `[ OK ]` dizendo que a cor funciona manda procurar no
lugar errado — e as três causas que sobram depois da permissão continuam
todas de pé (hidraw em EIO no Bluetooth, `lightbar_source=="desired"`, driver
`hid_playstation` ausente). Permissão de escrita derruba UMA hipótese; não
prova nenhuma.

O que estes testes travam:

- **o `pass` não afirma efeito.** Nada de "cor ... OK", "a cor funciona", "cor
  aplicada": a linha diz o que foi medido, que é gravabilidade;
- **o `pass` declara a natureza da medição** — cita o `test -w`, ou que o
  check não escreve, ou que não é prova de efeito. Sem essa metade, "gravável"
  sozinho volta a ser lido como "funciona";
- **o check continua somente-leitura de verdade** — rodado contra um sysfs de
  mentira, o conteúdo do nó tem de sair byte a byte igual ao que entrou.

A mordida: devolvendo a frase antiga ao `doctor.sh` numa cópia, os dois
primeiros testes reprovam nomeando a linha inteira.

O check é extraído do `doctor.sh` e roda em bash contra um `/sys/class/leds`
de mentira em `tmp_path` — sem hardware, sem root, sem encostar no daemon.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8")

NOME_DO_CHECK = "check_led_sysfs_gravavel"

#: O que uma linha de diagnóstico NÃO pode dizer sem ter escrito no nó. Cada
#: padrão é uma afirmação de efeito — a primeira é literalmente a frase que
#: estava no ar até 13/08/2026.
AFIRMACOES_DE_EFEITO = (
    r"cor\s+por-controle\s+via\s+sysfs\s+OK",
    r"\bcor\b[^\n]{0,40}\bOK\b",
    r"\ba\s+cor\s+funciona\b",
    r"\bcor\s+aplicada\b",
    r"\bcor\s+sai\s+OK\b",
)

#: E o que ela PRECISA dizer para não ser lida como efeito.
MARCAS_DE_HONESTIDADE = (
    r"test\s+-w",
    r"NUNCA\s+escreve",
    r"não\s+prova",
    r"PERMISS[ÃA]O",
)


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


def _sem_comentarios(texto: str) -> str:
    """Tira comentário de linha inteira — o corpo do check, não a prosa dele."""
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    )


def _linha_do_pass(corpo: str) -> str:
    """A linha do `pass` do check — é ela que o usuário lê como `[ OK ]`."""
    for linha in _sem_comentarios(corpo).splitlines():
        nu = linha.strip()
        if nu.startswith("pass "):
            return nu
    raise AssertionError(f"{NOME_DO_CHECK} não tem linha `pass` — o check mudou de forma")


def test_bash_n_do_doctor() -> None:
    """Sanidade: a edição do texto não pode ter quebrado a sintaxe do script."""
    proc = subprocess.run(
        [BASH, "-n", str(DOCTOR_PATH)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr


def test_o_pass_nao_afirma_que_a_cor_funciona() -> None:
    linha = _linha_do_pass(_extrai_funcao_bash(DOCTOR, NOME_DO_CHECK))
    for padrao in AFIRMACOES_DE_EFEITO:
        assert not re.search(padrao, linha, re.IGNORECASE), (
            f"o `pass` de {NOME_DO_CHECK} afirma EFEITO ({padrao!r}) sem nunca ter "
            f"escrito no nó — o check só faz `test -w`. A linha é:\n  {linha}"
        )


def test_o_pass_declara_que_so_mediu_gravabilidade() -> None:
    linha = _linha_do_pass(_extrai_funcao_bash(DOCTOR, NOME_DO_CHECK))
    assert any(re.search(m, linha, re.IGNORECASE) for m in MARCAS_DE_HONESTIDADE), (
        "o `pass` precisa dizer que mediu PERMISSÃO (citar `test -w`, ou que o "
        "check não escreve, ou que não prova efeito) — sem isso, 'gravável' é "
        f"lido como 'a cor funciona'. A linha é:\n  {linha}"
    )


def test_o_check_nao_escreve_no_no(tmp_path: Path) -> None:
    """Roda o check contra um sysfs de mentira: o nó sai igual ao que entrou."""
    leds = tmp_path / "leds"
    no = leds / "0003:054C:0CE6.0001:rgb:indicator"
    no.mkdir(parents=True)
    conteudo = "1 2 3\n"
    intensidade = no / "multi_intensity"
    intensidade.write_text(conteudo, encoding="utf-8")
    dispositivo = tmp_path / "devices" / "pci0000:00" / "hid" / "controle"
    dispositivo.mkdir(parents=True)
    (no / "device").symlink_to(dispositivo)

    corpo = _extrai_funcao_bash(DOCTOR, NOME_DO_CHECK).replace(
        "/sys/class/leds", str(leds)
    )
    cena = tmp_path / "cena.sh"
    cena.write_text(
        "set -u\n"
        'pass() { printf "PASS %s\\n" "$*"; }\n'
        'warn() { printf "WARN %s\\n" "$*"; }\n'
        'info() { printf "INFO %s\\n" "$*"; }\n'
        f"{corpo}\n"
        f"{NOME_DO_CHECK}\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [BASH, str(cena)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert intensidade.read_text(encoding="utf-8") == conteudo, (
        "o check ESCREVEU no nó — ele é somente-leitura por contrato"
    )
    assert proc.stdout.startswith("PASS "), (
        f"nó gravável tinha de dar `pass`; saiu: {proc.stdout!r}"
    )


def test_a_mensagem_que_ela_le_nao_promete_cor(tmp_path: Path) -> None:
    """A frase RENDERIZADA (não o fonte) é a que ela lê — e ela também não mente."""
    leds = tmp_path / "leds"
    no = leds / "0005:054C:0CE6.0002:rgb:indicator"
    no.mkdir(parents=True)
    (no / "multi_intensity").write_text("0 0 0\n", encoding="utf-8")
    dispositivo = tmp_path / "devices" / "pci0000:00" / "hid" / "outro"
    dispositivo.mkdir(parents=True)
    (no / "device").symlink_to(dispositivo)

    corpo = _extrai_funcao_bash(DOCTOR, NOME_DO_CHECK).replace(
        "/sys/class/leds", str(leds)
    )
    cena = tmp_path / "cena.sh"
    cena.write_text(
        "set -u\n"
        'pass() { printf "PASS %s\\n" "$*"; }\n'
        'warn() { printf "WARN %s\\n" "$*"; }\n'
        'info() { printf "INFO %s\\n" "$*"; }\n'
        f"{corpo}\n"
        f"{NOME_DO_CHECK}\n",
        encoding="utf-8",
    )
    saida = subprocess.run(
        [BASH, str(cena)], capture_output=True, text=True, check=False
    ).stdout
    for padrao in AFIRMACOES_DE_EFEITO:
        assert not re.search(padrao, saida, re.IGNORECASE), (
            f"a mensagem que ela lê afirma EFEITO ({padrao!r}):\n  {saida.strip()}"
        )
    assert any(re.search(m, saida, re.IGNORECASE) for m in MARCAS_DE_HONESTIDADE), (
        f"a mensagem não declara que mediu só permissão:\n  {saida.strip()}"
    )
