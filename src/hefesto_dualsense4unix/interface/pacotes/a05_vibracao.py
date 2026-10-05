#!/usr/bin/env python3
"""O pacote da aba `05` Vibração.

CORRIGIDO EM 01/09/2026. O que estava aqui:

    "motor-esq: o valor por motor — o daemon publica a política da mesa, não o
     motor"

Está errado, e o próprio daemon desmente: `rumble_ff.per_vpad[]` traz
`last_weak` e `last_strong` — **os dois motores, por gamepad virtual** — além de
`ff_maior_pedido: [weak, strong]`, `rumble_no_fisico` e a contagem de plays.
Medido no daemon dela, com o DualSense no cabo.

O DualSense tem DOIS motores e eles não são "esquerdo e direito" por acaso: o
`strong` é o motor pesado e o `weak` o leve — a nomenclatura vem do protocolo de
force-feedback do evdev, e é a que o produto usa de ponta a ponta. A tela fala
"esquerdo/direito" porque é onde eles ficam no plástico.

O QUE DE FATO NÃO TEM DONO: nada. O que a aba mostra é o pedido que o JOGO fez
(o que chegou ao gamepad virtual), e não a corrente que passou no motor — isso o
aparelho não devolve. É uma ressalva sobre o SIGNIFICADO do número, não sobre a
existência dele, e a tela a carrega no `title`.
"""
from __future__ import annotations

import contextlib
from time import monotonic as _monotonic
from typing import Any

# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
from hefesto_dualsense4unix.app.telas import vibracao as _tela
from hefesto_dualsense4unix.core.rumble import POLITICA_PADRAO, vale_o_padrao

from . import Contexto, registrar
from . import perfil as _perfil

#: era o ENDEREÇO no desenho mais a EMISSÃO aqui. As duas metades entraram
#: fantasma — a próxima pessoa esperaria por uma cura que já chegou.
SEM_DONO: dict[str, str] = {}

#
# **ELA DECIDIU, E FORA DAS OPÇÕES QUE EU OFERECI:**
#
#     "os slcers do botão esquerdo e direito (forte e  # (noqa-acento): dela
#      fraco) se multiplicam (interagem com os botões economia, moderado,
#      máximo, se eu tiver 150% do perfil de vibração e as duas linhas
#      estiverem 100 entao a vibração dos 2 será 150%, mas se so a do motor

# (`_aplicar_a_forca`, que leva a frase ao cartão daquele controle) e no TEMPO
# uma dela é uma linha em `FRASE_DA_MESA_EM_AUTO` e outra em


def _plastico_do_item(controle: dict[str, Any]) -> str:
    """O `#hex` da cor do plástico daquele controle, ou `""` quando não se sabe.

    O item de mesa traz o SLUG (`mesa_viva.mesa_do_estado`, campo `cor`), e o
    dono da tradução slug → cor é `monta.cor_da_zona`, que LÊ o `<style>` que o
    `gerar_cores_do_dualsense.py` escreveu no SVG. Digitar um hexadecimal aqui
    seria a segunda lista de cores que o `docs/data/cores-do-dualsense.csv`
    existe para não ter.

    VAZIO É RESPOSTA, e é a mais comum na mesa dela: pelo rádio o mapa de canais
    diz `identidade.cor_do_aparelho = não`, o `LeitorDeCor` guarda `None`, e o
    item chega com `cor = ""`. Devolver `""` faz o pintor APAGAR a variável — a
    moldura cai no tom neutro em vez de ficar com a cor do desenho.

    `cor_da_zona` LEVANTA `SystemExit` num slug que não existe, e `SystemExit`
    não é `Exception`: os dois entram no `except` de propósito. Um colorway novo
    no aparelho dela não pode derrubar a aba inteira — ele deixa a moldura sem
    cor, que é o mesmo caminho do "não sei".
    """
    slug = str(controle.get("cor") or "")
    if not slug:
        return ""
    try:
        import monta

        return str(monta.cor_da_zona(slug))
    except (Exception, SystemExit):
        return ""


def teto_da_barra() -> int:
    """O 100% da barra "Personalizado", em pontos percentuais. Hoje: **200**.

    **DECISÃO DELA, 03/09/2026:** *"0 a 200%, e grava na hora."* A barra deixou
    de ser leitura e virou um `<input type=range>` que ela arrasta
    (:func:`intensidade`), e o teto do que ela pode PEDIR é o do multiplicador
    personalizado — não o do degrau `Máximo`.

    O NÚMERO NÃO SE DIGITA, e o dono é o esquema do perfil:
    `RUMBLE_CUSTOM_MULT_MAX` = 2,0 é quem RECUSA o que passa dele, nas duas
    bordas (`RumbleConfig` e `ControllerRumbleOverride`). Escrever `200` aqui
    seria a segunda verdade, e o `150` que a aba usava até ontem já era
    exatamente isso: a segunda cópia de `RUMBLE_POLICY_MULT["max"]`.

    **NÃO É `app/telas/vibracao.teto_da_barra()`, e a diferença é o ponto.**
    Aquela função é o teto da ESCADA — o quanto o degrau mais alto pede —, e
    continua sendo o que a janela estável desenha. Esta é o teto do que se pode
    ARRASTAR. Enquanto a barra era leitura os dois coincidiam; a partir do
    momento em que ela arrasta, deixaram de coincidir, e usar o da escada faria
    a barra encher aos 150% e ficar cheia até os 200 — escondendo um quarto do
    que o produto aceita.

    O MESMO DONO ESTÁ NO GERADOR (`aba05.TETO`), e é de propósito: um lê para
    desenhar o `max` do `<input>`, o outro para calcular a largura e o `Máx`.
    Dois leitores, uma fonte.
    """
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    return round(RUMBLE_CUSTOM_MULT_MAX * 100)


def _no_teto(pct: dict[str, Any]) -> str:
    """`"1"` quando o multiplicador desta coluna bateu no teto da barra; `""` não."""
    if not pct.get("sabe"):
        return ""
    try:
        valor = int(str(pct.get("n") or "").rstrip("%"))
    except ValueError:
        return ""
    return "1" if valor >= teto_da_barra() else ""


