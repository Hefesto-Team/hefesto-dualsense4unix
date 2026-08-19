"""CARONA-DO-WRAPPER-01: salvar ou aplicar um perfil repõe o wrapper.

16/08/2026, e o desenho é DELA: *"nem precisa ter um botão na gui, mas ele se
auto corrigir ao clicarmos em aplicar ou salvar o perfil seja dentro ou fora da
guia de perfis."*

O defeito por trás (SENTINELA-WRAPPER-01, medido ao vivo às 02h30): a Steam
guarda UMA linha de `LaunchOptions` por jogo, e qualquer coisa escrita nela
substitui a chamada do `hefesto-launch` em silêncio. Sem o wrapper, o
`launch_env` que o daemon materializa nunca é lido, e vence a lista de IGNORE
da própria Steam — que manda o jogo ignorar o PID do NOSSO vpad. O controle
fica vivo, a luz acesa, o perfil aplicado, e só o JOGO não enxerga.

A cura existia desde as 04h (`integrations/sentinela_do_wrapper`, 19 testes) e
**ninguém a chamava**: `grep sentinela_do_wrapper app/` devolvia zero. Estes
testes travam o fio que faltava.

A MORDIDA, que é o que este arquivo existe para ser: arranque a linha
``self.pegar_carona_no_gesto(...)`` de qualquer um dos cinco gestos e o teste
correspondente reprova com o wrapper AINDA faltando no vdf de fixture.
(Medido em 16/08 arrancando a do ``app.py``: três reprovações, e a de
comportamento reprova no ``_tem_wrapper`` — não só no portão de fonte.)

**Nenhum `localconfig.vdf` real é tocado** — tudo em `tmp_path`, e a carona só
liga porque este arquivo religa o `HEFESTO_CARONA_WRAPPER` que o `conftest.py`
desliga em toda a suíte (justamente para a suíte não reescrever a biblioteca
Steam dela).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito. Os
# `footer_actions`/`profiles_actions` importados abaixo puxam `app.gui_dialogs`,
# que faz `import gi` no topo — sem esta guarda o módulo derruba a COLETA
# inteira no CI headless (censo de coleta), em vez de pular.
exigir_gi_real("carona do wrapper 01 (footer/profiles actions puxam GTK)")

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.app.actions import carona_do_wrapper as carona
from hefesto_dualsense4unix.app.actions import footer_actions, profiles_actions
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
)

_TAB = "\t"

#: O jogo dela, e a linha literal que comeu o wrapper (conferida em seis
#: backups datados do `localconfig.vdf`).
PRAGMATA = "3357650"
LINHA_PRAGMATA = "VKD3D_CONFIG=no_upload_hvv %command%"

#: Um segundo jogo, que JÁ tem o wrapper: prova que a passada é idempotente e
#: que o reparo não estraga quem estava bem.
SACKBOY = "1599660"


# ---------------------------------------------------------------------------
# Aparelhagem — fixtures em tmp_path, nenhuma leitura do disco real dela
# ---------------------------------------------------------------------------


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
    # Sem `appmanifest` de mentira o rótulo é o appid cru, e é honesto — o que
    # NÃO pode acontecer é a frase da tela sair vasculhando os steamapps dela.
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
    """Religa a carona, que o `conftest.py` desliga em toda a suíte.

    O desligador global existe porque o `HOME` da suíte NÃO é isolado: sem ele,
    qualquer teste de GUI que clicasse "Salvar" varreria — e reescreveria — o
    `localconfig.vdf` de verdade dela. Aqui a religamos por escrito, com o
    `discover_vdfs` já desviado para o `tmp_path` pela fixture `biblioteca`.
    """
    monkeypatch.delenv(carona.CARONA_ENV, raising=False)


@pytest.fixture(autouse=True)
def carona_sincrona(monkeypatch: pytest.MonkeyPatch) -> None:
    """A troca de thread da carona, sem thread — worker e callback aqui mesmo.

    Mesma técnica que a suíte já usa com ``ipc_bridge.run_in_thread``: sem loop
    GTK, o callback nunca rodaria, e o teste mediria só metade do caminho.
    """

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


def _janela(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Dublê com os DOIS mixins que o ``HefestoApp`` compõe de verdade.

    Os quatro gestos que pegam carona moram nos dois: "Salvar este perfil" e
    "Ativar" na aba Perfis, "Salvar Perfil" e o botão verde "Aplicar" no
    rodapé. Testá-los separados mediria uma composição que não existe.
    """
    from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    perfil = _perfil()

    class _Janela(ProfilesActionsMixin, FooterActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.draft = DraftConfig()
            self._active_profile_name = ""
            self._draft_baseline: Any = self.draft
            self._profiles_cache: list[Profile] = []
            self._new_profile = False
            self._duplicate_source = None
            self.toasts: list[str] = []
            self.aplicou_o_rascunho = 0
            builder = MagicMock()
            builder.get_object.return_value = MagicMock()
            self.builder = builder

        # --- o que a aba Perfis leria dos widgets ---
        def _build_profile_from_editor(self) -> Profile:
            return perfil

        def _alvo_do_salvar_do_editor(self) -> str | None:
            return perfil.name

        def _selected_profile_name(self, *a: Any, **k: Any) -> str:
            return perfil.name

        def _reconciliar_rascunho_com_perfil_salvo(self, *a: Any, **k: Any) -> None:
            return None

        def _reload_profiles_store(self, *a: Any, **k: Any) -> None:
            return None

        def _notify_launch_env_refresh(self) -> None:
            return None

        # --- o AGORA do botão verde, que não é o assunto deste arquivo ---
        def _apply_draft_agora(self, *a: Any, **k: Any) -> None:
            self.aplicou_o_rascunho += 1

        # --- a barra de status ---
        def _footer_toast(self, msg: str, context: str = "footer") -> None:
            self.toasts.append(msg)

        def _toast_profile(self, msg: str) -> None:
            self.toasts.append(msg)

    # O daemon não participa de nenhum destes testes.
    monkeypatch.setattr(profiles_actions, "call_async", lambda **k: None)
    monkeypatch.setattr(profiles_actions, "active_profile_name", lambda: None)
    monkeypatch.setattr(profiles_actions, "profile_switch", lambda name: False)
    return _Janela()


def _salvar_pelo_rodape(janela: Any, nome: str = "Pragmata") -> None:
    """O gesto: botão "Salvar Perfil" do rodapé, digita o nome, confirma."""
    dialogos = MagicMock()
    dialogos.prompt_profile_name.return_value = nome
    dialogos.prompt_overwrite_existing.return_value = True
    with patch.object(footer_actions, "gui_dialogs", dialogos):
        janela.on_save_profile()


def _tem_wrapper(vdf: Path, appid: str) -> bool:
    valor = slo.read_apps_by_appid(vdf.read_text(encoding="utf-8")).get(appid)
    return valor is not None and slo.WRAPPER_PREFIX in valor


# ---------------------------------------------------------------------------
# A MORDIDA — os cinco gestos dela
# ---------------------------------------------------------------------------


def test_salvar_na_aba_perfis_repoe_o_wrapper(
    biblioteca: Path, steam_fechada: None, disco: Path, monkeypatch: Any
) -> None:
    """"Salvar este perfil", DENTRO da guia de perfis.

    MORDIDA: arranque o ``pegar_carona_no_gesto`` do fim de
    ``profiles_actions.on_profile_save`` e a última asserção reprova — o
    Pragmata continua com a linha que comeu o wrapper.
    """
    assert not _tem_wrapper(biblioteca, PRAGMATA)

    janela = _janela(monkeypatch)
    janela.on_profile_save(None)

    assert _tem_wrapper(biblioteca, PRAGMATA)


def test_ativar_na_aba_perfis_repoe_o_wrapper(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """"Ativar", DENTRO da guia de perfis — o outro gesto que ela nomeou."""
    janela = _janela(monkeypatch)
    janela.on_profile_activate(None)

    assert _tem_wrapper(biblioteca, PRAGMATA)


def test_salvar_perfil_pelo_rodape_repoe_o_wrapper(
    biblioteca: Path, steam_fechada: None, disco: Path, monkeypatch: Any
) -> None:
    """"Salvar Perfil" do rodapé — FORA da guia de perfis, pelo funil.

    Este é o caminho que cobre três botões de uma vez (Salvar, Importar e
    Restaurar Padrão passam todos pelo ``_gravar_perfil_async``).
    """
    janela = _janela(monkeypatch)
    _salvar_pelo_rodape(janela)

    assert _tem_wrapper(biblioteca, PRAGMATA)


def test_botao_verde_aplicar_repoe_o_wrapper(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """O "Aplicar" verde do rodapé — o "aplicar" que mora fora da aba."""
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)

    assert _tem_wrapper(biblioteca, PRAGMATA)
    # E o gesto dela continua fazendo o que fazia: a carona é efeito colateral,
    # nunca substituta.
    assert janela.aplicou_o_rascunho == 1


# ---------------------------------------------------------------------------
# O reparo PRESERVA a linha dela — o Pragmata precisa dos dois
# ---------------------------------------------------------------------------


def test_o_reparo_nao_joga_fora_o_vkd3d_dela(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """Repor o wrapper jogando fora o `VKD3D_CONFIG` trocaria "o jogo não vê o
    controle" por "o jogo fecha sozinho" — a cura do crash de 14/08. Não é
    conserto nenhum, e já aconteceu de verdade em 16/08 às 03h33."""
    _janela(monkeypatch).on_apply_draft(None)

    linha = slo.read_apps_by_appid(biblioteca.read_text(encoding="utf-8"))[PRAGMATA]
    assert slo.WRAPPER_PREFIX in linha
    assert "VKD3D_CONFIG=no_upload_hvv" in linha
    assert linha.count("%command%") == 1


def test_quem_ja_tinha_o_wrapper_nao_e_tocado(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """Idempotência por construção: o Sackboy sai como entrou."""
    antes = slo.read_apps_by_appid(biblioteca.read_text(encoding="utf-8"))[SACKBOY]
    _janela(monkeypatch).on_apply_draft(None)
    depois = slo.read_apps_by_appid(biblioteca.read_text(encoding="utf-8"))[SACKBOY]
    assert depois == antes


# ---------------------------------------------------------------------------
# O QUE ELA VÊ — e o que ela NÃO vê
# ---------------------------------------------------------------------------


def test_sem_nada_a_reparar_a_carona_fica_muda(
    tmp_path: Path, steam_fechada: None, disco: Path, monkeypatch: Any
) -> None:
    """O caso comum: todo jogo com o wrapper. Nenhuma palavra no rodapé.

    Uma linha a cada Salvar viraria ruído no gesto mais comum da janela — e o
    pedido dela começa justamente recusando mais um clique.
    """
    alvo = tmp_path / "localconfig.vdf"
    alvo.write_text(_vdf({SACKBOY: slo.WRAPPER_LAUNCH}), encoding="utf-8")
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "discover_vdfs", lambda home=None: [alvo])
    monkeypatch.setattr(slo, "sem_wrapper_path", lambda *a, **k: tmp_path / "opt.txt")
    monkeypatch.setattr(
        sw, "caminho_do_registro", lambda home=None: tmp_path / "visto.json"
    )
    monkeypatch.setattr(slo, "nome_do_appid", lambda appid, home=None: None)

    janela = _janela(monkeypatch)
    _salvar_pelo_rodape(janela)

    assert not [t for t in janela.toasts if "Inicialização" in t]


def test_reparado_a_frase_nomeia_o_jogo(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """"1 jogo com problema" não ajuda ninguém a agir — a frase diz QUAL."""
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)

    frases = [t for t in janela.toasts if "Inicialização" in t]
    assert len(frases) == 1
    assert PRAGMATA in frases[0]
    assert "preservadas" in frases[0]


# ---------------------------------------------------------------------------
# A STEAM ABERTA — a restrição dura, e a vigia que a resolve
# ---------------------------------------------------------------------------


def test_com_a_steam_aberta_nao_escreve_e_avisa(
    biblioteca: Path, steam_aberta: None, monkeypatch: Any
) -> None:
    """Reparar com a Steam viva é jogar o reparo fora: ela regrava o vdf ao
    sair. Aconteceu em 16/08 e o reparo de 03h33 foi desfeito."""
    antes = biblioteca.read_text(encoding="utf-8")
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)

    assert biblioteca.read_text(encoding="utf-8") == antes
    assert not _tem_wrapper(biblioteca, PRAGMATA)
    frases = [t for t in janela.toasts if "Inicialização" in t]
    assert len(frases) == 1
    assert "Steam FECHADA" in frases[0]
    janela._carona_desarmar_vigia()


def test_o_aviso_nao_repete_no_mesmo_episodio(
    biblioteca: Path, steam_aberta: None, monkeypatch: Any
) -> None:
    """Ela salva cinco vezes seguidas com a Steam aberta: UM aviso, não cinco.

    O episódio é o CONJUNTO de jogos faltantes. Enquanto ele não mudar, a
    carona já disse o que tinha para dizer.
    """
    janela = _janela(monkeypatch)
    for _ in range(5):
        janela.on_apply_draft(None)

    assert len([t for t in janela.toasts if "Inicialização" in t]) == 1
    janela._carona_desarmar_vigia()


def test_um_episodio_novo_com_os_mesmos_jogos_volta_a_falar(
    biblioteca: Path, steam_aberta: None, monkeypatch: Any
) -> None:
    """Calar o repeteco é uma coisa; calar o episódio seguinte é outra.

    O roteiro é real: ela salva com a Steam aberta e é avisada; conserta a
    linha na mão (ou o `install.sh` conserta); um Salvar depois a carona diz
    "nada a fazer" e fica MUDA — e é aí que a memória do aviso tem de morrer.
    Semanas depois a Steam come o wrapper do MESMO jogo. Se o episódio velho
    ainda estivesse de pé, este segundo defeito nasceria silencioso.

    MORDIDA: tire o ``self._carona_ja_avisado = frozenset()`` do ramo "não
    adiado" de ``_carona_reagir`` e a última asserção volta a zero.
    """
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)
    assert len([t for t in janela.toasts if "Inicialização" in t]) == 1

    # Ela conserta na mão: agora todo jogo tem o wrapper, e a carona se cala.
    biblioteca.write_text(
        _vdf({PRAGMATA: slo.WRAPPER_LAUNCH, SACKBOY: slo.WRAPPER_LAUNCH}),
        encoding="utf-8",
    )
    janela.on_apply_draft(None)
    assert len([t for t in janela.toasts if "Inicialização" in t]) == 1
    assert janela._carona_vigia_id is None, "sem pendência, a vigia tinha de sair"

    # Semanas depois: a Steam come a linha do MESMO jogo. Episódio novo.
    biblioteca.write_text(
        _vdf({PRAGMATA: LINHA_PRAGMATA, SACKBOY: slo.WRAPPER_LAUNCH}),
        encoding="utf-8",
    )
    janela.on_apply_draft(None)

    assert len([t for t in janela.toasts if "Inicialização" in t]) == 2, (
        "o segundo episódio nasceu calado — a memória do primeiro não morreu"
    )
    janela._carona_desarmar_vigia()


def test_a_vigia_repara_sozinha_quando_a_steam_fecha(
    biblioteca: Path, steam_aberta: None, monkeypatch: Any
) -> None:
    """O coração do pedido dela: **ela não precisa lembrar de nada.**

    Salvou com a Steam aberta, o reparo foi adiado e uma vigia ficou armada.
    Quando ela fecha a Steam, o reparo simplesmente ACONTECE — sem clique,
    sem diálogo, sem ter de voltar à janela.
    """
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)
    assert not _tem_wrapper(biblioteca, PRAGMATA)
    assert janela._carona_vigia_id is not None, "a vigia tinha de ficar armada"

    # Um tique com a Steam ainda viva: barato, e não abre o vdf.
    janela._carona_tique_da_vigia()
    assert not _tem_wrapper(biblioteca, PRAGMATA)
    assert janela._carona_vigia_id is not None

    # Ela fecha a Steam. O tique seguinte repara e a vigia se desarma.
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: False)
        monkeypatch.setattr(mod, "steam_game_running", lambda: False)
    janela._carona_tique_da_vigia()

    assert _tem_wrapper(biblioteca, PRAGMATA)
    assert janela._carona_vigia_id is None, "reparado, a vigia tinha de sair"


