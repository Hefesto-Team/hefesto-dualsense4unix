"""A aba Controles passa a GRAVAR o som de CADA controle no perfil.

PEDIDO DELA, 05/09/2026, e ele é sobre AMANHÃ:

    *"ao pular e sair configurando de aba em aba o perfil vai se lembrando de
    cada config de cada aba pra cada controle. aí aplicar aplica todas as
    configs naquele perfil e salvar se lembra disso quando eu for jogar o jogo
    e no dia seguinte e por diante. pra cada perfil e dentro dele cada config
    pra cada comtrole"*

O QUE ESTAVA MEDIDO, nesta árvore, com o ciclo inteiro — perfil no disco → os
cinco gestos de som da aba 02 → reler o arquivo::

    mudo/microfone      chamadas: ['mic_canal_set_detalhado']   controllers: None
    mudo/alto-falante   chamadas: ['speaker_set']               controllers: None
    volume/microfone    chamadas: ['mic_volume_set_detalhado']  controllers: None
    volume/alto-falante chamadas: ['speaker_set']               controllers: None
    rota/jogo           chamadas: ['speaker_set']               controllers: None

Os cinco chegavam ao aparelho e NENHUM chegava ao disco. Ela mexia no volume do
microfone do P2, e no dia seguinte o número era o de ontem.

É PERSISTÊNCIA NO CLIQUE — a decisão D2 de 05/09
(``docs/process/2026-09-05-AS-TRES-DECISOES-DO-PERFIL-medidas-e-decididas.md``):
o requisito dela é DURABILIDADE, não o gesto de salvar, e só a escrita no clique
sobrevive a fechar a janela sem clicar em nada.

**E ELA GRAVA SEM MANDAR REAPLICAR** — a diferença medida com o
``_gravar_a_forca`` da aba Vibração: lá a escolha só chega ao motor PELA
ativação do perfil; aqui o aparelho já está no valor, e
``ProfileManager.activate`` faz ``load_profile`` a cada ativação
(``profiles/manager.py:297``). Um ``profile.switch`` por clique reaplicaria o
perfil INTEIRO — luz, gatilhos, vibração — no meio de uma partida, para
reafirmar um byte já escrito.

AS MORDIDAS DESTE ARQUIVO
--------------------------

Cada uma foi executada, e a frase entre parênteses é a que a régua devolveu:

* apagar a chamada ``_lembrar_do_som`` do ramo ``microfone`` do gesto ``mudo``
  — reprova ``test_o_mudo_do_microfone_vira_override_no_perfil`` (*"o mudo do
  microfone não chegou ao perfil"*);
* apagar a do ramo ``alto-falante`` — reprova
  ``test_o_mudo_do_alto_falante_grava_volume_e_mudo_juntos``;
* apagar a do gesto ``rota`` — reprova ``test_a_rota_do_som_vai_para_o_perfil``;
* apagar as duas do gesto ``volume`` — reprovam
  ``test_os_dois_volumes_vao_em_escalas_diferentes``;
* trocar ``if base.volume is None:`` por ``if True:`` em ``_lembrar_do_som``
  (preferir a leitura VIVA ao que o perfil já sabe) — reprova
  ``test_a_rota_nao_derruba_o_volume_que_ela_escolheu``. **É a mordida que
  mediu um defeito meu**: a primeira versão desta cura preferia o tique do
  daemon, e com o perfil em 62 e o tique ainda em 100 o clique na rota devolvia
  o disco a 100;
* mover a chamada para ANTES do ``raise`` de recusa — reprova
  ``test_o_pedido_recusado_nao_chega_ao_disco``;
* levantar quando NÃO há perfil ativo, em vez de sair calado — reprova
  ``test_sem_perfil_ativo_o_gesto_funciona_e_fica_calado`` **e as oito réguas
  vizinhas** que já mediam este mundo (ver aquele caso: foram elas que
  corrigiram o desenho desta cura, e nenhuma foi afrouxada);
* trocar ``loader.save_profile`` por ``perfil.gravar_e_reaplicar`` — reprova
  ``test_o_mudo_do_microfone_vira_override_no_perfil``, que conta o que o gesto
  pediu ao daemon;
* tirar o ramo ``igual_ao_global`` de ``with_controller_speaker`` — reprova
  ``test_o_que_iguala_o_global_nao_vira_override``;
* tirar o ``to_profile`` de dentro do ``try`` — reprova
  ``test_sem_endereco_estavel_ele_avisa``, com um ``ValidationError`` cru
  escapando pela janela;
* trocar o ``raise RuntimeError(SOM_SEM_VOLUME_PARA_GUARDAR)`` por um
  ``return`` — reprova
  ``test_a_rota_sem_volume_nenhum_avisa_em_vez_de_gravar_meia_secao``.

São ONZE, e as onze reprovaram com a frase que nomeia o defeito.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Os dois DualSense da bancada dela, com a máscara da casa (octetos 4 e 5
#: zerados). São DOIS de propósito: metade destas réguas mede que a escolha de
#: um não encosta no outro, que é o *"pra cada controle"* do pedido.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

#: A grafia com que o PERFIL guarda cada um — doze hexa, sem dois-pontos. Quem
#: canoniza é `core.sysfs_leds.norm_mac`, o mesmo que o esquema usa ao carregar.
CHAVE_P1 = "aabbcc000001"
CHAVE_P2 = "aabbcc000002"

NOME = "Bancada"


class Ponte:
    """Um daemon de papel que CONFIRMA — e que sabe recusar quando mandado.

    Ela guarda a LISTA de chamadas porque metade destas réguas mede o que o
    gesto NÃO pediu: gravar o perfil não pode virar um pedido novo ao daemon —
    o aparelho já está no valor, e reaplicar o perfil inteiro a cada clique é o
    custo que esta cura existe para não cobrar dela.
    """

    def __init__(self, *, recusa: str = "") -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self.recusa = recusa

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, dict(k)))
            if self.recusa and nome.startswith(self.recusa):
                return None if nome.endswith("_detalhado") else False
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True
        return registrar

    @property
    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture
def casa(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um `XDG_CONFIG_HOME` só deste teste, com um perfil ativo dentro.

    A pasta de perfis é resolvida na CHAMADA (`utils.xdg_paths.profiles_dir`),
    nunca no import — por isso o `monkeypatch` da variável basta e não há
    constante congelada a contornar.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    loader.save_profile(Profile(name=NOME, match=MatchManual()), origem="regua")
    return profiles_dir()


def _perfil_do_disco() -> dict[str, Any]:
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    alvo = profiles_dir() / f"{NOME.lower()}.json"
    if not alvo.exists():
        return {}
    lido: dict[str, Any] = json.loads(alvo.read_text(encoding="utf-8"))
    return lido


def _dele(uniq: str) -> dict[str, Any]:
    """O que o daemon publica daquele controle: sabe o mudo do mic e o volume."""
    return {"uniq": uniq, "transport": "usb", "connected": True, "inputs": {},
            "audio": {"mic_mudo": False},
            "speaker": {"volume": 100, "muted": False}}


def _ctx(*entradas: dict[str, Any], perfil: str = NOME) -> Any:
    import pacotes

    lista = list(entradas) or [_dele(P1)]
    return pacotes.Contexto(state={"active_profile": perfil}, mesa=[],
                            conectados=lista, estados={})


def _gesto(nome: str) -> Any:
    import pacotes
    import pacotes.a02_controles  # importar é registrar: o decorador `@gesto`

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


def _do_controle(uniq_chave: str) -> dict[str, Any]:
    dos = _perfil_do_disco().get("controllers") or {}
    bloco = dos.get(uniq_chave)
    return bloco if isinstance(bloco, dict) else {}


def _bytes_do_perfil() -> bytes:
    """O arquivo CRU. `NADA MUDOU = NADA GRAVA` se mede aqui, e não por eco.

    Comparar os bytes é a leitura, não a digitação: uma régua que perguntasse à
    ponte *"você chamou save?"* mediria a intenção do arquivo que ela testa.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    alvo = profiles_dir() / f"{NOME.lower()}.json"
    return alvo.read_bytes() if alvo.exists() else b""


