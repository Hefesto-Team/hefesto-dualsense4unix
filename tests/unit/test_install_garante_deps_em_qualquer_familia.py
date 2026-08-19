"""DEPS-UNIVERSAIS-01 — o install garante as dependências em QUALQUER família.

O pedido dela, em 19/08/2026, em duas frases: *"corrige nosso install pra
instalar isso tudo aí"* e *"qualquer install. inclusive o do andre ou de
qualquer outro user"*. A segunda é a que manda no desenho: a cura não pode ser
para a máquina dela.

O DEFEITO, medido antes desta leva:

    grep -c "libhidapi\\|librsvg" install.sh   ->  0   (as duas OBRIGATÓRIAS)
    run_apt() { ... sudo apt-get install ... } ->  a ÚNICA porta

Numa máquina limpa de Fedora ou de Arch o instalador nativo terminava
"ok" sem a libhidapi — a biblioteca que o backend do controle abre por dlopen —
e sem o loader SVG do gdk-pixbuf, sem o qual o ícone da bandeja some e todo
glifo da interface cai junto. É o verde mentiroso que o próprio ``install.sh``
já nomeia por escrito no bloco do DKMS.

O que este arquivo tranca, em quatro frentes:

1. a família é descoberta pelo ``/etc/os-release`` — Debian, Fedora e Arch —
   e cai no PATH só quando o os-release não conclui;
2. UMA tabela traduz o nome canônico para cada família, e o despacho instala
   com o gerenciador certo (o valor da cura está justamente na distro que
   ninguém desta casa roda à mão);
3. as duas OBRIGATÓRIAS são FATAIS quando continuam faltando depois da
   tentativa — reconferidas pelo EFEITO, para que nome errado na tabela não
   passe por instalado;
4. numa família SEM tratamento o install NÃO aborta e NÃO mente: diz o que
   falta, com o nome de referência, e segue.

PROVA DE QUE MORDE: ver o cabeçalho de cada teste e o relatório da leva.
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

#: As três famílias que a tabela trata — e são três, não quatro, desde
#: 19/08/2026: o ``zypper`` foi retirado porque **todos** os seus nomes de
#: pacote eram inferidos e nenhum smoke os conferia (ver a nota datada no
#: cabeçalho da tabela, em ``install.sh``). Cada nome que sobrou tem
#: empacotamento desta casa ou contêiner do ``smoke-multi-distro`` por trás.
FAMILIAS = ("apt", "dnf", "pacman")

#: Buracos ACEITOS na tabela, com o motivo. Não é folga: é o registro de que a
#: ausência foi decidida. ``bluez-tools`` não existe com esse nome no Fedora —
#: nesse caso o ``run_pkg`` diz "não tenho nome para isso aqui" em vez de
#: instalar outra coisa.
VAZIOS_ACEITOS = {
    ("bt-agent", "dnf"),
}


# --------------------------------------------------------------------------
# Extração — executar bash de VERDADE, como test_install_dkms_default.py
# --------------------------------------------------------------------------

def _linha_do_install(agulha: str) -> str | None:
    """A primeira linha do `install.sh` que contém `agulha`."""
    for linha in (RAIZ / "install.sh").read_text(encoding="utf-8").splitlines():
        if agulha in linha and not linha.lstrip().startswith("#"):
            return linha
    return None


def _path_sem(binarios: list[str]) -> str:
    """Um PATH com o essencial, mas SEM os binários pedidos.

    Monta um diretório de links: é a única forma honesta de medir "máquina que
    não tem X" numa bancada que tem X.
    """
    import tempfile

    alvo = Path(tempfile.mkdtemp(prefix="hefesto-path-magro-"))
    for nome in ("bash", "sh", "awk", "sed", "grep", "cat", "printf", "uname"):
        origem = shutil.which(nome)
        if origem and nome not in binarios:
            (alvo / nome).symlink_to(origem)
    return str(alvo)


def _entradas_de_deps() -> list[str]:
    """As linhas da tabela `_DEPS_DE_SISTEMA` do `install.sh`."""
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    m = re.search(r"_DEPS_DE_SISTEMA=\((.*?)\n\)", texto, re.S)
    if m is None:
        return []
    return re.findall(r'"([^"]*\|[^"]*)"', m.group(1))


def _extrai_funcao(nome: str) -> str:
    """``nome() { ... }`` até a primeira ``}`` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", INSTALL, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada em install.sh"
    fim = re.search(r"^\}\n", INSTALL[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return INSTALL[match.start() : match.end() + fim.end()]


def _extrai_array(nome: str) -> str:
    """``nome=(`` até a primeira ``)`` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}=\(\n", INSTALL, re.MULTILINE)
    assert match is not None, f"array {nome} não encontrado em install.sh"
    fim = re.search(r"^\)\n", INSTALL[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome} não encontrado"
    return INSTALL[match.start() : match.end() + fim.end()]


def _extrai_linha(padrao: str) -> str:
    match = re.search(padrao, INSTALL, re.MULTILINE)
    assert match is not None, f"linha ausente em install.sh: {padrao}"
    return match.group(0)


PRELUDO = "\n".join(
    [
        "set -euo pipefail",
        'warn() { printf "aviso: %s\\n" "$*"; }',
        'die()  { printf "ERRO: %s\\n" "$*" >&2; exit 42; }',
        'ask_yn() { REPLY="${3:-y}"; }',
        "AUTO_YES=1",
        _extrai_linha(r"^_OS_RELEASE=.*$"),
        _extrai_funcao("_familia_pacotes"),
        _extrai_funcao("_pkg_nome"),
        _extrai_funcao("_run_pkg_quieto"),
        _extrai_funcao("run_apt"),
        _extrai_funcao("run_pkg"),
        _extrai_funcao("comando_manual_pkg"),
    ]
)

PRELUDO_DRIVER = "\n".join(
    [
        PRELUDO,
        'VENV_DIR="/naoexiste"',
        '_VENV_PYTHON="python3"',
        _extrai_array("_DEPS_DE_SISTEMA"),
        _extrai_funcao("_dep_presente"),
        _extrai_funcao("_garantir_deps_de_sistema"),
    ]
)


def _roda(corpo: str, *, preludo: str = PRELUDO, env: dict[str, str] | None = None):
    ambiente = dict(os.environ)
    ambiente.pop("HEFESTO_FAMILIA_PACOTES", None)
    ambiente.pop("HEFESTO_OS_RELEASE", None)
    ambiente.update(env or {})
    return subprocess.run(
        [BASH, "-c", preludo + "\n" + corpo],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=60,
    )


def _bin_falso(tmp_path: Path) -> Path:
    """Um ``sudo`` que só ANOTA o que teria rodado. Nada é instalado."""
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    sudo = binario / "sudo"
    sudo.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "${LOG_PKG}"\nexit 0\n',
        encoding="utf-8",
    )
    sudo.chmod(0o755)
    return binario


# --------------------------------------------------------------------------
# 1. A família sai do /etc/os-release
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("os_release", "esperado"),
    [
        ('ID=ubuntu\nID_LIKE=debian\n', "apt"),
        ('ID=debian\n', "apt"),
        ('ID=pop\nID_LIKE="ubuntu debian"\n', "apt"),  # a máquina do André
        ('ID=fedora\n', "dnf"),
        ('ID=nobara\nID_LIKE="fedora"\n', "dnf"),
        ('ID=arch\n', "pacman"),
        ('ID=cachyos\nID_LIKE="arch"\n', "pacman"),
    ],
)
def test_familia_sai_do_os_release(tmp_path: Path, os_release: str, esperado: str) -> None:
    """A régua não pode depender do PATH desta máquina.

    Esta bancada tem apt-get. Se a descoberta olhasse só para o PATH, TODA
    distro daria "apt" aqui e o portão passaria por vacuidade — que é o pior
    estado possível.
    """
    arquivo = tmp_path / "os-release"
    arquivo.write_text(os_release, encoding="utf-8")
    proc = _roda("_familia_pacotes", env={"HEFESTO_OS_RELEASE": str(arquivo)})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == esperado


def _path_magro(tmp_path: Path) -> Path:
    """Um PATH com o mínimo para o script rodar e NENHUM gerenciador de pacotes.

    Sem isto a régua passa por vacuidade: esta bancada tem ``apt-get``, então
    o passo de PATH do ``_familia_pacotes`` responderia "apt" para qualquer
    ``/etc/os-release``.
    """
    magro = tmp_path / "magro"
    magro.mkdir(exist_ok=True)
    for utilitario in ("sed", "tr", "head", "cat", "rm", "mktemp", "grep"):
        alvo = shutil.which(utilitario)
        if alvo:
            (magro / utilitario).symlink_to(alvo)
    return magro


def test_familia_desconhecida_nao_inventa(tmp_path: Path) -> None:
    """NixOS com PATH sem gerenciador nenhum: a resposta honesta é "nenhum"."""
    arquivo = tmp_path / "os-release"
    arquivo.write_text('ID=nixos\n', encoding="utf-8")
    proc = _roda(
        "_familia_pacotes",
        env={"HEFESTO_OS_RELEASE": str(arquivo), "PATH": str(_path_magro(tmp_path))},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "nenhum"


@pytest.mark.parametrize(
    "os_release",
    [
        'ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n',
        'ID="opensuse-leap"\nID_LIKE="suse opensuse"\n',
        'ID=sles\n',
    ],
)
def test_opensuse_nao_e_prometido(tmp_path: Path, os_release: str) -> None:
    """19/08/2026 — decisão dela: **não prometer openSUSE**.

    A leva da manhã tinha acrescentado a família ``zypper`` com nomes de pacote
    INFERIDOS em 100% das linhas, sem um único smoke que os conferisse — o
    repositório não tem uma linha sequer sobre zypper. Afirmação forte sem
    teste que a sustente é o que esta casa reprova por portão.

    A resposta honesta, então, é a mesma do NixOS: "nenhum". Quem está lá cai
    no caminho de família sem tratamento, que já existe, DIZ o que falta e
    SEGUE — ver ``test_familia_sem_tratamento_nao_aborta_e_diz_o_que_falta``.

    O QUE DERRUBA ESTE TESTE (e deve derrubá-lo): um contêiner openSUSE na
    matriz ``smoke-multi-distro`` do CI conferindo os nomes. Aí a coluna volta
    medida, e esta régua é reescrita junto.
    """
    arquivo = tmp_path / "os-release"
    arquivo.write_text(os_release, encoding="utf-8")
    proc = _roda(
        "_familia_pacotes",
        env={"HEFESTO_OS_RELEASE": str(arquivo), "PATH": str(_path_magro(tmp_path))},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "nenhum", (
        "o install voltou a prometer uma família de pacotes para o openSUSE. "
        "Os nomes de pacote do zypper nunca foram medidos por esta casa: só "
        "volte a prometê-los junto com um contêiner openSUSE no "
        "`smoke-multi-distro`"
    )


def test_nenhum_gerenciador_sem_medicao_no_codigo() -> None:
    """O portão do inferido: gerenciador sem smoke não entra pela porta dos fundos.

    Olha só as linhas EXECUTÁVEIS — a nota datada do ``install.sh`` cita o
    zypper pelo nome de propósito, e apagar a nota seria apagar a decisão.
    """
    codigo = "\n".join(
        linha for linha in INSTALL.splitlines() if not linha.strip().startswith("#")
    )
    for gerenciador in ("zypper", "emerge", "xbps-install", "eopkg", "apk"):
        assert gerenciador not in codigo, (
            f"'{gerenciador}' apareceu no código do install.sh sem contêiner "
            "próprio no `smoke-multi-distro` do CI: os nomes de pacote seriam "
            "inferidos, e prometer distro sem medição é o que esta casa reprova"
        )


# --------------------------------------------------------------------------
# 2. O despacho instala com o gerenciador certo, com o nome certo
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("familia", "comando"),
    [
        ("apt", "apt-get install -y -qq libhidapi-hidraw0 librsvg2-common"),
        ("dnf", "dnf install -y hidapi librsvg2"),
        ("pacman", "pacman -S --noconfirm --needed hidapi librsvg"),
    ],
)
def test_run_pkg_despacha_por_familia(tmp_path: Path, familia: str, comando: str) -> None:
    """As duas OBRIGATÓRIAS, nas três famílias medidas, sem tocar no sistema.

    Este é o teste que morde se alguém arrancar uma linha da tabela: sem o
    nome, o ``run_pkg`` recusa e o comando não sai.
    """
    log = tmp_path / "log"
    binario = _bin_falso(tmp_path)
    proc = _roda(
        "run_pkg hidapi svg-loader",
        env={
            "HEFESTO_FAMILIA_PACOTES": familia,
            "LOG_PKG": str(log),
            "PATH": f"{binario}:{os.environ['PATH']}",
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert log.read_text(encoding="utf-8").strip() == comando


def test_run_pkg_sem_nome_recusa_e_nao_instala_outra_coisa(tmp_path: Path) -> None:
    """``bluez-tools`` não existe em Fedora — e a recusa é o comportamento."""
    log = tmp_path / "log"
    binario = _bin_falso(tmp_path)
    proc = _roda(
        "run_pkg bt-agent || printf 'RECUSOU\\n'",
        env={
            "HEFESTO_FAMILIA_PACOTES": "dnf",
            "LOG_PKG": str(log),
            "PATH": f"{binario}:{os.environ['PATH']}",
        },
    )
    assert "RECUSOU" in proc.stdout
    assert "bt-agent" in proc.stdout
    assert not log.exists(), "instalou alguma coisa sem saber o nome"


def test_run_apt_continua_sendo_o_braco_apt(tmp_path: Path) -> None:
    """``run_apt`` não virou fachada morta: é ele que roda no apt.

    Há chamadores e documentos desta casa que o citam, e é ele que guarda a
    disciplina de saída quieta. Se alguém o cortar do caminho do ``run_pkg``,
    esta régua reprova.
    """
    log = tmp_path / "log"
    binario = _bin_falso(tmp_path)
    proc = _roda(
        'run_apt() { printf "FACHADA %s\\n" "$*"; }\nrun_pkg hidapi',
        env={
            "HEFESTO_FAMILIA_PACOTES": "apt",
            "LOG_PKG": str(log),
            "PATH": f"{binario}:{os.environ['PATH']}",
        },
    )
    assert "FACHADA libhidapi-hidraw0" in proc.stdout


# --------------------------------------------------------------------------
# 3. A tabela cobre o que o install pede
# --------------------------------------------------------------------------
def _canonicos_usados() -> set[str]:
    """Nomes canônicos passados literalmente a ``run_pkg``/``comando_manual_pkg``."""
    usados: set[str] = set()
    padrao = re.compile(r"\b(?:run_pkg|comando_manual_pkg)((?:\s+[a-z0-9-]+)+)")
    for corpo in padrao.findall(INSTALL):
        # O `2` de `run_pkg wlrctl 2>/dev/null` não é nome de pacote.
        usados.update(
            token for token in corpo.split() if re.fullmatch(r"[a-z][a-z0-9-]+", token)
        )
    return usados


def test_todo_canonico_usado_tem_linha_na_tabela(tmp_path: Path) -> None:
    """Portão contra o canônico órfão.

    Escrever ``run_pkg foo`` sem linha na tabela produz um install que avisa
    "não tenho nome para 'foo'" em TODA máquina — falha silenciosa que só
    aparece na distro de outra pessoa.
    """
    usados = _canonicos_usados()
    assert usados, "nenhuma chamada de run_pkg encontrada — a régua ficou cega"
    faltando: list[str] = []
    for canonico in sorted(usados):
        for familia in FAMILIAS:
            if (canonico, familia) in VAZIOS_ACEITOS:
                continue
            proc = _roda(f'_pkg_nome {canonico} {familia}')
            if not proc.stdout.strip():
                faltando.append(f"{canonico} em {familia}")
    assert not faltando, "sem nome de pacote: " + ", ".join(faltando)


def test_as_duas_obrigatorias_estao_no_censo_e_sao_fatais() -> None:
    """libhidapi e o loader SVG são OBRIGATÓRIAS — não "recomendadas"."""
    tabela = _extrai_array("_DEPS_DE_SISTEMA")
    for canonico in ("hidapi", "svg-loader"):
        linha = [x for x in tabela.splitlines() if x.strip().startswith(f'"{canonico}|')]
        assert linha, f"{canonico} saiu do censo de dependências de sistema"
        assert "|obrigatoria|" in linha[0], f"{canonico} deixou de ser obrigatória"


def test_o_passo_e_chamado_no_fluxo_native() -> None:
    """Função definida e nunca chamada é a cura escrita que ninguém ligou."""
    chamadas = [
        linha
        for linha in INSTALL.splitlines()
        if linha.strip() == "_garantir_deps_de_sistema"
    ]
    assert chamadas, "_garantir_deps_de_sistema está definida mas nunca é chamada"


# --------------------------------------------------------------------------
# 4. Criticidade: obrigatória morre, importante avisa, desconhecida não aborta
# --------------------------------------------------------------------------
def test_obrigatoria_que_continua_faltando_e_fatal(tmp_path: Path) -> None:
    """A reconferência pelo EFEITO é o que impede o verde mentiroso.

    Aqui o gerenciador "instala" com sucesso (sai 0) e a biblioteca continua
    ausente — exatamente o que acontece com nome de pacote errado. O install
    tem de MORRER, não celebrar.
    """
    proc = _roda(
        "\n".join(
            [
                "_dep_presente() { return 1; }",
                "run_pkg() { return 0; }",
                "_garantir_deps_de_sistema",
            ]
        ),
        preludo=PRELUDO_DRIVER,
        env={"HEFESTO_FAMILIA_PACOTES": "dnf"},
    )
    assert proc.returncode == 42, proc.stdout + proc.stderr
    assert "hidapi" in proc.stderr
    assert "svg-loader" in proc.stderr


def test_importante_ausente_avisa_e_segue(tmp_path: Path) -> None:
    """Sem `lsusb` o diagnóstico perde uma leitura; o install não morre."""
    proc = _roda(
        "\n".join(
            [
                '_dep_presente() { [[ "$1" == "cmd:lsusb" ]] && return 1; return 0; }',
                "run_pkg() { return 1; }",
                "_garantir_deps_de_sistema",
                'printf "SOBREVIVEU\\n"',
            ]
        ),
        preludo=PRELUDO_DRIVER,
        env={"HEFESTO_FAMILIA_PACOTES": "pacman"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SOBREVIVEU" in proc.stdout
    assert "usbutils" in proc.stdout


def test_familia_sem_tratamento_nao_aborta_e_diz_o_que_falta() -> None:
    """Uma pessoa no Nix tem de sair sabendo o que instalar à mão.

    Nem mentir ("ok") nem abortar (a máquina dela pode ter tudo por outro
    caminho): dizer o nome e seguir.
    """
    proc = _roda(
        "\n".join(
            [
                "_dep_presente() { return 1; }",
                'run_pkg() { printf "NAO DEVIA INSTALAR\\n"; }',
                "_garantir_deps_de_sistema",
                'printf "SEGUIU\\n"',
            ]
        ),
        preludo=PRELUDO_DRIVER,
        env={"HEFESTO_FAMILIA_PACOTES": "nenhum"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SEGUIU" in proc.stdout
    assert "NAO DEVIA INSTALAR" not in proc.stdout
    # O nome de referência tem de aparecer, senão o aviso não serve para nada.
    assert "librsvg2-common" in proc.stdout
    assert "libhidapi-hidraw0" in proc.stdout


def test_checagem_de_biblioteca_nao_morre_de_sigpipe(tmp_path: Path) -> None:
    """SIGPIPE-NA-CHECAGEM-01 — MEDIDO em 19/08/2026.

    ``ldconfig -p | grep -q libopus`` sob ``set -o pipefail`` devolve **141**:
    o grep sai no primeiro acerto, o ldconfig morre de SIGPIPE e o pipeline
    herda o sinal. A biblioteca PRESENTE era lida como ausente, e o bloco
    BT-MIC-01 chamava o gerenciador de pacotes a cada execução do install para
    instalar o que já estava instalado. O ``ldconfig`` falso abaixo imprime
    muito, justamente para que o SIGPIPE seja certo se alguém devolver o pipe.
    """
    binario = tmp_path / "bin"
    binario.mkdir()
    falso = binario / "ldconfig"
    falso.write_text(
        "#!/usr/bin/env bash\n"
        'printf "\\tlibhidapi-hidraw.so.0 (libc6,x86-64) => /usr/lib/libhidapi-hidraw.so.0\\n"\n'
        'for i in $(seq 1 20000); do\n'
        '    printf "\\tlib%s.so.6 => /usr/lib/lib%s.so.6\\n" "$i" "$i"\n'
        'done\n',
        encoding="utf-8",
    )
    falso.chmod(0o755)
    proc = _roda(
        '_dep_presente "lib:libhidapi" && printf "PRESENTE\\n"',
        preludo=PRELUDO_DRIVER,
        env={"PATH": f"{binario}:{os.environ['PATH']}"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PRESENTE" in proc.stdout


# --------------------------------------------------------------------------
# 5. O texto que caducou foi SUBSTITUÍDO
# --------------------------------------------------------------------------
def test_reconhecimento_nao_diz_mais_que_so_sabe_apt() -> None:
    """Fato errado se substitui (regra dela, 11/08/2026).

    A frase "o caminho nativo instala dependências só por apt" descrevia o
    instalador de ontem. Mantê-la ao lado do certo obriga a próxima pessoa a
    escolher entre duas afirmações.
    """
    assert "instala dependências só por apt" not in INSTALL
    assert "sem apt-get: esta não é uma distro da família Debian/Ubuntu" not in INSTALL


def test_nenhum_bloco_de_dependencia_ficou_preso_no_apt() -> None:
    """Os blocos que instalavam por apt passaram todos pelo despacho.

    Se alguém escrever um ``run_apt`` novo com nome de pacote na grafia do
    Debian, a distro de outra pessoa volta a ficar sem a cura — e é isso que
    esta régua pega.
    """
    # Nome LITERAL começa com letra/dígito; a única chamada legítima é a do
    # despacho, que passa a lista já traduzida (`run_apt "${_nomes[@]}"`).
    literais = re.compile(r"(?:^|[;&|(]|\s)run_apt\s+(?:\\\n\s*)?[A-Za-z0-9]", re.MULTILINE)
    sem_comentario = "\n".join(
        linha for linha in INSTALL.splitlines() if not linha.strip().startswith("#")
    )
    achados = literais.findall(sem_comentario)
    assert achados == [], "run_apt com nome de pacote literal, fora do run_pkg"


# ── PATH-SEM-SBIN-01 (19/08/2026) ────────────────────────────────────────────
# A régua de biblioteca perguntava ao `ldconfig`, e ele mora em `/usr/sbin` —
# que NÃO está no PATH de usuária comum no Debian 12; só no do root. Toda
# biblioteca PRESENTE era lida como ausente, e o instalador pedia `sudo` para
# instalar o que já estava lá (ou morria, no caso das obrigatórias).
#
# Por que nenhum portão via: os contêineres do `smoke-multi-distro`
# (.github/workflows/ci.yml) rodam como ROOT, e o root tem sbin no PATH em
# qualquer distro. O teste abaixo tira o sbin de propósito.
#
# A cura é a disciplina que o próprio arquivo já declara três linhas acima da
# função: "cada checagem pergunta pelo EFEITO, nunca pelo nome do pacote".
# `ctypes.CDLL` é o que o produto faz — o `hidapi` do pip abre por `ffi.dlopen`
# e o `dualsense_bt_audio` abre a libopus por `ctypes.CDLL`.


def _dep_presente_isolada(soname: str, *, path: str) -> int:
    """Roda `_dep_presente lib:<soname>` com o PATH que se pedir."""
    corpo = _extrai_funcao("_dep_presente")
    script = (
        "set -euo pipefail\n"
        f'VENV_DIR="{RAIZ / ".venv"}"\n'
        f"{corpo}\n"
        f'_dep_presente "lib:{soname}"\n'
    )
    return subprocess.run(
        ["/usr/bin/bash", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": path, "HOME": os.environ.get("HOME", "/tmp")},
    ).returncode


PATH_COM_SBIN = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
PATH_SEM_SBIN = "/usr/local/bin:/usr/bin:/bin"


class TestARaguaNaoDependeDoSbin:
    """A MORDIDA. Devolva o `ldconfig` no lugar do `ctypes` e isto reprova."""

    @pytest.mark.parametrize("path", [PATH_COM_SBIN, PATH_SEM_SBIN])
    def test_biblioteca_presente_e_vista_nos_dois_paths(self, path: str) -> None:
        rc = _dep_presente_isolada("libc.so.6", path=path)
        assert rc == 0, (
            "a libc — que existe em toda máquina Linux — foi lida como AUSENTE "
            f"com PATH={path!r}. Se o sbin sumiu do PATH, a régua está "
            "perguntando ao `ldconfig` em vez de perguntar se a biblioteca "
            "ABRE: é o defeito que fazia o instalador pedir sudo para instalar "
            "o que já estava instalado, em toda Debian 12 de usuária comum"
        )

    @pytest.mark.parametrize("path", [PATH_COM_SBIN, PATH_SEM_SBIN])
    def test_biblioteca_ausente_continua_ausente(self, path: str) -> None:
        """A cura não pode virar um sim para tudo."""
        rc = _dep_presente_isolada("libnaoexisteemlugarnenhum.so.99", path=path)
        assert rc != 0, (
            "uma biblioteca que não existe foi lida como PRESENTE — a régua "
            "parou de reprovar, e o instalador deixaria de instalar o que falta"
        )


# ── MAQUINA-SEM-BLUETOOTHCTL-01 e SONAME-QUE-NAO-ABRE-01 (19/08/2026) ────────
# Os dois foram achados pelo job novo que EXECUTA o `install.sh` em contêiner,
# no primeiro uso dele. Nenhuma máquina de quem desenvolve os pega: todas têm
# `bluetoothctl`, e todas tinham o `ldconfig` no PATH.


class TestMaquinaSemBluetoothctl:
    """O `install.sh` morria com 127, calado, antes do passo 1 de 11.

    `bluetoothctl --version | awk ...` num PATH sem `bluetoothctl`: o
    `command not found` devolve 127, o `set -o pipefail` (install.sh:188)
    propaga, o `set -e` derruba o script — e o `2>/dev/null` engole até a
    mensagem. Medido em contêiner debian:12 limpo:
    `install.sh terminou com código 127 em 50s`.

    E contradizia o desenho do próprio arquivo: o censo lista `bluez` como
    IMPORTANTE, não obrigatória — o instalador deve seguir sem ele e avisar.
    """

    def test_a_leitura_da_versao_do_bluez_nao_derruba_o_script(self) -> None:
        """A MORDIDA. Tire o `|| true` da linha e isto reprova com 127."""
        linha = _linha_do_install("bluetoothctl --version")
        assert linha is not None, "a leitura da versão do BlueZ sumiu do install.sh"
        assert "|| true" in linha, (
            "a leitura da versão do BlueZ voltou a ser um pipeline sem guarda: "
            f"{linha.strip()!r}. Numa máquina sem `bluetoothctl` isso devolve "
            "127, o pipefail propaga e o instalador morre CALADO antes do "
            "passo 1 de 11 — medido em contêiner debian:12 limpo"
        )

    def test_o_pipeline_sem_guarda_realmente_mata(self) -> None:
        """A prova de que a guarda não é decoração: sem ela, 127."""
        sem_guarda = (
            'set -euo pipefail\n'
            '_bz="$(bluetoothctl --version 2>/dev/null | awk "{print \\$NF}")"\n'
            'echo PASSOU\n'
        )
        com_guarda = sem_guarda.replace('}")"', '}" || true)"')
        magro = _path_sem(["bluetoothctl"])
        r_sem = subprocess.run(
            ["/usr/bin/bash", "-c", sem_guarda],
            capture_output=True, text=True, env={"PATH": magro},
        )
        r_com = subprocess.run(
            ["/usr/bin/bash", "-c", com_guarda],
            capture_output=True, text=True, env={"PATH": magro},
        )
        assert r_sem.returncode == 127, (
            "sem a guarda o pipeline devia morrer com 127 e não morreu — o "
            "ambiente do teste tem `bluetoothctl` no PATH e a prova não vale"
        )
        assert r_com.returncode == 0, (
            f"COM a guarda o pipeline ainda morre (rc={r_com.returncode}): "
            "a cura não cobre o caso"
        )


class TestOSonameTemDeAbrir:
    """A régua pergunta pelo EFEITO (`ctypes.CDLL`), e efeito exige soname real.

    `lib:libhidapi` funcionava com o `ldconfig -p | grep` porque ali era
    SUBSTRING. Com `ctypes.CDLL` é `dlopen`, e `dlopen('libhidapi')` falha:
    medido nesta bancada, com a biblioteca instalada.
    """

    def test_todo_soname_da_tabela_e_carregavel_ou_ausente_de_verdade(self) -> None:
        """A MORDIDA. Troque um soname por um nome sem `.so` e isto reprova."""
        import ctypes

        maus: list[str] = []
        for linha in _entradas_de_deps():
            checagem = linha.split("|")[2]
            if not checagem.startswith("lib:"):
                continue
            for soname in checagem[len("lib:"):].split(","):
                if ".so" not in soname:
                    maus.append(soname)
                    continue
                try:
                    ctypes.CDLL(soname)
                except OSError as exc:
                    # Ausente nesta máquina é legítimo; nome INVÁLIDO não é.
                    if "cannot open shared object file" not in str(exc):
                        maus.append(f"{soname} ({exc})")
        assert not maus, (
            f"soname que o `dlopen` nunca abre: {maus}. A régua do install "
            "pergunta pelo EFEITO com `ctypes.CDLL`, e isso é `dlopen` — um "
            "nome sem `.so` funcionava só enquanto a régua era `grep` na saída "
            "do `ldconfig`, e reprovaria a dependência em TODA máquina"
        )
