"""LUZ-DO-MIC-01 · PEÇA E — o `install.sh` entrega a luz do microfone pronta."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
PYPROJECT = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))

CANONICO = "pactl"

CHECAGEM = "cmd:pactl,parec"

NOMES_DE_PACOTE = {
    "apt": "pulseaudio-utils",
    "dnf": "pulseaudio-utils",
    "pacman": "libpulse",
}
FAMILIAS = tuple(NOMES_DE_PACOTE)

LIFECYCLE = "src/hefesto_dualsense4unix/daemon/lifecycle.py"

SUBSISTEMA_DA_LUZ = "luz_do_mic"
SUBSISTEMA_GATEADO = "mic_hotkey"

PECAS_DA_LUZ = (
    "src/hefesto_dualsense4unix/integrations/quem_ouve_o_microfone.py",
    "src/hefesto_dualsense4unix/integrations/nivel_do_microfone.py",
    "src/hefesto_dualsense4unix/daemon/subsystems/luz_do_mic.py",
)

BIBLIOTECAS_NAO_DECLARADAS = (
    "numpy",
    "scipy",
    "sounddevice",
    "pyaudio",
    "soundfile",
    "alsaaudio",
    "pulsectl",
    "samplerate",
)


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


def _roda(
    corpo: str, *, preludo: str = "", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    ambiente = dict(os.environ)
    ambiente.pop("HEFESTO_FAMILIA_PACOTES", None)
    ambiente.pop("HEFESTO_OS_RELEASE", None)
    ambiente.update(env or {})
    cabeca = "\n".join(
        [
            "set -euo pipefail",
            _extrai_funcao("_familia_pacotes"),
            _extrai_funcao("_pkg_nome"),
            preludo,
        ]
    )
    return subprocess.run(
        [BASH, "-c", cabeca + "\n" + corpo],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=120,
    )


def test_o_censo_pede_as_ferramentas_do_pulseaudio() -> None:
    """A MORDIDA: tire a linha ``"pactl|...`` do ``_DEPS_DE_SISTEMA`` e isto"""
    linha = _linha_do_censo(CANONICO)
    assert linha is not None, (
        "as ferramentas do PulseAudio saíram do censo `_DEPS_DE_SISTEMA`: a "
        "luz do microfone volta a depender de instalação à mão, contra a regra "
        "dela — toda cura entra no install, sem flag"
    )


def test_a_checagem_pede_os_dois_binarios() -> None:
    """A METADE QUE FALTAVA, e é o ponto inteiro desta linha."""
    linha = _linha_do_censo(CANONICO)
    assert linha is not None, "a linha do pactl sumiu do censo"
    checagem = linha.split("|")[2]
    assert checagem == CHECAGEM, (
        f"a checagem virou {checagem!r}. Ela tem de pedir os DOIS binários "
        f"({CHECAGEM}): o `pactl` dá o 'quem está ouvindo' e o `parec` dá o "
        "'está entrando som'. Com um só, metade da luz morre em silêncio"
    )


def test_a_criticidade_e_importante_e_a_razao_diz_o_que_quebra() -> None:
    """`importante`, não `obrigatoria` — e a diferença é deliberada."""
    linha = _linha_do_censo(CANONICO)
    assert linha is not None, "a linha do pactl sumiu do censo"
    _, criticidade, _, razao = linha.split("|")
    assert criticidade == "importante", (
        f"a criticidade virou {criticidade!r}. `obrigatoria` mataria o install "
        "de quem não usa o microfone do controle — e a luz apagada é estado "
        "válido do contrato da LUZ-DO-MIC-01, não falha de instalação"
    )
    assert razao.strip(), "a linha ficou sem o 'o que quebra sem ele'"
    assert "luz" in razao.lower(), (
        "a razão não diz que quem quebra é a LUZ do microfone. Ela é o texto "
        "que o install imprime na tela dela quando a dependência falta"
    )


