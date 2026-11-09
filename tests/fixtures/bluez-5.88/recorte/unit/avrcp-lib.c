
	return player->ind->list_attributes(session, transaction,
							player->user_data);
}

static bool check_attributes(uint8_t number, const uint8_t *attrs)
{
	int i;

	for (i = 0; i < number; i++) {
		if (attrs[i] > AVRCP_ATTRIBUTE_LAST ||
					attrs[i] == AVRCP_ATTRIBUTE_ILLEGAL)
			return false;
	}

	return true;
}

static ssize_t get_attribute_text(struct avrcp *session, uint8_t transaction,
					uint16_t params_len, uint8_t *params,
					void *user_data)
{
	struct avrcp_player *player = user_data;
{
	struct avrcp_player *player = user_data;
	struct list_values_req *req;

	DBG("");

	if (!params || params_len != sizeof(*req))
		return -EINVAL;

	req = (void *) params;
	if (req->attr > AVRCP_ATTRIBUTE_LAST ||
					req->attr == AVRCP_ATTRIBUTE_ILLEGAL)
		return -EINVAL;

	if (!player->ind || !player->ind->list_values)
		return -ENOSYS;

	return player->ind->list_values(session, transaction, req->attr,
							player->user_data);
}

static bool check_value(uint8_t attr, uint8_t number, const uint8_t *values)
{
	if (!player->ind || !player->ind->get_value_text)
		return -ENOSYS;

	if (!params || params_len < sizeof(*req))
		return -EINVAL;

	req = (void *) params;
	if (params_len != sizeof(*req) + req->number)
		return -EINVAL;

	if (req->number > AVRCP_ATTRIBUTE_LAST ||
					req->number == AVRCP_ATTRIBUTE_ILLEGAL)
		return -EINVAL;

	if (!check_value(req->attr, req->number, req->values))
		return -EINVAL;

	return player->ind->get_value_text(session, transaction, params[0],
						params[1], &params[2],
						player->user_data);
}

static ssize_t get_value(struct avrcp *session, uint8_t transaction,

	if (number > AVRCP_ATTRIBUTE_LAST)
		return -EINVAL;

	iov[0].iov_base = &number;
	iov[0].iov_len = sizeof(number);

	for (i = 0; i < number; i++) {
		uint8_t len = 0;

		if (attrs[i] > AVRCP_ATTRIBUTE_LAST ||
					attrs[i] == AVRCP_ATTRIBUTE_ILLEGAL)
			return -EINVAL;

		if (text[i])
			len = strlen(text[i]);

		val[i].attr = attrs[i];
		val[i].charset = cpu_to_be16(AVRCP_CHARSET_UTF8);
		val[i].len = len;

		iov[i + 1].iov_base = &val[i];
		iov[i + 1].iov_len = sizeof(val[i]);
