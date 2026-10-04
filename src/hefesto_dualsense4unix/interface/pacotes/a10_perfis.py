#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

ESTA ABA JÁ ESTAVA MARCADA: **77 endereços**
(`data-hef`) e 11 gestos nela em 31/08, com um esquema de nomes próprio. Os dois
convivem — o nome do atributo não é o contrato; o contrato é este despachante.

O QUE TEM DONO: o perfil em vigor (`active_profile`) e o Modo Freestyle
(`freestyle_ligado`), que é o que diz se o Freestyle manda em todo jogo.

OS DEZ PRIMEIROS A GANHAR DONO — 01/09/2026, em duas levas:

    selecionar          a célula do nome, na lista. Abre o perfil no editor.
    ativar              `profile.switch`
    voltar-a-de-ontem   `restaurar_do_historico` + reaplicar + `launch_env.refresh`
    ---- a segunda leva ----------------------------------------------------
    editor.nome         renomeia: `save_profile` do nome novo + `delete_profile`
    editor.ambiente     troca a REGRA: `from_simple_choice` + `save_profile`
    editor.jogo         o programa (ou o appid) dentro da regra
    detectar            o jogo da Steam em foco, de `window_detect_last_class`
    novo                um perfil em branco, com a regra do jogo em foco
    duplicar            `model_copy` com "(cópia)" no nome, e o editor abre nela
    remover             `delete_profile`, com a pergunta NO RÓTULO do botão

A SEGUNDA LEVA SÓ FOI POSSÍVEL POR TRÊS CORREÇÕES, e nenhuma é do daemon:

