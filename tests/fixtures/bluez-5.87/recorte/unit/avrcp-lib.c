/* [recorte do teste: linhas do fonte omitidas aqui] */
}

static bool check_attributes(uint8_t number, const uint8_t *attrs)
{
	int i;

	for (i = 0; i < number; i++) {
		if (attrs[i] > AVRCP_ATTRIBUTE_LAST ||
					attrs[i] == AVRCP_ATTRIBUTE_ILEGAL)
			return false;
	}

	return true;
}

static ssize_t get_attribute_text(struct avrcp *session, uint8_t transaction,
					uint16_t params_len, uint8_t *params,
/* [recorte do teste: linhas do fonte omitidas aqui] */

	DBG("");

	if (!params || params_len != sizeof(*req))
		return -EINVAL;

	req = (void *) params;
	if (req->attr > AVRCP_ATTRIBUTE_LAST ||
					req->attr == AVRCP_ATTRIBUTE_ILEGAL)
		return -EINVAL;

	if (!player->ind || !player->ind->list_values)
		return -ENOSYS;

	return player->ind->list_values(session, transaction, req->attr,
							player->user_data);
}
/* [recorte do teste: linhas do fonte omitidas aqui] */
	if (!params || params_len < sizeof(*req))
		return -EINVAL;

	req = (void *) params;
	if (params_len != sizeof(*req) + req->number)
		return -EINVAL;

	if (req->number > AVRCP_ATTRIBUTE_LAST ||
					req->number == AVRCP_ATTRIBUTE_ILEGAL)
		return -EINVAL;

	if (!check_value(req->attr, req->number, req->values))
		return -EINVAL;

	return player->ind->get_value_text(session, transaction, params[0],
						params[1], &params[2],
						player->user_data);
/* [recorte do teste: linhas do fonte omitidas aqui] */

	iov[0].iov_base = &number;
	iov[0].iov_len = sizeof(number);

	for (i = 0; i < number; i++) {
		uint8_t len = 0;

		if (attrs[i] > AVRCP_ATTRIBUTE_LAST ||
					attrs[i] == AVRCP_ATTRIBUTE_ILEGAL)
			return -EINVAL;

		if (text[i])
			len = strlen(text[i]);

		val[i].attr = attrs[i];
		val[i].charset = cpu_to_be16(AVRCP_CHARSET_UTF8);
		val[i].len = len;
/* [recorte do teste: linhas do fonte omitidas aqui] */
