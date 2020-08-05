import btree

# Storage of general persistent data
try:
    dbFile = open("db", "r+b")
except OSError:
    print('[BTREE] OSError')
    dbFile = open("db", "w+b")
db = btree.open(dbFile)


def byte_str_to_bool(string):
    if string == b'0':
        return False
    else:
        return True