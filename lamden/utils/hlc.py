from hlcpy import HLC

def nanos_from_hlc_timestamp(hlc_timestamp: str) -> int:
    try:
        hlc = HLC.from_str(hlc_timestamp)
        return hlc.nanos
    except:
        return 0