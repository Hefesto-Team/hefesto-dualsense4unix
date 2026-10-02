"""CARONA-DO-WRAPPER-01: salvar ou aplicar um perfil repõe o wrapper."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("carona do wrapper 01 (footer/profiles actions puxam GTK)")

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.app.actions import carona_do_wrapper as carona
from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
)

_TAB = "\t"

PRAGMATA = "3357650"
LINHA_PRAGMATA = "VKD3D_CONFIG=no_upload_hvv %command%"

SACKBOY = "1599660"


def _vdf(apps: dict[str, str | None]) -> str:
    """localconfig.vdf mínimo. Valor ``None`` = app SEM a linha LaunchOptions."""
    blocos = []
    for appid, valor in apps.items():
        linha = (
            f'{_TAB * 6}"LaunchOptions"{_TAB * 2}"{slo._vdf_escape(valor)}"\n'
            if valor is not None
            else ""
        )
        blocos.append(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f"{linha}"
            f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * 5}}}\n"
        )
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f"{''.join(blocos)}"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


@pytest.fixture
def biblioteca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O `localconfig.vdf` de mentira, e TODA porta que leva ao disco dela.

    Os dois módulos precisam ser desviados: o censo pergunta às referências que
    a sentinela importou, e o `apply_wrapper_to_all_games` às do
    `steam_launch_options`. Desviar um só deixaria o outro perguntando à
    máquina de verdade — e o "outro" é justamente quem ESCREVE.
    """
    alvo = tmp_path / "localconfig.vdf"
    alvo.write_text(
        _vdf({PRAGMATA: LINHA_PRAGMATA, SACKBOY: slo.WRAPPER_LAUNCH}),
        encoding="utf-8",
    )
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "discover_vdfs", lambda home=None: [alvo])
    monkeypatch.setattr(
        slo, "sem_wrapper_path", lambda *a, **k: tmp_path / "jogos_sem_wrapper.txt"
    )
    monkeypatch.setattr(
        sw, "caminho_do_registro", lambda home=None: tmp_path / "wrapper-visto.json"
    )
    monkeypatch.setattr(slo, "nome_do_appid", lambda appid, home=None: None)
    return alvo


@pytest.fixture
def steam_fechada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O único estado em que escrever no vdf não é jogar o reparo fora."""
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: False)
        monkeypatch.setattr(mod, "steam_game_running", lambda: False)


@pytest.fixture
def steam_aberta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Steam viva: ela regrava o vdf ao sair e engoliria qualquer edição."""
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: True)
        monkeypatch.setattr(mod, "steam_game_running", lambda: False)


@pytest.fixture(autouse=True)
def carona_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Religa a carona, que o `conftest.py` desliga em toda a suíte."""
    monkeypatch.delenv(carona.CARONA_ENV, raising=False)


@pytest.fixture(autouse=True)
def carona_sincrona(monkeypatch: pytest.MonkeyPatch) -> None:
    """A troca de thread da carona, sem thread — worker e callback aqui mesmo."""

    def _sincrono(trabalho: Any, ao_terminar: Any) -> None:
        ao_terminar(trabalho())

    monkeypatch.setattr(carona, "despachar", _sincrono)


@pytest.fixture(autouse=True)
def _run_in_thread_sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    """O funil de gravação também roda em worker; aqui, síncrono."""

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado."""
    import hefesto_dualsense4unix.profiles.loader as loader_mod

    destino = tmp_path / "profiles"
    destino.mkdir()
    monkeypatch.setattr(loader_mod, "profiles_dir", lambda ensure=False: destino)
    return destino


def _perfil() -> Profile:
    return Profile(
        name="Pragmata",
        match=MatchCriteria(window_class=[f"steam_app_{PRAGMATA}"]),
        priority=60,
        leds=LedsConfig(lightbar=(97, 53, 131)),
    )


def _tem_wrapper(vdf: Path, appid: str) -> bool:
    valor = slo.read_apps_by_appid(vdf.read_text(encoding="utf-8")).get(appid)
    return valor is not None and slo.WRAPPER_PREFIX in valor