def _chave_no_perfil(uniq: str) -> str:
    """O `uniq` na grafia com que o PERFIL o guarda — doze hexa, ou `""`."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(str(uniq or "").strip()) or ""


def degrau_da_faixa(policy: str, custom: Any) -> str:
    """O degrau que acende pelo valor do trilho da Força: o MAIOR que o valor alcança.

    A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01 (a resposta [26]
    dela, 29/09/2026): *«qualquer valor acima disso é Máximo o botão ativo mas
    o valor real é o do slicer»*. <!-- noqa-acento: citação literal dela -->
    De 150 a 200, o Máximo; de 30 a 99, o Economia; abaixo de 30, nenhum. De
    100 a 149, nenhum: o «Padrão» (antes «Balanceado») só acende pelo nome, porque
    desde 04/10/2026 ele trava as barras, e o trilho não. A faixa entre os
    degraus é por delegação, a validar por ela (a fala dela diz só a de cima).
    Os limites são os da escada do produto (``app/telas/vibracao``), e não
    números daqui.

    O VALOR É O DO TRILHO: o mesmo pedido que o número ao lado mostra
    (``_tela._pedido_da_politica``). Política fora da escada, ou personalizado
    sem número lido, não acende nada.
    """
    pedido = _tela._pedido_da_politica(
        {"rumble_policy": policy, "rumble_mult_applied": custom})
    if pedido is None:
        return ""
    valor = round(float(pedido) * 100)
    escada = _tela._escada()
    aceso = ""
    for chave in _tela.degraus_da_forca():
        if valor >= round(escada[chave] * 100):
            aceso = chave
    if aceso == POLITICA_PADRAO and policy != POLITICA_PADRAO:
        # «Padrão» é um ESTADO, não uma faixa do trilho (04/10/2026): o sinal como o jogo
        # mandou, com as barras travadas. O trilho entre 100 e 149 multiplica e destrava as
        # barras, e acender «Padrão» ali diria na tela o que o aparelho não faz.
        return ""
    return aceso


def _haptica_do_controle(state: dict[str, Any], uniq: str) -> tuple[int, bool]:
    """``(haptica_pct, alcança)`` deste controle, do `state_full`.

    A-LINHA-DA-HAPTICA-POR-AUDIO-NA-VIBRACAO-01, 29/09/2026. O número é o do
    dono do ganho (`daemon.ganho_da_haptica`), que o daemon publica por
    controle; sem ele vale o `haptica_pct_padrao` publicado ao lado, e só o
    daemon velho, que não publica nenhum dos dois, cai no padrão do esquema.
    ``alcança`` é falso onde o Hefesto não está no caminho do controle.
    """
    padrao = state.get("haptica_pct_padrao")
    if not isinstance(padrao, int) or isinstance(padrao, bool):
        from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

        padrao = HAPTICA_PCT_PADRAO
    chave = _chave_no_perfil(uniq)
    for c in state.get("controllers") or ():
        if not isinstance(c, dict):
            continue
        dele = str(c.get("uniq") or "")
        if not dele or (dele != uniq and _chave_no_perfil(dele) != chave):
            continue
        valor = c.get("haptica_pct")
        pct = (int(valor) if isinstance(valor, int) and not isinstance(valor, bool)
               else int(padrao))
        return pct, c.get("haptica_alcanca") is not False
    return int(padrao), True


def _haptica_no_ar(state: dict[str, Any], uniq: str) -> bool:
    """O `haptica_no_ar` deste controle no `state_full`; sem ele, apagada."""
    chave = _chave_no_perfil(uniq)
    for c in state.get("controllers") or ():
        if not isinstance(c, dict):
            continue
        dele = str(c.get("uniq") or "")
        if dele and (dele == uniq or _chave_no_perfil(dele) == chave):
            return c.get("haptica_no_ar") is True
    return False


def _perfil_ativo(ctx: Contexto) -> dict[str, Any]:
    """O perfil ATIVO inteiro, cru do disco. `{}` quando não há.

    CRU E SEM PYDANTIC de propósito — é o que `pacotes/perfil.ativo` entrega, e
    a razão está escrita lá: validar aqui só serviria para LEVANTAR a aba
    inteira por causa de um campo que o esquema ainda não conhece, e a tela
    congelaria sem dizer por quê.

    LÊ O DISCO A CADA TIQUE, e é o que a aba Conexões já faz para o mesmo dado
    (`a08_conexoes._teto_do_controle`). O `state_full` **não publica override
    por controle nenhum** — nem o de vibração, nem o dos LEDs —, então o disco é
    a única fonte que existe. Um perfil é um JSON de alguns kB; dois tiques por
    segundo cabem.

    **DEVOLVE O ARQUIVO INTEIRO, E NÃO SÓ O `controllers` — 04/09/2026.** Ela
    era `_overrides_do_perfil`, e devolvia só aquele bloco; a ressalva da mesa
    em `Auto` (:func:`_ressalva_da_mesa`) precisa do bloco `rumble` do MESMO
    arquivo, e duas funções abrindo o mesmo JSON no mesmo tique seriam duas
    leituras de disco por tique para responder o que uma já tinha na mão.

    O NOME SE PERGUNTA AO DONO — costura da ONDA D, 06/09/2026, e é a metade
    que a `PERFIL-MODO-01` não alcançou. Aqui estava::

        nome = ctx.state.get("active_profile") or ""
        return _perfil.ativo(nome) if nome else {}

    O `if nome else {}` DECIDIA ANTES DO DONO: com o daemon respondendo
    ``active_profile: null`` — o estado da máquina dela — a guarda saía com `{}`
    sem nunca chamar `perfil.ativo`, então a cura que ensinou o dono a olhar
    também o marcador em disco não chegava a esta aba. `nome_do_ativo` resolve as
    duas pernas (o daemon primeiro, o disco depois) e devolve `""` só quando
    ninguém está valendo — e `perfil.ativo("")` já responde `{}` por si.
    """
    return _perfil.ativo_que_vale(_perfil.nome_do_ativo(getattr(ctx, "state", None)))


def _ressalva_da_mesa(perfil: dict[str, Any], mesa: list[dict[str, Any]]) -> str:
    """A linha que confessa a escolha GRAVADA que não chega ao motor. `""` = não há.

    **É A METADE QUE VIVE NO TEMPO da cura de 04/09/2026.** A outra é o recado
    do clique (:func:`_aplicar_a_forca`), e as duas não se substituem: o recado
    dura :data:`hefesto_vivo.SEGUNDOS_DO_RECADO` e fala do gesto que ela acabou
    de fazer; ESTA linha fica na tela **enquanto a condição existir** — inclusive
    para quem abrir a aba amanhã, sem ter clicado nada, e vir quatro degraus
    acesos que o motor não obedece.

    A CONDIÇÃO É UMA SÓ, e o produto a nomeia: com a força da MESA (a do próprio
    perfil) em `auto`, `profiles/manager._controllers_to_rumble_scales` PULA
    toda peça com opinião — `escala_de_vibracao_pulada_base_movel` — porque o
    denominador muda com a bateria a cada tique. Era o
    :data:`SEM_DONO`\\ ``["forca:global-em-auto"]``, que dizia *"o que falta é a
    tela AVISAR"*.

    **SÓ QUANDO HÁ O QUE PERDER.** Sem nenhuma peça com `rumble` no bloco
    `controllers`, a mesa em `Auto` não está engolindo escolha nenhuma, e a
    linha viraria ruído crônico — a mesma disciplina do
    `rumble_actions.texto_de_onde_grava_e_onde_manda`, que devolve `None` quando
    não há divergência a confessar.

    A CONTAGEM É DA MESA VIVA, e não do arquivo: um perfil pode guardar a
    opinião de dez controles que não estão na sala, e avisar sobre eles seria
    alarme sobre um aparelho que ela não tem na mão. Quem conta são os `uniq`
    que estão na mesa AGORA, nas duas grafias — pelo mesmo motivo de
    :func:`_forca_da_coluna`: um perfil editado à mão traz `aa:bb:…` e o disco
    canoniza para doze hexa só quando alguém o CARREGA.
    """
    if str((perfil.get("rumble") or {}).get("policy") or "") != "auto":
        return ""
    dos_controles = perfil.get("controllers")
    if not isinstance(dos_controles, dict):
        return ""
    quantos = 0
    for c in mesa:
        uniq = str(c.get("uniq") or "")
        if not uniq:
            continue
        dele = dos_controles.get(_chave_no_perfil(uniq)) or dos_controles.get(uniq) or {}
        if isinstance(dele, dict) and isinstance(dele.get("rumble"), dict):
            quantos += 1
    if not quantos:
        return ""
    # (:data:`FRASE_DA_MESA_EM_AUTO`), que mora numa caixa que CRESCE. Esta
    return (f"a força geral está em Auto, e por isso a força própria de "
            f"{quantos} controle(s) fica guardada sem chegar ao motor. Tire o "
            f"Auto e as escolhas voltam a valer.")


def _quanto_multiplica(pct: dict[str, Any], barra: int | None) -> str:
    """A frase que diz o efetivo deste motor — `barra x degrau`.

    **VIBRA-MULT-01, 09/09/2026.** Ela responde, sem um clique, a pergunta que
    a queixa dela fazia: *"o motor esquerdo está multiplicando pela força?"*.

    CALA QUANDO NÃO SABE, que é a regra desta casa para campo sem informação:
    sem degrau conhecido (uma política fora das cinco) não há produto a
    afirmar, e uma frase com `—` no meio é pior que silêncio.

    O NÚMERO SAI INTEIRO quando é redondo — `75%`, não `75.0%`: a tela desta
    aba imprime porcentagem sem casa em toda parte, e uma casa decimal aqui
    faria a dica parecer mais precisa do que o degrau que a origina.
    """
    if not pct.get("sabe") or barra is None:
        return ""
    degrau = float(str(pct.get("n", "")).rstrip("%") or 0)
    efetivo = degrau * int(barra) / 100.0
    def _n(v: float) -> str:
        return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"
    return (f"Este motor a {barra}%, força {_n(degrau)}% — sai "
            f"{_n(efetivo)}% do que o jogo pedir.")


PALAVRA_DO_PADRAO = "Padrão"

PALAVRA_DO_ZERO = "Desligado"

FRASE_DO_PADRAO = (
    "Padrão: o sinal chega como o jogo mandou. Escolha Economia ou Máximo para ajustar.")


def _texto_da_barra(valor: int, padrao: bool) -> str:
    """O que o número da barra diz: «Padrão» travado, «Desligado» no zero, ou o valor."""
    if padrao:
        return PALAVRA_DO_PADRAO
    return PALAVRA_DO_ZERO if int(valor) <= 0 else str(valor)


def _barras_dos_motores(state: dict[str, Any], uniq: str) -> dict[str, int]:
    """``{"e": forte_pct, "d": fraco_pct}`` DESTE controle, do `state_full`.

    **É A METADE QUE LÊ DE VOLTA** o que :func:`motor` grava — e sem ela a aba
    desenha a barra onde ela ESTAVA, não onde ela está. A fonte é
    `state_full.rumble_motores`, publicada pela ONDA1-D2 em 04/09/2026, e ela é
    **o mesmo mapa que `apply_game_rumble` multiplica**
    (`gamepad._motores_do_perfil_ativo`, memoizado pelo nome do perfil). Ler o
    disco aqui por conta própria poderia pintar um número que o motor não está
    usando — que é o "aplicado" falso que esta casa passou 04/09 arrancando.

    **O PADRÃO NÃO SE DIGITA:** a peça sem opinião **não entra no mapa** (mesma
    disciplina do `set_rumble_scales`), e o valor dela chega ao lado, em
    `rumble_motor_pct_padrao`. Escrever `100` aqui seria a segunda cópia do
    `MOTOR_PCT_PADRAO` do esquema — e a segunda diverge no dia em que a primeira
    mudar.

    AS DUAS GRAFIAS DE CHAVE, como em :func:`_forca_da_coluna`: o daemon chaveia
    pelo MAC normalizado (`gamepad._chave_da_peca`), e a mesa pode trazer o
    endereço com dois-pontos. Sem as duas, o mapa fica **mudo em silêncio** —
    que é o defeito que o próprio `_chave_da_peca` nasceu para evitar do outro
    lado da ponte.
    """
    padrao = state.get("rumble_motor_pct_padrao")
    if not isinstance(padrao, int) or isinstance(padrao, bool):
        from hefesto_dualsense4unix.profiles.schema import MOTOR_PCT_PADRAO

        padrao = MOTOR_PCT_PADRAO
    mapa = state.get("rumble_motores")
    dele = {}
    if isinstance(mapa, dict):
        achado = mapa.get(_chave_no_perfil(uniq)) or mapa.get(uniq) or {}
        if isinstance(achado, dict):
            dele = achado
    fora: dict[str, int] = {}
    for lado, motor in _tela.LADO_PARA_MOTOR.items():
        valor = dele.get(_tela.MOTOR_PARA_BARRA[motor])
        fora[lado] = (int(valor)
                      if isinstance(valor, int) and not isinstance(valor, bool)
                      else int(padrao))
    return fora


def _forca_propria(overrides: dict[str, Any], uniq: str) -> tuple[str, Any] | None:
    """A força que ESTE controle guarda só para ele, ou ``None`` quando herda.

    **É O QUE A DECISÃO [05] DELA PRECISA E NÃO EXISTIA** — 04/09/2026: *"a
    coluna sem ajuste próprio deixa de acender degrau e passa a apontar para
    essa linha; 'herdado' fica óbvio sem uma palavra a mais"*. Até hoje as duas
    coisas tinham a MESMA cara na tela: um degrau que ela escolheu para aquele
    controle e um degrau que o Hefesto está usando porque a mesa manda.

    A REGRA É A DO PRODUTO, e é um campo só: `policy` escrita no override vence;
    sem ela, herda. É o mesmo desvio de `app/draft_config.effective_rumble_for`
    e de `profiles/manager._controllers_to_rumble_scales`.
    """
    dele = overrides.get(_chave_no_perfil(uniq)) or overrides.get(uniq) or {}
    seu = dele.get("rumble") if isinstance(dele, dict) else None
    if isinstance(seu, dict) and seu.get("policy"):
        return str(seu["policy"]), seu.get("custom_mult")
    return None


def _forca_da_coluna(overrides: dict[str, Any], uniq: str,
                     state: dict[str, Any]) -> tuple[str, Any]:
    """`(policy, custom_mult)` que ESTA coluna está pedindo — dela, ou da mesa.

    **É A METADE QUE PINTA da decisão dela de 03/09/2026** — *"construir por
    controle"*. A outra é :func:`_gravar_a_forca`, e sem esta a tela mentiria
    logo depois do primeiro clique: o override vai para o PERFIL, o
    `state_full` continua publicando só o `rumble_policy` da mesa, e as quatro
    colunas voltariam a acender o mesmo degrau um tique depois de ela escolher
    quatro diferentes.

    A PRECEDÊNCIA É A DO PRODUTO, campo por campo: override com `policy`
    escrita vence; sem ela, herda o global. É a mesma regra de
    `app/draft_config.effective_rumble_for` e de
    `profiles/manager._controllers_to_rumble_scales` — os dois desviam por
    `cfg.rumble is None` e por `"policy" not in model_fields_set`.

    AS DUAS GRAFIAS DE CHAVE, e a segunda não é paranoia: `perfil.ativo` lê o
    JSON **sem** o pydantic, então um arquivo editado à mão pode trazer
    `aa:bb:…` — que o loader só canoniza quando alguém o CARREGA. É o mesmo
    cuidado do `a08_conexoes._teto_do_controle`.
    """
    politica, custom, _ = _forca_em_vigor(overrides, uniq, state)
    return politica, custom


def _forca_em_vigor(overrides: dict[str, Any], uniq: str,
                    state: dict[str, Any]) -> tuple[str, Any, bool]:
    """`(policy, custom_mult, é dela?)` — **o dono único de "qual degrau vale"**.

    **NASCEU DA VIBRA-ACESA-01, 17/09/2026, e o defeito que ela fecha é de
    DUPLICIDADE.** A mesma pergunta tinha duas bocas: `pacote_da_coluna`
    repetia o desvio de :func:`_forca_propria` na própria linha em que montava a
    coluna, e :func:`_forca_da_coluna` o montava de novo para o gesto. As duas
    respondiam a mesma coisa por caminhos separados, e
    :func:`_aplicar_a_forca` comparava UMA com a OUTRA — que é a forma clássica
    desta casa de fabricar um buraco.

    A TERCEIRA CASA DA TUPLA É O QUE FALTAVA À TELA: a precedência já era
    conhecida, mas a PROCEDÊNCIA morria dentro da função. Quem pinta precisa
    saber se aquele degrau é escolha dela para este controle ou herança do
    ajuste geral — são coisas diferentes e tinham a mesma cara.

    A REGRA É A DO PRODUTO, e continua sendo um campo só: override com `policy`
    escrita vence; sem ela, herda o global. É o mesmo desvio de
    `app/draft_config.effective_rumble_for` e de
    `profiles/manager._controllers_to_rumble_scales`.
    """
    propria = _forca_propria(overrides, uniq)
    if propria is not None:
        politica, custom = propria
        return politica, custom, True
    return (str(state.get("rumble_policy") or ""),
            state.get("rumble_mult_applied"), False)


def _pct_da_coluna(policy: str, custom: Any) -> dict[str, str]:
    """A barra do multiplicador DESTA coluna: largura, número e o `sabe`.

    A CONTA NÃO NASCE AQUI. `app/telas/vibracao._pedido_da_politica` é a mesma
    linha da janela estável (`rumble_actions._pintar_a_linha_do_teto:537`) —
    `custom_mult if policy == "custom" else _POLICY_MULT.get(policy)` — e ela
    recebe um dicionário com as duas chaves. Passar `{"rumble_policy": …,
    "rumble_mult_applied": …}` **não é forjar um estado**: são os nomes que o
    daemon dá aos mesmos dois valores, e para `custom` o `rumble_mult_applied`
    do daemon É o multiplicador personalizado. Redigitar `_POLICY_MULT[policy]
    * 100` aqui seria a segunda tabela de degraus que `_escada()` existe para
    não ter.

    ESTA FUNÇÃO SUCEDE A `_pct_do_pedido`, e herda a medição que a decidiu —
    ela sai daqui inteira porque é decisão medida, não número errado.

    **O NÚMERO ESTAVA MORTO, e a medição é de 03/09/2026, contra o daemon
    dela.** `pacote_da_coluna` montava esta barra a partir de
    `state_full.rumble_mult_applied`, que é o `daemon._last_auto_mult`. Cliquei
    os QUATRO degraus pela mesma porta que o botão da coluna usava então
    (`rumble_policy_set_checked`), esperei meio segundo e reli o `state_full`::

        policy_set(max       ) → policy='max'        applied=0.7
        policy_set(economia  ) → policy='economia'   applied=0.7
        policy_set(auto      ) → policy='auto'       applied=0.7
        policy_set(balanceado) → policy='balanceado' applied=0.7

    O daemon obedeceu as quatro vezes — a política mudou —, e o número que a
    tela mostra **não se moveu uma vez**. Com `rumble_policy='balanceado'`
    (multiplicador 1,0) a aba escrevia `70%`, pintava o trilho em 46,7% e
    deixava o `Máx` apagado no `max`. A própria dica dela, duas linhas acima na
    mesma tela, promete o contrário: *"Economia 30% · Balanceado 100% · Máximo
    150%"*.

    O PRODUTO JÁ SABIA, por escrito: `daemon/lifecycle.py:2635-2641` conta que
    `_last_auto_mult` fica **preso no default 0.7** em passthrough ocioso e que,
    ao vivo, `policy=max` com `rumble_mult_applied=0.7` *"parecia atenuação real
    do rumble do jogo"*. A aba publicava exatamente essa aparência.

    `None` — política fora das cinco, ou `custom` sem multiplicador lido —
    atravessa como o `—` de sempre: `_barra(None, …)` devolve `sabe = ""`, e
    campo sem informação não acende o `Máx` nem afirma largura.

    O QUE ISTO NÃO RESOLVE, e fica dito: no degrau `Auto` a barra diz **100%**,
    que é o TETO dele — o mesmo número da janela estável — e não os 70% que a
    cena do mockup ensina para uma bateria no meio. O valor vivo do Auto exige
    um campo que o daemon não publica com honestidade hoje.
    """
    pedido = _tela._pedido_da_politica(
        {"rumble_policy": policy, "rumble_mult_applied": custom})
    return _tela._barra(
        None if pedido is None else round(pedido * 100),
        teto_da_barra(),
        sufixo="%",
    )


# fixo fizesse ela o que fizesse com as barras. A prosa da VIBRA-MULT-01 em
# `state_full` e a busca por `player` cabe em três linhas.


@registrar("05-vibracao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `app/telas/vibracao.pacote_da_mesa` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA, e é o `casa-sabe` que a denunciou:
    `app/telas/vibracao.py` tinha funções públicas — `pacote_da_mesa`,
    `pacote_da_coluna`, `degraus_da_forca`, `motores_do_controle`,
    `teto_da_barra` — e **nenhuma tinha chamador em produção**. O portão as
    listava como promessa sem caminho desde 31/08/2026. As duas que só serviam
    à remontagem e ao eco do clique (`estado_da_coluna`, `gesto_do_clique`)
    saíram em 28/09/2026 (A-TELA-PERGUNTA-AO-DONO-01).

    Ela é MAIS COMPLETA que o que este pacote tinha: devolve a largura da barra
    já em `%` (`pct.w`), o número formatado, o `sabe` que distingue "zero" de
    "não sei", a cor do plástico e o `treme` por motor. Reescrever isso era a
    duplicação que a pergunta dela de 01/09 pegou — *"não estamos refazendo do
    zero né?"*

    O QUE SOBRA AQUI é o ACHATAMENTO: o produto devolve `{"pct": {"w": "66.7%"}}`
    e a tela endereça `data-campo="forca-pct"`. Traduzir a forma é da interface;
    calcular o valor é do produto.

    A ÚNICA CONTA QUE NÃO VEM DO `pacote_da_mesa` é a barra do multiplicador, e
    ela vem de outra função do MESMO módulo do produto — ver
    :func:`_pct_da_coluna`, com as quatro medições que a decidiram.

    O NOME `forca` NÃO SAI MAIS DAQUI — 02/09/2026, e a razão está fotografada.
    O pintor procura um valor por `[data-campo=X],[data-papel=X],[data-hef=X]`
    (`hefesto_vivo.py:74`), e nesta página `forca` é **as duas coisas**: o
    `data-campo` do número do multiplicador E o `data-papel` dos quatro degraus
    mais o da linha inteira do "Personalizado". Emitir a chave `forca` escrevia
    `"balanceado"` em DEZ elementos por tique:

    * os quatro botões perdiam o rótulo — "Economia", "Balanceado", "Máximo" e
      "Auto" viraram os quatro a mesma palavra, e ela deixa de poder escolher;
    * a linha do "Personalizado" é um `<div>` com filhos, e `textContent`
      **apaga os filhos**: o trilho, o número e o "Máx" sumiam da tela — junto
      com os endereços `forca-pct` e `mult`, que a pintura seguinte já não
      achava.

    Medido em 02/09/2026 na foto `/tmp/antes-05.png`, com o daemon dela vivo.
    O NÚMERO passou a se endereçar por `mult` (`aba05._barra`, `campo_num`);
    o trilho continua `forca-pct`, que nunca esteve em colisão. A régua
    `test_a_vibracao_nao_escreve_no_botao.py` reprova qualquer nome que volte a
    ser valor e clique ao mesmo tempo.
    """
    import mesa_viva


    # NINGUÉM a punha: `mesa_viva.mesa_do_estado` monta o item com `cor` (o slug)
    mesa = [dict(c, plastico=_plastico_do_item(c)) for c in ctx.mesa]
    bruto = _tela.pacote_da_mesa(ctx.state, mesa, ctx.conectados,
                                 contagem=mesa_viva.texto_da_contagem(ctx.mesa))
    modelo_por_uniq = {
        str(c.get("uniq") or ""): str(c.get("cor") or "") for c in ctx.mesa
    }
    colunas: dict[str, dict[str, Any]] = {}
    # `col["forca"]`, porque `pacote_da_coluna` só conhece o `state_full`; quem
    # UMA LEITURA POR TIQUE, e não uma por coluna: `perfil.ativo` abre o JSON,
    perfil_ativo = _perfil_ativo(ctx)
    bloco_dos_controles = perfil_ativo.get("controllers")
    overrides = bloco_dos_controles if isinstance(bloco_dos_controles, dict) else {}
    for uniq, col in (bruto.get("colunas") or {}).items():
        politica, custom, propria = _forca_em_vigor(overrides, uniq, ctx.state)
        pct = _pct_da_coluna(politica, custom)
        barras = _barras_dos_motores(ctx.state, uniq)
        padrao = vale_o_padrao(politica)
        plano = {
            "identidade": _sem_marcacao(col.get("identidade", "")),
            # variável em vez de inventar um tom.
            "plastico": str(col.get("plastico") or ""),
            "colorway": modelo_por_uniq.get(uniq, ""),
            "mult": pct.get("n", "—"),
            "mult-pos": (str(pct.get("n", "")).rstrip("%")
                         if pct.get("sabe") else ""),
            "forca-pct": str(pct.get("w", "")).rstrip("%"),
            "degrau": degrau_da_faixa(politica, custom),
            "degrau-herdado": "1" if politica and not propria else "",
            "mult-teto": _no_teto(pct),
            "em-teste": "1" if uniq and uniq in em_teste() else "",
            "padrao": "1" if padrao else "",  # (noqa-acento) campo
        }
        for lado, m in (col.get("motores") or {}).items():
            plano[f"motor-{lado}"] = m.get("n", "—")
            plano[f"motor-{lado}-pct"] = str(m.get("w", "")).rstrip("%")
            # O PEDIDO DO JOGO VIRA `title` — 04/09/2026, e é onde a LEITURA foi
            # `state_full.rumble_motores`, o MESMO mapa que
            plano[f"motor-{lado}-pedido"] = (
                f'O jogo pediu {m.get("n")} de 255 neste motor agora.'
                if m.get("sabe") else FRASE_DO_PADRAO if padrao
                else _quanto_multiplica(pct, barras.get(lado)))
            plano[f"barra-{lado}"] = str(barras[lado])
            plano[f"barra-{lado}-pct"] = _texto_da_barra(barras[lado], padrao)
            # ELE NÃO TEM VALOR PRÓPRIO, e é isso que o deixa nascer sem campo
            plano[f"lado-{lado}"] = "1" if barras[lado] > 0 else ""
        haptica, alcanca = _haptica_do_controle(ctx.state, uniq)
        plano["barra-h"] = str(haptica)
        plano["barra-h-pct"] = _texto_da_barra(haptica, padrao)
        plano["lado-h"] = "1" if haptica > 0 else ""
        plano["haptica-fora"] = "" if alcanca else "1"
        # chegando a ESTE controle agora, do `state_full` (`haptica_no_ar`).
        plano["haptica-no-ar"] = "1" if _haptica_no_ar(ctx.state, uniq) else ""
        plano["em-teste-h"] = "1" if uniq and uniq in em_teste_da_haptica() else ""
        for lado, treme in (col.get("treme") or {}).items():
            plano[f"treme-{lado}"] = "1" if treme else ""
        # sempre vai ser o jogo mandando os input pro controle e a gnt
        # aba terminam em `rumble_passthrough(True)` — :func:`testar` (passos 3
        colunas[uniq] = plano
    linhas_do_estado = _tela.textos_do_estado(ctx.state)
    ressalva = _ressalva_da_mesa(perfil_ativo, ctx.mesa)
    if ressalva:
        linhas_do_estado.append((_tela.ALERTA, ressalva))
    estado = _tela.html_do_estado(linhas_do_estado)
    return {
        "colunas": colunas,
        "mesa": {},
        "blocos": {"#vib-estado": estado},
        "sem_dono": dict(SEM_DONO),
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


def _sem_marcacao(texto: str) -> str:
    """Tira o HTML do produto: a tela nova escreve `textContent`, não `innerHTML`."""
    import re as _re

    sem_tags = _re.sub(r"<[^>]+>", "", texto)
    return _re.sub(r"\s*•\s*", " · ", sem_tags).strip()


# disso — `app/actions/rumble_actions.py` escreve *"não há IPC de política
from . import coracao, gesto, largada  # noqa: E402

#: estável (`app/actions/rumble_actions.py`, `weak = 160` / `strong =
PAR_DE_TESTE = (160, 220)

_O_PULSO_SAIU = "07/09/2026 — o Testar virou estado; ver `_EM_TESTE`"

#:
#: (`app/actions/rumble_actions.py`) remove a fonte GLib pendente e é
_VEZ = [0]

#: Os controles com o «Testar» da vibração LIGADO agora. UM POR CONTROLE: o
#: teste de um não toca no do outro (03/10/2026, ela: *«vibração e háptico é
#: por cada controle e precisam funcionar em independente»*). Era um `uniq` só,
#: e ligar o do P2 calava o do P1.
_EM_TESTE: set[str] = set()


def em_teste() -> frozenset[str]:
    """Os `uniq` em teste agora. Leitura pura, para a tela e a régua."""
    return frozenset(_EM_TESTE)


#: O mesmo para o «Háptica» (botões lado a lado, a resposta [24] dela).
_EM_TESTE_DA_HAPTICA: set[str] = set()


def em_teste_da_haptica() -> frozenset[str]:
    """Os `uniq` com o teste da háptica ligado agora. Leitura pura."""
    return frozenset(_EM_TESTE_DA_HAPTICA)


def parar_o_teste_da_haptica(uniq: str | None = None) -> None:
    """Apaga a marca do teste da háptica de `uniq`, ou de todos sem argumento."""
    if uniq is None:
        _EM_TESTE_DA_HAPTICA.clear()
        _BATEU_A_HAPTICA_EM.clear()
        return
    _EM_TESTE_DA_HAPTICA.discard(uniq)
    _BATEU_A_HAPTICA_EM.pop(uniq, None)


def parar_o_teste(uniq: str | None = None) -> None:
    """Apaga a marca do teste de `uniq`, ou de todos sem argumento.

    DUAS PORTAS PRECISAM DISTO, e as duas são risco de verdade:

    * a suíte, que roda os gestos no MESMO processo — um "Testar" de um caso
      deixava a marca ligada e o arraste de barra do caso seguinte mandava
      vibração que ninguém pediu (medido em 07/09/2026);
    * o controle que SAI da mesa com o teste ligado. Sem apagar a marca, o
      próximo arraste de barra tentaria vibrar um aparelho que não está aqui.
    """
    if uniq is None:
        _EM_TESTE.clear()
        _BATEU_EM.clear()
        return
    _EM_TESTE.discard(uniq)
    _BATEU_EM.pop(uniq, None)


SEGUNDOS_ENTRE_BATIMENTOS = 1.0

_BATEU_EM: dict[str, float] = {}


@coracao
def _bater_o_coracao_do_teste(ctx: Contexto, p: Any) -> None:
    """Diz ao daemon, a cada segundo, que a janela ainda segura os motores DE CADA teste.

    NASCEU DA ORDEM DELA, 15/09/2026: *"o testar e parar é sobre o teste naquele
    momento isso nao interfere in game"*  (noqa-acento: citação literal dela). O
    "Testar" tira os motores do jogo e os devolve no "Parar" — e fechar a
    janela, trocar de aba ou a janela morrer deixava o jogo mudo até ela voltar
    e clicar. O daemon solta o par que ninguém rebate
    (`TETO_DO_RUMBLE_FIXADO_S`); o batimento é o que diz *"ainda estou aqui"*.

    ELE NÃO MANDA VIBRAÇÃO NOVA. O par vem de :func:`_par_das_barras`, o mesmo
    que o arraste reenvia, e cada controle em teste bate com o endereço dele.
    """
    agora = _monotonic()
    for uniq in sorted(_EM_TESTE):
        if agora - _BATEU_EM.get(uniq, 0.0) < SEGUNDOS_ENTRE_BATIMENTOS:
            continue
        _BATEU_EM[uniq] = agora
        if not any(str(c.get("uniq") or "") == uniq for c in ctx.mesa):
            parar_o_teste(uniq)
            continue
        weak, strong = _par_das_barras(ctx, uniq)
        with contextlib.suppress(Exception):
            p.rumble_set_checked(weak, strong, uniq=uniq)


_BATEU_A_HAPTICA_EM: dict[str, float] = {}


@coracao
def _bater_o_coracao_da_haptica(ctx: Contexto, p: Any) -> None:
    """Rebate o teste da háptica de cada controle a cada segundo."""
    agora = _monotonic()
    for uniq in sorted(_EM_TESTE_DA_HAPTICA):
        if agora - _BATEU_A_HAPTICA_EM.get(uniq, 0.0) < SEGUNDOS_ENTRE_BATIMENTOS:
            continue
        _BATEU_A_HAPTICA_EM[uniq] = agora
        if not any(str(c.get("uniq") or "") == uniq for c in ctx.mesa):
            parar_o_teste_da_haptica(uniq)
            continue
        with contextlib.suppress(Exception):
            p.haptica_testar(uniq, True)


@largada
def _largar_o_teste_da_haptica(p: Any) -> None:
    """Cala os testes da háptica ao trocar de página e ao fim da janela."""
    for uniq in sorted(_EM_TESTE_DA_HAPTICA):
        _calar_o_teste_da_haptica(p, uniq)


def _calar_o_teste_da_haptica(p: Any, uniq: str) -> None:
    """O teste da háptica DESTE controle cala, e a marca cai. Os outros seguem."""
    if uniq not in _EM_TESTE_DA_HAPTICA:
        return
    parar_o_teste_da_haptica(uniq)
    with contextlib.suppress(Exception):
        p.haptica_testar(uniq, False)


def _devolver_ao_jogo(p: Any, uniq: str) -> None:
    """Para os motores DESTE controle e devolve a mão dele ao jogo.

    São os dois passos que o «Parar» sempre deu: parar sozinho fixa `(0, 0)` e o
    laço do daemon re-afirma o silêncio, e o jogo ficaria mudo depois de um teste
    (SPRINT-GAME-RUMBLE-01). Com `uniq`, nenhum dos dois toca no par dos outros.
    """
    with contextlib.suppress(Exception):
        p.rumble_stop(uniq)
    with contextlib.suppress(Exception):
        p.rumble_passthrough(True, uniq)


@largada
def _largar_o_teste(p: Any) -> None:
    """Devolve os motores ao jogo. Chamado ao trocar de página e ao fim da janela."""
    for uniq in sorted(_EM_TESTE):
        parar_o_teste(uniq)
        _devolver_ao_jogo(p, uniq)


def _reduzido_pela_barra(valor: int, pontos: int) -> int:
    """`valor` (0-255) reduzido pela barra daquele motor, e nunca fora da faixa."""
    return max(0, min(255, round(valor * int(pontos) / 100.0)))


def _par_das_barras(
    ctx: Contexto, uniq: str, *, acabou_de_gravar: tuple[str, int] | None = None
) -> tuple[int, int]:
    """`(weak, strong)` do teste DAQUELE controle, **reduzido pela barra de cada motor**.

    **MEDIDO EM 09/09/2026 — VIBRA-MULT-01, e é a queixa dela inteira.** Ela:
    *"na guia vibração os slicers não estão se multiplicando: motor esquerdo x
    força de vibração (…) pra cada controle"*. Duas coisas estavam erradas, e a
    segunda é a razão de a primeira nunca ter aparecido:

    1. **Esta função lia duas chaves que o daemon não publica no bloco de onde
       ela lia.** `last_weak` e `last_strong` moram no TOPO do `rumble_ff`
       (`daemon/ipc_handlers.py:2522`), e o que chegava aqui era um bloco de
       `per_vpad`, que não tem nem uma nem outra. As duas leituras davam `0`
       sempre, o `if` caía sempre no :data:`PAR_DE_TESTE`, e o "Testar" mandava
       `(160, 220)` **fizesse ela o que fizesse com as barras**. Medido com a
       barra esquerda em ZERO: `rumble.set(160, 220)` — o motor que ela mandou
       calar tremia igual ao outro.
    2. **O caminho do rumble FIXADO não aplica a barra.**
       `gamepad._mults_por_motor` — o dono da conta `degrau x barra` — tem UM
       chamador, `gamepad.apply_game_rumble`, que é o FF do JOGO. O `rumble.set`
       desta aba vai por `daemon/ipc_handlers._handle_rumble_set` ->
       `apply_rumble_policy`, e o reassert de 5 Hz por
       `daemon/subsystems/rumble.reassert_rumble` -> `_effective_mult`: os dois
       aplicam **um fator só, o degrau, igual nos dois motores**. Mesmo com a
       leitura curada, arrastar a barra não mudaria uma vírgula na mão dela.

    **O QUE ESTA FUNÇÃO FAZ, e o que ela NÃO faz.** Ela reduz o par de teste
    pela barra de cada motor, e **só isso**. O degrau continua sendo do daemon
    nos três andares em que ele já morava — a política global em
    `apply_rumble_policy`, a escala por controle em
    `profiles/manager._controllers_to_rumble_scales` e o teto do card do cabo no
    backend. O que a mão dela sente passa a ser `base x barra x degrau`: o mesmo
    produto que `_mults_por_motor` monta para o jogo, com cada metade aplicada
    por quem já a aplicava.

    **É PROVISÓRIO — decisão dela.** A cura que cobre TODOS os chamadores é do
    lado do daemon (`_handle_rumble_set` e `reassert_rumble` passando por
    `_mults_por_motor`), e os dois arquivos não são da posse desta sprint. Sem
    ela, `hef test rumble` e o "Testar" da janela GTK continuam sem a barra —
    está na entrega, com as linhas nomeadas.

    A INVERSÃO É A ARMADILHA DESTE ASSUNTO: `weak` é o motor da DIREITA (`d`) e
    `strong` o da ESQUERDA (`e`) — `core/backend_pydualsense.py:3369` faz
    `setLeftMotor(eff_strong)`. A tradução não se digita aqui: ela é de
    `app/telas/vibracao.LADO_PARA_MOTOR`, e :func:`_barras_dos_motores` já
    devolve o mapa na língua da tela.

    `acabou_de_gravar` É O ARRASTE QUE AINDA NÃO VOLTOU: o `ctx` de um gesto é
    o tique ANTERIOR à gravação, então reenviar lendo só o `state` faria ela
    sentir o valor de antes do arraste — o "ao vivo" atrasado em um tique. Quem
    grava sabe o que gravou e diz.
    """
    weak, strong = PAR_DE_TESTE
    perfil = _perfil_ativo(ctx).get("controllers")
    politica, _, _ = _forca_em_vigor(perfil if isinstance(perfil, dict) else {}, uniq, ctx.state)
    if vale_o_padrao(politica):
        # Em Padrão as barras não se aplicam, e o Testar sente o mesmo que o jogo.
        return (weak, strong)
    barras = dict(_barras_dos_motores(ctx.state, uniq))
    if acabou_de_gravar is not None:
        lado, pontos = acabou_de_gravar
        if lado in barras:
            barras[lado] = pontos
    return (
        _reduzido_pela_barra(weak, barras["d"]),
        _reduzido_pela_barra(strong, barras["e"]),
    )


def _refrescar_o_teste(
    ctx: Contexto, p: Any, uniq: str, *,
    acabou_de_gravar: tuple[str, int] | None = None,
) -> None:
    """Reenvia o par ao controle em teste — é o "ao vivo" que ela pediu."""
    if not uniq or uniq not in _EM_TESTE:
        return
    if not any(str(c.get("uniq") or "") == uniq for c in ctx.mesa):
        parar_o_teste(uniq)
        return
    weak, strong = _par_das_barras(ctx, uniq, acabou_de_gravar=acabou_de_gravar)
    with contextlib.suppress(Exception):
        p.rumble_set_checked(weak, strong, uniq=uniq)


def _minha_vez() -> int:
    """Toma a vez do teste e devolve o número dela. Quem chega depois vence."""
    _VEZ[0] += 1
    return _VEZ[0]


#: caminho DELA, pelo piloto) e :func:`_indice` (a guarda contra o broadcast,
#: ELA NÃO CITA ENDEREÇO DE RÁDIO, e é contrato: os dois portões de anonimato
FRASE_DO_CONTROLE_QUE_SAIU = (
    "este controle se desligou. Espere ele voltar e clique de novo.")


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": sem alvo o `rumble.set` faz BROADCAST, e um "Testar"
    sem dono sacudiria a mesa inteira. O desenho promete o contrário — *"Testar
    faz este controle tremer até o Parar"*.

    **ELE PASSOU A SABER A DIFERENÇA ENTRE DOIS FATOS — 05/09/2026, e a decisão
    é dela na `05-Q6`:** *"Parece erro. Não deveria ocorrer ajuste de gambiarra
    sobre falha de produto nosso"*. Até aqui ele devolvia `""` para os dois, e
    quem chamava escrevia a frase de UM — a do clique solto. O outro fato é o
    controle que caiu, e a tela acusava o clique DELA por ele.

    O CAMINHO MEDIDO, e ele tem quatro degraus: o ouvinte manda `controle` = o
    assento (`p1`..`p4`), lido do `dataset.controle` da coluna
    (`hefesto_vivo.py`); o despachante traduz assento em `uniq` contra
    `self._mesa_de_agora`; essa mesa é `ctx.mesa`, montada **só com quem está
    conectado** (`mesa_viva.mesa_do_estado` → `app/mesa.py`, que filtra
    `connected`); logo, para um controle que caiu, a tradução não acha nada e o
    gesto chega com o assento e **sem** `uniq`. **O clique DISSE em qual
    controle** — a coluna existe na tela, e ela clicou dentro dela.

    A CURA MORA AQUI, e não dentro de um gesto, porque são QUATRO os
    chamadores: :func:`_mirar` (que serve `testar` e `parar`), :func:`forca`,
    :func:`intensidade` e :func:`motor`. Uma cura escrita dentro de um gesto
    deixa a próxima pessoa remedindo o mesmo defeito nos outros três — foi o que
    esta casa pagou duas vezes em 05/09.

    O CLIQUE SOLTO CONTINUA COM A FRASE DE SEMPRE: sem `controle` não há coluna,
    e é a frase de quem chama que ensina o que fazer ("clique o botão dentro da
    coluna…"). Ela varia por gesto de propósito — a do `forca` fala em degrau, a
    do `motor` fala em barra —, e por isso continua com eles.
    """
    uniq = str(o.get("uniq") or "")
    if uniq:
        return uniq
    if str(o.get("controle") or ""):
        raise RuntimeError(FRASE_DO_CONTROLE_QUE_SAIU)
    return ""


def _resposta(r: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)` seja qual for a forma que a função da ponte devolveu."""
    if isinstance(r, tuple):
        ok = bool(r[0]) if r else False
        motivo = r[1] if len(r) > 1 else None
        return ok, (str(motivo) if motivo else None)
    return bool(r), None


TETO_DA_LINHA_DA_FAIXA = 180

SEPARADOR_DA_FAIXA = " · "

TOM_DO_RECIBO = "recibo"

#: (`rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL`), sem a metade do
FATO_DO_AJUSTE_GERAL = "voltou ao ajuste geral"

FRASE_DA_MESA_EM_AUTO = (
    "guardei esta força no perfil, mas ela não chega ao motor enquanto a força "
    "geral estiver em Auto. Tire o Auto e ela volta a valer."
)

FRASE_DO_QUE_A_COLUNA_MOSTRA = (
    "esta coluna vai continuar mostrando %s: a sua escolha é igual à força "
    "geral."
)

FRASE_DO_AJUSTE_GERAL = FATO_DO_AJUSTE_GERAL + ", e esta coluna vai mostrar %s."

FRASE_JA_E_A_ESCOLHA_DESTA_COLUNA = (
    "esta coluna já está em %s — foi o que você escolheu para ela."
)


def _fator_no_motor(global_do_perfil: Any, policy: str | None,
                    custom: float | None) -> float | None:
    """O fator que esta escolha registra contra o global do PERFIL. `None` = nenhum."""
    from hefesto_dualsense4unix.profiles.manager import fator_da_unidade

    return fator_da_unidade(
        policy, getattr(global_do_perfil, "policy", None),
        custom, getattr(global_do_perfil, "custom_mult", None))


def _aplicar_a_forca(ctx: Contexto, p: Any, uniq: str,
                     policy: str, custom: float | None = None
                     ) -> dict[str, Any] | None:
    """Grava a força daquele controle **e diz o que aconteceu com ela**.

    **É A CURA DO SILÊNCIO DE 04/09/2026**, e o defeito tinha esta forma: o
    gesto gravava no perfil, voltava sem levantar, e o piloto anotava
    `("aplicou", "")`. Nos casos em que a escolha **não vira nada** — ou vira
    algo que a coluna não vai mostrar — ela clicava, nada mudava na tela, e não
    havia uma letra explicando. É a família de defeito que esta casa persegue:
    *grava e não aplica, sem uma palavra*.

    OS QUATRO DESFECHOS, e o quarto é a queixa dela de 17/09/2026:

    1. **a escolha vira escala** (o caso comum) — silêncio, que é o certo: o
       tique seguinte acende o degrau e a barra, e uma frase por clique bem
       sucedido é ruído crônico. **O silêncio só é resposta quando a TELA
       responde** — e era essa condição que faltava até 17/09: o desfecho 4
       caía aqui, num tique que não acendia nada;
    2. **a mesa está em `Auto`** — o produto PULA a peça, com log e razão
       escrita, e a escolha fica esperando no disco. :data:`FRASE_DA_MESA_EM_AUTO`;
    3. **a coluna vai mostrar OUTRO degrau** — e este só aparece LENDO DE VOLTA.
       `with_controller_rumble` limpa o override em três casos (igual ao global
       do perfil, `policy=None`, `auto`), e a coluna sem override cai no
       `rumble_policy` da MESA (:func:`_forca_em_vigor`). Clicar "Auto" no P2
       apagava o `max` dele e acendia "Balanceado" um tique depois, calado — o
       botão que ela clicou não é o que fica aceso;
    4. **o clique NÃO MUDOU NADA** — 17/09/2026, e é a queixa *"o botão não tá
       ativo"*. O degrau que ela clicou já era o que valia naquela coluna, o
       perfil não recebeu um byte, e o produto não dizia uma palavra. São dois
       estados por baixo (a coluna HERDA o degrau, ou ele já é o override dela)
       e por isso duas frases — :data:`FRASE_DO_QUE_A_COLUNA_MOSTRA` e
       :data:`FRASE_JA_E_A_ESCOLHA_DESTA_COLUNA`. Quem conta que nada foi
       escrito é o terceiro item de :func:`_gravar_a_forca`, e não uma segunda
       leitura das regras do produto.

    A CONFERÊNCIA É POR LEITURA DE VOLTA, e não por uma segunda cópia das regras
    do produto: depois de gravar, esta função relê o mapa RESULTANTE pela MESMA
    :func:`_forca_da_coluna` que pinta a tela, e compara com o que ela pediu.
    Enquanto as três regras do `with_controller_rumble` estiverem escritas lá e
    a leitura for a mesma da pintura, esta guarda não envelhece — nem no dia em
    que o produto acrescentar a quarta.

    DUAS FRASES PARA O MESMO DESFECHO, e a diferença é a CAUSA. Quando o degrau
    clicado foi o `Auto`, a razão de a coluna mostrar outra coisa tem dono e
    nome no produto — `rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL`, a
    oração RUM-3 que a janela estável diz desde 25/08 no MESMO caso. O que a
    faixa mostra é a metade do FATO dela (:data:`FATO_DO_AJUSTE_GERAL`, as
    palavras dela na `05-Q4`), e a régua exige que essa metade continue DENTRO
    da oração do produto — o dia em que ele renomear o "ajuste geral", ela
    reprova. Para os outros degraus a causa é outra — a escolha não DIVERGE da
    força geral —, e essa frase nasce aqui porque só este caminho a produz.

    **O RAMO DO `Auto` NÃO É ALCANÇÁVEL PELO CLIQUE DELA — medido em
    06/09/2026, e a data importa.** O botão `Auto` saiu da tela em 05/09
    (`aba05.FORCA` tem três, e `RUMBLE_POLICY_MULT` também), então
    `policy == "auto"` não chega aqui pelo gesto :func:`forca`. Ele FICA, pela
    mesma razão do `raise` de :func:`_indice`: um perfil antigo, a janela
    estável ou qualquer chamador que não seja a tela ainda produzem o caso, e
    devolver a coluna ao ajuste geral calado é o silêncio que esta função
    existe para curar. Inalcançável pelo piloto não é o mesmo que enfeite.

    **A FRASE SAIU DO CARTÃO E FOI PARA A FAIXA — 05-Q4 dela, 06/09/2026:**
    *"Linha embaixo da grade (…) nomeando a coluna (`P2 · voltou ao ajuste
    geral`) e some logo depois; nada se mexe dentro das colunas"*. Fora do
    cartão a frase perde o endereço — uma linha embaixo da grade fala das
    quatro colunas ao mesmo tempo —, e por isso as três passam por
    :func:`_na_faixa`, que põe o `P{jogador}` na frente. O prefixo é de UM
    lugar só: escrevê-lo nos três ramos deixaria o quarto ramo sem ele no dia
    em que alguém acrescentasse um.

    **OS TRÊS AVISOS DEIXARAM DE SER `RuntimeError` — 04/09/2026, decisão [04]
    dela (D-01), e é uma correção de SIGNIFICADO, não de forma.** Até esta manhã
    eles subiam como recusa, com a nota escrita aqui de que *"o `RuntimeError`
    não quer dizer 'recusei' — é o único canal que chega ao cartão dela hoje"*.
    A frase estava certa e caducou no mesmo dia: a ONDA0-P construiu o canal de
    SUCESSO (`hefesto_vivo._deu_certo_dizendo`), e um gesto que devolva
    ``{"recado": "…"}`` manda a própria frase.

    O QUE MUDA NA TELA DELA, e é o ponto: a tarja passa a nascer **verde** e a
    viver 6 s em vez de 30, porque isto é um RECIBO — a gravação aconteceu, e é
    o que ela pediu. Uma tarja laranja de meio minuto sobre um clique que deu
    certo ensina que o botão falha; era o defeito, com o canal certo faltando.

    E O `piloto` PASSA A ANOTAR `("aplicou", "")` em vez de
    `("recusou dizendo", …)` — o desfecho que a régua lê deixa de contradizer o
    disco.
    """
    global_do_perfil, depois, mudou = _gravar_a_forca(ctx, p, uniq, policy, custom)
    # de `profiles/manager._controllers_to_rumble_scales` no `profile.switch`
    # que o :func:`_gravar_a_forca` acabou de fazer. Reenviar o mesmo par já
    _refrescar_o_teste(ctx, p, uniq)
    # `with_controller_rumble`, que envelheceria na quarta regra que o produto
    # acrescentasse.
    mostra, _, propria = _forca_em_vigor(depois, uniq, ctx.state)
    if mostra != policy:
        modelo = (FRASE_DO_AJUSTE_GERAL if policy == "auto"
                  else FRASE_DO_QUE_A_COLUNA_MOSTRA)
        return {"recado": _na_faixa(ctx, uniq,
                                    modelo % _nome_do_degrau(mostra))}
    # clicar "Máximo" não gravava (`with_controller_rumble` limpa o override
    # igual ao global), não acendia (o degrau herdado saía vazio) e não dizia
    # quebraria a COR-04 (`with_controller_rumble`: *"o override guarda só o que
    if not mudou and policy != "custom":
        modelo = (FRASE_JA_E_A_ESCOLHA_DESTA_COLUNA if propria
                  else FRASE_DO_QUE_A_COLUNA_MOSTRA)
        return {"recado": _na_faixa(ctx, uniq,
                                    modelo % _nome_do_degrau(mostra))}
    if _fator_no_motor(global_do_perfil, policy, custom) is None:
        return {"recado": _na_faixa(ctx, uniq, FRASE_DA_MESA_EM_AUTO)}
    return None


def _na_faixa(ctx: Contexto, uniq: str, frase: str) -> str:
    """A frase pronta para a FAIXA: `P2 · …`, com a coluna nomeada."""
    chave = _chave_no_perfil(uniq)
    for c in ctx.mesa:
        dele = str(c.get("uniq") or "")
        if dele != uniq and _chave_no_perfil(dele) != chave:
            continue
        jogador = c.get("jogador")
        if isinstance(jogador, int) and not isinstance(jogador, bool):
            return f"P{jogador}{SEPARADOR_DA_FAIXA}{frase}"
        break
    return frase


def _nome_do_degrau(chave: str) -> str:
    """O nome que ela LÊ no botão, a partir da chave do produto.

    OS RÓTULOS NÃO SE DIGITAM: `rumble_actions.ROTULOS_DO_ORCAMENTO` é a cópia
    pública do `_POLICY_LABEL` que a janela estável usa nos toasts desta mesma
    aba, e o gerador escreve os quatro botões com as mesmas palavras
    (`aba05.FORCA`). Uma terceira lista aqui viraria "Máximo" na tela e "Max" na
    frase no primeiro dia em que alguém renomeasse um degrau.

    **NÃO SE IMPORTA O `aba05` PARA ISTO**, e a razão é medida: o gerador roda
    `_conferir()` no corpo do módulo (`aba05.py`, última linha) — importá-lo
    aqui faria toda carga do pacote LER o desenho da bancada e, num desenho em
    trabalho, levantar `SystemExit` no meio da aba. O dono do rótulo é o
    produto, e o produto não tem esse efeito colateral.

    `custom` NÃO É DEGRAU e por isso não está no mapa do produto: ele é a barra.
    O nome que sai aqui é o que a linha se chama na tela dela, e o gerador
    escreve a mesma palavra no rótulo da linha (`aba05.LINHAS`, "Personalizado").
    """
    from hefesto_dualsense4unix.app.actions.rumble_actions import (
        ROTULOS_DO_ORCAMENTO,
    )

    if chave == "custom":
        return "o que a barra Personalizado marca"
    return ROTULOS_DO_ORCAMENTO.get(chave) or "o degrau da força geral"


def _degraus_que_a_tela_oferece() -> str:
    """Os botões de força que EXISTEM, escritos como ela os lê: "A, B ou C".

    **ELA NASCEU DE UMA FRASE QUE MEDIA O MUNDO DE ONTEM — 05/09/2026.** A
    recusa do :func:`forca` mandava tentar *"em cima de um dos quatro botões
    (Economia, Balanceado, Máximo ou Auto)"*, e desde 05/09 são **três**: o
    `Auto` saiu da tela pela palavra dela, e `aba05.FORCA` tem os outros três. A
    tela mandava ela procurar um botão que não está lá — a mesma família de
    defeito que esta sprint inteira persegue.

    QUANTOS SÃO NÃO SE DIGITA, e por isso a frase não conta: um numeral aqui
    volta a envelhecer no dia seguinte, e foi exatamente assim que "quatro"
    sobreviveu à saída do quarto botão.

    QUAIS SÃO TAMBÉM NÃO SE DIGITAM, e o dono é o produto:
    `app/telas/vibracao.degraus_da_forca()`, na ordem da tela. Até 28/09/2026
    esta função lia `RUMBLE_POLICY_MULT` (`daemon/subsystems/rumble.py`) por
    conta própria, ao lado de um dono que ninguém perguntava
    (A-TELA-PERGUNTA-AO-DONO-01). O gerador do desenho reprova a si mesmo se os
    botões da tela divergirem do mesmo dono (`aba05.py`, o `SystemExit` logo
    abaixo de `FORCA`). Os nomes saem de :func:`_nome_do_degrau`, que os pede a
    `rumble_actions.ROTULOS_DO_ORCAMENTO` — a mesma cópia pública que a janela
    estável usa nos toasts desta aba.

    **NÃO SE IMPORTA O `aba05` PARA ISTO**, pela razão medida em
    :func:`_nome_do_degrau`: o gerador roda `_conferir()` no corpo do módulo, e
    importá-lo aqui faria toda carga do pacote ler o desenho da bancada e, num
    desenho em trabalho, levantar `SystemExit` no meio da aba.
    """
    nomes = [_nome_do_degrau(chave) for chave in _tela.degraus_da_forca()]
    if len(nomes) < 2:
        return "".join(nomes)
    return f"{', '.join(nomes[:-1])} ou {nomes[-1]}"


def _como_a_tela_le(mapa: Any) -> dict[str, Any]:
    """O mapa `controllers` do rascunho na forma CRUA que a pintura lê."""
    if not isinstance(mapa, dict):
        return {}
    fora: dict[str, Any] = {}
    for chave, valor in mapa.items():
        despejar = getattr(valor, "model_dump", None)
        fora[str(chave)] = despejar() if callable(despejar) else (valor or {})
    return fora


def _gravar_a_forca(ctx: Contexto, p: Any, uniq: str, policy: str | None,
                    custom: float | None = None
                    ) -> tuple[Any, dict[str, Any], bool]:
    """Grava a força DAQUELE controle onde a marca do cartão diz, e manda reaplicar.

    Devolve `(global_do_perfil, overrides_depois, mudou)`:

    * o **global de vibração do PERFIL** que serviu de denominador — o
      `draft.rumble`. Quem chama precisa dele para saber se a escolha vira
      escala ou é PULADA (ver :func:`_fator_no_motor`), e relê-lo do disco
      depois seria abrir o mesmo JSON uma segunda vez para responder o que esta
      função já sabia;
    * o mapa `controllers` **depois** da mudança, na forma que a pintura lê
      (:func:`_como_a_tela_le`) — para que quem chama possa conferir, com a
      MESMA função que pinta, o que a coluna vai mostrar;
    * **se alguma coisa foi escrita** — 17/09/2026, VIBRA-ACESA-01. A guarda que
      pula o `profile.switch` quando o mapa não mudou é de 03/09 e sempre soube
      disto; o que faltava era CONTAR. Sem este item, quem chama não distingue
      "gravei o que você pediu" de "não havia o que gravar", e os dois desfechos
      saíam iguais: calados.

    **É A DECISÃO DELA DE 03/09/2026** — *"construir por controle"* — e a
    cadeia inteira já existia (`POR-UNIDADE-01`, 10/08): o que este gesto
    escreve é `controllers[chave].rumble` no PERFIL, e daí em diante o produto
    faz sozinho — `profiles/manager._controllers_to_rumble_scales` converte em
    fator RELATIVO ao global, `ProfileManager.apply` publica o mapa com
    `set_rumble_scales`, e `core/backend_pydualsense._escalar_rumble`
    multiplica o que vai ao motor. Nenhum payload novo, nenhum IPC novo.

    **QUEM DECIDE O QUE VIRA OVERRIDE É O PRODUTO**, e não este arquivo:
    `app/draft_config.with_controller_rumble` já tem as três regras escritas, e
    reescrevê-las aqui seria a segunda cópia que esta casa persegue:

    * igual ao global **não vira override** — a conta do produto descarta o
      fator 1,0, e guardar a opinião só deixaria no disco o que o motor ignora;
    * `policy=None` **limpa**;
    * `auto` **limpa também**, porque o esquema o recusa por unidade (ele
      escala pela bateria do controle PRIMÁRIO) — e o produto chama isso, com
      todas as letras, de *"a leitura honesta do gesto, e não um erro
      silencioso"*.

    O CAMINHO DE DISCO É O DA ABA PERFIS (`pacotes/rodape.salvar`):
    `load_profile` → `DraftConfig.from_profile` → o método acima →
    `to_profile(nome, priority=…)` → `perfil.gravar_e_reaplicar`. A `priority`
    vai junto porque `to_profile` a recebe de fora; sem ela o perfil dela
    perderia a ordem de casamento — é o `BUG-FOOTER-SAVE-DROPS-SECTIONS-01`,
    nomeado no próprio `to_profile`.

    NADA MUDOU = NADA GRAVA, e não é economia: regravar um perfil idêntico
    troca a data do arquivo e faz o daemon reaplicá-lo, e um `profile.switch`
    no meio de uma partida não é de graça. É a mesma guarda do
    `a08_conexoes._com_o_teto`. Ela também é o que torna inócuo o clique DOBRADO
    da barra arrastável — ver :func:`intensidade`.

    A BORDA RECUSA, E A FRASE DELA VAI PARA A TELA. Um `uniq` degenerado
    (`000000…`, o broadcast, o MAC forjado que dois clones compartilham) ou um
    multiplicador fora de `[0, RUMBLE_CUSTOM_MULT_MAX]` faz o esquema levantar
    com a razão escrita — e é ela que sobe como `RuntimeError`, em vez de um
    traço de pydantic. Repetir a lista de recusas aqui a faria envelhecer na
    primeira que o produto acrescentasse.
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig, RumbleDraft

    nome = _perfil.nome_do_ativo(getattr(ctx, "state", None)).strip()
    chave = _chave_no_perfil(uniq)
    if not chave:
        raise RuntimeError(
            "este controle não tem um endereço fixo, e sem ele o perfil não "
            "sabe guardar a força só dele — amanhã ela cairia em outro "
            "aparelho.")

    loader = _perfil._com_o_src()
    if nome:
        try:
            loader.load_profile(nome)
        except Exception as erro:
            raise RuntimeError(f"não consegui ler o perfil {nome!r}: {erro}") from erro

    resultado: dict[str, Any] = {}

    def _com_a_forca(prof: Any) -> Any:
        draft = DraftConfig.from_profile(prof)
        resultado["global"] = draft.rumble
        try:
            # com o nome dele (`custom_mult`, com o `le=RUMBLE_CUSTOM_MULT_MAX`
            pedido = RumbleDraft.model_validate(
                {**draft.rumble.model_dump(), "policy": policy, "custom_mult": custom})
            novo = draft.with_controller_rumble(chave, pedido)
            if novo.source_controllers == draft.source_controllers:
                # "não havia o que gravar" por ele. Ver :func:`_aplicar_a_forca`.
                resultado["depois"] = _como_a_tela_le(draft.source_controllers)
                resultado["mudou"] = False
                return None
            resultado["depois"] = _como_a_tela_le(novo.source_controllers)
            resultado["mudou"] = True
            return novo.to_profile(prof.name, priority=prof.priority)
        except Exception as erro:
            raise RuntimeError(
                f"o produto recusou essa força para este controle: {erro}") from erro

    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    gravar_pelo_gesto("vibracao", nome, _com_a_forca, uniq=chave, origem="interface-nova")
    if resultado["mudou"]:
        _perfil.reaplicar(nome, ctx, p)
    return resultado["global"], resultado["depois"], resultado["mudou"]


@gesto("05-vibracao.html", "forca", grava="_gravar_a_forca")
def forca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Um dos quatro degraus, **daquele controle** — decisão dela, 03/09/2026.

    **FATO SUBSTITUÍDO, e era o parágrafo final deste docstring:** *"a política
    é da MESA, não da coluna … clicar 'Economia' na coluna do P2 muda os
    quatro"*. Era verdade enquanto o gesto chamava `rumble.policy_set`, que não
    aceita `uniq` (`daemon/ipc_handlers.py:3674`). Ela decidiu **construir por
    controle**, e o caminho já existia inteiro pelo PERFIL — ver
    :func:`_gravar_a_forca`. O clique da coluna deixou de mexer nos vizinhos.

    O DEGRAU VEM DO `data-forca`, nunca do rótulo: o HTML carrega a CHAVE do
    produto (`economia`/`balanceado`/`max`/`auto`), e o gerador reprova a si
    mesmo se os degraus divergirem do `RUMBLE_POLICY_MULT` (`aba05.py`).

    O `Auto` NÃO VIRA OVERRIDE, e quem decidiu foi o produto — o esquema o
    recusa por unidade e `with_controller_rumble` traduz o clique em *"limpa o
    override e devolve a peça ao global"*. Na tela isso é: a coluna volta a
    seguir o degrau da mesa. O que não existe mais é o caminho para PÔR a mesa
    em `Auto` a partir daqui, e está declarado em
    :data:`SEM_DONO`\\ ``["forca:auto-da-mesa"]``.

    A RECUSA VIRA `RuntimeError`, e não `ValueError` — 03/09/2026. O contrato
    do piloto é explícito: `RuntimeError` leva a frase ao CARTÃO dela e
    `ValueError` fica no `stderr` de quem lançou a janela
    (`hefesto_vivo._recusou_dizendo`). As duas recusas deste gesto falam com
    quem está com o controle na mão — "clique sem degrau" e "clique sem
    controle" —, então as duas têm de chegar aos olhos dela.

    **E ELE PASSOU A DIZER O QUE ACONTECEU COM A ESCOLHA — 04/09/2026.** Até
    ontem o gesto gravava e voltava calado, e o "Auto" era o caso que mais
    machucava: ele APAGA o override daquela peça (regra do produto, com razão
    escrita), a coluna cai no degrau da mesa um tique depois, e o botão que ela
    clicou **não é o que fica aceso**. A janela estável conta isso desde 25/08
    (`rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL`, RUM-3); esta aba não
    contava. Ver :func:`_aplicar_a_forca`.
    """
    degrau = str(o.get("forca") or "")
    if not degrau:
        raise RuntimeError(
            "Clique em cima de um dos degraus: "
            f"{_degraus_que_a_tela_oferece()}.")
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Clique o degrau dentro da coluna do controle que você quer "
            "mudar.")
    return _aplicar_a_forca(ctx, p, uniq, degrau)


@gesto("05-vibracao.html", "intensidade", grava="_gravar_a_forca")
def intensidade(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra "Personalizado", arrastada: **0 a 200%, e grava na hora.**

    DECISÃO DELA, 03/09/2026, e são as palavras dela. Até ontem esta linha era
    LEITURA: um `<div>` sem `value`, e o gesto `forca` a recusava com um
    `ValueError` que **não chegava à tela** — para ela, arrastar não fazia nada
    e não explicava nada.

    O TETO É DO ESQUEMA (:func:`teto_da_barra`, do `RUMBLE_CUSTOM_MULT_MAX`), e
    o `<input type=range>` do desenho já nasce com `max` igual a ele
    (`aba05._trilho_arrastavel`). Aqui ele não se confere de novo: quem recusa
    o que passa do teto é a BORDA do esquema, e :func:`_gravar_a_forca` sobe a
    frase dela. Uma segunda checagem aqui seria a segunda régua do mesmo
    número, e é ela que envelhece.

    A DIVISÃO POR 100 É A ÚNICA CONTA, e ela é de unidade: a tela fala em
    pontos percentuais (o que ela lê ao lado da barra) e o perfil guarda o
    multiplicador (`custom_mult`, 0 a 2). É a mesma tradução que
    `_pedido_da_politica` faz na volta.

    O CLIQUE CHEGA DUAS VEZES, e é inócuo de propósito. O ouvinte do piloto
    escuta `change` **e** `click`, e soltar o polegar de um `<input type=range>`
    dispara os dois com o MESMO valor. A segunda passagem encontra o perfil já
    com aquele número e :func:`_gravar_a_forca` volta sem gravar — a mesma
    guarda que impede um `profile.switch` no meio de uma partida. Filtrar por
    `evento` aqui seria escrever, neste arquivo, uma regra sobre o ouvinte que
    mora em outro; a guarda que já existe cobre o caso sem saber dele.
    """
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Use a barra dentro da coluna do controle que você quer mudar.")
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            "Arraste o cursor da barra, em vez de clicar no número ao lado.")
    try:
        pontos = round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número de porcentagem"
        ) from erro
    return _aplicar_a_forca(ctx, p, uniq, "custom", custom=pontos / 100)


@gesto("05-vibracao.html", "motor", grava="rumble_motores_set")
def motor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A barra de UM motor daquele controle: **0 a 100, e ela MULTIPLICA o degrau.**"""
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Use a barra dentro da coluna do controle que você quer mudar.")
    lado = str(o.get("lado") or "")
    motor_do_lado = _tela.LADO_PARA_MOTOR.get(lado)
    if not motor_do_lado:
        raise RuntimeError(
            "Use a barra do motor esquerdo ou a do direito.")
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            "Arraste o cursor da barra, em vez de clicar no número ao lado.")
    try:
        pontos = round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número de porcentagem"
        ) from erro
    campo = _tela.MOTOR_PARA_BARRA[motor_do_lado]
    ok, corpo = p.rumble_motores_set(**{campo: pontos}, uniq=uniq)
    if not ok:
        raise RuntimeError(
            "o Hefesto não está rodando — ligue na aba Sistema")
    resposta = corpo if isinstance(corpo, dict) else {}
    if str(resposta.get("status") or "") != "ok":
        raise RuntimeError(
            str(resposta.get("motivo")
                or "o Hefesto não gravou esta barra. Tente de novo."))
    _refrescar_o_teste(ctx, p, uniq, acabou_de_gravar=(lado, pontos))


