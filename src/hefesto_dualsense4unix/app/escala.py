"""A escala da fonte da interface: o dado e a leitura do disco, sem GTK.

Mora fora de `app.theme` porque quem a lê não é só o tema: a seção «A janela»
da configuração (`app/actions/config/secao_janela.py`) mostra os degraus, e
ela é importada pelas páginas da interface nova, que não carregam o GTK. Com a
escala dentro do tema, gerar uma página exigia o `gi` inteiro, e o CI sem GTK
reprovava dois mil testes de página por isso (27/09/2026).

O tema continua sendo o dono de APLICAR a escala (`theme.escala_fonte`,
`theme.escalar_css`); este módulo só diz quanto ela vale.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Chave da preferência (``~/.config/hefesto-dualsense4unix/gui_preferences.json``).
CHAVE_ESCALA = "escala_fonte"

#: Quanto a interface cresce, em PIXELS, por cima de cada tamanho declarado.
#: 3 é o pedido da mantenedora ("não seria interessante aumentarmos em 3 o
#: tamanho delas?"), medido e aprovado no orçamento de largura e altura depois
#: da realocação — ver `tests/unit/test_layout_orcamento_altura.py`.
ESCALA_PADRAO = 3

#: Teto de segurança. Acima disso o conteúdo passa a exigir mais largura do que
#: uma tela 1080p oferece, e a janela deixa de caber em vez de ficar legível.
ESCALA_MAXIMA = 8

#: Os três degraus que a aba Configurações oferece, e o delta de cada um.
#:
#: A escala aceita 0 a 8, mas nove degraus numa fileira de botões é uma régua,
#: não uma escolha — e a pergunta que a pessoa faz é "está pequeno demais?",
#: que tem três respostas. "Normal" é o `ESCALA_PADRAO` por definição: o degrau
#: do meio não pode divergir do padrão da casa no dia em que ele mudar.
#:
#: "Grande" é 6 e não `ESCALA_MAXIMA`: 8 é o teto de SEGURANÇA (acima dele a
#: janela deixa de caber numa tela 1080p), e um degrau colado no teto não tem
#: folga para o dia em que uma tela nova pedir mais um pixel.
DEGRAUS_DE_ESCALA: dict[str, int] = {
    "compacto": 0,
    "normal": ESCALA_PADRAO,
    "grande": 6,
}


def escala_gravada() -> int:
    """Delta de tamanho da fonte que está NO DISCO agora, sem cache.

    Valor fora da faixa (ou de tipo errado, num arquivo editado à mão) cai no
    padrão em vez de quebrar a abertura da janela — o tema NUNCA pode ser o
    motivo de a interface não abrir.

    Existe separada de `escala_fonte` por causa da aba Configurações: a fileira
    de degraus tem de nascer marcando o que VALE NA PRÓXIMA ABERTURA, e
    `escala_fonte` devolve o cache `_escala_aplicada` da sessão — depois da
    primeira leitura ela mente sobre o disco, que é justamente onde a gravação
    de agora foi parar.
    """
    bruto = load_gui_prefs().get(CHAVE_ESCALA, ESCALA_PADRAO)
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float)):
        logger.warning("theme_escala_invalida", valor=repr(bruto))
        bruto = ESCALA_PADRAO
    delta = int(bruto)
    if delta < 0 or delta > ESCALA_MAXIMA:
        logger.warning("theme_escala_fora_da_faixa", valor=delta)
        delta = max(0, min(ESCALA_MAXIMA, delta))
    return delta


def degrau_da_escala(delta: int) -> str:
    """O degrau de `DEGRAUS_DE_ESCALA` mais perto de `delta`.

    Nunca devolve "nenhum": um arquivo com `escala_fonte: 5` (alcançável
    editando o JSON à mão, e foi o único caminho até esta tela existir) tem de
    marcar um botão, senão a fileira nasce em branco e a pessoa não descobre
    qual tamanho está valendo. Empate não existe entre inteiros — os degraus
    são 0, 3 e 6, e as fronteiras caem em 1,5 e 4,5.
    """
    return min(DEGRAUS_DE_ESCALA, key=lambda nome: abs(DEGRAUS_DE_ESCALA[nome] - delta))