1. o clique passou a trazer `valor` — o `value` do `<input>`/`<select>`. A
   primeira leva parou exatamente aqui: *"o ouvinte manda `texto:
   alvo.textContent`, que num `<input>` é vazio"*;
2. os quatro campos ganharam `data-hef-alvo="valor"` no gerador. Sem isso a
   pintura APAGAVA as opções dos dois `<select>` (medido: 5 → 0 e 15 → 0) e
   deixava os dois `<input>` com o texto do MOCKUP para sempre;
3. `pacote()` passou a mandar `editado=` para o produto. Sem isso o editor
   pintava o perfil ATIVO enquanto os botões agiam sobre o ESCOLHIDO — e ligar
   o campo Nome seria ela renomear um perfil olhando o nome de outro.

NÃO SOBRA NENHUM SEM DONO — 03/09/2026, e os DOIS ÚLTIMOS fecharam no fim do
dia:

    editor.prioridade   o `<input type=range>` que ela pediu — era o ÚNICO
                        campo do editor sem NENHUM caminho de escrita
    editor.estilo       escolher um estilo APLICA a receita: gatilho, degrau de
                        vibração e a cor de cada controle, de uma vez

São TREZE gestos com dono. As duas decisões são dela, do mesmo dia: *"Slider,
como você pediu"* e *"Construir o motor"* — e as receitas moram em
`profiles/estilos_de_jogo.py`, num lugar só, nunca digitadas aqui.

RECUSA-CHEGA-NA-TELA-01 — A REGRA DE QUAL EXCEÇÃO LEVANTAR, e ela não é gosto.
`hefesto_vivo._recusou_dizendo` pinta a tarja **só para `RuntimeError`**; um
`ValueError` sai no `stderr` do processo que lançou a janela e mais nada. O
contrato está escrito lá: `RuntimeError` é *"o produto recusou, e a frase VAI
PARA A TELA"*; `ValueError` é *clique inválido*, frase para quem programa.

**ESTA ABA VINHA VIOLANDO O CONTRATO EM NOVE FRASES**, e a mais cara delas
tinha teste verde. Medido em 03/09/2026, dirigindo a aba no produto instalado —
clique de verdade no "Ativar" com o perfil ativo já escolhido:

    [gesto falhou] ativar: “meu_perfil” já é o perfil que está valendo…  (stderr)
    tarjas na tela: []                                                   (o DOM)

A frase é inequivocamente DELA (*"Escolha outro na lista da esquerda e clique em
Ativar"*), a cura de 02/09 a escreveu com cuidado, o
`test_ativar_nao_diz_aplicado_sobre_o_perfil_que_ja_vale` a provou — e ela nunca
chegou à tela. É a forma de defeito que o próprio `_recusou_dizendo` nomeia:
*alguém curou o caminho e provou a cura num caminho que ela não usa.* Sobrou
UM `ValueError` neste arquivo — o do `selecionar`, que fala de um clique sem
nome de perfil e é a única frase daqui escrita para quem programa.

A LISTA PASSOU A CABER INTEIRA — 02/09/2026. O `<tbody>` publicado tem catorze
linhas porque catorze cabiam na figura, e a pasta dela tem **33 perfis**: os
outros dezenove não existiam na tela, e com eles nove dos dez botões desta aba,
que agem sobre o perfil ESCOLHIDO. A lista virou um `blocos` — ver
`_html_da_lista`, que também explica por que a régua do mockup não conta esta
entrega.

E A ABA PAROU DE PERGUNTAR SÓ AO DAEMON quem está valendo — ver `_valendo`. Com
`active_profile: null`, que é o estado da máquina dela hoje, três guardas se
desligavam ao mesmo tempo.

O QUE A ONDA2-10 ACRESCENTOU — 04/09/2026, as decisões do PO:

    [01] o CADEADO e o PONTO DE ALERTA. `editor.ambiente.travado` e
         `editor.ambiente.recado` saíam do produto e caíam no vazio — não havia
         endereço na página. Agora há, e junto veio a metade que ninguém tinha
         olhado: o `<select>` travado ficava com o **"Jogo" do mockup**, porque
         `escrever()` não tem onde pousar um `—` num `<select>` que não o
         oferece. Ver `aba10.opts(travessao=True)`.
    [02] o FIM da frase da exigência escondida, reescrito para ESTA tela — ver
         `FIM_DA_EXIGENCIA_AQUI`. A frase do produto está certa na janela GTK e
         errada aqui, e por isso a substituição é neste arquivo.
    [04] o CAMPO DO JOGO SE CORRIGE: `editor_jogo` e `detectar` devolvem
         `editor.jogo` na forma canônica junto com o desfecho. É o único
         instante em que a tela pode fazê-lo — o campo está em
         `CAMPOS_QUE_ELA_DIGITA` e o tique não o repinta.

    As decisões [03] e [05] são de DESENHO e moram no `aba10.py`.

O QUE ESTA ABA NÃO SABE FAZER, e é o teto de tudo o que está acima: **o daemon
não tem `profile.save` nem `profile.delete`.** Os 39 métodos que ele atende
trazem só `profile.switch`, `profile.list` e `profile.apply_draft` — gravar e
apagar perfil roda no processo da janela, direto no disco, e por isso todo gesto
que escreve tem de avisar o daemon depois (`profile.switch` para reaplicar,
`launch_env.refresh` para a antecipação por appid).
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any, NamedTuple

# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
from hefesto_dualsense4unix.app import gui_prefs as _prefs
from hefesto_dualsense4unix.app.actions import perfis_web as _tela

# `from_simple_choice`.
from hefesto_dualsense4unix.integrations.jogos_locais import LANCADOR_DIRETO
from hefesto_dualsense4unix.profiles.simple_match import (
    PROCEDENCIA_DA_NAVEGACAO,
    PROCEDENCIA_DA_STEAM,
    PROCEDENCIA_DE_QUALQUER_JOGO,
    SEPARADOR_DA_PROCEDENCIA,
    oferta_do_funciona_em,
)

from . import (
    PONTO_DO_ROTULO,
    SEM_NINGUEM_AQUI,
    TODOS_OS_LUGARES,
    TRAVESSAO,
    Contexto,
    perfil,
    registrar,
)

#: do state_full" — e daí eu concluí que não tinha dono. `profile.list` é um
#: `profiles_dir()`. Ter outro dono que não o `state_full` não é não ter dono.
SEM_DONO: dict[str, str] = {}


#: disco dela, `_secoes_do_controle` devolvia seis chaves, esta lista lia cinco,
SECOES_DA_COLUNA: tuple[str, ...] = (
    "leds", "triggers", "rumble", "speaker", "mic", "sensores", "mascara",
    "movimento")

#: não chega, `perfis_web._secoes_do_controle` não devolve a chave, o pacote lê
ESPERANDO_O_ESQUEMA: frozenset[str] = frozenset()


QUANDO = {"criteria": "Jogo", "any": "Todos — quando nenhum casa",
          "manual": "Só quando eu escolher"}


_ESCOLHIDO: str = ""


def _escolhido(todos: list[dict[str, Any]], ativo: str) -> str:
    """A linha aberta no editor: a última clicada, ou o perfil ativo.

    ELE DEIXA DE VALER SOZINHO quando o perfil sai do disco — apagado por fora,
    renomeado, o `HEFESTO_VARIANTE` trocado. Sem esta queda, "Voltar à de
    ontem" continuaria mirando um arquivo que não existe mais e a mensagem de
    erro falaria de um perfil que ela não vê na lista.

    A SINCRONIZAÇÃO INICIAL É ESCRITA AQUI DE PROPÓSITO, e a guarda é o que a
    torna segura de repetir: só grava quando a lista tem aquele nome. Na régua
    dos botões o `active_profile` é "regua" e nenhum perfil se chama assim,
    então nada é gravado e o estado do módulo continua limpo.

    FATO SUBSTITUÍDO — 02/09/2026, e é a segunda correção desta mesma linha.
    Estava escrito que, *"no mesmo lar de mentira do `conftest.py`"*,
    `load_all_profiles()` devolve **9 perfis** (os de fábrica, que ela semeia).
    **Sob o `pytest` ele devolve `[]`**: a `conftest.py:1327` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, e é justamente
    esse env que desliga o `_maybe_seed_presets`. Os nove eram reais — mas num
    processo SEM o pytest, que é onde a medição de 01/09 rodou. Conferido em
    02/09 com uma sonda dentro da suíte: `sorted(nomes) == []`.

    O QUE ISSO NÃO MUDA: a guarda continua segura de repetir. Com a lista vazia
    o `ativo` nunca está em `nomes`, então nada é gravado — que é o mesmo
    desfecho que a razão original previa por outro caminho.
    """
    global _ESCOLHIDO
    nomes = {p["nome"] for p in todos}
    if _ESCOLHIDO and _ESCOLHIDO not in nomes:
        _ESCOLHIDO = ""
    if not _ESCOLHIDO and ativo in nomes:
        _ESCOLHIDO = ativo
    return _ESCOLHIDO or ativo


# ORDEM DELA: *"Na tabela do perfil tem que terum svg dde  # (noqa-acento) cita ela
# lupa no titulo da tabela"*, *"Procura nome de perfil, e  # (noqa-acento) cita ela
# demais configs dos perfis, a ideia é  # (noqa-acento) cita ela
# acharmos rápido o nome de um jogo e essa tabela precisa permitir que eu  # (noqa-acento) cita ela
# escolha a ordenação dando duplo clique no nome das colunas."*  # (noqa-acento) cita ela
#

_PROCURA: str = ""

TABELA_DA_LISTA = "10-perfis.lista"

TABELA_DA_GUARDA = "10-perfis.guarda"

COLUNAS_DA_LISTA = ("nome", "prioridade", "quando")

_NOME_DA_COLUNA = {"nome": "Nome", "prioridade": "Preferência",
                   "quando": "Funciona em"}


def _sem_acento(texto: str) -> str:
    """O texto pronto para comparar — sem acento, sem caixa, sem pontuação."""
    from hefesto_dualsense4unix.profiles.slug import slugify
    try:
        return slugify(texto)
    except ValueError:
        return ""


def _casa(linha: dict[str, Any], termo: str) -> bool:
    """Aquela linha responde à busca?"""
    alvo = " ".join(str(linha.get(c) or "") for c in
                    ("nome", "prioridade", "quando", "dica"))
    return termo in _sem_acento(alvo)


def _filtrada(lista: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A lista com o filtro da lupa aplicado. Sem termo, ela sai inteira."""
    termo = _sem_acento(_PROCURA)
    if not termo:
        return list(lista)
    return [x for x in lista if _casa(x, termo)]


def _chave_da_ordem(coluna: str) -> Callable[[dict[str, Any]], Any]:
    """Como cada coluna se compara."""
    if coluna == "prioridade":
        def por_numero(x: dict[str, Any]) -> tuple[int, float, str]:
            try:
                return (0, float(str(x.get("prioridade") or "")), "")
            except ValueError:
                return (1, 0.0, _sem_acento(str(x.get("prioridade") or "")))
        return por_numero

    def por_texto(x: dict[str, Any]) -> tuple[int, float, str]:
        return (0, 0.0, _sem_acento(str(x.get(coluna) or "")))
    return por_texto


def _seta_da_coluna(coluna: str) -> str:
    """O que a seta daquela coluna mostra: `"↑"`, `"↓"` ou nada."""
    escolhida, sentido = _prefs.ordem_da_tabela(TABELA_DA_LISTA)
    if coluna != escolhida:
        return ""
    return "↓" if sentido == "desc" else "↑"


def _larguras_em_texto(tabela: str) -> str:
    """As larguras daquela tabela como `coluna:px` separados por `·`."""
    larguras = _prefs.larguras_da_tabela(tabela)
    return "·".join(f"{c}:{px}" for c, px in sorted(larguras.items()))


def _ordenada(lista: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A lista na ordem que ela escolheu — ou na que o produto monta."""
    coluna, sentido = _prefs.ordem_da_tabela(TABELA_DA_LISTA)
    if coluna not in COLUNAS_DA_LISTA:
        return list(lista)
    return sorted(lista, key=_chave_da_ordem(coluna), reverse=(sentido == "desc"))


SEGUNDOS_PARA_CONFIRMAR = 8.0

#: (`profiles_actions.py`) — "Perfil removido: X", "Lista recarregada",
#: `mensagem_do_salvar`, `mensagem_de_ativacao`. Aqui só a RECUSA falava:
#: `RuntimeError` vira tarja (`hefesto_vivo._recusou_dizendo`) e o SUCESSO era
_DESFECHO: tuple[str, float] | None = None

SEGUNDOS_DO_DESFECHO = 30.0


def _com_a_carona(frase: str) -> str:
    """Repõe o wrapper que a Steam comeu, e junta a notícia à frase do gesto."""
    from hefesto_dualsense4unix.app.actions import carona_do_wrapper as carona

    if not carona.ligada():
        return frase
    try:
        resultado = carona.passada(completa=True)
    except Exception:
        return frase
    curta = getattr(resultado, "frase_curta", "") or resultado.frase
    return f"{frase} · {curta}" if resultado.frase else frase


def _dizer(frase: str, **campos: Any) -> dict[str, Any]:
    """Relata o desfecho do gesto e devolve, na hora, os campos que ele corrige.

    DESDE 13/09/2026 A FRASE NÃO VAI PARA A TELA: ela sai em `relato` e no
    diário da janela, e a tira recebe vazio (ver o fim desta função). O que
    segue descreve o caminho dos `campos`, que continua valendo.

    `campos` SÃO OS ENDEREÇOS QUE O GESTO CORRIGE NA HORA, e eles viajam no
    mesmo embrulho — 04/09/2026, decisão [04] do PO. O caso que os pediu é o do
    "Nome do Jogo": os campos que ela DIGITA são omitidos do tique
    (`CAMPOS_QUE_ELA_DIGITA`, para a pintura não apagar o que ela está
    escrevendo), então o único instante em que a tela pode devolver a forma
    canônica do que ela colou é a resposta do PRÓPRIO gesto. Sem isto, o
    endereço da loja fica no campo até ela trocar de perfil.

    O CAMINHO DE VOLTA JÁ EXISTIA e ninguém desta aba o usava: um gesto que
    devolve um dicionário tem a carga pintada na hora (`hefesto_vivo._deu_certo`
    → `window.__hef.pintar`), no mesmo vocabulário `endereço → valor` da
    pintura — logo o tique seguinte não briga, sobrescreve com o mesmo valor.

    POR QUE NA HORA E NÃO NO TIQUE, e o argumento é o do piloto, palavra por
    palavra: *"Meio segundo entre o clique e a resposta basta para ela clicar de
    novo achando que o primeiro não pegou"*. Meio segundo é o tique desta aba.

    **O `mesa:` NÃO É ENFEITE.** O `_deu_certo` entrega a carga CRUA ao
    `window.__hef.pintar`, que lê `p.blocos`, `p.mesa`, `p.colunas` e
    `p.vazios` — e mais nada. Um dicionário achatado (`{"perfis.desfecho": …}`)
    passa por todos os laços sem casar com nenhum: **zero escrito, zero erro**,
    que é a forma exata do defeito que esta casa chama de *ausência de notícia
    lida como sucesso*, e que já custou dois dias ao `blocos` do `normalizar`.
    O `pacote()` chega ao JS com esse embrulho porque `pacotes.normalizar` o
    põe; um gesto não passa por lá, e põe o seu.
    """
    global _CARONA_PENDENTE
    # registro de chamada que `perfil.com_a_carona` documenta para quem já tem
    # `_com_a_carona(frase)` direto e este campo continua vazio — dois `·` para
    if _CARONA_PENDENTE:
        frase = f"{frase} · {_CARONA_PENDENTE}" if frase else _CARONA_PENDENTE
        _CARONA_PENDENTE = ""
    _anotar(frase)
    #  nao devia aparecer nunca"  # (noqa-acento) citação literal dela
    return {"mesa": {"perfis.desfecho": "", **campos}, "relato": frase}


def _anotar(frase: str) -> None:
    """Leva o desfecho do gesto ao diário da janela — e não mais à tela."""
    global _DESFECHO
    _DESFECHO = None
    if frase:
        print(f"[desfecho] {PAGINA} · {frase}", file=sys.stderr)


def _desfecho_para_a_tela() -> str:
    """O desfecho ainda vivo, ou vazio — e a PODA mora aqui, no leitor."""
    global _DESFECHO
    if _DESFECHO is None:
        return ""
    frase, quando = _DESFECHO
    if time.monotonic() - quando >= SEGUNDOS_DO_DESFECHO:
        _DESFECHO = None
        return ""
    return frase


#: `data-hef-alvo="largura"` estaria *"já escrito na BANCADA (`aba10.py`),
#:                       desta frente; está no relatório.
#: `data-hef-alvo="classe"`, e o produto passou a acender e apagar cada uma.
NAO_PINTAVEIS = ("guarda.linhas", "editor.prioridade.dica",
                 "editor.estilo")

#: os valores que a página NÃO TEM — eles caem no vazio, sem estrago e sem
SEM_ENDERECO = {
    # a `classe` acendendo em `editor.ambiente.travado` e a frase no hover, por
    "editor.estilo.travado": "o campo GRAVA desde 03/09 (`estilo_travado` é "
                             "sempre `False`) — uma marca de travado aqui "
                             "nunca acenderia",
    "editor.estilo.recado": "a frase que explica por que o campo volta ao "
                            "travessão (`perfis_web.ESTILO_APLICA_E_SAI`) diz "
                            "o mesmo que o `title` do rótulo, no mesmo hover — "
                            "um segundo canal para o mesmo fato",
    "quantos": "a contagem que a tela mostra é `perfis.conta`, e essa tem endereço",
    "travado": "a trava da troca automática não é desenhada nesta aba",
    "editor.modo": "o quadro «Modo» saiu do editor por ordem dela em "
                   "11/09/2026 — a aba onde o modo se escolhe é a Jogar; "
                   "`Profile.mode` continua no disco e o `ativar` continua "
                   "o aplicando",
}

#: baixa. As datas: `perfis.desfecho` (03/09) · `editor.prioridade.escolha`
ESPERANDO_A_PUBLICACAO: dict[str, str] = {
}


FIM_DA_EXIGENCIA_NA_GTK = "Ligue o Modo avançado para ver e mudar."
FIM_DA_EXIGENCIA_AQUI = "Esta tela não mostra esses campos."


def _exigencia_para_esta_tela(match: Any) -> str:
    """A exigência escondida daquele `match`, com o fim que ESTA tela alcança.

    NUNCA LEVANTA: ela roda dentro de `pacote()`, e uma exceção aqui derrubaria
    a pintura da aba inteira por causa de um perfil com uma regra estranha — a
    tela ficaria congelada sem dizer por quê.

    **A TROCA É EXATA E COBRADA**: `test_a_aba_10_perfis_fecha_as_linhas.py`
    exige que `FIM_DA_EXIGENCIA_NA_GTK` continue sendo o fim que o produto
    emite. No dia em que a frase de lá mudar, a régua reprova AQUI — em vez de
    a troca falhar em silêncio e a tela voltar a mandá-la a um lugar que não
    existe. É a diferença entre uma remenda declarada e uma remenda podre.
    """
    try:
        from hefesto_dualsense4unix.profiles.simple_match import (
            exigencia_invisivel,
        )

        frase = str(exigencia_invisivel(match) or "") if match is not None else ""
    except Exception:
        return ""
    if not frase:
        return ""
    return f"{frase} {FIM_DA_EXIGENCIA_AQUI}"

_ARMADO: tuple[str, float] | None = None

_PINTADO_PARA: str = ""
_ULTIMO_TIQUE: float = 0.0

CAMPOS_QUE_ELA_DIGITA = ("editor.nome", "editor.jogo",
                         "editor.prioridade.escolha")


def _uma_vez_so(alvo: str) -> tuple[str, ...]:
    """Os endereços a OMITIR deste tique. Vazio = pinte tudo."""
    global _PINTADO_PARA, _ULTIMO_TIQUE
    agora = time.monotonic()
    voltou = (agora - _ULTIMO_TIQUE) > 2.0
    _ULTIMO_TIQUE = agora
    if voltou or alvo != _PINTADO_PARA:
        _PINTADO_PARA = alvo
        return ()
    return CAMPOS_QUE_ELA_DIGITA


SEPARADOR_EM_TEXTO = " • "


def _rotulo_curto(controle: dict[str, Any]) -> str:
    """`P1 • Cosmic Red • USB` — a forma `curta` do `monta.rotulo`, sem marcação.

    `jogador`, `nome` e `via` são os três campos que `mesa_viva.mesa_do_estado`
    devolve, e são exatamente os três que a forma `curta` junta.
    """
    return SEPARADOR_EM_TEXTO.join([
        f"P{controle.get('jogador') or '—'}",
        str(controle.get("nome") or "—"),
        str(controle.get("via") or "—"),
    ])


def _plastico(controle: dict[str, Any]) -> str:
    """O hexadecimal da casca daquele controle, **pelo dono da cor**.

    A LEI É DELA, 03/09/2026: *"se no topo tá mostrando controle white player 1,
    então cada aba vai usar os controles lá de cima. Não mistura com a info dos
    mockups."* A barra de 3px da linha era `--plastico` cravado no `<tr>` pelo
    gerador — a cor do controle do DESENHO —, e ficava lá enquanto o
    `guarda.nome` ao lado já vinha do aparelho: a linha dizia `P1 • White • USB`
    com a barra vermelha do mockup.

    `monta.cor_da_zona` lê o `<style>` que `scripts/gerar_cores_do_dualsense.py`
    escreveu no `ds_limpo.svg` — o MESMO lugar de onde a fita do topo tira a cor
    do chip. Reescrever a leitura aqui criaria a segunda verdade sobre a cor, que
    é o que o portão `check_cores_do_dualsense.py` existe para matar.

    O IMPORT É TARDIO E GUARDADO, e não uma exceção que eu abri: é exatamente o
    que `hefesto_vivo._fita` faz para esta mesma leitura, pela mesma razão. O
    `monta` lê disco no import (o esqueleto, o SVG e dois CSV de `docs/`), então
    um `import` no topo derrubaria a janela onde não há repositório. E não é um
    caminho novo: sem repositório a fita do topo também não repinta.

    `SystemExit` NO `except`, e ele não é `Exception`: `cor_da_zona` ergue
    justamente essa para um colorway que o SVG não tem, e um `except Exception`
    passaria ao lado — foi como o piloto morreu na primeira execução da fita viva.

    SEM COR LIDA, DEVOLVE VAZIO. Pelo rádio a cor não vem (o mapa de canais diz
    `identidade.cor_do_aparelho = não`) e `mesa_do_estado` entrega `cor: ""`.
    Inventar um cinza, ou cair na cor do mockup, seria a tela afirmando um modelo
    que ninguém pode conferir — o defeito que esta frente veio desfazer. Com o
    vazio o piloto escreve `''` no alvo `cor`, o `style` de linha cai, o
    `color:transparent` da classe volta e a barra SOME: campo sem informação não
    mostra nada, regra dela.
    """
    slug = str(controle.get("cor") or "")
    if not slug:
        return ""
    try:
        from hefesto_dualsense4unix.interface import monta

        return str(monta.cor_da_zona(slug))
    except (Exception, SystemExit):
        return ""


def _mesa_com_rotulo(mesa: list[dict[str, Any]], conectados: Any = ()) -> list[dict[str, Any]]:
    """A mesa no formato que `perfis_web.pacote_da_aba` DIZ esperar.

    FATO ERRADO, SUBSTITUÍDO — 02/09/2026. A docstring de
    `perfis_web.pacote_da_aba` afirma que a mesa vem *"no formato que
    ``mesa_viva.mesa_do_estado`` devolve mais ``rotulo`` e ``plastico``"*, e o
    `_linhas_da_guarda` lê `controle.get("rotulo")` (`perfis_web.py:300`).
    **`mesa_do_estado` não devolve nenhum dos dois** — os campos dela são
    `pref`, `uniq`, `jogador`, `cor`, `nome`, `via`, `transporte`, `alvo`,
    `mascara` (`mesa_viva.py:376-397`). Medido: `guarda.nome` saía `["", ""]`
    para os DOIS controles da mesa dela, e a tabela ficava sem nome nenhum.

    FATO ERRADO, SUBSTITUÍDO — 11/09/2026. Aqui estava escrito *"QUEM JÁ FAZIA
    ISTO CERTO: `interface/perfis_vivos.mesa_de_agora` — o visor da aba"*.
    **Ele fazia o CONTRÁRIO**, e a medição é uma foto: aquele visor punha em
    `rotulo` a saída de `monta.rotulo(c, "curta")`, que é MARCAÇÃO
    (`P1 <span …>•</span> Cosmic Red …`), e o pintor da tela escreve
    `textContent`. A bancada mostrava a marcação como TEXTO, em quatro linhas —
    e o produto, que passa por aqui, mostrava o rótulo certo. O instrumento
    respondia sobre outra coisa que não o produto, que é a assinatura de defeito
    mais cara desta casa. O visor foi curado no mesmo commit e passou a chamar
    `_rotulo_curto`; o que ele já fazia certo era a FORMA — uma mesa com
    `rotulo` e `plastico` —, não o conteúdo.

    O `plastico` ENTROU EM 03/09/2026, e o fato acima valia para ele também:
    `_linhas_da_guarda` lê `controle.get("plastico")` (`perfis_web.py:300`) e
    recebia `""` para todo controle, porque ninguém o punha aqui. Ver `_plastico`.
    """
    return [{**c, "rotulo": _rotulo_curto(c), "plastico": _plastico(c),
             "entrada": _entrada_viva(conectados, str(c.get("uniq") or ""))}
            for c in mesa]


SELETOR_DA_LISTA = 'tbody[data-hef="perfis.lista"]'

SELETOR_DOS_JOGOS = 'datalist[data-hef="editor.jogo.lista"]'

#: Ele virou `blocos` pela MESMA razão que a lista dos jogos: as opções são os
SELETOR_DO_AMBIENTE = 'select[data-hef="editor.ambiente"]'

#: QUANTOS JOGOS A LISTA OFERECE, no máximo. **É teto de SEGURANÇA, não de
TETO_DA_LISTA_DE_JOGOS = 500

_RECUO = " " * 16


def _texto(v: Any) -> str:
    """Um valor pronto para virar TEXTO dentro de uma célula."""
    s = str(v if v is not None else "")
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("\xa0", "&nbsp;"))


def _atr(v: Any) -> str:
    """Um valor pronto para virar VALOR DE ATRIBUTO — `title=`, `data-…=`.

    **ESCAPA MENOS QUE O `html.escape` DO PYTHON, e isso é a cura de um defeito
    medido, não um relaxamento.** O `blocos` do piloto só reescreve o miolo
    quando `alvo.innerHTML !== html` — ou seja, ele compara a MINHA string com a
    **serialização que o navegador devolve**. Escapar o que o serializador não
    escapa faz as duas nunca baterem, e o bloco é reescrito a cada 500 ms para
    sempre.

    MEDIDO em 02/09/2026, com o piloto aberto na aba por dez segundos e com o
    mesmo HTML injetado num Chrome de bancada (`_ferramentas` do desenho, sem
    janela) para ler o `innerHTML` de volta:

        `html.escape(quote=True)`  →  21 tiques, 17 escritas em CADA um
        escapando como o serializador →  1 escrita, e silêncio depois

    As duas divergências, e as duas são de escapar DEMAIS:

        `'`   o Python manda `&#x27;`, o navegador devolve `'`   (`DON'T SCREAM`)
        `\\n`  o Python (na minha primeira tentativa) mandava `&#10;`, o navegador
              devolve a quebra CRUA — e a dica da disputa tem dois parágrafos

    E NÃO É INSEGURO: dentro de aspas duplas, um `'` e um `<` não fecham nada —
    quem fecha o atributo é a aspa dupla, e ela continua virando `&quot;`. É
    exatamente o conjunto que o serializador de HTML escapa em atributo.

    O CUSTO DE NÃO CURAR ISTO NÃO É SÓ O CONTADOR: reescrever o `<tbody>` a cada
    meio segundo apaga o `:hover` da linha sob o mouse dela e desfaz qualquer
    seleção de texto na lista — três vezes por segundo, enquanto ela procura um
    perfil entre 33.
    """
    s = str(v if v is not None else "")
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("\xa0", "&nbsp;")


def _linha_da_lista(nome: str, prioridade: str, quando: str,
                    ativo: bool, dica: str = "", escolhido: bool = False) -> str:
    """Uma linha da lista de perfis — a MESMA forma que o desenho crava.

    O DONO DA FORMA CONTINUA SENDO O GERADOR, `aba10.linha_do_perfil`, cuja
    docstring já dizia a que veio: *"a MESMA para o mockup e para a viva … a aba
    viva precisa do desenho, não de uma cópia dele"*. Só que ele **não atravessa
    para o produto**: `aba10.py` faz `sys.path.insert` e `from monta import …`,
    e o `monta` lê seis arquivos do repositório no import — um gerador no
    caminho do produto é uma janela que não abre onde não há repositório. É a
    mesma razão pela qual o `SEPARADOR_EM_TEXTO` acima é uma constante e não um
    import.

    ENTÃO O QUE IMPEDE A SEGUNDA GRAMÁTICA É UMA RÉGUA, e não a boa vontade:
    `test_a_lista_de_perfis_cabe_inteira.py::test_a_linha_viva_e_a_linha_do_desenho`
    importa o gerador (no teste ele pode) e compara as duas saídas caractere a
    caractere. Mexer no desenho da linha sem mexer aqui reprova ANTES de a tela
    discordar de si mesma.

    A ÚNICA DIVERGÊNCIA DECLARADA É O ESCAPE — ver `_texto` e `_atr`.

    `escolhido` É A LINHA ABERTA NO EDITOR — 04/09/2026, queixa dela: *"quando
    clica em algum nome do perfis salvos nada indica que tal coisa tá
    selecionado"*. O valor já existia (`_escolhido`, no alto deste arquivo) e
    alimentava só o texto do botão Remover e os gestos; ele não chegava à LINHA,
    e a tela ficava calada sobre o alvo de nove botões.

    **A MARCA TEM DE VIR DAQUI, e não de um `classList.add` no JS**: o `blocos`
    do piloto reescreve este `<tbody>` inteiro a cada tique, e o tique é de
    **100 ms** — qualquer marca posta pelo navegador vive um décimo de segundo.

    NÃO É UMA SEGUNDA CLASSE, e a razão é medida:
    `test_a_lista_de_perfis_cabe_inteira.py:159` procura a SUBSTRING
    `class="ativo"` na linha realçada, e um `class="ativo escolhido"` a some —
    a régua do realce ficaria verde sobre uma linha que ela não acha mais. O
    estado vai em `aria-selected`, que é o que o papel `row` já define para
    seleção: uma verdade só, no atributo que a própria plataforma leu primeiro.
    """
    return (f'{_RECUO}<tr class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{_atr(nome)}" data-hef-gesto="selecionar" '
            f'aria-selected="{"true" if escolhido else "false"}" title="{_atr(dica)}">'
            f'<td data-hef="perfis.linha.nome">'
            f'{_texto(nome)}</td>'
            f'<td class="pri" data-hef="perfis.linha.prioridade">'
            f'{_texto(prioridade)}</td>'
            f'<td class="quando" data-hef="perfis.linha.quando" '
            f'title="{_atr(quando)}">'
            f'{_texto(quando)}</td></tr>')


def _html_da_lista(lista: list[dict[str, Any]], vazia: str,
                   escolhido: str = "") -> str:
    """As linhas da lista de perfis, TODAS — e é a maior mentira que esta aba
    contava.

    MEDIDO em 02/09/2026, na máquina dela: `load_all_profiles()` devolve **33**
    perfis e o `<tbody>` publicado tem **14 linhas**. O contador ao lado do
    título dizia "33 perfis" — e dizia a verdade — enquanto a tabela logo abaixo
    mostrava catorze. **Dezenove perfis dela não tinham como ser clicados**, e
    com eles nove dos dez botões desta aba: `ativar`, `remover`, `duplicar`,
    `editor.nome`… todos agem sobre o perfil ESCOLHIDO, e escolher é clicar numa
    linha que existe.

    POR QUE NÃO SE PINTA CAMPO A CAMPO: é a mesma razão da fita de chips e do
    mapa do gabinete — **um bloco cujo número de filhos muda com o dado não tem
    endereço para o filho que ainda não existe**. A lista de perfis é o caso
    mais puro: o desenho cravou catorze porque catorze cabiam na figura.

    TRÊS COISAS CHEGAM À TELA POR AQUI E NÃO CHEGAVAM POR NENHUMA OUTRA PORTA:

    1. **as linhas que faltavam** — as 19;
    2. **a classe `ativo` na linha certa.** O desenho a crava na PRIMEIRA linha,
       e até hoje ela ficava lá. Acertava por acidente — `ordem_de_exibicao`
       põe o ativo em primeiro —, e mentia inteiro quando não há perfil ativo
       nenhum: a tela realçava um perfil que não está valendo. Nenhum dos cinco
       alvos do pintor liga uma CLASSE; o `blocos` traz a linha pronta, com a
       classe dentro dela, e não precisa dele;
    3. **o `title` da disputa.** `explicacao_da_disputa` existe em
       `profiles_actions:403`, `perfis_web._linhas_da_lista` já a chamava a cada
       tique, e o valor morria no dicionário: o `title=""` do desenho nasce
       vazio *"porque a dica é a DISPUTA, e disputa é dado — o mockup não tem
       nenhum"* (palavras do gerador). O dado existe desde então; faltava a
       porta.

    A LISTA VAZIA TAMBÉM É UM ESTADO, e a frase dela já estava escrita e nunca
    tinha aparecido: `perfis_web.LISTA_VAZIA` diz o que fazer para ter o
    primeiro perfil. Sem esta linha o `<tbody>` ficaria em branco — a tela
    calada sobre um estado que ela sabe explicar.

    **ESTE `<tbody>` AINDA É REESCRITO A CADA TIQUE, e a causa NÃO é o escape** —
    medido em 02/09/2026 no WebKit da janela dela, com o daemon vivo e uma sonda
    no laço do `blocos` do piloto. Em 20 tiques: `BLOCOS 20`, contra 1 de cada
    um dos outros endereços da aba (eles assentam no primeiro tique). O primeiro
    caractere divergente é o 594:

        na TELA     …data-hef-gesto="selecionar" data-hef-visto="1">meu_perfil…
        no PRODUTO  …data-hef-gesto="selecionar">meu_perfil…

    O `escrever()` do piloto carimba `el.dataset.hefVisto = '1'` em TODO
    elemento que visita — inclusive quando escreve zero, que é o ponto do selo.
    O laço do `blocos` roda ANTES da distribuição por endereço e compara
    `alvo.innerHTML !== html`: do segundo tique em diante a tela tem 99 selos
    que o produto não tem (12.222 caracteres contra 10.341), e as duas strings
    nunca mais batem. O custo é o que a nota do `_atr` já descreve — o `:hover`
    da linha sob o mouse dela apagado duas vezes por segundo, enquanto ela
    procura um perfil entre 33.

    **A CURA MORA NO PILOTO, e não aqui** — carimbar o selo fora da serialização
    (um `WeakSet` em JS) ou comparar sem ele. Emitir o selo daqui faria esta aba
    conhecer um detalhe interno do pintor.

    HOJE SÓ ESTA LISTA PAGA, e conferi antes de acusar as irmãs: o defeito só
    morde um `blocos` cujos FILHOS tenham endereço, e os dois da `08-conexoes`
    (`.mm-faces` e `.mm-lista`) não emitem `data-campo` nenhum dentro. Quando
    emitirem, entram no mesmo buraco.

    `escolhido` É O NOME DA LINHA ABERTA NO EDITOR, e a comparação é por NOME
    EXATO de propósito: quem chama já resolveu o slug (`find_by_slug`) contra os
    perfis que existem, e o `nome` de cada linha vem do mesmo `p.name`. Comparar
    slug de novo aqui seria a segunda resolução do mesmo dado — e é assim que
    esta aba já deu dois vereditos sobre a mesma tela em 02/09.

    O VAZIO É O ESTADO SEM MARCA: `escolhido=""` não casa com nome nenhum, e a
    lista sai como saía. É o que mantém verde toda régua que chama esta função
    sem saber que ela ganhou um terceiro argumento.
    """
    if not lista:
        return (f'{_RECUO}<tr class="vazia"><td colspan="3">'
                f'{_texto(vazia)}</td></tr>')
    return "\n".join(
        _linha_da_lista(str(x.get("nome") or ""), str(x.get("prioridade") or ""),
                        str(x.get("quando") or ""), bool(x.get("ativo")),
                        str(x.get("dica") or ""),
                        escolhido=bool(escolhido)
                        and str(x.get("nome") or "") == escolhido)
        for x in lista)


def _html_dos_jogos(procedencia: str = "", foto: _FotoDoCatalogo | None = None) -> str:
    """As `<option>` do `<datalist>` — os jogos DESTA máquina, do disco dela.

    **E DAQUELE LANÇADOR, desde 11/09/2026** (C4-FUNCIONA-EM, §3): com
    `procedencia` cheia a lista traz só os jogos de onde o campo de cima diz
    que o jogo vem. Sem ela — e nas duas procedências que não são lançador —
    a lista sai inteira, que é o que ela sempre foi. Ver `_PROCEDENCIAS_SEM_JOGO`.

    PERFIL-MODO-01, Passo 3 (06/09/2026). A linha 378 do CSV da paridade dizia
    do lado HTML: *"NADA. O `<input>` é texto livre"* — e a nota explicava o
    custo: *"criar um perfil de jogo pelo HTML exige ela saber o appid de cor ou
    ir buscá-lo na loja"*. O botão "Detectar" cobre metade (só com o jogo em
    foco); a lista cobre o resto, inclusive jogo FECHADO.

    O CATÁLOGO É O DO PRODUTO, não uma segunda leitura: `_nomes_dos_jogos()` já
    existe nesta aba desde a 10-Q4 e é memoizado pela ASSINATURA da biblioteca
    (`jogos_locais.assinatura_da_biblioteca`) — então dez tiques por segundo não
    abrem 33 `.acf` dez vezes por segundo. Chamar `catalogo_de_jogos()` direto
    aqui seria a segunda leitura do mesmo disco, sem o cache.

    O `value` É O APPID E O `label` É O NOME, e a ordem não é livre: num
    `<datalist>` o navegador escreve o `value` NO CAMPO quando ela escolhe, e o
    campo grava um appid (`from_simple_choice("steam_game", …)` quer o número).
    É a MESMA divisão que a janela GTK faz com as duas colunas do
    `Gtk.EntryCompletion` — *"Coluna 0 = o rótulo que ela lê, Coluna 1 = o
    appid, que é o que o campo grava"* — e o comentário de lá diz o preço de
    trocar: um perfil nasceria com `steam_app_Sea of Stars`, que nunca casa com
    janela nenhuma.

    ESCAPAR É OBRIGATÓRIO E É O `_atr`, não o `html.escape`: os nomes vêm dos
    `.acf` e dos `.desktop` DELA — `DON'T SCREAM` está no catálogo desta casa —,
    e escapar o que o serializador do navegador não escapa faria o `blocos`
    reescrever o bloco a cada 500 ms para sempre. A medição está na docstring de
    `_atr`.

    **E OS JOGOS DE FORA DA STEAM ENTRAM — 11/09/2026**, que é a queixa dela
    com o exemplo na mão: *"em perfil falta detectar os jogos dos demais
    lançadores. dando exemplo do guardi]ães da galáxia."*  # (noqa-acento) citação dela

    A DIVISÃO `value`/`label` É A MESMA, e o `value` de um jogo de lançador é a
    `wm_class` dele (``gotg.exe``) em vez do appid — o MESMO campo do perfil
    (`window_class`), pela sexta forma do `simple_match` ("janela"). Quem
    decide qual dos dois é `JogoLocal.valor`, e a JUNÇÃO das duas origens é
    `jogos_locais.ofertas_do_campo_do_jogo`: escrever aqui um `if` e uma ordem
    própria seria a segunda verdade sobre o que esta lista oferece.

    NUNCA LEVANTA, pela mesma razão de `_jogo_reconhecido`: isto é PINTURA, a
    duas vezes por segundo, sobre a biblioteca dela. Uma exceção lendo um
    `.desktop` estragado derrubaria a aba inteira por causa de uma sugestão.

    `foto` é a do tique (`_foto_do_catalogo`); sem ela, a pergunta de sempre.
    """
    jogos = _ofertas_de(foto)
    if procedencia and procedencia not in _PROCEDENCIAS_SEM_JOGO:
        jogos = [j for j in jogos if _procedencia_do_jogo(j) == procedencia]
    linhas = [
        f'<option value="{_atr(jogo.valor)}" label="{_atr(_linha_do_jogo(jogo))}">'
        f'</option>'
        for jogo in jogos
    ]
    return "".join(linhas[:TETO_DA_LISTA_DE_JOGOS])


_PROCEDENCIAS_SEM_JOGO = frozenset(
    {PROCEDENCIA_DA_NAVEGACAO, PROCEDENCIA_DE_QUALQUER_JOGO})


def _ofertas_de_jogos(nomes: dict[str, str] | None = None) -> list[Any]:
    """Os jogos DESTA máquina, das duas origens — a leitura que dois campos usam."""
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            JogoLocal,
            jogos_de_janela,
            ofertas_do_campo_do_jogo,
        )

        if nomes is None:
            nomes = _nomes_dos_jogos()
        de_janela = jogos_de_janela()
        return list(ofertas_do_campo_do_jogo(
            [JogoLocal(appid=appid, nome=nome, fonte="steam")
             for appid, nome in nomes.items()],
            de_janela))
    except Exception:
        return []


class _FotoDoCatalogo(NamedTuple):
    """O catálogo de jogos desta máquina, perguntado UMA vez por tique."""

    nomes: dict[str, str]
    ofertas: list[Any]


def _foto_do_catalogo() -> _FotoDoCatalogo:
    """As duas perguntas ao catálogo, uma vez cada — e nunca levanta."""
    try:
        nomes = _nomes_dos_jogos()
    except Exception:
        nomes = {}
    return _FotoDoCatalogo(nomes=nomes, ofertas=_ofertas_de_jogos(nomes))


def _ofertas_de(foto: _FotoDoCatalogo | None) -> list[Any]:
    """As ofertas da foto do tique, ou a pergunta de sempre sem ela."""
    return foto.ofertas if foto is not None else _ofertas_de_jogos()


def _nomes_de(foto: _FotoDoCatalogo | None) -> dict[str, str]:
    """Os nomes da Steam da foto do tique, ou a pergunta de sempre sem ela."""
    return foto.nomes if foto is not None else _nomes_dos_jogos()


def _procedencia_do_jogo(jogo: Any) -> str:
    """De onde vem ESTE jogo — o nome que o campo «Funciona em:» mostra."""
    return str(getattr(jogo, "lancador", "") or "") or PROCEDENCIA_DA_STEAM


def _linha_do_jogo(jogo: Any) -> str:
    """O que a LINHA da lista do campo «Nome do Jogo» diz — item 12 da lista dela."""
    appid = str(getattr(jogo, "appid", "") or "")
    nome = str(getattr(jogo, "nome", "") or "")
    return f"{nome} · {appid}" if appid else nome


ORDEM_DOS_LANCADORES = (PROCEDENCIA_DA_STEAM, "Heroic", "Lutris", "RetroArch",
                        "Dolphin", "mGBA")


def _procedencias_da_maquina(foto: _FotoDoCatalogo | None = None) -> list[str]:
    """Os lançadores que ESTA máquina tem — a lista que o campo oferece."""
    achadas = {_procedencia_do_jogo(j) for j in _ofertas_de(foto)}
    conhecidas = [n for n in ORDEM_DOS_LANCADORES if n in achadas]
    return conhecidas + sorted(achadas - set(ORDEM_DOS_LANCADORES))


def _lancador_da_chave(chave: str, foto: _FotoDoCatalogo | None = None) -> str:
    """De qual lançador vem o jogo com ESTA `wm_class` (ou nome de programa).

    É a ponte que `simple_match.procedencia_do_match` pede, e ela mora aqui
    porque é leitura de disco: `profiles/` é o esquema, e um módulo de esquema
    que importasse `integrations/` obrigaria toda régua dele a ter a biblioteca
    dela na mão.

    **O RESIDUAL É «Instalado aqui», e nunca o campo travado.** Uma chave que o
    catálogo não conhece — ``guard``, ``Hefesto-Dualsense4Unix``, os dois
    medidos no disco dela em 11/09/2026 — é um perfil que ELA escreveu, que
    funciona, e que a §5 manda continuar válido e mostrado. `LANCADOR_DIRETO` é
    a palavra que o produto já tem para isso (*"de lugar nenhum, está no
    menu"*), e é a mesma que a lista do campo de baixo escreve. Travar o campo
    aqui seria tirar dela o gesto sobre um perfil que nada tem de errado.

    **O RESIDUAL DE UM ENDEREÇO DA STEAM É «Steam» — 21/09/2026.** Desde que
    `procedencia_do_match` passou a trazer aqui também o preset `steam_game`
    (porque o jogo do Heroic anuncia `steam_app_<id>`), um appid que nenhum
    lançador reivindica chega a esta função — e dele a resposta honesta não é
    *"está no menu"*: é a Steam. `steam_app_<id>` é o carimbo dela, e a
    biblioteca da Steam entra no catálogo por outra porta (por APPID, não por
    chave de janela), então o `jogo_da_janela` não a acha e nem deve.

    NUNCA LEVANTA — a queda também é o residual, pelo mesmo motivo: um `.desktop`
    estragado não pode travar o seletor de um perfil que está certo.
    """
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    residual = (PROCEDENCIA_DA_STEAM
                if steam_appid_from_wm_class(chave) is not None
                else LANCADOR_DIRETO)
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import jogo_da_janela

        achado = jogo_da_janela(chave, _ofertas_de(foto))
    except Exception:
        return residual
    return _procedencia_do_jogo(achado) if achado is not None else residual


def _jogo_da_procedencia(procedencia: str, texto: str) -> Any:
    """O jogo DESTA procedência que este texto nomeia — ou ``None``."""
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import chave_de_busca

        alvo = chave_de_busca(texto)
        if not alvo:
            return None
        candidatos = [j for j in _ofertas_de_jogos()
                      if _procedencia_do_jogo(j) == procedencia]
        for de_qual in ("valor", "nome"):
            for jogo in candidatos:
                if chave_de_busca(str(getattr(jogo, de_qual, ""))) == alvo:
                    return jogo
    except Exception:
        return None
    return None


def _com_a_procedencia(lista: list[dict[str, Any]], todos: list[Any],
                       foto: _FotoDoCatalogo | None = None) -> list[dict[str, Any]]:
    """A coluna «Funciona em» de cada linha, traduzida — ver `_quando_usar`."""
    por_nome = {str(getattr(p, "name", "")): p for p in todos}
    fora: list[dict[str, Any]] = []
    for linha in lista:
        prof = por_nome.get(str(linha.get("perfil") or linha.get("nome") or ""))
        if prof is None:
            fora.append(linha)
            continue
        nova = dict(linha)
        nova["quando"] = _quando_usar(getattr(prof, "match", None),
                                      str(linha.get("quando") or ""), foto)
        fora.append(nova)
    return fora


def _nome_no_catalogo(chave: str, foto: _FotoDoCatalogo | None = None) -> str:
    """O NOME do jogo com esta chave de janela, ou `""` — nunca levanta."""
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import jogo_da_janela

        achado = jogo_da_janela(chave, _ofertas_de(foto))
    except Exception:
        return ""
    return str(getattr(achado, "nome", "") or "") if achado is not None else ""


def _nome_e_codigo(chave: str, foto: _FotoDoCatalogo | None = None) -> tuple[str, str]:
    """``(nome do jogo, código)`` para o que o perfil guarda — item 12 dela."""
    from hefesto_dualsense4unix.profiles.simple_match import normalize_appid

    if not chave:
        return ("", "")
    appid = normalize_appid(chave)
    if appid is not None:
        da_steam = _nomes_de(foto).get(appid, "")
        if da_steam:
            return (da_steam, appid)
        do_lancador = _nome_no_catalogo(f"steam_app_{appid}", foto)
        return (do_lancador, "") if do_lancador else ("", appid)
    do_catalogo = _nome_no_catalogo(chave, foto)
    return (do_catalogo, "") if do_catalogo else ("", chave)


def _quando_usar(match: Any, base: str, foto: _FotoDoCatalogo | None = None) -> str:
    """A coluna «Funciona em» na MESMA língua do campo do editor."""
    procedencia, _recado = _procedencia_e_recado(match, foto=foto)
    if not procedencia or procedencia == PROCEDENCIA_DE_QUALQUER_JOGO:
        return base
    from hefesto_dualsense4unix.profiles.simple_match import simple_extra

    nome, codigo = _nome_e_codigo(simple_extra(match) if match is not None else "", foto)
    return SEPARADOR_DA_PROCEDENCIA.join(
        p for p in (procedencia, nome, codigo) if p)


def _procedencia_e_recado(match: Any, recado_do_produto: Any = "",
                          foto: _FotoDoCatalogo | None = None) -> tuple[str, str]:
    """``(procedência, recado)`` do campo «Funciona em:» — e nunca os dois cheios.

    Procedência vazia quer dizer o que o `ambiente_travado` do produto sempre
    quis dizer: **esta tela não sabe descrever esta regra**, o campo vai travado
    com a frase do que ela é, e o `match` do disco fica intacto. Não há estado
    novo aqui — há a MESMA válvula do R-12, falando a língua nova.

    **ELA É O ÚNICO DONO DA PERGUNTA**, e por isso a pintura e os dois gestos
    (`editor_ambiente`, `editor_jogo`) a chamam em vez de lerem
    `editor["ambiente_travado"]`. Ler o booleano do produto travaria a
    «Navegação»: `browser` está em `perfis_web.FORA_DO_DESENHO`, então o produto
    responde *"não sei mostrar"* sobre um preset que a tela nova SABE mostrar
    desde hoje — e ela ganharia uma opção que o gesto ao lado recusaria.
    """
    from hefesto_dualsense4unix.profiles.simple_match import procedencia_do_match

    procedencia = procedencia_do_match(
        match, _lancador_da_chave if foto is None
        else (lambda chave: _lancador_da_chave(chave, foto)))
    if procedencia:
        return (procedencia, "")
    return ("", str(recado_do_produto or ""))


def _html_do_ambiente(opcoes: list[str], atual: str) -> str:
    """As `<option>` do «Funciona em:» — a lista desta máquina, pronta.

    ELA VIAJA PELO `blocos`, como a lista de perfis e a dos jogos, e pela mesma
    razão escrita em `_html_da_lista`: **um bloco cujo número de filhos muda com
    o dado não tem endereço para o filho que ainda não existe.** O desenho tem
    os lançadores de uma máquina de exemplo; a máquina de quem instalou hoje
    pode não ter nenhum.

    O TRAVESSÃO VEM JUNTO E DESABILITADO, igual ao do desenho: é onde o
    `escrever()` do piloto pousa o `—` de um perfil cuja regra a tela não sabe
    mostrar. Sem ele o `el.value = '—'` não casa nada, o campo fica com a opção
    do MOCKUP — a tela afirmando uma regra que não é — e o contador de pinturas
    soma +1 por tique para sempre. Medido no DOM vivo em 04/09/2026.
    """
    linhas = [f'<option value="{_atr(TRAVESSAO)}" disabled>{_texto(TRAVESSAO)}'
              f'</option>']
    linhas += [f'<option{" selected" if o == atual else ""}>{_texto(o)}</option>'
               for o in opcoes]
    return "".join(linhas)


def _valendo(ctx: Contexto, todos: list[Any] | None = None) -> str:
    """Qual perfil está valendo AGORA, **com o nome que a LISTA mostra**.

    `profiles_actions.perfil_que_esta_valendo` é o §P1 desta casa, e esta aba
    era o lugar mais caro para não o chamar: ela lia
    `ctx.state.get("active_profile")` cru, e a própria docstring de lá diz que o
    daemon responder `active_profile: null` é *"o estado da máquina dela hoje"*.
    Com o `null`, as três guardas desta aba se desligavam ao mesmo tempo:

        ativar     deixava de recusar o perfil que JÁ está valendo
        remover    deixava de recusar apagar o perfil que está valendo —
                   e o daemon segue aplicando um arquivo que não existe mais
        voltar…    deixava de reaplicar depois de restaurar, e o arquivo voltava
                   ao que era com o controle no que estava

    E a lista perdia o realce da linha certa. O dono consulta o daemon primeiro
    e, só se ele calar, o marcador em disco — pelo mesmo caminho do boot
    (`resolve_boot_profile`). Ele nunca levanta: qualquer falha de I/O vira
    `nao_sei`, que aqui é o `""`.

    **O `find_by_slug` NO FIM É A SEGUNDA METADE, e sem ele a mesma tela dava
    DOIS vereditos** — 02/09/2026. O que vem do daemon ou do marcador é um NOME
    DIGITADO, e daqui ele seguia cru para dois comparadores diferentes:

        o realce da lista   `perfis_web._linhas_da_lista:358` faz `p.name == ativo`
        as guardas dos gestos  `mesmo_slug` (R-10), em `ativar` e `voltar…`

    MEDIDO com 33 perfis no disco e o daemon calado, marcador em `sackboy` e o
    perfil chamado `Sackboy`:

        realce -> []                     (nenhuma das 33 linhas se acende)
        Ativar -> "já é o perfil que está valendo"   (a guarda por slug pega)

    Duas guardas, dois vereditos, uma tela — e o marcador em caixa diferente é
    exatamente o caso que `find_by_slug` existe para cobrir (a docstring dele
    cita "Navegação"/"Navegacao"). **O dono passa a ser UM SÓ:** o nome é
    resolvido aqui, contra os perfis do disco, e sai já sendo o `p.name` de uma
    linha da lista. O `==` de lá não pode mais discordar do `mesmo_slug` daqui.

    **E O MARCADOR ÓRFÃO CAI JUNTO** — perfil renomeado ou apagado por fora. O
    `resolve_boot_profile` declara na própria docstring que *"só resolve NOMES —
    não valida se o perfil carrega"*; o que ele devolve ia CRU para o REALCE DA
    LISTA e para o alvo dos gestos. Sem casar com ninguém, o nome vira `""` —
    que aqui é "não há", e a lista não acende linha nenhuma.

    **FATO ERRADO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito que o nome
    cru ia também *"para o chip 'Perfil ativo'"*, e que a cura o levava ao
    travessão. **O chip não passa por aqui, e continua nomeando o órfão.** Ele
    é `<span class="pa-nome" data-campo="perfil">` (o chip «Perfil ativo», nas
    duas páginas), do `topo.html`, que é das dez abas — e quem o pinta é
    `pacotes.topo()`, com `ctx.state.get("active_profile")` CRU. Medido pelo
    caminho do piloto (`pacote_da_pagina` → `normalizar` → `topo` com
    `setdefault`), dois perfis no disco e dublê de ponte:

        daemon diz              chip na tela            linhas realçadas
        "Perfil Que Ela Apagou" "Perfil Que Ela Apagou"  []
        "sackboy"               "sackboy"                ["Sackboy"]

    A segunda linha é a pior: a MESMA tela passa a dar dois nomes para a mesma
    pergunta. A cura mora no dono compartilhado (`pacotes/__init__.py`, `topo`),
    que tem de resolver o nome do mesmo jeito — **não aqui**: um pacote de aba
    que emitisse `perfil` seria o segundo dono do cabeçalho, que é o defeito
    fotografado às 04:23 de 02/09 na aba Sistema e está escrito em
    `a09_sistema.pacote`. A dívida tem régua própria, em
    `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`.

    **LISTA VAZIA NÃO É PROVA DE ÓRFÃO — é a AUSÊNCIA de prova**, e essa
    distinção é a que impede a cura de desarmar o §P7. Só se rebaixa o nome a
    `""` quando há uma lista contra a qual conferi-lo; sem lista, o nome cru
    segue, e `ativar`/`remover` continuam recusando. Medido em 02/09/2026: sob
    o `pytest` a `conftest.py:1327` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, e
    `load_all_profiles()` devolve **[]** — sem esta guarda, todas as réguas
    desta aba passariam a medir o ramo vazio e a guarda de apagar o perfil que
    vale ficaria verde sem existir.

    `todos` é para quem já leu o disco neste tique: `pacote()` roda a cada
    500 ms e chama `load_all_profiles()` uma vez; ler 33 arquivos duas vezes por
    tique seria pagar de novo o que já está na mão. Os gestos chamam sem ele —
    são um clique, não um laço.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    nome = str(perfil_que_esta_valendo(ctx.state).nome or "")
    if not nome:
        return ""
    if todos is None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        try:
            todos = list(load_all_profiles())
        except Exception:
            return nome
    if not todos:
        return nome
    achado = find_by_slug(nome, todos)
    return str(getattr(achado, "name", "") or "") if achado is not None else ""


def _rotulo_do_remover(alvo: str) -> str:
    """"Remover", ou a PERGUNTA que a dica dela promete — sobre o alvo de AGORA.

    A dica no desenho diz *"Apaga do disco. Pergunta antes."* — e esta janela
    não tem diálogo. O `on_profile_remove` da janela estável abre um
    `gui_dialogs.confirm_delete_profile` (`profiles_actions.py`), que é
    GTK e MODAL; daqui não dá para abri-lo, porque **os gestos rodam em
    thread** (`hefesto_vivo.py:2703`) e GTK só aceita diálogo no laço principal.

    **FATO CADUCO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito que *"a
    recusa do piloto não serve de pergunta: ela sai em `stderr`, no terminal,
    onde a dona não está olhando"*. **Não sai mais.** O piloto ganhou
    `_recusou_dizendo` (`hefesto_vivo.py:2786`): todo `RuntimeError` de gesto
    virava TARJA na tela — no cartão do controle quando a página tinha um, e no
    `document.body` quando não tinha, o caso desta aba —, até 13/09/2026, quando
    a recusa passou ao diário e à piscada do botão (FRASES-E-DICAS-01).

    **O RÓTULO CONTINUA SENDO A PERGUNTA, e agora por outra razão:** a tarja é
    AVISO e o rótulo é ESTADO. A tarja conta o que acabou de acontecer e vai
    embora em trinta segundos; o rótulo diz, enquanto o armamento vive, qual
    perfil o próximo clique apaga. Com só a tarja, ela leria "Apagar
    “Pragmata”?" e teria oito segundos para decidir olhando um botão que diz
    "Remover".

    O rótulo é o pedaço de tela que
    já existe, que ela está olhando no instante do clique, e que o piloto sabe
    pintar. O desenho não muda: o mockup continua escrevendo "Remover".

    **O `alvo` É A CURA DE 02/09/2026, e sem ele o botão ANUNCIAVA UM PERFIL E
    APAGAVA OUTRO.** O armamento sempre foi por perfil — `remover` exige
    `_ARMADO[0] == nome` — mas este rótulo olhava só o RELÓGIO, e por isso
    continuava perguntando pelo perfil armado depois de ela clicar noutra linha.
    **A SEQUÊNCIA, MEDIDA PASSO A PASSO** — dois perfis no disco, dublê de
    ponte, ninguém valendo. A coluna ANTES é este rótulo sem o `== alvo` (a
    mordida); a coluna DEPOIS é o de hoje:

        passo                          ANTES                      DEPOIS
        1 clicou na linha do Pragmata  "Remover"                  "Remover"
        2 CLIQUE em Remover            arma o Pragmata, levanta   igual
        3 o rótulo, no tique seguinte  "Remover “Pragmata”? …"    igual
        4 clicou na linha do Sackboy   "Remover “Pragmata”? …"    "Remover"
        5 CLIQUE em Remover            arma o SACKBOY, levanta    igual
        6 o rótulo, no tique seguinte  "Remover “Sackboy”? …"     igual
        7 CLIQUE em Remover            APAGA o Sackboy            igual

    **UM ÚNICO PASSO DIFERE, e é o 4 — o defeito inteiro está ali:** o botão
    anuncia que o próximo clique apaga o Pragmata, e o próximo clique arma o
    Sackboy.

    **FATO ERRADO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito *"três
    cliques num botão que nunca deixou de dizer 'Pragmata' apagam o Sackboy"*, e
    que o passo 5 armava *"calado"*. A medição acima derruba as duas: no passo
    6, **ainda sem a cura**, o rótulo já diz "Sackboy" — dentro de um tique de
    500 ms —, então o clique que APAGA nunca acontece sob um botão dizendo
    "Pragmata". E o "calado" é o que menos se sustenta hoje: com
    `_recusou_dizendo` no piloto, o passo 5 **põe a frase em TARJA na tela**, e
    o rótulo fala meio segundo depois. Exagerar o defeito não o torna mais real,
    e a próxima pessoa leria isto como o enunciado.

    Com o alvo, o rótulo volta a "Remover" no instante em que ela troca de
    linha — que é a verdade: o próximo clique naquele botão ARMA, não apaga.
    """
    if (_ARMADO and _ARMADO[0] == alvo
            and (time.monotonic() - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR):
        return f"Remover “{_ARMADO[0]}”? Clique de novo"
    return "Remover"


LUGARES_DA_TABELA = len(TODOS_OS_LUGARES)


def _com_os_lugares_vazios(
    da_mesa: list[Any], para_o_vazio: Callable[[int], Any]
) -> list[Any]:
    """A lista da mesa completada até os quatro lugares do desenho.

    NASCEU EM 05/09/2026, da palavra dela — *"os svgs não deveriam aparecer prós
    demais controles desconectados"*. Antes disto o pacote mandava só as linhas
    da mesa e o `forEach` do bootstrap escrevia `''` no que sobrava. `''` serve
    para APAGAR (uma classe, uma cor, um texto) e nunca para ACENDER — e o
    lugar vazio precisa acender uma classe (`fora`) e escrever um rótulo
    (`P3 • Desconectado`). Sem as quatro, os dois voltam a ser do desenho, que
    é quem não sabe quantos controles estão na mesa.

    ``para_o_vazio`` recebe o NÚMERO do lugar (1..4) e devolve o valor daquela
    linha — uma função, e não um valor fixo, porque o rótulo do lugar vazio traz
    o próprio número.

    Sobra de mesa não é aparada: uma mesa maior que o desenho é outro defeito, e
    escondê-lo aqui faria esta função mentir sobre o tamanho da tabela.
    """
    completa = list(da_mesa)
    for n in range(len(completa) + 1, LUGARES_DA_TABELA + 1):
        completa.append(para_o_vazio(n))
    return completa


@registrar("10-perfis.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `app/actions/perfis_web.pacote_da_aba` — a camada do PRODUTO."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    try:
        todos = os_perfis_de_escolher(load_all_profiles())
        foto = _foto_do_catalogo()
        ativo = _valendo(ctx, todos)
        escolhido = _escolhido([{"nome": x.name} for x in todos], ativo)
        alvo = find_by_slug(escolhido, todos)
        bruto = _tela.pacote_da_aba(todos, ativo=ativo or None,
                                    mesa=_mesa_com_rotulo(ctx.mesa, getattr(ctx, "conectados", ())),
                                    editado=alvo)
    except Exception:
        return {"sem_dono": {}, "cobertura": {"pintados": 0, "sem_dono": 1}}

    lista = _ordenada(_filtrada(_com_a_procedencia(bruto.get("lista") or [], todos, foto)))
    editor = bruto.get("editor") or {}
    fora = {
        "perfis.conta": bruto.get("conta", "—"),
        "perfis.com-ajuste": bruto.get("com_ajuste", ""),
        "perfis.linha.nome": [x.get("nome", "") for x in lista],
        "perfis.linha.prioridade": [x.get("prioridade", "") for x in lista],
        "perfis.linha.quando": [x.get("quando", "") for x in lista],
        "perfis.procura": _PROCURA,
        "perfis.procura.conta": (f"{len(bruto.get('lista') or []) - len(lista)} "
                                 f"fora da busca" if _PROCURA.strip() else ""),
        **{f"perfis.ordem.{c}": (_seta_da_coluna(c)) for c in COLUNAS_DA_LISTA},
        "perfis.larguras": _larguras_em_texto(TABELA_DA_LISTA),
        "guarda.larguras": _larguras_em_texto(TABELA_DA_GUARDA),
        # quem o pinta é `pacotes.topo()` — o dono das dez abas.
        "quantos": len(lista),
        "travado": bool(ctx.state.get("freestyle_ligado")),
        "sem_dono": {},
    }
    for chave in ("nome", "jogo", "estilo", "ambiente"):
        fora.setdefault(f"editor.{chave}", "—")
    fora.setdefault("editor.prioridade.n", "—")
    fora.setdefault("editor.prioridade.dica", "")
    for chave, valor in editor.items():
        if not isinstance(valor, (dict, list)):
            fora[f"editor.{chave.replace('_', '.')}"] = valor
    fora["editor.prioridade"] = str(editor.get("prioridade") or "0").rstrip("%")

    # Estilo faz com a opção vazia dela.
    if editor:
        fora["editor.prioridade.escolha"] = str(editor.get("prioridade_n") or "0")

    exigencia = _exigencia_para_esta_tela(getattr(alvo, "match", None))
    fora["editor.jogo.exigencia"] = exigencia
    fora["editor.jogo.exige"] = "sim" if exigencia else ""

    # o campo seria ler a tela — e a tela é justamente o que este rótulo explica.
    # ELE NÃO ENTRA EM `CAMPOS_QUE_ELA_DIGITA`: ninguém digita dentro de um
    rotulo, alerta = _jogo_reconhecido(str(editor.get("jogo") or ""), foto)
    fora["editor.jogo.rotulo"] = rotulo
    fora["editor.jogo.alerta"] = "sim" if alerta else ""

    for chave in _uma_vez_so(str(getattr(alvo, "name", ""))):
        fora.pop(chave, None)

    fora["perfis.remover"] = _rotulo_do_remover(escolhido)

    fora["perfis.desfecho"] = _desfecho_para_a_tela()

    guarda = bruto.get("guarda") or []
    if isinstance(guarda, list):
        # ela decide as duas metades de uma vez: o pacote passa a mandar as
        nomes_da_mesa = [g.get("nome", "") for g in guarda]
        fora["guarda.nome"] = _com_os_lugares_vazios(
            nomes_da_mesa,
            lambda n: f"P{n} {PONTO_DO_ROTULO} {SEM_NINGUEM_AQUI}")
        fora["guarda.vazio"] = _com_os_lugares_vazios(
            ["" for _ in guarda], lambda _n: "sim")
        fora["guarda.id"] = _com_os_lugares_vazios(
            [g.get("id", "") for g in guarda], lambda _n: "")
        # barra de 3px que diz de quem é a linha, e ela era o `--plastico` do
        fora["guarda.plastico"] = _com_os_lugares_vazios(
            [g.get("plastico", "") for g in guarda], lambda _n: "")
        # FATO DERRUBADO, e ele estava aqui: a linha era
        # **dicionário** (`perfis_web._secoes_do_controle` devolve
        estado = getattr(ctx, "state", None) or {}
        agora = [o_agora_da_linha(g, estado) for g in guarda]
        vazio = [("", "") for _ in SECOES_DA_COLUNA]
        celulas = [c for bloco in _com_os_lugares_vazios(agora, lambda _n: vazio)
                   for c in bloco]
        fora["guarda.secao"] = [valor for valor, _dica in celulas]
        fora["guarda.incerto"] = ["sim" if valor == AGORA_NAO_DIZ else ""
                                  for valor, _dica in celulas]
        fora["guarda.dica"] = [dica for _valor, dica in celulas]
        por_linha = [
            ["sim" if (g.get("secoes") or {}).get(secao) else ""
             for secao in SECOES_DA_COLUNA]
            for g in guarda
        ]
        fora["guarda.proprio"] = [
            valor
            for bloco in _com_os_lugares_vazios(
                por_linha, lambda _n: ["" for _ in SECOES_DA_COLUNA])
            for valor in bloco
        ]
        fora["guarda.linhas"] = str(len(guarda))

    # linha com a medição. (Este comentário dizia "OS QUATRO" quando a lista
    for chave in NAO_PINTAVEIS:
        fora.pop(chave, None)

    # achar o `<tbody>`; numa página que mude o seletor, a pintura campo a campo
    escolhido_na_lista = str(getattr(alvo, "name", "") or escolhido)

    # e é uma sobrescrita de propósito: `perfis_web` continua servindo o
    procedencia, recado = _procedencia_e_recado(
        getattr(alvo, "match", None), editor.get("ambiente_recado"), foto)
    fora["editor.ambiente"] = procedencia
    fora["editor.ambiente.travado"] = not procedencia
    fora["editor.ambiente.recado"] = recado

    fora["blocos"] = {
        SELETOR_DA_LISTA: _html_da_lista(
            lista, str(bruto.get("lista_vazia") or ""), escolhido_na_lista),
        SELETOR_DO_AMBIENTE: _html_do_ambiente(
            oferta_do_funciona_em(_procedencias_da_maquina(foto), procedencia),
            procedencia),
        SELETOR_DOS_JOGOS: _html_dos_jogos(procedencia, foto),
    }
    fora["cobertura"] = {"pintados": len(fora) + len(lista) * 3, "sem_dono": 0}
    return fora


from . import gesto  # noqa: E402


@gesto("10-perfis.html", "selecionar")
def selecionar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Abrir um perfil no editor. É o clique em QUALQUER CÉLULA da linha.

    ELE NÃO FALA COM O DAEMON, e é o único desta aba que não fala — de
    propósito. Escolher uma linha não muda nada no aparelho; muda o ALVO dos
    botões ao lado, que é o que a janela estável faz no
    `on_profile_selection_changed` (`profiles_actions.py`). Ligar isto ao
    `profile.switch` faria passar o mouse pela lista trocar o perfil que está
    valendo — o oposto da coluna ter um botão "Ativar".

    E ELE NÃO RESPONDE CALADO: o editor ao lado repinta no tique seguinte com a
    preferência daquele perfil (`editor.prioridade.n`). O campo Nome ainda não
    acompanha, e o motivo está no relato — ele é um `<input>`, e a pintura
    escreve `textContent` nele, que não aparece.

    O NOME VEM DA LINHA, desde 02/10/2026 (A-LINHA-INTEIRA-ABRE-O-PERFIL-01): o
    gesto mora na `<tr>`, e o ouvinte do piloto manda o `dataset` inteiro do
    alvo (`hefesto_vivo.py`, `Object.assign({}, d)`) — o `data-hef-perfil`
    chega como `hefPerfil`, com o nome vivo que `_linha_da_lista` escreve. O
    `texto` da linha seria as três células coladas («Pragmata80Steam · …»); ele
    fica como volta para quem chama o gesto com `{"texto": nome}`.
    """
    global _ESCOLHIDO
    nome = str(o.get("hefPerfil") or o.get("texto") or "").strip()
    if not nome:
        raise ValueError("selecionar: o clique não trouxe o nome do perfil")
    _ESCOLHIDO = nome


@gesto("10-perfis.html", "ativar")
def ativar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Ativar o perfil selecionado na tabela. `profile.switch`.

    O NOME VEM DO TEXTO DA LINHA, e não de um `data-` novo: a tabela já mostra o
    nome, e é o nome que o `profile.switch` quer. Marcar um segundo endereço com
    o mesmo valor seria a segunda verdade que esta casa persegue.

    DUAS CORREÇÕES DE 01/09/2026, ao ligar o resto da aba — e as duas são o
    mesmo defeito, que é o botão dizer "aplicado" sem ter aplicado:

    1. **A LINHA NÃO ERA CLICÁVEL.** O gesto lê o texto da linha, mas nenhum
       elemento da lista tinha endereço — o ouvinte do piloto casa
       `[data-gesto],[data-hef-gesto],…` (`hefesto_vivo.py:845`) e a `<tr>` só
       trazia `data-hef-perfil`. Quem clicava num perfil não mandava nada; quem
       clicava no BOTÃO mandava `texto="Ativar"`, e o gesto pedia ao daemon um
       perfil chamado "Ativar". Agora a célula do nome marca `selecionar`, e o
       botão age sobre o escolhido — o `_ESCOLHIDO` vem primeiro, e o `texto`
       fica como último recurso (é o que a prova declarada exercita).
    2. **A RECUSA DO DAEMON SUMIA.** `profile_switch` devolve `False` quando ele
       não confirmou (`ipc_bridge.py:196`, ATIVAR-NAO-MENTE-01) e o retorno era
       descartado: o piloto imprimia "→ aplicado" sobre uma troca que não
       aconteceu. Levantar aqui é o que faz o botão recusar dizendo.
    """
    nome = _ESCOLHIDO or str(o.get("texto") or "").strip()
    if not nome:
        raise RuntimeError("ativar: escolha um perfil na lista primeiro")
    # `mesmo_slug` e não `==`: com "Navegação" no disco e "Navegacao" no daemon
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        raise RuntimeError(
            f"“{nome}” já é o perfil que está valendo. Escolha outro na lista "
            f"da esquerda e clique em Ativar — reativar o mesmo não muda nada, "
            f"e dizer “aplicado” seria mentira.")
    # esse corpo desde sempre — `mensagem_de_ativacao(name, result)`
    # (`ponte.TETOS["profile.switch"]` == `ipc_bridge.PROFILE_SWITCH_TIMEOUT_S`,
    try:
        corpo = p.resultado("profile.switch", name=nome)
    except RuntimeError as erro:
        raise RuntimeError(
            f"o Hefesto não confirmou a troca para {nome!r}") from erro
    # A FRASE É DO PRODUTO. `mensagem_de_ativacao` cai na frase de sempre
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_de_ativacao,
    )

    frase = mensagem_de_ativacao(nome, corpo)
    # (`profiles_actions.py`). Sem ela, o `launch_env.refresh` que esta aba
    return _dizer(_com_a_carona(frase))


@gesto("10-perfis.html", "voltar-a-de-ontem", grava="restaurar_do_historico")
def voltar_a_de_ontem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Desfazer a última gravação do perfil aberto. `profiles/loader.py`.

    O QUE ELE DESFAZ, e o produto já sabia fazer isto pelo terminal:
    `save_profile` copia o arquivo ANTERIOR para `profiles/.historico/<slug>/`
    a cada gravação (PERFIL-SEM-RASTRO-01, `loader.py:1230`), e
    `restaurar_do_historico` devolve a mais recente **byte a byte**
    (`loader.py:1509`). O único chamador até hoje era `profile restore` da CLI
    (`cli/cmd_profile.py:254`) — este é o segundo, e é uma tela.

    POR QUE NÃO PEDE CONFIRMAÇÃO, e é a diferença dele para o "Remover": a
    própria restauração ARQUIVA a versão atual antes de substituí-la, então
    restaurar por engano também tem volta. É o desfazer, não a perda.

    AS DUAS CHAMADAS DEPOIS DO DISCO NÃO SÃO ENFEITE:

    * `profile.reaplicar` — **o daemon não relê JSON de perfil por conta
      própria** (PERFIL-SAVE-APPLY-01, `profiles_actions.py`). Sem ele o
      arquivo volta ao que era e o controle continua com o de agora, que é o
      sintoma que ela leu como "não está salvando". Só quando o perfil restaurado
      é o que está VALENDO: reaplicar outro trocaria o perfil pelas costas dela.
      NOTA DATADA — 01/10/2026: era o `profile.switch`, a ativação À MÃO, e o
      desfazer de um perfil de jogo posto pelo autoswitch o gravava como a
      escolha dela (O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01).
    * `launch_env.refresh` — a regra pode ter mudado, e com ela o
      `steam_app_<id>.env` de antecipação. É o mesmo aviso que o Salvar e o
      Remover da janela estável mandam (`footer_actions.py:101`), e a ordem é a
      de lá: reaplicar primeiro, avisar depois.

    A COMPARAÇÃO É POR SLUG, não por string: com "Navegação" no disco e
    "Navegacao" no daemon, um `==` cru diria que são perfis diferentes e o
    reaplicar não aconteceria (R-10, `profiles/slug.py:37`).

    E ELE PASSOU A DIZER QUAL VERSÃO VOLTOU — 03/09/2026. **É o gesto em que o
    silêncio era mais caro desta aba**: o arquivo inteiro dela é substituído por
    outro, e a tela não mudava nada que ela pudesse ver (o editor mostra nome e
    regra; o que volta é gatilho, luz, vibração, máscara). Um desfazer mudo é
    indistinguível de um desfazer que não pegou.

    A FRASE É A DA CLI, que era o único chamador antes desta tela: *"perfil
    restaurado: X (versão …)"* (`cli/cmd_profile.py:263`). O carimbo da versão
    entra porque é ele que o `profile historico` lista  (noqa-acento: nome do
    subcomando da CLI, ASCII em `cmd_profile.py:211`) — é o que ela digita para
    voltar a outra, e sem ele a frase não diz de onde veio.

    O NOME, E NÃO O CAMINHO: a CLI imprime o `Path` que `restaurar_do_historico`
    devolve, porque quem lê está no terminal. A tira mostra o nome do perfil,
    que é como a lista ao lado o chama. E o carimbo vai sem o `.json` — é a
    forma que o `--em` do `profile restore` aceita (`loader.py:1478` casa as
    duas), então a frase é copiável para o comando que volta a outra versão.
    """
    from hefesto_dualsense4unix.profiles.loader import restaurar_do_historico
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    nome = _ESCOLHIDO or _valendo(ctx)
    if not nome:
        raise RuntimeError("voltar à de ontem: escolha um perfil na lista primeiro")
    _, versao = restaurar_do_historico(nome)
    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        p.profile_reaplicar(nome)
    p.chamar("launch_env.refresh")
    return _dizer(_com_a_carona(
        f"Perfil restaurado: {nome} · versão {versao.stem}"))


#     2. reaplica, se for o ativo   `profile.switch` — o daemon NÃO relê JSON de
#     3. avisa a antecipação    `launch_env.refresh` — a regra pode ter mudado,


def _perfil_do_editor(ctx: Contexto) -> str:
    """O perfil em que o editor está aberto. Vazio é RECUSA, nunca "o primeiro"."""
    nome = _ESCOLHIDO or _valendo(ctx)
    if not nome:
        raise RuntimeError("escolha um perfil na lista primeiro — a coluna da "
                           "esquerda; o editor abre na linha que você clicar.")
    return nome


def _o_perfil_no_disco(nome: str) -> Any:
    """`load_profile(nome)`: a base de todo gesto do editor que grava.

    O gesto lê o perfil do disco, muda o campo que ela editou e grava o
    perfil inteiro, sem nada do aparelho (decisão `D-2709-O-SALVAR-LE-O-PERFIL`):
    as outras abas gravam as escolhas delas no clique, e o estado vivo não é
    escolha dela. Até 27/09 esta base punha o vivo por cima, e mudar a
    PRIORIDADE ligava o microfone de um controle no PRAGMATA dela.

    A VOLTA É PELO NOME QUE O PERFIL TEM: quem renomeia (`editor_nome`) o faz
    DEPOIS, por `model_copy`. O `DraftConfig.to_profile` com um nome novo zera
    `match`, `mode` e `suppress_desktop_emulation` de propósito (R-11), e é
    por isso que nenhum gesto do editor passa pelo rascunho.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return load_profile(nome)


#: INVERSÃO de `perfis_web.AMBIENTE_DO_PRESET`, e não uma segunda tabela: o
#: `from_simple_choice` faz com chave desconhecida (`simple_match.py:167`), e
PRESET_DO_ROTULO = {v: k for k, v in _tela.AMBIENTE_DO_PRESET.items()}


_CARONA_PENDENTE: str = ""


def _gravar(prof: Any, ctx: Contexto, p: Any, *, era: str = "") -> None:
    """Os três tempos: disco, reaplicar se for o ativo, avisar a antecipação.

    O CORPO MUDOU DE CASA em 01/09/2026, e a razão é que ele ganhou um SEGUNDO
    chamador: o `a06_navegacao`, que devolve os atalhos de botão ao de fábrica,
    precisa exatamente destes três tempos. Uma segunda cópia é a que esquece o
    `launch_env.refresh` no dia em que alguém mexer numa só — então o corpo foi
    para `pacotes/perfil.py`, que é o módulo que as abas já compartilham, e este
    nome fica como a porta desta aba.

    E A CARONA ENTROU AQUI — 06/09/2026, o que a `ONDA5-07-02` mediu e deixou no
    colo desta frente. O censo por árvore de sintaxe daquela sprint achou NOVE
    gestos desta aba que gravam o perfil INTEIRO sem repor o atalho de
    inicialização que a Steam come: os OITO que passam por este funil
    (`editor.nome`, `editor.prioridade`, `editor.ambiente`, `editor.estilo`,
    `editor.jogo`, `detectar`, `novo`, `duplicar` — OITO) mais o
    `voltar-a-de-ontem`, que tem funil próprio.

    ERAM NOVE ATÉ 11/09/2026: o `editor.modo` passava por aqui e saiu com o
    quadro «Modo», por ordem dela. O funil não muda — o que muda é quem entra
    nele.

    **AQUI E NÃO EM `perfil.gravar_e_reaplicar`**, e a razão é medida e está
    escrita lá: aquela função tem SEIS chamadores em CINCO abas, e a interface
    nova é de ação imediata — clicar num tom ou num degrau de vibração já grava.
    Pendurar a carona lá seria uma varredura do `localconfig.vdf` **por
    clique**, que é a opção que o dono da carona pesou e RECUSOU. Este funil é o
    único cujos gestos são o perfil INTEIRO, e não um campo.

    A NOTÍCIA NÃO SE PERDE, e é a diferença entre pegar a carona e pegá-la em
    silêncio: `_com_a_carona("")` devolve só a notícia (vazia quando não há
    nada a repor), ela fica em `_CARONA_PENDENTE`, e o `_dizer` do gesto a
    junta ao desfecho dele. Sem isto, o reparo aconteceria e a tira diria só
    "renomeado" — o mesmo silêncio que o desfecho inteiro existe para curar.
    """
    global _CARONA_PENDENTE
    perfil.gravar_e_reaplicar(prof, ctx, p, era=era)
    _CARONA_PENDENTE = _com_a_carona("")


def _nome_livre(base: str, todos: Any) -> str:
    """`base`, ou `base 2`, `base 3`… — o primeiro que não colide por SLUG."""
    from hefesto_dualsense4unix.profiles.slug import slugify

    usados = {slugify(x.name) for x in todos}
    if slugify(base) not in usados:
        return base
    n = 2
    while slugify(f"{base} {n}") in usados:
        n += 1
    return f"{base} {n}"


_ARMADO_REBAIXAR: tuple[str, float] | None = None


def _pergunta_antes_de_rebaixar(prof: Any, chave: str) -> None:
    """Trocar "Funciona em" para "Todos" APAGA a regra. Pergunta antes."""
    global _ARMADO_REBAIXAR
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label
    from hefesto_dualsense4unix.profiles.schema import MatchAny

    if chave != "any" or isinstance(prof.match, MatchAny):
        _ARMADO_REBAIXAR = None
        return
    agora = time.monotonic()
    if (_ARMADO_REBAIXAR and _ARMADO_REBAIXAR[0] == prof.name
            and (agora - _ARMADO_REBAIXAR[1]) < SEGUNDOS_PARA_CONFIRMAR):
        _ARMADO_REBAIXAR = None
        return
    _ARMADO_REBAIXAR = (prof.name, agora)
    raise RuntimeError(
        f"O perfil “{prof.name}” não vale para tudo hoje — hoje ele é: "
        f"{_match_label(prof.match)}. Trocar para “Todos” faz ele valer para "
        f"TUDO (Quando usar: Sempre) e apaga os programas em que ele valia. "
        f"Escolha “Todos” de novo para confirmar — o campo espera oito segundos.")


_NOMES_DOS_JOGOS: tuple[tuple[tuple[str, int], ...], dict[str, str]] | None = None


def _nomes_dos_jogos() -> dict[str, str]:
    """``{appid: nome}`` do disco, relido só quando a biblioteca muda."""
    global _NOMES_DOS_JOGOS
    from hefesto_dualsense4unix.integrations.jogos_locais import (
        assinatura_da_biblioteca,
        catalogo_de_jogos,
        nomes_por_appid,
    )

    assinatura = assinatura_da_biblioteca()
    if _NOMES_DOS_JOGOS is not None and _NOMES_DOS_JOGOS[0] == assinatura:
        return _NOMES_DOS_JOGOS[1]
    nomes = nomes_por_appid(catalogo_de_jogos())
    _NOMES_DOS_JOGOS = (assinatura, nomes)
    return nomes


def _forma_do_que_ela_escolheu(texto: str) -> str:
    """Que FORMA de regra este texto pede, quando o seletor não disse nada."""
    from hefesto_dualsense4unix.profiles.simple_match import normalize_appid

    if normalize_appid(texto) is not None:
        return "steam_game"
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            jogo_da_janela,
            jogos_de_janela,
        )

        achado = jogo_da_janela(texto, jogos_de_janela())
    except Exception:
        return "game"
    return achado.forma if achado is not None else "game"


def _jogo_reconhecido(texto: str, foto: _FotoDoCatalogo | None = None) -> tuple[str, bool]:
    """``(frase, é_alerta)`` para o campo do jogo — a decisão da janela estável.

    JOGO-QUE-SE-DIZ-01. `851100` sozinho não diz nada a ninguém, nem a ela daqui
    a um mês: a janela estável põe o nome do jogo ao lado do campo
    (`profile_jogo_reconhecido`, `profiles_actions._atualizar_frase_do_jogo`).

    **E ESTA ABA PASSOU A TER O RÓTULO — 06/09/2026, decisão 10-Q4 dela**:
    *"Rótulo ao lado, ao vivo — à direita do campo aparece o nome do jogo (…),
    ou «não está nesta máquina», ou «não reconheci este endereço»"*. O desfecho
    do gesto continua dizendo o nome; o rótulo é o segundo lugar, e é o que
    responde SEM ela ter de gravar nada.

    O BOOLEANO DEIXOU DE MORRER AQUI, e era ele que faltava. Até 06/09 esta
    função devolvia só a PRIMEIRA metade do par e jogava fora o `é_alerta` que
    `frase_do_campo_do_jogo` devolve — o mesmo bit que separa *"não instalado
    aqui (o número vale)"*, que é rotina, de *"não reconheci este endereço"*,
    que é erro. Sem ele o rótulo não tem como se pintar, e as duas frases sairiam
    da mesma cor.

    A DECISÃO É DA FUNÇÃO PURA DO PRODUTO, e não desta tela:
    `jogos_locais.frase_do_campo_do_jogo(texto, nomes)` é a MESMA que alimenta o
    rótulo de lá, com as MESMAS quatro respostas — nome do jogo, "não instalado
    aqui (o número vale)", "não reconheci este endereço" e o silêncio de quem
    ainda está digitando. Escrever um `if` aqui seria a segunda verdade sobre o
    que é um jogo reconhecido.

    **A QUINTA RESPOSTA CHEGOU COM O TERCEIRO ARGUMENTO — 11/09/2026, e é a
    queixa dela fechada.** O `<datalist>` passou a oferecer jogo de lançador,
    cujo `value` é a `wm_class` (``gotg.exe``), e o «Detectar» sempre gravou
    essa classe para um jogo de fora da Steam. Sem as `chaves`, as duas
    deixavam o rótulo MUDO: o botão respondia *"PRAGMATA"* a um jogo da Steam
    e **nada** a um do Heroic — exatamente o silêncio que a decisão 10-Q4 dela
    existe para fechar.

    NUNCA LEVANTA, e é o mesmo contrato de `_com_a_carona`: ela é acabamento de
    um gesto que JÁ GRAVOU — e, desde o rótulo, também é PINTURA, chamada dez
    vezes por segundo. Uma exceção lendo a biblioteca dela transformaria uma
    gravação bem-sucedida em tarja de recusa, e derrubaria a aba inteira por
    causa de um rótulo.
    """
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            frase_do_campo_do_jogo,
            nomes_das_janelas,
        )

        decisao = frase_do_campo_do_jogo(texto, _nomes_de(foto),
                                         nomes_das_janelas())
    except Exception:
        return ("", False)
    if decisao is None:
        return ("", False)
    return (str(decisao[0]), bool(decisao[1]))


