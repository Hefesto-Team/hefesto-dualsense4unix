"""SOM-02 / E4 — seção opcional `speaker` do perfil (persistência do volume)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from hefesto_dualsense4unix.app.draft_config import DraftConfig, SpeakerDraft
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileSpeakerConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, **kw: object) -> Profile:
    defaults: dict[str, object] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)  # type: ignore[arg-type]


class _BackendComAudio(FakeController):
    """Backend que CONTA as escritas de áudio e imita a posse do real.

    Espelha o contrato medido em `core/backend_pydualsense.py`:

      - `speaker_state_for` devolve **None** enquanto ninguém escreveu — é o
        que faz a chave `speaker` nem entrar no `daemon.state_full` e o rótulo
        da janela dizer "não ajustado";
      - depois de uma escrita devolve `{"volume": preferido, "muted": efetivo
        == 0}`, guardando a preferência para o par mudo/ativar sobreviver.
    """

    def __init__(self) -> None:
        super().__init__()
        self.escritas_de_audio: list[dict[str, Any]] = []
        self._pref: int | None = None
        self._efetivo: int | None = None

    def set_speaker_volume(
        self,
        volume: int | None = None,
        *,
        muted: bool | None = None,
        uniq: str | None = None,
        rota: int | None = None,
    ) -> bool:
        self.escritas_de_audio.append(
            {"volume": volume, "muted": muted, "uniq": uniq, "rota": rota}
        )
        pref = self._pref
        if volume is not None:
            pref = max(0, min(255, int(volume)))
        if pref is None:
            pref = 0
        self._pref = pref
        self._efetivo = 0 if muted else pref
        return True

    def speaker_state_for(self, uniq: str | None = None) -> dict[str, Any] | None:
        if self._efetivo is None:
            return None
        return {"volume": int(self._pref or 0), "muted": self._efetivo == 0}


def _applier_do_daemon(backend: _BackendComAudio):  # type: ignore[no-untyped-def]
    """O applier como o daemon o injetará: par (volume, muted) SEMPRE completo."""

    def aplicar(
        volume: int,
        muted: bool,
        *,
        uniq: str | None = None,
        origin: str = "manual",
        rota: int | None = None,
    ) -> bool:
        return bool(
            backend.set_speaker_volume(volume, muted=muted, uniq=uniq, rota=rota)
        )

    return aplicar


def _manager(
    backend: _BackendComAudio,
    store: StateStore | None = None,
    *,
    com_applier: bool = True,
) -> ProfileManager:
    return ProfileManager(
        controller=backend,
        store=store or StateStore(),
        speaker_applier=_applier_do_daemon(backend) if com_applier else None,
    )


def _store_com_audio_travado() -> StateStore:
    """Store com a categoria manual `"audio"` armada."""
    store = StateStore()
    store.mark_manual_trigger_active("audio")
    assert "audio" in store.manual_override_categories
    return store


def test_json_v1_sem_a_secao_continua_valido() -> None:
    """Aditivo sem bump de versão: JSON antigo valida e `speaker` fica None."""
    raw = {
        "name": "legado",
        "version": 1,
        "match": {"type": "any"},
        "priority": 0,
        "triggers": {
            "left": {"mode": "Off", "params": []},
            "right": {"mode": "Off", "params": []},
        },
        "leds": {"lightbar": [1, 2, 3], "player_leds": [False] * 5},
        "rumble": {"passthrough": True},
    }
    assert Profile.model_validate(raw).speaker is None


def test_secao_valida_com_default_de_mudo() -> None:
    cfg = ProfileSpeakerConfig(volume=180)
    assert (cfg.volume, cfg.muted) == (180, False)


@pytest.mark.parametrize("volume", [-1, 256])
def test_volume_fora_do_range_rejeitado(volume: int) -> None:
    with pytest.raises(ValidationError):
        ProfileSpeakerConfig(volume=volume)


def test_secao_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        ProfileSpeakerConfig(volume=100, headphone=100)  # type: ignore[call-arg]


def test_mudo_sem_volume_e_recusado_com_mensagem_que_explica() -> None:
    """A armadilha 1, barrada na BORDA do esquema."""
    with pytest.raises(ValidationError) as exc:
        ProfileSpeakerConfig(muted=True)  # type: ignore[call-arg]
    texto = str(exc.value)
    assert "volume" in texto
    assert "posse" in texto or "ZERO" in texto

    with pytest.raises(ValidationError):
        Profile.model_validate(
            {
                "name": "so_mudo",
                "match": {"type": "any"},
                "speaker": {"muted": True},
            }
        )


def test_profile_com_a_secao_roundtrip_json() -> None:
    p = _mk_profile("som", speaker={"volume": 180, "muted": True})
    p2 = Profile.model_validate(p.model_dump(mode="json"))
    assert p2.speaker is not None
    assert (p2.speaker.volume, p2.speaker.muted) == (180, True)


class _ProfileDeBinarioAntigo(BaseModel):
    """Encenação do binário ANTERIOR à sprint: não conhece `speaker`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: int = 1
    match: dict[str, Any]
    priority: int = 0
    triggers: dict[str, Any] | None = None
    leds: dict[str, Any] | None = None
    rumble: dict[str, Any] | None = None
    key_bindings: dict[str, Any] | None = None
    mouse: dict[str, Any] | None = None
    mic: dict[str, Any] | None = None
    mode: dict[str, Any] | None = None
    suppress_desktop_emulation: bool = False
    controllers: dict[str, Any] | None = None


