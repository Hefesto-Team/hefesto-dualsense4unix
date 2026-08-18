"""O desfazer do Steam Input existe — e passa por uma porta de verdade.

BOTAO-QUE-NAO-MENTE-01 (entrega 2) e STEAM-INPUT-01 (entrega 3).

O defeito medido em 26/07: `remove_appid_from_steam_input_allowlist` estava
escrita, testada com nove casos em `test_steam_launch_options_vdf.py` — e com
ZERO chamadores em `src/`. Função órfã não é feature: pôr um jogo na exceção do
Steam Input era um clique, tirar exigia editor de texto. E o preço de um jogo
marcado por engano é alto (perde cor, gatilhos e co-op do Hefesto).

Estes testes cobrem os dois lados do buraco:

1. a porta funciona — a remoção pela CLI tira o appid do ARQUIVO (não basta
   imprimir uma mensagem bonita);
2. a função não voltou a ser órfã — um grep em `src/` tem de achar chamador.

O teste 2 é o que impede a regressão silenciosa: alguém pode apagar a chamada e
todos os testes de unidade da função continuariam verdes, porque eles chamam a
função direto.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"
#: Onde a função é DEFINIDA — a definição não conta como chamador.
DEFINICAO = SRC / "hefesto_dualsense4unix" / "integrations" / "steam_launch_options.py"
ALVO = "remove_appid_from_steam_input_allowlist"

CABECALHO = (
    "# hefesto-dualsense4unix — allowlist do Steam Input per-app\n"
    "# (STEAM-INPUT-ALLOWLIST-01)\n"
    "#\n"
    "# Uma linha por AppID; '#' comenta.\n"
    "\n"
    "# Mullet Mad Jack — SetDualSenseTriggerEffect via Steamworks:\n"
    "2111190\n"
    "\n"
    "# Pragmata — suporte nativo a DualSense entregue PELA Steam.\n"
    "3357650\n"
)

#: appid: nome, como a Steam escreve no appmanifest da máquina dela.
JOGOS = {"2111190": "Mullet Mad Jack", "3357650": "PRAGMATA"}


@pytest.fixture
def steam_falsa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME hermético: allowlist em XDG + appmanifests de uma Steam nativa.

    `steam_input_allowlist_path` resolve `XDG_CONFIG_HOME` e `default_steam_root`
    resolve `Path.home()` (que honra `HOME`) — então o teste não encosta na
    configuração real da mantenedora.
    """
    config = tmp_path / "config"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    # Largura fixa: sem isso o rich quebra a linha do jogo no meio do nome.
    monkeypatch.setenv("COLUMNS", "200")

    allowlist = config / "hefesto-dualsense4unix" / "steam_input_apps.txt"
    allowlist.parent.mkdir(parents=True, exist_ok=True)
    allowlist.write_text(CABECALHO, encoding="utf-8")

    steamapps = tmp_path / ".steam" / "steam" / "steamapps"
    steamapps.mkdir(parents=True, exist_ok=True)
    for appid, nome in JOGOS.items():
        (steamapps / f"appmanifest_{appid}.acf").write_text(
            '"AppState"\n{\n'
            f'\t"appid"\t\t"{appid}"\n'
            f'\t"name"\t\t"{nome}"\n'
            "}\n",
            encoding="utf-8",
        )
    return allowlist


