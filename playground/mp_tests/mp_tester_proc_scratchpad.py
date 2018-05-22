class MPTesterProcess:
    """
    We create the blocking tester object, and configure it with mock objects using a function passed in
    Then, we ensure futures __recv_cmd() to read from cmd_self.socket for proxy'd commands, and __check_assertions() to
    check assertions on a scheduled basis until they complete or until we get a SIG_ABORT from main thread
    """

    def __init__(self, name, url, build_fn, config_fn, assert_fn):
        self.config_fn = config_fn
        self.assert_fn = assert_fn
        self.url = url
        self.log = get_logger("TesterProc[{}]".format(name))

        self.tester_obj, self.loop = build_fn()
        assert isinstance(self.loop, asyncio.AbstractEventLoop), \
            "Got {} that isn't an instance of asyncio.AbstractEventLoop".format(self.loop)

        asyncio.set_event_loop(self.loop)

        # Connect to parent process over ipc PAIR self.socket
        self.ctx = zmq.asyncio.Context()
        self.socket = self.ctx.socket(socket_type=zmq.PAIR)
        self.socket.connect(self.url)

        if self.config_fn:
            tester_obj = self.config_fn(self.tester_obj)

        self._start_test()

    async def _recv_cmd(self):
        """
        Receive commands from the main process and execute them on the tester object. If cmd is equal to ABORT_SIG,
        then we execute __teardown() to stop this self.loop. If its an SIG_START, we start polling for assertions.
        Otherwise, cmd is assumed to be a a tuple of command info of the format
        (func_name: str, args: list, kwargs: dict).
        """
        while True:
            cmd = await self.socket.recv_pyobj()  # recv commands/events from test orchestrator

            # If we got a SIG_ABORT, tear this bish down
            if cmd == SIG_ABORT:
                # self.log.critical("\n!!!!!\nGOT ABORT SIG\n!!!!!\n")
                errs = self._assertions()
                if errs:
                    self.log.critical("\n\n{0}\nASSERTIONS FAILED FOR {2}:\n{1}\n{0}\n".format('!' * 120, errs, name))
                self._teardown()
                return

            # If we got a SIG_START, start polling for assertions (if self.assert_fn passed in)
            elif cmd == SIG_START:
                self.log.critical("Got SIG_START from test orchestrator")
                if self.assert_fn:
                    self.log.critical("\nStarting to check assertions every {} seconds\n".format(ASSERTS_POLL_FREQ))
                    asyncio.ensure_future(self._check_assertions())
                continue

            # If msg is not a signal, we assume its a command tuple of form (func, args, kwargs)
            assert len(
                cmd) == 3, "Expected command tuple of len 3 with form (func: str, args: list, kwargs: dict) but " \
                           "got {}".format(cmd)
            func, args, kwargs = cmd

            # Execute cmd in a try/catch, and send a SIG_FAIL to test orchestrator proc if something blow up
            try:
                output = getattr(self.tester_obj, func)(*args, **kwargs)

                # If result is coroutine, run it in the event self.loop
                if output and inspect.iscoroutine(output):
                    self.log.debug("Coroutine detect for func name {}, running it in event self.loop".format(func))
                    result = await asyncio.ensure_future(output)
                    self.log.debug("Got result from coroutine {}\nresult: {}".format(func, result))
                # self.log.critical("got cmd: {}".format(cmd))
                # self.log.critical("cmd name: {}\nkwargs: {}".format(func, kwargs))
            except Exception as e:
                self.log.error("\n\n TESTER GOT EXCEPTION: {}\n\n".format(traceback.format_exc()))
                self.socket.send_pyobj(SIG_FAIL)
                self._teardown()
                return

    async def _check_assertions(self):
        """
        Schedule assertion check every TEST_CHECK_FREQ seconds, until either:
            1) The assertions exceed, in which case we send a success signal SUCC_SIG to main thread
            2) The assertions timeout, in which case we send a fail signal FAIL_SIG to main thread
            3) We get can abort cmd (read in __recv_cmd), in which case we send an ABORT_SIG to main thread

        Once one one of these conditions is met, the corresponding signal is sent to the main thread as this
        process calls __teardown() cleans up the event self.loop.
        """
        self.log.debug("Starting assertion checks")

        # Run assertions for until either case (1) or (2) described above occurs
        while True:
            if self._assertions() is None:
                break

            # Sleep until next assertion check
            await asyncio.sleep(ASSERTS_POLL_FREQ)

        # Once out of the assertion checking self.loop, send success to main thread
        self.log.debug("\n\nassertions passed! putting ready sig in queue\n\n")
        self.socket.send(SIG_SUCC)

    def _teardown(self):
        """
        Stop all tasks and close this processes event self.loop. Invoked after we successfully pass all assertions, or
        timeout.
        """
        self.log.info("Tearing down")
        # self.log.info("Closing pair self.socket")
        self.socket.close()
        # self.log.info("Stopping self.loop")
        self.loop.stop()

    def _start_test(self):
        """
        Sends ready signal to parent process, and then starts the event self.loop in this process
        """
        self.log.debug("sending ready sig to parent")
        self.socket.send_pyobj(SIG_RDY)

        # asyncio.ensure_future(__recv_cmd())
        # if self.assert_fn:
        #     asyncio.ensure_future(__check_assertions())

        self.log.debug("starting tester proc event self.loop")
        self.loop.run_until_complete(self._recv_cmd())

    def _assertions(self):
        """
        Helper method to run tester object's assertions, and return the error raised as a string, or None if no
        assertions are raised
        """
        if not self.assert_fn:
            return None

        try:
            self.assert_fn(self.tester_obj)
            return None
        except Exception as e:
            return str(e)