/* [recorte do teste: linhas do fonte omitidas aqui] */
	/* Is there are no clients the discovery must have been stopped while
	 * discovery command was pending.
	 */
	if (!adapter->discovery_list) {
		struct mgmt_cp_stop_discovery cp;

		if (status != MGMT_STATUS_SUCCESS)
			return;

		/* Stop discovering as there are no clients left */
		cp.type = rp->type;
		mgmt_send(adapter->mgmt, MGMT_OP_STOP_DISCOVERY,
					adapter->dev_id, sizeof(cp), &cp,
					NULL, NULL, NULL);
		return;
	}

/* [recorte do teste: linhas do fonte omitidas aqui] */
	adapter->exps = queue_new();
	adapter->exp_pending = queue_new();

	return btd_adapter_ref(adapter);
}

static void adapter_remove(struct btd_adapter *adapter)
{
	GSList *l;
	struct gatt_db *db;

	DBG("Removing adapter %s", adapter->path);

	g_slist_free(adapter->connect_list);
	adapter->connect_list = NULL;

	for (l = adapter->devices; l; l = l->next) {
		device_removed_drivers(adapter, l->data);
		device_remove(l->data, FALSE);
	}

	g_slist_free(adapter->devices);
	adapter->devices = NULL;

	discovery_cleanup(adapter, 0);

	unload_drivers(adapter);

	db = btd_gatt_database_get_db(adapter->database);
	gatt_db_unregister(db, adapter->db_id);
	adapter->db_id = 0;
/* [recorte do teste: linhas do fonte omitidas aqui] */
struct agent *adapter_get_agent(struct btd_adapter *adapter)
{
	return agent_get(NULL);
}

static void adapter_remove_connection(struct btd_adapter *adapter,
						struct btd_device *device,
						uint8_t bdaddr_type,
						uint8_t reason)
{
	bool remove_device = false;

	DBG("");

	if (!g_slist_find(adapter->connections, device)) {
		btd_error(adapter->dev_id, "No matching connection for device");
		return;
	}

	device_remove_connection(device, bdaddr_type, &remove_device, reason);

	device_cancel_authentication(device, TRUE);
/* [recorte do teste: linhas do fonte omitidas aqui] */

	adapter->connections = g_slist_remove(adapter->connections, device);

	if (remove_device) {
		const char *path = device_get_path(device);

		DBG("Removing temporary device %s", path);
		btd_adapter_remove_device(adapter, device);
	}
}

static void adapter_stop(struct btd_adapter *adapter)
{
	/* check pending requests */
	reply_pending_requests(adapter);

	cancel_passive_scanning(adapter);
/* [recorte do teste: linhas do fonte omitidas aqui] */
	set_discovery_discoverable(adapter, false);
	adapter->discovering = false;

	while (adapter->connections) {
		struct btd_device *device = adapter->connections->data;
		uint8_t addr_type = btd_device_get_bdaddr_type(device);

		adapter_remove_connection(adapter, device, BDADDR_BREDR,
						MGMT_DEV_DISCONN_UNKNOWN);
		if (addr_type != BDADDR_BREDR)
			adapter_remove_connection(adapter, device, addr_type,
						MGMT_DEV_DISCONN_UNKNOWN);
	}

	g_dbus_emit_property_changed(dbus_conn, adapter->path,
					ADAPTER_INTERFACE, "Discovering");

	if (adapter->dev_class) {
		/* the kernel should reset the class of device when powering
		 * down, but it does not. So force it here ... */
/* [recorte do teste: linhas do fonte omitidas aqui] */
	char dst[18];

	ba2str(&addr->bdaddr, dst);

	DBG("Device %s disconnected, reason %u", dst, reason);

	device = btd_adapter_find_device(adapter, &addr->bdaddr, addr->type);
	if (device) {
		adapter_remove_connection(adapter, device, addr->type, reason);
		disconnect_notify(device, reason);
	}

	/* device could be still connected to different bearer */
	if (!device || !btd_device_is_connected(device))
		bonding_attempt_complete(adapter, &addr->bdaddr, addr->type,
						MGMT_STATUS_DISCONNECTED);
}
/* [recorte do teste: linhas do fonte omitidas aqui] */
