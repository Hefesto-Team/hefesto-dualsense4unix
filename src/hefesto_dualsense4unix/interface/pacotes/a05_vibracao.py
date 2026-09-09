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
from typing import Any

# O IMPORT É DE MÓDULO, e não de dentro da função — 01/09/2026. O
# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
# piloto que o lançador abre, e um `from … import` escondido dentro de uma
# função não entra nesse fecho: a camada do produto continuava aparecendo como
# "promessa sem caminho" mesmo depois de eu a ligar.
#
# O `sys.path` já tem o `src/` quando esta linha roda: `pacotes/__init__.py` o
# insere no import do pacote.
from hefesto_dualsense4unix.app.telas import vibracao as _tela

from . import Contexto, registrar
from . import perfil as _perfil

#: O QUE ESTA ABA MOSTRA E ESTE PACOTE NÃO PINTA — com o motivo e o DONO da
#: cura. Estava `{}` até 02/09/2026, e o vazio dizia "nada falta", que é a forma
#: mais barata de mentir numa aba onde quatro coisas faltavam.
#:
#: **ERAM QUATRO E HOJE SÃO DOIS — 03/09/2026.** `degrau-aceso` e `mult-teto`
#: fecharam: o alvo `classe` já existia no pintor desde 02/09, e o que faltava
#: era o ENDEREÇO no desenho mais a EMISSÃO aqui. As duas metades entraram
#: juntas (`aba05._coluna` e `aba05._teto_do_multiplicador`; as chaves `degrau` e
#: `mult-teto` da :func:`pacote`). Mantê-los depois de pintados seria dívida
#: fantasma — a próxima pessoa esperaria por uma cura que já chegou.
#:
#: **E HOJE É UM SÓ — 04/09/2026.** A `barra:motor` e a `forca:auto-da-mesa`
#: fecharam com as decisões dela do mesmo dia; a razão datada de cada uma está
#: no bloco logo abaixo desta lista. O que sobra é o interruptor de punho, que
#: continua sem UMA linha de fonte no produto inteiro.
#:
#: **A `barra:forca` FECHOU — 03/09/2026, decisão dela: *"0 a 200%, e grava na
#: hora."*** A linha do "Personalizado" era um `<div>` sem `value`, e a receita
#: da cura estava escrita na irmã dela abaixo: *"sem um `<input type=range>` no
#: desenho, o clique chega sem quantidade nenhuma"*. O desenho ganhou o
#: `<input>` (`aba05._trilho_arrastavel`) e o gesto :func:`intensidade` grava —
#: no perfil, e só para aquele controle.
SEM_DONO: dict[str, str] = {
    "lado:ligado": "Os oito interruptores de punho são DESENHO, e o produto "
    "concorda por escrito: `app/telas/vibracao.SEM_FONTE['lado:ligado']` — não "
    "há campo em `profiles/schema.py`, nem método de IPC, nem chave no "
    "`state_full`. Fecha: MIGRA-VIBRACAO-06.",
}

# **A `barra:motor` FECHOU — 04/09/2026, e as duas metades entraram no mesmo
# dia, por frentes diferentes.** Ela dizia que faltavam (a) o desenho e (b) *a
# palavra dela*, porque o par `weak`/`strong` viajava JUNTO ao daemon
# (`rumble.set` leva os dois) e uma barra por lado mandaria meio par.
#
# **ELA DECIDIU, E FORA DAS OPÇÕES QUE EU OFERECI:**
#
#     "os slcers do botão esquerdo e direito (forte e  # noqa-acento: citação dela
#      fraco) se multiplicam (interagem com os botões economia, moderado,
#      máximo, se eu tiver 150% do perfil de vibração e as duas linhas
#      estiverem 100 entao a vibração dos 2 será 150%, mas se so a do motor
#      fraco tiver 100 e a outrqa 50% então será 150 em um e 75% no outro
#      entende?"
#
# A barra NÃO é comando: é POLÍTICA, e `efetivo(motor) = degrau x barra(motor)`.
# Com isso as duas deixam de ser meio par de nada — são dois números
# independentes no perfil, e o método que grava um sem o outro nasceu no mesmo
# dia (`rumble.motores.set`, campo omitido não mexe naquela barra). O desenho é
# `aba05._barra_de_motor`, e o gesto é :func:`motor`, aqui embaixo.
#
# **A `forca:auto-da-mesa` FECHOU DUAS VEZES, e a segunda é a que vale.** Em
# 04/09/2026 ela virou a linha de mesa, com o botão que ela escolheu. Em
# 05/09/2026 a linha SAIU inteira, e o `Auto` com ela: *"não é pra ter mesa em
# nada da interface (…) segue os três modos sempre. clicou em perfil de energia
# econômico na aba sistema todos vão pra vibração manual. o resto é
# desnecessário e só polui e deixa difícil entender"*. A economia de bateria já
# tinha dono — o Perfil de Bateria da aba 09 —, e `_effective_mult` aplica
# `min(modo, teto)`. Eram dois donos do mesmo trabalho. Ver `aba05.FORCA`.
# O que a linha diz sobre `auto` por peça continua valendo e continua escrito
# onde vale: no gesto :func:`forca`.
#
# Mantê-las na lista depois de pintadas seria dívida fantasma — a próxima pessoa
# esperaria por uma cura que já chegou.

# **`forca:global-em-auto` FECHOU — 04/09/2026.** Ele dizia *"a escolha fica
# GRAVADA e volta a valer assim que o global sair do `Auto` — o que falta é a
# tela AVISAR"*, e agora a tela avisa em dois tempos: no clique
# (`_aplicar_a_forca`, que leva a frase ao cartão daquele controle) e no TEMPO
# (`_ressalva_da_mesa`, que fica na linha de estado enquanto a condição
# existir). Mantê-lo na lista depois de pintado seria dívida fantasma — a
# próxima pessoa esperaria por uma cura que já chegou.
#
# A FRASE DE TELA NÃO FOI ESCRITA POR ELA, e é o que sobra a decidir: o que está
# no produto hoje é a minha, com o mecanismo explicado em português. Trocar por
# uma dela é uma linha em `FRASE_DA_MESA_EM_AUTO` e outra em
# `_ressalva_da_mesa`.


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
    """`"1"` quando o multiplicador desta coluna bateu no teto da barra; `""` não.

    É o que acende o `Máx` (decisão 11 dela, 03/09/2026). O TETO NÃO SE DIGITA:
    sai de :func:`teto_da_barra`, que o lê do esquema do perfil.

    **O TETO MUDOU DE DONO NO MESMO DIA**, e a linha anterior lia
    `app/telas/vibracao.teto_da_barra()` (150, o degrau `Máximo`). Com a barra
    arrastável até 200, o `Máx` no 150 acenderia com um quarto da barra ainda
    por percorrer — a tela dizendo "não passa daqui" com espaço à frente.

    NÃO SEI NÃO É TETO, e é o único caso que engana: `_barra` devolve `n = "—"`
    com `sabe = ""` quando o daemon não respondeu o multiplicador. Sem a guarda
    do `sabe`, um travessão não numérico cairia no `except` e devolveria `""` —
    o mesmo resultado, por acaso. Com ela, a razão fica escrita: campo sem
    informação não acende nada.
    """
    if not pct.get("sabe"):
        return ""
    try:
        valor = int(str(pct.get("n") or "").rstrip("%"))
    except ValueError:
        return ""
    return "1" if valor >= teto_da_barra() else ""


