"""O 🎙 confessa DE QUEM era o microfone, e o alto-falante volta a confirmar com som.

A-CONFISSAO-NO-BOTAO-01 (06/09/2026). As duas linhas nasceram do laudo da
paridade e vieram para hoje por causa da bancada de QUATRO desta noite: com um
controle na mesa, nenhuma das duas dói.

AS DUAS METADES QUE ESTA RÉGUA MEDE
------------------------------------

1. **o mudo confessa o alvo.** O gesto `mudo` do microfone passa a perguntar ao
   mesmo dono que o deslizante já pergunta — `frase_do_alvo_do_mic` sobre
   `alvo_honrado` — e sobe a confissão pelo canal da recusa, **antes** de
   gravar no perfil. `frase_do_ato_do_microfone`, que já estava lá, responde
   outra pergunta: QUAL METADE do ato faltou;
2. **o som de confirmação.** `app/audio_saida.tocar_confirmacao` tinha zero
   chamadores em `interface/`, e a janela GTK o toca em quatro gestos do bloco
   do alto-falante desde a SOM-04. Ele volta nos TRÊS que esta aba tem — o
   deslizante, o ♪ e a rota —, com o motor reusado inteiro e o caminho novo
   sendo só *quem sabe o sink daquele controle* e *onde a chamada entra*.

O QUE FOI MEDIDO NA MÁQUINA, e é o que faz esta régua ser segura de rodar: com
um `uniq` sintético (todos os desta casa), `audio_saida.sink_do_controle`
devolve `""` — o casamento por dispositivo USB VETA o sink real que está na
máquina. Nenhum som sai daqui, e o motor nunca toca no sink padrão.

**E ISSO NÃO BASTAVA — o achado mais caro deste dia, e o defeito era MEU.**
Numa régua que DUBLA o `pactl` (a irmã `test_a02_som_e_sensor_falam_quando_
recusam.py` faz isso), o veto acima não existe: a lista viva é de mentira, o
sink do DualSense casa pela regra do um-para-um, e o motor segue para o
`paplay`, que **não** está dublado. Medido: `paplay --device=<o sink do controle
dela>`. A cura é `ponte.dentro_da_janela` — sem janela de pé, ninguém clicou —
e a `TestAGuardaDaMaquinaDela` é quem a segura.

AS MORDIDAS DESTE ARQUIVO
--------------------------

* **arrancar** as duas linhas da confissão do ramo `microfone` do gesto `mudo`
  — reprova `test_o_mudo_confessa_quando_o_alvo_nao_foi_honrado`, dizendo que o
  gesto voltou como SUCESSO;
* **acusar sem ler o valor** (confessar com `alvo_honrado` valendo `True` ou
  `None`) — reprova `test_o_mudo_nao_acusa_quando_honrou_nem_quando_nao_sabe`,
  a mordida que separa a cura da superstição: *"não sei" não é "não honrei"*;
* **gravar antes de confessar** — reprova o terceiro `assert` da primeira, que
  lê os BYTES do perfil no disco;
* **digitar a frase** em vez de perguntar ao dono — reprova
  `test_a_frase_da_confissao_e_a_do_dono`;
* **arrancar `_confirmar_com_som`** de qualquer um dos três gestos — reprova
  `test_os_tres_gestos_do_alto_falante_confirmam_com_som`;
* **chamar `tocar_confirmacao` direto no corpo do gesto**, sem `_fora_do_voo` —
  reprova `test_o_som_nao_segura_o_botao_em_voo`;
* **deixar a exceção do som subir** (tirar o `try` de `tocar`) — reprova
  `test_o_som_que_falha_nao_derruba_o_volume`;
* **inventar uma segunda chave para o som** — reprova
  `test_a_chave_dela_desliga_o_som_e_o_gesto_nao_recusa`;
* **tirar o `dentro_da_janela` de `_fora_do_voo`** — reprovam as duas da
  `TestAGuardaDaMaquinaDela`, e a segunda mostra o `paplay` que sairia.
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.widgets.controller_card import (
    frase_do_alvo_do_mic,
)

#: MAC da faixa sintética desta casa — há DOIS portões de anonimato nesta árvore.
P1 = "aa:bb:cc:00:00:01"
CHAVE_P1 = "aabbcc000001"

NOME = "Regua da confissao"

#: Um nome de sink de DualSense na forma que o PipeWire usa nesta bancada. Ele
#: é DADO DE TESTE e nunca chega a lugar nenhum: o tocador está dublado em toda
#: régua que o usa.
SINK = ("alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
        "Controller-00.analog-surround-40")


class PonteQueDizDeQuem:
    """O dublê ESTRITO: devolve o CORPO do daemon, como a ponte real devolve.

    **Um dublê mais frouxo que a ponte real é a cicatriz de 04/09/2026**, e ela
    custou duas máscaras que nunca gravaram um byte. O `_corpo` do pacote
    converte `True` em `{"status": "ok"}` e mais nada — sem `por_uniq` —, então
    uma ponte que respondesse `True` mediria o caminho do *"não sei"* achando
    que estava medindo o do *"não honrei"*.
    """

    def __init__(self, corpo: dict[str, Any] | None = None) -> None:
        self.corpo = corpo if corpo is not None else {"status": "ok"}
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def mic_canal_set_detalhado(self, *a: Any, **k: Any) -> dict[str, Any] | None:
        self.chamadas.append(("mic_canal_set_detalhado", dict(k)))
        return self.corpo

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, dict(k)))
            return True

        return registrar

    @property
    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture
def casa(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um `XDG_CONFIG_HOME` só desta régua, com um perfil ativo dentro.

    O perfil precisa existir porque metade destas medições é sobre o que NÃO foi
    ao disco: sem arquivo, *"não gravou"* seria verdade por acaso.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    loader.save_profile(Profile(name=NOME, match=MatchManual()), origem="regua")
    return profiles_dir()


@pytest.fixture
def som(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """O som, medido sem tocar: o espião no motor e a linha própria desligada.

    DUAS SUBSTITUIÇÕES, e cada uma tem razão própria:

    * `tocar_confirmacao` vira espião — o motor tem dono e régua próprios
      (`test_audio_saida*`), e o que se mede AQUI é o caminho até ele: com que
      sink, com que `saida_muda`, em que ordem;
    * `_fora_do_voo` vira chamada direta — o produto roda o som numa thread, e
      uma régua que esperasse relógio seria corrida. Este é o ponto de injeção
      declarado no próprio produto.
    """
    import pacotes.a02_controles as a02

    tocados: list[tuple[str, Any]] = []

    def espiao(sink: str, **k: Any) -> Any:
        tocados.append((sink, k.get("saida_muda")))
        return None

    monkeypatch.setattr(a02.audio_saida, "tocar_confirmacao", espiao)
    monkeypatch.setattr(a02, "_fora_do_voo", lambda fn: fn())
    monkeypatch.setattr(a02, "_sink_para_o_som", lambda uniq, na_mesa: SINK)
    return tocados


def _arquivo_do_perfil() -> pathlib.Path | None:
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    for alvo in sorted(profiles_dir().glob("*.json")):
        return alvo
    return None


def _bytes_do_perfil() -> bytes:
    """O arquivo CRU — é assim que *"não gravou"* se mede, sem perguntar ao dublê."""
    alvo = _arquivo_do_perfil()
    return alvo.read_bytes() if alvo is not None else b""


def _do_controle(uniq_chave: str) -> dict[str, Any]:
    alvo = _arquivo_do_perfil()
    if alvo is None:
        return {}
    lido = json.loads(alvo.read_text(encoding="utf-8"))
    bloco = (lido.get("controllers") or {}).get(uniq_chave)
    return bloco if isinstance(bloco, dict) else {}


def _dele(uniq: str = P1) -> dict[str, Any]:
    """O que o daemon publica: sabe o mudo do microfone e o volume do alto-falante."""
    return {"uniq": uniq, "transport": "usb", "connected": True, "inputs": {},
            "audio": {"mic_mudo": False},
            "speaker": {"volume": 100, "muted": False, "rota": 2}}


def _ctx(*entradas: dict[str, Any]) -> Any:
    import pacotes

    return pacotes.Contexto(state={"active_profile": NOME}, mesa=[],
                            conectados=list(entradas) or [_dele()], estados={})


def _gesto(nome: str) -> Any:
    import pacotes
    import pacotes.a02_controles  # importar é registrar: o decorador `@gesto`

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


# ===========================================================================
# 1. O mudo confessa o alvo
# ===========================================================================


def test_o_mudo_confessa_quando_o_alvo_nao_foi_honrado(casa: Any) -> None:
    """MORDIDA: arranque as duas linhas da confissão e isto reprova.

    Sem elas o gesto passa das duas metades do ato, grava o override e volta
    como SUCESSO — que é o defeito inteiro na mesa cheia: a tela pinta o selo do
    cartão certo e quem ficou mudo foi outra pessoa.

    A TERCEIRA ASSERÇÃO É A ORDEM, e ela é a razão de a confissão vir antes do
    `_lembrar_do_som`: gravar primeiro poria no `controllers[este]` um estado
    que este controle nunca teve. Ela lê os BYTES do arquivo — perguntar ao
    dublê mediria a intenção do código que está sob teste.
    """
    antes = _bytes_do_perfil()
    p = PonteQueDizDeQuem({"status": "ok", "por_uniq": False})

    with pytest.raises(RuntimeError) as erro:
        _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "microfone"}, p)

    assert str(erro.value) == frase_do_alvo_do_mic(False), (
        "o gesto do mudo não confessou o alvo — o pedido caiu na rota global e "
        "o botão voltou como sucesso"
    )
    assert p.nomes == ["mic_canal_set_detalhado"], (
        f"o gesto pediu mais que o ato ao daemon: {p.nomes!r}"
    )
    assert _bytes_do_perfil() == antes, (
        "o perfil mudou com o alvo NÃO honrado — o disco passou a guardar um "
        "mudo que este controle nunca teve"
    )


@pytest.mark.parametrize(
    ("rotulo", "corpo"),
    [
        ("honrado", {"status": "ok", "por_uniq": True}),
        ("desconhecido", {"status": "ok", "por_uniq": None}),
        ("o daemon não disse nada a respeito", {"status": "ok"}),
    ],
)
def test_o_mudo_nao_acusa_quando_honrou_nem_quando_nao_sabe(
    casa: Any, rotulo: str, corpo: dict[str, Any]
) -> None:
    """A MORDIDA QUE SEPARA A CURA DA SUPERSTIÇÃO — *"não sei" não é "não honrei"*.

    `frase_do_alvo_do_mic` devolve `""` para `True` e para `None` de propósito, e
    o terceiro caso é o daemon DESTA árvore: o corpo de `mic.canal.set` não traz
    `por_uniq` (ver a régua-estopim, abaixo). Acusar por ausência de notícia
    poria no cartão dela um erro que ninguém mediu — e calaria o botão do
    microfone em todo clique, com o daemon fazendo a coisa certa.

    MORDIDA: troque a condição por `alvo_honrado(corpo) is not True` e os três
    casos reprovam.
    """
    p = PonteQueDizDeQuem(corpo)
    _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "microfone"}, p)

    assert _do_controle(CHAVE_P1).get("mic") == {"muted": True}, (
        f"com o alvo {rotulo}, o mudo não chegou ao perfil — a confissão "
        f"recusou um gesto que o daemon honrou"
    )


def test_a_frase_da_confissao_e_a_do_dono(casa: Any) -> None:
    """A frase não se digita: ela vem de `frase_do_alvo_do_mic`.

    ESTA RÉGUA NÃO REPETE O TEXTO, e é a regra da casa: quem digita a frase mede
    a PALAVRA e não o ATO, e passa a dar verde no dia em que o dono mudar de
    opinião sem o gesto mudar junto. O que ela cobra é a IDENTIDADE com o que o
    dono devolve.

    **E ELA GUARDA O CONFLITO QUE ESTA LEVA ACHOU:** a frase do dono começa
    falando de VOLUME, porque nasceu para o deslizante. Dita depois de um clique
    no 🎙, nomeia um gesto que ela não fez. Enquanto o daemon não responder
    `por_uniq` neste caminho, a frase é inerte; o dia em que responder, a palavra
    é dela — e quem cobra isso é a régua-estopim abaixo.
    """
    p = PonteQueDizDeQuem({"status": "ok", "por_uniq": False})
    with pytest.raises(RuntimeError) as erro:
        _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "microfone"}, p)

    assert str(erro.value) == frase_do_alvo_do_mic(False)
    assert frase_do_alvo_do_mic(True) == frase_do_alvo_do_mic(None) == "", (
        "o dono passou a acusar sobre 'honrado' ou sobre 'não sei' — os dois "
        "gestos desta aba que o consultam mudam de comportamento junto"
    )


def test_a_metade_do_ato_continua_falando_antes_da_confissao(casa: Any) -> None:
    """As duas perguntas são diferentes, e a ordem delas é medida.

    `frase_do_ato_do_microfone` responde QUAL METADE faltou (o canal foi eleito e
    o firmware ficou represado · o firmware obedeceu e não há canal);
    `frase_do_alvo_do_mic` responde DE QUEM era o microfone. Com as duas
    disponíveis quem fala é a primeira — ela descreve o que o daemon acabou de
    relatar, e a segunda fala de um alvo que, nesse corpo, nem chegou a ser
    tocado.
    """
    motivo = "o canal deste controle não foi tocado"
    p = PonteQueDizDeQuem(
        {"status": "incompleto", "motivo": motivo, "por_uniq": False}
    )
    with pytest.raises(RuntimeError) as erro:
        _gesto("mudo")(_ctx(), {"uniq": P1, "mudo": "microfone"}, p)

    assert str(erro.value) == motivo, (
        "a confissão do alvo passou na frente da metade que faltou — quem está "
        "com o controle na mão perdeu a notícia de qual metade do ato não deu"
    )


def test_o_ato_do_microfone_ainda_nao_diz_de_quem_e_o_microfone() -> None:
    """A RÉGUA-ESTOPIM: o fato medido em 06/09/2026, e o dia em que ele mudar.

    O corpo de `mic.canal.set` é montado por `AtoDoMicrofone.como_corpo`, e ele
    não tem `por_uniq` — quem tem é o `mic.volume.set`. Logo a confissão do gesto
    `mudo` é, hoje, uma trava armada e calada: `alvo_honrado` devolve `None` e
    nada é dito. **Isso não é defeito e não se conserta daqui** — o ato já recusa
    dizendo quando a eleição do canal não é deste controle, e essa recusa sobe
    pela outra frase.

    **QUANDO O CAMPO NASCER, ESTA RÉGUA REPROVA — e é o que se quer.** Nesse dia
    duas coisas passam a valer de uma vez: a confissão deixa de ser inerte, e a
    frase do dono (`TEXTO_MIC_ALVO_NAO_HONRADO`, marcada `PROVISÓRIO — decisão
    dela`) começa a dizer *"O volume foi para o microfone de OUTRO controle"*
    depois de um clique no botão de MUDO.
    """
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        AtoDoMicrofone,
        MetadeDoAto,
    )

    corpo = AtoDoMicrofone(
        uniq=P1,
        ligado=True,
        canal_no_sistema=MetadeDoAto(True),
        firmware=MetadeDoAto(True),
    ).como_corpo()

    assert "por_uniq" not in corpo, (
        "`mic.canal.set` passou a dizer DE QUEM foi o microfone. A confissão do "
        "gesto `mudo` deixou de ser inerte — e a frase do dono fala de VOLUME. "
        "Antes de deixar isto chegar à tela dela, a frase precisa da palavra "
        "dela: ver `TEXTO_MIC_ALVO_NAO_HONRADO` e a entrega da "
        "A-CONFISSAO-NO-BOTAO-01"
    )


# ===========================================================================
# 2. O som de confirmação
# ===========================================================================


@pytest.mark.parametrize(
    ("gesto", "clique"),
    [
        ("volume", {"volume": "alto-falante", "valor": "42"}),
        ("mudo", {"mudo": "alto-falante"}),
        ("rota", {"rota": "jogo"}),
    ],
)
def test_os_tres_gestos_do_alto_falante_confirmam_com_som(
    casa: Any, som: list[tuple[str, Any]], gesto: str, clique: dict[str, Any]
) -> None:
    """MORDIDA: arranque `_confirmar_com_som` de qualquer um dos três e reprova.

    São os três que esta aba tem, e a GTK toca nos quatro dela — o quarto é a
    devolução da posse, que esta tela não oferece. Cobrir só o deslizante
    deixaria a próxima pessoa remedindo o mesmo defeito nos outros dois: *quando
    a cura conhece a causa, ela cobre todos os chamadores*.

    O SOM VAI PARA O SINK DAQUELE CONTROLE, e é o ponto inteiro: o motor recusa
    sink vazio em vez de cair no padrão, porque um `paplay --device` inexistente
    sai com ZERO e toca na televisão dela.
    """
    _gesto(gesto)(_ctx(), {"uniq": P1, **clique}, PonteQueDizDeQuem())

    assert som == [(SINK, None)], (
        f"o gesto {gesto!r} não confirmou com som: {som!r}. O registrador de "
        f"volume não tem leitura de volta hoje — sem o som ela mexe e não tem "
        f"como saber que a mudança valeu"
    )


def test_o_som_nao_segura_o_botao_em_voo(casa: Any,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: chame `tocar_confirmacao` no corpo do gesto e isto reprova.

    O gesto já roda fora do laço do GTK (o piloto o despacha numa thread), então
    a tela não congela — o que se paga chamando o som ali é a RESPOSTA VISUAL:
    o botão só volta do voo, e o campo só pisca verde, quando o gesto retorna, e
    o som custa 0,35 s medidos com teto de 5 s.

    A régua desliga `_fora_do_voo` (ele não executa nada) e cobra que nenhum som
    tenha saído no corpo do gesto: se algum saiu, a chamada não passou pelo
    ponto de injeção.
    """
    import pacotes.a02_controles as a02

    tocados: list[str] = []
    monkeypatch.setattr(
        a02.audio_saida, "tocar_confirmacao",
        lambda sink, **k: tocados.append(sink))
    monkeypatch.setattr(a02, "_sink_para_o_som", lambda uniq, na_mesa: SINK)
    guardadas: list[Any] = []
    monkeypatch.setattr(a02, "_fora_do_voo", guardadas.append)

    _gesto("volume")(
        _ctx(), {"uniq": P1, "volume": "alto-falante", "valor": "42"},
        PonteQueDizDeQuem())

    assert tocados == [], (
        "o som tocou dentro do corpo do gesto — o botão fica em voo e a piscada "
        "verde espera o tocador"
    )
    assert len(guardadas) == 1, (
        "o gesto não passou o som pelo ponto de injeção `_fora_do_voo`"
    )


