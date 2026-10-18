"""ENSAIO-DO-INSTALL-01 — o `--dry-run` do `install.sh` diz o que faria e não faz."""

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
CAMADA_PATH = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
CAMADA = CAMADA_PATH.read_text(encoding="utf-8")

BINARIOS_DUBLADOS = (
    "sudo",
    "systemctl",
    "apt-get",
    "dnf",
    "pacman",
    "dkms",
    "kernelstub",
    "flatpak",
    "pactl",
    "gnome-extensions",
    "just",
    "cargo",
    "dmidecode",
    "update-initramfs",
    "modprobe",
    "udevadm",
    "visudo",
)

VERBOS_QUE_MUDAM = (
    "sudo install",
    "sudo tee",
    "sudo rm",
    "sudo cp",
    "sudo mkdir",
    "sudo kernelstub",
    "sudo apt-get",
    "sudo dnf",
    "sudo pacman",
    "sudo dkms",
    "sudo systemctl",
    "sudo env",
    "apt-get install",
    "dnf install",
    "pacman -S",
    "dkms add",
    "dkms build",
    "dkms install",
    "kernelstub",
    "update-initramfs",
    "daemon-reload",
    "enable",
    "disable",
    "restart",
    "unmask",
    "reset-failed",
    "gnome-extensions enable",
)

PEDIDOS_DE_SENHA = ("-v", "-A")

#: O que o `dpkg-query` de mentira responde à pergunta do `_pacotes_a_meio` (todos os pacotes, o
#: estado em três letras): só estados que NÃO são pacote a meio (`hi` retido, `rc` removido com
#: configuração, `un` desconhecido). O ensaio mede o install, não o banco do dpkg de quem roda.
DPKG_TUDO_EM_ORDEM = "ii  bash\nhi  linux-libc-dev\nrc  pacote-removido\nun  pacote-que-nao-veio\n"

#: Um pacote a meio de uma atualização, como o kernel baixado e não configurado (`iF`/`iU`).
DPKG_COM_PACOTE_A_MEIO = DPKG_TUDO_EM_ORDEM + "iF  linux-image-7.2.6-76070206-generic\n"

DPKG_QUERY_DE_VERDADE = shutil.which("dpkg-query")


def _dubla_o_dpkg(dublagem: Path, lista: str) -> None:
    """Põe um `dpkg-query` de mentira na frente do PATH, só para a pergunta do `_pacotes_a_meio`.

    Sem isto o plano do `run_pkg` muda numa máquina com o dpkg a meio (`iF`/`iU`): o ensaio
    diria «não faria» onde outra máquina diz «faria», e a régua mediria a máquina, não o install.
    Qualquer outra pergunta vai ao `dpkg-query` de verdade. Sem `dpkg-query` na máquina não há
    dublê: o `command -v` do install já dá «sem pacote a meio» e o resto do plano não muda.
    """
    if DPKG_QUERY_DE_VERDADE is None:
        return
    (dublagem / "dpkg-query.lista").write_text(lista, encoding="utf-8")
    alvo = dublagem / "dpkg-query"
    alvo.write_text(
        "#!/bin/sh\n"
        'if [ "$#" -eq 2 ] && [ "$1" = "-W" ]; then\n'
        '  case "$2" in\n'
        "    *'${db:Status-Abbrev}'*'${Package}'*)\n"
        f'      cat "{dublagem}/dpkg-query.lista"; exit 0 ;;\n'
        "  esac\n"
        "fi\n"
        f'exec "{DPKG_QUERY_DE_VERDADE}" "$@"\n',
        encoding="utf-8",
    )
    alvo.chmod(0o755)