def _chave_no_perfil(uniq: str) -> str:
    """O `uniq` na grafia com que o PERFIL o guarda — doze hexa, ou `""`.

    O DONO É `core.sysfs_leds.norm_mac`, e é o MESMO que
    `Profile._validate_controllers_keys` usa para canonizar o mapa ao carregar.
    Escrever a normalização de novo aqui produziria duas grafias da mesma regra
    — e o defeito que isso causa é caro e calado: gravar sob `aa:bb:…` quando o
    disco guarda `aabbcc…` cria uma SEGUNDA chave para o mesmo aparelho, e a
    borda do esquema rejeita o perfil INTEIRO com "chaves duplicadas após
    normalização". A escolha dela sumiria, e o arquivo junto.

    `""` é resposta, e quem a trata é quem chama: um controle sem endereço
    estável (a chave de recurso `path:…` do backend) não tem onde guardar uma
    força só dele.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(str(uniq or "").strip()) or ""


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
    return _perfil.ativo(_perfil.nome_do_ativo(getattr(ctx, "state", None)))


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
    # UMA LINHA, E O TAMANHO FOI MEDIDO NA TELA — 04/09/2026. O quadro reserva
    # UMA linha para o estado (`#vib-estado`, no rodapé dele), e a primeira
    # versão desta frase tinha 285 caracteres: a foto mostrou a segunda linha
    # CORTADA no meio de "contra um número que se move". Uma explicação que ela
    # não consegue ler é pior que nenhuma — ocupa o lugar e não informa.
    #
    # O MECANISMO SAIU DAQUI E FICOU NO RECADO DO CLIQUE
    # (:data:`FRASE_DA_MESA_EM_AUTO`), que mora numa caixa que CRESCE. Esta
    # linha diz o fato e o conserto, que é o que serve para quem só passa o
    # olho; o porquê fica onde há espaço para ele.
    # A PALAVRA "MESA" SAIU DA TELA — decisão dela, 06/09/2026: *"O termo sai e
    # coloca-se termos simples pro user comum"* (`docs/A-LINGUA-DESTA-CASA`).
    # Ela sai DESTA linha junto com as três do recado porque as duas metades
    # moram na MESMA faixa desde a 05-Q4: uma dizendo "força da mesa" ao lado de
    # outra dizendo "força geral" seriam dois nomes para o mesmo botão, um
    # embaixo do outro. Na casa continua sendo a mesa (`ctx.mesa`).
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
        # O daemon velho não publica o campo. Sem ele não há padrão a afirmar, e
        # a barra fica onde o desenho a pôs — o mesmo silêncio honesto do resto
        # desta aba quando o daemon não conhece o método.
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
    propria = _forca_propria(overrides, uniq)
    if propria is not None:
        return propria
    return str(state.get("rumble_policy") or ""), state.get("rumble_mult_applied")


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

    O PRODUTO JÁ SABIA, por escrito: `daemon/lifecycle.py:3459-3468` conta que
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


# O `_do_vpad` SAIU EM 09/09/2026, com o único chamador que ele tinha.
#
# Ele achava o bloco `per_vpad` de um jogador para que :func:`_par_das_barras`
# lesse dali `last_weak`/`last_strong` — **duas chaves que aquele bloco nunca
# teve**: elas moram no TOPO do `rumble_ff` (`daemon/ipc_handlers.py:3529`). A
# leitura dava zero em toda execução de produção, e o "Testar" mandava o par
# fixo fizesse ela o que fizesse com as barras. A prosa da VIBRA-MULT-01 em
# :func:`_par_das_barras` tem a medição.
#
# Não é decisão a preservar, é código que respondia sobre outra coisa: sai. Se
# alguém precisar de novo do bloco por jogador, o `per_vpad` continua no
# `state_full` e a busca por `player` cabe em três linhas.


@registrar("05-vibracao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `app/telas/vibracao.pacote_da_mesa` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA, e é o `casa-sabe` que a denunciou:
    `app/telas/vibracao.py` tem oito funções públicas — `pacote_da_mesa`,
    `pacote_da_coluna`, `estado_da_coluna`, `degraus_da_forca`,
    `motores_do_controle`, `teto_da_barra`, `gesto_do_clique` — e **nenhuma
    tinha chamador em produção**. O portão as listava como promessa sem caminho
    desde 31/08/2026.

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
    (`hefesto_vivo.py:183`), e nesta página `forca` é **as duas coisas**: o
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


    # A COR DO PLÁSTICO ENTRA NA MESA AQUI, e o campo é do PRODUTO: a
    # `app/telas/vibracao.pacote_da_coluna` devolve `controle["plastico"]` desde
    # que nasceu, com a nota de que a cor *"vem pronta, e não se resolve aqui,
    # porque quem sabe traduzir colorway em cor é o gerador do desenho"*. Só que
    # NINGUÉM a punha: `mesa_viva.mesa_do_estado` monta o item com `cor` (o slug)
    # e `nome`, e nunca com `plastico` — o campo saía vazio em todo tique desde
    # 01/09/2026. Traduzir slug em `#hex` é uma linha, e ela mora do lado da
    # interface, que é quem conhece `monta.cor_da_zona`.
    mesa = [dict(c, plastico=_plastico_do_item(c)) for c in ctx.mesa]
    bruto = _tela.pacote_da_mesa(ctx.state, mesa, ctx.conectados,
                                 contagem=mesa_viva.texto_da_contagem(ctx.mesa))
    # O MODELO DO DESENHO, POR COLUNA — 03/09/2026, e é a outra metade da lei da
    # identidade. A moldura já vinha do aparelho desde a manhã (o `plastico`); o
    # CONTROLE DESENHADO dentro dela continuava sendo o do mockup.
    #
    # O SLUG É O DO MAPA DELA, e ele já vem pronto: `mesa_viva.CORES` traduz o
    # código de fábrica que o aparelho respondeu no `id` do
    # `docs/data/cores-do-dualsense.csv` (`white`, `galactic-purple`…), que é o
    # mesmo `id` com que o `gerar_cores_do_dualsense.py` escreve
    # `svg[data-colorway="…"]`. Não há tradução nova aqui — só o achatamento, que
    # é o trabalho desta camada.
    #
    # A CHAVE VEM DE `ctx.mesa` E NÃO DE `col`: `pacote_da_coluna` devolve a cor
    # já RESOLVIDA em `#hex` (para a moldura) e joga o slug fora. Repescá-lo aqui
    # custa uma linha; pedi-lo ao produto seria mexer em `app/telas/vibracao`,
    # que é de outro dono e não sabe nada de desenho.
    #
    # VAZIO É RESPOSTA, e é a mais comum na mesa dela: pelo rádio o mapa de
    # canais diz `identidade.cor_do_aparelho = não`, o `LeitorDeCor` guarda
    # `None` e o item chega com `cor = ""`. O alvo `atributo` do pintor APAGA o
    # `data-colorway` nesse caso, e o desenho cai no cinza neutro — o controle
    # sem identidade, que é o que a regra dela pede. Deixar o atributo manteria o
    # Cosmic Red do mockup sobre um aparelho que é outro.
    modelo_por_uniq = {
        str(c.get("uniq") or ""): str(c.get("cor") or "") for c in ctx.mesa
    }
    colunas: dict[str, dict[str, Any]] = {}
    # A FORÇA PASSOU A SER POR CONTROLE — 03/09/2026, decisão dela: *"construir
    # por controle"*. O `bruto` do produto ainda traz o degrau da MESA em
    # `col["forca"]`, porque `pacote_da_coluna` só conhece o `state_full`; quem
    # sabe do override é o PERFIL, e ele mora no disco. Ver
    # :func:`_forca_da_coluna`.
    #
    # UMA LEITURA POR TIQUE, e não uma por coluna: `perfil.ativo` abre o JSON,
    # e quatro colunas o abririam quatro vezes por tique para ler o mesmo mapa.
    # A ressalva da mesa em `Auto` lê o MESMO dicionário — ver `_perfil_ativo`.
    perfil_ativo = _perfil_ativo(ctx)
    bloco_dos_controles = perfil_ativo.get("controllers")
    overrides = bloco_dos_controles if isinstance(bloco_dos_controles, dict) else {}
    for uniq, col in (bruto.get("colunas") or {}).items():
        # O MULTIPLICADOR É O PEDIDO DESTA COLUNA, e não o `rumble_mult_applied`
        # da mesa — as quatro medições que derrubaram aquele campo estão em
        # :func:`_pct_da_coluna`, que é quem faz a conta para a coluna e para a
        # mesa (é dela que a coluna herda quando não tem opinião própria).
        propria = _forca_propria(overrides, uniq)
        politica, custom = (propria if propria is not None else
                            (str(ctx.state.get("rumble_policy") or ""),
                             ctx.state.get("rumble_mult_applied")))
        pct = _pct_da_coluna(politica, custom)
        barras = _barras_dos_motores(ctx.state, uniq)
        plano = {
            "identidade": _sem_marcacao(col.get("identidade", "")),
            # A COR DA MOLDURA, e ela é o campo que a lei da identidade cobra:
            # a borda em volta do desenho passa a ser a cor do controle LIDO, e
            # não a do mockup. Vazio é resposta válida — pelo rádio o mapa diz
            # que a cor não se lê —, e o alvo `plastico` do pintor apaga a
            # variável em vez de inventar um tom.
            "plastico": str(col.get("plastico") or ""),
            # O MODELO DO CONTROLE DESENHADO — o par do `plastico`, e o que
            # fecha a lei da identidade nesta aba. O alvo é `atributo`
            # (`aba05.ENDERECO_DA_COR`), e ele troca o `data-colorway` do
            # `<svg>`; a página publica as dez zonas dos 28 modelos dela, então
            # qualquer um dos 28 pinta. Ver `modelo_por_uniq`, acima.
            "colorway": modelo_por_uniq.get(uniq, ""),
            # O NÚMERO DO MULTIPLICADOR, e não o nome do degrau: o desenho
            # escreve `150%` nesta caixa, ao lado do trilho e do "Máx".
            "mult": pct.get("n", "—"),
            # A POSIÇÃO DO CURSOR DA BARRA, e ela substituiu a LARGURA de um
            # trilho pintado — 03/09/2026. O elemento deixou de ser um `<span>`
            # cuja largura o pintor escrevia e virou um `<input type=range>`:
            # quem move o polegar agora é o `value`, e o alvo é `valor`
            # (`aba05._trilho_arrastavel`).
            #
            # É O NÚMERO CRU (0 a 200), NÃO UMA PORCENTAGEM DE LARGURA. O
            # `pct["w"]` do produto é `100 * valor / teto` — a fração da barra
            # —, e escrevê-lo no `value` de um range que vai a 200 poria o
            # cursor em 75 quando o pedido é 150.
            #
            # VAZIO QUANDO NÃO SE SABE, e o pintor o troca por travessão
            # (`hefesto_vivo.escrever`). Um `<input type=range>` recusa o
            # travessão e cai no valor padrão dele — o meio da escala. Acontece
            # só quando o daemon responde uma política fora das cinco que o
            # produto conhece, e o número ao lado diz `—` no mesmo tique: a
            # tela não afirma o valor, mas o cursor fica num lugar que ninguém
            # escolheu. É o que sobra para ela decidir — desabilitar a barra
            # nesse estado é desenho.
            "mult-pos": (str(pct.get("n", "")).rstrip("%")
                         if pct.get("sabe") else ""),
            # A LARGURA CONTINUA SAINDO, e ela é a PONTE DE PUBLICAÇÃO — 03/09,
            # medido na tela dela e não deduzido. O desenho novo já não tem o
            # `<span class="cheio">`, mas a página que ela ABRE hoje ainda tem:
            # publicar é ato dela, e enquanto a `05-vibracao` estiver em
            # `mockup/DIVERGENCIAS.md` os dois endereços convivem.
            #
            # TIRÁ-LA CUSTOU UMA FOTO: com `mult-pos` sozinho, o clique em
            # "Economia" trocou o número de `100%` para `30%` e o trilho da
            # coluna FICOU ONDE ESTAVA, com a largura que o mockup cravou. É a
            # mentira que esta aba mais persegue — *o olho lê a barra, não o
            # travessão* — e ela apareceu na página publicada, não na bancada.
            #
            # QUANDO ELA SAI: no dia em que a `05-vibracao` deixar a
            # `DIVERGENCIAS.md`, o `<span>` some do produto e esta linha vira
            # endereço que ninguém pinta. Sai junto com a publicação.
            "forca-pct": str(pct.get("w", "")).rstrip("%"),
            # QUAL DEGRAU ESTÁ ACESO — 03/09/2026, e é o campo que fechou a
            # maior dívida desta aba. O valor é a CHAVE do produto
            # (`economia`/`balanceado`/`max`/`auto`), a mesma que o
            # `data-hef-quando` de cada botão carrega; o alvo `classe` do pintor
            # acende quem casar e apaga o resto, sem lista de irmãos.
            #
            # O NOME É `degrau`, NUNCA `forca`: `forca` é `data-papel` dos quatro
            # botões E da linha do "Personalizado", e emiti-lo escrevia
            # `balanceado` DENTRO de dez elementos por tique — o defeito
            # fotografado em 02/09. A régua 6 do `aba05._conferir` reprova o dia
            # em que um nome voltar a ser valor e clique ao mesmo tempo.
            #
            # E ELE PASSOU A SER POR COLUNA — 03/09/2026, decisão dela:
            # *"construir por controle"*. Até ontem esta linha era
            # `col.get("forca")`, o `rumble_policy` da MESA, e as quatro colunas
            # acendiam forçosamente o mesmo degrau — o que era honesto enquanto
            # o clique também era da mesa.
            #
            # AGORA A FONTE É O PERFIL, e a precedência é a do produto:
            # override com `policy` escrita vence, sem ela herda o global. Ver
            # :func:`_forca_da_coluna`. `custom` NÃO acende degrau nenhum: ele
            # não é um dos quatro botões, é a barra — e o `classe` do pintor
            # apaga os quatro quando o valor não casa com nenhum
            # `data-hef-quando`, que é a resposta certa.
            # E ELE SÓ ACENDE QUANDO A FORÇA É DESTA PEÇA — decisão [05] dela,
            # 04/09/2026. Vazio quando a coluna HERDA: o alvo `classe` apaga os
            # quatro, e o único degrau aceso na tela passa a ser o da LINHA DE
            # MESA — que é, literalmente, o que o produto está usando aqui.
            # Antes as duas coisas tinham a mesma cara, e ela não tinha como
            # saber se aquele degrau era escolha dela ou herança.
            "degrau": politica if propria is not None else "",
            # O `Máx` AO LADO DO NÚMERO — decisão 11 dela. Booleano: o alvo
            # `classe` sem `data-hef-quando` acende por si.
            "mult-teto": _no_teto(pct),
        }
        for lado, m in (col.get("motores") or {}).items():
            # OS DOIS VELHOS SÃO A PONTE DE PUBLICAÇÃO, e não redundância: a
            # página que ela ABRE hoje ainda tem a linha de motor como LEITURA
            # (o par 0-255 que o jogo pediu), com estes dois endereços. Tirá-los
            # deixaria o produto dela com dois números congelados no que o
            # mockup cravou — que é a mentira que esta aba mais persegue. Eles
            # saem no dia em que a `05-vibracao` deixar a `DIVERGENCIAS.md`.
            plano[f"motor-{lado}"] = m.get("n", "—")
            plano[f"motor-{lado}-pct"] = str(m.get("w", "")).rstrip("%")
            # O PEDIDO DO JOGO VIRA `title` — 04/09/2026, e é onde a LEITURA foi
            # parar quando a linha virou AJUSTE. O alvo é `atributo`, e quando
            # não há o que dizer o pintor **APAGA** o atributo em vez de escrever
            # travessão: não sobra dica afirmando um pedido que ninguém mediu.
            #
            # **E QUANDO O JOGO NÃO PEDE NADA, ELA DIZ A MULTIPLICAÇÃO** —
            # VIBRA-MULT-01, 09/09/2026. A queixa dela era *"na guia vibração
            # os slicers não estão se multiplicando: motor esquerdo x força de
            # vibração (…) pra cada controle"*, e o que estava errado não era a
            # conta — `gamepad._mults_por_motor` faz `degrau x barra` desde
            # 04/09, com 55 réguas — era **a tela, que não a mostrava em lugar
            # nenhum**. Medido em 09/09 com os quatro na mesa: o P2 imprimia
            # `mult 200%` com os DOIS motores em 0%, e o efetivo era zero.
            #
            # O `mult` CONTINUA SENDO O DEGRAU, e não vira o produto: ele é o
            # que o trilho ao lado move, e trocar o significado do campo faria
            # o número discordar do cursor. O produto vai para onde havia
            # espaço vazio — esta dica, que só falava quando o jogo tremia.
            #
            # A CONTA NÃO SE DIGITA AQUI: `barras[lado]` é lido do
            # `state_full.rumble_motores`, o MESMO mapa que
            # `apply_game_rumble` multiplica, e o degrau sai do `pct` da
            # coluna. Uma multiplicação escrita à mão nesta linha seria a
            # segunda cópia da conta do daemon — e a que envelheceria calada.
            plano[f"motor-{lado}-pedido"] = (
                f'O jogo pediu {m.get("n")} de 255 neste motor agora.'
                if m.get("sabe") else _quanto_multiplica(pct, barras.get(lado)))
            # A BARRA DAQUELE MOTOR — o AJUSTE, de 0 a 100, que MULTIPLICA o
            # degrau da coluna (decisão dela, 04/09/2026). Endereço NOVO de
            # propósito: `motor-e` já quer dizer outra coisa na página publicada.
            #
            # O NÚMERO E A POSIÇÃO SÃO O MESMO VALOR, em dois elementos: o
            # `<input>` recebe o número cru pelo alvo `valor` (é ele que move o
            # polegar) e o `<span class="num">` recebe o mesmo texto. Uma
            # segunda conta para o segundo elemento seria a forma de os dois
            # discordarem na mesma linha.
            plano[f"barra-{lado}"] = str(barras[lado])
            plano[f"barra-{lado}-pct"] = str(barras[lado])
        # O PUNHO QUE TREME — 03/09/2026, e era um FIO SOLTO com as duas pontas
        # já prontas. `app/telas/vibracao.pacote_da_coluna` calcula `treme` por
        # lado desde que nasceu, o CSS que acende o punho existe
        # (`aba05.py`, `.vib .ds-svg .oculta.acesa`) e o desenho já sabe qual
        # grupo do SVG é cada motor. O que faltava era ESTE achatamento: o
        # `treme` era descartado entre o produto e a tela, e o punho aceso na
        # página era o da CENA do mockup — o P1 com o direito aceso e o P2 com o
        # esquerdo, para sempre, com a mesa parada e `vpads == 0`.
        #
        # BOOLEANO, como o `mult-teto`: o alvo `classe` sem `data-hef-quando`
        # acende por si (`hefesto_vivo.py:636`). `""` atravessa como o travessão
        # e APAGA — que é a resposta certa para "ninguém mediu tremor nenhum".
        for lado, treme in (col.get("treme") or {}).items():
            plano[f"treme-{lado}"] = "1" if treme else ""
        # O CAMPO `trava` SAIU EM 05/09/2026, com a faixa "Estado" da grade —
        # decisão dela: *"pq temos uma linha de estado se o estado em vibração
        # sempre vai ser o jogo mandando os input pro controle e a gnt
        # aumentando eles ou diminuindo? remove ela não faz sentido"*.
        #
        # E A MEDIÇÃO DÁ RAZÃO A ELA PELO CAMINHO QUE ELA USA: os dois estados
        # "travada" precisam de `rumble_active` armado, e os DOIS gestos desta
        # aba terminam em `rumble_passthrough(True)` — :func:`testar` (passos 3
        # e 4) e :func:`parar` —, que o solta. Quem arma e deixa armado é a
        # janela GTK ou `hef test rumble`. Nesta tela a faixa dizia sempre "o
        # jogo controla a vibração", menos pelo meio segundo do "Testar".
        #
        # O CAMPO SAI COM O ENDEREÇO: emitir `trava` para uma página que não
        # tem `data-campo="trava"` é escrita em lugar nenhum, calada — o
        # defeito que esta casa persegue. As cinco peças da trava em
        # `app/telas/vibracao.py` saíram no mesmo dia, porque esta aba era a
        # única chamadora delas; a lápide está lá.
        colunas[uniq] = plano
    # A LINHA DO ESTADO — 02/09/2026, e ela é a única coisa que esta aba diz
    # sobre a MESA. Vai por `blocos` e não por campo: o NÚMERO de linhas muda com
    # o estado (um aviso que não se aplica não aparece), e o pintor troca vazio
    # por travessão — um `—` numa linha de alerta afirmaria "não sei" onde a
    # resposta é "não há nada a avisar" (`hefesto_vivo.py:118`).
    #
    # O SELETOR É `#vib-estado`, e ele ESTÁ NA PÁGINA PUBLICADA — medido em
    # 03/09/2026, contando as duas: `id="vib-estado"` aparece uma vez na bancada
    # e uma vez no publicado, e os dois arquivos são byte-idênticos.
    #
    # FATO ERRADO, SUBSTITUÍDO: esta nota dizia que o seletor *"só existe na
    # BANCADA até ela publicar"* e que na publicada o `querySelector` devolvia
    # `null`. Era verdade quando foi escrita e deixou de ser quando ela publicou
    # a aba; enquanto ficou aqui, ensinava que a única linha de texto desta tela
    # não chegava ao produto — e a próxima pessoa a leria como dívida aberta.
    # A frase que ELA vê hoje, no rodapé do quadro, é a que este bloco escreve.
    # A RESSALVA ENTRA NA MESMA LINHA E PELO MESMO EMISSOR — 04/09/2026. Ela é
    # uma tupla `(tom, frase)` como as quatro do produto, e vai para o
    # `html_do_estado` junto com elas: um segundo bloco de HTML nesta tela seria
    # o segundo dono do desenho da linha de estado, que é exatamente o que o
    # docstring de `html_do_estado` existe para impedir.
    #
    # O TOM É `ALERTA` porque a frase diz que algo que ela escolheu NÃO está
    # valendo — é a mesma família do aviso de teto do orçamento, e não a do
    # `INFO` que só explica. Ver :func:`_ressalva_da_mesa`.
    linhas_do_estado = _tela.textos_do_estado(ctx.state)
    ressalva = _ressalva_da_mesa(perfil_ativo, ctx.mesa)
    if ressalva:
        linhas_do_estado.append((_tela.ALERTA, ressalva))
    estado = _tela.html_do_estado(linhas_do_estado)
    return {
        "colunas": colunas,
        # A MESA VOLTOU A EMITIR — 04/09/2026, decisão [05] dela, e com UM campo
        # só. Ele é a LINHA DE MESA (`aba05`, `.vib-mesa`): os quatro degraus do
        # ajuste geral, fora das colunas.
        #
        # A MESA NÃO EMITE CAMPO NENHUM — de novo, e desta vez para ficar.
        # Ela emitiu `degrau-mesa` entre 04/09 e 05/09/2026, enquanto a linha de
        # mesa existiu na tela. Decisão dela em 05/09: *"não é pra ter mesa em
        # nada da interface (…) segue os três modos sempre"*. Sem a linha, não há
        # o que pintar fora das colunas, e um campo emitido para endereço que a
        # página não tem é escrita em lugar nenhum, calada.
        "mesa": {},
        "blocos": {"#vib-estado": estado},
        "sem_dono": dict(SEM_DONO),
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


# `_sem_o_que_dizer` SAIU EM 05/09/2026, com a faixa "Estado" — era a única
# chamadora. O contrato que ela guardava continua vivo onde ainda há linha que
# pode não ter o que dizer: `monta.NADA_A_DIZER` e o `.ressalva:has(.nada)
# {display:none}` da folha das dez, e o mesmo par em `a04_iluminacao` e
# `a06_navegacao`. O que morreu aqui foi a cópia sem chamador, não a regra.


def _sem_marcacao(texto: str) -> str:
    """Tira o HTML do produto: a tela nova escreve `textContent`, não `innerHTML`.

    A camada do produto monta `P1 <span class="pt">•</span> Não sei` porque a
    janela dela injeta como HTML. Escrever isso num `textContent` mostraria as
    tags.

    CORRIGIDO EM 02/09/2026. O que estava aqui trocava CADA TAG por um `·` e
    dizia, no próprio docstring, que *"o separador vira o `·`"* — mas a tag de
    abertura e a de fechamento são DUAS, com o `•` no meio, e o que saía era
    `P1 ·•· Não sei ·•· BT`. Medido contra o daemon dela:

        antes:  'P1 ·•· Não sei ·•· BT'
        depois: 'P1 · Não sei · BT'

    O `·` é o separador que os outros pacotes usam (`a01_jogar.py:50`); o `•` é
    o do desenho, e ele vive dentro da tag que sai. Some com a marcação, e o
    ponto que ela vê é um só.
    """
    import re as _re

    sem_tags = _re.sub(r"<[^>]+>", "", texto)
    return _re.sub(r"\s*•\s*", " · ", sem_tags).strip()




# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando aos DOIS motores
# ---------------------------------------------------------------------------
# O QUE ESTA ABA TEM DE DIFERENTE DAS OUTRAS NOVE, e muda todo gesto daqui:
# **os métodos de vibração não recebem `uniq`.** Medido no censo do daemon em
# 01/09/2026 (`pacotes/daemon.parametros`):
#
#     rumble.set          ('weak', 'strong')      ← nenhum endereço
#     rumble.stop         ()                      ← nenhum endereço
#     rumble.policy_set   ('policy',)             ← nenhum endereço
#     rumble.passthrough  ('enabled',)            ← nenhum endereço
#
# Quem escolhe o controle é o ALVO DE OUTPUT do daemon, e o handler o congela
# junto do par: `daemon/ipc_handlers.py:4913` grava `rumble_active_uniq =
# uniq_do_alvo_de_output(self.controller)`. Sem alvo escolhido o padrão é
# BROADCAST (`ipc_handlers.py:4533`) — os quatro tremeriam, e a coluna, que é o
# endereço desta aba, estaria mentindo. Por isso `_mirar()` vem antes.
#
# A política é a exceção, e não é descuido meu: ela é DA MESA e o produto sabe
# disso — `app/actions/rumble_actions.py:978` escreve *"não há IPC de política
# por unidade, e inventar um seria mecanismo novo"*.
from . import gesto  # noqa: E402

#: O PAR DO TESTE quando ninguém pediu vibração ainda. É o mesmo da janela
#: estável (`app/actions/rumble_actions.py:1078`, `weak = 160` / `strong =
#: 220`), e ele **não tem dono em lugar nenhum** — lá é literal dentro do
#: método, e aqui é literal dentro do módulo. São duas cópias, e a segunda
#: nasce declarada para que a próxima pessoa as ache com um `grep`.
PAR_DE_TESTE = (160, 220)

#: O MEIO SEGUNDO SAIU EM 07/09/2026, com o pulso que ele contava.
#:
#: Ele era `SEGUNDOS_DO_TESTE = 0.5`, e a decisão dela de 30/08 tinha preservado
#: o comportamento e mudado só o rótulo. Em 07/09 ela mudou o COMPORTAMENTO:
#: *"o botão Testar tem que ficar em estado de ligado e ir refletindo os slicers
#: ao vivo comigo. E se eu clicar em Parar ele para de testar"*. Sem pulso não
#: há duração a declarar — quem termina o teste é o "Parar".
#:
#: A DICA DA TELA AINDA PROMETE MEIO SEGUNDO (`aba05.py`), e isso é dívida
#: desta mesma leva: a frase publicada tem de deixar de falar em duração.
_O_PULSO_SAIU = "07/09/2026 — o Testar virou estado; ver `_EM_TESTE`"

#: O TESTE EM CURSO, para que o seguinte o CANCELE — 03/09/2026.
#:
#: A janela estável tem isto e a aba nova não tinha: `_cancel_rumble_test_timer`
#: (`app/actions/rumble_actions.py:1041-1046`) remove a fonte GLib pendente e é
#: chamado no começo do "Testar", do "Aplicar", do "Parar" e do "Devolver" —
#: *"senão o `_rumble_test_stop` pendente desfaria a ação seguinte"*, que é o
#: defeito M6, nomeado lá.
#:
#: AQUI ELE VOLTA PIOR, e por uma diferença desta aba: o meio segundo é um
#: `time.sleep` numa thread própria (o piloto roda todo gesto fora do laço), e
#: `rumble.stop` **não leva endereço** — ele cai no alvo de output DE AGORA. Dois
#: cliques seguidos em colunas diferentes fazem a thread do primeiro acordar
#: depois de o segundo já ter mirado o outro controle: o "Testar" do P2 morre
#: meio segundo antes da hora, e quem o desliga é o clique do P1.
#:
#: O CONTADOR É A CURA MAIS BARATA QUE EXISTE: quem começa um teste leva um
#: número; ao acordar, só solta o silêncio e devolve a mão ao jogo se o número
#: ainda for o dele. Não há temporizador a cancelar, não há thread a matar — o
#: teste que perdeu a vez simplesmente não fala.
#:
#: A GUARDA NÃO DEIXA ESTADO MORTO: o teste que ATROPELA é responsável por
#: parar e devolver o passthrough no fim do próprio meio segundo, e o "Parar"
#: também toma a vez (por isso ele conta). O último a falar sempre devolve a
#: vibração ao jogo, que é a regra desta aba.
_VEZ = [0]

#: QUEM ESTÁ EM TESTE AGORA — o `uniq`, ou `""` quando ninguém está.
#:
#: O "TESTAR" VIROU ESTADO — pedido dela, 07/09/2026: *"o botão Testar tem que
#: ficar em estado de ligado e ir refletindo os slicers ao vivo comigo. E se eu
#: clicar em Parar ele para de testar"*.
#:
#: ATÉ AQUI ELE ERA UM PULSO de :data:`SEGUNDOS_DO_TESTE`: tremia meio segundo e
#: devolvia a mão ao jogo sozinho. Meio segundo serve para responder *"o motor
#: vive?"*; não serve para o que ela está fazendo, que é **ajustar** — arrastar
#: a barra e sentir o que mudou, na mão, sem reclicar a cada arraste.
#:
#: UM SÓ, e não um por controle: `rumble.stop` não leva endereço (cai no alvo de
#: output DE AGORA), então dois testes vivos ao mesmo tempo seriam dois donos
#: para um silêncio só. Começar um teste no P2 encerra o do P1 — que é o que a
#: mão dela faz de qualquer jeito, porque ela tem um par de mãos.
_EM_TESTE = [""]


def em_teste() -> str:
    """O `uniq` em teste agora, ou `""`. Leitura pura, para a tela e a régua."""
    return _EM_TESTE[0]


def parar_o_teste() -> None:
    """Apaga a marca do teste. O ÚNICO jeito de zerá-la de fora.

    DUAS PORTAS PRECISAM DISTO, e as duas são risco de verdade:

    * a suíte, que roda os gestos no MESMO processo — um "Testar" de um caso
      deixava a marca ligada e o arraste de barra do caso seguinte mandava
      vibração que ninguém pediu (medido em 07/09/2026, e a régua da barra
      pegou: *"o gesto chamou ['rumble_motores_set', 'rumble_set_checked']"*);
    * o controle que SAI da mesa com o teste ligado. Sem apagar a marca, o
      próximo arraste de barra tentaria vibrar um aparelho que não está aqui —
      e, pior, `rumble.stop` não leva endereço: o silêncio cairia em quem
      estivesse mirado.
    """
    _EM_TESTE[0] = ""


def _reduzido_pela_barra(valor: int, pontos: int) -> int:
    """`valor` (0-255) reduzido pela barra daquele motor, e nunca fora da faixa.

    A barra é o SEGUNDO fator da conta dela; o primeiro — o degrau — é do
    daemon. Ver :func:`_par_das_barras`, que é quem sabe por que a conta está
    partida em dois.
    """
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
       (`daemon/ipc_handlers.py:3529`), e o que chegava aqui era um bloco de
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
    `strong` o da ESQUERDA (`e`) — `core/backend_pydualsense.py:3840` faz
    `setLeftMotor(eff_strong)`. A tradução não se digita aqui: ela é de
    `app/telas/vibracao.LADO_PARA_MOTOR`, e :func:`_barras_dos_motores` já
    devolve o mapa na língua da tela.

    `acabou_de_gravar` É O ARRASTE QUE AINDA NÃO VOLTOU: o `ctx` de um gesto é
    o tique ANTERIOR à gravação, então reenviar lendo só o `state` faria ela
    sentir o valor de antes do arraste — o "ao vivo" atrasado em um tique. Quem
    grava sabe o que gravou e diz.
    """
    barras = dict(_barras_dos_motores(ctx.state, uniq))
    if acabou_de_gravar is not None:
        lado, pontos = acabou_de_gravar
        if lado in barras:
            barras[lado] = pontos
    weak, strong = PAR_DE_TESTE
    return (
        _reduzido_pela_barra(weak, barras["d"]),
        _reduzido_pela_barra(strong, barras["e"]),
    )


