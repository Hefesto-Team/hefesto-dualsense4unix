/* [recorte do teste: linhas do fonte omitidas aqui] */
								caps) != 3) {
				warn("Unable to load Endpoint: seid %u", rseid);
				g_free(value);
				continue;
			}
			delay_reporting = false;
		}

		for (i = 0, size = strlen(caps); i < size && i >= 2; i += 2) {
			uint8_t *tmp = data + i / 2;

			if (sscanf(caps + i, "%02hhx", tmp) != 1) {
				warn("Unable to load Endpoint: seid %u", rseid);
				break;
			}
		}

		g_free(value);

		if (i != size)
			continue;

		caps_add_codec(&l, codec, data, size / 2);

		rsep = avdtp_register_remote_sep(chan->session, rseid, type, l,
							delay_reporting);
/* [recorte do teste: linhas do fonte omitidas aqui] */
