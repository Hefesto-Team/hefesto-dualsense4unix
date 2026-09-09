"""QUEM-E-QUEM-03 (29/08/2026) — as nove features têm dono, e a conta sai da mão.

O DEFEITO, NUMA FRASE
----------------------
A conta das features por controle está escrita **à mão** dentro do código, no
comentário logo acima dos campos de ``ControllerOverrides``
(``profiles/schema.py``), e nada obriga esse número a acompanhar a lista de
campos abaixo dele. No dia em que alguém acrescentar um campo sem mexer no
comentário, a tabela em que a próxima pessoa vai confiar vira ficção.

**E ISSO JÁ ACONTECEU DUAS VEZES, entre o enunciado desta sprint e a execução
dela.** O comentário dizia ``QUATRO`` em 29/08; o ``mic`` entrou em 03/09
(MIC-QUINTO-AJUSTE-01) e o ``sensores`` em 04/09 (SENSOR-DE-VERDADE-01). As
duas vezes a conta foi corrigida **à mão**, e as duas vezes ela podia não ter
sido. Este arquivo é o que faz a conta parar de depender de alguém lembrar.

O QUE ESTE PORTÃO É, E O QUE ELE NÃO É
---------------------------------------
Ele é o **CENSO**: as NOVE features que a tela oferece por controle, e, para
cada uma, onde ela mora hoje (por controle · global · ausente), o que
``None`` significa, quem responde no lugar, e **a sprint dona da entrega**. Ele
compara o censo com ``ControllerOverrides.model_fields`` nos DOIS sentidos.

Ele **não** é o irmão ``test_perfil_por_controle_o_campo_espera_o_caminho``,
que pergunta outra coisa: *quem LÊ este campo por peça*. Aquele é o eixo
campo → consumidor; este é o eixo feature-da-tela → endereço no perfil → dono.
Um campo pode ter consumidor e mesmo assim sumir do censo; foi por um buraco
desse tamanho que a lista de portões virou duas (``portoes.sh``, 25/08).

**Nenhuma linha de produto.** A ``posse`` desta sprint é só este arquivo:
``profiles/schema.py`` é disputado por treze sprints, e o censo não precisa de
uma linha dele. Quem acrescentar o sétimo campo passa por aqui — agora com um
vermelho apontando o caminho, em vez do silêncio.

A LINHA SEM DONO, e ela fica sem dono de propósito
---------------------------------------------------
Oito das nove têm dono. O **touchpad** não tem, e não é esquecimento: nenhuma
tela aprovada oferece interruptor para ele (na aba Controles ele é leitura
viva, e as 27 menções da página são glifo e moldura, nenhuma é interruptor), e
o mapa de canais fecha o outro lado — ``toque.touchpad.escrita`` tem
``existe=nao-tem``: **o aparelho não tem por onde receber uma escrita de
touchpad**. Inventar o campo aqui seria feature nova.

Por isso o censo tem NOVE linhas e a nona diz ``dono=None`` com o motivo. Uma
tabela que some quando ninguém olha é o esquecimento que este arquivo existe
para impedir — então feature sem dono **passa** e é impressa. Ausência de dono
é fato do projeto, não defeito do código; o portão a torna visível, não ilegal.

**A PERGUNTA QUE VAI À MESA DELA**, e está escrita aqui para ter endereço: o
touchpad de cada controle guarda alguma coisa no perfil do jogo — ligado /
desligado, ou sensibilidade —, ou é **só leitura** e o perfil não tem nada a
lembrar dele?

UNIVERSAL POR CONSTRUÇÃO
-------------------------
Nenhum MAC, nenhum aparelho, nenhum arquivo dela: o portão lê a definição dos
modelos e a fonte do próprio módulo, e um modelo é o mesmo em qualquer bancada
do mundo. O ``uniq`` sintético do teste da parcialidade vem da faixa da casa.

MORDIDAS (o que arrancar para ver reprovar)
--------------------------------------------
1. acrescente um campo a ``ControllerOverrides`` sem tocar no censo — reprova
   nomeando o campo, **e** o teste da conta reprova dizendo SEIS contra SETE;
2. remova ``speaker`` do censo — reprova no outro sentido;
3. apague a frase de ``sem_opiniao`` de um campo presente — reprova;
4. troque a prova da parcialidade por um ``model_dump()`` denso — os campos não
   escritos aparecem, que é em letra a regressão R-20 de 23/07;
5. dê um dono falso ao touchpad, ou apague a linha dele — reprova pelas duas
   pontas (a contagem de nove, e a identidade da única sem dono);
6. troque ``SEIS`` por ``CINCO`` no comentário de ``schema.py`` — reprova.
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass

import pytest

from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    ControllerSensoresOverride,
    LedsConfig,
    Profile,
)

# ---------------------------------------------------------------------------
# O CENSO — nove linhas, e a nona é a que não pode sumir
# ---------------------------------------------------------------------------

#: Onde a feature mora HOJE. Não é opinião sobre onde ela deveria morar.
NIVEIS = ("por-controle", "global", "ausente")


@dataclass(frozen=True)
class LinhaDoCenso:
    """Uma das nove features que a tela oferece por controle."""

    #: o nome na língua da casa (docs/A-LINGUA-DESTA-CASA...), não o do código.
    feature: str
    #: `por-controle` · `global` · `ausente` — onde ela mora no perfil hoje.
    nivel: str
    #: o campo de `ControllerOverrides` que a carrega, ou `None` se não há.
    campo: str | None
    #: quando duas features dividem um campo, o campo de dentro. Senão `None`.
    subcampo: str | None
    #: o que `None` significa NESTE campo. Vazio só é aceito em `ausente`.
    sem_opiniao: str
    #: quem responde no lugar quando esta peça não opinou.
    quem_responde: str
    #: a sprint que entregou (ou entrega) o caminho. `None` = ninguém, e é fato.
    dono: str | None
    #: a chave de `docs/data/mapa-controles.csv` que descreve o canal.
    chave_do_mapa: str
    #: para o que está fora do perfil: onde mora, e por que mora lá.
    mora_em: str


#: NOVE LINHAS, SEMPRE NOVE. A tela oferece nove ajustes por controle; o perfil
#: carrega SETE deles desde 08/09/2026 — a `mascara` entrou com a decisão dela
#: (MASCARA-NO-PERFIL-01: *"pode entrar sim"*), e a linha dela deixou de dizer
#: *"NÃO no perfil, por medição"*. As duas restantes estão declaradas onde
#: estão, com a razão medida — que é o que impede a tabela de virar ficção
#: quando alguém olhar daqui a um mês.
CENSO: tuple[LinhaDoCenso, ...] = (
    LinhaDoCenso(
        feature="barra de luz",
        nivel="por-controle",
        campo="leds",
        subcampo=None,
        sem_opiniao="esta peça não escolheu cor nem brilho",
        quem_responde=(
            "a seção global `Profile.leds`, e abaixo dela a cor automática do "
            "slot (`led_control.player_slot_color`)"
        ),
        dono="PERFIL-02",
        chave_do_mapa="luz.barra",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="gatilho",
        nivel="por-controle",
        campo="triggers",
        subcampo=None,
        sem_opiniao="esta peça não escolheu efeito para L2/R2",
        quem_responde="a seção global `Profile.triggers`",
        dono="PERFIL-02",
        chave_do_mapa="gatilho.adaptativo",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="vibração",
        nivel="por-controle",
        campo="rumble",
        subcampo=None,
        sem_opiniao="esta peça não tem escala própria de força",
        quem_responde="a seção global `Profile.rumble`",
        dono="POR-UNIDADE-01",
        chave_do_mapa="vibracao.rumble.esquerdo",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="alto-falante",
        nivel="por-controle",
        campo="speaker",
        subcampo=None,
        sem_opiniao="esta peça não tem volume nem rota próprios",
        quem_responde=(
            "a seção global `Profile.speaker`; e perfil SEM a seção não escreve "
            "NADA — escrever tomaria a posse dos bytes de volume"
        ),
        dono="POR-UNIDADE-01",
        chave_do_mapa="audio.alto_falante.volume",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="microfone",
        nivel="por-controle",
        campo="mic",
        subcampo=None,
        sem_opiniao="esta peça não opina sobre o mudo",
        quem_responde=(
            "a seção global `Profile.mic`, e abaixo dela a máquina "
            "(`ControleDeclarado.microfone`, em `utils/maquina.py`)"
        ),
        dono="MIC-QUINTO-AJUSTE-01",
        chave_do_mapa="audio.microfone.mudo",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="giroscópio",
        nivel="por-controle",
        campo="sensores",
        subcampo="giroscopio",
        sem_opiniao="esta peça não opina, e sem opinião é LIGADO",
        quem_responde=(
            "`D-AUDIO-E-GIRO-NASCEM-LIGADOS` (25/08/2026): o giroscópio nasce "
            "ligado em todo jogo — um perfil que não pediu nada não desliga o "
            "sensor dela por omissão"
        ),
        dono="SENSOR-DE-VERDADE-01",
        chave_do_mapa="movimento.giroscopio",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="acelerômetro",
        nivel="por-controle",
        campo="sensores",
        subcampo="acelerometro",
        sem_opiniao="esta peça não opina, e sem opinião é LIGADO",
        quem_responde=(
            "o mesmo default do irmão acima, e independente dele de propósito — "
            'é o *"ambos"* dela, cada um por si'
        ),
        dono="SENSOR-DE-VERDADE-01",
        chave_do_mapa="movimento.acelerometro",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="o controle é visto como",
        nivel="por-controle",
        campo="mascara",
        subcampo=None,
        sem_opiniao="esta peça não escolheu como aparecer nos jogos",
        quem_responde=(
            "o `mode.gamepad_flavor` do perfil e, sem ele, o padrão do daemon "
            "— a mesma herança de sempre, agora com o perfil como dono"
        ),
        dono="MASCARA-NO-PERFIL-01",
        chave_do_mapa="plataforma.vpad",
        mora_em="",
    ),
    LinhaDoCenso(
        feature="touchpad",
        nivel="ausente",
        campo=None,
        subcampo=None,
        sem_opiniao="",
        quem_responde="ninguém — não há o que herdar, porque não há campo",
        dono=None,
        chave_do_mapa="toque.touchpad.escrita",
        mora_em=(
            "lugar nenhum. Não há campo no perfil, não há tela aprovada com "
            "interruptor (na aba Controles ele é leitura viva), e o mapa fecha "
            "o outro lado: `toque.touchpad.escrita` tem `existe=nao-tem` — o "
            "aparelho não tem por onde receber escrita de touchpad. É pergunta "
            "aberta para ELA, não dívida com dono"
        ),
    ),
)

#: A feature sem dono é UMA, e é esta. Escrito à parte de propósito: se um dia
#: alguém apagar a linha do censo, a contagem reprova por nove; se alguém lhe
#: der um dono falso, esta constante reprova por identidade.
FEATURE_SEM_DONO = "touchpad"

#: Quantas a TELA oferece por controle. É o segundo número do comentário de
#: `ControllerOverrides`, e o tamanho do censo.
FEATURES_NA_TELA = 9


# ---------------------------------------------------------------------------
# AS CONTAS — funções puras, para a régua saber recusar (§4 do protocolo)
# ---------------------------------------------------------------------------


def campos_declarados_por_controle(censo: tuple[LinhaDoCenso, ...]) -> set[str]:
    """Os campos de topo que o censo diz existirem em `ControllerOverrides`."""
    return {
        linha.campo
        for linha in censo
        if linha.nivel == "por-controle" and linha.campo is not None
    }


def campos_fora_do_censo(campos: set[str], censo: tuple[LinhaDoCenso, ...]) -> list[str]:
    """Campo no modelo que o censo não conhece. Campo novo cai aqui."""
    return sorted(campos - campos_declarados_por_controle(censo))


def declarados_sem_campo(campos: set[str], censo: tuple[LinhaDoCenso, ...]) -> list[str]:
    """Censo diz `por-controle` e o modelo não tem o campo. Campo removido."""
    return sorted(campos_declarados_por_controle(censo) - campos)


def features_sem_dono(censo: tuple[LinhaDoCenso, ...]) -> list[str]:
    """As features que ninguém entregou nem prometeu entregar."""
    return sorted(linha.feature for linha in censo if linha.dono is None)


def test_a_regua_sabe_recusar() -> None:
    """As quatro contas, exercitadas com um censo sintético.

    Sem isto, um erro nas funções puras faria todos os testes abaixo passarem em
    silêncio para sempre. Régua que só sabe passar não é régua.
    """
    inventado = LinhaDoCenso(
        feature="inventada",
        nivel="por-controle",
        campo="inventado",
        subcampo=None,
        sem_opiniao="sem opinião",
        quem_responde="ninguém",
        dono=None,
        chave_do_mapa="",
        mora_em="",
    )
    sintetico = (CENSO[0], inventado)

    assert campos_declarados_por_controle(sintetico) == {"leds", "inventado"}
    # um campo real que o censo sintético não conhece:
    assert campos_fora_do_censo({"leds", "rumble"}, sintetico) == ["rumble"]
    # e um que o censo promete e o modelo não tem:
    assert declarados_sem_campo({"leds"}, sintetico) == ["inventado"]
    assert features_sem_dono(sintetico) == ["inventada"]
    # e o censo de verdade, pelo contrário, não tem campo prometido a menos:
    assert declarados_sem_campo(set(ControllerOverrides.model_fields), CENSO) == []


# ---------------------------------------------------------------------------
# 1. O CENSO BATE COM OS CAMPOS DE HOJE — nos dois sentidos
# ---------------------------------------------------------------------------


def test_o_censo_cobre_o_esquema_nos_dois_sentidos() -> None:
    """Campo fora do censo reprova; feature declarada sem campo reprova.

    MORDIDA: acrescente ``sensors: bool | None = None`` a
    ``ControllerOverrides`` sem tocar no censo — a primeira asserção o aponta
    pelo nome. É a sprint seguinte batendo no portão, que é para isso que ele
    existe.
    """
    campos = set(ControllerOverrides.model_fields)

    fora = campos_fora_do_censo(campos, CENSO)
    assert not fora, (
        f"campo(s) de ControllerOverrides fora do censo: {fora}. Uma feature "
        "por controle que não está no censo é uma feature que some quando "
        "ninguém olha — acrescente a linha em CENSO, com o que `None` "
        "significa e a sprint dona, e conserte a conta do comentário em "
        "profiles/schema.py."
    )

    faltando = declarados_sem_campo(campos, CENSO)
    assert not faltando, (
        f"o censo diz `por-controle` para campo(s) que o esquema não tem: "
        f"{faltando}. Portão de um lado só deixa passar metade dos erros."
    )


def test_o_censo_tem_nove_linhas_e_nenhuma_repetida() -> None:
    """A tela oferece nove, e o censo conta nove. Sempre nove."""
    assert len(CENSO) == FEATURES_NA_TELA, (
        f"o censo tem {len(CENSO)} linhas e a tela oferece {FEATURES_NA_TELA}. "
        "Se a tela passou a oferecer outro número, mude FEATURES_NA_TELA e o "
        "comentário de ControllerOverrides no MESMO commit."
    )
    nomes = [linha.feature for linha in CENSO]
    assert len(set(nomes)) == len(nomes), f"feature repetida no censo: {nomes}"

    for linha in CENSO:
        assert linha.nivel in NIVEIS, f"{linha.feature}: nível {linha.nivel!r} não existe"


def test_o_subcampo_declarado_existe_no_modelo_de_dentro() -> None:
    """Duas features dividem `sensores`; cada uma aponta o campo de dentro.

    MORDIDA: troque ``giroscopio`` por ``giro`` na linha do giroscópio e veja
    reprovar. Sem isto, o censo poderia declarar um subcampo que não existe e
    ninguém saberia — que é a forma exata do defeito que ele veio curar.
    """
    de_dentro = {
        "sensores": ControllerSensoresOverride,
        "mic": ControllerMicOverride,
        "leds": LedsConfig,
    }
    conferidos = 0
    for linha in CENSO:
        if linha.subcampo is None:
            continue
        assert linha.campo in de_dentro, (
            f"{linha.feature}: o censo declara o subcampo {linha.subcampo!r} "
            f"num campo ({linha.campo!r}) cujo modelo de dentro não está "
            "mapeado aqui"
        )
        modelo = de_dentro[linha.campo]
        assert linha.subcampo in modelo.model_fields, (
            f"{linha.feature}: {modelo.__name__} não tem o campo "
            f"{linha.subcampo!r} — tem {sorted(modelo.model_fields)}"
        )
        conferidos += 1
    assert conferidos == 2, (
        "esperava exatamente duas features dividindo um campo (giroscópio e "
        f"acelerômetro, dentro de `sensores`) e encontrei {conferidos}"
    )


# ---------------------------------------------------------------------------
# 2. A CONTA SAI DA MÃO — o comentário do esquema deixa de poder mentir
# ---------------------------------------------------------------------------

#: Só os numerais que a conta pode assumir. Escrito à mão de propósito: um
#: `int(...)` sobre a palavra não existe, e uma tabela curta é auditável.
_NUMERAIS = {
    "TRÊS": 3,
    "QUATRO": 4,
    "CINCO": 5,
    "SEIS": 6,
    "SETE": 7,
    "OITO": 8,
    "NOVE": 9,
    "DEZ": 10,
}

#: A forma da frase da conta. Montado por partes de propósito: uma sprint de
#: 05/09 escreveu um comentário para AVISAR sobre um padrão, CITOU o padrão
#: literalmente, e virou a primeira ocorrência que seis réguas casavam. Aqui a
#: régua ainda exige ocorrência ÚNICA, que é a outra metade da cura.
_FORMA_DA_CONTA = re.compile(
    r"#\s*SÃO\s+([^\W\d_]+),\s*e a tela oferece\s+([^\W\d_]+)",
    re.IGNORECASE,
)


def _contas_do_comentario() -> list[tuple[str, str]]:
    """As contas escritas à mão no corpo de `ControllerOverrides`.

    Lê a FONTE do módulo de produto, nunca uma cópia digitada aqui — que é a
    diferença entre uma régua e um segundo lugar onde o mesmo número mora.
    """
    fonte = inspect.getsource(ControllerOverrides)
    # Maiúsculas por conta da casa: hoje o comentário escreve `SÃO SEIS` em
    # caixa alta e `nove` em minúscula, e nenhuma das duas grafias é contrato.
    return [(a.upper(), b.upper()) for a, b in _FORMA_DA_CONTA.findall(fonte)]


def test_a_conta_escrita_no_esquema_acompanha_os_campos() -> None:
    """O comentário `SÃO <n>` bate com quantos campos a classe realmente tem.

    **É O DEFEITO QUE ABRE ESTA SPRINT.** A conta estava escrita à mão, dizia
    QUATRO em 29/08, e passou a SEIS em 04/09 — as duas correções feitas por
    alguém lembrar. A partir daqui, quem acrescentar o sétimo campo sem mexer
    no comentário leva vermelho com os dois números na mensagem.

    MORDIDA: troque ``SEIS`` por ``CINCO`` em ``profiles/schema.py`` e veja
    reprovar dizendo `o comentário diz 5 e a classe tem 6 campos`.
    """
    contas = _contas_do_comentario()
    assert len(contas) == 1, (
        f"esperava UMA conta no corpo de ControllerOverrides e achei "
        f"{len(contas)}: {contas}. Duas ocorrências tornam ambíguo qual delas é "
        "a conta — se você escreveu um comentário que CITA a forma da frase, "
        "reescreva-o sem citá-la."
    )
    palavra_campos, palavra_tela = contas[0]

    assert palavra_campos in _NUMERAIS, (
        f"o comentário diz SÃO {palavra_campos!r}, que não é um numeral que eu "
        f"saiba ler — conheço {sorted(_NUMERAIS)}"
    )
    assert palavra_tela in _NUMERAIS, (
        f"o comentário diz que a tela oferece {palavra_tela!r}, que não é um "
        f"numeral que eu saiba ler — conheço {sorted(_NUMERAIS)}"
    )

    escrito = _NUMERAIS[palavra_campos]
    real = len(ControllerOverrides.model_fields)
    assert escrito == real, (
        f"a conta do comentário de ControllerOverrides diz {escrito} e a "
        f"classe tem {real} campos ({sorted(ControllerOverrides.model_fields)}). "
        "Quem acrescentou ou tirou o campo passa por este comentário — a fila "
        "do que falta está na docstring da classe, ordenada por custo."
    )

    assert _NUMERAIS[palavra_tela] == FEATURES_NA_TELA, (
        f"o comentário diz que a tela oferece {_NUMERAIS[palavra_tela]} e o "
        f"censo tem {FEATURES_NA_TELA} linhas. Os dois números respondem à "
        "mesma pergunta e não podem divergir."
    )


# ---------------------------------------------------------------------------
# 3. "SEM OPINIÃO" É DECLARADO, NUNCA EM BRANCO
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "linha", [pytest.param(linha, id=linha.feature) for linha in CENSO]
)
def test_sem_opiniao_e_declarado_em_toda_feature_presente(linha: LinhaDoCenso) -> None:
    """Campo que existe diz o que `None` significa NELE, e quem responde.

    "Sem opinião" não é uma frase só — o que muda de campo para campo é *quem é
    a máquina* que responde no lugar. O censo obriga a escrever isso.

    MORDIDA: apague a frase de ``sem_opiniao`` de qualquer campo presente e veja
    reprovar nomeando a feature.
    """
    assert linha.quem_responde.strip(), (
        f"{linha.feature}: ninguém foi declarado para responder no lugar dela"
    )

    if linha.nivel == "ausente":
        assert not linha.sem_opiniao, (
            f"{linha.feature}: está `ausente` do perfil, então não há `None` a "
            "explicar — o que ela precisa declarar é `mora_em`"
        )
        assert linha.mora_em.strip(), (
            f"{linha.feature}: está fora do perfil e não diz ONDE mora nem por "
            "quê. Ausência sem endereço é a tabela virando ficção"
        )
        assert linha.campo is None, (
            f"{linha.feature}: declarada `ausente` mas com campo "
            f"{linha.campo!r}"
        )
        return

    assert linha.sem_opiniao.strip(), (
        f"{linha.feature}: o campo {linha.campo!r} existe e não diz o que "
        "`None` significa nele. Sem essa frase, a próxima pessoa lê 'sem "
        "opinião' como 'opinião igual ao default' — e essa confusão já custou "
        "a regressão R-20"
    )
    assert linha.campo is not None, f"{linha.feature}: nível {linha.nivel} sem campo"


# ---------------------------------------------------------------------------
# 4. A PARCIALIDADE VALE DENTRO DA SEÇÃO — a regressão R-20, em letra
# ---------------------------------------------------------------------------


def test_a_parcialidade_vale_dentro_da_secao() -> None:
    """Só o que foi escrito à mão entra; o resto herda o global.

    R-20 (auditoria de 23/07/2026): ajustar o BRILHO de um controle matava a COR
    do slot dele, porque o override materializava campos que ninguém escrevera.
    É esta a diferença entre *"sem opinião"* e *"opinião igual ao default"*.

    MORDIDA: troque `model_fields_set` por um ``model_dump()`` denso e veja os
    campos não escritos aparecerem — que é, em letra, a regressão.
    """
    override = ControllerOverrides(leds=LedsConfig(lightbar_brightness=0.5))

    # ENTRE seções: só `leds` foi escrito; as outras cinco são `None`.
    assert override.model_fields_set == {"leds"}
    for campo in ControllerOverrides.model_fields:
        if campo != "leds":
            assert getattr(override, campo) is None, (
                f"{campo} materializou sem ninguém o escrever — é o R-20 na "
                "camada de fora"
            )

    # DENTRO da seção: só `brightness` foi escrito.
    assert override.leds is not None
    assert override.leds.model_fields_set == {"lightbar_brightness"}, (
        "o override de brilho materializou outros campos de LedsConfig: "
        f"{sorted(override.leds.model_fields_set)}. É o R-20 — a cor do slot "
        "morreria junto com o ajuste do brilho"
    )

    # E a mesma parcialidade sobrevive ao disco, que é onde ela precisa valer.
    perfil = Profile.model_validate(
        {
            "name": "uma_peca_so",
            "match": {"type": "any"},
            "controllers": {"aabbcc001122": {"leds": {"lightbar_brightness": 0.5}}},
        }
    )
    guardado = perfil.controllers["aabbcc001122"]
    assert guardado.model_fields_set == {"leds"}
    assert guardado.leds is not None
    assert guardado.leds.model_fields_set == {"lightbar_brightness"}


# ---------------------------------------------------------------------------
# 5. A LINHA SEM DONO É NOMEADA, NÃO SILENCIOSA
# ---------------------------------------------------------------------------


def test_existe_exatamente_uma_feature_sem_dono_e_ela_e_o_touchpad(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Feature sem dono PASSA — e sai impressa, com o motivo.

    Ausência de dono é fato do projeto, não defeito do código: o portão a torna
    visível, não ilegal. O que ele proíbe é ela sumir em silêncio.

    MORDIDA: dê um dono falso ao touchpad e veja reprovar por contagem; apague a
    linha dele do censo e veja reprovar pelas nove.
    """
    sem_dono = features_sem_dono(CENSO)
    assert sem_dono == [FEATURE_SEM_DONO], (
        f"esperava exatamente uma feature sem dono ({FEATURE_SEM_DONO!r}) e "
        f"encontrei {sem_dono}. Se o touchpad ganhou dono, a pergunta dela foi "
        "respondida — e então FEATURE_SEM_DONO e a docstring deste arquivo "
        "mudam junto. Se apareceu OUTRA sem dono, ela precisa de linha própria "
        "no censo, com o motivo escrito"
    )

    linha = next(item for item in CENSO if item.feature == FEATURE_SEM_DONO)
    assert linha.nivel == "ausente" and linha.campo is None, (
        "o touchpad ganhou campo no perfil sem ninguém decidir por ela — "
        "inventá-lo aqui seria feature nova"
    )

    print(
        f"[censo] SEM DONO: {linha.feature} — {linha.mora_em}\n"
        "[censo] a pergunta que espera a palavra dela: o touchpad de cada "
        "controle guarda alguma coisa no perfil do jogo (ligado/desligado, ou "
        "sensibilidade), ou é só leitura?"
    )
    assert "SEM DONO" in capsys.readouterr().out


def test_as_oito_com_dono_nomeiam_a_sprint() -> None:
    """As outras oito dizem QUEM entregou, e o nome não é vazio."""
    com_dono = [linha for linha in CENSO if linha.dono is not None]
    assert len(com_dono) == FEATURES_NA_TELA - 1
    for linha in com_dono:
        assert linha.dono and linha.dono.strip(), (
            f"{linha.feature}: dono declarado em branco — ou é `None` (e é "
            "fato registrado), ou é o nome de uma sprint"
        )
