"""A bancada fala a tela de hoje — A-BANCADA-DELTA-6A, 24/09/2026."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec

_RAIZ = Path(__file__).resolve().parents[2]
_INTERFACE = _RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
_PAGINAS = _INTERFACE / "paginas"  # noqa-acento: nome de PASTA; caminho não leva acento
_GESTOS = (
    _RAIZ / "docs/method/2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md",
    _RAIZ / "docs/method/2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md",
)

if str(_INTERFACE) not in sys.path:
    sys.path.insert(0, str(_INTERFACE))


def _secoes() -> dict[str, str]:
    """`{cabeçalho: corpo}` das seções `## ` dos dois arquivos do gesto."""
    fora: dict[str, str] = {}
    for arquivo in _GESTOS:
        atual = ""
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.startswith("## ") or linha.startswith("# "):
                atual = linha[3:].strip() if linha.startswith("## ") else ""
                if atual:
                    fora[atual] = ""
                continue
            if atual:
                fora[atual] += linha + "\n"
    assert len(fora) > 180, f"os arquivos do gesto publicaram {len(fora)} seções — régua cega"
    return fora


def _campo(corpo: str, rotulo: str) -> str:
    """O texto de um campo do molde (`**Os passos.**`…) até o campo seguinte."""
    m = re.search(rf"\*\*{re.escape(rotulo)}\*\*(.*?)(?=\n\*\*[A-Z][^*]*\.\*\*|\Z)", corpo, re.S)
    return m.group(1) if m else ""


def _frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?])\s+|\n", texto) if f.strip()]


def _citados(texto: str) -> list[str]:
    return re.findall(r"«([^»]+)»", texto)


def _texto_visivel(pagina: str) -> str:
    corpo = (_PAGINAS / pagina).read_text(encoding="utf-8")
    corpo = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", " ", corpo, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "\n", corpo))


def test_quem_manda_nao_clicar_nos_botoes_do_cartao_nomeia_todos() -> None:
    """O aviso «não clique nos botões do alto do cartão» nomeia TODOS os botões."""
    pagina = (_PAGINAS / "02-controles.html").read_text(encoding="utf-8")
    botoes = sorted(set(re.findall(
        r'<button class="sw[^"]*" data-gesto="(?:sensor|mira)"[^>]*>'
        r'<span class="p"></span>([^<]+)</button>', pagina)))
    assert len(botoes) >= 3, f"a régua achou {botoes} no alto do cartão — cega"

    faltam = []
    for titulo, corpo in _secoes().items():
        for frase in _frases(corpo):
            if not re.search(r"(?i)\bn[ãa]o clique", frase):
                continue
            citados = [b for b in botoes if f"«{b}»" in frase]
            if len(citados) >= 2 and len(citados) < len(botoes):
                faltam.append((titulo.split(" — ")[0], sorted(set(botoes) - set(citados))))
    assert not faltam, (
        f"{len(faltam)} avisos de «não clique» esquecem botões do cartão: {faltam}")


def test_as_dicas_do_giroscopio_citadas_sao_as_do_pacote() -> None:
    """A dica do «Giroscópio» que a bancada cita é a que o pacote pinta."""
    import pacotes.a02_controles as a02

    donos = {
        "Ligado: o jogo recebe o giro": {a02.DICA_DO_GIRO},
        "Com a Mira Virtual acesa": {a02.DICA_DO_GIRO_COM_A_MIRA,
                                     a02.DICA_DO_GIRO_NO_ESQUERDO,
                                     a02.DICA_DO_GIRO_NO_CURSOR},
    }
    vistas = {inicio: 0 for inicio in donos}
    erradas = []
    for titulo, corpo in _secoes().items():
        for citado in _citados(corpo):
            for inicio, dono in donos.items():
                if citado.startswith(inicio):
                    vistas[inicio] += 1
                    if citado not in dono:
                        erradas.append((titulo.split(" — ")[0], citado))
    assert not erradas, f"dicas citadas que não são as do pacote: {erradas}"
    assert vistas["Com a Mira Virtual acesa"] >= 2, (
        "nenhuma célula confere a dica que muda com a Mira acesa — no cabo e no "
        f"rádio, ela tem de aparecer pelo menos duas vezes: {vistas}")


def test_os_ajustes_da_mira_citados_existem_na_calibrar() -> None:
    """O que a bancada diz morar no bloco «Mira Virtual» mora na Calibrar publicada."""
    tela = _texto_visivel("calibrar-sensores.html")
    frases_do_bloco = 0
    ausentes = []
    for titulo, corpo in _secoes().items():
        for frase in _frases(corpo):
            if "bloco «Mira Virtual»" not in frase:
                continue
            frases_do_bloco += 1
            for citado in _citados(frase):
                if citado not in tela:
                    ausentes.append((titulo.split(" — ")[0], citado))
    assert frases_do_bloco >= 2, "nenhuma célula fala do bloco da Mira na Calibrar — régua cega"
    assert not ausentes, f"rótulos que a Calibrar publicada não tem: {ausentes}"


def test_o_desligado_nao_tira_mais_o_hefesto_das_lampadas() -> None:
    """O teste que promete o Linux sozinho para o serviço, e não usa o Nativo."""
    assert "player_leds" in bp._CAMPOS_QUE_O_NATIVO_ESCREVE, (
        "o Modo Nativo deixou de escrever o número do jogador — a premissa desta "
        "régua caiu, e os gestos do padrão do driver podem voltar ao «Desligado»")

    fora_do_meio = 0
    erradas = []
    for titulo, corpo in _secoes().items():
        prova = _campo(corpo, "O que isto prova.")
        if "com o Hefesto fora do meio" not in prova or "lâmpadas" not in prova:
            continue
        fora_do_meio += 1
        passos = _campo(corpo, "Os passos.")
        if ("«Parar o serviço»" not in passos or "«Ativar o serviço»" not in passos
                or "«Desligado»" in passos):
            erradas.append(titulo.split(" — ")[0])
    assert fora_do_meio >= 2, "nenhuma célula promete o Linux sozinho — régua cega"
    assert not erradas, (
        f"células que prometem o Hefesto fora do meio sem parar o serviço: {erradas}")


_MAC = "AA:BB:CC:00:00:01"
_UNIQ = "aabbcc000001"
_AMARELO = (255, 255, 0)
_COR_DO_JOGO = (200, 60, 0)


class _NoDeLed:
    """Nó sysfs de mentira — grava as chamadas, nunca toca o disco."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        return True

    def invalidate_cache(self) -> None:
        return None


