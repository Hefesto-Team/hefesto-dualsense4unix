	avdtp_remote_sep_set_destroy(rsep, sep, remote_sep_destroy);

done:
	queue_push_tail(chan->seps, sep);

	return sep;
}

static bool match_seid(const void *data, const void *user_data)
{
	const struct a2dp_remote_sep *sep = data;
	const uint8_t *seid = user_data;

	return avdtp_get_seid(sep->sep) == *seid;
}

static int match_sep(const void *data, const void *user_data)
{
	struct a2dp_sep *sep = (void *) data;
	const uint8_t *seid = user_data;

	return *seid - avdtp_sep_get_seid(sep->lsep);
}

static struct a2dp_sep *find_sep_by_seid(struct a2dp_server *server,
							uint8_t seid)
{
	GSList *l;

	l = g_slist_find_custom(server->sources, &seid, match_sep);
	if (l)
		return l->data;

	l = g_slist_find_custom(server->sinks, &seid, match_sep);
	if (l)
		return l->data;

	return NULL;
}

