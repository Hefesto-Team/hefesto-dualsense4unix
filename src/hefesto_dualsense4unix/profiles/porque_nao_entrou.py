"""Por que o perfil DAQUELE jogo não entrou — a pergunta que ninguém respondia.

O QUE ISTO CURA (PERFIL-MUDO-01, 10/08/2026)
--------------------------------------------
Ela abriu o Pragmata para testar o touchpad e o giroscópio, e o controle veio
duplicado. O perfil ``Pragmata`` estava no disco, com o appid certo, e **não
entrou**. O daemon sabia — logou ``profile_select_catch_all_sem_autoridade_em_jogo
candidatos=['fallback'] wm_class=steam_app_3357650``, quatro vezes — e a janela
não disse **nada**. O journal não é interface.

O tamanho disso foi MEDIDO na máquina dela, em 30 dias de journal:

- perfis que o autoswitch já elegeu sozinho: ``Sackboy``, ``Big Walk``,
  ``Dont Scream``, ``Navegação``, ``sackboy_nativo`` — **todos** identificados
  por ``window_class``, nenhum com ``process_name``;
- ``Pragmata`` só aparece com ``origin=manual`` — **nunca** por autoswitch;
- os cinco perfis dela que só têm ``process_name`` (``Ação``, ``Aventura``,
  ``Corrida``, ``Esportes``, ``FPS``) **nunca apareceram, nenhuma vez**.

Reproduzido fora do journal, com os perfis dela e o mesmo código: com
``wm_class=steam_app_3357650`` os candidatos são ``['fallback']``; tirando **só**
o ``PRAGMATA.exe`` do critério, viram ``['fallback', 'Pragmata']``. Um campo
separa o perfil do jogo dele.

O QUE ESTE MÓDULO **NÃO** FAZ
-----------------------------
Não corrige o perfil dela, não sugere apagar campo nenhum e não teoriza sobre o
Proton. *"A vontade na GUI prevalece sempre"* — quem escreveu o critério foi ela,
e a decisão de mudá-lo é dela. O que faltava não era decisão: era **informação**.

Por isso as frases daqui são estritamente factuais — dizem o que o perfil EXIGIU
e o que o Hefesto VIU, lado a lado, sem nomear culpado:

    O seu perfil "Pragmata" é deste jogo, mas não entrou.
    Ele exige nome do processo "PRAGMATA.exe"; aqui o Hefesto vê "wine64-preloader".

Com isso ela decide vendo, que é como ela decide.

POR QUE UM MÓDULO PRÓPRIO, E NÃO UM RAMO DENTRO DO ``matches``
--------------------------------------------------------------
``MatchCriteria.matches`` responde SIM/NÃO e é chamado a 0,5 Hz para cada perfil
do disco; ele não pode virar um coletor de diagnóstico. Aqui a pergunta é outra e
o custo é pago só quando alguém pergunta: a janela, ao desenhar a aba, e o
doctor. Funções puras, sem I/O e sem GTK — a única entrada é o ``window_info`` que
o detector já produz e a lista de perfis que o loader já carregou.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

__all__ = [
    "CampoReprovado",
    "PerfilQueNaoEntrou",
    "campos_reprovados",
    "frase_do_perfil_que_nao_entrou",
    "perfis_que_nao_entraram",
]

#: Rótulos dos campos do critério — os MESMOS nomes que o editor avançado da aba
#: Perfis mostra na tela. Se ela vir "nome do processo" na frase e o campo se
#: chamar outra coisa no editor, a frase manda ela procurar o que não existe.
_ROTULO_DO_CAMPO = {
    "window_class": "classe da janela",
    "window_title_regex": "título da janela",
    "process_name": "nome do processo",
}

#: De onde sai o valor observado de cada campo, dentro do ``window_info``.
_CHAVE_OBSERVADA = {
    "window_class": "wm_class",
    "window_title_regex": "wm_name",
    "process_name": "exe_basename",
}


@dataclass(frozen=True)
class CampoReprovado:
    """Um critério que o perfil exigiu e a janela em foco não satisfez."""

    campo: str
    exigido: list[str]
    observado: str

    @property
    def rotulo(self) -> str:
        return _ROTULO_DO_CAMPO.get(self.campo, self.campo)


@dataclass(frozen=True)
class PerfilQueNaoEntrou:
    """Um perfil que reprovou, e por quais campos.

    ``e_regra_deste_jogo`` separa os dois casos que NÃO podem virar o mesmo
    aviso. Um perfil de FPS genérico que não casou com o jogo dela é o
    funcionamento normal — dizer isso a cada troca de janela seria ruído. Já um
    perfil cuja ``window_class`` nomeia ESTE appid é uma promessa quebrada: ela
    escreveu "este perfil é deste jogo" e o jogo abriu sem ele.
    """

    nome: str
    reprovados: list[CampoReprovado]
    e_regra_deste_jogo: bool


def _observado(window_info: dict[str, Any], campo: str) -> str:
    valor = window_info.get(_CHAVE_OBSERVADA[campo])
    return valor if isinstance(valor, str) else ""


def campos_reprovados(
    match: MatchCriteria, window_info: dict[str, Any]
) -> list[CampoReprovado]:
    """Quais campos preenchidos do critério NÃO casaram com esta janela.

    Espelha `MatchCriteria.matches` condição a condição, e essa duplicação é
    deliberada e barata: são três `if` idênticos aos de lá. A alternativa —
    fazer o `matches` devolver os detalhes — encareceria o caminho quente, que
    roda para cada perfil do disco a cada tique do autoswitch.

    O par (exigido, observado) sai daqui já pronto para a frase: sem ele, o
    aviso viraria "não casou", que é exatamente o que a janela já não dizia.
    """
    reprovados: list[CampoReprovado] = []
    for campo in ("window_class", "window_title_regex", "process_name"):
        exigido = getattr(match, campo, None)
        if not exigido:
            continue
        lista = [exigido] if isinstance(exigido, str) else list(exigido)
        # Reusa o veredito do PRÓPRIO matcher, campo a campo: um critério com
        # só este campo preenchido responde exatamente pela condição dele. Assim
        # a caixa (R-12), o `re.search` do título e o "alvo vazio nunca casa"
        # continuam decididos num lugar só, e este módulo nunca diverge dele.
        so_este_campo = MatchCriteria(**{campo: exigido})
        if not so_este_campo.matches(window_info):
            reprovados.append(
                CampoReprovado(
                    campo=campo,
                    exigido=lista,
                    observado=_observado(window_info, campo),
                )
            )
    return reprovados


def perfis_que_nao_entraram(
    window_info: dict[str, Any], perfis: list[Profile]
) -> list[PerfilQueNaoEntrou]:
    """Os perfis que reprovaram nesta janela, com o motivo de cada um.

    Fora da conta, de propósito:

    - **perfis que CASARAM** — não há o que explicar;
    - **catch-all e ``MatchManual``** — o primeiro casa com tudo, e o segundo
      nunca casa POR ESCOLHA dela (é o "só entra quando eu mandar"). Chamar
      isso de falha seria transformar uma decisão dela em defeito nosso.

    A ordem coloca as regras DESTE jogo na frente: é a única classe que a janela
    mostra sem ela pedir, e a ordem é o que a torna previsível quando há duas.
    """
    appid_em_foco = steam_appid_from_wm_class(str(window_info.get("wm_class") or ""))
    achados: list[PerfilQueNaoEntrou] = []
    for perfil in perfis:
        match = getattr(perfil, "match", None)
        if not isinstance(match, MatchCriteria):
            continue
        if match.matches(dict(window_info)):
            continue
        reprovados = campos_reprovados(match, window_info)
        # Aqui morava um `if perfil.e_catch_all: continue`, e ele foi RETIRADO
        # por ser inalcançável: um `MatchCriteria` catch-all é, por definição, o
        # que não tem nenhum dos três campos preenchidos — e esse não produz
        # reprovado nenhum, então a linha abaixo já o descarta. `MatchAny` e
        # `MatchManual` saem antes, no `isinstance`. Um `continue` que nunca
        # executa não é cinto: é a aparência de um, e o teste que tentava
        # mordê-lo passava com ele arrancado.
        if not reprovados:
            continue
        e_deste_jogo = appid_em_foco is not None and any(
            steam_appid_from_wm_class(classe) == appid_em_foco
            for classe in match.window_class
        )
        achados.append(
            PerfilQueNaoEntrou(
                nome=str(getattr(perfil, "name", "") or ""),
                reprovados=reprovados,
                e_regra_deste_jogo=e_deste_jogo,
            )
        )
    achados.sort(key=lambda a: (not a.e_regra_deste_jogo, a.nome))
    return achados


def _lista_humana(valores: list[str]) -> str:
    aspas = [f'"{v}"' for v in valores]
    if len(aspas) == 1:
        return aspas[0]
    if len(aspas) == 2:
        return f"{aspas[0]} ou {aspas[1]}"
    return f"{', '.join(aspas[:-1])} ou {aspas[-1]}"


def frase_do_perfil_que_nao_entrou(achado: PerfilQueNaoEntrou) -> str:
    """A frase que a janela mostra. Factual: o exigido e o observado, lado a lado.

    Nunca manda apagar campo, nunca chama a configuração dela de errada e nunca
    fala em Proton — o Hefesto não mediu o que o Proton faz, e afirmar mecanismo
    sem medida é a família de erro que esta casa mais pagou caro.

    Quando o Hefesto não viu NADA no campo (``exe_basename`` vazio, que é o que
    os dois backends de Wayland sempre devolvem), a frase diz isso com todas as
    letras em vez de mostrar um par de aspas vazias: "não vê nome de processo
    nesta janela" é informação; ``""`` é enigma.
    """
    partes: list[str] = []
    for r in achado.reprovados:
        if r.observado:
            partes.append(f"exige {r.rotulo} {_lista_humana(r.exigido)}, e aqui vê ")
            partes.append(f'"{r.observado}"')
        else:
            partes.append(
                f"exige {r.rotulo} {_lista_humana(r.exigido)}, "
                f"e aqui não vê {r.rotulo} nesta janela"
            )
        partes.append("; ")
    motivo = "".join(partes).rstrip("; ")
    if achado.e_regra_deste_jogo:
        return (
            f'O seu perfil "{achado.nome}" é deste jogo, mas não entrou: '
            f"ele {motivo}."
        )
    return f'O perfil "{achado.nome}" não entrou: ele {motivo}.'
