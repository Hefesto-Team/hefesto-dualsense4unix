"""O fixador e o leitor só nas fontes (O-FIXADOR-E-O-LEITOR-SO-NAS-FONTES-01).

A caixa do leitor e do fixador leva ``tmpfs`` na ``HOME``. O leitor recebe, só de leitura, as
pastas visíveis da ``HOME`` (sem ponto, onde moram as pastas de jogos que a configuração aponta),
cada fonte (com o ``-wal`` e o ``-shm`` do banco) e as pastas da última leitura que são do mesmo
programa de uma fonte; o fixador, só as fontes, graváveis. A pasta que a leitura devolve é saída
não confiável: a ``HOME``, a raiz, o escondido do topo e o de outro programa não voltam. A fonte
fora da pasta de um lançador, ou que alcança o que roda na sessão ou guarda chave (``.bashrc``,
``.ssh``, ``site-packages``…), recusa o manifesto.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]

_LEITOR = """
import json, os, sys
casa = os.environ["HOME"]
visto = {}
for rel in sys.argv[1:]:
    caminho = os.path.join(casa, rel)
    try:
        with open(caminho) as f:
            visto[rel] = f.read().strip()
    except OSError as exc:
        visto[rel] = type(exc).__name__
print(json.dumps(visto))
"""


def _lar(base: Path) -> Path:
    lar = base / "casa"
    for rel, texto in ((".ssh/x", "chave"), (".gnupg/y", "segredo"), (".bashrc", "alias"),
                       (".config/emu/emu.ini", "jogos=Jogos"), (".config/emu/outro.ini", "par"),
                       (".config/vizinho/z.ini", "vizinho"), ("Jogos/a.iso", "jogo"),
                       (".local/share/roms/b.gba", "rom"), (".local/share/emu/roms/c.gba", "rom"),
                       (".config/emu/banco.db", "db"), (".config/emu/banco.db-wal", "wal")):
        alvo = lar / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto)
    return lar


def _rodar(argv: list[str], lar: Path) -> dict[str, str]:
    feito = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False,
                           env={"HOME": str(lar), "PATH": "/usr/bin:/bin"})
    assert feito.returncode == 0, feito.stderr
    return json.loads(feito.stdout)


_LIDOS = [".ssh/x", ".gnupg/y", ".bashrc", ".config/emu/emu.ini", ".config/emu/outro.ini",
          ".config/vizinho/z.ini", "Jogos/a.iso", ".local/share/roms/b.gba",
          ".local/share/emu/roms/c.gba", ".config/emu/banco.db", ".config/emu/banco.db-wal"]


def test_com_o_bwrap_real_o_leitor_nao_abre_a_ssh_e_ve_as_fontes(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exigir_caixa_do_bwrap()
    lar = _lar(curto)
    pasta = curto / "ext"
    pasta.mkdir()
    leitor = censo.LeitorPorProcesso("emu", "Emu", ("python3",), pasta,
                                     fontes=(".config/emu/emu.ini", ".config/emu/banco.db"))
    monkeypatch.setattr(censo, "_PASTAS_DA_ULTIMA_LEITURA",
                        {"emu": (str(lar / ".local/share/roms"),
                                 str(lar / ".local/share/emu/roms"))})
    argv = censo.linha_do_leitor(leitor, ["/usr/bin/python3", "-c", _LEITOR, *_LIDOS],
                                 shutil.which("bwrap"), lar)
    visto = _rodar(argv, lar)
    assert visto[".ssh/x"] == "FileNotFoundError", visto
    assert visto[".gnupg/y"] == "FileNotFoundError", visto
    assert visto[".bashrc"] == "FileNotFoundError", visto
    assert visto[".config/vizinho/z.ini"] == "FileNotFoundError", visto
    assert visto[".config/emu/emu.ini"] == "jogos=Jogos"
    assert visto[".config/emu/outro.ini"] == "FileNotFoundError", "só a fonte, não a pasta da fonte"
    assert visto[".config/emu/banco.db"] == "db"
    assert visto[".config/emu/banco.db-wal"] == "wal", "o -wal do banco volta com ele"
    assert visto["Jogos/a.iso"] == "jogo", "a pasta de jogos que a configuração aponta"
    assert visto[".local/share/emu/roms/c.gba"] == "rom", "a pasta da última leitura, do emu"
    assert visto[".local/share/roms/b.gba"] == "FileNotFoundError", "a de outro programa"


_PASTAS_RUINS = ("/", "{lar}", "{lar}/..", "{lar}/.ssh", "{lar}/.config", "{lar}/.local/share",
                 "{lar}/Jogos/atalho", "{lar}/.config/vizinho", "{lar}/.config/autostart")


def test_a_pasta_que_a_leitura_devolve_nao_reabre_a_casa(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pasta da última leitura vem da extensão: a raiz, a HOME, o escondido do topo, o atalho
    para a ``.ssh`` e a pasta de outro programa não voltam (mordida: aceitar toda pasta)."""
    exigir_caixa_do_bwrap()
    lar = _lar(curto)
    (lar / ".config/autostart").mkdir(parents=True)
    (lar / "Jogos/atalho").symlink_to(lar / ".ssh")
    pasta = curto / "ext"
    pasta.mkdir()
    leitor = censo.LeitorPorProcesso("emu", "Emu", ("python3",), pasta,
                                     fontes=(".config/emu/emu.ini",))
    ruins = tuple(p.format(lar=lar) for p in _PASTAS_RUINS)
    monkeypatch.setattr(censo, "_PASTAS_DA_ULTIMA_LEITURA", {"emu": ruins})
    argv = censo.linha_do_leitor(leitor, ["/usr/bin/python3", "-c", _LEITOR, *_LIDOS],
                                 shutil.which("bwrap"), lar)
    for escrever in (False, True):
        casa = censo._a_casa_na_caixa(lar, leitor.fontes, ruins, escrever=escrever)[2:]
        for ruim in ruins:
            assert ruim not in casa, ruim
    visto = _rodar(argv, lar)
    for segredo in (".ssh/x", ".gnupg/y", ".bashrc", ".config/vizinho/z.ini"):
        assert visto[segredo] == "FileNotFoundError", (segredo, visto)
    for escrever in (False, True):
        for ruim in ruins:
            assert not censo._pasta_que_volta(ruim, lar, (".config/emu/emu.ini",),
                                              escrever=escrever), ruim


