"""Os arquivos dos lançadores se leem e se escrevem por um dono só (utils/arquivo_de_terceiro.py).

D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: toda escrita num arquivo da Steam, do Heroic, do
Bottles ou de um prefixo guarda a cópia de antes, troca o arquivo por inteiro e poda as cópias; toda
leitura diz o motivo em frase em vez de levantar. A casa, a Steam e os vdf são de mentira.
"""
from __future__ import annotations

import stat
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import opcoes_por_jogo as opj
from hefesto_dualsense4unix.integrations import proton_pin as pp
from hefesto_dualsense4unix.utils import arquivo_de_terceiro as dono
from tests.unit.test_o_pin_do_proton_alcanca_todo_jogo import conf, lar  # noqa: F401
from tests.unit.test_o_pino_chega_a_qualquer_computador import (
    _jogo,
    _pino_na,
    _steam_de_verdade,
)
from tests.unit.test_opcoes_por_jogo_01_uma_linha_um_dono import (
    APPID,
    OPCOES,
    _a_steam_esta_fechada,  # noqa: F401
    _tabela,
    _vdf_de_mentira,
)

PASSOS: list[str] = []

TABELA = f"# meu comentário\n\n{APPID}\t{OPCOES}\n990000023\tMANGOHUD=1 %command%\n# o último\n"


def _copias(arquivo: Path, familia: str) -> list[Path]:
    achadas = arquivo.parent.glob(f"{arquivo.name}.bak.{familia}-*")
    return sorted(c for c in achadas if c.name.rsplit("-", 1)[1].isdigit()
                  and c.name == f"{arquivo.name}.bak.{familia}-{c.name.rsplit('-', 1)[1]}")


def _planta(arquivo: Path, familia: str, n: int) -> None:
    arquivo.with_name(f"{arquivo.name}.bak.{familia}-{n}").write_text("a\n", encoding="utf-8")


def _restos(pasta: Path) -> list[str]:
    return sorted(p.name for p in pasta.iterdir() if p.name.endswith("tmp"))


def _sobras(*_a: object, **_k: object) -> tuple[list[object], dict[str, str]]:
    PASSOS.append("sobras")
    return [], {}


