
#define AVRCP_CHARSET_UTF8		106

#define AVRCP_BROWSING_TIMEOUT		1
#define AVRCP_CT_VERSION		0x0106
#define AVRCP_TG_VERSION		0x0106

#define AVRCP_SCOPE_MEDIA_PLAYER_LIST			0x00
#define AVRCP_SCOPE_MEDIA_PLAYER_VFS			0x01
#define AVRCP_SCOPE_SEARCH				0x02
#define AVRCP_SCOPE_NOW_PLAYING			0x03

#define AVRCP_MTU	(AVC_MTU - AVC_HEADER_LENGTH)
#define AVRCP_PDU_MTU	(AVRCP_MTU - AVRCP_HEADER_LENGTH)

struct get_folder_items_rsp {
	uint8_t status;
	uint16_t uid_counter;
	uint16_t num_items;
	uint8_t data[0];
} __attribute__ ((packed));

struct folder_item {
	uint8_t type;
	return FALSE;
}

static void avrcp_list_player_attributes(struct avrcp *session)
{
	uint8_t buf[AVRCP_HEADER_LENGTH];
	struct avrcp_header *pdu = (void *) buf;

	memset(buf, 0, sizeof(buf));

	set_company_id(pdu->company_id, IEEEID_BTSIG);
	pdu->pdu_id = AVRCP_LIST_PLAYER_ATTRIBUTES;
	pdu->packet_type = AVRCP_PACKET_TYPE_SINGLE;

	avctp_send_vendordep_req(session->conn, AVC_CTYPE_STATUS,
					AVC_SUBUNIT_PANEL, buf, sizeof(buf),
					avrcp_list_player_attributes_rsp,
					session);
}

struct parse_attribute_data {
	struct media_player *mp;
	struct media_item *item;
};

static void parse_attribute(const struct avrcp_attribute *attr,
							void *user_data)
{
	struct parse_attribute_data *data = user_data;
	const char *key;

	if (attr->charset != 106)
		return;

	key = metadata_to_str(attr->id);
	if (key == NULL)
		return;

	media_player_set_metadata(data->mp, data->item, key, attr->value,
								attr->len);
}

static void avrcp_player_parse_attributes(struct avrcp_player *player,
					struct media_item *item,
					struct iovec *iov, uint8_t count)
{
	struct parse_attribute_data data = {
		.mp = player->user_data,
		.item = item,
	};

	avrcp_parse_attribute_list(iov, count, parse_attribute, &data);
}

static void avrcp_abort_continuing(struct avrcp *session, uint8_t pdu_id)
{
	uint8_t buf[AVRCP_HEADER_LENGTH + 1];
	struct avrcp_header *pdu = (void *) buf;

	memset(buf, 0, sizeof(buf));

	set_company_id(pdu->company_id, IEEEID_BTSIG);
	pdu->pdu_id = AVRCP_ABORT_CONTINUING;
	pdu->packet_type = AVRCP_PACKET_TYPE_SINGLE;
	pdu->params_len = cpu_to_be16(1);
	avctp_send_vendordep_req(session->conn, AVC_CTYPE_CONTROL,
					AVC_SUBUNIT_PANEL, buf, sizeof(buf),
					NULL, session);
}

