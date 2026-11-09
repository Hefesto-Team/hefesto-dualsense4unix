static void sdp_xml_data_flush_seq(struct sdp_xml_data *elem)
{
	const struct queue_entry *entry;
	sdp_data_t *tail = NULL;

	if (!elem->seq)
		return;

	for (entry = queue_get_entries(elem->seq); entry; entry = entry->next) {
		if (tail)
			sdp_seq_append(tail, entry->data);
		else
			elem->data->val.dataseq = sdp_seq_append(NULL,
								entry->data);
		tail = entry->data;
	}

	queue_destroy(elem->seq, NULL);
	elem->seq = NULL;
}

static void sdp_xml_data_free(struct sdp_xml_data *elem)
{
	queue_destroy(elem->seq, (queue_destroy_func_t) sdp_data_free);

	if (elem->data)
		sdp_data_free(elem->data);

	free(elem->name);
	free(elem->text);
	free(elem);
}

/* Free the elements left on the stack, e.g. by a document that is malformed */
static void sdp_xml_data_free_stack(struct sdp_xml_data *elem)
{
	while (elem) {
		struct sdp_xml_data *next = elem->next;

		sdp_xml_data_free(elem);
		elem = next;
	}
}

static void element_end(GMarkupParseContext *context,
		const char *element_name, gpointer user_data, GError **err)
{
	struct context_data *ctx_data = user_data;
	struct sdp_xml_data *elem;

	if (!strcmp(element_name, "record"))
		return;

	if (!strcmp(element_name, "attribute")) {
		/* Attributes are expected at top-level record scope. */
		if (ctx_data->stack_head && ctx_data->stack_head->data &&
		    ctx_data->stack_head->next == NULL) {
			int ret = sdp_attr_add(ctx_data->record, ctx_data->attr_id,
							ctx_data->stack_head->data);
			if (ret == -1)
				DBG("Could not add attribute 0x%04x",
							ctx_data->attr_id);
			else {
				/* ownership transferred to record */
				ctx_data->stack_head->data = NULL;
			}

			sdp_xml_data_free(ctx_data->stack_head);
			ctx_data->stack_head = NULL;
		} else if (ctx_data->stack_head && ctx_data->stack_head->next) {
			g_set_error(err, G_MARKUP_ERROR,
				    G_MARKUP_ERROR_INVALID_CONTENT,
				    "Nested <attribute> is invalid");
			return;
		} else {
			DBG("No data for attribute 0x%04x", ctx_data->attr_id);
		}
		return;
	}

	if (!ctx_data->stack_head)
		return;

	if (!ctx_data->stack_head->data) {
