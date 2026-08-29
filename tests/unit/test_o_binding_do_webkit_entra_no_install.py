"""ROTA-WEBKIT — o binding do WebKit entra no `install.sh`, sem flag.

O pedido dela, em 29/08/2026, depois de instalar o `gir1.2-webkit2-4.1` à mão
para a medição: *"isso precisa estar dentro do nosso install na verdade"* …
*"de qualquer forma tá instalado à parte, mas ainda precisa estar no install é
regra do projeto original."*

A regra que ela cita é de 08/08/2026 — **toda cura entra no install, sem
flag**: nada à mão, nada opt-in.

O QUE ESTE ARQUIVO TRANCA:

1. a tabela `_pkg_nome` traduz `webkit2gtk` nas TRÊS famílias, com os nomes
   MEDIDOS (nenhum inferido — é o defeito que derrubou a família ``zypper`` em
   19/08/2026, ver `test_install_garante_deps_em_qualquer_familia.py`);
2. o censo `_DEPS_DE_SISTEMA` pede o binding como **importante**, e a linha de
   cima escreve que ela vira `obrigatoria` no dia em que a rota for adotada —
   a decisão é dela, e enquanto não é dela ninguém paga o peso obrigatório
   (25,2 MB baixados e ~93 MB em disco no apt; 140 MB no Arch — medido);
3. a checagem pergunta pelo EFEITO — o motor **carrega**? —, não pela versão
   do typelib. As duas metades da régua são medidas: presente é lido como
   presente, e ausente (nas DUAS formas de ausência) como ausente;
4. todo canônico do censo tem nome nas três famílias — buraco que nenhuma
   régua cobria: o portão que existia olha só os canônicos passados
   LITERALMENTE a `run_pkg`, e uma linha do censo com o nome trocado produziria
   um install que avisa "não tenho nome para isso" em TODA máquina.

AS MORDIDAS ESTÃO NO CABEÇALHO DE CADA TESTE.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
INSTALL_PATH = RAIZ / "install.sh"
INSTALL = INSTALL_PATH.read_text(encoding="utf-8")

#: O canônico do binding, e os nomes MEDIDOS em 29/08/2026 — um por família:
#:   apt     `gir1.2-webkit2-4.1` 2.52.3, instalado nesta bancada, com o
#:           `WebKit2-4.1.typelib` em `/usr/lib/*/girepository-1.0/`
#:   dnf     `webkit2gtk4.1` 2.52.5 (Fedora 43), cuja LISTA DE ARQUIVOS traz
#:           `/usr/lib/girepository-1.0/WebKit2-4.1.typelib` — o Fedora não
#:           separa o gir num pacote próprio, como já acontece com o `gtk3`
#:   pacman  `webkit2gtk-4.1` 2.52.6 (extra), lista de arquivos com
#:           `girepository-1.0/WebKit2-4.1.typelib`
CANONICO = "webkit2gtk"
NOMES_MEDIDOS = {
    "apt": "gir1.2-webkit2-4.1",
    "dnf": "webkit2gtk4.1",
    "pacman": "webkit2gtk-4.1",
}

FAMILIAS = tuple(NOMES_MEDIDOS)

#: Buracos ACEITOS no censo, com o motivo. Vazio hoje: toda linha de
#: `_DEPS_DE_SISTEMA` tem nome nas três famílias. (`bt-agent` não vive no censo
#: — é chamado à parte, e o buraco dele está declarado no outro arquivo.)
VAZIOS_ACEITOS_NO_CENSO: set[tuple[str, str]] = set()


# --------------------------------------------------------------------------
# Extração — rodar bash de VERDADE, como o resto das réguas do install
# --------------------------------------------------------------------------
def _extrai_funcao(nome: str) -> str:
    """``nome() { ... }`` até a primeira ``}`` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", INSTALL, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada em install.sh"
    fim = re.search(r"^\}\n", INSTALL[match.end():], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return INSTALL[match.start(): match.end() + fim.end()]


def _extrai_array(nome: str) -> str:
    """``nome=(`` até a primeira ``)`` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}=\(\n", INSTALL, re.MULTILINE)
    assert match is not None, f"array {nome} não encontrado em install.sh"
    fim = re.search(r"^\)\n", INSTALL[match.end():], re.MULTILINE)
    assert fim is not None, f"fim de {nome} não encontrado"
    return INSTALL[match.start(): match.end() + fim.end()]


def _entradas_do_censo() -> list[str]:
    """As linhas ``canônico|criticidade|checagem|razão`` do censo."""
    return re.findall(r'"([^"]*\|[^"]*)"', _extrai_array("_DEPS_DE_SISTEMA"))


def _linha_do_censo(canonico: str) -> str | None:
    for linha in _entradas_do_censo():
        if linha.split("|")[0] == canonico:
            return linha
    return None


def _roda(corpo: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ)
    ambiente.pop("HEFESTO_FAMILIA_PACOTES", None)
    ambiente.pop("HEFESTO_OS_RELEASE", None)
    ambiente.update(env or {})
    preludo = "\n".join(
        [
            "set -euo pipefail",
            _extrai_funcao("_familia_pacotes"),
            _extrai_funcao("_pkg_nome"),
        ]
    )
    return subprocess.run(
        [BASH, "-c", preludo + "\n" + corpo],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=120,
    )


def _checagem(venv_dir: Path, checagem: str) -> int:
    """Roda ``_dep_presente <checagem>`` com o ``VENV_DIR`` que se pedir."""
    script = "\n".join(
        [
            "set -euo pipefail",
            f'VENV_DIR="{venv_dir}"',
            '_VENV_PYTHON="python3"',
            _extrai_funcao("_dep_presente"),
            f'_dep_presente "{checagem}"',
        ]
    )
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=120
    ).returncode


# --------------------------------------------------------------------------
# 1. A tabela sabe o nome nas três famílias
# --------------------------------------------------------------------------
@pytest.mark.parametrize("familia", FAMILIAS)
def test_a_tabela_traduz_o_binding_em_cada_familia(familia: str) -> None:
    """A MORDIDA: arranque a linha ``webkit2gtk)`` de ``_pkg_nome`` e as três
    famílias devolvem vazio — o install passaria a avisar "não tenho nome para
    'webkit2gtk'" em toda máquina, que é falha silenciosa de outra distro.
    """
    proc = _roda(f"_pkg_nome {CANONICO} {familia}")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == NOMES_MEDIDOS[familia], (
        f"o nome do binding em {familia} mudou. Os três foram MEDIDOS em "
        "29/08/2026 (apt nesta bancada; dnf e pacman na lista de arquivos do "
        "pacote, conferindo o `WebKit2-4.1.typelib` lá dentro). Nome de pacote "
        "inferido é o que esta casa reprova desde a queda da família zypper"
    )


def test_a_serie_e_a_4_1_que_e_a_de_gtk3() -> None:
    """4.1 é a série de GTK 3; a 6.0 é GTK 4.

    O produto é GTK 3.0 — 60.862 linhas e um `main.glade` de 4.288. Um binding
    da série 6.0 não entra no mesmo processo, e instalá-lo seria pagar ~93 MB
    por uma biblioteca que a interface não consegue usar.

    A MORDIDA: troque um `4.1` por `6.0` em qualquer das três colunas e isto
    reprova.
    """
    for familia, nome in NOMES_MEDIDOS.items():
        assert "4.1" in nome or "4-1" in nome, (
            f"o nome em {familia} ({nome!r}) não é da série 4.1 — a 6.0 é GTK 4 "
            "e não entra no processo do produto, que é GTK 3.0"
        )


# --------------------------------------------------------------------------
# 2. O censo pede o binding, e a criticidade é a decisão dela
# --------------------------------------------------------------------------
def test_o_censo_pede_o_binding() -> None:
    """A MORDIDA: tire a linha ``"webkit2gtk|...`` do ``_DEPS_DE_SISTEMA`` e
    isto reprova. Sem ela o binding continua sendo instalação À MÃO — que é
    exatamente o que a regra de 08/08/2026 proíbe.
    """
    linha = _linha_do_censo(CANONICO)
    assert linha is not None, (
        "o binding do WebKit saiu do censo `_DEPS_DE_SISTEMA`: voltou a ser "
        "instalação à mão, contra a regra dela — toda cura entra no install, "
        "sem flag"
    )
    _, criticidade, checagem, razao = linha.split("|")
    assert checagem == "webkit", (
        f"a checagem do binding virou {checagem!r} — a régua tem de perguntar "
        "pelo EFEITO (o motor carrega?), como manda o desenho do `_dep_presente`"
    )
    assert razao.strip(), "a linha ficou sem o 'o que quebra sem ele'"
    assert criticidade == "importante", (
        "a criticidade do binding mudou. Ela é `importante` **de propósito**: a "
        "rota WebKit ainda não foi escolhida por ela, e enquanto não for, "
        "ninguém pode pagar ~93 MB em disco por uma decisão que não foi "
        "tomada. NO DIA EM QUE A ROTA FOR ADOTADA a linha vira `obrigatoria` — "
        "e este teste é o outro lugar que muda junto, de propósito: a troca "
        "tem de ser consciente"
    )


def test_a_troca_para_obrigatoria_esta_escrita_em_cima_da_linha() -> None:
    """A decisão adiada tem de estar ESCRITA onde ela será feita.

    Sem isso a próxima pessoa lê "importante" e conclui que o binding é
    acessório — quando a verdade é que ele vira obrigatório junto com a rota.

    A MORDIDA: apague o comentário acima da linha do censo e isto reprova.
    """
    linhas = INSTALL.splitlines()
    alvo = next(
        (i for i, x in enumerate(linhas) if x.strip().startswith(f'"{CANONICO}|')),
        None,
    )
    assert alvo is not None, "a linha do binding sumiu do censo"
    inicio = alvo
    while inicio > 0 and linhas[inicio - 1].strip().startswith("#"):
        inicio -= 1
    acima = "\n".join(linhas[inicio:alvo])
    assert "obrigatoria" in acima.lower(), (
        "o comentário acima da linha do binding não diz que ela vira "
        "`obrigatoria` no dia em que a rota WebKit for adotada. A decisão é "
        "dela e ainda não foi tomada: sem essa nota, a próxima pessoa não tem "
        "como saber que a troca é de UMA palavra, nesta linha"
    )


# --------------------------------------------------------------------------
# 3. A checagem pergunta pelo EFEITO — e as duas metades são medidas
# --------------------------------------------------------------------------
def _venv_falso(tmp_path: Path, stub: str, repositorio_stub: str = "") -> Path:
    """Um ``VENV_DIR`` cujo python enxerga um ``gi`` de mentira.

    É a única forma honesta de medir "máquina sem o binding" numa bancada que
    TEM o binding — mesma disciplina do `_path_sem` da régua irmã.
    """
    pacote = tmp_path / "stub" / "gi"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text(stub, encoding="utf-8")
    repositorio = pacote / "repository"
    repositorio.mkdir()
    (repositorio / "__init__.py").write_text(
        repositorio_stub
        or (
            "def __getattr__(nome):\n"
            "    raise ImportError('sem %s: a biblioteca não carrega' % nome)\n"
        ),
        encoding="utf-8",
    )
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin" / "python"
    python.write_text(
        "#!/usr/bin/env bash\n"
        f'exec env PYTHONPATH="{tmp_path / "stub"}" '
        f'"{RAIZ / ".venv" / "bin" / "python"}" "$@"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    return venv


STUB_SEM_TYPELIB = (
    "def require_version(espaco, serie):\n"
    "    raise ValueError('Namespace %s not available for version %s'\n"
    "                     % (espaco, serie))\n"
)

#: O CASO REAL, encenado — e a versão anterior NÃO o encenava.
#:
#: MEDIDO em 29/08/2026, remendando um typelib de verdade com um SONAME
#: inexistente: `require_version` PASSA, o `from gi.repository import WebKit2`
#: PASSA TAMBÉM (só um WARNING no stderr, que o `2>&1` da checagem come), e
#: quem estoura é a primeira CHAMADA:
#:   GError: Could not locate webkit_get_major_version: libNAOEXISTE-4.1.so.0
#:
#: A régua anterior usava um `gi` cujo `repository` levantava no acesso ao
#: atributo — logo o IMPORT quebrava. Ela provava que a checagem importa; NÃO
#: provava que importar detecta biblioteca ausente, que é o que o comentário do
#: install afirmava. *A régua confundia a PALAVRA com o ATO* — o padrão que esta
#: casa já nomeou, e que só se pega encenando o caso, não a sua descrição.
STUB_TYPELIB_SEM_BIBLIOTECA = (
    "def require_version(espaco, serie):\n"
    "    return None\n"
)

#: O `gi.repository` do caso real: o módulo EXISTE e importa; tocar um símbolo
#: é que estoura, como o librsvg faz quando o `.so` não está lá.
STUB_REPOSITORIO_QUE_IMPORTA_E_NAO_CARREGA = (
    "class _MotorSemBiblioteca:\n"
    "    @staticmethod\n"
    "    def get_major_version():\n"
    "        raise RuntimeError(\n"
    "            'Could not locate webkit_get_major_version: '\n"
    "            'libNAOEXISTE-4.1.so.0: cannot open shared object file')\n"
    "\n"
    "WebKit2 = _MotorSemBiblioteca()\n"
)


def test_maquina_sem_o_binding_le_como_ausente(tmp_path: Path) -> None:
    """A metade que TODA máquina consegue medir.

    A MORDIDA: troque o corpo da checagem por um `true` (ou por qualquer coisa
    que sempre sai 0) e isto reprova — a régua teria virado um sim para tudo, e
    o install nunca instalaria o binding em quem não o tem.
    """
    rc = _checagem(_venv_falso(tmp_path, STUB_SEM_TYPELIB), "webkit")
    assert rc != 0, (
        "um `gi` que NÃO tem o WebKit2 4.1 foi lido como PRESENTE: a régua "
        "parou de reprovar e o install deixaria de instalar o binding"
    )


def test_typelib_sem_a_biblioteca_tambem_e_ausente(tmp_path: Path) -> None:
    """O motivo de a checagem IMPORTAR, e não só pedir a versão.

    `gi.require_version` só olha o typelib. Se o typelib estiver lá e a
    biblioteca não carregar, a versão passa e o produto quebra depois — o verde
    mentiroso que o próprio `install.sh` nomeia no bloco do DKMS.

    A MORDIDA: apague o `from gi.repository import WebKit2` da checagem,
    deixando só o `require_version`, e isto reprova.
    """
    rc = _checagem(
        _venv_falso(
            tmp_path,
            STUB_TYPELIB_SEM_BIBLIOTECA,
            STUB_REPOSITORIO_QUE_IMPORTA_E_NAO_CARREGA,
        ),
        "webkit",
    )
    assert rc != 0, (
        "typelib presente e biblioteca que não carrega passou por PRESENTE — a "
        "checagem voltou a olhar só a versão, em vez de perguntar se o motor "
        "CARREGA"
    )


def test_binding_presente_le_como_presente() -> None:
    """A outra metade: a régua não pode virar um não para tudo.

    Sem isto, a checagem quebrada (um erro de digitação no nome do espaço, por
    exemplo) faria o install pedir sudo para instalar o que já está instalado —
    o defeito PATH-SEM-SBIN-01, de 19/08/2026, na íntegra.
    """
    venv = RAIZ / ".venv"
    if not (venv / "bin" / "python").exists():
        pytest.skip("sem venv nesta árvore")
    disponivel = subprocess.run(
        [
            str(venv / "bin" / "python"),
            "-c",
            "import gi;gi.require_version('WebKit2','4.1');"
            "from gi.repository import WebKit2",
        ],
        capture_output=True,
        timeout=120,
    ).returncode
    if disponivel != 0:
        pytest.skip(
            "esta máquina não tem o `gir1.2-webkit2-4.1` (ou o equivalente da "
            "família): a metade PRESENTE da régua não pode ser medida aqui"
        )
    assert _checagem(venv, "webkit") == 0, (
        "o binding está instalado nesta máquina e a checagem do install o leu "
        "como AUSENTE — o instalador pediria sudo para instalar o que já está lá"
    )


# --------------------------------------------------------------------------
# 4. O buraco que nenhuma régua cobria: canônico do censo sem nome
# --------------------------------------------------------------------------
def test_todo_canonico_do_censo_tem_nome_nas_tres_familias() -> None:
    """O portão que faltava.

    O `test_todo_canonico_usado_tem_linha_na_tabela` olha só os canônicos
    passados LITERALMENTE a `run_pkg`/`comando_manual_pkg`. Um canônico que
    vive SÓ no censo — como o do WebKit — passava por baixo: bastava um nome
    trocado na linha para o install avisar "não tenho nome para isso" em toda
    máquina, sem nenhuma régua reprovar.

    A MORDIDA: troque o `webkit2gtk` da linha do censo por `webkit2gtk-4.1`
    (que não existe na tabela) e isto reprova.
    """
    entradas = _entradas_do_censo()
    assert entradas, "o censo saiu vazio — a régua ficou cega"
    pedidos = [
        (linha.split("|")[0], familia)
        for linha in entradas
        for familia in FAMILIAS
        if (linha.split("|")[0], familia) not in VAZIOS_ACEITOS_NO_CENSO
    ]
    corpo = "\n".join(
        f'printf "%s|%s|%s\\n" "{c}" "{f}" "$(_pkg_nome {c} {f})"' for c, f in pedidos
    )
    proc = _roda(corpo)
    assert proc.returncode == 0, proc.stderr
    faltando = [
        linha for linha in proc.stdout.splitlines() if linha.strip().endswith("|")
    ]
    assert not faltando, (
        "canônico do censo sem nome de pacote: "
        + ", ".join(x.rstrip("|").replace("|", " em ") for x in faltando)
        + ". O install avisaria 'não tenho nome para isso' e a dependência "
        "nunca seria instalada"
    )
