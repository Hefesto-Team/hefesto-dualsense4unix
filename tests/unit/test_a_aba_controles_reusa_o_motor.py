#!/usr/bin/env python3
"""A RÉGUA DO REUSO NA ABA CONTROLES — e das três regras que ela reescrevia errado.

POR QUE ELA EXISTE. LEI 0 da migração, palavra dela em 02/09/2026:

    *"no gtk eu já deixei praticamente tudo pronto, estamos adaptando e migrando
    o que fizemos na versão estável pra ela funcionar no html. Não temos que
    recriar nada."*

`app/widgets/controller_card.py` tem **26 funções públicas de módulo** — 5.951
linhas de texto de tela que a GTK já provou. Medido em 02/09/2026, a interface
nova alcançava DUAS (`rotulo_lightbar`, pela aba Iluminação, e
`texto_degradacao`, pelo `pacotes/__init__.py`), e **esta aba, a mais servida
das dez, chamava ZERO**. Ela reescrevia à mão o que o motor já sabia — e três
das reescritas estavam ERRADAS.

O QUE CADA UMA CUSTAVA, medido com os DOIS controles dela na mesa (um `usb`, um
`bt`) em 02/09/2026 às 16h:

1. **"102%"**. `speaker.volume` é o registrador do protocolo, **0-255**
   (`ipc_handlers.py:3584`), e a aba EMITIA o número CRU com um `%` colado. O
   valor vivo era 102, e o pacote emitia uma porcentagem acima de cem; no talo
   ele emitiria "255%". E a conta certa não é `bruto / 255`: `core/speaker_scale.py`
   existe por causa da curva MEDIDA no hardware — abaixo de 38 tudo é mudo,
   acima de 102 tudo é o mesmo volume.
   **EMITIA, e não MOSTRAVA** (medido em 02/09/2026, contra a primeira redação
   deste arquivo): o `alto-estado` é `hidden` na página publicada e o `escrever`
   do piloto não toca esse atributo — o número ia para um vão invisível. O
   defeito é real e latente; dizer que chegou aos olhos dela é a afirmação
   forte que esta casa cobra prova.
2. **"0%" sobre um alto-falante que ninguém mediu.** `sp.get('volume', 0)`
   transformava AUSÊNCIA em zero. O daemon só publica `speaker` depois do
   primeiro `speaker.set` (`ipc_handlers.py:4600`).
3. **`#000000` sobre uma cor desconhecida.** O motor diz por que é mentira, com
   todas as letras: *"o 0,0,0 do sysfs sem escrita nossa pode ser o azul-kernel
   brilhando neste exato momento"* (`controller_card.rotulo_lightbar`).
4. **um ramo inteiro que só sabia devolver `—`.** A máscara caía em
   `NOME_DA_MASCARA.get(vpad_backend, "—")`, e `NOME_DA_MASCARA` é indexada por
   MÁSCARA (`dualsense`, `xbox`) enquanto `vpad_backend` vale `uhid`/`uinput`/
   `None`. Um `.get` com padrão não estoura, e por isso o defeito era mudo.
5. **uma leitura cega à segunda posição do bloco.** `speaker_do_entry` aceita
   `entry["speaker"]` **e** `entry["inputs"]["speaker"]` porque *"quem publica é
   o daemon, e o widget não pode quebrar por causa de onde o dado mora"*. Este
   arquivo lia só a primeira, em TRÊS lugares — a pintura, o gesto do ♪ e o
   `_volume_conhecido`.

A MORDIDA de cada caso está escrita no teste que a cobra.

O QUE ESTA RÉGUA **NÃO** MEDE, e é declarado para não virar verde por vacuidade:
ela não mede TEXTO de código. A auditoria do selo do microfone (02/09/2026)
mostrou o preço de medir fonte com `inspect.getsource`: *"trocar `mic_sabemos`
por `True` deixa o controle caído voltando a pintar ATIVO com a régua VERDE"*.
A asserção estrutural é de IDENTIDADE de objeto
(`a02.speaker_do_entry is controller_card.speaker_do_entry`) — reimplementar a
função localmente quebra a identidade, e nenhuma reescrita de comentário a
afeta. **Ela cobre os CINCO nomes desde 02/09/2026**: cobria dois, e a
auditoria mediu o buraco — clonar `texto_volume` dentro do pacote passava nos
15 testes e no `ruff`.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O REGISTRADOR VIVO DA MESA DELA em 02/09/2026, 16h: `speaker.volume` = 102
#: nos dois controles. É o número que o pacote emitia como "102%".
VOLUME_VIVO = 102


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def motor():
    from hefesto_dualsense4unix.app.widgets import controller_card

    return controller_card


class PonteDeMentira:
    """Dublê da `pacotes/ponte.py` que guarda o que foi chamado.

    Mesma forma do dublê de `test_os_botoes_tem_dono.py`: `__getattr__` responde
    por qualquer nome, de propósito, para não virar uma segunda lista das
    funções da ponte.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any):
            self.chamadas.append((nome, args, kwargs))
            return (True, None) if nome.endswith("_set") and "identity" in nome else True

        return registrar