@pytest.mark.parametrize("familia", FAMILIAS)
def test_a_tabela_traduz_o_canonico_em_cada_familia(familia: str) -> None:
    """A MORDIDA: arranque a linha ``pactl)`` de ``_pkg_nome`` e as três"""
    proc = _roda(f"_pkg_nome {CANONICO} {familia}")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == NOMES_DE_PACOTE[familia], (
        f"o nome do pacote em {familia} mudou. O `apt` foi MEDIDO nesta bancada "
        "em 03/09/2026 (`dpkg -S` de `/usr/bin/pactl` e de `/usr/bin/pacat`, "
        "para onde o `parec` aponta, devolvem os dois `pulseaudio-utils`); as "
        "outras duas colunas vêm da DEPS-UNIVERSAIS-01 e este teste as tranca "
        "contra mudança silenciosa"
    )


def _path_so_com(tmp_path: Path, binarios: tuple[str, ...]) -> str:
    """Um PATH que contém EXATAMENTE os binários pedidos."""
    alvo = tmp_path / "bin"
    alvo.mkdir(exist_ok=True)
    for nome in binarios:
        falso = alvo / nome
        falso.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        falso.chmod(0o755)
    return str(alvo)


def _checagem_do_censo() -> str:
    """A checagem COMO ELA ESTÁ NO `install.sh`, não a constante deste arquivo."""
    linha = _linha_do_censo(CANONICO)
    assert linha is not None, "a linha do pactl sumiu do censo `_DEPS_DE_SISTEMA`"
    return linha.split("|")[2]


def _checagem_com_path(caminho: str, checagem: str) -> int:
    """Roda ``_dep_presente <checagem>`` com o PATH que se pedir."""
    script = "\n".join(
        [
            "set -euo pipefail",
            f'PATH="{caminho}"',
            'VENV_DIR="/naoexiste"',
            '_VENV_PYTHON="python3"',
            _extrai_funcao("_dep_presente"),
            f'_dep_presente "{checagem}"',
        ]
    )
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=120
    ).returncode


def test_maquina_com_os_dois_binarios_le_como_presente(tmp_path: Path) -> None:
    """A régua não pode virar um NÃO para tudo."""
    caminho = _path_so_com(tmp_path, ("pactl", "parec"))
    assert _checagem_com_path(caminho, _checagem_do_censo()) == 0, (
        "os dois binários estavam no PATH e a checagem os leu como AUSENTES — "
        "o instalador pediria sudo a cada execução para instalar o que já tem"
    )


def test_falta_so_o_parec_e_lido_como_ausente(tmp_path: Path) -> None:
    """O CASO REAL DA METADE QUE FALTAVA, encenado — e ele é o motivo do `,parec`."""
    caminho = _path_so_com(tmp_path, ("pactl",))
    assert _checagem_com_path(caminho, _checagem_do_censo()) != 0, (
        "uma máquina COM o pactl e SEM o parec foi lida como completa. A luz "
        "acenderia fixa e nunca piscaria, e o install não teria o que instalar"
    )


def test_maquina_sem_nenhum_dos_dois_le_como_ausente(tmp_path: Path) -> None:
    """A metade que toda máquina consegue medir."""
    caminho = _path_so_com(tmp_path, ())
    assert _checagem_com_path(caminho, _checagem_do_censo()) != 0, (
        "um PATH sem pactl e sem parec foi lido como PRESENTE: a régua parou "
        "de reprovar e o install deixaria de instalar as ferramentas"
    )