def test_os_cinco_gestos_chamam_a_carona() -> None:
    """`grep sentinela_do_wrapper app/` devolvia ZERO até 16/08."""
    raiz = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
    esperado = {
        "app/actions/profiles_actions.py": 2,
        "app/actions/profile_writer.py": 1,
        "app/actions/footer_actions.py": 1,
    }
    for relativo, quantas in esperado.items():
        texto = (raiz / relativo).read_text(encoding="utf-8")
        achadas = texto.count("self.pegar_carona_no_gesto(")
        assert achadas == quantas, (
            f"{relativo}: {achadas} chamada(s) a pegar_carona_no_gesto, "
            f"esperadas {quantas} — um gesto do pedido dela ficou sem carona"
        )


#: entrega: um `texto.count(...)` diria *"rodape.py: 2, esperadas 3"* e deixaria
GESTOS_DA_INTERFACE_NOVA = {
    "interface/pacotes/rodape.py": {
        "aplicar",
        "salvar",
        "importar",
    },
    "interface/pacotes/a10_perfis.py": {"ativar", "_gravar",
                                        "voltar_a_de_ontem"},
}

#     voltar-a-de-ontem   restaurar_do_historico + switch + launch_env.refresh

GESTOS_SEM_CARONA = {"interface/pacotes/rodape.py": {"exportar"}}


def _funcoes_que_pegam_carona(caminho: Path) -> set[str]:
    """As funções de módulo que chamam a carona, lidas da árvore de sintaxe.

    Casa por SUFIXO do atributo (`perfil.com_a_carona` e o `_com_a_carona`
    privado que a `a10_perfis` ainda tem) porque as duas formas são a mesma
    chamada: a segunda é a cópia que espera a delegação de uma linha, e o dia
    em que ela virar delegação esta régua não muda.
    """
    import ast

    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    achadas: set[str] = set()
    for no in arvore.body:
        if not isinstance(no, ast.FunctionDef):
            continue
        for dentro in ast.walk(no):
            if not isinstance(dentro, ast.Call):
                continue
            alvo = dentro.func
            nome = alvo.attr if isinstance(alvo, ast.Attribute) else (
                alvo.id if isinstance(alvo, ast.Name) else "")
            if nome.endswith("com_a_carona"):
                achadas.add(no.name)
    return achadas


def test_a_interface_nova_tambem_pega_a_carona() -> None:
    """`07-Q1`, decisão dela: *"Deve aplicar automaticamente como era no gtk"*.

    A janela GTK sai nesta leva; o MOTOR (`app/actions/carona_do_wrapper.py`)
    fica. Este portão é o que impede o motor de ficar sem chamador do lado novo
    — que é exatamente o defeito de 16/08 que o arquivo inteiro existe para
    guardar, repetido um andar acima.

    MORDIDA: arranque o `perfil.com_a_carona()` do fim de `rodape.salvar` e a
    primeira asserção reprova NOMEANDO o gesto — "salvar".
    """
    raiz = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
    for relativo, esperados in GESTOS_DA_INTERFACE_NOVA.items():
        achadas = _funcoes_que_pegam_carona(raiz / relativo)
        faltando = esperados - achadas
        assert not faltando, (
            f"{relativo}: {sorted(faltando)} não pega(m) a carona — "
            "um gesto que aplica ou grava perfil ficou sem repor o atalho "
            "de inicialização que a Steam come"
        )
    for relativo, proibidos in GESTOS_SEM_CARONA.items():
        achadas = _funcoes_que_pegam_carona(raiz / relativo)
        intrusos = proibidos & achadas
        assert not intrusos, (
            f"{relativo}: {sorted(intrusos)} pega(m) a carona sem precisar — "
            "o de fora é declarado no docstring do módulo, com a razão"
        )


