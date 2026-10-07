"""A Steam e os lançadores sem arquivo interno: grava, RELÊ e só então dá por feito.

A-STEAM-E-OS-LANCADORES-SEM-ARQUIVO-INTERNO-01, 07/10/2026. O `localconfig.vdf` é da Steam, e ela
já apagou o wrapper de um jogo sem aviso (17/09). Gravar com `tmp.replace` e declarar o jogo
aplicado era dar por feito o que ninguém leu de volta; reabrir a Steam e dizer «reabriu» porque o
pedido saiu, o mesmo. Aqui a Steam é um dublê que DESFAZ o que o Hefesto grava (reescreve o arquivo
na troca), e o estado lido de volta é que decide.

Tudo em `tmp_path`: nenhum arquivo da Steam, nenhum processo dela, nenhum comando de verdade.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

_TAB = "\t"


def _vdf(launch_options: dict[str, str]) -> str:
    blocos = "".join(
        f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
        f'{_TAB * 6}"LaunchOptions"{_TAB * 2}"{valor}"\n'
        f"{_TAB * 5}}}\n"
        for appid, valor in launch_options.items()
    )
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f"{blocos}"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


@pytest.fixture()
def steam_fechada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)


@pytest.fixture()
def a_steam_desfaz(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A Steam reescreve o arquivo no instante da troca: o que o Hefesto gravou não fica.

    O dublê não é mais frouxo que o real: a gravação acontece de verdade (cópia, tmp, replace) e
    só o conteúdo que chega ao destino é o do «outro dono» (o texto de antes, sem o wrapper).
    """
    historico: list[str] = []
    troca = Path.replace

    def _replace(self: Path, alvo: str | Path) -> Path:
        if self.name.endswith(".hefesto-tmp"):
            destino = Path(alvo)
            historico.append(destino.name)
            self.write_text(destino.read_text(encoding="utf-8"), encoding="utf-8")
        return troca(self, alvo)

    monkeypatch.setattr(Path, "replace", _replace)
    return historico


def test_o_apply_que_a_steam_desfez_nao_vira_aplicado(
    tmp_path: Path, steam_fechada: None, a_steam_desfaz: list[str]
) -> None:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": "MANGOHUD=1 %command%"}), encoding="utf-8")

    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf])

    assert a_steam_desfaz, "o dublê da Steam nunca foi chamado: o teste não mede nada"
    assert resultado["applied"] == []
    assert [(e["appid"], e["reason"]) for e in resultado["errors"]] == [
        ("620", slo.MOTIVO_NAO_FIRMOU)
    ]


def test_o_apply_que_firmou_continua_aplicado(tmp_path: Path, steam_fechada: None) -> None:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": "MANGOHUD=1 %command%"}), encoding="utf-8")

    resultado = slo.apply_wrapper_to_all_games(vdfs=[vdf])

    assert [a["appid"] for a in resultado["applied"]] == ["620"]
    assert resultado["errors"] == []
    assert slo.nao_firmaram(vdf, ["620"], com_wrapper=True) == []


def test_o_relatorio_do_apply_nomeia_o_jogo_que_nao_firmou(
    tmp_path: Path,
    steam_fechada: None,
    a_steam_desfaz: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": "%command%"}), encoding="utf-8")

    rc = slo.main(["--apply", "--vdf", str(vdf)])

    saida = capsys.readouterr().out
    assert rc == 1
    assert "o jogo 620 não ficou como gravei" in saida


def test_o_atalho_que_a_steam_devolveu_nao_vira_removido(
    tmp_path: Path, steam_fechada: None
) -> None:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": slo._vdf_escape(slo.WRAPPER_LAUNCH)}), encoding="utf-8")
    original = vdf.read_text(encoding="utf-8")
    troca = Path.replace

    def _devolve(self: Path, alvo: str | Path) -> Path:
        if self.name.endswith(".hefesto-tmp"):
            self.write_text(original, encoding="utf-8")
        return troca(self, alvo)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Path, "replace", _devolve)
        resultado = slo.tirar_o_atalho_dos_jogos(["620"], vdfs=[vdf])

    assert resultado["removed"] == []
    assert [(e["appid"], e["reason"]) for e in resultado["errors"]] == [
        ("620", slo.MOTIVO_NAO_FIRMOU)
    ]


def test_o_atalho_tirado_e_lido_de_volta_como_tirado(tmp_path: Path, steam_fechada: None) -> None:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": slo._vdf_escape(slo.WRAPPER_LAUNCH)}), encoding="utf-8")

    resultado = slo.tirar_o_atalho_dos_jogos(["620"], vdfs=[vdf])

    assert [r["appid"] for r in resultado["removed"]] == ["620"]
    assert slo.nao_firmaram(vdf, ["620"], com_wrapper=False) == []


