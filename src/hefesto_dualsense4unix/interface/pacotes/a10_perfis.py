#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

A aba já estava marcada em 31/08 (77 endereços `data-hef`, 11 gestos, esquema de nomes próprio); o
nome do atributo não é o contrato, o contrato é este despachante. Tem dono: o perfil em vigor
(`active_profile`) e o Modo Freestyle (`freestyle_ligado`, que diz se o Freestyle manda em todo
jogo).

Os gestos com dono (de 01/09/2026; o desenho de 12/10 tirou a Preferência, o «Funciona em» e o
Detectar):

    selecionar          a célula do nome, na lista. Abre o perfil no editor.
    ativar              `profile.switch`
    voltar-a-de-ontem   `restaurar_do_historico` + reaplicar + `launch_env.refresh`
    perfis.renomear     renomeia: `save_profile` do nome novo + `delete_profile`
    editor.jogo         o programa (ou o appid) dentro da regra
    novo                um perfil em branco, com a regra do jogo em foco
    duplicar            `model_copy` com "(cópia)" no nome, e o editor abre nela
    remover             `delete_profile`, com a pergunta NO RÓTULO do botão
    editor.estilo       escolher um estilo APLICA a receita: gatilho, degrau de vibração e a
                        cor de cada controle ("Construir o motor"), de `profiles/estilos_de_jogo.py`

A segunda leva só foi possível por três correções (nenhuma do daemon): (1) o clique passou a trazer
`valor`, o `value` do `<input>`/`<select>` (o ouvinte mandava `texto: alvo.textContent`, vazio num
`<input>`); (2) os quatro campos ganharam `data-hef-alvo="valor"` no gerador (sem isso a pintura
APAGAVA as opções dos dois `<select>`, 5 → 0 e 15 → 0, e deixava os `<input>` com o texto do
MOCKUP); (3) `pacote()` manda `editado=` ao produto (sem isso o editor pintava o ATIVO enquanto os
botões agiam sobre o ESCOLHIDO, e renomear seria olhar o nome de outro).

**RECUSA-CHEGA-NA-TELA-01, qual exceção levantar não é gosto**: `hefesto_vivo._recusou_dizendo`
pinta a tarja **só para `RuntimeError`** (*"o produto recusou, e a frase VAI PARA A TELA"*);
`ValueError` é *clique inválido*, frase para quem programa, e sai no `stderr`. A aba violava o
contrato em nove frases, a mais cara com teste verde (medido em 03/09/2026, clique real no "Ativar"
com o perfil ativo já escolhido: `[gesto falhou] ativar: “meu_perfil” já é o perfil que está
valendo…` no stderr e tarjas `[]` no DOM). Forma de defeito que o próprio `_recusou_dizendo` nomeia:
*alguém curou o caminho e provou a cura num caminho que ela não usa.* Sobrou um `ValueError`, o do
`selecionar` (clique sem nome de perfil, a única frase escrita para quem programa).

**A lista cabe inteira** (02/09/2026): o `<tbody>` publicado tem catorze linhas porque catorze
cabiam na figura, e a pasta do usuário tem 33 perfis; os outros dezenove não existiam na tela, e com
eles nove dos dez botões (que agem sobre o ESCOLHIDO). A lista é um `blocos` (`_html_da_lista`, que
explica por que a régua do mockup não conta esta entrega). A aba também parou de perguntar só ao
daemon quem está valendo (`_valendo`): com `active_profile: null` três guardas se desligavam juntas.

ONDA2-10, decisões do PO (04/09/2026):

    [02] o FIM da frase da exigência escondida, reescrito para ESTA
    tela (`FIM_DA_EXIGENCIA_AQUI`): a do produto está certa na janela GTK e errada aqui. [04] o
    CAMPO DO JOGO SE CORRIGE: `editor_jogo` devolve `editor.jogo` na forma canônica
    com o desfecho. É o único instante em que a tela pode fazê-lo: o campo está em
    `CAMPOS_QUE_ELA_DIGITA` e o tique não o repinta.

    [03] e [05] são de DESENHO e moram no `aba10.py`.

O teto: **o daemon não tem `profile.save` nem `profile.delete`.** Dos 39 métodos há
`profile.switch`, `profile.list` e `profile.reaplicar`; gravar e apagar perfil roda no processo da
janela, direto no disco, e todo gesto que escreve avisa o daemon depois (`profile.switch` para
reaplicar, `launch_env.refresh` para a antecipação por appid).
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable
from datetime import datetime
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
)

from . import (
    TODOS_OS_LUGARES,
    TRAVESSAO,
    Contexto,
    perfil,
    registrar,
)

#: `profiles_dir()`. Ter outro dono que não o `state_full` não é não ter dono.
SEM_DONO: dict[str, str] = {}


#: disco do usuário, `_secoes_do_controle` devolvia seis chaves, esta lista lia cinco,
SECOES_DA_COLUNA: tuple[str, ...] = (
    "leds", "triggers", "rumble", "speaker", "mic", "sensores", "mascara",
    "movimento", "ativacao", "analogicos")  # (noqa-acento) identificadores ASCII

#: não chega, `perfis_web._secoes_do_controle` não devolve a chave, o pacote lê
ESPERANDO_O_ESQUEMA: frozenset[str] = frozenset()


_ESCOLHIDO: str = ""


def _escolhido(todos: list[dict[str, Any]], ativo: str) -> str:
    """A linha aberta no editor: a última clicada, ou o perfil ativo.

    Deixa de valer sozinha quando o perfil sai do disco (apagado por fora, renomeado,
    `HEFESTO_VARIANTE` trocado); sem a queda, "Voltar à de ontem" miraria arquivo inexistente e o
    erro falaria de perfil que ela não vê. A sincronização inicial é escrita aqui de propósito e a
    guarda a torna segura de repetir: só grava quando a lista tem aquele nome (na régua dos botões o
    `active_profile` é "regua", nenhum perfil se chama assim, e o estado do módulo fica limpo).

    Sob o `pytest` `load_all_profiles()` devolve `[]`: a `conftest.py` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, o que desliga o `_maybe_seed_presets`
    (os 9 perfis de fábrica só existem em processo SEM o pytest). Com a lista vazia o `ativo` nunca
    está em `nomes` e nada é gravado.
    """
    global _ESCOLHIDO
    nomes = {p["nome"] for p in todos}
    if _ESCOLHIDO and _ESCOLHIDO not in nomes:
        _ESCOLHIDO = ""
    if not _ESCOLHIDO and ativo in nomes:
        _ESCOLHIDO = ativo
    return _ESCOLHIDO or ativo


# Ordem de produto: a tabela do perfil leva uma lupa no título, procura por nome de perfil e demais
# configs, e ordena por duplo clique no nome das colunas.

_PROCURA: str = ""

#: O «Nome do jogo» recusou o nome do botão: (perfil, frase). O nome recusado não grava, então o
#: tique, que lê a exigência do disco, apagaria o ponto laranja no décimo de segundo seguinte; a
#: recusa vale até o campo mudar de novo ou outro perfil abrir no editor.
_RECUSA_DO_JOGO: tuple[str, str] = ("", "")

FRASE_DO_FREESTYLE = "Freestyle é o botão do controle, não um jogo"


def _esquecer_a_recusa_do_jogo() -> None:
    """Outro perfil abriu no editor: a recusa era do campo do anterior."""
    global _RECUSA_DO_JOGO
    _RECUSA_DO_JOGO = ("", "")

TABELA_DA_LISTA = "10-perfis.lista"

TABELA_DA_GUARDA = "10-perfis.guarda"

COLUNAS_DA_LISTA = ("nome", "criado", "modificado")

_NOME_DA_COLUNA = {"nome": "Nome", "criado": "Criado em", "modificado": "Modificado em"}

#: as colunas de data: «mais novo primeiro» é o sentido `asc`, e o perfil sem data fica embaixo.
COLUNAS_DE_DATA = ("criado", "modificado")


def _sem_acento(texto: str) -> str:
    """O texto pronto para comparar — sem acento, sem caixa, sem pontuação."""
    from hefesto_dualsense4unix.profiles.slug import slugify
    try:
        return slugify(texto)
    except ValueError:
        return ""


def _casa(linha: dict[str, Any], termo: str) -> bool:
    """Aquela linha responde à busca?"""
    alvo = " ".join(str(linha.get(c) or "") for c in ("nome", "quando", "dica"))
    return termo in _sem_acento(alvo)


