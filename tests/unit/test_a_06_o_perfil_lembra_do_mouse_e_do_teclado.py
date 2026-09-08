"""A aba Navegação grava no PERFIL, e a tela para de prometer por-controle.

O PEDIDO DELA, 05/09/2026: *"ao pular e sair configurando de aba em aba o perfil
vai se lembrando de cada config de cada aba pra cada controle. aí aplicar aplica
todas as configs naquele perfil e salvar se lembra disso quando eu for jogar o
jogo e no dia seguinte e por diante."*

O QUE FOI MEDIDO ANTES DE ESCREVER UMA LINHA, no ciclo inteiro (perfil no disco
→ ela mexe na aba 06 → Salvar do rodapé → relê o disco), em `HOME` de mentira:

    mouse.speed         11 → 11   SOBREVIVE   (o rodapé já o levava, ed91c687)
    mouse.scroll_speed   4 →  4   SOBREVIVE
    mouse.enabled     True → True SOBREVIVE
    teclado_emulado  False → True PERDIDO

**O `teclado_emulado` não tinha caminho NENHUM.** `keyboard.emulation.set` grava
na flag global da sessão (`utils/session.py:372`) e `DraftConfig.to_profile` o
emite por PASSTHROUGH do que veio do disco — então desligar o teclado e clicar
Salvar devolvia o valor VELHO, por cima da escolha dela, sem uma palavra.

E O CAMINHO DO CLIQUE NÃO EXISTIA PARA NENHUM DOS DOIS (decisão D2 do
`docs/process/2026-09-05-AS-TRES-DECISOES-DO-PERFIL-medidas-e-decididas.md`):
fechar a janela depois de arrastar a barra perdia a escolha, calada. O requisito
dela é DURABILIDADE — *"no dia seguinte e por diante"* —, não o gesto de salvar.

O QUE ESTES TESTES COBREM, cada um com a mordida escrita:

1. as duas barras e a lista do teclado GRAVAM no disco, no clique, sem Salvar;
2. o "Status do Modo" grava os DOIS lados juntos — meio perfil seria um estado
   que este botão não sabe produzir;
3. o segundo disparo do mesmo arraste (`change` + `click`) não reescreve o
   arquivo — o guarda é a IGUALDADE, não um relógio;
4. gravar NÃO reaplica o perfil: nenhum `profile.switch` sai destes gestos, e é
   o que impede um arraste de barra de desfazer o que ela mexeu em outra aba;
5. sem perfil ativo o aparelho muda e o gesto DIZ que não guardou — pelo canal
   de aviso, nunca pela recusa: o mouse ficou mesmo mais rápido;
6. a RESSALVA da D3 nasce só com mais de um controle ligado, e o desenho
   publicado tem o endereço dela VAZIO;
7. os quatro gestos estão em `hefesto_vivo.PERIGOSOS` — uma régua de clique não
   troca a velocidade do mouse dela para provar que sabe clicar.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; estes testes
escrevem perfil de verdade, com `save_profile`, dentro dele — que é a única
forma de provar que o DISCO recebeu, em vez de provar que uma função foi
chamada. Foi por medir a chamada, e não o byte, que o defeito da máscara
atravessou 04/09.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PAGINA = "06-navegacao.html"

#: Endereços da faixa SINTÉTICA da casa — há dois portões de anonimato aqui.
UM = "aa:bb:cc:00:00:01"
OUTRO = "aa:bb:cc:00:00:02"

#: O QUE O DAEMON PUBLICA no tique em que ela clica. `speed`/`scroll_speed` são
#: os do perfil semeado, para o teste medir a MUDANÇA e não o acaso.
VIVO = {"enabled": True, "speed": 3, "scroll_speed": 1}


@pytest.fixture
def a06():
    from pacotes import a06_navegacao

    return a06_navegacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


class PonteDeMentira:
    """Um dublê da ponte: guarda o que foi chamado e aceita tudo.

    O DUBLÊ NÃO PODE SER MAIS FROUXO QUE A PONTE REAL — é a cicatriz de 04/09,
    em que um dublê generoso deixou passar a máscara que nunca gravou um byte.
    Aqui `resultado` devolve o corpo do caminho FELIZ dos dois métodos que estes
    gestos chamam (`{"status": "ok"}`), que é o que o daemon responde; qualquer
    outra forma faria o gesto levantar antes de chegar ao disco.
    """

    def __init__(self, recusa: str = "") -> None:
        self.recusa = recusa
        self.chamadas: list[tuple[str, dict]] = []

    def resultado(self, metodo: str, **params):
        self.chamadas.append((metodo, params))
        if metodo == self.recusa:
            return {"status": "failed", "bloqueio": "sem_device"}
        return {"status": "ok"}

    def chamar(self, metodo: str, **params):
        self.chamadas.append((metodo, params))
        return True

    def profile_switch(self, nome: str):  # pragma: no cover - existe para ser visto
        self.chamadas.append(("profile.switch", {"nome": nome}))
        return True

    @property
    def metodos(self) -> list[str]:
        return [m for m, _ in self.chamadas]


def _semear(nome: str, *, speed: int = 3, scroll: int = 1, enabled: bool = True,
            teclado: bool | None = True, com_mouse: bool = True) -> pathlib.Path:
    """Escreve o perfil de ONTEM no lar de mentira, pelo dono do arquivo.

    Pelo `save_profile` do produto e não por um `json.dump`: o que se mede aqui
    é um round-trip disco→gesto→disco, e semear por fora deixaria a régua
    concordando com uma forma de arquivo que o produto não escreve.
    """
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        MatchAny,
        Profile,
        ProfileMouseConfig,
    )

    prof = Profile(
        name=nome,
        match=MatchAny(),
        mouse=(ProfileMouseConfig(enabled=enabled, speed=speed, scroll_speed=scroll)
               if com_mouse else None),
        teclado_emulado=teclado,
    )
    return save_profile(prof, origem="regua")


def _ctx(pac, *, perfil: str = "regua", conectados: int = 1, **estado):
    """O `ctx` de um tique, com o modo em DESKTOP — que é onde o portão abre.

    O MODO NÃO É UM CAMPO `mode`, e digitá-lo aqui daria verde sobre o portão
    errado: `mode_of_state` deriva o modo de `native_mode` e de
    `gamepad_emulation.enabled` (`app/actions/mode_transition.py:198`), e a
    ausência dos dois É o desktop. Um `{"mode": "gamepad"}` inventado passaria
    pelo portão como se fosse desktop — foi assim que a primeira versão deste
    arquivo mediu um bloqueio que não houve.
    """
    st = {
        "active_profile": perfil,
        "mouse_emulation": dict(VIVO),
        "keyboard_emulation": {"enabled": True},
    }
    st.update(estado)
    corpos = [{"uniq": u, "connected": True, "is_primary": i == 0}
              for i, u in enumerate((UM, OUTRO)[:conectados])]
    return pac.Contexto(state=st, mesa=[], conectados=corpos, estados={})


def _disco(nome: str = "regua") -> dict:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    p = load_profile(nome)
    return {
        "speed": p.mouse.speed if p.mouse else None,
        "scroll": p.mouse.scroll_speed if p.mouse else None,
        "enabled": p.mouse.enabled if p.mouse else None,
        "teclado": p.teclado_emulado,
    }


def _zerar_a_memoria(a06) -> None:
    """A memória de um clique é de MÓDULO, e viaja entre testes.

    `_PEDIDO` guarda o alvo do último clique do interruptor por 2 s
    (`MEMORIA_DE_UM_CLIQUE`). Sem zerá-la, o segundo teste que clica o "Status
    do Modo" parte do alvo do primeiro e mede o gesto errado — foi assim que
    um dublê envenenou outro arquivo por ordem de teste em 04/09.
    """
    a06._PEDIDO.clear()
    a06._largar_o_que_ela_mexeu()


# ---------------------------------------------------------------------------
# 1. AS DUAS BARRAS GRAVAM — no clique, sem ninguém clicar em "Salvar"
# ---------------------------------------------------------------------------
def test_a_barra_do_cursor_grava_no_perfil(pac, a06):
    """Ela arrasta para 11 e fecha a janela. No dia seguinte o perfil diz 11.

    A MORDIDA: tire o `_guardar_no_perfil` de `vel_cursor` e esta linha reprova
    com `3` — a velocidade de ONTEM, que é exatamente o defeito relatado.
    """
    _semear("regua", speed=3)
    a06.vel_cursor(_ctx(pac), {"valor": "11"}, PonteDeMentira())
    assert _disco()["speed"] == 11, (
        "a velocidade do cursor não chegou ao disco: ela arrastou a barra, "
        "fechou a janela, e o perfil devolveu a de ontem")


def test_a_barra_da_rolagem_grava_no_perfil(pac, a06):
    """Mesma medição do vizinho, no outro número e na outra faixa (1..5)."""
    _semear("regua", scroll=1)
    a06.vel_rolagem(_ctx(pac), {"valor": "4"}, PonteDeMentira())
    assert _disco()["scroll"] == 4


def test_a_barra_grava_o_numero_que_foi_ao_daemon_e_nao_o_do_tique(pac, a06):
    """O `ctx` é o tique ANTERIOR — gravar dali guardaria o valor velho.

    A distinção não é teórica: o estado do dublê diz `speed: 3` enquanto a barra
    manda `11`. Um `_guardar_no_perfil(ctx, mouse_speed=_rato(ctx)["speed"])`
    passaria nos dois testes acima com o disco em 3 se o perfil já estivesse em
    3 — aqui ele reprova, porque os dois números são diferentes DE PROPÓSITO.

    A MORDIDA: troque o `alvo` por `_rato(ctx).get("speed")` na chamada de
    `vel_cursor` e esta linha reprova com `3`.
    """
    _semear("regua", speed=3)
    ponte = PonteDeMentira()
    a06.vel_cursor(_ctx(pac), {"valor": "11"}, ponte)
    foi_ao_daemon = [p for m, p in ponte.chamadas if m == "mouse.emulation.set"]
    assert foi_ao_daemon and foi_ao_daemon[0].get("speed") == 11
    assert _disco()["speed"] == foi_ao_daemon[0]["speed"], (
        "o disco e o daemon receberam números diferentes — a tela mostraria um "
        "e o dia seguinte devolveria o outro")


def test_a_barra_apara_na_faixa_do_dono_antes_de_gravar(pac, a06):
    """Um `999` da barra não vira `999` no disco: o esquema o recusaria.

    `ProfileMouseConfig.speed` é `ge=1, le=12`. A aparadura já existia para o
    daemon; o que este teste fixa é que o DISCO recebe o mesmo número aparado, e
    não o cru — um `ValidationError` aqui derrubaria o gesto DEPOIS de o
    aparelho já ter mudado.
    """
    _semear("regua", speed=3)
    a06.vel_cursor(_ctx(pac), {"valor": "999"}, PonteDeMentira())
    from hefesto_dualsense4unix.integrations.uinput_mouse import MOUSE_SPEED_MAX

    assert _disco()["speed"] == MOUSE_SPEED_MAX


# ---------------------------------------------------------------------------
# 2. O TECLADO — o campo que o Salvar PERDIA
# ---------------------------------------------------------------------------
def test_a_lista_do_teclado_grava_teclado_emulado(pac, a06):
    """Ela escolhe "Desativado", e o perfil passa a dizer `False`.

    ESTE É O BURACO INTEIRO desta aba, e ele sobrevivia até ao "Salvar": o
    `to_profile` emite `teclado_emulado` por passthrough do disco, então o
    rodapé regravava o valor VELHO por cima da escolha dela.

    A MORDIDA: tire o `_guardar_no_perfil` de `teclado()` e esta linha reprova
    com `True`.
    """
    _semear("regua", teclado=True)
    a06.teclado(_ctx(pac), {"valor": a06.TECLADO_DESATIVADO}, PonteDeMentira())
    assert _disco()["teclado"] is False


def test_a_lista_do_teclado_grava_o_ligar_tambem(pac, a06):
    """A ida e a volta: "Só fora do jogo" devolve `True` ao perfil."""
    _semear("regua", teclado=False)
    a06.teclado(_ctx(pac), {"valor": a06.TECLADO_SO_FORA}, PonteDeMentira())
    assert _disco()["teclado"] is True


def test_a_opcao_sem_dono_nao_toca_no_disco(pac, a06):
    """"Só dentro do jogo" recusa dizendo — e não grava um valor inventado.

    A opção que o produto não tem não pode virar `True` nem `False` por
    conveniência. Ela recusa, e o disco fica como estava.

    A MORDIDA: faça `_ESCOLHA["dentro"] = False` e esta linha reprova.
    """
    _semear("regua", teclado=True)
    with pytest.raises(RuntimeError):
        a06.teclado(_ctx(pac), {"valor": a06.TECLADO_SO_DENTRO}, PonteDeMentira())
    assert _disco()["teclado"] is True


def test_o_teclado_recusado_pelo_daemon_nao_grava(pac, a06):
    """Recusou lá, não guarda aqui: o disco não afirma o que não aconteceu.

    A MORDIDA: mova o `_guardar_no_perfil` para ANTES do `if …failed` e esta
    linha reprova — o perfil passaria a dizer `False` sobre um teclado que
    continua ligado.
    """
    _semear("regua", teclado=True)
    ponte = PonteDeMentira(recusa="keyboard.emulation.set")
    with pytest.raises(RuntimeError):
        a06.teclado(_ctx(pac), {"valor": a06.TECLADO_DESATIVADO}, ponte)
    assert _disco()["teclado"] is True


# ---------------------------------------------------------------------------
# 3. O "STATUS DO MODO" grava os DOIS lados
# ---------------------------------------------------------------------------
def test_o_interruptor_grava_o_mouse_e_o_teclado_juntos(pac, a06):
    """Meio perfil seria um estado que este botão não sabe produzir.

    Ele desliga mouse E teclado com um clique. Gravar só o mouse deixaria o
    perfil dizendo *mouse desligado, teclado ligado* — e a próxima ativação
    imporia esse meio-passo.

    A MORDIDA: tire o `teclado_emulado=novo` da chamada e esta linha reprova.
    """
    _zerar_a_memoria(a06)
    _semear("regua", enabled=True, teclado=True)
    a06.modo(_ctx(pac), {}, PonteDeMentira())
    d = _disco()
    assert (d["enabled"], d["teclado"]) == (False, False)


def test_o_interruptor_recusado_no_teclado_nao_grava_meio_passo(pac, a06):
    """O mouse mudou e o teclado não: o gesto levanta, e o disco não guarda.

    A MORDIDA: mova a gravação para entre as duas chamadas e esta linha reprova
    — o perfil guardaria `mouse.enabled=False` com o teclado ainda ligado.
    """
    _zerar_a_memoria(a06)
    _semear("regua", enabled=True, teclado=True)
    ponte = PonteDeMentira(recusa="keyboard.emulation.set")
    with pytest.raises(RuntimeError):
        a06.modo(_ctx(pac), {}, ponte)
    d = _disco()
    assert (d["enabled"], d["teclado"]) == (True, True)


def test_o_portao_de_modo_recusa_antes_de_qualquer_escrita(pac, a06):
    """Jogando, o interruptor recusa — e o disco não é tocado.

    A MORDIDA: apague o `if modo_agora != MODE_DESKTOP` e esta linha reprova.
    """
    _zerar_a_memoria(a06)
    _semear("regua", enabled=True, teclado=True)
    ponte = PonteDeMentira()
    jogando = _ctx(pac, gamepad_emulation={"enabled": True})
    with pytest.raises(RuntimeError):
        a06.modo(jogando, {}, ponte)
    assert ponte.chamadas == []
    assert _disco()["teclado"] is True


# ---------------------------------------------------------------------------
# 4. O SEGUNDO DISPARO DO MESMO ARRASTE não reescreve o arquivo
# ---------------------------------------------------------------------------
def _quantos_backups(nome: str = "regua") -> int:
    """Quantas cópias o `save_profile` já guardou no `.historico`.

    É a CONTAGEM DE ESCRITAS medida pelo disco, e não pelo número de chamadas:
    `save_profile` faz backup a cada gravação de arquivo já existente, então uma
    escrita a mais aparece aqui mesmo que o conteúdo final seja igual.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    hist = profiles_dir() / ".historico" / nome.replace("-", "_")
    return len(list(hist.glob("*.json"))) if hist.is_dir() else 0


