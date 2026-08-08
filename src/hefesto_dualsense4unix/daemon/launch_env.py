"""Materialização das envs de launch para o wrapper `hefesto-launch` (DEDUP-04).

A launch option persistida na Steam virou uma string CONSTANTE (o wrapper);
quem varia é ISTO aqui: arquivos `VAR=VAL` em
`~/.local/state/hefesto-dualsense4unix/launch_env/` que o daemon REGRAVA a
cada transição de estado e que o wrapper lê no momento do launch — depois de
passar no gate de vida (connect+ping IPC). Daemon morto/degradado => o
wrapper não exporta NADA e o jogo abre com o físico visível (pior caso:
controle duplicado, nunca zero controles).

Gatilhos de regravação (os três do sprint doc + o da revisão adversarial):
1. mudança de perfil/config (troca de máscara, liga/desliga emulação, Modo
   Nativo, `profile.switch`/`daemon.reload` via IPC);
2. transição de backend do vpad (uhid<->uinput — as promoções recriam o
   device via `start/stop_gamepad_emulation`, que chamam aqui; a falha TOTAL
   do start também regrava — daemon vivo sem vpad não pode deixar um IGNORE
   rançoso da sessão anterior no arquivo);
3. mudança do conjunto de jogadores do co-op (spawn/teardown de vpad);
4. mudança do CONJUNTO de perfis (save/delete/import pela GUI grava direto no
   disco — a GUI avisa via IPC `launch_env.refresh`, senão o
   `steam_app_<appid>.env` de um perfil novo ficaria ausente/rançoso na
   primeira sessão do jogo).

O conteúdo reflete o backend REAL agregado POR JOGADOR (espelha a
honestidade do `daemon_actions.compose_launch` histórico): QUALQUER vpad em
uinput/0ce6 => SEM `IGNORE_DEVICES` (esconder o físico com um vpad que a SDL
pode mapear errado deixaria um controle de botões trocados — ou nenhum —
como único; duplicado > zero controles).

Arquivos por appid: perfil com `steam_app_<appid>` no `window_class` ganha
`steam_app_<appid>.env` com a opinião DAQUELE perfil (o jogo é lançado ANTES
de a janela existir, então o autoswitch ainda não ativou o perfil — o
arquivo antecipa o modo que ele vai impor). Perfil sem opinião => sem
arquivo => o wrapper cai no `default.env` (máscara/backend globais atuais).
Resolução no MÍNIMO, sem UI de biblioteca de jogos.

JOGO-01 (25/07): o ramo da allowlist do Steam Input rotulava-se "sem dedup" e
era literalmente isso — omitia `SDL_GAMECONTROLLER_IGNORE_DEVICES` e
`PROTON_DISABLE_HIDRAW` e não fazia mais nada. Só que omitir o dedup COM o
gamepad virtual de pé é o próprio duplicado: medido ao vivo com UM DualSense
no cabo, o Mullet Mad Jack (2111190) enxergava js0=vpad e js2=físico (mais os
dois pads que o Steam Input cria), atribuía jogador 1 a um e jogador 2 ao
outro e metade dos comandos dela ia para o controle que o jogo não estava
lendo. O invariante que faltava, e que agora vale nos dois lados desta
fronteira: **um controle físico produz exatamente UM dispositivo de jogo**. A
allowlist muda QUAL dispositivo (o físico, falando com a Steam), nunca
QUANTOS — quem retira o vpad de cena enquanto o jogo da allowlist está em
sessão é `subsystems.gamepad.sync_steam_input_exception`, a partir do mesmo
appid que `steam_input_exception_appid` decide aqui.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import os
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Vars que o wrapper aceita exportar (allowlist ESPELHADA em
#: `assets/hefesto-launch.sh` — mudar aqui exige mudar lá). Qualquer outra
#: linha no arquivo é ignorada pelo wrapper (fail-safe contra arquivo
#: corrompido/adulterado exportando LD_PRELOAD e afins).
ENV_ALLOWLIST = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_JOYSTICK_HIDAPI",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS",
    "PROTON_DISABLE_HIDRAW",
    "__GL_SHADER_DISK_CACHE",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP",
)

#: MÁSCARA-01, entrega 3 — METADE SEGURA (07/08/2026): o par VID/PID do
#: DualSense FÍSICO. Ele estava cravado DENTRO das duas strings abaixo; agora é
#: o ÚNICO item de uma LISTA, e as duas strings são COMPOSTAS por
#: `compor_lista_vidpid`. O chamador continua passando só este par — a função
#: nasce testada e NÃO LIGADA. A condição para a lista crescer está escrita no
#: docstring dela, e não é hoje.
#:
#: Fonte canônica dos dois números: `integrations.uhid_gamepad`
#: (`DUALSENSE_VENDOR`/`DUALSENSE_PRODUCT`). Aqui eles são repetidos DE
#: PROPÓSITO: este módulo importa `uhid_gamepad` de forma LAZY (dentro de
#: `_env_for_profile`), e um import de topo criaria a aresta
#: `daemon -> integrations -> core` só para ler dois inteiros. Quem impede as
#: duas cópias de divergirem é um teste dedicado
#: (`tests/unit/test_launch_env_lista_vidpid.py`), não a boa vontade de quem
#: for editar.
PAR_DUALSENSE_FISICO = (0x054C, 0x0CE6)


def _par_vidpid(par: Any) -> tuple[int, int] | None:
    """`(vid, pid)` quando o par cabe em 16 bits cada; `None` quando não cabe.

    RECUSA em vez de corrigir. Um número fora da faixa formatado por `%04x`
    sai com CINCO dígitos, e o par seguinte gruda no anterior — o SDL leria um
    VID que ninguém pediu, e o winebus deixaria de casar a agulha certa.
    Descartar é o lado seguro da assimetria desta casa: um par A MENOS é o
    controle DUPLICADO (o pior caso aceito por escrito em
    `assets/hefesto-launch.sh` e `install.sh`); um par ERRADO a mais some com
    o controle de alguém.

    `bool` é `int` em Python e entraria aqui como 0/1 sem querer dizer isso —
    fica de fora de propósito.
    """
    try:
        vid, pid = par
    except (TypeError, ValueError):
        return None
    if isinstance(vid, bool) or isinstance(pid, bool):
        return None
    if not isinstance(vid, int) or not isinstance(pid, int):
        return None
    if not (0 <= vid <= 0xFFFF) or not (0 <= pid <= 0xFFFF):
        return None
    return vid, pid


def compor_lista_vidpid(pares: Iterable[tuple[int, int]], *, maiusculas: bool) -> str:
    """O VALOR de uma env de VID/PID, composto a partir de uma LISTA de pares.

    Formato: `0xVVVV/0xPPPP`, quatro dígitos hexadecimais com zero à esquerda,
    pares separados por VÍRGULA e mais nada (nem espaço). Lista vazia devolve
    string VAZIA, e quem chama tem de OMITIR a variável: `VAR=` no arquivo tem
    a mesma cara de quem escondeu alguém, e o `.env` é a primeira coisa que se
    lê ao diagnosticar um jogo que "enxerga controle demais".

    O FORMATO, e o grau de cada metade
    ----------------------------------

    `PROTON_DISABLE_HIDRAW` — **GRAU: MEDIDO** em 07/08/2026, no Proton 10
    instalado na máquina dela. O `is_hidraw_enabled` do
    `files/lib/wine/x86_64-windows/winebus.sys` monta a agulha com o molde
    WIDE `0x%04X/0x%04X` e procura com `wcscasestr` — busca de SUBSTRING, sem
    caixa. Daí: o prefixo `0x` e os quatro dígitos são OBRIGATÓRIOS (fazem
    parte da agulha), a CAIXA é indiferente e o SEPARADOR é livre, então a
    vírgula serve. O próprio Proton escreve uma lista assim no `proton:1828`
    (contorno do God of War Ragnarok no Deck):
    `0x054C/0x05C4,0x054C/0x09CC,0x054C/0x0BA0,0x054C/0x0CE6,0x054C/0x0DF2`.

    `SDL_GAMECONTROLLER_IGNORE_DEVICES` — **GRAU: SUSPEITA COM MECANISMO**
    (forte; nenhum parser do SDL foi executado). Três corroborações: o formato
    documentado do hint é lista separada por vírgula de `0xVID/0xPID`; a
    LaunchOptions DELA já foi estendida por vírgula, e o repositório tem regra
    escrita para não quebrar isso (`integrations/steam_launch_options.py:147`);
    e o Proton usa exatamente esse formato na env irmã. Medir o parser exigiria
    plantar um joystick falso em `/dev/input` na máquina dela, com três
    controles conectados e ela jogando — recusado, e é por isso que o grau
    para aqui.

    A CAIXA de cada valor não é enfeite
    -----------------------------------

    Minúsculas no IGNORE porque `integrations/steam_launch_options.py:97`
    compara a LaunchOptions envenenada contra o token LITERAL
    `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6`, byte a byte (**GRAU:
    MEDIDO**, é a `IGNORE_SIGNATURE`). Trocar a caixa aqui faria o `has_poison`
    deixar de reconhecer o veneno que as versões antigas persistiram — e
    veneno com o vpad fora de cena é ZERO controles. Maiúsculas no DISABLE por
    paridade com o que o próprio Proton escreve; ali a caixa é indiferente ao
    `wcscasestr`, então é preservação do que já roda, não exigência.

    O WRAPPER NÃO MUDA — e isto foi conferido
    -----------------------------------------

    **GRAU: MEDIDO** na leitura de `assets/hefesto-launch.sh`: a allowlist
    espelhada (`:85-91`) filtra por NOME de variável (`case "$line" in
    SDL_GAMECONTROLLER_IGNORE_DEVICES=*)`), nunca por valor; e o laço final
    (`:309-313`) passa cada linha INTEIRA como UM argumento do `env(1)`, sem
    word-split. Um valor com vírgulas atravessa literal. O aviso da sprint
    ("mudar de um lado exige mudar do outro") vale para NOME novo de variável,
    e nenhum nasce aqui.

    QUANDO ESTA LISTA PODE CRESCER — a condição, escrita
    ----------------------------------------------------

    Ela recebe um SEGUNDO par quando existir a `E4` da LUGAR-À-MESA-01
    (`docs/process/sprints/2026-08-06-LUGAR-A-MESA-01-tres-controles-ligados-e-um-jogador-so.md`),
    que é a **cobertura POR PAR**: *"o par só sai no `IGNORE` se TODO aparelho
    daquele par na mesa tiver vpad vivo"*. E a `E4` vem depois da `E3` (a
    adoção dos externos), que ela adiou até a máscara existir.

    O que a condição protege, MEDIDO naquela sprint: `054c:05c4` é o par do
    8BitDo em modo PS4 **e** o de um DualShock 4 Sony genuíno. Emitir esse par
    numa mesa onde o aparelho é um DS4 SEM vpad some com o controle da pessoa.
    Enquanto a cobertura por par não existir, esta função tem de continuar
    recebendo um par só — e é o que ela recebe.
    """
    molde = "0x%04X/0x%04X" if maiusculas else "0x%04x/0x%04x"
    vistos: set[tuple[int, int]] = set()
    saida: list[str] = []
    for par in pares:
        normal = _par_vidpid(par)
        if normal is None:
            logger.warning("launch_env_par_vidpid_descartado", par=str(par))
            continue
        if normal in vistos:
            continue
        vistos.add(normal)
        saida.append(molde % normal)
    return ",".join(saida)


def valor_ignore_devices(pares: Iterable[tuple[int, int]]) -> str:
    """Valor do `SDL_GAMECONTROLLER_IGNORE_DEVICES` para estes pares.

    Minúsculas — a caixa é contrato com o `IGNORE_SIGNATURE` do
    `steam_launch_options`, ver `compor_lista_vidpid`.
    """
    return compor_lista_vidpid(pares, maiusculas=False)


def valor_disable_hidraw(pares: Iterable[tuple[int, int]]) -> str:
    """Valor do `PROTON_DISABLE_HIDRAW` para estes pares.

    Maiúsculas — paridade com o que o próprio Proton escreve, ver
    `compor_lista_vidpid`.
    """
    return compor_lista_vidpid(pares, maiusculas=True)


#: O valor de HOJE, byte a byte: um par só, o do DualSense físico.
_IGNORE_VALUE = valor_ignore_devices((PAR_DUALSENSE_FISICO,))

#: GUERRA-01: lista VID/PID que o winebus.sys dos Protons 10/11 lê para NEGAR
#: hidraw (a whitelist default dele dá hidraw à família Sony INTEIRA — físico
#: 0ce6 E vpad 0df2 — e ignora a env do SDL). SÓ o físico entra aqui: o vpad
#: Edge 0df2 PRECISA do hidraw (é por ele que rumble/triggers/lightbar do
#: jogo chegam) — NUNCA incluir 0x0DF2. `PROTON_ENABLE_HIDRAW` morreu no
#: Proton 10 e foi aposentada (só AMPLIAVA exposição).
_DISABLE_HIDRAW_VALUE = valor_disable_hidraw((PAR_DUALSENSE_FISICO,))

#: UNIFICA-PREDICADO-01: o predicado "isto é janela de jogo da Steam?" DESCEU
#: para `profiles/steam_app.py` (stdlib pura, sem import do projeto) e é
#: REEXPORTADO daqui — os oito callsites históricos e os testes que importam
#: `daemon.launch_env.steam_appid_from_wm_class` continuam valendo sem tocar em
#: nada. A fonte desceu em vez de subir porque `profiles/simple_match.py` é
#: `profiles/` puro e importar `daemon.launch_env` de lá deixaria o ciclo
#: `profiles -> daemon -> profiles` a um commit de distância.

#: GUI-05 item 3 (honestidade do dedup): idade MÁXIMA, em segundos, do marker
#: `last_run` (gravado pelo wrapper no LAUNCH) em relação à PRIMEIRA detecção
#: da janela `steam_app_<appid>`. A janela serve para DESCARTAR markers de
#: sessões ANTIGAS (o jogo de ontem/horas atrás) — NÃO para limitar a latência
#: launch→janela: jogos pesados (Proton na 1ª execução, compilação de shaders,
#: RDR2 com o Rockstar Launcher) só abrem a janela `steam_app_N` minutos depois
#: do launch, e o marker legítimo desse launch ficaria fora de uma janela
#: curta, derrubando `wrapper_used` para false no MEIO do jogo (falso alarme
#: de "jogo sem wrapper"). Por isso 15 min: cobre o carregamento AAA mais lento
#: e ainda rejeita marker de uma sessão de verdade velha. Marker de outro
#: appid, ou ausente = o jogo NÃO passou pelo `hefesto-launch`.
WRAPPER_MARKER_WINDOW_SEC = 900.0

#: R-04 (auditoria 23/07): idade MÁXIMA, em segundos, do marker `last_run` para
#: ele contar como "launch ACONTECENDO AGORA" e disparar o arming do modo do
#: perfil. NÃO confundir com `WRAPPER_MARKER_WINDOW_SEC` (15 min), que responde
#: outra pergunta ("esta JANELA já aberta veio de um launch nosso?") e por isso
#: é generosa. Aqui a pergunta é "este marker é de um jogo SUBINDO agora?" — e a
#: resposta tem de ser curta, senão um `daemon.status` da CLI meia hora depois
#: rearmaria o perfil de um jogo que ela já fechou. O wrapper grava o marker e,
#: milissegundos depois, pede o ping de vida; a reconciliação do daemon roda a
#: 1 Hz. 60 s cobre com folga (inclusive um restart do daemon no meio do
#: carregamento) sem virar "arming retroativo".
LAUNCH_ARM_WINDOW_SEC = 60.0

#: JOGO-01: rótulo do `estado:` gravado no `steam_app_<appid>.env` dos jogos da
#: allowlist. O texto antigo ("allowlist Steam Input (sem dedup)") descrevia com
#: precisão o que o ramo fazia — e era exatamente o defeito: "sem dedup" com o
#: vpad de pé é o controle duplicado. O rótulo agora diz a REGRA que passou a
#: valer, porque este arquivo é a primeira coisa que se lê ao diagnosticar um
#: jogo que "enxerga quatro controles onde existe um".
ESTADO_ALLOWLIST_STEAM_INPUT = "allowlist Steam Input (físico é o único dispositivo)"


def _read_kv_int_fields(path: Path) -> dict[str, int]:
    """Lê um marker chave=valor (NUMÉRICO), best-effort — nunca levanta.

    Compartilhado por `read_last_run_marker`/`read_last_run_pid`/
    `read_last_exit_marker`: linhas desconhecidas ou com valor não-dígito
    são ignoradas silenciosamente (marker corrompido/adulterado não quebra
    o parse dos campos válidos). Arquivo ausente/ilegível devolve `{}`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    except Exception:  # defensivo: leitura de marker jamais derruba o IPC
        logger.debug("wrapper_marker_read_falhou", exc_info=True)
        return {}
    out: dict[str, int] = {}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        value = value.strip()
        if value.isdigit():
            out[key] = int(value)
    return out


