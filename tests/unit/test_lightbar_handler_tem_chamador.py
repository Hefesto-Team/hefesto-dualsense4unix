"""L10 — todo handler desta aba tem de ter um chamador de PRODUÇÃO.

**A forma que faltava em todos os portões desta casa é esta pergunta:** *existe
chamador de PRODUÇÃO?* Um método que ninguém chama não é código morto inofensivo
— é código que ninguém exercita, que ninguém atualiza junto com o resto, e que
volta a ser chamado um dia por engano trazendo o comportamento de meses atrás.

**O caso que a criou (M9 da sprint LIGHTBAR-COR-DE-CADA-UM-01).**
``on_player_led_toggled`` está no dicionário de sinais de ``app.py`` e não tem
mais quem o dispare: os ``<signal name="toggled">`` **saíram do glade** na
BOTÃO-QUE-NÃO-MENTE-01, e o próprio XML registra a medição — a caixa é
``visible=False``/``no-show-all``, ninguém clica, e os dois lugares que chamam
``set_active`` já se protegem por guard.

**O escopo é DECLARADO e é pequeno de propósito:** os handlers ``on_*`` do
``lightbar_actions.py``, cruzados com o dicionário de sinais do ``app.py``. Um
portão que nasce global nasce ignorado — este cabe numa aba, e a aba tem dono.
Quem quiser o mesmo para as outras dez copia trinta linhas.

**O que conta como chamador de produção**, em três formas, todas medidas no
disco e nenhuma escrita à mão numa lista:

1. um ``<signal ... handler="X">`` no ``main.glade``;
2. um ``.connect(..., self.X)`` em qualquer arquivo de ``app/``;
3. uma chamada ``self.X(...)`` em qualquer arquivo de ``app/``.

Teste NÃO conta, e é o ponto inteiro: o defeito é justamente o método que só a
suíte exercita.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"
LIGHTBAR = APP / "actions" / "lightbar_actions.py"
APP_PY = APP / "app.py"
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"

#: A DÍVIDA DECLARADA — handlers sem chamador que ainda não puderam sair, com o
#: motivo e o que os desbloqueia. Não é lista de exceções permanentes: o teste
#: de baixo reprova se um nome daqui GANHAR chamador (ou sumir), então a lista
#: não tem como apodrecer em silêncio.
#:
#: `on_player_led_toggled` (25/08/2026, agente A4 da leva das onze abas): as 27
#: linhas do método saem junto com a linha `"on_player_led_toggled":
#: self.on_player_led_toggled` de `app/app.py` — remover só o método faria a
#: janela morrer no boot com `AttributeError`. Nesta leva o `app.py` é da frente
#: A2 (Status) e agente nenhum edita arquivo de outro; a remoção é uma costura
#: de dois arquivos, e está nomeada no relatório de A4.
#:
#: As CAIXAS `player_led_1..5` ficam de qualquer forma, e isso é medição, não
#: esquecimento: `get_current_player_leds` as lê por id, e `builder.get_object`
#: de um id inexistente devolve `None` — sumir com elas faria "Aplicar o
#: desenho" apagar as cinco luzes e gravar "tudo apagado" no perfil dela.
DIVIDA_DECLARADA: dict[str, str] = {
    "on_player_led_toggled": (
        "L10 — sai junto com a entrada de app/app.py, que é de outra frente "
        "nesta leva"
    ),
}


def _handlers_da_aba() -> set[str]:
    """Os métodos ``on_*`` definidos no mixin da Lightbar."""
    arvore = ast.parse(LIGHTBAR.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == "LightbarActionsMixin":
            for corpo in no.body:
                if isinstance(
                    corpo, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and corpo.name.startswith("on_"):
                    nomes.add(corpo.name)
    assert nomes, "o mixin da Lightbar não tem handler nenhum — a régua ficou cega"
    return nomes


def _registrados_no_dicionario_de_sinais() -> set[str]:
    """As chaves do ``_signal_handlers()`` do ``app.py``."""
    fonte = APP_PY.read_text(encoding="utf-8")
    chaves = set(re.findall(r'"(on_[a-z0-9_]+)":\s*self\.\1', fonte))
    assert chaves, "o dicionário de sinais do app.py sumiu — a régua ficou cega"
    return chaves


def _handlers_com_sinal_no_glade() -> set[str]:
    arvore = ET.parse(str(GLADE))
    return {
        sinal.get("handler") or "" for sinal in arvore.iter("signal")
    } - {""}


def _handlers_chamados_em_producao() -> set[str]:
    """``.connect(..., self.X)`` ou ``self.X(...)`` em qualquer arquivo de ``app/``."""
    achados: set[str] = set()
    for arquivo in APP.rglob("*.py"):
        fonte = arquivo.read_text(encoding="utf-8")
        achados.update(re.findall(r"\bself\.(on_[a-z0-9_]+)\s*\(", fonte))
        achados.update(
            re.findall(r"\.connect\(\s*[^)]*?self\.(on_[a-z0-9_]+)", fonte)
        )
    return achados


def _orfaos() -> dict[str, str]:
    """``{handler: por que ele é órfão}`` — os que nada dispara em produção."""
    da_aba = _handlers_da_aba()
    registrados = _registrados_no_dicionario_de_sinais()
    no_glade = _handlers_com_sinal_no_glade()
    chamados = _handlers_chamados_em_producao()
    orfaos: dict[str, str] = {}
    for nome in sorted(da_aba & registrados):
        if nome in no_glade or nome in chamados:
            continue
        orfaos[nome] = (
            "está no dicionário de sinais de app.py, não tem <signal> no "
            "main.glade e ninguém o chama em app/"
        )
    return orfaos


def test_nenhum_handler_da_lightbar_ficou_sem_chamador() -> None:
    """A MORDIDA do L10: tire ``on_player_led_toggled`` da dívida declarada.

    Sem a entrada na dívida, este teste reprova NOMEANDO o handler morto — que
    é a prova de que a régua o enxerga. Com a costura feita (o método fora do
    ``lightbar_actions.py`` e a linha fora do ``app.py``) a dívida some e o
    teste continua verde por mérito, não por exceção.
    """
    orfaos = {k: v for k, v in _orfaos().items() if k not in DIVIDA_DECLARADA}
    assert not orfaos, (
        "handler(es) de produção sem quem os dispare na aba Lightbar: "
        + "; ".join(f"{nome} ({motivo})" for nome, motivo in orfaos.items())
        + ". Ou ligue o handler a um gesto real, ou remova-o junto com a "
        "entrada dele no dicionário de sinais de app/app.py."
    )


def test_a_divida_declarada_nao_apodrece() -> None:
    """A lista de exceções tem de continuar sendo verdade.

    Um nome que ganhou chamador (ou que já saiu do código) não é dívida: é
    entrada velha, e entrada velha transforma o portão em carimbo — ele passa a
    perdoar um handler que já não precisa de perdão, e no dia seguinte alguém
    acrescenta outro nome à sombra dele.
    """
    orfaos = _orfaos()
    da_aba = _handlers_da_aba()
    for nome in DIVIDA_DECLARADA:
        assert nome in da_aba, (
            f"{nome} não existe mais no mixin da Lightbar — tire-o da "
            "DIVIDA_DECLARADA, a dívida foi paga"
        )
        assert nome in orfaos, (
            f"{nome} ganhou chamador de produção — tire-o da DIVIDA_DECLARADA, "
            "ele deixou de ser dívida"
        )


def test_os_seis_botoes_de_desenho_continuam_fiados() -> None:
    """A recíproca da régua: o que a tela dispara TEM de existir no Python.

    Um ``<signal handler="X">`` apontando para método que não existe só aparece
    quando alguém clica — em produção, na mão dela. Aqui aparece agora.
    """
    da_aba = _handlers_da_aba()
    fonte_glade = GLADE.read_text(encoding="utf-8")
    inicio = fonte_glade.index('id="tab_lightbar_box"')
    fim = fonte_glade.index('id="tab_rumble_box"')
    handlers_da_aba_no_xml = set(
        re.findall(r'<signal\s+name="[^"]+"\s+handler="([^"]+)"', fonte_glade[inicio:fim])
    )
    assert handlers_da_aba_no_xml, "a aba Lightbar não declara sinal nenhum?"
    faltando = sorted(handlers_da_aba_no_xml - da_aba)
    assert not faltando, (
        "o glade da aba Lightbar dispara handler que o Python não define: "
        f"{faltando}"
    )


if __name__ == "__main__":  # pragma: no cover - conveniência de bancada
    pytest.main([__file__])
