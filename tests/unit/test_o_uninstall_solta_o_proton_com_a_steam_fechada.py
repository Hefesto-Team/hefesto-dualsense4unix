"""O-UNINSTALL-SOLTA-O-PROTON-COM-A-STEAM-FECHADA-01: a Steam fecha uma vez e o Proton se solta.

O uninstall mexia nos arquivos da Steam em três passos, cada um com a própria janela: o primeiro
fechava e reabria a Steam, o destravamento do Proton caía com a Steam aberta (rc 3, adiado) e o
terceiro fechava a Steam de novo. Agora o dono da janela única é
``scripts/lib/a_steam_fechada_uma_vez.sh``, o mesmo do install: fecha uma vez antes dos três passos,
reabre no fim, e o que adiar vira pendência no resumo.

O uninstall roda DE VERDADE no lar de mentira de ``test_o_uninstall_nao_deixa_rastro`` (HOME e
XDG desviados, guarda que sai se vazar, comandos que mudam a máquina viram dublês). A Steam de
mentira é a tabela de processos do lar: fechar apaga a Steam da tabela e abrir a devolve, e cada
gesto vai ao diário. O ``disable_steam_input.sh`` é um dublê que cumpre o contrato do script (se a
Steam está aberta, fecha e reabre; com jogo aberto, recusa), porque o ``bash`` do lar é um dublê.

A MORDIDA (feita na sprint, com a cura devolvida): o uninstall sem a janela única (a ordem de
antes) reprova os dois primeiros testes, e a última linha sem a conta das pendências reprova o
terceiro.
"""
from __future__ import annotations

import re
import shutil
import stat
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin
from tests.unit import test_o_uninstall_nao_deixa_rastro as base

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
LIB = RAIZ / "scripts" / "lib" / "a_steam_fechada_uma_vez.sh"
PINO = proton_pin.parse_pin_conf(
    (RAIZ / "assets" / "proton-pin.conf").read_text(encoding="utf-8"))["name"]

A_STEAM = {4244: "/lar/.local/share/Steam/ubuntu12_64/steamrt64/steam -silent"}
A_STEAM_COM_JOGO = {**A_STEAM, 4243: "reaper SteamLaunch AppId=9900100 -- /lar/jogo/jogo.exe"}

GESTOS_DA_STEAM = '''
import json, sys

TABELA = {tabela!r}
DIARIO = {diario!r}


def _anota(texto):
    with open(DIARIO, "a", encoding="utf-8") as d:
        d.write(texto + "\\n")


def _linhas():
    return {{int(k): v for k, v in json.load(open(TABELA, encoding="utf-8")).items()}}


def _grava(linhas):
    json.dump({{str(k): v for k, v in linhas.items()}}, open(TABELA, "w", encoding="utf-8"))


def _da_steam(cmd):
    return "steamrt64/steam" in cmd or "steamwebhelper" in cmd


def fechar():
    linhas = _linhas()
    _anota("STEAM fechou")
    _grava({{k: v for k, v in linhas.items() if not _da_steam(v)}})
    return {{k: v for k, v in linhas.items() if _da_steam(v)}}


def abrir(saidas):
    _anota("STEAM abriu")
    _grava({{**_linhas(), **saidas}})


def disable_steam_input(argv):
    _anota("bash " + " ".join(argv))
    linhas = _linhas()
    if any("SteamLaunch" in v for v in linhas.values()):
        _anota("disable_steam_input recusou: jogo aberto")
        return 4
    if any(_da_steam(v) for v in linhas.values()):
        abrir(fechar())
    return 0


if __name__ == "__main__":
    sys.exit(disable_steam_input(sys.argv[1:]))
'''

RECORDADOR = '''def _fechar_a_steam_do_lar():
    saidas = gestos.fechar()
    PROCESSOS.clear()
    PROCESSOS.update({k: v for k, v in gestos._linhas().items()})
    return True
def _abrir_a_steam_do_lar():
    gestos.abrir({4244: PROCESSOS_DE_ANTES})
    PROCESSOS.update(gestos._linhas())
    return True
slo.stop_steam = _fechar_a_steam_do_lar
slo.reopen_steam = _abrir_a_steam_do_lar
'''


