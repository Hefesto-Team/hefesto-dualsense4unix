"""O-BROKER-ESQUECE-O-CONTROLE-QUE-SAIU-01, a metade do doctor: medir só o que é físico.

O `doctor.sh` das 03:44 e das 03:55 de 29/09, com os quatro DualSense no rádio
e os quatro pads `uhid`, disse::

    [WARN] o hide não fechou os nós de entrada: 4 de 5 controle(s) escondido(s)
    do jogo — o FÍSICO segue alcançável em 5 nó(s) de entrada (event260
    event261 event262 event263 js2) …

e mandou reiniciar o broker. Os cinco nós eram do pad do P2: o broker guardava
por NOME a lease do `hidraw6` do P1, que saiu, e o kernel deu o nome ao pad. O
doctor mediu certo o que recebeu; a cura da origem é do broker
(`test_o_broker_esquece_o_controle_que_saiu.py`). A metade daqui: o conjunto
medido é o hide ∩ o censo (o validador do broker, que separa o pad pelo
barramento e pela marca, nunca pelo nome), e o resto do hide sai numa linha
`info`.

O molde é o `_roda` da `test_esconde_so_o_hidraw_veredito_das_tres_superficies.py`
(bash, `/dev` e `/sys` de mentira, `getfacl` de mentira), copiado na forma e
com o pai HID de cada nó dito pela cena. As duas réguas leem a mesma função do
`doctor.sh`. Cada régua tem a mordida dela rodando aqui dentro.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
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

UHID = "sys/devices/virtual/misc/uhid"
#: A frase de 29/09, que acusava o pad de físico.
NAO_FECHOU = "o hide não fechou"
#: A linha que a cura acrescenta: o resto do hide, fora do veredito.
FORA = "fora deste veredito:"


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada no doctor.sh"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


def _morde(velho: str, novo: str) -> str:
    """O `doctor.sh` com UMA troca, que tem de existir uma vez só."""
    assert DOCTOR.count(velho) == 1, f"a linha da cura mudou de forma: {velho!r}"
    return DOCTOR.replace(velho, novo)


# ---------------------------------------------------------------------------
# A cena: um /dev e um /sys de mentira, com o pai HID de cada nome
# ---------------------------------------------------------------------------


@dataclass
class Entrada:
    """Um nó de `/dev/input` do aparelho: nome, modo e se tem ACL nomeada."""

    base: str
    modo: int
    acl: bool = False


@dataclass
class Aparelho:
    """O pai HID atrás de um `hidrawN` e os nós de entrada dele, por input."""

    pai: str
    inputs: list[list[Entrada]]


def _monta_cena(raiz: Path, aparelhos: dict[str, Aparelho]) -> None:
    (raiz / "dev" / "input").mkdir(parents=True, exist_ok=True)
    (raiz / "sys" / "class" / "hidraw").mkdir(parents=True, exist_ok=True)
    for hidraw, aparelho in aparelhos.items():
        classe = raiz / "sys" / "class" / "hidraw" / hidraw
        classe.mkdir(parents=True, exist_ok=True)
        pai = raiz / aparelho.pai
        pai.mkdir(parents=True, exist_ok=True)
        (classe / "device").symlink_to(pai)
        for i, entradas in enumerate(aparelho.inputs):
            pasta = pai / "input" / f"input{hidraw.removeprefix('hidraw')}{i}"
            pasta.mkdir(parents=True, exist_ok=True)
            for entrada in entradas:
                (pasta / entrada.base).write_text("")
                no = raiz / "dev" / "input" / entrada.base
                no.write_text("")
                no.chmod(entrada.modo)


def _stub_getfacl(raiz: Path) -> Path:
    """`getfacl` de mentira: `user:<eu>:rw-` só para quem está em COM_ACL."""
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
    aparelhos: dict[str, Aparelho],
    *,
    hide: list[str],
    censo: list[str],
    doctor: str | None = None,
) -> str:
    """Extrai as funções do doctor, reancora os caminhos na cena e roda o veredito.

    `hide` é o `hidden` do `status` do broker (a ordem dele, que é a de
    `sorted`), e o `hidden_count` é o tamanho dele, como o
    `check_hidraw_broker` repassa. `censo` é o `physical_nodes_exposure`.
    """
    fonte = DOCTOR if doctor is None else doctor
    corpo = "\n".join(_extrai_funcao_bash(fonte, nome) for nome in FUNCOES)
    corpo = corpo.replace("/sys/class/hidraw/", f"{raiz}/sys/class/hidraw/")
    corpo = corpo.replace("/dev/input/${base}", f"{raiz}/dev/input/${{base}}")
    _monta_cena(raiz, aparelhos)
    com_acl = " ".join(
        e.base for a in aparelhos.values() for entradas in a.inputs for e in entradas if e.acl
    )
    nos = [f"/dev/{h}" for h in hide]
    script = raiz / "cena.sh"
    script.write_text(
        # `set -u`, como o doctor roda; o gesto é global do doctor.sh.
        "set -u\n"
        'GESTO_DE_REINICIAR_O_BROKER="(o gesto)"\n'
        'pass() { echo "[PASS] $*"; }\n'
        'warn() { echo "[WARN] $*"; }\n'
        'fail() { echo "[FAIL] $*"; }\n'
        'info() { echo "[INFO] $*"; }\n'
        + corpo
        + f'\n_veredito_do_hide "{len(nos)}" "1" "False"'
        + ' "{}"'.format(" ".join(f"/dev/{h}" for h in censo))
        + "".join(f' "{no}"' for no in nos)
        + "\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PATH"] = f"{_stub_getfacl(raiz)}{os.pathsep}{env['PATH']}"
    env["COM_ACL"] = com_acl
    r = subprocess.run(
        [BASH, str(script)], capture_output=True, text=True, check=False, env=env
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _fisico_fechado(hidraw: str, seq: int) -> Aparelho:
    """Um DualSense físico pelo rádio, com os nós que o broker fechou."""
    n = hidraw.removeprefix("hidraw")
    return Aparelho(
        pai=f"{UHID}/0005:054C:0CE6.{seq:04X}",
        inputs=[
            [Entrada(f"event{n}0", 0o600), Entrada(f"js{n}0", 0o600)],
            [Entrada(f"event{n}1", 0o600), Entrada(f"js{n}1", 0o000)],
            [Entrada(f"event{n}2", 0o600)],
            [Entrada(f"event{n}3", 0o600)],
        ],
    )


def _o_pad_do_p2() -> Aparelho:
    """O `hidraw6` às 03:55: o pad do P2, com os nós abertos para o jogo."""
    return Aparelho(
        pai=f"{UHID}/0003:054C:0DF2.0030",
        inputs=[
            [Entrada("event260", 0o660, acl=True), Entrada("js2", 0o664, acl=True)],
            [Entrada("event261", 0o660, acl=True), Entrada("js7", 0o000)],
            [Entrada("event262", 0o660, acl=True)],
            [Entrada("event263", 0o660, acl=True)],
        ],
    )


def _um_teclado() -> Aparelho:
    """Um teclado pelo rádio que herdou o nome (o modo Xbox não tem hidraw)."""
    return Aparelho(
        pai=f"{UHID}/0005:3554:FA09.0031",
        inputs=[[Entrada("event270", 0o660, acl=True)]],
    )


OS_QUATRO = ["hidraw10", "hidraw5", "hidraw7", "hidraw9"]
#: O `hidden` do `status` às 03:55, na ordem do `sorted` do broker.
O_HIDE_DAS_0355 = ["hidraw10", "hidraw5", "hidraw6", "hidraw7", "hidraw9"]


def _a_cena_das_0355(herdeiro: Aparelho | None = None) -> dict[str, Aparelho]:
    aparelhos = {h: _fisico_fechado(h, 0x10 + i) for i, h in enumerate(OS_QUATRO)}
    aparelhos["hidraw6"] = herdeiro if herdeiro is not None else _o_pad_do_p2()
    return aparelhos


def _linhas(saida: str, prefixo: str) -> list[str]:
    return [ln for ln in saida.splitlines() if ln.startswith(prefixo)]


# ---------------------------------------------------------------------------
# 1. A cena das 03:55
# ---------------------------------------------------------------------------


class TestACenaDas0355:
    def test_pass_com_quatro_e_a_linha_info_nomeia_o_hidraw6(self, tmp_path: Path) -> None:
        saida = _roda(tmp_path, _a_cena_das_0355(), hide=O_HIDE_DAS_0355, censo=OS_QUATRO)

        assert NAO_FECHOU not in saida, saida
        assert _linhas(saida, "[WARN]") == [], saida
        passes = _linhas(saida, "[PASS]")
        assert len(passes) == 1 and "escondendo 4 nó(s)" in passes[0], saida
        infos = [ln for ln in _linhas(saida, "[INFO]") if FORA in ln]
        assert len(infos) == 1 and "/dev/hidraw6" in infos[0], saida
        for outro in OS_QUATRO:
            assert f"/dev/{outro}" not in infos[0], saida
        for no in ("event260", "event261", "event262", "event263", "js2"):
            assert no not in saida, f"o nó {no} é do pad, e o jogo tem de vê-lo:\n{saida}"

    def test_a_mordida_o_hide_inteiro_volta_a_ser_medido(self, tmp_path: Path) -> None:
        """Sem o `set --` do conjunto medido, volta o texto de 29/09."""
        arrancado = _morde('        set -- "${no_censo[@]}"\n', "")
        saida = _roda(
            tmp_path, _a_cena_das_0355(), hide=O_HIDE_DAS_0355, censo=OS_QUATRO, doctor=arrancado
        )
        assert NAO_FECHOU in saida, saida
        assert "4 de 5" in saida, saida
        assert "(event260 event261 event262 event263 js2)" in saida, saida


# ---------------------------------------------------------------------------
# 2. Um teclado com o nome
# ---------------------------------------------------------------------------


#: A mordida da 2: separar pela FORMA do pad (`0003` sob o `uhid`), no bash,
#: em vez de perguntar ao censo.
_PELO_CENSO = (
    "            for _do_censo in ${censo}; do\n"
    '                [[ "${_do_censo}" == "${_escondido}" ]] && { _visto=1; break; }\n'
    "            done\n"
)
_PELA_FORMA_DO_PAD = (
    '            [[ "$(readlink -f "/sys/class/hidraw/${_escondido##*/}/device")"'
    " == */misc/uhid/0003:* ]] || _visto=1\n"
)


class TestUmTecladoComONome:
    def test_o_teclado_fica_fora_do_veredito(self, tmp_path: Path) -> None:
        saida = _roda(
            tmp_path, _a_cena_das_0355(_um_teclado()), hide=O_HIDE_DAS_0355, censo=OS_QUATRO
        )

        assert _linhas(saida, "[WARN]") == [], saida
        assert "escondendo 4 nó(s)" in saida, saida
        assert any(FORA in ln and "/dev/hidraw6" in ln for ln in _linhas(saida, "[INFO]"))
        assert "event270" not in saida, saida

    def test_a_mordida_pela_forma_do_pad_o_teclado_vira_fisico(self, tmp_path: Path) -> None:
        arrancado = _morde(_PELO_CENSO, _PELA_FORMA_DO_PAD)
        pad = _roda(
            tmp_path / "pad", _a_cena_das_0355(), hide=O_HIDE_DAS_0355, censo=OS_QUATRO,
            doctor=arrancado,
        )
        assert _linhas(pad, "[WARN]") == [], "a forma do pad separa o pad, e só ele"
        teclado = _roda(
            tmp_path / "teclado", _a_cena_das_0355(_um_teclado()), hide=O_HIDE_DAS_0355,
            censo=OS_QUATRO, doctor=arrancado,
        )
        assert NAO_FECHOU in teclado and "event270" in teclado, teclado


# ---------------------------------------------------------------------------
# 3. O defeito de verdade continua pego
# ---------------------------------------------------------------------------


def _fisico_com_o_gamepad_aberto(hidraw: str, seq: int) -> Aparelho:
    aparelho = _fisico_fechado(hidraw, seq)
    n = hidraw.removeprefix("hidraw")
    aparelho.inputs[0][0] = Entrada(f"event{n}0", 0o660, acl=True)
    return aparelho


class TestODefeitoDeVerdadeContinua:
    def test_o_fisico_do_censo_com_o_event_aberto_segue_no_warn(self, tmp_path: Path) -> None:
        """O defeito da HIDE-SO-O-HIDRAW-02: o físico escondido com um nó de
        entrada aberto está no hide e no censo, e segue acusado com a frase e
        o gesto de hoje."""
        aparelhos = {
            "hidraw5": _fisico_com_o_gamepad_aberto("hidraw5", 0x11),
            "hidraw7": _fisico_fechado("hidraw7", 0x12),
        }
        dois = ["hidraw5", "hidraw7"]
        saida = _roda(tmp_path, aparelhos, hide=dois, censo=dois)

        avisos = _linhas(saida, "[WARN]")
        assert len(avisos) == 1 and NAO_FECHOU in avisos[0], saida
        assert "1 de 2" in avisos[0] and "(event50)" in avisos[0], saida
        assert _linhas(saida, "[PASS]") == [], saida

    def test_a_mordida_medir_o_de_fora_em_vez_do_censo(self, tmp_path: Path) -> None:
        arrancado = _morde(
            '            if [[ "${_visto}" -eq 1 ]]; then\n                no_censo+=',
            '            if [[ "${_visto}" -eq 0 ]]; then\n                no_censo+=',
        )
        aparelhos = {
            "hidraw5": _fisico_com_o_gamepad_aberto("hidraw5", 0x11),
            "hidraw7": _fisico_fechado("hidraw7", 0x12),
        }
        saida = _roda(
            tmp_path, aparelhos, hide=["hidraw5", "hidraw7"], censo=["hidraw5", "hidraw7"],
            doctor=arrancado,
        )
        assert _linhas(saida, "[WARN]") == [], saida


# ---------------------------------------------------------------------------
# 4. Censo vazio segue «não sei»
# ---------------------------------------------------------------------------


class TestCensoVazioSegueNaoSei:
    def test_censo_vazio_mede_o_hide_inteiro_como_hoje(self, tmp_path: Path) -> None:
        """Sem o validador alcançável o doctor não separa pad de físico: mede o
        hide inteiro, e o `hidraw6` com os nós abertos segue no `warn`. Só a
        cura do broker cobre este caso."""
        saida = _roda(tmp_path, _a_cena_das_0355(), hide=O_HIDE_DAS_0355, censo=[])

        assert NAO_FECHOU in saida and "4 de 5" in saida, saida
        assert FORA not in saida, saida

    def test_a_mordida_a_intersecao_com_o_censo_vazio(self, tmp_path: Path) -> None:
        """Vazio não é tudo fechado: a interseção com o censo vazio sai no
        `pass` de «nada medido»."""
        arrancado = _morde('    if [[ -n "${censo}" ]]; then\n', "    if true; then\n")
        saida = _roda(
            tmp_path, _a_cena_das_0355(), hide=O_HIDE_DAS_0355, censo=[], doctor=arrancado
        )
        assert NAO_FECHOU not in saida, saida
        assert _linhas(saida, "[PASS]"), saida


# ---------------------------------------------------------------------------
# 5. As contagens
# ---------------------------------------------------------------------------


class TestAsContagens:
    def test_o_de_m_do_warn_e_o_conjunto_medido(self, tmp_path: Path) -> None:
        """A cena das 03:55 com um quinto físico aberto: «4 de 5», com cinco
        físicos no censo e o `hidraw6` fora."""
        aparelhos = _a_cena_das_0355()
        aparelhos["hidraw12"] = _fisico_com_o_gamepad_aberto("hidraw12", 0x20)
        hide = sorted([*O_HIDE_DAS_0355, "hidraw12"])
        censo = sorted([*OS_QUATRO, "hidraw12"])
        saida = _roda(tmp_path, aparelhos, hide=hide, censo=censo)

        avisos = _linhas(saida, "[WARN]")
        assert len(avisos) == 1 and "4 de 5" in avisos[0], saida
        assert "(event120)" in avisos[0], saida
        assert "event260" not in saida, saida
        assert any(FORA in ln and "/dev/hidraw6" in ln for ln in _linhas(saida, "[INFO]"))

    def test_a_mordida_o_pass_volta_a_contar_o_hidden_count(self, tmp_path: Path) -> None:
        arrancado = DOCTOR.replace(
            'pass "broker escondendo ${contados}', 'pass "broker escondendo ${hidden_count}'
        )
        assert arrancado != DOCTOR, "a contagem do pass mudou de forma"
        saida = _roda(
            tmp_path, _a_cena_das_0355(), hide=O_HIDE_DAS_0355, censo=OS_QUATRO, doctor=arrancado
        )
        assert "escondendo 5 nó(s)" in saida, saida


# ---------------------------------------------------------------------------
# O que as réguas de hoje procuram, e a fala de quem usa
# ---------------------------------------------------------------------------


class TestOQueAsReguasDeHojeProcuram:
    def test_as_duas_linhas_e_a_linha_da_cura_ficam_byte_a_byte(self) -> None:
        """A mordida da `test_esconde_so_o_hidraw_veredito_das_tres_superficies`
        troca o laço do censo e a chamada da medição por texto; a da
        `test_hide_so_o_hidraw_02_o_doctor_mede_a_cura` procura o gesto no
        `warn`. Uma quinta função bash não chegaria à cena delas, e por isso a
        interseção mora dentro do `_veredito_do_hide`."""
        corpo = _extrai_funcao_bash(DOCTOR, "_veredito_do_hide")
        assert corpo.count("    for _fisico in ${censo}; do\n") == 1
        assert corpo.count('    _tres_superficies_medir "$@"\n') == 1
        assert "${GESTO_DE_REINICIAR_O_BROKER}" in corpo

    def test_a_linha_nova_nao_tem_id_nem_vira_aviso(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "_veredito_do_hide")
        linhas = [ln.strip() for ln in corpo.splitlines() if FORA in ln]
        assert len(linhas) == 1, linhas
        assert "&& info " in linhas[0], linhas[0]
        criterio_5 = r"\b[A-Z]{2,}(-[A-Z0-9]+)*-[0-9]{2}\b|\bcasa\b|Onda [A-Z]\b"
        assert not re.search(criterio_5, linhas[0]), linhas[0]
