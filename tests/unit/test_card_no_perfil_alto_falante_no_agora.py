"""SOM-NO-AGORA-01 — o alto-falante dela também entra no botão VERDE.

O PEDIDO DELA, 09/08/2026, literal: *"Preciso que cada feature de cada aba ao
clicarmos em salvar perfil e aplicar (botão verde) tudo fique salvo no perfil
ativo (...) touch, giroscopio, speaker, mic, gatilho, lightbar. tudo."* E o
veredito dela sobre o que aconteceu: *"literalmente nenhuma feature ficou lá"*.

O DEFEITO, medido em 10/08/2026 no ``DraftConfig.to_ipc_dict``: o dicionário do
``profile.apply_draft`` tinha exatamente sete chaves — ``triggers``, ``leds``,
``rumble``, ``mouse``, ``mic``, ``keyboard`` e ``controllers``. **Nenhuma delas
era o alto-falante.** O volume, o mudo e o canal que ela ajusta no card viajavam
para o ARQUIVO (``to_profile``, curado na SOM-02/E4 em 09/08) e não viajavam
para o CONTROLE: o botão verde era o único gesto da janela que prometia
"aplicar tudo" e deixava o som de fora, calado.

Era o par simétrico do defeito de ontem, e vale registrar a simetria porque ela
é a assinatura desta classe: em 09/08 o gesto chegava ao controle e não ao
arquivo; hoje ele chegava ao arquivo e não ao controle. O mesmo dado, dois
donos, e a metade que faltava trocou de lado.

A REGRA QUE A CURA MANTÉM. A seção viaja SÓ com ``speaker.dirty`` — a mesma
disciplina do ``mouse`` e do ``mic``. O comentário original da SOM-02/E4 recusava
emitir a seção porque *"um Aplicar disparado por ter mexido num gatilho tomaria
a posse dos bytes de volume do controle sem ninguém ter pedido volume nenhum"*,
e esse medo continua inteiro aqui: sem gesto de som nesta sessão não há chave
nenhuma no payload. O que caducou foi a ausência, não o raciocínio — e por isso
metade destes testes afere a EMISSÃO e a outra metade afere o SILÊNCIO.

A OUTRA PONTA É DE OUTRA LEVA, e este arquivo não afirma nada sobre ela: quem
recebe a seção é o ``daemon/ipc_draft_applier.DraftApplier``, e o que se afere
aqui é o que a JANELA emite. O último teste daqui é a única fronteira que se
atravessa, e de propósito ele mede as VIZINHAS: a seção nova é aditiva e não
pode custar as outras, valha ela do outro lado ou não.

A RÉGUA É O CONTRATO ENTRE AS DUAS PONTAS, e tem teste próprio aqui porque é
onde esta casa já se enganou: ``volume`` é 0-255, a régua do REGISTRADOR —
a do ``SpeakerDraft``, a do ``ProfileSpeakerConfig`` e a do IPC ``speaker.set``
(*"'volume' fora de 0-255"*). A porcentagem da tela morre no card, no
``volume_do_percentual``. Medido em 10/08/2026: o controle deslizante em 100 %
sai como **102** no registrador, e ela usa perfis com 180 — quem validar a
seção como 0-100 do outro lado recusa o volume normal dela.

Sem GTK de propósito: o caminho do GESTO até o rascunho já tem duas testemunhas
(``test_som_02_o_volume_dela_chega_ao_perfil.py``, com o card real, e o portão
de AST de ``test_perfil_salva_tudo_registrar_nao_e_aplicar.py``, que tranca o
card em ``registrar_alto_falante_no_rascunho``). O que faltava testemunha era
daqui para a frente, e daqui para a frente é função pura.

AS MORDIDAS (cada uma foi arrancada e vista reprovar, 10/08/2026):

- apagar ``"speaker": speaker_ipc`` do dicionário de ``to_ipc_dict`` ->
  reprova o arquivo INTEIRO, e com ``KeyError: 'speaker'``, que é o defeito ao
  pé da letra: a chave não existia no payload do botão verde;
- trocar o gate ``self.speaker.dirty`` por ``dirty or in_profile`` ->
  reprova ``test_perfil_com_som_mas_sem_gesto_dela_nao_viaja_no_aplicar``;
- tirar ``and self.speaker.volume is not None`` do gate ->
  reprova ``test_secao_sem_numero_nunca_viaja``;
- emitir ``rota`` sempre (sem o ``if ... is not None``) ->
  reprova ``test_a_rota_so_viaja_quando_ela_escolheu_o_canal``;
- apagar o bloco do ``rota`` (nunca emitir) ->
  reprova ``test_o_canal_escolhido_por_ela_viaja_no_aplicar``;
- converter o volume para porcentagem antes de emitir ->
  reprova ``test_o_volume_viaja_na_regua_do_protocolo_e_nao_na_da_tela``.
"""

from __future__ import annotations

from typing import Any, Final

from unittest.mock import MagicMock

from hefesto_dualsense4unix.app.draft_config import (
    DraftConfig,
    SpeakerDraft,
    registrar_alto_falante_no_rascunho,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileSpeakerConfig,
)

