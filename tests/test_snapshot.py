from sanctions_screening.models import Entity, EntityType
from sanctions_screening.snapshot import read_snapshot, snapshot_path, write_snapshot


def make_entity(source_id: str) -> Entity:
    return Entity(
        source_id=source_id,
        list_name="OFAC SDN",
        list_version="2026-09-18",
        canonical_name="Acme Trading",
        entity_type=EntityType.COMPANY,
    )


class TestSnapshotPath:
    def test_slugifies_list_name(self):
        path = snapshot_path("/tmp/snaps", "OFAC SDN", "2026-09-18")
        assert path.name == "ofac_sdn_2026-09-18.jsonl"


class TestWriteAndReadSnapshot:
    def test_round_trips_entities(self, tmp_path):
        entities = [make_entity("OFAC-1"), make_entity("OFAC-2")]
        out_path = write_snapshot(entities, tmp_path, "OFAC SDN", "2026-09-18")

        assert out_path.exists()
        read_back = list(read_snapshot(out_path))
        assert [e.source_id for e in read_back] == ["OFAC-1", "OFAC-2"]
        assert read_back[0].entity_type is EntityType.COMPANY

    def test_one_json_object_per_line(self, tmp_path):
        entities = [make_entity("OFAC-1"), make_entity("OFAC-2"), make_entity("OFAC-3")]
        out_path = write_snapshot(entities, tmp_path, "OFAC SDN", "2026-09-18")
        lines = out_path.read_text().splitlines()
        assert len(lines) == 3

    def test_creates_out_dir_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b"
        out_path = write_snapshot([make_entity("OFAC-1")], nested, "OFAC SDN", "2026-09-18")
        assert out_path.exists()