def read_last_run_marker(base_dir: Path | None = None) -> tuple[int, int] | None:
    """Lê o marker `last_run` do wrapper: ``(appid, epoch)`` ou None.

    Formato (gravado por `assets/hefesto-launch.sh`, chave=valor por linha):
    ``appid=<int>`` + ``epoch=<unix epoch s>`` (+ `pid=<int>` OPCIONAL desde
    NUMA-01 — ignorado aqui, ver `read_last_run_pid`; o contrato de retorno
    deste `read_last_run_marker` fica intacto para os chamadores existentes,
    `wrapper_used_state` incluso). Tolerante a lixo: linhas desconhecidas
    são ignoradas; faltando qualquer um dos dois campos (ou valores
    não-numéricos), devolve None — quem consome trata como "wrapper nunca
    rodou". Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_run"
    fields = _read_kv_int_fields(path)
    appid = fields.get("appid")
    epoch = fields.get("epoch")
    if appid is None or epoch is None or appid <= 0:
        return None
    return appid, epoch


def read_last_run_pid(base_dir: Path | None = None) -> int | None:
    """Lê o campo `pid=` OPCIONAL do marker `last_run` (NUMA-01), ou None.

    `pid=$$` é gravado pelo wrapper no MOMENTO do launch — como `exec env
    "$@"` preserva o PID (o wrapper VIRA o jogo), este é o pid do próprio
    processo do jogo enquanto ele roda. Ausente (marker antigo, sem o
    campo) ou lixo (não-dígito) devolve None. Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_run"
    return _read_kv_int_fields(path).get("pid")