def test_a_fonte_na_raiz_de_config_nao_abre_a_config_inteira(curto: Path) -> None:
    lar = _lar(curto)
    (lar / ".config/emu.ini").write_text("x")
    argv = censo._a_casa_na_caixa(lar, (".config/emu.ini",), (), escrever=False)
    assert str(lar / ".config") not in argv
    assert str(lar / ".config/emu.ini") in argv


_FIXADOR = """
import json, os, sys
casa = os.environ["HOME"]
visto = {}
for rel in sys.argv[1:]:
    try:
        with open(os.path.join(casa, rel), "a") as f:
            f.write("+")
        visto[rel] = "escreveu"
    except OSError as exc:
        visto[rel] = type(exc).__name__
print(json.dumps(visto))
"""


def test_com_o_bwrap_real_o_fixador_escreve_so_a_fonte(curto: Path) -> None:
    exigir_caixa_do_bwrap()
    lar = _lar(curto)
    pasta = curto / "ext"
    pasta.mkdir()
    fixador = censo.FixadorPorProcesso("emu", "Emu", ("python3",), pasta,
                                       (".config/emu/emu.ini",))
    argv = censo.linha_do_fixador(
        fixador, ["/usr/bin/python3", "-c", _FIXADOR, ".config/emu/emu.ini", ".bashrc",
                  "Jogos/a.iso"], shutil.which("bwrap"), lar)
    visto = _rodar(argv, lar)
    assert visto[".config/emu/emu.ini"] == "escreveu"
    assert visto["Jogos/a.iso"] == "FileNotFoundError", visto
    assert (lar / ".bashrc").read_text() == "alias", "o .bashrc de dentro é do tmpfs"
    assert (lar / "Jogos/a.iso").read_text() == "jogo"
    assert (lar / ".config/emu/emu.ini").read_text() == "jogos=Jogos+"