def _card(pac, a02, entrada: dict, state: dict | None = None) -> dict:
    """O dicionário de UM card, do pacote real, sem janela e sem daemon."""
    ctx = pac.Contexto(state=state or {}, mesa=[], conectados=[entrada], estados={})
    return next(iter(a02.pacote(ctx)["cards"].values()))


#: O controle da régua. Sem `speaker` e sem `lightbar_*` de propósito: cada
#: teste monta o que a sua pergunta precisa, em vez de herdar um estado que
#: ninguém leu.
BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
}


# --------------------------------------------------------------------------
# 1. O VOLUME — o registrador cru com um sinal de porcentagem
# --------------------------------------------------------------------------
def test_o_volume_nao_e_o_registrador_cru_com_por_cento(pac, a02):
    """102 no registrador é **100 %** no campo, e nunca "102%".

    O rótulo é o do produto (`sensor_widgets.texto_volume`), que passa pela
    curva medida de `core/speaker_scale.py`. Os dois lados são cobrados: o que
    a tela TEM de dizer e o que ela NÃO pode dizer.

    MORDE: devolver `f"{sp.get('volume', 0)}%"` a esta linha reprova aqui com
    `'102%' != '100 %'` — que é exatamente o que o pacote emitia com a
    mesa dela cheia.
    """
    d = _card(pac, a02, {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": False}})
    assert d["alto-estado"] == "100 %"
    assert "%" in d["alto-estado"]
    assert str(VOLUME_VIVO) not in d["alto-estado"], (
        "a tela escreveu o registrador cru do protocolo como se fosse por cento")


def test_o_talo_do_registrador_nao_vira_duzentos_e_cinquenta_e_cinco_por_cento(pac, a02):
    """255 é o talo da escala do protocolo, e o talo da tela é 100 %.

    MORDE: qualquer conta linear (`volume * 100 // 255`) devolve 100 aqui e
    passa — por isso o caso do 128 vem junto: ele SOA igual ao 255 (a curva
    satura em 102), e a linear diria "50 %" sobre o volume máximo. É o defeito
    nomeado em `core/speaker_scale.fracao_do_volume`.
    """
    talo = _card(pac, a02, {**BASE, "speaker": {"volume": 255, "muted": False}})
    meio = _card(pac, a02, {**BASE, "speaker": {"volume": 128, "muted": False}})
    assert talo["alto-estado"] == "100 %"
    assert meio["alto-estado"] == "100 %", (
        "128 soa igual a 255 no alto-falante do DualSense (curva medida em "
        "01/08/2026) — uma conta linear diria 50 % sobre o volume máximo")


def test_o_mudo_vence_a_porcentagem(pac, a02):
    """Calado, o campo diz "Mudo" — a régua não pode virar "sempre por cento".

    MORDE: trocar `texto_volume(*sp_lido)` por `f"{percentual}...%"` reprova
    aqui, porque a palavra some.
    """
    d = _card(pac, a02, {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": True}})
    assert d["alto-estado"] == "Mudo"


def test_sem_alto_falante_a_tela_nao_diz_zero(pac, a02):
    """Ausência não é zero. O daemon só publica `speaker` depois do primeiro set.

    MORDE: devolver o `sp.get('volume', 0)` faz este teste reprovar com
    `'0%' != '—'` — a tela afirmando "o volume está no mínimo" sobre um
    alto-falante que ninguém mediu. É o gêmeo exato do "Sem toque" que a régua
    do analógico já trancou.
    """
    import mesa_viva

    d = _card(pac, a02, BASE)
    assert d["alto-estado"] == mesa_viva.SEM_LEITOR
    assert "0" not in d["alto-estado"]


def test_o_bloco_do_alto_falante_e_lido_nas_duas_posicoes(pac, a02):
    """`inputs.speaker` vale tanto quanto `entry.speaker` — o motor aceita as duas.

    A razão é do daemon, e está escrita em `controller_card.speaker_do_entry`:
    *"quem publica é o daemon, e o widget não pode quebrar por causa de onde o
    dado mora"*. Medido na mesa dela em 02/09/2026, o daemon publica nas DUAS;
    esta régua tranca o dia em que ele publicar só na de dentro.

    MORDE: voltar a `c.get("speaker") or {}` reprova aqui com `'—'`, e o
    defeito seria INVISÍVEL enquanto o daemon mandasse as duas.
    """
    dentro = {k: v for k, v in BASE.items() if k != "speaker"}
    dentro["inputs"] = {"speaker": {"volume": 60, "muted": False}}
    assert _card(pac, a02, dentro)["alto-estado"] == "34 %"


# --------------------------------------------------------------------------
# 2. O GESTO DO ♪ — a mesma leitura, do outro lado do clique
# --------------------------------------------------------------------------
def test_o_mudo_do_alto_falante_le_a_segunda_posicao(pac, a02):
    """Clicar no ♪ com o volume só em `inputs.speaker` manda o volume junto.

    O daemon RECUSA `speaker.set {muted}` sem volume conhecido de propósito
    (`ipc_handlers.py:4682`): calar como primeira escrita tranca o alto-falante
    em zero e o próprio mudo não o solta. Com a leitura cega à segunda posição,
    o botão mandava o pedido SEM volume — e o daemon o recusava sobre um volume
    que estava no payload, duas chaves ao lado.

    MORDE: devolver `(dele.get("speaker") or {}).get("volume")` ao
    `_volume_conhecido` reprova aqui — o `volume` some do payload.
    """
    entrada = {k: v for k, v in BASE.items() if k != "speaker"}
    entrada["inputs"] = {"speaker": {"volume": 60, "muted": True}}
    ctx = pac.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    p = PonteDeMentira()
    a02.mudo(ctx, {"uniq": UNIQ, "mudo": "alto-falante"}, p)
    assert p.chamadas == [
        ("speaker_set", (), {"muted": False, "uniq": UNIQ, "volume": 60})
    ], "o gesto não leu o bloco que o daemon publicou dentro de `inputs`"


def test_sem_volume_conhecido_o_pedido_vai_sem_volume(pac, a02):
    """O outro lado: sem bloco nenhum, o payload NÃO inventa um número.

    Mandar um palpite tomaria a posse do registrador com o valor errado — a
    razão está no `_volume_conhecido`, e vem da GUI estável.

    MORDE: fazer `_volume_conhecido` devolver `{"volume": 0}` na ausência
    reprova aqui.
    """
    ctx = pac.Contexto(state={}, mesa=[], conectados=[BASE], estados={})
    p = PonteDeMentira()
    a02.mudo(ctx, {"uniq": UNIQ, "mudo": "alto-falante"}, p)
    assert p.chamadas == [("speaker_set", (), {"muted": True, "uniq": UNIQ})]


# --------------------------------------------------------------------------
# 3. A COR DA BARRA — `#000000` sobre o que ninguém mediu
# --------------------------------------------------------------------------
def test_a_cor_de_fonte_desconhecida_nao_vira_preto(pac, a02):
    """`lightbar_source == "desconhecida"` é "não sei", e não "apagada".

    O dono da regra é `controller_card.rotulo_lightbar`, e ele devolve `None`
    como cor-base exatamente aqui. A frase dele: *"NUNCA 'apagada': o 0,0,0 do
    sysfs sem escrita nossa pode ser o azul-kernel brilhando neste exato
    momento"*.

    MORDE: voltar ao `"#{:02X}{:02X}{:02X}".format(*rgb[:3])` cru reprova aqui
    com `'#000000' != '—'`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "desconhecida"})
    assert d["luz-hex"] == mesa_viva.SEM_LEITOR
    assert "000000" not in d["luz-hex"]


def test_a_cor_conhecida_continua_saindo(pac, a02):
    """A metade que prova que a cura não é "nunca mais mostra cor nenhuma".

    MORDE: devolver `mesa_viva.SEM_LEITOR` em todos os casos reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 255],
                         "lightbar_source": "sysfs", "lightbar_on": True})
    assert d["luz-hex"] == "#0000FF"


def test_a_barra_apagada_nao_diz_nao_sei(pac, a02):
    """Apagada é um FATO, e "não sei" é outra coisa — o campo tem de separá-los.

    ESTA RÉGUA COBRAVA O DEFEITO ATÉ 02/09/2026. Ela dizia *"barra apagada não
    tem código de cor a mostrar — o motor devolve o neutro"* e exigia
    `SEM_LEITOR`; o `None` do motor ali é a base do ACCENT (*"None = usar o
    neutro"*, `controller_card.py:1178`), não a resposta "não sei". Com o mesmo
    travessão que o piloto usa para null (`hefesto_vivo.py:118`), a tela dizia
    "não medi" sobre a única coisa que se mediu.

    MORDE: voltar a decidir pela base (`base is not None`) reprova aqui com
    `'—' != '#000000'`, porque o motor devolve `None` como base nos DOIS casos.
    """
    import mesa_viva

    apagada = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 255],
                               "lightbar_source": "sysfs", "lightbar_on": False})
    naosei = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                              "lightbar_source": "desconhecida"})
    assert apagada["luz-hex"] == a02.HEX_DA_LUZ_APAGADA
    assert apagada["luz-hex"] != mesa_viva.SEM_LEITOR
    assert apagada["luz-hex"] != naosei["luz-hex"], (
        "dois estados que o motor SEPARA voltaram a mostrar a mesma coisa")


