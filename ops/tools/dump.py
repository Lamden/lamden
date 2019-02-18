from cilantro.utils.test.dumpatron import Dumpatron
import sys

SSL_ENABLED = False  # TODO make this infered instead of a hard coded flag


if __name__ == '__main__':
    assert len(sys.argv) >= 2, "Expected at least 1 arg -- the path of the environment to use"
    env_path = sys.argv[1]

    mr_dump = Dumpatron(env_path)
    mr_dump.start_interactive_dump()

