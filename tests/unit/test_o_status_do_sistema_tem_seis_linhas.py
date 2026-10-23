"""O Status da aba Sistema tem seis linhas, sempre.

Sprint O-STATUS-DO-SISTEMA-TEM-SEIS-LINHAS-SEMPRE-01. Medido na foto de 22/10/2026, 20:22 (P1 pelo
BT, um jogo cujo Steam Input mudou): sete linhas, porque `_so_o_que_a_tela_mostra` punha depois dos
seis temas «qualquer outra linha que peça ação», e o aviso do prontuário abria uma sétima. A cura:
seis temas fixos (`a09_sistema.TEMAS`), e todo aviso entra na linha do tema dele.

MORDIDAS (executadas em 22/10/2026, cada uma vista reprovar e devolvida):

* o acréscimo das linhas «que pedem ação» de volta no fim: os cenários com aviso dão sete;
* o prontuário sem tema em `_achados`: o aviso do Steam Input cai na linha do Serviço;
* uma fonte nova da coluna de atenção sem tema: `test_toda_fonte_que_chega_ao_status_tem_tema`;
* o corte da cabeça «título: explicação» arrancado de `_cabeca_e_destino`: o aviso do modo volta a
  ocupar a linha inteira, quebrando em duas, e `test_o_aviso_de_titulo_e_explicacao_fica_curto`
  reprova.
"""

from __future__ import annotations

import ast
import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions, home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import sistema as tela
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "09-sistema.html"
PACOTES = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes"

BEM = [("[OK]", "cura do travamento do USB ativa"),
       ("[OK]", "áudio presente nos controles no cabo"),
       ("[OK]", "quirk anti-storm ativo (054c:0ce6)"),
       ("[OK]", "Steam Input desligado (com exceções: 1 jogo)"),
       ("[OK]", "WirePlumber configurado"),
       ("[OK]", "regra áudio-off inativa")]
SEM_CABO = ("[INFO]", "nenhum controle no cabo")


def _estado(cabo: int = 0, radio: int = 0, vpads: int | None = None) -> dict[str, Any]:
    controles = ([{"connected": True, "transport": "usb"} for _ in range(cabo)]
                 + [{"connected": True, "transport": "bt"} for _ in range(radio)])
    return {"controllers": controles,
            "rumble_ff": {"vpads": cabo + radio if vpads is None else vpads},
            "native_mode": False, "gamepad_emulation": {"enabled": True}}


def _prontuario() -> tuple[str, str] | None:
    censo = type("Censo", (), {"jogos": [type("J", (), {"nome": "Mullet Mad Jack",
                                                       "ponte_divergente": True})()]})()
    return daemon_actions.interpretar_prontuario_dos_jogos(censo)


