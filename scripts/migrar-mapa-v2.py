#!/usr/bin/env python3
"""migrar-mapa-v2.py — leva o mapa de canais para o formato que ela pediu.

O PEDIDO, nas palavras dela: *"cada feature de cada um deles deve ter o canal
via bt ou cabo NA MESMA LINHA e todos os 3 controles devem ser possíveis de
serem comparados. exemplo: descobrimos que todos tem microfone e já mapeamos no
dsx, se eu mapear no 8bitdo o funcionamento de um pro outro será coisa de eu
mover o nome de uma variável."*

O QUE MUDA
----------
O grão do v1 era ``(feature, controle, transporte)``: 204 linhas, e a mesma
feature aparecia duas vezes — uma para o cabo, outra para o rádio — com o texto
da feature às vezes divergindo por um parêntese. Comparar cabo com rádio exigia
achar as duas linhas; comparar os três controles exigia um pivô que ninguém faz
à mão.

O grão do v2 é ``(chave, controle)``. O "COMO se faz" — o que muda de verdade
entre os barramentos — vira par de colunas ``cabo_*`` / ``radio_*`` na MESMA
linha. O "O QUE existe" fica em coluna única. Ordenado por ``chave``, cada
feature é um bloco de TRÊS linhas adjacentes, uma por controle: ela abre o CSV e
vê os três, sem pivô.

A recomendação foi MEDIDA antes de ser escrita. Nos 58 pares limpos do v1,
``comando`` difere entre cabo e rádio em 100% dos casos, ``offset`` em 78% e
``report_id`` em 50% — mas ``aparelho_aceita`` difere em 9% e ``canal`` em 7%.
Duplicar só o que varia. Aqui a regra foi aplicada ao pé da letra: **todo campo
que difere em ao menos um par ganha o par de colunas**, inclusive
``aparelho_aceita`` — porque os 9% que divergem são exatamente as assimetrias
que este mapa existe para não deixar escapar. Achatar aquele campo faria uma
prova de cabo passar por prova de rádio, que é a mentira mais cara daqui.

AS COLUNAS NOVAS
----------------
``chave``   ``familia.peca[.aspecto]``, estável entre os três controles. É o
            nome da variável que ela move de um controle para o outro.
``peca``    o id do grupo no SVG DAQUELE controle (``l2`` no DualSense, ``zl``
            no Pro). A máscara de expressões regulares que o gerador resolvia em
            tempo de desenho vira DADO, resolvido uma vez e conferido contra os
            ids que o desenho realmente tem.
``evdev``   o código evdev canônico, lido do ``data-evdev`` dos SVG do Pro e do
            SN30. Vazio onde o desenho não declara — não localizado é resposta
            válida, inventar não é.
``existe``  ``tem`` / ``nao-tem`` / ``parcial`` / ``desconhecido``: a resposta
            sobre o PLÁSTICO, separada da resposta sobre o transporte. É isto
            que faz a ausência virar informação em vez de buraco.

OS PARES ÓRFÃOS
---------------
Dez pares do v1 não casavam por texto porque o lado do cabo trazia um parêntese
a mais ("Sticks analógicos (dois eixos por stick)" contra "Sticks analógicos").
Seis foram julgados um a um por agentes independentes, todos com veredicto
``mesma_feature=true`` e confiança alta; os outros quatro (todos do DualSense)
têm exatamente a mesma forma — rótulo idêntico fora do parêntese — e o
julgamento do par de áudio do Pro cita dois deles pelo nome como o mesmo padrão.
Casar a CHAVE nunca funde as EVIDÊNCIAS: cada transporte continua com o seu
``aceita``, o seu ``de_onde_sei``, a sua ``evidencia`` e a sua ``ressalva``.

NADA SE PERDE
-------------
As 204 linhas do v1 carregam medição real. Este script prova campo a campo que
toda informação sobreviveu, e reprova se não sobreviver. O v1 fica guardado em
``docs/data/mapa-controles-v1.csv`` — não se apaga medição.

Uso:
    .venv/bin/python scripts/migrar-mapa-v2.py           # migra e prova
    .venv/bin/python scripts/migrar-mapa-v2.py --provar  # só reprova a prova
"""
# ruff: noqa: RUF001 — o MINUS SIGN (U+2212) é deliberado: este arquivo
# imprime intervalos e diferenças em PROSA para quem lê a migração, e o
# sinal tipográfico é o certo ali. Trocar por hífen-menos empobrece o
# texto sem ganhar nada, e a casa exige português bem escrito.
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
V1 = RAIZ / "docs" / "data" / "mapa-controles.csv"
V1_GUARDADO = RAIZ / "docs" / "data" / "mapa-controles-v1.csv"
V2 = RAIZ / "docs" / "data" / "mapa-controles.csv"
ENSAIOS = RAIZ / "docs" / "data" / "ensaios.csv"
ENSAIOS_GUARDADO = RAIZ / "docs" / "data" / "ensaios-v1.csv"
SVGS = {
    "dualsense": RAIZ / "assets" / "control-svg" / "dualsense.svg",
    "pro": RAIZ / "assets" / "control-svg" / "nintendo-pro.svg",
    "sn30": RAIZ / "assets" / "control-svg" / "8bitdo-sn30-pro.svg",
}
CONTROLES = ("dualsense", "pro", "sn30")

# ── a máscara, materializada ────────────────────────────────────────────────
# Era `ALVOS` em scripts/gerar-mapa.py, resolvida a cada geração. Aqui ela roda
# UMA vez e o resultado vira a coluna `peca`. Primeiro padrão que casar vence,
# então o mais específico vem antes.
ALVOS = [
    (r"lightbar|barra de luz", "lightbar"),
    (r"led de jogador|indicador de jogador|player.?led|n[úu]mero do jogador", "led-jogador"),
    (r"touchpad", "touchpad"),
    (r"alto-falante|speaker", "alto-falante"),
    (r"microfone|\bmic\b", "microfone mic"),
    (r"girosc", "feat-giroscopio"),
    (r"aceler", "feat-acelerometro"),
    (r"bateria|carga", "feat-bateria"),
    (r"gatilho|trigger|adaptativ", "l2 r2 zl zr"),
    (r"rumble|vibra|h[áa]ptic", "feat-rumble-esquerdo feat-rumble-direito feat-rumble"),
    (r"d-?pad|direcional", "dpad dpad_up dpad_down dpad_left dpad_right"),
    (r"bot[õo]es|face|a/b/x/y|cruz|c[íi]rculo|quadrado|tri[âa]ngulo",
     "a b x y cross circle square triangle"),
    (r"ombro|bumper|\bl1\b|\br1\b", "l1 r1 l r"),
    (r"home|\bps\b|guia", "ps home"),
    (r"select|start|share|options|op[çc][õo]es|menu", "share options select start plus minus"),
    (r"touch|clique do toque", "touchpad"),
    (r"anal[óo]gic|stick", "stick_l stick_r"),
]