def test_o_click_depois_do_change_nao_grava_de_novo(pac, a06):
    """`change` e `click` chegam com o MESMO valor — e o disco recebe UMA vez.

    O guarda é a IGUALDADE e não um relógio: a segunda passagem encontra o
    perfil já dizendo `11` e `_secao_do_mouse` devolve `None`. Isso é mais forte
    que uma janela de tempo — cobre também ela arrastar a barra e voltar ao
    valor de origem.

    A MORDIDA: faça `_secao_do_mouse` devolver sempre a seção (tire o
    `if atual is not None and novo == base: return None`) e esta linha reprova
    com uma escrita a mais.
    """
    _semear("regua", speed=3)
    a06.vel_cursor(_ctx(pac), {"valor": "11"}, PonteDeMentira())
    depois_do_change = _quantos_backups()
    a06.vel_cursor(_ctx(pac), {"valor": "11"}, PonteDeMentira())
    assert _quantos_backups() == depois_do_change, (
        "o `click` que o navegador manda depois do `change` gravou uma segunda "
        "vez — cada arraste da barra dela custaria duas escritas no disco")
    assert _disco()["speed"] == 11


def test_a_secao_do_mouse_nasce_quando_o_perfil_nao_a_tinha(pac, a06):
    """Perfil sem `mouse`: a seção NASCE, e o `enabled` vem do que está valendo.

    `ProfileMouseConfig.enabled` é obrigatório, então uma seção que nasce por um
    arraste de VELOCIDADE precisa dizer alguma coisa sobre o liga/desliga — e a
    única coisa verdadeira é o estado vivo. Inventar `False` faria o perfil, na
    próxima ativação, DESLIGAR uma emulação que estava ligada.

    A MORDIDA: troque o `bool(vivo.get("enabled"))` por `False` e esta linha
    reprova.
    """
    _semear("regua", com_mouse=False)
    a06.vel_cursor(_ctx(pac), {"valor": "9"}, PonteDeMentira())
    d = _disco()
    assert (d["speed"], d["enabled"]) == (9, VIVO["enabled"])