def _seis(monkeypatch: pytest.MonkeyPatch, state: dict[str, Any] | None,
          storm: list[tuple[str, str]] | None, *, prontuario: bool = False,
          som: tuple[str, str] | None = None, servico: str = "online_systemd",
          avisos: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """O caminho do produto: `_achados`, `_com_os_avisos` e `_so_o_que_a_tela_mostra`."""
    if storm is None:
        def _cai(**_k: Any) -> list[tuple[str, str]]:
            raise OSError("o exame caiu")
        monkeypatch.setattr(a09._exame, "storm_report", _cai)
    else:
        monkeypatch.setattr(a09._exame, "storm_report", lambda **_k: list(storm))
    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input", lambda: None)
    monkeypatch.setattr(a09, "_prontuario",
                        lambda *_a: _prontuario() if prontuario else None)
    monkeypatch.setattr(a09, "linha_do_som_do_sistema", lambda _s: som)
    monkeypatch.setattr(a09, "linha_da_sobreposicao_vulkan", lambda: None)
    monkeypatch.setattr(a09, "linhas_dos_perfis", lambda *_a: [])
    monkeypatch.setattr(a01_jogar, "coluna_de_atencao", lambda _c: list(avisos or []))
    exame = tela.exame(a09._achados(state))
    status = [tela.status_do_servico(servico, state), tela.status_da_troca(state),
              tela.status_do_bluetooth(1, state)]
    ctx = Contexto(state=state or {}, mesa=[], conectados=[], estados={})
    return list(a09._so_o_que_a_tela_mostra(a09._com_os_avisos(exame, ctx), status,
                                            state)["linhas"])


def _contadas(linhas: list[dict[str, Any]]) -> list[str]:
    """Os temas das linhas, contados no HTML que o pacote escreve."""
    um, resto = a09._notas_em_tercos(linhas[:2], linhas[2:])
    return re.findall(r'class="saude[^"]*"[^>]*data-tema="([^"]+)"', um + resto)


CENARIOS = {
    "daemon-fora": dict(state=None, storm=BEM, servico="offline"),
    "nenhum-controle": dict(state=_estado(), storm=[*BEM[:1], SEM_CABO, *BEM[2:]]),
    "um-no-cabo": dict(state=_estado(cabo=1), storm=BEM),
    "dois-no-cabo": dict(state=_estado(cabo=2), storm=BEM),
    "quatro-no-cabo": dict(state=_estado(cabo=4), storm=BEM),
    "um-no-radio": dict(state=_estado(radio=1), storm=[*BEM[:1], SEM_CABO, *BEM[2:]]),
    "dois-no-radio": dict(state=_estado(radio=2), storm=[*BEM[:1], SEM_CABO, *BEM[2:]]),
    "quatro-no-radio": dict(state=_estado(radio=4), storm=[*BEM[:1], SEM_CABO, *BEM[2:]]),
    "misturados": dict(state=_estado(cabo=2, radio=2), storm=BEM),
    "aviso-do-steam-input": dict(state=_estado(radio=1), prontuario=True,
                                 storm=[*BEM[:1], SEM_CABO, *BEM[2:]]),
    "aviso-do-som": dict(state=_estado(cabo=2), som=("[WARN]", "o som do sistema caiu"),
                         storm=[*BEM[:1], ("[WARN]", "áudio ausente em 1 dos 2 controles"),
                                *BEM[2:]]),
    "falha-do-gamepad": dict(state=_estado(cabo=2, vpads=0), storm=BEM),
    "conexao-nativa": dict(state={**_estado(radio=1), "native_mode": True},
                           storm=[*BEM[:1], SEM_CABO, *BEM[2:]]),
    "emulacao-desligada": dict(state={**_estado(cabo=1, radio=1),
                                      "gamepad_emulation": {"enabled": False}}, storm=BEM),
    "aviso-do-modo": dict(
        state=_estado(radio=1), storm=[*BEM[:1], SEM_CABO, *BEM[2:]],
        avisos=[{"selo": "MODO", "texto": home_actions.TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO,
                 "fonte": "home_actions.texto_do_desktop_sem_emulacao"}]),
    "exame-caiu": dict(state=_estado(cabo=1), storm=None),
    "avisos-de-todo-tema": dict(
        state=_estado(cabo=1, radio=1), prontuario=True, storm=[
            ("[WARN]", "a cura do travamento do USB não está posta"), *BEM[1:4],
            ("[FAIL]", "o WirePlumber não carregou"), BEM[5]],
        avisos=[{"selo": "GAMEPAD", "texto": "um aviso do gamepad",
                 "fonte": "home_actions.vpad_degradation_text"},
                {"selo": "RÁDIO", "texto": "o rádio está frágil",
                 "fonte": "home_actions.texto_do_radio_fragil"},
                {"selo": "JOGO", "texto": "uma fonte sem dono", "fonte": "fonte.nova"}]),
}


@pytest.mark.parametrize("nome", list(CENARIOS))
def test_sao_seis_linhas_uma_por_tema(monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    """Prova da D-2210-O-STATUS-DO-SISTEMA-TEM-SEIS-LINHAS."""
    linhas = _seis(monkeypatch, **CENARIOS[nome])
    assert _contadas(linhas) == list(a09.TEMAS), [
        (a.get("tema"), a.get("cls"), a.get("txt")) for a in linhas]


def test_o_aviso_do_steam_input_e_a_linha_dele_laranja(monkeypatch: pytest.MonkeyPatch) -> None:
    """A foto: «com exceções» e o aviso que mudou viram UMA linha, laranja, levando à aba Perfis."""
    linhas = _seis(monkeypatch, **CENARIOS["aviso-do-steam-input"])
    steam = linhas[a09.TEMAS.index("steam-input")]
    assert (steam["cls"], steam["txt"]) == ("aviso", "O Steam Input de Mullet Mad Jack mudou")
    assert steam["href"] == "10-perfis.html", steam
    assert "confira o perfil dele na aba Perfis" in steam["dica"], steam["dica"]
    assert "Steam Input desligado, com exceções." in steam["dica"], steam["dica"]
    assert a09._exame.PREFIXO_DA_CURA not in steam["dica"]
    html_ = a09._linha_do_exame(steam)
    assert 'class="saude vai longa"' in html_ and 'href="10-perfis.html"' in html_, html_


def test_o_aviso_de_titulo_e_explicacao_fica_curto(monkeypatch: pytest.MonkeyPatch) -> None:
    """«Título: explicação» põe só o título na linha; a frase inteira vai à dica."""
    gamepad = _seis(monkeypatch, **CENARIOS["aviso-do-modo"])[a09.TEMAS.index("gamepad")]
    assert (gamepad["cls"], gamepad["txt"]) == ("aviso", "Mouse e teclado emulados desligados")
    assert home_actions.TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO.split(". ")[0] in gamepad["dica"]


def test_vence_o_pior_veredito(monkeypatch: pytest.MonkeyPatch) -> None:
    linhas = _seis(monkeypatch, **CENARIOS["avisos-de-todo-tema"])
    por_tema = {a["tema"]: a for a in linhas}
    assert por_tema["audio"]["cls"] == "falha", por_tema["audio"]
    assert "cura do travamento" in por_tema["audio"]["dica"], por_tema["audio"]["dica"]
    gamepad = por_tema["gamepad"]
    assert (gamepad["cls"], gamepad["txt"]) == ("aviso", "Um aviso do gamepad"), gamepad
    assert "Um gamepad virtual por jogador." in gamepad["dica"], gamepad["dica"]
    assert por_tema["bluetooth"]["cls"] == "aviso", por_tema["bluetooth"]
    assert por_tema["serviço"]["cls"] == "aviso", "a fonte sem tema caiu fora das seis"


def test_sem_controle_o_gamepad_diz_nenhum_controle_ligado() -> None:
    linha = a09.linha_do_gamepad_por_jogador(_estado())
    assert (linha["cls"], linha["txt"]) == ("nt", "Nenhum controle ligado"), linha


def test_o_desenho_tem_os_mesmos_seis_temas_na_mesma_ordem() -> None:
    desenho = DESENHO.read_text(encoding="utf-8")
    temas = re.findall(r'class="saude[^"]*"[^>]*data-tema="([^"]+)"', desenho)
    assert temas == list(a09.TEMAS), temas


def _fontes_sem_outra_casa() -> set[str]:
    """As fontes que `a01_jogar._avisos_sem_outra_casa` escreve à mão, lidas no fonte."""
    arvore = ast.parse((PACOTES / "a01_jogar.py").read_text(encoding="utf-8"))
    funcao = next(no for no in ast.walk(arvore)
                  if isinstance(no, ast.FunctionDef) and no.name == "_avisos_sem_outra_casa")
    return {valor.value for no in ast.walk(funcao) if isinstance(no, ast.Dict)
            for chave, valor in zip(no.keys, no.values, strict=True)
            if isinstance(chave, ast.Constant) and chave.value == "fonte"
            and isinstance(valor, ast.Constant)}


def test_toda_fonte_que_chega_ao_status_tem_tema() -> None:
    """Fonte que chega sem tema reprova, e tema de fonte que não existe também."""
    do_painel = {a.nome for a in painel.AVISOS_DA_TELA}
    chegam = ((do_painel | _fontes_sem_outra_casa())
              - set(a01_jogar.FONTES_DO_PAINEL_COM_OUTRA_CASA)
              - set(a09.FONTES_QUE_NAO_PEDEM_ACAO))
    assert chegam - set(a09.TEMA_DA_FONTE) == set(), "fonte sem tema abriria a sétima linha"
    assert set(a09.TEMA_DA_FONTE) - chegam == set(), "tema de fonte que não chega ao Status"
    assert set(a09.TEMA_DA_FONTE.values()) <= set(a09.TEMAS)


def test_todo_achado_do_exame_tem_tema() -> None:
    assert len(a09.TEMA_DO_EXAME) == a09.LINHAS_DO_EXAME_COMPLETO
    assert set(a09.TEMA_DO_EXAME) <= set(a09.TEMAS)
    for tema, posicao in a09.POSICAO_NO_EXAME.items():
        assert a09.TEMA_DO_EXAME[posicao] == tema, (tema, posicao)
    assert set(a09.TEMA_DOS_ACRESCIMOS.values()) <= set(a09.TEMAS)
    fonte = (PACOTES / "a09_sistema.py").read_text(encoding="utf-8")
    achados = next(no for no in ast.walk(ast.parse(fonte))
                   if isinstance(no, ast.FunctionDef) and no.name == "_achados")
    usados = {no.slice.value for no in ast.walk(achados)
              if isinstance(no, ast.Subscript) and isinstance(no.slice, ast.Constant)
              and isinstance(no.value, ast.Name) and no.value.id == "TEMA_DOS_ACRESCIMOS"}
    assert usados == set(a09.TEMA_DOS_ACRESCIMOS), usados
    appends = sum(1 for no in ast.walk(achados) if isinstance(no, ast.Call)
                  and isinstance(no.func, ast.Attribute) and no.func.attr in ("append", "extend"))
    assert appends == len(a09.TEMA_DOS_ACRESCIMOS), "acréscimo novo ao exame sem tema"
