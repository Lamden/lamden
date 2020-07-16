from unittest import TestCase
from lamden.formatting import primatives, rules


class TestFormatting(TestCase):
    def test_dict_has_keys_true(self):
        good_dict = {'a': 1, 'b': 2}

        self.assertTrue(primatives.dict_has_keys(good_dict, {'a', 'b'}))

    def test_dict_has_keys_false(self):
        bad_dict = {'a': 1, 'b': 2}

        self.assertFalse(primatives.dict_has_keys(bad_dict, {'a', 'x'}))

    def test_dict_has_keys_false_other_dict(self):
        bad_dict = {'a': 1, 'b': 2, 'x': 5}

        self.assertFalse(primatives.dict_has_keys(bad_dict, {'a', 'x'}))

    def test_identifier_is_formatted_passes(self):
        self.assertTrue(primatives.identifier_is_formatted('hello_there'))

    def test_identifier_starts_with_underscore_fails(self):
        self.assertFalse(primatives.identifier_is_formatted('_hello_there'))

    def test_identifier_not_string_fails(self):
        self.assertFalse(primatives.identifier_is_formatted(None))

    def test_contract_name_is_formatted_passes(self):
        self.assertTrue(primatives.contract_name_is_formatted('con_hello_there'))

    def test_contract_name_starts_with_underscore_fails(self):
        self.assertFalse(primatives.contract_name_is_formatted('_con_hello_there'))

    def test_contract_name_not_starting_with_con_fails(self):
        self.assertFalse(primatives.contract_name_is_formatted('hello_there'))

    def test_contract_name_not_string_fails(self):
        self.assertFalse(primatives.contract_name_is_formatted(None))

    def test_vk_formatted_passes(self):
        self.assertTrue(primatives.vk_is_formatted('a' * 64))

    def test_vk_too_long_fails(self):
        self.assertFalse(primatives.vk_is_formatted('a' * 65))

    def test_vk_too_short_fails(self):
        self.assertFalse(primatives.vk_is_formatted('a' * 63))

    def test_vk_not_hex_fails(self):
        self.assertFalse(primatives.vk_is_formatted('x' * 64))

    def test_vk_not_str_fails(self):
        self.assertFalse(primatives.vk_is_formatted(None))

    def test_vk_not_string_fails(self):
        self.assertFalse(primatives.signature_is_formatted(123))

    def test_signature_formatted_passes(self):
        self.assertTrue(primatives.signature_is_formatted('a' * 128))

    def test_signature_too_long_fails(self):
        self.assertFalse(primatives.signature_is_formatted('a' * 1234))

    def test_signature_too_short_fails(self):
        self.assertFalse(primatives.signature_is_formatted('a' * 12))

    def test_signature_not_hex_fails(self):
        self.assertFalse(primatives.signature_is_formatted('x' * 128))

    def test_signature_not_string_fails(self):
        self.assertFalse(primatives.signature_is_formatted(123))

    def test_number_is_formatted_passes(self):
        self.assertTrue(primatives.number_is_formatted(1))

    def test_neg_number_fails(self):
        self.assertFalse(primatives.number_is_formatted(-1))

    def test_non_number_fails(self):
        self.assertFalse(primatives.number_is_formatted('1'))

    def test_is_string(self):
        self.assertTrue(primatives.is_string('123'))

    def test_is_string_fail(self):
        self.assertFalse(primatives.is_string(1))

    def test_is_dict(self):
        self.assertTrue(primatives.is_dict({}))

    def test_is_dict_fails(self):
        self.assertFalse(primatives.is_dict(123))

    def test_is_ip(self):
        self.assertTrue(primatives.is_ip('127.0.0.1:18000'))

    def test_is_ip_no_port(self):
        self.assertFalse(primatives.is_ip('127.0.0.1'))

    def test_has_port_not_digit(self):
        self.assertFalse(primatives.is_ip('127.0.0.1:X'))

    def test_has_port_more_than_2_components(self):
        self.assertFalse(primatives.is_ip('127.0.0.1:4444:5555'))

    def test_has_port_less_than_1024(self):
        self.assertFalse(primatives.is_ip('127.0.0.1:1'))

    def test_has_port_more_than_65535(self):
        self.assertFalse(primatives.is_ip('127.0.0.1:99999'))

    def test_is_ip_not_string(self):
        self.assertFalse(primatives.is_ip(123))

    def test_is_ip_more_than_4_comps(self):
        self.assertFalse(primatives.is_ip('127.0.0.1.8:18000'))

    def test_is_ip_non_numerics(self):
        self.assertFalse(primatives.is_ip('127.0.X.1:18000'))

    def test_is_ip_greater_than_255(self):
        self.assertFalse(primatives.is_ip('127.999.0.1:18000'))

    def test_is_ip_less_than_0(self):
        self.assertFalse(primatives.is_ip('-127.0.0.1:18000'))

    def test_is_file_path(self):
        self.assertTrue(primatives.is_file_path('/tmp/feeds/0'))

    def test_is_file_path_not_string(self):
        self.assertFalse(primatives.is_file_path(123))

    def test_if_file_more_than_16_parts(self):
        self.assertFalse(primatives.is_file_path('/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a'))

    def test_if_file_not_alpha_num(self):
        self.assertFalse(primatives.is_file_path('/a/%!/a/'))

    def test_is_tcp_returns_true(self):
        self.assertTrue(primatives.is_tcp_or_ipc_string('tcp://127.0.0.1:18000'))

    def test_is_ipc_returns_true(self):
        self.assertTrue(primatives.is_tcp_or_ipc_string('ipc:///tmp/123'))

    def test_is_unsupported_returns_false(self):
        self.assertFalse(primatives.is_tcp_or_ipc_string('xxx://123.123.123:18000'))

    def test_kwargs_formatted_passes(self):
        d = {
            'asdf': 12,
            'Aghe': 44,
            'hello_there': 267
        }

        self.assertTrue(primatives.kwargs_are_formatted(d))

    def test_kwargs_not_identifier_types_fails(self):
        d = {
            True: 12,
            'Aghe': 44,
            'hello_there': 267
        }

        self.assertFalse(primatives.kwargs_are_formatted(d))

    def test_kwargs_not_formatted_fails(self):
        d = {
            '_asdf': 12,
            'Aghe': 44,
            'hello_there': 267
        }

        self.assertFalse(primatives.kwargs_are_formatted(d))

    def test_transaction_payload_formatted_passes(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertTrue(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_keys_unexpected(self):
        t = {
            'bad': 'key',
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_keys_missing(self):
        t = {
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_vk_sender_bad(self):
        t = {
            'sender': 'a' * 65,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_vk_processor_bad(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 65,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_stamps_bad(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': -123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_nonce_bad(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': -10,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_contract_bad(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 123,
            'function': 'transfer',
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_function(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 123,
            'kwargs': {
                'amount': 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_payload_fails_kwargs_bad(self):
        t = {
            'sender': 'a' * 64,
            'processor': 'b' * 64,
            'stamps_supplied': 123,
            'nonce': 0,
            'contract': 'currency',
            'function': 'transfer',
            'kwargs': {
                True: 123,
                'to': 'jeff'
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_PAYLOAD_RULES))

    def test_tx_metadata_passes(self):
        t = {
            'signature': 'a' * 128,
            'timestamp': 123
        }

        self.assertTrue(primatives.check_format(t, rules.TRANSACTION_METADATA_RULES))

    def test_tx_metadata_missing_key_fails(self):
        t = {
            'signature': 'a' * 128,
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_METADATA_RULES))

    def test_tx_metadata_extra_key_fails(self):
        t = {
            'signature': 'a' * 128,
            'timestamp': 123,
            'bad': 'key'
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_METADATA_RULES))

    def test_tx_metadata_timestamp_fails(self):
        t = {
            'signature': 'a' * 128,
            'timestamp': 'abc'
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_METADATA_RULES))

    def test_tx_passes(self):
        t = {
            'payload': {
                'sender': 'a' * 64,
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            },
            'metadata': {
                'signature': 'a' * 128,
                'timestamp': 123
            }
        }

        self.assertTrue(primatives.check_format(t, rules.TRANSACTION_RULES))

    def test_tx_fails_extra_key(self):
        t = {
            'bad': 'key',
            'payload': {
                'sender': 'a' * 64,
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            },
            'metadata': {
                'signature': 'a' * 128,
                'timestamp': 123
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_RULES))

    def test_tx_missing_key_fails(self):
        t = {
            'payload': {
                'sender': 'a' * 64,
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_RULES))

    def test_tx_fails_tx_payload(self):
        t = {
            'payload': {
                'sender': 'a' * 65,
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            },
            'metadata': {
                'signature': 'a' * 128,
                'timestamp': 123
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_RULES))

    def test_tx_fails_tx_metadata(self):
        t = {
            'payload': {
                'sender': 'a' * 64,
                'processor': 'b' * 64,
                'stamps_supplied': 123,
                'nonce': 0,
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': 123,
                    'to': 'jeff'
                }
            },
            'metadata': {
                'signature': 'a' * 129,
                'timestamp': 123
            }
        }

        self.assertFalse(primatives.check_format(t, rules.TRANSACTION_RULES))

    def test_list_recurses_returns_true(self):
        test_rule = {
            'sender': primatives.vk_is_formatted
        }

        thing = {
            'sender': [
                'a' * 64,
                'b' * 64,
                'c' * 64,
                'd' * 64,
                'e' * 64,
            ]
        }

        self.assertTrue(primatives.check_format(thing, test_rule))

    def test_rescurses_returns_false(self):
        test_rule = {
            'sender': primatives.vk_is_formatted
        }

        thing = {
            'sender': [
                'a' * 64,
                'b' * 64,
                'c' * 64,
                'd' * 64,
                'e' * 63,
            ]
        }

        self.assertFalse(primatives.check_format(thing, test_rule))