def _sysfs_do_wifi(raiz: Path, *, com_wifi_usb: bool) -> Path:
    """Um sysfs de mentira para o `wifi_usb.sh --lista`: com ou sem um Wi-Fi no barramento USB.

    O plano do vigia depende de a máquina ter dongle (fc05e3599); o ensaio não pode
    perguntar isso ao `/sys` de quem roda a régua.
    """
    usb = raiz / "bus" / "usb"
    usb.mkdir(parents=True)
    (raiz / "class" / "net").mkdir(parents=True)
    if com_wifi_usb:
        aparelho = raiz / "devices" / "usb1" / "1-1" / "1-1:1.0"
        aparelho.mkdir(parents=True)
        (aparelho / "subsystem").symlink_to(usb)
        interface = raiz / "class" / "net" / "wlx0"
        (interface / "wireless").mkdir(parents=True)
        (interface / "device").symlink_to(aparelho)
    return raiz


def _bancada(
    tmp_path: Path,
    *,
    com_credencial: bool = True,
    com_wifi_usb: bool = False,
    dpkg: str = DPKG_TUDO_EM_ORDEM,
    dubles_extra: dict[str, str] | None = None,
) -> tuple[Path, Path, dict[str, str]]:
    """Um lar de mentira, um PATH só de dublês, e o ambiente que os usa.

    O `dpkg-query` também é dublê (`dpkg`: o que ele lista, tudo em ordem por padrão): o plano
    sai igual em qualquer máquina, com o dpkg dela a meio ou não.
    """
    lar = tmp_path / "lar"
    lar.mkdir()
    dublagem = tmp_path / "dubles"
    dublagem.mkdir()
    diario = tmp_path / "chamadas.log"

    for nome in BINARIOS_DUBLADOS:
        alvo = dublagem / nome
        recusa_o_n = (
            'case "$1" in -n) exit 1 ;; esac\n'
            if nome == "sudo" and not com_credencial
            else ""
        )
        alvo.write_text(
            "#!/bin/sh\n"
            f'printf "%s %s\\n" "{nome}" "$*" >> "{diario}"\n'
            + recusa_o_n
            + "exit 0\n",
            encoding="utf-8",
        )
        alvo.chmod(0o755)
    _dubla_o_dpkg(dublagem, dpkg)
    for nome, corpo in (dubles_extra or {}).items():
        (dublagem / nome).write_text(corpo, encoding="utf-8")
        (dublagem / nome).chmod(0o755)

    ambiente = dict(os.environ)
    ambiente["PATH"] = f"{dublagem}:{ambiente.get('PATH', '/usr/bin:/bin')}"
    ambiente["HOME"] = str(lar)
    ambiente["XDG_CONFIG_HOME"] = str(lar / ".config")
    ambiente["XDG_STATE_HOME"] = str(lar / ".local" / "state")
    ambiente["XDG_CACHE_HOME"] = str(lar / ".cache")
    ambiente["XDG_DATA_HOME"] = str(lar / ".local" / "share")
    ambiente["HEFESTO_WIFI_SYSFS"] = str(
        _sysfs_do_wifi(tmp_path / "sys", com_wifi_usb=com_wifi_usb)
    )
    return lar, diario, ambiente


