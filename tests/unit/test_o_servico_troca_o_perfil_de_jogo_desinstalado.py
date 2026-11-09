"""O-SERVICO-TROCA-O-PERFIL-ATIVO-DE-JOGO-DESINSTALADO-01: o serviço devolve o padrão sem a aba.

O perfil ativo cujo jogo saiu do disco sai no passo do autoswitch, ao subir e quando a biblioteca
muda, sem aba aberta: o sistema devolve o que o restore devolveria (o último jogo, senão a escolha
do usuário), e sem nada nenhum perfil fica ativo. A biblioteca é a de mentira do lar isolado.

AS MORDIDAS: tire o `_o_desinstalado_sai` do `_tick`, e o perfil fica; tire o `bool(foto.nomes)`
do `fora_do_disco`, e a Steam sem leitura troca o perfil do usuário; tire o `casa_a_janela`, e o
jogo em cena perde o perfil; tire o `self._chave = chave`, e o laço pergunta ao disco a cada volta;
troque a devolução por `activate("Freestyle", origin="manual")`, e o próximo jogo não troca.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations import jogos_locais
from hefesto_dualsense4unix.profiles import jogo_desinstalado
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

NENHUM = ("—", "soltar")


class _Gerente:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.pedidos: list[tuple[str, str]] = []
        self.recusar = False

    def activate(self, nome: str, *, origin: str = "manual", **_: Any) -> None:
        if self.recusar:
            raise RuntimeError("o daemon recusou")
        self.pedidos.append((nome, origin))
        self.store.set_active_profile(nome)

    def soltar_o_perfil(self) -> None:
        if self.recusar:
            raise RuntimeError("o daemon recusou")
        self.pedidos.append(NENHUM)
        self.store.set_active_profile(None)


@pytest.fixture(autouse=True)
def _lar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for var, rel in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_STATE_HOME", ".local/state")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    for nome in ("_NOMES_DOS_JOGOS", "_FORA_DO_DISCO"):
        monkeypatch.setattr(jogo_desinstalado, nome, None)
    monkeypatch.setattr(jogos_locais, "_NOMES_DAS_JANELAS", None, raising=False)


def _instalar(appid: str, nome: str) -> None:
    from hefesto_dualsense4unix.integrations.proton_pin import default_steam_root

    pasta = default_steam_root() / "steamapps"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n', encoding="utf-8")


def _perfis() -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile

    save_profile(Profile(name="Instalado", priority=90,
                         match=MatchCriteria(window_class=["steam_app_9100001"])))
    save_profile(Profile(name="Ativo fora", priority=70,
                         match=MatchCriteria(window_class=["steam_app_9100003"])))
    save_profile(Profile(name="Sem jogo", priority=60, match=MatchAny()))


def _servico(ativo: str, janela: str = "") -> tuple[AutoSwitcher, _Gerente]:
    store = StateStore()
    store.set_active_profile(ativo)
    gerente = _Gerente(store)
    sw = AutoSwitcher(manager=gerente, window_reader=lambda: {"wm_class": janela},  # type: ignore[arg-type]
                      store=store)
    sw._decidir = lambda info, now: None  # type: ignore[method-assign]
    return sw, gerente


def _volta(sw: AutoSwitcher, tempo: float = 0.0) -> None:
    info = sw._ler_fora_do_laco()
    sw._tick(info, tempo)


def test_ao_subir_o_ativo_de_jogo_desinstalado_vira_o_padrao_uma_vez() -> None:
    """Prova da D-0811-O-PERFIL-ATIVO-DE-JOGO-DESINSTALADO-TAMBEM-SE-OCULTA."""
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    sw, gerente = _servico("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == [NENHUM]
    _volta(sw)
    assert len(gerente.pedidos) == 1


def test_quando_a_biblioteca_muda_o_ativo_que_perdeu_o_jogo_troca(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar("9100001", "Jogo Instalado")
    _instalar("9100003", "Jogo Ativo")
    _perfis()
    sw, gerente = _servico("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == []
    from hefesto_dualsense4unix.integrations.proton_pin import default_steam_root

    (default_steam_root() / "steamapps" / "appmanifest_9100003.acf").unlink()
    gerente.store.set_active_profile("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == [NENHUM]


def test_perfil_ativado_depois_tambem_e_visto() -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    sw, gerente = _servico("Instalado")
    _volta(sw)
    assert gerente.pedidos == []
    gerente.store.set_active_profile("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == [NENHUM]


def test_instalado_ou_sem_jogo_nao_troca() -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    for ativo in ("Instalado", "Sem jogo"):
        sw, gerente = _servico(ativo)
        _volta(sw)
        assert gerente.pedidos == []


def test_sem_biblioteca_legivel_nada_se_troca() -> None:
    _perfis()
    sw, gerente = _servico("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == []


def test_com_a_leitura_da_steam_falhando_nada_se_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()

    def falha() -> dict[str, str]:
        raise OSError("biblioteca ilegível")

    monkeypatch.setattr(jogo_desinstalado, "nomes_dos_jogos", falha)
    sw, gerente = _servico("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == []


def test_com_a_janela_do_jogo_em_cena_nao_troca() -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    sw, gerente = _servico("Ativo fora", janela="steam_app_9100003")
    _volta(sw)
    assert gerente.pedidos == []


def test_o_pedido_recusado_volta_depois_da_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    sw, gerente = _servico("Ativo fora")
    gerente.recusar = True
    _volta(sw)
    _volta(sw)
    assert gerente.pedidos == []
    gerente.recusar = False
    _volta(sw)
    assert gerente.pedidos == []
    monkeypatch.setattr(jogo_desinstalado, "ESPERA_DEPOIS_DA_FALHA_S", 0.0)
    _volta(sw)
    assert gerente.pedidos == [NENHUM]


def test_volta_a_escolha_do_usuario_pela_origem_do_restore() -> None:
    from hefesto_dualsense4unix.utils.session import load_last_profile, save_last_profile

    _instalar("9100001", "Jogo Instalado")
    _perfis()
    save_last_profile("Sem jogo")
    sw, gerente = _servico("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == [("Sem jogo", "system")]
    assert load_last_profile() == "Sem jogo"


def test_o_desinstalado_sai_da_escolha_e_do_ultimo_jogo() -> None:
    from hefesto_dualsense4unix.utils.session import (
        a_escolha_do_usuario,
        lembrar_o_ultimo_jogo,
        o_ultimo_jogo,
        save_last_profile,
    )

    _instalar("9100001", "Jogo Instalado")
    _perfis()
    save_last_profile("Ativo fora")
    lembrar_o_ultimo_jogo("Ativo fora")
    sw, gerente = _servico("Ativo fora")
    _volta(sw)
    assert gerente.pedidos == [NENHUM]
    assert a_escolha_do_usuario(freestyle_ligado=False) is None
    assert o_ultimo_jogo() is None
    _volta(sw)
    assert gerente.pedidos == [NENHUM]


def test_o_proximo_jogo_troca_o_perfil_depois_da_troca() -> None:
    """Prova da D-0811-O-PERFIL-ATIVO-DE-JOGO-DESINSTALADO-TAMBEM-SE-OCULTA.

    A troca não trava a troca por jogo: nem o Modo Freestyle liga, nem a trava da mão arma.

    MORDIDA: devolva `activate("Freestyle", origin="manual")` no `_o_desinstalado_sai` e o
    perfil do jogo aberto não entra.
    """
    import time

    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager, o_freestyle_manda
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    _instalar("9100001", "Jogo Instalado")
    _perfis()
    save_profile(Profile(name="Freestyle", priority=0, match=MatchAny()))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    gerente = ProfileManager(controller=fc, store=store)
    gerente.activate("Ativo fora", origin="autoswitch")
    janela = {"wm_class": "kodi"}
    sw = AutoSwitcher(manager=gerente, window_reader=lambda: dict(janela), store=store)
    agora = 0.0
    for _ in range(4):
        agora += 1.0
        sw._tick(sw._ler_fora_do_laco(), agora)
    assert store.active_profile != "Ativo fora"
    assert not o_freestyle_manda(store)
    assert not store.manual_profile_lock_active(time.monotonic())
    janela["wm_class"] = "steam_app_9100001"
    for _ in range(30):
        agora += 1.0
        sw._tick(sw._ler_fora_do_laco(), agora)
    assert store.active_profile == "Instalado"


def test_a_pergunta_repetida_nao_le_o_catalogo(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar("9100001", "Jogo Instalado")
    _perfis()
    sw, _gerente = _servico("Instalado")
    _volta(sw)
    leituras: list[int] = []
    original = jogo_desinstalado.foto_do_catalogo
    monkeypatch.setattr(jogo_desinstalado, "foto_do_catalogo",
                        lambda: leituras.append(1) or original())
    for _ in range(5):
        _volta(sw)
    assert leituras == []