static gboolean avrcp_get_element_attributes_rsp(struct avctp *conn,
						uint8_t code, uint8_t subunit,
						uint8_t transaction,
						uint8_t *operands,
						size_t operand_count,
						void *user_data)
{
	struct avrcp *session = user_data;
	struct avrcp_player *player = session->controller->player;
	struct iovec iov = { operands, operand_count };
	struct avrcp_header *pdu;
	struct media_player *mp = player->user_data;
	struct media_item *item;
	uint8_t count;

	if (code == AVC_CTYPE_REJECTED)
		return FALSE;

	pdu = avrcp_pull_header(&iov);
	if (!pdu)
		return FALSE;

	/* Abort fragmented responses as reassembly is not supported */
	if (pdu->packet_type == AVRCP_PACKET_TYPE_START ||
			pdu->packet_type == AVRCP_PACKET_TYPE_CONTINUING) {
		avrcp_abort_continuing(session, AVRCP_GET_ELEMENT_ATTRIBUTES);
		return FALSE;
	}

	if (!util_iov_pull_u8(&iov, &count))
		return FALSE;

	media_player_clear_metadata(mp);

	item = media_player_set_playlist_item(mp, player->uid);

	avrcp_player_parse_attributes(player, item, &iov, count);

	media_player_metadata_changed(mp);

	avrcp_get_play_status(session);


	memset(buf, 0, sizeof(buf));

	set_company_id(pdu->company_id, IEEEID_BTSIG);
	pdu->pdu_id = AVRCP_GET_ELEMENT_ATTRIBUTES;
	pdu->params_len = cpu_to_be16(9);
	pdu->packet_type = AVRCP_PACKET_TYPE_SINGLE;

	length = AVRCP_HEADER_LENGTH + be16_to_cpu(pdu->params_len);

	avctp_send_vendordep_req(session->conn, AVC_CTYPE_STATUS,
					AVC_SUBUNIT_PANEL, buf, length,
					avrcp_get_element_attributes_rsp,
					session);
}

static const char *type_to_string(uint8_t type)
{
	switch (type & 0x0F) {
	case 0x01:
		return "Audio";
	case 0x02:
		return "Video";
	case 0x03:
		return "Audio, Video";
	case 0x04:
		return "Audio Broadcasting";
	case 0x05:
		return "Audio, Audio Broadcasting";
	case 0x06:
		return "Video, Audio Broadcasting";
	case 0x07:
		return "Audio, Video, Audio Broadcasting";
	case 0x08:
		return "Video Broadcasting";
	case 0x09:
		return "Audio, Video Broadcasting";
	case 0x0A:
		return "Video, Video Broadcasting";
	case 0x0B:
		return "Audio, Video, Video Broadcasting";
	case 0x0C:
		return "Audio Broadcasting, Video Broadcasting";
	case 0x0D:
		return "Audio, Audio Broadcasting, Video Broadcasting";
	case 0x0E:
		return "Video, Audio Broadcasting, Video Broadcasting";
	case 0x0F:
		return "Audio, Video, Audio Broadcasting, Video Broadcasting";
	}

	return "None";
}