def test_o_zero_de_uma_barra_desligada_tambem_e_apagada(pac, a02):
    """O outro ramo do "apagada": `rgb == (0,0,0)` com a fonte NOSSA.

    O motor manda os dois para a mesma frase (`controller_card.py:1189`), e a
    tela tem de mandá-los para o mesmo lugar — senão a cura separa três estados
    onde o dono separa dois.

    MORDE: cravar `#000000` só no ramo `lightbar_on is False` reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "sysfs", "lightbar_on": True})
    assert d["luz-hex"] == a02.HEX_DA_LUZ_APAGADA


def test_em_nativo_a_tela_nao_afirma_a_cor_crua(pac, a02):
    """Modo Nativo: o jogo é dono do LED, e o `rgb` que sobra é CRU.

    O RAMO NÃO TINHA UM ÚNICO CASO até 02/09/2026 — os três testes de `luz-hex`
    passavam `state=None`, então `native_mode` era sempre falso, e a cura que
    dizia curar "o `#000000` sobre cor desconhecida" **não alcançava este
    ramo**: medido com sonda, `nativo + fonte desconhecida + rgb 0,0,0` dava
    `#000000` antes e depois dela.

    `rotulo_lightbar` decide `native_mode` PRIMEIRO (`controller_card.py:1182`)
    e devolve o `rgb` CRU — o teste de fonte desconhecida nem é alcançado. A
    GTK mostra essa cor COM a frase que a explica ao lado; aqui a frase não tem
    endereço, e cor sem ressalva é afirmar o que ninguém mediu.

    MORDE: decidir pela base (`base is not None`) reprova aqui com `'#000000'`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "desconhecida", "lightbar_on": True},
              state={"native_mode": True})
    assert d["luz-hex"] == mesa_viva.SEM_LEITOR
    assert "000000" not in d["luz-hex"]