def _filtrada(lista: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A lista com o filtro da lupa aplicado. Sem termo, ela sai inteira."""
    termo = _sem_acento(_PROCURA)
    if not termo:
        return list(lista)
    return [x for x in lista if _casa(x, termo)]


def _chave_da_ordem(coluna: str) -> Callable[[dict[str, Any]], Any]:
    """Como cada coluna se compara. A data compara pelo ISO, e o mais novo vem antes no `asc`."""
    if coluna in COLUNAS_DE_DATA:
        def por_data(x: dict[str, Any]) -> tuple[int, float, str]:
            try:
                quando = datetime.fromisoformat(str(x.get(f"{coluna}_iso") or ""))
            except ValueError:
                return (1, 0.0, "")
            return (0, -quando.timestamp(), "")
        return por_data

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
    """A lista na ordem que o usuário escolheu — ou na que o produto monta."""
    coluna, sentido = _prefs.ordem_da_tabela(TABELA_DA_LISTA)
    if coluna not in COLUNAS_DA_LISTA:
        return list(lista)
    sem_data = [x for x in lista if coluna in COLUNAS_DE_DATA and not x.get(f"{coluna}_iso")]
    com_data = [x for x in lista if x not in sem_data]
    return sorted(com_data, key=_chave_da_ordem(coluna), reverse=(sentido == "desc")) + sem_data


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

    Desde 13/09/2026 a frase NÃO vai para a tela: sai em `relato` e no diário da janela, e a tira
    recebe vazio (fim da função). Os `campos` seguem valendo.

    `campos` são os endereços que o gesto corrige NA HORA, no mesmo embrulho (04/09/2026, decisão
    [04] do PO). Os campos que ela DIGITA são omitidos do tique (`CAMPOS_QUE_ELA_DIGITA`, para a
    pintura não apagar o que se escreve), então o único instante em que a tela devolve a forma
    canônica do que foi colado (o endereço da loja, por exemplo) é a resposta do PRÓPRIO gesto. O
    caminho já existia: gesto que devolve dicionário tem a carga pintada na hora
    (`hefesto_vivo._deu_certo` → `window.__hef.pintar`), no vocabulário `endereço → valor` da
    pintura, e o tique seguinte sobrescreve com o mesmo valor. Na hora e não no tique porque *"Meio
    segundo entre o clique e a resposta basta para ela clicar de novo achando que o primeiro não
    pegou"* (o tique desta aba).

    **O `mesa:` não é enfeite.** O `_deu_certo` entrega a carga CRUA ao `window.__hef.pintar`, que
    lê `p.blocos`, `p.mesa`, `p.colunas` e `p.vazios` e mais nada; dicionário achatado
    (`{"perfis.desfecho": …}`) passa por todos os laços sem casar: **zero escrito, zero erro**, a
    *ausência de notícia lida como sucesso*, que já custou dois dias ao `blocos` do `normalizar`. O
    `pacote()` chega ao JS com esse embrulho porque `pacotes.normalizar` o põe; um gesto não passa
    por lá e põe o seu.
    """
    global _CARONA_PENDENTE
    # registro de chamada que `perfil.com_a_carona` documenta para quem já tem
    # `_com_a_carona(frase)` direto e este campo continua vazio — dois `·` para
    if _CARONA_PENDENTE:
        frase = f"{frase} · {_CARONA_PENDENTE}" if frase else _CARONA_PENDENTE
        _CARONA_PENDENTE = ""
    _anotar(frase)
    #  nao devia aparecer nunca"  # (noqa-acento) citação literal
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


#: `data-hef-alvo="largura"` estaria.
#:                       desta frente; está no relatório.
#: `data-hef-alvo="classe"`, e o produto passou a acender e apagar cada uma.
NAO_PINTAVEIS = ("guarda.linhas",)

#: Os escalares do editor que a página tem onde pôr (15/10/2026: a página perdeu o Nome, a
#: Preferência, o Funciona em e o rótulo do jogo; o produto deixou de emiti-los).
CAMPOS_DO_EDITOR_NA_PAGINA = ("jogo", "estilo", "evento", "evento_comando")

#: os valores que a página NÃO TEM — eles caem no vazio, sem estrago e sem
SEM_ENDERECO = {
    "quantos": "a tela nova não desenha contagem de perfis",
    "travado": "a trava da troca automática não é desenhada nesta aba",
}

#: baixa. As datas: `perfis.desfecho` (03/09)
ESPERANDO_A_PUBLICACAO: dict[str, str] = {
}


FIM_DA_EXIGENCIA_NA_GTK = "Ligue o Modo avançado para ver e mudar."
FIM_DA_EXIGENCIA_AQUI = "Esta tela não mostra esses campos."


def _exigencia_para_esta_tela(match: Any) -> str:
    """A exigência escondida daquele `match`, com o fim que ESTA tela alcança.

    NUNCA LEVANTA: roda dentro de `pacote()`, e exceção derrubaria a pintura da aba inteira por
    causa de um perfil com regra estranha. **A troca é exata e cobrada**:
    `test_a_aba_10_perfis_fecha_as_linhas.py` exige que `FIM_DA_EXIGENCIA_NA_GTK` continue sendo o
    fim que o produto emite; se a frase de lá mudar a régua reprova AQUI, em vez de a troca falhar
    em silêncio e a tela mandar a um lugar que não existe.
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

CAMPOS_QUE_ELA_DIGITA = ("editor.jogo", "editor.evento.comando", "editor.estilo")


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
    """`Cosmic Red • USB`: a cor do plástico e a via, sem marcação e sem número de jogador.

    Fala pela cor do plástico, nunca P1 a P4 (A-ABA-PERFIS-DO-TODO-01); vem de `mesa_do_estado`.
    """
    return SEPARADOR_EM_TEXTO.join([
        str(controle.get("nome") or "—"),
        str(controle.get("via") or "—"),
    ])


#: as quatro cores do plástico, na ordem em que o desenho as oferece nos lugares vazios.
CORES_DO_PLASTICO = (("cosmic-red", "Cosmic Red"), ("starlight-blue", "Starlight Blue"),
                     ("galactic-purple", "Galactic Purple"), ("white", "White"))


def _lugar_vazio(n: int, presentes: list[str]) -> tuple[str, str]:
    """`(nome, cor)` do lugar vazio de número `n`: uma cor do plástico que ninguém na mesa usa."""
    livres = [(slug, nome) for slug, nome in CORES_DO_PLASTICO
              if not any(nome in dado for dado in presentes)] or list(CORES_DO_PLASTICO)
    slug, nome = livres[(n - 1 - len(presentes)) % len(livres)]
    return nome, _plastico({"cor": slug})


def _plastico(controle: dict[str, Any]) -> str:
    """O hexadecimal da casca daquele controle, **pelo dono da cor**.

    Lei do usuário, 03/09/2026: cada aba usa os controles que o topo mostra, nunca a informação do
    mockup. A barra de 3px da linha era `--plastico` cravado no `<tr>` pelo gerador (a cor do
    DESENHO), com `guarda.nome` já vindo do aparelho: `P1 • White • USB` com a barra vermelha do
    mockup.

    `monta.cor_da_zona` lê o `<style>` que `scripts/gerar_cores_do_dualsense.py` escreveu no
    `ds_limpo.svg`, o MESMO lugar de onde a fita do topo tira a cor do chip; reescrever a leitura
    criaria a segunda verdade sobre a cor, que o portão `check_cores_do_dualsense.py` existe para
    matar. O import é tardio e guardado, como em `hefesto_vivo._fita`: o `monta` lê disco no import
    (esqueleto, SVG, dois CSV de `docs/`) e um import no topo derrubaria a janela onde não há
    repositório (sem repositório a fita do topo também não repinta). `SystemExit` no `except`, que
    não é `Exception`: `cor_da_zona` a ergue para colorway que o SVG não tem, e um `except
    Exception` passaria ao lado (foi como o piloto morreu na primeira execução da fita viva).

    Sem cor lida, devolve vazio: pelo rádio a cor não vem (`identidade.cor_do_aparelho = não` no
    mapa de canais) e `mesa_do_estado` entrega `cor: ""`. Inventar cinza ou cair na cor do mockup
    afirmaria modelo que ninguém confere; com o vazio o piloto escreve `''` no alvo `cor`, o `style`
    de linha cai, o `color:transparent` da classe volta e a barra SOME (campo sem informação não
    mostra nada).
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
    """A mesa no formato que `perfis_web.pacote_da_aba` diz esperar: `mesa_do_estado` mais `rotulo`
    e `plastico`.

    `mesa_do_estado` não devolve nenhum dos dois (seus campos: `pref`, `uniq`, `jogador`, `cor`,
    `nome`, `via`, `transporte`, `alvo`, `mascara`, `botoes`), e `_linhas_da_guarda` lê
    `controle.get("rotulo")` e `controle.get("plastico")`; medido em 02/09/2026, `guarda.nome` saía
    `["", ""]` para os dois controles e a tabela ficava sem nome. O `plastico` entrou em 03/09/2026
    (ver `_plastico`).

    O visor `interface/perfis_vivos.mesa_de_agora` NÃO fazia isso certo (medido em 11/09/2026,
    foto): punha em `rotulo` a saída de `monta.rotulo(c, "curta")`, que é MARCAÇÃO (`P1 <span
    …>•</span> Cosmic Red …`), e o pintor escreve `textContent`, mostrando a marcação como TEXTO em
    quatro linhas; o instrumento respondia sobre outra coisa que não o produto. Foi curado no mesmo
    commit para chamar `_rotulo_curto`; o que fazia certo era a FORMA.
    """
    return [{**c, "rotulo": _rotulo_curto(c), "plastico": _plastico(c),
             "entrada": _entrada_viva(conectados, str(c.get("uniq") or ""))}
            for c in mesa]


SELETOR_DA_LISTA = 'tbody[data-hef="perfis.lista"]'

SELETOR_DOS_JOGOS = 'datalist[data-hef="editor.jogo.lista"]'

#: «Qual vale primeiro»: os perfis do mesmo jogo, em ordem. Número de filhos que muda com o dado,
#: então vai por `blocos`, como a lista. O `data-hef` mora NO `<ol>`: um seletor de descendente
#: (`… ol`) não acha nada, e a página ficava com os dois perfis do desenho.
SELETOR_DA_ORDEM = 'ol[data-hef="editor.ordem"]'

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

    **Escapa menos que o `html.escape` do Python, cura de defeito medido.** O `blocos` do piloto só
    reescreve o miolo quando `alvo.innerHTML !== html`, comparando a string do gerador com a
    **serialização do navegador**; escapar o que o serializador não escapa faz as duas nunca baterem
    e o bloco é reescrito a cada 500 ms. Medido em 02/09/2026 (piloto na aba por dez segundos, mesmo
    HTML num Chrome de bancada): `html.escape(quote=True)` → 21 tiques, 17 escritas em CADA um;
    escapando como o serializador → 1 escrita. Os dois escapes a MAIS: `'` (Python `&#x27;`,
    navegador `'`) e `\n` (Python `&#10;`, navegador a quebra CRUA; a dica da disputa tem dois
    parágrafos). Não é inseguro: dentro de aspas duplas `'` e `<` não fecham nada, e a aspa dupla
    continua `&quot;`; é o conjunto que o serializador escapa em atributo.

    Não curar custaria mais que o contador: reescrever o `<tbody>` a cada meio segundo apaga o
    `:hover` da linha e desfaz a seleção de texto na lista (três vezes por segundo, enquanto se
    procura um perfil entre 33).
    """
    s = str(v if v is not None else "")
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("\xa0", "&nbsp;")


def _linha_da_lista(nome: str, criado: str, modificado: str,
                    ativo: bool, dica: str = "", escolhido: bool = False) -> str:
    """Uma linha da lista de perfis — a MESMA forma que o desenho crava.

    O dono da forma é o gerador, `aba10.linha_do_perfil` (*"a MESMA para o mockup e para a viva"*),
    que não atravessa para o produto: `aba10.py` faz `sys.path.insert` e `from monta import …`, e o
    `monta` lê seis arquivos do repositório no import (a janela não abriria sem repositório; mesma
    razão de `SEPARADOR_EM_TEXTO` ser constante). A segunda gramática é impedida por régua:
    `test_a_lista_de_perfis_cabe_inteira.py:: test_a_linha_viva_e_a_linha_do_desenho` compara as
    duas saídas caractere a caractere. A única divergência declarada é o escape (`_texto`, `_atr`).

    `escolhido` é a linha aberta no editor (04/09/2026, queixa de uso: clicar num perfil salvo não
    indicava a seleção; o valor alimentava só o texto do Remover e os gestos). **A marca vem daqui,
    não de `classList.add` no JS**: o `blocos` reescreve o `<tbody>` a cada tique de 100 ms e marca
    do navegador vive um décimo de segundo. Não é uma segunda classe:
    `test_a_lista_de_perfis_cabe_inteira.py` procura a SUBSTRING `class="ativo"` na linha realçada,
    e `class="ativo escolhido"` a some (régua verde sobre linha que ela não acha mais). O estado vai
    em `aria-selected`, que o papel `row` já define para seleção.
    """
    return (f'{_RECUO}<tr tabindex="0" data-dica="Clique: ativa e abre no editor" '
            f'class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{_atr(nome)}" data-hef-gesto="selecionar" '
            f'aria-selected="{"true" if escolhido else "false"}">'
            f'<td data-hef="perfis.linha.nome" '
            f'data-dica="Clique abre no editor; duplo clique renomeia">{_texto(nome)}</td>'
            f'<td class="data" data-hef="perfis.linha.criado">{_texto(criado)}</td>'
            f'<td class="data" data-hef="perfis.linha.modificado">{_texto(modificado)}</td></tr>')


def _html_da_lista(lista: list[dict[str, Any]], vazia: str,
                   escolhido: str = "") -> str:
    """As linhas da lista de perfis, TODAS — a maior mentira que esta aba contava.

    Medido em 02/09/2026: `load_all_profiles()` devolve **33** perfis e o `<tbody>` publicado tem
    **14 linhas**; o contador dizia "33 perfis" (verdade) sobre catorze linhas, e dezenove perfis
    não tinham como ser clicados, nem os nove dos dez botões que agem sobre o perfil ESCOLHIDO. Não
    se pinta campo a campo (mesma razão da fita de chips e do mapa do gabinete): **bloco cujo número
    de filhos muda com o dado não tem endereço para o filho que ainda não existe**; o desenho cravou
    catorze porque cabiam na figura.

    Chegam à tela por aqui e por nenhuma outra porta: (1) as 19 linhas que faltavam; (2) a classe
    `ativo` na linha certa (o desenho a crava na PRIMEIRA, acerto por acidente porque
    `ordem_de_exibicao` põe o ativo primeiro, e mentira inteira sem perfil ativo; nenhum dos cinco
    alvos do pintor liga CLASSE); (3) o `title` da disputa (`explicacao_da_disputa`,
    `profiles_actions`; `perfis_web._linhas_da_lista` já a chamava a cada tique e o valor morria no
    dicionário, pois o `title=""` do desenho nasce vazio *"porque a dica é a DISPUTA, e disputa é
    dado"*). A lista vazia também é estado: `perfis_web.LISTA_VAZIA` diz o que fazer para ter o
    primeiro perfil.

    **Este `<tbody>` ainda é reescrito a cada tique, e a causa NÃO é o escape** (medido em
    02/09/2026 no WebKit, daemon vivo, sonda no laço do `blocos`): em 20 tiques `BLOCOS 20` contra 1
    dos demais endereços. O primeiro caractere divergente é o 594:

        na TELA     …data-hef-gesto="selecionar" data-hef-visto="1">meu_perfil…
        no PRODUTO  …data-hef-gesto="selecionar">meu_perfil…

    O `escrever()` carimba `el.dataset.hefVisto = '1'` em TODO elemento que visita, inclusive quando
    escreve zero. O laço do `blocos` roda ANTES da distribuição por endereço e compara
    `alvo.innerHTML !== html`: do segundo tique em diante a tela tem 99 selos que o produto não tem
    (12.222 contra 10.341 caracteres) e as strings nunca mais batem; o custo é o do `_atr` (`:hover`
    apagado duas vezes por segundo). **A cura mora no piloto, não aqui** (carimbar o selo fora da
    serialização, `WeakSet` em JS, ou comparar sem ele); emitir o selo daqui faria a aba conhecer
    detalhe interno do pintor. Hoje só esta lista paga (o defeito morde `blocos` cujos FILHOS têm
    endereço; os dois da `08-conexoes`, `.mm-faces` e `.mm-lista`, não emitem `data-campo` dentro, e
    quando emitirem entram no mesmo buraco).

    `escolhido` é o NOME da linha aberta no editor, comparado por NOME EXATO: quem chama já resolveu
    o slug (`find_by_slug`) contra os perfis do disco e o `nome` de cada linha vem do mesmo
    `p.name`; comparar slug de novo seria a segunda resolução do mesmo dado (esta aba deu dois
    vereditos sobre a mesma tela em 02/09). `escolhido=""` não casa com nome nenhum e a lista sai
    sem marca, o que mantém verde toda régua que chama a função sem o terceiro argumento.
    """
    if not lista:
        return (f'{_RECUO}<tr class="vazia"><td colspan="3">'
                f'{_texto(vazia)}</td></tr>')
    return "\n".join(
        _linha_da_lista(str(x.get("nome") or ""), str(x.get("criado") or TRAVESSAO),
                        str(x.get("modificado") or TRAVESSAO), bool(x.get("ativo")),
                        "",
                        escolhido=bool(escolhido)
                        and str(x.get("nome") or "") == escolhido)
        for x in lista)


def _html_da_ordem(ordem: list[dict[str, Any]]) -> str:
    """Os `<li>` arrastáveis de «Qual vale primeiro». Vazio com menos de dois perfis no jogo."""
    return "\n".join(
        f'{_RECUO}<li class="{"ativo" if x.get("ativo") else ""}" draggable="true" tabindex="0" '
        f'data-hef-gesto="editor.ordem" data-hef-perfil="{_atr(x.get("perfil"))}">'
        f'<span class="pos">{int(x.get("pos") or 0)}</span><span class="pega">⋮⋮</span>'
        f'{_texto(x.get("perfil"))}</li>'
        for x in ordem)


def _html_dos_jogos(procedencia: str = "", foto: _FotoDoCatalogo | None = None) -> str:
    """As `<option>` do `<datalist>` — os jogos DESTA máquina, do disco do usuário.

    Com `procedencia` cheia (C4-FUNCIONA-EM, §3, 11/09/2026) traz só os jogos do lançador que o
    campo de cima diz; sem ela, e nas duas procedências que não são lançador, sai inteira
    (`_PROCEDENCIAS_SEM_JOGO`). PERFIL-MODO-01, Passo 3 (06/09/2026): o CSV da paridade (linha 378)
    dizia do lado HTML *"NADA. O `<input>` é texto livre"*, e criar perfil de jogo exigia saber o
    appid de cor; "Detectar" cobre só o jogo em foco, a lista cobre o resto, inclusive jogo FECHADO.

    O catálogo é o do produto: `_nomes_dos_jogos()` (10-Q4) é memoizado pela ASSINATURA da
    biblioteca (`jogos_locais.assinatura_da_biblioteca`), então dez tiques por segundo não abrem 33
    `.acf` dez vezes; `catalogo_de_jogos()` direto seria a segunda leitura do disco, sem o cache.
    `value` é o APPID e `label` o NOME, ordem não livre: num `<datalist>` o navegador escreve o
    `value` NO CAMPO e o campo grava um appid (`from_simple_choice("steam_game", …)` quer o número);
    é a divisão das duas colunas do `Gtk.EntryCompletion` da GTK, e trocar criaria perfil
    `steam_app_Sea of Stars`, que nunca casa com janela. Escapar é o `_atr`, não o `html.escape`: os
    nomes vêm dos `.acf` e `.desktop` DO USUÁRIO (`DON'T SCREAM` está no catálogo) e escapar a mais
    faria o `blocos` reescrever a cada 500 ms.

    **Os jogos de fora da Steam entram (11/09/2026)**, queixa de uso: *"em perfil falta detectar os
    jogos dos demais lançadores. dando exemplo
    do guardi]ães da galáxia."*  # (noqa-acento) citação
    A divisão é a mesma, e o `value` do jogo de lançador é a `wm_class` dele (``gotg.exe``) no MESMO
    campo do perfil (`window_class`), pela sexta forma do `simple_match` ("janela"). Quem decide é
    `JogoLocal.valor` e a JUNÇÃO das origens é `jogos_locais.ofertas_do_campo_do_jogo`; `if` e ordem
    próprios aqui seriam a segunda verdade sobre o que a lista oferece.

    Nunca levanta (como `_jogo_reconhecido`): é PINTURA, duas vezes por segundo, e `.desktop`
    estragado não derruba a aba por uma sugestão. `foto` é a do tique (`_foto_do_catalogo`); sem
    ela, a pergunta de sempre.
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


def _nome_no_campo(valor: str, nomes: dict[str, str]) -> str:
    """O «Nome do jogo» mostra o nome que o catálogo conhece; o número só quando ele não sabe.

    A página do todo tirou o rótulo do lado (BRIEF-T4: «Saem o número, o título do lado»), e o
    campo com `1245620` sozinho voltava a ser o número que não diz nada (JOGO-QUE-SE-DIZ-01).
    """
    from hefesto_dualsense4unix.profiles.simple_match import normalize_appid

    appid = normalize_appid(valor) if valor else None
    return nomes.get(str(appid), valor) if appid is not None else valor


def _appid_do_nome(texto: str, nomes: dict[str, str]) -> str:
    """O caminho de volta: o nome de um jogo da Steam desta máquina vira o número dele."""
    alvo = texto.casefold()
    return next((appid for appid, nome in nomes.items() if nome.casefold() == alvo), texto)


def _procedencia_do_jogo(jogo: Any) -> str:
    """De onde vem ESTE jogo — o nome que o campo «Funciona em:» mostra."""
    return str(getattr(jogo, "lancador", "") or "") or PROCEDENCIA_DA_STEAM


def _linha_do_jogo(jogo: Any) -> str:
    """O que a LINHA da lista do campo «Nome do Jogo» diz — item 12 da lista dela."""
    appid = str(getattr(jogo, "appid", "") or "")
    nome = str(getattr(jogo, "nome", "") or "")
    return f"{nome} · {appid}" if appid else nome


def _lancador_da_chave(chave: str, foto: _FotoDoCatalogo | None = None) -> str:
    """De qual lançador vem o jogo com ESTA `wm_class` (ou nome de programa).

    É a ponte que `simple_match.procedencia_do_match` pede, aqui por ser leitura de disco
    (`profiles/` é esquema, e um módulo de esquema que importasse `integrations/` obrigaria toda
    régua dele a ter a biblioteca do usuário). **O residual é «Instalado aqui», nunca o campo
    travado**: chave que o catálogo não conhece (``guard``, ``Hefesto-Dualsense4Unix``, medidas no
    disco em 11/09/2026) é perfil que o usuário escreveu, que funciona e que a §5 manda manter
    válido e mostrado; `LANCADOR_DIRETO` é a palavra do produto para isso (*"de lugar nenhum, está
    no menu"*), a mesma da lista do campo de baixo, e travar tiraria o gesto sobre perfil sem erro.

    **O residual de endereço da Steam é «Steam» (21/09/2026)**: desde que `procedencia_do_match`
    traz também o preset `steam_game` (o jogo do Heroic anuncia `steam_app_<id>`), appid que nenhum
    lançador reivindica chega aqui, e a resposta honesta é a Steam (`steam_app_<id>` é o carimbo
    dela; a biblioteca entra no catálogo por APPID, não por chave de janela, então `jogo_da_janela`
    não a acha). Nunca levanta: a queda também é o residual, pois `.desktop` estragado não trava o
    seletor de perfil certo.
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
    """``(procedência, recado)`` do campo «Funciona em:» — nunca os dois cheios.

    Procedência vazia = o que o `ambiente_travado` do produto sempre quis dizer: **esta tela não
    sabe descrever esta regra**, o campo vai travado com a frase do que ela é e o `match` do disco
    fica intacto (a MESMA válvula do R-12). É o único dono da pergunta, e pintura e gestos
    (`editor_jogo`) a chama em vez de ler `editor["ambiente_travado"]`: o
    booleano do produto travaria a «Navegação» (`browser` está em `perfis_web.FORA_DO_DESENHO`,
    *"não sei mostrar"*, enquanto a tela nova SABE) e ganharia opção que o gesto ao lado recusaria.
    """
    from hefesto_dualsense4unix.profiles.simple_match import procedencia_do_match

    procedencia = procedencia_do_match(
        match, _lancador_da_chave if foto is None
        else (lambda chave: _lancador_da_chave(chave, foto)))
    if procedencia:
        return (procedencia, "")
    return ("", str(recado_do_produto or ""))


def _valendo(ctx: Contexto, todos: list[Any] | None = None) -> str:
    """Qual perfil está valendo AGORA, **com o nome que a LISTA mostra**.

    `profiles_actions.perfil_que_esta_valendo` é o §P1 da casa: a aba lia
    `ctx.state.get("active_profile")` cru, e o daemon responde `active_profile: null` (*"o estado da
    máquina do usuário hoje"*), o que desligava três guardas ao mesmo tempo: `ativar` deixava de
    recusar o perfil que JÁ vale; `remover` deixava de recusar apagar o que vale (e o daemon segue
    aplicando arquivo que não existe); `voltar…` deixava de reaplicar depois de restaurar. E a lista
    perdia o realce. O dono consulta o daemon e, se calar, o marcador em disco (caminho do boot,
    `resolve_boot_profile`), e nunca levanta (falha de I/O vira `nao_sei`, aqui `""`).

    **O `find_by_slug` no fim impede DOIS vereditos na mesma tela** (02/09/2026): o nome do daemon
    ou do marcador é DIGITADO e seguia cru para o realce (`perfis_web._linhas_da_lista`, `p.name ==
    ativo`) e para as guardas (`mesmo_slug`, R-10, em `ativar` e `voltar…`). Medido com 33 perfis,
    daemon calado, marcador `sackboy` e perfil `Sackboy`: realce `[]` (nenhuma das 33 linhas acende)
    e Ativar → "já é o perfil que está valendo". O nome é resolvido aqui contra os perfis do disco e
    sai já sendo o `p.name` de uma linha, e o `==` de lá não discorda do `mesmo_slug`. **O marcador
    órfão cai junto** (perfil renomeado ou apagado por fora; `resolve_boot_profile` *"só resolve
    NOMES, não valida se o perfil carrega"*): sem casar com ninguém vira `""`, "não há", e a lista
    não acende linha.

    **O chip «Perfil ativo» NÃO passa por aqui e segue nomeando o órfão** (02/09/2026): é `<span
    class="pa-nome" data-campo="perfil">` do `topo.html` (das dez abas), pintado por
    `pacotes.topo()` com `ctx.state.get("active_profile")` CRU. Medido (`pacote_da_pagina` →
    `normalizar` → `topo`, dois perfis, dublê de ponte): daemon `"Perfil Que Ela Apagou"` → chip
    igual, linhas `[]`; `"sackboy"` → chip `"sackboy"`, linhas `["Sackboy"]` (a mesma tela com dois
    nomes para a mesma pergunta). A cura mora no dono compartilhado (`pacotes/__init__.py`, `topo`),
    não aqui: pacote de aba que emitisse `perfil` seria o segundo dono do cabeçalho (defeito
    fotografado às 04:23 de 02/09 na aba Sistema, em `a09_sistema.pacote`). A dívida tem régua em
    `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`.

    **Lista vazia não é prova de órfão, é a ausência de prova**, o que impede a cura de desarmar o
    §P7: só se rebaixa o nome a `""` quando há lista contra a qual conferi-lo. Medido em 02/09/2026,
    sob o `pytest` a `conftest.py` põe `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste e
    `load_all_profiles()` devolve `[]`; sem a guarda todas as réguas da aba medem o ramo vazio e a
    guarda de apagar o perfil que vale fica verde sem existir.

    `todos` é para quem já leu o disco neste tique (`pacote()` roda a cada 500 ms; 33 arquivos duas
    vezes por tique seria pagar de novo). Os gestos chamam sem ele: são um clique, não um laço.
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
    """"Remover", ou a PERGUNTA que a dica promete — sobre o alvo de AGORA.

    A dica diz *"Apaga do disco. Pergunta antes."* e esta janela não tem diálogo: o
    `on_profile_remove` da estável abre `gui_dialogs.confirm_delete_profile`
    (`profiles_actions.py`), GTK e MODAL, e os gestos rodam em thread (`hefesto_vivo.py`) e GTK só
    aceita diálogo no laço principal. O rótulo continua sendo a pergunta porque a tarja é AVISO e o
    rótulo é ESTADO: a tarja conta o que acabou de acontecer e vai em trinta segundos (desde
    13/09/2026, FRASES-E-DICAS-01, a recusa vai ao diário e à piscada do botão), e o rótulo diz,
    enquanto o armamento vive, qual perfil o próximo clique apaga. É o pedaço de tela que ela olha
    no instante do clique, e o mockup continua escrevendo "Remover".

    **O `alvo` é a cura de 02/09/2026, e sem ele o botão anunciava um perfil e apagava outro.** O
    armamento é por perfil (`remover` exige `_ARMADO[0] == nome`) mas o rótulo olhava só o RELÓGIO e
    seguia perguntando pelo armado depois de clicar noutra linha. Medido (dois perfis, dublê de
    ponte, ninguém valendo; ANTES = rótulo sem o `== alvo`, DEPOIS = o de hoje):

        passo                          ANTES                      DEPOIS
        1 clicou na linha do Pragmata  "Remover"                  "Remover"
        2 CLIQUE em Remover            arma o Pragmata, levanta   igual
        3 o rótulo, no tique seguinte  "Remover “Pragmata”? …"    igual
        4 clicou na linha do Sackboy   "Remover “Pragmata”? …"    "Remover"
        5 CLIQUE em Remover            arma o SACKBOY, levanta    igual
        6 o rótulo, no tique seguinte  "Remover “Sackboy”? …"     igual
        7 CLIQUE em Remover            APAGA o Sackboy            igual

    Só o passo 4 difere: o botão anuncia que o próximo clique apaga o Pragmata e o próximo clique
    arma o Sackboy. O clique que APAGA nunca ocorre sob botão dizendo "Pragmata" (no passo 6 o
    rótulo já diz "Sackboy", dentro de um tique de 500 ms). Com o alvo o rótulo volta a "Remover" ao
    trocar de linha, o que é a verdade: o próximo clique ARMA.
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

    Nasceu em 05/09/2026, da palavra de produto *"os svgs não deveriam aparecer prós demais
    controles desconectados"*. Antes o pacote mandava só as linhas da mesa e o `forEach` do
    bootstrap escrevia `''` no que sobrava, o que serve para APAGAR e nunca para ACENDER, e o lugar
    vazio precisa acender a classe `fora` e escrever `P3 • Desconectado`. ``para_o_vazio`` recebe o
    NÚMERO do lugar (1..4) e devolve o valor da linha (função, pois o rótulo traz o número). Sobra
    de mesa não é aparada: mesa maior que o desenho é outro defeito, e escondê-lo faria a função
    mentir sobre o tamanho da tabela.
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

    try:
        todos = os_perfis_de_escolher(load_all_profiles())
        foto = _foto_do_catalogo()
        ativo = _em_uso(ctx, todos)
        alvo = _alvo_do_editor(ctx, todos)
        escolhido = str(getattr(alvo, "name", "") or "")
        bruto = _tela.pacote_da_aba(todos, ativo=ativo or None,
                                    mesa=_mesa_com_rotulo(ctx.mesa, getattr(ctx, "conectados", ())),
                                    editado=alvo)
    except Exception:
        return {"sem_dono": {}, "cobertura": {"pintados": 0, "sem_dono": 1}}

    lista = _ordenada(_filtrada(_com_a_procedencia(bruto.get("lista") or [], todos, foto)))
    editor = bruto.get("editor") or {}
    fora = {
        "perfis.linha.nome": [x.get("nome", "") for x in lista],
        "perfis.linha.criado": [x.get("criado", "") for x in lista],
        "perfis.linha.modificado": [x.get("modificado", "") for x in lista],
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
    for chave in ("jogo", "estilo"):
        fora.setdefault(f"editor.{chave}", "—")
    for chave in CAMPOS_DO_EDITOR_NA_PAGINA:
        if chave in editor:
            fora[f"editor.{chave.replace('_', '.')}"] = editor[chave]
    if "jogo" in editor:
        fora["editor.jogo"] = _nome_no_campo(str(editor["jogo"] or ""), foto.nomes)

    alvo_do_editor = str(editor.get("alvo") or "")
    for valor in ALVOS_DO_PERFIL:
        fora[f"editor.alvo.{valor}"] = "sim" if valor == alvo_do_editor else ""
    # «Qual vale primeiro» só aparece com dois perfis do mesmo jogo (a lista vem em `blocos`).
    fora["editor.ordem.ha"] = "sim" if len(editor.get("ordem") or []) >= 2 else ""

    exigencia = _exigencia_para_esta_tela(getattr(alvo, "match", None))
    if _RECUSA_DO_JOGO[0] == escolhido:
        exigencia = _RECUSA_DO_JOGO[1] or exigencia
    else:
        _esquecer_a_recusa_do_jogo()
    fora["editor.jogo.exigencia"] = exigencia
    fora["editor.jogo.exige"] = "sim" if exigencia else ""

    for chave in _uma_vez_so(str(getattr(alvo, "name", ""))):
        fora.pop(chave, None)

    fora["perfis.remover"] = _rotulo_do_remover(escolhido)

    fora["perfis.desfecho"] = _desfecho_para_a_tela()
    if _servico_responde(ctx):
        _RECUSA_DO_ATIVAR[0] = ""
    fora[CAMPO_DA_RAZAO_DO_ATIVAR] = _RECUSA_DO_ATIVAR[0]

    guarda = bruto.get("guarda") or []
    if isinstance(guarda, list):
        # ela decide as duas metades de uma vez: o pacote passa a mandar as
        nomes_da_mesa = [g.get("nome", "") for g in guarda]
        fora["guarda.nome"] = _com_os_lugares_vazios(
            nomes_da_mesa, lambda n: _lugar_vazio(n, nomes_da_mesa)[0])
        fora["guarda.vazio"] = _com_os_lugares_vazios(
            ["" for _ in guarda], lambda _n: "sim")
        fora["guarda.id"] = _com_os_lugares_vazios(
            [g.get("id", "") for g in guarda], lambda _n: "")
        # barra de 3px que diz de quem é a linha, e ela era o `--plastico` do
        fora["guarda.plastico"] = _com_os_lugares_vazios(
            [g.get("plastico", "") for g in guarda],
            lambda n: _lugar_vazio(n, nomes_da_mesa)[1])
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
    procedencia, _recado = _procedencia_e_recado(
        getattr(alvo, "match", None), editor.get("ambiente_recado"), foto)
    sem_jogo = procedencia == PROCEDENCIA_DE_QUALQUER_JOGO
    if sem_jogo:
        procedencia = ""

    fora["blocos"] = {
        SELETOR_DA_LISTA: _html_da_lista(
            lista, str(bruto.get("lista_vazia") or ""), escolhido_na_lista),
        SELETOR_DOS_JOGOS: _html_dos_jogos(procedencia, foto),
        SELETOR_DA_ORDEM: _html_da_ordem(list(editor.get("ordem") or [])),
    }
    fora["cobertura"] = {"pintados": len(fora) + len(lista) * 3, "sem_dono": 0}
    return fora


from . import gesto  # noqa: E402


@gesto("10-perfis.html", "selecionar")
def selecionar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O clique na linha: abre o perfil no editor E o ativa (`profile.switch`).

    O Perfil ativo do cabeçalho e o editor mostram sempre o mesmo nome (A-ABA-PERFIS-DO-TODO-01).
    O nome vem da linha (`data-hef-perfil` → `hefPerfil`), com `texto` de volta. Perfil que já vale
    só abre, sem chamar o daemon; com o Modo Freestyle ligado só abre, pois o Freestyle manda.
    """
    global _ESCOLHIDO
    nome = str(o.get("hefPerfil") or o.get("texto") or "").strip()
    if not nome:
        raise ValueError("selecionar: o clique não trouxe o nome do perfil")
    _ESCOLHIDO = nome
    if ctx.state.get("freestyle_ligado"):
        return None
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    ativo = _em_uso(ctx)
    if ativo and mesmo_slug(ativo, nome):
        return None
    return _ativar_o(nome, p, ctx)


#: O campo que apaga o Ativar e escreve a razão na dica dele (`aba10.CAMPO_DA_RAZAO_DO_ATIVAR`).
CAMPO_DA_RAZAO_DO_ATIVAR = "perfis.ativar-razao"
#: A recusa do último Ativar com o serviço parado; some quando o serviço volta a responder.
_RECUSA_DO_ATIVAR: list[str] = [""]
SERVICO_NAO_SUBIU = "O serviço não subiu"
SERVICO_NAO_RESPONDEU = ("O serviço subiu e não respondeu à troca. Veja a aba Sistema e clique "
                         "de novo")
SERVICO_NAO_LIGOU = ("O serviço está parado e não liguei: ele não está instalado, ou um Hefesto "
                     "roda por fora. Veja a aba Sistema")


def _servico_responde(ctx: Contexto) -> bool:
    """O serviço respondeu o estado neste tique? A mesma conta do topo (`servico_do_menu`)."""
    from . import servico_do_menu

    return servico_do_menu(ctx.state) != "parado"


def _em_uso(ctx: Contexto, todos: list[Any] | None = None) -> str:
    """O perfil em uso, para a tela e para o clique: nenhum com o serviço parado.

    `_valendo` cai no marcador do disco quando o serviço cala, e é o que as guardas de apagar e de
    voltar precisam; a lista, a ordem e o «já vale» do clique não: o perfil do marcador só vale
    quando o serviço voltar (O-ATIVAR-DO-PERFIL-VALE-OU-A-TELA-DIZ-POR-QUE-01).
    """
    return _valendo(ctx, todos) if _servico_responde(ctx) else ""


def _recusar_o_ativar(frase: str) -> RuntimeError:
    """Guarda a recusa para o Ativar (campo `perfis.ativar-razao`) e a devolve para a tarja."""
    _RECUSA_DO_ATIVAR[0] = frase
    return RuntimeError(frase)


def _religar_o_servico() -> bool:
    """Liga o serviço parado antes da troca (um clique religa e troca, mesmo depois do Parar).

    Diz se ele subiu: sem unit, de pé ou com um avulso vivo o dono (`ativar_o_servico`) não liga.
    """
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja

    from . import a09_sistema

    try:
        subiu = a09_sistema.ativar_o_servico()
    except RuntimeError as erro:
        raise _recusar_o_ativar(f"{SERVICO_NAO_SUBIU}: {erro}") from erro
    if subiu:
        atos_da_bandeja.garantir_a_bandeja()
    return subiu


def _ativar_o(nome: str, p: Any, ctx: Contexto) -> dict[str, Any]:
    """`profile.switch` do perfil `nome`: o corpo único do clique na linha e do botão Ativar.

    Com o serviço parado, ele sobe antes (`_religar_o_servico`); se não sobe, a recusa vai à dica
    do Ativar e à tarja. A recusa do daemon NÃO some (ATIVAR-NAO-MENTE-01): `resultado` levanta e o
    gesto diz. A frase é do produto (`mensagem_de_ativacao`), com a carona do `launch_env.refresh`.
    """
    parado = not _servico_responde(ctx)
    subiu = _religar_o_servico() if parado else False
    try:
        corpo = p.resultado("profile.switch", name=nome)
    except RuntimeError as erro:
        if parado:
            raise _recusar_o_ativar(SERVICO_NAO_RESPONDEU if subiu else SERVICO_NAO_LIGOU) from erro
        raise RuntimeError(
            f"o Hefesto não confirmou a troca para {nome!r}") from erro
    _RECUSA_DO_ATIVAR[0] = ""
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_de_ativacao,
    )

    return _dizer(_com_a_carona(mensagem_de_ativacao(nome, corpo)))


@gesto("10-perfis.html", "ativar")
def ativar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Ativar o perfil que o editor mostra (`profile.switch`).

    O alvo é o do EDITOR (`_perfil_do_editor`) e não o texto do botão: o `texto` que o botão manda
    foi o «Ativar» pedido ao daemon como nome de perfil (01/09/2026), e a lista e o editor
    divergindo foi o defeito de 12/10. Sem perfil aberto recusa sem chamar o daemon; reativar o que
    já vale recusa dizendo, pois «aplicado» seria mentira.
    """
    nome = _perfil_do_editor(ctx)
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    ativo = _em_uso(ctx)
    if ativo and mesmo_slug(ativo, nome):
        raise RuntimeError(
            f"“{nome}” já é o perfil que está valendo. Escolha outro na lista "
            f"e clique em Ativar — reativar o mesmo não muda nada, "
            f"e dizer “aplicado” seria mentira.")
    return _ativar_o(nome, p, ctx)


@gesto("10-perfis.html", "voltar-a-de-ontem", grava="restaurar_do_historico")
def voltar_a_de_ontem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Desfazer a última gravação do perfil aberto. `profiles/loader.py`.

    `save_profile` copia o arquivo ANTERIOR para `profiles/.historico/<slug>/` a cada gravação
    (PERFIL-SEM-RASTRO-01) e `restaurar_do_historico` devolve a mais recente **byte a byte**; o
    único chamador era o `profile restore` da CLI e este é o segundo. Não pede confirmação
    (diferença para o "Remover"): a restauração ARQUIVA a versão atual antes de substituí-la, então
    restaurar por engano também tem volta.

    As duas chamadas depois do disco não são enfeite:

    * `profile.reaplicar`: **o daemon não relê JSON de perfil por conta própria**
    (PERFIL-SAVE-APPLY-01); sem ele o arquivo volta e o controle fica com o de agora (o sintoma lido
    como "não está salvando"). Só quando o restaurado é o que está VALENDO, pois reaplicar outro
    trocaria o perfil pelas costas dela. Era `profile.switch` até 01/10/2026, a ativação À MÃO, e o
    desfazer de perfil de jogo posto pelo autoswitch o gravava como escolha do usuário
    (O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01).
    * `launch_env.refresh`: a regra pode ter mudado, e com ela o `steam_app_<id>.env` de
      antecipação; é o aviso que Salvar e Remover da estável mandam (`footer_actions.py`), na ordem
      de lá (reaplicar, depois avisar).

    A comparação é por SLUG (R-10, `profiles/slug.py`): com "Navegação" no disco e "Navegacao" no
    daemon, `==` cru diria perfis diferentes e não reaplicaria.

    **É o gesto em que o silêncio era mais caro desta aba (03/09/2026)**: o arquivo inteiro é
    substituído (gatilho, luz, vibração, máscara) e a tela não mudava nada visível, então um
    desfazer mudo era indistinguível de um que não pegou. Por isso diz qual versão voltou, com a
    frase da CLI (*"perfil restaurado: X (versão …)"*): o nome do perfil e não o `Path`, e o carimbo
    sem o `.json`, forma que o `--em` do `profile restore` aceita, de modo que a frase é copiável
    para o comando que volta a outra versão. O subcomando que lista os carimbos é
    `profile historico` (noqa-acento: nome do subcomando da CLI, ASCII em `cmd_profile.py`).
    """
    from hefesto_dualsense4unix.profiles.loader import restaurar_do_historico
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    nome = _perfil_do_editor(ctx)
    _, versao = restaurar_do_historico(nome)
    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        p.profile_reaplicar(nome, prender=True)
    p.chamar("launch_env.refresh")
    return _dizer(_com_a_carona(
        f"Perfil restaurado: {nome} · versão {versao.stem}"))


#     2. reaplica, se for o ativo   `profile.switch` — o daemon NÃO relê JSON de
#     3. avisa a antecipação    `launch_env.refresh` — a regra pode ter mudado,


def _alvo_do_editor(ctx: Contexto, todos: list[Any] | None = None) -> Any:
    """O perfil aberto no editor: o DONO ÚNICO de quem pinta e de quem grava.

    Lê a lista de ESCOLHER, a que a tela mostra: a linha clicada (`_escolhido`), e sem ela o
    primeiro. O Freestyle nunca é o alvo, pois não está nela (a tela dele é o botão, 02/10/2026);
    até 09/10/2026 quem gravava lia a lista inteira, e com o Modo Freestyle ligado o editor mostrava
    «Corrida» e o renomear apagava o `freestyle.json`. `todos` é para o `pacote()`, que já leu o
    disco neste tique. `None` com a lista vazia.
    """
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    if todos is None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles
        from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher

        todos = os_perfis_de_escolher(load_all_profiles())
    escolhido = _escolhido([{"nome": x.name} for x in todos], _valendo(ctx, todos))
    alvo = find_by_slug(escolhido, todos) if escolhido else None
    if alvo is None and todos:
        alvo = todos[0]
    return alvo


def _perfil_do_editor(ctx: Contexto) -> str:
    """O nome do perfil que o editor mostra (`_alvo_do_editor`). Vazio é RECUSA."""
    nome = str(getattr(_alvo_do_editor(ctx), "name", "") or "")
    if not nome:
        raise RuntimeError("escolha um perfil na lista primeiro — a coluna da "
                           "esquerda; o editor abre na linha que você clicar.")
    return nome


def _o_perfil_no_disco(nome: str) -> Any:
    """`load_profile(nome)`: a base de todo gesto do editor que grava.

    O gesto lê o perfil do disco, muda o campo editado e grava o perfil inteiro, sem nada do
    aparelho (`D-2709-O-SALVAR-LE-O-PERFIL`): as outras abas gravam as escolhas no clique e o estado
    vivo não é escolha do usuário (até 27/09 esta base punha o vivo por cima, e mudar a PRIORIDADE
    ligava o microfone de um controle no PRAGMATA dela). A volta é pelo nome que o perfil TEM: quem
    renomeia (`perfis_renomear`) o faz DEPOIS, por `model_copy`, porque `DraftConfig.to_profile` com
    nome novo zera `match`, `mode` e `suppress_desktop_emulation` de propósito (R-11); por isso
    nenhum gesto do editor passa pelo rascunho.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return load_profile(nome)


#: INVERSÃO de `perfis_web.AMBIENTE_DO_PRESET`, e não uma segunda tabela: o
#: `from_simple_choice` faz com chave desconhecida (`simple_match.py:167`), e
PRESET_DO_ROTULO = {v: k for k, v in _tela.AMBIENTE_DO_PRESET.items()}


_CARONA_PENDENTE: str = ""


def _gravar(prof: Any, ctx: Contexto, p: Any, *, era: str = "") -> None:
    """Os três tempos: disco, reaplicar se for o ativo, avisar a antecipação.

    O corpo mora em `pacotes/perfil.py` desde 01/09/2026 (o `a06_navegacao`, que devolve os atalhos
    de botão ao de fábrica, é o segundo chamador; uma cópia esquece o `launch_env.refresh` no dia em
    que alguém mexer numa só) e este nome é a porta desta aba.

    **A carona entra AQUI e não em `perfil.gravar_e_reaplicar`** (06/09/2026, ONDA5-07-02): o censo
    por árvore de sintaxe achou NOVE gestos que gravam o perfil INTEIRO sem repor o atalho de
    inicialização que a Steam come, os que passam por este funil (`perfis.renomear`,
    `editor.estilo`, `editor.jogo`, `novo`, `duplicar`; eram oito com a Preferência, o «Funciona em»
    e o Detectar, que saíram com o desenho de 12/10) mais o `voltar-a-de-ontem`, que tem funil
    próprio (eram nove com o `editor.modo`, que saiu com o quadro «Modo» em 11/09/2026). Aquela
    função tem SEIS chamadores em CINCO abas e a interface é de ação imediata (clicar num tom ou
    degrau já grava): pendurar a carona lá seria varrer o `localconfig.vdf` **por clique**, opção
    que o dono da carona pesou e RECUSOU. Este funil é o único cujos gestos são o perfil INTEIRO e
    não um campo.

    A notícia não se perde: `_com_a_carona("")` devolve só a notícia (vazia sem nada a repor), ela
    fica em `_CARONA_PENDENTE` e o `_dizer` do gesto a junta ao desfecho. Sem isso o reparo
    aconteceria e a tira diria só "renomeado", o silêncio que o desfecho existe para curar.
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

    JOGO-QUE-SE-DIZ-01: `851100` sozinho não diz nada a ninguém, e a estável põe o nome ao lado do
    campo (`profile_jogo_reconhecido`, `profiles_actions._atualizar_frase_do_jogo`). Esta aba ganhou
    o rótulo em 06/09/2026 (decisão 10-Q4): *"Rótulo ao lado, ao vivo — à direita do campo aparece o
    nome do jogo (…), ou «não está nesta máquina», ou «não reconheci este endereço»"*; o desfecho do
    gesto continua dizendo o nome e o rótulo responde SEM gravar nada. Devolve o par inteiro, com o
    `é_alerta` que separa *"não instalado aqui (o número vale)"*, rotina, de *"não reconheci este
    endereço"*, erro (sem o bit as duas saem da mesma cor).

    A decisão é da função pura do produto, `jogos_locais.frase_do_campo_do_jogo(texto, nomes)`, a
    MESMA do rótulo de lá, com as mesmas respostas (nome, "não instalado aqui (o número vale)", "não
    reconheci este endereço" e o silêncio de quem digita); um `if` aqui seria a segunda verdade.

    **A quinta resposta veio com o terceiro argumento (11/09/2026, queixa de uso)**: o `<datalist>`
    passou a oferecer jogo de lançador, cujo `value` é a `wm_class` (``gotg.exe``), e o «Detectar»
    sempre gravou essa classe; sem as `chaves` o rótulo ficava MUDO (*"PRAGMATA"* para jogo da Steam
    e **nada** para um do Heroic).

    Nunca levanta (contrato de `_com_a_carona`): é acabamento de gesto que JÁ GRAVOU e também
    PINTURA, dez vezes por segundo; exceção lendo a biblioteca transformaria gravação bem-sucedida
    em tarja de recusa e derrubaria a aba por causa de um rótulo.
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

    O rótulo sai de `_match_label`, a função pura da coluna "Funciona em" (o desfecho não pode
    chamar de outra coisa um perfil que a lista chama de «Só quando eu escolher»). `texto` é o que o
    usuário digitou ou o que o «Detectar» achou (appid **ou `wm_class`**, desde 11/09/2026) e serve
    só para o nome do jogo; vazio, a frase termina no rótulo, o certo para "Todos" e "Steam".
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

    frase = f"“{prof.name}” agora vale em: {_match_label(prof.match)}"
    jogo = _jogo_reconhecido(texto)[0] if texto else ""
    return f"{frase} · {jogo}" if jogo else frase


def _so_mudou(o: dict[str, Any]) -> bool:
    """`False` quando o clique foi só um clique — e aí o campo não age."""
    return str(o.get("evento") or "") in ("", "change")


@gesto("10-perfis.html", "perfis.renomear", grava="_gravar")
def perfis_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Renomear o perfil da linha pelo duplo clique no nome: `save_profile` e `delete_profile`.

    O perfil é o da linha (`data-hef-perfil` → `hefPerfil`), não o do editor: o campo nasce na
    célula do nome (19/10/2026, o desenho escolhido; o campo «Nome» do editor saiu com o desenho do
    todo). Sem `hefPerfil`, vale o do editor.

    O valor vem de `valor` e não de `texto`: o ouvinte manda `texto: alvo.textContent`, vazio num
    `<input>`; desde 01/09 o clique traz o `value` (`hefesto_vivo.py`) e o piloto escuta `change`, o
    único evento que campo de texto dispara com o valor novo. Renomeia na hora porque esta aba não
    tem "Salvar" próprio (decisão de 01/09, *"clicar na cor já deveria aplicar a cor no controle"*;
    o do rodapé regrava o perfil ATIVO como o disco o tem, `rodape._draft_do_ativo`, e nem olha este
    campo): campo que aceita texto e não guarda é o botão que responde calado.

    Não há `rename` no produto (`profiles/loader.py` tem `save_profile`, `delete_profile`,
    `load_profile` e `restaurar_do_historico`); a estável faz a mesma dupla no Salvar, com o diálogo
    do R-10. Grava PRIMEIRO e apaga depois: invertida, falha no meio perderia o perfil. O antigo não
    some de vez: `delete_profile` arquiva a última versão em `profiles/.historico/<slug>/`
    (PERFIL-SEM-RASTRO-01), e um renomear por engano se desfaz com `hefesto-dualsense4unix profile
    restore <nome-antigo>`.

    Duas recusas: nome vazio (apagar o campo não vira arquivo `.json`) e nome que já é de OUTRO
    perfil (`save_profile` grava por SLUG, então renomear "Elden Ring" para "Pragmata" gravaria por
    cima, calado; o `_nome_livre` evita o mesmo no Duplicar).

    Diz que renomeou (03/09/2026, ver `_dizer`): o gesto que APAGA um `.json` e cria outro terminava
    mudo. A frase é a do produto, `mensagem_do_salvar(nome, renomeado_de=…)`, a mesma do rodapé da
    estável ("Perfil renomeado: era → novo"). Sem `reaplicou=`, o honesto: quem reaplica é
    `gravar_e_reaplicar`, que devolve `None` (`pacotes/perfil.py`); deduzir aqui se o daemon recebeu
    seria a segunda verdade sobre o que o gesto não mediu.
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
    from hefesto_dualsense4unix.profiles.manager import (
        e_o_freestyle,
        levar_o_perfil_renomeado,
    )

    novo = str(o.get("valor") or "").strip()
    do_editor = _perfil_do_editor(ctx)
    era = str(o.get("hefPerfil") or "").strip() or do_editor
    if not novo:
        raise RuntimeError("o perfil precisa de um nome — o campo ficou vazio.")
    if e_o_freestyle(novo):
        raise RuntimeError(FRASE_DO_FREESTYLE)
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
    levar_o_perfil_renomeado(prof.name, novo)  # a escolha, o último jogo e o Point and click
    if era == do_editor:
        _ESCOLHIDO = novo
    return _dizer(mensagem_do_salvar(novo, renomeado_de=prof.name))


def _sem_o_ajuste_do_estilo(controllers: Any, *, gatilho: bool,
                            vibracao: bool) -> tuple[dict[str, Any], int]:
    """O mapa `controllers` sem o gatilho e o degrau da vibração por controle.

    O estilo é a escolha mais nova para o perfil INTEIRO
    (O-ESTILO-CHEGA-AO-GATILHO-E-A-VIBRACAO-DE-CADA-CONTROLE-01) e no aparelho o ajuste do controle
    vence o global; o «Guardar» da aba Gatilhos grava sempre no do controle, então sem esta limpeza
    o controle com gatilho guardado ignorava todo estilo dali em diante. Sai `triggers` e, de
    `rumble`, só `policy` e `custom_mult`, de TODA entrada (o desligado também herda quando voltar);
    sair é deixar o `model_fields_set`, que o disco grava (`exclude_unset`), e não gravar `None` por
    cima. Luz, som, microfone, sensores, máscara e o equilíbrio dos motores e da háptica ficam.
    Devolve o mapa novo e QUANTOS controles deixaram o ajuste próprio.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        ControllerRumbleOverride,
    )

    saida: dict[str, Any] = {}
    largaram = 0
    for uniq, cfg in dict(controllers or {}).items():
        campos = {k: getattr(cfg, k) for k in cfg.model_fields_set}
        mudou = tinha = False
        if gatilho and "triggers" in campos:
            mudou = True
            tinha = campos.pop("triggers") is not None
        rumble = campos.get("rumble")
        degrau = (rumble.model_fields_set & {"policy", "custom_mult"}
                  if vibracao and rumble is not None else set())
        if degrau and rumble is not None:
            mudou = True
            tinha = tinha or any(getattr(rumble, k) is not None for k in degrau)
            resto = rumble.model_fields_set - degrau
            if resto:
                campos["rumble"] = ControllerRumbleOverride(
                    **{k: getattr(rumble, k) for k in resto})
            else:
                campos.pop("rumble")
        if not mudou:
            saida[uniq] = cfg
        elif campos:
            saida[uniq] = ControllerOverrides(**campos)
        largaram += int(tinha)
    return saida, largaram


def _tabela_do_molde(chave: str | None) -> dict[str, str]:
    """A tabela de botões de um molde de estilo (`estilos_de_jogo.MOLDES`); `{}` sem molde."""
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import MOLDES

    return dict(MOLDES.get(str(chave or ""), {}))


def _molde_do(estilo: Any) -> str | None:
    invisivel = getattr(estilo, "receita_invisivel", None)
    return getattr(invisivel, "molde", None)


def _com_a_tabela_do_estilo(prof: Any, estilo: Any) -> dict[str, Any]:
    """O que o estilo muda na tabela de botões do perfil: `button_actions` e `tabela_no_jogo`.

    Estilo com molde (o Point and click, o Visual novel) grava as linhas do molde por cima da
    tabela do perfil e liga a chave «Também no jogo», porque sem ela a tabela não age com o jogo
    aberto. As linhas que o molde do estilo ANTERIOR gravou e o usuário não mexeu saem antes:
    escolher outro estilo não deixa o PageUp do visual novel num jogo de tiro. O que o usuário
    escreveu à mão fica. Estilo sem molde só tira as linhas do anterior; a tabela do usuário
    não se toca.
    """
    anterior = _tabela_do_molde(_molde_do(_estilo_do_perfil(prof)))
    atual = dict(getattr(prof, "button_actions", None) or {})
    base = {b: a for b, a in atual.items() if anterior.get(b) != a}
    novo = _tabela_do_molde(_molde_do(estilo))
    if not novo:
        if len(base) == len(atual):
            return {}
        return {"button_actions": base or None, "tabela_no_jogo": None}
    return {"button_actions": {**base, **novo}, "tabela_no_jogo": True}


def _estilo_do_perfil(prof: Any) -> Any:
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

    return POR_CHAVE.get(str(getattr(prof, "estilo", "") or ""))


def _gatilho_do_lado(specs: Any, estilo: Any, lado: Any, ajustes: dict[str, int]) -> Any:
    """O ``TriggerConfig`` de UM lado: o L2 e o R2 do estilo são receitas separadas.

    Com imersão no ``Lado``, os números são os dela (a variante do estilo sobreposta); sem ela, o
    lado do acionamento do estilo leva os ``ajustes`` da receita e o outro, os números de partida.
    """
    from hefesto_dualsense4unix.profiles import efeitos_de_imersao
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig

    spec = specs.get_spec(lado.modo)
    if spec is None:  # pragma: no cover — o motor só nomeia modo do produto
        raise RuntimeError(
            f"o estilo “{estilo.rotulo}” pede o gatilho {lado.modo!r}, "
            f"que não é um dos modos do produto. Nada foi salvo.")
    numeros = ajustes if lado.modo == estilo.gatilho else {}
    if lado.imersao:
        imersao = efeitos_de_imersao.POR_CHAVE[lado.imersao]
        numeros = efeitos_de_imersao.ajustes_da_imersao(
            imersao, lado.modo, estilo.chave) or numeros
    return TriggerConfig(
        mode=lado.modo, params=list(specs.preset_to_positional_params(spec, numeros)))


def _efeito_da_luz_do_estilo(invisivel: Any, cor: tuple[int, int, int]) -> dict[str, Any]:
    """A base da luz do estilo (``Receita.luz_base``) na cor da unidade, ou nada (luz fixa).

    O efeito viaja no ``LedsConfig`` de CADA controle, com a cor DELE: a base não iguala as
    unidades que ``as_quatro`` separou. A maré e a chama usam a primeira cor; o arco-íris, nenhuma.
    """
    from hefesto_dualsense4unix.profiles.schema import escrever_o_efeito_da_luz

    base = getattr(invisivel, "luz_base", None)
    if not base:
        return {}
    cores = [] if base == "arco-iris" else [f"{cor[0]:02X}{cor[1]:02X}{cor[2]:02X}"]
    return {"efeito": escrever_o_efeito_da_luz(base, cores, int(invisivel.luz_ritmo))}


def _com_o_estilo(prof: Any, estilo: Any, mesa: list[dict[str, Any]]) -> tuple[Any, int]:
    """O perfil com a receita do estilo dentro, e QUANTOS controles ganharam cor.

    O estilo escreve o que o usuário aprovou em 03/09/2026 ao mandar construir o motor, **gatilho +
    vibração + luz**: `estilo.l2`/`r2` → `triggers.left/right`; `estilo.vibracao` → `rumble.policy`
    (o degrau, não multiplicador); a cor e a base da luz → `controllers[uniq].leds`, **uma por
    unidade**.

    Os parâmetros do gatilho não são digitados: `Estilo.gatilho` guarda só a CHAVE do modo
    (`AutoGun`, `PulseB`…) e as factories exigem posicionais sem default; `params=[]` passaria pelo
    esquema e explodiria no `apply()`, ou pior, `simple_rigid` com zonas zeradas é *"nenhuma zona
    ativa"* e a tela diz que aplicou. Os números vêm de `app/actions/trigger_specs.PRESETS` via
    `preset_to_positional_params(spec, {})`, a porta da aba Gatilhos (`a03_gatilhos._padroes`).

    A luz é por unidade porque a lei é do usuário: dois controles nunca têm a mesma cor, nem no
    mesmo perfil e estilo. Quem garante, medindo, é `estilos_de_jogo.as_quatro`, e a cor sai de
    `cor_da_unidade(estilo, jogador)`, nunca de cor escrita aqui. **O global `leds` NÃO é tocado**:
    cor no global é a que os quatro herdariam, o defeito que a lei proíbe. Dois controles no mesmo
    lugar é RECUSA, não escolha silenciosa: dois `jogador` iguais dariam a MESMA cor às duas peças,
    o único caminho pelo qual a lei cairia depois de o motor dizer que está tudo distinto.

    A receita invisível (08/10/2026, O-ESTILO-DO-JOGO-LIGA-A-IMERSAO-INTEIRA-EM-TODO-MODO-01) entra
    pelos motores existentes: `ajustes_do_gatilho` nos parâmetros do modo e o `modo` na seção `mode`
    (o Point and click liga a Navegação), que nasce em `manager.secao_do_modo_do_estilo`. O resto
    (`estilos_de_jogo.SO_DADO`) não se escreve aqui: o perfil guarda a CHAVE (`Profile.estilo`,
    O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01) e o motor do tato lê a receita por ela.

    `LedsConfig` com DOIS campos só é contrato: `_controllers_to_specs` lê `model_fields_set`
    (`profiles/manager.py`), e escrever `lightbar` e `lightbar_brightness` deixa `player_leds` e
    `auto_player_colors` SEM OPINIÃO (o controle herda o resto). Um `LedsConfig` "cheio" apagaria os
    LEDs de jogador de quem nunca pediu.
    """
    from hefesto_dualsense4unix.app.actions import trigger_specs as specs
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import cor_da_unidade
    from hefesto_dualsense4unix.profiles.manager import secao_do_modo_do_estilo
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        RumbleConfig,
        TriggersConfig,
        com_o_brilho_das_luzes_de,
    )

    mudanca: dict[str, Any] = {"estilo": estilo.chave}
    invisivel = estilo.receita_invisivel
    ajustes = dict(invisivel.ajustes_do_gatilho) if invisivel else {}
    if estilo.gatilho:
        direito = _gatilho_do_lado(specs, estilo, estilo.r2, ajustes)
        esquerdo = _gatilho_do_lado(specs, estilo, estilo.l2, ajustes)
        mudanca["triggers"] = TriggersConfig(left=esquerdo, right=direito)
    if estilo.vibracao:
        # CONSTRUÍDO, e não `model_copy`: o `custom_mult` do perfil antigo é
        mudanca["rumble"] = RumbleConfig(
            passthrough=bool(getattr(prof.rumble, "passthrough", True)),
            policy=estilo.vibracao)
    mudou, secao = secao_do_modo_do_estilo(prof.mode, invisivel.modo if invisivel else None)
    if mudou:
        mudanca["mode"] = secao
    mudanca.update(_com_a_tabela_do_estilo(prof, estilo))

    atuais, largaram = _sem_o_ajuste_do_estilo(
        prof.controllers, gatilho=bool(estilo.gatilho), vibracao=bool(estilo.vibracao))
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
        cor = cor_da_unidade(estilo, jogador)
        novos = LedsConfig(
            lightbar=cor,
            lightbar_brightness=estilo.brilho,
            lightbar_para_o_numero=jogador,
            **_efeito_da_luz_do_estilo(invisivel, cor))
        atuais[uniq] = dele.model_copy(
            update={"leds": com_o_brilho_das_luzes_de(dele.leds, novos)})
        pintados += 1
    if pintados or largaram:
        mudanca["controllers"] = atuais
    _sai_do_nativo(prof, mudanca)
    return prof.model_copy(update=mudanca), pintados


def _sai_do_nativo(prof: Any, mudanca: dict[str, Any]) -> None:
    """Quem sai do Nativo volta os três modos e o da aba Controles ao Personalizado.

    Sem isso o Automático que o Nativo pôs seguiria neutralizando o gatilho, a luz e a vibração
    do estilo seguinte (ou os ajustes à mão do Personalizado).
    """
    if getattr(prof, "estilo", None) != "nativo":
        return
    for campo in ("triggers", "leds", "rumble"):
        atual = mudanca.get(campo, getattr(prof, campo))
        mudanca[campo] = atual.model_copy(update={"modo": "personalizado"})
    mudanca["controles_modo"] = "personalizado"


def _com_o_nativo(prof: Any, estilo: Any) -> tuple[Any, int]:
    """O perfil no Nativo, e QUANTOS controles largaram o ajuste próprio de gatilho e vibração.

    Gatilho, luz e vibração ficam em Automático (`schema.perfil_no_modo` neutraliza a escolha, que
    segue no disco e volta no Personalizado), a vibração do perfil e a do controle perdem o degrau,
    a receita do tato sai e a tabela do molde anterior também. O Nativo não pinta controle.
    """
    from hefesto_dualsense4unix.profiles.manager import secao_do_modo_do_estilo
    from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO, RumbleConfig

    mudanca: dict[str, Any] = {
        "estilo": estilo.chave,
        "triggers": prof.triggers.model_copy(update={"modo": MODO_AUTOMATICO}),
        "leds": prof.leds.model_copy(update={"modo": MODO_AUTOMATICO}),
        "rumble": RumbleConfig(
            passthrough=bool(getattr(prof.rumble, "passthrough", True)),
            policy=None, modo="automatico"),  # (noqa-acento) chave ASCII
        "controles_modo": MODO_AUTOMATICO,
        "receita_do_tato": None,
    }
    mudou, secao = secao_do_modo_do_estilo(prof.mode, None)
    if mudou:
        mudanca["mode"] = secao
    mudanca.update(_com_a_tabela_do_estilo(prof, estilo))
    atuais, largaram = _sem_o_ajuste_do_estilo(prof.controllers, gatilho=True, vibracao=True)
    if atuais != dict(prof.controllers or {}):
        mudanca["controllers"] = atuais
    return prof.model_copy(update=mudanca), largaram


@gesto("10-perfis.html", "editor.estilo", grava="_gravar")
def editor_estilo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Estilo de Jogo": escolher um APLICA a receita inteira no perfil.

    **Ganhou motor em 03/09/2026, por decisão do usuário** (*"Construir o motor"*, alcance **gatilho
    + vibração + luz**). As receitas estão em `profiles/estilos_de_jogo.py` (*"o resto ta
    aprovado"*), de onde saem os rótulos do `<select>` (`aba10.ESTILOS`) e o que cada um faz; tabela
    neste arquivo divergiria no dia em que ela mudasse uma. Medido antes (produto instalado, daemon
    vivo, DualSense White no cabo): tela afirmava "Terror", `tarjas: []` e o md5 do
    `meu_perfil.json` igual ANTES e DEPOIS, nada gravou; à tarde passou a RECUSAR dizendo e agora
    **grava**.

    O estilo é um **VERBO**: resolve gatilho, vibração e luz de uma vez e dali quem manda são esses
    três, que ela reajusta nas abas sem nada "voltar atrás". O `<select>` mostra o estilo GUARDADO
    no perfil aberto (19/10/2026; antes ficava fora da pintura e mostrava o do perfil anterior), e
    só quando outro perfil abre: `editor.estilo` está em `CAMPOS_QUE_ELA_DIGITA`, então pintar
    nunca dispara este gesto nem reaplica a receita. O perfil guarda também a CHAVE
    (`Profile.estilo`, desde 09/10/2026, O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01), por onde o
    motor do tato acha a receita invisível que nenhuma aba mostra; o pacote de `perfis_web` já traz
    o rótulo do estilo, e pintá-lo é da tela
    (O-POINT-AND-CLICK-E-A-ACESSIBILIDADE-SE-DEFINEM-NA-NAVEGACAO-01).

    "Personalizado" não mexe nas abas e DESLIGA a receita: é o *"eu ajusto na mão"* (`as_quatro()`
    levanta de propósito se pedirem a cor). Grava só `estilo = "personalizado"`, sem receita
    invisível, e o motor do tato para de tocar a do estilo anterior; gatilho, vibração, luz e o
    desvio `receita_do_tato` ficam («canal a canal»). Até 09/10/2026 respondia sem gravar e o
    `estilo` antigo seguia no disco (O-PERSONALIZADO-DESLIGA-A-RECEITA-DO-ESTILO-ANTERIOR-01).

    `RuntimeError` nas recusas (`RECUSA-CHEGA-NA-TELA-01`, no alto do arquivo): é a única classe que
    `_recusou_dizendo` leva ao DOM. Saiu de `SEM_ECO` e continua fora: o `state_full` não publica o
    conteúdo do perfil, mas o `_gravar` chama `profile.switch` quando é o ativo, e é isso que leva
    luz e gatilho ao aparelho no mesmo segundo.
    """
    from hefesto_dualsense4unix.profiles import estilos_de_jogo as receitas

    # primeira escolha do usuário passar calada, que foi o defeito de manhã.
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    if escolhido == "—":
        escolhido = ""
    if not escolhido:
        raise RuntimeError(
            "escolha um estilo de jogo na lista — um estilo de jogo não foi "
            "salvo, e o que vale continua sendo o que está nas abas.")
    estilo = receitas.POR_ROTULO.get(escolhido)
    if estilo is None:
        raise RuntimeError(
            f"“{escolhido}” não é um dos estilos de jogo do produto. Nada foi "
            f"salvo, e o que vale continua sendo o que está nas abas.")
    nome = _perfil_do_editor(ctx)
    prof = _o_perfil_no_disco(nome)
    if estilo.chave == "personalizado":
        era = receitas.POR_CHAVE.get(str(getattr(prof, "estilo", "") or ""))
        if era is not estilo:
            mudanca: dict[str, Any] = {"estilo": estilo.chave}
            _sai_do_nativo(prof, mudanca)
            _gravar(prof.model_copy(update=mudanca), ctx, p)
        desligou = (f"a receita de “{era.rotulo}” foi desligada, e "
                    if era is not None and era is not estilo else "")
        return _dizer(
            f"“{estilo.rotulo}” em “{prof.name}”: {desligou}o que vale é o que "
            f"está nas abas.")
    if estilo.chave == "nativo":
        novo, largaram = _com_o_nativo(prof, estilo)
        _gravar(novo, ctx, p)
        proprio = (f" {largaram} controle{'s deixaram' if largaram != 1 else ' deixou'} "
                   f"o ajuste próprio de gatilho e vibração." if largaram else "")
        return _dizer(
            f"“{estilo.rotulo}” em “{prof.name}”: o jogo decide o gatilho, a vibração, a luz "
            f"e o toque.{proprio}")
    _, largaram = _sem_o_ajuste_do_estilo(
        prof.controllers, gatilho=bool(estilo.gatilho), vibracao=bool(estilo.vibracao))
    novo, pintados = _com_o_estilo(prof, estilo, ctx.mesa)
    _gravar(novo, ctx, p)
    luz = (f"e a luz de {pintados} controle{'s' if pintados != 1 else ''}"
           if pintados else "e nenhum controle ligado para acender")
    invisivel = estilo.receita_invisivel
    modo = ", e o modo Navegação" if invisivel and invisivel.modo else ""
    tabela = (" A tabela de botões do estilo entrou no perfil."
              if invisivel and invisivel.molde else "")
    proprio = (f" {largaram} controle{'s deixaram' if largaram != 1 else ' deixou'} "
               f"o ajuste próprio de gatilho e vibração." if largaram else "")
    return _dizer(
        f"“{estilo.rotulo}” aplicado em “{prof.name}”: gatilho, vibração {luz}{modo}."
        f"{tabela}{proprio}")


@gesto("10-perfis.html", "editor.jogo", grava="_gravar")
def editor_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Nome do Jogo": o programa (ou o número da Steam) que faz o perfil entrar.

    Só tem efeito em DUAS das cinco opções do "Funciona em": `from_simple_choice` só lê o
    `custom_name` em "game" e "steam_game"; com "Todos" ou "Steam" o texto seria descartado sem uma
    palavra. **Então o seletor anda junto**, o que desfaz um impasse medido antes de entregar: com o
    perfil em "Todos", escolher "Jogo" recusava por falta de nome (`MSG_JOGO_SEM_NOME`) e digitar o
    nome recusava por o seletor estar em "Todos", os dois caminhos fechados e o perfil preso.
    Digitar o nome é dizer "este perfil é deste jogo": o gesto grava a regra inteira e o seletor
    mostra o resultado no tique seguinte. O produto já faz isso (`_aplicar_nascimento_com_jogo`
    chama `_select_radio("steam_game")` **e** preenche o campo).

    Qual das duas: `normalize_appid` decide (só dígitos, ou endereço da loja, é "Jogo da Steam"; o
    resto é "Jogo", com o nome do programa), e só quando o seletor NÃO estava numa das TRÊS com
    campo livre ("Jogo", "Jogo da Steam", "Jogo (pela janela)", a terceira de ONDA5-10-01,
    06/09/2026): a escolha do usuário manda, e "1245620" digitado num perfil em "Jogo" não vira
    perfil da Steam pelas costas dela.

    R-12: o nome do programa vai **como ela digitar**, sem `.lower()`: o matcher compara com o
    basename cru de `/proc/PID/exe` e `Cyberpunk2077.exe` nunca casaria com `cyberpunk2077.exe`.

    Diz o que gravou (03/09/2026): reescreve a regra INTEIRA e movia o seletor calado. O desfecho
    nomeia o rótulo novo do "Quando usar" e, se o número é de jogo que a máquina conhece, o NOME
    dele (JOGO-QUE-SE-DIZ-01).

    **O campo se corrige (04/09/2026, decisão [04] do PO).** Colar o endereço da loja funciona
    (`normalize_appid` lê o número e a regra grava o número), mas a TELA seguia mostrando
    `https://store.steampowered.com/app/1599660/…` sobre regra que já guardava `1599660`. A correção
    só cabe aqui: `editor.jogo` está em `CAMPOS_QUE_ELA_DIGITA`, o tique NÃO o repinta no mesmo
    perfil (senão apagaria a segunda tecla) e a resposta deste gesto é o único instante em que a
    tela devolve a forma canônica, pintada na hora. O valor sai de `jogo_do_perfil`, a mesma
    função com que `perfis_web._pacote_do_editor` enche o campo a cada tique; um `if` local
    seria a segunda verdade.
    """
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        jogo_do_perfil,
    )

    global _RECUSA_DO_JOGO
    from hefesto_dualsense4unix.profiles.manager import e_o_freestyle

    if not _so_mudou(o):
        return None
    nome = _perfil_do_editor(ctx)
    cru = str(o.get("valor") or "").strip()
    if e_o_freestyle(cru):
        _RECUSA_DO_JOGO = (nome, FRASE_DO_FREESTYLE)
        return _dizer(FRASE_DO_FREESTYLE, **{"editor.jogo.exige": "sim",
                                             "editor.jogo.exigencia": FRASE_DO_FREESTYLE})
    _RECUSA_DO_JOGO = ("", "")
    try:
        nomes = _nomes_dos_jogos()
    except Exception:
        nomes = {}
    texto = _appid_do_nome(cru, nomes)
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
    # a regra foi reescrita por ela: o nome de quando o perfil nasceu já não diz esta regra
    prof.nome_do_jogo = None
    _gravar(prof, ctx, p)
    return _dizer(_agora_vale_em(prof, texto),
                  **{"editor.jogo": _nome_no_campo(
                      jogo_do_perfil(prof.match, prof.nome_do_jogo) or texto, nomes)})


ALVOS_DO_PERFIL = ("jogos", "navegacao", "programas", "eventos")
EVENTOS_DO_PERFIL = ("cena", "menu", "pausa", "controle_conectado", "programa_aberto",
                     "hora_marcada", "meu_comando")
#: O que a frase da tela diz de cada valor: o rótulo do botão e da opção, nunca o valor gravado.
ROTULO_DO_ALVO = {"jogos": "Jogos", "navegacao": "Navegação", "programas": "Programas",
                  "eventos": "Eventos"}
ROTULO_DO_MOMENTO = {"cena": "Cena", "menu": "Menu", "pausa": "Pausa",
                     "controle_conectado": "Controle conectado",
                     "programa_aberto": "Programa aberto", "hora_marcada": "Hora marcada",
                     "meu_comando": "Meu comando"}


@gesto("10-perfis.html", "editor.alvo", grava="_gravar")
def editor_alvo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Aplicar em»: onde o perfil vale (jogos, navegação, programas, eventos).

    Grava `Profile.alvo`. O de «Eventos» só entra pelo momento (`eventos_do_perfil`), nunca pela
    janela, salvo o «Programa aberto». Sair de «Eventos» leva junto o momento e o comando.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import mensagem_do_salvar

    novo = str(o.get("v") or o.get("valor") or "").strip()
    if novo not in ALVOS_DO_PERFIL:
        raise RuntimeError(f"“{novo}” não é um lugar onde o perfil vale. Nada foi salvo.")
    prof = _o_perfil_no_disco(_perfil_do_editor(ctx))
    if prof.alvo == novo:
        return None
    mudanca: dict[str, Any] = {"alvo": novo}
    if novo != "eventos":
        mudanca.update(evento=None, evento_comando=None)
    _gravar(prof.model_copy(update=mudanca), ctx, p)
    return _dizer(f"{mensagem_do_salvar(prof.name)} · aplica em {ROTULO_DO_ALVO[novo]}")


@gesto("10-perfis.html", "editor.quando", grava="_gravar")
def editor_quando(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Quando», do alvo Eventos: o momento (`evento`) e o comando (`evento_comando`).

    Quem chama: o `eventos_do_perfil` do daemon (Controle conectado, Meu comando) e o autoswitch
    (Programa aberto); Cena, Menu, Pausa e Hora marcada gravam sem motor, por falta de fonte.

    Os dois campos mandam o gesto; `data-que="comando"` marca o do comando, o outro é o momento.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import mensagem_do_salvar

    if not _so_mudou(o):
        return None
    prof = _o_perfil_no_disco(_perfil_do_editor(ctx))
    valor = str(o.get("valor") or "").strip()
    por_comando = str(o.get("que") or "") == "comando"
    momento = prof.evento if por_comando else (valor or None)
    comando = valor if por_comando else (prof.evento_comando or "")
    if momento is not None and momento not in EVENTOS_DO_PERFIL:
        raise RuntimeError(f"“{momento}” não é um momento que o perfil conhece. Nada foi salvo.")
    if (momento, comando or None) == (prof.evento, prof.evento_comando):
        return None
    _gravar(prof.model_copy(update={"evento": momento, "evento_comando": comando or None}),
            ctx, p)
    rotulo = ROTULO_DO_MOMENTO[momento] if momento else "—"
    return _dizer(f"{mensagem_do_salvar(prof.name)} · quando: {rotulo}")


def _valores_da_nova_ordem(atuais: list[int], teto: int) -> list[int]:
    """Os valores de `priority` do grupo, do que vale primeiro ao último, sem empate.

    Reaproveita os que o grupo já tem (decrescentes). Empate: o de cima sobe um acima do de baixo,
    e o teto (`PRIORIDADE_MAXIMA`) puxa de volta sem repetir.
    """
    novos = sorted(atuais, reverse=True)
    for k in range(len(novos) - 2, -1, -1):
        novos[k] = max(novos[k], novos[k + 1] + 1)
    return [max(0, min(v, teto - k)) for k, v in enumerate(novos)]


@gesto("10-perfis.html", "editor.ordem", grava="_gravar")
def editor_ordem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«Qual vale primeiro»: arrastar um perfil do mesmo jogo regrava a `priority` do grupo.

    Sem campo novo: a ordem é a `priority`, e é ela que o manager já lê. O grupo é o dos perfis
    com o mesmo jogo do aberto no editor (`perfis_web._ordem_do_jogo`).
    """
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import PRIORIDADE_MAXIMA

    movido = str(o.get("hefPerfil") or "").strip()
    # O item tem `tabindex` e recebe clique solto (e o Enter do teclado): só o `dragend` põe a
    # `posNova`, então sem ela não houve arrasto, e não há o que ordenar nem o que recusar.
    if not str(o.get("posNova") or "").strip():
        return None
    try:
        destino = int(str(o.get("posNova") or ""))
    except ValueError:
        raise RuntimeError(
            "não entendi para onde o perfil foi arrastado. Nada foi salvo.") from None
    aberto = _o_perfil_no_disco(_perfil_do_editor(ctx))
    grupo = _tela._ordem_do_jogo(aberto, load_all_profiles(), None)
    nomes = [x["perfil"] for x in grupo]
    if movido not in nomes or not 1 <= destino <= len(nomes):
        raise RuntimeError("esse perfil não está na lista deste jogo. Nada foi salvo.")
    atuais = {n: int(_o_perfil_no_disco(n).priority or 0) for n in nomes}
    nomes.remove(movido)
    nomes.insert(destino - 1, movido)
    valores = _valores_da_nova_ordem(list(atuais.values()), PRIORIDADE_MAXIMA)
    mexeu = False
    for nome, valor in zip(nomes, valores, strict=True):
        if atuais[nome] != valor:
            prof = _o_perfil_no_disco(nome)
            _gravar(prof.model_copy(update={"priority": valor}), ctx, p)
            mexeu = True
    if not mexeu:
        return None
    return _dizer(f"Ordem salva · {nomes[0]} vale primeiro")


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


@gesto("10-perfis.html", "novo", grava="_gravar")
def novo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Novo": um perfil em branco no disco, já com a regra do jogo em foco.

    Nasce no DISCO e não num rascunho porque esta aba não tem "Salvar" próprio (a estável só
    PREENCHE O EDITOR, `on_profile_new`, e o botão seguinte grava); com a ação imediata o arquivo
    nasce e a lista o mostra no tique seguinte, já aberto. A regra do jogo em foco e a guarda são as
    do produto: `_aplicar_nascimento_com_jogo` só age com **appid da Steam** e devolve `False`
    calado no resto; com jogo da Steam em foco nasce mirando aquele jogo, sem ele nasce catch-all,
    "que é o certo para um perfil de desktop".

    **A prioridade deixou de nascer em zero (03/09/2026, PERFIL-NASCE-CERTO-01).** Dizia-se que a
    conta *"mora num mixin GTK que depende de widget"*; não depende:
    `_prioridade_acima_dos_catch_all` lê UM atributo, `self._profiles_cache`, e faltava só entregar
    a lista, que esta aba tem. O defeito (medido em 26/07, ela jogando): perfil criado para o
    Pragmata nasceu 0 e NUNCA valia, pois o catch-all dela (100) vencia o resto; **a janela não
    tinha saída**. Medido no disco do usuário, os catch-all são `meu_perfil` (1) e `fallback` (0),
    folga **11**, e os perfis de jogo dele estão em 80: a conta promete vencer os "vale sempre", não
    todo mundo. Chama a função da janela e não uma segunda conta (`max(catch-all) + 10`): teto
    (`PRIORIDADE_MAXIMA`), folga (`_FOLGA_ACIMA_DO_CATCH_ALL`) e o que É catch-all
    (`Profile.e_catch_all`) ficariam com dois donos. Não é ativado: nascer não é passar a valer.

    **Nasce SEM a seção `mode` (11/09/2026).** Com o quadro «Modo» fora do editor ninguém respondia
    *"que modo tem um perfil criado aqui?"*; é `None`, **«Não mexer no modo»**, o perfil sem
    opinião, como todo perfil nascia antes de 06/09; outro padrão faria o novo MEXER no modo da
    máquina sem pedido, a cicatriz do `or "xbox"` do Salvar da estável (ESCOLHA-DELA-VENCE-01/E1).
    **A exceção (20/10/2026):** o jogo da Steam cuja ponte o prontuário confirmou nasce com essa
    máscara (`_o_modo_que_o_jogo_pede`). Quem muda depois é a aba Jogar, e nada aqui zera o campo
    de perfil que já o tem: o gesto cria arquivo novo, não reescreve os dela.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    classe = _classe_de_outro_app(ctx)
    appid = steam_appid_from_wm_class(classe) if classe else None
    regra = (from_simple_choice("steam_game", str(appid)) if appid is not None
             else MatchAny())
    return _dizer(_nascer(ctx, p, regra, "Novo perfil"))


def _o_modo_que_o_jogo_pede(regra: Any) -> Any:
    """A seção `mode` com a máscara que o prontuário confirmou para o jogo da regra, ou `None`.

    O produto só SABE a máscara de um jogo quando uma ponte foi confirmada nele
    (`prontuario_dos_jogos.pontes_confirmadas`, por appid da Steam): é a tupla que o carimbo
    guarda, e a máscara do carimbo vale para os quatro controles (`mode.gamepad_flavor` é do
    perfil, cabo e rádio; a de uma peça só mora em `controllers`). Sem ponte de gamepad com
    máscara, devolve `None` e o perfil segue sem opinião, o padrão que o daemon aplica.
    """
    from hefesto_dualsense4unix.integrations.prontuario_dos_jogos import pontes_confirmadas
    from hefesto_dualsense4unix.profiles.schema import (
        MatchCriteria,
        ProfileModeConfig,
        normalizar_gamepad_flavor,
    )
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    if not isinstance(regra, MatchCriteria):
        return None
    appids = [str(a) for a in map(steam_appid_from_wm_class, regra.window_class) if a is not None]
    if not appids:
        return None
    pontes = pontes_confirmadas()
    for appid in appids:
        ponte = pontes.get(appid)
        mascara = normalizar_gamepad_flavor(ponte.gamepad_flavor) if ponte is not None else None
        if ponte is not None and ponte.kind == "gamepad" and mascara is not None:
            return ProfileModeConfig(kind="gamepad", gamepad_flavor=mascara)
    return None


NOME_DO_PERFIL_NOVO = "Novo perfil"


def _nascer(ctx: Contexto, p: Any, regra: Any, base: str, *, jogo: str | None = None) -> str:
    """O perfil novo no disco, já aberto no editor — o gravador dos dois caminhos.

    **Nasce dizendo o jogo e levando a máscara dele** (O-PERFIL-QUE-NASCE-NA-LANCADORES-DIZ-O-JOGO-
    E-LEVA-A-MASCARA-01): `jogo` (ou, sem ele, o `base` que não é o nome de fábrica) vai para
    `Profile.nome_do_jogo`, e o «Nome do jogo» do editor o mostra mesmo quando a regra tem várias
    janelas; a máscara vem de :func:`_o_modo_que_o_jogo_pede` quando o prontuário a sabe.
    """
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
    dito = jogo if jogo is not None else (base if base != NOME_DO_PERFIL_NOVO else "")
    _gravar(Profile(name=nome, match=regra, priority=prioridade, nome_do_jogo=dito or None,
                    mode=_o_modo_que_o_jogo_pede(regra)), ctx, p)
    _ESCOLHIDO = nome
    return f"Perfil criado: {nome}"


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
    jogo = nome_do_jogo.strip()
    try:
        return _nascer(ctx, p, regra, jogo or NOME_DO_PERFIL_NOVO, jogo=jogo)
    except ValueError:
        return _nascer(ctx, p, regra, NOME_DO_PERFIL_NOVO, jogo=jogo)


@gesto("10-perfis.html", "duplicar", grava="_gravar")
def duplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Duplicar": o perfil inteiro numa cópia, e o editor abre nela.

    A dica promete *"Copia o perfil inteiro para o editor, com «(cópia)» no nome"*: a cópia nasce no
    disco e o `_ESCOLHIDO` passa a ser ela, que o editor pinta no tique seguinte. "Inteiro" é
    literal (BUG-DUPLICATE-NO-CONFIG-COPY-01, já pago pela estável: a cópia tinha só o nome trocado
    e o resto virava default): o `model_copy` leva gatilhos, luz, vibração, alto-falante, máscara e
    os overrides por controle, tudo menos o nome.

    A cópia NÃO é ativada (a coluna tem o "Ativar"), por isso `_gravar` não reaplica: o nome novo
    nunca é o ativo. O número no fim ("(cópia) 2") evita que duplicar duas vezes grave a segunda POR
    CIMA da primeira (`save_profile` escreve por slug).

    **A exceção a "inteiro" é o carimbo de ponte (03/09/2026).** O `model_copy` levava o `ponte`
    junto e a estável o CORTA de propósito: em `_build_profile_from_editor` o duplicar entra como
    estreia (`estreia = _new_profile or _duplicate_source is not None`), o degrau 2 de
    `carimbo_que_o_save_leva` é cortado e o degrau 1, o disco pelo nome NOVO, devolve `None`.
    Importa no gesto seguinte, repontar a cópia para OUTRO jogo: com o carimbo herdado,
    `pontes_confirmadas()` publica ponte que ninguém provou naquele appid e a escada de
    `integrations/ponte_escada.py` para num jogo nunca testado. **O carimbo é REGISTRO de uma
    confirmação, não configuração que se copia.** A regra não é reescrita aqui: decide
    `carimbo_que_o_save_leva`, o dono que a aba Perfis e o rodapé consultam (`profile_writer.py`);
    os argumentos são os do caso (`existente` é quem ocupa o nome novo, ninguém, pois `_nome_livre`
    acabou de garantir; sem rascunho), e se a escada mudar esta linha muda com ela.
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
    from hefesto_dualsense4unix.profiles.manager import esquecer_o_perfil_apagado

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
    esquecer_o_perfil_apagado(nome)  # o dono do `profile delete`: a escolha e o último jogo
    _ESCOLHIDO = ""
    # SEM `profile.switch` AQUI, de propósito: o perfil apagado não é o ativo
    p.chamar("launch_env.refresh")
    # `_dizer` E NÃO `_anotar` — 03/09/2026. Os dois guardam a frase; só o
    return _dizer(f"Perfil removido: {nome}")


@gesto("10-perfis.html", "recarregar")
def recarregar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Recarregar": reler a lista do disco AGORA, e dizer que releu.

    Era um botão morto com aparência de vivo (03/09/2026): o `data-hef-gesto="recarregar"` estava na
    página desde 31/08 sem `@gesto`, o piloto caía no ramo SEM DONO e imprimia `[gesto sem dono]
    10-perfis.html · recarregar` no stdout de quem lançou a janela, sem tarja (`_recusou_dizendo` só
    pinta exceção de HANDLER). Havia a justificativa *"a lista já é relida do disco a cada 500 ms,
    ligá-lo seria fingir trabalho"*, certa na premissa e errada na conclusão: a estável tem o MESMO
    botão sobre lista em cache (`on_profile_reload` → `_reload_profiles_store` + toast "Lista
    recarregada", `profiles_actions.py`). O trabalho dele não é ler, é **dizer que leu**.

    Chama `pacote()`, que relê o disco, e devolve a carga INTEIRA (o `blocos` da lista, a contagem,
    o editor), pintada no ato (`_deu_certo` → `window.__hef.pintar`) e não no tique seguinte. Não
    fala com o daemon, por isso não está em `PROVAS` (o disco é a fonte da lista e o `state` do
    ativo já chegou pelo tique); é o segundo gesto da aba sem chamada de ponte, o outro é
    `selecionar`. A frase é a da estável, palavra por palavra, `"Lista recarregada"`, com o número
    de perfis, que faz o clique VALER (ela relê para conferir que o novo apareceu).
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
    """A lupa: guarda o que o usuário digitou, e o tique seguinte mostra a lista curta.

    É um gesto VIVO (`data-hef-vivo`), a quarta porta do piloto, a que dispara a cada TECLA e por
    contrato só LÊ. **Não pinta nada**: o vivo tem `CHAVES_QUE_O_VIVO_RECUSA = ("blocos", "fita",
    "recado", "recados")` e resposta que troque HTML é recusada na porta, então o gesto só ANOTA e
    quem mostra é o tique de 100 ms, por `_filtrada`, uma linha acima de onde a lista vira tela
    (latência de um décimo de segundo). **Não grava**: `_PROCURA` mora na memória da janela, pois
    filtro vindo do disco esconderia perfis na próxima abertura sem ela ter digitado. O termo vem do
    `valor` e não do `texto`: num `<input>` o `textContent` é vazio (o defeito que deixou quatro
    campos sem dono em 01/09).
    """
    global _PROCURA
    _PROCURA = str(o.get("valor") or "")
    return {}


#: a frase do primeiro e a do segundo duplo clique: texto (de A a Z) e data (do mais novo).
_SENTIDO_DA_FRASE = {False: ("de A a Z", "de Z a A"),
                     True: ("do mais novo ao mais antigo", "do mais antigo ao mais novo")}


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
        sentidos = _SENTIDO_DA_FRASE[coluna in COLUNAS_DE_DATA]
        frase = f"Ordenado por {_NOME_DA_COLUNA[coluna]}, {sentidos[0]}"
    elif sentido == "asc":
        _prefs.guardar_ordem_da_tabela(TABELA_DA_LISTA, coluna, "desc")
        sentidos = _SENTIDO_DA_FRASE[coluna in COLUNAS_DE_DATA]
        frase = f"Ordenado por {_NOME_DA_COLUNA[coluna]}, {sentidos[1]}"
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
    # O clique na linha ATIVA o perfil e o abre; o botão «Ativar» lê o editor e tem teste próprio
    # (`test_o_ativar_age_sobre_o_perfil_do_editor`), pois a régua não abre uma linha antes.
    {"pagina": PAGINA, "gesto": "selecionar",  # (noqa-acento) id
     "clique": {"hefPerfil": "Bancada"},
     "chama": [("resultado", ["profile.switch"], {"name": "Bancada"})]},
]

#: O QUE NÃO ECOA NO `state_full`. A razão é uma só e está
SEM_ECO = ("perfis.renomear", "editor.jogo", "editor.estilo",
           "editor.alvo", "editor.quando", "editor.ordem", "novo", "duplicar", "remover",
           "voltar-a-de-ontem", "recarregar",
           # `state_full` muda quando o usuário arrasta uma divisa.
           "procurar", "ordenar", "largura-da-coluna")


AGORA_NAO_DIZ = TRAVESSAO

#: A dica da célula neutra, e a da máscara que não é a DualSense (decisão de produto
#: de 29/09, pergunta [40]: «Aceso no DualSense», com a dica dizendo qual).
DICA_DO_NAO_DIZ = "O controle não diz"
DICA_DA_MASCARA = "Máscara: {mascara}"


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

    Medido em 02/10/2026 no `state_full`: nenhuma chave `trigger_*` por controle (`trigger_replicas`
    é a contagem da réplica do pad virtual) e o DualSense não devolve o efeito
    (`a03_gatilhos.SEM_ECO`). A célula fica neutra e o disco não a preenche até a publicação virar
    sprint própria.
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


def _da_acessibilidade(entrada: dict[str, Any], secao: str) -> bool | None:
    """O bloco `acessibilidade` do daemon (`_merge_acessibilidade`); `None` = não disse."""
    bloco = entrada.get("acessibilidade")
    valor = bloco.get(secao) if isinstance(bloco, dict) else None
    return valor if isinstance(valor, bool) else None


def _ativacao_agora(entrada: dict[str, Any], _state: dict[str, Any],
                    _linha: dict[str, Any]) -> bool | None:
    """Um modo de botão ou um filtro vale neste controle agora."""
    return _da_acessibilidade(entrada, "ativacao")  # (noqa-acento) chave ASCII


def _analogicos_agora(entrada: dict[str, Any], _state: dict[str, Any],
                      _linha: dict[str, Any]) -> bool | None:
    """Uma curva, zona morta ou mão vale nos analógicos deste controle agora."""
    return _da_acessibilidade(entrada, "analogicos")  # (noqa-acento) chave ASCII


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
    "ativacao": _ativacao_agora,  # (noqa-acento) chave ASCII
    "analogicos": _analogicos_agora,  # (noqa-acento) chave ASCII
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
            fora.append(("sim" if aceso else "", _dica_do_agora(secao, entrada)))
    return fora


def _dica_do_agora(secao: str, entrada: dict[str, Any]) -> str:
    """A dica de uma célula que tem o que dizer além de aceso ou apagado.

    Hoje só os «comandos virtuais» (A-MIRA-DA-CALIBRAR-E-A-MESMA-DAS-OUTRAS-ABAS-01): o `title` diz
    os quatro ajustes da Mira DESTE controle, pelo leitor da Calibrar (`a11.resumo_da_mira`) sobre o
    bloco `mira` do daemon. Sem o bloco, nada: a tela não inventa número.
    """
    if secao != "movimento":
        return ""
    from .a11_calibrar_sensores import resumo_da_mira

    return resumo_da_mira(entrada.get("mira")) or ""


def _entrada_viva(conectados: Any, uniq: str) -> dict[str, Any]:
    """A entrada do daemon deste `uniq` (`Contexto.conectados`), ou `{}`."""
    for entrada in conectados or ():
        if isinstance(entrada, dict) and str(entrada.get("uniq") or "") == uniq:
            return entrada
    return {}
