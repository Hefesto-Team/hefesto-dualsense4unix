"""A cura do engasgo tem de ALCANÇAR os prefixos — todos, em todo disco."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

RAIZ = Path(__file__).resolve().parents[2]

_CABECALHO = "WINE REGISTRY Version 2\n;; All keys relative to REGISTRY\\\\Machine\n\n"


def _registro(*camadas: tuple[str, str]) -> str:
    """Monta um `system.reg` com o driver e as camadas pedidas."""
    linhas = [
        _CABECALHO,
        "[Software\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238072",
        '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000',
        "",
        "[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
    ]
    for caminho, valor in camadas:
        linhas.append(f'"{cv._escapar(caminho)}"=dword:{valor}')
    linhas.append("")
    return "\n".join(linhas)


def _monta_biblioteca(base: Path, appids: dict[str, str]) -> Path:
    """Cria `<base>/steamapps/compatdata/<appid>/pfx/system.reg`."""
    steamapps = base / "steamapps"
    for appid, texto in appids.items():
        pfx = steamapps / "compatdata" / appid / "pfx"
        pfx.mkdir(parents=True)
        (pfx / "system.reg").write_text(texto, encoding="utf-8")
    return steamapps


EPIC = r"C:\Program Files (x86)\Epic Games\EOSOverlayVkLayer-Win64.json"
MANGO = r"C:\windows\system32\VkLayer_MANGOHUD_x86_64.json"


@pytest.fixture()
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Duas bibliotecas Steam, como na máquina do usuário: a padrão e a de outro disco."""
    home = tmp_path / "home"
    outro_disco = tmp_path / "OutroDisco" / "SteamLibrary"
    padrao = home / ".steam" / "steam"
    _monta_biblioteca(
        padrao,
        {
            "111": _registro(),
            "222": _registro((EPIC, "00000000")),
        },
    )
    _monta_biblioteca(outro_disco, {"333": _registro((MANGO, "00000000"))})
    escapado = str(outro_disco).replace("\\", "\\\\")
    (padrao / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{escapado}"\n\t}}\n}}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return home


def test_o_censo_enxerga_a_biblioteca_do_outro_disco(casa: Path) -> None:
    """Sem o `libraryfolders.vdf`, a cura só pegaria metade dos jogos do usuário."""
    pastas = cv.pastas_compatdata(casa)
    assert len(pastas) == 2, f"esperava as duas bibliotecas, achei {pastas}"

    achados = {p.appid for p in cv.censo(casa, com_nomes=False)}
    assert achados == {"222", "333"}, (
        "o censo tem de trazer o jogo do outro disco e pular o prefixo sem "
        f"camada nenhuma; trouxe {achados}"
    )


def test_a_camada_preservada_nao_e_sobra_e_a_desconhecida_e(casa: Path) -> None:
    """MangoHud fica; o overlay desconhecido é candidato. A régua em uma linha."""
    por_appid = {p.appid: p for p in cv.censo(casa, com_nomes=False)}
    assert [c.nome_curto for c in por_appid["222"].sobras] == [
        "EOSOverlayVkLayer-Win64.json"
    ]
    assert por_appid["333"].sobras == ()
    assert por_appid["333"].camadas[0].preservada_por is not None


def test_curar_todos_mexe_no_desconhecido_e_deixa_o_preservado(casa: Path) -> None:
    antes_mango = (
        casa.parent / "OutroDisco" / "SteamLibrary" / "steamapps" / "compatdata"
        / "333" / "pfx" / "system.reg"
    ).read_bytes()

    resultados = {r.appid: r for r in cv.curar_todos(casa)}
    assert resultados["222"].desligadas == ("EOSOverlayVkLayer-Win64.json",)
    assert resultados["333"].desligadas == ()

    assert (
        casa.parent / "OutroDisco" / "SteamLibrary" / "steamapps" / "compatdata"
        / "333" / "pfx" / "system.reg"
    ).read_bytes() == antes_mango


def test_devolver_deixa_o_registro_byte_a_byte_como_estava(casa: Path) -> None:
    """Reversível SEM terminal é requisito dela — e reversível é byte a byte."""
    registro = (
        casa / ".steam" / "steam" / "steamapps" / "compatdata" / "222" / "pfx"
        / "system.reg"
    )
    antes = registro.read_bytes()

    cv.curar_todos(casa)
    assert registro.read_bytes() != antes

    cv.curar_todos(casa, religar=True)
    assert registro.read_bytes() == antes


def test_a_cura_e_idempotente(casa: Path) -> None:
    """Segundo clique (e segundo lançamento) não pode inventar trabalho."""
    cv.curar_todos(casa)
    de_novo = {r.appid: r for r in cv.curar_todos(casa)}
    assert de_novo["222"].desligadas == ()
    assert de_novo["222"].erro == ""


def test_o_gancho_nao_desfaz_o_que_ela_devolveu(casa: Path) -> None:
    """Ela devolveu de propósito: o jogo seguinte NÃO pode desligar de novo."""
    raiz = casa / ".steam" / "steam" / "steamapps" / "compatdata" / "222"
    cv.curar_todos(casa)
    cv.curar_todos(casa, religar=True)

    resultado = cv.curar_um_prefixo(raiz, appid="222", home=casa)
    assert resultado.desligadas == ()
    assert resultado.respeitadas == ("EOSOverlayVkLayer-Win64.json",)
    assert "dword:00000000" in (raiz / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_o_que_reapareceu_ligado_e_desligado_de_novo_pelo_gancho(casa: Path) -> None:
    """A camada voltou a `00000000` sem passar pelo botão: o gancho REFAZ a cura."""
    raiz = casa / ".steam" / "steam" / "steamapps" / "compatdata" / "222"
    registro = raiz / "pfx" / "system.reg"
    cv.curar_todos(casa)

    registro.write_text(
        registro.read_text(encoding="utf-8").replace("dword:00000001", "dword:00000000"),
        encoding="utf-8",
    )
    assert cv.curar_um_prefixo(raiz, appid="222", home=casa).desligadas == (
        "EOSOverlayVkLayer-Win64.json",
    )
    assert "dword:00000001" in registro.read_text(encoding="utf-8")


def test_o_botao_forca_e_vence_a_memoria(casa: Path) -> None:
    """A vontade da GUI prevalece (regra, 09/08/2026): clique explícito manda."""
    cv.curar_todos(casa)
    cv.curar_todos(casa, religar=True)
    de_novo = {r.appid: r for r in cv.curar_todos(casa, forcar=True)}
    assert de_novo["222"].desligadas == ("EOSOverlayVkLayer-Win64.json",)


def test_o_gancho_de_lancamento_chama_o_curador() -> None:
    """`hefesto-launch` roda em TODO jogo: é ele que cobre o jogo de amanhã."""
    texto = (RAIZ / "assets" / "hefesto-launch.sh").read_text(encoding="utf-8")
    assert "curar_camadas_vulkan" in texto
    assert re.search(r"^curar_camadas_vulkan \|\| true$", texto, re.MULTILINE), (
        "a chamada tem de existir E ser à prova de falha (`|| true`), como o "
        "`enter_game_mode` ao lado"
    )
    assert "STEAM_COMPAT_DATA_PATH" in texto
    assert "hefesto-camadas" in texto


def _path_sem_game_mode(base: Path) -> str:
    """O PATH do sistema com o Game Mode mudo na frente."""
    mudos = base / "game-mode-mudo"
    mudos.mkdir(exist_ok=True)
    for nome in ("system76-power", "busctl", "dbus-send"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    return f"{mudos}:/usr/bin:/bin"


def test_o_gancho_e_a_prova_de_falha_e_nao_atrasa_jogo_nativo(tmp_path: Path) -> None:
    """Sem prefixo Proton o gancho sai na primeira linha — e o jogo abre."""
    home = tmp_path / "home"
    home.mkdir()
    saida = subprocess.run(
        ["/bin/sh", str(RAIZ / "assets" / "hefesto-launch.sh"), "/bin/echo", "ABRIU"],
        env={
            "HOME": str(home),
            "PATH": _path_sem_game_mode(tmp_path),
            "XDG_STATE_HOME": str(tmp_path / "state"),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert saida.returncode == 0, saida.stderr
    assert "ABRIU" in saida.stdout


def test_o_gancho_cura_de_verdade_um_prefixo_e_o_jogo_abre(tmp_path: Path) -> None:
    """A prova de ponta a ponta: wrapper + curador materializado + prefixo real."""
    home = tmp_path / "home"
    config = home / ".config"
    cv.gravar_camadas_da_steam_fora(True, config_home=config)
    jogo = tmp_path / "common" / "Jogo"
    jogo.mkdir(parents=True)
    (jogo / "vulkan-1.dll").write_bytes(b"MZ")
    binario = home / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
    binario.mkdir(parents=True)
    alvo = binario / "hefesto-camadas"
    alvo.write_bytes(
        (RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "camadas_vulkan.py")
        .read_bytes()
    )
    alvo.chmod(0o755)

    prefixo = tmp_path / "compatdata" / "222"
    (prefixo / "pfx").mkdir(parents=True)
    registro = prefixo / "pfx" / "system.reg"
    registro.write_text(_registro((EPIC, "00000000")), encoding="utf-8")

    saida = subprocess.run(
        ["/bin/sh", str(RAIZ / "assets" / "hefesto-launch.sh"), "/bin/echo", "ABRIU"],
        env={
            "HOME": str(home),
            "PATH": _path_sem_game_mode(tmp_path),
            "XDG_CONFIG_HOME": str(config),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "SteamAppId": "222",
            "STEAM_COMPAT_DATA_PATH": str(prefixo),
            "STEAM_COMPAT_INSTALL_PATH": str(jogo),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert saida.returncode == 0, saida.stderr
    assert "ABRIU" in saida.stdout

    texto = registro.read_text(encoding="utf-8")
    assert "EOSOverlayVkLayer-Win64.json\"=dword:00000001" in texto, (
        "o gancho não desligou a camada — a cura não alcança o lançamento"
    )
    assert '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000' in texto


def test_a_copia_avulsa_nao_finge_que_olhou(tmp_path: Path) -> None:
    """A cópia instalada não alcança o irmão — e tem de DIZER isso."""
    avulso = tmp_path / "bin" / "hefesto-camadas"
    avulso.parent.mkdir(parents=True)
    fonte = RAIZ / "src/hefesto_dualsense4unix/integrations/camadas_vulkan.py"
    avulso.write_bytes(fonte.read_bytes())

    ambiente = dict(os.environ)
    ambiente.pop("PYTHONPATH", None)
    saida = subprocess.run(
        ["python3", str(avulso), "--relatorio"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        env=ambiente,
    )
    assert saida.returncode != 0, (
        "a cópia avulsa não sabe listar jogos e mesmo assim saiu com sucesso — "
        f"quem chamou vai ler isso como 'está tudo limpo'. saída: {saida.stdout!r}"
    )
    assert "nenhum prefixo" not in saida.stdout, (
        "a cópia avulsa afirmou que não há camada nenhuma sem ter conseguido "
        "olhar — é o instrumento mentindo"
    )
    assert "não consegue listar os jogos" in saida.stderr


def _bloco_do_install(nome: str = "CAMADAS_SRC") -> str:
    """Recorta do `install.sh` o bloco que materializa o curador."""
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = re.search(rf"^readonly {re.escape(nome)}=", texto, re.MULTILINE)
    assert inicio is not None, f"bloco {nome} não encontrado no install.sh"
    fim = re.search(r"^fi\n", texto[inicio.start() :], re.MULTILINE)
    assert fim is not None, f"fim do bloco {nome} não encontrado"
    return texto[inicio.start() : inicio.start() + fim.end()]


def test_o_install_materializa_o_curador_sem_flag(tmp_path: Path) -> None:
    """Toda cura entra no install, sem flag (regra da casa, 08/08/2026)."""
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    for flag in ("--camadas", "--no-camadas", "--vulkan"):
        assert flag not in texto, f"a cura ganhou uma flag ({flag}) — não pode"

    casa = tmp_path / "casa"
    casa.mkdir()
    roteiro = (
        "set -euo pipefail\n"
        "warn() { echo \"WARN: $*\" >&2; }\n"
        f'ROOT_DIR="{RAIZ}"\n'
        f'HOME="{casa}"\n'
        f"{_bloco_do_install()}\n"
    )
    saida = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, timeout=60
    )
    assert saida.returncode == 0, saida.stderr

    alvo = casa / ".local/share/hefesto-dualsense4unix/bin/hefesto-camadas"
    assert alvo.is_file(), (
        "o install rodou e o curador não apareceu no HOME — a cura não entra "
        f"no install. stderr: {saida.stderr}"
    )
    assert os.access(alvo, os.X_OK), "o curador entrou sem bit de execução"
    fonte = RAIZ / "src/hefesto_dualsense4unix/integrations/camadas_vulkan.py"
    assert alvo.read_bytes() == fonte.read_bytes(), (
        "a cópia instalada divergiu da fonte — a fonte da verdade tem de ser UMA"
    )
    assert "WARN:" not in saida.stderr

    alvo.write_text("velho\n", encoding="utf-8")
    de_novo = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, timeout=60
    )
    assert de_novo.returncode == 0, de_novo.stderr
    assert alvo.read_bytes() == fonte.read_bytes()


def test_o_uninstall_devolve_antes_de_apagar_o_curador() -> None:
    """Simetria: o que mexemos no dado dela volta, e volta ANTES do curador sair."""
    texto = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    devolucao = texto.index("--devolver")
    remocao = texto.index('rm -f "${CAMADAS_TARGET}"')
    assert devolucao < remocao, (
        "o uninstall apagaria o curador antes de devolver as sobreposições — "
        "ela ficaria sem produto E sem as camadas"
    )
