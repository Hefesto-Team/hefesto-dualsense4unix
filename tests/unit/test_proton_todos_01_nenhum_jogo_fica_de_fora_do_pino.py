"""PROTON-TODOS-01 — nenhum jogo fica de fora do pino, nem os de depois."""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.integrations import proton_pin


PINO = "GE-Proton11-7-x86_64"


def _vdf(mapeamento: dict[str, str]) -> str:
    """Um `config.vdf` mínimo, com o bloco que o produto edita."""
    linhas = [
        '"InstallConfigStore"', "{", '\t"Software"', "\t{", '\t\t"Valve"',
        "\t\t{", '\t\t\t"Steam"', "\t\t\t{", '\t\t\t\t"CompatToolMapping"',
        "\t\t\t\t{",
    ]
    for app, nome in mapeamento.items():
        linhas += [
            f'\t\t\t\t\t"{app}"', "\t\t\t\t\t{",
            f'\t\t\t\t\t\t"name"\t\t"{nome}"',
            '\t\t\t\t\t\t"config"\t\t""',
            '\t\t\t\t\t\t"priority"\t\t"250"',
            "\t\t\t\t\t}",
        ]
    linhas += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}", "}"]
    return "\n".join(linhas) + "\n"


def _nomes(texto: str) -> dict[str, str]:
    import re
    return {a: n for a, n in re.findall(r'"(\d+|0)"\s*\{[^}]*?"name"\s*"([^"]*)"', texto, re.S)}


@pytest.fixture(autouse=True)
def _a_steam_dela_nao_decide_o_resultado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutraliza o gate da Steam VIVA nas réguas que chamam a função pública."""
    monkeypatch.setattr(proton_pin, "_steam_gate", lambda: None)

def test_com_todos_o_jogo_em_outra_ferramenta_migra() -> None:
    """A cena exata da queixa: o DON'T SCREAM em `proton_11`, o resto no pino."""
    original = _vdf({"0": PINO, "2497900": "proton_11", "111": PINO})

    novo, mudancas = proton_pin.build_compat_tool_mapping(
        original,
        tool_name=PINO,
        appids=["2497900", "111"],
        pinos_nossos=(PINO,),
        atropelar_escolha_dela=True,
    )

    assert _nomes(novo)["2497900"] == PINO, (
        "o jogo que apontava para outra ferramenta NÃO migrou com a ordem dela "
        "ligada — é a queixa de 17/09/2026"
    )
    assert mudancas["2497900"]["action"] != "preservado"
    assert mudancas["2497900"]["previous_name"] == "proton_11", (
        "o caminho de volta tem de ficar registrado: o `--unlock` devolve o "
        "`previous_name`, e sem ele a decisão dela vira via de mão única"
    )


def test_sem_todos_a_guarda_continua_sendo_o_padrao() -> None:
    """O padrão da função não mudou — quem não pede, não atropela."""
    original = _vdf({"0": PINO, "2497900": "proton_11"})

    novo, mudancas = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["2497900"], pinos_nossos=(PINO,),
    )

    assert _nomes(novo)["2497900"] == "proton_11", "a guarda deixou de ser o padrão"
    assert mudancas == {}, f"preservar não pode escrever nada: {mudancas}"
    assert novo == original, "o arquivo mudou apesar de a guarda ter preservado"


@pytest.mark.parametrize(
    "ferramenta",
    ["proton_11", "proton_experimental", "proton_hotfix", "GE-Proton9-20"],
)
def test_todos_alcanca_qualquer_ferramenta(ferramenta: str) -> None:
    """*"todo o resto"* é literal — não é uma lista de ferramentas conhecidas."""
    original = _vdf({"0": PINO, "42": ferramenta})

    novo, _ = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["42"], pinos_nossos=(PINO,),
        atropelar_escolha_dela=True,
    )
    assert _nomes(novo)["42"] == PINO


def test_o_install_pede_todos() -> None:
    """Sem esta linha, a decisão de produto morre no CLI e nunca alcança a máquina."""
    import re

    raiz = pathlib.Path(proton_pin.__file__).resolve().parents[3]
    inst = raiz / "install.sh"
    assert inst.is_file(), (
        f"o `install.sh` não está em {inst} — se o caminho mudou, reaponte-o; "
        "um `skip` aqui esconderia a asserção que importa"
    )

    texto = inst.read_text(encoding="utf-8")
    assert re.search(r"proton_pin\.py[^\n]*--lock\b[^\n]*--todos\b", texto) or \
           re.search(r'PROTON_PIN_PY\}"\s+--lock\s+--todos', texto), (
        "o `install.sh` chama `--lock` sem `--todos`: a guarda `preservado` "
        "volta a valer e jogo com outra ferramenta fica fora do pino, em "
        "silêncio. É a ordem dela de 17/09/2026"
    )


def test_a_flag_existe_no_cli() -> None:
    """E ela tem de estar no `--help`, senão ninguém a encontra."""
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, proton_pin.__file__, "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert "--todos" in r.stdout, "a flag sumiu do CLI"


