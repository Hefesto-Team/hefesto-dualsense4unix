"""As versões do Proton que sobram — O-FIXAR-PROTON-DESINSTALA-AS-VERSOES-QUE-SOBRAM-01."""
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
    (alvo / "version").write_text("1 x\n", encoding="utf-8")
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


def _sem_steam_aberta() -> None:
    return None


def test_sem_o_pino_instalado_nada_sobra(steam: Path) -> None:
    """Apagar é de vez: sem a fixada no disco, as outras não saem (ficaria sem Proton nenhum)."""
    import shutil

    _mapa(steam, {"1": PINO})
    shutil.rmtree(steam / ".steam" / "steam" / "compatibilitytools.d" / PINO)
    assert pp.versoes_que_sobram(steam, pino=PINO) == []


def test_o_jogo_fora_do_pino_e_o_desinstalado_mantem_a_versao(steam: Path) -> None:
    """O 2 foi tirado do pino (11-3); o 3 nem está instalado (10-34): as duas ficam."""
    _mapa(steam, {"1": PINO, "2": "GE-Proton11-3", "3": "GE-Proton10-34"})
    assert _nomes(pp.versoes_que_sobram(steam, pino=PINO)) == {
        "GE-Proton11-1", "GE-Proton11-6-x86_64"}


def test_apagar_tira_do_disco_so_a_sobra_e_nao_deixa_lixeira(
        steam: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De vez: a pasta some, o pino, o decoy da Valve e o resto ficam, e nada vai à lixeira."""
    raiz = steam / ".steam" / "steam"
    valve = raiz / "steamapps" / "common" / "Proton 9.0"
    valve.mkdir(parents=True)
    (valve / "proton").write_bytes(b"v")
    monkeypatch.setenv("XDG_DATA_HOME", str(steam / "dados"))
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, em_uso=lambda _p: False, steam_barra=_sem_steam_aberta)
    assert {s.pasta.name for s in saiu} == _nomes(sobras) and recusadas == {}
    compat = raiz / "compatibilitytools.d"
    assert sorted(p.name for p in compat.iterdir()) == [PINO]
    assert (valve / "proton").is_file()
    assert not (steam / "dados" / "Trash").exists()


def test_nada_fora_de_compatibilitytools_d_e_tocado(steam: Path) -> None:
    """Mordida: tire o guarda do pai e a Valve em `steamapps/common` vai embora."""
    valve = steam / ".steam" / "steam" / "steamapps" / "common" / "Proton 9.0"
    valve.mkdir(parents=True)
    (valve / "proton").write_bytes(b"v")
    alheia = pp.VersaoQueSobra(valve, ("Proton 9.0",), 1)
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        [alheia], em_uso=lambda _p: False, steam_barra=_sem_steam_aberta)
    assert saiu == [] and "Proton 9.0" in recusadas
    assert (valve / "proton").is_file()


def test_a_steam_aberta_nao_apaga_nada(steam: Path) -> None:
    """A Steam regrava o que viu ao sair: com ela aberta, ou com jogo aberto, tudo fica."""
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    for barra, frase in (("steam_aberta", "a Steam está aberta"),
                         ("jogo_da_steam_aberto", "há um jogo da Steam aberto")):
        saiu, recusadas = pp.desinstalar_as_que_sobram(
            sobras, em_uso=lambda _p: False, steam_barra=lambda b=barra: b)
        assert saiu == []
        assert set(recusadas.values()) == {frase}
    assert all(s.pasta.is_dir() for s in sobras)


def test_sem_dizer_nada_a_porta_da_steam_e_a_de_verdade(
        steam: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O padrão pergunta à Steam de verdade: ninguém apaga por esquecer de passar a porta."""
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)
    monkeypatch.setattr(pp, "steam_running", lambda: True)
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    saiu, _recusadas = pp.desinstalar_as_que_sobram(sobras, em_uso=lambda _p: False)
    assert saiu == [] and all(s.pasta.is_dir() for s in sobras)


def test_a_pasta_em_uso_fica(steam: Path) -> None:
    """A fila da Steam roda de dentro da pasta logo depois de ela abrir."""
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, em_uso=lambda p: p.name == "GE-Proton11-1", steam_barra=_sem_steam_aberta)
    assert "GE-Proton11-1" in recusadas
    assert (steam / ".steam" / "steam" / "compatibilitytools.d" / "GE-Proton11-1").is_dir()
    assert len(saiu) == 3


def test_o_que_o_disco_recusa_vira_motivo(steam: Path) -> None:
    _mapa(steam, {"1": PINO})
    sobras = pp.versoes_que_sobram(steam, pino=PINO)[:1]
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, apagar=lambda _p: "sem permissão", em_uso=lambda _p: False,
        steam_barra=_sem_steam_aberta)
    assert saiu == []
    assert list(recusadas.values()) == ["sem permissão"]


def test_apagar_de_vez_devolve_o_motivo_quando_nao_da(tmp_path: Path) -> None:
    pasta = tmp_path / "compatibilitytools.d" / "x"
    pasta.mkdir(parents=True)
    assert pp._apagar_de_vez(pasta) is None and not pasta.exists()
    assert pp._apagar_de_vez(pasta) is not None


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


def test_o_reaplicar_apaga_as_que_sobram_sem_perguntar_por_elas(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O clique 1 só mostra os consertos; as versões saem no 2, e a frase não as cita."""
    import pacotes

    sobras = [_sobra("GE-Proton11-1"), _sobra("GE-Proton11-3")]
    monkeypatch.setattr(a09, "_versoes_que_sobram", lambda: list(sobras))
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    levadas: list[str] = []
    monkeypatch.setattr(pp, "desinstalar_as_que_sobram",
                        lambda s: (levadas.extend(x.pasta.name for x in s), (list(s), {}))[1])
    acao = pacotes.gesto_da_pagina("09-sistema.html", "refazer-consertos")

    acao(_ctx(), {"texto": a09._rotulo_do_desenho("refazer-consertos")}, None)
    painel = str(a09._PAINEL[0])
    assert "Proton" not in painel and "lixeira" not in painel.lower()
    assert levadas == []
    with contextlib.redirect_stderr(io.StringIO()):
        acao(_ctx(), {"texto": a09.CONFIRMA}, None)

    assert levadas == ["GE-Proton11-1", "GE-Proton11-3"]
    assert "foram apagadas (3,0 GB)" in a09.recibos_da_regua[-1][1]


def test_ligar_o_fixar_proton_apaga_as_que_sobram(
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
        ("fixar-proton", "Travei. 1 versão do Proton sem uso foi apagada (1,5 GB).")]


def test_o_recibo_diz_quantas_e_quantos_gb_e_junta_as_que_ficaram_pelo_mesmo_motivo(
        a09: Any) -> None:
    tres = [_sobra(n) for n in ("GE-Proton10-34", "GE-Proton11-1", "GE-Proton11-3")]
    assert a09._frase_do_que_saiu(tres, {}) == (
        "3 versões do Proton sem uso foram apagadas (4,5 GB).")
    ficou = a09._frase_do_que_saiu([], {"a": "a Steam está aberta", "b": "a Steam está aberta"})
    assert ficou == "2 versões do Proton sem uso ficaram (a, b): a Steam está aberta."
    assert "lixeira" not in ficou