def test_o_tique_da_vigia_nao_le_o_vdf_a_toa(
    biblioteca: Path, steam_aberta: None, monkeypatch: Any
) -> None:
    """A vigia bate de 45 em 45 segundos; ela não pode reler a biblioteca toda.

    NOTA HONESTA — este teste NÃO trava uma cura, trava um CUSTO. Arrancado o
    gate barato de ``passada(completa=False)``, nenhum outro teste deste
    arquivo reprova (medido por arrancamento em 16/08): a correção continua
    certa, porque `reparar_ou_adiar` recusa a Steam aberta de qualquer jeito.
    O que muda é o preço — o `localconfig.vdf` dela passa a ser lido inteiro a
    cada tique, para sempre, enquanto a Steam estiver de pé. Sem esta asserção
    isso sairia de fininho na primeira refatoração.
    """
    leituras: list[int] = []
    original = sw.discover_vdfs

    def _contando(home: Any = None) -> Any:
        leituras.append(1)
        return original(home)

    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)
    monkeypatch.setattr(sw, "discover_vdfs", _contando)

    janela._carona_tique_da_vigia()
    assert leituras == [], "o tique com a Steam viva abriu o vdf sem precisar"

    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: False)
        monkeypatch.setattr(mod, "steam_game_running", lambda: False)
    monkeypatch.setattr(sw, "discover_vdfs", _contando)
    janela._carona_tique_da_vigia()
    assert leituras, "com a Steam fechada o tique TEM de ler o vdf"
    janela._carona_desarmar_vigia()


