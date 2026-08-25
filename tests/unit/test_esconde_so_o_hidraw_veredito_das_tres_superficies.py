"""ESCONDE-SÓ-O-HIDRAW-01 (E1 e E3) — a régua que mentia sobre a própria cura.

Até 25/08/2026 o `check_hidraw_broker` do `scripts/doctor.sh` respondia à cena
abaixo com **`pass`** e o texto *"o jogo só vê o vpad"*:

```
/dev/hidraw4        crw-------   root:root                 <- escondido
/dev/input/event21  crw-rw----   + user:<ela>:rw-          <- qualquer processo dela
/dev/input/js0      crw-rw-r--   + user:<ela>:rw- e other::r--   <- e o mundo inteiro
```

Os três nós são **o mesmo controle** (medido nesta bancada em 25/08/2026, um
DualSense no cabo, `0003:054C:0CE6.0009`). O `hide` do broker age numa
superfície só — `hidraw` — e o veredito lia a contagem dela como resposta a
uma pergunta sobre três. É a família `O-PORTAO-QUE-NAO-MEDE-O-QUE-PROMETE` no
pior lugar possível: quem investiga *"por que o Steam mostra controle
dobrado"* — o terceiro controle dela — começava lendo um verde.

O que estes testes travam:

- **a cena de hoje sai `warn`, nunca `pass`**, e o aviso NOMEIA os nós de
  entrada abertos: sem o nome, ninguém sabe onde olhar;
- **as três formas de um nó estar alcançável** são medidas separadamente, cada
  uma com um teste que só ela faz passar — bit de leitura de `other` (o estado
  de fábrica do `jsN`), ACL nomeada (o que o `uaccess` dá no login) e grupo do
  nó com a sessão dentro dele (o acidente do grupo `input`, que existe nesta
  máquina e não numa limpa);
- **ausência de dado não é prova de cura.** Nó cujo sysfs não mapeia as outras
  duas superfícies fica FORA do veredito, e a linha diz que não afirma nada —
  o inverso do defeito de 09/08, em que o instrumento deu verde sobre o que
  não tinha olhado;
- **o `pass` só usa a frase "o jogo só vê o vpad" depois de fechar as TRÊS
  superfícies** — é a frase que mentia, e ela agora tem preço;
- **a fiação dos NOMES** dos nós escondidos, do `status` do broker até o
  veredito: sem os nomes o sysfs não tem por onde achar as outras duas
  superfícies, e o veredito inteiro degrada para "sem mapa" em silêncio;
- **Modo Nativo e daemon parado continuam decidindo antes** — o físico exposto
  é o esperado num, e a invariante quebrada é mais grave no outro.

A MORDIDA está em `TestAMordida...`: com `_tres_superficies_medir "$@"`
comentado no `doctor.sh` — a cura arrancada, o veredito voltando a ser a
contagem de hidraw — a cena de hoje volta a sair `pass` com a frase antiga.

Tudo roda em bash contra um `/dev` e um `/sys` de MENTIRA em `tmp_path`, com
`getfacl` de mentira: sem hardware, sem root, sem daemon, sem tocar a máquina.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8") if DOCTOR_PATH.exists() else ""

pytestmark = pytest.mark.skipif(not DOCTOR, reason="scripts/doctor.sh ausente")

#: As quatro funções do veredito, na ordem em que uma chama a outra.
FUNCOES = (
    "_nos_de_entrada_do_hidraw",
    "_entrada_alcancavel_pelo_jogo",
    "_tres_superficies_medir",
    "_veredito_do_hide",
)

#: A frase que mentia. Só pode aparecer num `pass` que mediu as três
#: superfícies — e o `TestAFraseQueMentia` é quem cobra isso.
FRASE_ANTIGA = "o jogo só vê o vpad"

#: O pai HID do DualSense FÍSICO desta bancada (USB, 25/08/2026).
HID_FISICO = "sys/devices/pci0000:00/0000:00:08.1/usb3/3-1/0003:054C:0CE6.0009"


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada no doctor.sh"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


# ---------------------------------------------------------------------------
# A cena: um /dev e um /sys de mentira
# ---------------------------------------------------------------------------


class Entrada:
    """Um nó de `/dev/input` do controle: nome, modo e se tem ACL nomeada."""

    def __init__(self, base: str, modo: int, *, acl: bool = False, grupo: bool = False):
        self.base = base
        self.modo = modo
        self.acl = acl
        self.grupo = grupo


def _monta_cena(raiz: Path, controles: dict[str, list[Entrada] | None]) -> list[str]:
    """Monta a árvore falsa e devolve os nós hidraw na ordem pedida.

    ``controles`` mapeia `hidrawN` para a lista de entradas do MESMO device
    HID. ``None`` encena o sysfs que não sabe responder — nó recém-sumido,
    replug no meio da leitura —, que é diferente de "está tudo fechado".
    """
    (raiz / "dev" / "input").mkdir(parents=True, exist_ok=True)
    (raiz / "sys" / "class" / "hidraw").mkdir(parents=True, exist_ok=True)
    nos: list[str] = []
    for i, (hidraw, entradas) in enumerate(controles.items()):
        nos.append(f"/dev/{hidraw}")
        classe = raiz / "sys" / "class" / "hidraw" / hidraw
        classe.mkdir(parents=True, exist_ok=True)
        if entradas is None:
            continue
        pai = raiz / f"{HID_FISICO}.{i:04d}"
        (pai / "input" / f"input{100 + i}").mkdir(parents=True, exist_ok=True)
        enlace = classe / "device"
        if not enlace.exists():
            enlace.symlink_to(pai)
        for entrada in entradas:
            (pai / "input" / f"input{100 + i}" / entrada.base).write_text("")
            no = raiz / "dev" / "input" / entrada.base
            no.write_text("")
            no.chmod(entrada.modo)
    return nos


def _stub_getfacl(raiz: Path) -> Path:
    """`getfacl` de mentira: só devolve `user:<eu>:rw-` para quem está em COM_ACL.

    Sem ele a cena não teria como encenar a ACL nomeada do `uaccess` — a
    árvore falsa em `tmp_path` não tem ACL nenhuma —, e a distinção entre "ACL
    da sessão" e "grupo do nó", que é o coração da função, sumiria.
    """
    binario = raiz / "bin"
    binario.mkdir(parents=True, exist_ok=True)
    stub = binario / "getfacl"
    stub.write_text(
        "#!/bin/sh\n"
        'alvo=""\n'
        'for a in "$@"; do alvo="$a"; done\n'
        'base=$(basename "$alvo")\n'
        'echo "# file: $base"\n'
        "echo 'user::rw-'\n"
        'case " $COM_ACL " in\n'
        '  *" $base "*) echo "user:$(id -un):rw-" ;;\n'
        "esac\n"
        "echo 'group::rw-'\n"
        "echo 'other::---'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return binario


def _roda(
    raiz: Path,
    controles: dict[str, list[Entrada] | None],
    *,
    hidden_count: int | None = None,
    daemon_vivo: int = 1,
    native_mode: str = "False",
    doctor: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Extrai as funções do doctor, reancora os caminhos na cena e roda."""
    fonte = DOCTOR if doctor is None else doctor
    corpo = "\n".join(_extrai_funcao_bash(fonte, nome) for nome in FUNCOES)
    corpo = corpo.replace("/sys/class/hidraw/", f"{raiz}/sys/class/hidraw/")
    corpo = corpo.replace("/dev/input/${base}", f"{raiz}/dev/input/${{base}}")
    nos = _monta_cena(raiz, controles)
    com_acl = " ".join(
        e.base
        for entradas in controles.values()
        if entradas
        for e in entradas
        if e.acl
    )
    if hidden_count is None:
        hidden_count = len(nos)
    script = raiz / "cena.sh"
    script.write_text(
        'pass() { echo "[PASS] $*"; }\n'
        'warn() { echo "[WARN] $*"; }\n'
        'fail() { echo "[FAIL] $*"; }\n'
        'info() { echo "[INFO] $*"; }\n'
        + corpo
        + f'\n_veredito_do_hide "{hidden_count}" "{daemon_vivo}" "{native_mode}"'
        + "".join(f' "{no}"' for no in nos)
        + "\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PATH"] = f"{_stub_getfacl(raiz)}{os.pathsep}{env['PATH']}"
    env["COM_ACL"] = com_acl
    return subprocess.run(
        [BASH, str(script)], capture_output=True, text=True, check=False, env=env
    )