def test_o_censo_oferece_o_pactl_sozinho_quando_ele_falta() -> None:
    """Item 4 da PEÇA E: *nada de novo pede configuração do usuário*."""
    preludo = "\n".join(
        [
            'warn() { printf "aviso: %s\\n" "$*"; }',
            'die()  { printf "ERRO: %s\\n" "$*" >&2; exit 42; }',
            'ask_yn() { REPLY="y"; }',
            "AUTO_YES=1",
            _extrai_array("_DEPS_DE_SISTEMA"),
            f'_dep_presente() {{ [[ "$1" == "{CHECAGEM}" ]] && return 1; return 0; }}',
            'run_pkg() { printf "run_pkg %s\\n" "$*"; return 0; }',
            'comando_manual_pkg() { printf "manual %s\\n" "$*"; }',
            _extrai_funcao("_garantir_deps_de_sistema"),
        ]
    )
    proc = _roda("_garantir_deps_de_sistema", preludo=preludo,
                 env={"HEFESTO_FAMILIA_PACOTES": "apt"})
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    assert "falta pactl" in saida, (
        "o laço do install não NOMEOU o `pactl` como faltando. Sem isso ela "
        f"não tem como saber o que instalar. Saída:\n{saida}"
    )
    assert "luz do microfone" in saida, (
        "o install disse o nome da dependência mas não o que quebra sem ela — "
        f"a razão do censo não chegou à tela. Saída:\n{saida}"
    )
    assert re.search(r"^run_pkg .*\bpactl\b", saida, re.MULTILINE), (
        "o `pactl` foi listado como faltando mas NÃO foi passado ao "
        f"gerenciador de pacotes: o install avisa e não instala. Saída:\n{saida}"
    )


def test_a_luz_nao_acrescenta_flag_nem_variavel_de_ambiente() -> None:
    """A luz entra pelo mesmo caminho de toda dependência, e por nenhum outro."""
    proibidos = re.findall(
        r"(HEFESTO_[A-Z_]*(?:LUZ|MIC_LED)[A-Z_]*|--[a-z-]*luz-do-mic[a-z-]*)",
        INSTALL,
    )
    assert not proibidos, (
        f"o install ganhou flag ou variável só para a luz: {sorted(set(proibidos))}. "
        "A LUZ-DO-MIC-01 tem de nascer ligada num `./install.sh` limpo"
    )
    chamadas = [x for x in INSTALL.splitlines() if x.strip() == "_garantir_deps_de_sistema"]
    assert chamadas, (
        "`_garantir_deps_de_sistema` não é chamado em coluna 0 e sem condição: "
        "o censo virou opcional, e com ele a luz"
    )


def _distribuicoes_declaradas() -> set[str]:
    """Os nomes de import que o `pyproject.toml` autoriza."""
    brutos: list[str] = list(PYPROJECT["project"].get("dependencies", []))
    for extra in PYPROJECT["project"].get("optional-dependencies", {}).values():
        brutos.extend(extra)
    nomes = {
        re.split(r"[<>=!~\[ ]", x, maxsplit=1)[0].strip().lower().replace("-", "_")
        for x in brutos
    }
    apelidos = {
        "pygobject": "gi",
        "python_uinput": "uinput",
        "python_xlib": "Xlib",
        "pyyaml": "yaml",
        "types_pyyaml": "yaml",
        "types_python_xlib": "Xlib",
    }
    return nomes | {v for k, v in apelidos.items() if k in nomes} | {"gi", "uinput", "Xlib"}