def test_com_a_steam_segurando_o_fd_a_tela_nao_afirma_a_cor_crua(pac, a02):
    """`lightbar_disputada`: o segundo ramo que a cura de 02/09 não alcançava.

    O motor explica por que a cor não vale: com a Steam segurando o `fd`, *"o
    que a classe LED devolve é o que o Hefesto PEDIU — a madrugada de 16/08 leu
    `[0 255 0]` com a barra apagada e `[0 255 0]` com ela verde"*.

    MORDE: decidir pela base reprova aqui com `'#000000'`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "desconhecida", "lightbar_on": True,
                         "lightbar_disputada": True})
    assert d["luz-hex"] == mesa_viva.SEM_LEITOR


def test_o_rotulo_da_apagada_e_perguntado_ao_motor(a02, motor):
    """A frase da barra apagada não é digitada nesta aba — ela é PERGUNTADA.

    Das quatro frases de `rotulo_lightbar`, só `ROTULO_LIGHTBAR_SEGURADA` é
    constante exportada. Digitar as outras aqui seria a cópia muda que a LEI 0
    proíbe: no dia em que o motor trocasse o texto, a aba voltaria a colapsar
    "apagada" e "não sei" com a régua verde.

    ESTE TESTE É O QUE TRANCA A PERGUNTA. Ele cobra que a resposta seja uma
    frase de verdade e que ela seja DIFERENTE das outras três — se a ordem dos
    ramos do motor mudar e a sondagem cair no ramo errado, a igualdade acusa.

    MORDE: digitar `ROTULO_DA_LUZ_APAGADA = "Lightbar: apagada"` continua
    passando (a string é a mesma nos dois mundos) — quem pega essa é o dia em
    que o motor mudar. O que ESTE teste pega é a sondagem cair no ramo errado,
    e a mordida é trocar o `lightbar_on` da sondagem para `True`: a resposta
    vira `None` e a primeira asserção reprova.
    """
    naosei = motor.rotulo_lightbar({"lightbar_source": "desconhecida"}, {})[0]
    nativo = motor.rotulo_lightbar({}, {"native_mode": True})[0]
    acesa = motor.rotulo_lightbar(
        {"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs",
         "lightbar_on": True}, {})[0]

    assert isinstance(a02.ROTULO_DA_LUZ_APAGADA, str) and a02.ROTULO_DA_LUZ_APAGADA
    assert acesa is None, "o ramo da cor conhecida deixou de ser o sem-rótulo"
    for outro in (naosei, nativo, motor.ROTULO_LIGHTBAR_SEGURADA):
        assert outro != a02.ROTULO_DA_LUZ_APAGADA, (
            f"a sondagem da barra apagada caiu no ramo de {outro!r}")


# --------------------------------------------------------------------------
# 4. A MÁSCARA — o ramo que só sabia devolver travessão
# --------------------------------------------------------------------------
def test_o_backend_uhid_diz_dualsense(pac, a02):
    """`uhid` implica máscara DualSense, e a regra é do produto.

    `virtual_pad._try_uhid` recusa o uhid para saída Xbox — *"Xbox não é
    trabalho do uhid"*, o `hid_playstation` só faz bind em produto Sony —, e é
    por isso que `home_actions.mascara_viva` pode afirmar a máscara a partir do
    backend. A aba não podia: ela procurava `uhid` numa tabela cujas chaves são
    `dualsense` e `xbox`, e o `.get` com padrão devolvia `—` calado.

    MORDE: devolver `NOME_DA_MASCARA.get(c.get("vpad_backend") or "", "—")`
    reprova aqui com `'—' != 'DualSense'`.
    """
    d = _card(pac, a02, {**BASE, "vpad_backend": "uhid"})
    assert d["mascara"] == "DualSense"


def test_o_backend_uinput_e_ambiguo_e_diz_nao_sei(pac, a02):
    """`uinput` é Xbox normal OU DualSense degradado — dizer "não sei" é honesto.

    MORDE: mapear `uinput` para qualquer nome de máscara reprova aqui. A régua
    existe porque a cura ÓBVIA do teste acima é um segundo dicionário
    `{"uhid": "DualSense", "uinput": "Xbox 360"}`, e ele estaria ERRADO — é a
    afirmação que `mascara_viva` se recusa a fazer.
    """
    assert _card(pac, a02, {**BASE, "vpad_backend": "uinput"})["mascara"] == "—"
    assert _card(pac, a02, {**BASE, "vpad_backend": None})["mascara"] == "—"


# --------------------------------------------------------------------------
# 5. O TOQUE — o terceiro estado que o `or {}` apagava
# --------------------------------------------------------------------------
def test_inputs_com_leitura_e_sem_touchpad_nao_e_sem_toque(pac, a02):
    """Ler os botões e não ler o touchpad é "não sei", não "ninguém encostou".

    O `tem_leitor` separa `inputs: None` de `inputs: {}`; faltava separar
    `inputs` COM leitura mas SEM a chave `touchpad`. Os dois são o mesmo
    travessão, pela mesma razão.

    MORDE: voltar ao `e.get("touchpad") or {}` reprova aqui com `'Sem toque'`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "inputs": {"buttons": ["cross"]}})
    assert d["touch-estado"] == mesa_viva.SEM_LEITOR