#: A bancada de 25/08/2026, byte a byte: hidraw escondido, evdev com a ACL
#: dela, joydev com a ACL dela E o bit de leitura de `other`.
def _cena_de_hoje() -> dict[str, list[Entrada] | None]:
    return {
        "hidraw4": [
            Entrada("event21", 0o660, acl=True),
            Entrada("js0", 0o664, acl=True),
        ]
    }


#: O mesmo controle com as três superfícies fechadas — a cena que o `pass`
#: descreve, e que nesta casa ninguém produziu ainda.
def _cena_fechada() -> dict[str, list[Entrada] | None]:
    return {"hidraw4": [Entrada("event21", 0o600), Entrada("js0", 0o600)]}


class TestOVeredictoNaoMenteMais:
    def test_a_cena_de_hoje_sai_warn_e_nao_pass(self, tmp_path: Path) -> None:
        r = _roda(tmp_path, _cena_de_hoje())
        assert "[WARN]" in r.stdout, r.stdout
        assert "[PASS]" not in r.stdout, (
            "verde sobre um controle cujo evdev e joydev estão abertos — é a "
            "linha que mentia até 25/08/2026"
        )

    def test_o_aviso_nomeia_os_nos_abertos(self, tmp_path: Path) -> None:
        """Sem o nome, quem lê o aviso não sabe onde olhar."""
        r = _roda(tmp_path, _cena_de_hoje())
        assert "event21" in r.stdout, r.stdout
        assert "js0" in r.stdout, r.stdout

    def test_o_aviso_conta_controles_e_nao_so_nos(self, tmp_path: Path) -> None:
        """E3: o veredito é POR CONTROLE — `0 de 1`, não `1 nó escondido`."""
        r = _roda(tmp_path, _cena_de_hoje())
        assert "0 de 1" in r.stdout, r.stdout

    def test_as_tres_superficies_fechadas_sao_pass(self, tmp_path: Path) -> None:
        r = _roda(tmp_path, _cena_fechada())
        assert "[PASS]" in r.stdout, r.stdout
        assert "[WARN]" not in r.stdout, r.stdout
        assert "TRÊS superfícies" in r.stdout

    def test_meia_cura_continua_sendo_defeito(self, tmp_path: Path) -> None:
        """Um controle fechado e outro aberto não vira verde pela média."""
        cena: dict[str, list[Entrada] | None] = {
            "hidraw4": [Entrada("event21", 0o600), Entrada("js0", 0o600)],
            "hidraw5": [Entrada("event31", 0o660, acl=True), Entrada("js1", 0o600)],
        }
        r = _roda(tmp_path, cena)
        assert "[WARN]" in r.stdout, r.stdout
        assert "[PASS]" not in r.stdout
        assert "1 de 2" in r.stdout, r.stdout
        assert "event31" in r.stdout
        assert "js0" not in r.stdout, "o nó FECHADO não pode entrar na lista de abertos"