def test_a_escrita_que_levanta_no_meio_deixa_o_vdf_inteiro(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: o vdf nunca fica pela metade."""
    vdf = _vdf_de_mentira(tmp_path)
    _tabela(tmp_path, **{APPID: OPCOES})
    antes = vdf.read_bytes()
    troca = Path.replace

    def _cai_na_troca(self: Path, alvo: str | Path) -> Path:
        if self.name.endswith(".hefesto-tmp"):
            self.write_bytes(self.read_bytes()[:40])
            raise OSError(28, "No space left on device")
        return troca(self, alvo)

    monkeypatch.setattr(Path, "replace", _cai_na_troca)
    relato = opj.aplicar(vdfs=[vdf], config_home=tmp_path)

    assert relato["status"] == opj.ERRO, relato
    assert vdf.read_bytes() == antes
    assert _restos(vdf.parent) == []
    assert _copias(vdf, "hefesto-opcoes") == []


def test_a_tabela_com_byte_invalido_recusa_o_definir_e_fica_igual(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: a tabela ilegível não se regrava."""
    tabela = opj.tabela_path(tmp_path)
    tabela.parent.mkdir(parents=True)
    torta = f"{APPID}\t{OPCOES}\n".encode() + b"990000023\tX=\xff %command%\n"
    tabela.write_bytes(torta)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    with pytest.raises(opj.TabelaIlegivelError, match="UTF-8"):
        opj.definir("990000024", "A=1 %command%", config_home=tmp_path)
    with pytest.raises(opj.TabelaIlegivelError):
        opj.tirar(APPID, config_home=tmp_path)
    assert opj.main(["--definir", "990000024", "A=1 %command%"]) == 2
    assert opj.main(["--tirar", APPID]) == 2

    assert "UTF-8" in capsys.readouterr().err
    assert tabela.read_bytes() == torta
    assert _copias(tabela, "hefesto-tabela") == []


def test_o_definir_e_o_tirar_guardam_os_comentarios_e_as_outras_linhas(tmp_path: Path) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: o `--definir` não apaga o resto."""
    tabela = opj.tabela_path(tmp_path)
    tabela.parent.mkdir(parents=True)
    tabela.write_text(TABELA, encoding="utf-8")

    opj.definir("990000024", "A=1 %command%", config_home=tmp_path)
    opj.definir(APPID, "B=2 %command%", config_home=tmp_path)
    assert opj.tirar("990000023", config_home=tmp_path) is True

    assert tabela.read_text(encoding="utf-8") == (
        f"# meu comentário\n\n{APPID}\tB=2 %command%\n# o último\n990000024\tA=1 %command%\n")
    assert len(_copias(tabela, "hefesto-tabela")) == 3


def _vdf_ilegivel(raiz: Path) -> tuple[Path, Path, bytes]:
    config = raiz / "config" / "config.vdf"
    torto = b"\xff" + config.read_bytes()
    config.write_bytes(torto)
    estado = raiz.parent / "estado.json"
    estado.write_text(
        '{"tool_name": "GE-Proton9-20", "changes": {"123": {"action": "added"}}}',
        encoding="utf-8")
    return config, estado, torto


def test_o_config_vdf_ilegivel_da_motivo_no_unlock_e_no_gesto_de_um_jogo(
        lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: o byte inválido vira motivo."""
    config, estado, torto = _vdf_ilegivel(_steam_de_verdade(lar))

    todos = pp.unlock_games_from_pinned_proton(config_vdf=config, state_path=estado)
    um = pp.destravar_um_jogo("123", config_vdf=config, state_path=estado)
    de_fora = pp.destravar_os_de_fora(config_vdf=config, state_path=estado, fora=["123"])

    for resultado in (todos, um):
        assert resultado["status"] == "erro"
        assert "UTF-8" in str(resultado["reason"]), resultado
    assert de_fora == []
    assert config.read_bytes() == torto
    assert pp.main(["--unlock", "--config-vdf", str(config), "--state", str(estado)]) == 1
    assert pp.main(["--report", "--config-vdf", str(config)]) == 0


def test_o_manter_com_o_config_vdf_ilegivel_diz_o_motivo_e_segue_para_as_sobras(
        lar: Path, conf: dict[str, str], tmp_path: Path,  # noqa: F811
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: o motivo vai ao diário e o resto roda."""
    raiz = _steam_de_verdade(lar)
    _pino_na(raiz)
    _jogo(raiz, "123")
    config, estado, torto = _vdf_ilegivel(raiz)
    arquivo_conf = tmp_path / "proton-pin.conf"
    arquivo_conf.write_text("".join(f"{k}={v}\n" for k, v in conf.items()), encoding="utf-8")
    PASSOS.clear()
    monkeypatch.setattr(pp, "apagar_as_sobras", _sobras)
    monkeypatch.setattr(pp, "_manter_os_lancadores", lambda *_a, **_k: PASSOS.append("lancadores"))

    rc = pp.main(["--manter", "--conf", str(arquivo_conf), "--state", str(estado)])

    assert rc == 0
    assert PASSOS == ["lancadores", "sobras"]
    assert "UTF-8" in capsys.readouterr().out
    assert config.read_bytes() == torto


def test_vinte_escritas_deixam_a_primeira_e_as_cinco_mais_novas(tmp_path: Path) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: a cópia de antes do Hefesto fica."""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text("v 0\n", encoding="utf-8")
    for n in range(1, 21):
        dono.escrever(vdf, f"v {n}\n", familia="hefesto-launch")

    copias = _copias(vdf, "hefesto-launch")
    lidas = [c.read_text(encoding="utf-8") for c in copias]
    assert lidas == ["v 0\n", *(f"v {n}\n" for n in range(15, 20))]
    assert vdf.read_text(encoding="utf-8") == "v 20\n"
    assert _restos(tmp_path) == []


def test_a_poda_conta_por_familia_exata_e_nao_por_prefixo(tmp_path: Path) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: steam-input não leva o ponte."""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text("v\n", encoding="utf-8")
    for n in range(1, 9):
        _planta(vdf, "steam-input-ponte", n)
        _planta(vdf, "steam-input-fora-da-lista", n)
    for n in range(1, 9):
        dono.escrever(vdf, f"v{n}\n", familia="steam-input")

    assert len(_copias(vdf, "steam-input")) == 6
    assert len(_copias(vdf, "steam-input-ponte")) == 8
    assert len(_copias(vdf, "steam-input-fora-da-lista")) == 8
    assert dono.podar(vdf) == 4
    assert len(_copias(vdf, "steam-input-ponte")) == 6
    assert len(_copias(vdf, "steam-input-fora-da-lista")) == 6


def test_o_install_poda_o_acumulado_numa_passada(lar: Path) -> None:  # noqa: F811
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: o acumulado de uma máquina vira seis."""
    raiz = _steam_de_verdade(lar)
    local = raiz / "userdata" / "1" / "config" / "localconfig.vdf"
    local.parent.mkdir(parents=True)
    local.write_text("v\n", encoding="utf-8")
    config = raiz / "config" / "config.vdf"
    for n in range(1, 31):
        _planta(local, "hefesto-launch", n)
        _planta(config, "hefesto-proton", n)
    _planta(local, "antes-de-eu-mexer", 1)

    assert pp.main(["--podar-as-copias"]) == 0

    assert len(_copias(local, "hefesto-launch")) == 6
    assert len(_copias(config, "hefesto-proton")) == 6
    assert (local.parent / "localconfig.vdf.bak.hefesto-launch-1").exists()
    assert (local.parent / "localconfig.vdf.bak.antes-de-eu-mexer-1").exists()


def test_a_troca_guarda_o_modo_e_a_leitura_diz_ausente_ou_motivo(tmp_path: Path) -> None:
    """D-1911-OS-ARQUIVOS-DOS-LANCADORES-TEM-UM-DONO-SO: o modo fica; ausente não é ilegível."""
    alvo = tmp_path / "config.vdf"
    alvo.write_text("a\r\nb\n", encoding="utf-8")
    alvo.chmod(0o640)

    dono.escrever(alvo, "c\r\nd\n", familia="hefesto-proton")

    assert stat.S_IMODE(alvo.stat().st_mode) == 0o640
    assert dono.ler(alvo).texto == "c\r\nd\n"
    assert dono.ler(tmp_path / "nao-ha").ausente
    assert not dono.ler(tmp_path / "nao-ha").ilegivel
    alvo.write_bytes(b"ok\xffok")
    torto = dono.ler(alvo)
    assert torto.texto is None and torto.ilegivel and "posição 2" in torto.motivo
    assert dono.ler(alvo, errors="replace").texto == "ok�ok"
    assert dono.ler(tmp_path).ilegivel
