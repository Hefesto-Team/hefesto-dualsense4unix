/* [recorte do teste: linhas do fonte omitidas aqui] */
#define AVRCP_BROWSING_TIMEOUT		1
#define AVRCP_CT_VERSION		0x0106
#define AVRCP_TG_VERSION		0x0106

#define AVRCP_SCOPE_MEDIA_PLAYER_LIST			0x00
#define AVRCP_SCOPE_MEDIA_PLAYER_VFS			0x01
#define AVRCP_SCOPE_SEARCH				0x02
#define AVRCP_SCOPE_NOW_PLAYING			0x03

#if __BYTE_ORDER == __LITTLE_ENDIAN

struct avrcp_header {
	uint8_t company_id[3];
	uint8_t pdu_id;
	uint8_t packet_type:2;
	uint8_t rsvd:6;
	uint16_t params_len;
/* [recorte do teste: linhas do fonte omitidas aqui] */
					avrcp_player_value_rsp, session);
}

static gboolean avrcp_list_player_attributes_rsp(struct avctp *conn,
					uint8_t code, uint8_t subunit,
					uint8_t transaction, uint8_t *operands,
					size_t operand_count, void *user_data)
{
	uint8_t attrs[AVRCP_ATTRIBUTE_LAST];
	struct avrcp *session = user_data;
	struct avrcp_header *pdu = (void *) operands;
	uint8_t len, count = 0;
	int i;

	if (code == AVC_CTYPE_REJECTED || code == AVC_CTYPE_NOT_IMPLEMENTED)
		return FALSE;

	len = pdu->params[0];

	if (be16_to_cpu(pdu->params_len) < count) {
		error("Invalid parameters");
		return FALSE;
	}

	for (i = 0; len > 0; len--, i++) {
		/* Don't query invalid attributes */
		if (pdu->params[i + 1] == AVRCP_ATTRIBUTE_ILEGAL ||
				pdu->params[i + 1] > AVRCP_ATTRIBUTE_LAST)
			continue;

		attrs[count++] = pdu->params[i + 1];
	}

	avrcp_get_current_player_value(session, attrs, count);

	return FALSE;
}

static void avrcp_list_player_attributes(struct avrcp *session)
{
	uint8_t buf[AVRCP_HEADER_LENGTH];
/* [recorte do teste: linhas do fonte omitidas aqui] */
	avctp_send_vendordep_req(session->conn, AVC_CTYPE_STATUS,
					AVC_SUBUNIT_PANEL, buf, sizeof(buf),
					avrcp_list_player_attributes_rsp,
					session);
}

static void avrcp_parse_attribute_list(struct avrcp_player *player,
					struct media_item *item,
					uint8_t *operands, uint8_t count)
{
	struct media_player *mp = player->user_data;
	int i;

	for (i = 0; count > 0; count--) {
		uint32_t id;
		uint16_t charset, len;

		id = get_be32(&operands[i]);
		i += sizeof(uint32_t);

		charset = get_be16(&operands[i]);
		i += sizeof(uint16_t);

		len = get_be16(&operands[i]);
		i += sizeof(uint16_t);

		if (charset == 106) {
			const char *key = metadata_to_str(id);

			if (key != NULL)
				media_player_set_metadata(mp, item,
							metadata_to_str(id),
							&operands[i], len);
		}

		i += len;
	}
}

static void avrcp_abort_continuing(struct avrcp *session, uint8_t pdu_id)
{
	uint8_t buf[AVRCP_HEADER_LENGTH + 1];
	struct avrcp_header *pdu = (void *) buf;

/* [recorte do teste: linhas do fonte omitidas aqui] */
						uint8_t code, uint8_t subunit,
						uint8_t transaction,
						uint8_t *operands,
						size_t operand_count,
						void *user_data)
{
	struct avrcp *session = user_data;
	struct avrcp_player *player = session->controller->player;
	struct avrcp_header *pdu = (void *) operands;
	struct media_player *mp = player->user_data;
	struct media_item *item;
	uint8_t count;

	if (code == AVC_CTYPE_REJECTED)
		return FALSE;

	/* Abort fragmented responses as reassembly is not supported */
	if (pdu->packet_type == AVRCP_PACKET_TYPE_START ||
			pdu->packet_type == AVRCP_PACKET_TYPE_CONTINUING) {
		avrcp_abort_continuing(session, AVRCP_GET_ELEMENT_ATTRIBUTES);
		return FALSE;
	}

	count = pdu->params[0];

	if (be16_to_cpu(pdu->params_len) - 1 < count * 8) {
		error("Invalid parameters");
		return FALSE;
	}

	media_player_clear_metadata(mp);

	item = media_player_set_playlist_item(mp, player->uid);

	avrcp_parse_attribute_list(player, item, &pdu->params[1], count);

	media_player_metadata_changed(mp);

	avrcp_get_play_status(session);

	return FALSE;
}