# ===========================================================================
# 1. Os cinco gestos chegam ao disco
# ===========================================================================


def test_o_mudo_do_microfone_vira_override_no_perfil(casa: Any) -> None:
    """O 🎙 daquele card guarda o mudo DAQUELE controle.

    MORDIDA: apagar a chamada `_lembrar_do_som` do ramo `microfone` do gesto
    `mudo` — o override some e esta régua diz que o mudo não chegou ao perfil.
    """
    p = Ponte()
    _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "microfone"}, p)

    assert _do_controle(CHAVE_P1).get("mic") == {"muted": True}, (
        "o mudo do microfone não chegou ao perfil — amanhã ele volta ao de "
        f"ontem. No disco: {_perfil_do_disco().get('controllers')!r}")
    # ELE GRAVA E NÃO MANDA REAPLICAR, e a ausência é a decisão medida: o
    # aparelho JÁ está no valor (a linha acima é o eco do daemon confirmando), e
    # `ProfileManager.activate` faz `load_profile` a cada ativação — não há
    # cópia em memória a corrigir. Um `profile.switch` aqui reaplicaria o perfil
    # INTEIRO — luz, gatilhos, vibração — a cada clique no mudo, no meio de uma
    # partida, para reafirmar um byte que já estava escrito.
    assert p.nomes == ["mic_canal_set_detalhado"], (
        f"o clique no mudo pediu mais que o ato ao daemon: {p.nomes!r}")