@pytest.fixture(autouse=True)
def _as_extensoes_de_caixa_ligadas(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.as_caixas_das_extensoes import ligar

    ligar(monkeypatch)


@pytest.fixture(autouse=True)
def _a_steam_de_mentira(monkeypatch: pytest.MonkeyPatch) -> None:
    original = base._montar_o_path

    def montar(raiz: Path, diario: Path, processos: dict[int, str] | None = None) -> Path:
        binp = original(raiz, diario, processos)
        (raiz / "gestos_da_steam.py").write_text(
            GESTOS_DA_STEAM.format(tabela=str(raiz / "processos.json"), diario=str(diario)),
            encoding="utf-8")
        partida = raiz / "py_guardado.py"
        texto = partida.read_text(encoding="utf-8")
        alvo = "slo.stop_steam = _recusa\n"
        assert alvo in texto, "o lar de mentira mudou de forma"
        recordador = RECORDADOR.replace("PROCESSOS_DE_ANTES", repr(A_STEAM[4244]))
        entrada = f"sys.path.insert(0, {str(raiz)!r})\nimport gestos_da_steam as gestos\n"
        partida.write_text(texto.replace(alvo, entrada + recordador), encoding="utf-8")
        real_py = shutil.which("python3", path=base.SISTEMA)
        assert real_py, "sem python3 no sistema"
        (binp / "bash").write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            f'  */disable_steam_input.sh) exec "{real_py}" "{raiz / "gestos_da_steam.py"}" "$@";;\n'
            "esac\n"
            f'printf "%s\\n" "bash $*" >> "{diario}"\nexit 0\n', encoding="utf-8")
        (binp / "bash").chmod((binp / "bash").stat().st_mode | stat.S_IXUSR)
        return binp

    monkeypatch.setattr(base, "_montar_o_path", montar)


def _desinstalar(tmp_path: Path, processos: dict[int, str]) -> tuple[str, str, Path]:
    """Roda o uninstall: devolve a saída, o diário e o config.vdf da Steam do lar."""
    r, repo = base._casa_de_mentira(tmp_path, xdg_fora=False)
    base._instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)
    rodou, diario = base._desinstalar(
        tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"), xdg_fora=False,
        processos=processos)
    assert rodou.returncode == 0, rodou.stdout[-3000:] + rodou.stderr[-3000:]
    assert "RECUSADO" not in diario, diario
    return rodou.stdout, diario, r.lar / ".steam/steam/config/config.vdf"


def _gestos(diario: str) -> list[str]:
    return [x for x in diario.splitlines() if x.startswith("STEAM ")]


def test_a_steam_aberta_fecha_uma_vez_solta_o_proton_e_reabre_no_fim(tmp_path: Path) -> None:
    """D-2011-O-UNINSTALL-FECHA-A-STEAM-UMA-VEZ: fecha uma vez, solta o Proton e reabre no fim."""
    saida, diario, config_vdf = _desinstalar(tmp_path, A_STEAM)

    assert _gestos(diario) == ["STEAM fechou", "STEAM abriu"], diario
    assert PINO not in config_vdf.read_text(encoding="utf-8"), (
        "o Proton que o Hefesto fixou segue nos jogos depois do uninstall")
    assert "ADIADO" not in saida, saida[-3000:]
    assert "desinstalado (wipe completo)" in saida
    ordem = diario.splitlines()
    assert ordem.index("STEAM fechou") < next(
        i for i, x in enumerate(ordem) if "disable_steam_input.sh --apply" in x)
    assert ordem.index("STEAM abriu") > next(
        i for i, x in enumerate(ordem) if "--strip --stop-steam" in x)


def test_com_jogo_aberto_nada_fecha_e_o_resumo_traz_a_pendencia(tmp_path: Path) -> None:
    saida, diario, config_vdf = _desinstalar(tmp_path, A_STEAM_COM_JOGO)

    assert _gestos(diario) == [], diario
    assert PINO in config_vdf.read_text(encoding="utf-8")
    assert "wipe completo" not in saida
    assert "desinstalado, com pendência na Steam" in saida
    pendencias = re.findall(r"^   python3 (\S+) (--\S+)$", saida, re.M)
    assert [(Path(arquivo).name, verbo) for arquivo, verbo in pendencias] == [
        ("proton_pin.py", "--unlock"), ("steam_launch_options.py", "--strip")], saida[-1500:]


def test_o_dono_da_janela_e_a_lib_dos_dois_roteiros() -> None:
    uninstall = UNINSTALL.read_text(encoding="utf-8")
    install = (RAIZ / "install.sh").read_text(encoding="utf-8")
    lib = LIB.read_text(encoding="utf-8")
    for texto in (install, uninstall):
        assert 'source "${ROOT_DIR}/scripts/lib/a_steam_fechada_uma_vez.sh"' in texto
        assert texto.count("fechar_a_steam_uma_vez") == 1
        assert '--fechar-steam' not in texto
    assert lib.count("--fechar-steam") == 1 and lib.count("--reabrir-steam") == 1
    janela = uninstall.index("\nfechar_a_steam_uma_vez\n")
    fim = uninstall.index("\nreabrir_a_steam_se_fechei\n")
    reabre_se_morrer = uninstall.index(
        "trap '_cleanup_sudo_keepalive; reabrir_a_steam_se_fechei' EXIT\n")
    assert reabre_se_morrer < janela < fim < uninstall.index(
        "\ntrap _cleanup_sudo_keepalive EXIT\n", fim)
    for passo in ('bash "${DISABLE_STEAM_INPUT_SCRIPT}" --apply',
                  'python3 "${PROTON_PIN_PY}" --unlock',
                  'python3 "${LAUNCH_STRIP_PY}" --strip --stop-steam'):
        assert janela < uninstall.index(passo) < fim, passo
