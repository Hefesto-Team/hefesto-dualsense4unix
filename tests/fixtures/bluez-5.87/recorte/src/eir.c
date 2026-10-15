/* [recorte do teste: linhas do fonte omitidas aqui] */
		eir->services = queue_append(eir->services, uuid_str);
		uuid_ptr += 16;
	}
}

static char *name2utf8(const uint8_t *name, uint8_t len)
{
	char utf8_name[HCI_MAX_NAME_LENGTH + 2];

	memset(utf8_name, 0, sizeof(utf8_name));
	strncpy(utf8_name, (char *) name, len);
	strtoutf8(utf8_name, len);

	/* Remove leading and trailing whitespace characters */
	g_strstrip(utf8_name);

	return g_strdup(utf8_name);
/* [recorte do teste: linhas do fonte omitidas aqui] */
