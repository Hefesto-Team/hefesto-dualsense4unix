"""As versões do Proton que sobram — O-FIXAR-PROTON-DESINSTALA-AS-VERSOES-QUE-SOBRAM-01.

Ela, 01/10: *«Nosso botao de fixar o proton deveria desinstalar as outras
versoes nao usadas»*. <!-- noqa-acento: citação literal dela -->

Ao abrir, a Steam roda o `d3ddriverquery64.exe` duas vezes por versão em
`compatibilitytools.d`. Tudo aqui é Steam de mentira no `tmp_path`: nada toca
a Steam real nem a lixeira dela.

AS MORDIDAS:

- troque `usadas = {nome_do_pino, *mapa.values()}` de `versoes_que_sobram`
  por `usadas = {nome_do_pino}` e `test_a_versao_de_um_jogo_fica` reprova;
- troque o `if em_uso(sobra.pasta)` de `desinstalar_as_que_sobram` por
  `if False` e `test_a_pasta_em_uso_fica` reprova.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import proton_pin as pp

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PINO = "GE-Proton11-7-x86_64"


def _vdf(mapeamento: dict[str, str]) -> str:
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


def _ferramenta(compat: Path, pasta: str, nome: str | None = None) -> Path:
    """Uma pasta como as do GE: o `compatibilitytool.vdf` com o nome interno."""
    alvo = compat / pasta
    alvo.mkdir(parents=True)
    interno = nome or pasta
    (alvo / "compatibilitytool.vdf").write_text(
        '"compatibilitytools"\n{\n  "compat_tools"\n  {\n'
        f'    "{interno}" // Internal name of this tool\n    {{\n'
        '      "install_path" "."\n      "display_name" "x"\n    }\n  }\n}\n',
        encoding="utf-8")
    (alvo / "proton").write_bytes(b"x" * 1000)
    return alvo


@pytest.fixture
def steam(tmp_path: Path) -> Path:
    """A casa de mentira com uma Steam nativa e cinco GE, como a dela em 01/10."""
    casa = tmp_path / "casa"
    raiz = casa / ".steam" / "steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir()
    compat = raiz / "compatibilitytools.d"
    for pasta in ("GE-Proton10-34", "GE-Proton11-1", "GE-Proton11-3",
                  "GE-Proton11-6-x86_64", PINO):
        _ferramenta(compat, pasta)
    return casa


def _mapa(casa: Path, mapeamento: dict[str, str]) -> None:
    (casa / ".steam" / "steam" / "config" / "config.vdf").write_text(
        _vdf(mapeamento), encoding="utf-8")


def _nomes(sobras: list[pp.VersaoQueSobra]) -> set[str]:
    return {s.pasta.name for s in sobras}


def test_com_todo_jogo_no_pino_sobram_as_outras_quatro(steam: Path) -> None:
    _mapa(steam, {str(a): PINO for a in range(1, 31)})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    assert _nomes(sobras) == {"GE-Proton10-34", "GE-Proton11-1", "GE-Proton11-3",
                              "GE-Proton11-6-x86_64"}
    assert all(s.tamanho >= 1000 for s in sobras)


def test_a_versao_de_um_jogo_fica(steam: Path) -> None:
    """Um jogo fora do pino, ou desinstalado, que nomeia o 11-3: o 11-3 fica."""
    _mapa(steam, {"1": PINO, "2": "GE-Proton11-3"})
    assert "GE-Proton11-3" not in _nomes(pp.versoes_que_sobram(steam, pino=PINO))


def test_a_chave_global_conta(steam: Path) -> None:
    """A chave `"0"` é o Proton padrão da Steam: a versão dela fica."""
    _mapa(steam, {"0": "GE-Proton10-34", "1": PINO})
    assert "GE-Proton10-34" not in _nomes(pp.versoes_que_sobram(steam, pino=PINO))


def test_o_nome_interno_manda_e_nao_o_da_pasta(steam: Path) -> None:
    """O `CompatToolMapping` aponta pelo nome interno do `compatibilitytool.vdf`."""
    compat = steam / ".steam" / "steam" / "compatibilitytools.d"
    _ferramenta(compat, "pasta-com-outro-nome", "Proton-tkg-9")
    _mapa(steam, {"1": PINO, "2": "Proton-tkg-9"})
    assert "pasta-com-outro-nome" not in _nomes(pp.versoes_que_sobram(steam, pino=PINO))


def test_o_que_nao_e_proton_fica(steam: Path) -> None:
    """Luxtorpeda é escolha de rodar nativo: não é versão do Proton."""
    _ferramenta(steam / ".steam" / "steam" / "compatibilitytools.d", "luxtorpeda")
    _mapa(steam, {"1": PINO})
    assert "luxtorpeda" not in _nomes(pp.versoes_que_sobram(steam, pino=PINO))


def test_sem_o_config_vdf_nada_sobra(steam: Path) -> None:
    """Na dúvida, nada: sem o mapa legível não se sabe o que é usado."""
    assert pp.versoes_que_sobram(steam, pino=PINO) == []


def test_sem_steam_nada_sobra(tmp_path: Path) -> None:
    assert pp.versoes_que_sobram(tmp_path / "vazia", pino=PINO) == []


def test_a_lixeira_recebe_as_sobras(steam: Path) -> None:
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    levadas: list[Path] = []

    def lixeira(pasta: Path) -> None:
        levadas.append(pasta)
        return None

    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, lixeira=lixeira, em_uso=lambda _p: False)
    assert {s.pasta.name for s in saiu} == _nomes(sobras)
    assert recusadas == {}
    assert PINO not in {p.name for p in levadas}


def test_a_pasta_em_uso_fica(steam: Path) -> None:
    """A fila da Steam roda de dentro da pasta logo depois de ela abrir."""
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    levadas: list[Path] = []
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, lixeira=lambda p: levadas.append(p),
        em_uso=lambda p: p.name == "GE-Proton11-1")
    assert "GE-Proton11-1" in recusadas
    assert "GE-Proton11-1" not in {p.name for p in levadas}
    assert len(saiu) == 3


def test_a_lixeira_que_recusa_vira_motivo(steam: Path) -> None:
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)[:1]
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, lixeira=lambda _p: "sem lixeira", em_uso=lambda _p: False)
    assert saiu == []
    assert list(recusadas.values()) == ["sem lixeira"]


def test_a_lixeira_de_verdade_nunca_apaga_sem_gio(
        steam: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o `gio`, recusa. A pasta continua no disco."""
    monkeypatch.setattr(pp.shutil, "which", lambda _n: None)
    pasta = steam / ".steam" / "steam" / "compatibilitytools.d" / "GE-Proton11-1"
    assert pp._para_a_lixeira(pasta) is not None
    assert pasta.is_dir()