# ── a chave canônica de cada linha do v1 ────────────────────────────────────
# Chaveado pelo par (controle, feature) EXATO do v1, que é único. Duas entradas
# com a mesma chave e o mesmo controle são o par cabo/rádio casado.
CHAVES: dict[tuple[str, str], str] = {
    # ── audio ───────────────────────────────────────────────────────────────
    ("dualsense", "Alto-falante — SOM SAINDO (dados de áudio)"): "audio.alto_falante",
    ("pro", "Alto-falante do controle"): "audio.alto_falante",
    ("sn30", "Alto-falante do controle"): "audio.alto_falante",
    ("dualsense", "Alto-falante — PRÉ-AMPLIFICADOR"): "audio.alto_falante.preamp",
    ("dualsense", "Alto-falante — ROTA de saída"): "audio.alto_falante.rota",
    ("dualsense", "Alto-falante — ROTA de saída (o caso Zelda)"): "audio.alto_falante.rota",
    ("dualsense", "Alto-falante — VOLUME"): "audio.alto_falante.volume",
    ("dualsense", "Detecção de fone/microfone plugados (status1)"): "audio.jack.deteccao",
    ("dualsense", "Fone de ouvido (jack do controle) — VOLUME"): "audio.jack.volume",
    ("dualsense", "Microfone — CAPTAÇÃO do áudio (o sinal)"): "audio.microfone",
    ("pro", "Microfone"): "audio.microfone",
    ("sn30", "Microfone"): "audio.microfone",
    ("dualsense", "Microfone — MUDO no firmware"): "audio.microfone.mudo",
    ("dualsense", "Microfone — VOLUME"): "audio.microfone.volume",
    ("dualsense", "Saída de áudio DEDICADA do controle"): "audio.saida_dedicada",
    ("dualsense", "Saída de áudio DEDICADA do controle (distinta do HDMI)"):
        "audio.saida_dedicada",
    ("pro", "Saída de áudio dedicada"): "audio.saida_dedicada",
    ("pro", "Saída de áudio dedicada (placa USB Audio no controle)"): "audio.saida_dedicada",
    ("sn30", "Saída de áudio dedicada (jack de fone no controle)"): "audio.saida_dedicada",
    ("dualsense", "Áudio — LEITURA de volta (qualquer registrador)"): "audio.leitura_de_volta",

    # ── energia ─────────────────────────────────────────────────────────────
    ("dualsense", "Bateria — percentual e estado de carga"): "energia.bateria.percentual",
    ("sn30", "Bateria — PORCENTAGEM"): "energia.bateria.percentual",
    ("pro", "Bateria — nível em CINCO DEGRAUS (não há percentual)"): "energia.bateria.degraus",
    ("sn30", "Bateria — nível em CINCO degraus"): "energia.bateria.degraus",
    ("dualsense", "Bateria — espelho ao JOGO (vpad)"): "energia.bateria.jogo",
    ("sn30", "Bateria lida pelo Hefesto"): "energia.bateria.leitura_hefesto",
    ("dualsense", "Desligar o controle / gerir energia por software"): "energia.desligar",
    ("pro", "Desligar o controle (SET_HCI_STATE)"): "energia.desligar",
    ("sn30", "Desligar o controle / modo de baixo consumo / re-pareamento por subcomando"):
        "energia.desligar",

    # ── entrada ─────────────────────────────────────────────────────────────
    ("pro", "Botões e D-pad (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Capture, L3/R3)"):
        "entrada.botoes",
    ("sn30", "Botões digitais (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Captura, L3/R3) + D-pad"):
        "entrada.botoes",
    ("sn30", "Botões digitais + D-pad"): "entrada.botoes",
    ("pro", "Analógicos (dois sticks, faixa −32767..32767)"): "entrada.stick",
    ("sn30", "Sticks analógicos"): "entrada.stick",
    ("sn30", "Sticks analógicos (dois eixos por stick)"): "entrada.stick",
    ("sn30", "Calibração de fábrica dos sticks"): "entrada.stick.calibracao",
    ("dualsense", "Botões, sticks e gatilhos analógicos (entrada bruta)"): "entrada.bruta",

    # ── gatilho ─────────────────────────────────────────────────────────────
    ("dualsense", "Gatilho adaptativo ESQUERDO (L2)"): "gatilho.esquerdo.adaptativo",
    ("dualsense", "Gatilho adaptativo DIREITO (R2)"): "gatilho.direito.adaptativo",
    ("pro", "Gatilhos adaptativos (resistência/força por zona)"): "gatilho.adaptativo",
    ("sn30", "Gatilhos adaptativos (resistência/efeito)"): "gatilho.adaptativo",
    ("dualsense", "Gatilho — LEITURA do estado"): "gatilho.leitura",
    ("dualsense", "Gatilho — LEITURA do estado (o que o gatilho está sentindo)"):
        "gatilho.leitura",
    ("dualsense", "Gatilho — modos do firmware (enum)"): "gatilho.modos_firmware",
    ("pro", "Gatilhos ZL/ZR — são DIGITAIS, não há eixo analógico"): "gatilho.analogico",
    ("sn30", "Gatilhos ANALÓGICOS (ZL/ZR com curso)"): "gatilho.analogico",

    # ── identidade ──────────────────────────────────────────────────────────
    ("dualsense", "Atualização de FIRMWARE"): "identidade.firmware",
    ("sn30", "Atualização de firmware"): "identidade.firmware",
    ("pro", "Pareamento manual, esquecer o host, HID OFF (0x01 / 0x07 / 0x08)"):
        "identidade.pareamento",
    ("sn30", "Pareamento / bond por Bluetooth"): "identidade.pareamento",
    ("pro", "REQ_DEV_INFO — endereço de rádio e tipo do controle"): "identidade.req_dev_info",
    ("sn30", "Identidade quando o REQ_DEV_INFO não responde (endereço sintético)"):
        "identidade.req_dev_info.fallback",

    # ── luz ─────────────────────────────────────────────────────────────────
    ("dualsense", "Lightbar (cor RGB)"): "luz.lightbar.cor",
    ("pro", "Lightbar RGB"): "luz.lightbar.cor",
    ("sn30", "Lightbar RGB"): "luz.lightbar.cor",
    ("dualsense", "Lightbar — brilho de HARDWARE (3 níveis)"): "luz.lightbar.brilho",
    ("dualsense", "Lightbar — devolver o claim (RELEASE_LEDS 0x08)"): "luz.lightbar.release_leds",
    ("dualsense", "Lightbar — fade in/out (lightbar_setup)"): "luz.lightbar.fade",
    ("dualsense", "LED de jogador (5 lâmpadas)"): "luz.led_jogador",
    ("pro", "LED de jogador — as QUATRO lâmpadas VERDES"): "luz.led_jogador",
    ("sn30", "LED de jogador — as 4 lâmpadas verdes"): "luz.led_jogador",
    ("pro", "LED de jogador — o padrão que o DRIVER acende sozinho, no probe"):
        "luz.led_jogador.padrao_driver",
    ("sn30", "Padrão de jogador que o DRIVER acende sozinho na probe"):
        "luz.led_jogador.padrao_driver",
    ("pro", "Leitura do LED de jogador (saber o que está aceso)"): "luz.led_jogador.leitura",
    ("sn30", "Escrita de LED de jogador pelo Hefesto (a numeração aparecer na lâmpada)"):
        "luz.led_jogador.escrita_hefesto",
    ("pro", "Quinto LED de jogador"): "luz.led_jogador.quinto",
    ("pro", "Regra udev 79 — tornar o LED do Pro gravável sem sudo"): "luz.led_jogador.udev",
    ("sn30", "Regra udev que torna os LEDs graváveis sem sudo"): "luz.led_jogador.udev",
    ("sn30", "Pisca de LED em HARDWARE (nibble `flash` do subcomando 0x30)"):
        "luz.led_jogador.pisca",
    ("dualsense", "LED de HOME / botão PS iluminado"): "luz.led_home",
    ("pro", "LED HOME (a lâmpada AZUL do anel do botão Home)"): "luz.led_home",
    ("sn30", "LED HOME (nó `:blue:player-5`, brilho 0–15)"): "luz.led_home",
    ("dualsense", "Microfone — LED do botão de mudo"): "luz.led_microfone",
    ("pro", "LED do microfone (o botão de mudo iluminado)"): "luz.led_microfone",
    ("pro", "Réplica do output do JOGO (gatilho adaptativo, lightbar, LED de jogador) no Pro"):
        "luz.replica_output_jogo",
    ("sn30", "Turbo, LEDs de indicação de modo e demais recursos próprios da 8BitDo"):
        "luz.recursos_proprios",

    # ── movimento ───────────────────────────────────────────────────────────
    ("dualsense", "Acelerômetro — número para a INTERFACE"): "movimento.acelerometro",
    ("pro", "Acelerômetro"): "movimento.acelerometro",
    ("sn30", "Acelerômetro"): "movimento.acelerometro",
    ("dualsense", "Acelerômetro — dado para o JOGO"): "movimento.acelerometro.jogo",
    ("dualsense", "Giroscópio — número para a INTERFACE"): "movimento.giroscopio",
    ("pro", "Giroscópio"): "movimento.giroscopio",
    ("sn30", "Giroscópio"): "movimento.giroscopio",
    ("dualsense", "Giroscópio — dado para o JOGO (espelho ao vpad)"): "movimento.giroscopio.jogo",
    ("pro", "Espelho de motion (giroscópio cru do físico → vpad)"): "movimento.giroscopio.jogo",
    ("sn30", "Giroscópio CHEGANDO ao jogo"): "movimento.giroscopio.jogo",
    ("dualsense", "Giroscópio — TAXA declarada vs entregue"): "movimento.giroscopio.taxa",
    ("dualsense", "Calibração da IMU (feature report 0x05)"): "movimento.imu.calibracao",
    ("pro", "Calibração de sticks e de IMU"): "movimento.imu.calibracao",
    ("sn30", "Calibração de fábrica da IMU"): "movimento.imu.calibracao",
    ("sn30", "Ligar a IMU (subcomando 0x40 / arg 0x01)"): "movimento.imu.ligar",
    ("pro", "Perda de amostras de IMU"): "movimento.imu.perda",
    ("pro", "Perda de amostras de IMU (o instrumento de rádio que está de graça no journal)"):
        "movimento.imu.perda",

    # ── plataforma ──────────────────────────────────────────────────────────
    ("pro", "Adoção do Pro pelo backend (input, output desejado, perfil)"): "plataforma.adocao",
    ("sn30", "Adoção pelo Hefesto (grab do evdev, gamepad virtual, espelho de motion, "
             "perfil de botões)"): "plataforma.adocao",
    ("dualsense", "NFC / amiibo"): "plataforma.nfc",
    ("pro", "NFC / amiibo (canais de MCU)"): "plataforma.nfc",
    ("sn30", "NFC / amiibo (canal MCU)"): "plataforma.nfc",
    ("pro", "CRC-32 no envelope (integridade de report)"): "plataforma.crc32",
    ("pro", "Câmera IR"): "plataforma.camera_ir",
    ("pro", "Distinguir o Pro GENUÍNO do clone 8BitDo"): "plataforma.distinguir_clone",
    ("sn30", "Discriminar clone × Pro genuíno"): "plataforma.distinguir_clone",
    ("pro", "Gamepad virtual (vpad) que o Hefesto cria para o Pro"): "plataforma.vpad",
    ("pro", "Handshake USB, baudrate 3M e no-timeout"): "plataforma.handshake_usb",
    ("sn30", "Handshake USB + baudrate 3M + no-timeout"): "plataforma.handshake_usb",
    ("pro", "Limitador de subcomando (o que governa TODA escrita)"):
        "plataforma.limitador_subcomando",
    ("pro", "Modo de relatório (SET_REPORT_MODE)"): "plataforma.modo_relatorio",
    ("sn30", "Modo de relatório completo (SET_REPORT_MODE → 0x30)"): "plataforma.modo_relatorio",
    ("pro", "Referências a Nintendo em src/ (a prova que a página de uso cita)"):
        "plataforma.referencias_nintendo",
    ("pro", "Regra udev 81 — o Pro nunca dorme no barramento USB"):
        "plataforma.udev_autosuspend",
    ("pro", "Sniff / link policy do rádio"): "plataforma.sniff",
    ("sn30", "SNIFF do link (política de rádio)"): "plataforma.sniff",
    ("pro", "Taxa de relatórios de entrada"): "plataforma.taxa_relatorios",
    ("sn30", "Botão de taxa de rádio (poll interval programável)"):
        "plataforma.taxa_relatorios.botao",
    ("sn30", "Diagnóstico da morte por Bluetooth (doctor)"): "plataforma.diagnostico_morte_radio",
    ("sn30", "Escrita CRUA por hidraw (qualquer subcomando)"): "plataforma.escrita_crua",
    ("sn30", "Inventário read-only do controle na interface e na CLI"): "plataforma.inventario",
    ("sn30", "Mapeamento por POSIÇÃO nos jogos lançados pelo Hefesto"):
        "plataforma.mapeamento_posicao",
    ("sn30", "Subir a probe no cabo (o controle EXISTIR em modo Switch por USB)"):
        "plataforma.probe",
    ("sn30", "Retry de probe por rádio"): "plataforma.probe.retry",
    ("sn30", "Slot / número de jogador atribuído pelo Hefesto"): "plataforma.slot_jogador",
    ("sn30", "Timeout de supervisão / intervalo de sniff negociado / latência do link"):
        "plataforma.link_parametros",
    ("sn30", "Transporte de rádio (tipo de link)"): "plataforma.transporte_radio",
    ("sn30", "Vigia de zumbi (link de pé e controle mudo)"): "plataforma.vigia_zumbi",

    # ── toque ───────────────────────────────────────────────────────────────
    ("dualsense", "Touchpad — os DOIS pontos de toque (ao jogo)"): "toque.touchpad",
    ("pro", "Touchpad"): "toque.touchpad",
    ("sn30", "Touchpad"): "toque.touchpad",
    ("dualsense", "Touchpad — cursor do mouse (o dedo)"): "toque.touchpad.cursor",
    ("dualsense", "Touchpad — o CLIQUE (botão)"): "toque.touchpad.clique",
    ("dualsense", "Touchpad — ESCRITA (qualquer)"): "toque.touchpad.escrita",

    # ── vibracao ────────────────────────────────────────────────────────────
    ("pro", "Rumble (HD rumble, dois motores lineares)"): "vibracao.rumble.ff",
    ("sn30", "Rumble (motor esquerdo = strong, direito = weak)"): "vibracao.rumble.ff",
    ("sn30", "Rumble (motor esquerdo e direito)"): "vibracao.rumble.ff",
    ("dualsense", "Rumble — motor ESQUERDO (strong)"): "vibracao.rumble.esquerdo",
    ("dualsense", "Rumble — motor DIREITO (weak)"): "vibracao.rumble.direito",
    ("pro", "Rumble — as frequências HD (41–626 Hz banda baixa, 82–1253 Hz banda alta)"):
        "vibracao.rumble.frequencia",
    ("sn30", "Rumble HD — controle de FREQUÊNCIA por motor"): "vibracao.rumble.frequencia",
    ("sn30", "Rumble HD — controle de FREQUÊNCIA por motor (41–1253 Hz)"):
        "vibracao.rumble.frequencia",
    ("dualsense", "Rumble do JOGO (vpad → físico)"): "vibracao.rumble.passthrough",
    ("pro", "Rumble do JOGO mirado no Pro (via o vpad que o Hefesto cria para ele)"):
        "vibracao.rumble.passthrough",
    ("sn30", "Rumble do JOGO roteado pelo Hefesto para este controle"):
        "vibracao.rumble.passthrough",
    ("pro", "Enable vibration (habilitar o motor no firmware)"): "vibracao.rumble.habilitar",
    ("dualsense", "Haptics VCM (motores voice-coil)"): "vibracao.haptics_vcm",
    ("dualsense", 'Haptics VCM (motores voice-coil, "HD rumble" da Sony)'): "vibracao.haptics_vcm",
    ("pro", "Haptics VCM / PCM (motores voice-coil com forma de onda)"): "vibracao.haptics_vcm",
    ("sn30", "Haptics VCM / áudio-háptico (PCM nos motores)"): "vibracao.haptics_vcm",
}

