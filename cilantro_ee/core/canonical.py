

def format_dictionary(d: dict) -> dict:
    for k, v in d.items():
        assert type(k) == str, 'Non-string key types not allowed.'
        if isinstance(v, dict):
            format_dictionary(v)
        elif isinstance(v, bytes):
            d[k] = v.hex()
        return {k: v for k, v in sorted(d.items())}