class TestAsTresFormasDeAlcancar:
    """Cada forma tem um teste que só ela faz passar — as três foram medidas
    nesta casa, e nenhuma é hipótese."""

    def test_bit_de_leitura_de_other_no_joydev(self, tmp_path: Path) -> None:
        """O estado de fábrica do `jsN`: `crw-rw-r--`, legível pelo mundo."""
        cena: dict[str, list[Entrada] | None] = {
            "hidraw4": [Entrada("event21", 0o600), Entrada("js0", 0o604)]
        }
        r = _roda(tmp_path, cena)
        assert "[WARN]" in r.stdout, r.stdout
        assert "js0" in r.stdout
        assert "event21" not in r.stdout

    def test_acl_nomeada_do_uaccess_no_evdev(self, tmp_path: Path) -> None:
        """`user:<ela>:rw-` — o que o login dá, e o que o `hide` tira do hidraw."""
        cena: dict[str, list[Entrada] | None] = {
            "hidraw4": [Entrada("event21", 0o600, acl=True), Entrada("js0", 0o600)]
        }
        r = _roda(tmp_path, cena)
        assert "[WARN]" in r.stdout, r.stdout
        assert "event21" in r.stdout
        assert "js0" not in r.stdout

    def test_grupo_do_no_com_a_sessao_dentro(self, tmp_path: Path) -> None:
        """O acidente do grupo `input` (OQ-6): funciona aqui, não numa limpa.

        O nó nasce no grupo primário de quem roda o teste, e `id -nG` o
        contém — que é exatamente a forma do `root:input` com ela dentro do
        grupo `input`. Sem este ramo o instrumento diria "fechado" para um nó
        que a máquina dela abre.
        """
        cena: dict[str, list[Entrada] | None] = {
            "hidraw4": [Entrada("event21", 0o640), Entrada("js0", 0o600)]
        }
        r = _roda(tmp_path, cena)
        assert "[WARN]" in r.stdout, r.stdout
        assert "event21" in r.stdout

    def test_no_sem_nenhuma_das_tres_nao_vira_alarme(self, tmp_path: Path) -> None:
        """`0600 root:root` sem ACL é fechado — e tem de sair do aviso."""
        r = _roda(tmp_path, _cena_fechada())
        assert "[WARN]" not in r.stdout, r.stdout