def test_o_mudo_do_alto_falante_grava_volume_e_mudo_juntos(casa: Any) -> None:
    """A seção do alto-falante é ALL-OR-NOTHING, e o volume vem junto.

    `ProfileSpeakerConfig` exige `volume` porque uma seção sem número manda
    ZERO ao firmware e tranca o alto-falante (SOM-02, armadilha 1) — nem o
    próprio botão o solta depois. Guardar só o `muted` seria escrever no disco
    a armadilha que o esquema recusa.

    MORDIDA: apagar a chamada do ramo `alto-falante`.
    """
    p = Ponte()
    _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "alto-falante"}, p)

    assert _do_controle(CHAVE_P1).get("speaker") == {"volume": 100, "muted": True}, (
        "o mudo do alto-falante não chegou ao perfil com o volume junto — e "
        "sem o volume o esquema recusaria a seção inteira")


def test_a_rota_do_som_vai_para_o_perfil(casa: Any) -> None:
    """"Sons do jogo" é um BYTE do firmware, e o perfil o guarda.

    A camada 1 (a saída padrão do PipeWire) não entra aqui de propósito: ela é
    um fato GLOBAL do sistema, e um perfil por controle não é lugar dela.

    MORDIDA: apagar a chamada do gesto `rota`.
    """
    p = Ponte()
    _gesto("rota")(_ctx(), {"uniq": P1, "rota": "jogo"}, p)

    som = _do_controle(CHAVE_P1).get("speaker") or {}
    assert som.get("rota") == 2, (
        f"a rota não chegou ao perfil deste controle — no disco: {som!r}")


