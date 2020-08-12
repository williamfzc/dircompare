from dircompare import compare


def test_compare():
    assert compare("dirs/dir1", "dirs/dir2")