def test_sem_o_bloco_do_daemon_a_secao_nao_nasce_chutada(pac, a06):
    """Daemon mudo e perfil sem `mouse`: nada nasce, em vez de nascer inventado.

    Um `enabled` chutado aqui valeria para todo jogo que casasse com este
    perfil, para sempre.

    A MORDIDA: apague o `if vivo.get("speed") is None: return None` e esta linha
    reprova — a seção nasceria com o liga/desliga que ninguém mediu.
    """
    _semear("regua", com_mouse=False)
    a06.vel_cursor(_ctx(pac, mouse_emulation={}), {"valor": "9"}, PonteDeMentira())
    assert _disco()["speed"] is None


# ---------------------------------------------------------------------------
# 5. GRAVAR NÃO REAPLICA — e é o que protege as outras abas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("gesto,carga", [
    ("vel-cursor", {"valor": "11"}),
    ("vel-rolagem", {"valor": "4"}),
])
def test_a_barra_nao_manda_o_daemon_reaplicar_o_perfil(pac, a06, gesto, carga):
    """Nenhum `profile.switch` sai daqui, e o preço de mandar está medido.

    `perfil.gravar_e_reaplicar` termina em `profile_switch`, que reaplica o
    perfil INTEIRO — e a barra de luz que ela DESLIGOU acende de novo (medido em
    03/09 no `a03_gatilhos`, repetido em 04/09 no trilho de brilho da 04). Numa
    BARRA seria pior: cada passo do arraste desfaria o que ela mexeu nas outras
    abas e ainda não salvou.

    A MORDIDA: troque o `loader.save_profile` de `_guardar_no_perfil` por
    `perfil.gravar_e_reaplicar` e esta linha reprova nomeando o `profile.switch`.
    """
    _semear("regua")
    ponte = PonteDeMentira()
    pac.gesto_da_pagina(PAGINA, gesto)(_ctx(pac), carga, ponte)
    assert "profile.switch" not in ponte.metodos, (
        f"o gesto `{gesto}` mandou o daemon reaplicar o perfil inteiro — um "
        f"arraste de barra desfaria a cor que ela acabou de escolher na aba 04")