static const char *subtype_to_string(uint32_t subtype)
{
	switch (subtype & 0x03) {

static struct media_item *parse_media_folder(struct avrcp *session,
							struct iovec *iov)
{
	struct avrcp_player *player = session->controller->player;
	struct media_player *mp = player->user_data;
	struct media_item *item;
	struct avrcp_media_folder folder;

	if (!avrcp_parse_media_folder(iov, &folder))
		return NULL;

	item = media_player_create_folder(mp, folder.name, folder.type,
								folder.uid);
	if (!item)
		return NULL;

	media_item_set_playable(item, folder.playable & 0x01);

	return item;
}

static void avrcp_list_items(struct avrcp *session, uint32_t start,
								uint32_t end);
static gboolean avrcp_list_items_rsp(struct avctp *conn, uint8_t *operands,
					size_t operand_count, void *user_data)
{
	struct avrcp_browsing_header *pdu = (void *) operands;
	struct avrcp *session = user_data;
	struct avrcp_player *player = session->controller->player;
	struct pending_list_items *p = player->p;
	uint16_t count;
	uint64_t items;
	uint64_t new_items = 0;
	size_t i;
	int err = 0;

	if (player->p == NULL) {
		media_player_list_complete(player->user_data, NULL, -EINVAL);
		return FALSE;
	}

	if (pdu == NULL) {
		err = -ETIMEDOUT;
		goto done;
	}

	/* AVRCP 1.5 - Page 76:
	 * If the TG receives a GetFolderItems command for an empty folder then
	 * the TG shall return the error (= Range Out of Bounds) in the status
	 * field of the GetFolderItems response.
	 */
	if (pdu->params[0] == AVRCP_STATUS_OUT_OF_BOUNDS)
		goto done;

	if (pdu->params[0] != AVRCP_STATUS_SUCCESS || operand_count < 5) {
		err = -EINVAL;
		goto done;
	}

	count = get_be16(&operands[6]);
	if (count == 0)
		goto done;

	for (i = 8; count && i + 3 < operand_count; count--) {
		struct media_item *item;
		struct iovec iov;
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

		iov.iov_base = &operands[i];
		iov.iov_len = len;

		if (type == 0x03)
			item = parse_media_element(session, &iov);
		else
			item = parse_media_folder(session, &iov);

		if (item) {
			p->items = g_slist_append(p->items, item);
			new_items++;
		}

		i += len;
	}

	items = g_slist_length(p->items);

	DBG("start %u end %u items %" PRIu64 " total %" PRIu64 "", p->start,
						p->end, items, p->total);

	if (new_items > 0 && items < p->total) {
		avrcp_list_items(session, p->start + items, p->end);
		return FALSE;
	}

done:
	media_player_list_complete(player->user_data, p->items, err);

	g_slist_free(p->items);
	g_free(p);
	player->p = NULL;

	return FALSE;
}

	avctp_send_browsing_req(session->conn, buf, length,
					avrcp_list_items_rsp, session);
}

static gboolean avrcp_change_path_rsp(struct avctp *conn,
					uint8_t *operands, size_t operand_count,
					void *user_data)
{
	struct iovec iov = { operands, operand_count };
	struct avrcp *session = user_data;
	struct avrcp_player *player = session->controller->player;
	struct media_player *mp = player->user_data;
	uint32_t items;
	uint8_t status;
	int ret;

	if (operands == NULL) {
		ret = -ETIMEDOUT;
		goto done;
	}

	if (!avrcp_pull_browsing_header(&iov) ||
			!util_iov_pull_u8(&iov, &status) ||
			status != AVRCP_STATUS_SUCCESS ||
			!util_iov_pull_be32(&iov, &items)) {
		ret = -EINVAL;
		goto done;
	}

	ret = items;

done:
	if (ret < 0) {
		g_free(player->change_path);
		player->change_path = NULL;
	} else {
		g_free(player->path);
		player->path = player->change_path;
		player->change_path = NULL;
	}

	media_player_change_folder_complete(mp, player->path,
						player->change_uid, ret);

	player->change_uid = 0;

	return FALSE;
								uint8_t val)
{
	uint8_t buf[AVRCP_HEADER_LENGTH + 3];
	struct avrcp_header *pdu = (void *) buf;
	uint8_t length;

	memset(buf, 0, sizeof(buf));

	set_company_id(pdu->company_id, IEEEID_BTSIG);
	pdu->pdu_id = AVRCP_SET_PLAYER_VALUE;
	pdu->packet_type = AVRCP_PACKET_TYPE_SINGLE;
	pdu->params[0] = 1;
	pdu->params[1] = attr;
	pdu->params[2] = val;
	pdu->params_len = cpu_to_be16(3);

	length = AVRCP_HEADER_LENGTH + be16_to_cpu(pdu->params_len);

	avctp_send_vendordep_req(session->conn, AVC_CTYPE_CONTROL,
					AVC_SUBUNIT_PANEL, buf, length,
					avrcp_player_value_rsp, session);
}

static gboolean avrcp_set_addressed_player_rsp(struct avctp *conn, uint8_t code,
					uint8_t subunit, uint8_t transaction,
					uint8_t *operands, size_t operand_count,
					void *user_data)
{
	struct avrcp *session = user_data;
	struct avrcp_player *player = session->controller->player;
	struct iovec iov = { operands, operand_count };

	if (!operands || code != AVC_CTYPE_ACCEPTED)
		return FALSE;

	if (!avrcp_pull_header(&iov))
		return FALSE;

	player->addressed = true;

	return FALSE;
}

static void avrcp_set_addressed_player(struct avrcp *session,
						struct avrcp_player *player)
{
	uint8_t buf[AVRCP_HEADER_LENGTH + 2];
	struct avrcp_header *pdu = (void *) buf;
	uint16_t id;

	memset(buf, 0, sizeof(buf));

	set_company_id(pdu->company_id, IEEEID_BTSIG);
	pdu->pdu_id = AVRCP_SET_ADDRESSED_PLAYER;
	pdu->packet_type = AVRCP_PACKET_TYPE_SINGLE;
	id = cpu_to_be16(player->id);
	memcpy(pdu->params, &id, 2);
	pdu->params_len = cpu_to_be16(2);
