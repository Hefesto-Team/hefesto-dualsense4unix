-- Hefesto - DualSense4Unix — FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01
--
-- Rebaixa a prioridade da entrada do controle (e do monitor da saída dele) para que
-- ele nunca seja eleito microfone padrão sozinho; continua selecionável à mão.
--
-- WirePlumber 0.4 (Ubuntu 24.04, Linux Mint 22, Debian 12): a mesma regra do
-- 51-…-no-default-source.conf, na forma que o 0.4 lê (Lua em ~/.config/wireplumber/main.lua.d/). O
-- 0.4 IGNORA wireplumber.conf.d/ sem erro nenhum, por isso a regra SPA-JSON não
-- valia ali. O instalador escolhe a forma pela pasta de sistema do WirePlumber
-- (utils/xdg_paths.wireplumber_forma); no 0.5 este arquivo não é instalado.
--
-- O 0.4 casa por glob (`*` e `?`), não por regex: o `[Dd]ual[Ss]ense` da regra
-- SPA-JSON vira as quatro grafias abaixo.
--
-- Portão: tests/unit/test_as_regras_do_som_valem_no_wireplumber_da_distro.py

local grafias = { "DualSense", "Dualsense", "dualSense", "dualsense" }

local function casar(campo, prefixo, sufixo)
  local grupos = {}
  for _, g in ipairs(grafias) do
    table.insert(grupos, { { campo, "matches", prefixo .. g .. sufixo } })
  end
  return grupos
end

local entrada = {
  matches = {},
  apply_properties = {
    ["priority.session"] = 1500,
    ["priority.driver"] = 1500,
    ["node.dont-reconnect"] = true,
  },
}
for _, g in ipairs(casar("node.name", "alsa_input.*", "*")) do
  table.insert(entrada.matches, g)
end
table.insert(alsa_monitor.rules, entrada)

-- O cartão do controle e o monitor da SAÍDA dele descem para 50: sem isto o
-- monitor do alto-falante do controle vence a eleição e o que se grava é o som
-- que sai, não a voz (FONTE-PADRÃO-01).
local rebaixados = {
  matches = {},
  apply_properties = {
    ["priority.session"] = 50,
    ["priority.driver"] = 50,
  },
}
for _, g in ipairs(casar("device.name", "alsa_card.*", "*")) do
  table.insert(rebaixados.matches, g)
end
for _, g in ipairs(casar("node.name", "alsa_output.*", "*onitor")) do
  table.insert(rebaixados.matches, g)
end
table.insert(alsa_monitor.rules, rebaixados)
