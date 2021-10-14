def obj_repr(o: object) -> str:
    """
    Returns a string representation of object, supports __slots__.
    """
    if hasattr(o, "__slots__"):
        d = {attr: getattr(o, attr, None) for attr in o.__slots__}
    else:
        d = o.__dict__
    return f"<{o.__class__.__name__}: {d}>"

def ensure(cond: bool, msg: str | None = None) -> None:
    if not cond:
        if msg is None:
            raise AssertionError
        else:
            raise AssertionError(msg)