# ---------------------------------------------------------------------------
# Os dois botões da aba Sistema
# ---------------------------------------------------------------------------


class _Janela:
    """O dublê da janela antiga: o script do conserto nunca existe."""

    def _find_repo_file(self, relpath: str) -> Path:
        return Path("/nao-existe") / relpath


@pytest.fixture
def a09(monkeypatch: pytest.MonkeyPatch) -> Any:
    from pacotes import a09_sistema as mod

    def limpar() -> None:
        mod._LENTO.clear()
        mod._ARMADO.clear()
        mod._PAINEL[0] = None
        mod._PERGUNTA.clear()
        mod._ANTES_DO_CONSERTO.clear()

    mod._JANELA_ANTIGA[:] = [_Janela()]
    limpar()
    recibos: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "_relatar_o_recibo", lambda g, f: recibos.append((g, f)))
    mod.recibos_da_regua = recibos
    yield mod
    mod._JANELA_ANTIGA.clear()
    limpar()


def _sobra(nome: str) -> pp.VersaoQueSobra:
    return pp.VersaoQueSobra(Path("/x/compatibilitytools.d") / nome, (nome,), 1_500_000_000)


def _ctx() -> Any:
    import pacotes

    return pacotes.Contexto(state={"paused": False, "controllers": []},
                            mesa=[], conectados=[], estados={})


def test_o_reaplicar_mostra_antes_e_leva_so_o_que_mostrou(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Clique 1 mostra as duas; no clique 2 apareceu uma terceira, que fica."""
    import pacotes

    vistas = [_sobra("GE-Proton11-1"), _sobra("GE-Proton11-3")]
    agora = [list(vistas)]
    monkeypatch.setattr(a09, "_versoes_que_sobram", lambda: list(agora[0]))
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    levadas: list[str] = []
    monkeypatch.setattr(pp, "desinstalar_as_que_sobram",
                        lambda s: (levadas.extend(x.pasta.name for x in s), (list(s), {}))[1])
    acao = pacotes.gesto_da_pagina("09-sistema.html", "refazer-consertos")

    acao(_ctx(), {"texto": a09._rotulo_do_desenho("refazer-consertos")}, None)
    assert "GE-Proton11-1, GE-Proton11-3 (3,0 GB)" in str(a09._PAINEL[0])
    agora[0] = [*vistas, _sobra("GE-Proton10-34")]
    with contextlib.redirect_stderr(io.StringIO()):
        acao(_ctx(), {"texto": a09.CONFIRMA}, None)

    assert levadas == ["GE-Proton11-1", "GE-Proton11-3"]
    assert "foram para a lixeira (3,0 GB)" in a09.recibos_da_regua[-1][1]


def test_ligar_o_fixar_proton_leva_as_que_sobram(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import pacotes

    fixado = [False]
    monkeypatch.setattr(a09, "_o_pino",
                        lambda: (object(), lambda **k: fixado.__setitem__(0, True)))
    monkeypatch.setattr(a09, "_porque_o_proton_nao_trava", lambda *_a: None)
    monkeypatch.setattr(a09, "proton_fixado", lambda: fixado[0])
    monkeypatch.setattr(a09._daemon, "format_proton_lock_result", lambda _r: "Travei.")
    monkeypatch.setattr(a09, "_versoes_que_sobram", lambda: [_sobra("GE-Proton11-6-x86_64")])
    monkeypatch.setattr(pp, "desinstalar_as_que_sobram", lambda s: (list(s), {}))

    pacotes.gesto_da_pagina("09-sistema.html", "fixar-proton")(_ctx(), {}, None)

    assert a09.recibos_da_regua == [
        ("fixar-proton", "Travei. 1 versão do Proton sem uso foi para a lixeira (1,5 GB).")]
