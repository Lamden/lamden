from cilantro.messages import MessageBase, MessageMeta
import capnp
import command_capnp


class ReactorCommand(MessageBase):

    def serialize(self) -> bytes:
        if not self._data:
            raise Exception("internal attribute _data not set.")
        return self._data.as_builder().to_bytes()

    def validate(self):
        # TODO implement
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return command_capnp.CpDict.from_bytes(data)

    @classmethod
    def create(cls, class_name: str, func_name: str, metadata: MessageMeta=None, data: MessageBase=None, **kwargs):
        cmd = command_capnp.ReactorCommand.new_message()

        cmd.className = class_name
        cmd.funcName = func_name

        if metadata:
            # Sanity checks (we should probably remove these in production)
            assert metadata and data, "If creating command with a binary payload, " \
                                      "BOTH metadata and data must be passed in (not one or the other)"
            assert

        cmd.init('kwargs', len(kwargs))
        i = 0
        for key, value in kwargs.items():
            cmd.kwargs[i].key, cmd.kwargs[i].value = str(key), str(value)
            i += 1

        return cls.from_data(cmd)

    @property
    def class_name(self):
        return self._data.className

    @property
    def func_name(self):
        return self._data.funcName

    @property
    def kwargs(self):
        print("building kwargs for command {}".format(self))  # just for debugging, remove this later
        args = {}
        for arg in self._data.kwargs:
            args[arg.key] = arg.value
        return args

