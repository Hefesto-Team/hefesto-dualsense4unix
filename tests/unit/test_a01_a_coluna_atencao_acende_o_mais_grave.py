#!/usr/bin/env python3
"""Os avisos do produto: o mais grave em cima, e a lista do exame da 09 os recebe."""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.home_actions`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.integrations import storm_doctor
from pacotes import Contexto
from pacotes import a01_jogar as aba

VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def _acesas(fora: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    """Os selos e os textos da lista, na ordem em que ela os devolveu."""
    return [a["selo"] for a in fora], [a["texto"] for a in fora]


def _canal(ctx: Contexto) -> list[dict[str, str]]:
    """O CANAL INTEIRO, na ordem da gravidade — com as fontes que têm outra casa."""
    return aba._em_ordem(aba._avisos(ctx))


def _so_estes(monkeypatch: Any, avisos: list[dict[str, str]]) -> None:
    """Cala as outras fontes: a régua mede a ORDEM, não quem fala."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: list(avisos))
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", lambda: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)


QUIRK_DE_PE = "054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m\n"


def _maquina(monkeypatch: Any, quirk_flags: str,
             conf: pathlib.Path) -> tuple[str, str]:
    """Põe a máquina no estado pedido e devolve o que o DONO responde nele."""
    real = storm_doctor.check_snd_quirk
    monkeypatch.setattr(storm_doctor, "check_snd_quirk",
                        lambda *a, **k: real(quirk_flags, conf))
    return real(quirk_flags, conf)


def _so_a_cura(monkeypatch: Any) -> None:
    """Cala TODAS as fontes menos a cura do travamento."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)


def test_o_mais_grave_sobe_e_a_ordem_e_a_da_gravidade(monkeypatch: Any) -> None:
    """A PAUSA vem antes do PERFIL, mesmo chegando depois dele."""
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "cadeado", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "degradado", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert selos == ["GAMEPAD", "RÁDIO", "PERFIL"], (
        f"a coluna não pôs o mais grave em cima: {selos!r}")


def test_a_pausa_vence_tudo_porque_ela_invalida_tudo(monkeypatch: Any) -> None:
    """Com o Hefesto em pausa, nada do resto está acontecendo."""
    _so_estes(monkeypatch, [
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "PAUSA", "texto": "em pausa", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert selos[0] == "PAUSA", f"a pausa não subiu: {selos!r}"


def test_a_ordem_e_estavel_entre_iguais(monkeypatch: Any) -> None:
    """Dois avisos do mesmo selo mantêm a ordem em que as fontes falaram."""
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "primeiro", "fonte": "x"},
        {"selo": "PERFIL", "texto": "segundo", "fonte": "y"},
    ])
    _, textos = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert textos == ["primeiro", "segundo"], (
        f"a ordem entre iguais mudou: {textos!r}")


def test_a_lista_leva_todos_os_avisos(monkeypatch: Any) -> None:
    """Dez avisos, dez linhas: a lista do exame da 09 não tem o teto da coluna.

    A MORDIDA: corte a devolução de `coluna_de_atencao` em três (o teto que a
    coluna da Jogar tinha) e esta régua reprova — sete avisos somem calados.
    """
    _so_estes(monkeypatch, [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                            for i in range(10)])
    _, textos = _acesas(aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO)))
    assert textos == [str(i) for i in range(10)], (
        f"a lista cortou avisos: {textos!r}")


def test_as_fontes_com_outra_casa_nao_vao_a_09(monkeypatch: Any) -> None:
    """O serviço calado, a ponte, a cura do travamento e o exame dos controles"""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: {
        "selo": aba.SELO_DA_PONTE, "texto": "nenhuma — nenhum jogo",
        "fonte": "home_actions.texto_da_ponte"})
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", lambda: {
        "selo": aba.SELO_DA_CURA, "texto": "a cura", "fonte": "storm_doctor.check_snd_quirk"})
    monkeypatch.setattr(aba, "_do_exame", lambda: [
        {"selo": "AVISO", "titulo": "um achado grave", "grave": True}])
    vazio = Contexto(state={}, mesa=[], conectados=[], estados={})

    no_canal = {a["fonte"] for a in aba._avisos(vazio)}
    assert {"storm_doctor.check_snd_quirk", "a08_conexoes._exame",
            "home_actions._render_home (ramo offline)",
            "home_actions.texto_da_ponte"} <= no_canal, (
        f"o canal perdeu uma fonte: {sorted(no_canal)}")
    assert aba.coluna_de_atencao(vazio) == [], (
        "uma fonte que já tem casa na tela foi levada à lista da 09: "
        f"{aba.coluna_de_atencao(vazio)!r}")


def test_o_que_o_status_da_09_ja_diz_nao_se_repete_no_exame() -> None:
    """Pausa, detector cego e Freestyle: no canal, e fora da lista da 09."""
    from hefesto_dualsense4unix.interface import sistema as aba_sistema

    estado = {**VIVO_NAVEGACAO, "paused": True, "freestyle_ligado": True,
              "window_detect_backend": "x11", "window_detect_seeing": False,
              "window_detect_reason": "sem_conexao_x"}
    ctx = _ctx(estado)
    tres = {"home_actions.texto_da_pausa", "home_actions.texto_do_cadeado_cego",
            "home_actions.autoswitch_lock_text"}
    no_canal = {a["fonte"] for a in aba._avisos(ctx)}
    assert tres <= no_canal, f"o canal perdeu uma das três: {sorted(tres - no_canal)}"
    na_09 = {a["fonte"] for a in aba.coluna_de_atencao(ctx)} & tres
    assert not na_09, f"voltou à lista da 09, ao lado da linha que já diz o mesmo: {na_09}"
    assert aba_sistema.status_do_servico("online_systemd", estado)["selo"] == "PAUSADO"
    assert aba_sistema.status_da_troca(estado)["selo"] == "SEM VER"


_EM_MS = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*ms\b")


def _tique_ms() -> float:
    """O tique do piloto, LIDO do fonte — e o import fica de fora de propósito."""
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    achado = re.search(r"^TIQUE_MS\s*=\s*(\d+)", fonte, re.MULTILINE)
    assert achado, "`TIQUE_MS` sumiu de `hefesto_vivo.py` — a régua perdeu o alvo"
    return float(achado.group(1))


def test_o_custo_da_cura_esta_medido_no_docstring() -> None:
    """Quanto custa por tique tem de estar ESCRITO, como a 09 escreveu os dela."""
    doc = aba._aviso_da_cura_do_travamento.__doc__ or ""
    medidos = [float(m.group(1).replace(",", ".")) for m in _EM_MS.finditer(doc)]
    tique = _tique_ms()
    assert medidos, (
        "o docstring de `_aviso_da_cura_do_travamento` não declara quanto ela "
        "custa por tique — a fonte lê dois arquivos do sistema a cada 100 ms")
    assert tique in medidos, (
        f"o docstring não nomeia o tique ({tique:g} ms): um custo sem o teto "
        "ao lado não diz se cabe")
    assert min(medidos) < tique, (
        f"nenhuma medida do docstring é menor que o tique: {medidos!r}")


def test_a_cura_ativa_nao_vira_alarme(monkeypatch: Any, tmp_path: Any) -> None:
    """``[ OK ]`` NÃO entra: boa notícia não é Atenção — e é o estado dela hoje."""
    _so_a_cura(monkeypatch)
    selo, _ = _maquina(monkeypatch, QUIRK_DE_PE, tmp_path / "nao-existe.conf")
    assert selo == storm_doctor.OK, "o estado montado não é o `[ OK ]` do dono"

    assert aba._aviso_da_cura_do_travamento() is None
    fora = _canal(_ctx(VIVO_NAVEGACAO))
    assert fora == [], f"a cura DE PÉ virou aviso: {fora!r}"


def test_a_cura_ausente_chega_a_coluna(monkeypatch: Any, tmp_path: Any) -> None:
    """``[WARN]`` entra, com a frase do dono — palavra por palavra."""
    _so_a_cura(monkeypatch)
    selo, frase = _maquina(monkeypatch, "", tmp_path / "nao-existe.conf")
    assert selo == storm_doctor.WARN, "o estado montado não é o `[WARN]` do dono"

    selos, textos = _acesas(_canal(_ctx(VIVO_NAVEGACAO)))
    assert textos == [frase], (
        f"a frase do dono não chegou inteira ao canal: {textos!r}")
    assert selos == [aba.SELO_DA_CURA], f"o selo não é o da cura: {selos!r}"


def test_a_cura_agendada_tambem_e_trabalho_pendente(
        monkeypatch: Any, tmp_path: Any) -> None:
    """``[INFO]`` entra: *"desconecte e reconecte"* é gesto do usuário, não estado bom."""
    conf = tmp_path / "hefesto-dualsense-storm.conf"
    conf.write_text(f"options snd_usb_audio quirk_flags={QUIRK_DE_PE}",
                    encoding="utf-8")
    _so_a_cura(monkeypatch)
    selo, frase = _maquina(monkeypatch, "", conf)
    assert selo == storm_doctor.INFO, "o estado montado não é o `[INFO]` do dono"

    _, textos = _acesas(_canal(_ctx(VIVO_NAVEGACAO)))
    assert textos == [frase], (
        f"a cura AGENDADA não chegou ao canal: {textos!r}")


def test_o_selo_novo_esta_na_escada(monkeypatch: Any, tmp_path: Any) -> None:
    """``CONTROLE`` está em `ORDEM_DA_GRAVIDADE` — senão a cura desce."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "PERFIL", "texto": "cadeado", "fonte": "x"},
        {"selo": "PERFIL", "texto": "cego", "fonte": "x"},
    ])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    _, frase = _maquina(monkeypatch, "", tmp_path / "nao-existe.conf")

    selos, textos = _acesas(_canal(_ctx(VIVO_NAVEGACAO)))
    assert aba.SELO_DA_CURA in aba.ORDEM_DA_GRAVIDADE, (
        "o selo da cura saiu da escada — ele vai para depois de tudo")
    assert selos[0] == aba.SELO_DA_CURA, (
        f"a cura não subiu na escada: {selos!r}")
    assert textos[0] == frase, f"a frase da cura não é a do dono: {textos!r}"


def test_o_selo_nao_e_o_do_radio(monkeypatch: Any, tmp_path: Any) -> None:
    """A cura é do CABO; quem já ocupa ``RÁDIO`` fala de Bluetooth."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [
        {"selo": "RÁDIO", "texto": "o rádio está frágil", "fonte": "x"},
    ])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    _maquina(monkeypatch, "", tmp_path / "nao-existe.conf")

    selos, _ = _acesas(_canal(_ctx(VIVO_NAVEGACAO)))
    assert aba.SELO_DA_CURA != "RÁDIO", "a cura do cabo pegou o selo do rádio"
    assert len(set(selos)) == len(selos) == 2, (
        f"o cabo e o rádio saíram com o mesmo selo: {selos!r}")


def test_a_fonte_que_levanta_vira_erro_e_nao_derruba_a_coluna(
        monkeypatch: Any) -> None:
    """A política do `try` próprio: a coluna sobrevive à fonte que quebra.

    É a mesma de `painel.avisos_do_estado`, do opt-out e do exame. Esta fonte
    é a PRIMEIRA desta coluna a tocar o disco a cada tique — um `/sys`
    remontado ou um `/etc` sem permissão não pode apagar as outras nove linhas.

    A MORDIDA: tire o `try/except` que embrulha a chamada em
    `_avisos_com_outra_casa` e o canal inteiro levanta — as outras linhas somem
    com ele.

    ELA JÁ DERRUBOU O `pacote()` INTEIRO, e isso mudou em 07/09/2026: `_avisos`
    era chamado no meio de `pacote()`, então uma fonte que quebrasse levava
    junto a mesa, os cartões e a faixa. Com a coluna fora da Jogar o estrago
    ficou menor — mas a política do `try` próprio não afrouxa por isso, e é o
    que esta régua continua cobrando.
    """
    def _explode() -> dict[str, str]:
        raise OSError("o /sys sumiu")

    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", _explode)

    selos, textos = _acesas(_canal(_ctx(VIVO_NAVEGACAO)))
    assert selos == ["ERRO"], f"a fonte que levantou não virou ERRO: {selos!r}"
    assert "OSError" in textos[0], (
        f"o aviso de erro não diz o que quebrou: {textos[0]!r}")


def test_a_frase_da_cura_nao_se_digita_nesta_aba(tmp_path: Any) -> None:
    """A frase tem DONO, e a aba a lê — não a redigita."""
    _, frase = storm_doctor.check_snd_quirk("", tmp_path / "nao-existe.conf")
    trecho = frase.split(" — ", 1)[0].strip()
    assert len(trecho) > 20, f"o trecho do dono ficou curto demais: {trecho!r}"

    caminho = "src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py"
    fonte = (RAIZ / caminho).read_text(encoding="utf-8")
    dentro_de_prosa = False
    acusados: list[str] = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        nua = linha.strip()
        if nua.count('"""') == 1:
            dentro_de_prosa = not dentro_de_prosa
            continue
        if dentro_de_prosa or nua.startswith("#") or not nua:
            continue
        if trecho in nua.split("#", 1)[0]:
            acusados.append(f"{caminho}:{numero}: {nua}")
    assert not acusados, (
        "a frase da cura foi redigitada em código:\n  " + "\n  ".join(acusados)
        + "\nEla vem inteira de `storm_doctor.check_snd_quirk` e de mais lugar "
          "nenhum")


def test_a_lista_do_exame_da_09_recebe_os_avisos(monkeypatch: Any) -> None:
    """O aviso entra no fim da lista do exame, com o selo AVISO do desenho.

    O SELO NÃO SE DIGITA: o veredito é ``[WARN]`` e quem o traduz é
    `interface/sistema.exame`, o mesmo dono que traduz as linhas do `doctor`.

    A MORDIDA: faça `_com_os_avisos` devolver o `exame` sem tocar e a frase da
    pausa some da lista — reprova na primeira asserção.
    """
    from pacotes import a09_sistema

    frase = "O Hefesto está em pausa."
    monkeypatch.setattr(aba, "coluna_de_atencao", lambda _c: [
        {"selo": "PAUSA", "texto": frase, "fonte": "home_actions.texto_da_pausa"}])
    exame = {"linhas": [{"selo": "OK", "cls": "ok", "g": "✓", "txt": "do doctor"}],
             "vazio": ""}
    fora = a09_sistema._com_os_avisos(exame, _ctx(VIVO_NAVEGACAO))
    assert [linha["txt"] for linha in fora["linhas"]] == ["do doctor", frase], (
        f"o aviso não entrou no fim do exame: {fora['linhas']!r}")
    assert fora["linhas"][-1]["selo"] == "AVISO"
    assert frase in a09_sistema._html_do_exame(fora)


def test_o_exame_que_nao_respondeu_nao_some_atras_do_aviso(monkeypatch: Any) -> None:
    """Sem linha do exame e com aviso, a frase do vazio vira uma linha de NOTA."""
    from pacotes import a09_sistema

    monkeypatch.setattr(aba, "coluna_de_atencao", lambda _c: [
        {"selo": "RÁDIO", "texto": "o rádio está frágil", "fonte": "x"}])
    nao_respondeu = a09_sistema._tela.exame(None)
    fora = a09_sistema._com_os_avisos(nao_respondeu, _ctx(VIVO_NAVEGACAO))
    textos = [linha["txt"] for linha in fora["linhas"]]
    assert textos == [nao_respondeu["vazio"], "o rádio está frágil"], textos


def test_o_pacote_da_09_passa_o_exame_pelos_avisos() -> None:
    """`a09_sistema.pacote` chama `_com_os_avisos` antes de desenhar o exame.

    Medido pelo FONTE, e não pelo pacote inteiro: ele pergunta ao `systemctl`,
    ao disco e ao Proton, e cada dublê a mais é uma chance de a régua medir o
    dublê. O que se cobra aqui é a costura; o que ela faz, as duas acima.

    A MORDIDA: troque `_html_do_exame(_com_os_avisos(exame, ctx))` por
    `_html_do_exame(exame)` e esta régua reprova.
    """
    import ast

    fonte = (INTERFACE / "pacotes" / "a09_sistema.py").read_text(encoding="utf-8")
    pacote = next(no for no in ast.walk(ast.parse(fonte))
                  if isinstance(no, ast.FunctionDef) and no.name == "pacote")
    chamadas = {no.func.id for no in ast.walk(pacote)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)}
    assert "_com_os_avisos" in chamadas, (
        "o pacote da 09 deixou de levar os avisos do produto ao exame")
