		if (!uuid_str)
			continue;
		eir->services = queue_append(eir->services, uuid_str);
		uuid_ptr += 16;
	}
}

static void eir_parse_msd(struct eir_data *eir, const uint8_t *data,
								uint8_t len)
{
	struct eir_msd *msd;

	if (len < 2 || len > 2 + sizeof(msd->data))
		return;

	msd = g_malloc(sizeof(*msd));
	msd->company = get_le16(data);
	msd->data_len = len - 2;
	memcpy(&msd->data, data + 2, msd->data_len);

	eir->msd_list = queue_append(eir->msd_list, msd);
}

static void eir_parse_sd(struct eir_data *eir, uuid_t *service,