def test_save_de_perfil_sem_a_secao_nao_grava_a_chave(
    isolated_profiles_dir: Path,
) -> None:
    """Critério 2: `load -> save` de perfil sem a seção não acrescenta a chave."""
    import json

    caminho = save_profile(_mk_profile("legado"))
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    assert "speaker" not in bruto

    caminho2 = save_profile(load_profile("legado"))
    assert "speaker" not in json.loads(caminho2.read_text(encoding="utf-8"))


def test_binario_antigo_ainda_carrega_perfil_salvo_por_este(
    isolated_profiles_dir: Path,
) -> None:
    """Critério 4: é ESTA asserção que a omissão do None existe para salvar."""
    import json

    caminho = save_profile(_mk_profile("legado"))
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    _ProfileDeBinarioAntigo.model_validate(bruto)


def test_nenhuma_secao_opcional_none_e_gravada(isolated_profiles_dir: Path) -> None:
    """A omissão vale para TODAS as seções opcionais, não só a nova."""
    import json

    caminho = save_profile(_mk_profile("legado"))
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    for chave in ("speaker", "mouse", "mic", "mode", "key_bindings", "controllers"):
        assert chave not in bruto, f"{chave} não deveria estar no arquivo"


def test_teclado_silencioso_sobrevive_ao_save(isolated_profiles_dir: Path) -> None:
    """A omissão é do `None`, NUNCA do vazio."""
    import json

    caminho = save_profile(_mk_profile("silencioso", key_bindings={}))
    assert json.loads(caminho.read_text(encoding="utf-8"))["key_bindings"] == {}
    assert load_profile("silencioso").key_bindings == {}


def test_save_de_perfil_com_a_secao_grava_a_chave(
    isolated_profiles_dir: Path,
) -> None:
    """A omissão vale para o None — não para o dado. Perfil que USA a seção a"""
    import json

    caminho = save_profile(
        _mk_profile("com_som", speaker={"volume": 200, "muted": False})
    )
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    assert bruto["speaker"] == {"volume": 200, "muted": False}
    with pytest.raises(ValidationError):
        _ProfileDeBinarioAntigo.model_validate(bruto)


def test_perfil_sem_a_secao_nao_produz_escrita_de_audio(
    isolated_profiles_dir: Path,
) -> None:
    """Critério 1, contando as chamadas ao BACKEND."""
    save_profile(_mk_profile("v1_puro"))
    backend = _BackendComAudio()
    backend.connect()
    _manager(backend).activate("v1_puro")

    assert backend.escritas_de_audio == []
    assert backend.speaker_state_for() is None


