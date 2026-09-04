#!/usr/bin/env python3
"""A prova botão a botão não cala um achado da máquina dela.

**03/09/2026.** Medido com o journal do daemon dos dois lados, na mesa dela:

    16:11:53  (antes)  MesaDeclarada(altura_da_antena='acima',
                                     linha_de_visada='com_gente',
                                     radios={}, ordens_dispensadas={})

    16:13:44  (depois de `--prova-no-aparelho --abre 08-conexoes.html`)
              maquina.json → "ordens_dispensadas": {
                  "dongle_atras_de_hub": {"arranjo": "3-1.2 3-1.4",
                                          "quando": "2026-09-03"}}

E o Check-up dela perdeu a linha *"2 de 3 adaptadores Bluetooth chegam ao
computador por dentro de um hub"* — uma das DUAS únicas que acusam nesta
máquina. O ⊘ é o gesto `ignorar`, e ele grava
`MesaDeclarada.ordens_dispensadas` (`a08_conexoes.ignorar`).

**NÃO VOLTA SOZINHO:** `ordens_da_mesa.ordens_novas` compara o arranjo guardado
com o de agora — enquanto os cabos não mudarem, a linha fica calada.

**POR QUE SÓ ESTE**, e não os outros onze gestos da mesma aba que chamam
`machine.declare`: os outros clicam o valor que a PÁGINA mostra, e a página
mostra o que a declaração já dizia. Na mesma volta, `sala-altura`,
`sala-visada` e `mic-existe` gravaram exatamente o que já estava no disco — o
ÚNICO campo que mudou foi `ordens_dispensadas`. O ⊘ é diferente porque o que
ele grava não vem da declaração, vem do EXAME.

A MORDIDA: tire `("08-conexoes.html", "ignorar")` de `hefesto_vivo.PERIGOSOS` e
rode este arquivo — os dois primeiros testes reprovam.
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "08-conexoes.html"


def _perigosos() -> set[tuple[str, str]]:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    return set(hefesto_vivo.PERIGOSOS)


def test_o_gesto_ignorar_da_conexoes_esta_isento() -> None:
    """O ⊘ da aba Conexões não entra na volta automática."""
    assert (PAGINA, "ignorar") in _perigosos(), (
        "o ⊘ da Conexões saiu de `PERIGOSOS` — a próxima `--prova-no-aparelho` "
        "volta a dispensar uma ordem de serviço da máquina dela, e a linha não "
        "reaparece enquanto os cabos não mudarem")


def test_a_regua_realmente_pula_o_ignorar() -> None:
    """E a régua tem de PULÁ-LO — a lista sozinha não é a cura.

    Um nome em `PERIGOSOS` que `_alvos_a_clicar` não consulte seria uma isenção
    de papel. Aqui se mede o que a régua faz, não o que a lista diz.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup

    clicar, pulados = regua_do_mockup._alvos_a_clicar(
        [], {"ignorar", "alvo", "todos"}, PAGINA, _perigosos())
    assert "ignorar" in pulados, (
        f"a régua ainda clicaria o ⊘: clicar={clicar!r} pulados={pulados!r}")
    assert "ignorar" not in clicar


def test_os_outros_gestos_da_aba_continuam_sendo_provados() -> None:
    """A isenção é de UM gesto, e não da aba.

    Isentar demais é o outro jeito de a régua deixar de medir: os gestos
    idempotentes desta aba têm de continuar sendo clicados, senão a prova botão
    a botão da 08 vira uma volta em branco.

    **ESTA RÉGUA DIGITAVA A LISTA, e envelheceu na primeira melhora** —
    04/09/2026. Ela cravava os onze nomes e cobrava que os onze fossem
    clicados; quando `teto-da-vibracao` entrou em `PERIGOSOS` (ele passou a
    gravar `controllers[uniq].rumble` no perfil ATIVO, por decisão dela de
    construir a política por controle), a régua REPROVOU A MELHORA. É a família
    de defeito que esta casa mais paga: *a régua digita em vez de perguntar*.

    Agora ela pergunta ao dono. O que se mede é o que a régua garantia de
    verdade: **tudo o que ela pula desta aba está em `PERIGOSOS`, e nada mais.**
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup

    outros = {"alvo", "todos", "mic-existe", "sala-altura", "sala-visada",
              "vizinho-o-que-e", "teto-da-vibracao", "examinar-portas",
              "escolher-aparelho", "luz-nao-acende", "aplicar"}
    perigosos = _perigosos()
    protegidos = {g for p, g in perigosos if p == PAGINA} & outros
    clicar, pulados = regua_do_mockup._alvos_a_clicar(
        [], outros, PAGINA, perigosos)

    assert set(pulados) <= protegidos, (
        "a régua pulou gesto que NÃO está em `PERIGOSOS` — a isenção do ⊘ "
        f"levou junto: {sorted(set(pulados) - protegidos)!r}")
    assert set(clicar) == outros - protegidos, (
        f"a volta perdeu gesto sem razão: clicar={sorted(clicar)!r} "
        f"pulados={pulados!r} protegidos={sorted(protegidos)!r}")
    assert len(clicar) >= 8, (
        f"sobraram só {len(clicar)} gestos a clicar nesta aba — se a lista de "
        "PERIGOSOS crescer a este ponto, a prova da 08 virou volta em branco e "
        "a cobertura precisa de outro caminho, não de mais isenção")