#: O rótulo compartilhado de cada chave — o nome que vale para os três
#: controles. O texto original de cada linha do v1 sobrevive intacto em
#: `cabo_feature_v1` / `radio_feature_v1`; este é o nome do conceito.
ROTULOS: dict[str, str] = {
    "audio.alto_falante": "Alto-falante do controle — som saindo",
    "audio.alto_falante.preamp": "Alto-falante — pré-amplificador",
    "audio.alto_falante.rota": "Alto-falante — rota de saída",
    "audio.alto_falante.volume": "Alto-falante — volume",
    "audio.jack.deteccao": "Jack — detecção de fone/microfone plugados",
    "audio.jack.volume": "Fone de ouvido (jack do controle) — volume",
    "audio.leitura_de_volta": "Áudio — leitura de volta (qualquer registrador)",
    "audio.microfone": "Microfone — captação do áudio",
    "audio.microfone.mudo": "Microfone — mudo no firmware",
    "audio.microfone.volume": "Microfone — volume",
    "audio.saida_dedicada": "Saída de áudio dedicada",
    "energia.bateria.degraus": "Bateria — nível em cinco degraus",
    "energia.bateria.jogo": "Bateria — espelho ao jogo (vpad)",
    "energia.bateria.leitura_hefesto": "Bateria — leitura pelo Hefesto",
    "energia.bateria.percentual": "Bateria — percentual e estado de carga",
    "energia.desligar": "Desligar o controle por software",
    "entrada.botoes": "Botões digitais (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Captura, L3/R3) + D-pad",
    "entrada.bruta": "Botões, sticks e gatilhos analógicos (entrada bruta)",
    "entrada.stick": "Sticks analógicos (dois eixos por stick)",
    "entrada.stick.calibracao": "Calibração de fábrica dos sticks",
    "gatilho.adaptativo": "Gatilhos adaptativos (resistência por zona) — os dois",
    "gatilho.analogico": "Gatilhos analógicos (eixo de curso em ZL/ZR ou L2/R2)",
    "gatilho.direito.adaptativo": "Gatilho adaptativo DIREITO",
    "gatilho.esquerdo.adaptativo": "Gatilho adaptativo ESQUERDO",
    "gatilho.leitura": "Gatilho — leitura do estado",
    "gatilho.modos_firmware": "Gatilho — modos do firmware (enum)",
    "identidade.firmware": "Atualização de firmware",
    "identidade.pareamento": "Pareamento / bond e esquecer o host",
    "identidade.req_dev_info": "REQ_DEV_INFO — endereço de rádio e tipo do controle",
    "identidade.req_dev_info.fallback":
        "Identidade quando o REQ_DEV_INFO não responde (endereço sintético)",
    "luz.led_home": "LED do botão HOME / PS iluminado",
    "luz.led_jogador": "LED de jogador (as lâmpadas de numeração)",
    "luz.led_jogador.escrita_hefesto": "LED de jogador — escrita pelo Hefesto",
    "luz.led_jogador.leitura": "LED de jogador — leitura (saber o que está aceso)",
    "luz.led_jogador.padrao_driver": "LED de jogador — o padrão que o driver acende na probe",
    "luz.led_jogador.pisca": "LED de jogador — pisca em hardware",
    "luz.led_jogador.quinto": "LED de jogador — a quinta lâmpada",
    "luz.led_jogador.udev": "LED de jogador — regra udev que o torna gravável sem sudo",
    "luz.led_microfone": "LED do microfone (o botão de mudo iluminado)",
    "luz.lightbar.brilho": "Lightbar — brilho de hardware",
    "luz.lightbar.cor": "Lightbar — cor RGB",
    "luz.lightbar.fade": "Lightbar — fade in/out",
    "luz.lightbar.release_leds": "Lightbar — devolver o claim (RELEASE_LEDS 0x08)",
    "luz.recursos_proprios": "Recursos próprios do fabricante (turbo, LEDs de modo)",
    "luz.replica_output_jogo": "Réplica do output do jogo (lightbar, LED de jogador, gatilho)",
    "movimento.acelerometro": "Acelerômetro — número para a interface",
    "movimento.acelerometro.jogo": "Acelerômetro — dado para o jogo",
    "movimento.giroscopio": "Giroscópio — número para a interface",
    "movimento.giroscopio.jogo": "Giroscópio — dado para o jogo (espelho ao vpad)",
    "movimento.giroscopio.taxa": "Giroscópio — taxa declarada contra entregue",
    "movimento.imu.calibracao": "Calibração de fábrica da IMU",
    "movimento.imu.ligar": "Ligar a IMU",
    "movimento.imu.perda": "Perda de amostras de IMU",
    "plataforma.adocao": "Adoção pelo Hefesto (grab, vpad, perfil)",
    "plataforma.camera_ir": "Câmera IR",
    "plataforma.crc32": "CRC-32 no envelope (integridade de report)",
    "plataforma.diagnostico_morte_radio": "Diagnóstico da morte por rádio (doctor)",
    "plataforma.distinguir_clone": "Distinguir o genuíno do clone",
    "plataforma.escrita_crua": "Escrita crua por hidraw (qualquer subcomando)",
    "plataforma.handshake_usb": "Handshake USB, baudrate 3M e no-timeout",
    "plataforma.inventario": "Inventário read-only do controle na interface e na CLI",
    "plataforma.limitador_subcomando": "Limitador de subcomando (o que governa toda escrita)",
    "plataforma.link_parametros":
        "Parâmetros do link (supervisão, sniff negociado, latência)",
    "plataforma.mapeamento_posicao": "Mapeamento por posição nos jogos lançados pelo Hefesto",
    "plataforma.modo_relatorio": "Modo de relatório (SET_REPORT_MODE)",
    "plataforma.nfc": "NFC / amiibo",
    "plataforma.probe": "Subir a probe (o controle EXISTIR para o sistema)",
    "plataforma.probe.retry": "Retry de probe",
    "plataforma.referencias_nintendo": "Referências a Nintendo em src/",
    "plataforma.slot_jogador": "Slot / número de jogador atribuído pelo Hefesto",
    "plataforma.sniff": "Sniff / link policy do rádio",
    "plataforma.taxa_relatorios": "Taxa de relatórios de entrada",
    "plataforma.taxa_relatorios.botao": "Taxa de relatórios — botão na interface",
    "plataforma.transporte_radio": "Transporte de rádio (tipo de link)",
    "plataforma.udev_autosuspend": "Regra udev — o controle nunca dorme no barramento USB",
    "plataforma.vigia_zumbi": "Vigia de zumbi (link de pé e controle mudo)",
    "plataforma.vpad": "Gamepad virtual (vpad) que o Hefesto cria",
    "toque.touchpad": "Touchpad — os pontos de toque",
    "toque.touchpad.clique": "Touchpad — o clique (botão)",
    "toque.touchpad.cursor": "Touchpad — cursor do mouse (o dedo)",
    "toque.touchpad.escrita": "Touchpad — escrita (qualquer)",
    "vibracao.haptics_vcm": "Haptics VCM / PCM (motores voice-coil com forma de onda)",
    "vibracao.rumble.direito": "Rumble — motor DIREITO (weak)",
    "vibracao.rumble.esquerdo": "Rumble — motor ESQUERDO (strong)",
    "vibracao.rumble.ff": "Rumble por amplitude (FF_RUMBLE — motor esquerdo = strong, "
                          "direito = weak)",
    "vibracao.rumble.frequencia": "Rumble HD — controle de FREQUÊNCIA por motor",
    "vibracao.rumble.habilitar": "Habilitar o motor no firmware (enable vibration)",
    "vibracao.rumble.passthrough": "Rumble do JOGO roteado pelo Hefesto (vpad → físico)",
}

