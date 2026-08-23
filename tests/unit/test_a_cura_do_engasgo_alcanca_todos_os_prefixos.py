"""A cura do engasgo tem de ALCANÇAR os prefixos — todos, em todo disco.

ENGASGO-VULKAN-01 (23/08/2026). O defeito que este portão existe para impedir é
o mesmo de sempre nesta casa: a cura escrita e nunca ligada, ou ligada só onde é
fácil. `compatdata` não mora num lugar só — nesta máquina são DOIS, e o segundo
(`/mnt/Mnemosyne/SteamLibrary`) só aparece pelo `libraryfolders.vdf`.

Morde em quatro alturas:

1. **alcance** — o censo enxerga as duas bibliotecas, não só a padrão;
2. **reversibilidade** — devolver deixa o registro byte a byte como estava;
3. **memória da escolha dela** — o que ela religou não é desligado de novo no
   lançamento seguinte;
4. **fiação** — o gancho de lançamento, o install e o uninstall chamam mesmo o
   curador; sem isto a cura existe e nunca roda em jogo nenhum.
"""
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
    """Monta um `system.reg` com o driver e as camadas pedidas.

    `camadas` são pares `(caminho_windows, dword)`. O driver entra SEMPRE, na
    chave dele, porque é assim no real e porque nenhum teste daqui pode rodar
    contra um registro mais fácil que o da máquina dela.
    """
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
    """Duas bibliotecas Steam, como na máquina dela: a padrão e a de outro disco."""
    home = tmp_path / "home"
    outro_disco = tmp_path / "OutroDisco" / "SteamLibrary"
    padrao = home / ".steam" / "steam"
    _monta_biblioteca(
        padrao,
        {
            "111": _registro(),  # jogo sem camada nenhuma
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


# ---------------------------------------------------------------------------
# 1. Alcance
# ---------------------------------------------------------------------------


def test_o_censo_enxerga_a_biblioteca_do_outro_disco(casa: Path) -> None:
    """Sem o `libraryfolders.vdf`, a cura só pegaria metade dos jogos dela."""
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


# ---------------------------------------------------------------------------
# 2. Reversibilidade
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 3. A escolha dela sobrevive ao próximo lançamento
# ---------------------------------------------------------------------------


def test_o_gancho_nao_desfaz_o_que_ela_devolveu(casa: Path) -> None:
    """Ela devolveu de propósito: o jogo seguinte NÃO pode desligar de novo."""
    raiz = casa / ".steam" / "steam" / "steamapps" / "compatdata" / "222"
    cv.curar_todos(casa)
    cv.curar_todos(casa, religar=True)

    # O gancho de lançamento passa por aqui, e nunca força.
    resultado = cv.curar_um_prefixo(raiz, appid="222", home=casa)
    assert resultado.desligadas == ()
    assert resultado.respeitadas == ("EOSOverlayVkLayer-Win64.json",)
    assert "dword:00000000" in (raiz / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_religar_por_fora_tambem_conta_como_escolha(casa: Path) -> None:
    """Editou o registro à mão? Isso é escolha, não é convite para briga."""
    raiz = casa / ".steam" / "steam" / "steamapps" / "compatdata" / "222"
    registro = raiz / "pfx" / "system.reg"
    cv.curar_todos(casa)

    # "Ela" religou por fora, sem passar pelo produto.
    registro.write_text(
        registro.read_text(encoding="utf-8").replace("dword:00000001", "dword:00000000"),
        encoding="utf-8",
    )
    assert cv.curar_um_prefixo(raiz, appid="222", home=casa).desligadas == ()
    assert "dword:00000000" in registro.read_text(encoding="utf-8")


def test_o_botao_forca_e_vence_a_memoria(casa: Path) -> None:
    """A vontade da GUI prevalece (regra dela, 09/08/2026): clique explícito manda."""
    cv.curar_todos(casa)
    cv.curar_todos(casa, religar=True)
    de_novo = {r.appid: r for r in cv.curar_todos(casa, forcar=True)}
    assert de_novo["222"].desligadas == ("EOSOverlayVkLayer-Win64.json",)


# ---------------------------------------------------------------------------
# 4. Fiação — a cura escrita e nunca ligada é o defeito mais caro desta casa
# ---------------------------------------------------------------------------


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


def test_o_gancho_e_a_prova_de_falha_e_nao_atrasa_jogo_nativo(tmp_path: Path) -> None:
    """Sem prefixo Proton o gancho sai na primeira linha — e o jogo abre.

    Roda o wrapper DE VERDADE com um HOME de mentira: sem
    `STEAM_COMPAT_DATA_PATH` (jogo nativo) e sem curador instalado, o comando
    final tem de executar mesmo assim.
    """
    home = tmp_path / "home"
    home.mkdir()
    saida = subprocess.run(
        ["/bin/sh", str(RAIZ / "assets" / "hefesto-launch.sh"), "/bin/echo", "ABRIU"],
        env={
            "HOME": str(home),
            "PATH": "/usr/bin:/bin",
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
    """A prova de ponta a ponta: wrapper + curador materializado + prefixo real.

    Reproduz o que o `install.sh` monta: o curador em
    `~/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas`, executável.
    """
    home = tmp_path / "home"
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
            "PATH": "/usr/bin:/bin",
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "SteamAppId": "222",
            "STEAM_COMPAT_DATA_PATH": str(prefixo),
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
    """A cópia instalada não alcança o irmão — e tem de DIZER isso.

    Medido em 23/08/2026: instalada em `bin/hefesto-camadas`, longe do pacote,
    a CLI respondia *"nenhum prefixo com camada Vulkan implícita registrada"* —
    quando a verdade era que ela não conseguiu abrir a lista de jogos. É a
    armadilha número um desta casa (*o instrumento mente mais que o produto*):
    "não achei" e "não consegui olhar" dão a mesma lista vazia, e só o primeiro
    é notícia boa.

    O modo `--prefixo`, que é o do gancho de lançamento, continua inteiro:
    ele recebe o caminho pronto e nunca enumera.
    """
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
    """Recorta do `install.sh` o bloco que materializa o curador.

    Padrão da casa para lógica de `sh` (`test_install_broker_step.py`): não se
    confere um passo de instalação por `grep` — recorta-se e RODA-SE com bash
    de verdade. Aprendido na mordida desta leva: a versão só-texto deste teste
    passava com o bloco inteiro trancado atrás de um `if false`, porque a
    linha do `install -Dm755` continuava lá, escrita e inalcançável — que é
    exatamente o defeito "a casa sabe e o produto não faz".

    O recorte vai do `readonly <nome>=` até o primeiro `fi` em coluna zero; o
    bloco só usa `if/else/fi`, sem aninhamento, então esse `fi` é o fim real.
    """
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = re.search(rf"^readonly {re.escape(nome)}=", texto, re.MULTILINE)
    assert inicio is not None, f"bloco {nome} não encontrado no install.sh"
    fim = re.search(r"^fi\n", texto[inicio.start() :], re.MULTILINE)
    assert fim is not None, f"fim do bloco {nome} não encontrado"
    return texto[inicio.start() : inicio.start() + fim.end()]


def test_o_install_materializa_o_curador_sem_flag(tmp_path: Path) -> None:
    """Toda cura entra no install, sem flag (regra da casa, 08/08/2026).

    RODA o bloco de verdade num `HOME` de mentira e cobra o arquivo no disco —
    é a única forma de o teste morder quando alguém desliga o passo em vez de
    apagá-lo.
    """
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

    # Reinstalar ATUALIZA a cópia em vez de falhar (o `install.sh` roda de novo
    # a cada release, e um curador velho seria pior que nenhum).
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
