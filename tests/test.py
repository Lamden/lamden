CAP = 26


def num_ways(msg: str) -> int:
    # return _num_ways(msg, 0, set())
    return _num_ways(msg)


# def _num_ways(msg: str, i) -> int:
#     if len(msg) == 0:
#         return 0
#     elif len(msg) == 1:
#         return 1
#
#     count = 1 + _num_ways(msg[i+1:])
#     if msg[i:i+1] <= CAP:
#         count += 1 + _num_ways(msg[i:])

def _num_ways(msg: str) -> int:
    if len(msg) == 0:
        return 1
    elif len(msg) == 1:
        return 1

    count = _num_ways(msg[2:])
    if len(msg) > 2 and int(msg[:2]) <= CAP:
        count += _num_ways(msg[1:])

    return count

if __name__ == '__main__':
    # inp = "1234"
    # inp = "12"
    inp = "123"
    print(num_ways(inp))


"""
123

1 2 3 
1 23
12 3 
 
"""

"""
1234

1 2 3 4
1 23 4
12 3 4
 
"""

"""
1234

1, ways(234) (2)
12, + ways(34) (1)


234

2, ways(34) (1)
23, ways(4) (1)
"""

"""
12345
1 2 3 4 5
1 23 4 5
12 3 4 5
 
"""

"""
12345

1, ways(2345) (2)
12, + ways(345) (1)


234

+1 [2], ways(345) (1)
23, ways(45) (1)


345
+1 [3], ways 45 (1)
[X] 34 not an option ....
"""