#: Onde a resposta daquele controle mora em OUTRA chave. Sem isto, uma linha
#: completada viraria "desconhecido" mentindo — o DualSense tem stick, só que o
#: v1 escreveu botões, sticks e gatilhos numa linha só.
VER_TAMBEM: dict[tuple[str, str], str] = {
    ("entrada.stick", "dualsense"): "entrada.bruta",
    ("entrada.botoes", "dualsense"): "entrada.bruta",
    ("gatilho.analogico", "dualsense"): "entrada.bruta",
    ("entrada.bruta", "pro"): "entrada.botoes",
    ("entrada.bruta", "sn30"): "entrada.botoes",
    ("entrada.stick.calibracao", "pro"): "movimento.imu.calibracao",
    ("gatilho.adaptativo", "dualsense"): "gatilho.esquerdo.adaptativo",
    ("gatilho.esquerdo.adaptativo", "pro"): "gatilho.adaptativo",
    ("gatilho.esquerdo.adaptativo", "sn30"): "gatilho.adaptativo",
    ("gatilho.direito.adaptativo", "pro"): "gatilho.adaptativo",
    ("gatilho.direito.adaptativo", "sn30"): "gatilho.adaptativo",
    ("vibracao.rumble.ff", "dualsense"): "vibracao.rumble.esquerdo",
    ("vibracao.rumble.esquerdo", "pro"): "vibracao.rumble.ff",
    ("vibracao.rumble.esquerdo", "sn30"): "vibracao.rumble.ff",
    ("vibracao.rumble.direito", "pro"): "vibracao.rumble.ff",
    ("vibracao.rumble.direito", "sn30"): "vibracao.rumble.ff",
    ("movimento.acelerometro.jogo", "pro"): "movimento.giroscopio.jogo",
    ("movimento.acelerometro.jogo", "sn30"): "movimento.giroscopio.jogo",
    ("energia.bateria.leitura_hefesto", "dualsense"): "energia.bateria.percentual",
    ("energia.bateria.leitura_hefesto", "pro"): "energia.bateria.degraus",
    ("plataforma.probe.retry", "pro"): "plataforma.probe",
    ("plataforma.taxa_relatorios.botao", "pro"): "plataforma.taxa_relatorios",
    ("identidade.req_dev_info.fallback", "pro"): "identidade.req_dev_info",
}

