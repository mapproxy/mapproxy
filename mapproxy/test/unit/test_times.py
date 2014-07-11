from mapproxy.util.times import timestamp_from_isodate


def test_timestamp_from_isodate():
    ts = timestamp_from_isodate('2009-06-09T10:57:00')
    assert (1244537820.0 - 14 * 3600) < ts < (1244537820.0 + 14 * 3600)

    try:
        timestamp_from_isodate('2009-06-09T10:57')
    except ValueError:
        pass
    else:
        assert False, 'expected ValueError'