def read_last_exit_marker(base_dir: Path | None = None) -> int | None:
    """Lê o marker `last_exit` do wrapper: epoch (int) ou None (NUMA-01).

    Formato: ``epoch=<unix epoch s>`` (+ ``pid=<int>`` OPCIONAL desde a
    correção pós-auditoria, ver `read_last_exit_pid`), gravado pelo trap de
    EXIT do wrapper — best-effort e só cobre as saídas SEM `exec`
    bem-sucedido (o exec substitui o processo do wrapper pelo jogo; o trap
    de um shell que virou outro programa não existe mais para disparar).
    Serve para encurtar na prática a janela de "pid reuse" do `last_run`
    (ver riscos da síntese): um marker de saída mais novo que o `last_run`
    é evidência de que aquele launch específico NUNCA chegou a rodar o
    jogo — MAS só quando os dois pertencem ao MESMO launch (ver
    `read_last_exit_pid`/`wrapper_game_running`: sem essa correlação por
    pid, o `last_exit` de um launch A que falhou o próprio `exec` invalida
    o `last_run` de um launch B posterior e bem-sucedido, sempre que o trap
    tardio de A grava DEPOIS de B já ter sobrescrito o marker global —
    achado da auditoria da Onda N). Arquivo ausente/ilegível ou sem campo
    válido devolve None. Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_exit"
    return _read_kv_int_fields(path).get("epoch")


def read_last_exit_pid(base_dir: Path | None = None) -> int | None:
    """Lê o campo `pid=` OPCIONAL do marker `last_exit`, ou None.

    Correção pós-auditoria da Onda N: `last_run`/`last_exit` são arquivos
    GLOBAIS (não por appid/sessão) — dois wrappers concorrentes (um cujo
    `exec` FALHA, outro que lança o jogo com sucesso) escrevem nos MESMOS
    dois arquivos sem qualquer lock entre si. `pid=$$` é o PID do PRÓPRIO
    wrapper que gravou aquele `last_exit` (o mesmo `$$` que ele também
    gravou no seu `last_run`, ANTES do `exec` falhar) — correlacionar este
    pid com o `pid=` do `last_run` CORRENTE (`read_last_run_pid`) é o que
    permite a `wrapper_game_running` distinguir "este `last_exit` é do
    MESMO launch que o `last_run` atual" (invalida de verdade) de "este
    `last_exit` é de um launch ANTERIOR/outro, que só perdeu a corrida de
    escrita" (não invalida — o jogo do launch mais novo segue rodando).
    Ausente (marker antigo, sem o campo) ou lixo (não-dígito) devolve None
    — quem consome trata como "sem correlação possível" e cai no critério
    anterior, só por epoch. Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_exit"
    return _read_kv_int_fields(path).get("pid")


def pid_is_alive(pid: int | None) -> bool:
    """True quando `pid` é de um processo vivo agora (NUMA-01).

    `None`/`pid<=0` ⇒ False (sem pid, sem evidência). Usa `os.kill(pid, 0)`
    (não envia sinal nenhum, só sonda `/proc`): `ProcessLookupError` ⇒
    morto; `PermissionError` ⇒ vivo, mas de outro dono (ainda conta como
    vivo — o marker é do MESMO usuário do daemon na prática). Qualquer
    outro `OSError` degrada para False (fail-safe do lado do CHAMADOR:
    `wrapper_game_running` trata "não sei se vive" como "não conta" —
    quem quer o fail-safe do lado do JOGO é `classify`, via `unknown`
    explícito no gather, nunca aqui).
    """
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def wrapper_game_running(
    *,
    marker: tuple[int, int] | None,
    exit_marker: int | None,
    pid_alive: bool,
    marker_pid: int | None = None,
    exit_pid: int | None = None,
    now: float | None = None,
    window_sec: float = WRAPPER_MARKER_WINDOW_SEC,
) -> bool:
    """Decisão PURA: o marker do wrapper ainda atesta um jogo em execução?

    NUMA-01 — evidência #3 do sinal "jogo real ativo": marker `last_run`
    FRESCO (gravado até `window_sec` atrás de `now`) E `pid_alive` E sem
    `exit_marker` mais novo que o próprio marker (senão aquele launch já
    terminou/nunca decolou). Cobre a janela launch→janela (shaders/AAA,
    mesma constante generosa de `wrapper_used_state`), Wayland puro COM
    wrapper (não depende do detector de janela) e sobrevive a restart do
    daemon (o marker é do disco, não de memória). Nunca levanta.

    Correção pós-auditoria da Onda N (`last_run`/`last_exit` GLOBAIS, sem
    pid/sessão amarrando um ao outro): um `exit_marker` mais novo (ou
    igual) que `marker_epoch` só invalida o launch corrente quando
    `marker_pid`/`exit_pid` estão presentes E CASAM — ou seja, quando o
    `last_exit` pertence ao MESMO launch do `last_run` que está sendo
    avaliado. Sequência do achado: launch A grava `last_run` (epoch=E1,
    pid=P1) e o próprio `exec` FALHA; launch B (retry, ou outro jogo)
    grava `last_run` (epoch=E2>E1, pid=P2) com sucesso — P2 vivo rodando o
    jogo de verdade; o trap tardio de A só termina de gravar `last_exit`
    (epoch=E3>=E2) DEPOIS que B já sobrescreveu o marker. Sem a correlação
    por pid, `exit_marker(E3) >= marker_epoch(E2)` derrubava B mesmo com o
    jogo de B genuinamente vivo. Com `exit_pid=P1 != marker_pid=P2`, o
    `exit_marker` é reconhecido como de OUTRO launch e ignorado — o
    critério antigo (só por epoch) permanece como fallback quando qualquer
    um dos dois pids está ausente (markers gravados antes desta correção,
    ou leitura que falhou): fail-safe do lado conservador desta evidência
    específica (`classify` ainda tem os outros 2 ramos). Nunca levanta.
    """
    if marker is None:
        return False
    _, marker_epoch = marker
    moment = now if now is not None else time.time()
    if (moment - marker_epoch) > window_sec:
        return False
    if not pid_alive:
        return False
    if exit_marker is None or exit_marker < marker_epoch:
        return True
    if marker_pid is None or exit_pid is None:
        return False
    return exit_pid != marker_pid