def test_perfil_com_a_secao_escreve_o_par_completo(
    isolated_profiles_dir: Path,
) -> None:
    save_profile(_mk_profile("som", speaker={"volume": 180, "muted": False}))
    backend = _BackendComAudio()
    backend.connect()
    _manager(backend).activate("som")

    assert backend.escritas_de_audio == [
        {"volume": 180, "muted": False, "uniq": None, "rota": None}
    ]


def test_o_canal_do_perfil_chega_ao_controle(isolated_profiles_dir: Path) -> None:
    """SOM-ROTA-01/perfil (09/08/2026): o campo GUARDADO passa a ser ESCRITO."""
    save_profile(
        _mk_profile("todo_o_pc", speaker={"volume": 180, "rota": 3})
    )
    backend = _BackendComAudio()
    backend.connect()
    _manager(backend).activate("todo_o_pc")

    assert backend.escritas_de_audio == [
        {"volume": 180, "muted": False, "uniq": None, "rota": 3}
    ]


def test_perfil_sem_canal_nao_toca_o_byte_do_microfone(
    isolated_profiles_dir: Path,
) -> None:
    """A outra metade da regra, e a mais cara: ``None`` é NÃO ESCREVER."""
    save_profile(_mk_profile("legado_sem_canal", speaker={"volume": 120}))
    backend = _BackendComAudio()
    backend.connect()
    _manager(backend).activate("legado_sem_canal")

    assert backend.escritas_de_audio[0]["rota"] is None


def test_trocar_de_perfil_muda_o_volume_e_o_estado_publica(
    isolated_profiles_dir: Path,
) -> None:
    """Critério 3: trocar de perfil muda o volume e a chave `speaker` aparece."""
    save_profile(_mk_profile("baixo", speaker={"volume": 60}))
    save_profile(_mk_profile("alto", speaker={"volume": 220}))
    backend = _BackendComAudio()
    backend.connect()
    manager = _manager(backend)

    manager.activate("baixo")
    assert backend.speaker_state_for() == {"volume": 60, "muted": False}
    manager.activate("alto")
    assert backend.speaker_state_for() == {"volume": 220, "muted": False}
    assert [e["volume"] for e in backend.escritas_de_audio] == [60, 220]


def test_nenhuma_escrita_sai_sem_volume(isolated_profiles_dir: Path) -> None:
    """A regra dura que atravessa a sprint: nunca um `speaker.set` sem volume."""
    save_profile(_mk_profile("mudo", speaker={"volume": 180, "muted": True}))
    backend = _BackendComAudio()
    backend.connect()
    _manager(backend).activate("mudo")

    assert backend.escritas_de_audio == [
        {"volume": 180, "muted": True, "uniq": None, "rota": None}
    ]
    assert all(e["volume"] is not None for e in backend.escritas_de_audio)
    assert backend.speaker_state_for() == {"volume": 180, "muted": True}


def test_sem_applier_a_secao_e_ignorada_sem_quebrar(
    isolated_profiles_dir: Path,
) -> None:
    """CLI/testes sem daemon: applier None = seção ignorada, ativação ok."""
    save_profile(_mk_profile("som", speaker={"volume": 180}))
    backend = _BackendComAudio()
    backend.connect()
    perfil = _manager(backend, com_applier=False).activate("som")
    assert perfil.name == "som"
    assert backend.escritas_de_audio == []


def test_applier_que_levanta_nao_aborta_a_ativacao(
    isolated_profiles_dir: Path,
) -> None:
    save_profile(_mk_profile("som", speaker={"volume": 180}))

    def boom(*_a: object, **_kw: object) -> None:
        raise RuntimeError("controle sumiu no meio")

    backend = _BackendComAudio()
    backend.connect()
    store = StateStore()
    manager = ProfileManager(controller=backend, store=store, speaker_applier=boom)
    relatorio: dict[str, str] = {}
    perfil = manager.activate("som", relatorio=relatorio)

    assert perfil.name == "som"
    assert store.active_profile == "som"
    assert relatorio["speaker"] == "falhou"


