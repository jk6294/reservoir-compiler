from pyres import std


def main():
    n3o1 = None
    n3o2 = None
    n1o1, n1o2, n1go = std.nor3(n3o1, n3o2)
    n2o1, n2o2, n2go = std.nor3(n1o1, n1o2)
    n3o1, n3o2, n3go = std.nor3(n2o1, n2o2)
    return n1go, n2go, n3go