def wrapper_used_state(
    *,
    appid: int,
    marker: tuple[int, int] | None,
    first_seen_epoch: float,
    window_sec: float = WRAPPER_MARKER_WINDOW_SEC,
) -> bool:
    """Decisão PURA do `wrapper_used` para um jogo detectado (GUI-05 item 3).

    ``appid`` = jogo cuja janela `steam_app_N` o detector viu;
    ``first_seen_epoch`` = epoch da PRIMEIRA detecção desse appid;
    ``marker`` = `(appid, epoch)` do `last_run` (ou None).

    True quando o marker é do MESMO appid e foi gravado até ``window_sec``
    ANTES da primeira detecção — o wrapper roda no launch, antes de a janela
    existir. Marker mais NOVO que a primeira detecção também conta (relaunch
    pelo wrapper com a leitura do detector ainda quente). O caso "sem jogo"
    (wm_class não é steam_app) é decidido pelo chamador (devolve None lá).
    """
    if marker is None:
        return False
    marker_appid, marker_epoch = marker
    if marker_appid != appid:
        return False
    return (first_seen_epoch - marker_epoch) <= window_sec


def steam_input_appids(path: Path | None = None) -> set[int]:
    """AppIDs da allowlist do Steam Input (`steam_input_apps.txt`) — R-06.

    A allowlist é opt-in EXPLÍCITO da usuária: jogos cuja via oficial de
    DualSense é o Steam Input per-app (medido: Mullet Mad Jack, appid 2111190,
    chama `SetDualSenseTriggerEffect` da API Steamworks, que só funciona com o
    Steam Input DAQUELE jogo ligado). Até aqui o arquivo só era lido pelo guard
    de VDF (`disable_steam_input.sh`/`storm_doctor`) — o caminho de LANÇAMENTO
    e o broker o ignoravam por completo, então o Hefesto continuava escondendo
    o hidraw do controle físico e a exceção que ela configurou era inerte.

    A leitura reusa `storm_doctor.steam_input_allowlist` (fonte única do
    formato: uma linha por appid, `#` comenta) e converte para int — appid é
    número; token não-numérico no arquivo é ignorado em vez de virar erro.

    O caminho default sai de `config_dir()` (XDG), como no
    `disable_steam_input.sh`, e não do `Path.home()` fixo do `storm_doctor` —
    assim os testes ficam herméticos com `XDG_CONFIG_HOME` e a leitura segue a
    convenção do resto do projeto.
    """
    try:
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            steam_input_allowlist,
        )
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        tokens = steam_input_allowlist(
            path if path is not None else config_dir() / "steam_input_apps.txt"
        )
    except Exception:  # arquivo ilegível/import quebrado: allowlist vazia
        logger.debug("steam_input_allowlist_indisponivel", exc_info=True)
        return set()
    out: set[int] = set()
    for token in tokens:
        limpo = str(token).strip()
        if limpo.isdigit():
            out.add(int(limpo))
    return out


def launch_session_appid(
    *, base_dir: Path | None = None, now: float | None = None
) -> int | None:
    """Appid do jogo lançado PELO WRAPPER que ainda está rodando, ou None.

    Reusa a decisão pura `wrapper_game_running` (NUMA-01) — marker fresco +
    pid vivo + sem `last_exit` correlacionado — em vez de reinventar o
    critério: o mesmo sinal que já sustenta `game_signal` é o que decide se a
    exceção do R-06 continua valendo. Sobrevive a alt-tab (o critério é o PID
    do jogo, não o foco) e a restart do daemon (o marker é do disco).
    """
    marker = read_last_run_marker(base_dir)
    if marker is None:
        return None
    marker_pid = read_last_run_pid(base_dir)
    vivo = wrapper_game_running(
        marker=marker,
        exit_marker=read_last_exit_marker(base_dir),
        pid_alive=pid_is_alive(marker_pid),
        marker_pid=marker_pid,
        exit_pid=read_last_exit_pid(base_dir),
        now=now,
    )
    return marker[0] if vivo else None


#: Classes de janela que NÃO são evidência de "outro app está na frente".
#: PARTIDA-PICOTADA-01: são os dois casos medidos no journal dela em 08/08 —
#: o backend não conseguiu ler (`unknown`/vazio) e a janela em foco ser a nossa
#: própria (ela abrindo o editor de perfil no meio da partida). Espelha
#: `autoswitch._tick_sem_informacao` e `autoswitch._janela_propria`; a lista de
#: classes da GUI vem de lá, para não haver duas verdades.
_CLASSES_CEGAS: frozenset[str] = frozenset({"", "unknown"})


def _leitura_cega(wm_class: str | None) -> bool:
    """True quando a leitura de janela não é evidência de app nenhum.

    PARTIDA-PICOTADA-01. Duas famílias, as duas medidas no journal dela:
    o detector não leu nada (`None`, vazio ou ``"unknown"``), ou a janela em
    foco é a desta própria aplicação. Nenhuma das duas é evidência de outro app
    em foco, e tratá-las como se fossem é o que picotava a partida.
    """
    if wm_class is None:
        return True
    normalizada = wm_class.strip().casefold()
    if normalizada in _CLASSES_CEGAS:
        return True
    # Importado aqui, e não no topo, porque `profiles.autoswitch` importa deste
    # módulo — subir o import quebraria o ciclo que `daemon/protocols.py` existe
    # para manter desfeito.
    from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

    return normalizada in OWN_GUI_WM_CLASSES


