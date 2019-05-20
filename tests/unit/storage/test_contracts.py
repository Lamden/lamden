# TODO revive these


from unittest import TestCase
import unittest
from unittest import mock
from cilantro_ee.storage.contracts import *
from cilantro_ee.storage.driver import SafeDriver
from cilantro_ee.protocol import wallet
from contracting.execution.executor import Executor


TEST_WALLET1 = wallet.new()
TEST_WALLET2 = wallet.new()

