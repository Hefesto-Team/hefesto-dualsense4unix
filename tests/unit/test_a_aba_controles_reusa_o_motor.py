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
   (`ipc_handlers.py:3584`), e a aba escrevia o número CRU com um `%` colado.
   O valor vivo era 102, e a tela dizia uma porcentagem acima de cem; no talo
   ela diria "255%". E a conta certa não é `bruto / 255`: `core/speaker_scale.py`
   existe por causa da curva MEDIDA no hardware — abaixo de 38 tudo é mudo,
   acima de 102 tudo é o mesmo volume.
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
Aqui só há uma asserção estrutural, e ela é de IDENTIDADE de objeto
(`a02.speaker_do_entry is controller_card.speaker_do_entry`) — reimplementar a
função localmente quebra a identidade, e nenhuma reescrita de comentário a
afeta.
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
#: nos dois controles. É o número que fazia a tela dizer "102%".
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
    """102 no registrador é **100 %** na tela, e nunca "102%".

    O rótulo é o do produto (`sensor_widgets.texto_volume`), que passa pela
    curva medida de `core/speaker_scale.py`. Os dois lados são cobrados: o que
    a tela TEM de dizer e o que ela NÃO pode dizer.

    MORDE: devolver `f"{sp.get('volume', 0)}%"` a esta linha reprova aqui com
    `'102%' != '100 %'` — que é exatamente o que a mesa dela mostrava.
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


def test_a_barra_apagada_nao_publica_um_codigo_de_cor(pac, a02):
    """Barra apagada não tem código de cor a mostrar — o motor devolve o neutro.

    MORDE: ler o `lightbar_rgb` direto em vez do segundo valor de
    `rotulo_lightbar` reprova aqui com `'#000000'`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "sysfs", "lightbar_on": False})
    assert d["luz-hex"] == mesa_viva.SEM_LEITOR


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

    MORDE: copiar a função do motor para dentro do pacote (que é exatamente o
    que a LEI 0 proíbe) reprova aqui nomeando qual.
    """
    assert a02.speaker_do_entry is motor.speaker_do_entry
    assert a02.rotulo_lightbar is motor.rotulo_lightbar