def test_os_dois_volumes_vao_em_escalas_diferentes(casa: Any) -> None:
    """O mic é 0-100 (a FONTE de captura); o alto-falante é 0-255 (o protocolo).

    SÃO DUAS ESCALAS E NÃO É DETALHE: `ProfileMicConfig.volume` é o por cento
    da fonte no PipeWire e `ProfileSpeakerConfig.volume` é o registrador do
    aparelho. Gravar os dois na mesma escala faria o número que ela arrasta e o
    número que o perfil devolve discordarem.

    MORDIDA: apagar as duas chamadas do gesto `volume`; ou converter o volume
    do alto-falante duas vezes.
    """
    from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual

    p = Ponte()
    _gesto("volume")(_ctx(), {"uniq": P1, "volume": "microfone", "valor": "42"}, p)
    _gesto("volume")(_ctx(), {"uniq": P1, "volume": "alto-falante", "valor": "37"}, p)

    dele = _do_controle(CHAVE_P1)
    assert (dele.get("mic") or {}).get("volume") == 42, (
        f"o ganho do microfone não chegou ao perfil em 0-100: {dele!r}")
    assert (dele.get("speaker") or {}).get("volume") == volume_do_percentual(37), (
        "o volume do alto-falante não chegou no registrador 0-255 — a curva "
        f"medida diz {volume_do_percentual(37)}, o disco diz "
        f"{(dele.get('speaker') or {}).get('volume')!r}")


# ===========================================================================
# 2. O que a escrita NÃO pode fazer
# ===========================================================================


def test_a_rota_nao_derruba_o_volume_que_ela_escolheu(casa: Any) -> None:
    """O TIQUE DO DAEMON NÃO CORRIGE O QUE ELA ESCOLHEU — defeito meu, medido.

    A primeira versão de `_lembrar_do_som` preenchia o volume do alto-falante
    com a leitura VIVA sempre que o gesto não falava dele. Com o perfil em 62 e
    o tique do daemon ainda em 100 — a janela entre a escrita e a publicação do
    estado —, o clique seguinte na rota devolvia o disco a 100 e a escolha dela
    sumia sem uma palavra. É a mesma família do *"o Salvar destruía o que o
    produto gravou"* que esta leva fecha.

    O tique serve para SABER quando o perfil não sabe; nunca para corrigir.

    MORDIDA: em `_lembrar_do_som`, trocar `if base.volume is None:` por
    `if True:` — o volume volta a 100 e esta régua reprova.
    """
    p = Ponte()
    _gesto("volume")(_ctx(), {"uniq": P1, "volume": "alto-falante", "valor": "24"}, p)
    escolhido = (_do_controle(CHAVE_P1).get("speaker") or {}).get("volume")
    assert escolhido is not None and escolhido != 100, (
        "o caso não foi montado: o volume escolhido tem de diferir do que o "
        "tique publica (100), senão a régua não mede nada")

    # O tique continua dizendo 100 — é a janela entre a escrita e a publicação.
    _gesto("rota")(_ctx(), {"uniq": P1, "rota": "jogo"}, p)

    som = _do_controle(CHAVE_P1).get("speaker") or {}
    assert som.get("volume") == escolhido, (
        f"o clique na rota devolveu o volume ao número do tique: o perfil "
        f"tinha {escolhido}, agora tem {som.get('volume')!r}")
    assert som.get("rota") == 2, "e a rota nem sequer foi guardada"


def test_o_pedido_recusado_nao_chega_ao_disco(casa: Any) -> None:
    """SÓ SE GRAVA O QUE O DAEMON CONFIRMOU.

    Um pedido recusado que fosse ao disco seria a tela decidindo por ela: o
    número no arquivo passaria a contradizer o aparelho, e a ativação seguinte
    reimporia o que nunca pegou.

    MORDIDA: mover a chamada de `_lembrar_do_som` para ANTES do `raise` de
    recusa em qualquer dos cinco ramos.
    """
    antes = _bytes_do_perfil()
    p = Ponte(recusa="speaker_set")
    with pytest.raises(RuntimeError):
        _gesto("volume")(_ctx(), {"uniq": P1, "volume": "alto-falante",
                                  "valor": "37"}, p)

    assert _perfil_do_disco().get("controllers") in (None, {}), (
        "o daemon recusou e o perfil guardou assim mesmo — o disco passou a "
        "contradizer o aparelho")
    assert _bytes_do_perfil() == antes, "o arquivo foi reescrito por um pedido recusado"