def _agora_vale_em(prof: Any, texto: str = "") -> str:
    """A frase de desfecho de quem trocou a REGRA do perfil. Um dono, três gestos.

    O RÓTULO SAI DE `_match_label`, a mesma função pura que alimenta a coluna
    "Quando usar" — pelo argumento que `_pergunta_antes_de_rebaixar` já usa
    logo acima: *o desfecho não pode chamar de outra coisa um perfil que a
    lista chama de "Só manual"*.

    `texto` É O QUE ELA DIGITOU (ou o que o «Detectar» achou: o appid da Steam
    **ou a `wm_class`**, desde 11/09/2026), e serve só para o nome do jogo.
    Vazio, a frase termina no rótulo — que é o certo para "Todos" e "Steam",
    onde jogo nenhum entra na regra.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

    frase = f"“{prof.name}” agora vale em: {_match_label(prof.match)}"
    jogo = _jogo_reconhecido(texto)[0] if texto else ""
    return f"{frase} · {jogo}" if jogo else frase


def _so_mudou(o: dict[str, Any]) -> bool:
    """`False` quando o clique foi só um clique — e aí o campo não age."""
    return str(o.get("evento") or "") in ("", "change")


@gesto("10-perfis.html", "editor.nome", grava="_gravar")
def editor_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Renomear o perfil aberto no editor. `save_profile` + `delete_profile`.

    O VALOR VEM DE `valor`, E NÃO DE `texto` — foi a causa nomeada na primeira
    leva: *"o ouvinte manda `texto: alvo.textContent`, que num `<input>` é
    vazio"*. Desde 01/09 o clique traz o `value` do campo
    (`hefesto_vivo.py:1401`) e o piloto escuta `change` além de `click`, que é o
    único evento que um campo de texto dispara com o valor novo.

    POR QUE RENOMEAR NA HORA, e não guardar num rascunho: decisão dela de
    01/09 — *"clicar na cor já deveria aplicar a cor no controle"* —, e esta aba
    não tem "Salvar" próprio (o do rodapé regrava o perfil ATIVO como o disco
    o tem, `rodape._draft_do_ativo`, e nem olha para este campo). Um
    campo que aceita texto e não guarda nada é o botão que responde calado.

    NÃO HÁ `rename` NO PRODUTO — medido: `profiles/loader.py` tem
    `save_profile`, `delete_profile`, `load_profile` e `restaurar_do_historico`,
    e nenhum renomeia. A janela estável faz a mesma dupla no Salvar, com o
    diálogo do R-10 se oferecendo para apagar o antigo. Aqui a ordem é gravar
    PRIMEIRO e apagar depois: invertida, uma falha no meio perderia o perfil.

    E O ANTIGO NÃO SOME DE VEZ: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). Um renomear por engano se desfaz com
    `hefesto-dualsense4unix profile restore <nome-antigo>`.

    AS DUAS RECUSAS:

    * nome vazio — apagar o campo não pode virar um arquivo `.json`;
    * nome que já é de OUTRO perfil — o `save_profile` grava por SLUG, então
      renomear "Elden Ring" para "Pragmata" gravaria por cima do Pragmata dela,
      calado. É o mesmo estrago que o `_nome_livre` evita no Duplicar.

    E ELE PASSOU A DIZER QUE RENOMEOU — 03/09/2026, ver `_dizer`. O campo
    voltava ao normal e mais nada: um gesto que APAGA um `.json` e cria outro
    terminava mudo, e o único jeito de saber que pegou era esperar a lista
    repintar. A frase é a do produto, `mensagem_do_salvar(nome, renomeado_de=…)`
    (`profiles_actions.py`) — a MESMA que o rodapé da janela estável
    escreve, "Perfil renomeado: era → novo".

    SEM `reaplicou=`, e é o honesto: quem reaplica é `gravar_e_reaplicar`, que
    devolve `None` (`pacotes/perfil.py:339`). Deduzir aqui se o daemon recebeu
    seria a segunda verdade sobre uma coisa que este gesto não mediu — e a
    frase de três estados de `mensagem_do_salvar` existe exatamente para não
    prometer o controle quando ninguém olhou para ele.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_do_salvar,
    )
    from hefesto_dualsense4unix.profiles.loader import (
        delete_profile,
        load_all_profiles,
    )
    from hefesto_dualsense4unix.profiles.slug import slugify

    if not _so_mudou(o):
        return None
    novo = str(o.get("valor") or "").strip()
    era = _perfil_do_editor(ctx)
    if not novo:
        raise RuntimeError("o perfil precisa de um nome — o campo ficou vazio.")
    prof = _o_perfil_no_disco(era)
    if prof.name == novo:
        return None
    troca_de_arquivo = slugify(novo) != slugify(prof.name)
    if troca_de_arquivo:
        for outro in load_all_profiles():
            if slugify(outro.name) == slugify(novo):
                raise RuntimeError(
                    f"já existe um perfil chamado “{outro.name}”. Escolha outro "
                    f"nome — gravar este por cima apagaria o dele.")
    _gravar(prof.model_copy(update={"name": novo}), ctx, p, era=era)
    if troca_de_arquivo:
        delete_profile(era)
    _ESCOLHIDO = novo
    return _dizer(mensagem_do_salvar(novo, renomeado_de=prof.name))


@gesto("10-perfis.html", "editor.prioridade", grava="_gravar")
def editor_prioridade(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Prioridade": o número que decide quem vence quando dois perfis servem."""
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_do_salvar,
    )
    from hefesto_dualsense4unix.profiles.schema import (
        PRIORIDADE_MAXIMA,
        PRIORIDADE_MINIMA,
    )

    if not _so_mudou(o):
        return None
    cru = str(o.get("valor") or "").strip()
    nome = _perfil_do_editor(ctx)
    try:
        novo = int(float(cru))
    except ValueError:
        raise RuntimeError(
            f"a preferência tem de ser um número, e o campo mandou “{cru}”. "
            f"Nada foi salvo.") from None
    if not PRIORIDADE_MINIMA <= novo <= PRIORIDADE_MAXIMA:
        raise RuntimeError(
            f"a preferência {novo} está fora da faixa que o perfil aceita "
            f"({PRIORIDADE_MINIMA} a {PRIORIDADE_MAXIMA}). Nada foi salvo.")
    prof = _o_perfil_no_disco(nome)
    if int(prof.priority or 0) == novo:
        return None
    _gravar(prof.model_copy(update={"priority": novo}), ctx, p)
    resposta = _dizer(f"{mensagem_do_salvar(prof.name)} · preferência {novo}")
    pct = round(novo * 100 / PRIORIDADE_MAXIMA) if PRIORIDADE_MAXIMA else 0
    resposta["mesa"]["editor.prioridade"] = str(pct)
    resposta["mesa"]["editor.prioridade.n"] = str(novo)
    return resposta


