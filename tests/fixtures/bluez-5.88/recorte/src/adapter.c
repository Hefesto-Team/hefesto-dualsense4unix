		adapter->set_filter_list = g_slist_prepend(
					adapter->set_filter_list, client);
	else
		discovery_free(client);

	/*
	 * If there are other client discoveries in progress, then leave
	 * it active. If not, then make sure to stop the restart timeout.
	 */
	if (adapter->discovery_list)
		return;

	discovery_cleanup(adapter, TEMP_DEV_TIMEOUT);
}

static void trigger_start_discovery(struct btd_adapter *adapter, guint delay);

static struct discovery_client *discovery_complete(struct btd_adapter *adapter,
						uint8_t status)
{
	struct discovery_client *client = adapter->client;
	DBusMessage *reply;

	if (!client)
		return NULL;

	adapter->client = NULL;


	g_free(data);
	g_key_file_free(key_file);
}

static void convert_proximity_entry(char *key, char *value, void *user_data)
{
	char *src_addr = user_data;
	char *alert;
	char filename[PATH_MAX];
	GKeyFile *key_file;
	GError *gerr = NULL;
	struct stat st;
	int err;
	char *data;
	gsize length = 0;

	if (!strchr(key, '#'))
		return;

	key[17] = '\0';
	alert = &key[18];

	if (bachk(key) != 0)
		return;

	/* Check if the device directory has been created as records should
	 * only be converted for known devices */
	create_filename(filename, PATH_MAX, "/%s/%s", src_addr, key);

	err = stat(filename, &st);
	if (err || !S_ISDIR(st.st_mode))
		return;

	create_filename(filename, PATH_MAX, "/%s/%s/proximity", src_addr, key);

	key_file = g_key_file_new();
	if (!g_key_file_load_from_file(key_file, filename, 0, &gerr)) {
		error("Unable to load key file from %s: (%s)", filename,
								gerr->message);
		g_clear_error(&gerr);
	}
		g_error_free(gerr);
	}
	g_free(data);
}

static void fix_storage(struct btd_adapter *adapter)
{
	char filename[PATH_MAX];
	char address[18];
	char *converted;

	ba2str(&adapter->bdaddr, address);

	create_filename(filename, PATH_MAX, "/%s/config", address);

	converted = textfile_get(filename, "converted");
	if (!converted)
		return;

	free(converted);

	textfile_del(filename, "converted");

	create_filename(filename, PATH_MAX, "/%s/names", address);
	textfile_del(filename, "converted");
	GSList *l;

	for (l = adapter->discovery_list; l; l = g_slist_next(l)) {
		struct discovery_client *client = l->data;
		struct discovery_filter *filter = client->discovery_filter;

		if (filter && (filter->rssi != DISTANCE_VAL_INVALID ||
				filter->pathloss != DISTANCE_VAL_INVALID))
			return true;
	}

	return false;
}

static bool device_is_discoverable(struct btd_adapter *adapter,
					struct eir_data *eir, const char *addr,
					uint8_t bdaddr_type, bool *auto_connect)
{
	GSList *l;
	bool discoverable;

	if (bdaddr_type == BDADDR_BREDR || adapter->filtered_discovery)
		discoverable = true;
	else if (btd_opts.filter_discoverable)
		discoverable = eir->flags & (EIR_LIM_DISC | EIR_GEN_DISC);
	else
		discoverable = true;

	/*
	 * Mark as not discoverable if no client has requested discovery and
	 * report has not set any discoverable flags.
	 */
	if (!adapter->discovery_list && !discoverable)
		return false;

	/* Do a prefix match for both address and name if pattern is set */
	for (l = adapter->discovery_list; l; l = g_slist_next(l)) {
		struct discovery_client *client = l->data;
		struct discovery_filter *filter = client->discovery_filter;
		size_t pattern_len;

		if (!filter || !filter->pattern)
			continue;

		/* Reset discoverable if a client has a pattern filter */
		discoverable = false;

		pattern_len = strlen(filter->pattern);
		if (!pattern_len) {
			*auto_connect = filter->auto_connect;
			return true;
		}

		if (!strncasecmp(filter->pattern, addr, pattern_len)) {
			*auto_connect = filter->auto_connect;
			*auto_connect = filter->auto_connect;
			return true;
		}
	}

	return discoverable;
}

void btd_adapter_device_found(struct btd_adapter *adapter,
					const bdaddr_t *bdaddr,
					uint8_t bdaddr_type, int8_t rssi,
					uint32_t flags,
					const uint8_t *data, uint8_t data_len,
					bool monitoring)
{
	struct btd_device *dev;
	struct bt_ad *ad = NULL;
	struct eir_data eir_data;
	bool name_known, discoverable;
	char addr[18];
	bool confirm;
	bool legacy;
	bool not_connectable;
	bool name_resolve_failed;
	bool scan_rsp;
	bool duplicate = false;
	if (passkey == INVALID_PASSKEY) {
		struct mgmt_cp_user_passkey_neg_reply cp;

		memset(&cp, 0, sizeof(cp));
		bacpy(&cp.addr.bdaddr, bdaddr);
		cp.addr.type = bdaddr_type;

		id = mgmt_reply(adapter->mgmt, MGMT_OP_USER_PASSKEY_NEG_REPLY,
					adapter->dev_id, sizeof(cp), &cp,
					NULL, NULL, NULL);
	} else {
		struct mgmt_cp_user_passkey_reply cp;

		memset(&cp, 0, sizeof(cp));
		bacpy(&cp.addr.bdaddr, bdaddr);
		cp.addr.type = bdaddr_type;
		cp.passkey = htobl(passkey);

		id = mgmt_reply(adapter->mgmt, MGMT_OP_USER_PASSKEY_REPLY,
					adapter->dev_id, sizeof(cp), &cp,
					NULL, NULL, NULL);
	}

	if (id == 0)
		return -EIO;

	return 0;
}

static void user_passkey_request_callback(uint16_t index, uint16_t length,
					const void *param, void *user_data)
{
	const struct mgmt_ev_user_passkey_request *ev = param;