# ---------------------------------------------------------------------------
# 6. SEM PERFIL ATIVO: o aparelho muda, e o gesto DIZ que não guardou
# ---------------------------------------------------------------------------
def test_sem_perfil_ativo_o_gesto_avisa_em_vez_de_recusar(pac, a06):
    """O canal é o de AVISO, nunca o da recusa — o mouse mudou de verdade.

    Um `RuntimeError` pintaria o cartão laranja de *"não deu"* sobre um cursor
    que acabou de ficar mais rápido. O `{"recado": …}` deposita no mesmo cartão
    com tom de sucesso e diz a metade que faltou.

    A MORDIDA: troque o `return {"recado": …}` por um `raise RuntimeError` e esta
    linha reprova.
    """
    ponte = PonteDeMentira()
    volta = a06.vel_cursor(_ctx(pac, active_profile=""), {"valor": "11"}, ponte)
    assert "mouse.emulation.set" in ponte.metodos, (
        "o gesto nem chegou ao daemon — sem perfil ativo o ajuste ainda tem de "
        "valer AGORA; o que falta é a memória para amanhã")
    assert isinstance(volta, dict) and "perfil ativo" in volta.get("recado", "")


def test_com_perfil_ativo_o_gesto_nao_tem_nada_a_dizer(pac, a06):
    """Caminho feliz: gravou, e o cartão fica com a frase padrão do piloto.

    Um `recado` aqui faria toda barra arrastada abrir um cartão — e ela arrasta
    a barra dezenas de vezes seguidas.
    """
    _semear("regua", speed=3)
    assert a06.vel_cursor(_ctx(pac), {"valor": "11"}, PonteDeMentira()) is None