def test_o_som_que_falha_nao_derruba_o_volume(
    casa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA 2 da sprint: ponha o motor para levantar e a gravação segue.

    O som é CONFIRMAÇÃO, não pré-requisito. Um alto-falante mudo que impedisse o
    volume de mudar seria o defeito trocado de lugar — e, na thread de verdade,
    uma exceção solta viraria traceback no terminal de quem lançou a janela, que
    ninguém lê.

    MORDIDA: tire o `try` de dentro de `tocar` e isto reprova com a exceção
    subindo pelo gesto.
    """
    import pacotes.a02_controles as a02

    def explode(_sink: str, **_k: Any) -> Any:
        raise OSError("o tocador sumiu no meio")

    monkeypatch.setattr(a02.audio_saida, "tocar_confirmacao", explode)
    monkeypatch.setattr(a02, "_fora_do_voo", lambda fn: fn())
    monkeypatch.setattr(a02, "_sink_para_o_som", lambda uniq, na_mesa: SINK)

    _gesto("volume")(
        _ctx(), {"uniq": P1, "volume": "alto-falante", "valor": "42"},
        PonteQueDizDeQuem())

    assert _do_controle(CHAVE_P1).get("speaker", {}).get("volume") is not None, (
        "o som que falhou levou a gravação do volume junto"
    )


def test_a_chave_dela_desliga_o_som_e_o_gesto_nao_recusa(
    casa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA 3 da sprint, e ela roda o motor DE VERDADE — sem tocar nada.

    A chave é do motor (`audio_saida.som_ligado`, o primeiro dos sete degraus), e
    o gesto não inventa uma segunda: ele chama `tocar_confirmacao` sem opinião
    sobre `ligado`. Com a chave desligada o motor sai calado, e o clique continua
    valendo.

    OS DOIS ESPIÕES SÃO A REDE DE SEGURANÇA, e não enfeite: **a bancada desta
    sprint é `false`**. Se a cura deixasse de respeitar a chave, o `_rodar_tocador`
    seria chamado — e aqui ele é um espião, não o `paplay`. Nenhum som sai da
    suíte, nem por engano.

    MORDIDA: passe `ligado=True` na chamada do gesto e isto reprova.
    """
    import pacotes.a02_controles as a02

    passos: list[Any] = []
    monkeypatch.setattr(audio_saida, "_carregar_prefs",
                        lambda: {audio_saida.CHAVE_PREF_SOM: False})
    monkeypatch.setattr(audio_saida, "_rodar_tocador",
                        lambda argv: passos.append(argv) or 0)
    monkeypatch.setattr(audio_saida, "rodar_leitura",
                        lambda argv: passos.append(argv) or "")
    monkeypatch.setattr(a02, "_fora_do_voo", lambda fn: fn())
    monkeypatch.setattr(a02, "_sink_para_o_som", lambda uniq, na_mesa: SINK)

    _gesto("volume")(
        _ctx(), {"uniq": P1, "volume": "alto-falante", "valor": "42"},
        PonteQueDizDeQuem())

    assert passos == [], (
        f"com a chave dela DESLIGADA o produto foi ao sistema de áudio: "
        f"{passos!r}"
    )
    assert _do_controle(CHAVE_P1).get("speaker", {}).get("volume") is not None, (
        "a chave do som desligada recusou o gesto do volume"
    )


def _seletor_do_piloto(*_a: Any, **_k: Any) -> None:
    """O que o piloto põe em `ponte.escolher_arquivo` ao subir a janela.

    Ela mora no módulo do TESTE de propósito: é o `__module__` diferente que
    `ponte.dentro_da_janela` lê, e é exatamente o que acontece quando o piloto
    substitui o ponto de extensão pelo método dele.
    """
    return None


class TestAGuardaDaMaquinaDela:
    """**Sem a janela de pé, o som não nasce — e o defeito que isto cura era MEU.**

    Medido na bancada em 06/09/2026, com a cura do som já escrita: a régua irmã
    `test_a02_som_e_sensor_falam_quando_recusam.py` dubla o `pactl` e devolve uma
    lista com um sink de DualSense. O `escolher_sink` casa por REGRA (o
    um-para-um: uma fonte, um controle na mesa), o motor encontra o sink "na
    lista viva" — que é de mentira — e segue para o `paplay`, **que não está
    dublado**. A suíte tocava som no alto-falante do controle DELA, com ela
    trabalhando.

    **A guarda-mãe do `audio_saida` não alcança este caso, e é de propósito:**
    ela confere o sink contra a lista viva, e numa régua a lista viva é de
    mentira. Quem sabe que ninguém clicou é a camada de cima.
    """

    def test_sem_a_janela_de_pe_o_som_nao_nasce(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire o `dentro_da_janela` de `_fora_do_voo` e isto reprova.

        Os dois lados são medidos: sem janela a linha do som **não nasce**; com
        o ponto de extensão substituído — que é o que o piloto faz ao subir —
        ela nasce. Uma guarda que só sabe recusar desligaria o produto.
        """
        import pacotes.a02_controles as a02
        from pacotes import ponte as _ponte

        assert not _ponte.dentro_da_janela(), (
            "a régua acha que há janela de pé — sem isso ela não mede nada"
        )
        correu = threading.Event()
        a02._fora_do_voo(correu.set)
        assert not correu.wait(0.3), (
            "o som nasceu SEM janela: numa régua com `pactl` dublado isto chega "
            "ao `paplay` e toca no alto-falante do controle dela"
        )

        monkeypatch.setattr(_ponte, "escolher_arquivo", _seletor_do_piloto)
        assert _ponte.dentro_da_janela()
        a02._fora_do_voo(correu.set)
        assert correu.wait(3.0), (
            "com a janela de pé o som deixou de nascer — a guarda passou a "
            "desligar o produto em vez de proteger a máquina dela"
        )

    def test_o_cenario_que_tocava_som_de_verdade(
        self, casa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O cenário EXATO da régua irmã, com o tocador espionado.

        `pactl` dublado devolvendo o sink do DualSense, mesa de um, e o gesto
        `rota` — que é o mesmo caminho que a irmã exercita três vezes. Com a
        guarda, `_rodar_tocador` **não** é chamado.

        MORDIDA: tire o `dentro_da_janela` de `_fora_do_voo` e o espião registra
        um `paplay --device=<o sink do controle dela>`.
        """

        def pactl(argv: list[str]) -> str:
            if argv[:2] == ["pactl", "get-default-sink"]:
                return "alsa_output.pci-0000_00_1f.3.analog-stereo\n"
            if argv[:4] == ["pactl", "list", "sinks", "short"]:
                return f"0\t{SINK}\tmodule\ts16le 2ch 48000Hz\tSUSPENDED\n"
            return ""

        tocou: list[Any] = []
        monkeypatch.setattr(audio_saida, "rodar_leitura", pactl)
        monkeypatch.setattr(audio_saida, "_rodar_tocador",
                            lambda argv: tocou.append(argv) or 0)

        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "jogo"}, PonteQueDizDeQuem())
        time.sleep(0.3)

        assert tocou == [], (
            f"a suíte chegou ao tocador de áudio de verdade: {tocou!r}. O sink "
            f"casou pela regra do um-para-um sobre uma lista de mentira, e o "
            f"`paplay` não estava dublado"
        )


