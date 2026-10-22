#!/usr/bin/env python3
"""O pacote da aba `03` Gatilhos — e ele nasceu ERRADO, corrigido em 01/09/2026.

O QUE ESTAVA ESCRITO AQUI, e estava errado:

    "o modo escolhido      NÃO EXISTE no state    ← sem dono
     o efeito pronto       NÃO EXISTE no state    ← sem dono
     os ajustes do modo    NÃO EXISTEM no state   ← sem dono"

A parte factual continua verdadeira: o `state_full` do daemon **não** publica
`triggers`, e o DualSense não devolve o modo em que está — gatilho adaptativo é
comando de ida. O que estava errado era a CONCLUSÃO: dali se tirou "não tem
dono" e pintei quatro travessões.

A PERGUNTA QUE DESFEZ O ERRO: o dado tem dono, e são dois, os dois já no
produto:

    profiles/schema.py       `triggers.left/right` → `mode` e `params`
    app/actions/trigger_specs.py   `PRESETS`: `name` (disco) → `label` (tela)
                                   e cada `param` com nome, faixa e padrão

MEDIDO NO DISCO DO USUÁRIO, perfil "Ação", em 01/09/2026::

    triggers.left  = {"mode": "Rigid",     "params": [0, 180]}
    triggers.right = {"mode": "Vibration", "params": [3, 8, 20]}

Cinco dos 33 perfis do usuário têm gatilho configurado. Mostrar `—` ali era apagar da
tela uma escolha que ela salvou.

O QUE AINDA NÃO TEM DONO, e agora a lista é honesta: nada desta aba. O que muda
é a NATUREZA do valor — ele é o que o **perfil manda ao controle**, não o que
está **aceso no plástico**, e essas são coisas diferentes. Como o aparelho não
devolve a segunda, a primeira é a melhor verdade disponível, e a tela diz de
qual está falando. No lado que o perfil não escreve, o que ele manda é o
nascimento do esquema (24/09/2026, ver `_o_que_o_controle_recebe`).
"""
from __future__ import annotations

import importlib
import re
import time
from typing import Any

from hefesto_dualsense4unix.interface.monta import MODO_AUTOMATICO

from . import Contexto, jogador_de, perfil, registrar
from .meus_efeitos import (
    PREFIXO_DO_MEU,
    TETO_DO_NOME,
    criar_efeito,
    guardar_meus_efeitos,
)
from .meus_efeitos import meus_efeitos as _meus_efeitos_da

SEM_DONO: dict[str, str] = {}

LADOS = {"e": "left", "d": "right"}

NOME_DO_LADO = {"left": "Gatilho esquerdo (L2)", "right": "Gatilho direito (R2)"}

VAZIO = ""

#: A escada da força do aperto (16/10/2026): quantos degraus, e o endereço de cada gatilho.
DEGRAUS_DA_FORCA = 8
CAMPO_DA_FORCA = {"l2": "forca-l2", "r2": "forca-r2"}


def nivel_da_forca(cru: Any) -> int:
    """Quantos degraus o aperto acende: `0..255` vira `0..8`; sem leitura é o repouso."""
    if not isinstance(cru, int) or isinstance(cru, bool):
        return 0
    return max(0, min(cru, 255)) * DEGRAUS_DA_FORCA // 255


PAGINA = "03-gatilhos.html"

_LUGAR_VAZIO = re.compile(r'data-controle="(p\d+)"[^>]*data-conectado="nao"')

_QUALQUER_LUGAR = re.compile(r'data-controle="(p\d+)"')

_SELECT = re.compile(
    r'<select[^>]*class="(?P<classe>g2-acion|g2-imersao)"[^>]*>'
    r'(?P<dentro>.*?)</select>', re.S)

#: a classe do campo na página → o campo que ele é
_CAMPO_DA_CLASSE = {"g2-acion": "modo", "g2-imersao": "imersao"}

_COMO_O_DOM_ESCREVE = re.compile(r"\s(disabled|hidden|readonly|required)(?=[\s>])")

_COMENTARIO_CSS = re.compile(r"/\*.*?\*/", re.S)

_ENDERECOS: frozenset[str] | None = None
_VAZIOS: frozenset[str] | None = None
_OFERECE: dict[str, frozenset[str]] | None = None


def _pagina_publicada() -> str:
    """O HTML que o produto renderiza AGORA, ou `''` se não der para ler."""
    from hefesto_dualsense4unix.interface import onde

    try:
        return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return ""


def sem_comentarios_de_css(doc: str) -> str:
    """O documento sem os `/* … */` — e sem espaço, para casar declaração."""
    return _COMENTARIO_CSS.sub(" ", doc).replace(" ", "").replace("\n", "")


def _o_que_o_select_oferece() -> dict[str, frozenset[str]]:
    """Os `value` que cada campo de escolha da página publicada aceita."""
    global _OFERECE
    if _OFERECE is None:
        fora: dict[str, set[str]] = {"modo": set(), "imersao": set()}
        for m in _SELECT.finditer(_pagina_publicada()):
            fora[_CAMPO_DA_CLASSE[m.group("classe")]].update(
                re.findall(r'<option[^>]*value="([^"]*)"', m.group("dentro")))
        _OFERECE = {k: frozenset(v) for k, v in fora.items()}
    return _OFERECE


def _enderecos_da_pagina() -> frozenset[str]:
    """Todo `data-campo` que a página publicada tem. Vazio se ela não abrir."""
    global _ENDERECOS
    if _ENDERECOS is None:
        _ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', _pagina_publicada()))
    return _ENDERECOS


def _lugares_que_o_desenho_da_por_vazios() -> frozenset[str]:
    """Os `pref` que a página publicada já marca `data-conectado="nao"`.

    POR QUE O PACOTE PRECISA SABER DISSO, e é o defeito D4, medido em
    02/09/2026: os quatro `<select>` das colunas P3 e P4 são **endereço morto**.
    O piloto preenche todo lugar que a mesa não tem com `dict.fromkeys(chaves,
    "—")` (`pacotes/__init__.py:501`), e `escrever()` **recusa** escrever um
    valor que o `<select>` não oferece (`hefesto_vivo.py:170-174`) — a recusa é
    CERTA, porque escrever qualquer outra coisa deixaria o campo em branco
    somando +1 por tique para sempre. O desfecho é que o travessão nunca pousa e
    a coluna vazia continua mostrando o que o gerador escreveu.

    Enquanto o valor cravado é `Off`/`custom`, isso passa por inofensivo. **Ele
    não é**: o dia em que um controle sai do P3 com `Rígido` aplicado, o
    `Rígido` FICA na tela — a coluna de um lugar sem aparelho afirmando um
    efeito. É a nona aparição do defeito que esta casa nomeia, *a tela afirmando
    o que não é*, e a única cura é o pacote escrever ali um valor que o
    `<select>` aceite.

    POR QUE SÓ OS LUGARES QUE O DESENHO JÁ DÁ POR VAZIOS, e não todo lugar
    vazio: quem emite uma coluna SAI da conta `TODOS_OS_LUGARES - vivos` do
    piloto, e com ela perde o `data-conectado="nao"` que o piloto escreveria —
    que é o que segura o `pointer-events:none` do lugar vazio. Nas colunas que a
    página já dá por vazias isso não custa nada (a marca está no arquivo); numa
    que a página dá por conectada — o P2 com um controle só na mesa — custaria a
    trava. O acoplamento é do piloto (ele deduz "vazio" de "quem não emitiu", em
    vez de perguntar à mesa) e a cura é lá; aqui fica a metade que não regride.
    """
    global _VAZIOS
    if _VAZIOS is None:
        _VAZIOS = frozenset(_LUGAR_VAZIO.findall(_pagina_publicada()))
    return _VAZIOS


def _todos_os_lugares_da_pagina() -> frozenset[str]:
    """Os `pref` de TODAS as colunas da página publicada, cheias ou vazias."""
    return frozenset(_QUALQUER_LUGAR.findall(_pagina_publicada()))


#: O QUE O DESENHO OFERECE PARA DIZER "NÃO HÁ NADA AQUI" — decisão 13,
TRAVESSAO = "—"


def _sem_nada(campo: str, cravado: str) -> str:
    """O que este campo mostra num lugar SEM APARELHO, hoje."""
    return VAZIO if TRAVESSAO in _o_que_o_select_oferece().get(campo, ()) else cravado


