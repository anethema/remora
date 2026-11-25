import pytest
from remora.scenario import LocalFrame, load, validate

@pytest.mark.parametrize("lat,lon", [(28.1,-110.1),(-35.1,149.1),(80.0,179.999)])
def test_round_trip(lat, lon):
    frame = LocalFrame(lat, lon)
    assert frame.en(*frame.gps(1200, -90)) == pytest.approx((1200,-90), abs=0.001)
    assert frame.gps(0,100)[0] > lat

@pytest.mark.parametrize("key,value", [("speedup",True),("loss",1.1),("drift_e_mps",float("nan")),
                                      ("schema_version", True),("seed",2.5),("live_port",5760)])
def test_invalid_fields(key, value):
    with pytest.raises(ValueError):
        validate({**load(), key:value})