def test_o_rotulo_do_sem_toque_nao_e_digitado_aqui(a02):
    """"Sem toque" tem UM dono, e é `sensor_widgets.texto_toques`.

    A constante desta aba já dizia, em comentário, que a palavra era "a do
    produto" — e ainda assim era uma segunda cópia das mesmas cinco letras. Um
    comentário não é um dono.

    ESTA RÉGUA NASCEU CEGA E FOI CONSERTADA NA MORDIDA (02/09/2026). A primeira
    versão tinha só a segunda linha, e ela **não mordia**: redigitar
    `SEM_TOQUE = "Sem toque"` continuava passando, porque a igualdade de string
    é verdadeira nos dois mundos. Uma régua que passa com a cura arrancada não
    mede nada — foi a mordida que a pegou, e é por isso que ela é obrigatória.

    A PRIMEIRA LINHA É QUE MORDE, e é de IDENTIDADE: apagar o import e redigitar
    o literal derruba `a02.texto_toques` com `AttributeError`. E se alguém
    apagar só o USO, mantendo o import, quem pega é o `ruff` — `texto_toques`
    não tem outro uso neste arquivo, então ele vira `F401`, e o lint é portão.
    """
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques

    assert a02.texto_toques is texto_toques, (
        "a aba deixou de importar o dono da palavra e voltou a digitá-la")
    assert texto_toques(0) == a02.SEM_TOQUE