#: O que os julgamentos dos pares órfãos deixaram gravado. Vai para `nota`, na
#: linha — e não dentro de `ressalva`, que é campo de medição e não se
#: reescreve. A ressalva de cada lado continua exatamente como estava.
NOTAS_DE_JULGAMENTO: dict[tuple[str, str], str] = {
    ("movimento.imu.perda", "pro"):
        "Par órfão CASADO por julgamento independente (confiança alta): as duas linhas "
        "citam o mesmo trecho (hid-nintendo.c:1718-1725) e a detecção é puro delta de "
        "tempo, sem consultar hdev->bus. O parêntese do lado do rádio era título de "
        "seção grudado pelo extrator, não outra feature. ATENÇÃO: o número é SÓ do "
        "rádio (07/08/2026); por cabo nunca se mediu nesta casa. E o que está gravado "
        "em offset é a constante JC_IMU_DROPPED_PKT_WARNING = 3, que não é offset.",
    ("audio.saida_dedicada", "pro"):
        "Par órfão CASADO por julgamento independente (confiança alta): é a mesma "
        "ausência vista por dois transportes, e cada linha já citava a contraparte do "
        "DualSense. ATENÇÃO: a leitura do registro BlueZ do Pro (UUIDs e Class of "
        "Device) NUNCA foi feita aqui — a medição de 07/08 que costuma ser citada é do "
        "DualSense e do DualShock 4, não do Pro.",
    ("entrada.botoes", "sn30"):
        "Par órfão CASADO por julgamento independente (confiança alta): "
        "procon_button_mappings é escolhido por TIPO de controle (hid-nintendo.c:2433-"
        "2437), nunca por barramento; o kernel não sabe publicar um subconjunto por "
        "rádio. O `parcial` do rádio é do link — cascata de timeouts até "
        "`joycon_enforce_subcmd_rate: exceeded max attempts`, com o bond de pé.",
    ("entrada.stick", "sn30"):
        "Par órfão CASADO por julgamento independente (confiança alta): "
        "joycon_config_left_stick/right_stick (hid-nintendo.c:2260-2290) são chamadas "
        "no ramo que decide por TIPO de controle, nunca por bus. O `parcial` do rádio "
        "é do link, não do eixo.",
    ("vibracao.rumble.ff", "sn30"):
        "Par órfão CASADO por julgamento independente (confiança alta): "
        "joycon_play_effect → joycon_set_rumble → report 0x10, sem ramo de barramento; "
        "só o ritmo muda (20 ms por cabo, 60 ms por rádio). O `parcial` do rádio vem de "
        "skip_tx_on_rate_exceeded=1, que DESCARTA o pacote quando não há janela de TX.",
    ("vibracao.rumble.frequencia", "sn30"):
        "Par órfão CASADO por julgamento independente (confiança alta): as duas linhas "
        "citam a mesma tabela joycon_rumble_frequencies (hid-nintendo.c:277-337). "
        "RESSALVA QUE VALE PARA OS DOIS TRANSPORTES e que o v1 gravou só no lado do "
        "cabo: SEM PROVA de que o SN30 Pro tenha atuadores lineares (HD de verdade) e "
        "não motores ERM comuns — ninguém mediu isso aqui.",
    ("gatilho.leitura", "dualsense"):
        "Par órfão casado pela regra do parêntese: o rótulo do cabo é o do rádio mais "
        "um parêntese que descreve o mecanismo daquele transporte. Não passou por "
        "julgamento individual — foi casado pela mesma forma dos seis que passaram.",
    ("audio.alto_falante.rota", "dualsense"):
        "Par órfão casado pela regra do parêntese: o rótulo do cabo é o do rádio mais "
        "um parêntese que descreve o mecanismo daquele transporte. Não passou por "
        "julgamento individual, mas é citado pelo nome no julgamento do par de áudio do "
        "Pro como o mesmo padrão.",
    ("audio.saida_dedicada", "dualsense"):
        "Par órfão casado pela regra do parêntese. O julgamento do par de áudio do Pro "
        "cita este par (linhas 190/191 do v1) e diz que a mesma chave deve servir: aqui "
        "a feature é genuinamente assimétrica — o cabo aceita, o rádio não.",
    ("vibracao.haptics_vcm", "dualsense"):
        "Par órfão casado pela regra do parêntese: o rótulo do cabo é o do rádio mais "
        "um parêntese que descreve o mecanismo daquele transporte. Não passou por "
        "julgamento individual — foi casado pela mesma forma dos seis que passaram.",
}