def test_o_som_de_um_controle_nao_mexe_no_do_outro(casa: Any) -> None:
    """*"pra cada perfil e dentro dele cada config pra cada comtrole"*.

    Com dois DualSense na mesa, o volume do P2 é do P2. Esta é a metade do
    pedido dela que nenhum campo global sabe cumprir.
    """
    p = Ponte()
    _gesto("volume")(_ctx(_dele(P1), _dele(P2)),
                     {"uniq": P2, "volume": "microfone", "valor": "77"}, p)

    assert (_do_controle(CHAVE_P2).get("mic") or {}).get("volume") == 77
    assert _do_controle(CHAVE_P1) == {}, (
        "a escolha feita no card do P2 encostou no P1 — é o defeito que o "
        "perfil por controle existe para não cometer")


def test_o_que_iguala_o_global_nao_vira_override(casa: Any) -> None:
    """COR-04: repetir o global não deixa rastro no mapa por peça.

    Um override que repete o global é dívida silenciosa — some da tela e
    reaparece no dia em que o global mudar, contradizendo a peça sem ninguém
    ver. Quem aplica a regra é o produto (`with_controller_speaker`), e esta
    régua mede que a aba NÃO a contorna com um `if` seu.

    MORDIDA: tirar o ramo `igual_ao_global` de `with_controller_speaker`.
    """
    from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import (
        MatchManual,
        Profile,
        ProfileSpeakerConfig,
    )

    pct = 37
    loader.save_profile(
        Profile(name=NOME, match=MatchManual(),
                speaker=ProfileSpeakerConfig(
                    volume=volume_do_percentual(pct), muted=False)),
        origem="regua")

    antes = _bytes_do_perfil()
    p = Ponte()
    _gesto("volume")(_ctx(), {"uniq": P1, "volume": "alto-falante",
                              "valor": str(pct)}, p)

    assert _perfil_do_disco().get("controllers") in (None, {}), (
        "escolher para a peça o MESMO número do global virou override — é a "
        "dívida silenciosa que a COR-04 existe para não deixar nascer")
    assert _bytes_do_perfil() == antes, (
        "nada mudou e o perfil foi regravado assim mesmo — regravar um perfil "
        "idêntico troca a data do arquivo por nada")


def test_o_botao_do_sistema_nao_entra_por_peca(casa: Any) -> None:
    """`mic.button_toggles_system` é UM por MÁQUINA e não pode viajar por peça.

    Quem o lê é `hotkey.mic_button_loop`, em
    `daemon.config.mic_button_toggles_system`, sem consultar `uniq` nenhum.
    Guardá-lo por controle faria quatro controles gravarem quatro opiniões
    sobre um interruptor só — e campo que grava sem quem leia faz a tela
    prometer.

    A LISTA VEM DO PRODUTO, não daqui: `_NAO_GRAVA_POR_PECA` é a declaração do
    arquivo sobre o que ele não escreve, e esta régua a LÊ. Digitar o nome do
    campo aqui faria a régua e a declaração envelhecerem em separado — e no dia
    em que um segundo campo entrasse na lista, só a declaração saberia.
    """
    from pacotes.a02_controles import _NAO_GRAVA_POR_PECA

    assert _NAO_GRAVA_POR_PECA, "a declaração está vazia e a régua mede o vácuo"

    p = Ponte()
    _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "microfone"}, p)
    _gesto("volume")(_ctx(), {"uniq": P1, "volume": "microfone", "valor": "42"}, p)

    guardado = _do_controle(CHAVE_P1).get("mic") or {}
    assert guardado, "o caso não foi montado: nada do microfone chegou ao perfil"
    for campo in _NAO_GRAVA_POR_PECA:
        assert campo not in guardado, (
            f"{campo!r} foi gravado por peça, e ele é UM por máquina — quatro "
            "controles passariam a gravar quatro opiniões sobre um "
            "interruptor só")


# ===========================================================================
# 3. Quando não há onde lembrar, ele DIZ
# ===========================================================================