BARRA_CHEIA = 100

CAMPO_DA_HAPTICA = "haptica_pct"


@gesto("05-vibracao.html", "lado", grava="rumble_motores_set")
def lado(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O interruptor de punho: liga e desliga AQUELE motor, naquele controle."""
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Use o interruptor dentro da coluna do controle que você quer mudar.")
    sigla = str(o.get("lado") or "")
    motor_do_lado = _tela.LADO_PARA_MOTOR.get(sigla)
    if not motor_do_lado:
        raise RuntimeError(
            "Use o interruptor do motor esquerdo ou o do direito.")
    barras = _barras_dos_motores(ctx.state, uniq)
    campo = _tela.MOTOR_PARA_BARRA[motor_do_lado]
    pontos = 0 if barras.get(sigla, 0) > 0 else BARRA_CHEIA
    ok, corpo = p.rumble_motores_set(**{campo: pontos}, uniq=uniq)
    if not ok:
        raise RuntimeError(
            "o Hefesto não está rodando — ligue na aba Sistema")
    resposta = corpo if isinstance(corpo, dict) else {}
    if str(resposta.get("status") or "") != "ok":
        raise RuntimeError(
            str(resposta.get("motivo")
                or "o Hefesto não gravou esta barra. Tente de novo."))
    _refrescar_o_teste(ctx, p, uniq, acabou_de_gravar=(sigla, pontos))


@gesto("05-vibracao.html", "haptica", grava="rumble_motores_set")
def haptica(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A linha «Háptica por áudio»: o trilho grava o ganho, o interruptor liga e desliga.

    UM GESTO para as duas peças da linha, e o que as separa é o `valor`: o
    trilho manda o número dela (0 a 200); o interruptor é um botão, e chega sem
    número. É o par das linhas dos motores, sem campo booleano à parte:
    desligar grava 0, ligar devolve o padrão do dono (`haptica_pct_padrao`, do
    `state_full`), e o aceso é a leitura da barra acima de zero.

    Um gesto próprio, e não o `motor`/`lado` com uma terceira sigla: as réguas
    das barras dos motores contam dois por lugar, com teto 100, e a háptica tem
    teto 200. A faixa quem recusa é a borda do esquema (`HAPTICA_PCT_MAX`).
    """
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Use a barra dentro da coluna do controle que você quer mudar.")
    bruto = str(o.get("valor") or "").strip()
    if bruto:
        try:
            pontos = round(float(bruto))
        except ValueError as erro:
            raise RuntimeError(
                f"a barra mandou {bruto!r}, que não é um número de porcentagem"
            ) from erro
    else:
        atual, _alcanca = _haptica_do_controle(ctx.state, uniq)
        padrao = ctx.state.get("haptica_pct_padrao")
        if not isinstance(padrao, int) or isinstance(padrao, bool):
            from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

            padrao = HAPTICA_PCT_PADRAO
        pontos = 0 if atual > 0 else int(padrao)
    ok, corpo = p.rumble_motores_set(**{CAMPO_DA_HAPTICA: pontos}, uniq=uniq)
    if not ok:
        raise RuntimeError(
            "o Hefesto não está rodando — ligue na aba Sistema")
    resposta = corpo if isinstance(corpo, dict) else {}
    if str(resposta.get("status") or "") != "ok":
        raise RuntimeError(
            str(resposta.get("motivo")
                or "o Hefesto não gravou esta barra. Tente de novo."))
    if uniq in _EM_TESTE_DA_HAPTICA:
        with contextlib.suppress(Exception):
            p.haptica_testar(uniq, True)


@gesto("05-vibracao.html", "testar")
def testar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Testar": AQUELE controle começa a tremer e FICA tremendo até ela parar.

    PEDIDO DELA, 07/09/2026: *"o botão Testar tem que ficar em estado de ligado
    e ir refletindo os slicers ao vivo comigo. E se eu clicar em Parar ele para
    de testar"*. Era um pulso de meio segundo, e o pulso não responde *"quanto é
    40%?"*: para isso a mão precisa estar no controle enquanto a outra arrasta a
    barra. `_refrescar_o_teste` reenvia o par a cada mudança de barra.

    **UM TESTE POR CONTROLE — 03/10/2026, ela: *«vibração e háptico é por cada
    controle e precisam funcionar em independente. hoje se eu clico em um o
    outro controle para de ter o efeito»*.** O pedido leva o `uniq` do controle
    (`rumble_set_checked(..., uniq=...)`) e o serviço guarda um par por
    controle; esta aba não mira mais o seletor global (`controller.target.set`),
    que era o que fazia o serviço inteiro seguir o último clique. O «Testar» de
    um controle só cala o teste da háptica DELE (os dois se excluem no mesmo
    controle, D-0210).

    A CHECADA, e não a crua: a recusa do Modo Nativo vem no CORPO da resposta, e
    foi por não a ler que a aba anunciou "vibração travada" com o motor parado
    (NATIVO-RUMBLE-01). **O par sai reduzido pela barra de cada motor** (ver
    :func:`_par_das_barras`, para a inversão `weak`/`strong`).

    **A mão só volta ao jogo quando ela clicar em Parar**, que é o que ela pediu.
    """
    _minha_vez()
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Clique o botão dentro da coluna do controle que você quer sentir.")
    _calar_o_teste_da_haptica(p, uniq)
    weak, strong = _par_das_barras(ctx, uniq)
    ok, motivo = _resposta(p.rumble_set_checked(weak, strong, uniq=uniq))
    if not ok:
        raise RuntimeError(motivo or "o Hefesto não está rodando — ligue na aba Sistema")
    _EM_TESTE.add(uniq)


@gesto("05-vibracao.html", "parar")
def parar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Parar": corta a vibração DAQUELE controle AGORA e devolve a mão dele ao jogo.

    SÃO DUAS COISAS, e nesta aba elas são um botão só — a dica publicada diz
    *"Parar corta a vibração dele agora e devolve a mão ao jogo"*. O pedido leva
    o `uniq`: o par dos outros controles em teste segue de pé (03/10/2026).

    O NOME DO MÉTODO DO DONO **NÃO** SE ESCREVE AQUI, e não é descuido: ele é o
    `sinal` da linha 177 do `docs/data/paridade-gtk-html.csv`, e
    `scripts/check_paridade_gtk_html.py` reprova quando um sinal declarado
    AUSENTE no lado HTML aparece num arquivo de `interface/`.

    O SEGUNDO PASSO NÃO É ENFEITE: esta aba não tem o botão de devolver, e sem
    ele o "Parar" deixaria o controle num estado MORTO — mudo para o jogo, sem
    caminho de volta na tela. A CHECADA, e não a crua: dentro do Modo Nativo o
    `rumble.stop` não trava silêncio, ele SOLTA o par e diz que não alcança o
    motor que o jogo toca pelo hidraw — NATIVO-RUMBLE-01, segunda metade.
    """
    _minha_vez()
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Clique o botão dentro da coluna do controle que você quer sentir.")
    _calar_o_teste_da_haptica(p, uniq)
    ok, motivo = _resposta(p.rumble_stop_checked(uniq=uniq))
    if not ok:
        raise RuntimeError(motivo or "o Hefesto não está rodando — ligue na aba Sistema")
    p.rumble_passthrough(True, uniq=uniq)
    parar_o_teste(uniq)
    if motivo:
        raise RuntimeError(motivo)


FRASE_SEM_HAPTICA_NESTE_CONTROLE = (
    "este controle não tem a háptica por áudio agora. Veja se ele é um "
    "DualSense e se o som do Hefesto está no ar, na aba Sistema.")


@gesto("05-vibracao.html", "testar-haptica")
def testar_haptica(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Háptica»: o tocador DAQUELE controle toca o par de teste até o «Parar»."""
    _minha_vez()
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "Clique o botão dentro da coluna do controle que você quer sentir.")
    if uniq in _EM_TESTE:
        parar_o_teste(uniq)
        _devolver_ao_jogo(p, uniq)
    ok, corpo = p.haptica_testar(uniq, True)
    if not ok:
        raise RuntimeError("o Hefesto não está rodando — ligue na aba Sistema")
    resposta = corpo if isinstance(corpo, dict) else {}
    if str(resposta.get("status") or "") != "ok":
        raise RuntimeError(str(resposta.get("motivo") or FRASE_SEM_HAPTICA_NESTE_CONTROLE))
    _EM_TESTE_DA_HAPTICA.add(uniq)
    _BATEU_A_HAPTICA_EM[uniq] = _monotonic()


#: `perfil.gravar_e_reaplicar` grava e manda o daemon reaplicar. É a decisão
PONTE = {"chamar", "profile_switch", "rumble_set_checked",
         "rumble_stop", "rumble_stop_checked", "rumble_passthrough",
         "rumble_motores_set", "rumble_policy_set_checked", "haptica_testar"}
METODOS: set[str] = set()


PAGINA = "05-vibracao.html"
PISO_DA_ABA = 5
#: DISCO; o `profile.switch` vem depois. Uma prova que só olhasse a ponte diria
PROVAS = [
    # não pode ficar ligado — o `rumble_stop` e o `rumble_passthrough` mudaram
    {"pagina": PAGINA, "gesto": "testar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("rumble_set_checked", [160, 220], {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "parar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("rumble_stop_checked", [], {"uniq": "aa:bb:cc:00:00:01"}),
               ("rumble_passthrough", [True], {"uniq": "aa:bb:cc:00:00:01"})]},
]

#: tremor não deixa rastro no `state_full`. O `rumble_ff` conta os pedidos do
#: passaram a escrever no PERFIL, e o `state_full` **não publica override por
#: controle nenhum**. Eles TÊM efeito vivo — o `profile.switch` de
#: `state_full` do DAEMON antes e depois do clique (`hefesto_vivo._depois_do_gesto`).
#:   `rumble_passthrough` já voltaram ao que eram. Não há campo a comparar;
#:   faltava passou a morar DENTRO do gesto**: :func:`_aplicar_a_forca` LÊ DE
#: virada do avesso: ele TEM eco, e o eco é honesto.** `state_full.rumble_motores`
#: daemon dela com o DualSense azul no cabo.** O interruptor de punho escreve a
#:     daemon.state_full.rumble_motores  ->  {}
SEM_ECO = ("testar", "parar", "forca", "intensidade", "motor", "lado",
           "testar-haptica")
