"""JOGO-COMPLETO-01 / E4: o `--apply` do CLI e o passo do install SEM FLAG.



O buraco medido em 02/08, com o install inteiro já rodado nesta máquina: o
`--status` dizia **"veneno estático: 0 / chamadas do wrapper: 0"** e o doctor
avisava "NENHUM jogo com o wrapper nas LaunchOptions". A causa é que o passo
11b do install só roda `--migrate`, que MIGRA veneno legado — numa instalação
limpa não há veneno, então ele não põe nada, as envs do projeto nunca são
exportadas e **todo jogo enxerga dois DualSense**.

Este arquivo trava o modo que fecha o buraco (aplica; é idempotente; recusa
com a Steam ou um jogo aberto; `--dry-run` não escreve), o passo do install
que o chama sem flag, e a SIMETRIA com o `--strip` do uninstall.

Tudo com FIXTURES em `tmp_path` — nenhum localconfig.vdf real é tocado.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

_TAB = "\t"

LINHA_914 = (
    "SDL_JOYSTICK_HIDAPI=0 SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6 "
    "__GL_SHADER_DISK_CACHE=1 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%"
)


def _vdf(launch_options: dict[str, str], sem_launch_options: tuple[str, ...] = ()) -> str:
    """localconfig.vdf mínimo: um app por appid, com ou sem LaunchOptions."""
    blocos = []
    for appid, valor in launch_options.items():
        blocos.append(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f'{_TAB * 6}"LaunchOptions"{_TAB * 2}"{valor}"\n'
            f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * 5}}}\n"
        )
    for appid in sem_launch_options:
        blocos.append(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * 5}}}\n"
        )
    apps = "".join(blocos)
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f"{apps}"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


@pytest.fixture()
def steam_fechada(monkeypatch):
    """A Steam e os jogos fechados — o único estado em que se edita o vdf."""
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)


def test_apply_poe_o_wrapper_em_todo_jogo_inclusive_no_que_nunca_teve_opcoes(
    tmp_path: Path, steam_fechada, capsys
):
    """O defeito da E4 em uma linha: com `--migrate`, o jogo 1599660 (sem"""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(
        _vdf({"620": "MANGOHUD=1 %command%"}, sem_launch_options=("1599660",)),
        encoding="utf-8",
    )

    rc = slo.main(["--apply", "--vdf", str(vdf)])

    assert rc == 0
    valores = slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))
    assert valores["1599660"] == slo.WRAPPER_LAUNCH
    assert valores["620"] == f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"
    out = capsys.readouterr().out
    assert "wrapper aplicado a 2 jogos" in out
    assert len(list(tmp_path.glob("localconfig.vdf.bak.hefesto-launch-*"))) == 1


def test_apply_e_idempotente_rodar_duas_vezes_nao_duplica(
    tmp_path: Path, steam_fechada, capsys
):
    """Requisito dela, palavra por palavra: idempotente. O install roda sem"""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(
        _vdf({"620": "MANGOHUD=1 %command%"}, sem_launch_options=("1599660",)),
        encoding="utf-8",
    )

    assert slo.main(["--apply", "--vdf", str(vdf)]) == 0
    depois_da_primeira = vdf.read_text(encoding="utf-8")
    capsys.readouterr()

    assert slo.main(["--apply", "--vdf", str(vdf)]) == 0
    depois_da_segunda = vdf.read_text(encoding="utf-8")

    assert depois_da_segunda == depois_da_primeira
    escapado = slo._vdf_escape(slo.WRAPPER_PREFIX)
    assert depois_da_segunda.count(escapado) == 2
    assert len(list(tmp_path.glob("localconfig.vdf.bak.hefesto-launch-*"))) == 1
    out = capsys.readouterr().out
    assert "nada a fazer" in out
    assert "ja_tem_wrapper" in out


def test_apply_remove_o_veneno_legado_no_mesmo_passo(tmp_path: Path, steam_fechada):
    """Quem tinha a linha 914 sai dela DIRETO para o wrapper (o `--apply` usa o"""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"1599660": LINHA_914}), encoding="utf-8")

    assert slo.main(["--apply", "--vdf", str(vdf)]) == 0

    texto = vdf.read_text(encoding="utf-8")
    assert slo.IGNORE_SIGNATURE not in texto
    assert slo.read_launch_options_by_appid(texto)["1599660"] == slo.WRAPPER_LAUNCH


def test_apply_recusa_com_a_steam_aberta(tmp_path: Path, monkeypatch, capsys):
    """Editar com a Steam viva é edição PERDIDA: ela regrava o vdf ao sair."""
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"620": "MANGOHUD=1 %command%"})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)

    rc = slo.main(["--apply", "--vdf", str(vdf)])

    assert rc == 3
    assert vdf.read_text(encoding="utf-8") == original
    out = capsys.readouterr().out
    assert "Steam está aberta" in out
    assert list(tmp_path.glob("*.bak.*")) == []


def test_apply_recusa_com_jogo_aberto_e_nao_derruba_a_steam(
    tmp_path: Path, monkeypatch, capsys
):
    """`steam -shutdown` com jogo aberto MATA o jogo (progresso não salvo"""
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"620": ""}, sem_launch_options=("1599660",))
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: True)
    parou: list[bool] = []
    monkeypatch.setattr(slo, "stop_steam", lambda: parou.append(True) or True)

    for args in (
        ["--apply", "--vdf", str(vdf)],
        ["--apply", "--stop-steam", "--vdf", str(vdf)],
    ):
        assert slo.main(args) == 3, args
        assert vdf.read_text(encoding="utf-8") == original

    assert parou == []
    out = capsys.readouterr().out
    assert "JOGO" in out
    assert "MATARIA" in out


def test_apply_tem_segunda_muralha_quando_o_stop_steam_mente(
    tmp_path: Path, monkeypatch, capsys
):
    """`stop_steam()` pode voltar True sem ter fechado (pkill que não pegou).
    O gate de dentro do `apply_wrapper_to_all_games` é a segunda muralha: em
    vez de escrever num vdf que a Steam vai regravar, recusa com rc=3."""
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"620": "MANGOHUD=1 %command%"})
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "stop_steam", lambda: True)
    monkeypatch.setattr(slo, "reopen_steam", lambda: None)

    rc = slo.main(["--apply", "--stop-steam", "--vdf", str(vdf)])

    assert rc == 3
    assert vdf.read_text(encoding="utf-8") == original
    assert "Steam está aberta" in capsys.readouterr().out


def test_apply_com_stop_steam_fecha_aplica_e_reabre(
    tmp_path: Path, monkeypatch
):
    """O caminho EXATO do install (`--apply --stop-steam`): quem fechou a"""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": "MANGOHUD=1 %command%"}), encoding="utf-8")
    estado = {"viva": True}
    eventos: list[str] = []

    def _fechar() -> bool:
        eventos.append("fechou")
        estado["viva"] = False
        return True

    monkeypatch.setattr(slo, "steam_running", lambda: estado["viva"])
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "stop_steam", _fechar)
    monkeypatch.setattr(slo, "reopen_steam", lambda: eventos.append("reabriu"))

    rc = slo.main(["--apply", "--stop-steam", "--vdf", str(vdf)])

    assert rc == 0
    assert eventos == ["fechou", "reabriu"]
    valores = slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))
    assert valores["620"] == f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%"


def test_apply_nao_reabre_uma_steam_que_ja_estava_fechada(
    tmp_path: Path, steam_fechada, monkeypatch
):
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": ""}), encoding="utf-8")
    eventos: list[str] = []
    monkeypatch.setattr(slo, "reopen_steam", lambda: eventos.append("reabriu"))

    assert slo.main(["--apply", "--stop-steam", "--vdf", str(vdf)]) == 0

    assert eventos == []


def test_apply_dry_run_nao_escreve_nada(tmp_path: Path, monkeypatch, capsys):
    vdf = tmp_path / "localconfig.vdf"
    original = _vdf({"620": "MANGOHUD=1 %command%"}, sem_launch_options=("1599660",))
    vdf.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        slo, "steam_running", lambda: (_ for _ in ()).throw(AssertionError)
    )
    monkeypatch.setattr(
        slo, "steam_game_running", lambda: (_ for _ in ()).throw(AssertionError)
    )

    rc = slo.main(["--apply", "--dry-run", "--vdf", str(vdf)])

    assert rc == 0
    assert vdf.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.bak.*")) == []
    out = capsys.readouterr().out
    assert "--dry-run: 2 jogos receberiam o wrapper" in out
    assert "nada foi escrito" in out


def test_apply_pula_o_vdf_de_sandbox_inteiro(tmp_path: Path, steam_fechada, capsys):
    """Steam Flatpak/Snap: o wrapper do host é invisível lá dentro (DEDUP-04) —"""
    sandbox = (
        tmp_path / ".var/app/com.valvesoftware.Steam/.steam/steam/userdata"
        / "12345678/config"
    )
    sandbox.mkdir(parents=True)
    vdf = sandbox / "localconfig.vdf"
    original = _vdf({"620": ""})
    vdf.write_text(original, encoding="utf-8")

    rc = slo.main(["--apply", "--vdf", str(vdf)])

    assert rc == 0
    assert vdf.read_text(encoding="utf-8") == original
    out = capsys.readouterr().out
    assert "sandbox" in out
    assert "nada a fazer" in out


def test_apply_erro_por_vdf_nao_aborta_os_demais(tmp_path: Path, steam_fechada, capsys):
    """Um localconfig.vdf não-UTF-8 (multi-usuário, byte latin-1 legado) vira"""
    ruim = tmp_path / "ruim" / "localconfig.vdf"
    ruim.parent.mkdir()
    ruim.write_bytes(b'"UserLocalConfigStore"\n{\n\xff byte invalido\n}\n')
    bom = tmp_path / "bom" / "localconfig.vdf"
    bom.parent.mkdir()
    bom.write_text(_vdf({"620": "MANGOHUD=1 %command%"}), encoding="utf-8")

    rc = slo.main(["--apply", "--vdf", str(ruim), "--vdf", str(bom)])

    assert rc == 1
    assert "ERRO" in capsys.readouterr().out
    valores = slo.read_launch_options_by_appid(bom.read_text(encoding="utf-8"))
    assert valores["620"].startswith(slo.WRAPPER_PREFIX)


def test_apply_e_mutuamente_exclusivo_com_migrate_e_strip(tmp_path: Path):
    """Um modo por vez: `--apply --strip` na mesma linha seria ambíguo (põe ou"""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_vdf({"620": ""}), encoding="utf-8")
    for args in (
        ["--apply", "--migrate", "--vdf", str(vdf)],
        ["--apply", "--strip", "--vdf", str(vdf)],
        ["--apply", "--status", "--vdf", str(vdf)],
    ):
        with pytest.raises(SystemExit) as exc:
            slo.main(args)
        assert exc.value.code == 2, args


def _raiz() -> Path:
    return Path(__file__).resolve().parents[2]


def test_install_aplica_o_wrapper_sem_flag_e_depois_da_migracao():
    """E4: o passo entra no install.sh SEM FLAG, depois da migração (11b) e"""
    texto = (_raiz() / "install.sh").read_text(encoding="utf-8")

    assert 'step "11b-bis"' in texto
    pos_apply = texto.index("--apply --stop-steam")
    assert pos_apply > texto.index("--migrate --stop-steam")
    assert pos_apply > texto.index('install -Dm755 "${LAUNCH_WRAPPER_SRC}"')

    corpo = texto[texto.index('step "11b-bis"'): texto.index('step "11c"')]
    for opt_out in ("KEEP_STEAM_INPUT", "NO_PROTON_PIN", "SKIP_UDEV", "NO_DKMS"):
        assert opt_out not in corpo, opt_out
    assert "warn " in corpo


def test_install_liga_o_broker_antes_mas_o_hide_e_em_tempo_de_jogo():
    """Armadilha 1 da sprint ("não ligar o broker antes do wrapper"): o passo"""
    texto = (_raiz() / "install.sh").read_text(encoding="utf-8")
    corpo = texto[texto.index("# 11b-bis."): texto.index('step "11b-bis"')]
    assert "3h" in corpo
    assert "vpad" in corpo


def test_uninstall_tira_exatamente_o_que_o_apply_pos(tmp_path: Path, steam_fechada):
    """Simetria (regra da casa): tudo que o install põe, o uninstall tira. O"""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(
        _vdf({"620": "MANGOHUD=1 %command%"}, sem_launch_options=("1599660",)),
        encoding="utf-8",
    )

    assert slo.main(["--apply", "--vdf", str(vdf)]) == 0
    assert slo._vdf_escape(slo.WRAPPER_PREFIX) in vdf.read_text(encoding="utf-8")

    assert slo.main(["--strip", "--vdf", str(vdf)]) == 0

    texto = vdf.read_text(encoding="utf-8")
    assert slo.WRAPPER_PREFIX not in texto
    assert slo._vdf_escape(slo.WRAPPER_PREFIX) not in texto
    valores = slo.read_launch_options_by_appid(texto)
    assert valores["620"] == "MANGOHUD=1 %command%"
    assert valores["1599660"] == ""

    uninstall = (_raiz() / "uninstall.sh").read_text(encoding="utf-8")
    assert "--strip --stop-steam" in uninstall