def steam_input_exception_appid(
    daemon: Any | None = None,
    *,
    base_dir: Path | None = None,
    now: float | None = None,
    allowlist: set[int] | None = None,
) -> int | None:
    """Appid da allowlist com sessão ATIVA agora (R-06), ou None.

    Duas evidências, nesta ordem — a mesma dupla que o plano pede
    ("marker `last_run` **ou** janela"):

    1. **marker do wrapper** (`launch_session_appid`): autoritativo e imune a
       alt-tab, mas só existe para jogo lançado pelo wrapper;
    2. **janela em foco** (`window_detect_current_class`): cobre o jogo aberto
       sem as LaunchOptions do Hefesto. Leitura CRUA de propósito: aqui a
       pergunta é "o jogo da allowlist está na frente agora?", e usar o sinal
       sticky faria a exceção sobreviver 30 s depois do alt-tab — tempo em que
       o físico ficaria exposto ao desktop sem motivo.

    `allowlist` é injetável para o chamador que já a leu (evita reler o
    arquivo em cada gate). Allowlist vazia ⇒ None sem tocar em disco de novo.

    JOGO-01: este appid deixou de decidir só "solto o grab e exponho o hidraw"
    e passou a decidir também "retiro o gamepad virtual de cena" (ver
    `gamepad.suspend_vpads_for_steam_input`). Por isso as duas evidências
    continuam sendo exatamente estas, e não uma janela mais folgada: enquanto
    esta função disser um appid, a usuária está SEM vpad — o sinal tem de
    apagar assim que o jogo sai da frente, não 30 s depois.

    PARTIDA-PICOTADA-01 (08/08/2026): "leitura crua" não pode significar
    "leitura CEGA derruba a exceção". A crueza existe para que um alt-tab de
    verdade apague o sinal na hora; ela **não** existe para que um tique sem
    informação faça o mesmo. A diferença é o defeito inteiro, e ele foi medido:
    em 08/08, entre 01:43 e 03:03, oito ciclos de suspender/retomar vpad no meio
    da partida dela, e **todos** os encerramentos vieram colados a um tique cego
    — `wm_class=unknown` (o backend não leu) ou a classe da PRÓPRIA janela desta
    aplicação, quando ela ia mexer na configuração. Nenhum deles é evidência de
    outro app em foco. O contraste fecha a conta: no sábado 01-02/08 foram 15 quedas de
    vpad em **48 h**; em 08/08, **12 em 1h25** — vinte e sete vezes mais.

    A cura é a mesma disciplina que o autoswitch já aplica em
    `_tick_sem_informacao` e `_janela_propria`, e é assimétrica de propósito:
    **só evidência POSITIVA de outra janela encerra a exceção.** Um tique cego
    ou a própria GUI não decidem nada — mantêm o que valia antes, consultando o
    sinal sticky (`window_detect_last_class`). O medo registrado no parágrafo
    acima — o físico exposto ao desktop 30 s depois do alt-tab — continua
    coberto, porque um alt-tab de verdade produz leitura POSITIVA da outra
    janela, e essa apaga a exceção no mesmo tique.
    """
    appids = allowlist if allowlist is not None else steam_input_appids()
    if not appids:
        return None
    sessao = launch_session_appid(base_dir=base_dir, now=now)
    if sessao is not None and sessao in appids:
        return sessao
    store = getattr(daemon, "store", None)
    wm_class = getattr(store, "window_detect_current_class", None)
    crua = wm_class if isinstance(wm_class, str) else None
    if _leitura_cega(crua):
        # Tique sem informação, ou a nossa própria janela: não é evidência de
        # nada. Cai no sticky — a última classe ÚTIL que o detector viu.
        sticky = getattr(store, "window_detect_last_class", None)
        crua = sticky if isinstance(sticky, str) else None
    foco = steam_appid_from_wm_class(crua)
    if foco is not None and foco in appids:
        return foco
    return None