CABECALHO_V2 = [
    "chave", "controle", "familia", "rotulo", "peca", "evdev", "existe", "transporte",
    "cabo_aceita", "radio_aceita",
    "cabo_aciona", "radio_aciona",
    "cabo_canal", "radio_canal",
    "cabo_report_id", "radio_report_id",
    "cabo_offset", "radio_offset",
    "cabo_comando", "radio_comando",
    "cabo_de_onde_sei", "radio_de_onde_sei",
    "cabo_evidencia", "radio_evidencia",
    "cabo_codigo_ref", "radio_codigo_ref",
    "cabo_detalhe", "radio_detalhe",
    "cabo_ressalva", "radio_ressalva",
    "cabo_ate_onde_foi", "radio_ate_onde_foi",
    "cabo_feature_v1", "radio_feature_v1",
    "teste_que_morde", "mordida", "mordida_provada_em",
    "provado_em", "provado_por", "validade_dias",
    "assimetria_declarada", "estado_hoje",
    "nota", "id", "id_v1",
]

#: v1 → (coluna do v2 do lado cabo, coluna do v2 do lado rádio). O que estiver
#: aqui é conferido campo a campo pela prova; o que não estiver tem prova
#: própria (`id`, `controle`, `familia`, `feature`, `transporte`).
PARES_V1_V2 = {
    "aparelho_aceita": ("cabo_aceita", "radio_aceita"),
    "hefesto_aciona": ("cabo_aciona", "radio_aciona"),
    "canal": ("cabo_canal", "radio_canal"),
    "report_id": ("cabo_report_id", "radio_report_id"),
    "offset": ("cabo_offset", "radio_offset"),
    "comando": ("cabo_comando", "radio_comando"),
    "aparelho_confianca": ("cabo_de_onde_sei", "radio_de_onde_sei"),
    "aparelho_evidencia": ("cabo_evidencia", "radio_evidencia"),
    "codigo_ref": ("cabo_codigo_ref", "radio_codigo_ref"),
    "detalhe": ("cabo_detalhe", "radio_detalhe"),
    "ressalva": ("cabo_ressalva", "radio_ressalva"),
    "grau": ("cabo_ate_onde_foi", "radio_ate_onde_foi"),
    "feature": ("cabo_feature_v1", "radio_feature_v1"),
}
UNICOS_V1_V2 = ["teste_que_morde", "mordida", "mordida_provada_em", "provado_em",
                "provado_por", "validade_dias", "assimetria_declarada", "estado_hoje"]

ORDEM_EXISTE = {"sim": 3, "parcial": 2, "desconhecido": 1, "não": 0}
NOME_EXISTE = {3: "tem", 2: "parcial", 1: "desconhecido", 0: "nao-tem"}


# ── leitura dos desenhos ────────────────────────────────────────────────────
def ids_e_evdev(caminho: Path) -> tuple[set[str], dict[str, str]]:
    bruto = caminho.read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', bruto))
    evdev: dict[str, str] = {}
    for tag in re.findall(r"<[^>]*>", bruto):
        mi = re.search(r'\bid="([^"]+)"', tag)
        me = re.search(r'\bdata-evdev="([^"]+)"', tag)
        if mi and me:
            evdev[mi.group(1)] = me.group(1)
    return ids, evdev


def resolve_peca(texto: str, presentes: set[str]) -> str:
    baixo = texto.lower()
    for padrao, ids in ALVOS:
        if re.search(padrao, baixo):
            bons = [i for i in ids.split() if i in presentes]
            return " ".join(bons)
    return ""