class TestAusenciaDeDadoNaoEProvaDeCura:
    """O defeito de 09/08 em traje novo: verde sobre o que não se olhou."""

    def test_sysfs_mudo_nao_afirma_que_o_jogo_so_ve_o_vpad(self, tmp_path: Path) -> None:
        r = _roda(tmp_path, {"hidraw4": None})
        assert "[WARN]" not in r.stdout, r.stdout
        linhas_pass = [ln for ln in r.stdout.splitlines() if ln.startswith("[PASS]")]
        assert linhas_pass, r.stdout
        for linha in linhas_pass:
            assert FRASE_ANTIGA not in linha, (
                "o `pass` afirmou o que não mediu: o sysfs não devolveu "
                f"superfície nenhuma. Linha: {linha}"
            )
        assert "NÃO afirma" in r.stdout, r.stdout

    def test_no_sem_mapa_nao_conta_como_escondido(self, tmp_path: Path) -> None:
        """Um controle mapeado e aberto, outro sem mapa: o aviso continua, e
        o sem-mapa é declarado fora da conta em vez de virar crédito."""
        cena: dict[str, list[Entrada] | None] = {
            "hidraw4": [Entrada("event21", 0o660, acl=True), Entrada("js0", 0o664)],
            "hidraw5": None,
        }
        r = _roda(tmp_path, cena)
        assert "[WARN]" in r.stdout, r.stdout
        assert "sem mapa no sysfs" in r.stdout, r.stdout
        assert "0 de 2" in r.stdout, r.stdout


class TestOsRamosQueDecidemAntes:
    def test_modo_nativo_nao_chega_a_medir_superficie(self, tmp_path: Path) -> None:
        """No Modo Nativo o físico DEVE estar exposto — o defeito é o hide."""
        r = _roda(tmp_path, _cena_de_hoje(), native_mode="True")
        assert "[WARN]" in r.stdout, r.stdout
        assert "Modo Nativo" in r.stdout
        assert "[PASS]" not in r.stdout
        assert "event21" not in r.stdout, "o veredito das três superfícies não é daqui"

    def test_daemon_parado_e_fail_com_a_cura_nomeada(self, tmp_path: Path) -> None:
        r = _roda(tmp_path, _cena_de_hoje(), daemon_vivo=0)
        assert "[FAIL]" in r.stdout, r.stdout
        assert "systemctl restart" in r.stdout, "o FAIL tem de nomear a cura"

    def test_nada_escondido_e_info(self, tmp_path: Path) -> None:
        r = _roda(tmp_path, {}, hidden_count=0)
        assert "[INFO]" in r.stdout, r.stdout
        assert "[PASS]" not in r.stdout
        assert "[WARN]" not in r.stdout
        assert "[FAIL]" not in r.stdout


class TestAFraseQueMentia:
    """Portão de fonte: a frase antiga tem preço, e o preço é medir as três."""

    def test_todo_pass_com_a_frase_declara_as_tres_superficies(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "_veredito_do_hide")
        for linha in corpo.splitlines():
            despido = linha.strip()
            if not despido.startswith("pass ") or FRASE_ANTIGA not in despido:
                continue
            assert "TRÊS superfícies" in despido, (
                "um `pass` voltou a usar a frase que mentia sem dizer que "
                f"mediu as três superfícies do controle. Linha: {despido}"
            )

    def test_o_veredito_e_uma_funcao_propria_e_testavel(self) -> None:
        """A régua que mentia nunca teve teste porque vivia soldada dentro de
        uma função de 220 linhas que precisa de systemd, socket e aparelho."""
        for nome in FUNCOES:
            assert f"\n{nome}() {{\n" in DOCTOR, f"{nome}() sumiu do doctor.sh"


