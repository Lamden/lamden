def _get_input(prompt, skip=False):
    if skip:
        return 0
    else:
        return input(prompt)


def main():
    config_name = input("Enter the name of this configuration (ex cloud-2-2-2)")

    num_mn = int(input("Enter number of Masternodes"))
    assert num_mn > 0, "num_mn must be greater than 0"

    num_dels = int(input("Enter number of Delegates"))
    assert num_dels > 0, "num_dels must be greater than 0"

    num_wits = int(input("Enter number of Witnesses"))
    assert num_wits > 0, "num_wits must be greater than 0"

    # TODO create config files here

    skip = input("Use default values for rest of config? (y/n)") or 'n'
    if skip.lower() == 'y':
        skip = True
        print("Using default values for remaining inputs")
    else:
        skip = False

    reset_db = _get_input("Reset DB on all nodes upon boot? (y/n), default='y'", skip=skip) or 'y'
    assert reset_db.lower() in ('y', 'n'), "invalid reset_db val. Must be 'y' or 'n'"
    reset_db = True if reset_db.lower() == 'y' else False

    ssl_enabled = _get_input("Enable SSL on Webservers? (y/n), default='y'", skip=skip) or 'y'
    assert ssl_enabled.lower() in ('y', 'n'), "invalid ssl_enabled val. Must be 'y' or 'n'"
    ssl_enabled = True if ssl_enabled.lower() == 'y' else False

    nonce_enabled = _get_input("Require nonces for user transactions? (y/n), default='n'", skip=skip) or 'n'
    assert nonce_enabled.lower() in ('y', 'n'), "invalid nonce_enabled val. Must be 'y' or 'n'"
    nonce_enabled = True if nonce_enabled.lower() == 'y' else False

    mn_log_lvl = _get_input("Enter Masternode log lvl. Must be 0 or in [11, 100]. (default=11)", skip=skip) or 11
    assert mn_log_lvl >= 0, 'log lvl must be greater than 0'
    assert mn_log_lvl not in range(1, 11), "Masternode log cannot be in range [1, 10]"

    wit_log_lvl = int(_get_input("Enter Witness log lvl.) (default=11)", skip=skip)) or 11
    assert wit_log_lvl >= 0, 'log lvl must be greater than 0'

    del_log_lvl = int(_get_input("Enter Delegate log lvl). (default=11)", skip=skip)) or 11
    assert del_log_lvl >= 0, 'log lvl must be greater than 0'

    sen_log_lvl = int(_get_input("Enter Seneca log lvl. )(default=11)", skip=skip)) or 11
    assert sen_log_lvl >= 0, 'log lvl must be greater than 0'


if __name__ == '__main__':
    main()