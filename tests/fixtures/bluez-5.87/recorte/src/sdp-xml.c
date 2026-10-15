/* [recorte do teste: linhas do fonte omitidas aqui] */
{
	struct context_data *ctx_data = user_data;
	struct sdp_xml_data *elem;

	if (!strcmp(element_name, "record"))
		return;

	if (!strcmp(element_name, "attribute")) {
		if (ctx_data->stack_head && ctx_data->stack_head->data) {
			int ret = sdp_attr_add(ctx_data->record, ctx_data->attr_id,
							ctx_data->stack_head->data);
			if (ret == -1)
				DBG("Could not add attribute 0x%04x",
							ctx_data->attr_id);

			ctx_data->stack_head->data = NULL;
			sdp_xml_data_free(ctx_data->stack_head);
			ctx_data->stack_head = NULL;
		} else {
			DBG("No data for attribute 0x%04x", ctx_data->attr_id);
		}
		return;
	}

	if (!ctx_data->stack_head)
		return;

/* [recorte do teste: linhas do fonte omitidas aqui] */

		elem = ctx_data->stack_head;
		ctx_data->stack_head = ctx_data->stack_head->next;
		sdp_xml_data_free(elem);
		return;
	}

	if (!strcmp(element_name, "sequence")) {
		ctx_data->stack_head->data->unitSize = compute_seq_size(ctx_data->stack_head->data);

		if (ctx_data->stack_head->data->unitSize > USHRT_MAX) {
			ctx_data->stack_head->data->unitSize += sizeof(uint32_t);
			ctx_data->stack_head->data->dtd = SDP_SEQ32;
		} else if (ctx_data->stack_head->data->unitSize > UCHAR_MAX) {
			ctx_data->stack_head->data->unitSize += sizeof(uint16_t);
			ctx_data->stack_head->data->dtd = SDP_SEQ16;
		} else {
			ctx_data->stack_head->data->unitSize += sizeof(uint8_t);
		}
	} else if (!strcmp(element_name, "alternate")) {
		ctx_data->stack_head->data->unitSize = compute_seq_size(ctx_data->stack_head->data);

		if (ctx_data->stack_head->data->unitSize > USHRT_MAX) {
			ctx_data->stack_head->data->unitSize += sizeof(uint32_t);
			ctx_data->stack_head->data->dtd = SDP_ALT32;
		} else if (ctx_data->stack_head->data->unitSize > UCHAR_MAX) {
			ctx_data->stack_head->data->unitSize += sizeof(uint16_t);
			ctx_data->stack_head->data->dtd = SDP_ALT16;
		} else {
/* [recorte do teste: linhas do fonte omitidas aqui] */