/* [recorte do teste: linhas do fonte omitidas aqui] */
		return "Podcast";
	case 0x03:
		return "Audio Book, Podcast";
	}

	return "None";
}

static struct media_item *parse_media_element(struct avrcp *session,
					uint8_t *operands, uint16_t len)
{
	struct avrcp_player *player;
	struct media_player *mp;
	struct media_item *item;
	uint16_t namelen, namesize;
	char name[255];
	uint64_t uid;
	uint8_t count;

	if (len < 13)
		return NULL;

	uid = get_be64(&operands[0]);

	memset(name, 0, sizeof(name));
	namesize = get_be16(&operands[11]);
	namelen = MIN(namesize, sizeof(name) - 1);
	if (namelen > 0) {
		memcpy(name, &operands[13], namelen);
		strtoutf8(name, namelen);
	}

	count = operands[13 + namesize];

	player = session->controller->player;
	mp = player->user_data;

	item = media_player_create_item(mp, name, PLAYER_ITEM_TYPE_AUDIO, uid);
	if (item == NULL)
		return NULL;

	media_item_set_playable(item, true);

	avrcp_parse_attribute_list(player, item, &operands[14 + namesize],
					count);

	return item;
}

static struct media_item *parse_media_folder(struct avrcp *session,
					uint8_t *operands, uint16_t len)
{
	struct avrcp_player *player = session->controller->player;
	struct media_player *mp = player->user_data;
	struct media_item *item;
	uint16_t namelen;
	char name[255];
	uint64_t uid;
	uint8_t type;
	uint8_t playable;

	if (len < 12)
		return NULL;

	uid = get_be64(&operands[0]);
	type = operands[8];
	playable = operands[9];

	memset(name, 0, sizeof(name));
	namelen = MIN(get_be16(&operands[12]), sizeof(name) - 1);
	if (namelen > 0)
		memcpy(name, &operands[14], namelen);

	item = media_player_create_folder(mp, name, type, uid);
	if (!item)
		return NULL;

	media_item_set_playable(item, playable & 0x01);

	return item;
/* [recorte do teste: linhas do fonte omitidas aqui] */
	}

	count = get_be16(&operands[6]);
	if (count == 0)
		goto done;

	for (i = 8; count && i + 3 < operand_count; count--) {
		struct media_item *item;
		uint8_t type;
		uint16_t len;

		type = operands[i++];
		len = get_be16(&operands[i]);
		i += 2;

		if (type != 0x03 && type != 0x02) {
			i += len;
			continue;
		}

		if (i + len > operand_count) {
			error("Invalid item length");
			break;
		}

		if (type == 0x03)
			item = parse_media_element(session, &operands[i], len);
		else
			item = parse_media_folder(session, &operands[i], len);

		if (item) {
			p->items = g_slist_append(p->items, item);
			new_items++;
		}

		i += len;
	}
/* [recorte do teste: linhas do fonte omitidas aqui] */

static gboolean avrcp_get_item_attributes_rsp(struct avctp *conn,
						uint8_t *operands,
						size_t operand_count,
						void *user_data)
{
	struct avrcp *session = user_data;
	struct avrcp_player *player = session->controller->player;
	struct avrcp_browsing_header *pdu = (void *) operands;
	struct media_player *mp = player->user_data;
	struct media_item *item;
	uint8_t count;

	if (pdu == NULL) {
		avrcp_get_element_attributes(session);
		return FALSE;
	}

	if (pdu->params[0] != AVRCP_STATUS_SUCCESS || operand_count < 4) {
		avrcp_get_element_attributes(session);
		return FALSE;
	}

	count = pdu->params[1];

	if (be16_to_cpu(pdu->param_len) - 1 < count * 8) {
		error("Invalid parameters");
		return FALSE;
	}

	media_player_clear_metadata(mp);

	item = media_player_set_playlist_item(mp, player->uid);

	avrcp_parse_attribute_list(player, item, &pdu->params[2], count);

	media_player_metadata_changed(mp);

	avrcp_get_play_status(session);

	return FALSE;
}

/* [recorte do teste: linhas do fonte omitidas aqui] */