def test_sem_perfil_ativo_o_gesto_funciona_e_fica_calado(casa: Any) -> None:
    """RÉGUA INVERTIDA EM 05/09/2026, e quem a inverteu foram OITO já escritas.

    ELA NASCEU DIZENDO O CONTRÁRIO — *"sem perfil ativo ele AVISA em vez de
    calar"* —, e a primeira versão desta cura levantava um `RuntimeError` aqui.
    Rodadas as vizinhas, OITO reprovaram
    (`test_a_aba_02_controles_fecha_as_linhas.py`, quatro, e
    `test_a02_som_e_sensor_falam_quando_recusam.py`, quatro): todas montam um
    mundo com daemon e controle e SEM perfil, e todas medem que o gesto que dá
    certo não levanta.

    ELAS ESTAVAM CERTAS, e a razão é a regra dela de 02/09: *"é aviso, não
    estado"*. "Não há perfil ativo" é ESTADO PARADO — o chip `Perfil ativo` do
    cabeçalho o mostra o tempo todo, e está na foto desta aba. Repeti-lo como
    recado de 30 s a cada clique de som é estado disfarçado de aviso, e o preço
    é o oposto do pretendido: quem recebe a mesma frase em todo clique para de
    ler os recados.

    E o ramo é raro: medido no `state_full` VIVO da máquina dela, o daemon
    publica `active_profile: 'meu_perfil'` — este caminho é o do daemon parado.

    MORDIDA: devolver o `raise` — esta régua reprova, e com ela as oito
    vizinhas.
    """
    antes = _bytes_do_perfil()
    p = Ponte()
    _gesto("mudo")(_ctx(perfil=""), {"uniq": P1, "mudo": "microfone"}, p)

    assert p.nomes == ["mic_canal_set_detalhado"], (
        "o ato não aconteceu, ou aconteceu junto de outra coisa — sem perfil "
        f"ativo o gesto tem de fazer só o que sempre fez: {p.nomes!r}")
    assert _bytes_do_perfil() == antes, (
        "sem perfil ativo alguma coisa foi ao disco assim mesmo")


def test_sem_endereco_estavel_ele_avisa(casa: Any) -> None:
    """Um `path:` NÃO vira chave de perfil — e quem recusa é a BORDA do esquema.

    **ESTA RÉGUA MEDIU UM DEFEITO MEU, na primeira execução.** A guarda que eu
    tinha escrito era `norm_mac(uniq) or ""` seguida de `if not chave: raise` —
    e ela não pega nada, porque `norm_mac("path:/dev/hidraw3")` devolve
    `"adeda3"`: um caminho tem letras de `a` a `f` no meio, e a peneira as
    recolhe. É o defeito que `sysfs_leds.norm_mac` já descreve por escrito
    desde 04/09/2026 — *"para GRAVAR é perda de dado dela: a escolha vai ao
    disco sob uma chave que parece boa e que aparelho nenhum reivindica, e some
    calada"*.

    A CURA NÃO FOI UMA TERCEIRA CÓPIA DA REGRA DOS DOZE HEXA. Quem julga é
    `Profile._validate_controllers_keys`, e o `to_profile` passou a rodar
    DENTRO do `try` para que a razão dela suba como frase de tela em vez de
    traço cru de pydantic.

    MORDIDA: tirar o `to_profile` de dentro do `try` — a régua volta a ver um
    `ValidationError` escapando pela janela.
    """
    from pacotes.a02_controles import SOM_SEM_ENDERECO

    avulso = _dele("path:/dev/hidraw3")
    p = Ponte()
    with pytest.raises(RuntimeError) as erro:
        _gesto("mudo")(_ctx(avulso), {"uniq": "path:/dev/hidraw3",
                                      "mudo": "microfone"}, p)

    frase = str(erro.value)
    assert frase.startswith(SOM_SEM_ENDERECO), (
        f"a frase não começa dizendo o que PEGOU no aparelho: {frase!r}")
    assert "MAC de 12 dígitos hex" in frase, (
        "a razão da borda não subiu para a tela — quem clica leria um traço "
        f"de pydantic ou nada: {frase!r}")
    assert _perfil_do_disco().get("controllers") in (None, {}), (
        "a escolha foi ao disco sob uma chave que aparelho nenhum reivindica")


