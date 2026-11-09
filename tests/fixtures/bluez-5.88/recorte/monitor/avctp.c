#define AVRCP_SEARCH			0x80
#define AVRCP_ADD_TO_NOW_PLAYING	0x90
#define AVRCP_GENERAL_REJECT		0xA0

/* Packet types */
#define AVRCP_PACKET_TYPE_SINGLE	0x00
#define AVRCP_PACKET_TYPE_START		0x01
#define AVRCP_PACKET_TYPE_CONTINUING	0x02
#define AVRCP_PACKET_TYPE_END		0x03

/* player attributes */
#define AVRCP_ATTRIBUTE_ILLEGAL		0x00
#define AVRCP_ATTRIBUTE_EQUALIZER	0x01
#define AVRCP_ATTRIBUTE_REPEAT_MODE	0x02
#define AVRCP_ATTRIBUTE_SHUFFLE		0x03
#define AVRCP_ATTRIBUTE_SCAN		0x04

/* media attributes */
#define AVRCP_MEDIA_ATTRIBUTE_ILLEGAL	0x00
#define AVRCP_MEDIA_ATTRIBUTE_TITLE	0x01
#define AVRCP_MEDIA_ATTRIBUTE_ARTIST	0x02
#define AVRCP_MEDIA_ATTRIBUTE_ALBUM	0x03
#define AVRCP_MEDIA_ATTRIBUTE_TRACK	0x04
		return "Continuing";
	case AVRCP_PACKET_TYPE_END:
		return "End";
	default:
		return "Unknown";
	}
}

static const char *attr2str(uint8_t attr)
{
	switch (attr) {
	case AVRCP_ATTRIBUTE_ILLEGAL:
		return "Illegal";
	case AVRCP_ATTRIBUTE_EQUALIZER:
		return "Equalizer ON/OFF Status";
	case AVRCP_ATTRIBUTE_REPEAT_MODE:
		return "Repeat Mode Status";
	case AVRCP_ATTRIBUTE_SHUFFLE:
		return "Shuffle ON/OFF Status";
	case AVRCP_ATTRIBUTE_SCAN:
		return "Scan ON/OFF Status";
	default:
		return "Unknown";
	}
}

static const char *value2str(uint8_t attr, uint8_t value)
{
	switch (attr) {
	case AVRCP_ATTRIBUTE_ILLEGAL:
		return "Illegal";
	case AVRCP_ATTRIBUTE_EQUALIZER:
		switch (value) {
		case 0x01:
			return "OFF";
		case 0x02:
			return "ON";
		default:
			return "Reserved";
		}
	case AVRCP_ATTRIBUTE_REPEAT_MODE:
