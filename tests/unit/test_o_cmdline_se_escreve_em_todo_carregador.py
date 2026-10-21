"""O-CMDLINE-DO-DUALSENSE-SO-SE-ESCREVE-NO-KERNELSTUB-01: o cmdline se escreve em todo carregador.

O `integrations/kernel_cmdline.py` é o dono único de quem lê e de quem escreve o carregador de
boot: o kernelstub do Pop!_OS, o grub do Ubuntu e do Fedora (com o comando de regenerar que a
máquina tem) e o systemd-boot pelo `/etc/kernel/cmdline`. Cada caso roda contra uma árvore de
mentira: o plano do passo 3e escrito e revertido deixa o arquivo como estava, e o comando de
regenerar é o daquela distro. Nada aqui toca o `/etc` da máquina.

A mordida: tirar um carregador de `carregadores_presentes` (o `/etc/kernel/cmdline`, por exemplo)
reprova o caso dele.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
QUIRK = "usbcore.quirks=054c:0ce6:gn"
GRUB_UBUNTU = (
    "GRUB_DEFAULT=0\n"
    "GRUB_TIMEOUT=5\n"
    'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n'
    'GRUB_CMDLINE_LINUX=""\n'
)
GRUB_FEDORA = (
    "GRUB_TIMEOUT=5\n"
    'GRUB_DISTRIBUTOR="$(sed \'s, release .*$,,g\' /etc/system-release)"\n'
    'GRUB_CMDLINE_LINUX="rhgb quiet"\n'
    "GRUB_ENABLE_BLSCFG=true\n"
)
KERNEL_CMDLINE = "root=UUID=0000-forjado rw quiet\n"


class _Maquina:
    """Uma árvore de mentira: os arquivos do carregador, os comandos que há e os que rodaram."""

    def __init__(self, raiz: Path, comandos: tuple[str, ...]) -> None:
        self.raiz = raiz
        self.lugares = kc.Lugares.da_raiz(raiz)
        self.comandos = {nome: f"/usr/sbin/{nome}" for nome in comandos}
        self.rodou: list[list[str]] = []

    def which(self, nome: str) -> str | None:
        return self.comandos.get(nome)

    def rodar(self, comando: list[str]) -> int:
        """Grava o comando; o kernelstub de mentira edita o JSON, como o de verdade."""
        self.rodou.append(comando)
        if comando[0].endswith("/kernelstub"):
            conf = self.lugares.kernelstub
            data = json.loads(conf.read_text(encoding="utf-8"))
            opcoes = data["user"]["kernel_options"]
            if comando[1] == "--delete-options":
                opcoes[:] = [o for o in opcoes if o != comando[2]]
            else:
                opcoes.append(comando[2])
            conf.write_text(json.dumps(data), encoding="utf-8")
        return 0

    def ler(self) -> kc.Carregador:
        return kc.ler_o_carregador(self.lugares, self.which)

    def escrever(self, tira: list[str], poe: list[str]) -> kc.Escrita:
        return kc.escrever(self.ler(), tira, poe, self.lugares, self.which, self.rodar)


def _escrito(caminho: Path, texto: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def _ubuntu(tmp_path: Path) -> tuple[_Maquina, Path]:
    maquina = _Maquina(tmp_path, ("update-grub",))
    return maquina, _escrito(maquina.lugares.grub, GRUB_UBUNTU)


def _fedora_bls(tmp_path: Path) -> tuple[_Maquina, Path]:
    maquina = _Maquina(tmp_path, ("grubby", "grub2-mkconfig"))
    (tmp_path / "boot/loader/entries").mkdir(parents=True)
    _escrito(tmp_path / "boot/grub2/grub.cfg", "")
    return maquina, _escrito(maquina.lugares.grub, GRUB_FEDORA)


def _fedora_sem_bls(tmp_path: Path) -> tuple[_Maquina, Path]:
    maquina = _Maquina(tmp_path, ("grub2-mkconfig",))
    _escrito(tmp_path / "boot/grub2/grub.cfg", "")
    return maquina, _escrito(maquina.lugares.grub, GRUB_FEDORA)


def _systemd_boot(tmp_path: Path) -> tuple[_Maquina, Path]:
    maquina = _Maquina(tmp_path, ("kernel-install",))
    for versao in ("6.9.1-forjado", "6.10.0-forjado"):
        _escrito(tmp_path / "usr/lib/modules" / versao / "vmlinuz", "")
    return maquina, _escrito(maquina.lugares.kernel_cmdline, KERNEL_CMDLINE)


def _pop(tmp_path: Path) -> tuple[_Maquina, Path]:
    maquina = _Maquina(tmp_path, ("kernelstub",))
    conf = {"user": {"kernel_options": ["quiet", "splash", "loglevel=0"]}}
    return maquina, _escrito(maquina.lugares.kernelstub, json.dumps(conf))


ARVORES = {
    "ubuntu-grub": (_ubuntu, kc.BACKEND_GRUB),
    "fedora-grubby": (_fedora_bls, kc.BACKEND_GRUB),
    "fedora-grub2-mkconfig": (_fedora_sem_bls, kc.BACKEND_GRUB),
    "systemd-boot": (_systemd_boot, kc.BACKEND_SYSTEMD_BOOT),
    "pop-kernelstub": (_pop, kc.BACKEND_KERNELSTUB),
}


def _plano(tokens: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """O ``(tira, poe)`` do passo 3e sobre ``tokens``, sem bateria."""
    tira: list[str] = []
    poe: list[str] = []
    for acao in kc.plan_tokens(tokens):
        if acao.op in (kc.OP_ADD, kc.OP_REPLACE):
            tira.extend(acao.remove_tokens)
            poe.append(acao.token)
    return tira, poe


def _conteudo(arquivo: Path) -> object:
    texto = arquivo.read_text(encoding="utf-8")
    return json.loads(texto) if arquivo.name == "configuration" else texto


@pytest.mark.parametrize("arvore", sorted(ARVORES))
def test_o_plano_escrito_e_revertido_deixa_o_arquivo_como_estava(
    tmp_path: Path, arvore: str,
) -> None:
    montar, backend = ARVORES[arvore]
    maquina, arquivo = montar(tmp_path)
    antes = _conteudo(arquivo)
    carregador = maquina.ler()
    assert carregador.backend == backend, carregador

    tira, poe = _plano(carregador.tokens)
    assert QUIRK in poe and kc.AUTOSUSPEND_TOKEN in poe, poe
    escrita = maquina.escrever(tira, poe)
    assert escrita.falhas == () and escrita.avisos == (), escrita
    depois = maquina.ler()
    assert QUIRK in depois.tokens and kc.AUTOSUSPEND_TOKEN in depois.tokens, depois
    assert _plano(depois.tokens) == ([], []), "a segunda volta do plano tem de ser no-op"

    maquina.escrever(poe, tira)
    if arvore.startswith("fedora"):
        # O Fedora não traz a GRUB_CMDLINE_LINUX_DEFAULT: a 1ª escrita a cria; fica vazia.
        antes = f'{antes}GRUB_CMDLINE_LINUX_DEFAULT=""\n'
    assert _conteudo(arquivo) == antes, f"{arvore}: o revertido não voltou ao que estava"


def test_o_grub_do_ubuntu_regenera_pelo_update_grub_e_so_mexe_na_linha_dele(
    tmp_path: Path,
) -> None:
    maquina, arquivo = _ubuntu(tmp_path)
    maquina.escrever([], [QUIRK])
    assert maquina.rodou == [["/usr/sbin/update-grub"]]
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    assert linhas[2] == f'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash {QUIRK}"', linhas
    assert [linhas[0], linhas[1], linhas[3]] == ["GRUB_DEFAULT=0", "GRUB_TIMEOUT=5",
                                                 'GRUB_CMDLINE_LINUX=""']


def test_o_fedora_com_bls_regenera_pelo_grubby_em_todo_kernel(tmp_path: Path) -> None:
    maquina, arquivo = _fedora_bls(tmp_path)
    maquina.escrever([], [QUIRK])
    assert maquina.rodou == [["/usr/sbin/grubby", "--update-kernel=ALL", f"--args={QUIRK}"]]
    assert f'GRUB_CMDLINE_LINUX_DEFAULT="{QUIRK}"' in arquivo.read_text(encoding="utf-8")
    maquina.rodou.clear()
    maquina.escrever([QUIRK], [])
    assert maquina.rodou == [["/usr/sbin/grubby", "--update-kernel=ALL",
                              f"--remove-args={QUIRK}"]]


def test_o_fedora_sem_grubby_regenera_o_grub_cfg_que_existe(tmp_path: Path) -> None:
    maquina, _ = _fedora_sem_bls(tmp_path)
    maquina.escrever([], [QUIRK])
    assert maquina.rodou == [["/usr/sbin/grub2-mkconfig", "-o",
                              str(tmp_path / "boot/grub2/grub.cfg")]]


def test_o_systemd_boot_leva_o_cmdline_a_cada_kernel_pelo_kernel_install(
    tmp_path: Path,
) -> None:
    maquina, arquivo = _systemd_boot(tmp_path)
    maquina.escrever([], [QUIRK])
    assert arquivo.read_text(encoding="utf-8") == f"root=UUID=0000-forjado rw quiet {QUIRK}\n"
    modulos = tmp_path / "usr/lib/modules"
    assert maquina.rodou == [
        ["/usr/sbin/kernel-install", "add", v, str(modulos / v / "vmlinuz")]
        for v in ("6.10.0-forjado", "6.9.1-forjado")
    ]


def test_o_kernelstub_escreve_pelos_proprios_comandos(tmp_path: Path) -> None:
    maquina, _ = _pop(tmp_path)
    velho = "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"
    maquina.escrever([], [velho])
    maquina.rodou.clear()
    maquina.escrever([velho], [QUIRK])
    assert maquina.rodou == [["/usr/sbin/kernelstub", "--delete-options", velho],
                             ["/usr/sbin/kernelstub", "--add-options", QUIRK]]


def test_o_kernelstub_vem_antes_do_grub_e_sem_nenhum_e_none(tmp_path: Path) -> None:
    maquina, _ = _pop(tmp_path)
    _escrito(maquina.lugares.grub, GRUB_UBUNTU)
    assert maquina.ler().backend == kc.BACKEND_KERNELSTUB
    assert [c.backend for c in kc.carregadores_presentes(maquina.lugares, maquina.which)] == [
        kc.BACKEND_KERNELSTUB, kc.BACKEND_GRUB]
    vazia = _Maquina(tmp_path / "vazia", ("kernelstub", "update-grub"))
    assert vazia.ler() == kc.Carregador(kc.BACKEND_NENHUM)
    with pytest.raises(ValueError, match="desconhecido"):
        kc.escrever(vazia.ler(), [], [QUIRK], vazia.lugares, vazia.which, vazia.rodar)


def test_sem_comando_de_regenerar_o_grub_avisa_em_vez_de_calar(tmp_path: Path) -> None:
    maquina = _Maquina(tmp_path, ())
    _escrito(maquina.lugares.grub, GRUB_UBUNTU)
    escrita = maquina.escrever([], [QUIRK])
    assert maquina.rodou == []
    assert escrita.avisos and "regenere o grub.cfg" in escrita.avisos[0], escrita


def test_a_linha_de_comando_escreve_no_carregador_que_o_plano_pediu(tmp_path: Path) -> None:
    """O ``escrever`` do script recusa outro carregador: o plano é de um, a escrita é dele."""
    grub = _escrito(tmp_path / "etc/default/grub", GRUB_UBUNTU)
    argumentos = ["--raiz", str(tmp_path), "--grub-conf", str(grub),
                  "--kernelstub-conf", str(tmp_path / "nao-ha"),
                  "--kernel-cmdline", str(tmp_path / "nao-ha")]
    assert kc.main(["escrever", "--backend", kc.BACKEND_SYSTEMD_BOOT, "--poe", QUIRK,
                    *argumentos]) == 2
    assert QUIRK not in grub.read_text(encoding="utf-8")


# --- O python REAL do passo 3e, contra cada árvore ----------------------------------------


def _heredoc_do_passo_3e() -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    m = re.search(r"_cmdline_plan=\"\$\(python3 - [^\n]*<<'PYEOF'\n(?P<py>.*?)\nPYEOF\n",
                  texto, re.S)
    assert m is not None, "o python do passo 3e saiu do install.sh"
    return m["py"]


@pytest.mark.parametrize(("arvore", "backend"), [
    ("ubuntu-grub", "grub"), ("systemd-boot", "systemd-boot"), ("pop-kernelstub", "kernelstub"),
])
def test_o_passo_3e_le_cada_carregador_pelo_dono(
    tmp_path: Path, arvore: str, backend: str,
) -> None:
    montar, _ = ARVORES[arvore]
    maquina, _ = montar(tmp_path)
    codigo = _heredoc_do_passo_3e()
    for caminho, falso in (("/etc/kernelstub/configuration", maquina.lugares.kernelstub),
                           ("/etc/default/grub", maquina.lugares.grub),
                           ("/etc/kernel/cmdline", maquina.lugares.kernel_cmdline)):
        assert f'"{caminho}"' in codigo, caminho
        codigo = codigo.replace(f'"{caminho}"', f'"{falso}"')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if backend == "kernelstub":
        (bin_dir / "kernelstub").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "kernelstub").chmod(0o755)
    r = subprocess.run([sys.executable, "-", str(RAIZ), "0"], input=codigo,
                       capture_output=True, text=True, timeout=60, check=True,
                       env={"PATH": str(bin_dir)})
    assert f"backend={backend}" in r.stdout.splitlines(), r.stdout
    planos = [ln.split("\t") for ln in r.stdout.splitlines() if ln.startswith("plan\t")]
    assert {p[1]: p[3] for p in planos}["usbcore.quirks"] == QUIRK, planos


def test_o_install_escreve_pelo_dono_em_qualquer_carregador() -> None:
    """O 3e não escreve mais só no kernelstub, e o bootloader desconhecido ganha o token exato."""
    texto = INSTALL.read_text(encoding="utf-8")
    bloco = texto[texto.index('step "3e" "cmdline do kernel'):texto.index('step "3e-trava"')]
    assert "kernelstub --add-options" not in bloco and "kernelstub --delete-options" not in bloco
    assert 'kernel_cmdline.py"' in bloco and "escrever --backend" in bloco
    assert '_register_cmdline_owner "cmdline.backend"' in bloco
    assert "carregador de boot desconhecido" in bloco and "${_token}" in bloco
    assert shutil.which("bash")


def test_o_kernelstub_quebrado_nao_cai_no_grub(tmp_path: Path) -> None:
    """Com o kernelstub presente e o JSON dele quebrado, a leitura levanta: o grub não é o alvo."""
    maquina = _Maquina(tmp_path, ("kernelstub", "update-grub"))
    _escrito(maquina.lugares.kernelstub, "{ quebrado")
    grub = _escrito(maquina.lugares.grub, GRUB_UBUNTU)
    with pytest.raises(ValueError):
        maquina.ler()
    with pytest.raises(ValueError):
        kc.carregadores_presentes(maquina.lugares, maquina.which)
    assert grub.read_text(encoding="utf-8") == GRUB_UBUNTU