# ── a migração ──────────────────────────────────────────────────────────────
def le_v1(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def confere_cobertura(linhas: list[dict]) -> None:
    faltam = sorted({(r["controle"], r["feature"]) for r in linhas
                     if (r["controle"], r["feature"]) not in CHAVES})
    if faltam:
        for c, f in faltam:
            print(f"  SEM CHAVE: ({c!r}, {f!r})", file=sys.stderr)
        raise SystemExit(f"{len(faltam)} linha(s) do v1 sem chave canônica — "
                         "migrar assim perderia medição")
    sem_rotulo = sorted(set(CHAVES.values()) - set(ROTULOS))
    if sem_rotulo:
        raise SystemExit(f"chaves sem rótulo: {sem_rotulo}")
    sobra = sorted(set(ROTULOS) - set(CHAVES.values()))
    if sobra:
        raise SystemExit(f"rótulos sem chave correspondente: {sobra}")


def agrupa(linhas: list[dict]) -> OrderedDict:
    """(chave, controle) → {'cabo': linha|None, 'radio': linha|None, ...}."""
    grao: OrderedDict = OrderedDict()
    for r in linhas:
        chave = CHAVES[(r["controle"], r["feature"])]
        g = grao.setdefault((chave, r["controle"]),
                            {"cabo": None, "radio": None, "origem": [], "v1": []})
        g["v1"].append(r)
        g["origem"].append(r["transporte"])
        if r["transporte"] == "usb":
            lados = ["cabo"]
        elif r["transporte"] == "bluetooth":
            lados = ["radio"]
        else:                       # ambos, nenhum → a linha vale para os dois
            lados = ["cabo", "radio"]
        for lado in lados:
            if g[lado] is not None:
                raise SystemExit(
                    f"colisão em {chave}@{r['controle']} lado {lado}: "
                    f"{g[lado]['id']} e {r['id']} disputam a mesma célula"
                )
            g[lado] = r
    return grao


def rotulo_transporte(origens: list[str]) -> str:
    o = sorted(set(origens))
    if o == ["bluetooth", "usb"]:
        return "cabo+rádio"
    if o == ["usb"]:
        return "só cabo"
    if o == ["bluetooth"]:
        return "só rádio"
    if o == ["ambos"]:
        return "ambos"
    if o == ["nenhum"]:
        return "nenhum"
    return "+".join(o)


def existe_de(valores: list[str]) -> str:
    """A resposta sobre o PLÁSTICO, a partir do que o aparelho aceita.

    Aceitar por qualquer transporte prova que a peça existe. Recusar pelos dois
    é a única evidência de ausência que o v1 tem. `desconhecido` continua
    `desconhecido` — é resposta, não buraco.
    """
    pesos = [ORDEM_EXISTE.get(v.strip(), 1) for v in valores if v.strip()]
    if not pesos:
        return "desconhecido"
    return NOME_EXISTE[max(pesos)]


def monta_v2(linhas: list[dict]) -> list[dict]:
    presentes = {}
    evdevs = {}
    for c, p in SVGS.items():
        presentes[c], evdevs[c] = ids_e_evdev(p)

    grao = agrupa(linhas)

    # existe por (controle, peça-da-chave) — para completar bloco de três sem
    # inventar. A peça da chave é `familia.peca`, os dois primeiros pedaços.
    por_peca: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (chave, ctl), g in grao.items():
        peca_chave = ".".join(chave.split(".")[:2])
        for r in g["v1"]:
            por_peca[(ctl, peca_chave)].append(r["aparelho_aceita"])

    existe_grao = {k: existe_de([r["aparelho_aceita"] for r in g["v1"]])
                   for k, g in grao.items()}

    saida = []
    for chave in sorted(set(CHAVES.values())):
        for ctl in CONTROLES:
            g = grao.get((chave, ctl))
            rot = ROTULOS[chave]
            fam = chave.split(".")[0]
            lin = {c: "" for c in CABECALHO_V2}
            lin["chave"] = chave
            lin["controle"] = ctl
            lin["familia"] = fam
            lin["rotulo"] = rot
            lin["id"] = f"{chave}@{ctl}"
            notas = []

            if g is None:
                # Bloco de três: a linha nasce mesmo sem medição, e diz isso.
                lin["transporte"] = "sem linha no v1"
                ver = VER_TAMBEM.get((chave, ctl), "")
                irmas = sorted({k[0] for k in grao if k[1] == ctl
                                and k[0] != chave
                                and k[0].startswith(".".join(chave.split(".")[:2]))})
                irmas_aceita = por_peca.get((ctl, ".".join(chave.split(".")[:2])), [])
                if ver and (ver, ctl) in existe_grao:
                    # A MESMA feature com outro nome: herdar é dizer a verdade.
                    lin["existe"] = existe_grao[(ver, ctl)]
                    notas.append(f"o v1 não tem linha desta chave para este controle; "
                                 f"a resposta mora em `{ver}` — `existe` foi herdado de lá")
                elif len(chave.split(".")) == 2:
                    # A chave É a peça: o que as irmãs aceitam responde por ela.
                    lin["existe"] = existe_de(irmas_aceita)
                    notas.append("o v1 não tem linha desta chave para este controle; "
                                 "`existe` vem das linhas irmãs da mesma peça")
                elif irmas_aceita and existe_de(irmas_aceita) == "nao-tem":
                    # A peça não existe, então o aspecto dela também não. É a
                    # única direção que a herança sustenta.
                    lin["existe"] = "nao-tem"
                    notas.append("o v1 não tem linha desta chave para este controle; "
                                 "`nao-tem` vem de a PEÇA não existir neste aparelho")
                else:
                    # A peça existe, mas ninguém mediu ESTE aspecto. Herdar aqui
                    # seria afirmar prova que não houve — a mentira que este
                    # mapa existe para impedir.
                    lin["existe"] = "desconhecido"
                    notas.append("o v1 não tem linha desta chave para este controle; "
                                 "a peça existe, mas ninguém mediu ESTE aspecto — "
                                 "herdar das irmãs seria afirmar prova que não houve")
                if irmas:
                    notas.append("irmãs: " + ", ".join(f"`{i}`" for i in irmas))
                lin["peca"] = resolve_peca(rot, presentes[ctl])
            else:
                lin["transporte"] = rotulo_transporte(g["origem"])
                lin["existe"] = existe_grao[(chave, ctl)]
                for lado in ("cabo", "radio"):
                    r = g[lado]
                    if r is None:
                        continue
                    for v1c, (cc, cr) in PARES_V1_V2.items():
                        lin[cc if lado == "cabo" else cr] = r[v1c]
                for u in UNICOS_V1_V2:
                    vals = {r[u] for r in g["v1"]}
                    lin[u] = " | ".join(sorted(v for v in vals if v.strip()))
                lin["id_v1"] = " | ".join(r["id"] for r in g["v1"])
                # a peça sai do texto MAIS RICO que a linha tem
                texto = max([r["feature"] for r in g["v1"]] + [rot], key=len)
                lin["peca"] = resolve_peca(texto, presentes[ctl])
                fams = sorted({r["familia"] for r in g["v1"]})
                if fams != [fam]:
                    notas.append("família no v1: " + ", ".join(fams))
                if lin["transporte"] == "só cabo":
                    notas.append("o v1 só tem a linha do cabo — o lado do rádio está "
                                 "VAZIO porque ninguém respondeu, não porque é não")
                if lin["transporte"] == "só rádio":
                    notas.append("o v1 só tem a linha do rádio — o lado do cabo está "
                                 "VAZIO porque ninguém respondeu, não porque é não")

            lin["evdev"] = " ".join(
                dict.fromkeys(evdevs[ctl][i] for i in lin["peca"].split()
                              if i in evdevs[ctl]))
            jul = NOTAS_DE_JULGAMENTO.get((chave, ctl))
            if jul:
                notas.insert(0, jul)
            lin["nota"] = " · ".join(notas)
            saida.append(lin)
    return saida


# ── a prova ─────────────────────────────────────────────────────────────────
def prova(v1: list[dict], v2: list[dict]) -> tuple[bool, list[str]]:
    """Confere campo a campo que nada das 204 linhas se perdeu."""
    porid = {lin["id"]: lin for lin in v2}
    falhas: list[str] = []
    conferidos = 0
    for r in v1:
        chave = CHAVES[(r["controle"], r["feature"])]
        alvo = porid.get(f"{chave}@{r['controle']}")
        if alvo is None:
            falhas.append(f"{r['id']}: sem linha no v2")
            continue
        if r["id"] not in alvo["id_v1"].split(" | "):
            falhas.append(f"{r['id']}: id não consta em id_v1")
        if r["controle"] != alvo["controle"]:
            falhas.append(f"{r['id']}: controle mudou")
        if r["familia"] != alvo["familia"] and r["familia"] not in alvo["nota"]:
            falhas.append(f"{r['id']}: família {r['familia']} não sobreviveu")
        lados = (["cabo"] if r["transporte"] == "usb"
                 else ["radio"] if r["transporte"] == "bluetooth"
                 else ["cabo", "radio"])
        for lado in lados:
            for v1c, (cc, cr) in PARES_V1_V2.items():
                col = cc if lado == "cabo" else cr
                if alvo[col] != r[v1c]:
                    falhas.append(f"{r['id']}: {v1c} != {col}")
                conferidos += 1
        for u in UNICOS_V1_V2:
            if r[u].strip() and r[u] not in alvo[u]:
                falhas.append(f"{r['id']}: {u} sumiu")
            conferidos += 1
        if r["transporte"] not in ("usb", "bluetooth") and \
                r["transporte"] not in alvo["transporte"]:
            falhas.append(f"{r['id']}: transporte {r['transporte']} não declarado")
    return not falhas, [*falhas, f"{conferidos} campos conferidos"]


# ── ensaios ─────────────────────────────────────────────────────────────────
def migra_ensaios(v1: list[dict]) -> tuple[list[dict], list[str]]:
    """O caderno aponta para o id antigo — sem isto os ensaios somem da tela.

    O `linha_id` passa a ser o id do grão, e o transporte, que morava no sufixo
    do id antigo, vira COLUNA. Ele não pode virar decoração: os sete ensaios da
    lightbar por rádio e o do cabo têm o MESMO suspeito e resultados opostos —
    é essa oposição que isolou a janela de 3,4 s. Se os dois lados caíssem no
    mesmo balde, o veredicto viraria `confuso` e o estudo de dezesseis dias
    voltaria para a estaca zero.
    """
    if not ENSAIOS.exists():
        return [], []
    de_para = {r["id"]: (CHAVES[(r["controle"], r["feature"])], r["controle"],
                         {"usb": "cabo", "bluetooth": "radio"}.get(r["transporte"], "ambos"))
               for r in v1}
    with open(ENSAIOS, encoding="utf-8", newline="") as fh:
        velhos = list(csv.DictReader(fh))
    novos, perdidos = [], []
    for e in velhos:
        alvo = de_para.get(e["linha_id"])
        if alvo is None:
            perdidos.append(e["linha_id"])
            novo = dict(e)
            novo["transporte"] = ""
            novo["linha_id_v1"] = e["linha_id"]
            novos.append(novo)
            continue
        chave, ctl, lado = alvo
        novo = dict(e)
        novo["linha_id"] = f"{chave}@{ctl}"
        novo["transporte"] = lado
        novo["linha_id_v1"] = e["linha_id"]
        novos.append(novo)
    return novos, perdidos


#: `resultado_da_feature` entrou em 13/08/2026, entre `resultado` e
#: `observado_por`: o `resultado` responde pelo SUSPEITO da linha, e há ensaio
#: em que as duas respostas são opostas sem que nenhuma esteja errada. Vazia
#: quer dizer "o `resultado` também responde pela feature", que é o caso de 76
#: dos 77 ensaios — por isso acrescentá-la não reescreveu medição nenhuma.
#: `degrau` entrou em 20/08/2026, logo depois de `transporte`, porque é o mesmo
#: tipo de eixo: o que a medição estava medindo. Vazio quer dizer "não declarou",
#: NUNCA "serve para tudo" — e é essa distinção que faz os dois degraus de
#: ENTRADA exigirem declaração explícita. Ver ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01: sem
#: ela o portão aceitava ensaio de acender lightbar como prova de que um JOGO
#: REAGIU, e foi reproduzido à mão.
CABECALHO_ENSAIOS = ["id", "linha_id", "transporte", "degrau", "quando", "suspeito",
                     "presente",
                     "resultado", "resultado_da_feature", "observado_por", "fonte",
                     "nota", "linha_id_v1"]


def escreve(caminho: Path, cabecalho: list[str], linhas: list[dict]) -> None:
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cabecalho, lineterminator="\n",
                           quoting=csv.QUOTE_MINIMAL, extrasaction="ignore")
        w.writeheader()
        for lin in linhas:
            w.writerow({c: lin.get(c, "") for c in cabecalho})