def test_o_migrate_que_a_steam_desfez_sai_como_erro(
    tmp_path: Path, a_steam_desfaz: list[str]
) -> None:
    veneno = f"{slo.IGNORE_SIGNATURE} %command%"
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": veneno}), encoding="utf-8")

    with pytest.raises(OSError, match=slo.MOTIVO_NAO_FIRMOU):
        slo.process_vdf(vdf, "migrate")


def test_o_migrate_que_firmou_devolve_o_que_mudou(tmp_path: Path) -> None:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": f"{slo.IGNORE_SIGNATURE} %command%"}), encoding="utf-8")

    mudadas, _ = slo.process_vdf(vdf, "migrate")

    assert mudadas == 1


class _Portas:
    """A Steam de mentira: cada porta que o produto bate pode ou não levantá-la."""

    def __init__(self, levanta: str | None) -> None:
        self.levanta = levanta
        self.batidas: list[list[str]] = []
        self.de_pe = False

    def abrir(self, cmd: list[str], **_k: object) -> None:
        self.batidas.append(list(cmd))
        if cmd[0] == self.levanta:
            self.de_pe = True


@pytest.fixture()
def portas_da_steam(monkeypatch: pytest.MonkeyPatch):
    def _monta(levanta: str | None) -> _Portas:
        portas = _Portas(levanta)
        monkeypatch.setattr(slo.shutil, "which", lambda n: f"/usr/bin/{n}")
        monkeypatch.setattr(slo.fora_do_servico, "abrir", portas.abrir)
        return portas

    return _monta


def test_reabrir_tenta_a_proxima_porta_quando_a_primeira_nao_levantou_a_steam(
    portas_da_steam,
) -> None:
    portas = portas_da_steam("xdg-open")

    voltou = slo.reopen_steam(de_pe=lambda: portas.de_pe, dormir=lambda _s: None, espera_s=2)

    assert voltou is True
    assert portas.batidas == [["steam"], ["xdg-open", "steam://open/main"]]


def test_reabrir_nao_bate_na_segunda_porta_quando_a_primeira_levantou(portas_da_steam) -> None:
    portas = portas_da_steam("steam")

    voltou = slo.reopen_steam(de_pe=lambda: portas.de_pe, dormir=lambda _s: None, espera_s=2)

    assert voltou is True
    assert portas.batidas == [["steam"]]


def test_reabrir_diz_que_nao_voltou_quando_nenhuma_porta_levanta_a_steam(portas_da_steam) -> None:
    portas = portas_da_steam(None)

    voltou = slo.reopen_steam(de_pe=lambda: portas.de_pe, dormir=lambda _s: None, espera_s=2)

    assert voltou is False
    assert len(portas.batidas) == 2


def test_reabrir_nao_espera_quando_a_steam_ja_esta_de_pe(portas_da_steam) -> None:
    portas_da_steam(None)
    esperas: list[float] = []

    voltou = slo.reopen_steam(de_pe=lambda: True, dormir=esperas.append, espera_s=30)

    assert voltou is True
    assert esperas == []


def _clicar_abrir_a_steam() -> str:
    """O gesto «Abrir o lançador» da 07 no cartão da Steam; devolve a recusa que ele diz."""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    with pytest.raises(RuntimeError) as erro:
        a07.abrir_lancador(None, {"gesto": desenho.ABRIR, "v": desenho.STEAM}, None)
    return str(erro.value)


def test_a_steam_pedida_que_nao_aparece_nao_vira_maquina_sem_steam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com a porta no PATH e a Steam sem ficar de pé, a frase não diz «não achei como abrir».

    O `False` do `reopen_steam` passou a ter duas causas quando ele começou a conferir a Steam de
    pé; a recusa da tela tem de dizer a que aconteceu. MORDIDA: volte o gesto à frase única.
    """
    monkeypatch.setattr(slo, "reopen_steam", lambda: False)
    monkeypatch.setattr(slo.shutil, "which", lambda n: f"/usr/bin/{n}")

    frase = _clicar_abrir_a_steam()

    assert "não achei" not in frase.lower(), frase
    assert "ainda não abriu" in frase and "nada foi alterado" in frase, frase


def test_a_maquina_sem_porta_nenhuma_diz_que_nao_achou(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(slo, "reopen_steam", lambda: False)
    monkeypatch.setattr(slo.shutil, "which", lambda _n: None)

    frase = _clicar_abrir_a_steam()

    assert frase.startswith("Não achei como abrir a Steam"), frase
    assert "nada foi alterado" in frase, frase