def _escapar(texto: str) -> str:
    """O mínimo para um texto de dado caber num atributo e num nó de texto."""
    return (texto.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _modulo_do_src(nome: str) -> Any:
    """Um módulo do produto, importado do `src/`, ou `None` se ele não abrir."""
    try:
        perfil._com_o_src()
        return importlib.import_module(f"hefesto_dualsense4unix.{nome}")
    except Exception:
        return None


def _specs() -> Any:
    """A tabela de presets do produto, ou `None` se o `src/` não abrir."""
    return _modulo_do_src("app.actions.trigger_specs")


DICA_DO_MODO = {
 "Off": "O jogo manda no gatilho; sem jogo, ele fica solto, como num controle comum.",
 "Resistance": "Peso firme a partir do ponto escolhido, sem estalo — pedal, alavanca, remada.",
 "Weapon": "Resiste, estala e rearma sozinho a cada aperto: um tiro por aperto.",
 "Bow": "Fica cada vez mais pesado até o fim do curso, e então solta de uma vez.",
 "Galloping": "Batidas ritmadas enquanto o gatilho está apertado — cavalo correndo, motor pegando.",
 "Machine": "Batidas rápidas e fortes enquanto apertado.",
 "Vibration": "Treme o gatilho na frequência escolhida, sem opor força.",
 "SlopeFeedback": "A força sobe em linha reta do início ao fim do curso.",
 "MultiPositionFeedback": "A força sobe em dez degraus ao longo do curso, do solto ao máximo.",
 "MultiPositionVibration": "Treme cada vez mais forte à medida que o gatilho afunda.",
 "Custom": "O modo e as sete forças em bytes crus, todos em zero: a base do efeito feito à mão.",
}

SEM_APARELHO_AQUI = "Nenhum controle neste lugar."

PREFIXO_DA_DICA_DO_MODO = "dica-modo-"


def descricao_do_modo(chave: str) -> str:
    """A explicação do modo, na frase desta tela — vazio nunca.

    A QUEDA É A DESCRIÇÃO DO PRODUTO, e não o silêncio: um modo que o produto
    ganhe e que esta tela ainda não tenha frase para continua tendo o
    `spec.description`, que é a frase da GTK. Entre a frase concreta, a genérica
    e nenhuma, a ordem é essa — e o gerador reprova alto no dia em que a
    primeira faltar, para que a segunda não vire o padrão calado.
    """
    daqui = DICA_DO_MODO.get(chave)
    if daqui:
        return daqui
    specs = _specs()
    spec = specs.get_spec(chave) if specs else None
    return str(getattr(spec, "description", "") or "")


#: O QUE A TELA CHAMA O «DESLIGADO» DO GATILHO — 03/10/2026, decisão de produto: os controles
#: obedecem quando o jogo manda e, na ausência disso, o perfil ganha.
#: A chave segue sendo `Off` (o perfil não muda de forma, e o
#: `trigger.reset` do gesto é o mesmo): o que muda é o NOME, que diz o que o
#: gesto faz. O dono do rótulo do produto (`trigger_specs`, «Desligado») não
#: muda: a CLI e o daemon seguem falando dele.
#:
#: 06/10/2026: o rótulo da chave `Off` é «Sem efeito» (o jogo que comanda
#: vence nos dois modos; o rótulo diz o que o Hefesto faz, não quem decide). O
#: NOME da constante ficou, porque os testes e o desenho a leem por ele.
ROTULO_DO_JOGO_DECIDE = "Sem efeito"

#: O gesto do par «Modo automático | Modo personalizado» (o mesmo `GESTO_DO_MODO` do desenho).
GESTO_DO_MODO = "modo-dos-gatilhos"


def _rotulo_do_modo(chave: str) -> str:
    """O rótulo de tela de um modo (`Rigid` → `Rígido`), ou a chave crua."""
    if chave == "Off":
        return ROTULO_DO_JOGO_DECIDE
    specs = _specs()
    spec = specs.get_spec(chave) if specs else None
    return str(getattr(spec, "label", "") or chave)


# * TROCA DE PERFIL — o daemon REAPLICA o perfil no `profile.switch`, então o
_PERFIL_DO_RASCUNHO: str = ""
_RASCUNHO: dict[tuple[str, str], dict[str, Any]] = {}


def _chave_do_rascunho(uniq: str, disco: str) -> tuple[str, str]:
    """O endereço de uma metade do rascunho: `uniq` NORMALIZADO e o lado.

    O `uniq` do clique vem da mesa (`d4:2f:…`) e o do perfil vem do disco
    (`d42f…`). Normalizar aqui é o que impede o mesmo controle de ter duas
    entradas — a mesma razão que `_com_os_gatilhos` já escreve.
    """
    return (uniq.replace(":", "").lower(), disco)


def esquecer_o_rascunho() -> None:
    """Joga fora o que esta sessão lembrava de ter aplicado."""
    _RASCUNHO.clear()


def _o_rascunho_e_deste_perfil(perfil: str) -> None:
    """Poda o rascunho quando o perfil ativo mudou. Ver a nota da seção."""
    global _PERFIL_DO_RASCUNHO
    if perfil != _PERFIL_DO_RASCUNHO:
        _PERFIL_DO_RASCUNHO = perfil
        esquecer_o_rascunho()


def _o_rascunho_e_de_quem_esta_na_mesa(uniqs: set[str]) -> None:
    """Poda o rascunho dos controles que saíram. Ver a nota da seção."""
    for chave in [k for k in _RASCUNHO if k[0] not in uniqs]:
        _RASCUNHO.pop(chave, None)


def _lembrar_o_aplicado(perfil: str, uniq: str, disco: str,
                        cfg: dict[str, Any]) -> None:
    """Grava no rascunho o que acabou de ir para o aparelho."""
    _o_rascunho_e_deste_perfil(perfil)
    _RASCUNHO[_chave_do_rascunho(uniq, disco)] = {
        "mode": str(cfg.get("mode") or "Off"),
        "params": [int(v) for v in (cfg.get("params") or [])],
    }


def _do_rascunho(uniq: str, disco: str) -> dict[str, Any] | None:
    """O que esta sessão aplicou naquele gatilho, ou `None` se não aplicou nada."""
    return _RASCUNHO.get(_chave_do_rascunho(uniq, disco))


def _chave_no_perfil(uniq: str) -> str:
    """O `uniq` na grafia do mapa `controllers` — doze hexa, ou `""`."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(str(uniq or "").strip()) or ""


def _o_lado_que_o_perfil_cala(disco: str) -> dict[str, Any]:
    """O gatilho com que o esquema preenche o lado que o perfil não escreve."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.profiles.schema import TriggersConfig

        lado = getattr(TriggersConfig(), disco)
        return {"mode": str(lado.mode), "params": list(lado.params)}
    except Exception:
        return {}


def _modo_do_lado(lado: Any) -> str:
    """A chave do modo de um lado do perfil CRU; sem nada escrito vale o de nascimento.

    É o que o modelo faz (`TriggersConfig` nasce com `MODO_DE_NASCIMENTO_DO_GATILHO`): a tela e
    o aparelho leem o mesmo perfil e têm de dizer o mesmo modo.
    """
    from hefesto_dualsense4unix.profiles.schema import MODO_DE_NASCIMENTO_DO_GATILHO

    if isinstance(lado, dict) and lado:
        return str(lado.get("mode") or MODO_DE_NASCIMENTO_DO_GATILHO)
    return MODO_DE_NASCIMENTO_DO_GATILHO


def _todos_os_gatilhos_sem_efeito(p: dict[str, Any]) -> bool:
    """Os dois lados globais e todo lado escrito de cada controle são «Sem efeito»?"""
    from hefesto_dualsense4unix.profiles.schema import MODO_SEM_EFEITO_DO_GATILHO

    globais = p.get("triggers")
    lados: list[Any] = [
        globais.get(disco) if isinstance(globais, dict) else None for disco in LADOS.values()]
    controles = p.get("controllers")
    for dele in (controles.values() if isinstance(controles, dict) else ()):
        seus = dele.get("triggers") if isinstance(dele, dict) else None
        if isinstance(seus, dict):
            lados.extend(seus.get(disco) for disco in LADOS.values()
                         if isinstance(seus.get(disco), dict) and seus.get(disco))
    return all(_modo_do_lado(lado) == MODO_SEM_EFEITO_DO_GATILHO for lado in lados)


def modo_dos_gatilhos_do_perfil(p: dict[str, Any] | None) -> str:
    """O modo da aba (Automático ou Personalizado), lido do perfil CRU.

    A regra é a do esquema (`decidir_o_modo_dos_gatilhos`), a mesma que o `ProfileManager`
    usa para decidir o que vai ao aparelho. Sem perfil, o Personalizado.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        MODO_PERSONALIZADO,
        decidir_o_modo_dos_gatilhos,
    )

    if not isinstance(p, dict) or not p:
        return MODO_PERSONALIZADO
    globais = p.get("triggers")
    escrito = globais.get("modo") if isinstance(globais, dict) else None
    return decidir_o_modo_dos_gatilhos(
        escrito if isinstance(escrito, str) else None, _todos_os_gatilhos_sem_efeito(p))


def _o_modo_escrito_e_automatico(p: dict[str, Any] | None) -> bool:
    """O perfil traz o modo automático ESCRITO em `triggers.modo` (e não deduzido)?"""
    globais = p.get("triggers") if isinstance(p, dict) else None
    return isinstance(globais, dict) and globais.get("modo") == MODO_AUTOMATICO


RECADO_DO_AUTOMATICO_PARADO = (
    "Os gatilhos estão no modo automático: o jogo comanda, e o estilo do perfil ajusta. "
    "Passe para o modo personalizado para escolher.")


def _nao_no_automatico(ctx: Contexto) -> None:
    """A guarda de cada gesto que escolhe um efeito: recusa com o Automático ESCRITO.

    A tela já deixa as colunas paradas (a folha da aba), então o clique não chega; esta é a
    porta de quem fala com o gesto sem a tela. O perfil de antes, sem `triggers.modo`, segue
    aceitando o que sempre aceitou.
    """
    nome = perfil.nome_do_ativo(ctx.state).strip()
    if nome and _o_modo_escrito_e_automatico(perfil.ativo_que_vale(nome)):
        raise RuntimeError(RECADO_DO_AUTOMATICO_PARADO)


def _o_que_o_controle_recebe(p: dict[str, Any] | None, uniq: str,
                             disco: str) -> dict[str, Any]:
    """O gatilho que aquele controle RECEBE daquele lado — `{"mode", "params"}`.

    No modo automático ESCRITO a tela mostra «Sem efeito» nos dois lados de cada controle,
    antes de olhar o rascunho: o aparelho recebe `Off` (a vista do `ProfileManager`), e as
    escolhas guardadas ficam no disco para o Personalizado devolver.
    """
    if _o_modo_escrito_e_automatico(p):
        return {"mode": "Off", "params": []}
    seu = _do_rascunho(uniq, disco)
    if seu:
        return seu
    if not p:
        return {}
    alvo = _chave_no_perfil(uniq)
    controles = p.get("controllers")
    for chave, dele in (controles.items() if isinstance(controles, dict) else ()):
        if not alvo or _chave_no_perfil(str(chave)) != alvo or not isinstance(dele, dict):
            continue
        seus = dele.get("triggers")
        escrito = seus.get(disco) if isinstance(seus, dict) else None
        if isinstance(escrito, dict) and escrito:
            return escrito
    globais = p.get("triggers")
    escrito = globais.get(disco) if isinstance(globais, dict) else None
    if isinstance(escrito, dict) and escrito:
        return escrito
    return _o_lado_que_o_perfil_cala(disco)


def meus_efeitos() -> dict[str, Any]:
    """Os efeitos dos gatilhos que ela guardou. O dono da biblioteca é `meus_efeitos.py`."""
    return _meus_efeitos_da("gatilhos")


def _meia_do_efeito(efeito: Any, disco: str) -> dict[str, Any] | None:
    """A metade `left`/`right` de um efeito salvo, ou `None` se ele não a tem."""
    if not isinstance(efeito, dict):
        return None
    meia = efeito.get(disco)
    if not isinstance(meia, dict) or not meia.get("mode"):
        return None
    return meia


def _meu_efeito_que_casa(disco: str, cfg: dict[str, Any]) -> str:
    """O nome do efeito salvo que É esta configuração, ou `""`."""
    modo_agora = str((cfg or {}).get("mode") or "Off")
    params_agora = list((cfg or {}).get("params") or [])
    for nome, efeito in meus_efeitos().items():
        meia = _meia_do_efeito(efeito, disco)
        if meia is None:
            continue
        if str(meia.get("mode")) == modo_agora and list(meia.get("params") or []) == params_agora:
            return nome
    return ""


def _na_lista_da_tela(modo: str, params: list[int], specs: Any) -> tuple[str, list[int]]:
    """O gatilho do perfil como a lista de onze o mostra (`Rigid` abre como Resistência)."""
    if specs is None:
        return modo, params
    nome, ajustes = specs.na_lista_de_onze(modo, params)
    return str(nome), [int(v) for v in ajustes]


def _do_lado(cfg: dict[str, Any], specs: Any) -> dict[str, Any]:
    """Um lado do gatilho, do perfil para a tela: o rótulo do modo, a chave dele e os ajustes.

    Perfil antigo abre com o acionamento certo selecionado: a chave que saiu da lista de onze
    (`Rigid`, `AutoGun`…) aparece pela linha nova, com os ajustes já postos na ordem da linha nova.
    """
    nome, params = _na_lista_da_tela(
        str((cfg or {}).get("mode") or "Off"), _params_inteiros(cfg or {}), specs)
    spec = specs.get_spec(nome) if specs else None
    return {"modo": spec.label if spec else nome, "modo-chave": nome, "params": params,
            "cru": (str((cfg or {}).get("mode") or "Off"), _params_inteiros(cfg or {}))}


#: é o rótulo, e é só ele que `html_das_opcoes_de_modo` troca. Tudo o mais da
_OPCAO = re.compile(
    r'(?P<cabeca><option value="(?P<valor>[^"]*)"[^>]*>)(?P<texto>[^<]*)</option>')

_OPCOES_DO_MODO: str | None = None


def _opcoes_cravadas_do_modo() -> str:
    """As opções do campo "Modo" que a página publicada traz, como o DOM as escreve."""
    global _OPCOES_DO_MODO
    if _OPCOES_DO_MODO is None:
        dentro = ""
        for m in _SELECT.finditer(_pagina_publicada()):
            if _CAMPO_DA_CLASSE[m.group("classe")] == "modo":
                dentro = m.group("dentro")
                break
        _OPCOES_DO_MODO = _COMO_O_DOM_ESCREVE.sub(
            r' \1=""', dentro.split("<optgroup", 1)[0].replace(" selected", "")).rstrip()
    return _OPCOES_DO_MODO


def html_das_opcoes_de_modo(disco: str = "") -> str:
    """As opções do «Efeito de acionamento», com o RÓTULO perguntado ao dono.

    No fim vai o grupo «Seus efeitos» daquele gatilho (`disco`): os que a pessoa guardou com
    uma metade para ele.
    """
    return _rotuladas(_opcoes_cravadas_do_modo()) + _seus_do_acionamento(disco)


def _rotuladas(cravadas: str) -> str:
    """As opções cravadas do desenho, com a palavra de produto no lugar da digitada.

    Só as onze de `trigger_specs.PRESETS` passam: o que o desenho publicado ainda traga de fora
    da lista (as chaves que se fundiram) cai aqui, e a tela mostra a lista nova sem esperar o
    `--publicar`.
    """
    specs = _specs()
    if specs is None:
        return cravadas
    do_produto = {p.name: _rotulo_do_modo(p.name) for p in specs.PRESETS}

    def rotular(m: re.Match[str]) -> str:
        if m.group("valor") == TRAVESSAO:
            # O `—` é do lugar vazio, não da lista que se abre — também numa
            # página publicada antes de o desenho o esconder.
            if "hidden" in m.group("cabeca"):
                return m.group(0)
            return m.group(0).replace(">", ' hidden="">', 1)
        rot = do_produto.get(m.group("valor"))
        if rot is None:
            # Uma opção que a lista de onze não tem (a página publicada de antes da fusão
            # ainda oferece as dezenove) não vai para a tela.
            return ""
        return f'{m.group("cabeca")}{_escapar(rot)}</option>'

    return _OPCAO.sub(rotular, cravadas)


#: o grupo das listas de efeito que leva o que a pessoa criou
SEUS_EFEITOS = "Seus efeitos"

#: a opção que desfaz a imersão e deixa só o efeito de acionamento
SEM_IMERSAO = "nenhum"
ROTULO_DO_SEM_IMERSAO = "Sem efeito"


def _imersoes() -> Any:
    """Os efeitos de imersão do produto (`profiles/efeitos_de_imersao.py`), ou `None`."""
    return _modulo_do_src("profiles.efeitos_de_imersao")


def _estilo_do_perfil(p: dict[str, Any] | None) -> str:
    """A chave do estilo de jogo que o perfil ativo escolheu, ou `""`."""
    return str((p or {}).get("estilo") or "")


def _rotulo_do_estilo(chave: str) -> str:
    """O nome do estilo na tela, ou `""` quando o perfil não tem estilo."""
    if not chave:
        return ""
    estilos = _modulo_do_src("profiles.estilos_de_jogo")
    estilo = estilos.POR_CHAVE.get(chave) if estilos else None
    return estilo.rotulo if estilo else ""


def _grupo_dos_seus(nomes: list[str]) -> str:
    """O `<optgroup>` «Seus efeitos» com um item por nome, ou nada se não há nenhum."""
    if not nomes:
        return ""
    itens = "".join(
        f'<option value="{_escapar(PREFIXO_DO_MEU + n)}">{_escapar(n)}</option>'
        for n in nomes)
    return f'<optgroup label="{SEUS_EFEITOS}">{itens}</optgroup>'


def _seus_do_acionamento(disco: str) -> str:
    """O grupo «Seus efeitos» do acionamento daquele gatilho."""
    if not disco:
        return ""
    return _grupo_dos_seus([n for n, e in meus_efeitos().items()
                            if _meia_do_efeito(e, disco) is not None])


def _params_da_imersao(imersao: Any, modo: str, estilo: str) -> list[int] | None:
    """Os ajustes dela, postos na ordem do modo; `None` se ela não vale nesse modo."""
    imer, specs = _imersoes(), _specs()
    spec = specs.get_spec(modo) if specs else None
    if imer is None or spec is None:
        return None
    ajustes = imer.ajustes_da_imersao(imersao, modo, estilo)
    if ajustes is None:
        return None
    return [int(v) for v in specs.preset_to_positional_params(spec, ajustes)]


def _metade_da_imersao_criada(item: Any) -> dict[str, Any] | None:
    """`{"mode", "params"}` de uma imersão que a pessoa criou, ou `None` se o item não lê."""
    specs = _specs()
    if specs is None or not isinstance(item, dict):
        return None
    base, nomeados = str(item.get("base") or ""), item.get("parametros")
    spec = specs.get_spec(base)
    if spec is None or not isinstance(nomeados, dict):
        return None
    valores = {str(k): int(v) for k, v in nomeados.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {"mode": base,
            "params": [int(v) for v in specs.preset_to_positional_params(spec, valores)]}


#: o endereço da imersão na coluna, o do estilo no canto, e a dica dela
CAMPO_DA_IMERSAO = "imersao"

PREFIXO_DA_DICA_DA_IMERSAO = "dica-imersao-"

#: a etiqueta da família («Golpe», «Carga»…) à esquerda da caixa do efeito do gatilho (20/10/2026)
PREFIXO_DA_FAMILIA_DA_IMERSAO = "familia-imersao-"
#: a frase de quem não tem efeito: o gatilho livre, de fábrica
DICA_DO_SEM_IMERSAO = "O gatilho livre, de fábrica."

CAMPO_DO_ESTILO = "estilo-do-perfil"

#: onde pousam os chips do que a pessoa criou, na área «Criar efeitos novos»
SELETOR_DOS_SEUS = "#criar-gatilhos .meus"


def _params_inteiros(cfg: dict[str, Any]) -> list[int]:
    """Os ajustes de um lado como inteiros, ou `[]` quando algum não é número simples."""
    fora: list[int] = []
    for v in (cfg or {}).get("params") or []:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return []
        fora.append(int(v))
    return fora


def dica_da_imersao(chave: str) -> str:
    """A dica da caixa do efeito do gatilho: «Nome. frase». A frase mora SÓ aqui e no `title`.

    A das criadas e a do «Sem efeito» são fixas. O nome leva a família («Golpe · imersivo»), que
    a caixa também mostra como etiqueta.
    """
    imer = _imersoes()
    feita = imer.POR_CHAVE.get(chave) if imer else None
    if feita is not None:
        return f"{feita.rotulo}. {feita.dica}"
    if chave.startswith(PREFIXO_DO_MEU):
        return "Um efeito que você criou"
    if chave == SEM_IMERSAO:
        return f"{ROTULO_DO_SEM_IMERSAO}. {DICA_DO_SEM_IMERSAO}"
    return "O que o gatilho faz no jogo"


def familia_da_imersao(chave: str) -> str:
    """A etiqueta de família da caixa («Golpe»); vazio no «Sem efeito», nos criados e no vazio."""
    imer = _imersoes()
    feita = imer.POR_CHAVE.get(chave) if imer else None
    return str(imer.familia_da_pagina(feita)) if imer and feita is not None else ""


def html_dos_seus_efeitos() -> str:
    """Os chips do que a pessoa criou: bolinha roxa o acionamento, rosa a imersão."""
    def chip(nome: str, cor: str, quem: str) -> str:
        return (f'<span class="meu" data-dica="{quem}"><i style="--cor:var({cor})"></i>'
                f"{_escapar(nome)}</span>")

    return "".join(
        [chip(n, "--purple", "Efeito de acionamento") for n in meus_efeitos()]
        + [chip(n, "--pink", "Efeito de imersão") for n in _meus_efeitos_da("imersao")])


def _imersao_que_casa(
    modo: str, params: list[int], cru: tuple[str, list[int]] | None = None,
) -> str:
    """A imersão cujos números SÃO estes (`meu:<nome>` se é uma criada).

    `cru` é o gatilho como o perfil o guarda quando a chave dele saiu da lista de onze
    (`Rigid`…): a imersão salva com os números de lá segue valendo, e o campo a mostra.

    `nenhum` quando são os padrões do modo; vazio (o campo fica em branco) quando o perfil
    guarda números próprios que nenhuma da lista conhece: dizer «Nenhum» seria mentir.
    """
    for nome, item in _meus_efeitos_da("imersao").items():
        meia = _metade_da_imersao_criada(item)
        if meia and meia["mode"] == modo and meia["params"] == params:
            return f"{PREFIXO_DO_MEU}{nome}"
    imer, specs = _imersoes(), _specs()
    spec = specs.get_spec(modo) if specs else None
    if imer is None or spec is None:
        return SEM_IMERSAO
    # A regra é uma só, a do motor do tato que toca os momentos (`imersao_dos_numeros`).
    achada = imer.imersao_dos_numeros(modo, params)
    if achada is None and cru is not None and cru[0] != modo:
        achada = imer.imersao_dos_numeros(cru[0], cru[1])
        if achada is not None and modo not in imer.FAMILIAS.get(achada[0].familia, ()):
            achada = None
    if achada is not None:
        return str(imer.IGUAL_A.get(achada[0].chave, achada[0].chave))
    if not params or params == _padroes(modo):
        return SEM_IMERSAO
    if cru is not None and not cru[1]:
        return SEM_IMERSAO  # sem ajuste nenhum no perfil antigo: nada que o campo afirme
    return ""


def _com_maiuscula(texto: str) -> str:
    """A primeira letra maiúscula, sem mexer no resto («rajada que sobe» vira «Rajada que sobe»)."""
    return texto[:1].upper() + texto[1:]


def html_das_opcoes_de_imersao(estilo: str = "") -> str:
    """As opções do «Efeito do gatilho»: Sem efeito, um grupo por família e «Seus efeitos».

    O texto da opção é a variante («Rajada que sobe») e o grupo é a família («Golpe»); o nome
    inteiro («Golpe · rajada que sobe») está na dica da caixa. A frase de cada efeito mora SÓ
    no `title` da opção. Com um estilo no perfil, os efeitos dele vão na frente do grupo. O `—` é
    o do lugar sem controle, escondido da lista que se abre.
    """
    partes = [f'<option value="{TRAVESSAO}" disabled="" hidden="">{TRAVESSAO}</option>',
              f'<option value="{SEM_IMERSAO}" title="{_escapar(DICA_DO_SEM_IMERSAO)}">'
              f"{ROTULO_DO_SEM_IMERSAO}</option>"]
    imer = _imersoes()
    for familia, delas in (imer.imersoes_por_familia(estilo) if imer else ()):
        itens = "".join(
            f'<option value="{_escapar(i.chave)}" title="{_escapar(i.dica)}">'
            f"{_escapar(_com_maiuscula(imer.variante_da_pagina(i)))}</option>" for i in delas)
        partes.append(f'<optgroup label="{_escapar(familia)}">{itens}</optgroup>')
    partes.append(_grupo_dos_seus(list(_meus_efeitos_da("imersao"))))
    return "".join(partes)


# emite o chip sem `--plastico`. Esta aba continua não dependendo disso: ela lê

CLASSE_DO_CHIP = "cabeca"

#: * logo o `--plastico` ficava num elemento cujo alvo era `texto`, e
CAMPO_DO_CHIP = "chip-do-controle"

#: O ALVO É `plastico`, e ele é o único que escreve `--plastico`: os outros
#: `.chip.plastico{border-color:var(--plastico, var(--border-forte))}` e a queda
CAMPO_DO_PLASTICO = "plastico"

ALVO_DO_PLASTICO = "plastico"

PONTO = ' <span class="pt">•</span> '


def cor_de_borda(tinta: str) -> str:
    """A tinta da zona quando ela É cor, e `""` quando o mapa não tem hex.

    O QUE O MAPA DO USUÁRIO RESPONDE, e são TRÊS formas — `gerar_cores_do_dualsense.
    _tinta` é quem as escreve, a partir de `docs/data/cores-do-dualsense.csv`:

        `#rrggbb`                 o hexadecimal daquela zona
        `url(#casca-<modelo>)`    a casca partida em duas, num gradiente
        `url(#hachura-sem-hex)`   a AUSÊNCIA DECLARADA — *"o acabamento não cabe
                                  num hexadecimal (iridescente, metálico,
                                  camuflado, arte)"*

    Só a primeira é uma cor. E a terceira não é caso raro: **OITO dos vinte e
    oito modelos** respondem hachura na `casca-solida`, que é justamente a zona
    do chip — Grey Camouflage, Chroma Teal, Chroma Indigo, Chroma Pearl, Ghost
    of Yōtei, Marathon, Genshin Impact e 007 First Light.

    MEDIDO NO WEBKIT DESTA MÁQUINA, 03/09/2026, com a regra que o `topo.html`
    declara (`.chip.plastico{border-color:var(--plastico, var(--border-forte))}`)::

        --plastico:#ae335a                → rgb(174, 51, 90)   a cor do plástico
        --plastico ausente                → rgb(98, 114, 164)  a QUEDA declarada
        --plastico:url(#hachura-sem-hex)  → rgb(139, 233, 253) a cor do TEXTO

    A terceira linha é o defeito, e ele é do CSS e não do desenho: uma `var()`
    que resolve para algo que a propriedade não aceita fica **inválida no tempo
    de valor computado**, e nesse caso o navegador NÃO usa a queda escrita ao
    lado — ele volta ao valor herdado, que numa `border-color` é o
    `currentColor`. O chip vestia a cor da LETRA e a dica ao lado dizia, com
    todas as letras, que aquela era a cor do plástico daquele aparelho.

    A REGRA É A DO USUÁRIO: *sem cor lida, sem cor na tela.* Sem `--plastico` a queda
    do `topo.html` vale, a borda fica neutra, e a dica diz por quê.

    O TESTE DO `#` NÃO É NOVO: é o mesmo que `gerar_cores_do_dualsense.legivel`
    já usa, pela mesma razão — *"gradiente, hachura: não são cor"*. Não há
    tabela de cor aqui; quem sabe a cor continua sendo o CSV dela.
    """
    tinta = (tinta or "").strip()
    return tinta if tinta.startswith("#") else ""


def miolo_do_chip(jogador: int, nome: str, via: str,
                  conectado: bool = True) -> str:
    """O texto do chip: `P1 • White • USB`, e cada pedaço só entra se existir."""
    if not conectado:
        return f"P{jogador}{PONTO}Desconectado"
    pedacos = [f"P{jogador}"]
    if nome:
        pedacos.append(nome)
    if via:
        pedacos.append(via)
    return PONTO.join(pedacos)


def chip_do_controle(jogador: int, nome: str, via: str, plastico: str,
                     conectado: bool = True) -> str:
    """O `<span>` do cabeçalho da coluna, com endereço e sem cor inventada.

    `plastico` é o HEX JÁ RESOLVIDO, e não o *slug*, de propósito: o gerador
    resolve por `monta.cor_da_zona`, que **levanta** num colorway que o desenho
    não tem (é portão, e está certo em levantar); o pacote resolve por
    `_cor_do_plastico`, que devolve `""` — derrubar a pintura da aba por causa
    de um modelo novo seria trocar uma borda que falta por uma tela congelada.
    A política de resolução é de quem chama; a MARCAÇÃO é daqui, e é ela que não
    pode divergir.

    A COR NÃO SAI DAQUI NO DESENHO — 03/09/2026, e é a mudança desta frente. O
    `--plastico` subiu para o EMBRULHO (:func:`_cabeca_do_controle`), que tem
    endereço e alvo próprios; este `<span>` é o miolo que o alvo `html` refaz.
    O parâmetro `plastico` fica porque é ele que decide A DICA, e a dica tem de
    saber separar as duas ausências. Quem julga o que é hex é
    :func:`cor_de_borda`, que recusa o que o mapa dela responde quando não há
    hex. A borda não some: `topo.html` declara
    `.chip.plastico{border-color:var(--plastico, var(--border-forte))}`, com a
    queda já escrita.

    **E A DICA ACOMPANHA A COR — 03/09/2026.** Ela dizia *"a borda é a cor do
    plástico"* nos TRÊS casos, e nos dois últimos era mentira: sem hex a borda é
    a neutra do tema, não o plástico de ninguém. São duas ausências diferentes, e
    a tela tem de saber dizer qual é qual — porque uma se conserta lendo o
    aparelho e a outra não se conserta:

        o mapa RESPONDEU e não é cor  o acabamento não cabe num hexadecimal
                                      (:func:`cor_de_borda`, oito dos 28 modelos)
        ninguém leu a cor             pelo rádio ela pode não chegar nunca, hoje

    É a metade que faltava da regra de produto: *sem cor lida, sem cor na tela* — e,
    quando não há, dizer POR QUE não há.

    **A SEGUNDA AUSÊNCIA PAROU DE SE EXPLICAR — FRASES-E-DICAS-02, 13/09/2026.**
    A dica de quem ninguém leu confessava que a cor ainda não tinha sido lida:
    confissão sobre um estado nosso numa dica flutuante, e a ordem de 13/09
    a tira da tela. Ela diz só o nome — e, sem nome, o `<span>` não tem dica.
    A do acabamento fica: ela diz o que o modelo É, não o que nós não fizemos.
    """
    cor = cor_de_borda(plastico)
    classe = "chip plastico" if conectado else "chip vazio"
    if not conectado:
        dica = SEM_APARELHO_AQUI
    elif cor:
        dica = (f"{nome} — a borda é a cor do plástico" if nome
                else "A borda é a cor do plástico deste controle.")
    elif plastico:
        dica = (f"{nome} — o acabamento deste modelo não cabe num hexadecimal, "
                f"e a borda fica neutra" if nome else
                "O acabamento deste modelo não cabe num hexadecimal, e a borda "
                "fica neutra.")
    else:
        dica = nome
    titulo = f' title="{dica}"' if dica else ""
    return (f'<span class="{classe}"{titulo}>'
            f"{miolo_do_chip(jogador, nome, via, conectado)}</span>")


def _cabeca_do_controle(jogador: int, nome: str, via: str, plastico: str,
                        conectado: bool = True) -> str:
    """O cabeçalho INTEIRO da coluna: o embrulho que veste a cor e o miolo.

    ELE É PRIVADO, e o nome diz um fato: **só o gerador monta este elemento**. O
    produto escreve nos dois endereços que ele deixa; nunca refaz a `.cabeca`.
    Público, ele seria uma promessa ao produto sem chamador em produção — e o
    `portao_a_casa_sabe_e_o_produto_nao_faz` acusa isso, com razão: os dez
    `interface/abaNN.py` são BANCADA e saem da conta pela poda dele.

    MORA AQUI E NÃO NO GERADOR porque a MARCAÇÃO tem um dono só. Se o desenho a
    escrevesse por conta própria, a estrutura que ele emite e a que
    :func:`seletor_do_chip` procura divergiriam no primeiro dia em que alguém
    mexesse numa só — e o produto passaria a escrever no lugar errado, calado.

    DOIS ELEMENTOS, DOIS ENDEREÇOS, e a divisão é o ponto:

        .cabeca   `data-campo="plastico"`  alvo `plastico`  → a COR do aparelho
          span    `data-campo="chip-do-controle"` alvo `html` → o CHIP inteiro

    Só o gerador emite esta função — o produto escreve nos dois endereços que
    ela deixa. Aninhá-los é o que permite as duas escritas conviverem: o selo do
    embrulho fica FORA do `innerHTML` que o miolo compara, e o selo do miolo fica
    no elemento que o escreve. Com a cor dentro do miolo (como era até hoje) uma
    das duas tinha de ser sacrificada, e a sacrificada era a cor.

    O EMBRULHO TEM ENDEREÇO NAS QUATRO COLUNAS, inclusive nas vazias, e isso é
    deliberado: a página é estática e o piloto não cria endereço. Sem ele, o dia
    em que um controle entra no P3 a coluna mostra o nome do plástico e uma borda
    neutra — a cor não teria por onde chegar. Onde não há leitura o produto
    escreve o vazio, que APAGA a variável.
    """
    cor = cor_de_borda(plastico) if conectado else ""
    estilo = f' style="--plastico:{cor}"' if cor else ""
    return (f'<div class="{CLASSE_DO_CHIP}" data-campo="{CAMPO_DO_PLASTICO}"'
            f' data-hef-alvo="{ALVO_DO_PLASTICO}"{estilo}>'
            f'<span data-campo="{CAMPO_DO_CHIP}" data-hef-alvo="html">'
            f"{chip_do_controle(jogador, nome, via, plastico, conectado)}"
            f"</span></div>")


def _cor_do_plastico(slug: str) -> str:
    """A TINTA da casca daquele modelo, como o mapa dela a escreve — ou `""`."""
    if not slug:
        return ""
    try:
        import monta

        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        return str(monta.cor_de_css(slug))
    except (Exception, SystemExit):
        return ""


def _casa_na_mesa(ctx: Contexto, uniq: str) -> dict[str, Any]:
    """A entrada da MESA daquele controle — a mesma que a FITA DO TOPO desenha."""
    for m in ctx.mesa:
        if str(m.get("uniq") or "") == uniq:
            return m
    return {}


def seletor_do_chip(pref: str) -> str:
    """O endereço de bloco do cabeçalho daquela coluna."""
    return f'[data-controle="{pref}"] [data-campo="{CAMPO_DO_CHIP}"]'


def _numero_da_posicao(pref: str) -> int:
    """`p3` → 3. O número do lugar VAZIO, que é posição e não identidade."""
    digitos = "".join(ch for ch in pref if ch.isdigit())
    return int(digitos) if digitos else 0


def _identidade_viva(ctx: Contexto, c: dict[str, Any]) -> tuple[int, str, str, str]:
    """`(jogador, nome, via, plástico)` de um controle que está na mesa AGORA."""
    from . import VIA_DO_TRANSPORTE, identidade_de

    casa = _casa_na_mesa(ctx, str(c.get("uniq") or ""))
    via = str(casa.get("via")
              or VIA_DO_TRANSPORTE.get(str(c.get("transport") or "").lower(), ""))
    # `identidade_de` É O DONO DO NOME NA TELA, e ele já sabe que `"Não sei"`
    # o transporte já tem lugar próprio, então a queda vira ausência.
    nome = identidade_de(c, ctx.mesa)
    if nome in ("—", via):
        nome = ""
    jogador = casa.get("jogador")
    if not isinstance(jogador, int) or isinstance(jogador, bool):
        jogador = _numero_da_posicao(str(casa.get("pref") or ""))
    return jogador, nome, via, _cor_do_plastico(str(casa.get("cor") or ""))


def _cabecalho_vivo(ctx: Contexto, c: dict[str, Any]) -> tuple[str, str]:
    """`(chip, cor)` de um controle que está na mesa AGORA — de UMA leitura.

    Os dois valores vão para endereços diferentes (o miolo pelo alvo `html`, a
    cor pelo alvo `plastico`) e por isso saem juntos daqui: lidos em duas
    chamadas, `_identidade_viva` podia responder duas mesas no mesmo tique — e a
    coluna vestiria a borda de um controle com o nome de outro, que é a família
    de defeito desta frente.

    A COR VAI PENEIRADA por :func:`cor_de_borda`, e não crua: em oito dos 28
    modelos o mapa dela responde a hachura do SEM-HEX, que não é cor. Escrevê-la
    em `--plastico` deixa a `var()` inválida no tempo de valor computado, e a
    borda vira o `currentColor` — o chip vestindo a cor da LETRA com a dica ao
    lado dizendo que aquela é a cor do plástico. Vazio APAGA a variável, e a
    queda do `topo.html` assume.
    """
    identidade = _identidade_viva(ctx, c)
    chip = chip_do_controle(*identidade)
    return chip, cor_de_borda(identidade[3])


def _chip_do_lugar_vazio(pref: str) -> str:
    """O chip de um lugar sem aparelho: a posição e o estado, e mais nada."""
    return chip_do_controle(_numero_da_posicao(pref), "", "", "", conectado=False)


@registrar("03-gatilhos.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Endereço → valor, por controle da mesa. E as listas de acionamento e imersão, em bloco."""
    specs = _specs()
    p = perfil.ativo(ctx.state.get("active_profile"))
    # a intensidade se lê com o computador por baixo: sem jogo, é lá que o trilho grava
    vale = perfil.ativo_que_vale(ctx.state.get("active_profile"))
    tem_endereco = _enderecos_da_pagina()

    _o_rascunho_e_deste_perfil(perfil.nome_do_ativo(ctx.state))
    _o_rascunho_e_de_quem_esta_na_mesa(
        {_chave_do_rascunho(str(c.get("uniq") or ""), "")[0] for c in ctx.conectados})

    pref_de = {str(m.get("uniq") or ""): str(m.get("pref") or "") for m in ctx.mesa}
    estilo = _estilo_do_perfil(p)

    colunas: dict[str, dict[str, Any]] = {}
    blocos: dict[str, str] = {}
    pintados = 0
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        entradas = c.get("inputs") or {}
        l2, r2 = entradas.get("l2_raw"), entradas.get("r2_raw")

        cfgs = {sig: _o_que_o_controle_recebe(p, uniq, disco)
                for sig, disco in LADOS.items()}
        deste = {sig: _do_lado(cfgs[sig], specs) for sig in LADOS}

        chip, plastico = _cabecalho_vivo(ctx, c)
        col: dict[str, object] = {
            CAMPO_DO_CHIP: chip,
            CAMPO_DO_PLASTICO: plastico,
            "l2-raw": l2, "r2-raw": r2,
            "l2-pct": round((l2 or 0) / 255 * 100),
            "r2-pct": round((r2 or 0) / 255 * 100),
            CAMPO_DA_FORCA["l2"]: nivel_da_forca(l2),
            CAMPO_DA_FORCA["r2"]: nivel_da_forca(r2), **_intensidade_da_coluna(vale, uniq),
        }
        for sig, d in deste.items():
            col[f"modo-{sig}"] = d["modo"]
            col[f"modo-chave-{sig}"] = d["modo-chave"]
            col[f"{PREFIXO_DA_DICA_DO_MODO}{sig}"] = descricao_do_modo(
                str(d["modo-chave"]))
            meu_nome = _meu_efeito_que_casa(LADOS[sig], cfgs[sig])
            if meu_nome:
                col[f"modo-chave-{sig}"] = f"{PREFIXO_DO_MEU}{meu_nome}"
            feita = _imersao_que_casa(
                str(d["modo-chave"]), list(d["params"]), d["cru"])
            if feita == SEM_IMERSAO and str(d["modo-chave"]) not in ("Off", ""):
                # um acionamento sem efeito de família não é «Sem efeito»: o gatilho resiste, e
                # quem o diz é a linha «Como o gatilho faz», atrás do Avançado
                feita = ""
            col[f"{CAMPO_DA_IMERSAO}-{sig}"] = feita
            col[f"{PREFIXO_DA_DICA_DA_IMERSAO}{sig}"] = dica_da_imersao(feita)
            col[f"{PREFIXO_DA_FAMILIA_DA_IMERSAO}{sig}"] = familia_da_imersao(feita)
        colunas[uniq] = col
        pintados += sum(1 for k in col if k in tem_endereco)
        blocos.update(_blocos_da_coluna(pref_de.get(uniq) or uniq, deste, estilo=estilo))

    ocupados = {str(m.get("pref") or "") for m in ctx.mesa}
    sem_ninguem = _do_lado({}, specs)
    for pref in sorted(_lugares_que_o_desenho_da_por_vazios() - ocupados):
        modo_vazio = str(sem_ninguem["modo-chave"])
        vazia: dict[str, Any] = {f"modo-chave-{sig}": _sem_nada("modo", modo_vazio)
                                 for sig in LADOS}
        vazia.update({f"{pref_}{sig}": SEM_APARELHO_AQUI
                      for pref_ in (PREFIXO_DA_DICA_DO_MODO, PREFIXO_DA_DICA_DA_IMERSAO)
                      for sig in LADOS})
        vazia.update({f"{CAMPO_DA_IMERSAO}-{sig}": _sem_nada("imersao", SEM_IMERSAO)
                      for sig in LADOS})
        vazia.update({f"{PREFIXO_DA_FAMILIA_DA_IMERSAO}{sig}": "" for sig in LADOS})
        # colunas` do piloto, e com ela some o `data-conectado="nao"` que segura
        vazia[CAMPO_DO_CHIP] = _chip_do_lugar_vazio(pref)
        # `--plastico` do embrulho (`escrever` chama `removeProperty`), que é o
        vazia[CAMPO_DO_PLASTICO] = ""
        vazia.update(dict.fromkeys(CAMPO_DA_FORCA.values(), 0))
        colunas[pref] = vazia
        pintados += sum(1 for k in vazia if k in tem_endereco)

    # depende o `data-conectado="nao"` do piloto. Com um controle só na mesa,
    for pref in sorted(_todos_os_lugares_da_pagina() - ocupados):
        blocos.update(_blocos_da_coluna(
            pref, dict.fromkeys(LADOS, sem_ninguem), estilo=estilo))
        # emitir uma coluna custaria o `data-conectado="nao"` que segura o
        if CAMPO_DO_CHIP not in (colunas.get(pref) or {}):
            blocos[seletor_do_chip(pref)] = _chip_do_lugar_vazio(pref)

    blocos[SELETOR_DOS_SEUS] = html_dos_seus_efeitos()
    modo_da_aba = modo_dos_gatilhos_do_perfil(p)
    return {
        "colunas": colunas,
        "blocos": blocos,
        CAMPO_DO_ESTILO: _rotulo_do_estilo(estilo),
        # O MODO DA ABA: o quadro leva o modo no `data-modo-da-aba` (a folha deixa as colunas
        # paradas no Automático), e cada botão do par acende pelo modo do perfil.
        GESTO_DO_MODO: modo_da_aba,
        f"{GESTO_DO_MODO}-{MODO_AUTOMATICO}": "sim" if modo_da_aba == MODO_AUTOMATICO else "",
        f"{GESTO_DO_MODO}-personalizado": "sim" if modo_da_aba == "personalizado" else "",
        # `perfil` saiu em 13/09/2026: o chip é das dez, dono `pacotes.topo()`.
        "sem_dono": {},
        "cobertura": {"pintados": pintados, "sem_dono": len(SEM_DONO),
                      "sem_endereco": sum(1 for col in colunas.values()
                                          for k in col if k not in tem_endereco),
                      "blocos": len(blocos)},
    }


def _blocos_da_coluna(pref: str, deste: dict[str, dict[str, Any]],
                      estilo: str = "") -> dict[str, str]:
    """As duas listas de cada lado de uma coluna: o efeito de acionamento e o de imersão.

    O seletor é CSS e tem de achar UM elemento: o piloto usa `document.querySelector`, e
    `[data-controle="p1"] select.g2-acion[data-lado="e"]` é único na página. Os blocos são
    pintados antes dos campos, então o `modo-chave-<lado>` reescolhe a opção depois da troca
    da lista. A de imersão é a mesma nos dois lados: só o estilo do perfil muda a ordem.
    """
    fora: dict[str, str] = {}
    if not pref:
        return fora
    for sig in deste:
        lugar = f'[data-controle="{pref}"]'
        fora[f'{lugar} select.g2-acion[data-lado="{sig}"]'] = (
            html_das_opcoes_de_modo(LADOS[sig]))
        fora[f'{lugar} select.g2-imersao[data-lado="{sig}"]'] = (
            html_das_opcoes_de_imersao(estilo))
    return fora


from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` da coluna onde o usuário clicou. Vazio = recusa, nunca "todos".

    ESTA ABA TEM UMA COLUNA POR CONTROLE, e o alcance é a diferença entre um
    ajuste e um estrago: o `trigger.reset` sem `uniq` vai em BROADCAST e zera o
    gatilho dos quatro. Foi o defeito ABAS-06 (25/07), descrito no próprio
    `ipc_bridge.trigger_reset_detalhado`: *"com 'Controle 2' selecionado,
    'Desligar' zerava o gatilho dos QUATRO"*. Aqui ele não pode voltar.
    """
    return str(o.get("uniq") or "")


def _exigir_controle(o: dict[str, Any], gesto_: str) -> str:
    """O `uniq` da coluna, ou uma recusa que DIZ QUAL é o caso. Nunca inventa.

    SÃO DOIS CASOS, e tratá-los pela mesma frase foi um defeito medido em
    02/09/2026. O `hefesto_vivo._gesto` resolve `uniq` percorrendo a mesa por
    `pref`; um clique numa coluna VAZIA não acha nada e chega aqui igualzinho a
    um clique que não trouxe controle nenhum. A frase única — *"o clique não
    disse em qual controle"* — culpa o instrumento quando quem está errado é a
    tela: a página publicada deixa os quatro `<select>` e o "Guardar esse
    efeito" das colunas P3 e P4 CLICÁVEIS, com `data-conectado="nao"` ao lado.

    Fotografado no mesmo dia: as colunas P3 e P4 dizem `Desconectado` no
    cabeçalho e mostram `Desligado` · `— Nenhum —` em campos que abrem. A cura
    de forma é o `disabled` no gerador (`aba03.py`), e publicá-la é ato dela;
    a cura de FUNDO é esta — o gesto recusa, e a frase vai para a tela.
    """
    uniq = _uniq(o)
    if uniq:
        return uniq
    lugar = str(o.get("controle") or "").strip()
    if lugar:
        raise RuntimeError(
            f"não há controle no lugar {lugar.upper()}. Ligue um aqui e ele "
            f"pega o efeito.")
    raise ValueError(f"{gesto_}: o clique não disse em qual controle")


def _lado(o: dict[str, Any]) -> str:
    """`e`/`d` da tela → `left`/`right` do daemon, pela tradução que já existe."""
    sigla = str(o.get("lado") or "").strip()
    if sigla not in LADOS:
        raise ValueError(
            f"o clique não disse qual gatilho (veio {sigla!r}; espero 'e' ou 'd'). "
            f"É o `data-lado` do campo de escolha.")
    return LADOS[sigla]


def _escolhido(o: dict[str, Any]) -> str:
    """O que o usuário escolheu no campo, sem inventar nada quando não veio."""
    return str(o.get("modo") or o.get("v") or o.get("valor") or "").strip()


def _desfecho(resposta: Any) -> tuple[bool, str, dict[str, Any] | None]:
    """`(ok, motivo, corpo)` de uma resposta da ponte, que tem TRÊS formas.

    `trigger_set` devolve `bool`, `trigger_set_checked` devolve `(ok, motivo)` e
    `trigger_set_detalhado` devolve `(ok, motivo, corpo)`. Normalizar aqui é o
    que permite o gesto RECUSAR DIZENDO sem depender de qual das três a ponte
    entregou — e um `ok, motivo = ...` rígido rebentaria com um `TypeError` na
    primeira troca de porta, que é erro sobre erro.

    O CORPO DEIXOU DE SER JOGADO FORA — 03/09/2026, e era a terceira mentira
    desta aba. Esta função reduzia a resposta a `(ok, motivo)`, e com isso três
    desfechos diferentes chegavam à tela como o mesmo silêncio de sucesso:

    * `{status: ok, aplicado_em: [], guardado_em: []}` — **nada aconteceu**, e é
      a rota que a bancada mediu em 23/08 com a aba dizendo "aplicado";
    * `guardado_em` com alguém — a intenção ficou guardada e o gatilho dela
      **não mudou**;
    * `status: ok` COM `motivo` — a recusa que vem dentro de uma resposta
      bem-sucedida (`ipc_bridge._recusa_no_corpo`), que `trigger_set_detalhado`
      entrega com `ok=True`.

    `None` quer dizer *"não há corpo a ler"* — a ponte antiga, ou o dublê da
    régua. Nesse caso quem decide continua sendo o `ok`, exatamente como antes.
    """
    if isinstance(resposta, tuple):
        motivo = resposta[1] if len(resposta) > 1 else ""
        corpo = resposta[2] if len(resposta) > 2 else None
        return (bool(resposta[0]), str(motivo or ""),
                corpo if isinstance(corpo, dict) else None)
    return bool(resposta), "", None


def _na_lingua_da_tela(motivo: str, modo: str) -> str:
    """A recusa do daemon na língua dos rótulos desta aba. Sem dono novo.

    O TRADUTOR JÁ EXISTIA E NINGUÉM O CHAMAVA. `triggers_actions.
    humanizar_erro_gatilho` (`app/actions/triggers_actions.py`) é a HARM-19,
    escrita e testada para a aba Gatilhos da GUI estável: o daemon fala a língua
    do `core/trigger_effects` — *"end (3) deve ser > start (5)"* — e ela devolve
    *"Fim (3) precisa ser maior que Início (5)"*, com os MESMOS rótulos que o
    `<select>` desta tela mostra, porque tira os dois do mesmo `spec.params`.
    Conferido em 02/09/2026: zero pacotes da interface nova a chamavam, e a
    recusa chegava CRUA à tela do usuário.

    O `_rotulo_do_param` (`:45`) FICA PRIVADO, e é decisão escrita: quem precisa
    dele é esta função, que já o usa por dentro. Torná-lo público criaria uma
    segunda porta para a mesma tradução — e a próxima pessoa teria de escolher
    entre duas, que é o defeito que a regra do dono único existe para matar.

    O MOTIVO CRU VOLTA INTEIRO quando não há tradução, e é deliberado: o
    `humanizar_erro_gatilho` devolve `None` para todo formato que não conhece
    (*"aí o chamador mostra o texto cru do daemon, que ainda diz mais que
    'daemon offline?'"*, palavras do próprio docstring dele). Calar aqui seria
    trocar uma frase feia por nenhuma.

    E ELE NÃO PODE DERRUBAR O GESTO. O módulo do tradutor importa `Gtk` no topo;
    numa árvore sem PyGObject o import levanta, e um `except` que virasse erro
    faria a interface recusar um clique VÁLIDO por causa da tradução da recusa.
    """
    if not motivo:
        return motivo
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.triggers_actions import (
            humanizar_erro_gatilho,
        )
    except Exception:
        return motivo
    specs = _specs()
    spec = specs.get_spec(modo) if specs else None
    return humanizar_erro_gatilho(motivo, spec) or motivo


def _padroes(nome: str) -> list[int]:
    """Os ajustes PADRÃO daquele modo, na ordem em que o daemon os lê.

    NÃO SE DIGITA NENHUM NÚMERO. `preset_to_positional_params(spec, {})` devolve
    `[p.default for p in spec.params]`, que é a mesma lista que a GUI estável
    monta nos sliders ao trocar de modo (`triggers_actions._rebuild_params` →
    `_apply_trigger`), e a mesma ordem que `_persist_params_to_draft` grava —
    *"usa SEMPRE a lista posicional plana na ordem do spec"*.

    E ELA JÁ É O FORMATO DO FIO PARA OS TRÊS MODOS "ESPECIAIS", conferido contra
    `triggers_actions._send_trigger_named`: `MultiPositionFeedback` tem
    `pos_0..pos_9` (= `strengths`), `MultiPositionVibration` tem
    `frequency, pos_0..pos_9` (= `[freq, *strengths]`) e `Custom` tem
    `mode, force_0..force_6` (= `[mode, *forces]`). Os três casos que aquela
    função trata à mão saem prontos daqui — não há caso especial a reescrever.
    """
    specs = _specs()
    if specs is None:
        raise RuntimeError(
            "modo: não consegui ler os ajustes deste modo, e aplicá-lo assim "
            "deixaria o gatilho solto. Nada foi mandado.")
    spec = specs.get_spec(nome)
    if spec is None:
        raise ValueError(
            f"modo: {nome!r} não é um dos modos do produto "
            f"(`app/actions/trigger_specs.PRESETS`).")
    return list(specs.preset_to_positional_params(spec, {}))


#: `reenviar`, que somava com ele os desfechos dos DOIS gatilhos da coluna, e
#: saiu com o botão. Fica o primeiro, a D-17: o `_aplicar` soma o recibo do
#: guardou*. A constante fica onde subiu, acima do chamador: quem lê `_aplicar`
_E_TAMBEM = " · "


def _aplicar(p: Any, lado: str, modo_: str, params: list[int],
             uniq: str, ctx: Contexto | None = None) -> tuple[bool, str, str]:
    """Manda o efeito ao daemon pela porta CERTA, e a certa depende do modo.

    "DESLIGADO" É `trigger.reset` (a R-19): ele grava `Off`, carimbado com a
    camada `usuaria` daquele controle, e o jogo que mandar efeito depois vence.

    A FUNÇÃO EXISTE PORQUE HÁ MAIS DE UM CHAMADOR — o `modo`, a `imersao` e a régua.
    Escrito em cada um, o `if chave == "Off"` some num deles no dia em que alguém mexer.

    E ELA É O CHOKE POINT DO RASCUNHO — 03/09/2026. Toda escrita no gatilho
    passa por aqui, então é aqui que a tela aprende o que foi aplicado. É o
    lugar da GTK: `_persist_params_to_draft` é chamado ANTES de todo envio
    (`triggers_actions.py`), pela mesma razão — quatro chamadores gravando
    o draft por conta própria seria o quarto que esquece.

    O RASCUNHO SÓ RECEBE O QUE O DAEMON ACEITOU. Guardar antes faria a tela
    afirmar um efeito que o aparelho recusou — trocaria a mentira de hoje (a
    escolha some) por uma pior (a escolha fica, e é falsa).

    E ELE DEVOLVE O RECIBO — 04/09/2026, a D-01. A terceira casa é a frase de
    SUCESSO daquele envio, e ela sai daqui porque é aqui que o CORPO do daemon
    existe: montá-la nos quatro chamadores seria o quarto que esquece, que é o
    mesmo argumento pelo qual o rascunho já mora nesta função.

    **A TERCEIRA CASA DEIXOU DE SER O RECIBO E PASSOU A SER A NOTÍCIA —
    06/09/2026, a `03-Q4` dela.** Perguntada com as quatro formas lado a lado,
    o usuário escolheu *"O campo pisca em verde"*, e a opção que descrevia o que esta
    função fazia até aqui — a tarja verde no cartão com a frase do recibo — foi
    a que ela recusou, com estas palavras: *"nenhuma palavra nova entra na
    tela"*. A regra que isso escreve, e ela vale para a aba inteira:

        *quando o gesto só repete o que ela acabou de fazer, a tela pisca;
        quando ele tem NOTÍCIA, a tela fala.*

    Então a terceira casa passa a responder **"o que ela precisa saber e não
    está vendo"**, e são dois casos só:

    * aparelho recebeu **e** perfil guardou → `""`. A piscada do campo
      (`hefesto_vivo.MS_DA_PISCADA`) é a resposta inteira, e o cartão fica
      calado. Um `""` cai no MESMO ramo de um `{}` porque
      `_deu_certo_dizendo` testa `bruto.strip()` antes de aceitar a frase —
      conferido no fonte do piloto, não suposto.
    * aparelho recebeu **e** o disco não guardou → as duas metades, somadas
      pelo :data:`_E_TAMBEM`, com o recibo NA FRENTE. É a `AS-DUAS-ABAS-FALAM-01`
      inteira, e ela não se desfaz aqui: é justamente por ela existir que o
      corte é entre *sucesso pleno* e *meio ato*, e não entre *sucesso* e
      *recusa*.

    **A ESCOLHA MORA NESTA FUNÇÃO, e não nos gestos**, pela razão de sempre:
    escrita nos quatro, o quarto é o que esquece — e o defeito seria mudo,
    porque um gesto que manda recibo a mais não quebra nada, só devolve à tela
    a palavra que o usuário mandou tirar. É o defeito de forma que esta casa pagou
    duas vezes em 05/09.

    **`_recibo` NÃO se apagou**, e continua dono da frase: o que mudou é QUANDO
    ele é chamado — só quando há uma segunda metade para prefixar.

    ``recibo_sempre`` SAIU EM 08/09/2026, COM O `reenviar`. Ele era a exceção e
    tinha um dono só: o reenvio decidia pelo **par** e não pelo lado, então
    pedia o recibo sempre e escolhia depois. Com o botão fora da tela por
    decisão de produto, o sinalizador ficou sem chamador — e um parâmetro que ninguém
    passa é um ramo que ninguém mede. Se a faixa de reenvio voltar, ele volta
    com ela; a razão está guardada na lápide. **Sem aquela porta, a frase da
    recusa perderia o nome do gatilho que
    FUNCIONOU** — medido: a régua `test_um_lado_que_recusa_nao_cala_o_outro`
    reprovou com a frase *"Gatilho esquerdo (L2): Rigid — end (3)… · "*, com o
    separador pendurado e o R2 sumido. É a cura TRG-01 de novo, pelo avesso.

    **E O RECIBO PASSOU A DIZER AS DUAS METADES — 06/09/2026, a decisão D-17**
    (a sprint `AS-DUAS-ABAS-FALAM-01`). Quando o
    efeito FOI para o aparelho e o DISCO não recebeu, a terceira casa sai como
    *«… aplicado · o efeito FOI para o aparelho, mas não consegui ABRIR o
    perfil …»*, somada pelo :data:`_E_TAMBEM`. Ela continua sendo a frase de
    SUCESSO — o canal é o `{"recado": …}` do verde de 6 s, e não o `RuntimeError`
    do laranja de 30 s, porque um gesto que fez o que prometeu no aparelho **não
    é recusa**. É a mesma escolha que `a06_navegacao._guardar_no_perfil` já
    tinha feito, com a razão escrita lá.

    E ELE PASSOU A GRAVAR NO PERFIL — 05/09/2026, a **decisão D2**
    (o registro «AS-TRES-DECISOES-DO-PERFIL-medidas-e-decididas» de 05/09/2026):
    *"persistência no clique em toda parte, com o rodapé como rede de
    segurança"*. O usuário pediu, com estas palavras: *"ao pular e sair configurando
    de aba em aba o perfil vai se lembrando de cada config de cada aba pra cada
    controle … e salvar se lembra disso quando eu for jogar o jogo e no dia
    seguinte"*.

    **O QUE FALTAVA, MEDIDO:** `controllers[uniq].triggers` não persistia por
    clique nenhum. O `_RASCUNHO` guardava o gatilho aplicado NESTA SESSÃO e o
    rodapé não o alcançava — `pacotes/rodape.py` não importa este módulo. Clicar
    `Rígido` no L2 e depois "Salvar perfil" gravava o gatilho DE ONTEM, porque o
    rodapé monta o rascunho a partir do PERFIL NO DISCO. É o mesmo defeito que
    o reenvio nomeava pela outra ponta, antes de o botão sair da tela.

    **O RASCUNHO CONTINUA, e não é redundância:** ele é a memória entre o clique
    e o tique seguinte (500 ms), e é ele que impede a coluna de voltar ao valor
    velho enquanto o disco não chega. O disco é a memória do dia seguinte.

    **A GUARDA É A MESMA DO RASCUNHO** — `ok and _chegou_ao_aparelho(corpo)`.
    Gravar no perfil um efeito que o aparelho recusou seria a tela prometendo
    amanhã o que não fez hoje.
    """
    if modo_ == "Off":
        ok, motivo, corpo = _desfecho(p.trigger_reset_detalhado(lado, uniq=uniq))
        params = []
    else:
        ok, motivo, corpo = _desfecho(
            p.trigger_set_detalhado(lado, modo_, params, uniq=uniq))
    nao_guardou = ""
    if ok and _chegou_ao_aparelho(corpo):
        _lembrar_o_aplicado(
            perfil.nome_do_ativo(ctx.state if ctx else None),
            uniq, lado, {"mode": modo_, "params": params})
        nao_guardou = _guardar_no_perfil(ctx, p, uniq, lado,
                                         {"mode": modo_, "params": params})
    ok, motivo = _conferir_o_desfecho(lado, modo_, ok, motivo, corpo, ctx, uniq)
    recibo = ""
    if nao_guardou:
        recibo = _recibo(lado, modo_, corpo, ctx, uniq)
    if nao_guardou:
        recibo = _E_TAMBEM.join((recibo, nao_guardou))
    return ok, motivo, recibo


def _guardar_no_perfil(ctx: Contexto | None, p: Any, uniq: str, disco: str,
                       cfg: dict[str, Any]) -> str:
    """Grava no perfil ATIVO o gatilho que acabou de chegar ao aparelho.

    :return: `""` quando gravou — e também quando não havia o que gravar, ou
        quando não há perfil ativo. A frase do que NÃO deu quando havia perfil
        NOMEADO e o arquivo não abriu. É a mesma assinatura de
        `a06_navegacao._guardar_no_perfil`, e usar a mesma não é gosto: são os
        dois únicos escritores de perfil por clique que não podem levantar.

    **SÓ O LADO QUE ELA TOCOU.** :func:`_com_os_gatilhos` recebe um dicionário
    de um item só, e o esquema faz o resto: `model_fields_set` decide o que é
    opinião do controle e o que herda a seção global do perfil
    (`profiles/manager._controllers_to_specs` lê os dois lados separados). Se
    este caminho escrevesse os DOIS, clicar `Rígido` no L2 gravaria um `Off`
    explícito no R2 e silenciaria o gatilho direito que o perfil dava a todo
    mundo — um efeito dela apagado por um clique no outro lado.

    **NÃO ABRIU O PERFIL, NÃO GRAVA — E NÃO LEVANTA.** São dois casos: não há
    `active_profile`, ou o nome que
    o daemon publica não existe para ESTE leitor. O segundo não é hipótese: as
    réguas desta aba rodam com `active_profile` de mentira, e na máquina do usuário o
    daemon pode nomear um perfil que a pasta lida aqui não tem (apagado,
    renomeado, outra pasta). Nos dois, o gatilho FOI para o aparelho e o
    `_RASCUNHO` o segura na tela — levantar diria "não deu" sobre um efeito que
    ela está sentindo na mão. **Esta metade vale, e é ela que escolhe o CANAL:**
    o do `{"recado": …}` verde, nunca o do `RuntimeError` laranja.

    **NÃO ABRIU O PERFIL, NÃO FALA — CADUCOU EM 05/09/2026, decisão D-17**
    (*"as duas abas falam"*, dela). Até aqui esta função sumia neste ramo, e o
    argumento acima era usado para as duas coisas — mas ele é verdadeiro sobre
    o CANAL e falso sobre o SILÊNCIO. **A frase não diz "não deu": diz as duas
    metades** — *o aparelho recebeu · o perfil não guardou* —, e é o ramo irmão
    logo abaixo que já a escrevia. E o caso que justificava o silêncio é
    justamente o caso em que ela precisa saber: perfil apagado, renomeado ou
    noutra pasta quer dizer que **cada gatilho ajustado a partir dali morre na
    próxima troca de perfil**, com o produto SABENDO e não dizendo.

    **MAS A GRAVAÇÃO QUE FALHA FALA.** Perfil aberto e escrita recusada é a
    promessa de amanhã que não se cumpre — o defeito exato que a decisão D2 veio
    matar. A frase diz as duas metades: o aparelho recebeu, o perfil não
    guardou. Sem isso, ela descobriria a perda no dia seguinte, longe do clique.

    **E ELA AINDA FALA PELO CANAL DA RECUSA — declarado, não esquecido.** Os
    dois ramos desta função dizem as duas metades desde a D-17, mas por canais
    diferentes: o de ABRIR devolve frase (verde de 6 s) e o de GRAVAR levanta
    `RuntimeError` (laranja de 30 s). Alinhá-los é outra sprint, e ela precisa
    das réguas do outro ramo relidas uma a uma — a mesma divergência que a
    §5 da D-17 mede entre a aba 02 e a aba 06 e deixa declarada.

    O CAMINHO DE DISCO É :func:`_gravar_so_o_gatilho`, e não
    `perfil.gravar_e_reaplicar`. A razão está medida lá: reaplicar o perfil
    inteiro acende de volta a barra de luz que ela desligou noutra aba.
    """
    nome = perfil.nome_do_ativo(getattr(ctx, "state", None)).strip()
    if not nome:
        return ""
    try:
        prof = perfil._com_o_src().load_profile(nome)
    except Exception:
        return (f"o efeito foi para o aparelho, mas não entrou no perfil "
                f"{nome}. Ele vale até você trocar de perfil.")
    try:
        novo = _com_os_gatilhos(prof, uniq, {disco: cfg})
        if novo is not None:
            _gravar_so_o_gatilho(novo, p)
    except Exception as erro:
        raise RuntimeError(
            f"o efeito foi para o aparelho, mas não entrou no perfil "
            f"{nome}. Ele vale até você trocar de perfil.") from erro
    return ""


_CAMPOS_DE_DESTINO = ("aplicado_em", "guardado_em")


def _fala_de_destino(corpo: dict[str, Any] | None) -> bool:
    """O corpo diz alguma coisa sobre ONDE a escrita foi parar?"""
    return isinstance(corpo, dict) and any(c in corpo for c in _CAMPOS_DE_DESTINO)


def _chegou_ao_aparelho(corpo: dict[str, Any] | None) -> bool:
    """O byte SAIU no fio para alguém — a pergunta que decide o rascunho."""
    if not _fala_de_destino(corpo):
        return True
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.ipc_bridge import destinos_da_aplicacao
    except Exception:
        return True
    aplicado, _ = destinos_da_aplicacao(corpo)
    return bool(aplicado)


def _como_a_janela_pergunta(ctx: Contexto | None, uniq: str) -> Any:
    """O `host` que `frase_do_desfecho` interroga, com o que ESTA aba sabe.

    A GTK lê três coisas do objeto da janela para explicar um "guardado": o
    alvo de edição, o mapa de conectados e o modo nativo. Esta aba SABE as três,
    e melhor do que a GTK — ela não tem alvo de edição, tem uma COLUNA POR
    CONTROLE, e a coluna clicada é o alvo sem ambiguidade nenhuma.

    POR QUE UM DUBLÊ E NÃO UMA SEGUNDA FRASE: `app/textos_de_aplicacao.py` é o
    dono único do vocabulário de aplicado/guardado/nada-aconteceu, e a D-9 diz
    com todas as letras por que ele é um só — *"para que trocá-lo seja uma
    linha, e não uma caçada por strings"*. Escrever aqui "guardado, vai valer
    quando…" seria a sexta cópia.

    OS TRÊS ATRIBUTOS SÃO OS DO CONTRATO, e não inventados:
    `_alvo_de_edicao` (o canônico de `app/alvo_de_edicao.py`),
    `_target_uniq_by_index` (o mapa que a aba Status recalcula do `state_full`)
    e `_modo_nativo_ligado` (o `native_mode` do mesmo `state_full`).
    """
    from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, EstadoDoAlvo

    conectados = list((ctx.conectados if ctx else []) or [])
    rotulo = ""
    for c in conectados:
        if str(c.get("uniq") or "") == uniq:
            # `player_slot` preenchido. Lendo cru, o secundário do co-op vinha
            rotulo = f"Controle {jogador_de(c) or '?'}"
            break

    class _Janela:
        def __init__(self) -> None:
            self._alvo_de_edicao = AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq,
                                                label=rotulo or None)
            self._target_uniq_by_index = {i: str(c.get("uniq") or "")
                                          for i, c in enumerate(conectados)}
            self._modo_nativo_ligado = bool(
                (ctx.state if ctx else {}).get("native_mode"))

    return _Janela()


def _assunto(lado: str, modo_: str) -> str:
    """`"Gatilho esquerdo (L2): Rigid"` — o assunto de toda frase desta aba."""
    return f"{NOME_DO_LADO.get(lado, lado)}: {modo_}"


def _recibo(lado: str, modo_: str, corpo: dict[str, Any] | None,
            ctx: Contexto | None, uniq: str) -> str:
    """A frase de SUCESSO que vai ao CARTÃO daquele controle — a D-01 em ato.

    **O DEFEITO QUE ELA FECHA**, e ele é a queixa de origem desta casa: quando
    dava certo, a tela não dizia nada. O piloto imprimia `[gesto] … → aplicado`
    no terminal de quem lançou a janela, e quem clica não lê terminal. A decisão, 04/09/2026: *"No
    próprio cartão, como a recusa."*

    **NÃO HÁ CANAL NOVO AQUI, e é o ponto inteiro do conflito C-3.** A lista
    desta aba propunha *o campo que pisca*; o cartão é a mesma peça das outras
    quatro abas. Esta função só ESCREVE a frase — quem a leva ao cartão é o
    `hefesto_vivo._deu_certo_dizendo`, lendo o `recado` que o gesto devolve.

    **QUEM ESCOLHEU O CARTÃO FOI O PO, E A ESCOLHA CADUCOU — 06/09/2026.** Este
    parágrafo dizia *"o usuário escolheu o cartão"*, e a atribuição estava errada nas
    duas metades. Quem recusou o campo que pisca foi o PO, em 04/09, lendo a
    D-01 (*"no próprio cartão, como a recusa"*) como se ela fechasse a FORMA —
    o conflito C-3 de `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` é
    dele. Em 05/09 ELA respondeu a `03-Q4` vendo as quatro formas lado a lado e
    escolheu **o campo que pisca**, com *"nenhuma palavra nova entra na tela"*.
    A palavra de produto vence a leitura que o PO fez da palavra de produto.

    **O QUE ISSO FAZ COM ESTA FUNÇÃO: ela sai do caminho do sucesso pleno, e
    não do produto.** O `_aplicar` só a chama quando há uma segunda metade a
    prefixar (a `AS-DUAS-ABAS-FALAM-01`), e aí a frase abre pelo que ela fez.
    As três frases que contam esta história — esta, a do `_aplicar` e a do
    `hefesto_vivo._deu_certo_dizendo` — têm de dizer o mesmo, ou a próxima
    pessoa acredita na que ler primeiro.

    A FRASE É DO DONO DO ASSUNTO: `app/textos_de_aplicacao.frase_do_desfecho`,
    a mesma que a barra da GTK usa, com o CORPO do daemon como autoridade — é
    ela que sabe dizer *"aplicado em 2 controles"* em vez de um "aplicado" que
    não conta.

    **O CORPO QUE NÃO FALA DE DESTINO NÃO PASSA POR ELA**, e essa guarda é a
    lição de 04/09: o dublê da régua devolve `{}`, e `frase_do_desfecho` leria
    as duas listas vazias como *"nenhum controle recebeu"* — um recibo de
    SUCESSO afirmando que nada aconteceu. É a mesma armadilha que
    `_fala_de_destino` já documenta do outro lado, e a resposta é a mesma
    pergunta.
    """
    assunto = _assunto(lado, modo_)
    if not _fala_de_destino(corpo):
        return f"{assunto} aplicado"
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_do_desfecho

        return frase_do_desfecho(assunto, corpo, _como_a_janela_pergunta(ctx, uniq))
    except Exception:
        return f"{assunto} aplicado"


def _conferir_o_desfecho(lado: str, modo_: str, ok: bool, motivo: str,
                         corpo: dict[str, Any] | None,
                         ctx: Contexto | None, uniq: str) -> tuple[bool, str]:
    """Levanta quando o gatilho dela NÃO mudou, com a frase do dono do assunto.

    A DÍVIDA QUE ISTO PAGA, e ela é a feature 19 da medição de 03/09: *"dizer
    na tela o desfecho — aplicado, guardado para depois, nada aconteceu"*. A
    GTK escreve na barra de status a cada Aplicar, lendo o CORPO do daemon
    (`_toast_trigger` → `frase_do_desfecho`, ELO-MUDO-01/T3). O HTML jogava o
    corpo fora, e três desfechos diferentes viravam o mesmo nada.

    O CANAL É O `RuntimeError`, e é o único que esta tela tem: o piloto leva a
    frase de um `RuntimeError` ao CARTÃO daquele controle
    (`hefesto_vivo._recusou_dizendo`) e não tem por onde levar a de um sucesso.
    Então a regra é a honesta: **cala quando o byte saiu, fala quando não
    saiu.** O "aplicado" na tela — a outra metade da feature 19 — precisa de um
    lugar na página, e lugar na página é do usuário.

    SÃO DOIS OS CASOS QUE FALAM, e o segundo é o mais fino:

    * nada saiu no fio (as duas listas vazias, ou só `guardado_em`);
    * o corpo traz `motivo` COM `status: ok` — sucesso PARCIAL
      (`ipc_bridge._recusa_no_corpo`). O `ok` continua `True` e o byte pode até
      ter saído, mas o daemon disse alguma coisa e essa coisa é do usuário.

    A RECUSA SECA (`ok=False`) NÃO PASSA POR AQUI: quem a trata é o chamador,
    que sabe nomear o que tentou aplicar ("o seu efeito 'Recuo do MK'", "a curva
    'stop_hard'"). Repetir a decisão aqui daria duas frases para a mesma recusa.

    SEM CORPO NÃO HÁ O QUE CONFERIR: a ponte antiga e o dublê da régua não
    devolvem corpo, e nesse caso o `ok` decide, palavra por palavra como antes.

    O ASSUNTO É A FRASE DA GTK, e não uma escrita aqui: `_toast_trigger` monta
    `"Gatilho esquerdo (L2): <modo>"` — a cura TRG-01, que existe porque a barra
    dizia `"LEFT -> Off"`, trocando a fala do usuário por id interno mais o lado em
    inglês. A tela nova não vai reintroduzir o defeito com outro atalho.
    """
    assunto = _assunto(lado, modo_)
    if not ok or corpo is None:
        return ok, motivo
    calado = ((not _fala_de_destino(corpo) or _chegou_ao_aparelho(corpo))
              and not str(corpo.get("motivo") or ""))
    if calado:
        return ok, motivo
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_do_desfecho

        frase = frase_do_desfecho(assunto, corpo, _como_a_janela_pergunta(ctx, uniq))
    except Exception:
        frase = f"{assunto} — o Hefesto respondeu, e nenhum controle recebeu."
    raise RuntimeError(frase)


def _metade_do_meu(nome: str, lado: str) -> tuple[str, list[int]]:
    """`(modo, ajustes)` da metade deste gatilho num efeito que a pessoa guardou."""
    meia = _meia_do_efeito(meus_efeitos().get(nome), lado)
    if meia is None:
        raise RuntimeError(
            f"«{nome}» não tem nada para este gatilho: quando ele foi "
            f"guardado, só o outro lado estava ajustado.")
    return (str(meia.get("mode") or "Off"),
            [int(v) for v in (meia.get("params") or [])])


@gesto("03-gatilhos.html", "modo", grava="_gravar_so_o_gatilho")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Escolher um modo APLICA o efeito naquele gatilho, naquele controle.

    É O QUE O PRÓPRIO DESENHO PROMETE, na dica do quadro: *"Escolher um modo já
    manda o efeito para aquele controle, e quem está com ele na mão sente na
    hora"* — e *"soltar já manda"*. É também a decisão de 01/09 para a
    interface inteira: o gesto age na hora, e não junta rascunho.

    E É O QUE A GUI ESTÁVEL FAZ. `triggers_actions._on_mode_changed` remonta os
    ajustes nos padrões do modo (`_rebuild_params`) e agenda o live-preview de
    300 ms, que chama `_apply_trigger` com esses mesmos padrões. Aqui não há
    debounce a fazer: o clique é um, não um arrastar de slider.

    "DESLIGADO" É `trigger.reset`, pelo `_aplicar`: o `Off` sem efeito do
    Hefesto, e o jogo que mandar efeito depois vence.

    A PORTA É A `_detalhado`, e não a `_checked`, pela mesma razão que a GUI
    estável migrou (ELO-MUDO-01/T3): só ela junta as DUAS formas de o daemon
    dizer não — o erro JSON-RPC de parâmetro inválido e a recusa que vem DENTRO
    de uma resposta bem-sucedida (`_recusa_no_corpo`). Com a `_checked`, a
    segunda chegaria como sucesso.
    """
    _nao_no_automatico(ctx)
    uniq, lado = _exigir_controle(o, "modo"), _lado(o)
    chave = _escolhido(o)
    if not chave:
        raise ValueError(
            "modo: o clique não trouxe qual modo foi escolhido. O `<select>` "
            "carrega a chave no `value` de cada opção; quem tem de mandá-la é a "
            "ponte do piloto, no `change` — ver `_escolhido`.")
    if chave == TRAVESSAO:
        raise ValueError(
            "modo: `—` é como esta tela diz que não há controle neste lugar, e "
            "não um efeito a aplicar. Escolha `Sem efeito` para soltar o gatilho.")
    if chave.startswith(PREFIXO_DO_MEU):
        nome = chave[len(PREFIXO_DO_MEU):]
        modo_salvo, params = _metade_do_meu(nome, lado)
        ok, motivo, recibo = _aplicar(p, lado, modo_salvo, params, uniq, ctx)
        if not ok:
            raise RuntimeError(_na_lingua_da_tela(motivo, modo_salvo)
                               or f"o Hefesto não aplicou o efeito «{nome}»")
        return {"recado": recibo}
    ok, motivo, recibo = _aplicar(p, lado, chave, _padroes(chave), uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, chave)
                           or f"o Hefesto não aplicou o modo «{_rotulo_do_modo(chave)}»")
    return {"recado": recibo}


def _acionamento_da_coluna(ctx: Contexto, o: dict[str, Any], uniq: str, lado: str) -> str:
    """O efeito de acionamento em que aquele gatilho está: o da tela, senão o de agora."""
    forma = o.get("forma")
    sigla = str(o.get("lado") or "").strip()
    visto = str(forma.get(f"modo-chave-{sigla}") or "").strip() if isinstance(forma, dict) else ""
    if visto.startswith(PREFIXO_DO_MEU):
        meia = _meia_do_efeito(meus_efeitos().get(visto[len(PREFIXO_DO_MEU):]), lado)
        return str(meia.get("mode") or "Off") if meia else _modo_de_agora(ctx, uniq, lado)
    if visto and visto != TRAVESSAO:
        return visto
    return _modo_de_agora(ctx, uniq, lado)


@gesto("03-gatilhos.html", "imersao", grava="_gravar_so_o_gatilho")
def imersao_escolhida(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Escolher um efeito do gatilho põe os números dele no gatilho, na hora.

    Ele é a receita que o `PRESETS` aceita (`profiles/efeitos_de_imersao.py`), com a variante
    do estilo do perfil. O acionamento fica o da coluna (`data-hef-forma`, não o do disco) quando
    o efeito vale nele; senão vai ao de nascença do efeito (20/10/2026: a lista mostra todos os
    efeitos, e o acionamento fica atrás do Avançado). «Sem efeito» solta o gatilho
    (`trigger.reset`, como o `Off` da linha «Como o gatilho faz»). `meu:<nome>` leva o
    acionamento de onde a pessoa partiu.
    """
    _nao_no_automatico(ctx)
    uniq, lado = _exigir_controle(o, "imersão"), _lado(o)
    chave = _escolhido(o)
    if not chave:
        raise ValueError("imersão: o clique não trouxe qual imersão foi escolhida.")
    if chave == TRAVESSAO:
        raise ValueError(
            "imersão: `—` é como esta tela diz que não há controle neste lugar, e não "
            "um efeito a aplicar. Escolha `Sem efeito` para soltar o gatilho.")
    modo_ = _acionamento_da_coluna(ctx, o, uniq, lado)
    nome = chave
    if chave == SEM_IMERSAO:
        modo_ = "Off"
        params = _padroes(modo_)
    elif chave.startswith(PREFIXO_DO_MEU):
        nome = chave[len(PREFIXO_DO_MEU):]
        criada = _metade_da_imersao_criada(_meus_efeitos_da("imersao").get(nome))
        if criada is None:
            raise RuntimeError(f"«{nome}» não está mais nos seus efeitos de imersão.")
        modo_, params = str(criada["mode"]), list(criada["params"])
    else:
        imer = _imersoes()
        feita = imer.POR_CHAVE.get(chave) if imer else None
        if feita is None:
            raise ValueError(f"imersão: {chave!r} não é uma imersão do produto.")
        nome = feita.rotulo
        estilo = _estilo_do_perfil(perfil.ativo(ctx.state.get("active_profile")))
        modo_ = imer.modo_que_a_imersao_pede(feita, modo_)
        achados = _params_da_imersao(feita, modo_, estilo)
        if achados is None:
            raise RuntimeError(
                f"«{feita.rotulo}» não vale para o acionamento «{_rotulo_do_modo(modo_)}». "
                f"Escolha outro acionamento ou outra imersão.")
        params = achados
    ok, motivo, recibo = _aplicar(p, lado, modo_, params, uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, modo_)
                           or f"o Hefesto não aplicou a imersão «{nome}»")
    return {"recado": recibo}


#: o que cada barra da área «Criar efeitos novos» mexe, pelo NOME do parâmetro, e a faixa dela
SLOTS_DA_CRIACAO: dict[str, tuple[str, ...]] = {
    "inicio": ("start", "position"),
    "fim": ("end",),
    "forca": ("strength", "force", "amplitude", "start_strength", "end_strength"),
    "freq": ("frequency",),
}

FAIXA_DOS_SLOTS: dict[str, tuple[int, int]] = {
    "inicio": (0, 9), "fim": (0, 9), "forca": (0, 8), "freq": (0, 255)}

#: quanto o «Sentir» deixa o efeito tocar antes de devolver ao controle o que ele recebia
SENTIR_S = 1.5


def _ajustes_da_criacao(modo_: str, forma: dict[str, Any]) -> dict[str, int]:
    """Os parâmetros do modo que as barras mexem, em escala proporcional à faixa de cada um.

    Uma barra que o modo não tem não faz nada: a Metralhadora não tem «Início» de posição
    fixa, e o Pulso não tem «Frequência».
    """
    specs = _specs()
    spec = specs.get_spec(modo_) if specs else None
    if spec is None:
        raise ValueError(f"{modo_!r} não é um dos modos do produto.")
    fora: dict[str, int] = {}
    for slot, nomes in SLOTS_DA_CRIACAO.items():
        cru = str(forma.get(slot) or "").strip()
        if not cru:
            continue
        try:
            valor = float(cru)
        except ValueError:
            raise ValueError(f"a barra {slot!r} devolveu {cru!r}, que não é número.") from None
        de, ate = FAIXA_DOS_SLOTS[slot]
        fracao = max(0.0, min(1.0, (valor - de) / (ate - de)))
        for q in spec.params:
            if q.name in nomes or (slot == "forca" and q.name.startswith("pos_")):
                fora[q.name] = round(q.min_value + fracao * (q.max_value - q.min_value))
    return fora


def _da_area_de_criar(o: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """`(o modo de onde parte, a forma)` da área «Criar efeitos novos», ou recusa dizendo."""
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError("não consegui ler a área de criar efeitos. Nada foi feito.")
    partir = str(forma.get("partir") or "").strip()
    if not partir or partir == TRAVESSAO:
        raise RuntimeError("Escolha em qual efeito partir.")
    return partir, forma


@gesto("03-gatilhos.html", "criar-efeito", grava="guardar_meus_efeitos")
def criar_efeito_dos_gatilhos(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Criar um efeito de acionamento ou de imersão: ele entra nas listas de cima.

    Parte de um modo e das quatro barras (Início, Fim, Força, Frequência), postas na faixa
    de cada parâmetro. O acionamento vai à biblioteca dos gatilhos, com o par L2 e R2 igual;
    a imersão vai à biblioteca de imersões, com o modo de onde partiu. Só a caixa de
    preferências da interface é gravada: nenhum perfil e nenhum aparelho.
    """
    partir, forma = _da_area_de_criar(o)
    apelido = str(forma.get("nome") or "").strip()
    if not apelido:
        raise RuntimeError("Dê um nome ao efeito.")
    if len(apelido) > TETO_DO_NOME:
        raise RuntimeError(f"O nome do efeito tem no máximo {TETO_DO_NOME} letras.")
    ajustes = _ajustes_da_criacao(partir, forma)
    tipo = str(forma.get("tipo") or "").strip()
    if tipo == "imersao":
        criar_efeito("imersao", apelido, partir, ajustes)
        return
    if tipo != "acionamento":
        raise RuntimeError("Escolha se o efeito é de acionamento ou de imersão.")
    specs = _specs()
    params = [int(v) for v in specs.preset_to_positional_params(
        specs.get_spec(partir), ajustes)] if specs else []
    todos = meus_efeitos()
    todos[apelido] = {disco: {"mode": partir, "params": list(params)}
                      for disco in LADOS.values()}
    guardar_meus_efeitos(todos, "gatilhos")


def _controle_do_sentir(ctx: Contexto, o: dict[str, Any]) -> str:
    """O `uniq` do controle em que o «Sentir» toca: o do clique, o escolhido, o primeiro vivo."""
    if _uniq(o):
        return _uniq(o)
    lugar = str(o.get("controle") or getattr(ctx, "escolhido", "") or "").strip()
    for m in ctx.mesa:
        if lugar and lugar in (str(m.get("pref") or ""), str(m.get("uniq") or "")):
            return str(m.get("uniq") or "")
    for c in ctx.conectados:
        if c.get("uniq"):
            return str(c["uniq"])
    raise RuntimeError("Nenhum controle ligado para sentir o efeito. Ligue um e tente de novo.")


def _tocar(p: Any, disco: str, modo_: str, params: list[int], uniq: str) -> None:
    """Manda ao aparelho, sem lembrar no rascunho nem no perfil. Recusa dizendo."""
    if modo_ == "Off":
        ok, motivo, _ = _desfecho(p.trigger_reset_detalhado(disco, uniq=uniq))
    else:
        ok, motivo, _ = _desfecho(
            p.trigger_set_detalhado(disco, modo_, params, uniq=uniq))
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, modo_)
                           or f"o controle não tocou o efeito «{_rotulo_do_modo(modo_)}»")


def _segurar_o_toque() -> None:
    """O tempo em que a pessoa sente o efeito antes de o controle voltar ao que tinha."""
    time.sleep(SENTIR_S)


@gesto("03-gatilhos.html", "sentir")
def sentir(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Toca o efeito da área de criar nos dois gatilhos do controle escolhido, sem guardar.

    Passado o tempo, cada gatilho volta ao que o controle recebe AGORA (`Off` vira
    `trigger.reset`), lido depois do toque: uma escolha feita durante ele vale. Não grava
    perfil, não mexe no rascunho e não cria efeito.
    """
    partir, forma = _da_area_de_criar(o)
    uniq = _controle_do_sentir(ctx, o)
    params = _padroes(partir)
    ajustes = _ajustes_da_criacao(partir, forma)
    specs = _specs()
    if specs is not None and ajustes:
        params = list(specs.preset_to_positional_params(specs.get_spec(partir), ajustes))
    try:
        for disco in LADOS.values():
            _tocar(p, disco, partir, params, uniq)
        _segurar_o_toque()
    finally:
        agora = perfil.ativo(ctx.state.get("active_profile"))
        for disco in LADOS.values():
            volta = _o_que_o_controle_recebe(agora, uniq, disco)
            _tocar(p, disco, str(volta.get("mode") or "Off"),
                   list(volta.get("params") or []), uniq)


def _gravar_so_o_gatilho(novo: Any, p: Any) -> None:
    """Grava o perfil no disco — e NÃO reaplica o perfil inteiro no aparelho.

    ELE NÃO PODE SER O `perfil.gravar_e_reaplicar`, e o motivo foi MEDIDO em
    03/09/2026, clicando este botão no produto instalado com um DualSense no
    cabo. `gravar_e_reaplicar` termina em `p.profile_switch(...)`, que manda o
    daemon aplicar o perfil INTEIRO — barra de luz, LEDs de jogador, tudo. A
    prova, com um gesto só (`--prova-clique guardar`) e a barra apagada antes:

        antes   lightbar_on: false · lightbar_rgb: [0, 0, 0]
        depois  lightbar_on: true  · lightbar_rgb: [0, 0, 255]

    Ou seja: ela desliga a barra na aba Iluminação, vai aos Gatilhos, clica
    "Guardar esse efeito" — e a barra ACENDE de novo, sem nada na tela dizendo
    que isso ia acontecer. É *a tela afirmando o que não é*, na forma mais cara:
    um botão de escopo estreito ("esse efeito") desfazendo escolha viva dela em
    OUTRA aba.

    E A REAPLICAÇÃO NÃO ERA NECESSÁRIA PARA NADA. Esta aba aplica NA HORA — é a
    decisão de 01/09, *"clicar já aplica"*: cada escolha da coluna já mandou o
    efeito ao aparelho por `_aplicar`. O
    `profile_switch` reaplicava por cima um gatilho que já estava lá, e levava
    junto nove seções que ninguém pediu.

    O `launch_env.refresh` FICA, e é a metade que tem de sobreviver: sem ele o
    perfil novo só chega ao jogo no próximo start do daemon. Ele relê o que os
    jogos vão receber e não escreve no aparelho.
    """
    loader = perfil._com_o_src()
    loader.save_profile(novo, origem="interface-nova")
    p.chamar("launch_env.refresh")


@gesto("03-gatilhos.html", GESTO_DO_MODO, grava="_gravar_so_o_gatilho")
def modo_dos_gatilhos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O par «Modo automático | Modo personalizado» — e ele MUDA o perfil.

    **O Automático** deixa os gatilhos «Sem efeito» (a chave `Off`) em todos os controles: é o
    `triggers.modo` escrito como Automático, que o `ProfileManager` lê para mandar `Off` ao
    aparelho. **Nada se apaga:** as escolhas guardadas ficam no disco, e o **Personalizado** as
    devolve. O jogo que comanda o gatilho vence nos dois modos (a saída do jogo chega ao
    controle; o Hefesto só potencializa, nunca veta).

    **A LEITURA DE VOLTA É DO DISCO**, não do clique: o `data-modo` do botão diz o que o usuário
    PEDIU, e pedir o modo em que o perfil já está não grava nada.

    **REAPLICAR É METADE DO GESTO:** o modo só entra em vigor na ativação do perfil, e
    `perfil.reaplicar` é o dono desse tempo. O `_gravar_so_o_gatilho` sozinho só grava.
    """
    pedido = str(o.get("modo") or "")
    if pedido not in (MODO_AUTOMATICO, "personalizado"):
        raise ValueError(
            f"{GESTO_DO_MODO}: o clique não disse qual modo. Cada botão do par manda o "
            f"`data-modo`; um pedido sem ele não vem da tela")
    nome = perfil.nome_do_ativo(ctx.state).strip()
    if not nome:
        raise RuntimeError(
            "sem perfil ativo não há onde guardar o modo. Escolha um perfil na aba Perfis.")
    if modo_dos_gatilhos_do_perfil(perfil.ativo_que_vale(nome)) == pedido:
        return None
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = prof.model_copy(update={
        "triggers": prof.triggers.model_copy(update={"modo": pedido})})
    _gravar_so_o_gatilho(novo, p)
    perfil.reaplicar(nome, ctx, p)
    return {"recado": ("Gatilhos no modo automático: o jogo manda; o estilo ajusta."
                       if pedido == MODO_AUTOMATICO
                       else "Gatilhos no modo personalizado: valem as suas escolhas.")}


def _modo_de_agora(ctx: Contexto, uniq: str, disco: str) -> str:
    """O modo em que aquele gatilho está, pela MESMA função que a tela pinta."""
    p = perfil.ativo(ctx.state.get("active_profile")) or {}
    cfg = _o_que_o_controle_recebe(p, uniq, disco)
    return _na_lista_da_tela(
        str(cfg.get("mode") or "Off"), _params_inteiros(cfg), _specs())[0]


def _com_os_gatilhos(prof: Any, uniq: str, dos_lados: dict[str, Any]) -> Any:
    """O perfil com o gatilho DESTE controle trocado, ou `None` se nada mudou.

    `None` evita o barulho: regravar um perfil idêntico troca a data do arquivo
    e faz o daemon reaplicar — e um `profile.switch` no meio de uma partida não
    é de graça.

    A CHAVE DO OVERRIDE É O `uniq` NORMALIZADO, e é o que o esquema espera
    (`_validate_controllers_keys`). Escrever `d4:2f:…` onde o disco guarda
    `d42f…` criaria um segundo dono para o mesmo controle.

    LADO NÃO TOCADO NÃO VIRA OPINIÃO — 05/09/2026, e é o que faz a persistência
    no clique caber aqui. Antes desta linha, um `dos_lados` com uma metade só
    densificava a outra: sem override anterior ela virava um `Off` EXPLÍCITO, e
    `profiles/manager._controllers_to_specs` lê exatamente `model_fields_set`
    para decidir o que herda a seção global do perfil. Ou seja: clicar `Rígido`
    no L2 gravava um `Off` no R2 e silenciava, só naquele controle, o gatilho
    direito que o perfil dava a todos.

    Agora o lado ausente do pedido só entra se o override JÁ o tinha escrito —
    a metade que ela nunca tocou continua herdando o global, que é o contrato do
    esquema (*"`None` = sem opinião"*).
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        TriggerConfig,
        TriggersConfig,
    )

    chave = uniq.replace(":", "").lower()
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.triggers
    ja_escritos = antes.model_fields_set if antes is not None else set()
    lados: dict[str, Any] = {}
    for lado in ("left", "right"):
        if lado in dos_lados:
            lados[lado] = TriggerConfig(**dos_lados[lado])
        elif lado in ja_escritos:
            lados[lado] = getattr(antes, lado)
    novos = TriggersConfig(**lados, **_a_intensidade_que_fica(antes))
    if (antes is not None and antes == novos
            and antes.model_fields_set == novos.model_fields_set):
        return None
    atuais[chave] = dele.model_copy(update={"triggers": novos})
    return prof.model_copy(update={"controllers": atuais})


#: A «Intensidade do gatilho» (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-
#: 01): o trilho de 0 a 200%, de 5 em 5, por controle (`aba03.GESTO_DA_INTENSIDADE`).
GESTO_DA_INTENSIDADE = "intensidade-do-gatilho"
CAMPO_DA_INTENSIDADE = "intensidade-do-gatilho"
TETO_DA_INTENSIDADE = 200
#: O cartão do padrão do computador em que a intensidade mora, como a «Força da vibração» da 05
#: (A-INTENSIDADE-DO-GATILHO-VALE-NO-PADRAO-DO-COMPUTADOR-01).
CARTAO_DA_INTENSIDADE = "gatilho"


def _intensidade_no_perfil(p: dict[str, Any] | None, uniq: str) -> int:
    """A intensidade daquele controle em porcento, lida do perfil; sem escolha, 100."""
    alvo = _chave_no_perfil(uniq)
    controles = (p or {}).get("controllers")
    for chave, dele in (controles.items() if isinstance(controles, dict) else ()):
        if not alvo or _chave_no_perfil(str(chave)) != alvo or not isinstance(dele, dict):
            continue
        seus = dele.get("triggers")
        escala = seus.get("intensidade") if isinstance(seus, dict) else None
        if isinstance(escala, (int, float)):
            return round(float(escala) * 100)
    return 100


def _intensidade_da_coluna(p: dict[str, Any] | None, uniq: str) -> dict[str, Any]:
    """Os dois campos do trilho de uma coluna viva: o cursor e o número ao lado.

    O lugar vazio fica como o gerador o desenha (cursor no zero, travessão no número): a coluna
    vazia só recebe `<select>` e a força (`test_o_lugar_vazio_recebe_desligado_e_nenhum`).
    """
    pct = _intensidade_no_perfil(p, uniq)
    return {CAMPO_DA_INTENSIDADE: pct, f"{CAMPO_DA_INTENSIDADE}-pct": pct}


def _a_intensidade_que_fica(antes: Any) -> dict[str, Any]:
    """A intensidade já escrita, para o efeito novo não a apagar ao trocar o `TriggersConfig`."""
    escala = getattr(antes, "intensidade", None)
    return {} if escala is None else {"intensidade": escala}


def _com_a_intensidade(prof: Any, uniq: str, pontos: int, *, cem_por_cima: bool = False) -> Any:
    """O perfil com a intensidade DESTE controle trocada, ou `None` se nada mudou.

    100% não vira opinião (`None`): é o que o firmware faz sem o byte, e o dump do controle fica o
    de antes. A exceção é `cem_por_cima`: o jogo que volta a 100% por cima de outra intensidade do
    computador grava o 1,0, porque sem ele a do computador voltaria a valer. O efeito dos dois
    lados não muda: o trilho multiplica o que o estilo e o jogo escolheram, e a chave é o `uniq`
    normalizado, como em :func:`_com_os_gatilhos`.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, TriggersConfig

    chave = uniq.replace(":", "").lower()
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.triggers
    escala = None if pontos == 100 and not cem_por_cima else pontos / 100
    if (antes.intensidade if antes is not None else None) == escala:
        return None
    if antes is None:
        novos = TriggersConfig.model_validate({"intensidade": escala})
    else:
        novos = antes.model_copy(update={"intensidade": escala})
    atuais[chave] = dele.model_copy(update={"triggers": novos})
    return prof.model_copy(update={"controllers": atuais})


def _cem_por_cima(nome: str, uniq: str) -> bool:
    """O jogo ativo grava por cima de uma intensidade do computador diferente de 100%?"""
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    loader = perfil._com_o_src()
    cru = loader.load_profile(nome) if nome else None
    if opc.onde_grava(CARTAO_DA_INTENSIDADE, cru) != opc.JOGO:
        return False
    dele = opc.o_computador().controles.get(opc.chave(uniq) or "")
    escala = dele.triggers.intensidade if dele is not None and dele.triggers is not None else None
    return escala is not None and escala != 1.0


@gesto("03-gatilhos.html", GESTO_DA_INTENSIDADE, grava="gravar_pelo_gesto")
def intensidade_do_gatilho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O trilho «Intensidade do gatilho» de UM controle: 0 a 200%, e grava na hora.

    Grava só `controllers[uniq].triggers.intensidade` (0 a 2) pelo `gravar_pelo_gesto`, como a
    «Força da vibração» da 05: com um jogo, no perfil dele; sem jogo, no padrão do computador.
    O `ProfileManager` a publica (`set_trigger_scales`) lida do perfil com o computador por baixo,
    e ela multiplica também o efeito do Modo automático. O segundo evento do mesmo arrasto
    (`change` e `click`) acha o número já gravado e não grava.
    """
    uniq = _exigir_controle(o, "intensidade do gatilho")
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError("Arraste o cursor da barra, em vez de clicar no número ao lado.")
    try:
        pontos = round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número de porcentagem") from erro
    if not 0 <= pontos <= TETO_DA_INTENSIDADE:
        raise RuntimeError(
            f"a intensidade vai de 0 a {TETO_DA_INTENSIDADE}%, e a barra mandou {pontos}%.")
    nome = perfil.nome_do_ativo(ctx.state).strip()
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    if not _chave_no_perfil(uniq):
        raise RuntimeError(
            "este controle não tem um endereço fixo, e sem ele a intensidade cairia em outro "
            "aparelho amanhã.")
    por_cima = _cem_por_cima(nome, uniq)
    _onde, novo = gravar_pelo_gesto(
        CARTAO_DA_INTENSIDADE, nome,
        lambda vista: _com_a_intensidade(vista, uniq, pontos, cem_por_cima=por_cima),
        uniq=_chave_no_perfil(uniq), origem="interface-nova")
    if novo is not None:
        perfil.reaplicar(nome, ctx, p)


PONTE = {"trigger_set_detalhado", "trigger_reset_detalhado"}
#: Vazio: os dois métodos que esta aba usa (`trigger.set` e `trigger.reset`) têm
METODOS: set[str] = set()


#: Os seis gestos da aba do todo: `modo`, `imersao`, `criar-efeito`, `sentir`, o par
#: «Modo automático | Modo personalizado» (`GESTO_DO_MODO`) e o trilho da intensidade.
PISO_DA_ABA = 6
_UNIQ = "aa:bb:cc:00:00:01"
_GUARDOU: tuple[str, list[str], dict[str, Any]] = (
    "chamar", ["launch_env.refresh"], {})

_IMERSAO_DE_PROVA = _imersoes().imersoes_do_acionamento("Machine")[0]


def _forma_de_prova(sigla: str, modo_: str) -> dict[str, str]:
    """A coluna que o piloto recolheria, montada pelo endereço que a pintura usa."""
    return {f"modo-chave-{sigla}": modo_}


PROVAS = [
    # calados no dia em que ela mudasse um padrão — e a régua daria verde sobre
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "e",  # (noqa-acento) id
     "modo": "Rigid"},
     "chama": [("trigger_set_detalhado", ["left", "Rigid", _padroes("Rigid")],
                {"uniq": _UNIQ}), _GUARDOU]},
    # "Desligado" é `trigger.reset` — a R-19. Se alguém trocar por um
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "d", "modo": "Off"},  # (noqa-acento) id
     "chama": [("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ}), _GUARDOU]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "modo", "clique": {"lado": "e", "valor": "Vibration"},
     "chama": [("trigger_set_detalhado", ["left", "Vibration", _padroes("Vibration")],
                {"uniq": _UNIQ}), _GUARDOU]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "imersao", "clique": {"lado": "e", "valor": _IMERSAO_DE_PROVA.chave,
                                    "forma": _forma_de_prova("e", "Machine")},
     "chama": [("trigger_set_detalhado",
                ["left", "Machine", _params_da_imersao(_IMERSAO_DE_PROVA, "Machine", "")],
                {"uniq": _UNIQ}), _GUARDOU]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     # «Sem efeito» solta o gatilho, qualquer que seja o acionamento da coluna (20/10/2026)
     "gesto": "imersao", "clique": {"lado": "d", "valor": SEM_IMERSAO,
                                    "forma": _forma_de_prova("d", "Machine")},
     "chama": [("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ}), _GUARDOU]},
]

#: OS GESTOS QUE O DAEMON ACEITA E NÃO PUBLICA. O `state_full` não traz
#: `triggers`: o DualSense não devolve o modo em que está — gatilho adaptativo é
SEM_ECO = ("modo", "imersao")