def main() -> int:
    ap = argparse.ArgumentParser(description="migra o mapa de canais para o v2")
    ap.add_argument("--provar", action="store_true",
                    help="não escreve nada: só refaz a conta e reprova se faltar campo")
    args = ap.parse_args()

    fonte = V1_GUARDADO if V1_GUARDADO.exists() else V1
    v1 = le_v1(fonte)
    confere_cobertura(v1)
    v2 = monta_v2(v1)
    ok, notas = prova(v1, v2)

    chaves = sorted(set(CHAVES.values()))
    print(f"  v1: {len(v1)} linhas, {len({(r['controle'], r['feature']) for r in v1})} "
          f"grupos (controle, feature)")
    print(f"  v2: {len(v2)} linhas, {len(chaves)} chaves x {len(CONTROLES)} controles")
    medidos = sum(1 for lin in v2 if lin["transporte"] != "sem linha no v1")
    print(f"      {medidos} com medição do v1 · {len(v2) - medidos} completando o "
          f"bloco de três")
    print(f"  prova: {notas[-1]}")
    if not ok:
        for f in notas[:-1]:
            print(f"    FALHA {f}", file=sys.stderr)
        print(f"  {len(notas) - 1} FALHA(S) — nada foi escrito", file=sys.stderr)
        return 1
    print("  prova: nenhum campo do v1 se perdeu")

    if args.provar:
        return 0

    if not V1_GUARDADO.exists():
        shutil.copy2(V1, V1_GUARDADO)
        print(f"  guardado: {V1_GUARDADO.relative_to(RAIZ)} (medição não se apaga)")
    if ENSAIOS.exists() and not ENSAIOS_GUARDADO.exists():
        shutil.copy2(ENSAIOS, ENSAIOS_GUARDADO)
        print(f"  guardado: {ENSAIOS_GUARDADO.relative_to(RAIZ)}")

    ens, perdidos = migra_ensaios(v1)
    escreve(V2, CABECALHO_V2, v2)
    print(f"  escrito: {V2.relative_to(RAIZ)} · {len(CABECALHO_V2)} colunas")
    if ens:
        escreve(ENSAIOS, CABECALHO_ENSAIOS, ens)
        alvos = sorted({(e["linha_id"], e["transporte"]) for e in ens})
        print(f"  escrito: {ENSAIOS.relative_to(RAIZ)} · {len(ens)} ensaios em "
              f"{len(alvos)} lado(s):")
        for lid, lado in alvos:
            n = sum(1 for e in ens if e["linha_id"] == lid and e["transporte"] == lado)
            print(f"      {lid} [{lado}] — {n} ensaio(s)")
    if perdidos:
        print(f"  AVISO: {len(perdidos)} ensaio(s) com linha_id sem correspondente: "
              f"{sorted(set(perdidos))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