def _refrescar_o_teste(
    ctx: Contexto, p: Any, uniq: str, *,
    acabou_de_gravar: tuple[str, int] | None = None,
) -> None:
    """Reenvia o par ao controle em teste — é o "ao vivo" que ela pediu.

    SÓ FALA SE O TESTE FOR DAQUELE CONTROLE. Arrastar a barra do P2 enquanto o
    P1 é que treme não pode sacudir o P1 com o número do P2 — e também não pode
    ligar o P2, porque ela não mandou testar o P2.

    E É MUDO NO ERRO: quem arrasta a barra está gravando o perfil, e essa
    gravação já respondeu. Uma recusa do reenvio (Modo Nativo, controle que
    caiu) não pode transformar um "gravado" em erro na tela — o que ela perde é
    o tremor, não o dado.
    """
    if not uniq or _EM_TESTE[0] != uniq:
        return
    # E O CONTROLE TEM DE ESTAR AQUI. Um teste ligado num controle que saiu da
    # mesa mandaria o par para o alvo de output DE AGORA, que é outro aparelho.
    if not any(str(c.get("uniq") or "") == uniq for c in ctx.mesa):
        parar_o_teste()
        return
    weak, strong = _par_das_barras(ctx, uniq, acabou_de_gravar=acabou_de_gravar)
    with contextlib.suppress(Exception):
        p.rumble_set_checked(weak, strong)