VOLUME_DELA: Final[int] = 180

VOLUME_DO_ARQUIVO: Final[int] = 60

ROTA_SO_O_ALTO_FALANTE: Final[int] = 3


class _Janela:
    """A ``HefestoApp`` reduzida ao que o escritor do rascunho precisa."""

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None


def _perfil_com_som(volume: int) -> Profile:
    """O perfil dela, já com a seção de alto-falante em disco."""
    return Profile(
        name="pragmata",
        match=MatchCriteria(window_class=["pragmata_class"]),
        priority=10,
        speaker=ProfileSpeakerConfig(volume=volume, muted=False),
    )


def _secao(draft: DraftConfig) -> Any:
    """A seção ``speaker`` do payload do botão verde."""
    return draft.to_ipc_dict()["speaker"]


def test_o_volume_dela_viaja_no_botao_verde() -> None:
    """O gesto do controle deslizante entra no payload do ``apply_draft``."""
    janela = _Janela(DraftConfig.from_profile(_perfil_com_som(VOLUME_DO_ARQUIVO)))
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)

    secao = _secao(janela.draft)
    assert secao is not None
    assert secao["volume"] == VOLUME_DELA
    assert secao["volume"] != VOLUME_DO_ARQUIVO


def test_o_mudo_viaja_junto_do_volume() -> None:
    """Mudo e volume são um PAR, aqui como no perfil."""
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=True)

    secao = _secao(janela.draft)
    assert secao == {"volume": VOLUME_DELA, "muted": True}


def test_o_canal_escolhido_por_ela_viaja_no_aplicar() -> None:
    """SOM-CANAL-NO-PERFIL-01: o canal de saída é gesto dela e vai junto."""
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(
        janela, volume=VOLUME_DELA, muted=False, rota=ROTA_SO_O_ALTO_FALANTE
    )

    secao = _secao(janela.draft)
    assert secao is not None
    assert secao["rota"] == ROTA_SO_O_ALTO_FALANTE


def test_a_rota_so_viaja_quando_ela_escolheu_o_canal() -> None:
    """Sem opinião sobre o canal, a chave não existe — e isso é o contrato."""
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)

    assert "rota" not in _secao(janela.draft)


def test_as_chaves_sao_as_do_ipc_speaker_set() -> None:
    """Um vocabulário só para o mesmo byte: ``volume``, ``muted`` e ``rota``."""
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(
        janela, volume=VOLUME_DELA, muted=True, rota=ROTA_SO_O_ALTO_FALANTE
    )

    assert set(_secao(janela.draft)) == {"volume", "muted", "rota"}


def test_perfil_com_som_mas_sem_gesto_dela_nao_viaja_no_aplicar() -> None:
    """Abrir um perfil com volume NÃO é pedir volume."""
    draft = DraftConfig.from_profile(_perfil_com_som(VOLUME_DO_ARQUIVO))
    assert draft.speaker.volume == VOLUME_DO_ARQUIVO
    assert draft.speaker.in_profile is True
    assert draft.speaker.dirty is False

    assert _secao(draft) is None
    salvo = draft.to_profile("pragmata").speaker
    assert salvo is not None
    assert salvo.volume == VOLUME_DO_ARQUIVO


def test_rascunho_de_fabrica_nao_manda_som_nenhum() -> None:
    """Sem perfil e sem gesto não há chave — a aba Status nem foi aberta."""
    assert _secao(DraftConfig.default()) is None


def test_soltar_cala_a_secao_no_aplicar() -> None:
    """Devolver a posse (SOM-02/E3) apaga o pedido, não só o número."""
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)
    assert _secao(janela.draft) is not None

    registrar_alto_falante_no_rascunho(janela, volume=None)
    assert _secao(janela.draft) is None


def test_secao_sem_numero_nunca_viaja() -> None:
    """Marcada e sem volume não é seção: é o pedido que emudece o controle."""
    draft = DraftConfig.default().model_copy(
        update={"speaker": SpeakerDraft(volume=None, muted=True, dirty=True)}
    )
    assert _secao(draft) is None


def test_o_volume_viaja_na_regua_do_protocolo_e_nao_na_da_tela() -> None:
    """0 a 255, a régua do registrador — nunca a porcentagem do controle."""
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)

    secao = _secao(janela.draft)
    assert secao["volume"] == janela.draft.speaker.volume
    assert secao["volume"] > 100
    assert 0 <= secao["volume"] <= 255


def test_a_secao_nova_nao_derruba_as_outras_no_daemon() -> None:
    """O payload com ``speaker`` continua aplicando o que o daemon já sabe."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(
        janela, volume=VOLUME_DELA, muted=False, rota=ROTA_SO_O_ALTO_FALANTE
    )
    payload = janela.draft.to_ipc_dict()
    assert payload["speaker"] is not None

    ctrl = MagicMock()
    applier = DraftApplier(controller=ctrl, store=MagicMock(), daemon=None)
    applied = applier.apply(payload)

    assert "leds" in applied
    assert "triggers" in applied
    assert "leds" not in applier.failed
    assert "triggers" not in applier.failed