def test_a_rota_sem_volume_nenhum_avisa_em_vez_de_gravar_meia_secao(
    casa: Any,
) -> None:
    """`ProfileSpeakerConfig` exige volume, e "meia seção" tranca o aparelho.

    O CASO É REAL e é do próprio protocolo: o DualSense **não devolve** o
    registrador de volume, então o daemon só publica a chave `speaker` depois
    de alguém ESCREVER um. Num controle cujo volume nunca foi ajustado, o
    clique em "Sons do jogo" escreve o byte da rota e não tem número nenhum
    para guardar junto — nem do disco nem do tique.

    GRAVAR ASSIM MESMO SERIA A ARMADILHA 1 DA SOM-02 escrita no arquivo dela:
    uma seção sem volume manda ZERO ao firmware e tranca o alto-falante em
    zero, e nem o próprio botão o solta depois.

    MORDIDA: trocar o `raise RuntimeError(SOM_SEM_VOLUME_PARA_GUARDAR)` por um
    `return` — a frase some, e ela deixa de saber que a rota não vai durar.
    """
    from pacotes.a02_controles import SOM_SEM_VOLUME_PARA_GUARDAR

    # O daemon NÃO publica `speaker` deste controle — é o estado de quem nunca
    # recebeu um `speaker.set`.
    mudo_de_volume = _dele(P1)
    mudo_de_volume.pop("speaker")

    p = Ponte()
    with pytest.raises(RuntimeError) as erro:
        _gesto("rota")(_ctx(mudo_de_volume), {"uniq": P1, "rota": "jogo"}, p)

    assert str(erro.value) == SOM_SEM_VOLUME_PARA_GUARDAR
    assert "speaker_set" in p.nomes, (
        "o aviso saiu ANTES de a rota chegar ao controle — então ele não é "
        "sobre guardar, é uma recusa disfarçada")
    assert _perfil_do_disco().get("controllers") in (None, {}), (
        "uma seção de alto-falante sem volume foi ao disco: a próxima ativação "
        "manda ZERO ao firmware e tranca o alto-falante dela")


# ===========================================================================
# 4. O round-trip não perde nada do resto do perfil
# ===========================================================================


def test_gravar_o_som_nao_derruba_o_resto_do_perfil(casa: Any) -> None:
    """A escrita passa por `from_profile`/`to_profile`, e nada pode cair no caminho.

    É a mesma travessia que produziu o `BUG-FOOTER-SAVE-DROPS-SECTIONS-01` — o
    "Salvar" que destruía seções que o produto tinha acabado de gravar. Aqui a
    régua confere as três coisas que o rodapé já perdeu uma vez: a prioridade,
    o casamento e o override de OUTRA peça.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        ControllerRumbleOverride,
        MatchManual,
        Profile,
    )

    loader.save_profile(
        Profile(name=NOME, match=MatchManual(), priority=7,
                controllers={CHAVE_P2: ControllerOverrides(
                    rumble=ControllerRumbleOverride(policy="max"))}),
        origem="regua")

    p = Ponte()
    _gesto("mudo")(_ctx(_dele(P1), _dele(P2)), {"uniq": P1, "mudo": "microfone"}, p)

    disco = _perfil_do_disco()
    assert disco.get("priority") == 7, "a prioridade caiu na travessia"
    assert (disco.get("match") or {}).get("type") == "manual", (
        "o casamento caiu na travessia — o perfil deixou de ser só-manual")
    assert (_do_controle(CHAVE_P2).get("rumble") or {}).get("policy") == "max", (
        "a força própria do OUTRO controle caiu quando este gravou o som")
    assert _do_controle(CHAVE_P1).get("mic") == {"muted": True}
