import os
from subprocess import check_call

def test_make_icsv_smoke(tmp_path):
    src = tmp_path / "sample.csv"
    src.write_text("""timestamp,temp_C,RH,station_id,lat,lon
2021-01-01T00:00:00,2.5,0.41,ST001,46.95,7.44
2021-01-01T01:00:00,2.3,0.40,ST001,46.95,7.44
""", encoding="utf-8")

    out_icsv = tmp_path / "sample.icsv"
    out_schema = tmp_path / "sample_schema.json"
    # invoke the script (assumes python in PATH and script is in repo root)
    check_call(["python", "make_icsv.py", str(src), "--out", str(out_icsv), "--schema-out", str(out_schema)])
    assert out_icsv.exists()
    assert out_schema.exists()