def test_com_jogo_aberto_a_carona_nem_cogita(
    biblioteca: Path, monkeypatch: Any
) -> None:
    """Fechar a Steam com um jogo aberto mataria o jogo. A ordem dos portões
    da sentinela é jogo ANTES de Steam, e a carona a herda inteira."""
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: True)
        monkeypatch.setattr(mod, "steam_game_running", lambda: True)

    antes = biblioteca.read_text(encoding="utf-8")
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)

    assert biblioteca.read_text(encoding="utf-8") == antes
    frases = [t for t in janela.toasts if "Inicialização" in t]
    assert len(frases) == 1
    assert "o jogo e a Steam fecharem" in frases[0]
    janela._carona_desarmar_vigia()


# ---------------------------------------------------------------------------
# A recusa dela, a memória, e o que a carona NUNCA pode fazer
# ---------------------------------------------------------------------------


def test_jogo_que_ela_recusou_nao_recebe_o_wrapper_de_carona(
    biblioteca: Path, steam_fechada: None, tmp_path: Path, monkeypatch: Any
) -> None:
    """Intenção nunca é inferida, mas quando ela é DECLARADA, vale.

    O `jogos_sem_wrapper.txt` é a única voz que tira um jogo do reparo — e um
    gesto de salvar perfil não pode ser a porta dos fundos que desfaz isso.
    """
    (tmp_path / "jogos_sem_wrapper.txt").write_text(
        f"{PRAGMATA}\n", encoding="utf-8"
    )
    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)

    assert not _tem_wrapper(biblioteca, PRAGMATA)
    assert not [t for t in janela.toasts if "Inicialização" in t]