class TestAFiacaoDosNomes:
    """Sem os NOMES dos nós escondidos não há veredito nenhum — e a degradação
    seria SILENCIOSA: tudo viraria "sem mapa" e o doctor voltaria a calar."""

    def test_o_status_do_broker_imprime_os_nomes(self) -> None:
        assert 'print("hidden_nodes=" + " ".join(hidden))' in DOCTOR, (
            "o bloco python que fala com o broker parou de publicar os nomes"
        )

    def test_o_check_le_os_nomes_e_os_repassa(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hidraw_broker")
        assert "s/^hidden_nodes=//p" in corpo, "os nomes não são lidos da saída"
        chamada = re.search(r"_veredito_do_hide[^\n]*", corpo)
        assert chamada is not None, "o check parou de chamar o veredito"
        assert "${hidden_nodes}" in chamada.group(0), (
            "o veredito foi chamado sem os nomes: ele mediria zero superfície "
            f"e degradaria para 'sem mapa' em silêncio. Chamada: {chamada.group(0)}"
        )


class TestOInstrumentoNaoCura:
    """Confere e NÃO cura: qual das três saídas o produto vai tomar é a E2, e
    a E2 é DELA. Nenhuma destas funções pode escrever permissão nenhuma."""

    def test_nenhuma_funcao_do_veredito_escreve_permissao(self) -> None:
        proibidos = ("setfacl", "chmod", "chown", "udevadm control", "usermod")
        for nome in FUNCOES:
            corpo = _extrai_funcao_bash(DOCTOR, nome)
            for verbo in proibidos:
                assert verbo not in corpo, f"{nome}() executa `{verbo}`"

    def test_o_no_de_mentira_sai_igual_ao_que_entrou(self, tmp_path: Path) -> None:
        _roda(tmp_path, _cena_de_hoje())
        for base, modo in (("event21", 0o660), ("js0", 0o664)):
            atual = (tmp_path / "dev" / "input" / base).stat().st_mode & 0o777
            assert atual == modo, f"{base} saiu {atual:04o}, entrou {modo:04o}"


class TestAMordidaDaCuraArrancada:
    """A prova de que a régua não sabe só passar.

    Com `_tres_superficies_medir "$@"` comentado — a cura arrancada, o
    veredito voltando a ser a contagem de hidraw —, a cena de hoje volta a
    sair `pass` com a frase antiga. É literalmente o `doctor.sh` de ontem.
    """

    def test_sem_a_medicao_das_superficies_a_cena_de_hoje_volta_a_ser_verde(
        self, tmp_path: Path
    ) -> None:
        arrancado = DOCTOR.replace(
            '    _tres_superficies_medir "$@"\n',
            '    : # _tres_superficies_medir "$@"  (cura arrancada)\n',
        )
        assert arrancado != DOCTOR, "a linha da cura mudou de forma"
        r = _roda(tmp_path, _cena_de_hoje(), doctor=arrancado)
        assert "[PASS]" in r.stdout, r.stdout
        assert "[WARN]" not in r.stdout, r.stdout

    def test_sem_o_ramo_da_acl_o_evdev_dela_passa_batido(self, tmp_path: Path) -> None:
        """A segunda mordida: a ACL nomeada é a única forma que abre o
        `event21` desta bancada. Arrancado o ramo, o instrumento jura que o
        controle está escondido — e o evdev dela continua aberto."""
        corpo = _extrai_funcao_bash(DOCTOR, "_entrada_alcancavel_pelo_jogo")
        alvo = "getfacl -p \"${no}\" 2>/dev/null | grep -Eq '^user:[^:]+:r'"
        assert alvo in corpo, "o ramo da ACL mudou de forma"
        arrancado = DOCTOR.replace(alvo, "false")
        cena: dict[str, list[Entrada] | None] = {
            "hidraw4": [Entrada("event21", 0o600, acl=True), Entrada("js0", 0o600)]
        }
        r = _roda(tmp_path, cena, doctor=arrancado)
        assert "[PASS]" in r.stdout, r.stdout
        assert "event21" not in r.stdout


class TestOPassNaoAfirmaSobreOQueNaoMediu:
    """O `pass` só pode falar dos controles que ele MEDIU.

    ACRESCENTADO em 25/08/2026 pela conferência da frente C4, e o defeito era
    real: `TRES_SUP_CONTROLES` é incrementado ANTES do `continue` que manda o
    nó sem mapa embora, então ele conta quem entrou na varredura, não quem foi
    medido. O `pass` usava esse número e afirmava as três superfícies fechadas
    de controles que a linha `info` logo acima acabara de declarar **fora do
    veredito**.

    É a mesma família do defeito que este bloco inteiro veio curar — a régua
    mentindo sobre a própria cura —, só que uma camada acima.
    """

    def _cena_uma_fechada_uma_sem_mapa(self) -> dict[str, list[Entrada] | None]:
        """Um controle com tudo fechado; outro que o sysfs não soube mapear.

        `None` encena o nó recém-sumido ou o replug no meio da leitura, que é
        diferente de "está tudo fechado" — a distinção que o `_monta_cena` já
        modelava e que o `pass` apagava.
        """
        return {
            "hidraw4": [Entrada("event21", 0o600), Entrada("js0", 0o600)],
            "hidraw5": None,
        }

    def test_o_pass_conta_os_medidos_e_nao_os_varridos(self, tmp_path: Path) -> None:
        r = _roda(tmp_path, self._cena_uma_fechada_uma_sem_mapa())
        assert "[PASS]" in r.stdout, r.stdout
        assert "dos 1 controle(s)" in r.stdout, (
            "o `pass` devia contar UM controle — o único que foi medido —, e "
            f"não os dois que entraram na varredura. Saiu:\n{r.stdout}"
        )
        assert "dos 2 controle(s)" not in r.stdout, (
            "o `pass` afirmou as três superfícies fechadas de DOIS controles, "
            "e um deles o sysfs não soube mapear. É o achado ALTA da "
            f"conferência da frente C4.\n{r.stdout}"
        )

    def test_o_pass_confessa_o_que_ficou_de_fora(self, tmp_path: Path) -> None:
        """Contar certo não basta: quem lê tem de saber que houve um não-medido.

        Sem esta linha, o `pass` "dos 1 controle(s)" seria verdadeiro e ainda
        assim enganoso — some o segundo controle sem dizer que ele existiu.
        """
        r = _roda(tmp_path, self._cena_uma_fechada_uma_sem_mapa())
        assert "NÃO afirmo nada sobre 1" in r.stdout, (
            f"o `pass` contou certo mas não disse o que ficou de fora:\n{r.stdout}"
        )
        assert "o jogo só vê o vpad" not in r.stdout, (
            "com um nó fora do veredito, o `pass` NÃO pode concluir que o jogo "
            f"só vê o vpad — ele não olhou para todos.\n{r.stdout}"
        )

    def test_sem_nenhum_sem_mapa_a_frase_forte_continua(self, tmp_path: Path) -> None:
        """A cura não pode ter custado a conclusão quando ela é VERDADE.

        Sem esta guarda passaria um "conserto" que apagasse a frase forte
        sempre — e o `pass` deixaria de dizer o que a pessoa precisa saber no
        caso em que tudo foi medido e tudo está fechado.
        """
        r = _roda(tmp_path, _cena_fechada())
        assert "[PASS]" in r.stdout, r.stdout
        assert "o jogo só vê o vpad" in r.stdout, (
            f"tudo medido e tudo fechado: a frase forte é honesta aqui.\n{r.stdout}"
        )
        assert "NÃO afirmo nada" not in r.stdout, r.stdout

    def test_a_mordida_o_pass_volta_a_contar_os_varridos(self, tmp_path: Path) -> None:
        """Arrancada a cura, o `pass` volta a afirmar sobre o não-medido."""
        alvo = "local medidos=$((TRES_SUP_CONTROLES - TRES_SUP_SEM_MAPA))"
        assert alvo in DOCTOR, "a linha da cura mudou de forma"
        arrancado = DOCTOR.replace(alvo, "local medidos=${TRES_SUP_CONTROLES}")
        r = _roda(tmp_path, self._cena_uma_fechada_uma_sem_mapa(), doctor=arrancado)
        assert "dos 2 controle(s)" in r.stdout, (
            "com a cura arrancada o `pass` devia voltar a contar os dois "
            f"varridos — se não voltou, esta régua não está medindo.\n{r.stdout}"
        )