def test_o_sink_sai_do_cache_da_camada_1_e_nunca_do_padrao(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """De onde vem o sink, e por que a resposta vazia é a certa.

    O cache da camada 1 é o dono barato (uma thread o renova a cada 2 s, e a aba
    02 é a mais pintada da casa). No caso frio — o primeiro clique de uma aba
    recém-aberta — quem responde é o MESMO dono que o cache consulta,
    `audio_saida.sink_do_controle`, e não uma segunda regra de atribuição.

    `""` É RESPOSTA HONESTA: o controle sem placa de som atribuída não tem para
    onde tocar, e o motor recusa em vez de cair no sink padrão — que é a
    guarda-mãe do `audio_saida` (`paplay --device` inexistente sai com ZERO e
    toca na televisão dela).
    """
    import pacotes.a02_controles as a02

    monkeypatch.setitem(a02._CAMADA_1, P1, type("L", (), {
        "sink_do_controle": SINK})())
    assert a02._sink_para_o_som(P1, (P1,)) == SINK

    a02._CAMADA_1.pop(P1, None)
    monkeypatch.setattr(a02.audio_saida, "sink_do_controle",
                        lambda uniq, mesa: "")
    assert a02._sink_para_o_som(P1, (P1,)) == "", (
        "sem sink conhecido o caminho do som inventou um nome — e um nome "
        "inventado toca no sink PADRÃO do sistema"
    )