# ---------------------------------------------------------------------------
# 7. A RESSALVA DA D3 — a tela para de prometer por-controle
# ---------------------------------------------------------------------------
def test_a_ressalva_nasce_com_dois_controles_e_cala_com_um(pac, a06):
    """*"Linha fixa só quando HÁ ressalva."* (D-02)

    Com UM controle ligado o ajuste global É o ajuste daquele controle: não há
    promessa quebrada, e a linha ocuparia a tela para dizer uma verdade sem
    consequência. Com DOIS, a fileira de cartões em cima oferece uma escolha que
    as sete linhas de baixo não honram.

    A MORDIDA: troque o `len(ctx.conectados) > 1` por `True` e a primeira linha
    reprova; troque por `False` e a segunda.
    """
    assert a06._a_ressalva_dos_globais(_ctx(pac, conectados=1)) == a06.NADA_A_DIZER
    com_dois = a06._a_ressalva_dos_globais(_ctx(pac, conectados=2))
    assert "todos os controles ligados" in com_dois


def test_a_ressalva_sai_no_pacote_em_todo_tique(pac, a06):
    """A chave é emitida sempre, cheia ou vazia.

    Chave AUSENTE deixaria a frase na tela depois de o segundo controle sair, e
    a linha passaria a ressalvar uma escolha que não existe mais — é a mesma
    razão pela qual `monta.ressalva` tem o marcador `.nada`.

    A MORDIDA: ponha a emissão sob um `if` e esta linha reprova.
    """
    for quantos in (1, 2):
        mesa = a06.pacote(_ctx(pac, conectados=quantos))["mesa"]
        assert a06.ENDERECO_DA_RESSALVA in mesa


