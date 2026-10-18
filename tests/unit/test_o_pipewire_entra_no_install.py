"""O passo 3f-bis do install traz o PipeWire da casa, só sobre o que a máquina já tem.

O-PIPEWIRE-DA-CASA-LEVA-A-CURA-DO-METADATA-01 (15/10/2026). O passo constrói pelo
``scripts/construir_pipewire_backport.sh``, confere o ``SHA256SUMS``, fixa o
``.pref``, instala só os pacotes ``ii`` que estão abaixo da casa e reinicia o som.
Com a Steam aberta, recusa.

Nada aqui constrói, instala ou reinicia: o passo roda num bash com o construtor,
o ``dpkg-query``, o ``apt-get``, o ``sudo``, o ``pgrep`` e o ``systemctl`` de
mentira no PATH, e um lar de mentira no ``HOME``.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
DPKG = shutil.which("dpkg")
RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
CONSTRUTOR = RAIZ / "scripts" / "construir_pipewire_backport.sh"
RECEITA = RAIZ / "docs" / "usage" / "receita-backport-pipewire.md"

pytestmark = pytest.mark.skipif(DPKG is None, reason="sem dpkg para comparar versões")

PW = "1.6.9-0~hefesto24.04.1"
WP = "0.5.18-0~hefesto24.04.1"
PW_POP = "1.6.8-1pop1~1787688714~24.04~fdff050"
WP_POP = "0.5.12-2pop1~1766191027~24.04~d4bf441"

# A entrega: o nome do .deb e a revisão dele.
ENTREGA = {
    "libpipewire-0.3-modules": (PW, "amd64"),
    "libpipewire-0.3-0t64": (PW, "amd64"),
    "pipewire": (PW, "amd64"),
    "pipewire-bin": (PW, "amd64"),
    "pipewire-pulse": (PW, "amd64"),
    "pipewire-doc": (PW, "all"),
    "pipewire-tests": (PW, "amd64"),
    "libspa-0.2-jack": (PW, "amd64"),
    "wireplumber": (WP, "amd64"),
    "libwireplumber-0.5-0": (WP, "amd64"),
}

# A máquina do Pop: o que está `ii`, o que só o dpkg conhece (`un`), o que saiu
# deixando configuração (`rc`) e o metapacote que o mk-build-deps deixa.
MAQUINA_DO_POP = {
    "libpipewire-0.3-modules": ("ii ", "libpipewire-0.3-modules:amd64", PW_POP),
    "libpipewire-0.3-0t64": ("ii ", "libpipewire-0.3-0t64:amd64", PW_POP),
    "pipewire": ("ii ", "pipewire:amd64", PW_POP),
    "pipewire-bin": ("ii ", "pipewire-bin", PW_POP),
    "pipewire-pulse": ("ii ", "pipewire-pulse", PW_POP),
    "pipewire-doc": ("un ", "pipewire-doc", ""),
    "libspa-0.2-jack": ("rc ", "libspa-0.2-jack:amd64", PW_POP),
    "pipewire-build-deps": ("ii ", "pipewire-build-deps", PW),
    "wireplumber": ("ii ", "wireplumber", WP_POP),
    "libwireplumber-0.5-0": ("ii ", "libwireplumber-0.5-0:amd64", WP_POP),
}

INSTALADOS_DO_POP = {
    "libpipewire-0.3-modules",
    "libpipewire-0.3-0t64",
    "pipewire",
    "pipewire-bin",
    "pipewire-pulse",
    "wireplumber",
    "libwireplumber-0.5-0",
}


#: As funções do `install.sh` que o passo extraído carrega para o bash de mentira. Função que o
#: passo chama e não está aqui vira «command not found» e, dentro de um `if`, falso calado: foi
#: assim que a checagem do pacote a meio ficou fora da régua. O guarda abaixo confere a lista.
FUNCOES_EXTRAIDAS = (
    "ask_yn",
    "_bz_maior_do_archive",
    "_pw_versao_ii",
    "_pw_veredito",
    "_pw_debs_da_maquina",
    "_pw_versoes_anteriores",
    "_pw_o_que_sairia",
    "_pw_steam_aberta",
    "_pacotes_a_meio",
    "_avisa_pacote_a_meio",
    "install_pipewire_da_casa",
)

#: O que o script da régua define por conta própria, no lugar do `install.sh` inteiro.
FUNCOES_DUBLADAS = ("step", "warn", "_faria", "_faria_root")


def _funcao(nome: str) -> str:
    inicio = INSTALL.index(f"{nome}() {{\n")
    fim = INSTALL.index("\n}\n", inicio) + 3
    return INSTALL[inicio:fim]


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


@dataclass
class Corrida:
    rc: int
    saida: str
    chamadas: list[str]
    entrega: Path

    def instalados(self) -> set[str]:
        """Os pacotes do `apt-get install` de verdade (não a simulação)."""
        nomes: set[str] = set()
        for linha in self.chamadas:
            if linha.startswith("apt-get install ") and " -s " not in f"{linha} ":
                for palavra in linha.split():
                    if palavra.endswith(".deb"):
                        nomes.add(Path(palavra).name.split("_", 1)[0])
        return nomes

    def chamou(self, trecho: str) -> bool:
        return any(trecho in linha for linha in self.chamadas)


def _correr(
    tmp_path: Path,
    *,
    maquina: dict[str, tuple[str, str, str]] | None = None,
    steam_aberta: bool = False,
    sudo_ok: bool = True,
    rc_construtor: int = 0,
    remv: tuple[str, ...] = (),
    estragar: str = "",
    dry_run: bool = False,
    registro_antigo: str = "",
    outra_arquitetura: dict[str, tuple[str, str, str]] | None = None,
    a_meio: tuple[str, ...] = (),
) -> Corrida:
    maquina = MAQUINA_DO_POP if maquina is None else maquina
    lar = tmp_path / "lar"
    entrega = lar / ".cache" / "hefesto-dualsense4unix" / "pipewire-backport"
    entrega.mkdir(parents=True)
    raiz = tmp_path / "raiz"
    (raiz / "assets" / "pipewire-backport" / "apt").mkdir(parents=True)
    for rel in (
        "assets/pipewire-backport/BASELINE",
        "assets/pipewire-backport/apt/hefesto-pipewire.pref",
    ):
        shutil.copy(RAIZ / rel, raiz / rel)
    diario = tmp_path / "chamadas.log"
    fakes = tmp_path / "fakes"

    linhas_sums = []
    for pkg, (ver, arch) in ENTREGA.items():
        deb = entrega / f"{pkg}_{ver}_{arch}.deb"
        deb.write_bytes(f"deb de mentira {pkg}".encode())
        linhas_sums.append(f"{hashlib.sha256(deb.read_bytes()).hexdigest()}  {deb.name}")
    (entrega / "SHA256SUMS").write_text("\n".join(linhas_sums) + "\n", encoding="utf-8")
    if estragar:
        (entrega / estragar).write_bytes(b"outros bytes")
    if registro_antigo:
        (entrega / "VERSOES-ANTERIORES.txt").write_text(registro_antigo, encoding="utf-8")

    _exe(
        raiz / "scripts",
        "construir_pipewire_backport.sh",
        f'printf "construtor %s\\n" "$HEFESTO_PIPEWIRE_CACHE" >> "{diario}"\n'
        f'echo "[pipewire-backport] ERRO: faltam dependências de build (acima)" >&2\n'
        f"exit {rc_construtor}\n",
    )
    casos = "\n".join(
        f'  {pkg}) st="{st}"; bp="{bp}"; v="{v}" ;;' for pkg, (st, bp, v) in maquina.items()
    )
    # A cópia de outra arquitetura (o i386 que a Steam puxa) sai como segunda
    # linha quando o pacote é pedido sem `:arch`, como no dpkg-query de verdade.
    casos2 = "\n".join(
        f'  {pkg}) st2="{st}"; bp2="{bp}"; v2="{v}" ;;'
        for pkg, (st, bp, v) in (outra_arquitetura or {}).items()
    )
    # A pergunta de `_pacotes_a_meio` (todos os pacotes, estado de três letras): a máquina de
    # mentira só tem `ii`, e `a_meio` acrescenta os pacotes quebrados (`iF  nome`).
    lista_do_dpkg = "".join(f"{st}{bp.split(':')[0]}\\n" for st, bp, _v in maquina.values())
    lista_do_dpkg += "".join(f"{linha}\\n" for linha in a_meio)
    _exe(
        fakes,
        "dpkg-query",
        'fmt=""; pkg=""\n'
        'for a in "$@"; do case "$a" in -f=*) fmt="${a#-f=}" ;; -W) ;; *) pkg="$a" ;; esac; done\n'
        'if [[ -z "$pkg" && "$fmt" == *\'${db:Status-Abbrev}\'*\'${Package}\'* ]]; then\n'
        f'  printf "{lista_do_dpkg}"; exit 0\nfi\n'
        f'case "${{pkg%%:*}}" in\n{casos}\n'
        '  *) echo "dpkg-query: nenhum pacote casa com $pkg" >&2; exit 1 ;;\n'
        "esac\n"
        "out=\"${fmt//'${db:Status-Abbrev}'/$st}\"\n"
        "out=\"${out//'${binary:Package}'/$bp}\"\n"
        "out=\"${out//'${Version}'/$v}\"\n"
        'printf "%b" "$out"\n'
        f'st2=""; case "$pkg" in\n{casos2}\n  *) ;;\nesac\n'
        'if [[ -n "$st2" ]]; then\n'
        "  out=\"${fmt//'${db:Status-Abbrev}'/$st2}\"\n"
        "  out=\"${out//'${binary:Package}'/$bp2}\"\n"
        "  out=\"${out//'${Version}'/$v2}\"\n"
        '  printf "%b" "$out"\n'
        "fi\n",
    )
    _exe(
        fakes,
        "dpkg",
        'if [[ "$1" == "--print-architecture" ]]; then echo amd64; exit 0; fi\n'
        f'exec "{DPKG}" "$@"\n',
    )
    remv_txt = "".join(f"Remv {p} [x]\\n" for p in remv)
    _exe(
        fakes,
        "apt-get",
        f'printf "apt-get %s\\n" "$*" >> "{diario}"\n'
        'for a in "$@"; do [[ "$a" == "-s" ]] && { '
        f'printf "Inst pipewire [x] (y)\\n{remv_txt}"; exit 0; }}; done\n'
        "exit 0\n",
    )
    _exe(
        fakes,
        "apt-cache",
        f'printf "     %s | {PW_POP} | http://apt.pop-os.org x\\n" "$2"\n',
    )
    _exe(
        fakes,
        "sudo",
        f'printf "sudo %s\\n" "$*" >> "{diario}"\n'
        f'if [[ "$1" == "-n" ]]; then exit {0 if sudo_ok else 1}; fi\n'
        'if [[ "$1" == "env" ]]; then exec "$@"; fi\n'
        "exit 0\n",
    )
    _exe(
        fakes,
        "pgrep",
        f'printf "pgrep %s\\n" "$*" >> "{diario}"\nexit {0 if steam_aberta else 1}\n',
    )
    _exe(fakes, "systemctl", f'printf "systemctl %s\\n" "$*" >> "{diario}"\nexit 0\n')

    funcoes = "".join(_funcao(n) for n in FUNCOES_EXTRAIDAS)
    script = (
        "set -euo pipefail\n"
        'step() { printf \'\\n[%s] %s\\n\' "$1" "$2"; }\n'
        "warn() { printf '      aviso: %s\\n' \"$*\"; }\n"
        "_faria() { printf '      FARIA        %s\\n' \"$*\"; }\n"
        "_faria_root() { printf '      FARIA (root) %s\\n' \"$*\"; }\n"
        f'source "{RAIZ}/scripts/lib/som_da_sessao.sh"\n'
        + funcoes
        + "install_pipewire_da_casa\n"
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={
            "PATH": f"{fakes}:/usr/bin:/bin",
            "HOME": str(lar),
            "ROOT_DIR": str(raiz),
            "AUTO_YES": "1",
            "DRY_RUN": "1" if dry_run else "0",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return Corrida(r.returncode, r.stdout + r.stderr, chamadas, entrega)


def test_instala_so_os_pacotes_ii_e_reinicia_o_som(tmp_path: Path) -> None:
    """MORDIDA: tirar o filtro do `ii` faz o doc, o tests e o jack (rc) entrarem."""
    c = _correr(tmp_path)
    assert c.rc == 0, c.saida
    assert c.instalados() == INSTALADOS_DO_POP, c.saida
    assert c.chamou("systemctl --user restart pipewire pipewire-pulse wireplumber"), c.chamadas
    assert c.chamou("/etc/apt/preferences.d/hefesto-pipewire"), c.chamadas
    assert c.chamou("construtor "), "o passo não chamou o construtor"


def test_o_passo_extraido_leva_toda_funcao_do_install_que_ele_chama() -> None:
    """MORDIDA: tire `_avisa_pacote_a_meio` da lista e a chamada vira «command not found»."""
    definidas = set(re.findall(r"^([A-Za-z_][A-Za-z_0-9]*)\(\) \{$", INSTALL, re.MULTILINE))
    corpo = _funcao("install_pipewire_da_casa")

    def chama(nome: str, texto: str) -> bool:
        return re.search(rf"(?<![\w-]){re.escape(nome)}(?![\w-])", texto) is not None

    chamadas = {nome for nome in definidas if chama(nome, corpo)}
    # as funções de que as extraídas dependem, uma a uma, fecham o conjunto
    pendentes = list(chamadas)
    while pendentes:
        nome = pendentes.pop()
        if nome in FUNCOES_DUBLADAS:
            continue
        for outra in definidas - chamadas - {nome}:
            if chama(outra, _funcao(nome)):
                chamadas.add(outra)
                pendentes.append(outra)
    faltam = sorted(chamadas - set(FUNCOES_EXTRAIDAS) - set(FUNCOES_DUBLADAS))
    assert not faltam, (
        "o passo extraído chama função do install.sh que o bash de mentira não carrega "
        f"(vira «command not found» calado dentro de um `if`): {faltam}"
    )


def test_com_pacote_a_meio_o_apt_nao_e_chamado_e_o_recado_sai(tmp_path: Path) -> None:
    """MORDIDA: sem a checagem no passo (ou sem as duas funções na extração) o apt é chamado."""
    c = _correr(tmp_path, a_meio=("iF  linux-image-7.2.6-76070206-generic",))
    assert c.rc == 0, c.saida
    assert "pacote a meio" in c.saida and "linux-image-7.2.6-76070206-generic" in c.saida, c.saida
    assert "apt-get install -f" in c.saida, c.saida
    assert "rode ./install.sh de novo" in c.saida, c.saida
    assert not c.chamou("apt-get"), c.chamadas
    assert not c.instalados() and not c.chamou("systemctl"), c.chamadas
    assert not (c.entrega / "VERSOES-ANTERIORES.txt").exists()


def test_com_tudo_em_ii_nao_ha_recado_e_o_caminho_e_o_de_sempre(tmp_path: Path) -> None:
    c = _correr(tmp_path, a_meio=())
    assert "a meio" not in c.saida, c.saida
    assert c.instalados() == INSTALADOS_DO_POP, c.saida


def test_o_arquivo_de_volta_so_tem_ii_com_versao(tmp_path: Path) -> None:
    c = _correr(tmp_path)
    linhas = (c.entrega / "VERSOES-ANTERIORES.txt").read_text(encoding="utf-8").splitlines()
    assert linhas, c.saida
    for linha in linhas:
        pacote, _, versao = linha.partition("=")
        assert pacote and versao, f"linha sem versão no caminho de volta: {linha!r}"
        assert not pacote.endswith("-build-deps"), linha
    nomes = {linha.split("=", 1)[0].split(":", 1)[0] for linha in linhas}
    assert nomes == INSTALADOS_DO_POP
    assert f"libpipewire-0.3-modules:amd64={PW_POP}" in linhas


def test_a_copia_de_outra_arquitetura_so_entra_na_volta_se_instalada(tmp_path: Path) -> None:
    """MORDIDA: sem o filtro do `ii` na volta, o i386 que o dpkg só conhece sai `pacote=`."""
    c = _correr(
        tmp_path,
        outra_arquitetura={
            "libpipewire-0.3-0t64": ("ii ", "libpipewire-0.3-0t64:i386", PW_POP),
            "libpipewire-0.3-modules": ("un ", "libpipewire-0.3-modules:i386", ""),
            "libwireplumber-0.5-0": ("rc ", "libwireplumber-0.5-0:i386", WP_POP),
        },
    )
    linhas = (c.entrega / "VERSOES-ANTERIORES.txt").read_text(encoding="utf-8").splitlines()
    i386 = [linha for linha in linhas if ":i386=" in linha]
    assert i386 == [f"libpipewire-0.3-0t64:i386={PW_POP}"], linhas
    assert all(not linha.endswith("=") for linha in linhas), linhas


def test_o_registro_de_antes_nao_e_sobrescrito(tmp_path: Path) -> None:
    antigo = f"pipewire:amd64={PW_POP}\n"
    c = _correr(tmp_path, registro_antigo=antigo)
    assert (c.entrega / "VERSOES-ANTERIORES.txt").read_text(encoding="utf-8") == antigo


def test_uma_versao_nossa_volta_pela_do_archive(tmp_path: Path) -> None:
    """Sobre um ~hefesto anterior, a volta é a versão que o archive serve."""
    antiga = "1.6.9-0~hefesto24.04.0"
    maquina = dict(MAQUINA_DO_POP)
    maquina["pipewire"] = ("ii ", "pipewire:amd64", antiga)
    c = _correr(tmp_path, maquina=maquina)
    texto = (c.entrega / "VERSOES-ANTERIORES.txt").read_text(encoding="utf-8")
    assert "~hefesto" not in texto, texto
    assert f"pipewire:amd64={PW_POP}" in texto.splitlines()


def test_com_a_steam_aberta_recusa(tmp_path: Path) -> None:
    """MORDIDA: tirar a recusa faz a troca e o reinício do som saírem com a Steam aberta."""
    c = _correr(tmp_path, steam_aberta=True)
    assert c.rc == 0, c.saida
    assert "a Steam está aberta" in c.saida, c.saida
    assert not c.instalados(), c.chamadas
    assert not c.chamou("systemctl"), c.chamadas
    assert not (c.entrega / "VERSOES-ANTERIORES.txt").exists()


def test_sem_dependencias_de_build_avisa_e_segue(tmp_path: Path) -> None:
    c = _correr(tmp_path, rc_construtor=3)
    assert c.rc == 0, c.saida
    assert "faltam dependências de build" in c.saida
    assert "receita-backport-pipewire.md" in c.saida
    assert not c.chamou("apt-get"), c.chamadas


def test_a_entrega_que_nao_confere_nao_instala_nada(tmp_path: Path) -> None:
    c = _correr(tmp_path, estragar=f"pipewire-doc_{PW}_all.deb")
    assert "não confere pelo SHA256SUMS" in c.saida, c.saida
    assert not c.chamou("apt-get"), c.chamadas


def test_nunca_rebaixa(tmp_path: Path) -> None:
    """Um WirePlumber da distro acima da casa fica: a versão mais nova vence."""
    maquina = dict(MAQUINA_DO_POP)
    maquina["wireplumber"] = ("ii ", "wireplumber", "0.5.19-1")
    maquina["libwireplumber-0.5-0"] = ("ii ", "libwireplumber-0.5-0:amd64", "0.5.19-1")
    c = _correr(tmp_path, maquina=maquina)
    assert c.instalados() == INSTALADOS_DO_POP - {"wireplumber", "libwireplumber-0.5-0"}


def test_com_a_cura_ja_instalada_nem_constroi(tmp_path: Path) -> None:
    maquina = dict(MAQUINA_DO_POP)
    maquina["libpipewire-0.3-modules"] = ("ii ", "libpipewire-0.3-modules:amd64", PW)
    maquina["wireplumber"] = ("ii ", "wireplumber", WP)
    c = _correr(tmp_path, maquina=maquina)
    assert "nada a fazer" in c.saida, c.saida
    assert not c.chamou("construtor"), c.chamadas


def test_o_que_sairia_da_maquina_faz_recusar(tmp_path: Path) -> None:
    """Uma biblioteca i386 que o apt tiraria (a Steam a usa) barra a troca."""
    c = _correr(tmp_path, remv=("libpipewire-0.3-0t64:i386",))
    assert "tiraria da máquina" in c.saida and "i386" in c.saida, c.saida
    assert not c.instalados(), c.chamadas


def test_o_libcamera_pode_sair(tmp_path: Path) -> None:
    """A 1.6.9 da casa não constrói o libcamera: ele sair é o sabido."""
    c = _correr(tmp_path, remv=("libspa-0.2-libcamera",))
    assert c.instalados() == INSTALADOS_DO_POP, c.saida


def test_sudo_recusado_nao_instala(tmp_path: Path) -> None:
    c = _correr(tmp_path, sudo_ok=False)
    assert "sudo recusado" in c.saida, c.saida
    assert not c.instalados()


def test_o_ensaio_nao_constroi_nem_instala(tmp_path: Path) -> None:
    c = _correr(tmp_path, dry_run=True)
    assert "FARIA (root)" in c.saida and "REINICIAR o som" in c.saida, c.saida
    assert not c.chamadas, c.chamadas


def test_o_passo_vem_depois_do_bluez_e_com_a_mesma_guarda() -> None:
    """O PipeWire constrói contra o libbluetooth da casa: o 3f vem antes."""
    i3f = INSTALL.index('step "3f" ')
    ibis = INSTALL.index('step "3f-bis" ')
    i3g = INSTALL.index('step "3g" ')
    assert i3f < ibis < i3g
    guarda = INSTALL.rindex("\nif ", 0, ibis)
    assert '"${SKIP_UDEV}" -eq 0' in INSTALL[guarda:ibis]
    assert "command -v dpkg-query" in INSTALL[guarda:ibis]


def test_a_receita_grava_a_volta_so_com_ii(tmp_path: Path) -> None:
    """O comando da receita, rodado sobre um dpkg-query de mentira."""
    texto = RECEITA.read_text(encoding="utf-8")
    blocos = [b.split("```", 1)[0] for b in texto.split("```bash\n")[1:]]
    alvo = [b for b in blocos if "VERSOES-ANTERIORES.txt" in b and "dpkg-query" in b]
    assert len(alvo) == 1, "a receita perdeu o comando que grava o caminho de volta"
    fakes = tmp_path / "fakes"
    linhas = "".join(f"{st}|{bp}={v}\\n" for st, bp, v in MAQUINA_DO_POP.values())
    _exe(fakes, "dpkg-query", f'printf "{linhas}"\n')
    lar = tmp_path / "lar"
    (lar / ".cache" / "hefesto-dualsense4unix" / "pipewire-backport").mkdir(parents=True)
    r = subprocess.run(
        [BASH, "-c", "set -euo pipefail\n" + alvo[0]],
        env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(lar)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    gravado = (
        lar / ".cache" / "hefesto-dualsense4unix" / "pipewire-backport" / "VERSOES-ANTERIORES.txt"
    ).read_text(encoding="utf-8")
    saida = gravado.splitlines()
    assert saida, gravado
    assert all(not linha.endswith("=") for linha in saida), saida
    assert not any("-build-deps" in linha for linha in saida), saida
    assert not any(linha.startswith("libspa-0.2-jack") for linha in saida), "um rc entrou"
    assert f"libpipewire-0.3-modules:amd64={PW_POP}" in saida


def _aviso_do_libbluetooth(tmp_path: Path, versao: str, *, com_deb: bool, falta: str) -> str:
    texto = CONSTRUTOR.read_text(encoding="utf-8")
    inicio = texto.index("avisar_do_libbluetooth_dev() {\n")
    fim = texto.index("\n}\n", inicio) + 3
    fakes = tmp_path / "fakes"
    _exe(
        fakes,
        "dpkg-query",
        f'[[ "${{@: -1}}" == "libbluetooth3:amd64" ]] && printf "%s" "{versao}"\nexit 0\n',
    )
    _exe(fakes, "dpkg", "echo amd64\n")
    cache = tmp_path / "cache"
    obra = cache / "bluez-obra"
    obra.mkdir(parents=True)
    if com_deb:
        (obra / f"libbluetooth-dev_{versao}_amd64.deb").write_bytes(b"x")
    r = subprocess.run(
        [BASH, "-c", texto[inicio:fim] + 'avisar_do_libbluetooth_dev "$FALTA"\n'],
        env={
            "PATH": f"{fakes}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_BLUEZ_CACHE": str(cache),
            "FALTA": falta,
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout + r.stderr


FALTA_DO_PIPEWIRE = "dpkg-checkbuilddeps: erro: doxygen libbluetooth-dev meson-1.7"
BLUEZ_DA_CASA = "5.87-0ubuntu0.1~hefesto24.04.5"


def test_o_construtor_avisa_a_ordem_do_libbluetooth_dev(tmp_path: Path) -> None:
    saida = _aviso_do_libbluetooth(tmp_path, BLUEZ_DA_CASA, com_deb=True, falta=FALTA_DO_PIPEWIRE)
    assert "ANTES do mk-build-deps" in saida, saida
    deb = f"{tmp_path}/cache/bluez-obra/libbluetooth-dev_{BLUEZ_DA_CASA}_amd64.deb"
    assert f"sudo apt install {deb}" in saida


def test_sem_o_deb_da_obra_manda_construir_o_bluez(tmp_path: Path) -> None:
    saida = _aviso_do_libbluetooth(tmp_path, BLUEZ_DA_CASA, com_deb=False, falta=FALTA_DO_PIPEWIRE)
    assert "scripts/construir_bluez_backport.sh" in saida, saida


@pytest.mark.parametrize(
    "ver,falta",
    [
        ("5.72-0ubuntu5.5", FALTA_DO_PIPEWIRE),
        (BLUEZ_DA_CASA, "dpkg-checkbuilddeps: erro: doxygen meson-1.7"),
    ],
)
def test_sem_bluez_da_casa_ou_sem_a_falta_fica_calado(tmp_path: Path, ver: str, falta: str) -> None:
    assert _aviso_do_libbluetooth(tmp_path, ver, com_deb=True, falta=falta) == ""


def test_o_aviso_sai_antes_do_mk_build_deps() -> None:
    texto = CONSTRUTOR.read_text(encoding="utf-8")
    corpo = texto[texto.index("checar_dependencias() {\n") :]
    corpo = corpo[: corpo.index("\n}\n")]
    assert corpo.index("avisar_do_libbluetooth_dev") < corpo.index("mk-build-deps")


DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _doctor_fora_do_dpkg(tmp_path: Path, dono: str) -> str:
    """O doctor numa máquina sem o PipeWire no dpkg, com o binário de `dono`."""
    fakes = tmp_path / "fakes"
    _exe(fakes, "pipewire", 'printf "pipewire\\nLinked with libpipewire 1.6.8\\n"\n')
    _exe(fakes, "dpkg-query", "exit 1\n")
    _exe(fakes, "dpkg", "exit 1\n")
    _exe(fakes, "pacman", f"exit {0 if dono == 'arch' else 1}\n")
    _exe(fakes, "rpm", f"exit {0 if dono == 'fedora' else 1}\n")
    r = subprocess.run(
        [BASH, "-c", 'set --; source "$DOCTOR_SH"; check_pipewire_cura_do_metadata; true'],
        env={"PATH": f"{fakes}:/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.mark.parametrize(
    "dono,gesto",
    [("fedora", "sudo dnf upgrade"), ("arch", "sudo pacman -Syu"), ("", "1.6.9 ou mais nova")],
)
def test_fora_do_dpkg_a_cura_vem_da_distro(tmp_path: Path, dono: str, gesto: str) -> None:
    saida = _doctor_fora_do_dpkg(tmp_path, dono)
    assert saida.startswith("[WARN] o PipeWire 1.6.8 não tem a cura"), saida
    assert "a cura vem da distro" in saida and gesto in saida, saida
    assert "receita" not in saida and "install.sh" not in saida, saida


def test_no_dpkg_o_doctor_aponta_o_install_e_a_receita() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    corpo = texto[texto.index("_pw_gesto_da_cura() {\n") :]
    corpo = corpo[: corpo.index("\n}\n")]
    assert "./install.sh, passo 3f-bis" in corpo
    assert "docs/usage/receita-backport-pipewire.md" in corpo