def _controle_com_o_jogo() -> bp.PyDualSenseController:
    """Um controle de verdade do backend, com o jogo na autoridade e o nó de mentira."""
    ctl = bp.PyDualSenseController()
    ctl._handles = {_MAC: SimpleNamespace(
        triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None)}
    ctl._sysfs = {_MAC: _NoDeLed()}
    ctl.set_game_authority_provider(lambda: "game")
    return ctl


def _replicas() -> dict[str, str]:
    replicas = {t: c for t, c in _secoes().items() if t.startswith("mapa-luz.replica_output_jogo-")}
    assert len(replicas) == 2, f"as duas células da réplica sumiram: {sorted(replicas)}"
    return replicas


def test_o_perfil_novo_ativado_a_mao_devolve_a_barra_ao_jogo() -> None:
    """O gesto novo da réplica PODE passar — pela ativação de verdade."""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    ctl = _controle_com_o_jogo()
    ctl.apply_output_for(_UNIQ, OutputSpec(led=_AMARELO))
    ProfileManager(controller=ctl).apply(
        Profile(name="Teste da réplica", match=MatchAny(), priority=11),
        origin="manual")
    ctl.set_game_output_for(_MAC, led=_COR_DO_JOGO)
    with ctl._io_lock:
        assert ctl._merged_desired_for_key(_MAC).led == _COR_DO_JOGO, (
            "o perfil novo ativado à mão não devolveu a barra ao jogo — a premissa "
            "do gesto da réplica caiu")

    erradas = []
    for titulo, corpo in _replicas().items():
        antes = _campo(corpo, "Os passos.").split("Abra o jogo", 1)[0]
        depois_do_novo = antes.split("«Novo»", 1)[-1]
        if "«Novo»" not in antes or "«Ativar»" not in depois_do_novo:
            erradas.append(titulo.split(" — ")[0])
    assert not erradas, f"réplicas que não ativam o perfil novo antes do jogo: {erradas}"


def test_a_replica_termina_apagando_o_perfil_novo_de_verdade() -> None:
    """O «Remover» pergunta antes, e o gesto manda dar o segundo clique.

    O perfil do «Novo» vale para tudo e nasce ACIMA dos que valem sempre
    (`_prioridade_acima_dos_catch_all`): esquecido no disco, ele passa a valer
    no lugar do perfil do usuário em toda janela sem jogo. O primeiro clique no
    «Remover» só ARMA; quem apaga é o segundo, dentro do prazo do dono
    (`a10_perfis.SEGUNDOS_PARA_CONFIRMAR`).

    MORDIDA: tire o «clique nele de novo» do último passo e a régua reprova.
    """
    import pacotes.a10_perfis as a10

    assert a10.SEGUNDOS_PARA_CONFIRMAR > 0, (
        "o «Remover» deixou de perguntar — a premissa desta régua caiu")
    erradas = []
    for titulo, corpo in _replicas().items():
        passos = [p for p in _campo(corpo, "Os passos.").splitlines() if p.strip()]
        ultimo = passos[-1] if passos else ""
        if "«Remover»" not in ultimo or "de novo" not in ultimo:
            erradas.append(titulo.split(" — ")[0])
    assert not erradas, f"réplicas que deixam o perfil novo no disco: {erradas}"


def test_a_replica_nao_escolhe_antes_a_cor_do_controle_que_mede() -> None:
    """A réplica da cor do jogo se mede num controle cuja cor ninguém escolheu."""
    ctl = _controle_com_o_jogo()
    ctl.apply_output_for(_UNIQ, OutputSpec(led=_AMARELO))
    ctl.set_game_output_for(_MAC, led=_COR_DO_JOGO)
    with ctl._io_lock:
        # Desde 03/10/2026 o jogo manda e o que foi clicado ANTES cede (a decisão
        # dela que revoga a PERFIL-MANDA-01): a réplica que começa sem cor escolhida
        # segue medindo só a cor do jogo.
        assert ctl._merged_desired_for_key(_MAC).led == _COR_DO_JOGO, (
            "a cor clicada antes do jogo venceu a do jogo — o jogo deixou de mandar")

    erradas = []
    for titulo, corpo in _replicas().items():
        passos = _campo(corpo, "Os passos.")
        antes = passos.split("Abra o jogo", 1)[0]
        if "Abra o jogo" not in passos or "quadradinho" in antes or "«Novo»" not in antes:
            erradas.append(titulo.split(" — ")[0])
    assert not erradas, (
        f"réplicas que escolhem a cor antes do jogo, ou sem o perfil novo: {erradas}")