def _ctx_do_rodape() -> Any:
    """Um `Contexto` com o perfil ativo e a mesa vazia.

    MESA VAZIA DE PROPÓSITO: o que se mede aqui é a carona. O Salvar e o
    Aplicar não leem a mesa desde 27/09 (`D-2709-O-SALVAR-LE-O-PERFIL`), e
    quem mede isso é `test_o_salvar_e_o_aplicar_leem_so_o_perfil.py`.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={"active_profile": "Pragmata"})


def test_o_salvar_do_rodape_repoe_o_atalho_de_inicializacao(
    biblioteca: Path, steam_fechada: None, disco: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """«Salvar Perfil» do rodapé — FORA da guia de perfis, na interface NOVA.

    Até 06/09 este gesto gravava o perfil dela e deixava o jogo sem enxergar o
    controle: o perfil entrava, o atalho de inicialização continuava comido.

    MORDIDA: arranque o `_recado(perfil.com_a_carona())` do fim de
    `rodape.salvar` e a primeira asserção reprova — o Pragmata continua com a
    linha que comeu o atalho.
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(_perfil())
    assert not _tem_wrapper(biblioteca, PRAGMATA)

    resposta = rodape.salvar(_ctx_do_rodape(), {}, MagicMock())

    assert _tem_wrapper(biblioteca, PRAGMATA)
    assert resposta is None, resposta
    assert PRAGMATA in capsys.readouterr().err
    assert (disco / "pragmata.json").exists()


def test_o_aplicar_verde_do_rodape_repoe_o_atalho(
    biblioteca: Path, steam_fechada: None, disco: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """O botão verde «Aplicar» da interface nova — o irmão do `on_apply_draft`."""
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(_perfil())
    ponte = MagicMock()

    resposta = rodape.aplicar(_ctx_do_rodape(), {}, ponte)

    assert _tem_wrapper(biblioteca, PRAGMATA)
    assert resposta is None, resposta
    assert PRAGMATA in capsys.readouterr().err
    assert ponte.profile_reaplicar.call_count == 1


def test_sem_nada_a_repor_o_rodape_nao_fala(
    biblioteca: Path, steam_fechada: None, disco: Path
) -> None:
    """O SILÊNCIO É O CASO COMUM, e é decisão dela (`03-Q4`).

    Com a biblioteca inteira já com o atalho, a carona não tem notícia — e o
    gesto volta a `None`. Quem responde é a piscada verde de ~1,5 s no campo,
    **sem palavra nova na tela**. Um `{"recado": ""}` aqui faria o piloto
    depositar um recado vazio no cartão a cada Salvar.
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import save_profile

    biblioteca.write_text(
        _vdf({PRAGMATA: slo.WRAPPER_LAUNCH, SACKBOY: slo.WRAPPER_LAUNCH}),
        encoding="utf-8",
    )
    save_profile(_perfil())

    assert rodape.salvar(_ctx_do_rodape(), {}, MagicMock()) is None


def test_a_carona_sozinha_nao_deixa_separador_orfao(
    biblioteca: Path, steam_fechada: None
) -> None:
    """`com_a_carona()` sem frase base devolve a notícia SOZINHA.

    A função nasceu na aba Perfis, onde SEMPRE há uma frase de desfecho a que
    se grudar (*"Perfil ativado: X · …"*). O rodapé não tem nenhuma, e a forma
    de lá — `f"{frase} · {resultado.frase}"` — poria um `" · "` órfão na frente
    do recado, na tela dela.

    MORDIDA: troque o fecho de `perfil.com_a_carona` pelo da aba
    (`return f"{frase} · {resultado.frase}"`) e a segunda asserção reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as pacote_perfil

    sozinha = pacote_perfil.com_a_carona()
    assert sozinha.startswith("Reposta"), sozinha
    assert " · " not in sozinha.split(":")[0]

    biblioteca.write_text(
        _vdf({PRAGMATA: LINHA_PRAGMATA, SACKBOY: slo.WRAPPER_LAUNCH}),
        encoding="utf-8",
    )
    junta = pacote_perfil.com_a_carona("Perfil ativado: Pragmata")
    assert junta.startswith("Perfil ativado: Pragmata · Reposta"), junta


def test_a_carona_do_rodape_nunca_derruba_o_gesto_dela(
    biblioteca: Path, steam_fechada: None, disco: Path, monkeypatch: Any
) -> None:
    """Uma exceção na carona não pode virar tarja de recusa sobre um Salvar OK.

    É o mesmo contrato de `test_a_carona_nunca_derruba_o_gesto_dela`, um andar
    acima: lá o mixin engole, aqui é `perfil.com_a_carona`.
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(_perfil())

    def _explode(**_kw: Any) -> Any:
        raise RuntimeError("a Steam mudou o formato do arquivo")

    monkeypatch.setattr(carona, "passada", _explode)

    assert rodape.salvar(_ctx_do_rodape(), {}, MagicMock()) is None
    assert (disco / "pragmata.json").exists()