def _minha_vez() -> int:
    """Toma a vez do teste e devolve o número dela. Quem chega depois vence."""
    _VEZ[0] += 1
    return _VEZ[0]


#: A FRASE DO CONTROLE QUE CAIU ENTRE O CLIQUE E AGORA — e ela tem UM dono
#: desde 05/09/2026, porque tem DOIS lugares de onde subir: :func:`_uniq` (o
#: caminho DELA, pelo piloto) e :func:`_indice` (a guarda contra o broadcast,
#: para qualquer outro chamador). Duas cópias de um texto de tela divergem na
#: primeira edição, e esta casa já pagou por isso.
#:
#: ELA NÃO CITA ENDEREÇO DE RÁDIO, e é contrato: os dois portões de anonimato
#: desta casa existem para que um MAC não saia numa frase de tela — e a frase
#: que ela substituiu (`o controle d4:2f:… não está na mesa agora`) o citava.
FRASE_DO_CONTROLE_QUE_SAIU = (
    "este controle se desligou entre o clique e agora. Sem o lugar dele na "
    "lista do Hefesto não há como mirar só nele — e mandar assim faria "
    "todos tremerem. Espere ele voltar e clique de novo.")


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": sem alvo o `rumble.set` faz BROADCAST, e um "Testar"
    sem dono sacudiria a mesa inteira. O desenho promete o contrário — *"Testar
    faz aquele controle tremer meio segundo"*.

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


def _indice(ctx: Contexto, uniq: str) -> int:
    """A POSIÇÃO daquele controle na lista do daemon — o que o alvo espera.

    `controller.target.set` recebe `index` (0 = primário), **não** `uniq`:
    `daemon/ipc_handlers.py:4196`. O número sai do próprio bloco `controllers`
    (`core/backend_pydualsense.py:5945`, `"index": idx`), que é a posição em
    `list(self._handles)` — o MESMO que cada linha do seletor da janela estável
    carrega (`app/actions/status_actions.py:1585`).

    O RECURSO À POSIÇÃO NA MESA existe porque nem toda entrada publica `index`
    (backend falso, daemon legado); o próprio handler cai nesse recurso em
    `_numero_de_exibicao` (`ipc_handlers.py:596`). E se o controle não estiver
    na mesa, levanta: mirar um lugar vazio deixaria o alvo ANTERIOR de pé, e o
    tremor sairia na coluna errada, calado.

    **A RECUSA VIRA `RuntimeError` — 04/09/2026, e era um dos dois silêncios
    desta aba.** Ela era `ValueError`, e o contrato do piloto é explícito:
    `RuntimeError` leva a frase ao CARTÃO dela e `ValueError` fica no `stderr`
    de quem lançou a janela (`hefesto_vivo._recusou_dizendo` — *"quem clica na
    janela não lê o terminal de quem a lançou"*). **Esta metade vale inteira.**

    **A OUTRA METADE CADUCOU EM 05/09/2026, MEDIDA.** Este parágrafo dizia que
    este era *"o caminho do 'Testar' e do 'Parar' clicados numa coluna cujo
    controle acabou de cair"*, e não é — nem nunca foi, pelo caminho dela. A
    prova é de duas linhas: `_indice` só roda depois de o `uniq` não ser vazio
    (:func:`_mirar`), um `uniq` não vazio veio de `ctx.mesa`, e `ctx.mesa` está
    **contida** em `ctx.conectados` (o piloto filtra `connected` com padrão
    `True`; `app/mesa.py` filtra `connected` sem padrão). Então
    :meth:`Contexto.por_uniq` sempre acha, e este `raise` **não dispara pelo
    clique dela**. A cura de 04/09 foi entregue no ramo errado; o caminho dela é
    o de :func:`_uniq`, que hoje sabe a diferença.

    **E O `raise` FICA.** Ele é a guarda contra o broadcast para qualquer
    chamador que não seja o piloto — um `uniq` fora da mesa devolvendo posição
    faria a mira cair no controle ERRADO, e mirar um lugar vazio deixaria o alvo
    ANTERIOR de pé: o tremor sairia na coluna errada, calado. Inalcançável pelo
    piloto não é o mesmo que enfeite.

    E A FRASE FALA COM QUEM ESTÁ COM O CONTROLE NA MÃO, não com quem programa:
    o `ValueError` de antes dizia `o controle d4:2f:… não está na mesa agora`,
    com o endereço de rádio no meio — e é justamente o que os dois portões de
    anonimato desta casa existem para não deixar sair. Ela é a mesma de
    :func:`_uniq` porque é o mesmo fato, e mora em
    :data:`FRASE_DO_CONTROLE_QUE_SAIU`.
    """
    i = ctx.por_uniq(uniq).get("index")
    if isinstance(i, int) and not isinstance(i, bool):
        return i
    for pos, c in enumerate(ctx.conectados):
        if str(c.get("uniq") or "") == uniq:
            return pos
    raise RuntimeError(FRASE_DO_CONTROLE_QUE_SAIU)