@pytest.mark.parametrize("fonte", [".bashrc", ".profile", ".zshrc", ".zprofile",
                                   ".config/autostart/x.desktop", ".config/systemd/user/x.service",
                                   ".config/environment.d/x.conf", ".local/bin/x", ".ssh/id",
                                   ".gnupg/pubring.kbx", ".config/*", "*", ".*rc",
                                   ".config/fish/config.fish", ".config/zsh/.zshrc",
                                   ".config/" + "hefesto-dualsense" + "4unix/x.json",
                                   ".local/share/" + "hefesto-dualsense" + "4unix/mods/x/x.py",
                                   ".local/share/applications/x.desktop",
                                   ".local/lib/python3.12/site-packages/x.pth",
                                   "Jogos/site-packages/x.pth", ".mozilla/x", ".local/share",
                                   ".config", "emu.ini", ".kshrc", ".xinitrc", ".bash_logout"])
def test_a_fonte_que_executa_recusa_o_manifesto(fonte: str, tmp_path: Path) -> None:
    for campo in ("leitor", "fixador"):
        bloco = {"rotulo": "Emu", "comandos": ["emu"],
                 campo: {"executar": ["python3", "x.py"], "fontes": [fonte]}}
        with pytest.raises(ValueError, match="fora da pasta de um lançador ou no que roda"):
            censo.lancador_da_modificacao("emu", bloco, tmp_path)


def test_as_fontes_das_extensoes_da_casa_passam(tmp_path: Path) -> None:
    for fonte in (".config/retroarch/playlists/*.lpl", "Games/Hookshot/bin/*",
                  ".var/app/net.lutris.Lutris/data/lutris/pga.db", ".config/Kyty/Kyty.ini",
                  ".local/share/lutris/games/*.yml", ".config/lutris",
                  ".config/hookshot/builder.ini",
                  ".var/app/org.DolphinEmu.dolphin-emu/config/dolphin-emu/Dolphin.ini"):
        assert not censo.fonte_que_executa(fonte), fonte


def test_o_sim_do_lancador_lista_as_fontes_do_fixador(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.cli import cmd_mod
    from hefesto_dualsense4unix.mods.instalador import instalar

    casa = curto / "casa"
    casa.mkdir()
    for nome, valor in (("HOME", casa), ("XDG_CONFIG_HOME", casa / ".config"),
                        ("XDG_DATA_HOME", casa / ".local/share"),
                        ("XDG_STATE_HOME", casa / ".local/state"),
                        ("XDG_CACHE_HOME", casa / ".cache"), ("XDG_RUNTIME_DIR", curto / "run")):
        monkeypatch.setenv(nome, str(valor))
    (curto / "run").mkdir(mode=0o700)
    fonte = curto / "fonte"
    fonte.mkdir()
    (fonte / "fixa.py").write_text("print('{}')\n")
    (fonte / "hefesto-mod.json").write_text(json.dumps({
        "id": "emu", "nome": "Emu", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["lancador"], "permissoes": ["lancador"],  # (noqa-acento)
        "lancador": {"rotulo": "Emu", "comandos": ["emu"],
                     "fixador": {"executar": ["python3", "fixa.py"],
                                 "fontes": [".config/emu/emu.ini"]}}}))
    instalar(str(fonte), lugares=None)
    saida = CliRunner().invoke(cmd_mod.app, ["permissoes", "emu"]).output  # (noqa-acento)
    assert "a extensão escreve só: .config/emu/emu.ini." in saida, saida
    assert censo.frase_do_fixador({"rotulo": "x"}) == ""
