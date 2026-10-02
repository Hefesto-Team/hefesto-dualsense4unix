"""O nome de cada dongle, e a costura que o produto põe por cima.

Este arquivo é PURO: nenhuma linha importa `gi`, nenhuma fala com o BlueZ real.
O D-Bus é DUBLADO — um `busctl` de mentira que responde de um dicionário — e o
sysfs entra por leitor injetado. Nada aqui toca `/sys`, `/dev` ou o barramento
de sistema da máquina de quem roda a suíte.

A MORDIDA, feita em 22/08/2026 e registrada aqui porque teste que passa com a
cura arrancada não testa nada. Foram QUATRO, uma por cura:

1. **a costura do prefixo.** Arranquei o ramo do prefixo de
   `_alias_sem_tesoura` (o `return f"{PREFIXO_NINTENDO} {limpo}"` virou
   `return limpo`). Reprovaram DEZ nós, entre eles
   `test_nome_sem_prefixo_em_adaptador_com_pro_sai_costurado` e
   `test_a_mesa_desta_bancada_costura_o_adaptador_do_pro_e_so_ele` — o
   adaptador do Pro passou a receber `"Sala"` puro, que é o alias que derruba o
   Pro sob carga. Devolvi e voltaram ao verde.

2. **a condição da limpeza.** Tirei o `if not hospeda_nintendo: return texto`
   de `limpar_o_nome`, deixando a limpeza incondicional. Reprovaram QUATRO,
   entre eles `test_o_nome_dela_nao_e_comido_no_segundo_salvamento` —
   `"Nintendo do sofá"` num dongle SEM Pro voltou como `"do sofá"`, e o segundo
   salvamento gravaria `"do sofá"`, comendo uma palavra que ela escreveu.

3. **o teto de bytes — e a régua que não mordia nada.** Troquei `TETO_DE_BYTES`
   de 247 para 4096 e a suíte passou VERDE: os dois testes do teto importavam a
   constante do próprio módulo, então conferiam o produto contra o produto. A
   régua foi trocada por `TETO_MEDIDO_NO_BLUEZ = 247`, escrito à mão a partir
   da medição ao vivo. Com a régua certa, a mesma mordida reprovou os dois:
   `assert 809 <= 247` em
   `test_o_corte_come_a_cauda_e_nunca_o_prefixo`. Fica registrado porque o erro
   é o de sempre: teste que itera a mesma lista que deveria conferir.

4. **a identidade por endereço.** Fiz `renomear_o_dongle` montar o caminho pela
   POSIÇÃO na tabela (`f"/org/bluez/hci{indice_na_tabela}"`, o palpite de que a
   ordem por endereço acompanha o índice) em vez de usar o objeto lido agora.
   Reprovou `test_a_escrita_e_por_endereco_e_nao_pelo_indice_do_boot`: com a
   árvore invertida entre boots, o nome foi parar em `aa:bb:cc:00:00:11` em vez
   de `aa:bb:cc:00:00:33`. É a cicatriz do `bt_health_watchdog.sh`, viva.

A MESA QUE ESTES TESTES REPRODUZEM é a desta bancada em 22/08/2026, com os
endereços trocados pela faixa sintética `aa:bb:cc:`: três adaptadores idênticos,
quatro DualSense e um Pro Controller, todos no rádio, distribuídos 1/2/2 — e o
Pro no SEGUNDO adaptador, que é o detalhe que faz o defeito aparecer.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    NINTENDO_REAL_OUI,
)
from hefesto_dualsense4unix.integrations.apelido_do_dongle import (
    OUIS_NINTENDO,
    PREFIXO_NINTENDO,
    Dongle,
    adaptadores_com_nintendo,
    costurar_a_mesa,
    costurar_o_nome,
    ler_os_dongles,
    limpar_o_nome,
    renomear_o_dongle,
)


UM = "aa:bb:cc:00:00:11"
DOIS = "aa:bb:cc:00:00:22"
TRES = "aa:bb:cc:00:00:33"

PRO = "aa:bb:cc:00:00:aa"
DS_UM = "aa:bb:cc:00:00:b1"
DS_DOIS = "aa:bb:cc:00:00:b2"
DS_TRES = "aa:bb:cc:00:00:b3"
DS_QUATRO = "aa:bb:cc:00:00:b4"

#: O `HID_PHYS` REAL de um DualSense no CABO nesta máquina, lido do uevent em
PHYS_DO_CABO = "usb-0000:0c:00.3-1/input3"

TETO_MEDIDO_NO_BLUEZ = 247

ALIAS_INICIAL = {
    UM: "Nintendo MeowSystem",
    DOIS: "MeowSystem #2",
    TRES: "MeowSystem #3",
}


def _uevent(*, nome: str, phys: str, uniq: str) -> str:
    """Um uevent de nó hidraw, no formato exato que o kernel publica."""
    return (
        "DRIVER=hid-generic\n"
        "HID_ID=0005:0000054C:00000CE6\n"
        f"HID_NAME={nome}\n"
        f"HID_PHYS={phys}\n"
        f"HID_UNIQ={uniq}\n"
    )


#: A mesa medida: 1 DualSense em UM, 1 DualSense + o Pro em DOIS, 2 em TRES,
#: mais um DualSense no cabo que não pertence a adaptador nenhum.
UEVENTS = {
    "hidraw0": _uevent(
        nome="DualSense Wireless Controller", phys=UM, uniq=DS_UM
    ),
    "hidraw1": _uevent(
        nome="DualSense Wireless Controller", phys=DOIS, uniq=DS_DOIS
    ),
    "hidraw2": _uevent(nome="Pro Controller", phys=DOIS, uniq=PRO),
    "hidraw3": _uevent(
        nome="DualSense Wireless Controller", phys=TRES, uniq=DS_TRES
    ),
    "hidraw4": _uevent(
        nome="DualSense Wireless Controller", phys=TRES, uniq=DS_QUATRO
    ),
    "hidraw5": _uevent(
        nome="DualSense Wireless Controller",
        phys=PHYS_DO_CABO,
        uniq=DS_QUATRO,
    ),
}


class BusDublado:
    """Um `busctl` de mentira — a árvore, as propriedades e a escrita."""

    def __init__(
        self,
        aliases: dict[str, str] | None = None,
        *,
        ordem: Sequence[str] = (UM, DOIS, TRES),
        sem_busctl: bool = False,
    ) -> None:
        self.aliases = dict(ALIAS_INICIAL if aliases is None else aliases)
        self.ordem = list(ordem)
        self.sem_busctl = sem_busctl
        self.escritas: list[tuple[str, str]] = []

    def _objeto(self, endereco: str) -> str:
        return f"/org/bluez/hci{self.ordem.index(endereco)}"

    def _endereco(self, objeto: str) -> str:
        return self.ordem[int(objeto.rsplit("hci", 1)[1])]

    def __call__(self, argumentos: Sequence[str]) -> str | None:
        if self.sem_busctl:
            return None
        if list(argumentos[:1]) == ["tree"]:
            corpo = "\n".join(self._objeto(e) for e in self.ordem)
            return f"/org/bluez\n{corpo}\n"
        if argumentos[0] == "get-property":
            _, _, objeto, _, propriedade = argumentos
            endereco = self._endereco(objeto)
            if propriedade == "Address":
                return _json(endereco.upper())
            if propriedade == "Alias":
                return _json(self.aliases[endereco])
            if propriedade == "Name":
                return _json("MeowSystem")
            if propriedade == "Powered":
                return json.dumps({"type": "b", "data": True})
            raise AssertionError(f"propriedade não prevista: {propriedade}")
        if argumentos[0] == "set-property":
            _, _, objeto, _, propriedade, _, valor = argumentos
            assert propriedade == "Alias"
            endereco = self._endereco(objeto)
            self.aliases[endereco] = valor
            self.escritas.append((endereco, valor))
            return ""
        raise AssertionError(f"chamada não prevista: {argumentos!r}")


def _json(valor: str) -> str:
    return json.dumps({"type": "s", "data": valor})


def _sysfs(uevents: dict[str, str] | None = None):
    """`listar` e `ler` de mentira sobre `/sys/class/hidraw`."""
    tabela = UEVENTS if uevents is None else uevents

    def listar(raiz: str) -> list[str]:
        assert raiz == "/sys/class/hidraw"
        return sorted(tabela)

    def ler(caminho: str) -> str:
        for no, texto in tabela.items():
            if caminho == f"/sys/class/hidraw/{no}/device/uevent":
                return texto
        return ""

    return listar, ler


def _mesa(bus: BusDublado, uevents: dict[str, str] | None = None):
    listar, ler = _sysfs(uevents)
    return {"executar": bus, "listar": listar, "ler": ler}


def test_nome_sem_prefixo_em_adaptador_com_pro_sai_costurado() -> None:
    """Adaptador que hospeda Pro: o que vai ao BlueZ começa com "Nintendo"."""
    assert costurar_o_nome("Sala", hospeda_nintendo=True) == "Nintendo Sala"


def test_nome_sem_prefixo_em_adaptador_sem_pro_sai_limpo() -> None:
    """Sem Nintendo na mesa, o produto não acrescenta palavra nenhuma."""
    assert costurar_o_nome("Sala", hospeda_nintendo=False) == "Sala"


def test_o_prefixo_e_prefixo_e_nao_sufixo() -> None:
    """O firmware do Pro casa o COMEÇO do nome — `Nintendo*`."""
    alias = costurar_o_nome("Sofá da Vitória", hospeda_nintendo=True)
    assert alias.startswith(PREFIXO_NINTENDO)
    assert alias.endswith("Sofá da Vitória")


def test_a_costura_e_idempotente() -> None:
    """O `bt_active_mode.sh` roda a cada tique da vigia — o nome não cresce."""
    alias = costurar_o_nome("Sala", hospeda_nintendo=True)
    for _ in range(5):
        alias = costurar_o_nome(alias, hospeda_nintendo=True)
    assert alias == "Nintendo Sala"


def test_nome_vazio_com_pro_ainda_protege() -> None:
    """Alias vazio manda o BlueZ VOLTAR ao nome do sistema — e perder a cura."""
    assert costurar_o_nome("", hospeda_nintendo=True) == PREFIXO_NINTENDO
    assert costurar_o_nome("   ", hospeda_nintendo=True) == PREFIXO_NINTENDO


def test_nome_vazio_sem_pro_continua_vazio() -> None:
    """Sem Pro não há o que proteger: vazio é vazio, e o BlueZ que decida."""
    assert costurar_o_nome("", hospeda_nintendo=False) == ""


def test_a_tela_mostra_o_nome_dela_sem_a_costura() -> None:
    assert limpar_o_nome("Nintendo Sala", hospeda_nintendo=True) == "Sala"


def test_o_nome_dela_nao_e_comido_no_segundo_salvamento() -> None:
    """Ela batiza um dongle SEM Pro de "Nintendo do sofá" — e a palavra fica."""
    escrito = "Nintendo do sofá"
    visto = limpar_o_nome(escrito, hospeda_nintendo=False)
    assert visto == escrito
    assert costurar_o_nome(visto, hospeda_nintendo=False) == escrito


@pytest.mark.parametrize("hospeda", [True, False])
@pytest.mark.parametrize(
    "alias",
    ["Sala", "Nintendo Sala", "Nintendo do sofá", "MeowSystem #2", "Nintendo"],
)
def test_ida_e_volta_estabiliza_na_primeira_passagem(
    alias: str, hospeda: bool
) -> None:
    """Mostrar e salvar de novo muda o alias NO MÁXIMO uma vez."""
    uma = costurar_o_nome(
        limpar_o_nome(alias, hospeda_nintendo=hospeda), hospeda_nintendo=hospeda
    )
    duas = costurar_o_nome(
        limpar_o_nome(uma, hospeda_nintendo=hospeda), hospeda_nintendo=hospeda
    )
    assert duas == uma


@pytest.mark.parametrize("hospeda", [True, False])
@pytest.mark.parametrize(
    "alias", ["Nintendo Sala", "Nintendo do sofá", "MeowSystem #2", "Nintendo"]
)
def test_alias_ja_protegido_atravessa_a_ida_e_volta_intacto(
    alias: str, hospeda: bool
) -> None:
    """Mesa em ordem: abrir a tela e salvar sem mexer não muda nada no BlueZ."""
    if hospeda and not alias.startswith(PREFIXO_NINTENDO):
        pytest.skip("neste estado o alias está desprotegido — é caso do reparo")
    volta = costurar_o_nome(
        limpar_o_nome(alias, hospeda_nintendo=hospeda), hospeda_nintendo=hospeda
    )
    assert volta == alias


def test_nintendo_colado_na_palavra_nao_e_costura_deste_produto() -> None:
    """`NintendoCasa` é nome dela — nem o script nem o módulo colam assim."""
    assert limpar_o_nome("NintendoCasa", hospeda_nintendo=True) == "NintendoCasa"


def test_prefixo_em_caixa_errada_e_normalizado_na_ida_e_volta() -> None:
    """`nintendo casa` vira `Nintendo casa`, e numa passagem só."""
    uma = costurar_o_nome(
        limpar_o_nome("nintendo casa", hospeda_nintendo=True),
        hospeda_nintendo=True,
    )
    assert uma == "Nintendo casa"
    duas = costurar_o_nome(limpar_o_nome(uma, hospeda_nintendo=True), hospeda_nintendo=True)
    assert duas == uma


def test_nome_comprido_com_acento_e_cortado_em_fronteira_de_caractere() -> None:
    """124 x "á" = 248 bytes, e o BlueZ desta bancada RECUSOU esse tamanho."""
    alias = costurar_o_nome("á" * 400, hospeda_nintendo=False)
    assert len(alias.encode("utf-8")) <= TETO_MEDIDO_NO_BLUEZ
    assert alias.encode("utf-8").decode("utf-8") == alias


def test_o_corte_come_a_cauda_e_nunca_o_prefixo() -> None:
    """Truncar pela cauda é o que faz a proteção sobreviver ao teto."""
    alias = costurar_o_nome("á" * 400, hospeda_nintendo=True)
    assert alias.startswith(PREFIXO_NINTENDO)
    assert len(alias.encode("utf-8")) <= TETO_MEDIDO_NO_BLUEZ


def test_so_o_adaptador_do_pro_e_apontado() -> None:
    listar, ler = _sysfs()
    assert adaptadores_com_nintendo(listar=listar, ler=ler) == frozenset({DOIS})


def test_controle_no_cabo_nao_da_adaptador_a_ninguem() -> None:
    """Controle negativo medido: no cabo o `HID_PHYS` é caminho USB, não MAC."""
    listar, ler = _sysfs(
        {
            "hidraw0": _uevent(
                nome="Pro Controller", phys=PHYS_DO_CABO, uniq=PRO
            )
        }
    )
    assert adaptadores_com_nintendo(listar=listar, ler=ler) == frozenset()


def test_a_oui_genuina_sozinha_denuncia_a_linhagem() -> None:
    """Nome irreconhecível, OUI genuína: ainda é linhagem Nintendo."""
    canonica = ":".join(
        NINTENDO_REAL_OUI[i : i + 2] for i in range(0, len(NINTENDO_REAL_OUI), 2)
    )
    assert canonica in OUIS_NINTENDO
    listar, ler = _sysfs(
        {
            "hidraw0": _uevent(
                nome="Generic USB Joystick",
                phys=UM,
                uniq=f"{canonica}:00:00:01",
            )
        }
    )
    assert adaptadores_com_nintendo(listar=listar, ler=ler) == frozenset({UM})


def test_dualsense_sozinho_nao_pede_prefixo_nenhum() -> None:
    """Quatro DualSense e nenhum Nintendo: nada a costurar."""
    listar, ler = _sysfs(
        {
            no: texto
            for no, texto in UEVENTS.items()
            if "Pro Controller" not in texto
        }
    )
    assert adaptadores_com_nintendo(listar=listar, ler=ler) == frozenset()


def test_sysfs_ilegivel_nao_inventa_adaptador() -> None:
    def listar(_raiz: str) -> list[str]:
        raise PermissionError("sysfs fechado")

    assert adaptadores_com_nintendo(listar=listar, ler=lambda _c: "") == frozenset()


def test_a_leitura_traz_endereco_alias_e_quem_hospeda_nintendo() -> None:
    bus = BusDublado()
    dongles = ler_os_dongles(**_mesa(bus))
    assert [d.endereco for d in dongles] == [
        UM.upper(),
        DOIS.upper(),
        TRES.upper(),
    ]
    assert [d.hospeda_nintendo for d in dongles] == [False, True, False]


def test_o_nome_com_espaco_chega_inteiro() -> None:
    """`s "Nintendo MeowSystem"` não pode virar `MeowSystem`."""
    bus = BusDublado()
    por_endereco = {d.endereco: d for d in ler_os_dongles(**_mesa(bus))}
    assert por_endereco[UM.upper()].alias == "Nintendo MeowSystem"


def test_a_ordem_da_tabela_nao_muda_quando_o_hci_inverte() -> None:
    """A tabela é ordenada por endereço — o `hciN` inverte entre boots."""
    antes = ler_os_dongles(**_mesa(BusDublado()))
    depois = ler_os_dongles(
        **_mesa(BusDublado(ordem=(TRES, UM, DOIS)))
    )
    assert [d.endereco for d in antes] == [d.endereco for d in depois]


def test_o_busctl_sem_json_ainda_entrega_o_nome_com_espaco() -> None:
    """Plano B do desembrulho: `busctl` velho, que não conhece `--json`."""

    class BusDeTexto(BusDublado):
        def __call__(self, argumentos: Sequence[str]) -> str | None:
            resposta = super().__call__(argumentos)
            if resposta is None or argumentos[0] != "get-property":
                return resposta
            dado = json.loads(resposta)["data"]
            if isinstance(dado, bool):
                return f"b {str(dado).lower()}\n"
            return f's "{dado}"\n'

    por_endereco = {d.endereco: d for d in ler_os_dongles(**_mesa(BusDeTexto()))}
    assert por_endereco[UM.upper()].alias == "Nintendo MeowSystem"
    assert por_endereco[UM.upper()].ligado is True


def test_sem_busctl_a_leitura_e_vazia_e_nao_explode() -> None:
    """Sem barramento de sistema (um sandbox sem o `org.bluez`) — e isso não é exceção."""
    assert ler_os_dongles(**_mesa(BusDublado(sem_busctl=True))) == ()


def test_a_escrita_e_por_endereco_e_nao_pelo_indice_do_boot() -> None:
    """Com a árvore invertida, o nome tem de ir para o MESMO aparelho."""
    invertido = BusDublado(ordem=(TRES, DOIS, UM))
    renomeacao = renomear_o_dongle(TRES, "Do teclado", **_mesa(invertido))
    assert renomeacao.aplicado
    assert invertido.escritas == [(TRES, "Do teclado")]
    assert invertido.aliases[UM] == ALIAS_INICIAL[UM]


def test_renomear_o_dongle_do_pro_costura_e_o_dos_outros_nao() -> None:
    bus = BusDublado()
    do_pro = renomear_o_dongle(DOIS, "Sofá", **_mesa(bus))
    do_resto = renomear_o_dongle(TRES, "Teclado", **_mesa(bus))
    assert (do_pro.alias, do_pro.costurado) == ("Nintendo Sofá", True)
    assert (do_resto.alias, do_resto.costurado) == ("Teclado", False)
    assert bus.aliases[DOIS] == "Nintendo Sofá"
    assert bus.aliases[TRES] == "Teclado"


def test_dongle_que_saiu_da_mesa_nao_vira_escrita_em_outro() -> None:
    bus = BusDublado()
    fora = renomear_o_dongle("aa:bb:cc:00:00:99", "Sumido", **_mesa(bus))
    assert not fora.aplicado
    assert fora.porque
    assert bus.escritas == []


def test_recusa_do_bluez_volta_como_nao_aplicado_e_com_motivo() -> None:
    bus = BusDublado()
    tabela = ler_os_dongles(**_mesa(bus))

    def recusa(argumentos: Sequence[str]) -> str | None:
        return None if argumentos[0] == "set-property" else bus(argumentos)

    resposta = renomear_o_dongle(DOIS, "Sofá", dongles=tabela, executar=recusa)
    assert not resposta.aplicado
    assert resposta.porque
    assert resposta.alias == "Nintendo Sofá"


def test_a_mesa_desta_bancada_costura_o_adaptador_do_pro_e_so_ele() -> None:
    """O `bt_active_mode.sh` costura o PRIMEIRO adaptador; o Pro está no segundo."""
    bus = BusDublado()
    feitos = costurar_a_mesa(**_mesa(bus))
    assert [(r.endereco, r.alias) for r in feitos] == [
        (DOIS.upper(), "Nintendo MeowSystem #2")
    ]
    assert bus.escritas == [(DOIS, "Nintendo MeowSystem #2")]


def test_o_passe_de_reparo_e_idempotente() -> None:
    bus = BusDublado()
    costurar_a_mesa(**_mesa(bus))
    assert costurar_a_mesa(**_mesa(bus)) == ()


def test_o_passe_nunca_tira_prefixo_de_quem_nao_hospeda_nintendo() -> None:
    """O produto acrescenta, nunca subtrai."""
    bus = BusDublado()
    costurar_a_mesa(**_mesa(bus))
    assert bus.aliases[UM] == "Nintendo MeowSystem"


def test_mesa_sem_nintendo_nenhum_nao_escreve_em_ninguem() -> None:
    sem_pro = {
        no: texto for no, texto in UEVENTS.items() if "Pro Controller" not in texto
    }
    bus = BusDublado()
    assert costurar_a_mesa(**_mesa(bus, sem_pro)) == ()
    assert bus.escritas == []


def test_o_dongle_sabe_dizer_se_esta_protegido() -> None:
    bus = BusDublado()
    por_endereco = {d.endereco: d for d in ler_os_dongles(**_mesa(bus))}
    assert por_endereco[DOIS.upper()].protegido is False
    assert por_endereco[TRES.upper()].protegido is True
    assert por_endereco[DOIS.upper()].nome == "MeowSystem #2"


def test_dongle_sem_objeto_nao_tenta_escrever() -> None:
    """Sem caminho no D-Bus não há onde escrever — e isso não é exceção."""
    bus = BusDublado()
    orfao = Dongle(endereco=UM.upper(), alias="Sala")
    resposta = renomear_o_dongle(UM, "Sala", dongles=[orfao], executar=bus)
    assert not resposta.aplicado
    assert bus.escritas == []