def _resposta(r: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)` seja qual for a forma que a função da ponte devolveu.

    O `ipc_bridge` tem DUAS formas de retorno, e esta aba usa as duas: as
    `*_checked` devolvem o par `(ok, motivo)` — o motivo é a recusa do daemon
    já traduzida em frase de tela — e as outras devolvem só `bool`. Sem este
    normalizador, trocar uma função pela irmã (`rumble_stop` por
    `rumble_stop_checked`) rebentaria no primeiro clique com um `TypeError` de
    desempacotamento, que é o erro mais barato de cometer e o mais caro de ler.
    """
    if isinstance(r, tuple):
        ok = bool(r[0]) if r else False
        motivo = r[1] if len(r) > 1 else None
        return ok, (str(motivo) if motivo else None)
    return bool(r), None


def _mirar(ctx: Contexto, o: dict[str, Any], p: Any) -> str:
    """Aponta o alvo de output para a coluna clicada, e devolve o `uniq`.

    ISTO NÃO É ENFEITE: é a única forma de o botão da coluna falar com AQUELE
    controle, porque `rumble.set` e `rumble.stop` não têm parâmetro de endereço
    (ver o bloco no topo desta seção). O `rumble.stop` mira no mesmo lugar —
    `ipc_handlers.py:5028` lê `uniq_do_alvo_de_output` antes de zerar.

    É o MESMO par de passos da janela estável, só que sem seletor: lá o chip
    manda `controller.target.set` (`app/actions/status_actions.py:2452`) e a
    aba Rumble manda o `rumble.set` depois. Aqui os dois viram um gesto só,
    porque nesta aba o endereço é a coluna — a fita nasce esmaecida de
    propósito (decisão dela, 28/08).

    `controller.target.set` não tem função no `ipc_bridge` (procurei: o módulo
    não cita `target` uma vez), então é o degrau 3 da ponte — e passa pelo
    mesmo `_safe_call`, com o mesmo timeout.

    **A MIRA PASSOU A SER CONFERIDA — 04/09/2026, e é o defeito mais caro que
    esta função guardava.** O `chamar()` devolve `bool` e o retorno era jogado
    fora: com o daemon mudo — ou só lento além dos 250 ms do `_safe_call` —, a
    mira FALHAVA e o gesto seguia adiante para o `rumble.set`, **que sem alvo
    escolhido é BROADCAST** (`ipc_handlers.py:4533`). O "Testar" da coluna do
    P2 sacudia os quatro controles, e a tela não dizia uma palavra. É o
    contrário do que o desenho promete — *"Testar faz aquele controle tremer
    meio segundo"* — e é pior que não fazer nada: faz na mesa inteira.

    RECUSAR É MAIS HONESTO QUE ACERTAR POR ACASO: quando a mira não vai, nada
    é mandado e a frase diz por quê. O par `_minha_vez()`/`_mirar()` continua na
    mesma ordem — quem toma a vez e não consegue mirar não deixa estado morto,
    porque não chegou a pedir vibração nenhuma.

    **AS DUAS RECUSAS SÃO `RuntimeError` — 04/09/2026.** A primeira era
    `ValueError`, e ia para o `stderr` de quem lançou a janela; ver
    :func:`_indice`, que caiu pelo mesmo motivo no mesmo dia.

    **E A PRIMEIRA DELAS DEIXOU DE ACUSAR O CLIQUE DELA — 05/09/2026.** A frase
    *"o clique não disse em qual controle"* cobre um fato só: o clique que veio
    SEM coluna. O outro — a coluna cujo controle caiu entre o clique e agora —
    chegava aqui com o mesmo `""` e levava a mesma frase, e o clique tinha dito
    em qual controle. Quem separa os dois é :func:`_uniq`, que recusa antes com
    :data:`FRASE_DO_CONTROLE_QUE_SAIU`; esta função só vê o clique solto.
    """
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "o clique não disse em qual controle — e sem alvo todos "
            "tremeriam. Clique o botão dentro da coluna do controle que você "
            "quer sentir.")
    if not p.chamar("controller.target.set", index=_indice(ctx, uniq)):
        raise RuntimeError(
            "o Hefesto não aceitou mirar este controle, e sem mira a vibração "
            "iria para todos — então nada foi mandado. Veja se ele "
            "está rodando, na aba Sistema, e tente de novo.")
    return uniq


#: O TETO DE UMA LINHA DA FAIXA, EM CARACTERES — MEDIDO no navegador, não
#: escolhido. A faixa `#vib-estado` reserva UMA linha por frase, e a segunda
#: sai CORTADA: foi o que a foto de 04/09/2026 mostrou com a primeira versão da
#: :func:`_ressalva_da_mesa`, de 285 caracteres.
#:
#: A MEDIÇÃO, no Chrome a 1920x1080, na bancada `mockup/05-vibracao.html`, com
#: a mesma receita do `interface/olhar.py`: o `.est` mede **1104 px** dentro de
#: uma janela de 1180, a altura de UMA linha é **17 px**, e a busca binária
#: pergunta pela ALTURA — duas linhas dão 34.
#:
#: **O TETO EM CARACTERES NÃO É UM NÚMERO SÓ, e por isso ele é medido três
#: vezes.** Quantas letras cabem depende de QUAIS letras são, então a régua
#: mediu com três vocabulários e o teto guardado fica abaixo do MENOR:
#:
#: ==========================  ====================
#: vocabulário                 o último que cabe
#: ==========================  ====================
#: palavras longas da aba      **181**
#: as palavras da própria faixa  189
#: palavras muito curtas         187
#: ==========================  ====================
#:
#: O NÚMERO É 180 E NÃO 181 de propósito: o caractere de folga é o que absorve
#: um `P10` no lugar de um `P2`. Um teto colado no limite medido passa por um
#: pixel — e a segunda linha sai CORTADA, que foi o que a foto de 04/09/2026
#: mostrou com a primeira versão da :func:`_ressalva_da_mesa`, de 285.
TETO_DA_LINHA_DA_FAIXA = 180

#: O SEPARADOR DA FAIXA, e ele é a palavra DELA na `05-Q4`, 05/09/2026:
#: *"a frase entra na faixa que já existe sob a grade, nomeando a coluna
#: (`P2 · voltou ao ajuste geral`) e some logo depois; nada se mexe dentro das
#: colunas"*.
#:
#: POR QUE O RÓTULO PRECISOU ENTRAR NA FRASE: dentro do cartão o endereço era a
#: própria coluna em que o aviso pousava. Fora dela, uma linha embaixo da grade
#: fala de quatro colunas ao mesmo tempo, e sem o `P2` ninguém sabe de qual.
SEPARADOR_DA_FAIXA = " · "

#: O TOM DA LINHA QUE É RECIBO — o quarto, ao lado dos três de
#: `app/telas/vibracao` (:data:`DIZ`, :data:`ALERTA`, :data:`INFO`).
#:
#: VERDE É A COR QUE ESTA CASA JÁ USA PARA O QUE DEU CERTO —
#: `hefesto_vivo.COR_DO_SUCESSO` lê o mesmo `--green` da paleta. Uma quinta cor
#: para o mesmo fato seria a segunda tradução da mesma coisa. E não pode ser o
#: `ALERTA`: laranja sobre um clique que GRAVOU ensina que o botão falha, que é
#: o defeito que a D-01 fechou em 04/09/2026.
#:
#: ELE MORA AQUI, e não em `app/telas/vibracao`: é o único tom que a janela
#: estável não tem — lá o recibo é um toast, não uma linha de card.
TOM_DO_RECIBO = "recibo"

#: O FATO DO AJUSTE GERAL, e são as palavras DELA na `05-Q4`.
#:
#: ELE NÃO É REDIGITADO DO PRODUTO — é a metade do FATO da oração que a janela
#: estável diz no mesmo caso desde 25/08
#: (`rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL`), sem a metade do
#: MECANISMO, que não cabe numa linha (ver :data:`TETO_DA_LINHA_DA_FAIXA`) e
#: mora no `?` do rótulo "Força da vibração".
#:
#: E A RÉGUA PERGUNTA AO DONO: `test_a_frase_da_faixa_diz_o_que_o_produto_diz`
#: exige que esta oração continue DENTRO da do produto. No dia em que o produto
#: renomear o "ajuste geral", a régua reprova em vez de as duas telas passarem a
#: dizer coisas diferentes sobre o mesmo fato.
FATO_DO_AJUSTE_GERAL = "voltou ao ajuste geral"

#: A FRASE DO CASO EM QUE A ESCOLHA FICA GRAVADA E NÃO CHEGA AO MOTOR —
#: 04/09/2026, e ela fecha o :data:`SEM_DONO`\\ ``["forca:global-em-auto"]``, que
#: dizia com todas as letras *"o que falta é a tela AVISAR"*.
#:
#: O MECANISMO, e ele é do produto, não desta aba:
#: `profiles/manager._controllers_to_rumble_scales` PULA a peça — com log
#: `escala_de_vibracao_pulada_base_movel` — quando a força GERAL (a do próprio
#: perfil) está em `auto`, porque o denominador muda com a bateria a cada tique
#: e um fator sobre denominador móvel faria a peça vibrar de forma
#: imprevisível. A escolha fica no disco e volta a valer sozinha assim que a
#: força geral sair do `Auto`.
#:
#: **ELA ENCOLHEU PARA CABER NUMA LINHA — 05-Q4 dela, 06/09/2026.** Tinha 331
#: caracteres, escritos para o CARTÃO, que é uma caixa que CRESCE; a faixa
#: reserva uma linha e corta o resto. O que saiu foi o MECANISMO (*"o Auto muda
#: com a bateria a cada instante…"*), que passou para o `?` do rótulo "Força da
#: vibração"; o que ficou é o FATO e o CONSERTO, a mesma disciplina que a
#: :func:`_ressalva_da_mesa` já seguia.
#:
#: E A PALAVRA "MESA" SAIU DA TELA — decisão dela, 06/09/2026:
#: *"O termo sai e coloca-se termos simples pro user comum"*
#: (`docs/A-LINGUA-DESTA-CASA`). Na tela é **força geral**; na casa continua
#: sendo a mesa.
#:
#: POR QUE ELA NASCE AQUI E NÃO EM `app/telas/vibracao`: este é o único caminho
#: do produto que grava força POR CONTROLE (a janela estável manda
#: `rumble.policy_set`, que é da mesa e não passa por esta conta). Uma frase
#: sobre uma condição que só existe aqui, escrita lá, seria texto sem chamador —
#: e é o que o `casa-sabe` conta como promessa sem caminho.
FRASE_DA_MESA_EM_AUTO = (
    "guardei esta força no perfil, mas ela não chega ao motor enquanto a força "
    "geral estiver em Auto. Tire o Auto e ela volta a valer."
)

