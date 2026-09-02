"""A régua do despachante: quantas abas pintam, e quanto cada uma cobre.

Ela nasce do §1.3 do plano de uma hora, com estas palavras: *"sem o item 3 este
plano não vale nada — é ele que diz, a cada minuto, quanto falta, e é o que
impede um agente de dizer 'pronto' sobre uma aba que não pinta."*

O plano acabou não indo por agentes (decisão dela em 01/09: *"você mesmo vai
conectando tudo aba a aba"*), mas a régua vale igual: ela impede que EU diga
pronto sobre uma aba que não pinta.

O QUE ELA MORDE, e cada item já falhou de verdade nesta casa:

* uma aba SEM pacote passa despercebida  → a lista das dez é fixa aqui;
* um pacote que devolve `{}`             → `cobertura` é obrigatória;
* "zero achados" lido como "tudo certo"  → `pintados` e `sem_dono` são contados
  separados, e um pacote com pintados=0 e sem_dono=0 é ERRO;
* a página sem endereço para pintar      → o HTML é lido e os endereços contados.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FERR = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(FERR))

#: AS DEZ, e a lista é FIXA de propósito. Derivá-la do diretório faria a régua
#: passar por vacuidade no dia em que uma aba sumisse — e sumir calado é o
#: defeito que ela existe para pegar.
ABAS = [
    "01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
    "05-vibracao.html", "06-navegacao.html", "07-lancadores.html",
    "08-conexoes.html", "09-sistema.html", "10-perfis.html",
]

#: NENHUMA, DESDE 02/09/2026 — e a exceção que morreu fica registrada, porque
#: não se apaga decisão medida:
#:
#:   01/09 — *"a única que não faremos, só deixamos o botão levando pra ela, é
#:            a de lançadores."*
#:   02/09 — *"não daria para incluir G e F aqui? (…) temos um mapa funcional
#:            disso no gtk."*   <-- a `F` é a Lançadores
#:
#: A segunda vale, e traz a razão: `sentinela_do_wrapper`, `prontuario_dos_jogos`
#: e `steam_launch_options` já respondiam o que aquela tela pergunta. O pacote é
#: `a07_lancadores.py` e a sprint é a ROTA-F.
SEM_PACOTE: set[str] = set()

#: Os dois esquemas de endereço que convivem: `data-campo` (o meu) e `data-hef`
#: (o do outro agente, nas 77 marcações da Perfis). O nome não é o contrato.
ENDERECO = re.compile(r'data-(?:campo|hef|papel|gesto|hef-gesto|ajuste|player)="')


@pytest.fixture(scope="module")
def pacotes_mod():
    import pacotes
    return pacotes


def test_toda_aba_tem_pacote_ou_razao(pacotes_mod):
    faltam = [a for a in ABAS if a not in SEM_PACOTE and a not in pacotes_mod.PACOTES]
    assert not faltam, f"sem função de pacote: {faltam}"


def test_as_dez_tem_pacote_e_nenhuma_esta_de_fora(pacotes_mod):
    """A MORDIDA DOS DOIS LADOS, e ela mudou de lado em 02/09/2026.

    Enquanto valeu a decisão de 01/09, esta régua acusava quem ESCREVESSE um
    pacote para a Lançadores. Com a de 02/09 (*"não daria para incluir G e F
    aqui?"*), ela passa a acusar quem o TIRAR — e uma aba que saísse da tabela
    ficaria verde por vacuidade, que é o pior estado.
    """
    tem = {a for a in ABAS if a in pacotes_mod.PACOTES}
    assert tem == set(ABAS) - SEM_PACOTE, (
        f"a lista de quem pinta mudou sem a decisão dela mudar: {sorted(tem)}")


#: UM CONTROLE DE MENTIRA, com a forma do que o daemon devolve. A régua roda com
#: ELE, e não com a mesa vazia — porque um pacote que só pinta por controle
#: devolve `pintados: 0` com a mesa vazia, e reprovaria por estar CERTO. Medido:
#: foi o que aconteceu na primeira versão desta régua.
#:
#: O MAC é da faixa sintética da casa (`aa:bb:cc`), nunca um endereço real: há
#: dois portões de anonimato nesta árvore e eles não perdoam.
FALSO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "battery_pct": 95, "transport": "usb",
    "vpad_backend": "uhid", "lightbar_rgb": [0, 0, 255], "is_primary": True,
    "inputs": {"lx": 127, "ly": 128, "rx": 127, "ry": 128, "l2_raw": 0, "r2_raw": 0,
               "buttons": []},
    "audio": {"mic_mudo": False, "mic_mudo_desejado": None},
    "speaker": {"volume": 102, "muted": False},
}


#: A MESA TEM OUTRA FORMA QUE O CONTROLE, e confundi-las derruba os pacotes que
#: delegam para a camada do produto. `mesa_viva.mesa_do_estado` devolve `pref`,
#: `jogador`, `nome`, `via`, `cor`, `uniq` e `mascara`; o item de `controllers`
#: devolve `player`, `transport`, `lightbar_rgb`… São vocabulários diferentes de
#: propósito — um é o do desenho, o outro é o do daemon.
#:
#: Medido em 01/09/2026: passar o CONTROLE como mesa dava `KeyError: 'jogador'`
#: dentro de `app/telas/vibracao.py`, e só na suíte completa — porque isolado o
#: pacote ainda não delegava.
MESA = [{"pref": "p1", "jogador": 1, "uniq": "aa:bb:cc:00:00:01",
         "nome": "Régua", "via": "USB", "cor": "starlight-blue",
         "mascara": "DualSense", "alvo": True}]


def test_todo_pacote_declara_cobertura(pacotes_mod):
    ctx = pacotes_mod.Contexto(state={"active_profile": "x", "rumble_policy": "balanceado"},
                               mesa=MESA, conectados=[FALSO], estados={})
    for aba in ABAS:
        if aba in SEM_PACOTE:
            assert pacotes_mod.pacote_da_pagina(aba, ctx) is None
            continue
        p = pacotes_mod.pacote_da_pagina(aba, ctx)
        assert isinstance(p, dict), f"{aba}: pacote não é dicionário"
        assert "cobertura" in p, f"{aba}: pacote sem `cobertura` — é ela que diz quanto falta"
        c = p["cobertura"]
        assert {"pintados", "sem_dono"} <= set(c), f"{aba}: cobertura incompleta"
        # ZERO E ZERO É ERRO, nunca silêncio: um pacote que não pinta nada e não
        # declara nada sem dono não está honesto — está vazio.
        assert c["pintados"] or c["sem_dono"], (
            f"{aba}: pinta 0 e declara 0 sem dono — pacote vazio passando por pronto")


@pytest.mark.parametrize("aba", [a for a in ABAS if a not in SEM_PACOTE])
def test_a_pagina_tem_onde_pintar(aba):
    """Um pacote sem endereço na página pinta no vazio.

    Foi o buraco que a medição de 01/09 achou e que o plano de uma hora não
    tinha: **72 endereços para 172 valores vivos**, com CINCO abas em zero.
    """
    html = (RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / aba)  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)
    assert html.exists(), f"{aba} não existe no produto"
    n = len(ENDERECO.findall(html.read_text(encoding="utf-8")))
    assert n > 0, f"{aba}: nenhum endereço de pintura — o pacote dela pintaria no vazio"
