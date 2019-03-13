import os, sys
from cilantro_ee.constants.db_config import DATA_DIR


LEDIS_CONF_PATH = '/etc/ledis.conf'
LEDIS_DIR = DATA_DIR + '/ledis'


def start_ledis(conf_path):
    print("Starting Ledis server...")
    if not os.path.exists(LEDIS_DIR):
        print("Creating Ledis directory at {}".format(LEDIS_DIR))
        os.makedirs(LEDIS_DIR, exist_ok=True)

    print("Ledis using data directory: {}".format(LEDIS_DIR))

    if conf_path is None:
        os.system('ledis-server')
    else:
        assert os.path.exists(conf_path), "No Ledis.conf file found at path {}".format(conf_path)
        os.system('ledis-server -config={}'.format(conf_path))
    #
    # if conf_path is not None:
    #     if conf_path == '-no-conf':
    #         os.system('ledis-server')
    #     else:
    #         assert os.path.exists(conf_path), "No Ledis.conf file found at path {}".format(conf_path)
    #         os.system('ledis-server -config={}'.format(conf_path))
    # else:
    #     # No conf_path or '-no-conf' arg was specified
    #     os.system('ledis-server -config={}'.format(conf_path))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '-no-conf':
            start_ledis(None)
        else:
            start_ledis(sys.argv[1])
    else:
        start_ledis(LEDIS_CONF_PATH)

