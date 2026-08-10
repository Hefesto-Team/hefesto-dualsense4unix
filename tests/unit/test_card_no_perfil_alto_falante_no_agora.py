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

#: O volume que ela deixou no controle deslizante, em unidades do protocolo.
VOLUME_DELA: Final[int] = 180

#: O volume que o perfil dela JÁ tinha em disco — o número que não pode virar
#: pedido ao controle sem ela ter tocado no som nesta sessão.
VOLUME_DO_ARQUIVO: Final[int] = 60

#: "Só o alto-falante" (``OUTPUT_PATH_SEL`` = 3), a rota que ela ouviu em 02/08.
ROTA_SO_O_ALTO_FALANTE: Final[int] = 3


class _Janela:
    """A ``HefestoApp`` reduzida ao que o escritor do rascunho precisa.

    Mesmo contrato de ``registrar_alto_falante_no_rascunho``: quem guarda o
    rascunho é a janela, e o escritor só sabe que ela tem um ``draft``.
    """

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft


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


# --- 1. O gesto dela chega ao AGORA ------------------------------------------


def test_o_volume_dela_viaja_no_botao_verde() -> None:
    """O gesto do controle deslizante entra no payload do ``apply_draft``.

    É o teste que reprova com o defeito de pé: antes da cura a chave nem
    existia no dicionário, e ``["speaker"]`` levantava ``KeyError``.

    Mordida: apagar ``"speaker": speaker_ipc`` do dicionário de
    ``to_ipc_dict``.
    """
    janela = _Janela(DraftConfig.from_profile(_perfil_com_som(VOLUME_DO_ARQUIVO)))
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)

    secao = _secao(janela.draft)
    assert secao is not None
    assert secao["volume"] == VOLUME_DELA
    assert secao["volume"] != VOLUME_DO_ARQUIVO


def test_o_mudo_viaja_junto_do_volume() -> None:
    """Mudo e volume são um PAR, aqui como no perfil.

    O backend recusa mudo sem volume (SOM-02/E3) — mandar a metade seria pedir
    ao daemon que tomasse a posse com a preferência ZERO, que é a armadilha 1
    da mesma sprint. O par sai junto ou não sai.

    Mordida: apagar a chave ``muted`` do ``speaker_ipc``.
    """
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=True)

    secao = _secao(janela.draft)
    assert secao == {"volume": VOLUME_DELA, "muted": True}


def test_o_canal_escolhido_por_ela_viaja_no_aplicar() -> None:
    """SOM-CANAL-NO-PERFIL-01: o canal de saída é gesto dela e vai junto.

    Ela, em 09/08: *"a ideia é respeitar tudo (...) tanto usar o mic do
    controle quanto usar o canal de saída de som específico do DS"*. O seletor
    do card já manda volume e rota no MESMO ``speaker.set``; o botão verde
    passa a mandar os dois pelo mesmo motivo — anotar um sem o outro deixaria
    metade do gesto de fora.

    Mordida: apagar o bloco ``if self.speaker.rota is not None``.
    """
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(
        janela, volume=VOLUME_DELA, muted=False, rota=ROTA_SO_O_ALTO_FALANTE
    )

    secao = _secao(janela.draft)
    assert secao is not None
    assert secao["rota"] == ROTA_SO_O_ALTO_FALANTE


def test_a_rota_so_viaja_quando_ela_escolheu_o_canal() -> None:
    """Sem opinião sobre o canal, a chave não existe — e isso é o contrato.

    O byte ``common[7]`` guarda a rota de saída E o caminho do MICROFONE.
    Mandar ``rota`` sem ela ter escolhido canal nenhum é escrever aquele byte
    por conta própria; chave AUSENTE é a única forma de dizer "não escrevo".
    Os gestos de volume e de mudo não tocam no canal, e é a maioria deles.

    Mordida: emitir ``rota`` sempre (tirar o ``if self.speaker.rota is not
    None`` e pôr a chave no literal) — a seção passa a carregar ``None``, e o
    lado de lá não tem como distinguir isso de um pedido.
    """
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)

    assert "rota" not in _secao(janela.draft)


def test_as_chaves_sao_as_do_ipc_speaker_set() -> None:
    """Um vocabulário só para o mesmo byte: ``volume``, ``muted`` e ``rota``.

    São os nomes que o ``speaker.set`` do daemon já valida (``ipc_handlers.
    _handle_speaker_set``). Inventar um segundo nome aqui obrigaria a ponta do
    daemon a traduzir o que já sabe ler — e tradução é onde esta casa perde
    dado (a rota que chega como ``path``, o volume que chega em porcentagem).

    Mordida: renomear qualquer uma das três chaves.
    """
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(
        janela, volume=VOLUME_DELA, muted=True, rota=ROTA_SO_O_ALTO_FALANTE
    )

    assert set(_secao(janela.draft)) == {"volume", "muted", "rota"}


# --- 2. O silêncio, que é a metade que a SOM-02/E4 pagou ---------------------


