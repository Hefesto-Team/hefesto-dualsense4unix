"""O fixador e o leitor só nas fontes (O-FIXADOR-E-O-LEITOR-SO-NAS-FONTES-01).

A caixa do leitor e do fixador leva ``tmpfs`` na ``HOME``. O leitor recebe, só de leitura, as
pastas visíveis da ``HOME`` (sem ponto, onde moram as pastas de jogos que a configuração aponta),
a pasta de cada fonte e as pastas da última leitura; o fixador, só as fontes, graváveis. As fontes
que alcançam o que roda na sessão ou guarda chave (``.bashrc``, ``.ssh``…) recusam o manifesto.
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
                       (".local/share/roms/b.gba", "rom")):
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
          ".config/vizinho/z.ini", "Jogos/a.iso", ".local/share/roms/b.gba"]


def test_com_o_bwrap_real_o_leitor_nao_abre_a_ssh_e_ve_as_fontes(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exigir_caixa_do_bwrap()
    lar = _lar(curto)
    pasta = curto / "ext"
    pasta.mkdir()
    leitor = censo.LeitorPorProcesso("emu", "Emu", ("python3",), pasta,
                                     fontes=(".config/emu/emu.ini",))
    monkeypatch.setattr(censo, "_PASTAS_DA_ULTIMA_LEITURA",
                        {"emu": (str(lar / ".local/share/roms"),)})
    argv = censo.linha_do_leitor(leitor, ["/usr/bin/python3", "-c", _LEITOR, *_LIDOS],
                                 shutil.which("bwrap"), lar)
    visto = _rodar(argv, lar)
    assert visto[".ssh/x"] == "FileNotFoundError", visto
    assert visto[".gnupg/y"] == "FileNotFoundError", visto
    assert visto[".bashrc"] == "FileNotFoundError", visto
    assert visto[".config/vizinho/z.ini"] == "FileNotFoundError", visto
    assert visto[".config/emu/emu.ini"] == "jogos=Jogos"
    assert visto[".config/emu/outro.ini"] == "par", "a pasta da fonte volta inteira"
    assert visto["Jogos/a.iso"] == "jogo", "a pasta de jogos que a configuração aponta"
    assert visto[".local/share/roms/b.gba"] == "rom", "a pasta da última leitura"


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
                                   ".gnupg/pubring.kbx", ".config/*", "*", ".*rc"])
def test_a_fonte_que_executa_recusa_o_manifesto(fonte: str, tmp_path: Path) -> None:
    for campo in ("leitor", "fixador"):
        bloco = {"rotulo": "Emu", "comandos": ["emu"],
                 campo: {"executar": ["python3", "x.py"], "fontes": [fonte]}}
        with pytest.raises(ValueError, match="roda na sessão ou guarda chave"):
            censo.lancador_da_modificacao("emu", bloco, tmp_path)


def test_as_fontes_das_extensoes_da_casa_passam(tmp_path: Path) -> None:
    for fonte in (".config/retroarch/playlists/*.lpl", "Games/Hookshot/bin/*",
                  ".var/app/net.lutris.Lutris/data/lutris/pga.db", ".config/Kyty/Kyty.ini"):
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