def test_a_carona_alimenta_a_memoria_de_quem_tinha_o_wrapper(
    biblioteca: Path, steam_fechada: None, tmp_path: Path, monkeypatch: Any
) -> None:
    """É o que separa "perdeu" de "nunca teve" na PRÓXIMA vez.

    Também é o que fecha, de graça, a única lacuna do botão "Aplicar aos jogos
    da Steam", que aplica em massa sem anotar nada.
    """
    _janela(monkeypatch).on_apply_draft(None)

    registro = json.loads((tmp_path / "wrapper-visto.json").read_text("utf-8"))
    assert SACKBOY in registro["appids"], "quem já tinha o wrapper é anotado"
    assert PRAGMATA in registro["appids"], "e quem acabou de receber, também"


def test_a_carona_nunca_derruba_o_gesto_dela(
    biblioteca: Path, steam_fechada: None, disco: Path, monkeypatch: Any
) -> None:
    """Salvar um perfil tem de salvar o perfil, aconteça o que acontecer.

    A carona é efeito colateral de um gesto dela; uma exceção aqui não pode
    virar "não consegui salvar". O perfil vai para o disco do mesmo jeito.
    """

    def _explode(**_k: Any) -> Any:
        raise RuntimeError("a Steam sumiu do mapa")

    monkeypatch.setattr(carona, "passada", _explode)

    janela = _janela(monkeypatch)
    _salvar_pelo_rodape(janela)

    assert (disco / "pragmata.json").exists()