#: A FRASE DO CASO EM QUE A TELA VAI MOSTRAR OUTRA COISA — 04/09/2026, e ela
#: encolheu de 267 para caber numa linha da faixa (05-Q4 dela, 06/09/2026).
#:
#: O `%s` é o degrau que a coluna VAI acender, lido do disco depois da gravação.
#: Não é enfeite: sem ele a frase diria *"não ficou o que você pediu"* e deixaria
#: para ela descobrir o quê, olhando três botões.
FRASE_DO_QUE_A_COLUNA_MOSTRA = (
    "esta coluna vai continuar mostrando %s: a sua escolha é igual à força "
    "geral, e só o que difere dela fica guardado no controle."
)

#: A FRASE DO `Auto` QUE DEVOLVE A COLUNA AO AJUSTE GERAL. O `%s` é o degrau que
#: a coluna vai acender.
FRASE_DO_AJUSTE_GERAL = FATO_DO_AJUSTE_GERAL + ", e esta coluna vai mostrar %s."


def _fator_no_motor(global_do_perfil: Any, policy: str | None,
                    custom: float | None) -> float | None:
    """O fator que esta escolha registra contra o global do PERFIL. `None` = nenhum.

    A CONTA É DO PRODUTO E NÃO SE DIGITA AQUI: `profiles/manager.fator_da_unidade`
    é a MESMA função que `_controllers_to_rumble_scales` usa para montar o mapa
    que vai a `set_rumble_scales` — ela foi extraída em 01/09/2026 justamente
    para que a TELA pudesse dizer o que chega ao motor sem reescrever o cálculo.
    Uma segunda conta aqui divergiria no primeiro degrau novo.

    `None` QUER DIZER "NÃO DÁ PARA CALCULAR", e é o que esta aba precisa saber:
    política fora da tabela, ou o global do perfil em `auto` (base móvel). Nos
    dois casos a peça é PULADA no mapa das escalas — a escolha fica no disco e
    não chega ao motor.
    """
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

    OS TRÊS DESFECHOS, e o terceiro é o que ninguém tinha medido:

    1. **a escolha vira escala** (o caso comum) — silêncio, que é o certo: o
       tique seguinte acende o degrau e a barra, e uma frase por clique bem
       sucedido é ruído crônico;
    2. **a mesa está em `Auto`** — o produto PULA a peça, com log e razão
       escrita, e a escolha fica esperando no disco. :data:`FRASE_DA_MESA_EM_AUTO`;
    3. **a coluna vai mostrar OUTRO degrau** — e este só aparece LENDO DE VOLTA.
       `with_controller_rumble` limpa o override em três casos (igual ao global
       do perfil, `policy=None`, `auto`), e a coluna sem override cai no
       `rumble_policy` da MESA (:func:`_forca_da_coluna`). Clicar "Auto" no P2
       apagava o `max` dele e acendia "Balanceado" um tique depois, calado — o
       botão que ela clicou não é o que fica aceso.

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
    global_do_perfil, depois = _gravar_a_forca(ctx, p, uniq, policy, custom)
    # E O TESTE VIVO SEGUE O DEGRAU — E A CONTA TEM DOIS DONOS (09/09/2026,
    # VIBRA-MULT-01). O que a mão dela sente é `base x barra x degrau`, e cada
    # fator é aplicado por um lado diferente: a BARRA é a metade DESTA ABA,
    # aplicada em :func:`_par_das_barras` antes de o par sair; o DEGRAU — a
    # força e a intensidade — é a metade do DAEMON, aplicada sobre o par que
    # chega. Mudar o degrau com o teste ligado tem de chegar à mão dela igual
    # ao arraste da barra: é o mesmo "ao vivo", por caminhos diferentes.
    #
    # ATÉ 09/09/2026 ESTA LINHA DIZIA O CONTRÁRIO DO QUE O PRODUTO FAZIA —
    # *"a força e a intensidade multiplicam as barras"* —, e ela é de 07/09. O
    # caminho do rumble FIXADO aplicava só o degrau; a barra não chegava ao
    # motor em lugar nenhum, e um motor posto em ZERO tremia igual ao outro.
    # A medição está em :func:`_par_das_barras`.
    #
    # AQUI NÃO VAI `acabou_de_gravar`, e a diferença é de ANDAR (09/09/2026): a
    # barra é o fator que ESTA aba aplica ao par (:func:`_par_das_barras`), e
    # por isso ela precisa do valor recém-gravado; o degrau é aplicado pelo
    # daemon e pelo backend sobre o par que chega — a escala por controle sai
    # de `profiles/manager._controllers_to_rumble_scales` no `profile.switch`
    # que o :func:`_gravar_a_forca` acabou de fazer. Reenviar o mesmo par já
    # basta: quem o escala é o outro lado, com o número novo.
    _refrescar_o_teste(ctx, p, uniq)
    # A COLUNA DE DEPOIS, lida PELA MESMA FUNÇÃO QUE PINTA. É o ponto inteiro:
    # se o que sai daqui não bate com o que ela pediu, é literalmente o que a
    # coluna vai mostrar no tique seguinte — não uma segunda cópia das regras do
    # `with_controller_rumble`, que envelheceria na quarta regra que o produto
    # acrescentasse.
    #
    # O MAPA VEM DO OBJETO QUE FOI GRAVADO, e não de um segundo `open()` do
    # JSON. Reler o disco aqui custaria uma leitura a mais por clique e abriria
    # uma corrida com o `gravar_e_reaplicar` que acabou de escrever — e o
    # `source_controllers` do rascunho É o que foi para o arquivo.
    mostra, _ = _forca_da_coluna(depois, uniq, ctx.state)
    if mostra != policy:
        modelo = (FRASE_DO_AJUSTE_GERAL if policy == "auto"
                  else FRASE_DO_QUE_A_COLUNA_MOSTRA)
        return {"recado": _na_faixa(ctx, uniq,
                                    modelo % _nome_do_degrau(mostra))}
    if _fator_no_motor(global_do_perfil, policy, custom) is None:
        return {"recado": _na_faixa(ctx, uniq, FRASE_DA_MESA_EM_AUTO)}
    return None


def _na_faixa(ctx: Contexto, uniq: str, frase: str) -> str:
    """A frase pronta para a FAIXA: `P2 · …`, com a coluna nomeada.

    **05-Q4 dela, 05/09/2026** — *"a frase entra na faixa que já existe sob a
    grade, nomeando a coluna (`P2 · voltou ao ajuste geral`) e some logo depois;
    nada se mexe dentro das colunas"*.

    O NÚMERO NÃO SE DIGITA: ele é o `jogador` do item de mesa, o MESMO que a
    coluna já mostra no rótulo dela (`aba05`, `P{c["jogador"]}`). Contar a
    posição na lista aqui produziria um segundo número para a mesma coluna, e
    os dois divergem no dia em que um controle cair — que é o defeito de
    identidade que o `_recados_para_a_tela` do piloto já paga.

    SEM COLUNA, SEM PREFIXO. Um `uniq` que a mesa deste tique não conhece não
    tem coluna na tela, e escrever `P?` seria a tela afirmando um endereço que
    ela não sabe. Não acontece pelo caminho dela — :func:`_uniq` recusa antes,
    com :data:`FRASE_DO_CONTROLE_QUE_SAIU` —, e o `""` é a resposta honesta
    para quem chegar por outro.

    A GRAFIA DO `uniq` NÃO SE ASSUME: o clique traz a que o piloto resolveu
    contra a mesa, e um perfil editado à mão traz `aa:bb:…` onde o disco guarda
    doze hexa. A comparação é pelas DUAS, como :func:`_forca_da_coluna`.
    """
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
    # "MESA" SAIU DA TELA — 06/09/2026 (`docs/A-LINGUA-DESTA-CASA`). Este é o
    # recurso para uma chave que o produto tenha e os rótulos não conheçam, e
    # ele entra na MESMA frase da faixa que as outras: dois nomes para o mesmo
    # botão na mesma linha é o que a decisão dela existe para matar.
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

    QUAIS SÃO TAMBÉM NÃO SE DIGITAM. O conjunto é `RUMBLE_POLICY_MULT`
    (`daemon/subsystems/rumble.py`) — o produto —, e o gerador do desenho
    reprova a si mesmo se os botões da tela divergirem dele
    (`aba05.py`, o `SystemExit` logo abaixo de `FORCA`). Os nomes saem de
    :func:`_nome_do_degrau`, que os pede a `rumble_actions.ROTULOS_DO_ORCAMENTO`
    — a mesma cópia pública que a janela estável usa nos toasts desta aba.

    **NÃO SE IMPORTA O `aba05` PARA ISTO**, pela razão medida em
    :func:`_nome_do_degrau`: o gerador roda `_conferir()` no corpo do módulo, e
    importá-lo aqui faria toda carga do pacote ler o desenho da bancada e, num
    desenho em trabalho, levantar `SystemExit` no meio da aba.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import (
        RUMBLE_POLICY_MULT,
    )

    nomes = [_nome_do_degrau(chave) for chave in RUMBLE_POLICY_MULT]
    if len(nomes) < 2:
        return "".join(nomes)
    return f"{', '.join(nomes[:-1])} ou {nomes[-1]}"


def _como_a_tela_le(mapa: Any) -> dict[str, Any]:
    """O mapa `controllers` do rascunho na forma CRUA que a pintura lê.

    `DraftConfig.source_controllers` guarda os `ControllerOverrides` do pydantic
    — que é o que vai para o disco —, e :func:`_forca_da_coluna` lê dicionários,
    porque a pintura os recebe do JSON por `pacotes/perfil.ativo`. Esta é a
    tradução entre as duas formas, e ela existe para que a conferência da volta
    use A MESMA função que pinta a coluna, em vez de uma segunda leitura das
    regras do produto.
    """
    if not isinstance(mapa, dict):
        return {}
    fora: dict[str, Any] = {}
    for chave, valor in mapa.items():
        despejar = getattr(valor, "model_dump", None)
        fora[str(chave)] = despejar() if callable(despejar) else (valor or {})
    return fora