def arm_launch_profile(
    daemon: DaemonProtocol,
    *,
    base_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Aplica o modo do perfil do jogo NO LAUNCH, não quando a janela aparece.

    R-04 (auditoria 23/07). O modo do perfil só existia quando o autoswitch
    via a JANELA — ou seja, com o jogo JÁ RODANDO e com a env dele já congelada
    no `exec` do wrapper. Duas consequências medidas:

    - a troca de máscara chegava tarde e DESTRUÍA/RECRIAVA os vpads com o jogo
      aberto, invalidando os handles que ele abriu (a Steam nunca reabre o
      hidraw do vpad do P1) — "o modo de jogar nunca é respeitado";
    - com o gate destrutivo do R-04 em `subsystems/gamepad.py`, essa troca
      tardia passa a ser RECUSADA — logo o arming não é enfeite: é o que faz o
      perfil valer desde o primeiro frame em vez de não valer nunca.

    O gatilho é o marker `last_run`, que o wrapper grava ANTES de qualquer
    outra coisa (inclusive antes do gate de vida por IPC) e ANTES do `exec`.
    O arming é idempotente por `(appid, epoch)`: um mesmo launch arma UMA vez,
    por mais vezes que a reconciliação rode.

    Ordem deliberada: a `.env` por appid NÃO depende deste arming — ela já é
    materializada com a opinião do perfil (e, desde o R-05, com o backend
    PROGNOSTICADO). Por isso o arming pode ser assíncrono ao ping do wrapper
    sem risco: o que ele conserta é a MÁSCARA, que o jogo só consulta segundos
    depois, ao enumerar os controles.

    Appid da allowlist do Steam Input NÃO tem a MÁSCARA armada (contradição 11
    do plano): a allowlist é opt-in explícito de "quem entrega a ENTRADA deste
    jogo é a Steam", e impor a máscara de um perfil ali seria contradizer a
    própria exceção — a máscara é justamente uma opinião sobre o dispositivo
    de entrada.

    NOTA DATADA — 07/08/2026. O parágrafo acima dizia que a allowlist é opt-in
    de *"o Hefesto sai de cena neste jogo"*, e essa leitura está **refutada
    pela metade** pela medição dela de 06/08 (`CONTROLE-SONY-MEDIDO-01`, seção
    *A INVERSÃO*, grau MEDIDO): o Hefesto sai da ENTRADA e **fica inteiro na
    saída** — os gatilhos dela seguraram e a cor dela ficou, com o jogo da
    lista aberto. A decisão de código NÃO muda (a máscara continua fora, e por
    um motivo agora mais preciso); o que muda é a frase que a descreve, e ela
    é a mesma que o estudo
    `docs/process/estudos/2026-08-06-desenho-a-flag-do-jogo-e-o-perfil-a-partir-da-biblioteca.md`
    (seção 5.3, item 2) já cobrava desta função.

    ALLOWLIST-SUPRESSAO-01 (auditoria 24/07): "sair de cena" era largo demais e
    engolia o que NÃO disputa nada com o jogo. O `return` antecipado da
    allowlist vinha ANTES de olhar o perfil, então o
    `suppress_desktop_emulation` — o "modo jogo", que só PARA o mouse/teclado
    emulados do desktop — nunca era aplicado nesses appids. O que a allowlist
    existe para evitar é o Hefesto ROUBAR o controle (máscara/grab/vpad); parar
    de mexer o cursor enquanto ela joga não rouba nada de ninguém. Agora a
    allowlist pula SÓ a seção `mode`; a supressão do perfil é aplicada
    normalmente.
    """
    marker = read_last_run_marker(base_dir)
    if marker is None:
        return None
    appid, epoch = marker
    moment = now if now is not None else time.time()
    if (moment - epoch) > LAUNCH_ARM_WINDOW_SEC:
        return None
    if getattr(daemon, "_launch_armed_for", None) == (appid, epoch):
        return None
    daemon._launch_armed_for = (appid, epoch)  # type: ignore[attr-defined]

    na_allowlist = appid in steam_input_appids()

    profile = None
    for candidato_appid, candidato in _steam_profiles(daemon):
        if candidato_appid == appid:
            profile = candidato
            break
    if profile is None:
        logger.info(
            "launch_arm_pulado_allowlist_steam_input"
            if na_allowlist
            else "launch_arm_sem_perfil",
            appid=appid,
        )
        return {
            "appid": appid,
            "armado": False,
            "motivo": "allowlist_steam_input" if na_allowlist else "sem_perfil",
        }

    # ALLOWLIST-SUPRESSAO-01: a supressão vem ANTES do desvio da allowlist —
    # ela vale para os dois caminhos. `origin="launch"` não fura o lock manual
    # (R-03): se ela alternou o modo jogo na mão nos últimos 30 s, o gesto dela
    # é mais novo que o perfil e o applier guarda/ignora sozinho.
    supressao: object | None = None
    aplicar_supressao = getattr(daemon, "apply_profile_suppression", None)
    if callable(aplicar_supressao):
        try:
            supressao = aplicar_supressao(
                bool(getattr(profile, "suppress_desktop_emulation", False)),
                profile=profile,
                origin="launch",
            )
        except Exception as exc:
            logger.warning(
                "launch_arm_supressao_falhou",
                appid=appid,
                profile=getattr(profile, "name", None),
                err=str(exc),
            )

    if na_allowlist:
        logger.info(
            "launch_arm_pulado_allowlist_steam_input",
            appid=appid,
            profile=getattr(profile, "name", None),
            supressao=supressao,
        )
        return {
            "appid": appid,
            "armado": False,
            "motivo": "allowlist_steam_input",
            "supressao": supressao,
        }

    mode = getattr(profile, "mode", None)
    if mode is None:
        # Perfil sem seção `mode` é ausência de opinião (R-02) — nada a armar.
        logger.info(
            "launch_arm_perfil_sem_modo", appid=appid,
            profile=getattr(profile, "name", None),
        )
        return {"appid": appid, "armado": False, "motivo": "perfil_sem_modo"}

    applier = getattr(daemon, "apply_profile_mode", None)
    if not callable(applier):
        return {"appid": appid, "armado": False, "motivo": "daemon_sem_applier"}
    logger.info(
        "launch_arm_modo_do_perfil",
        appid=appid,
        profile=getattr(profile, "name", None),
        kind=getattr(mode, "kind", None),
    )
    # `origin="launch"`: NÃO fura o lock manual (R-03) — se ela mexeu na
    # máscara nos últimos 30 s, o gesto dela é mais novo que o perfil e o
    # applier guarda a pendência sozinho. Só o gesto DELA fura o lock.
    resultado = applier(mode, profile=profile, origin="launch")
    # A máscara pode ter mudado: regrava as envs para o `default.env` refletir
    # o estado real (o arquivo por appid já vinha certo pelo `_env_for_profile`).
    materialize_launch_env(daemon)
    return {
        "appid": appid,
        "armado": True,
        "profile": getattr(profile, "name", None),
        "resultado": resultado,
    }


def compose_env(
    *,
    native_mode: bool,
    emulation_enabled: bool,
    flavor: str,
    backends: Sequence[str],
    fisicos: int = 0,
) -> dict[str, str]:
    """Envs de launch para UM estado do daemon. Pura e testável.

    GUERRA-01 (estudo 2026-07-18): o IGNORE do SDL só filtra o caminho SDL —
    o winebus dos Protons 10/11 dá hidraw à família Sony inteira POR DEFAULT
    e é por ESSE canal que o jogo continuava escrevendo no físico (a guerra
    de escritores de lightbar/rumble). A env moderna é `PROTON_DISABLE_HIDRAW`
    (lista VID/PID); `PROTON_ENABLE_HIDRAW` morreu no Proton 10.

    - Modo Nativo: NENHUMA env de hidraw — a whitelist default do winebus já
      expõe o físico Sony (Protons 10/11); esconder o físico aqui é
      exatamente o "zero controles" relatado ao vivo.
    - Xbox: `SDL_JOYSTICK_HIDAPI=0` (SDL lê o evdev, que o daemon graba) +
      IGNORE + DISABLE do físico (o vazamento winebus vale para qualquer
      máscara). O vpad é 045e — nunca colide com o 0ce6.
    - DualSense com TODOS os vpads em uhid (Edge 0df2 com hidraw real):
      DISABLE do físico + IGNORE — dedup no layout PS; o vpad segue com
      hidraw pleno pela whitelist default (NUNCA 0x0DF2 no DISABLE).
    - DualSense com QUALQUER vpad em uinput (degradado), emulação desligada
      ou sem vpad vivo: SÓ o preload de shaders. Duplicado > zero controles.

    O preload (`__GL_SHADER_*`) entra em toda variante: é inócuo e é a parte
    "carregamento completo" que o botão da GUI sempre prometeu.
    """
    env: dict[str, str] = {}
    # WRAPPER-EM-TODOS-01 (03/08/2026) — A COBERTURA, e por que ela é o portão.
    #
    # O `SDL_GAMECONTROLLER_IGNORE_DEVICES` esconde o DualSense físico do SDL
    # **por VID/PID** (`_IGNORE_VALUE`, um par cravado): ele some para TODOS os
    # controles daquele par de uma vez. Quem devolve cada um ao jogo é o vpad
    # correspondente. Logo, emitir o IGNORE sem haver um vpad por físico é
    # afirmar ao SDL algo falso — e o jogo fica com MENOS controles do que a
    # mesa tem.
    #
    # A decisão era pelo TIPO (`all(b == "uhid")`), nunca pela CONTAGEM. E o
    # `_snapshot` só listava vpads que EXISTEM: um jogador de co-op pendente
    # (aguardando o `EVIOCGRAB`, `vpad is None`) não entrava, e o `all(...)`
    # passava trivialmente sobre uma lista incompleta. Com 2 DualSense físicos
    # e 1 vpad vivo — exatamente o que o `EBUSY` de 02/08 produzia o tempo
    # todo — o IGNORE escondia os dois e só um voltava.
    #
    # Sem cobertura, cai no comportamento de sempre: o controle DUPLICADO, que
    # é o pior caso que a doutrina desta casa aceita por escrito
    # (`assets/hefesto-launch.sh`, `install.sh`) — nunca um jogo sem controle.
    # O `PROTON_DISABLE_HIDRAW` NÃO sai junto: ele impede o winebus de entregar
    # o hidraw do físico, e não esconde nada do SDL.
    # `fisicos == 0` significa "NÃO SEI", não "nenhum": o `_fisicos_na_mesa`
    # devolve 0 quando o backend não expõe `describe_controllers`
    # (`FakeController`, dublê de teste, backend legado) e nos prognósticos de
    # perfil, que montam env ANTES de haver controle na mão. Nesse caso mantém-se
    # o comportamento histórico (decidir pelo TIPO do vpad) — apertar sem
    # informação removeria o dedup de quem sempre o teve, que é regressão, não
    # cura. Só se exige cobertura quando se SABE quantos físicos há.
    cobertura_total = fisicos <= 0 or len(backends) >= fisicos
    # Modo Nativo: expõe o físico — sem DISABLE, sem IGNORE (whitelist default).
    if not native_mode and emulation_enabled and backends:
        if flavor == "xbox":
            env["SDL_JOYSTICK_HIDAPI"] = "0"
            env["PROTON_DISABLE_HIDRAW"] = _DISABLE_HIDRAW_VALUE
            if cobertura_total:
                env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        elif flavor == "dualsense" and all(b == "uhid" for b in backends):
            env["PROTON_DISABLE_HIDRAW"] = _DISABLE_HIDRAW_VALUE
            if cobertura_total:
                env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        # dualsense degradado (algum uinput) => sem IGNORE, de propósito.
        if not cobertura_total:
            logger.info(
                "launch_env_ignore_omitido_sem_cobertura",
                fisicos=fisicos,
                vpads=len(backends),
                motivo="um vpad por DualSense físico é requisito do IGNORE",
            )
    env["__GL_SHADER_DISK_CACHE"] = "1"
    env["__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"] = "1"
    # 8BIT-03: controles Nintendo (Pro/8BitDo modo Switch) mapeados por
    # POSIÇÃO física, como o resto do ecossistema PC espera — sem isso o SDL
    # segue as etiquetas Nintendo e A/B (e X/Y) chegam trocados ao jogo.
    # Inócua para DualSense/Xbox; entra em toda variante, como o preload.
    env["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] = "0"
    return env


def _fisicos_na_mesa(daemon: DaemonProtocol) -> int:
    """Quantos DualSense FÍSICOS estão conectados agora (0 se não der para saber).

    WRAPPER-EM-TODOS-01 (03/08/2026). O `_snapshot` abaixo sempre soube quantos
    VPADS existem e nunca soube quantos FÍSICOS há — e é a comparação entre os
    dois que decide se o `SDL_GAMECONTROLLER_IGNORE_DEVICES` pode sair.

    Zero na dúvida, e isso é deliberado: com zero, `compose_env` não emite o
    IGNORE, e o pior caso volta a ser o controle DUPLICADO, que é o que a
    doutrina desta casa aceita (`assets/hefesto-launch.sh`, `install.sh`).
    Nunca o contrário — um número otimista aqui esconde controle do jogo.
    """
    describe = getattr(getattr(daemon, "controller", None), "describe_controllers", None)
    if not callable(describe):
        return 0
    try:
        entradas = describe()
    except Exception:
        logger.debug("launch_env_fisicos_indisponiveis", exc_info=True)
        return 0
    if not isinstance(entradas, list):
        return 0
    return sum(
        1 for e in entradas if isinstance(e, dict) and e.get("connected")
    )


def _snapshot(daemon: DaemonProtocol) -> tuple[bool, bool, str, list[str], int]:
    """(native, emulation_enabled, flavor, backends dos vpads, físicos na mesa).

    WRAPPER-EM-TODOS-01: o quinto campo é novo. Sem ele, `compose_env` decidia
    pelo TIPO dos vpads (`all(b == "uhid")`) e nunca pela COBERTURA — e um
    jogador de co-op PENDENTE (aguardando o `EVIOCGRAB`, com `vpad is None`)
    simplesmente não entrava na lista, fazendo o `all(...)` passar
    trivialmente. Com 2 DualSense físicos e 1 vpad, o IGNORE escondia os DOIS
    por VID/PID e só UM voltava.
    """
    native = False
    with contextlib.suppress(Exception):
        native = bool(daemon.is_native_mode())
    cfg = getattr(daemon, "config", None)
    enabled = bool(getattr(cfg, "gamepad_emulation_enabled", False))
    flavor = str(getattr(cfg, "gamepad_flavor", "dualsense") or "dualsense")

    backends: list[str] = []
    primary = getattr(daemon, "_gamepad_device", None)
    if primary is not None:
        backends.append(str(getattr(primary, "backend", "") or ""))
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None)
    if isinstance(players, dict):
        for player in players.values():
            vpad = getattr(player, "vpad", None)
            if vpad is not None:
                backends.append(str(getattr(vpad, "backend", "") or ""))
    return native, enabled, flavor, backends, _fisicos_na_mesa(daemon)


def _load_profiles(daemon: DaemonProtocol) -> list[Any]:
    """Perfis do disco, best-effort ([] quando indisponível)."""
    try:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        return list(ProfileManager(controller=daemon.controller).list_profiles())
    except Exception:
        logger.debug("launch_env_perfis_indisponiveis", exc_info=True)
        return []


def _steam_profiles(daemon: DaemonProtocol) -> list[tuple[int, Any]]:
    """(appid, Profile) para cada perfil com `steam_app_<appid>` no match."""
    out: list[tuple[int, Any]] = []
    for profile in _load_profiles(daemon):
        match = getattr(profile, "match", None)
        for wc in getattr(match, "window_class", None) or []:
            appid = steam_appid_from_wm_class(str(wc))
            if appid is not None:
                out.append((appid, profile))
    return out


def _nativos_fora_da_antecipacao(profiles: Sequence[Any]) -> list[str]:
    """Nomes dos perfis nativo/desktop que a antecipação por-appid NÃO cobre.

    Achado MED da revisão adversarial da Fase 2: um perfil `kind=native|
    desktop` casado por `window_title_regex`/`process_name` (o próprio sprint
    UX recomenda "perfil para o launcher" por título) — ou por um
    `window_class` que não seja `steam_app_<id>` — não gera arquivo por appid,
    então o jogo lança pelo `default.env`. Se esse default carrega IGNORE, a
    sequência é determinística: a janela ganha foco → o autoswitch ativa o
    perfil nativo → a emulação cai → o vpad some e o físico continua escondido
    pelo IGNORE congelado na env do processo = ZERO controles. Quando existe
    ao menos um perfil assim, o `default.env` OMITE o IGNORE (conservador:
    duplicado > zero controles). Perfil coberto = só `steam_app_*` no
    window_class e nenhum outro critério (o arquivo por-appid antecipa o modo
    dele). `MatchAny` com modo nativo/desktop conta como arriscado.
    """
    out: list[str] = []
    for profile in profiles:
        kind = getattr(getattr(profile, "mode", None), "kind", None)
        if kind not in ("native", "desktop"):
            continue
        match = getattr(profile, "match", None)
        wcs = [str(wc) for wc in getattr(match, "window_class", None) or []]
        coberto = (
            bool(wcs)
            and all(steam_appid_from_wm_class(wc) is not None for wc in wcs)
            and not getattr(match, "window_title_regex", None)
            and not (getattr(match, "process_name", None) or [])
        )
        if not coberto:
            out.append(str(getattr(profile, "name", "?")))
    return out



def _permite_uhid(daemon: Any) -> bool:
    """Gate VPAD-08 da factory, tolerante a dublês (R-05).

    `controller_allows_uhid` mora em `subsystems.gamepad`; importar no topo
    criaria ciclo, e um daemon dublado em teste pode não ter a superfície que
    ele espera. Na dúvida, False = prognóstico conservador.
    """
    try:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            controller_allows_uhid,
        )

        return bool(controller_allows_uhid(daemon))
    except Exception:
        return False


def _env_for_profile(
    profile: Any,
    *,
    flavor_atual: str,
    backends: list[str],
    permite_uhid: bool = False,
) -> tuple[dict[str, str], str] | None:
    """(env, motivo) antecipando o modo que o perfil impõe; None = sem opinião.

    Perfil `mode=None` não materializa arquivo próprio — o wrapper cai no
    `default.env`. `kind=gamepad` com máscara dualsense usa os backends
    REAIS atuais (se a emulação está desligada agora, não dá para garantir
    uhid no futuro => conservador, sem IGNORE).
    """
    mode = getattr(profile, "mode", None)
    if mode is None:
        return None
    kind = getattr(mode, "kind", None)
    if kind == "native":
        return (
            compose_env(
                native_mode=True, emulation_enabled=False,
                flavor=flavor_atual, backends=[],
            ),
            "perfil nativo",
        )
    if kind == "desktop":
        return (
            compose_env(
                native_mode=False, emulation_enabled=False,
                flavor=flavor_atual, backends=[],
            ),
            "perfil desktop",
        )
    if kind == "gamepad":
        flavor = str(getattr(mode, "gamepad_flavor", None) or flavor_atual)
        if flavor == "xbox":
            # O vpad Xbox é uinput 045e POR DESIGN — o IGNORE é seguro
            # independente do estado atual (invariante VPAD-06).
            return (
                compose_env(
                    native_mode=False, emulation_enabled=True,
                    flavor="xbox", backends=["uinput"],
                ),
                "perfil gamepad xbox",
            )
        # R-05 (auditoria 23/07): quando o perfil pede uma máscara DIFERENTE da
        # vigente, os `backends` recebidos são os do vpad ATUAL — que é de outro
        # flavor e não descreve o que vai existir quando o perfil ativar.
        #
        # Caso medido: máscara global em `xbox` (vpad uinput) e o Sackboy com
        # perfil `dualsense`. O `steam_app_1599660.env` saía SEM
        # `SDL_GAMECONTROLLER_IGNORE_DEVICES` e SEM `PROTON_DISABLE_HIDRAW`,
        # porque "uinput" não autoriza o dedup — ou seja, o arquivo por-appid
        # ficava estritamente PIOR que o `default.env`, e o jogo abria vendo o
        # DualSense físico junto com o virtual (o controle duplicado).
        #
        # A correção é PROGNOSTICAR o backend com os MESMOS gates da factory,
        # em vez de herdar o do vpad de outro flavor.
        #
        # A assimetria de risco favorece o prognóstico: se ele errar, o vpad cai
        # para uinput Edge `0x0DF2`, que NÃO está na lista do IGNORE
        # (`0x054c/0x0ce6`) — o pior caso é mapeamento SDL menos validado, nunca
        # "zero controles".
        backends_efetivos = backends
        motivo = "perfil gamepad dualsense (backends reais)"
        if flavor != flavor_atual or not backends:
            from hefesto_dualsense4unix.integrations.uhid_gamepad import uhid_available

            prognostico_uhid = uhid_available() and permite_uhid
            backends_efetivos = ["uhid"] if prognostico_uhid else backends
            motivo = (
                "perfil gamepad dualsense (prognóstico uhid)"
                if prognostico_uhid
                else "perfil gamepad dualsense (prognóstico conservador)"
            )
        return (
            compose_env(
                native_mode=False, emulation_enabled=True,
                flavor=flavor, backends=backends_efetivos,
            ),
            motivo,
        )
    return None


def _render(env: dict[str, str], estado: str) -> str:
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# Materializado pelo daemon do Hefesto (DEDUP-04). Não edite:",
        "# é regravado a cada transição de estado do gamepad virtual.",
        f"# estado: {estado} | {ts}",
    ]
    lines.extend(f"{key}={value}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava `default.env` + `steam_app_<appid>.env` com o estado REAL.

    Best-effort e barata (arquivos de ~200 B): NUNCA propaga exceção — o
    wrapper degrada sozinho para "nenhuma env" quando o arquivo falta; a
    materialização quebrada não pode derrubar o start da emulação.
    """
    try:
        target = launch_env_dir(ensure=True)
        native, enabled, flavor, backends, fisicos = _snapshot(daemon)
        estado = (
            f"native={native} emulacao={enabled} mascara={flavor} "
            f"backends={backends or '[]'}"
        )
        # DEDUP-06: o log de "dedup quebrada" mora AQUI, na borda de
        # materialização (transição de estado) — nunca no state_full de 20 Hz.
        # O `dedup_ok` por jogador que a GUI/doctor consomem sai do IPC.
        if (
            not native
            and enabled
            and flavor == "dualsense"
            and backends
            and any(b != "uhid" for b in backends)
        ):
            logger.warning("dedup_broken", motivo="vpad_uinput", backends=backends)
        default_env = compose_env(
            native_mode=native,
            emulation_enabled=enabled,
            flavor=flavor,
            backends=backends,
            # WRAPPER-EM-TODOS-01: este é o ÚNICO chamador com o estado real da
            # mesa; os demais montam prognóstico de perfil (backends
            # antecipados, sem controle na mão) e ficam no default 0, que é
            # o conservador — sem cobertura provada, sem IGNORE.
            fisicos=fisicos,
        )
        if "SDL_GAMECONTROLLER_IGNORE_DEVICES" in default_env:
            arriscados = _nativos_fora_da_antecipacao(_load_profiles(daemon))
            if arriscados:
                # Perfil nativo/desktop fora do alcance da antecipação por
                # appid: o IGNORE congelado no default.env viraria zero
                # controles quando o autoswitch ativasse esse perfil (ver
                # `_nativos_fora_da_antecipacao`). Duplicado > zero.
                del default_env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
                estado += " ignore_omitido=perfil_nativo_sem_appid"
                logger.info(
                    "launch_env_ignore_omitido_por_perfil_nativo",
                    perfis=arriscados,
                )
        _write_atomic(target / "default.env", _render(default_env, estado))
        desired = {"default.env"}
        for appid, profile in _steam_profiles(daemon):
            per_profile = _env_for_profile(
                profile,
                flavor_atual=flavor,
                backends=backends,
                # R-05: o prognóstico do backend precisa do MESMO gate que a
                # factory usa (VPAD-08 — o modo fake não pode plantar um Edge
                # real no kernel).
                permite_uhid=_permite_uhid(daemon),
            )
            if per_profile is None:
                continue
            env, motivo = per_profile
            name = f"steam_app_{appid}.env"
            _write_atomic(target / name, _render(env, f"{motivo} | {estado}"))
            desired.add(name)
        # R-06 (auditoria 23/07): a allowlist do Steam Input é fonte de verdade
        # do launch — e VENCE (contradição 11 do plano). Ela é opt-in EXPLÍCITO
        # da usuária para "neste jogo o DualSense é entregue pela Steam"; nesse
        # caso esconder o físico (IGNORE do SDL + PROTON_DISABLE_HIDRAW) mata
        # exatamente a via que ela pediu. O arquivo nasce mesmo SEM perfil
        # (antes o jogo caía no `default.env`, que carrega o dedup) e sobrescreve
        # de propósito o arquivo derivado de perfil do mesmo appid — daí este
        # laço vir DEPOIS do de perfis.
        #
        # `native_mode=True` aqui não liga o Modo Nativo do daemon: é só o ramo
        # de `compose_env` que produz "nenhuma env de hidraw", que é exatamente
        # a semântica pedida (o preload de shaders e o rótulo de botões seguem,
        # como em toda variante).
        #
        # JOGO-01: a env continua a MESMA — e agora ela é honesta. Omitir o
        # IGNORE só está certo porque o gamepad virtual sai de cena enquanto o
        # jogo da allowlist estiver em sessão (`gamepad.sync_steam_input_
        # exception`): o físico passa a ser o único dispositivo, e escondê-lo
        # aqui seria zero controles. Enquanto o par não era par — env sem dedup
        # + vpad de pé — cada metade estava certa isoladamente e o resultado era
        # o duplicado que o jogo dividia entre dois jogadores.
        for appid in sorted(steam_input_appids()):
            name = f"steam_app_{appid}.env"
            env_allow = compose_env(
                native_mode=True,
                emulation_enabled=False,
                flavor=flavor,
                backends=[],
            )
            _write_atomic(
                target / name,
                _render(env_allow, f"{ESTADO_ALLOWLIST_STEAM_INPUT} | {estado}"),
            )
            desired.add(name)
        for stale in target.glob("steam_app_*.env"):
            if stale.name not in desired:
                with contextlib.suppress(OSError):
                    stale.unlink()
        logger.info(
            "launch_env_materializado",
            native=native,
            emulacao=enabled,
            mascara=flavor,
            backends=backends,
            arquivos=len(desired),
        )
    except Exception:
        logger.warning("launch_env_materialize_falhou", exc_info=True)


__all__ = [
    "ENV_ALLOWLIST",
    "ESTADO_ALLOWLIST_STEAM_INPUT",
    "LAUNCH_ARM_WINDOW_SEC",
    "PAR_DUALSENSE_FISICO",
    "WRAPPER_MARKER_WINDOW_SEC",
    "arm_launch_profile",
    "compor_lista_vidpid",
    "compose_env",
    "launch_session_appid",
    "materialize_launch_env",
    "pid_is_alive",
    "read_last_exit_marker",
    "read_last_exit_pid",
    "read_last_run_marker",
    "read_last_run_pid",
    "steam_appid_from_wm_class",
    "steam_input_appids",
    "steam_input_exception_appid",
    "valor_disable_hidraw",
    "valor_ignore_devices",
    "wrapper_game_running",
    "wrapper_used_state",
]