def _roda_ensaio(
    tmp_path: Path,
    *flags: str,
    com_credencial: bool = True,
    com_wifi_usb: bool = False,
    dpkg: str = DPKG_TUDO_EM_ORDEM,
    ambiente_extra: dict[str, str] | None = None,
    dubles_extra: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    lar, diario, ambiente = _bancada(
        tmp_path,
        com_credencial=com_credencial,
        com_wifi_usb=com_wifi_usb,
        dpkg=dpkg,
        dubles_extra=dubles_extra,
    )
    ambiente.update(ambiente_extra or {})
    resultado = subprocess.run(
        [BASH, str(INSTALL_PATH), "--dry-run", *flags],
        capture_output=True,
        text=True,
        check=False,
        env=ambiente,
        cwd=str(RAIZ),
        timeout=45,
    )
    return resultado, lar, diario


class TestOEnsaioExiste:
    def test_a_flag_esta_no_parser_nas_duas_grafias(self) -> None:
        """A MORDIDA: apague `--dry-run|-n)` do `case` e isto reprova."""
        assert "--dry-run|-n)" in INSTALL, (
            "o `install.sh` não aceita mais `--dry-run`/`-n` — e o parser dele "
            "ABORTA com 'argumento desconhecido', então quem tentar o ensaio "
            "não vai ver um plano: vai ver um erro"
        )

    def test_o_help_anuncia_o_ensaio(self) -> None:
        """A MORDIDA: tire a linha `--dry-run` do cabeçalho e isto reprova."""
        ajuda = subprocess.run(
            [BASH, str(INSTALL_PATH), "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert ajuda.returncode == 0, ajuda.stderr
        assert "--dry-run" in ajuda.stdout, (
            "o `--help` do install não fala do `--dry-run`. É a flag que existe "
            "para ela olhar ANTES de deixar rodar — escondê-la anula o motivo"
        )

    def test_o_ensaio_sai_bem(self, tmp_path: Path) -> None:
        resultado, _lar, _diario = _roda_ensaio(tmp_path)
        assert resultado.returncode == 0, (
            f"o ensaio saiu com rc={resultado.returncode}.\n"
            f"stdout final:\n{resultado.stdout[-3000:]}\n"
            f"stderr:\n{resultado.stderr[-3000:]}"
        )
        assert "FIM DO ENSAIO" in resultado.stdout, (
            "o ensaio não chegou ao fim — ele parou no meio do plano, e um "
            "plano pela metade é pior que nenhum: dá a impressão de que o "
            "install faz só aquilo"
        )


#: Um kernel que não tem os cabeçalhos instalados: com o `uname -r` de mentira o passo dos módulos
#: DKMS não acha `/lib/modules/<versão>/build` e pede o pacote dos cabeçalhos ao `run_pkg`, o passo
#: do plano que chama o gerenciador de pacotes numa máquina de desenvolvimento com tudo instalado.
UNAME_SEM_CABECALHOS = (
    '#!/bin/sh\nif [ "$1" = "-r" ]; then echo 0.0.0-mentira; exit 0; fi\n'
    f'exec "{shutil.which("uname")}" "$@"\n'
)
AMBIENTE_DO_APT = {"HEFESTO_FAMILIA_PACOTES": "apt"}
O_PACOTE_DOS_CABECALHOS = "pacote(s) linux-headers-0.0.0-mentira"


@pytest.mark.skipif(
    DPKG_QUERY_DE_VERDADE is None or shutil.which("uname") is None,
    reason="o caso precisa do dpkg-query de verdade para dublar e do uname",
)
class TestOPlanoNaoDependeDoDpkgDeQuemRoda:
    """O ensaio mede o install: o `dpkg-query` de quem roda a régua não entra na conta."""

    def test_com_tudo_em_ordem_o_plano_instalaria_o_pacote(self, tmp_path: Path) -> None:
        """A MORDIDA: tire o dublê do `_bancada` e, numa máquina com `iF`, este caso reprova."""
        resultado, _lar, _diario = _roda_ensaio(
            tmp_path,
            ambiente_extra=AMBIENTE_DO_APT,
            dubles_extra={"uname": UNAME_SEM_CABECALHOS},
        )
        assert resultado.returncode == 0, resultado.stderr[-2000:]
        assert "FARIA (root) instalar pacote(s) com apt: linux-headers-0.0.0-mentira" in (
            resultado.stdout
        ), resultado.stdout[-2500:]
        assert "pacote a meio" not in resultado.stdout, resultado.stdout[-2500:]

    def test_com_pacote_a_meio_o_plano_diz_que_nao_instalaria(self, tmp_path: Path) -> None:
        """A MORDIDA: tire a checagem do `run_pkg` e o plano volta a prometer a instalação."""
        resultado, _lar, diario = _roda_ensaio(
            tmp_path,
            dpkg=DPKG_COM_PACOTE_A_MEIO,
            ambiente_extra=AMBIENTE_DO_APT,
            dubles_extra={"uname": UNAME_SEM_CABECALHOS},
        )
        assert resultado.returncode == 0, resultado.stderr[-2000:]
        assert "FIM DO ENSAIO" in resultado.stdout
        assert (
            f"não faria:   instalar {O_PACOTE_DOS_CABECALHOS}: o sistema tem pacote a meio "
            "(linux-image-7.2.6-76070206-generic)"
        ) in resultado.stdout, resultado.stdout[-2500:]
        assert "FARIA (root) instalar pacote(s) com apt: linux-headers" not in resultado.stdout
        chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
        assert not [linha for linha in chamadas if linha.startswith("apt-get")], chamadas


class TestOEnsaioNaoEscreve:
    """O coração da régua: o ATO, não a palavra."""

    def test_nao_cria_nenhum_arquivo_do_hefesto_no_lar(self, tmp_path: Path) -> None:
        """A MORDIDA: tire um `if [[ "${DRY_RUN:-0}" -eq 1 ]]` de qualquer passo"""
        _resultado, lar, _diario = _roda_ensaio(tmp_path)
        nossos = [
            str(p.relative_to(lar))
            for p in lar.rglob("*")
            if "hefesto" in str(p.relative_to(lar)).lower()
            or "wireplumber" in str(p.relative_to(lar)).lower()
            or "systemd" in str(p.relative_to(lar)).lower()
        ]
        assert not nossos, (
            "o ENSAIO ESCREVEU no lar de quem só queria ver o plano: "
            + ", ".join(sorted(nossos))
        )

    def test_nao_chama_nenhum_comando_que_mude_a_maquina(self, tmp_path: Path) -> None:
        """A MORDIDA: troque um `_ensaio_camada broker` de volta por"""
        _resultado, _lar, diario = _roda_ensaio(tmp_path)
        chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
        culpadas = [
            linha
            for linha in chamadas
            for verbo in VERBOS_QUE_MUDAM
            if verbo in linha
        ]
        assert not culpadas, (
            "o ensaio chamou comando que MUDA a máquina:\n  "
            + "\n  ".join(sorted(set(culpadas)))
        )

    def test_nao_pede_senha(self, tmp_path: Path) -> None:
        """A MORDIDA (feita em 03/09/2026): troque a condição do ramo do ensaio"""
        _resultado, _lar, diario = _roda_ensaio(tmp_path, com_credencial=False)
        chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
        pedidos = [
            linha
            for linha in chamadas
            if linha.startswith("sudo ")
            and any(f" {p}" in f" {linha[5:]} " for p in PEDIDOS_DE_SENHA)
        ]
        assert not pedidos, (
            "o ensaio PEDIU A SENHA do sudo:\n  " + "\n  ".join(sorted(set(pedidos)))
        )

    def test_nao_arma_o_keepalive_da_credencial(self, tmp_path: Path) -> None:
        """O `_start_sudo_keepalive` põe um laço em segundo plano que renova a"""
        resultado, _lar, _diario = _roda_ensaio(tmp_path, com_credencial=True)
        assert resultado.returncode == 0, resultado.stderr[-2000:]

    def test_nao_apaga_os_caches_da_arvore(self, tmp_path: Path) -> None:
        """O passo 1 apaga `dist/`, `build/` e os caches da árvore do projeto."""
        script = (
            'set -euo pipefail\n'
            f'ROOT_DIR="{tmp_path}"\n'
            'DRY_RUN=1\n'
            '_faria() { printf "FARIA %s\\n" "$*"; }\n'
            '_nao_faria() { :; }\n'
            + _bloco_do_passo_1()
        )
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "pacote.deb").write_text("não me apague", encoding="utf-8")
        subprocess.run(
            [BASH, "-c", script], capture_output=True, text=True, check=False, timeout=60
        )
        assert (tmp_path / "dist" / "pacote.deb").exists(), (
            "o ensaio APAGOU o dist/ da árvore — e ali pode estar o pacote que "
            "alguém acabou de construir"
        )


def _bloco_do_passo_1() -> str:
    """O laço de limpeza de caches do passo 1, extraído do arquivo."""
    abertura = 'if [[ "${DRY_RUN:-0}" -eq 1 ]]; then\n    # O ensaio nomeia os diretórios'
    inicio = INSTALL.index(abertura)
    fim = INSTALL.index("# 2. venv + GTK3 + pacote Python", inicio)
    corpo = INSTALL[inicio:fim]
    return corpo[: corpo.rindex("# ---")]


class TestNenhumaCuraDeHostEscapa:
    def test_o_ensaio_dubla_toda_funcao_host_da_camada(self) -> None:
        """A MORDIDA: acrescente uma `install_qualquer_coisa_host()` à"""
        na_lib = set(re.findall(r"^([a-z_0-9]+_host)\(\)\s*\{", CAMADA, re.MULTILINE))
        assert na_lib, "não achei função `*_host` nenhuma na camada_de_maquina.sh"
        dublada = {par[0] for par in _tabela_de_curas()}
        faltando = sorted(na_lib - dublada)
        assert not faltando, (
            "estas curas de HOST rodariam DE VERDADE dentro do `--dry-run`, "
            "escrevendo em /etc na máquina de quem só queria ver o plano: "
            + ", ".join(faltando)
            + ". Acrescente a linha em `_ENSAIO_CURAS_DE_HOST` (no `install.sh`, "
            "logo abaixo do `source` da lib) e a descrição em `_ensaio_camada`."
        )

    def test_todo_dubla_tem_descricao(self) -> None:
        """Um dublê sem `case` correspondente é um passo que some do plano —"""
        rotulos = {par[1] for par in _tabela_de_curas()}
        corpo = _corpo_da_funcao("_ensaio_camada")
        sem_descricao = sorted(r for r in rotulos if f"        {r})" not in corpo)
        assert not sem_descricao, (
            "estes passos ficariam MUDOS no plano do ensaio (o dublê existe, a "
            "descrição não): " + ", ".join(sem_descricao)
        )

    def test_a_tabela_nao_escreve_uma_definicao_de_cura_no_arquivo(self) -> None:
        """O `install.sh` não pode conter um SEGUNDO `nome_host() {`."""
        definicoes = re.findall(r"^\s*([a-z_0-9]+_host)\(\)\s*\{", INSTALL, re.MULTILINE)
        assert not definicoes, (
            "o `install.sh` define função `*_host` no próprio corpo: "
            + ", ".join(sorted(set(definicoes)))
            + ". Elas moram em `scripts/lib/camada_de_maquina.sh`, e as réguas "
            "desta casa acham o corpo de cada cura por este texto — um segundo "
            "`nome_host() {` aqui faz seis delas medirem a coisa errada. Para "
            "o ensaio, use a tabela `_ENSAIO_CURAS_DE_HOST`."
        )


def _corpo_da_funcao(nome: str) -> str:
    inicio = INSTALL.index(f"{nome}() {{")
    fim = INSTALL.index("\n}\n", inicio)
    return INSTALL[inicio:fim]


def _tabela_de_curas() -> list[tuple[str, str]]:
    """A tabela `_ENSAIO_CURAS_DE_HOST` do `install.sh`, lida do arquivo."""
    inicio = INSTALL.index("_ENSAIO_CURAS_DE_HOST=(")
    fim = INSTALL.index("\n)\n", inicio)
    return [
        (par.split(":")[0], par.split(":")[1])
        for par in re.findall(r'"([a-z_0-9]+_host:[a-z0-9-]+)"', INSTALL[inicio:fim])
    ]


DONOS_DOS_CAMINHOS = {
    "_ensaio_snd_quirk": ("scripts/install_snd_quirk.sh",),
    "_ensaio_wireplumber": ("scripts/fix_wireplumber_default_source.sh",),
    "_ensaio_camada": (
        "scripts/lib/camada_de_maquina.sh",
        "scripts/install_udev.sh",
        "scripts/install_osk.sh",
        "scripts/dkms_lib.sh",
        "scripts/desempenho.sh",
    ),
}

CAMINHOS_DO_SISTEMA = {
    "/sys/module/snd_usb_audio/parameters/quirk_flags",
    "/etc/modprobe.d",
    "/etc/systemd/system",
    "/usr/local/lib/hefesto-dualsense4unix",
}


class TestOPlanoNaoEnvelhece:
    @pytest.mark.parametrize("descritora", sorted(DONOS_DOS_CAMINHOS))
    def test_todo_caminho_citado_existe_no_roteiro_que_o_escreve(self, descritora: str) -> None:
        """A MORDIDA: troque um nome de arquivo na descrição (por exemplo"""
        corpo = _corpo_da_funcao(descritora)
        fontes = "\n".join(
            (RAIZ / dono).read_text(encoding="utf-8")
            for dono in DONOS_DOS_CAMINHOS[descritora]
        )
        caminhos = set(re.findall(r'(?:\$\{HOME\})?/[A-Za-z0-9_./${}-]+', corpo))
        orfaos = []
        for caminho in sorted(caminhos):
            limpo = caminho.rstrip("/.,)")
            if limpo in CAMINHOS_DO_SISTEMA or limpo.count("/") < 1:
                continue
            base = limpo.rsplit("/", 1)[-1]
            if not base or base in {"apps", "bin", "d"}:
                continue
            if base not in fontes:
                orfaos.append(f"{caminho} (procurei por '{base}')")
        assert not orfaos, (
            f"o plano do `--dry-run` promete mexer em coisa que "
            f"{', '.join(DONOS_DOS_CAMINHOS[descritora])} não escreve — a "
            f"descrição em `{descritora}` envelheceu: " + "; ".join(orfaos)
        )

    def test_o_plano_nomeia_o_que_mais_assusta(self, tmp_path: Path) -> None:
        """As mudanças que uma pessoa PRECISA ver antes de dizer sim."""
        resultado, _lar, _diario = _roda_ensaio(tmp_path)
        exigidas = {
            "a regra do sudoers": "/etc/sudoers.d/49-hefesto-bt-ponte",
            "as regras udev": "/etc/udev/rules.d/",
            "os módulos DKMS": "hefesto-hid-nintendo",
            "o serviço de sistema do broker": "/etc/systemd/system/hefesto-hidraw-broker.service",
            "os arquivos da Steam": "localconfig.vdf",
            "o backup do vdf": ".bak.steam-input-",
            "o initramfs": "initramfs",
            "a queda do daemon": "REINICIÁ-LO",
        }
        sumiram = [
            f"{o_que} ({marca})"
            for o_que, marca in exigidas.items()
            if marca not in resultado.stdout
        ]
        assert not sumiram, (
            "o plano do ensaio deixou de nomear mudanças que ela precisa ver "
            "antes de autorizar: " + "; ".join(sumiram)
        )

    def test_o_ensaio_diz_no_fim_que_nada_aconteceu(self, tmp_path: Path) -> None:
        """Quem rola oitenta linhas de plano não se lembra do cabeçalho."""
        resultado, _lar, _diario = _roda_ensaio(tmp_path)
        assert "NADA foi escrito" in resultado.stdout
        assert re.search(r"\d+ mudanças planejadas, \d+ delas com root", resultado.stdout), (
            "o fecho do ensaio não conta quantas mudanças o plano tem — o "
            "número é o que diz se ela está olhando um install inteiro ou um "
            "plano que morreu no meio"
        )