def test_a_ressalva_nao_usa_a_palavra_que_ela_baniu(a06):
    """*"não é pra ter mesa em nada da interface"* — ordem dela, 05/09/2026.

    A palavra tinha dois sentidos na mesma tela, e o que saiu foi o de *conjunto
    de controles ligados* — que é exatamente o sentido de que esta frase
    precisa. Ela diz "todos os controles ligados", como as outras oito frases
    reescritas naquele corte.
    """
    assert "mesa" not in a06.RESSALVA_DOS_GLOBAIS.lower()


def test_a_pagina_publicada_tem_o_endereco_da_ressalva_e_ele_nasce_vazio(a06):
    """O desenho dá o LUGAR; quem escreve a frase é o pacote, ao vivo.

    Uma ressalva cravada no HTML afirmaria também na tela de quem tem um
    controle só — *"ressalva congelada é a que já mentiu na aba 08"*.

    A FORMA MUDOU EM 07/09/2026, e a razão é dela, olhando a aba com os quatro
    controles na mesa: *"navegacao tem essas 3 frases aqui na parte de baixo que
    quebram o layout"*. A ressalva era uma delas — uma `<div class="ressalva">`
    logo abaixo da grade das sete linhas. Ela virou `<span class="viva">` dentro
    do `?` dos três campos de que fala, e o que esta régua cobra não mudou: o
    endereço existe, o alvo é `html` e ele NASCE VAZIO.

    A MORDIDA: passe o texto da ressalva para dentro do `ajuda()` do `aba06.py`,
    regere a página e esta linha reprova — o `<i class="nada"></i>` some.
    """
    import onde

    doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    alvo = (f'<span class="viva" data-campo="{a06.ENDERECO_DA_RESSALVA}"'
            f' data-hef-alvo="html"><i class="nada"></i></span>')
    assert alvo in doc, (
        "a página publicada não tem o lugar da ressalva da D3 vazio — sem ele a "
        "aba promete por-controle e entrega global")


