from ..util import resolve_ns


def test_resolve_ns():
    assert resolve_ns("/bar/bar", {}, None) == "/bar/bar"

    assert (
        resolve_ns("/bar/bar", {}, "http://foo") == "/{http://foo}bar/{http://foo}bar"
    )

    assert (
        resolve_ns(
            "/bar/xlink:bar", {"xlink": "http://www.w3.org/1999/xlink"}, "http://foo"
        )
        == "/{http://foo}bar/{http://www.w3.org/1999/xlink}bar"
    )

    assert (
        resolve_ns(
            "bar/xlink:bar", {"xlink": "http://www.w3.org/1999/xlink"}, "http://foo"
        )
        == "{http://foo}bar/{http://www.w3.org/1999/xlink}bar"
    )
