import xplane_mcp


def test_package_version_is_defined():
    assert xplane_mcp.__version__
    assert isinstance(xplane_mcp.__version__, str)