def _gravar_a_forca(ctx: Contexto, p: Any, uniq: str, policy: str | None,
                    custom: float | None = None) -> tuple[Any, dict[str, Any]]:
    """Grava a força DAQUELE controle no perfil ativo, e manda reaplicar.

    Devolve `(global_do_perfil, overrides_depois)`:

    * o **global de vibração do PERFIL** que serviu de denominador — o
      `draft.rumble`. Quem chama precisa dele para saber se a escolha vira
      escala ou é PULADA (ver :func:`_fator_no_motor`), e relê-lo do disco
      depois seria abrir o mesmo JSON uma segunda vez para responder o que esta
      função já sabia;
    * o mapa `controllers` **depois** da mudança, na forma que a pintura lê
      (:func:`_como_a_tela_le`) — para que quem chama possa conferir, com a
      MESMA função que pinta, o que a coluna vai mostrar.

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

    nome = str((getattr(ctx, "state", None) or {}).get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e a força da vibração de um controle é "
            "do PERFIL — não de todos. Escolha um perfil na aba Perfis e tente "
            "de novo.")
    chave = _chave_no_perfil(uniq)
    if not chave:
        raise RuntimeError(
            "este controle não tem endereço fixo de doze hexa, e sem ele não há "
            "chave no perfil para guardar a força só dele. Um controle sem "
            "endereço estável muda de nome a cada conexão, e a escolha cairia "
            "num aparelho diferente do que você está vendo.")

    loader = _perfil._com_o_src()
    try:
        prof = loader.load_profile(nome)
    except Exception as erro:
        raise RuntimeError(f"não consegui ler o perfil {nome!r}: {erro}") from erro

    draft = DraftConfig.from_profile(prof)
    try:
        # `model_validate` E NÃO `model_copy`, e a razão é a FRASE, não a
        # segurança: o `model_copy` do pydantic não valida, mas a borda de baixo
        # (`ControllerRumbleOverride`) pega o mesmo número um passo adiante —
        # medido com a cura arrancada, e o teste continuou verde. O que se ganha
        # aqui é a recusa mais PERTO do valor, e por isso com o nome dele
        # (`custom_mult`, com o `le=RUMBLE_CUSTOM_MULT_MAX` que o declara) em
        # vez do nome de um campo interno de `Profile`.
        pedido = RumbleDraft.model_validate(
            {**draft.rumble.model_dump(), "policy": policy, "custom_mult": custom})
        novo = draft.with_controller_rumble(chave, pedido)
        if novo.source_controllers == draft.source_controllers:
            return draft.rumble, _como_a_tela_le(draft.source_controllers)
        adiante = novo.to_profile(nome, priority=prof.priority)
    except Exception as erro:
        raise RuntimeError(
            f"o produto recusou essa força para este controle: {erro}") from erro
    _perfil.gravar_e_reaplicar(adiante, ctx, p)
    return draft.rumble, _como_a_tela_le(novo.source_controllers)


@gesto("05-vibracao.html", "forca", grava="_gravar_a_forca")
def forca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Um dos quatro degraus, **daquele controle** — decisão dela, 03/09/2026.

    **FATO SUBSTITUÍDO, e era o parágrafo final deste docstring:** *"a política
    é da MESA, não da coluna … clicar 'Economia' na coluna do P2 muda os
    quatro"*. Era verdade enquanto o gesto chamava `rumble.policy_set`, que não
    aceita `uniq` (`daemon/ipc_handlers.py:5071`). Ela decidiu **construir por
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
            "este clique não disse qual degrau — tente de novo em cima de um "
            f"dos botões ({_degraus_que_a_tela_oferece()}).")
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "o clique não disse em qual controle — e a força agora é de cada "
            "um. Clique o degrau dentro da coluna do controle que você quer "
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
            "o arraste não disse em qual controle — a intensidade agora é de "
            "cada um. Use a barra dentro da coluna do controle que você quer "
            "mudar.")
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            "a barra não mandou número nenhum. Arraste o cursor dela em vez de "
            "clicar no rótulo ao lado.")
    try:
        pontos = round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número de porcentagem"
        ) from erro
    return _aplicar_a_forca(ctx, p, uniq, "custom", custom=pontos / 100)


@gesto("05-vibracao.html", "motor", grava="rumble_motores_set")
def motor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A barra de UM motor daquele controle: **0 a 100, e ela MULTIPLICA o degrau.**

    DECISÃO DELA, 04/09/2026, e ela veio FORA das três opções que eu ofereci —
    eu perguntei se a barra mandava o par `rumble.set` agora ou se virava
    leitura, e as duas perguntas estavam erradas:

        "os slcers do botão esquerdo e direito (forte e  # noqa-acento: citação dela
         fraco) se multiplicam (…) se eu tiver 150% do perfil de vibração e as
         duas linhas estiverem 100 entao a vibração dos 2 será 150%, mas se so
         a do motor fraco tiver 100 e a outrqa 50% então será 150 em um e 75%
         no outro entende?"

    `efetivo(motor) = degrau(coluna) x barra(motor)`, e a conta mora num lugar
    só, do lado do daemon (`gamepad._mults_por_motor`). Este gesto não a
    reproduz — ele grava o segundo fator.

    **UMA BARRA POR VEZ, e é o contrato do método:** `rumble.motores.set` deixa
    intacta a barra cujo campo for omitido. É o caso dela por escrito — as duas
    são independentes —, e é o que impede um arraste no punho esquerdo de
    reescrever o direito com o número que a TELA mostrava.

    A TRADUÇÃO `lado → campo` NÃO SE DIGITA: `e`/`d` é a língua da tela,
    `strong`/`weak` é a do protocolo e `forte_pct`/`fraco_pct` é a do IPC. As
    duas pontes têm dono (`app/telas/vibracao.LADO_PARA_MOTOR` e
    `.MOTOR_PARA_BARRA`), e a armadilha deste assunto é que **`weak` é o motor
    da DIREITA** — escrever a tradução aqui é como ela se inverte calada.

    A FAIXA NÃO SE CONFERE AQUI, pela mesma razão da :func:`intensidade`: quem
    recusa fora de 0-100 é a BORDA do esquema, com a frase que explica, e o
    corpo da resposta a traz pronta. Uma segunda régua do mesmo número é a que
    envelhece.

    **O `0` É ESCOLHA VÁLIDA** — *"este motor não treme neste perfil"* —, e por
    isso o teste é `bruto == ""` e não `not pontos`. Confundir "zero" com "não
    sei" é o defeito que a `MIGRA-VIBRACAO-01` nomeia.

    O CLIQUE CHEGA DUAS VEZES, como na :func:`intensidade` (o ouvinte escuta
    `change` **e** `click`), e é inócuo pela mesma guarda — do outro lado: o
    handler responde `gravado: False` quando nada mudou, sem regravar o perfil.
    """
    uniq = _uniq(o)
    if not uniq:
        raise RuntimeError(
            "o arraste não disse em qual controle — cada controle tem as suas "
            "duas barras de motor. Use a barra dentro da coluna do controle que "
            "você quer mudar.")
    lado = str(o.get("lado") or "")
    motor_do_lado = _tela.LADO_PARA_MOTOR.get(lado)
    if not motor_do_lado:
        raise RuntimeError(
            "este arraste não disse qual punho — tente de novo na barra do "
            "motor esquerdo ou na do direito.")
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            "a barra não mandou número nenhum. Arraste o cursor dela em vez de "
            "clicar no rótulo ao lado.")
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
    # A RECUSA VEM NO CORPO, e não como erro JSON-RPC — é a lição do
    # NATIVO-RUMBLE-01, e a ponte devolve o corpo inteiro de propósito
    # (`app/ipc_bridge.rumble_motores_set`, "invólucro que estreita faz a tela
    # re-deduzir o que o daemon já sabia"). Ler só o `ok` anunciaria "gravado"
    # sobre um `sem_perfil`.
    resposta = corpo if isinstance(corpo, dict) else {}
    if str(resposta.get("status") or "") != "ok":
        raise RuntimeError(
            str(resposta.get("motivo")
                or "o Hefesto não aceitou gravar esta barra, e não disse por quê"))
    # E O TESTE VIVO SEGUE O ARRASTE — o "ao vivo" que ela pediu. Depois da
    # gravação, nunca antes: o que ela sente tem de ser o que ficou gravado.
    #
    # O `acabou_de_gravar` NÃO É ENFEITE (09/09/2026): o `ctx` deste gesto é o
    # tique ANTERIOR ao `rumble.motores.set` que acabou de responder, então
    # `state.rumble_motores` ainda traz a barra VELHA. Sem dizer o que gravou,
    # o reenvio faria a mão dela sentir o valor de antes do arraste — um "ao
    # vivo" atrasado em um tique, que é a forma mais convincente de um ajuste
    # parecer que não funciona.
    _refrescar_o_teste(ctx, p, uniq, acabou_de_gravar=(lado, pontos))


