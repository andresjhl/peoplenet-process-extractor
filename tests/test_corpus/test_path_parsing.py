"""Tests for corpus path parsing and PeopleNet structure recognition."""

from peoplenet_process_extractor.corpus.path_parsing import (
    normalize_path,
    parse_peoplenet_path,
    parse_rule_filename,
)


class TestNormalizePath:
    def test_forward_slashes_unchanged(self):
        assert normalize_path("a/b/c") == "a/b/c"

    def test_backslashes_converted(self):
        assert normalize_path("a\\b\\c") == "a/b/c"

    def test_mixed_slashes(self):
        assert normalize_path("a/b\\c/d") == "a/b/c/d"


class TestParseRuleFilename:
    def test_valid_rule_filename(self):
        rule_id, rule_date, warnings = parse_rule_filename("TEST_METHOD#R1#1800_01_01.ln4")
        assert rule_id == "R1"
        assert rule_date == "1800_01_01"
        assert warnings == []

    def test_no_hash_separators(self):
        rule_id, rule_date, warnings = parse_rule_filename("INCOMPLETE.ln4")
        assert rule_id is None
        assert rule_date is None
        assert len(warnings) == 1
        assert "no '#' separators" in warnings[0]

    def test_one_hash_separator(self):
        rule_id, rule_date, warnings = parse_rule_filename("NAME#R1.ln4")
        assert rule_id is None
        assert rule_date is None
        assert len(warnings) == 1

    def test_too_many_hash_separators(self):
        rule_id, rule_date, warnings = parse_rule_filename("A#B#C#D.ln4")
        assert rule_id is None
        assert rule_date is None
        assert len(warnings) == 1
        assert "unexpected '#' count" in warnings[0]

    def test_case_insensitive_extension(self):
        rule_id, rule_date, _ = parse_rule_filename("NAME#R1#2020_01_01.LN4")
        assert rule_id == "R1"
        assert rule_date == "2020_01_01"


class TestParsePeoplenetPath:
    def test_structured_method_path(self):
        path = "CP/NODE STRUCTURE/TEST_OBJECT/ITEM/METHOD/TEST_METHOD/RULES/TEST_METHOD#R1#1800_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "CP"
        assert structure is not None
        assert structure.meta4object == "TEST_OBJECT"
        assert structure.item_type == "METHOD"
        assert structure.item_name == "TEST_METHOD"
        assert structure.rule_id == "R1"
        assert structure.rule_date == "1800_01_01"
        assert warnings == []

    def test_structured_concept_path(self):
        path = "CP/NODE STRUCTURE/TEST_OBJECT/ITEM/CONCEPT/TEST_CONCEPT/RULES/TEST_CONCEPT#R1#1800_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "CP"
        assert structure is not None
        assert structure.item_type == "CONCEPT"
        assert structure.item_name == "TEST_CONCEPT"

    def test_other_item_type(self):
        path = "GTO/NODE STRUCTURE/OBJ/ITEM/CUSTOM_TYPE/MY_ITEM/RULES/MY_ITEM#R5#2024_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert structure is not None
        assert structure.item_type == "CUSTOM_TYPE"

    def test_unknown_root_structured(self):
        path = "UNKNOWN_ROOT/NODE STRUCTURE/THIRD_OBJECT/ITEM/METHOD/THIRD_METHOD/RULES/THIRD_METHOD#R1#2024_06_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "UNKNOWN_ROOT"
        assert structure is not None

    def test_file_at_corpus_root(self):
        path = "outside_structure.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root is None
        assert structure is None
        assert warnings == []

    def test_path_with_spaces(self):
        path = "name with spaces.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root is None
        assert structure is None

    def test_file_in_source_root_no_node_structure(self):
        path = "CP/some_file.json"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "CP"
        assert structure is None

    def test_incomplete_rule_name_warns(self):
        path = "CP/NODE STRUCTURE/OBJ/ITEM/METHOD/MY_METHOD/RULES/INCOMPLETE_METHOD.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "CP"
        assert structure is not None
        assert structure.rule_id is None
        assert structure.rule_date is None
        assert len(warnings) == 1

    def test_wrong_node_structure_label(self):
        path = "CP/node_structure/OBJ/ITEM/METHOD/MY_METHOD/RULES/FILE#R1#2020_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "CP"
        assert structure is None

    def test_wrong_item_label(self):
        path = "CP/NODE STRUCTURE/OBJ/ITEMS/METHOD/MY_METHOD/RULES/FILE#R1#2020_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert structure is None

    def test_wrong_rules_label(self):
        path = "CP/NODE STRUCTURE/OBJ/ITEM/METHOD/MY_METHOD/RULE/FILE#R1#2020_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert structure is None

    def test_too_shallow_path(self):
        path = "CP/NODE STRUCTURE/OBJ/ITEM/METHOD/MY_METHOD/RULES"
        # 7 parts — not enough
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert structure is None

    def test_windows_path_normalized(self):
        path = "CP\\NODE STRUCTURE\\OBJ\\ITEM\\METHOD\\MY_METHOD\\RULES\\MY_METHOD#R1#2020_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert source_root == "CP"
        assert structure is not None
        assert structure.item_type == "METHOD"

    def test_names_with_spaces_in_object(self):
        path = "GTO/NODE STRUCTURE/MY OBJECT/ITEM/METHOD/MY METHOD/RULES/MY METHOD#R1#2020_01_01.ln4"
        source_root, structure, warnings = parse_peoplenet_path(path)
        assert structure is not None
        assert structure.meta4object == "MY OBJECT"
        assert structure.item_name == "MY METHOD"
