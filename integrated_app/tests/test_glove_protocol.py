import struct
import unittest
from unittest.mock import patch

from gesture_sources import (
    GloveGestureSource,
    PACKET_FLAG_RECENTER,
    PACKET_FORMAT_V1,
    PACKET_FORMAT_V2,
    PACKET_FORMAT_VERSIONED_V2,
    PACKET_FORMAT_V3,
    PACKET_VERSION_V2,
    PACKET_VERSION_V3,
)


class GloveProtocolTests(unittest.TestCase):
    def setUp(self):
        self.glove = GloveGestureSource()

    def notify(self, payload):
        with patch("gesture_sources.setting", side_effect=self._setting):
            self.glove._on_notification(None, bytearray(payload))

    @staticmethod
    def _setting(section, key):
        values = {
            ("glove_logging", "enabled"): False,
            ("pulse", "valid_min"): 35,
            ("pulse", "valid_max"): 220,
        }
        return values[(section, key)]

    def test_v3_packet_updates_sensors_and_pulse(self):
        payload = struct.pack(
            PACKET_FORMAT_V3, PACKET_VERSION_V3, 0,
            10, 20, 30, 40, 50, 100, -200, 300, 72,
        )
        self.notify(payload)
        self.assertEqual(self.glove.pulse_bpm, 72.0)
        self.assertGreater(self.glove._latest_flex[0], 0)

    def test_v3_recenter_flag_resets_pointer(self):
        self.glove._pointer_x = 0.8
        self.glove._pointer_y = 0.2
        payload = struct.pack(
            PACKET_FORMAT_V3, PACKET_VERSION_V3, PACKET_FLAG_RECENTER,
            0, 0, 0, 0, 0, 900, 900, 0, 0,
        )
        self.notify(payload)
        self.assertEqual((self.glove._pointer_x, self.glove._pointer_y), (0.5, 0.5))

    def test_legacy_packets_remain_supported(self):
        self.notify(struct.pack(PACKET_FORMAT_V1, 1, 2, 3, 4, 5, 0, 0, 0))
        self.notify(struct.pack(PACKET_FORMAT_V2, 1, 2, 3, 4, 5, 0, 0, 0, 80))
        self.assertEqual(self.glove.pulse_bpm, 80.0)

    def test_versioned_v2_packet_remains_supported(self):
        self.notify(struct.pack(
            PACKET_FORMAT_VERSIONED_V2, PACKET_VERSION_V2,
            1, 2, 3, 4, 5, 0, 0, 0, 81,
        ))
        self.assertEqual(self.glove.pulse_bpm, 81.0)


if __name__ == "__main__":
    unittest.main()