def test_a_regua_sabe_reprovar() -> None:
    """Com a ordem de produto DESLIGADA, o caso central falha — é o que a prova."""
    original = _vdf({"0": PINO, "2497900": "proton_11"})

    sem, _ = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["2497900"], pinos_nossos=(PINO,),
    )
    com, _ = proton_pin.build_compat_tool_mapping(
        original, tool_name=PINO, appids=["2497900"], pinos_nossos=(PINO,),
        atropelar_escolha_dela=True,
    )
    assert _nomes(sem)["2497900"] != _nomes(com)["2497900"], (
        "a flag não mudou nada — ou ela parou de ser lida, ou o jogo já era "
        "alcançado por outro caminho e esta régua dá verde sobre nada"
    )


class TestOCaminhoDaFlag:
    """De `lock_games_to_pinned_proton(todos=…)` até o byte no arquivo."""

    def _cena(self, tmp_path: pathlib.Path) -> pathlib.Path:
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8")
        return vdf

    def test_o_lock_com_todos_alcanca_o_jogo(self, tmp_path: pathlib.Path) -> None:
        """A MORDIDA: tire `atropelar_escolha_dela=todos` do `lock` e isto reprova."""
        vdf = self._cena(tmp_path)
        r = proton_pin.lock_games_to_pinned_proton(
            tool_name=PINO,
            appids=["2497900"],
            config_vdf=vdf,
            state_path=tmp_path / "estado.json",
            todos=True,
        )
        assert r["status"] in ("locked", "noop"), r
        assert _nomes(vdf.read_text(encoding="utf-8"))["2497900"] == PINO, (
            "o `todos=True` não chegou ao miolo que decide — o repasse se "
            "perdeu entre a função pública e `build_compat_tool_mapping`"
        )

    def test_o_lock_sem_todos_preserva(self, tmp_path: pathlib.Path) -> None:
        """O outro lado: sem pedir, o arquivo não muda. Sem este caso, um"""
        vdf = self._cena(tmp_path)
        antes = vdf.read_text(encoding="utf-8")
        proton_pin.lock_games_to_pinned_proton(
            tool_name=PINO,
            appids=["2497900"],
            config_vdf=vdf,
            state_path=tmp_path / "estado.json",
        )
        assert _nomes(vdf.read_text(encoding="utf-8"))["2497900"] == "proton_11", (
            "o padrão deixou de preservar: alguém grudou o `todos` em True"
        )
        assert vdf.read_text(encoding="utf-8") == antes


class TestAEntradaOrfa:
    """O jogo desinstalado cuja escolha ficou no `config.vdf`."""

    def test_com_todos_a_entrada_orfa_tambem_migra(self) -> None:
        """A cena medida: o alvo não está em `appids` porque não está instalado."""
        original = _vdf({"0": PINO, "1245620": "proton_11", "2369580": "GE-Proton10-34"})

        novo, mudancas = proton_pin.build_compat_tool_mapping(
            original,
            tool_name=PINO,
            appids=[],
            pinos_nossos=(PINO,),
            atropelar_escolha_dela=True,
        )

        nomes = _nomes(novo)
        assert nomes["1245620"] == PINO, (
            "a entrada órfã continuou no `proton_11`: o `--todos` só olhou os "
            "appids passados, e o jogo volta fora do pino quando for reinstalado"
        )
        assert nomes["2369580"] == PINO
        assert mudancas["1245620"]["previous_name"] == "proton_11", (
            "o caminho de volta some: sem `previous_name` o `--unlock` não "
            "devolve a órfã ao que era"
        )

    def test_sem_todos_a_orfa_nao_e_tocada(self) -> None:
        """A MORDIDA do outro lado — e ela prova que o alcance é da FLAG."""
        original = _vdf({"0": PINO, "1245620": "proton_11"})

        novo, mudancas = proton_pin.build_compat_tool_mapping(
            original, tool_name=PINO, appids=[], pinos_nossos=(PINO,),
        )
        assert novo == original, "o padrão passou a mexer em entrada não mirada"
        assert mudancas == {}

    def test_o_lock_inteiro_alcanca_a_orfa(self, tmp_path: pathlib.Path) -> None:
        """Fim a fim pela função pública — o CAMINHO, não o método."""
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_vdf({"0": PINO, "1245620": "proton_11"}), encoding="utf-8")

        r = proton_pin.lock_games_to_pinned_proton(
            tool_name=PINO,
            appids=[],
            config_vdf=vdf,
            state_path=tmp_path / "estado.json",
            todos=True,
        )
        assert r["status"] in ("locked", "noop"), r
        assert _nomes(vdf.read_text(encoding="utf-8"))["1245620"] == PINO, (
            "o `todos=True` não alcançou a órfã pelo caminho de produção"
        )

    def test_a_orfa_nao_inventa_entrada(self, tmp_path: pathlib.Path) -> None:
        """`--todos` alcança o que JÁ ESTÁ no mapa — nunca cria jogo do nada."""
        original = _vdf({"0": PINO, "111": "proton_11"})
        novo, _ = proton_pin.build_compat_tool_mapping(
            original, tool_name=PINO, appids=[], pinos_nossos=(PINO,),
            atropelar_escolha_dela=True,
        )
        assert set(_nomes(novo)) == {"0", "111"}, (
            "o `--todos` inventou entrada: ele só pode alcançar quem já está "
            "no `CompatToolMapping`"
        )