def test_reaplica_no_connect_so_com_a_secao(isolated_profiles_dir: Path) -> None:
    """Armadilha 4: a posse morre com o cabo, e o volume também."""
    save_profile(_mk_profile("som", speaker={"volume": 180}))
    save_profile(_mk_profile("v1_puro"))
    backend = _BackendComAudio()
    backend.connect()
    store = StateStore()
    manager = _manager(backend, store)

    manager.activate("som")
    backend.escritas_de_audio.clear()
    assert manager.reapply_speaker_on_connect() == "aplicado"
    assert backend.escritas_de_audio == [
        {"volume": 180, "muted": False, "uniq": None, "rota": None}
    ]

    manager.activate("v1_puro")
    backend.escritas_de_audio.clear()
    assert manager.reapply_speaker_on_connect() is None
    assert backend.escritas_de_audio == []


def test_reaplica_no_connect_sem_perfil_ativo_nao_escreve(
    isolated_profiles_dir: Path,
) -> None:
    backend = _BackendComAudio()
    backend.connect()
    manager = _manager(backend)
    assert manager.reapply_speaker_on_connect() is None
    assert backend.escritas_de_audio == []


def test_reaplica_no_connect_roteia_por_uniq(isolated_profiles_dir: Path) -> None:
    """A reaplicação é do controle que CHEGOU, não de todos."""
    save_profile(_mk_profile("som", speaker={"volume": 90}))
    backend = _BackendComAudio()
    backend.connect()
    manager = _manager(backend)
    manager.activate("som")
    backend.escritas_de_audio.clear()

    manager.reapply_speaker_on_connect(uniq="aabbcc000002")

    assert backend.escritas_de_audio == [
        {"volume": 90, "muted": False, "uniq": "aabbcc000002", "rota": None}
    ]


def test_from_profile_popula_o_rascunho_sem_dirty() -> None:
    draft = DraftConfig.from_profile(
        _mk_profile("som", speaker={"volume": 200, "muted": True})
    )
    assert (draft.speaker.volume, draft.speaker.muted) == (200, True)
    assert draft.speaker.in_profile is True
    assert draft.speaker.dirty is False


def test_from_profile_sem_a_secao_usa_o_default_sem_volume() -> None:
    draft = DraftConfig.from_profile(_mk_profile("legado"))
    assert draft.speaker == SpeakerDraft()
    assert draft.speaker.volume is None


def test_to_profile_sem_toque_e_sem_origem_omite_a_secao() -> None:
    assert DraftConfig().to_profile("intocado").speaker is None


def test_to_profile_nao_inventa_secao_com_rascunho_sem_volume() -> None:
    """Rascunho marcado mas sem número não vira seção pela metade."""
    draft = DraftConfig().model_copy(
        update={"speaker": SpeakerDraft(muted=True, dirty=True, in_profile=True)}
    )
    assert draft.to_profile("sem_numero").speaker is None


def test_roundtrip_perfil_com_a_secao_preserva(isolated_profiles_dir: Path) -> None:
    original = _mk_profile("som", speaker={"volume": 200, "muted": True})
    salvo = DraftConfig.from_profile(original).to_profile("som", priority=10)
    assert salvo.speaker is not None
    assert (salvo.speaker.volume, salvo.speaker.muted) == (200, True)


def test_roundtrip_perfil_legado_inalterado() -> None:
    """Perfil sem a seção atravessa from_profile -> to_profile sem ganhá-la."""
    original = Profile(
        name="legado",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(lightbar=(10, 20, 30), player_leds=[False] * 5),
    )
    salvo = DraftConfig.from_profile(original).to_profile("legado", priority=5)
    assert salvo.speaker is None
    assert salvo.model_dump(mode="json") == original.model_dump(mode="json")