def vivos(allowlist: Path) -> list[str]:
    """AppIDs em linha VIVA (comentário não conta) — o que o guarda enxerga."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        parse_steam_input_allowlist,
    )

    return parse_steam_input_allowlist(allowlist.read_text(encoding="utf-8"))


def test_remove_pela_cli_tira_o_appid_do_arquivo(steam_falsa: Path) -> None:
    """A MORDIDA: sem a chamada ligada, o arquivo continua com os dois appids."""
    assert vivos(steam_falsa) == ["2111190", "3357650"]

    resultado = runner.invoke(app, ["gamepad", "steam-input", "remove", "2111190"])

    assert resultado.exit_code == 0, resultado.output
    assert vivos(steam_falsa) == ["3357650"], "o appid removido continua no arquivo"


def test_remove_preserva_o_arquivo_da_mantenedora(steam_falsa: Path) -> None:
    """Só a linha do appid sai — cabeçalho e anotações dela ficam byte a byte."""
    runner.invoke(app, ["gamepad", "steam-input", "remove", "2111190"])

    texto = steam_falsa.read_text(encoding="utf-8")
    assert "allowlist do Steam Input per-app" in texto
    assert "# Pragmata — suporte nativo a DualSense entregue PELA Steam." in texto
    assert "\n2111190\n" not in texto


def test_remove_aceita_o_nome_do_jogo(steam_falsa: Path) -> None:
    """Ninguém decora appid. Digitar parte do nome remove o jogo certo."""
    resultado = runner.invoke(app, ["gamepad", "steam-input", "remove", "pragmata"])

    assert resultado.exit_code == 0, resultado.output
    assert vivos(steam_falsa) == ["2111190"]


def test_list_mostra_o_nome_e_nao_so_o_numero(steam_falsa: Path) -> None:
    """"Uma linha por jogo, com nome, no lugar da contagem" (STEAM-INPUT-01)."""
    resultado = runner.invoke(app, ["gamepad", "steam-input", "list"])

    assert resultado.exit_code == 0, resultado.output
    assert "Mullet Mad Jack" in resultado.output
    assert "PRAGMATA" in resultado.output
    assert "2111190" in resultado.output


def test_list_diz_como_desfazer(steam_falsa: Path) -> None:
    """A listagem não pode ser um beco: ela ensina o gesto de saída."""
    resultado = runner.invoke(app, ["gamepad", "steam-input", "list"])

    assert "remove" in resultado.output


def test_remove_de_jogo_ausente_avisa_e_falha(steam_falsa: Path) -> None:
    """Pedir para tirar o que não está lá é aviso, não silêncio nem traceback."""
    resultado = runner.invoke(app, ["gamepad", "steam-input", "remove", "620"])

    assert resultado.exit_code == 1
    assert "não estava" in resultado.output
    assert vivos(steam_falsa) == ["2111190", "3357650"]


def test_nome_ambiguo_nao_remove_no_chute(steam_falsa: Path) -> None:
    """Trecho que casa com dois jogos mostra os candidatos e NÃO mexe no arquivo."""
    resultado = runner.invoke(app, ["gamepad", "steam-input", "remove", "a"])

    assert resultado.exit_code == 1
    assert vivos(steam_falsa) == ["2111190", "3357650"]


def test_lista_vazia_nao_mente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem allowlist no disco, a resposta é "nenhum jogo" — não um erro."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("COLUMNS", "200")

    resultado = runner.invoke(app, ["gamepad", "steam-input", "list"])

    assert resultado.exit_code == 0, resultado.output
    assert "Nenhum jogo" in resultado.output


def chamadores_em_src() -> list[str]:
    """Arquivos de `src/` que CHAMAM a remoção (a definição não conta).

    Por AST, não por grep de texto: o docstring deste módulo e o do próprio
    `cmd_steam.py` citam o nome da função ao explicar o defeito, e um grep
    ingênuo daria o teste por satisfeito com uma MENÇÃO. Só contam referências
    reais no código — `from ... import`, nome usado, ou atributo (`slo.f(...)`,
    que é como `daemon_actions.py` chama a irmã `add_...`).
    """
    achados: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        if arquivo == DEFINICAO:
            continue
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover - arquivo quebrado é outro problema
            continue
        for no in ast.walk(arvore):
            referencia = (
                (isinstance(no, ast.Name) and no.id == ALVO)
                or (isinstance(no, ast.Attribute) and no.attr == ALVO)
                or (
                    isinstance(no, ast.ImportFrom)
                    and any(nome.name == ALVO for nome in no.names)
                )
            )
            if referencia:
                achados.append(str(arquivo.relative_to(RAIZ)))
                break
    return achados


def test_a_remocao_nao_voltou_a_ser_orfa() -> None:
    """A regressão que os nove testes de unidade da função NÃO pegariam.

    Eles chamam a função direto; se a única chamada de produção sumir, todos
    seguem verdes e o desfazer some da mão da mantenedora sem ninguém notar.
    Em 26/07 este grep devolvia lista vazia.
    """
    chamadores = chamadores_em_src()

    assert chamadores, (
        "remove_appid_from_steam_input_allowlist voltou a ser órfã: "
        "nenhum arquivo de src/ a chama — o desfazer sumiu da interface"
    )


def test_a_definicao_sozinha_nao_conta_como_chamador() -> None:
    """Prova que o teste acima morde: o arquivo da definição está excluído."""
    assert DEFINICAO.is_file()
    assert ALVO in DEFINICAO.read_text(encoding="utf-8")
    assert str(DEFINICAO.relative_to(RAIZ)) not in chamadores_em_src()


def test_mencao_em_docstring_nao_conta_como_chamador(tmp_path: Path) -> None:
    """A segunda mordida: citar o nome numa prosa não religa o desfazer.

    `cmd_steam.py` explica o defeito no próprio docstring — e cita o nome da
    função ali. Se a contagem fosse por grep de texto, apagar a chamada real
    deixaria o teste verde por causa da explicação de que ela existe.
    """
    so_prosa = tmp_path / "so_prosa.py"
    so_prosa.write_text(f'"""Fala de {ALVO} sem chamar."""\n# {ALVO}\n', encoding="utf-8")

    arvore = ast.parse(so_prosa.read_text(encoding="utf-8"))
    referencias = [
        no
        for no in ast.walk(arvore)
        if (isinstance(no, ast.Name) and no.id == ALVO)
        or (isinstance(no, ast.Attribute) and no.attr == ALVO)
        or (isinstance(no, ast.ImportFrom) and any(n.name == ALVO for n in no.names))
    ]

    assert referencias == []
    assert ALVO in so_prosa.read_text(encoding="utf-8")