def _imports_de_terceiros(caminho: Path) -> set[str]:
    """Os módulos de topo importados que não são da stdlib nem da casa."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    topos: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            topos.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                continue
            if no.module:
                topos.add(no.module.split(".")[0])
    return {
        x
        for x in topos
        if x not in sys.stdlib_module_names
        and x != "hefesto_dualsense4unix"
        and not x.startswith("_")
    }


def test_a_regua_de_imports_le_stdlib_puro_como_limpo(tmp_path: Path) -> None:
    """A metade que impede a régua de virar um NÃO para tudo."""
    alvo = tmp_path / "peca_de_mentira.py"
    alvo.write_text(
        "import struct\nimport subprocess\nfrom pathlib import Path\n"
        "from hefesto_dualsense4unix.integrations import fontes_de_captura\n"
        "from . import vizinho\n",
        encoding="utf-8",
    )
    assert _imports_de_terceiros(alvo) == set(), (
        "a régua acusou biblioteca de terceiro num módulo que só usa stdlib, a "
        "casa e import relativo — ela reprovaria a PEÇA B correta"
    )


def test_a_regua_de_imports_pega_a_biblioteca_nao_declarada(tmp_path: Path) -> None:
    """A outra metade, e é a que paga a dívida do `playwright`."""
    alvo = tmp_path / "peca_com_numpy.py"
    alvo.write_text("import numpy as np\nimport struct\n", encoding="utf-8")
    assert "numpy" in _imports_de_terceiros(alvo), (
        "a régua deixou o `numpy` passar. Ele NÃO está no `pyproject.toml` — "
        "vive só no `~/.local/lib` desta bancada — e uma árvore criada com "
        '`pip install -e ".[dev,emulation,cosmic]"` nasceria com a luz morta'
    )


def test_nenhum_modulo_do_src_importa_biblioteca_de_audio_nao_declarada() -> None:
    """A régua que já está VIVA hoje, antes de as PEÇAS A/B/C existirem."""
    achados: list[str] = []
    for caminho in sorted((RAIZ / "src").rglob("*.py")):
        try:
            terceiros = _imports_de_terceiros(caminho)
        except SyntaxError:  # pragma: no cover - módulo quebrado é outro portão
            continue
        for nome in sorted(terceiros & set(BIBLIOTECAS_NAO_DECLARADAS)):
            achados.append(f"{caminho.relative_to(RAIZ)}: {nome}")
    assert not achados, (
        "biblioteca NÃO declarada no `pyproject.toml` importada em `src/`: "
        + "; ".join(achados)
        + ". É a dívida do `playwright` repetida: a bancada de quem escreveu "
        "tem a biblioteca, e toda árvore nova nasce quebrada sem dizer por quê"
    )


def test_as_pecas_da_luz_so_importam_o_que_o_install_entrega() -> None:
    """O portão que acorda sozinho quando as PEÇAS A/B/C chegarem."""
    existentes = [RAIZ / x for x in PECAS_DA_LUZ if (RAIZ / x).exists()]
    if not existentes:
        pytest.skip(
            "as PEÇAS A/B/C ainda não estão nesta árvore — a régua acorda "
            "sozinha quando o primeiro dos três arquivos aparecer"
        )
    autorizadas = _distribuicoes_declaradas()
    achados: list[str] = []
    for caminho in existentes:
        for nome in sorted(_imports_de_terceiros(caminho)):
            if nome.lower().replace("-", "_") not in autorizadas and nome not in autorizadas:
                achados.append(f"{caminho.relative_to(RAIZ)}: {nome}")
    assert not achados, (
        "as peças da luz importam biblioteca que o `pyproject.toml` não "
        "declara: " + "; ".join(achados) + ". Ou ela entra no `pyproject.toml` "
        "(e no `.spec`, no `PKGBUILD`, no `control` e no flatpak junto), ou o "
        "código volta para a stdlib — que é o que a medição de custo mandou"
    )


def test_os_modulos_novos_viajam_no_wheel_sem_lista() -> None:
    """A razão de a PEÇA E não precisar tocar o `pyproject.toml` para isto."""
    alvo = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert alvo.get("packages") == ["src/hefesto_dualsense4unix"], (
        "o alvo do wheel deixou de levar o pacote inteiro: "
        f"{alvo.get('packages')!r}. Os módulos da LUZ-DO-MIC-01 "
        "(quem_ouve_o_microfone, nivel_do_microfone, luz_do_mic) viajam porque "
        "o pacote viaja — sem isso a feature fica só na árvore de quem a escreveu"
    )
    for padrao in alvo.get("include", []):
        assert not padrao.endswith(".py"), (
            f"o `include` do wheel ganhou um padrão de `.py` ({padrao!r}): isso "
            "sugere que alguém passou a listar módulo por módulo, e o próximo "
            "esquecido some do pacote sem aviso"
        )


FORMATOS = {
    "packaging/debian/control": r"^(Depends|Recommends|Suggests):.*\bpulseaudio-utils\b",
    "packaging/fedora/hefesto-dualsense4unix.spec":
        r"^(Requires|Recommends|Suggests):[[:space:]]*pulseaudio-utils",
    "packaging/arch/PKGBUILD": r"libpulse",
    "packaging/nix/package.nix": r"libpulseaudio|pulseaudio",
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml": r"pulseaudio",
}

LACUNAS_DECLARADAS = {
    "packaging/fedora/hefesto-dualsense4unix.spec": (
        "03/09/2026 — o `.spec` nunca declarou `pulseaudio-utils`, nem para o "
        "microfone por Bluetooth, que é mais velho que esta sprint. Fechar a "
        "lacuna é acrescentar um `Recommends`, e é mudança em arquivo que a "
        "PEÇA E não possui: fica para o fecho, com a palavra do usuário."
    ),
    "packaging/arch/PKGBUILD": (
        "03/09/2026 — mesma lacuna do `.spec`, herdada do BT-MIC-01. No Arch o "
        "nome é `libpulse`, e o lugar natural é `optdepends`."
    ),
    "packaging/nix/package.nix": (
        "03/09/2026 — mesma lacuna, herdada do BT-MIC-01."
    ),
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml": (
        "03/09/2026 — e esta é de outra natureza: o manifesto NÃO monta "
        "`--socket=pulseaudio`, então de dentro do sandbox não há servidor de "
        "áudio a alcançar. Declarar o binário lá não entregaria a luz; o que "
        "entregaria é o socket, e isso é decisão de permissão, não de pacote."
    ),
}


def _campos_debian(texto: str) -> str:
    """Junta as continuações (linhas que começam com espaço) ao campo delas."""
    linhas: list[str] = []
    for bruta in texto.splitlines():
        if bruta[:1] in (" ", "\t") and linhas:
            linhas[-1] = linhas[-1] + " " + bruta.strip()
        else:
            linhas.append(bruta)
    return "\n".join(linhas)


def _declara(arquivo: str) -> bool:
    caminho = RAIZ / arquivo
    if not caminho.exists():
        return False
    texto = caminho.read_text(encoding="utf-8")
    if arquivo.endswith("control"):
        texto = _campos_debian(texto)
    padrao = FORMATOS[arquivo].replace("[[:space:]]", r"\s")
    return re.search(padrao, texto, re.MULTILINE) is not None


def test_o_deb_declara_as_ferramentas_do_pulseaudio() -> None:
    """O formato que a máquina do usuário mais provavelmente encontra, e o único que"""
    assert _declara("packaging/debian/control"), (
        "`packaging/debian/control` parou de declarar `pulseaudio-utils`. É "
        "`Recommends` e não `Depends` de propósito — o apt o instala por "
        "padrão (que é o que atende 'sem flag') e ainda permite removê-lo sem "
        "levar o Hefesto junto"
    )


def test_todo_formato_declara_ou_tem_lacuna_com_motivo() -> None:
    """O portão que impede a lacuna SILENCIOSA."""
    sem_dono = [
        arquivo
        for arquivo in FORMATOS
        if not _declara(arquivo) and arquivo not in LACUNAS_DECLARADAS
    ]
    assert not sem_dono, (
        "formato de empacotamento que não declara as ferramentas do PulseAudio "
        "e não tem lacuna declarada: " + ", ".join(sem_dono) + ". A luz do "
        "microfone nasce morta nesse formato, em silêncio"
    )
    sem_motivo = [a for a, motivo in LACUNAS_DECLARADAS.items() if len(motivo.strip()) < 40]
    assert not sem_motivo, (
        f"lacuna declarada sem motivo escrito: {sem_motivo}. Lacuna sem motivo "
        "é a lacuna silenciosa com outro nome"
    )


def test_a_lista_de_lacunas_nao_guarda_lacuna_ja_fechada() -> None:
    """A lista não pode ficar velha."""
    velhas = [a for a in LACUNAS_DECLARADAS if _declara(a)]
    assert not velhas, (
        "lacuna JÁ FECHADA continua na lista: " + ", ".join(velhas) + ". Tire a "
        "entrada de `LACUNAS_DECLARADAS` — uma lista velha faz a próxima pessoa "
        "acreditar num buraco que não existe mais"
    )


def test_o_motivo_da_lacuna_do_flatpak_continua_verdadeiro() -> None:
    """O motivo do flatpak é uma AFIRMAÇÃO sobre o manifesto, e ela pode caducar."""
    manifesto = RAIZ / "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"
    assert manifesto.exists(), "o manifesto do flatpak sumiu"
    texto = manifesto.read_text(encoding="utf-8")
    tem_socket = re.search(r"^\s*-\s*--socket=(pulseaudio|pipewire)\b", texto, re.MULTILINE)
    assert tem_socket is None, (
        "o flatpak passou a montar o socket do servidor de áudio "
        f"({tem_socket.group(0).strip() if tem_socket else ''}). O motivo da "
        "lacuna dele em `LACUNAS_DECLARADAS` dizia o contrário e agora está "
        "errado: ou declare as ferramentas do PulseAudio no manifesto, ou "
        "reescreva o motivo com o que passou a valer"
    )


def test_familia_sem_tratamento_ainda_diz_o_nome_do_pacote() -> None:
    """A quarta família, e ela existe por decisão, de 19/08/2026."""
    proc = _roda(
        f"comando_manual_pkg {CANONICO}",
        preludo=_extrai_funcao("comando_manual_pkg"),
        env={"HEFESTO_FAMILIA_PACOTES": "nenhum"},
    )
    assert proc.returncode == 0, proc.stderr
    saida = proc.stdout.strip()
    assert NOMES_DE_PACOTE["apt"] in saida, (
        "numa família sem tratamento o install não NOMEOU o pacote das "
        f"ferramentas do PulseAudio. Saída: {saida!r}. Quem está no openSUSE ou "
        "no NixOS ficaria com a luz apagada e sem uma palavra sobre o que falta"
    )


def _gates_dos_subsistemas() -> dict[str, list[str]]:
    """Para cada ``self._safe_start("<nome>", …)``, as condições que o cercam."""
    caminho = RAIZ / LIFECYCLE
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: dict[str, list[str]] = {}

    def visita(no: ast.AST, cercas: list[str]) -> None:
        if isinstance(no, ast.Call):
            alvo = no.func
            if (
                isinstance(alvo, ast.Attribute)
                and alvo.attr == "_safe_start"
                and no.args
                and isinstance(no.args[0], ast.Constant)
                and isinstance(no.args[0].value, str)
            ):
                achados[no.args[0].value] = list(cercas)
        if isinstance(no, ast.If):
            dentro = [*cercas, ast.unparse(no.test)]
            fora = [*cercas, f"não ({ast.unparse(no.test)})"]
            for filho in no.body:
                visita(filho, dentro)
            for filho in no.orelse:
                visita(filho, fora)
            return
        for descendente in ast.iter_child_nodes(no):
            visita(descendente, cercas)

    visita(arvore, [])
    return achados


def test_a_regua_de_gate_enxerga_um_subsistema_que_e_gateado() -> None:
    """A metade que impede a régua de virar um SIM para tudo."""
    gates = _gates_dos_subsistemas()
    assert SUBSISTEMA_GATEADO in gates, (
        f"o subsistema `{SUBSISTEMA_GATEADO}` sumiu do laço de boot; a régua de "
        "gate ficou sem controle positivo e pode ter virado um sim para tudo"
    )
    assert gates[SUBSISTEMA_GATEADO], (
        f"o `{SUBSISTEMA_GATEADO}` deixou de ser gateado. Ou a régua parou de "
        "enxergar cercas — e aí ela daria verde para uma luz gateada —, ou o "
        "controle positivo mudou de lugar e este teste precisa de outro"
    )


def test_o_daemon_sobe_a_luz_do_mic_sem_gate_de_configuracao() -> None:
    """Item 4 da PEÇA E, na metade que o `install.sh` sozinho NÃO alcança."""
    gates = _gates_dos_subsistemas()
    assert SUBSISTEMA_DA_LUZ in gates, (
        "o daemon parou de subir o subsistema `luz_do_mic` no boot "
        f"({LIFECYCLE}). Um `install.sh` limpo instala as ferramentas e a luz "
        "continua apagada, porque ninguém liga o laço"
    )
    assert not gates[SUBSISTEMA_DA_LUZ], (
        "o subsistema `luz_do_mic` passou a subir atrás de "
        f"{gates[SUBSISTEMA_DA_LUZ]}. A LUZ-DO-MIC-01 §5.3b exige que um "
        "`install.sh` limpo entregue a luz funcionando, sem passo manual e sem "
        "flag: gate de configuração é passo manual com outro nome"
    )