# --------------------------------------------------------------------------
# 6. A ASSERÇÃO ESTRUTURAL — e ela é de IDENTIDADE, não de texto
# --------------------------------------------------------------------------
def test_a_aba_chama_o_motor_em_vez_de_reescreve_lo(a02, motor):
    """Os nomes do motor estão LIGADOS neste módulo, e são os mesmos objetos.

    POR QUE ISTO NÃO É MEDIR TEXTO: a auditoria do selo do microfone
    (02/09/2026) mostrou o preço de conferir fonte com `inspect.getsource` —
    *"trocar `mic_sabemos` por `True` deixa o controle caído voltando a pintar
    ATIVO com a régua VERDE"*. Identidade de objeto não tem esse buraco:
    reimplementar `speaker_do_entry` dentro deste arquivo faz o `is` falhar, e
    nenhuma reescrita de comentário o afeta.

    ELA PROMETIA CINCO E TRANCAVA DOIS — auditoria de 02/09/2026. O docstring
    dizia *"reprova aqui nomeando qual"* e as asserções eram duas
    (`speaker_do_entry` e `rotulo_lightbar`); `texto_volume` e `mascara_viva`
    ficavam de fora, e são justamente as duas cujo COMPORTAMENTO um clone local
    reproduz de graça. Medido: reescrever `texto_volume` dentro do pacote e
    apagar o import passava nos 15 testes e no `ruff`.

    MORDE: copiar qualquer um dos cinco para dentro do pacote (que é
    exatamente o que a LEI 0 proíbe) reprova aqui nomeando qual.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import mascara_viva
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
        texto_toques,
        texto_volume,
    )

    donos = {
        "speaker_do_entry": motor.speaker_do_entry,
        "rotulo_lightbar": motor.rotulo_lightbar,
        "texto_volume": texto_volume,
        "texto_toques": texto_toques,
        "mascara_viva": mascara_viva,
    }
    reescritos = [
        nome for nome, dono in donos.items() if getattr(a02, nome, None) is not dono
    ]
    assert not reescritos, (
        f"a aba deixou de chamar o motor e reescreveu: {', '.join(reescritos)}")
