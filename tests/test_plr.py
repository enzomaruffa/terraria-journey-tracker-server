import struct

import pytest

from plr_fixture import build_plr, write_string
from terraria_tracker.plr.crypto import DecryptionError, decrypt_player_file, encrypt_player_file
from terraria_tracker.plr.player import PlayerFileError, parse_player
from terraria_tracker.plr.reader import BinaryReader, BinaryReadError


class TestReader:
    def test_7bit_encoded_int_round_trip(self):
        from plr_fixture import write_7bit_encoded_int

        for value in (0, 1, 127, 128, 255, 300, 16_383, 16_384, 1_000_000):
            reader = BinaryReader(write_7bit_encoded_int(value))
            assert reader.read_7bit_encoded_int() == value

    def test_reads_strings_longer_than_127_bytes(self):
        """The old parser used a single length byte, which truncated anything longer."""
        text = "A" * 400
        assert BinaryReader(write_string(text)).read_string() == text

    def test_reads_non_ascii(self):
        assert BinaryReader(write_string("Kröte ✦")).read_string() == "Kröte ✦"

    def test_rejects_a_short_read(self):
        with pytest.raises(BinaryReadError):
            BinaryReader(b"\x02").read(4)


class TestCrypto:
    def test_round_trip(self):
        plain = b"terraria" * 4
        assert decrypt_player_file(encrypt_player_file(plain)).startswith(plain)

    def test_rejects_empty_file(self):
        with pytest.raises(DecryptionError):
            decrypt_player_file(b"")

    def test_rejects_a_truncated_file(self):
        with pytest.raises(DecryptionError, match="not a multiple"):
            decrypt_player_file(b"\x00" * 17)


class TestParsePlayer:
    def test_reads_header_fields(self, sample_research, game_data):
        raw = build_plr(name="Enzo", difficulty=3, file_version=279, research=sample_research)
        save = parse_player(raw, known_names=game_data.internal_names)

        assert save.name == "Enzo"
        assert save.difficulty_name == "journey"
        assert save.is_journey
        assert save.file_version == 279

    def test_finds_research_behind_arbitrary_filler(self, sample_research, game_data):
        """The whole point of the scanner: the offset of the table is never assumed."""
        for filler in (0, 500, 3000, 12_000):
            raw = build_plr(research=sample_research, filler_before=filler, seed=filler + 1)
            save = parse_player(raw, known_names=game_data.internal_names)

            assert save.research_found
            assert save.research == sample_research

    def test_verifies_against_the_stored_entry_count(self, sample_research, game_data):
        raw = build_plr(research=sample_research)
        assert parse_player(raw, known_names=game_data.internal_names).research_verified

    def test_survives_a_future_file_layout(self, sample_research, game_data):
        """A Terraria update that moves the table is a no-op for us."""
        raw = build_plr(research=sample_research, file_version=999, filler_before=40_000)
        save = parse_player(raw, known_names=game_data.internal_names)

        assert save.research == sample_research

    def test_ignores_a_decoy_run_shorter_than_the_threshold(self, sample_research, game_data):
        """A few item-shaped bytes elsewhere in the file must not outvote the real table."""
        decoy = b"".join(write_string(name) + struct.pack("<i", 7) for name in list(sample_research)[:4])

        plain = build_plr(research=sample_research, filler_before=200, filler_after=200, encrypt=False)
        spliced = plain[:100] + decoy + plain[100:]

        save = parse_player(encrypt_player_file(spliced), known_names=game_data.internal_names)

        assert save.research == sample_research

    def test_rejects_a_file_that_is_not_a_character(self):
        with pytest.raises(PlayerFileError, match="relogic"):
            parse_player(encrypt_player_file(b"\x00" * 512))

    def test_reports_when_there_is_no_research_table(self, game_data):
        raw = build_plr(research={}, filler_before=2000)
        save = parse_player(raw, known_names=game_data.internal_names)

        assert not save.research_found
        assert save.research == {}

    def test_non_journey_character_is_flagged(self, sample_research, game_data):
        raw = build_plr(difficulty=0, research=sample_research)
        save = parse_player(raw, known_names=game_data.internal_names)

        assert not save.is_journey
        assert save.difficulty_name == "classic"