@gesto("05-vibracao.html", "testar")
def testar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Testar": AQUELE controle começa a tremer e FICA tremendo até ela parar.

    PEDIDO DELA, 07/09/2026, com os quatro na bancada: *"o botão Testar tem que
    ficar em estado de ligado e ir refletindo os slicers ao vivo comigo. E se eu
    clicar em Parar ele para de testar"*.

    ERA UM PULSO DE MEIO SEGUNDO, e o pulso responde a outra pergunta. *"O motor
    vive?"* se responde com meio segundo; *"quanto é 40%?"* não — para isso a
    mão precisa estar no controle enquanto a outra arrasta a barra. Com o pulso,
    cada arraste custava um reclique e o que ela sentia era sempre o valor
    ANTERIOR ao que estava vendo.

    DUAS CHAMADAS, e o que sumiu é o terceiro e o quarto passo:

    1. `controller.target.set` — sem ele o par iria para os quatro (`_mirar`);
    2. `rumble_set_checked` — a mesma função do `on_rumble_test_500ms`
       (`app/actions/rumble_actions.py:1073`). A CHECADA, e não a crua: a
       recusa do Modo Nativo vem no CORPO da resposta, não como erro JSON-RPC
       (`app/ipc_bridge.py:597`), e foi por não a ler que a aba anunciou
       "vibração travada" com o motor parado — NATIVO-RUMBLE-01.

    O `rumble_stop` E O `rumble_passthrough(True)` NÃO SUMIRAM DO PRODUTO —
    mudaram de dono. Eles são o "Parar", e continuam sendo os dois passos
    exatos do `_rumble_test_stop` (`rumble_actions.py:1279-1280`): parar sozinho
    fixa `(0, 0)` e o laço do daemon re-afirma o silêncio, e o jogo ficaria mudo
    depois de um teste (SPRINT-GAME-RUMBLE-01). **A mão só volta ao jogo quando
    ela clicar em Parar** — que é exatamente o que ela pediu, e é o preço
    honesto de um teste que fica ligado.

    OS VALORES SÃO OS DAS BARRAS DAQUELA COLUNA, e agora eles seguem o arraste:
    `_refrescar_o_teste` reenvia o par a cada mudança de barra, de intensidade e
    de força, enquanto o teste for DESTE controle. Ver `_par_das_barras` para a
    inversão `weak`/`strong`, que é a armadilha deste assunto.

    **E O PAR SAI REDUZIDO PELA BARRA DE CADA MOTOR — 09/09/2026,
    VIBRA-MULT-01.** Até esta manhã a frase acima era falsa em duas camadas: a
    leitura das barras batia em chave inexistente e o caminho do rumble FIXADO
    não aplica a barra em lugar nenhum. Um motor posto em ZERO tremia igual ao
    outro no "Testar", que é a queixa dela — *"os slicers não estão se
    multiplicando"*. A medição e o que ficou em aberto estão em
    :func:`_par_das_barras`.
    """
    _minha_vez()
    uniq = _mirar(ctx, o, p)
    weak, strong = _par_das_barras(ctx, uniq)
    ok, motivo = _resposta(p.rumble_set_checked(weak, strong))
    if not ok:
        raise RuntimeError(motivo or "o Hefesto não está rodando — ligue na aba Sistema")
    # ELE FICA LIGADO — ver :data:`_EM_TESTE`. Não há `sleep` nem parada
    # automática: quem para é ela, no "Parar". O meio segundo servia para
    # responder "o motor vive?"; ela está AJUSTANDO, e ajustar pede o tremor
    # ligado enquanto a mão arrasta a barra.
    _EM_TESTE[0] = uniq


@gesto("05-vibracao.html", "parar")
def parar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Parar": corta a vibração daquele controle AGORA e devolve a mão ao jogo.

    SÃO DUAS COISAS, e nesta aba elas são um botão só — a dica publicada diz
    isso com todas as letras: *"Parar corta a vibração dele agora e devolve a
    mão ao jogo"*. Na janela estável são DOIS botões: o "Parar"
    (`rumble_stop_checked`, que FIXA `(0, 0)` e manda o laço re-afirmar o
    silêncio) e o "Devolver ao jogo" (`rumble_passthrough(True)`,
    `rumble_actions.py:1157`).

    O NOME DO MÉTODO DO DONO **NÃO** SE ESCREVE AQUI, e não é descuido: ele é o
    `sinal` da linha 177 do `docs/data/paridade-gtk-html.csv`, e
    `scripts/check_paridade_gtk_html.py` reprova quando um sinal declarado
    AUSENTE no lado HTML aparece num arquivo de `interface/`. Escrevê-lo em
    prosa faria a régua anunciar dívida fechada por causa de um comentário —
    medido em 06/09/2026, com o portão vermelho na mão.

    O SEGUNDO PASSO NÃO É ENFEITE: esta aba não tem o botão de devolver, e sem
    ele o "Parar" deixaria o controle num estado MORTO — mudo para o jogo, sem
    caminho de volta na tela. É a regra da casa: *nada fica num estado morto*.

    A CHECADA, e não a crua: dentro do Modo Nativo o `rumble.stop` não trava
    silêncio, ele SOLTA o par e diz que não alcança o motor que o jogo toca
    pelo hidraw (`ipc_handlers.py:4543`). Anunciar "parada" ali seria prometer
    o que não aconteceu — NATIVO-RUMBLE-01, segunda metade. O motivo sobe como
    erro porque é o único canal que esta aba tem hoje; um recado de tela para
    ele ainda não existe, e está no relato.
    """
    # O "PARAR" TAMBÉM TOMA A VEZ — é o equivalente da chamada que a janela
    # estável faz em `on_rumble_stop` (`rumble_actions.py:1129`). Sem ela, um
    # "Testar" ainda dormindo acordaria depois deste "Parar" e mandaria
    # `rumble.stop` no alvo de agora: parar o P1 apagaria a vibração do P2.
    _minha_vez()
    _mirar(ctx, o, p)
    ok, motivo = _resposta(p.rumble_stop_checked())
    if not ok:
        # O `motivo` É A RECUSA DO DAEMON JÁ TRADUZIDA EM FRASE DE TELA, e é
        # para isso que a `_checked` existe (:func:`_resposta`). Até 05/09/2026
        # ele era lido e jogado fora aqui, e a tela afirmava uma causa que
        # ninguém mediu — "o Hefesto não está rodando" sobre um daemon vivo que
        # recusou por outra coisa. A irmã 41 linhas acima (:func:`testar`) já
        # fazia o certo, com o mesmo `or`: o palpite é o RECURSO, não a resposta.
        raise RuntimeError(motivo or "o Hefesto não está rodando — ligue na aba Sistema")
    p.rumble_passthrough(True)
    # O TESTE DESLIGA AQUI — ver `parar_o_teste`. Antes do `raise` de
    # propósito: mesmo que o passthrough reclame, o teste ACABOU (o
    # `rumble_stop` já fixou o silêncio), e deixar a marca ligada faria o
    # próximo arraste de barra ressuscitar o tremor de um teste que ela parou.
    parar_o_teste()
    if motivo:
        raise RuntimeError(motivo)


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
#:
#: `rumble_policy_set_checked` SAIU EM 03/09/2026, e `profile_switch` entrou no
#: lugar dele: a força deixou de ir por IPC global e passa a ir pelo PERFIL —
#: `perfil.gravar_e_reaplicar` grava e manda o daemon reaplicar. É a decisão
#: dela de construir por controle, vista do lado da ponte.
#: **DOIS ENTRARAM EM 04/09/2026**, e os dois com decisão dela por trás:
#: `rumble_motores_set` (a barra de cada motor, :func:`motor`) e
#: `rumble_policy_set_checked` — que voltou em 04/09 como porta da linha de mesa
#: e ficou SEM CHAMADOR nesta aba em 05/09, quando a linha saiu. Ele continua na
#: `PONTE` porque a janela GTK o usa e porque tirá-lo daqui não tiraria um método
#: do produto — só esconderia da régua que esta aba não o chama mais.
PONTE = {"chamar", "profile_switch", "rumble_set_checked",
         "rumble_stop", "rumble_stop_checked", "rumble_passthrough",
         "rumble_motores_set", "rumble_policy_set_checked"}
#: O ÚNICO MÉTODO CRU, e ele é o que dá endereço aos outros quatro.
METODOS = {"controller.target.set"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, não no teste.
PAGINA = "05-vibracao.html"
#: **O PISO CAIU DE 6 PARA 5 EM 05/09/2026, E A QUEDA É DECLARADA.** A régua
#: diz que o piso SÓ SOBE, e ela está certa: uma queda silenciosa não aparece
#: na tela — o clique simplesmente deixa de fazer alguma coisa. Esta não é
#: silenciosa, e não é gesto que parou de funcionar: é gesto que **deixou de
#: existir por decisão dela**. O `forca-mesa` era o único dono da linha de
#: mesa, e a palavra foi *"não é pra ter mesa em nada da interface (…) segue os
#: três modos sempre"*. A linha saiu inteira — CSS, HTML e a régua 15 do
#: desenho — e o gesto saiu com ela. Restam CINCO donos nesta aba.
#:
#: Se este número cair de novo sem um parágrafo como este ao lado, a queda é
#: defeito, não decisão.
PISO_DA_ABA = 5
#: `forca`, `intensidade` E `motor` NÃO TÊM LINHA AQUI — e a razão é a mesma
#: que tirou o `teto-da-vibracao` das provas da aba Conexões: esta régua passa
#: um dublê de ponte e cobra QUAL função dela foi chamada, e os dois gestos
#: exigem **perfil ativo** — que o `ctx` dela não tem — e mudam primeiro o
#: DISCO; o `profile.switch` vem depois. Uma prova que só olhasse a ponte diria
#: que eles funcionam mesmo com o que foi para o arquivo errado.
#:
#: A prova deles é o disco, com perfil descartável e ponte dublê, e está em
#: `tests/unit/test_a_forca_da_vibracao_e_por_controle.py`.
#:
#: **`motor` ENTROU NESTA ISENÇÃO EM 04/09/2026, E POR OUTRA RAZÃO — o DUBLÊ.**
#: A `PonteDeMentira` da régua geral responde `True` a qualquer nome, e
#: `rumble_motores_set` devolve `(ok, corpo)`: o gesto faria
#: `TypeError: cannot unpack` no primeiro `zip`. Pôr o gesto ali exigiria
#: afrouxar o gesto para caber num dublê mais frouxo que a ponte real — que é
#: **exatamente** o defeito que esta casa mediu duas vezes em 04/09 (*"nos dois
#: casos o dublê do teste era mais frouxo que a ponte real"*).
#:
#: A prova dele é um dublê FIEL — que devolve o par e o corpo com `status` —, e
#: está em `tests/unit/test_a_aba_05_vibracao_fecha_as_linhas.py`.
PROVAS = [
    # DUAS chamadas — mirar e vibrar —, e as duas que saíram viraram o "Parar".
    # 07/09/2026: o "Testar" deixou de ser um pulso de meio segundo e virou
    # ESTADO (`_EM_TESTE`), a pedido dela: *"o botão Testar tem que ficar em
    # estado de ligado e ir refletindo os slicers ao vivo comigo. E se eu
    # clicar em Parar ele para de testar"*. Um gesto que se desliga sozinho
    # não pode ficar ligado — o `rumble_stop` e o `rumble_passthrough` mudaram
    # de dono, não sumiram do produto.
    {"pagina": PAGINA, "gesto": "testar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["controller.target.set"], {"index": 0}),
               ("rumble_set_checked", [160, 220], {})]},
    {"pagina": PAGINA, "gesto": "parar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["controller.target.set"], {"index": 0}),
               ("rumble_stop_checked", [], {}),
               ("rumble_passthrough", [True], {})]},
]

#: OS DOIS QUE O DAEMON ACEITA E NÃO PUBLICA, e a razão é do assunto: "Testar"
#: e "Parar" produzem um efeito FÍSICO — o plástico treme na mão dela — e o
#: tremor não deixa rastro no `state_full`. O `rumble_ff` conta os pedidos do
#: JOGO ao gamepad virtual; um teste mandado pela tela não passa por ali.
#:
#: A prova destes dois é a mão dela, e é honesto dizer isso em vez de fingir que
#: uma régua os alcança.
#:
#: `forca` E `intensidade` ENTRARAM EM 03/09/2026, e por outra razão: eles
#: passaram a escrever no PERFIL, e o `state_full` **não publica override por
#: controle nenhum**. Eles TÊM efeito vivo — o `profile.switch` de
#: `gravar_e_reaplicar` faz `ProfileManager.apply` publicar as escalas no
#: backend; o que não têm é ECO. A prova deles é o ARQUIVO, e está em
#: `tests/unit/test_a_forca_da_vibracao_e_por_controle.py`.
#:
#: **OS QUATRO FORAM REVISTOS EM 04/09/2026, e os quatro FICAM — mas por razões
#: diferentes, e a diferença é o que faltava escrito aqui.**
#:
#: A régua que este dado cala é UMA só: o `--prova-no-aparelho`, que lê o
#: `state_full` do DAEMON antes e depois do clique (`hefesto_vivo._depois_do_gesto`).
#: Não é uma dispensa geral de prova — é a declaração de que **aquela** régua
#: não alcança o assunto:
#:
#: * `testar`/`parar` — o efeito é FÍSICO e passa. Medido em 04/09 no daemon
#:   dela: o gesto acaba com `rumble.stop` + `rumble.passthrough(True)`, e a
#:   régua lê o estado 1,2 s depois do clique; nesse instante `rumble_active` e
#:   `rumble_passthrough` já voltaram ao que eram. Não há campo a comparar;
#: * `forca`/`intensidade` — o disco muda e o daemon não conta. **A régua que
#:   faltava passou a morar DENTRO do gesto**: :func:`_aplicar_a_forca` LÊ DE
#:   VOLTA o perfil pela mesma função que pinta a coluna e fala quando o que
#:   ficou não é o que ela pediu. É o que a pergunta *"não dá para ler de
#:   volta?"* pedia — e ler de volta do DAEMON continua impossível, porque não
#:   há o que ler.
#:
#: **`motor` ENTROU EM 04/09/2026, e pela mesma razão de `forca`/`intensidade`
#: virada do avesso: ele TEM eco, e o eco é honesto.** `state_full.rumble_motores`
#: publica as duas barras de cada peça — a ONDA1-D2 as pôs lá exatamente para a
#: tela ler de volta. O que ele **não** tem é eco no par de campos que a régua
#: `--prova-no-aparelho` compara hoje, porque ela lê o estado 1,2 s depois do
#: clique e as barras só mudam quando o perfil grava. Fica FORA da lista: quem
#: prova este gesto é a leitura de volta em :func:`_barras_dos_motores`, e a
#: régua do aparelho pode alcançá-lo no dia em que souber comparar mapas.
#:
#: `forca-mesa` ESTEVE NESTA CONVERSA e não está mais: o gesto saiu em
#: 05/09/2026 com a linha de mesa.
SEM_ECO = ("testar", "parar", "forca", "intensidade", "motor")
