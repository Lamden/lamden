import random, string

def random_password():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=64))

if __name__ == '__main__':
    print(random_password())