def test_perfil_com_som_mas_sem_gesto_dela_nao_viaja_no_aplicar() -> None:
    """Abrir um perfil com volume NÃO é pedir volume.

    É o medo escrito na SOM-02/E4, e ele continua de pé: um "Aplicar" disparado
    por ter mexido num gatilho não pode tomar a posse dos bytes de volume do
    controle sem ninguém ter pedido volume nenhum. Quem separa as duas coisas é
    o ``dirty`` — carga programática não é gesto.

    Mordida: trocar o gate por ``self.speaker.dirty or self.speaker.in_profile``
    (que é o gate do ``to_profile``, e aqui seria o defeito).
    """
    draft = DraftConfig.from_profile(_perfil_com_som(VOLUME_DO_ARQUIVO))
    assert draft.speaker.volume == VOLUME_DO_ARQUIVO
    assert draft.speaker.in_profile is True
    assert draft.speaker.dirty is False

    assert _secao(draft) is None
    # E o mesmo rascunho SEGUE persistindo a seção — as duas perguntas são
    # diferentes, e é essa diferença que a cura preserva.
    salvo = draft.to_profile("pragmata").speaker
    assert salvo is not None
    assert salvo.volume == VOLUME_DO_ARQUIVO


def test_rascunho_de_fabrica_nao_manda_som_nenhum() -> None:
    """Sem perfil e sem gesto não há chave — a aba Status nem foi aberta."""
    assert _secao(DraftConfig.default()) is None


def test_soltar_cala_a_secao_no_aplicar() -> None:
    """Devolver a posse (SOM-02/E3) apaga o pedido, não só o número.

    Depois de "Soltar", o registrador voltou a ser do firmware. Um "Aplicar"
    seguinte que ainda mandasse volume retomaria a posse que ela acabou de
    largar — o mesmo eco de estado velho que a devolução existe para matar.

    Mordida: fazer ``without_speaker`` apagar só o ``volume``
    (``model_copy(update={"volume": None})``) em vez de zerar a seção: o
    ``dirty`` ficaria de pé e a seção voltaria a viajar sem número.
    """
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)
    assert _secao(janela.draft) is not None

    registrar_alto_falante_no_rascunho(janela, volume=None)
    assert _secao(janela.draft) is None


def test_secao_sem_numero_nunca_viaja() -> None:
    """Marcada e sem volume não é seção: é o pedido que emudece o controle.

    ``speaker.set`` sem ``volume`` faz o backend cair na preferência, que sem
    volume anterior é ZERO — ele toma a posse e trava o alto-falante em zero
    (SOM-02, armadilha 1). É a mesma razão pela qual o ESQUEMA do perfil recusa
    seção sem volume, e o gate daqui é o mesmo gate de lá, de propósito.

    Mordida: tirar ``and self.speaker.volume is not None`` do gate.
    """
    draft = DraftConfig.default().model_copy(
        update={"speaker": SpeakerDraft(volume=None, muted=True, dirty=True)}
    )
    assert _secao(draft) is None


# --- 3. A seção nova é ADITIVA: não atrapalha o resto ------------------------


def test_o_volume_viaja_na_regua_do_protocolo_e_nao_na_da_tela() -> None:
    """0 a 255, a régua do registrador — nunca a porcentagem do controle.

    Esta é a régua de TODO o resto do caminho, e a lista é a prova: o
    ``SpeakerDraft`` (``ge=0, le=255``), o ``ProfileSpeakerConfig`` do esquema
    (idem) e o próprio IPC ``speaker.set``, que recusa com
    *"'volume' fora de 0-255"*. Quem converte a porcentagem da tela é o
    ``core/speaker_scale.volume_do_percentual``, uma vez só, no card — a régua
    única da SOM-02.

    O número deste teste é escolhido: 180 está ACIMA de 100 e passa, que é a
    diferença entre as duas réguas. Emitir a porcentagem daqui faria o volume
    dela chegar ao controle dividido por dois e meio.

    Mordida: converter o volume para porcentagem no ``to_ipc_dict``
    (``percentual_do_volume(...)``) — o valor deixa de ser o do rascunho.
    """
    janela = _Janela(DraftConfig.default())
    registrar_alto_falante_no_rascunho(janela, volume=VOLUME_DELA, muted=False)

    secao = _secao(janela.draft)
    assert secao["volume"] == janela.draft.speaker.volume
    assert secao["volume"] > 100
    assert 0 <= secao["volume"] <= 255


def test_a_secao_nova_nao_derruba_as_outras_no_daemon() -> None:
    """O payload com ``speaker`` continua aplicando o que o daemon já sabe.

    A seção é ADITIVA: o ``DraftApplier`` aplica cada uma em best-effort, e a
    chegada da nova não pode custar as vizinhas. Este teste afere as VIZINHAS,
    de propósito — ele segue verdadeiro tanto no dia em que o daemon ignorava a
    seção quanto depois de ele aprender a lê-la.

    Mordida: pôr o volume dentro da seção de outra chave (ex.: emitir o
    ``speaker`` como ``leds``) — a seção de luzes falha.
    """
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