def test_desligada_a_carona_nao_toca_em_nada(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """O desligador do `conftest.py` tem de valer de verdade — é ele que impede
    a suíte inteira de reescrever a biblioteca Steam DELA."""
    monkeypatch.setenv(carona.CARONA_ENV, "0")
    antes = biblioteca.read_text(encoding="utf-8")

    janela = _janela(monkeypatch)
    janela.on_apply_draft(None)

    assert biblioteca.read_text(encoding="utf-8") == antes
    assert janela.aplicou_o_rascunho == 1


# ---------------------------------------------------------------------------
# O PORTÃO — a cura não pode voltar a ser código que ninguém chama
# ---------------------------------------------------------------------------


def test_a_bandeja_tambem_repoe_o_wrapper(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """Trocar de perfil pela BANDEJA — o "fora da guia" mais longe da guia.

    É o caminho de quem nem abriu a janela, e a janela compacta sai do MESMO
    ``on_switch_profile``. Sem esta carona, quem só usa a bandeja nunca seria
    consertado: nenhum dos outros quatro gestos passa por aqui.

    MORDIDA: arranque o ``pegar_carona_no_gesto`` de
    ``HefestoApp._trocar_perfil_de_fora`` e a asserção do wrapper reprova.
    """
    from hefesto_dualsense4unix.app import app as app_mod

    trocados: list[str] = []
    monkeypatch.setattr(
        app_mod, "profile_switch", lambda nome: trocados.append(nome) or True
    )

    janela = _janela(monkeypatch)
    # O `HefestoApp` compõe a `ProfilesActionsMixin`; o dublê tem a mesma base,
    # então o método do app roda aqui sem subir GTK nenhum.
    resultado = app_mod.HefestoApp._trocar_perfil_de_fora(janela, "Pragmata")

    assert trocados == ["Pragmata"], "a troca de perfil dela tem de acontecer"
    assert resultado is True
    assert _tem_wrapper(biblioteca, PRAGMATA)


def test_a_bandeja_repara_mesmo_com_o_daemon_parado(
    biblioteca: Path, steam_fechada: None, monkeypatch: Any
) -> None:
    """O wrapper que a Steam comeu continua comido quando o daemon cai.

    Pendurar a carona no SUCESSO da troca seria deixar sem conserto justamente
    quem já está com meio produto quebrado. Por isso ela vai no ``finally``.
    """
    from hefesto_dualsense4unix.app import app as app_mod

    def _daemon_morto(_nome: str) -> bool:
        raise RuntimeError("daemon offline")

    monkeypatch.setattr(app_mod, "profile_switch", _daemon_morto)

    janela = _janela(monkeypatch)
    with pytest.raises(RuntimeError):
        app_mod.HefestoApp._trocar_perfil_de_fora(janela, "Pragmata")

    assert _tem_wrapper(biblioteca, PRAGMATA)


def test_os_cinco_gestos_chamam_a_carona() -> None:
    """`grep sentinela_do_wrapper app/` devolvia ZERO até 16/08.

    Este portão existe para que a resposta nunca volte a ser zero: cada gesto
    que ela nomeou tem de ter a chamada no fonte. Reprova antes mesmo de o
    teste de comportamento chegar lá, e diz qual arquivo perdeu o fio.
    """
    raiz = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
    esperado = {
        "app/actions/profiles_actions.py": 2,  # Salvar e Ativar, na aba
        "app/actions/profile_writer.py": 1,  # o funil: Salvar/Importar/Restaurar
        "app/actions/footer_actions.py": 1,  # o botão verde "Aplicar"
        "app/app.py": 1,  # bandeja e janela compacta, pelo mesmo método
    }
    for relativo, quantas in esperado.items():
        texto = (raiz / relativo).read_text(encoding="utf-8")
        achadas = texto.count("self.pegar_carona_no_gesto(")
        assert achadas == quantas, (
            f"{relativo}: {achadas} chamada(s) a pegar_carona_no_gesto, "
            f"esperadas {quantas} — um gesto do pedido dela ficou sem carona"
        )
