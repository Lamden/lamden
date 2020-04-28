from cilantro_ee.crypto.wallet import Wallet


def build_nodes(num_nodes=1) -> list:
    nodes = []
    for i in range(num_nodes):
        i = Wallet()
        nodes.append({'sk': i.signing_key(as_hex=True), 'vk': i.verifying_key(as_hex=True)})

    print(nodes)


def main():
    num_keys = input('Num key pair gen:')
    build_nodes(int(num_keys))


if __name__ == "__main__" :
    main()