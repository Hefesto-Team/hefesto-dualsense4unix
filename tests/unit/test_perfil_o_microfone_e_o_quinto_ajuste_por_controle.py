"""MIC-QUINTO-AJUSTE-01 (03/09/2026) — o microfone entra no perfil POR CONTROLE.

A DECISÃO DELA, e é ela que abre este arquivo
----------------------------------------------
*"4 controles os 4 tem que ter canais de entrada
unico pra cada qual."*  (noqa-acento: citação literal dela)

Com o canal por controle, o ajuste que faz aquele canal funcionar deixa de
caber num valor só para a mesa: **um controle no cabo e outro no rádio precisam
poder ter tratamentos diferentes.** Por isso o microfone vira o QUINTO ajuste de
``ControllerOverrides``, ao lado de luz, gatilhos, vibração e alto-falante.

O QUE ENTROU, E POR QUE SÓ ISSO
--------------------------------
``ProfileMicConfig`` tem TRÊS campos e ``ControllerMicOverride`` aceita UM. Não
é economia: é a ordem que esta casa não inverte — **primeiro o caminho por
unidade EXISTIR, depois o campo entrar no esquema.** Campo que grava e ninguém
lê é pior que campo nenhum: ele faz a coluna "Ajuste próprio" da aba Perfis
acender sobre um valor que nada aplica.

- ``muted`` — **entra.** ``set_microphone_mute(muted, uniq=…)`` →
  ``_handle_for(uniq)`` casa o MAC com o handle daquela peça.
- ``volume`` — fica fora. ``Daemon.apply_profile_mic`` resolve a fonte com
  ``fonte_de_captura_do_controle()``, a PRIMEIRA da lista; na mesa cheia o
  número iria para o microfone do vizinho.
- ``button_toggles_system`` — fica fora. ``hotkey.mic_button_loop`` lê
  ``daemon.config``, que é UM por máquina.

Os dois "não" são recusados na BORDA, com a razão na mensagem — a mesma
disciplina do ``custom_mult`` do rumble e do ``auto`` por unidade. E cada um tem
fio de gatilho em
``tests/unit/test_perfil_por_controle_o_campo_espera_o_caminho.py``: quando a
costura nascer, o fio fica vermelho e diz qual campo trazer.

A GUARDA QUE NÃO PODE SER COPIADA
----------------------------------
``muted`` é o mudo do FIRMWARE, o mesmo que apaga o LED vermelho, e a exceção
MIC-GRAVACAO-01 só o deixa atravessar a troca EXPLÍCITA de perfil. Se
``apply_controller_mics`` tivesse a própria cópia dessa regra, o perfil de um
jogo voltaria a roubar o mudo dela no meio de uma gravação — o defeito que a
AUDIT-FINDING-PROFILE-MIC-LED-RESET-01 fechou. Por isso o método REUSA
``apply_mic`` verbatim, e há teste abaixo que prova a herança da guarda.

AS MORDIDAS (o que arrancar para ver reprovar)
-----------------------------------------------
1. apagar ``mic: ControllerMicOverride | None = None`` de ``ControllerOverrides``;
2. tirar o ``uniq=str(uniq)`` da chamada em ``apply_controller_mics``;
3. apagar a linha ``self.apply_controller_mics(...)`` de ``_apply_appliers``;
4. apagar o validador ``_o_que_ainda_nao_tem_caminho_por_peca`` do esquema.

Endereços de rádio: faixa SINTÉTICA da casa (``aabbcc…``) — nunca o OUI de um
aparelho real.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileMicConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import (
    BRANCO,
    PRETO,
    _StoreSemTrava,
)


class _StoreComTrava(_StoreSemTrava):
    """A trava manual de áudio ARMADA — ela acabou de mexer no mic na mão."""

    manual_override_categories: tuple[str, ...] = ("audio",)


def _gerente(applier: Any, *, store: Any = None) -> ProfileManager:
    return ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=store if store is not None else _StoreSemTrava(),  # type: ignore[arg-type]
        mic_applier=applier,
    )


def _espiao() -> tuple[Any, list[tuple[int | None, bool | None, str | None, str]]]:
    """Applier de dublê que anota ``(volume, muted, uniq, origin)`` de cada ordem."""
    chamadas: list[tuple[int | None, bool | None, str | None, str]] = []

    def applier(
        volume: int | None = None,
        muted: bool | None = None,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
    ) -> str:
        chamadas.append((volume, muted, uniq, origin))
        return "aplicado"

    return applier, chamadas


# ---------------------------------------------------------------------------
# O ESQUEMA — o campo existe, é o quinto, e o que sobra é recusado com a razão
# ---------------------------------------------------------------------------


def test_o_microfone_e_o_quinto_ajuste_por_controle() -> None:
    """O ``mic`` é o QUINTO, depois de luz, gatilhos, vibração e alto-falante.

    MORDIDA 1: apagar o campo de ``ControllerOverrides`` — a lista encurta e o
    prefixo deixa de casar. Trocar a ORDEM reprova igual, e é a metade que
    importa: quem lê o esquema conta as seções na ordem em que elas aparecem.

    **O SEXTO NASCEU EM 04/09/2026, e esta régua reprovou por isso.** Ela cravava
    a lista INTEIRA (``== [leds, triggers, rumble, speaker, mic]``), e a ONDA1-D3
    acrescentou ``sensores`` — o interruptor de giroscópio e acelerômetro por
    peça, decisão dela (*"ele tem que funcionar de verdade. ambos independente do
    modo e da mascara."*).  <!-- noqa-acento: citação literal dela -->
    Medido com ``list(ControllerOverrides.model_fields)``:
    ``['leds', 'triggers', 'rumble', 'speaker', 'mic', 'sensores']``.

    O QUE ESTA RÉGUA AFIRMA continua sendo o que o título deste arquivo diz — o
    microfone é o quinto —, e ela passou a afirmar SÓ isso. Cravar o comprimento
    total nunca foi o contrato: obrigaria toda frente que abrir um ajuste novo
    por controle a vir editar um arquivo sobre microfone, e foi assim que a
    ONDA1-D3 deixou este arquivo vermelho sem tocar numa linha dele.
    """
    assert list(ControllerOverrides.model_fields)[:5] == [
        "leds",
        "triggers",
        "rumble",
        "speaker",
        "mic",
    ]


def test_o_override_e_subconjunto_estrito_do_global() -> None:
    """``ControllerMicOverride`` só pode ter campos que o global também tem.

    É o que torna honesta a vista (``model_copy(update={"mic": override})``) que
    ``apply_controller_mics`` usa para reusar ``apply_mic``: o applier lê a
    seção por ``getattr`` e um campo que só existisse no override sumiria calado
    no caminho.
    """
    do_override = set(ControllerMicOverride.model_fields)
    do_global = set(ProfileMicConfig.model_fields)
    assert do_override <= do_global, (
        f"campo(s) só no override: {sorted(do_override - do_global)} — "
        "`apply_mic` lê a seção por getattr e não os veria"
    )
    # O CONJUNTO É `{muted, volume}` DESDE 03/09/2026 — ela mandou abrir o
    # volume por peça, e o applier já o consumia (`apply_mic` lê a seção por
    # `getattr(secao, "volume"/"muted")`).
    #
    # E ELE DEIXOU DE SER DIGITADO: a régua cobra a RELAÇÃO — todo campo do
    # override tem de existir no global —, que é o contrato de verdade. Uma
    # lista literal aqui obrigaria alguém a vir editar duas vezes a cada campo
    # novo, e foi assim que ela reprovou a abertura do `volume` no mesmo dia.
    assert do_override <= do_global, (
        f"o override tem campo que o global não tem: {do_override - do_global}. "
        "O override é subconjunto do global por construção — `apply_mic` lê a "
        "seção por `getattr`, e um campo só daqui não teria quem o lesse.")
    assert do_override, "o override ficou vazio — nenhum ajuste de mic por peça"
    # E O QUE FICA DE FORA CONTINUA FORA, com a razão na borda. Sem esta
    # metade, abrir `button_toggles_system` passaria calado.
    assert "button_toggles_system" not in do_override, (
        "`button_toggles_system` entrou no override: ele é UM por máquina "
        "(`hotkey.mic_button_loop` lê `daemon.config`, sem consultar uniq), e "
        "quatro controles gravariam quatro opiniões sobre um interruptor só")


def test_o_que_continua_recusado_diz_a_medicao_na_mensagem() -> None:
    """"Extra inputs are not permitted" mandaria procurar no lugar errado.

    O `volume` SAIU desta lista em 03/09/2026 — ela mandou abri-lo. O que
    sobrou é `button_toggles_system`, e a razão dele NÃO é decisão: o
    interruptor é UM por máquina, e a mensagem tem de dizer isso, senão quem
    esbarrar nele vai procurar a palavra dela em vez do limite técnico.

    MORDIDA: apagar o validador ``_o_que_ainda_nao_tem_caminho_por_peca``.
    """
    # O que ABRIU passa, nos dois níveis do esquema.
    assert ControllerMicOverride.model_validate({"volume": 50}).volume == 50
    assert ControllerOverrides.model_validate(
        {"mic": {"volume": 50}}).mic.volume == 50

    # O que continua fora recusa DIZENDO o motivo — e o motivo é o mecanismo,
    # não a fila.
    for erro in (pytest.raises(ValueError, match="UM por"),
                 pytest.raises(ValueError, match="interruptor só")):
        with erro:
            ControllerMicOverride.model_validate(
                {"button_toggles_system": True})


def test_o_interruptor_do_botao_por_peca_e_recusado_com_a_razao() -> None:
    """Um por MÁQUINA — quatro controles não têm quatro opiniões sobre ele."""
    with pytest.raises(ValueError, match="MÁQUINA"):
        ControllerMicOverride.model_validate({"button_toggles_system": True})
    with pytest.raises(ValueError, match=r"hotkey\.mic_button_loop"):
        ControllerOverrides.model_validate({"mic": {"button_toggles_system": False}})


def test_o_perfil_antigo_sem_o_campo_carrega_e_vale() -> None:
    """Aditivo, sem bump de versão — é o contrato do ``speaker`` e do ``mode``.

    Os perfis do disco dela nasceram antes deste campo. Um que não o tem carrega
    e a peça segue SEM OPINIÃO, herdando o ``mic`` global do perfil.
    """
    perfil = Profile.model_validate(
        {
            "name": "jogo_de_ontem",
            "version": 1,
            "match": {"type": "any"},
            "mic": {"button_toggles_system": True, "muted": True},
            "controllers": {BRANCO: {"leds": {"lightbar": [1, 2, 3]}}},
        }
    )
    assert perfil.controllers is not None
    assert perfil.controllers[BRANCO].mic is None
    assert perfil.mic is not None and perfil.mic.muted is True


def test_a_ida_e_volta_pelo_disco_preserva_o_mudo_da_peca() -> None:
    """Grava, lê de volta, e o ``muted`` daquela peça volta igual.

    E o dump de quem NÃO opinou continua idêntico ao que era: sem isso um
    hefesto antigo (``extra="forbid"``) recusaria o perfil inteiro ao ver a
    chave nova, e "voltar uma versão" viraria "todos os perfis quebrados".
    """
    perfil = Profile(
        name="mic_por_peca",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True)),
            PRETO: ControllerOverrides(mic=ControllerMicOverride(muted=False)),
        },
    )
    cru = perfil.model_dump(mode="json", exclude_none=True)
    assert cru["controllers"] == {
        BRANCO: {"mic": {"muted": True}},
        PRETO: {"mic": {"muted": False}},
    }
    de_volta = Profile.model_validate(cru)
    assert de_volta.controllers is not None
    assert de_volta.controllers[BRANCO].mic is not None
    assert de_volta.controllers[BRANCO].mic.muted is True
    assert de_volta.controllers[PRETO].mic is not None
    assert de_volta.controllers[PRETO].mic.muted is False

    sem_opiniao = Profile(
        name="sem_mic",
        match=MatchAny(),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride())},
    )
    magro = sem_opiniao.model_dump(mode="json", exclude_none=True)
    assert magro["controllers"] == {BRANCO: {"mic": {}}}, (
        "sem opinião continua sendo silêncio: nenhum valor inventado vai ao "
        "disco por uma peça que não pediu nada"
    )


# ---------------------------------------------------------------------------
# O CAMINHO — o gesto de UMA peça sai endereçado ÀQUELA peça
# ---------------------------------------------------------------------------


def test_cada_peca_recebe_o_proprio_mudo_na_ativacao() -> None:
    """Duas unidades, dois mudos, um perfil só — o pedido dela por microfone.

    MORDIDA 2: tirar o ``uniq=str(uniq)`` da chamada em
    ``apply_controller_mics`` — o dado continua sendo calculado e deixa de ter
    dono, que é o defeito, e não a ausência do valor.
    """
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="mic_por_peca",
        match=MatchAny(),
        mic=ProfileMicConfig(button_toggles_system=True, muted=False),
        controllers={
            BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True)),
            PRETO: ControllerOverrides(mic=ControllerMicOverride(muted=False)),
        },
    )

    relatorio: dict[str, str] = {}
    gerente.apply_mic(perfil, relatorio=relatorio)
    gerente.apply_controller_mics(perfil, relatorio=relatorio)

    assert chamadas == [
        (None, False, None, "manual"),  # o global, sem endereço
        (None, True, BRANCO, "manual"),
        (None, False, PRETO, "manual"),
    ]
    # O relatório diz QUAL peça, para a GUI não fundir tudo num rótulo só.
    assert relatorio[f"mic:{BRANCO}"] == "aplicado"
    assert relatorio[f"mic:{PRETO}"] == "aplicado"


def test_a_ativacao_do_perfil_chama_o_por_peca_depois_do_global() -> None:
    """A ordem é a entrega: invertê-la faria o global apagar a peça.

    MORDIDA 3: apagar a linha ``self.apply_controller_mics(...)`` de
    ``apply_emulation`` — sobra só a chamada global e a lista perde a entrada
    com ``uniq``.
    """
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="ativacao_inteira",
        match=MatchAny(),
        mic=ProfileMicConfig(button_toggles_system=True, muted=False),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )

    relatorio = gerente.apply_emulation(perfil, origin="manual")

    assert [(c[1], c[2]) for c in chamadas] == [(False, None), (True, BRANCO)]
    assert relatorio["mic"] == "aplicado"
    assert relatorio[f"mic:{BRANCO}"] == "aplicado"


def test_a_peca_sem_opiniao_nao_produz_ordem_nenhuma() -> None:
    """``mic=None`` é ausência de opinião — e ausência não vira chamada vazia.

    Vale também para a seção que EXISTE e não escreveu nada: ``apply_mic`` sai
    antes de tocar no applier quando não há ``volume`` nem ``muted``.
    """
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="sem_opiniao",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(),
            PRETO: ControllerOverrides(mic=ControllerMicOverride()),
        },
    )

    relatorio = gerente.apply_controller_mics(perfil)

    assert chamadas == []
    assert relatorio == {}


# ---------------------------------------------------------------------------
# AS GUARDAS HERDADAS — o reuso de `apply_mic` é a entrega, e ele se prova
# ---------------------------------------------------------------------------


def test_o_mudo_da_peca_nao_atravessa_o_autoswitch() -> None:
    """MIC-GRAVACAO-01 vale igual por peça — e é a guarda mais cara de perder.

    Ela grava, o jogo abre, o autoswitch entra com a trava manual já limpa
    (``profiles/autoswitch.py``, exceção F2). Se o ``muted`` por peça
    atravessasse, o perfil do jogo roubaria o mudo dela no meio da gravação e
    apagaria o LED vermelho como COLATERAL — o que a
    AUDIT-FINDING-PROFILE-MIC-LED-RESET-01 proíbe.

    MORDIDA: escrever a chamada ao applier direto em ``apply_controller_mics``,
    em vez de reusar ``apply_mic`` — a guarda fica do lado de fora e este teste
    vê a ordem passar.
    """
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="gravacao",
        match=MatchAny(),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )

    for origem in ("autoswitch", "system"):
        assert gerente.apply_controller_mics(perfil, origin=origem) == {}
    assert chamadas == [], "o mudo da peça atravessou uma ativação automática"

    assert gerente.apply_controller_mics(perfil, origin="manual") == {
        f"mic:{BRANCO}": "aplicado"
    }
    assert chamadas == [(None, True, BRANCO, "manual")]


def test_a_trava_manual_de_audio_vence_o_override_da_peca() -> None:
    """Se ela acabou de mexer no microfone na mão, quem manda é ela.

    E o descarte é REGISTRADO com o endereço da peça: sem o relatório, a seção
    que a trava descartou sumiria sem rastro e a janela mostraria o perfil ativo
    como se tudo tivesse sido aplicado (é o buraco que o R-03 fechou).
    """
    applier, chamadas = _espiao()
    gerente = _gerente(applier, store=_StoreComTrava())
    perfil = Profile(
        name="ela_mexeu_agora",
        match=MatchAny(),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )

    relatorio = gerente.apply_controller_mics(perfil, origin="manual")

    assert chamadas == []
    assert relatorio == {f"mic:{BRANCO}": "ignorado_trava_manual"}


def test_o_applier_que_cai_nao_aborta_a_ativacao_e_diz_qual_peca() -> None:
    """Best-effort como os irmãos — e a falha tem endereço, não um rótulo só."""

    def applier(
        volume: int | None = None,
        muted: bool | None = None,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
    ) -> str:
        if uniq == BRANCO:
            raise RuntimeError("hidraw ocupado")
        return "aplicado"

    gerente = _gerente(applier)
    perfil = Profile(
        name="uma_cai_a_outra_nao",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True)),
            PRETO: ControllerOverrides(mic=ControllerMicOverride(muted=True)),
        },
    )

    relatorio = gerente.apply_controller_mics(perfil, origin="manual")

    assert relatorio == {
        f"mic:{BRANCO}": "falhou",
        f"mic:{PRETO}": "aplicado",
    }


def test_o_override_da_peca_nao_suja_o_perfil_em_memoria() -> None:
    """A vista é uma CÓPIA: o ``mic`` global do perfil sai da ativação intacto.

    ``model_copy`` não muta o original — mas quem lê o método precisa ver isso
    provado, porque um ``profile.mic = secao`` no lugar da cópia produziria o
    defeito mais silencioso possível: o perfil salvo depois levaria o mudo de
    uma peça como se fosse da mesa inteira.
    """
    applier, _ = _espiao()
    gerente = _gerente(applier)
    global_original = ProfileMicConfig(button_toggles_system=True, muted=False)
    perfil = Profile(
        name="nao_suja",
        match=MatchAny(),
        mic=global_original,
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )

    gerente.apply_controller_mics(perfil, origin="manual")

    assert perfil.mic is global_original
    assert perfil.mic.muted is False