def test_a_ressalva_esta_no_ponto_de_interrogacao_dos_tres_campos(a06):
    """Nos `?` dos três campos que ela NOMEIA, e em nenhum outro lugar.

    A frase diz *"O cursor, a rolagem e o teclado são um só para o computador
    inteiro"*, e os três campos são "Velocidade de cursor", "Velocidade da
    rolagem" e "Função do teclado". Ela nunca valeu para as sete linhas do
    painel: "Navegação Interna" é por controle e "Modo Steam" já diz na própria
    dica que vale para a máquina.

    TRÊS, E NÃO CINCO. As dicas das duas velocidades são COMPARTILHADAS com a
    pop-up "Estilo Point-and-click", cujos dois botões de passo são a velocidade
    do ESTILO e não escrevem em lugar nenhum. Pendurar a ressalva na dica
    compartilhada leva a frase para uma tela onde ela é falsa — foi o defeito da
    primeira volta desta frente, e é o que este número trava.

    A MORDIDA: troque `D_VEL_ESTILO` por `D_VEL` no `TELA_PONTO` do `aba06.py`,
    regere e esta linha reprova com 4.
    """
    import onde

    doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    alvo = (f'<span class="viva" data-campo="{a06.ENDERECO_DA_RESSALVA}"'
            f' data-hef-alvo="html">')
    assert doc.count(alvo) == 3, (
        f"a ressalva da D3 aparece em {doc.count(alvo)} dicas e devia aparecer "
        "em 3 — as de 'Velocidade de cursor', 'Velocidade da rolagem' e "
        "'Função do teclado'")


def test_a_ressalva_nao_ocupa_mais_linha_no_pe_do_painel(a06):
    """Ela saiu do pé — e nenhuma `.ressalva` solta voltou para lá.

    O QUE FOI MEDIDO em 07/09/2026, na página publicada, com as três frases
    pintadas: o quadro "As opções de ativação" ia de **215px a 300,25px**, o
    miolo passava **66px** da janela e a fileira dos quatro botões terminava
    **41,25px FORA** dela — cortada pelo rodapé, como na foto dela.

    A MORDIDA: devolva o `monta.ressalva` ao `MIOLO` do `aba06.py`, regere e
    esta linha reprova.
    """
    import onde

    doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    painel = doc.split("As opções de ativação", 1)[-1].split('class="tela-nova"', 1)[0]
    assert 'class="ressalva"' not in painel, (
        "voltou uma linha de ressalva solta ao pé do painel das opções de "
        "ativação — é uma das três frases que ela mandou tirar em 07/09")


# ---------------------------------------------------------------------------
# 8. OS QUATRO GESTOS ESTÃO PROTEGIDOS
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", ["vel-cursor", "vel-rolagem", "teclado", "modo"])
def test_o_gesto_que_grava_esta_em_perigosos(nome):
    """A régua de clique não troca a velocidade do mouse dela para se provar.

    A lista ficou para trás de uma cura CINCO vezes até 04/09, e a regra que
    sobrou é a que este teste cobra: *quem ensinar um gesto a escrever no disco
    acrescenta a linha lá NO MESMO COMMIT*.

    O irmão exaustivo é `test_todo_gesto_que_grava_esta_protegido`, que lê a
    ÁRVORE de todo gesto registrado. Este nomeia os quatro desta frente — para
    a mensagem dizer QUAL saiu, em vez de dizer que a contagem mudou.
    """
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    assert (PAGINA, nome) in PERIGOSOS


# ---------------------------------------------------------------------------
# 9. O ARQUIVO QUE SAI É O QUE O ESQUEMA LÊ
# ---------------------------------------------------------------------------
def test_o_json_no_disco_tem_as_chaves_do_esquema(pac, a06):
    """Ida e volta pelo JSON, não pelo objeto em memória.

    Provar com `load_profile` já é um round-trip; olhar o JSON cru fecha a
    outra ponta — `save_profile` OMITE chave `None` por compatibilidade, e uma
    seção que saísse com nome trocado passaria calada por um `getattr`.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    _semear("regua", speed=3, teclado=True)
    a06.vel_cursor(_ctx(pac), {"valor": "11"}, PonteDeMentira())
    a06.teclado(_ctx(pac), {"valor": a06.TECLADO_DESATIVADO}, PonteDeMentira())
    cru = json.loads((profiles_dir() / "regua.json").read_text(encoding="utf-8"))
    assert cru["mouse"]["speed"] == 11
    assert cru["teclado_emulado"] is False