@gesto("10-perfis.html", "editor.ambiente", grava="_gravar")
def editor_ambiente(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Funciona em": trocar a REGRA que faz o perfil entrar. `from_simple_choice`.

    QUEM MONTA A REGRA É O PRODUTO, e não este arquivo:
    `profiles/simple_match.from_simple_choice:203` é a mesma função que o Salvar
    da janela estável usa (`profiles_actions._build_profile_from_editor`), com
    as frases de recusa já escritas em português ("Diga o número do jogo na
    Steam (ex.: 1599660)"). Montar um `MatchCriteria` aqui seria a segunda
    verdade sobre o que cada opção significa.

    O `regra_do_disco` NÃO É ENFEITE: para "Jogo da Steam" ele preserva o
    `process_name` do MESMO jogo, que ela nunca viu na tela e portanto nunca
    pediu para tirar (ESCONDER-EM-VEZ-DE-SAIR-01, `simple_match.py:277`).

    AS DUAS RECUSAS, e as duas existem para não REBAIXAR a regra dela:

    * **o seletor travado** — quando o perfil casa por uma regra que esta tela
      não sabe mostrar (`window_title_regex`, lista de classes), o produto abre
      o campo travado com a frase do que fazer (`perfis_web.py:91`). Aceitar a
      troca ali seria o defeito R-12: substituir uma regra fina por "Todos".
      MEDIDO: sete dos nove perfis de fábrica caem nesse estado.
    * **"Estilo de Jogo"** — é a quinta opção do desenho e não tem preset
      nenhum atrás. `from_simple_choice` devolve `MatchAny()` para chave
      desconhecida, sem reclamar (`simple_match.py:167`): escolher "Estilo de
      Jogo" gravaria um catch-all no lugar da regra do jogo dela, em silêncio.

    **E O CAMPO PASSOU A DIZER DE ONDE O JOGO VEM — C4-FUNCIONA-EM,
    11/09/2026, desenho DELA.** O que chega agora é uma PROCEDÊNCIA
    («Navegação», «Steam», «Heroic», «Qualquer jogo»…), e quem a traduz na
    forma técnica é `simple_match.forma_da_procedencia` — o produto, sozinho,
    com o que o lançador entrega. A recusa do "Estilo de Jogo" deixou de ser
    necessária pelo caminho mais simples: ele **saiu deste campo** e ficou no
    campo próprio, uma linha abaixo.

    **A GUARDA NOVA É A DA FORMA PRESERVADA, e ela não é zelo.** Se a
    procedência escolhida é a MESMA que o campo já mostrava, o gesto não grava
    nada. Sem isso, um perfil em «Instalado aqui» cuja regra é por
    `process_name` (``guard``, medido no disco dela) seria reescrito como
    `window_class` por um gesto que não mudou nada na tela — trocar um dado
    por outro que *"casa por acaso"* é o R-12 que esta casa já pagou. Quem
    quiser mudar de verdade muda a opção, e aí a reescrita é o que ela pediu.
    """
    from hefesto_dualsense4unix.profiles.simple_match import (
        MSG_ESCOLHA_O_JOGO,
        forma_da_procedencia,
        from_simple_choice,
    )

    if not _so_mudou(o):
        return None
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    nome = _perfil_do_editor(ctx)
    prof = _o_perfil_no_disco(nome)
    editor = _editor_de(prof)
    agora, recado = _procedencia_e_recado(
        getattr(prof, "match", None), editor.get("ambiente_recado"))
    if not agora:
        raise RuntimeError(recado)
    if rotulo == agora:
        return None
    if rotulo in (TRAVESSAO, ""):
        raise RuntimeError(
            f"“{TRAVESSAO}” não é uma procedência — ele é o que a tela mostra "
            f"quando não sabe descrever a regra do perfil. Escolha de onde o "
            f"jogo vem.")
    # baixo junto não muda nada — `from_simple_choice` não lê `custom_name`
    jogo = "" if rotulo in _PROCEDENCIAS_SEM_JOGO else str(editor.get("jogo") or "")
    achado = _jogo_da_procedencia(rotulo, jogo) if jogo else None
    if achado is not None:
        jogo = achado.valor
    elif rotulo not in _PROCEDENCIAS_SEM_JOGO and rotulo != PROCEDENCIA_DA_STEAM:
        raise RuntimeError(MSG_ESCOLHA_O_JOGO.format(procedencia=rotulo))
    chave = forma_da_procedencia(
        rotulo, jogo,
        forma_do_catalogo=str(getattr(achado, "forma", "") or ""))
    _pergunta_antes_de_rebaixar(prof, chave)
    prof.match = from_simple_choice(chave, jogo, regra_do_disco=prof.match)
    _gravar(prof, ctx, p)
    return _dizer(f"“{prof.name}” agora vale em: {rotulo}")


def _com_o_estilo(prof: Any, estilo: Any, mesa: list[dict[str, Any]]) -> tuple[Any, int]:
    """O perfil com a receita do estilo dentro, e QUANTOS controles ganharam cor.

    AS TRÊS COISAS QUE O ESTILO ESCREVE são as que ela aprovou em 03/09/2026 ao
    mandar construir o motor — **gatilho + vibração + luz** —, e cada uma vai
    para o lugar que já era dela no esquema:

        `estilo.gatilho`  → `triggers.left/right.mode`, nos DOIS lados
        `estilo.vibracao` → `rumble.policy` (o degrau, não um multiplicador)
        a cor            → `controllers[uniq].leds`, **uma por unidade**

    OS PARÂMETROS DO GATILHO NÃO SÃO DIGITADOS. `Estilo.gatilho` guarda só a
    CHAVE do modo (`AutoGun`, `PulseB`…), e as factories do produto exigem
    posicionais sem default — um `params=[]` passaria pelo esquema e explodiria
    lá no `apply()`, ou pior: `simple_rigid` com zonas zeradas é *"nenhuma zona
    ativa"*, o gatilho fica solto e a tela diz que aplicou. Quem sabe os números
    é `app/actions/trigger_specs.PRESETS`, e `preset_to_positional_params(spec,
    {})` devolve exatamente o padrão de cada modo. É a mesma porta que a aba
    Gatilhos usa (`a03_gatilhos._padroes`).

    A LUZ É POR UNIDADE PORQUE A LEI É DELA, verbatim: *"nenhuma cor dos
    controles nunca pode ser a mesma, mesmo no mesmo perfil e estilo de jogo.
    Dentro da paleta de fps tem que ter variações pra cada unidade de
    controle."* Quem garante isso, medindo, é `estilos_de_jogo.as_quatro` — e
    por isso a cor sai de `cor_da_unidade(estilo, jogador)`, nunca de uma cor
    escrita aqui. **O global `leds` NÃO é tocado**: uma cor no global é a cor
    que os quatro herdariam, que é exatamente o defeito que a lei dela proíbe.

    E DOIS CONTROLES NO MESMO LUGAR É RECUSA, não escolha silenciosa: dois
    `jogador` iguais na mesa dariam a MESMA cor às duas peças, com o motor
    inocente. É o único caminho pelo qual a lei dela cairia depois de o motor
    dizer que está tudo distinto.

    `LedsConfig` COM DOIS CAMPOS SÓ, e isso é contrato: `_controllers_to_specs`
    lê `model_fields_set` (`profiles/manager.py`), então escrever `lightbar` e
    `lightbar_brightness` deixa `player_leds` e `auto_player_colors` SEM
    OPINIÃO — o controle continua herdando o resto do perfil. Um `LedsConfig`
    "cheio" apagaria os LEDs de jogador de quem nunca pediu isso.
    """
    from hefesto_dualsense4unix.app.actions import trigger_specs as specs
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import cor_da_unidade
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        RumbleConfig,
        TriggerConfig,
        TriggersConfig,
        com_o_brilho_das_luzes_de,
    )

    mudanca: dict[str, Any] = {}
    if estilo.gatilho:
        spec = specs.get_spec(estilo.gatilho)
        if spec is None:  # pragma: no cover — o motor só nomeia modo do produto
            raise RuntimeError(
                f"o estilo “{estilo.rotulo}” pede o gatilho {estilo.gatilho!r}, "
                f"que não é um dos modos do produto. Nada foi salvo.")
        lado = TriggerConfig(
            mode=estilo.gatilho,
            params=list(specs.preset_to_positional_params(spec, {})))
        mudanca["triggers"] = TriggersConfig(left=lado, right=lado)
    if estilo.vibracao:
        # CONSTRUÍDO, e não `model_copy`: o `custom_mult` do perfil antigo é
        mudanca["rumble"] = RumbleConfig(
            passthrough=bool(getattr(prof.rumble, "passthrough", True)),
            policy=estilo.vibracao)

    atuais = dict(prof.controllers or {})
    lugares: dict[int, str] = {}
    pintados = 0
    for controle in mesa:
        uniq = str(controle.get("uniq") or "").replace(":", "").lower()
        try:
            jogador = int(controle.get("jogador"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not uniq or not 1 <= jogador <= 4:
            continue
        if jogador in lugares and lugares[jogador] != uniq:
            raise RuntimeError(
                f"dois controles estão no lugar P{jogador}, e o estilo "
                f"daria a MESMA cor aos dois — a regra é que nenhum controle "
                f"repete a cor de outro. Nada foi salvo.")
        lugares[jogador] = uniq
        dele = atuais.get(uniq) or ControllerOverrides()
        novos = LedsConfig(
            lightbar=cor_da_unidade(estilo, jogador),
            lightbar_brightness=estilo.brilho,
            lightbar_para_o_numero=jogador)
        atuais[uniq] = dele.model_copy(
            update={"leds": com_o_brilho_das_luzes_de(dele.leds, novos)})
        pintados += 1
    if pintados:
        mudanca["controllers"] = atuais
    return prof.model_copy(update=mudanca), pintados


@gesto("10-perfis.html", "editor.estilo", grava="_gravar")
def editor_estilo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Estilo de Jogo": escolher um APLICA a receita inteira no perfil.

    **ELE GANHOU MOTOR EM 03/09/2026, e a decisão de construí-lo é dela.**
    Perguntada se o motor devia existir, respondeu *"Construir o motor"*, e
    escolheu o alcance: **gatilho + vibração + luz**. As receitas estão
    em `profiles/estilos_de_jogo.py` — *"o resto ta aprovado"* —, e é de lá que
    saem tanto os rótulos do `<select>` (`aba10.ESTILOS`) quanto o que cada um
    faz. **Não há tabela de estilo neste arquivo**, e não pode haver: uma
    segunda cópia da receita divergiria no dia em que ela mudasse uma.

    O QUE ELE ERA ATÉ HOJE DE MANHÃ, medido no produto instalado com o daemon
    dela vivo e um DualSense White no cabo:

        estilo_na_tela: "Terror"      ← a tela AFIRMA o estilo, e continua
        tarjas: []                    ← ninguém disse nada
        md5 de meu_perfil.json:  b4387a17…  ANTES **e** DEPOIS — nada gravou

    À tarde ele passou a RECUSAR dizendo, o que já era melhor que o silêncio.
    Agora ele **grava** — e é a diferença entre a tela pedir desculpa e a tela
    fazer o trabalho.

    O ESTILO NÃO FICA GUARDADO NO PERFIL, e isso é a coisa mais importante a
    entender aqui: `Profile` não tem campo de estilo, e não ganhou um. O estilo
    é um **verbo**, não um campo — ele resolve gatilho, vibração e luz de uma
    vez, e a partir daí quem manda são esses três, que ela pode reajustar nas
    abas sem nada "voltar atrás". Por isso `editor.estilo` continua em
    `NAO_PINTAVEIS` e o `<select>` continua abrindo no travessão: afirmar um
    estilo depois do clique seria a tela dizendo que guardou o que não guardou.

    "PERSONALIZADO" NÃO MEXE EM NADA, e é o único que responde sem gravar. Ele é
    o estilo que diz *"eu ajusto na mão"* — `as_quatro()` levanta de propósito se
    alguém lhe pedir a cor. A resposta é um DESFECHO (a tira do rodapé), não uma
    tarja de recusa: escolher "Personalizado" é uma escolha legítima, e recusar
    dizendo faria a tela tratar de erro o que é o comportamento pedido.

    `RuntimeError` NAS RECUSAS — ver `RECUSA-CHEGA-NA-TELA-01`, no alto do
    arquivo: é a única classe que `_recusou_dizendo` leva ao DOM.

    ELE SAIU DE `SEM_ECO`, e continua fora: o `state_full` não publica nada do
    conteúdo do perfil, então a gravação não ecoa — mas o `_gravar` chama
    `profile.switch` quando o perfil é o ativo, e é isso que faz a luz e o
    gatilho chegarem ao aparelho no mesmo segundo.
    """
    from hefesto_dualsense4unix.profiles import estilos_de_jogo as receitas

    # primeira escolha dela passar calada, que foi o defeito de manhã.
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    if escolhido == "—":
        escolhido = ""
    if not escolhido:
        raise RuntimeError(
            "escolha um Estilo de Jogo na lista — um Estilo de Jogo não foi "
            "salvo, e o que vale continua sendo o que está nas abas.")
    estilo = receitas.POR_ROTULO.get(escolhido)
    if estilo is None:
        raise RuntimeError(
            f"“{escolhido}” não é um dos Estilos de Jogo do produto. Nada foi "
            f"salvo, e o que vale continua sendo o que está nas abas.")
    nome = _perfil_do_editor(ctx)
    if estilo.chave == "personalizado":
        return _dizer(
            f"“{estilo.rotulo}” não mexe em nada: é o estilo que diz “eu ajusto "
            f"na mão”. O que vale em “{nome}” continua sendo o que está nas abas.")
    prof = _o_perfil_no_disco(nome)
    novo, pintados = _com_o_estilo(prof, estilo, ctx.mesa)
    _gravar(novo, ctx, p)
    luz = (f"e a luz de {pintados} controle{'s' if pintados != 1 else ''}"
           if pintados else "e nenhum controle ligado para acender")
    return _dizer(
        f"“{estilo.rotulo}” aplicado em “{prof.name}”: gatilho, vibração {luz}.")


@gesto("10-perfis.html", "editor.jogo", grava="_gravar")
def editor_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Nome do Jogo": o programa (ou o número da Steam) que faz o perfil entrar.

    ELE SÓ TEM EFEITO EM DUAS DAS CINCO OPÇÕES do "Funciona em":
    `from_simple_choice` só lê o `custom_name` em "game" e "steam_game"
    (`simple_match.py:155-166`). Com o seletor em "Todos" ou "Steam", o texto
    seria descartado sem uma palavra — ela digitaria o nome do jogo, veria o
    campo aceitar, e a regra continuaria a mesma.

    ENTÃO O SELETOR ANDA JUNTO, e isso desfaz um IMPASSE que eu mesmo criei e
    medi antes de entregar: com o perfil em "Todos", escolher "Jogo" no seletor
    recusava por falta de nome (`MSG_JOGO_SEM_NOME`), e digitar o nome recusava
    por o seletor estar em "Todos". **Os dois caminhos fechados, e o perfil
    preso em "Todos" para sempre.** Digitar o nome de um jogo é dizer "este
    perfil é deste jogo": o gesto grava a regra inteira, e o seletor mostra o
    resultado no tique seguinte.

    O PRODUTO JÁ FAZ ISSO, e não é invenção desta tela: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py`) chama
    `_select_radio("steam_game")` **e** preenche o campo, no mesmo gesto.

    QUAL DAS DUAS ELE ESCOLHE: `normalize_appid` decide — só dígitos (ou um
    endereço da loja, que ele sabe ler) é "Jogo da Steam"; qualquer outra coisa
    é "Jogo", com o nome do programa. E ele SÓ decide quando o seletor não
    estava numa das TRÊS que têm campo livre: com "Jogo", "Jogo da Steam" ou
    "Jogo (pela janela)" já escolhido por ela, a escolha dela manda — digitar
    "1245620" num perfil que ela pôs em "Jogo" não pode virar um perfil da
    Steam pelas costas dela. (A terceira entrou em 06/09/2026, ONDA5-10-01.)

    R-12: o nome do programa vai **como ela digitar**, sem `.lower()` — o
    matcher compara com o basename cru de `/proc/PID/exe`, e
    `Cyberpunk2077.exe` nunca casaria com `cyberpunk2077.exe`.

    E ELE PASSOU A DIZER O QUE GRAVOU — 03/09/2026. Ele **reescreve a regra
    INTEIRA** do perfil e movia o seletor junto, calado: ela digitava um número,
    o campo aceitava, e o único sinal era o `<select>` mudar no tique seguinte.
    O desfecho nomeia as duas coisas que mudaram — o rótulo novo do "Quando
    usar" e, quando o número é de um jogo que esta máquina conhece, o NOME dele.
    É o degrau que faltava para ela conferir o que digitou (JOGO-QUE-SE-DIZ-01).

    **E O CAMPO SE CORRIGE — 04/09/2026, decisão [04] do PO.** Colar o endereço
    da loja funciona: `normalize_appid` lê o número de dentro dele e a regra
    grava o número. O que ficava errado era a TELA — o campo continuava
    mostrando `https://store.steampowered.com/app/1599660/…` sobre uma regra que
    já guardava `1599660`, e assim ficava até ela trocar de perfil. A janela
    antiga trocava o endereço pelo número na frente dela.

    **A CORREÇÃO SÓ CABE AQUI, e a razão é medida:** `editor.jogo` está em
    `CAMPOS_QUE_ELA_DIGITA`, logo o tique NÃO o repinta enquanto ela está no
    mesmo perfil (senão a pintura apagaria a segunda tecla que ela digita). O
    único instante em que a tela pode devolver a forma canônica é a resposta
    deste gesto — e ela é pintada na hora, sem esperar os 500 ms.

    O VALOR SAI DE `simple_extra(prof.match)`, e não de um `if` meu: é a MESMA
    função que `perfis_web._pacote_do_editor` usa para encher este campo a cada
    tique. Escrever aqui "o appid quando é steam_game, o texto quando não é"
    seria a segunda verdade sobre o que este campo mostra — e as duas
    divergiriam no dia em que a regra ganhasse uma terceira forma.
    """
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        simple_extra,
    )

    if not _so_mudou(o):
        return None
    texto = str(o.get("valor") or "").strip()
    nome = _perfil_do_editor(ctx)
    prof = _o_perfil_no_disco(nome)
    editor = _editor_de(prof)
    _procedencia, recado = _procedencia_e_recado(
        getattr(prof, "match", None), editor.get("ambiente_recado"))
    if not _procedencia:
        raise RuntimeError(recado)
    # (`process_name` contra `wm_class`), e quem a nomeia é `AMBIENTE_DO_PRESET`.
    chave = PRESET_DO_ROTULO.get(str(editor.get("ambiente") or ""))
    if chave not in ("game", "steam_game", "janela"):
        chave = _forma_do_que_ela_escolheu(texto)
    prof.match = from_simple_choice(chave, texto, regra_do_disco=prof.match)
    _gravar(prof, ctx, p)
    return _dizer(_agora_vale_em(prof, texto),
                  **{"editor.jogo": simple_extra(prof.match) or texto})


def _classe_de_outro_app(ctx: Contexto) -> str:
    """A `wm_class` da última janela que NÃO é a nossa — `""` quando não há."""
    from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

    for chave in ("window_detect_last_class", "window_detect_current_class"):
        classe = str(ctx.state.get(chave) or "").strip()
        if not classe or classe == "unknown":
            continue
        if classe.casefold() in OWN_GUI_WM_CLASSES:
            continue
        return classe
    return ""


@gesto("10-perfis.html", "detectar", grava="_gravar")
def detectar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Detectar": pegar o jogo em foco e montar a regra com ele.

    A AFIRMAÇÃO QUE ESTAVA NO PRODUTO ESTÁ ERRADA PELA METADE, e é o que
    destravou este botão. `perfis_web.DONOS_DOS_GESTOS["detectar"]` diz *"o IPC
    NÃO PUBLICA o título nem a classe"* — e daí a primeira leva o deixou sem
    dono. MEDIDO em 01/09/2026, contra o daemon `dev` desta árvore, com
    `ipc_bridge.daemon_state_full()`: das 49 chaves do `state_full`, SETE são
    de detecção de janela, e duas delas são a classe —
    `window_detect_last_class` e `window_detect_current_class`. O TÍTULO é que
    não é publicado. A janela estável já lia exatamente esta chave desde o
    PERFIL-NASCE-CERTO-01 (`profiles_actions._aplicar_nascimento_com_jogo`).

    O QUE ELE FAZ E O QUE AINDA NÃO FAZ:

    * **jogo da Steam** — a classe vem como `steam_app_<id>` e o appid sai dela
      pela fonte única do produto (`profiles/steam_app.steam_appid_from_wm_class`,
      UNIFICA-PREDICADO-01). A regra vira "Jogo da Steam" com aquele número.
    * **jogo de fora da Steam** — GRAVA A CLASSE, desde 06/09/2026
      (ONDA5-10-01). A regra vira "Jogo (pela janela)" com aquela `wm_class`.

      **AQUI ESTAVA ESCRITA UMA RECUSA, e o raciocínio dela estava certo e a
      conclusão não seguia.** Ele dizia: *"o detector entrega uma wm_class, e o
      produto só sabe guardá-la como `MatchCriteria(window_class=…)`, que é uma
      regra que este editor não sabe MOSTRAR — o perfil abriria travado, com a
      frase de usar a linha de comando. Gravar isso a partir de um botão seria
      empurrar o perfil dela para fora da tela."* Se gravar a regra empurra o
      perfil para fora da tela, **o conserto é a tela aprender a regra**, e foi
      o que a sprint fez: `simple_match` ganhou o preset `"janela"`, e os TRÊS
      seletores ganharam o rótulo antes de este botão gravar um byte.

      O que continua valendo daquele bloco é a outra metade, e ela é o motivo
      de o preset novo NÃO ser `process_name`: é outro dado (o basename de
      `/proc/PID/exe`), e casaria por acaso.

    * **nenhuma janela em foco** — RECUSA, e é a única recusa honesta que
      sobrou: `classe` vazia ou `"unknown"` é o caso em que o detector não viu
      nada. Ela continua nomeando o que viu.

    `last_class` ANTES de `current_class`: a primeira é a última classe ÚTIL
    vista (`launch_wrapper_dialog.py:45`) e sobrevive ao foco ir para a janela
    do Hefesto — que é exatamente o que acontece quando ela clica neste botão.

    E ELE PASSOU A DIZER O QUE ACHOU — 03/09/2026. A recusa já nomeava a classe
    que o detector estava vendo; o SUCESSO não dizia nada, e é o caso em que
    dizer vale mais: o botão grava um appid que ela não digitou, vindo de uma
    janela que ela não está mais olhando. O desfecho devolve o NOME do jogo
    (`_jogo_reconhecido`), que é a única forma de ela conferir que o detector
    pegou o jogo certo e não o launcher que estava por cima.
    """
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        simple_extra,
    )
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    nome = _perfil_do_editor(ctx)
    classe = _classe_de_outro_app(ctx)
    if not classe:
        crua = str(ctx.state.get("window_detect_current_class") or "").strip()
        vendo = f" (estou vendo «{crua}»)" if crua and crua != "unknown" else ""
        raise RuntimeError(
            "não achei janela de jogo em foco — o detector não está vendo "
            f"nenhuma{vendo}. Abra o jogo, deixe-o em foco por um instante e "
            "clique de novo.")
    prof = _o_perfil_no_disco(nome)
    appid = steam_appid_from_wm_class(classe)
    if appid is not None:
        prof.match = from_simple_choice("steam_game", str(appid),
                                        regra_do_disco=prof.match)
        _gravar(prof, ctx, p)
        return _dizer(_agora_vale_em(prof, str(appid)),
                      **{"editor.jogo": simple_extra(prof.match) or str(appid)})
    prof.match = from_simple_choice("janela", classe)
    _gravar(prof, ctx, p)
    return _dizer(_agora_vale_em(prof, classe),
                  **{"editor.jogo": simple_extra(prof.match) or classe})


@gesto("10-perfis.html", "novo", grava="_gravar")
def novo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Novo": um perfil em branco no disco, já com a regra do jogo em foco.

    NASCE NO DISCO, e não num rascunho, porque esta aba não tem "Salvar"
    próprio — a janela estável só PREENCHE O EDITOR (`on_profile_new:3016`) e
    quem grava é o botão seguinte. Aqui, com a ação imediata que ela pediu, o
    arquivo nasce e a lista o mostra no tique seguinte, já aberto no editor.

    A REGRA DO JOGO EM FOCO É A MESMA DO PRODUTO, e a guarda também: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py`) só age quando há
    **appid da Steam**, e devolve `False` calado no resto. É o que este gesto
    faz — com jogo da Steam em foco nasce mirando aquele jogo, sem ele nasce
    catch-all, "que é o certo para um perfil de desktop" (palavras de lá).

    **A PRIORIDADE DEIXOU DE NASCER EM ZERO** — 03/09/2026,
    PERFIL-NASCE-CERTO-01. Aqui estava escrito que a conta *"mora num mixin GTK
    que depende de widget"*. **Não depende.** O corpo de
    `_prioridade_acima_dos_catch_all` (`profiles_actions.py:416`) lê UM
    atributo — `self._profiles_cache`, a lista de perfis — e mais nada: sem
    `Gtk`, sem `self._get`, sem widget. O que faltava era alguém lhe entregar a
    lista, e esta aba já a tem na mão.

    O DEFEITO QUE ISSO FECHA foi medido em 26/07 com ela jogando: o perfil que
    ela criou para o Pragmata nasceu prioridade 0 e NUNCA valia no jogo, porque
    o catch-all dela (prioridade 100) vencia em todo o resto. **Ela não errou a
    configuração — a janela não tinha saída**, e um perfil novo desta tela caía
    no mesmo buraco. Medido no disco dela hoje: os catch-all são `meu_perfil`
    (1) e `fallback` (0), então a folga sai **11** — e os perfis de jogo dela
    estão em 80, o que continua sendo o certo: a conta promete vencer os
    "vale sempre", não vencer todo mundo.

    A CHAMADA É À FUNÇÃO DA JANELA, e não a uma segunda conta: o mixin é uma
    classe, e um método que só lê `getattr(self, "_profiles_cache", None)` roda
    com qualquer objeto que tenha esse atributo. Copiar `max(catch-all) + 10`
    para cá seria a segunda verdade sobre quem vence a disputa — e o teto
    (`PRIORIDADE_MAXIMA`), a folga (`_FOLGA_ACIMA_DO_CATCH_ALL`) e a regra do
    que É catch-all (`Profile.e_catch_all`) ficariam com dois donos.

    Ele NÃO é ativado: nascer não é passar a valer.

    **E NASCE SEM A SEÇÃO `mode` — decisão desta sprint, 11/09/2026.** Com o
    quadro «Modo» fora do editor (ordem dela), a pergunta *"que modo tem um
    perfil criado aqui?"* deixou de ter quem a responda na tela, e alguém tinha
    de decidir. É `None`, que é o que `Profile` já faz sozinho, e o valor tem
    nome na tela dela: **«Não mexer no modo»** — o perfil sem opinião, que entra
    e deixa o modo como estiver.

    POR QUE ESTE E NÃO OUTRO: é o único que preserva o comportamento de HOJE.
    Antes de 06/09 o campo não era alcançável por esta tela e todo perfil nascia
    assim; nos cinco dias em que o quadro existiu, quem não o tocou continuou
    nascendo assim. Qualquer outro padrão faria um perfil novo passar a MEXER no
    modo da máquina dela sem que ninguém tivesse pedido — que é a cicatriz do
    `or "xbox"` do Salvar da janela estável (ESCOLHA-DELA-VENCE-01/E1).

    QUEM MUDA DEPOIS É A ABA JOGAR, e nada aqui zera o campo de um perfil que já
    o tem: este gesto cria arquivo novo, não reescreve os dela.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    classe = _classe_de_outro_app(ctx)
    appid = steam_appid_from_wm_class(classe) if classe else None
    regra = (from_simple_choice("steam_game", str(appid)) if appid is not None
             else MatchAny())
    return _dizer(_nascer(ctx, p, regra, "Novo perfil"))


def _nascer(ctx: Contexto, p: Any, regra: Any, base: str) -> str:
    """O perfil novo no disco, já aberto no editor — o gravador dos dois caminhos."""
    global _ESCOLHIDO
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import Profile

    todos = list(load_all_profiles())
    nome = _nome_livre(base, todos)
    so_o_cache: Any = SimpleNamespace(_profiles_cache=todos)
    prioridade = ProfilesActionsMixin._prioridade_acima_dos_catch_all(so_o_cache)
    _gravar(Profile(name=nome, match=regra, priority=prioridade), ctx, p)
    _ESCOLHIDO = nome
    return (f"Perfil criado: {nome} · preferência {prioridade}, acima dos "
            f"que valem sempre")


def criar_para_o_jogo(ctx: Contexto, p: Any, *, classes: tuple[str, ...],
                      nome_do_jogo: str) -> str:
    """O perfil novo para UM jogo escolhido na aba Lançadores. Devolve a frase."""
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    limpas = tuple(c.strip() for c in classes if c.strip())
    appid = steam_appid_from_wm_class(limpas[0]) if limpas else None
    if appid is not None:
        regra: Any = from_simple_choice("steam_game", str(appid))
    else:
        regra = MatchCriteria(window_class=list(limpas))
    try:
        return _nascer(ctx, p, regra, nome_do_jogo.strip() or "Novo perfil")
    except ValueError:
        return _nascer(ctx, p, regra, "Novo perfil")


@gesto("10-perfis.html", "duplicar", grava="_gravar")
def duplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Duplicar": o perfil inteiro numa cópia, e o editor abre nela.

    A DICA DELA DIZ *"Copia o perfil inteiro para o editor, com «(cópia)» no
    nome"*, e as três partes se cumprem — a última por consequência da segunda:
    a cópia nasce no disco e o `_ESCOLHIDO` passa a ser ela, então é ela que o
    editor pinta no tique seguinte.

    "O PERFIL INTEIRO" É LITERAL, e é a diferença para o defeito
    BUG-DUPLICATE-NO-CONFIG-COPY-01, que a janela estável já pagou: a cópia
    tinha só o nome trocado e o resto virava default. O `model_copy` do pydantic
    leva gatilhos, luz, vibração, alto-falante, máscara e os overrides por
    controle — tudo, menos o nome.

    E A CÓPIA NÃO É ATIVADA. Duplicar não é trocar o perfil que está valendo; a
    coluna tem um "Ativar" para isso. Por isso `_gravar` não reaplica aqui: o
    nome novo nunca é o ativo.

    O NÚMERO NO FIM ("(cópia) 2") NÃO É ENFEITE: sem ele, duplicar duas vezes o
    mesmo perfil gravaria a segunda cópia POR CIMA da primeira — `save_profile`
    escreve por slug.

    **"O PERFIL INTEIRO" TEM UMA EXCEÇÃO, E ELA É O CARIMBO DE PONTE** —
    03/09/2026, e era um defeito de comportamento. O `model_copy` levava o
    `ponte` junto, e a janela estável o CORTA de propósito: em
    `_build_profile_from_editor` o duplicar entra como estreia
    (`estreia = _new_profile or _duplicate_source is not None`,
    `profiles_actions.py`), o degrau 2 de `carimbo_que_o_save_leva` é
    cortado, e o degrau 1 — o disco, pelo nome NOVO — devolve `None`.

    POR QUE ISSO IMPORTA, e o cenário é o gesto seguinte ao duplicar: repontar a
    cópia para OUTRO jogo. Com o carimbo herdado, `pontes_confirmadas()` publica
    uma ponte que ninguém provou naquele appid, a escada de
    `integrations/ponte_escada.py` para num jogo nunca testado, e o produto jura
    saber o que não sabe. **O carimbo é REGISTRO de uma confirmação, não
    configuração que se copia.**

    A REGRA NÃO É REESCRITA AQUI: quem decide é `carimbo_que_o_save_leva`, o
    mesmo dono que a aba Perfis e o rodapé já consultam
    (`profile_writer.py:10`). Os argumentos são os do caso: `existente` é quem
    ocupa o nome novo em disco (ninguém — `_nome_livre` acabou de garantir), e
    não há rascunho. Se a escada mudar, esta linha muda com ela.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.app.actions.profile_writer import (
        carimbo_que_o_save_leva,
    )
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles, load_profile
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    era = _perfil_do_editor(ctx)
    todos = list(load_all_profiles())
    prof = load_profile(era)
    copia = _nome_livre(f"{prof.name} (cópia)", todos)
    carimbo = carimbo_que_o_save_leva(find_by_slug(copia, todos), None)
    _gravar(prof.model_copy(update={"name": copia, "ponte": carimbo}), ctx, p)
    _ESCOLHIDO = copia
    return _dizer(f"Cópia criada: {copia}")


@gesto("10-perfis.html", "remover", grava="delete_profile")
def remover(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Remover": apagar o perfil do disco. PERGUNTA ANTES, no rótulo do botão."""
    global _ARMADO, _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import delete_profile

    nome = _perfil_do_editor(ctx)
    # E ELA DECIDE MELHOR QUE UM `mesmo_slug` LOCAL: recebe o `PerfilQueVale`
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        frase_da_remocao_do_perfil_ativo,
        perfil_que_esta_valendo,
    )

    aviso = frase_da_remocao_do_perfil_ativo(nome, perfil_que_esta_valendo(ctx.state))
    if aviso:
        raise RuntimeError(aviso)
    agora = time.monotonic()
    armado = (_ARMADO and _ARMADO[0] == nome
              and (agora - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR)
    if not armado:
        _ARMADO = (nome, agora)
        raise RuntimeError(
            f"Apagar “{nome}” do disco? Clique em Remover de novo para "
            f"confirmar — o botão espera oito segundos.")
    _ARMADO = None
    delete_profile(nome)
    _ESCOLHIDO = ""
    # SEM `profile.switch` AQUI, de propósito: o perfil apagado não é o ativo
    p.chamar("launch_env.refresh")
    # `_dizer` E NÃO `_anotar` — 03/09/2026. Os dois guardam a frase; só o
    return _dizer(f"Perfil removido: {nome}")


@gesto("10-perfis.html", "recarregar")
def recarregar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Recarregar": reler a lista do disco AGORA, e dizer que releu.

    **ELE ERA UM BOTÃO MORTO COM APARÊNCIA DE VIVO** — 03/09/2026. O
    `data-hef-gesto="recarregar"` está na página desde 31/08 e não havia
    `@gesto`: o piloto caía no ramo do gesto SEM DONO, anotava `("sem dono", "")` e
    imprimia `[gesto sem dono] 10-perfis.html · recarregar` **no stdout de quem
    lançou a janela**. Ela clicava, nada acontecia, e nada dizia por quê — nem a
    tarja, porque `_recusou_dizendo` só pinta para exceção de HANDLER, e um
    gesto sem handler não chega lá.

    **O MOTIVO DE ELE TER FICADO SEM DONO CAIU, E CAIU PELA METADE QUE FALTAVA.**
    Estava escrito aqui que *"não há o que chamar: a lista já é relida do disco
    a cada 500 ms, então ligá-lo a um `load_all` extra seria fingir trabalho já
    feito"*. A premissa está certa e a conclusão não segue — a janela estável
    tem o MESMO botão, sobre uma lista que ela também mantém em cache
    (`on_profile_reload` → `_reload_profiles_store` + toast "Lista recarregada",
    `profiles_actions.py`). O trabalho que ele faz não é a leitura: é
    **dizer que leu**. Um botão cuja promessa é tranquilizar não fica mudo
    porque o produto já estava certo.

    O QUE ELE FAZ, e é o `_reload_profiles_store` desta tela: chama `pacote()`,
    que relê o disco, e devolve a carga INTEIRA — o `blocos` da lista, a
    contagem, o editor. A pintura acontece no ato (`_deu_certo` →
    `window.__hef.pintar`), não no tique seguinte, que é a diferença entre um
    botão que responde e um botão que parece não ter pego.

    NÃO FALA COM O DAEMON, e por isso não está em `PROVAS`: o disco é a fonte da
    lista, e o `state` que decide quem está ativo já chegou pelo tique. É o
    segundo gesto desta aba sem chamada de ponte — o outro é o `selecionar`.

    A FRASE É A DA JANELA ESTÁVEL, palavra por palavra: `"Lista recarregada"`
    (`profiles_actions.py`). O número de perfis vai junto porque é o que
    faz o clique VALER: ela relê para conferir que o perfil novo apareceu.
    """
    carga = pacote(ctx)
    quantos = len(carga.get("perfis.linha.nome") or [])
    frase = f"Lista recarregada · {quantos} perfis"
    _anotar(frase)
    carga["perfis.desfecho"] = ""
    return {"blocos": carga.get("blocos") or {},
            "mesa": {k: v for k, v in carga.items()
                     if k != "blocos" and not isinstance(v, dict)},
            "relato": frase}


@gesto("10-perfis.html", "procurar")
def procurar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A lupa: guarda o que ela digitou, e o tique seguinte mostra a lista curta.

    **ELE É UM GESTO VIVO (`data-hef-vivo`), e não um clique** — a quarta porta
    do piloto, a que dispara a cada TECLA e por contrato só LÊ. As outras três
    portas despacham o `data-hef-gesto`, e nenhuma delas é acionada por digitar.

    **ELE NÃO PINTA NADA, E ISSO É O DESENHO INTEIRO.** O vivo tem
    `CHAVES_QUE_O_VIVO_RECUSA = ("blocos", "fita", "recado", "recados")`: uma
    resposta que troque HTML é recusada na porta. Então este gesto só ANOTA, e
    quem mostra a lista curta é o tique de 100 ms, que já relê o disco e já
    monta o `blocos` — por `_filtrada`, uma linha acima de onde a lista vira
    tela. A latência é de um décimo de segundo e o caminho é o mesmo de sempre.

    **E ELE NÃO GRAVA**, que é a outra metade do contrato do vivo: `_PROCURA`
    mora na memória desta janela. Um filtro que voltasse do disco esconderia
    perfis dela na próxima abertura sem que ela tivesse digitado nada.

    O TERMO VEM DO `valor`, e não do `texto`: num `<input>` o `textContent` é
    vazio — é o defeito que deixou quatro campos desta aba sem dono em 01/09.
    """
    global _PROCURA
    _PROCURA = str(o.get("valor") or "")
    return {}


@gesto("10-perfis.html", "ordenar")
def ordenar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O duplo clique no nome da coluna: ordena por ela; de novo, inverte."""
    coluna = str(o.get("coluna") or "").strip()
    if coluna not in COLUNAS_DA_LISTA:
        raise ValueError(
            f"ordenar: o duplo clique não disse por qual coluna ({coluna!r}). "
            f"As que ordenam são {COLUNAS_DA_LISTA}.")
    atual, sentido = _prefs.ordem_da_tabela(TABELA_DA_LISTA)
    if atual != coluna:
        _prefs.guardar_ordem_da_tabela(TABELA_DA_LISTA, coluna, "asc")
        frase = f"Ordenado por {_NOME_DA_COLUNA[coluna]}, do menor para o maior"
    elif sentido == "asc":
        _prefs.guardar_ordem_da_tabela(TABELA_DA_LISTA, coluna, "desc")
        frase = f"Ordenado por {_NOME_DA_COLUNA[coluna]}, do maior para o menor"
    else:
        _prefs.guardar_ordem_da_tabela(TABELA_DA_LISTA, "", "")
        frase = "Ordem de sempre: o perfil que está valendo em primeiro"
    carga = pacote(ctx)
    _anotar(frase)
    carga["perfis.desfecho"] = ""
    return {"blocos": carga.get("blocos") or {},
            "mesa": {k: v for k, v in carga.items()
                     if k != "blocos" and not isinstance(v, dict)},
            "relato": frase}


@gesto("10-perfis.html", "largura-da-coluna")
def largura_da_coluna(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Soltar a divisa entre duas colunas: grava a largura que ficou."""
    tabela = str(o.get("tabela") or "").strip()
    coluna = str(o.get("coluna") or "").strip()
    if tabela not in (TABELA_DA_LISTA, TABELA_DA_GUARDA):
        raise ValueError(f"largura-da-coluna: tabela desconhecida ({tabela!r})")
    if not coluna:
        raise ValueError("largura-da-coluna: o arraste não disse qual coluna")
    try:
        pedido = int(float(str(o.get("px") or "")))
    except ValueError:
        raise ValueError(
            f"largura-da-coluna: {o.get('px')!r} não é um número de pixels"
        ) from None
    ficou = _prefs.guardar_largura_de_coluna(tabela, coluna, pedido)
    carga = pacote(ctx)
    return {"mesa": {k: v for k, v in carga.items()
                     if k != "blocos" and not isinstance(v, dict)},
            "relato": f"Coluna com {ficou} pixels"}


def _editor_de(prof: Any) -> dict[str, Any]:
    """Os campos do editor daquele perfil, pela porta da FRENTE do produto."""
    editor: dict[str, Any] = _tela.pacote_da_aba(
        [prof], ativo=None, editado=prof)["editor"]
    return editor


#: `profile.switch` em vez do booleano (ELO-MUDO-01). O `profile_reaplicar`
PONTE = {"profile_reaplicar", "chamar", "resultado"}
#: `profile.switch` ENTROU com o `resultado`: quem chama por nome de método
METODOS = {"launch_env.refresh", "profile.switch"}


PAGINA = "10-perfis.html"
PISO_DA_ABA = 16
#: mentira que o `conftest.py` monta", `load_all_profiles()` devolve **9
PROVAS: list[dict[str, Any]] = [
    {"pagina": PAGINA, "gesto": "ativar", "clique": {"texto": "Ação"},  # (noqa-acento) id
     "chama": [("resultado", ["profile.switch"], {"name": "Ação"})]},
]

#: O QUE NÃO ECOA NO `state_full`, e são DOZE dos treze. A razão é uma só e está
SEM_ECO = ("selecionar", "editor.nome", "editor.ambiente", "editor.jogo",
           "editor.prioridade", "editor.estilo",
           "detectar", "novo", "duplicar", "remover", "voltar-a-de-ontem",
           "recarregar",
           # `state_full` muda quando ela arrasta uma divisa.
           "procurar", "ordenar", "largura-da-coluna")


AGORA_NAO_DIZ = TRAVESSAO

#: A dica da célula neutra, e a da máscara que não é a DualSense (decisão dela
#: de 29/09, pergunta [40]: «Aceso no DualSense», com a dica dizendo qual).
DICA_DO_NAO_DIZ = "O controle não diz."
DICA_DA_MASCARA = "Máscara: {mascara}."


def _luz_agora(entrada: dict[str, Any], state: dict[str, Any], _linha: dict[str, Any]
               ) -> bool | None:
    """A barra acesa, pela regra do cartão (`controller_card.rotulo_lightbar`).

    Quem traduz o rótulo em aceso, apagado ou incerto é a aba Iluminação
    (`a04_iluminacao.estado_da_tira`), e é ela que se pergunta aqui.
    """
    from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar

    from . import a04_iluminacao

    estado = a04_iluminacao.estado_da_tira(rotulo_lightbar(entrada, state)[0])
    if estado == a04_iluminacao.ACESA:
        return True
    return False if estado == a04_iluminacao.APAGADA else None


def _gatilhos_agora(_entrada: dict[str, Any], _state: dict[str, Any],
                    _linha: dict[str, Any]) -> bool | None:
    """Sempre `None`: o daemon não publica o efeito do gatilho por controle.

    Medido em 02/10/2026 no `state_full`: nenhuma chave `trigger_*` por
    controle (o `trigger_replicas` é a contagem da réplica do pad virtual), e
    o DualSense não devolve o efeito (`a03_gatilhos.SEM_ECO`). A publicação
    vira sprint própria; até lá a célula fica neutra, e o disco não a
    preenche.
    """
    return None


def _vibracao_agora(_entrada: dict[str, Any], state: dict[str, Any],
                    linha: dict[str, Any]) -> bool | None:
    """Um motor deste controle acima de zero (`a05_vibracao._barras_dos_motores`).

    Sem o mapa `rumble_motores` no `state_full` (daemon velho), a força que o
    dono devolveria seria o padrão do esquema, e não uma leitura: neutro.
    """
    if not isinstance(state.get("rumble_motores"), dict):
        return None
    from . import a05_vibracao

    barras = a05_vibracao._barras_dos_motores(state, str(linha.get("uniq") or ""))
    return any(valor > 0 for valor in barras.values())


def _alto_falante_agora(entrada: dict[str, Any], _state: dict[str, Any],
                        _linha: dict[str, Any]) -> bool | None:
    """Ligado e sem mudo (`controller_card.speaker_do_entry`)."""
    from hefesto_dualsense4unix.interface.cartao_do_controle import speaker_do_entry

    lido = speaker_do_entry(entrada)
    if lido is None:
        return None
    volume, mudo = lido
    if mudo is True or volume == 0:
        return False
    return None if mudo is None else True


def _microfone_agora(entrada: dict[str, Any], _state: dict[str, Any],
                     _linha: dict[str, Any]) -> bool | None:
    """Aberto, pelas quatro faces (`a02_controles._faces_do_microfone`)."""
    audio = entrada.get("audio")
    if not isinstance(audio, dict):
        return None
    from . import a02_controles

    calado, nao_sei = a02_controles._faces_do_microfone(audio)
    if calado:
        return False
    return None if nao_sei else True


def _sensores_agora(entrada: dict[str, Any], _state: dict[str, Any],
                    _linha: dict[str, Any]) -> bool | None:
    """Giroscópio ou acelerômetro ligado (`a02_controles._sensor_ligado`)."""
    from . import a02_controles

    lidos = [a02_controles._sensor_ligado(entrada, qual)
             for qual in ("giroscopio", "acelerometro")]
    if any(valor is True for valor in lidos):
        return True
    return False if all(valor is False for valor in lidos) else None


def _mascara_agora(_entrada: dict[str, Any], _state: dict[str, Any],
                   linha: dict[str, Any]) -> bool | None:
    """A máscara deste controle é a DualSense (`mesa_viva.NOME_DA_MASCARA`)."""
    import mesa_viva

    mascara = str(linha.get("mascara") or "")
    if mascara in ("", TRAVESSAO):
        return None
    return mascara == str(mesa_viva.NOME_DA_MASCARA["dualsense"])


def _comandos_virtuais_agora(entrada: dict[str, Any], _state: dict[str, Any],
                             _linha: dict[str, Any]) -> bool | None:
    """Mira, toque ou inclinação ligados (`a02_controles._mira_ligada` e"""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    from . import a02_controles

    ligada = a02_controles._mira_ligada(entrada)
    if ligada is None:
        return None
    destinos = [a02_controles._destino_da_mira(entrada, chave)
                for chave in ("toque", "inclinacao")]
    return ligada or any(d not in (None, rot.DESTINO_NENHUM) for d in destinos)


QUEM_DIZ_O_AGORA: dict[str, Callable[[dict[str, Any], dict[str, Any], dict[str, Any]],
                                     bool | None]] = {
    "leds": _luz_agora,
    "triggers": _gatilhos_agora,
    "rumble": _vibracao_agora,
    "speaker": _alto_falante_agora,
    "mic": _microfone_agora,
    "sensores": _sensores_agora,
    "mascara": _mascara_agora,
    "movimento": _comandos_virtuais_agora,
}


def o_agora_da_linha(linha: dict[str, Any], state: dict[str, Any]
                     ) -> list[tuple[str, str]]:
    """`(valor, dica)` de cada célula da linha, na ordem de `SECOES_DA_COLUNA`."""
    entrada = linha.get("entrada")
    fora: list[tuple[str, str]] = []
    for secao in SECOES_DA_COLUNA:
        dono = QUEM_DIZ_O_AGORA.get(secao)
        if not isinstance(entrada, dict) or not entrada or dono is None:
            fora.append((AGORA_NAO_DIZ, DICA_DO_NAO_DIZ))
            continue
        aceso = dono(entrada, state, linha)
        if aceso is None:
            fora.append((AGORA_NAO_DIZ, DICA_DO_NAO_DIZ))
        elif secao == "mascara" and not aceso:
            fora.append(("", DICA_DA_MASCARA.format(mascara=linha.get("mascara"))))
        else:
            fora.append(("sim" if aceso else "", ""))
    return fora


def _entrada_viva(conectados: Any, uniq: str) -> dict[str, Any]:
    """A entrada do daemon deste `uniq` (`Contexto.conectados`), ou `{}`."""
    for entrada in conectados or ():
        if isinstance(entrada, dict) and str(entrada.get("uniq") or "") == uniq:
            return entrada
    return {}
