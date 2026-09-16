"""SOM-ROTA-03 — o replug devolve a escolha DAQUELA PEÇA, não a global.

O DEFEITO, medido em 16/09/2026 sobre cópias dos perfis reais dela: o gancho
`reapply_speaker_on_connect` olhava só `profile.speaker`, a seção GLOBAL, e
desistia sem ela. Só que o alto-falante é da PEÇA — decisão dela de 10/08 — e os
perfis dela guardam o som exclusivamente em ``controllers[uniq].speaker``:

    personalizado.json        global_speaker: null · d42f4b…d8 -> rota 3, mudo
    sackboy…adventure.json    global_speaker: null · 444648…03 -> rota 2

Nos dois, o gancho devolvia ``None`` e a lista de chamadas ao applier ficava
VAZIA. Efeito: **a escolha dela nunca voltava depois de um replug.** A posse dos
bytes de áudio morre com o cabo (cada conexão cria um handle novo), então a
última palavra ficava sendo a da ADOÇÃO — `ROTA_PADRAO_DO_SOM` —, e o "rota 3 +
mudo" que ela gravou sumia ao trocar o cabo, sem recado.

E o mesmo defeito existia com o SINAL TROCADO: quando havia global, o gancho
mandava a GLOBAL para o ``uniq`` que voltou e ignorava o override da peça — o
replug pisava o ajuste dela.

A cura não inventa caminho: reusa a vista ``model_copy`` de
``apply_controller_speakers`` e a ordem que ``apply`` já respeita — global
primeiro, peça por cima.

AS MORDIDAS: exigir a seção global de volta cala o gancho nos perfis dela; e
aplicar só a global faz o replug pisar o override.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.profiles.manager import ProfileManager
#: O construtor vem da régua VIZINHA da mesma seção: as duas medem o mesmo
#: `ProfileSpeakerConfig` e não podem divergir no que é "um perfil válido".
from tests.unit.test_profile_speaker_section import _mk_profile

from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    Profile,
    ProfileSpeakerConfig,
)

#: As duas peças da mesa dela, mascaradas: o octeto 4 e o 5 zerados.
PECA_A = "aa:bb:cc:00:00:01"
PECA_B = "aa:bb:cc:00:00:02"


class _Loja:
    def __init__(self, nome: str) -> None:
        self.active_profile = nome


def _manager(profile: Profile, monkeypatch: Any) -> tuple[ProfileManager, list[dict]]:
    """`ProfileManager` real; só o applier e o `load_profile` são de mentira.

    Real de propósito: o que se afere é o gancho que roda na máquina dela, e um
    dublê de manager provaria apenas que a linha foi digitada.
    """
    chamadas: list[dict] = []

    def applier(volume: int, muted: bool, **kw: Any) -> str:
        chamadas.append({"volume": volume, "muted": muted, **kw})
        return "aplicado"

    import hefesto_dualsense4unix.profiles.manager as m

    monkeypatch.setattr(m, "load_profile", lambda _n: profile)
    inst = ProfileManager.__new__(ProfileManager)
    inst.store = _Loja("o-perfil-dela")  # type: ignore[attr-defined]
    inst.speaker_applier = applier  # type: ignore[attr-defined]
    return inst, chamadas


def _perfil(
    *, global_: ProfileSpeakerConfig | None, por_peca: dict[str, ProfileSpeakerConfig]
) -> Profile:
    return _mk_profile(
        "o-perfil-dela",
        speaker=global_,
        controllers={
            u: ControllerOverrides(speaker=s) for u, s in por_peca.items()
        },
    )


class TestOReplugDevolveOQueElaGravou:
    def test_o_perfil_sem_global_volta_a_ser_aplicado(self, monkeypatch: Any) -> None:
        """A MORDIDA: exigir `profile.speaker` de novo cala isto por inteiro.

        É a forma exata dos perfis dela — som só por peça, global nenhuma.
        """
        p = _perfil(
            global_=None,
            por_peca={PECA_A: ProfileSpeakerConfig(volume=102, muted=True, rota=3)},
        )
        inst, chamadas = _manager(p, monkeypatch)

        assert inst.reapply_speaker_on_connect(PECA_A) == "aplicado"

        assert len(chamadas) == 1
        assert chamadas[0]["rota"] == 3
        assert chamadas[0]["muted"] is True
        assert chamadas[0]["uniq"] == PECA_A

    def test_a_peca_vence_a_global_no_replug(self, monkeypatch: Any) -> None:
        """A MORDIDA: aplicar só a global faz o replug pisar o ajuste dela."""
        p = _perfil(
            global_=ProfileSpeakerConfig(volume=102, muted=False, rota=2),
            por_peca={PECA_A: ProfileSpeakerConfig(volume=102, muted=True, rota=3)},
        )
        inst, chamadas = _manager(p, monkeypatch)

        inst.reapply_speaker_on_connect(PECA_A)

        assert chamadas, "o gancho não escreveu nada"
        ultima = chamadas[-1]
        assert ultima["rota"] == 3, "quem escreve por último é a peça"
        assert ultima["muted"] is True

    def test_a_peca_sem_opiniao_fica_com_a_global(self, monkeypatch: Any) -> None:
        """"Sem opinião" continua querendo dizer "herda", como em toda seção."""
        p = _perfil(
            global_=ProfileSpeakerConfig(volume=90, muted=False, rota=2),
            por_peca={PECA_A: ProfileSpeakerConfig(volume=102, muted=True, rota=3)},
        )
        inst, chamadas = _manager(p, monkeypatch)

        inst.reapply_speaker_on_connect(PECA_B)

        assert len(chamadas) == 1
        assert chamadas[0]["volume"] == 90
        assert chamadas[0]["rota"] == 2

    def test_sem_opiniao_nenhuma_o_gancho_continua_calado(
        self, monkeypatch: Any
    ) -> None:
        """A guarda da E4 fica de pé: sem pedido, não se toma posse no replug."""
        p = _perfil(global_=None, por_peca={})
        inst, chamadas = _manager(p, monkeypatch)

        assert inst.reapply_speaker_on_connect(PECA_A) is None
        assert chamadas == []

    def test_sem_uniq_o_gancho_ainda_atende_a_global(self, monkeypatch: Any) -> None:
        """O caminho antigo (broadcast, sem `uniq`) não pode ter regredido."""
        p = _perfil(
            global_=ProfileSpeakerConfig(volume=102, muted=False, rota=2),
            por_peca={PECA_A: ProfileSpeakerConfig(volume=102, muted=True, rota=3)},
        )
        inst, chamadas = _manager(p, monkeypatch)

        assert inst.reapply_speaker_on_connect(None) == "aplicado"

        assert len(chamadas) == 1, "sem uniq não se escolhe peça nenhuma"
        assert chamadas[0]["rota"] == 2
